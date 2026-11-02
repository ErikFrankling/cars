//! Screenshots and clips: the frames `cars record` would draw, written by ffmpeg away from the window's thread.
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::mpsc::{Sender, SyncSender, sync_channel};

pub fn folder() -> PathBuf {
    std::env::var_os("HOME").map(PathBuf::from).unwrap_or_else(|| "/tmp".into()).join("Videos/cars-gui")
}

pub fn file_name(scenario: &str, clock: f32, extension: &str) -> PathBuf {
    let unique = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_secs());
    folder().join(format!("{scenario}-{clock:.0}s-{unique}.{extension}"))
}

fn ensure_parent(path: &Path) -> Result<(), String> {
    if let Some(p) = path.parent() {
        std::fs::create_dir_all(p).map_err(|e| format!("{}: {e}", p.display()))?;
    }
    Ok(())
}

/// Write a PNG on its own thread. The outcome comes back as text for the window.
pub fn save_png(pixels: Vec<u8>, w: u32, h: u32, path: PathBuf, report: Sender<Result<String, String>>) {
    let _ = std::thread::Builder::new().name("png".into()).spawn(move || {
        let result = (|| -> Result<String, String> {
            ensure_parent(&path)?;
            let mut child = Command::new("ffmpeg")
                .args(["-y", "-v", "error", "-threads", "1", "-filter_threads", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-s"])
                .arg(format!("{w}x{h}"))
                .args(["-i", "-", "-frames:v", "1", "-threads", "1", "-update", "1"])
                .arg(&path)
                .stdin(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| format!("could not start ffmpeg: {e}. Start the app with scripts/cars-gui.sh, which brings it."))?;
            child.stdin.take().ok_or("no pipe to ffmpeg")?.write_all(&pixels).map_err(|e| e.to_string())?;
            let out = child.wait_with_output().map_err(|e| e.to_string())?;
            if !out.status.success() {
                return Err(format!("ffmpeg failed: {}", String::from_utf8_lossy(&out.stderr)));
            }
            Ok(format!("Saved {}", path.display()))
        })();
        let _ = report.send(result);
    });
}

/// A clip being written. Frames go to ffmpeg on a thread, and dropping back to fewer frames is
/// better than holding the simulation up: a full queue skips the frame. The finished clip's
/// timestamps are scaled to the real time recorded, so it plays at true speed however many were lost.
pub struct Recorder {
    tx: Option<SyncSender<Vec<u8>>>,
    pub path: PathBuf,
    pub frames: u32,
    pub skipped: u32,
    pub size: (u32, u32),
    pub next_at: f64,
    fps: u32,
    started: std::time::Instant,
    stretch: std::sync::Arc<std::sync::Mutex<f64>>,
    report: Sender<Result<String, String>>,
    worker: Option<std::thread::JoinHandle<Result<String, String>>>,
}

impl Recorder {
    pub fn start(w: u32, h: u32, fps: u32, path: PathBuf, report: Sender<Result<String, String>>) -> Result<Self, String> {
        ensure_parent(&path)?;
        let partial = path.with_extension("partial.mp4");
        let mut child = Command::new("ffmpeg")
            .args(["-y", "-v", "error", "-threads", "2", "-filter_threads", "2", "-f", "rawvideo", "-pix_fmt", "rgba", "-s"])
            .arg(format!("{w}x{h}"))
            .args(["-r", &fps.to_string(), "-i", "-", "-vf", "scale=trunc(min(1920\\,iw)/2)*2:-2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast", "-threads", "2", "-movflags", "+faststart"])
            .arg(&partial)
            .stdin(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("could not start ffmpeg: {e}. Start the app with scripts/cars-gui.sh, which brings it."))?;
        let mut pipe = child.stdin.take().ok_or("no pipe to ffmpeg")?;
        let (tx, rx) = sync_channel::<Vec<u8>>(6);
        let done = path.clone();
        let stretch = std::sync::Arc::new(std::sync::Mutex::new(1.0f64));
        let stretch_for_worker = stretch.clone();
        let worker = std::thread::Builder::new()
            .name("clip".into())
            .spawn(move || {
                for frame in rx {
                    if pipe.write_all(&frame).is_err() {
                        break;
                    }
                }
                drop(pipe);
                let out = child.wait_with_output().map_err(|e| e.to_string())?;
                if !out.status.success() {
                    return Err(format!("ffmpeg failed: {}", String::from_utf8_lossy(&out.stderr)));
                }
                let factor = stretch_for_worker.lock().map_or(1.0, |f| *f);
                if (factor - 1.0).abs() < 0.02 {
                    std::fs::rename(&partial, &done).map_err(|e| e.to_string())?;
                } else {
                    let out = Command::new("ffmpeg")
                        .args(["-y", "-v", "error", "-threads", "1", "-itsscale", &format!("{factor:.4}"), "-i"])
                        .arg(&partial)
                        .args(["-c", "copy", "-movflags", "+faststart"])
                        .arg(&done)
                        .output()
                        .map_err(|e| e.to_string())?;
                    if !out.status.success() {
                        return Err(format!("ffmpeg failed: {}", String::from_utf8_lossy(&out.stderr)));
                    }
                    let _ = std::fs::remove_file(&partial);
                }
                Ok(format!("Saved {}", done.display()))
            })
            .map_err(|e| e.to_string())?;
        Ok(Self { tx: Some(tx), path, frames: 0, skipped: 0, size: (w, h), next_at: 0.0, fps, started: std::time::Instant::now(), stretch, report, worker: Some(worker) })
    }

    pub fn push(&mut self, frame: Vec<u8>) {
        if let Some(tx) = &self.tx {
            match tx.try_send(frame) {
                Ok(()) => self.frames += 1,
                Err(_) => self.skipped += 1,
            }
        }
    }

    /// Stop on the side, so a slow finish does not hold up the window.
    pub fn finish(mut self) {
        if self.frames > 0
            && let Ok(mut f) = self.stretch.lock()
        {
            *f = self.started.elapsed().as_secs_f64() / (self.frames as f64 / self.fps as f64);
        }
        self.tx = None;
        let worker = self.worker.take();
        let report = self.report.clone();
        let _ = std::thread::Builder::new().name("clip end".into()).spawn(move || {
            if let Some(w) = worker {
                let result = w.join().unwrap_or_else(|_| Err("the clip writer crashed".into()));
                let _ = report.send(result);
            }
        });
    }
}
