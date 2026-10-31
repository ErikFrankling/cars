use clap::{Parser, Subcommand};
mod record;
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
}
fn main() {
    match Args::parse().command {
        Command::Run(a) => run::run(a),
        Command::Record(a) => {
            if let Err(e) = record::run(a) {
                eprintln!("record: {e}");
                std::process::exit(1);
            }
        }
    }
}
