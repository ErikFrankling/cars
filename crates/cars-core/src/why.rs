//! Per-step reasons, on demand. `step.wgsl` and `lc.wgsl` carry no debugging code: the probes below are
//! patched into their text only for `Sim::with_why`, so a normal run compiles the same bytes as ever.
//! A probe whose anchor has gone after a merge is named at start up, and in `cargo test -p cars-core`.
use bytemuck::{Pod, Zeroable};

pub const WHY_WGSL: &str = include_str!("shaders/why.wgsl");
/// Above any binding the main layout will reach, so branches adding buffers never collide.
pub const WHY_BINDING: u32 = 63;
pub const WHY_WORDS: u64 = 48;
pub const ITEM_WORDS: u64 = 5;
pub const MAX_ITEMS: u64 = 8;
pub const LIMITS: usize = 24;
pub const WHY_NONE: u32 = u32::MAX;
pub const BLAME_LANE: u32 = 0x8000_0000;
pub const BLAME_LINK: u32 = 0x4000_0000;

/// Names of the decider and limit kinds, in the order of `K_*` in why.wgsl.
pub const KINDS: [&str; 23] = [
    "none", "accel", "free", "next_limit", "curve", "leader", "leader_ahead", "tail", "signal", "yield", "exit_full", "junction", "lane_end", "arrival", "lane_change", "zipper",
    "dawdle", "brake_limit", "power", "committed", "coordinator", "abreast", "missed_turn",
];
pub const CLOSED: [&str; 4] = ["", "red", "stop_sign", "foe"];

/// One vehicle in one step, as written to the `.why` file beside a trace. Layout in DEBUGGING.md.
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable, Default)]
pub struct WhyRecord {
    pub decider: u8,
    pub plan: u8,
    pub item: u8,
    pub closed: u8,
    pub blame: u32,
    pub blame_gap: f32,
    pub v_safe: f32,
    pub leader: u32,
    pub leader_gap: f32,
    pub leader_speed: f32,
    pub first_link: u32,
    pub first_dist: f32,
    pub foe_trip: u32,
    pub foe_link: u32,
    pub foe_gap: f32,
    pub lc_right: u32,
    pub lc_left: u32,
    pub lc_chosen: i32,
    pub right_gap: f32,
    pub right_follow_gap: f32,
    pub left_gap: f32,
    pub left_follow_gap: f32,
    pub right_leader: u32,
    pub right_follower: u32,
    pub left_leader: u32,
    pub left_follower: u32,
    /// m/s × 128, 0xffff when that limit did not speak this step.
    pub limits: [u16; 22],
}

impl WhyRecord {
    /// None unless the record was finished on this step.
    pub fn from_words(w: &[u32], step: u32) -> Option<Self> {
        if w[0] != step {
            return None;
        }
        let f = |k: usize| f32::from_bits(w[k]);
        let mut limits = [0xffffu16; 22];
        for (k, l) in limits.iter_mut().enumerate().take(21) {
            let v = f(LIMITS + k);
            if v < 500.0 {
                *l = (v.max(0.0) * 128.0).round().min(65534.0) as u16;
            }
        }
        Some(Self {
            decider: w[1] as u8,
            plan: (w[1] >> 8) as u8,
            item: (w[1] >> 16) as u8,
            closed: (w[1] >> 24) as u8,
            blame: w[2],
            blame_gap: f(3),
            v_safe: f(4),
            leader: w[5],
            leader_gap: f(6),
            leader_speed: f(7),
            first_link: w[8],
            first_dist: f(9),
            foe_trip: w[10],
            foe_link: w[11],
            foe_gap: f(12),
            lc_right: w[13],
            lc_left: w[14],
            lc_chosen: w[15] as i32,
            right_gap: f(16),
            right_follow_gap: f(17),
            left_gap: f(18),
            left_follow_gap: f(19),
            right_leader: w[20],
            right_follower: w[21],
            left_leader: w[22],
            left_follower: w[23],
            limits,
        })
    }
}

struct Probe {
    /// Functions to look in, `|` between them: code moves between branches.
    func: &'static str,
    find: &'static str,
    with: &'static str,
    /// Every occurrence in the function, rather than the first.
    all: bool,
}

const fn p(func: &'static str, find: &'static str, with: &'static str) -> Probe {
    Probe { func, find, with, all: false }
}
const fn every(func: &'static str, find: &'static str, with: &'static str) -> Probe {
    Probe { func, find, with, all: true }
}

const PROBES: &[Probe] = &[
    p("plan", "let ego = cur[i];", "let ego = cur[i]; why_begin(i);"),
    p("plan", "pl_v = min(max_v, lane_max);", "pl_v = min(max_v, lane_max); why_start(max_v, lane_max);"),
    p("adapt_to_lane", "adapt_to_leader(gap, seen, l_len, lead.speed", "why_who(lead.trip, first); adapt_to_leader(gap, seen, l_len, lead.speed"),
    p("adapt_to_lane", "adapt_to_leader(gap, seen, l_len, unpack_speed(p)", "why_who_tail(lane); adapt_to_leader(gap, seen, l_len, unpack_speed(p)"),
    p("adapt_to_leader", "pl_v = min(pl_v, vsafe);", "why_lim(vsafe, gap, ls); pl_v = min(pl_v, vsafe);"),
    p("adapt_to_junction_leader", "pl_v = min(pl_v, vsafe);", "why_lim(vsafe, gap, ls); pl_v = min(pl_v, vsafe);"),
    p("check_link_leader", "adapt_to_junction_leader(gap, critical,", "why_who_foe(f.trip); adapt_to_junction_leader(gap, critical,"),
    p("check_link_leader", "adapt_to_junction_leader(gap, false,", "why_who_foe_tail(cf.foe_lane); adapt_to_junction_leader(gap, false,"),
    p("check_link_leader", "pl_v = max(pl_v, items[pl_base + pl_n - 1u].v_wait);", "pl_v = max(pl_v, items[pl_base + pl_n - 1u].v_wait); why_floor();"),
    p("plan", "items[last].v_wait = min(items[last].v_wait, pl_v);", "why_wait_lower(last); items[last].v_wait = min(items[last].v_wait, pl_v);"),
    p("plan", "pl_v = min(pl_v, va);", "why_lim_k(K_ARRIVAL, va); pl_v = min(pl_v, va);"),
    p("plan", "pl_v = min(va, pl_v);\n            push_item(NONE", "why_lim_k(K_LANE_END, va); wy_wanted = routes[route_i + 1u]; pl_v = min(va, pl_v);\n            push_item(NONE"),
    p("plan", "pl_v_wait = min(pl_v, stop_v);", "pl_v_wait = min(pl_v, stop_v); why_stop(state, stop_v, link);"),
    p("plan", "pl_v = min(va, pl_v);\n        let len", "why_next_lane(next_lane, va); pl_v = min(va, pl_v);\n        let len"),
    p("push_item", "items[pl_base + pl_n] = it;", "why_item(link, v_pass, v_wait, dist); items[pl_base + pl_n] = it;"),
    p("check_rewind", "had |= 1u << j;", "had |= 1u << j; wy_full = to;"),
    p("check_rewind", "if ((lane_free[via].flags & FREE_STOPPED) != 0u) { found = true; }", "if ((lane_free[via].flags & FREE_STOPPED) != 0u) { found = true; wy_full = via; }"),
    p("check_rewind", "items[base + j].v_pass = it.v_wait;", "why_rewind(base, j); items[base + j].v_pass = it.v_wait;"),
    p("exec", "var e = cur[i];", "var e = cur[i]; why_exec_begin(i);"),
    every("walk_links|exec", "v_safe = it.v_wait;", "v_safe = it.v_wait; wy_src = j * 2u + 1u;"),
    p("walk_links", "(*e).flags |= F_DENIED;", "(*e).flags |= F_DENIED; wy_full = links[it.link].to_lane;"),
    every("walk_links|exec", "v_safe = it.v_pass;", "v_safe = it.v_pass; wy_src = j * 2u;"),
    p("exec", "v_safe = min(v_safe, f32(bound) / 1024.0 - 0.002);", "v_safe = min(v_safe, f32(bound) / 1024.0 - 0.002); wy_abreast = (e.flags & F_ABREAST) != 0u;"),
    p("exec", "v_safe = min(v_safe, v_zipper);", "v_safe = min(v_safe, v_zipper); wy_zip = v_zipper;"),
    p("exec", "v_next = lc_patch_speed(v_next, e, vmax_here);", "wy_pre = v_next; v_next = lc_patch_speed(v_next, e, vmax_here); wy_post = v_next;"),
    every("exec", "e.speed = v_next;", "why_final(v_safe, v_next, cj_controlled(e)); e.speed = v_next;"),
    p("link_opened", "if (have_red(state)) { return false; }", "if (have_red(state)) { why_closed(1u, link, WHY_NONE, 0.0); return false; }"),
    p("link_opened", "if (state == CH_w && wait < dt) { return false; }", "if (state == CH_w && wait < dt) { why_closed(2u, link, WHY_NONE, 0.0); return false; }"),
    p("link_opened", "if (state == CH_s && wait < dt) { return false; }", "if (state == CH_s && wait < dt) { why_closed(2u, link, WHY_NONE, 0.0); return false; }"),
    p(
        "link_opened",
        "if (blocked_by_foe(r, a, l, va, vl, same_target, impatience, decel, wait, foe_state)) { return false; }",
        "if (blocked_by_foe(r, a, l, va, vl, same_target, impatience, decel, wait, foe_state)) { why_closed(3u, foe, r.trip, r.arrival - a); return false; }",
    ),
    p("lc_evaluate", "state_r = wants_change(-1, e, own, n, b, dest, i);", "state_r = wants_change(-1, e, own, n, b, dest, i); why_lc(0u, i, state_r, n);"),
    p("lc_evaluate", "state_l = wants_change(1, e, own, n, b, dest, i);", "state_l = wants_change(1, e, own, n, b, dest, i); why_lc(1u, i, state_l, n);"),
    p("lc_evaluate", "if (chosen == 0) { return; }", "why_lc_end(i, chosen, state_r, state_l); if (chosen == 0) { return; }"),
];

/// Byte range of a function's body, by counting braces from its signature.
fn body(src: &str, func: &str) -> Option<(usize, usize)> {
    let start = src.find(&format!("fn {func}("))?;
    let open = start + src[start..].find('{')?;
    let mut depth = 0i32;
    for (k, c) in src[open..].char_indices() {
        match c {
            '{' => depth += 1,
            '}' => {
                depth -= 1;
                if depth == 0 {
                    return Some((open, open + k + 1));
                }
            }
            _ => {}
        }
    }
    None
}

/// The kernels with every probe in, and the probe `why.wgsl` after them. Errors list what no longer fits.
pub fn instrument(src: &str) -> Result<String, Vec<String>> {
    let mut out = src.to_string();
    let mut lost = Vec::new();
    for probe in PROBES {
        let place = probe.func.split('|').filter_map(|f| body(&out, f)).find(|&(a, b)| out[a..b].contains(probe.find));
        let Some((a, b)) = place else {
            lost.push(format!("{}: {}", probe.func, probe.find.replace('\n', " ")));
            continue;
        };
        let text = &out[a..b];
        let new = if probe.all { text.replace(probe.find, probe.with) } else { text.replacen(probe.find, probe.with, 1) };
        out.replace_range(a..b, &new);
    }
    if !lost.is_empty() {
        return Err(lost);
    }
    out.push('\n');
    out.push_str(WHY_WGSL);
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_probe_finds_its_place() {
        let src = format!("{}\n{}\n{}\n{}", include_str!("shaders/common.wgsl"), include_str!("shaders/route.wgsl"), include_str!("shaders/step.wgsl"), include_str!("shaders/lc.wgsl"));
        if let Err(lost) = instrument(&src) {
            panic!("probes that no longer fit:\n  {}", lost.join("\n  "));
        }
    }

    #[test]
    fn file_record_is_packed() {
        assert_eq!(size_of::<WhyRecord>(), 136);
    }
}
