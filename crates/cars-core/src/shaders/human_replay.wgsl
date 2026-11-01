// The human driver of common.wgsl behind recorded leaders, for research/truth/05 section 9. Same rule,
// same guard and same update as `exec`, one lane per vehicle.

struct RVeh {
    x: f32,
    v: f32,
    af: f32,
    n: f32,
    state: u32,
    acc: f32,
    lead: i32,      // another row of this buffer, or -1 - r for row r of the recording
    t: f32,
    s0: f32,
    amax: f32,
    v0: f32,
    trip: u32,
}

struct RParams {
    dt: f32,
    n: u32,
    samples: u32,   // of the recording, per row
    step: u32,
    per_sample: f32,
    hu_k: f32,
    hu_rho: f32,
    hu_nscale: f32,
    len_model: f32,
    len_guard: f32,
    guard_on: u32,
    pad: u32,
}

@group(0) @binding(0) var<uniform> R: RParams;
@group(0) @binding(1) var<storage, read> prev: array<RVeh>;
@group(0) @binding(2) var<storage, read_write> next: array<RVeh>;
@group(0) @binding(3) var<storage, read> rec: array<vec2f>;
@group(0) @binding(4) var<storage, read> types: array<VType>;
@group(0) @binding(5) var<storage, read_write> stats: array<atomic<u32>>;

@compute @workgroup_size(64)
fn replay(@builtin(global_invocation_id) id: vec3u) {
    let i = id.x;
    if (i >= R.n) { return; }
    var e = prev[i];
    ty = types[0];
    dt = R.dt;
    mu = 0.85;
    ph_load = 1.0;
    ph_power = 1.0;
    ph_gz = 0.0;
    ph_gz_lead = 0.0;
    ph_curved = 1.0;
    ego_acc = e.acc;
    hu_on = true;
    hu_t = e.t;
    hu_s0 = e.s0;
    hu_amax = e.amax;
    hu_af = e.af;
    hu_n = e.n;
    hu_k = R.hu_k;
    hu_v0 = e.v0;
    var xl: f32;
    var vl: f32;
    if (e.lead >= 0) {
        let l = prev[u32(e.lead)];
        xl = l.x;
        vl = l.v;
    } else {
        let at = min(u32(f32(R.step) * R.per_sample + 0.5), R.samples - 1u);
        let r = rec[u32(-1 - e.lead) * R.samples + at];
        xl = r.x;
        vl = r.y;
    }
    let s = xl - e.x;
    let v = e.v;
    let wish = min(hu_next(v, hu_target(v, s - R.len_model, vl, e.v0, e.s0)), max_next_speed(v));
    var v_safe = wish;
    var cert_binds = false;
    if (R.guard_on != 0u) {
        let c = ph_v_cert(s - R.len_guard, v, vl, min(ty.apparent, ty.b_lo), e.acc);
        v_safe = ph_limit(wish, c);
        cert_binds = c < wish;
    }
    let floor_v = ph_floor(v, e.acc);
    var nv = max(min(max(v_safe, 0.0), ph_release(v, e.acc)), floor_v);
    if (v_safe < 0.0) { nv = floor_v; }
    if (R.guard_on == 0u) { nv = max(wish, 0.0); }
    if (v < 0.05) {
        e.state = hu_timer(e.state, v, v_safe);
        if (hu_waiting_to_start(e.state)) { nv = 0.0; }
    }
    var acc = (nv - v) / dt;
    var ds = v * dt + 0.5 * acc * dt * dt;
    if (nv <= 0.0) {
        ds = 0.0;
        if (acc < 0.0) { ds = v * v / (2.0 * -acc); }
        nv = 0.0;
        acc = 0.0;
    }
    e.x += ds;
    e.v = nv;
    e.acc = acc;
    e.af = hu_filtered(v, v_safe, nv);
    e.n = hu_noise_next(e.n, e.trip, R.step, R.hu_rho, R.hu_nscale);
    next[i] = e;
    if (cert_binds) { atomicAdd(&stats[0], 1u); }
    atomicAdd(&stats[1], 1u);
}
