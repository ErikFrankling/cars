// Which way a vehicle goes, shared by the step kernels and the coordinator.

// How far a vehicle can stay on from `lane` along its route without changing lanes.
fn continuation_length(start: u32, route_i: u32, route_end: u32) -> f32 {
    var l = start;
    var r = route_i;
    var total = 0.0;
    for (var d = 0u; d < 8u; d++) {
        total += lanes[l].length;
        if (total > 3000.0 || r + 1u >= route_end) { return 1e9; }
        let la = lanes[l];
        let want = routes[r + 1u];
        var next = NONE;
        for (var k = 0u; k < la.links_count; k++) {
            let t = links[la.links_start + k].to_lane;
            if (links[la.links_start + k].to_edge == want && (next == NONE || t > next)) { next = t; }
        }
        if (next == NONE) { return total; }
        l = next;
        r += 1u;
    }
    return total;
}

// The link out of `lane` that continues the route. With several, as SUMO's best lanes: the target
// lane with the longest continuation, and the first of equals.
fn pick_link(lane: u32, route_i: u32, route_end: u32) -> u32 {
    let l = lanes[lane];
    if (l.links_count == 0u) { return NONE; }
    if ((l.flags & LANE_INTERNAL) != 0u) { return l.links_start; }
    if (route_i + 1u >= route_end) { return NONE; }
    let want = routes[route_i + 1u];
    var first = NONE;
    var best_len = -1.0;
    var count = 0u;
    for (var k = 0u; k < l.links_count; k++) {
        let c = l.links_start + k;
        if (links[c].to_edge != want || (lanes[links[c].to_lane].allow & ty.vclass) != ty.vclass) { continue; }
        count += 1u;
        if (count == 1u) { first = c; continue; }
        if (count == 2u) { best_len = continuation_length(links[first].to_lane, route_i + 1u, route_end); }
        let len = continuation_length(links[c].to_lane, route_i + 1u, route_end);
        if (len > best_len) {
            best_len = len;
            first = c;
        }
    }
    return first;
}

// Coordinated cars take their speed from cj_apply, not from the plan.
fn cj_controlled(e: Veh) -> bool {
    if (types[e.vtype].model != MODEL_AV) { return false; }
    let f = lanes[e.lane].flags;
    return (f & LANE_CJ) != 0u || ((f & LANE_CJ_EXIT) != 0u && e.route_i + 1u >= e.route_end);
}
