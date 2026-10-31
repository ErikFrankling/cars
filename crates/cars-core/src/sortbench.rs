//! Measures the radix sort alone, to size the rest of the design.

use wgpu::util::DeviceExt;

use crate::gpu::Gpu;

/// Returns milliseconds per full sort at this key count.
pub fn bench(gpu: &Gpu, n: u32, key_bits: u32, digit_bits: u32, block: u32, repeat: u32) -> f64 {
    let device = &gpu.device;
    let queue = &gpu.queue;
    let shader = gpu.shader("sort", include_str!("shaders/sort.wgsl"));
    let passes = key_bits.div_ceil(digit_bits);
    let radix = 1u64 << digit_bits;
    let blocks = n.div_ceil(block);
    let mut rng = 0x9E3779B97F4A7C15u64;
    let keys: Vec<u32> = (0..n)
        .map(|_| {
            rng ^= rng << 13;
            rng ^= rng >> 7;
            rng ^= rng << 17;
            (rng >> 16) as u32 & ((1u64 << key_bits) - 1) as u32
        })
        .collect();
    let vals: Vec<u32> = (0..n).collect();
    let usage = wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC | wgpu::BufferUsages::COPY_DST;
    let init = |label, data: &[u32]| {
        device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some(label),
            contents: bytemuck::cast_slice(data),
            usage,
        })
    };
    let keys_a = init("keys_a", &keys);
    let vals_a = init("vals_a", &vals);
    let keys_b = init("keys_b", &keys);
    let vals_b = init("vals_b", &vals);
    let hist = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("hist"),
        size: blocks as u64 * radix * 4,
        usage: wgpu::BufferUsages::STORAGE,
        mapped_at_creation: false,
    });
    let totals = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("totals"),
        size: radix * 4,
        usage: wgpu::BufferUsages::STORAGE,
        mapped_at_creation: false,
    });
    let opts = wgpu::PipelineCompilationOptions {
        constants: &[("DIGIT_BITS", digit_bits as f64)],
        ..Default::default()
    };
    let pipe = |entry: &str| {
        device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some(entry),
            layout: None,
            module: &shader,
            entry_point: Some(entry),
            compilation_options: opts.clone(),
            cache: None,
        })
    };
    let (count, prefix, starts, scatter) = (pipe("count"), pipe("prefix"), pipe("starts"), pipe("scatter"));
    let mut groups = Vec::new();
    for pass in 0..passes {
        let params: [u32; 4] = [n, block, blocks, pass * digit_bits];
        let ubuf = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("params"),
            contents: bytemuck::cast_slice(&params),
            usage: wgpu::BufferUsages::UNIFORM,
        });
        let (ka, va, kb, vb) = if pass % 2 == 0 {
            (&keys_a, &vals_a, &keys_b, &vals_b)
        } else {
            (&keys_b, &vals_b, &keys_a, &vals_a)
        };
        let all = [
            ubuf.as_entire_binding(),
            ka.as_entire_binding(),
            va.as_entire_binding(),
            kb.as_entire_binding(),
            vb.as_entire_binding(),
            hist.as_entire_binding(),
            totals.as_entire_binding(),
        ];
        let mk = |p: &wgpu::ComputePipeline, bindings: &[u32]| {
            let entries: Vec<_> = bindings
                .iter()
                .map(|&b| wgpu::BindGroupEntry { binding: b, resource: all[b as usize].clone() })
                .collect();
            device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: None,
                layout: &p.get_bind_group_layout(0),
                entries: &entries,
            })
        };
        groups.push((
            mk(&count, &[0, 1, 5]),
            mk(&prefix, &[0, 5, 6]),
            mk(&starts, &[6]),
            mk(&scatter, &[0, 1, 2, 3, 4, 5, 6]),
        ));
    }
    let mut encoder = device.create_command_encoder(&Default::default());
    {
        let mut c = encoder.begin_compute_pass(&Default::default());
        for _ in 0..repeat {
            for (gc, gp, gs, gt) in &groups {
                c.set_pipeline(&count);
                c.set_bind_group(0, gc, &[]);
                c.dispatch_workgroups(blocks.div_ceil(64), 1, 1);
                c.set_pipeline(&prefix);
                c.set_bind_group(0, gp, &[]);
                c.dispatch_workgroups((radix as u32).div_ceil(64), 1, 1);
                c.set_pipeline(&starts);
                c.set_bind_group(0, gs, &[]);
                c.dispatch_workgroups(1, 1, 1);
                c.set_pipeline(&scatter);
                c.set_bind_group(0, gt, &[]);
                c.dispatch_workgroups(blocks.div_ceil(64), 1, 1);
            }
        }
    }
    let t = std::time::Instant::now();
    queue.submit([encoder.finish()]);
    gpu.wait();
    t.elapsed().as_secs_f64() * 1000.0 / repeat as f64
}
