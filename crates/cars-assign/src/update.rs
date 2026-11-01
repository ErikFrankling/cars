//! Route and departure updates, and the relative gap.

use cars_core::net::Net;
use rayon::prelude::*;
use rustc_hash::FxHashMap;

use crate::costs::{CostTable, NONE, Supply};
use crate::population::{CLASS_FIXED, Population, Traveller};
use crate::route::{Graph, Work};
use crate::unit;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Rule {
    /// Sample `share`; switch with probability `min(1, 2 rel / share)`. Same as `min(share, 2 rel)`
    /// overall while routing only the sample.
    Capped { share: f64 },
    /// Everyone goes to the best route. The control that gridlocks.
    Everyone,
    /// A chance per traveller, and only if the saving beats max(30 s, 5%).
    Bounded { chance: f64 },
}

pub struct Graphs {
    pub by_mask: FxHashMap<u32, Graph>,
    pub work_size: usize,
}

impl Graphs {
    pub fn new(net: &Net, supply: &Supply, pop: &Population, landmarks: usize) -> Self {
        let mut masks: Vec<u32> = pop.travellers.iter().map(|t| pop.demand.vtypes[t.vtype as usize].vclass).collect();
        masks.sort_unstable();
        masks.dedup();
        let by_mask = masks.par_iter().map(|&m| (m, Graph::new(net, supply, m, landmarks))).collect();
        Self { by_mask, work_size: supply.n() }
    }
}

#[derive(Clone, Copy, Debug, Default, serde::Serialize)]
pub struct StepStats {
    pub sampled: u64,
    pub unreachable: u64,
    pub switched: u64,
    pub gap: f64,
    pub cost_current: f64,
    pub cost_best: f64,
    pub secs: f64,
    pub settled_per_path: f64,
}

fn to_dense(supply: &Supply, route: &[u32]) -> Vec<u32> {
    route.iter().map(|&e| supply.dense[e as usize]).collect()
}

fn sample_indices(pop: &Population, share: f64, seed: u64) -> Vec<u32> {
    pop.travellers
        .iter()
        .enumerate()
        .filter(|(i, t)| t.class & CLASS_FIXED == 0 && unit(seed, *i as u64) < share)
        .map(|(i, _)| i as u32)
        .collect()
}

/// Gap on a sample, with nothing changed.
pub fn gap_only(pop: &Population, graphs: &Graphs, supply: &Supply, costs: &CostTable, share: f64, seed: u64) -> StepStats {
    let sample = sample_indices(pop, share, seed);
    let t0 = std::time::Instant::now();
    let tv = &pop.travellers;
    let res: Vec<(f64, f64, bool)> = sample
        .par_iter()
        .map_init(
            || Work::new(graphs.work_size),
            |w, &i| {
                let t = &tv[i as usize];
                let g = &graphs.by_mask[&pop.demand.vtypes[t.vtype as usize].vclass];
                let cur = to_dense(supply, &pop.demand.routes[t.route() as usize]);
                let c_cur = costs.evaluate(&cur, t.depart_s) as f64;
                match g.path(costs, w, supply.dense[t.o_edge as usize], supply.dense[t.d_edge as usize], t.depart_s, true) {
                    Some((_, c)) => (c_cur, (c as f64).min(c_cur), true),
                    None => (c_cur, c_cur, false),
                }
            },
        )
        .collect();
    let mut s = StepStats { sampled: sample.len() as u64, ..Default::default() };
    for (a, b, ok) in res {
        s.cost_current += a;
        s.cost_best += b;
        s.unreachable += u64::from(!ok);
    }
    s.gap = (s.cost_current - s.cost_best) / s.cost_current.max(1e-9);
    s.secs = t0.elapsed().as_secs_f64();
    s
}

/// One route update. The sample doubles as the gap estimate.
pub fn update_routes(pop: &mut Population, graphs: &Graphs, supply: &Supply, costs: &CostTable, rule: Rule, seed: u64) -> StepStats {
    let share = match rule {
        Rule::Capped { share } => share,
        Rule::Everyone => 1.0,
        Rule::Bounded { chance } => chance,
    };
    let sample = sample_indices(pop, share, seed);
    let t0 = std::time::Instant::now();
    let tv = &pop.travellers;
    let routes = &pop.demand.routes;
    let vtypes = &pop.demand.vtypes;
    struct Out {
        i: u32,
        cur: f64,
        best: f64,
        path: Option<Vec<u32>>,
        reachable: bool,
    }
    let (res, settled): (Vec<Out>, u64) = {
        let settled = std::sync::atomic::AtomicU64::new(0);
        let res = sample
            .par_iter()
            .map_init(
                || Work::new(graphs.work_size),
                |w, &i| {
                    let t = &tv[i as usize];
                    let g = &graphs.by_mask[&vtypes[t.vtype as usize].vclass];
                    let cur = to_dense(supply, &routes[t.route() as usize]);
                    let c_cur = costs.evaluate(&cur, t.depart_s) as f64;
                    let before = w.settled;
                    let found = g.path(costs, w, supply.dense[t.o_edge as usize], supply.dense[t.d_edge as usize], t.depart_s, true);
                    settled.fetch_add(w.settled - before, std::sync::atomic::Ordering::Relaxed);
                    let Some((path, c)) = found else {
                        return Out { i, cur: c_cur, best: c_cur, path: None, reachable: false };
                    };
                    let c_best = (c as f64).min(c_cur);
                    let saving = c_cur - c_best;
                    let rel = if c_cur > 0.0 { saving / c_cur } else { 0.0 };
                    let take = match rule {
                        Rule::Capped { share } => unit(seed ^ 0x5555, i as u64) < (2.0 * rel / share).min(1.0),
                        Rule::Everyone => saving > 0.0,
                        Rule::Bounded { .. } => saving > (0.05 * c_cur).max(30.0),
                    };
                    let path = if take && path != cur { Some(path.iter().map(|&d| supply.normal[d as usize]).collect()) } else { None };
                    Out { i, cur: c_cur, best: c_best, path, reachable: true }
                },
            )
            .collect();
        (res, settled.load(std::sync::atomic::Ordering::Relaxed))
    };
    let mut s = StepStats { sampled: sample.len() as u64, ..Default::default() };
    for o in res {
        s.cost_current += o.cur;
        s.cost_best += o.best;
        s.unreachable += u64::from(!o.reachable);
        if let Some(p) = o.path {
            let r = pop.intern(p);
            pop.travellers[o.i as usize].add_route(r);
            s.switched += 1;
        }
    }
    s.gap = (s.cost_current - s.cost_best) / s.cost_current.max(1e-9);
    s.secs = t0.elapsed().as_secs_f64();
    s.settled_per_path = settled as f64 / s.sampled.max(1) as f64;
    s
}

/// Route everyone with no routes yet on free-flow costs. Returns (routed, dropped as unreachable).
pub fn route_free_flow(pop: &mut Population, graphs: &Graphs, supply: &Supply, n_bins: usize) -> (u64, u64) {
    let costs = CostTable::free_flow(supply, n_bins.min(2));
    let mut keys: Vec<(u32, u32, u32)> = pop
        .travellers
        .iter()
        .filter(|t| t.n_plan == 0)
        .map(|t| (t.o_edge, t.d_edge, pop.demand.vtypes[t.vtype as usize].vclass))
        .collect();
    keys.sort_unstable();
    keys.dedup();
    let found: Vec<Option<Vec<u32>>> = keys
        .par_iter()
        .map_init(
            || Work::new(graphs.work_size),
            |w, &(o, d, m)| {
                let (a, b) = (supply.dense[o as usize], supply.dense[d as usize]);
                if a == NONE || b == NONE {
                    return None;
                }
                graphs.by_mask[&m].path(&costs, w, a, b, 0.0, true).map(|(p, _)| p.iter().map(|&x| supply.normal[x as usize]).collect())
            },
        )
        .collect();
    let mut lookup: FxHashMap<(u32, u32, u32), u32> = FxHashMap::default();
    let mut dropped = 0u64;
    let mut routed = 0u64;
    let mut ok = Vec::with_capacity(keys.len());
    for (k, f) in keys.iter().zip(found) {
        if let Some(path) = f {
            let r = pop.intern(path);
            lookup.insert(*k, r);
            ok.push(r);
        }
    }
    let vts: Vec<u32> = pop.demand.vtypes.iter().map(|v| v.vclass).collect();
    let mut kept: Vec<Traveller> = Vec::with_capacity(pop.travellers.len());
    for t in pop.travellers.drain(..) {
        let mut t = t;
        if t.n_plan == 0 {
            match lookup.get(&(t.o_edge, t.d_edge, vts[t.vtype as usize])) {
                Some(&r) => {
                    t.plan[0] = r;
                    t.n_plan = 1;
                    t.cur = 0;
                    routed += 1;
                    kept.push(t);
                }
                None => dropped += 1,
            }
        } else {
            kept.push(t);
        }
    }
    pop.travellers = kept;
    (routed, dropped)
}

/// Throw away the routes a demand file gave, keeping fixed classes.
pub fn forget_routes(pop: &mut Population) {
    for t in &mut pop.travellers {
        if t.class & CLASS_FIXED == 0 {
            t.n_plan = 0;
            t.cur = 0;
        }
    }
}

/// Early and late weights, in seconds of travel time per second of schedule delay.
#[derive(Clone, Copy, Debug, serde::Serialize)]
pub struct Schedule {
    pub early: f32,
    pub late: f32,
}

impl Schedule {
    pub fn cost(&self, travel: f32, arrival: f32, desired: f32) -> f32 {
        travel + self.early * (desired - arrival).max(0.0) + self.late * (arrival - desired).max(0.0)
    }
}

#[derive(Clone, Copy, Debug, Default, serde::Serialize)]
pub struct DepartStats {
    pub tried: u64,
    pub moved: u64,
    pub at_window_edge: u64,
    pub mean_shift_s: f64,
}

/// `depart = desired arrival - experienced travel time`, for travellers with no observed departure.
pub fn consistent_start(pop: &mut Population, supply: &Supply, costs: &CostTable) {
    let travel: Vec<f32> = pop
        .travellers
        .par_iter()
        .map(|t| {
            let r = to_dense(supply, &pop.demand.routes[t.route() as usize]);
            costs.evaluate(&r, t.depart_s)
        })
        .collect();
    for (t, c) in pop.travellers.iter_mut().zip(travel) {
        if t.desired_arrival_s.is_finite() {
            t.depart_s = (t.desired_arrival_s - c).clamp(t.earliest_s, t.latest_s).max(0.0);
        }
    }
}

/// Default windows and desired arrivals, for demand with none: depart + free flow + 10%, then -60/+15 min.
pub fn default_schedule(pop: &mut Population, supply: &Supply) {
    let ff: Vec<f32> = pop.travellers.par_iter().map(|t| pop.demand.routes[t.route() as usize].iter().map(|&e| supply.ff[supply.dense[e as usize] as usize]).sum::<f32>()).collect();
    for (t, f) in pop.travellers.iter_mut().zip(ff) {
        if !t.desired_arrival_s.is_finite() {
            t.desired_arrival_s = t.depart_s + f * 1.1;
            t.earliest_s = (t.depart_s - 3600.0).max(0.0);
            t.latest_s = t.depart_s + 900.0;
        }
    }
}

/// Try a 5 minute shift for `share` of tours. Accept if the generalised saving beats 30 s. Legs of a tour shift together.
pub fn update_departures(pop: &mut Population, supply: &Supply, costs: &CostTable, s: Schedule, share: f64, seed: u64) -> DepartStats {
    let mut tours: FxHashMap<u32, Vec<u32>> = FxHashMap::default();
    for (i, t) in pop.travellers.iter().enumerate() {
        if t.class & CLASS_FIXED == 0 {
            tours.entry(t.tour).or_default().push(i as u32);
        }
    }
    let list: Vec<(u32, Vec<u32>)> = tours.into_iter().filter(|(k, _)| unit(seed, *k as u64) < share).collect();
    let tv = &pop.travellers;
    let routes = &pop.demand.routes;
    let leg_cost = |t: &Traveller, depart: f32| {
        let r = to_dense(supply, &routes[t.route() as usize]);
        let travel = costs.evaluate(&r, depart);
        s.cost(travel, depart + travel, t.desired_arrival_s)
    };
    let moves: Vec<(Vec<u32>, f32, bool)> = list
        .par_iter()
        .filter_map(|(k, legs)| {
            let try_shift = |d: f32| -> Option<f32> {
                let mut total = 0.0;
                for &i in legs {
                    let t = &tv[i as usize];
                    let at = t.depart_s + d;
                    if at < t.earliest_s || at > t.latest_s || at < 0.0 {
                        return None;
                    }
                    total += leg_cost(t, at) - leg_cost(t, t.depart_s);
                }
                Some(total)
            };
            let dir = if unit(seed ^ 0x77, *k as u64) < 0.5 { [-300.0, 300.0] } else { [300.0, -300.0] };
            let (mut best, mut best_d) = (0.0f32, 0.0f32);
            let mut blocked = false;
            for d in dir {
                match try_shift(d) {
                    Some(g) => {
                        if g < best {
                            best = g;
                            best_d = d;
                        }
                    }
                    None => blocked = true,
                }
            }
            (best < -30.0).then(|| (legs.clone(), best_d, blocked))
        })
        .collect();
    let mut st = DepartStats { tried: list.len() as u64, ..Default::default() };
    for (legs, d, _) in moves {
        for i in legs {
            pop.travellers[i as usize].depart_s += d;
        }
        st.moved += 1;
        st.mean_shift_s += d.abs() as f64;
    }
    st.mean_shift_s /= st.moved.max(1) as f64;
    st.at_window_edge = pop.travellers.iter().filter(|t| t.class & CLASS_FIXED == 0 && (t.depart_s - 300.0 < t.earliest_s || t.depart_s + 300.0 > t.latest_s)).count() as u64;
    st
}
