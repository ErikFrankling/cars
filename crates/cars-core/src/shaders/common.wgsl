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
const F_SHADOW: u32 = 16384u;      // the old-lane image of a vehicle in a lane change, not a vehicle
const F_HAS_SHADOW: u32 = 32768u;
const F_LAT_FAST: u32 = 65536u;    // this lane change runs at the raised lateral speed
const F_DENIED: u32 = 131072u;     // held at a junction lane in the last step: not coming for now
const F_GRANTED: u32 = 262144u;    // won a junction lane in the last step, and goes on holding it

// Link flags.
const L_CONT: u32 = 1u;
const L_HAS_FOES: u32 = 2u;
const L_KEEP_CLEAR: u32 = 4u;
const L_HAS_VIA: u32 = 8u;
const L_FROM_INTERNAL: u32 = 16u;
const L_EXIT_AFTER_IJ: u32 = 32u;
const L_INTERNAL_JUNCTION: u32 = 64u;
const L_WATCHED: u32 = 1u << 16u;  // some other link yields to this one

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
    mu: f32,
    shadow_reserve: u32,
    detect_every: u32,
    grid_mask: u32,
    trace_len: u32,
    safety: u32,
    width_margin: f32,
    claim_scale: f32,
    queue_speed: f32,
    lost_after: f32,
    zones_ahead: u32,
    pad_b: f32,
    pad_c: f32,
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
    phys: u32,
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
    gz: f32,
    curve_v: f32,
    sqrt_r: f32,
    s_curve: f32,
    s_curve_end: f32,
    width: f32,
    zone_start: u32,
    zone_count: u32,
    shape_count: u32,
    from_node: u32,
    to_node: u32,
    geom_scale: f32,
}

struct Zone {
    foe_lane: u32,
    own_in: f32,
    own_out: f32,
    foe_in: f32,
    foe_out: f32,
    dist: f32,
}

struct Mirror {
    pos: f32,
    speed: f32,
    acc: f32,
    state: u32,
}

struct TripEnergy {
    wheel: f32,
    brake: f32,
    road: f32,
    pe: f32,
    ke: f32,
    idle_s: f32,
    moving_s: f32,
    dist: f32,
}

struct Contact {
    step: u32,
    trip_a: u32,
    trip_b: u32,
    lane_a: u32,
    lane_b: u32,
    kind: u32,
    depth: f32,
    pos_a: f32,
    pos_b: f32,
    x: f32,
    y: f32,
    pad: f32,
}

struct Pose {
    center: vec2f,
    dir: vec2f,
    half_len: f32,
    half_width: f32,
    cell: u32,
    pad: u32,
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
    tc: f32,
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
    exit_comply: f32,
    pw_kg: f32,
    road_a: f32,
    road_c: f32,
    i_inv: f32,
    trac: f32,
    v_corner: f32,
    b_lo: f32,
    b_hi: f32,
    t_r: f32,
    a0: f32,
    a1: f32,
    a_floor: f32,
    v_lat: f32,
    width: f32,
    ph_tau: f32,
    m_ref: f32,
    b_assume: f32,
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
    phys: u32,
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
    grant: u32,       // physical mode: 0 no claim needed, 1 denied, else the bid
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

// Per-vehicle context, set up at the top of a kernel.
var<private> ty: VType;
var<private> dt: f32;
var<private> ego_flags: u32;
var<private> ego_acc: f32;
var<private> mode_done: bool;

// Physical mode. mu 0 selects SUMO's formulas everywhere below.
const G_ACC: f32 = 9.81;
const STOP_NOW: f32 = -0.001;     // a safe speed of zero or less: brake as hard as possible
var<private> mu: f32;
var<private> cert_on: bool;
var<private> ph_gz: f32;
var<private> ph_gz_lead: f32;
var<private> ph_load: f32;
var<private> ph_power: f32;
var<private> ph_curved: f32;

fn ph_force(u: f32) -> f32 {
    return ty.i_inv * (min(ty.pw_kg * ph_power / (ph_load * max(u, ty.v_corner)), mu * ty.trac) - ty.road_a - ty.road_c * u * u / ph_load) - ph_gz;
}

// What the vehicle can do at speed v over this step: evaluated at the middle, so dt does not matter.
fn ph_a_cap(v: f32) -> f32 {
    return ph_force(v + 0.5 * max(ph_force(v), 0.0) * dt);
}

// What the driver asks for.
fn ph_a_drv(v: f32) -> f32 {
    return min(max(ty.a0 - ty.a1 * v, ty.a_floor) - ph_gz, ph_a_cap(v));
}

fn ph_b_follower() -> f32 {
    return max((min(ty.b_lo, mu * G_ACC) + ph_gz) * ph_curved, 0.05);
}

fn ph_b_leader(b_hi: f32) -> f32 {
    return max(min(b_hi, 1.35 * mu * G_ACC) + max(ph_gz, ph_gz_lead), 0.05);
}

fn ph_jerk(b: f32) -> f32 {
    if (dt >= ty.t_r) { return b / ty.t_r; }
    return b / (ty.t_r + dt);
}

// The certificate. Whatever the leader does within its limits, a follower that takes this speed now
// can still stop behind it. bl <= 0 means a fixed stop line.
fn ph_v_cert(gap_bumper: f32, v: f32, vl: f32, b_hi: f32, a_prev: f32) -> f32 {
    let bf = ph_b_follower();
    var bl = bf;
    var along = 0.0;
    if (b_hi > 0.0) {
        bl = ph_b_leader(b_hi);
        along = vl * vl / (2.0 * bl);
    }
    let b = min(bf, bl);
    let d_lo = max(0.0, -a_prev - ph_jerk(b) * dt);
    let lam = max(0.0, 1.0 - d_lo / b);
    let h = (ty.t_r * lam * lam + dt) * 0.5;
    let q = gap_bumper - 0.5 + along - v * dt * 0.5;
    return b * (-h + sqrt(h * h + 2.0 * max(q, 0.0) / b));
}

// Bumper gap the certificate needs for a vehicle to keep speed v behind one at vl.
fn ph_gap_required(v: f32, vl: f32, b_hi: f32, a_prev: f32) -> f32 {
    let bl = ph_b_leader(b_hi);
    let b = min(ph_b_follower(), bl);
    let d_lo = max(0.0, -a_prev - ph_jerk(b) * dt);
    let lam = max(0.0, 1.0 - d_lo / b);
    let h = (ty.t_r * lam * lam + dt) * 0.5;
    return 0.5 + v * v / (2.0 * b) + h * v + v * dt * 0.5 - vl * vl / (2.0 * bl);
}

// The highest speed a new vehicle may enter at, which is ph_gap_required solved for v.
fn ph_v_insert(gap_bumper: f32, vl: f32, b_hi: f32) -> f32 {
    let bf = ph_b_follower();
    var bl = bf;
    var along = 0.0;
    if (b_hi > 0.0) {
        bl = ph_b_leader(b_hi);
        along = vl * vl / (2.0 * bl);
    }
    let b = min(bf, bl);
    let h = (ty.t_r + 2.0 * dt) * 0.5;
    return b * (-h + sqrt(h * h + 2.0 * max(gap_bumper - 0.5 + along, 0.0) / b));
}

fn ph_limit(driver: f32, cert: f32) -> f32 {
    if (!cert_on) { return max(driver, 0.0); }
    if (cert <= 0.0) { return STOP_NOW; }
    return min(max(driver, 0.0), cert);
}

// MSCFModel::maximumSafeStopSpeedBallistic.
fn ph_stop_driver(gap_total: f32, v: f32, b: f32, tau: f32) -> f32 {
    if (gap_total <= 0.0) { return 0.0; }
    // At dt above the reaction time the law alone runs past the gap in a step and stops short of nothing.
    // What is driven this step, and what stopping takes in the next, have to fit in the gap.
    let fits = max(gap_total - v * dt * 0.5, 0.0) / dt;
    if (gap_total <= v * tau * 0.5) { return min(fits, max(0.0, v - v * v / (2.0 * gap_total) * dt)); }
    let bt = b * tau * 0.5;
    let v1 = -bt + sqrt(bt * bt + b * (2.0 * gap_total - tau * v));
    return min(fits, max(0.0, v + (v1 - v) * min(dt / tau, 1.0)));
}

// The hardest the brakes allow by the end of this step. Below zero, the stop is inside the step.
fn ph_floor(v: f32, a_prev: f32) -> f32 {
    let b = ph_b_follower();
    let d = max(0.0, -a_prev);
    if (dt >= ty.t_r) {
        let t1 = max(b - d, 0.0) * ty.t_r / b;
        return v - (d * t1 + 0.5 * (b / ty.t_r) * t1 * t1 + b * (dt - t1));
    }
    return v - min(b, d + b * dt / (ty.t_r + dt)) * dt;
}

// How far hard braking from here takes to stop.
fn ph_stop_distance(v: f32, a_prev: f32) -> f32 {
    let f = ph_floor(v, a_prev);
    if (f <= 0.0) { return v * v * dt / (2.0 * max(v - f, 1e-3)); }
    return 0.5 * (v + f) * dt + f * f / (2.0 * ph_b_follower());
}

fn ph_release(v: f32, a_prev: f32) -> f32 {
    if (a_prev >= 0.0) { return 1e9; }
    return v + (a_prev + ph_jerk(ph_b_follower()) * dt) * dt;
}

// Whatever brakes hardest among tails we know nothing else about.
fn tail_b() -> f32 {
    if (mu > 0.0) { return 1.35 * mu * G_ACC; }
    return ty.apparent;
}

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
    if (mu > 0.0) { return max(0.0, min(v + ph_a_drv(v) * dt, ty.max_speed)); }
    return min(v + ty.accel * dt, ty.max_speed);
}

fn min_next_speed(v: f32) -> f32 {
    var d = ty.decel;
    if (ty.model == MODEL_IDM) { d = max(ty.decel, min(ty.emergency, 1.5)); }
    return max(v - d * dt, 0.0);
}

fn min_next_speed_emergency(v: f32) -> f32 {
    if (mu > 0.0) { return max(ph_floor(v, ego_acc), 0.0); }
    return max(v - ty.emergency * dt, 0.0);
}

fn brake_gap(v: f32, decel: f32, headway: f32) -> f32 {
    if (mu > 0.0) { return v * v / (2.0 * decel) + v * headway; }
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
    if (mu > 0.0) { return ph_stop_driver(gap, v, decel, select(dt, ty.ph_tau, headway > 0.0)); }
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
    if (mu > 0.0) { return ph_stop_driver(max(gap, 0.0) + vp * vp / (2.0 * ty.b_assume), v, ty.decel, ty.ph_tau); }
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

// CF::followSpeed. `lane_vmax` is the lane's limit for this vehicle, `lane_limit` the posted limit.
// Physical mode keeps the model as the driver's wish and bounds it by the certificate, so any model
// can sit here: nothing past this point depends on which one asked.
fn follow_speed(v: f32, gap: f32, vp: f32, bp: f32, leader_cacc: bool, lane_vmax: f32, lane_limit: f32) -> f32 {
    if (mu > 0.0) {
        return ph_limit(follow_driver(v, gap, vp, bp, leader_cacc, lane_vmax, lane_limit), ph_v_cert(gap + ty.min_gap, v, vp, bp, ego_acc));
    }
    return follow_driver(v, gap, vp, bp, leader_cacc, lane_vmax, lane_limit);
}

fn follow_driver(v: f32, gap: f32, vp: f32, bp: f32, leader_cacc: bool, lane_vmax: f32, lane_limit: f32) -> f32 {
    switch ty.model {
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
    if (mu > 0.0) {
        var d = min(ph_stop_driver(gap, v, decel, ty.ph_tau), max_next_speed(v));
        if (ty.model == MODEL_IDM) { d = min(d, stop_driver_idm(v, gap, decel, lane_vmax)); }
        return ph_limit(d, ph_v_cert(gap, v, 0.0, 0.0, ego_acc));
    }
    return stop_driver(v, gap, decel, relax, lane_vmax);
}

fn stop_driver_idm(v: f32, gap: f32, decel: f32, lane_vmax: f32) -> f32 {
    if (gap < 0.01) { return 0.0; }
    return min(idm_v(gap, v, 0.0, lane_vmax, false), gap / dt);
}

fn stop_driver(v: f32, gap: f32, decel: f32, relax: bool, lane_vmax: f32) -> f32 {
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
    if (mu > 0.0) {
        var v = min(speed, ph_v_insert(gap + ty.min_gap, vp, bp));
        if (ty.model != MODEL_KRAUSS) { v = min(v, insertion_driver(speed, gap, vp, bp, vmax, leader_cacc)); }
        return max(v, 0.0);
    }
    return insertion_driver(speed, gap, vp, bp, vmax, leader_cacc);
}

fn insertion_driver(speed: f32, gap: f32, vp: f32, bp: f32, vmax: f32, leader_cacc: bool) -> f32 {
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
        default: { return safe_follow(gap, speed, vp, bp, true); }
    }
}

// CF::insertionStopSpeed
fn insertion_stop(speed: f32, gap: f32, vmax: f32) -> f32 {
    if (mu > 0.0) { return min(speed, ph_v_insert(gap, 0.0, 0.0)); }
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
    if (mu > 0.0) {
        let bh = ty.decel * dt * 0.5;
        return max(vt, -bh + sqrt(bh * bh + vt * vt + 2.0 * ty.decel * max(seen - v * dt * 0.5, 0.0)));
    }
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
    if (mu > 0.0) { return max(0.0, ph_gap_required(v, vl, bl, 0.0) - ty.min_gap); }
    switch ty.model {
        case MODEL_IDM: { return idm_secure_gap(v, vl); }
        case MODEL_ACC: { return 0.07 * (v - vl) / 0.23 + ty.tau * v; }
        default: {
            return max(0.0, brake_gap(v, ty.decel, ty.tau) - brake_gap(vl, max(ty.decel, bl), 0.0));
        }
    }
}
