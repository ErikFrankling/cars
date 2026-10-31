//! Detector placement and phase assignment of MSActuatedTrafficLightLogic::init.

use rustc_hash::{FxHashMap, FxHashSet};

use crate::net::{vclass_bit, Net, TlsLogic};
use crate::topology::Topology;

const DETECTOR_GAP: f32 = 2.0;
const PASSING_TIME: f32 = 1.9;
const LENGTH_WITH_GAP: f32 = 7.5;

#[derive(Default)]
pub struct Actuation {
    /// Lane carrying a loop and the loop's position on it.
    pub placements: Vec<(u32, f32)>,
    /// For each phase, the lanes carrying the loops that may extend it.
    pub phase_loops: Vec<Vec<u32>>,
}

fn is_green_phase(state: &[u8]) -> bool {
    state.iter().any(|&c| c == b'G' || c == b'g') && !state.iter().any(|&c| c == b'y' || c == b'Y')
}

pub fn build(net: &Net, topo: &Topology, t: &TlsLogic, links: &[u32]) -> Actuation {
    let n = t.phases.first().map_or(0, |p| p.state.len());
    let mut links_at: Vec<Vec<u32>> = vec![Vec::new(); n];
    for &l in links {
        let i = topo.links[l as usize].tl_index as usize;
        if i < n {
            links_at[i].push(l);
        }
    }
    let lanes_at: Vec<Vec<u32>> = links_at
        .iter()
        .map(|ls| {
            let mut out: Vec<u32> = Vec::new();
            for &l in ls {
                let lane = topo.links[l as usize].from_lane;
                if !out.contains(&lane) {
                    out.push(lane);
                }
            }
            out
        })
        .collect();
    let vulnerable = vclass_bit("pedestrian") | vclass_bit("wheelchair") | vclass_bit("bicycle") | vclass_bit("scooter");
    let motorized = !(vclass_bit("pedestrian") | vclass_bit("bicycle"));
    let actuated = |p: usize| t.phases[p].min_dur != t.phases[p].max_dur;

    // Build one loop per lane, for lanes that are green in some actuated phase.
    let mut placement: FxHashMap<u32, u32> = FxHashMap::default();
    let mut out = Actuation::default();
    for lanes in &lanes_at {
        for &lane in lanes {
            let info = &net.lanes[lane as usize];
            if info.allow & !vclass_bit("pedestrian") == 0 || placement.contains_key(&lane) {
                continue;
            }
            let mut min_dur = f32::MAX;
            for (p, ph) in t.phases.iter().enumerate() {
                if !actuated(p) {
                    continue;
                }
                for (i, &c) in ph.state.iter().enumerate() {
                    if (c == b'G' || c == b'g') && lanes_at.get(i).is_some_and(|ls| ls.contains(&lane)) {
                        min_dur = min_dur.min(ph.min_dur);
                    }
                }
            }
            if min_dur == f32::MAX {
                continue;
            }
            let distance = (DETECTOR_GAP * info.speed).min((min_dur / PASSING_TIME + 0.5) * LENGTH_WITH_GAP);
            let mut pos = info.length - distance;
            let mut at = lane;
            while pos < 0.0 {
                let inc = &topo.incoming[at as usize];
                if inc.len() != 1 || topo.links[topo.links[inc[0] as usize].entry as usize].tl.is_some() {
                    break;
                }
                at = topo.links[inc[0] as usize].from_lane;
                pos += net.lanes[at as usize].length;
            }
            placement.insert(lane, at);
            out.placements.push((at, pos.max(0.0)));
        }
    }

    let mut never_major = vec![true; n];
    for ph in &t.phases {
        for (i, &c) in ph.state.iter().enumerate() {
            if c == b'G' && i < n {
                never_major[i] = false;
            }
        }
    }
    let mut one_lane = vec![false; n];
    let mut turnaround = vec![true; n];
    for i in 0..n {
        for &lane in &lanes_at[i] {
            let e = &net.edges[net.lanes[lane as usize].edge as usize];
            let motor = (e.first_lane..e.first_lane + e.lane_count)
                .filter(|&l| net.lanes[l as usize].allow & motorized != 0)
                .count();
            if motor == 1 {
                one_lane[i] = true;
                break;
            }
        }
        turnaround[i] = links_at[i].iter().all(|&l| topo.links[l as usize].dir == b't');
    }

    let weak_conflict = |i: usize, state: &[u8]| -> bool {
        for &a in &links_at[i] {
            let la = &topo.links[a as usize];
            for (j, &c) in state.iter().enumerate() {
                if j == i || j >= n || (c != b'G' && c != b'g') {
                    continue;
                }
                for &b in &links_at[j] {
                    let lb = &topo.links[b as usize];
                    if la.junction != lb.junction || la.request_index < 0 || lb.request_index < 0 {
                        continue;
                    }
                    let Some(req) = net.junctions[la.junction as usize].requests.get(la.request_index as usize) else { continue };
                    let foe = req.foes.get(lb.request_index as usize).copied().unwrap_or(false);
                    let foe_lane = &net.lanes[lb.from_lane as usize];
                    if foe && foe_lane.allow & !vulnerable != 0 && foe_lane.edge != net.lanes[la.from_lane as usize].edge {
                        return false;
                    }
                }
            }
        }
        true
    };

    for (p, ph) in t.phases.iter().enumerate() {
        let mut loops = Vec::new();
        if actuated(p) && is_green_phase(&ph.state) {
            let state = &ph.state;
            let has_major = |lanes: &[u32]| {
                state.iter().enumerate().any(|(i, &c)| {
                    c == b'G' && lanes_at.get(i).is_some_and(|ls| ls.iter().any(|l| lanes.contains(l)))
                })
            };
            let mut green: FxHashSet<usize> = FxHashSet::default();
            for i in 0..n.min(state.len()) {
                match state[i] {
                    b'G' => {
                        green.insert(i);
                    }
                    b'g' => {
                        if ((never_major[i] || turnaround[i]) && has_major(&lanes_at[i]))
                            || one_lane[i]
                            || weak_conflict(i, state)
                        {
                            green.insert(i);
                        }
                    }
                    _ => {}
                }
            }
            let links_of = |lane: u32| -> Vec<usize> { (0..n).filter(|&i| lanes_at[i].contains(&lane)).collect() };
            for lanes in &lanes_at {
                for &lane in lanes {
                    let Some(&at) = placement.get(&lane) else { continue };
                    if !links_of(lane).iter().all(|j| green.contains(j)) {
                        continue;
                    }
                    let blocked_next = topo.lane_links[lane as usize].iter().any(|&l| {
                        let link = &topo.links[l as usize];
                        link.dir != b't'
                            && placement.contains_key(&link.to_lane)
                            && !links_of(link.to_lane).iter().all(|j| green.contains(j))
                    });
                    if !blocked_next && !loops.contains(&at) {
                        loops.push(at);
                    }
                }
            }
        }
        out.phase_loops.push(loops);
    }
    out
}
