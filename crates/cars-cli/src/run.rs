use std::path::PathBuf;
use std::time::Instant;

use cars_core::{
    Checks, Gpu, GpuOptions,
    demand::Demand,
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
    #[arg(long, default_value_t = 3600.0)]
    end: f32,
    #[arg(long, default_value_t = 0)]
    seed: u64,
    #[arg(long)]
    fcd: Option<PathBuf>,
}

pub fn run(args: Args) {
    let t = Instant::now();
    let mut net = Net::load(&args.net).expect("net");
    for a in &args.additional {
        net.load_additional(a).expect("additional");
    }
    let demand = Demand::load(
        &net,
        &args.routes,
        &args.additional,
        args.seed,
        Some(args.end as f64),
    )
    .expect("demand");
    eprintln!(
        "loaded in {:.2}s: {}",
        t.elapsed().as_secs_f64(),
        demand.summary()
    );
    let cfg = SimConfig {
        dt: args.dt,
        end_seconds: args.end,
        seed: args.seed,
        ..Default::default()
    };
    let t = Instant::now();
    let world = World::build(&net, &demand, &cfg, &[]);
    eprintln!(
        "world in {:.2}s: {} lanes, {} links, {} foes, {} conflicts, {} tls, {} trips, key bits {}",
        t.elapsed().as_secs_f64(),
        world.lanes.len(),
        world.links.len(),
        world.foes.len(),
        world.conflicts.len(),
        world.tls.len(),
        world.trips.len(),
        world.params.key_bits
    );
    let gpu = pollster::block_on(Gpu::headless(GpuOptions {
        adapter_name: Some("7900".into()),
        checks: Checks::Safe,
    }))
    .expect("gpu");
    let mut sim = Sim::new(&gpu, &world).expect("sim");
    eprintln!(
        "gpu buffers: {:.1} MB, sort passes {}",
        sim.buffers.total_bytes as f64 / 1e6,
        sim.passes()
    );
    let steps = (args.end / args.dt).ceil() as u64;
    let t = Instant::now();
    let mut fcd = args
        .fcd
        .as_ref()
        .map(|p| std::io::BufWriter::new(std::fs::File::create(p).expect("fcd")));
    if let Some(f) = fcd.as_mut() {
        use std::io::Write;
        writeln!(f, "time,trip,lane,pos,speed,acc").unwrap();
    }
    let mut done = 0u64;
    while done < steps {
        if fcd.is_some() {
            sim.run_batch(&gpu, 1);
            done += 1;
            let vs = sim.vehicles(&gpu);
            let f = fcd.as_mut().unwrap();
            use std::io::Write;
            for v in vs.iter() {
                if v.flags & 1 != 0 {
                    continue;
                }
                writeln!(
                    f,
                    "{:.2},{},{},{:.4},{:.4},{:.4}",
                    (done - 1) as f32 * args.dt,
                    demand.ids[demand.trips[v.trip as usize].id as usize],
                    net.lanes[v.lane as usize].id,
                    v.pos,
                    v.speed,
                    v.acc
                )
                .unwrap();
            }
        } else {
            done += sim.run(&gpu, (steps - done).min(1000));
            let g = sim.globals(&gpu);
            let c = sim.counters(&gpu);
            eprintln!(
                "step {done}/{steps}: active {} inserted {} arrived {} teleports {} overflow {} items_full {} ({:.1} steps/s, {} steps per submit)",
                g.n_active,
                c[3],
                c[2],
                c[4],
                c[5],
                c[8],
                done as f64 / t.elapsed().as_secs_f64(),
                sim.steps_per_submit
            );
        }
    }
    let wall = t.elapsed().as_secs_f64();
    let out = sim.trip_outputs(&gpu);
    let done_trips: Vec<_> = out.iter().filter(|o| o.flags & 1 != 0).collect();
    let dur: f64 = done_trips
        .iter()
        .map(|o| (o.arrive_step - o.depart_step) as f64 * args.dt as f64)
        .sum();
    let wait: f64 = done_trips.iter().map(|o| o.wait as f64).sum();
    let loss: f64 = done_trips.iter().map(|o| o.time_loss as f64).sum();
    let n = done_trips.len().max(1) as f64;
    println!(
        "wall {wall:.2}s, trips done {}, duration {:.2}, wait {:.2}, loss {:.2}",
        done_trips.len(),
        dur / n,
        wait / n,
        loss / n
    );
}
