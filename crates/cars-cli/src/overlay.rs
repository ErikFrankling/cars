use cars_core::{
    net::Net,
    render::Camera,
    world::{GpuVeh, World},
};
use std::collections::HashMap;
#[derive(Default)]
pub struct Overlay {
    previous: HashMap<u32, ([f32; 2], u32)>,
    flashes: Vec<([f32; 2], f32)>,
}
pub fn pose(net: &Net, lane: u32, pos: f32) -> Option<([f32; 2], [f32; 2])> {
    let l = net.lanes.get(lane as usize)?;
    let total: f32 = l
        .shape
        .windows(2)
        .map(|p| (p[1][0] - p[0][0]).hypot(p[1][1] - p[0][1]))
        .sum();
    let mut d = (pos / l.length).clamp(0., 1.) * total;
    for p in l.shape.windows(2) {
        let len = (p[1][0] - p[0][0]).hypot(p[1][1] - p[0][1]);
        if d <= len {
            let u = d / len.max(0.001);
            return Some((
                [
                    p[0][0] + u * (p[1][0] - p[0][0]),
                    p[0][1] + u * (p[1][1] - p[0][1]),
                ],
                [
                    (p[1][0] - p[0][0]) / len.max(0.001),
                    (p[1][1] - p[0][1]) / len.max(0.001),
                ],
            ));
        }
        d -= len;
    }
    None
}
impl Overlay {
    pub fn draw(
        &mut self,
        pixels: &mut [u8],
        width: u32,
        height: u32,
        cam: Camera,
        net: &Net,
        world: &World,
        vs: &[GpuVeh],
        time: f32,
        modes: &[String],
    ) {
        let enabled = |s: &str| modes.iter().any(|m| m == s || m == "all");
        let project = |p: [f32; 2]| {
            [
                (width as f32 / 2. + (p[0] - cam.center[0]) / cam.metres_per_pixel) as i32,
                (height as f32 / 2. - (p[1] - cam.center[1]) / cam.metres_per_pixel) as i32,
            ]
        };
        let mut line = |a: [f32; 2], b: [f32; 2], color: [u8; 3]| {
            let a = project(a);
            let b = project(b);
            let n = (b[0] - a[0])
                .abs()
                .max((b[1] - a[1]).abs())
                .max(1)
                .min(8000);
            for i in 0..=n {
                let x = a[0] + (b[0] - a[0]) * i / n;
                let y = a[1] + (b[1] - a[1]) * i / n;
                if x >= 0 && y >= 0 && x < width as i32 && y < height as i32 {
                    let k = (y as usize * width as usize + x as usize) * 4;
                    pixels[k..k + 3].copy_from_slice(&color);
                }
            }
        };
        if enabled("foes") {
            for j in &net.junctions {
                if (j.x - cam.center[0]).abs() > width as f32 * cam.metres_per_pixel {
                    continue;
                }
                for r in &j.requests {
                    let Some(a) = j
                        .int_lanes
                        .get(r.index as usize)
                        .and_then(|s| net.lane_index.get(s))
                        .and_then(|&l| pose(net, l, 0.))
                    else {
                        continue;
                    };
                    for (i, foe) in r.foes.iter().enumerate() {
                        if !foe {
                            continue;
                        }
                        if let Some(b) = j
                            .int_lanes
                            .get(i)
                            .and_then(|s| net.lane_index.get(s))
                            .and_then(|&l| pose(net, l, 0.))
                        {
                            let mid = [(a.0[0] + b.0[0]) / 2. + 2., (a.0[1] + b.0[1]) / 2. + 2.];
                            line(a.0, mid, [170, 80, 220]);
                            line(mid, b.0, [170, 80, 220]);
                        }
                    }
                }
            }
        }
        let mut groups: HashMap<u32, Vec<&GpuVeh>> = HashMap::new();
        for v in vs {
            if v.replica != 0 || v.flags & 1 != 0 {
                continue;
            }
            let Some((xy, dir)) = pose(net, v.lane, v.pos) else {
                if enabled("events") {
                    if let Some((p, _)) = self.previous.remove(&v.trip) {
                        self.flashes.push((p, time));
                    }
                }
                continue;
            };
            groups.entry(v.lane).or_default().push(v);
            self.previous.insert(v.trip, (xy, v.lane));
            if enabled("braking") {
                let d = v.speed * v.speed / (2. * world.vtypes[v.vtype as usize].decel.max(0.1));
                if let Some((end, _)) = pose(net, v.lane, v.pos + d) {
                    line(xy, end, [255, 190, 50]);
                }
            }
            if enabled("state") {
                let color = if v.flags & 2048 != 0 {
                    [255, 100, 30]
                } else if v.flags & 512 != 0 {
                    [30, 255, 100]
                } else {
                    [120, 140, 200]
                };
                line(
                    [xy[0] - dir[1] * 2., xy[1] + dir[0] * 2.],
                    [xy[0] + dir[1] * 2., xy[1] - dir[0] * 2.],
                    color,
                );
            }
            if enabled("speed") {
                let text = format!("{:.0}", v.speed * 3.6);
                let digits = [
                    0b1111110u8,
                    0b0110000,
                    0b1101101,
                    0b1111001,
                    0b0110011,
                    0b1011011,
                    0b1011111,
                    0b1110000,
                    0b1111111,
                    0b1111011,
                ];
                for (i, c) in text.bytes().enumerate() {
                    let mask = digits[(c - b'0') as usize];
                    for (j, (a, b)) in [
                        ([0., 0.], [1., 0.]),
                        ([1., 0.], [1., -1.]),
                        ([1., -1.], [1., -2.]),
                        ([0., -2.], [1., -2.]),
                        ([0., -1.], [0., -2.]),
                        ([0., 0.], [0., -1.]),
                        ([0., -1.], [1., -1.]),
                    ]
                    .into_iter()
                    .enumerate()
                    {
                        if mask & (1 << (6 - j)) != 0 {
                            let s = cam.metres_per_pixel * 5.;
                            let origin = [xy[0] + 2. + i as f32 * s * 1.5, xy[1] + 2.];
                            line(
                                [origin[0] + a[0] * s, origin[1] + a[1] * s],
                                [origin[0] + b[0] * s, origin[1] + b[1] * s],
                                [255, 255, 255],
                            );
                        }
                    }
                }
            }
        }
        for rows in groups.values_mut() {
            rows.sort_by(|a, b| a.pos.total_cmp(&b.pos));
            for p in rows.windows(2) {
                let a = p[0];
                let b = p[1];
                let x = pose(net, a.lane, a.pos).unwrap().0;
                let y = pose(net, b.lane, b.pos).unwrap().0;
                if enabled("leader") {
                    line(x, y, [60, 220, 255]);
                }
                if enabled("events")
                    && b.pos - world.vtypes[b.vtype as usize].length - a.pos < -0.05
                {
                    self.flashes.push((x, time));
                }
            }
        }
        self.flashes.retain(|(_, t)| time - *t < 1.);
        for &(p, _) in &self.flashes {
            line([p[0] - 3., p[1] - 3.], [p[0] + 3., p[1] + 3.], [255, 0, 0]);
            line([p[0] - 3., p[1] + 3.], [p[0] + 3., p[1] - 3.], [255, 0, 0]);
        }
    }
}
