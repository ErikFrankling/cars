//! MSVehicle::updateBestLanes for the first edge of a route, for departLane="best" and "best_prob".

use crate::demand::VType;
use crate::net::Net;
use crate::topology::Topology;

const BEST_LANE_LOOKAHEAD: f32 = 3000.0;
const MAX_LANES: usize = 16;

fn brake_gap(speed: f32, decel: f32, tau: f32) -> f32 {
    let steps = (speed / decel) as u32 as f32;
    steps * speed - decel * steps * (steps + 1.0) / 2.0 + speed * tau
}

fn nearer(k: usize, lo: usize, hi: usize) -> i32 {
    let (a, b) = (lo as i32 - k as i32, hi as i32 - k as i32);
    if a.abs() < b.abs() { a } else { b }
}

/// Bit per lane of the route's first edge: the lanes a vehicle may depart on.
pub fn depart_mask(net: &Net, topo: &Topology, route: &[u32], vt: &VType) -> u32 {
    let first = &net.edges[route[0] as usize];
    let edge_len = |e: u32| net.lanes[net.edges[e as usize].first_lane as usize].length;
    let brake = net.lanes[first.first_lane as usize].length + brake_gap(vt.max_speed, vt.decel, vt.tau) + vt.min_gap;
    let mut stop = 0;
    let mut seen = 0.0;
    loop {
        seen += edge_len(route[stop]);
        stop += 1;
        if stop >= route.len() || (stop > 4 && seen >= brake.max(3000.0)) || (stop > 8 && seen >= brake.max(200.0)) {
            break;
        }
    }
    let allowed = |l: u32| net.lanes[l as usize].allow & vt.vclass == vt.vclass;
    let mut b = [0f32; MAX_LANES];
    let mut next_off = [0i32; MAX_LANES];
    let mut next_ok = [false; MAX_LANES];
    for ri in (0..stop).rev() {
        let edge = &net.edges[route[ri] as usize];
        let count = (edge.lane_count as usize).min(MAX_LANES);
        let next_edge = route.get(ri + 1).copied();
        let lane = |k: usize| edge.first_lane + k as u32;
        let mut a = [0f32; MAX_LANES];
        let mut whole = [0f32; MAX_LANES];
        let mut off = [0i32; MAX_LANES];
        let mut prio = [-1i32; MAX_LANES];
        let mut ok = [false; MAX_LANES];
        for k in 0..count {
            if allowed(lane(k)) {
                a[k] = edge_len(route[ri]);
            }
            whole[k] = a[k];
            ok[k] = match next_edge {
                None => true,
                Some(ne) => {
                    a[k] > 0.0
                        && topo.lane_links[lane(k) as usize].iter().any(|&l| {
                            let lk = &topo.links[l as usize];
                            lk.to_edge == ne && allowed(lk.to_lane)
                        })
                }
            };
        }
        let (mut bi, mut bmax) = (0, 0);
        if ri + 1 == stop {
            let mut top = -1.0;
            for k in 0..count {
                if a[k] > top {
                    top = a[k];
                    bi = k;
                    bmax = k;
                } else if a[k] == top {
                    bmax = k;
                }
            }
            for k in 0..count {
                if a[k] < top {
                    off[k] = nearer(k, bi, bmax);
                }
            }
        } else {
            let ne = route[ri + 1];
            let next = &net.edges[ne as usize];
            let n_next = (next.lane_count as usize).min(MAX_LANES);
            let mut approached = [false; MAX_LANES];
            for k in 0..count {
                for &l in &topo.lane_links[lane(k) as usize] {
                    let lk = &topo.links[l as usize];
                    if lk.to_edge == ne {
                        approached[(net.lanes[lk.to_lane as usize].index as usize).min(MAX_LANES - 1)] = true;
                    }
                }
            }
            let (mut best_connected, mut best_len) = (-1f32, -1f32);
            for m in 0..n_next {
                if approached[m] && best_connected < b[m] {
                    best_connected = b[m];
                }
                best_len = best_len.max(b[m]);
            }
            if best_connected > 0.0 {
                for k in 0..count {
                    let mut bn: Option<usize> = None;
                    let mut bn_link = 0u32;
                    if ok[k] {
                        for &l in &topo.lane_links[lane(k) as usize] {
                            let lk = &topo.links[l as usize];
                            if lk.to_edge != ne || !allowed(lk.to_lane) {
                                continue;
                            }
                            let m = (net.lanes[lk.to_lane as usize].index as usize).min(MAX_LANES - 1);
                            let better = match bn {
                                None => true,
                                Some(o) => {
                                    b[o] < b[m] || (b[o] == b[m] && (next_off[o].abs() > next_off[m].abs() || (next_off[o].abs() == next_off[m].abs() && m < o)))
                                }
                            };
                            if better {
                                bn = Some(m);
                                bn_link = l;
                            }
                        }
                        if let Some(o) = bn {
                            if b[o] == best_connected && next_off[o].abs() < 2 {
                                a[k] += best_len;
                            } else {
                                a[k] += b[o];
                            }
                            off[k] = next_off[o];
                        }
                    }
                    match bn {
                        Some(o) if next_ok[o] || b[o] > 0.0 => {
                            let lk = &topo.links[bn_link as usize];
                            prio[k] = i32::from(lk.tl.is_some() || lk.state.is_ascii_uppercase());
                        }
                        _ => ok[k] = false,
                    }
                    if a[bi] < a[k] || (a[bi] == a[k] && off[bi].abs() > off[k].abs()) || (a[bi] == a[k] && off[bi].abs() == off[k].abs() && prio[bi] < prio[k]) {
                        bi = k;
                        bmax = k;
                    } else if a[bi] == a[k] && off[bi].abs() == off[k].abs() && prio[bi] == prio[k] {
                        bmax = k;
                    }
                }
            } else {
                let mut best_dist = count as i32;
                let mut best_next = 0;
                for k in 0..count {
                    if !ok[k] {
                        continue;
                    }
                    for &l in &topo.lane_links[lane(k) as usize] {
                        let lk = &topo.links[l as usize];
                        if lk.to_edge != ne {
                            continue;
                        }
                        let m = (net.lanes[lk.to_lane as usize].index as usize).min(MAX_LANES - 1);
                        if best_dist > next_off[m].abs() {
                            best_dist = next_off[m].abs();
                            bi = k;
                            bmax = k;
                            best_next = m;
                        }
                    }
                }
                a[bi] += b[best_next];
            }
            for k in 0..count {
                if a[k] < a[bi] || (a[k] == a[bi] && off[k].abs() > off[bi].abs()) || prio[k] < prio[bi] {
                    off[k] = nearer(k, bi, bmax);
                    if prio[k] < prio[bi] {
                        a[k] = whole[k];
                    }
                } else {
                    off[k] = 0;
                }
            }
        }
        let mut right_banned = false;
        let mut left_banned = -1i32;
        for k in 0..count {
            if off[k] == 0 || ok[k] {
                continue;
            }
            let l = &net.lanes[lane(k) as usize];
            if off[k] < 0 && (l.change_right & vt.vclass != vt.vclass || k == 0 || !allowed(lane(k - 1)) || right_banned) {
                right_banned = true;
                if a[k] == whole[k] {
                    a[k] = 0.0;
                }
            } else if off[k] > 0 && (l.change_left & vt.vclass != vt.vclass || k + 1 >= count || !allowed(lane(k + 1))) {
                left_banned = k as i32;
            }
        }
        for q in (0..=left_banned).rev() {
            if a[q as usize] == whole[q as usize] {
                a[q as usize] = 0.0;
            }
        }
        b = a;
        next_off = off;
        next_ok = ok;
    }
    let count = (first.lane_count as usize).min(MAX_LANES);
    let mut best_len = b[..count].iter().copied().fold(-1.0, f32::max);
    let mut depart = 0.0;
    if best_len > BEST_LANE_LOOKAHEAD {
        depart = (vt.length + 0.1).min(net.lanes[first.first_lane as usize].length);
        best_len = (best_len - depart).min(BEST_LANE_LOOKAHEAD);
    }
    let mut mask = 0;
    for k in 0..count {
        if b[k] - depart >= best_len && allowed(first.first_lane + k as u32) {
            mask |= 1 << k;
        }
    }
    mask
}
