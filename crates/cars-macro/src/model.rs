use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::Write;
use std::time::Instant;

use rayon::prelude::*;
use rustc_hash::{FxHashMap, FxHasher};
use std::hash::{Hash, Hasher};

const NONE: u32 = u32::MAX;
const X_CAP: f32 = 3.0;

pub struct Params {
    pub dynamic: bool,
    pub hours: Vec<u32>,
    pub iters: usize,
    pub s: f32,
    pub rule_greens: bool,
    pub green_scale: f32,
    pub sigma: f32,
    pub reroute: u64,
    pub period: f32,
    pub demand_mult: f32,
    pub beta_mult: f32,
    pub retime_every: usize,
    pub save_paths: bool,
}

struct Edge {
    id: String,
    len: f32,
    v: f32,
    lanes: f32,
    motorway: bool,
    beta: f32,
    mask: u8,
    rev: u32,
    midblock: f32,
}

struct Conn {
    arc: u32,
    lane: u32,
    kind: u8, // 0 no foes, 1 signal, 2 give-way, 3 merge
    ctrl: u32,
    idx: u32,
    f: f32,
    tg: f32,
    tf: f32,
    foes: Vec<u32>,
    foe_yield: Vec<u32>,
}

struct Arc {
    from: u32,
    to: u32,
    mask: u8,
    group: u32,
    uturn: bool,
}

struct Ctrl {
    phases: Vec<(f32, Vec<u8>)>,
}

struct Leg {
    o: u32,
    d: u32,
    dep: f32,
    bit: u8,
    pce: f32,
    w: f32,
}

#[derive(Clone)]
struct LegState {
    paths: Vec<(u32, f32)>,
    n: u32,
}

pub struct Net {
    edges: Vec<Edge>,
    arcs: Vec<Arc>,
    first: Vec<u32>,
    conns: Vec<Conn>,
    ctrls: Vec<Ctrl>,
    n_groups: usize,
    group_conns: Vec<Vec<u32>>,
    group_arcs: Vec<Vec<u32>>,
    in_arcs: Vec<Vec<u32>>,
}

fn tsv(path: &str) -> Vec<Vec<String>> {
    std::fs::read_to_string(path).unwrap_or_else(|e| panic!("{path}: {e}")).lines().skip(1).map(|l| l.split('\t').map(str::to_string).collect()).collect()
}

fn ids(s: &str) -> Vec<u32> {
    s.split(' ').filter(|x| !x.is_empty()).map(|x| x.parse().unwrap()).collect()
}

fn load_net(dir: &str) -> Net {
    let edges: Vec<Edge> = tsv(&format!("{dir}/edges.tsv"))
        .into_iter()
        .map(|r| Edge { id: r[0].clone(), len: r[1].parse().unwrap(), v: r[2].parse().unwrap(), lanes: r[3].parse().unwrap(), motorway: r[4] == "1", beta: r[5].parse().unwrap(), mask: r[6].parse().unwrap(), rev: r[7].parse::<i64>().map(|x| if x < 0 { NONE } else { x as u32 }).unwrap(), midblock: r[8].parse().unwrap() })
        .collect();
    let mut arcs: Vec<(u32, Arc)> = tsv(&format!("{dir}/arcs.tsv")).into_iter().map(|r| (r[0].parse().unwrap(), Arc { from: r[1].parse().unwrap(), to: r[2].parse().unwrap(), mask: r[3].parse().unwrap(), group: r[4].parse().unwrap(), uturn: r[5] == "1" })).collect();
    arcs.sort_by_key(|x| x.0);
    let arcs: Vec<Arc> = arcs.into_iter().map(|x| x.1).collect();
    // arcs arrive sorted by from edge: prepare.py guarantees it
    let mut first = vec![0u32; edges.len() + 1];
    for a in &arcs {
        first[a.from as usize + 1] += 1;
    }
    for i in 0..edges.len() {
        first[i + 1] += first[i];
    }
    let conns: Vec<Conn> = tsv(&format!("{dir}/conns.tsv")).into_iter().map(|r| Conn { arc: r[0].parse().unwrap(), lane: r[1].parse().unwrap(), kind: r[2].parse().unwrap(), ctrl: r[3].parse::<i64>().map(|x| if x < 0 { NONE } else { x as u32 }).unwrap(), idx: r[4].parse::<i64>().unwrap().max(0) as u32, f: r[5].parse().unwrap(), tg: r[6].parse().unwrap(), tf: r[7].parse().unwrap(), foes: ids(r.get(8).map(|s| s.as_str()).unwrap_or("")), foe_yield: ids(r.get(9).map(|s| s.as_str()).unwrap_or("")) }).collect();
    let mut ctrls: Vec<Ctrl> = Vec::new();
    for r in tsv(&format!("{dir}/ctrls.tsv")) {
        let c: usize = r[0].parse().unwrap();
        while ctrls.len() <= c {
            ctrls.push(Ctrl { phases: Vec::new() });
        }
        ctrls[c].phases.push((r[1].parse().unwrap(), r[2].as_bytes().to_vec()));
    }
    let n_groups = arcs.iter().map(|a| a.group as usize + 1).max().unwrap_or(0);
    let mut group_conns = vec![Vec::new(); n_groups];
    for (i, c) in conns.iter().enumerate() {
        group_conns[arcs[c.arc as usize].group as usize].push(i as u32);
    }
    let mut group_arcs = vec![Vec::new(); n_groups];
    let mut in_arcs = vec![Vec::new(); edges.len()];
    for (i, a) in arcs.iter().enumerate() {
        group_arcs[a.group as usize].push(i as u32);
        in_arcs[a.to as usize].push(i as u32);
    }
    Net { edges, arcs, first, conns, ctrls, n_groups, group_conns, group_arcs, in_arcs }
}

/// Supply per period: what the loaded flows imply for delay on each arc.
struct Supply {
    p: usize,
    delay: Vec<f32>,    // arc, period: at the stop line, seconds
    run: Vec<f32>,      // edge, period: running time
    x: Vec<f32>,        // group, period
    cap_g: Vec<f32>,    // group, period: veh/h
    res: Vec<f32>,      // group, period: queue at the end of the period, veh
    gc: Vec<f32>,       // conn, block: green share
    prot: Vec<f32>,     // conn, block seconds
    perm: Vec<f32>,     // conn, block seconds
    cyc: Vec<f32>,      // conn, block
    res_e: Vec<f32>,    // edge, period: queue to enter the edge
}

const BLOCKS: usize = 4;
fn block_of_hour(h: f32) -> usize {
    if (6.0..10.0).contains(&h) {
        0
    } else if (10.0..15.0).contains(&h) {
        1
    } else if (15.0..19.0).contains(&h) {
        2
    } else {
        3
    }
}

fn cycle_of_block(_b: usize, hour_is_day: bool) -> f32 {
    if hour_is_day { 90.0 } else { 75.0 }
}

fn siegloch(qp: f32, tg: f32, tf: f32) -> f32 {
    3600.0 / tf * (-(qp / 3600.0) * (tg - tf / 2.0)).exp()
}

/// Greens per connection and block. Rule fixed in macro-log.md: map's stages, equal degree of saturation on macro's flows, cycle by time of day.
fn retime(net: &Net, sup: &mut Supply, flow: &[f32], periods_of_block: &[Vec<usize>], s: f32, rule: bool, scale: f32) {
    let na = net.arcs.len();
    let nc = net.conns.len();
    let mut per_ctrl: Vec<Vec<u32>> = vec![Vec::new(); net.ctrls.len()];
    for (i, c) in net.conns.iter().enumerate() {
        if c.ctrl != NONE {
            per_ctrl[c.ctrl as usize].push(i as u32);
        }
    }
    let lanes_of_arc = {
        let mut v = vec![0f32; na];
        for c in &net.conns {
            v[c.arc as usize] += 1.0;
        }
        v
    };
    for b in 0..BLOCKS {
        // peak flow per arc in the block, veh/h
        let mut q = vec![0f32; na];
        for &p in &periods_of_block[b] {
            for a in 0..na {
                q[a] = q[a].max(flow[p * na + a]);
            }
        }
        let cycle_target = cycle_of_block(b, b != 3);
        for (ci, ctrl) in net.ctrls.iter().enumerate() {
            // real stages hold for more than a transition; transitions keep their map length and carry the lost time (B 5.2: G + 3 - 4)
            let is_green = |p: usize| ctrl.phases[p].1.iter().any(|&x| x == b'G' || x == b'g');
            let stages: Vec<usize> = (0..ctrl.phases.len()).filter(|&p| is_green(p) && ctrl.phases[p].0 > 5.0).collect();
            if stages.is_empty() {
                continue;
            }
            let map_c: f32 = ctrl.phases.iter().map(|x| x.0).sum();
            let fixed: f32 = (0..ctrl.phases.len()).filter(|p| !stages.contains(p)).map(|p| ctrl.phases[p].0).sum();
            let mut g: Vec<f32> = ctrl.phases.iter().map(|x| x.0).collect();
            let cyc = if rule { cycle_target } else { map_c };
            if rule {
                let mut y = vec![0f32; ctrl.phases.len()];
                for &cc in &per_ctrl[ci] {
                    let c = &net.conns[cc as usize];
                    let greens: Vec<usize> = stages.iter().copied().filter(|&p| matches!(ctrl.phases[p].1.get(c.idx as usize), Some(b'G') | Some(b'g'))).collect();
                    if greens.len() == 1 {
                        let r = q[c.arc as usize] / lanes_of_arc[c.arc as usize].max(1.0) / (s * c.f);
                        y[greens[0]] = y[greens[0]].max(r);
                    }
                }
                let green_total = (cyc - fixed).max(7.0 * stages.len() as f32);
                let tot: f32 = y.iter().sum();
                let spare = green_total - 7.0 * stages.len() as f32;
                let map_g: f32 = stages.iter().map(|&p| ctrl.phases[p].0).sum();
                for &p in &stages {
                    let share = if tot > 1e-3 { y[p] / tot } else { ctrl.phases[p].0 / map_g.max(1.0) };
                    g[p] = 7.0 + spare * share;
                }
            }
            for &cc in &per_ctrl[ci] {
                let c = &net.conns[cc as usize];
                let (mut pr, mut pe) = (0f32, 0f32);
                let n = ctrl.phases.len();
                let mut on = vec![false; n];
                for p in 0..n {
                    match ctrl.phases[p].1.get(c.idx as usize) {
                        Some(b'G') => {
                            pr += g[p];
                            on[p] = true;
                        }
                        Some(b'g') => {
                            pe += g[p];
                            on[p] = true;
                        }
                        _ => {}
                    }
                }
                let st = (0..n).filter(|&i| !on[i] && on[(i + 1) % n]).count().max(1) as f32;
                let t = pr + pe;
                if t > 0.0 {
                    let eff = ((t - st) / t).max(0.0);
                    pr *= eff;
                    pe *= eff;
                }
                let i = cc as usize * BLOCKS + b;
                sup.prot[i] = pr * scale;
                sup.perm[i] = pe * scale;
                sup.cyc[i] = cyc;
                sup.gc[i] = (pr + pe) * scale / cyc;
            }
        }
    }
    let _ = nc;
}

/// Capacity of each connection, min-max lane use per group, delays. `flow`: veh/h per arc and period, in PCE. `first_pass`: no queue carried.
fn update_supply(net: &Net, sup: &mut Supply, flow: &[f32], block_of_period: &[usize], t_h: f32, s: f32, dynamic: bool, alpha: f32) {
    let na = net.arcs.len();
    let ne = net.edges.len();
    let ng = net.n_groups;
    let p_n = sup.p;
    let mut new_delay = vec![0f32; p_n * na];
    let mut new_x = vec![0f32; p_n * ng];
    let mut new_cap = vec![0f32; p_n * ng];
    let mut new_res = vec![0f32; p_n * ng];
    let results: Vec<(Vec<f32>, Vec<f32>, Vec<f32>)> = (0..p_n)
        .into_par_iter()
        .map(|p| {
            let q = &flow[p * na..(p + 1) * na];
            let b = block_of_period[p];
            let mut d = vec![0f32; na];
            let mut xg = vec![0f32; ng];
            let mut cg = vec![0f32; ng];
            // single-lane capacity by connection; rank-3 impedance uses the previous pass's x
            let mut caps = vec![0f32; net.conns.len()];
            for (i, c) in net.conns.iter().enumerate() {
                let e = &net.edges[net.arcs[c.arc as usize].from as usize];
                let qp: f32 = c.foes.iter().map(|&f| q[f as usize]).sum();
                let vcap = e.midblock * c.f;
                caps[i] = match c.kind {
                    1 => {
                        let j = i * BLOCKS + b;
                        let (gp, gq, cy) = (sup.prot[j], sup.perm[j], sup.cyc[j].max(1.0));
                        let sat = (s * c.f).min(e.midblock);
                        let mut cap = sat * gp / cy;
                        if gq > 0.0 {
                            let qg = qp * cy / (gp + gq).max(1.0);
                            cap += gq / cy * sat.min(siegloch(qg, c.tg, c.tf));
                            cap += 3600.0 / cy * 2.0; // sneakers per cycle
                        }
                        cap
                    }
                    2 => {
                        let mut p0 = 1.0f32;
                        for &f in &c.foe_yield {
                            let g = net.arcs[f as usize].group as usize;
                            let xprev = sup.x[p * ng + g];
                            p0 *= (1.0 - xprev).clamp(0.1, 1.0);
                        }
                        vcap.min(siegloch(qp, c.tg, c.tf) * p0).max(15.0)
                    }
                    3 => (vcap - qp / 2.0).max(0.4 * vcap),
                    _ => vcap,
                };
            }
            for g in 0..ng {
                let conns = &net.group_conns[g];
                let moves = &net.group_arcs[g];
                if conns.is_empty() {
                    continue;
                }
                // lanes: small vector of (lane, arc, cap, x)
                let mut items: Vec<(u32, u32, f32, f32)> = conns.iter().map(|&c| (net.conns[c as usize].lane, net.conns[c as usize].arc, caps[c as usize].max(1.0), 0.0)).collect();
                // one lane appears once per movement: keep the best
                items.sort_by(|a, b| (a.0, a.1).cmp(&(b.0, b.1)).then(b.2.total_cmp(&a.2)));
                items.dedup_by(|a, b| a.0 == b.0 && a.1 == b.1);
                let mut lanes: Vec<u32> = items.iter().map(|x| x.0).collect();
                lanes.sort_unstable();
                lanes.dedup();
                let total: f32 = moves.iter().map(|&m| q[m as usize]).sum();
                // capacity with no flow: sum over lanes of best movement
                let empty_cap: f32 = lanes.iter().map(|l| items.iter().filter(|x| x.0 == *l).map(|x| x.2).fold(0.0, f32::max)).sum();
                if total <= 0.01 {
                    cg[g] = empty_cap;
                    xg[g] = 0.0;
                } else {
                    for &m in moves.iter() {
                        let n = items.iter().filter(|x| x.1 == m).count().max(1) as f32;
                        for it in items.iter_mut().filter(|x| x.1 == m) {
                            it.3 = q[m as usize] / n;
                        }
                    }
                    let mut u = vec![0f32; lanes.len()];
                    let li = |l: u32| lanes.binary_search(&l).unwrap();
                    for it in &items {
                        u[li(it.0)] += it.3 / it.2;
                    }
                    if lanes.len() > 1 && moves.len() >= 1 {
                        for _ in 0..30 {
                            let mut moved = false;
                            for &m in moves.iter() {
                                let idx: Vec<usize> = items.iter().enumerate().filter(|(_, x)| x.1 == m).map(|(i, _)| i).collect();
                                if idx.len() < 2 {
                                    continue;
                                }
                                let hi = *idx.iter().max_by(|&&a, &&b| u[li(items[a].0)].total_cmp(&u[li(items[b].0)])).unwrap();
                                let lo = *idx.iter().min_by(|&&a, &&b| u[li(items[a].0)].total_cmp(&u[li(items[b].0)])).unwrap();
                                let (uh, ul) = (u[li(items[hi].0)], u[li(items[lo].0)]);
                                if uh - ul > 1e-3 && items[hi].3 > 0.0 {
                                    let dd = items[hi].3.min((uh - ul) / (1.0 / items[hi].2 + 1.0 / items[lo].2) / 2.0);
                                    items[hi].3 -= dd;
                                    items[lo].3 += dd;
                                    let (lh, ll) = (li(items[hi].0), li(items[lo].0));
                                    u[lh] -= dd / items[hi].2;
                                    u[ll] += dd / items[lo].2;
                                    moved = true;
                                }
                            }
                            if !moved {
                                break;
                            }
                        }
                    }
                    let x = u.iter().copied().fold(0.0, f32::max);
                    xg[g] = x;
                    cg[g] = if x > 1e-4 { total / x } else { empty_cap };
                }
            }
            (d.drain(..).collect::<Vec<f32>>(), xg, cg)
        })
        .collect();
    for (p, (_, xg, cg)) in results.into_iter().enumerate() {
        new_x[p * ng..(p + 1) * ng].copy_from_slice(&xg);
        new_cap[p * ng..(p + 1) * ng].copy_from_slice(&cg);
    }
    // queues through time, then delays
    let mut res_e = vec![0f32; p_n * ne];
    for g in 0..ng {
        let mut r = 0f32;
        for p in 0..p_n {
            let q: f32 = net.group_arcs[g].iter().map(|&m| flow[p * na + m as usize]).sum();
            let c = new_cap[p * ng + g];
            let r0 = r;
            if dynamic {
                r = (r + (q - c) * t_h).max(0.0);
            }
            new_res[p * ng + g] = r;
            let cap = c.max(1.0);
            let x = new_x[p * ng + g];
            let (x_rand, det) = if dynamic { (x.min(1.0), (r0 + r) / 2.0 / cap * 3600.0) } else { (x.min(X_CAP), 0.0) };
            let over = 900.0 * t_h * ((x_rand - 1.0) + ((x_rand - 1.0).powi(2) + 8.0 * 0.5 * x_rand / (cap * t_h)).sqrt());
            let b = block_of_period[p];
            for &m in &net.group_arcs[g] {
                let c0 = net.group_conns[g].iter().map(|&i| i as usize).find(|&i| net.conns[i].arc == m);
                let Some(ci) = c0 else { continue };
                let con = &net.conns[ci];
                let mut d = 0f32;
                match con.kind {
                    1 => {
                        let j = ci * BLOCKS + b;
                        let cy = sup.cyc[j].max(1.0);
                        let gc = ((sup.prot[j] + sup.perm[j]) / cy).clamp(0.02, 1.0);
                        d += 0.5 * cy * (1.0 - gc).powi(2) / (1.0 - x_rand.min(1.0) * gc).max(0.02);
                        d += over.max(0.0) + det;
                    }
                    2 => {
                        d += 3600.0 / cap * net.group_arcs[g].len() as f32 * 0.5 + over.max(0.0) + det;
                    }
                    _ => {
                        if x > 0.8 || det > 0.0 {
                            d += over.max(0.0) + det;
                        }
                    }
                }
                new_delay[p * na + m as usize] = d.min(3600.0);
            }
        }
    }
    // entering an edge: its own capacity. Merges and lane drops queue here. Running time rises on motorways.
    let mut new_run = vec![0f32; p_n * ne];
    for e in 0..ne {
        let ed = &net.edges[e];
        let c = ed.lanes.max(1.0) * ed.midblock;
        let mut r = 0f32;
        for p in 0..p_n {
            let q: f32 = net.in_arcs[e].iter().map(|&m| flow[p * na + m as usize]).sum();
            let x = q / c;
            let t0 = ed.len / ed.v.max(0.5);
            let bpr = if ed.motorway { 1.0 + 0.15 * x.min(1.2).powi(4) } else { 1.0 };
            let r0 = r;
            let det = if dynamic {
                r = (r + (q - c) * t_h).max(0.0);
                (r0 + r) / 2.0 / c * 3600.0
            } else {
                1800.0 * t_h * (x.min(X_CAP) - 1.0).max(0.0)
            };
            res_e[p * ne + e] = r;
            new_run[p * ne + e] = t0 * bpr + det.min(3600.0);
        }
    }
    for i in 0..sup.delay.len() {
        sup.delay[i] += alpha * (new_delay[i] - sup.delay[i]);
    }
    for i in 0..sup.run.len() {
        sup.run[i] += alpha * (new_run[i] - sup.run[i]);
    }
    sup.x = new_x;
    sup.cap_g = new_cap;
    sup.res = new_res;
    sup.res_e = res_e;
}

struct Work {
    dist: Vec<f32>,
    stamp: Vec<u32>,
    prev: Vec<u32>,
    cur: u32,
    heap: BinaryHeap<Reverse<(u32, u32)>>,
}

/// Cheapest tree from an origin edge and its opposite (a trip's kerb can be either side). Costs: perceived, time-indexed.
fn tree(net: &Net, sup: &Supply, w: &mut Work, seeds: &[u32], bit: u8, dep: f32, period: f32, dynamic: bool, noise: &[f32], beta_mult: f32, targets: &mut FxHashMap<u32, ()>) {
    w.cur += 1;
    w.heap.clear();
    let ne = net.edges.len();
    let na = net.arcs.len();
    let p_fix = ((dep / period) as usize).min(sup.p - 1);
    for &s in seeds {
        w.dist[s as usize] = 0.0;
        w.stamp[s as usize] = w.cur;
        w.prev[s as usize] = NONE;
        w.heap.push(Reverse((0, s)));
    }
    let mut left = targets.len();
    while let Some(Reverse((key, e))) = w.heap.pop() {
        let eu = e as usize;
        let de = w.dist[eu];
        if (de * 16.0) as u32 != key {
            continue;
        }
        if targets.contains_key(&e) {
            left -= 1;
            if left == 0 {
                break;
            }
        }
        let p = if dynamic { (((dep + de) / period) as usize).min(sup.p - 1) } else { p_fix };
        let run = sup.run[p * ne + eu];
        let f = 1.0 + net.edges[eu].beta * beta_mult;
        let n = noise[eu];
        for arc in net.first[eu] as usize..net.first[eu + 1] as usize {
            let a = &net.arcs[arc];
            if a.mask & bit == 0 {
                continue;
            }
            let mut c = (run + sup.delay[p * na + arc]) * f * n;
            if a.uturn {
                c += 60.0;
            }
            let nd = de + c.max(0.05);
            let nu = a.to as usize;
            if w.stamp[nu] != w.cur || nd < w.dist[nu] {
                w.stamp[nu] = w.cur;
                w.dist[nu] = nd;
                w.prev[nu] = arc as u32;
                w.heap.push(Reverse(((nd * 16.0) as u32, a.to)));
            }
        }
    }
}

fn path_to(net: &Net, w: &Work, d: u32) -> Option<Vec<u32>> {
    if w.stamp[d as usize] != w.cur {
        return None;
    }
    let mut p = Vec::new();
    let mut e = d;
    loop {
        let a = w.prev[e as usize];
        if a == NONE {
            break;
        }
        p.push(a);
        e = net.arcs[a as usize].from;
    }
    p.reverse();
    Some(p)
}

struct Load {
    a: Vec<f32>,   // arc, period: PCE arriving at the stop line, veh/h when divided
    o: Vec<f32>,   // arc, period: vehicles leaving, count
    n: Vec<f32>,   // arc, period: vehicles arriving, count
    dw: Vec<f32>,  // arc, period: vehicle-seconds of delay
    vs: Vec<f32>,  // edge, period: vehicle-seconds
    vm: Vec<f32>,  // edge, period: vehicle-metres
    starts: Vec<f32>,
    ends: Vec<f32>,
}

impl Load {
    fn new(na: usize, ne: usize, p: usize) -> Self {
        Load { a: vec![0.0; na * p], o: vec![0.0; na * p], n: vec![0.0; na * p], dw: vec![0.0; na * p], vs: vec![0.0; ne * p], vm: vec![0.0; ne * p], starts: vec![0.0; ne * p], ends: vec![0.0; ne * p] }
    }
    fn add(&mut self, b: &Load) {
        for (x, y) in self.a.iter_mut().zip(&b.a) {
            *x += *y;
        }
        for (x, y) in self.o.iter_mut().zip(&b.o) {
            *x += *y;
        }
        for (x, y) in self.n.iter_mut().zip(&b.n) {
            *x += *y;
        }
        for (x, y) in self.dw.iter_mut().zip(&b.dw) {
            *x += *y;
        }
        for (x, y) in self.vs.iter_mut().zip(&b.vs) {
            *x += *y;
        }
        for (x, y) in self.vm.iter_mut().zip(&b.vm) {
            *x += *y;
        }
        for (x, y) in self.starts.iter_mut().zip(&b.starts) {
            *x += *y;
        }
        for (x, y) in self.ends.iter_mut().zip(&b.ends) {
            *x += *y;
        }
    }
}

/// Walk every path through the current delays. In model a every arc stays in the departure period.
fn load(net: &Net, sup: &Supply, legs: &[Leg], st: &[LegState], arena: &[Vec<u32>], period: f32, dynamic: bool) -> Load {
    let na = net.arcs.len();
    let ne = net.edges.len();
    let pn = sup.p;
    let idx: Vec<usize> = (0..legs.len()).collect();
    idx.par_chunks(4096)
        .fold(|| Load::new(na, ne, pn), |mut l, ch| {
            for &i in ch {
                let g = &legs[i];
                for &(pid, fr) in &st[i].paths {
                    let w = g.w * fr;
                    let p0 = ((g.dep / period) as usize).min(pn - 1);
                    let path = &arena[pid as usize];
                    let o_edge = path.first().map(|&a| net.arcs[a as usize].from).unwrap_or(g.o);
                    l.starts[p0 * ne + o_edge as usize] += w;
                    let mut t = g.dep;
                    let mut last = o_edge;
                    for &a in path.iter() {
                        let arc = a as usize;
                        let e = net.arcs[arc].from as usize;
                        let p = if dynamic { ((t / period) as usize).min(pn - 1) } else { p0 };
                        let r = sup.run[p * ne + e];
                        let t_stop = t + r;
                        let ps = if dynamic { ((t_stop / period) as usize).min(pn - 1) } else { p0 };
                        let d = sup.delay[ps * na + arc];
                        l.a[ps * na + arc] += w * g.pce;
                        l.n[ps * na + arc] += w;
                        l.dw[ps * na + arc] += w * d;
                        let t_out = t_stop + d;
                        let pe = if dynamic { ((t_out / period) as usize).min(pn - 1) } else { p0 };
                        l.o[pe * na + arc] += w;
                        l.vs[p * ne + e] += w * (r + d);
                        l.vm[p * ne + e] += w * net.edges[e].len;
                        t = t_out;
                        last = net.arcs[arc].to;
                    }
                    let p = if dynamic { ((t / period) as usize).min(pn - 1) } else { p0 };
                    l.ends[p * ne + last as usize] += w;
                    let le = &net.edges[last as usize];
                    l.vs[p * ne + last as usize] += w * le.len / le.v.max(0.5) * 0.5;
                    l.vm[p * ne + last as usize] += w * le.len * 0.5;
                }
            }
            l
        })
        .reduce(|| Load::new(na, ne, pn), |mut a, b| {
            a.add(&b);
            a
        })
}

fn true_cost(net: &Net, sup: &Supply, path: &[u32], dep: f32, period: f32, dynamic: bool) -> f32 {
    let (ne, na, pn) = (net.edges.len(), net.arcs.len(), sup.p);
    let p0 = ((dep / period) as usize).min(pn - 1);
    let mut t = dep;
    for &a in path {
        let arc = a as usize;
        let e = net.arcs[arc].from as usize;
        let p = if dynamic { ((t / period) as usize).min(pn - 1) } else { p0 };
        t += sup.run[p * ne + e] + sup.delay[p * na + arc];
        if net.arcs[arc].uturn {
            t += 60.0;
        }
    }
    t - dep
}

fn perceived_cost(net: &Net, sup: &Supply, path: &[u32], dep: f32, period: f32, dynamic: bool, beta_mult: f32) -> f32 {
    let (ne, na, pn) = (net.edges.len(), net.arcs.len(), sup.p);
    let p0 = ((dep / period) as usize).min(pn - 1);
    let (mut t, mut c) = (dep, 0f32);
    for &a in path {
        let arc = a as usize;
        let e = net.arcs[arc].from as usize;
        let p = if dynamic { ((t / period) as usize).min(pn - 1) } else { p0 };
        let d = sup.run[p * ne + e] + sup.delay[p * na + arc];
        t += d;
        c += d * (1.0 + net.edges[e].beta * beta_mult);
        if net.arcs[arc].uturn {
            c += 60.0;
        }
    }
    c
}

fn hash64(a: u64, b: u64) -> u64 {
    let mut h = FxHasher::default();
    a.hash(&mut h);
    b.hash(&mut h);
    h.finish().wrapping_mul(0x9E3779B97F4A7C15)
}

pub fn run(dir: &str, out: &str, prm: &Params) -> Result<(), String> {
    let t0 = Instant::now();
    std::fs::create_dir_all(out).map_err(|e| e.to_string())?;
    let net = load_net(dir);
    let (ne, na) = (net.edges.len(), net.arcs.len());
    let dynamic = prm.dynamic;
    let period = if dynamic { prm.period } else { 3600.0 };
    let horizon: f32 = 30.0 * 3600.0;
    let pn = (horizon / period).ceil() as usize;
    let index: FxHashMap<&str, u32> = net.edges.iter().enumerate().map(|(i, e)| (e.id.as_str(), i as u32)).collect();
    let mut legs: Vec<Leg> = Vec::new();
    let mut dropped = 0u64;
    for r in tsv(&format!("{dir}/legs.tsv")) {
        let dep: f32 = r[2].parse().unwrap();
        if !prm.hours.is_empty() && !prm.hours.contains(&((dep / 3600.0) as u32)) {
            continue;
        }
        let (Some(&o), Some(&d)) = (index.get(r[0].as_str()), index.get(r[1].as_str())) else {
            dropped += 1;
            continue;
        };
        let cl: u8 = r[3].parse().unwrap();
        legs.push(Leg { o, d, dep, bit: 1 << cl, pce: r[4].parse().unwrap(), w: r[5].parse::<f32>().unwrap() * prm.demand_mult });
    }
    eprintln!("edges {ne} arcs {na} conns {} groups {} ctrls {} legs {} dropped {dropped}, loaded in {:.1}s", net.conns.len(), net.n_groups, net.ctrls.len(), legs.len(), t0.elapsed().as_secs_f32());
    let mut sup = Supply {
        p: pn,
        delay: vec![0.0; pn * na],
        run: vec![0.0; pn * ne],
        x: vec![0.0; pn * net.n_groups],
        cap_g: vec![0.0; pn * net.n_groups],
        res: vec![0.0; pn * net.n_groups],
        gc: vec![0.0; net.conns.len() * BLOCKS],
        prot: vec![0.0; net.conns.len() * BLOCKS],
        perm: vec![0.0; net.conns.len() * BLOCKS],
        cyc: vec![90.0; net.conns.len() * BLOCKS],
        res_e: vec![0.0; pn * ne],
    };
    for p in 0..pn {
        for e in 0..ne {
            sup.run[p * ne + e] = net.edges[e].len / net.edges[e].v.max(0.5);
        }
    }
    let block_of_period: Vec<usize> = (0..pn).map(|p| block_of_hour(((p as f32 + 0.5) * period / 3600.0) % 24.0)).collect();
    let mut periods_of_block = vec![Vec::new(); BLOCKS];
    for (p, &b) in block_of_period.iter().enumerate() {
        periods_of_block[b].push(p);
    }
    let mut flow = vec![0f32; pn * na];
    retime(&net, &mut sup, &flow, &periods_of_block, prm.s, prm.rule_greens, prm.green_scale);
    update_supply(&net, &mut sup, &flow, &block_of_period, period / 3600.0, prm.s, dynamic, 1.0);

    // legs grouped by origin (either side), class, departure period
    let mut groups: FxHashMap<(u32, u8, u32), Vec<u32>> = FxHashMap::default();
    for (i, g) in legs.iter().enumerate() {
        let r = net.edges[g.o as usize].rev;
        let key = if r != NONE && r < g.o { r } else { g.o };
        groups.entry((key, g.bit, (g.dep / period) as u32)).or_default().push(i as u32);
    }
    let mut group_list: Vec<((u32, u8, u32), Vec<u32>)> = groups.into_iter().collect();
    group_list.sort_by_key(|x| x.0);
    eprintln!("trees per full pass {}", group_list.len());
    let mut st: Vec<LegState> = vec![LegState { paths: Vec::new(), n: 0 }; legs.len()];
    let mut arena: Vec<Vec<u32>> = Vec::new();
    let mut intern: FxHashMap<Vec<u32>, u32> = FxHashMap::default();
    let mut rng_state = 88172645463325252u64;
    let mut rnd = move || {
        rng_state ^= rng_state << 13;
        rng_state ^= rng_state >> 7;
        rng_state ^= rng_state << 17;
        rng_state
    };
    // noise vectors: lognormal per edge, drawn once per iteration per vector
    const K_NOISE: usize = 32;
    let mut noise = vec![1f32; K_NOISE * ne];
    let mut log = std::fs::File::create(format!("{out}/iters.tsv")).map_err(|e| e.to_string())?;
    writeln!(log, "iter\tseconds\trerouted\tno_path\texcess_pct\tveh_km\tveh_h\tx_gt1\tchange_lt1pct\tres_max").unwrap();
    let mut prev_o = vec![0f32; pn * na];
    let mut l = Load::new(na, ne, pn);
    for it in 1..=prm.iters {
        for v in noise.iter_mut() {
            let (u1, u2) = (((rnd() >> 40) as f32 + 1.0) / 16777218.0, ((rnd() >> 40) as f32 + 1.0) / 16777218.0);
            let z = (-2.0 * u1.ln()).sqrt() * (6.2831853 * u2).cos();
            *v = (prm.sigma * z).exp();
        }
        let chosen: Vec<usize> = (0..group_list.len()).filter(|&g| it == 1 || hash64(g as u64, it as u64) % prm.reroute == 0).collect();
        let sup_ref = &sup;
        let net_ref = &net;
        let noise_ref = &noise;
        let group_ref = &group_list;
        let legs_ref = &legs;
        let results: Vec<Vec<(u32, Option<Vec<u32>>)>> = chosen
            .par_iter()
            .map_init(
                || Work { dist: vec![0.0; ne], stamp: vec![0; ne], prev: vec![NONE; ne], cur: 0, heap: BinaryHeap::new() },
                |w, &g| {
                    let ((o, bit, pd), ref ls) = group_ref[g];
                    let mut seeds = vec![o];
                    let r = net_ref.edges[o as usize].rev;
                    if r != NONE && net_ref.edges[r as usize].mask & bit != 0 {
                        seeds.push(r);
                    }
                    let k = (hash64(g as u64, it as u64 * 7919) % K_NOISE as u64) as usize;
                    let nv = &noise_ref[k * ne..(k + 1) * ne];
                    let mut targets: FxHashMap<u32, ()> = FxHashMap::default();
                    for &i in ls {
                        let d = legs_ref[i as usize].d;
                        targets.insert(d, ());
                        let rd = net_ref.edges[d as usize].rev;
                        if rd != NONE {
                            targets.insert(rd, ());
                        }
                    }
                    let dep = (pd as f32 + 0.5) * period;
                    tree(net_ref, sup_ref, w, &seeds, bit, dep, period, dynamic, nv, prm.beta_mult, &mut targets);
                    let mut out = Vec::with_capacity(ls.len());
                    for &i in ls {
                        let d = legs_ref[i as usize].d;
                        let rd = net_ref.edges[d as usize].rev;
                        let mut best = d;
                        if rd != NONE && w.stamp[rd as usize] == w.cur && (w.stamp[d as usize] != w.cur || w.dist[rd as usize] < w.dist[d as usize]) {
                            best = rd;
                        }
                        out.push((i, path_to(net_ref, w, best)));
                    }
                    out
                },
            )
            .collect();
        let mut rerouted = 0u64;
        let mut no_path = 0u64;
        for rs in results {
            for (i, p) in rs {
                let s = &mut st[i as usize];
                match p {
                    Some(path) => {
                        let pid = *intern.entry(path).or_insert_with_key(|k| {
                            arena.push(k.clone());
                            (arena.len() - 1) as u32
                        });
                        if s.paths.is_empty() {
                            s.paths.push((pid, 1.0));
                        } else if !s.paths.iter().any(|x| x.0 == pid) {
                            s.paths.push((pid, 0.0));
                        }
                        s.n += 1;
                        rerouted += 1;
                    }
                    None => no_path += 1,
                }
            }
        }
        // path swap: each leg's split moves toward a logit over its kept paths on true costs, with the same scale as the perception noise (D step 3)
        if it > 1 {
            let gamma = (0.6 / (it as f32).sqrt()).max(0.1);
            let (arena_ref, sup_ref) = (&arena, &sup);
            let net_ref = &net;
            let sigma = prm.sigma.max(0.02);
            let beta_mult = prm.beta_mult;
            st.par_iter_mut().zip(legs.par_iter()).for_each(|(s, g)| {
                if s.paths.len() < 2 {
                    return;
                }
                let cs: Vec<f32> = s.paths.iter().map(|x| perceived_cost(net_ref, sup_ref, &arena_ref[x.0 as usize], g.dep, period, dynamic, beta_mult)).collect();
                let best = cs.iter().copied().fold(f32::INFINITY, f32::min);
                let mu = sigma * best.max(10.0);
                let w: Vec<f32> = cs.iter().map(|c| (-(c - best) / mu).exp()).collect();
                let t: f32 = w.iter().sum();
                for (x, wi) in s.paths.iter_mut().zip(&w) {
                    x.1 += gamma * (wi / t - x.1);
                }
                s.paths.retain(|x| x.1 > 0.005);
                if s.paths.len() > 8 {
                    s.paths.sort_by(|a, b| b.1.total_cmp(&a.1));
                    s.paths.truncate(8);
                }
                let t: f32 = s.paths.iter().map(|x| x.1).sum();
                for x in s.paths.iter_mut() {
                    x.1 /= t;
                }
            });
        }
        // inner fixed point between loads and delays
        let alpha = if it == 1 { 1.0 } else { 0.5f32.max(1.0 / (it as f32).sqrt()) };
        for inner in 0..2 {
            l = load(&net, &sup, &legs, &st, &arena, period, dynamic);
            let to_h = 3600.0 / period;
            for (f, a) in flow.iter_mut().zip(&l.a) {
                *f = *a * to_h;
            }
            if prm.rule_greens && (it % prm.retime_every == 0) && inner == 0 {
                retime(&net, &mut sup, &flow, &periods_of_block, prm.s, true, prm.green_scale);
            }
            update_supply(&net, &mut sup, &flow, &block_of_period, period / 3600.0, prm.s, dynamic, alpha);
        }
        // excess over the best kept path, on true costs
        let (mut num, mut den) = (0f64, 0f64);
        for (i, g) in legs.iter().enumerate() {
            let s = &st[i];
            if s.paths.len() < 2 {
                continue;
            }
            let cs: Vec<f32> = s.paths.iter().map(|x| true_cost(&net, &sup, &arena[x.0 as usize], g.dep, period, dynamic)).collect();
            let best = cs.iter().copied().fold(f32::INFINITY, f32::min);
            let mean: f32 = s.paths.iter().zip(&cs).map(|(x, c)| x.1 * c).sum();
            num += (g.w * (mean - best)) as f64;
            den += (g.w * best) as f64;
        }
        let vk: f64 = l.vm.iter().map(|&x| x as f64).sum::<f64>() / 1000.0;
        let vh: f64 = l.vs.iter().map(|&x| x as f64).sum::<f64>() / 3600.0;
        let xover = sup.x.iter().filter(|&&x| x > 1.0).count();
        let same = (0..pn * na).filter(|&i| l.o[i] > 20.0).filter(|&i| (l.o[i] - prev_o[i]).abs() < 0.01 * l.o[i]).count() as f64 / (0..pn * na).filter(|&i| l.o[i] > 20.0).count().max(1) as f64;
        prev_o.copy_from_slice(&l.o);
        let rm = sup.res.iter().copied().fold(0.0, f32::max);
        let line = format!("{it}\t{:.1}\t{rerouted}\t{no_path}\t{:.3}\t{vk:.0}\t{vh:.0}\t{xover}\t{same:.3}\t{rm:.0}", t0.elapsed().as_secs_f32(), 100.0 * num / den.max(1.0));
        writeln!(log, "{line}").unwrap();
        log.flush().ok();
        eprintln!("{line}");
    }
    // final outputs: per hour
    let hour_of = |p: usize| ((p as f32 * period) / 3600.0) as usize;
    let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{out}/arcs.tsv")).map_err(|e| e.to_string())?);
    writeln!(f, "hour\tarc\tn\to\tdelay\tx\tgc\tres\tcap").unwrap();
    let hours = hour_of(pn - 1) + 1;
    let ng = net.n_groups;
    for h in 0..hours {
        let ps: Vec<usize> = (0..pn).filter(|&p| hour_of(p) == h).collect();
        for a in 0..na {
            let (mut n, mut o, mut dw) = (0f32, 0f32, 0f32);
            for &p in &ps {
                n += l.n[p * na + a];
                o += l.o[p * na + a];
                dw += l.dw[p * na + a];
            }
            if n < 0.01 && o < 0.01 {
                continue;
            }
            let g = net.arcs[a].group as usize;
            let (mut x, mut rs, mut cp) = (0f32, 0f32, 0f32);
            for &p in &ps {
                x = x.max(sup.x[p * ng + g]);
                rs = rs.max(sup.res[p * ng + g]);
                cp += sup.cap_g[p * ng + g];
            }
            cp /= ps.len().max(1) as f32;
            let ci = net.group_conns[g].iter().map(|&i| i as usize).find(|&i| net.conns[i].arc == a as u32).unwrap_or(0);
            let b = block_of_period[ps[0]];
            writeln!(f, "{h}\t{a}\t{n:.1}\t{o:.1}\t{:.1}\t{x:.3}\t{:.3}\t{rs:.1}\t{cp:.0}", if n > 0.0 { dw / n } else { 0.0 }, sup.gc[ci * BLOCKS + b]).unwrap();
        }
    }
    drop(f);
    let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{out}/edge_hour.tsv")).map_err(|e| e.to_string())?);
    writeln!(f, "hour\tedge\tvs\tvm\tstarts\tends\tres_e").unwrap();
    for h in 0..hours {
        let ps: Vec<usize> = (0..pn).filter(|&p| hour_of(p) == h).collect();
        for e in 0..ne {
            let (mut vs, mut vm, mut st_, mut en, mut re) = (0f32, 0f32, 0f32, 0f32, 0f32);
            for &p in &ps {
                vs += l.vs[p * ne + e];
                vm += l.vm[p * ne + e];
                st_ += l.starts[p * ne + e];
                en += l.ends[p * ne + e];
                re = re.max(sup.res_e[p * ne + e]);
            }
            if vs > 0.01 || st_ > 0.0 || en > 0.0 {
                writeln!(f, "{h}\t{e}\t{vs:.0}\t{vm:.0}\t{st_:.1}\t{en:.1}\t{re:.1}").unwrap();
            }
        }
    }
    drop(f);
    if prm.save_paths {
        let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{out}/paths.tsv")).map_err(|e| e.to_string())?);
        for p in &arena {
            let s: Vec<String> = p.iter().map(|x| x.to_string()).collect();
            writeln!(f, "{}", s.join(" ")).unwrap();
        }
        drop(f);
        let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{out}/leg_paths.tsv")).map_err(|e| e.to_string())?);
        for s in &st {
            let v: Vec<String> = s.paths.iter().map(|x| format!("{}:{:.4}", x.0, x.1)).collect();
            writeln!(f, "{}", v.join(" ")).unwrap();
        }
    }
    eprintln!("done in {:.1}s", t0.elapsed().as_secs_f32());
    Ok(())
}
