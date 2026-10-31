// LC2013 discrete motivations. Omitted: sublane/continuous maneuvers, opposite driving,
// pedestrians, stops/arrival-lane constraints, roundabout bonus and TraCI. Negotiation
// uses bounded next-step speed advice rather than SUMO's sequential message exchange.
// Reservations conservatively retain departures and may reject distant hash collisions.

@compute @workgroup_size(64)
fn lc_best(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let e = cur[i];
    if ((e.flags & (F_BEST_DIRTY | F_REMOVED)) != F_BEST_DIRTY || is_internal(e.lane)) { return; }
    ty = types[e.vtype];
    dt = P.dt;
    let ed = edges[lanes[e.lane].edge];
    // Separate scratch upstream the decision kernel. Wide edges keep their dirty bit.
    if (ed.lane_count > 64u) { return; }
    var a: array<f32, 64>;
    var b: array<f32, 64>;
    var off: array<i32, 64>;
    var next_off: array<i32, 64>;
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
        if (edge.lane_count > 64u) { return; }
        var best = 0.0;
        var best_offset = 1000;
        var next_best = 0.0;
        if (ri + 1u < stop) {
            let ne = edges[routes[ri + 1u]];
            for (var k = 0u; k < ne.lane_count; k++) { next_best = max(next_best, b[k]); }
        }
        for (var k = 0u; k < edge.lane_count; k++) {
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
                    let nk = lanes[lk.to_lane].index;
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
        for (var k = 0u; k < edge.lane_count; k++) {
            var nearest = 1000;
            for (var j = 0u; j < edge.lane_count; j++) {
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
    if (k + 1u < ed.lane_count) { cur[i].best_left = b[k + 1u]; }
    if (k > 0u) { cur[i].best_right = b[k - 1u]; }
    cur[i].best_off = next_off[k];
    cur[i].flags &= ~F_BEST_DIRTY;
}

struct LcNeighbors {
    leader: u32,
    follower: u32,
    follower_pos: f32,
    back: f32,
    speed: f32,
    decel: f32,
}

fn lc_neighbors(l: u32, pos: f32, ego: u32) -> LcNeighbors {
    var r = LcNeighbors(NONE, NONE, -1e9, 1e9, 0.0, ty.apparent);
    if (lane_occupied(l)) {
        let s = seg[l];
        var lo = s.first;
        var hi = s.end;
        // Entries that crossed an edge have wrapped positions. Search only live keys.
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
                r.leader = k; r.back = o.pos - types[o.vtype].length;
                r.speed = o.speed; r.decel = types[o.vtype].apparent; break;
            }
        }
        var k = lo;
        loop {
            if (k == s.first) { break; }
            k--;
            let o = cur[k];
            if (k != ego && o.lane == l && (o.flags & F_REMOVED) == 0u && o.pos < pos) { r.follower = k; break; }
        }
    }
    let ent = atomicLoad(&entrant[l]);
    if (ent != NONE) {
        let k = ent & 0x3fffffu;
        let o = cur[k];
        if (k != ego && o.lane == l && (o.flags & F_REMOVED) == 0u) {
            if (o.pos >= pos && o.pos - types[o.vtype].length < r.back) {
                r.leader = k; r.back = o.pos - types[o.vtype].length;
                r.speed = o.speed; r.decel = types[o.vtype].apparent;
            } else if (o.pos < pos) {
                if (r.follower == NONE) { r.follower = k; }
                else if (o.pos > cur[r.follower].pos) { r.follower = k; }
            }
        }
    }
    if (r.follower != NONE) { r.follower_pos = cur[r.follower].pos; }
    // A changer near the upstream boundary must also leave room for approaching
    // vehicles on the target lane's incoming connection (including short internals).
    if (pos < 200.0) {
        for (var j = 0u; j < P.n_links; j++) {
            if (links[j].next_lane != l) { continue; }
            let src = links[j].from_lane;
            for (var level = 0u; level < 2u; level++) {
                var upstream = src;
                var distance = 0.0;
                if (level == 1u) {
                    if (!is_internal(src) || lanes[src].pred == NONE) { continue; }
                    upstream = lanes[src].pred; distance = lanes[src].length;
                }
                let en = atomicLoad(&entrant[upstream]);
                if (en != NONE) {
                    let k = en & 0x3fffffu;
                    let fp = cur[k].pos - lanes[upstream].length - distance;
                    if (k != ego && cur[k].lane == upstream && (cur[k].flags & F_REMOVED) == 0u && fp > r.follower_pos) {
                        r.follower = k; r.follower_pos = fp;
                    }
                }
                if (!lane_occupied(upstream)) { continue; }
                let sg = seg[upstream];
                var k = sg.end;
                loop {
                    if (k == sg.first) { break; }
                    k--;
                    if (k == ego || cur[k].lane != upstream || (cur[k].flags & F_REMOVED) != 0u) { continue; }
                    let fp = cur[k].pos - lanes[upstream].length - distance;
                    if (fp > r.follower_pos) { r.follower = k; r.follower_pos = fp; }
                    break;
                }
            }
        }
    }
    // Include continuation leaders beyond a short internal connection.
    var ahead = l;
    var seen = lanes[l].length;
    for (var hop = 0u; hop < 3u; hop++) {
        let e = cur[ego];
        let lk = pick_link(ahead, e.route_i, e.route_end);
        if (lk == NONE || seen - pos > 200.0) { break; }
        ahead = links[lk].next_lane;
        let packed = atomicLoad(&tail[ahead]);
        if (packed != NONE && seen + unpack_back(packed) < r.back) {
            r.back = seen + unpack_back(packed); r.speed = unpack_speed(packed); r.leader = NONE;
        }
        seen += lanes[ahead].length;
        if (!is_internal(ahead)) { break; }
    }
    let p = atomicLoad(&partial_occ[l]);
    if (p != NONE && unpack_back(p) < r.back) {
        r.back = unpack_back(p); r.speed = unpack_speed(p); r.leader = NONE;
    }
    return r;
}

fn lc_safe_speed(e: Veh, l: u32, n: LcNeighbors, accelerating: bool) -> f32 {
    let vmax = lane_vmax(l, e.sf);
    if (n.back > 1e8) { return vmax; }
    let gap = n.back - e.pos - ty.min_gap;
    if (accelerating) { return min(vmax, follow_speed(e.speed + ty.accel * (1.0 - dt), gap, n.speed, n.decel, false, vmax, lanes[l].speed)); }
    return min(vmax, safe_follow(gap, e.speed, n.speed, n.decel, true));
}

fn lc_advice(trip: u32, speed: f32) { atomicMin(&advice[trip], u32(max(0.0, speed) * 1024.0)); }

@compute @workgroup_size(64)
fn lc_decide(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    lc_plan[i].side = 0;
    let e = cur[i];
    if ((e.flags & F_REMOVED) != 0u || is_internal(e.lane)) { return; }
    let ed = edges[lanes[e.lane].edge];
    if (ed.lane_count <= 1u) { return; }
    ty = types[e.vtype]; dt = P.dt;
    ego_flags = e.flags; ego_acc = e.acc; mode_done = true;
    let own = lc_neighbors(e.lane, e.pos, i);

    let look = max(e.speed, max(0.0, (1.0 - 0.1 * dt) * e.look_v + 0.1 * dt * e.speed));
    cur[i].look_v = look;
    var chosen = 0;
    var chosen_urgent = false;
    var pr = e.lc_right;
    var pl = e.lc_left;
    var pk = e.lc_keep;
    for (var side = -1; side <= 1; side += 2) {
        let index = i32(lanes[e.lane].index) + side;
        if (index < 0 || index >= i32(ed.lane_count)) { continue; }
        let dest = ed.first_lane + u32(index);
        if ((lanes[dest].allow & ty.vclass) != ty.vclass) { continue; }
        let right = side < 0;
        let permission = select(lanes[e.lane].pad0, lanes[e.lane].pad1, right);
        if ((permission & ty.vclass) != ty.vclass) { continue; }
        let dist = select(e.best_left, e.best_right, right);
        let to_best = e.best_off * side > 0;
        let occupation = f32(lane_load(dest)) * (ty.length + ty.min_gap);
        let usable = max(0.0, e.best_cur - e.pos - occupation);
        let la = look * 10.0 * ty.lc_strategic * select(ty.lc_look_left, 1.0, right) + 2.0 * (ty.length + ty.min_gap);
        let urgent = to_best && ty.lc_strategic >= 0.0 && usable / f32(max(1, abs(e.best_off))) < la;
        if (right && e.best_off == 0 && dist < e.best_cur && lanes[e.lane].speed > 80.0 / 3.6 && look > HALT_SPEED) { continue; }
        let neigh = lc_neighbors(dest, e.pos, i);
        var accelerating = false;
        if (own.leader != NONE) { accelerating = cur[own.leader].acc > 0.0; }
        if (neigh.leader != NONE) { accelerating = accelerating || cur[neigh.leader].acc > 0.0; }
        let own_safe = lc_safe_speed(e, e.lane, own, accelerating);
        let vs = lc_safe_speed(e, dest, neigh, accelerating);
        let gain = (vs - own_safe) / max(vs, 10.0);
        let tl = 0.2 / max(EPS, ty.lc_speed_gain);
        let tr = tl / max(EPS, ty.lc_speed_gain_right);
        var want = urgent;
        // Avoid leaving a route-compatible lane for a short turn lane.
        let suitable = dist + EPS >= e.best_cur || dist - e.pos > max(200.0, look * 10.0);
        if (right) {
            if (own_safe - 5.0 / 3.6 > vs) { pr *= pow(0.5, dt); }
            else {
                pr += dt * gain;
                let vmax = max(EPS, lane_vmax(e.lane, e.sf));
                let acceptance = 7.0 * vmax / lanes[e.lane].speed * max(1.0, e.speed);
                var full = max(0.0, dist - brake_gap(vmax, ty.decel, 0.0));
                var seconds = min(acceptance, full / vmax);
                if (neigh.speed < vmax && neigh.back < 1e8) {
                    full = max(0.0, min(full, neigh.back - e.pos - ty.min_gap - secure_gap(vmax, neigh.speed, neigh.decel)));
                    seconds = min(seconds, full / max(EPS, vmax - neigh.speed));
                }
                if (ty.lc_speed_gain > 0.0) { pk -= dt * tr * seconds / max(EPS, acceptance) / 5.0; }
            }
            want = want || (suitable && ty.lc_speed_gain > 0.0 && ((pr > tr && dist / max(0.1, e.speed) > 20.0) || pk * ty.lc_keep_right < -tr));
        } else {
            if (own_safe > vs) { pl *= pow(0.5, dt); }
            else if (own_safe == vs) { pl *= pow(0.8, dt); }
            else { pl += dt * gain; }
            want = want || (suitable && ty.lc_speed_gain > 0.0 && pl > tl && gain > EPS && dist / max(0.1, e.speed) > 20.0);
        }
        want = want || (to_best && ty.lc_strategic >= 0.0 && gain >= 0.0);
        if (!want) { continue; }
        let factor = 1.0 / max(EPS, ty.lc_assertive);
        let front = neigh.back - e.pos - ty.min_gap;
        let front_need = max(0.0, secure_gap(e.speed, neigh.speed, neigh.decel)) * factor;
        var back_ok = true;
        if (neigh.follower != NONE) {
            let f = cur[neigh.follower]; let ft = types[f.vtype];
            let gap = e.pos - ty.length - neigh.follower_pos - ft.min_gap;
            let save = ty; ty = ft;
            let need = max(0.0, secure_gap(f.speed, e.speed, save.apparent)) * factor;
            ty = save;
            back_ok = gap >= need && gap >= 0.0;
            if (!back_ok && urgent && ft.lc_cooperative > 0.0) {
                ty = ft;
                let help = max(min_next_speed(f.speed), safe_follow(max(0.0, gap), f.speed, e.speed, save.apparent, false));
                ty = save;
                lc_advice(f.trip, help);
            }
        }
        let front_ok = front >= 0.0 && front >= front_need;
        if ((!front_ok || !back_ok) && urgent) {
            // Fall behind a blocking leader; otherwise maintain speed to pass the follower.
            if (!front_ok) { lc_advice(e.trip, max(min_next_speed(e.speed), vs)); }
        }
        if (front_ok && back_ok && (chosen == 0 || (urgent && !chosen_urgent))) { chosen = side; chosen_urgent = urgent; }
    }
    cur[i].lc_right = pr; cur[i].lc_left = pl; cur[i].lc_keep = pk;
    if (chosen == 0) { return; }
    let dest = u32(i32(e.lane) + chosen);
    // An upper bound on the follower's secure gap, against a stationary leader.
    let reach = ty.min_gap + max(0.0, secure_gap(e.speed, 0.0, ty.apparent)) / max(EPS, ty.lc_assertive);
    let first = u32(max(0.0, floor((e.pos - ty.length) / 8.0)));
    let count = min(64u, u32(ceil((e.pos + reach) / 8.0)) - first + 1u);
    let rank = (i + G.step) % max(1u, G.n_active);
    let priority = select(0x80000000u, 0u, chosen_urgent) | rank;
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
    for (var k = 0u; k < p.pad0; k++) {
        if (atomicLoad(&claims[dest * 64u + (p.flags + k) % 64u]) != p.pad1) { return; }
    }
    cur[i].lane = dest;
    cur[i].flags |= F_LANE_CHANGED | F_BEST_DIRTY;
    cur[i].lc_right = 0.0; cur[i].lc_left = 0.0; cur[i].lc_keep = 0.0;
    atomicMin(&tail[dest], pack_back(cur[i].pos - types[cur[i].vtype].length, cur[i].speed));
    atomicAdd(&C[C_LANE_CHANGES], 1u);
}
