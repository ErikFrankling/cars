use crate::overlay::{self, Canvas, Hud, Overlay, Snapshot};
use cars_core::{
    Gpu, GpuOptions,
    demand::Demand,
    net::Net,
    render::{Camera, Renderer},
    sim::Sim,
    world::{SimConfig, World},
};
use clap::Parser;
use serde::Deserialize;
use std::{
    io::Write,
    path::{Path, PathBuf},
    process::{Command, Stdio},
};
#[derive(Parser)]
pub struct Args {
    #[arg(long)]
    net: PathBuf,
    /// Centre on this junction, at a zoom that fits it unless --metres-per-pixel says otherwise.
    #[arg(long)]
    junction: Option<String>,
    /// Follow this trip or flow vehicle id.
    #[arg(long)]
    follow: Option<String>,
    #[arg(long)]
    metres_per_pixel: Option<f32>,
    /// One simulated second per video second, interpolating between steps. Close cameras
    /// do this unless --steps-per-frame is given.
    #[arg(long)]
    realtime: bool,
    /// Simulated seconds per video second, for slow motion or a faster look.
    #[arg(long, default_value_t = 1.0)]
    speed: f32,
    /// Show steps as they are, instead of interpolating between them.
    #[arg(long)]
    raw_steps: bool,
    /// Simulation times of stills. With `cars shot` these are the point of the run.
    #[arg(long, value_delimiter = ',')]
    at: Vec<f32>,
    #[arg(long,value_delimiter=',',value_parser=["all","leader","braking","speed","state","foes","events"])]
    overlay: Vec<String>,
    /// JSON with many cameras over one simulation run, see RECORDING.md. Replaces --out.
    #[arg(long)]
    views: Option<PathBuf>,
    #[arg(long,num_args=1..,value_delimiter=',')]
    routes: Vec<PathBuf>,
    #[arg(long, value_delimiter = ',')]
    additional: Vec<PathBuf>,
    #[arg(long, default_value_t = 1.0)]
    dt: f32,
    #[arg(long, default_value_t = 0.0)]
    begin: f32,
    #[arg(long, default_value_t = 3600.0)]
    end: f32,
    #[arg(long, default_value_t = 0)]
    seed: u64,
    #[arg(long, default_value_t = 0)]
    capacity: u32,
    #[arg(long, default_value_t = 300.0)]
    time_to_teleport: f32,
    #[arg(long, default_value_t = 1e9)]
    ignore_junction_blocker: f32,
    #[arg(long)]
    steps_per_frame: Option<u32>,
    #[arg(long, default_value_t = 30)]
    fps: u32,
    #[arg(long, default_value_t = 1920)]
    width: u32,
    #[arg(long, default_value_t = 1080)]
    height: u32,
    #[arg(long)]
    camera: Option<PathBuf>,
    #[arg(long)]
    fit: bool,
    #[arg(long)]
    out: Option<PathBuf>,
    #[arg(long, default_value = "")]
    title: String,
    #[arg(long, default_value = "")]
    subtitle: String,
    /// Colour by speed, type, waiting time, or give each car its own paint.
    #[arg(long,value_parser=["speed","type","wait","paint"])]
    color: Option<String>,
    /// Where the simulation starts; the part before --begin runs without rendering.
    #[arg(long, default_value_t = 0.0)]
    sim_begin: f32,
}
#[derive(Deserialize, Default)]
struct Script {
    #[serde(default)]
    keyframes: Vec<Key>,
    #[serde(default)]
    captions: Vec<Caption>,
}
#[derive(Deserialize)]
struct Key {
    #[serde(default)]
    time: Option<f32>,
    #[serde(default)]
    frame: Option<u32>,
    center: [f32; 2],
    #[serde(alias = "mpp")]
    metres_per_pixel: f32,
}
#[derive(Deserialize)]
struct Caption {
    from: f32,
    to: f32,
    text: String,
}
#[derive(Deserialize, Default, Clone)]
struct ViewSpec {
    /// Video file. Leave out for stills only.
    #[serde(default)]
    out: Option<PathBuf>,
    /// One PNG per time in `shots`. `name.png` becomes `name-<time>.png` when there are several.
    #[serde(default)]
    png: Option<PathBuf>,
    #[serde(default)]
    shots: Vec<f32>,
    #[serde(default)]
    junction: Option<String>,
    #[serde(default)]
    follow: Option<String>,
    #[serde(default)]
    center: Option<[f32; 2]>,
    #[serde(default, alias = "mpp")]
    metres_per_pixel: Option<f32>,
    #[serde(default)]
    overlay: Vec<String>,
    #[serde(default)]
    title: String,
    #[serde(default)]
    subtitle: String,
}
#[derive(Deserialize)]
struct ViewFile {
    views: Vec<ViewSpec>,
}
fn ass_text(s: &str) -> String {
    s.replace('\\', "／")
        .replace('{', "(")
        .replace('}', ")")
        .replace('\n', "\\N")
        .replace('\r', "")
}
fn stamp(seconds: f64) -> String {
    let t = (seconds * 100.0).round() as u64;
    format!(
        "{}:{:02}:{:02}.{:02}",
        t / 360000,
        t / 6000 % 60,
        t / 100 % 60,
        t % 100
    )
}
fn event(f: &mut impl Write, start: f64, end: f64, style: &str, text: &str) -> std::io::Result<()> {
    writeln!(
        f,
        "Dialogue: 0,{},{},{},,0,0,0,,{}",
        stamp(start),
        stamp(end),
        style,
        ass_text(text)
    )
}
struct Encoder(std::process::Child);
impl Drop for Encoder {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}
fn encoder(width: u32, height: u32, fps: u32, threads: u32, out: &Path) -> Result<Encoder, Box<dyn std::error::Error>> {
    let threads = threads.to_string();
    Ok(Encoder(
        Command::new("ffmpeg")
            .args(["-y", "-v", "error", "-threads", &threads, "-filter_threads", &threads, "-f", "rawvideo", "-pix_fmt", "rgba", "-s"])
            .arg(format!("{width}x{height}"))
            .args(["-r", &fps.to_string(), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast", "-threads", &threads, "-movflags", "+faststart"])
            .arg(out)
            .stdin(Stdio::piped())
            .spawn()?,
    ))
}
fn write_png(pixels: &[u8], width: u32, height: u32, out: &Path) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(p) = out.parent().filter(|p| !p.as_os_str().is_empty()) {
        std::fs::create_dir_all(p)?;
    }
    let mut child = Command::new("ffmpeg")
        .args(["-y", "-v", "error", "-threads", "1", "-filter_threads", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-s"])
        .arg(format!("{width}x{height}"))
        .args(["-i", "-", "-frames:v", "1", "-threads", "1", "-update", "1"])
        .arg(out)
        .stdin(Stdio::piped())
        .spawn()?;
    child.stdin.take().ok_or("png stdin")?.write_all(pixels)?;
    if !child.wait()?.success() {
        return Err("PNG writer failed".into());
    }
    Ok(())
}
enum Target {
    Fixed(Camera),
    Follow { trip: u32, mpp: f32, center: Option<[f32; 2]>, start: [f32; 2] },
    Script,
}
struct View {
    target: Target,
    out: Option<PathBuf>,
    partial: Option<PathBuf>,
    ffmpeg: Option<(Encoder, std::process::ChildStdin)>,
    shots: Vec<(f32, PathBuf)>,
    overlay: Vec<String>,
    state: Overlay,
    title: String,
    subtitle: String,
}
/// Centre and zoom that show a junction with its approaches on a 16:9 frame.
fn junction_camera(net: &Net, id: &str, height: u32, mpp: Option<f32>) -> Result<Camera, String> {
    let j = net
        .junction_index
        .get(id)
        .map(|&i| &net.junctions[i as usize])
        .ok_or_else(|| format!("unknown junction id {id}"))?;
    let mut radius = 0.0f32;
    for p in &j.shape {
        radius = radius.max((p[0] - j.x).hypot(p[1] - j.y));
    }
    Ok(Camera {
        center: [j.x, j.y],
        metres_per_pixel: mpp.unwrap_or(((radius * 2.0 + 75.0) / height as f32).clamp(0.05, 0.3)),
    })
}
fn trip_index(world: &World, demand: &Demand, id: &str) -> Result<u32, String> {
    let source = demand
        .trips
        .iter()
        .position(|t| demand.ids[t.id as usize] == id)
        .ok_or_else(|| format!("unknown follow trip {id}"))? as u32;
    world
        .trip_source
        .iter()
        .position(|&s| s == source)
        .map(|i| i as u32)
        .ok_or_else(|| format!("trip {id} is not in the simulated window"))
}
fn trip_start(net: &Net, world: &World, trip: u32) -> [f32; 2] {
    let t = &world.trips[trip as usize];
    let edge = world.routes[t.route_start as usize] as usize;
    net.lanes[world.edges[edge].first_lane as usize]
        .shape
        .first()
        .copied()
        .unwrap_or([0.0, 0.0])
}
fn shot_path(base: &Path, time: f32, many: bool) -> PathBuf {
    if !many {
        return base.to_path_buf();
    }
    let stem = base.file_stem().and_then(|s| s.to_str()).unwrap_or("shot");
    base.with_file_name(format!("{stem}-{time:.1}.png"))
}
pub fn run(mut a: Args, shot_only: bool) -> Result<(), Box<dyn std::error::Error>> {
    if !a.sim_begin.is_finite() || a.sim_begin < 0. || a.sim_begin > a.begin {
        return Err("sim-begin must be <= begin".into());
    }
    let mut specs: Vec<ViewSpec> = match &a.views {
        Some(p) => serde_json::from_slice::<ViewFile>(&std::fs::read(p)?)?.views,
        None => {
            let out = a.out.clone().ok_or("--out or --views required")?;
            let (video, png) = if shot_only { (None, Some(out)) } else if out.extension().is_some_and(|e| e == "png") { (None, Some(out)) } else { (Some(out), None) };
            vec![ViewSpec {
                out: video,
                png,
                shots: a.at.clone(),
                junction: a.junction.clone(),
                follow: a.follow.clone(),
                center: None,
                metres_per_pixel: a.metres_per_pixel,
                overlay: a.overlay.clone(),
                title: a.title.clone(),
                subtitle: a.subtitle.clone(),
            }]
        }
    };
    for s in &mut specs {
        if s.png.is_some() && s.shots.is_empty() {
            s.shots.push(a.begin);
        }
        s.shots.retain(|t| t.is_finite());
    }
    let videos = specs.iter().any(|s| s.out.is_some());
    let last_shot = specs.iter().flat_map(|s| s.shots.iter().copied()).fold(f32::MIN, f32::max);
    if !videos {
        if last_shot == f32::MIN {
            return Err("nothing to do: give --at".into());
        }
        a.end = last_shot + 2.0 * a.dt;
    }
    a.end = a.end.max(last_shot + 2.0 * a.dt);
    let spf = a.steps_per_frame.unwrap_or(1);
    let close = a.views.is_some() || a.junction.is_some() || a.follow.is_some() || !videos;
    if !close && a.title.is_empty() {
        a.title = "Traffic in motion".into();
    }
    // Close cameras watch in real time unless told how many steps to take per frame.
    let realtime = a.realtime || (close && a.steps_per_frame.is_none());
    let interpolate = realtime && !a.raw_steps;
    if !a.dt.is_finite()
        || a.dt <= 0.0
        || !a.begin.is_finite()
        || !a.end.is_finite()
        || a.begin < 0.0
        || a.end <= a.begin
        || spf == 0
        || a.fps == 0
        || a.width < 2
        || a.height < 2
        || a.width % 2 != 0
        || a.height % 2 != 0
        || a.width > 1920
        || a.height > 1920
        || !a.speed.is_finite()
        || a.speed <= 0.0
    {
        return Err("use positive dt/fps/steps/speed, end > begin >= 0, even dimensions up to 1920".into());
    }
    let mut script: Script = match &a.camera {
        Some(p) => serde_json::from_slice(&std::fs::read(p)?)?,
        None => Script::default(),
    };
    for k in &script.keyframes {
        if k.time.is_some() == k.frame.is_some()
            || !k.metres_per_pixel.is_finite()
            || k.metres_per_pixel <= 0.0
            || k.center.iter().any(|x| !x.is_finite())
            || k.time.is_some_and(|x| !x.is_finite())
        {
            return Err(
                "each keyframe needs time OR frame, finite center and positive metres_per_pixel"
                    .into(),
            );
        }
    }
    let seconds_per_frame = if realtime { a.speed / a.fps as f32 } else { a.dt * spf as f32 };
    let key_time = |k: &Key| k.time.unwrap_or(a.begin + k.frame.unwrap_or(0) as f32 * seconds_per_frame);
    script
        .keyframes
        .sort_by(|x, y| key_time(x).total_cmp(&key_time(y)));
    let mut net = Net::load(&a.net)?;
    for p in &a.additional {
        net.load_additional(p)?;
    }
    let mut demand = Demand::load(&net, &a.routes, &a.additional, a.seed, Some(a.end as f64))?;
    let mut world = World::build(
        &net,
        &demand,
        &SimConfig {
            dt: a.dt,
            begin_seconds: a.sim_begin,
            end_seconds: a.end,
            seed: a.seed,
            capacity: a.capacity,
            time_to_teleport: a.time_to_teleport,
            ignore_blocker: a.ignore_junction_blocker,
            ..Default::default()
        },
        &[],
    );
    let threads = if specs.iter().filter(|s| s.out.is_some()).count() > 1 { 1 } else { 2 };
    let mut views = Vec::new();
    let mut far_roads = false;
    for s in &specs {
        let target = if let Some(id) = &s.follow {
            let trip = trip_index(&world, &demand, id)?;
            let mpp = s.metres_per_pixel.unwrap_or(0.12);
            far_roads |= mpp > 0.35;
            Target::Follow { trip, mpp, center: None, start: trip_start(&net, &world, trip) }
        } else if let Some(id) = &s.junction {
            let cam = junction_camera(&net, id, a.height, s.metres_per_pixel)?;
            far_roads |= cam.metres_per_pixel > 0.35;
            Target::Fixed(cam)
        } else if let Some(center) = s.center {
            let mpp = s.metres_per_pixel.unwrap_or(0.12);
            far_roads |= mpp > 0.35;
            Target::Fixed(Camera { center, metres_per_pixel: mpp })
        } else {
            far_roads = true;
            Target::Script
        };
        let mut shots: Vec<(f32, PathBuf)> = match &s.png {
            Some(base) => s.shots.iter().map(|&t| (t, shot_path(base, t, s.shots.len() > 1))).collect(),
            None => Vec::new(),
        };
        shots.sort_by(|x, y| x.0.total_cmp(&y.0));
        views.push(View {
            target,
            out: s.out.clone(),
            partial: None,
            ffmpeg: None,
            shots,
            overlay: s.overlay.clone(),
            state: Overlay::default(),
            title: s.title.clone(),
            subtitle: s.subtitle.clone(),
        });
    }
    let widths: Vec<f32> = demand.vtypes.iter().map(|t| t.width).collect();
    demand.routes = Vec::new();
    let gpu = pollster::block_on(Gpu::headless(GpuOptions {
        adapter_name: Some("7900".into()),
        ..Default::default()
    }))?;
    let mut sim = Sim::new(&gpu, &world)?;
    let mut renderer = Renderer::new(&gpu, &world, &net, &widths, a.width, a.height, far_roads);
    world.shapes = Vec::new();
    let mode = match a.color.as_deref() {
        Some("type") => 1,
        Some("wait") => 2,
        Some("paint") => 3,
        Some("speed") => 0,
        _ => {
            if close {
                3
            } else {
                0
            }
        }
    };
    let start_step = ((a.begin - a.sim_begin) / a.dt).ceil() as u64;
    let end_step = ((a.end - a.sim_begin) / a.dt).ceil() as u64;
    // What each frame shows: display time, and the step it must have reached.
    let mut plan: Vec<(f32, u64, f32)> = Vec::new();
    let plan_time = |s: f32| {
        let rel = s - a.sim_begin;
        // FCD labels the state after step k with time (k-1)*dt, and frames must agree with it.
        let k = (rel / a.dt).ceil() as u64 + 1;
        let blend = if interpolate { ((rel - (k as f32 - 2.0) * a.dt) / a.dt).clamp(0.0, 1.0) } else { 1.0 };
        (s, k, blend)
    };
    if videos {
        if realtime {
            let n = ((a.end - a.begin) / a.speed * a.fps as f32).ceil() as u64;
            for f in 0..n {
                plan.push(plan_time(a.begin + f as f32 * a.speed / a.fps as f32));
            }
        } else {
            let n = end_step.saturating_sub(start_step).div_ceil(spf as u64);
            for f in 0..n {
                let k = (start_step + (f + 1) * spf as u64).min(end_step);
                plan.push((a.sim_begin + (k.saturating_sub(1)) as f32 * a.dt, k, 1.0));
            }
        }
    } else {
        let mut times: Vec<f32> = views.iter().flat_map(|v| v.shots.iter().map(|s| s.0)).collect();
        times.sort_by(f32::total_cmp);
        times.dedup();
        for t in times {
            plan.push(plan_time(t));
        }
    }
    if let Some(p) = a.out.as_ref().and_then(|o| o.parent()).filter(|p| !p.as_os_str().is_empty()) {
        std::fs::create_dir_all(p)?;
    }
    for v in &mut views {
        if let Some(out) = &v.out {
            if let Some(p) = out.parent().filter(|p| !p.as_os_str().is_empty()) {
                std::fs::create_dir_all(p)?;
            }
            let stem = out.file_stem().and_then(|s| s.to_str()).unwrap_or("clip");
            let partial = if close { out.with_file_name(format!("{stem}.partial.mp4")) } else { out.with_extension("silent.mp4") };
            let mut enc = encoder(a.width, a.height, a.fps, threads, &partial)?;
            let stdin = enc.0.stdin.take().ok_or("ffmpeg stdin")?;
            v.partial = Some(partial);
            v.ffmpeg = Some((enc, stdin));
        }
    }
    let duration = plan.len() as f64 / a.fps as f64;
    let mut subtitles = None;
    if !close && videos {
        let out = views[0].out.as_ref().ok_or("no video")?;
        let mut f = std::fs::File::create(out.with_extension("ass"))?;
        writeln!(
            f,
            "[Script Info]\nScriptType: v4.00+\nPlayResX: {}\nPlayResY: {}\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            a.width, a.height
        )?;
        let scale = a.height as f32 / 1080.0;
        for (name, size, bold, align, margin) in [
            ("Title", 38, -1, 7, 40),
            ("Subtitle", 24, 0, 7, 90),
            ("Caption", 24, 0, 1, 82),
            ("HUD", 22, 0, 1, 40),
        ] {
            writeln!(
                f,
                "Style: {name},DejaVu Sans,{},&H00F0F5FF,&H00FFFFFF,&HCC0C0805,&H990C0805,{bold},0,0,0,100,100,0,0,1,1.5,0,{align},{},{},{},1",
                size as f32 * scale,
                40.0 * scale,
                40.0 * scale,
                margin as f32 * scale
            )?;
        }
        writeln!(f, "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")?;
        event(&mut f, 0.0, duration, "Title", &a.title)?;
        event(&mut f, 0.0, duration, "Subtitle", &a.subtitle)?;
        subtitles = Some(f);
    }
    let fit = Camera::fit(world.bounds, a.width, a.height);
    let scripted = |time: f32| {
        if a.fit || script.keyframes.is_empty() {
            return fit;
        }
        let ks = &script.keyframes;
        let i = ks.partition_point(|k| key_time(k) <= time);
        let left = &ks[i.saturating_sub(1)];
        let right = &ks[i.min(ks.len() - 1)];
        let u = ((time - key_time(left)) / (key_time(right) - key_time(left)).max(0.001)).clamp(0.0, 1.0);
        let u = u * u * (3.0 - 2.0 * u);
        Camera {
            center: [
                left.center[0] + (right.center[0] - left.center[0]) * u,
                left.center[1] + (right.center[1] - left.center[1]) * u,
            ],
            metres_per_pixel: left.metres_per_pixel * (right.metres_per_pixel / left.metres_per_pixel).powf(u),
        }
    };
    let any_overlay = views.iter().any(|v| !v.overlay.is_empty());
    let mut snapshot = Snapshot::new();
    let lead = (5.0 / a.dt).ceil() as u64;
    let warm = plan.first().map_or(0, |p| p.1);
    let warm_to = if realtime || !videos { warm.saturating_sub(lead) } else { start_step };
    sim.run(&gpu, warm_to);
    let total = plan.len();
    for (frame, &(display, k, blend)) in plan.iter().enumerate() {
        // Pose history has to see the last seconds, or a lane change in progress would be lost.
        while sim.step + 1 < k {
            let silent = k - sim.step - 1;
            if silent > lead {
                sim.run(&gpu, silent - lead);
            } else {
                sim.run(&gpu, 1);
                renderer.prepare(&gpu, &sim, 1.0, mode);
            }
        }
        if sim.step < k {
            sim.run(&gpu, 1);
        }
        let (count, speed) = renderer.prepare(&gpu, &sim, blend, mode);
        if any_overlay {
            snapshot.update(&gpu, &sim, &renderer);
        }
        let clock = a.sim_begin + (sim.step as f32 - 2.0 + blend) * a.dt;
        for v in &mut views {
            let due: Vec<PathBuf> = v.shots.iter().filter(|s| s.0 <= display + 0.5 * seconds_per_frame).map(|s| s.1.clone()).collect();
            if v.ffmpeg.is_none() && due.is_empty() {
                continue;
            }
            let camera = match &mut v.target {
                Target::Fixed(c) => *c,
                Target::Script => scripted(clock),
                Target::Follow { trip, mpp, center, start } => {
                    let target = renderer.trip_position(&gpu, *trip).map_or(*start, |t| t.0);
                    let c = match *center {
                        None => target,
                        Some(c) => {
                            let k = 1.0 - (-seconds_per_frame / 0.35).exp();
                            [c[0] + (target[0] - c[0]) * k, c[1] + (target[1] - c[1]) * k]
                        }
                    };
                    *center = Some(c);
                    Camera { center: c, metres_per_pixel: *mpp }
                }
            };
            let mut pixels = renderer.draw(&gpu, &net, camera);
            if close {
                let mut canvas = Canvas { px: &mut pixels, w: a.width as i32, h: a.height as i32 };
                if !v.overlay.is_empty() {
                    v.state.draw(&mut canvas, camera, &net, &world, &snapshot, clock, &v.overlay);
                    if v.state.first_teleports.is_none() {
                        v.state.first_teleports = Some(snapshot.teleports);
                        v.state.first_collisions = snapshot.collisions;
                    }
                }
                let teleports = v.state.first_teleports.map(|t| snapshot.teleports - t);
                let collisions = teleports.map(|_| snapshot.collisions - v.state.first_collisions);
                overlay::draw_hud(
                    &mut canvas,
                    &Hud {
                        title: &v.title,
                        subtitle: &v.subtitle,
                        clock,
                        count,
                        speed,
                        mpp: camera.metres_per_pixel,
                        teleports,
                        collisions,
                        modes: &v.overlay,
                    },
                );
            }
            if !due.is_empty() {
                for path in &due {
                    write_png(&pixels, a.width, a.height, path)?;
                    eprintln!("saved {}", path.display());
                }
                v.shots.drain(..due.len());
            }
            if let Some((_, pipe)) = &mut v.ffmpeg {
                pipe.write_all(&pixels)?;
            }
        }
        if let Some(f) = subtitles.as_mut() {
            let start = frame as f64 / a.fps as f64;
            let stop = (frame + 1) as f64 / a.fps as f64;
            let minutes = (clock.max(0.0) / 60.0) as u64;
            event(
                f,
                start,
                stop,
                "HUD",
                &format!(
                    "{:02}:{:02}   ·   {} vehicles   ·   {:.0} km/h",
                    minutes / 60 % 24,
                    minutes % 60,
                    count,
                    speed * 3.6
                ),
            )?;
            let caption = script
                .captions
                .iter()
                .find(|c| clock >= c.from && clock < c.to)
                .map(|c| c.text.as_str())
                .unwrap_or(&a.subtitle);
            event(f, start, stop, "Caption", caption)?;
        }
        if frame % a.fps as usize == 0 {
            eprintln!("frame {frame}/{total}, sim {clock:.1}s, {count} vehicles");
        }
    }
    for v in &mut views {
        let Some((mut enc, pipe)) = v.ffmpeg.take() else {
            continue;
        };
        drop(pipe);
        if !enc.0.wait()?.success() {
            return Err("ffmpeg encode failed".into());
        }
        if close && let (Some(p), Some(o)) = (&v.partial, &v.out) {
            std::fs::rename(p, o)?;
            eprintln!("saved {}", o.display());
        }
    }
    if let Some(f) = subtitles.take() {
        drop(f);
        let out = views[0].out.clone().ok_or("no video")?;
        let intermediate = out.with_extension("silent.mp4");
        let ass = out.with_extension("ass");
        // Use a private temporary working directory so arbitrary output paths never enter filter syntax.
        let temp = std::env::temp_dir().join(format!("cars-ass-{}", std::process::id()));
        std::fs::create_dir_all(&temp)?;
        std::fs::copy(&ass, temp.join("hud.ass"))?;
        let input = std::fs::canonicalize(&intermediate)?;
        let output = std::env::current_dir()?.join(&out);
        let status = Command::new("ffmpeg")
            .current_dir(&temp)
            .args(["-y", "-v", "error", "-threads", "2", "-filter_threads", "2", "-i"])
            .arg(input)
            .args(["-vf", "ass=hud.ass", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast", "-threads", "2", "-movflags", "+faststart"])
            .arg(output)
            .status();
        let _ = std::fs::remove_dir_all(temp);
        if !status?.success() {
            return Err("ffmpeg subtitle burn failed; silent video retained".into());
        }
        std::fs::remove_file(intermediate)?;
        eprintln!("saved {}", out.display());
    }
    Ok(())
}
