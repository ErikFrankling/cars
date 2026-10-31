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
    [8,0x7e,9,1,2],[0xc,0x52,0x52,0x52,0x3e],[0x7f,8,4,4,0x78],[0,0x44,0x7d,0x40,0],[0x20,0x40,0x44,0x3d,0],
    [0x7f,0x10,0x28,0x44,0],[0,0x41,0x7f,0x40,0],[0x7c,4,0x18,4,0x78],[0x7c,8,4,4,0x78],[0x38,0x44,0x44,0x44,0x38],
    [0x7c,0x14,0x14,0x14,8],[8,0x14,0x14,0x18,0x7c],[0x7c,8,4,4,8],[0x48,0x54,0x54,0x54,0x20],[4,0x3f,0x44,0x40,0x20],
    [0x3c,0x40,0x40,0x20,0x7c],[0x1c,0x20,0x40,0x20,0x1c],[0x3c,0x40,0x30,0x40,0x3c],[0x44,0x28,0x10,0x28,0x44],[0xc,0x50,0x50,0x50,0x3c],
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
            step: u64::MAX,
        }
    }
    pub fn update(&mut self, g: &Gpu, sim: &Sim, r: &Renderer) {
        if self.step != sim.step {
            self.step = sim.step;
            self.vs = sim.vehicles(g);
            self.items = sim.read(g, &sim.buffers.items, self.vs.len() as u64 * 8);
            self.by_lane.clear();
            for (i, v) in self.vs.iter().enumerate() {
                if v.flags & F_REMOVED == 0 && v.replica == 0 {
                    self.by_lane.entry(v.lane).or_default().push(i);
                }
            }
            let vs = &self.vs;
            for list in self.by_lane.values_mut() {
                list.sort_by(|&a, &b| vs[a].pos.total_cmp(&vs[b].pos));
            }
            let c = sim.counters(g);
            self.teleports = c[4];
            self.collisions = c[7];
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

impl Overlay {
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
                    let collided = snap.collisions > self.collisions;
                    self.flashes.push((p, time, if collided { "COLLISION" } else { "TELEPORT" }));
                }
                continue;
            }
            if v.flags & F_REMOVED != 0 || v.replica != 0 || i >= snap.poses.len() || snap.poses[i].alive < 0.5 {
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
                let near = v.n_items > 0 && item[0] != NONE && f32::from_bits(item[7]) < 40.0;
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
                    if k >= snap.poses.len() || net.lanes[f.from_lane as usize].length - o.pos > 40.0 {
                        continue;
                    }
                    let (a, b) = (front(i), front(k));
                    let mid = [(a[0] + b[0]) * 0.5 - (b[1] - a[1]) * 0.15, (a[1] + b[1]) * 0.5 + (b[0] - a[0]) * 0.15];
                    c.line(at(a), at(mid), 1.5, MAGENTA, 0.45);
                    c.line(at(mid), at(b), 1.5, MAGENTA, 0.45);
                }
            }
        }
        for &i in &shown {
            let v = &snap.vs[i];
            let t = &world.vtypes[v.vtype as usize];
            let leader = (on("leader") || on("braking") || on("events")).then(|| leader_of(net, world, snap, i, 200.0)).flatten();
            if on("braking") {
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
                if on("speed") && gap < 40.0 {
                    let mid = [(a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5];
                    c.label(mid[0] as i32 + 5, mid[1] as i32 - 5, &format!("{gap:.1}m"), 1, CYAN);
                }
            }
            if on("events") {
                if let Some((k, gap)) = leader
                    && gap < -0.05
                    && k < snap.poses.len()
                {
                    self.flashes.push((rear(k), time, "OVERLAP"));
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
                        self.flashes.push(([(p[0] + q[0]) * 0.5, (p[1] + q[1]) * 0.5], time, "OVERLAP"));
                    }
                }
            }
        }
        for &i in &shown {
            let v = &snap.vs[i];
            let p = at(snap.poses[i].xy);
            let mut y = p[1] as i32 - 16 * scale;
            let x = p[0] as i32 + 5 * scale;
            if on("speed") {
                c.label(x, y, &format!("{:.0}", v.speed * 3.6), scale, WHITE);
                y -= 10 * scale;
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
                    (format!("WAIT {} {:.0}m", state(item[0]), dist), ORANGE)
                } else if v.flags & F_WILL_PASS != 0 {
                    (format!("GO {} {:.0}m", state(item[0]), dist), GREEN)
                } else {
                    (format!("APPR {} {:.0}m", state(item[0]), dist), SLATE)
                };
                if !text.is_empty() {
                    c.label(x, y, &text, scale, color);
                }
                if v.acc < -4.6 {
                    y -= 10 * scale;
                    c.label(x, y, &format!("{:.1} m/s2", v.acc), scale, RED);
                }
                if v.lc_own & 3 != 0 {
                    y -= 10 * scale;
                    let side = if v.lc_own & 1 != 0 { "LC <" } else { "LC >" };
                    c.label(x, y, side, scale, AMBER);
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
    pub modes: &'a [String],
}

pub fn draw_hud(c: &mut Canvas, hud: &Hud) {
    let (w, h) = (c.w, c.h);
    if !hud.title.is_empty() {
        c.label(24, 22, hud.title, 3, WHITE);
    }
    if !hud.subtitle.is_empty() {
        c.label(24, 56, hud.subtitle, 2, [205, 212, 220]);
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
        c.label(24, h - 64, &format!("teleports {a}  collisions {b} in this clip"), 2, color);
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
    ] {
        if on(name) {
            c.label(24, y, text, 1, color);
            y -= 14;
        }
    }
    let nice = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0];
    let metres = nice.iter().copied().find(|m| m / hud.mpp > 90.0).unwrap_or(1000.0);
    let px = (metres / hud.mpp) as i32;
    let x = w - 40 - px;
    c.rect(x - 8, h - 66, px + 16, 44, [8, 8, 10], 0.55);
    c.rect(x, h - 34, px, 5, WHITE, 1.0);
    c.rect(x, h - 40, 3, 11, WHITE, 1.0);
    c.rect(x + px - 3, h - 40, 3, 11, WHITE, 1.0);
    c.text(x, h - 60, &format!("{metres:.0} m"), 2, WHITE);
}
