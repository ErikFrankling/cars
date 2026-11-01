//! Route assignment, calibration and demand verdicts on top of the GPU simulator.
//! `research/truth/06-demand-and-route-choice.md` section 8 is the spec.

pub mod calibrate;
pub mod costs;
pub mod cuts;
pub mod day;
pub mod driver;
pub mod enroute;
pub mod ledger;
pub mod population;
pub mod route;
pub mod scenario;
pub mod update;

/// A small deterministic hash, for per-traveller random draws that do not depend on thread order.
pub fn mix(a: u64, b: u64) -> u64 {
    let mut z = a.wrapping_mul(0x9E3779B97F4A7C15) ^ b.wrapping_mul(0xC2B2AE3D27D4EB4F);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

pub fn unit(a: u64, b: u64) -> f64 {
    (mix(a, b) >> 11) as f64 / (1u64 << 53) as f64
}
