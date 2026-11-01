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

const K_LANE: u32 = 6u;
const K_BOX: u32 = 16u;
const N_CLASS: u32 = 6u;
const PLAN_MAX: u32 = 32u;
const AUD_MAX: u32 = 32u;
const STATS_PER_REPLICA: u32 = 32u;
const EVENTS_MAX: u32 = 4095u;
const INF: f32 = 1e30;
const HEARD_NOTHING: f32 = 20.0;

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

const CAND_STALE: u32 = 0u;
const CAND_OK: u32 = 1u;
const CAND_NONE: u32 = 2u;

var<private> now: f32;
var<private> cand_t: f32;
var<private> cand_k: u32;

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
    let a = cfg.accel;
    let b = cfg.b_plan;
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
                let err = now - e.cj_t_line;
                if (now >= cfg.warm) {
                    stat(e.replica, S_ERR_ABS, u32(abs(err) * 1000.0));
                    stat(e.replica, S_ERR_N, 1u);
                    if (abs(err) > 0.15) { stat(e.replica, S_ERR_BIG, 1u); }
                }
            }
            st = (e.cj_state & CJ_KEEP) | CJ_BOX;
            cur[i].cj_state = st;
            cur[i].cj_link = mi;
            // A stalled record keeps its end time in cj_t_line.
        }
        atomicAdd(&cj_exits[x].n_box, 1u);
        atomicMin(&cj_apps[m.from_lane].box_tail, pack_box(s - cfg.length, e.speed));
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
    }
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
    if (seg[sim].stamp == G.step) {
        let first = seg[sim].first;
        let len = cj_apps[a].length;
        var idx = seg[sim].end;
        loop {
            if (idx <= first || n >= K_LANE) { break; }
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
            cj_req[cj_apps[a].req_start + n] = q;
            n += 1u;
        }
    }
    cj_apps[a].n_req = n;
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
    if (J.mode != MODE_FREE || J.frozen != 0u || !coordinator_up()) { return; }
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

// ---------------------------------------------------------------- stage 3: commit, durable before visible

fn commit_real(j: u32, q: CjReq, mi: u32, k: u32, t: f32, deliver_now: bool) {
    let m = cj_links[mi];
    for (var c = 0u; c < m.conf_count; c++) {
        let ci = m.conf_start + c;
        let rv = cj_conflicts[ci].rev_index;
        cj_rel[rv] = max(cj_rel[rv], t + cj_times[ci * 12u + 6u + k]);
    }
    cj_apps[m.from_lane].line_ref = mi * N_CLASS + k;
    cj_apps[m.from_lane].line_t = t;
    cj_exits[m.to_lane].exit_ref = mi * N_CLASS + k;
    cj_exits[m.to_lane].exit_t = t;
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
fn yield_foes(j: u32, f: u32, foe_in: f32, t_clear: f32) {
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
            if (t_clear > to_conf / vq - 0.1 && to_conf >= e.speed * cfg.t_r + e.speed * e.speed / (2.0 * cfg.b_e)) {
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
        if (t_clear > to_conf / vq - 0.1 && to_conf >= b.v * cfg.t_r + b.v * b.v / (2.0 * cfg.b_e)) {
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
                let t_clear = (cf.s_out + cfg.length - b.s) / max(b.v, 0.5);
                yield_foes(j, cf.foe, cf.foe_s_in, t_clear);
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
    let v = e.speed;
    let len = lanes[e.lane].length;
    let a_max = cfg.accel;
    let bp = cfg.b_plan;
    var state = e.cj_state & CJ_STATE_MASK;
    var mi = NONE;
    var vcap = lanes[e.lane].speed;
    var s = e.pos - len;
    let in_box = info.box_mov != NONE;
    var d = len - e.pos;
    var has_line = false;
    let replica = e.replica;
    if (in_box) {
        mi = info.box_mov;
        vcap = cj_links[mi].v_turn;
        s = info.s_offset + e.pos;
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
        if (te >= 0.0 && tl >= 0.0 && now + te <= e.cj_t_line + 0.15 && e.cj_t_line - now <= tl) {
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
        let tg = e.cj_t_line - now;
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
                if (te < 0.0) { te = select(0.0, d / max(v, 0.5), d > 1.0); }
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
    let ungranted = !in_box && has_line && state != CJ_FIRM;
    if (ungranted) {
        let vs = av_stop_curve(d, cfg.b_plan, cfg.t_r);
        a_cmd = min(a_cmd, clamp((vs - v) / dt, -cfg.b_s, a_max));
    }
    if (!in_box && (state == CJ_ADVISED || state == CJ_FIRM || state == CJ_PENDING)) {
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
        } else {
            let sim = cj_exits[x].sim_lane;
            if (seg[sim].stamp == G.step) {
                let t = cur[seg[sim].first];
                has_leader = true;
                gap = t.pos - xf - types[t.vtype].length;
                vl = t.speed;
            }
        }
    } else if (i + 1u < G.n_active && cur[i + 1u].lane == e.lane && (cur[i + 1u].flags & F_REMOVED) == 0u) {
        let t = cur[i + 1u];
        has_leader = true;
        gap = t.pos - types[t.vtype].length - e.pos;
        vl = t.speed;
    } else if (info.app != NONE) {
        let p = atomicLoad(&cj_apps[info.app].box_tail);
        if (p != NONE) {
            has_leader = true;
            gap = f32(p >> 16u) / 8.0 - 500.0 + d;
            vl = f32(p & 0xffffu) / 256.0;
        }
    }
    if (has_leader) {
        let vsafe = av_safe_speed(gap, vl, cfg.b_s, cfg.t_r, cfg.s0);
        let asafe = (vsafe - v) / dt;
        let acf = 0.3 * (gap - cfg.s0 - v * cfg.tau) + 0.8 * (vl - v);
        if (state == CJ_FIRM || in_box) {
            a_cmd = min(a_cmd, asafe);
        } else {
            a_cmd = min(a_cmd, min(acf, asafe));
        }
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
        if (v > 0.05) { a_cmd = min(a_cmd, -v * v / (2.0 * dd)); } else if (dd < 1.0) { a_cmd = min(a_cmd, 0.0); }
        if (now >= cfg.warm) { stat(replica, S_HOLDS, 1u); }
    }
    if (yield_at < 1e29) {
        let dd = max(yield_at - s, 0.05);
        a_cmd = min(a_cmd, -v * v / (2.0 * dd));
        if (now >= cfg.warm) { stat(replica, S_YIELDS, 1u); }
    }
    if ((e.cj_state & CJ_STALLED) != 0u) { a_cmd = -cfg.b_e; }
    a_cmd = max(a_cmd, -cfg.b_e);
    let vn = max(v + a_cmd * dt, 0.0);
    e.cj_v_cmd = vn;

    // Metrics.
    if (now >= cfg.warm) {
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
