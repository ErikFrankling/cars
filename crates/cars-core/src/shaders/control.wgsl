// Counts and indirect dispatch sizes. Separate from the other kernels because the indirect buffer
// cannot be bound while it is used for a dispatch.

@group(0) @binding(0) var<uniform> P: Params;
@group(0) @binding(1) var<storage, read_write> G: Globals;
@group(0) @binding(2) var<storage, read_write> C: array<atomic<u32>>;
@group(0) @binding(3) var<storage, read_write> indirect: array<u32>;

const C_NEW: u32 = 0u;
const C_REMOVED: u32 = 1u;

@compute @workgroup_size(1)
fn begin() {
    G.step += 1u;
    let n = G.n_active + atomicExchange(&C[C_NEW], 0u);
    G.n = n;
    G.blocks = (n + P.block - 1u) / P.block;
    atomicStore(&C[C_REMOVED], 0u);
    indirect[0] = (n + 63u) / 64u;
    indirect[1] = 1u;
    indirect[2] = 1u;
    indirect[3] = (G.blocks + 63u) / 64u;
    indirect[4] = 1u;
    indirect[5] = 1u;
}

@compute @workgroup_size(1)
fn after_gather() {
    let n = G.n - atomicLoad(&C[C_REMOVED]);
    G.n_active = n;
    indirect[6] = (n + 63u) / 64u;
    indirect[7] = 1u;
    indirect[8] = 1u;
}
