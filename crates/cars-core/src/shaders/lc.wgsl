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
const MIN_FALLBEHIND: f32 = 7.0 / 3.6;
const TURN_LANE_DIST: f32 = 200.0;

@compute @workgroup_size(64)
fn lc_best(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let e = cur[i];
    if ((e.flags & F_REMOVED) != 0u || is_internal(e.lane)) { return; }
    // SUMO refreshes occupation every step. Every two seconds is close, and much cheaper.
    let periodic = ((G.step + e.trip) % max(1u, u32(2.0 / P.dt))) == 0u;
    if ((e.flags & F_BEST_DIRTY) == 0u && !periodic) { return; }
    ty = types[e.vtype];
    dt = P.dt;
    let ed = edges[lanes[e.lane].edge];
    if (ed.lane_count > 16u) { return; }
    if (ed.lane_count == 1u) {
        cur[i].flags &= ~F_BEST_DIRTY;
        return;
    }
    let len_gap = ty.length + ty.min_gap;
    var occ: array<f32, 16>;
    var next_occ: array<f32, 16>;
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
            occ[k] = 0.0;
            if ((l.allow & ty.vclass) != ty.vclass) { continue; }
            a[k] = l.length;
            if (ri + 1u < stop) {
                var cont = 0.0;
                var co = 1000;
                var co_occ = 0.0;
                for (var j = 0u; j < l.links_count; j++) {
                    let lk = links[l.links_start + j];
                    if (lk.to_edge != routes[ri + 1u] || (lanes[lk.to_lane].allow & ty.vclass) != ty.vclass) { continue; }
                    let nk = min(lanes[lk.to_lane].index, 15u);
                    if (b[nk] > cont || (b[nk] == cont && abs(next_off[nk]) < abs(co))) {
                        cont = b[nk]; co = next_off[nk];
                        co_occ = next_occ[nk] + f32(lane_load(lk.to_lane)) * len_gap;
                    }
                }
                occ[k] = co_occ;
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
        for (var k = 0u; k < count; k++) { next_occ[k] = occ[k]; }
        if (ri == e.route_i) { break; }
    }
    let k = lanes[e.lane].index;
    cur[i].best_cur = b[k];
    cur[i].best_left = 0.0;
    cur[i].best_right = 0.0;
    cur[i].occ_cur = occ[k];
    cur[i].occ_left = 0.0;
    cur[i].occ_right = 0.0;
    let best_k = u32(clamp(i32(k) + next_off[k], 0, 15));
    cur[i].occ_best = occ[best_k];
    var packed = next_off[k] & 255;
    if (k + 1u < ed.lane_count) {
        cur[i].best_left = b[k + 1u];
        cur[i].occ_left = occ[k + 1u];
        if (next_off[k + 1u] == 0) { packed |= 256; }
    }
    if (k > 0u) {
        cur[i].best_right = b[k - 1u];
        cur[i].occ_right = occ[k - 1u];
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
    leader_vtype: u32,
    leader_own: u32,
    leader_sf: f32,
    leader_cacc: bool,
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
                r.leader_cacc = ot.model == MODEL_CACC;
                r.leader_wait = o.wait; r.leader_len = ot.length; r.leader_vtype = o.vtype; r.leader_own = o.lc_own; r.leader_sf = o.sf;
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
                    r.leader_trip = o.trip; r.leader_cacc = ot.model == MODEL_CACC;
                r.leader_wait = o.wait; r.leader_len = ot.length; r.leader_vtype = o.vtype; r.leader_own = o.lc_own; r.leader_sf = o.sf;
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
            r.leader_cacc = unpack_cacc(p);
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
            (*r).leader_cacc = unpack_cacc(packed);
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

fn overtake_distance(leader_vtype: u32, f_len: f32, gap: f32, leader_speed: f32, follower_speed: f32, f_decel: f32) -> f32 {
    let self_ty = ty;
    ty = types[leader_vtype];
    let sec = secure_gap(leader_speed, follower_speed, f_decel);
    let lg = ty.length + ty.min_gap;
    ty = self_ty;
    return max(gap + lg + f_len + sec, 0.0);
}

// SUMO avoids overtaking on the right unless congested or on a slow road.
fn avoid_overtake_right(speed: f32, limit: f32) -> bool {
    return !(speed < 60.0 / 3.6 || limit < 60.1 / 3.6);
}

fn inform_leader(e: Veh, n: LcNeighbors, blocked: u32, dir: u32, remaining: f32, vmax: f32, limit: f32) -> f32 {
    var planned = e.speed;
    planned = min(planned, stop_speed(e.speed, lc_left_space - lc_blocker, ty.decel, true, vmax));
    if (n.gap > 1e8) { return planned; }
    let nv_next = n.speed - max(1.0, -n.acc) * dt;
    let next_gap = n.gap + (nv_next - planned) * dt;
    if ((blocked & LCA_BLOCK_LEADER) != 0u) {
        var over = max(n.gap, 0.0) + ty.length + n.leader_len + ty.min_gap;
        if (n.leader_trip != NONE) { over = overtake_distance(n.leader_vtype, ty.length, n.gap, n.speed, e.speed, ty.decel); }
        let dv = planned - n.speed;
        var ot: f32;
        if (dv > 0.0) { ot = over / dv; }
        else if (n.leader_wait > 5.0 && ty.length + ty.min_gap + n.leader_len + ty.min_gap <= lc_left_space) { ot = remaining - 1.0; }
        else { ot = remaining + 1.0; }
        let fall_behind = dv < 0.0
            || (dir == LCA_M_LEFT && avoid_overtake_right(e.speed, limit))
            || lc_left_space - lc_blocker - brake_gap(e.speed, ty.decel, ty.tau) < over
            || remaining < ot;
        if (fall_behind) {
            if (n.leader_trip != NONE) { atomicOr(&adv_flags[n.leader_trip], dir | LCA_AM_LEADER); }
            let tgt = max(min_next_speed(e.speed), follow_speed(e.speed, next_gap, nv_next, n.decel, false, vmax, limit));
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
        if (n.leader_trip != NONE && n.leader_wait <= 5.0) {
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
    let limit = lanes[e.lane].speed;
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
        var ego_yields = false;
        if (decel_gap > 0.0 && decel_gap >= sec) {
            let v1 = max(new_v, follow_speed(v, gap + planned * dt, planned, self_ty.decel, false, limit, limit));
            out = max(new_v, follow_speed(v, gap + (planned - v1) * dt, planned, self_ty.decel, false, limit, limit));
        } else if (dv > 0.0 && dv * remaining > sec - decel_gap + POS_EPS) {
            out = new_v;
        } else if (dir == LCA_M_RIGHT && avoid_overtake_right(v, limit)) {
            out = max(new_v, HELP_OVERTAKE);
        } else {
            var vhelp = max(v, e.speed + HELP_OVERTAKE);
            if (v > e.speed && (dir == LCA_M_RIGHT
                || (dir == LCA_M_LEFT && planned > 27.0)
                || (dir == LCA_M_LEFT && lanes[e.lane].length > 200.0))) {
                vhelp = max(new_v, e.speed + HELP_OVERTAKE);
                if ((v - e.speed) / help_decel < remaining) { out = vhelp; }
            }
            if (out < 0.0) {
                out = vhelp;
                ego_yields = true;
            }
        }
        ty = self_ty;
        lc_advice(f_trip, out);
        atomicOr(&adv_flags[f_trip], dir | LCA_AM_FOLLOWER);
        if (ego_yields) {
            // Let the follower pass: fall back far enough for it to get by in time.
            let over = overtake_distance(e.vtype, ft.length, gap, planned, out, ft.decel);
            lc_advice(e.trip, max(out - over / remaining, e.speed - ty.decel * dt));
        }
    } else if ((blocked & LCA_BLOCK_LEADER) != 0u) {
        // MSLCHelper::getSpeedPreservingSecureGap
        ty = ft;
        let next_gap = gap + (planned - v) * dt;
        let sg = secure_gap(v, planned, self_ty.decel);
        var vs: f32;
        if (next_gap >= sg) {
            let vm = follow_speed(v, gap + (planned - max_next_speed(v)) * dt, planned, self_ty.decel, false, limit, limit);
            vs = max(vm, v);
        } else {
            let vm = follow_speed(v, next_gap, planned, self_ty.decel, false, limit, limit);
            vs = max(vm, min_next_speed(v));
        }
        ty = self_ty;
        lc_advice(f_trip, vs);
    }
}

// MSLaneChanger::dens includes only vehicles already swept ahead of ego.
fn lc_ahead_load(l: u32, pos: f32, ego: u32) -> u32 {
    var count = 0u;
    var end = 0u;
    var first = 0u;
    if (lane_occupied(l)) {
        let s = seg[l];
        first = s.first;
        var lo = s.first;
        var hi = s.end;
        loop {
            if (lo >= hi) { break; }
            let mid = (lo + hi) / 2u;
            if (cur[mid].lane == l && (cur[mid].flags & F_REMOVED) == 0u) { lo = mid + 1u; }
            else { hi = mid; }
        }
        end = lo;
        lo = s.first;
        hi = end;
        loop {
            if (lo >= hi) { break; }
            let mid = (lo + hi) / 2u;
            if (cur[mid].pos < pos) { lo = mid + 1u; } else { hi = mid; }
        }
        count = end - lo;
        if (ego >= lo && ego < end) { count -= 1u; }
    }
    let ent = atomicLoad(&entrant[l]);
    if (ent != NONE) {
        let k = ent & 0x3fffffu;
        let o = cur[k];
        if (k != ego && (k < first || k >= end) && o.lane == l && o.pos >= pos && (o.flags & F_REMOVED) == 0u) { count += 1u; }
    }
    return count;
}

// MSLCM_LC2013::_wantsChange. Returns the state for this direction.
fn wants_change(side: i32, e: Veh, own: LcNeighbors, neigh: LcNeighbors, blocked: u32, dest: u32, ego: u32) -> u32 {
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
    let best_occ = f32(lc_ahead_load(best_lane, pos, ego)) * len_gap + select(e.occ_best, select(e.occ_left, e.occ_right, right), curr_offset == 0);
    let usable = current_dist - pos - best_occ;
    let cur_occ = f32(lc_ahead_load(e.lane, pos, ego)) * len_gap + e.occ_cur;
    let neigh_occ = f32(lc_ahead_load(dest, pos, ego)) * len_gap + select(e.occ_left, e.occ_right, right);
    let max_jam = max(cur_occ, neigh_occ);
    let neigh_left = max(0.0, neigh_dist - pos - max_jam);
    let has_own = own.gap < 1e8;
    let has_neigh = neigh.gap < 1e8;

    var ret = 0u;
    var this_limit = vmax;
    var left_to_avoid = false;
    let check_otr = avoid_overtake_right(e.speed, lane.speed);
    let tl = 0.2 / max(1e-6, ty.lc_speed_gain);
    let tr = tl / max(1e-6, ty.lc_speed_gain_right);
    if (change_to_best && best_offset == curr_offset && usable / f32(abs(best_offset)) < la_dist) {
        ret |= lca | LCA_STRATEGIC | LCA_URGENT;
    } else {
        if (has_neigh && neigh.leader_trip != NONE && check_otr && !right) {
            let nv_max = min(lanes[dest].speed * neigh.leader_sf, types[neigh.leader_vtype].max_speed);
            let dv = max(vmax - nv_max, e.speed - neigh.speed);
            if (dv > 0.0) {
                let v_max_decel = max(0.0, e.speed - ty.decel * dt);
                let v_follow = follow_speed(e.speed, neigh.gap, neigh.speed, neigh.decel, false, vmax, lane.speed);
                var v_safe = max(v_max_decel, neigh.speed - HELP_OVERTAKE);
                if (v_follow >= v_max_decel) { v_safe = v_follow; }
                if (lc_pl < tl) { v_safe = max(v_safe, neigh.speed); }
                this_limit = min(this_limit, v_safe);
                if ((lc_own & LCA_RIGHT) == 0u) { lc_advice(e.trip, v_safe); }
                let future = follow_speed(e.speed, neigh.gap - dv * 8.0, neigh.speed, neigh.decel, false, vmax, lane.speed);
                if (future < v_safe) {
                    lc_pl += dt * dv / max(vmax, 10.0);
                    left_to_avoid = true;
                }
            }
        }
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
            // getExtraReservation
            if (neigh_dist - current_dist <= len_gap) { lc_blocker = max(select(40.0, 20.0, best_offset < 0), lc_blocker); }
        }
        // updateBlockerLength: leave room for a neighbour that wants to come the opposite way.
        let counter = select(LCA_RIGHT, LCA_LEFT, right);
        if (neigh.leader_trip != NONE && (neigh.leader_own & counter) != 0u) {
            let potential = lc_left_space - POS_EPS - brake_gap(e.speed, ty.decel, 0.0);
            let room = neigh.leader_len + ty.min_gap;
            if (room <= potential) { lc_blocker = max(room, lc_blocker); }
        }
        let lanes_left = f32(max(1, abs(best_offset)));
        let remaining = max(dt, lc_left_space / max(lc_look, EPS) / lanes_left / 2.0);
        let planned = inform_leader(e, neigh, blocked, my_lca, remaining, vmax, lane.speed);
        if (planned >= 0.0) { inform_follower(e, neigh, blocked, my_lca, remaining, planned); }
        return ret | blocked;
    }
    let accelerating = (has_neigh && neigh.acc > 0.0) || (has_own && own.acc > 0.0);
    let neigh_safe = min(neigh_vmax, anticipate(neigh.gap, has_neigh, neigh_dist, neigh_vmax, lanes[dest].speed, e.speed, neigh.speed, neigh.decel, accelerating));
    let this_safe = min(this_limit, anticipate(own.gap, has_own, current_dist, vmax, lane.speed, e.speed, own.speed, own.decel, accelerating));
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
            if (check_otr && has_own && own.leader_trip != NONE && min(lane.speed * own.leader_sf, types[own.leader_vtype].max_speed) < vmax) {
                full_gap = min(full_gap, own.gap);
                seconds = min(seconds, full_gap / (vmax - own.speed));
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
        if (lc_pl > tl && (gain > EPS || left_to_avoid) && neigh_dist / max(0.1, e.speed) > 20.0) {
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

// MSLCM_LC2013::slowDownForBlocked, seen from the blocked side: the vehicle behind us on the lane
// we want treats us as its leader, which opens the gap we need.
fn hold_follower_for_blocked(e: Veh, n: LcNeighbors) {
    if (n.follower == NONE || n.f_gap <= POS_EPS) { return; }
    let self_ty = ty;
    ty = types[n.f_vtype];
    if (n.f_speed < ty.decel) {
        let limit = lanes[e.lane].speed;
        lc_advice(n.f_trip, follow_speed(n.f_speed, n.f_gap - POS_EPS, e.speed, self_ty.decel, false, limit, limit));
    }
    ty = self_ty;
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
            let need = secure_gap_lc(e.speed, n.speed, n.decel, e.acc, safety, n.leader_cacc);
            if (n.gap < need * safety) { blocked |= LCA_BLOCK_LEADER; }
        }
    }
    return blocked;
}

@compute @workgroup_size(64)
fn lc_decide(@builtin(global_invocation_id) id: vec3u) {
    if (id.x >= G.n_active) { return; }
    lc_plan[id.x].side = 0;
    lc_evaluate(id.x);
}

// SUMO's sweep lets a vehicle react to a neighbour's request in the same step. This second look,
// only for vehicles that were just asked to help, gives the same order of events.
@compute @workgroup_size(64)
fn lc_decide_helpers(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active || lc_plan[i].side != 0) { return; }
    if (atomicLoad(&adv_flags[cur[i].trip]) == 0u) { return; }
    lc_evaluate(i);
}

fn lc_evaluate(i: u32) {
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
            state_r = wants_change(-1, e, own, n, b, dest, i);
            if ((state_r & LCA_RIGHT) != 0u && (state_r & (LCA_BLOCK_LEADER | LCA_BLOCK_FOLLOWER)) == 0u) { chosen = -1; }
            else if ((state_r & LCA_RIGHT) != 0u && (state_r & LCA_URGENT) != 0u) { hold_follower_for_blocked(e, n); }
        }
    }
    if (chosen == 0 && index + 1 < i32(ed.lane_count)) {
        let dest = ed.first_lane + u32(index + 1);
        if ((lanes[dest].allow & ty.vclass) == ty.vclass && (lanes[e.lane].pad0 & ty.vclass) == ty.vclass) {
            var n = lc_neighbors(dest, e.pos, i, back);
            lc_leader_ahead(&n, dest, e.pos, e.route_i, e.route_end, lookahead);
            let b = check_blocked(e, n);
            state_l = wants_change(1, e, own, n, b, dest, i);
            if ((state_l & LCA_LEFT) != 0u && (state_l & (LCA_BLOCK_LEADER | LCA_BLOCK_FOLLOWER)) == 0u) { chosen = 1; }
            else if ((state_l & LCA_LEFT) != 0u && (state_l & LCA_URGENT) != 0u) { hold_follower_for_blocked(e, n); }
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
