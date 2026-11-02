//! New routes for vehicles that missed their turn. The kernel asks, this answers between short batches.

use rayon::prelude::*;
use rustc_hash::FxHashSet;

use crate::gpu::Gpu;
use crate::net::Net;
use crate::router::Router;
use crate::sim::Sim;
use crate::world::{C_HU_REROUTE, REROUTE_LOG, World};

struct Request {
    trip: u32,
    lane: u32,
    dest_edge: u32,
    vclass: u32,
}

pub struct Rerouter {
    router: Router,
    served: u32,
    arena_at: u64,
    arena_start: u64,
    arena_end: u64,
    /// Aimsun's counts: rerouted on to the destination, sent out of the network, or with no way on at all.
    pub patched: u64,
    pub lost_outside: u64,
    pub failed: u64,
    lost: FxHashSet<u32>,
}

impl Rerouter {
    pub fn new(net: &Net, masks: impl IntoIterator<Item = u32>, sim: &Sim) -> Self {
        let arena_start = sim.buffers.route_arena_at;
        Self { router: Router::new(net, masks), served: 0, arena_at: arena_start, arena_start, arena_end: sim.buffers.routes.size() / 4, patched: 0, lost_outside: 0, failed: 0, lost: FxHashSet::default() }
    }

    /// Cars that missed a turn at least once.
    pub fn lost_cars(&self) -> u64 {
        self.lost.len() as u64
    }

    pub fn arena_used(&self) -> u64 {
        self.arena_at - self.arena_start
    }

    /// The route starts on the edge the vehicle is on, and goes on by a link its own lane has.
    pub fn service(&mut self, gpu: &Gpu, sim: &Sim, world: &World) {
        let asked = sim.counters(gpu)[C_HU_REROUTE];
        if asked == self.served {
            return;
        }
        let all: Vec<[u32; 2]> = sim.read(gpu, &sim.buffers.route_patch, world.params.n_trips as u64 + 2 * REROUTE_LOG);
        let log = &all[world.params.n_trips as usize..];
        let fresh: Vec<Request> = (self.served..asked)
            .map(|k| {
                let at = (k as u64 % REROUTE_LOG) as usize * 2;
                Request { trip: log[at][0], lane: log[at][1], dest_edge: log[at + 1][0], vclass: log[at + 1][1] }
            })
            .collect();
        self.served = asked;
        let answers: Vec<Option<(Vec<u32>, bool)>> = fresh
            .par_iter()
            .map(|r| {
                let lane = &world.lanes[r.lane as usize];
                let edge0 = world.trips[r.trip as usize].replica * world.n_edges_per_replica;
                let starts: Vec<u32> = (lane.links_start..lane.links_start + lane.links_count).map(|k| world.links[k as usize].to_edge - edge0).collect();
                let (path, outside) = match self.router.from_any(r.vclass, &starts, r.dest_edge - edge0) {
                    Some(p) => (p, false),
                    None => (self.router.to_any_exit(r.vclass, &starts)?, true),
                };
                let mut full = vec![lane.edge];
                full.extend(path.iter().map(|&e| e + edge0));
                Some((full, outside))
            })
            .collect();
        for (r, a) in fresh.iter().zip(answers) {
            self.lost.insert(r.trip);
            let Some((full, outside)) = a.filter(|f| self.arena_at + f.0.len() as u64 <= self.arena_end) else {
                self.failed += 1;
                continue;
            };
            self.lost_outside += outside as u64;
            gpu.queue.write_buffer(&sim.buffers.routes, self.arena_at * 4, bytemuck::cast_slice(&full));
            let end = self.arena_at + full.len() as u64;
            gpu.queue.write_buffer(&sim.buffers.route_patch, r.trip as u64 * 8, bytemuck::cast_slice(&[self.arena_at as u32, end as u32]));
            self.arena_at = end;
            self.patched += !outside as u64;
        }
        gpu.queue.submit([]);
    }
}
