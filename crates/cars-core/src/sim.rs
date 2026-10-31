//! Owns the GPU buffers and pipelines and steps the simulation.

use std::time::Instant;

use bytemuck::Pod;
use wgpu::util::DeviceExt;

use crate::gpu::Gpu;
use crate::world::*;

const COMMON: &str = include_str!("shaders/common.wgsl");
const STEP: &str = include_str!("shaders/step.wgsl");
const LC: &str = include_str!("shaders/lc.wgsl");
const CONTROL: &str = include_str!("shaders/control.wgsl");
const SORT: &str = include_str!("shaders/sort.wgsl");

/// Bindings of the main layout, in binding order: (read only).
const MAIN_BINDINGS: &[bool] = &[
    /*0 P*/ true, /*1 G*/ false, /*2 C*/ false, /*3 lanes*/ true, /*4 edges*/ true,
    /*5 links*/ true, /*6 foes*/ true, /*7 conflicts*/ true, /*8 types*/ true, /*9 routes*/ true,
    /*10 trips*/ true, /*11 queues*/ false, /*12 tls*/ false, /*13 phases*/ true, /*14 states*/ true,
    /*15 prev*/ true, /*16 cur*/ false, /*17 incoming*/ true, /*18 adv_flags*/ false, /*19 unused*/ true,
    /*20 seg*/ false, /*21 items*/ false, /*22 slots*/ false, /*23 link_count*/ false,
    /*24 partial*/ false, /*25 tail*/ false, /*26 entrant*/ false, /*27 trip_out*/ false,
    /*28 series*/ false, /*29 edge_acc*/ false, /*30 unused*/ true, /*31 advice*/ false,
    /*32 queue_trips*/ true, /*33 claims*/ false, /*34 last_detect*/ false, /*35 lc_plan*/ false,
];

pub struct Sim {
    pub world_params: GpuParams,
    pub step: u64,
    pub buffers: Buffers,
    pipelines: Pipelines,
    main_groups: [wgpu::BindGroup; 2],
    control_group: wgpu::BindGroup,
    keys_group: wgpu::BindGroup,
    gather_group: wgpu::BindGroup,
    sort_groups: Vec<[wgpu::BindGroup; 4]>,
    passes: u32,
    radix: u32,
    /// Largest number of steps one submission may hold, adjusted to keep submissions short.
    pub steps_per_submit: u32,
    pub target_submit_ms: f64,
}

pub struct Buffers {
    pub params: wgpu::Buffer,
    pub globals: wgpu::Buffer,
    pub counters: wgpu::Buffer,
    pub lanes: wgpu::Buffer,
    pub veh: [wgpu::Buffer; 2],
    pub trip_out: wgpu::Buffer,
    pub series: wgpu::Buffer,
    pub edge_acc: wgpu::Buffer,
    pub indirect: wgpu::Buffer,
    pub tls: wgpu::Buffer,
    pub queues: wgpu::Buffer,
    pub items: wgpu::Buffer,
    pub total_bytes: u64,
}

struct Pipelines {
    begin: wgpu::ComputePipeline,
    after_gather: wgpu::ComputePipeline,
    tls: wgpu::ComputePipeline,
    keys: wgpu::ComputePipeline,
    gather: wgpu::ComputePipeline,
    build_seg: wgpu::ComputePipeline,
    clear_links: wgpu::ComputePipeline,
    clear_lanes: wgpu::ComputePipeline,
    plan: wgpu::ComputePipeline,
    approach: wgpu::ComputePipeline,
    exec: wgpu::ComputePipeline,
    lc_best: Option<wgpu::ComputePipeline>,
    lc_decide: wgpu::ComputePipeline,
    lc_commit: Option<wgpu::ComputePipeline>,
    lc_release: Option<wgpu::ComputePipeline>,
    glosa: Option<wgpu::ComputePipeline>,
    insert: wgpu::ComputePipeline,
    sample_stats: wgpu::ComputePipeline,
    next_sample: wgpu::ComputePipeline,
    count: wgpu::ComputePipeline,
    prefix: wgpu::ComputePipeline,
    starts: wgpu::ComputePipeline,
    scatter: wgpu::ComputePipeline,
}

fn storage_entry(binding: u32, read_only: bool) -> wgpu::BindGroupLayoutEntry {
    wgpu::BindGroupLayoutEntry {
        binding,
        visibility: wgpu::ShaderStages::COMPUTE,
        ty: wgpu::BindingType::Buffer {
            ty: wgpu::BufferBindingType::Storage { read_only },
            has_dynamic_offset: false,
            min_binding_size: None,
        },
        count: None,
    }
}

fn uniform_entry(binding: u32) -> wgpu::BindGroupLayoutEntry {
    wgpu::BindGroupLayoutEntry {
        binding,
        visibility: wgpu::ShaderStages::COMPUTE,
        ty: wgpu::BindingType::Buffer {
            ty: wgpu::BufferBindingType::Uniform,
            has_dynamic_offset: false,
            min_binding_size: None,
        },
        count: None,
    }
}

impl Sim {
    pub fn new(gpu: &Gpu, world: &World) -> Result<Self, String> {
        let device = &gpu.device;
        let p = world.params;
        let total_bytes = std::cell::Cell::new(0u64);
        let storage = wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC | wgpu::BufferUsages::COPY_DST;
        let init = |label: &str, data: &[u8], usage: wgpu::BufferUsages| -> wgpu::Buffer {
            total_bytes.set(total_bytes.get() + data.len() as u64);
            let padded;
            let contents = if data.len() < 256 {
                let mut v = data.to_vec();
                v.resize(256, 0);
                padded = v;
                &padded[..]
            } else {
                data
            };
            device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some(label),
                contents,
                usage,
            })
        };
        let params = init("params", bytemuck::bytes_of(&p), wgpu::BufferUsages::UNIFORM);
        // step starts at -1 so that the first begin() makes it 0, SUMO's first time step.
        let globals_init = GpuGlobals { step: u32::MAX, ..Default::default() };
        let globals = init("globals", bytemuck::bytes_of(&globals_init), storage);
        let counters = init("counters", &[0u8; 64], storage);
        let lanes = init("lanes", bytemuck::cast_slice(&world.lanes), storage);
        let edges = init("edges", bytemuck::cast_slice(&world.edges), storage);
        let links = init("links", bytemuck::cast_slice(&world.links), storage);
        let foes = init("foes", bytemuck::cast_slice(&world.foes), storage);
        let conflicts = init("conflicts", bytemuck::cast_slice(&world.conflicts), storage);
        let types = init("types", bytemuck::cast_slice(&world.vtypes), storage);
        let routes = init("routes", bytemuck::cast_slice(&world.routes), storage);
        let trips = init("trips", bytemuck::cast_slice(&world.trips), storage);
        let queues = init("queues", bytemuck::cast_slice(&world.queues), storage);
        let tls = init("tls", bytemuck::cast_slice(&world.tls), storage);
        let phases = init("phases", bytemuck::cast_slice(&world.phases), storage);
        let states = init("states", bytemuck::cast_slice(&world.states), storage);
        let queue_trips = init("queue_trips", bytemuck::cast_slice(&world.queue_trips), storage);
        let indirect = init(
            "indirect",
            &[0u8; 64],
            storage | wgpu::BufferUsages::INDIRECT,
        );

        let cap = p.capacity.max(1) as u64;
        let empty = |label: &str, size: u64| -> wgpu::Buffer {
            total_bytes.set(total_bytes.get() + size);
            device.create_buffer(&wgpu::BufferDescriptor {
                label: Some(label),
                size: size.max(256),
                usage: storage,
                mapped_at_creation: false,
            })
        };
        let veh_bytes = std::mem::size_of::<GpuVeh>() as u64;
        let veh = [empty("veh_a", cap * veh_bytes), empty("veh_b", cap * veh_bytes)];
        let keys = [empty("keys0", cap * 4), empty("keys1", cap * 4)];
        let vals = [empty("vals0", cap * 4), empty("vals1", cap * 4)];
        let digit_bits = 8u32;
        let radix = 1u32 << digit_bits;
        let passes = p.key_bits.div_ceil(digit_bits);
        let blocks = (cap as u32).div_ceil(p.block) as u64;
        let hist = empty("hist", blocks * radix as u64 * 4);
        let totals = empty("totals", radix as u64 * 4);
        let seg = empty("seg", p.n_lanes as u64 * SEG_BYTES);
        let items = empty("items", cap * MAX_ITEMS * ITEM_BYTES);
        let slots_init = vec![0xffu8; (p.n_links as u64 * SLOTS * APPROACH_BYTES) as usize];
        let slots = init("slots", &slots_init, storage);
        let link_count = empty("link_count", p.n_links as u64 * 4);
        let ones = vec![0xffu8; p.n_lanes as usize * 4];
        let partial = init("partial", &ones, storage);
        let tail = init("tail", &ones, storage);
        let entrant = init("entrant", &ones, storage);
        let trip_out = empty(
            "trip_out",
            p.n_trips as u64 * std::mem::size_of::<GpuTripOut>() as u64,
        );
        let series = empty("series", p.n_samples as u64 * p.n_replicas as u64 * 16);
        let edge_acc = empty("edge_acc", p.n_edges as u64 * 16);
        let advice_init = vec![0xffu8; p.n_trips as usize * 4];
        let advice = init("advice", &advice_init, storage);
        let adv_flags = empty("adv_flags", p.n_trips as u64 * 4);
        let incoming_links = init("incoming_links", bytemuck::cast_slice(&world.incoming_links), storage);
        let claims_init = vec![0xffu8; p.n_lanes as usize * 4 * 64];
        let claims = init("claims", &claims_init, storage);
        let last_detect = empty("last_detect", p.n_lanes as u64 * 4);
        let lc_plan = empty("lc_plan", cap * LCPLAN_BYTES);
        let unused = empty("unused", 16);

        // Layouts.
        let main_layout = {
            let entries: Vec<_> = MAIN_BINDINGS
                .iter()
                .enumerate()
                .map(|(b, &ro)| {
                    if b == 0 {
                        uniform_entry(0)
                    } else {
                        storage_entry(b as u32, ro)
                    }
                })
                .collect();
            device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
                label: Some("main"),
                entries: &entries,
            })
        };
        let control_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("control"),
            entries: &[
                uniform_entry(0),
                storage_entry(1, false),
                storage_entry(2, false),
                storage_entry(3, false),
            ],
        });
        let sort_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("sort"),
            entries: &[
                uniform_entry(0),
                storage_entry(1, true),
                storage_entry(2, true),
                storage_entry(3, true),
                storage_entry(4, false),
                storage_entry(5, false),
                storage_entry(6, false),
                storage_entry(7, false),
            ],
        });

        // After `passes` passes starting from buffer 0, the result sits in buffer passes % 2.
        let final_vals = &vals[(passes % 2) as usize];
        let keys_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("keys"),
            entries: &[storage_entry(0, false), storage_entry(1, false)],
        });
        let gather_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("gather"),
            entries: &[storage_entry(2, true)],
        });
        let keys_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("keys"),
            layout: &keys_layout,
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: keys[0].as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: vals[0].as_entire_binding() },
            ],
        });
        let gather_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("gather"),
            layout: &gather_layout,
            entries: &[wgpu::BindGroupEntry { binding: 2, resource: final_vals.as_entire_binding() }],
        });

        let main_group = |prev: &wgpu::Buffer, cur: &wgpu::Buffer| {
            let list: Vec<&wgpu::Buffer> = vec![
                &params, &globals, &counters, &lanes, &edges, &links, &foes, &conflicts, &types, &routes,
                &trips, &queues, &tls, &phases, &states, prev, cur, &incoming_links, &adv_flags, &unused, &seg,
                &items, &slots, &link_count, &partial, &tail, &entrant, &trip_out, &series, &edge_acc,
                &unused, &advice, &queue_trips, &claims, &last_detect, &lc_plan,
            ];
            let entries: Vec<_> = list
                .iter()
                .enumerate()
                .map(|(i, b)| wgpu::BindGroupEntry {
                    binding: i as u32,
                    resource: b.as_entire_binding(),
                })
                .collect();
            device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("main"),
                layout: &main_layout,
                entries: &entries,
            })
        };
        let main_groups = [main_group(&veh[0], &veh[1]), main_group(&veh[1], &veh[0])];

        let control_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("control"),
            layout: &control_layout,
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: params.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: globals.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: counters.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 3, resource: indirect.as_entire_binding() },
            ],
        });

        let mut sort_groups = Vec::new();
        for pass in 0..passes {
            let uniform = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("sort pass"),
                contents: bytemuck::cast_slice(&[pass * digit_bits, p.block, 0u32, 0u32]),
                usage: wgpu::BufferUsages::UNIFORM,
            });
            let (a, b) = if pass % 2 == 0 { (0usize, 1usize) } else { (1, 0) };
            let group = |pairs: &[(u32, &wgpu::Buffer)]| {
                let entries: Vec<_> = pairs
                    .iter()
                    .map(|(i, b)| wgpu::BindGroupEntry {
                        binding: *i,
                        resource: b.as_entire_binding(),
                    })
                    .collect();
                device.create_bind_group(&wgpu::BindGroupDescriptor {
                    label: Some("sort"),
                    layout: &sort_layout,
                    entries: &entries,
                })
            };
            let all = group(&[
                (0, &uniform),
                (1, &globals),
                (2, &keys[a]),
                (3, &vals[a]),
                (4, &keys[b]),
                (5, &vals[b]),
                (6, &hist),
                (7, &totals),
            ]);
            sort_groups.push([all.clone(), all.clone(), all.clone(), all]);
        }

        let main_src = format!("{COMMON}\n{STEP}\n{LC}");
        let main_module = gpu.shader("step", &main_src);
        let control_module = gpu.shader("control", &format!("{COMMON}\n{CONTROL}"));
        let sort_module = gpu.shader("sort", &format!("{COMMON}\n{SORT}"));
        let main_pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("main"),
            bind_group_layouts: &[Some(&main_layout)],
            immediate_size: 0,
        });
        let control_pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("control"),
            bind_group_layouts: &[Some(&control_layout)],
            immediate_size: 0,
        });
        let sort_pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("sort"),
            bind_group_layouts: &[Some(&sort_layout)],
            immediate_size: 0,
        });
        let keys_pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("keys"),
            bind_group_layouts: &[Some(&main_layout), Some(&keys_layout)],
            immediate_size: 0,
        });
        let gather_pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("gather"),
            bind_group_layouts: &[Some(&main_layout), Some(&gather_layout)],
            immediate_size: 0,
        });
        let make = |layout: &wgpu::PipelineLayout, module: &wgpu::ShaderModule, entry: &str| {
            device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
                label: Some(entry),
                layout: Some(layout),
                module,
                entry_point: Some(entry),
                compilation_options: Default::default(),
                cache: None,
            })
        };
        let m = |e: &str| make(&main_pl, &main_module, e);
        let s = |e: &str| make(&sort_pl, &sort_module, e);
        let has = |e: &str| main_src.contains(&format!("fn {e}("));
        let pipelines = Pipelines {
            begin: make(&control_pl, &control_module, "begin"),
            after_gather: make(&control_pl, &control_module, "after_gather"),
            tls: m("tls_step"),
            keys: make(&keys_pl, &main_module, "keys"),
            gather: make(&gather_pl, &main_module, "gather"),
            build_seg: m("build_seg"),
            clear_links: m("clear_links"),
            clear_lanes: m("clear_lanes"),
            plan: m("plan"),
            approach: m("approach"),
            exec: m("exec"),
            lc_best: has("lc_best").then(|| m("lc_best")),
            lc_decide: m("lc_decide"),
            lc_commit: has("lc_commit").then(|| m("lc_commit")),
            lc_release: has("lc_release").then(|| m("lc_release")),
            glosa: world.vtypes.iter().any(|t| t.glosa_range > 0.0).then(|| m("glosa")),
            insert: m("insert"),
            sample_stats: m("sample_stats"),
            next_sample: m("next_sample"),
            count: s("count"),
            prefix: s("prefix"),
            starts: s("starts"),
            scatter: s("scatter"),
        };

        let buffers = Buffers {
            params,
            globals,
            counters,
            lanes,
            veh,
            trip_out,
            series,
            edge_acc,
            indirect,
            tls,
            queues,
            items,
            total_bytes: total_bytes.get(),
        };
        Ok(Self {
            world_params: p,
            step: 0,
            buffers,
            pipelines,
            main_groups,
            control_group,
            keys_group,
            gather_group,
            sort_groups,
            passes,
            radix,
            steps_per_submit: 1,
            target_submit_ms: 15.0,
        })
    }

    /// The vehicle buffer the last completed step wrote to.
    pub fn current_veh(&self) -> &wgpu::Buffer {
        // Step k (0-based) writes `cur` of group k % 2: buffer 1 for even k.
        if self.step % 2 == 1 { &self.buffers.veh[1] } else { &self.buffers.veh[0] }
    }

    fn record_step(&self, c: &mut wgpu::ComputePass<'_>) {
        let p = &self.pipelines;
        let params = &self.world_params;
        let group = &self.main_groups[(self.step % 2) as usize];
        let ind = &self.buffers.indirect;
        c.set_pipeline(&p.begin);
        c.set_bind_group(0, &self.control_group, &[]);
        c.dispatch_workgroups(1, 1, 1);

        c.set_bind_group(0, group, &[]);
        if params.n_tls > 0 {
            c.set_pipeline(&p.tls);
            c.dispatch_workgroups(params.n_tls.div_ceil(16), 1, 1);
        }
        c.set_pipeline(&p.keys);
        c.set_bind_group(1, &self.keys_group, &[]);
        c.dispatch_workgroups_indirect(ind, 0);

        for g in &self.sort_groups {
            c.set_bind_group(0, &g[0], &[]);
            c.set_pipeline(&p.count);
            c.dispatch_workgroups_indirect(ind, 12);
            c.set_pipeline(&p.prefix);
            c.dispatch_workgroups(self.radix.div_ceil(64), 1, 1);
            c.set_pipeline(&p.starts);
            c.dispatch_workgroups(1, 1, 1);
            c.set_pipeline(&p.scatter);
            c.dispatch_workgroups_indirect(ind, 12);
        }

        c.set_bind_group(0, group, &[]);
        c.set_pipeline(&p.gather);
        c.set_bind_group(1, &self.gather_group, &[]);
        c.dispatch_workgroups_indirect(ind, 0);
        c.set_pipeline(&p.after_gather);
        c.set_bind_group(0, &self.control_group, &[]);
        c.dispatch_workgroups(1, 1, 1);
        c.set_bind_group(0, group, &[]);
        c.set_pipeline(&p.build_seg);
        c.dispatch_workgroups_indirect(ind, 24);
        c.set_pipeline(&p.clear_links);
        c.dispatch_workgroups(params.n_links.div_ceil(64), 1, 1);
        c.set_pipeline(&p.plan);
        c.dispatch_workgroups_indirect(ind, 24);
        c.set_pipeline(&p.approach);
        c.dispatch_workgroups_indirect(ind, 24);
        c.set_pipeline(&p.clear_lanes);
        c.dispatch_workgroups(params.n_lanes.div_ceil(64), 1, 1);
        c.set_pipeline(&p.exec);
        c.dispatch_workgroups_indirect(ind, 24);
        if let Some(gl) = &p.glosa {
            c.set_pipeline(gl);
            c.dispatch_workgroups_indirect(ind, 24);
        }
        if let Some(best) = &p.lc_best {
            c.set_pipeline(best);
            c.dispatch_workgroups_indirect(ind, 24);
        }
        c.set_pipeline(&p.lc_decide);
        c.dispatch_workgroups_indirect(ind, 24);
        if let Some(commit) = &p.lc_commit {
            c.set_pipeline(commit);
            c.dispatch_workgroups_indirect(ind, 24);
        }
        if let Some(release) = &p.lc_release {
            c.set_pipeline(release);
            c.dispatch_workgroups_indirect(ind, 24);
        }
        if params.n_queues > 0 {
            c.set_pipeline(&p.insert);
            c.dispatch_workgroups(params.n_queues.div_ceil(16), 1, 1);
        }
        if self.step % params.sample_steps as u64 == 0 {
            c.set_pipeline(&p.sample_stats);
            c.dispatch_workgroups_indirect(ind, 24);
            c.set_pipeline(&p.next_sample);
            c.dispatch_workgroups(1, 1, 1);
        }
    }

    /// Run `n` steps in one GPU submission and wait for them.
    pub fn run_batch(&mut self, gpu: &Gpu, n: u32) -> f64 {
        let t = Instant::now();
        let mut enc = gpu.device.create_command_encoder(&Default::default());
        {
            let mut c = enc.begin_compute_pass(&Default::default());
            for _ in 0..n {
                self.record_step(&mut c);
                self.step += 1;
            }
        }
        gpu.queue.submit([enc.finish()]);
        gpu.wait();
        t.elapsed().as_secs_f64() * 1000.0
    }

    /// Run up to `limit` steps, keeping each GPU submission short so the desktop stays smooth.
    pub fn run(&mut self, gpu: &Gpu, limit: u64) -> u64 {
        let mut done = 0;
        while done < limit {
            let n = (self.steps_per_submit as u64).min(limit - done) as u32;
            let ms = self.run_batch(gpu, n);
            done += n as u64;
            // Steer towards the target, without big jumps.
            let per = ms / n as f64;
            let want = (self.target_submit_ms / per).clamp(1.0, 4096.0);
            let next = if want > self.steps_per_submit as f64 {
                (self.steps_per_submit as f64 * 1.5).min(want)
            } else {
                want
            };
            self.steps_per_submit = (next.ceil() as u32).max(1);
        }
        done
    }

    pub fn read<T: Pod>(&self, gpu: &Gpu, buffer: &wgpu::Buffer, count: u64) -> Vec<T> {
        let size = (count * std::mem::size_of::<T>() as u64).min(buffer.size());
        if size == 0 {
            return Vec::new();
        }
        let staging = gpu.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("read"),
            size,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        let mut enc = gpu.device.create_command_encoder(&Default::default());
        enc.copy_buffer_to_buffer(buffer, 0, &staging, 0, size);
        gpu.queue.submit([enc.finish()]);
        let slice = staging.slice(..);
        slice.map_async(wgpu::MapMode::Read, |_| {});
        gpu.wait();
        let data = slice.get_mapped_range().expect("mapped");
        let out = bytemuck::pod_collect_to_vec(&data[..]);
        drop(data);
        staging.unmap();
        out
    }

    pub fn globals(&self, gpu: &Gpu) -> GpuGlobals {
        self.read::<GpuGlobals>(gpu, &self.buffers.globals, 1)[0]
    }

    pub fn counters(&self, gpu: &Gpu) -> Vec<u32> {
        self.read::<u32>(gpu, &self.buffers.counters, 16)
    }

    pub fn vehicles(&self, gpu: &Gpu) -> Vec<GpuVeh> {
        let g = self.globals(gpu);
        self.read::<GpuVeh>(gpu, self.current_veh(), g.n_active as u64 + self.counters(gpu)[0] as u64)
    }

    pub fn trip_outputs(&self, gpu: &Gpu) -> Vec<GpuTripOut> {
        self.read(gpu, &self.buffers.trip_out, self.world_params.n_trips as u64)
    }

    pub fn series(&self, gpu: &Gpu) -> Vec<[u32; 4]> {
        let n = self.world_params.n_samples as u64 * self.world_params.n_replicas as u64;
        self.read(gpu, &self.buffers.series, n)
    }

    /// Per edge: samples, distance in 1/8 m, entered, spare. Returned and reset.
    pub fn take_edge_acc(&self, gpu: &Gpu) -> Vec<[u32; 4]> {
        let out = self.read(gpu, &self.buffers.edge_acc, self.world_params.n_edges as u64);
        let mut enc = gpu.device.create_command_encoder(&Default::default());
        enc.clear_buffer(&self.buffers.edge_acc, 0, None);
        gpu.queue.submit([enc.finish()]);
        out
    }

    pub fn passes(&self) -> u32 {
        self.passes
    }
}
