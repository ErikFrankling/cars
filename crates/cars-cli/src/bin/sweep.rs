//! Runs a whole thesis sweep (tiers x penetrations x seeds) as replicas in one GPU world.

use std::io::Write;
use std::path::PathBuf;
use std::time::Instant;

use cars_core::metrics::{EdgeLog, replica_metrics};
use cars_core::{Checks, Gpu, GpuOptions, demand::Demand, net::Net, sim::Sim, world::{Replica, SimConfig, World}};
use clap::Parser;

#[derive(Parser)]
struct Args {
    #[arg(long)]
    scenario: String,
    #[arg(long, default_value = "/home/erikf/projects/personal/thesis-src/bachelor/config")]
    root: PathBuf,
    #[arg(long, value_delimiter = ',', default_value = "krauss,idm,acc,cacc,glosa")]
    tiers: Vec<String>,
    #[arg(long, value_delimiter = ',')]
    penetrations: Vec<f64>,
    #[arg(long, value_delimiter = ',', default_value = "0,1,2")]
    seeds: Vec<u64>,
    #[arg(long)]
    capacity_per_replica: Option<u32>,
    #[arg(long)]
    end: Option<f32>,
    /// Write per-interval edge data for these labels (for time-space plots).
    #[arg(long)]
    out: PathBuf,
    #[arg(long, default_value_t = 256)]
    block: u32,
}

struct Spec {
    net: PathBuf,
    routes: Vec<PathBuf>,
    additional: Vec<PathBuf>,
    dt: f32,
    end: f32,
    interval: f32,
    capacity: u32,
    glosa: bool,
    script_t0: f32,
}

fn spec(a: &Args) -> Spec {
    let r = &a.root;
    let vt = r.join("vtypes.xml");
    match a.scenario.as_str() {
        "ring" => Spec {
            net: r.join("networks/ring.net.xml"),
            routes: vec![r.join("demand/ring.rou.xml")],
            additional: vec![vt],
            dt: 0.1,
            end: 4000.0,
            interval: 50.0,
            capacity: 200,
            glosa: false,
            script_t0: 2000.0,
        },
        "bologna" => Spec {
            net: r.join("scenarios/bologna/joined_buslanes.net.xml"),
            routes: vec![r.join("scenarios/bologna/bologna_cars.rou.xml")],
            additional: vec![vt, r.join("scenarios/bologna/joined_tls.add.xml")],
            dt: 0.1,
            end: 5400.0,
            interval: 60.0,
            capacity: 2500,
            glosa: true,
            script_t0: 0.0,
        },
        "i80_vsl" => Spec {
            net: r.join("networks/i80_vsl.net.xml"),
            routes: vec![r.join("demand/i80_vsl.rou.xml")],
            additional: vec![vt],
            dt: 1.0,
            end: 18000.0,
            interval: 60.0,
            capacity: 6000,
            glosa: false,
            script_t0: 0.0,
        },
        "glosa_two_signal" => Spec {
            net: r.join("networks/glosa_two_signal.net.xml"),
            routes: vec![r.join("demand/glosa_two_signal.rou.xml")],
            additional: vec![vt],
            dt: 0.1,
            end: 2400.0,
            interval: 60.0,
            capacity: 300,
            glosa: true,
            script_t0: 0.0,
        },
        other => panic!("unknown scenario {other}"),
    }
}

fn tier_type(t: &str) -> &'static str {
    match t {
        "krauss" => "av_krauss",
        "idm" => "av_basic",
        "acc" => "av_acc",
        "cacc" => "av_cacc",
        "glosa" => "av_glosa",
        _ => panic!("unknown tier {t}"),
    }
}

fn splitmix(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E3779B97F4A7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

fn main() {
    let args = Args::parse();
    let sp = spec(&args);
    let mut net = Net::load(&sp.net).expect("net");
    for a in &sp.additional {
        net.load_additional(a).expect("additional");
    }
    let demand = Demand::load(&net, &sp.routes, &sp.additional, 0, Some(sp.end as f64)).expect("demand");
    eprintln!("{}", demand.summary());
    let human = demand.vtype_index["human"];
    let pens = if args.penetrations.is_empty() {
        (0..=20).map(|i| i as f64 * 0.05).collect()
    } else {
        args.penetrations.clone()
    };
    let mut replicas = Vec::new();
    for tier in &args.tiers {
        if tier == "glosa" && !sp.glosa {
            continue;
        }
        let av = demand.vtype_index[tier_type(tier)];
        for &p in &pens {
            for &seed in &args.seeds {
                let n = demand.trips.len();
                let count = (n as f64 * p).round() as usize;
                let mut order: Vec<u32> = (0..n as u32).collect();
                let mut rng = seed.wrapping_mul(7919) ^ ((p * 1000.0) as u64) << 20;
                for i in (1..n).rev() {
                    let j = (splitmix(&mut rng) % (i as u64 + 1)) as usize;
                    order.swap(i, j);
                }
                let mut trip_vtype = vec![human; n];
                for &t in &order[..count] {
                    trip_vtype[t as usize] = av;
                }
                replicas.push(Replica {
                    seed: seed + 1 + (p * 1000.0) as u64 * 100,
                    trip_vtype,
                    label: format!("{},{tier},{p},{seed}", args.scenario),
                });
            }
        }
    }
    let labels: Vec<String> = replicas.iter().map(|r| r.label.clone()).collect();
    let end = args.end.unwrap_or(sp.end);
    let cfg = SimConfig {
        dt: sp.dt,
        end_seconds: end,
        capacity: args.capacity_per_replica.unwrap_or(sp.capacity) * replicas.len() as u32,
        block: args.block,
        script_t0: sp.script_t0,
        ..Default::default()
    };
    let t = Instant::now();
    let mut world = World::build(&net, &demand, &cfg, &replicas);
    if sp.script_t0 > 0.0 {
        // The disturbed vehicle in every replica.
        let v0 = demand.trips.iter().position(|t| demand.ids[t.id as usize] == "v0").unwrap_or(0);
        for r in 0..replicas.len() {
            world.trips[r * demand.trips.len() + v0].pad[0] = 1;
        }
    }
    eprintln!(
        "{} replicas, {} lanes, {} trips, capacity {}, key bits {}, built in {:.1}s",
        replicas.len(), world.lanes.len(), world.trips.len(), world.params.capacity, world.params.key_bits, t.elapsed().as_secs_f64()
    );
    let gpu = pollster::block_on(Gpu::headless(GpuOptions { adapter_name: Some("7900".into()), checks: Checks::Trusted })).expect("gpu");
    let mut sim = Sim::new(&gpu, &world).expect("sim");
    eprintln!("gpu buffers {:.0} MB", sim.buffers.total_bytes as f64 / 1e6);
    let steps = (end / sp.dt).ceil() as u64;
    let interval = (sp.interval / sp.dt).round() as u64;
    let mut edges = EdgeLog::new(&world, interval, false);
    let t = Instant::now();
    let mut done = 0;
    let mut last = Instant::now();
    while done < steps {
        let next_stop = ((done / interval) + 1) * interval;
        sim.run(&gpu, next_stop.min(steps) - done);
        done = next_stop.min(steps);
        edges.collect(&gpu, &sim, &world);
        if last.elapsed().as_secs_f64() > 5.0 {
            let g = sim.globals(&gpu);
            let c = sim.counters(&gpu);
            eprintln!("t={:.0}s active {} inserted {} arrived {} teleports {} overflow {} lanechanges {} ({:.0} steps/s, {} steps/submit)",
                done as f32 * sp.dt, g.n_active, c[3], c[2], c[4], c[5], c[6], done as f64 / t.elapsed().as_secs_f64(), sim.steps_per_submit);
            last = Instant::now();
        }
    }
    let wall = t.elapsed().as_secs_f64();
    let c = sim.counters(&gpu);
    eprintln!("done in {wall:.1}s: arrived {} teleports {} collisions {} overflow {}", c[2], c[4], c[7], c[5]);
    let metrics = replica_metrics(&gpu, &sim, &world, &labels, &edges);
    let mut f = std::io::BufWriter::new(std::fs::File::create(&args.out).expect("out"));
    writeln!(f, "scenario,tier,penetration,seed,completed,travel_time,waiting_time,time_loss,speed,running,edge_flow,density").unwrap();
    for m in &metrics {
        writeln!(f, "{},{},{},{},{},{},{},{},{}", m.label, m.completed, m.travel_time, m.waiting_time, m.time_loss, m.speed, m.running, m.edge_flow, m.density).ok();
    }
    println!("wall_seconds={wall:.2} steps={steps} replicas={}", replicas.len());
}
