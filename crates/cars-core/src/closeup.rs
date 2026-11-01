//! Road surface for close-up views: asphalt, kerbs, markings and signs for one region of the net.
use crate::net::{EdgeFunc, Net, vclass_mask};

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
pub struct Vertex {
    xy: [f32; 2],
    normal: [f32; 2],
    width: f32,
    /// Dash cycles along the line, and the lit fraction of a cycle. 0 means solid.
    dash: [f32; 2],
    color: u32,
}

const fn rgb(r: u8, g: u8, b: u8) -> u32 {
    r as u32 | (g as u32) << 8 | (b as u32) << 16 | 255 << 24
}
const GROUND: u32 = rgb(70, 82, 60);
const VERGE: u32 = rgb(92, 96, 80);
const KERB: u32 = rgb(150, 150, 142);
const SIDEWALK: u32 = rgb(122, 120, 112);
const BIKE: u32 = rgb(112, 70, 62);
const BALLAST: u32 = rgb(88, 80, 72);
const ASPHALT: u32 = rgb(52, 54, 58);
const JUNCTION: u32 = rgb(60, 61, 65);
const WHITE: u32 = rgb(232, 232, 226);
const RED: u32 = rgb(205, 30, 30);
const YELLOW: u32 = rgb(250, 200, 30);
const AMBER: u32 = rgb(240, 150, 40);

#[derive(Clone, Copy, Default)]
pub struct Approach {
    dirs: u8,
    signal: bool,
    major: bool,
    minor: bool,
    stop: bool,
    equal: bool,
    zipper: bool,
}

const LEFT: u8 = 1;
const STRAIGHT: u8 = 2;
const RIGHT: u8 = 4;

/// What every lane's outgoing connections say about its stop line and arrows.
pub fn approaches(net: &Net) -> Vec<Approach> {
    let mut out = vec![Approach::default(); net.lanes.len()];
    for c in &net.conns {
        let Some(lane) = net.lane_of(c.from_edge, c.from_lane) else {
            continue;
        };
        let a = &mut out[lane as usize];
        a.dirs |= match c.dir {
            b'l' | b'L' | b't' | b'T' => LEFT,
            b'r' | b'R' => RIGHT,
            _ => STRAIGHT,
        };
        a.signal |= c.tl.is_some();
        match c.state {
            b'M' | b'O' => a.major = true,
            b'm' => a.minor = true,
            b's' | b'w' => a.stop = true,
            b'=' => a.equal = true,
            b'Z' => a.zipper = true,
            _ => {}
        }
    }
    out
}

fn sub(a: [f32; 2], b: [f32; 2]) -> [f32; 2] {
    [a[0] - b[0], a[1] - b[1]]
}
fn add(a: [f32; 2], b: [f32; 2], k: f32) -> [f32; 2] {
    [a[0] + b[0] * k, a[1] + b[1] * k]
}
fn len(a: [f32; 2]) -> f32 {
    a[0].hypot(a[1])
}
fn unit(a: [f32; 2]) -> [f32; 2] {
    let d = len(a).max(1e-5);
    [a[0] / d, a[1] / d]
}
fn left(a: [f32; 2]) -> [f32; 2] {
    [-a[1], a[0]]
}

/// Point and tangent at a distance along a polyline.
fn along(shape: &[[f32; 2]], mut d: f32) -> ([f32; 2], [f32; 2]) {
    for p in shape.windows(2) {
        let s = len(sub(p[1], p[0]));
        if d <= s || std::ptr::eq(&p[1], shape.last().unwrap()) {
            let t = unit(sub(p[1], p[0]));
            return (add(p[0], t, d.min(s)), t);
        }
        d -= s;
    }
    (shape[0], [1.0, 0.0])
}

fn length(shape: &[[f32; 2]]) -> f32 {
    shape.windows(2).map(|p| len(sub(p[1], p[0]))).sum()
}

/// The part of a polyline between two distances.
fn slice(shape: &[[f32; 2]], a: f32, b: f32) -> Vec<[f32; 2]> {
    let mut out = vec![along(shape, a).0];
    let mut d = 0.0;
    for p in shape.windows(2) {
        d += len(sub(p[1], p[0]));
        if d > a + 0.01 && d < b - 0.01 {
            out.push(p[1]);
        }
    }
    out.push(along(shape, b).0);
    out
}

fn tri(out: &mut Vec<Vertex>, a: [f32; 2], b: [f32; 2], c: [f32; 2], color: u32) {
    for xy in [a, b, c] {
        out.push(Vertex { xy, normal: [0.0; 2], width: 0.0, dash: [0.0; 2], color });
    }
}

/// A strip along a polyline, offset to its left, with mitred joints so curves have no gaps.
fn ribbon(out: &mut Vec<Vertex>, shape: &[[f32; 2]], offset: f32, width: f32, color: u32, dash: Option<(f32, f32)>) {
    let mut pts: Vec<[f32; 2]> = Vec::with_capacity(shape.len());
    for &p in shape {
        if pts.last().is_none_or(|q| len(sub(p, *q)) > 0.01) {
            pts.push(p);
        }
    }
    if pts.len() < 2 {
        return;
    }
    let n = pts.len();
    let normals: Vec<[f32; 2]> = (0..n)
        .map(|i| {
            let a = left(unit(sub(pts[i.min(n - 2) + 1], pts[i.min(n - 2)])));
            let b = left(unit(sub(pts[i.max(1)], pts[i.max(1) - 1])));
            let m = unit([a[0] + b[0], a[1] + b[1]]);
            let c = (m[0] * a[0] + m[1] * a[1]).max(0.5);
            [m[0] / c, m[1] / c]
        })
        .collect();
    let (period, lit) = dash.unwrap_or((1.0, 0.0));
    let mut d = 0.0;
    for i in 0..n - 1 {
        let s = len(sub(pts[i + 1], pts[i]));
        let (a, b) = (add(pts[i], normals[i], offset), add(pts[i + 1], normals[i + 1], offset));
        let (ca, cb) = (d / period, (d + s) / period);
        for (xy, normal, cycles, side) in [
            (a, normals[i], ca, -1.0),
            (b, normals[i + 1], cb, -1.0),
            (a, normals[i], ca, 1.0),
            (a, normals[i], ca, 1.0),
            (b, normals[i + 1], cb, -1.0),
            (b, normals[i + 1], cb, 1.0),
        ] {
            out.push(Vertex {
                xy,
                normal: [normal[0] * side, normal[1] * side],
                width,
                dash: [cycles, lit],
                color,
            });
        }
        d += s;
    }
}

fn area(p: &[[f32; 2]]) -> f32 {
    let mut a = 0.0;
    for i in 0..p.len() {
        let (u, v) = (p[i], p[(i + 1) % p.len()]);
        a += u[0] * v[1] - v[0] * u[1];
    }
    a * 0.5
}

/// Ear clipping. Junction outlines are often concave, where a fan would paint over the kerb.
fn fill(out: &mut Vec<Vertex>, shape: &[[f32; 2]], color: u32) {
    let mut p: Vec<[f32; 2]> = Vec::with_capacity(shape.len());
    for &q in shape {
        if p.last().is_none_or(|l| len(sub(q, *l)) > 0.01) {
            p.push(q);
        }
    }
    if p.len() > 1 && len(sub(p[0], p[p.len() - 1])) < 0.01 {
        p.pop();
    }
    if area(&p) < 0.0 {
        p.reverse();
    }
    let cross = |a: [f32; 2], b: [f32; 2], c: [f32; 2]| (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    while p.len() > 3 {
        let n = p.len();
        let ear = (0..n).find(|&i| {
            let (a, b, c) = (p[(i + n - 1) % n], p[i], p[(i + 1) % n]);
            cross(a, b, c) > 1e-5
                && !p.iter().any(|&q| {
                    q != a && q != b && q != c && cross(a, b, q) >= 0.0 && cross(b, c, q) >= 0.0 && cross(c, a, q) >= 0.0
                })
        });
        // A polygon that crosses itself has no ear left: fall back on the first corner.
        let i = ear.unwrap_or(0);
        tri(out, p[(i + n - 1) % n], p[i], p[(i + 1) % n], color);
        p.remove(i);
    }
    if p.len() == 3 {
        tri(out, p[0], p[1], p[2], color);
    }
}

fn overlaps(b: [f32; 4], shape: &[[f32; 2]]) -> bool {
    let mut q = [f32::MAX, f32::MAX, f32::MIN, f32::MIN];
    for p in shape {
        q = [q[0].min(p[0]), q[1].min(p[1]), q[2].max(p[0]), q[3].max(p[1])];
    }
    q[0] <= b[2] && q[2] >= b[0] && q[1] <= b[3] && q[3] >= b[1]
}

/// Stroke in the frame of an arrow painted on the road: x forward, y to the left, metres.
struct Paint<'a> {
    out: &'a mut Vec<Vertex>,
    at: [f32; 2],
    t: [f32; 2],
    color: u32,
}
impl Paint<'_> {
    fn p(&self, x: f32, y: f32) -> [f32; 2] {
        add(add(self.at, self.t, x), left(self.t), y)
    }
    fn stroke(&mut self, a: [f32; 2], b: [f32; 2], width: f32) {
        let pts = [self.p(a[0], a[1]), self.p(b[0], b[1])];
        ribbon(self.out, &pts, 0.0, width, self.color, None);
    }
    fn tri(&mut self, a: [f32; 2], b: [f32; 2], c: [f32; 2]) {
        let (a, b, c) = (self.p(a[0], a[1]), self.p(b[0], b[1]), self.p(c[0], c[1]));
        tri(self.out, a, b, c, self.color);
    }
}

fn arrow(out: &mut Vec<Vertex>, at: [f32; 2], t: [f32; 2], dirs: u8) {
    let mut pen = Paint { out, at, t, color: WHITE };
    pen.stroke([0.0, 0.0], [2.2, 0.0], 0.18);
    if dirs & STRAIGHT != 0 {
        pen.stroke([2.2, 0.0], [3.6, 0.0], 0.18);
        pen.tri([5.0, 0.0], [3.6, 0.42], [3.6, -0.42]);
    }
    for (bit, side) in [(LEFT, 1.0), (RIGHT, -1.0)] {
        if dirs & bit != 0 {
            pen.stroke([1.8, 0.0], [2.9, 0.62 * side], 0.18);
            pen.tri([3.45, 1.45 * side], [3.2, 0.32 * side], [2.45, 0.92 * side]);
        }
    }
}

fn sign(out: &mut Vec<Vertex>, at: [f32; 2], t: [f32; 2], a: &Approach) {
    let n = left(t);
    let p = |x: f32, y: f32| add(add(at, t, x), n, y);
    if a.stop && !a.major {
        for (radius, color) in [(1.05, WHITE), (0.9, RED)] {
            for i in 0..8 {
                let u = (i as f32 + 0.5) * std::f32::consts::FRAC_PI_4;
                let v = u + std::f32::consts::FRAC_PI_4;
                tri(out, at, p(u.cos() * radius, u.sin() * radius), p(v.cos() * radius, v.sin() * radius), color);
            }
        }
    } else if a.minor && !a.major {
        for (radius, color) in [(1.2, RED), (0.72, WHITE)] {
            tri(out, p(-radius, 0.0), p(radius * 0.72, radius), p(radius * 0.72, -radius), color);
        }
    } else if a.major {
        for (radius, color) in [(1.05, WHITE), (0.75, YELLOW)] {
            tri(out, p(radius, 0.0), p(0.0, radius), p(0.0, -radius), color);
            tri(out, p(-radius, 0.0), p(0.0, -radius), p(0.0, radius), color);
        }
    }
}

/// Everything in `region`, back to front, so a plain painter's pass gets the layers right.
pub fn build(net: &Net, approaches: &[Approach], region: [f32; 4]) -> Vec<Vertex> {
    let (mut under, mut asphalt, mut paint, mut signs) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let ground = [[region[0], region[1]], [region[2], region[1]], [region[2], region[3]], [region[0], region[3]]];
    tri(&mut under, ground[0], ground[1], ground[2], GROUND);
    tri(&mut under, ground[0], ground[2], ground[3], GROUND);
    let pedestrian = vclass_mask("pedestrian");
    let bicycle = vclass_mask("bicycle");
    let road_mask = vclass_mask("passenger bus truck taxi delivery emergency motorcycle");
    #[derive(PartialEq, Clone, Copy)]
    enum Kind {
        Road,
        Walk,
        Bike,
        Rail,
    }
    let kind = |allow: u32| {
        if allow & road_mask != 0 {
            Kind::Road
        } else if allow & bicycle != 0 {
            Kind::Bike
        } else if allow & pedestrian != 0 {
            Kind::Walk
        } else {
            Kind::Rail
        }
    };
    for j in &net.junctions {
        if j.shape.len() < 3 || !overlaps(region, &j.shape) {
            continue;
        }
        let mut ring = j.shape.clone();
        if ring.first() != ring.last() {
            ring.push(ring[0]);
        }
        ribbon(&mut under, &ring, 0.0, 3.6, VERGE, None);
        ribbon(&mut under, &ring, 0.0, 1.0, KERB, None);
        fill(&mut asphalt, &j.shape, JUNCTION);
    }
    for e in &net.edges {
        let lanes = &net.lanes[e.first_lane as usize..(e.first_lane + e.lane_count) as usize];
        if lanes.iter().all(|l| l.shape.len() < 2 || !overlaps(region, &l.shape)) {
            continue;
        }
        match e.func {
            EdgeFunc::Pedestrian => {
                // A crossing is a zebra; walking areas are left to the junction surface.
                if e.id.contains('c') && e.lane_count == 1 && lanes[0].shape.len() == 2 && lanes[0].allow == pedestrian {
                    let mut across = Vec::new();
                    let l = &lanes[0];
                    let t = unit(sub(l.shape[1], l.shape[0]));
                    let n = left(t);
                    let total = length(&l.shape);
                    let mut d = 0.5;
                    while d < total {
                        let c = add(l.shape[0], t, d);
                        across.extend(ribbon_quad(add(c, n, -l.width * 0.5), add(c, n, l.width * 0.5), 0.5, WHITE));
                        d += 1.0;
                    }
                    paint.extend(across);
                }
                continue;
            }
            EdgeFunc::Internal => {
                for l in lanes {
                    ribbon(&mut asphalt, &l.shape, 0.0, l.width + 0.02, JUNCTION, None);
                }
                continue;
            }
            _ => {}
        }
        let kinds: Vec<Kind> = lanes.iter().map(|l| kind(l.allow)).collect();
        let to = net.junction_index.get(&e.to).map(|&j| &net.junctions[j as usize]);
        let contested = to.is_some_and(|j| j.requests.iter().any(|r| r.foes.iter().any(|f| *f)) || j.jtype.starts_with("traffic_light"));
        for (i, l) in lanes.iter().enumerate() {
            if l.shape.len() < 2 {
                continue;
            }
            let total = length(&l.shape);
            let color = match kinds[i] {
                Kind::Road => ASPHALT,
                Kind::Walk => SIDEWALK,
                Kind::Bike => BIKE,
                Kind::Rail => BALLAST,
            };
            ribbon(&mut asphalt, &l.shape, 0.0, l.width + 0.02, color, None);
            if i == 0 {
                ribbon(&mut under, &l.shape, -l.width * 0.5 - 1.0, 2.2, VERGE, None);
                ribbon(&mut under, &l.shape, -l.width * 0.5 - 0.1, 0.5, KERB, None);
            }
            if i + 1 == lanes.len() {
                ribbon(&mut under, &l.shape, l.width * 0.5 + 1.0, 2.2, VERGE, None);
                ribbon(&mut under, &l.shape, l.width * 0.5 + 0.1, 0.5, KERB, None);
            }
            if kinds[i] != Kind::Road {
                if i + 1 < lanes.len() && kinds[i + 1] == Kind::Road {
                    ribbon(&mut paint, &l.shape, l.width * 0.5, 0.25, if kinds[i] == Kind::Walk { KERB } else { WHITE }, None);
                }
                continue;
            }
            let fast = l.speed > 22.0;
            let solid_from = if contested { (total - 22.0).max(total * 0.45) } else { total };
            if i == 0 {
                let inset = -l.width * 0.5 + 0.14;
                ribbon(&mut paint, &l.shape, inset, 0.14, WHITE, None);
            }
            if i + 1 == lanes.len() {
                let inset = l.width * 0.5 - 0.14;
                ribbon(&mut paint, &l.shape, inset, 0.14, WHITE, None);
            } else if kinds[i + 1] == Kind::Road {
                let dash = if fast { (18.0, 1.0 / 3.0) } else { (9.0, 1.0 / 3.0) };
                let offset = l.width * 0.5;
                ribbon(&mut paint, &slice(&l.shape, 0.0, solid_from), offset, 0.13, WHITE, Some(dash));
                if solid_from < total {
                    ribbon(&mut paint, &slice(&l.shape, solid_from, total), offset, 0.13, WHITE, None);
                }
            }
            if !contested {
                continue;
            }
            let a = approaches[e.first_lane as usize + i];
            let (end, t) = along(&l.shape, total);
            let n = left(t);
            let half = l.width * 0.5 - 0.12;
            let line_at = add(end, t, -0.3);
            if a.signal || (a.stop && !a.major) {
                paint.extend(ribbon_quad(add(line_at, n, -half), add(line_at, n, half), 0.5, WHITE));
            } else if a.minor && !a.major {
                let teeth = (l.width / 0.75).floor().max(1.0);
                for k in 0..teeth as u32 {
                    let y = (k as f32 + 0.5) / teeth * 2.0 * half - half;
                    let c = add(line_at, n, y);
                    tri(&mut paint, add(c, t, -0.75), add(c, n, 0.3), add(c, n, -0.3), WHITE);
                }
            } else if a.equal && !a.major {
                ribbon(&mut paint, &[add(line_at, n, -half), add(line_at, n, half)], 0.0, 0.2, WHITE, Some((0.8, 0.5)));
            } else if a.zipper {
                let teeth = (l.width / 0.75).floor().max(1.0);
                for k in 0..teeth as u32 {
                    let y = (k as f32 + 0.5) / teeth * 2.0 * half - half;
                    let c = add(line_at, n, y);
                    tri(&mut paint, add(c, t, -0.75), add(c, n, 0.3), add(c, n, -0.3), AMBER);
                }
            }
            if total > 22.0 && a.dirs != 0 {
                let (at, along_t) = along(&l.shape, total - 11.0);
                arrow(&mut paint, at, along_t, a.dirs);
            }
            if i == 0 && !a.signal {
                let (at, along_t) = along(&l.shape, (total - 3.0).max(0.0));
                sign(&mut signs, add(at, left(along_t), -l.width * 0.5 - 1.7), along_t, &a);
            }
        }
    }
    let mut out = under;
    out.extend(asphalt);
    out.extend(paint);
    out.extend(signs);
    out
}

fn ribbon_quad(a: [f32; 2], b: [f32; 2], width: f32, color: u32) -> Vec<Vertex> {
    let mut out = Vec::with_capacity(6);
    ribbon(&mut out, &[a, b], 0.0, width, color, None);
    out
}
