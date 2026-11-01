// Signal-free junctions: earliest-start scheduling on conflict pairs. research/truth/09, build spec.
// Stages, each a separate dispatch: clear, pre (crossings and the box table), audit, snapshot, propose,
// arbitrate, commit, perceive, apply. A junction writes only its own lanes and the vehicles on them;
// a vehicle only its own record, plus atomic counters. Nothing else may be assumed collision free.

@group(0) @binding(0) var<uniform> P: Params;
@group(0) @binding(1) var<storage, read_write> G: Globals;
@group(0) @binding(3) var<storage, read> lanes: array<Lane>;
@group(0) @binding(5) var<storage, read> links: array<Link>;
@group(0) @binding(8) var<storage, read> types: array<VType>;
@group(0) @binding(9) var<storage, read> routes: array<u32>;
@group(0) @binding(16) var<storage, read_write> cur: array<Veh>;
@group(0) @binding(20) var<storage, read_write> seg: array<LaneSeg>;

@group(1) @binding(0) var<uniform> cfg: CjCfg;
@group(1) @binding(1) var<storage, read_write> cj_junctions: array<CjJunction>;
@group(1) @binding(2) var<storage, read> cj_links: array<CjLink>;
@group(1) @binding(3) var<storage, read> cj_conflicts: array<CjConflict>;
@group(1) @binding(4) var<storage, read> cj_times: array<f32>;
@group(1) @binding(5) var<storage, read> cj_pairs: array<CjPair>;
@group(1) @binding(6) var<storage, read> cj_head: array<f32>;
@group(1) @binding(7) var<storage, read> cj_mov_k: array<CjMovK>;
@group(1) @binding(8) var<storage, read_write> cj_rel: array<f32>;
@group(1) @binding(9) var<storage, read_write> cj_rel_s: array<f32>;
@group(1) @binding(10) var<storage, read_write> cj_apps: array<CjApp>;
@group(1) @binding(11) var<storage, read_write> cj_exits: array<CjExit>;
@group(1) @binding(12) var<storage, read_write> cj_req: array<CjReq>;
@group(1) @binding(13) var<storage, read_write> cj_plan: array<u32>;
@group(1) @binding(14) var<storage, read_write> cj_box: array<CjBox>;
@group(1) @binding(15) var<storage, read> cj_lane_info: array<CjLaneInfo>;
@group(1) @binding(16) var<storage, read_write> cj_stats: array<atomic<u32>>;
@group(1) @binding(17) var<storage, read_write> cj_events: array<atomic<u32>>;
@group(1) @binding(18) var<storage, read> cj_path: array<vec2f>;
@group(1) @binding(19) var<storage, read_write> cj_aud: array<CjAud>;
@group(1) @binding(20) var<storage, read_write> cj_rel_ms: array<u32>;

const K_LANE: u32 = 6u;
const K_BOX: u32 = 16u;
const N_CLASS: u32 = 6u;
const PLAN_MAX: u32 = 32u;
const AUD_MAX: u32 = 32u;
const STATS_PER_REPLICA: u32 = 64u;
const EVENTS_MAX: u32 = 4095u;
const INF: f32 = 1e30;
const HEARD_NOTHING: f32 = 20.0;
const FOE_DWELL: f32 = 3.0;

const S_LOSS: u32 = 0u;
const S_STOPS: u32 = 1u;
const S_BOX_BLOCK: u32 = 2u;
const S_CROSS_UNGRANTED: u32 = 3u;
const S_STOP_CURVE: u32 = 4u;
const S_GRANTS: u32 = 5u;
const S_ABORTS: u32 = 6u;
const S_LATE: u32 = 7u;
const S_LATE_COMMITTED: u32 = 8u;
const S_PONR_ABORT: u32 = 9u;
const S_OVERLAP_STEPS: u32 = 10u;
const S_MSG_SENT: u32 = 11u;
const S_MSG_LOST: u32 = 12u;
const S_A2: u32 = 13u;
const S_A2N: u32 = 14u;
const S_NEG_CREDIT: u32 = 15u;
const S_STALLS: u32 = 16u;
const S_ERR_ABS: u32 = 17u;
const S_ERR_N: u32 = 18u;
const S_ERR_BIG: u32 = 19u;
const S_AUD_OVERFLOW: u32 = 20u;
const S_BOX_OVERFLOW: u32 = 21u;
const S_ADVISED_STEPS: u32 = 22u;
const S_FIRM_STEPS: u32 = 23u;
const S_STALL_BOX: u32 = 24u;
const S_YIELDS: u32 = 25u;
const S_HOLDS: u32 = 26u;
const S_SPEED_LOST: u32 = 27u;
const S_KE_LOST: u32 = 28u;
const S_HARD_STOP_CURVE: u32 = 29u;
const S_HARD_LEADER: u32 = 30u;
const S_HARD_YIELD: u32 = 31u;
const S_HARD_HOLD: u32 = 32u;
const S_HARD_PLAN: u32 = 33u;
const S_HARD_STALL: u32 = 34u;
const S_MOVED_LATER: u32 = 35u;
const S_MOVED_EARLIER: u32 = 36u;
const S_SLOTS_FULL: u32 = 38u;
const S_EXIT_REFUSED: u32 = 39u;
const S_BYTES_UP: u32 = 40u;
const S_BYTES_DOWN: u32 = 41u;
const S_ERR_HIST: u32 = 42u;
const PLAN_PROFILE: u32 = 1u;
const PLAN_STABLE: u32 = 2u;
const PLAN_FOLLOW: u32 = 4u;
const PLAN_CUBIC: u32 = 8u;
const PLAN_DR: u32 = 16u;
const PLAN_ROUTE: u32 = 32u;
const MAX_NEW: u32 = 8u;
const INSERT_TRIES: u32 = 12u;

const CAND_STALE: u32 = 0u;
const CAND_OK: u32 = 1u;
const CAND_NONE: u32 = 2u;

var<private> now: f32;
var<private> cand_t: f32;
var<private> cand_k: u32;
var<private> now_ms: u32;

fn ms_rel(x: u32) -> f32 { return f32(i32(x - now_ms)) * 0.001; }
fn rel_ms(t: f32) -> u32 { return now_ms + u32(i32(round(t * 1000.0))); }
fn plan_route() -> bool { return (cfg.plan & PLAN_ROUTE) != 0u; }
fn plan_on() -> bool { return (cfg.plan & PLAN_STABLE) != 0u; }
fn plan_here(j: u32) -> bool { return plan_on() && cj_junctions[j].fallback == 0u; }

// A unit normal per car and purpose, fixed for the whole trip.
fn car_normal(trip: u32, c: u32) -> f32 {
    return (hash01(trip, c, 20u) + hash01(trip, c, 21u) + hash01(trip, c, 22u) + hash01(trip, c, 23u) - 2.0) * 1.732;
}

fn stat(replica: u32, which: u32, n: u32) {
    atomicAdd(&cj_stats[replica * STATS_PER_REPLICA + which], n);
}

// ---------------------------------------------------------------- kinematics, closed form

// -1 when the car cannot reach or brake to ve in d.
fn earliest(d: f32, v: f32, ve: f32, vmax: f32, a: f32, b: f32) -> f32 {
    if (v <= ve) {
        if ((ve * ve - v * v) / (2.0 * a) > d + 1e-3) { return -1.0; }
    } else if ((v * v - ve * ve) / (2.0 * b) > d + 1e-3) {
        return -1.0;
    }
    let vp = sqrt(max((2.0 * a * b * d + b * v * v + a * ve * ve) / (a + b), 0.0));
    if (vp <= vmax) {
        return max(vp - v, 0.0) / a + max(vp - ve, 0.0) / b;
    }
    return (vmax - v) / a + (vmax - ve) / b + (d - (vmax * vmax - v * v) / (2.0 * a) - (vmax * vmax - ve * ve) / (2.0 * b)) / vmax;
}

// -1 when the car cannot make it at all, INF when it can stop and wait.
fn latest(d: f32, v: f32, ve: f32, a: f32, b: f32) -> f32 {
    let c = d - v * v / (2.0 * b) - ve * ve / (2.0 * a);
    if (c >= 0.0) { return INF; }
    let vc = sqrt(-c / (1.0 / (2.0 * b) + 1.0 / (2.0 * a)));
    if (vc > min(v, ve) + 1e-3) { return -1.0; }
    return (v - vc) / b + (ve - vc) / a;
}

// Cruise speed that arrives at the line at time T with speed ve.
fn plan_vc(v: f32, d: f32, t: f32, ve: f32, vcap: f32) -> f32 {
    return plan_vc_b(v, d, t, ve, vcap, cfg.b_plan);
}

fn plan_vc_b(v: f32, d: f32, t: f32, ve: f32, vcap: f32, b: f32) -> f32 {
    return plan_vc_ab(v, d, t, ve, vcap, cfg.accel, b);
}

fn plan_vc_ab(v: f32, d: f32, t: f32, ve: f32, vcap: f32, a: f32, b: f32) -> f32 {
    var lo = 0.02;
    var hi = max(vcap, 1.0);
    for (var it = 0u; it < 12u; it++) {
        let vc = 0.5 * (lo + hi);
        let r1 = select(b, a, vc > v);
        let r3 = select(b, a, ve > vc);
        let d1 = abs(vc * vc - v * v) / (2.0 * r1);
        let d3 = abs(ve * ve - vc * vc) / (2.0 * r3);
        let rem = d - d1 - d3;
        let time = abs(vc - v) / r1 + abs(ve - vc) / r3 + rem / vc;
        var slow = false;
        if (rem >= 0.0) { slow = time > t; } else { slow = vc < max(v, ve); }
        if (slow) { lo = vc; } else { hi = vc; }
    }
    return 0.5 * (lo + hi);
}

// ---------------------------------------------------------------- channel, stateless by hash

fn hash01(a: u32, b: u32, c: u32) -> f32 {
    let h = pcg(a * 2654435761u ^ pcg(b * 40503u ^ pcg(c + 0x9e3779b9u)));
    return f32(h >> 8u) * (1.0 / 16777216.0);
}

fn radio_up() -> bool { return !(now >= cfg.blackout_t0 && now < cfg.blackout_t1); }

fn coordinator_up() -> bool { return !(now >= cfg.crash_t0 && now < cfg.crash_t1); }

// Did a message between this car and the coordinator get through? p_load comes from channel load.
fn delivered(trip: u32, kind: u32, d: f32, p_load: f32, replica: u32) -> bool {
    stat(replica, S_MSG_SENT, 1u);
    var ok = radio_up();
    if (ok) {
        var p = cfg.p_loss;
        if (cfg.chan == 1u) {
            // Report 08: range cliff of width 15% of R50 with a shadow offset per link, floor, bursts, load.
            let z = hash01(trip, 7u, 0u) + hash01(trip, 8u, 0u) - 1.0;
            let dd = max(d, 0.0) * exp(0.46 * z);
            let width = 0.15 * cfg.r50;
            let pr = clamp((dd - (cfg.r50 - 0.5 * width)) / width, 0.0, 1.0);
            let pf = select(0.0, cfg.p_floor, dd > 250.0);
            p = 1.0 - (1.0 - p) * (1.0 - pr) * (1.0 - pf) * (1.0 - p_load);
            let bucket = u32(now / cfg.burst_len);
            if (hash01(trip, bucket, 3u) < cfg.burst_len / cfg.burst_every) { ok = false; }
        }
        if (p > 0.0 && hash01(trip, G.step, kind) < p) { ok = false; }
    }
    if (!ok) { stat(replica, S_MSG_LOST, 1u); }
    return ok;
}

// Fixed-rate channel with no loss at all, where a grant needs no retry.
fn lossless() -> bool { return cfg.p_loss <= 0.0 && cfg.blackout_t0 > 1e29 && cfg.chan == 0u; }

fn is_tick(j: u32) -> bool { return G.step % cfg.tick_steps == cj_junctions[j].tick_phase; }

// ---------------------------------------------------------------- stage 0: per step clears

@compute @workgroup_size(64)
fn cj_clear_exits(@builtin(global_invocation_id) id: vec3u) {
    if (id.x >= cfg.n_exits) { return; }
    atomicStore(&cj_exits[id.x].n_box, 0u);
}

@compute @workgroup_size(64)
fn cj_clear_apps(@builtin(global_invocation_id) id: vec3u) {
    if (id.x >= cfg.n_apps) { return; }
    atomicStore(&cj_apps[id.x].box_tail, NONE);
    atomicStore(&cj_apps[id.x].box_tail_m, NONE);
}

// ---------------------------------------------------------------- crossings and the box table

fn pack_box(s: f32, v: f32) -> u32 {
    return (u32(clamp(s + 500.0, 0.0, 7500.0) * 8.0) << 16u) | u32(clamp(v, 0.0, 127.0) * 256.0);
}

fn abort_grant(i: u32, mi: u32, replica: u32) {
    let x = cj_links[mi].to_lane;
    atomicSub(&cj_exits[x].n_committed, 1u);
    if ((cur[i].cj_state & CJ_ARMED) != 0u) { atomicSub(&cj_exits[x].n_armed, 1u); }
    cur[i].cj_state = (cur[i].cj_state & CJ_KEEP) | CJ_NONE;
    stat(replica, S_ABORTS, 1u);
}

@compute @workgroup_size(64)
fn cj_pre(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let e = cur[i];
    if ((e.flags & F_REMOVED) != 0u || e.lane == P.dummy_lane) { return; }
    if (types[e.vtype].model != MODEL_AV) { return; }
    now = f32(G.step) * P.dt;
    let info = cj_lane_info[e.lane];
    let state = e.cj_state & CJ_STATE_MASK;
    if (info.box_mov != NONE) {
        let mi = info.box_mov;
        let m = cj_links[mi];
        let x = m.to_lane;
        let s = info.s_offset + e.pos;
        var st = e.cj_state;
        if (state != CJ_BOX) {
            if (state != CJ_FIRM) { stat(e.replica, S_CROSS_UNGRANTED, 1u); }
            if (state == CJ_FIRM || state == CJ_PENDING) {
                atomicSub(&cj_exits[x].n_committed, 1u);
                if ((e.cj_state & CJ_ARMED) != 0u) { atomicSub(&cj_exits[x].n_armed, 1u); }
                // The line was crossed inside the last step: solve the ballistic update for when.
                let vb = max(e.speed, 0.0);
                let ab = e.acc;
                var since = s / max(vb, 0.1);
                if (abs(ab) > 1e-3) { since = (vb - sqrt(max(vb * vb - 2.0 * ab * s, 0.0))) / ab; }
                now_ms = G.step * cfg.dt_ms;
                let err = select(now - e.cj_t_line, -ms_rel(e.cj_t_ms), plan_on()) - since;
                if (now >= cfg.warm) {
                    stat(e.replica, S_ERR_ABS, u32(abs(err) * 1000.0));
                    stat(e.replica, S_ERR_N, 1u);
                    if (abs(err) > 0.15) { stat(e.replica, S_ERR_BIG, 1u); }
                    let ae = abs(err) * 1000.0;
                    var bin = 9u;
                    if (ae < 1.0) { bin = 0u; } else if (ae < 2.0) { bin = 1u; } else if (ae < 5.0) { bin = 2u; } else if (ae < 10.0) { bin = 3u; } else if (ae < 20.0) { bin = 4u; } else if (ae < 50.0) { bin = 5u; } else if (ae < 100.0) { bin = 6u; } else if (ae < 200.0) { bin = 7u; } else if (ae < 500.0) { bin = 8u; }
                    stat(e.replica, S_ERR_HIST + bin, 1u);
                }
            }
            st = (e.cj_state & CJ_KEEP) | CJ_BOX;
            cur[i].cj_state = st;
            cur[i].cj_link = mi;
            // A stalled record keeps its end time in cj_t_line.
        }
        atomicAdd(&cj_exits[x].n_box, 1u);
        atomicMin(&cj_apps[m.from_lane].box_tail, pack_box(s - cfg.length, e.speed));
        atomicMin(&cj_apps[m.from_lane].box_tail_m, (pack_box(s - cfg.length, 0.0) & 0xffff0000u) | (cj_lane_info[e.lane].box_mov & 0xffffu));
        let slot = x * K_BOX + e.cj_seq % K_BOX;
        var b: CjBox;
        b.veh = i;
        b.seq = e.cj_seq;
        b.stamp = G.step + 1u;
        b.mov = mi;
        b.s = s;
        b.v = e.speed;
        b.trip = e.trip;
        cj_box[slot] = b;
        return;
    }
    if (state == CJ_BOX) {
        var st = e.cj_state & CJ_KEEP;
        cur[i].cj_state = st;
        cur[i].cj_rank = NONE;
        cur[i].cj_link = NONE;
        cur[i].cj_zone_t = now;
    } else if (!cj_controlled(e)) {
        cur[i].cj_zone_t = now;
    }
    // A tail still hanging back through a short box, over the stop line of the lane it came from.
    if (e.pos < cfg.length && e.prev_lane != NONE && cj_lane_info[e.prev_lane].box_mov != NONE) {
        let m = cj_links[cj_lane_info[e.prev_lane].box_mov];
        atomicMin(&cj_apps[m.from_lane].box_tail, pack_box(m.path_len + e.pos - cfg.length, e.speed));
    }
}

// ---------------------------------------------------------------- auditor, independent of the planner

fn path_at(mi: u32, s: f32) -> vec2f {
    let m = cj_links[mi];
    let n = m.path_n;
    let start = m.path_start;
    let spacing = m.path_len / f32(n - 1u);
    // Beyond either end the body lies along the lane it is on, not along the curve's first chord.
    if (s <= 0.0) { return cj_path[start] + m.dir_in * s; }
    if (s >= m.path_len) { return cj_path[start + n - 1u] + m.dir_out * (s - m.path_len); }
    let t = s / spacing;
    let k = min(u32(t), n - 2u);
    let a = cj_path[start + k];
    let b = cj_path[start + k + 1u];
    return a + (b - a) * (t - f32(k));
}

fn aud_add(j: u32, mi: u32, s: f32, trip: u32, v: f32) {
    let at = cj_junctions[j].aud_n;
    if (at >= AUD_MAX) {
        stat(cj_junctions[j].replica, S_AUD_OVERFLOW, 1u);
        return;
    }
    var a: CjAud;
    a.f = path_at(mi, s);
    a.r = path_at(mi, s - cfg.length);
    a.trip = trip;
    a.mov = mi;
    a.s = s;
    a.v = v;
    cj_aud[cj_junctions[j].aud_start + at] = a;
    cj_junctions[j].aud_n = at + 1u;
}

fn rects_overlap(a: CjAud, b: CjAud) -> bool {
    let ca = 0.5 * (a.f + a.r);
    let cb = 0.5 * (b.f + b.r);
    let la = 0.5 * length(a.f - a.r);
    let lb = 0.5 * length(b.f - b.r);
    let ua = (a.f - a.r) / max(2.0 * la, 1e-6);
    let ub = (b.f - b.r) / max(2.0 * lb, 1e-6);
    let na = vec2f(-ua.y, ua.x);
    let nb = vec2f(-ub.y, ub.x);
    let w = 0.5 * cfg.width;
    let d = ca - cb;
    let ra1 = la + lb * abs(dot(ub, ua)) + w * abs(dot(nb, ua));
    if (abs(dot(d, ua)) >= ra1) { return false; }
    let ra2 = w + lb * abs(dot(ub, na)) + w * abs(dot(nb, na));
    if (abs(dot(d, na)) >= ra2) { return false; }
    let rb1 = lb + la * abs(dot(ua, ub)) + w * abs(dot(na, ub));
    if (abs(dot(d, ub)) >= rb1) { return false; }
    let rb2 = w + la * abs(dot(ua, nb)) + w * abs(dot(na, nb));
    if (abs(dot(d, nb)) >= rb2) { return false; }
    return true;
}

@compute @workgroup_size(16)
fn cj_audit(@builtin(global_invocation_id) id: vec3u) {
    let j = id.x;
    if (j >= cfg.n_junctions) { return; }
    let J = cj_junctions[j];
    cj_junctions[j].aud_n = 0u;
    // Every body at or inside the box: those inside, those with a tail still in it, those at the line.
    for (var xi = J.exit_start; xi < J.exit_start + J.exit_count; xi++) {
        var listed = 0u;
        for (var k = 0u; k < K_BOX; k++) {
            let b = cj_box[xi * K_BOX + k];
            if (b.stamp == G.step + 1u) {
                aud_add(j, b.mov, b.s, b.trip, b.v);
                listed += 1u;
            }
        }
        // More cars in this box than the table shows: one was overwritten, and is hidden from followers.
        if (listed != atomicLoad(&cj_exits[xi].n_box)) { stat(J.replica, S_BOX_OVERFLOW, 1u); }
        let sim = cj_exits[xi].sim_lane;
        if (seg[sim].stamp == G.step) {
            let last = min(seg[sim].first + 3u, seg[sim].end);
            for (var q = seg[sim].first; q < last; q++) {
                let e = cur[q];
                if ((e.flags & F_REMOVED) != 0u || e.pos > cfg.length + 1.0 || e.prev_lane == NONE) { continue; }
                let mi = cj_lane_info[e.prev_lane].box_mov;
                if (mi != NONE && cj_links[mi].to_lane == xi) {
                    aud_add(j, mi, cj_links[mi].path_len + e.pos, e.trip, e.speed);
                }
            }
        }
    }
    for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
        let sim = cj_apps[a].sim_lane;
        if (seg[sim].stamp != G.step) { continue; }
        let e = cur[seg[sim].end - 1u];
        let d = cj_apps[a].length - e.pos;
        if ((e.flags & F_REMOVED) == 0u && d < 3.0 && e.cj_link != NONE && e.lane == sim) {
            aud_add(j, e.cj_link, -d, e.trip, e.speed);
        }
    }
    let n = cj_junctions[j].aud_n;
    let start = cj_junctions[j].aud_start;
    for (var p = 0u; p < n; p++) {
        let a = cj_aud[start + p];
        for (var q = p + 1u; q < n; q++) {
            let b = cj_aud[start + q];
            if (a.trip != b.trip && rects_overlap(a, b)) {
                stat(J.replica, S_OVERLAP_STEPS, 1u);
                let at = atomicAdd(&cj_events[0], 1u);
                if (at < EVENTS_MAX) {
                    let w = (at + 1u) * 8u;
                    atomicStore(&cj_events[w], G.step);
                    atomicStore(&cj_events[w + 1u], a.trip);
                    atomicStore(&cj_events[w + 2u], b.trip);
                    atomicStore(&cj_events[w + 3u], j);
                    atomicStore(&cj_events[w + 4u], a.mov);
                    atomicStore(&cj_events[w + 5u], b.mov);
                    atomicStore(&cj_events[w + 6u], bitcast<u32>(a.s));
                    atomicStore(&cj_events[w + 7u], bitcast<u32>(b.s));
                }
            }
        }
    }
}

// ---------------------------------------------------------------- stage 0 and 1: snapshot, propose

@compute @workgroup_size(64)
fn cj_snapshot(@builtin(global_invocation_id) id: vec3u) {
    let xi = id.x;
    if (xi >= cfg.n_exits) { return; }
    let j = cj_exits[xi].junction;
    if (!is_tick(j)) { return; }
    let sim = cj_exits[xi].sim_lane;
    let on_lane = select(0u, seg[sim].end - seg[sim].first, seg[sim].stamp == G.step);
    cj_exits[xi].n_on_lane = on_lane + atomicLoad(&cj_exits[xi].n_box);
    if (atomicLoad(&cj_exits[xi].n_committed) > 0x7fffffffu) { stat(cj_junctions[j].replica, S_NEG_CREDIT, 1u); }
    // The tail of the lane's order: the newest car still in the box, or else the last one past it.
    var best_seq = 0u;
    var has = false;
    var tx = 0.0;
    var tv = 0.0;
    var ta = 0.0;
    for (var k = 0u; k < K_BOX; k++) {
        let b = cj_box[xi * K_BOX + k];
        if (b.stamp == G.step + 1u && (!has || b.seq > best_seq)) {
            has = true;
            best_seq = b.seq;
            tx = b.s - cj_links[b.mov].path_len;
            tv = b.v;
        }
    }
    if (!has && on_lane > 0u) {
        let e = cur[seg[sim].first];
        has = true;
        tx = e.pos;
        tv = e.speed;
        ta = e.acc;
    }
    cj_exits[xi].tail_a = ta;
    cj_exits[xi].has_tail = u32(has);
    cj_exits[xi].tail_x = tx;
    cj_exits[xi].tail_v = tv;
}

@compute @workgroup_size(64)
fn cj_propose(@builtin(global_invocation_id) id: vec3u) {
    let a = id.x;
    if (a >= cfg.n_apps) { return; }
    let j = cj_apps[a].junction;
    if (!is_tick(j)) { return; }
    let sim = cj_apps[a].sim_lane;
    var n = 0u;
    var n_exp = 0u;
    var n_rx = 0u;
    if (seg[sim].stamp == G.step) {
        let first = seg[sim].first;
        let len = cj_apps[a].length;
        var idx = seg[sim].end;
        loop {
            if (idx <= first || n >= cfg.k_lane) { break; }
            idx -= 1u;
            let e = cur[idx];
            if ((e.flags & F_REMOVED) != 0u) { continue; }
            let state = e.cj_state & CJ_STATE_MASK;
            // Nothing goes firm behind a car whose own grant is unconfirmed.
            if (state == CJ_PENDING) { break; }
            if (state == CJ_FIRM) { continue; }
            ty = types[e.vtype];
            let k = pick_link(sim, e.route_i, e.route_end);
            if (k == NONE) {
                if (e.route_i + 1u >= e.route_end) { continue; }
                break;
            }
            var q: CjReq;
            q.veh = idx;
            q.link = cj_apps[a].mov_start + (k - lanes[sim].links_start);
            q.d = max(len - e.pos, 0.0);
            q.v = e.speed;
            q.age_t = e.cj_zone_t;
            q.trip = e.trip;
            if (plan_on()) {
                // Heard from as far as the radio reaches, one Path Prediction CAM a second.
                now_ms = G.step * cfg.dt_ms;
                now = f32(G.step) * P.dt;
                if (cfg.pos_err > 0.0) { q.d = max(q.d + cfg.pos_err * car_normal(e.trip, 1u), 0.0); }
                let on_turn = ((G.step / cfg.tick_steps) + e.trip) % 2u == 0u;
                // No slot yet after a turn in range means it was not heard: say it again.
                let tick_s = f32(cfg.tick_steps) * P.dt;
                let retry = e.cj_rank == NONE && now - e.cj_zone_t > tick_s + 0.01 && q.d + e.speed * tick_s <= cfg.plan_range;
                var heard = false;
                if ((on_turn || retry) && q.d <= cfg.plan_range) {
                    stat(cj_junctions[j].replica, S_BYTES_UP, 262u);
                    heard = lossless() || delivered(e.trip, 4u, q.d, cj_junctions[j].p_load, cj_junctions[j].replica);
                    // A car on the books that misses its turn is a lost message. Nobody has to know the true rate.
                    if (on_turn && (e.cj_rank != NONE || cj_junctions[j].fallback != 0u)) {
                        n_exp += 1u;
                        if (heard) { n_rx += 1u; }
                    }
                }
                // Not yet heard: not in the schedule, but the fallback for a dead radio still has to see it.
                q.heard = u32(heard || e.cj_rank != NONE);
                q.rank = select(f32(e.cj_rank), INF, e.cj_rank == NONE);
                q.held = select(ms_rel(e.cj_plan_ms), INF, e.cj_rank == NONE);
                if (cj_junctions[j].fallback != 0u) { cur[idx].cj_rank = NONE; }
            }
            cj_req[cj_apps[a].req_start + n] = q;
            n += 1u;
        }
    }
    cj_apps[a].n_req = n;
    cj_apps[a].n_exp = n_exp;
    cj_apps[a].n_rx = n_rx;
    cj_apps[a].s_ptr = 0u;
    cj_apps[a].s_cand_state = CAND_STALE;
    cj_apps[a].s_line_ref = cj_apps[a].line_ref;
    cj_apps[a].s_line_t = cj_apps[a].line_t;
}

// ---------------------------------------------------------------- candidate times

fn headway(mi: u32, k: u32, rf: u32, is_exit: u32) -> f32 {
    let p = rf / N_CLASS;
    let kp = rf % N_CLASS;
    let m = cj_links[mi];
    for (var q = m.pair_start; q < m.pair_start + m.pair_count; q++) {
        let pr = cj_pairs[q];
        if (pr.other == p && pr.is_exit == is_exit) { return cj_head[pr.table + kp * N_CLASS + k]; }
    }
    return 0.0;
}

// Earliest time this car can reach its line without crossing what is already reserved.
fn cand_time(mi: u32, d: f32, v: f32, min_t: f32, kmin: u32, scratch: bool) -> bool {
    let m = cj_links[mi];
    let a = cfg.accel;
    let b = cfg.b_plan;
    var line_ref: u32;
    var line_t: f32;
    var exit_ref: u32;
    var exit_t: f32;
    if (scratch) {
        line_ref = cj_apps[m.from_lane].s_line_ref;
        line_t = cj_apps[m.from_lane].s_line_t;
        exit_ref = cj_exits[m.to_lane].s_exit_ref;
        exit_t = cj_exits[m.to_lane].s_exit_t;
    } else {
        line_ref = cj_apps[m.from_lane].line_ref;
        line_t = cj_apps[m.from_lane].line_t;
        exit_ref = cj_exits[m.to_lane].exit_ref;
        exit_t = cj_exits[m.to_lane].exit_t;
    }
    let has_tail = cj_exits[m.to_lane].has_tail != 0u;
    let vt = cj_exits[m.to_lane].tail_v;
    let tx = cj_exits[m.to_lane].tail_x;
    for (var k = kmin; k < N_CLASS; k++) {
        let mk = cj_mov_k[mi * N_CLASS + k];
        let te = earliest(d, v, mk.vk, m.v_lane, a, b);
        if (te < 0.0) { continue; }
        let tl = latest(d, v, mk.vk, a, b);
        if (tl < 0.0) { continue; }
        var t = max(now + te, min_t);
        if (line_ref != NONE) { t = max(t, line_t + headway(mi, k, line_ref, 0u)); }
        if (exit_ref != NONE) { t = max(t, exit_t + headway(mi, k, exit_ref, 1u)); }
        // The exit tail may slow for its own next junction: be clear of the box behind it at this pace.
        if (has_tail && vt > 0.5) {
            let need = 2.0 * cfg.length + cfg.s0 + mk.vout * cfg.tau - tx;
            if (need > 0.0) { t = max(t, now + need / vt - mk.t_clear); }
        }
        var margin = cfg.m_t;
        if (cfg.level_b != 0u) { margin += cfg.t_r + max(mk.vk, 2.0) / (2.0 * cfg.b_e); }
        for (var c = 0u; c < m.conf_count; c++) {
            let ci = m.conf_start + c;
            let rel = select(cj_rel[cj_conflicts[ci].rel_index], cj_rel_s[cj_conflicts[ci].rel_index], scratch);
            t = max(t, rel + margin - cj_times[ci * 12u + k]);
        }
        if (t - now > tl + 1e-3) { continue; }
        cand_t = t;
        cand_k = k;
        return true;
    }
    return false;
}

fn exit_ok(mi: u32, k: u32) -> bool {
    if (cfg.exit_check == 0u) { return true; }
    let x = cj_links[mi].to_lane;
    let committed = atomicLoad(&cj_exits[x].n_committed);
    let n = cj_exits[x].n_on_lane + committed;
    // A lane too short for one car still takes one at a time.
    if (n > 0u && f32(n + 1u) * cfg.unit > cj_exits[x].length) { return false; }
    if (cj_exits[x].has_tail != 0u && cj_exits[x].tail_v < 5.0) {
        let vt = cj_exits[x].tail_v;
        let xt = cj_exits[x].tail_x - cfg.length + vt * vt / (2.0 * cfg.b_s);
        let vo = cj_mov_k[mi * N_CLASS + k].vout;
        let need = cfg.unit + cfg.t_r * vo + vo * vo / (2.0 * cfg.b_s);
        if (xt - f32(committed) * cfg.unit < need) { return false; }
    }
    return true;
}

// ---------------------------------------------------------------- stage 2: arbitrate, on scratch only

@compute @workgroup_size(16)
fn cj_arbitrate(@builtin(global_invocation_id) id: vec3u) {
    let j = id.x;
    if (j >= cfg.n_junctions || !is_tick(j)) { return; }
    let J = cj_junctions[j];
    cj_junctions[j].plan_n = 0u;
    now = f32(G.step) * P.dt;
    var in_zone = 0u;
    for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
        let sim = cj_apps[a].sim_lane;
        if (seg[sim].stamp == G.step) { in_zone += seg[sim].end - seg[sim].first; }
    }
    // CBR from senders, loss from CBR: report 08's Qualcomm anchors.
    let n = f32(in_zone);
    let cbr = select(select(0.47 + (n - 100.0) / 150.0 * 0.38, 0.25 + (n - 50.0) / 50.0 * 0.22, n < 100.0), n / 50.0 * 0.25, n < 50.0);
    let pl = select(select(0.007 + (cbr - 0.47) / 0.35 * 0.123, 0.005 + (cbr - 0.25) / 0.22 * 0.002, cbr < 0.47), cbr / 0.25 * 0.005, cbr < 0.25);
    cj_junctions[j].p_load = clamp(pl, 0.0, 0.5);
    if (plan_on()) {
        var ex = 0u;
        var rx = 0u;
        for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
            ex += cj_apps[a].n_exp;
            rx += cj_apps[a].n_rx;
        }
        if (ex > 0u) {
            let w = min(f32(ex) / LOSS_WINDOW, 1.0);
            cj_junctions[j].p_hat += (1.0 - f32(rx) / f32(ex) - J.p_hat) * w;
        }
        plan_loss = cj_junctions[j].p_hat;
        if (plan_loss >= P_FALLBACK_ON) { cj_junctions[j].fallback = 1u; }
        if (plan_loss <= P_FALLBACK_OFF) { cj_junctions[j].fallback = 0u; }
    }
    if (J.mode != MODE_FREE || J.frozen != 0u || !coordinator_up()) { return; }
    if (plan_here(j)) {
        now_ms = G.step * cfg.dt_ms;
        plan_sequence(j);
        return;
    }
    for (var r = J.rel_start; r < J.rel_start + J.rel_count; r++) { cj_rel_s[r] = cj_rel[r]; }
    for (var x = J.exit_start; x < J.exit_start + J.exit_count; x++) {
        cj_exits[x].s_exit_ref = cj_exits[x].exit_ref;
        cj_exits[x].s_exit_t = cj_exits[x].exit_t;
    }
    var planned = 0u;
    for (var round = 0u; round < PLAN_MAX; round++) {
        var best = NONE;
        var best_score = INF;
        for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
            if (cj_apps[a].s_cand_state == CAND_STALE) {
                let ptr = cj_apps[a].s_ptr;
                var ok = false;
                if (ptr < cj_apps[a].n_req) {
                    let q = cj_req[cj_apps[a].req_start + ptr];
                    ok = cand_time(q.link, q.d, q.v, now + 0.1, 0u, true);
                    if (ok) {
                        var score = cand_t;
                        if (now - q.age_t > cfg.a_max) { score -= 1e6; }
                        cj_apps[a].s_cand_t = cand_t;
                        cj_apps[a].s_cand_k = cand_k;
                        cj_apps[a].s_cand_score = score;
                    }
                }
                cj_apps[a].s_cand_state = select(CAND_NONE, CAND_OK, ok);
            }
            if (cj_apps[a].s_cand_state == CAND_OK && cj_apps[a].s_cand_score < best_score) {
                best_score = cj_apps[a].s_cand_score;
                best = a;
            }
        }
        if (best == NONE) { break; }
        let slot = cj_apps[best].req_start + cj_apps[best].s_ptr;
        let t = cj_apps[best].s_cand_t;
        let k = cj_apps[best].s_cand_k;
        let mi = cj_req[slot].link;
        let m = cj_links[mi];
        for (var c = 0u; c < m.conf_count; c++) {
            let ci = m.conf_start + c;
            let rv = cj_conflicts[ci].rev_index;
            cj_rel_s[rv] = max(cj_rel_s[rv], t + cj_times[ci * 12u + 6u + k]);
        }
        cj_apps[best].s_line_ref = mi * N_CLASS + k;
        cj_apps[best].s_line_t = t;
        cj_exits[m.to_lane].s_exit_ref = mi * N_CLASS + k;
        cj_exits[m.to_lane].s_exit_t = t;
        cj_req[slot].t_plan = t;
        cj_req[slot].k_plan = k;
        cj_plan[J.plan_start + planned] = slot;
        planned += 1u;
        cj_apps[best].s_ptr += 1u;
        // Only lanes in conflict with this choice need a fresh look.
        for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
            if (((m.conf_lanes >> (a - J.app_start)) & 1u) != 0u) { cj_apps[a].s_cand_state = CAND_STALE; }
        }
    }
    cj_junctions[j].plan_n = planned;
}

// ---------------------------------------------------------------- the planned schedule, research/truth/09d
// Times here are seconds from now in f32 and whole milliseconds since the start in u32.

// A car still turning speeds up when it leaves the box, one already out keeps doing what it is doing.
// How long until it has moved this far, and how far and how fast it is after t.
fn tail_time(dist: f32, x0: f32, v: f32, a_tail: f32, vmax: f32) -> f32 {
    let v0 = max(v, 0.5);
    var rem = dist;
    var t = 0.0;
    var acc = max(a_tail, 0.0);
    if (x0 < 0.0) {
        if (rem <= -x0) { return rem / v0; }
        t = -x0 / v0;
        rem += x0;
        acc = cfg.accel;
    }
    if (acc < 0.1 || vmax <= v0) { return t + rem / v0; }
    let ta = (vmax - v0) / acc;
    let da = v0 * ta + 0.5 * acc * ta * ta;
    if (rem <= da) { return t + (sqrt(v0 * v0 + 2.0 * acc * rem) - v0) / acc; }
    return t + ta + (rem - da) / vmax;
}

fn lead_x(v: f32, rem: f32, a_lead: f32, vmax: f32, tau: f32) -> f32 {
    let t1 = min(rem / max(v, 0.5), tau);
    let tr = tau - t1;
    let acc = select(max(a_lead, 0.0), cfg.accel, rem > 0.0);
    var x = v * t1;
    if (acc < 0.1 || vmax <= v) { return x + v * tr; }
    let ta = min((vmax - v) / acc, tr);
    return x + v * ta + 0.5 * acc * ta * ta + (tr - ta) * max(v + acc * ta, v);
}

fn tail_speed_at(tx: f32, v: f32, a_tail: f32, vmax: f32, t: f32) -> f32 {
    let t1 = select(0.0, -tx / max(v, 0.5), tx < 0.0);
    let acc = select(max(a_tail, 0.0), cfg.accel, tx < 0.0);
    return min(v + acc * max(t - t1, 0.0), max(vmax, v));
}

// As exit_ok, with the tail where it will be when this car arrives; the point of no return looks again.
fn plan_exit_ok(mi: u32, k: u32, t: f32) -> bool {
    if (cfg.exit_check == 0u) { return true; }
    let x = cj_links[mi].to_lane;
    let committed = atomicLoad(&cj_exits[x].n_committed);
    let n = cj_exits[x].n_on_lane + committed;
    if (n > 0u && f32(n + 1u) * cfg.unit > cj_exits[x].length) { return false; }
    if (cj_exits[x].has_tail != 0u) {
        let v0 = cj_exits[x].tail_v;
        let a0 = cj_exits[x].tail_a;
        let tx = cj_exits[x].tail_x;
        let vm = cj_links[mi].v_lane;
        let vt = tail_speed_at(tx, v0, a0, vm, t);
        if (vt < 5.0) {
            let xn = tx + lead_x(v0, max(-tx, 0.0), a0, vm, t);
            let xt = xn - cfg.length + vt * vt / (2.0 * cfg.b_s);
            let vo = cj_mov_k[mi * N_CLASS + k].vout;
            let need = cfg.unit + cfg.t_r * vo + vo * vo / (2.0 * cfg.b_s);
            if (xt - f32(committed) * cfg.unit < need) { return false; }
        }
    }
    return true;
}

// A lost grant leaves a car crossing slower and later than the table thinks, and the slower it crosses
// the more that costs in time. Level B, which promises no contact with a stalled car, always takes the
// margin; Level A only when the channel is losing messages, the full one when it loses many.
fn plan_slip(v: f32) -> f32 {
    if (cfg.level_b != 0u) { return 1.0 / max(v, 1.0); }
    // From a standstill the engine takes a moment to come in, and the table does not know that.
    if (plan_route() && v < 1.5 && plan_loss < 0.3) { return 0.5; }
    if (plan_loss < 0.01) { return 0.0; }
    return clamp(plan_loss / 0.3, 0.5, 1.0) / max(v, 1.0);
}

// When the lane out of this movement has the room a car needs, seconds from now. Room is counted as if
// everyone on it stopped where they fit, so it holds even if the next junction stops them. The cars on it
// leave in their order at the next junction at the times that junction has given them, so its plan
// reaches back here. Negative: there is room already. INF: no time can be named yet.
fn plan_room_time(x: u32, added: u32, need: f32, firm_only: bool) -> f32 {
    let on_box = atomicLoad(&cj_exits[x].n_box) + atomicLoad(&cj_exits[x].n_committed) + added;
    let sim = cj_exits[x].sim_lane;
    let on_lane = select(0u, seg[sim].end - seg[sim].first, seg[sim].stamp == G.step);
    let base = cj_exits[x].length - f32(on_lane + on_box) * cfg.unit;
    if (base >= need) { return -1.0; }
    let gone = u32(ceil((need - base) / cfg.unit));
    if (gone > on_lane) { return INF; }
    let e = cur[seg[sim].end - gone];
    if (cj_exits[x].next_app == NONE) {
        // No plan to read: going by what it is doing, as long as it is moving at all.
        if (e.speed < 1.0) { return INF; }
        return (cj_exits[x].length - e.pos) / e.speed;
    }
    let state = e.cj_state & CJ_STATE_MASK;
    // For a plan its plan will do. For a grant, only a grant counts: a car past the point of no return
    // must not be relying on a slot that can still move.
    if (state == CJ_FIRM) { return ms_rel(e.cj_t_ms); }
    if (firm_only || state == CJ_NONE || e.cj_rank == NONE) { return INF; }
    return ms_rel(e.cj_plan_ms);
}

// Max pressure, as a tie-break in time: how full the lane ahead is against how full this one is.
fn plan_pressure(mi: u32) -> f32 {
    let m = cj_links[mi];
    let sa = cj_apps[m.from_lane].sim_lane;
    let n_app = select(0u, seg[sa].end - seg[sa].first, seg[sa].stamp == G.step);
    let sx = cj_exits[m.to_lane].sim_lane;
    let n_exit = select(0u, seg[sx].end - seg[sx].first, seg[sx].stamp == G.step);
    return f32(n_exit) * cfg.unit / max(cj_exits[m.to_lane].length, 1.0) - f32(n_app) * cfg.unit / max(cj_apps[m.from_lane].length, 1.0);
}

const GATE_FILL: f32 = 0.5;
const PRESSURE: f32 = 0.0;
const ROOM_UNKNOWN: f32 = 30.0;
const LOSS_WINDOW: f32 = 40.0;
const P_FALLBACK_ON: f32 = 0.3;
const P_FALLBACK_OFF: f32 = 0.15;
const STALE_MS: i32 = 2500;
var<private> plan_loss: f32;
var<private> plan_wait: f32;
var<private> plan_vmax: f32;

// How much later than free flow this car will get through its approach, in all.
fn plan_delay(age_t: f32, t: f32, mi: u32) -> f32 {
    if (t > INF * 0.5) { return 0.0; }
    let m = cj_links[mi];
    return now - age_t + t - cj_apps[m.from_lane].length / max(m.v_lane, 1.0);
}


fn plan_cand(mi: u32, d: f32, v: f32, min_t: f32, kmin: u32, scratch: bool) -> bool {
    let m = cj_links[mi];
    let a = cfg.accel;
    var line_ref = cj_apps[m.from_lane].line_ref;
    var line_t = ms_rel(cj_apps[m.from_lane].line_ms);
    var exit_ref = cj_exits[m.to_lane].exit_ref;
    var exit_t = ms_rel(cj_exits[m.to_lane].exit_ms);
    if (scratch) {
        line_ref = cj_apps[m.from_lane].s_line_ref;
        line_t = cj_apps[m.from_lane].s_line_t;
        exit_ref = cj_exits[m.to_lane].s_exit_ref;
        exit_t = cj_exits[m.to_lane].s_exit_t;
    }
    let has_tail = cj_exits[m.to_lane].has_tail != 0u;
    let vt = cj_exits[m.to_lane].tail_v;
    let tx = cj_exits[m.to_lane].tail_x;
    var best_done = INF;
    var found = false;
    for (var k = kmin; k < N_CLASS; k++) {
        let mk = cj_mov_k[mi * N_CLASS + k];
        // The time to brake for a corner gently, while there is room; the normal limit when there is not.
        // The rate the car would brake at, as in plan_accel, or what it has to when it is that close.
        var bx = mix(cfg.plan_b, cfg.b_plan, clamp((plan_wait - cfg.plan_slack) / 8.0, 0.0, 1.0));
        if (v > mk.vk) { bx = clamp((v * v - mk.vk * mk.vk) / (2.0 * max(d, 0.1)) * 1.01, bx, cfg.b_plan); }
        var te = earliest(d, v, mk.vk, m.v_lane, a, bx);
        if (te < 0.0) { continue; }
        // The engine takes a moment to come in: a car that has to gain speed on its way to the line
        // would miss a slot exactly at the limit.
        if (v < mk.vk - 0.5 && d < 1.3 * (mk.vk * mk.vk - v * v) / (2.0 * a)) { te += 0.5 * a / (2.5 * cfg.plan_j); }
        // Waiting for a slot and still reaching its speed takes room. Not at the car's limits: a slot that
        // needs them gets missed, and a car arriving under its class speed stays in the box too long.
        let tl = latest(d, v, mk.vk, 0.9 * a, 0.8 * cfg.b_plan);
        if (tl < 0.0) { continue; }
        var t = max(te, min_t);
        if (line_ref != NONE) { t = max(t, line_t + headway(mi, k, line_ref, 0u)); }
        if (exit_ref != NONE) { t = max(t, exit_t + headway(mi, k, exit_ref, 1u)); }
        // The table covers a tail that follows its plan. One that has stopped following it is a real obstacle.
        // A lane that cannot hold a car is no store to count: the older exit check deals with it.
        if (plan_route() && cj_exits[m.to_lane].length >= 2.0 * cfg.unit) {
            let added = select(0u, cj_exits[m.to_lane].s_added, scratch);
            var need = cfg.unit + cfg.t_r * mk.vout + mk.vout * mk.vout / (2.0 * cfg.plan_bc);
            // From outside the coordinated area into it: keep room inside, so the area stays below the
            // density where it stops flowing. Cars then wait outside, not in the way.
            if (m.pad_l > 0.5 && cj_exits[m.to_lane].next_app != NONE) { need = max(need, GATE_FILL * cj_exits[m.to_lane].length); }
            // A short lane cannot give a fast car its whole stopping room; it takes a slower one or a part of it.
            let room = plan_room_time(m.to_lane, added, min(need, max(cfg.unit, 0.6 * cj_exits[m.to_lane].length)), !scratch);
            // Through the box and clear of it by then. If no time can be named yet, the slot is far out.
            if (room >= INF * 0.5) { t = max(t, ROOM_UNKNOWN); }
            else if (room > 0.0) { t = max(t, room - mk.t_clear); }
        }
        if (has_tail && tx >= 0.0 && vt < 1.0 && cj_exits[m.to_lane].tail_a < 0.1) {
            let v_t = 2.0;
            let need = 2.0 * cfg.length + cfg.s0 + mk.vout * cfg.tau - tx;
            if (need > 0.0) { t = max(t, need / v_t - mk.t_clear); }
            if (cfg.ponr != 0u) {
                let room = cfg.unit + cfg.length - tx - vt * vt / (2.0 * cfg.b_plan);
                let vm = max(mk.vk, 0.5);
                if (room > 0.0) { t = max(t, room / v_t + cfg.t_r + vm / (2.0 * cfg.b_s) + 2.0 / vm); }
            }
        }
        var margin = cfg.m_t;
        if (cfg.level_b != 0u) { margin += cfg.t_r + max(mk.vk, 2.0) / (2.0 * cfg.b_e); }
        // The slower a car crosses, the more a small slip in position costs in time.
        margin += plan_slip(mk.vk);
        for (var c = 0u; c < m.conf_count; c++) {
            let ci = m.conf_start + c;
            let ri = cj_conflicts[ci].rel_index;
            var rel = 0.0;
            if (scratch) { rel = cj_rel_s[ri]; } else { rel = ms_rel(cj_rel_ms[ri]); }
            t = max(t, rel + margin - cj_times[ci * 12u + k]);
        }
        if (t > tl + 1e-3) { continue; }
        // A slower class may go earlier behind a slow leader. Whichever clears the box first.
        let done = t + mk.t_clear;
        if (done < best_done - 0.05) {
            best_done = done;
            cand_t = t;
            cand_k = k;
            found = true;
        }
    }
    return found;
}

// The order is fixed once a car is close to its slot, because a later change would make it brake.
// Further out every car takes the earliest time it can, the list rule of the baseline, because keeping
// order from first contact collapses capacity (first come first served; see the report). A held slot
// moves earlier only when that gains something.
fn plan_scratch(j: u32) {
    let J = cj_junctions[j];
    for (var r = J.rel_start; r < J.rel_start + J.rel_count; r++) { cj_rel_s[r] = ms_rel(cj_rel_ms[r]); }
    for (var x = J.exit_start; x < J.exit_start + J.exit_count; x++) {
        cj_exits[x].s_exit_ref = cj_exits[x].exit_ref;
        cj_exits[x].s_exit_t = ms_rel(cj_exits[x].exit_ms);
    }
    for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
        cj_apps[a].s_line_ref = cj_apps[a].line_ref;
        cj_apps[a].s_line_t = ms_rel(cj_apps[a].line_ms);
        cj_apps[a].s_ptr = 0u;
    }
}

// One pass over the sequence as ranked. Returns the sum of times.
fn plan_pass(j: u32, store: bool) -> f32 {
    let J = cj_junctions[j];
    plan_scratch(j);
    var cost = 0.0;
    var planned = 0u;
    for (var guard = 0u; guard < cfg.plan_max; guard++) {
        var best = NONE;
        var best_rank = INF;
        for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
            if (cj_apps[a].s_ptr >= cj_apps[a].n_req) { continue; }
            let r = cj_req[cj_apps[a].req_start + cj_apps[a].s_ptr].rank;
            if (r < best_rank) {
                best_rank = r;
                best = a;
            }
        }
        if (best == NONE) { break; }
        let slot = cj_apps[best].req_start + cj_apps[best].s_ptr;
        let q = cj_req[slot];
        if (!plan_cand(q.link, q.d, q.v, 0.1, 0u, true)) {
            cj_apps[best].s_ptr = cj_apps[best].n_req;
            continue;
        }
        var t = cand_t;
        let k = cand_k;
        if (q.held < INF * 0.5 && t < q.held && q.held - t < cfg.plan_up) {
            let tl = latest(q.d, q.v, cj_mov_k[q.link * N_CLASS + k].vk, cfg.accel, cfg.b_plan);
            if (q.held <= tl) { t = q.held; }
        }
        let m = cj_links[q.link];
        for (var c = 0u; c < m.conf_count; c++) {
            let ci = m.conf_start + c;
            let rv = cj_conflicts[ci].rev_index;
            cj_rel_s[rv] = max(cj_rel_s[rv], t + cj_times[ci * 12u + 6u + k]);
        }
        cj_apps[best].s_line_ref = q.link * N_CLASS + k;
        cj_apps[best].s_line_t = t;
        cj_exits[m.to_lane].s_exit_ref = q.link * N_CLASS + k;
        cj_exits[m.to_lane].s_exit_t = t;
        if (store) {
            cj_req[slot].t_plan = t;
            cj_req[slot].k_plan = k;
            cj_plan[J.plan_start + planned] = slot;
        }
        cost += t;
        planned += 1u;
        cj_apps[best].s_ptr += 1u;
    }
    if (store) {
        cj_junctions[j].plan_n = planned;
        for (var n = 0u; n < planned; n++) { cj_req[cj_plan[J.plan_start + n]].rank = f32(n); }
    }
    return cost;
}

// Dynamic resequencing (Xu et al. 2020): the order of those placed stays, each new car goes where the
// sum of arrival times is least. It may not jump a car over the age limit.
fn plan_dr(j: u32) {
    let J = cj_junctions[j];
    var pass_done = false;
    for (var new_car = 0u; new_car < MAX_NEW; new_car++) {
        var pick = NONE;
        var pick_key = INF;
        var top = -1.0;
        var floor_r = -1.0;
        for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
            var first_new = NONE;
            for (var n = 0u; n < cj_apps[a].n_req; n++) {
                let q = cj_req[cj_apps[a].req_start + n];
                if (q.rank >= INF * 0.5) {
                    if (first_new == NONE) { first_new = cj_apps[a].req_start + n; }
                } else {
                    top = max(top, q.rank);
                    if (now - q.age_t > cfg.a_max) { floor_r = max(floor_r, q.rank); }
                }
            }
            if (first_new != NONE) {
                let q = cj_req[first_new];
                let key = q.d / max(q.v, 1.0);
                if (key < pick_key) {
                    pick_key = key;
                    pick = first_new;
                }
            }
        }
        if (pick == NONE) { break; }
        var lowest = floor_r;
        let lane = cj_links[cj_req[pick].link].from_lane;
        if (pick > cj_apps[lane].req_start) { lowest = max(lowest, cj_req[pick - 1u].rank); }
        var best_r = top + 0.5;
        var best_cost = INF;
        var r = top;
        for (var tries = 0u; tries < INSERT_TRIES && r >= lowest; tries++) {
            cj_req[pick].rank = r + 0.5;
            let cost = plan_pass(j, false);
            if (cost < best_cost - 0.01) {
                best_cost = cost;
                best_r = r + 0.5;
            }
            r -= 1.0;
        }
        cj_req[pick].rank = best_r;
        plan_pass(j, true);
        pass_done = true;
    }
    if (!pass_done) { plan_pass(j, true); }
}

fn plan_sequence(j: u32) {
    let J = cj_junctions[j];
    if ((cfg.plan & PLAN_DR) != 0u) {
        plan_dr(j);
        return;
    }
    for (var r = J.rel_start; r < J.rel_start + J.rel_count; r++) { cj_rel_s[r] = ms_rel(cj_rel_ms[r]); }
    for (var x = J.exit_start; x < J.exit_start + J.exit_count; x++) {
        cj_exits[x].s_exit_ref = cj_exits[x].exit_ref;
        cj_exits[x].s_exit_t = ms_rel(cj_exits[x].exit_ms);
        cj_exits[x].s_added = 0u;
    }
    for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
        cj_apps[a].s_line_ref = cj_apps[a].line_ref;
        cj_apps[a].s_line_t = ms_rel(cj_apps[a].line_ms);
        cj_apps[a].s_ptr = 0u;
        cj_apps[a].s_cand_state = CAND_STALE;
    }
    var planned = 0u;
    for (var guard = 0u; guard < cfg.plan_max; guard++) {
        var best = NONE;
        var best_rank = INF;
        for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
            if (cj_apps[a].s_ptr >= cj_apps[a].n_req) { continue; }
            let q = cj_req[cj_apps[a].req_start + cj_apps[a].s_ptr];
            if (q.held <= cfg.plan_freeze && q.rank < best_rank) {
                best_rank = q.rank;
                best = a;
            }
        }
        var t = 0.0;
        var k = 0u;
        if (best != NONE) {
            let q = cj_req[cj_apps[best].req_start + cj_apps[best].s_ptr];
            plan_wait = plan_delay(q.age_t, q.held, q.link);
            if (!plan_cand(q.link, q.d, q.v, 0.1, 0u, true)) {
                cj_apps[best].s_ptr = cj_apps[best].n_req;
                continue;
            }
            t = cand_t;
            k = cand_k;
        } else {
            var best_score = INF;
            for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
                if (cj_apps[a].s_cand_state == CAND_STALE) {
                    var ok = false;
                    if (cj_apps[a].s_ptr < cj_apps[a].n_req && cj_req[cj_apps[a].req_start + cj_apps[a].s_ptr].heard != 0u) {
                        let q = cj_req[cj_apps[a].req_start + cj_apps[a].s_ptr];
                        plan_wait = plan_delay(q.age_t, q.held, q.link);
                        ok = plan_cand(q.link, q.d, q.v, 0.1, 0u, true);
                        if (ok) {
                            var score = cand_t;
                            if (now - q.age_t > cfg.a_max) { score -= 1e6; }
                            if (plan_route()) { score += PRESSURE * plan_pressure(q.link); }
                            cj_apps[a].s_cand_t = cand_t;
                            cj_apps[a].s_cand_k = cand_k;
                            cj_apps[a].s_cand_score = score;
                        }
                    }
                    cj_apps[a].s_cand_state = select(CAND_NONE, CAND_OK, ok);
                }
                if (cj_apps[a].s_cand_state == CAND_OK && cj_apps[a].s_cand_score < best_score) {
                    best_score = cj_apps[a].s_cand_score;
                    best = a;
                }
            }
            if (best == NONE) { break; }
            t = cj_apps[best].s_cand_t;
            k = cj_apps[best].s_cand_k;
        }
        let slot = cj_apps[best].req_start + cj_apps[best].s_ptr;
        let q = cj_req[slot];
        if (q.held < INF * 0.5 && t < q.held && q.held - t < cfg.plan_up) {
            let tl = latest(q.d, q.v, cj_mov_k[q.link * N_CLASS + k].vk, cfg.accel, cfg.b_plan);
            if (q.held <= tl) { t = q.held; }
        }
        let m = cj_links[q.link];
        for (var c = 0u; c < m.conf_count; c++) {
            let ci = m.conf_start + c;
            let rv = cj_conflicts[ci].rev_index;
            cj_rel_s[rv] = max(cj_rel_s[rv], t + cj_times[ci * 12u + 6u + k] + plan_slip(cj_mov_k[q.link * N_CLASS + k].vk));
        }
        cj_apps[best].s_line_ref = q.link * N_CLASS + k;
        cj_apps[best].s_line_t = t;
        cj_exits[m.to_lane].s_exit_ref = q.link * N_CLASS + k;
        cj_exits[m.to_lane].s_exit_t = t;
        cj_exits[m.to_lane].s_added += 1u;
        // Only lanes in conflict get a fresh look below; a lane sharing this exit is one of them.
        cj_req[slot].t_plan = t;
        cj_req[slot].k_plan = k;
        cj_plan[J.plan_start + planned] = slot;
        planned += 1u;
        cj_apps[best].s_ptr += 1u;
        for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
            if (((m.conf_lanes >> (a - J.app_start)) & 1u) != 0u) { cj_apps[a].s_cand_state = CAND_STALE; }
        }
    }
    cj_junctions[j].plan_n = planned;
}

fn plan_commit_real(j: u32, q: CjReq, mi: u32, k: u32, t: f32, deliver_now: bool) {
    let m = cj_links[mi];
    let ms = rel_ms(t);
    for (var c = 0u; c < m.conf_count; c++) {
        let ci = m.conf_start + c;
        let rv = cj_conflicts[ci].rev_index;
        let out = rel_ms(t + cj_times[ci * 12u + 6u + k] + plan_slip(cj_mov_k[mi * N_CLASS + k].vk));
        if (i32(out - cj_rel_ms[rv]) > 0) { cj_rel_ms[rv] = out; }
        cj_rel[rv] = max(cj_rel[rv], now + ms_rel(out));
    }
    cj_apps[m.from_lane].line_ref = mi * N_CLASS + k;
    cj_apps[m.from_lane].line_ms = ms;
    cj_apps[m.from_lane].line_t = now + ms_rel(ms);
    cj_exits[m.to_lane].exit_ref = mi * N_CLASS + k;
    cj_exits[m.to_lane].exit_ms = ms;
    cj_exits[m.to_lane].exit_t = now + ms_rel(ms);
    atomicAdd(&cj_exits[m.to_lane].n_committed, 1u);
    let seq = cj_exits[m.to_lane].seq + 1u;
    cj_exits[m.to_lane].seq = seq;
    stat(cj_junctions[j].replica, S_GRANTS, 1u);
    stat(cj_junctions[j].replica, S_BYTES_DOWN, 180u);
    cur[q.veh].cj_rx_ms = now_ms;
    cur[q.veh].cj_t_ms = ms;
    cur[q.veh].cj_plan_ms = ms;
    cur[q.veh].cj_t_line = f32(ms) * 0.001;
    cur[q.veh].cj_v_line = cj_mov_k[mi * N_CLASS + k].vk;
    cur[q.veh].cj_link = mi;
    cur[q.veh].cj_seq = seq;
    let keep = cur[q.veh].cj_state & CJ_KEEP;
    cur[q.veh].cj_state = keep | select(CJ_PENDING, CJ_FIRM, deliver_now) | (k << CJ_K_SHIFT);
}

// When the tail of the exit will have room for this car at its point of no return, on what it knows now.
// A grant that the check there would refuse is a hard brake already planned.
fn plan_ponr_time(mi: u32, k: u32) -> f32 {
    let x = cj_links[mi].to_lane;
    if (cfg.ponr == 0u || cj_exits[x].has_tail == 0u) { return -INF; }
    let v0 = cj_exits[x].tail_v;
    let a0 = cj_exits[x].tail_a;
    let tx = cj_exits[x].tail_x;
    let vm = cj_links[mi].v_lane;
    let ahead = f32(atomicLoad(&cj_exits[x].n_committed));
    let vk = max(cj_mov_k[mi * N_CLASS + k].vk, 0.5);
    let lead = cfg.t_r + vk / (2.0 * cfg.b_s) + 2.0 / vk;
    var tau = 0.0;
    for (var it = 0u; it < 24u; it++) {
        let xn = tx + lead_x(v0, max(-tx, 0.0), a0, vm, tau);
        let vn = tail_speed_at(tx, v0, a0, vm, tau);
        if (xn < 0.0 || xn - cfg.length + vn * vn / (2.0 * cfg.b_plan) - ahead * cfg.unit >= cfg.unit) { return tau + lead; }
        tau += 0.25;
    }
    return tau + lead;
}

fn plan_firm(mi: u32, d: f32, v: f32, min_t: f32, replica: u32) -> bool {
    var kmin = 0u;
    loop {
        if (kmin >= N_CLASS) { return false; }
        if (!plan_cand(mi, d, v, min_t, kmin, false)) { return false; }
        let need = plan_ponr_time(mi, cand_k);
        if (cand_t < need && !plan_cand(mi, d, v, need, kmin, false)) { return false; }
        if (cand_t > cfg.t_firm + 1.0) { return false; }
        if (plan_exit_ok(mi, cand_k, cand_t)) { return true; }
        stat(replica, S_EXIT_REFUSED, 1u);
        kmin = cand_k + 1u;
    }
    return false;
}

// The slots go out; those inside the firm horizon become grants at the time they were promised.
fn plan_commit(j: u32) {
    let J = cj_junctions[j];
    let tick = f32(cfg.tick_steps) * P.dt;
    var blocked = 0u;
    let free = lossless();
    for (var n = 0u; n < J.plan_n; n++) {
        let slot = cj_plan[J.plan_start + n];
        let q = cj_req[slot];
        let ord = cj_links[q.link].from_lane - J.app_start;
        let ms = rel_ms(q.t_plan);
        let mk = cj_mov_k[q.link * N_CLASS + q.k_plan];
        let e = cur[q.veh];
        if (now >= cfg.warm) {
            if (q.held > INF * 0.5) {
            } else if (q.t_plan - q.held > 0.05) {
                stat(J.replica, S_MOVED_LATER, 1u);
            } else if (q.held - q.t_plan > 0.05) {
                stat(J.replica, S_MOVED_EARLIER, 1u);
            }
        }
        cur[q.veh].cj_rank = n;
        cur[q.veh].cj_plan_ms = ms;
        // Sent when it changed, and once a second otherwise, so a lost one is repaired.
        let known = (e.cj_state & CJ_STATE_MASK) != CJ_NONE;
        let changed = !known || abs(i32(ms - e.cj_t_ms)) > 20 || e.cj_v_line != mk.vk;
        let repeat_now = ((G.step / cfg.tick_steps) + q.trip) % 2u == 1u;
        if (changed || repeat_now) {
            stat(J.replica, S_BYTES_DOWN, 180u);
            if (free || delivered(q.trip, 3u, q.d, J.p_load, J.replica)) {
                cur[q.veh].cj_rx_ms = now_ms;
                cur[q.veh].cj_t_ms = ms;
                cur[q.veh].cj_t_line = f32(ms) * 0.001;
                cur[q.veh].cj_v_line = mk.vk;
                cur[q.veh].cj_link = q.link;
                if (!known) { cur[q.veh].cj_state = (e.cj_state & CJ_KEEP) | CJ_ADVISED; }
            }
        }
        let horizon = q.d <= q.v * q.v / (2.0 * cfg.b_plan) + q.v * (tick + 0.3) + 5.0 || q.t_plan <= cfg.t_firm;
        if (!horizon || ((blocked >> ord) & 1u) != 0u) {
            blocked |= 1u << ord;
            continue;
        }
        if (!free && !delivered(q.trip, 1u, q.d, J.p_load, J.replica)) {
            blocked |= 1u << ord;
            continue;
        }
        plan_wait = plan_delay(q.age_t, q.t_plan, q.link);
        if (!plan_firm(q.link, q.d, q.v, max(0.1, q.t_plan), J.replica)) {
            blocked |= 1u << ord;
            continue;
        }
        plan_commit_real(j, q, q.link, cand_k, cand_t, free);
    }
}

// How the car drives to its slot. By default it slows once, gently, holds the speed that arrives on
// time, and ramps to the class speed on the last metres. With PLAN_CUBIC, the energy optimal arc of
// Malikopoulos, Cassandras and Zhang 2018 where that stays in bounds: acceleration linear in time, which
// with a fixed end speed dips 1.5 times as far below the start speed as the cruise does.
fn plan_accel(d: f32, v: f32, t: f32, ve: f32, vcap: f32, bc: f32) -> f32 {
    let a_c = cfg.accel;
    if (t <= 0.0) { return min((vcap - v) / dt, a_c); }
    // In the last moment there is no time left to correct and small errors blow up: go for the speed.
    if (t <= 0.5) { return clamp((ve - v) / max(t, 0.2), -1.0, a_c); }
    let aa = ve - v;
    let bb = d - v * t;
    let u0 = (6.0 * bb - 2.0 * aa * t) / (t * t);
    // Near the line only the exact arc hits both the time and the speed, if it stays inside the car's
    // limits. If it would ask for more than the engine has at the end, gain the speed now instead.
    if (bc > cfg.plan_bc && t <= max(abs(aa) / select(cfg.plan_b, 0.8 * a_c, ve > v) * 1.2, 1.0)) {
        let uend = u0 + 2.0 * (aa - u0 * t) / t;
        if (max(u0, uend) <= a_c && min(u0, uend) >= -bc) { return u0; }
        let up = 0.9 * a_c;
        let vc = plan_vc_ab(v, d, t, ve, vcap, up, cfg.b_plan);
        let d3 = abs(ve * ve - v * v) / (2.0 * select(cfg.b_plan, up, ve > v));
        if (d <= d3 + v * dt) {
            if (ve < v) { return clamp((ve * ve - v * v) / (2.0 * max(d, 0.1)), -bc, 0.0); }
            if (t <= (ve - v) / up + 0.1) { return min((ve * ve - v * v) / (2.0 * max(d, 0.1)) + 0.1, a_c); }
            return clamp(min(v, vc) - v, -bc, 0.0);
        }
        return clamp((vc - v) / 0.3, -bc, a_c);
    }
    if ((cfg.plan & PLAN_CUBIC) != 0u) {
        let j = 2.0 * (aa - u0 * t) / (t * t);
        var vext = v;
        if (abs(j) > 1e-6) {
            let tau = -u0 / j;
            if (tau > 0.0 && tau < t) { vext = v + u0 * tau + 0.5 * j * tau * tau; }
        }
        let uend = u0 + j * t;
        if (vext <= vcap + 0.05 && vext >= 0.3 && v <= vcap + 0.2 && max(u0, uend) <= a_c && min(u0, uend) >= -bc) { return u0; }
    }
    // Leaves some of the engine in hand for the last ramp, so a small delay can still be made up.
    let up = 0.8 * a_c;
    // A car in a long queue keeps its speed longer and brakes less gently, so that it can still take an
    // earlier slot when one opens: slowing early gives up the freedom that saturation flow needs.
    var b = mix(cfg.plan_b, cfg.plan_bc, clamp((plan_wait - cfg.plan_slack) / 8.0, 0.0, 1.0));
    // A firm slot that moved at the last moment has to be kept, or the car arrives early and then too slow.
    if (plan_route() && bc > cfg.plan_bc) { b = cfg.plan_bc; }
    let vc = plan_vc_ab(v, d, t, ve, vcap, up, b);
    let rate = select(b, up, ve > v);
    let d3 = abs(ve * ve - v * v) / (2.0 * rate);
    if (d <= d3 + v * (dt + 0.5 * b / cfg.plan_j)) {
        if (ve < v) { return clamp((ve * ve - v * v) / (2.0 * max(d, 0.1)), -cfg.b_plan, 0.0); }
        if (t <= (ve - v) / rate + 0.2) { return min((ve * ve - v * v) / (2.0 * max(d, 0.1)) + 0.1, a_c); }
        return clamp(min(v, vc) - v, -bc, 0.0);
    }
    if (bc <= cfg.plan_bc) { return clamp(vc - v, -b, a_c); }
    return clamp(vc - v, -bc, a_c);
}

// Where a planned car will be in tau seconds, as the plan it broadcasts says.
fn plan_x(d: f32, v: f32, t: f32, ve: f32, a_now: f32, tau: f32) -> f32 {
    // Takes up the speed that arrives on time, then the last ramp to the class speed, as plan_accel drives it.
    if (t > 0.2 && (cfg.plan & PLAN_CUBIC) == 0u) {
        let up = 0.8 * cfg.accel;
        let vc = plan_vc_ab(v, d, t, ve, max(max(v, ve), plan_vmax), up, cfg.plan_b);
        let rate = select(cfg.plan_b, up, ve > vc);
        let tr = min(abs(ve - vc) / rate, t);
        let tc = t - tr;
        // Not faster than it can get going from what it is doing now, for instance stuck in a queue.
        if (tau <= tc) { return min(vc * tau, v * tau + 0.5 * up * tau * tau); }
        let u = select(-rate, rate, ve > vc);
        let dt_r = min(tau - tc, tr);
        return vc * tc + vc * dt_r + 0.5 * u * dt_r * dt_r + max(tau - t, 0.0) * ve;
    }
    if (t > 0.2) {
        let aa = ve - v;
        let bb = d - v * t;
        let u0 = (6.0 * bb - 2.0 * aa * t) / (t * t);
        let j = 2.0 * (aa - u0 * t) / (t * t);
        let tm = min(tau, t);
        let x = v * tm + 0.5 * u0 * tm * tm + j * tm * tm * tm / 6.0;
        var vext = v;
        if (abs(j) > 1e-6) {
            let t0 = -u0 / j;
            if (t0 > 0.0 && t0 < t) { vext = v + u0 * t0 + 0.5 * j * t0 * t0; }
        }
        if (vext >= 0.0 && x >= 0.0) { return x + max(tau - t, 0.0) * ve; }
    }
    return max(v * tau + 0.5 * min(a_now, 0.0) * tau * tau, 0.0);
}

// The largest acceleration that keeps behind a leader whose motion over the next seconds is given.
fn behind(gap: f32, v: f32, x1: f32, x2: f32, x4: f32, tg: f32) -> f32 {
    let u1 = (gap + x1 - v - cfg.s0 - tg * v) / (0.5 + tg);
    let u2 = (gap + x2 - 2.0 * v - cfg.s0 - tg * v) / (2.0 + 2.0 * tg);
    let u4 = (gap + x4 - 4.0 * v - cfg.s0 - tg * v) / (8.0 + 4.0 * tg);
    return min(u1, min(u2, u4));
}

// ---------------------------------------------------------------- stage 3: commit, durable before visible

fn commit_real(j: u32, q: CjReq, mi: u32, k: u32, t: f32, deliver_now: bool) {
    let m = cj_links[mi];
    for (var c = 0u; c < m.conf_count; c++) {
        let ci = m.conf_start + c;
        let rv = cj_conflicts[ci].rev_index;
        cj_rel[rv] = max(cj_rel[rv], t + cj_times[ci * 12u + 6u + k]);
        // The planner reads milliseconds; when it comes back it must see these reservations.
        if (plan_on()) {
            let out = rel_ms(t - now + cj_times[ci * 12u + 6u + k]);
            if (i32(out - cj_rel_ms[rv]) > 0) { cj_rel_ms[rv] = out; }
        }
    }
    cj_apps[m.from_lane].line_ref = mi * N_CLASS + k;
    cj_apps[m.from_lane].line_t = t;
    cj_exits[m.to_lane].exit_ref = mi * N_CLASS + k;
    cj_exits[m.to_lane].exit_t = t;
    if (plan_on()) {
        let ms = rel_ms(t - now);
        cj_apps[m.from_lane].line_ms = ms;
        cj_exits[m.to_lane].exit_ms = ms;
        cur[q.veh].cj_t_ms = ms;
        cur[q.veh].cj_plan_ms = ms;
        cur[q.veh].cj_rx_ms = now_ms;
    }
    atomicAdd(&cj_exits[m.to_lane].n_committed, 1u);
    // Numbered per exit lane, so that cars in its box never share a table slot until K_BOX of them are in.
    let seq = cj_exits[m.to_lane].seq + 1u;
    cj_exits[m.to_lane].seq = seq;
    stat(cj_junctions[j].replica, S_GRANTS, 1u);
    cur[q.veh].cj_t_line = t;
    cur[q.veh].cj_v_line = cj_mov_k[mi * N_CLASS + k].vk;
    cur[q.veh].cj_link = mi;
    cur[q.veh].cj_seq = seq;
    let keep = cur[q.veh].cj_state & CJ_KEEP;
    cur[q.veh].cj_state = keep | select(CJ_PENDING, CJ_FIRM, deliver_now) | (k << CJ_K_SHIFT);
}

fn firm_time(mi: u32, d: f32, v: f32, min_t: f32) -> bool {
    var kmin = 0u;
    loop {
        if (kmin >= N_CLASS) { return false; }
        if (!cand_time(mi, d, v, min_t, kmin, false)) { return false; }
        if (cand_t - now > cfg.t_firm + 1.0) { return false; }
        if (exit_ok(mi, cand_k)) { return true; }
        kmin = cand_k + 1u;
    }
    return false;
}

// All-way stop, by V2V or sensing: the oldest head car at its line has the whole box to itself.
fn awsc(j: u32, min_wait: f32) {
    let J = cj_junctions[j];
    if (now < J.awsc_free) { return; }
    var best_age = INF;
    var best = NONE;
    for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
        let sim = cj_apps[a].sim_lane;
        if (seg[sim].stamp != G.step || cj_apps[a].n_req == 0u) { continue; }
        let head = cur[seg[sim].end - 1u];
        let state = head.cj_state & CJ_STATE_MASK;
        if (state == CJ_FIRM || state == CJ_PENDING) { continue; }
        let q = cj_req[cj_apps[a].req_start];
        if (q.d < 3.0 && q.v < 0.5 && head.wait >= min_wait && q.age_t < best_age) {
            best_age = q.age_t;
            best = a;
        }
    }
    if (best == NONE) { return; }
    let q = cj_req[cj_apps[best].req_start];
    if (plan_here(j)) {
        now_ms = G.step * cfg.dt_ms;
        plan_wait = 0.0;
        if (!plan_cand(q.link, q.d, q.v, 0.5, 0u, false) || !exit_ok(q.link, cand_k)) { return; }
        let tp = cand_t;
        let kp = cand_k;
        cj_junctions[j].awsc_free = now + tp + cj_mov_k[q.link * N_CLASS + kp].t_clear + 1.0;
        plan_commit_real(j, q, q.link, kp, tp, true);
        return;
    }
    if (!cand_time(q.link, q.d, q.v, now + 0.5, 0u, false) || !exit_ok(q.link, cand_k)) { return; }
    let t = cand_t;
    let k = cand_k;
    let m = cj_links[q.link];
    cj_junctions[j].awsc_free = t + cj_mov_k[q.link * N_CLASS + k].t_clear + 1.0;
    commit_real(j, q, q.link, k, t, true);
}

fn group_has_demand(j: u32, g: u32, horizon: f32) -> bool {
    let J = cj_junctions[j];
    for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
        var serves = false;
        let start = cj_apps[a].mov_start;
        for (var m = start; m < start + cj_apps[a].mov_count; m++) {
            if (((cj_links[m].group >> g) & 1u) != 0u) { serves = true; }
        }
        if (serves && cj_apps[a].n_req > 0u) {
            let q = cj_req[cj_apps[a].req_start];
            if (q.d / max(q.v, 1.0) < horizon) { return true; }
        }
    }
    return false;
}

// The signal baseline: the same cars and the same conflict table, but only one phase group may go.
fn signal_tick(j: u32) {
    let J = cj_junctions[j];
    var phase = J.phase;
    let el = now - J.phase_t;
    let ext = group_has_demand(j, phase, cfg.sig_gap);
    var next = NONE;
    for (var g = 0u; g < 32u; g++) {
        if (((J.group_mask >> g) & 1u) == 0u || g == phase) { continue; }
        if (group_has_demand(j, g, 60.0)) {
            next = g;
            break;
        }
    }
    if (next != NONE && el >= cfg.sig_min && (!ext || el >= cfg.sig_max) && now >= J.switch_t) {
        phase = next;
        cj_junctions[j].phase = phase;
        cj_junctions[j].phase_t = now + cfg.sig_lost;
        cj_junctions[j].switch_t = now + cfg.sig_lost;
    }
    if (now < cj_junctions[j].switch_t) { return; }
    let tick = f32(cfg.tick_steps) * P.dt;
    for (var a = J.app_start; a < J.app_start + J.app_count; a++) {
        for (var n = 0u; n < cj_apps[a].n_req; n++) {
            let q = cj_req[cj_apps[a].req_start + n];
            if (((cj_links[q.link].group >> phase) & 1u) == 0u) { break; }
            let horizon = q.d <= q.v * q.v / (2.0 * cfg.b_plan) + q.v * (tick + 0.3) + 5.0;
            var extra = 0.0;
            if (q.v < 0.5 && now - cj_junctions[j].phase_t < tick * 1.5) { extra = cfg.sig_start; }
            var kmin = 0u;
            var found = false;
            loop {
                if (kmin >= N_CLASS) { break; }
                if (!cand_time(q.link, q.d, q.v, now + 0.1 + extra, kmin, false)) { break; }
                if (exit_ok(q.link, cand_k)) {
                    found = true;
                    break;
                }
                kmin = cand_k + 1u;
            }
            if (!found) { break; }
            if (!(horizon || cand_t - now <= cfg.t_firm) || cand_t - now > cfg.t_firm + 1.0) { break; }
            commit_real(j, q, q.link, cand_k, cand_t, lossless());
        }
    }
}

@compute @workgroup_size(16)
fn cj_commit(@builtin(global_invocation_id) id: vec3u) {
    let j = id.x;
    if (j >= cfg.n_junctions || !is_tick(j)) { return; }
    let J = cj_junctions[j];
    if (J.mode == MODE_SUMO || J.frozen != 0u) { return; }
    now = f32(G.step) * P.dt;
    if (!coordinator_up()) {
        if (cfg.fallback != 0u) { awsc(j, 0.0); }
        return;
    }
    if (J.mode == MODE_SIGNAL) {
        signal_tick(j);
        return;
    }
    now_ms = G.step * cfg.dt_ms;
    plan_loss = J.p_hat;
    if (plan_here(j)) {
        plan_commit(j);
        if (cfg.fallback != 0u) { awsc(j, HEARD_NOTHING); }
        return;
    }
    let tick = f32(cfg.tick_steps) * P.dt;
    var blocked = 0u;
    let free = lossless();
    for (var n = 0u; n < J.plan_n; n++) {
        let slot = cj_plan[J.plan_start + n];
        let q = cj_req[slot];
        let ord = cj_links[q.link].from_lane - J.app_start;
        let mk = cj_mov_k[q.link * N_CLASS + q.k_plan];
        var state = cur[q.veh].cj_state;
        if ((state & CJ_STATE_MASK) == CJ_NONE) { state = (state & CJ_KEEP) | CJ_ADVISED; }
        cur[q.veh].cj_state = state;
        cur[q.veh].cj_t_line = q.t_plan;
        cur[q.veh].cj_v_line = mk.vk;
        cur[q.veh].cj_link = q.link;
        let horizon = q.d <= q.v * q.v / (2.0 * cfg.b_plan) + q.v * (tick + 0.3) + 5.0 || q.t_plan - now <= cfg.t_firm;
        if (!horizon || ((blocked >> ord) & 1u) != 0u) {
            blocked |= 1u << ord;
            continue;
        }
        if (!free && !delivered(q.trip, 1u, q.d, J.p_load, J.replica)) {
            blocked |= 1u << ord;
            continue;
        }
        if (!firm_time(q.link, q.d, q.v, now + 0.1)) {
            blocked |= 1u << ord;
            continue;
        }
        commit_real(j, q, q.link, cand_k, cand_t, free);
    }
    // A car cannot tell a dead radio from bad luck. Parked at the line this long with no grant, it
    // goes by sensing alone, one car at a time with the box to itself.
    if (cfg.fallback != 0u) { awsc(j, HEARD_NOTHING); }
}

// ---------------------------------------------------------------- stage 5: sensing, independent of the schedule

fn abort_on_lane(q: u32, mi: u32, replica: u32) {
    abort_grant(q, mi, replica);
}

// A foe on movement `f`, entering at foe_in: brake for the body at (t_clear) if it can still stop.
fn yield_foes(j: u32, f: u32, foe_in: f32, t_clear: f32, t_in: f32) {
    let fm = cj_links[f];
    let sim = cj_apps[fm.from_lane].sim_lane;
    let len = cj_apps[fm.from_lane].length;
    if (seg[sim].stamp == G.step) {
        let first = seg[sim].first;
        var idx = seg[sim].end;
        loop {
            if (idx <= first) { break; }
            idx -= 1u;
            let e = cur[idx];
            let d = len - e.pos;
            let to_conf = foe_in + d;
            if (to_conf > 80.0) { break; }
            if ((e.cj_state & CJ_STATE_MASK) != CJ_FIRM || e.cj_link != f || to_conf <= 0.5) { continue; }
            let vq = max(e.speed, 0.5);
            if (t_clear > to_conf / vq - 0.1 && to_conf / vq + FOE_DWELL > t_in && to_conf >= e.speed * cfg.t_r + e.speed * e.speed / (2.0 * cfg.b_e)) {
                cur[idx].cj_yield = min(cur[idx].cj_yield, foe_in - 0.5);
            }
        }
    }
    let x = fm.to_lane;
    for (var k = 0u; k < K_BOX; k++) {
        let b = cj_box[x * K_BOX + k];
        if (b.stamp != G.step + 1u || b.mov != f) { continue; }
        let to_conf = foe_in - b.s;
        if (to_conf <= 0.5 || to_conf > 80.0) { continue; }
        let vq = max(b.v, 0.5);
        if (t_clear > to_conf / vq - 0.1 && to_conf / vq + FOE_DWELL > t_in && to_conf >= b.v * cfg.t_r + b.v * b.v / (2.0 * cfg.b_e)) {
            cur[b.veh].cj_yield = min(cur[b.veh].cj_yield, foe_in - 0.5);
        }
    }
}

// Where a stalled car is now: its path position, -INF if gone.
fn stalled_position(j: u32) -> f32 {
    let J = cj_junctions[j];
    let x = cj_links[J.stall_mov].to_lane;
    let b = cj_box[x * K_BOX + J.stall_seq % K_BOX];
    if (b.stamp == G.step + 1u && b.trip == J.stall_trip) { return b.s; }
    let sim = cj_exits[x].sim_lane;
    if (seg[sim].stamp == G.step) {
        for (var q = seg[sim].first; q < seg[sim].end; q++) {
            if (cur[q].trip == J.stall_trip) { return cj_links[J.stall_mov].path_len + cur[q].pos; }
        }
    }
    return -INF;
}

fn hold_car(q: u32, s_hold: f32) {
    cur[q].cj_hold = min(cur[q].cj_hold, s_hold);
}

// One car on this movement responds to a body stalled at ss on movement sm.
fn stall_rule(j: u32, q: u32, s_q: f32, mv: u32, sm: u32, ss: f32, on_approach: bool) {
    let J = cj_junctions[j];
    let e = cur[q];
    let vq = e.speed;
    let d_brake = vq * cfg.t_r + vq * vq / (2.0 * cfg.b_e);
    let m = cj_links[mv];
    let sl = cj_links[sm];
    if (m.to_lane == sl.to_lane) {
        let at = m.path_len + (ss - sl.path_len) - cfg.length - 1.0;
        if (s_q < at + 1.0) { hold_car(q, at); }
    } else {
        var crossing = false;
        var rs = 0.0;
        for (var c = m.conf_start; c < m.conf_start + m.conf_count; c++) {
            if (cj_conflicts[c].foe == sm) {
                crossing = true;
                rs = cj_conflicts[c].s_in;
            }
        }
        var on_shared = false;
        if (m.from_lane == sl.from_lane) {
            for (var p = m.pair_start; p < m.pair_start + m.pair_count; p++) {
                if (cj_pairs[p].other == sm && cj_pairs[p].is_exit == 0u && ss - cfg.length < cj_pairs[p].s_end) { on_shared = true; }
            }
        }
        if (on_shared) {
            let at = ss - cfg.length - 1.0;
            if (s_q < at + 1.0) { hold_car(q, at); }
        } else if (crossing) {
            let at = rs - 0.5;
            if (s_q < at && at - s_q >= d_brake) { hold_car(q, at); }
        }
    }
    if (on_approach && -s_q >= d_brake) {
        hold_car(q, -0.5);
        let state = e.cj_state & CJ_STATE_MASK;
        if (state == CJ_FIRM || state == CJ_PENDING) { abort_on_lane(q, mv, J.replica); }
    }
}

@compute @workgroup_size(16)
fn cj_perceive(@builtin(global_invocation_id) id: vec3u) {
    let j = id.x;
    if (j >= cfg.n_junctions) { return; }
    let J = cj_junctions[j];
    now = f32(G.step) * P.dt;
    // Stall injection: at most one at a time per junction.
    if (cfg.stall_rate > 0.0 && now >= cfg.warm && J.stall_active == 0u
        && hash01(j + 1000u * J.replica, G.step, 11u) < cfg.stall_rate / 3600.0 * P.dt) {
        var count = 0u;
        for (var x = J.exit_start; x < J.exit_start + J.exit_count; x++) {
            for (var k = 0u; k < K_BOX; k++) {
                if (cj_box[x * K_BOX + k].stamp == G.step + 1u) { count += 1u; }
            }
        }
        if (count > 0u) {
            var pick = u32(hash01(j, G.step, 12u) * f32(count));
            for (var x = J.exit_start; x < J.exit_start + J.exit_count; x++) {
                for (var k = 0u; k < K_BOX; k++) {
                    let b = cj_box[x * K_BOX + k];
                    if (b.stamp != G.step + 1u) { continue; }
                    if (pick == 0u) {
                        cj_junctions[j].stall_active = 1u;
                        cj_junctions[j].stall_trip = b.trip;
                        cj_junctions[j].stall_mov = b.mov;
                        cj_junctions[j].stall_seq = b.seq;
                        cj_junctions[j].stall_detect = now + cfg.t_r;
                        cj_junctions[j].stall_until = now + cfg.stall_t;
                        cur[b.veh].cj_state |= CJ_STALLED;
                        stat(J.replica, S_STALLS, 1u);
                    }
                    pick -= 1u;
                }
            }
        }
    }
    let Jn = cj_junctions[j];
    var box_busy = false;
    for (var x = Jn.exit_start; x < Jn.exit_start + Jn.exit_count; x++) {
        if (atomicLoad(&cj_exits[x].n_box) > 0u) { box_busy = true; }
    }
    if (Jn.stall_active != 0u) {
        let ss = stalled_position(j);
        if (now >= Jn.stall_until || ss <= -INF) {
            cj_junctions[j].stall_active = 0u;
            let sim = cj_exits[cj_links[Jn.stall_mov].to_lane].sim_lane;
            let b = cj_box[cj_links[Jn.stall_mov].to_lane * K_BOX + Jn.stall_seq % K_BOX];
            if (b.stamp == G.step + 1u && b.trip == Jn.stall_trip) { cur[b.veh].cj_state &= ~CJ_STALLED; }
            if (seg[sim].stamp == G.step) {
                for (var q = seg[sim].first; q < seg[sim].end; q++) {
                    if (cur[q].trip == Jn.stall_trip) { cur[q].cj_state &= ~CJ_STALLED; }
                }
            }
        } else if (now >= Jn.stall_detect) {
            cj_junctions[j].frozen = 1u;
            for (var mv = Jn.mov_start; mv < Jn.mov_start + Jn.mov_count; mv++) {
                let m = cj_links[mv];
                let sim = cj_apps[m.from_lane].sim_lane;
                if (seg[sim].stamp == G.step) {
                    let len = cj_apps[m.from_lane].length;
                    for (var q = seg[sim].first; q < seg[sim].end; q++) {
                        if (cur[q].cj_link == mv) { stall_rule(j, q, cur[q].pos - len, mv, Jn.stall_mov, ss, true); }
                    }
                }
                for (var k = 0u; k < K_BOX; k++) {
                    let b = cj_box[m.to_lane * K_BOX + k];
                    if (b.stamp == G.step + 1u && b.mov == mv && b.trip != Jn.stall_trip) {
                        stall_rule(j, b.veh, b.s, mv, Jn.stall_mov, ss, false);
                    }
                }
            }
        }
    } else if (Jn.frozen != 0u && !box_busy) {
        cj_junctions[j].frozen = 0u;
    }
    if (cfg.perception == 0u) { return; }
    for (var x = Jn.exit_start; x < Jn.exit_start + Jn.exit_count; x++) {
        for (var k = 0u; k < K_BOX; k++) {
            let b = cj_box[x * K_BOX + k];
            if (b.stamp != G.step + 1u) { continue; }
            let m = cj_links[b.mov];
            for (var c = m.conf_start; c < m.conf_start + m.conf_count; c++) {
                let cf = cj_conflicts[c];
                if (b.s - cfg.length >= cf.s_out || b.s < cf.s_in - 0.5) { continue; }
                var t_clear = (cf.s_out + cfg.length - b.s) / max(b.v, 0.5);
                // Speeding up out of a slow class it clears sooner than its speed now says.
                let ab = cur[b.veh].acc;
                if (plan_on() && ab > 0.5) { t_clear = (sqrt(b.v * b.v + 2.0 * ab * (cf.s_out + cfg.length - b.s)) - b.v) / ab; }
                yield_foes(j, cf.foe, cf.foe_s_in, t_clear, -INF);
            }
        }
        // A car held up on the exit with its tail still across a conflict is a body in the road too.
        let sim = cj_exits[x].sim_lane;
        if (seg[sim].stamp == G.step) {
            let last = min(seg[sim].first + 3u, seg[sim].end);
            for (var q = seg[sim].first; q < last; q++) {
                let e = cur[q];
                if (e.pos > cfg.length + 1.0 || e.prev_lane == NONE) { continue; }
                let mi = cj_lane_info[e.prev_lane].box_mov;
                if (mi == NONE || cj_links[mi].to_lane != x) { continue; }
                let m = cj_links[mi];
                let s_tail = m.path_len + e.pos;
                for (var c = m.conf_start; c < m.conf_start + m.conf_count; c++) {
                    let cf = cj_conflicts[c];
                    if (s_tail - cfg.length >= cf.s_out) { continue; }
                    var t_tail = (cf.s_out + cfg.length - s_tail) / max(e.speed, 0.5);
                    if (plan_on() && e.acc > 0.5) { t_tail = (sqrt(e.speed * e.speed + 2.0 * e.acc * (cf.s_out + cfg.length - s_tail)) - e.speed) / e.acc; }
                    yield_foes(j, cf.foe, cf.foe_s_in, t_tail, -INF);
                }
            }
        }
    }
    // A car that has missed its slot and can no longer stop will enter anyway, later than reserved.
    for (var a = Jn.app_start; a < Jn.app_start + Jn.app_count; a++) {
        let sim = cj_apps[a].sim_lane;
        if (seg[sim].stamp != G.step) { continue; }
        let first = seg[sim].first;
        var idx = seg[sim].end;
        for (var n = 0u; n < 3u && idx > first; n++) {
            idx -= 1u;
            let e = cur[idx];
            if ((e.cj_state & CJ_STATE_MASK) != CJ_FIRM || (e.cj_state & CJ_LATE) == 0u) { continue; }
            let m = cj_links[e.cj_link];
            let s = e.pos - cj_apps[a].length;
            let v = max(e.speed, 0.5);
            for (var c = m.conf_start; c < m.conf_start + m.conf_count; c++) {
                let cf = cj_conflicts[c];
                yield_foes(j, cf.foe, cf.foe_s_in, (cf.s_out + cfg.length - s) / v, (cf.s_in - s) / v);
            }
        }
    }
}

// ---------------------------------------------------------------- stage 4: vehicle control

// At the point of no return: the last car past the box brakes comfortably and everyone committed
// before us stacks behind it. Our rear must still clear the box.
fn exit_clear_now(x: u32, armed_count: u32) -> bool {
    let sim = cj_exits[x].sim_lane;
    let ahead = armed_count + atomicLoad(&cj_exits[x].n_box);
    if (seg[sim].stamp != G.step) {
        return f32(ahead + 1u) * cfg.unit <= cj_exits[x].length;
    }
    let tail = cur[seg[sim].first];
    let xt = tail.pos - types[tail.vtype].length;
    let have = xt + tail.speed * tail.speed / (2.0 * cfg.b_plan) - f32(ahead) * cfg.unit;
    return have >= cfg.unit;
}

@compute @workgroup_size(64)
fn cj_apply(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    var e = cur[i];
    if ((e.flags & F_REMOVED) != 0u || e.lane == P.dummy_lane || !cj_controlled(e)) { return; }
    let info = cj_lane_info[e.lane];
    ty = types[e.vtype];
    dt = P.dt;
    now = f32(G.step) * dt;
    now_ms = G.step * cfg.dt_ms;
    let v = e.speed;
    let len = lanes[e.lane].length;
    let a_max = cfg.accel;
    var planned = (cfg.plan & PLAN_PROFILE) != 0u;
    // Time to its slot, in the car's own clock.
    var t_left = select(e.cj_t_line - now, ms_rel(e.cj_t_ms), plan_on());
    if (cfg.clock_err > 0.0) { t_left += cfg.clock_err * car_normal(e.trip, 2u); }
    let bp = cfg.b_plan;
    var state = e.cj_state & CJ_STATE_MASK;
    var mi = NONE;
    var vcap = lanes[e.lane].speed;
    var s = e.pos - len;
    let in_box = info.box_mov != NONE;
    var d = len - e.pos;
    if (cfg.pos_err > 0.0) { d = max(d + cfg.pos_err * car_normal(e.trip, 1u), 0.0); }
    var has_line = false;
    let replica = e.replica;
    if (in_box) {
        mi = info.box_mov;
        vcap = cj_links[mi].v_turn;
        s = info.s_offset + e.pos;
        if (planned && s >= cj_links[mi].s_free) { vcap = max(vcap, cj_links[mi].v_after); }
    } else if (info.app != NONE) {
        if (state == CJ_FIRM || state == CJ_PENDING) {
            mi = e.cj_link;
            has_line = true;
        } else if (e.route_i + 1u < e.route_end) {
            has_line = true;
            let k = pick_link(e.lane, e.route_i, e.route_end);
            if (k != NONE) {
                mi = cj_apps[info.app].mov_start + (k - lanes[e.lane].links_start);
                if (e.cj_link != mi) {
                    // The car changed lanes or plans: old advice is void.
                    if (state == CJ_ADVISED) {
                        state = CJ_NONE;
                        e.cj_state = (e.cj_state & CJ_KEEP) | CJ_NONE;
                        cur[i].cj_rank = NONE;
                    }
                }
            }
            e.cj_link = mi;
        } else {
            e.cj_link = NONE;
        }
    } else {
        e.cj_link = NONE;
    }
    // A junction on today's horizon has its cars on today's control.
    if (planned && !in_box && mi != NONE && cj_junctions[cj_links[mi].junction].fallback != 0u) {
        planned = false;
        t_left = e.cj_t_line - now;
    }
    // Stop curve margin in the auditor's words: nobody without a grant may be unable to stop.
    var yield_at = e.cj_yield;
    e.cj_yield = INF;
    var hold_at = e.cj_hold;
    e.cj_hold = INF;
    var replica_p = 0.0;
    if (mi != NONE) { replica_p = cj_junctions[cj_links[mi].junction].p_load; }

    // The grant arrives, or does not.
    if (state == CJ_PENDING && delivered(e.trip, 2u, d, replica_p, replica)) {
        let k = (e.cj_state >> CJ_K_SHIFT) & 7u;
        let ve = cj_mov_k[mi * N_CLASS + k].vk;
        let te = earliest(max(d, 0.0), v, ve, lanes[e.lane].speed, a_max, bp);
        let tl = latest(max(d, 0.0), v, ve, a_max, bp);
        if (te >= 0.0 && tl >= 0.0 && te <= t_left + 0.15 && t_left <= tl) {
            state = CJ_FIRM;
            e.cj_state = (e.cj_state & ~CJ_STATE_MASK) | CJ_FIRM;
        } else {
            cur[i].cj_state = e.cj_state;
            abort_grant(i, mi, replica);
            e.cj_state = cur[i].cj_state;
            state = CJ_NONE;
        }
    }

    // A firm car that can no longer make its slot and can still stop gives it up.
    if (state == CJ_FIRM && (G.step & 1u) == 0u) {
        let tg = t_left;
        if (tg <= 6.0) {
            let stop_d = v * cfg.t_r + v * v / (2.0 * cfg.b_s);
            let x = cj_links[mi].to_lane;
            var dropped = false;
            if (cfg.ponr != 0u && (e.cj_state & CJ_ARMED) == 0u && d <= stop_d + 2.0) {
                let a = atomicAdd(&cj_exits[x].n_armed, 1u);
                if (exit_clear_now(x, a)) {
                    e.cj_state |= CJ_ARMED;
                } else {
                    atomicSub(&cj_exits[x].n_armed, 1u);
                    if (d >= stop_d + 0.5) {
                        cur[i].cj_state = e.cj_state;
                        abort_grant(i, mi, replica);
                        e.cj_state = cur[i].cj_state;
                        state = CJ_NONE;
                        dropped = true;
                        if (now >= cfg.warm) { stat(replica, S_PONR_ABORT, 1u); }
                    }
                }
            }
            if (!dropped) {
                let ve = e.cj_v_line;
                var te = earliest(max(d, 0.0), v, ve, lanes[e.lane].speed, a_max, bp);
                if (te < 0.0) {
                    te = select(0.0, d / max(v, 0.5), d > 1.0);
                    // Short of the class speed, but with the engine flat out it may still be on time.
                    if (planned && ve > v) { te = (sqrt(v * v + 2.0 * a_max * max(d, 0.0)) - v) / a_max; }
                }
                if (te > tg + dt + 0.15) {
                    if (d >= stop_d + 0.5) {
                        cur[i].cj_state = e.cj_state;
                        abort_grant(i, mi, replica);
                        e.cj_state = cur[i].cj_state;
                        state = CJ_NONE;
                        if (now >= cfg.warm) { stat(replica, S_LATE, 1u); }
                    } else if ((e.cj_state & CJ_LATE) == 0u) {
                        e.cj_state |= CJ_LATE;
                        if (now >= cfg.warm) { stat(replica, S_LATE_COMMITTED, 1u); }
                    }
                }
            }
        }
    }

    // Longitudinal command, as the reference model.
    var a_cmd = min((vcap - v) / dt, a_max);
    a_cmd = max(a_cmd, -bp);
    // Planned control has a soft part, comfort and jerk limited, and a hard part: safety, which is not.
    var a_hard = 1e9;
    var a_stopc = 1e9;
    var a_lead = 1e9;
    var a_y = 1e9;
    var a_h = 1e9;
    var a_track = 1e9;
    if (planned) { a_cmd = clamp((vcap - v) / 0.5, -cfg.plan_bc, a_max); }
    let ungranted = !in_box && has_line && state != CJ_FIRM;
    if (ungranted) {
        let vs = av_stop_curve(d, cfg.b_plan, cfg.t_r);
        a_stopc = clamp((vs - v) / dt, -cfg.b_s, a_max);
        if (planned) { a_hard = a_stopc; } else { a_cmd = min(a_cmd, a_stopc); }
    }
    // The car can see for itself that its plan has gone quiet: then it keeps going, as today, on its stop curve.
    let stale = state == CJ_ADVISED && i32(now_ms - e.cj_rx_ms) > STALE_MS;
    if (planned && !in_box && (state == CJ_ADVISED || state == CJ_FIRM || state == CJ_PENDING) && !stale) {
        let di = max(d, 0.0);
        e.cj_v_cruise = di / max(t_left, 0.1);
        // A firm slot is a promise about conflicts: keep it even past comfort, and count that.
        let promise = state == CJ_FIRM || state == CJ_PENDING;
        plan_wait = 0.0;
        if (mi != NONE) { plan_wait = plan_delay(e.cj_zone_t, t_left, mi); }
        a_track = plan_accel(di, v, t_left, e.cj_v_line, vcap, select(cfg.plan_bc, cfg.b_s, promise));
        a_cmd = min(a_cmd, a_track);
        if (state == CJ_FIRM && t_left < 0.0) { a_cmd = min((vcap - v) / dt, a_max); }
        // Never well ahead of the slot; the conflict margin covers a little.
        // A car creeping up to the line a moment early is not ahead of anything: stopping it there makes
        // it late. Well early, it waits at the line: even at walking pace it would be in the way.
        let early = t_left - di / max(v, 0.5);
        if (promise && di < 8.0 && (((v > 0.8 || !plan_route()) && early > 0.25) || early > 0.6)) {
            a_hard = min(a_hard, max((di / t_left - v) / dt, -cfg.b_s));
        }
    } else if (!planned && !in_box && (state == CJ_ADVISED || state == CJ_FIRM || state == CJ_PENDING)) {
        if ((G.step & 1u) == 0u) {
            e.cj_v_cruise = plan_vc(v, max(d, 0.0), max(e.cj_t_line - now, 0.01), e.cj_v_line, vcap);
        }
        let di = max(d, 0.0);
        let ve = e.cj_v_line;
        let rate = select(bp, a_max, ve > v);
        let d3 = abs(ve * ve - v * v) / (2.0 * rate);
        let t3 = abs(ve - v) / rate;
        let close = di <= d3 + v * dt;
        let go = close && (ve < v || e.cj_t_line - now <= t3 + 0.2);
        var aim = e.cj_v_cruise;
        if (go) { aim = ve; } else if (close) { aim = min(v, e.cj_v_cruise); }
        a_cmd = min(a_cmd, clamp((aim - v) / dt, -cfg.b_s, a_max));
        if (state == CJ_FIRM) {
            let tg = e.cj_t_line - now;
            // Never well ahead of the slot.
            if (tg > 0.3 && di < 8.0 && v > 1.5 * di / max(tg, 0.3)) {
                a_cmd = min(a_cmd, (1.5 * di / max(tg, 0.3) - v) / dt);
            }
            if (tg < 0.0) { a_cmd = min((vcap - v) / dt, a_max); }
        }
    }

    // Car following on the lane order.
    var has_leader = false;
    var gap = 0.0;
    var vl = 0.0;
    var lead_i = NONE;
    var lead_rem = 0.0;
    var lead_a = 0.0;
    if (in_box) {
        let m = cj_links[mi];
        let x = m.to_lane;
        var best = NONE;
        var best_seq = 0u;
        for (var k = 0u; k < K_BOX; k++) {
            let b = cj_box[x * K_BOX + k];
            if (b.stamp == G.step + 1u && b.seq < e.cj_seq && (best == NONE || b.seq > best_seq)) {
                best = k;
                best_seq = b.seq;
            }
        }
        let xf = s - m.path_len;
        if (best != NONE) {
            let b = cj_box[x * K_BOX + best];
            has_leader = true;
            gap = b.s - cj_links[b.mov].path_len - xf - cfg.length;
            vl = b.v;
            lead_rem = max(cj_links[b.mov].path_len - b.s, 0.0);
        } else {
            let sim = cj_exits[x].sim_lane;
            if (seg[sim].stamp == G.step) {
                let t = cur[seg[sim].first];
                has_leader = true;
                gap = t.pos - xf - types[t.vtype].length;
                vl = t.speed;
                lead_a = t.acc;
            }
        }
    } else if (i + 1u < G.n_active && cur[i + 1u].lane == e.lane && (cur[i + 1u].flags & F_REMOVED) == 0u) {
        let t = cur[i + 1u];
        has_leader = true;
        gap = t.pos - types[t.vtype].length - e.pos;
        vl = t.speed;
        lead_i = i + 1u;
    } else if (info.app != NONE) {
        let p = atomicLoad(&cj_apps[info.app].box_tail);
        if (p != NONE) {
            has_leader = true;
            gap = f32(p >> 16u) / 8.0 - 500.0 + d;
            vl = f32(p & 0xffffu) / 256.0;
            let pm = atomicLoad(&cj_apps[info.app].box_tail_m);
            if (pm != NONE) { lead_rem = max(cj_links[pm & 0xffffu].path_len - (f32(pm >> 16u) / 8.0 - 500.0) - cfg.length, 0.0); }
        }
    }
    if (has_leader) {
        let vsafe = av_safe_speed(gap, vl, cfg.b_s, cfg.t_r, cfg.s0);
        let asafe = (vsafe - v) / dt;
        let acf = 0.3 * (gap - cfg.s0 - v * cfg.tau) + 0.8 * (vl - v);
        a_lead = asafe;
        if (planned) {
            a_hard = min(a_hard, asafe);
            // A firm car behind its leader has the headway table on its side, as in the baseline.
            let tight = state == CJ_FIRM || in_box;
            if (tight) {
            } else if ((cfg.plan & PLAN_FOLLOW) != 0u) {
                // The leader says where it will be, so slow now for what it plans, not for what it did.
                let vm = lanes[e.lane].speed;
                plan_vmax = vm;
                var x1 = lead_x(vl, lead_rem, lead_a, vm, 1.0);
                var x2 = lead_x(vl, lead_rem, lead_a, vm, 2.0);
                var x4 = lead_x(vl, lead_rem, lead_a, vm, 4.0);
                if (lead_i != NONE && info.app != NONE) {
                    let t = cur[lead_i];
                    let sl = t.cj_state & CJ_STATE_MASK;
                    if ((sl == CJ_ADVISED && i32(now_ms - t.cj_rx_ms) <= STALE_MS) || sl == CJ_FIRM || sl == CJ_PENDING) {
                        let dl = len - t.pos;
                        let tl = select(t.cj_t_line - now, ms_rel(t.cj_t_ms), plan_on());
                        x1 = plan_x(dl, t.speed, tl, t.cj_v_line, t.acc, 1.0);
                        x2 = plan_x(dl, t.speed, tl, t.cj_v_line, t.acc, 2.0);
                        x4 = plan_x(dl, t.speed, tl, t.cj_v_line, t.acc, 4.0);
                    } else {
                        x1 = plan_x(0.0, t.speed, 0.0, 0.0, t.acc, 1.0);
                        x2 = plan_x(0.0, t.speed, 0.0, 0.0, t.acc, 2.0);
                        x4 = plan_x(0.0, t.speed, 0.0, 0.0, t.acc, 4.0);
                    }
                }
                let u = behind(gap, v, x1, x2, x4, cfg.tau);
                a_cmd = min(a_cmd, max(u, -cfg.plan_bc));
            } else {
                a_cmd = min(a_cmd, max(acf, -cfg.plan_bc));
            }
        } else if (state == CJ_FIRM || in_box) {
            a_cmd = min(a_cmd, asafe);
        } else {
            a_cmd = min(a_cmd, min(acf, asafe));
        }
    }
    if (planned) {
        // Close to a firm slot, hitting it matters more than the last of the jerk limit.
        let near = !in_box && state == CJ_FIRM && t_left <= 3.0;
        let jd = select(cfg.plan_j, 5.0, near);
        // Letting off the brake needs no limit worth the time it costs.
        a_cmd = clamp(a_cmd, e.acc - jd * dt, e.acc + select(2.5 * cfg.plan_j, 20.0, e.acc < -1.0) * dt);
        // Ease off in time, so the jerk limit does not carry the car over the speed limit.
        if (a_cmd > 0.0) { a_cmd = min(a_cmd, sqrt(2.0 * jd * max(vcap - v, 0.0))); }
        if (a_track < -cfg.plan_bc) { a_cmd = min(a_cmd, a_track + 0.5); }
        a_cmd = min(a_cmd, a_hard);
    }

    // The far end of a closed or metered lane.
    if (info.exit != NONE && e.route_i + 1u >= e.route_end && !in_box) {
        let x = info.exit;
        let head = !(i + 1u < G.n_active && cur[i + 1u].lane == e.lane);
        if (head && now >= cj_exits[x].block_t0 && now < cj_exits[x].block_t1) {
            let interval = cj_exits[x].cap_interval;
            var closed = interval <= 0.0;
            if (interval > 0.0) {
                closed = now < cj_exits[x].sink_ready;
                if (!closed && len - e.pos <= 0.5 + v * dt) { cj_exits[x].sink_ready = now + interval; }
            }
            if (closed) {
                let dd = max(len - e.pos - 0.6, 0.05);
                if (v > 0.05) { a_cmd = min(a_cmd, -v * v / (2.0 * dd)); } else if (dd < 1.0) { a_cmd = 0.0; }
            }
        }
    }
    if (hold_at < 1e29) {
        let dd = max(hold_at - s - 0.3, 0.05);
        if (v > 0.05) { a_h = -v * v / (2.0 * dd); a_cmd = min(a_cmd, a_h); } else if (dd < 1.0) { a_cmd = min(a_cmd, 0.0); }
        if (now >= cfg.warm) { stat(replica, S_HOLDS, 1u); }
    }
    if (yield_at < 1e29) {
        let dd = max(yield_at - s, 0.05);
        a_y = -v * v / (2.0 * dd);
        a_cmd = min(a_cmd, a_y);
        if (now >= cfg.warm) { stat(replica, S_YIELDS, 1u); }
    }
    if ((e.cj_state & CJ_STALLED) != 0u) { a_cmd = -cfg.b_e; }
    a_cmd = max(a_cmd, -cfg.b_e);
    let vn = max(v + a_cmd * dt, 0.0);
    e.cj_v_cmd = vn;

    // A hard brake, once per episode, by whatever asked for it. Braking is a measured failure.
    if (a_cmd < -cfg.b_plan - 0.01 && (e.cj_state & CJ_HARD) == 0u) {
        e.cj_state |= CJ_HARD;
        if (now >= cfg.warm) {
            var cause = S_HARD_PLAN;
            if ((e.cj_state & CJ_STALLED) != 0u) { cause = S_HARD_STALL; }
            else if (a_y <= a_cmd + 0.01) { cause = S_HARD_YIELD; }
            else if (a_h <= a_cmd + 0.01) { cause = S_HARD_HOLD; }
            else if (a_lead <= a_cmd + 0.01) { cause = S_HARD_LEADER; }
            else if (a_stopc <= a_cmd + 0.01) { cause = S_HARD_STOP_CURVE; }
            stat(replica, cause, 1u);
        }
    } else if (a_cmd > -1.0) {
        e.cj_state &= ~CJ_HARD;
    }

    // Metrics.
    if (now >= cfg.warm) {
        if (vn < v) {
            stat(replica, S_SPEED_LOST, u32((v - vn) * 1000.0));
            stat(replica, S_KE_LOST, u32((v * v - vn * vn) * 100.0));
        }
        stat(replica, S_LOSS, u32(256.0 * (1.0 - min(vn / max(vcap, 1.0), 1.0))));
        stat(replica, S_A2, u32(min(a_cmd * a_cmd, 64.0) * 256.0));
        stat(replica, S_A2N, 1u);
        if ((e.cj_state & CJ_WAS_MOVING) != 0u && vn < 0.5) { stat(replica, S_STOPS, 1u); }
        if (in_box && vn < 0.5 && (e.cj_state & CJ_STALLED) == 0u) { stat(replica, S_BOX_BLOCK, 1u); }
        if (state == CJ_ADVISED) { stat(replica, S_ADVISED_STEPS, 1u); }
        if (state == CJ_FIRM) { stat(replica, S_FIRM_STEPS, 1u); }
        // Invariant: without a grant a car can always stop before the line.
        if (ungranted) {
            let need = vn * cfg.t_r + vn * vn / (2.0 * cfg.b_s);
            if (d - vn * dt < need - 0.5 && vn > 0.1) { stat(replica, S_STOP_CURVE, 1u); }
        }
    }
    if (vn > 2.0) { e.cj_state |= CJ_WAS_MOVING; } else if (vn < 0.5) { e.cj_state &= ~CJ_WAS_MOVING; }
    cur[i].cj_state = e.cj_state;
    cur[i].cj_v_cruise = e.cj_v_cruise;
    cur[i].cj_link = e.cj_link;
    cur[i].cj_v_cmd = e.cj_v_cmd;
    cur[i].cj_yield = e.cj_yield;
    cur[i].cj_hold = e.cj_hold;
}
