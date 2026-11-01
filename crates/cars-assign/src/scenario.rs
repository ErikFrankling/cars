//! `scenario.toml`: which files make a run, each named and hashed.

use std::io::Read;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

fn default_dt() -> f32 {
    1.0
}
fn default_share() -> f64 {
    0.15
}
fn default_memory() -> f32 {
    0.3
}
fn default_turnaround() -> f32 {
    crate::route::TURNAROUND_S
}
fn default_landmarks() -> usize {
    16
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Scenario {
    pub name: String,
    pub net: PathBuf,
    /// SUMO demand files: their ODs and departures are kept, their routes dropped unless `init = "given"`.
    #[serde(default)]
    pub routes: Vec<PathBuf>,
    /// Vehicle types and signal programs.
    #[serde(default)]
    pub additional: Vec<PathBuf>,
    /// Population instead of `routes`.
    pub travellers: Option<PathBuf>,
    /// Vehicle ids starting with one of these keep their route: bus lines.
    #[serde(default)]
    pub fixed_prefixes: Vec<String>,
    /// Vehicle types that keep their route.
    #[serde(default)]
    pub fixed_vtypes: Vec<String>,
    pub counts: Option<PathBuf>,
    /// Test rows stay out of everything until `eval --open-test`, which works once.
    #[serde(default)]
    pub blind_test: bool,
    /// Count WAPE between comparable days at the same sites, from real data.
    pub noise_floor: Option<f64>,
    pub cuts: Option<PathBuf>,
    pub discharge: Option<PathBuf>,
    #[serde(default)]
    pub begin: f32,
    /// Last departure kept.
    pub end: f32,
    /// Clearance horizon. Demand end plus two hours, or 26 h for a day.
    pub horizon: f32,
    #[serde(default = "default_dt")]
    pub dt: f32,
    #[serde(default)]
    pub seed: u64,
    /// Most vehicles on the road at once, per replica.
    pub capacity: u32,
    /// Labelled diagnostics only. A counted run leaves these off.
    #[serde(default)]
    pub time_to_teleport: f32,
    pub ignore_blocker: Option<f32>,
    #[serde(default = "default_share")]
    pub share: f64,
    #[serde(default = "default_memory")]
    pub memory: f32,
    #[serde(default = "default_landmarks")]
    pub landmarks: usize,
    /// Seconds added to a turn back onto the opposite edge.
    #[serde(default = "default_turnaround")]
    pub turnaround_s: f32,
    #[serde(default)]
    pub init: String,
    /// Zones for OD cells and cut bisections.
    pub zones: Option<usize>,
    /// Run the kernels with bounds checks off.
    #[serde(default)]
    pub trusted: bool,
}

impl Scenario {
    pub fn load(path: &Path) -> Result<Self, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
        toml::from_str(&text).map_err(|e| format!("{}: {e}", path.display()))
    }

    pub fn n_bins(&self) -> usize {
        (self.horizon / crate::costs::BIN_S).ceil() as usize
    }

    pub fn counted(&self) -> bool {
        self.time_to_teleport == 0.0 && self.ignore_blocker.is_none()
    }

    /// Input files and their SHA-256.
    pub fn manifest(&self) -> serde_json::Value {
        let mut files: Vec<&PathBuf> = vec![&self.net];
        files.extend(&self.routes);
        files.extend(&self.additional);
        files.extend(self.travellers.iter());
        files.extend(self.counts.iter());
        files.extend(self.cuts.iter());
        files.extend(self.discharge.iter());
        let hashed: Vec<_> = files
            .iter()
            .map(|p| {
                let mut h = Sha256::new();
                let mut buf = vec![0u8; 1 << 20];
                let mut size = 0u64;
                if let Ok(mut f) = std::fs::File::open(p) {
                    while let Ok(n) = f.read(&mut buf) {
                        if n == 0 {
                            break;
                        }
                        h.update(&buf[..n]);
                        size += n as u64;
                    }
                }
                let digest: String = h.finalize().iter().map(|b| format!("{b:02x}")).collect();
                serde_json::json!({"path": p, "bytes": size, "sha256": digest})
            })
            .collect();
        serde_json::json!({"scenario": self, "files": hashed})
    }
}
