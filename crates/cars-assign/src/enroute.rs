//! En-route rerouting and incidents, at the 300 s pause between bins. Off for baseline days.

use cars_core::net::Net;
use cars_core::world::GpuVeh;
use rayon::prelude::*;

use crate::costs::{BIN_S, CostTable, DayCounts, NONE, Supply};
use crate::day::{Engine, Pause};
use crate::route::Work;
use crate::update::Graphs;
use crate::{population::Population, unit};

const F_BEST_DIRTY: u32 = 16;
const OFF_ROUTE_I: u64 = std::mem::offset_of!(GpuVeh, route_i) as u64;
const OFF_ROUTE_END: u64 = std::mem::offset_of!(GpuVeh, route_end) as u64;
const OFF_FLAGS: u64 = std::mem::offset_of!(GpuVeh, flags) as u64;

#[derive(Clone, Debug)]
pub struct Incident {
    pub edges: Vec<u32>,
    pub t0: f32,
    pub t1: f32,
    /// Lane speed while it lasts. About 1 m/s leaves near a fifth of normal discharge.
    pub speed: f32,
}

#[derive(Clone, Debug, Default, serde::Serialize)]
pub struct EnrouteStats {
    pub epochs: u32,
    pub considered: u64,
    pub patched: u64,
    pub arena_edges: u64,
    pub out_of_arena: u64,
    pub route_secs: f64,
}

pub struct Enroute<'a> {
    pub net: &'a Net,
    pub supply: &'a Supply,
    pub graphs: &'a Graphs,
    pub pop: &'a Population,
    /// Share of vehicles that follow live guidance.
    pub navigators: f64,
    pub incident: Option<Incident>,
    pub seed: u64,
    pub stats: EnrouteStats,
    pub arena_at: u64,
    incident_on: bool,
}

impl<'a> Enroute<'a> {
    pub fn new(net: &'a Net, supply: &'a Supply, graphs: &'a Graphs, pop: &'a Population, navigators: f64, incident: Option<Incident>, seed: u64) -> Self {
        Self { net, supply, graphs, pop, navigators, incident, seed, stats: EnrouteStats::default(), arena_at: 0, incident_on: false }
    }

    fn set_incident(&mut self, engine: &mut Engine, on: bool) {
        let Some(inc) = &self.incident else { return };
        let sim = engine.sim.as_ref().expect("sim");
        for &d in &inc.edges {
            let e = &self.net.edges[self.supply.normal[d as usize] as usize];
            for r in 0..engine.seeds.len() {
                let lane0 = engine.world.edges[engine.world.replica_edge_start[r] as usize + self.supply.normal[d as usize] as usize].first_lane;
                for l in 0..e.lane_count {
                    let at = (lane0 + l) as usize;
                    let mut lane = engine.world.lanes[at];
                    if on {
                        lane.speed = lane.speed.min(inc.speed);
                    }
                    engine.gpu.queue.write_buffer(&sim.buffers.lanes, at as u64 * std::mem::size_of::<cars_core::world::GpuLane>() as u64, bytemuck::bytes_of(&lane));
                }
            }
        }
        engine.gpu.queue.submit([]);
        self.incident_on = on;
    }

    /// What is on each edge right now, over the last bin's rate.
    fn instant_costs(&self, counts: &DayCounts, bin: usize) -> CostTable {
        let n = self.supply.n();
        let k = counts.replicas.max(1) as f32;
        let mut c = vec![0f32; n];
        c.par_iter_mut().enumerate().for_each(|(e, x)| {
            let (mut cum_in, mut cum_out, mut peak) = (0.0f32, 0.0f32, 0.0f32);
            for b in 0..=bin {
                cum_in += counts.n_in[e * counts.n_bins + b] as f32 / k;
                let l = counts.left[e * counts.n_bins + b] as f32 / k;
                cum_out += l;
                peak = peak.max(l / BIN_S);
            }
            let rate = (counts.left[e * counts.n_bins + bin] as f32 / k / BIN_S).max(0.25 * peak.max(0.1));
            *x = self.supply.ff[e] + (cum_in - cum_out).max(0.0) / rate;
        });
        CostTable { n_edges: n, n_bins: 1, wait: vec![0.0; n], c }
    }

    fn reroute(&mut self, engine: &mut Engine, counts: &DayCounts, bin: usize) {
        if self.navigators <= 0.0 {
            return;
        }
        let t0 = std::time::Instant::now();
        let live = self.instant_costs(counts, bin);
        let sim = engine.sim.as_ref().expect("sim");
        let vs = sim.vehicles(&engine.gpu);
        let per = engine.world.n_edges_per_replica;
        if self.arena_at == 0 {
            self.arena_at = engine.world.routes.len() as u64;
        }
        let dummy = engine.world.params.dummy_lane;
        let routes = &engine.world.routes;
        let lanes = &engine.world.lanes;
        let trips = &engine.world.trips;
        let supply = self.supply;
        let graphs = self.graphs;
        let (nav, seed) = (self.navigators, self.seed);
        let vt = &self.pop.demand.vtypes;
        let patches: Vec<(usize, Vec<u32>)> = vs
            .par_iter()
            .enumerate()
            .filter(|(_, v)| v.flags & 1 == 0 && v.lane != dummy && lanes[v.lane as usize].flags & 1 == 0 && v.route_i + 2 < v.route_end && unit(seed, v.trip as u64) < nav)
            .map_init(
                || Work::new(graphs.work_size),
                |w, (i, v)| {
                    if (v.route_end as usize) > routes.len() {
                        return None;
                    }
                    let edge0 = trips[v.trip as usize].replica * per;
                    let rest: Vec<u32> = routes[v.route_i as usize + 1..v.route_end as usize].iter().map(|&e| supply.dense[(e - edge0) as usize]).collect();
                    if rest.iter().any(|&d| d == NONE) {
                        return None;
                    }
                    let (next, dest) = (rest[0], *rest.last().unwrap());
                    let cost_now: f32 = rest.iter().map(|&e| live.c[e as usize]).sum();
                    let g = &graphs.by_mask[&vt[v.vtype as usize].vclass];
                    let (path, cost_new) = g.path(&live, w, next, dest, 0.0, true)?;
                    (cost_now - cost_new > (0.1 * cost_now).max(60.0) && path != rest).then(|| {
                        let cur = routes[v.route_i as usize];
                        let mut full = vec![cur];
                        full.extend(path.iter().map(|&d| supply.normal[d as usize] + edge0));
                        (i, full)
                    })
                },
            )
            .flatten()
            .collect();
        self.stats.considered += vs.len() as u64;
        let capacity = sim.buffers.routes.size() / 4;
        let veh = sim.current_veh();
        let stride = std::mem::size_of::<GpuVeh>() as u64;
        for (i, full) in patches {
            let n = full.len() as u64;
            if self.arena_at + n > capacity {
                self.stats.out_of_arena += 1;
                continue;
            }
            engine.gpu.queue.write_buffer(&sim.buffers.routes, self.arena_at * 4, bytemuck::cast_slice(&full));
            engine.world.routes.extend_from_slice(&full);
            let at = i as u64 * stride;
            engine.gpu.queue.write_buffer(veh, at + OFF_ROUTE_I, bytemuck::bytes_of(&(self.arena_at as u32)));
            engine.gpu.queue.write_buffer(veh, at + OFF_ROUTE_END, bytemuck::bytes_of(&((self.arena_at + n) as u32)));
            engine.gpu.queue.write_buffer(veh, at + OFF_FLAGS, bytemuck::bytes_of(&(vs[i].flags | F_BEST_DIRTY)));
            self.arena_at += n;
            self.stats.patched += 1;
            self.stats.arena_edges += n;
        }
        engine.gpu.queue.submit([]);
        self.stats.epochs += 1;
        self.stats.route_secs += t0.elapsed().as_secs_f64();
    }
}

impl Pause for Enroute<'_> {
    fn at_bin_edge(&mut self, engine: &mut Engine, t: f32, counts: &DayCounts, bin: usize) {
        if let Some(inc) = &self.incident {
            let (a, b) = (inc.t0, inc.t1);
            if !self.incident_on && t >= a && t < b {
                self.set_incident(engine, true);
            } else if self.incident_on && t >= b {
                self.set_incident(engine, false);
            }
        }
        self.reroute(engine, counts, bin);
    }
}
