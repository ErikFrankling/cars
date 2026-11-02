//! Compact binary trajectories, written while a simulation runs and rendered after it.
//!
//! The simulation never knows: a `Tracer` runs the steps through the public `Sim::run` and copies
//! finished vehicle state to its own staging buffers, between submissions. Layout in RECORDING.md.
use bytemuck::{Pod, Zeroable};
use cars_core::{
    Gpu,
    demand::Demand,
    net::Net,
    sim::Sim,
    why::{KINDS, WHY_WORDS, WhyRecord},
    world::{GpuGlobals, GpuTlsState, GpuVeh, World},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::{HashMap, VecDeque},
    fs::File,
    io::{BufWriter, Read, Write},
    os::unix::fs::FileExt,
    path::{Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    time::Instant,
};

pub const MAGIC: &[u8; 8] = b"CARSTRC2";
const FRAME_MAGIC: u32 = u32::from_le_bytes(*b"TRFR");
pub const NONE_LANE: u32 = 0xff_ffff;
pub const NO_LINK: u32 = 63;
pub const LANE_CHANGED: u32 = 1;
pub const TELEPORT: u32 = 2;
pub const COLLISION: u32 = 4;
pub const WILL_PASS: u32 = 8;
pub const HAVE_TO_WAIT: u32 = 16;
pub const WANT_LEFT: u32 = 32;
pub const WANT_RIGHT: u32 = 64;
pub const ON_JUNCTION: u32 = 128;
const F_REMOVED: u32 = 1;
const F_LANE_CHANGED: u32 = 32;
const F_ON_JUNCTION: u32 = 128;
const F_WILL_PASS: u32 = 512;
const F_HAVE_TO_WAIT: u32 = 2048;
const NAME_LANE: u32 = 1 << 31;

/// One vehicle in one frame, 24 bytes. A taken off vehicle keeps its last lane and position.
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Default)]
pub struct Record {
    /// Trip index, then flags in the top byte.
    pub trip_flags: u32,
    /// Lane index, then vehicle type in the top byte.
    pub lane_type: u32,
    /// Previous lane index, then waiting seconds, saturating, in the top byte.
    pub prev_wait: u32,
    /// Front bumper in 1/256 m, then the index of the next link among this lane's links.
    pub pos_link: u32,
    /// 1/256 m/s².
    pub acc: i16,
    /// 1/512 m/s.
    pub speed: u16,
    /// Sideways from the lane centre, left positive, in 1/256 m.
    pub lat: i16,
    pub pad: u16,
}
impl Record {
    pub fn lat(&self) -> f32 {
        self.lat as f32 / 256.0
    }
    pub fn trip(&self) -> u32 {
        self.trip_flags & 0xff_ffff
    }
    pub fn flags(&self) -> u32 {
        self.trip_flags >> 24
    }
    pub fn lane(&self) -> u32 {
        self.lane_type & 0xff_ffff
    }
    pub fn vtype(&self) -> u32 {
        self.lane_type >> 24
    }
    pub fn prev_lane(&self) -> u32 {
        self.prev_wait & 0xff_ffff
    }
    pub fn wait(&self) -> f32 {
        (self.prev_wait >> 24) as f32
    }
    pub fn pos(&self) -> f32 {
        (self.pos_link & 0xff_ffff) as f32 / 256.0
    }
    pub fn link_offset(&self) -> u32 {
        (self.pos_link >> 24) & 63
    }
    pub fn speed(&self) -> f32 {
        self.speed as f32 / 512.0
    }
    pub fn acc(&self) -> f32 {
        self.acc as f32 / 256.0
    }
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Default)]
struct FrameHead {
    magic: u32,
    step: u32,
    records: u32,
    names_bytes: u32,
    teleports: u32,
    collisions: u32,
    /// Every vehicle on the road, also outside a bbox, and their mean speed.
    running: u32,
    mean_speed: f32,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct VTypeInfo {
    pub id: String,
    pub length: f32,
    pub width: f32,
    pub min_gap: f32,
    pub decel: f32,
    pub emergency: f32,
    pub model: u32,
}
#[derive(Serialize, Deserialize, Clone)]
pub struct TlsInfo {
    pub index: u32,
    pub id: String,
    /// State string of each phase, as SUMO's tlsStates. Reads by link index.
    pub phases: Vec<String>,
}
#[derive(Serialize, Deserialize, Clone)]
pub struct Header {
    pub net_hash: String,
    pub dt: f32,
    /// Simulation time of step 0. A frame after `step` steps is labelled sim_begin + (step-1)*dt.
    pub sim_begin: f64,
    pub begin: f32,
    pub end: f32,
    pub stride: u32,
    pub bbox: Vec<f32>,
    pub time_to_teleport: f32,
    pub dummy_lane: u32,
    pub vtypes: Vec<VTypeInfo>,
    /// Signals in scope, in the order of each frame's phase array.
    pub tls: Vec<TlsInfo>,
}

/// Depends on what a trace's lane and link numbers mean, not on how the file is written.
pub fn net_hash(net: &Net) -> String {
    let mut h = 0xcbf29ce484222325u64;
    let mut eat = |bytes: &[u8]| {
        for &b in bytes {
            h = (h ^ b as u64).wrapping_mul(0x100000001b3);
        }
    };
    for l in &net.lanes {
        eat(l.id.as_bytes());
        eat(&l.length.to_le_bytes());
        for p in &l.shape {
            eat(bytemuck::cast_slice(p));
        }
    }
    for c in &net.conns {
        eat(bytemuck::cast_slice(&[c.from_edge, c.from_lane, c.to_edge, c.to_lane, c.tl.unwrap_or(u32::MAX), c.link_index as u32]));
        eat(&[c.state, c.dir]);
    }
    for t in &net.tls {
        eat(t.id.as_bytes());
    }
    format!("{h:016x}")
}

#[derive(Clone, Default)]
pub struct Options {
    pub begin: f32,
    pub end: f32,
    pub stride: u32,
    pub bbox: Vec<f32>,
}

const WHY_MAGIC: &[u8; 8] = b"CARSWHY1";

struct Slot {
    buffer: wgpu::Buffer,
    ready: Arc<AtomicBool>,
    n: u64,
    n_tls: u64,
    n_why: u64,
    has_why: bool,
    step: u32,
    teleports: u32,
    collisions: u32,
}

pub struct Tracer {
    first: u64,
    last: u64,
    stride: u64,
    head: wgpu::Buffer,
    free: Vec<Slot>,
    made: usize,
    busy: VecDeque<Slot>,
    send: Option<mpsc::Sender<Slot>>,
    back: mpsc::Receiver<Slot>,
    writer: Option<std::thread::JoinHandle<Stats>>,
    n_tls: u64,
    capture_ms: f64,
    frames: u64,
    path: PathBuf,
}

#[derive(Default)]
struct Stats {
    records: u64,
    bytes: u64,
    teleports: u64,
    collisions: u64,
}

const SLOTS: usize = 6;

impl Tracer {
    /// Takes the routes from `world`: they are only on the CPU for finding each vehicle's next link.
    pub fn new(path: &Path, o: Options, net: &Net, world: &mut World, demand: &Demand, widths: &[f32], sim_begin: f32, time_to_teleport: f32, g: &Gpu) -> std::io::Result<Self> {
        let dt = world.params.dt;
        if !o.bbox.is_empty() && o.bbox.len() != 4 {
            return Err(std::io::Error::other("--trace-bbox takes x0,y0,x1,y1"));
        }
        if demand.vtypes.len() > 256 || world.trips.len() >= 0xff_ffff || world.lanes.len() >= 0xff_ffff {
            return Err(std::io::Error::other("trace holds at most 256 vehicle types and 16 million trips or lanes"));
        }
        let first = (((o.begin - sim_begin) / dt).ceil().max(0.0) as u64 + 1).max(1);
        let last = ((o.end - sim_begin) / dt).floor().max(0.0) as u64 + 1;
        let in_box: Vec<bool> = net
            .lanes
            .iter()
            .map(|l| o.bbox.len() != 4 || l.shape.iter().any(|p| p[0] >= o.bbox[0] && p[1] >= o.bbox[1] && p[0] <= o.bbox[2] && p[1] <= o.bbox[3]))
            .collect();
        let mut in_scope = vec![o.bbox.len() != 4; world.tls.len()];
        for l in &world.links {
            if l.tl != u32::MAX && in_box.get(l.from_lane as usize).is_some_and(|&b| b) {
                in_scope[l.tl as usize] = true;
            }
        }
        let tls: Vec<TlsInfo> = in_scope
            .iter()
            .enumerate()
            .filter(|(_, on)| **on)
            .map(|(i, _)| {
                let t = &world.tls[i];
                let count = net.tls[i].phases.first().map_or(0, |p| p.state.len());
                TlsInfo {
                    index: i as u32,
                    id: net.tls[i].id.clone(),
                    phases: (0..t.n_phases)
                        .map(|k| {
                            let start = world.phases[(t.first_phase + k) as usize].state_start as usize;
                            world.states[start..start + count].iter().map(|&c| c as u8 as char).collect()
                        })
                        .collect(),
                }
            })
            .collect();
        let header = Header {
            net_hash: net_hash(net),
            dt,
            sim_begin: sim_begin as f64,
            begin: o.begin,
            end: o.end,
            stride: o.stride.max(1),
            bbox: o.bbox.clone(),
            time_to_teleport,
            dummy_lane: world.params.dummy_lane,
            vtypes: demand
                .vtypes
                .iter()
                .zip(&world.vtypes)
                .zip(widths)
                .map(|((d, t), &width)| VTypeInfo { id: d.id.clone(), length: t.length, width, min_gap: t.min_gap, decel: t.decel, emergency: t.emergency, model: t.model })
                .collect(),
            tls,
        };
        let mut file = BufWriter::with_capacity(1 << 20, File::create(path)?);
        let json = serde_json::to_vec(&header).map_err(std::io::Error::other)?;
        let pad = json.len().next_multiple_of(4) - json.len();
        file.write_all(MAGIC)?;
        file.write_all(&((json.len() + pad) as u32).to_le_bytes())?;
        file.write_all(&json)?;
        file.write_all(&b"    "[..pad])?;
        let (send, take) = mpsc::channel::<Slot>();
        let (give, back) = mpsc::channel();
        let writer = Writer {
            file,
            why_path: PathBuf::from(format!("{}.why", path.display())),
            why_file: None,
            why_records: Vec::new(),
            give,
            routes: std::mem::take(&mut world.routes),
            lane_links: world.lanes.iter().map(|l| (l.links_start, l.links_count)).collect(),
            to_edge: world.links.iter().map(|l| l.to_edge).collect(),
            in_box,
            tls_scope: header.tls.iter().map(|t| t.index).collect(),
            dummy: world.params.dummy_lane,
            threshold: if time_to_teleport > 0.0 { time_to_teleport - o.stride.max(1) as f32 * dt - 1e-3 } else { f32::MAX },
            last_seen: vec![Last { lane: u32::MAX, pos: 0.0, wait: 0.0 }; world.trips.len()],
            lane_width: world.lanes.iter().map(|l| l.width).collect(),
            vtype_lat: world.vtypes.iter().map(|t| t.v_lat).collect(),
            trip_seen: vec![false; world.trips.len()],
            lane_seen: vec![false; net.lanes.len()],
            trip_names: world.trip_source.iter().map(|&s| demand.ids[demand.trips[s as usize].id as usize].clone()).collect(),
            lane_names: net.lanes.iter().map(|l| l.id.clone()).collect(),
            counters: None,
            names: Vec::new(),
            records: Vec::new(),
            stats: Stats::default(),
        };
        let handle = std::thread::Builder::new().name("trace writer".into()).spawn(move || writer.run(take))?;
        let head = g.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("trace head"),
            size: size_of::<GpuGlobals>() as u64 + 64,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        Ok(Self {
            first,
            last,
            stride: o.stride.max(1) as u64,
            head,
            free: Vec::new(),
            made: 0,
            busy: VecDeque::new(),
            send: Some(send),
            back,
            writer: Some(handle),
            n_tls: world.tls.len() as u64,
            capture_ms: 0.0,
            frames: 0,
            path: path.to_path_buf(),
        })
    }

    fn next_capture(&self, now: u64) -> u64 {
        let next = if now < self.first { self.first } else { self.first + ((now - self.first) / self.stride + 1) * self.stride };
        if next <= self.last { next } else { u64::MAX }
    }

    /// `Sim::run`, stopping where the window asks for a copy of the vehicles.
    pub fn run(&mut self, g: &Gpu, sim: &mut Sim, chunk: u64) -> u64 {
        let mut moved = 0;
        while moved < chunk {
            let next = self.next_capture(sim.step);
            let stop = next.min(sim.step + (chunk - moved));
            moved += sim.run(g, stop - sim.step);
            if sim.step == next {
                let t = Instant::now();
                self.capture(g, sim);
                self.capture_ms += t.elapsed().as_secs_f64() * 1000.0;
            }
        }
        moved
    }

    fn capture(&mut self, g: &Gpu, sim: &Sim) {
        self.collect(g, false);
        let globals_bytes = size_of::<GpuGlobals>() as u64;
        let mut e = g.device.create_command_encoder(&Default::default());
        e.copy_buffer_to_buffer(&sim.buffers.globals, 0, &self.head, 0, globals_bytes);
        e.copy_buffer_to_buffer(&sim.buffers.counters, 0, &self.head, globals_bytes, 64);
        g.queue.submit([e.finish()]);
        let slice = self.head.slice(..);
        slice.map_async(wgpu::MapMode::Read, |_| {});
        g.wait();
        let (n_active, counters) = {
            let data = slice.get_mapped_range().expect("mapped");
            let globals: GpuGlobals = bytemuck::pod_read_unaligned(&data[..globals_bytes as usize]);
            let counters: [u32; 16] = bytemuck::pod_read_unaligned(&data[globals_bytes as usize..]);
            (globals.n_active, counters)
        };
        self.head.unmap();
        let n = n_active as u64 + counters[0] as u64;
        let veh_bytes = n * size_of::<GpuVeh>() as u64;
        let tls_bytes = self.n_tls * size_of::<GpuTlsState>() as u64;
        let why_bytes = if sim.buffers.why.is_some() { n * WHY_WORDS * 4 } else { 0 };
        let size = (veh_bytes + tls_bytes + why_bytes).max(256);
        let mut slot = self.take_slot(g, size);
        let mut e = g.device.create_command_encoder(&Default::default());
        if veh_bytes > 0 {
            e.copy_buffer_to_buffer(sim.current_veh(), 0, &slot.buffer, 0, veh_bytes);
        }
        if tls_bytes > 0 {
            e.copy_buffer_to_buffer(&sim.buffers.tls, 0, &slot.buffer, veh_bytes, tls_bytes);
        }
        if why_bytes > 0 {
            e.copy_buffer_to_buffer(sim.buffers.why.as_ref().expect("Sim::with_why"), 0, &slot.buffer, veh_bytes + tls_bytes, why_bytes);
        }
        g.queue.submit([e.finish()]);
        slot.n = n;
        slot.n_why = why_bytes / (WHY_WORDS * 4);
        slot.has_why = sim.buffers.why.is_some();
        slot.n_tls = self.n_tls;
        slot.step = sim.step as u32;
        slot.teleports = counters[4];
        slot.collisions = counters[7];
        slot.ready.store(false, Ordering::Release);
        let ready = slot.ready.clone();
        // The next wait for the simulation also delivers this, so the copy costs no wait of its own.
        slot.buffer.slice(..).map_async(wgpu::MapMode::Read, move |_| ready.store(true, Ordering::Release));
        self.busy.push_back(slot);
        self.frames += 1;
    }

    fn take_slot(&mut self, g: &Gpu, size: u64) -> Slot {
        loop {
            self.free.extend(self.back.try_iter());
            if !self.free.is_empty() || self.made < SLOTS {
                break;
            }
            if self.busy.is_empty() {
                self.free.push(self.back.recv().expect("trace writer stopped"));
            } else {
                g.wait();
                self.collect(g, false);
            }
        }
        if let Some(i) = self.free.iter().position(|s| s.buffer.size() >= size) {
            return self.free.swap_remove(i);
        }
        if self.free.pop().is_none() {
            self.made += 1;
        }
        Slot {
            buffer: g.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("trace staging"),
                size: (size + size / 4).next_multiple_of(4),
                usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
                mapped_at_creation: false,
            }),
            ready: Arc::new(AtomicBool::new(false)),
            n: 0,
            n_tls: 0,
            n_why: 0,
            has_why: false,
            step: 0,
            teleports: 0,
            collisions: 0,
        }
    }

    /// Hand finished copies to the writer, in order, still mapped so it does the reading.
    /// `all` waits for every one still on its way.
    fn collect(&mut self, g: &Gpu, all: bool) {
        if all && !self.busy.is_empty() {
            g.wait();
        }
        while self.busy.front().is_some_and(|s| s.ready.load(Ordering::Acquire)) {
            let slot = self.busy.pop_front().expect("front");
            self.send.as_ref().expect("writer").send(slot).expect("trace writer stopped");
        }
    }

    pub fn finish(mut self, g: &Gpu) {
        self.collect(g, true);
        self.send = None;
        let stats = self.writer.take().expect("writer").join().expect("trace writer failed");
        eprintln!(
            "trace {}: {} frames, {} records, {:.1} MB, {:.1} bytes per record, capture {:.2}s, {} teleports {} collisions flagged",
            self.path.display(),
            self.frames,
            stats.records,
            stats.bytes as f64 / 1e6,
            stats.bytes as f64 / stats.records.max(1) as f64,
            self.capture_ms / 1000.0,
            stats.teleports,
            stats.collisions
        );
    }
}

#[derive(Clone, Copy)]
struct Last {
    lane: u32,
    pos: f32,
    wait: f32,
}

struct Writer {
    file: BufWriter<File>,
    why_path: PathBuf,
    why_file: Option<BufWriter<File>>,
    why_records: Vec<WhyRecord>,
    give: mpsc::Sender<Slot>,
    routes: Vec<u32>,
    lane_links: Vec<(u32, u32)>,
    to_edge: Vec<u32>,
    in_box: Vec<bool>,
    tls_scope: Vec<u32>,
    dummy: u32,
    threshold: f32,
    last_seen: Vec<Last>,
    lane_width: Vec<f32>,
    vtype_lat: Vec<f32>,
    trip_seen: Vec<bool>,
    lane_seen: Vec<bool>,
    trip_names: Vec<String>,
    lane_names: Vec<String>,
    counters: Option<(u32, u32)>,
    names: Vec<u8>,
    records: Vec<Record>,
    stats: Stats,
}

fn why_head(path: &Path) -> std::io::Result<BufWriter<File>> {
    let mut w = BufWriter::with_capacity(1 << 20, File::create(path)?);
    let json = serde_json::to_vec(&serde_json::json!({"record": size_of::<WhyRecord>(), "kinds": KINDS})).map_err(std::io::Error::other)?;
    let pad = json.len().next_multiple_of(4) - json.len();
    w.write_all(WHY_MAGIC)?;
    w.write_all(&((json.len() + pad) as u32).to_le_bytes())?;
    w.write_all(&json)?;
    w.write_all(&b"    "[..pad])?;
    Ok(w)
}

fn name_entry(out: &mut Vec<u8>, id: u32, name: &str) {
    out.extend_from_slice(&id.to_le_bytes());
    out.extend_from_slice(&(name.len() as u32).to_le_bytes());
    out.extend_from_slice(name.as_bytes());
    out.resize(out.len().next_multiple_of(4), 0);
}

impl Writer {
    fn run(mut self, take: mpsc::Receiver<Slot>) -> Stats {
        while let Ok(slot) = take.recv() {
            let veh_bytes = (slot.n * size_of::<GpuVeh>() as u64) as usize;
            let tls_bytes = (slot.n_tls * size_of::<GpuTlsState>() as u64) as usize;
            {
                let data = slot.buffer.slice(..).get_mapped_range().expect("mapped");
                let vehicles: &[GpuVeh] = bytemuck::cast_slice(&data[..veh_bytes]);
                let tls: &[GpuTlsState] = bytemuck::cast_slice(&data[veh_bytes..veh_bytes + tls_bytes]);
                let why_bytes = (slot.n_why * WHY_WORDS * 4) as usize;
                let why: &[u32] = bytemuck::cast_slice(&data[veh_bytes + tls_bytes..veh_bytes + tls_bytes + why_bytes]);
                self.frame(&slot, vehicles, tls, why);
            }
            slot.buffer.unmap();
            let _ = self.give.send(slot);
        }
        self.file.flush().expect("trace write");
        if let Some(w) = self.why_file.as_mut() {
            w.flush().expect("why write");
        }
        self.stats
    }

    fn next_link(&self, v: &GpuVeh) -> u32 {
        if v.route_i + 1 >= v.route_end {
            return NO_LINK;
        }
        // A route handed out during the run is not here. Only the drawing of the next link is lost.
        let Some(&want) = self.routes.get(v.route_i as usize + 1) else { return NO_LINK };
        let (start, count) = self.lane_links[v.lane as usize];
        (0..count.min(NO_LINK)).find(|&k| self.to_edge[(start + k) as usize] == want).unwrap_or(NO_LINK)
    }

    fn see_lane(&mut self, lane: u32) {
        let i = lane as usize;
        if i < self.lane_seen.len() && !self.lane_seen[i] {
            self.lane_seen[i] = true;
            name_entry(&mut self.names, lane | NAME_LANE, &self.lane_names[i]);
        }
    }

    fn see_trip(&mut self, trip: u32) {
        let i = trip as usize;
        if !self.trip_seen[i] {
            self.trip_seen[i] = true;
            name_entry(&mut self.names, trip, &self.trip_names[i]);
        }
    }

    fn frame(&mut self, c: &Slot, vehicles: &[GpuVeh], tls: &[GpuTlsState], why: &[u32]) {
        let (teleports0, collisions0) = self.counters.unwrap_or((c.teleports, c.collisions));
        self.counters = Some((c.teleports, c.collisions));
        let (new_teleports, new_collisions) = (c.teleports - teleports0, c.collisions - collisions0);
        self.names.clear();
        self.records.clear();
        self.why_records.clear();
        let words = WHY_WORDS as usize;
        let mut running = 0u32;
        let mut speed_sum = 0f64;
        for v in vehicles {
            if v.replica != 0 || v.flags & crate::report::F_SHADOW != 0 {
                continue;
            }
            let t = v.trip as usize;
            let last = self.last_seen[t];
            let removed = v.flags & F_REMOVED != 0;
            if removed || v.lane == self.dummy {
                let was_on_road = last.lane != u32::MAX && last.lane != self.dummy;
                // An arrival is removed too. Only one that was stuck at the end of its route teleported.
                if was_on_road && (!removed || (new_teleports > 0 && last.wait >= self.threshold)) && self.in_box[last.lane as usize] {
                    let collision = if new_collisions == 0 {
                        false
                    } else if new_teleports == 0 {
                        true
                    } else {
                        last.wait < self.threshold
                    };
                    let flag = if collision { COLLISION } else { TELEPORT };
                    if collision {
                        self.stats.collisions += 1;
                    } else {
                        self.stats.teleports += 1;
                    }
                    self.see_trip(v.trip);
                    self.see_lane(last.lane);
                    self.records.push(Record {
                        trip_flags: v.trip | flag << 24,
                        lane_type: last.lane | v.vtype << 24,
                        prev_wait: NONE_LANE | (last.wait.clamp(0.0, 255.0) as u32) << 24,
                        pos_link: ((last.pos * 256.0).round().clamp(0.0, 16777215.0) as u32) | NO_LINK << 24,
                        acc: 0,
                        speed: 0,
                        lat: 0,
                        pad: 0,
                    });
                    if !why.is_empty() {
                        self.why_records.push(WhyRecord::default());
                    }
                }
                self.last_seen[t].lane = if removed { u32::MAX } else { self.dummy };
                continue;
            }
            self.last_seen[t] = Last { lane: v.lane, pos: v.pos, wait: v.wait };
            running += 1;
            speed_sum += v.speed as f64;
            if !self.in_box[v.lane as usize] {
                continue;
            }
            self.see_trip(v.trip);
            self.see_lane(v.lane);
            if v.prev_lane != u32::MAX {
                self.see_lane(v.prev_lane);
            }
            let mut flags = 0;
            if v.flags & F_LANE_CHANGED != 0 {
                flags |= LANE_CHANGED;
            }
            if v.flags & F_WILL_PASS != 0 {
                flags |= WILL_PASS;
            }
            if v.flags & F_HAVE_TO_WAIT != 0 {
                flags |= HAVE_TO_WAIT;
            }
            if v.flags & F_ON_JUNCTION != 0 {
                flags |= ON_JUNCTION;
            }
            // Report 18: 60% signal before moving over, 33% after they start, 7% never.
            let w = self.lane_width[v.lane as usize];
            let dir = v.phys >> 30;
            let lat = if dir == 0 { v.lc_edge } else { cars_core::physics::lateral_offset(v.phys, w, self.vtype_lat[v.vtype as usize]) * (1.0 - v.lc_edge.abs() / w) };
            let style = (v.trip.wrapping_mul(2654435761) >> 8) as f32 / 16777216.0;
            let human = self.vtype_lat[v.vtype as usize] <= 0.0;
            let moving = dir != 0 || v.lc_edge.abs() > 0.1;
            let signals = !human || style < 0.6 || (style < 0.93 && moving);
            if signals && (v.lc_own & 1 != 0 || (human && dir != 0 && lat < 0.0)) {
                flags |= WANT_LEFT;
            }
            if signals && (v.lc_own & 2 != 0 || (human && dir != 0 && lat > 0.0)) {
                flags |= WANT_RIGHT;
            }
            let prev = if v.prev_lane == u32::MAX { NONE_LANE } else { v.prev_lane };
            self.records.push(Record {
                trip_flags: v.trip | flags << 24,
                lane_type: v.lane | v.vtype << 24,
                prev_wait: prev | (v.wait.clamp(0.0, 255.0) as u32) << 24,
                pos_link: ((v.pos * 256.0).round().clamp(0.0, 16777215.0) as u32) | self.next_link(v) << 24,
                acc: (v.acc * 256.0).round().clamp(-32768.0, 32767.0) as i16,
                speed: (v.speed * 512.0).round().clamp(0.0, 65535.0) as u16,
                lat: (lat * 256.0).round().clamp(-32768.0, 32767.0) as i16,
                pad: 0,
            });
            if !why.is_empty() {
                let index = (std::ptr::from_ref(v).addr() - vehicles.as_ptr().addr()) / size_of::<GpuVeh>();
                self.why_records.push(WhyRecord::from_words(&why[index * words..(index + 1) * words], c.step).unwrap_or_default());
            }
        }
        let phases: Vec<u16> = self.tls_scope.iter().map(|&i| tls[i as usize].phase as u16).collect();
        let head = FrameHead {
            magic: FRAME_MAGIC,
            step: c.step,
            records: self.records.len() as u32,
            names_bytes: self.names.len() as u32,
            teleports: c.teleports,
            collisions: c.collisions,
            running,
            mean_speed: (speed_sum / running.max(1) as f64) as f32,
        };
        let phase_bytes = (phases.len() * 2).next_multiple_of(4);
        let mut phase_data = vec![0u8; phase_bytes];
        phase_data[..phases.len() * 2].copy_from_slice(bytemuck::cast_slice(&phases));
        self.file.write_all(bytemuck::bytes_of(&head)).expect("trace write");
        self.file.write_all(&self.names).expect("trace write");
        self.file.write_all(&phase_data).expect("trace write");
        self.file.write_all(bytemuck::cast_slice(&self.records)).expect("trace write");
        if c.has_why && self.why_file.is_none() {
            self.why_file = Some(why_head(&self.why_path).expect("why write"));
        }
        if let Some(w) = self.why_file.as_mut() {
            w.write_all(b"WHYF").expect("why write");
            w.write_all(&c.step.to_le_bytes()).expect("why write");
            w.write_all(&(self.why_records.len() as u32).to_le_bytes()).expect("why write");
            w.write_all(&0u32.to_le_bytes()).expect("why write");
            w.write_all(bytemuck::cast_slice(&self.why_records)).expect("why write");
        }
        self.stats.records += self.records.len() as u64;
        self.stats.bytes += (size_of::<FrameHead>() + self.names.len() + phase_bytes + self.records.len() * size_of::<Record>()) as u64;
    }
}

/// Where each frame of a trace is. Records come from disk only when a frame is asked for.
pub struct FrameIndex {
    pub step: u32,
    pub records: u32,
    pub teleports: u32,
    pub collisions: u32,
    pub running: u32,
    pub mean_speed: f32,
    phases_at: u64,
}

pub struct Trace {
    file: File,
    pub header: Header,
    pub frames: Vec<FrameIndex>,
    pub trip_ids: HashMap<String, u32>,
    pub max_records: u32,
}

impl Trace {
    /// A run that was cut short still reads, up to its last whole frame.
    pub fn open(path: &Path) -> Result<Self, String> {
        let fail = |e: std::io::Error| format!("{}: {e}", path.display());
        let mut file = File::open(path).map_err(fail)?;
        let length = file.metadata().map_err(fail)?.len();
        let mut start = [0u8; 12];
        file.read_exact(&mut start).map_err(fail)?;
        if &start[..8] != MAGIC {
            return Err(format!("{}: not a cars trace", path.display()));
        }
        let json_bytes = u32::from_le_bytes([start[8], start[9], start[10], start[11]]) as usize;
        let mut json = vec![0u8; json_bytes];
        file.read_exact(&mut json).map_err(fail)?;
        let header: Header = serde_json::from_slice(&json).map_err(|e| format!("{}: {e}", path.display()))?;
        let phase_bytes = (header.tls.len() as u64 * 2).next_multiple_of(4);
        let mut at = 12 + json_bytes as u64;
        let mut frames = Vec::new();
        let mut trip_ids = HashMap::new();
        let mut max_records = 0;
        let mut names = Vec::new();
        while at + size_of::<FrameHead>() as u64 <= length {
            let mut head = FrameHead::zeroed();
            file.read_exact_at(bytemuck::bytes_of_mut(&mut head), at).map_err(fail)?;
            if head.magic != FRAME_MAGIC {
                return Err(format!("{}: damaged frame at byte {at}", path.display()));
            }
            let names_at = at + size_of::<FrameHead>() as u64;
            let phases_at = names_at + head.names_bytes as u64;
            let next = phases_at + phase_bytes + head.records as u64 * size_of::<Record>() as u64;
            if next > length {
                break;
            }
            names.resize(head.names_bytes as usize, 0);
            file.read_exact_at(&mut names, names_at).map_err(fail)?;
            let mut p = 0;
            while p + 8 <= names.len() {
                let id = u32::from_le_bytes(names[p..p + 4].try_into().expect("4 bytes"));
                let len = u32::from_le_bytes(names[p + 4..p + 8].try_into().expect("4 bytes")) as usize;
                if id & NAME_LANE == 0 {
                    trip_ids.insert(String::from_utf8_lossy(&names[p + 8..p + 8 + len]).into_owned(), id);
                }
                p = (p + 8 + len).next_multiple_of(4);
            }
            max_records = max_records.max(head.records);
            frames.push(FrameIndex {
                step: head.step,
                records: head.records,
                teleports: head.teleports,
                collisions: head.collisions,
                running: head.running,
                mean_speed: head.mean_speed,
                phases_at,
            });
            at = next;
        }
        Ok(Self { file, header, frames, trip_ids, max_records })
    }

    pub fn time_of(&self, step: u32) -> f32 {
        (self.header.sim_begin + (step as f64 - 1.0) * self.header.dt as f64) as f32
    }

    pub fn read(&self, frame: usize, phases: &mut Vec<u16>, records: &mut Vec<Record>) -> Result<(), String> {
        let f = &self.frames[frame];
        phases.resize(self.header.tls.len(), 0);
        records.resize(f.records as usize, Record::default());
        let phase_bytes = (phases.len() as u64 * 2).next_multiple_of(4);
        let fail = |e: std::io::Error| format!("trace: {e}");
        self.file.read_exact_at(bytemuck::cast_slice_mut(&mut phases[..]), f.phases_at).map_err(fail)?;
        self.file.read_exact_at(bytemuck::cast_slice_mut(&mut records[..]), f.phases_at + phase_bytes).map_err(fail)?;
        Ok(())
    }
}
