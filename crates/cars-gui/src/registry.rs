//! Scenarios and models offered by the app, read from registry.toml.
use serde::Deserialize;
use std::path::{Path, PathBuf};

const BUILT_IN: &str = include_str!("../registry.toml");

/// How far a scenario can be trusted, from research/truth/VALIDATION-GATE.md. Required on every
/// entry, so nothing reaches the picker without one.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Trust {
    MatchesRealDay,
    PartlyChecked,
    NotChecked,
    SpeedBenchmark,
}
impl Trust {
    pub fn label(self) -> &'static str {
        match self {
            Trust::MatchesRealDay => "matches a real day",
            Trust::PartlyChecked => "partly checked",
            Trust::NotChecked => "not checked against reality",
            Trust::SpeedBenchmark => "speed benchmark only",
        }
    }
    pub fn color(self) -> [u8; 3] {
        match self {
            Trust::MatchesRealDay => [90, 210, 120],
            Trust::PartlyChecked => [235, 200, 90],
            Trust::NotChecked => [240, 150, 90],
            Trust::SpeedBenchmark => [165, 170, 185],
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct Scenario {
    pub id: String,
    pub name: String,
    pub group: String,
    pub description: String,
    pub trust: Trust,
    #[serde(default)]
    pub trust_note: String,
    #[serde(default)]
    pub generate: Option<String>,
    pub net: String,
    #[serde(default)]
    pub routes: Vec<String>,
    #[serde(default)]
    pub additional: Vec<String>,
    #[serde(default = "default_dt")]
    pub dt: f32,
    #[serde(default)]
    pub begin: f32,
    #[serde(default = "default_end")]
    pub end: f32,
    #[serde(default)]
    pub capacity: u32,
    #[serde(default = "default_teleport")]
    pub time_to_teleport: f32,
    #[serde(default = "default_blocker")]
    pub ignore_blocker: f32,
    /// Starting simulated seconds per real second.
    #[serde(default = "default_speed")]
    pub speed: f32,
    /// Which junctions the coordinator runs: `all`, `box:x0,y0,x1,y1` or ids separated by commas.
    #[serde(default = "default_coordinated")]
    pub coordinated: String,
}
fn default_dt() -> f32 {
    1.0
}
fn default_end() -> f32 {
    3600.0
}
fn default_teleport() -> f32 {
    300.0
}
fn default_blocker() -> f32 {
    1e9
}
fn default_speed() -> f32 {
    1.0
}
fn default_coordinated() -> String {
    "all".into()
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Merged,
    NotMerged,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Model {
    pub id: String,
    pub name: String,
    pub description: String,
    pub status: Status,
    #[serde(default)]
    pub branch: String,
    #[serde(default)]
    pub vtype: String,
    #[serde(default)]
    pub coordinated: bool,
}

#[derive(Clone, Debug, Default, Deserialize)]
pub struct Registry {
    #[serde(default)]
    pub scenario: Vec<Scenario>,
    #[serde(default)]
    pub model: Vec<Model>,
}

/// Where things live. Environment variables override the defaults.
pub struct Roots {
    pub repo: PathBuf,
    pub data: PathBuf,
    pub thesis: PathBuf,
    pub cache: PathBuf,
}
impl Roots {
    pub fn find() -> Self {
        let var = |name: &str, default: PathBuf| std::env::var_os(name).map(PathBuf::from).unwrap_or(default);
        let home = PathBuf::from(std::env::var_os("HOME").unwrap_or_default());
        let repo = var("CARS_GUI_ROOT", Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."));
        let cache = std::env::var_os("XDG_CACHE_HOME").map(PathBuf::from).unwrap_or(home.join(".cache")).join("cars-gui");
        Self {
            repo,
            data: var("CARS_DATA", home.join("projects/personal/cars-data")),
            thesis: var("CARS_THESIS", home.join("projects/personal/thesis-src/bachelor/config")),
            cache,
        }
    }
    pub fn expand(&self, scenario: &str, text: &str) -> String {
        text.replace("$REPO", &self.repo.to_string_lossy())
            .replace("$DATA", &self.data.to_string_lossy())
            .replace("$THESIS", &self.thesis.to_string_lossy())
            .replace("$CACHE", &self.cache.join(scenario).to_string_lossy())
    }
    pub fn path(&self, scenario: &str, text: &str) -> PathBuf {
        PathBuf::from(self.expand(scenario, text))
    }
}

impl Registry {
    pub fn parse(text: &str) -> Result<Self, String> {
        let r: Registry = toml::from_str(text).map_err(|e| e.to_string())?;
        for m in &r.model {
            if m.status == Status::Merged && m.vtype.is_empty() {
                return Err(format!("model {} is merged but has no vtype", m.id));
            }
        }
        Ok(r)
    }
    /// The registry next to the code, so an edit needs no rebuild. A broken file falls back on the
    /// built-in one, and the problem is returned for the window to show.
    pub fn load(roots: &Roots) -> (Self, Option<String>) {
        let path = roots.repo.join("crates/cars-gui/registry.toml");
        match std::fs::read_to_string(&path) {
            Ok(text) => match Self::parse(&text) {
                Ok(r) => (r, None),
                Err(e) => (Self::parse(BUILT_IN).unwrap_or_default(), Some(format!("{}: {e}. Using the built-in list.", path.display()))),
            },
            Err(_) => (Self::parse(BUILT_IN).unwrap_or_default(), None),
        }
    }
    pub fn scenario(&self, id: &str) -> Option<&Scenario> {
        self.scenario.iter().find(|s| s.id == id)
    }
    pub fn model(&self, id: &str) -> Option<&Model> {
        self.model.iter().find(|m| m.id == id)
    }
    pub fn groups(&self) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();
        for s in &self.scenario {
            if !out.contains(&s.group) {
                out.push(s.group.clone());
            }
        }
        out
    }
}

/// A scenario for any net and route files the user picks. Nothing is known about it.
pub fn custom(net: &str, routes: &str, additional: &str) -> Scenario {
    let split = |s: &str| s.split(',').map(str::trim).filter(|x| !x.is_empty()).map(String::from).collect();
    let stem = Path::new(net).file_stem().map(|s| s.to_string_lossy().replace(".net", "")).unwrap_or_default();
    Scenario {
        id: "custom".into(),
        name: format!("Opened: {stem}"),
        group: "Opened".into(),
        description: net.into(),
        trust: Trust::NotChecked,
        trust_note: "An opened file: nothing is known about it.".into(),
        generate: None,
        net: net.into(),
        routes: split(routes),
        additional: split(additional),
        dt: 1.0,
        begin: 0.0,
        end: 3600.0,
        capacity: 0,
        time_to_teleport: 300.0,
        ignore_blocker: 1e9,
        speed: 1.0,
        coordinated: "all".into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn built_in() -> Registry {
        Registry::parse(BUILT_IN).expect("registry.toml parses")
    }

    #[test]
    fn every_asked_for_scenario_is_there() {
        let r = built_in();
        for id in ["phantom-jam", "one-av-ring", "lane-drop", "on-ramp", "zipper", "roundabout", "signal-junction", "priority-junction", "d8-j1", "d8-grid1", "bologna", "lust", "berlin", "charlottenburg", "mitte", "stockholm-old", "stockholm-new"] {
            assert!(r.scenario(id).is_some(), "{id} is missing");
        }
    }

    #[test]
    fn nothing_claims_more_trust_than_the_gate_allows() {
        for s in built_in().scenario {
            assert!(matches!(s.trust, Trust::NotChecked | Trust::SpeedBenchmark), "{} claims {:?}", s.id, s.trust);
            assert!(!s.trust_note.is_empty(), "{} says nothing about why", s.id);
        }
    }

    #[test]
    fn a_scenario_without_a_trust_label_is_refused() {
        let text = "[[scenario]]\nid=\"x\"\nname=\"x\"\ngroup=\"x\"\ndescription=\"x\"\nnet=\"x\"\n";
        assert!(Registry::parse(text).is_err());
    }

    #[test]
    fn unmerged_models_say_where_they_are() {
        let r = built_in();
        for id in ["d1-d7", "m1", "physical", "human"] {
            let m = r.model(id).expect(id);
            assert_eq!(m.status, Status::NotMerged);
            assert!(m.branch.starts_with("t3/"));
        }
        for id in ["krauss", "idm", "acc", "cacc", "glosa", "d8"] {
            assert_eq!(r.model(id).expect(id).status, Status::Merged);
        }
    }

    #[test]
    fn paths_expand() {
        let roots = Roots { repo: "/r".into(), data: "/d".into(), thesis: "/t".into(), cache: "/c".into() };
        assert_eq!(roots.expand("ring", "$CACHE/net.xml"), "/c/ring/net.xml");
        assert_eq!(roots.expand("x", "$DATA/a $REPO/b $THESIS/c"), "/d/a /r/b /t/c");
    }
}
