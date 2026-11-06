//! Macroscopic assignment on the movement table: rung 4, D step 3. No simulation.
//!
//!   macro DIR OUT [--model a|b] [--hours 8] [--iters 40] [--s 1750] [--greens rule|map] [--green-scale 1] [--sigma .15] [--reroute 4] [--period 1800] [--cycle 90] [--cycle-night 75] [--threads 3]
//!
//! Movement costs: free run plus Webster's uniform delay plus Akcelik's overflow, per lane group. Conflicts make it non-separable, so capacity
//! and greens are held for a load and updated after it, and the gap is not expected to fall monotonically (D 4.2).
//! Model a: each hour on its own, every arc of a trip in its departure hour. Model b: periods, trips walk through time, a queue stays for the next period.

mod model;

use std::collections::HashMap;

fn main() -> Result<(), String> {
    let a: Vec<String> = std::env::args().collect();
    let mut kv: HashMap<String, String> = HashMap::new();
    let mut i = 3;
    while i + 1 < a.len() {
        kv.insert(a[i].trim_start_matches("--").to_string(), a[i + 1].clone());
        i += 2;
    }
    let get = |k: &str, d: &str| kv.get(k).cloned().unwrap_or_else(|| d.to_string());
    let threads: usize = get("threads", "3").parse().unwrap();
    rayon::ThreadPoolBuilder::new().num_threads(threads).build_global().unwrap();
    let p = model::Params {
        dynamic: get("model", "a") == "b",
        hours: get("hours", "").split(',').filter(|x| !x.is_empty()).map(|x| x.parse().unwrap()).collect(),
        iters: get("iters", "40").parse().unwrap(),
        s: get("s", "1750").parse().unwrap(),
        rule_greens: get("greens", "rule") == "rule",
        green_scale: get("green-scale", "1").parse().unwrap(),
        sigma: get("sigma", ".15").parse().unwrap(),
        reroute: get("reroute", "4").parse().unwrap(),
        period: get("period", "1800").parse().unwrap(),
        demand_mult: 1.0,
        beta_mult: get("beta-mult", "1").parse().unwrap(),
        retime_every: get("retime-every", "3").parse().unwrap(),
        save_paths: get("save-paths", "0") == "1",
        cycle_day: get("cycle", "90").parse().unwrap(),
        cycle_night: get("cycle-night", "75").parse().unwrap(),
    };
    model::run(&a[1], &a[2], &p)
}
