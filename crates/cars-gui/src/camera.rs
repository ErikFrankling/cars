//! The camera: where it is, where it is heading, and turning screen points into net metres.
use cars_core::render::Camera;

pub const MIN_MPP: f32 = 0.012;

#[derive(Clone, Copy, Debug)]
pub struct Flyer {
    pub center: [f32; 2],
    pub mpp: f32,
    pub target_center: [f32; 2],
    pub target_mpp: f32,
    /// Largest zoom out, from the size of the map.
    pub max_mpp: f32,
    /// How many seconds the eased moves take to close most of the distance. 0 jumps.
    pub ease: f32,
}

impl Flyer {
    pub fn new(center: [f32; 2], mpp: f32, max_mpp: f32) -> Self {
        Self { center, mpp, target_center: center, target_mpp: mpp, max_mpp, ease: 0.09 }
    }
    pub fn camera(&self) -> Camera {
        Camera { center: self.center, metres_per_pixel: self.mpp }
    }
    /// Is anything still moving towards its target?
    pub fn moving(&self) -> bool {
        (self.mpp / self.target_mpp - 1.0).abs() > 0.001 || (self.center[0] - self.target_center[0]).hypot(self.center[1] - self.target_center[1]) > self.mpp * 0.25
    }
    pub fn update(&mut self, dt: f32) {
        let k = if self.ease <= 0.0 { 1.0 } else { 1.0 - (-dt / self.ease).exp() };
        // Zooming eases in log space so it feels the same at every scale, and around the point that
        // set the target: the two are tied together by easing the centre with the same factor.
        self.mpp = (self.mpp.ln() + (self.target_mpp.ln() - self.mpp.ln()) * k).exp();
        self.center[0] += (self.target_center[0] - self.center[0]) * k;
        self.center[1] += (self.target_center[1] - self.center[1]) * k;
    }
    /// Pan so the map moves with the pointer, at once.
    pub fn drag(&mut self, dx_px: f32, dy_px: f32) {
        let (dx, dy) = (-dx_px * self.mpp, dy_px * self.mpp);
        self.center[0] += dx;
        self.center[1] += dy;
        self.target_center[0] += dx;
        self.target_center[1] += dy;
    }
    /// Move at a speed given in screen widths' worth of pixels per second, keeping any easing going.
    pub fn fly(&mut self, vx_px: f32, vy_px: f32, dt: f32) {
        let (dx, dy) = (vx_px * self.target_mpp * dt, vy_px * self.target_mpp * dt);
        self.target_center[0] += dx;
        self.target_center[1] += dy;
    }
    /// Zoom by a factor, keeping the net point under `anchor` where it is. `anchor` is in pixels from
    /// the middle of the view, x right and y down.
    pub fn zoom_at(&mut self, factor: f32, anchor: [f32; 2]) {
        let next = (self.target_mpp * factor).clamp(MIN_MPP, self.max_mpp);
        let world = [self.target_center[0] + anchor[0] * self.target_mpp, self.target_center[1] - anchor[1] * self.target_mpp];
        self.target_center = [world[0] - anchor[0] * next, world[1] + anchor[1] * next];
        self.target_mpp = next;
    }
    pub fn go_to(&mut self, center: [f32; 2], mpp: Option<f32>) {
        self.target_center = center;
        if let Some(m) = mpp {
            self.target_mpp = m.clamp(MIN_MPP, self.max_mpp);
        }
    }
    pub fn follow(&mut self, center: [f32; 2], dt: f32) {
        let k = 1.0 - (-dt / 0.2).exp();
        self.target_center = center;
        self.center[0] += (center[0] - self.center[0]) * k;
        self.center[1] += (center[1] - self.center[1]) * k;
    }
}

/// Camera that shows all of `bounds` in a view of this many pixels.
pub fn fit(bounds: [f32; 4], w: f32, h: f32) -> ([f32; 2], f32) {
    let c = Camera::fit(bounds, w.max(1.0) as u32, h.max(1.0) as u32);
    (c.center, c.metres_per_pixel)
}

/// Net metres at a point in a view, from the view's top left, in pixels.
pub fn to_world(cam: Camera, w: f32, h: f32, px: [f32; 2]) -> [f32; 2] {
    [cam.center[0] + (px[0] - w * 0.5) * cam.metres_per_pixel, cam.center[1] - (px[1] - h * 0.5) * cam.metres_per_pixel]
}

/// Pixels from the view's top left at a point in net metres.
pub fn to_screen(cam: Camera, w: f32, h: f32, p: [f32; 2]) -> [f32; 2] {
    [w * 0.5 + (p[0] - cam.center[0]) / cam.metres_per_pixel, h * 0.5 - (p[1] - cam.center[1]) / cam.metres_per_pixel]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn screen_and_world_are_inverse() {
        let cam = Camera { center: [100.0, -50.0], metres_per_pixel: 0.5 };
        let p = to_world(cam, 800.0, 600.0, [123.0, 456.0]);
        let q = to_screen(cam, 800.0, 600.0, p);
        assert!((q[0] - 123.0).abs() < 1e-3 && (q[1] - 456.0).abs() < 1e-3);
    }

    #[test]
    fn zoom_keeps_the_point_under_the_cursor() {
        let mut f = Flyer::new([1000.0, 2000.0], 2.0, 100.0);
        let anchor = [150.0, -80.0];
        let before = [1000.0 + anchor[0] * 2.0, 2000.0 - anchor[1] * 2.0];
        f.zoom_at(0.25, anchor);
        let after = [f.target_center[0] + anchor[0] * f.target_mpp, f.target_center[1] - anchor[1] * f.target_mpp];
        assert!((before[0] - after[0]).abs() < 1e-2 && (before[1] - after[1]).abs() < 1e-2);
        assert!((f.target_mpp - 0.5).abs() < 1e-5);
    }

    #[test]
    fn zoom_stays_in_range_and_motion_settles() {
        let mut f = Flyer::new([0.0, 0.0], 1.0, 50.0);
        f.zoom_at(1e6, [0.0, 0.0]);
        assert_eq!(f.target_mpp, 50.0);
        f.zoom_at(1e-9, [0.0, 0.0]);
        assert_eq!(f.target_mpp, MIN_MPP);
        for _ in 0..600 {
            f.update(1.0 / 60.0);
        }
        assert!(!f.moving());
    }

    #[test]
    fn drag_moves_the_map_with_the_pointer() {
        let mut f = Flyer::new([0.0, 0.0], 2.0, 50.0);
        f.drag(10.0, 5.0);
        assert_eq!(f.center, [-20.0, 10.0]);
    }
}
