//! Route assignment, calibration and demand verdicts on the GPU simulator.

use std::path::PathBuf;
use std::time::Instant;

use cars_assign::calibrate::{self, CountRow, Counts, Role};
use cars_assign::costs::{BIN_S, CostTable};
use cars_assign::cuts;
use cars_assign::day::{Engine, NoPause, run_day};
use cars_assign::driver::{self, CalibrateOpts, LoopOpts, Setup, load_costs, setup};
use cars_assign::enroute::{Enroute, Incident};
use cars_assign::population::Traveller;
use cars_assign::route::Work;
use cars_assign::update::{self, Rule, Schedule};
use cars_assign::{mix, unit};
use clap::{Parser, Subcommand};
use rayon::prelude::*;

#[derive(Parser)]
struct Args {
    #[arg(long)]
    scenario: PathBuf,
    #[arg(long)]
    out: PathBuf,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Free-flow routes and pre-simulation checks. No GPU, so this can run on the homelab.
    Init,
    /// Time k replicas of the world, on whatever routes the scenario gives.
    Replicas {
        #[arg(long, value_delimiter = ',', default_value = "1,2,4")]
        ks: Vec<usize>,
    },
    /// ALT against plain Dijkstra on real origins and destinations.
    Routebench {
        #[arg(long, default_value_t = 10000)]
        paths: usize,
    },
    /// Assignment iterations, resuming from the checkpoint in `out`.
    Loop {
        #[arg(long, default_value_t = 30)]
        iters: u32,
        /// Stop after this many, so that others get the GPU.
        #[arg(long, default_value_t = 1000)]
        chunk: u32,
        #[arg(long, default_value = "capped")]
        rule: String,
        #[arg(long)]
        memory: Option<f32>,
        #[arg(long, default_value_t = 0.02)]
        target_gap: f64,
        #[arg(long, default_value_t = 1)]
        replicas: u32,
    },
    /// Frozen routes on unseen seeds.
    Eval {
        #[arg(long, value_delimiter = ',', default_value = "9001,9002,9003,9004")]
        seeds: Vec<u64>,
        #[arg(long, default_value = "unseen")]
        tag: String,
        /// Seeds per world. Sequential unless replicas pay.
        #[arg(long, default_value_t = 1)]
        per_world: usize,
        /// Read the blind test rows. Works once per run directory.
        #[arg(long)]
        open_test: bool,
    },
    /// The verdict ladder.
    Verdict {
        #[arg(long, default_value_t = 9101)]
        seed: u64,
    },
    /// Departure-time adaptation with its guard, after route convergence.
    Depart {
        #[arg(long, default_value_t = 15)]
        iters: u32,
        #[arg(long, default_value_t = 0.5)]
        early: f32,
        #[arg(long, default_value_t = 2.0)]
        late: f32,
        #[arg(long)]
        consistent: bool,
    },
    /// Measure discharge per cut link in isolation, into a discharge file.
    Discharge {
        #[arg(long)]
        file: PathBuf,
        #[arg(long, default_value_t = 2)]
        max_level: u32,
    },
    /// A count file from a simulated day, for tests with known truth, with the seed noise between days.
    SynthCounts {
        #[arg(long)]
        file: PathBuf,
        #[arg(long, default_value_t = 0.3)]
        site_share: f64,
        #[arg(long, default_value_t = 200.0)]
        min_flow: f64,
        #[arg(long, default_value_t = 9201)]
        seed: u64,
    },
    /// Damage a converged OD: a scale and lognormal noise per cell. Starts a test with known truth.
    Perturb {
        #[arg(long)]
        into: PathBuf,
        #[arg(long, default_value_t = 1.3)]
        scale: f64,
        #[arg(long, default_value_t = 0.5)]
        sigma: f64,
        #[arg(long, default_value_t = 16)]
        zones: usize,
        #[arg(long, default_value_t = 77)]
        seed: u64,
    },
    /// Cell fit, guards, warm re-assignment.
    Calibrate {
        #[arg(long, default_value_t = 3)]
        rounds: u32,
        #[arg(long, default_value_t = 8)]
        warm: u32,
        #[arg(long)]
        noise_floor: f64,
        #[arg(long)]
        report_only_tag: bool,
        #[arg(long, default_value_t = 16)]
        zones: usize,
    },
    /// Normal day and incident day for each navigator share.
    Incident {
        #[arg(long, value_delimiter = ',', default_value = "0,0.3,0.6,1")]
        navigators: Vec<f64>,
        #[arg(long, default_value_t = 4)]
        busiest: usize,
        #[arg(long, default_value_t = 28800.0)]
        t0: f32,
        #[arg(long, default_value_t = 31500.0)]
        t1: f32,
        #[arg(long, default_value_t = 1.0)]
        speed: f32,
        #[arg(long, default_value_t = 9301)]
        seed: u64,
    },
}

fn main() {
    let args = Args::parse();
    if let Err(e) = run(args) {
        eprintln!("error: {e}");
        std::process::exit(1);
    }
}

fn run(args: Args) -> Result<(), String> {
    std::fs::create_dir_all(&args.out).map_err(|e| e.to_string())?;
    let mut x = setup(&args.scenario)?;
    match args.cmd {
        Cmd::Init => driver::prepare_routes(&mut x, &args.out)?,
        Cmd::Replicas { ks } => replicas(&mut x, &args.out, &ks)?,
        Cmd::Routebench { paths } => routebench(&mut x, &args.out, paths)?,
        Cmd::Loop { iters, chunk, rule, memory, target_gap, replicas } => {
            let rule = match rule.as_str() {
                "capped" => Rule::Capped { share: x.s.share },
                "everyone" => Rule::Everyone,
                "bounded" => Rule::Bounded { chance: 0.2 },
                other => return Err(format!("unknown rule {other}")),
            };
            let memory = memory.unwrap_or(x.s.memory);
            let done = driver::assignment(&mut x, &args.out, &LoopOpts { iters, chunk, rule, memory, target_gap, replicas })?;
            println!("{}", if done { "done" } else { "more" });
        }
        Cmd::Eval { seeds, tag, per_world, open_test } => {
            let r = driver::evaluate(&mut x, &args.out, &seeds, &tag, per_world, open_test)?;
            println!("{}", serde_json::to_string_pretty(&r).unwrap());
        }
        Cmd::Verdict { seed } => {
            let r = driver::verdict(&mut x, &args.out, seed)?;
            println!("{}", serde_json::to_string_pretty(&r).unwrap());
        }
        Cmd::Depart { iters, early, late, consistent } => {
            let memory = x.s.memory;
            let r = driver::departures(&mut x, &args.out, iters, Schedule { early, late }, memory, consistent)?;
            let name = format!("depart_{early}_{late}{}.json", if consistent { "_consistent" } else { "" });
            std::fs::write(args.out.join(name), serde_json::to_string_pretty(&r).unwrap()).map_err(|e| e.to_string())?;
            println!("{}", r["status"]);
        }
        Cmd::Discharge { file, max_level } => discharge(&mut x, &file, max_level)?,
        Cmd::SynthCounts { file, site_share, min_flow, seed } => synth_counts(&mut x, &args.out, &file, site_share, min_flow, seed)?,
        Cmd::Perturb { into, scale, sigma, zones, seed } => perturb(&mut x, &args.out, &into, scale, sigma, zones, seed)?,
        Cmd::Calibrate { rounds, warm, noise_floor, report_only_tag, zones } => {
            let o = CalibrateOpts { rounds, warm, noise_floor, enforce_tag: !report_only_tag, zones, seed: x.s.seed };
            let r = driver::calibration(&mut x, &args.out, &o)?;
            println!("{}", serde_json::to_string_pretty(&r).unwrap());
        }
        Cmd::Incident { navigators, busiest, t0, t1, speed, seed } => incident(&mut x, &args.out, &navigators, busiest, t0, t1, speed, seed)?,
    }
    Ok(())
}

/// The early measurement the spec asks for: does k worlds cost k times one?
fn replicas(x: &mut Setup, out: &std::path::Path, ks: &[usize]) -> Result<(), String> {
    driver::prepare_routes(x, out)?;
    let mut rows = Vec::new();
    let mut base = None;
    for &k in ks {
        let seeds: Vec<u64> = (0..k as u64).map(|i| 500 + i).collect();
        let t = Instant::now();
        let mut e = Engine::new(&x.net, &mut x.pop, &x.s, &seeds)?;
        let setup_s = t.elapsed().as_secs_f64();
        let sim = e.sim.as_ref().unwrap();
        let buffers = sim.buffers.total_bytes;
        let (lanes, links, trips) = (e.world.lanes.len(), e.world.links.len(), e.world.trips.len());
        let day = run_day(&mut e, &x.supply, &x.pop, &x.s, &mut NoPause);
        let sim = e.sim.as_ref().unwrap();
        let (gpu_ms, encode_ms) = (sim.gpu_ms, sim.encode_ms);
        let steps = sim.step;
        let wall = day.wall_s;
        let per_step_ms = wall * 1000.0 / steps.max(1) as f64;
        let b = *base.get_or_insert(per_step_ms);
        let row = serde_json::json!({
            "k": k, "steps": steps, "wall_s": wall, "per_step_ms": per_step_ms, "ratio_to_k1": per_step_ms / b,
            "gpu_ms": gpu_ms, "encode_ms": encode_ms, "setup_s": setup_s, "buffer_mb": buffers / 1_000_000,
            "lanes": lanes, "links": links, "trips": trips, "peak_active": day.peak_active,
            "vehicle_updates_m_s": day.vehicle_steps as f64 / wall / 1e6, "arrived": day.ledgers.iter().map(|l| l.arrived).sum::<u64>(),
        });
        eprintln!("{row}");
        rows.push(row);
        drop(e);
    }
    std::fs::write(out.join("replicas.json"), serde_json::to_string_pretty(&rows).unwrap()).map_err(|e| e.to_string())?;
    println!("{}", serde_json::to_string_pretty(&rows).unwrap());
    Ok(())
}

fn routebench(x: &mut Setup, out: &std::path::Path, paths: usize) -> Result<(), String> {
    driver::prepare_routes(x, out)?;
    let n_bins = x.s.n_bins();
    // Congestion up to 3 times free flow in a space-time pattern, as in the first benchmark.
    let mut costs = CostTable::free_flow(&x.supply, n_bins);
    for e in 0..costs.n_edges {
        let w = (mix(9, e as u64) & 0xff) as f32 / 255.0;
        for b in 0..n_bins {
            let h = b as f32 * BIN_S / 3600.0;
            let peak = (-(h - 8.0).powi(2) / 2.0).exp() + (-(h - 17.0).powi(2) / 3.0).exp();
            costs.c[e * n_bins + b] = x.supply.ff[e] * (1.0 + 2.0 * w * peak);
        }
    }
    costs.enforce_fifo();
    let n = x.pop.travellers.len();
    let step = (n / paths.max(1)).max(1);
    let sample: Vec<&Traveller> = x.pop.travellers.iter().step_by(step).take(paths).collect();
    let g_for = |t: &Traveller| &x.graphs.by_mask[&x.pop.demand.vtypes[t.vtype as usize].vclass];
    let mut w = Work::new(x.graphs.work_size);
    let t0 = Instant::now();
    let d: Vec<Option<f32>> = sample.iter().map(|t| g_for(t).path(&costs, &mut w, x.supply.dense[t.o_edge as usize], x.supply.dense[t.d_edge as usize], t.depart_s, false).map(|p| p.1)).collect();
    let d_s = t0.elapsed().as_secs_f64();
    let d_settled = w.settled;
    let mut w = Work::new(x.graphs.work_size);
    let t0 = Instant::now();
    let a: Vec<Option<f32>> = sample.iter().map(|t| g_for(t).path(&costs, &mut w, x.supply.dense[t.o_edge as usize], x.supply.dense[t.d_edge as usize], t.depart_s, true).map(|p| p.1)).collect();
    let a_s = t0.elapsed().as_secs_f64();
    let (mut worst, mut wrong, mut sum) = (0f32, 0u64, 0f64);
    for (p, q) in d.iter().zip(&a) {
        match (p, q) {
            (Some(p), Some(q)) => {
                worst = worst.max((p - q).abs());
                sum += *p as f64;
            }
            (None, None) => {}
            _ => wrong += 1,
        }
    }
    let m = sample.len() as f64;
    let r = serde_json::json!({
        "paths": sample.len(), "dijkstra_ms": d_s * 1000.0 / m, "alt_ms": a_s * 1000.0 / m,
        "dijkstra_settled": d_settled as f64 / m, "alt_settled": w.settled as f64 / m,
        "worst_abs_cost_difference_s": worst, "reachability_mismatches": wrong, "mean_cost_s": sum / m,
    });
    println!("{}", serde_json::to_string_pretty(&r).unwrap());
    std::fs::write(out.join("routebench.json"), serde_json::to_string_pretty(&r).unwrap()).map_err(|e| e.to_string())?;
    Ok(())
}

/// Discharge per cut link, measured with nothing else on the network.
fn discharge(x: &mut Setup, file: &std::path::Path, max_level: u32) -> Result<(), String> {
    let succ = cuts::successors(&x.net, &x.supply);
    let mut family = cuts::cluster_cuts(&x.supply, &succ);
    family.retain(|c| c.name[1..].split('_').next().and_then(|k| k.parse::<u32>().ok()).is_some_and(|k| k <= 1 << max_level));
    if let Some(p) = &x.s.cuts {
        family.extend(cuts::load_named_cuts(p, &x.net, &x.supply, &succ)?);
    }
    let mut edges: Vec<u32> = family.iter().flat_map(|c| c.out_edges.iter().chain(&c.in_edges).copied()).collect();
    edges.sort_unstable();
    edges.dedup();
    let rates = driver::measure_discharge(x, &edges)?;
    let mut text = String::from("edge,veh_s,nominal_veh_s\n");
    for (d, r) in rates {
        text.push_str(&format!("{},{:.4},{:.4}\n", x.net.edges[x.supply.normal[d as usize] as usize].id, r, x.supply.nominal_capacity(d as usize)));
    }
    std::fs::write(file, text).map_err(|e| e.to_string())
}

fn synth_counts(x: &mut Setup, out: &std::path::Path, file: &std::path::Path, site_share: f64, min_flow: f64, seed: u64) -> Result<(), String> {
    driver::prepare_routes(x, out)?;
    let mut e = Engine::new(&x.net, &mut x.pop, &x.s, &[seed])?;
    let day = run_day(&mut e, &x.supply, &x.pop, &x.s, &mut NoPause);
    e.load_day(&x.net, &mut x.pop, &[seed + 1])?;
    let other = run_day(&mut e, &x.supply, &x.pop, &x.s, &mut NoPause);
    drop(e);
    let mut counts = Counts::default();
    let n_bins = day.counts.n_bins;
    let hours = (x.s.horizon / 3600.0).ceil() as usize;
    for d in 0..x.supply.n() {
        let flow: f64 = (0..n_bins).map(|b| day.counts.n_in[d * n_bins + b] as f64).sum();
        if flow < min_flow || unit(seed ^ 0xA5, d as u64) >= site_share {
            continue;
        }
        let site = counts.sites.len() as u32;
        counts.sites.push(format!("s{d}"));
        for h in 0..hours {
            let row = CountRow { site, edge: d as u32, t0: h as f32 * 3600.0, t1: (h + 1) as f32 * 3600.0, y: 0.0, role: Role::Train, corridor: site };
            let y = calibrate::simulated(&row, &day.counts);
            if y > 0.0 {
                counts.rows.push(CountRow { y, ..row });
            }
        }
    }
    counts.split(&x.net, &x.supply, 500.0, (0.6, 0.2), (15.0 * 3600.0, 18.0 * 3600.0), seed);
    counts.write(file, &x.net, &x.supply)?;
    let by_seed = calibrate::count_error(&counts.rows, Role::Train, |c| calibrate::simulated(c, &other.counts));
    let by_seed_all = {
        let mut rows = counts.rows.clone();
        for r in &mut rows {
            r.role = Role::Train;
        }
        calibrate::count_error(&rows, Role::Train, |c| calibrate::simulated(c, &other.counts))
    };
    let r = serde_json::json!({"sites": counts.sites.len(), "rows": counts.rows.len(), "seed_noise_wape_train": by_seed.wape, "seed_noise_wape_all": by_seed_all.wape, "seed_noise_geh5_all": by_seed_all.geh5});
    println!("{r}");
    std::fs::write(file.with_extension("noise.json"), r.to_string()).map_err(|e| e.to_string())
}

fn perturb(x: &mut Setup, out: &std::path::Path, into: &std::path::Path, scale: f64, sigma: f64, zones: usize, seed: u64) -> Result<(), String> {
    driver::prepare_routes(x, out)?;
    std::fs::create_dir_all(into).map_err(|e| e.to_string())?;
    let zone = calibrate::zones(&x.supply, zones);
    let costs = load_costs(&x.supply, x.s.n_bins(), &out.join("costs.bin"))?;
    let a = calibrate::build_assignment(&x.pop, &x.supply, &costs, &zone, &[]);
    let mut truth = String::from("cell,q\n");
    for (i, c) in a.cells.iter().enumerate() {
        truth.push_str(&format!("{},{}\n", c, a.q[i]));
    }
    std::fs::write(into.join("truth_cells.csv"), truth).map_err(|e| e.to_string())?;
    let target: Vec<f64> = a.cells.iter().zip(&a.q).map(|(c, q)| {
        // Zone pairs share their noise, as a wrong prior would.
        let pair = c >> 16;
        let (u1, u2) = (unit(seed, pair).max(1e-12), unit(seed ^ 1, pair));
        let z = (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos();
        q * scale * (sigma * z - sigma * sigma / 2.0).exp()
    }).collect();
    let (added, removed) = calibrate::apply_cells(&mut x.pop, &a, &target, seed);
    eprintln!("perturbed: {added} added, {removed} removed, {} travellers", x.pop.travellers.len());
    // Forget everything the true assignment learned: the prior starts from free flow.
    update::forget_routes(&mut x.pop);
    x.pop.compact();
    update::route_free_flow(&mut x.pop, &x.graphs, &x.supply, 2);
    x.pop.save_state(&into.join("init.bin"))?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn incident(x: &mut Setup, out: &std::path::Path, navs: &[f64], busiest: usize, t0: f32, t1: f32, speed: f32, seed: u64) -> Result<(), String> {
    driver::prepare_routes(x, out)?;
    let mut e = Engine::new(&x.net, &mut x.pop, &x.s, &[seed])?;
    let base = run_day(&mut e, &x.supply, &x.pop, &x.s, &mut NoPause);
    let n_bins = base.counts.n_bins;
    let mut flow: Vec<(u64, u32)> = (0..x.supply.n()).map(|d| ((0..n_bins).map(|b| base.counts.n_in[d * n_bins + b] as u64).sum(), d as u32)).collect();
    // Busiest while it lasts, not over the day.
    let (b0, b1) = ((t0 / BIN_S) as usize, (t1 / BIN_S) as usize);
    for f in &mut flow {
        f.0 = (b0..b1.min(n_bins)).map(|b| base.counts.n_in[f.1 as usize * n_bins + b] as u64).sum();
    }
    flow.par_sort_unstable_by_key(|f| std::cmp::Reverse(f.0));
    let edges: Vec<u32> = flow.iter().take(busiest).map(|f| f.1).collect();
    let names: Vec<String> = edges.iter().map(|&d| x.net.edges[x.supply.normal[d as usize] as usize].id.clone()).collect();
    eprintln!("incident edges: {names:?}");
    let inc = Incident { edges: edges.clone(), t0, t1, speed };
    let mut rows = Vec::new();
    for &nav in navs {
        for (label, incident) in [("normal", None), ("incident", Some(inc.clone()))] {
            e.load_day(&x.net, &mut x.pop, &[seed])?;
            let mut pause = Enroute::new(&x.net, &x.supply, &x.graphs, &x.pop, nav, incident, seed);
            let day = run_day(&mut e, &x.supply, &x.pop, &x.s, &mut pause);
            let navigators = x.pop.travellers.len() as f64 * nav;
            let row = serde_json::json!({
                "navigators": nav, "day": label, "stats": day.stats[0], "ledger": day.ledgers[0], "enroute": pause.stats,
                "reroutes_per_navigator": pause.stats.patched as f64 / navigators.max(1.0), "wall_s": day.wall_s, "stalled_at_s": day.stalled_at_s,
            });
            eprintln!("{row}");
            rows.push(row);
        }
    }
    let r = serde_json::json!({"edges": names, "t0": t0, "t1": t1, "speed_m_s": speed, "seed": seed, "rows": rows});
    std::fs::write(out.join("incident.json"), serde_json::to_string_pretty(&r).unwrap()).map_err(|e| e.to_string())?;
    println!("{}", serde_json::to_string_pretty(&r).unwrap());
    Ok(())
}
