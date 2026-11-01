//! Per-edge, per-bin costs from GPU counters: free flow plus queue over rate.

use cars_core::demand::VType;
use cars_core::net::{EdgeFunc, Net};
use rayon::prelude::*;

pub const BIN_S: f32 = 300.0;
pub const NONE: u32 = u32::MAX;
const MAX_COST: f32 = 2e5;

/// Normal edges in a dense numbering, with what routing and cut checks need to know about them.
pub struct Supply {
    pub normal: Vec<u32>,
    pub dense: Vec<u32>,
    pub length: Vec<f32>,
    pub ff: Vec<f32>,
    pub lanes: Vec<u32>,
    pub speed: Vec<f32>,
    pub mid: Vec<[f32; 2]>,
}

impl Supply {
    /// `used` lists each trip's vehicle type: only the mean speed factor matters to free-flow time.
    pub fn new(net: &Net, vtypes: &[VType], used: impl Iterator<Item = u32>) -> Self {
        let mut use_count = vec![0f64; vtypes.len()];
        for t in used {
            use_count[t as usize] += 1.0;
        }
        let n: f64 = use_count.iter().sum();
        let factor = if n > 0.0 { (use_count.iter().zip(vtypes).map(|(c, v)| c * v.speed_factor_mean as f64).sum::<f64>() / n) as f32 } else { 1.0 };
        let mut s = Supply { normal: Vec::new(), dense: vec![NONE; net.edges.len()], length: Vec::new(), ff: Vec::new(), lanes: Vec::new(), speed: Vec::new(), mid: Vec::new() };
        for (i, e) in net.edges.iter().enumerate() {
            if e.func != EdgeFunc::Normal || e.lane_count == 0 {
                continue;
            }
            let ls = &net.lanes[e.first_lane as usize..(e.first_lane + e.lane_count) as usize];
            let speed = ls.iter().map(|l| l.speed).fold(0.0f32, f32::max).max(0.5);
            let length = ls.iter().map(|l| l.length).fold(f32::INFINITY, f32::min);
            s.dense[i] = s.normal.len() as u32;
            s.normal.push(i as u32);
            s.length.push(length);
            s.speed.push(speed);
            s.lanes.push(e.lane_count);
            s.ff.push(length / (speed * factor.max(0.1)));
            let sh = &ls[0].shape;
            s.mid.push(if sh.is_empty() { [0.0, 0.0] } else { sh[sh.len() / 2] });
        }
        s
    }

    pub fn n(&self) -> usize {
        self.normal.len()
    }

    /// Deliberately optimistic link capacity, for cut checks where nothing was measured.
    pub fn nominal_capacity(&self, e: usize) -> f32 {
        let v = self.speed[e];
        self.lanes[e] as f32 * (3600.0 / (1.0 + 7.0 / v)).min(2400.0) / 3600.0
    }
}

/// What one simulated day did per edge and bin, summed over replicas.
pub struct DayCounts {
    pub n_edges: usize,
    pub n_bins: usize,
    pub replicas: u32,
    /// Bins the day really ran. Later bins hold nothing.
    pub end_bin: usize,
    pub n_in: Vec<u16>,
    pub left: Vec<u16>,
    pub inserted: Vec<u16>,
    pub requested: Vec<u16>,
}

impl DayCounts {
    pub fn new(n_edges: usize, n_bins: usize, replicas: u32) -> Self {
        let z = n_edges * n_bins;
        Self { n_edges, n_bins, replicas, end_bin: 0, n_in: vec![0; z], left: vec![0; z], inserted: vec![0; z], requested: vec![0; z] }
    }

    /// Another day's counters, to average over seeds that ran apart.
    pub fn add(&mut self, o: &DayCounts) {
        self.replicas += o.replicas;
        self.end_bin = self.end_bin.max(o.end_bin);
        for (a, b) in [(&mut self.n_in, &o.n_in), (&mut self.left, &o.left), (&mut self.inserted, &o.inserted), (&mut self.requested, &o.requested)] {
            for (x, y) in a.iter_mut().zip(b) {
                *x = x.saturating_add(*y);
            }
        }
    }
}

#[derive(Clone)]
pub struct CostTable {
    pub n_edges: usize,
    pub n_bins: usize,
    pub c: Vec<f32>,
    pub wait: Vec<f32>,
}

fn interp(curve: &[f32], t: f32) -> f32 {
    let x = (t / BIN_S).max(0.0);
    let b = x as usize;
    if b + 1 >= curve.len() {
        return *curve.last().unwrap_or(&0.0);
    }
    curve[b] + (curve[b + 1] - curve[b]) * (x - b as f32)
}

impl CostTable {
    pub fn free_flow(supply: &Supply, n_bins: usize) -> Self {
        let n_edges = supply.n();
        let mut c = vec![0.0; n_edges * n_bins];
        for (e, row) in c.chunks_mut(n_bins).enumerate() {
            row.fill(supply.ff[e]);
        }
        Self { n_edges, n_bins, c, wait: vec![0.0; n_edges * n_bins] }
    }

    /// One day's costs, with no memory. Vehicles still on the network stay in the queue: when a day
    /// stops early its last bin stands for the rest of the day.
    pub fn from_day(supply: &Supply, day: &DayCounts) -> Self {
        let (n_edges, n_bins) = (day.n_edges, day.n_bins);
        let mut c = vec![0.0f32; n_edges * n_bins];
        let mut wait = vec![0.0f32; n_edges * n_bins];
        let k = day.replicas.max(1) as f32;
        let end = day.end_bin.clamp(1, n_bins);
        c.par_chunks_mut(n_bins).zip(wait.par_chunks_mut(n_bins)).enumerate().for_each(|(e, (cost, w))| {
            let ff = supply.ff[e];
            let at = |v: &[u16], b: usize| v[e * n_bins + b] as f32 / k;
            let mut cum_in = vec![0.0f32; end + 1];
            let mut cum_out = vec![0.0f32; end + 1];
            let mut cum_req = vec![0.0f32; end + 1];
            let mut cum_ins = vec![0.0f32; end + 1];
            let (mut peak, mut peak_ins) = (0.0f32, 0.0f32);
            for b in 0..end {
                cum_in[b + 1] = cum_in[b] + at(&day.n_in, b);
                cum_out[b + 1] = cum_out[b] + at(&day.left, b);
                cum_req[b + 1] = cum_req[b] + at(&day.requested, b);
                cum_ins[b + 1] = cum_ins[b] + at(&day.inserted, b);
                peak = peak.max(at(&day.left, b) / BIN_S);
                peak_ins = peak_ins.max(at(&day.inserted, b) / BIN_S);
            }
            let cap = peak.max(0.1);
            let cap_ins = peak_ins.max(0.1);
            cost.fill(ff);
            if cum_in[end] == 0.0 && cum_req[end] == 0.0 {
                return;
            }
            for b in 0..end {
                let mid = (b as f32 + 0.5) * BIN_S;
                let out = (cum_out[b] + cum_out[b + 1]) * 0.5;
                let q = (interp(&cum_in, mid - ff) - out).max(0.0);
                let rate = (at(&day.left, b) / BIN_S).max(0.25 * cap);
                cost[b] = (ff + q / rate).min(MAX_COST);
                let waiting = ((cum_req[b] + cum_req[b + 1]) - (cum_ins[b] + cum_ins[b + 1])) * 0.5;
                if waiting > 0.0 {
                    let ins_rate = (at(&day.inserted, b) / BIN_S).max(0.25 * cap_ins);
                    w[b] = (waiting / ins_rate).min(MAX_COST);
                }
            }
            for b in end..n_bins {
                cost[b] = cost[end - 1];
                w[b] = w[end - 1];
            }
        });
        Self { n_edges, n_bins, c, wait }
    }

    /// `C = (1 - m) C_prev + m cost`, then FIFO from the last bin backwards.
    pub fn blend(&mut self, new: &CostTable, m: f32) {
        self.c.par_iter_mut().zip(new.c.par_iter()).for_each(|(a, b)| *a = (1.0 - m) * *a + m * b);
        self.wait.par_iter_mut().zip(new.wait.par_iter()).for_each(|(a, b)| *a = (1.0 - m) * *a + m * b);
        self.enforce_fifo();
    }

    pub fn enforce_fifo(&mut self) {
        let n_bins = self.n_bins;
        self.c.par_chunks_mut(n_bins).for_each(|row| {
            for b in (0..row.len().saturating_sub(1)).rev() {
                row[b] = row[b].min(BIN_S + row[b + 1]);
            }
        });
    }

    #[inline]
    pub fn bin(&self, t: f32) -> usize {
        ((t / BIN_S).max(0.0) as usize).min(self.n_bins - 1)
    }

    #[inline]
    pub fn cost(&self, e: usize, t: f32) -> f32 {
        self.c[e * self.n_bins + self.bin(t)]
    }

    #[inline]
    pub fn wait_at(&self, e: usize, t: f32) -> f32 {
        self.wait[e * self.n_bins + self.bin(t)]
    }

    /// Generalised time of a route of dense edges from `depart`, insertion delay included.
    pub fn evaluate(&self, route: &[u32], depart: f32) -> f32 {
        if route.is_empty() {
            return f32::INFINITY;
        }
        let mut t = depart + self.wait_at(route[0] as usize, depart);
        for &e in route {
            t += self.cost(e as usize, t);
        }
        t - depart
    }

    /// When a route's traveller reaches each edge, walking through the table.
    pub fn passage(&self, route: &[u32], depart: f32, mut f: impl FnMut(u32, f32)) {
        if route.is_empty() {
            return;
        }
        let mut t = depart + self.wait_at(route[0] as usize, depart);
        for &e in route {
            f(e, t);
            t += self.cost(e as usize, t);
        }
    }
}
