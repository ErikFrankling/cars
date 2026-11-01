//! The loops: assignment, evaluation on unseen seeds, departures with their guard, calibration, verdicts.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::Instant;

use cars_core::demand::Demand;
use cars_core::net::Net;
use rustc_hash::FxHashMap;
use serde::Serialize;

use crate::calibrate::{self, CountError, Counts, Role};
use crate::costs::{BIN_S, CostTable, Supply};
use crate::cuts::{self, Cut, CutReport, Discharge};
use crate::day::{DayResult, Engine, NoPause, TripStats, run_day};
use crate::ledger::{self, Ledger, Verdict, VerdictInput};
use crate::population::{CLASS_FIXED, Population};
use crate::scenario::Scenario;
use crate::update::{self, Graphs, Rule, Schedule, StepStats};

pub struct Setup {
    pub s: Scenario,
    pub net: Net,
    pub supply: Supply,
    pub pop: Population,
    pub graphs: Graphs,
    pub counts: Option<Counts>,
    pub checks: serde_json::Value,
}

/// Reversals and reachability, before any simulation.
fn demand_checks(pop: &Population, graphs: &Graphs, supply: &Supply, unknown: u64, dropped: u64) -> serde_json::Value {
    let (mut km, mut rev) = (0f64, 0u64);
    for t in &pop.travellers {
        let r = &pop.demand.routes[t.route() as usize];
        km += r.iter().map(|&e| supply.length[supply.dense[e as usize] as usize] as f64).sum::<f64>() / 1000.0;
        let d: Vec<u32> = r.iter().map(|&e| supply.dense[e as usize]).collect();
        rev += u64::from(graphs.by_mask[&pop.demand.vtypes[t.vtype as usize].vclass].has_reversal(&d));
    }
    let n = pop.travellers.len().max(1) as f64;
    serde_json::json!({
        "trips": pop.travellers.len(),
        "unknown_edge_dropped": unknown,
        "unreachable_dropped": dropped,
        "planned_vkm": km,
        "mean_planned_km": km / n,
        "trips_with_reversal": rev,
        "reversal_share": rev as f64 / n,
    })
}

pub fn setup(path: &Path) -> Result<Setup, String> {
    let s = Scenario::load(path)?;
    let t = Instant::now();
    let mut net = Net::load(&s.net)?;
    for a in &s.additional {
        net.load_additional(a)?;
    }
    eprintln!("net in {:.1}s: {} edges, {} lanes, {} connections", t.elapsed().as_secs_f64(), net.edges.len(), net.lanes.len(), net.conns.len());
    let t = Instant::now();
    let mut unknown = 0;
    let mut pop = if let Some(file) = &s.travellers {
        let vt = Demand::load(&net, &[], &s.additional, s.seed, None)?;
        let (p, u) = Population::load_csv(file, &net, vt)?;
        unknown = u;
        p
    } else {
        let d = Demand::load(&net, &s.routes, &s.additional, s.seed, Some(s.end as f64))?;
        eprintln!("{}", d.summary());
        Population::from_demand_fixed(d, &s.fixed_prefixes, &s.fixed_vtypes)
    };
    pop.travellers.retain(|t| t.depart_s >= s.begin && t.depart_s <= s.end);
    if s.init != "given" {
        update::forget_routes(&mut pop);
    }
    pop.compact();
    eprintln!("population in {:.1}s: {} travellers", t.elapsed().as_secs_f64(), pop.travellers.len());
    let supply = Supply::new(&net, &pop.demand.vtypes, pop.travellers.iter().map(|t| t.vtype));
    let t = Instant::now();
    let conn = crate::route::connection_masks(&s.net, &net)?;
    let graphs = Graphs::with_options(&net, &supply, &pop, s.landmarks, s.turnaround_s, &conn);
    eprintln!("graphs in {:.1}s for {} classes, {} connections with their own permissions", t.elapsed().as_secs_f64(), graphs.by_mask.len(), conn.len());
    let counts = match &s.counts {
        Some(p) => {
            let mut c = Counts::load(p, &net, &supply)?;
            if s.blind_test {
                c.rows.retain(|r| !matches!(r.role, Role::Test | Role::TestOther));
            }
            Some(c)
        }
        None => None,
    };
    Ok(Setup { s, net, supply, pop, graphs, counts, checks: serde_json::Value::Null })
    .map(|mut x| {
        x.checks = serde_json::json!({"unknown": unknown});
        x
    })
}

/// Free-flow routes for everyone without one, or the checkpoint if there is one.
pub fn prepare_routes(x: &mut Setup, out: &Path) -> Result<(), String> {
    let state = out.join("state.bin");
    if state.exists() {
        x.pop.load_state(&state)?;
        return Ok(());
    }
    let init = out.join("init.bin");
    if init.exists() {
        x.pop.load_state(&init)?;
        return Ok(());
    }
    let t = Instant::now();
    let (routed, dropped) = update::route_free_flow(&mut x.pop, &x.graphs, &x.supply, 2);
    eprintln!("free-flow routes for {routed} travellers in {:.1}s, {dropped} unreachable dropped", t.elapsed().as_secs_f64());
    let unknown = x.checks["unknown"].as_u64().unwrap_or(0);
    x.checks = demand_checks(&x.pop, &x.graphs, &x.supply, unknown, dropped);
    eprintln!("checks: {}", x.checks);
    std::fs::write(out.join("checks.json"), serde_json::to_string_pretty(&x.checks).unwrap()).map_err(|e| e.to_string())?;
    x.pop.save_state(&init)?;
    Ok(())
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct IterRow {
    pub iter: u32,
    pub seed: u64,
    pub sim_wall_s: f64,
    pub route_wall_s: f64,
    pub total_wall_s: f64,
    pub vehicle_updates_m_s: f64,
    pub peak_active: u32,
    pub stalled_at_s: f64,
    pub end_s: f64,
    pub requested: u64,
    pub arrived: u64,
    pub unfinished: u64,
    pub unfinished_share: f64,
    pub teleports: u64,
    pub collisions: u64,
    pub imbalance: i64,
    pub mean_travel_s: f64,
    pub p50_travel_s: f64,
    pub p95_travel_s: f64,
    pub insertion_wait_s: f64,
    pub generalised_h: f64,
    pub route_km_mean: f64,
    pub gap_memory: f64,
    pub gap_unseen: f64,
    pub switched: u64,
    pub sampled: u64,
    pub settled_per_path: f64,
    pub train_wape: f64,
    pub train_geh5: f64,
    pub selection_wape: f64,
    pub held_peak_wape: f64,
    pub test_wape: f64,
    pub test_geh5: f64,
    pub test_other_wape: f64,
    pub count_ratio_train: f64,
    pub count_ratio_test: f64,
    pub arena_routes: u64,
}

impl IterRow {
    pub const HEADER: &'static str = "iter,seed,sim_wall_s,route_wall_s,total_wall_s,vehicle_updates_m_s,peak_active,stalled_at_s,end_s,requested,arrived,unfinished,unfinished_share,teleports,collisions,imbalance,mean_travel_s,p50_travel_s,p95_travel_s,insertion_wait_s,generalised_h,route_km_mean,gap_memory,gap_unseen,switched,sampled,settled_per_path,train_wape,train_geh5,selection_wape,held_peak_wape,test_wape,test_geh5,test_other_wape,count_ratio_train,count_ratio_test,arena_routes";

    fn csv(&self) -> String {
        format!(
            "{},{},{:.2},{:.2},{:.2},{:.2},{},{:.0},{:.0},{},{},{},{:.5},{},{},{},{:.2},{:.1},{:.1},{:.2},{:.1},{:.3},{:.5},{:.5},{},{},{:.0},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{}",
            self.iter, self.seed, self.sim_wall_s, self.route_wall_s, self.total_wall_s, self.vehicle_updates_m_s, self.peak_active, self.stalled_at_s, self.end_s, self.requested, self.arrived, self.unfinished, self.unfinished_share, self.teleports, self.collisions, self.imbalance, self.mean_travel_s, self.p50_travel_s, self.p95_travel_s, self.insertion_wait_s, self.generalised_h, self.route_km_mean, self.gap_memory, self.gap_unseen, self.switched, self.sampled, self.settled_per_path, self.train_wape, self.train_geh5, self.selection_wape, self.held_peak_wape, self.test_wape, self.test_geh5, self.test_other_wape, self.count_ratio_train, self.count_ratio_test, self.arena_routes
        )
    }
}

pub fn fill_day(row: &mut IterRow, day: &DayResult) {
    let st: &TripStats = &day.stats[0];
    let l: &Ledger = &day.ledgers[0];
    row.sim_wall_s = day.wall_s;
    row.vehicle_updates_m_s = day.vehicle_steps as f64 / day.wall_s.max(1e-3) / 1e6;
    row.peak_active = day.peak_active;
    row.stalled_at_s = day.stalled_at_s.unwrap_or(-1.0) as f64;
    row.end_s = day.end_s as f64;
    row.requested = l.requested;
    row.arrived = l.arrived;
    row.unfinished = l.unfinished();
    row.unfinished_share = l.unfinished_share();
    row.teleports = l.teleports;
    row.collisions = l.collisions;
    row.imbalance = l.imbalance;
    row.mean_travel_s = st.mean_travel_s;
    row.p50_travel_s = st.p50_travel_s;
    row.p95_travel_s = st.p95_travel_s;
    row.insertion_wait_s = st.mean_insertion_wait_s;
    row.generalised_h = st.total_generalised_s / 3600.0;
    row.route_km_mean = st.route_km / st.arrived.max(1) as f64;
}

pub fn fill_counts(row: &mut IterRow, counts: &Counts, day: &DayResult) -> FxHashMap<&'static str, CountError> {
    let mut m = FxHashMap::default();
    for r in [Role::Train, Role::Selection, Role::Test, Role::HeldPeak, Role::TestOther] {
        m.insert(r.name(), calibrate::count_error(&counts.rows, r, |c| calibrate::simulated(c, &day.counts)));
    }
    row.train_wape = m["train"].wape;
    row.train_geh5 = m["train"].geh5;
    row.selection_wape = m["selection"].wape;
    row.held_peak_wape = m["held_peak"].wape;
    row.test_wape = m["test"].wape;
    row.test_geh5 = m["test"].geh5;
    row.test_other_wape = m["test_other"].wape;
    row.count_ratio_train = m["train"].simulated / m["train"].observed.max(1e-9);
    row.count_ratio_test = m["test"].simulated / m["test"].observed.max(1e-9);
    m
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct Convergence {
    pub gap_ok: bool,
    pub stable: bool,
    pub ledger_clean: bool,
    pub converged: bool,
    pub stability_cost_change: f64,
    pub stability_flow_change: f64,
    pub gap_unseen: f64,
}

pub fn appender(path: &Path, header: &str) -> Result<std::fs::File, String> {
    let new = !path.exists();
    let mut f = std::fs::OpenOptions::new().create(true).append(true).open(path).map_err(|e| e.to_string())?;
    if new {
        writeln!(f, "{header}").map_err(|e| e.to_string())?;
    }
    Ok(f)
}

pub fn save_costs(c: &CostTable, path: &Path) -> Result<(), String> {
    let tmp = path.with_extension("tmp");
    {
        let mut w = std::io::BufWriter::with_capacity(1 << 20, std::fs::File::create(&tmp).map_err(|e| e.to_string())?);
        w.write_all(bytemuck::cast_slice(&c.c)).map_err(|e| e.to_string())?;
        w.write_all(bytemuck::cast_slice(&c.wait)).map_err(|e| e.to_string())?;
    }
    std::fs::rename(&tmp, path).map_err(|e| e.to_string())
}

pub fn load_costs(supply: &Supply, n_bins: usize, path: &Path) -> Result<CostTable, String> {
    use std::io::Read;
    let mut c = CostTable::free_flow(supply, n_bins);
    let mut r = std::io::BufReader::with_capacity(1 << 20, std::fs::File::open(path).map_err(|e| e.to_string())?);
    r.read_exact(bytemuck::cast_slice_mut(&mut c.c)).map_err(|e| e.to_string())?;
    r.read_exact(bytemuck::cast_slice_mut(&mut c.wait)).map_err(|e| e.to_string())?;
    Ok(c)
}

pub struct LoopOpts {
    pub iters: u32,
    /// Stop this process after so many iterations, leaving the GPU to others. It resumes from the checkpoint.
    pub chunk: u32,
    pub rule: Rule,
    pub memory: f32,
    pub target_gap: f64,
    /// Seeds per iteration. Replicas are for what is parallel, and one iteration's noise is.
    pub replicas: u32,
}

fn iterations_done(out: &Path) -> u32 {
    std::fs::read_to_string(out.join("iter.txt")).ok().and_then(|s| s.trim().parse().ok()).unwrap_or(0)
}

/// Gap under 2% on seeds the loop has not seen, under 1% change in cost and screenline flows across 5
/// iterations, and a clean ledger with teleports off. All three, or it is not converged.
pub fn convergence(rows: &[(f64, Vec<f64>)], gap_unseen: f64, ledger_clean: bool, target_gap: f64) -> Convergence {
    let n = rows.len();
    let mut c = Convergence { gap_unseen, ledger_clean, gap_ok: gap_unseen < target_gap, stability_cost_change: f64::INFINITY, stability_flow_change: f64::INFINITY, ..Default::default() };
    if n >= 6 {
        let last = &rows[n - 1];
        let (mut dc, mut df) = (0.0f64, 0.0f64);
        for r in &rows[n - 6..n - 1] {
            dc = dc.max((r.0 - last.0).abs() / last.0.abs().max(1e-9));
            for (a, b) in r.1.iter().zip(&last.1) {
                if *b >= 500.0 {
                    df = df.max((a - b).abs() / b);
                }
            }
        }
        c.stability_cost_change = dc;
        c.stability_flow_change = df;
        c.stable = dc < 0.01 && df < 0.01;
    }
    c.converged = c.gap_ok && c.stable && c.ledger_clean;
    c
}

/// Run a chunk of assignment iterations, resuming from `out`. True when converged or out of budget.
pub fn assignment(x: &mut Setup, out: &Path, o: &LoopOpts) -> Result<bool, String> {
    std::fs::create_dir_all(out).map_err(|e| e.to_string())?;
    prepare_routes(x, out)?;
    let manifest = out.join("manifest.json");
    if !manifest.exists() {
        std::fs::write(&manifest, serde_json::to_string_pretty(&x.s.manifest()).unwrap()).map_err(|e| e.to_string())?;
    }
    let n_bins = x.s.n_bins();
    let start = iterations_done(out);
    if start >= o.iters {
        return Ok(true);
    }
    let cost_file = out.join("costs.bin");
    let mut costs = if start > 0 && cost_file.exists() { load_costs(&x.supply, n_bins, &cost_file)? } else { CostTable::free_flow(&x.supply, n_bins) };
    let succ = cuts::successors(&x.net, &x.supply);
    let screen: Vec<Cut> = cuts::cluster_cuts(&x.supply, &succ).into_iter().filter(|c| c.name.starts_with("k2") || c.name.starts_with("k4")).collect();
    let mut history = load_history(out);
    let seeds_for = |k: u32, s: &Scenario| -> Vec<u64> { (0..o.replicas.max(1) as u64).map(|r| s.seed.wrapping_mul(1000).wrapping_add(k as u64 + r * 100_000)).collect() };
    let t = Instant::now();
    let mut engine = Engine::new(&x.net, &mut x.pop, &x.s, &seeds_for(start, &x.s))?;
    eprintln!("engine up in {:.1}s: {} MB of buffers", t.elapsed().as_secs_f64(), engine.sim.as_ref().unwrap().buffers.total_bytes / 1_000_000);
    let mut csv = appender(&out.join("iters.csv"), IterRow::HEADER)?;
    let mut hist_file = appender(&out.join("history.csv"), "generalised,screenlines")?;
    let mut finished = false;
    for k in start..(start + o.chunk.max(1)).min(o.iters) {
        let t_iter = Instant::now();
        let seeds = seeds_for(k, &x.s);
        let seed = seeds[0];
        engine.load_day(&x.net, &mut x.pop, &seeds)?;
        let day = run_day(&mut engine, &x.supply, &x.pop, &x.s, &mut NoPause);
        let t_route = Instant::now();
        let raw = CostTable::from_day(&x.supply, &day.counts);
        // Routes so far never saw this seed, so its raw table gives an out-of-sample gap for free.
        let share = (2000.0 / x.pop.travellers.len().max(1) as f64).clamp(0.02, 1.0);
        let oos: StepStats = update::gap_only(&x.pop, &x.graphs, &x.supply, &raw, share, seed ^ 0xABC);
        if k == 0 {
            costs = raw;
            costs.enforce_fifo();
        } else {
            costs.blend(&raw, o.memory);
        }
        let step = update::update_routes(&mut x.pop, &x.graphs, &x.supply, &costs, o.rule, seed);
        let mut row = IterRow { iter: k, seed, ..Default::default() };
        fill_day(&mut row, &day);
        row.gap_memory = step.gap;
        row.gap_unseen = oos.gap;
        row.switched = step.switched;
        row.sampled = step.sampled;
        row.settled_per_path = step.settled_per_path;
        if let Some(c) = &x.counts {
            fill_counts(&mut row, c, &day);
        }
        let flows = cuts::screenline_flows(&screen, &day.counts);
        history.push((row.generalised_h, flows.clone()));
        writeln!(hist_file, "{},{}", row.generalised_h, flows.iter().map(|f| format!("{f:.0}")).collect::<Vec<_>>().join(";")).map_err(|e| e.to_string())?;
        if k % 5 == 4 {
            x.pop.compact();
            engine.world.depart_masks.clear();
        }
        row.arena_routes = x.pop.demand.routes.len() as u64;
        row.route_wall_s = t_route.elapsed().as_secs_f64();
        row.total_wall_s = t_iter.elapsed().as_secs_f64();
        let conv = convergence(&history, oos.gap, day.ledgers[0].clean(), o.target_gap);
        eprintln!(
            "iter {k}: sim {:.0}s route {:.1}s, {} arrived of {}, unfinished {:.3}%, teleports {} collisions {}, travel {:.0}s p95 {:.0}s, gap {:.2}% unseen {:.2}%, switched {} of {}, stall {:.0}, train {:.3} sel {:.3} test {:.3}",
            row.sim_wall_s, row.route_wall_s, row.arrived, row.requested, row.unfinished_share * 100.0, row.teleports, row.collisions, row.mean_travel_s, row.p95_travel_s, row.gap_memory * 100.0, row.gap_unseen * 100.0, row.switched, row.sampled, row.stalled_at_s, row.train_wape, row.selection_wape, row.test_wape
        );
        writeln!(csv, "{}", row.csv()).map_err(|e| e.to_string())?;
        x.pop.save_state(&out.join("state.bin"))?;
        save_costs(&costs, &cost_file)?;
        std::fs::write(out.join("iter.txt"), format!("{}", k + 1)).map_err(|e| e.to_string())?;
        std::fs::write(out.join("convergence.json"), serde_json::to_string_pretty(&conv).unwrap()).map_err(|e| e.to_string())?;
        if conv.converged {
            finished = true;
            std::fs::write(out.join("iter.txt"), format!("{}", o.iters)).map_err(|e| e.to_string())?;
            break;
        }
    }
    Ok(finished || iterations_done(out) >= o.iters)
}

fn load_history(out: &Path) -> Vec<(f64, Vec<f64>)> {
    let Ok(text) = std::fs::read_to_string(out.join("history.csv")) else { return Vec::new() };
    text.lines()
        .skip(1)
        .filter_map(|l| {
            let (a, b) = l.split_once(',')?;
            Some((a.parse().ok()?, b.split(';').filter_map(|v| v.parse().ok()).collect()))
        })
        .collect()
}

#[derive(Clone, Debug, Serialize)]
pub struct EvalSeed {
    pub seed: u64,
    pub ledger: Ledger,
    pub balanced: bool,
    pub clean: bool,
    pub stats: TripStats,
    pub peak_active: u32,
    pub stalled_at_s: Option<f32>,
    pub wall_s: f64,
    pub errors: FxHashMap<&'static str, CountError>,
}

/// Frozen routes on seeds the loop never used. This is the number to quote. With `open_test` the blind test
/// rows are read, once per run.
pub fn evaluate(x: &mut Setup, out: &Path, seeds: &[u64], tag: &str, per_world: usize, open_test: bool) -> Result<serde_json::Value, String> {
    prepare_routes(x, out)?;
    if open_test {
        let marker = out.join("test_opened.json");
        if marker.exists() {
            return Err(format!("{} exists: the test rows were opened already", marker.display()));
        }
        let p = x.s.counts.clone().ok_or("no counts to open")?;
        x.counts = Some(Counts::load(&p, &x.net, &x.supply)?);
        std::fs::write(&marker, serde_json::json!({"tag": tag, "seeds": seeds}).to_string()).map_err(|e| e.to_string())?;
    }
    let mut results = Vec::new();
    let mut engine: Option<Engine> = None;
    let mut combined: Option<crate::costs::DayCounts> = None;
    for group in seeds.chunks(per_world.max(1)) {
        match engine.as_mut() {
            Some(e) if e.seeds.len() == group.len() => e.load_day(&x.net, &mut x.pop, group)?,
            _ => {
                engine = None;
                engine = Some(Engine::new(&x.net, &mut x.pop, &x.s, group)?);
            }
        }
        let e = engine.as_mut().unwrap();
        let day = run_day(e, &x.supply, &x.pop, &x.s, &mut NoPause);
        for (i, &seed) in group.iter().enumerate() {
            let mut errors = FxHashMap::default();
            if let Some(c) = &x.counts {
                let mut row = IterRow::default();
                errors = fill_counts(&mut row, c, &day);
            }
            results.push(EvalSeed {
                seed,
                ledger: day.ledgers[i].clone(),
                balanced: day.ledgers[i].balanced(),
                clean: day.ledgers[i].clean(),
                stats: day.stats[i].clone(),
                peak_active: day.peak_active,
                stalled_at_s: day.stalled_at_s,
                wall_s: day.wall_s,
                errors,
            });
        }
        match combined.as_mut() {
            Some(c) => c.add(&day.counts),
            None => combined = Some(day.counts),
        }
    }
    drop(engine);
    // Averaged over the seeds, as noise in a single table makes the best route look better than it is.
    let combined = combined.ok_or("no seeds")?;
    let raw = CostTable::from_day(&x.supply, &combined);
    let share = 0.15_f64.max(2000.0 / x.pop.travellers.len().max(1) as f64).min(1.0);
    let gap = update::gap_only(&x.pop, &x.graphs, &x.supply, &raw, share, seeds[0] ^ 0xE1);
    write_edge_flows(&out.join(format!("edge_flows_{tag}.csv")), x, &combined)?;
    let n = results.len().max(1) as f64;
    let mean = |f: &dyn Fn(&EvalSeed) -> f64| results.iter().map(f).sum::<f64>() / n;
    let mean_travel = mean(&|r| r.stats.mean_travel_s);
    let sd_travel = (results.iter().map(|r| (r.stats.mean_travel_s - mean_travel).powi(2)).sum::<f64>() / n).sqrt();
    let result = serde_json::json!({
        "seeds": results,
        "gap": gap.gap,
        "gap_sampled": gap.sampled,
        "seeds_averaged": seeds.len(),
        "mean_travel_s": mean_travel,
        "sd_travel_s": sd_travel,
        "p95_travel_s": mean(&|r| r.stats.p95_travel_s),
        "unfinished_share": mean(&|r| r.ledger.unfinished_share()),
        "teleports": mean(&|r| r.ledger.teleports as f64),
        "collisions": mean(&|r| r.ledger.collisions as f64),
        "all_balanced": results.iter().all(|r| r.balanced),
        "all_clean": results.iter().all(|r| r.clean),
    });
    std::fs::write(out.join(format!("eval_{tag}.json")), serde_json::to_string_pretty(&result).unwrap()).map_err(|e| e.to_string())?;
    Ok(result)
}

pub fn write_edge_flows(path: &PathBuf, x: &Setup, day: &crate::costs::DayCounts) -> Result<(), String> {
    let mut s = String::from("edge,flow\n");
    let k = day.replicas.max(1) as f64;
    for e in 0..x.supply.n() {
        let f: f64 = (0..day.n_bins).map(|b| day.n_in[e * day.n_bins + b] as f64).sum::<f64>() / k;
        s.push_str(&format!("{},{f:.1}\n", x.net.edges[x.supply.normal[e] as usize].id));
    }
    std::fs::write(path, s).map_err(|e| e.to_string())
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct DepartRow {
    pub iter: u32,
    pub share: f64,
    pub tried: u64,
    pub moved: u64,
    pub at_window_edge: u64,
    pub mean_travel_s: f64,
    pub unfinished: u64,
    pub schedule_cost_mean: f64,
    pub rejected: bool,
}

/// Departure-time adaptation after route convergence. A batch that worsens the ledger or the total
/// generalised cost is undone, the share halved and tried again. Two rejections stop it.
pub fn departures(x: &mut Setup, out: &Path, iters: u32, schedule: Schedule, memory: f32, consistent: bool) -> Result<serde_json::Value, String> {
    prepare_routes(x, out)?;
    let n_bins = x.s.n_bins();
    let mut costs = load_costs(&x.supply, n_bins, &out.join("costs.bin")).unwrap_or_else(|_| CostTable::free_flow(&x.supply, n_bins));
    if consistent {
        update::consistent_start(&mut x.pop, &x.supply, &costs);
    }
    update::default_schedule(&mut x.pop, &x.supply);
    let seed0 = x.s.seed.wrapping_mul(7000);
    let mut engine = Engine::new(&x.net, &mut x.pop, &x.s, &[seed0])?;
    let mut share = 0.05f64;
    let mut rejections = 0;
    let mut rows = Vec::new();
    let (mut prev_unfinished, mut prev_general): (Option<u64>, Option<f64>) = (None, None);
    let mut snapshot = x.pop.travellers.clone();
    let mut unstable = false;
    let score = |day: &DayResult, pop: &Population| -> f64 {
        pop.travellers.iter().zip(&day.experienced).filter(|(_, e)| e.is_finite()).map(|(t, &e)| schedule.cost(e, t.depart_s + e, t.desired_arrival_s) as f64).sum()
    };
    for k in 0..iters {
        let seed = seed0 + k as u64;
        engine.load_day(&x.net, &mut x.pop, &[seed])?;
        let day = run_day(&mut engine, &x.supply, &x.pop, &x.s, &mut NoPause);
        let general = score(&day, &x.pop);
        let unfinished = day.ledgers[0].unfinished();
        let requested = day.ledgers[0].requested as f64;
        let rejected = prev_unfinished.is_some_and(|u| unfinished as f64 > u as f64 + 0.001 * requested) || prev_general.is_some_and(|g| general > 1.02 * g);
        let mut row = DepartRow { iter: k, share, mean_travel_s: day.stats[0].mean_travel_s, unfinished, schedule_cost_mean: general / requested.max(1.0), rejected, ..Default::default() };
        if rejected {
            rejections += 1;
            x.pop.travellers = snapshot.clone();
            share /= 2.0;
            rows.push(row.clone());
            if rejections >= 2 {
                unstable = true;
                break;
            }
        } else {
            rejections = 0;
            prev_unfinished = Some(unfinished);
            prev_general = Some(general);
            snapshot = x.pop.travellers.clone();
        }
        let raw = CostTable::from_day(&x.supply, &day.counts);
        costs.blend(&raw, memory);
        if !rejected {
            let st = update::update_departures(&mut x.pop, &x.supply, &costs, schedule, share, seed);
            row.tried = st.tried;
            row.moved = st.moved;
            row.at_window_edge = st.at_window_edge;
            rows.push(row);
        }
        eprintln!("departure iter {k}: {:?}", rows.last());
    }
    let result = serde_json::json!({
        "schedule": schedule,
        "status": if unstable { "departure adaptation unstable at this load" } else { "completed" },
        "rows": rows,
    });
    x.pop.travellers = snapshot;
    x.pop.save_state(&out.join("state_depart.bin"))?;
    Ok(result)
}

/// A saturating stream on each edge, onto its first successor, with nothing else on the network.
pub fn measure_discharge(x: &Setup, edges: &[u32]) -> Result<Vec<(u32, f32)>, String> {
    let succ = cuts::successors(&x.net, &x.supply);
    let mut demand = Demand::load(&x.net, &[], &x.s.additional, 1, None)?;
    let vt = demand.vtype_index.get("passenger").or(demand.vtype_index.get("DEFAULT_VEHTYPE")).copied().unwrap_or(0);
    let (period, warm, window) = (1.2f32, 300.0f32, 900.0f32);
    let mut tv = Vec::new();
    let tested: Vec<u32> = edges.iter().copied().filter(|&e| !succ[e as usize].is_empty()).collect();
    for &e in &tested {
        let route = vec![x.supply.normal[e as usize], x.supply.normal[succ[e as usize][0] as usize]];
        let r = demand.routes.len() as u32;
        demand.routes.push(route.clone());
        let lanes = x.supply.lanes[e as usize] as f32;
        for i in 0..((warm + window) / period * lanes) as u32 {
            let depart = i as f32 * period / lanes;
            let id = tv.len() as u32;
            let mut t = crate::population::Traveller { id, o_edge: route[0], d_edge: route[1], depart_s: depart, desired_arrival_s: depart, earliest_s: depart, latest_s: depart, tour: id, vtype: vt, ..Default::default() };
            t.plan[0] = r;
            t.n_plan = 1;
            tv.push(t);
        }
    }
    eprintln!("discharge test: {} links, {} trips", tested.len(), tv.len());
    let mut pop = Population::new(demand, vec![Default::default()], tv);
    let mut s = x.s.clone();
    s.begin = 0.0;
    s.end = warm + window;
    s.horizon = warm + window;
    s.capacity = 40000.max(tested.len() as u32 * 200);
    let mut e = Engine::new(&x.net, &mut pop, &s, &[11])?;
    let day = run_day(&mut e, &x.supply, &pop, &s, &mut NoPause);
    let (b0, b1) = ((warm / BIN_S) as usize, ((warm + window) / BIN_S) as usize);
    Ok(tested.iter().map(|&d| (d, (b0..b1).map(|b| day.counts.left[d as usize * day.counts.n_bins + b] as f32).sum::<f32>() / window)).collect())
}

const HALF_DEMAND_ITERATIONS: u32 = 5;

#[derive(Clone, Debug, Serialize)]
pub struct VerdictReport {
    pub verdict: Verdict,
    pub requested: u64,
    pub unfinished: u64,
    pub teleports: u64,
    pub collisions: u64,
    pub stalled_at_s: Option<f32>,
    pub due_at_stall: f64,
    pub half_demand_day: Option<serde_json::Value>,
    pub converged: Convergence,
    pub first_queues: Vec<serde_json::Value>,
    pub suspect_links: Vec<serde_json::Value>,
    pub cuts_checked: usize,
    pub cuts_violated: Vec<CutReport>,
    pub worst_cuts: Vec<CutReport>,
    pub min_unmet_demand: f64,
    pub delay_ratio: f64,
    pub notes: Vec<String>,
}

/// The ladder, from a day on the current routes, the convergence record and the cut family.
pub fn verdict(x: &mut Setup, out: &Path, seed: u64) -> Result<VerdictReport, String> {
    prepare_routes(x, out)?;
    let mut engine = Engine::new(&x.net, &mut x.pop, &x.s, &[seed])?;
    let day = run_day(&mut engine, &x.supply, &x.pop, &x.s, &mut NoPause);
    drop(engine);
    // Gridlock at half the demand is what makes a network suspect. Routes assigned for the whole demand
    // would not be fair to half of it, so it gets a few iterations of its own first.
    let mut half_load: Option<serde_json::Value> = None;
    if day.stalled_at_s.is_some() || !day.ledgers[0].clean() {
        let all = x.pop.travellers.clone();
        x.pop.travellers.retain(|t| crate::unit(seed ^ 0xBEEF, t.id as u64) < 0.5);
        let mut e = Engine::new(&x.net, &mut x.pop, &x.s, &[seed])?;
        let mut half_costs = load_costs(&x.supply, x.s.n_bins(), &out.join("costs.bin")).unwrap_or_else(|_| CostTable::free_flow(&x.supply, x.s.n_bins()));
        for j in 0..HALF_DEMAND_ITERATIONS {
            let s = seed + 1 + j as u64;
            e.load_day(&x.net, &mut x.pop, &[s])?;
            let d = run_day(&mut e, &x.supply, &x.pop, &x.s, &mut NoPause);
            half_costs.blend(&CostTable::from_day(&x.supply, &d.counts), x.s.memory);
            update::update_routes(&mut x.pop, &x.graphs, &x.supply, &half_costs, Rule::Capped { share: x.s.share }, s);
        }
        e.load_day(&x.net, &mut x.pop, &[seed])?;
        let half = run_day(&mut e, &x.supply, &x.pop, &x.s, &mut NoPause);
        drop(e);
        half_load = Some(serde_json::json!({"stalled_at_s": half.stalled_at_s, "unfinished_share": half.ledgers[0].unfinished_share(), "teleports": half.ledgers[0].teleports, "mean_travel_s": half.stats[0].mean_travel_s}));
        x.pop.travellers = all;
        x.pop.fill_trips();
    }
    let half_gridlocks = half_load.as_ref().is_some_and(|h| h["stalled_at_s"].is_number() || h["unfinished_share"].as_f64().unwrap_or(0.0) >= 0.001);
    let succ = cuts::successors(&x.net, &x.supply);
    let mut family = cuts::cluster_cuts(&x.supply, &succ);
    if let Some(p) = &x.s.cuts {
        family.extend(cuts::load_named_cuts(p, &x.net, &x.supply, &succ)?);
    }
    let sets = cuts::queued_sets(&x.supply, &day.counts, &succ, 3);
    for (i, set) in sets.iter().enumerate() {
        let mut side = vec![false; x.supply.n()];
        for &e in set {
            side[e as usize] = true;
        }
        family.push(Cut::from_set(format!("queue_{i}"), side, &succ));
    }
    let mut discharge = Discharge { observed: Discharge::from_day(&day.counts), ..Default::default() };
    if let Some(p) = &x.s.discharge {
        discharge.measured = Discharge::load(p, &x.net, &x.supply)?;
    }
    let mut reports: Vec<CutReport> = family.iter().flat_map(|c| cuts::check_cut(c, &x.pop, &x.supply, &discharge, x.s.begin, x.s.horizon)).collect();
    reports.sort_by(|a, b| b.shortfall_1h.total_cmp(&a.shortfall_1h).then((b.peak_1h_crossing as f64 / b.capacity_veh_h.max(1.0)).total_cmp(&(a.peak_1h_crossing as f64 / a.capacity_veh_h.max(1.0)))));
    let violated: Vec<CutReport> = reports.iter().filter(|r| r.violated).cloned().collect();
    let min_unmet = reports.iter().map(|r| r.min_unmet).fold(0.0, f64::max);
    // First persistent queues, and whether what they discharge is under half the nominal screen.
    let n_bins = day.counts.n_bins;
    let k = day.counts.replicas.max(1) as f32;
    let mut first: Vec<(usize, u32)> = Vec::new();
    for set in &sets {
        for &e in set {
            let mut run = 0;
            let (mut a, mut b) = (0.0f32, 0.0f32);
            for bin in 0..day.counts.end_bin {
                a += day.counts.n_in[e as usize * n_bins + bin] as f32 / k;
                b += day.counts.left[e as usize * n_bins + bin] as f32 / k;
                let storage = x.supply.length[e as usize] * x.supply.lanes[e as usize] as f32 / cuts::QUEUE_SPACING;
                run = if a - b > 0.5 * storage.max(2.0) { run + 1 } else { 0 };
                if run >= 3 {
                    first.push((bin, e));
                    break;
                }
            }
        }
    }
    first.sort_unstable();
    let name = |e: u32| x.net.edges[x.supply.normal[e as usize] as usize].id.clone();
    let first_queues: Vec<_> = first.iter().take(30).map(|&(b, e)| serde_json::json!({"edge": name(e), "from_s": b as f32 * BIN_S, "discharge_veh_h": discharge.observed[e as usize] * 3600.0, "nominal_veh_h": x.supply.nominal_capacity(e as usize) * 3600.0})).collect();
    // The first queues, tested in isolation. A signal takes its share of green, so its screen is half as high.
    let first_edges: Vec<u32> = first.iter().take(30).map(|f| f.1).filter(|e| !discharge.measured.contains_key(e)).collect();
    if !first_edges.is_empty() {
        discharge.measured.extend(measure_discharge(x, &first_edges)?);
    }
    let signalled: rustc_hash::FxHashSet<u32> = x.net.conns.iter().filter(|c| c.tl.is_some()).map(|c| x.supply.dense[c.from_edge as usize]).collect();
    let suspect: Vec<_> = first
        .iter()
        .take(30)
        .filter(|&&(_, e)| {
            let limit = if signalled.contains(&e) { 0.25 } else { 0.5 };
            discharge.measured.get(&e).is_some_and(|&r| r < limit * x.supply.nominal_capacity(e as usize))
        })
        .map(|&(b, e)| serde_json::json!({"edge": name(e), "from_s": b as f32 * BIN_S, "isolated_discharge_veh_h": discharge.measured[&e] * 3600.0, "nominal_veh_h": x.supply.nominal_capacity(e as usize) * 3600.0}))
        .collect();
    let conv: Convergence = std::fs::read_to_string(out.join("convergence.json")).ok().and_then(|t| serde_json::from_str::<serde_json::Value>(&t).ok()).map(|v| Convergence { converged: v["converged"].as_bool().unwrap_or(false), gap_ok: v["gap_ok"].as_bool().unwrap_or(false), stable: v["stable"].as_bool().unwrap_or(false), ledger_clean: v["ledger_clean"].as_bool().unwrap_or(false), gap_unseen: v["gap_unseen"].as_f64().unwrap_or(f64::NAN), stability_cost_change: v["stability_cost_change"].as_f64().unwrap_or(f64::NAN), stability_flow_change: v["stability_flow_change"].as_f64().unwrap_or(f64::NAN) }).unwrap_or_default();
    let ff_mean: f64 = x.pop.travellers.iter().map(|t| x.pop.demand.routes[t.route() as usize].iter().map(|&e| x.supply.ff[x.supply.dense[e as usize] as usize] as f64).sum::<f64>()).sum::<f64>() / x.pop.travellers.len().max(1) as f64;
    let delay_ratio = day.stats[0].mean_travel_s / ff_mean.max(1.0);
    let v = ledger::verdict(&VerdictInput {
        gridlock_at_half_demand: half_gridlocks,
        suspect_links: suspect.len(),
        cuts_violated: violated.len(),
        converged: conv.converged,
        ledger_clean: day.ledgers[0].clean(),
        // Selection rows only: a converged city that stays this far from the counts disagrees with them.
        observations_conflict: match (&x.counts, x.s.noise_floor) {
            (Some(c), Some(floor)) => calibrate::count_error(&c.rows, Role::Selection, |r| calibrate::simulated(r, &day.counts)).wape > 2.0 * floor,
            _ => false,
        },
        delay_ratio,
    });
    let mut notes = vec![
        "Cut capacity is measured discharge from an isolated test where a discharge file was given; otherwise the larger of the day's peak outflow and half a nominal screen.".to_string(),
    ];
    if !x.s.counted() {
        notes.push("Labelled diagnostic: teleports or ignore-junction-blocker were on, so this is not a counted run.".into());
    }
    let report = VerdictReport {
        verdict: v,
        requested: day.ledgers[0].requested,
        unfinished: day.ledgers[0].unfinished(),
        teleports: day.ledgers[0].teleports,
        collisions: day.ledgers[0].collisions,
        stalled_at_s: day.stalled_at_s,
        due_at_stall: day.due_at_stall,
        half_demand_day: half_load,
        converged: conv,
        first_queues,
        suspect_links: suspect,
        cuts_checked: reports.len(),
        cuts_violated: violated,
        worst_cuts: reports.iter().take(10).cloned().collect(),
        min_unmet_demand: min_unmet,
        delay_ratio,
        notes,
    };
    std::fs::write(out.join("verdict.json"), serde_json::to_string_pretty(&report).unwrap()).map_err(|e| e.to_string())?;
    Ok(report)
}

/// Whether a class of traveller is rerouted at all, for reporting.
pub fn rerouted(pop: &Population) -> u64 {
    pop.travellers.iter().filter(|t| t.class & CLASS_FIXED == 0).count() as u64
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct CalibrationRound {
    pub round: u32,
    pub lambda: f64,
    pub alpha: f64,
    pub trips_before: u64,
    pub trips_after: u64,
    pub added: u64,
    pub removed: u64,
    pub predicted_selection_wape: f64,
    pub train_wape: f64,
    pub selection_wape: f64,
    pub held_peak_wape: f64,
    pub test_wape: f64,
    pub test_geh5: f64,
    pub test_other_wape: f64,
    pub unfinished_share: f64,
    pub guards: calibrate::Guards,
    pub lower_standard: bool,
    pub stopped_at_floor: bool,
}

pub struct CalibrateOpts {
    pub rounds: u32,
    pub warm: u32,
    pub noise_floor: f64,
    pub enforce_tag: bool,
    pub zones: usize,
    pub seed: u64,
}

/// One assignment iteration in a world that already exists.
#[allow(clippy::too_many_arguments)]
fn warm_iteration(x: &mut Setup, engine: &mut Engine, costs: &mut CostTable, memory: f32, k: u32, seed: u64, csv: &mut std::fs::File) -> Result<DayResult, String> {
    let t0 = Instant::now();
    engine.load_day(&x.net, &mut x.pop, &[seed])?;
    let day = run_day(engine, &x.supply, &x.pop, &x.s, &mut NoPause);
    let t = Instant::now();
    let raw = CostTable::from_day(&x.supply, &day.counts);
    let oos = update::gap_only(&x.pop, &x.graphs, &x.supply, &raw, (2000.0 / x.pop.travellers.len().max(1) as f64).clamp(0.02, 1.0), seed ^ 0xABC);
    costs.blend(&raw, memory);
    let step = update::update_routes(&mut x.pop, &x.graphs, &x.supply, costs, Rule::Capped { share: x.s.share }, seed);
    let mut row = IterRow { iter: k, seed, ..Default::default() };
    fill_day(&mut row, &day);
    row.gap_memory = step.gap;
    row.gap_unseen = oos.gap;
    row.switched = step.switched;
    row.sampled = step.sampled;
    row.settled_per_path = step.settled_per_path;
    if let Some(c) = &x.counts {
        fill_counts(&mut row, c, &day);
    }
    row.arena_routes = x.pop.demand.routes.len() as u64;
    row.route_wall_s = t.elapsed().as_secs_f64();
    row.total_wall_s = t0.elapsed().as_secs_f64();
    eprintln!("warm iter {k}: sim {:.0}s, unfinished {:.3}%, travel {:.0}s, gap unseen {:.2}%, train {:.3} sel {:.3} test {:.3}", row.sim_wall_s, row.unfinished_share * 100.0, row.mean_travel_s, row.gap_unseen * 100.0, row.train_wape, row.selection_wape, row.test_wape);
    writeln!(csv, "{}", row.csv()).map_err(|e| e.to_string())?;
    Ok(day)
}

/// Fit cells to the training counts only, respecting the limits on change, then re-assign warm. Test rows are
/// reported and read by nothing else.
pub fn calibration(x: &mut Setup, out: &Path, o: &CalibrateOpts) -> Result<Vec<CalibrationRound>, String> {
    prepare_routes(x, out)?;
    let counts = x.counts.clone().ok_or("calibration needs counts")?;
    let n_bins = x.s.n_bins();
    let mut costs = load_costs(&x.supply, n_bins, &out.join("costs.bin"))?;
    let zone = calibrate::zones(&x.supply, o.zones);
    let mut csv = appender(&out.join("iters.csv"), IterRow::HEADER)?;
    let mut k = iterations_done(out);
    let mut prior: FxHashMap<u64, f64> = FxHashMap::default();
    for t in &x.pop.travellers {
        *prior.entry(calibrate::cell_key(&zone, &x.supply, t.o_edge, t.d_edge, t.depart_s)).or_insert(0.0) += 1.0;
    }
    let cell_means = |pop: &Population, a: &calibrate::Assignment, supply: &Supply| -> Vec<f64> {
        let mut sum = vec![0.0f64; a.cells.len()];
        for (i, t) in pop.travellers.iter().enumerate() {
            sum[a.of_traveller[i] as usize] += pop.demand.routes[t.route() as usize].iter().map(|&e| supply.length[supply.dense[e as usize] as usize] as f64).sum::<f64>();
        }
        sum.iter().zip(&a.q).map(|(s, q)| s / q.max(1.0)).collect()
    };
    let mut rounds = Vec::new();
    let mut best: Option<(f64, Vec<crate::population::Traveller>)> = None;
    for r in 0..o.rounds {
        let a = calibrate::build_assignment(&x.pop, &x.supply, &costs, &zone, &counts.rows);
        let q0: Vec<f64> = a.cells.iter().map(|c| prior.get(c).copied().unwrap_or(0.0)).collect();
        // Lambda by what the selection rows say under this fixed assignment.
        let (mut lambda, mut fit, mut sel) = (0.5, Vec::new(), f64::INFINITY);
        for l in [0.1, 0.5, 2.0, 8.0] {
            let f = calibrate::cell_fit(&a, &counts.rows, &q0, l, 200);
            let p = calibrate::predict(&a, &f, counts.rows.len());
            let e = calibrate::count_error(&counts.rows, Role::Selection, |c| {
                let i = (c as *const _ as usize - counts.rows.as_ptr() as usize) / std::mem::size_of::<calibrate::CountRow>();
                p[i] as f32
            });
            if e.wape < sel {
                (lambda, fit, sel) = (l, f, e.wape);
            }
        }
        let mean_len = cell_means(&x.pop, &a, &x.supply);
        // WebTAG: when limits and flow criteria conflict, respect the limits and report the lower standard.
        let mut alpha = 1.0f64;
        let mut target: Vec<f64> = fit.clone();
        if o.enforce_tag {
            for try_alpha in [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03, 0.015, 0.0] {
                alpha = try_alpha;
                target = q0.iter().zip(&fit).map(|(a, b)| a + try_alpha * (b - a)).collect();
                let mid: Vec<f64> = a.q.iter().zip(&target).map(|(x, y)| 0.5 * x + 0.5 * y).collect();
                if calibrate::guards(&a.cells, &q0, &mid, &mean_len).pass {
                    break;
                }
            }
        }
        let q_new: Vec<f64> = a.q.iter().zip(&target).map(|(x, y)| 0.5 * x + 0.5 * y).collect();
        let g = calibrate::guards(&a.cells, &q0, &q_new, &mean_len);
        let before = x.pop.travellers.len() as u64;
        let (added, removed) = calibrate::apply_cells(&mut x.pop, &a, &q_new, o.seed ^ (r as u64 * 1009));
        let mut engine = Engine::new(&x.net, &mut x.pop, &x.s, &[o.seed + 5000 + r as u64])?;
        let mut last = None;
        for j in 0..o.warm {
            let seed = o.seed.wrapping_mul(1000).wrapping_add(7000 + (r * 100 + j) as u64);
            last = Some(warm_iteration(x, &mut engine, &mut costs, x.s.memory, k, seed, &mut csv)?);
            k += 1;
        }
        drop(engine);
        let day = last.ok_or("no warm iterations")?;
        let mut row = IterRow::default();
        fill_counts(&mut row, &counts, &day);
        let stopped = row.selection_wape <= o.noise_floor;
        let round = CalibrationRound {
            round: r,
            lambda,
            alpha,
            trips_before: before,
            trips_after: x.pop.travellers.len() as u64,
            added,
            removed,
            predicted_selection_wape: sel,
            train_wape: row.train_wape,
            selection_wape: row.selection_wape,
            held_peak_wape: row.held_peak_wape,
            test_wape: row.test_wape,
            test_geh5: row.test_geh5,
            test_other_wape: row.test_other_wape,
            unfinished_share: day.ledgers[0].unfinished_share(),
            lower_standard: !g.pass || alpha < 1.0,
            guards: g,
            stopped_at_floor: stopped,
        };
        eprintln!("round {r}: {}", serde_json::to_string(&round).unwrap());
        rounds.push(round);
        std::fs::write(out.join("calibration.json"), serde_json::to_string_pretty(&serde_json::json!({"noise_floor": o.noise_floor, "tag_enforced": o.enforce_tag, "rounds": rounds})).unwrap()).map_err(|e| e.to_string())?;
        if best.as_ref().is_none_or(|b| row.selection_wape < b.0) {
            best = Some((row.selection_wape, x.pop.travellers.clone()));
        }
        x.pop.save_state(&out.join("state_calibrated.bin"))?;
        save_costs(&costs, &out.join("costs.bin"))?;
        if stopped {
            break;
        }
    }
    if let Some((_, tv)) = best {
        x.pop.travellers = tv;
    }
    x.pop.save_state(&out.join("state_calibrated.bin"))?;
    let a = calibrate::build_assignment(&x.pop, &x.supply, &costs, &zone, &[]);
    let mut s = String::from("cell,o_zone,d_zone,slice,q0,q\n");
    for (i, c) in a.cells.iter().enumerate() {
        s.push_str(&format!("{},{},{},{},{},{}\n", c, c >> 32, (c >> 16) & 0xffff, c & 0xffff, prior.get(c).copied().unwrap_or(0.0), a.q[i]));
    }
    std::fs::write(out.join("cells.csv"), s).map_err(|e| e.to_string())?;
    std::fs::write(out.join("iter.txt"), format!("{k}")).map_err(|e| e.to_string())?;
    Ok(rounds)
}
