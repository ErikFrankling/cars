// Shared data layout and car-following arithmetic. The equations follow SUMO's MSCFModel_*.
// Every struct here has a #[repr(C)] twin in world.rs.

const NONE: u32 = 0xffffffffu;
const EPS: f32 = 0.001;          // NUMERICAL_EPS
const POS_EPS: f32 = 0.1;        // POSITION_EPS
const HALT_SPEED: f32 = 0.1;     // SUMO_const_haltingSpeed
const MAX_ITEMS: u32 = 8u;       // drive items per vehicle
const SLOTS: u32 = 8u;           // approaching vehicles remembered per link
const SLOTS_NEAR: u32 = 4u;      // of which reserved for the first vehicles on the source lane
const CUTOFF: f32 = 40.0;        // approach further away in time than this cannot block anyone

const MODEL_KRAUSS: u32 = 0u;
const MODEL_IDM: u32 = 1u;
const MODEL_ACC: u32 = 2u;
const MODEL_CACC: u32 = 3u;
const MODEL_AV: u32 = 4u;

// Vehicle flags.
const F_REMOVED: u32 = 1u;        // arrived or teleported away, gone at the next sort
const F_ACC_GAP: u32 = 2u;        // ACC controller mode
const F_CACC_GAP: u32 = 4u;       // CACC controller mode
const F_WAITING: u32 = 8u;        // inside a waiting episode, for waitingCount
const F_BEST_DIRTY: u32 = 16u;    // best lanes need a refresh
const F_LANE_CHANGED: u32 = 32u;  // changed lane in the last step
const F_GLOSA_ACTIVE: u32 = 64u;
const F_ON_JUNCTION: u32 = 128u;
const F_HAVE_STOPPED: u32 = 256u; // has stopped for its stop sign
const F_WILL_PASS: u32 = 512u;     // requested its next link in the last step
const F_NEAR_ROUNDABOUT: u32 = 8192u; // a roundabout edge lies within 300 m on the route
const F_HAVE_TO_WAIT: u32 = 2048u; // must stop at its next link, as of the last step
const F_SCRIPTED: u32 = 1024u;     // gets the speed cap disturbance from Params.script_t0

// Link flags.
const L_CONT: u32 = 1u;
const L_HAS_FOES: u32 = 2u;
const L_KEEP_CLEAR: u32 = 4u;
const L_HAS_VIA: u32 = 8u;
const L_FROM_INTERNAL: u32 = 16u;
const L_EXIT_AFTER_IJ: u32 = 32u;
const L_INTERNAL_JUNCTION: u32 = 64u;
const L_WATCHED: u32 = 1u << 16u;  // some other link yields to this one
const L_COORD: u32 = 1u << 17u;    // at a coordinated junction

// Conflict flags.
const C_SAME_TARGET: u32 = 1u;
const C_SAME_SOURCE: u32 = 2u;
const C_CONT_LANE: u32 = 4u;
const C_DUMMY_MERGE: u32 = 8u;
const C_NO_CROSSING: u32 = 16u;

// Lane flags.
const LANE_INTERNAL: u32 = 1u;
const LANE_ROUNDABOUT: u32 = 2u;
const LANE_TO_BIG_JUNCTION: u32 = 4u;
const LANE_CJ: u32 = 8u;           // approach to, or inside, a coordinated junction
const LANE_CJ_EXIT: u32 = 16u;     // leaves one, and does not lead to another
const EDGE_ROUNDABOUT: u32 = 2u;

struct Params {
    dt: f32,
    n_lanes: u32,
    n_links: u32,
    n_tls: u32,
    n_trips: u32,
    n_edges: u32,
    capacity: u32,
    n_replicas: u32,
    block: u32,
    key_bits: u32,
    n_queues: u32,
    teleport_steps: u32,
    sample_steps: u32,
    n_samples: u32,
    tls_yellow_min_decel: f32,
    time_to_impatience: f32,
    ignore_blocker: f32,
    script_t0: f32,
    dummy_lane: u32,
    pad1: f32,
    meter_n: u32,
    pad2: u32,
    pad3: u32,
    pad4: u32,
}

struct Globals {
    step: u32,
    n_active: u32,
    n: u32,
    blocks: u32,
    sample: u32,
    pad0: u32,
    pad1: u32,
    pad2: u32,
}

struct Veh {
    pos: f32,
    speed: f32,
    lane: u32,
    route_i: u32,
    acc: f32,
    sf: f32,
    vtype: u32,
    trip: u32,
    rng: u32,
    route_end: u32,
    arrival: f32,
    flags: u32,
    wait: f32,
    lc_right: f32,
    lc_left: f32,
    lc_keep: f32,
    look_v: f32,
    best_cur: f32,
    best_left: f32,
    best_right: f32,
    best_off: i32,
    entry_step: u32,
    prev_lane: u32,
    prev2_lane: u32,
    tot_wait: f32,
    time_loss: f32,
    route_len: f32,
    depart_step: u32,
    wait_count: u32,
    replica: u32,
    v_next: f32,
    n_items: u32,
    lc_own: u32,
    left_space: f32,
    blocker: f32,
    occ_cur: f32,
    occ_left: f32,
    occ_right: f32,
    occ_best: f32,
    pad: u32,
    cj_t_line: f32,    // scheduled time at the stop line
    cj_v_line: f32,    // scheduled speed at the stop line
    cj_v_cruise: f32,
    cj_link: u32,      // movement it is scheduled on
    cj_state: u32,     // CJ_* in the low bits, then flags and the speed class
    cj_zone_t: f32,    // when it entered the control zone
    cj_seq: u32,       // commit order of its grant
    cj_hold: f32,      // path position to stop at during a fault
    cj_v_cmd: f32,     // this step's speed from cj_apply
    cj_yield: f32,     // path position to stop at for a sensed foe
    cj_t_ms: u32,      // the slot this car knows, in ms since start
    cj_plan_ms: u32,   // the slot the coordinator holds for it
    cj_rank: u32,      // its place in the junction's sequence, NONE before it is heard
}

struct Lane {
    length: f32,
    speed: f32,
    edge: u32,
    links_start: u32,
    links_count: u32,
    index: u32,
    allow: u32,
    flags: u32,
    key_base: u32,
    key_scale: f32,
    det_pos: f32,
    shape_start: u32,
    pred: u32,
    entry_link: u32,
    pad0: u32,
    pad1: u32,
    in_start: u32,
    in_count: u32,
}

struct Edge {
    first_lane: u32,
    lane_count: u32,
    length: f32,
    flags: u32,
}

struct Link {
    next_lane: u32,
    to_lane: u32,
    to_edge: u32,
    flags: u32,
    tl: u32,
    tl_index: u32,
    foe_start: u32,
    foe_count: u32,
    conf_start: u32,
    conf_count: u32,
    length: f32,
    visibility: f32,
    entry: u32,
    before: u32,
    state: u32,
    from_lane: u32,
}

struct Conflict {
    foe_lane: u32,
    flags: u32,
    len_behind: f32,
    foe_len_behind: f32,
    width: f32,
    foe_width: f32,
}

struct VType {
    model: u32,
    length: f32,
    min_gap: f32,
    accel: f32,
    decel: f32,
    emergency: f32,
    apparent: f32,
    tau: f32,
    sigma: f32,
    max_speed: f32,
    impatience: f32,
    timegap_minor: f32,
    vclass: u32,
    idm_delta: f32,
    idm_iters: u32,
    two_sqrt_ab: f32,
    headway_acc: f32,
    glosa_range: f32,
    lc_strategic: f32,
    lc_cooperative: f32,
    lc_speed_gain: f32,
    lc_keep_right: f32,
    lc_assertive: f32,
    lc_look_left: f32,
    lc_speed_gain_right: f32,
    collision_factor: f32,
    reaction: f32,
    pad2: f32,
}

struct Trip {
    depart_step: u32,
    route_start: u32,
    route_end: u32,
    vtype: u32,
    depart_lane: i32,
    depart_pos: f32,
    depart_pos_mode: u32,
    depart_speed: f32,
    depart_speed_mode: u32,
    arrival: f32,
    sf: f32,
    rng: u32,
    replica: u32,
    script: u32,
    best_mask: u32,
    pad2: u32,
}

struct TripOut {
    depart_step: u32,
    arrive_step: u32,
    wait: f32,
    time_loss: f32,
    route_len: f32,
    wait_count: u32,
    flags: u32,
    pad: u32,
}

struct LaneFree {
    space: f32,
    brutto: f32,
    flags: u32,
    mean_speed: f32,
}

struct Item {
    link: u32,
    v_pass: f32,
    v_wait: f32,
    request: u32,
    arrival: f32,
    arr_speed: f32,
    braking: f32,
    dist: f32,
    leave: f32,
    pad: f32,
}

struct Approach {
    arrival: f32,
    leave: f32,
    arr_speed: f32,
    leave_speed: f32,
    braking: f32,
    wait: f32,
    dist: f32,
    speed: f32,
    decel: f32,
    will_pass: u32,
    trip: u32,
    stamp: u32,
}

struct LaneSeg {
    first: u32,
    end: u32,
    stamp: u32,
    pad: u32,
}

struct TlsState {
    phase: u32,
    next_switch: u32,
    first_phase: u32,
    n_phases: u32,
    last_change: u32,
    actuated: u32,
    link_start: u32,
    link_count: u32,
}

struct TlsPhase {
    duration: u32,
    min_dur: u32,
    max_dur: u32,
    state_start: u32,
    loops_start: u32,
    loops_count: u32,
}

const CJ_NONE: u32 = 0u;
const CJ_ADVISED: u32 = 1u;
const CJ_FIRM: u32 = 2u;
const CJ_BOX: u32 = 3u;
const CJ_PENDING: u32 = 4u;       // the grant is written but has not reached the car
const CJ_STATE_MASK: u32 = 15u;
const CJ_ARMED: u32 = 16u;        // past its point of no return with the exit checked
const CJ_LATE: u32 = 32u;
const CJ_STALLED: u32 = 64u;      // injected failure
const CJ_WAS_MOVING: u32 = 128u;
const CJ_K_SHIFT: u32 = 8u;       // speed class of the grant
const CJ_HARD: u32 = 2048u;       // in a hard braking episode, for counting them
const CJ_KEEP: u32 = CJ_STALLED | CJ_WAS_MOVING | CJ_HARD;

const MODE_SUMO: u32 = 0u;
const MODE_FREE: u32 = 1u;
const MODE_SIGNAL: u32 = 2u;
const MODE_MIXED: u32 = 3u;

struct CjCfg {
    length: f32,
    width: f32,
    s0: f32,
    tau: f32,
    accel: f32,
    b_plan: f32,
    b_s: f32,
    b_e: f32,
    t_r: f32,
    m_t: f32,
    level_b: u32,
    tick_steps: u32,
    t_firm: f32,
    a_max: f32,
    unit: f32,
    exit_check: u32,
    ponr: u32,
    perception: u32,
    audit: u32,
    p_loss: f32,
    blackout_t0: f32,
    blackout_t1: f32,
    crash_t0: f32,
    crash_t1: f32,
    fallback: u32,
    stall_rate: f32,
    stall_t: f32,
    warm: f32,
    chan: u32,
    r50: f32,
    p_floor: f32,
    burst_len: f32,
    burst_every: f32,
    sig_min: f32,
    sig_max: f32,
    sig_gap: f32,
    sig_lost: f32,
    sig_start: f32,
    n_junctions: u32,
    n_apps: u32,
    n_exits: u32,
    plan: u32,         // bit 0 smooth profile, bit 1 stable far-out schedule, bit 2 followers read the leader's plan
    k_lane: u32,
    plan_max: u32,
    plan_b: f32,       // braking the plan assumes when it can choose
    plan_bc: f32,      // comfort limit of any planned braking
    plan_j: f32,       // jerk limit of planned control
    pos_err: f32,      // sigma of each car's position bias, m
    clock_err: f32,    // sigma of each car's clock bias, s
    dt_ms: u32,
    plan_up: f32,      // a held slot moves earlier only for this gain, s
    plan_range: f32,
    plan_freeze: f32,  // the order is fixed this long before the slot, s
    plan_slack: f32,   // a wait up to this long is planned at plan_b; longer, firmer up to plan_bc, s
    pad_a: u32,
    pad_b: u32,
    pad_c: u32,
}

struct CjJunction {
    app_start: u32,
    app_count: u32,
    exit_start: u32,
    exit_count: u32,
    mov_start: u32,
    mov_count: u32,
    rel_start: u32,
    rel_count: u32,
    plan_start: u32,
    plan_n: u32,
    aud_start: u32,
    aud_n: u32,
    tick_phase: u32,
    mode: u32,
    replica: u32,
    seq: u32,
    cx: f32,
    cy: f32,
    awsc_free: f32,
    frozen: u32,
    group_mask: u32,
    phase: u32,
    phase_t: f32,
    switch_t: f32,
    stall_active: u32,
    stall_trip: u32,
    stall_mov: u32,
    stall_seq: u32,
    stall_detect: f32,
    stall_until: f32,
    p_load: f32,
    pad: u32,
}

struct CjLink {
    junction: u32,
    from_lane: u32,
    to_lane: u32,
    conf_start: u32,
    conf_count: u32,
    pair_start: u32,
    pair_count: u32,
    path_len: f32,
    v_turn: f32,
    s_free: f32,
    pad_l: f32,
    v_lane: f32,
    v_after: f32,
    group: u32,
    conf_lanes: u32,
    path_start: u32,
    path_n: u32,
    sim_link: u32,
    dir_in: vec2f,
    dir_out: vec2f,
}

struct CjConflict {
    rel_index: u32,
    rev_index: u32,
    foe: u32,
    s_in: f32,
    s_out: f32,
    foe_s_in: f32,
}

struct CjPair {
    other: u32,
    is_exit: u32,
    table: u32,
    s_end: f32,
}

struct CjMovK {
    vk: f32,
    vout: f32,
    t_clear: f32,
    pad: f32,
}

struct CjApp {
    sim_lane: u32,
    junction: u32,
    ord: u32,
    req_start: u32,
    n_req: u32,
    mov_start: u32,
    mov_count: u32,
    speed: f32,
    length: f32,
    line_ref: u32,
    line_t: f32,
    s_line_ref: u32,
    s_line_t: f32,
    s_ptr: u32,
    s_cand_state: u32,
    s_cand_k: u32,
    s_cand_t: f32,
    s_cand_score: f32,
    box_tail: atomic<u32>,
    line_ms: u32,
    n_ranked: u32,
    box_tail_m: atomic<u32>,
    pad1: u32,
}

struct CjExit {
    sim_lane: u32,
    junction: u32,
    length: f32,
    exit_ref: u32,
    exit_t: f32,
    s_exit_ref: u32,
    s_exit_t: f32,
    n_on_lane: u32,
    has_tail: u32,
    tail_x: f32,
    tail_v: f32,
    n_committed: atomic<u32>,
    n_armed: atomic<u32>,
    n_box: atomic<u32>,
    block_t0: f32,
    block_t1: f32,
    cap_interval: f32,
    sink_ready: f32,
    seq: u32,
    exit_ms: u32,
    tail_a: f32,
}

struct CjReq {
    veh: u32,
    link: u32,
    d: f32,
    v: f32,
    age_t: f32,
    trip: u32,
    t_plan: f32,
    k_plan: u32,
    held: f32,      // seconds from now to its held slot, INF for none
    rank: f32,
    heard: u32,
    pad: u32,
}

struct CjBox {
    veh: u32,
    seq: u32,
    stamp: u32,
    mov: u32,
    s: f32,
    v: f32,
    trip: u32,
    pad: u32,
}

struct CjAud {
    f: vec2f,
    r: vec2f,
    trip: u32,
    mov: u32,
    s: f32,
    v: f32,
}

struct CjLaneInfo {
    app: u32,
    exit: u32,
    box_mov: u32,
    s_offset: f32,
}

// Per-vehicle context, set up at the top of a kernel.
var<private> ty: VType;
var<private> dt: f32;
var<private> ego_flags: u32;
var<private> ego_acc: f32;
var<private> mode_done: bool;

fn pcg(state: u32) -> u32 {
    let s = state * 747796405u + 2891336453u;
    let w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
    return (w >> 22u) ^ w;
}

fn rand01(rng: ptr<private, u32>) -> f32 {
    *rng = pcg(*rng);
    return f32(*rng >> 8u) * (1.0 / 16777216.0);
}

fn max_next_speed(v: f32) -> f32 {
    return min(v + ty.accel * dt, ty.max_speed);
}

fn min_next_speed(v: f32) -> f32 {
    var d = ty.decel;
    if (ty.model == MODEL_IDM) { d = max(ty.decel, min(ty.emergency, 1.5)); }
    return max(v - d * dt, 0.0);
}

fn min_next_speed_emergency(v: f32) -> f32 {
    return max(v - ty.emergency * dt, 0.0);
}

fn brake_gap(v: f32, decel: f32, headway: f32) -> f32 {
    let r = decel * dt;
    let steps = floor(v / r);
    return dt * (steps * v - r * steps * (steps + 1.0) * 0.5) + v * headway;
}

fn safe_stop_euler(gap: f32, decel: f32, headway: f32) -> f32 {
    let g = gap - EPS;
    if (g < 0.0) { return 0.0; }
    let b = decel * dt;
    let t = headway;
    let s = dt;
    let n = floor(0.5 - ((t + sqrt(s * s + 4.0 * (s * (2.0 * g / b - t) + t * t)) * -0.5) / s));
    let h = 0.5 * n * (n - 1.0) * b * s + n * b * t;
    let r = (g - h) / (n * s + t);
    return n * b + r;
}

fn emergency_decel(gap: f32, v: f32, vp: f32, bp: f32) -> f32 {
    if (gap <= 0.0) { return ty.emergency; }
    let pbd = 0.5 * vp * vp / bp;
    let b1 = 0.5 * v * v / (gap + pbd);
    if (b1 <= bp) { return b1; }
    return 0.5 * (v * v - vp * vp) / gap;
}

fn safe_stop(gap: f32, decel: f32, v: f32, headway: f32, relax: bool) -> f32 {
    var vsafe = safe_stop_euler(gap, decel, headway);
    if (relax && ty.decel != ty.emergency) {
        let orig = (v - vsafe) / dt;
        if (orig > ty.decel + EPS) {
            var safe_d = 1.2 * emergency_decel(gap, v, 0.0, 1.0);
            safe_d = min(max(safe_d, ty.decel), orig);
            vsafe = max(v - safe_d * dt, 0.0);
        }
    }
    return vsafe;
}

fn safe_follow(gap: f32, v: f32, vp: f32, bp: f32, on_insertion: bool) -> f32 {
    var x: f32;
    if (gap >= 0.0) {
        x = safe_stop(gap + brake_gap(vp, max(ty.decel, bp), 0.0), ty.decel, v, ty.tau, false);
    } else {
        x = max(v - ty.emergency * dt, 0.0);
    }
    if (ty.decel != ty.emergency && !on_insertion) {
        let orig = (v - x) / dt;
        if (orig > ty.decel + EPS) {
            var safe_d = 1.2 * emergency_decel(gap, v, vp, bp);
            safe_d = min(max(safe_d, ty.decel), orig);
            x = max(v - safe_d * dt, 0.0);
        }
    }
    return x;
}

fn idm_v(gap2pred: f32, v: f32, vp: f32, des: f32, respect_min_gap: bool) -> f32 {
    var nv = v;
    var gap = gap2pred;
    if (respect_min_gap) { gap += ty.min_gap; }
    let iters = f32(ty.idm_iters);
    for (var k = 0u; k < ty.idm_iters; k++) {
        let dv = nv - vp;
        var s = max(0.0, nv * ty.tau + nv * dv / ty.two_sqrt_ab);
        if (respect_min_gap) { s += ty.min_gap; }
        gap = max(EPS, gap);
        let acc = ty.accel * (1.0 - pow(nv / max(EPS, des), ty.idm_delta) - (s * s) / (gap * gap));
        nv = max(0.0, nv + acc * dt / iters);
        gap -= max(0.0, (nv - vp) * dt / iters);
    }
    return max(0.0, nv);
}

fn acc_gap_control(gap: f32, v: f32, vp: f32, verr: f32, headway: f32) -> f32 {
    let dv = vp - v;
    var d0 = 2.0;
    if (v > 0.0) { d0 = max(0.0, min(75.0 / v - 5.0, 2.0)); }
    let spacing = gap - headway * v - d0;
    if (abs(spacing) < 0.2 && abs(verr) < 0.1) {
        return 0.07 * dv + 0.23 * spacing;
    } else if (spacing < 0.0) {
        return 0.23 * dv + 0.8 * spacing;
    }
    return 0.8 * dv + 0.04 * spacing;
}

fn acc_v(gap: f32, v: f32, vp: f32, des: f32, headway: f32) -> f32 {
    let verr = v - des;
    let set_mode = !mode_done;
    mode_done = true;
    var a: f32;
    if (gap > 120.0) {
        a = -0.4 * verr;
        if (set_mode) { ego_flags &= ~F_ACC_GAP; }
    } else if (gap < 100.0) {
        a = acc_gap_control(gap, v, vp, verr, headway);
        if (set_mode) { ego_flags |= F_ACC_GAP; }
    } else if ((ego_flags & F_ACC_GAP) == 0u) {
        a = -0.4 * verr;
    } else {
        a = acc_gap_control(gap, v, vp, verr, headway);
    }
    return max(0.0, v + a * dt);
}

fn cacc_gap_control(gap: f32, v: f32, vp: f32, des: f32, verr: f32, leader_cacc: bool, has_leader: bool) -> f32 {
    if (!has_leader) { return v + (-0.4 * verr) * dt; }
    if (!leader_cacc) { return acc_v(gap, v, vp, des, ty.headway_acc); }
    let spacing = gap - ty.tau * v;
    let edot = vp - v - ty.tau * ego_acc;
    if (spacing > 0.0 && spacing < 0.2 && verr < 0.1) {
        return v + 0.45 * spacing + 0.0125 * edot;
    } else if (spacing < 0.0) {
        return v + 0.45 * spacing + 0.05 * edot;
    }
    return v + 0.005 * spacing + 0.05 * edot;
}

fn cacc_v(gap: f32, v: f32, vp: f32, des: f32, leader_cacc: bool, has_leader: bool) -> f32 {
    let verr = v - des;
    let time_gap = gap / max(EPS, v);
    let spacing = gap - ty.tau * v;
    var nv: f32;
    if (time_gap > 2.0 && spacing > 1.66) {
        nv = v + (-0.4 * verr) * dt;
        if (!mode_done) { ego_flags &= ~F_CACC_GAP; mode_done = true; }
    } else if (time_gap < 1.5) {
        nv = cacc_gap_control(gap, v, vp, des, verr, leader_cacc, has_leader);
        if (!mode_done) { ego_flags |= F_CACC_GAP; mode_done = true; }
    } else if ((ego_flags & F_CACC_GAP) == 0u) {
        nv = v + (-0.4 * verr) * dt;
    } else {
        nv = cacc_gap_control(gap, v, vp, des, verr, leader_cacc, has_leader);
    }
    if (dt < 0.1) { nv = v + (nv - v) * 10.0 * dt; }
    return max(0.0, nv);
}

// The automated car's safety filter: can stop behind a leader braking as hard as itself, after
// reaction time. Every AV kernel goes through these two, so the physics layer swaps them here.
fn av_safe_speed(gap: f32, vl: f32, b: f32, tr: f32, s0: f32) -> f32 {
    return -b * tr + sqrt(b * tr * b * tr + vl * vl + 2.0 * b * max(gap - 0.5 * s0, 0.0));
}

// The fastest a car may go and still stop before a line d ahead.
fn av_stop_curve(d: f32, b: f32, tr: f32) -> f32 {
    return b * (sqrt(tr * tr + 2.0 * max(d - 0.5, 0.0) / b) - tr);
}

// CF::followSpeed. `lane_vmax` is the lane's limit for this vehicle, `lane_limit` the posted limit.
fn follow_speed(v: f32, gap: f32, vp: f32, bp: f32, leader_cacc: bool, lane_vmax: f32, lane_limit: f32) -> f32 {
    switch ty.model {
        case MODEL_AV: {
            let g = gap + ty.min_gap;
            let a = 0.3 * (gap - v * ty.tau) + 0.8 * (vp - v);
            return max(0.0, min(v + min(a, ty.accel) * dt, av_safe_speed(g, vp, ty.apparent, ty.reaction, ty.min_gap)));
        }
        case MODEL_IDM: {
            return idm_v(gap, v, vp, lane_vmax, true);
        }
        case MODEL_ACC: {
            let des = min(lane_limit, ty.max_speed);
            let vacc = acc_v(gap, v, vp, des, ty.tau);
            let vsafe = safe_follow(gap, v, vp, bp, false);
            if (vsafe + 2.0 < vacc) { return vsafe + 2.0; }
            return vacc;
        }
        case MODEL_CACC: {
            let vc = cacc_v(gap, v, vp, lane_vmax, leader_cacc, true);
            let vsafe = safe_follow(gap, v, vp, bp, true);
            let ov = min(2.0, gap);
            if (vsafe + ov < vc) { return max(0.0, vsafe + ov); }
            return vc;
        }
        default: {
            return min(safe_follow(gap, v, vp, bp, false), max_next_speed(v));
        }
    }
}

// CF::stopSpeed
fn stop_speed(v: f32, gap: f32, decel: f32, relax: bool, lane_vmax: f32) -> f32 {
    if (ty.model == MODEL_IDM) {
        if (gap < 0.01) { return 0.0; }
        var r = idm_v(gap, v, 0.0, lane_vmax, false);
        if (gap > 0.0 && v < EPS && r < EPS) {
            r = safe_stop(gap, decel, v, dt, true);
        }
        if (gap >= 0.0) { r = min(r, gap / dt); }
        return r;
    }
    return min(safe_stop(gap, decel, v, dt, relax), max_next_speed(v));
}

// CF::insertionFollowSpeed
fn insertion_follow(speed: f32, gap: f32, vp: f32, bp: f32, vmax: f32, leader_cacc: bool) -> f32 {
    switch ty.model {
        case MODEL_IDM: {
            var v = speed;
            for (var i = 0u; i < 32u; i++) {
                if (gap >= idm_secure_gap(v, vp)) { return v; }
                let v2 = idm_v(gap, v, vp, vmax, true);
                let v3 = idm_v(gap, v2, vp, vmax, true);
                if (v2 - v3 < dt) { return v2; }
                v = v2;
            }
            return v;
        }
        case MODEL_ACC: {
            var res = speed;
            for (var i = 0u; i < 50u; i++) {
                let a = (follow_speed(res, gap, vp, bp, false, vmax, vmax) - res) / dt;
                res += 0.1 * a;
                if (abs(a) < 0.1) { break; }
            }
            return res;
        }
        case MODEL_CACC: {
            var res = speed;
            var damping = 0.8;
            for (var i = 0u; i < 50u; i++) {
                let a = min(cacc_v(gap, res, vp, speed, leader_cacc, true), safe_follow(gap, res, vp, bp, true)) - res;
                res += damping * a;
                damping *= 0.9;
                if (abs(a) < 0.1) { break; }
            }
            return res;
        }
        case MODEL_AV: { return speed; }
        default: { return safe_follow(gap, speed, vp, bp, true); }
    }
}

// CF::insertionStopSpeed
fn insertion_stop(speed: f32, gap: f32, vmax: f32) -> f32 {
    var v = speed;
    var r = stop_speed(v, gap, ty.decel, false, vmax);
    if (ty.model == MODEL_IDM) {
        for (var i = 1u; i < 10u; i++) {
            if (r - v >= -ty.decel * dt) { break; }
            v = r;
            r = stop_speed(v, gap, ty.decel, false, vmax);
        }
    }
    return r;
}

fn free_speed_euler(dist: f32, vt: f32, on_insertion: bool) -> f32 {
    let v = vt * dt;
    if (dist < v) { return vt; }
    let b = ty.decel * dt * dt;
    let y = max(0.0, ((sqrt((b + 2.0 * v) * (b + 2.0 * v) + 8.0 * b * dist) - b) * 0.5 - v) / b);
    let yf = floor(y);
    var extra = 0.0;
    if (y > yf) { extra = v; }
    let exact = (yf * yf + yf) * 0.5 * b + yf * v + extra;
    var gain = yf;
    if (on_insertion) { gain += 1.0; }
    return max(0.0, dist - exact) / (yf + 1.0) / dt + gain * ty.decel * dt + vt;
}

fn idm_secure_gap(v: f32, vl: f32) -> f32 {
    return max(0.0, v * ty.tau + v * (v - vl) / ty.two_sqrt_ab);
}

// CF::freeSpeed
fn free_speed(v: f32, seen: f32, vt: f32, lane_vmax: f32) -> f32 {
    if (vt < 0.0) { return vt; }
    if (ty.model == MODEL_IDM) {
        let sec = idm_secure_gap(vt, 0.0);
        var vs: f32;
        if (v <= vt) {
            vs = idm_v(1e6, v, vt, lane_vmax, false);
        } else {
            vs = idm_v(max(seen, sec), v, 0.0, lane_vmax, false);
        }
        if (seen < sec) { vs = min(vs, vt); }
        return vs;
    }
    return free_speed_euler(seen, vt, false);
}

fn estimate_speed(dist: f32, v: f32, a: f32) -> f32 {
    return min(ty.max_speed, sqrt(max(0.0, 2.0 * dist * a + v * v)));
}

fn minimal_arrival_time(dist: f32, v: f32, arr_in: f32) -> f32 {
    if (dist <= 0.0) { return 0.0; }
    let arr = max(0.0, arr_in);
    var a = -ty.decel;
    if (arr >= v) { a = ty.accel; }
    var at = 0.0;
    if (a != 0.0) { at = (arr - v) / a; }
    let way = at * (arr + v) * 0.5;
    if (dist >= way) {
        return at + (dist - way) / max(max(v, arr), HALT_SPEED);
    }
    return -(v - sqrt(v * v + 2.0 * a * dist)) / a;
}

fn minimal_arrival_speed_euler(dist: f32, v: f32) -> f32 {
    if (dist < v) { return -1.0; }
    if (2.0 * (dist - v * ty.tau) * -ty.decel + v * v >= 0.0) {
        return estimate_speed(dist - v * ty.tau, v, -ty.decel);
    }
    return ty.decel;
}

// CF::getSecureGap, used by lane changing and insertion.
fn secure_gap(v: f32, vl: f32, bl: f32) -> f32 {
    switch ty.model {
        case MODEL_IDM: { return idm_secure_gap(v, vl); }
        case MODEL_ACC: { return 0.07 * (v - vl) / 0.23 + ty.tau * v; }
        default: {
            return max(0.0, brake_gap(v, ty.decel, ty.tau) - brake_gap(vl, max(ty.decel, bl), 0.0));
        }
    }
}
