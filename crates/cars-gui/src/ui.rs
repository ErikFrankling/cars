//! The panels, the map's input handling, and drawing overlays on the map.
use crate::camera;
use crate::registry::{self, Scenario, Status, Trust};
use crate::session::{self, Pace, Selection, Series, Session, clock_text};
use crate::settings::{Junctions, Plan, Settings};
use crate::{Colour, Model};
use cars_core::overlay::Paint;
use egui::{Align2, Color32, FontId, Key, Pos2, Rect, RichText, Sense, Stroke, Ui, Vec2};
use std::path::PathBuf;

pub struct Problem {
    pub text: String,
    /// Scenario and settings to load regardless, when the user may insist.
    pub retry: Option<(Scenario, Settings)>,
}

#[derive(Default)]
pub struct UiState {
    pub keep_camera: Option<(String, camera::Flyer)>,
    pub junction_filter: String,
    pub goto_text: String,
    pub open_net: String,
    pub open_routes: String,
    pub open_additional: String,
    pub browse: Option<Browse>,
    pub opener: bool,
    pub event_log: Vec<(f32, &'static str, [f32; 2])>,
    pub show_perf: bool,
}

pub struct Browse {
    pub dir: PathBuf,
    pub target: u8,
    pub entries: Vec<(String, bool)>,
}

const INK: Color32 = Color32::from_rgb(222, 226, 232);
const MUTED: Color32 = Color32::from_rgb(150, 156, 168);
const GRID: Color32 = Color32::from_rgb(58, 62, 72);
const LINE: Color32 = Color32::from_rgb(92, 178, 232);
const SURFACE: Color32 = Color32::from_rgb(24, 26, 31);
const ACCENT: Color32 = Color32::from_rgb(70, 130, 200);
const BAD: Color32 = Color32::from_rgb(240, 90, 80);

pub fn style(ctx: &egui::Context) {
    ctx.set_visuals(egui::Visuals::dark());
    ctx.all_styles_mut(|s| {
        s.visuals.panel_fill = SURFACE;
        s.visuals.window_fill = Color32::from_rgb(30, 33, 40);
        s.spacing.item_spacing = Vec2::new(6.0, 5.0);
        s.spacing.slider_width = 150.0;
    });
}

fn trust_chip(ui: &mut Ui, trust: Trust, note: &str) {
    let [r, g, b] = trust.color();
    let response = ui.label(RichText::new(trust.label()).color(Color32::from_rgb(r, g, b)).size(11.5));
    if !note.is_empty() {
        response.on_hover_text(note);
    }
}

fn hhmm(t: f32) -> String {
    let t = t.max(0.0) as u32;
    format!("{:02}:{:02}", t / 3600, t / 60 % 60)
}

fn big(n: f32) -> String {
    if n >= 1e6 {
        format!("{:.1} M", n / 1e6)
    } else if n >= 1e4 {
        format!("{:.0} k", n / 1e3)
    } else {
        format!("{n:.0}")
    }
}

/// Put the overlay code's drawing on the map. It thinks in view pixels.
struct MapPaint<'a> {
    painter: &'a egui::Painter,
    origin: Pos2,
    ppp: f32,
    size: (i32, i32),
}
impl MapPaint<'_> {
    fn pos(&self, p: [f32; 2]) -> Pos2 {
        self.origin + Vec2::new(p[0], p[1]) / self.ppp
    }
    fn colour(c: [u8; 3], a: f32) -> Color32 {
        Color32::from_rgba_unmultiplied(c[0], c[1], c[2], (a.clamp(0.0, 1.0) * 255.0) as u8)
    }
}
impl Paint for MapPaint<'_> {
    fn size(&self) -> (i32, i32) {
        self.size
    }
    fn line(&mut self, a: [f32; 2], b: [f32; 2], width: f32, c: [u8; 3], alpha: f32) {
        self.painter.line_segment([self.pos(a), self.pos(b)], Stroke::new(width / self.ppp, Self::colour(c, alpha)));
    }
    fn ring(&mut self, center: [f32; 2], radius: f32, width: f32, c: [u8; 3], alpha: f32) {
        self.painter.circle_stroke(self.pos(center), radius / self.ppp, Stroke::new(width / self.ppp, Self::colour(c, alpha)));
    }
    fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: [u8; 3], a: f32) {
        let min = self.pos([x as f32, y as f32]);
        self.painter.rect_filled(Rect::from_min_size(min, Vec2::new(w as f32, h as f32) / self.ppp), 0.0, Self::colour(c, a));
    }
    fn text(&mut self, x: i32, y: i32, s: &str, scale: i32, c: [u8; 3]) {
        self.painter.text(self.pos([x as f32, y as f32]), Align2::LEFT_TOP, s, FontId::monospace(9.0 * scale as f32 / self.ppp), Self::colour(c, 1.0));
    }
    fn label(&mut self, x: i32, y: i32, s: &str, scale: i32, c: [u8; 3]) {
        let w = s.chars().count() as i32 * 6 * scale + 2 * scale;
        self.rect(x - scale, y - scale, w, 9 * scale + scale, [8, 8, 10], 0.62);
        self.text(x, y, s, scale, c);
    }
}

/// One measure against simulated time, with a crosshair on hover.
fn chart(ui: &mut Ui, title: &str, unit: &str, series: &Series, floor_zero: bool, alarm: bool) {
    let latest = series.v.last().copied().unwrap_or(0.0);
    ui.horizontal(|ui| {
        ui.label(RichText::new(title).color(MUTED).size(11.5));
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            ui.label(RichText::new(format!("{} {unit}", big(latest))).color(if alarm && latest > 0.0 { BAD } else { INK }).size(11.5));
        });
    });
    let (rect, response) = ui.allocate_exact_size(Vec2::new(ui.available_width(), 42.0), Sense::hover());
    let p = ui.painter_at(rect);
    p.line_segment([rect.left_bottom(), rect.right_bottom()], Stroke::new(1.0, GRID));
    if series.t.len() < 2 {
        return;
    }
    let (t0, t1) = (series.t[0], *series.t.last().unwrap());
    let hi = series.v.iter().copied().fold(f32::MIN, f32::max).max(1e-3);
    let lo = if floor_zero { 0.0 } else { series.v.iter().copied().fold(f32::MAX, f32::min) };
    let span = (hi - lo).max(1e-3);
    let at = |t: f32, v: f32| Pos2::new(rect.left() + (t - t0) / (t1 - t0).max(1e-3) * rect.width(), rect.bottom() - 2.0 - (v - lo) / span * (rect.height() - 6.0));
    let points: Vec<Pos2> = series.t.iter().zip(&series.v).map(|(&t, &v)| at(t, v)).collect();
    p.add(egui::Shape::line(points, Stroke::new(1.6, LINE)));
    p.text(rect.left_top(), Align2::LEFT_TOP, big(hi), FontId::proportional(9.5), MUTED);
    if let Some(pos) = response.hover_pos() {
        let u = ((pos.x - rect.left()) / rect.width()).clamp(0.0, 1.0);
        let t = t0 + u * (t1 - t0);
        let i = series.t.partition_point(|&x| x < t).min(series.t.len() - 1);
        p.line_segment([Pos2::new(pos.x, rect.top()), Pos2::new(pos.x, rect.bottom())], Stroke::new(1.0, MUTED));
        p.circle_filled(at(series.t[i], series.v[i]), 3.5, LINE);
        response.on_hover_text(format!("{}: {} {unit}", clock_text(series.t[i]), big(series.v[i])));
    }
}

fn fit_camera(s: &mut Session, view: (u32, u32)) {
    let (c, m) = camera::fit(s.world.bounds, view.0 as f32, view.1 as f32);
    s.flyer.max_mpp = s.flyer.max_mpp.max(m * 1.6);
    s.following = false;
    s.flyer.go_to(c, Some(m));
}

fn junction_view(s: &mut Session, j: &cars_core::net::Junction, view_h: u32) {
    let radius = j.shape.iter().map(|p| (p[0] - j.x).hypot(p[1] - j.y)).fold(0.0, f32::max);
    s.following = false;
    s.flyer.go_to([j.x, j.y], Some(((radius * 2.0 + 75.0) / view_h.max(1) as f32).clamp(0.05, 0.3)));
}

/// Go to a time. Backwards means starting again, since the simulation only runs forwards.
fn go_to_time(m: &mut Model, t: f32) {
    let Some(s) = &mut m.session else { return };
    let t = t.clamp(s.scenario.begin, s.scenario.end);
    if t >= s.clock() {
        s.jump = Some(t);
        return;
    }
    let (sc, st) = (s.scenario.clone(), s.settings.clone());
    m.pending_jump = Some(t);
    m.load(sc, st, false);
}

fn top_bar(ui: &mut Ui, m: &mut Model) {
    ui.horizontal(|ui| {
        let Some(s) = &mut m.session else {
            ui.label(RichText::new("No scenario running").color(MUTED));
            return;
        };
        let paused = s.pace == Pace::Paused;
        if ui.button(if paused { "Play" } else { "Pause" }).on_hover_text("Space").clicked() {
            s.pace = if paused { Pace::Multiple(s.scenario.speed) } else { Pace::Paused };
        }
        if ui.button("Step").on_hover_text("Run one simulation step. Key: .").clicked() {
            s.pace = Pace::Paused;
            s.step_once(&m.gpu);
        }
        let mut x = match s.pace {
            Pace::Multiple(x) => x,
            Pace::Paused => s.scenario.speed,
            Pace::AsFast => 2000.0,
        };
        let changed = ui.add(egui::Slider::new(&mut x, 0.1..=2000.0).logarithmic(true).suffix("×").custom_formatter(|v, _| if v >= 100.0 { format!("{v:.0}") } else if v >= 10.0 { format!("{v:.0}") } else { format!("{v:.1}") })).on_hover_text("Simulated seconds per real second. Keys: [ and ]").changed();
        if changed {
            s.pace = Pace::Multiple(x);
        }
        let fast = s.pace == Pace::AsFast;
        if ui.selectable_label(fast, "Fastest").on_hover_text("As fast as the card goes, keeping the window smooth").clicked() {
            s.pace = if fast { Pace::Multiple(s.scenario.speed) } else { Pace::AsFast };
        }
        ui.separator();
        ui.label(RichText::new(clock_text(s.clock())).monospace().size(16.0).color(INK));
        ui.label(RichText::new(format!("{:.1}× real time", s.multiple)).color(MUTED)).on_hover_text("Measured over the last half second");
        ui.label(RichText::new(format!("{} steps/s", big(s.steps_per_second))).color(MUTED));
        ui.label(RichText::new(format!("{} updates/s", big(s.vehicle_updates))).color(MUTED)).on_hover_text("Vehicle updates per second");
        ui.separator();
        ui.label("Go to");
        let edit = ui.add(egui::TextEdit::singleline(&mut m.ui.goto_text).desired_width(50.0).hint_text("08:00"));
        let enter = edit.lost_focus() && ui.input(|i| i.key_pressed(Key::Enter));
        if ui.button("Go").clicked() || enter {
            match session::parse_clock(&m.ui.goto_text) {
                Some(t) => go_to_time(m, t),
                None => m.errors.push(Problem { text: format!("\"{}\" is not a time. Write it like 08:00.", m.ui.goto_text), retry: None }),
            }
        }
    });
    ui.horizontal(|ui| {
        ui.label("Colour by");
        let name = |c: Colour| match c {
            Colour::Speed => "speed",
            Colour::Waiting => "waiting",
            Colour::VehicleType => "vehicle type",
            Colour::Braking => "braking",
            Colour::Paint => "paint",
        };
        egui::ComboBox::from_id_salt("colour").selected_text(name(m.colour)).show_ui(ui, |ui| {
            for c in [Colour::Speed, Colour::Waiting, Colour::VehicleType, Colour::Braking, Colour::Paint] {
                ui.selectable_value(&mut m.colour, c, name(c));
            }
        });
        ui.checkbox(&mut m.far_brake, "Brake lights far out").on_hover_text("Close up, cars always show their lamps");
        ui.separator();
        let view = m.view_px;
        if let Some(s) = &mut m.session {
            if ui.button("Fit map").on_hover_text("F").clicked() {
                fit_camera(s, view);
            }
            ui.label(RichText::new(format!("{:.2} m/pixel", s.flyer.mpp)).color(MUTED));
        }
        ui.separator();
        if ui.button("Screenshot").on_hover_text("P").clicked() {
            m.want_screenshot = true;
        }
        let recording = m.recorder.is_some();
        let label = if recording { RichText::new("Stop clip").color(BAD) } else { RichText::new("Record clip") };
        if ui.button(label).on_hover_text("R").clicked() {
            m.want_record_toggle = true;
        }
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if ui.button("Help").on_hover_text("? or F1").clicked() {
                m.help = !m.help;
            }
            let ft = m.frame_times;
            ui.toggle_value(&mut m.ui.show_perf, RichText::new(format!("{:.0} fps", ft.fps)).color(MUTED)).on_hover_text("Where each frame's time goes");
            if let Some((used, total)) = m.vram {
                let free = total.saturating_sub(used) as f64 / 1e9;
                let colour = if free < 3.0 { BAD } else { MUTED };
                ui.label(RichText::new(format!("{free:.1} GB VRAM free")).color(colour));
            }
        });
    });
}

fn scenario_list(ui: &mut Ui, m: &mut Model) {
    let current = m.session.as_ref().map(|s| s.scenario.id.clone());
    let mut chosen = None;
    for group in m.registry.groups() {
        ui.add_space(4.0);
        ui.label(RichText::new(&group).strong().color(MUTED).size(12.0));
        for sc in m.registry.scenario.iter().filter(|s| s.group == group) {
            let selected = current.as_deref() == Some(sc.id.as_str());
            let frame = egui::Frame::new().inner_margin(4.0).corner_radius(4.0).fill(if selected { Color32::from_rgb(38, 56, 80) } else { Color32::TRANSPARENT });
            let inner = frame.show(ui, |ui| {
                ui.set_width(ui.available_width());
                ui.label(RichText::new(&sc.name).color(INK));
                trust_chip(ui, sc.trust, &sc.trust_note);
            });
            let response = ui.interact(inner.response.rect, ui.scope_id().with(("scenario", &sc.id)), Sense::click());
            let response = response.on_hover_text(format!("{}\n\n{}: {}", sc.description, sc.trust.label(), sc.trust_note));
            if response.hovered() {
                ui.painter().rect_stroke(inner.response.rect, 4.0, Stroke::new(1.0, GRID), egui::StrokeKind::Inside);
            }
            if response.clicked() {
                chosen = Some(sc.clone());
            }
        }
    }
    ui.add_space(6.0);
    if ui.button("Open any net and route file…").clicked() {
        m.ui.opener = true;
    }
    if let Some(sc) = chosen {
        let settings = Settings::for_scenario(&sc);
        m.load(sc, settings, false);
    }
}

fn variables(ui: &mut Ui, m: &mut Model) {
    let Some(scenario) = m.scenario.clone() else { return };
    let registry = m.registry.clone();
    let d = &mut m.draft;
    egui::Grid::new("vars").num_columns(2).spacing([8.0, 6.0]).show(ui, |ui| {
        ui.label("Demand");
        ui.add(egui::Slider::new(&mut d.demand_pct, 5.0..=300.0).suffix(" %").fixed_decimals(0));
        ui.end_row();
        ui.label("Step size");
        egui::ComboBox::from_id_salt("dt").selected_text(format!("{} s", d.dt)).show_ui(ui, |ui| {
            for v in [0.05f32, 0.1, 0.2, 0.25, 0.5, 1.0] {
                ui.selectable_value(&mut d.dt, v, format!("{v} s"));
            }
        });
        ui.end_row();
        ui.label("Seed");
        ui.add(egui::DragValue::new(&mut d.seed).speed(1.0));
        ui.end_row();
        ui.label("Teleports");
        ui.horizontal(|ui| {
            ui.checkbox(&mut d.teleports, "");
            ui.add_enabled(d.teleports, egui::DragValue::new(&mut d.teleport_s).range(1.0..=7200.0).suffix(" s")).on_hover_text("How long a stuck car waits before it is taken off and put further on");
        });
        ui.end_row();
    });
    let share = d.automated_share(&registry);
    let header = if share > 0.0 { format!("Automated cars: {:.0}%", share * 100.0) } else { "Automated cars: none (human-only)".to_string() };
    egui::CollapsingHeader::new(header).id_salt("automated").default_open(false).show(ui, |ui| {
        ui.horizontal_wrapped(|ui| {
            ui.label(RichText::new("This scenario is").color(MUTED));
            trust_chip(ui, scenario.trust, &scenario.trust_note);
        });
        ui.label(RichText::new("Automated results count for nothing until human-only driving passes the validation gate against a real measured day. Use this to look, not to conclude.").color(MUTED).size(11.5));
        ui.add_space(4.0);
        let selected = d.model.as_deref().and_then(|id| registry.model(id)).map_or("none (human-only)".to_string(), |x| x.name.clone());
        egui::ComboBox::from_id_salt("model").selected_text(selected).width(190.0).show_ui(ui, |ui| {
            ui.selectable_value(&mut d.model, None, "none (human-only)");
            for x in &registry.model {
                match x.status {
                    Status::Merged => {
                        ui.selectable_value(&mut d.model, Some(x.id.clone()), &x.name).on_hover_text(&x.description);
                    }
                    Status::NotMerged => {
                        ui.add_enabled(false, egui::Button::selectable(false, format!("{}: not merged yet", x.name))).on_disabled_hover_text(format!("{} On branch {}.", x.description, x.branch));
                    }
                }
            }
        });
        d.normalise(&registry);
        let coordinated = d.coordinated(&registry);
        if d.model.is_some() && !coordinated {
            ui.horizontal(|ui| {
                ui.label("Humans");
                ui.add(egui::Slider::new(&mut d.human_pct, 0.0..=100.0).suffix(" %").fixed_decimals(0));
            });
            if d.human_pct >= 100.0 {
                ui.label(RichText::new("At 100% humans this model drives nobody. Move the slider.").color(MUTED).size(11.5));
            }
        }
        if coordinated {
            ui.label(RichText::new("Every car is automated: this build's coordinator has no mixed mode.").color(MUTED).size(11.5));
            ui.horizontal(|ui| {
                ui.label("Junctions");
                ui.selectable_value(&mut d.junctions, Junctions::SignalFree, "Signal-free");
                ui.selectable_value(&mut d.junctions, Junctions::Baseline, "Signals").on_hover_text("The coordinator's own signals: the baseline with the same cars");
            });
            ui.horizontal(|ui| {
                ui.label("Planning");
                for p in [Plan::Off, Plan::Full, Plan::Route] {
                    ui.selectable_value(&mut d.plan, p, p.label());
                }
            });
            ui.horizontal(|ui| {
                ui.label("Message loss");
                ui.add(egui::Slider::new(&mut d.loss_pct, 0.0..=50.0).suffix(" %").fixed_decimals(0));
            });
            ui.horizontal(|ui| {
                ui.label("Safety level");
                ui.selectable_value(&mut d.level_b, false, "A").on_hover_text("The specified rule");
                ui.selectable_value(&mut d.level_b, true, "B").on_hover_text("The stricter, stall-tolerant margin");
            });
        }
    });
    let changes = m.session.as_ref().map_or(Vec::new(), |s| m.draft.changes(&s.settings));
    let needs_restart = !changes.is_empty();
    ui.add_space(4.0);
    let text = if needs_restart { RichText::new("Restart to apply").strong().color(Color32::WHITE) } else { RichText::new("Restart") };
    let button = egui::Button::new(text).fill(if needs_restart { ACCENT } else { Color32::from_rgb(50, 54, 62) });
    if ui.add_sized([ui.available_width(), 26.0], button).on_hover_text("The camera stays where it is. Key: Ctrl+R").clicked() {
        restart(m);
    }
    if needs_restart {
        ui.label(RichText::new(format!("Changed: {}", changes.join(", "))).color(MUTED).size(11.5));
    }
    if ui.small_button("Back to this scenario's defaults").clicked() {
        m.draft = Settings::for_scenario(&scenario);
    }
}

fn restart(m: &mut Model) {
    if let Some(sc) = m.scenario.clone() {
        let d = m.draft.clone();
        m.load(sc, d, false);
    }
}

fn numbers(ui: &mut Ui, s: &Session) {
    let n = &s.numbers;
    egui::Grid::new("numbers").num_columns(2).spacing([14.0, 2.0]).show(ui, |ui| {
        let row = |ui: &mut Ui, k: &str, v: String, alarm: bool| {
            ui.label(RichText::new(k).color(MUTED));
            ui.label(RichText::new(v).color(if alarm { BAD } else { INK }));
            ui.end_row();
        };
        row(ui, "Vehicles running", format!("{}", n.stats.vehicles), false);
        row(ui, "Mean speed", format!("{:.1} km/h", n.stats.mean_speed * 3.6), false);
        row(ui, "Arrived", format!("{}", n.arrived), false);
        row(ui, "Teleports", format!("{}", n.teleports), n.teleports > 0);
        row(ui, "Collisions", format!("{}", n.collisions), n.collisions > 0);
        row(ui, "Stuck over 2 min", format!("{}", n.stats.stuck), n.stats.stuck > 0);
        row(ui, "Standing", format!("{}", n.stats.halting), false);
        row(ui, "Braking", format!("{}", n.stats.braking), false);
        if n.overflow > 0 {
            row(ui, "Junction slots full", format!("{}", n.overflow), false);
        }
    });
    ui.add_space(4.0);
    chart(ui, "Vehicles running", "", &n.running, true, false);
    chart(ui, "Mean speed", "km/h", &n.speed, true, false);
    chart(ui, "Arrivals", "/min", &n.arrivals, true, false);
    chart(ui, "Stuck over 2 min", "", &n.stuck, true, true);
    chart(ui, "Teleports", "total", &n.teleports_s, true, true);
    chart(ui, "Collisions", "total", &n.collisions_s, true, true);
}

fn selection_panel(ui: &mut Ui, m: &mut Model) {
    let Some(s) = &mut m.session else { return };
    match s.selection.clone() {
        Selection::None => {
            ui.label(RichText::new("Click a car or a junction on the map.").color(MUTED));
        }
        Selection::Car(trip) => {
            let name = s.trip_names.get(trip as usize).cloned().unwrap_or_else(|| trip.to_string());
            ui.label(RichText::new(format!("Car {name}")).strong().color(INK));
            if !s.car.on_road {
                ui.label(RichText::new(if s.car.seen { "Finished its trip." } else { "Not on the road yet." }).color(MUTED));
            } else {
                let v = s.car.veh;
                let t = s.world.vtypes.get(v.vtype as usize).copied().unwrap_or_default();
                let type_name = s.vtype_names.get(v.vtype as usize).cloned().unwrap_or_default();
                let model = ["Krauss", "IDM", "ACC", "CACC", "EIDM", "CarsAV"].get(t.model as usize).copied().unwrap_or("other");
                let route_i = v.route_i;
                let route_end = v.route_end;
                let lane = s.net.lanes.get(v.lane as usize).map_or(String::new(), |l| l.id.clone());
                let speed_limit = s.net.lanes.get(v.lane as usize).map_or(0.0, |l| l.speed);
                egui::Grid::new("car").num_columns(2).spacing([14.0, 2.0]).show(ui, |ui| {
                    let row = |ui: &mut Ui, k: &str, v: String| {
                        ui.label(RichText::new(k).color(MUTED));
                        ui.label(RichText::new(v).color(INK));
                        ui.end_row();
                    };
                    row(ui, "Speed", format!("{:.1} km/h, limit {:.0}", v.speed * 3.6, speed_limit * 3.6));
                    row(ui, "Acceleration", format!("{:+.2} m/s²", v.acc));
                    row(ui, "Model", format!("{model} ({type_name})"));
                    row(ui, "Size", format!("{:.1} m long", t.length));
                    row(ui, "Lane", lane);
                    row(ui, "At", format!("{:.1} m along", v.pos));
                    row(ui, "Waiting", format!("{:.0} s", v.wait));
                    row(ui, "Time lost", format!("{:.0} s", v.time_loss));
                    match s.car.leader {
                        Some((other, gap, speed)) => {
                            let leader = s.trip_names.get(other as usize).cloned().unwrap_or_else(|| other.to_string());
                            row(ui, "Leader", leader);
                            row(ui, "Gap", format!("{gap:.1} m"));
                            row(ui, "Its speed", format!("{:.0} km/h", speed * 3.6));
                        }
                        None => row(ui, "Leader", "none within 200 m".into()),
                    }
                    row(ui, "Route", format!("edge {} of {}", (route_i + 1).saturating_sub(s.world.trips.get(trip as usize).map_or(0, |x| x.route_start)), s.trip_route(trip).len()));
                });
                let ids: Vec<String> = s.world.routes.get(route_i as usize..route_end as usize).unwrap_or(&[]).iter().take(6).filter_map(|&e| s.net.edges.get(e as usize).map(|x| x.id.clone())).collect();
                ui.label(RichText::new(format!("Next: {}", ids.join(", "))).color(MUTED).size(11.0));
            }
            ui.horizontal(|ui| {
                let label = if s.following { "Stop following" } else { "Follow" };
                if ui.button(label).on_hover_text("G").clicked() {
                    s.following = !s.following;
                    if s.following && s.flyer.mpp > 0.3 {
                        s.flyer.go_to(s.numbers.stats.selected_xy, Some(0.12));
                    }
                }
                if ui.button("Clear").on_hover_text("Esc").clicked() {
                    s.selection = Selection::None;
                    s.following = false;
                }
            });
        }
        Selection::Junction(index) => {
            let Some(j) = s.net.junctions.get(index as usize) else { return };
            let row_info = s.junctions.iter().find(|r| r.id == j.id);
            ui.label(RichText::new(format!("Junction {}", j.id)).strong().color(INK));
            egui::Grid::new("junction").num_columns(2).spacing([14.0, 2.0]).show(ui, |ui| {
                let row = |ui: &mut Ui, k: &str, v: String| {
                    ui.label(RichText::new(k).color(MUTED));
                    ui.label(RichText::new(v).color(INK));
                    ui.end_row();
                };
                row(ui, "Type", j.jtype.clone());
                row(ui, "Where", format!("{:.0}, {:.0}", j.x, j.y));
                row(ui, "Links", format!("{}", j.requests.len()));
                if let Some(r) = row_info {
                    row(ui, "Incoming lanes", format!("{}", r.lanes));
                }
                if let Some(p) = s.junction.phase {
                    row(ui, "Coordinator phase", format!("{p}"));
                }
            });
            for (id, phase, colours, left) in &s.junction.signals {
                ui.label(RichText::new(format!("Signal {id}, phase {phase}, next switch in {left:.0} s")).color(MUTED).size(11.5));
                ui.horizontal_wrapped(|ui| {
                    ui.spacing_mut().item_spacing.x = 1.0;
                    for c in colours.chars() {
                        let colour = match c {
                            'G' => Color32::from_rgb(70, 230, 100),
                            'g' => Color32::from_rgb(110, 190, 100),
                            'y' | 'Y' | 'u' => Color32::from_rgb(240, 190, 40),
                            'r' | 'R' => Color32::from_rgb(235, 60, 50),
                            _ => MUTED,
                        };
                        ui.label(RichText::new(c.to_string()).monospace().color(colour));
                    }
                });
            }
            let i = &s.junction;
            if s.world.coord.is_some() {
                ui.label(RichText::new(format!("Grants: {} firm, {} on advice, {} in the box, {} lost", i.firm, i.advised, i.in_box, i.lost)).color(INK).size(11.5));
            }
            if ui.button("Look at it").clicked() {
                let j = j.clone();
                let h = m.view_px.1;
                junction_view(s, &j, h);
            }
        }
    }
}

fn overlays_panel(ui: &mut Ui, m: &mut Model) {
    let mut toggle = |ui: &mut Ui, key: &str, label: &str, tip: &str, enabled: bool| {
        let mut on = m.overlays.iter().any(|x| x == key);
        if ui.add_enabled(enabled, egui::Checkbox::new(&mut on, label)).on_hover_text(tip).changed() {
            m.overlays.retain(|x| x != key);
            if on {
                m.overlays.push(key.to_string());
            }
        }
    };
    toggle(ui, "leader", "Leader links", "Cyan line from each car to the one it follows", true);
    toggle(ui, "braking", "Stopping distance", "Amber band: where the car can stop. Red tick: an emergency stop", true);
    toggle(ui, "speed", "Speed labels", "km/h beside moving cars", true);
    toggle(ui, "state", "What each driver decided", "WAIT, GO or APPR, the link's state and metres to it", true);
    toggle(ui, "foes", "Foes at junctions", "Magenta: who a car has to watch, and where the paths cross", true);
    toggle(ui, "events", "Events", "A red marker at teleports, collisions and overlaps", true);
    let coordinated = m.session.as_ref().is_some_and(|s| s.world.coord.is_some());
    let tip = if coordinated { "" } else { " Needs D8 coordinated junctions." };
    toggle(ui, "grants", "Grants and slot chart", &format!("Firm slots, speed advice, lost grants, and the live slot chart.{tip}"), coordinated);
    toggle(ui, "paths", "Planned paths", &format!("Paths through the box, wide where a crossing foe needs the road too.{tip}"), coordinated);
    toggle(ui, "channel", "Who talks to whom", &format!("Coordinator rings and the messages to it.{tip}"), coordinated);
    toggle(ui, "arrivals", "Broadcast arrivals", &format!("Each car's arrival time to the millisecond, and a chart of slots 30 s ahead.{tip}"), coordinated);
    toggle(ui, "brake", "Brake totals", &format!("Red tail on braking cars, with stops, hard brakes and energy thrown away.{tip}"), coordinated);
    if let Some(s) = &m.session
        && !m.overlays.is_empty()
    {
        if s.flyer.mpp > 2.0 && s.numbers.stats.vehicles >= 1500 {
            ui.label(RichText::new("Zoom in to see overlays on a map this big.").color(MUTED).size(11.5));
        } else if s.overlay.truncated {
            ui.label(RichText::new("Showing the first 700 cars on screen. Zoom in for all of them.").color(MUTED).size(11.5));
        } else if s.overlay_cost_ms > 8.0 {
            ui.label(RichText::new(format!("Reading cars back costs {:.0} ms per update.", s.overlay_cost_ms)).color(MUTED).size(11.5));
        }
    }
    if !m.ui.event_log.is_empty() {
        ui.add_space(4.0);
        ui.label(RichText::new("Latest events, click to go").color(MUTED).size(11.5));
        let log: Vec<_> = m.ui.event_log.iter().rev().take(8).copied().collect();
        for (t, name, at) in log {
            if ui.small_button(format!("{} {name}", clock_text(t))).clicked()
                && let Some(s) = &mut m.session
            {
                s.following = false;
                s.flyer.go_to(at, Some(0.1));
            }
        }
    }
}

fn junctions_panel(ui: &mut Ui, m: &mut Model) {
    let view_h = m.view_px.1;
    let Some(s) = &mut m.session else { return };
    ui.add(egui::TextEdit::singleline(&mut m.ui.junction_filter).hint_text("Search id or kind, like signal").desired_width(f32::INFINITY));
    let needle = m.ui.junction_filter.to_lowercase();
    let list: Vec<usize> = s.junctions.iter().enumerate().filter(|(_, r)| needle.is_empty() || r.kind.contains(&needle) || r.id.to_lowercase().contains(&needle)).map(|(i, _)| i).collect();
    ui.label(RichText::new(format!("{} junctions, biggest first", list.len())).color(MUTED).size(11.0));
    let mut go = None;
    egui::ScrollArea::vertical().id_salt("junctions").max_height(180.0).auto_shrink([false, true]).show_rows(ui, 18.0, list.len(), |ui, range| {
        for &i in &list[range] {
            let r = &s.junctions[i];
            let text = format!("{:<10} {} lanes  {}", r.kind, r.lanes, r.id);
            if ui.add(egui::Button::selectable(false, RichText::new(text).monospace().size(11.0))).clicked() {
                go = Some(r.id.clone());
            }
        }
    });
    if let Some(id) = go
        && let Some(&index) = s.net.junction_index.get(&id)
    {
        let j = s.net.junctions[index as usize].clone();
        junction_view(s, &j, view_h);
        s.selection = Selection::Junction(index);
    }
}

fn legend(ui: &mut Ui, m: &Model) {
    let swatch = |ui: &mut Ui, c: Color32, text: &str| {
        ui.horizontal(|ui| {
            let (r, _) = ui.allocate_exact_size(Vec2::splat(11.0), Sense::hover());
            ui.painter().rect_filled(r, 3.0, c);
            ui.label(RichText::new(text).color(MUTED).size(11.5));
        });
    };
    match m.colour {
        Colour::Speed => {
            swatch(ui, Color32::from_rgb(255, 40, 70), "stopped");
            swatch(ui, Color32::from_rgb(255, 210, 90), "half the limit");
            swatch(ui, Color32::from_rgb(160, 235, 255), "at the limit");
        }
        Colour::Waiting => {
            swatch(ui, Color32::from_rgb(160, 235, 255), "not waiting");
            swatch(ui, Color32::from_rgb(255, 40, 70), "a minute or more");
        }
        Colour::Braking => {
            swatch(ui, Color32::from_rgb(80, 92, 112), "not braking");
            swatch(ui, Color32::from_rgb(255, 184, 40), "braking gently");
            swatch(ui, Color32::from_rgb(255, 20, 20), "braking hard");
        }
        Colour::Paint => {
            ui.label(RichText::new("Each car has its own paint.").color(MUTED).size(11.5));
        }
        Colour::VehicleType => {
            let table = [[242, 178, 82], [184, 184, 199], [51, 217, 242], [77, 140, 255], [153, 89, 255], [51, 230, 102], [255, 77, 191], [242, 242, 77]];
            if let Some(s) = &m.session {
                for (class, name) in &s.legend {
                    let [r, g, b] = table[*class as usize % 8];
                    swatch(ui, Color32::from_rgb(r, g, b), name);
                }
            }
        }
    }
}

/// Everything that happens on the map itself. Runs after the panels, so it knows what is left.
fn map(ui: &mut Ui, m: &mut Model, wall: f32) {
    let (rect, response) = ui.allocate_exact_size(ui.available_size(), Sense::click_and_drag());
    let ppp = ui.ctx().pixels_per_point();
    m.ppp = ppp;
    m.view_px = (((rect.width() * ppp).round() as u32).max(2), ((rect.height() * ppp).round() as u32).max(2));
    m.view_at = ((rect.left() * ppp).round() as u32, (rect.top() * ppp).round() as u32);
    let view = m.view_px;
    let (w, h) = (m.view_px.0 as f32, m.view_px.1 as f32);
    let gpu = m.gpu.clone();
    let Some(s) = &mut m.session else {
        ui.painter().rect_filled(rect, 0.0, Color32::BLACK);
        return;
    };
    let view_h = m.view_px.1;
    // Until the camera has been touched, it keeps fitting the map as the window finds its size.
    if s.flyer_untouched && s.fitted_for != view {
        let (c, f) = camera::fit(s.world.bounds, view.0 as f32, view.1 as f32);
        s.flyer = camera::Flyer::new(c, f, f * 1.6);
        s.fitted_for = view;
    }
    let touched = response.dragged() || response.clicked() || ui.input(|i| i.smooth_scroll_delta != Vec2::ZERO || i.zoom_delta() != 1.0 || i.keys_down.iter().any(|k| matches!(k, Key::W | Key::A | Key::S | Key::D | Key::ArrowUp | Key::ArrowDown | Key::ArrowLeft | Key::ArrowRight | Key::Plus | Key::Minus | Key::Equals)));
    if touched && response.contains_pointer() {
        s.flyer_untouched = false;
    }
    if response.dragged() {
        let d = response.drag_delta() * ppp;
        s.flyer.drag(d.x, d.y);
        s.following = false;
        ui.ctx().set_cursor_icon(egui::CursorIcon::Grabbing);
    }
    let hover = response.hover_pos().map(|p| [(p.x - rect.left()) * ppp, (p.y - rect.top()) * ppp]);
    if let Some(p) = hover {
        let (scroll, pinch) = ui.input(|i| (i.smooth_scroll_delta.y + i.smooth_scroll_delta.x * 0.0, i.zoom_delta()));
        let factor = (-scroll / 170.0).exp() / pinch;
        if (factor - 1.0).abs() > 1e-4 {
            let anchor = if s.following { [0.0, 0.0] } else { [p[0] - w * 0.5, p[1] - h * 0.5] };
            s.flyer.zoom_at(factor, anchor);
        }
    }
    if response.double_clicked()
        && let Some(p) = hover
    {
        s.flyer.zoom_at(0.5, [p[0] - w * 0.5, p[1] - h * 0.5]);
    } else if response.clicked()
        && let Some(p) = hover
    {
        let at = camera::to_world(s.flyer.camera(), w, h, p);
        let reach = (s.flyer.mpp * 10.0).max(2.5);
        let junction_reach = (s.flyer.mpp * 16.0).max(12.0);
        let pick = if let Some(trip) = s.car_at(&gpu, at, reach) {
            Selection::Car(trip)
        } else if let Some(j) = s.junction_at(at, junction_reach) {
            Selection::Junction(j)
        } else {
            Selection::None
        };
        if pick != s.selection {
            s.following = false;
            s.car = Default::default();
        }
        s.selection = pick;
    }
    // Keys, unless a text box has them.
    if !ui.ctx().egui_wants_keyboard_input() {
        let (mut vx, mut vy) = (0.0f32, 0.0f32);
        let (keys, shift) = ui.input(|i| {
            (
                [i.key_down(Key::A) || i.key_down(Key::ArrowLeft), i.key_down(Key::D) || i.key_down(Key::ArrowRight), i.key_down(Key::W) || i.key_down(Key::ArrowUp), i.key_down(Key::S) || i.key_down(Key::ArrowDown)],
                i.modifiers.shift,
            )
        });
        let speed = if shift { 2400.0 } else { 800.0 };
        if keys[0] {
            vx -= speed;
        }
        if keys[1] {
            vx += speed;
        }
        if keys[2] {
            vy += speed;
        }
        if keys[3] {
            vy -= speed;
        }
        if vx != 0.0 || vy != 0.0 {
            s.following = false;
            s.flyer.fly(vx, vy, wall);
        }
    }
    let cam = s.flyer.camera();
    let painter = ui.painter_at(rect);
    let screen = |p: [f32; 2]| {
        let q = camera::to_screen(cam, w, h, p);
        rect.min + Vec2::new(q[0], q[1]) / ppp
    };
    if let Selection::Car(_) = s.selection
        && s.numbers.stats.selected_index.is_some()
    {
        let (route_i, route_end) = (s.car.veh.route_i as usize, s.car.veh.route_end as usize);
        for &edge in s.world.routes.get(route_i..route_end).unwrap_or(&[]).iter().take(400) {
            let Some(e) = s.net.edges.get(edge as usize) else { continue };
            let Some(l) = s.net.lanes.get(e.first_lane as usize) else { continue };
            let pts: Vec<Pos2> = l.shape.iter().map(|p| screen(*p)).collect();
            painter.add(egui::Shape::line(pts, Stroke::new(2.0, Color32::from_rgba_unmultiplied(90, 200, 255, 130))));
        }
        let xy = s.numbers.stats.selected_xy;
        let radius = (6.0 / cam.metres_per_pixel / ppp).clamp(9.0, 60.0);
        painter.circle_stroke(screen(xy), radius, Stroke::new(2.0, Color32::WHITE));
    }
    if let Selection::Junction(j) = s.selection
        && let Some(j) = s.net.junctions.get(j as usize)
        && j.shape.len() >= 3
    {
        let mut pts: Vec<Pos2> = j.shape.iter().map(|p| screen(*p)).collect();
        pts.push(pts[0]);
        painter.add(egui::Shape::line(pts, Stroke::new(2.0, Color32::WHITE)));
    }
    if !m.overlays.is_empty() && !s.snapshot.vs.is_empty() && (s.flyer.mpp <= 2.0 || s.numbers.stats.vehicles < 1500) {
        let mut paint = MapPaint { painter: &painter, origin: rect.min, ppp, size: (m.view_px.0 as i32, m.view_px.1 as i32) };
        let clock = s.clock();
        s.overlay.draw(&mut paint, cam, &s.net, &s.world, &s.snapshot, clock, &m.overlays);
        m.ui.event_log.append(&mut s.overlay.log);
        if m.ui.event_log.len() > 200 {
            m.ui.event_log.drain(..100);
        }
    }
    // Scale bar.
    let nice = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0];
    let metres = nice.iter().copied().find(|x| x / cam.metres_per_pixel / ppp > 80.0).unwrap_or(20000.0);
    let px = metres / cam.metres_per_pixel / ppp;
    let base = rect.right_bottom() + Vec2::new(-20.0 - px, -18.0);
    painter.line_segment([base, base + Vec2::new(px, 0.0)], Stroke::new(3.0, Color32::WHITE));
    painter.text(base + Vec2::new(0.0, -4.0), Align2::LEFT_BOTTOM, if metres >= 1000.0 { format!("{:.0} km", metres / 1000.0) } else { format!("{metres} m") }, FontId::proportional(12.0), Color32::WHITE);
    if s.ended {
        painter.text(rect.center_top() + Vec2::new(0.0, 14.0), Align2::CENTER_TOP, "End of the scenario. Press Restart to run it again.", FontId::proportional(15.0), Color32::WHITE);
    }
    if let Some(j) = s.jump {
        painter.text(rect.center_top() + Vec2::new(0.0, 14.0), Align2::CENTER_TOP, format!("Running to {}…", hhmm(j)), FontId::proportional(15.0), Color32::WHITE);
    }
    let _ = view_h;
}

fn keys(ctx: &egui::Context, m: &mut Model) {
    if ctx.egui_wants_keyboard_input() {
        return;
    }
    let pressed = |k: Key| ctx.input(|i| i.key_pressed(k));
    let view = m.view_px;
    if pressed(Key::Questionmark) || pressed(Key::F1) {
        m.help = !m.help;
    }
    if pressed(Key::Tab) {
        m.panels = !m.panels;
    }
    if pressed(Key::P) {
        m.want_screenshot = true;
    }
    if ctx.input(|i| i.modifiers.command) && pressed(Key::R) {
        restart(m);
        return;
    }
    if pressed(Key::R) {
        m.want_record_toggle = true;
    }
    for (k, c) in [(Key::Num1, Colour::Speed), (Key::Num2, Colour::Waiting), (Key::Num3, Colour::VehicleType), (Key::Num4, Colour::Braking), (Key::Num5, Colour::Paint)] {
        if pressed(k) {
            m.colour = c;
        }
    }
    let gpu = m.gpu.clone();
    let Some(s) = &mut m.session else { return };
    if pressed(Key::Space) {
        s.pace = if s.pace == Pace::Paused { Pace::Multiple(s.scenario.speed) } else { Pace::Paused };
    }
    if pressed(Key::Period) {
        s.pace = Pace::Paused;
        s.step_once(&gpu);
    }
    let current = match s.pace {
        Pace::Multiple(x) => x,
        _ => s.scenario.speed,
    };
    if pressed(Key::OpenBracket) {
        s.pace = Pace::Multiple((current / 2.0).max(0.1));
    }
    if pressed(Key::CloseBracket) {
        s.pace = Pace::Multiple((current * 2.0).min(2000.0));
    }
    if pressed(Key::Backslash) {
        s.pace = Pace::AsFast;
    }
    if pressed(Key::F) || pressed(Key::Home) {
        fit_camera(s, view);
    }
    if pressed(Key::G) && matches!(s.selection, Selection::Car(_)) {
        s.following = !s.following;
        if s.following && s.flyer.mpp > 0.3 {
            s.flyer.go_to(s.numbers.stats.selected_xy, Some(0.12));
        }
    }
    if pressed(Key::Escape) {
        s.selection = Selection::None;
        s.following = false;
    }
    let (ctrl_plus, ctrl_minus) = (pressed(Key::Plus) || pressed(Key::Equals), pressed(Key::Minus));
    if ctrl_plus {
        s.flyer.zoom_at(0.5, [0.0, 0.0]);
    }
    if ctrl_minus {
        s.flyer.zoom_at(2.0, [0.0, 0.0]);
    }
}

fn help_window(ctx: &egui::Context, m: &mut Model) {
    let mut open = m.help;
    egui::Window::new("Keys").open(&mut open).collapsible(false).resizable(false).anchor(Align2::CENTER_CENTER, Vec2::ZERO).show(ctx, |ui| {
        egui::Grid::new("keys").num_columns(2).spacing([24.0, 4.0]).show(ui, |ui| {
            for (k, what) in [
                ("Drag", "move the map"),
                ("Wheel, or pinch", "zoom around the pointer"),
                ("W A S D, or arrows", "fly; hold Shift for faster"),
                ("+  -", "zoom at the middle"),
                ("F or Home", "fit the whole map"),
                ("Click", "pick a car or junction"),
                ("Double click", "zoom in here"),
                ("G", "follow the picked car"),
                ("Esc", "clear the pick"),
                ("Space", "pause or play"),
                (".", "one simulation step"),
                ("[  ]", "half or double the speed"),
                ("\\", "as fast as possible"),
                ("1 2 3 4 5", "colour by speed, waiting, type, braking, paint"),
                ("P", "screenshot"),
                ("R", "start or stop a clip"),
                ("Ctrl+R", "restart with the variables shown"),
                ("Tab", "hide or show the panels"),
                ("? or F1", "this help"),
            ] {
                ui.label(RichText::new(k).monospace().color(INK));
                ui.label(RichText::new(what).color(MUTED));
                ui.end_row();
            }
        });
        ui.add_space(6.0);
        ui.label(RichText::new("Screenshots and clips go to ~/Videos/cars-gui.").color(MUTED).size(11.5));
    });
    m.help = open;
}

fn read_dir(dir: &std::path::Path) -> Vec<(String, bool)> {
    let mut out: Vec<(String, bool)> = std::fs::read_dir(dir)
        .map(|r| r.flatten().filter_map(|e| Some((e.file_name().into_string().ok()?, e.path().is_dir()))).filter(|(n, _)| !n.starts_with('.')).collect())
        .unwrap_or_default();
    out.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    out
}

fn opener_window(ctx: &egui::Context, m: &mut Model) {
    if !m.ui.opener {
        return;
    }
    let mut open = true;
    let mut load = false;
    egui::Window::new("Open any net and route file").open(&mut open).default_width(520.0).show(ctx, |ui| {
        let start = m.roots.data.clone();
        egui::Grid::new("open").num_columns(3).show(ui, |ui| {
            for (index, (label, text)) in [("Net", &mut m.ui.open_net), ("Routes", &mut m.ui.open_routes), ("Additional", &mut m.ui.open_additional)].into_iter().enumerate() {
                ui.label(label);
                ui.add(egui::TextEdit::singleline(text).desired_width(360.0).hint_text(if index == 0 { ".net.xml" } else { "comma separated, may be empty" }));
                if ui.button("Browse").clicked() {
                    let dir = std::path::Path::new(text.split(',').next_back().unwrap_or("").trim()).parent().filter(|p| p.is_dir()).map(PathBuf::from).unwrap_or_else(|| start.clone());
                    m.ui.browse = Some(Browse { entries: read_dir(&dir), dir, target: index as u8 });
                }
                ui.end_row();
            }
        });
        let mut pick = None;
        if let Some(b) = &mut m.ui.browse {
            ui.separator();
            ui.label(RichText::new(b.dir.display().to_string()).monospace().size(11.0));
            let mut next = None;
            egui::ScrollArea::vertical().max_height(240.0).auto_shrink([false, true]).show(ui, |ui| {
                if ui.small_button("Up one folder").clicked() {
                    next = b.dir.parent().map(PathBuf::from);
                }
                for (name, is_dir) in &b.entries {
                    let label = if *is_dir { format!("{name}/") } else { name.clone() };
                    if ui.add(egui::Button::selectable(false, label)).clicked() {
                        let p = b.dir.join(name);
                        if *is_dir {
                            next = Some(p);
                        } else {
                            pick = Some((b.target, p));
                        }
                    }
                }
            });
            if let Some(d) = next {
                b.entries = read_dir(&d);
                b.dir = d;
            }
        }
        if let Some((target, p)) = pick {
            let p = p.display().to_string();
            match target {
                0 => m.ui.open_net = p,
                1 if m.ui.open_routes.trim().is_empty() => m.ui.open_routes = p,
                1 => m.ui.open_routes = format!("{}, {p}", m.ui.open_routes),
                _ if m.ui.open_additional.trim().is_empty() => m.ui.open_additional = p,
                _ => m.ui.open_additional = format!("{}, {p}", m.ui.open_additional),
            }
            m.ui.browse = None;
        }
        ui.separator();
        let ready = !m.ui.open_net.trim().is_empty();
        if ui.add_enabled(ready, egui::Button::new("Load")).clicked() {
            load = true;
        }
    });
    if load {
        let sc = registry::custom(m.ui.open_net.trim(), &m.ui.open_routes, &m.ui.open_additional);
        let settings = Settings::for_scenario(&sc);
        m.load(sc, settings, false);
        open = false;
    }
    m.ui.opener = open;
}

fn loading_card(ctx: &egui::Context, m: &mut Model) {
    let Some(job) = &m.job else { return };
    let progress = job.progress.lock().map(|p| p.clone()).unwrap_or(crate::loader::Progress { stage: String::new(), done: 0 });
    let (name, elapsed, done) = (job.name.clone(), job.started.elapsed().as_secs_f32(), progress.done);
    let mut cancel = false;
    egui::Window::new("loading").title_bar(false).resizable(false).anchor(Align2::CENTER_CENTER, Vec2::ZERO).show(ctx, |ui| {
        ui.set_width(340.0);
        ui.horizontal(|ui| {
            ui.spinner();
            ui.label(RichText::new(format!("Loading {name}")).strong().color(INK));
        });
        ui.label(RichText::new(format!("{} ({elapsed:.0} s)", progress.stage)).color(MUTED));
        ui.add(egui::ProgressBar::new(done as f32 / crate::loader::STAGES as f32));
        if ui.button("Cancel").clicked() {
            cancel = true;
        }
    });
    if cancel && let Some(job) = m.job.take() {
        job.cancel.store(true, std::sync::atomic::Ordering::Relaxed);
    }
}

fn problems(ctx: &egui::Context, m: &mut Model) {
    if m.errors.is_empty() {
        return;
    }
    let mut dismiss = None;
    let mut retry = None;
    egui::Window::new(RichText::new("Something went wrong").color(BAD)).collapsible(false).resizable(true).default_width(560.0).anchor(Align2::CENTER_TOP, Vec2::new(0.0, 90.0)).show(ctx, |ui| {
        for (i, e) in m.errors.iter().enumerate() {
            ui.label(RichText::new(&e.text).color(INK));
            ui.horizontal(|ui| {
                if ui.button("OK").clicked() {
                    dismiss = Some(i);
                }
                if let Some(again) = &e.retry
                    && ui.button("Load anyway").clicked()
                {
                    retry = Some(again.clone());
                    dismiss = Some(i);
                }
                if ui.button("Copy").clicked() {
                    ui.ctx().copy_text(e.text.clone());
                }
            });
            ui.separator();
        }
    });
    if let Some(i) = dismiss {
        m.errors.remove(i);
    }
    if let Some((sc, st)) = retry {
        m.load(sc, st, true);
    }
}

fn toasts(ctx: &egui::Context, m: &mut Model) {
    m.toasts.retain(|t| t.0.elapsed().as_secs_f32() < 6.0);
    if m.toasts.is_empty() {
        return;
    }
    egui::Area::new(egui::Id::unique("toasts")).anchor(Align2::LEFT_BOTTOM, Vec2::new(14.0, -14.0)).interactable(false).show(ctx, |ui| {
        for (_, text) in &m.toasts {
            egui::Frame::popup(ui.style()).show(ui, |ui| {
                ui.label(RichText::new(text).color(INK));
            });
        }
    });
    ctx.request_repaint_after(std::time::Duration::from_millis(500));
}

pub fn build(root: &mut Ui, m: &mut Model, wall: f32) {
    let ctx = root.ctx().clone();
    keys(&ctx, m);
    if m.panels {
        egui::Panel::top("top").show(root, |ui| {
            ui.add_space(3.0);
            top_bar(ui, m);
            ui.add_space(2.0);
        });
        egui::Panel::bottom("status").show(root, |ui| {
            ui.horizontal(|ui| {
                if let Some(s) = &m.session {
                    ui.label(RichText::new(&s.scenario.name).color(INK));
                    trust_chip(ui, s.scenario.trust, &s.scenario.trust_note);
                    ui.separator();
                    let who = if s.settings.human_only(&m.registry) {
                        "human-only".to_string()
                    } else {
                        let name = s.settings.model.as_deref().and_then(|id| m.registry.model(id)).map_or("", |x| x.name.as_str());
                        format!("{:.0}% automated, {name}", s.settings.automated_share(&m.registry) * 100.0)
                    };
                    ui.label(RichText::new(who).color(MUTED));
                    ui.separator();
                    ui.label(RichText::new(format!("loaded in {:.1} s, {}", s.load_seconds, s.memory_note())).color(MUTED).size(11.5));
                }
                if m.ui.show_perf {
                    let f = m.frame_times;
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.label(RichText::new(format!("frame {:.1} ms: simulation {:.1}, poses {:.1}, panels {:.1}, drawing {:.1}", f.total_ms, f.sim_ms, f.prepare_ms, f.ui_ms, f.draw_ms)).color(MUTED).size(11.5));
                    });
                }
            });
        });
        egui::Panel::left("left").exact_size(280.0).resizable(false).show(root, |ui| {
            ui.heading(RichText::new("Scenarios").size(15.0));
            let height = ui.available_height() * 0.48;
            egui::ScrollArea::vertical().id_salt("scenarios").max_height(height).auto_shrink([false, false]).show(ui, |ui| scenario_list(ui, m));
            ui.separator();
            ui.heading(RichText::new("Variables").size(15.0));
            egui::ScrollArea::vertical().id_salt("variables").auto_shrink([false, false]).show(ui, |ui| variables(ui, m));
        });
        egui::Panel::right("right").exact_size(285.0).resizable(false).show(root, |ui| {
            egui::ScrollArea::vertical().id_salt("right").show(ui, |ui| {
                egui::CollapsingHeader::new("Selected").default_open(true).show(ui, |ui| selection_panel(ui, m));
                egui::CollapsingHeader::new("Colours").default_open(true).show(ui, |ui| legend(ui, m));
                if m.session.is_some() {
                    egui::CollapsingHeader::new("Live numbers").default_open(true).show(ui, |ui| {
                        if let Some(s) = &m.session {
                            numbers(ui, s);
                        }
                    });
                }
                egui::CollapsingHeader::new("Overlays").default_open(false).show(ui, |ui| overlays_panel(ui, m));
                egui::CollapsingHeader::new("Jump to a junction").default_open(false).show(ui, |ui| junctions_panel(ui, m));
            });
        });
    }
    egui::CentralPanel::no_frame().show(root, |ui| map(ui, m, wall));
    help_window(&ctx, m);
    opener_window(&ctx, m);
    loading_card(&ctx, m);
    problems(&ctx, m);
    toasts(&ctx, m);
    if m.ui.show_perf {
        ctx.request_repaint_after(std::time::Duration::from_millis(250));
    }
}
