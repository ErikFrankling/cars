//! A running scenario: stepping it against the clock, and what is known about it right now.
use crate::camera::Flyer;
use crate::loader::Loaded;
use crate::registry::Scenario;
use crate::settings::Settings;
use cars_core::{
    Gpu,
    closeup::Approach,
    coord,
    net::{JunctionRow, Net},
    overlay::{Overlay, Snapshot},
    render::{self, CloseMesh, FrameStats, Renderer},
    sim::Sim,
    world::{GpuTlsState, GpuVeh, World},
};
use std::sync::Arc;
use std::sync::mpsc::{Receiver, Sender, channel};
use std::time::Instant;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Pace {
    Paused,
    /// Simulated seconds per real second.
    Multiple(f32),
    AsFast,
}

/// One live chart: time and value, halved in resolution whenever it fills up.
#[derive(Default, Clone)]
pub struct Series {
    pub t: Vec<f32>,
    pub v: Vec<f32>,
}
const SERIES_MAX: usize = 1200;

#[derive(Default)]
pub struct Numbers {
    pub stats: FrameStats,
    pub inserted: u32,
    pub arrived: u32,
    pub teleports: u32,
    pub collisions: u32,
    pub overflow: u32,
    pub lane_changes: u32,
    pub running: Series,
    pub speed: Series,
    pub arrivals: Series,
    pub stuck: Series,
    pub teleports_s: Series,
    pub collisions_s: Series,
    pub every: f32,
    last_t: f32,
    last_arrived: u32,
}

impl Numbers {
    fn push(&mut self, t: f32) {
        if self.every == 0.0 {
            self.every = 2.0;
        }
        if !self.running.t.is_empty() && t - self.last_t < self.every {
            return;
        }
        let dt = (t - self.last_t).max(0.001);
        let rate = self.arrived.saturating_sub(self.last_arrived) as f32 / dt * 60.0;
        let first = self.running.t.is_empty();
        self.last_t = t;
        self.last_arrived = self.arrived;
        let s = self.stats;
        for (series, value) in [
            (&mut self.running, s.vehicles as f32),
            (&mut self.speed, s.mean_speed * 3.6),
            (&mut self.arrivals, if first { 0.0 } else { rate }),
            (&mut self.stuck, s.stuck as f32),
            (&mut self.teleports_s, self.teleports as f32),
            (&mut self.collisions_s, self.collisions as f32),
        ] {
            series.t.push(t);
            series.v.push(value);
        }
        if self.running.t.len() >= SERIES_MAX {
            for series in [&mut self.running, &mut self.speed, &mut self.arrivals, &mut self.stuck, &mut self.teleports_s, &mut self.collisions_s] {
                let keep = |x: &Vec<f32>| x.iter().step_by(2).copied().collect::<Vec<f32>>();
                series.t = keep(&series.t);
                series.v = keep(&series.v);
            }
            self.every *= 2.0;
        }
    }
}

/// What was clicked.
#[derive(Clone, Debug, PartialEq)]
pub enum Selection {
    None,
    Car(u32),
    Junction(u32),
}

#[derive(Clone, Default)]
pub struct CarInfo {
    pub on_road: bool,
    pub veh: GpuVeh,
    pub leader: Option<(u32, f32, f32)>,
    pub seen: bool,
}

#[derive(Clone, Default)]
pub struct JunctionInfo {
    /// Per signal controlling this junction: id, current phase, its colours, seconds to the next switch.
    pub signals: Vec<(String, u32, String, f32)>,
    /// Cars with a firm slot, waiting on advice, in the box, or with a lost grant.
    pub firm: u32,
    pub advised: u32,
    pub in_box: u32,
    pub lost: u32,
    pub phase: Option<u32>,
}

struct MeshWorker {
    ask: Sender<[f32; 4]>,
    answer: Receiver<CloseMesh>,
    busy: bool,
}

pub struct Session {
    pub scenario: Scenario,
    pub settings: Settings,
    pub net: Arc<Net>,
    pub world: World,
    pub sim: Sim,
    pub renderer: Renderer,
    pub junctions: Vec<JunctionRow>,
    pub trip_names: Vec<String>,
    pub vtype_names: Vec<String>,
    pub legend: Vec<(u32, String)>,
    pub widths: Vec<f32>,
    pub load_seconds: f64,
    pub flyer: Flyer,
    pub pace: Pace,
    /// Run flat out to this time, then go back to `pace`.
    pub jump: Option<f32>,
    pub selection: Selection,
    pub following: bool,
    pub car: CarInfo,
    pub junction: JunctionInfo,
    pub numbers: Numbers,
    pub snapshot: Snapshot,
    pub overlay: Overlay,
    pub ended: bool,
    /// Seconds since begin that the picture has reached, continuous between steps.
    rel: f64,
    dt: f64,
    end_step: u64,
    blend: f32,
    pub steps_per_second: f32,
    pub multiple: f32,
    pub vehicle_updates: f32,
    rate_steps: u64,
    rate_at: Instant,
    rate_vehicle_steps: f64,
    last_sample: Instant,
    last_inspect: Instant,
    last_leader: Instant,
    snapshot_ready: Instant,
    pub overlay_cost_ms: f32,
    mesh: MeshWorker,
    began: Instant,
    pub flyer_untouched: bool,
    pub fitted_for: (u32, u32),
}

impl Session {
    pub fn new(l: Loaded, flyer: Flyer, fresh_camera: bool) -> Self {
        let (ask, jobs) = channel::<[f32; 4]>();
        let (done, answer) = channel();
        let dt = l.settings.dt as f64;
        let mut l = l;
        l.sim.target_submit_ms = 8.0;
        let end_step = ((l.scenario.end - l.scenario.begin) as f64 / dt).ceil() as u64;
        let mut overlay = Overlay::default();
        overlay.keep_log = true;
        overlay.max_shown = Some(700);
        let now = Instant::now();
        Self {
            pace: Pace::Multiple(l.scenario.speed),
            scenario: l.scenario,
            settings: l.settings,
            net: l.net,
            world: l.world,
            sim: l.sim,
            renderer: l.renderer,
            junctions: l.junctions,
            trip_names: l.trip_names,
            vtype_names: l.vtype_names,
            legend: l.legend,
            widths: l.widths,
            load_seconds: l.seconds,
            flyer,
            jump: None,
            selection: Selection::None,
            following: false,
            car: CarInfo::default(),
            junction: JunctionInfo::default(),
            numbers: Numbers::default(),
            snapshot: Snapshot::new(),
            overlay,
            ended: false,
            rel: 0.0,
            dt,
            end_step,
            blend: 1.0,
            steps_per_second: 0.0,
            multiple: 0.0,
            vehicle_updates: 0.0,
            rate_steps: 0,
            rate_at: now,
            rate_vehicle_steps: 0.0,
            last_sample: now - std::time::Duration::from_secs(10),
            last_inspect: now - std::time::Duration::from_secs(10),
            last_leader: now - std::time::Duration::from_secs(10),
            snapshot_ready: now,
            overlay_cost_ms: 0.0,
            mesh: MeshWorker { ask, answer, busy: false },
            began: now,
            flyer_untouched: fresh_camera,
            fitted_for: (0, 0),
        }
        .with_mesh_worker(jobs, done)
    }

    fn with_mesh_worker(self, jobs: Receiver<[f32; 4]>, done: Sender<CloseMesh>) -> Self {
        // Runs until the session is dropped, which closes its channel.
        let net = self.net.clone();
        let approaches: Vec<Approach> = self.renderer.approaches();
        let gpu = crate::GPU.get().cloned();
        let _ = std::thread::Builder::new().name("close mesh".into()).spawn(move || {
            let Some(gpu) = gpu else { return };
            while let Ok(mut region) = jobs.recv() {
                while let Ok(newer) = jobs.try_recv() {
                    region = newer;
                }
                if done.send(render::build_close_mesh(&gpu, &net, &approaches, region)).is_err() {
                    break;
                }
            }
        });
        self
    }

    /// Real seconds since this run started, for pacing a clip.
    pub fn started_clock(&self) -> f64 {
        self.began.elapsed().as_secs_f64()
    }

    pub fn clock(&self) -> f32 {
        self.scenario.begin + ((self.sim.step as f64 - 2.0 + self.blend as f64) * self.dt).max(0.0) as f32
    }

    pub fn step_once(&mut self, gpu: &Gpu) {
        if self.sim.step < self.end_step {
            self.sim.run(gpu, 1);
            self.blend = 1.0;
            self.rel = (self.sim.step as f64 - 1.0) * self.dt;
        }
    }

    /// Move simulated time on, spending at most `budget_ms` of this frame on it.
    pub fn advance(&mut self, gpu: &Gpu, wall: f32, budget_ms: f64) {
        let full_speed = self.jump.is_some() || self.pace == Pace::AsFast;
        let want = match self.pace {
            _ if full_speed => f64::INFINITY,
            Pace::Paused => self.rel,
            Pace::Multiple(x) => self.rel + wall as f64 * x as f64,
            Pace::AsFast => f64::INFINITY,
        };
        if self.pace == Pace::Paused && self.jump.is_none() {
            self.update_rates();
            return;
        }
        // As record.rs does: the state after step k is labelled (k-1)*dt, and pictures follow it.
        let step_for = |rel: f64, dt: f64| (rel / dt).ceil().max(0.0) as u64 + 1;
        let target = if want.is_finite() { step_for(want, self.dt).min(self.end_step) } else { self.end_step };
        let t0 = Instant::now();
        let start = self.sim.step;
        while self.sim.step < target {
            let n = (self.sim.steps_per_submit as u64).min(target - self.sim.step);
            self.sim.run(gpu, n);
            if t0.elapsed().as_secs_f64() * 1000.0 >= budget_ms {
                break;
            }
            if let Some(j) = self.jump
                && self.clock() >= j
            {
                break;
            }
        }
        self.rate_vehicle_steps += (self.sim.step - start) as f64 * self.numbers.stats.vehicles as f64;
        if want.is_finite() && self.sim.step >= target {
            self.rel = want.min(self.end_step as f64 * self.dt);
            let k = step_for(self.rel, self.dt);
            self.blend = ((self.rel - (k as f64 - 2.0) * self.dt) / self.dt).clamp(0.0, 1.0) as f32;
        } else {
            // Behind the clock: show what there is, and do not build up a debt.
            self.rel = (self.sim.step as f64 - 1.0).max(0.0) * self.dt;
            self.blend = 1.0;
        }
        if let Some(j) = self.jump
            && self.clock() >= j
        {
            self.jump = None;
            self.rel = (self.sim.step as f64 - 1.0).max(0.0) * self.dt;
        }
        if self.sim.step >= self.end_step && !self.ended {
            self.ended = true;
            self.pace = Pace::Paused;
            self.jump = None;
        }
        self.update_rates();
    }

    fn update_rates(&mut self) {
        let span = self.rate_at.elapsed().as_secs_f32();
        if span < 0.5 {
            return;
        }
        let steps = self.sim.step - self.rate_steps;
        self.steps_per_second = steps as f32 / span;
        self.multiple = steps as f32 * self.dt as f32 / span;
        self.vehicle_updates = self.rate_vehicle_steps as f32 / span;
        self.rate_steps = self.sim.step;
        self.rate_vehicle_steps = 0.0;
        self.rate_at = Instant::now();
    }

    pub fn prepare(&mut self, gpu: &Gpu, mode: u32, flags: u32) {
        let selected = match self.selection {
            Selection::Car(t) => Some(t),
            _ => None,
        };
        let blend = self.blend;
        let (renderer, sim) = (&mut self.renderer, &self.sim);
        renderer.prepare_live(gpu, sim, blend, mode, flags, selected);
    }

    /// Slow-moving numbers, a few times a second, so reading them costs the simulation almost nothing.
    pub fn sample(&mut self, gpu: &Gpu) {
        let tracking = matches!(self.selection, Selection::Car(_));
        let due = self.last_sample.elapsed().as_secs_f32() >= 0.25;
        if due || tracking {
            self.numbers.stats = self.renderer.stats(gpu, &self.sim);
        }
        if !due {
            return;
        }
        self.last_sample = Instant::now();
        let c = self.sim.counters(gpu);
        self.numbers.arrived = c[2];
        self.numbers.inserted = c[3];
        self.numbers.teleports = c[4];
        self.numbers.overflow = c[5];
        self.numbers.lane_changes = c[6];
        self.numbers.collisions = c[7];
        if let Some(cj) = &self.sim.coord {
            let seen: Vec<u32> = self.sim.read(gpu, &cj.events, 1);
            self.numbers.collisions += seen[0];
        }
        let t = self.clock();
        self.numbers.push(t);
    }

    /// Details of what is selected.
    pub fn inspect(&mut self, gpu: &Gpu) {
        if self.last_inspect.elapsed().as_secs_f32() < 0.2 {
            return;
        }
        self.last_inspect = Instant::now();
        match self.selection.clone() {
            Selection::Car(trip) => {
                let stats = self.numbers.stats;
                self.car.on_road = stats.selected_index.is_some();
                if self.car.on_road {
                    self.car.seen = true;
                    self.car.veh = self.renderer.selected_vehicle(gpu, &self.sim);
                }
                // Finding the leader copies every vehicle, so a big city does it less often.
                let vehicles = self.numbers.stats.vehicles;
                let every = if vehicles > 20_000 { 1.5 } else { 0.25 };
                if self.car.on_road && self.last_leader.elapsed().as_secs_f32() >= every {
                    self.last_leader = Instant::now();
                    self.car.leader = self.find_leader(gpu, trip);
                }
            }
            Selection::Junction(j) => self.junction = self.read_junction(gpu, j),
            Selection::None => {}
        }
    }

    fn find_leader(&self, gpu: &Gpu, trip: u32) -> Option<(u32, f32, f32)> {
        let vs = self.sim.vehicles(gpu);
        let i = vs.iter().position(|v| v.trip == trip && v.flags & 1 == 0)?;
        let me = vs[i];
        let items = read_range::<[u32; 10]>(gpu, &self.sim.buffers.items, i as u64 * 8 * 40, 8);
        let mut lane = me.lane;
        let (mut base, mut after) = (-me.pos, me.pos);
        for j in 0..8 {
            let found = vs.iter().filter(|o| o.lane == lane && o.flags & 1 == 0 && o.replica == 0 && o.trip != trip && o.pos > after).min_by(|a, b| a.pos.total_cmp(&b.pos));
            if let Some(o) = found {
                let gap = base + o.pos - self.world.vtypes[o.vtype as usize].length;
                return Some((o.trip, gap, o.speed));
            }
            base += self.net.lanes[lane as usize].length;
            if base > 200.0 || j >= me.n_items as usize {
                return None;
            }
            let link = items[j][0];
            if link == u32::MAX {
                return None;
            }
            lane = self.world.links.get(link as usize)?.next_lane;
            after = -1.0;
        }
        None
    }

    fn read_junction(&self, gpu: &Gpu, index: u32) -> JunctionInfo {
        let mut info = JunctionInfo::default();
        let Some(j) = self.net.junctions.get(index as usize) else { return info };
        let incoming: Vec<u32> = self.net.edges.iter().enumerate().filter(|(_, e)| e.to == j.id).flat_map(|(_, e)| e.first_lane..e.first_lane + e.lane_count).collect();
        let mut tls: Vec<u32> = incoming
            .iter()
            .filter_map(|&lane| self.world.lanes.get(lane as usize))
            .flat_map(|l| self.world.links[l.links_start as usize..(l.links_start + l.links_count) as usize].iter())
            .filter(|l| l.tl != u32::MAX)
            .map(|l| l.tl)
            .collect();
        tls.sort_unstable();
        tls.dedup();
        if !tls.is_empty() {
            let states: Vec<GpuTlsState> = self.sim.read(gpu, &self.sim.buffers.tls, self.world.tls.len() as u64);
            let step = self.sim.step as u32;
            for tl in tls {
                let Some(t) = states.get(tl as usize) else { continue };
                let Some(phase) = self.world.phases.get((t.first_phase + t.phase) as usize) else { continue };
                let start = phase.state_start as usize;
                let n = (t.link_count as usize).min(self.world.states.len().saturating_sub(start));
                let colours: String = self.world.states[start..start + n].iter().map(|&c| c as u8 as char).collect();
                let name = self.net.tls.get(tl as usize).map_or(tl.to_string(), |x| x.id.clone());
                info.signals.push((name, t.phase, colours, t.next_switch.saturating_sub(step) as f32 * self.dt as f32));
            }
        }
        if let Some(cw) = &self.world.coord
            && let Some(ji) = cw.ids.iter().position(|x| *x == j.id)
        {
            let vs = self.sim.vehicles(gpu);
            for v in vs.iter().filter(|v| v.flags & 1 == 0 && v.replica == 0) {
                let Some(m) = cw.links.get(v.cj_link as usize) else { continue };
                if m.junction as usize != ji {
                    continue;
                }
                match v.cj_state & coord::CJ_STATE_MASK {
                    coord::CJ_FIRM => info.firm += 1,
                    coord::CJ_ADVISED => info.advised += 1,
                    coord::CJ_BOX => info.in_box += 1,
                    coord::CJ_PENDING => info.lost += 1,
                    _ => {}
                }
            }
            if let Some(c) = &self.sim.coord {
                let js: Vec<coord::GpuCjJunction> = self.sim.read(gpu, &c.junctions, cw.junctions.len() as u64);
                info.phase = js.get(ji).filter(|x| x.mode == coord::MODE_SIGNAL).map(|x| x.phase);
            }
        }
        info
    }

    /// The car nearest this point in net metres, within `reach`. Copies all vehicles, so only on a click.
    pub fn car_at(&self, gpu: &Gpu, p: [f32; 2], reach: f32) -> Option<u32> {
        let vs = self.sim.vehicles(gpu);
        let poses = self.renderer.instances(gpu, &self.sim, vs.len() as u32);
        let mut best = None;
        let mut dist = reach;
        for (i, pose) in poses.iter().enumerate() {
            if pose.alive != 1.0 || vs.get(i).is_none_or(|v| v.flags & 1 != 0 || v.replica != 0) {
                continue;
            }
            let d = (pose.xy[0] - p[0]).hypot(pose.xy[1] - p[1]);
            if d < dist {
                dist = d;
                best = Some(vs[i].trip);
            }
        }
        best
    }

    pub fn junction_at(&self, p: [f32; 2], reach: f32) -> Option<u32> {
        let mut best = None;
        let mut dist = reach;
        for (i, j) in self.net.junctions.iter().enumerate() {
            if j.jtype == "internal" {
                continue;
            }
            let inside = j.shape.len() >= 3 && point_in(&j.shape, p);
            let d = if inside { 0.0 } else { (j.x - p[0]).hypot(j.y - p[1]) };
            if d < dist {
                dist = d;
                best = Some(i as u32);
                if inside {
                    break;
                }
            }
        }
        best
    }

    /// Bring overlay data up to date when it is worth it. Over a big map this is a large copy, so it
    /// takes at most a fifth of the time.
    pub fn update_snapshot(&mut self, gpu: &Gpu) {
        if Instant::now() < self.snapshot_ready {
            return;
        }
        let t = Instant::now();
        let (snapshot, sim, renderer) = (&mut self.snapshot, &self.sim, &self.renderer);
        snapshot.update(gpu, sim, renderer);
        let cost = t.elapsed();
        self.overlay_cost_ms = cost.as_secs_f32() * 1000.0;
        self.snapshot_ready = Instant::now() + cost * 4;
    }

    /// Ask for the close-up road the camera needs and take any that has finished.
    pub fn tend_mesh(&mut self) {
        while let Ok(m) = self.mesh.answer.try_recv() {
            self.renderer.add_close_mesh(m);
            self.mesh.busy = false;
        }
        if !self.mesh.busy
            && let Some(region) = self.renderer.close_mesh_wanted(self.flyer.camera())
            && self.mesh.ask.send(region).is_ok()
        {
            self.mesh.busy = true;
        }
    }

    pub fn trip_route(&self, trip: u32) -> &[u32] {
        let Some(t) = self.world.trips.get(trip as usize) else { return &[] };
        self.world.routes.get(t.route_start as usize..t.route_end as usize).unwrap_or(&[])
    }

    pub fn memory_note(&self) -> String {
        format!("{:.1} GB of simulation buffers", self.sim.buffers.total_bytes as f64 / 1e9)
    }
}

fn point_in(shape: &[[f32; 2]], p: [f32; 2]) -> bool {
    let mut inside = false;
    let mut j = shape.len() - 1;
    for i in 0..shape.len() {
        let (a, b) = (shape[i], shape[j]);
        if (a[1] > p[1]) != (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0] {
            inside = !inside;
        }
        j = i;
    }
    inside
}

fn read_range<T: bytemuck::Pod>(gpu: &Gpu, buffer: &wgpu::Buffer, offset: u64, count: u64) -> Vec<T> {
    let size = (count * std::mem::size_of::<T>() as u64).min(buffer.size().saturating_sub(offset));
    if size == 0 {
        return Vec::new();
    }
    let staging = gpu.device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("read range"),
        size,
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    let mut e = gpu.device.create_command_encoder(&Default::default());
    e.copy_buffer_to_buffer(buffer, offset, &staging, 0, size);
    gpu.queue.submit([e.finish()]);
    let slice = staging.slice(..);
    slice.map_async(wgpu::MapMode::Read, |_| {});
    gpu.wait();
    let data = slice.get_mapped_range().expect("mapped");
    let out = bytemuck::pod_collect_to_vec(&data[..]);
    drop(data);
    staging.unmap();
    out
}

pub fn clock_text(t: f32) -> String {
    let t = t.max(0.0) as u32;
    format!("{:02}:{:02}:{:02}", t / 3600 % 24, t / 60 % 60, t % 60)
}

/// "08:00", "8:30:15" or plain seconds into simulated seconds.
pub fn parse_clock(s: &str) -> Option<f32> {
    let parts: Vec<&str> = s.trim().split(':').collect();
    let num = |x: &str| x.trim().parse::<f32>().ok().filter(|v| v.is_finite() && *v >= 0.0);
    match parts.len() {
        1 => num(parts[0]),
        2 => Some(num(parts[0])? * 3600.0 + num(parts[1])? * 60.0),
        3 => Some(num(parts[0])? * 3600.0 + num(parts[1])? * 60.0 + num(parts[2])?),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clock_round_trips() {
        assert_eq!(clock_text(8.0 * 3600.0 + 61.0), "08:01:01");
        assert_eq!(parse_clock("08:00"), Some(28800.0));
        assert_eq!(parse_clock(" 8:30:15 "), Some(30615.0));
        assert_eq!(parse_clock("900"), Some(900.0));
        assert_eq!(parse_clock("soon"), None);
        assert_eq!(parse_clock("-3"), None);
    }

    #[test]
    fn point_in_polygon() {
        let square = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]];
        assert!(point_in(&square, [1.0, 1.0]));
        assert!(!point_in(&square, [3.0, 1.0]));
    }

    #[test]
    fn charts_stay_bounded_and_keep_their_span() {
        let mut n = Numbers::default();
        for i in 0..20_000 {
            n.arrived = i;
            n.push(i as f32 * 2.0);
        }
        assert!(n.running.t.len() <= SERIES_MAX);
        assert!(n.every > 2.0);
        assert_eq!(n.running.t[0], 0.0);
        assert!(*n.running.t.last().unwrap() > 39_000.0);
    }
}
