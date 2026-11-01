//! Physical data derived from the network: grades, curve speeds, conflict zones. The energy model
//! and lateral motion that output needs. See `research/truth/11-vehicle-physics.md`.

use rustc_hash::FxHashMap;

use crate::net::{EdgeFunc, Net};
use crate::topology::Topology;
use crate::world::{GpuTripEnergy, GpuZone};

pub const G: f32 = 9.81;
const CHORD: f32 = 10.0;
const STRAIGHT_RADIUS: f32 = 500.0;

#[derive(Clone, Copy, Debug, Default)]
pub struct LanePhys {
    pub gz: f32,
    pub curve_v: f32,
    pub sqrt_r: f32,
    pub s_curve: f32,
    pub s_curve_end: f32,
    pub geom_length: f32,
}

pub fn surface_mu(name: &str) -> Option<f32> {
    match name {
        "dry" => Some(0.85),
        "wet" => Some(0.54),
        "snow" => Some(0.32),
        "ice" => Some(0.073),
        _ => None,
    }
}

fn point_at(shape: &[[f32; 2]], cum: &[f32], s: f32) -> [f32; 2] {
    let s = s.clamp(0.0, *cum.last().unwrap_or(&0.0));
    let k = cum.partition_point(|&d| d <= s).clamp(1, shape.len().max(2) - 1);
    let span = (cum[k] - cum[k - 1]).max(1e-4);
    let u = ((s - cum[k - 1]) / span).clamp(0.0, 1.0);
    [shape[k - 1][0] + (shape[k][0] - shape[k - 1][0]) * u, shape[k - 1][1] + (shape[k][1] - shape[k - 1][1]) * u]
}

fn cumulative(shape: &[[f32; 2]]) -> Vec<f32> {
    let mut at = 0.0;
    let mut out = Vec::with_capacity(shape.len());
    out.push(0.0);
    for w in shape.windows(2) {
        at += ((w[1][0] - w[0][0]).powi(2) + (w[1][1] - w[0][1]).powi(2)).sqrt();
        out.push(at);
    }
    out
}

/// Radius through three points, infinite when they lie on a line.
fn radius(a: [f32; 2], b: [f32; 2], c: [f32; 2]) -> f32 {
    let (ab, bc, ca) = (
        ((b[0] - a[0]).powi(2) + (b[1] - a[1]).powi(2)).sqrt(),
        ((c[0] - b[0]).powi(2) + (c[1] - b[1]).powi(2)).sqrt(),
        ((a[0] - c[0]).powi(2) + (a[1] - c[1]).powi(2)).sqrt(),
    );
    let area2 = ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])).abs();
    if area2 < 1e-3 { 1e9 } else { ab * bc * ca / (2.0 * area2) }
}

/// Lateral acceleration drivers accept at a radius: Xu et al., capped at Bosetti's measured comfort.
fn driver_lateral(r: f32, cap: f32) -> f32 {
    (20.5 * r.powf(-0.46) - 0.35).min(cap)
}

pub fn lanes(net: &Net, lateral_cap: f32) -> Vec<LanePhys> {
    net.lanes
        .iter()
        .map(|l| {
            let mut p = LanePhys::default();
            if l.shape.len() < 2 {
                p.geom_length = l.length;
                return p;
            }
            let cum = cumulative(&l.shape);
            let geom = *cum.last().unwrap();
            p.geom_length = geom;
            if l.z_rise != 0.0 && l.length > 0.1 {
                let g = l.z_rise / l.length;
                p.gz = G * g * (1.0 - g * g / 2.0);
            }
            let half = (CHORD / 2.0).min(geom / 2.0);
            if half < 0.5 {
                return p;
            }
            let n = (geom.ceil() as usize + 1).max(3);
            let mut limit = vec![f32::MAX; n];
            let mut rad = vec![f32::MAX; n];
            let mut tightest = f32::MAX;
            let mut lowest = f32::MAX;
            for (i, (lim, ra)) in limit.iter_mut().zip(rad.iter_mut()).enumerate() {
                let s = (i as f32).min(geom);
                let c = s.clamp(half, geom - half);
                let r = radius(point_at(&l.shape, &cum, c - half), point_at(&l.shape, &cum, c), point_at(&l.shape, &cum, c + half));
                if r >= STRAIGHT_RADIUS {
                    continue;
                }
                let v = (driver_lateral(r, lateral_cap) * r).sqrt();
                *lim = v;
                *ra = r;
                tightest = tightest.min(r);
                lowest = lowest.min(v);
            }
            if tightest == f32::MAX {
                return p;
            }
            let scale = l.length / geom.max(1e-3);
            let lowest_at = limit.iter().position(|&v| v == lowest).unwrap_or(0);
            let mut lo = lowest_at;
            let mut hi = lowest_at;
            while lo > 0 && limit[lo - 1] <= lowest * 1.2 {
                lo -= 1;
            }
            while hi + 1 < n && limit[hi + 1] <= lowest * 1.2 {
                hi += 1;
            }
            p.curve_v = lowest;
            p.sqrt_r = tightest.sqrt();
            p.s_curve = lo as f32 * scale;
            p.s_curve_end = (hi as f32 + 1.0) * scale;
            p
        })
        .collect()
}

/// Every pair of internal lanes of a junction that come within body reach of each other, and where.
/// Symmetric by construction, from geometry alone, independent of the right-of-way tables.
pub fn zones(net: &Net, topo: &Topology, reach: f32) -> Vec<Vec<GpuZone>> {
    let mut by_junction: FxHashMap<&str, Vec<u32>> = FxHashMap::default();
    for (li, l) in net.lanes.iter().enumerate() {
        if net.edges[l.edge as usize].func == EdgeFunc::Internal && l.shape.len() >= 2 {
            let junction = l.id[1..].rsplitn(3, '_').last().unwrap_or("");
            by_junction.entry(junction).or_default().push(li as u32);
        }
    }
    let mut out: Vec<Vec<GpuZone>> = vec![Vec::new(); net.lanes.len()];
    let cum: Vec<Vec<f32>> = net.lanes.iter().map(|l| if l.shape.len() >= 2 { cumulative(&l.shape) } else { Vec::new() }).collect();
    let bbox = |l: u32| {
        let s = &net.lanes[l as usize].shape;
        let mut b = [f32::MAX, f32::MAX, f32::MIN, f32::MIN];
        for p in s {
            b[0] = b[0].min(p[0]);
            b[1] = b[1].min(p[1]);
            b[2] = b[2].max(p[0]);
            b[3] = b[3].max(p[1]);
        }
        b
    };
    let successive = |a: u32, b: u32| {
        topo.lane_links[a as usize].iter().any(|&k| topo.links[k as usize].next_lane == b) || topo.lane_links[b as usize].iter().any(|&k| topo.links[k as usize].next_lane == a)
    };
    for list in by_junction.values() {
        let boxes: Vec<[f32; 4]> = list.iter().map(|&l| bbox(l)).collect();
        for (ia, &a) in list.iter().enumerate() {
            for (ib, &b) in list.iter().enumerate().skip(ia + 1) {
                let (ba, bb) = (boxes[ia], boxes[ib]);
                if ba[0] > bb[2] + reach || bb[0] > ba[2] + reach || ba[1] > bb[3] + reach || bb[1] > ba[3] + reach {
                    continue;
                }
                if successive(a, b) {
                    continue;
                }
                let Some((a_in, a_out, d1)) = interval(net, &cum, a, b, reach) else { continue };
                let Some((b_in, b_out, d2)) = interval(net, &cum, b, a, reach) else { continue };
                let dist = d1.min(d2);
                out[a as usize].push(GpuZone { foe_lane: b, own_in: a_in, own_out: a_out, foe_in: b_in, foe_out: b_out, dist });
                out[b as usize].push(GpuZone { foe_lane: a, own_in: b_in, own_out: b_out, foe_in: a_in, foe_out: a_out, dist });
            }
        }
    }
    out
}

/// Where along `a`, in lane positions, its centre line is within reach of `b`.
fn interval(net: &Net, cum: &[Vec<f32>], a: u32, b: u32, reach: f32) -> Option<(f32, f32, f32)> {
    let (la, lb) = (&net.lanes[a as usize], &net.lanes[b as usize]);
    let ca = &cum[a as usize];
    let geom = *ca.last()?;
    let n = (geom.ceil() as usize).max(1);
    let (mut first, mut last, mut least) = (f32::MAX, f32::MIN, f32::MAX);
    for i in 0..=n {
        let s = geom * i as f32 / n as f32;
        let p = point_at(&la.shape, ca, s);
        let d2 = lb.shape.windows(2).map(|w| segment_dist2(p, w[0], w[1])).fold(f32::MAX, f32::min);
        if d2 < reach * reach {
            first = first.min(s);
            last = last.max(s);
            least = least.min(d2);
        }
    }
    if first > last {
        return None;
    }
    let scale = la.length / geom.max(1e-3);
    Some((first * scale, last * scale, least.sqrt()))
}

fn segment_dist2(p: [f32; 2], a: [f32; 2], b: [f32; 2]) -> f32 {
    let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
    let l2 = dx * dx + dy * dy;
    let t = if l2 < 1e-9 { 0.0 } else { (((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2).clamp(0.0, 1.0) };
    let (ex, ey) = (p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
    ex * ex + ey * ey
}

/// Metres sideways after `t` seconds of a change at `v_lat`: near-constant speed with 1 s ends.
pub fn lateral_done(t: f32, lane_width: f32, v_lat: f32) -> f32 {
    let total = lane_width / v_lat + 1.0;
    let rise = |t: f32| v_lat * (t / 2.0 - (std::f32::consts::PI * t).sin() / (2.0 * std::f32::consts::PI));
    if t < 1.0 {
        rise(t)
    } else if t <= total - 1.0 {
        v_lat * (t - 0.5)
    } else {
        lane_width - rise((total - t).max(0.0))
    }
}

/// Sideways distance from the new lane's centre towards the old lane, left of travel positive.
pub fn lateral_offset(phys: u32, lane_width: f32, v_lat: f32) -> f32 {
    let dir = phys >> 30;
    if dir == 0 {
        return 0.0;
    }
    let u = ((phys >> 16) & 0x3fff) as f32 / 16383.0;
    let remain = if v_lat <= 0.0 {
        lane_width * (1.0 - u * u * u * (10.0 + u * (6.0 * u - 15.0)))
    } else {
        lane_width - lateral_done(u * (lane_width / v_lat + 1.0), lane_width, v_lat)
    };
    if dir == 1 { -remain } else { remain }
}

/// Drivetrains are design values. The electric figures are the ones section 2.3 of the report checks
/// against WLTC; the combustion ones give about 6 l/100 km for the fleet-mean car over WLTC.
#[derive(Clone, Copy, Debug)]
pub struct Drivetrain {
    pub ice_efficiency: f32,
    pub ice_idle_kw: f32,
    pub ev_efficiency: f32,
    pub ev_regen: f32,
    pub ev_aux_kw: f32,
}

pub const PETROL_KWH_PER_L: f32 = 8.9;
pub const DIESEL_KWH_PER_L: f32 = 10.0;

pub fn drivetrain(heavy: bool) -> Drivetrain {
    if heavy {
        Drivetrain { ice_efficiency: 0.38, ice_idle_kw: 3.0, ev_efficiency: 0.85, ev_regen: 0.6, ev_aux_kw: 3.0 }
    } else {
        Drivetrain { ice_efficiency: 0.31, ice_idle_kw: 1.0, ev_efficiency: 0.85, ev_regen: 0.6, ev_aux_kw: 0.5 }
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct TripEnergy {
    pub wheel_kwh: f32,
    pub brake_kwh: f32,
    pub road_kwh: f32,
    pub pe_kwh: f32,
    pub ke_kwh: f32,
    pub fuel_kwh: f32,
    pub fuel_l: f32,
    pub ev_kwh: f32,
    /// Share of the wheel work that the other terms do not explain.
    pub residual: f32,
}

pub fn trip_energy(e: &GpuTripEnergy, heavy: bool) -> TripEnergy {
    const J: f32 = 1.0 / 3.6e6;
    let d = drivetrain(heavy);
    let hours = (e.idle_s + e.moving_s) / 3600.0;
    let fuel_kwh = e.wheel * J / d.ice_efficiency + d.ice_idle_kw * e.idle_s / 3600.0;
    let per_l = if heavy { DIESEL_KWH_PER_L } else { PETROL_KWH_PER_L };
    let balance = e.brake + e.road + e.pe + e.ke - e.wheel;
    let scale = (e.wheel.abs() + e.brake.abs() + e.road.abs()).max(1.0);
    TripEnergy {
        wheel_kwh: e.wheel * J,
        brake_kwh: e.brake * J,
        road_kwh: e.road * J,
        pe_kwh: e.pe * J,
        ke_kwh: e.ke * J,
        fuel_kwh,
        fuel_l: fuel_kwh / per_l,
        ev_kwh: e.wheel * J / d.ev_efficiency - d.ev_regen * d.ev_efficiency * e.brake * J + d.ev_aux_kw * hours,
        residual: balance / scale,
    }
}
