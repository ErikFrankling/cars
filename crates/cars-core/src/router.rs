use std::cmp::Reverse;
use std::collections::BinaryHeap;

use rayon::prelude::*;
use rustc_hash::FxHashMap;

use crate::net::{EdgeFunc, Net};

pub type RouteRequest = (u32, u32, Vec<u32>, u32);

struct Graph {
    next: Vec<Vec<u32>>,
    cost: Vec<f64>,
}

impl Graph {
    fn new(net: &Net, mask: u32) -> Self {
        let cost: Vec<_> = net
            .edges
            .iter()
            .map(|e| {
                if e.func != EdgeFunc::Normal {
                    return f64::INFINITY;
                }
                net.lanes[e.first_lane as usize..(e.first_lane + e.lane_count) as usize]
                    .iter()
                    .filter(|l| l.allow & mask != 0 && l.speed > 0.)
                    .map(|l| (l.length / l.speed) as f64)
                    .fold(f64::INFINITY, f64::min)
            })
            .collect();
        let mut next = vec![Vec::new(); net.edges.len()];
        for c in &net.conns {
            if net.conn_allow(c) & mask != 0 && cost[c.to_edge as usize].is_finite() {
                next[c.from_edge as usize].push(c.to_edge);
            }
        }
        Self { next, cost }
    }

    fn path(&self, from: u32, to: u32) -> Option<Vec<u32>> {
        if !self.cost.get(from as usize)?.is_finite() {
            return None;
        }
        self.path_any(&[from], to)
    }

    /// The cheapest way to `to` from whichever of `starts` is best.
    fn path_any(&self, starts: &[u32], to: u32) -> Option<Vec<u32>> {
        if !self.cost.get(to as usize)?.is_finite() {
            return None;
        }
        let mut dist = vec![u64::MAX; self.next.len()];
        let mut prev = vec![u32::MAX; self.next.len()];
        let mut queue = BinaryHeap::new();
        for &s in starts {
            if self.cost.get(s as usize).is_some_and(|c| c.is_finite()) {
                dist[s as usize] = 0;
                queue.push(Reverse((0u64, s)));
            }
        }
        while let Some(Reverse((d, e))) = queue.pop() {
            if d != dist[e as usize] {
                continue;
            }
            if e == to {
                break;
            }
            for &n in &self.next[e as usize] {
                let nd = d.saturating_add((self.cost[n as usize] * 1e6).round() as u64);
                if nd < dist[n as usize] {
                    dist[n as usize] = nd;
                    prev[n as usize] = e;
                    queue.push(Reverse((nd, n)));
                }
            }
        }
        if dist[to as usize] == u64::MAX {
            return None;
        }
        let mut result = vec![to];
        while prev[*result.last()? as usize] != u32::MAX {
            result.push(prev[*result.last()? as usize]);
        }
        result.reverse();
        Some(result)
    }
}

/// The graphs of a run, one per vehicle class mask, kept for routes asked for while it runs.
pub struct Router {
    graphs: FxHashMap<u32, Graph>,
}

impl Router {
    pub fn new(net: &Net, masks: impl IntoIterator<Item = u32>) -> Self {
        let mut graphs = FxHashMap::default();
        for m in masks {
            graphs.entry(m).or_insert_with(|| Graph::new(net, m));
        }
        Self { graphs }
    }

    /// Any way out of the network from one of `starts`, for a car with no way to its destination.
    pub fn to_any_exit(&self, mask: u32, starts: &[u32]) -> Option<Vec<u32>> {
        let g = self.graphs.get(&mask)?;
        let mut prev = vec![u32::MAX; g.next.len()];
        let mut seen = vec![false; g.next.len()];
        let mut queue = std::collections::VecDeque::new();
        for &s in starts {
            if g.cost.get(s as usize).is_some_and(|c| c.is_finite()) {
                seen[s as usize] = true;
                queue.push_back(s);
            }
        }
        while let Some(e) = queue.pop_front() {
            if g.next[e as usize].is_empty() {
                let mut result = vec![e];
                while prev[*result.last()? as usize] != u32::MAX {
                    result.push(prev[*result.last()? as usize]);
                }
                result.reverse();
                return Some(result);
            }
            for &n in &g.next[e as usize] {
                if !seen[n as usize] {
                    seen[n as usize] = true;
                    prev[n as usize] = e;
                    queue.push_back(n);
                }
            }
        }
        None
    }

    /// A way to `to` that begins on one of `starts`.
    pub fn from_any(&self, mask: u32, starts: &[u32], to: u32) -> Option<Vec<u32>> {
        self.graphs.get(&mask)?.path_any(starts, to)
    }
}

pub fn route(
    net: &Net,
    from_edge: u32,
    to_edge: u32,
    via: &[u32],
    vclass_mask: u32,
) -> Option<Vec<u32>> {
    route_many(net, &[(from_edge, to_edge, via.to_vec(), vclass_mask)]).pop()?
}

pub fn route_many(net: &Net, requests: &[RouteRequest]) -> Vec<Option<Vec<u32>>> {
    let mut graphs = FxHashMap::default();
    let mut keys = FxHashMap::default();
    for (from, to, via, mask) in requests {
        graphs
            .entry(*mask)
            .or_insert_with(|| Graph::new(net, *mask));
        let mut start = *from;
        for end in via.iter().copied().chain(std::iter::once(*to)) {
            keys.entry((start, end, *mask)).or_insert(None);
            start = end;
        }
    }
    let paths: Vec<_> = keys
        .keys()
        .copied()
        .collect::<Vec<_>>()
        .into_par_iter()
        .map(|k| (k, graphs[&k.2].path(k.0, k.1)))
        .collect();
    for (k, p) in paths {
        keys.insert(k, p);
    }
    requests
        .iter()
        .map(|(from, to, via, mask)| {
            let mut result = vec![*from];
            let mut start = *from;
            for end in via.iter().copied().chain(std::iter::once(*to)) {
                result.extend_from_slice(&keys[&(start, end, *mask)].as_ref()?[1..]);
                start = end;
            }
            Some(result)
        })
        .collect()
}
