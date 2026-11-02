// Compiled in only for `cars run --why`, by the probes in why.rs. Layout in why.rs too.
@group(0) @binding(63) var<storage, read_write> why_buf: array<u32>;

const WHY_WORDS: u32 = 48u;
const WHY_ITEM_WORDS: u32 = 5u;
const WHY_LIM: u32 = 24u;
const WHY_NONE: u32 = 0xffffffffu;
const WHY_LANE: u32 = 0x80000000u;
const WHY_LINK: u32 = 0x40000000u;
const K_ACCEL: u32 = 1u;
const K_FREE: u32 = 2u;
const K_NEXT_LIMIT: u32 = 3u;
const K_CURVE: u32 = 4u;
const K_LEADER: u32 = 5u;
const K_LEADER_AHEAD: u32 = 6u;
const K_TAIL: u32 = 7u;
const K_SIGNAL: u32 = 8u;
const K_YIELD: u32 = 9u;
const K_EXIT_FULL: u32 = 10u;
const K_JUNCTION: u32 = 11u;
const K_LANE_END: u32 = 12u;
const K_ARRIVAL: u32 = 13u;
const K_LC: u32 = 14u;
const K_ZIPPER: u32 = 15u;
const K_DAWDLE: u32 = 16u;
const K_BRAKE: u32 = 17u;
const K_POWER: u32 = 18u;
const K_COMMITTED: u32 = 19u;
const K_CJ: u32 = 20u;
const K_ABREAST: u32 = 21u;
const K_MISSED: u32 = 22u;

var<private> wy_abreast: bool = false;
var<private> wy_on: bool = false;
var<private> wy_i: u32 = 0u;
var<private> wy_v: f32 = 1e30;
var<private> wy_k: u32 = 0u;
var<private> wy_b: u32 = WHY_NONE;
var<private> wy_g: f32 = 0.0;
var<private> wy_who_k: u32 = 0u;
var<private> wy_who_b: u32 = WHY_NONE;
var<private> wy_stop_k: u32 = K_YIELD;
var<private> wy_stop_b: u32 = WHY_NONE;
var<private> wy_full: u32 = WHY_NONE;
var<private> wy_wanted: u32 = WHY_NONE;
var<private> wy_src: u32 = WHY_NONE;
var<private> wy_closed: u32 = 0u;
var<private> wy_foe: u32 = WHY_NONE;
var<private> wy_foe_link: u32 = WHY_NONE;
var<private> wy_foe_gap: f32 = 0.0;
var<private> wy_zip: f32 = 1e30;
var<private> wy_pre: f32 = -1.0;
var<private> wy_post: f32 = -1.0;

fn why_item_at(i: u32, j: u32) -> u32 { return P.capacity * WHY_WORDS + (i * MAX_ITEMS + j) * WHY_ITEM_WORDS; }

fn why_set(k: u32, v: f32) {
    let s = wy_i * WHY_WORDS + WHY_LIM + k;
    if (v < bitcast<f32>(why_buf[s])) { why_buf[s] = bitcast<u32>(v); }
}

fn why_begin(i: u32) {
    wy_on = true;
    wy_i = i;
    let r = i * WHY_WORDS;
    for (var k = 0u; k < WHY_LIM; k++) { why_buf[r + k] = 0u; }
    for (var k = WHY_LIM; k < WHY_WORDS; k++) { why_buf[r + k] = bitcast<u32>(1e30); }
    why_buf[r + 2u] = WHY_NONE;
    why_buf[r + 5u] = WHY_NONE;
    why_buf[r + 8u] = WHY_NONE;
    why_buf[r + 10u] = WHY_NONE;
    why_buf[r + 11u] = WHY_NONE;
    for (var k = 16u; k < 20u; k++) { why_buf[r + k] = bitcast<u32>(1e30); }
    for (var k = 20u; k < 24u; k++) { why_buf[r + k] = WHY_NONE; }
}

fn why_start(max_v: f32, lane_max: f32) {
    why_set(K_ACCEL, max_v);
    why_set(K_FREE, lane_max);
    wy_v = min(max_v, lane_max);
    wy_k = select(K_FREE, K_ACCEL, max_v < lane_max);
}

fn why_who(trip: u32, first: bool) {
    wy_who_k = select(K_LEADER_AHEAD, K_LEADER, first);
    wy_who_b = trip;
}

fn why_who_tail(lane: u32) {
    wy_who_k = K_TAIL;
    wy_who_b = WHY_LANE | lane;
}

fn why_who_foe(trip: u32) {
    wy_who_k = K_JUNCTION;
    wy_who_b = trip;
}

fn why_who_foe_tail(lane: u32) {
    wy_who_k = K_JUNCTION;
    wy_who_b = WHY_LANE | lane;
}

fn why_lim(v: f32, gap: f32, ls: f32) {
    let r = wy_i * WHY_WORDS;
    why_set(wy_who_k, v);
    if (wy_who_k != K_JUNCTION && why_buf[r + 5u] == WHY_NONE) {
        why_buf[r + 5u] = wy_who_b;
        why_buf[r + 6u] = bitcast<u32>(gap);
        why_buf[r + 7u] = bitcast<u32>(ls);
    }
    if (v < wy_v) {
        wy_v = v;
        wy_k = wy_who_k;
        wy_b = wy_who_b;
        wy_g = gap;
    }
}

fn why_lim_k(k: u32, v: f32) {
    why_set(k, v);
    if (v < wy_v) {
        wy_v = v;
        wy_k = k;
        wy_b = WHY_NONE;
        wy_g = 0.0;
    }
}

fn why_next_lane(lane: u32, v: f32) { why_lim_k(select(K_NEXT_LIMIT, K_CURVE, is_internal(lane)), v); }

// A vehicle already bound to wait before the previous link is not asked to stop sooner.
fn why_floor() {
    if (pl_v > wy_v && pl_n > 0u) {
        let at = why_item_at(wy_i, pl_n - 1u);
        wy_v = pl_v;
        wy_k = (why_buf[at] >> 8u) & 255u;
        wy_b = why_buf[at + 2u];
        wy_g = bitcast<f32>(why_buf[at + 4u]);
    }
}

fn why_stop(state: u32, v: f32, link: u32) {
    wy_stop_k = select(K_YIELD, K_SIGNAL, have_red(state) || have_yellow(state));
    wy_stop_b = WHY_LINK | link;
    why_set(wy_stop_k, v);
}

fn why_item(link: u32, v_pass: f32, v_wait: f32, dist: f32) {
    if (pl_n >= MAX_ITEMS) { return; }
    let r = wy_i * WHY_WORDS;
    // With no link on, this word says which road the route asked for. why_final fills it from wy_foe_link only when a link closed.
    if (link == NONE && pl_n == 0u) { why_buf[r + 11u] = wy_wanted; }
    if (pl_n == 0u) {
        why_buf[r + 8u] = link;
        why_buf[r + 9u] = bitcast<u32>(dist);
    }
    let at = why_item_at(wy_i, pl_n);
    let stopped = v_wait < v_pass;
    why_buf[at] = wy_k | (select(wy_k, wy_stop_k, stopped) << 8u);
    why_buf[at + 1u] = wy_b;
    why_buf[at + 2u] = select(wy_b, wy_stop_b, stopped);
    why_buf[at + 3u] = bitcast<u32>(wy_g);
    why_buf[at + 4u] = bitcast<u32>(select(wy_g, dist, stopped));
}

fn why_wait_lower(last: u32) {
    if (pl_v < items[last].v_wait) {
        let at = why_item_at(wy_i, last - pl_base);
        why_buf[at] = (why_buf[at] & 255u) | (wy_k << 8u);
        why_buf[at + 2u] = wy_b;
        why_buf[at + 4u] = bitcast<u32>(wy_g);
    }
}

// No room past the junction: the link is given up, and it is the far side that holds this car.
fn why_rewind(base: u32, j: u32) {
    let at = why_item_at(base / MAX_ITEMS, j);
    var kw = (why_buf[at] >> 8u) & 255u;
    if (kw == K_YIELD && wy_full != WHY_NONE) {
        kw = K_EXIT_FULL;
        why_buf[at + 2u] = WHY_LANE | wy_full;
    }
    why_buf[at] = kw | (kw << 8u);
    why_buf[at + 1u] = why_buf[at + 2u];
    why_buf[at + 3u] = why_buf[at + 4u];
}

fn why_exec_begin(i: u32) {
    wy_on = true;
    wy_i = i;
}

fn why_closed(reason: u32, link: u32, trip: u32, gap: f32) {
    if (!wy_on) { return; }
    wy_closed = reason;
    wy_foe = trip;
    wy_foe_link = link;
    wy_foe_gap = gap;
}

fn why_final(v_safe: f32, v_next: f32, cj: bool) {
    let r = wy_i * WHY_WORDS;
    var plan = 0u;
    var blame = WHY_NONE;
    var gap = 0.0;
    var j = 255u;
    if (wy_src != WHY_NONE) {
        j = wy_src / 2u;
        let at = why_item_at(wy_i, j);
        if ((wy_src & 1u) != 0u) {
            plan = (why_buf[at] >> 8u) & 255u;
            blame = why_buf[at + 2u];
            gap = bitcast<f32>(why_buf[at + 4u]);
        } else {
            plan = why_buf[at] & 255u;
            blame = why_buf[at + 1u];
            gap = bitcast<f32>(why_buf[at + 3u]);
        }
    }
    if (wy_closed != 0u && plan == K_YIELD) {
        blame = wy_foe;
        if (wy_foe == WHY_NONE) { blame = WHY_LINK | wy_foe_link; }
    }
    if (v_safe == wy_zip && wy_zip < 1e29) {
        plan = K_ZIPPER;
        why_set(K_ZIPPER, wy_zip);
    }
    let tol = 1e-3;
    var dec = plan;
    if (cj) {
        dec = K_CJ;
        why_set(K_CJ, v_next);
    } else if ((cur[wy_i].flags & F_REROUTE) != 0u && v_next <= v_safe + tol) {
        dec = K_MISSED;
    } else if (wy_abreast && v_next <= v_safe + tol) {
        dec = K_ABREAST;
        why_set(K_ABREAST, v_next);
    } else if (v_next > v_safe + tol) {
        if (v_next <= fin_min + tol) {
            dec = K_BRAKE;
            why_set(K_BRAKE, fin_min);
        } else if (wy_post > wy_pre + tol) {
            dec = K_LC;
            why_set(K_LC, wy_post);
        } else {
            dec = K_COMMITTED;
            why_set(K_COMMITTED, v_next);
        }
    } else if (wy_post < wy_pre - tol) {
        dec = K_LC;
        why_set(K_LC, wy_post);
    } else if (v_next < fin_max - tol) {
        // Noise on top of what the limit asked for: the limit still decided.
        why_set(K_DAWDLE, v_next);
    } else if (fin_max < v_safe - tol) {
        dec = K_POWER;
        why_set(K_POWER, fin_max);
    }
    why_buf[r] = G.step + 1u;
    why_buf[r + 1u] = dec | (plan << 8u) | (j << 16u) | (wy_closed << 24u);
    why_buf[r + 2u] = blame;
    why_buf[r + 3u] = bitcast<u32>(gap);
    why_buf[r + 4u] = bitcast<u32>(v_safe);
    why_buf[r + 10u] = wy_foe;
    if (wy_closed != 0u) { why_buf[r + 11u] = wy_foe_link; }
    why_buf[r + 12u] = bitcast<u32>(wy_foe_gap);
}

fn why_lc(side: u32, i: u32, state: u32, n: LcNeighbors) {
    let r = i * WHY_WORDS;
    why_buf[r + 13u + side] = state;
    why_buf[r + 16u + side * 2u] = bitcast<u32>(n.gap);
    why_buf[r + 17u + side * 2u] = bitcast<u32>(n.f_gap);
    why_buf[r + 20u + side * 2u] = n.leader_trip;
    why_buf[r + 21u + side * 2u] = n.f_trip;
}

fn why_lc_end(i: u32, chosen: i32, state_r: u32, state_l: u32) {
    let r = i * WHY_WORDS;
    why_buf[r + 13u] = state_r;
    why_buf[r + 14u] = state_l;
    why_buf[r + 15u] = bitcast<u32>(chosen);
}
