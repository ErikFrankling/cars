//! Headless HDR renderer. Vehicle state stays on the GPU; only pixels and two statistics return.
use crate::{Gpu, net::Net, sim::Sim, world::World};
use wgpu::util::DeviceExt;
#[derive(Clone, Copy, Debug)]
pub struct Camera {
    pub center: [f32; 2],
    pub metres_per_pixel: f32,
}
impl Camera {
    pub fn fit(bounds: [f32; 4], w: u32, h: u32) -> Self {
        Self {
            center: [(bounds[0] + bounds[2]) * 0.5, (bounds[1] + bounds[3]) * 0.5],
            metres_per_pixel: ((bounds[2] - bounds[0]) / w as f32)
                .max((bounds[3] - bounds[1]) / h as f32)
                .max(0.001)
                * 1.15,
        }
    }
}
pub struct Renderer {
    render_links: wgpu::Buffer,
    render_routes: wgpu::Buffer,
    history: wgpu::Buffer,
    dt: f32,
    signals: wgpu::Buffer,
    phases: wgpu::Buffer,
    states: wgpu::Buffer,
    capacity: u32,
    total: u32,
    camera: wgpu::Buffer,
    ranges: wgpu::Buffer,
    points: wgpu::Buffer,
    types: wgpu::Buffer,
    instances: wgpu::Buffer,
    stats: wgpu::Buffer,
    roads: wgpu::Buffer,
    road_count: u32,
    compute: wgpu::ComputePipeline,
    road: wgpu::RenderPipeline,
    car: wgpu::RenderPipeline,
    tone: wgpu::RenderPipeline,
    draw_group: wgpu::BindGroup,
    tone_group: wgpu::BindGroup,
    hdr: wgpu::TextureView,
    msaa: wgpu::TextureView,
    output: wgpu::Texture,
    readback: wgpu::Buffer,
    width: u32,
    height: u32,
    stride: u32,
}
fn buffer(g: &Gpu, name: &str, data: &[u8], usage: wgpu::BufferUsages) -> wgpu::Buffer {
    let padded = vec![0; 256];
    g.device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some(name),
            contents: if data.is_empty() { &padded } else { data },
            usage,
        })
}
impl Renderer {
    pub fn new(g: &Gpu, w: &World, net: &Net, width: u32, height: u32) -> Self {
        let storage = wgpu::BufferUsages::STORAGE;
        let mut points = Vec::<[f32; 4]>::new();
        let mut ranges = Vec::<[u32; 4]>::new();
        let mut roads = Vec::<[f32; 6]>::new();
        let mut marks = Vec::<[f32; 6]>::new();
        let quad = |out: &mut Vec<[f32; 6]>, a: [f32; 2], b: [f32; 2], width: f32, tint: f32| {
            let d = ((b[0] - a[0]).powi(2) + (b[1] - a[1]).powi(2))
                .sqrt()
                .max(0.001);
            let n = [-(b[1] - a[1]) / d, (b[0] - a[0]) / d];
            for (p, k) in [(a, -1.), (b, -1.), (a, 1.), (a, 1.), (b, -1.), (b, 1.)] {
                out.push([p[0], p[1], n[0] * k, n[1] * k, width, tint]);
            }
        };
        for j in &net.junctions {
            if j.shape.len() < 3 {
                continue;
            }
            for pair in j.shape[1..].windows(2) {
                for p in [j.shape[0], pair[0], pair[1]] {
                    roads.push([p[0], p[1], 0., 0., 0., 1.]);
                }
            }
        }
        for (i, &(start, count)) in w.shape_range.iter().enumerate() {
            let shape = &w.shapes[start as usize..(start + count) as usize];
            let base = points.len() as u32;
            let mut distance = 0.0;
            for (j, p) in shape.iter().enumerate() {
                if j > 0 {
                    distance += ((p[0] - shape[j - 1][0]).powi(2)
                        + (p[1] - shape[j - 1][1]).powi(2))
                    .sqrt();
                }
                points.push([p[0], p[1], distance, 0.0]);
            }
            ranges.push([base, count, distance.to_bits(), 0]);
            let lane = &w.lanes[i];
            let tint = if lane.flags & 1 != 0 {
                0.0
            } else if lane.speed > 25.0 {
                1.5
            } else {
                1.0
            };
            let mut along = 0.0;
            for pair in shape.windows(2) {
                let a = pair[0];
                let b = pair[1];
                let d = ((b[0] - a[0]).powi(2) + (b[1] - a[1]).powi(2)).sqrt();
                if d < 0.001 {
                    continue;
                }
                let n = [-(b[1] - a[1]) / d, (b[0] - a[0]) / d];
                if lane.flags & 1 == 0 {
                    let nl = &net.lanes[i];
                    let edge = &net.edges[nl.edge as usize];
                    for side in [-1., 1.] {
                        let outer = side < 0. && nl.index == 0
                            || side > 0. && nl.index + 1 == edge.lane_count;
                        let offset = nl.width * 0.5 * side;
                        let mut t = 0.0;
                        while t < d {
                            let solid = outer || along + t > distance - 25.;
                            let phase = (along + t) % 9.;
                            let len = if solid {
                                d - t
                            } else {
                                (d - t)
                                    .min(if phase < 3. { 3. - phase } else { 9. - phase })
                                    .max(0.001)
                            };
                            if outer || along + t > distance - 25. || (along + t) % 9. < 3. {
                                let x = [
                                    a[0] + (b[0] - a[0]) * t / d + n[0] * offset,
                                    a[1] + (b[1] - a[1]) * t / d + n[1] * offset,
                                ];
                                let y = [
                                    x[0] + (b[0] - a[0]) * len / d,
                                    x[1] + (b[1] - a[1]) * len / d,
                                ];
                                quad(&mut marks, x, y, if outer { 0.18 } else { 0.12 }, -1.);
                                if outer {
                                    quad(
                                        &mut marks,
                                        [x[0] + n[0] * side * 0.35, x[1] + n[1] * side * 0.35],
                                        [y[0] + n[0] * side * 0.35, y[1] + n[1] * side * 0.35],
                                        0.3,
                                        -4.,
                                    );
                                }
                            }
                            t += len;
                        }
                    }
                }
                along += d;
                for (p, sign) in [
                    (a, -1.0),
                    (b, -1.0),
                    (a, 1.0),
                    (a, 1.0),
                    (b, -1.0),
                    (b, 1.0),
                ] {
                    roads.push([
                        p[0],
                        p[1],
                        n[0] * sign,
                        n[1] * sign,
                        net.lanes[i].width,
                        tint,
                    ]);
                }
            }
        }
        let minor_lanes: std::collections::HashSet<u32> = net
            .conns
            .iter()
            .filter(|c| c.state == b'm' || c.state == b's')
            .filter_map(|c| net.lane_of(c.from_edge,c.from_lane))
            .collect();
        for (i, l) in net.lanes.iter().enumerate() {
            if net.is_internal_lane(i as u32) || l.shape.len() < 2 {
                continue;
            }
            let edge = &net.edges[l.edge as usize];
            if let Some(&ji) = net.junction_index.get(&edge.to) {
                let j = &net.junctions[ji as usize];
                if j.requests.is_empty() {
                    continue;
                }
                let b = l.shape[l.shape.len() - 1];
                let a = l.shape[l.shape.len() - 2];
                let d = ((b[0] - a[0]).powi(2) + (b[1] - a[1]).powi(2))
                    .sqrt()
                    .max(0.001);
                let n = [-(b[1] - a[1]) / d, (b[0] - a[0]) / d];
                if !j.jtype.starts_with("traffic_light") {
                    let minor = minor_lanes.contains(&(i as u32));
                    let x = [b[0] - (b[0] - a[0]) / d * 5., b[1] - (b[1] - a[1]) / d * 5.];
                    if minor || j.jtype == "allway_stop" {
                        let rear = [x[0] - (b[0] - a[0]) / d * 2., x[1] - (b[1] - a[1]) / d * 2.];
                        for p in [
                            x,
                            [rear[0] + n[0], rear[1] + n[1]],
                            [rear[0] - n[0], rear[1] - n[1]],
                        ] {
                            marks.push([p[0], p[1], 0., 0., 0., -1.]);
                        }
                    } else {
                        quad(
                            &mut marks,
                            [x[0] - n[0] * 0.6, x[1] - n[1] * 0.6],
                            [x[0] + n[0] * 0.6, x[1] + n[1] * 0.6],
                            1.2,
                            -2.,
                        );
                    }
                }
                quad(
                    &mut marks,
                    [b[0] - n[0] * l.width * 0.45, b[1] - n[1] * l.width * 0.45],
                    [b[0] + n[0] * l.width * 0.45, b[1] + n[1] * l.width * 0.45],
                    0.35,
                    -1.,
                );
            }
        }
        roads.extend(marks);
        let mut slots = std::collections::HashMap::<u32, u32>::new();
        let signal_data: Vec<[u32; 4]> = w
            .links
            .iter()
            .filter(|l| l.tl != u32::MAX && (l.from_lane as usize) < w.shape_range.len())
            .map(|l| {
                let slot = slots.entry(l.from_lane).or_default();
                let row = [l.from_lane, l.tl, l.tl_index, *slot];
                *slot += 1;
                row
            })
            .collect();
        let turns: std::collections::HashMap<(u32, u32), u32> = net
            .conns
            .iter()
            .map(|c| {
                (
                    (net.lane_of(c.from_edge,c.from_lane).unwrap_or(u32::MAX), c.to_edge),
                    match c.dir {
                        b'l' | b'L' => 2,
                        b'r' | b'R' => 4,
                        _ => 0,
                    },
                )
            })
            .collect();
        let link_data: Vec<[u32; 4]> = w
            .links
            .iter()
            .map(|l| {
                [
                    l.to_edge,
                    *turns.get(&(l.from_lane, l.to_edge)).unwrap_or(&0),
                    0,
                    0,
                ]
            })
            .collect();
        let render_links = buffer(
            g,
            "render link turns",
            bytemuck::cast_slice(&link_data),
            storage,
        );
        let render_routes = buffer(g, "render routes", bytemuck::cast_slice(&w.routes), storage);
        let history = g.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("render history by trip"),
            size: (w.trips.len().max(1) * 32) as u64,
            usage: storage,
            mapped_at_creation: false,
        });
        let signals = buffer(g, "signals", bytemuck::cast_slice(&signal_data), storage);
        let phases = buffer(g, "signal phases", bytemuck::cast_slice(&w.phases), storage);
        let states = buffer(g, "signal colors", bytemuck::cast_slice(&w.states), storage);
        let capacity = w.params.capacity;
        let total = capacity + signal_data.len() as u32;
        let camera = buffer(
            g,
            "camera",
            &[0; 32],
            wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        );
        let ranges = buffer(g, "shape ranges", bytemuck::cast_slice(&ranges), storage);
        let points = buffer(
            g,
            "cumulative geometry",
            bytemuck::cast_slice(&points),
            storage,
        );
        let types = buffer(g, "render types", bytemuck::cast_slice(&w.vtypes), storage);
        let instances = g.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("instances"),
            size: total.max(1) as u64 * 32,
            usage: storage | wgpu::BufferUsages::VERTEX,
            mapped_at_creation: false,
        });
        let stats = buffer(
            g,
            "render stats",
            &[0; 8],
            storage | wgpu::BufferUsages::COPY_SRC | wgpu::BufferUsages::COPY_DST,
        );
        let road_count = roads.len() as u32;
        let roads = buffer(
            g,
            "road mesh",
            bytemuck::cast_slice(&roads),
            wgpu::BufferUsages::VERTEX,
        );
        let module = g.shader(
            "renderer",
            &format!(
                "{}\n{}",
                include_str!("shaders/common.wgsl"),
                include_str!("shaders/render.wgsl")
            ),
        );
        let compute = g
            .device
            .create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
                label: Some("prepare instances"),
                layout: None,
                module: &module,
                entry_point: Some("prepare"),
                compilation_options: Default::default(),
                cache: None,
            });
        let attrs = wgpu::vertex_attr_array![0=>Float32x2,1=>Float32x2,2=>Float32,3=>Float32];
        let car_attrs = wgpu::vertex_attr_array![0=>Float32x2,1=>Float32x2,2=>Float32,3=>Float32,4=>Float32,5=>Float32];
        let make = |entry: &str, frag: &str, stride, step, attributes: &[wgpu::VertexAttribute]| {
            g.device
                .create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                    label: Some(entry),
                    layout: None,
                    vertex: wgpu::VertexState {
                        module: &module,
                        entry_point: Some(entry),
                        compilation_options: Default::default(),
                        buffers: &[Some(wgpu::VertexBufferLayout {
                            array_stride: stride,
                            step_mode: step,
                            attributes,
                        })],
                    },
                    fragment: Some(wgpu::FragmentState {
                        module: &module,
                        entry_point: Some(frag),
                        compilation_options: Default::default(),
                        targets: &[Some(wgpu::ColorTargetState {
                            format: wgpu::TextureFormat::Rgba16Float,
                            blend: Some(wgpu::BlendState {
                                color: wgpu::BlendComponent {
                                    src_factor: wgpu::BlendFactor::One,
                                    dst_factor: wgpu::BlendFactor::One,
                                    operation: wgpu::BlendOperation::Add,
                                },
                                alpha: wgpu::BlendComponent::REPLACE,
                            }),
                            write_mask: wgpu::ColorWrites::ALL,
                        })],
                    }),
                    primitive: Default::default(),
                    depth_stencil: None,
                    multisample: wgpu::MultisampleState {
                        count: 4,
                        ..Default::default()
                    },
                    multiview_mask: None,
                    cache: None,
                })
        };
        let road = make(
            "road",
            "road_frag",
            24,
            wgpu::VertexStepMode::Vertex,
            &attrs,
        );
        let car = make(
            "car",
            "car_frag",
            32,
            wgpu::VertexStepMode::Instance,
            &car_attrs,
        );
        let draw_group = g.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &road.get_bind_group_layout(0),
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: camera.as_entire_binding(),
            }],
        });
        let texture = |format, samples, usage| {
            g.device.create_texture(&wgpu::TextureDescriptor {
                label: None,
                size: wgpu::Extent3d {
                    width,
                    height,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: samples,
                dimension: wgpu::TextureDimension::D2,
                format,
                usage,
                view_formats: &[],
            })
        };
        let hdr = texture(
            wgpu::TextureFormat::Rgba16Float,
            1,
            wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
        )
        .create_view(&Default::default());
        let msaa = texture(
            wgpu::TextureFormat::Rgba16Float,
            4,
            wgpu::TextureUsages::RENDER_ATTACHMENT,
        )
        .create_view(&Default::default());
        let output = texture(
            wgpu::TextureFormat::Rgba8Unorm,
            1,
            wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
        );
        let tm = g.shader("tone map", include_str!("shaders/tonemap.wgsl"));
        let tone = g
            .device
            .create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: Some("tone map"),
                layout: None,
                vertex: wgpu::VertexState {
                    module: &tm,
                    entry_point: Some("vs"),
                    compilation_options: Default::default(),
                    buffers: &[],
                },
                fragment: Some(wgpu::FragmentState {
                    module: &tm,
                    entry_point: Some("fs"),
                    compilation_options: Default::default(),
                    targets: &[Some(wgpu::TextureFormat::Rgba8Unorm.into())],
                }),
                primitive: Default::default(),
                depth_stencil: None,
                multisample: Default::default(),
                multiview_mask: None,
                cache: None,
            });
        let tone_group = g.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &tone.get_bind_group_layout(0),
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: wgpu::BindingResource::TextureView(&hdr),
            }],
        });
        let stride = (width * 4).next_multiple_of(256);
        let readback = g.device.create_buffer(&wgpu::BufferDescriptor {
            label: None,
            size: stride as u64 * height as u64,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        Self {
            render_links,
            render_routes,
            history,
            dt: w.params.dt,
            signals,
            phases,
            states,
            capacity,
            total,
            camera,
            ranges,
            points,
            types,
            instances,
            stats,
            roads,
            road_count,
            compute,
            road,
            car,
            tone,
            draw_group,
            tone_group,
            hdr,
            msaa,
            output,
            readback,
            width,
            height,
            stride,
        }
    }
    pub fn frame(&self, g: &Gpu, sim: &Sim, cam: Camera, mode: u32) -> (Vec<u8>, u32, f32) {
        let uniform = [
            cam.center[0].to_bits(),
            cam.center[1].to_bits(),
            (self.width as f32).to_bits(),
            (self.height as f32).to_bits(),
            cam.metres_per_pixel.to_bits(),
            mode,
            self.capacity,
            (sim.step as f32 * self.dt).to_bits(),
        ];
        g.queue
            .write_buffer(&self.camera, 0, bytemuck::cast_slice(&uniform));
        let buffers = [
            &self.camera,
            sim.current_veh(),
            &sim.buffers.lanes,
            &self.ranges,
            &self.points,
            &self.types,
            &sim.buffers.globals,
            &self.instances,
            &self.stats,
            &self.signals,
            &sim.buffers.tls,
            &self.phases,
            &self.states,
            &self.history,
            &self.render_links,
            &self.render_routes,
        ];
        let entries: Vec<_> = buffers
            .iter()
            .enumerate()
            .map(|(i, b)| wgpu::BindGroupEntry {
                binding: i as u32,
                resource: b.as_entire_binding(),
            })
            .collect();
        let group = g.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.compute.get_bind_group_layout(0),
            entries: &entries,
        });
        let mut e = g.device.create_command_encoder(&Default::default());
        e.clear_buffer(&self.stats, 0, None);
        {
            let mut p = e.begin_compute_pass(&Default::default());
            p.set_pipeline(&self.compute);
            p.set_bind_group(0, &group, &[]);
            p.dispatch_workgroups(self.total.max(1).div_ceil(64), 1, 1);
        }
        {
            let mut p = e.begin_render_pass(&wgpu::RenderPassDescriptor {
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &self.msaa,
                    resolve_target: Some(&self.hdr),
                    depth_slice: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Discard,
                    },
                })],
                ..Default::default()
            });
            p.set_pipeline(&self.road);
            p.set_bind_group(0, &self.draw_group, &[]);
            p.set_vertex_buffer(0, self.roads.slice(..));
            p.draw(0..self.road_count, 0..1);
            p.set_pipeline(&self.car);
            let cg = g.device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: None,
                layout: &self.car.get_bind_group_layout(0),
                entries: &[wgpu::BindGroupEntry {
                    binding: 0,
                    resource: self.camera.as_entire_binding(),
                }],
            });
            p.set_bind_group(0, &cg, &[]);
            p.set_vertex_buffer(0, self.instances.slice(..));
            p.draw(0..3, 0..self.total);
        }
        let view = self.output.create_view(&Default::default());
        {
            let mut p = e.begin_render_pass(&wgpu::RenderPassDescriptor {
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    depth_slice: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            p.set_pipeline(&self.tone);
            p.set_bind_group(0, &self.tone_group, &[]);
            p.draw(0..3, 0..1);
        }
        e.copy_texture_to_buffer(
            self.output.as_image_copy(),
            wgpu::TexelCopyBufferInfo {
                buffer: &self.readback,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(self.stride),
                    rows_per_image: None,
                },
            },
            wgpu::Extent3d {
                width: self.width,
                height: self.height,
                depth_or_array_layers: 1,
            },
        );
        g.queue.submit([e.finish()]);
        self.readback
            .slice(..)
            .map_async(wgpu::MapMode::Read, |r| r.expect("map frame"));
        g.wait();
        let data = self.readback.get_mapped_range(..).expect("mapped frame");
        let mut out = Vec::with_capacity((self.width * self.height * 4) as usize);
        for row in data.chunks(self.stride as usize) {
            out.extend_from_slice(&row[..(self.width * 4) as usize]);
        }
        drop(data);
        self.readback.unmap();
        let stats = sim.read::<u32>(g, &self.stats, 2);
        (
            out,
            stats[0],
            stats[1] as f32 / 100.0 / stats[0].max(1) as f32,
        )
    }
}
