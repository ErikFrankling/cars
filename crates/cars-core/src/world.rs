//! Flattens a network and its demand into the arrays the GPU kernels read. Each `#[repr(C)]` struct
//! has a twin in `shaders/common.wgsl`.

use bytemuck::{Pod, Zeroable};

use crate::actuated::Actuation;
use crate::demand::{ArrivalPos, CfModel, Demand, DepartLane, DepartPos, DepartSpeed, VType};
use crate::net::{EdgeFunc, Net};
use crate::topology::{NONE, Topology};

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuParams {
    pub dt: f32,
    pub n_lanes: u32,
    pub n_links: u32,
    pub n_tls: u32,
    pub n_trips: u32,
    pub n_edges: u32,
    pub capacity: u32,
    pub n_replicas: u32,
    pub block: u32,
    pub key_bits: u32,
    pub n_queues: u32,
    pub teleport_steps: u32,
    pub sample_steps: u32,
    pub n_samples: u32,
    pub tls_yellow_min_decel: f32,
    pub time_to_impatience: f32,
    pub ignore_blocker: f32,
    pub script_t0: f32,
    pub dummy_lane: u32,
    /// Road friction. 0 keeps the SUMO-parity kernel, anything else is physical mode.
    pub mu: f32,
    pub shadow_reserve: u32,
    pub detect_every: u32,
    pub grid_mask: u32,
    pub trace_len: u32,
    /// Bit 0 certificate, bit 1 junction arbiter, bit 2 exit-clear. All on unless a test turns one off.
    pub safety: u32,
    pub width_margin: f32,
    pub claim_scale: f32,
    pub queue_speed: f32,
    /// Seconds at the end of a wrong lane before the vehicle is taken off and counted lost. 0 never.
    pub lost_after: f32,
    /// Hold zones by where a body can reach, and ask again for those ahead on the lane. Off: by lane.
    pub zones_ahead: u32,
    pub lc_gap: f32,
    /// A body about to leave a zone holds it not: 0 never, 1 at merges, 2 everywhere.
    pub zone_time: u32,
    /// Under this speed a change is not held to the heading limit: steering at a crawl can take any angle, and
    /// a car held to it stays across two lanes for good.
    pub lc_crawl: f32,
    /// A change may run on over the end of its lane. Off: it finishes first, and waits at the line if it must.
    pub lc_carry: u32,
    pub meter_n: u32,
    pub lateral_median: f32,
    pub hu_k: f32,
    pub hu_rho: f32,
    pub hu_nscale: f32,
    pub hu_flags: u32,
    pub hu_a: [f32; 4],
    pub hu_b: [f32; 4],
    pub hu_c: [f32; 4],
    pub hu_d: [f32; 4],
    pub hu_e: [f32; 4],
    pub hu_f: [f32; 4],
    pub hu_g: [f32; 4],
    pub hu_i: [f32; 4],
    pub hu_h: [f32; 4],
    pub hm_a: [f32; 4],
    pub hm_b: [f32; 4],
    pub hm_c: [f32; 4],
    pub hm_d: [f32; 4],
    /// Metres from which a driver can see whether a give-way line is free, at least. The map's 4.5 m means stopping at every one.
    pub vis_floor: f32,
    /// Seconds at a stand a driver keeps holding back for someone else's lane change.
    pub lc_patience: f32,
    /// Spread between drivers of the gap they keep: sigma of a lognormal around 1.
    pub gap_spread: f32,
    /// How hard the one of two cars abreast slows to fall behind the other, m/s2.
    pub abreast_b: f32,
    /// Mean seconds at the end of a lane with no way on before a driver goes past and looks for another way. 0 never.
    pub miss_patience: f32,
    /// On a lane shorter than this there is no waiting: a change can't fit.
    pub miss_short: f32,
    /// Seconds a driver standing still takes to go once its way opens. 0 off.
    pub start_react: f32,
    /// The same for the first car at a stop line, which reacts to the light rather than to a leader.
    pub first_react: f32,
    pub pad_f: f32,
    pub pad_g: f32,
    pub pad_h: f32,
    pub pad_i: f32,
    /// The measured driver, research/truth/measure/MODEL.md: closing gain K (m/s), leader share, braking k_g, pull k_p.
    pub md_a: [f32; 4],
    /// Response share per step, noise correlation per step, noise scale per step, on (1) or off (0).
    pub md_b: [f32; 4],
    /// Standstill bumper gap (m), braking edge of the band (s), closing response cap (m/s), spare.
    pub md_c: [f32; 4],
    /// Median steady time gap at 6.5, 12.5, 17.5, 22.5 m/s, then 30 and 40 m/s.
    pub md_t: [f32; 4],
    pub md_u: [f32; 4],
    /// Measured lane changes, research/truth/measure/LANECHANGE.md: start law constant and its slope per 10 s to the
    /// end of the lane; critical lag time gap, log median and its rise per m/s the follower closes.
    pub lcm_a: [f32; 4],
    /// Critical lag log-SD; critical lead time gap log median, rise per m/s ego closes, log-SD.
    pub lcm_b: [f32; 4],
    /// Share of target-lane followers who open a gap for a must-change; on (1) or off (0); spare; spare.
    pub lcm_c: [f32; 4],
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuGlobals {
    pub step: u32,
    pub n_active: u32,
    pub n: u32,
    pub blocks: u32,
    pub sample: u32,
    pub pad: [u32; 3],
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuVeh {
    pub pos: f32,
    pub speed: f32,
    pub lane: u32,
    pub route_i: u32,
    pub acc: f32,
    pub sf: f32,
    pub vtype: u32,
    pub trip: u32,
    pub rng: u32,
    pub route_end: u32,
    pub arrival: f32,
    pub flags: u32,
    pub wait: f32,
    pub lc_right: f32,
    pub lc_left: f32,
    pub lc_keep: f32,
    pub look_v: f32,
    pub best_cur: f32,
    pub best_left: f32,
    pub best_right: f32,
    pub best_off: i32,
    pub entry_step: u32,
    pub prev_lane: u32,
    pub prev2_lane: u32,
    pub tot_wait: f32,
    pub time_loss: f32,
    pub route_len: f32,
    pub depart_step: u32,
    pub wait_count: u32,
    pub replica: u32,
    pub v_next: f32,
    pub n_items: u32,
    pub lc_own: u32,
    pub left_space: f32,
    pub blocker: f32,
    pub occ_cur: f32,
    pub occ_left: f32,
    pub occ_right: f32,
    pub occ_best: f32,
    /// Bits 0-7 load, 8-15 power, 16-29 lateral phase, 30-31 lateral direction. See `phys_bits`.
    pub phys: u32,
    pub hu_acc: f32,
    pub hu_noise: f32,
    pub lc_wait: f32,
    pub hu_state: u32,
    pub lc_bias: f32,
    pub lc_edge: f32,
    pub cj_t_line: f32,
    pub cj_v_line: f32,
    pub cj_v_cruise: f32,
    pub cj_link: u32,
    pub cj_state: u32,
    pub cj_zone_t: f32,
    pub cj_seq: u32,
    pub cj_hold: f32,
    pub cj_v_cmd: f32,
    pub cj_yield: f32,
    pub cj_t_ms: u32,
    pub cj_plan_ms: u32,
    pub cj_rx_ms: u32,
    pub cj_rank: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuLane {
    pub length: f32,
    pub speed: f32,
    pub edge: u32,
    pub links_start: u32,
    pub links_count: u32,
    pub index: u32,
    pub allow: u32,
    pub flags: u32,
    pub key_base: u32,
    pub key_scale: f32,
    pub det_pos: f32,
    pub shape_start: u32,
    pub pred: u32,
    pub entry_link: u32,
    pub pad: [u32; 2],
    pub in_start: u32,
    pub in_count: u32,
    /// sin(theta) times g, uphill positive.
    pub gz: f32,
    /// Speed the curve asks of a driver, 0 when straight.
    pub curve_v: f32,
    /// Square root of the tightest radius, 0 when straight.
    pub sqrt_r: f32,
    pub sqrt_path_r: f32,
    pub s_curve: f32,
    pub s_curve_end: f32,
    pub width: f32,
    pub zone_start: u32,
    pub zone_count: u32,
    pub shape_count: u32,
    pub from_node: u32,
    pub to_node: u32,
    pub geom_scale: f32,
}

/// Where a junction lane and another one come too close for two bodies. Positions along each lane.
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuZone {
    pub foe_lane: u32,
    pub own_in: f32,
    pub own_out: f32,
    pub foe_in: f32,
    pub foe_out: f32,
    /// Least distance between the two centre lines.
    pub dist: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuEdge {
    pub first_lane: u32,
    pub lane_count: u32,
    pub length: f32,
    pub flags: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuLink {
    pub next_lane: u32,
    pub to_lane: u32,
    pub to_edge: u32,
    pub flags: u32,
    pub tl: u32,
    pub tl_index: u32,
    pub foe_start: u32,
    pub foe_count: u32,
    pub conf_start: u32,
    pub conf_count: u32,
    pub length: f32,
    pub visibility: f32,
    pub entry: u32,
    pub before: u32,
    pub state: u32,
    pub from_lane: u32,
    /// Critical gap for a yielding movement in physical mode, seconds. 0 when it does not yield.
    pub tc: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuConflict {
    pub foe_lane: u32,
    pub flags: u32,
    pub len_behind: f32,
    pub foe_len_behind: f32,
    pub width: f32,
    pub foe_width: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuVType {
    pub model: u32,
    pub length: f32,
    pub min_gap: f32,
    pub accel: f32,
    pub decel: f32,
    pub emergency: f32,
    pub apparent: f32,
    pub tau: f32,
    pub sigma: f32,
    pub max_speed: f32,
    pub impatience: f32,
    pub timegap_minor: f32,
    pub vclass: u32,
    pub idm_delta: f32,
    pub idm_iters: u32,
    pub two_sqrt_ab: f32,
    pub headway_acc: f32,
    pub glosa_range: f32,
    pub lc_strategic: f32,
    pub lc_cooperative: f32,
    pub lc_speed_gain: f32,
    pub lc_keep_right: f32,
    pub lc_assertive: f32,
    pub lc_look_left: f32,
    pub lc_speed_gain_right: f32,
    pub collision_factor: f32,
    /// Share of drivers of this type who keep the junction clear.
    pub exit_comply: f32,
    pub pw_kg: f32,
    pub road_a: f32,
    pub road_c: f32,
    pub i_inv: f32,
    pub trac: f32,
    pub v_corner: f32,
    pub b_lo: f32,
    pub b_hi: f32,
    pub t_r: f32,
    pub a0: f32,
    pub a1: f32,
    pub a_floor: f32,
    pub v_lat: f32,
    pub width: f32,
    pub ph_tau: f32,
    pub m_ref: f32,
    /// How hard a driver assumes the leader will brake, Gipps' b-hat.
    pub b_assume: f32,
    pub reaction: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuTrip {
    pub depart_step: u32,
    pub route_start: u32,
    pub route_end: u32,
    pub vtype: u32,
    pub depart_lane: i32,
    pub depart_pos: f32,
    pub depart_pos_mode: u32,
    pub depart_speed: f32,
    pub depart_speed_mode: u32,
    pub arrival: f32,
    pub sf: f32,
    pub rng: u32,
    pub replica: u32,
    pub pad: [u32; 3],
    pub persona: u32,
    pub persona2: u32,
    /// The measured driver's own time gap factor, 0 for every other driver.
    pub gap_f: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuTripOut {
    pub depart_step: u32,
    pub arrive_step: u32,
    pub wait: f32,
    pub time_loss: f32,
    pub route_len: f32,
    pub wait_count: u32,
    pub flags: u32,
    pub pad: u32,
}

/// Work done on one trip, in joules. Wheel work balances the rest by construction of `exec`.
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuTripEnergy {
    pub wheel: f32,
    pub brake: f32,
    pub road: f32,
    pub pe: f32,
    pub ke: f32,
    pub idle_s: f32,
    pub moving_s: f32,
    pub dist: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuContact {
    pub step: u32,
    pub trip_a: u32,
    pub trip_b: u32,
    pub lane_a: u32,
    pub lane_b: u32,
    pub kind: u32,
    pub depth: f32,
    pub pos_a: f32,
    pub pos_b: f32,
    pub x: f32,
    pub y: f32,
    pub pad: f32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuQueue {
    pub edge: u32,
    pub next: u32,
    pub end: u32,
    pub pad: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuTlsState {
    pub phase: u32,
    pub next_switch: u32,
    pub first_phase: u32,
    pub n_phases: u32,
    pub last_change: u32,
    pub actuated: u32,
    pub link_start: u32,
    pub link_count: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuTlsPhase {
    pub duration: u32,
    pub min_dur: u32,
    pub max_dur: u32,
    pub state_start: u32,
    pub loops_start: u32,
    pub loops_count: u32,
}

pub const ITEM_BYTES: u64 = 40;
pub const APPROACH_BYTES: u64 = 48;
pub const SEG_BYTES: u64 = 16;
pub const LCPLAN_BYTES: u64 = 16;
pub const MAX_ITEMS: u64 = 8;
pub const SLOTS: u64 = 8;
pub const CONTACT_LOG: u64 = 65536;
pub const COUNTERS: u64 = 64;
pub const MIRROR_BYTES: u64 = 16;
pub const POSE_BYTES: u64 = 32;
/// Counters of the physical kernel, after those shared with SUMO-parity mode.
pub const C_CERT_FLOOR: usize = 16;
pub const C_NO_BRAKE: usize = 17;
pub const C_DEAD_END: usize = 18;
pub const C_SHADOWS: usize = 19;
pub const C_SHADOW_REFUSED: usize = 20;
pub const F_SHADOW: u32 = 16384;
pub const C_UNGRANTED: usize = 21;
pub const C_LC_REFUSED_ROOM: usize = 22;
pub const C_DENIED: usize = 23;
pub const C_CONTACT: usize = 24;
pub const C_CONTACT_KINDS: usize = 25;
/// Human lane change rules, counted after the contact kinds.
pub const C_HU_YIELD: usize = 32;
pub const C_HU_REROUTE: usize = 35;
pub const C_HU_LC_URGENT: usize = 36;
pub const C_HU_GUARD: usize = 37;
pub const C_HU_STEPS: usize = 39;
pub const REROUTE_LOG: u64 = 65536;
/// Measured lane changes (research/truth/measure/LANECHANGE.md, lc_decision.json), frozen before any scene or replay test.
/// One likelihood over every 0.5 s a must-change car spends beside its target lane (I-80 and US-101 cohorts of report 14,
/// 959 cars): crossing hazard sigmoid(a0 + AT tte / 10) times the chance both gaps pass. The simulator commits at the start
/// of the sideways motion, which is 2.0 s before the centre crosses (exiD merges, highD): A0 = a0 - AT * 2.0 / 10.
pub const LCM_A0: f32 = -0.825 + 1.119 * 0.2;
pub const LCM_AT: f32 = -1.119;
/// Critical time gaps, lognormal: ln median, rise of the ln per m/s of closing speed, log-SD. Lag over the follower's
/// speed, lead over own speed, both floored at 1 m/s. Same fit; drawn afresh every 0.5 s as the fit assumes.
pub const LCM_LAG: [f32; 3] = [-0.908, 0.551, 1.676];
pub const LCM_LEAD: [f32; 3] = [-2.004, 0.453, 1.374];
/// Share of followers who open a gap when a blocked must-changer is alongside: report 14's 0.4, provisional (swept on
/// I-80). F707 measures something else: per merge, 11.9% of new followers slow 0.3 m/s2 beyond matched ones against
/// 6.4% (exiD), mostly in free flow where nobody is blocked. Taking 0.055 for the share made lane-end waits three times
/// I-80's (LC8 p99 187 s against 72.7); 0.4 gives 76.5 s, median 24 against 22.6.
pub const LCM_COURTESY: f32 = 0.4;
/// Sideways speed of the physical change (1 s ends): the 1.4 m from 10% of the lane to its marking in the measured
/// 1.96-2.0 s from the start to the centre crossing, and the 2.3 m to a body clear of the old lane in 3.2-3.3 s
/// (exiD merges 1,480 at 20-25 m/s, highD 1,124 at 25-30 m/s; both give 0.71). DLR HT gives 0.47-0.52.
pub const LCM_V_LAT: f32 = 0.71;
/// Everything on except the rules named.
pub fn human_flags(off: &[String]) -> u32 {
    let mut flags = HUMAN_RULES.iter().fold(0, |a, r| a | r.1);
    for name in off {
        let rule = HUMAN_RULES.iter().find(|r| r.0 == name).unwrap_or_else(|| panic!("no human rule {name}"));
        flags &= !rule.1;
    }
    flags
}

/// Rules of `research/truth/14-human-courtesy.md`, as bits of `GpuParams::hu_flags`.
pub const HUMAN_RULES: [(&str, u32); 13] = [("courtesy", 1), ("shrink", 2), ("offset", 4), ("anticipate", 8), ("miss", 16), ("gate", 32), ("yellow", 64), ("tte", 128), ("start", 256), ("edge", 512), ("follow", 1024), ("match", 2048), ("steer", 4096)];

/// The human driver's numbers that are ours to choose. Provenance of each: `shaders/HUMAN.md`.
#[derive(Clone, Copy, Debug)]
pub struct HumanParams {
    /// Aimsun's "cooperation creating a gap", a share of drivers.
    pub cooperation: f32,
    /// Mean seconds at a standstill before giving up on a turn. Each driver draws 0.5 to 1.5 times this.
    pub t_miss: f32,
    /// Stop short of the end of a lane: Trafikverket's minimum 5 m, 7 m more on every second lane.
    pub stop_base: f32,
    pub stop_offset: f32,
    pub sig_react: f32,
    pub r_urg: f32,
    /// Vissim's CoopDecel.
    pub coop_decel: f32,
    pub tau_gate: f32,
    pub tau_min: f32,
    pub b_em: f32,
    pub gap_model: f32,
    pub gap_junction: f32,
    pub gap_roundabout: f32,
    pub t_scale: f32,
    pub s0_scale: f32,
    /// Lee's constants are what MITSIMLab recalibrates per site (Choudhury 2007, section 5.4.2).
    pub lead_shift: f32,
    pub lag_shift: f32,
    /// Vissim's 0.6 on the safety distance during a lane change.
    pub lc_safety: f32,
    /// Median sideways acceleration a driver holds through a corner, report 19.
    pub a_y: f32,
    /// Region's mean of free speed against the limit, Sweden's from VTI 1001. 0 off.
    pub free_table: f32,
    /// Invented, see HUMAN.md: Gipps approach to a standing target.
    pub b_approach: f32,
    pub tau_approach: f32,
    pub overshoot: f32,
    pub standing: f32,
    pub see: f32,
    pub lc_slope: f32,
    pub stop_s0: f32,
    pub comfort: f32,
    /// A lane shorter than this is no place to wait for a gap: the route is given up at once.
    pub stub: f32,
    /// Speed match weight once the driver has decided to go.
    pub w_s_near: f32,
    /// Braking when stopping for a lane end, as late as is comfortable.
    pub b_end: f32,
    /// Report 18, section 4.
    pub tte0: f32,
    pub s_0: f32,
    pub s_t: f32,
    pub s_lag: f32,
    pub s_lead: f32,
    pub s_driver: f32,
    pub w_f: f32,
    pub t_f: f32,
    pub b_f: f32,
    pub w_s_neg: f32,
    pub w_s_pos: f32,
    pub k_c: f32,
    pub q_edge: f32,
    pub v_edge: f32,
    pub tau_a: f32,
    pub tau_sd: f32,
    /// Gipps limit behind a moving leader, deceleration and reaction term. 0 off.
    pub gipps_b: f32,
    pub gipps_tau: f32,
    /// Critical gap shifts far from a lane end, moving to lead_shift and lag_shift within r_urg of it.
    pub lead_far: f32,
    pub lag_far: f32,
}

impl Default for HumanParams {
    fn default() -> Self {
        Self { cooperation: 0.4, t_miss: 120.0, stop_base: 5.0, stop_offset: 7.0, sig_react: 1.0, r_urg: 100.0, coop_decel: 3.0, tau_gate: 0.4, tau_min: 0.3, b_em: 7.5, gap_model: 1.0, gap_junction: 0.65, gap_roundabout: 1.5, t_scale: 0.7, s0_scale: 1.0, lead_shift: -6.0, lag_shift: -2.0, lc_safety: 0.35, a_y: 2.2, free_table: 0.0, b_approach: 1.2, tau_approach: 2.0, overshoot: 1.4, standing: 0.5, see: 30.0, lc_slope: 1.0, stop_s0: 1.0, comfort: 1.5, stub: 7.0, w_s_near: 0.45, b_end: 2.5, tte0: 43.0, s_0: 0.4, s_t: -1.544, s_lag: 0.133, s_lead: 0.164, s_driver: 0.5, w_f: 0.756, t_f: 0.5, b_f: 3.0, w_s_neg: 0.12, w_s_pos: 0.25, k_c: 0.05, q_edge: 0.13, v_edge: 15.0, tau_a: 1.87, tau_sd: 1.44, gipps_b: 3.0, gipps_tau: 0.5, lead_far: -6.0, lag_far: -2.0 }
    }
}

impl HumanParams {
    /// Sweden: Trafikverket's jam spacing and through saturation flow, from `TRVMB Kapacitet`.
    pub fn sweden() -> Self {
        Self { free_table: 1.0, t_scale: 0.55, s0_scale: 0.47, ..Self::default() }
    }

    /// With what `--tune` names. Names that are not this driver's belong to the physics.
    pub fn tuned(mut self, tune: &[(String, f32)]) -> Self {
        for (k, v) in tune {
            let v = *v;
            match k.as_str() {
                "cooperation" => self.cooperation = v,
                "t_miss" => self.t_miss = v,
                "stop_base" => self.stop_base = v,
                "stop_offset" => self.stop_offset = v,
                "sig_react" => self.sig_react = v,
                "r_urg" => self.r_urg = v,
                "coop_decel" => self.coop_decel = v,
                "tau_gate" => self.tau_gate = v,
                "tau_min" => self.tau_min = v,
                "b_em" => self.b_em = v,
                "gap_model" => self.gap_model = v,
                "gap_junction" => self.gap_junction = v,
                "gap_roundabout" => self.gap_roundabout = v,
                "t_scale" => self.t_scale = v,
                "s0_scale" => self.s0_scale = v,
                "lead_shift" => self.lead_shift = v,
                "lag_shift" => self.lag_shift = v,
                "lc_safety" => self.lc_safety = v,
                "a_y" => self.a_y = v,
                "free_table" => self.free_table = v,
                "b_approach" => self.b_approach = v,
                "tau_approach" => self.tau_approach = v,
                "overshoot" => self.overshoot = v,
                "standing" => self.standing = v,
                "see" => self.see = v,
                "lc_slope" => self.lc_slope = v,
                "stop_s0" => self.stop_s0 = v,
                "comfort" => self.comfort = v,
                "stub" => self.stub = v,
                "w_s_near" => self.w_s_near = v,
                "b_end" => self.b_end = v,
                "tte0" => self.tte0 = v,
                "s_0" => self.s_0 = v,
                "s_t" => self.s_t = v,
                "s_lag" => self.s_lag = v,
                "s_lead" => self.s_lead = v,
                "s_driver" => self.s_driver = v,
                "w_f" => self.w_f = v,
                "t_f" => self.t_f = v,
                "b_f" => self.b_f = v,
                "w_s_neg" => self.w_s_neg = v,
                "w_s_pos" => self.w_s_pos = v,
                "k_c" => self.k_c = v,
                "q_edge" => self.q_edge = v,
                "v_edge" => self.v_edge = v,
                "tau_a" => self.tau_a = v,
                "tau_sd" => self.tau_sd = v,
                "gipps_b" => self.gipps_b = v,
                "gipps_tau" => self.gipps_tau = v,
                "lead_far" => self.lead_far = v,
                "lag_far" => self.lag_far = v,
                _ => {}
            }
        }
        self
    }
}
pub const C_LOST: usize = 34;
/// Contact kinds, as counted from `C_CONTACT_KINDS`.
pub const CONTACT_NAMES: [&str; 9] = ["same lane", "neighbour lane", "junction crossing", "junction merge", "junction diverge", "lane start", "other", "crossed without grant", "lost on a wrong lane"];
/// Kinds from here on are protocol breaches, not bodies touching.
pub const CONTACT_BODIES: usize = 7;
/// Sort key resolution: two vehicles on a lane are always further apart than this.
const KEY_METRES: f32 = 2.5;

#[derive(Clone, Debug)]
pub struct SimConfig {
    pub dt: f32,
    /// Seconds a stuck lane head waits before teleporting. 0 turns teleporting off.
    pub time_to_teleport: f32,
    pub sample_seconds: f32,
    pub begin_seconds: f32,
    pub end_seconds: f32,
    pub seed: u64,
    /// Most vehicles on the road at once. 0 means every trip.
    pub capacity: u32,
    /// How fast minor road drivers lose patience, SUMO's time-to-impatience.
    pub time_to_impatience: f32,
    pub tls_yellow_min_decel: f32,
    pub block: u32,
    pub use_actuation: bool,
    /// SUMO's ignore-junction-blocker: stuck vehicles on a junction stop counting after this long.
    pub ignore_blocker: f32,
    /// When the ring disturbance starts, in seconds. 0 turns it off.
    pub script_t0: f32,
    /// Road friction. 0 keeps SUMO parity: Euler positions, no physics, no arbitration.
    pub mu: f32,
    /// Steps between 2D collision checks. 0 turns the detector off.
    pub detect_every: u32,
    /// Desired speed per step for scripted vehicles, for driving-cycle checks.
    pub speed_trace: Vec<f32>,
    /// Every vehicle type drives as `MODEL_HUMAN`, in physical mode.
    pub humans: bool,
    /// Which rules of `HUMAN_RULES` are on.
    pub human_flags: u32,
    pub human: HumanParams,
    /// Room in the routes buffer for routes handed out during the run, in edges.
    pub route_arena: u32,
    /// Physical parameters a sensitivity test wants to move. See `tune`.
    pub tune: Vec<(String, f32)>,
    /// Junctions run by the coordinator instead of SUMO's rules.
    pub coord: Option<crate::coord::CoordConfig>,
    /// One insertion queue per lane for trips with a fixed departure lane, instead of one per edge.
    pub per_lane_queues: bool,
    /// Hold new vehicles outside the network while this many are on it. 0 for no metering.
    pub meter_n: u32,
}

impl SimConfig {
    pub fn tune(&self, name: &str, default: f32) -> f32 {
        self.tune.iter().rev().find(|(k, _)| k == name).map_or(default, |(_, v)| *v)
    }

    /// `--tune measured=1` drives Krauss types by the measured driver of research/truth/measure/MODEL.md in physical mode.
    /// Off by default until it passes its held-out tests and T0 (measure/MODEL_RESULTS.md); the default is the one driver
    /// of foundations/scenes-log.md section 3.
    pub fn measured(&self) -> bool {
        self.mu > 0.0 && !self.humans && self.tune("measured", 0.0) > 0.0
    }
}

/// The measured driver's numbers, research/truth/measure/model_fit.json: fitted on highD (without location 6), DLR HT
/// 06-14 UTC and TGSIM I-90/94 stationary, I-294 L1, I-395, frozen before any held-out recording was read.
pub const MD_K: f32 = 2.687;
pub const MD_CA: f32 = 0.508;
pub const MD_KG: f32 = 0.284;
pub const MD_KP: f32 = 0.0253;
pub const MD_NOISE_SD: f32 = 0.968;
pub const MD_NOISE_T: f32 = 0.1;
/// Free driving relaxes to the desired speed with this time, fitted on 30 s rollouts (F311).
pub const MD_TV: f32 = 1.0;
/// DRIVER.md: response time constant, standstill gap, gap spread between drivers and its link to free speed, desired speed spread.
pub const MD_TAU_R: f32 = 0.5;
pub const MD_S0: f32 = 1.7;
pub const MD_GAP_SD: f64 = 0.27;
pub const MD_GAP_SPEED_R: f64 = -0.41;
pub const MD_SPEED_DEV: f32 = 0.17;

fn md_type(t: &VType, cfg: &SimConfig) -> bool {
    cfg.measured() && t.model == CfModel::Krauss
}

impl Default for SimConfig {
    fn default() -> Self {
        Self {
            dt: 1.0,
            time_to_teleport: 300.0,
            sample_seconds: 1.0,
            begin_seconds: 0.0,
            end_seconds: 3600.0,
            seed: 0,
            capacity: 0,
            time_to_impatience: 180.0,
            tls_yellow_min_decel: 3.0,
            block: 256,
            use_actuation: true,
            ignore_blocker: 1e9,
            script_t0: 0.0,
            mu: 0.0,
            detect_every: 0,
            speed_trace: Vec::new(),
            humans: false,
            human_flags: 127,
            human: HumanParams::default(),
            route_arena: 0,
            tune: Vec::new(),
            coord: None,
            per_lane_queues: false,
            meter_n: 0,
        }
    }
}

/// One copy of the scenario in an ensemble: which vehicle type each trip gets, and a seed.
#[derive(Clone, Debug, Default)]
pub struct Replica {
    pub seed: u64,
    /// Replaces each trip's vehicle type. Empty keeps the demand's types.
    pub trip_vtype: Vec<u32>,
    pub label: String,
}

#[derive(Default)]
pub struct World {
    pub params: GpuParams,
    pub lanes: Vec<GpuLane>,
    pub edges: Vec<GpuEdge>,
    pub links: Vec<GpuLink>,
    pub foes: Vec<u32>,
    pub conflicts: Vec<GpuConflict>,
    pub vtypes: Vec<GpuVType>,
    pub routes: Vec<u32>,
    /// Room reserved after `routes` on the GPU, in edges.
    pub route_arena: u32,
    pub trips: Vec<GpuTrip>,
    /// Which demand trip each GPU trip came from.
    pub trip_source: Vec<u32>,
    pub queues: Vec<GpuQueue>,
    pub queue_trips: Vec<u32>,
    pub tls: Vec<GpuTlsState>,
    pub phases: Vec<GpuTlsPhase>,
    pub states: Vec<u32>,
    pub incoming_links: Vec<u32>,
    /// Lane polylines for drawing: flat points, offset per lane in `GpuLane::shape_start`.
    pub shapes: Vec<[f32; 2]>,
    pub shape_range: Vec<(u32, u32)>,
    pub bounds: [f32; 4],
    /// First edge of each replica, to separate statistics.
    pub replica_edge_start: Vec<u32>,
    pub n_edges_per_replica: u32,
    pub edge_is_normal: Vec<bool>,
    pub total_cells: u64,
    /// Which lanes a route and vehicle type may depart on, kept for `rewrite_demand`.
    pub depart_masks: rustc_hash::FxHashMap<(u32, u32), u32>,
    pub zones: Vec<GpuZone>,
    pub speed_trace: Vec<f32>,
    /// Lane geometry for the detector: x, y, distance along, per point.
    pub shape_points: Vec<[f32; 4]>,
    pub coord: Option<crate::coord::CoordWorld>,
    /// Recorded tracks that overwrite their vehicles each step, see `crate::replay`.
    pub replay: Option<ReplayWorld>,
}

/// Twin of `ReplayCfg` in replay.wgsl.
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuReplayCfg {
    pub begin: f32,
    pub n_tracks: u32,
    pub n_trips: u32,
    pub pad: u32,
}

/// Twin of `ReplayTrack` in replay.wgsl. Keys `first..first + n` at `t0 + k * key_dt`; replayed while time < `release`.
/// Times in seconds after `--begin`.
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuReplayTrack {
    pub first: u32,
    pub n: u32,
    pub t0: f32,
    pub key_dt: f32,
    pub release: f32,
    pub pad: [u32; 3],
}

/// Twin of `ReplayKey` in replay.wgsl. `route_i` is absolute in `routes`, as `Veh::route_i`.
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Debug, Default)]
pub struct GpuReplayKey {
    pub lane: u32,
    pub pos: f32,
    pub speed: f32,
    pub route_i: u32,
    /// Offset from the lane's centreline, left positive; drawn and detected through `Veh::lc_edge`.
    pub lat: f32,
}

#[derive(Default, Clone)]
pub struct ReplayWorld {
    pub cfg: GpuReplayCfg,
    pub tracks: Vec<GpuReplayTrack>,
    pub keys: Vec<GpuReplayKey>,
    /// Track per GPU trip, `u32::MAX` for a trip simulated throughout.
    pub trip_track: Vec<u32>,
}

/// Counters of `replay_apply`, in `rstats`.
pub const REPLAY_STATS: [&str; 5] = ["applied", "ended", "shadows_removed", "lane_jumps", "released"];

fn splitmix(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E3779B97F4A7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

fn uniform(state: &mut u64) -> f64 {
    (splitmix(state) >> 11) as f64 / (1u64 << 53) as f64
}

fn normal(state: &mut u64) -> f64 {
    let (u1, u2) = (uniform(state).max(1e-12), uniform(state));
    (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos()
}

/// `normc`: a rejection sampled truncated normal, per vehicle.
fn speed_factor(t: &VType, state: &mut u64) -> f32 {
    let (mean, dev) = (t.speed_factor_mean as f64, t.speed_factor_dev as f64);
    if dev <= 0.0 {
        return mean as f32;
    }
    let (lo, hi) = (t.speed_factor_min as f64, t.speed_factor_max as f64);
    for _ in 0..1000 {
        let x = mean + dev * normal(state);
        if x >= lo && x <= hi {
            return ((x * 1e4).round() / 1e4) as f32;
        }
    }
    mean as f32
}

/// Vehicle parameters of `research/truth/11-vehicle-physics.md`, build spec. All design values until
/// fitted to fleet data, except those the report grades as measured.
struct PhysRow {
    m_ref: f32,
    p_kw: f32,
    kappa: f32,
    cda: f32,
    crr: f32,
    v_corner: f32,
    f_d: f32,
    eps: f32,
    b_lo: f32,
    b_hi: f32,
    t_r: f32,
    a0: f32,
    a1: f32,
    a_floor: f32,
    /// Load range and power spread for drawing each vehicle.
    load: (f32, f32),
    power_sd: f32,
}

fn phys_row(vclass: u32) -> PhysRow {
    let car = PhysRow { m_ref: 1650., p_kw: 90., kappa: 0.775, cda: 0.68, crr: 0.0105, v_corner: 10., f_d: 0.55, eps: 0.05, b_lo: 8.3, b_hi: 11.3, t_r: 0.30, a0: 2.02, a1: 0.125, a_floor: 0.7, load: (0.9, 1.15), power_sd: 0.35 };
    let name = crate::net::VCLASSES.get(vclass.trailing_zeros() as usize).copied().unwrap_or("passenger");
    match name {
        "delivery" | "emergency" => PhysRow { m_ref: 2800., p_kw: 95., cda: 1.6, crr: 0.012, b_lo: 6.0, b_hi: 8.5, t_r: 0.47, load: (0.75, 1.15), power_sd: 0.2, ..car },
        "bus" | "coach" | "tram" => PhysRow { m_ref: 16000., p_kw: 170., kappa: 0.85, cda: 5.0, crr: 0.007, v_corner: 3., f_d: 0.30, eps: 0.08, b_lo: 4.5, b_hi: 7.5, t_r: 0.45, a0: 1.0, a1: 0.0, a_floor: 1.0, load: (0.8, 1.15), power_sd: 0.1, ..car },
        "truck" => PhysRow { m_ref: 18000., p_kw: 220., kappa: 0.85, cda: 5.0, crr: 0.006, v_corner: 3., f_d: 0.40, eps: 0.08, b_lo: 4.4, b_hi: 7.7, t_r: 0.45, a0: 0.76, a1: 0.0, a_floor: 0.76, load: (0.45, 1.05), power_sd: 0.1, ..car },
        "trailer" => PhysRow { m_ref: 40000., p_kw: 300., kappa: 0.85, cda: 6.0, crr: 0.006, v_corner: 3., f_d: 0.275, eps: 0.08, b_lo: 4.4, b_hi: 7.7, t_r: 0.45, a0: 0.6, a1: 0.0, a_floor: 0.6, load: (0.35, 1.0), power_sd: 0.1, ..car },
        "motorcycle" | "moped" => PhysRow { m_ref: 300., p_kw: 35., cda: 0.5, crr: 0.015, f_d: 0.5, b_lo: 6.0, b_hi: 9.0, load: (0.9, 1.1), power_sd: 0.2, ..car },
        "bicycle" | "scooter" => PhysRow { m_ref: 95., p_kw: 0.25, kappa: 1.0, cda: 0.5, crr: 0.006, v_corner: 3., f_d: 0.5, eps: 0.0, b_lo: 3.0, b_hi: 5.0, t_r: 0.3, a0: 1.0, a1: 0.05, a_floor: 0.2, load: (0.9, 1.1), power_sd: 0.2, ..car },
        _ => car,
    }
}

const G: f32 = 9.81;
const RHO: f32 = 1.225;

/// Fills in the physical half of a type. `phys.*` parameters on the vType override the table.
fn physical_type(g: &mut GpuVType, t: &VType, cfg: &SimConfig) {
    let r = phys_row(t.vclass);
    let num = |key: &str, default: f32| t.params.get(key).and_then(|v| v.parse().ok()).unwrap_or(default);
    let m = num("phys.mass", r.m_ref);
    let p = num("phys.power_kw", r.p_kw) * 1e3;
    g.m_ref = m;
    g.pw_kg = num("phys.kappa", r.kappa) * p / m;
    g.road_a = num("phys.crr", r.crr) * G;
    g.road_c = 0.5 * RHO * num("phys.cda", r.cda) / m;
    g.i_inv = 1.0 / (1.0 + num("phys.eps", r.eps));
    g.trac = num("phys.f_d", r.f_d) * G;
    g.v_corner = num("phys.v_corner", r.v_corner);
    g.b_lo = num("phys.b_lo", if r.m_ref == 1650.0 { cfg.tune("car_b_lo", r.b_lo) } else { r.b_lo });
    g.b_hi = num("phys.b_hi", r.b_hi);
    g.t_r = num("phys.t_r", r.t_r);
    g.a0 = num("phys.a0", r.a0);
    g.a1 = num("phys.a1", r.a1);
    g.a_floor = num("phys.a_floor", r.a_floor.min(g.a0));
    g.v_lat = num("phys.v_lat", cfg.tune("v_lat", if !cfg.humans && cfg.tune("lc_measured", 0.0) > 0.0 { LCM_V_LAT } else { 0.6 }));
    g.width = t.width;
    // DRIVER.md: real cars stand 1.7 m apart in rounD and inD queues, measured on real box lengths. SUMO's 2.5 had no source.
    if md_type(t, cfg) {
        g.min_gap = num("phys.min_gap", if t.min_gap == 2.5 { cfg.tune("md_s0", MD_S0) } else { t.min_gap });
    }
    // The human driver keeps the physics it was fitted on: tau 0.65, sigma as given, leader braking 4.5.
    let human = cfg.humans || t.model == CfModel::Human;
    // Newell's T, the median driver: real medians fit 1.4 s at any speed (foundations/B §1, report 19's pairs).
    g.ph_tau = num("phys.tau", cfg.tune("tau", if human { 0.65 } else { 1.4 }));
    // Krauss's 0.5 is inherited. 0.2 brings 50 km/h saturation into report 04's band, 1,846 against 1,714.
    if t.sigma == 0.5 && !human { g.sigma = 0.2; }
    g.sigma = cfg.tune("sigma", g.sigma);
    g.lc_strategic = cfg.tune("lc_strategic", g.lc_strategic);
    let automated = matches!(t.model, CfModel::Acc | CfModel::Cacc);
    // Share of drivers who keep a junction box clear. The old 0.9 had no source and never acted: check_rewind held
    // everyone back. 1.0 keeps what traffic has done; a measured share (foundations C §7) replaces it.
    g.exit_comply = num("phys.exit_comply", if automated { 1.0 } else { cfg.tune("exit_comply", 1.0) });
    // Gipps' two decelerations: what the driver plans with, and what it expects of the leader.
    if t.model == CfModel::Krauss {
        g.decel = num("phys.b_plan", cfg.tune("driver_b", 3.0));
    }
    g.b_assume = num("phys.b_assume", cfg.tune("leader_b", if human && t.model == CfModel::Krauss { 4.5 } else { g.decel }));
    // Leaders and tails are judged by their hardest possible stop.
    g.apparent = g.b_hi;
}

fn lognormal(median: f32, sd: f32, lo: f32, hi: f32, state: &mut u64) -> f32 {
    (median * (normal(state) as f32 * sd).exp()).clamp(lo, hi)
}

/// One driver, as `research/truth/05-real-human-driving.md` section 8 draws them, packed for `GpuTrip`.
fn draw_persona(state: &mut u64) -> (u32, u32) {
    let q = |x: f32, lo: f32, hi: f32| (((x - lo) / (hi - lo)).clamp(0.0, 1.0) * 255.0).round() as u32;
    let t = lognormal(1.30, 0.25, 0.6, 3.0, state);
    let s0 = lognormal(2.8, 0.40, 0.5, 6.0, state);
    let amax = lognormal(1.80, 0.19, 1.0, 3.0, state);
    let d = lognormal(10.3, 0.33, 4.0, 22.0, state);
    let critical = lognormal(1.0, 0.26, 0.4, 2.5, state);
    let u = (uniform(state) as f32).clamp(1e-4, 1.0 - 1e-4);
    let yellow = 5.1 + 0.54 * (u / (1.0 - u)).ln();
    (q(t, 0.6, 3.0) | (q(s0, 0.5, 6.0) << 8) | (q(amax, 1.0, 3.0) << 16) | (q(d, 4.0, 22.0) << 24), q(critical, 0.4, 2.5) | (q(yellow, 2.0, 9.0) << 8))
}

/// Mean free speed over the limit on Swedish municipal main streets, Sept 2018, VTI rapport 1001. Unchecked above 70 km/h.
fn sweden_speed(limit: f32) -> f32 {
    match (limit * 3.6).round() as u32 {
        35..=44 => 0.98,
        45..=54 => 0.90,
        55..=64 => 0.85,
        65..=74 => 0.89,
        _ => 1.0,
    }
}

/// Load and power of one vehicle, packed for `GpuVeh::phys`.
fn draw_phys(vclass: u32, state: &mut u64) -> u32 {
    let r = phys_row(vclass);
    let load = (r.load.0 + (r.load.1 - r.load.0) * uniform(state) as f32).clamp(0.25, 2.0);
    let power = (normal(state) as f32 * r.power_sd).exp().clamp(0.5, 2.5);
    let lq = (((load - 0.25) * 146.0).round() as u32).min(255);
    let pq = (((power - 0.5) * 127.5).round() as u32).min(255);
    lq | (pq << 8)
}

/// Default vehicle, nominal load and power, for tests that want exact table values.
const PHYS_NOMINAL: u32 = 110 | (64 << 8);

fn gpu_vtype(t: &VType, dt: f32) -> GpuVType {
    let model = match t.model {
        CfModel::Krauss | CfModel::Eidm => 0,
        CfModel::Idm => 1,
        CfModel::Acc => 2,
        CfModel::Cacc => 3,
        CfModel::Av => 4,
        CfModel::Human => 5,
    };
    let delta = t.params.get("delta").and_then(|v| v.parse().ok()).unwrap_or(4.0);
    let stepping: f32 = t.params.get("stepping").and_then(|v| v.parse().ok()).unwrap_or(0.25);
    GpuVType {
        model,
        length: t.length,
        min_gap: t.min_gap,
        accel: t.accel,
        decel: t.decel,
        emergency: t.emergency_decel,
        apparent: t.apparent_decel,
        tau: t.tau,
        sigma: t.sigma,
        max_speed: t.max_speed,
        impatience: t.impatience,
        timegap_minor: t.jm_timegap_minor,
        vclass: t.vclass,
        idm_delta: delta,
        idm_iters: ((dt / stepping + 0.5) as u32).max(1),
        two_sqrt_ab: 2.0 * (t.accel * t.decel).sqrt(),
        headway_acc: t.headway_time_acc,
        glosa_range: if t.glosa { t.glosa_range } else { 0.0 },
        lc_strategic: t.lc_strategic,
        lc_cooperative: t.lc_cooperative,
        lc_speed_gain: t.lc_speed_gain,
        lc_keep_right: t.lc_keep_right,
        lc_assertive: t.lc_assertive,
        lc_look_left: t.lc_lookahead_left,
        lc_speed_gain_right: t.lc_speed_gain_right,
        collision_factor: t.params.get("collisionMinGapFactor").and_then(|v| v.parse().ok()).unwrap_or(match t.model {
            CfModel::Krauss | CfModel::Eidm => 1.0,
            CfModel::Idm | CfModel::Acc | CfModel::Cacc => 0.1,
            CfModel::Human | CfModel::Av => 0.0,
        }),
        reaction: t.params.get("reactionTime").and_then(|v| v.parse().ok()).unwrap_or(0.3),
        ..Default::default()
    }
}

/// A nominal car, as the replay kernel needs it.
pub fn human_replay_type(t: &VType) -> GpuVType {
    let mut g = gpu_vtype(t, 0.1);
    physical_type(&mut g, t, &SimConfig::default());
    g.model = 4;
    g.v_lat = -1.0;
    g
}

impl World {
    pub fn build(net: &Net, demand: &Demand, cfg: &SimConfig, replicas: &[Replica]) -> Self {
        let topo = Topology::build(net);
        Self::build_with(net, &topo, demand, cfg, replicas)
    }

    pub fn build_with(net: &Net, topo: &Topology, demand: &Demand, cfg: &SimConfig, replicas: &[Replica]) -> Self {
        let mut w = World {
            bounds: net.bounds,
            speed_trace: cfg.speed_trace.clone(),
            route_arena: cfg.route_arena,
            ..Default::default()
        };
        let phys = (cfg.mu > 0.0).then(|| (crate::physics::lanes(net, cfg.tune("curve_cap", 4.3)), crate::physics::zones(net, topo, cfg.tune("zone_distance", 2.6), !cfg.humans)));
        w.vtypes = demand.vtypes.iter().map(|t| gpu_vtype(t, cfg.dt)).collect();
        if cfg.mu > 0.0 {
            for (g, t) in w.vtypes.iter_mut().zip(&demand.vtypes) {
                physical_type(g, t, cfg);
                if cfg.humans || matches!(t.model, CfModel::Human) {
                    g.model = 5;
                    // Below zero: lateral motion is a human's quintic, not a fixed speed.
                    g.v_lat = -1.0;
                    g.collision_factor = 0.0;
                }
            }
        }
        w.n_edges_per_replica = net.edges.len() as u32;
        let single = [Replica {
            seed: cfg.seed,
            ..Default::default()
        }];
        let reps: &[Replica] = if replicas.is_empty() { &single } else { replicas };
        let mut key_base = 0u64;
        let coord_base = cfg.coord.as_ref().map(|c| crate::coord::build(net, topo, c, cfg.dt, cfg.seed));
        if let Some(base) = &coord_base {
            w.coord = Some(crate::coord::CoordWorld {
                cfg: base.cfg,
                ids: base.ids.clone(),
                refused: base.refused.clone(),
                mov_chain: base.mov_chain.clone(),
                ..Default::default()
            });
        }
        for (ri, rep) in reps.iter().enumerate() {
            let lane0 = w.lanes.len() as u32;
            w.append_replica(net, topo, demand, cfg, rep, ri as u32, &mut key_base, phys.as_ref(), coord_base.as_ref());
            if let (Some(base), Some(out)) = (&coord_base, w.coord.as_mut()) {
                crate::coord::add_replica(out, base, lane0, ri as u32);
            }
        }
        // Teleporting vehicles wait on one extra lane that nothing connects to.
        w.lanes.push(GpuLane {
            length: 1.0,
            speed: 13.89,
            edge: 0,
            flags: 1,
            key_base: key_base as u32,
            key_scale: 0.0,
            det_pos: -1.0,
            pred: NONE,
            entry_link: NONE,
            ..Default::default()
        });
        key_base += 1;
        w.total_cells = key_base;
        let key_bits = 64 - (key_base + 2).leading_zeros();
        assert!(key_bits < 32, "too many sort cells: {key_base}");
        if let Some(out) = w.coord.as_mut() {
            out.cfg.n_junctions = out.junctions.len() as u32;
            out.cfg.n_apps = out.apps.len() as u32;
            out.cfg.n_exits = out.exits.len() as u32;
            out.n_replicas = reps.len() as u32;
            // Which coordinator record each simulated lane belongs to, in every replica.
            out.lane_info = vec![crate::coord::GpuCjLaneInfo { app: NONE, exit: NONE, box_mov: NONE, s_offset: 0.0 }; w.lanes.len()];
            if let Some(base) = &coord_base {
                let per_lanes = net.lanes.len();
                for r in 0..reps.len() {
                    let (a0, e0, m0) = (r * base.apps.len(), r * base.exits.len(), r * base.links.len());
                    for (l, i) in base.lane_info.iter().enumerate() {
                        let shift = |x: u32, by: usize| if x == NONE { NONE } else { x + by as u32 };
                        out.lane_info[r * per_lanes + l] = crate::coord::GpuCjLaneInfo {
                            app: shift(i.app, a0),
                            exit: shift(i.exit, e0),
                            box_mov: shift(i.box_mov, m0),
                            s_offset: i.s_offset,
                        };
                    }
                }
            }
        }
        let n_trips = w.trips.len() as u32;
        let capacity = if cfg.capacity == 0 { n_trips } else { cfg.capacity.min(n_trips) };
        // Shadows of lane changes share the vehicle array and get their own slice of it.
        let shadow_reserve = if cfg.mu > 0.0 { capacity / 20 + 64 } else { 0 };
        let capacity = capacity + shadow_reserve;
        let sample_steps = ((cfg.sample_seconds / cfg.dt).round() as u32).max(1);
        let n_steps = ((cfg.end_seconds - cfg.begin_seconds) / cfg.dt).ceil() as u32 + 1;
        let human = cfg.human.tuned(&cfg.tune);
        w.params = GpuParams {
            dt: cfg.dt,
            n_lanes: w.lanes.len() as u32,
            n_links: w.links.len() as u32,
            n_tls: w.tls.len() as u32,
            n_trips,
            n_edges: w.edges.len() as u32,
            capacity,
            n_replicas: reps.len() as u32,
            block: cfg.block,
            key_bits,
            n_queues: w.queues.len() as u32,
            teleport_steps: (cfg.time_to_teleport / cfg.dt).round() as u32,
            sample_steps,
            n_samples: n_steps / sample_steps + 2,
            tls_yellow_min_decel: cfg.tls_yellow_min_decel,
            time_to_impatience: cfg.time_to_impatience,
            ignore_blocker: cfg.ignore_blocker,
            script_t0: cfg.script_t0,
            dummy_lane: w.lanes.len() as u32 - 1,
            mu: cfg.mu,
            shadow_reserve,
            detect_every: if cfg.mu > 0.0 { cfg.detect_every } else { 0 },
            grid_mask: (capacity.max(16) as u64 * 2).next_power_of_two() as u32 - 1,
            trace_len: cfg.speed_trace.len() as u32,
            safety: (cfg.tune("certificate", 1.0) as u32) | ((cfg.tune("arbiter", 1.0) as u32) << 1) | ((cfg.tune("exit_clear", 1.0) as u32) << 2) | ((cfg.tune("lc_path", 1.0) as u32) << 3) | ((cfg.tune("rewind", 1.0) as u32) << 4),
            width_margin: cfg.tune("width_margin", 0.1),
            claim_scale: cfg.tune("claim_scale", 1.0),
            queue_speed: cfg.tune("queue_speed", 2.0),
            hu_k: 1.0 - (-cfg.dt / 1.0).exp(),
            hu_rho: (-cfg.dt / 3.0).exp(),
            hu_nscale: 0.20 * (1.0 - (-2.0 * cfg.dt / 3.0).exp()).sqrt(),
            hu_flags: cfg.human_flags | if !cfg.humans && cfg.tune("decide", 1.0) > 0.0 { 8192 } else { 0 },
            hu_a: [human.cooperation, human.t_miss, 0.0, human.stop_base],
            hu_b: [human.stop_offset, human.sig_react, human.r_urg, human.coop_decel],
            hu_c: [human.tau_gate, human.tau_min, human.b_em, human.gap_model],
            hu_d: [human.gap_junction, human.gap_roundabout, human.t_scale, human.s0_scale],
            hu_e: [human.lead_shift, human.lag_shift, human.lc_safety, human.a_y],
            hu_f: [human.b_approach, human.tau_approach, human.overshoot, human.standing],
            hu_g: [human.see, human.lc_slope, human.stop_s0, human.comfort],
            hu_i: [human.gipps_b, human.gipps_tau, human.w_s_near, human.free_table],
            hu_h: [human.stub, human.lead_far, human.lag_far, human.b_end],
            hm_a: [human.tte0, human.s_0, human.s_t, human.s_lag],
            hm_b: [human.s_lead, human.s_driver, human.w_f, human.t_f],
            hm_c: [human.b_f, human.w_s_neg, human.w_s_pos, human.k_c],
            hm_d: [human.q_edge, human.v_edge, human.tau_a, human.tau_sd],
            lost_after: cfg.tune("lost_after", 0.0),
            zones_ahead: cfg.tune("zones_ahead", 0.0) as u32,
            lc_gap: cfg.tune("lc_gap", 0.6),
            zone_time: cfg.tune("zone_time", 1.0) as u32,
            lc_crawl: cfg.tune("lc_crawl", 0.5),
            lc_carry: cfg.tune("lc_carry", 0.0) as u32,
            meter_n: cfg.meter_n,
            lateral_median: cfg.tune("lateral_median", 2.2),
            vis_floor: cfg.tune("vis_floor", 30.0),
            lc_patience: cfg.tune("lc_patience", 10.0),
            gap_spread: cfg.tune("gap_spread", if cfg.humans { 0.0 } else { 0.3 }),
            abreast_b: cfg.tune("abreast_b", if cfg.humans { 0.0 } else { 2.5 }),
            miss_patience: if cfg.route_arena > 0 && !cfg.humans { cfg.tune("miss_patience", 60.0) } else { 0.0 },
            miss_short: cfg.tune("miss_short", 15.0),
            // Report 05, DLR UT: position 2 moves 1.0 s after its predecessor, the first car 1.62 s after green.
            start_react: if cfg.humans { 0.0 } else { cfg.tune("start_react", 1.0) },
            // The measured driver: SinD weekdays pass 1.5 m/s 2.0 s after green, of which its 0.5 s response takes 1.22 s.
            first_react: if cfg.humans { 0.0 } else { cfg.tune("first_react", if cfg.measured() { 0.78 } else { 1.62 }) },
            pad_f: 0.0,
            pad_g: 0.0,
            pad_h: 0.0,
            pad_i: 0.0,
            md_a: [cfg.tune("md_k", MD_K), cfg.tune("md_ca", MD_CA), cfg.tune("md_kg", MD_KG), cfg.tune("md_kp", MD_KP)],
            md_b: {
                // An OU noise averaged over the step: the same noise at any dt, down to a correlation time under one step.
                let (sd, tn, dt) = (cfg.tune("md_noise", MD_NOISE_SD), cfg.tune("md_noise_t", MD_NOISE_T), cfg.dt);
                let avg = (2.0 * (tn / dt).powi(2) * (dt / tn - 1.0 + (-dt / tn).exp())).sqrt();
                [1.0 - (-cfg.dt / cfg.tune("md_tau_r", MD_TAU_R)).exp(), (-dt / tn).exp(), sd * avg, if cfg.measured() { 1.0 } else { 0.0 }]
            },
            md_c: [cfg.tune("md_s0", MD_S0), cfg.tune("md_near", 0.5), cfg.tune("md_dv_max", 1.5), cfg.tune("md_tv", MD_TV)],
            md_t: [1.6, 1.4, 1.2, 1.1],
            md_u: [0.95, 0.8, 0.0, 0.0],
            lcm_a: [cfg.tune("lcm_a0", LCM_A0), cfg.tune("lcm_at", LCM_AT), cfg.tune("lcm_lag_mu", LCM_LAG[0]), cfg.tune("lcm_lag_close", LCM_LAG[1])],
            lcm_b: [cfg.tune("lcm_lag_sd", LCM_LAG[2]), cfg.tune("lcm_lead_mu", LCM_LEAD[0]), cfg.tune("lcm_lead_close", LCM_LEAD[1]), cfg.tune("lcm_lead_sd", LCM_LEAD[2])],
            lcm_c: [cfg.tune("lcm_courtesy", LCM_COURTESY), if !cfg.humans && cfg.tune("lc_measured", 0.0) > 0.0 { 1.0 } else { 0.0 }, 0.0, 0.0],
        };
        w
    }

    /// Replace routes, trips and queues without touching the network. `Sim::write_demand` uploads them.
    /// Trips must be sorted by departure, as `Demand::load` leaves them.
    pub fn rewrite_demand(&mut self, net: &Net, topo: &Topology, demand: &Demand, cfg: &SimConfig, replicas: &[Replica]) {
        self.routes.clear();
        self.trips.clear();
        self.trip_source.clear();
        self.queues.clear();
        self.queue_trips.clear();
        let single = [Replica { seed: cfg.seed, ..Default::default() }];
        let reps: &[Replica] = if replicas.is_empty() { &single } else { replicas };
        for (ri, rep) in reps.iter().enumerate() {
            let edge0 = self.replica_edge_start[ri];
            self.append_demand(net, topo, demand, cfg, rep, ri as u32, edge0);
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn append_replica(
        &mut self,
        net: &Net,
        topo: &Topology,
        demand: &Demand,
        cfg: &SimConfig,
        rep: &Replica,
        ri: u32,
        key_base: &mut u64,
        phys: Option<&(Vec<crate::physics::LanePhys>, Vec<Vec<GpuZone>>)>,
        coord: Option<&crate::coord::CoordWorld>,
    ) {
        let lane0 = self.lanes.len() as u32;
        let node_ids: std::collections::HashMap<&str, u32> = net.junctions.iter().enumerate().map(|(i, j)| (j.id.as_str(), i as u32)).collect();
        let edge0 = self.edges.len() as u32;
        let link0 = self.links.len() as u32;
        let tls0 = self.tls.len() as u32;
        self.replica_edge_start.push(edge0);

        let roundabout: Vec<bool> = {
            let mut r = vec![false; net.edges.len()];
            for &e in &net.roundabout_edges {
                r[e as usize] = true;
            }
            r
        };
        // Edges.
        for (ei, e) in net.edges.iter().enumerate() {
            let mut length = 0.0f32;
            if e.lane_count > 0 {
                length = net.lanes[e.first_lane as usize].length;
                for l in 0..e.lane_count {
                    length = length.min(net.lanes[(e.first_lane + l) as usize].length);
                }
            }
            self.edges.push(GpuEdge {
                first_lane: e.first_lane + lane0,
                lane_count: e.lane_count,
                length,
                flags: u32::from(e.func == EdgeFunc::Internal) | if roundabout[ei] { 2 } else { 0 },
            });
            self.edge_is_normal.push(e.func != EdgeFunc::Internal);
        }

        // Traffic lights, which lanes and detectors depend on.
        let mut tls_links: Vec<Vec<u32>> = vec![Vec::new(); net.tls.len()];
        for (id, l) in topo.links.iter().enumerate() {
            if let Some(t) = l.tl {
                tls_links[t as usize].push(id as u32);
            }
        }
        for (ti, t) in net.tls.iter().enumerate() {
            let first_phase = self.phases.len() as u32;
            let steps = |s: f32| ((s / cfg.dt).round() as u32).max(1);
            let mut cycle = 0.0f32;
            for ph in &t.phases {
                let state_start = self.states.len() as u32;
                self.states.extend(ph.state.iter().map(|&c| c as u32));
                self.phases.push(GpuTlsPhase {
                    duration: steps(ph.duration),
                    min_dur: steps(ph.min_dur),
                    max_dur: steps(ph.max_dur),
                    state_start,
                    loops_start: 0,
                    loops_count: 0,
                });
                cycle += ph.duration;
            }
            // Position in the cycle at time 0, given the offset.
            let mut pos = (cfg.begin_seconds - t.offset).rem_euclid(cycle.max(1e-3));
            let mut phase = 0u32;
            for ph in &t.phases {
                if pos < ph.duration {
                    break;
                }
                pos -= ph.duration;
                phase += 1;
            }
            let phase = phase.min(t.phases.len() as u32 - 1);
            let actuated = cfg.use_actuation && t.tl_type == "actuated";
            self.tls.push(GpuTlsState {
                phase,
                next_switch: steps(t.phases[phase as usize].duration - pos),
                first_phase,
                n_phases: t.phases.len() as u32,
                last_change: 0,
                actuated: u32::from(actuated),
                link_start: tls_links[ti].first().copied().unwrap_or(0) + link0,
                link_count: tls_links[ti].len() as u32,
            });
        }

        // Lanes.
        let mut degree: std::collections::HashMap<&str, u32> = std::collections::HashMap::new();
        for e in net.edges.iter().filter(|e| e.func != EdgeFunc::Internal) {
            *degree.entry(e.from.as_str()).or_insert(0) += 1;
            *degree.entry(e.to.as_str()).or_insert(0) += 1;
        }
        let mut detector_pos = vec![-1.0f32; net.lanes.len()];
        let mut actuation: Vec<Option<Actuation>> = Vec::new();
        for (id, t) in net.tls.iter().enumerate() {
            if cfg.use_actuation && t.tl_type == "actuated" {
                let a = crate::actuated::build(net, topo, t, &tls_links[id]);
                for &(lane, pos) in &a.placements {
                    detector_pos[lane as usize] = detector_pos[lane as usize].max(pos);
                }
                actuation.push(Some(a));
            } else {
                actuation.push(None);
            }
        }
        for (li, l) in net.lanes.iter().enumerate() {
            let shape_start = self.shapes.len() as u32;
            if ri == 0 {
                self.shapes.extend_from_slice(&l.shape);
                self.shape_range.push((shape_start, l.shape.len() as u32));
            }
            let cells = (l.length / KEY_METRES).ceil() as u64 + 1;
            let links = &topo.lane_links[li];
            let internal = net.is_internal_lane(li as u32);
            let incoming = topo.incoming[li].first().copied();
            self.lanes.push(GpuLane {
                length: l.length,
                speed: if cfg.tune("free_speed_sweden", 0.0) > 0.0 { l.speed * sweden_speed(l.speed) } else { l.speed },
                edge: l.edge + edge0,
                links_start: links.first().copied().unwrap_or(0) + link0,
                links_count: links.len() as u32,
                index: l.index,
                allow: l.allow,
                flags: u32::from(internal)
                    | if on_roundabout(topo, net, &roundabout, li as u32) { 2 } else { 0 }
                    | if degree.get(net.edges[l.edge as usize].to.as_str()).copied().unwrap_or(0) > 2 { 4 } else { 0 },
                key_base: *key_base as u32,
                key_scale: 1.0 / KEY_METRES,
                det_pos: detector_pos[li],
                shape_start,
                pred: if internal {
                    incoming.map(|inc| normal_pred(topo, net, inc) + lane0).unwrap_or(NONE)
                } else {
                    NONE
                },
                entry_link: incoming.map(|inc| topo.links[inc as usize].entry + link0).unwrap_or(NONE),
                pad: [l.change_left, l.change_right],
                in_start: 0,
                in_count: 0,
                ..Default::default()
            });
            if let Some((ph, _)) = phys {
                let g = self.lanes.last_mut().unwrap();
                let lp = &ph[li];
                g.gz = lp.gz;
                g.curve_v = lp.curve_v;
                g.sqrt_path_r = lp.sqrt_path_r;
                g.sqrt_r = lp.sqrt_r;
                g.s_curve = lp.s_curve;
                g.s_curve_end = lp.s_curve_end;
                g.width = l.width.max(1.0);
                let e = &net.edges[l.edge as usize];
                let node = |id: &str| node_ids.get(id).copied().unwrap_or(NONE);
                if e.func == EdgeFunc::Internal {
                    let j = l.id[1..].rsplitn(3, '_').last().unwrap_or("");
                    let n = node(j);
                    g.from_node = n;
                    g.to_node = n;
                } else {
                    g.from_node = node(&e.from);
                    g.to_node = node(&e.to);
                }
                g.geom_scale = lp.geom_length / l.length.max(1e-3);
                if ri == 0 {
                    g.shape_start = self.shape_points.len() as u32;
                    g.shape_count = l.shape.len() as u32;
                    let mut at = 0.0f32;
                    let mut last = l.shape.first().copied().unwrap_or([0.0, 0.0]);
                    for q in &l.shape {
                        at += ((q[0] - last[0]).powi(2) + (q[1] - last[1]).powi(2)).sqrt();
                        self.shape_points.push([q[0], q[1], at, 0.0]);
                        last = *q;
                    }
                }
            }
            *key_base += cells;
        }

        if let Some((_, zones)) = phys {
            for (li, list) in zones.iter().enumerate() {
                let g = &mut self.lanes[lane0 as usize + li];
                g.zone_start = self.zones.len() as u32;
                g.zone_count = list.len() as u32;
                self.zones.extend(list.iter().map(|z| GpuZone { foe_lane: z.foe_lane + lane0, ..*z }));
            }
        }
        if let Some(c) = coord {
            for &(l, f) in &c.lane_flags {
                self.lanes[lane0 as usize + l as usize].flags |= f;
            }
        }

        // Links must sit contiguously per lane: rebuild them lane by lane.
        // Connection order within a lane is preserved.
        let mut remap = vec![0u32; topo.links.len()];
        {
            let mut at = link0;
            for links in &topo.lane_links {
                for &id in links {
                    remap[id as usize] = at;
                    at += 1;
                }
            }
        }
        for (li, links) in topo.lane_links.iter().enumerate() {
            if let Some(&f) = links.first() {
                self.lanes[lane0 as usize + li].links_start = remap[f as usize];
            }
        }
        for (li, inc) in topo.incoming.iter().enumerate() {
            let gl = &mut self.lanes[lane0 as usize + li];
            gl.in_start = self.incoming_links.len() as u32;
            gl.in_count = inc.len() as u32;
            self.incoming_links.extend(inc.iter().map(|&l| remap[l as usize]));
        }
        let mut watched = vec![false; topo.links.len()];
        for l in &topo.links {
            for &f in &l.foe_links {
                watched[f as usize] = true;
            }
        }
        for gl in self.lanes.iter_mut().skip(lane0 as usize) {
            if gl.entry_link != NONE {
                gl.entry_link = remap[(gl.entry_link - link0) as usize];
            }
        }
        for (ti, t) in self.tls.iter_mut().skip(tls0 as usize).enumerate() {
            t.link_start = self.incoming_links.len() as u32;
            self.incoming_links.extend(tls_links[ti].iter().map(|&l| remap[l as usize]));
            if let Some(a) = &actuation[ti] {
                for (p, loops) in a.phase_loops.iter().enumerate() {
                    let ph = &mut self.phases[t.first_phase as usize + p];
                    ph.loops_start = self.incoming_links.len() as u32;
                    ph.loops_count = loops.len() as u32;
                    self.incoming_links.extend(loops.iter().map(|&l| l + lane0));
                }
            }
        }
        for links in &topo.lane_links {
            for &id in links {
                let l = &topo.links[id as usize];
                let foe_start = self.foes.len() as u32;
                self.foes.extend(l.foe_links.iter().map(|&f| remap[f as usize]));
                let conf_start = self.conflicts.len() as u32;
                for c in &l.conflicts {
                    let mut flags = 0;
                    if c.same_target {
                        flags |= 1;
                    }
                    if c.same_source {
                        flags |= 2;
                    }
                    if c.cont_lane {
                        flags |= 4;
                    }
                    if c.dummy_merge {
                        flags |= 8;
                    }
                    if c.len_behind < -1000.0 {
                        flags |= 16;
                    }
                    self.conflicts.push(GpuConflict {
                        foe_lane: c.foe_lane + lane0,
                        flags,
                        len_behind: c.len_behind,
                        foe_len_behind: c.foe_len_behind,
                        width: c.width,
                        foe_width: c.foe_width,
                    });
                }
                let mut flags = 0u32;
                if l.cont {
                    flags |= 1;
                }
                if l.has_foes {
                    flags |= 2;
                }
                if l.keep_clear {
                    flags |= 4;
                }
                if l.via.is_some() {
                    flags |= 8;
                }
                if l.internal_before.is_some() {
                    flags |= 16;
                }
                if topo_exit_after_ij(topo, id) {
                    flags |= 32;
                }
                if l.internal_before.is_some() && l.via.is_some() {
                    flags |= 64;
                }
                flags |= (l.dir as u32) << 8;
                let coordinated = coord.is_some_and(|c| c.link_flags[id as usize] != 0);
                if coordinated {
                    flags |= crate::coord::L_COORD;
                } else if watched[id as usize] {
                    flags |= 1 << 16;
                }
                self.links.push(GpuLink {
                    next_lane: l.next_lane + lane0,
                    to_lane: l.to_lane + lane0,
                    to_edge: l.to_edge + edge0,
                    flags,
                    tl: l.tl.map(|t| t + tls0).unwrap_or(NONE),
                    tl_index: l.tl_index,
                    foe_start,
                    foe_count: l.foe_links.len() as u32,
                    conf_start,
                    conf_count: l.conflicts.len() as u32,
                    length: l.length,
                    visibility: l.visibility,
                    entry: remap[l.entry as usize],
                    before: l.internal_before.map(|b| b + lane0).unwrap_or(NONE),
                    state: l.state as u32,
                    from_lane: l.from_lane + lane0,
                    tc: if cfg.mu <= 0.0 { 0.0 } else if cfg.humans { (critical_gap(net, topo, l) - cfg.tune("tc_clear", 1.2)).max(0.1) } else { if cfg.measured() && roundabout[l.to_edge as usize] && !roundabout[net.lanes[l.from_lane as usize].edge as usize] && critical_gap_hbs(net, topo, l, true) > 0.0 { cfg.tune("tc_roundabout", 3.0) } else { critical_gap_hbs(net, topo, l, cfg.measured()) * cfg.tune("tc_scale", 1.0) } },
                });
            }
        }

        self.append_demand(net, topo, demand, cfg, rep, ri, edge0);
    }

    /// Routes and trips of one replica.
    #[allow(clippy::too_many_arguments)]
    fn append_demand(&mut self, net: &Net, topo: &Topology, demand: &Demand, cfg: &SimConfig, rep: &Replica, ri: u32, edge0: u32) {
        // Only routes a trip uses: assignment keeps alternatives in the arena that no vehicle follows today.
        let mut used = vec![false; demand.routes.len()];
        for t in &demand.trips {
            used[t.route as usize] = true;
        }
        let mut route_at = Vec::with_capacity(demand.routes.len());
        for (i, r) in demand.routes.iter().enumerate() {
            route_at.push(self.routes.len() as u32);
            if used[i] {
                self.routes.extend(r.iter().map(|&e| e + edge0));
            }
        }
        let mut rng_state = rep.seed.wrapping_mul(0x2545F4914F6CDD1D) ^ (ri as u64 + 1);
        let mut by_edge: Vec<Vec<u32>> = vec![Vec::new(); net.edges.len()];
        let mut by_lane: std::collections::BTreeMap<(u32, u32), Vec<u32>> = Default::default();
        for (ti, t) in demand.trips.iter().enumerate() {
            if t.depart < cfg.begin_seconds as f64 {
                continue;
            }
            let route = &demand.routes[t.route as usize];
            let vtype_id = rep.trip_vtype.get(ti).copied().unwrap_or(t.vtype);
            let vt = &demand.vtypes[vtype_id as usize];
            let (depart_lane, _) = match t.depart_lane {
                DepartLane::First => (-1, 0),
                DepartLane::Index(i) => (i as i32, 0),
                DepartLane::Random => (-2, 0),
                DepartLane::Free => (-3, 0),
                DepartLane::Allowed => (-4, 0),
                DepartLane::Best => (-5, 0),
                DepartLane::BestProb => (-6, 0),
            };
            let (depart_pos, depart_pos_mode) = match t.depart_pos {
                DepartPos::Base => (0.0, 0),
                DepartPos::Value(v) => (v, 1),
                DepartPos::Random | DepartPos::RandomFree | DepartPos::Free => (0.0, 2),
                DepartPos::Last => (0.0, 0),
            };
            let (depart_speed, depart_speed_mode) = match t.depart_speed {
                DepartSpeed::Zero => (0.0, 0),
                DepartSpeed::Value(v) => (v, 1),
                DepartSpeed::Random => (0.0, 2),
                DepartSpeed::Max => (0.0, 3),
                DepartSpeed::Desired => (0.0, 4),
                DepartSpeed::SpeedLimit => (0.0, 5),
                DepartSpeed::Avg => (0.0, 6),
            };
            let arrival = match t.arrival_pos {
                ArrivalPos::Max => 1e9,
                ArrivalPos::Value(v) => v,
                ArrivalPos::Random => {
                    let e = route.last().copied().unwrap_or(0);
                    let edge = &net.edges[e as usize];
                    let len = net.lanes[edge.first_lane as usize].length;
                    uniform(&mut rng_state) as f32 * len
                }
            };
            let md = md_type(vt, cfg);
            let sf = if md && vt.speed_factor_dev == 0.1 {
                // DRIVER.md: desired speed spreads by a CV of 0.12-0.20 between drivers; SUMO's 0.1 is too narrow.
                speed_factor(&VType { speed_factor_dev: cfg.tune("md_speed_dev", MD_SPEED_DEV), ..vt.clone() }, &mut rng_state)
            } else {
                speed_factor(vt, &mut rng_state)
            };
            // DRIVER.md: each driver keeps a time gap factor (log-SD 0.27) for the trip, lower for drivers who are fast when free.
            let gap_f = if md {
                let dev = if vt.speed_factor_dev == 0.1 { cfg.tune("md_speed_dev", MD_SPEED_DEV) } else { vt.speed_factor_dev } as f64;
                let zv = if dev > 0.0 { (sf as f64 - vt.speed_factor_mean as f64) / (dev * vt.speed_factor_mean as f64) } else { 0.0 };
                let r = cfg.tune("md_gap_speed_r", MD_GAP_SPEED_R as f32) as f64;
                let z = r * zv + (1.0 - r * r).sqrt() * normal(&mut rng_state);
                (cfg.tune("md_gap_sd", MD_GAP_SD as f32) as f64 * z).exp() as f32
            } else {
                0.0
            };
            let (persona, persona2) = if cfg.mu > 0.0 && (cfg.humans || matches!(vt.model, CfModel::Human)) { draw_persona(&mut rng_state) } else { (0, 0) };
            let mask = match t.depart_lane {
                DepartLane::Best | DepartLane::BestProb => {
                    *self.depart_masks.entry((t.route, vtype_id)).or_insert_with(|| crate::bestlanes::depart_mask(net, topo, route, vt))
                }
                _ => 0,
            };
            let id = self.trips.len() as u32;
            self.trip_source.push(ti as u32);
            let start = route_at[t.route as usize];
            self.trips.push(GpuTrip {
                depart_step: ((t.depart - cfg.begin_seconds as f64) / cfg.dt as f64 - 1e-6).ceil().max(0.0) as u32,
                route_start: start,
                route_end: start + route.len() as u32,
                vtype: vtype_id,
                depart_lane,
                depart_pos,
                depart_pos_mode,
                depart_speed,
                depart_speed_mode,
                arrival,
                sf,
                rng: splitmix(&mut rng_state) as u32,
                replica: ri,
                pad: [0, mask, if cfg.mu > 0.0 {
                    if vt.params.contains_key("phys.nominal") { PHYS_NOMINAL } else { draw_phys(vt.vclass, &mut rng_state) }
                } else { 0 }],
                persona,
                persona2,
                gap_f,
            });
            match t.depart_lane {
                DepartLane::Index(l) if cfg.per_lane_queues => by_lane.entry((route[0], l)).or_default().push(id),
                _ => by_edge[route[0] as usize].push(id),
            }
        }
        for ((e, _), list) in by_lane {
            let next = self.queue_trips.len() as u32;
            self.queue_trips.extend_from_slice(&list);
            self.queues.push(GpuQueue { edge: e + edge0, next, end: self.queue_trips.len() as u32, pad: 0 });
        }
        for (e, list) in by_edge.into_iter().enumerate() {
            if list.is_empty() {
                continue;
            }
            let next = self.queue_trips.len() as u32;
            self.queue_trips.extend_from_slice(&list);
            self.queues.push(GpuQueue {
                edge: e as u32 + edge0,
                next,
                end: self.queue_trips.len() as u32,
                pad: 0,
            });
        }
    }
}

/// Trafikverket's base critical gaps, TRVMB Kapacitet: major left, minor right, straight, left, for give way
/// and stop, on a 50 km/h major road, and 0.9 s more at 70 km/h. A critical gap runs from one major vehicle
/// to the next at the conflict point; a driver can use it only after the first has cleared, which `tc_clear` takes off.
fn critical_gap(net: &Net, topo: &Topology, l: &crate::topology::Link) -> f32 {
    let entry = &topo.links[l.entry as usize];
    let foes = if l.foe_links.is_empty() { &entry.foe_links } else { &l.foe_links };
    if foes.is_empty() {
        return 0.0;
    }
    let stop = matches!(entry.state, b's' | b'w');
    // Turning left from a lane that also has right of way somewhere is the major road's left.
    let major_left = topo.lane_links[entry.from_lane as usize].iter().any(|&k| matches!(topo.links[k as usize].state, b'M' | b'O'));
    let base = match (entry.dir, stop) {
        (b'l' | b'L' | b't', _) if major_left => 4.8,
        (b'r' | b'R', false) => 5.0,
        (b'r' | b'R', true) => 5.7,
        (b'l' | b'L' | b't', false) => 5.3,
        (b'l' | b'L' | b't', true) => 6.0,
        (_, false) => 5.1,
        (_, true) => 5.8,
    };
    let fast = foes.iter().map(|&f| net.lanes[topo.links[f as usize].from_lane as usize].speed).fold(0.0f32, f32::max);
    base + 0.9 * ((fast - 50.0 / 3.6) / (20.0 / 3.6)).clamp(0.0, 1.0)
}

/// HBS 2015 S5, urban give-way, critical gap by movement: right from the minor road 5.9 s, left from the major 5.5,
/// through 6.7, left from the minor 6.5 (KNOBEL form of HBS 2015; foundations/B §3). Stop sign and a fast major road
/// as TRVMB adds them: 0.7 s and up to 0.9 s.
/// HBS 2015 S5 by movement, or with `measured` the critical gaps of DRIVER.md (inD Bendplatz, rounD): minor road left
/// 6.9 s, minor road straight 6.6, left off the priority road 3.9, roundabout entry 3.0. Right from a minor road was not
/// measurable and keeps HBS's 5.9; the stop sign and fast major terms stay HBS's.
fn critical_gap_hbs(net: &Net, topo: &Topology, l: &crate::topology::Link, measured: bool) -> f32 {
    let entry = &topo.links[l.entry as usize];
    let foes = if l.foe_links.is_empty() { &entry.foe_links } else { &l.foe_links };
    if foes.is_empty() {
        return 0.0;
    }
    // A zipper is not a give-way: its turns are taken in the zipper's own crossing rule.
    if entry.state == b'Z' {
        return 0.0;
    }
    let stop = matches!(entry.state, b's' | b'w');
    let major_left = topo.lane_links[entry.from_lane as usize].iter().any(|&k| matches!(topo.links[k as usize].state, b'M' | b'O'));
    let base = match entry.dir {
        b'l' | b'L' | b't' if major_left => if measured { 3.9 } else { 5.5 },
        b'r' | b'R' => 5.9,
        b'l' | b'L' | b't' => if measured { 6.9 } else { 6.5 },
        _ => if measured { 6.6 } else { 6.7 },
    };
    let fast = foes.iter().map(|&f| net.lanes[topo.links[f as usize].from_lane as usize].speed).fold(0.0f32, f32::max);
    base + if stop { 0.7 } else { 0.0 } + 0.9 * ((fast - 50.0 / 3.6) / (20.0 / 3.6)).clamp(0.0, 1.0)
}

fn topo_exit_after_ij(topo: &Topology, id: u32) -> bool {
    let l = &topo.links[id as usize];
    let Some(before) = l.internal_before else { return false };
    let inc = &topo.incoming[before as usize];
    inc.len() == 1 && {
        let v = &topo.links[inc[0] as usize];
        v.internal_before.is_some() && v.via.is_some()
    }
}

/// A roundabout edge, or an internal lane between roundabout edges.
fn on_roundabout(topo: &Topology, net: &Net, roundabout: &[bool], lane: u32) -> bool {
    let edge = |l: u32| net.lanes[l as usize].edge as usize;
    if !net.is_internal_lane(lane) {
        return roundabout[edge(lane)];
    }
    let (Some(&inc), Some(&out)) = (topo.incoming[lane as usize].first(), topo.lane_links[lane as usize].first()) else {
        return false;
    };
    roundabout[edge(normal_pred(topo, net, inc))] || roundabout[edge(topo.links[out as usize].to_lane)]
}

fn normal_pred(topo: &Topology, net: &Net, link: u32) -> u32 {
    let mut lane = topo.links[link as usize].from_lane;
    let mut guard = 0;
    while net.is_internal_lane(lane) && guard < 8 {
        let Some(&inc) = topo.incoming[lane as usize].first() else { break };
        lane = topo.links[inc as usize].from_lane;
        guard += 1;
    }
    lane
}
