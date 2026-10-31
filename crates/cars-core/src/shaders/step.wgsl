// One simulation step, in SUMO's order: signals, plan, approach, execute, lane change, insert.
// `prev` holds the last step's vehicles, `cur` this step's, sorted by lane and position.

@group(0) @binding(0) var<uniform> P: Params;
@group(0) @binding(1) var<storage, read_write> G: Globals;
@group(0) @binding(2) var<storage, read_write> C: array<atomic<u32>>;
@group(0) @binding(3) var<storage, read> lanes: array<Lane>;
@group(0) @binding(4) var<storage, read> edges: array<Edge>;
@group(0) @binding(5) var<storage, read> links: array<Link>;
@group(0) @binding(6) var<storage, read> foes: array<u32>;
@group(0) @binding(7) var<storage, read> conflicts: array<Conflict>;
@group(0) @binding(8) var<storage, read> types: array<VType>;
@group(0) @binding(9) var<storage, read> routes: array<u32>;
@group(0) @binding(10) var<storage, read> trips: array<Trip>;
@group(0) @binding(11) var<storage, read_write> queues: array<Queue>;
@group(0) @binding(12) var<storage, read_write> tls: array<TlsState>;
@group(0) @binding(13) var<storage, read> phases: array<TlsPhase>;
@group(0) @binding(14) var<storage, read> states: array<u32>;
@group(0) @binding(15) var<storage, read> prev: array<Veh>;
@group(0) @binding(16) var<storage, read_write> cur: array<Veh>;
@group(1) @binding(0) var<storage, read_write> keys0: array<u32>;
@group(1) @binding(1) var<storage, read_write> vals0: array<u32>;
@group(1) @binding(2) var<storage, read> sorted_vals: array<u32>;
@group(0) @binding(20) var<storage, read_write> seg: array<LaneSeg>;
@group(0) @binding(21) var<storage, read_write> items: array<Item>;
@group(0) @binding(22) var<storage, read_write> slots: array<Approach>;
@group(0) @binding(23) var<storage, read_write> link_count: array<atomic<u32>>;
@group(0) @binding(24) var<storage, read_write> partial_occ: array<atomic<u32>>;
@group(0) @binding(25) var<storage, read_write> tail: array<atomic<u32>>;
@group(0) @binding(26) var<storage, read_write> entrant: array<atomic<u32>>;
@group(0) @binding(27) var<storage, read_write> trip_out: array<TripOut>;
@group(0) @binding(28) var<storage, read_write> series: array<atomic<u32>>;
@group(0) @binding(29) var<storage, read_write> edge_acc: array<atomic<u32>>;
@group(0) @binding(31) var<storage, read_write> advice: array<atomic<u32>>;
@group(0) @binding(32) var<storage, read> queue_trips: array<u32>;
@group(0) @binding(33) var<storage, read_write> claims: array<atomic<u32>>;
@group(0) @binding(34) var<storage, read_write> last_detect: array<u32>;
@group(0) @binding(35) var<storage, read_write> lc_plan: array<LcPlan>;

const C_NEW: u32 = 0u;
const C_REMOVED: u32 = 1u;
const C_ARRIVED: u32 = 2u;
const C_INSERTED: u32 = 3u;
const C_TELEPORTS: u32 = 4u;
const C_OVERFLOW: u32 = 5u;
const C_LANE_CHANGES: u32 = 6u;
const C_COLLISIONS: u32 = 7u;
const C_ITEMS_FULL: u32 = 8u;

struct Queue {
    edge: u32,
    next: u32,
    end: u32,
    pad: u32,
}

struct LcPlan {
    side: i32,    // 0 none, -1 right, +1 left
    first: u32,   // first reservation cell
    count: u32,
    priority: u32,
}

fn is_internal(l: u32) -> bool { return (lanes[l].flags & LANE_INTERNAL) != 0u; }

fn lane_vmax(l: u32, sf: f32) -> f32 { return min(lanes[l].speed * sf, ty.max_speed); }

fn link_state(l: u32) -> u32 {
    let k = links[l].tl;
    if (k == NONE) { return links[l].state; }
    let ts = tls[k];
    return states[phases[ts.first_phase + ts.phase].state_start + links[l].tl_index];
}

const CH_r: u32 = 114u;
const CH_u: u32 = 117u;
const CH_y: u32 = 121u;
const CH_Y: u32 = 89u;
const CH_G: u32 = 71u;
const CH_g: u32 = 103u;
const CH_M: u32 = 77u;
const CH_m: u32 = 109u;
const CH_EQ: u32 = 61u;
const CH_s: u32 = 115u;
const CH_w: u32 = 119u;
const CH_Z: u32 = 90u;

fn have_red(s: u32) -> bool { return s == CH_r || s == CH_u; }
fn have_yellow(s: u32) -> bool { return s == CH_y || s == CH_Y; }
fn have_green(s: u32) -> bool { return s == CH_G || s == CH_g; }
fn have_priority(s: u32) -> bool { return s >= 65u && s <= 90u; }

fn last_was_cont_major(l: u32) -> bool {
    if ((links[l].flags & (L_EXIT_AFTER_IJ | L_INTERNAL_JUNCTION)) == 0u) { return false; }
    let e = link_state(links[l].entry);
    return have_priority(e) || have_yellow(e);
}

// ---------------------------------------------------------------- bookkeeping

@compute @workgroup_size(16)
fn tls_step(@builtin(global_invocation_id) id: vec3u) {
    let t = id.x;
    if (t >= P.n_tls) { return; }
    var s = tls[t];
    let now = G.step;
    if (now < s.next_switch) {
        if (s.actuated == 0u) { return; }
    }
    let ph = phases[s.first_phase + s.phase];
    if (s.actuated != 0u) {
        // Gap control: a green phase holds while a vehicle has crossed a detector recently.
        let elapsed = now - s.last_change;
        if (elapsed < ph.min_dur) { return; }
        if (elapsed < ph.max_dur && ph.max_dur > ph.min_dur) {
            var demand = false;
            for (var k = 0u; k < s.link_count; k++) {
                let l = s.link_start + k;
                let cs = states[ph.state_start + links[l].tl_index];
                if (have_green(cs)) {
                    let at = last_detect[links[l].from_lane];
                    if (at != 0u && now - at < u32(3.0 / P.dt)) { demand = true; break; }
                }
            }
            if (demand) { return; }
        }
    }
    s.phase = (s.phase + 1u) % s.n_phases;
    s.last_change = now;
    s.next_switch = now + phases[s.first_phase + s.phase].duration;
    tls[t] = s;
}

@compute @workgroup_size(64)
fn keys(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n) { return; }
    let v = prev[i];
    vals0[i] = i;
    if ((v.flags & F_REMOVED) != 0u) {
        keys0[i] = (1u << P.key_bits) - 1u;
        atomicAdd(&C[C_REMOVED], 1u);
        return;
    }
    let l = lanes[v.lane];
    keys0[i] = l.key_base + u32(clamp(v.pos, 0.0, l.length) * l.key_scale);
}

@compute @workgroup_size(64)
fn gather(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n) { return; }
    cur[i] = prev[sorted_vals[i]];
}

@compute @workgroup_size(64)
fn build_seg(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    let n = G.n_active;
    if (i >= n) { return; }
    let l = cur[i].lane;
    let starts = i == 0u || cur[i - 1u].lane != l;
    let ends = i + 1u == n || cur[i + 1u].lane != l;
    if (starts) {
        seg[l].first = i;
        seg[l].stamp = G.step;
    }
    if (ends) { seg[l].end = i + 1u; }
}

@compute @workgroup_size(64)
fn clear_links(@builtin(global_invocation_id) id: vec3u) {
    if (id.x >= P.n_links) { return; }
    atomicStore(&link_count[id.x], 0u);
}

@compute @workgroup_size(64)
fn clear_lanes(@builtin(global_invocation_id) id: vec3u) {
    if (id.x >= P.n_lanes) { return; }
    atomicStore(&partial_occ[id.x], NONE);
    atomicStore(&tail[id.x], NONE);
    atomicStore(&entrant[id.x], NONE);
    for (var k = 0u; k < 64u; k++) { atomicStore(&claims[id.x * 64u + k], NONE); }
}

fn pack_back(back: f32, speed: f32) -> u32 {
    return (u32(clamp(back, 0.0, 8000.0) * 8.0) << 16u) | u32(clamp(speed, 0.0, 200.0) * 256.0);
}
fn unpack_back(p: u32) -> f32 { return f32(p >> 16u) / 8.0; }
fn unpack_speed(p: u32) -> f32 { return f32(p & 0xffffu) / 256.0; }

fn lane_occupied(l: u32) -> bool { return seg[l].stamp == G.step; }

// ---------------------------------------------------------------- plan

var<private> pl_i: u32;
var<private> pl_v: f32;
var<private> pl_pass: f32;
var<private> pl_speed: f32;
var<private> pl_lane_vmax: f32;
var<private> pl_limit: f32;
var<private> pl_base: u32;
var<private> pl_n: u32;
var<private> pl_set_request: bool;
var<private> pl_v_wait: f32;
var<private> pl_rng: u32;

fn adapt_leave(item: u32, v: f32) {
    let a = items[item].leave;
    if (a < 0.0) { items[item].leave = v; } else { items[item].leave = min(a, v); }
}

fn adapt_to_leader(gap: f32, seen: f32, cur_len: f32, ls: f32, lb: f32, lcacc: bool, back_on_this: bool, stop_extra: f32) {
    var vsafe = 0.0;
    var back_on_route = true;
    let has_last = pl_n > 0u;
    if (gap < 0.0 && has_last) {
        back_on_route = back_on_this;
        if (!back_on_route) {
            vsafe = stop_speed(pl_speed, seen - cur_len - POS_EPS - stop_extra, ty.decel, true, pl_lane_vmax);
        }
    }
    if (back_on_route) {
        vsafe = follow_speed(pl_speed, gap, ls, lb, lcacc, pl_lane_vmax, pl_limit);
    }
    if (has_last) {
        let last = pl_base + pl_n - 1u;
        let future = follow_speed(max(items[last].leave, 0.0), gap, ls, lb, lcacc, pl_lane_vmax, pl_limit);
        adapt_leave(last, future);
    }
    pl_v = min(pl_v, vsafe);
    pl_pass = min(pl_pass, vsafe);
}

// Everything that sits on `lane` ahead of us: the rear-most full vehicle, and any vehicle whose
// tail is still hanging onto this lane from the next one.
fn adapt_to_lane(lane: u32, seen: f32, first: bool, leader_index: u32, ego_pos: f32) {
    let l_len = lanes[lane].length;
    var extra = 0.0;
    if (pl_n > 0u) {
        let lk = items[pl_base + pl_n - 1u].link;
        if (lk != NONE && links[lk].before != NONE) { extra = lanes[links[lk].before].length; }
    }
    if (leader_index != NONE && leader_index != pl_i) {
        let lead = cur[leader_index];
        let lt = types[lead.vtype];
        let back = lead.pos - lt.length;
        var gap: f32;
        if (first) { gap = back - ego_pos - ty.min_gap; } else { gap = back + seen - l_len - ty.min_gap; }
        adapt_to_leader(gap, seen, l_len, lead.speed, lt.apparent, lt.model == MODEL_CACC, back >= 0.0, extra);
    }
    let p = atomicLoad(&partial_occ[lane]);
    if (p != NONE) {
        let back = unpack_back(p);
        if (!first || back > ego_pos) {
            var gap: f32;
            if (first) { gap = back - ego_pos - ty.min_gap; } else { gap = back + seen - l_len - ty.min_gap; }
            adapt_to_leader(gap, seen, l_len, unpack_speed(p), ty.apparent, false, true, extra);
        }
    }
}

fn adapt_to_junction_leader(gap: f32, is_critical: bool, seen: f32, l_len: f32, dist_cross: f32, ls: f32, lb: f32, lcacc: bool) {
    var vsafe = 0.0;
    if (!is_critical && gap >= 0.0) {
        vsafe = follow_speed(pl_speed, gap, ls, lb, lcacc, pl_lane_vmax, pl_limit);
    } else {
        vsafe = stop_speed(pl_speed, seen - l_len - POS_EPS, ty.decel, true, pl_lane_vmax);
    }
    if (dist_cross >= 0.0) {
        let vstop = stop_speed(pl_speed, dist_cross - ty.min_gap, ty.decel, true, pl_lane_vmax);
        if (is_critical) {
            vsafe = max(vsafe, vstop);
        } else {
            let leader_dist = dist_cross - gap;
            let past_time = leader_dist / max(ls, HALT_SPEED);
            let vfinal = max(pl_speed, 2.0 * (dist_cross - ty.min_gap) / past_time - pl_speed);
            let v2 = pl_speed + (vfinal - pl_speed) / past_time * dt;
            vsafe = max(vsafe, min(v2, vstop));
        }
    }
    if (pl_n > 0u) {
        let last = pl_base + pl_n - 1u;
        let future = follow_speed(max(items[last].leave, 0.0), gap, ls, lb, lcacc, pl_lane_vmax, pl_limit);
        if (gap >= 0.0 && !is_critical) { adapt_leave(last, future); }
    }
    pl_v = min(pl_v, vsafe);
    pl_pass = min(pl_pass, vsafe);
}

fn yields_to_foe(link_i: u32, foe_lane: u32) -> bool {
    // Is the foe's entry link among the links this link must give way to?
    let e = links[link_i].entry;
    let fi = links_incoming_entry(foe_lane);
    let k = links[e];
    for (var j = 0u; j < k.foe_count; j++) {
        if (foes[k.foe_start + j] == fi) { return true; }
    }
    return false;
}

fn links_incoming_entry(lane: u32) -> u32 { return lanes[lane].entry_link; }

// MSVehicle::isLeader, with one entry time per vehicle.
fn is_leader(link_i: u32, ego_lane: u32, ego_entry: u32, foe_i: u32, gap: f32) -> bool {
    if (!is_internal(ego_lane)) { return true; }
    let foe = cur[foe_i];
    if (!is_internal(foe.lane)) { return true; }
    let foe_pred = lanes[foe.lane].pred;
    let ego_pred = lanes[ego_lane].pred;
    var response = true;
    var response2 = true;
    if (foe_pred != ego_pred) {
        let entry = link_state(links[link_i].entry);
        let foe_entry = link_state(lanes[foe.lane].entry_link);
        if (have_red(entry) || have_red(foe_entry)) {
            if (!have_red(foe_entry) && foe.speed > HALT_SPEED && gap < 0.0) {
                let ft = types[foe.vtype];
                let foe_next = foe.speed + ft.accel * dt;
                let foe_brake = foe_next * ft.tau + foe_next * foe_next / (2.0 * ft.decel);
                let foe_gap = -gap - ft.length - 2.0 * ty.min_gap;
                if (foe_gap < foe_brake) { response = true; response2 = false; } else { response = false; response2 = true; }
            }
        } else if (have_priority(entry) != have_priority(foe_entry)) {
            response = !have_priority(entry);
            response2 = !have_priority(foe_entry);
        } else if (have_yellow(entry) && have_yellow(foe_entry)) {
            response = foe.speed >= pl_speed;
            response2 = pl_speed >= foe.speed;
        } else {
            response = yields_to_foe(link_i, foe.lane);
            response2 = !response;
        }
        if (!response) { return false; }
    }
    let foe_et = foe.entry_step;
    if (ego_entry == foe_et) {
        if (pl_speed == foe.speed) { return cur[pl_i].trip < foe.trip; }
        return pl_speed < foe.speed;
    }
    return ego_entry > foe_et;
}

// MSVehicle::checkLinkLeader over MSLink::getLeaderInfo.
fn check_link_leader(link_i: u32, lane: u32, seen: f32, ego_lane: u32, ego_entry: u32, ego_wait: f32) {
    let k = links[link_i];
    if (k.conf_count == 0u) { return; }
    let l_len = lanes[lane].length;
    let e_entry = link_state(k.entry);
    for (var c = 0u; c < k.conf_count; c++) {
        let cf = conflicts[k.conf_start + c];
        if ((cf.flags & C_NO_CROSSING) != 0u) { continue; }
        let dist_cross = seen - cf.len_behind;
        let foe_dist = lanes[cf.foe_lane].length - cf.foe_len_behind;
        let same_target = (cf.flags & C_SAME_TARGET) != 0u;
        let same_source = (cf.flags & C_SAME_SOURCE) != 0u;
        let cont_lane = (cf.flags & C_CONT_LANE) != 0u;
        let dummy = (cf.flags & C_DUMMY_MERGE) != 0u;
        if (dist_cross + cf.width < 0.0 && !same_target) { continue; }
        var ignore_green_cont = false;
        if (cont_lane) {
            let foe_entry_link = lanes[cf.foe_lane].entry_link;
            if (have_green(e_entry) && have_green(link_state(foe_entry_link))
                && links[k.entry].from_lane != links[foe_entry_link].from_lane) {
                ignore_green_cont = true;
            }
        }
        // Whole vehicles on the foe lane.
        if (lane_occupied(cf.foe_lane)) {
            let s = seg[cf.foe_lane];
            for (var idx = s.first; idx < s.end; idx++) {
                if (idx == pl_i) { continue; }
                let f = cur[idx];
                if (f.wait >= P.ignore_blocker) { continue; }
                let ft = types[f.vtype];
                let back = f.pos - ft.length;
                let back_dist = foe_dist - back;
                let past = back_dist + cf.foe_width < 0.0;
                let entered = back_dist < ft.length;
                let cannot_ignore = cont_lane || same_target || same_source;
                let way1 = (!past && dist_cross > 0.0) || (same_target && dist_cross > back_dist - ft.length);
                let in_way = way1 && (entered || (same_source && !entered && foe_dist < dist_cross)) && (!dummy || same_source);
                if (!in_way && ignore_green_cont) { continue; }
                if (dist_cross < -POS_EPS && !in_way) { continue; }
                if (same_source && lanes[ego_lane].edge == lanes[lane].edge
                    && back + ft.length < cur[pl_i].pos - ty.length) { continue; }
                let will_pass = (f.flags & F_WILL_PASS) != 0u;
                if ((!cannot_ignore || same_target) && !will_pass && f.speed < HALT_SPEED && !in_way) { continue; }
                var gap = 0.0;
                var critical = false;
                if (cont_lane && !same_source) {
                    critical = true;
                    gap = -1e6;
                } else {
                    if (past && !same_target) { continue; }
                    var bd2 = back_dist;
                    if (same_target && bd2 < 0.0) {
                        let mismatch = cf.foe_len_behind - cf.len_behind;
                        if (mismatch > 0.0) { bd2 += mismatch; }
                    }
                    gap = dist_cross - ty.min_gap - bd2 - cf.foe_width;
                }
                if (is_leader(link_i, ego_lane, ego_entry, idx, gap) || in_way) {
                    adapt_to_junction_leader(gap, critical, seen, l_len, dist_cross, f.speed, ft.apparent, ft.model == MODEL_CACC);
                    if (pl_n > 0u) { pl_v = max(pl_v, items[pl_base + pl_n - 1u].v_wait); }
                    if (pl_v < HALT_SPEED) {
                        let same_pred = lanes[f.lane].pred == lanes[ego_lane].pred;
                        let pred_me = lanes[f.lane].pred == ego_lane;
                        if (same_pred || pred_me || f.wait > 5.0) {
                            pl_set_request = false;
                            if (pl_n > 0u && pred_me) { items[pl_base + pl_n - 1u].request = 0u; }
                        }
                    }
                }
            }
        }
        // A tail still hanging on the foe lane from the vehicle ahead of it.
        let p = atomicLoad(&partial_occ[cf.foe_lane]);
        if (p != NONE) {
            let back = unpack_back(p);
            let back_dist = foe_dist - back;
            let past = back_dist + cf.foe_width < 0.0;
            let entered = back_dist < 5.0;
            let in_way = ((!past && dist_cross > 0.0) || (same_target && dist_cross > back_dist - 5.0)) && entered && !dummy;
            if ((in_way || !past) && dist_cross >= -POS_EPS && !(past && !same_target)) {
                let gap = dist_cross - ty.min_gap - back_dist - cf.foe_width;
                if (in_way) {
                    adapt_to_junction_leader(gap, false, seen, l_len, dist_cross, unpack_speed(p), ty.apparent, false);
                }
            }
        }
    }
    pl_v_wait = min(pl_v_wait, pl_v);
}

// The thesis ring disturbance: cap one vehicle for 60 s, then let it recover over 300 s.
fn apply_script(flags: u32, cap: f32) {
    if ((flags & F_SCRIPTED) == 0u || P.script_t0 <= 0.0 || cap <= 0.0) { return; }
    let t = f32(G.step) * P.dt;
    if (t < P.script_t0) { return; }
    let orig = ty.max_speed;
    var m = cap;
    if (t >= P.script_t0 + 60.0) { m = cap + (orig - cap) * min(1.0, (t - P.script_t0 - 60.0) / 300.0); }
    ty.max_speed = m;
}

fn route_has_next(route_i: u32, route_end: u32) -> bool { return route_i + 1u < route_end; }

// The link out of `lane` that continues the route. Among several, prefer one whose target lane can
// continue beyond the next edge.
fn pick_link(lane: u32, route_i: u32, route_end: u32) -> u32 {
    let l = lanes[lane];
    if (l.links_count == 0u) { return NONE; }
    if ((l.flags & LANE_INTERNAL) != 0u) { return l.links_start; }
    if (route_i + 1u >= route_end) { return NONE; }
    let want = routes[route_i + 1u];
    let after = route_i + 2u < route_end;
    var first = NONE;
    for (var k = 0u; k < l.links_count; k++) {
        let c = l.links_start + k;
        if (links[c].to_edge != want) { continue; }
        if (first == NONE) {
            first = c;
            if (!after) { return c; }
        }
        // Does the target lane reach the edge after next?
        let t = lanes[links[c].to_lane];
        let wanted2 = routes[route_i + 2u];
        for (var m = 0u; m < t.links_count; m++) {
            if (links[t.links_start + m].to_edge == wanted2) { return c; }
        }
    }
    return first;
}

fn push_item(link: u32, v_pass: f32, v_wait: f32, request: bool, arrival: f32, arr_speed: f32, braking: f32, dist: f32, leave: f32) {
    if (pl_n >= MAX_ITEMS) {
        atomicAdd(&C[C_ITEMS_FULL], 1u);
        return;
    }
    var it: Item;
    it.link = link;
    it.v_pass = v_pass;
    it.v_wait = v_wait;
    it.request = u32(request);
    it.arrival = arrival;
    it.arr_speed = arr_speed;
    it.braking = braking;
    it.dist = dist;
    it.leave = leave;
    items[pl_base + pl_n] = it;
    pl_n += 1u;
}

@compute @workgroup_size(64)
fn plan(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let ego = cur[i];
    ty = types[ego.vtype];
    dt = P.dt;
    ego_flags = ego.flags;
    ego_acc = ego.acc;
    mode_done = false;
    if ((ego.flags & F_SCRIPTED) != 0u && P.script_t0 > 0.0 && f32(G.step) * dt >= P.script_t0 && ego.v_next == 0.0) {
        cur[i].v_next = min(ty.max_speed, max(5.0, ego.speed - 5.0));
    }
    apply_script(ego.flags, cur[i].v_next);
    pl_i = i;
    pl_base = i * MAX_ITEMS;
    pl_n = 0u;
    pl_speed = ego.speed;
    pl_rng = ego.rng;

    let speed = ego.speed;
    let max_v = max_next_speed(speed);
    let v_min_comfort = min_next_speed(speed);
    var lane = ego.lane;
    var route_i = ego.route_i;
    pl_limit = lanes[lane].speed;
    pl_lane_vmax = lane_vmax(lane, ego.sf);
    var lane_max = max(pl_lane_vmax, v_min_comfort);
    pl_v = min(max_v, lane_max);
    let horizon = max_v * dt + brake_gap(max_v, ty.decel, ty.tau);
    var seen = lanes[lane].length - ego.pos;
    var had_non_internal = false;
    var seen_non_internal = 0.0;
    var seen_internal = 0.0;
    if (is_internal(lane)) { seen_internal = seen; }
    pl_pass = min(estimate_speed(seen, pl_v, ty.accel), lane_max);
    var slowed_for_minor = false;
    let leaving_junction = is_internal(lane);

    // The vehicle ahead on our own lane comes straight from the sorted order.
    var leader_index = NONE;
    if (i + 1u < G.n_active && cur[i + 1u].lane == lane) { leader_index = i + 1u; }
    var first_lane = true;

    loop {
        adapt_to_lane(lane, seen, first_lane, leader_index, ego.pos);
        if (pl_n > 0u) {
            let last = pl_base + pl_n - 1u;
            items[last].v_wait = min(items[last].v_wait, pl_v);
        }
        let internal = is_internal(lane);
        if (!internal && route_i + 1u >= ego.route_end) {
            // Final edge: drive through the arrival position.
            let len = lanes[lane].length;
            var ap = ego.arrival;
            if (ap < 0.0) { ap += len; }
            ap = min(ap, len);
            let arr_v = lane_max;
            let d = seen + ap - len - arr_v * dt;
            let va = max(EPS, free_speed(speed, d, arr_v, pl_lane_vmax));
            pl_v = min(pl_v, va);
            if (pl_n > 0u) { adapt_leave(pl_base + pl_n - 1u, va); }
            push_item(NONE, pl_v, pl_v, false, 0.0, 0.0, 0.0, seen, -1.0);
            break;
        }
        let link = pick_link(lane, route_i, ego.route_end);
        if (link == NONE) {
            let va = stop_speed(speed, seen, ty.decel, true, pl_lane_vmax);
            if (pl_n > 0u) { adapt_leave(pl_base + pl_n - 1u, va); }
            pl_v = min(va, pl_v);
            push_item(NONE, pl_v, pl_v, false, 0.0, 0.0, 0.0, seen, -1.0);
            break;
        }
        let lk = links[link];
        let state = link_state(link);
        let yellow_or_red = have_red(state) || have_yellow(state);
        var stop_decel = ty.decel;
        if (yellow_or_red) { stop_decel = max(min(P.tls_yellow_min_decel, ty.emergency), ty.decel); }
        let brake_dist = brake_gap(speed, stop_decel, 0.0);
        let can_brake = seen >= brake_dist;
        var stop_off: f32;
        if (yellow_or_red) {
            stop_off = 1.0;
        } else if (have_priority(state)) {
            stop_off = min(lk.visibility - POS_EPS, 1.0);
        } else {
            stop_off = min(lk.visibility - POS_EPS, 0.0);
        }
        if (can_brake) { stop_off = min(stop_off, seen - brake_dist); }
        stop_off = max(POS_EPS, stop_off);
        let stop_dist = max(0.0, seen - stop_off);
        let leaving_now = leaving_junction && pl_n == 0u;
        let abort_after_minor = slowed_for_minor && lk.before == NONE;
        pl_set_request = (pl_v > 0.1 * EPS * dt && !abort_after_minor) || leaving_now;
        let stop_v = stop_speed(speed, stop_dist, stop_decel, true, pl_lane_vmax);
        pl_v_wait = min(pl_v, stop_v);
        if (yellow_or_red && can_brake) {
            if (internal && seen < horizon + 30.0) {
                check_link_leader(link, lane, seen, ego.lane, ego.entry_step, ego.wait);
            }
            let arr = -dt + minimal_arrival_time(seen, pl_v, pl_pass);
            push_item(link, pl_v, pl_v_wait, false, arr, pl_v_wait, 0.0, seen, -1.0);
            break;
        }
        if (seen < horizon + 30.0) {
            check_link_leader(link, lane, seen, ego.lane, ego.entry_step, ego.wait);
        }
        if (pl_n > 0u) { adapt_leave(pl_base + pl_n - 1u, lane_max); }
        var arr_speed = pl_pass;
        let vis = lk.visibility;
        let determined = seen <= vis;
        let could_brake_minor = !have_priority(state) && brake_dist < seen && !last_was_cont_major(link);
        if (could_brake_minor && !determined) {
            let at_vis = safe_stop(vis, ty.decel, speed, 0.0, false);
            let max_arr = estimate_speed(vis, at_vis, ty.accel);
            arr_speed = min(pl_pass, max_arr);
            slowed_for_minor = true;
        } else if (state == CH_EQ && ego.wait > 0.0) {
            // SUMO detects circular yielding and backs out at random. Same effect, without the walk.
            var th = 0.75;
            if (ego.wait < 5.0) { th = 0.0; } else if (((lk.flags >> 8u) & 255u) == 115u) { th = 0.25; }
            pl_rng = pcg(pl_rng);
            if (f32(pl_rng >> 8u) / 16777216.0 < th) { pl_set_request = false; }
        }
        let arrival = -dt + minimal_arrival_time(seen, pl_v, arr_speed);
        var braking = 0.0;
        let bgap = brake_gap(pl_v, ty.decel, ty.tau);
        if (seen < bgap) {
            braking = min(minimal_arrival_speed_euler(seen, pl_v), arr_speed);
        }
        let next_lane = lk.next_lane;
        let leave_est = min(lane_vmax(next_lane, ego.sf), estimate_speed(lk.length, arr_speed, ty.accel));
        push_item(link, pl_v, pl_v_wait, pl_set_request, arrival, arr_speed, braking, seen, leave_est);
        if ((lk.flags & L_HAS_VIA) == 0u) {
            had_non_internal = true;
            route_i += 1u;
        }
        if ((!pl_set_request || pl_v <= 0.0 || seen > horizon) && had_non_internal
            && seen_non_internal > max(ty.length * 5.0, ty.length + seen_internal)) {
            break;
        }
        if (pl_n >= MAX_ITEMS) { break; }
        lane = next_lane;
        pl_limit = lanes[lane].speed;
        pl_lane_vmax = lane_vmax(lane, ego.sf);
        lane_max = pl_lane_vmax;
        let va = max(free_speed(speed, seen, lane_max, pl_lane_vmax), v_min_comfort - EPS);
        pl_v = min(va, pl_v);
        let len = lanes[lane].length;
        if (is_internal(lane)) { seen_internal += len; } else { seen_non_internal += len; }
        seen += len;
        pl_pass = min(estimate_speed(len, pl_v, ty.accel), lane_max);
        leader_index = NONE;
        if (lane_occupied(lane)) { leader_index = seg[lane].first; }
        first_lane = false;
    }
    cur[i].flags = ego_flags;
    cur[i].rng = pl_rng;
    cur[i].n_items = pl_n;
}

// ---------------------------------------------------------------- approach

// Junction blocking: do not ask for a link when the road behind it has no room for us.
fn exit_room(lane: u32) -> f32 {
    if (!lane_occupied(lane)) { return lanes[lane].length; }
    let s = seg[lane];
    let t = cur[s.first];
    if (t.speed > HALT_SPEED * 5.0) { return 1e6; }
    return t.pos - types[t.vtype].length;
}

@compute @workgroup_size(64)
fn approach(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let ego = cur[i];
    ty = types[ego.vtype];
    dt = P.dt;
    let base = i * MAX_ITEMS;
    let n = ego.n_items;
    let need = ty.length + ty.min_gap;
    var ahead = 0.0;
    let s = seg[ego.lane];
    if (s.end > i + 1u) { ahead = f32(min(s.end - i - 1u, 6u)) * need; }
    var cancel = false;
    var wants = false;
    for (var j = 0u; j < n; j++) {
        let it = items[base + j];
        if (it.link == NONE) { continue; }
        let k = links[it.link];
        var request = it.request != 0u;
        if (cancel) {
            request = false;
        } else if (request && (k.flags & L_KEEP_CLEAR) != 0u && (k.flags & L_HAS_FOES) != 0u && (k.flags & L_HAS_VIA) != 0u) {
            var room = exit_room(k.to_lane);
            if (room < 1e5 && lane_occupied(k.next_lane)) {
                room -= f32(seg[k.next_lane].end - seg[k.next_lane].first) * need;
            }
            if (room < 1e5 && room - ahead - need < 0.0 && lanes[k.to_lane].length > need) {
                if (it.dist >= brake_gap(ego.speed, ty.decel, ty.tau) + POS_EPS) {
                    cancel = true;
                    request = false;
                }
            }
        }
        if (it.request != u32(request)) { items[base + j].request = u32(request); }
        if (j == 0u && request) { wants = true; }
        if (it.arrival > CUTOFF) { continue; }
        let slot = atomicAdd(&link_count[it.link], 1u);
        if (slot >= SLOTS) {
            atomicAdd(&C[C_OVERFLOW], 1u);
            continue;
        }
        var a: Approach;
        a.arrival = it.arrival;
        var leave = it.leave;
        if (leave < 0.0) { leave = it.v_pass; }
        a.leave = it.arrival + (k.length + ty.length) / max((it.arr_speed + leave) * 0.5, EPS);
        a.arr_speed = it.arr_speed;
        a.leave_speed = leave;
        a.braking = it.braking;
        a.wait = ego.wait;
        a.dist = it.dist;
        a.speed = ego.speed;
        a.decel = ty.decel;
        a.will_pass = u32(request);
        a.trip = ego.trip;
        slots[it.link * SLOTS + slot] = a;
    }
    var flags = ego.flags & ~F_WILL_PASS;
    if (wants) { flags |= F_WILL_PASS; }
    cur[i].flags = flags;
}

// ---------------------------------------------------------------- execute

var<private> ex_foe_brake_arr: f32;

fn unsafe_merge(v_leader: f32, v_follower: f32, b_leader: f32, b_follower: f32) -> bool {
    return v_leader * v_leader / b_leader <= v_follower * v_follower / b_follower;
}

fn foe_arrival(a: f32, r: Approach, impatience: f32) -> f32 {
    ex_foe_brake_arr = r.braking;
    if (impatience <= 0.0 || a >= r.arrival) { return r.arrival; }
    if (floor(a / dt) == floor(r.arrival / dt)) { return r.arrival; }
    let ac = ceil(a / dt) * dt;
    let m = r.decel * impatience;
    let d_t = r.arrival - ac;
    if (d_t <= 0.0) { return r.arrival; }
    let d = d_t * m;
    let aa = d_t * d / 2.0;
    let v = r.dist / (r.arrival + dt);
    let x_dist = r.dist - v * ac;
    var fa_brake: f32;
    if (v * v / (2.0 * m) <= x_dist) {
        fa_brake = r.arrival + 30.0;
        ex_foe_brake_arr = 0.0;
    } else {
        let x = (-0.5 * sqrt(max(0.0, 4.0 * (v - d) * (v - d) - 8.0 * m * aa)) - d + v) / m;
        ex_foe_brake_arr = v - (d_t + x) * m;
        fa_brake = r.arrival + x;
    }
    return (1.0 - impatience) * r.arrival + impatience * fa_brake;
}

fn blocked_by_foe(r: Approach, a: f32, l: f32, va: f32, vl: f32, same_target: bool, impatience: f32, decel: f32, wait: f32, foe_state: u32) -> bool {
    if (r.will_pass == 0u) { return false; }
    var h = ty.timegap_minor;
    if (foe_state == CH_Z) { h = 16.0; }
    if (foe_state == CH_w) {
        if (wait > r.wait + dt) { return false; }
        if (wait == r.wait + dt && a < r.arrival + dt) { return false; }
    }
    let fa = foe_arrival(a, r, impatience);
    if (r.leave < a) {
        return same_target && (a - r.leave < h || unsafe_merge(r.leave_speed, va, r.decel, decel));
    } else if (fa > l + h) {
        return same_target && unsafe_merge(vl, ex_foe_brake_arr, decel, r.decel);
    }
    return true;
}

fn link_opened(link: u32, a: f32, va: f32, vl: f32, veh_len: f32, impatience: f32, decel: f32, wait: f32, trip: u32) -> bool {
    let k = links[link];
    let state = link_state(link);
    if (have_red(state)) { return false; }
    if ((k.flags & L_CONT) != 0u) { return true; }
    let l = a + (k.length + veh_len) / max((va + vl) * 0.5, EPS);
    let e_is_major_green = (k.flags & (L_EXIT_AFTER_IJ | L_INTERNAL_JUNCTION)) != 0u && link_state(k.entry) == CH_G;
    if ((have_priority(state) || e_is_major_green) && state != CH_Z) { return true; }
    if (state == CH_w && wait < dt) { return false; }
    if (state == CH_s && wait < dt) { return false; }
    for (var f = 0u; f < k.foe_count; f++) {
        let foe = foes[k.foe_start + f];
        let same_target = links[foe].to_lane == k.to_lane;
        let foe_state = link_state(foe);
        // A foe held at red cannot arrive.
        let cnt = min(atomicLoad(&link_count[foe]), SLOTS);
        for (var s = 0u; s < cnt; s++) {
            let r = slots[foe * SLOTS + s];
            if (r.trip == trip) { continue; }
            if (blocked_by_foe(r, a, l, va, vl, same_target, impatience, decel, wait, foe_state)) { return false; }
        }
    }
    return true;
}

fn finalize_speed(v_pos: f32, old_v: f32, lane_vmax_: f32, rng: ptr<private, u32>) -> f32 {
    let v_e = min_next_speed_emergency(old_v);
    let v_min = min(min_next_speed(old_v), max(v_pos, v_e));
    let a_max = (max(lane_vmax_, v_pos) - old_v) / dt;
    let v_max = max(v_min, min(min(old_v + a_max * dt, max_next_speed(old_v)), v_pos));
    if (ty.model == MODEL_KRAUSS) {
        let r = rand01(rng);
        var s = v_max;
        if (s < ty.accel) {
            s -= dt * ty.sigma * s * r;
        } else {
            s -= dt * ty.sigma * ty.accel * r;
        }
        return max(v_min, max(0.0, s));
    }
    return v_max;
}

var<private> ex_rng: u32;

@compute @workgroup_size(64)
fn exec(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    var e = cur[i];
    e.flags &= ~F_LANE_CHANGED;
    ty = types[e.vtype];
    dt = P.dt;
    apply_script(e.flags, e.v_next);
    let base = i * MAX_ITEMS;
    let n = e.n_items;
    let speed = e.speed;
    var v_safe = speed;
    var v_safe_min = 0.0;
    var v_safe_min_dist = 0.0;
    var can_brake_min = false;

    let impat = clamp(ty.impatience + e.wait / P.time_to_impatience, 0.0, 1.0);
    for (var j = 0u; j < n; j++) {
        let it = items[base + j];
        if (it.link != NONE && it.request != 0u) {
            let state = link_state(it.link);
            let yellow = have_yellow(state);
            let can_brake = it.dist > brake_gap(speed, ty.decel, 0.0) || speed < ty.decel * dt;
            if (yellow && can_brake) {
                v_safe = it.v_wait;
                break;
            }
            var leave = it.leave;
            if (leave < 0.0) { leave = it.v_pass; }
            var imp = 1.0;
            if (can_brake) { imp = impat; }
            let opened = yellow || link_opened(it.link, it.arrival, it.arr_speed, leave, ty.length, imp, ty.decel, e.wait, e.trip);
            let k = links[it.link];
            let determined = it.dist <= k.visibility;
            if (opened && !have_priority(state) && !last_was_cont_major(it.link) && (k.flags & L_CONT) == 0u) {
                if (!determined && (can_brake || !yellow)) {
                    v_safe = it.v_wait;
                    break;
                } else {
                    v_safe_min_dist = it.dist;
                    v_safe_min = min(min((it.dist + POS_EPS) / dt, it.v_pass), max_next_speed(speed));
                    can_brake_min = can_brake;
                }
            }
            if (opened) {
                v_safe = it.v_pass;
            } else if (!can_brake && k.tl == NONE && it.dist < brake_gap(speed, ty.emergency, 0.0)) {
                v_safe = it.v_pass;
            } else {
                v_safe = it.v_wait;
                break;
            }
        } else {
            v_safe = it.v_wait;
            break;
        }
    }
    if (v_safe + EPS < v_safe_min) {
        if (can_brake_min && v_safe < speed) {
            v_safe = min(v_safe, max(min_next_speed(speed), stop_speed(speed, v_safe_min_dist, ty.decel, true, lane_vmax(e.lane, e.sf))));
            v_safe_min = 0.0;
        } else {
            v_safe_min = v_safe;
        }
    }

    ex_rng = e.rng;
    let vmax_here = lane_vmax(e.lane, e.sf);
    var v_next = finalize_speed(v_safe, speed, vmax_here, &ex_rng);
    e.rng = ex_rng;
    v_next = max(v_next, v_safe_min);
    if (v_next < 0.1 * EPS * dt) { v_next = 0.0; }

    // Cooperative requests from neighbours.
    let adv = atomicExchange(&advice[e.trip], NONE);
    if (adv != NONE) {
        let wanted = f32(adv) / 1024.0;
        v_next = min(v_next, max(wanted, min_next_speed(speed)));
    }

    let acc = (v_next - speed) / dt;
    let old_pos = e.pos;
    e.pos += v_next * dt;
    e.speed = v_next;
    e.acc = acc;

    // Waiting and time loss.
    if (v_next <= HALT_SPEED && acc <= 0.5 * ty.accel) {
        e.wait += dt;
        e.tot_wait += dt;
        if ((e.flags & F_WAITING) == 0u) {
            e.wait_count += 1u;
            e.flags |= F_WAITING;
        }
    } else {
        e.wait = 0.0;
        e.flags &= ~F_WAITING;
    }

    // Detector crossing for actuated signals.
    let det = lanes[e.lane].det_pos;
    if (det >= 0.0 && old_pos < det && e.pos >= det) { last_detect[e.lane] = G.step; }

    // Cross onto the following lanes.
    var j = 0u;
    let first_lane = e.lane;
    loop {
        let len = lanes[e.lane].length;
        let on_final = !is_internal(e.lane) && e.route_i + 1u >= e.route_end;
        if (on_final) { break; }
        if (e.pos <= len) { break; }
        var link = NONE;
        if (j < n) { link = items[base + j].link; }
        if (link == NONE) {
            // Nowhere to go: this only happens on a dead end.
            e.pos = len;
            e.speed = 0.0;
            break;
        }
        let k = links[link];
        e.pos -= len;
        e.route_len += len;
        e.prev2_lane = e.prev_lane;
        e.prev_lane = e.lane;
        e.lane = k.next_lane;
        if ((k.flags & L_HAS_VIA) == 0u) { e.route_i += 1u; }
        if (is_internal(e.lane) && !is_internal(e.prev_lane)) { e.entry_step = G.step; }
        if (!is_internal(e.lane)) {
            e.entry_step = NONE;
            e.flags |= F_BEST_DIRTY;
            atomicAdd(&edge_acc[lanes[e.lane].edge * 4u + 2u], 1u);
        }
        j += 1u;
        if (j >= MAX_ITEMS) { break; }
    }

    let vmax_after = lane_vmax(e.lane, e.sf);
    if (vmax_after > 0.0) { e.time_loss += dt * (vmax_after - v_next) / vmax_after; }

    // Arrival.
    let llen = lanes[e.lane].length;
    if (!is_internal(e.lane) && e.route_i + 1u >= e.route_end) {
        var ap = e.arrival;
        if (ap < 0.0) { ap += llen; }
        ap = min(ap, llen);
        if (e.pos > ap - POS_EPS) {
            var out: TripOut;
            out.depart_step = e.depart_step;
            out.arrive_step = G.step + 1u;
            out.wait = e.tot_wait;
            out.time_loss = e.time_loss;
            out.route_len = e.route_len + ap;
            out.wait_count = e.wait_count;
            out.flags = 1u;
            trip_out[e.trip] = out;
            e.flags |= F_REMOVED;
            atomicAdd(&C[C_ARRIVED], 1u);
            cur[i] = e;
            return;
        }
    }

    // Teleport the head of a lane that has been stuck for too long.
    if (P.teleport_steps != 0u && e.wait > f32(P.teleport_steps) * dt) {
        let s0 = seg[first_lane];
        if (first_lane == e.lane && i + 1u == s0.end) {
            teleport(&e);
        }
    }

    // Publish where the vehicle is for lane changing, insertion and next step's planning.
    let back = e.pos - ty.length;
    if (back < 0.0 && e.prev_lane != NONE) {
        let plen = lanes[e.prev_lane].length;
        let b2 = plen + back;
        atomicMin(&partial_occ[e.prev_lane], pack_back(b2, e.speed));
        atomicMin(&tail[e.prev_lane], pack_back(b2, e.speed));
        if (b2 < 0.0 && e.prev2_lane != NONE) {
            let b3 = lanes[e.prev2_lane].length + b2;
            atomicMin(&partial_occ[e.prev2_lane], pack_back(b3, e.speed));
            atomicMin(&tail[e.prev2_lane], pack_back(b3, e.speed));
        }
    }
    let s = seg[first_lane];
    if (e.lane != first_lane || i == s.first) {
        atomicMin(&tail[e.lane], pack_back(back, e.speed));
    }
    if (e.lane != first_lane) {
        atomicMin(&entrant[e.lane], (u32(clamp(e.pos, 0.0, 127.0) * 8.0) << 22u) | i);
    }
    cur[i] = e;
}

// MSVehicleTransfer: lift the vehicle off the road and put it down further along its route.
fn teleport(e: ptr<function, Veh>) {
    atomicAdd(&C[C_TELEPORTS], 1u);
    (*e).wait = 0.0;
    if ((*e).route_i + 1u >= (*e).route_end) {
        (*e).flags |= F_REMOVED;
        return;
    }
    (*e).route_i += 1u;
    let ed = edges[routes[(*e).route_i]];
    // Least occupied lane of the next edge that continues the route.
    var best_lane = ed.first_lane;
    var best_n = 0xffffffffu;
    for (var l = 0u; l < ed.lane_count; l++) {
        let cand = ed.first_lane + l;
        if ((lanes[cand].allow & ty.vclass) == 0u) { continue; }
        var count = 0u;
        if (lane_occupied(cand)) { count = seg[cand].end - seg[cand].first; }
        if (count < best_n) {
            best_n = count;
            best_lane = cand;
        }
    }
    (*e).lane = best_lane;
    (*e).pos = min(ty.length, lanes[best_lane].length);
    (*e).speed = 0.0;
    (*e).acc = 0.0;
    (*e).prev_lane = NONE;
    (*e).prev2_lane = NONE;
    (*e).entry_step = NONE;
    (*e).flags |= F_BEST_DIRTY;
}

// ---------------------------------------------------------------- GLOSA, MSDevice_GLOSA

fn glosa_earliest(dist: f32, vmax: f32, v: f32) -> f32 {
    let a = ty.accel;
    let ph = v / a;
    let tc = -ph + sqrt(ph * ph + 2.0 * dist / a);
    let at = min((vmax - v) / a, tc);
    let rem = dist - (v * at + a * at * at / 2.0);
    return at + rem / vmax;
}

fn phase_char(first: u32, p: u32, idx: u32) -> u32 { return states[phases[first + p].state_start + idx]; }

@compute @workgroup_size(64)
fn glosa(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let vt = cur[i].vtype;
    if (types[vt].glosa_range <= 0.0) { return; }
    var e = cur[i];
    if ((e.flags & F_REMOVED) != 0u) { return; }
    ty = types[vt];
    dt = P.dt;
    let orig = trips[e.trip].sf;
    var lane = e.lane;
    var r = e.route_i;
    var seen = lanes[lane].length - e.pos;
    var link = pick_link(lane, r, e.route_end);
    var found = NONE;
    for (var hops = 0u; hops < 12u && link != NONE; hops++) {
        if (!is_internal(lane) && links[link].tl != NONE) {
            found = link;
            break;
        }
        if (seen > ty.glosa_range + 200.0) { break; }
        if ((links[link].flags & L_HAS_VIA) == 0u) { r += 1u; }
        lane = links[link].next_lane;
        seen += lanes[lane].length;
        link = pick_link(lane, r, e.route_end);
    }
    var flags = e.flags;
    var sf = e.sf;
    if (found == NONE) {
        if ((flags & F_GLOSA_ACTIVE) != 0u) {
            sf = orig;
            flags &= ~F_GLOSA_ACTIVE;
        }
    } else if (seen <= ty.glosa_range) {
        let k = links[found];
        let ts = tls[k.tl];
        let state = link_state(found);
        var green = have_green(state);
        var stop = have_red(state) || have_yellow(state);
        let n = ts.n_phases;
        let limit = lanes[e.lane].speed;
        let vmax = min(limit * sf, ty.max_speed);
        let v = e.speed;
        let tjunc = glosa_earliest(seen, vmax, v);
        // getTimeToSwitch
        var count_old = 0u;
        var next_switch = f32(ts.next_switch - min(ts.next_switch, G.step)) * dt;
        for (var c = 1u; c < n; c++) {
            let p = (ts.phase + c) % n;
            let ls = phase_char(ts.first_phase, p, k.tl_index);
            let is_g = have_green(ls);
            if ((stop && is_g) || (green && !is_g)) {
                count_old = ts.phase + c;
                break;
            }
            next_switch += f32(phases[ts.first_phase + p].duration) * dt;
        }
        var offset = 0.0;
        for (var w = 1u; w < 11u; w++) {
            if (green) {
                if ((flags & F_GLOSA_ACTIVE) != 0u && orig > sf) {
                    sf = orig;
                    flags &= ~F_GLOSA_ACTIVE;
                }
                if (tjunc > next_switch) {
                    let max_factor = 1.1;
                    if (max_factor > orig) {
                        let v2 = min(limit * sf, ty.max_speed) / sf * max_factor;
                        if (glosa_earliest(seen, v2, v) <= next_switch) {
                            sf = max_factor;
                            flags |= F_GLOSA_ACTIVE;
                            break;
                        }
                    }
                } else {
                    break;
                }
            } else if (stop) {
                // adaptSpeed
                let w_v = limit * orig;
                let t_s = next_switch;
                let a = ty.accel;
                let s = seen;
                let root_c = a * a * t_s * t_s - 2.0 * a * w_v * t_s + 2.0 * a * s;
                var v_const = 0.0;
                if (root_c >= 0.0) { v_const = sqrt(root_c) - a * t_s + w_v; }
                var d = ty.decel;
                if (v < v_const) { d = a; }
                let root = a * d * ((2.0 * d * (s - w_v * t_s)) - ((v - w_v) * (v - w_v)) + (a * ((d * t_s * t_s) + 2.0 * (s - t_s * v))));
                if (root < 0.0) { break; }
                let x = ((a * (v - d * t_s)) + d * w_v + sqrt(root)) / (d + a);
                var y = (v - x) / d;
                if (v < x) { y = (x - v) / d; }
                if (s < (w_v * w_v - x * x) / 2.0 / a) {
                    sf = orig;
                    flags &= ~F_GLOSA_ACTIVE;
                } else if (!(x >= 5.0 && x <= w_v && y < t_s)) {
                    if (x < 5.0) { break; }
                } else {
                    let vt2 = max(x, min_next_speed(v));
                    sf = vt2 / limit;
                    flags |= F_GLOSA_ACTIVE;
                    break;
                }
            }
            // getTimeToNextSwitch
            var extra = 0.0;
            let cur_p = count_old;
            for (var c = 0u; c < n; c++) {
                let p = (cur_p + c) % n;
                let ls = phase_char(ts.first_phase, p, k.tl_index);
                let is_g = have_green(ls);
                if (green && is_g) { count_old = p; break; }
                if (stop && !is_g) { count_old = p; break; }
                extra += f32(phases[ts.first_phase + p].duration) * dt;
            }
            green = !green;
            stop = !stop;
            next_switch += extra;
            if (next_switch > 80.0) {
                next_switch += offset;
                offset = 6.0;
                next_switch -= offset;
            } else if (next_switch > 60.0) {
                next_switch += offset;
                offset = 4.0;
                next_switch -= offset;
            } else if (next_switch > 40.0) {
                next_switch += offset;
                offset = 3.0;
                next_switch -= offset;
            } else if (next_switch > 20.0) {
                next_switch += offset;
                offset = 2.0;
                next_switch -= offset;
            }
        }
    }
    if (sf != e.sf) { cur[i].sf = sf; }
    if (flags != e.flags) { cur[i].flags = flags; }
}

// ---------------------------------------------------------------- insertion

// The rear-most thing on a lane right now: back position, speed.
fn lane_tail_back(l: u32) -> u32 {
    return atomicLoad(&tail[l]);
}

fn lane_is_good(l: u32, route_i: u32, route_end: u32) -> bool {
    if ((lanes[l].allow & ty.vclass) == 0u) { return false; }
    if (route_i + 1u >= route_end) { return true; }
    let want = routes[route_i + 1u];
    let la = lanes[l];
    for (var k = 0u; k < la.links_count; k++) {
        if (links[la.links_start + k].to_edge == want) { return true; }
    }
    return false;
}

fn lane_load(l: u32) -> u32 {
    var count = 0u;
    if (lane_occupied(l)) { count = seg[l].end - seg[l].first; }
    if (atomicLoad(&tail[l]) != NONE) { count += 1u; }
    return count;
}

fn choose_lane(ed: Edge, t: Trip, rng: ptr<private, u32>) -> u32 {
    let mode = t.depart_lane;
    if (mode >= 0) {
        if (u32(mode) < ed.lane_count) { return ed.first_lane + u32(mode); }
        return NONE;
    }
    if (mode == -2) {
        // random among allowed
        var cnt = 0u;
        for (var l = 0u; l < ed.lane_count; l++) {
            if ((lanes[ed.first_lane + l].allow & ty.vclass) != 0u) { cnt += 1u; }
        }
        if (cnt == 0u) { return NONE; }
        var pick = u32(rand01(rng) * f32(cnt));
        for (var l = 0u; l < ed.lane_count; l++) {
            if ((lanes[ed.first_lane + l].allow & ty.vclass) != 0u) {
                if (pick == 0u) { return ed.first_lane + l; }
                pick -= 1u;
            }
        }
        return NONE;
    }
    if (mode == -1) {
        // first allowed
        for (var l = 0u; l < ed.lane_count; l++) {
            if ((lanes[ed.first_lane + l].allow & ty.vclass) != 0u) { return ed.first_lane + l; }
        }
        return NONE;
    }
    // free, allowed, best: the emptiest lane, limited to lanes reaching the next edge unless free.
    var best = NONE;
    var best_load = 0xffffffffu;
    for (var round = 0u; round < 2u; round++) {
        for (var l = 0u; l < ed.lane_count; l++) {
            let c = ed.first_lane + l;
            if ((lanes[c].allow & ty.vclass) == 0u) { continue; }
            if (round == 0u && mode != -3 && !lane_is_good(c, t.route_start, t.route_end)) { continue; }
            var load = lane_load(c);
            let packed = atomicLoad(&tail[c]);
            if (packed != NONE) {
                let vmax = min(lanes[c].speed * t.sf, ty.max_speed);
                let pos = min(ty.length + POS_EPS, ed.length);
                let gap = unpack_back(packed) - pos - ty.min_gap;
                let safe = min(vmax, safe_follow(gap, vmax, unpack_speed(packed), ty.apparent, true));
                load += u32(max(0.0, vmax - safe) * 1000.0) * 1024u;
            }
            if (load < best_load) {
                best_load = load;
                best = c;
            }
        }
        if (best != NONE) { break; }
    }
    return best;
}

var<private> ins_rng: u32;

fn try_insert(q: u32, trip_i: u32, t: Trip) -> bool {
    ty = types[t.vtype];
    dt = P.dt;
    ins_rng = t.rng;
    let ed = edges[queues[q].edge];
    let lane = choose_lane(ed, t, &ins_rng);
    if (lane == NONE) { return false; }
    let la = lanes[lane];

    var pos: f32;
    switch t.depart_pos_mode {
        case 1u: {
            pos = t.depart_pos;
            if (pos < 0.0) { pos += la.length; }
        }
        case 2u: { pos = rand01(&ins_rng) * la.length; }
        default: { pos = min(ty.length + POS_EPS, ed.length); }
    }
    pos = min(pos, la.length);

    let vmax = min(la.speed * t.sf, ty.max_speed);
    var speed = 0.0;
    var patch_speed = false;
    switch t.depart_speed_mode {
        case 1u: { speed = t.depart_speed; }
        case 2u: { speed = rand01(&ins_rng) * vmax; patch_speed = true; }
        case 3u: { speed = vmax; patch_speed = true; }
        case 4u: { speed = vmax; }
        case 5u: { speed = min(la.speed, ty.max_speed); }
        default: {}
    }

    // Leader and follower on the lane, from this step's positions.
    var lead_back = 1e9;
    var lead_v = 0.0;
    var lead_b = ty.apparent;
    var foll = NONE;
    let p = atomicLoad(&tail[lane]);
    if (lane_occupied(lane) || p != NONE) {
        let s = seg[lane];
        var lo = s.first;
        var hi = s.end;
        if (!lane_occupied(lane)) { hi = lo; }
        for (var k = lo; k < hi; k++) {
            let o = cur[k];
            if (o.lane != lane || (o.flags & F_REMOVED) != 0u) { continue; }
            let ot = types[o.vtype];
            let back = o.pos - ot.length;
            if (o.pos >= pos) {
                if (back < lead_back) {
                    lead_back = back;
                    lead_v = o.speed;
                    lead_b = ot.apparent;
                }
            } else {
                foll = k;
            }
            if (back > pos + 500.0) { break; }
        }
        if (p != NONE) {
            let b = unpack_back(p);
            if (b >= pos - ty.length - 0.125 && b < lead_back) {
                lead_back = b;
                lead_v = unpack_speed(p);
            }
        }
    }

    let gap = lead_back - pos - ty.min_gap;
    if (lead_back < 1e8) {
        if (gap < 0.0) { return false; }
        // The speed we may start with behind the leader, as SUMO's insertionFollowSpeed.
        let vsafe = safe_follow(gap, speed, lead_v, lead_b, true);
        if (vsafe < speed) {
            if (patch_speed) { speed = vsafe; } else { return false; }
        }
    }
    if (foll != NONE) {
        let o = cur[foll];
        let ot = types[o.vtype];
        let fg = pos - ty.length - o.pos - ot.min_gap;
        if (fg < 0.0) { return false; }
        // The follower must be able to keep following us.
        let save = ty;
        ty = ot;
        let need = secure_gap(o.speed, speed, save.apparent);
        ty = save;
        if (fg < need) { return false; }
    }
    // Keep enough distance to stop at the lane end when the next link is closed for us.
    let seen = la.length - pos;
    if (t.route_end > t.route_start + 1u) {
        let want = routes[t.route_start + 1u];
        for (var k = 0u; k < la.links_count; k++) {
            let c = la.links_start + k;
            if (links[c].to_edge == want) {
                let st = link_state(c);
                if (have_red(st) || have_yellow(st)) {
                    let vstop = safe_stop(seen - POS_EPS, ty.decel, speed, ty.tau, false);
                    if (vstop < speed) {
                        if (patch_speed) { speed = vstop; } else { return false; }
                    }
                }
                break;
            }
        }
    }

    let idx = G.n_active + atomicAdd(&C[C_NEW], 1u);
    if (idx >= P.capacity) {
        atomicSub(&C[C_NEW], 1u);
        return false;
    }
    var e: Veh;
    e.pos = pos;
    e.speed = speed;
    e.lane = lane;
    e.route_i = t.route_start;
    e.acc = 0.0;
    e.sf = t.sf;
    e.vtype = t.vtype;
    e.trip = trip_i;
    e.rng = ins_rng;
    e.route_end = t.route_end;
    e.arrival = t.arrival;
    e.flags = F_BEST_DIRTY;
    if (t.script != 0u) { e.flags |= F_SCRIPTED; }
    e.entry_step = NONE;
    e.prev_lane = NONE;
    e.prev2_lane = NONE;
    e.depart_step = G.step;
    e.replica = t.replica;
    e.route_len = -pos;
    e.look_v = speed;
    e.best_cur = 1e9;
    e.best_left = 0.0;
    e.best_right = 0.0;
    cur[idx] = e;
    atomicAdd(&C[C_INSERTED], 1u);
    let lb = pack_back(pos - ty.length, speed);
    atomicMin(&tail[lane], lb);
    return true;
}

@compute @workgroup_size(16)
fn insert(@builtin(global_invocation_id) id: vec3u) {
    let q = id.x;
    if (q >= P.n_queues) { return; }
    let qq = queues[q];
    if (qq.next >= qq.end) { return; }
    let n_lanes = edges[qq.edge].lane_count;
    var next = qq.next;
    for (var attempt = 0u; attempt < n_lanes; attempt++) {
        if (next >= qq.end) { break; }
        let ti = queue_trips[next];
        let t = trips[ti];
        if (t.depart_step > G.step) { break; }
        if (!try_insert(q, ti, t)) { break; }
        next += 1u;
    }
    if (next != qq.next) { queues[q].next = next; }
}

// ---------------------------------------------------------------- statistics

@compute @workgroup_size(64)
fn sample_stats(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let e = cur[i];
    if ((e.flags & F_REMOVED) != 0u) { return; }
    // series: running, halting, speed sum in mm/s, relative speed sum in 1/1000
    let at = (G.sample * P.n_replicas + e.replica) * 4u;
    atomicAdd(&series[at], 1u);
    if (e.speed < HALT_SPEED) { atomicAdd(&series[at + 1u], 1u); }
    atomicAdd(&series[at + 2u], u32(e.speed * 100.0));
    let la = lanes[e.lane];
    atomicAdd(&series[at + 3u], u32(e.speed / la.speed * 1000.0));
    if ((la.flags & LANE_INTERNAL) == 0u) {
        // per edge: samples, distance in 1/8 m, entered, spare
        atomicAdd(&edge_acc[la.edge * 4u], 1u);
        atomicAdd(&edge_acc[la.edge * 4u + 1u], u32(e.speed * 8.0 * P.dt * f32(P.sample_steps)));
    }
}

@compute @workgroup_size(1)
fn next_sample() {
    G.sample += 1u;
}
