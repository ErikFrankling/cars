//! Links, foes and crossing conflicts: what `MSRightOfWayJunction`, `MSInternalJunction` and
//! `MSLink::setRequestInformation` compute when SUMO loads a network.

use rustc_hash::FxHashMap;

use crate::net::{EdgeFunc, Net};

pub const NONE: u32 = u32::MAX;

const NO_INTERSECTION: f64 = 10000.0;
const DIVERGENCE_MIN_WIDTH: f64 = 2.5;

#[derive(Clone, Debug, Default)]
pub struct Link {
    pub from_lane: u32,
    /// The lane a vehicle moves onto next: the internal lane if there is one, else the target.
    pub next_lane: u32,
    /// The normal lane the connection finally reaches.
    pub to_lane: u32,
    /// Route matching: the edge of `to_lane`.
    pub to_edge: u32,
    pub via: Option<u32>,
    pub tl: Option<u32>,
    pub tl_index: u32,
    pub state: u8,
    pub dir: u8,
    pub cont: bool,
    pub has_foes: bool,
    pub keep_clear: bool,
    pub length: f32,
    pub visibility: f32,
    pub foe_links: Vec<u32>,
    pub foe_lanes: Vec<u32>,
    pub conflicts: Vec<Conflict>,
    /// The internal lane this link starts from, when it is an exit or second stop link.
    pub internal_before: Option<u32>,
    /// The entry link into the junction this one belongs to.
    pub entry: u32,
    /// Index into the junction's request matrix, if any.
    pub request_index: i32,
    pub junction: u32,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Conflict {
    pub foe_lane: u32,
    pub len_behind: f32,
    pub foe_len_behind: f32,
    pub width: f32,
    pub foe_width: f32,
    pub same_target: bool,
    pub same_source: bool,
    pub cont_lane: bool,
    pub dummy_merge: bool,
}

pub struct Topology {
    pub links: Vec<Link>,
    /// Outgoing links of each lane, in connection order.
    pub lane_links: Vec<Vec<u32>>,
    /// The link that leads onto each lane: only meaningful for internal lanes.
    pub incoming: Vec<Vec<u32>>,
}

fn dist(a: [f32; 2], b: [f32; 2]) -> f64 {
    let (dx, dy) = ((a[0] - b[0]) as f64, (a[1] - b[1]) as f64);
    (dx * dx + dy * dy).sqrt()
}

fn shape_length(s: &[[f32; 2]]) -> f64 {
    s.windows(2).map(|w| dist(w[0], w[1])).sum()
}

/// Positions along `a` where it crosses `b`.
fn intersections(a: &[[f32; 2]], b: &[[f32; 2]]) -> Vec<f64> {
    let mut out = Vec::new();
    let mut at = 0.0;
    for w in a.windows(2) {
        let (p, q) = (w[0], w[1]);
        let seg = dist(p, q);
        for v in b.windows(2) {
            let (r, s) = (v[0], v[1]);
            let d1 = ((q[0] - p[0]) as f64, (q[1] - p[1]) as f64);
            let d2 = ((s[0] - r[0]) as f64, (s[1] - r[1]) as f64);
            let den = d1.0 * d2.1 - d1.1 * d2.0;
            if den.abs() < 1e-9 {
                continue;
            }
            let dx = (r[0] - p[0]) as f64;
            let dy = (r[1] - p[1]) as f64;
            let t = (dx * d2.1 - dy * d2.0) / den;
            let u = (dx * d1.1 - dy * d1.0) / den;
            if (0.0..=1.0).contains(&t) && (0.0..=1.0).contains(&u) {
                out.push(at + t * seg);
            }
        }
        at += seg;
    }
    out
}

/// Direction of travel at a geometric offset, in degrees.
fn angle_at(s: &[[f32; 2]], offset: f64) -> f64 {
    let mut at = 0.0;
    for w in s.windows(2) {
        let seg = dist(w[0], w[1]);
        if at + seg >= offset {
            return ((w[1][1] - w[0][1]) as f64)
                .atan2((w[1][0] - w[0][0]) as f64)
                .to_degrees();
        }
        at += seg;
    }
    let n = s.len();
    ((s[n - 1][1] - s[n - 2][1]) as f64)
        .atan2((s[n - 1][0] - s[n - 2][0]) as f64)
        .to_degrees()
}

fn min_angle_diff(a: f64, b: f64) -> f64 {
    let d = (a - b).rem_euclid(360.0);
    d.min(360.0 - d)
}

fn point_seg_dist(p: [f32; 2], a: [f32; 2], b: [f32; 2]) -> f64 {
    let (ax, ay, bx, by, px, py) = (a[0] as f64, a[1] as f64, b[0] as f64, b[1] as f64, p[0] as f64, p[1] as f64);
    let (dx, dy) = (bx - ax, by - ay);
    let l2 = dx * dx + dy * dy;
    let t = if l2 < 1e-12 { 0.0 } else { (((px - ax) * dx + (py - ay) * dy) / l2).clamp(0.0, 1.0) };
    let (cx, cy) = (ax + t * dx, ay + t * dy);
    ((px - cx).powi(2) + (py - cy).powi(2)).sqrt()
}

fn point_shape_dist(p: [f32; 2], s: &[[f32; 2]]) -> f64 {
    s.windows(2)
        .map(|w| point_seg_dist(p, w[0], w[1]))
        .fold(f64::MAX, f64::min)
}

/// `MSLink::computeDistToDivergence` for ordinary road lanes.
fn dist_to_divergence(net: &Net, lane: u32, sibling: u32, min_dist: f64, same_source: bool) -> f64 {
    let (la, sa) = (&net.lanes[lane as usize], &net.lanes[sibling as usize]);
    let mut l = la.shape.clone();
    let mut s = sa.shape.clone();
    let (length, sib_length) = (shape_length(&l), shape_length(&s));
    if !same_source {
        l.reverse();
        s.reverse();
    }
    let (mut lbc_s, mut lbc_l) = (0.0, 0.0);
    if !l.is_empty() && !s.is_empty() && dist(*l.last().unwrap(), *s.last().unwrap()) > min_dist {
        let dl: Vec<f64> = l.iter().map(|p| point_shape_dist(*p, &s)).collect();
        let ds: Vec<f64> = s.iter().map(|p| point_shape_dist(*p, &l)).collect();
        if *ds.last().unwrap() > min_dist && *dl.last().unwrap() > min_dist {
            for j in (0..s.len().saturating_sub(1)).rev() {
                let seg = dist(s[j], s[j + 1]);
                if ds[j] > min_dist {
                    lbc_s += seg;
                } else {
                    lbc_s += seg - (min_dist - ds[j]) * seg / (ds[j + 1] - ds[j]);
                    break;
                }
            }
            for i in (0..l.len().saturating_sub(1)).rev() {
                let seg = dist(l[i], l[i + 1]);
                if dl[i] > min_dist {
                    lbc_l += seg;
                } else {
                    lbc_l += seg - (min_dist - dl[i]) * seg / (dl[i + 1] - dl[i]);
                    break;
                }
            }
        }
    }
    let d1 = sa.length as f64 - lbc_s;
    let d2 = la.length as f64 - lbc_l;
    d1.max(d2).min(sib_length).min(length)
}

impl Topology {
    pub fn build(net: &Net) -> Self {
        let n_lanes = net.lanes.len();
        let mut links: Vec<Link> = Vec::with_capacity(net.conns.len());
        let mut lane_links: Vec<Vec<u32>> = vec![Vec::new(); n_lanes];
        let mut incoming: Vec<Vec<u32>> = vec![Vec::new(); n_lanes];

        for c in &net.conns {
            let Some(from_lane) = net.lane_of(c.from_edge, c.from_lane) else { continue };
            let Some(to_lane) = net.lane_of(c.to_edge, c.to_lane) else { continue };
            let next_lane = c.via.unwrap_or(to_lane);
            let length = match c.via {
                Some(v) => net.lanes[v as usize].length,
                None => {
                    let a = net.lanes[from_lane as usize].shape.last().copied();
                    let b = net.lanes[to_lane as usize].shape.first().copied();
                    match (a, b) {
                        (Some(a), Some(b)) => dist(a, b) as f32,
                        _ => 0.0,
                    }
                }
            };
            let id = links.len() as u32;
            let from_internal = net.is_internal_lane(from_lane);
            links.push(Link {
                from_lane,
                next_lane,
                to_lane,
                to_edge: c.to_edge,
                via: c.via,
                tl: c.tl,
                tl_index: c.link_index.max(0) as u32,
                state: c.state,
                dir: c.dir,
                cont: false,
                has_foes: false,
                keep_clear: c.keep_clear,
                length,
                visibility: if c.state == b'Z' { 100.0 } else { c.visibility },
                foe_links: Vec::new(),
                foe_lanes: Vec::new(),
                conflicts: Vec::new(),
                internal_before: from_internal.then_some(from_lane),
                entry: id,
                request_index: -1,
                junction: NONE,
            });
            lane_links[from_lane as usize].push(id);
            incoming[next_lane as usize].push(id);
        }

        let mut topo = Topology { links, lane_links, incoming };
        topo.link_entries(net);
        topo.right_of_way(net);
        topo.internal_junctions(net);
        topo.conflicts(net);
        topo
    }

    fn link_entries(&mut self, net: &Net) {
        // Follow internal lanes back to the normal lane to find the entry link.
        for id in 0..self.links.len() {
            let mut at = id as u32;
            let mut guard = 0;
            while let Some(before) = self.links[at as usize].internal_before {
                let Some(&inc) = self.incoming[before as usize].first() else { break };
                at = inc;
                guard += 1;
                if guard > 8 {
                    break;
                }
            }
            self.links[id].entry = at;
        }
        let _ = net;
    }

    fn right_of_way(&mut self, net: &Net) {
        for (jid, j) in net.junctions.iter().enumerate() {
            if j.requests.is_empty() || j.jtype == "internal" {
                continue;
            }
            // All incoming links, in the order of incLanes and each lane's connections.
            let mut all: Vec<u32> = Vec::new();
            for lane in &j.inc_lanes {
                if let Some(&l) = net.lane_index.get(lane) {
                    // Only vehicle links: crossings and walking areas are not loaded.
                    all.extend_from_slice(&self.lane_links[l as usize]);
                }
            }
            let int_lanes: Vec<Option<u32>> = j
                .int_lanes
                .iter()
                .map(|l| net.lane_index.get(l).copied())
                .collect();
            let has_foes = j.requests.iter().any(|r| r.response.iter().any(|b| *b));
            for (i, &link) in all.iter().enumerate() {
                let Some(req) = j.requests.get(i) else { continue };
                let mut foe_links = Vec::new();
                let mut foe_lanes = Vec::new();
                for (c, &other) in all.iter().enumerate() {
                    if req.response.get(c).copied().unwrap_or(false) {
                        foe_links.push(other);
                        if let Some(via) = self.links[other as usize].via
                            && let Some(&second) = self.lane_links[via as usize].first()
                            && self.links[second as usize].via.is_some()
                        {
                            foe_links.push(second);
                        }
                    }
                }
                // int_lanes lines up with the request matrix position.
                let mut li = 0usize;
                for c in 0..all.len() {
                    if req.foes.get(c).copied().unwrap_or(false)
                        && let Some(Some(lane)) = int_lanes.get(li)
                    {
                        foe_lanes.push(*lane);
                        if req.response.get(c).copied().unwrap_or(false)
                            && self.incoming[*lane as usize].len() == 1
                        {
                            let before = self.links[self.incoming[*lane as usize][0] as usize].from_lane;
                            if net.is_internal_lane(before) {
                                foe_lanes.push(before);
                            }
                        }
                    }
                    li += 1;
                }
                let l = &mut self.links[link as usize];
                l.foe_links = foe_links;
                l.foe_lanes = foe_lanes.clone();
                l.has_foes = has_foes;
                l.cont = req.cont;
                l.request_index = req.index as i32;
                l.junction = jid as u32;
                if !req.cont
                    && let Some(via) = l.via
                    && let Some(&exit) = self.lane_links[via as usize].first()
                {
                    let e = &mut self.links[exit as usize];
                    e.foe_lanes = foe_lanes;
                    e.junction = jid as u32;
                    e.request_index = req.index as i32;
                }
            }
        }
    }

    fn internal_junctions(&mut self, net: &Net) {
        for (jid, j) in net.junctions.iter().enumerate() {
            if j.jtype != "internal" || j.inc_lanes.is_empty() {
                continue;
            }
            let lanes: Vec<u32> = j.inc_lanes.iter().filter_map(|l| net.lane_index.get(l).copied()).collect();
            let Some(&special) = lanes.first() else { continue };
            let Some(&this_link) = self.lane_links[special as usize].first() else { continue };
            let Some(&entry) = self.incoming[special as usize].first() else { continue };
            let own_index = self.links[entry as usize].request_index;
            let parent = self.links[entry as usize].junction;
            if parent == NONE || own_index < 0 {
                continue;
            }
            let Some(req) = net.junctions[parent as usize].requests.get(own_index as usize) else { continue };
            let response = req.response.clone();
            let test = |bit: i32| bit >= 0 && response.get(bit as usize).copied().unwrap_or(false);
            let mut foe_lanes: Vec<u32> = Vec::new();
            for il in &j.int_lanes {
                let Some(&lane) = net.lane_index.get(il) else { continue };
                for &link in &self.lane_links[lane as usize] {
                    if let Some(via) = self.links[link as usize].via {
                        let foe_index = self.incoming[lane as usize]
                            .first()
                            .map(|&l| self.links[l as usize].request_index)
                            .unwrap_or(-1);
                        if test(foe_index) {
                            foe_lanes.push(lane);
                        }
                        if !foe_lanes.contains(&via) {
                            foe_lanes.push(via);
                        }
                    } else if !foe_lanes.contains(&lane) {
                        foe_lanes.push(lane);
                    }
                }
            }
            let mut foe_links: Vec<u32> = Vec::new();
            for &lane in lanes.iter().skip(1) {
                for &link in &self.lane_links[lane as usize] {
                    let entry_index = self.links[self.links[link as usize].entry as usize].request_index;
                    if test(entry_index) {
                        foe_links.push(link);
                        if let Some(via) = self.links[link as usize].via
                            && let Some(&second) = self.lane_links[via as usize].first()
                            && self.links[second as usize].via.is_some()
                        {
                            foe_links.push(second);
                        }
                    }
                }
            }
            let via = self.links[this_link as usize].via;
            {
                let l = &mut self.links[this_link as usize];
                l.foe_links = foe_links;
                l.foe_lanes = foe_lanes.clone();
                l.has_foes = true;
                l.cont = false;
                l.request_index = own_index;
                l.junction = jid as u32;
            }
            if let Some(via) = via
                && let Some(&exit) = self.lane_links[via as usize].first()
            {
                let e = &mut self.links[exit as usize];
                e.foe_lanes = foe_lanes;
                e.foe_links = Vec::new();
                e.request_index = own_index;
                e.junction = jid as u32;
            }
        }
    }

    /// Crossing points between a link's internal lane and each of its foe lanes.
    fn conflicts(&mut self, net: &Net) {
        let mut raw: FxHashMap<(u32, u32), (f64, f64, bool)> = FxHashMap::default();
        for id in 0..self.links.len() {
            let Some(lane) = self.links[id].internal_before else { continue };
            let foes = self.links[id].foe_lanes.clone();
            for foe in foes {
                let (behind, size, dummy) = self.conflict_info(net, id as u32, lane, foe);
                raw.insert((lane, foe), (behind, size, dummy));
            }
        }
        for id in 0..self.links.len() {
            let Some(lane) = self.links[id].internal_before else { continue };
            let foes = self.links[id].foe_lanes.clone();
            let mut out = Vec::with_capacity(foes.len());
            for foe in foes {
                let (behind, size, dummy) = raw[&(lane, foe)];
                let foe_exit = self.lane_links[foe as usize].first().copied();
                let (foe_behind, foe_size) = match raw.get(&(foe, lane)) {
                    Some(r) => (r.0, r.1),
                    None => self.foe_fallback(net, foe, lane),
                };
                let target = self.links[id].to_lane;
                let this_is_ij = self.links[id].via.is_some();
                let foe_exit_link = foe_exit.map(|f| &self.links[f as usize]);
                let same_target = foe_exit_link.is_some_and(|f| f.next_lane == self.links[id].next_lane && f.to_lane == target)
                    && !this_is_ij
                    && foe_exit_link.is_some_and(|f| f.via.is_none());
                let same_source = self.normal_predecessor(net, lane) == self.normal_predecessor(net, foe);
                let exit_after_ij = self.is_exit_after_ij(id as u32);
                let cont_lane = foe_exit_link.is_some_and(|f| f.via.is_some()) && !(this_is_ij || exit_after_ij);
                out.push(Conflict {
                    foe_lane: foe,
                    len_behind: behind as f32,
                    foe_len_behind: foe_behind as f32,
                    width: if same_target || same_source { 0.0 } else { size as f32 },
                    foe_width: if same_target || same_source { 0.0 } else { foe_size as f32 },
                    same_target,
                    same_source,
                    cont_lane,
                    dummy_merge: dummy,
                });
            }
            self.links[id].conflicts = out;
        }
    }

    fn is_exit_after_ij(&self, link: u32) -> bool {
        let l = &self.links[link as usize];
        let Some(before) = l.internal_before else { return false };
        let inc = &self.incoming[before as usize];
        inc.len() == 1 && {
            let v = &self.links[inc[0] as usize];
            v.internal_before.is_some() && v.via.is_some()
        }
    }

    fn normal_predecessor(&self, net: &Net, lane: u32) -> u32 {
        let mut at = lane;
        let mut guard = 0;
        while net.is_internal_lane(at) && guard < 8 {
            let Some(&inc) = self.incoming[at as usize].first() else { break };
            at = self.links[inc as usize].from_lane;
            guard += 1;
        }
        at
    }

    fn foe_fallback(&self, net: &Net, foe: u32, lane: u32) -> (f64, f64) {
        let exit = self.lane_links[foe as usize].first().copied().unwrap_or(0);
        let (b, s, _) = self.conflict_info(net, exit, foe, lane);
        (b, s)
    }

    fn conflict_info(&self, net: &Net, link: u32, lane: u32, foe: u32) -> (f64, f64, bool) {
        let la = &net.lanes[lane as usize];
        let fo = &net.lanes[foe as usize];
        let l = &self.links[link as usize];
        let before_ij = self.lane_links[lane as usize]
            .first()
            .map(|&f| self.links[f as usize].via.is_some())
            .unwrap_or(false);
        let foe_first = self.lane_links[foe as usize].first().copied();
        let same_target = foe_first.is_some_and(|f| self.links[f as usize].next_lane == l.next_lane);
        let foe_cont = foe_first.is_some_and(|f| self.links[f as usize].via.is_some());
        let shapes_cross = !intersections(&la.shape, &fo.shape).is_empty();
        if same_target && !before_ij && !(foe_cont && shapes_cross) {
            let min_dist = DIVERGENCE_MIN_WIDTH.min(0.5 * (la.width + fo.width) as f64);
            let (a, b) = (la.shape.last().copied(), fo.shape.last().copied());
            if let (Some(a), Some(b)) = (a, b)
                && dist(a, b) >= min_dist
            {
                return (0.0, fo.width as f64, true);
            }
            let d = dist_to_divergence(net, lane, foe, min_dist, false);
            return (geom_to_lane(la, d), fo.width as f64, false);
        }
        if self.normal_predecessor(net, lane) == self.normal_predecessor(net, foe) && !shapes_cross {
            let min_dist = DIVERGENCE_MIN_WIDTH.min(0.5 * (la.width + fo.width) as f64);
            let d = dist_to_divergence(net, lane, foe, min_dist, true);
            return (la.length as f64 - geom_to_lane(la, d), fo.width as f64, false);
        }
        let mut hits1 = intersections(&la.shape, &fo.shape);
        hits1.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let mut hits2 = intersections(&fo.shape, &la.shape);
        hits2.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let mut have = !hits1.is_empty();
        let mut at1 = hits1.last().copied().unwrap_or(-NO_INTERSECTION);
        let mut at2 = hits2.last().copied().unwrap_or(0.0);
        if !have && foe_cont {
            if let Some(&wait) = fo.shape.last() {
                let d = point_shape_dist(wait, &la.shape);
                if d < (la.width / 2.0) as f64 {
                    at1 = nearest_offset(&la.shape, wait);
                    at2 = shape_length(&fo.shape);
                    have = true;
                }
            }
        }
        let mut size = fo.width as f64;
        if have {
            let diff = min_angle_diff(angle_at(&la.shape, at1), angle_at(&fo.shape, at2));
            let factor = 1.0 / diff.to_radians().sin().max(0.2) * 2.0 - 1.0;
            size = (size * factor).min(la.length as f64);
            at1 = (at1 - size / 2.0).max(0.0);
            at1 = geom_to_lane(la, at1);
        }
        (la.length as f64 - at1, size, false)
    }

    pub fn is_normal_link(&self, net: &Net, link: u32) -> bool {
        net.edges[net.lanes[self.links[link as usize].from_lane as usize].edge as usize].func != EdgeFunc::Internal
    }
}

fn geom_to_lane(l: &crate::net::Lane, pos: f64) -> f64 {
    let g = shape_length(&l.shape);
    if g > 1e-6 { pos * l.length as f64 / g } else { pos }
}

fn nearest_offset(s: &[[f32; 2]], p: [f32; 2]) -> f64 {
    let mut best = (f64::MAX, 0.0);
    let mut at = 0.0;
    for w in s.windows(2) {
        let seg = dist(w[0], w[1]);
        let d = point_seg_dist(p, w[0], w[1]);
        if d < best.0 {
            let (ax, ay, bx, by) = (w[0][0] as f64, w[0][1] as f64, w[1][0] as f64, w[1][1] as f64);
            let (dx, dy) = (bx - ax, by - ay);
            let t = if seg < 1e-9 { 0.0 } else { (((p[0] as f64 - ax) * dx + (p[1] as f64 - ay) * dy) / (seg * seg)).clamp(0.0, 1.0) };
            best = (d, at + t * seg);
        }
        at += seg;
    }
    best.1
}
