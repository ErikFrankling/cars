//! What a physical-mode run has to answer for: contacts between bodies, gridlock, teleports and the
//! energy used. A gridlock is a failure and is written out with where it is.

use std::collections::HashMap;
use std::path::Path;

use cars_core::{
    Gpu,
    demand::Demand,
    net::Net,
    physics,
    sim::Sim,
    world::{self, GpuVeh, World},
};
use serde_json::json;

pub const F_SHADOW: u32 = 16384;
const F_REMOVED: u32 = 1;
const GRIDLOCK_EVERY: f32 = 60.0;

pub fn offset_of(v: &GpuVeh, world: &World) -> f32 {
    let t = &world.vtypes[v.vtype as usize];
    let v_lat = if v.flags & 65536 != 0 { 1.1 } else { t.v_lat };
    physics::lateral_offset(v.phys, world.lanes[v.lane as usize].width, v_lat)
}

#[derive(Clone, Debug)]
struct Incident {
    kind: u32,
    first: u32,
    last: u32,
    samples: u32,
    worst: f32,
    lane_a: u32,
    lane_b: u32,
    x: f32,
    y: f32,
}

#[derive(Clone, Debug)]
struct StuckLane {
    first: f32,
    last: f32,
    wait: f32,
    cars: usize,
    cause: String,
}

pub struct Physics {
    begin: f32,
    dt: f32,
    gridlock_after: f32,
    incidents: HashMap<(u32, u32), Incident>,
    contacts_seen: u32,
    log_lost: u32,
    lane_xy: Vec<[f32; 2]>,
    next_gridlock: f32,
    gridlocks: Vec<serde_json::Value>,
    worst_stuck: usize,
    last_gridlock: Option<serde_json::Value>,
    /// Every lane whose head was ever stuck, for the low-demand check.
    stuck_lanes: HashMap<u32, StuckLane>,
}

pub struct Finished {
    pub text: String,
    pub json: serde_json::Value,
}

impl Physics {
    pub fn new(net: &Net, world: &World, begin: f32, dt: f32, gridlock_after: f32) -> Self {
        let lane_xy = net.lanes.iter().map(|l| l.shape.get(l.shape.len() / 2).copied().unwrap_or([0.0, 0.0])).collect();
        let _ = world;
        Self {
            begin,
            dt,
            gridlock_after,
            incidents: HashMap::new(),
            contacts_seen: 0,
            log_lost: 0,
            lane_xy,
            next_gridlock: begin + GRIDLOCK_EVERY,
            gridlocks: Vec::new(),
            worst_stuck: 0,
            last_gridlock: None,
            stuck_lanes: HashMap::new(),
        }
    }

    pub fn collect(&mut self, sim: &Sim, gpu: &Gpu, net: &Net, world: &World, done: u64) {
        let now = self.begin + done as f32 * self.dt;
        let c = sim.counters(gpu);
        let seen = c[world::C_CONTACT];
        if seen != self.contacts_seen {
            let log = sim.contacts(gpu);
            let fresh = seen - self.contacts_seen;
            if fresh as u64 > world::CONTACT_LOG {
                self.log_lost += fresh - world::CONTACT_LOG as u32;
            }
            for k in 0..(fresh as u64).min(world::CONTACT_LOG) {
                let at = (seen as u64 - 1 - k) % world::CONTACT_LOG;
                let e = &log[at as usize];
                let key = (e.trip_a.min(e.trip_b), e.trip_a.max(e.trip_b));
                let i = self.incidents.entry(key).or_insert(Incident { kind: e.kind, first: e.step, last: e.step, samples: 0, worst: 0.0, lane_a: e.lane_a, lane_b: e.lane_b, x: e.x, y: e.y });
                i.samples += 1;
                i.first = i.first.min(e.step);
                i.last = i.last.max(e.step);
                if e.depth > i.worst || e.kind as usize >= world::CONTACT_BODIES {
                    i.worst = e.depth;
                    i.kind = e.kind;
                    i.lane_a = e.lane_a;
                    i.lane_b = e.lane_b;
                    i.x = e.x;
                    i.y = e.y;
                }
            }
            self.contacts_seen = seen;
        }
        if now >= self.next_gridlock {
            self.next_gridlock = now + GRIDLOCK_EVERY;
            let g = self.gridlock(sim, gpu, net, world, now);
            if let Some(g) = g {
                self.gridlocks.push(json!({"t": now, "stuck": g["stuck"], "cycles": g["cycles"].as_array().map_or(0, |a| a.len())}));
                self.last_gridlock = Some(g);
            }
        }
    }

    /// Who is waiting for whom. Vehicles stuck for longer than any signal cycle, lane by lane, with
    /// each lane pointing at the lane its head wants next. A loop in that graph cannot resolve itself.
    fn gridlock(&mut self, sim: &Sim, gpu: &Gpu, net: &Net, world: &World, now: f32) -> Option<serde_json::Value> {
        let vs = sim.vehicles(gpu);
        let items: Vec<[u32; 10]> = sim.read(gpu, &sim.buffers.items, vs.len() as u64 * 8);
        let mut heads: HashMap<u32, usize> = HashMap::new();
        let mut stuck = 0usize;
        let mut wait_sum = 0.0f32;
        for (i, v) in vs.iter().enumerate() {
            if v.flags & (F_REMOVED | F_SHADOW) != 0 || v.lane == world.params.dummy_lane {
                continue;
            }
            if v.wait >= self.gridlock_after {
                stuck += 1;
                wait_sum += v.wait;
            }
            let h = heads.entry(v.lane).or_insert(i);
            if vs[*h].pos < v.pos {
                *h = i;
            }
        }
        if stuck == 0 {
            return None;
        }
        self.worst_stuck = self.worst_stuck.max(stuck);
        let mut next: HashMap<u32, u32> = HashMap::new();
        let mut causes: HashMap<&str, u32> = HashMap::new();
        let mut places: Vec<(f32, u32)> = Vec::new();
        for (&lane, &i) in &heads {
            let v = &vs[i];
            if v.wait < self.gridlock_after {
                continue;
            }
            places.push((v.wait, lane));
            let link = items[i * 8][0];
            let link = if (link as usize) < world.links.len() { link } else { u32::MAX };
            let denied = items[i * 8][9] == 1;
            let cause = if link == u32::MAX || v.n_items == 0 {
                if v.lc_own & 3 != 0 { "wants another lane" } else { "no link ahead" }
            } else if denied {
                "junction lane occupied or exit full"
            } else {
                "next lane or right of way"
            };
            *causes.entry(cause).or_insert(0) += 1;
            let cars = vs.iter().filter(|o| o.lane == lane && o.flags & (F_REMOVED | F_SHADOW) == 0).count();
            let state = if link == u32::MAX { '-' } else {
                let k = &world.links[link as usize];
                if k.tl == u32::MAX { k.state as u8 as char } else { 's' }
            };
            let s = self.stuck_lanes.entry(lane).or_insert(StuckLane { first: now, last: now, wait: 0.0, cars: 0, cause: String::new() });
            s.last = now;
            s.wait = s.wait.max(v.wait);
            s.cars = s.cars.max(cars);
            s.cause = format!("{cause}; link {state}, tl {}", link != u32::MAX && world.links[link as usize].tl != u32::MAX);
            if link != u32::MAX && v.n_items != 0 {
                next.insert(lane, world.links[link as usize].to_lane);
            }
        }
        let mut cycles = Vec::new();
        let mut done: HashMap<u32, bool> = HashMap::new();
        for &start in next.keys() {
            if done.contains_key(&start) {
                continue;
            }
            let mut path = Vec::new();
            let mut at = start;
            while let Some(&n) = next.get(&at) {
                if done.contains_key(&at) {
                    break;
                }
                done.insert(at, true);
                path.push(at);
                at = n;
                if let Some(pos) = path.iter().position(|&l| l == at) {
                    let ring = &path[pos..];
                    let xy = self.lane_xy[ring[0] as usize];
                    cycles.push(json!({"lanes": ring.iter().map(|&l| net.lanes[l as usize].id.clone()).collect::<Vec<_>>(), "x": xy[0], "y": xy[1]}));
                    break;
                }
            }
        }
        places.retain(|&(_, l)| (l as usize) < net.lanes.len());
        places.sort_by(|a, b| b.0.total_cmp(&a.0));
        let worst: Vec<_> = places.iter().take(10).map(|&(w, l)| {
            let xy = self.lane_xy[l as usize];
            json!({"lane": net.lanes[l as usize].id, "wait": w, "x": xy[0], "y": xy[1]})
        }).collect();
        Some(json!({"t": now, "stuck": stuck, "mean_wait": wait_sum / stuck as f32, "cycles": cycles, "causes": causes, "worst_heads": worst}))
    }

    #[allow(clippy::too_many_arguments)]
    pub fn finish(&mut self, sim: &Sim, gpu: &Gpu, net: &Net, world: &World, heavy: &[bool], c: &[u32], done: u64, m_updates: f64, wall: f64) -> Finished {
        self.collect(sim, gpu, net, world, done);
        let last = self.gridlock(sim, gpu, net, world, self.begin + done as f32 * self.dt);
        let mut by_kind = vec![0u32; world::CONTACT_NAMES.len()];
        let mut samples = vec![0u32; world::CONTACT_NAMES.len()];
        for i in self.incidents.values() {
            by_kind[i.kind as usize] += 1;
            samples[i.kind as usize] += i.samples;
        }
        let mut list: Vec<&Incident> = self.incidents.values().collect();
        list.sort_by(|a, b| b.worst.total_cmp(&a.worst));
        let place = |i: &&Incident| json!({
            "kind": world::CONTACT_NAMES[i.kind as usize], "t": self.begin + i.first as f32 * self.dt, "last": self.begin + i.last as f32 * self.dt, "samples": i.samples, "depth": i.worst,
            "lane_a": net.lanes[i.lane_a as usize].id, "lane_b": net.lanes[i.lane_b as usize].id, "x": i.x, "y": i.y,
        });
        let mut stuck: Vec<_> = self.stuck_lanes.iter().collect();
        stuck.sort_by(|a, b| b.1.wait.total_cmp(&a.1.wait));
        let stuck_list: Vec<_> = stuck.iter().take(5000).map(|(l, s)| {
            let l = **l;
            let xy = self.lane_xy[l as usize];
            json!({"lane": net.lanes[l as usize].id, "x": xy[0], "y": xy[1], "first": s.first, "last": s.last, "wait": s.wait, "cars": s.cars, "cause": s.cause})
        }).collect();
        let energy = sim.trip_energy(gpu);
        let out = sim.trip_outputs(gpu);
        let (mut wheel, mut brake, mut road, mut pe, mut ke, mut fuel, mut ev, mut km, mut worst_balance, mut trips) = (0.0f64, 0.0f64, 0.0f64, 0.0f64, 0.0f64, 0.0f64, 0.0f64, 0.0f64, 0.0f32, 0u32);
        for (i, e) in energy.iter().enumerate() {
            if out[i].flags & 1 == 0 {
                continue;
            }
            let t = physics::trip_energy(e, heavy[world.trips[i].vtype as usize]);
            wheel += t.wheel_kwh as f64;
            brake += t.brake_kwh as f64;
            road += t.road_kwh as f64;
            pe += t.pe_kwh as f64;
            ke += t.ke_kwh as f64;
            fuel += t.fuel_l as f64;
            ev += t.ev_kwh as f64;
            km += e.dist as f64 / 1000.0;
            worst_balance = worst_balance.max(t.residual.abs());
            trips += 1;
        }
        let per_km = |x: f64| if km > 0.0 { x * 1000.0 / km } else { 0.0 };
        let collisions: u32 = by_kind[..world::CONTACT_BODIES].iter().sum();
        let kinds: Vec<String> = world::CONTACT_NAMES.iter().zip(&by_kind).map(|(n, k)| format!("{n} {k}")).collect();
        let stuck_now = last.as_ref().map_or(0, |g| g["stuck"].as_u64().unwrap_or(0));
        let cycles_now = last.as_ref().and_then(|g| g["cycles"].as_array().map(|a| a.len())).unwrap_or(0);
        let mut text = format!(
            "physics: collisions {collisions} incidents, {} contact samples ({}){}; teleports {}; certificate floor hits {}, no-brake {}, dead-end clamps {}, crossed without grant {}; lost on a wrong lane {}; shadows {}, refused {}, refused for room {}; denied bids {}\nenergy: {} trips, {km:.0} km, wheel {:.0} Wh/km, brake {:.0}, road {:.0}, combustion {:.2} l/100km, electric {:.0} Wh/km, books balance within {:.4}%\ngridlock: {stuck_now} vehicles stuck over {} s now, worst {}, {cycles_now} waiting cycles now",
            c[world::C_CONTACT], kinds.join(", "), if self.log_lost > 0 { format!(", {} log entries lost", self.log_lost) } else { String::new() }, c[4],
            c[world::C_CERT_FLOOR], c[world::C_NO_BRAKE], c[world::C_DEAD_END], c[world::C_UNGRANTED], c[world::C_LOST], c[world::C_SHADOWS], c[world::C_SHADOW_REFUSED], c[world::C_LC_REFUSED_ROOM], c[world::C_DENIED],
            trips, per_km(wheel), per_km(brake), per_km(road), if km > 0.0 { fuel * 100.0 / km } else { 0.0 }, per_km(ev), worst_balance * 100.0,
            self.gridlock_after, self.worst_stuck,
        );
        if let Some(g) = &last {
            if cycles_now > 0 || stuck_now > 0 {
                text.push_str(&format!("\nGRIDLOCK FAILURE: {}", serde_json::to_string(g).unwrap_or_default()));
            }
        }
        let json = json!({
            "collision_incidents": collisions, "contact_samples": c[world::C_CONTACT], "incidents_by_kind": world::CONTACT_NAMES.iter().zip(&by_kind).map(|(n, k)| (n.to_string(), *k)).collect::<HashMap<_, _>>(),
            "worst_incidents": list.iter().take(50).map(place).collect::<Vec<_>>(), "contact_log_lost": self.log_lost,
            "teleports": c[4], "lane_changes": c[6], "cert_floor": c[world::C_CERT_FLOOR], "no_brake": c[world::C_NO_BRAKE], "dead_end": c[world::C_DEAD_END], "ungranted": c[world::C_UNGRANTED],
            "shadows": c[world::C_SHADOWS], "shadow_refused": c[world::C_SHADOW_REFUSED], "lc_refused_room": c[world::C_LC_REFUSED_ROOM], "denied": c[world::C_DENIED], "overflow": c[5], "items_full": c[8],
            "lost": c[world::C_LOST], "inserted": c[3], "arrived": c[2], "m_updates_per_s": m_updates, "wall_s": wall, "steps": done,
            "stuck_lanes": stuck_list, "gridlock_end": last, "gridlock_series": self.gridlocks, "gridlock_worst_stuck": self.worst_stuck,
            "energy": {"trips": trips, "km": km, "wheel_wh_km": per_km(wheel), "brake_wh_km": per_km(brake), "road_wh_km": per_km(road), "pe_wh_km": per_km(pe), "ke_wh_km": per_km(ke), "fuel_l_100km": if km > 0.0 { fuel * 100.0 / km } else { 0.0 }, "ev_wh_km": per_km(ev), "balance_worst": worst_balance},
        });
        Finished { text, json }
    }
}

/// Types and lanes as the kernel holds them, so that a check can run without it.
pub fn write_phys_json(path: &Path, net: &Net, world: &World, demand: &Demand) -> std::io::Result<()> {
    let types: Vec<_> = world.vtypes.iter().zip(&demand.vtypes).map(|(g, t)| json!({
        "id": t.id, "length": g.length, "width": g.width, "min_gap": g.min_gap, "m_ref": g.m_ref, "pw_kg": g.pw_kg, "road_a": g.road_a, "road_c": g.road_c, "i_inv": g.i_inv, "trac": g.trac,
        "v_corner": g.v_corner, "b_lo": g.b_lo, "b_hi": g.b_hi, "t_r": g.t_r, "a0": g.a0, "a1": g.a1, "a_floor": g.a_floor, "v_lat": g.v_lat, "tau": g.ph_tau,
        "vclass": cars_core::net::VCLASSES.get(t.vclass.trailing_zeros() as usize).copied().unwrap_or("passenger"),
    })).collect();
    let lanes: HashMap<&str, _> = net.lanes.iter().enumerate().map(|(i, l)| {
        let g = &world.lanes[i];
        (l.id.as_str(), json!({"length": l.length, "speed": l.speed, "gz": g.gz, "curve_v": g.curve_v, "sqrt_r": g.sqrt_r, "s_curve": g.s_curve, "s_curve_end": g.s_curve_end, "width": g.width, "zones": g.zone_count}))
    }).collect();
    std::fs::write(path, serde_json::to_string(&json!({"mu": world.params.mu, "dt": world.params.dt, "types": types, "lanes": lanes})).unwrap())
}
