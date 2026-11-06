"""Shared pieces of replay scenes: the .rpl writer, nets from lane centrelines, map matching, FCD reading.
Format: crates/cars-core/src/replay.rs. Design: research/truth/replay/README.md."""
import os, struct, subprocess, xml.etree.ElementTree as ET
import numpy as np

DATA = '/home/erikf/projects/personal/cars-data'
OUT = os.path.join(DATA, 'replay')
INF = 3.0e38


def write_rpl(path, lanes, tracks):
    """lanes: list of lane ids. tracks: list of (trip_id, t0, key_dt, release, lane_idx[], pos[], speed[] [, lat[]]),
    lat the offset from the lane's centreline, left positive. With any lat the file is RPL2 (missing ones are 0)."""
    lateral = any(len(t) > 7 for t in tracks)
    with open(path, 'wb') as f:
        f.write(b'RPL2' if lateral else b'RPL1')
        f.write(struct.pack('<I', len(lanes)))
        for l in lanes:
            b = l.encode(); f.write(struct.pack('<H', len(b))); f.write(b)
        f.write(struct.pack('<I', len(tracks)))
        for tr in tracks:
            tid, t0, kdt, rel, li, pos, spd = tr[:7]
            b = str(tid).encode(); f.write(struct.pack('<H', len(b))); f.write(b)
            n = len(li)
            f.write(struct.pack('<fffI', t0, kdt, min(rel, INF), n))
            if n:
                k = np.zeros(n, dtype=[('l', '<u4'), ('p', '<f4'), ('v', '<f4')] + ([('a', '<f4')] if lateral else []))
                k['l'] = li; k['p'] = pos; k['v'] = spd
                if lateral and len(tr) > 7:
                    k['a'] = tr[7]
                f.write(k.tobytes())


def netconvert(plain_prefix, out, extra=()):
    cmd = ['netconvert', '-n', plain_prefix + '.nod.xml', '-e', plain_prefix + '.edg.xml', '-o', out,
           '--no-internal-links', '--no-turnarounds', '--offset.disable-normalization', '--no-warnings'] + list(extra)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def fmt_shape(xy):
    return ' '.join(f'{x:.3f},{y:.3f}' for x, y in xy)


def lane_shapes(net_xml):
    """lane id -> (N,2) shape, plus lane length and speed."""
    out = {}
    for ln in ET.parse(net_xml).getroot().iter('lane'):
        pts = np.array([[float(a) for a in p.split(',')[:2]] for p in ln.get('shape').split()])
        out[ln.get('id')] = dict(shape=pts, length=float(ln.get('length')), speed=float(ln.get('speed')))
    return out


class Polyline:
    """Projection onto a lane: arc length along it (scaled to the lane's length as SUMO does) and signed lateral offset."""
    def __init__(self, pts, length=None):
        self.p = np.asarray(pts, float)
        d = np.diff(self.p, axis=0)
        self.seg = np.hypot(d[:, 0], d[:, 1])
        self.cum = np.r_[0, np.cumsum(self.seg)]
        self.u = d / np.maximum(self.seg, 1e-9)[:, None]
        self.scale = (length / self.cum[-1]) if length else 1.0

    def project(self, x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        best = np.full(x.shape, np.inf); s = np.zeros(x.shape); lat = np.zeros(x.shape)
        for i in range(len(self.seg)):
            dx = x - self.p[i, 0]; dy = y - self.p[i, 1]
            t = np.clip(dx * self.u[i, 0] + dy * self.u[i, 1], 0, self.seg[i])
            px = dx - t * self.u[i, 0]; py = dy - t * self.u[i, 1]
            dist = np.hypot(px, py)
            m = dist < best
            best[m] = dist[m]; s[m] = self.cum[i] + t[m]
            lat[m] = (self.u[i, 0] * py - self.u[i, 1] * px)[m]
        return s * self.scale, lat

    def point(self, s):
        s = np.clip(np.asarray(s, float) / self.scale, 0, self.cum[-1])
        i = np.clip(np.searchsorted(self.cum, s, side='right') - 1, 0, len(self.seg) - 1)
        t = s - self.cum[i]
        return self.p[i, 0] + t * self.u[i, 0], self.p[i, 1] + t * self.u[i, 1]


def read_fcd(path, cols=('time', 'trip', 'lane', 'pos', 'speed', 'acc')):
    import pandas as pd
    return pd.read_csv(path, usecols=list(cols))


def cars_bin():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, '..', '..', 'target', 'release', 'cars')


def run_cars(args, gpu=False, log=None):
    """One cars run. GPU runs hold the lock; small scenes go to llvmpipe."""
    env = dict(os.environ)
    cmd = [cars_bin(), 'run'] + [str(a) for a in args]
    if gpu:
        cmd = ['flock', '/tmp/cars-gpu.lock'] + cmd
    else:
        env['CARS_ADAPTER'] = 'llvmpipe'
        env.setdefault('LP_NATIVE_VECTOR_WIDTH', '128')
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if log:
        open(log, 'w').write(r.stderr)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-3000:])
    return r.stderr
