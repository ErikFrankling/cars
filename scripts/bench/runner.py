"""Runs a driver on a scene and reads the outcome. One job at a time, through the GPU lock when on the GPU."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pandas as pd

import scenes

STORE = Path(os.environ.get('BENCH_HOME', '/home/erikf/projects/personal/cars-data/bench'))
HERE = Path(__file__).resolve().parent
LOG_RE = re.compile(r'lane changes (\d+), teleports (\d+), collisions (\d+)')
PHYS_RE = re.compile(r'physics: collisions (\d+) incidents')
USE = ['time', 'trip', 'lane', 'pos', 'speed', 'acc', 'length']


def sha(path, n=16):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()[:n]


def load_config(name):
    import tomllib
    cfg = tomllib.loads((HERE / 'configs' / f'{name}.toml').read_text())
    pin = STORE / 'pins' / name
    commit = pin.read_text().strip() if pin.exists() else subprocess.check_output(['git', '-C', str(HERE), 'rev-parse', cfg['branch']], text=True).strip()
    patch = HERE / cfg['patch']
    cfg['commit'], cfg['patch_sha'] = commit, sha(patch, 8)
    cfg['binary'] = str(STORE / 'bin' / f"{name}-{commit[:8]}-{cfg['patch_sha']}")
    if not Path(cfg['binary']).exists():
        raise SystemExit(f"no binary {cfg['binary']}: scripts/bench/build_driver.sh {name}")
    cfg['binary_sha'] = sha(cfg['binary'])
    cfg['hash'] = hashlib.sha256(json.dumps({k: cfg[k] for k in ('name', 'kind', 'dt', 'dt_network', 'time_to_teleport', 'flags', 'vtype')}, sort_keys=True).encode()).hexdigest()[:16]
    return cfg


class Run:
    def __init__(self, d, plan, log, secs, cmd):
        self.d, self.plan, self.log, self.secs, self.cmd = d, plan, log, secs, cmd
        m = LOG_RE.findall(log)
        self.lane_changes, self.teleports, self.collisions = map(int, m[-1]) if m else (None, None, None)
        p = PHYS_RE.findall(log)
        if p:
            self.collisions = int(p[-1])
        self.fcd = d / 'fcd.csv'

    def table(self):
        head = pd.read_csv(self.fcd, nrows=0).columns
        cols = [c for c in USE + ['offset'] if c in head]
        f = pd.read_csv(self.fcd, usecols=cols, dtype={'trip': str, 'lane': str, 'pos': 'f8', 'speed': 'f4', 'acc': 'f4', 'length': 'f4', 'time': 'f8'})
        if 'offset' not in f:
            f['offset'] = 0.0
        return f

    def summary(self):
        p = self.d / 'summary.csv'
        return pd.read_csv(p) if p.exists() else None

    def counts(self, f=None):
        """inserted, arrived, running at the last frame. With trajectories on, the engine writes no summary, so they are counted here."""
        s = self.summary()
        if s is not None and len(s):
            last = s.iloc[-1]
            return int(last.inserted), int(last.arrived), int(last.running)
        if f is None or not len(f):
            return None
        last_t = f.time.max()
        t = self.trips()
        seen = set(f.trip.unique())
        gone = set(t.trip.astype(str)) if t is not None else set()
        ended = last_t < self.plan['end'] - 2 * (self.plan.get('fcd') or 1)
        running = (set() if ended else set(f[f.time == last_t].trip)) - gone
        return len(seen), len(seen & gone), len(running)

    def trips(self):
        p = self.d / 'trips.csv'
        return pd.read_csv(p) if p.exists() else None


def run(cfg, scene, seed, fast, ov=None, work=None, gpu=False, dt=None, tag='', ctx=None):
    ov = ov or {}
    key = hashlib.sha256(json.dumps([scene, cfg['name'], cfg['hash'], fast, ov, dt, sorted((ctx or {}).keys())], sort_keys=True, default=str).encode()).hexdigest()[:10]
    base = Path(work or STORE / 'work') / f'{cfg["name"]}-{scene}-{key}'
    base.mkdir(parents=True, exist_ok=True)
    kw = dict(ctx or {})
    plan = scenes.SCENES[scene](base, cfg, ov, fast, seed, **kw)
    d = base / f's{seed}{tag}'
    d.mkdir(exist_ok=True)
    return launch(cfg, plan, d, seed, ov, base / 'net.xml', dt, gpu)


def launch(cfg, plan, d, seed, ov, net, dt=None, gpu=False):
    dt = dt or ov.get('dt') or cfg['dt']
    interval = max(plan.get('fcd') or dt, dt)
    ttt = ov.get('teleport', cfg['time_to_teleport'])
    cmd = [cfg['binary'], 'run', '--net', str(plan.get('net', net)), '--routes', str(plan['routes']), '--dt', str(dt), '--end', str(plan['end']), '--seed', str(seed),
           '--time-to-teleport', str(ttt), '--summary-csv', str(d / 'summary.csv'), '--trip-csv', str(d / 'trips.csv')]
    if plan.get('fcd'):
        cmd += ['--fcd', str(d / 'fcd.csv'), '--fcd-interval', str(interval)]
    if plan.get('add'):
        cmd += ['--additional', ','.join(map(str, plan['add']))]
    if plan.get('sensors'):
        cmd += ['--sensors', str(plan['sensors']), '--sensor-csv', str(d / 'sensors.csv')]
    cmd += ['--edge-interval', str(plan.get('edge_interval', 60))]
    if plan.get('edges'):
        cmd += ['--edge-csv', str(d / 'edges.csv')]
    cmd += [str(x) for x in plan.get('extra', [])]
    cmd += cfg['flags'] + ov.get('flags', [])
    env = dict(os.environ)
    if gpu:
        env.pop('CARS_ADAPTER', None)
        cmd = ['flock', '/tmp/cars-gpu.lock'] + cmd
    else:
        env['CARS_ADAPTER'] = 'llvmpipe'
        env.setdefault('LP_NUM_THREADS', '2')
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    (d / 'log.txt').write_text(r.stdout[-4000:] + r.stderr[-6000:])
    if r.returncode:
        raise RuntimeError(f"failed {' '.join(cmd[:12])}\n{r.stderr[-1500:]}")
    return Run(d, plan, r.stdout + r.stderr, time.time() - t, cmd)


def clean(run_):
    if run_.fcd.exists():
        run_.fcd.unlink()
