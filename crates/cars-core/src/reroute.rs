//! New routes for vehicles that missed their turn. The kernel asks, this answers between short batches.

use rayon::prelude::*;

use crate::gpu::Gpu;
use crate::net::Net;
use crate::router::Router;
use crate::sim::Sim;
use crate::world::{C_HU_REROUTE, REROUTE_LOG, World};

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
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
    pub patched: u64,
    pub failed: u64,
}

impl Rerouter {
    pub fn new(net: &Net, masks: impl IntoIterator<Item = u32>, sim: &Sim) -> Self {
        let arena_start = sim.buffers.route_arena_at;
        Self { router: Router::new(net, masks), served: 0, arena_at: arena_start, arena_start, arena_end: sim.buffers.routes.size() / 4, patched: 0, failed: 0 }
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
        let log: Vec<Request> = sim.read(gpu, &sim.buffers.reroute_req, REROUTE_LOG);
        let fresh: Vec<Request> = (self.served..asked).map(|k| log[(k as u64 % REROUTE_LOG) as usize]).collect();
        self.served = asked;
        let answers: Vec<Option<Vec<u32>>> = fresh
            .par_iter()
            .map(|r| {
                let lane = &world.lanes[r.lane as usize];
                let edge0 = world.trips[r.trip as usize].replica * world.n_edges_per_replica;
                let starts: Vec<u32> = (lane.links_start..lane.links_start + lane.links_count).map(|k| world.links[k as usize].to_edge - edge0).collect();
                let path = self.router.from_any(r.vclass, &starts, r.dest_edge - edge0)?;
                let mut full = vec![lane.edge];
                full.extend(path.iter().map(|&e| e + edge0));
                Some(full)
            })
            .collect();
        for (r, a) in fresh.iter().zip(answers) {
            let Some(full) = a.filter(|f| self.arena_at + f.len() as u64 <= self.arena_end) else {
                self.failed += 1;
                continue;
            };
            gpu.queue.write_buffer(&sim.buffers.routes, self.arena_at * 4, bytemuck::cast_slice(&full));
            let end = self.arena_at + full.len() as u64;
            gpu.queue.write_buffer(&sim.buffers.route_patch, r.trip as u64 * 8, bytemuck::cast_slice(&[self.arena_at as u32, end as u32]));
            self.arena_at = end;
            self.patched += 1;
        }
        gpu.queue.submit([]);
    }
}
