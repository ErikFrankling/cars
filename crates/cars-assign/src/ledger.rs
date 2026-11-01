//! The conservation ledger and the verdict ladder.

use serde::Serialize;

#[derive(Clone, Debug, Default, Serialize)]
pub struct Ledger {
    pub requested: u64,
    pub arrived: u64,
    pub active: u64,
    pub waiting_to_insert: u64,
    pub not_yet_due: u64,
    pub teleports: u64,
    pub collisions: u64,
    pub imbalance: i64,
}

impl Ledger {
    pub fn unfinished(&self) -> u64 {
        self.requested - self.arrived.min(self.requested)
    }

    pub fn unfinished_share(&self) -> f64 {
        self.unfinished() as f64 / self.requested.max(1) as f64
    }

    /// Exact: arrived, active, waiting and not yet due account for every requested trip, and nothing
    /// teleported or collided out of the kernel.
    pub fn balanced(&self) -> bool {
        self.imbalance == 0 && self.arrived + self.active + self.waiting_to_insert + self.not_yet_due == self.requested
    }

    pub fn clean(&self) -> bool {
        self.balanced() && self.teleports == 0 && self.unfinished_share() < 0.001
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Verdict {
    NetworkSuspect,
    DemandExceedsCut,
    UnstableOrUnconverged,
    FeasibleButCongested,
    IncompatibleWithObservations,
    Converged,
}

#[derive(Clone, Debug, Default)]
pub struct VerdictInput {
    /// Share of the day's requested trips due by the time it stalled, if it stalled.
    pub stalled_at_load: Option<f64>,
    pub suspect_links: usize,
    pub cuts_violated: usize,
    pub converged: bool,
    pub ledger_clean: bool,
    pub observations_conflict: bool,
    /// Mean trip time over free-flow trip time.
    pub delay_ratio: f64,
}

/// In the order of the spec: a loop problem is only what is left once the network and the cuts are cleared.
pub fn verdict(v: &VerdictInput) -> Verdict {
    if v.stalled_at_load.is_some_and(|x| x <= 0.5) || v.suspect_links > 0 {
        return Verdict::NetworkSuspect;
    }
    if v.cuts_violated > 0 {
        return Verdict::DemandExceedsCut;
    }
    if !v.converged || !v.ledger_clean {
        return Verdict::UnstableOrUnconverged;
    }
    if v.observations_conflict {
        return Verdict::IncompatibleWithObservations;
    }
    if v.delay_ratio > 1.5 {
        return Verdict::FeasibleButCongested;
    }
    Verdict::Converged
}
