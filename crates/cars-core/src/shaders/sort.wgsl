// Stable LSD radix sort of (key, value) pairs in blocks: every invocation owns one block of keys
// and one histogram, so no atomics are needed. Passes alternate between two pairs of buffers.

struct Pass {
    shift: u32,
    block: u32,
}

override DIGIT_BITS: u32 = 8;
override RADIX: u32 = 1u << DIGIT_BITS;

@group(0) @binding(0) var<uniform> S: Pass;
@group(0) @binding(1) var<storage, read> G: Globals;
@group(0) @binding(2) var<storage, read> keys_in: array<u32>;
@group(0) @binding(3) var<storage, read> vals_in: array<u32>;
@group(0) @binding(4) var<storage, read_write> keys_out: array<u32>;
@group(0) @binding(5) var<storage, read_write> vals_out: array<u32>;
@group(0) @binding(6) var<storage, read_write> hist: array<u32>;
@group(0) @binding(7) var<storage, read_write> totals: array<u32>;

@compute @workgroup_size(64)
fn count(@builtin(global_invocation_id) id: vec3u) {
    let b = id.x;
    if (b >= G.blocks) { return; }
    let base = b * RADIX;
    for (var d = 0u; d < RADIX; d++) { hist[base + d] = 0u; }
    let start = b * S.block;
    let end = min(start + S.block, G.n);
    for (var i = start; i < end; i++) {
        let d = (keys_in[i] >> S.shift) & (RADIX - 1u);
        hist[base + d] += 1u;
    }
}

// Turn per-block counts into running offsets per digit.
@compute @workgroup_size(64)
fn prefix(@builtin(global_invocation_id) id: vec3u) {
    let d = id.x;
    if (d >= RADIX) { return; }
    var sum = 0u;
    for (var b = 0u; b < G.blocks; b++) {
        let at = b * RADIX + d;
        let c = hist[at];
        hist[at] = sum;
        sum += c;
    }
    totals[d] = sum;
}

@compute @workgroup_size(1)
fn starts() {
    var sum = 0u;
    for (var d = 0u; d < RADIX; d++) {
        let c = totals[d];
        totals[d] = sum;
        sum += c;
    }
}

@compute @workgroup_size(64)
fn scatter(@builtin(global_invocation_id) id: vec3u) {
    let b = id.x;
    if (b >= G.blocks) { return; }
    let base = b * RADIX;
    let start = b * S.block;
    let end = min(start + S.block, G.n);
    for (var i = start; i < end; i++) {
        let k = keys_in[i];
        let d = (k >> S.shift) & (RADIX - 1u);
        let at = base + d;
        let o = hist[at];
        hist[at] = o + 1u;
        let idx = totals[d] + o;
        keys_out[idx] = k;
        vals_out[idx] = vals_in[i];
    }
}
