//! Time-dependent A* on the edge graph with ALT bounds from free-flow landmarks.

use std::cmp::Reverse;
use std::collections::BinaryHeap;

use cars_core::net::{Net, vclass_mask};
use rustc_hash::{FxHashMap, FxHashSet};

use crate::costs::{CostTable, NONE, Supply};

pub const LANDMARKS: usize = 16;
pub const TURNAROUND_S: f32 = 10.0;

/// Classes a connection itself allows, where the net says: `(from edge, from lane, to edge, to lane) -> mask`.
pub type ConnectionMasks = FxHashMap<(u32, u32, u32, u32), u32>;

/// Read `allow` and `disallow` on connections. `Net` does not keep them, and routes must respect turn bans.
pub fn connection_masks(path: &std::path::Path, net: &Net) -> Result<ConnectionMasks, String> {
    use std::io::BufRead;
    let f = std::fs::File::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut out = ConnectionMasks::default();
    fn attr<'a>(line: &'a str, key: &str) -> Option<&'a str> {
        let at = line.find(&format!(" {key}=\""))? + key.len() + 3;
        Some(&line[at..at + line[at..].find('"')?])
    }
    for line in std::io::BufReader::with_capacity(1 << 20, f).lines() {
        let line = line.map_err(|e| e.to_string())?;
        if !line.trim_start().starts_with("<connection ") || !line.contains("allow=\"") {
            continue;
        }
        let (Some(from), Some(to), Some(fl), Some(tl)) = (attr(&line, "from"), attr(&line, "to"), attr(&line, "fromLane"), attr(&line, "toLane")) else { continue };
        let (Some(&a), Some(&b)) = (net.edge_index.get(from), net.edge_index.get(to)) else { continue };
        let mask = match (attr(&line, "allow"), attr(&line, "disallow")) {
            (Some(x), _) => vclass_mask(x),
            (None, Some(x)) => !vclass_mask(x),
            _ => continue,
        };
        out.insert((a, fl.parse().unwrap_or(0), b, tl.parse().unwrap_or(0)), mask);
    }
    Ok(out)
}

/// The turns one vehicle class may make, as compressed rows over dense edges.
pub struct Graph {
    pub mask: u32,
    pub n: usize,
    pub first: Vec<u32>,
    pub to: Vec<u32>,
    pub reversal: Vec<bool>,
    pub usable: Vec<bool>,
    /// Added to a turn back onto the opposite edge.
    pub turnaround_s: f32,
    from_l: Vec<f32>,
    to_l: Vec<f32>,
    landmarks: usize,
}

pub struct Work {
    dist: Vec<f32>,
    stamp: Vec<u32>,
    prev: Vec<u32>,
    cur: u32,
    heap: BinaryHeap<Reverse<(u32, u32)>>,
    pub settled: u64,
}

impl Work {
    pub fn new(n: usize) -> Self {
        Self { dist: vec![0.0; n], stamp: vec![0; n], prev: vec![NONE; n], cur: 0, heap: BinaryHeap::new(), settled: 0 }
    }
}

fn sssp(first: &[u32], to: &[u32], ff: &[f32], src: usize, reversed: bool) -> Vec<f32> {
    let n = first.len() - 1;
    let mut d = vec![f32::INFINITY; n];
    let mut h = BinaryHeap::new();
    d[src] = 0.0;
    h.push(Reverse((0u32, src as u32)));
    while let Some(Reverse((k, e))) = h.pop() {
        let eu = e as usize;
        if (d[eu] * 16.0) as u32 != k {
            continue;
        }
        for &x in &to[first[eu] as usize..first[eu + 1] as usize] {
            let xu = x as usize;
            // Distances cost the edge entered. On the reversed graph that is the edge being left.
            let w = if reversed { ff[eu] } else { ff[xu] };
            let nd = d[eu] + w;
            if nd < d[xu] {
                d[xu] = nd;
                h.push(Reverse(((nd * 16.0) as u32, x)));
            }
        }
    }
    d
}

impl Graph {
    pub fn new(net: &Net, supply: &Supply, mask: u32, landmarks: usize) -> Self {
        Self::with_connections(net, supply, mask, landmarks, &ConnectionMasks::default())
    }

    pub fn with_connections(net: &Net, supply: &Supply, mask: u32, landmarks: usize, conn: &ConnectionMasks) -> Self {
        let n = supply.n();
        let mut usable = vec![false; n];
        for (d, &e) in supply.normal.iter().enumerate() {
            let edge = &net.edges[e as usize];
            usable[d] = net.lanes[edge.first_lane as usize..(edge.first_lane + edge.lane_count) as usize].iter().any(|l| l.allow & mask != 0 && l.speed > 0.0);
        }
        let mut seen: FxHashSet<(u32, u32)> = FxHashSet::default();
        let mut arcs: Vec<(u32, u32)> = Vec::new();
        for c in &net.conns {
            let (a, b) = (supply.dense[c.from_edge as usize], supply.dense[c.to_edge as usize]);
            if a == NONE || b == NONE || !usable[a as usize] || !usable[b as usize] {
                continue;
            }
            let ok = net.lane_of(c.from_edge, c.from_lane).zip(net.lane_of(c.to_edge, c.to_lane)).is_some_and(|(x, y)| net.lanes[x as usize].allow & mask != 0 && net.lanes[y as usize].allow & mask != 0)
                && conn.get(&(c.from_edge, c.from_lane, c.to_edge, c.to_lane)).is_none_or(|m| m & mask != 0);
            if ok && seen.insert((a, b)) {
                arcs.push((a, b));
            }
        }
        arcs.sort_unstable();
        let mut first = vec![0u32; n + 1];
        for &(a, _) in &arcs {
            first[a as usize + 1] += 1;
        }
        for i in 0..n {
            first[i + 1] += first[i];
        }
        let to: Vec<u32> = arcs.iter().map(|x| x.1).collect();
        let reversal: Vec<bool> = arcs
            .iter()
            .map(|&(a, b)| {
                let (x, y) = (&net.edges[supply.normal[a as usize] as usize], &net.edges[supply.normal[b as usize] as usize]);
                x.from == y.to && x.to == y.from
            })
            .collect();
        let mut g = Graph { mask, n, first, to, reversal, usable, turnaround_s: TURNAROUND_S, from_l: Vec::new(), to_l: Vec::new(), landmarks: 0 };
        g.build_landmarks(&supply.ff, landmarks);
        g
    }

    fn build_landmarks(&mut self, ff: &[f32], count: usize) {
        let n = self.n;
        let mut rfirst = vec![0u32; n + 1];
        for &x in &self.to {
            rfirst[x as usize + 1] += 1;
        }
        for i in 0..n {
            rfirst[i + 1] += rfirst[i];
        }
        let mut rto = vec![0u32; self.to.len()];
        let mut fill = rfirst.clone();
        for e in 0..n {
            for &x in &self.to[self.first[e] as usize..self.first[e + 1] as usize] {
                rto[fill[x as usize] as usize] = e as u32;
                fill[x as usize] += 1;
            }
        }
        let Some(start) = (0..n).find(|&e| self.usable[e] && self.first[e + 1] > self.first[e]) else {
            return;
        };
        let mut land = start;
        let mut best = vec![f32::INFINITY; n];
        self.from_l = vec![0.0; n * count];
        self.to_l = vec![0.0; n * count];
        for l in 0..count {
            let fl = sssp(&self.first, &self.to, ff, land, false);
            let tl = sssp(&rfirst, &rto, ff, land, true);
            for v in 0..n {
                if fl[v].is_finite() {
                    best[v] = best[v].min(fl[v]);
                }
                self.from_l[v * count + l] = fl[v];
                self.to_l[v * count + l] = tl[v];
            }
            land = (0..n).filter(|&v| best[v].is_finite()).max_by(|&a, &b| best[a].total_cmp(&best[b])).unwrap_or(start);
        }
        self.landmarks = count;
    }

    #[inline]
    fn pot(&self, v: usize, t: usize) -> f32 {
        let k = self.landmarks;
        let mut p = 0f32;
        for l in 0..k {
            let a = self.from_l[t * k + l] - self.from_l[v * k + l];
            let b = self.to_l[v * k + l] - self.to_l[t * k + l];
            if a.is_finite() && a > p {
                p = a;
            }
            if b.is_finite() && b > p {
                p = b;
            }
        }
        p
    }

    /// Cheapest path from `o` to `d`, departing at `t0`, as dense edges and its time.
    pub fn path(&self, costs: &CostTable, w: &mut Work, o: u32, d: u32, t0: f32, use_alt: bool) -> Option<(Vec<u32>, f32)> {
        if !self.usable[o as usize] || !self.usable[d as usize] {
            return None;
        }
        w.cur = w.cur.wrapping_add(1);
        if w.cur == 0 {
            w.stamp.fill(0);
            w.cur = 1;
        }
        w.heap.clear();
        let du = d as usize;
        let alt = use_alt && self.landmarks > 0;
        let pot = |v: usize| if alt { self.pot(v, du) } else { 0.0 };
        let d0 = t0 + costs.wait_at(o as usize, t0) + costs.cost(o as usize, t0 + costs.wait_at(o as usize, t0));
        w.dist[o as usize] = d0;
        w.stamp[o as usize] = w.cur;
        w.prev[o as usize] = NONE;
        w.heap.push(Reverse((((d0 + pot(o as usize)) * 16.0) as u32, o)));
        while let Some(Reverse((key, e))) = w.heap.pop() {
            let eu = e as usize;
            let de = w.dist[eu];
            if ((de + pot(eu)) * 16.0) as u32 != key {
                continue;
            }
            w.settled += 1;
            if e == d {
                let mut p = vec![d];
                while let Some(&x) = p.last() {
                    let up = w.prev[x as usize];
                    if up == NONE {
                        break;
                    }
                    p.push(up);
                }
                p.reverse();
                return Some((p, de - t0));
            }
            for arc in self.first[eu] as usize..self.first[eu + 1] as usize {
                let n = self.to[arc];
                let nu = n as usize;
                let at = if self.reversal[arc] { de + self.turnaround_s } else { de };
                let nd = at + costs.cost(nu, at);
                if w.stamp[nu] != w.cur || nd < w.dist[nu] {
                    w.stamp[nu] = w.cur;
                    w.dist[nu] = nd;
                    w.prev[nu] = e;
                    w.heap.push(Reverse((((nd + pot(nu)) * 16.0) as u32, n)));
                }
            }
        }
        None
    }

    /// A route's cost on the same terms as `path`: time plus turnaround penalties.
    pub fn evaluate(&self, costs: &CostTable, route: &[u32], depart: f32) -> f32 {
        let Some(&first) = route.first() else { return f32::INFINITY };
        let mut t = depart + costs.wait_at(first as usize, depart);
        t += costs.cost(first as usize, t);
        for p in route.windows(2) {
            let a = p[0] as usize;
            if (self.first[a] as usize..self.first[a + 1] as usize).any(|arc| self.to[arc] == p[1] && self.reversal[arc]) {
                t += self.turnaround_s;
            }
            t += costs.cost(p[1] as usize, t);
        }
        t - depart
    }

    pub fn has_reversal(&self, route: &[u32]) -> bool {
        route.windows(2).any(|p| {
            let a = p[0] as usize;
            (self.first[a] as usize..self.first[a + 1] as usize).any(|arc| self.to[arc] == p[1] && self.reversal[arc])
        })
    }
}
