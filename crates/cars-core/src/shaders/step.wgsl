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
@group(0) @binding(17) var<storage, read> incoming_links: array<u32>;
@group(0) @binding(18) var<storage, read_write> adv_flags: array<atomic<u32>>;
@group(0) @binding(31) var<storage, read_write> advice: array<atomic<u32>>;
@group(0) @binding(32) var<storage, read> queue_trips: array<u32>;
@group(0) @binding(33) var<storage, read_write> claims: array<atomic<u32>>;
@group(0) @binding(34) var<storage, read_write> last_detect: array<u32>;
@group(0) @binding(19) var<storage, read_write> lane_free: array<LaneFree>;
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
    if ((links[l].flags & L_COORD) != 0u) { return CH_r; }
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
    if (now < s.next_switch) { return; }
    let ph = phases[s.first_phase + s.phase];
    if (s.actuated != 0u) {
        // gapControl and duration of MSActuatedTrafficLightLogic.
        let elapsed = now - s.last_change;
        if (elapsed < ph.max_dur) {
            var gap = 1e9;
            for (var k = 0u; k < ph.loops_count; k++) {
                let at = last_detect[incoming_links[ph.loops_start + k]];
                if (at == 0u) { continue; }
                let since = now - at;
                gap = min(gap, select((f32(since) - 1.5) * P.dt, 0.0, since <= 1u));
            }
            if (gap < 3.0) {
                let until = ceil(f32(elapsed) * P.dt + max(2.0 - gap, 0.001));
                let wait = max(u32(ceil(until / P.dt)), elapsed + 1u) - elapsed;
                s.next_switch = now + min(wait, ph.max_dur - elapsed);
                tls[t] = s;
                return;
            }
        }
    }
    s.phase = (s.phase + 1u) % s.n_phases;
    s.last_change = now;
    let next_phase = phases[s.first_phase + s.phase];
    s.next_switch = now + select(next_phase.duration, next_phase.min_dur, s.actuated != 0u);
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
}

// Back position in 1/8 m, then a CACC bit and the speed in 1/256 m/s.
fn pack_back(back: f32, speed: f32, cacc: u32) -> u32 {
    return (u32(clamp(back, 0.0, 8000.0) * 8.0) << 16u) | (cacc << 15u) | u32(clamp(speed, 0.0, 127.0) * 256.0);
}
fn is_cacc(t: VType) -> u32 { return u32(t.model == MODEL_CACC); }
fn unpack_back(p: u32) -> f32 { return f32(p >> 16u) / 8.0; }
fn unpack_speed(p: u32) -> f32 { return f32(p & 0x7fffu) / 256.0; }
fn unpack_cacc(p: u32) -> bool { return (p & 0x8000u) != 0u; }

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
            adapt_to_leader(gap, seen, l_len, unpack_speed(p), ty.apparent, unpack_cacc(p), true, extra);
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
    if (pl_n > 0u) { adapt_leave(pl_base + pl_n - 1u, vsafe); }
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
                    let stop_asap = cannot_ignore;
                    let crossing = select(dist_cross, -1.0, stop_asap);
                    adapt_to_junction_leader(gap, critical, seen, l_len, crossing, f.speed, ft.apparent, ft.model == MODEL_CACC);
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
                    let crossing = select(dist_cross, -1.0, same_target || same_source);
                    adapt_to_junction_leader(gap, false, seen, l_len, crossing, unpack_speed(p), ty.apparent, unpack_cacc(p));
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

// Only the links it will cross: cj_apply has decided the speed.
fn plan_cj(i: u32, ego: Veh) {
    pl_base = i * MAX_ITEMS;
    pl_n = 0u;
    var lane = ego.lane;
    var route_i = ego.route_i;
    var seen = lanes[lane].length - ego.pos;
    let reach = 2.0 * max(ego.speed, ty.max_speed) * dt + 5.0;
    loop {
        if (!is_internal(lane) && route_i + 1u >= ego.route_end) {
            push_item(NONE, 1e9, 1e9, false, 0.0, 0.0, 0.0, seen, -1.0);
            break;
        }
        let link = pick_link(lane, route_i, ego.route_end);
        if (link == NONE) {
            push_item(NONE, 1e9, 1e9, false, 0.0, 0.0, 0.0, seen, -1.0);
            break;
        }
        push_item(link, 1e9, 1e9, false, 0.0, 0.0, 0.0, seen, -1.0);
        if (seen > reach || pl_n >= MAX_ITEMS) { break; }
        let lk = links[link];
        if ((lk.flags & L_HAS_VIA) == 0u) { route_i += 1u; }
        lane = lk.next_lane;
        seen += lanes[lane].length;
    }
    cur[i].n_items = pl_n;
}

@compute @workgroup_size(64)
fn plan(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let ego = cur[i];
    if (ego.lane == P.dummy_lane) {
        cur[i].n_items = 0u;
        return;
    }
    ty = types[ego.vtype];
    dt = P.dt;
    if (cj_controlled(ego)) {
        plan_cj(i, ego);
        return;
    }
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
        lane_max = lane_vmax(lane, ego.sf);
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

const FREE_STOPPED: u32 = 1u;
const FREE_LAST_WAITS: u32 = 2u;

// MSLane::getSpaceTillLastStanding and getBruttoVehLenSum, once per occupied lane.
@compute @workgroup_size(64)
fn lane_free_scan(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let lane = cur[i].lane;
    if (i != 0u && cur[i - 1u].lane == lane) { return; }
    let roundabout = (lanes[lane].flags & LANE_ROUNDABOUT) != 0u;
    let end = seg[lane].end;
    var f: LaneFree;
    f.space = lanes[lane].length;
    var lengths = 0.0;
    var stopped = false;
    var speed_sum = 0.0;
    if ((cur[i].flags & F_HAVE_TO_WAIT) != 0u) { f.flags = FREE_LAST_WAITS; }
    for (var k = i; k < end; k++) {
        let vt = types[cur[k].vtype];
        let speed = cur[k].speed;
        speed_sum += speed;
        if (!stopped && speed < HALT_SPEED && !roundabout) {
            stopped = true;
            f.flags |= FREE_STOPPED;
            f.space = cur[k].pos - vt.length + brake_gap(speed, vt.decel, vt.tau) - lengths;
        }
        lengths += vt.length + vt.min_gap;
    }
    if (!stopped) { f.space -= lengths; }
    f.brutto = lengths;
    f.mean_speed = speed_sum / f32(max(end - i, 1u));
    lane_free[lane] = f;
}

var<private> av0: vec4f;
var<private> av1: vec4f;

fn av_get(j: u32) -> f32 {
    if (j < 4u) { return av0[j]; }
    return av1[j - 4u];
}

fn av_set(j: u32, v: f32) {
    if (j < 4u) { av0[j] = v; } else { av1[j - 4u] = v; }
}

fn keep_clear(k: Link) -> bool {
    return (k.flags & L_KEEP_CLEAR) != 0u && (k.flags & L_HAS_FOES) != 0u;
}

// MSLink::opened for a link further ahead, at planning time: what foes announced in the last step.
fn foe_on_last_approach(link: u32, a: f32, va: f32, vl: f32, ego: Veh) -> bool {
    let k = links[link];
    let l = a + (k.length + ty.length) / max((va + vl) * 0.5, EPS);
    let impat = clamp(ty.impatience + ego.wait / P.time_to_impatience, 0.0, 1.0);
    for (var f = 0u; f < k.foe_count; f++) {
        let foe = foes[k.foe_start + f];
        let same_target = links[foe].to_lane == k.to_lane;
        let foe_state = link_state(foe);
        for (var s = 0u; s < SLOTS; s++) {
            let r = slots[foe * SLOTS + s];
            if (r.stamp + 1u < G.step || r.trip == ego.trip) { continue; }
            if (blocked_by_foe(r, a, l, va, vl, same_target, impat, ty.decel, ego.wait, foe_state)) { return true; }
        }
    }
    return false;
}

// MSVehicle::checkRewindLinkLanes.
fn check_rewind(ego: Veh, base: u32, n: u32, lengths_in_front: f32) {
    if ((lanes[ego.lane].flags & LANE_ROUNDABOUT) != 0u || n == 0u) { return; }
    let need = ty.length + ty.min_gap;
    var seen = -lengths_in_front;
    var found = false;
    var had = 0u;
    for (var j = 0u; j < n; j++) {
        let l = items[base + j].link;
        if (l == NONE || found) {
            av_set(j, seen);
            continue;
        }
        let k = links[l];
        if ((k.flags & L_HAS_VIA) != 0u) {
            let via = k.next_lane;
            let occupied = lane_occupied(via);
            if (keep_clear(k)) {
                if (occupied) { seen -= lane_free[via].brutto; }
                if (via == ego.lane) { seen += need; }
            } else if (occupied) {
                seen += lane_free[via].space;
                if ((lane_free[via].flags & FREE_STOPPED) != 0u) { found = true; }
            } else {
                seen += lanes[via].length;
            }
            av_set(j, seen);
            continue;
        }
        let to = k.to_lane;
        if (!lane_occupied(to) || to == ego.lane) {
            if (lanes[to].length > ty.length || keep_clear(k)) { seen += lanes[to].length; }
            av_set(j, seen);
        } else {
            let f = lane_free[to];
            seen += f.space;
            av_set(j, seen);
            if (f.flags != 0u) {
                found = true;
                had |= 1u << j;
            }
        }
    }
    for (var i = n - 1u; i > 0u; i--) {
        let l = items[base + i - 1u].link;
        if (l == NONE) { continue; }
        let k = links[l];
        let next = items[base + i];
        let can_leave = (k.flags & L_HAS_VIA) == 0u || next.link == NONE || next.request != 0u;
        let state = link_state(l);
        var opened = can_leave && (have_priority(state) || i == 1u);
        if (can_leave && !opened && !(have_red(state) || have_yellow(state) || state == CH_s || state == CH_w)) {
            let it = items[base + i - 1u];
            var leave = it.leave;
            if (leave < 0.0) { leave = it.v_pass; }
            opened = !foe_on_last_approach(l, it.arrival, it.arr_speed, leave, ego);
        }
        var allows = ((k.flags & L_CONT) != 0u || opened) && ((had >> (i - 1u)) & 1u) == 0u;
        if (!opened) {
            found = true;
            if (i > 1u) {
                let l2 = items[base + i - 2u].link;
                if (l2 != NONE && (links[l2].flags & L_CONT) != 0u) { allows = true; }
            }
        }
        if (allows) { av_set(i - 1u, av_get(i)); }
    }
    if (!found) { return; }
    var removal = NONE;
    for (var j = 0u; j < n; j++) {
        let l = items[base + j].link;
        if (l == NONE) { continue; }
        if (av_get(j) - need < 0.0 && keep_clear(links[l])) {
            removal = j;
            break;
        }
    }
    if (removal == NONE || (removal == 0u && (lanes[ego.lane].flags & LANE_INTERNAL) != 0u)) { return; }
    let gap = brake_gap(ego.speed, ty.decel, 0.0);
    for (var j = removal; j < n; j++) {
        let it = items[base + j];
        if (it.link == NONE) { break; }
        items[base + j].v_pass = it.v_wait;
        if (it.dist >= gap + POS_EPS) {
            let f = links[it.link].flags;
            let exit_link = (f & L_FROM_INTERNAL) != 0u && (f & L_HAS_VIA) == 0u;
            if (!exit_link || j == 0u || items[base + j - 1u].request == 0u) {
                items[base + j].request = 0u;
            }
        }
    }
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
    let s = seg[ego.lane];
    check_rewind(ego, base, n, f32(s.end - i - 1u) * (ty.length + ty.min_gap));
    var wants = false;
    for (var j = 0u; j < n; j++) {
        let it = items[base + j];
        if (it.link == NONE) { continue; }
        let k = links[it.link];
        let request = it.request != 0u;
        if (j == 0u && request) { wants = true; }
        if (it.arrival > CUTOFF) { continue; }
        if ((k.flags & L_WATCHED) == 0u) { continue; }
        // The vehicles nearest the stop line get fixed slots by their place in the lane, so the
        // ones that matter most are never crowded out. Upstream ones share what is left.
        var slot: u32;
        let rank = s.end - 1u - i;
        if (k.from_lane == ego.lane && rank < SLOTS_NEAR) {
            slot = rank;
        } else {
            let far = atomicAdd(&link_count[it.link], 1u);
            if (far >= SLOTS - SLOTS_NEAR) {
                atomicAdd(&C[C_OVERFLOW], 1u);
                continue;
            }
            slot = SLOTS_NEAR + far;
        }
        var a: Approach;
        a.arrival = it.arrival;
        if (link_state(it.link) == CH_w) {
            // A random tie break at all-way stops, as SUMO's one millisecond.
            a.arrival += f32(pcg(G.step ^ (ego.trip * 2654435761u)) & 1u) * 0.001;
            items[base + j].arrival = a.arrival;
        }
        var leave = it.leave;
        if (leave < 0.0) { leave = it.v_pass; }
        a.leave = it.arrival + (k.length + ty.length) / max((it.arr_speed + leave) * 0.5, EPS);
        a.arr_speed = it.arr_speed;
        a.leave_speed = leave;
        a.braking = it.braking;
        a.wait = ego.wait;
        if ((ego.flags & F_HAVE_STOPPED) != 0u) { a.wait = 1e9; }
        a.dist = it.dist;
        a.speed = ego.speed;
        a.decel = ty.decel;
        a.will_pass = u32(request);
        a.trip = ego.trip;
        a.stamp = G.step;
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
        if (wait > r.wait) { return false; }
        if (wait == r.wait && a < r.arrival) { return false; }
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
        for (var s = 0u; s < SLOTS; s++) {
            let r = slots[foe * SLOTS + s];
            if (r.stamp != G.step || r.trip == trip) { continue; }
            if (blocked_by_foe(r, a, l, va, vl, same_target, impatience, decel, wait, foe_state)) { return false; }
        }
    }
    return true;
}

var<private> fin_min: f32;
var<private> fin_max: f32;

// MSLCM_LC2013::_patchSpeed: what lane changing wants from the speed this step.
fn lc_patch_speed(wanted: f32, e: Veh, vmax: f32) -> f32 {
    var mn = fin_min;
    var mx = fin_max;
    var nv = wanted;
    var got = false;
    if (e.blocker != 0.0 && !is_internal(e.lane)) {
        let space = e.left_space - e.blocker - POS_EPS;
        if (space > 0.0) {
            let vme = min_next_speed_emergency(e.speed);
            let safe = stop_speed(e.speed, space, ty.decel, true, vmax);
            mx = min(mx, max(safe, vme));
            if (safe < wanted) {
                if (safe < mn && safe >= vme) { mn = max(vme, safe); }
                nv = max(mn, safe);
                got = true;
            }
        }
    }
    let adv = atomicExchange(&advice[e.trip], NONE);
    if (adv != NONE) {
        // Stored rounded down, so compare with the rounding in mind.
        let v = f32(adv) / 1024.0;
        if (v >= mn - 0.002 && v <= mx) {
            nv = min(max(v, mn), nv);
            got = true;
        }
    }
    if (got) { return nv; }
    let state = e.lc_own | atomicLoad(&adv_flags[e.trip]);
    if ((state & LCA_WANTS) != 0u && (state & (LCA_BLOCK_LEADER | LCA_BLOCK_FOLLOWER)) != 0u) {
        if ((state & LCA_STRATEGIC) != 0u) { return (mx + wanted) / 2.0; }
        if ((state & LCA_COOPERATIVE) != 0u) {
            if ((state & LCA_BLOCK_LEADER) != 0u) { return (max(0.0, mn) + wanted) / 2.0; }
            return (mx + wanted) / 2.0;
        }
    }
    if ((state & LCA_AM_LEADER) != 0u && ty.lc_cooperative >= 0.0) { return (mx + wanted) / 2.0; }
    return wanted;
}

fn could_brake_for_leader(f_dist: f32, l_dist: f32, f_speed: f32, f_decel: f32, l_speed: f32) -> bool {
    return f_dist > l_dist && f_dist - l_dist > f_speed - f_decel - l_speed;
}

// MSLink::getZipperSpeed: fall in behind the vehicle arriving first on the other branch.
fn zipper_speed(link: u32, dist: f32, v_in: f32, a: f32, speed: f32, vl: f32, va: f32, trip: u32, lane: u32, imp: f32, wait: f32, vmax: f32) -> f32 {
    let bg = brake_gap(v_in, ty.decel, dt);
    let k = links[link];
    if (dist > max(k.visibility, bg)) { return v_in; }
    let l = a + (k.length + ty.length) / max((va + vl) * 0.5, EPS);
    var v_safe = v_in;
    for (var f = 0u; f < k.foe_count; f++) {
        let foe = foes[k.foe_start + f];
        let same_target = links[foe].to_lane == k.to_lane;
        let foe_state = link_state(foe);
        for (var s = 0u; s < SLOTS; s++) {
            let r = slots[foe * SLOTS + s];
            if (r.stamp != G.step || r.trip == trip) { continue; }
            if (!blocked_by_foe(r, a, l, va, vl, same_target, imp, ty.decel, wait, foe_state)) { continue; }
            if ((r.arrival > a && !could_brake_for_leader(dist, r.dist, speed, ty.decel, r.speed))
                || could_brake_for_leader(r.dist, dist, r.speed, r.decel, speed)
                || (r.arrival == a && r.dist == dist && trip < r.trip)) { continue; }
            let u_end = min(vmax, sqrt(max(0.0, 2.0 * r.dist * ty.accel + r.speed * r.speed)));
            let u_avg = (r.speed + u_end) / 2.0;
            let tf = max(1.0, ceil(r.dist / max(EPS, u_avg) / dt) * dt);
            let v_acc = estimate_speed(dist, speed, ty.accel);
            let v_dec = estimate_speed(dist, speed, -ty.decel);
            let v_end = min(min(vmax, v_acc), max(u_end, v_dec));
            let v_avg = (speed + v_end) / 2.0;
            let te = max(1.0, ceil(dist / max(EPS, v_avg) / dt) * dt);
            let t_target = tf + ty.tau;
            var acc: f32;
            if (dist <= 0.0) {
                acc = -ty.decel;
            } else if (t_target * v_safe > 2.0 * dist) {
                acc = -0.5 * v_safe * v_safe / dist;
            } else {
                acc = 2.0 * (dist / t_target - v_safe) / t_target;
            }
            let gap = dist - ty.length - ty.min_gap - r.dist;
            let v_follow = follow_speed(speed, gap, r.speed, r.decel, false, vmax, lanes[lane].speed);
            let v_gap = max(v_follow, speed + acc * dt);
            let w = min(1.0, te / 10.0);
            let md = w * ty.decel + (1.0 - w) * ty.emergency;
            v_safe = min(v_safe, max(max(v_follow, speed - md * dt), v_gap));
        }
    }
    return v_safe;
}

fn finalize_speed(v_pos: f32, old_v: f32, lane_vmax_: f32, rng: ptr<private, u32>) -> f32 {
    let v_e = min_next_speed_emergency(old_v);
    let v_min = min(min_next_speed(old_v), max(v_pos, v_e));
    let a_max = (max(lane_vmax_, v_pos) - old_v) / dt;
    let v_max = max(v_min, min(min(old_v + a_max * dt, max_next_speed(old_v)), v_pos));
    fin_min = v_min;
    fin_max = v_max;
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
    e.flags &= ~(4096u | F_HAVE_TO_WAIT);
    if ((e.flags & F_LANE_CHANGED) != 0u) { e.flags |= 4096u; }
    e.flags &= ~F_LANE_CHANGED;
    ty = types[e.vtype];
    dt = P.dt;
    if (e.lane == P.dummy_lane) {
        teleporting_step(&e, i);
        cur[i] = e;
        return;
    }
    apply_script(e.flags, e.v_next);
    let base = i * MAX_ITEMS;
    let n = e.n_items;
    let speed = e.speed;
    var v_safe = speed;
    var v_safe_min = 0.0;
    var v_safe_min_dist = 0.0;
    var can_brake_min = false;

    let impat = clamp(ty.impatience + e.wait / P.time_to_impatience, 0.0, 1.0);
    var v_zipper = 1e9;
    let vmax_lane = lane_vmax(e.lane, e.sf);
    var have_to_wait = false;
    for (var j = 0u; j < n; j++) {
        let it = items[base + j];
        if (it.link != NONE && it.request != 0u) {
            let state = link_state(it.link);
            let yellow = have_yellow(state);
            let can_brake = it.dist > brake_gap(speed, ty.decel, 0.0) || speed < ty.decel * dt;
            if (yellow && can_brake) {
                v_safe = it.v_wait;
                have_to_wait = true;
                break;
            }
            var leave = it.leave;
            if (leave < 0.0) { leave = it.v_pass; }
            var imp = 1.0;
            if (can_brake) { imp = impat; }
            var my_wait = e.wait;
            if ((e.flags & F_HAVE_STOPPED) != 0u) { my_wait = 1e9; }
            let opened = yellow || link_opened(it.link, it.arrival, it.arr_speed, leave, ty.length, imp, ty.decel, my_wait, e.trip);
            let k = links[it.link];
            let determined = it.dist <= k.visibility;
            if (opened && (state == CH_s || state == CH_w) && determined) { e.flags |= F_HAVE_STOPPED; }
            if (opened && !have_priority(state) && !last_was_cont_major(it.link) && (k.flags & L_CONT) == 0u) {
                if (!determined && (can_brake || !yellow)) {
                    v_safe = it.v_wait;
                    have_to_wait = true;
                    break;
                } else {
                    v_safe_min_dist = it.dist;
                    v_safe_min = min(min((it.dist + POS_EPS) / dt, it.v_pass), max_next_speed(speed));
                    can_brake_min = can_brake;
                }
            }
            if (opened) {
                v_safe = it.v_pass;
                if (v_safe < ty.decel && v_safe <= it.v_wait && v_safe < max_next_speed(speed)) { have_to_wait = true; }
            } else if (state == CH_Z) {
                v_safe = it.v_pass;
                v_zipper = min(v_zipper, zipper_speed(it.link, it.dist, it.v_pass, it.arrival, speed, leave, it.arr_speed, e.trip, e.lane, imp, my_wait, vmax_lane));
            } else if (!can_brake && k.tl == NONE && it.dist < brake_gap(speed, ty.emergency, 0.0)) {
                v_safe = it.v_pass;
            } else {
                v_safe = it.v_wait;
                have_to_wait = true;
                break;
            }
        } else {
            v_safe = it.v_wait;
            if (it.link != NONE && (v_safe < speed || v_safe < HALT_SPEED)) { have_to_wait = true; }
            break;
        }
    }
    if (v_safe + EPS < v_safe_min) {
        if (can_brake_min && v_safe < speed) {
            v_safe = min(v_safe, max(min_next_speed(speed), stop_speed(speed, v_safe_min_dist, ty.decel, true, lane_vmax(e.lane, e.sf))));
            v_safe_min = 0.0;
            have_to_wait = true;
        } else {
            v_safe_min = v_safe;
        }
    }

    if (have_to_wait && (lanes[e.lane].flags & LANE_ROUNDABOUT) == 0u) { e.flags |= F_HAVE_TO_WAIT; }
    v_safe = min(v_safe, v_zipper);
    ex_rng = e.rng;
    let vmax_here = lane_vmax(e.lane, e.sf);
    var v_next = finalize_speed(v_safe, speed, vmax_here, &ex_rng);
    e.rng = ex_rng;
    v_next = lc_patch_speed(v_next, e, vmax_here);
    v_next = max(v_next, v_safe_min);
    if (v_next < 0.1 * EPS * dt) { v_next = 0.0; }
    let cj = cj_controlled(e);
    if (cj) {
        // A car with no grant yet can still slow for a lane change next to it. A firm one flies its slot.
        let st = e.cj_state & CJ_STATE_MASK;
        if (st == CJ_FIRM || st == CJ_BOX || (e.cj_state & CJ_STALLED) != 0u) { v_next = e.cj_v_cmd; } else { v_next = min(v_next, e.cj_v_cmd); }
    }

    let acc = (v_next - speed) / dt;
    let old_pos = e.pos;
    e.pos += v_next * dt;
    if (cj) { e.pos -= 0.5 * (v_next - speed) * dt; }
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
        // A loop on a lane left in this step was crossed, however short the lane.
        let crossed = lanes[e.lane].det_pos;
        if (crossed >= 0.0 && (j > 0u || old_pos < crossed)) { last_detect[e.lane] = G.step; }
        e.pos -= len;
        e.route_len += len;
        e.prev2_lane = e.prev_lane;
        e.prev_lane = e.lane;
        e.lane = k.next_lane;
        e.flags &= ~F_HAVE_STOPPED;
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

    // A loop stays occupied until the back of the vehicle has passed it.
    var loop_back = e.pos - ty.length;
    let det = lanes[e.lane].det_pos;
    if (det >= 0.0 && e.pos >= det && (loop_back < det || j > 0u || old_pos < det)) { last_detect[e.lane] = G.step; }
    if (loop_back < 0.0 && e.prev_lane != NONE) {
        loop_back += lanes[e.prev_lane].length;
        let d1 = lanes[e.prev_lane].det_pos;
        if (d1 >= 0.0 && loop_back < d1) { last_detect[e.prev_lane] = G.step; }
        if (loop_back < 0.0 && e.prev2_lane != NONE) {
            loop_back += lanes[e.prev2_lane].length;
            let d2 = lanes[e.prev2_lane].det_pos;
            if (d2 >= 0.0 && loop_back < d2) { last_detect[e.prev2_lane] = G.step; }
        }
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
            finish_trip(&e, ap);
            cur[i] = e;
            return;
        }
    }

    // Teleport the head of a lane that has been stuck for too long.
    if (P.teleport_steps != 0u && e.wait > f32(P.teleport_steps) * dt) {
        let s0 = seg[first_lane];
        if (first_lane == e.lane && i + 1u == s0.end) {
            atomicAdd(&edge_acc[lanes[e.lane].edge * 4u + 3u], 1u);
            teleport(&e);
            atomicAdd(&C[C_TELEPORTS], 1u);
            var tele_kind = 13u;
            if (n == 0u || items[base].link == NONE) {
                tele_kind = 15u;
            } else if (!have_priority(link_state(items[base].link))) {
                tele_kind = 14u;
            }
            atomicAdd(&C[tele_kind], 1u);
            cur[i] = e;
            return;
        }
    }

    // Publish where the vehicle is for lane changing, insertion and next step's planning.
    let back = e.pos - ty.length;
    if (back < 0.0 && e.prev_lane != NONE) {
        let plen = lanes[e.prev_lane].length;
        let b2 = plen + back;
        let cb = is_cacc(ty);
        atomicMin(&partial_occ[e.prev_lane], pack_back(b2, e.speed, cb));
        atomicMin(&tail[e.prev_lane], pack_back(b2, e.speed, cb));
        if (b2 < 0.0 && e.prev2_lane != NONE) {
            let b3 = lanes[e.prev2_lane].length + b2;
            atomicMin(&partial_occ[e.prev2_lane], pack_back(b3, e.speed, cb));
            atomicMin(&tail[e.prev2_lane], pack_back(b3, e.speed, cb));
        }
    }
    let s = seg[first_lane];
    if (e.lane != first_lane || i == s.first) {
        atomicMin(&tail[e.lane], pack_back(back, e.speed, is_cacc(ty)));
    }
    if (e.lane != first_lane) {
        atomicMin(&entrant[e.lane], (u32(clamp(e.pos, 0.0, 127.0) * 8.0) << 22u) | i);
    }
    cur[i] = e;
}

// MSVehicleTransfer: lift the vehicle off the road. It waits on the dummy lane, and moves along
// its route virtually until there is room to put it back.
fn teleport(e: ptr<function, Veh>) {
    if ((*e).route_i + 1u >= (*e).route_end) {
        finish_trip(e, lanes[(*e).lane].length);
        return;
    }
    (*e).route_i += 1u;
    (*e).lane = P.dummy_lane;
    (*e).pos = 0.0;
    (*e).speed = 0.0;
    (*e).acc = 0.0;
    (*e).wait = 0.0;
    (*e).prev_lane = NONE;
    (*e).prev2_lane = NONE;
    (*e).entry_step = NONE;
}

fn finish_trip(e: ptr<function, Veh>, ap: f32) {
    var out: TripOut;
    out.depart_step = (*e).depart_step;
    out.arrive_step = G.step + 1u;
    out.wait = (*e).tot_wait;
    out.time_loss = (*e).time_loss;
    out.route_len = (*e).route_len + ap;
    out.wait_count = (*e).wait_count;
    out.flags = 1u;
    trip_out[(*e).trip] = out;
    (*e).flags |= F_REMOVED;
    atomicAdd(&C[C_ARRIVED], 1u);
}

// Would whatever comes up behind `pos` on this lane cope with a vehicle appearing there at speed v?
fn follower_allows(lane: u32, pos: f32, ego: u32, v: f32) -> bool {
    let n = lc_neighbors(lane, pos, ego, pos - ty.length);
    if (n.follower == NONE) { return true; }
    if (n.f_gap < 0.0) { return false; }
    let save = ty;
    ty = types[n.f_vtype];
    let need = secure_gap(n.f_speed, v, save.apparent);
    ty = save;
    return n.f_gap >= need;
}

fn teleporting_step(e: ptr<function, Veh>, index: u32) {
    let ed = edges[routes[(*e).route_i]];
    var best = NONE;
    var best_load = 0xffffffffu;
    for (var l = 0u; l < ed.lane_count; l++) {
        let c = ed.first_lane + l;
        if (!lane_is_good(c, (*e).route_i, (*e).route_end)) { continue; }
        let load = lane_load(c);
        if (load < best_load) {
            best_load = load;
            best = c;
        }
    }
    if (best != NONE) {
        let la = lanes[best];
        var back = 1e9;
        var lv = 0.0;
        var lb = ty.apparent;
        if (lane_occupied(best)) {
            let t = cur[seg[best].first];
            if (t.lane == best) {
                back = t.pos - types[t.vtype].length;
                lv = t.speed;
                lb = types[t.vtype].apparent;
            }
        }
        let p = atomicLoad(&tail[best]);
        if (p != NONE && unpack_back(p) < back) {
            back = unpack_back(p);
            lv = unpack_speed(p);
        }
        let pos = min(ty.length + POS_EPS, la.length);
        let gap = back - pos - ty.min_gap;
        let vmax = min(la.speed * (*e).sf, ty.max_speed);
        var v = vmax;
        if (back < 1e8) { v = min(vmax, insertion_follow(vmax, gap, lv, lb, vmax, ty.model == MODEL_CACC)); }
        if (gap > 0.0 && follower_allows(best, pos, index, v)) {
            (*e).lane = best;
            (*e).pos = pos;
            (*e).speed = max(v, 0.0);
            (*e).wait = 0.0;
            (*e).flags |= F_BEST_DIRTY;
            atomicMin(&tail[best], pack_back(pos - ty.length, (*e).speed, is_cacc(ty)));
            return;
        }
    }
    (*e).wait += dt;
    (*e).tot_wait += 0.0;
    if ((*e).wait * max(1.0, lanes[ed.first_lane].speed) >= ed.length) {
        (*e).wait = 0.0;
        (*e).route_len += ed.length;
        if ((*e).route_i + 1u >= (*e).route_end) {
            finish_trip(e, 0.0);
        } else {
            (*e).route_i += 1u;
        }
    }
}

// MSLane::detectCollisions with the default action, teleport: the follower that got too close goes.
@compute @workgroup_size(64)
fn collide(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i + 1u >= G.n_active) { return; }
    let a = cur[i];
    let b = cur[i + 1u];
    if (a.lane != b.lane || a.lane == P.dummy_lane || ((a.flags | b.flags) & F_REMOVED) != 0u) { return; }
    // Neighbours in the array are only neighbours on the road if neither has moved to this lane
    // since the sort. Those get checked after the next one.
    let sg = seg[a.lane];
    if (sg.stamp != G.step || i < sg.first || i + 1u >= sg.end) { return; }
    ty = types[a.vtype];
    dt = P.dt;
    let gap = b.pos - types[b.vtype].length - a.pos - ty.collision_factor * ty.min_gap;
    if (gap < -EPS) {
        if (ty.model == MODEL_AV) {
            // The auditor counts it. Never repaired.
            atomicAdd(&C[C_COLLISIONS], 1u);
            return;
        }
        var e = a;
        teleport(&e);
        cur[i] = e;
        atomicAdd(&C[C_COLLISIONS], 1u);
        if (((a.flags | b.flags) & (F_LANE_CHANGED | 4096u)) != 0u) {
            atomicAdd(&C[9], 1u);
        } else if (is_internal(a.lane)) {
            atomicAdd(&C[10], 1u);
        } else if (a.pos < ty.length + ty.min_gap + 1.0) {
            atomicAdd(&C[11], 1u);
        } else {
            atomicAdd(&C[12], 1u);
        }
    }
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
    if (mode <= -5) {
        // MSEdge::getFreeLane and getProbableLane over the best lanes: the largest gap to the last vehicle.
        let depart = min(ty.length + POS_EPS, ed.length);
        var largest = 0.0;
        var by_gap = NONE;
        var emptiest = NONE;
        var least = 1e30;
        for (var l = 0u; l < ed.lane_count; l++) {
            if (((t.best_mask >> l) & 1u) == 0u) { continue; }
            let c = ed.first_lane + l;
            let occupancy = brutto_on(c);
            if (occupancy < least) {
                least = occupancy;
                emptiest = c;
            }
            var last = ed.length;
            let packed = atomicLoad(&tail[c]);
            if (packed != NONE) { last = unpack_back(packed) + ty.length; }
            if (last - depart > largest) {
                largest = last - depart;
                by_gap = c;
            }
        }
        if (by_gap != NONE) { return by_gap; }
        return emptiest;
    }
    // free, allowed: the emptiest lane, limited to lanes reaching the next edge unless free.
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
                let safe = min(vmax, insertion_follow(vmax, gap, unpack_speed(packed), ty.apparent, vmax, ty.model == MODEL_CACC));
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
    mode_done = true;
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
        case 6u: {
            // MSLane::getDepartSpeed with DepartSpeedDefinition::AVG.
            speed = vmax;
            if (lane_occupied(lane)) { speed = min(vmax, lane_free[lane].mean_speed); }
            patch_speed = !lane_occupied(lane) && atomicLoad(&tail[lane]) == NONE;
        }
        default: {}
    }

    // Leader and follower on the lane, from this step's positions.
    var lead_back = 1e9;
    var lead_v = 0.0;
    var lead_b = ty.apparent;
    var lead_cacc = ty.model == MODEL_CACC;
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
                    lead_cacc = ot.model == MODEL_CACC;
                }
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
        if (ty.model == MODEL_AV) {
            // The upstream queue discharges at the equilibrium headway of the tail's speed.
            speed = min(speed, lead_v + 1.0);
            if (gap < 0.5 + speed * ty.tau) { return false; }
        }
        // The speed we may start with behind the leader, as SUMO's insertionFollowSpeed.
        let vsafe = insertion_follow(speed, gap, lead_v, lead_b, vmax, lead_cacc);
        if (vsafe < speed) {
            if (patch_speed) { speed = vsafe; } else { return false; }
        }
    }
    // Whoever comes up behind must be able to keep following us, even from the lane before.
    if (!follower_allows(lane, pos, 0xfffffffeu, speed)) { return false; }
    // What lies within braking distance along the route, as in MSLane::isInsertionSuccess.
    var seen = la.length - pos;
    var at = lane;
    var route_at = t.route_start;
    for (var hop = 0u; hop < 8u; hop++) {
        let dist = brake_gap(speed, ty.decel, ty.tau) + ty.min_gap;
        if (seen >= dist) { break; }
        let k = pick_link(at, route_at, t.route_end);
        if (k == NONE) {
            if (is_internal(at) || route_at + 1u < t.route_end) {
                let vs = insertion_stop(speed, seen, vmax);
                if (vs < speed) {
                    if (patch_speed) { speed = vs; } else { return false; }
                }
            }
            break;
        }
        let st = link_state(k);
        if (have_red(st) || have_yellow(st) || !have_priority(st) || st == CH_Z) {
            let vs = insertion_stop(speed, seen, vmax);
            if (vs < speed) {
                if (patch_speed) { speed = vs; } else { return false; }
            }
            if (seen >= ty.min_gap) { break; }
        }
        let next = links[k].next_lane;
        let packed = atomicLoad(&tail[next]);
        if (packed != NONE) {
            let g = seen + unpack_back(packed) - ty.min_gap;
            if (g < 0.0) { return false; }
            let vs = insertion_follow(speed, g, unpack_speed(packed), ty.apparent, vmax, ty.model == MODEL_CACC);
            if (vs < speed) {
                if (patch_speed) { speed = vs; } else { return false; }
            }
        }
        let next_vmax = min(lanes[next].speed * t.sf, ty.max_speed);
        let vf = free_speed(speed, seen, next_vmax, vmax);
        if (vf < speed) {
            if (patch_speed) { speed = vf; } else { return false; }
        }
        if ((links[k].flags & L_HAS_VIA) == 0u) { route_at += 1u; }
        seen += lanes[next].length;
        at = next;
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
    e.look_v = 0.0;
    e.best_cur = 1e9;
    e.best_left = 0.0;
    e.best_right = 0.0;
    e.cj_link = NONE;
    e.cj_zone_t = f32(G.step) * dt;
    e.cj_hold = 1e30;
    e.cj_yield = 1e30;
    cur[idx] = e;
    atomicAdd(&C[C_INSERTED], 1u);
    let lb = pack_back(pos - ty.length, speed, is_cacc(ty));
    atomicMin(&tail[lane], lb);
    return true;
}

// Perimeter metering: while the network holds its critical number of cars, new ones wait outside.
// Queues near the limit take turns by hash, so no entrance is starved by its place in the dispatch.
fn metered_in(q: u32) -> bool {
    let on = G.n_active + atomicLoad(&C[C_NEW]);
    if (on >= P.meter_n) { return false; }
    let free = f32(P.meter_n - on);
    return f32(pcg(q * 2654435761u ^ G.step) >> 8u) / 16777216.0 < free / f32(P.n_queues);
}

@compute @workgroup_size(16)
fn insert(@builtin(global_invocation_id) id: vec3u) {
    let q = id.x;
    if (q >= P.n_queues) { return; }
    let qq = queues[q];
    if (qq.next >= qq.end) { return; }
    if (P.meter_n != 0u && !metered_in(q)) { return; }
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
