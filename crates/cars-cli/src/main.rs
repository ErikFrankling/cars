use clap::{Parser, Subcommand};
mod junctions;
mod overlay;
mod record;
mod report;
mod run;
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
    /// List the busiest junctions of each kind.
    Junctions(junctions::Args),
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
        Command::Junctions(a) => {
            if let Err(e) = junctions::run(a) {
                fail("junctions", e);
            }
        }
    }
}
