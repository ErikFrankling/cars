// Lane changing is added on top of the step kernels.

@compute @workgroup_size(64)
fn lc_decide(@builtin(global_invocation_id) id: vec3u) {
    if (id.x >= G.n_active) { return; }
}
