//! Travellers, their remembered routes and the route arena. The arena is `Demand::routes`, so
//! `World` reads it directly and there is only one copy of every route on the CPU.

use std::io::{BufRead, BufReader, Read, Write};
use std::path::Path;

use bytemuck::{Pod, Zeroable};
use cars_core::demand::{ArrivalPos, Demand, DepartLane, DepartPos, DepartSpeed, Trip};
use cars_core::net::Net;
use flate2::Compression;
use flate2::read::GzDecoder;
use flate2::write::GzEncoder;
use rustc_hash::{FxHashMap, FxHasher};
use std::hash::{Hash, Hasher};

pub const MAX_PLAN: usize = 5;
/// Never rerouted, such as a bus line.
pub const CLASS_FIXED: u32 = 1;

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct Traveller {
    pub id: u32,
    pub class: u32,
    pub o_edge: u32,
    pub d_edge: u32,
    pub desired_arrival_s: f32,
    pub depart_s: f32,
    pub earliest_s: f32,
    pub latest_s: f32,
    /// Linked legs shift together. `tour_seq` orders them.
    pub tour: u32,
    pub tour_seq: u32,
    /// Indices into the route arena.
    pub plan: [u32; MAX_PLAN],
    pub n_plan: u32,
    pub cur: u32,
    pub vtype: u32,
    /// OD-time cell for calibration.
    pub cell: u32,
    /// Index into the table of depart and arrival procedures.
    pub proc_id: u32,
}

impl Traveller {
    #[inline]
    pub fn route(&self) -> u32 {
        self.plan[self.cur as usize]
    }

    pub fn add_route(&mut self, r: u32) {
        for i in 0..self.n_plan as usize {
            if self.plan[i] == r {
                self.cur = i as u32;
                return;
            }
        }
        if (self.n_plan as usize) < MAX_PLAN {
            self.plan[self.n_plan as usize] = r;
            self.cur = self.n_plan;
            self.n_plan += 1;
        } else {
            // The oldest route that is not in use goes, as in a rolling memory.
            let slot = (self.cur as usize + 1) % MAX_PLAN;
            self.plan[slot] = r;
            self.cur = slot as u32;
        }
    }
}

#[derive(Clone, Copy, PartialEq, Debug)]
pub struct Procedures {
    pub lane: DepartLane,
    pub pos: DepartPos,
    pub speed: DepartSpeed,
    pub arrival: ArrivalPos,
}

impl Default for Procedures {
    fn default() -> Self {
        Self { lane: DepartLane::BestProb, pos: DepartPos::Base, speed: DepartSpeed::Avg, arrival: ArrivalPos::Max }
    }
}

pub struct Population {
    pub travellers: Vec<Traveller>,
    /// Arena in `routes`, vehicle types in `vtypes`, sorted trips in `trips`.
    pub demand: Demand,
    pub procedures: Vec<Procedures>,
    index: FxHashMap<u64, u32>,
}

fn route_hash(r: &[u32], salt: u64) -> u64 {
    let mut h = FxHasher::default();
    salt.hash(&mut h);
    r.hash(&mut h);
    h.finish()
}

impl Population {
    pub fn new(demand: Demand, procedures: Vec<Procedures>, travellers: Vec<Traveller>) -> Self {
        let mut p = Self { travellers, demand, procedures, index: FxHashMap::default() };
        p.rebuild_index();
        p
    }

    fn rebuild_index(&mut self) {
        let mut idx = FxHashMap::default();
        idx.reserve(self.demand.routes.len());
        for (i, r) in self.demand.routes.iter().enumerate() {
            let mut salt = 0;
            loop {
                let h = route_hash(r, salt);
                if let std::collections::hash_map::Entry::Vacant(v) = idx.entry(h) {
                    v.insert(i as u32);
                    break;
                }
                salt += 1;
            }
        }
        self.index = idx;
    }

    /// Index of this route in the arena, added if new.
    pub fn intern(&mut self, r: Vec<u32>) -> u32 {
        let mut salt = 0;
        loop {
            let h = route_hash(&r, salt);
            match self.index.get(&h) {
                Some(&i) if self.demand.routes[i as usize] == r => return i,
                Some(_) => salt += 1,
                None => {
                    let i = self.demand.routes.len() as u32;
                    self.demand.routes.push(r);
                    self.index.insert(h, i);
                    return i;
                }
            }
        }
    }

    /// Drop routes no plan remembers. Route indices change, so masks cached on them must go too.
    pub fn compact(&mut self) -> usize {
        let n = self.demand.routes.len();
        let mut used = vec![false; n];
        for t in &self.travellers {
            for i in 0..t.n_plan as usize {
                used[t.plan[i] as usize] = true;
            }
        }
        let mut remap = vec![u32::MAX; n];
        let mut next = 0u32;
        let mut old = std::mem::take(&mut self.demand.routes);
        for (i, r) in old.iter_mut().enumerate() {
            if used[i] {
                remap[i] = next;
                self.demand.routes.push(std::mem::take(r));
                next += 1;
            }
        }
        for t in &mut self.travellers {
            for i in 0..t.n_plan as usize {
                t.plan[i] = remap[t.plan[i] as usize];
            }
        }
        self.rebuild_index();
        n - next as usize
    }

    /// Write the trips for this day, sorted by departure, with `Trip::id` holding the traveller.
    pub fn fill_trips(&mut self) {
        let mut order: Vec<u32> = (0..self.travellers.len() as u32).collect();
        let tv = &self.travellers;
        order.sort_unstable_by(|&a, &b| tv[a as usize].depart_s.total_cmp(&tv[b as usize].depart_s).then(a.cmp(&b)));
        let procs = &self.procedures;
        self.demand.trips = order
            .iter()
            .map(|&i| {
                let t = &tv[i as usize];
                let p = procs[t.proc_id as usize];
                Trip { id: i, depart: t.depart_s as f64, route: t.route(), vtype: t.vtype, depart_lane: p.lane, depart_pos: p.pos, depart_speed: p.speed, arrival_pos: p.arrival }
            })
            .collect();
    }

    /// Travellers from a loaded demand, keeping its routes as their first plan entry. Vehicle ids
    /// starting with a prefix in `fixed` are never rerouted.
    pub fn from_demand_fixed(mut demand: Demand, fixed: &[String]) -> Self {
        let mut procedures: Vec<Procedures> = Vec::new();
        let mut travellers = Vec::with_capacity(demand.trips.len());
        for (i, t) in demand.trips.iter().enumerate() {
            let p = Procedures { lane: t.depart_lane, pos: t.depart_pos, speed: t.depart_speed, arrival: t.arrival_pos };
            let proc_id = match procedures.iter().position(|x| *x == p) {
                Some(x) => x,
                None => {
                    procedures.push(p);
                    procedures.len() - 1
                }
            };
            let r = &demand.routes[t.route as usize];
            let mut tr = Traveller {
                id: i as u32,
                o_edge: r[0],
                d_edge: *r.last().unwrap(),
                depart_s: t.depart as f32,
                desired_arrival_s: f32::NAN,
                earliest_s: t.depart as f32 - 3600.0,
                latest_s: t.depart as f32 + 900.0,
                tour: i as u32,
                vtype: t.vtype,
                proc_id: proc_id as u32,
                class: u32::from(fixed.iter().any(|p| demand.ids[t.id as usize].starts_with(p.as_str()))) * CLASS_FIXED,
                ..Default::default()
            };
            tr.plan[0] = t.route;
            tr.n_plan = 1;
            travellers.push(tr);
        }
        demand.ids = Vec::new();
        Self::new(demand, procedures, travellers)
    }

    /// `id,class,o_edge,d_edge,desired_arrival_s,depart_s,earliest_s,latest_s,tour,tour_seq,vtype` with edge names.
    /// Routes are empty until routed.
    pub fn load_csv(path: &Path, net: &Net, mut demand: Demand) -> Result<(Self, u64), String> {
        let f = std::fs::File::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
        let reader: Box<dyn Read> = if path.extension().is_some_and(|x| x == "gz") { Box::new(GzDecoder::new(f)) } else { Box::new(f) };
        let mut travellers = Vec::new();
        let mut unknown = 0u64;
        for (n, line) in BufReader::new(reader).lines().enumerate() {
            let line = line.map_err(|e| e.to_string())?;
            if n == 0 {
                continue;
            }
            let v: Vec<&str> = line.split(',').collect();
            if v.len() < 11 {
                return Err(format!("{}: line {} has {} columns", path.display(), n + 1, v.len()));
            }
            let (Some(&o), Some(&d)) = (net.edge_index.get(v[2]), net.edge_index.get(v[3])) else {
                unknown += 1;
                continue;
            };
            let num = |i: usize| v[i].parse::<f32>().map_err(|e| format!("line {}: {e}", n + 1));
            let vtype = *demand.vtype_index.get(v[10]).ok_or_else(|| format!("unknown vType {}", v[10]))?;
            travellers.push(Traveller {
                id: v[0].parse().map_err(|_| format!("bad id on line {}", n + 1))?,
                class: v[1].parse().unwrap_or(0),
                o_edge: o,
                d_edge: d,
                desired_arrival_s: num(4)?,
                depart_s: num(5)?,
                earliest_s: num(6)?,
                latest_s: num(7)?,
                tour: v[8].parse().unwrap_or(0),
                tour_seq: v[9].parse().unwrap_or(0),
                vtype,
                ..Default::default()
            });
        }
        demand.trips = Vec::new();
        demand.routes = Vec::new();
        demand.ids = Vec::new();
        Ok((Self::new(demand, vec![Procedures::default()], travellers), unknown))
    }

    pub fn save_csv(&self, path: &Path, net: &Net) -> Result<(), String> {
        let f = std::fs::File::create(path).map_err(|e| e.to_string())?;
        let mut w = std::io::BufWriter::new(GzEncoder::new(f, Compression::fast()));
        writeln!(w, "id,class,o_edge,d_edge,desired_arrival_s,depart_s,earliest_s,latest_s,tour,tour_seq,vtype,route").map_err(|e| e.to_string())?;
        for t in &self.travellers {
            let route: Vec<&str> = self.demand.routes[t.route() as usize].iter().map(|&e| net.edges[e as usize].id.as_str()).collect();
            writeln!(
                w,
                "{},{},{},{},{},{},{},{},{},{},{},{}",
                t.id, t.class, net.edges[t.o_edge as usize].id, net.edges[t.d_edge as usize].id, t.desired_arrival_s, t.depart_s, t.earliest_s, t.latest_s, t.tour, t.tour_seq, self.demand.vtypes[t.vtype as usize].id, route.join(" ")
            )
            .map_err(|e| e.to_string())?;
        }
        Ok(())
    }

    /// Raw state, for resuming after a kill.
    pub fn save_state(&self, path: &Path) -> Result<(), String> {
        let tmp = path.with_extension("tmp");
        {
            let mut w = std::io::BufWriter::with_capacity(1 << 20, std::fs::File::create(&tmp).map_err(|e| e.to_string())?);
            let put = |w: &mut std::io::BufWriter<std::fs::File>, b: &[u8]| w.write_all(b).map_err(|e| e.to_string());
            put(&mut w, bytemuck::bytes_of(&(self.travellers.len() as u64)))?;
            put(&mut w, bytemuck::cast_slice(&self.travellers))?;
            put(&mut w, bytemuck::bytes_of(&(self.demand.routes.len() as u64)))?;
            for r in &self.demand.routes {
                put(&mut w, bytemuck::bytes_of(&(r.len() as u32)))?;
                put(&mut w, bytemuck::cast_slice(r))?;
            }
        }
        std::fs::rename(&tmp, path).map_err(|e| e.to_string())
    }

    pub fn load_state(&mut self, path: &Path) -> Result<(), String> {
        let mut r = BufReader::with_capacity(1 << 20, std::fs::File::open(path).map_err(|e| format!("{}: {e}", path.display()))?);
        let mut word = [0u8; 8];
        r.read_exact(&mut word).map_err(|e| e.to_string())?;
        let n = u64::from_le_bytes(word) as usize;
        let mut tv = vec![Traveller::default(); n];
        r.read_exact(bytemuck::cast_slice_mut(&mut tv)).map_err(|e| e.to_string())?;
        r.read_exact(&mut word).map_err(|e| e.to_string())?;
        let m = u64::from_le_bytes(word) as usize;
        let mut routes = Vec::with_capacity(m);
        for _ in 0..m {
            let mut len = [0u8; 4];
            r.read_exact(&mut len).map_err(|e| e.to_string())?;
            let mut route = vec![0u32; u32::from_le_bytes(len) as usize];
            r.read_exact(bytemuck::cast_slice_mut(&mut route)).map_err(|e| e.to_string())?;
            routes.push(route);
        }
        self.travellers = tv;
        self.demand.routes = routes;
        self.rebuild_index();
        Ok(())
    }
}
