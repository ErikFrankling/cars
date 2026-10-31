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
    path::PathBuf,
    process::{Command, Stdio},
};
#[derive(Parser)]
pub struct Args {
    #[arg(long)]
    net: PathBuf,
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
    #[arg(long, default_value_t = 1)]
    steps_per_frame: u32,
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
    out: PathBuf,
    #[arg(long, default_value = "Traffic in motion")]
    title: String,
    #[arg(long, default_value = "")]
    subtitle: String,
    #[arg(long,default_value="speed",value_parser=["speed","type","wait"])]
    color: String,
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
pub fn run(a: Args) -> Result<(), Box<dyn std::error::Error>> {
    if !a.dt.is_finite()
        || a.dt <= 0.0
        || !a.begin.is_finite()
        || !a.end.is_finite()
        || a.begin < 0.0
        || a.end <= a.begin
        || a.steps_per_frame == 0
        || a.fps == 0
        || a.width < 2
        || a.height < 2
        || a.width % 2 != 0
        || a.height % 2 != 0
        || a.width > 1920
        || a.height > 1920
    {
        return Err(
            "use positive dt/fps/steps, end > begin >= 0, even dimensions up to 1920".into(),
        );
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
    let key_time = |k: &Key| {
        k.time
            .unwrap_or(a.begin + k.frame.unwrap_or(0) as f32 * a.dt * a.steps_per_frame as f32)
    };
    script
        .keyframes
        .sort_by(|x, y| key_time(x).total_cmp(&key_time(y)));
    let mut net = Net::load(&a.net)?;
    for p in &a.additional {
        net.load_additional(p)?;
    }
    let demand = Demand::load(&net, &a.routes, &a.additional, a.seed, Some(a.end as f64))?;
    let world = World::build(
        &net,
        &demand,
        &SimConfig {
            dt: a.dt,
            end_seconds: a.end,
            seed: a.seed,
            ..Default::default()
        },
        &[],
    );
    let gpu = pollster::block_on(Gpu::headless(GpuOptions {
        adapter_name: Some("7900".into()),
        ..Default::default()
    }))?;
    let mut sim = Sim::new(&gpu, &world)?;
    let renderer = Renderer::new(&gpu, &world, &net, a.width, a.height);
    let first = (a.begin / a.dt).ceil() as u64;
    let end = (a.end / a.dt).ceil() as u64;
    sim.run(&gpu, first);
    if let Some(p) = a.out.parent().filter(|p| !p.as_os_str().is_empty()) {
        std::fs::create_dir_all(p)?;
    }
    let intermediate = a.out.with_extension("silent.mp4");
    let ass = a.out.with_extension("ass");
    if a.out == intermediate {
        return Err("output cannot end in .silent.mp4".into());
    }
    let mut subtitles = std::fs::File::create(&ass)?;
    writeln!(
        subtitles,
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
            subtitles,
            "Style: {name},DejaVu Sans,{},&H00F0F5FF,&H00FFFFFF,&HCC0C0805,&H990C0805,{bold},0,0,0,100,100,0,0,1,1.5,0,{align},{},{},{},1",
            size as f32 * scale,
            40.0 * scale,
            40.0 * scale,
            margin as f32 * scale
        )?;
    }
    writeln!(
        subtitles,
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    )?;
    let frames = (end - first).div_ceil(a.steps_per_frame as u64);
    let duration = frames as f64 / a.fps as f64;
    event(&mut subtitles, 0.0, duration, "Title", &a.title)?;
    event(&mut subtitles, 0.0, duration, "Subtitle", &a.subtitle)?;
    let mut ff = Encoder(
        Command::new("ffmpeg")
            .args([
                "-y", "-v", "error", "-threads", "2", "-filter_threads", "2", "-f", "rawvideo", "-pix_fmt", "rgba", "-s",
            ])
            .arg(format!("{}x{}", a.width, a.height))
            .args([
                "-r",
                &a.fps.to_string(),
                "-i",
                "-",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "20",
                "-preset",
                "veryfast",
                "-threads",
                "2",
            ])
            .arg(&intermediate)
            .stdin(Stdio::piped())
            .spawn()?,
    );
    let mut pipe = ff.0.stdin.take().ok_or("ffmpeg stdin")?;
    let fit = Camera::fit(world.bounds, a.width, a.height);
    let mode = match a.color.as_str() {
        "type" => 1,
        "wait" => 2,
        _ => 0,
    };
    for frame in 0..frames {
        sim.run(&gpu, (end - sim.step).min(a.steps_per_frame as u64));
        let time = sim.step.saturating_sub(1) as f32 * a.dt;
        let mut camera = fit;
        if !a.fit && !script.keyframes.is_empty() {
            let ks = &script.keyframes;
            let i = ks.partition_point(|k| key_time(k) <= time);
            let left = &ks[i.saturating_sub(1)];
            let right = &ks[i.min(ks.len() - 1)];
            let u = ((time - key_time(left)) / (key_time(right) - key_time(left)).max(0.001))
                .clamp(0.0, 1.0);
            let u = u * u * (3.0 - 2.0 * u);
            camera = Camera {
                center: [
                    left.center[0] + (right.center[0] - left.center[0]) * u,
                    left.center[1] + (right.center[1] - left.center[1]) * u,
                ],
                metres_per_pixel: left.metres_per_pixel
                    * (right.metres_per_pixel / left.metres_per_pixel).powf(u),
            };
        }
        let (pixels, count, speed) = renderer.frame(&gpu, &sim, camera, mode);
        pipe.write_all(&pixels)?;
        let start = frame as f64 / a.fps as f64;
        let stop = (frame + 1) as f64 / a.fps as f64;
        let minutes = (time.max(0.0) / 60.0) as u64;
        event(
            &mut subtitles,
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
            .find(|c| time >= c.from && time < c.to)
            .map(|c| c.text.as_str())
            .unwrap_or(&a.subtitle);
        event(&mut subtitles, start, stop, "Caption", caption)?;
        if frame % a.fps as u64 == 0 {
            eprintln!("frame {frame}/{frames}, sim {time:.1}s, {count} vehicles");
        }
    }
    drop(pipe);
    if !ff.0.wait()?.success() {
        return Err("ffmpeg encode failed".into());
    }
    drop(subtitles);
    // Use a private temporary working directory so arbitrary output paths never enter filter syntax.
    let temp = std::env::temp_dir().join(format!("cars-ass-{}", std::process::id()));
    std::fs::create_dir_all(&temp)?;
    std::fs::copy(&ass, temp.join("hud.ass"))?;
    let input = std::fs::canonicalize(&intermediate)?;
    let output = std::env::current_dir()?.join(&a.out);
    let status = Command::new("ffmpeg")
        .current_dir(&temp)
        .args(["-y", "-v", "error", "-threads", "2", "-filter_threads", "2", "-i"])
        .arg(input)
        .args([
            "-vf",
            "ass=hud.ass",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "20",
            "-preset",
            "veryfast",
            "-threads",
            "2",
            "-movflags",
            "+faststart",
        ])
        .arg(output)
        .status();
    let _ = std::fs::remove_dir_all(temp);
    if !status?.success() {
        return Err("ffmpeg subtitle burn failed; silent video retained".into());
    }
    std::fs::remove_file(intermediate)?;
    eprintln!("saved {}", a.out.display());
    Ok(())
}
