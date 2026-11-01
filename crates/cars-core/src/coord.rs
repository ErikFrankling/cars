//! Signal-free junctions: the geometry pre-pass and the tables the coordinator kernels read.
//! Conflicts come from swept paths on internal lane shapes, never from SUMO's foe bits, which answer
//! a different question. research/truth/scripts/ci_model.py is the reference for every function here.

use bytemuck::{Pod, Zeroable};
use rustc_hash::FxHashMap;

use crate::net::{EdgeFunc, Net};
use crate::topology::{NONE, Topology};

pub const K_LANE: u32 = 6;
pub const K_BOX: u32 = 16;
pub const N_CLASS: u32 = 6;
pub const PLAN_MAX: u32 = 32;
pub const AUD_MAX: u32 = 32;
pub const STATS_PER_REPLICA: u32 = 32;
pub const EVENTS_MAX: u32 = 4095;
const DS: f64 = 0.25;
const MIN_LANE: f32 = 25.0;
const FRACTIONS: [f64; N_CLASS as usize] = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0];

pub const MODE_SUMO: u32 = 0;
pub const MODE_FREE: u32 = 1;
pub const MODE_SIGNAL: u32 = 2;
/// Reserved for mixed traffic: AVs run the schedule, humans a signal, with both sharing `cj_rel`.
pub const MODE_MIXED: u32 = 3;

pub const LANE_CJ: u32 = 8;
pub const LANE_CJ_EXIT: u32 = 16;
pub const L_COORD: u32 = 1 << 17;

pub const CJ_NONE: u32 = 0;
pub const CJ_ADVISED: u32 = 1;
pub const CJ_FIRM: u32 = 2;
pub const CJ_BOX: u32 = 3;
pub const CJ_PENDING: u32 = 4;
pub const CJ_STATE_MASK: u32 = 15;

/// Indices into the per replica statistics.
pub mod stat {
    pub const LOSS: usize = 0;
    pub const STOPS: usize = 1;
    pub const BOX_BLOCK: usize = 2;
    pub const CROSS_UNGRANTED: usize = 3;
    pub const STOP_CURVE: usize = 4;
    pub const GRANTS: usize = 5;
    pub const ABORTS: usize = 6;
    pub const LATE: usize = 7;
    pub const LATE_COMMITTED: usize = 8;
    pub const PONR_ABORT: usize = 9;
    pub const OVERLAP_STEPS: usize = 10;
    pub const MSG_SENT: usize = 11;
    pub const MSG_LOST: usize = 12;
    pub const A2: usize = 13;
    pub const A2N: usize = 14;
    pub const NEG_CREDIT: usize = 15;
    pub const STALLS: usize = 16;
    pub const ERR_ABS: usize = 17;
    pub const ERR_N: usize = 18;
    pub const ERR_BIG: usize = 19;
    pub const AUD_OVERFLOW: usize = 20;
    pub const BOX_OVERFLOW: usize = 21;
    pub const ADVISED_STEPS: usize = 22;
    pub const FIRM_STEPS: usize = 23;
    pub const STALL_BOX: usize = 24;
    pub const YIELDS: usize = 25;
    pub const HOLDS: usize = 26;
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjCfg {
    pub length: f32,
    pub width: f32,
    pub s0: f32,
    pub tau: f32,
    pub accel: f32,
    pub b_plan: f32,
    pub b_s: f32,
    pub b_e: f32,
    pub t_r: f32,
    pub m_t: f32,
    pub level_b: u32,
    pub tick_steps: u32,
    pub t_firm: f32,
    pub a_max: f32,
    pub unit: f32,
    pub exit_check: u32,
    pub ponr: u32,
    pub perception: u32,
    pub audit: u32,
    pub p_loss: f32,
    pub blackout_t0: f32,
    pub blackout_t1: f32,
    pub crash_t0: f32,
    pub crash_t1: f32,
    pub fallback: u32,
    pub stall_rate: f32,
    pub stall_t: f32,
    pub warm: f32,
    pub chan: u32,
    pub r50: f32,
    pub p_floor: f32,
    pub burst_len: f32,
    pub burst_every: f32,
    pub sig_min: f32,
    pub sig_max: f32,
    pub sig_gap: f32,
    pub sig_lost: f32,
    pub sig_start: f32,
    pub n_junctions: u32,
    pub n_apps: u32,
    pub n_exits: u32,
    pub pad: [u32; 1],
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjJunction {
    pub app_start: u32,
    pub app_count: u32,
    pub exit_start: u32,
    pub exit_count: u32,
    pub mov_start: u32,
    pub mov_count: u32,
    pub rel_start: u32,
    pub rel_count: u32,
    pub plan_start: u32,
    pub plan_n: u32,
    pub aud_start: u32,
    pub aud_n: u32,
    pub tick_phase: u32,
    pub mode: u32,
    pub replica: u32,
    pub seq: u32,
    pub cx: f32,
    pub cy: f32,
    pub awsc_free: f32,
    pub frozen: u32,
    pub group_mask: u32,
    pub phase: u32,
    pub phase_t: f32,
    pub switch_t: f32,
    pub stall_active: u32,
    pub stall_trip: u32,
    pub stall_mov: u32,
    pub stall_seq: u32,
    pub stall_detect: f32,
    pub stall_until: f32,
    pub p_load: f32,
    pub pad: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjLink {
    pub junction: u32,
    pub from_lane: u32,
    pub to_lane: u32,
    pub conf_start: u32,
    pub conf_count: u32,
    pub pair_start: u32,
    pub pair_count: u32,
    pub path_len: f32,
    pub v_turn: f32,
    pub v_lane: f32,
    pub v_after: f32,
    pub group: u32,
    pub conf_lanes: u32,
    pub path_start: u32,
    pub path_n: u32,
    pub sim_link: u32,
    pub dir_in: [f32; 2],
    pub dir_out: [f32; 2],
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjConflict {
    pub rel_index: u32,
    pub rev_index: u32,
    pub foe: u32,
    pub s_in: f32,
    pub s_out: f32,
    pub foe_s_in: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjPair {
    pub other: u32,
    pub is_exit: u32,
    pub table: u32,
    pub s_end: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjMovK {
    pub vk: f32,
    pub vout: f32,
    pub t_clear: f32,
    pub pad: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjApp {
    pub sim_lane: u32,
    pub junction: u32,
    pub ord: u32,
    pub req_start: u32,
    pub n_req: u32,
    pub mov_start: u32,
    pub mov_count: u32,
    pub speed: f32,
    pub length: f32,
    pub line_ref: u32,
    pub line_t: f32,
    pub s_line_ref: u32,
    pub s_line_t: f32,
    pub s_ptr: u32,
    pub s_cand_state: u32,
    pub s_cand_k: u32,
    pub s_cand_t: f32,
    pub s_cand_score: f32,
    pub box_tail: u32,
    pub pad: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjExit {
    pub sim_lane: u32,
    pub junction: u32,
    pub length: f32,
    pub exit_ref: u32,
    pub exit_t: f32,
    pub s_exit_ref: u32,
    pub s_exit_t: f32,
    pub n_on_lane: u32,
    pub has_tail: u32,
    pub tail_x: f32,
    pub tail_v: f32,
    pub n_committed: u32,
    pub n_armed: u32,
    pub n_box: u32,
    pub block_t0: f32,
    pub block_t1: f32,
    pub cap_interval: f32,
    pub sink_ready: f32,
    pub seq: u32,
    pub pad: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjReq {
    pub veh: u32,
    pub link: u32,
    pub d: f32,
    pub v: f32,
    pub age_t: f32,
    pub trip: u32,
    pub t_plan: f32,
    pub k_plan: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjBox {
    pub veh: u32,
    pub seq: u32,
    pub stamp: u32,
    pub mov: u32,
    pub s: f32,
    pub v: f32,
    pub trip: u32,
    pub pad: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjAud {
    pub f: [f32; 2],
    pub r: [f32; 2],
    pub trip: u32,
    pub mov: u32,
    pub s: f32,
    pub v: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjEvent {
    pub step: u32,
    pub trip_a: u32,
    pub trip_b: u32,
    pub junction: u32,
    pub mov_a: u32,
    pub mov_b: u32,
    pub s_a: f32,
    pub s_b: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuCjLaneInfo {
    pub app: u32,
    pub exit: u32,
    pub box_mov: u32,
    pub s_offset: f32,
}

#[derive(Clone, Debug)]
pub enum Select {
    /// Junction ids.
    Ids(Vec<String>),
    /// Every junction of more than two approaches that the build can coordinate.
    All,
    /// Every junction inside x0,y0,x1,y1.
    Box([f32; 4]),
}

/// One fault: a lane whose far end is closed or metered between two times.
#[derive(Clone, Debug)]
pub struct ExitFault {
    pub lane_prefix: String,
    pub t0: f32,
    pub t1: f32,
    /// veh/h through the end, 0 for fully closed.
    pub cap: f32,
}

#[derive(Clone, Debug)]
pub struct CoordConfig {
    pub select: Select,
    pub mode: u32,
    /// Per junction exceptions to `mode`: one junction can run a signal among signal-free ones.
    pub modes: FxHashMap<String, u32>,
    pub level_b: bool,
    pub length: f64,
    pub width: f64,
    pub s0: f64,
    pub tau: f64,
    pub accel: f64,
    pub b_plan: f64,
    pub b_s: f64,
    pub b_e: f64,
    pub t_r: f64,
    pub a_lat: f64,
    pub m_lat: f64,
    pub m_t: f64,
    pub t_firm: f64,
    pub a_max: f64,
    pub exit_check: bool,
    pub ponr: bool,
    pub perception: bool,
    pub audit: bool,
    pub p_loss: f32,
    pub blackout: Option<(f32, f32)>,
    pub crash: Option<(f32, f32)>,
    pub fallback_awsc: bool,
    pub stall_rate: f32,
    pub stall_t: f32,
    pub warm: f32,
    /// 0 fixed loss only; 1 the statistical channel of report 08.
    pub chan: u32,
    pub r50: f32,
    pub p_floor: f32,
    pub burst_len: f32,
    pub burst_every: f32,
    pub sig_min: f32,
    pub sig_max: f32,
    pub sig_gap: f32,
    pub sig_lost: f32,
    pub sig_start: f32,
    pub exit_faults: Vec<ExitFault>,
}

impl Default for CoordConfig {
    fn default() -> Self {
        Self {
            select: Select::All,
            mode: MODE_FREE,
            modes: FxHashMap::default(),
            level_b: false,
            length: 5.0,
            width: 1.8,
            s0: 2.0,
            tau: 0.8,
            accel: 2.6,
            b_plan: 2.5,
            b_s: 4.5,
            b_e: 7.0,
            t_r: 0.3,
            a_lat: 2.5,
            m_lat: 0.5,
            m_t: 0.3,
            t_firm: 4.0,
            a_max: 90.0,
            exit_check: true,
            ponr: true,
            perception: true,
            audit: true,
            p_loss: 0.0,
            blackout: None,
            crash: None,
            fallback_awsc: true,
            stall_rate: 0.0,
            stall_t: 15.0,
            warm: 0.0,
            chan: 0,
            r50: 470.0,
            p_floor: 0.0,
            burst_len: 0.5,
            burst_every: 30.0,
            sig_min: 4.0,
            sig_max: 60.0,
            sig_gap: 1.0,
            sig_lost: 0.0,
            sig_start: 0.0,
            exit_faults: Vec::new(),
        }
    }
}

impl CoordConfig {
    pub fn human(mut self) -> Self {
        self.tau = 1.4;
        self.s0 = 2.5;
        self.t_r = 1.0;
        self.m_t = 0.5;
        self.sig_lost = 4.0;
        self.sig_start = 1.0;
        self
    }
}

/// A movement: a path from a stop line through the junction to an exit lane.
struct Mov {
    from: u32,
    to: u32,
    sim_link: u32,
    chain: Vec<u32>,
    s: Vec<f64>,
    xy: Vec<[f64; 2]>,
    p: f64,
    vm: f64,
    v_lane: f64,
    v_after: f64,
    vk: [f64; N_CLASS as usize],
    group: u32,
}

impl Mov {
    /// How long the front takes to travel s from the stop line, starting at v0.
    fn time(&self, v0: f64, s: f64, a: f64) -> f64 {
        if s <= 0.0 {
            return 0.0;
        }
        let (mut t, mut v) = (0.0, v0);
        for (cap, mut seg) in [(self.vm, s.min(self.p)), (self.v_after, (s - self.p).max(0.0))] {
            if seg <= 0.0 {
                continue;
            }
            if v < cap {
                let da = (cap * cap - v * v) / (2.0 * a);
                if da >= seg {
                    let vn = (v * v + 2.0 * a * seg).sqrt();
                    t += (vn - v) / a;
                    v = vn;
                    continue;
                }
                t += (cap - v) / a;
                seg -= da;
                v = cap;
            }
            t += seg / v.max(1e-3);
        }
        t
    }
    fn speed_along(&self, v0: f64, s: f64, a: f64) -> f64 {
        if s <= self.p {
            return self.vm.min((v0 * v0 + 2.0 * a * s).sqrt());
        }
        let vp = self.vm.min((v0 * v0 + 2.0 * a * self.p).sqrt());
        self.v_after.min((vp * vp + 2.0 * a * (s - self.p)).sqrt())
    }
}

/// The smallest t_m - t_p that keeps m behind p by L + s0 + v tau over the whole shared stretch.
fn pair_headway(p: &Mov, kp: usize, m: &Mov, k: usize, x0: f64, end: f64, is_exit: bool, c: &CoordConfig) -> f64 {
    let l0 = c.length + c.s0;
    let mut h = -1e9f64;
    let mut x = x0;
    while x <= end + 0.01 {
        if is_exit {
            let sm = m.p + x;
            let vm = m.speed_along(m.vk[k], sm.max(0.0), c.accel);
            let sp = p.p + x + l0 + vm * c.tau;
            h = h.max(p.time(p.vk[kp], sp, c.accel) - m.time(m.vk[k], sm.max(0.0), c.accel));
        } else {
            let vm = m.speed_along(m.vk[k], x, c.accel);
            let sp = x + l0 + vm * c.tau;
            h = h.max(p.time(p.vk[kp], sp, c.accel) - m.time(m.vk[k], x, c.accel));
        }
        x += 1.0;
    }
    h
}

fn sample_lane(net: &Net, lane: u32, base: f64, s: &mut Vec<f64>, xy: &mut Vec<[f64; 2]>) -> f64 {
    let l = &net.lanes[lane as usize];
    let length = l.length as f64;
    let mut cum = vec![0.0f64];
    for w in l.shape.windows(2) {
        cum.push(cum.last().unwrap() + ((w[1][0] - w[0][0]) as f64).hypot((w[1][1] - w[0][1]) as f64));
    }
    let total = *cum.last().unwrap();
    let n = (length / DS).ceil().max(1.0) as usize;
    let mut seg = 0usize;
    for i in 0..=n {
        let sim = length * i as f64 / n as f64;
        let geo = sim / length.max(1e-6) * total;
        while seg + 2 < l.shape.len() && cum[seg + 1] < geo {
            seg += 1;
        }
        let d = (cum[seg + 1] - cum[seg]).max(1e-9);
        let u = ((geo - cum[seg]) / d).clamp(0.0, 1.0);
        let (a, b) = (l.shape[seg], l.shape[seg + 1]);
        let p = [a[0] as f64 + u * (b[0] - a[0]) as f64, a[1] as f64 + u * (b[1] - a[1]) as f64];
        if i == 0 && !s.is_empty() {
            continue;
        }
        s.push(base + sim);
        xy.push(p);
    }
    length
}

/// The direction of a lane at its end, or at its start.
fn lane_end_dir(net: &Net, lane: u32, end: bool) -> [f32; 2] {
    let shape = &net.lanes[lane as usize].shape;
    let n = shape.len();
    let (a, b) = if end { (shape[n - 2], shape[n - 1]) } else { (shape[0], shape[1]) };
    let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
    let d = dx.hypot(dy).max(1e-6);
    [dx / d, dy / d]
}

/// Stop curve speed: the fastest a car may go and still stop in d. The same as av_stop_curve in WGSL.
fn stop_curve(d: f64, bc: f64, tr: f64) -> f64 {
    bc * ((tr * tr + 2.0 * (d - 0.5).max(0.0) / bc).sqrt() - tr)
}

#[derive(Default)]
pub struct CoordWorld {
    pub cfg: GpuCjCfg,
    pub junctions: Vec<GpuCjJunction>,
    pub links: Vec<GpuCjLink>,
    pub conflicts: Vec<GpuCjConflict>,
    pub times: Vec<f32>,
    pub pairs: Vec<GpuCjPair>,
    pub head: Vec<f32>,
    pub mov_k: Vec<GpuCjMovK>,
    pub rel_init: Vec<f32>,
    pub apps: Vec<GpuCjApp>,
    pub exits: Vec<GpuCjExit>,
    pub path: Vec<[f32; 2]>,
    pub lane_info: Vec<GpuCjLaneInfo>,
    pub n_req: u32,
    pub n_plan: u32,
    pub n_aud: u32,
    /// Junction id of each `junctions` entry, for the first replica.
    pub ids: Vec<String>,
    /// Junctions asked for that stayed on SUMO's control, and why.
    pub refused: Vec<(String, String)>,
    pub lane_flags: Vec<(u32, u32)>,
    pub link_flags: Vec<u32>,
    /// Sim lane ids of every path, for drawing: internal lanes of each movement.
    pub mov_chain: Vec<Vec<u32>>,
    pub n_replicas: u32,
}

impl CoordWorld {
    pub fn is_coordinated(&self, lane: u32) -> bool {
        self.lane_info.get(lane as usize).is_some_and(|i| i.app != NONE)
    }
    pub fn memory_bytes(&self) -> u64 {
        fn b<T>(v: &[T]) -> u64 {
            std::mem::size_of_val(v) as u64
        }
        b(&self.junctions)
            + b(&self.links)
            + b(&self.conflicts)
            + b(&self.times)
            + b(&self.pairs)
            + b(&self.head)
            + b(&self.mov_k)
            + 2 * b(&self.rel_init)
            + b(&self.apps)
            + b(&self.exits)
            + b(&self.path)
            + b(&self.lane_info)
            + self.n_req as u64 * std::mem::size_of::<GpuCjReq>() as u64
            + self.exits.len() as u64 * K_BOX as u64 * std::mem::size_of::<GpuCjBox>() as u64
            + self.n_plan as u64 * 4
            + self.n_aud as u64 * std::mem::size_of::<GpuCjAud>() as u64
    }
}

fn phase_group(net: &Net, tl: Option<u32>, idx: i32) -> u32 {
    let Some(t) = tl else { return u32::MAX };
    let mut m = 0u32;
    for (i, p) in net.tls[t as usize].phases.iter().enumerate().take(32) {
        if p.state.contains(&b'y') {
            continue;
        }
        if let Some(&c) = p.state.get(idx.max(0) as usize)
            && (c == b'G' || c == b'g')
        {
            m |= 1 << i;
        }
    }
    m
}

/// One replica's data in local indices; `offset` appends it to the world.
pub fn build(net: &Net, topo: &Topology, c: &CoordConfig, dt: f32, seed: u64) -> CoordWorld {
    let mut w = CoordWorld::default();
    let n_lanes = net.lanes.len();
    w.lane_info = vec![GpuCjLaneInfo { app: NONE, exit: NONE, box_mov: NONE, s_offset: 0.0 }; n_lanes];
    let pedestrian: Vec<bool> = {
        let mut p = vec![false; net.junctions.len()];
        for e in net.edges.iter().filter(|e| e.func == EdgeFunc::Pedestrian) {
            let id = e.id.trim_start_matches(':');
            if let Some(cut) = id.rfind('_')
                && let Some(&j) = net.junction_index.get(&id[..cut])
            {
                p[j as usize] = true;
            }
        }
        p
    };
    let mut wanted: Vec<u32> = Vec::new();
    match &c.select {
        Select::Ids(ids) => {
            for id in ids {
                match net.junction_index.get(id) {
                    Some(&j) => wanted.push(j),
                    None => w.refused.push((id.clone(), "unknown id".into())),
                }
            }
        }
        Select::All => wanted.extend(0..net.junctions.len() as u32),
        Select::Box(b) => {
            for (i, j) in net.junctions.iter().enumerate() {
                if j.x >= b[0] && j.y >= b[1] && j.x <= b[2] && j.y <= b[3] {
                    wanted.push(i as u32);
                }
            }
        }
    }
    let explicit = matches!(c.select, Select::Ids(_));
    let mut chosen: Vec<u32> = Vec::new();
    for &j in &wanted {
        let jn = &net.junctions[j as usize];
        if jn.jtype == "internal" || jn.jtype == "dead_end" {
            continue;
        }
        let approaches: std::collections::HashSet<u32> = jn
            .inc_lanes
            .iter()
            .filter_map(|l| net.lane_index.get(l))
            .filter(|&&l| !net.is_internal_lane(l))
            .map(|&l| net.lanes[l as usize].edge)
            .collect();
        if !explicit && approaches.len() < 2 {
            continue;
        }
        if pedestrian[j as usize] {
            w.refused.push((jn.id.clone(), "has pedestrian crossings".into()));
            continue;
        }
        let lanes: Vec<u32> = jn
            .inc_lanes
            .iter()
            .filter_map(|l| net.lane_index.get(l))
            .filter(|&&l| !net.is_internal_lane(l))
            .copied()
            .collect();
        if lanes.len() > 32 {
            w.refused.push((jn.id.clone(), format!("{} approach lanes, over 32", lanes.len())));
            continue;
        }
        let without_via = lanes.iter().flat_map(|&l| topo.lane_links[l as usize].iter()).any(|&k| topo.links[k as usize].via.is_none());
        if without_via {
            w.refused.push((jn.id.clone(), "connection without an internal lane".into()));
            continue;
        }
        // A chain of OSM nodes is one real junction drawn as many: a slot cannot be checked against
        // a 0.2 m exit, nor a stop made on a 3 m approach. These stay on their old control.
        let short_in = lanes.iter().map(|&l| net.lanes[l as usize].length).fold(f32::MAX, f32::min);
        let short_out = lanes
            .iter()
            .flat_map(|&l| topo.lane_links[l as usize].iter())
            .map(|&k| net.lanes[topo.links[k as usize].to_lane as usize].length)
            .fold(f32::MAX, f32::min);
        if short_in.min(short_out) < MIN_LANE {
            w.refused.push((jn.id.clone(), format!("lane of {:.1} m, under {MIN_LANE} m", short_in.min(short_out))));
            continue;
        }
        chosen.push(j);
    }
    let chosen_set: std::collections::HashSet<u32> = chosen.iter().copied().collect();
    let junction_of_lane_end = |lane: u32| -> Option<u32> {
        let e = &net.edges[net.lanes[lane as usize].edge as usize];
        net.junction_index.get(&e.to).copied()
    };
    w.cfg = GpuCjCfg {
        length: c.length as f32,
        width: c.width as f32,
        s0: c.s0 as f32,
        tau: c.tau as f32,
        accel: c.accel as f32,
        b_plan: c.b_plan as f32,
        b_s: c.b_s as f32,
        b_e: c.b_e as f32,
        t_r: c.t_r as f32,
        m_t: c.m_t as f32,
        level_b: u32::from(c.level_b),
        tick_steps: (0.5 / dt).round().max(1.0) as u32,
        t_firm: c.t_firm as f32,
        a_max: c.a_max as f32,
        unit: (c.length + c.s0 + 1.0) as f32,
        exit_check: u32::from(c.exit_check),
        ponr: u32::from(c.ponr),
        perception: u32::from(c.perception),
        audit: u32::from(c.audit),
        p_loss: c.p_loss,
        blackout_t0: c.blackout.map_or(1e30, |b| b.0),
        blackout_t1: c.blackout.map_or(1e30, |b| b.1),
        crash_t0: c.crash.map_or(1e30, |b| b.0),
        crash_t1: c.crash.map_or(1e30, |b| b.1),
        fallback: u32::from(c.fallback_awsc),
        stall_rate: c.stall_rate,
        stall_t: c.stall_t,
        warm: c.warm,
        chan: c.chan,
        r50: c.r50,
        p_floor: c.p_floor,
        burst_len: c.burst_len,
        burst_every: c.burst_every,
        sig_min: c.sig_min,
        sig_max: c.sig_max,
        sig_gap: c.sig_gap,
        sig_lost: c.sig_lost,
        sig_start: c.sig_start,
        ..Default::default()
    };
    let _ = seed;
    let w_swept = c.width + c.m_lat;
    let mut links_flag = vec![0u32; topo.links.len()];
    for (order, &j) in chosen.iter().enumerate() {
        let jn = &net.junctions[j as usize];
        let lanes: Vec<u32> = jn
            .inc_lanes
            .iter()
            .filter_map(|l| net.lane_index.get(l))
            .filter(|&&l| !net.is_internal_lane(l))
            .copied()
            .collect();
        let mut movs: Vec<Mov> = Vec::new();
        for &lane in &lanes {
            for &k in &topo.lane_links[lane as usize] {
                links_flag[k as usize] |= L_COORD;
                let link = &topo.links[k as usize];
                let (mut s, mut xy) = (Vec::new(), Vec::new());
                let mut chain = Vec::new();
                let mut speed = f64::MAX;
                let mut base = 0.0;
                let mut at = link.via.unwrap();
                loop {
                    chain.push(at);
                    speed = speed.min(net.lanes[at as usize].speed as f64);
                    w.lane_info[at as usize].s_offset = base as f32;
                    base += sample_lane(net, at, base, &mut s, &mut xy);
                    let Some(&nk) = topo.lane_links[at as usize].first() else { break };
                    links_flag[nk as usize] |= L_COORD;
                    match topo.links[nk as usize].via {
                        Some(v) => at = v,
                        None => break,
                    }
                }
                let v_lane = net.lanes[lane as usize].speed as f64;
                let v_after = net.lanes[link.to_lane as usize].speed as f64;
                let mut vm = if speed >= v_lane - 1e-3 { v_lane } else { speed * (c.a_lat / 5.5).sqrt() };
                // A short link to another coordinated junction: the car must still be able to stop at its line.
                if junction_of_lane_end(link.to_lane).is_some_and(|x| chosen_set.contains(&x)) {
                    vm = vm.min(stop_curve(net.lanes[link.to_lane as usize].length as f64, c.b_plan, c.t_r));
                }
                let vm = vm.max(1.0);
                movs.push(Mov {
                    from: lane,
                    to: link.to_lane,
                    sim_link: k,
                    chain,
                    p: base,
                    s,
                    xy,
                    vm,
                    v_lane,
                    v_after,
                    vk: FRACTIONS.map(|f| vm * f),
                    group: phase_group(net, link.tl, link.tl_index as i32),
                });
            }
        }
        if movs.is_empty() {
            continue;
        }
        let ji = w.junctions.len() as u32;
        let mov0 = w.links.len() as u32;
        let app0 = w.apps.len() as u32;
        let exit0 = w.exits.len() as u32;
        let rel0 = w.rel_init.len() as u32;
        let mut app_of: FxHashMap<u32, u32> = FxHashMap::default();
        for &lane in &lanes {
            if topo.lane_links[lane as usize].is_empty() {
                continue;
            }
            let at = w.apps.len() as u32;
            app_of.insert(lane, at);
            let links_here = &topo.lane_links[lane as usize];
            let first = movs.iter().position(|m| m.from == lane).unwrap() as u32 + mov0;
            let l = &net.lanes[lane as usize];
            w.apps.push(GpuCjApp {
                sim_lane: lane,
                junction: ji,
                ord: at - app0,
                req_start: w.n_req,
                mov_start: first,
                mov_count: links_here.len() as u32,
                speed: l.speed,
                length: l.length,
                line_ref: NONE,
                s_line_ref: NONE,
                line_t: -1e9,
                s_line_t: -1e9,
                box_tail: NONE,
                ..Default::default()
            });
            w.n_req += K_LANE;
            w.lane_info[lane as usize].app = at;
        }
        let mut exit_of: FxHashMap<u32, u32> = FxHashMap::default();
        for m in &movs {
            if exit_of.contains_key(&m.to) {
                continue;
            }
            let at = w.exits.len() as u32;
            exit_of.insert(m.to, at);
            let l = &net.lanes[m.to as usize];
            let mut e = GpuCjExit {
                sim_lane: m.to,
                junction: ji,
                length: l.length,
                exit_ref: NONE,
                s_exit_ref: NONE,
                exit_t: -1e9,
                s_exit_t: -1e9,
                block_t0: 1e30,
                block_t1: 1e30,
                ..Default::default()
            };
            for f in &c.exit_faults {
                if l.id.starts_with(&f.lane_prefix) {
                    e.block_t0 = f.t0;
                    e.block_t1 = f.t1;
                    e.cap_interval = if f.cap > 0.0 { 3600.0 / f.cap } else { 0.0 };
                }
            }
            w.exits.push(e);
            w.lane_info[m.to as usize].exit = at;
        }
        // Who conflicts with whom.
        let n = movs.len();
        let mut conf: Vec<Vec<(u32, u32, u32, f64, f64, f64)>> = vec![Vec::new(); n];
        let mut div: FxHashMap<(usize, usize), f64> = FxHashMap::default();
        let mut merge: FxHashMap<(usize, usize), f64> = FxHashMap::default();
        let mut rel_n = 0u32;
        for i in 0..n {
            for k in i + 1..n {
                let (a, b) = (&movs[i], &movs[k]);
                let (mut ia0, mut ia1, mut ib0, mut ib1) = (usize::MAX, 0usize, usize::MAX, 0usize);
                for (x, p) in a.xy.iter().enumerate() {
                    for (y, q) in b.xy.iter().enumerate() {
                        let (dx, dy) = (p[0] - q[0], p[1] - q[1]);
                        if dx * dx + dy * dy <= w_swept * w_swept {
                            ia0 = ia0.min(x);
                            ia1 = ia1.max(x);
                            ib0 = ib0.min(y);
                            ib1 = ib1.max(y);
                        }
                    }
                }
                if ia0 == usize::MAX {
                    continue;
                }
                let (sa0, sa1, sb0, sb1) = (a.s[ia0], a.s[ia1], b.s[ib0], b.s[ib1]);
                if a.from == b.from {
                    div.insert((i, k), sb1);
                    div.insert((k, i), sa1);
                    continue;
                }
                if a.to == b.to {
                    merge.insert((i, k), a.p - sa0);
                    merge.insert((k, i), b.p - sb0);
                    continue;
                }
                conf[i].push((rel0 + rel_n, rel0 + rel_n + 1, mov0 + k as u32, sa0, sa1, sb0));
                conf[k].push((rel0 + rel_n + 1, rel0 + rel_n, mov0 + i as u32, sb0, sb1, sa0));
                rel_n += 2;
            }
        }
        w.rel_init.extend(std::iter::repeat_n(-1e9f32, rel_n as usize));
        for (mi, m) in movs.iter().enumerate() {
            let conf_start = w.conflicts.len() as u32;
            let mut conf_lanes = 1u32 << (app_of[&m.from] - app0);
            for &(rel, rev, foe, si, so, fi) in &conf[mi] {
                w.conflicts.push(GpuCjConflict {
                    rel_index: rel,
                    rev_index: rev,
                    foe,
                    s_in: si as f32,
                    s_out: so as f32,
                    foe_s_in: fi as f32,
                });
                for kk in 0..N_CLASS as usize {
                    w.times.push(m.time(m.vk[kk], si, c.accel) as f32);
                }
                for kk in 0..N_CLASS as usize {
                    w.times.push(m.time(m.vk[kk], so + c.length, c.accel) as f32);
                }
                conf_lanes |= 1u32 << (app_of[&movs[(foe - mov0) as usize].from] - app0);
            }
            let pair_start = w.pairs.len() as u32;
            for (pi, p) in movs.iter().enumerate() {
                let same = p.from == m.from;
                let exit = p.to == m.to;
                if exit {
                    conf_lanes |= 1u32 << (app_of[&p.from] - app0);
                }
                if same {
                    let end = div.get(&(pi, mi)).copied().filter(|_| pi != mi).unwrap_or(m.p + 60.0);
                    let table = w.head.len() as u32;
                    for kp in 0..N_CLASS as usize {
                        for kk in 0..N_CLASS as usize {
                            w.head.push(pair_headway(p, kp, m, kk, 0.0, end, false, c) as f32);
                        }
                    }
                    w.pairs.push(GpuCjPair { other: mov0 + pi as u32, is_exit: 0, table, s_end: end as f32 });
                }
                if exit {
                    let x0 = -merge.get(&(mi, pi)).copied().unwrap_or(0.0).max(0.0);
                    let table = w.head.len() as u32;
                    for kp in 0..N_CLASS as usize {
                        for kk in 0..N_CLASS as usize {
                            w.head.push(pair_headway(p, kp, m, kk, x0, 60.0, true, c) as f32);
                        }
                    }
                    w.pairs.push(GpuCjPair { other: mov0 + pi as u32, is_exit: 1, table, s_end: -x0 as f32 });
                }
            }
            for kk in 0..N_CLASS as usize {
                let v0 = m.vk[kk];
                w.mov_k.push(GpuCjMovK {
                    vk: v0 as f32,
                    vout: m.vm.min((v0 * v0 + 2.0 * c.accel * m.p).sqrt()) as f32,
                    t_clear: m.time(v0, m.p + c.length, c.accel) as f32,
                    pad: 0.0,
                });
            }
            let path_start = w.path.len() as u32;
            let np = ((m.p / 0.5).ceil() as usize).max(1) + 1;
            for q in 0..np {
                let want = m.p * q as f64 / (np - 1) as f64;
                let t = m.s.partition_point(|&x| x < want).min(m.s.len() - 1);
                let p = if t == 0 {
                    m.xy[0]
                } else {
                    let u = ((want - m.s[t - 1]) / (m.s[t] - m.s[t - 1]).max(1e-9)).clamp(0.0, 1.0);
                    [m.xy[t - 1][0] + u * (m.xy[t][0] - m.xy[t - 1][0]), m.xy[t - 1][1] + u * (m.xy[t][1] - m.xy[t - 1][1])]
                };
                w.path.push([p[0] as f32, p[1] as f32]);
            }
            w.links.push(GpuCjLink {
                junction: ji,
                from_lane: app_of[&m.from],
                to_lane: exit_of[&m.to],
                conf_start,
                conf_count: conf[mi].len() as u32,
                pair_start,
                pair_count: w.pairs.len() as u32 - pair_start,
                path_len: m.p as f32,
                v_turn: m.vm as f32,
                v_lane: m.v_lane as f32,
                v_after: m.v_after as f32,
                group: m.group,
                conf_lanes,
                path_start,
                path_n: np as u32,
                sim_link: m.sim_link,
                dir_in: lane_end_dir(net, m.from, true),
                dir_out: lane_end_dir(net, m.to, false),
            });
            for &lane in &m.chain {
                w.lane_info[lane as usize].box_mov = mov0 + mi as u32;
            }
            w.mov_chain.push(m.chain.clone());
        }
        let group_mask = movs.iter().fold(0u32, |a, m| a | m.group);
        let first_group = if group_mask == 0 { 0 } else { group_mask.trailing_zeros() };
        w.junctions.push(GpuCjJunction {
            app_start: app0,
            app_count: w.apps.len() as u32 - app0,
            exit_start: exit0,
            exit_count: w.exits.len() as u32 - exit0,
            mov_start: mov0,
            mov_count: n as u32,
            rel_start: rel0,
            rel_count: rel_n,
            plan_start: w.n_plan,
            aud_start: w.n_aud,
            tick_phase: order as u32 % w.cfg.tick_steps,
            mode: c.modes.get(&jn.id).copied().unwrap_or(c.mode),
            cx: jn.x,
            cy: jn.y,
            awsc_free: -1e9,
            group_mask,
            phase: first_group,
            switch_t: -1e9,
            ..Default::default()
        });
        w.n_plan += PLAN_MAX;
        w.n_aud += AUD_MAX;
        w.ids.push(jn.id.clone());
    }
    // Lane flags and which links the coordinator owns.
    for (l, info) in w.lane_info.iter().enumerate() {
        let mut f = 0;
        if info.app != NONE || info.box_mov != NONE {
            f |= LANE_CJ;
        }
        if info.exit != NONE && info.app == NONE {
            f |= LANE_CJ_EXIT;
        }
        if f != 0 {
            w.lane_flags.push((l as u32, f));
        }
    }
    w.link_flags = links_flag;
    w.cfg.n_junctions = w.junctions.len() as u32;
    w.cfg.n_apps = w.apps.len() as u32;
    w.cfg.n_exits = w.exits.len() as u32;
    w.n_replicas = 1;
    w
}

/// Copies one replica's tables for further replicas, shifting every index.
pub fn add_replica(w: &mut CoordWorld, base: &CoordWorld, lane0: u32, replica: u32) {
    let (j0, m0, c0, t0, p0, h0, r0, a0, e0, pa0) = (
        w.junctions.len() as u32,
        w.links.len() as u32,
        w.conflicts.len() as u32,
        w.times.len() as u32,
        w.pairs.len() as u32,
        w.head.len() as u32,
        w.rel_init.len() as u32,
        w.apps.len() as u32,
        w.exits.len() as u32,
        w.path.len() as u32,
    );
    let (q0, pl0, au0) = (w.n_req, w.n_plan, w.n_aud);
    w.junctions.extend(base.junctions.iter().map(|x| GpuCjJunction {
        app_start: x.app_start + a0,
        exit_start: x.exit_start + e0,
        mov_start: x.mov_start + m0,
        rel_start: x.rel_start + r0,
        plan_start: x.plan_start + pl0,
        aud_start: x.aud_start + au0,
        replica,
        ..*x
    }));
    w.links.extend(base.links.iter().map(|x| GpuCjLink {
        junction: x.junction + j0,
        from_lane: x.from_lane + a0,
        to_lane: x.to_lane + e0,
        conf_start: x.conf_start + c0,
        pair_start: x.pair_start + p0,
        path_start: x.path_start + pa0,
        ..*x
    }));
    w.conflicts.extend(base.conflicts.iter().map(|x| GpuCjConflict {
        rel_index: x.rel_index + r0,
        rev_index: x.rev_index + r0,
        foe: x.foe + m0,
        ..*x
    }));
    let _ = t0;
    w.times.extend_from_slice(&base.times);
    w.pairs.extend(base.pairs.iter().map(|x| GpuCjPair { other: x.other + m0, table: x.table + h0, ..*x }));
    w.head.extend_from_slice(&base.head);
    w.mov_k.extend_from_slice(&base.mov_k);
    w.rel_init.extend_from_slice(&base.rel_init);
    w.apps.extend(base.apps.iter().map(|x| GpuCjApp {
        sim_lane: x.sim_lane + lane0,
        junction: x.junction + j0,
        req_start: x.req_start + q0,
        mov_start: x.mov_start + m0,
        ..*x
    }));
    w.exits.extend(base.exits.iter().map(|x| GpuCjExit { sim_lane: x.sim_lane + lane0, junction: x.junction + j0, ..*x }));
    w.path.extend_from_slice(&base.path);
    w.n_req += base.n_req;
    w.n_plan += base.n_plan;
    w.n_aud += base.n_aud;
}

#[cfg(test)]
mod tests {
    use super::*;
    use wgpu::util::DeviceExt;

    fn reference() -> serde_json::Value {
        let p = concat!(env!("CARGO_MANIFEST_DIR"), "/../../research/truth/fig/d8/kinematics.json");
        serde_json::from_slice(&std::fs::read(p).expect("run scripts/d8/kinematics_ref.py")).unwrap()
    }

    #[test]
    fn travel_time_matches_python() {
        let r = reference();
        let f = |k: &str| r[k].as_f64().unwrap();
        let m = Mov {
            from: 0,
            to: 0,
            sim_link: 0,
            chain: Vec::new(),
            s: Vec::new(),
            xy: Vec::new(),
            p: f("p"),
            vm: f("vm"),
            v_lane: f("v_after"),
            v_after: f("v_after"),
            vk: [0.0; 6],
            group: 0,
        };
        for row in r["times"].as_array().unwrap() {
            let t = m.time(row["v0"].as_f64().unwrap(), row["s"].as_f64().unwrap(), f("a"));
            assert!((t - row["t"].as_f64().unwrap()).abs() < 1e-3, "{row} got {t}");
        }
    }

    #[test]
    fn saturation_headway_is_the_reference_value() {
        let p = concat!(env!("CARGO_MANIFEST_DIR"), "/../../research/truth/fig/09-nets/j1.net.xml");
        let net = Net::load(std::path::Path::new(p)).unwrap();
        let topo = Topology::build(&net);
        let c = CoordConfig { select: Select::Ids(vec!["B1".into()]), ..Default::default() };
        let w = build(&net, &topo, &c, 0.1, 0);
        // Through movements run at the lane's speed; the follower of one, at full speed, on the same movement.
        let (mi, m) = w.links.iter().enumerate().find(|(_, m)| m.v_turn > 13.0).unwrap();
        let pair = w.pairs[m.pair_start as usize..(m.pair_start + m.pair_count) as usize].iter().find(|x| x.other == mi as u32 && x.is_exit == 0).unwrap();
        let h = w.head[pair.table as usize];
        assert!((h - 1.304).abs() < 0.02, "headway {h}");
        eprintln!("through-through headway {h:.3} s, reference 1.304");
    }

    // The closed forms as the coordinator kernels run them, on whatever Vulkan device is at hand.
    #[test]
    fn earliest_and_latest_match_python() {
        let Ok(gpu) = pollster::block_on(crate::Gpu::headless(crate::GpuOptions { adapter_name: Some("llvmpipe".into()), ..Default::default() })) else {
            eprintln!("no llvmpipe, skipped");
            return;
        };
        let r = reference();
        let rows = r["rows"].as_array().unwrap();
        let src = include_str!("shaders/av_junction.wgsl");
        let body = &src[src.find("fn earliest(").unwrap()..src.find("// Cruise speed").unwrap()];
        let code = format!(
            "const INF: f32 = 1e30;\n{body}\n@group(0) @binding(0) var<storage, read> inp: array<vec4f>;\n@group(0) @binding(1) var<storage, read_write> out: array<vec2f>;\n@compute @workgroup_size(64) fn main(@builtin(global_invocation_id) id: vec3u) {{ if (id.x >= arrayLength(&inp)) {{ return; }} let q = inp[id.x]; out[id.x] = vec2f(earliest(q.x, q.y, q.z, {}, {}, {}), latest(q.x, q.y, q.z, {}, {})); }}",
            r["vmax"], r["a"], r["b"], r["a"], r["b"]
        );
        let input: Vec<[f32; 4]> = rows.iter().map(|x| [x["d"].as_f64().unwrap() as f32, x["v"].as_f64().unwrap() as f32, x["ve"].as_f64().unwrap() as f32, 0.0]).collect();
        let d = &gpu.device;
        let inb = d.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&input), usage: wgpu::BufferUsages::STORAGE });
        let outb = d.create_buffer(&wgpu::BufferDescriptor { label: None, size: input.len() as u64 * 8, usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC, mapped_at_creation: false });
        let stage = d.create_buffer(&wgpu::BufferDescriptor { label: None, size: input.len() as u64 * 8, usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ, mapped_at_creation: false });
        let module = gpu.shader("kinematics", &code);
        let pipe = d.create_compute_pipeline(&wgpu::ComputePipelineDescriptor { label: None, layout: None, module: &module, entry_point: Some("main"), compilation_options: Default::default(), cache: None });
        let group = d.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &pipe.get_bind_group_layout(0),
            entries: &[wgpu::BindGroupEntry { binding: 0, resource: inb.as_entire_binding() }, wgpu::BindGroupEntry { binding: 1, resource: outb.as_entire_binding() }],
        });
        let mut enc = d.create_command_encoder(&Default::default());
        {
            let mut c = enc.begin_compute_pass(&Default::default());
            c.set_pipeline(&pipe);
            c.set_bind_group(0, &group, &[]);
            c.dispatch_workgroups((input.len() as u32).div_ceil(64), 1, 1);
        }
        enc.copy_buffer_to_buffer(&outb, 0, &stage, 0, input.len() as u64 * 8);
        gpu.queue.submit([enc.finish()]);
        stage.slice(..).map_async(wgpu::MapMode::Read, |_| {});
        gpu.wait();
        let data = stage.slice(..).get_mapped_range().unwrap();
        let got: Vec<[f32; 2]> = bytemuck::pod_collect_to_vec(&data[..]);
        let mut worst = 0f64;
        for (x, g) in rows.iter().zip(&got) {
            let (te, tl) = (x["te"].as_f64().unwrap(), x["tl"].as_f64().unwrap());
            // f32 tolerance widens the none/some boundary by a millimetre; those cases are not compared.
            if (te < 0.0) == (g[0] < 0.0) {
                worst = worst.max((te - g[0] as f64).abs());
            }
            if (tl < 0.0) == (g[1] < 0.0) && tl < 1e29 && g[1] < 1e29 {
                worst = worst.max((tl - g[1] as f64).abs());
            }
        }
        assert!(worst < 1e-3, "worst difference {worst} s");
        eprintln!("earliest and latest within {worst:.6} s of Python over {} cases", rows.len());
    }
}
