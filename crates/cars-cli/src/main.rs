#![recursion_limit = "512"]
use clap::{Parser, Subcommand};
mod av;
mod dbgnet;
mod junctions;
mod overlay;
mod record;
mod replay;
mod report;
mod run;
mod trace;
#[derive(Parser)]
struct Args {
    #[command(subcommand)]
    command: Command,
}
#[derive(Subcommand)]
enum Command {
    Run(run::Args),
    Record(record::Args),
    /// Save PNGs at given simulation times and cameras, without making a video.
    Shot(record::Args),
    /// Draw a trace written by `cars run --trace`, with no simulation at all.
    Replay(replay::Args),
    /// List the busiest junctions of each kind.
    Junctions(junctions::Args),
    /// Run coordinated junctions and report flow, delay, stops, collisions and failures as JSON.
    Av(av::Args),
    /// Write the net's lanes, links and junctions as JSON, for the debugging tools.
    Netinfo(dbgnet::Args),
    /// Explain a car at a tick: which limit decided its speed, who blocks it. See DEBUGGING.md.
    Why(dbgnet::Forward),
    /// Time-space diagrams and flow, density and speed heatmaps of a road, beside real tracks.
    Tsd(dbgnet::Forward),
    /// Walk who waits for whom back to the first cause; rank the seeds of a city run.
    Jam(dbgnet::Forward),
    /// Real against simulated at any level: sensors, map, road class, hour, junction type.
    Compare(dbgnet::Forward),
    /// Per junction: flow per movement, lost time, stops, queue, gaps, blocked time and by what.
    Junction(dbgnet::Forward),
    /// Distances between runs, or a run and real tracks: acceleration, braking, gaps, speeds, lane changes.
    Dist(dbgnet::Forward),
    /// A small scene around one place of a city recipe, to study a seed tick by tick on llvmpipe.
    Cut(dbgnet::Forward),
    /// Walk every route lane by lane against links and line markings; list what cannot be driven.
    Lanes(dbgnet::Forward),
}
fn fail(name: &str, e: impl std::fmt::Display) -> ! {
    eprintln!("{name}: {e}");
    std::process::exit(1);
}
fn main() {
    match Args::parse().command {
        Command::Run(a) => run::run(a),
        Command::Record(a) => {
            if let Err(e) = record::run(a, false) {
                fail("record", e);
            }
        }
        Command::Shot(a) => {
            if let Err(e) = record::run(a, true) {
                fail("shot", e);
            }
        }
        Command::Av(a) => {
            if let Err(e) = av::run(a) {
                fail("av", e);
            }
        }
        Command::Replay(a) => {
            if let Err(e) = replay::run(a) {
                fail("replay", e);
            }
        }
        Command::Netinfo(a) => {
            if let Err(e) = dbgnet::run(a) {
                fail("netinfo", e);
            }
        }
        Command::Why(a) => dbgnet::forward("why", a),
        Command::Tsd(a) => dbgnet::forward("tsd", a),
        Command::Jam(a) => dbgnet::forward("jam", a),
        Command::Compare(a) => dbgnet::forward("compare", a),
        Command::Junction(a) => dbgnet::forward("junction", a),
        Command::Dist(a) => dbgnet::forward("dist", a),
        Command::Cut(a) => dbgnet::forward("cut", a),
        Command::Lanes(a) => dbgnet::forward("lanes", a),
        Command::Junctions(a) => {
            if let Err(e) = junctions::run(a) {
                fail("junctions", e);
            }
        }
    }
}
