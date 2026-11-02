// A collision detector that shares nothing with the planner: where the bodies are, in the plane,
// from lane geometry alone. Reports, never repairs. Runs on every vehicle at each step it is on.

const GRID_CELL: f32 = 20.0;

fn shape_at(lane: u32, s: f32) -> vec2f {
    let l = lanes[lane];
    let first = l.shape_start;
    let count = l.shape_count;
    if (count < 2u) { return shape_points[first].xy; }
    let d = clamp(s * l.geom_scale, 0.0, shape_points[first + count - 1u].z);
    var lo = 0u;
    var hi = count - 1u;
    loop {
        if (hi - lo <= 1u) { break; }
        let m = (lo + hi) / 2u;
        if (shape_points[first + m].z < d) { lo = m; } else { hi = m; }
    }
    let a = shape_points[first + lo];
    let b = shape_points[first + hi];
    return mix(a.xy, b.xy, clamp((d - a.z) / max(b.z - a.z, 0.001), 0.0, 1.0));
}

fn grid_hash(x: i32, y: i32) -> u32 {
    let h = (u32(x) * 73856093u) ^ (u32(y) * 19349663u);
    return (h ^ (h >> 15u)) & P.grid_mask;
}

fn cell_of(c: vec2f) -> vec2i { return vec2i(floor(c / GRID_CELL)); }

@compute @workgroup_size(64)
fn detect_clear(@builtin(global_invocation_id) id: vec3u) {
    if (id.x > P.grid_mask) { return; }
    atomicStore(&grid_head[id.x], NONE);
}

@compute @workgroup_size(64)
fn detect_pose(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let v = cur[i];
    poses[i].half_len = 0.0;
    grid_next[i] = NONE;
    if ((v.flags & (F_REMOVED | F_SHADOW)) != 0u || v.lane == P.dummy_lane || v.replica != 0u) { return; }
    let t = types[v.vtype];
    let front = shape_at(v.lane, v.pos);
    var rear = front;
    let back = v.pos - t.length;
    if (back >= 0.0) {
        rear = shape_at(v.lane, back);
    } else {
        let start = shape_at(v.lane, 0.0);
        rear = start;
        var through = false;
        if (v.prev_lane != NONE && lanes[v.prev_lane].shape_count >= 2u) {
            let pl = lanes[v.prev_lane].length;
            if (distance(shape_at(v.prev_lane, pl), start) < 4.0) {
                through = true;
                let b2 = pl + back;
                if (b2 >= 0.0 || v.prev2_lane == NONE) {
                    rear = shape_at(v.prev_lane, max(b2, 0.0));
                } else {
                    rear = shape_at(v.prev2_lane, lanes[v.prev2_lane].length + b2);
                }
            }
        }
        if (!through) {
            var dir0 = vec2f(1.0, 0.0);
            let ahead = shape_at(v.lane, min(v.pos + 1.0, lanes[v.lane].length));
            if (distance(ahead, front) > 0.01) { dir0 = normalize(ahead - front); }
            rear = front - dir0 * t.length;
        }
    }
    var dir = front - rear;
    let len = length(dir);
    if (len > 0.2) {
        dir /= len;
    } else {
        let ahead = shape_at(v.lane, min(v.pos + 1.0, lanes[v.lane].length));
        dir = normalize(ahead - front + vec2f(1e-4, 0.0));
    }
    var center = front - dir * t.length * 0.5;
    if ((v.phys >> 30u) != 0u) {
        var v_lat = t.v_lat;
        if ((v.flags & F_LAT_FAST) != 0u) { v_lat = 1.1; }
        let w = lanes[v.lane].width;
        let done = ph_lateral_done(f32((v.phys >> 16u) & 0x3fffu) / 16383.0 * (w / v_lat + 1.0), w, v_lat);
        let side = select(1.0, -1.0, (v.phys >> 30u) == 1u);
        center += vec2f(-dir.y, dir.x) * side * (w - done);
    }
    // On a lane narrower than the body the driver squeezes over: the fault is the lane width in the net.
    let c = cell_of(center);
    poses[i] = Pose(center, dir, t.length * 0.5, min(t.width, lanes[v.lane].width) * 0.5, (u32(c.x + 32768) << 16u) | u32(c.y + 32768), 0u);
    let h = grid_hash(c.x, c.y);
    grid_next[i] = atomicExchange(&grid_head[h], i);
}

// Separating axes for two rectangles. Positive is how deep they overlap.
fn overlap_depth(a: Pose, b: Pose) -> f32 {
    let d = b.center - a.center;
    let na = vec2f(-a.dir.y, a.dir.x);
    let nb = vec2f(-b.dir.y, b.dir.x);
    let cross = abs(dot(a.dir, b.dir));
    let side = abs(dot(a.dir, nb));
    let s1 = a.half_len + b.half_len * cross + b.half_width * side - abs(dot(d, a.dir));
    let s2 = a.half_width + b.half_len * side + b.half_width * cross - abs(dot(d, na));
    let s3 = b.half_len + a.half_len * cross + a.half_width * side - abs(dot(d, b.dir));
    let s4 = b.half_width + a.half_len * side + a.half_width * cross - abs(dot(d, nb));
    return min(min(s1, s2), min(s3, s4));
}

fn related(a: Lane, b: Lane) -> bool {
    if (a.edge == b.edge) { return true; }
    return a.from_node == b.from_node || a.from_node == b.to_node || a.to_node == b.from_node || a.to_node == b.to_node;
}

fn contact_kind(a: Veh, b: Veh) -> u32 {
    if (a.lane == b.lane) { return 0u; }
    let la = lanes[a.lane];
    let lb = lanes[b.lane];
    if (la.edge == lb.edge) { return 1u; }
    let ia = (la.flags & LANE_INTERNAL) != 0u;
    let ib = (lb.flags & LANE_INTERNAL) != 0u;
    if (ia && ib) {
        if (la.pred == lb.pred) { return 4u; }
        if (la.links_count != 0u && lb.links_count != 0u && links[la.links_start].to_lane == links[lb.links_start].to_lane) { return 3u; }
        return 2u;
    }
    if ((!ia && a.pos < types[a.vtype].length + 1.0) || (!ib && b.pos < types[b.vtype].length + 1.0)) { return 5u; }
    return 6u;
}

@compute @workgroup_size(64)
fn detect_pairs(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    let a = poses[i];
    if (a.half_len <= 0.0) { return; }
    let c = cell_of(a.center);
    let la = lanes[cur[i].lane];
    for (var dx = -1; dx <= 1; dx++) {
        for (var dy = -1; dy <= 1; dy++) {
            let cx = c.x + dx;
            let cy = c.y + dy;
            let key = (u32(cx + 32768) << 16u) | u32(cy + 32768);
            var j = atomicLoad(&grid_head[grid_hash(cx, cy)]);
            var guard = 0u;
            loop {
                if (j == NONE || guard >= 256u) { break; }
                guard += 1u;
                let b = poses[j];
                let next = grid_next[j];
                if (j > i && b.cell == key) {
                    let reach = a.half_len + b.half_len + a.half_width + b.half_width;
                    if (dot(a.center - b.center, a.center - b.center) < reach * reach) {
                        let depth = overlap_depth(a, b);
                        if (depth > 0.02) {
                            let va = cur[i];
                            let vb = cur[j];
                            if (related(la, lanes[vb.lane])) {
                                let kind = contact_kind(va, vb);
                                let at = atomicAdd(&C[C_CONTACT], 1u) % CONTACT_LOG;
                                atomicAdd(&C[C_CONTACT_KINDS + kind], 1u);
                                contacts[at] = Contact(G.step, va.trip, vb.trip, va.lane, vb.lane, kind, depth, va.pos, vb.pos, a.center.x, a.center.y, 0.0);
                            }
                        }
                    }
                }
                j = next;
            }
        }
    }
}
