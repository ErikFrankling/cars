//! Loads a scenario on its own thread, so the window stays alive and can say how far it got.
use crate::registry::{Registry, Roots, Scenario};
use crate::settings::{Junctions, Plan, Settings};
use cars_core::{
    Gpu,
    coord::{self, CoordConfig, Select},
    demand::{Demand, Trip},
    net::{JunctionRow, Net},
    render::Renderer,
    sim::Sim,
    world::{self, Replica, SimConfig, World},
};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex};
use std::time::Instant;

pub const STAGES: usize = 6;

#[derive(Clone, Debug)]
pub struct Progress {
    pub stage: String,
    pub done: usize,
}

pub struct Loaded {
    pub scenario: Scenario,
    pub settings: Settings,
    pub net: Arc<Net>,
    pub world: World,
    pub sim: Sim,
    pub renderer: Renderer,
    pub junctions: Vec<JunctionRow>,
    /// Trip id for each GPU trip, as the demand files name it.
    pub trip_names: Vec<String>,
    pub vtype_names: Vec<String>,
    /// What each type's colour means in the vehicle type view: (class, name).
    pub legend: Vec<(u32, String)>,
    pub widths: Vec<f32>,
    pub seconds: f64,
    pub notes: Vec<String>,
}

pub enum Message {
    /// The CPU side is ready. The window drops the old simulation and answers, so two never share the card.
    NeedGpu,
    Done(Box<Loaded>),
    /// The text to show. `override_ok` means the user may insist.
    Failed { text: String, override_ok: bool },
}

pub struct Job {
    pub rx: Receiver<Message>,
    pub go: Sender<()>,
    pub progress: Arc<Mutex<Progress>>,
    pub cancel: Arc<AtomicBool>,
    pub started: Instant,
    pub name: String,
}

pub struct Request {
    pub scenario: Scenario,
    pub settings: Settings,
    pub model_vtype: Option<String>,
    pub model_class: u32,
    pub model_name: String,
    pub coordinated: bool,
    pub share: f32,
    pub force: bool,
    pub present: wgpu::TextureFormat,
    pub view: (u32, u32),
    pub cache: PathBuf,
    pub repo: PathBuf,
    pub net_path: PathBuf,
    pub routes: Vec<PathBuf>,
    pub additional: Vec<PathBuf>,
    pub generate: Option<String>,
}

impl Request {
    pub fn new(reg: &Registry, roots: &Roots, scenario: &Scenario, settings: &Settings, present: wgpu::TextureFormat, view: (u32, u32), force: bool) -> Self {
        let id = &scenario.id;
        let model = settings.model.as_deref().and_then(|m| reg.model(m));
        let model_class = settings.model.as_deref().and_then(|m| reg.model.iter().position(|x| x.id == m)).unwrap_or(0) as u32;
        Self {
            scenario: scenario.clone(),
            settings: settings.clone(),
            model_vtype: model.filter(|_| settings.automated_share(reg) > 0.0).map(|m| m.vtype.clone()),
            model_class,
            model_name: model.map_or(String::new(), |m| m.name.clone()),
            coordinated: settings.coordinated(reg),
            share: settings.automated_share(reg),
            force,
            present,
            view,
            cache: roots.cache.join(id),
            repo: roots.repo.clone(),
            net_path: roots.path(id, &scenario.net),
            routes: scenario.routes.iter().map(|p| roots.path(id, p)).collect(),
            additional: scenario.additional.iter().map(|p| roots.path(id, p)).collect(),
            generate: scenario.generate.as_ref().map(|g| roots.expand(id, g)),
        }
    }
}

fn missing(r: &Request) -> Vec<PathBuf> {
    std::iter::once(&r.net_path).chain(&r.routes).chain(&r.additional).filter(|p| !p.exists()).cloned().collect()
}

fn generate(r: &Request) -> Result<(), String> {
    let Some(cmd) = &r.generate else { return Ok(()) };
    std::fs::create_dir_all(&r.cache).map_err(|e| format!("{}: {e}", r.cache.display()))?;
    let mut parts = cmd.split_whitespace();
    let program = parts.next().ok_or("empty generate command")?;
    let out = std::process::Command::new(program)
        .args(parts)
        .arg(&r.cache)
        .current_dir(&r.repo)
        .output()
        .map_err(|e| format!("could not run `{cmd}`: {e}. Start the app with scripts/cars-gui.sh, which brings python3 and netconvert."))?;
    if !out.status.success() {
        let tail: String = String::from_utf8_lossy(&out.stderr).lines().rev().take(12).collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>().join("\n");
        return Err(format!("`{cmd}` failed:\n{tail}"));
    }
    Ok(())
}

fn meminfo_available() -> Option<u64> {
    let text = std::fs::read_to_string("/proc/meminfo").ok()?;
    let line = text.lines().find(|l| l.starts_with("MemAvailable:"))?;
    Some(line.split_whitespace().nth(1)?.parse::<u64>().ok()? * 1024)
}

/// VRAM used and total on the biggest card, from the kernel. None where it does not say.
pub fn vram() -> Option<(u64, u64)> {
    let mut best = None;
    for e in std::fs::read_dir("/sys/class/drm").ok()?.flatten() {
        let d = e.path().join("device");
        let read = |name: &str| std::fs::read_to_string(d.join(name)).ok()?.trim().parse::<u64>().ok();
        if let (Some(u), Some(t)) = (read("mem_info_vram_used"), read("mem_info_vram_total"))
            && best.is_none_or(|(_, b)| t > b)
        {
            best = Some((u, t));
        }
    }
    best
}

fn gb(b: u64) -> f64 {
    b as f64 / 1e9
}

const VRAM_SPARE: u64 = 3_000_000_000;
const RAM_SPARE: u64 = 1_000_000_000;

/// RAM the load will reach at its peak, a rough guess from the size of the files. Measured peaks:
/// Stockholm 1.2 GB (200 MB net, 14 MB routes), its old demand 1.8 GB (203, 30), Berlin to noon
/// 2.5 GB (170, 399). The last two gzipped.
fn ram_needed(r: &Request) -> u64 {
    let size = |p: &Path| std::fs::metadata(p).map_or(0, |m| m.len());
    let file = |p: &Path| if p.extension().is_some_and(|e| e == "gz") { size(p) * 5 } else { size(p) * 6 };
    file(&r.net_path) + r.routes.iter().map(|p| file(p)).sum::<u64>() + r.additional.iter().map(|p| file(p)).sum::<u64>()
}

fn vram_needed(w: &World, view: (u32, u32)) -> u64 {
    let p = w.params;
    let cap = p.capacity.max(1) as u64;
    let veh = std::mem::size_of::<world::GpuVeh>() as u64;
    cap * (2 * veh + 16 + world::MAX_ITEMS * world::ITEM_BYTES + world::LCPLAN_BYTES + 48)
        + p.n_links as u64 * world::SLOTS * world::APPROACH_BYTES
        + p.n_lanes as u64 * (world::SEG_BYTES + 16 + 12 + 256)
        + p.n_trips as u64 * (std::mem::size_of::<world::GpuTrip>() as u64 + std::mem::size_of::<world::GpuTripOut>() as u64 + 64 + 8)
        + (w.routes.len() as u64) * 8
        + w.shapes.len() as u64 * 32
        + view.0 as u64 * view.1 as u64 * (8 * 4 + 8 + 4)
        + 400_000_000
}

struct Splitmix(u64);
impl Splitmix {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }
    fn unit(&mut self) -> f64 {
        (self.next() >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// Change the demand by a percentage: a kept subset below 100, and copies at the same moment above,
/// as SUMO's --scale does. The same seed keeps the same trips, and a smaller scale keeps a subset.
pub fn scale_trips(trips: &[Trip], ids: &mut Vec<String>, pct: f32, seed: u64) -> Vec<Trip> {
    if (pct - 100.0).abs() < 1e-3 {
        return trips.to_vec();
    }
    let scale = (pct as f64 / 100.0).max(0.0);
    let mut rng = Splitmix(seed.wrapping_mul(0x9E37_79B9).wrapping_add(17));
    let mut out = Vec::with_capacity((trips.len() as f64 * scale) as usize + 1);
    for t in trips {
        let u = rng.unit();
        let copies = scale.floor() as u32 + u32::from(u < scale.fract());
        for c in 0..copies {
            let mut x = t.clone();
            if c > 0 {
                x.id = ids.len() as u32;
                let name = format!("{}.copy{c}", ids[t.id as usize]);
                ids.push(name);
            }
            out.push(x);
        }
    }
    out
}

/// Which trips drive the automated model. Only cars: buses and lorries stay as they are.
pub fn assign_automated(trips: &[Trip], vtypes: &[u32], passenger: u32, av: u32, share: f32, seed: u64) -> Vec<u32> {
    let mut rng = Splitmix(seed.wrapping_mul(7919) ^ 0x5eed);
    trips
        .iter()
        .map(|t| {
            let u = rng.unit();
            if vtypes[t.vtype as usize] & passenger != 0 && u < share as f64 { av } else { t.vtype }
        })
        .collect()
}

fn coord_config(r: &Request) -> Result<Option<CoordConfig>, String> {
    if !r.coordinated {
        return Ok(None);
    }
    let sel = r.scenario.coordinated.as_str();
    let select = if sel == "all" {
        Select::All
    } else if let Some(b) = sel.strip_prefix("box:") {
        let v: Vec<f32> = b.split(',').filter_map(|x| x.parse().ok()).collect();
        if v.len() != 4 {
            return Err(format!("{}: coordinated box needs x0,y0,x1,y1", r.scenario.id));
        }
        Select::Box([v[0], v[1], v[2], v[3]])
    } else {
        Select::Ids(sel.split(',').map(String::from).collect())
    };
    let s = &r.settings;
    Ok(Some(CoordConfig {
        select,
        mode: if s.junctions == Junctions::Baseline { coord::MODE_SIGNAL } else { coord::MODE_FREE },
        level_b: s.level_b,
        p_loss: s.loss_pct / 100.0,
        plan: match s.plan {
            Plan::Off => 0,
            Plan::Full => coord::PLAN_PROFILE | coord::PLAN_STABLE | coord::PLAN_FOLLOW,
            Plan::Route => coord::PLAN_PROFILE | coord::PLAN_STABLE | coord::PLAN_FOLLOW | coord::PLAN_ROUTE,
        },
        ..Default::default()
    }))
}

struct Failure {
    text: String,
    override_ok: bool,
}
impl From<&str> for Failure {
    fn from(text: &str) -> Self {
        Self { text: text.to_string(), override_ok: false }
    }
}
impl From<String> for Failure {
    fn from(text: String) -> Self {
        Self { text, override_ok: false }
    }
}

fn run(r: Request, gpu: &Gpu, tx: &Sender<Message>, go: &Receiver<()>, progress: &Mutex<Progress>, cancel: &AtomicBool) -> Result<Option<Box<Loaded>>, Failure> {
    let t0 = Instant::now();
    let stage = |done: usize, text: &str| {
        if let Ok(mut p) = progress.lock() {
            *p = Progress { stage: text.to_string(), done };
        }
        !cancel.load(Ordering::Relaxed)
    };
    if !missing(&r).is_empty() && r.generate.is_some() {
        stage(0, "Building the road");
        generate(&r)?;
    }
    let lost = missing(&r);
    if !lost.is_empty() {
        let list: Vec<String> = lost.iter().map(|p| format!("  {}", p.display())).collect();
        return Err(format!("{} can't load, because these files are missing:\n{}", r.scenario.name, list.join("\n")).into());
    }
    let needed = ram_needed(&r);
    if !r.force && let Some(free) = meminfo_available() && free < needed + RAM_SPARE {
        return Err(Failure {
            text: format!("{} needs about {:.1} GB of RAM to load and {:.1} GB is free. Loading it now could get something killed.", r.scenario.name, gb(needed), gb(free)),
            override_ok: true,
        });
    }
    if !stage(1, "Reading the road network") {
        return Ok(None);
    }
    let mut net = Net::load(&r.net_path).map_err(|e| format!("{}: {e}", r.net_path.display()))?;
    for p in &r.additional {
        net.load_additional(p).map_err(|e| format!("{}: {e}", p.display()))?;
    }
    if !stage(2, "Reading the demand") {
        return Ok(None);
    }
    let s = &r.settings;
    let mut demand = Demand::load(&net, &r.routes, &r.additional, s.seed, Some(r.scenario.end as f64))?;
    let mut notes = Vec::new();
    let dropped = &demand.dropped;
    let lost_trips = dropped.unknown_edge + dropped.unconnected + dropped.banned_connection + dropped.unknown_route + dropped.unknown_vtype + dropped.taz + dropped.unsupported_depart;
    if lost_trips > 0 {
        notes.push(format!("{lost_trips} trips in the demand files can't be driven on this net and were left out."));
    }
    let mut av_type = None;
    if let Some(xml) = &r.model_vtype {
        std::fs::create_dir_all(&r.cache).map_err(|e| format!("{}: {e}", r.cache.display()))?;
        let file = r.cache.join("model.rou.xml");
        std::fs::write(&file, format!("<routes>{xml}</routes>")).map_err(|e| format!("{}: {e}", file.display()))?;
        let one = Demand::load(&net, &[file], &[], 0, None)?;
        let index = *one.vtype_index.get("gui_av").ok_or("the model's vtype must have id=\"gui_av\"")?;
        demand.vtypes.push(one.vtypes[index as usize].clone());
        let at = demand.vtypes.len() as u32 - 1;
        demand.vtype_index.insert("gui_av".into(), at);
        av_type = Some(at);
    }
    let trips = scale_trips(&demand.trips, &mut demand.ids, s.demand_pct, s.seed);
    demand.trips = trips;
    if !stage(3, "Building the world") {
        return Ok(None);
    }
    let classes: Vec<u32> = demand.vtypes.iter().map(|t| t.vclass).collect();
    let passenger = cars_core::net::vclass_bit("passenger");
    let share = r.share;
    let replicas: Vec<Replica> = match av_type {
        Some(av) if share > 0.0 => vec![Replica { seed: s.seed, trip_vtype: assign_automated(&demand.trips, &classes, passenger, av, share, s.seed), label: String::new() }],
        _ => Vec::new(),
    };
    let capacity = if s.demand_pct > 100.0 { (r.scenario.capacity as f32 * s.demand_pct / 100.0).ceil() as u32 } else { r.scenario.capacity };
    let cfg = SimConfig {
        dt: s.dt,
        begin_seconds: r.scenario.begin,
        end_seconds: r.scenario.end,
        seed: s.seed,
        capacity,
        time_to_teleport: if s.teleports { s.teleport_s } else { 0.0 },
        ignore_blocker: if s.physical() { 1e9 } else { r.scenario.ignore_blocker },
        mu: if s.physical() { 0.85 } else { 0.0 },
        detect_every: if s.physical() { 1 } else { 0 },
        per_lane_queues: r.coordinated,
        coord: coord_config(&r)?,
        ..Default::default()
    };
    let mut world = World::build(&net, &demand, &cfg, &replicas);
    if let Some(c) = &world.coord {
        if !c.refused.is_empty() {
            notes.push(format!("{} of {} junctions stay on normal rules: the coordinator refused them.", c.refused.len(), c.refused.len() + c.junctions.len()));
        }
        if c.junctions.is_empty() {
            return Err(format!("The coordinator took none of the junctions in {}.", r.scenario.name).into());
        }
    }
    if world.params.n_trips == 0 {
        notes.push("No trips fall in this scenario's time window.".to_string());
    }
    let need = vram_needed(&world, r.view);
    if !r.force && let Some((used, total)) = vram() && total.saturating_sub(used) < need + VRAM_SPARE {
        return Err(Failure {
            text: format!(
                "{} needs about {:.1} GB of graphics memory and {:.1} GB is free. That would leave less than the 3 GB the desktop needs.",
                r.scenario.name,
                gb(need),
                gb(total.saturating_sub(used))
            ),
            override_ok: true,
        });
    }
    let widths: Vec<f32> = demand.vtypes.iter().map(|t| t.width).collect();
    let vtype_names: Vec<String> = demand.vtypes.iter().map(|t| t.id.clone()).collect();
    let trip_names: Vec<String> = world.trip_source.iter().map(|&src| demand.ids[demand.trips[src as usize].id as usize].clone()).collect();
    let class_of = |i: usize| -> u32 {
        if Some(i as u32) == av_type {
            2 + r.model_class % 6
        } else if classes[i] & passenger != 0 || classes[i] == 0 {
            0
        } else {
            1
        }
    };
    let legend: Vec<(u32, String)> = {
        let mut used = rustc_hash::FxHashSet::default();
        for t in world.trips.iter().take(200_000) {
            used.insert(t.vtype);
        }
        let mut l: Vec<(u32, String)> = Vec::new();
        for i in 0..vtype_names.len() {
            let c = class_of(i);
            if used.contains(&(i as u32)) && !l.iter().any(|x| x.0 == c) {
                l.push((c, match c { 0 => "human car".to_string(), 1 => "bus, lorry and others".to_string(), _ => format!("automated: {}", r.model_name) }));
            }
        }
        l
    };
    drop(demand);
    let class_values: Vec<f32> = (0..vtype_names.len()).map(|i| class_of(i) as f32).collect();
    let junctions = net.junction_rows();
    let net = Arc::new(net);
    if !stage(4, "Waiting for the graphics card") {
        return Ok(None);
    }
    tx.send(Message::NeedGpu).map_err(|_| "the window went away".to_string())?;
    if go.recv().is_err() {
        return Ok(None);
    }
    stage(5, "Setting up the graphics card");
    let scope = gpu.device.push_error_scope(wgpu::ErrorFilter::OutOfMemory);
    let sim = Sim::new(gpu, &world)?;
    let mut renderer = Renderer::new(gpu, &world, &net, &widths, r.view.0.max(2), r.view.1.max(2), false);
    renderer.enable_lods(gpu, &net);
    renderer.set_present_format(gpu, r.present);
    renderer.set_type_classes(gpu, &class_values);
    if let Some(e) = pollster::block_on(scope.pop()) {
        return Err(format!("The graphics card ran out of memory: {e}").into());
    }
    world.shapes = Vec::new();
    Ok(Some(Box::new(Loaded {
        scenario: r.scenario,
        settings: r.settings,
        net,
        world,
        sim,
        renderer,
        junctions,
        trip_names,
        vtype_names,
        legend,
        widths,
        seconds: t0.elapsed().as_secs_f64(),
        notes,
    })))
}

pub fn start(req: Request, gpu: Arc<Gpu>, wake: impl Fn() + Send + 'static) -> Job {
    let (tx, rx) = channel();
    let (go_tx, go_rx) = channel();
    let progress = Arc::new(Mutex::new(Progress { stage: "Starting".into(), done: 0 }));
    let cancel = Arc::new(AtomicBool::new(false));
    let name = req.scenario.name.clone();
    let (p, c) = (progress.clone(), cancel.clone());
    let spawned = std::thread::Builder::new().name("load".into()).spawn(move || {
        // A panic deep in the loaders is a bad file, not a reason to take the window down.
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| run(req, &gpu, &tx, &go_rx, &p, &c)));
        let message = match result {
            Ok(Ok(Some(l))) => Some(Message::Done(l)),
            Ok(Ok(None)) => None,
            Ok(Err(f)) => Some(Message::Failed { text: f.text, override_ok: f.override_ok }),
            Err(panic) => {
                let why = panic.downcast_ref::<String>().cloned().or_else(|| panic.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or_else(|| "unknown".into());
                Some(Message::Failed { text: format!("Loading stopped with an internal error: {why}"), override_ok: false })
            }
        };
        if let Some(m) = message {
            let _ = tx.send(m);
        }
        wake();
    });
    if let Err(e) = spawned {
        eprintln!("could not start the loading thread: {e}");
    }
    Job { rx, go: go_tx, progress, cancel, started: Instant::now(), name }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cars_core::demand::{ArrivalPos, DepartLane, DepartPos, DepartSpeed};

    fn trips(n: usize) -> (Vec<Trip>, Vec<String>) {
        let t: Vec<Trip> = (0..n)
            .map(|i| Trip {
                id: i as u32,
                depart: i as f64,
                route: 0,
                vtype: 0,
                depart_lane: DepartLane::First,
                depart_pos: DepartPos::Base,
                depart_speed: DepartSpeed::Value(0.0),
                arrival_pos: ArrivalPos::Max,
            })
            .collect();
        (t, (0..n).map(|i| format!("t{i}")).collect())
    }

    #[test]
    fn full_demand_is_untouched() {
        let (t, mut ids) = trips(100);
        let out = scale_trips(&t, &mut ids, 100.0, 7);
        assert_eq!(out.len(), 100);
        assert_eq!(ids.len(), 100);
    }

    #[test]
    fn scale_is_close_and_repeatable() {
        let (t, mut ids) = trips(20_000);
        let half = scale_trips(&t, &mut ids, 50.0, 3);
        assert!((half.len() as i64 - 10_000).abs() < 400, "{}", half.len());
        let again = scale_trips(&t, &mut ids, 50.0, 3);
        assert_eq!(half.iter().map(|x| x.id).collect::<Vec<_>>(), again.iter().map(|x| x.id).collect::<Vec<_>>());
        let n0 = ids.len();
        let double = scale_trips(&t, &mut ids, 200.0, 3);
        assert_eq!(double.len(), 40_000);
        assert_eq!(ids.len(), n0 + 20_000);
    }

    #[test]
    fn share_of_automated_is_close_and_spares_lorries() {
        let (mut t, _) = trips(20_000);
        for x in t.iter_mut().step_by(4) {
            x.vtype = 1;
        }
        let out = assign_automated(&t, &[1, 2], 1, 9, 0.5, 11);
        assert!(out.iter().zip(&t).all(|(o, x)| x.vtype != 1 || *o == 1));
        let av = out.iter().filter(|&&o| o == 9).count();
        assert!((av as i64 - 7_500).abs() < 400, "{av}");
        assert!(assign_automated(&t, &[1, 2], 1, 9, 0.0, 11).iter().all(|&o| o != 9));
    }
}
