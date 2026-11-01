//! Debug drawing on finished frames: text, the HUD, and what the engine thinks of each vehicle.
use cars_core::{
    Gpu,
    net::Net,
    render::{Camera, Instance, Renderer},
    sim::Sim,
    world::{GpuVeh, World},
};
use std::collections::HashMap;

const F_REMOVED: u32 = 1;
const F_ON_JUNCTION: u32 = 128;
const F_WILL_PASS: u32 = 512;
const F_HAVE_TO_WAIT: u32 = 2048;
const NONE: u32 = u32::MAX;
const AMBER: [u8; 3] = [255, 185, 40];
const CYAN: [u8; 3] = [70, 225, 255];
const RED: [u8; 3] = [255, 40, 40];
const GREEN: [u8; 3] = [60, 240, 110];
const ORANGE: [u8; 3] = [255, 130, 30];
const MAGENTA: [u8; 3] = [240, 90, 240];
const WHITE: [u8; 3] = [245, 245, 245];
const SLATE: [u8; 3] = [150, 170, 215];

#[rustfmt::skip]
const FONT: [[u8; 5]; 95] = [
    [0,0,0,0,0],[0,0,0x5f,0,0],[0,7,0,7,0],[0x14,0x7f,0x14,0x7f,0x14],[0x24,0x2a,0x7f,0x2a,0x12],
    [0x23,0x13,8,0x64,0x62],[0x36,0x49,0x55,0x22,0x50],[0,5,3,0,0],[0,0x1c,0x22,0x41,0],[0,0x41,0x22,0x1c,0],
    [0x14,8,0x3e,8,0x14],[8,8,0x3e,8,8],[0,0x50,0x30,0,0],[8,8,8,8,8],[0,0x60,0x60,0,0],
    [0x20,0x10,8,4,2],[0x3e,0x51,0x49,0x45,0x3e],[0,0x42,0x7f,0x40,0],[0x42,0x61,0x51,0x49,0x46],[0x21,0x41,0x45,0x4b,0x31],
    [0x18,0x14,0x12,0x7f,0x10],[0x27,0x45,0x45,0x45,0x39],[0x3c,0x4a,0x49,0x49,0x30],[1,0x71,9,5,3],[0x36,0x49,0x49,0x49,0x36],
    [6,0x49,0x49,0x29,0x1e],[0,0x36,0x36,0,0],[0,0x56,0x36,0,0],[8,0x14,0x22,0x41,0],[0x14,0x14,0x14,0x14,0x14],
    [0,0x41,0x22,0x14,8],[2,1,0x51,9,6],[0x32,0x49,0x79,0x41,0x3e],[0x7e,0x11,0x11,0x11,0x7e],[0x7f,0x49,0x49,0x49,0x36],
    [0x3e,0x41,0x41,0x41,0x22],[0x7f,0x41,0x41,0x22,0x1c],[0x7f,0x49,0x49,0x49,0x41],[0x7f,9,9,9,1],[0x3e,0x41,0x49,0x49,0x7a],
    [0x7f,8,8,8,0x7f],[0,0x41,0x7f,0x41,0],[0x20,0x40,0x41,0x3f,1],[0x7f,8,0x14,0x22,0x41],[0x7f,0x40,0x40,0x40,0x40],
    [0x7f,2,0xc,2,0x7f],[0x7f,4,8,0x10,0x7f],[0x3e,0x41,0x41,0x41,0x3e],[0x7f,9,9,9,6],[0x3e,0x41,0x51,0x21,0x5e],
    [0x7f,9,0x19,0x29,0x46],[0x46,0x49,0x49,0x49,0x31],[1,1,0x7f,1,1],[0x3f,0x40,0x40,0x40,0x3f],[0x1f,0x20,0x40,0x20,0x1f],
    [0x3f,0x40,0x38,0x40,0x3f],[0x63,0x14,8,0x14,0x63],[7,8,0x70,8,7],[0x61,0x51,0x49,0x45,0x43],[0,0x7f,0x41,0x41,0],
    [2,4,8,0x10,0x20],[0,0x41,0x41,0x7f,0],[4,2,1,2,4],[0x40,0x40,0x40,0x40,0x40],[0,1,2,4,0],
    [0x20,0x54,0x54,0x54,0x78],[0x7f,0x48,0x44,0x44,0x38],[0x38,0x44,0x44,0x44,0x20],[0x38,0x44,0x44,0x48,0x7f],[0x38,0x54,0x54,0x54,0x18],
    [8,0x7e,9,1,2],[0x18,0xa4,0xa4,0xa4,0x7c],[0x7f,8,4,4,0x78],[0,0x44,0x7d,0x40,0],[0x40,0x80,0x88,0x7d,0],
    [0x7f,0x10,0x28,0x44,0],[0,0x41,0x7f,0x40,0],[0x7c,4,0x18,4,0x78],[0x7c,8,4,4,0x78],[0x38,0x44,0x44,0x44,0x38],
    [0xfc,0x24,0x24,0x24,0x18],[0x18,0x24,0x24,0x18,0xfc],[0x7c,8,4,4,8],[0x48,0x54,0x54,0x54,0x20],[4,0x3f,0x44,0x40,0x20],
    [0x3c,0x40,0x40,0x20,0x7c],[0x1c,0x20,0x40,0x20,0x1c],[0x3c,0x40,0x30,0x40,0x3c],[0x44,0x28,0x10,0x28,0x44],[0x1c,0xa0,0xa0,0xa0,0x7c],
    [0x44,0x64,0x54,0x4c,0x44],[0,8,0x36,0x41,0],[0,0,0x7f,0,0],[0,0x41,0x36,8,0],[0x10,8,8,0x10,8],
];

pub struct Canvas<'a> {
    pub px: &'a mut [u8],
    pub w: i32,
    pub h: i32,
}
impl Canvas<'_> {
    fn put(&mut self, x: i32, y: i32, c: [u8; 3], a: f32) {
        if x < 0 || y < 0 || x >= self.w || y >= self.h {
            return;
        }
        let k = (y * self.w + x) as usize * 4;
        for i in 0..3 {
            self.px[k + i] = (self.px[k + i] as f32 * (1.0 - a) + c[i] as f32 * a) as u8;
        }
    }
    pub fn line(&mut self, a: [f32; 2], b: [f32; 2], width: f32, c: [u8; 3], alpha: f32) {
        let r = width * 0.5 + 1.0;
        let (x0, x1) = ((a[0].min(b[0]) - r).floor() as i32, (a[0].max(b[0]) + r).ceil() as i32);
        let (y0, y1) = ((a[1].min(b[1]) - r).floor() as i32, (a[1].max(b[1]) + r).ceil() as i32);
        if x1 < 0 || y1 < 0 || x0 >= self.w || y0 >= self.h {
            return;
        }
        let d = [b[0] - a[0], b[1] - a[1]];
        let dd = (d[0] * d[0] + d[1] * d[1]).max(1e-6);
        for y in y0.max(0)..=y1.min(self.h - 1) {
            for x in x0.max(0)..=x1.min(self.w - 1) {
                let p = [x as f32 + 0.5 - a[0], y as f32 + 0.5 - a[1]];
                let t = ((p[0] * d[0] + p[1] * d[1]) / dd).clamp(0.0, 1.0);
                let e = (p[0] - d[0] * t).hypot(p[1] - d[1] * t);
                let cover = (width * 0.5 + 0.5 - e).clamp(0.0, 1.0);
                if cover > 0.0 {
                    self.put(x, y, c, cover * alpha);
                }
            }
        }
    }
    pub fn ring(&mut self, center: [f32; 2], radius: f32, width: f32, c: [u8; 3], alpha: f32) {
        let r = radius + width;
        for y in (center[1] - r).floor() as i32..=(center[1] + r).ceil() as i32 {
            for x in (center[0] - r).floor() as i32..=(center[0] + r).ceil() as i32 {
                let e = ((x as f32 + 0.5 - center[0]).hypot(y as f32 + 0.5 - center[1]) - radius).abs();
                let cover = (width * 0.5 + 0.5 - e).clamp(0.0, 1.0);
                if cover > 0.0 {
                    self.put(x, y, c, cover * alpha);
                }
            }
        }
    }
    pub fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: [u8; 3], a: f32) {
        for yy in y..y + h {
            for xx in x..x + w {
                self.put(xx, yy, c, a);
            }
        }
    }
    pub fn text(&mut self, x: i32, y: i32, s: &str, scale: i32, c: [u8; 3]) {
        for (i, ch) in s.chars().enumerate() {
            let code = ch as usize;
            let glyph = if (32..127).contains(&code) { FONT[code - 32] } else { FONT[31] };
            for (col, bits) in glyph.iter().enumerate() {
                for row in 0..8 {
                    if bits & (1 << row) != 0 {
                        let (px, py) = (x + (i as i32 * 6 + col as i32) * scale, y + row * scale);
                        self.rect(px, py, scale, scale, c, 1.0);
                    }
                }
            }
        }
    }
    pub fn label(&mut self, x: i32, y: i32, s: &str, scale: i32, c: [u8; 3]) {
        let w = s.chars().count() as i32 * 6 * scale + 2 * scale;
        self.rect(x - scale, y - scale, w, 9 * scale, [8, 8, 10], 0.62);
        self.text(x, y, s, scale, c);
    }
}

/// Everything overlays need that is the same for every camera at this moment.
pub struct Snapshot {
    pub vs: Vec<GpuVeh>,
    pub poses: Vec<Instance>,
    pub items: Vec<[u32; 10]>,
    pub by_lane: HashMap<u32, Vec<usize>>,
    pub teleports: u32,
    pub collisions: u32,
    pub cj_phase: Vec<u32>,
    pub arrived: u32,
    /// Trips a trace says collided. Without one, a vehicle going to the dummy lane counts as a
    /// collision when the engine's counter moved.
    pub collided: Option<std::collections::HashSet<u32>>,
    step: u64,
}
impl Snapshot {
    pub fn new() -> Self {
        Self {
            vs: Vec::new(),
            poses: Vec::new(),
            items: Vec::new(),
            by_lane: HashMap::new(),
            teleports: 0,
            collisions: 0,
            cj_phase: Vec::new(),
            arrived: 0,
            collided: None,
            step: u64::MAX,
        }
    }
    /// Index vehicles by lane, for a snapshot filled in from a trace.
    pub fn index(&mut self) {
        self.by_lane.clear();
        for (i, v) in self.vs.iter().enumerate() {
            if v.flags & (F_REMOVED | crate::report::F_SHADOW) == 0 && v.replica == 0 {
                self.by_lane.entry(v.lane).or_default().push(i);
            }
        }
        let vs = &self.vs;
        for list in self.by_lane.values_mut() {
            list.sort_by(|&a, &b| vs[a].pos.total_cmp(&vs[b].pos));
        }
    }
    pub fn update(&mut self, g: &Gpu, sim: &Sim, r: &Renderer) {
        if self.step != sim.step {
            self.step = sim.step;
            self.vs = sim.vehicles(g);
            self.items = sim.read(g, &sim.buffers.items, self.vs.len() as u64 * 8);
            self.index();
            let c = sim.counters(g);
            self.teleports = c[4];
            self.collisions = c[7];
            self.arrived = c[2];
            if let Some(cj) = &sim.coord {
                // Whatever the auditor saw in a box counts as a collision on the frame.
                let seen: Vec<u32> = sim.read(g, &cj.events, 1);
                self.collisions += seen[0];
                let js: Vec<cars_core::coord::GpuCjJunction> = sim.read(g, &cj.junctions, (cj.junctions.size() / std::mem::size_of::<cars_core::coord::GpuCjJunction>() as u64).max(1));
                self.cj_phase = js.iter().map(|j| j.phase).collect();
            }
        }
        self.poses = r.instances(g, sim, self.vs.len() as u32);
    }
}

pub fn pose(net: &Net, lane: u32, pos: f32) -> Option<([f32; 2], [f32; 2])> {
    let l = net.lanes.get(lane as usize)?;
    if l.shape.len() < 2 {
        return None;
    }
    let total: f32 = l.shape.windows(2).map(|p| (p[1][0] - p[0][0]).hypot(p[1][1] - p[0][1])).sum();
    let mut d = (pos / l.length.max(0.01)).clamp(0.0, 1.0) * total;
    for (i, p) in l.shape.windows(2).enumerate() {
        let len = (p[1][0] - p[0][0]).hypot(p[1][1] - p[0][1]);
        if d <= len || i + 2 == l.shape.len() {
            let u = (d / len.max(0.001)).min(1.0);
            let dir = [(p[1][0] - p[0][0]) / len.max(0.001), (p[1][1] - p[0][1]) / len.max(0.001)];
            return Some(([p[0][0] + u * (p[1][0] - p[0][0]), p[0][1] + u * (p[1][1] - p[0][1])], dir));
        }
        d -= len;
    }
    None
}

/// The road ahead of a vehicle along its planned links, as lanes and metres.
fn walk_ahead(net: &Net, world: &World, snap: &Snapshot, i: usize, distance: f32) -> Vec<[f32; 2]> {
    let v = &snap.vs[i];
    let mut lane = v.lane;
    let mut from = v.pos;
    let mut left = distance;
    let mut out = Vec::new();
    for j in 0..8 {
        let length = net.lanes[lane as usize].length.max(0.01);
        let stop = (from + left).min(length);
        if let Some((p, _)) = pose(net, lane, from) {
            out.push(p);
        }
        let l = &net.lanes[lane as usize];
        let total: f32 = l.shape.windows(2).map(|p| (p[1][0] - p[0][0]).hypot(p[1][1] - p[0][1])).sum();
        let scale = total / length;
        let mut d = 0.0;
        for p in l.shape.windows(2) {
            d += (p[1][0] - p[0][0]).hypot(p[1][1] - p[0][1]);
            if d > from * scale + 0.05 && d < stop * scale - 0.05 {
                out.push(p[1]);
            }
        }
        if let Some((p, _)) = pose(net, lane, stop) {
            out.push(p);
        }
        left -= stop - from;
        if left <= 0.01 || j >= v.n_items as usize {
            break;
        }
        let link = snap.items[i * 8 + j][0];
        if link == NONE {
            break;
        }
        lane = world.links[link as usize].next_lane;
        from = 0.0;
    }
    out
}

/// The nearest vehicle ahead along the planned links, and the bumper to bumper gap.
fn leader_of(net: &Net, world: &World, snap: &Snapshot, i: usize, limit: f32) -> Option<(usize, f32)> {
    let v = &snap.vs[i];
    let mut lane = v.lane;
    let mut base = -v.pos;
    let mut after = v.pos;
    for j in 0..8 {
        if let Some(list) = snap.by_lane.get(&lane) {
            let next = list.iter().copied().find(|&k| k != i && (lane != v.lane || snap.vs[k].pos > after));
            if let Some(k) = next {
                let o = &snap.vs[k];
                return Some((k, base + o.pos - world.vtypes[o.vtype as usize].length));
            }
        }
        base += net.lanes[lane as usize].length;
        if base > limit || j >= v.n_items as usize {
            return None;
        }
        let link = snap.items[i * 8 + j][0];
        if link == NONE {
            return None;
        }
        lane = world.links[link as usize].next_lane;
        after = -1.0;
    }
    None
}

#[derive(Default)]
pub struct Overlay {
    previous: HashMap<u32, [f32; 2]>,
    flashes: Vec<([f32; 2], f32, &'static str)>,
    collisions: u32,
    pub first_teleports: Option<u32>,
    pub first_collisions: u32,
    pub first_arrived: u32,
    brake: BrakeTotals,
}

/// Running totals for the `brake` overlay: what every car on an approach has thrown away so far.
#[derive(Default)]
struct BrakeTotals {
    last: HashMap<u32, (f32, bool, bool)>,
    lost: f32,
    wh: f32,
    hard: u32,
    stops: u32,
    cars: u32,
}

fn corners(p: &Instance) -> [[f32; 2]; 4] {
    let n = [-p.dir[1], p.dir[0]];
    let (a, b) = (p.length * 0.5, p.width * 0.5);
    [(a, b), (a, -b), (-a, -b), (-a, b)].map(|(x, y)| [p.xy[0] + p.dir[0] * x + n[0] * y, p.xy[1] + p.dir[1] * x + n[1] * y])
}

fn separated(a: &[[f32; 2]; 4], b: &[[f32; 2]; 4], axis: [f32; 2]) -> bool {
    let range = |c: &[[f32; 2]; 4]| {
        let v = c.map(|p| p[0] * axis[0] + p[1] * axis[1]);
        (v.iter().cloned().fold(f32::MAX, f32::min), v.iter().cloned().fold(f32::MIN, f32::max))
    };
    let (ra, rb) = (range(a), range(b));
    ra.1 <= rb.0 + 0.05 || rb.1 <= ra.0 + 0.05
}

fn rectangles_touch(a: &Instance, b: &Instance) -> bool {
    let (ca, cb) = (corners(a), corners(b));
    ![a.dir, [-a.dir[1], a.dir[0]], b.dir, [-b.dir[1], b.dir[0]]].iter().any(|&axis| separated(&ca, &cb, axis))
}

const NAVY: [u8; 3] = [18, 26, 44];

/// A point on a movement's path, in network metres, straight beyond either end.
fn coord_point(cw: &cars_core::coord::CoordWorld, mi: u32, s: f32) -> [f32; 2] {
    let m = &cw.links[mi as usize];
    let pts = &cw.path[m.path_start as usize..(m.path_start + m.path_n) as usize];
    let spacing = m.path_len / (m.path_n - 1).max(1) as f32;
    let k = ((s / spacing).floor().max(0.0) as usize).min(pts.len().saturating_sub(2));
    let u = s / spacing - k as f32;
    [pts[k][0] + u * (pts[k + 1][0] - pts[k][0]), pts[k][1] + u * (pts[k + 1][1] - pts[k][1])]
}

impl Overlay {
    /// Grants, planned paths and slots, and who is talking to the junction.
    #[allow(clippy::too_many_arguments)]
    /// Brake lights on every car, red over 1 m/s2 and bright over 2.5, and the running totals.
    fn draw_brake(&mut self, c: &mut Canvas, at: &dyn Fn([f32; 2]) -> [f32; 2], world: &World, snap: &Snapshot, shown: &[usize], mpp: f32) {
        let Some(cw) = world.coord.as_ref() else { return };
        for v in snap.vs.iter() {
            if v.flags & F_REMOVED != 0 || v.replica != 0 || v.lane == world.params.dummy_lane {
                continue;
            }
            let Some(li) = cw.lane_info.get(v.lane as usize) else { continue };
            if li.app == u32::MAX {
                continue;
            }
            let t = &mut self.brake;
            let (prev, was_hard, was_stopped) = t.last.get(&v.trip).copied().unwrap_or_else(|| {
                t.cars += 1;
                (v.speed, false, false)
            });
            if v.speed < prev {
                t.lost += prev - v.speed;
                t.wh += 0.5 * 1500.0 * (prev * prev - v.speed * v.speed) / 3600.0;
            }
            let hard = v.acc < -2.5;
            let stopped = v.speed < 0.5;
            if hard && !was_hard {
                t.hard += 1;
            }
            if stopped && !was_stopped {
                t.stops += 1;
            }
            t.last.insert(v.trip, (v.speed, hard || (was_hard && v.acc < -1.0), stopped || (was_stopped && v.speed < 2.0)));
        }
        for &i in shown {
            let v = &snap.vs[i];
            if v.acc >= -1.0 {
                continue;
            }
            let p = &snap.poses[i];
            let bright = v.acc < -2.5;
            let half = p.length * 0.5;
            let rear = [p.xy[0] - p.dir[0] * half, p.xy[1] - p.dir[1] * half];
            let mid = [p.xy[0] - p.dir[0] * half * 0.2, p.xy[1] - p.dir[1] * half * 0.2];
            let width = (1.9 / mpp).max(3.0);
            c.line(at(rear), at(mid), width, if bright { [255, 30, 30] } else { [200, 25, 25] }, if bright { 1.0 } else { 0.85 });
            if bright {
                c.ring(at(rear), width * 0.9, 1.5, [255, 90, 90], 0.9);
            }
        }
        let t = &self.brake;
        let n = t.cars.max(1) as f32;
        let (x, y) = (c.w - 500, if c.w < 1400 { 84 } else { 18 });
        c.rect(x - 10, y - 8, 490, 78, NAVY, 0.72);
        c.text(x, y, &format!("stops {}   hard brakes {}", t.stops, t.hard), 2, if t.hard > 0 { [255, 170, 150] } else { WHITE });
        c.text(x, y + 22, &format!("speed thrown away {:.0} m/s  ({:.1} per car)", t.lost, t.lost / n), 2, WHITE);
        c.text(x, y + 44, &format!("braked away {:.0} Wh  ({:.1} per car)", t.wh, t.wh / n), 2, WHITE);
    }

    /// Each car's broadcast arrival to the millisecond beside it, and the slot chart filling up from far out.
    fn draw_arrivals(&mut self, c: &mut Canvas, at: &dyn Fn([f32; 2]) -> [f32; 2], world: &World, snap: &Snapshot, shown: &[usize], time: f32) {
        use cars_core::coord::{CJ_ADVISED, CJ_FIRM, CJ_PENDING, CJ_STATE_MASK};
        let Some(cw) = world.coord.as_ref() else { return };
        for &i in shown {
            let v = &snap.vs[i];
            let state = v.cj_state & CJ_STATE_MASK;
            let Some(li) = cw.lane_info.get(v.lane as usize) else { continue };
            if li.app == u32::MAX || (state != CJ_ADVISED && state != CJ_FIRM && state != CJ_PENDING) {
                continue;
            }
            let p = at(snap.poses[i].xy);
            let col = if state == CJ_FIRM { GREEN } else { AMBER };
            let ms = v.cj_t_ms;
            c.label(p[0] as i32 + 8, p[1] as i32 - 14, &format!("{}.{:03}", ms / 1000, ms % 1000), 1, col);
        }
        // Rows are approach lanes, the axis runs from now to 30 s ahead.
        let horizon = 30.0f32;
        let rows = cw.apps.len().min(16) as i32;
        let (w, row_h) = (c.w - 160, 12);
        let (x0, y0) = (120, c.h - 110 - rows * row_h);
        c.rect(x0 - 100, y0 - 26, w + 120, rows * row_h + 40, NAVY, 0.8);
        c.text(x0 - 90, y0 - 20, "slots: when each car has said it reaches the line. amber: planned, green: firm", 1, WHITE);
        for s in (0..=30).step_by(5) {
            let x = x0 + (s as f32 / horizon * w as f32) as i32;
            c.rect(x, y0 - 3, 1, rows * row_h + 3, WHITE, 0.25);
            c.text(x - 4, y0 + rows * row_h + 2, &format!("+{s}"), 1, [205, 212, 220]);
        }
        for (a, app) in cw.apps.iter().take(16).enumerate() {
            let _ = app;
            c.text(x0 - 90, y0 + a as i32 * row_h, &format!("lane {}", a + 1), 1, [205, 212, 220]);
        }
        for v in snap.vs.iter() {
            if v.flags & F_REMOVED != 0 || v.replica != 0 {
                continue;
            }
            let state = v.cj_state & CJ_STATE_MASK;
            if state != CJ_ADVISED && state != CJ_FIRM && state != CJ_PENDING {
                continue;
            }
            let Some(li) = cw.lane_info.get(v.lane as usize) else { continue };
            if li.app == u32::MAX || v.cj_link as usize >= cw.links.len() {
                continue;
            }
            let t = v.cj_t_ms as f32 * 0.001 - time;
            if !(0.0..=horizon).contains(&t) {
                continue;
            }
            let m = &cw.links[v.cj_link as usize];
            let dur = (m.path_len + 5.0) / v.cj_v_line.max(2.0);
            let row = (li.app as i32 - 0).min(rows - 1);
            let x = x0 + (t / horizon * w as f32) as i32;
            c.rect(x, y0 + row * row_h, ((dur / horizon * w as f32) as i32).clamp(3, x0 + w - x), row_h - 3, if state == CJ_FIRM { GREEN } else { AMBER }, 0.9);
        }
    }

    fn draw_coord(&mut self, c: &mut Canvas, at: &dyn Fn([f32; 2]) -> [f32; 2], world: &World, snap: &Snapshot, shown: &[usize], time: f32, modes: &[String]) {
        use cars_core::coord::{CJ_ADVISED, CJ_BOX, CJ_FIRM, CJ_PENDING, CJ_STATE_MASK};
        let Some(cw) = world.coord.as_ref() else { return };
        let on = |s: &str| modes.iter().any(|m| m == s || m == "all");
        let front = |i: usize| {
            let p = &snap.poses[i];
            [p.xy[0] + p.dir[0] * p.length * 0.5, p.xy[1] + p.dir[1] * p.length * 0.5]
        };
        let now = time;
        let info = |lane: u32| cw.lane_info.get(lane as usize).copied();
        let mut slots: Vec<(f32, f32, [u8; 3], &str)> = Vec::new();
        // The signal baseline: its lamps are the coordinator's own phase, drawn as stop bars.
        if on("grants") {
            for (ji, j) in cw.junctions.iter().enumerate() {
                if j.mode != cars_core::coord::MODE_SIGNAL {
                    continue;
                }
                let phase = snap.cj_phase.get(ji).copied().unwrap_or(0);
                for a in &cw.apps[j.app_start as usize..(j.app_start + j.app_count) as usize] {
                    let green = cw.links[a.mov_start as usize..(a.mov_start + a.mov_count) as usize].iter().any(|m| (m.group >> phase) & 1 != 0);
                    let m0 = &cw.links[a.mov_start as usize];
                    let p = cw.path[m0.path_start as usize];
                    let n = [-m0.dir_in[1] * 1.6, m0.dir_in[0] * 1.6];
                    c.line(at([p[0] + n[0], p[1] + n[1]]), at([p[0] - n[0], p[1] - n[1]]), 5.0, if green { GREEN } else { RED }, 1.0);
                }
            }
        }
        if on("channel") {
            for j in &cw.junctions {
                let q = at([j.cx, j.cy]);
                c.ring(q, 7.0, 2.0, WHITE, 0.9);
                c.ring(q, 13.0, 1.0, WHITE, 0.5);
            }
        }
        for &i in shown {
            let v = &snap.vs[i];
            let state = v.cj_state & CJ_STATE_MASK;
            let Some(li) = info(v.lane) else { continue };
            let in_box = li.box_mov != u32::MAX;
            let mi = if in_box { li.box_mov } else { v.cj_link };
            let color = match state {
                CJ_FIRM => GREEN,
                CJ_BOX => CYAN,
                CJ_ADVISED => AMBER,
                CJ_PENDING => MAGENTA,
                _ => SLATE,
            };
            if mi == u32::MAX || mi as usize >= cw.links.len() {
                continue;
            }
            let m = cw.links[mi as usize];
            let s = if in_box { li.s_offset + v.pos } else { v.pos - world.lanes[v.lane as usize].length };
            if on("paths") && (state == CJ_FIRM || state == CJ_BOX || state == CJ_PENDING) {
                let mut last = front(i);
                let alpha = if state == CJ_BOX { 0.55 } else { 0.8 };
                let step = 1.0;
                let mut x = s.max(0.0) + step;
                while x < m.path_len {
                    let p = coord_point(cw, mi, x);
                    c.line(at(last), at(p), 2.0, color, alpha);
                    last = p;
                    x += step;
                }
                c.line(at(last), at(coord_point(cw, mi, m.path_len)), 2.0, color, alpha);
                // The stretches of this path that a crossing foe also needs.
                for f in &cw.conflicts[m.conf_start as usize..(m.conf_start + m.conf_count) as usize] {
                    if f.s_out < s {
                        continue;
                    }
                    let (a, b) = (coord_point(cw, mi, f.s_in), coord_point(cw, mi, f.s_out));
                    c.line(at(a), at(b), 5.0, color, 0.28);
                }
            }
            if on("grants") {
                let p = at(snap.poses[i].xy);
                let t_left = v.cj_t_line - now;
                match state {
                    CJ_FIRM => {
                        c.ring(p, 11.0, 2.0, GREEN, 0.9);
                        c.label(p[0] as i32 + 13, p[1] as i32 - 16, &format!("slot {t_left:.1}s"), 1, GREEN);
                    }
                    CJ_ADVISED => {
                        c.ring(p, 11.0, 1.5, AMBER, 0.7);
                        let text = if t_left < 0.0 { "holding".to_string() } else { format!("{:.0} km/h {t_left:.0}s", v.cj_v_cruise * 3.6) };
                        c.label(p[0] as i32 + 13, p[1] as i32 - 16, &text, 1, AMBER);
                    }
                    CJ_PENDING => {
                        c.ring(p, 11.0, 2.0, MAGENTA, 1.0);
                        c.label(p[0] as i32 + 13, p[1] as i32 - 16, "GRANT LOST", 1, MAGENTA);
                    }
                    CJ_BOX => c.ring(p, 9.0, 1.5, CYAN, 0.8),
                    _ => {
                        if !in_box && li.app != u32::MAX && world.lanes[v.lane as usize].length - v.pos < 60.0 {
                            c.label(p[0] as i32 + 13, p[1] as i32 - 16, if v.speed < 0.5 { "holding" } else { "no grant" }, 1, SLATE);
                        }
                    }
                }
                if v.cj_state & 64 != 0 {
                    c.label(p[0] as i32 + 13, p[1] as i32 + 12, "STALLED", 2, RED);
                }
            }
            if on("channel") && (li.app != u32::MAX || in_box) {
                let j = &cw.junctions[m.junction as usize];
                let (a, b) = (at(snap.poses[i].xy), at([j.cx, j.cy]));
                let (col, al) = if state == CJ_PENDING { (MAGENTA, 0.9) } else if state == CJ_FIRM { (GREEN, 0.3) } else { (SLATE, 0.18) };
                c.line(a, b, 1.2, col, al);
            }
            if state == CJ_FIRM || state == CJ_PENDING {
                let width = (m.path_len + 5.0) / v.cj_v_line.max(2.0);
                let name = match state {
                    CJ_PENDING => "lost",
                    _ => "",
                };
                slots.push((v.cj_t_line - now, width, color, name));
            }
        }
        if on("grants") && !slots.is_empty() {
            slots.sort_by(|a, b| a.0.total_cmp(&b.0));
            let w = (c.w / 3).min(300);
            let (x0, y0) = (c.w - w - 30, 96);
            let horizon = 6.0;
            let rows = slots.len().min(16) as i32;
            c.rect(x0 - 8, y0 - 22, w + 16, rows * 11 + 30, NAVY, 0.72);
            c.text(x0, y0 - 16, if w < 300 { "slots, +6 s" } else { "granted slots, now to +6 s" }, 1, WHITE);
            for (r, (t, width, col, _)) in slots.iter().take(16).enumerate() {
                let bar_x = x0 + ((t.max(0.0) / horizon).min(1.0) * w as f32) as i32;
                let bar_w = ((width / horizon).min(1.0) * w as f32) as i32;
                c.rect(bar_x, y0 + r as i32 * 11, bar_w.min(x0 + w - bar_x).max(2), 8, *col, 0.9);
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn draw(&mut self, c: &mut Canvas, cam: Camera, net: &Net, world: &World, snap: &Snapshot, time: f32, modes: &[String]) {
        let on = |s: &str| modes.iter().any(|m| m == s || m == "all");
        let (w, h) = (c.w as f32, c.h as f32);
        let mpp = cam.metres_per_pixel;
        let at = |p: [f32; 2]| [w * 0.5 + (p[0] - cam.center[0]) / mpp, h * 0.5 - (p[1] - cam.center[1]) / mpp];
        let visible = |p: [f32; 2]| {
            let q = at(p);
            q[0] > -60.0 && q[1] > -60.0 && q[0] < w + 60.0 && q[1] < h + 60.0
        };
        let scale = if mpp < 0.16 { 2 } else { 1 };
        let mut shown = Vec::new();
        for (i, v) in snap.vs.iter().enumerate() {
            if v.lane == world.params.dummy_lane {
                if on("events")
                    && let Some(p) = self.previous.remove(&v.trip)
                {
                    let collided = snap.collided.as_ref().map_or(snap.collisions > self.collisions, |set| set.contains(&v.trip));
                    let name = if collided { "COLLISION" } else { "TELEPORT" };
                    eprintln!("event {time:.1} {name} at {:.1},{:.1}", p[0], p[1]);
                    self.flashes.push((p, time, name));
                }
                continue;
            }
            if v.flags & (F_REMOVED | crate::report::F_SHADOW) != 0 || v.replica != 0 || i >= snap.poses.len() || snap.poses[i].alive < 0.5 {
                continue;
            }
            if visible(snap.poses[i].xy) {
                shown.push(i);
                self.previous.insert(v.trip, snap.poses[i].xy);
            }
        }
        self.collisions = snap.collisions;
        let front = |i: usize| {
            let p = &snap.poses[i];
            [p.xy[0] + p.dir[0] * p.length * 0.5, p.xy[1] + p.dir[1] * p.length * 0.5]
        };
        let rear = |i: usize| {
            let p = &snap.poses[i];
            [p.xy[0] - p.dir[0] * p.length * 0.5, p.xy[1] - p.dir[1] * p.length * 0.5]
        };
        if on("foes") {
            let mut drawn = std::collections::HashSet::new();
            for &i in &shown {
                let v = &snap.vs[i];
                let on_junction = v.flags & F_ON_JUNCTION != 0 || world.lanes[v.lane as usize].flags & 1 != 0;
                let item = &snap.items[i * 8];
                let near = v.flags & F_WILL_PASS != 0 && v.n_items > 0 && item[0] != NONE && f32::from_bits(item[7]) < 40.0;
                if !on_junction && !near {
                    continue;
                }
                let link = if on_junction { world.lanes[v.lane as usize].entry_link } else { item[0] };
                let Some(l) = world.links.get(link as usize) else {
                    continue;
                };
                if !drawn.insert(link) && !on_junction {
                    continue;
                }
                let shape = &net.lanes[l.next_lane as usize].shape;
                for s in shape.windows(2) {
                    c.line(at(s[0]), at(s[1]), 1.5, WHITE, 0.4);
                }
                for cf in &world.conflicts[l.conf_start as usize..(l.conf_start + l.conf_count) as usize] {
                    let length = net.lanes[l.next_lane as usize].length;
                    let cross = if cf.len_behind > -1000.0 { pose(net, l.next_lane, length - cf.len_behind) } else { None };
                    let Some(list) = snap.by_lane.get(&cf.foe_lane) else {
                        continue;
                    };
                    let Some((x, _)) = cross else {
                        continue;
                    };
                    for &k in list {
                        if snap.poses.get(k).is_none_or(|p| p.alive < 0.5) {
                            continue;
                        }
                        c.line(at(front(i)), at(x), 1.5, MAGENTA, 0.8);
                        c.line(at(front(k)), at(x), 1.5, MAGENTA, 0.8);
                        c.ring(at(x), 5.0, 2.0, MAGENTA, 1.0);
                    }
                }
                for &foe in &world.foes[l.foe_start as usize..(l.foe_start + l.foe_count) as usize] {
                    let f = &world.links[foe as usize];
                    let Some(&k) = snap.by_lane.get(&f.from_lane).and_then(|s| s.last()) else {
                        continue;
                    };
                    let o = &snap.vs[k];
                    if k >= snap.poses.len() || o.flags & F_WILL_PASS == 0 || net.lanes[f.from_lane as usize].length - o.pos > 40.0 {
                        continue;
                    }
                    let (a, b) = (front(i), front(k));
                    if (a[0] - b[0]).hypot(a[1] - b[1]) > 60.0 {
                        continue;
                    }
                    let mid = [(a[0] + b[0]) * 0.5 - (b[1] - a[1]) * 0.15, (a[1] + b[1]) * 0.5 + (b[0] - a[0]) * 0.15];
                    c.line(at(a), at(mid), 1.5, MAGENTA, 0.45);
                    c.line(at(mid), at(b), 1.5, MAGENTA, 0.45);
                }
            }
        }
        if on("grants") || on("paths") || on("channel") {
            self.draw_coord(c, &at, world, snap, &shown, time, modes);
        }
        if on("brake") {
            self.draw_brake(c, &at, world, snap, &shown, mpp);
        }
        if on("arrivals") {
            self.draw_arrivals(c, &at, world, snap, &shown, time);
        }
        for &i in &shown {
            let v = &snap.vs[i];
            let t = &world.vtypes[v.vtype as usize];
            let leader = (on("leader") || on("braking") || on("events")).then(|| leader_of(net, world, snap, i, 60.0)).flatten();
            if on("braking") && v.speed > 0.5 {
                let stop = v.speed * v.speed / (2.0 * t.decel.max(0.1));
                let panic = v.speed * v.speed / (2.0 * t.emergency.max(0.1));
                let envelope = stop + t.min_gap;
                let conflict = leader.is_some_and(|(_, g)| g < envelope * 0.7);
                let color = if conflict { RED } else { AMBER };
                let path = walk_ahead(net, world, snap, i, envelope);
                let mut last = front(i);
                for p in path.iter().skip(1) {
                    c.line(at(last), at(*p), snap.poses[i].width / mpp * 0.8, color, 0.22);
                    last = *p;
                }
                let tick = walk_ahead(net, world, snap, i, panic);
                if let (Some(p), true) = (tick.last(), panic > 0.5) {
                    let n = [-snap.poses[i].dir[1], snap.poses[i].dir[0]];
                    let half = snap.poses[i].width * 0.5;
                    c.line(at([p[0] + n[0] * half, p[1] + n[1] * half]), at([p[0] - n[0] * half, p[1] - n[1] * half]), 2.0, RED, 0.8);
                }
            }
            if on("leader")
                && let Some((k, gap)) = leader
                && k < snap.poses.len()
                && snap.poses[k].alive > 0.5
            {
                let (a, b) = (at(front(i)), at(rear(k)));
                c.line(a, b, 2.0, if gap < 0.0 { RED } else { CYAN }, 0.9);
                c.ring(b, 3.0, 1.5, CYAN, 0.9);
                if on("speed") && gap < 40.0 && v.speed > 0.5 {
                    let mid = [(a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5];
                    c.label(mid[0] as i32 + 5, mid[1] as i32 - 5, &format!("{gap:.1}m"), 1, CYAN);
                }
            }
            if on("events") {
                if let Some((k, gap)) = leader
                    && gap < -0.05
                    && k < snap.poses.len()
                {
                    let p = rear(k);
                    eprintln!("event {time:.1} GAP {gap:.2} at {:.1},{:.1}", p[0], p[1]);
                    self.flashes.push((p, time, "OVERLAP"));
                }
            }
        }
        if on("events") {
            for a in 0..shown.len() {
                for b in a + 1..shown.len() {
                    let (i, k) = (shown[a], shown[b]);
                    let (la, lb) = (snap.vs[i].lane, snap.vs[k].lane);
                    if la == lb || world.lanes[la as usize].flags & 1 == 0 || world.lanes[lb as usize].flags & 1 == 0 {
                        continue;
                    }
                    if rectangles_touch(&snap.poses[i], &snap.poses[k]) {
                        let (p, q) = (snap.poses[i].xy, snap.poses[k].xy);
                        let m = [(p[0] + q[0]) * 0.5, (p[1] + q[1]) * 0.5];
                        eprintln!("event {time:.1} BODY at {:.1},{:.1}", m[0], m[1]);
                        self.flashes.push((m, time, "OVERLAP"));
                    }
                }
            }
        }
        for &i in &shown {
            let v = &snap.vs[i];
            let pose_now = &snap.poses[i];
            let p = at(pose_now.xy);
            let upright = pose_now.dir[1].abs() > pose_now.dir[0].abs();
            let x = if upright { p[0] + pose_now.width * 0.5 / mpp + 4.0 } else { p[0] - 14.0 } as i32;
            let mut y = if upright { p[1] - 8.0 } else { p[1] - pose_now.width * 0.5 / mpp - 12.0 } as i32;
            if on("speed") && v.speed > 0.1 {
                c.label(x, y, &format!("{:.0}", v.speed * 3.6), scale, WHITE);
                y -= 10;
            }
            if on("state") {
                let on_junction = v.flags & F_ON_JUNCTION != 0 || world.lanes[v.lane as usize].flags & 1 != 0;
                let item = &snap.items[i * 8];
                let dist = f32::from_bits(item[7]);
                let state = |link: u32| {
                    world.links.get(link as usize).map_or('-', |l| l.state as u8 as char)
                };
                let (text, color) = if on_junction {
                    ("IN".to_string(), SLATE)
                } else if v.n_items == 0 || item[0] == NONE || dist > 100.0 {
                    (String::new(), SLATE)
                } else if v.flags & F_HAVE_TO_WAIT != 0 {
                    (format!("WAIT {} {:.0}", state(item[0]), dist), ORANGE)
                } else if v.flags & F_WILL_PASS != 0 {
                    (format!("GO {} {:.0}", state(item[0]), dist), GREEN)
                } else {
                    (format!("APPR {} {:.0}", state(item[0]), dist), SLATE)
                };
                if !text.is_empty() {
                    c.label(x, y, &text, 1, color);
                }
                if v.acc < -4.6 {
                    y -= 10;
                    c.label(x, y, &format!("{:.1} m/s2", v.acc), 1, RED);
                }
                if v.lc_own & 3 != 0 {
                    y -= 10;
                    let side = if v.lc_own & 1 != 0 { "wants L" } else { "wants R" };
                    c.label(x, y, side, 1, AMBER);
                }
            }
        }
        self.flashes.retain(|f| time - f.1 < 3.0);
        for &(p, t, name) in &self.flashes.clone() {
            if ((time - t) * 4.0) as i32 % 2 == 1 {
                continue;
            }
            let q = at(p);
            c.ring(q, 22.0, 4.0, RED, 1.0);
            c.line([q[0] - 14.0, q[1] - 14.0], [q[0] + 14.0, q[1] + 14.0], 3.0, RED, 1.0);
            c.line([q[0] - 14.0, q[1] + 14.0], [q[0] + 14.0, q[1] - 14.0], 3.0, RED, 1.0);
            c.label(q[0] as i32 + 26, q[1] as i32 - 8, name, 2, RED);
        }
    }
}

pub struct Hud<'a> {
    pub title: &'a str,
    pub subtitle: &'a str,
    pub clock: f32,
    pub count: u32,
    pub speed: f32,
    pub mpp: f32,
    pub teleports: Option<u32>,
    pub collisions: Option<u32>,
    pub trips: Option<u32>,
    pub modes: &'a [String],
}

pub fn draw_hud(c: &mut Canvas, hud: &Hud) {
    let (w, h) = (c.w, c.h);
    let fit = |s: &str, scale: i32| -> String {
        let room = ((w - 48) / (6 * scale)).max(4) as usize;
        if s.chars().count() <= room { s.to_string() } else { s.chars().take(room - 3).chain("...".chars()).collect() }
    };
    if !hud.title.is_empty() {
        c.label(24, 22, &fit(hud.title, 3), 3, WHITE);
    }
    if !hud.subtitle.is_empty() {
        c.label(24, 56, &fit(hud.subtitle, 2), 2, [205, 212, 220]);
    }
    let t = hud.clock.max(0.0);
    let line = format!(
        "{:02}:{:02}:{:04.1}  {} vehicles  mean {:.0} km/h",
        (t / 3600.0) as u32 % 24,
        (t / 60.0) as u32 % 60,
        t % 60.0,
        hud.count,
        hud.speed * 3.6
    );
    c.label(24, h - 40, &line, 2, WHITE);
    if let (Some(a), Some(b)) = (hud.teleports, hud.collisions) {
        let color = if a + b > 0 { RED } else { [170, 180, 190] };
        let trips = hud.trips.map_or(String::new(), |t| format!("  {t} trips"));
        let text = if w < 900 { format!("teleports {a} collisions {b}{trips}") } else { format!("teleports {a}  collisions {b} in this clip{trips} done") };
        c.label(24, h - 64, &text, 2, color);
    }
    let on = |s: &str| hud.modes.iter().any(|m| m == s || m == "all");
    let mut y = h - 88;
    for (name, text, color) in [
        ("braking", "amber band: stops at decel + min gap, red tick: emergency stop", AMBER),
        ("leader", "cyan: leader link, bumper to bumper gap", CYAN),
        ("foes", "magenta: foe vehicles and crossing points of active links", MAGENTA),
        ("state", "WAIT/GO/APPR, link state, metres to link", GREEN),
        ("speed", "white: km/h", WHITE),
        ("events", "red marker: teleport, collision or body overlap", RED),
        ("grants", "green: firm slot, amber: speed advice, magenta: grant lost, cyan: in the box, grey: no grant", GREEN),
        ("paths", "lines: planned paths through the box, wide: stretches shared with a crossing foe", CYAN),
        ("channel", "white rings: coordinator, lines: messages, magenta: lost grant being resent", WHITE),
    ] {
        if on(name) && w >= 900 {
            c.label(24, y, text, 1, color);
            y -= 14;
        }
    }
    let nice = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0];
    let metres = nice.iter().copied().find(|m| m / hud.mpp > 90.0).unwrap_or(1000.0);
    let px = (metres / hud.mpp) as i32;
    let x = w - 40 - px;
    // A narrow frame has no room beside the text, so the bar moves above it.
    let lift = if w < 900 { 80 } else { 0 };
    c.rect(x - 8, h - 66 - lift, px + 16, 44, [8, 8, 10], 0.55);
    c.rect(x, h - 34 - lift, px, 5, WHITE, 1.0);
    c.rect(x, h - 40 - lift, 3, 11, WHITE, 1.0);
    c.rect(x + px - 3, h - 40 - lift, 3, 11, WHITE, 1.0);
    c.text(x, h - 60 - lift, &format!("{metres:.0} m"), 2, WHITE);
}
