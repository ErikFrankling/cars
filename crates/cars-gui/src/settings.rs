//! The variables of a run. Changing any of them means starting the simulation again.
use crate::registry::{Registry, Scenario};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Junctions {
    /// Signals and priority rules, as in the net.
    Normal,
    /// Signal-free, run by the coordinator.
    SignalFree,
    /// The coordinator running its own signals, the baseline with the same cars and conflict table.
    Baseline,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Plan {
    Off,
    Full,
    Route,
}
impl Plan {
    pub fn label(self) -> &'static str {
        match self {
            Plan::Off => "off",
            Plan::Full => "full",
            Plan::Route => "route",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Settings {
    pub demand_pct: f32,
    pub human_pct: f32,
    /// Model of the automated share. None is human-only, the default.
    pub model: Option<String>,
    pub dt: f32,
    pub seed: u64,
    pub teleports: bool,
    pub teleport_s: f32,
    pub junctions: Junctions,
    pub plan: Plan,
    pub loss_pct: f32,
    pub level_b: bool,
}

impl Settings {
    pub fn for_scenario(s: &Scenario) -> Self {
        Self {
            demand_pct: 100.0,
            human_pct: 100.0,
            model: None,
            dt: s.dt,
            seed: 0,
            teleports: s.time_to_teleport > 0.0,
            teleport_s: if s.time_to_teleport > 0.0 { s.time_to_teleport } else { 300.0 },
            junctions: Junctions::Normal,
            plan: Plan::Off,
            loss_pct: 0.0,
            level_b: false,
        }
    }
    pub fn coordinated(&self, r: &Registry) -> bool {
        self.model.as_deref().and_then(|m| r.model(m)).is_some_and(|m| m.coordinated)
    }
    /// Fraction of cars that are automated. This build's coordinator needs every car automated.
    pub fn automated_share(&self, r: &Registry) -> f32 {
        match &self.model {
            None => 0.0,
            Some(_) if self.coordinated(r) => 1.0,
            Some(_) => ((100.0 - self.human_pct) / 100.0).clamp(0.0, 1.0),
        }
    }
    pub fn human_only(&self, r: &Registry) -> bool {
        self.automated_share(r) <= 0.0
    }
    /// Keep what the choices imply consistent: signal-free needs the coordinated model.
    pub fn normalise(&mut self, r: &Registry) {
        if self.coordinated(r) {
            if self.junctions == Junctions::Normal {
                self.junctions = Junctions::SignalFree;
            }
        } else {
            self.junctions = Junctions::Normal;
            self.plan = Plan::Off;
            self.loss_pct = 0.0;
            self.level_b = false;
        }
    }
    /// In plain words, what differs from another set of settings.
    pub fn changes(&self, other: &Settings) -> Vec<String> {
        let mut out = Vec::new();
        let mut note = |same: bool, text: String| {
            if !same {
                out.push(text);
            }
        };
        note(self.demand_pct == other.demand_pct, format!("demand {:.0}%", self.demand_pct));
        note(self.human_pct == other.human_pct, format!("humans {:.0}%", self.human_pct));
        note(self.model == other.model, format!("model {}", self.model.as_deref().unwrap_or("none")));
        note(self.dt == other.dt, format!("step {} s", self.dt));
        note(self.seed == other.seed, format!("seed {}", self.seed));
        note(self.teleports == other.teleports, format!("teleports {}", if self.teleports { "on" } else { "off" }));
        note(self.teleports && self.teleport_s == other.teleport_s, format!("teleport after {:.0} s", self.teleport_s));
        note(self.junctions == other.junctions, format!("junctions {:?}", self.junctions));
        note(self.plan == other.plan, format!("planning {}", self.plan.label()));
        note(self.loss_pct == other.loss_pct, format!("loss {:.0}%", self.loss_pct));
        note(self.level_b == other.level_b, format!("safety level {}", if self.level_b { "B" } else { "A" }));
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::registry::{Registry, custom};

    fn registry() -> Registry {
        Registry::parse(include_str!("../registry.toml")).unwrap()
    }

    #[test]
    fn human_only_is_the_default() {
        let r = registry();
        for s in &r.scenario {
            let d = Settings::for_scenario(s);
            assert!(d.human_only(&r), "{} does not start human-only", s.id);
            assert_eq!(d.model, None);
            assert_eq!(d.human_pct, 100.0);
        }
        assert!(Settings::for_scenario(&custom("a", "b", "")).human_only(&r));
    }

    #[test]
    fn coordinated_junctions_mean_every_car_automated() {
        let r = registry();
        let mut d = Settings::for_scenario(&r.scenario[0]);
        d.model = Some("d8".into());
        d.normalise(&r);
        assert_eq!(d.automated_share(&r), 1.0);
        assert_eq!(d.junctions, Junctions::SignalFree);
        d.model = Some("acc".into());
        d.human_pct = 75.0;
        d.normalise(&r);
        assert_eq!(d.automated_share(&r), 0.25);
        assert_eq!(d.junctions, Junctions::Normal);
    }

    #[test]
    fn changes_are_named() {
        let r = registry();
        let a = Settings::for_scenario(&r.scenario[0]);
        let mut b = a.clone();
        assert!(a.changes(&b).is_empty());
        b.seed = 3;
        b.demand_pct = 50.0;
        assert_eq!(b.changes(&a), vec!["demand 50%".to_string(), "seed 3".to_string()]);
    }
}
