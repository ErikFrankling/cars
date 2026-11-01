//! Headless HDR renderer. Vehicle state stays on the GPU; pixels and statistics come back.
use crate::{Gpu, closeup, net::Net, sim::Sim, world::World};
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
    signals: wgpu::Buffer,
    phases: wgpu::Buffer,
    states: wgpu::Buffer,
    capacity: u32,
    total: u32,
    dt: f32,
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
    close_road: wgpu::RenderPipeline,
    close_car: wgpu::RenderPipeline,
    close_signal: wgpu::RenderPipeline,
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
    approaches: Vec<closeup::Approach>,
    meshes: Vec<CloseMesh>,
    uniform: [u32; 12],
}
struct CloseMesh {
    region: [f32; 4],
    buffer: wgpu::Buffer,
    count: u32,
}
/// Where a rendered vehicle really is, eased and interpolated. Same index as the vehicle buffer.
#[repr(C)]
#[derive(Clone, Copy, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct Instance {
    pub xy: [f32; 2],
    pub dir: [f32; 2],
    pub length: f32,
    pub width: f32,
    pub ratio: f32,
    pub alive: f32,
    pub detail: f32,
    pub seed: f32,
    pub pad: [f32; 2],
}
/// Close style fades in between these scales, in metres per pixel.
const CLOSE_FROM: f32 = 0.6;
const CLOSE_FULL: f32 = 0.35;
const MAX_MESHES: usize = 12;
fn buffer(g: &Gpu, name: &str, data: &[u8], usage: wgpu::BufferUsages) -> wgpu::Buffer {
    let padded = vec![0; 256];
    g.device
        .create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some(name),
            contents: if data.is_empty() { &padded } else { data },
            usage,
        })
}
fn turn_bits(dir: u8) -> u32 {
    match dir {
        b'l' | b'L' | b't' | b'T' => 2,
        b'r' | b'R' => 4,
        _ => 0,
    }
}
impl Renderer {
    /// `widths` is the body width of each vehicle type. `far_roads` builds the far-away road
    /// mesh; a job that only ever looks close can leave it out.
    pub fn new(g: &Gpu, w: &World, net: &Net, widths: &[f32], width: u32, height: u32, far_roads: bool) -> Self {
        let storage = wgpu::BufferUsages::STORAGE;
        let mut points = Vec::<[f32; 4]>::new();
        let mut ranges = Vec::<[u32; 4]>::new();
        let mut roads = Vec::<[f32; 6]>::new();
        let turns: std::collections::HashMap<(u32, u32), u32> = net
            .conns
            .iter()
            .filter_map(|c| Some(((net.lane_of(c.from_edge, c.from_lane)?, c.to_edge), turn_bits(c.dir))))
            .collect();
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
            if !far_roads {
                continue;
            }
            let lane = &w.lanes[i];
            let tint = if lane.flags & 1 != 0 {
                0.35
            } else if lane.speed > 25.0 {
                1.5
            } else {
                1.0
            };
            for pair in shape.windows(2) {
                let a = pair[0];
                let b = pair[1];
                let d = ((b[0] - a[0]).powi(2) + (b[1] - a[1]).powi(2)).sqrt();
                if d < 0.001 {
                    continue;
                }
                let n = [-(b[1] - a[1]) / d, (b[0] - a[0]) / d];
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
        // A driver inside a junction keeps indicating the turn it is making.
        for c in &net.conns {
            let bits = turn_bits(c.dir);
            if let Some(via) = c.via
                && let Some(r) = ranges.get_mut(via as usize)
            {
                r[3] = bits;
            }
            if let Some(from) = net.lane_of(c.from_edge, c.from_lane)
                && net.is_internal_lane(from)
                && let Some(r) = ranges.get_mut(from as usize)
            {
                r[3] = bits;
            }
        }
        let mut by_lane = std::collections::BTreeMap::<u32, Vec<(u32, u32, u32)>>::new();
        for l in &w.links {
            let Some(lane) = w.lanes.get(l.from_lane as usize) else {
                continue;
            };
            if l.tl == u32::MAX || lane.flags & 1 != 0 {
                continue;
            }
            let bits = *turns.get(&(l.from_lane, l.to_edge)).unwrap_or(&0);
            // Right turns sit on the right of the lane, so sort right, straight, left.
            let order = match bits {
                4 => 0,
                0 => 1,
                _ => 2,
            };
            let heads = by_lane.entry(l.from_lane).or_default();
            if !heads.iter().any(|h| h.0 == order && h.2 == l.tl_index) {
                heads.push((order, l.tl, l.tl_index));
            }
        }
        let mut signal_data = Vec::<[u32; 8]>::new();
        for (lane, mut heads) in by_lane {
            heads.sort();
            let (start, count) = w.shape_range[lane as usize];
            if count < 2 {
                continue;
            }
            let b = w.shapes[(start + count - 1) as usize];
            let a = w.shapes[(start + count - 2) as usize];
            let d = ((b[0] - a[0]).powi(2) + (b[1] - a[1]).powi(2)).sqrt().max(0.001);
            let t = [(b[0] - a[0]) / d, (b[1] - a[1]) / d];
            let lane_width = net.lanes[lane as usize].width;
            let slot = lane_width / heads.len() as f32;
            for (k, &(order, tl, index)) in heads.iter().enumerate() {
                let across = (k as f32 + 0.5) * slot - lane_width * 0.5;
                let bits = [4u32, 0, 2][order as usize];
                signal_data.push([
                    (b[0] + t[0] * 0.85 - t[1] * across).to_bits(),
                    (b[1] + t[1] * 0.85 + t[0] * across).to_bits(),
                    t[0].to_bits(),
                    t[1].to_bits(),
                    tl,
                    index,
                    slot.to_bits(),
                    bits,
                ]);
            }
        }
        let link_data: Vec<[u32; 4]> = w
            .links
            .iter()
            .map(|l| [l.to_edge, *turns.get(&(l.from_lane, l.to_edge)).unwrap_or(&0), 0, 0])
            .collect();
        let render_links = buffer(g, "render link turns", bytemuck::cast_slice(&link_data), storage);
        let render_routes = buffer(g, "render routes", bytemuck::cast_slice(&w.routes), storage);
        let history = g.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("render history by trip"),
            size: (w.trips.len().max(1) * 64) as u64,
            usage: storage | wgpu::BufferUsages::COPY_SRC,
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
            &[0; 48],
            wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        );
        let ranges = buffer(g, "shape ranges", bytemuck::cast_slice(&ranges), storage);
        let points = buffer(
            g,
            "cumulative geometry",
            bytemuck::cast_slice(&points),
            storage,
        );
        let type_data: Vec<[f32; 4]> = w
            .vtypes
            .iter()
            .zip(widths)
            .map(|(t, &body)| [t.length, body, if t.model >= 2 { 1.0 } else { 0.0 }, 0.0])
            .collect();
        let types = buffer(g, "render types", bytemuck::cast_slice(&type_data), storage);
        let instances = g.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("instances"),
            size: total.max(1) as u64 * 48,
            usage: storage | wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_SRC,
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
        let camera_layout = g.device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("camera"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX | wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });
        let layout = g.device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("drawing"),
            bind_group_layouts: &[Some(&camera_layout)],
            immediate_size: 0,
        });
        let road_attrs = wgpu::vertex_attr_array![0=>Float32x2,1=>Float32x2,2=>Float32,3=>Float32];
        let car_attrs = wgpu::vertex_attr_array![0=>Float32x2,1=>Float32x2,2=>Float32,3=>Float32,4=>Float32,5=>Float32,6=>Float32,7=>Float32];
        let close_attrs = wgpu::vertex_attr_array![0=>Float32x2,1=>Float32x2,2=>Float32,3=>Float32x2,4=>Unorm8x4];
        let additive = wgpu::BlendState {
            color: wgpu::BlendComponent {
                src_factor: wgpu::BlendFactor::One,
                dst_factor: wgpu::BlendFactor::One,
                operation: wgpu::BlendOperation::Add,
            },
            alpha: wgpu::BlendComponent::REPLACE,
        };
        let over = wgpu::BlendState {
            color: wgpu::BlendComponent {
                src_factor: wgpu::BlendFactor::One,
                dst_factor: wgpu::BlendFactor::OneMinusSrcAlpha,
                operation: wgpu::BlendOperation::Add,
            },
            alpha: wgpu::BlendComponent::OVER,
        };
        let make = |entry: &str, frag: &str, stride, step, attributes: &[wgpu::VertexAttribute], blend| {
            g.device
                .create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                    label: Some(entry),
                    layout: Some(&layout),
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
                            blend: Some(blend),
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
        let road = make("road", "road_frag", 24, wgpu::VertexStepMode::Vertex, &road_attrs, additive);
        let car = make("car", "car_frag", 48, wgpu::VertexStepMode::Instance, &car_attrs, additive);
        let close_road = make("close_road", "close_road_frag", 32, wgpu::VertexStepMode::Vertex, &close_attrs, over);
        let close_car = make("close_car", "close_car_frag", 48, wgpu::VertexStepMode::Instance, &car_attrs, over);
        let close_signal = make("close_signal", "close_signal_frag", 48, wgpu::VertexStepMode::Instance, &car_attrs, over);
        let draw_group = g.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &camera_layout,
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
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&hdr),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: camera.as_entire_binding(),
                },
            ],
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
            signals,
            phases,
            states,
            capacity,
            total,
            dt: w.params.dt,
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
            close_road,
            close_car,
            close_signal,
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
            approaches: closeup::approaches(net),
            meshes: Vec::new(),
            uniform: [0; 12],
        }
    }
    /// Work out every vehicle's pose for this frame. `blend` is how far the moment shown lies
    /// between the previous step and the current one.
    /// Returns the vehicle count and mean speed.
    pub fn prepare(&mut self, g: &Gpu, sim: &Sim, blend: f32, mode: u32) -> (u32, f32) {
        self.uniform[2] = (self.width as f32).to_bits();
        self.uniform[3] = (self.height as f32).to_bits();
        self.uniform[4] = 1f32.to_bits();
        self.uniform[5] = mode;
        self.uniform[6] = self.capacity;
        self.uniform[7] = ((sim.step as f32 - 1.0 + blend) * self.dt).to_bits();
        self.uniform[9] = blend.to_bits();
        self.uniform[10] = (sim.step as f32 * self.dt).to_bits();
        g.queue
            .write_buffer(&self.camera, 0, bytemuck::cast_slice(&self.uniform));
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
        g.queue.submit([e.finish()]);
        let stats = sim.read::<u32>(g, &self.stats, 2);
        (
            stats[0],
            stats[1] as f32 / 100.0 / stats[0].max(1) as f32,
        )
    }
    /// Poses of the first `n` vehicles, as drawn.
    pub fn instances(&self, g: &Gpu, sim: &Sim, n: u32) -> Vec<Instance> {
        sim.read(g, &self.instances, n.min(self.capacity) as u64)
    }
    /// Where a trip was last drawn and when, if it has been on the road at all.
    pub fn trip_position(&self, g: &Gpu, trip: u32) -> Option<([f32; 2], f32)> {
        let staging = g.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("trip pose"),
            size: 64,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        let mut e = g.device.create_command_encoder(&Default::default());
        e.copy_buffer_to_buffer(&self.history, trip as u64 * 64, &staging, 0, 64);
        g.queue.submit([e.finish()]);
        let slice = staging.slice(..);
        slice.map_async(wgpu::MapMode::Read, |_| {});
        g.wait();
        let data = slice.get_mapped_range().expect("mapped");
        let h: &[f32] = bytemuck::cast_slice(&data[..]);
        let out = (h[14].to_bits() != 0).then_some(([h[8], h[9]], h[12]));
        drop(data);
        staging.unmap();
        out
    }
    fn mesh(&mut self, g: &Gpu, net: &Net, cam: Camera) -> usize {
        let half = [
            self.width as f32 * 0.5 * cam.metres_per_pixel,
            self.height as f32 * 0.5 * cam.metres_per_pixel,
        ];
        let view = [
            cam.center[0] - half[0],
            cam.center[1] - half[1],
            cam.center[0] + half[0],
            cam.center[1] + half[1],
        ];
        if let Some(i) = self.meshes.iter().position(|m| {
            m.region[0] <= view[0] && m.region[1] <= view[1] && m.region[2] >= view[2] && m.region[3] >= view[3]
        }) {
            return i;
        }
        let m = [half[0] * 1.2 + 80.0, half[1] * 1.2 + 80.0];
        let region = [view[0] - m[0], view[1] - m[1], view[2] + m[0], view[3] + m[1]];
        let vertices = closeup::build(net, &self.approaches, region);
        let mesh = CloseMesh {
            region,
            count: vertices.len() as u32,
            buffer: buffer(g, "close road", bytemuck::cast_slice(&vertices), wgpu::BufferUsages::VERTEX),
        };
        if self.meshes.len() >= MAX_MESHES {
            self.meshes.remove(0);
        }
        self.meshes.push(mesh);
        self.meshes.len() - 1
    }
    /// Draw what `prepare` worked out through one camera.
    pub fn draw(&mut self, g: &Gpu, net: &Net, cam: Camera) -> Vec<u8> {
        let close = ((CLOSE_FROM - cam.metres_per_pixel) / (CLOSE_FROM - CLOSE_FULL)).clamp(0.0, 1.0);
        let close = close * close * (3.0 - 2.0 * close);
        self.uniform[0] = cam.center[0].to_bits();
        self.uniform[1] = cam.center[1].to_bits();
        self.uniform[4] = cam.metres_per_pixel.to_bits();
        self.uniform[8] = close.to_bits();
        g.queue
            .write_buffer(&self.camera, 0, bytemuck::cast_slice(&self.uniform));
        let mesh = (close > 0.0).then(|| self.mesh(g, net, cam));
        let mut e = g.device.create_command_encoder(&Default::default());
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
            p.set_bind_group(0, &self.draw_group, &[]);
            if close < 1.0 {
                p.set_pipeline(&self.road);
                p.set_vertex_buffer(0, self.roads.slice(..));
                p.draw(0..self.road_count, 0..1);
                p.set_pipeline(&self.car);
                p.set_vertex_buffer(0, self.instances.slice(..));
                p.draw(0..3, 0..self.total);
            }
            if let Some(i) = mesh {
                let m = &self.meshes[i];
                p.set_pipeline(&self.close_road);
                p.set_vertex_buffer(0, m.buffer.slice(..));
                p.draw(0..m.count, 0..1);
                p.set_vertex_buffer(0, self.instances.slice(..));
                p.set_pipeline(&self.close_signal);
                p.draw(0..6, self.capacity..self.total);
                p.set_pipeline(&self.close_car);
                p.draw(0..6, 0..self.capacity);
            }
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
        out
    }
}
