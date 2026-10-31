//! Turns GPU counters into the numbers SUMO's outputs report, one row per replica.

use serde::Serialize;

use crate::gpu::Gpu;
use crate::sim::Sim;
use crate::world::{GpuTripOut, World};

/// The columns of the thesis's `metrics.csv`.
#[derive(Clone, Debug, Default, Serialize)]
pub struct RunMetrics {
    pub label: String,
    pub completed: u64,
    pub travel_time: f64,
    pub waiting_time: f64,
    pub time_loss: f64,
    pub speed: f64,
    pub running: f64,
    pub edge_flow: f64,
    pub density: f64,
    pub route_length: f64,
}

/// Collects `edgeData`-style integrals over fixed intervals.
pub struct EdgeLog {
    pub interval_steps: u64,
    /// One entry per interval: per edge samples, distance (metres), entered.
    pub intervals: Vec<Vec<[f32; 3]>>,
    pub keep_detail: bool,
    sum_flow: Vec<f64>,
    n_flow: Vec<f64>,
    sum_density: Vec<f64>,
    n_density: Vec<f64>,
}

impl EdgeLog {
    pub fn new(world: &World, interval_steps: u64, keep_detail: bool) -> Self {
        let r = world.params.n_replicas as usize;
        Self {
            interval_steps,
            intervals: Vec::new(),
            keep_detail,
            sum_flow: vec![0.0; r],
            n_flow: vec![0.0; r],
            sum_density: vec![0.0; r],
            n_density: vec![0.0; r],
        }
    }

    /// Read the accumulators, fold them into per-replica flow and density, and reset them.
    pub fn collect(&mut self, gpu: &Gpu, sim: &Sim, world: &World) {
        let acc = sim.take_edge_acc(gpu);
        let p = &world.params;
        let t = self.interval_steps as f64 * p.dt as f64;
        let sample_dt = p.sample_steps as f64 * p.dt as f64;
        let per = world.n_edges_per_replica as usize;
        let mut detail = Vec::new();
        for r in 0..p.n_replicas as usize {
            let start = r * per;
            let (mut weighted, mut total_len) = (0.0f64, 0.0f64);
            for e in 0..per {
                let id = start + e;
                if !world.edge_is_normal[id] {
                    continue;
                }
                let a = acc[id];
                let len = world.edges[id].length as f64;
                if len <= 0.0 {
                    continue;
                }
                let samples = a[0] as f64 * sample_dt;
                let dist = a[1] as f64 / 8.0;
                let density = samples / t * 1000.0 / len;
                weighted += density * len;
                total_len += len;
                if samples > 0.0 {
                    // flow = density * frontSpeed * 3.6
                    self.sum_flow[r] += dist / (t * len) * 3600.0;
                    self.n_flow[r] += 1.0;
                }
                if self.keep_detail && r == 0 {
                    detail.push([samples as f32, dist as f32, a[2] as f32]);
                }
            }
            if total_len > 0.0 {
                self.sum_density[r] += weighted / total_len;
                self.n_density[r] += 1.0;
            }
        }
        if self.keep_detail {
            self.intervals.push(detail);
        }
    }

    pub fn flow(&self, r: usize) -> f64 {
        self.sum_flow[r] / self.n_flow[r].max(1.0)
    }

    pub fn density(&self, r: usize) -> f64 {
        self.sum_density[r] / self.n_density[r].max(1.0)
    }
}

/// Metrics for every replica, from trip outputs and the sampled series.
pub fn replica_metrics(gpu: &Gpu, sim: &Sim, world: &World, labels: &[String], edges: &EdgeLog) -> Vec<RunMetrics> {
    let p = &world.params;
    let trips: Vec<GpuTripOut> = sim.trip_outputs(gpu);
    let series: Vec<[u32; 4]> = sim.series(gpu);
    let r = p.n_replicas as usize;
    let mut out: Vec<RunMetrics> = (0..r)
        .map(|i| RunMetrics {
            label: labels.get(i).cloned().unwrap_or_default(),
            ..Default::default()
        })
        .collect();
    for (ti, o) in trips.iter().enumerate() {
        if o.flags & 1 == 0 {
            continue;
        }
        let m = &mut out[world.trips[ti].replica as usize];
        m.completed += 1;
        m.travel_time += (o.arrive_step - o.depart_step) as f64 * p.dt as f64;
        m.waiting_time += o.wait as f64;
        m.time_loss += o.time_loss as f64;
        m.route_length += o.route_len as f64;
    }
    let samples = series.len() / r.max(1);
    for (i, m) in out.iter_mut().enumerate() {
        let n = m.completed.max(1) as f64;
        m.travel_time /= n;
        m.waiting_time /= n;
        m.time_loss /= n;
        m.route_length /= n;
        let (mut sp, mut run, mut cnt) = (0.0, 0.0, 0.0);
        for s in 0..samples {
            let v = series[s * r + i];
            if v[0] > 0 {
                sp += v[2] as f64 / 100.0 / v[0] as f64;
                run += v[0] as f64;
                cnt += 1.0;
            }
        }
        m.speed = sp / f64::max(cnt, 1.0);
        m.running = run / f64::max(cnt, 1.0);
        m.edge_flow = edges.flow(i);
        m.density = edges.density(i);
    }
    out
}
