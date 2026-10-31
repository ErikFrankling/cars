// LC2013 discrete motivations, after MSLCM_LC2013::_wantsChange. Every vehicle decides at once from
// the positions after movement; reservations then pick one winner per gap.
// Omitted: sublanes and lateral dynamics, opposite driving, pedestrians, stops, the roundabout
// bonus, overtake-right avoidance on fast roads and TraCI. Messages to neighbours arrive one step
// later than in SUMO's sequential sweep.

const LCA_LEFT: u32 = 1u;
const LCA_RIGHT: u32 = 2u;
const LCA_STRATEGIC: u32 = 4u;
const LCA_COOPERATIVE: u32 = 8u;
const LCA_SPEEDGAIN: u32 = 16u;
const LCA_KEEPRIGHT: u32 = 32u;
const LCA_URGENT: u32 = 64u;
const LCA_BLOCK_LEADER: u32 = 128u;
const LCA_BLOCK_FOLLOWER: u32 = 256u;
const LCA_AM_LEADER: u32 = 512u;
const LCA_AM_FOLLOWER: u32 = 1024u;
const LCA_M_LEFT: u32 = 2048u;
const LCA_M_RIGHT: u32 = 4096u;
const LCA_STAY: u32 = 8192u;
const LCA_DONT_BRAKE: u32 = 16384u;
const LCA_WANTS: u32 = LCA_LEFT | LCA_RIGHT;
const HELP_OVERTAKE: f32 = 10.0 / 3.6;
const MIN_FALLBEHIND: f32 = 0.5;
const TURN_LANE_DIST: f32 = 200.0;

@compute @workgroup_size(64)
fn lc_best(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let e = cur[i];
    if ((e.flags & (F_BEST_DIRTY | F_REMOVED)) != F_BEST_DIRTY || is_internal(e.lane)) { return; }
    ty = types[e.vtype];
    dt = P.dt;
    let ed = edges[lanes[e.lane].edge];
    if (ed.lane_count > 16u) { return; }
    var a: array<f32, 16>;
    var b: array<f32, 16>;
    var off: array<i32, 16>;
    var next_off: array<i32, 16>;
    var stop = e.route_i;
    var seen = 0.0;
    let brake = lanes[e.lane].length + brake_gap(ty.max_speed, ty.decel, ty.tau) + ty.min_gap;
    loop {
        seen += edges[routes[stop]].length;
        stop += 1u;
        let n = stop - e.route_i;
        if (stop >= e.route_end || ((n > 4u && seen >= max(brake, 3000.0)) || (n > 8u && seen >= max(brake, 200.0)))) { break; }
    }
    var ri = stop;
    loop {
        ri -= 1u;
        let edge = edges[routes[ri]];
        let count = min(edge.lane_count, 16u);
        var best = 0.0;
        var best_offset = 1000;
        var next_best = 0.0;
        if (ri + 1u < stop) {
            let ne = edges[routes[ri + 1u]];
            for (var k = 0u; k < min(ne.lane_count, 16u); k++) { next_best = max(next_best, b[k]); }
        }
        for (var k = 0u; k < count; k++) {
            let l = lanes[edge.first_lane + k];
            a[k] = 0.0;
            off[k] = 0;
            if ((l.allow & ty.vclass) != ty.vclass) { continue; }
            a[k] = l.length;
            if (ri + 1u < stop) {
                var cont = 0.0;
                var co = 1000;
                for (var j = 0u; j < l.links_count; j++) {
                    let lk = links[l.links_start + j];
                    if (lk.to_edge != routes[ri + 1u] || (lanes[lk.to_lane].allow & ty.vclass) != ty.vclass) { continue; }
                    let nk = min(lanes[lk.to_lane].index, 15u);
                    if (b[nk] > cont || (b[nk] == cont && abs(next_off[nk]) < abs(co))) {
                        cont = b[nk]; co = next_off[nk];
                    }
                }
                if (cont > 0.0) {
                    if (abs(co) < 2 && cont == next_best) { cont = next_best; }
                    a[k] += cont; off[k] = co;
                }
            }
            if (a[k] > best || (a[k] == best && abs(off[k]) < abs(best_offset))) {
                best = a[k]; best_offset = off[k];
            }
        }
        for (var k = 0u; k < count; k++) {
            var nearest = 1000;
            for (var j = 0u; j < count; j++) {
                if (a[j] == best && abs(off[j]) == abs(best_offset) && abs(i32(j) - i32(k)) < abs(nearest)) { nearest = i32(j) - i32(k); }
            }
            b[k] = a[k];
            next_off[k] = 0;
            if (a[k] < best || abs(off[k]) > abs(best_offset)) { next_off[k] = nearest; }
        }
        if (ri == e.route_i) { break; }
    }
    let k = lanes[e.lane].index;
    cur[i].best_cur = b[k];
    cur[i].best_left = 0.0;
    cur[i].best_right = 0.0;
    var packed = next_off[k] & 255;
    if (k + 1u < ed.lane_count) {
        cur[i].best_left = b[k + 1u];
        if (next_off[k + 1u] == 0) { packed |= 256; }
    }
    if (k > 0u) {
        cur[i].best_right = b[k - 1u];
        if (next_off[k - 1u] == 0) { packed |= 512; }
    }
    cur[i].best_off = packed;
    cur[i].flags &= ~F_BEST_DIRTY;
}

fn unpack_off(p: i32) -> i32 { return ((p & 255) ^ 128) - 128; }

struct LcNeighbors {
    leader: u32,
    follower: u32,
    gap: f32,        // to the leader, after our minGap. 1e9 when none.
    f_gap: f32,      // from the follower, after its minGap. 1e9 when none.
    speed: f32,
    decel: f32,
    acc: f32,
    f_speed: f32,
    f_vtype: u32,
    f_trip: u32,
    f_acc: f32,
    leader_trip: u32,
    leader_wait: f32,
    leader_len: f32,
}

fn lc_consider_follower(r: ptr<function, LcNeighbors>, k: u32, fp: f32, egoback: f32) {
    let o = cur[k];
    let ot = types[o.vtype];
    let g = egoback - fp - ot.min_gap;
    if (g < (*r).f_gap) {
        (*r).f_gap = g; (*r).follower = k; (*r).f_speed = o.speed; (*r).f_vtype = o.vtype; (*r).f_trip = o.trip; (*r).f_acc = o.acc;
    }
}

// MSLaneChanger::getRealLeader and getRealFollower.
fn lc_neighbors(l: u32, pos: f32, ego: u32, egoback: f32) -> LcNeighbors {
    var r: LcNeighbors;
    r.leader = NONE; r.follower = NONE; r.gap = 1e9; r.f_gap = 1e9; r.decel = ty.apparent;
    r.leader_trip = NONE; r.leader_len = 5.0;
    if (lane_occupied(l)) {
        let s = seg[l];
        var lo = s.first;
        var hi = s.end;
        // Lower bound on position among entries still on this lane. Those that left wrapped around.
        loop {
            if (lo >= hi) { break; }
            let mid = (lo + hi) / 2u;
            var k = mid;
            loop {
                if (k >= hi || (cur[k].lane == l && (cur[k].flags & F_REMOVED) == 0u)) { break; }
                k++;
            }
            if (k == hi) { hi = mid; }
            else if (cur[k].pos < pos) { lo = k + 1u; }
            else { hi = mid; }
        }
        for (var k = lo; k < s.end; k++) {
            let o = cur[k];
            if (k == ego || o.lane != l || (o.flags & F_REMOVED) != 0u) { continue; }
            if (o.pos >= pos) {
                let ot = types[o.vtype];
                r.leader = k; r.gap = o.pos - ot.length - pos - ty.min_gap;
                r.speed = o.speed; r.decel = ot.apparent; r.acc = o.acc; r.leader_trip = o.trip;
                r.leader_wait = o.wait; r.leader_len = ot.length;
                break;
            }
        }
        var k = lo;
        loop {
            if (k == s.first) { break; }
            k--;
            let o = cur[k];
            if (k != ego && o.lane == l && (o.flags & F_REMOVED) == 0u && o.pos < pos) {
                lc_consider_follower(&r, k, o.pos, egoback);
                break;
            }
        }
    }
    let ent = atomicLoad(&entrant[l]);
    if (ent != NONE) {
        let k = ent & 0x3fffffu;
        let o = cur[k];
        if (k != ego && o.lane == l && (o.flags & F_REMOVED) == 0u) {
            let ot = types[o.vtype];
            let g = o.pos - ot.length - pos - ty.min_gap;
            if (o.pos >= pos) {
                if (g < r.gap) {
                    r.leader = k; r.gap = g; r.speed = o.speed; r.decel = ot.apparent; r.acc = o.acc;
                    r.leader_trip = o.trip; r.leader_wait = o.wait; r.leader_len = ot.length;
                }
            } else {
                lc_consider_follower(&r, k, o.pos, egoback);
            }
        }
    }
    // Followers still upstream of this lane, through the connections leading onto it.
    if (r.f_gap > 60.0 && pos < 120.0) {
        let la = lanes[l];
        for (var j = 0u; j < la.in_count; j++) {
            var src = links[incoming_links[la.in_start + j]].from_lane;
            var offset = 0.0;
            for (var level = 0u; level < 2u; level++) {
                let sl = lanes[src];
                if (lane_occupied(src)) {
                    let sg = seg[src];
                    var k = sg.end;
                    loop {
                        if (k == sg.first) { break; }
                        k--;
                        if (k == ego || cur[k].lane != src || (cur[k].flags & F_REMOVED) != 0u) { continue; }
                        lc_consider_follower(&r, k, cur[k].pos - sl.length - offset, egoback);
                        break;
                    }
                }
                if (!is_internal(src) || sl.pred == NONE) { break; }
                offset += sl.length;
                src = sl.pred;
            }
        }
    }
    // A tail hanging onto this lane.
    let p = atomicLoad(&partial_occ[l]);
    if (p != NONE) {
        let g = unpack_back(p) - pos - ty.min_gap;
        if (unpack_back(p) >= pos - 0.1 && g < r.gap) {
            r.gap = g; r.speed = unpack_speed(p); r.leader = NONE; r.leader_trip = NONE; r.acc = 0.0; r.decel = ty.apparent;
        }
    }
    return r;
}

// Leaders past the end of the lane, on the way the vehicle would go from there.
fn lc_leader_ahead(r: ptr<function, LcNeighbors>, l: u32, pos: f32, route_i: u32, route_end: u32, lookahead: f32) {
    if ((*r).gap < 1e8) { return; }
    var ahead = l;
    var seen = lanes[l].length - pos;
    var ri = route_i;
    for (var hop = 0u; hop < 4u; hop++) {
        if (seen > lookahead) { break; }
        let lk = pick_link(ahead, ri, route_end);
        if (lk == NONE) { break; }
        if ((links[lk].flags & L_HAS_VIA) == 0u) { ri += 1u; }
        ahead = links[lk].next_lane;
        let packed = atomicLoad(&tail[ahead]);
        if (packed != NONE) {
            (*r).gap = seen + unpack_back(packed) - ty.min_gap;
            (*r).speed = unpack_speed(packed);
            (*r).decel = ty.apparent;
            return;
        }
        seen += lanes[ahead].length;
    }
}

fn lc_advice(trip: u32, speed: f32) { atomicMin(&advice[trip], u32(max(0.0, speed) * 1024.0)); }

// CF::getSecureGap while changing lanes: a vehicle already braking may need less room.
fn secure_gap_lc(v: f32, vl: f32, bl: f32, acc: f32, safety: f32, leader_cacc: bool) -> f32 {
    var g: f32;
    switch ty.model {
        case MODEL_IDM: { g = idm_secure_gap(v, vl); }
        case MODEL_ACC: { g = 0.07 * (v - vl) / 0.23 + ty.tau * v; }
        case MODEL_CACC: {
            var want = ty.tau * v;
            if (!leader_cacc) { want = 0.07 * (v - vl) / 0.23 + ty.headway_acc * v; }
            let bg = brake_gap(vl, max(ty.decel, bl), 0.0);
            g = max(want, max(0.0, brake_gap(v, ty.decel, ty.tau) - bg));
        }
        default: {
            let bg = brake_gap(vl, max(ty.decel, bl), 0.0);
            g = max(0.0, brake_gap(v, ty.decel, ty.tau) - bg);
            if (acc < -EPS) {
                let sd = max(0.0, brake_gap(v, min(-acc, ty.decel), 0.0) - bg);
                g = min(g, sd / safety);
            }
        }
    }
    return g;
}

fn anticipate(gap: f32, has_leader: bool, dist: f32, vmax: f32, limit: f32, v: f32, ls: f32, lb: f32, accelerating: bool) -> f32 {
    var future: f32;
    if (accelerating) {
        let v1 = v + ty.accel - ty.accel * dt;
        if (!has_leader) {
            future = follow_speed(v1, dist, 0.0, ty.decel, false, vmax, limit);
        } else {
            future = follow_speed(v1, gap, ls, lb, false, vmax, limit);
        }
    } else {
        if (!has_leader) {
            future = safe_stop(dist, ty.decel, v, ty.tau, true);
        } else {
            future = safe_follow(gap, v, ls, lb, true);
        }
    }
    return min(vmax, future);
}

// State the kernel builds up for one vehicle.
var<private> lc_pr: f32;
var<private> lc_pl: f32;
var<private> lc_pk: f32;
var<private> lc_own: u32;
var<private> lc_left_space: f32;
var<private> lc_blocker: f32;
var<private> lc_look: f32;

fn inform_leader(e: Veh, n: LcNeighbors, blocked: u32, dir: u32, remaining: f32, vmax: f32, limit: f32) -> f32 {
    var planned = e.speed;
    planned = min(planned, stop_speed(e.speed, lc_left_space - lc_blocker, ty.decel, true, vmax));
    if (n.leader == NONE && n.gap > 1e8) { return planned; }
    let nv_next = n.speed - max(1.0, -n.acc) * dt;
    let next_gap = n.gap + (nv_next - planned) * dt;
    if ((blocked & LCA_BLOCK_LEADER) != 0u) {
        // overtakeDistance: drive past the leader and leave a secure gap ahead of it.
        let dv = planned - n.speed;
        let over = max(0.0, n.gap + n.leader_len + ty.min_gap + ty.length);
        var ot: f32;
        if (dv > 0.0) { ot = over / dv; }
        else if (n.leader_wait > 20.0 && ty.length + ty.min_gap + n.leader_len + ty.min_gap <= lc_left_space) { ot = remaining - 1.0; }
        else { ot = remaining + 1.0; }
        let fall_behind = dv < 0.0
            || lc_left_space - lc_blocker - brake_gap(e.speed, ty.decel, ty.tau) < over
            || remaining < ot;
        if (fall_behind) {
            if (n.leader_trip != NONE) { atomicOr(&adv_flags[n.leader_trip], dir | LCA_AM_LEADER); }
            let tgt = max(max(min_next_speed(e.speed), follow_speed(e.speed, next_gap, nv_next, n.decel, false, vmax, limit)), 0.0);
            if (tgt < e.speed) {
                var decel = ty.decel;
                if (remaining != 0.0) { decel = min(ty.decel, max(MIN_FALLBEHIND, (e.speed - tgt) / remaining)); }
                let next = min(planned, max(0.0, e.speed - decel * dt));
                lc_advice(e.trip, next);
                return next;
            }
            lc_advice(e.trip, tgt);
            return planned;
        }
        // Overtake: ask the leader to hold its speed.
        if (n.leader_trip != NONE && n.leader_wait <= 20.0) {
            lc_advice(n.leader_trip, n.speed);
            atomicOr(&adv_flags[n.leader_trip], dir | LCA_AM_LEADER);
        }
        return -1.0;
    }
    let tgt2 = max(min_next_speed(e.speed), follow_speed(e.speed, next_gap, nv_next, n.decel, false, vmax, limit));
    lc_advice(e.trip, tgt2);
    return min(tgt2, planned);
}

fn inform_follower(e: Veh, n: LcNeighbors, blocked: u32, dir: u32, remaining: f32, planned_in: f32) {
    if (n.follower == NONE) { return; }
    let self_ty = ty;
    let planned = max(planned_in, 0.0);
    let ft = types[n.f_vtype];
    let f_trip = n.f_trip;
    let v = n.f_speed;
    let gap = n.f_gap;
    if ((blocked & LCA_BLOCK_FOLLOWER) != 0u) {
        ty = ft;
        if (planned - v >= HELP_OVERTAKE) {
            let need = secure_gap(v, planned, self_ty.decel);
            if ((need - gap) / remaining < planned - v) {
                ty = self_ty;
                lc_advice(f_trip, planned - HELP_OVERTAKE);
                atomicOr(&adv_flags[f_trip], dir | LCA_AM_FOLLOWER);
                return;
            }
        }
        let help_decel = ft.decel;
        let new_v = max(0.0, v - help_decel * dt);
        let new_1s = max(0.0, v - help_decel);
        let dv = planned - new_1s;
        let decel_gap = gap + dv;
        let sec = secure_gap(new_1s, planned, self_ty.decel);
        var out = -1.0;
        if (decel_gap > 0.0 && decel_gap >= sec) {
            let v1 = max(new_v, follow_speed(v, gap + planned * dt, planned, self_ty.decel, false, lanes[e.lane].speed, lanes[e.lane].speed));
            out = max(new_v, follow_speed(v, gap + (planned - v1) * dt, planned, self_ty.decel, false, lanes[e.lane].speed, lanes[e.lane].speed));
        } else if (dv > 0.0 && dv * remaining > sec - decel_gap + POS_EPS) {
            out = new_v;
        } else {
            var vhelp = max(v, e.speed + HELP_OVERTAKE);
            if (v > e.speed && ((dir == LCA_M_RIGHT && e.wait > 5.0) || (dir == LCA_M_LEFT && planned > 5.0 / 3.6))) {
                vhelp = max(new_v, e.speed + HELP_OVERTAKE);
                if ((v - e.speed) / help_decel < remaining) { out = vhelp; }
            }
            if (out < 0.0) { out = vhelp; }
        }
        ty = self_ty;
        lc_advice(f_trip, out);
        atomicOr(&adv_flags[f_trip], dir | LCA_AM_FOLLOWER);
    } else if ((blocked & LCA_BLOCK_LEADER) != 0u) {
        // Keep a secure gap to the vehicle slowing to fall behind its leader.
        ty = ft;
        let vs = max(new_v_min(v), follow_speed(v, gap + planned * dt, planned, self_ty.decel, false, lanes[e.lane].speed, lanes[e.lane].speed));
        ty = self_ty;
        lc_advice(f_trip, vs);
    }
}

fn new_v_min(v: f32) -> f32 { return min_next_speed(v); }

// MSLCM_LC2013::_wantsChange. Returns the state for this direction.
fn wants_change(side: i32, e: Veh, own: LcNeighbors, neigh: LcNeighbors, blocked: u32, dest: u32) -> u32 {
    let right = side < 0;
    let lca = select(LCA_LEFT, LCA_RIGHT, right);
    let my_lca = select(LCA_M_LEFT, LCA_M_RIGHT, right);
    let lane = lanes[e.lane];
    let vmax = lane_vmax(e.lane, e.sf);
    let neigh_vmax = lane_vmax(dest, e.sf);
    let pos = e.pos;
    var current_dist = e.best_cur;
    var neigh_dist = select(e.best_left, e.best_right, right);
    var best_offset = unpack_off(e.best_off);
    let curr_offset = best_offset;
    let neigh_is_best = (e.best_off & select(256, 512, right)) != 0;
    if (best_offset == 0 && neigh_is_best) { best_offset = side; }
    let change_to_best = (right && best_offset < 0) || (!right && best_offset > 0);
    let len_gap = ty.length + ty.min_gap;

    var la_dist = lc_look * 10.0 * ty.lc_strategic * select(ty.lc_look_left, 1.0, right);
    la_dist += len_gap * 2.0;
    if (ty.lc_strategic < 0.0) { la_dist = -1e3; }

    let best_lane = u32(i32(e.lane) + clamp(best_offset, -8, 8));
    let best_occ = f32(lane_load(best_lane)) * len_gap;
    let usable = current_dist - pos - best_occ;
    let cur_occ = f32(lane_load(e.lane)) * len_gap;
    let neigh_occ = f32(lane_load(dest)) * len_gap;
    let max_jam = max(cur_occ, neigh_occ);
    let neigh_left = max(0.0, neigh_dist - pos - max_jam);
    let has_own = own.gap < 1e8;
    let has_neigh = neigh.gap < 1e8;

    var ret = 0u;
    if (change_to_best && best_offset == curr_offset && usable / f32(abs(best_offset)) < la_dist) {
        ret |= lca | LCA_STRATEGIC | LCA_URGENT;
    } else {
        let free_until_end = !has_own || neigh_dist - pos <= own.gap;
        if (!change_to_best && neigh_left / f32(abs(best_offset) + 2) < la_dist) {
            ret |= LCA_STAY | LCA_STRATEGIC;
        } else if (best_offset == 0 && neigh_left * 2.0 < la_dist) {
            ret |= LCA_STAY | LCA_STRATEGIC;
        } else if (best_offset == 0 && lanes[dest].links_count != 0u
            && ((ty.lc_strategic >= 0.0 && neigh_dist < TURN_LANE_DIST) || (ty.lc_strategic < 0.0 && free_until_end))) {
            ret |= LCA_STAY | LCA_STRATEGIC;
        }
    }
    if ((ret & LCA_STAY) != 0u) { return ret | blocked; }
    if ((ret & LCA_URGENT) != 0u) {
        lc_left_space = current_dist - pos;
        if (change_to_best && abs(best_offset) > 1 && e.route_i + 1u < e.route_end) {
            lc_blocker = max(f32(abs(best_offset) - 1) * len_gap, lc_blocker);
        }
        // updateBlockerLength: leave room for the vehicle that blocks us to get ahead.
        if (neigh.leader_trip != NONE && (neigh.gap < 0.0 || (blocked & LCA_BLOCK_LEADER) != 0u)) {
            let room = neigh.leader_len + ty.min_gap;
            if (lc_left_space - POS_EPS >= lc_blocker + room) { lc_blocker += room; }
        }
        let lanes_left = f32(max(1, abs(best_offset)));
        let remaining = max(dt, lc_left_space / max(lc_look, EPS) / lanes_left / 2.0);
        let planned = inform_leader(e, neigh, blocked, my_lca, remaining, vmax, lane.speed);
        if (planned >= 0.0) { inform_follower(e, neigh, blocked, my_lca, remaining, planned); }
        return ret | blocked;
    }
    let accelerating = (has_neigh && neigh.acc > 0.0) || (has_own && own.acc > 0.0);
    let neigh_safe = min(neigh_vmax, anticipate(neigh.gap, has_neigh, neigh_dist, neigh_vmax, lanes[dest].speed, e.speed, neigh.speed, neigh.decel, accelerating));
    let this_safe = min(vmax, anticipate(own.gap, has_own, current_dist, vmax, lane.speed, e.speed, own.speed, own.decel, accelerating));
    let tl = 0.2 / max(1e-6, ty.lc_speed_gain);
    let tr = tl / max(1e-6, ty.lc_speed_gain_right);
    let thr = select(tl, tr, right);
    var inconvenience: f32;
    if (right) { inconvenience = lc_pl / tr; } else { inconvenience = lc_pr / tl; }
    var rel = 0.0;
    if (this_safe != 0.0) { rel = (this_safe - neigh_safe) / max(this_safe, neigh_safe); }
    inconvenience = min(1.0, max(rel, inconvenience));
    let gain_inconvenient = inconvenience > ty.lc_cooperative;

    if (right && best_offset == 0 && lane.speed > 80.0 / 3.6 && lc_look > HALT_SPEED) {
        return ret | LCA_STAY | LCA_STRATEGIC | blocked;
    }
    if ((lc_own & LCA_AM_FOLLOWER) != 0u && !gain_inconvenient && (lc_own & my_lca) != 0u
        && (change_to_best || neigh_dist / f32(abs(best_offset) + 1) > la_dist)) {
        return ret | lca | LCA_COOPERATIVE | LCA_URGENT | blocked;
    }
    let gain = (neigh_safe - this_safe) / max(neigh_safe, 10.0);
    if (right) {
        if (this_safe - 5.0 / 3.6 > neigh_safe) {
            lc_pr *= pow(0.5, dt);
        } else {
            lc_pr += dt * gain;
            let factor = vmax / lane.speed;
            let acceptance = 7.0 * factor * max(1.0, e.speed);
            var full_gap = max(0.0, neigh_dist - brake_gap(vmax, ty.decel, ty.tau));
            var seconds = min(acceptance, full_gap / vmax);
            if (has_neigh && neigh.speed < vmax) {
                full_gap = max(0.0, min(full_gap, neigh.gap - secure_gap(vmax, neigh.speed, neigh.decel)));
                seconds = min(seconds, full_gap / (vmax - neigh.speed));
            }
            if (ty.lc_speed_gain > 0.0) { lc_pk -= dt * tr * (seconds / acceptance) / 5.0; }
            if (lc_pk * ty.lc_keep_right < -tr) { return ret | lca | LCA_KEEPRIGHT | blocked; }
        }
        if (lc_pr > tr && neigh_dist / max(0.1, e.speed) > 20.0) {
            var req = ret | lca | LCA_SPEEDGAIN;
            if (lc_pr > 50.0) { req |= LCA_URGENT; }
            return req | blocked;
        }
    } else {
        if (this_safe > neigh_safe) {
            lc_pl *= pow(0.5, dt);
        } else if (this_safe == neigh_safe) {
            lc_pl *= pow(0.8, dt);
        } else {
            lc_pl += dt * gain;
        }
        if (lc_pl > tl && gain > EPS && neigh_dist / max(0.1, e.speed) > 20.0) {
            var req = ret | lca | LCA_SPEEDGAIN;
            if (lc_pl > 50.0) {
                req |= LCA_URGENT;
                if ((blocked & LCA_BLOCK_FOLLOWER) != 0u && neigh.follower != NONE) {
                    let self_ty = ty;
                    ty = types[neigh.f_vtype];
                    let help = max(min_next_speed(neigh.f_speed), e.speed - 1.0);
                    ty = self_ty;
                    lc_advice(neigh.f_trip, help);
                    atomicOr(&adv_flags[neigh.f_trip], my_lca | LCA_AM_FOLLOWER);
                }
            }
            return req | blocked;
        }
    }
    if (change_to_best && best_offset == curr_offset && ty.lc_strategic >= 0.0 && gain >= 0.0
        && select(lc_pl, lc_pr, right) > 0.0) {
        return ret | lca | LCA_STRATEGIC | blocked;
    }
    return ret | blocked;
}

// MSLaneChanger::checkChange: the gaps a change into `dest` would have to respect.
fn check_blocked(e: Veh, n: LcNeighbors) -> u32 {
    var blocked = 0u;
    let safety = 1.0 / max(EPS, ty.lc_assertive);
    if (n.follower != NONE) {
        if (n.f_gap < 0.0) {
            blocked |= LCA_BLOCK_FOLLOWER;
        } else {
            let self_ty = ty;
            ty = types[n.f_vtype];
            let need = secure_gap_lc(n.f_speed, e.speed, self_ty.apparent, n.f_acc, safety, self_ty.model == MODEL_CACC);
            ty = self_ty;
            if (n.f_gap < need * safety) { blocked |= LCA_BLOCK_FOLLOWER; }
        }
    }
    if (n.gap < 1e8) {
        if (n.gap < 0.0) {
            blocked |= LCA_BLOCK_LEADER;
        } else {
            let need = secure_gap_lc(e.speed, n.speed, n.decel, e.acc, safety, false);
            if (n.gap < need * safety) { blocked |= LCA_BLOCK_LEADER; }
        }
    }
    return blocked;
}

@compute @workgroup_size(64)
fn lc_decide(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    lc_plan[i].side = 0;
    let e = cur[i];
    if ((e.flags & F_REMOVED) != 0u || is_internal(e.lane)) { return; }
    let ed = edges[lanes[e.lane].edge];
    if (ed.lane_count <= 1u) { return; }
    ty = types[e.vtype];
    dt = P.dt;
    ego_flags = e.flags;
    ego_acc = e.acc;
    mode_done = true;
    // prepareStep: only a strategic or cooperative wish survives to the next step.
    lc_own = 0u;
    if ((e.lc_own & (LCA_STRATEGIC | LCA_COOPERATIVE)) != 0u) { lc_own = e.lc_own & LCA_WANTS; }
    lc_own |= atomicExchange(&adv_flags[e.trip], 0u);
    lc_left_space = 0.0;
    lc_blocker = 0.0;
    if (e.speed > e.look_v) {
        lc_look = e.speed;
    } else {
        let m = 1.0 - 0.1 * dt;
        lc_look = max(0.0, m * e.look_v + (1.0 - m) * e.speed);
    }
    lc_pr = e.lc_right;
    lc_pl = e.lc_left;
    lc_pk = e.lc_keep;
    let back = e.pos - ty.length;
    var own = lc_neighbors(e.lane, e.pos, i, back);
    let lookahead = max(e.speed * 10.0, 100.0);
    lc_leader_ahead(&own, e.lane, e.pos, e.route_i, e.route_end, lookahead);
    var state_r = 0u;
    var state_l = 0u;
    var chosen = 0;
    let index = i32(lanes[e.lane].index);
    if (index > 0) {
        let dest = ed.first_lane + u32(index - 1);
        if ((lanes[dest].allow & ty.vclass) == ty.vclass && (lanes[e.lane].pad1 & ty.vclass) == ty.vclass) {
            var n = lc_neighbors(dest, e.pos, i, back);
            lc_leader_ahead(&n, dest, e.pos, e.route_i, e.route_end, lookahead);
            let b = check_blocked(e, n);
            state_r = wants_change(-1, e, own, n, b, dest);
            if ((state_r & LCA_RIGHT) != 0u && (state_r & (LCA_BLOCK_LEADER | LCA_BLOCK_FOLLOWER)) == 0u) { chosen = -1; }
        }
    }
    if (chosen == 0 && index + 1 < i32(ed.lane_count)) {
        let dest = ed.first_lane + u32(index + 1);
        if ((lanes[dest].allow & ty.vclass) == ty.vclass && (lanes[e.lane].pad0 & ty.vclass) == ty.vclass) {
            var n = lc_neighbors(dest, e.pos, i, back);
            lc_leader_ahead(&n, dest, e.pos, e.route_i, e.route_end, lookahead);
            let b = check_blocked(e, n);
            state_l = wants_change(1, e, own, n, b, dest);
            if ((state_l & LCA_LEFT) != 0u && (state_l & (LCA_BLOCK_LEADER | LCA_BLOCK_FOLLOWER)) == 0u) { chosen = 1; }
        }
    }
    var state = lc_own & (LCA_AM_LEADER | LCA_AM_FOLLOWER | LCA_M_LEFT | LCA_M_RIGHT);
    if (chosen < 0) { state |= state_r; }
    else if (chosen > 0) { state |= state_l; }
    else if ((state_r & LCA_URGENT) != 0u && (state_l & LCA_URGENT) == 0u) { state |= state_r; }
    else if ((state_l & LCA_URGENT) != 0u && (state_r & LCA_URGENT) == 0u) { state |= state_l; }
    else if ((state_r & LCA_WANTS) != 0u) { state |= state_r; }
    else { state |= state_l; }
    cur[i].look_v = lc_look;
    cur[i].lc_right = lc_pr;
    cur[i].lc_left = lc_pl;
    cur[i].lc_keep = lc_pk;
    cur[i].lc_own = state;
    cur[i].left_space = lc_left_space;
    cur[i].blocker = lc_blocker;
    if (chosen == 0) { return; }
    let urgent = (state & LCA_URGENT) != 0u;
    let dest = u32(i32(e.lane) + chosen);
    // Reserve the space from our rear to a little past our front, in 8 m cells.
    let reach = ty.min_gap + 4.0;
    let first = u32(max(0.0, floor((e.pos - ty.length) / 8.0)));
    let count = min(16u, u32(ceil((e.pos + reach) / 8.0)) - first + 1u);
    // Bit 31 clear wins: urgent changes first, then a varying order so that nobody starves.
    let rank = (e.trip * 2654435761u + G.step * 40503u) >> 1u;
    let priority = select(0x80000000u, 0u, urgent) | rank;
    lc_plan[i] = LcPlan(chosen, first, count, priority);
    for (var k = 0u; k < count; k++) { atomicMin(&claims[dest * 64u + (first + k) % 64u], priority); }
}

@compute @workgroup_size(64)
fn lc_commit(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let p = lc_plan[i];
    if (p.side == 0) { return; }
    let dest = u32(i32(cur[i].lane) + p.side);
    for (var k = 0u; k < p.count; k++) {
        if (atomicLoad(&claims[dest * 64u + (p.first + k) % 64u]) != p.priority) { return; }
    }
    lc_plan[i].first = 0xffffffffu;
    cur[i].lane = dest;
    cur[i].flags |= F_LANE_CHANGED | F_BEST_DIRTY;
    cur[i].lc_right = 0.0;
    cur[i].lc_left = 0.0;
    cur[i].lc_keep = 0.0;
    cur[i].lc_own &= ~(LCA_STRATEGIC | LCA_COOPERATIVE | LCA_WANTS);
    atomicMin(&tail[dest], pack_back(cur[i].pos - types[cur[i].vtype].length, cur[i].speed, 0u));
    atomicAdd(&C[C_LANE_CHANGES], 1u);
}

// Free the reservations of this step, touching only cells that were claimed.
@compute @workgroup_size(64)
fn lc_release(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let p = lc_plan[i];
    if (p.side == 0) { return; }
    var first = p.first;
    var dest = u32(i32(cur[i].lane) + p.side);
    if (first == 0xffffffffu) {
        // Committed: the plan lost `first`, recompute from where it stands now.
        dest = cur[i].lane;
        first = u32(max(0.0, floor((cur[i].pos - types[cur[i].vtype].length) / 8.0)));
    }
    for (var k = 0u; k < p.count; k++) { atomicStore(&claims[dest * 64u + (first + k) % 64u], NONE); }
}
