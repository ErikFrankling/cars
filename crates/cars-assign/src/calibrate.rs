//! Cell-level OD fit pulled toward the prior, with corridor-level splits, TAG limits on change, and
//! a stop at the noise floor. Counts validate. They do not identify OD.

use std::path::Path;

use cars_core::net::Net;
use rayon::prelude::*;
use rustc_hash::{FxHashMap, FxHashSet};
use serde::Serialize;

use crate::costs::{BIN_S, CostTable, DayCounts, NONE, Supply};
use crate::cuts::bisect;
use crate::population::{CLASS_FIXED, Population};
use crate::{mix, unit};

pub const SLICE_S: f32 = 1800.0;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Train,
    Selection,
    Test,
    /// Peak hours of training sites, held back from the fit.
    HeldPeak,
    /// Other held rows, such as another year.
    TestOther,
}

impl Role {
    pub fn name(&self) -> &'static str {
        match self {
            Role::Train => "train",
            Role::Selection => "selection",
            Role::Test => "test",
            Role::HeldPeak => "held_peak",
            Role::TestOther => "test_other",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "train" => Some(Role::Train),
            "selection" => Some(Role::Selection),
            "test" => Some(Role::Test),
            "held_peak" => Some(Role::HeldPeak),
            "test_other" => Some(Role::TestOther),
            _ => None,
        }
    }
}

#[derive(Clone, Debug)]
pub struct CountRow {
    pub site: u32,
    pub edge: u32,
    pub t0: f32,
    pub t1: f32,
    pub y: f32,
    pub role: Role,
    pub corridor: u32,
}

#[derive(Clone, Debug, Default)]
pub struct Counts {
    pub rows: Vec<CountRow>,
    pub sites: Vec<String>,
    pub rejected: FxHashMap<String, u64>,
}

impl Counts {
    /// `site, edge, dir, t0_s, t1_s, day_type, vehicles, class, source`, then optional `role, corridor`.
    /// Direction halved from a two-way flow and annual means with no day type are refused here, and an
    /// estimated source can never be test data.
    pub fn load(path: &Path, net: &Net, supply: &Supply) -> Result<Self, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
        let mut c = Counts::default();
        let mut site_ids: FxHashMap<String, u32> = FxHashMap::default();
        let mut corridors: FxHashMap<String, u32> = FxHashMap::default();
        for (i, line) in text.lines().enumerate() {
            if i == 0 || line.trim().is_empty() {
                continue;
            }
            let v: Vec<&str> = line.split(',').collect();
            if v.len() < 9 {
                return Err(format!("{}: line {} has {} columns", path.display(), i + 1, v.len()));
            }
            let mut reject = |why: &str| *c.rejected.entry(why.into()).or_insert(0) += 1;
            if v[2] == "halved" {
                reject("direction_halved");
                continue;
            }
            if v[5].is_empty() {
                reject("no_day_type");
                continue;
            }
            let Some(&e) = net.edge_index.get(v[1]) else {
                reject("unknown_edge");
                continue;
            };
            let d = supply.dense[e as usize];
            if d == NONE {
                reject("not_normal_edge");
                continue;
            }
            let role = v.get(9).and_then(|s| Role::parse(s)).unwrap_or(Role::Train);
            if v[8] == "estimated" && matches!(role, Role::Test | Role::TestOther | Role::Selection) {
                reject("estimated_as_validation");
                continue;
            }
            let n = site_ids.len() as u32;
            let site = *site_ids.entry(v[0].to_string()).or_insert_with(|| {
                c.sites.push(v[0].to_string());
                n
            });
            let name = v.get(10).filter(|s| !s.is_empty()).copied().unwrap_or(v[0]);
            let n = corridors.len() as u32;
            let corridor = *corridors.entry(name.to_string()).or_insert(n);
            c.rows.push(CountRow { site, edge: d, t0: v[3].parse().map_err(|_| format!("line {}", i + 1))?, t1: v[4].parse().map_err(|_| format!("line {}", i + 1))?, y: v[6].parse().map_err(|_| format!("line {}", i + 1))?, role, corridor });
        }
        Ok(c)
    }

    /// Freeze a split: counters joined within `join_m` along roads, whole clusters and named corridors
    /// together, then `train`, `selection`, `test` by hash. The hour from `peak.0` to `peak.1` of
    /// training sites is held back too.
    pub fn split(&mut self, net: &Net, supply: &Supply, join_m: f32, shares: (f64, f64), peak: (f32, f32), seed: u64) {
        let n = self.sites.len();
        let mut parent: Vec<u32> = (0..n as u32).collect();
        fn find(p: &mut [u32], mut x: u32) -> u32 {
            while p[x as usize] != x {
                p[x as usize] = p[p[x as usize] as usize];
                x = p[x as usize];
            }
            x
        }
        let mut site_edges: Vec<u32> = vec![NONE; n];
        let mut at_edge: FxHashMap<u32, Vec<u32>> = FxHashMap::default();
        let mut by_corridor: FxHashMap<u32, u32> = FxHashMap::default();
        let mut joins = Vec::new();
        for r in &self.rows {
            if site_edges[r.site as usize] == NONE {
                site_edges[r.site as usize] = r.edge;
                at_edge.entry(r.edge).or_default().push(r.site);
            }
            let first = *by_corridor.entry(r.corridor).or_insert(r.site);
            joins.push((first, r.site));
        }
        let succ = crate::cuts::successors(net, supply);
        let mut undirected = vec![Vec::new(); supply.n()];
        for (e, nx) in succ.iter().enumerate() {
            for &x in nx {
                undirected[e].push(x);
                undirected[x as usize].push(e as u32);
            }
        }
        for s in 0..n {
            let start = site_edges[s];
            if start == NONE {
                continue;
            }
            let mut seen: FxHashSet<u32> = FxHashSet::default();
            let mut stack = vec![(start, 0.0f32)];
            seen.insert(start);
            while let Some((e, d)) = stack.pop() {
                if let Some(list) = at_edge.get(&e) {
                    for &other in list {
                        joins.push((s as u32, other));
                    }
                }
                for &x in &undirected[e as usize] {
                    let nd = d + supply.length[x as usize];
                    if nd <= join_m && seen.insert(x) {
                        stack.push((x, nd));
                    }
                }
            }
        }
        for (a, b) in joins {
            let (x, y) = (find(&mut parent, a), find(&mut parent, b));
            parent[x as usize] = y;
        }
        let mut clusters: FxHashMap<u32, Vec<u32>> = FxHashMap::default();
        for s in 0..n as u32 {
            let root = find(&mut parent, s);
            clusters.entry(root).or_default().push(s);
        }
        let mut list: Vec<Vec<u32>> = clusters.into_values().collect();
        for l in &mut list {
            l.sort_unstable();
        }
        list.sort_by_key(|l| mix(seed, l[0] as u64));
        let mut role = vec![Role::Train; n];
        let mut taken = 0usize;
        for l in list {
            let at = taken as f64 / n.max(1) as f64;
            let r = if at < shares.0 {
                Role::Train
            } else if at < shares.0 + shares.1 {
                Role::Selection
            } else {
                Role::Test
            };
            for &s in &l {
                role[s as usize] = r;
            }
            taken += l.len();
        }
        for r in &mut self.rows {
            r.role = role[r.site as usize];
            if r.role == Role::Train && r.t0 < peak.1 && r.t1 > peak.0 {
                r.role = Role::HeldPeak;
            }
        }
    }

    pub fn write(&self, path: &Path, net: &Net, supply: &Supply) -> Result<(), String> {
        let mut s = String::from("site,edge,dir,t0_s,t1_s,day_type,vehicles,class,source,role,corridor\n");
        for r in &self.rows {
            s.push_str(&format!("{},{},measured,{},{},weekday,{},all,synthetic,{},c{}\n", self.sites[r.site as usize], net.edges[supply.normal[r.edge as usize] as usize].id, r.t0, r.t1, r.y, r.role.name(), r.corridor));
        }
        std::fs::write(path, s).map_err(|e| e.to_string())
    }
}

pub fn simulated(row: &CountRow, day: &DayCounts) -> f32 {
    let (b0, b1) = ((row.t0 / BIN_S) as usize, (row.t1 / BIN_S).ceil() as usize);
    let k = day.replicas.max(1) as f32;
    (b0..b1.min(day.n_bins)).map(|b| day.n_in[row.edge as usize * day.n_bins + b] as f32).sum::<f32>() / k
}

#[derive(Clone, Copy, Debug, Default, Serialize)]
pub struct CountError {
    pub rows: u64,
    pub observed: f64,
    pub simulated: f64,
    pub wape: f64,
    /// Share of hourly rows with GEH under 5.
    pub geh5: f64,
}

/// WAPE and GEH of one role. Hourly rows give the GEH its usual meaning.
pub fn count_error(rows: &[CountRow], role: Role, sim: impl Fn(&CountRow) -> f32) -> CountError {
    let (mut e, mut abs, mut geh) = (CountError::default(), 0.0f64, 0u64);
    for r in rows.iter().filter(|r| r.role == role) {
        let s = sim(r) as f64;
        let y = r.y as f64;
        e.rows += 1;
        e.observed += y;
        e.simulated += s;
        abs += (s - y).abs();
        let hours = ((r.t1 - r.t0) / 3600.0).max(1e-3) as f64;
        let (a, b) = (s / hours, y / hours);
        let g = if a + b > 0.0 { (2.0 * (a - b) * (a - b) / (a + b)).sqrt() } else { 0.0 };
        geh += u64::from(g < 5.0);
    }
    e.wape = abs / e.observed.max(1e-9);
    e.geh5 = geh as f64 / e.rows.max(1) as f64;
    e
}

/// `edge -> zone`, from a median bisection of all edges: `2^levels` zones.
pub fn zones(supply: &Supply, count: usize) -> Vec<u16> {
    bisect(supply, (count.max(2) as f64).log2().round() as u32)
}

/// Cell of a traveller: origin zone, destination zone, half hour.
pub fn cell_key(zone: &[u16], supply: &Supply, o: u32, d: u32, depart: f32) -> u64 {
    let (a, b) = (zone[supply.dense[o as usize] as usize] as u64, zone[supply.dense[d as usize] as usize] as u64);
    (a << 32) | (b << 16) | (depart / SLICE_S) as u64
}

/// Sparse assignment matrix over counted rows, as `(row, cell, passes per trip)`, plus the cell table.
pub struct Assignment {
    pub entries: Vec<(u32, u32, f32)>,
    pub cells: Vec<u64>,
    pub q: Vec<f64>,
    pub of_traveller: Vec<u32>,
}

pub fn build_assignment(pop: &Population, supply: &Supply, costs: &CostTable, zone: &[u16], rows: &[CountRow]) -> Assignment {
    let mut at_edge: FxHashMap<u32, Vec<u32>> = FxHashMap::default();
    for (i, r) in rows.iter().enumerate() {
        at_edge.entry(r.edge).or_default().push(i as u32);
    }
    let mut cell_index: FxHashMap<u64, u32> = FxHashMap::default();
    let mut cells = Vec::new();
    let mut q: Vec<f64> = Vec::new();
    let mut of_traveller = vec![NONE; pop.travellers.len()];
    for (i, t) in pop.travellers.iter().enumerate() {
        let key = cell_key(zone, supply, t.o_edge, t.d_edge, t.depart_s);
        let c = *cell_index.entry(key).or_insert_with(|| {
            cells.push(key);
            q.push(0.0);
            (cells.len() - 1) as u32
        });
        q[c as usize] += 1.0;
        of_traveller[i] = c;
    }
    let passes: Vec<(u32, u32)> = pop
        .travellers
        .par_iter()
        .enumerate()
        .flat_map_iter(|(i, t)| {
            let mut hits = Vec::new();
            let route: Vec<u32> = pop.demand.routes[t.route() as usize].iter().map(|&e| supply.dense[e as usize]).collect();
            costs.passage(&route, t.depart_s, |e, at| {
                if let Some(list) = at_edge.get(&e) {
                    for &r in list {
                        let row = &rows[r as usize];
                        if at >= row.t0 && at < row.t1 {
                            hits.push((r, of_traveller[i]));
                        }
                    }
                }
            });
            hits.into_iter()
        })
        .collect();
    let mut sum: FxHashMap<(u32, u32), f32> = FxHashMap::default();
    for p in passes {
        *sum.entry(p).or_insert(0.0) += 1.0;
    }
    let mut entries: Vec<(u32, u32, f32)> = sum.into_iter().map(|((r, c), n)| (r, c, n / q[c as usize] as f32)).collect();
    entries.sort_unstable_by_key(|e| (e.0, e.1));
    Assignment { entries, cells, q, of_traveller }
}

pub fn predict(a: &Assignment, q: &[f64], n_rows: usize) -> Vec<f64> {
    let mut p = vec![0.0f64; n_rows];
    for &(r, c, v) in &a.entries {
        p[r as usize] += v as f64 * q[c as usize];
    }
    p
}

/// `m = (Σ A_ij y_i / (Aq)_i + λ q0_j / q_j) / (Σ A_ij + λ)`, `q_j <- q_j m`, on the training rows only.
pub fn cell_fit(a: &Assignment, rows: &[CountRow], q0: &[f64], lambda: f64, sweeps: usize) -> Vec<f64> {
    let train: Vec<&(u32, u32, f32)> = a.entries.iter().filter(|e| rows[e.0 as usize].role == Role::Train).collect();
    let mut denom = vec![0.0f64; q0.len()];
    for e in &train {
        denom[e.1 as usize] += e.2 as f64;
    }
    let mut q = q0.to_vec();
    let mut pred = vec![0.0f64; rows.len()];
    for _ in 0..sweeps {
        pred.fill(0.0);
        for e in &train {
            pred[e.0 as usize] += e.2 as f64 * q[e.1 as usize];
        }
        let mut num = vec![0.0f64; q.len()];
        for e in &train {
            let r = e.0 as usize;
            if pred[r] > 0.0 {
                num[e.1 as usize] += e.2 as f64 * rows[r].y as f64 / pred[r];
            }
        }
        for j in 0..q.len() {
            if q[j] > 0.0 && q0[j] > 0.0 {
                let m = (num[j] + lambda * q0[j] / q[j]) / (denom[j] + lambda);
                q[j] *= m;
            }
        }
    }
    q
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Guards {
    pub cell_slope: f64,
    pub cell_intercept: f64,
    pub cell_r2: f64,
    pub ends_slope: f64,
    pub ends_r2: f64,
    pub length_mean_ratio: f64,
    pub length_sd_ratio: f64,
    pub sector_max_change: f64,
    pub total_ratio: f64,
    pub vkm_ratio: f64,
    pub pass: bool,
}

fn regress(x: &[f64], y: &[f64]) -> (f64, f64, f64) {
    let n = x.len() as f64;
    let (mx, my) = (x.iter().sum::<f64>() / n, y.iter().sum::<f64>() / n);
    let (mut sxx, mut sxy, mut syy) = (0.0, 0.0, 0.0);
    for (a, b) in x.iter().zip(y) {
        sxx += (a - mx) * (a - mx);
        sxy += (a - mx) * (b - my);
        syy += (b - my) * (b - my);
    }
    let slope = sxy / sxx.max(1e-12);
    (slope, my - slope * mx, if syy > 0.0 { sxy * sxy / (sxx * syy) } else { 1.0 })
}

/// TAG M3.1 Table 5 as the default limit on change from the prior.
pub fn guards(cells: &[u64], q0: &[f64], q: &[f64], mean_len: &[f64]) -> Guards {
    let (cell_slope, cell_intercept, cell_r2) = regress(q0, q);
    let (mut p0, mut p1): (FxHashMap<u64, f64>, FxHashMap<u64, f64>) = Default::default();
    let (mut sec0, mut sec1): (FxHashMap<(u64, u64), f64>, FxHashMap<(u64, u64), f64>) = Default::default();
    for (i, &c) in cells.iter().enumerate() {
        let (o, d) = (c >> 32, (c >> 16) & 0xffff);
        for (key, v0, v1) in [(o * 2, q0[i], q[i]), (d * 2 + 1, q0[i], q[i])] {
            *p0.entry(key).or_insert(0.0) += v0;
            *p1.entry(key).or_insert(0.0) += v1;
        }
        // Eight sectors out of however many zones: the high bits of the bisection label.
        let bits = 64 - (cells.iter().map(|c| c >> 32).max().unwrap_or(0)).leading_zeros() as i64 - 3;
        let shift = bits.max(0) as u64;
        let sec = (o >> shift, d >> shift);
        *sec0.entry(sec).or_insert(0.0) += q0[i];
        *sec1.entry(sec).or_insert(0.0) += q[i];
    }
    let keys: Vec<u64> = p0.keys().copied().collect();
    let x: Vec<f64> = keys.iter().map(|k| p0[k]).collect();
    let y: Vec<f64> = keys.iter().map(|k| p1[k]).collect();
    let (ends_slope, _, ends_r2) = regress(&x, &y);
    let stats = |w: &[f64]| {
        let total: f64 = w.iter().sum();
        let mean = w.iter().zip(mean_len).map(|(a, l)| a * l).sum::<f64>() / total.max(1e-9);
        let var = w.iter().zip(mean_len).map(|(a, l)| a * (l - mean) * (l - mean)).sum::<f64>() / total.max(1e-9);
        (total, mean, var.sqrt())
    };
    let (t0, m0, s0) = stats(q0);
    let (t1, m1, s1) = stats(q);
    let sector_max_change = sec0.iter().filter(|(_, v)| **v > 50.0).map(|(k, v)| (sec1[k] / v - 1.0).abs()).fold(0.0, f64::max);
    let mut g = Guards {
        cell_slope,
        cell_intercept,
        cell_r2,
        ends_slope,
        ends_r2,
        length_mean_ratio: m1 / m0.max(1e-9),
        length_sd_ratio: if s0 > 1e-6 { s1 / s0 } else { 1.0 },
        sector_max_change,
        total_ratio: t1 / t0.max(1e-9),
        vkm_ratio: (t1 * m1) / (t0 * m0).max(1e-9),
        pass: false,
    };
    g.pass = (0.98..=1.02).contains(&g.cell_slope)
        && g.cell_r2 > 0.95
        && (0.99..=1.01).contains(&g.ends_slope)
        && g.ends_r2 > 0.98
        && (g.length_mean_ratio - 1.0).abs() <= 0.05
        && (g.length_sd_ratio - 1.0).abs() <= 0.05
        && g.sector_max_change <= 0.05;
    g
}

/// Add or remove travellers by Poisson-sampling each cell's change. Clones keep the plan. A cell with no
/// prior trips is a structural zero. Returns (added, removed).
pub fn apply_cells(pop: &mut Population, a: &Assignment, q_new: &[f64], seed: u64) -> (u64, u64) {
    let mut members: Vec<Vec<u32>> = vec![Vec::new(); a.cells.len()];
    for (i, &c) in a.of_traveller.iter().enumerate() {
        if pop.travellers[i].class & CLASS_FIXED == 0 {
            members[c as usize].push(i as u32);
        }
    }
    let mut remove = vec![false; pop.travellers.len()];
    let (mut added, mut removed) = (0u64, 0u64);
    let mut clones = Vec::new();
    let mut next_id = pop.travellers.iter().map(|t| t.id).max().unwrap_or(0) + 1;
    let poisson = |mean: f64, s: u64| -> u64 {
        // Knuth under 30, normal above: only the rounding of a cell's change matters.
        if mean <= 0.0 {
            return 0;
        }
        if mean > 30.0 {
            let (u1, u2) = (unit(s, 1).max(1e-12), unit(s, 2));
            return (mean + mean.sqrt() * (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos()).round().max(0.0) as u64;
        }
        let limit = (-mean).exp();
        let (mut k, mut p) = (0u64, 1.0);
        loop {
            p *= unit(s, 100 + k);
            if p <= limit {
                return k;
            }
            k += 1;
        }
    };
    for (j, list) in members.iter().enumerate() {
        if list.is_empty() {
            continue;
        }
        let change = q_new[j] - list.len() as f64;
        let n = poisson(change.abs(), mix(seed, j as u64));
        if change > 0.0 {
            for c in 0..n {
                let src = list[(mix(seed ^ 0xC10, (j as u64) << 20 | c) % list.len() as u64) as usize];
                let mut t = pop.travellers[src as usize];
                t.id = next_id;
                next_id += 1;
                t.tour = t.id;
                let jitter = (unit(seed ^ 0xD3, t.id as u64) as f32 - 0.5) * 600.0;
                t.depart_s = (t.depart_s + jitter).max(0.0);
                t.earliest_s = (t.earliest_s + jitter).max(0.0);
                t.latest_s += jitter;
                t.desired_arrival_s += jitter;
                clones.push(t);
                added += 1;
            }
        } else {
            let mut order = list.clone();
            order.sort_unstable_by_key(|&i| mix(seed ^ 0xE7, i as u64));
            for &i in order.iter().take((n as usize).min(list.len())) {
                remove[i as usize] = true;
                removed += 1;
            }
        }
    }
    let mut i = 0usize;
    pop.travellers.retain(|_| {
        let keep = !remove[i];
        i += 1;
        keep
    });
    pop.travellers.extend(clones);
    (added, removed)
}
