use std::io::Write;
use std::path::PathBuf;
use std::time::Instant;

use cars_core::{
    Checks, Gpu, GpuOptions,
    demand::Demand,
    metrics::{EdgeLog, replica_metrics},
    net::Net,
    sim::Sim,
    world::{SimConfig, World},
};
use clap::Parser;

#[derive(Parser)]
pub struct Args {
    #[arg(long)]
    net: PathBuf,
    #[arg(long, num_args = 1.., value_delimiter = ',')]
    routes: Vec<PathBuf>,
    #[arg(long, value_delimiter = ',')]
    additional: Vec<PathBuf>,
    #[arg(long, default_value_t = 1.0)]
    dt: f32,
    #[arg(long, default_value_t = 0.0)]
    begin: f32,
    #[arg(long, default_value_t = 3600.0)]
    end: f32,
    #[arg(long, default_value_t = 0)]
    seed: u64,
    /// Seconds before a stuck lane head teleports. 0 turns it off.
    #[arg(long, default_value_t = 300.0)]
    time_to_teleport: f32,
    #[arg(long, default_value_t = 1e9)]
    ignore_junction_blocker: f32,
    #[arg(long, default_value_t = 0)]
    capacity: u32,
    #[arg(long)]
    fcd: Option<PathBuf>,
    #[arg(long)]
    trip_csv: Option<PathBuf>,
    /// Seconds between trajectory snapshots (simulation still advances at dt).
    #[arg(long, default_value_t = 0.1)]
    fcd_interval: f32,
    /// Per interval: time, running, halting, mean speed, inserted, arrived.
    #[arg(long)]
    summary_csv: Option<PathBuf>,
    /// Edge data every `edge_interval` seconds: interval, edge id, samples, distance, entered.
    #[arg(long)]
    edge_csv: Option<PathBuf>,
    #[arg(long, default_value_t = 900.0)]
    edge_interval: f32,
    #[arg(long)]
    check_overlaps: bool,
    /// Skip bounds checks in shaders once a run is trusted.
    #[arg(long)]
    trusted: bool,
    #[arg(long, default_value_t = 15.0)]
    target_submit_ms: f64,
    /// Print the head vehicle of this lane, with its planned links, from `debug_from` seconds on.
    #[arg(long)]
    debug_lane: Option<String>,
    #[arg(long, default_value_t = 0.0)]
    debug_from: f32,
    #[arg(long, default_value_t = 1e9)]
    debug_to: f32,
    /// Print each collision within the debug window: both vehicles before and after.
    #[arg(long)]
    debug_collisions: bool,
    /// Ignore signal actuation and run every program at its fixed durations.
    #[arg(long)]
    static_tls: bool,
    /// Classify why stuck lane heads are stuck at these simulated times.
    #[arg(long, value_delimiter = ',')]
    diagnose_at: Vec<f32>,
    /// Time every kernel for one step at these simulated times.
    #[arg(long, value_delimiter = ',')]
    profile_at: Vec<f32>,
}

pub fn run(args: Args) {
    let t = Instant::now();
    let mut net = Net::load(&args.net).expect("net");
    for a in &args.additional {
        net.load_additional(a).expect("additional");
    }
    eprintln!("net loaded in {:.2}s", t.elapsed().as_secs_f64());
    let t = Instant::now();
    let demand = Demand::load(&net, &args.routes, &args.additional, args.seed, Some(args.end as f64)).expect("demand");
    eprintln!("demand loaded in {:.2}s: {}", t.elapsed().as_secs_f64(), demand.summary());
    let cfg = SimConfig {
        dt: args.dt,
        begin_seconds: args.begin,
        end_seconds: args.end,
        seed: args.seed,
        time_to_teleport: args.time_to_teleport,
        ignore_blocker: args.ignore_junction_blocker,
        capacity: args.capacity,
        use_actuation: !args.static_tls,
        ..Default::default()
    };
    let t = Instant::now();
    let world = World::build(&net, &demand, &cfg, &[]);
    eprintln!(
        "world in {:.2}s: {} lanes, {} links, {} foes, {} conflicts, {} tls, {} trips, capacity {}, key bits {}",
        t.elapsed().as_secs_f64(), world.lanes.len(), world.links.len(), world.foes.len(), world.conflicts.len(),
        world.tls.len(), world.trips.len(), world.params.capacity, world.params.key_bits
    );
    let checks = if args.trusted { Checks::Trusted } else { Checks::Safe };
    let gpu = pollster::block_on(Gpu::headless(GpuOptions { adapter_name: Some("7900".into()), checks })).expect("gpu");
    let mut sim = Sim::new(&gpu, &world).expect("sim");
    sim.target_submit_ms = args.target_submit_ms;
    eprintln!("gpu buffers: {:.1} MB, sort passes {}", sim.buffers.total_bytes as f64 / 1e6, sim.passes());
    let steps = ((args.end - args.begin) / args.dt).ceil() as u64;
    let t = Instant::now();
    let mut fcd = args.fcd.as_ref().map(|p| std::io::BufWriter::new(std::fs::File::create(p).expect("fcd")));
    if let Some(f) = fcd.as_mut() {
        writeln!(f, "time,trip,lane,pos,speed,acc,wait,own,items,best_off").unwrap();
    }
    let mut summary = args.summary_csv.as_ref().map(|p| std::io::BufWriter::new(std::fs::File::create(p).expect("summary")));
    if let Some(f) = summary.as_mut() {
        writeln!(f, "time,running,inserted,arrived,teleports,wall").unwrap();
    }
    let mut edges_out = args.edge_csv.as_ref().map(|p| std::io::BufWriter::new(std::fs::File::create(p).expect("edges")));
    if let Some(f) = edges_out.as_mut() {
        writeln!(f, "begin,edge,samples,distance,entered,teleports").unwrap();
    }
    let interval = (args.edge_interval / args.dt).round() as u64;
    let mut edge_log = EdgeLog::new(&world, interval, false);
    let mut done = 0u64;
    let mut last_print = Instant::now();
    let mut collision_prev: Vec<cars_core::world::GpuVeh> = Vec::new();
    let mut vehicle_updates = 0u64;
    let mut last_summary_step = 0u64;
    let debug_start = ((args.debug_from - args.begin).max(0.0) / args.dt).ceil() as u64;
    let debug_end = ((args.debug_to - args.begin).max(0.0) / args.dt).floor() as u64;
    while done < steps {
        let debugging = (args.debug_lane.is_some() || args.debug_collisions) && done + 1 >= debug_start && done < debug_end;
        if fcd.is_some() || args.check_overlaps || debugging {
            let stride = if args.check_overlaps || debugging { 1 } else {
                (args.fcd_interval / args.dt).round().max(1.0) as u64
            };
            let advance = stride.min(steps - done).min(interval - done % interval);
            sim.run(&gpu, advance);
            done += advance;
            let now = args.begin + done as f32 * args.dt;
            if (args.debug_lane.is_some() || args.debug_collisions) && now < args.debug_from && fcd.is_none() {
                continue;
            }
            let vs = sim.vehicles(&gpu);
            if args.debug_collisions && now <= args.debug_to {
                let dummy = world.params.dummy_lane;
                let now_lane: std::collections::HashMap<u32, &cars_core::world::GpuVeh> = vs.iter().map(|v| (v.trip, v)).collect();
                for p in &collision_prev {
                    let gone = now_lane.get(&p.trip).is_some_and(|v| v.lane == dummy) && p.lane != dummy;
                    if !gone || p.wait > 100.0 {
                        continue;
                    }
                    let lane = &net.lanes[p.lane as usize].id;
                    println!("t={now} collider trip {} on {} pos {:.2}/{:.1} v {:.2} prev {} n_items {}", p.trip, lane, p.pos, world.lanes[p.lane as usize].length, p.speed, if p.prev_lane == u32::MAX { "-".to_string() } else { net.lanes[p.prev_lane as usize].id.clone() }, p.n_items);
                    for o in collision_prev.iter().filter(|o| o.trip != p.trip && (o.lane == p.lane || now_lane.get(&o.trip).is_some_and(|n| n.lane == p.lane)) ) {
                        let n = now_lane.get(&o.trip);
                        println!("   other {} before {} {:.2} v {:.2}; after {} {:.2} v {:.2}", o.trip, net.lanes[o.lane as usize].id, o.pos, o.speed, n.map_or("-".to_string(), |x| net.lanes[x.lane as usize].id.clone()), n.map_or(0.0, |x| x.pos), n.map_or(0.0, |x| x.speed));
                    }
                }
                collision_prev = vs.clone();
            }
            if let Some(name) = &args.debug_lane
                && now >= args.debug_from
                && now <= args.debug_to
            {
                let lane = net.lane_index[name];
                let items: Vec<[f32; 10]> = sim.read(&gpu, &sim.buffers.items, vs.len() as u64 * 8);
                if let Some((i, v)) = vs.iter().enumerate().filter(|(_, v)| v.lane == lane).max_by(|a, b| a.1.pos.total_cmp(&b.1.pos)) {
                    println!("t={now:.1} {} pos {:.2} v {:.2} acc {:.2} wait {:.1} flags {:#x} own {:#x} n_items {} best_off {} left_space {:.1} blocker {:.1}", demand.ids[demand.trips[world.trip_source[v.trip as usize] as usize].id as usize], v.pos, v.speed, v.acc, v.wait, v.flags, v.lc_own, v.n_items, v.best_off, v.left_space, v.blocker);
                    let ed = net.lanes[lane as usize].edge as usize;
                    for li in 0..net.edges[ed].lane_count {
                        let l2 = net.edges[ed].first_lane + li;
                        let txt = vs.iter().filter(|o| o.lane == l2 && o.flags & 1 == 0).map(|o| format!("{:.1}/{:.1}w{:.0}x{:x}", o.pos, o.speed, o.wait, o.lc_own)).collect::<Vec<_>>().join(" ");
                        println!("      lane {} [{}]", net.lanes[l2 as usize].id, txt);
                    }
                    for j in 0..v.n_items as usize {
                        let it = items[i * 8 + j];
                        let link = it[0].to_bits();
                        let desc = if link == u32::MAX { "end".to_string() } else {
                            let l = &world.links[link as usize];
                            let mut st = l.state as u8 as char;
                            let mut phase = -1i32;
                            if l.tl != u32::MAX {
                                let tls: Vec<cars_core::world::GpuTlsState> = sim.read(&gpu, &sim.buffers.tls, world.tls.len() as u64);
                                let ts = &tls[l.tl as usize];
                                phase = ts.phase as i32;
                                st = world.states[(world.phases[(ts.first_phase + ts.phase) as usize].state_start + l.tl_index) as usize] as u8 as char;
                            }
                            format!("{}->{} flags {:#x} tl {} ph {phase} state {st} foes {} confs {}", net.lanes[l.from_lane as usize].id, net.lanes[l.next_lane as usize].id, l.flags, l.tl as i32, l.foe_count, l.conf_count)
                        };
                        println!("   item {j}: {desc} pass {:.2} wait {:.2} req {} arr {:.2} arrv {:.2} dist {:.1} leave {:.2}", it[1], it[2], it[3].to_bits(), it[4], it[5], it[7], it[8]);
                        if link != u32::MAX && j == 0 {
                            let l = world.links[link as usize];
                            let on = |lane: u32| -> String {
                                vs.iter().filter(|o| o.lane == lane && o.flags & 1 == 0).map(|o| format!("{:.1}/{:.1}w{:.0}", o.pos, o.speed, o.wait)).collect::<Vec<_>>().join(" ")
                            };
                            println!("      next lane {} [{}], to lane {} [{}]", net.lanes[l.next_lane as usize].id, on(l.next_lane), net.lanes[l.to_lane as usize].id, on(l.to_lane));
                            for c in 0..l.conf_count {
                                let cf = world.conflicts[(l.conf_start + c) as usize];
                                let txt = on(cf.foe_lane);
                                if !txt.is_empty() {
                                    println!("      conflict {} flags {} behind {:.1} foe_behind {:.1} w {:.1} fw {:.1} foe len {:.1}: {}", net.lanes[cf.foe_lane as usize].id, cf.flags, cf.len_behind, cf.foe_len_behind, cf.width, cf.foe_width, net.lanes[cf.foe_lane as usize].length, txt);
                                }
                            }
                        }
                    }
                }
            }
            if args.check_overlaps {
                let mut active: Vec<_> = vs.iter().filter(|v| v.flags & 1 == 0 && v.lane != world.params.dummy_lane).collect();
                active.sort_by(|a, b| a.lane.cmp(&b.lane).then(a.pos.total_cmp(&b.pos)));
                for pair in active.windows(2) {
                    let (a, b) = (pair[0], pair[1]);
                    if a.lane == b.lane {
                        let gap = b.pos - world.vtypes[b.vtype as usize].length - a.pos;
                        assert!(gap >= -0.05, "overlap at step {done}, lane {}, trips {} and {}, gap {gap}", net.lanes[a.lane as usize].id, a.trip, b.trip);
                    }
                }
            }
            if let Some(f) = fcd.as_mut() {
                for v in vs.iter() {
                    if v.flags & 1 != 0 || v.lane == world.params.dummy_lane {
                        continue;
                    }
                    writeln!(f, "{:.2},{},{},{:.4},{:.4},{:.4},{:.1},{},{},{}", args.begin + done as f32 * args.dt, demand.ids[demand.trips[world.trip_source[v.trip as usize] as usize].id as usize], net.lanes[v.lane as usize].id, v.pos, v.speed, v.acc, v.wait, v.lc_own, v.n_items, v.best_off).unwrap();
                }
            }
        } else {
            let next = ((done / interval) + 1) * interval;
            let until_debug = if (args.debug_lane.is_some() || args.debug_collisions) && done + 1 < debug_start {
                debug_start - done - 1
            } else {
                u64::MAX
            };
            let mut chunk = (next - done).min(steps - done).min((60.0 / args.dt).ceil() as u64).min(until_debug);
            let t_next = args.begin + (done + chunk) as f32 * args.dt;
            if let Some(&at) = args.diagnose_at.iter().find(|&&at| at > args.begin + done as f32 * args.dt && at <= t_next) {
                chunk = ((at - args.begin) / args.dt) as u64 - done;
                done += sim.run(&gpu, chunk);
                diagnose(&sim, &gpu, &net, &world, at);
                continue;
            }
            if let Some(&at) = args.profile_at.iter().find(|&&at| {
                let s = ((at - args.begin) / args.dt) as u64;
                s > done && s <= done + chunk
            }) {
                let s = ((at - args.begin) / args.dt) as u64;
                if s > done + 1 {
                    chunk = s - done - 1;
                } else {
                    let g = sim.globals(&gpu);
                    let times = sim.profile_step(&gpu);
                    let total: f64 = times.iter().map(|t| t.1).sum();
                    println!("profile at t={at} with {} vehicles: {total:.3} ms", g.n_active);
                    for (name, ms) in times {
                        println!("  {name:12} {ms:8.3} ms");
                    }
                    done += 1;
                    continue;
                }
            }
            let g0 = sim.globals(&gpu);
            done += sim.run(&gpu, chunk);
            let g = sim.globals(&gpu);
            let c = sim.counters(&gpu);
            vehicle_updates += (g0.n_active as u64 + g.n_active as u64) / 2 * chunk;
            if let Some(f) = summary.as_mut() {
                writeln!(f, "{},{},{},{},{},{:.3}", args.begin + done as f32 * args.dt, g.n_active, c[3], c[2], c[4], t.elapsed().as_secs_f64()).unwrap();
                f.flush().ok();
            }
            last_summary_step = done;
            if last_print.elapsed().as_secs_f64() > 5.0 || done >= steps {
                eprintln!(
                    "t={:.0}s: active {} inserted {} arrived {} teleports {} overflow {} lc {} ({:.0} steps/s, {:.1} M updates/s, {} steps per submit)",
                    args.begin + done as f32 * args.dt, g.n_active, c[3], c[2], c[4], c[5], c[6],
                    done as f64 / t.elapsed().as_secs_f64(), vehicle_updates as f64 / t.elapsed().as_secs_f64() / 1e6, sim.steps_per_submit
                );
                last_print = Instant::now();
            }
        }
        if done % interval == 0 || done >= steps {
            let begin = args.begin + ((done - 1) / interval * interval) as f32 * args.dt;
            if let Some(f) = edges_out.as_mut() {
                let acc = sim.take_edge_acc(&gpu);
                for (e, a) in acc.iter().enumerate() {
                    if a[0] > 0 || a[2] > 0 || a[3] > 0 {
                        writeln!(f, "{},{},{},{},{},{}", begin, net.edges[e].id, a[0] as f32 * world.params.sample_steps as f32 * args.dt, a[1] as f32 / 8.0, a[2], a[3]).unwrap();
                    }
                }
            } else {
                edge_log.collect(&gpu, &sim, &world);
            }
        }
    }
    let _ = last_summary_step;
    let wall = t.elapsed().as_secs_f64();
    let c = sim.counters(&gpu);
    eprintln!("lane changes {}, teleports {}, collisions {} (lane change {}, junction {}, lane start {}, other {}), overflow {}, items full {}; teleports jam {} yield {} wrong lane {}", c[6], c[4], c[7], c[9], c[10], c[11], c[12], c[5], c[8], c[13], c[14], c[15]);
    let out = sim.trip_outputs(&gpu);
    if let Some(path) = &args.trip_csv {
        let mut f = std::io::BufWriter::new(std::fs::File::create(path).expect("trip csv"));
        writeln!(f, "trip,depart,arrival,duration,waiting,time_loss,route_length").unwrap();
        for (i, o) in out.iter().enumerate().filter(|(_, o)| o.flags & 1 != 0) {
            let duration = (o.arrive_step - o.depart_step) as f32 * args.dt;
            writeln!(
                f, "{},{},{},{},{},{},{}",
                demand.ids[demand.trips[world.trip_source[i] as usize].id as usize], args.begin + o.depart_step as f32 * args.dt, args.begin + o.arrive_step as f32 * args.dt,
                duration, o.wait, o.time_loss, o.route_len
            ).unwrap();
        }
    }
    eprintln!("time: encode {:.2}s, gpu submit+wait {:.2}s, total {wall:.2}s", sim.encode_ms / 1000.0, sim.gpu_ms / 1000.0);
    let m = &replica_metrics(&gpu, &sim, &world, &[String::new()], &edge_log)[0];
    println!(
        "wall {wall:.2}s, {:.1} M updates/s, speed {:.2}, running {:.1}, trips done {}, duration {:.2}, wait {:.2}, loss {:.2}, flow {:.1}, density {:.2}",
        vehicle_updates as f64 / wall / 1e6, m.speed, m.running, m.completed, m.travel_time, m.waiting_time, m.time_loss, m.edge_flow, m.density
    );
}

/// Why are the heads of stuck lanes stuck?
fn diagnose(sim: &Sim, gpu: &Gpu, net: &Net, world: &World, at: f32) {
    use std::collections::HashMap;
    let vs = sim.vehicles(gpu);
    let items: Vec<[f32; 10]> = sim.read(gpu, &sim.buffers.items, vs.len() as u64 * 8);
    let tls: Vec<cars_core::world::GpuTlsState> = sim.read(gpu, &sim.buffers.tls, world.tls.len() as u64);
    let mut heads: HashMap<u32, usize> = HashMap::new();
    for (i, v) in vs.iter().enumerate() {
        if v.flags & 1 != 0 || v.lane == world.params.dummy_lane {
            continue;
        }
        let e = heads.entry(v.lane).or_insert(i);
        if vs[*e].pos < v.pos {
            *e = i;
        }
    }
    let mut counts: HashMap<String, (u32, f32)> = HashMap::new();
    let mut worst: Vec<(f32, String)> = Vec::new();
    let mut n_stuck = 0;
    for (&lane, &i) in &heads {
        let v = &vs[i];
        if v.wait < 30.0 {
            continue;
        }
        n_stuck += 1;
        let internal = world.lanes[lane as usize].flags & 1 != 0;
        let mut kind = String::new();
        let it = items[i * 8];
        let link = it[0].to_bits();
        if link == u32::MAX {
            let dist = it[7];
            let wants = v.lc_own & 3;
            kind = format!("no link ahead (dist<10:{} wants_lc:{} blocked:{})", dist < 10.0, wants != 0, v.lc_own & 0x180 != 0);
        } else {
            let l = &world.links[link as usize];
            let mut st = l.state as u8 as char;
            if l.tl != u32::MAX {
                let ts = &tls[l.tl as usize];
                st = world.states[(world.phases[(ts.first_phase + ts.phase) as usize].state_start + l.tl_index) as usize] as u8 as char;
            }
            kind = format!("{} state {st} request {} far {}", if l.flags & 16 != 0 { "exit/2nd link" } else { "entry link" }, it[3].to_bits(), it[7] > 15.0);
        }
        if internal {
            kind = format!("[on junction] {kind}");
        }
        let c = counts.entry(kind.clone()).or_insert((0, 0.0));
        c.0 += 1;
        c.1 += v.wait;
        worst.push((v.wait, format!("{} pos {:.0}/{:.0} wait {:.0} own {:#x} {kind}", net.lanes[lane as usize].id, v.pos, world.lanes[lane as usize].length, v.wait, v.lc_own)));
    }
    let mut c: Vec<_> = counts.into_iter().collect();
    c.sort_by_key(|x| std::cmp::Reverse(x.1.0));
    println!("diagnose t={at}: {} active, {} lane heads waiting over 30 s", vs.len(), n_stuck);
    for (k, (n, w)) in c.iter().take(25) {
        println!("  {n:6}  mean wait {:6.1}  {k}", w / *n as f32);
    }
    worst.sort_by(|a, b| b.0.total_cmp(&a.0));
    for (_, w) in worst.iter().take(12) {
        println!("    {w}");
    }
}
