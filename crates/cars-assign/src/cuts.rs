//! Directed cut checks. Single-commodity max flow never flags the impossible case, because it lets
//! opposite directions cancel. A directional bound does.

use std::collections::VecDeque;
use std::path::Path;

use cars_core::net::Net;
use rustc_hash::{FxHashMap, FxHashSet};
use serde::Serialize;

use crate::costs::{BIN_S, DayCounts, NONE, Supply};
use crate::population::Population;

const SIDE_NONE: u16 = u16::MAX;
/// Space one queued car takes, in metres of lane.
pub const QUEUE_SPACING: f32 = 7.5;

/// A set of edges on one side, and the edges carrying traffic out of and into it.
#[derive(Clone, Debug)]
pub struct Cut {
    pub name: String,
    pub side: Vec<bool>,
    /// Edges on neither side: the bridges themselves, in a named cut.
    pub out_edges: Vec<u32>,
    pub in_edges: Vec<u32>,
    /// Trips ending on these edges count as on neither side when false.
    pub other: Vec<bool>,
}

/// Directed successors over dense edges, whatever class may use them.
pub fn successors(net: &Net, supply: &Supply) -> Vec<Vec<u32>> {
    let mut out = vec![Vec::new(); supply.n()];
    for c in &net.conns {
        let (a, b) = (supply.dense[c.from_edge as usize], supply.dense[c.to_edge as usize]);
        if a != NONE && b != NONE && !out[a as usize].contains(&b) {
            out[a as usize].push(b);
        }
    }
    out
}

/// Recursive median bisection of edge midpoints: `2^levels` clusters, returned per edge.
pub fn bisect(supply: &Supply, levels: u32) -> Vec<u16> {
    let mut label = vec![0u16; supply.n()];
    fn split(idx: &mut [u32], mid: &[[f32; 2]], level: u32, base: u16, label: &mut [u16]) {
        if level == 0 {
            for &i in idx.iter() {
                label[i as usize] = base;
            }
            return;
        }
        let (mut lo, mut hi) = ([f32::MAX; 2], [f32::MIN; 2]);
        for &i in idx.iter() {
            for k in 0..2 {
                lo[k] = lo[k].min(mid[i as usize][k]);
                hi[k] = hi[k].max(mid[i as usize][k]);
            }
        }
        let axis = usize::from(hi[1] - lo[1] > hi[0] - lo[0]);
        let m = idx.len() / 2;
        idx.select_nth_unstable_by(m, |&a, &b| mid[a as usize][axis].total_cmp(&mid[b as usize][axis]));
        let (a, b) = idx.split_at_mut(m);
        split(a, mid, level - 1, base * 2, label);
        split(b, mid, level - 1, base * 2 + 1, label);
    }
    let mut idx: Vec<u32> = (0..supply.n() as u32).collect();
    split(&mut idx, &supply.mid, levels, 0, &mut label);
    label
}

impl Cut {
    /// One side is `side`; everything else is the other.
    pub fn from_set(name: String, side: Vec<bool>, succ: &[Vec<u32>]) -> Self {
        let mut out_edges = Vec::new();
        let mut in_edges = Vec::new();
        for (e, next) in succ.iter().enumerate() {
            let inside = side[e];
            if next.iter().any(|&n| side[n as usize] != inside) {
                if inside {
                    out_edges.push(e as u32);
                } else {
                    in_edges.push(e as u32);
                }
            }
        }
        let other = side.iter().map(|x| !x).collect();
        Self { name, side, out_edges, in_edges, other }
    }
}

/// The cluster family at k = 2, 4, 8, 16: every cluster's boundary, both ways.
pub fn cluster_cuts(supply: &Supply, succ: &[Vec<u32>]) -> Vec<Cut> {
    let mut cuts = Vec::new();
    for level in 1..=4u32 {
        let label = bisect(supply, level);
        let k = 1u16 << level;
        // Two clusters at k = 2 are the same cut seen from both sides.
        let clusters = if level == 1 { 1 } else { k };
        for c in 0..clusters {
            let side: Vec<bool> = label.iter().map(|&l| l == c).collect();
            cuts.push(Cut::from_set(format!("k{k}_c{c}"), side, succ));
        }
    }
    cuts
}

/// Rivers and rings from `cuts.csv` (`cut, edge, dir`). Whichever directions the file lists are
/// removed, and the weak components of the rest make the two sides.
pub fn load_named_cuts(path: &Path, net: &Net, supply: &Supply, succ: &[Vec<u32>]) -> Result<Vec<Cut>, String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut by_name: FxHashMap<String, Vec<u32>> = FxHashMap::default();
    for (i, line) in text.lines().enumerate() {
        if i == 0 || line.trim().is_empty() {
            continue;
        }
        let v: Vec<&str> = line.split(',').collect();
        if v.len() < 2 {
            return Err(format!("cuts line {}: too few columns", i + 1));
        }
        let e = *net.edge_index.get(v[1]).ok_or_else(|| format!("cuts line {}: unknown edge {}", i + 1, v[1]))?;
        by_name.entry(v[0].to_string()).or_default().push(supply.dense[e as usize]);
    }
    let mut names: Vec<_> = by_name.keys().cloned().collect();
    names.sort();
    Ok(names.into_iter().flat_map(|name| named_cut(&name, &by_name[&name], succ)).collect())
}

fn named_cut(name: &str, edges: &[u32], succ: &[Vec<u32>]) -> Vec<Cut> {
    let n = succ.len();
    let removed: FxHashSet<u32> = edges.iter().copied().collect();
    let mut undirected = vec![Vec::new(); n];
    for (e, next) in succ.iter().enumerate() {
        for &x in next {
            if !removed.contains(&(e as u32)) && !removed.contains(&x) {
                undirected[e].push(x);
                undirected[x as usize].push(e as u32);
            }
        }
    }
    let mut comp = vec![SIDE_NONE; n];
    let mut sizes = Vec::new();
    for s in 0..n {
        if comp[s] != SIDE_NONE || removed.contains(&(s as u32)) {
            continue;
        }
        let id = sizes.len() as u16;
        let mut size = 0usize;
        let mut q = VecDeque::from([s as u32]);
        comp[s] = id;
        while let Some(e) = q.pop_front() {
            size += 1;
            for &x in &undirected[e as usize] {
                if comp[x as usize] == SIDE_NONE {
                    comp[x as usize] = id;
                    q.push_back(x);
                }
            }
        }
        sizes.push(size);
    }
    // Only sizable components are real sides: dead-end stubs next to a bridge are not.
    let big = sizes.iter().copied().max().unwrap_or(0) / 50;
    let sides: Vec<u16> = sizes.iter().enumerate().filter(|(_, s)| **s > big.max(1)).map(|(i, _)| i as u16).collect();
    let mut cuts = Vec::new();
    for (j, &a) in sides.iter().enumerate() {
        if sides.len() == 2 && j == 1 {
            break;
        }
        let side: Vec<bool> = comp.iter().map(|&c| c == a).collect();
        let other: Vec<bool> = comp.iter().map(|&c| c != a && c != SIDE_NONE && sides.contains(&c)).collect();
        // A cut edge leads out if something on this side feeds it.
        let mut out_edges = Vec::new();
        let mut in_edges = Vec::new();
        for &e in edges {
            let fed_from_side = succ.iter().enumerate().any(|(u, nx)| side[u] && nx.contains(&e));
            if fed_from_side {
                out_edges.push(e);
            } else {
                in_edges.push(e);
            }
        }
        cuts.push(Cut { name: format!("{name}_{j}"), side, out_edges, in_edges, other });
    }
    cuts
}

/// Sets of edges queued for at least `min_bins` in a row, joined when connected.
pub fn queued_sets(supply: &Supply, day: &DayCounts, succ: &[Vec<u32>], min_bins: usize) -> Vec<Vec<u32>> {
    let n_bins = day.n_bins;
    let k = day.replicas.max(1) as f32;
    let mut queued = vec![false; supply.n()];
    for (e, flag) in queued.iter_mut().enumerate() {
        let storage = supply.length[e] * supply.lanes[e] as f32 / QUEUE_SPACING;
        let (mut cum_in, mut cum_out, mut run) = (0.0f32, 0.0f32, 0usize);
        for b in 0..day.end_bin.min(n_bins) {
            cum_in += day.n_in[e * n_bins + b] as f32 / k;
            cum_out += day.left[e * n_bins + b] as f32 / k;
            run = if cum_in - cum_out > 0.5 * storage.max(2.0) { run + 1 } else { 0 };
            if run >= min_bins {
                *flag = true;
                break;
            }
        }
    }
    let mut seen = vec![false; supply.n()];
    let mut undirected: Vec<Vec<u32>> = vec![Vec::new(); supply.n()];
    for (e, next) in succ.iter().enumerate() {
        if queued[e] {
            for &x in next {
                if queued[x as usize] {
                    undirected[e].push(x);
                    undirected[x as usize].push(e as u32);
                }
            }
        }
    }
    let mut sets = Vec::new();
    for s in 0..supply.n() {
        if !queued[s] || seen[s] {
            continue;
        }
        let mut set = Vec::new();
        let mut q = VecDeque::from([s as u32]);
        seen[s] = true;
        while let Some(e) = q.pop_front() {
            set.push(e);
            for &x in &undirected[e as usize] {
                if !seen[x as usize] {
                    seen[x as usize] = true;
                    q.push_back(x);
                }
            }
        }
        if set.len() >= 3 {
            sets.push(set);
        }
    }
    sets.sort_by_key(|s| std::cmp::Reverse(s.len()));
    sets.truncate(32);
    sets
}

/// Measured discharge per edge, veh/s, where a test or a queued day has one.
#[derive(Clone, Default)]
pub struct Discharge {
    pub measured: FxHashMap<u32, f32>,
    pub observed: Vec<f32>,
}

impl Discharge {
    pub fn load(path: &Path, net: &Net, supply: &Supply) -> Result<FxHashMap<u32, f32>, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
        let mut m = FxHashMap::default();
        for (i, line) in text.lines().enumerate() {
            let v: Vec<&str> = line.split(',').collect();
            if i == 0 || v.len() < 2 {
                continue;
            }
            if let (Some(&e), Ok(r)) = (net.edge_index.get(v[0]), v[1].parse::<f32>()) {
                m.insert(supply.dense[e as usize], r);
            }
        }
        Ok(m)
    }

    /// Highest 5-minute outflow per edge on a day.
    pub fn from_day(day: &DayCounts) -> Vec<f32> {
        let k = day.replicas.max(1) as f32;
        (0..day.n_edges).map(|e| (0..day.n_bins).map(|b| day.left[e * day.n_bins + b]).max().unwrap_or(0) as f32 / k / BIN_S).collect()
    }

    /// Measured in isolation if tested. Otherwise the larger of what the day showed and half the
    /// nominal screen, which still lets a badly used link count for something.
    pub fn rate(&self, supply: &Supply, e: u32) -> f32 {
        if let Some(&r) = self.measured.get(&e) {
            return r;
        }
        let seen = self.observed.get(e as usize).copied().unwrap_or(0.0);
        seen.max(0.5 * supply.nominal_capacity(e as usize))
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct CutReport {
    pub name: String,
    pub direction: String,
    pub links: usize,
    pub capacity_veh_h: f64,
    pub storage_veh: f64,
    pub must_cross: u64,
    pub peak_1h_crossing: u64,
    pub peak_1h_start_s: f32,
    /// Trips over capacity and storage in the worst hour.
    pub shortfall_1h: f64,
    /// Trips that cannot cross by the horizon at all.
    pub min_unmet: f64,
    pub violated: bool,
}

/// Trips that must cross, by direction, in a sliding 1 hour window against capacity and the storage of the cut links.
pub fn check_cut(cut: &Cut, pop: &Population, supply: &Supply, discharge: &Discharge, begin: f32, horizon: f32) -> Vec<CutReport> {
    let mut reports = Vec::new();
    for (dir, edges, from_side) in [("out", &cut.out_edges, true), ("in", &cut.in_edges, false)] {
        if edges.is_empty() {
            continue;
        }
        let cap: f64 = edges.iter().map(|&e| discharge.rate(supply, e) as f64).sum();
        let storage: f64 = edges.iter().map(|&e| (supply.length[e as usize] * supply.lanes[e as usize] as f32 / QUEUE_SPACING) as f64).sum();
        let mut deps: Vec<f32> = pop
            .travellers
            .iter()
            .filter(|t| {
                let (o, d) = (supply.dense[t.o_edge as usize] as usize, supply.dense[t.d_edge as usize] as usize);
                if from_side { cut.side[o] && cut.other[d] } else { cut.other[o] && cut.side[d] }
            })
            .map(|t| t.depart_s)
            .collect();
        deps.sort_unstable_by(f32::total_cmp);
        let (mut peak, mut peak_at, mut j) = (0usize, 0.0f32, 0usize);
        for i in 0..deps.len() {
            while deps[i] - deps[j] > 3600.0 {
                j += 1;
            }
            if i + 1 - j > peak {
                peak = i + 1 - j;
                peak_at = deps[j];
            }
        }
        let shortfall = (peak as f64 - cap * 3600.0 - storage).max(0.0);
        let unmet = (deps.len() as f64 - cap * (horizon - begin) as f64).max(0.0);
        reports.push(CutReport {
            name: cut.name.clone(),
            direction: dir.into(),
            links: edges.len(),
            capacity_veh_h: cap * 3600.0,
            storage_veh: storage,
            must_cross: deps.len() as u64,
            peak_1h_crossing: peak as u64,
            peak_1h_start_s: peak_at,
            shortfall_1h: shortfall,
            min_unmet: unmet,
            violated: shortfall > 0.0,
        });
    }
    reports
}

/// Network flow per direction of each screenline, per simulated day: held back from fitting.
pub fn screenline_flows(cuts: &[Cut], day: &DayCounts) -> Vec<f64> {
    let k = day.replicas.max(1) as f64;
    let mut out = Vec::new();
    let day_flow = |e: u32| -> f64 { (0..day.n_bins).map(|b| day.n_in[e as usize * day.n_bins + b] as f64).sum::<f64>() / k };
    for c in cuts {
        out.push(c.out_edges.iter().map(|&e| day_flow(e)).sum());
        out.push(c.in_edges.iter().map(|&e| day_flow(e)).sum());
    }
    out
}
