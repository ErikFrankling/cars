// Replay with recorded boundaries, research/truth/replay/README.md. Compiled into the step module only
// with --replay. After lane changing, a replayed vehicle is put where its recording has it at the end of
// this step; from its release time on the driver has it. Twins: GpuReplay* in world.rs.

struct ReplayCfg {
    begin: f32,
    n_tracks: u32,
    n_trips: u32,
    pad: u32,
}

struct ReplayTrack {
    first: u32,
    n: u32,
    t0: f32,
    key_dt: f32,
    release: f32,
    pad0: u32,
    pad1: u32,
    pad2: u32,
}

struct ReplayKey {
    lane: u32,
    pos: f32,
    speed: f32,
    route_i: u32,
}

@group(1) @binding(10) var<uniform> rcfg: ReplayCfg;
@group(1) @binding(11) var<storage, read> rtracks: array<ReplayTrack>;
@group(1) @binding(12) var<storage, read> rkeys: array<ReplayKey>;
@group(1) @binding(13) var<storage, read> rtrip: array<u32>;
@group(1) @binding(14) var<storage, read_write> rstats: array<atomic<u32>>;

@compute @workgroup_size(64)
fn replay_apply(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= G.n_active) { return; }
    var e = cur[i];
    if ((e.flags & F_REMOVED) != 0u || e.trip >= rcfg.n_trips) { return; }
    let k = rtrip[e.trip];
    if (k == NONE) { return; }
    let tr = rtracks[k];
    // Track times are relative to --begin: seconds of day in f32 would cost centimetres.
    let t = f32(G.step) * P.dt;
    if (t >= tr.release || tr.n == 0u) {
        if (t < tr.release + P.dt * 1.5) { atomicAdd(&rstats[4], 1u); }
        return;
    }
    if ((e.flags & F_SHADOW) != 0u) {
        cur[i].flags |= F_REMOVED;
        atomicAdd(&rstats[2], 1u);
        return;
    }
    let u = (t - tr.t0) / tr.key_dt;
    if (u > f32(tr.n - 1u) + 0.05) {
        // The recording loses it here: it leaves the area, or the tracker lost it.
        cur[i].flags |= F_REMOVED;
        atomicAdd(&rstats[1], 1u);
        return;
    }
    let j = u32(clamp(floor(u), 0.0, f32(tr.n - 1u)));
    let a = rkeys[tr.first + j];
    let b = rkeys[tr.first + min(j + 1u, tr.n - 1u)];
    let f = clamp(u - f32(j), 0.0, 1.0);
    var key = a;
    if (a.lane == b.lane) {
        key.pos = mix(a.pos, b.pos, f);
        key.speed = mix(a.speed, b.speed, f);
    } else if (f >= 0.5) {
        key = b;
    }
    if (u < 0.0) { key.pos = a.pos + a.speed * u * tr.key_dt; }
    if (key.lane != e.lane) {
        e.prev_lane = e.lane;
        e.flags |= F_LANE_CHANGED | F_BEST_DIRTY;
        atomicMin(&tail[key.lane], pack_back(key.pos - types[e.vtype].length, key.speed, 0u));
        atomicAdd(&rstats[3], 1u);
    }
    e.acc = select(0.0, (b.speed - a.speed) / tr.key_dt, j + 1u < tr.n);
    e.lane = key.lane;
    e.pos = key.pos;
    e.speed = key.speed;
    e.v_next = key.speed;
    e.route_i = key.route_i;
    e.phys = e.phys & 0xffffu;
    e.flags &= ~F_HAS_SHADOW;
    cur[i] = e;
    atomicAdd(&rstats[0], 1u);
}
