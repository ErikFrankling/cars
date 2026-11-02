// Times time-dependent Dijkstra on the real Berlin edge graph: one thread, with a per-edge, per-bin cost table the
// size the assignment loop would use. rustc -O demand_routebench.rs; ./demand_routebench berlin.bin
// Costs are synthetic (free flow times a space-time congestion factor); the graph and trips are real.
use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::io::Read;
use std::time::Instant;

fn u64s(b: &[u8]) -> u64 { u64::from_le_bytes(b.try_into().unwrap()) }
fn f32s(b: &[u8]) -> Vec<f32> { b.chunks_exact(4).map(|c| f32::from_le_bytes(c.try_into().unwrap())).collect() }
fn u32s(b: &[u8]) -> Vec<u32> { b.chunks_exact(4).map(|c| u32::from_le_bytes(c.try_into().unwrap())).collect() }

const BINS: usize = 288;
const BIN: f32 = 300.0;

struct G { first: Vec<u32>, to: Vec<u32>, cost: Vec<f32>, n: usize }

impl G {
    #[inline]
    fn c(&self, e: usize, t: f32) -> f32 {
        let b = ((t / BIN) as usize).min(BINS - 1);
        self.cost[e * BINS + b]
    }
}

struct Work { dist: Vec<f32>, stamp: Vec<u32>, cur: u32, heap: BinaryHeap<Reverse<(u32, u32)>>, settled: u64 }

// Labels are arrival time at the end of the edge. Early stop when dest is settled; dest = u32::MAX means whole tree.
fn run(g: &G, w: &mut Work, o: u32, dest: u32, t0: f32) -> f32 {
    w.cur += 1;
    w.heap.clear();
    let d0 = t0 + g.c(o as usize, t0);
    w.dist[o as usize] = d0;
    w.stamp[o as usize] = w.cur;
    w.heap.push(Reverse(((d0 * 16.0) as u32, o)));
    let mut res = f32::INFINITY;
    while let Some(Reverse((dk, e))) = w.heap.pop() {
        let eu = e as usize;
        let d = w.dist[eu];
        if (d * 16.0) as u32 != dk { continue; }
        w.settled += 1;
        if e == dest { res = d; break; }
        for &n in &g.to[g.first[eu] as usize..g.first[eu + 1] as usize] {
            let nu = n as usize;
            let nd = d + g.c(nu, d);
            if w.stamp[nu] != w.cur || nd < w.dist[nu] {
                w.stamp[nu] = w.cur;
                w.dist[nu] = nd;
                w.heap.push(Reverse(((nd * 16.0) as u32, n)));
            }
        }
    }
    res
}

// Free-flow distances from one edge, on the forward or reversed graph, for ALT lower bounds.
fn sssp(first: &[u32], to: &[u32], ff: &[f32], src: usize, reversed: bool) -> Vec<f32> {
    let n = first.len() - 1;
    let mut d = vec![f32::INFINITY; n];
    let mut h = BinaryHeap::new();
    d[src] = 0.0;
    h.push(Reverse(((0.0f32 * 16.0) as u32, src as u32)));
    while let Some(Reverse((k, e))) = h.pop() {
        let eu = e as usize;
        if (d[eu] * 16.0) as u32 != k { continue; }
        for &x in &to[first[eu] as usize..first[eu + 1] as usize] {
            let xu = x as usize;
            // Distances cost the edge entered; on the reversed graph that is the edge being left.
            let w = if reversed { ff[eu] } else { ff[xu] };
            let nd = d[eu] + w;
            if nd < d[xu] {
                d[xu] = nd;
                h.push(Reverse(((nd * 16.0) as u32, x)));
            }
        }
    }
    d
}

struct Alt { from_l: Vec<Vec<f32>>, to_l: Vec<Vec<f32>> }

impl Alt {
    #[inline]
    fn pot(&self, v: usize, t: usize) -> f32 {
        let mut p = 0f32;
        for (fl, tl) in self.from_l.iter().zip(&self.to_l) {
            let (a, b) = (fl[t] - fl[v], tl[v] - tl[t]);
            if a.is_finite() && a > p { p = a; }
            if b.is_finite() && b > p { p = b; }
        }
        p
    }
}

// Time-dependent A*: every cost is at least free flow, so free-flow landmark bounds stay admissible.
fn run_alt(g: &G, alt: &Alt, w: &mut Work, o: u32, dest: u32, t0: f32) -> f32 {
    w.cur += 1;
    w.heap.clear();
    let tu = dest as usize;
    let d0 = t0 + g.c(o as usize, t0);
    w.dist[o as usize] = d0;
    w.stamp[o as usize] = w.cur;
    w.heap.push(Reverse((((d0 + alt.pot(o as usize, tu)) * 16.0) as u32, o)));
    while let Some(Reverse((dk, e))) = w.heap.pop() {
        let eu = e as usize;
        let d = w.dist[eu];
        if ((d + alt.pot(eu, tu)) * 16.0) as u32 != dk { continue; }
        w.settled += 1;
        if e == dest { return d; }
        for &n in &g.to[g.first[eu] as usize..g.first[eu + 1] as usize] {
            let nu = n as usize;
            let nd = d + g.c(nu, d);
            if w.stamp[nu] != w.cur || nd < w.dist[nu] {
                w.stamp[nu] = w.cur;
                w.dist[nu] = nd;
                w.heap.push(Reverse((((nd + alt.pot(nu, tu)) * 16.0) as u32, n)));
            }
        }
    }
    f32::INFINITY
}

fn main() {
    let path = std::env::args().nth(1).unwrap();
    let mut buf = Vec::new();
    std::fs::File::open(&path).unwrap().read_to_end(&mut buf).unwrap();
    let (n, m, k) = (u64s(&buf[0..8]) as usize, u64s(&buf[8..16]) as usize, u64s(&buf[16..24]) as usize);
    let mut at = 24;
    let mut take = |bytes: usize| { let s = &buf[at..at + bytes]; at += bytes; s };
    let length = f32s(take(n * 4));
    let speed = f32s(take(n * 4));
    let first = u32s(take((n + 1) * 4));
    let to = u32s(take(m * 4));
    let oo = u32s(take(k * 4));
    let dd = u32s(take(k * 4));
    let dep = f32s(take(k * 4));
    let t = Instant::now();
    let mut cost = vec![0f32; n * BINS];
    let mut s = 0x12345u64;
    for e in 0..n {
        s = s.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(1);
        let weight = ((s >> 40) & 0xff) as f32 / 255.0;
        let ff = length[e] / speed[e].max(0.5);
        for b in 0..BINS {
            let h = b as f32 / 12.0;
            let peak = (-(h - 8.0).powi(2) / 2.0).exp() + (-(h - 17.0).powi(2) / 3.0).exp();
            cost[e * BINS + b] = ff * (1.0 + 2.0 * weight * peak);
        }
    }
    let g = G { first, to, cost, n };
    println!("edges {} turns {} trips {} table {:.0} MB built in {:.2}s", g.n, m, k, (g.n * BINS * 4) as f64 / 1e6, t.elapsed().as_secs_f64());
    let mut w = Work { dist: vec![0.0; n], stamp: vec![0; n], cur: 0, heap: BinaryHeap::new(), settled: 0 };
    let step = (k / 20011).max(1);
    let sample: Vec<usize> = (0..k).step_by(step).collect();
    let t = Instant::now();
    let mut reach = 0u64;
    let mut sum = 0f64;
    for &i in &sample {
        let r = run(&g, &mut w, oo[i], dd[i], dep[i]);
        if r.is_finite() { reach += 1; sum += (r - dep[i]) as f64; }
    }
    let secs = t.elapsed().as_secs_f64();
    println!("early-stop paths {} reachable {} mean cost {:.0}s: {:.3} ms each, settled {:.0} edges each", sample.len(), reach, sum / reach.max(1) as f64, secs * 1e3 / sample.len() as f64, w.settled as f64 / sample.len() as f64);
    w.settled = 0;
    let t = Instant::now();
    let trees = 300usize;
    for j in 0..trees {
        let i = sample[j * sample.len() / trees];
        run(&g, &mut w, oo[i], u32::MAX, dep[i]);
    }
    let secs = t.elapsed().as_secs_f64();
    println!("full trees {}: {:.2} ms each, settled {:.0} edges each", trees, secs * 1e3 / trees as f64, w.settled as f64 / trees as f64);
    // Reversed graph and farthest-point landmarks.
    let t = Instant::now();
    let mut rcount = vec![0u32; n + 1];
    for &x in &g.to { rcount[x as usize + 1] += 1; }
    for i in 0..n { rcount[i + 1] += rcount[i]; }
    let mut rto = vec![0u32; m];
    let mut fill = rcount.clone();
    for e in 0..n {
        for &x in &g.to[g.first[e] as usize..g.first[e + 1] as usize] {
            rto[fill[x as usize] as usize] = e as u32;
            fill[x as usize] += 1;
        }
    }
    let ff: Vec<f32> = (0..n).map(|e| length[e] / speed[e].max(0.5)).collect();
    for &nl in &[4usize, 16] {
        let mut alt = Alt { from_l: Vec::new(), to_l: Vec::new() };
        let mut land = oo[0] as usize;
        let mut best = vec![f32::INFINITY; n];
        for _ in 0..nl {
            let fl = sssp(&g.first, &g.to, &ff, land, false);
            let tl = sssp(&rcount, &rto, &ff, land, true);
            for v in 0..n { if fl[v].is_finite() { best[v] = best[v].min(fl[v]); } }
            alt.from_l.push(fl);
            alt.to_l.push(tl);
            land = (0..n).filter(|&v| best[v].is_finite()).max_by(|&a, &b| best[a].total_cmp(&best[b])).unwrap();
        }
        println!("ALT {} landmarks built in {:.2}s", nl, t.elapsed().as_secs_f64());
        w.settled = 0;
        let t2 = Instant::now();
        let mut sum2 = 0f64;
        let mut wrong = 0u64;
        for &i in &sample {
            let r = run_alt(&g, &alt, &mut w, oo[i], dd[i], dep[i]);
            if r.is_finite() { sum2 += (r - dep[i]) as f64; } else { wrong += 1; }
        }
        let s2 = t2.elapsed().as_secs_f64();
        println!("ALT {} paths {}: {:.3} ms each, settled {:.0} edges each, mean cost {:.1}s (unreachable {})", nl, sample.len(), s2 * 1e3 / sample.len() as f64, w.settled as f64 / sample.len() as f64, sum2 / (sample.len() as u64 - wrong).max(1) as f64, wrong);
    }
}
