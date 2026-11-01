//! `cars av`: run signal-free or signal-baseline junctions and report the numbers ci_model.py reports.
use cars_core::{
    Gpu, GpuOptions,
    coord::{self, CoordConfig, ExitFault, Select, stat},
    demand::Demand,
    net::Net,
    sim::Sim,
    world::{SimConfig, World},
};
use clap::Parser;
use std::collections::HashSet;
use std::path::PathBuf;
use std::time::Instant;

#[derive(clap::Args, Clone, Debug, Default)]
pub struct CoordArgs {
    /// Junctions the coordinator runs: `all`, `box:x0,y0,x1,y1`, or ids separated by commas.
    #[arg(long)]
    pub cj: Option<String>,
    /// free, signal or mixed. Signal is the baseline with the same cars and conflict table.
    #[arg(long, default_value = "free")]
    pub cj_mode: String,
    /// Exceptions per junction, id=free or id=signal, separated by commas.
    #[arg(long, value_delimiter = ',')]
    pub cj_junction_mode: Vec<String>,
    /// The stall-tolerant stricter margin instead of the specified rule.
    #[arg(long)]
    pub cj_level_b: bool,
    /// Human parameters for the signal baseline: tau 1.4, s0 2.5, 1 s reaction, 4 s lost per switch.
    #[arg(long)]
    pub cj_human: bool,
    #[arg(long, default_value_t = 0.0)]
    pub cj_loss: f32,
    /// Radio silent between these two times: t0,t1.
    #[arg(long, value_delimiter = ',')]
    pub cj_blackout: Vec<f32>,
    /// Coordinator down between these two times: t0,t1.
    #[arg(long, value_delimiter = ',')]
    pub cj_crash: Vec<f32>,
    #[arg(long)]
    pub cj_no_fallback: bool,
    #[arg(long)]
    pub cj_no_exit_check: bool,
    #[arg(long)]
    pub cj_no_perception: bool,
    #[arg(long)]
    pub cj_no_audit: bool,
    /// Stalls per hour, injected into a random car in the box.
    #[arg(long, default_value_t = 0.0)]
    pub cj_stall_rate: f32,
    #[arg(long, default_value_t = 15.0)]
    pub cj_stall_t: f32,
    /// Channel model: 0 fixed loss only, 1 the statistical channel of report 08.
    #[arg(long, default_value_t = 0)]
    pub cj_chan: u32,
    /// Close the far end of lanes: prefix:t0:t1 or prefix:t0:t1:vehph. Repeatable.
    #[arg(long)]
    pub cj_exit_fault: Vec<String>,
    #[arg(long, default_value_t = 60.0)]
    pub cj_sig_max: f32,
    #[arg(long, default_value_t = 1.0)]
    pub cj_sig_gap: f32,
    /// Hold new cars outside the network while this many are on it. 0 for no metering.
    #[arg(long, default_value_t = 0)]
    pub cj_meter: u32,
    /// Plan the approach: off, profile (smooth speed only), stable (profile and a stable far-out
    /// schedule), full (stable, and followers plan from their leader's plan).
    #[arg(long, default_value = "off")]
    pub cj_plan: String,
    /// Time margin between conflicting cars, s.
    #[arg(long)]
    pub cj_margin: Option<f64>,
    /// Sigma of each car's position bias, m.
    #[arg(long, default_value_t = 0.0)]
    pub cj_pos_err: f32,
    /// Sigma of each car's clock bias, s.
    #[arg(long, default_value_t = 0.0)]
    pub cj_clock_err: f32,
    /// Braking a planned slot assumes, m/s².
    #[arg(long)]
    pub cj_plan_b: Option<f64>,
    /// Firm horizon, s.
    #[arg(long)]
    pub cj_firm: Option<f64>,
    /// How long before its slot a car's place in the order is fixed, s.
    #[arg(long)]
    pub cj_plan_freeze: Option<f64>,
    /// A wait up to this long is planned at the gentle rate; longer waits brake firmer, s.
    #[arg(long)]
    pub cj_plan_slack: Option<f64>,
    /// A held slot moves earlier only for this gain, s.
    #[arg(long)]
    pub cj_plan_up: Option<f64>,
    /// Leave the point of no return out of the headway table (for comparison).
    #[arg(long)]
    pub cj_no_ponr_table: bool,
    /// Measurements start here.
    #[arg(long, default_value_t = 0.0)]
    pub cj_warm: f32,
}

impl CoordArgs {
    pub fn config(&self) -> Result<Option<CoordConfig>, String> {
        let Some(sel) = &self.cj else { return Ok(None) };
        let select = if sel == "all" {
            Select::All
        } else if let Some(b) = sel.strip_prefix("box:") {
            let v: Vec<f32> = b.split(',').filter_map(|x| x.parse().ok()).collect();
            if v.len() != 4 {
                return Err("--cj box:x0,y0,x1,y1".into());
            }
            Select::Box([v[0], v[1], v[2], v[3]])
        } else {
            Select::Ids(sel.split(',').map(String::from).collect())
        };
        let pair = |v: &[f32], name: &str| -> Result<Option<(f32, f32)>, String> {
            match v.len() {
                0 => Ok(None),
                2 => Ok(Some((v[0], v[1]))),
                _ => Err(format!("--{name} t0,t1")),
            }
        };
        let mut exit_faults = Vec::new();
        for f in &self.cj_exit_fault {
            let p: Vec<&str> = f.split(':').collect();
            if p.len() < 3 {
                return Err("--cj-exit-fault prefix:t0:t1[:vehph]".into());
            }
            exit_faults.push(ExitFault {
                lane_prefix: p[0].to_string(),
                t0: p[1].parse().map_err(|_| "t0")?,
                t1: p[2].parse().map_err(|_| "t1")?,
                cap: p.get(3).map_or(Ok(0.0), |x| x.parse()).map_err(|_| "cap")?,
            });
        }
        let mode = match self.cj_mode.as_str() {
            "free" => coord::MODE_FREE,
            "signal" => coord::MODE_SIGNAL,
            "mixed" => return Err("mixed mode is reserved: this build runs automated cars only".into()),
            other => return Err(format!("unknown --cj-mode {other}")),
        };
        let mut modes = rustc_hash::FxHashMap::default();
        for m in &self.cj_junction_mode {
            let (id, name) = m.split_once('=').ok_or("--cj-junction-mode id=free|signal")?;
            let value = match name {
                "free" => coord::MODE_FREE,
                "signal" => coord::MODE_SIGNAL,
                other => return Err(format!("unknown mode {other} for {id}")),
            };
            modes.insert(id.to_string(), value);
        }
        let mut c = CoordConfig {
            select,
            mode,
            modes,
            level_b: self.cj_level_b,
            exit_check: !self.cj_no_exit_check,
            ponr: !self.cj_no_exit_check,
            perception: !self.cj_no_perception,
            audit: !self.cj_no_audit,
            p_loss: self.cj_loss,
            blackout: pair(&self.cj_blackout, "cj-blackout")?,
            crash: pair(&self.cj_crash, "cj-crash")?,
            fallback_awsc: !self.cj_no_fallback,
            stall_rate: self.cj_stall_rate,
            stall_t: self.cj_stall_t,
            warm: self.cj_warm,
            chan: self.cj_chan,
            sig_max: self.cj_sig_max,
            sig_gap: self.cj_sig_gap,
            exit_faults,
            ..Default::default()
        };
        if self.cj_human {
            c = c.human();
        }
        c.plan = match self.cj_plan.as_str() {
            "off" => 0,
            "profile" => coord::PLAN_PROFILE,
            "stable" => coord::PLAN_PROFILE | coord::PLAN_STABLE,
            "full" => coord::PLAN_PROFILE | coord::PLAN_STABLE | coord::PLAN_FOLLOW,
            "cubic" => coord::PLAN_PROFILE | coord::PLAN_STABLE | coord::PLAN_FOLLOW | coord::PLAN_CUBIC,
            "dr" => coord::PLAN_PROFILE | coord::PLAN_STABLE | coord::PLAN_FOLLOW | coord::PLAN_DR,
            other => return Err(format!("unknown --cj-plan {other}")),
        };
        if let Some(m) = self.cj_margin {
            c.m_t = m;
        }
        if let Some(b) = self.cj_plan_b {
            c.plan_b = b;
        }
        if let Some(t) = self.cj_firm {
            c.t_firm = t;
        }
        if let Some(t) = self.cj_plan_freeze {
            c.plan_freeze = t;
        }
        if let Some(t) = self.cj_plan_slack {
            c.plan_slack = t;
        }
        if let Some(t) = self.cj_plan_up {
            c.plan_up = t;
        }
        c.plan_ponr_table = !self.cj_no_ponr_table;
        c.pos_err = self.cj_pos_err;
        c.clock_err = self.cj_clock_err;
        Ok(Some(c))
    }
}

#[derive(Parser)]
pub struct Args {
    #[arg(long)]
    net: PathBuf,
    #[arg(long, num_args = 1.., value_delimiter = ',')]
    routes: Vec<PathBuf>,
    #[arg(long, value_delimiter = ',')]
    additional: Vec<PathBuf>,
    #[arg(long, default_value_t = 0.1)]
    dt: f32,
    #[arg(long, default_value_t = 800.0)]
    end: f32,
    #[arg(long, default_value_t = 0)]
    seed: u64,
    #[arg(long, default_value_t = 0)]
    capacity: u32,
    #[arg(long)]
    json: Option<PathBuf>,
    /// One line per kernel at these times.
    #[arg(long, value_delimiter = ',')]
    profile_at: Vec<f32>,
    /// Keep going past overlaps quietly; list at most this many in the output.
    #[arg(long, default_value_t = 12)]
    list_overlaps: usize,
    /// Print vehicles that overlap on a lane, at every chunk.
    #[arg(long)]
    debug_lanes: bool,
    /// Print these trips every step between two times: t0,t1,trip,trip... With only t0,t1, every car.
    #[arg(long, value_delimiter = ',')]
    trace: Vec<f32>,
    #[command(flatten)]
    coord: CoordArgs,
}

pub fn run(a: Args) -> Result<(), Box<dyn std::error::Error>> {
    let wall0 = Instant::now();
    let mut net = Net::load(&a.net)?;
    for p in &a.additional {
        net.load_additional(p)?;
    }
    let demand = Demand::load(&net, &a.routes, &a.additional, a.seed, Some(a.end as f64))?;
    let cfg_coord = a.coord.config()?;
    let warm = a.coord.cj_warm;
    let cfg = SimConfig {
        dt: a.dt,
        end_seconds: a.end,
        seed: a.seed,
        capacity: a.capacity,
        time_to_teleport: 0.0,
        per_lane_queues: true,
        meter_n: a.coord.cj_meter,
        coord: cfg_coord,
        ..Default::default()
    };
    let world = World::build(&net, &demand, &cfg, &[]);
    if let Some(c) = &world.coord {
        eprintln!(
            "{} junctions coordinated, {} movements, {} conflict pairs, {:.2} MB, {} refused",
            c.junctions.len(),
            c.links.len(),
            c.conflicts.len(),
            c.memory_bytes() as f64 / 1e6,
            c.refused.len()
        );
        for (id, why) in c.refused.iter().take(8) {
            eprintln!("  refused {id}: {why}");
        }
    }
    let checks = cars_core::Checks::Safe;
    let gpu = pollster::block_on(Gpu::headless(GpuOptions { adapter_name: Some(std::env::var("CARS_ADAPTER").unwrap_or("7900".into())), checks }))?;
    let mut sim = Sim::new(&gpu, &world)?;
    let setup_s = wall0.elapsed().as_secs_f64();
    let steps = (a.end / a.dt).ceil() as u64;
    let warm_step = (warm / a.dt).round() as u64;
    let chunk = (2.0 / a.dt).round() as u64;
    let mut depart: Vec<u32> = world.trips.iter().map(|t| t.depart_step).collect();
    depart.sort_unstable();
    let offered = depart.iter().filter(|&&d| d as u64 >= warm_step).count();
    let n_stats = coord::STATS_PER_REPLICA as usize;
    let mut stats = vec![0u64; n_stats];
    let mut overlap_keys: HashSet<(u32, u32, u32)> = HashSet::new();
    let mut overlap_list = Vec::new();
    let mut dropped_events = 0u64;
    let mut queue_loss = 0f64;
    let mut arrived_warm = 0u32;
    let mut peakq = 0usize;
    let mut q_at_warm = 0i64;
    let mut q_last = 0i64;
    let mut profile = Vec::new();
    let mut profile_at = a.profile_at.clone();
    let run_t = Instant::now();
    let (mut step_n, mut active_steps) = (0u64, 0u64);
    while step_n < steps {
        let t_now = step_n as f32 * a.dt;
        let tracing = a.trace.len() >= 2 && t_now >= a.trace[0] && t_now < a.trace[1];
        let n = if tracing { 1 } else { chunk.min(steps - step_n).min(if step_n < warm_step { warm_step - step_n } else { u64::MAX }) };
        if tracing {
            for v in sim.vehicles(&gpu) {
                if v.flags & 1 == 0 && v.lane != world.params.dummy_lane && (a.trace.len() == 2 || a.trace[2..].contains(&(v.trip as f32))) {
                    eprintln!("tr t={:.1} trip {} lane {} pos {:.2} v {:.2} a {:.2} st {:#x} link {} seq {} tl {:.2} vl {:.2} cmd {:.2} flags {:#x} cr {:.1}", t_now, v.trip, net.lanes[v.lane as usize].id, v.pos, v.speed, v.acc, v.cj_state, v.cj_link as i32, v.cj_seq, v.cj_t_line, v.cj_v_line, v.cj_v_cmd, v.flags, v.cj_v_cruise);
                }
            }
        }
        if let Some(i) = profile_at.iter().position(|&t| t <= t_now) {
            profile_at.remove(i);
            let g = sim.globals(&gpu);
            let times = sim.profile_step(&gpu);
            profile.push(serde_json::json!({"t": t_now, "vehicles": g.n_active, "kernels": times.iter().map(|x| (x.0.clone(), x.1)).collect::<Vec<_>>()}));
            step_n += 1;
            continue;
        }
        sim.run(&gpu, n);
        step_n += n;
        let c = sim.counters(&gpu);
        let g = sim.globals(&gpu);
        active_steps += g.n_active as u64 * n;
        let inserted = c[3] as usize;
        let due = depart.partition_point(|&d| d as u64 <= step_n);
        let queued = due.saturating_sub(inserted);
        if step_n > warm_step {
            queue_loss += queued as f64 * n as f64 * a.dt as f64;
        }
        if step_n == warm_step {
            arrived_warm = c[2];
        }
        if step_n % (chunk * 5) == 0 || step_n == warm_step || step_n >= steps {
            let vs = sim.vehicles(&gpu);
            let slow = vs.iter().filter(|v| v.flags & 1 == 0 && v.speed < 2.0).count();
            let q = queued + slow;
            q_last = q as i64;
            if step_n == warm_step {
                q_at_warm = q as i64;
            }
            if step_n >= warm_step {
                peakq = peakq.max(q);
            }
            for (i, x) in sim.take_coord_stats(&gpu).iter().enumerate() {
                stats[i % n_stats] += *x as u64;
            }
        }
        if a.debug_lanes {
            let mut vs = sim.vehicles(&gpu);
            vs.retain(|v| v.flags & 1 == 0);
            vs.sort_by(|x, y| x.lane.cmp(&y.lane).then(x.pos.total_cmp(&y.pos)));
            for w in vs.windows(2) {
                if w[0].lane == w[1].lane && w[1].pos - 5.0 < w[0].pos {
                    eprintln!(
                        "t={:.1} lane {} back trip {} pos {:.2} v {:.2} st {:#x} link {} | front trip {} pos {:.2} v {:.2} st {:#x} lc {:#x} prev {}",
                        step_n as f32 * a.dt, net.lanes[w[0].lane as usize].id, w[0].trip, w[0].pos, w[0].speed, w[0].cj_state, w[0].cj_link as i32, w[1].trip, w[1].pos, w[1].speed, w[1].cj_state, w[1].flags, net.lanes.get(w[1].prev_lane as usize).map_or("-", |l| l.id.as_str())
                    );
                }
            }
        }
        let (ev, dropped) = sim.take_coord_events(&gpu);
        dropped_events += dropped as u64;
        for e in ev {
            let t = e.step as f32 * a.dt;
            let key = (e.trip_a.min(e.trip_b), e.trip_a.max(e.trip_b), (t / 10.0) as u32);
            if overlap_keys.insert(key) && t >= warm && overlap_list.len() < a.list_overlaps {
                let cw = world.coord.as_ref().unwrap();
                let id = cw.ids.get(e.junction as usize).cloned().unwrap_or_default();
                let name = |m: u32| {
                    let l = &cw.links[m as usize];
                    format!("{}>{}", net.lanes[cw.apps[l.from_lane as usize].sim_lane as usize].id, net.lanes[cw.exits[l.to_lane as usize].sim_lane as usize].id)
                };
                overlap_list.push(serde_json::json!({"t": t, "a": e.trip_a, "b": e.trip_b, "junction": id, "mov_a": name(e.mov_a), "mov_b": name(e.mov_b), "s_a": e.s_a, "s_b": e.s_b}));
            }
        }
    }
    let run_s = run_t.elapsed().as_secs_f64();
    let c = sim.counters(&gpu);
    let out = sim.trip_outputs(&gpu);
    let vs = sim.vehicles(&gpu);
    let span = (a.end - warm) as f64;
    let exited = (c[2] - arrived_warm) as f64;
    let mut delays: Vec<f32> = Vec::new();
    let mut spawn_stops = 0u64;
    for (i, o) in out.iter().enumerate() {
        if o.flags & 1 != 0 && o.arrive_step as u64 >= warm_step {
            delays.push((o.arrive_step - world.trips[i].depart_step) as f32 * a.dt);
        }
        if o.flags & 1 != 0 && o.depart_step as u64 >= warm_step && (o.depart_step - world.trips[i].depart_step) as f32 * a.dt > 2.0 {
            spawn_stops += 1;
        }
    }
    for v in &vs {
        if v.flags & 1 == 0 && v.depart_step as u64 >= warm_step && (v.depart_step - world.trips[v.trip as usize].depart_step) as f32 * a.dt > 2.0 {
            spawn_stops += 1;
        }
    }
    let (mut loss_sum, mut loss_n) = (0f64, 0u64);
    for o in out.iter().filter(|o| o.flags & 1 != 0 && o.arrive_step as u64 >= warm_step) {
        loss_sum += o.time_loss as f64;
        loss_n += 1;
    }
    // Gridlock is a failure with a location: lanes where cars have stood still for two minutes.
    let mut stuck: std::collections::HashMap<u32, u32> = Default::default();
    for v in vs.iter().filter(|v| v.flags & 1 == 0 && v.wait > 120.0) {
        *stuck.entry(v.lane).or_default() += 1;
    }
    let mut stuck: Vec<(u32, u32)> = stuck.into_iter().collect();
    stuck.sort_by_key(|x| std::cmp::Reverse(x.1));
    let stuck_total: u32 = stuck.iter().map(|x| x.1).sum();
    let stuck_where: Vec<(String, u32)> = stuck.iter().take(6).map(|&(l, n)| (net.lanes.get(l as usize).map_or("-".to_string(), |x| x.id.clone()), n)).collect();
    delays.sort_by(f32::total_cmp);
    let pct = |p: f64| delays.get(((delays.len().saturating_sub(1)) as f64 * p) as usize).copied().unwrap_or(0.0);
    let mean = |v: &[f32]| v.iter().map(|&x| x as f64).sum::<f64>() / v.len().max(1) as f64;
    let overlaps = overlap_keys.iter().filter(|k| k.2 as f32 * 10.0 + 10.0 > warm).count();
    let loss = stats[stat::LOSS] as f64 / 256.0 * a.dt as f64 + queue_loss;
    let inserted = c[3] as i64;
    let arrived = c[2] as i64;
    let active = vs.iter().filter(|v| v.flags & 1 == 0).count() as i64;
    let pending = depart.len() as i64 - arrived;
    let conservation = inserted - arrived - active;
    let result = serde_json::json!({
        "flow": exited * 3600.0 / span,
        "offered": offered as f64 * 3600.0 / span,
        "delay": loss / (offered.max(1)) as f64,
        "stops": (stats[stat::STOPS] + spawn_stops) as f64 / exited.max(1.0),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "trip": mean(&delays),
        "time_loss": loss_sum / loss_n.max(1) as f64,
        "stuck": stuck_total,
        "stuck_where": stuck_where,
        "pending": pending,
        "growth": (q_last - q_at_warm) as f64 / span * 3600.0,
        "overlap": overlaps,
        "overlap_steps": stats[stat::OVERLAP_STEPS],
        "overlap_events_dropped": dropped_events,
        "overlaps": overlap_list,
        "invariant": stats[stat::CROSS_UNGRANTED] + stats[stat::STOP_CURVE],
        "cross_ungranted": stats[stat::CROSS_UNGRANTED],
        "stop_curve": stats[stat::STOP_CURVE],
        "neg_credit": stats[stat::NEG_CREDIT],
        "conservation": conservation,
        "late": stats[stat::LATE],
        "late_committed": stats[stat::LATE_COMMITTED],
        "aborts": stats[stat::ABORTS],
        "ponr_abort": stats[stat::PONR_ABORT],
        "rms_a": ((stats[stat::A2] as f64 / 256.0) / (stats[stat::A2N].max(1)) as f64).sqrt(),
        "peakq": peakq,
        "grants": stats[stat::GRANTS],
        "err_mean_abs": stats[stat::ERR_ABS] as f64 / 1000.0 / stats[stat::ERR_N].max(1) as f64,
        "err_big": stats[stat::ERR_BIG],
        "err_n": stats[stat::ERR_N],
        "stalls": stats[stat::STALLS],
        "box_block": stats[stat::BOX_BLOCK] as f64 * a.dt as f64,
        "yields": stats[stat::YIELDS],
        "speed_lost": stats[stat::SPEED_LOST] as f64 / 1000.0,
        "wh_lost": stats[stat::KE_LOST] as f64 * 1500.0 / 2.0 / 3600.0 / 100.0,
        "hard_stop_curve": stats[stat::HARD_STOP_CURVE],
        "hard_leader": stats[stat::HARD_LEADER],
        "hard_yield": stats[stat::HARD_YIELD],
        "hard_hold": stats[stat::HARD_HOLD],
        "hard_plan": stats[stat::HARD_PLAN],
        "hard_stall": stats[stat::HARD_STALL],
        "moved_later": stats[stat::MOVED_LATER],
        "moved_earlier": stats[stat::MOVED_EARLIER],
        "slots_full": stats[stat::SLOTS_FULL],
        "exit_refused": stats[stat::EXIT_REFUSED],
        "bytes_up": stats[stat::BYTES_UP],
        "bytes_down": stats[stat::BYTES_DOWN],
        "err_hist": (0..10).map(|i| stats[stat::ERR_HIST + i]).collect::<Vec<_>>(),
        "holds": stats[stat::HOLDS],
        "msg_sent": stats[stat::MSG_SENT],
        "msg_lost": stats[stat::MSG_LOST],
        "aud_overflow": stats[stat::AUD_OVERFLOW],
        "box_overflow": stats[stat::BOX_OVERFLOW],
        "teleports": c[4],
        "collisions": c[7],
        "inserted": inserted,
        "arrived": arrived,
        "steps": steps,
        "setup_s": setup_s,
        "wall": run_s,
        "ms_per_step": run_s * 1000.0 / steps as f64,
        "gpu_ms_per_step": sim.gpu_ms / steps as f64,
        "mean_active": active_steps as f64 / steps as f64,
        "coord_mb": world.coord.as_ref().map_or(0.0, |c| c.memory_bytes() as f64 / 1e6),
        "gpu_mb": sim.buffers.total_bytes as f64 / 1e6,
        "junctions": world.coord.as_ref().map_or(0, |c| c.junctions.len()),
        "movements": world.coord.as_ref().map_or(0, |c| c.links.len()),
        "conflict_pairs": world.coord.as_ref().map_or(0, |c| c.conflicts.len()),
        "refused": world.coord.as_ref().map_or(0, |c| c.refused.len()),
        "ids": world.coord.as_ref().map_or(Vec::new(), |c| c.ids.clone()),
        "profile": profile,
    });
    let text = serde_json::to_string(&result)?;
    if let Some(p) = &a.json {
        std::fs::write(p, &text)?;
    }
    println!("{text}");
    Ok(())
}
