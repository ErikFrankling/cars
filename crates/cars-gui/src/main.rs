//! A window onto the simulator: pick a scenario, set its variables, fly around it while it runs.
mod camera;
mod capture;
mod loader;
mod registry;
mod session;
mod settings;
mod ui;

use cars_core::{Checks, Gpu, overlay::{self, Canvas, Hud}};
use clap::Parser;
use egui_wgpu::ScreenDescriptor;
use registry::{Registry, Roots, Scenario};
use session::{Pace, Selection, Session};
use settings::Settings;
use std::io::Write;
use std::path::PathBuf;
use std::sync::mpsc::{Receiver, Sender, channel};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};
use winit::application::ApplicationHandler;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::window::{Window, WindowId};

/// The one device, for the threads that make GPU buffers in the background.
pub static GPU: OnceLock<Arc<Gpu>> = OnceLock::new();

#[derive(Parser, Clone)]
#[command(about = "Explore traffic scenarios in a window")]
struct Args {
    /// Scenario to open, by its id in registry.toml.
    #[arg(long, default_value = "signal-junction")]
    scenario: String,
    /// Start paused.
    #[arg(long)]
    paused: bool,
    /// Simulated seconds per real second to start with; 0 for as fast as possible.
    #[arg(long)]
    speed: Option<f32>,
    /// Look at this place: x,y,metres per pixel.
    #[arg(long, value_delimiter = ',', allow_negative_numbers = true)]
    camera: Vec<f32>,
    /// Append one JSON line a second: frame times, speed, vehicles.
    #[arg(long)]
    perf_log: Option<PathBuf>,
    /// Quit after this many seconds, for measuring.
    #[arg(long)]
    quit_after: Option<f32>,
    /// Load even when memory looks short.
    #[arg(long)]
    force: bool,
    /// Open this net instead of a scenario from the registry.
    #[arg(long)]
    net: Option<String>,
    /// Route files for --net, separated by commas. May be left out, to look at the map alone.
    #[arg(long, default_value = "")]
    routes: String,
    /// Additional files for --net, separated by commas.
    #[arg(long, default_value = "")]
    additional: String,
    /// What drives the traffic: physical, or sumo for the old driver.
    #[arg(long)]
    driver: Option<String>,
    /// Automated model, by its id in registry.toml. Without it the run is human-only.
    #[arg(long)]
    model: Option<String>,
    /// Percentage of cars driven by humans, when a model is given.
    #[arg(long)]
    human: Option<f32>,
    /// Demand percentage.
    #[arg(long)]
    demand: Option<f32>,
    #[arg(long)]
    seed: Option<u64>,
    /// Step size in seconds.
    #[arg(long)]
    dt: Option<f32>,
    /// Planning with coordinated junctions: off, full or route.
    #[arg(long)]
    plan: Option<String>,
    /// Message loss percentage with coordinated junctions.
    #[arg(long)]
    loss: Option<f32>,
    /// The stricter safety level B with coordinated junctions.
    #[arg(long)]
    level_b: bool,
    /// The coordinator's own signals instead of signal-free.
    #[arg(long)]
    baseline: bool,
    /// Overlays to turn on: leader,braking,speed,state,foes,events,grants,paths,channel,arrivals,brake.
    #[arg(long, value_delimiter = ',')]
    overlay: Vec<String>,
    /// Colour by speed, waiting, type, braking or paint.
    #[arg(long)]
    colour: Option<String>,
}

/// How the map is coloured. The numbers are the renderer's modes.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Colour {
    Speed = 0,
    Waiting = 2,
    Paint = 3,
    VehicleType = 4,
    Braking = 5,
}

/// What the app holds besides the window itself.
pub struct Model {
    pub roots: Roots,
    pub registry: Registry,
    pub gpu: Arc<Gpu>,
    pub session: Option<Session>,
    pub job: Option<loader::Job>,
    pub last_load: Option<(Scenario, Settings)>,
    pub scenario: Option<Scenario>,
    pub draft: Settings,
    pub colour: Colour,
    pub far_brake: bool,
    pub overlays: Vec<String>,
    pub errors: Vec<ui::Problem>,
    pub toasts: Vec<(Instant, String)>,
    pub help: bool,
    pub panels: bool,
    pub ui: ui::UiState,
    pub present: wgpu::TextureFormat,
    /// Top-left and size of the map in physical pixels, and points per that, as of the last frame.
    pub view_px: (u32, u32),
    pub view_at: (u32, u32),
    pub ppp: f32,
    pub frame_times: FrameTimes,
    pub device_lost: Arc<Mutex<Option<String>>>,
    pub uncaptured: Arc<Mutex<Vec<String>>>,
    pub recorder: Option<capture::Recorder>,
    pub capture_tx: Sender<Result<String, String>>,
    pub capture_rx: Receiver<Result<String, String>>,
    pub want_screenshot: bool,
    pub want_record_toggle: bool,
    pub pending_jump: Option<f32>,
    pub vram: Option<(u64, u64)>,
    pub vram_at: Instant,
    pub proxy: EventLoopProxy<()>,
    pub quit: bool,
    pub first_camera: Option<[f32; 3]>,
    pub first_pace: Option<Pace>,
    pub force: bool,
    pub clip_overlay: overlay::Overlay,
    pub last_tick: Instant,
}

#[derive(Default, Clone, Copy)]
pub struct FrameTimes {
    pub fps: f32,
    pub sim_ms: f32,
    pub prepare_ms: f32,
    pub ui_ms: f32,
    pub draw_ms: f32,
    pub total_ms: f32,
}

impl Model {
    pub fn load(&mut self, scenario: Scenario, settings: Settings, force: bool) {
        if let Some(job) = self.job.take() {
            job.cancel.store(true, std::sync::atomic::Ordering::Relaxed);
        }
        self.scenario = Some(scenario.clone());
        self.draft = settings.clone();
        self.last_load = Some((scenario.clone(), settings.clone()));
        let req = loader::Request::new(&self.registry, &self.roots, &scenario, &settings, self.present, self.view_px, force || self.force);
        let proxy = self.proxy.clone();
        self.job = Some(loader::start(req, self.gpu.clone(), move || {
            let _ = proxy.send_event(());
        }));
    }

    fn poll_load(&mut self) {
        let Some(job) = &self.job else { return };
        match job.rx.try_recv() {
            Ok(loader::Message::NeedGpu) => {
                // Free the old one first: two cities at once would crowd the card.
                if let Some(s) = self.session.take() {
                    self.ui.keep_camera = Some((s.scenario.id.clone(), s.flyer));
                    drop(s);
                    self.gpu.wait();
                }
                let _ = job.go.send(());
            }
            Ok(loader::Message::Done(l)) => {
                self.job = None;
                let bounds = l.world.bounds;
                let (center, mpp) = camera::fit(bounds, self.view_px.0 as f32, self.view_px.1 as f32);
                let max = mpp * 1.6;
                let kept = self.ui.keep_camera.take().filter(|(id, _)| *id == l.scenario.id).map(|(_, f)| f);
                let mut fresh = kept.is_none();
                let mut flyer = kept.unwrap_or_else(|| camera::Flyer::new(center, mpp, max));
                flyer.max_mpp = max.max(flyer.max_mpp);
                if let Some([x, y, m]) = self.first_camera.take() {
                    flyer = camera::Flyer::new([x, y], m, max);
                    fresh = false;
                }
                for n in &l.notes {
                    self.toasts.push((Instant::now(), n.clone()));
                }
                let mut s = Session::new(*l, flyer, fresh);
                if let Some(p) = self.first_pace.take() {
                    s.pace = p;
                }
                if let Some(t) = self.pending_jump.take() {
                    s.jump = Some(t);
                }
                self.ui.junction_filter.clear();
                self.session = Some(s);
            }
            Ok(loader::Message::Failed { text, override_ok }) => {
                self.job = None;
                self.errors.push(ui::Problem { text, retry: override_ok.then(|| self.last_load.clone()).flatten() });
            }
            Err(std::sync::mpsc::TryRecvError::Empty) => {}
            Err(std::sync::mpsc::TryRecvError::Disconnected) => {
                self.job = None;
            }
        }
    }

    /// Move the simulation on for what real time has passed, for at most `budget` milliseconds.
    fn tick_sim(&mut self, budget: f64) {
        let wall = self.last_tick.elapsed().as_secs_f32().min(0.25);
        self.last_tick = Instant::now();
        let gpu = self.gpu.clone();
        if let Some(s) = &mut self.session {
            s.advance(&gpu, wall, budget);
        }
    }

    fn sim_running(&self) -> bool {
        self.session.as_ref().is_some_and(|s| s.pace != Pace::Paused || s.jump.is_some())
    }
}

struct Running {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    config: wgpu::SurfaceConfiguration,
    ctx: egui::Context,
    egui_state: egui_winit::State,
    egui_rend: egui_wgpu::Renderer,
    model: Model,
    last: Instant,
    started: Instant,
    fps_at: Instant,
    fps_frames: u32,
    perf: Option<std::fs::File>,
    repaint_at: Option<Instant>,
}

struct App {
    args: Args,
    proxy: EventLoopProxy<()>,
    running: Option<Running>,
}

fn pick_format(surface: &wgpu::Surface, adapter: &wgpu::Adapter) -> wgpu::TextureFormat {
    let formats = surface.get_capabilities(adapter).formats;
    formats.iter().copied().find(|f| !f.is_srgb() && matches!(f, wgpu::TextureFormat::Bgra8Unorm | wgpu::TextureFormat::Rgba8Unorm)).unwrap_or(formats[0])
}

impl App {
    fn create(&mut self, event_loop: &ActiveEventLoop) -> Result<Running, String> {
        let attrs = Window::default_attributes().with_title("cars").with_inner_size(winit::dpi::LogicalSize::new(1600.0, 960.0));
        let window = Arc::new(event_loop.create_window(attrs).map_err(|e| e.to_string())?);
        let instance = cars_core::gpu::instance_with_display(event_loop.owned_display_handle());
        let surface = instance.create_surface(window.clone()).map_err(|e| e.to_string())?;
        let gpu = match std::env::var("CARS_ADAPTER") {
            Ok(name) => {
                let want = name.to_lowercase();
                let adapter = pollster::block_on(instance.enumerate_adapters(wgpu::Backends::all()))
                    .into_iter()
                    .find(|a| a.get_info().name.to_lowercase().contains(&want))
                    .ok_or_else(|| format!("no adapter matching {name:?}"))?;
                pollster::block_on(Gpu::from_adapter(instance, adapter, Checks::Safe))?
            }
            Err(_) => pollster::block_on(Gpu::for_surface(instance, &surface, Checks::Safe))?,
        };
        let gpu = Arc::new(gpu);
        let _ = GPU.set(gpu.clone());
        let device_lost = Arc::new(Mutex::new(None));
        let lost = device_lost.clone();
        gpu.device.set_device_lost_callback(move |_, why| {
            if let Ok(mut l) = lost.lock() {
                *l = Some(why);
            }
        });
        let uncaptured = Arc::new(Mutex::new(Vec::new()));
        let seen = uncaptured.clone();
        gpu.device.on_uncaptured_error(Arc::new(move |e: wgpu::Error| {
            eprintln!("{e}");
            if let Ok(mut l) = seen.lock() {
                l.push(e.to_string());
            }
        }));
        let format = pick_format(&surface, &gpu.adapter);
        let size = window.inner_size();
        let caps = surface.get_capabilities(&gpu.adapter);
        // Mailbox does not block a thread that is also stepping the simulation.
        let present_mode = if caps.present_modes.contains(&wgpu::PresentMode::Mailbox) { wgpu::PresentMode::Mailbox } else { wgpu::PresentMode::Fifo };
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            color_space: wgpu::SurfaceColorSpace::Auto,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode,
            desired_maximum_frame_latency: 2,
            alpha_mode: caps.alpha_modes[0],
            view_formats: vec![],
        };
        surface.configure(&gpu.device, &config);
        let ctx = egui::Context::default();
        ui::style(&ctx);
        let egui_state = egui_winit::State::new(ctx.clone(), egui::ViewportId::ROOT, &window, Some(window.scale_factor() as f32), None, None);
        let egui_rend = egui_wgpu::Renderer::new(&gpu.device, format, egui_wgpu::RendererOptions::default());
        let roots = Roots::find();
        let (registry, problem) = Registry::load(&roots);
        let (capture_tx, capture_rx) = channel();
        let mut errors = Vec::new();
        if let Some(text) = problem {
            errors.push(ui::Problem { text, retry: None });
        }
        let first = match &self.args.net {
            Some(net) => Some(registry::custom(net, &self.args.routes, &self.args.additional)),
            None => registry.scenario(&self.args.scenario).cloned(),
        };
        if first.is_none() {
            errors.push(ui::Problem { text: format!("There is no scenario called {} in the registry. Pick one on the left.", self.args.scenario), retry: None });
        }
        let mut draft = first.as_ref().map_or_else(|| Settings::for_scenario(&registry::custom("", "", "")), Settings::for_scenario);
        let a = &self.args;
        if let Some(id) = &a.driver {
            if registry.driver(id).is_some() {
                draft.driver = id.clone();
                draft.teleports = !draft.physical() && first.as_ref().is_some_and(|s| s.time_to_teleport > 0.0);
            } else {
                errors.push(ui::Problem { text: format!("There is no driver called {id} in the registry."), retry: None });
            }
        }
        draft.model = a.model.clone().filter(|id| match registry.model(id) {
            Some(m) if m.status == registry::Status::Merged => true,
            _ => {
                errors.push(ui::Problem { text: format!("{id} is not a model that can run. The list is under Automated cars."), retry: None });
                false
            }
        });
        draft.human_pct = a.human.unwrap_or(draft.human_pct);
        draft.demand_pct = a.demand.unwrap_or(draft.demand_pct);
        draft.seed = a.seed.unwrap_or(draft.seed);
        draft.dt = a.dt.unwrap_or(draft.dt);
        draft.loss_pct = a.loss.unwrap_or(draft.loss_pct);
        draft.level_b = a.level_b;
        draft.plan = match a.plan.as_deref() {
            Some("full") => settings::Plan::Full,
            Some("route") => settings::Plan::Route,
            _ => settings::Plan::Off,
        };
        if a.baseline {
            draft.junctions = settings::Junctions::Baseline;
        }
        draft.normalise(&registry);
        let colour = match a.colour.as_deref() {
            Some("waiting") => Colour::Waiting,
            Some("type") => Colour::VehicleType,
            Some("braking") => Colour::Braking,
            Some("paint") => Colour::Paint,
            _ => Colour::Speed,
        };
        let first_pace = match (self.args.paused, self.args.speed) {
            (true, _) => Some(Pace::Paused),
            (_, Some(0.0)) => Some(Pace::AsFast),
            (_, Some(x)) => Some(Pace::Multiple(x)),
            _ => None,
        };
        let mut model = Model {
            roots,
            registry,
            gpu,
            session: None,
            job: None,
            last_load: None,
            scenario: first.clone(),
            draft,
            colour,
            far_brake: false,
            overlays: self.args.overlay.clone(),
            errors,
            toasts: Vec::new(),
            help: false,
            panels: true,
            ui: ui::UiState::default(),
            present: format,
            view_px: (size.width.max(2) * 3 / 5, size.height.max(2) * 9 / 10),
            view_at: (0, 0),
            ppp: window.scale_factor() as f32,
            frame_times: FrameTimes::default(),
            device_lost,
            uncaptured,
            recorder: None,
            capture_tx,
            capture_rx,
            want_screenshot: false,
            want_record_toggle: false,
            pending_jump: None,
            vram: loader::vram(),
            vram_at: Instant::now(),
            proxy: self.proxy.clone(),
            quit: false,
            first_camera: (self.args.camera.len() == 3).then(|| [self.args.camera[0], self.args.camera[1], self.args.camera[2]]),
            first_pace,
            force: self.args.force,
            clip_overlay: overlay::Overlay::default(),
            last_tick: Instant::now(),
        };
        if let Some(s) = first {
            let d = model.draft.clone();
            model.load(s, d, false);
        }
        let perf = self.args.perf_log.as_ref().and_then(|p| std::fs::OpenOptions::new().create(true).append(true).open(p).ok());
        let now = Instant::now();
        Ok(Running { window, surface, config, ctx, egui_state, egui_rend, model, last: now, started: now, fps_at: now, fps_frames: 0, perf, repaint_at: None })
    }
}

impl Running {
    fn busy(&self) -> bool {
        let m = &self.model;
        m.job.is_some()
            || m.recorder.is_some()
            || m.session.as_ref().is_some_and(|s| s.pace != Pace::Paused || s.jump.is_some() || s.flyer.moving() || m.want_screenshot)
    }

    fn frame(&mut self) {
        let t_frame = Instant::now();
        let wall = t_frame.duration_since(self.last).as_secs_f32().min(0.25);
        self.last = t_frame;
        let gpu = self.model.gpu.clone();
        self.model.poll_load();
        if let Ok(l) = self.model.device_lost.lock()
            && let Some(why) = l.as_ref()
            && self.model.errors.iter().all(|e| !e.text.contains("graphics device was lost"))
        {
            self.model.errors.push(ui::Problem { text: format!("The graphics device was lost: {why}. Close the app and start it again."), retry: None });
        }
        if let Ok(mut l) = self.model.uncaptured.lock() {
            for text in l.drain(..).take(3) {
                self.model.errors.push(ui::Problem { text: format!("Graphics error: {text}"), retry: None });
            }
        }
        while let Ok(r) = self.model.capture_rx.try_recv() {
            match r {
                Ok(text) => self.model.toasts.push((Instant::now(), text)),
                Err(text) => self.model.errors.push(ui::Problem { text, retry: None }),
            }
        }
        if self.model.vram_at.elapsed().as_secs_f32() > 2.0 {
            self.model.vram_at = Instant::now();
            self.model.vram = loader::vram();
        }

        // The simulation also runs between frames, in about_to_wait, so this slice can stay small.
        let t = Instant::now();
        self.model.tick_sim(4.0);
        let sim_ms = t.elapsed().as_secs_f32() * 1000.0;
        let t = Instant::now();
        let mode = self.model.colour as u32;
        let flags = if self.model.far_brake { cars_core::render::FLAG_FAR_BRAKE } else { 0 };
        let overlays_on = !self.model.overlays.is_empty();
        if let Some(s) = &mut self.model.session {
            s.prepare(&gpu, mode, flags);
            s.sample(&gpu);
            s.inspect(&gpu);
            if overlays_on && (s.flyer.mpp <= 2.0 || s.numbers.stats.vehicles < 1500) {
                s.update_snapshot(&gpu);
            }
            if s.following
                && matches!(s.selection, Selection::Car(_))
                && s.numbers.stats.selected_index.is_some()
            {
                let xy = s.numbers.stats.selected_xy;
                s.flyer.follow(xy, wall);
            }
            s.flyer.update(wall);
            s.tend_mesh();
        }
        let prepare_ms = t.elapsed().as_secs_f32() * 1000.0;

        let t = Instant::now();
        let raw = self.egui_state.take_egui_input(&self.window);
        let ctx = self.ctx.clone();
        let model = &mut self.model;
        let wall_for_ui = wall;
        let mut full = ctx.run_ui(raw, |root| ui::build(root, model, wall_for_ui));
        self.egui_state.handle_platform_output(&self.window, full.platform_output);
        let ppp = full.pixels_per_point;
        let jobs = self.ctx.tessellate(full.shapes, ppp);
        // Textures are applied even when no frame can be drawn this time.
        let mut textures = std::mem::take(&mut full.textures_delta);
        for (id, deltas) in textures.set.drain() {
            for delta in deltas {
                self.egui_rend.update_texture(&gpu.device, &gpu.queue, id, &delta);
            }
        }
        self.repaint_at = full.viewport_output.get(&egui::ViewportId::ROOT).map(|v| Instant::now() + v.repaint_delay.min(Duration::from_secs(3600)));
        let ui_ms = t.elapsed().as_secs_f32() * 1000.0;

        let t = Instant::now();
        let (vw, vh) = self.model.view_px;
        if let Some(s) = &mut self.model.session {
            s.renderer.resize(&gpu, vw.max(2), vh.max(2));
        }
        if vw > 0 && vh > 0 {
            self.capture();
        }
        let frame = match self.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(f) | wgpu::CurrentSurfaceTexture::Suboptimal(f) => Some(f),
            wgpu::CurrentSurfaceTexture::Outdated | wgpu::CurrentSurfaceTexture::Lost => {
                self.surface.configure(&gpu.device, &self.config);
                None
            }
            _ => None,
        };
        if let Some(frame) = frame {
            let view = frame.texture.create_view(&Default::default());
            let mut e = gpu.device.create_command_encoder(&Default::default());
            let at = self.model.view_at;
            if let Some(s) = &mut self.model.session {
                let cam = s.flyer.camera();
                s.renderer.draw_live(&gpu, cam, &mut e, &view, [at.0, at.1]);
            }
            let screen = ScreenDescriptor { size_in_pixels: [self.config.width, self.config.height], pixels_per_point: ppp };
            let extra = self.egui_rend.update_buffers(&gpu.device, &gpu.queue, &mut e, &jobs, &screen);
            {
                let load = if self.model.session.is_some() { wgpu::LoadOp::Load } else { wgpu::LoadOp::Clear(wgpu::Color::BLACK) };
                let pass = e.begin_render_pass(&wgpu::RenderPassDescriptor {
                    color_attachments: &[Some(wgpu::RenderPassColorAttachment { view: &view, resolve_target: None, depth_slice: None, ops: wgpu::Operations { load, store: wgpu::StoreOp::Store } })],
                    ..Default::default()
                });
                let mut pass = pass.forget_lifetime();
                self.egui_rend.render(&mut pass, &jobs, &screen);
            }
            gpu.queue.submit(extra.into_iter().chain([e.finish()]));
            self.window.pre_present_notify();
            gpu.queue.present(frame);
        }
        for id in textures.free.drain() {
            self.egui_rend.free_texture(&id);
        }
        let draw_ms = t.elapsed().as_secs_f32() * 1000.0;

        self.fps_frames += 1;
        let ft = &mut self.model.frame_times;
        ft.sim_ms = sim_ms;
        ft.prepare_ms = prepare_ms;
        ft.ui_ms = ui_ms;
        ft.draw_ms = draw_ms;
        ft.total_ms = t_frame.elapsed().as_secs_f32() * 1000.0;
        if self.fps_at.elapsed().as_secs_f32() >= 1.0 {
            ft.fps = self.fps_frames as f32 / self.fps_at.elapsed().as_secs_f32();
            self.fps_frames = 0;
            self.fps_at = Instant::now();
            if let Some(f) = &mut self.perf {
                let ft = self.model.frame_times;
                let line = match &self.model.session {
                    Some(s) => serde_json::json!({
                        "t": self.started.elapsed().as_secs_f32(), "scenario": s.scenario.id, "fps": ft.fps, "frame_ms": ft.total_ms, "sim_ms": ft.sim_ms,
                        "prepare_ms": ft.prepare_ms, "ui_ms": ft.ui_ms, "draw_ms": ft.draw_ms, "clock": s.clock(), "multiple": s.multiple,
                        "steps_per_s": s.steps_per_second, "vehicles": s.numbers.stats.vehicles, "mean_speed": s.numbers.stats.mean_speed,
                        "mpp": s.flyer.mpp, "load_s": s.load_seconds, "lod_sizes": s.renderer.lod_sizes(), "gpu_buffers_mb": s.sim.buffers.total_bytes as f64 / 1e6, "close_mesh_ms": s.close_mesh_ms,
                    }),
                    None => serde_json::json!({"t": self.started.elapsed().as_secs_f32(), "loading": self.model.job.is_some(), "fps": ft.fps}),
                };
                let _ = writeln!(f, "{line}");
            }
        }
    }

    /// Screenshots and clips draw the view once more into the texture that can be read back, with
    /// the overlays on the pixels, exactly as `cars record` does.
    fn capture(&mut self) {
        let gpu = self.model.gpu.clone();
        let m = &mut self.model;
        let Some(s) = &mut m.session else {
            m.want_screenshot = false;
            return;
        };
        let (w, h) = m.view_px;
        if m.want_record_toggle {
            m.want_record_toggle = false;
            match m.recorder.take() {
                Some(r) => r.finish(),
                None => {
                    let path = capture::file_name(&s.scenario.id, s.clock(), "mp4");
                    match capture::Recorder::start(w, h, 30, path, m.capture_tx.clone()) {
                        Ok(r) => m.recorder = Some(r),
                        Err(text) => m.errors.push(ui::Problem { text, retry: None }),
                    }
                }
            }
        }
        // A window resized mid-clip changes the frame size, and ffmpeg would read garbage.
        if m.recorder.as_ref().is_some_and(|r| r.size != (w, h)) {
            if let Some(r) = m.recorder.take() {
                r.finish();
            }
            m.toasts.push((Instant::now(), "The view changed size, so the clip stopped.".into()));
        }
        let due_clip = m.recorder.as_ref().is_some_and(|r| r.next_at <= s.started_clock());
        if !m.want_screenshot && !due_clip {
            return;
        }
        let cam = s.flyer.camera();
        let net = s.net.clone();
        let mut pixels = s.renderer.draw(&gpu, &net, cam);
        let mut canvas = Canvas { px: &mut pixels, w: w as i32, h: h as i32 };
        if !m.overlays.is_empty() && !s.snapshot.vs.is_empty() {
            m.clip_overlay.draw(&mut canvas, cam, &s.net, &s.world, &s.snapshot, s.clock(), &m.overlays);
        }
        let title = format!("{}  |  {}", s.scenario.name, s.scenario.trust.label());
        overlay::draw_hud(
            &mut canvas,
            &Hud {
                title: &title,
                subtitle: "",
                clock: s.clock(),
                count: s.numbers.stats.vehicles,
                speed: s.numbers.stats.mean_speed,
                mpp: cam.metres_per_pixel,
                teleports: Some(s.numbers.teleports),
                collisions: Some(s.numbers.collisions),
                trips: Some(s.numbers.arrived),
                modes: &m.overlays,
            },
        );
        if m.want_screenshot {
            m.want_screenshot = false;
            capture::save_png(pixels.clone(), w, h, capture::file_name(&s.scenario.id, s.clock(), "png"), m.capture_tx.clone());
        }
        if due_clip && let Some(r) = &mut m.recorder {
            // Repeat a frame when frames come slower than the clip's rate, so it plays at true speed.
            let now = s.started_clock();
            let copies = if r.next_at == 0.0 { 1 } else { (((now - r.next_at) * 30.0).floor() as u32 + 1).min(5) };
            for _ in 1..copies {
                r.push(pixels.clone());
            }
            r.push(pixels);
            r.next_at = if r.next_at == 0.0 { now + 1.0 / 30.0 } else { (r.next_at + copies as f64 / 30.0).max(now) };
        }
    }
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.running.is_some() {
            return;
        }
        match self.create(event_loop) {
            Ok(r) => {
                r.window.request_redraw();
                self.running = Some(r);
            }
            Err(e) => {
                eprintln!("could not open the window: {e}");
                event_loop.exit();
            }
        }
    }

    fn user_event(&mut self, _: &ActiveEventLoop, _: ()) {
        if let Some(r) = &self.running {
            r.window.request_redraw();
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _: WindowId, event: WindowEvent) {
        let Some(r) = &mut self.running else { return };
        let response = r.egui_state.on_window_event(&r.window, &event);
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::Resized(size) => {
                if size.width > 0 && size.height > 0 {
                    r.config.width = size.width;
                    r.config.height = size.height;
                    let gpu = r.model.gpu.clone();
                    r.surface.configure(&gpu.device, &r.config);
                }
                r.window.request_redraw();
            }
            WindowEvent::RedrawRequested => {
                r.frame();
                if r.model.quit || self.args.quit_after.is_some_and(|q| r.started.elapsed().as_secs_f32() >= q) {
                    if let Some(rec) = r.model.recorder.take() {
                        rec.finish();
                    }
                    event_loop.exit();
                }
            }
            _ => {}
        }
        if response.repaint {
            r.window.request_redraw();
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        let Some(r) = &mut self.running else { return };
        if r.busy() {
            r.window.request_redraw();
            // Frames come when the compositor asks, and not at all while the window is hidden. The
            // simulation carries on between them, returning here often so input is never held up.
            if r.model.sim_running() {
                r.model.poll_load();
                r.model.tick_sim(6.0);
                let flat_out = r.model.session.as_ref().is_some_and(|s| s.jump.is_some() || s.pace == Pace::AsFast);
                event_loop.set_control_flow(if flat_out { ControlFlow::Poll } else { ControlFlow::WaitUntil(Instant::now() + Duration::from_millis(4)) });
            } else {
                event_loop.set_control_flow(ControlFlow::WaitUntil(Instant::now() + Duration::from_millis(16)));
            }
        } else if let Some(at) = r.repaint_at.filter(|at| *at < Instant::now() + Duration::from_secs(600)) {
            if at <= Instant::now() {
                r.window.request_redraw();
            }
            event_loop.set_control_flow(ControlFlow::WaitUntil(at.max(Instant::now() + Duration::from_millis(4))));
        } else {
            event_loop.set_control_flow(ControlFlow::Wait);
        }
    }
}

fn main() {
    let args = Args::parse();
    let event_loop = match EventLoop::<()>::with_user_event().build() {
        Ok(e) => e,
        Err(e) => {
            eprintln!("could not reach the display: {e}");
            std::process::exit(1);
        }
    };
    let proxy = event_loop.create_proxy();
    let mut app = App { args, proxy, running: None };
    if let Err(e) = event_loop.run_app(&mut app) {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
