//! One simulated day on the GPU: drain counters every 300 s, check the ledger, stop on a stall.

use std::time::Instant;

use cars_core::net::Net;
use cars_core::sim::Sim;
use cars_core::topology::Topology;
use cars_core::world::{Replica, SimConfig, World};
use cars_core::{Checks, Gpu, GpuOptions};
use serde::Serialize;

use crate::costs::{BIN_S, DayCounts, NONE, Supply};
use crate::ledger::Ledger;
use crate::population::Population;
use crate::scenario::Scenario;

const F_REMOVED: u32 = 1;
const C_NEW: usize = 0;
const C_ARRIVED: usize = 2;
const C_INSERTED: usize = 3;
const C_COLLISIONS: usize = 7;

pub fn open_gpu(trusted: bool) -> Result<Gpu, String> {
    let checks = if trusted { Checks::Trusted } else { Checks::Safe };
    pollster::block_on(Gpu::headless(GpuOptions { adapter_name: Some(std::env::var("CARS_ADAPTER").unwrap_or("7900".into())), checks }))
}

pub fn sim_config(s: &Scenario, replicas: u32) -> SimConfig {
    SimConfig {
        dt: s.dt,
        begin_seconds: s.begin,
        end_seconds: s.horizon,
        seed: s.seed,
        time_to_teleport: s.time_to_teleport,
        ignore_blocker: s.ignore_blocker.unwrap_or(1e9),
        capacity: s.capacity * replicas,
        sample_seconds: 10.0,
        mu: s.mu,
        ..Default::default()
    }
}

pub fn replicas(seeds: &[u64]) -> Vec<Replica> {
    seeds.iter().map(|&seed| Replica { seed, trip_vtype: Vec::new(), label: format!("seed{seed}") }).collect()
}

/// Everything that lives across iterations of one world.
pub struct Engine {
    pub gpu: Gpu,
    pub topo: Topology,
    pub world: World,
    pub sim: Option<Sim>,
    pub cfg: SimConfig,
    pub seeds: Vec<u64>,
}

impl Engine {
    pub fn new(net: &Net, pop: &mut Population, s: &Scenario, seeds: &[u64]) -> Result<Self, String> {
        let gpu = open_gpu(s.trusted)?;
        let topo = Topology::build(net);
        let cfg = sim_config(s, seeds.len() as u32);
        pop.fill_trips();
        let world = World::build_with(net, &topo, &pop.demand, &cfg, &replicas(seeds));
        let mut e = Self { gpu, topo, world, sim: None, cfg, seeds: seeds.to_vec() };
        e.new_sim()?;
        Ok(e)
    }

    /// Room for 1.3 times these routes, so that assignment rarely outgrows the buffer.
    fn new_sim(&mut self) -> Result<(), String> {
        self.sim = None;
        let real = self.world.routes.len();
        self.world.routes.resize(real * 13 / 10 + 1024, 0);
        self.sim = Some(Sim::new(&self.gpu, &self.world)?);
        self.world.routes.truncate(real);
        Ok(())
    }

    /// New routes, departures or travellers in the same world, ready to run from step 0.
    pub fn load_day(&mut self, net: &Net, pop: &mut Population, seeds: &[u64]) -> Result<(), String> {
        pop.fill_trips();
        self.seeds = seeds.to_vec();
        self.cfg = SimConfig { seed: seeds[0], ..self.cfg.clone() };
        self.world.rewrite_demand(net, &self.topo, &pop.demand, &self.cfg, &replicas(seeds));
        self.world.params.n_trips = self.world.trips.len() as u32;
        self.world.params.n_queues = self.world.queues.len() as u32;
        self.world.params.capacity = self.cfg.capacity.min(self.world.params.n_trips);
        let sim = self.sim.as_mut().ok_or("no sim")?;
        if sim.write_demand(&self.gpu, &self.world) {
            sim.reset(&self.gpu, &self.world);
        } else {
            eprintln!("demand outgrew the buffers: new Sim");
            self.new_sim()?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct TripStats {
    pub requested: u64,
    pub arrived: u64,
    pub unfinished: u64,
    /// Scheduled departure to arrival. Unfinished trips are charged their elapsed time.
    pub mean_travel_s: f64,
    pub p50_travel_s: f64,
    pub p95_travel_s: f64,
    pub mean_insertion_wait_s: f64,
    pub total_generalised_s: f64,
    pub route_km: f64,
}

pub struct DayResult {
    pub counts: DayCounts,
    pub ledgers: Vec<Ledger>,
    pub stats: Vec<TripStats>,
    /// Per traveller, in replica 0: travel time with insertion wait, and whether it arrived.
    pub experienced: Vec<f32>,
    pub finished: Vec<bool>,
    pub stalled_at_s: Option<f32>,
    pub due_at_stall: f64,
    pub end_s: f32,
    pub wall_s: f64,
    pub vehicle_steps: u64,
    pub peak_active: u32,
    pub speed_by_bin: Vec<f32>,
}

/// Hook for en-route rerouting and incidents, called at every bin edge.
pub trait Pause {
    fn at_bin_edge(&mut self, _engine: &mut Engine, _t: f32, _counts: &DayCounts, _bin: usize) {}
}
pub struct NoPause;
impl Pause for NoPause {}

pub fn run_day(engine: &mut Engine, supply: &Supply, pop: &Population, s: &Scenario, pause: &mut dyn Pause) -> DayResult {
    let t0 = Instant::now();
    let k = engine.seeds.len();
    let n_bins = s.n_bins();
    let mut counts = DayCounts::new(supply.n(), n_bins, k as u32);
    let per = engine.world.n_edges_per_replica as usize;
    let begin_bin = (s.begin / BIN_S) as usize;
    let steps_per_bin = (BIN_S / s.dt).round() as u64;
    // Requested per edge and bin, and how many are due at each bin edge.
    let mut due_by_bin = vec![0u64; n_bins + 2];
    for t in &pop.travellers {
        let b = ((t.depart_s / BIN_S) as usize).min(n_bins - 1);
        let e = supply.dense[t.o_edge as usize] as usize;
        let at = e * n_bins + b;
        counts.requested[at] = counts.requested[at].saturating_add(k as u16);
        due_by_bin[b + 1] += 1;
    }
    for b in 0..=n_bins {
        due_by_bin[b + 1] += due_by_bin[b];
    }
    let requested = pop.travellers.len() as u64;
    let mut no_arrival_bins = 0;
    let mut last_arrived = 0u64;
    let mut stalled_at_s = None;
    let mut due_at_stall = 0.0;
    let mut vehicle_steps = 0u64;
    let mut peak_active = 0u32;
    let mut inserted_by_replica = vec![0u64; k];
    let mut teleports_by_replica = vec![0u64; k];
    let mut speed_by_bin = vec![0.0f32; n_bins];
    let mut end_s = s.horizon;
    let mut bin = begin_bin;
    let sim_steps = ((s.horizon - s.begin) / s.dt).ceil() as u64;
    let mut done = 0u64;
    let mut imbalance = 0i64;
    while done < sim_steps && bin < n_bins {
        let run = steps_per_bin.min(sim_steps - done);
        let sim = engine.sim.as_mut().expect("sim");
        let before = sim.globals(&engine.gpu).n_active as u64;
        done += sim.run(&engine.gpu, run);
        let g = sim.globals(&engine.gpu);
        let c = sim.counters(&engine.gpu);
        let acc = sim.take_edge_acc(&engine.gpu);
        let (mut samples, mut dist) = (0u64, 0u64);
        for (id, a) in acc.iter().enumerate() {
            let (r, e) = (id / per, id % per);
            inserted_by_replica[r] += a[5] as u64;
            teleports_by_replica[r] += a[3] as u64;
            let d = supply.dense[e];
            if d == NONE {
                continue;
            }
            samples += a[0] as u64;
            dist += a[1] as u64;
            let at = d as usize * n_bins + bin;
            counts.n_in[at] = counts.n_in[at].saturating_add((a[2] + a[5] + a[6]) as u16);
            counts.left[at] = counts.left[at].saturating_add(a[4] as u16);
            counts.inserted[at] = counts.inserted[at].saturating_add(a[5] as u16);
        }
        speed_by_bin[bin] = if samples > 0 { dist as f32 / 8.0 / samples as f32 / (10.0) } else { 0.0 };
        let active = g.n_active as u64 + c[C_NEW] as u64;
        peak_active = peak_active.max(active as u32);
        vehicle_steps += (before + active) / 2 * run;
        let arrived = c[C_ARRIVED] as u64;
        let inserted = c[C_INSERTED] as u64;
        // The kernel's counter, the per-edge counters and the vehicle buffer must agree at every drain.
        imbalance += (inserted as i64 - inserted_by_replica.iter().sum::<u64>() as i64).abs();
        bin += 1;
        counts.end_bin = bin;
        no_arrival_bins = if arrived == last_arrived { no_arrival_bins + 1 } else { 0 };
        last_arrived = arrived;
        let now = s.begin + done as f32 * s.dt;
        pause.at_bin_edge(engine, now, &counts, bin - 1);
        // 15 minutes with nobody arriving, and what is on the road barely moving.
        let mean_speed = if samples > 0 { dist as f64 / 8.0 / samples as f64 / 10.0 } else { 0.0 };
        if active > 0 && no_arrival_bins >= 3 && mean_speed < 1.0 {
            stalled_at_s = Some(now);
            due_at_stall = due_by_bin[bin.min(n_bins)] as f64 / requested.max(1) as f64;
            end_s = now;
            break;
        }
        if arrived >= requested * k as u64 {
            end_s = now;
            break;
        }
        end_s = now;
    }
    let sim = engine.sim.as_ref().expect("sim");
    let wall_s = t0.elapsed().as_secs_f64();
    let out = sim.trip_outputs(&engine.gpu);
    let c = sim.counters(&engine.gpu);
    let g = sim.globals(&engine.gpu);
    let queues: Vec<cars_core::world::GpuQueue> = sim.read(&engine.gpu, &sim.buffers.queues, engine.world.queues.len() as u64);
    let dt = s.dt as f64;
    let n_tr = pop.travellers.len();
    let mut experienced = vec![f32::NAN; n_tr];
    let mut finished = vec![false; n_tr];
    let mut samples: Vec<Vec<f32>> = vec![Vec::with_capacity(n_tr); k];
    let mut stats: Vec<TripStats> = vec![TripStats::default(); k];
    let mut queue_inserted = vec![0u64; k];
    for (q, live) in engine.world.queues.iter().zip(&queues) {
        let r = engine.world.replica_edge_start.iter().rposition(|&x| x <= q.edge).unwrap_or(0);
        queue_inserted[r] += (live.next - q.next) as u64;
    }
    let mut arrived_by = vec![0u64; k];
    let mut wait_sum = vec![0f64; k];
    for (ti, o) in out.iter().enumerate() {
        let trip = &engine.world.trips[ti];
        let r = trip.replica as usize;
        let src = engine.world.trip_source[ti] as usize;
        let tr = pop.demand.trips[src].id as usize;
        let sched = trip.depart_step as f64 * dt;
        let st = &mut stats[r];
        st.requested += 1;
        let tt = if o.flags & 1 != 0 {
            st.arrived += 1;
            arrived_by[r] += 1;
            st.route_km += o.route_len as f64 / 1000.0;
            wait_sum[r] += (o.depart_step as f64 * dt - sched).max(0.0);
            (o.arrive_step as f64 * dt - sched).max(0.0)
        } else {
            (end_s as f64 - s.begin as f64 - sched).max(0.0)
        };
        samples[r].push(tt as f32);
        st.total_generalised_s += tt;
        if r == 0 {
            experienced[tr] = tt as f32;
            finished[tr] = o.flags & 1 != 0;
        }
    }
    let mut ledgers = Vec::with_capacity(k);
    let total_arrived: u64 = arrived_by.iter().sum();
    imbalance += (total_arrived as i64 - c[C_ARRIVED] as i64).abs();
    // Arrivals of the last step stay in the buffer, flagged, until the next sort.
    let on_road = sim.vehicles(&engine.gpu).iter().filter(|v| v.flags & F_REMOVED == 0).count() as i64;
    imbalance += (c[C_INSERTED] as i64 - c[C_ARRIVED] as i64 - on_road).abs();
    let due_end = due_by_bin[bin.min(n_bins)];
    for r in 0..k {
        let st = &mut stats[r];
        st.unfinished = st.requested - st.arrived;
        let n = samples[r].len();
        st.mean_travel_s = st.total_generalised_s / n.max(1) as f64;
        samples[r].sort_unstable_by(f32::total_cmp);
        if n > 0 {
            st.p50_travel_s = samples[r][n / 2] as f64;
            st.p95_travel_s = samples[r][(n * 95 / 100).min(n - 1)] as f64;
        }
        st.mean_insertion_wait_s = wait_sum[r] / st.arrived.max(1) as f64;
        let inserted = inserted_by_replica[r];
        let imb = imbalance + (inserted as i64 - queue_inserted[r] as i64).abs();
        let active = inserted.saturating_sub(arrived_by[r]);
        let due = due_end.max(inserted);
        ledgers.push(Ledger {
            requested: st.requested,
            arrived: arrived_by[r],
            active,
            waiting_to_insert: due - inserted,
            not_yet_due: st.requested - due.min(st.requested),
            teleports: teleports_by_replica[r],
            // Only counted per world, so a replica's share.
            collisions: c[C_COLLISIONS] as u64 / k as u64,
            imbalance: imb,
        });
    }
    let _ = g;
    DayResult { counts, ledgers, stats, experienced, finished, stalled_at_s, due_at_stall, end_s, wall_s, vehicle_steps, peak_active, speed_by_bin }
}
