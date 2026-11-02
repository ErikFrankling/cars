//! Draw a trace: no simulation, no simulation buffers. Poses are worked out here, the way the
//! `prepare` kernel does, and uploaded to the vertex stage each frame.
use crate::overlay::Snapshot;
use crate::record::{self, Common, Source};
use crate::trace::{self, COLLISION, NO_LINK, NONE_LANE, Record, TELEPORT, Trace};
use bytemuck::Zeroable;
use cars_core::{
    Gpu, GpuOptions,
    demand::Demand,
    net::Net,
    render::{self, Instance, Renderer, Tables},
    world::{GpuVType, GpuVeh, SimConfig, World},
};
use clap::Parser;
use std::{collections::HashSet, path::PathBuf};

const CHANGE_SECONDS: f32 = 3.0;
const NONE: u32 = u32::MAX;
const F_ON_JUNCTION: u32 = 128;
const F_WILL_PASS: u32 = 512;
const F_HAVE_TO_WAIT: u32 = 2048;

#[derive(Parser)]
pub struct Args {
    #[command(flatten)]
    common: Common,
    /// File from `cars run --trace`.
    #[arg(long)]
    trace: PathBuf,
}

type V2 = [f32; 2];
fn add(a: V2, b: V2) -> V2 {
    [a[0] + b[0], a[1] + b[1]]
}
fn sub(a: V2, b: V2) -> V2 {
    [a[0] - b[0], a[1] - b[1]]
}
fn scale(a: V2, k: f32) -> V2 {
    [a[0] * k, a[1] * k]
}
fn dot(a: V2, b: V2) -> f32 {
    a[0] * b[0] + a[1] * b[1]
}
fn length(a: V2) -> f32 {
    a[0].hypot(a[1])
}
fn perp(a: V2) -> V2 {
    [-a[1], a[0]]
}
fn mix(a: V2, b: V2, t: f32) -> V2 {
    [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
}

struct Geometry<'a> {
    tables: &'a Tables,
    world: &'a World,
}
impl Geometry<'_> {
    fn distance(&self, lane: usize, pos: f32) -> f32 {
        let total = f32::from_bits(self.tables.ranges[lane][2]);
        (pos / self.world.lanes[lane].length.max(0.001)).clamp(0.0, 1.0) * total
    }
    fn seg(&self, lane: usize, d: f32) -> usize {
        let r = self.tables.ranges[lane];
        let (mut lo, mut hi) = (0u32, r[1] - 1);
        while hi - lo > 1 {
            let m = (lo + hi) / 2;
            if self.tables.points[(r[0] + m) as usize][2] < d {
                lo = m;
            } else {
                hi = m;
            }
        }
        (r[0] + lo) as usize
    }
    fn xy(&self, lane: usize, pos: f32) -> V2 {
        let d = self.distance(lane, pos);
        let k = self.seg(lane, d);
        let (a, b) = (self.tables.points[k], self.tables.points[k + 1]);
        mix([a[0], a[1]], [b[0], b[1]], ((d - a[2]) / (b[2] - a[2]).max(0.001)).clamp(0.0, 1.0))
    }
    fn dir(&self, lane: usize, pos: f32) -> V2 {
        let k = self.seg(lane, self.distance(lane, pos));
        let (a, b) = (self.tables.points[k], self.tables.points[k + 1]);
        let d = [b[0] - a[0], b[1] - a[1]];
        scale(d, 1.0 / length(d).max(0.001))
    }
    /// Centre and heading of the body, as a chord from rear to front bumper.
    fn body(&self, r: &Record) -> Option<(V2, V2)> {
        let (lane, pos) = (r.lane() as usize, r.pos());
        let range = self.tables.ranges.get(lane)?;
        if range[1] < 2 || f32::from_bits(range[2]) <= 0.0 {
            return None;
        }
        let body = self.world.vtypes[r.vtype() as usize].length;
        let front = self.xy(lane, pos);
        let mut rear = self.xy(lane, pos - body);
        let prev = r.prev_lane();
        if pos < body && prev != NONE_LANE && prev as usize != lane && self.tables.ranges.get(prev as usize).is_some_and(|p| p[1] >= 2) {
            // A lane change keeps prev_lane, so only follow it when the two lanes actually meet.
            let p = self.tables.ranges[prev as usize];
            let end = self.tables.points[(p[0] + p[1] - 1) as usize];
            let start = self.tables.points[range[0] as usize];
            if length([end[0] - start[0], end[1] - start[1]]) < 2.0 {
                rear = self.xy(prev as usize, self.world.lanes[prev as usize].length + pos - body);
            }
        }
        let mut dir = self.dir(lane, pos);
        let chord = sub(front, rear);
        if length(chord) > 0.2 * body {
            dir = scale(chord, 1.0 / length(chord));
        }
        Some((sub(front, scale(dir, body * 0.5)), dir))
    }
}

#[derive(Clone, Copy)]
struct History {
    prev_xy: V2,
    prev_dir: V2,
    cur_xy: V2,
    cur_dir: V2,
    drawn: V2,
    lat: f32,
    changed: f32,
    time: f32,
    lane: u32,
}

struct TraceSource<'a> {
    trace: &'a Trace,
    world: &'a World,
    tables: &'a Tables,
    widths: Vec<f32>,
    interpolate: bool,
    next: usize,
    cur: Option<usize>,
    prev_step: u32,
    step: u32,
    records: Vec<Record>,
    scratch: Vec<Record>,
    phases: Vec<u16>,
    /// Events of frames passed over since the last snapshot, as a fast video skips frames.
    passed: Vec<Record>,
    passed_count: usize,
    slots: Vec<u32>,
    history: Vec<History>,
    instances: Vec<Instance>,
    signals: Vec<Instance>,
    snapped: Option<u32>,
}

impl TraceSource<'_> {
    fn feed(&mut self, i: usize) -> Result<(), String> {
        let trace = self.trace;
        std::mem::swap(&mut self.records, &mut self.scratch);
        if self.cur.is_some() && self.snapped != Some(self.step) {
            let flagged = self.scratch.iter().filter(|r| r.flags() & (TELEPORT | COLLISION) != 0);
            self.passed.extend(flagged);
        }
        trace.read(i, &mut self.phases, &mut self.records)?;
        let f = &trace.frames[i];
        let stride = trace.header.stride.max(1);
        self.prev_step = if self.cur.is_some() { self.step } else { f.step.saturating_sub(stride) };
        self.step = f.step;
        self.cur = Some(i);
        let dt = trace.header.dt;
        let step_time = f.step as f32 * dt;
        let geometry = Geometry { tables: self.tables, world: self.world };
        for r in &self.records {
            if r.flags() & (TELEPORT | COLLISION) != 0 {
                continue;
            }
            let Some((center, dir)) = geometry.body(r) else {
                continue;
            };
            let t = r.trip() as usize;
            if t >= self.slots.len() {
                self.slots.resize(t + 1, NONE);
            }
            if self.slots[t] == NONE {
                self.slots[t] = self.history.len() as u32;
                self.history.push(History { prev_xy: center, prev_dir: dir, cur_xy: center, cur_dir: dir, drawn: center, lat: 0.0, changed: -1e9, time: step_time, lane: r.lane() });
                continue;
            }
            let h = &mut self.history[self.slots[t] as usize];
            if step_time <= h.time {
                continue;
            }
            let elapsed = step_time - h.time;
            h.prev_xy = h.cur_xy;
            h.prev_dir = h.cur_dir;
            let n = perp(dir);
            let lanes = &self.world.lanes;
            if length(sub(center, h.cur_xy)) > (r.speed() + 10.0) * elapsed * 1.5 + 6.0 {
                h.prev_xy = center;
                h.prev_dir = dir;
                h.lat = 0.0;
            } else if h.lane != r.lane() && lanes[h.lane as usize].edge == lanes[r.lane() as usize].edge {
                let u = ((h.time - h.changed) / CHANGE_SECONDS).clamp(0.0, 1.0);
                let old = add(h.cur_xy, scale(perp(h.cur_dir), h.lat * (1.0 - u * u * (3.0 - 2.0 * u))));
                h.lat = dot(sub(old, center), n);
                h.prev_xy = add(h.cur_xy, scale(n, dot(sub(center, h.cur_xy), n)));
                h.changed = h.time;
            }
            h.cur_xy = center;
            h.cur_dir = dir;
            h.time = step_time;
            h.lane = r.lane();
        }
        Ok(())
    }

    fn pose_all(&mut self, blend: f32, time: f32, mode: u32) {
        let world = self.world;
        self.instances.clear();
        for r in &self.records {
            let slot = self.slots.get(r.trip() as usize).copied().unwrap_or(NONE);
            if slot == NONE || r.flags() & (TELEPORT | COLLISION) != 0 || r.lane() as usize >= self.tables.ranges.len() {
                self.instances.push(Instance::zeroed());
                continue;
            }
            let h = &mut self.history[slot as usize];
            let b = mix(h.prev_xy, h.cur_xy, blend);
            let mut d = mix(h.prev_dir, h.cur_dir, blend);
            d = if length(d) > 0.2 { scale(d, 1.0 / length(d)) } else { h.cur_dir };
            let dn = perp(d);
            let u = ((time - h.changed) / CHANGE_SECONDS).clamp(0.0, 1.0);
            let xy = add(b, scale(dn, h.lat * (1.0 - u * u * (3.0 - 2.0 * u))));
            let speed = r.speed();
            let yaw = (-h.lat * 6.0 * u * (1.0 - u) / CHANGE_SECONDS).atan2(speed.max(2.0)).clamp(-0.35, 0.35);
            let drawn_dir = add(scale(d, yaw.cos()), scale(dn, yaw.sin()));
            h.drawn = xy;
            let lane = &world.lanes[r.lane() as usize];
            let t = &world.vtypes[r.vtype() as usize];
            let ratio = match mode {
                1 => {
                    if t.model >= 2 {
                        0.85
                    } else {
                        0.15
                    }
                }
                2 => 1.0 - (r.wait() / 60.0).clamp(0.0, 1.0),
                _ => (speed / lane.speed.max(0.01)).clamp(0.0, 1.0),
            };
            let mut detail = if r.acc() < -0.5 || speed < 0.1 { 1u32 } else { 0 };
            if r.flags() & trace::WANT_LEFT != 0 {
                detail |= 2;
            }
            if r.flags() & trace::WANT_RIGHT != 0 {
                detail |= 4;
            }
            if u < 1.0 && h.lat > 0.3 {
                detail |= 4;
            }
            if u < 1.0 && h.lat < -0.3 {
                detail |= 2;
            }
            if lane.flags & 1 != 0 {
                detail |= self.tables.ranges[r.lane() as usize][3];
            } else if r.link_offset() != NO_LINK && lane.length - r.pos() < 60.0 {
                detail |= self.tables.links[(lane.links_start + r.link_offset()) as usize][1];
            }
            self.instances.push(Instance {
                xy,
                dir: drawn_dir,
                length: t.length,
                width: self.widths[r.vtype() as usize],
                ratio,
                alive: 1.0,
                detail: detail as f32,
                seed: (r.trip() as f32 * 0.618_034).fract(),
                pad: [0.0; 2],
            });
        }
    }

    fn pose_signals(&mut self) {
        let world = self.world;
        let mut phase = vec![NONE; world.tls.len()];
        for (t, &p) in self.trace.header.tls.iter().zip(&self.phases) {
            phase[t.index as usize] = p as u32;
        }
        self.signals.clear();
        for s in &self.tables.signals {
            let (tl, index) = (s[4] as usize, s[5]);
            // A signal outside the traced box is unknown, and drawn as off.
            let code = if phase[tl] == NONE {
                4.0
            } else {
                let t = &world.tls[tl];
                match world.states[(world.phases[(t.first_phase + phase[tl]) as usize].state_start + index) as usize] {
                    121 | 89 | 117 => 1.0,
                    71 => 2.0,
                    103 => 3.0,
                    111 | 79 => 4.0,
                    _ => 0.0,
                }
            };
            self.signals.push(Instance {
                xy: [f32::from_bits(s[0]), f32::from_bits(s[1])],
                dir: [f32::from_bits(s[2]), f32::from_bits(s[3])],
                length: 1.7,
                width: f32::from_bits(s[6]),
                ratio: code,
                alive: 2.0,
                detail: s[7] as f32,
                seed: 0.0,
                pad: [0.0; 2],
            });
        }
    }

    /// The engine's vehicle as far as a trace knows it. Taken off vehicles go to the dummy lane.
    fn vehicle(&self, r: &Record) -> GpuVeh {
        let mut v = GpuVeh::zeroed();
        let gone = r.flags() & (TELEPORT | COLLISION) != 0;
        v.pos = r.pos();
        v.speed = r.speed();
        v.acc = r.acc();
        v.wait = r.wait();
        v.trip = r.trip();
        v.vtype = r.vtype();
        v.lane = if gone { self.world.params.dummy_lane } else { r.lane() };
        v.prev_lane = if r.prev_lane() == NONE_LANE { NONE } else { r.prev_lane() };
        if r.flags() & trace::WILL_PASS != 0 {
            v.flags |= F_WILL_PASS;
        }
        if r.flags() & trace::HAVE_TO_WAIT != 0 {
            v.flags |= F_HAVE_TO_WAIT;
        }
        if r.flags() & trace::ON_JUNCTION != 0 {
            v.flags |= F_ON_JUNCTION;
        }
        if r.flags() & trace::WANT_LEFT != 0 {
            v.lc_own |= 1;
        }
        if r.flags() & trace::WANT_RIGHT != 0 {
            v.lc_own |= 2;
        }
        v
    }

    fn link_state(&self, link: u32) -> u8 {
        let world = self.world;
        let l = &world.links[link as usize];
        if l.tl == NONE {
            return l.state as u8;
        }
        let Some(k) = self.trace.header.tls.iter().position(|t| t.index == l.tl) else {
            return l.state as u8;
        };
        let t = &world.tls[l.tl as usize];
        world.states[(world.phases[(t.first_phase + self.phases[k] as u32) as usize].state_start + l.tl_index) as usize] as u8
    }

    /// The links ahead, from the one the route asks for and on as long as there is no choice.
    /// Ends where the engine's plan would: at a signal showing red or yellow, or beyond braking
    /// distance once past the next junction.
    fn plan(&self, r: &Record, items: &mut [[u32; 10]]) -> u32 {
        let world = self.world;
        items.fill([NONE; 10]);
        if r.flags() & (TELEPORT | COLLISION) != 0 || r.link_offset() == NO_LINK || r.lane() as usize >= world.lanes.len() {
            return 0;
        }
        let t = &world.vtypes[r.vtype() as usize];
        let speed = r.speed();
        let horizon = speed * world.params.dt + speed * speed / (2.0 * t.decel.max(0.1)) + speed;
        let lane = &world.lanes[r.lane() as usize];
        let mut link = lane.links_start + r.link_offset();
        let mut dist = lane.length - r.pos();
        let mut crossed = 0.0f32;
        let mut n = 0;
        while (n as usize) < items.len() {
            items[n as usize][0] = link;
            items[n as usize][7] = dist.to_bits();
            n += 1;
            if matches!(self.link_state(link), b'r' | b'u' | b'y' | b'Y') || (n == 1 && r.flags() & trace::HAVE_TO_WAIT != 0) {
                break;
            }
            let l = &world.links[link as usize];
            let Some(next) = world.lanes.get(l.next_lane as usize) else {
                break;
            };
            if next.flags & 1 == 0 {
                crossed += next.length;
            }
            if dist > horizon && crossed > t.length * 5.0 {
                break;
            }
            if next.links_count != 1 {
                break;
            }
            dist += next.length;
            link = next.links_start;
        }
        n
    }
}

impl Source for TraceSource<'_> {
    fn warm(&mut self, _g: &Gpu, step: u64) -> Result<(), String> {
        self.next = self.trace.frames.partition_point(|f| (f.step as u64) < step);
        Ok(())
    }

    fn show(&mut self, g: &Gpu, renderer: &mut Renderer, display: f32, k: u64, _blend: f32, mode: u32, _lead: u64) -> Result<(u32, f32, f32), String> {
        let trace = self.trace;
        let before = self.cur;
        while self.next < trace.frames.len() && (self.cur.is_none() || (self.step as u64) < k) {
            self.feed(self.next)?;
            self.next += 1;
        }
        let Some(cur) = self.cur else {
            return Err("trace has no frames".into());
        };
        if before != self.cur {
            self.pose_signals();
        }
        // What happened in the lead-up is not news to the first picture.
        if before.is_none() {
            self.passed.clear();
        }
        let span = self.step - self.prev_step;
        let blend = if self.interpolate && span > 0 {
            let (a, b) = (trace.time_of(self.prev_step), trace.time_of(self.step));
            ((display - a) / (b - a)).clamp(0.0, 1.0)
        } else {
            1.0
        };
        let dt = trace.header.dt;
        let moment = self.prev_step as f32 + blend * span as f32;
        self.pose_all(blend, moment * dt, mode);
        renderer.upload(g, &self.instances, &self.signals, moment * dt, mode);
        let f = &trace.frames[cur];
        Ok((f.running, f.mean_speed, trace.header.sim_begin as f32 + (moment - 1.0) * dt))
    }

    fn snapshot(&mut self, _g: &Gpu, _renderer: &Renderer, snap: &mut Snapshot) {
        if self.snapped != Some(self.step) {
            self.snapped = Some(self.step);
            let f = &self.trace.frames[self.cur.expect("shown before snapshot")];
            snap.teleports = f.teleports;
            snap.collisions = f.collisions;
            // First, so that a vehicle already back on the road flashes where it was before.
            let passed = std::mem::take(&mut self.passed);
            self.passed_count = passed.len();
            let all = || passed.iter().chain(self.records.iter());
            snap.vs = all().map(|r| self.vehicle(r)).collect();
            snap.collided = Some(all().filter(|r| r.flags() & COLLISION != 0).map(|r| r.trip()).collect::<HashSet<u32>>());
            snap.items.clear();
            snap.items.resize(snap.vs.len() * 8, [NONE; 10]);
            for (i, r) in all().enumerate() {
                snap.vs[i].n_items = self.plan(r, &mut snap.items[i * 8..(i + 1) * 8]);
            }
            snap.index();
        }
        snap.poses.clear();
        snap.poses.resize(self.passed_count, Instance::zeroed());
        snap.poses.extend_from_slice(&self.instances);
    }

    fn position(&self, _g: &Gpu, _renderer: &Renderer, trip: u32) -> Option<[f32; 2]> {
        let slot = *self.slots.get(trip as usize)?;
        (slot != NONE).then(|| self.history[slot as usize].drawn)
    }
}

pub fn run(mut r: Args) -> Result<(), Box<dyn std::error::Error>> {
    let trace = Trace::open(&r.trace)?;
    let (Some(first), Some(last)) = (trace.frames.first(), trace.frames.last()) else {
        return Err("trace has no frames".into());
    };
    let dt = trace.header.dt;
    let sim_begin = trace.header.sim_begin as f32;
    let begin = r.common.begin.unwrap_or(trace.time_of(first.step));
    let end = r.common.end.unwrap_or(trace.time_of(last.step).max(begin + dt));
    let job = record::job(&mut r.common, begin, end, dt, None, false)?;
    let a = &r.common;
    let mut net = Net::load(&a.net)?;
    for p in &a.additional {
        net.load_additional(p)?;
    }
    let hash = trace::net_hash(&net);
    if hash != trace.header.net_hash {
        return Err(format!("this trace is from another net: file {} here {hash}. Give the --net and --additional of the run", trace.header.net_hash).into());
    }
    let mut world = World::build(
        &net,
        &Demand::default(),
        &SimConfig { dt, begin_seconds: sim_begin, end_seconds: end, ..Default::default() },
        &[],
    );
    world.vtypes = trace
        .header
        .vtypes
        .iter()
        .map(|t| GpuVType { model: t.model, length: t.length, min_gap: t.min_gap, decel: t.decel, emergency: t.emergency, ..GpuVType::zeroed() })
        .collect();
    world.params.capacity = trace.max_records;
    let widths: Vec<f32> = trace.header.vtypes.iter().map(|t| t.width).collect();
    let tables = render::tables(&world, &net, false);
    let (views, far_roads) = record::make_views(a, &job, &net, |id| {
        let &trip = trace.trip_ids.get(id).ok_or_else(|| format!("trip {id} is not in this trace"))?;
        let geometry = Geometry { tables: &tables, world: &world };
        let (mut phases, mut records) = (Vec::new(), Vec::new());
        for i in 0..trace.frames.len() {
            trace.read(i, &mut phases, &mut records)?;
            if let Some(start) = records.iter().find(|r| r.trip() == trip).and_then(|r| geometry.body(r)) {
                return Ok((trip, start.0));
            }
        }
        Err(format!("trip {id} is not in this trace"))
    })?;
    let gpu = pollster::block_on(Gpu::headless(GpuOptions {
        adapter_name: Some(std::env::var("CARS_ADAPTER").unwrap_or("7900".into())),
        ..Default::default()
    }))?;
    let mut renderer = Renderer::new(&gpu, &world, &net, &widths, a.width, a.height, far_roads);
    world.shapes = Vec::new();
    let interpolate = job.interpolate;
    let mut source = TraceSource {
        trace: &trace,
        world: &world,
        tables: &tables,
        widths,
        interpolate,
        next: 0,
        cur: None,
        prev_step: 0,
        step: 0,
        records: Vec::new(),
        scratch: Vec::new(),
        phases: Vec::new(),
        passed: Vec::new(),
        passed_count: 0,
        slots: Vec::new(),
        history: Vec::new(),
        instances: Vec::new(),
        signals: Vec::new(),
        snapped: None,
    };
    record::render(a, job, dt, sim_begin, &net, &world, &gpu, &mut renderer, views, &mut source)
}
