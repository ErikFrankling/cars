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
        writeln!(f, "begin,edge,samples,distance,entered").unwrap();
    }
    let interval = (args.edge_interval / args.dt).round() as u64;
    let mut edge_log = EdgeLog::new(&world, interval, false);
    let mut done = 0u64;
    let mut last_print = Instant::now();
    let mut vehicle_updates = 0u64;
    let mut last_summary_step = 0u64;
    while done < steps {
        if fcd.is_some() || args.check_overlaps || args.debug_lane.is_some() {
            sim.run_batch(&gpu, 1);
            done += 1;
            let now = args.begin + done as f32 * args.dt;
            if let Some(name) = &args.debug_lane
                && now < args.debug_from
                && fcd.is_none()
            {
                let _ = name;
                continue;
            }
            let vs = sim.vehicles(&gpu);
            if let Some(name) = &args.debug_lane
                && now >= args.debug_from
                && now <= args.debug_to
            {
                let lane = net.lane_index[name];
                let items: Vec<[f32; 10]> = sim.read(&gpu, &sim.buffers.items, vs.len() as u64 * 8);
                if let Some((i, v)) = vs.iter().enumerate().filter(|(_, v)| v.lane == lane).max_by(|a, b| a.1.pos.total_cmp(&b.1.pos)) {
                    println!("t={now:.1} {} pos {:.2} v {:.2} acc {:.2} wait {:.1} flags {:#x} own {:#x} n_items {} best_off {} left_space {:.1} blocker {:.1}", demand.ids[demand.trips[v.trip as usize].id as usize], v.pos, v.speed, v.acc, v.wait, v.flags, v.lc_own, v.n_items, v.best_off, v.left_space, v.blocker);
                    for j in 0..v.n_items as usize {
                        let it = items[i * 8 + j];
                        let link = it[0].to_bits();
                        let desc = if link == u32::MAX { "end".to_string() } else {
                            let l = &world.links[link as usize];
                            format!("{}->{} flags {:#x} tl {} state {} foes {} confs {}", net.lanes[l.from_lane as usize].id, net.lanes[l.next_lane as usize].id, l.flags, l.tl as i32, l.state as u8 as char, l.foe_count, l.conf_count)
                        };
                        println!("   item {j}: {desc} pass {:.2} wait {:.2} req {} arr {:.2} arrv {:.2} dist {:.1} leave {:.2}", it[1], it[2], it[3].to_bits(), it[4], it[5], it[7], it[8]);
                    }
                }
            }
            if args.check_overlaps {
                let mut active: Vec<_> = vs.iter().filter(|v| v.flags & 1 == 0).collect();
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
                    if v.flags & 1 != 0 {
                        continue;
                    }
                    writeln!(f, "{:.2},{},{},{:.4},{:.4},{:.4},{:.1},{},{},{}", args.begin + (done - 1) as f32 * args.dt, demand.ids[demand.trips[v.trip as usize].id as usize], net.lanes[v.lane as usize].id, v.pos, v.speed, v.acc, v.wait, v.lc_own, v.n_items, v.best_off).unwrap();
                }
            }
        } else {
            let next = ((done / interval) + 1) * interval;
            let chunk = (next - done).min(steps - done).min((60.0 / args.dt).ceil() as u64);
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
                    if a[0] > 0 || a[2] > 0 {
                        writeln!(f, "{},{},{},{},{}", begin, net.edges[e].id, a[0] as f32 * world.params.sample_steps as f32 * args.dt, a[1] as f32 / 8.0, a[2]).unwrap();
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
    eprintln!("lane changes {}, teleports {}, collisions {}, overflow {}, items full {}", c[6], c[4], c[7], c[5], c[8]);
    let out = sim.trip_outputs(&gpu);
    if let Some(path) = &args.trip_csv {
        let mut f = std::io::BufWriter::new(std::fs::File::create(path).expect("trip csv"));
        writeln!(f, "trip,depart,arrival,duration,waiting,time_loss,route_length").unwrap();
        for (i, o) in out.iter().enumerate().filter(|(_, o)| o.flags & 1 != 0) {
            let duration = (o.arrive_step - o.depart_step) as f32 * args.dt;
            writeln!(
                f, "{},{},{},{},{},{},{}",
                demand.ids[demand.trips[i].id as usize], args.begin + o.depart_step as f32 * args.dt, args.begin + o.arrive_step as f32 * args.dt,
                duration, o.wait, o.time_loss, o.route_len
            ).unwrap();
        }
    }
    let m = &replica_metrics(&gpu, &sim, &world, &[String::new()], &edge_log)[0];
    println!(
        "wall {wall:.2}s, {:.1} M updates/s, speed {:.2}, running {:.1}, trips done {}, duration {:.2}, wait {:.2}, loss {:.2}, flow {:.1}, density {:.2}",
        vehicle_updates as f64 / wall / 1e6, m.speed, m.running, m.completed, m.travel_time, m.waiting_time, m.time_loss, m.edge_flow, m.density
    );
}
