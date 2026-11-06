//! Runs `human_replay.wgsl` over recorded leaders. scripts/human_replay.py writes the input and scores the output.

use std::path::PathBuf;

use bytemuck::{Pod, Zeroable};
use cars_core::{Gpu, GpuOptions, demand::VType, world};
use clap::Parser;
use wgpu::util::DeviceExt;

#[derive(Parser)]
pub struct Args {
    /// Vehicles: rows of 12 values, see `RVeh`.
    #[arg(long)]
    veh: PathBuf,
    /// Recording: rows x samples x (x, v) of f32 at `rec_dt`.
    #[arg(long)]
    rec: PathBuf,
    #[arg(long)]
    samples: u32,
    #[arg(long, default_value_t = 0.1)]
    rec_dt: f32,
    #[arg(long, default_value_t = 0.1)]
    dt: f32,
    #[arg(long)]
    steps: u32,
    #[arg(long)]
    sigma: f32,
    #[arg(long, default_value_t = 5.0)]
    len_model: f32,
    #[arg(long, default_value_t = 5.0)]
    len_guard: f32,
    #[arg(long)]
    no_guard: bool,
    /// Every step's x and v for every vehicle, f32.
    #[arg(long)]
    out: PathBuf,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Default)]
struct RParams {
    dt: f32,
    n: u32,
    samples: u32,
    step: u32,
    per_sample: f32,
    hu_k: f32,
    hu_rho: f32,
    hu_nscale: f32,
    len_model: f32,
    len_guard: f32,
    guard_on: u32,
    pad: u32,
}

pub fn run(a: Args) {
    let g = pollster::block_on(Gpu::headless(GpuOptions { adapter_name: Some("7900".into()), ..Default::default() })).expect("gpu");
    let veh = std::fs::read(&a.veh).expect("veh");
    let rec = std::fs::read(&a.rec).expect("rec");
    let n = (veh.len() / 48) as u32;
    let types = [world::human_replay_type(&VType::default())];
    let mut p = RParams {
        dt: a.dt,
        n,
        samples: a.samples,
        step: 0,
        per_sample: a.dt / a.rec_dt,
        hu_k: 1.0 - (-a.dt).exp(),
        hu_rho: (-a.dt / 3.0).exp(),
        hu_nscale: a.sigma * (1.0 - (-2.0 * a.dt / 3.0).exp()).sqrt(),
        len_model: a.len_model,
        len_guard: a.len_guard,
        guard_on: !a.no_guard as u32,
        pad: 0,
    };
    let d = &g.device;
    let storage = wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC | wgpu::BufferUsages::COPY_DST;
    let init = |label, contents: &[u8]| d.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: Some(label), contents, usage: storage });
    let params = d.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: Some("rparams"), contents: bytemuck::bytes_of(&p), usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST });
    let buf = [init("a", &veh), init("b", &veh)];
    let rec_buf = init("rec", &rec);
    let type_buf = init("types", bytemuck::cast_slice(&types));
    let stats = init("stats", &[0u8; 16]);
    let common = std::env::var("CARS_SHADER_DIR").ok().and_then(|d| std::fs::read_to_string(format!("{d}/common.wgsl")).ok()).unwrap_or_else(|| cars_core::sim::COMMON.to_string());
    let source = format!("{common}\n{}", include_str!("../../cars-core/src/shaders/human_replay.wgsl"));
    let module = d.create_shader_module(wgpu::ShaderModuleDescriptor { label: Some("replay"), source: wgpu::ShaderSource::Wgsl(source.into()) });
    let pipeline = d.create_compute_pipeline(&wgpu::ComputePipelineDescriptor { label: Some("replay"), layout: None, module: &module, entry_point: Some("replay"), compilation_options: Default::default(), cache: None });
    let layout = pipeline.get_bind_group_layout(0);
    let group = |x: &wgpu::Buffer, y: &wgpu::Buffer| {
        d.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &layout,
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: params.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: x.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: y.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 3, resource: rec_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 4, resource: type_buf.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 5, resource: stats.as_entire_binding() },
            ],
        })
    };
    let groups = [group(&buf[0], &buf[1]), group(&buf[1], &buf[0])];
    let mut out = std::io::BufWriter::new(std::fs::File::create(&a.out).expect("out"));
    let stride = 48usize;
    let read = |b: &wgpu::Buffer| -> Vec<u8> {
        let staging = d.create_buffer(&wgpu::BufferDescriptor { label: None, size: b.size(), usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ, mapped_at_creation: false });
        let mut enc = d.create_command_encoder(&Default::default());
        enc.copy_buffer_to_buffer(b, 0, &staging, 0, b.size());
        g.queue.submit([enc.finish()]);
        let slice = staging.slice(..);
        slice.map_async(wgpu::MapMode::Read, |_| {});
        g.wait();
        let data = slice.get_mapped_range().unwrap().to_vec();
        data
    };
    use std::io::Write;
    let write_state = |out: &mut std::io::BufWriter<std::fs::File>, bytes: &[u8]| {
        for row in bytes.chunks(stride) {
            out.write_all(&row[0..8]).unwrap();
        }
    };
    write_state(&mut out, &veh);
    for s in 0..a.steps {
        p.step = s;
        g.queue.write_buffer(&params, 0, bytemuck::bytes_of(&p));
        let which = (s % 2) as usize;
        let mut enc = d.create_command_encoder(&Default::default());
        {
            let mut c = enc.begin_compute_pass(&Default::default());
            c.set_pipeline(&pipeline);
            c.set_bind_group(0, &groups[which], &[]);
            c.dispatch_workgroups(n.div_ceil(64), 1, 1);
        }
        g.queue.submit([enc.finish()]);
        let bytes = read(&buf[1 - which]);
        write_state(&mut out, &bytes);
    }
    let st = read(&stats);
    let st: &[u32] = bytemuck::cast_slice(&st);
    println!("{{\"guard_steps\": {}, \"steps\": {}}}", st[0], st[1]);
}
