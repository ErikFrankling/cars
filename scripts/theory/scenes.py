#!/usr/bin/env python3
"""Rung 2: small scenes against hand-computed forecasts. research/truth/PLAN.md, foundations/forecasts.csv.

    python3 -I scripts/theory/scenes.py --driver physical|human [--dt X] [--only L1,S4] [--cars BIN] [--flags "..."]

Each batch puts all its scenes and seeds as disjoint cells in one world, since starting a process costs more
than the scene. A seed is one cell: its arrivals are drawn from a logged numpy seed, and the simulator's own seed
is --seed. Writes results/theory/<driver>_<dt>.csv and prints scene, forecast, measured, tolerance, verdict.
"""
import argparse
import csv
import math
import os
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import warnings
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

warnings.simplefilter('ignore')
ROOT = Path(__file__).resolve().parents[2]
FORECASTS = ROOT / 'research/truth/foundations/forecasts.csv'
BINS = {'physical': ROOT / 'target/release/cars', 'human': ROOT / 'target/drivers/cars-human-11afb41'}
FLAGS = {'physical': '', 'human': '--humans'}
LVP = '/run/opengl-driver/share/vulkan/icd.d/lvp_icd.x86_64.json'
ENV = dict(os.environ, CARS_ADAPTER='llvmpipe', LP_NUM_THREADS=os.environ.get('LP_NUM_THREADS', '2'), LP_NATIVE_VECTOR_WIDTH='128')
if Path(LVP).exists():
    ENV['VK_DRIVER_FILES'] = LVP
SEEDS = 5
SIM_SEED = 1
V50 = 50 / 3.6


def arrival_rng(scene, seed):
    return np.random.default_rng([zlib.crc32(scene.encode()), seed])


def poisson(rng, rate, t0, t1, tm=0.0):
    """Arrivals per hour between t0 and t1, exponential headways shifted by tm."""
    out, t, mean = [], t0, 3600 / rate if rate else 0
    while rate:
        t += tm + rng.exponential(mean - tm)
        if t >= t1:
            break
        out.append(t)
    return out


def uniform(rate, t0, t1):
    return list(np.arange(t0, t1, 3600 / rate)) if rate else []


class World:
    def __init__(self):
        self.nodes, self.edges, self.conns, self.tls, self.veh, self.types = [], [], [], {}, [], {}
        self.y = 0.0
        # The formulas have one free speed. A spread of speed factors on one lane is a fleet input, tested elsewhere.
        self.car(speedDev='0', speedFactor='1')

    def car(self, id='car', **attr):
        if id not in self.types:
            self.types[id] = ' '.join(f'{k}="{v}"' for k, v in attr.items())
        return id

    def cell(self, name, h=400.0, w=0):
        c = Cell(self, name, self.y)
        self.y += h + 300
        return c


class Cell:
    def __init__(self, w, name, y):
        self.w, self.name, self.y0 = w, name, y

    def id(self, s):
        return f'{self.name}.{s}'

    def node(self, i, x, y, t='priority'):
        self.w.nodes.append(f'<node id="{self.id(i)}" x="{x:.2f}" y="{y + self.y0:.2f}" type="{t}"/>')

    def edge(self, i, a, b, lanes=1, v=V50, prio=1, shape=None, lane_speed=None, lane_change=None):
        s = ''
        if shape is not None:
            s = ' shape="' + ' '.join(f'{x:.2f},{y + self.y0:.2f}' for x, y in shape) + '"'
        inner = ''.join(f'<lane index="{k}" speed="{u:.3f}"/>' for k, u in (lane_speed or {}).items())
        inner += ''.join(f'<lane index="{k}" changeLeft="{u}"/>' for k, u in (lane_change or {}).items())
        self.w.edges.append(f'<edge id="{self.id(i)}" from="{self.id(a)}" to="{self.id(b)}" numLanes="{lanes}" speed="{v:.3f}" priority="{prio}"{s}>{inner}</edge>')

    def conn(self, a, b, fl, tl):
        self.w.conns.append(f'<connection from="{self.id(a)}" to="{self.id(b)}" fromLane="{fl}" toLane="{tl}"/>')

    def signal(self, node, phases, offset=0.0):
        """phases: (duration, state) with one char for every link, or a function of (from edge, to edge, dir)."""
        self.w.tls[self.id(node)] = (phases, offset, self.name)

    def car(self, i, t, route, lane=0, pos=None, speed='max', vtype='car', repeat=None):
        p = f' departPos="{pos:.2f}"' if pos is not None else ''
        rep = f' repeat="{repeat}"' if repeat else ''
        edges = ' '.join(self.id(e) for e in route)
        self.w.veh.append((t, f'<vehicle id="{self.id(i)}" type="{vtype}" depart="{t:.2f}" departLane="{lane}"{p} departSpeed="{speed}"><route edges="{edges}"{rep}/></vehicle>'))

    def feeders(self, target, lanes, node, x, y, length=250.0, v=V50):
        """One source edge per lane of `target`, or a blocked lane holds back the others in the insertion queue."""
        for i in range(lanes):
            self.node(f'{target}f{i}', x - length, y + (i - (lanes - 1) / 2) * 60)
            self.edge(f'{target}f{i}', f'{target}f{i}', node, v=v)
            self.conn(f'{target}f{i}', target, 0, i)
        return [f'{target}f{i}' for i in range(lanes)]

    def line(self, x0, x1, nodes, y=0.0, types=None):
        """Nodes spaced along a straight road, named from the list."""
        for k, n in enumerate(nodes):
            self.node(n, x0 + (x1 - x0) * k / (len(nodes) - 1), y, (types or {}).get(n, 'priority'))

    def ring(self, radius, k=4, v=V50, node='traffic_light', lanes=1):
        """A circle of k tangent arcs. Edges e0..e(k-1), nodes n0..n(k-1), counter-clockwise.
        The lane runs 1.6 m to the right of the edge, on the outside, so the edge radius is cut to give the wanted perimeter."""
        radius -= 1.6
        for i in range(k):
            a = 2 * math.pi * i / k
            self.node(f'n{i}', radius * math.cos(a), radius * math.sin(a) + radius, node)
        for i in range(k):
            a0, a1 = 2 * math.pi * i / k, 2 * math.pi * (i + 1) / k
            pts = [(radius * math.cos(a0 + (a1 - a0) * j / 24), radius * math.sin(a0 + (a1 - a0) * j / 24) + radius) for j in range(25)]
            self.edge(f'e{i}', f'n{i}', f'n{(i + 1) % k}', lanes=lanes, v=v, shape=pts, prio=5)
        return [f'e{i}' for i in range(k)]


def rewrite_tls(path, world):
    x = path.read_text()
    conns = {}
    for m in re.finditer(r'<connection [^>]*tl="([^"]+)"[^>]*>', x):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(0)))
        conns.setdefault(a['tl'], {})[int(a['linkIndex'])] = (a['from'].split('.', 1)[1], a['to'].split('.', 1)[1], a.get('dir', 's'))
    for tl, (phases, offset, _) in world.tls.items():
        links = [conns[tl][i] for i in sorted(conns[tl])]
        body = ''
        for dur, st in phases:
            s = st(links) if callable(st) else st * len(links)
            body += f'<phase duration="{dur}" state="{s}"/>'
        new = f'<tlLogic id="{tl}" type="static" programID="0" offset="{offset:.2f}">{body}</tlLogic>'
        x, n = re.subn(rf'<tlLogic id="{re.escape(tl)}"[^>]*>.*?</tlLogic>', new, x, flags=re.S)
        assert n == 1, tl
    path.write_text(x)


class Run:
    def __init__(self, d, a):
        self.d, self.a = d, a
        self.net_lengths = None
        self._fcd = None
        self.rep = {}

    @property
    def lengths(self):
        if self.net_lengths is None:
            self.net_lengths = {l.get('id'): float(l.get('length')) for l in ET.parse(self.d / 'net.xml').getroot().iter('lane')}
        return self.net_lengths

    def lane_len(self, cell, lane):
        return self.lengths[f'{cell}.{lane}']

    def fcd(self):
        if self._fcd is None:
            f = pd.read_csv(self.d / 'fcd.csv', usecols=['time', 'trip', 'lane', 'pos', 'speed'], dtype={'trip': 'category', 'lane': 'category', 'time': 'float32', 'pos': 'float32', 'speed': 'float32'})
            names = pd.Index(f.trip.cat.categories.str.split('.').str[0])
            cells = names.unique()
            f['cell'] = pd.Categorical.from_codes(cells.get_indexer(names)[f.trip.cat.codes.to_numpy()], categories=cells)
            self._fcd = f
            self._groups = {k: g.index.to_numpy() for k, g in f.groupby('cell', observed=True)}
        return self._fcd

    def cell(self, name):
        f = self.fcd()
        g = f.iloc[self._groups[name]].copy()
        g['trip'] = g.trip.cat.remove_unused_categories()
        g['lane'] = g.lane.cat.remove_unused_categories()
        return g

    def trips(self, name=None):
        t = pd.read_csv(self.d / 'trips.csv', usecols=['trip', 'depart', 'arrival', 'duration', 'time_loss', 'route_length'])
        t['cell'] = t.trip.str.split('.').str[0]
        return t if name is None else t[t.cell == name].copy()

    def edges(self):
        e = pd.read_csv(self.d / 'edges.csv')
        e['cell'] = e.edge.str.split('.').str[0]
        e = e[~e.edge.str.startswith(':')]
        return e


def leave_times(f, cell, lane, L):
    """When each car's front passes the end of a lane. Interpolated to the next sample, on the next lane."""
    lid = f'{cell}.{lane}'
    g = f.sort_values(['trip', 'time'], kind='stable')
    tr, ti, po, la = g.trip.cat.codes.to_numpy(), g.time.to_numpy(), g.pos.to_numpy(), g.lane.astype(str).to_numpy()
    on = la == lid
    last = on & np.r_[(tr[1:] != tr[:-1]) | (la[1:] != lid), True]
    out = {}
    names = g.trip.astype(str).to_numpy()
    for i in np.flatnonzero(last):
        if i + 1 < len(tr) and tr[i + 1] == tr[i]:
            frac = (L - po[i]) / max(po[i + 1] + L - po[i], 1e-6)
            out[names[i]] = ti[i] + (ti[i + 1] - ti[i]) * min(max(frac, 0), 1)
    return pd.Series(out, dtype=float).sort_values()


def pass_times(f, cell, lane, x):
    """When each car's front passes position x on a lane."""
    g = f[f.lane == f'{cell}.{lane}'].sort_values(['trip', 'time'], kind='stable')
    out = {}
    for tr, h in g.groupby('trip', observed=True):
        p, t = h.pos.to_numpy(), h.time.to_numpy()
        i = np.argmax(p >= x)
        if p[i] >= x:
            out[str(tr)] = t[i] if i == 0 else t[i - 1] + (t[i] - t[i - 1]) * (x - p[i - 1]) / max(p[i] - p[i - 1], 1e-6)
    return pd.Series(out, dtype=float).sort_values()


# ---------------------------------------------------------------- forecasts and verdicts
class Book:
    def __init__(self, driver, dt):
        self.rows, self.driver, self.dt = [], driver, dt
        self.lines = {r['id']: r for r in csv.DictReader(open(FORECASTS))}

    def nums(self, s):
        return [float(x) for x in re.findall(r'-?\d*\.?\d+', s)]

    def row(self, scene, fid, quantity, forecast, measured, tol, verdict, spread='', seeds=''):
        self.rows.append(dict(scene=scene, id=fid, quantity=quantity, forecast=forecast, measured=measured, spread=spread, tolerance=tol, verdict=verdict, seeds=seeds, driver=self.driver, dt=self.dt))
        print(f'{scene:7} {fid:5} {quantity[:46]:46} {str(forecast):>10} {str(measured):>12} {str(spread):>17} {str(tol):>11} {verdict}', flush=True)

    def info(self, scene, quantity, measured, spread='', seeds=''):
        self.row(scene, '', quantity, '', fmt(measured), '', 'info', spread, seeds)

    def check(self, scene, fid, i, vals, quantity=None, seeds='', mode='two', forecast=None, tol=None):
        """Compare the mean over seeds against number i of a forecast line. mode two, low (at least), high (at most)."""
        ln = self.lines[fid]
        fn = self.nums(ln['forecast'])
        want = forecast if forecast is not None else fn[i]
        tolfield = ln['tolerance'] if tol is None else tol
        parts = [p.strip() for p in tolfield.split(';')]
        tp = parts[i] if len(parts) > 1 and i < len(parts) else parts[0]
        vals = [v for v in np.atleast_1d(vals) if v is not None and np.isfinite(v)]
        q = quantity or ln['quantity']
        if not vals:
            self.row(scene, fid, q, fmt(want), 'none', tp, 'FAIL', seeds=seeds)
            return False
        m = float(np.mean(vals))
        n = self.nums(tp)
        if tp.strip() == 'exact':
            band = 0.0
        elif '%' in tp:
            band = abs(want) * n[0] / 100
        elif n:
            band = n[0]
        else:
            band = 0.0
        ok = (m >= want - band) if mode == 'low' else (m <= want + band) if mode == 'high' else abs(m - want) <= band + 1e-9
        spread = f'{min(vals):.3g}..{max(vals):.3g}' if len(vals) > 1 else ''
        self.row(scene, fid, q, fmt(want), fmt(m), spread=spread, tol=('>= ' if mode == 'low' else '<= ' if mode == 'high' else '') + tp, verdict='pass' if ok else 'FAIL', seeds=seeds)
        return ok

    def verdict(self, scene, fid, quantity, forecast, measured, tol, ok, spread='', seeds=''):
        self.row(scene, fid, quantity, forecast, measured, tol, 'pass' if ok else 'FAIL', spread, seeds)


def fmt(x):
    if isinstance(x, str):
        return x
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return 'nan'
    return f'{x:.3g}' if abs(x) < 100 else f'{x:.0f}'


def seedtag(scene, n=SEEDS):
    return f'{scene} arrivals 0-{n - 1}, sim {SIM_SEED}'


# ---------------------------------------------------------------- batches
BATCHES = {}


def batch(name, end, fcd=0.5, tune=()):
    def deco(fn):
        BATCHES[name] = dict(build=fn, end=end, fcd=fcd, tune=list(tune), name=name)
        return fn
    return deco


class Scene:
    """build(world, state) adds cells; measure(run, book, state) reads them."""
    registry = []

    def __init__(self, names, batch_name, build, measure):
        self.names, self.batch, self.build, self.measure = names, batch_name, build, measure
        Scene.registry.append(self)


def scene(names, batch_name):
    def deco(cls):
        Scene(names.split(','), batch_name, cls.build, cls.measure)
        return cls
    return deco


BATCH_CFG = {
    'lane': dict(end=800, fcd=0.5),
    'ring': dict(end=620, fcd=1.0),
    'sringon': dict(end=600, fcd=1.0),
    'sringoff': dict(end=600, fcd=1.0, tune=['exit_clear=0']),
    'signal': dict(end=1900, fcd=0.5),
    'signal_long': dict(end=5700, fcd=0),
    'xone': dict(end=9000, fcd=0),
    'give': dict(end=1800, fcd=0.5),
    'give2': dict(end=1500, fcd=0),
    'lc': dict(end=1400, fcd=0.5),
    'lc2': dict(end=1500, fcd=0.5),
    'drop': dict(end=1800, fcd=0),
    'drop_city': dict(end=1500, fcd=0.5),
    'slow': dict(end=800, fcd=1.0),
    'net': dict(end=1200, fcd=1.0),
    'net_long': dict(end=3000, fcd=5.0),
    'n9': dict(end=2900, fcd=1.0),
    'n10': dict(end=3000, fcd=1.0),
    'grid': dict(end=7200, fcd=0),
    'grid_sig': dict(end=7200, fcd=0),
    'miss60': dict(end=1500, fcd=0.5, tune=['miss_patience=60']),
    'miss120': dict(end=1500, fcd=0.5, tune=['miss_patience=120']),
    'miss0': dict(end=1500, fcd=0.5, tune=['miss_patience=0']),
    'block1': dict(end=1500, fcd=0.5, tune=['exit_comply=1']),
    'block25': dict(end=1500, fcd=0.5, tune=['exit_comply=0.25']),
    'block0': dict(end=1500, fcd=0.5, tune=['exit_comply=0']),
}


# --- One lane
def queue_line(c, n, length, route, kmh=None):
    for i in range(n):
        c.car(f'v{i}', i * 0.001, route, pos=length - 16 - i * 8.0, speed='0')


@scene('L1,L3,L4,L7', 'lane')
class Lane:
    T = 230.0

    @staticmethod
    def build(w, st):
        for kmh in (50, 100, 30):
            for r in range(SEEDS):
                c = w.cell(f'L1k{kmh}r{r}', 50)
                v = kmh / 3.6
                c.line(0, 2000, ['a', 's', 'b'], types={'s': 'traffic_light'})
                w.nodes[-2] = f'<node id="{c.id("s")}" x="1500.00" y="{c.y0:.2f}" type="traffic_light"/>'
                c.edge('in', 'a', 's', v=v)
                c.edge('out', 's', 'b', v=v)
                c.signal('s', [(Lane.T, 'r'), (9000, 'G')])
                queue_line(c, 180, 1500, ['in', 'out'])

    @staticmethod
    def measure(run, book, st):
        caps = {50: [], 100: [], 30: []}
        spacing, wave, placed = [], [], []
        for kmh in caps:
            for r in range(SEEDS):
                name = f'L1k{kmh}r{r}'
                f = run.cell(name)
                t = pass_times(f, name, 'out_0', min(300.0, run.lane_len(name, 'out_0') - 5))
                t = t[t > Lane.T].values
                if len(t) > 20:
                    w = t[10:]
                    w = w[w <= w[0] + 300]
                    caps[kmh].append(3600 * (len(w) - 1) / (w[-1] - w[0]))
                if kmh == 50:
                    L = run.lane_len(name, 'in_0')
                    q = f[(np.abs(f.time - (Lane.T - 1)) < 0.26) & (f.lane == f'{name}.in_0')].sort_values('pos', ascending=False)
                    q = q[q.speed < 0.2]
                    placed.append(len(q))
                    spacing.append(float(np.median(-np.diff(q.pos.values[:100]))))
                    starts = []
                    for tr, x in zip(q.trip.astype(str).values[:60], q.pos.values[:60]):
                        g = f[(f.trip == tr) & (f.time >= Lane.T) & (f.speed > 1.0)]
                        if len(g):
                            starts.append((L - x, g.time.min()))
                    st_ = np.array(starts)
                    if len(st_) > 10:
                        wave.append(np.polyfit(st_[:, 1], st_[:, 0], 1)[0] * 3.6)
        tag = seedtag('L1')
        book.check('L1', 'F001', 0, caps[50], seeds=tag)
        book.check('L1', 'F002', 0, caps[100], seeds=tag)
        book.check('L1', 'F003', 0, caps[30], seeds=tag)
        m = float(np.mean(caps[50]))
        book.verdict('L1', 'F089', 'saturation 50 km/h: real read 1750 sweep 1640-1900', '1750', fmt(m), '1640-1900', 1640 <= m <= 1900, seeds=tag)
        book.check('L3', 'F004', 0, spacing, seeds=tag)
        book.check('L4', 'F005', 0, wave, seeds=tag)
        st['s'] = float(np.mean(spacing)) if spacing else float('nan')
        st['w'] = float(np.mean(wave)) if wave else float('nan')
        T = st['s'] / (st['w'] / 3.6)
        st['T'] = T
        book.info('L4', 'T from s/w (s)', T)
        self_cap = 3600 / (T + st['s'] / V50)
        book.check('L1', 'F050', 0, caps[50], forecast=self_cap, tol='3%', seeds=tag)
        # L7: instrument agrees with trajectories, and nobody is lost
        e = run.edges()
        worst = 0.0
        for r in range(SEEDS):
            name = f'L1k50r{r}'
            f = run.cell(name).sort_values(['trip', 'time'], kind='stable')
            same = (f.trip.values[1:] == f.trip.values[:-1]) & (f.lane.astype(str).values[1:] == f.lane.astype(str).values[:-1]) & (f.lane.astype(str).values[1:] == f'{name}.in_0')
            d_fcd = np.diff(f.pos.values)[same].sum()
            d_edge = e[(e.edge == f'{name}.in')].distance.sum()
            worst = max(worst, abs(d_fcd - d_edge) / max(d_edge, 1))
        book.verdict('L7', 'F007', 'distance: trajectories against edge counters (rel)', 'exact', fmt(worst), '1%', worst <= 0.01, seeds=tag)


@scene('L5', 'lane')
class Tail:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            c = w.cell(f'L5r{r}', 50)
            c.node('a', 0, 0)
            c.node('s', 1200, 0, 'traffic_light')
            c.node('b', 1400, 0)
            c.edge('in', 'a', 's')
            c.edge('out', 's', 'b')
            c.signal('s', [(9000, 'r')])
            for i, t in enumerate(uniform(600, 0, 700)):
                c.car(f'v{i}', t, ['in', 'out'])

    @staticmethod
    def measure(run, book, st):
        out = []
        for r in range(SEEDS):
            name = f'L5r{r}'
            f = run.cell(name)
            s = f[f.speed < 0.5]
            g = s.groupby(np.floor(s.time / 5)).pos.min()
            g = g[(g.index * 5 > 120) & (g.index * 5 < 500)]
            if len(g) > 5:
                out.append(-np.polyfit(g.index * 5, g.values, 1)[0] * 3.6)
        book.check('L5', 'F006', 0, out, seeds=seedtag('L5'))


@scene('L6', 'lane')
class Bottleneck:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            c = w.cell(f'L6r{r}', 50)
            c.node('a', 0, 0)
            c.node('m', 1500, 0)
            c.node('n', 1800, 0)
            c.node('b', 2000, 0)
            c.edge('in', 'a', 'm')
            c.edge('slow', 'm', 'n', v=1.63)
            c.edge('out', 'n', 'b')
            for i, t in enumerate(uniform(900, 0, 800)):
                c.car(f'v{i}', t, ['in', 'slow', 'out'])

    @staticmethod
    def measure(run, book, st):
        u, cap = [], []
        for r in range(SEEDS):
            name = f'L6r{r}'
            f = run.cell(name)
            s = f[(f.lane == f'{name}.in_0') & (f.speed < 7.0)]
            g = s.groupby(np.floor(s.time / 10)).pos.min()
            g = g[(g.index * 10 > 350) & (g.index * 10 < 780)]
            if len(g) > 5:
                u.append(-np.polyfit(g.index * 10, g.values, 1)[0] * 3.6)
            t = pass_times(f, name, 'slow_0', 50.0).values
            t = t[t > 250]
            if len(t) > 5:
                cap.append(3600 * (len(t) - 1) / (t[-1] - t[0]))
        book.check('L6', 'F054', 0, u, seeds=seedtag('L6'))
        book.info('L6', 'bottleneck flow c (veh/h), forecast used 600', float(np.mean(cap)) if cap else float('nan'))


def ring_cars(c, N, P, edges, repeat, vtype='car'):
    """N cars evenly placed, front first on each edge, none closer than a car length to the start of an edge."""
    k = len(edges)
    L = P / k
    per = [N // k + (1 if j < N % k else 0) for j in range(k)]
    n = 0
    for j, m in enumerate(per):
        route = [edges[(j + i) % k] for i in range(k)]
        sp = L / max(m, 1)
        for i in range(m):
            c.car(f'v{n}', 0.0, route, pos=L - 1.0 - i * sp, speed='0', repeat=repeat, vtype=vtype)
            n += 1
    return n


@scene('L2', 'ring')
class Ring:
    NS = (15, 25, 33, 37, 41, 50, 67, 83, 100)
    P = 1000.0

    @staticmethod
    def build(w, st):
        for N in Ring.NS:
            for r in range(3):
                c = w.cell(f'L2n{N}r{r}', 340, 340)
                edges = c.ring(Ring.P / (2 * math.pi), 4)
                for i in range(4):
                    c.signal(f'n{i}', [(45, 'r'), (90000, 'G')])
                ring_cars(c, N, Ring.P, edges, 60)

    @staticmethod
    def measure(run, book, st):
        rows = []
        for N in Ring.NS:
            for r in range(3):
                name = f'L2n{N}r{r}'
                f = run.cell(name)
                f = f[f.time >= 320]
                if not len(f):
                    continue
                n = f.groupby('time').size().median()
                v = f.speed.mean()
                P = sum(run.lane_len(name, f'e{i}_0') for i in range(4))
                rows.append(dict(N=N, r=r, placed=n, P=P, k=n / P * 1000, v=v, q=n / P * v * 3600))
        d = pd.DataFrame(rows)
        st['L2'] = d
        g = d.groupby('N').mean(numeric_only=True)
        book.info('L2', 'P of the ring (m), cars placed at N=100', f'{d.P.mean():.0f}, {g.placed.max():.0f}')
        book.info('L2', 'q(k): ' + ' '.join(f'{a:.0f}:{b:.0f}' for a, b in zip(g.k, g.q)), 0.0)
        free = g[g.k < 30]
        cong = g[g.k > 45]
        vf = (free.q / free.k).mean()
        pc = np.polyfit(cong.k, cong.q, 1) if len(cong) > 2 else (float('nan'), float('nan'))
        kc = pc[1] / (vf - pc[0])
        book.check('L2', 'F051', 0, [kc], quantity='critical density (free and congested branch meet)', seeds='L2 3 per density, sim 1')
        book.check('L2', 'F052', 0, d.groupby('r').q.max().values, seeds='L2 3 per density, sim 1')
        spac = {10: 100, 12: 83, 15: 67, 20: 50}
        vs = [d[d.N == spac[x]].v.values for x in (10, 12, 15, 20)]
        for i, v in enumerate(vs):
            book.check('L2', 'F053', i, v, quantity=f'congested speed at spacing {[10, 12, 15, 20][i]} m', seeds='L2 3 per density, sim 1')


# --- One signal
def s_cell(w, name, flow_times, G=40.0, y=3.0, C=90.0, red0=None, L=800.0):
    c = w.cell(name, 50)
    c.node('a', 0, 0)
    c.node('s', L, 0, 'traffic_light')
    c.node('b', L + 300, 0)
    c.edge('in', 'a', 's')
    c.edge('out', 's', 'b')
    c.signal('s', [(G, 'G'), (y, 'y'), (C - G - y, 'r')] if red0 is None else [(red0, 'r'), (90000, 'G')])
    for i, t in enumerate(flow_times):
        c.car(f'v{i}', t, ['in', 'out'])
    return c


def closed_form_headways(a, tr, d0, T, s, v, n):
    def tau(x):
        return math.sqrt(2 * x / a) if x <= v * v / (2 * a) else v / a + (x - v * v / (2 * a)) / v
    t = [tr + i * T + tau(i * s + d0) for i in range(n)]
    return [t[0]] + [t[i] - t[i - 1] for i in range(1, n)]


@scene('S1,S2,S3', 'signal')
class Discharge:
    R = 60.0

    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            c = w.cell(f'S1r{r}', 50)
            c.node('a', 0, 0)
            c.node('s', 500, 0, 'traffic_light')
            c.node('b', 900, 0)
            c.edge('in', 'a', 's')
            c.edge('out', 's', 'b')
            c.signal('s', [(Discharge.R, 'r'), (90000, 'G')])
            for i in range(25):
                c.car(f'v{i}', i * 0.5, ['in', 'out'], pos=480.0 - i * 9.0, speed='0')

    @staticmethod
    def measure(run, book, st):
        H, line, stop0 = [], [], []
        for r in range(SEEDS):
            name = f'S1r{r}'
            f = run.cell(name)
            L = run.lane_len(name, 'in_0')
            t = leave_times(f, name, 'in_0', L).values
            if len(t) < 13:
                continue
            H.append(np.r_[t[0] - Discharge.R, np.diff(t)])
            head = f[(f.time < Discharge.R) & (f.lane == f'{name}.in_0')]
            stop0.append(L - head.pos.max())
            after = f[f.lane != f'{name}.in_0'].sort_values('time').groupby('trip', observed=True).speed.first()
            line.append(after.loc[[x for x in after.index if int(str(x).split('.v')[1]) >= 10]].mean())
        H = np.array([h[:25] for h in H if len(h) >= 25])
        tag = seedtag('S1')
        hs = H[:, 9:].mean(axis=1)
        book.check('S1', 'F008', 0, hs, seeds=tag)
        book.info('S1', 'speed at the line from car 11 on (km/h)', float(np.mean(line) * 3.6))
        book.info('S1', 'first car stop distance d0 (m)', float(np.mean(stop0)))
        st['hs'] = float(hs.mean())
        for i in range(9):
            book.check('S2', 'F009', i, H[:, i], quantity=('t1 after green' if i == 0 else f'headway car {i + 1}'), seeds=tag)
        lost = (H[:, :4] - hs[:, None]).sum(axis=1)
        book.check('S3', 'F010', 0, lost, seeds=tag)
        st['lost'] = float(lost.mean())


@scene('S4', 'signal')
class Sat:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            s_cell(w, f'S4r{r}', uniform(1200, 0, 1880))

    @staticmethod
    def measure(run, book, st):
        out = []
        for r in range(SEEDS):
            name = f'S4r{r}'
            t = run.trips(name)
            out.append(((t.arrival >= 450) & (t.arrival < 450 + 1350)).sum() * 3600 / 1350)
        book.check('S4', 'F011', 0, out, seeds=seedtag('S4'))
        book.verdict('S4', 'F090', 'capacity at real saturation', '778', fmt(float(np.mean(out))), '729-844', 729 <= np.mean(out) <= 844, seeds=seedtag('S4'))
        st['c'] = float(np.mean(out))


@scene('S5,S6', 'signal')
class Uniform:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            s_cell(w, f'S5r{r}', uniform(600, 0, 1800))
        fr = w.cell('Sfree', 50)
        fr.node('a', 0, 0)
        fr.node('b', 1100, 0)
        fr.edge('in', 'a', 'b')
        for i, t in enumerate(uniform(120, 0, 1800)):
            fr.car(f'v{i}', t, ['in'])

    @staticmethod
    def measure(run, book, st):
        free = run.trips('Sfree')
        tf = (free.duration).mean()
        st['tfree'] = float(tf)
        N, L_, clear, D = [], [], [], []
        lost = st.get('lost', 0.0)
        for r in range(SEEDS):
            name = f'S5r{r}'
            allf = run.cell(name)
            Ll = run.lane_len(name, 'in_0')
            lt = leave_times(allf, name, 'in_0', Ll)
            f = allf[allf.lane == f'{name}.in_0']
            # one queue per cycle: every car the queue slowed under a quarter of free speed, by the cycle it crossed in
            slow = f[f.speed < 0.25 * V50]
            first = slow.sort_values('time').groupby('trip', observed=True).first()
            nc, lc, cl = [], [], []
            for k in range(3, 19):
                cross = lt[(lt.values >= k * 90) & (lt.values < (k + 1) * 90)]
                members = [x for x in cross.index if x in first.index]
                if not members:
                    continue
                nc.append(len(members))
                lc.append(Ll - first.loc[members].pos.min())
                cl.append(cross.loc[members].max() - k * 90 - lost)
            N.append(float(np.mean(nc)))
            L_.append(float(np.mean(lc)))
            clear.append(float(np.mean(cl)))
            t = run.trips(name)
            t = t[(t.depart > 270) & (t.depart < 1500)]
            D.append(t.duration.mean() - tf)
        tag = seedtag('S5')
        book.check('S5', 'F012', 0, N, quantity='max queue qa 600 (cars)', seeds=tag)
        book.check('S5', 'F012', 1, L_, quantity='max queue qa 600 (m)', seeds=tag)
        book.check('S5', 'F012', 2, clear, quantity='queue clears after effective green (s)', seeds=tag)
        book.check('S6', 'F013', 0, D, seeds=tag)


def delay_of(run, name, times, tfree, t0, t1):
    t = run.trips(name)
    idx = t.trip.str.split('.').str[1].str[1:].astype(int).values
    sched = np.array(times)[idx]
    keep = (sched >= t0) & (sched < t1)
    return float((t.arrival.values[keep] - sched[keep]).mean() - tfree), t, sched


@scene('S7,N8', 'signal_long')
class Webster:
    XS = (304, 448, 600, 720)

    @staticmethod
    def build(w, st):
        st['web'] = {}
        fr = w.cell('Wfree', 50)
        fr.node('a', 0, 0)
        fr.node('b', 1100, 0)
        fr.edge('in', 'a', 'b')
        for i, t in enumerate(uniform(120, 0, 3000)):
            fr.car(f'v{i}', t, ['in'])
        for q in Webster.XS:
            for r in range(SEEDS):
                t = poisson(arrival_rng(f'S7{q}', r), q, 0, 5400)
                st['web'][f'S7q{q}r{r}'] = t
                s_cell(w, f'S7q{q}r{r}', t)
        for q, end in ((640, 3600), (960, 1800)):
            for r in range(SEEDS):
                t = poisson(arrival_rng(f'N8{q}', r), q, 0, end)
                st['web'][f'N8q{q}r{r}'] = t
                s_cell(w, f'N8q{q}r{r}', t)

    @staticmethod
    def measure(run, book, st):
        tf = float(run.trips('Wfree').duration.mean())
        for i, q in enumerate(Webster.XS):
            out = [delay_of(run, f'S7q{q}r{r}', st['web'][f'S7q{q}r{r}'], tf, 600, 5200)[0] for r in range(SEEDS)]
            book.check('S7', 'F014', i, out, quantity=f'Webster delay qa {q}', seeds=seedtag(f'S7{q}'))
        ratios, growth = [], []
        for r in range(SEEDS):
            name = f'N8q640r{r}'
            tr = run.trips(name)
            sched = np.array(st['web'][name])
            ns = lambda t: (sched <= t).sum() - (tr.arrival <= t).sum()
            a = np.mean([ns(t) for t in np.arange(900, 2250, 30)])
            b = np.mean([ns(t) for t in np.arange(2250, 3600, 30)])
            ratios.append(b / max(a, 0.1))
            name = f'N8q960r{r}'
            tr = run.trips(name)
            sched = np.array(st['web'][name])
            n0 = np.mean([(sched <= t).sum() - (tr.arrival <= t).sum() for t in np.arange(300, 390, 10)])
            n1 = np.mean([(sched <= t).sum() - (tr.arrival <= t).sum() for t in np.arange(1710, 1800, 10)])
            cap = st.get('c', 800.0)
            growth.append((n1 - n0) / ((960 - 800) * 1410 / 3600))
        book.check('N8', 'F077', 0, ratios, quantity='x .8: queue second half over first half', seeds=seedtag('N8640'))
        book.check('N8', 'F077', 1, growth, quantity='x 1.2: growth over Q-c', seeds=seedtag('N8960'))


@scene('S8', 'signal')
class Over:
    @staticmethod
    def build(w, st):
        st['s8'] = {}
        for q in (720, 900):
            for r in range(10):
                t = poisson(arrival_rng(f'S8{q}', r), q, 0, 900)
                st['s8'][f'S8q{q}r{r}'] = t
                s_cell(w, f'S8q{q}r{r}', t)

    @staticmethod
    def measure(run, book, st):
        tf = st.get('tfree') or float(run.trips('Sfree').duration.mean())
        for i, q in enumerate((720, 900)):
            out = [delay_of(run, f'S8q{q}r{r}', st['s8'][f'S8q{q}r{r}'], tf, 0, 900)[0] for r in range(10)]
            book.check('S8', 'F085', i, out, quantity=f'delay qa {q} 15 min', seeds=seedtag(f'S8{q}', 10))
        gr = []
        for r in range(10):
            name = f'S8q900r{r}'
            tr = run.trips(name)
            sched = np.array(st['s8'][name])
            # queue at the end of the period: in the system, less the cars free flow would have en route
            en_route = 900 * tf / 3600
            n = np.mean([(sched <= t).sum() - (tr.arrival <= t).sum() for t in np.arange(811, 900, 10)])
            gr.append(n - en_route)
        book.check('S8', 'F015', 0, gr, seeds=seedtag('S8900', 10))


@scene('X1', 'xone')
class Clones:
    @staticmethod
    def build(w, st):
        c = st.get('c', 800.0)
        qa = 0.85 * c
        st['x1'] = {}
        st['x1qa'] = qa
        fr = w.cell('Xfree', 50)
        fr.node('a', 0, 0)
        fr.node('b', 1100, 0)
        fr.edge('in', 'a', 'b')
        for i, t in enumerate(uniform(120, 0, 3000)):
            fr.car(f'v{i}', t, ['in'])
        s_cell(w, 'Xuni', uniform(qa, 0, 8400))
        st['x1']['Xuni'] = uniform(qa, 0, 8400)
        for n in (1, 3, 5.6):
            # Copied within +-150 s, the demand's own rule. Five and ten copies give 2.97 and 5.63 in 5 min counts (dispersion.py).
            copies = {1: 1, 3: 5, 5.6: 10}[n]
            for r in range(SEEDS):
                rng = arrival_rng(f'X1{n}', r)
                base = poisson(rng, qa / copies, 0, 8400)
                times = []
                for b in base:
                    times += [b] if n == 1 else list(b + rng.uniform(-150, 150, copies))
                times = sorted(t for t in times if 0 <= t < 8400)
                st['x1'][f'X1n{n}r{r}'] = times
                s_cell(w, f'X1n{str(n).replace(".", "p")}r{r}', times)

    @staticmethod
    def measure(run, book, st):
        tf = float(run.trips('Xfree').duration.mean())
        qa = st['x1qa']
        d1 = delay_of(run, 'Xuni', st['x1']['Xuni'], tf, 900, 8000)[0]
        book.info('X1', f'qa {qa:.0f}, uniform delay (s)', d1)
        for i, n in enumerate((1, 3, 5.6)):
            I, Q = [], []
            for r in range(SEEDS):
                times = st['x1'][f'X1n{n}r{r}']
                name = f'X1n{str(n).replace(".", "p")}r{r}'
                counts = np.histogram(times, bins=np.arange(600, 8100, 300))[0]
                I.append(counts.var() / counts.mean())
                d = delay_of(run, name, times, tf, 900, 8000)[0]
                Q.append(qa / 3600 * (d - d1))
            book.check('X1', 'F084', i, I, quantity=f'input var/mean, copies {n}', seeds=seedtag(f'X1{n}'))
            book.check('X1', 'F039', i, Q, quantity=f'random queue, copies {n} (cars)', seeds=seedtag(f'X1{n}'))


# --- One give-way
def t_junction(w, name, qp, seed_key, tm=0.0, minor_end=1800, r=0, through=False, major_lanes=1, up=500):
    """Major west to east, minor from the south. Minor right, or through to the north."""
    c = w.cell(name, 500)
    c.node('w', 0, 0)
    c.node('c', up, 0)
    c.node('e', up + 300, 0)
    c.node('s', up, -150)
    c.edge('we', 'w', 'c', prio=5, lanes=major_lanes)
    c.edge('ce', 'c', 'e', prio=5, lanes=major_lanes)
    c.edge('sc', 's', 'c', prio=1)
    if through:
        c.node('n', up, 150)
        c.edge('cn', 'c', 'n', prio=1)
    rng = arrival_rng(seed_key, r)
    k = 0
    for li in range(major_lanes):
        for t in poisson(rng, qp / major_lanes, 0, minor_end, tm):
            c.car(f'm{k}', t, ['we', 'ce'], lane=li)
            k += 1
    route = ['sc', 'cn'] if through else ['sc', 'ce']
    for i, t in enumerate(uniform(1800, 0, minor_end)):
        c.car(f's{i}', t, route)
    return c


def gaps_log(run, name, major_lanes=1):
    f = run.cell(name)
    a = f[f.trip.astype(str).str.contains(r'\.m')].copy()
    b = f[f.trip.astype(str).str.contains(r'\.s')].copy()
    if len(a):
        a['trip'] = a.trip.astype(str).astype('category')
    b['trip'] = b.trip.astype(str).astype('category')
    tm = pd.concat([leave_times(a, name, f'we_{l}', run.lane_len(name, f'we_{l}')) for l in range(major_lanes)]).sort_values() if len(a) else pd.Series(dtype=float)
    ts = leave_times(b, name, 'sc_0', run.lane_len(name, 'sc_0'))
    return tm.values, ts.values


def follow_up(entries, major, t0=300):
    """Mean headway between minor cars entering in one major gap, under 6 s apart."""
    e = entries[entries > t0]
    h = []
    for x, y in zip(e[:-1], e[1:]):
        if not np.any((major > x) & (major < y)) and y - x < 8.0:
            h.append(y - x)
    return float(np.mean(h)) if h else float('nan')


def critical_gap(major, entries, t0=300):
    """Maximum likelihood, one largest rejected and one accepted gap per driver, lognormal. Troutbeck, monograph ch. 8."""
    major = major[major > t0]
    pairs = []
    acc = np.searchsorted(major, entries[entries > t0])
    prev_exit = t0
    for e, k in zip(entries[entries > t0], acc):
        if k == 0 or k >= len(major):
            prev_exit = e
            continue
        acc_gap = major[k] - major[k - 1]
        head_from = prev_exit
        idx = np.flatnonzero((major > head_from) & (major < major[k - 1]))
        rej = 0.0
        if len(idx):
            rej = float(np.max(np.diff(np.r_[major[idx], major[k - 1]])))
        if major[k - 1] >= prev_exit:
            pairs.append((rej, acc_gap))
        prev_exit = e
    p = np.array([x for x in pairs if x[1] > x[0] and x[1] > 0.5])
    if len(p) < 15:
        return float('nan'), len(p)
    from math import erf

    def cdf(x, mu, sd):
        v = np.where(x > 0, (np.log(np.maximum(x, 1e-6)) - mu) / sd, -50)
        return 0.5 * (1 + np.vectorize(erf)(v / np.sqrt(2)))
    best, arg = -1e18, None
    for mu in np.linspace(np.log(1.5), np.log(12), 60):
        for sd in (0.08, 0.12, 0.18, 0.25, 0.35, 0.5):
            ll = np.log(np.maximum(cdf(p[:, 1], mu, sd) - cdf(p[:, 0], mu, sd), 1e-12)).sum()
            if ll > best:
                best, arg = ll, (mu, sd)
    return float(np.exp(arg[0] + arg[1] ** 2 / 2)), len(p)


@scene('G1,G4', 'give')
class Give:
    QS = (0, 400, 800, 1200)

    @staticmethod
    def build(w, st):
        for q in Give.QS:
            for r in range(SEEDS):
                t_junction(w, f'G1q{q}r{r}', q, f'G1{q}', r=r)

    @staticmethod
    def measure(run, book, st):
        caps, tf, tc = {}, [], []
        tfs = {}
        for q in Give.QS:
            caps[q] = []
            tfs[q] = []
            for r in range(SEEDS):
                name = f'G1q{q}r{r}'
                major, entries = gaps_log(run, name)
                e = entries[(entries >= 300) & (entries < 1800)]
                caps[q].append(len(e) * 3600 / 1500)
                tfs[q].append(follow_up(entries, major))
                if q in (400, 800):
                    v, n = critical_gap(major, entries)
                    if np.isfinite(v):
                        tc.append(v)
        st['G1'] = {q: float(np.mean(v)) for q, v in caps.items()}
        for i, q in enumerate(Give.QS):
            tag = seedtag(f'G1{q}')
            book.check('G1', 'F016', i, caps[q], quantity=f'HBS right, major {q}', seeds=tag)
            book.check('G1', 'F018', i, caps[q], quantity=f'tf 3.0 t0 4.9, major {q}', seeds=tag)
            book.check('G1', 'F017', i, caps[q], quantity=f'report 23 before fix, major {q}', seeds=tag)
        all_tf = np.array([x for v in tfs.values() for x in v if np.isfinite(x)])
        book.check('G1', 'F058', 0, all_tf, seeds='G1 all')
        for q in Give.QS[1:]:
            got = []
            for r in range(SEEDS):
                major, _ = gaps_log(run, f'G1q{q}r{r}')
                got.append(((major >= 300) & (major < 1800)).sum() * 3600 / 1500)
            book.check('G1', 'F088', 0, np.array(got) / q, quantity=f'major delivered / offered, major {q}', seeds=seedtag(f'G1{q}'))
        book.info('G1', 'tf by major flow: ' + ' '.join(f'{q}:{np.nanmean(v):.2f}' for q, v in tfs.items()), 0.0)
        book.check('G4', 'F057', 0, tc, seeds='G1 q 400 800')


@scene('G2', 'give')
class Tanner:
    @staticmethod
    def build(w, st):
        for q in (400, 800, 1200):
            for r in range(SEEDS):
                t_junction(w, f'G2q{q}r{r}', q, f'G2{q}', r=r, tm=2.0)

    @staticmethod
    def measure(run, book, st):
        for i, q in enumerate((400, 800, 1200)):
            out = []
            for r in range(SEEDS):
                _, e = gaps_log(run, f'G2q{q}r{r}')
                out.append(((e >= 300) & (e < 1800)).sum() * 3600 / 1500)
            book.check('G2', 'F055', i, out, quantity=f'Tanner t_m 2, major {q}', seeds=seedtag(f'G2{q}'))


@scene('G3', 'give')
class TwoMajor:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            t_junction(w, f'G3a{r}', 800, 'G3a', r=r, through=True)
            t_junction(w, f'G3b{r}', 800, 'G3b', r=r, through=True, major_lanes=2)

    @staticmethod
    def measure(run, book, st):
        a, b = [], []
        for r in range(SEEDS):
            for name, l, tgt in ((f'G3a{r}', 1, a), (f'G3b{r}', 2, b)):
                _, e = gaps_log(run, name, l)
                tgt.append(((e >= 300) & (e < 1800)).sum() * 3600 / 1500)
        book.info('G3', 'minor through q 800: one major lane, two (veh/h); HBS 355', f'{np.mean(a):.0f}, {np.mean(b):.0f}')
        book.check('G3', 'F056', 0, np.array(b) / np.maximum(np.mean(a), 1), seeds=seedtag('G3a') + '; G3b')


def cross(w, name, arms=('n', 's', 'e', 'w'), jtype='priority', L=200, major=('e', 'w')):
    """A cross: arm in edges are i2c by arm name, out edges c2o."""
    c = w.cell(name, 2 * L + 50)
    c.node('c', L, L, jtype)
    pos = dict(n=(L, 2 * L), s=(L, 0), e=(2 * L, L), w=(0, L))
    for a in arms:
        c.node(a, *pos[a])
        pr = 5 if a in major else 1
        c.edge(f'i{a}', a, 'c', prio=pr)
        c.edge(f'o{a}', 'c', a, prio=pr)
    return c


@scene('G5', 'give')
class Rank:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            rng = arrival_rng('G5', r)
            c = cross(w, f'G5a{r}', arms=('s', 'e', 'w'))
            k = 0
            for arr, rt, q in (('m', ['iw', 'oe'], 200), ('n', ['ie', 'ow'], 50), ('l', ['ie', 'os'], 150)):
                for t in poisson(rng, q, 0, 1800):
                    c.car(f'{arr}{k}', t, rt)
                    k += 1
            for i, t in enumerate(uniform(1800, 0, 1800)):
                c.car(f's{i}', t, ['is', 'ow'])
            rng = arrival_rng('G5b', r)
            c = cross(w, f'G5b{r}')
            k = 0
            for arr, rt, q in (('m', ['iw', 'oe'], 150), ('n', ['ie', 'ow'], 150), ('l', ['ie', 'os'], 50), ('p', ['iw', 'on'], 50), ('t', ['in', 'os'], 60)):
                for t in poisson(rng, q, 0, 1800):
                    c.car(f'{arr}{k}', t, rt)
                    k += 1
            for i, t in enumerate(uniform(1800, 0, 1800)):
                c.car(f's{i}', t, ['is', 'ow'])

    @staticmethod
    def measure(run, book, st):
        a, b = [], []
        for r in range(SEEDS):
            for name, tgt in ((f'G5a{r}', a), (f'G5b{r}', b)):
                t = run.trips(name)
                t = t[t.trip.str.contains(r'\.s')]
                tgt.append(((t.arrival >= 300) & (t.arrival < 1800)).sum() * 3600 / 1500)
        book.check('G5', 'F059', 0, a, seeds=seedtag('G5'))
        book.check('G5', 'F060', 0, b, seeds=seedtag('G5b'))


@scene('G6', 'give')
class Shared:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            c = t_junction(w, f'G6r{r}', 400, 'G6', r=r, through=True)
            w.veh = [v for v in w.veh if f'id="{c.name}.s' not in v[1]]
            rng = arrival_rng('G6m', r)
            for i, t in enumerate(uniform(1800, 0, 1800)):
                c.car(f's{i}', t, ['sc', 'ce'] if rng.random() < 0.5 else ['sc', 'cn'])

    @staticmethod
    def measure(run, book, st):
        out = []
        for r in range(SEEDS):
            _, e = gaps_log(run, f'G6r{r}')
            out.append(((e >= 300) & (e < 1800)).sum() * 3600 / 1500)
        book.check('G6', 'F019', 0, out, seeds=seedtag('G6m'))


@scene('G7', 'give2')
class Wait:
    QS = (100, 200, 300, 400)

    @staticmethod
    def build(w, st):
        st['g7'] = {}
        for q in Wait.QS:
            for r in range(8):
                name = f'G7q{q}r{r}'
                c = t_junction(w, name, 800, f'G7m{q}', r=r, minor_end=900)
                w.veh = [v for v in w.veh if f'id="{c.name}.s' not in v[1]]
                times = poisson(arrival_rng(f'G7{q}', r), q, 0, 900)
                st['g7'][name] = times
                for i, t in enumerate(times):
                    c.car(f's{i}', t, ['sc', 'ce'])
        c = t_junction(w, 'G7free', 0, 'G7f', minor_end=900)
        w.veh = [v for v in w.veh if f'id="{c.name}.s' not in v[1]]
        for i, t in enumerate(uniform(60, 0, 900)):
            c.car(f's{i}', t, ['sc', 'ce'])

    @staticmethod
    def measure(run, book, st):
        tf = run.trips('G7free').duration.mean()
        for i, q in enumerate(Wait.QS):
            out = []
            for r in range(8):
                name = f'G7q{q}r{r}'
                t = run.trips(name)
                t = t[t.trip.str.contains(r'\.s')]
                idx = t.trip.str.split('.').str[1].str[1:].astype(int).values
                sched = np.array(st['g7'][name])[idx]
                out.append(float((t.arrival.values - sched).mean() - tf))
            book.check('G7', 'F020', i, out, quantity=f'mean wait, minor {q}', seeds=seedtag(f'G7{q}', 8))


@scene('G8', 'give')
class Roundabout:
    QS = (0, 400, 800, 1200)

    @staticmethod
    def build(w, st):
        R = 18.0
        for q in Roundabout.QS:
            for r in range(SEEDS):
                c = w.cell(f'G8q{q}r{r}', 500)
                c.y0 += 200
                for i in range(4):
                    a = 2 * math.pi * i / 4
                    c.node(f'n{i}', 300 + R * math.cos(a), R * math.sin(a))
                    c.node(f'x{i}', 300 + 250 * math.cos(a), 250 * math.sin(a))
                for i in range(4):
                    a0, a1 = 2 * math.pi * i / 4, 2 * math.pi * (i + 1) / 4
                    pts = [(300 + R * math.cos(a0 + (a1 - a0) * j / 12), R * math.sin(a0 + (a1 - a0) * j / 12)) for j in range(13)]
                    c.edge(f'e{i}', f'n{i}', f'n{(i + 1) % 4}', prio=5, v=8.33, shape=pts)
                    c.edge(f'in{i}', f'x{i}', f'n{i}', prio=1)
                    c.edge(f'ot{i}', f'n{i}', f'x{i}', prio=1)
                rng = arrival_rng(f'G8{q}', r)
                for k, t in enumerate(poisson(rng, q, 0, 1800)):
                    c.car(f'm{k}', t, ['in3', 'e3', 'e0', 'ot1'])
                for k, t in enumerate(uniform(1800, 0, 1800)):
                    c.car(f's{k}', t, ['in0', 'e0', 'ot1'])

    @staticmethod
    def measure(run, book, st):
        for i, q in enumerate(Roundabout.QS):
            out = []
            for r in range(SEEDS):
                name = f'G8q{q}r{r}'
                t = run.trips(name)
                t = t[t.trip.str.contains(r'\.s')]
                out.append(((t.arrival >= 300) & (t.arrival < 1800)).sum() * 3600 / 1500)
            book.check('G8', 'F061', i, out, quantity=f'roundabout entry, circulating {q}', seeds=seedtag(f'G8{q}'))


@scene('G9', 'give2')
class RBL:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            c = cross(w, f'G9r{r}', jtype='right_before_left', major=())
            for a, b in (('n', 's'), ('s', 'n'), ('e', 'w'), ('w', 'e')):
                for k, t in enumerate(uniform(1200, 0, 1500)):
                    c.car(f'{a}{k}', t, [f'i{a}', f'o{b}'])

    @staticmethod
    def measure(run, book, st):
        out = []
        for r in range(SEEDS):
            t = run.trips(f'G9r{r}')
            out.append(((t.arrival >= 300) & (t.arrival < 1500)).sum() * 3 / 4)
        book.check('G9', 'F062', 0, out, seeds=seedtag('G9'))


# --- Lane change
def weave(w, name, L, q_target=900, q_c=300, vt=10.0, vc=7.0, r=0, key='LC', tm=1.0, tend=1300):
    """Two feeder edges into a two-lane block of length L. Lane 0 goes on to rt, lane 1 to th. Changers need lane 1."""
    c = w.cell(name, 120)
    c.node('a', 0, -40)
    c.node('b', 0, 0)
    c.node('m', 300, 0)
    c.node('n', 300 + L, 0)
    c.node('t', 300 + L + 300, 0)
    c.node('r', 300 + L + 300, -60)
    c.edge('fa', 'a', 'm', v=vc)
    c.edge('fb', 'b', 'm', v=vt)
    # Lane speeds set the difference: after its change a car speeds up, so it can't slow the target lane for good.
    c.edge('m', 'm', 'n', lanes=2, v=vt, lane_speed={0: vc, 1: vt})
    c.edge('th', 'n', 't', v=vt)
    c.edge('rt', 'n', 'r', v=vt)
    c.conn('fa', 'm', 0, 0)
    c.conn('fb', 'm', 0, 1)
    c.conn('m', 'rt', 0, 0)
    c.conn('m', 'th', 1, 0)
    rng = arrival_rng(key, r)
    for k, t in enumerate(poisson(rng, q_target, 0, tend, tm)):
        c.car(f't{k}', t, ['fb', 'm', 'th'])
    for k, t in enumerate(uniform(q_c, 5, tend)):
        c.car(f'c{k}', t, ['fa', 'm', 'th'])
    return c


def changes(run, name, L):
    """For each changer: entry time on the block, time and position of the flip to lane 1, speed at the flip."""
    f = run.cell(name)
    f = f[f.trip.astype(str).str.contains(r'\.c')].sort_values(['trip', 'time'], kind='stable')
    a, b = f'{name}.m_0', f'{name}.m_1'
    rows = []
    for tr, h in f.groupby(f.trip.astype(str)):
        la = h.lane.astype(str).values
        on0 = np.flatnonzero(la == a)
        if not len(on0):
            continue
        t0 = h.time.values[on0[0]]
        on1 = np.flatnonzero(la == b)
        passed = len(h) and la[-1] not in (a, b)
        if len(on1):
            i = on1[0]
            rows.append(dict(trip=tr, t0=t0, t1=h.time.values[i], pos=h.pos.values[i], v=h.speed.values[i - 1], done=True, reached=True))
        else:
            rows.append(dict(trip=tr, t0=t0, t1=np.nan, pos=np.nan, v=np.nan, done=False, reached=bool(passed)))
    return pd.DataFrame(rows)


@scene('LC1', 'lc')
class LC1:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            weave(w, f'LC1r{r}', 1500, r=r, key='LC1')

    @staticmethod
    def measure(run, book, st):
        W, passes, dv = [], [], []
        for r in range(SEEDS):
            name = f'LC1r{r}'
            d = changes(run, name, 1500)
            d = d[d.done]
            if not len(d):
                continue
            W.append(float((d.t1 - d.t0).mean()))
            f = run.cell(name)
            lt = f[f.lane == f'{name}.m_1']
            lz = f[f.lane == f'{name}.m_0']
            dv.append(float(lt.speed.mean() - lz.speed.mean()))
            n, T = 0, 0.0
            pv = lt.pivot_table(index='time', columns='trip', values='pos', observed=True)
            for _, row in d.iterrows():
                g = lz[lz.trip.astype(str) == row.trip]
                if len(g) < 3:
                    continue
                t0, t1 = g.time.iloc[0], g.time.iloc[-1]
                x0, x1 = g.pos.iloc[0], g.pos.iloc[-1]
                if t0 in pv.index and t1 in pv.index:
                    a, b = pv.loc[t0], pv.loc[t1]
                    n += int((((a < x0) | a.isna()) & (b > x1)).sum())
                    T += t1 - t0
            passes.append(n / T if T > 0 else np.nan)
        tag = seedtag('LC1')
        book.check('LC1', 'F021', 0, W, seeds=tag, mode='high')
        book.check('LC1', 'F063', 0, passes, seeds=tag)
        book.info('LC1', 'speed difference actually seen (m/s), forecast 3', float(np.mean(dv)) if dv else float('nan'))


@scene('LC2', 'lc')
class LC2:
    @staticmethod
    def build(w, st):
        for L in (100, 300):
            for r in range(SEEDS):
                weave(w, f'LC2L{L}r{r}', L, r=r, key=f'LC2{L}')

    @staticmethod
    def measure(run, book, st):
        for i, L in enumerate((100, 300)):
            out, stop = [], []
            for r in range(SEEDS):
                d = changes(run, f'LC2L{L}r{r}', L)
                d = d[d.t0 < 1200]
                good = d.done & (d.v > 1.0)
                out.append(float(good.mean()))
                stop.append(float((d.done & ~(d.v > 1.0)).mean()))
            book.check('LC2', 'F022', i, out, quantity=f'share changed on the move, block {L} m', seeds=seedtag(f'LC2{L}'), mode='low')
            book.info('LC2', f'share changed only after stopping, block {L} m', float(np.mean(stop)))


@scene('LC3,LC8', 'lc2')
class LaneEnd:
    @staticmethod
    def build(w, st):
        for key, qt, qc in (('a', 900, 1800), ('b', 1800, 1800), ('c', 1500, 300)):
            for r in range(SEEDS):
                c = w.cell(f'LC3{key}{r}', 150)
                c.node('a', 0, 0)
                c.node('m', 500, 0)
                c.node('b', 900, 0)
                c.edge('up', 'a', 'm', lanes=2)
                c.edge('dn', 'm', 'b')
                c.conn('up', 'dn', 1, 0)
                fs = c.feeders('up', 2, 'a', 0, 0)
                rng = arrival_rng(f'LC3{key}', r)
                ta = uniform(qt, 0, 1450) if key == 'b' else poisson(rng, qt, 0, 1450, 1.0)
                for k, t in enumerate(ta):
                    c.car(f't{k}', t, [fs[1], 'up', 'dn'])
                for k, t in enumerate(uniform(qc, 0, 1450)):
                    c.car(f'c{k}', t, [fs[0], 'up', 'dn'])

    @staticmethod
    def lanes(run, name):
        f = run.cell(name)
        L = run.lane_len(name, 'up_0')
        f = f.sort_values(['trip', 'time'], kind='stable')
        z = f[f.trip.astype(str).str.contains(r'\.c')]
        tb = leave_times(f, name, 'up_1', run.lane_len(name, 'up_1'))
        return f, z, tb, L

    @staticmethod
    def measure(run, book, st):
        cap, shr, waits, held, tot = [], [], [], [], []
        for r in range(SEEDS):
            name = f'LC3a{r}'
            f, z, tb, L = LaneEnd.lanes(run, name)
            idx = tb.index.str.contains(r'\.c')
            t = tb.values
            cap.append(((t[idx] >= 300) & (t[idx] < 1450)).sum() * 3600 / 1150)
            name = f'LC3b{r}'
            f, z, tb, L = LaneEnd.lanes(run, name)
            idx = tb.index.str.contains(r'\.c')
            t = tb.values
            a = ((t[idx] >= 300) & (t[idx] < 1450)).sum()
            b = ((t[~idx] >= 300) & (t[~idx] < 1450)).sum()
            shr.append(a / max(a + b, 1))
            tot.append((a + b) * 3600 / 1150)
            name = f'LC3c{r}'
            f, z, tb, L = LaneEnd.lanes(run, name)
            for tr, h in z.groupby(z.trip.astype(str)):
                on0 = h[h.lane == f'{name}.up_0']
                if not len(on0):
                    continue
                nearby = on0[on0.pos > L - 100]
                if len(nearby):
                    waits.append(nearby.time.max() - nearby.time.min())
        book.check('LC3', 'F023', 0, cap, seeds=seedtag('LC3a'))
        book.check('LC3', 'F024', 0, shr, seeds=seedtag('LC3b'))
        book.info('LC3', 'both saturated: total out (veh/h)', float(np.mean(tot)))
        w = np.array(waits)
        if len(w):
            p99, mx = float(np.percentile(w, 99)), float(w.max())
            book.verdict('LC8', 'F028', 'wait, closing lane last 100 m: p99 (s)', '72.7', fmt(p99), 'p99 <= 75', p99 <= 75, spread=f'n={len(w)}', seeds=seedtag('LC3c'))
            book.verdict('LC8', 'F028', 'same: max; a hold over 300 s is a fault', '79', fmt(mx), '<= 300', mx <= 300, seeds=seedtag('LC3c'))
            book.info('LC8', 'median wait (s), I-80 22.6', float(np.median(w)))
        else:
            book.verdict('LC8', 'F028', 'wait', '72.7', 'none', 'p99 <= 75', False)


def lc4_cell(w, name, frac, r):
    c = w.cell(name, 120)
    c.node('a', 0, -40)
    c.node('b', 0, 0)
    c.node('m', 300, 0)
    c.node('n', 400, 0)
    c.node('t', 900, 0)
    c.node('r', 900, -60)
    c.edge('fa', 'a', 'm', v=10)
    c.edge('fb', 'b', 'm', v=10)
    c.edge('m', 'm', 'n', lanes=2, v=10)
    c.edge('th', 'n', 't', v=10)
    c.edge('rt', 'n', 'r', v=10)
    c.conn('fa', 'm', 0, 0)
    c.conn('fb', 'm', 0, 1)
    c.conn('m', 'rt', 0, 0)
    c.conn('m', 'th', 1, 0)
    rng = arrival_rng(f'LC4{frac}', r)
    for k, t in enumerate(uniform(2400, 0, 1400)):
        c.car(f'a{k}', t, ['fa', 'm', 'th'] if rng.random() < frac else ['fa', 'm', 'rt'], lane=0)
    for k, t in enumerate(uniform(2400, 0, 1400)):
        c.car(f'b{k}', t, ['fb', 'm', 'rt'] if rng.random() < frac else ['fb', 'm', 'th'], lane=0)


@scene('LC4', 'lc2')
class LC4:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            lc4_cell(w, f'LC4a{r}', 0.0, r)
            lc4_cell(w, f'LC4b{r}', 1 / 3, r)

    @staticmethod
    def measure(run, book, st):
        a, b = [], []
        for r in range(SEEDS):
            for n, t in ((f'LC4a{r}', a), (f'LC4b{r}', b)):
                x = run.trips(n)
                t.append(((x.arrival >= 300) & (x.arrival < 1450)).sum() * 3600 / 1150)
        book.info('LC4', 'two saturated lanes: no changes; a third change (veh/h)', f'{np.mean(a):.0f}, {np.mean(b):.0f}')
        book.check('LC4', 'F025', 0, np.array(b) / np.mean(a), seeds=seedtag('LC4b'))


def lc5_cell(w, name, dv, phi, r):
    v = V50
    c = w.cell(name, 120)
    c.node('a', 0, -40)
    c.node('b', 0, 0)
    c.node('m', 300, 0)
    c.node('n', 700, 0)
    c.node('t', 1200, 0)
    c.edge('fa', 'a', 'm', v=v - dv)
    c.edge('fb', 'b', 'm', v=v)
    c.edge('m', 'm', 'n', lanes=2, v=v, lane_speed={0: v - dv, 1: v})
    c.edge('dn', 'n', 't', v=v)
    c.conn('fa', 'm', 0, 0)
    c.conn('fb', 'm', 0, 1)
    c.conn('m', 'dn', 1, 0)
    for k, t in enumerate(uniform(2400, 0, 1400)):
        c.car(f'b{k}', t, ['fb', 'm', 'dn'], lane=0)
    for k, t in enumerate(uniform(phi, 3, 1400)):
        c.car(f'a{k}', t, ['fa', 'm', 'dn'], lane=0)


@scene('LC5', 'lc2')
class LC5:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            lc5_cell(w, f'LC5base{r}', 0, 0, r)
            lc5_cell(w, f'LC5d5r{r}', 5, 300, r)
            lc5_cell(w, f'LC5d10r{r}', 10, 300, r)

    @staticmethod
    def measure(run, book, st):
        def flow(n):
            x = run.trips(n)
            return ((x.arrival >= 300) & (x.arrival < 1450)).sum() * 3600 / 1150
        base = np.mean([flow(f'LC5base{r}') for r in range(SEEDS)])
        d5 = [1 - flow(f'LC5d5r{r}') / base for r in range(SEEDS)]
        d10 = [1 - flow(f'LC5d10r{r}') / base for r in range(SEEDS)]
        book.info('LC5', 'saturated target lane alone (veh/h)', float(base))
        book.check('LC5', 'F026', 0, d5, seeds=seedtag('LC5'))
        book.check('LC5', 'F064', 0, [np.mean(d10) / np.mean(d5)] if np.mean(d5) > 0.002 else [np.nan], seeds=seedtag('LC5'))


@scene('LC6', 'drop')
class LC6:
    @staticmethod
    def build(w, st):
        v = 100 / 3.6
        for r in range(SEEDS):
            c = w.cell(f'LC6r{r}', 50)
            c.node('a', 0, 0)
            c.node('m', 2500, 0)
            c.node('b', 3500, 0)
            c.edge('up', 'a', 'm', lanes=3, v=v)
            c.edge('dn', 'm', 'b', lanes=2, v=v)
            c.conn('up', 'dn', 1, 0)
            c.conn('up', 'dn', 2, 1)
            rng = arrival_rng('LC6', r)
            t, k = 0.0, 0
            while t < 1750:
                rate = 2000 + (6000 - 2000) * t / 1500
                t += rng.exponential(3600 / min(rate, 6000))
                c.car(f'v{k}', t, ['up', 'dn'], lane='free')
                k += 1

    @staticmethod
    def measure(run, book, st):
        e = run.edges()
        drops, pres, sus, on = [], [], [], []
        v = 100 / 3.6
        for r in range(SEEDS):
            n = f'LC6r{r}'
            dn = e[e.edge == f'{n}.dn'].set_index('begin')
            up = e[e.edge == f'{n}.up'].set_index('begin')
            q = dn.entered * 60.0
            spd = up.distance / up.samples.replace(0, np.nan)
            jam = spd[spd < 0.6 * v].index
            if not len(jam):
                continue
            onset = jam.min()
            pre = q[(q.index >= onset - 300) & (q.index < onset)].rolling(5, min_periods=1).mean().max()
            after = q[q.index >= onset + 180].mean()
            drops.append(100 * (1 - after / pre))
            pres.append(pre)
            sus.append(after)
            on.append(onset)
        ok = len(drops) > 0 and 5 <= np.mean(drops) <= 15 and min(drops) >= -1
        book.verdict('LC6', 'F027', 'capacity drop at a lane drop (%)', '5-15', fmt(float(np.mean(drops))) if drops else 'no jam', 'never negative', ok,
                     spread=f'{min(drops):.3g}..{max(drops):.3g}' if drops else '', seeds=seedtag('LC6'))
        if drops:
            book.info('LC6', f'before; after; onset s', f'{np.mean(pres):.0f}; {np.mean(sus):.0f}; {np.mean(on):.0f}')


@scene('LC7', 'slow')
class LC7:
    KMH = (30, 50, 60, 70, 80)

    @staticmethod
    def build(w, st):
        v = 100 / 3.6
        for kmh in LC7.KMH:
            w.car(f'slow{kmh}', vClass='passenger', speedDev='0', speedFactor='1', maxSpeed=f'{kmh / 3.6:.3f}')
            for r in range(SEEDS):
                c = w.cell(f'LC7k{kmh}r{r}', 50)
                c.node('a', 0, 0)
                c.node('b', 5000, 0)
                c.edge('r', 'a', 'b', lanes=2, v=v)
                rng = arrival_rng(f'LC7{kmh}', r)
                for k, t in enumerate(poisson(rng, 5000, 0, 790, 0.5)):
                    c.car(f'v{k}', t, ['r'], lane='free')
                c.car('slow', 200.0, ['r'], lane=0, vtype=f'slow{kmh}')

    @staticmethod
    def measure(run, book, st):
        out = {}
        for kmh in LC7.KMH:
            out[kmh] = []
            for r in range(SEEDS):
                name = f'LC7k{kmh}r{r}'
                f = run.cell(name)
                s = f[f.trip == f'{name}.slow'].set_index('time').pos
                s = s[s.index >= 300]
                qs = []
                for t, x in list(s.items())[::10]:
                    g = f[(f.time == t) & (f.pos > x + 20) & (f.pos < x + 420)]
                    if len(g):
                        qs.append(g.speed.sum() / 400 * 3600 / 2)
                out[kmh].append(float(np.mean(qs)) if qs else np.nan)
        m = [float(np.nanmean(out[k])) for k in LC7.KMH]
        book.info('LC7', 'flow per lane ahead of the slow car by speed: ' + ' '.join(f'{k}:{x:.0f}' for k, x in zip(LC7.KMH, m)), 0.0)
        up = m[1:]
        ok = up[-1] >= 1.03 * up[0] and all(b >= 0.98 * a for a, b in zip(up[:-1], up[1:]))
        book.verdict('LC7', 'F065', 'flow past the slow car rises with its speed', 'rises', f'{up[0]:.0f}..{up[-1]:.0f}', '3%', ok, seeds=seedtag('LC7'))


# --- Network
def sig_ring(c, l, n, C, G, y, v, offsets):
    edges = c.ring(l * n / (2 * math.pi), n, v=v)
    for i in range(n):
        c.signal(f'n{i}', [(G, 'G'), (y, 'y'), (C - G - y, 'r')], offsets[i])
    return edges


def sig_ring_measure(run, name, n, t0):
    f = run.cell(name)
    P = sum(run.lane_len(name, f'e{i}_0') for i in range(n))
    # lengths of internal lanes are small but counted by position only; flow from speeds, per Edie
    f = f[f.time >= t0]
    N = f.groupby('time').size().median() if len(f) else 0
    v = f.speed.mean() if len(f) else 0.0
    return dict(k=N / P * 1000, q=N / P * v * 3600, v=v * 3.6, N=N)


@scene('N1', 'net_long')
class N1:
    KS = (10, 20, 30, 40, 48, 60, 80, 100, 120, 130)

    @staticmethod
    def build(w, st):
        for k in N1.KS:
            for r in range(3):
                c = w.cell(f'N1k{k}r{r}', 340)
                rng = arrival_rng(f'N1{k}', r)
                edges = sig_ring(c, 123, 8, 60, 21, 3, 13.4, list(rng.uniform(0, 60, 8)))
                ring_cars(c, round(k * 0.984), 984.0, edges, 200)

    @staticmethod
    def measure(run, book, st):
        rows = []
        for k in N1.KS:
            for r in range(3):
                rows.append(dict(want=k, r=r, **sig_ring_measure(run, f'N1k{k}r{r}', 8, 1200)))
        d = pd.DataFrame(rows)
        g = d.groupby('want').mean(numeric_only=True)
        book.info('N1', 'q(k): ' + ' '.join(f'{a:.0f}:{b:.0f}' for a, b in zip(g.k, g.q)), 0.0)
        book.check('N1', 'F066', 0, d.groupby('r').q.max().values, seeds='N1 3 per density, sim 1')
        top = g.q.max()
        on = g[g.q >= 0.95 * top]
        book.check('N1', 'F067', 0, [on.k.min()], quantity='plateau from (veh/km)', seeds='N1')
        book.check('N1', 'F067', 1, [on.k.max()], quantity='plateau to (veh/km)', seeds='N1')
        high = d[d.want == 130]
        book.check('N1', 'F068', 0, high.q.values, seeds='N1', mode='high', tol='0')


@scene('N2', 'net_long')
class N2:
    KS = (5, 20, 36, 50, 70, 90)

    @staticmethod
    def build(w, st):
        wave = [(i * 24.0) % 90 for i in range(8)]
        anti = [(i * (24.0 + 45)) % 90 for i in range(8)]
        for label, off in (('w', wave), ('a', anti)):
            for k in N2.KS:
                c = w.cell(f'N2{label}k{k}', 800)
                edges = sig_ring(c, 300, 8, 90, 40.5, 3, 12.5, off)
                ring_cars(c, round(k * 2.4), 2400.0, edges, 80)

    @staticmethod
    def measure(run, book, st):
        d = {}
        for label in 'wa':
            d[label] = pd.DataFrame([dict(want=k, **sig_ring_measure(run, f'N2{label}k{k}', 8, 1200)) for k in N2.KS]).set_index('want')
            book.info('N2', f'{label} q(k): ' + ' '.join(f'{a:.0f}:{b:.0f}' for a, b in zip(d[label].k, d[label].q)), 0.0)
        book.check('N2', 'F069', 0, [d['w'].v.loc[5]], quantity='free running, wave', seeds='N2')
        book.check('N2', 'F069', 1, [d['a'].v.loc[5]], quantity='free running, anti-wave', seeds='N2')
        book.check('N2', 'F070', 0, [max(d['w'].q.max(), d['a'].q.max())], seeds='N2')


def n3_cell(w, name, L, inflow, G, r):
    c = w.cell(name, 100)
    c.node('u', 0, 0)
    c.node('a', 400, 0)
    c.node('s', 400 + L, 0, 'traffic_light')
    c.node('b', 400 + L + 300, 0)
    c.edge('up', 'u', 'a')
    c.edge('lk', 'a', 's', lanes=2)
    c.edge('dn', 's', 'b')
    c.conn('up', 'lk', 0, 0)
    c.conn('up', 'lk', 0, 1)
    c.conn('lk', 'dn', 0, 0)
    c.conn('lk', 'dn', 1, 0)
    c.signal('s', [(G, 'G'), (3, 'y'), (90 - G - 3, 'r')])
    for k, t in enumerate(poisson(arrival_rng(name[:3], r), inflow, 0, 2950, 1.5)):
        c.car(f'v{k}', t, ['up', 'lk', 'dn'])


@scene('N3,N3b,N6', 'net_long')
class N3:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            n3_cell(w, f'N3r{r}', 200, 800, 36, r)
            n3_cell(w, f'N3br{r}', 400, 1200, 40.5, r)

    @staticmethod
    def spill(run, name):
        f = run.cell(name)
        k = f[f.lane.astype(str).str.startswith(f'{name}.lk_')]
        n = k.groupby('time').size()
        slow = k[(k.pos < 25) & (k.speed < 2)]
        ts = float(slow.time.min()) if len(slow) else float('nan')
        cars = float(n[(n.index >= ts - 60) & (n.index < ts + 60)].mean()) if np.isfinite(ts) else float(n.max())
        s = k[k.speed < 2].groupby(np.floor(k[k.speed < 2].time / 90)).pos.min()
        s = s[(s.index * 90 > 200) & (s.index * 90 < (ts if np.isfinite(ts) else 2900))]
        tail = -np.polyfit(s.index * 90, s.values, 1)[0] * 3.6 if len(s) > 3 else float('nan')
        return ts, cars, tail

    @staticmethod
    def measure(run, book, st):
        a = [N3.spill(run, f'N3r{r}') for r in range(SEEDS)]
        b = [N3.spill(run, f'N3br{r}') for r in range(SEEDS)]
        book.check('N3', 'F029', 0, [x[1] for x in a], quantity='storage at spill (cars)', seeds=seedtag('N3r'))
        spill_a = [x[0] / 60 if np.isfinite(x[0]) else 50.0 for x in a]
        book.check('N3', 'F029', 1, spill_a, quantity='time to spill (min; 50 = not in 50 min)', seeds=seedtag('N3r'))
        book.check('N3b', 'F071', 0, [x[1] for x in b], quantity='storage at spill (cars)', seeds=seedtag('N3b'), tol='15%')
        book.check('N3b', 'F071', 1, [x[0] / 60 for x in b], quantity='time to spill (min)', seeds=seedtag('N3b'), tol='15%')
        book.check('N3b', 'F071', 2, [x[2] for x in b], quantity='tail speed (km/h)', seeds=seedtag('N3b'), tol='15%')
        # N6: dN/dt = e - P/l on the growing queue
        res = []
        e = run.edges()
        for r in range(SEEDS):
            name = f'N3r{r}'
            t = run.trips(name)
            l = t.route_length.mean()
            cells = e[(e.cell == name) & (e.begin >= 300) & (e.begin < 1500)]
            P = cells.distance.sum()
            arrived_est = P / l
            f = run.cell(name)
            n = f.groupby('time').size()
            dN = float(n[(n.index >= 1490) & (n.index < 1510)].mean() - n[(n.index >= 290) & (n.index < 310)].mean())
            first = f.groupby('trip', observed=True).time.min()
            ent = float(((first >= 300) & (first < 1500)).sum())
            res.append((dN, ent - arrived_est))
        rr = np.array(res)
        book.check('N6', 'F076', 0, rr[:, 1] / np.maximum(rr[:, 0], 1), quantity='predicted dN over measured dN (ratio), 20 min', forecast=1.0, tol='10%', seeds=seedtag('N3r'))


@scene('N4', 'net')
class N4:
    @staticmethod
    def build(w, st):
        for key, qb in (('a', 2400), ('b', 300)):
            for r in range(SEEDS):
                c = w.cell(f'N4{key}{r}', 150)
                c.node('a', 0, 60)
                c.node('b', 0, 0)
                c.node('m', 400, 0, 'zipper')
                c.node('e', 800, 0)
                c.edge('fa', 'a', 'm')
                c.edge('fb', 'b', 'm')
                c.edge('dn', 'm', 'e')
                for k, t in enumerate(uniform(2400, 0, 1150)):
                    c.car(f'a{k}', t, ['fa', 'dn'])
                for k, t in enumerate(uniform(qb, 0, 1150)):
                    c.car(f'b{k}', t, ['fb', 'dn'])

    @staticmethod
    def measure(run, book, st):
        ea, eb, ot = [], [], []
        for r in range(SEEDS):
            t = run.trips(f'N4a{r}')
            win = (t.arrival >= 300) & (t.arrival < 1150)
            a = (t.trip.str.contains(r'\.a') & win).sum() * 3600 / 850
            b = (t.trip.str.contains(r'\.b') & win).sum() * 3600 / 850
            ea.append(a)
            eb.append(b)
            t = run.trips(f'N4b{r}')
            win = (t.arrival >= 300) & (t.arrival < 1150)
            ot.append((t.trip.str.contains(r'\.a') & win).sum() * 3600 / 850)
        share = np.array(ea) / (np.array(ea) + np.array(eb))
        book.check('N4', 'F030', 0, ea, quantity='merge both saturated: arm a (veh/h)', seeds=seedtag('N4'), tol='10%')
        book.check('N4', 'F030', 0, eb, quantity='merge both saturated: arm b (veh/h)', seeds=seedtag('N4'), tol='10%')
        book.check('N4', 'F072', 0, ot, seeds=seedtag('N4b'))


def n5_cell(w, name, closed, beta=0.2, r=0, lanes=1):
    c = w.cell(name, 300)
    c.node('a', 0, 0)
    c.node('m', 300, 0)
    c.node('e', 800, 0)
    c.node('x', 340, -60)
    c.node('y', 500, -60)
    c.node('s', 340, -30, 'traffic_light')
    c.edge('in', 'a', 'm', lanes=lanes)
    c.edge('thr', 'm', 'e', lanes=max(1, lanes - 1))
    c.edge('ex1', 'm', 's')
    c.edge('ex2', 's', 'x')
    c.edge('ex3', 'x', 'y')
    c.signal('s', [(9000, 'r')] if closed else [(15, 'G'), (3, 'y'), (72, 'r')])
    rng = arrival_rng(name[:3], r)
    if lanes == 1:
        for k, t in enumerate(uniform(2400, 0, 1150)):
            c.car(f'v{k}', t, ['in', 'ex1', 'ex2', 'ex3'] if rng.random() < beta else ['in', 'thr'])
    else:
        fs = c.feeders('in', lanes, 'a', 0, 0)
        c.conn('in', 'ex1', 0, 0)
        for li in range(1, lanes):
            c.conn('in', 'thr', li, li - 1)
        for li in range(lanes):
            rt = ['in', 'ex1', 'ex2', 'ex3'] if li == 0 else ['in', 'thr']
            for k, t in enumerate(uniform(2400, 0, 1150)):
                c.car(f'v{li}k{k}', t, [fs[li]] + rt)


@scene('N5', 'net')
class N5:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            n5_cell(w, f'N5a{r}', False, r=r)
            n5_cell(w, f'N5b{r}', True, r=r)
            n5_cell(w, f'N5c{r}', True, r=r, lanes=3)

    @staticmethod
    def measure(run, book, st):
        a, b, c0, c1 = [], [], [], []
        e = run.edges()
        for r in range(SEEDS):
            for name, tgt in ((f'N5a{r}', a), (f'N5b{r}', b)):
                x = e[(e.begin >= 600) & (e.begin < 1150)]
                n = x[x.edge.isin([f'{name}.thr', f'{name}.ex1'])].entered.sum()
                tgt.append(n * 3600 / 550)
            x = e[(e.begin >= 300) & (e.begin < 1150)]
            c1.append(x[x.edge == f'N5c{r}.thr'].entered.sum() * 3600 / 850)
            c0.append(x[(x.edge == f'N5c{r}.ex1') & (x.begin >= 600)].entered.sum() * 3600 / 550)
        book.check('N5', 'F073', 0, a, seeds=seedtag('N5a'))
        book.check('N5', 'F074', 0, b, seeds=seedtag('N5b'), tol='30')
        book.check('N5', 'F075', 0, c1, quantity='3 lanes, other two lanes (veh/h)', seeds=seedtag('N5c'))
        book.check('N5', 'F075', 1, c0, quantity='3 lanes, closed lane (veh/h)', seeds=seedtag('N5c'), tol='30')


N9_CASES = (('z', 'offset 0', 0.0, 40, 1), ('o', 'opposed', 45.0, 40, 1), ('h', 'Hamburg +2 overlap .65', 2.0, 26, 1), ('i', 'Hamburg +2 end +4', 2.0, 42, 1),
            ('w', 'Hamburg, 2 lanes, lane wish', 2.0, 26, 2), ('x', 'opposed, 2 lanes, lane wish', 45.0, 40, 2))
N9_END = 1800
N9_GAP = {1: 20.0, 2: 20.0}
N9_FEED = dict(z=1000, o=180, h=650, i=1000, w=650, x=360)


@scene('N9', 'n9')
class N9:
    @staticmethod
    def build(w, st):
        for label, _, off, g2, lanes in N9_CASES:
            for r in range(SEEDS):
                c = w.cell(f'N9{label}{r}', 300)
                c.node('a', 0, 0)
                c.node('s', 800, 0, 'traffic_light')
                c.node('t', 800 + N9_GAP[lanes], 0, 'traffic_light')
                c.node('b', 1124, 0)
                c.edge('up', 'a', 's', lanes=lanes)
                c.edge('lk', 's', 't', lanes=lanes)
                c.edge('dn', 't', 'b')
                c.signal('s', [(40, 'G'), (3, 'y'), (47, 'r')], 0.0)
                c.signal('t', [(g2, 'G'), (3, 'y'), (90 - g2 - 3, 'r')], off)
                if lanes == 1:
                    for k, t in enumerate(uniform(N9_FEED[label], 0, N9_END)):
                        c.car(f'v{k}', t, ['up', 'lk', 'dn'])
                else:
                    c.node('e', 1124, -100)
                    c.edge('rt', 't', 'e')
                    fs = c.feeders('up', 2, 'a', 0, 0)
                    c.conn('up', 'lk', 0, 0)
                    c.conn('up', 'lk', 1, 1)
                    c.conn('lk', 'rt', 0, 0)
                    c.conn('lk', 'dn', 1, 0)
                    rng = arrival_rng(f'N9{label}', r)
                    for li in range(2):
                        for k, t in enumerate(uniform(N9_FEED[label] / 2, 0, N9_END)):
                            c.car(f'v{li}k{k}', t, [fs[li], 'up', 'lk', 'rt' if rng.random() < 0.5 else 'dn'])

    @staticmethod
    def measure(run, book, st):
        for label, text, off, g2, lanes in N9_CASES:
            out, L, trend, holds, left, why = [], [], [], [], [], []
            for r in range(SEEDS):
                name = f'N9{label}{r}'
                x = run.trips(name)
                a = x.arrival.to_numpy()
                n = ((a >= 400) & (a < N9_END)).sum() / ((N9_END - 400) / 90)
                out.append(n)
                early = ((a >= 400) & (a < 850)).sum() / 5
                late = ((a >= N9_END - 450) & (a < N9_END)).sum() / 5
                trend.append(late / max(early, 0.1))
                L.append(run.lane_len(name, 'lk_0'))
                f = run.cell(name).sort_values(['trip', 'time'], kind='stable')
                holds.append(longest_stand(f, on=('.lk_', '.up_')))
                left.append(len(f[f.time >= 2890]))
            q = [f"{np.mean(out):.1f}"]
            if lanes == 1:
                fid, i = {'z': ('F047', 0), 'o': ('F047', 1), 'h': ('F091', 0), 'i': ('F092', 0)}[label]
                book.check('N9', fid, i, out, quantity=f'{text}: cars per cycle', seeds=seedtag('N9'))
            else:
                book.check('N9', 'F095', 0, out, quantity=f'{text}: cars per cycle', seeds=seedtag(f'N9{label}'), mode='low', tol='0')
            book.check('N9', 'F093', 0, holds, quantity=f'{text}: longest stand on link or approach (s)', seeds=seedtag('N9'), mode='high', tol='0')
            book.check('N9', 'F094', 0, left, quantity=f'{text}: cars left {2890 - N9_END} s after the feed ends', seeds=seedtag('N9'), tol='0')
            book.info('N9', f'{text}: flow late over early (1 = no decay); link lane (m)', f'{np.mean(trend):.2f}; {np.mean(L):.1f}')


def longest_stand(f, on=None):
    """Longest time one car stands still without a break, on lanes whose id holds one of the given strings."""
    g = f
    if on:
        lanes = f.lane.astype(str)
        m = np.zeros(len(f), bool)
        for o in on:
            m |= lanes.str.contains(o, regex=False).to_numpy()
        g = f[m]
    tr = g.trip.cat.codes.to_numpy()
    ti = g.time.to_numpy()
    st_ = g.speed.to_numpy() < 0.1
    best, cur, start = 0.0, -1, 0.0
    for j in range(len(g)):
        if st_[j]:
            if tr[j] != cur:
                cur, start = tr[j], ti[j]
            best = max(best, ti[j] - start)
        else:
            cur = -1
    return float(best)


@scene('N10', 'n10')
class N10:
    @staticmethod
    def build(w, st):
        def state(green_arms, ch):
            def f(links):
                out = ''
                for a, b, d in links:
                    arm = a[1:]
                    if arm in green_arms:
                        out += ch if d not in ('l', 'L', 't') or ch != 'G' else 'g'
                    else:
                        out += 'r'
                return out
            return f
        for key, qopp, both in (('a', 2400, False), ('b', 900, False), ('c', 900, True), ('d', 2400, True)):
            for r in range(SEEDS):
                c = cross(w, f'N10{key}{r}', jtype='traffic_light', major=())
                c.signal('c', [(40, state(('n', 's'), 'G')), (3, state(('n', 's'), 'y')), (40, state(('e', 'w'), 'G')), (3, state(('e', 'w'), 'y'))])
                rng = arrival_rng(f'N10{key}', r)
                for k, t in enumerate(poisson(rng, 180, 0, 2900)):
                    c.car(f'l{k}', t, ['in', 'oe'])
                for k, t in enumerate(poisson(rng, qopp, 0, 2900, 1.0)):
                    if both and rng.random() < 0.15:
                        c.car(f'k{k}', t, ['is', 'ow'])
                    else:
                        c.car(f'o{k}', t, ['is', 'on'])

    @staticmethod
    def measure(run, book, st):
        for key in 'abcd':
            worst, per, ints = [], [], []
            for r in range(SEEDS):
                name = f'N10{key}{r}'
                f = run.cell(name).sort_values(['trip', 'time'], kind='stable')
                worst.append(longest_stand(f))
                x = run.trips(name)
                l = x[x.trip.str.contains(r'\.l')]
                per.append(((l.arrival >= 300) & (l.arrival < 2900)).sum() / (2600 / 86))
                il = f[f.lane.astype(str).str.startswith(':') & (f.speed < 0.1)]
                ints.append(il.groupby('trip', observed=True).size().max() * run.a.fcd if len(il) else 0.0)
            book.check('N10', 'F049', 0, worst, quantity=f'{key}: longest standing still (s), limit 5 min', forecast=300.0, tol='0', mode='high', seeds=seedtag(f'N10{key}'))
            book.info('N10', f'{key}: longest on an internal lane (s)', float(np.max(ints)))
            if key == 'a':
                book.check('N10', 'F087', 0, per, seeds=seedtag('N10a'), mode='low', tol='0')


# --- C's scenes
def hole_ring(w, name, N, P, repeat):
    c = w.cell(name, 340)
    edges = c.ring(P / (2 * math.pi), 4)
    for i in range(4):
        c.signal(f'n{i}', [(25, 'r'), (9000, 'G')])
    ring_cars(c, N, P, edges, repeat)
    return c


# (N, perimeter): one hole, as C's 39 of 300 but evenly placed per edge; full; full with a whisker of slack,
# since insertion refuses exact spacing by float rounding
S2_NS = ((36, 277.5), (40, 300.0), (40, 301.0), (40, 303.0))


def s2_flow(run, name):
    f = run.cell(name)
    g = f[(f.time >= 300)]
    n = g.groupby('time').size().median() if len(g) else 0
    P = sum(run.lane_len(name, f'e{i}_0') for i in range(4))
    return float(g.speed.mean() * n / P * 3600) if len(g) else 0.0, float(n), P


def s2_all(run, st, tag):
    res = {}
    for N, P in S2_NS:
        res[(N, P)] = [s2_flow(run, f'S2{tag}n{N}p{int(P)}r{r}') for r in range(SEEDS)]
    return res


def s2_build(w, st, tag):
    for N, P in S2_NS:
        for r in range(SEEDS):
            hole_ring(w, f'S2{tag}n{N}p{int(P)}r{r}', N, P, 60)


@scene('C-S2', 'sringon')
class S2On:
    @staticmethod
    def build(w, st):
        s2_build(w, st, 'on')

    @staticmethod
    def measure(run, book, st):
        res = s2_all(run, st, 'on')
        book.info('C-S2', 'N,P: in ring, flow ' + ' '.join(f'{k[0]},{k[1]:.0f}:{np.mean([x[1] for x in v]):.1f},{np.mean([x[0] for x in v]):.0f}' for k, v in res.items()), 0.0)
        T = st.get('T', 1.3)
        s_ = st.get('s', 7.5)
        hole = [x[0] for x in res[(36, 277.5)]]
        book.check('C-S2', 'F032', 0, hole, quantity='one hole, N 36 of 277.5 m: flow against w/perimeter', forecast=(s_ / T) / 277.5 * 3600, tol='20%', seeds=seedtag('C-S2'))
        for key in ((40, 300.0), (40, 301.0)):
            v = res[key]
            if np.mean([x[1] for x in v]) >= 39.5:
                book.check('C-S2', 'F032', 0, [x[0] for x in v], quantity=f'N 40 of {key[1]:.0f} m flow', forecast=0.0, tol=f'{(key[1] - 300 + .01) / T * 40 / key[1] * 3600 * 1.5:.0f}', seeds=seedtag('C-S2'))
            else:
                book.verdict('C-S2', 'F032', f'N 40 of {key[1]:.0f} m', '40 in', f'{np.mean([x[1] for x in v]):.1f} in', 'exact', False, seeds='insertion refuses it')


@scene('C-S2off', 'sringoff')
class S2Off:
    @staticmethod
    def build(w, st):
        s2_build(w, st, 'of')

    @staticmethod
    def measure(run, book, st):
        res = s2_all(run, st, 'of')
        v = res[(40, 301.0)]
        book.check('C-S2', 'F079', 0, [x[0] for x in v], quantity='N 40 of 301 m, exit clear off', tol='30', seeds=seedtag('C-S2'))


def s3_cell(w, name, f_share, lanes=2, r=0, key='S3'):
    """Lane 0 turns off gently, the others go through. A share of lane 0 wants through.
    lanes 2 (S3): a line no one may cross stands in for C's 'no gaps', so the head can only wait or give up.
    lanes 3 (S4): through lanes stand in a queue behind a short green, so a head needing two changes is held back."""
    c = w.cell(name, 300)
    c.node('a', 0, 0)
    c.node('m', 300, 0)
    c.node('t', 600, 0, 'traffic_light' if lanes == 3 else 'priority')
    c.node('z', 1000, 0)
    c.node('r', 600, -80)
    c.node('q', 800, -80)
    c.edge('in', 'a', 'm', lanes=lanes, lane_change={0: 'authority'} if lanes == 2 else None)
    c.edge('thr', 'm', 't', lanes=lanes - 1)
    c.edge('rt', 'm', 'r')
    c.edge('r2', 'r', 'q')
    c.edge('r3', 'q', 'z')
    c.node('y', 1400, 0)
    c.edge('end', 't', 'z', lanes=lanes - 1)
    c.edge('fin', 'z', 'y')
    c.conn('in', 'rt', 0, 0)
    for li in range(1, lanes):
        c.conn('in', 'thr', li, li - 1)
    if lanes == 3:
        c.signal('t', [(12, 'G'), (3, 'y'), (75, 'r')])
    fs = c.feeders('in', lanes, 'a', 0, 0)
    rng = arrival_rng(f'{key}{f_share}', r)
    through = ['in', 'thr', 'end', 'fin']
    for li in range(1, lanes):
        for k, t in enumerate(uniform(2400, 0, 1450)):
            c.car(f't{li}k{k}', t, [fs[li]] + through)
    for k, t in enumerate(uniform(2400, 0, 1450)):
        c.car(f'c{k}', t, [fs[0]] + (through if rng.random() < f_share else ['in', 'rt', 'r2', 'r3', 'fin']))


def s3_flow(run, name):
    """Everything leaving lane 0: its own turn, and those who gave up theirs."""
    e = run.edges()
    x = e[(e.begin >= 300) & (e.begin < 1450)]
    return x[x.edge == f'{name}.rt'].entered.sum() * 3600 / 1150


def s3_measure(run, book, fid, batch_vals, prefix, lanes=2):
    for i, (label, share, r_idx) in enumerate(batch_vals):
        vals = [s3_flow(run, f'{prefix}{label}{r}') for r in range(SEEDS)]
        book.check(prefix, fid, r_idx, vals, quantity=f'flow lane 0 {label}', seeds=seedtag(prefix))


@scene('C-S3,C-S4', 'miss60')
class S3a:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            s3_cell(w, f'CS3f00r{r}', 0.0, r=r)
            s3_cell(w, f'CS3f05r{r}', 0.05, r=r)
            s3_cell(w, f'CS3f10r{r}', 0.1, r=r)
            s3_cell(w, f'CS4f05r{r}', 0.05, lanes=3, r=r, key='S4')
            s3_cell(w, f'CS4f10r{r}', 0.1, lanes=3, r=r, key='S4')

    @staticmethod
    def measure(run, book, st):
        book.info('C-S3', 'lane 0 flow with no wrong-lane car, formula 1800', float(np.mean([s3_flow(run, f'CS3f00r{r}') for r in range(SEEDS)])))
        for pre, scene_name, fid in (('CS3', 'C-S3', 'F033'), ('CS4', 'C-S4', 'F034')):
            for i, lab in enumerate(('f05', 'f10')):
                vals = [s3_flow(run, f'{pre}{lab}r{r}') for r in range(SEEDS)]
                book.check(scene_name, fid, i, vals, quantity=f'lane 0 flow, f .{lab[1:]} patience 60', seeds=seedtag(scene_name))
        book.info('C-S4', 'missed turns asked, rerouted, no way', str({k: run.rep.get('missed_turns', {}).get(k) for k in ('asked', 'rerouted', 'no_way')}))


@scene('C-S3c', 'miss120')
class S3b:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            s3_cell(w, f'CS3f10r{r}', 0.1, r=r)
            s3_cell(w, f'CS4f10r{r}', 0.1, lanes=3, r=r, key='S4')

    @staticmethod
    def measure(run, book, st):
        book.check('C-S3', 'F033', 2, [s3_flow(run, f'CS3f10r{r}') for r in range(SEEDS)], quantity='lane 0 flow, f .10 patience 120', seeds=seedtag('C-S3'))
        book.check('C-S4', 'F034', 2, [s3_flow(run, f'CS4f10r{r}') for r in range(SEEDS)], quantity='lane 0 flow, f .10 patience 120', seeds=seedtag('C-S4'))


@scene('C-S3n', 'miss0')
class S3c:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            s3_cell(w, f'CS3f10r{r}', 0.1, r=r)
            s3_cell(w, f'CS4f10r{r}', 0.1, lanes=3, r=r, key='S4')

    @staticmethod
    def measure(run, book, st):
        book.check('C-S3', 'F033', 3, [s3_flow(run, f'CS3f10r{r}') for r in range(SEEDS)], quantity='lane 0 flow, f .10 never', seeds=seedtag('C-S3'), tol='30')
        book.check('C-S4', 'F034', 3, [s3_flow(run, f'CS4f10r{r}') for r in range(SEEDS)], quantity='lane 0 flow, f .10 never', seeds=seedtag('C-S4'), tol='30')


@scene('C-S4b,C-S6', 'drop_city')
class Drop:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            c = w.cell(f'CS6r{r}', 150)
            c.node('a', 0, 0)
            c.node('m', 500, 0)
            c.node('b', 900, 0)
            c.edge('up', 'a', 'm', lanes=2)
            c.edge('dn', 'm', 'b')
            c.conn('up', 'dn', 1, 0)
            fs = c.feeders('up', 2, 'a', 0, 0)
            for li, key in ((0, 'c'), (1, 't')):
                for k, t in enumerate(uniform(1300, 0, 1450)):
                    c.car(f'{key}{k}', t, [fs[li], 'up', 'dn'])

    @staticmethod
    def measure(run, book, st):
        tot, shr, w_ = [], [], []
        for r in range(SEEDS):
            name = f'CS6r{r}'
            t = run.trips(name)
            win = (t.arrival >= 300) & (t.arrival < 1450)
            a = (t.trip.str.contains(r'\.c') & win).sum()
            b = (t.trip.str.contains(r'\.t') & win).sum()
            tot.append((a + b) * 3600 / 1150)
            shr.append(a / max(a + b, 1))
            f = run.cell(name)
            L = run.lane_len(name, 'up_0')
            z = f[(f.lane == f'{name}.up_0') & (f.pos > L - 100)]
            w_ += list(z.groupby('trip', observed=True).time.agg(lambda s: s.max() - s.min()).values)
        tag = seedtag('C-S6')
        book.check('C-S6', 'F036', 0, tot, quantity='lane drop 1300+1300 total (veh/h)', seeds=tag, tol='10%')
        book.check('C-S6', 'F036', 0, shr, quantity='share of the closing lane', forecast=0.5, tol='.1', seeds=tag)
        mx = float(np.max(w_)) if w_ else float('nan')
        book.check('C-S6', 'F036', 0, [mx], quantity='longest wait last 100 m (s)', forecast=80.0, tol='0', mode='high', seeds=tag)
        book.verdict('C-S4b', 'F035', 'give-ups at a real lane drop', '0', str(run.rep.get('missed_turns', {}).get('asked', 'n/a')), 'exact', run.rep.get('missed_turns', {}).get('asked', 0) == 0, seeds=tag)


@scene('C-S5', 'net')
class Abreast:
    @staticmethod
    def build(w, st):
        for off in (7, 12):
            for r in range(SEEDS):
                c = w.cell(f'CS5o{off}r{r}', 150)
                c.node('a', 0, 0)
                c.node('m', 300, 0)
                c.node('t', 700, 0)
                c.node('r', 300, -200)
                c.edge('in', 'a', 'm', lanes=2)
                c.edge('thr', 'm', 't')
                c.edge('rt', 'm', 'r')
                c.conn('in', 'rt', 0, 0)
                c.conn('in', 'thr', 1, 0)
                # the two heads swap: lane 0 wants through, lane 1 wants right; each has a queue behind
                c.car('h0', 0.0, ['in', 'thr'], lane=0, pos=285.0, speed='0')
                c.car('h1', 0.0, ['in', 'rt'], lane=1, pos=285.0 - off, speed='0')
                for k in range(15):
                    c.car(f'q0k{k}', 0.5 + k * 0.5, ['in', 'rt'], lane=0, pos=285.0 - 9 * (k + 1), speed='0')
                    c.car(f'q1k{k}', 0.5 + k * 0.5, ['in', 'thr'], lane=1, pos=285.0 - off - 9 * (k + 1), speed='0')

    @staticmethod
    def measure(run, book, st):
        out = []
        for off in (7, 12):
            for r in range(SEEDS):
                name = f'CS5o{off}r{r}'
                f = run.cell(name)
                worst = 0.0
                for h, lane in (('h0', 'in_1'), ('h1', 'in_0')):
                    g = f[(f.trip == f'{name}.{h}') & (f.lane == f'{name}.{lane}')]
                    worst = max(worst, g.time.min() if len(g) else 1e4)
                out.append(worst)
        book.check('C-S5', 'F080', 0, [max(out)], quantity='both heads swapped by (s), worst of 10', tol='0', mode='high', seeds=seedtag('C-S5', 10))
        book.info('C-S5', 'median swap time (s), I-80 median 22.6', float(np.median(out)))


@scene('C-S7', 'give2')
class Yield:
    QS = (1200, 1800, 2400)

    @staticmethod
    def build(w, st):
        for q in Yield.QS:
            for r in range(SEEDS):
                t_junction(w, f'CS7q{q}r{r}', q, f'CS7{q}', r=r, through=True, major_lanes=2, minor_end=1500)

    @staticmethod
    def measure(run, book, st):
        for i, q in enumerate(Yield.QS):
            caps, waits = [], []
            for r in range(SEEDS):
                name = f'CS7q{q}r{r}'
                t = run.trips(name)
                t = t[t.trip.str.contains(r'\.s')]
                a = np.sort(t.arrival.values)
                caps.append(((a >= 300) & (a < 1500)).sum() * 3)
                waits += list(np.diff(a[a >= 300]))
            book.check('C-S7', 'F081', i, caps, quantity=f'minor through, major {q} (arrival count)', seeds=seedtag(f'CS7{q}'))
            w_ = np.array(waits) if waits else np.array([np.nan])
            book.check('C-S7', 'F082', 0, [w_.max()], quantity=f'longest head wait, major {q} (s)', tol='0', mode='high', seeds=seedtag(f'CS7{q}'))
            if q == 1800:
                p = float((w_ > 120).mean()) * 100
                book.info('C-S7', f'P(head wait>120 s) at 1800, %: table fixed 4.3, falling 0.6 (n={len(w_)})', p)


def s8_cell(w, name, lanes, r):
    """Cross street north-south, main road east-west with a hold 25 m past the junction."""
    c = w.cell(name, 800)
    c.node('c', 300, 200, 'traffic_light')
    c.node('w', 0, 200)
    c.node('h', 325, 200, 'traffic_light')
    c.node('e', 625, 200)
    c.node('s', 300, 0)
    c.node('n', 300, 400)
    c.edge('wc', 'w', 'c', prio=2)
    c.edge('ch', 'c', 'h', prio=2)
    c.edge('he', 'h', 'e', prio=2)
    c.edge('sc', 's', 'c', lanes=lanes, prio=2)
    c.edge('cn', 'c', 'n', lanes=lanes, prio=2)

    def st(mainc, crossc):
        return lambda links: ''.join(mainc if a == 'wc' else crossc for a, b, d in links)
    # main green first, cross green 30 s effective: G 30 y 3; main G 24 y 3. Hold releases 10 s into the cross green.
    c.signal('c', [(24, st('G', 'r')), (3, st('y', 'r')), (30, st('r', 'G')), (3, st('r', 'y'))])
    c.signal('h', [(27 + 10, 'r'), (23, 'G')])
    for k, t in enumerate(uniform(1200, 0, 1450)):
        c.car(f'm{k}', t, ['wc', 'ch', 'he'])
    if lanes == 1:
        for k, t in enumerate(uniform(1200, 0, 1450)):
            c.car(f'x{k}', t, ['sc', 'cn'])
    else:
        c.w.nodes.append(f'<node id="{c.id("s0")}" x="280.00" y="{c.y0 - 250:.2f}" type="priority"/>')
        c.w.nodes.append(f'<node id="{c.id("s1")}" x="320.00" y="{c.y0 - 250:.2f}" type="priority"/>')
        c.edge('sf0', 's0', 's')
        c.edge('sf1', 's1', 's')
        c.conn('sf0', 'sc', 0, 0)
        c.conn('sf1', 'sc', 0, 1)
        for li in range(2):
            for k, t in enumerate(uniform(1200, 0, 1450)):
                c.car(f'x{li}k{k}', t, [f'sf{li}', 'sc', 'cn'])


class Block:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            s8_cell(w, f'CS8a{r}', 1, r)

    @staticmethod
    def flow(run, name, lanes):
        e = run.edges()
        x = e[(e.begin >= 300) & (e.begin < 1440) & (e.edge == f'{name}.cn')]
        return x.entered.sum() * 3600 / 1140 / lanes


def block_scene(batch_name, idx, label):
    @scene(f'C-S8{label}', batch_name)
    class B(Block):
        @staticmethod
        def build(w, st):
            for r in range(SEEDS):
                s8_cell(w, f'CS8{label}{r}', 1, r)
                if idx == 1:
                    s8_cell(w, f'CS8T{r}', 2, r)

        @staticmethod
        def measure(run, book, st):
            book.check('C-S8', 'F083', idx, [Block.flow(run, f'CS8{label}{r}', 1) for r in range(SEEDS)], quantity=f"cross capacity b {['0', '.75', '1'][idx]} (exit_comply 1-b)", seeds=seedtag('C-S8'))
            if idx == 1:
                book.check('C-S8', 'F083', 3, [Block.flow(run, f'CS8T{r}', 2) for r in range(SEEDS)], quantity='two lanes b .75, per lane', seeds=seedtag('C-S8'))
    return B


block_scene('block1', 0, 'b0')
block_scene('block25', 1, 'b75')
block_scene('block0', 2, 'b1')


@scene('C-S9', 'lane')
class Spill:
    @staticmethod
    def build(w, st):
        for r in range(SEEDS):
            c = w.cell(f'CS9r{r}', 50)
            c.node('a', 0, 0)
            c.node('m', 300, 0)
            c.node('s', 397 + 3, 0, 'traffic_light')
            c.node('b', 700, 0)
            c.edge('up', 'a', 'm')
            c.edge('ed', 'm', 's')
            c.edge('out', 's', 'b')
            c.signal('s', [(9000, 'r')])
            for k, t in enumerate(uniform(600, 0, 700)):
                c.car(f'v{k}', t, ['up', 'ed', 'out'])

    @staticmethod
    def measure(run, book, st):
        out, L = [], []
        for r in range(SEEDS):
            name = f'CS9r{r}'
            f = run.cell(name)
            lane = f'{name}.ed_0'
            s = f[(f.lane == lane) & (f.speed < 0.5)]
            first = s.time.min()
            reach = s[s.pos < 8.0].time.min()
            out.append(reach - first)
            L.append(run.lane_len(name, 'ed_0'))
        book.check('C-S9', 'F038', 0, out, seeds=seedtag('C-S9'))
        book.info('C-S9', 'edge lane length (m), forecast 97', float(np.mean(L)))


# Closed grid: planar, so the 2D detector sees no overlapping edges. Rows and columns pair into ovals at the border.
def grid_cell(w, name, n, l, jtype, r, k_share, pt, kj=133.0, tls=False):
    c = w.cell(name, n * l + 500)
    # node i,j; even rows east, odd rows west; even columns north, odd columns south
    for i in range(n):
        for j in range(n):
            c.node(f'x{i}_{j}', 200 + j * l, 200 + i * l, 'traffic_light' if tls else jtype)
    nxt = {}
    edges = []

    def add(e, a, b, prio=1, shape=None):
        c.edge(e, a, b, prio=prio, shape=shape)
        edges.append(e)
        nxt.setdefault(a, []).append((e, b))
    for i in range(n):
        east = i % 2 == 0
        for j in range(n - 1):
            a, b = (f'x{i}_{j}', f'x{i}_{j + 1}') if east else (f'x{i}_{j + 1}', f'x{i}_{j}')
            add(f'r{i}_{j}', a, b, prio=2)
    for j in range(n):
        north = j % 2 == 0
        for i in range(n - 1):
            a, b = (f'x{i}_{j}', f'x{i + 1}_{j}') if north else (f'x{i + 1}_{j}', f'x{i}_{j}')
            add(f'c{i}_{j}', a, b, prio=2)
    # border links close the ovals: pair rows 0-1, 2-3, ... at both ends, and columns likewise, on their own side nodes
    for i in range(0, n, 2):
        add(f'E{i}', f'x{i}_{n - 1}', f'x{i + 1}_{n - 1}', shape=[(200 + (n - 1) * l, 200 + i * l), (200 + (n - 1) * l + 45, 200 + i * l), (200 + (n - 1) * l + 45, 200 + (i + 1) * l), (200 + (n - 1) * l, 200 + (i + 1) * l)])
        add(f'W{i}', f'x{i + 1}_0', f'x{i}_0', shape=[(200, 200 + (i + 1) * l), (155, 200 + (i + 1) * l), (155, 200 + i * l), (200, 200 + i * l)])
    for j in range(0, n, 2):
        add(f'N{j}', f'x{n - 1}_{j}', f'x{n - 1}_{j + 1}', shape=[(200 + j * l, 200 + (n - 1) * l), (200 + j * l, 200 + (n - 1) * l + 45), (200 + (j + 1) * l, 200 + (n - 1) * l + 45), (200 + (j + 1) * l, 200 + (n - 1) * l)])
        add(f'S{j}', f'x0_{j + 1}', f'x0_{j}', shape=[(200 + (j + 1) * l, 200), (200 + (j + 1) * l, 155), (200 + j * l, 155), (200 + j * l, 200)])
    if tls:
        for i in range(n):
            for j in range(n):
                def st(row):
                    return lambda links: ''.join(('G' if (a[0] in 'rEW') == row else 'r') for a, b, d in links)
                def yl(row):
                    return lambda links: ''.join(('y' if (a[0] in 'rEW') == row else 'r') for a, b, d in links)
                c.signal(f'x{i}_{j}', [(27, st(True)), (3, yl(True)), (27, st(False)), (3, yl(False))])
    to = {e: [] for e in edges}
    head = {}
    for a, lst in nxt.items():
        for e, b in lst:
            head[e] = b
    for e in edges:
        to[e] = [x[0] for x in nxt.get(head[e], [])]
    rng = arrival_rng(name, r)
    total_m = len(edges) * l
    N = round(k_share * kj * total_m / 1000)
    per = max(1, int(l // 7.8))
    slots = [(e, s) for e in edges for s in range(per)]
    chosen = rng.choice(len(slots), size=min(N, len(slots)), replace=False)
    chosen = sorted(chosen, key=lambda x: (slots[x][0], -slots[x][1]))
    legs = int(1.3 * 13.89 * w_end_hint(w) / l) + 8
    for v, idx in enumerate(chosen):
        e, s = slots[idx]
        route = [e]
        for _ in range(min(legs, 400)):
            opts = to[route[-1]]
            if len(opts) == 1:
                route.append(opts[0])
                continue
            kind = route[-1][0]
            same = [x for x in opts if (x[0] in 'rEW') == (kind in 'rEW')]
            other = [x for x in opts if x not in same]
            if same and other:
                route.append(other[0] if rng.random() < pt else same[0])
            else:
                route.append(opts[int(rng.integers(len(opts)))])
        c.car(f'v{v}', 0.0, route, pos=max(l - 12 - s * 7.8, 3.0), speed='0')
    st_ = dict(N=N, m=total_m)
    return st_


def w_end_hint(w):
    return getattr(w, 'end_hint', 7200)


class Grid:
    SHARES = (0.1, 0.2, 0.25, 0.3, 0.4)
    PTS = (0.1, 0.5)
    N = 6
    L = 100.0

    @staticmethod
    def build_common(w, st, tls, label):
        for s in Grid.SHARES:
            for pt in Grid.PTS:
                for r in range(3):
                    grid_cell(w, f'{label}s{int(s * 100)}t{int(pt * 10)}r{r}', Grid.N, Grid.L, 'right_before_left' if label == 'GU' else 'priority', r, s, pt, tls=tls)

    @staticmethod
    def measure_common(run, book, st, label):
        e = run.edges()
        hdr = f"{'signals 60 s' if label == 'GS' else 'priority'}"
        lock = {}
        for s in Grid.SHARES:
            for pt in Grid.PTS:
                for r in range(3):
                    name = f'{label}s{int(s * 100)}t{int(pt * 10)}r{r}'
                    x = e[e.cell == name].groupby('begin').distance.sum()
                    dead = x[x < 1.0]
                    lock.setdefault(s, []).append(dead.index.min() / 3600 if len(dead) else np.inf)
        end = e.begin.max() / 3600
        for s in Grid.SHARES:
            v = np.array(lock[s])
            finite = v[np.isfinite(v)]
            med = float(np.median(v)) if len(finite) > len(v) / 2 else float('inf')
            txt = f'{(~np.isfinite(v)).sum()}/{len(v)} free in {end:.1f} h; locks at ' + (' '.join(f'{x:.2f}' for x in np.sort(finite)[:5]) if len(finite) else 'none')
            if s < 0.25:
                book.verdict('C-S0', 'F031', f'{hdr} k .{int(s * 100)} kj', 'no lock', txt, 'explain', len(finite) == 0, seeds=f'{label} 3 per (k,P_T), sim 1')
            elif s == 0.25:
                book.info('C-S0', f'{hdr} k .25 kj: theirs hours', txt)
            else:
                book.verdict('C-S0', 'F078', f'{hdr} k .{int(s * 100)} kj: lock under 1 h', '< 1 h', txt, 'explain', len(finite) == len(v) and finite.max() <= 1.0, seeds=f'{label} 3 per (k,P_T), sim 1')


@scene('C-S0,N7', 'grid')
class Grid1:
    @staticmethod
    def build(w, st):
        Grid.build_common(w, st, False, 'GU')

    @staticmethod
    def measure(run, book, st):
        Grid.measure_common(run, book, st, 'GU')


@scene('C-S0s', 'grid_sig')
class Grid2:
    @staticmethod
    def build(w, st):
        Grid.build_common(w, st, True, 'GS')

    @staticmethod
    def measure(run, book, st):
        Grid.measure_common(run, book, st, 'GS')


# ---------------------------------------------------------------- run
def run_batch(name, scenes, a, book, st, out):
    cfg = BATCH_CFG[name]
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    w = World()
    w.end_hint = cfg['end']
    for s in scenes:
        s.build(w, st)
    (d / 'n.nod.xml').write_text('<nodes>' + ''.join(w.nodes) + '</nodes>')
    (d / 'e.edg.xml').write_text('<edges>' + ''.join(w.edges) + '</edges>')
    (d / 'c.con.xml').write_text('<connections>' + ''.join(w.conns) + '</connections>')
    cmd = ['netconvert', '-n', d / 'n.nod.xml', '-e', d / 'e.edg.xml', '-x', d / 'c.con.xml', '-o', d / 'net.xml', '--no-turnarounds', '--junctions.corner-detail', '5', '--offset.disable-normalization', 'true', '--no-left-connections', 'false', '--geometry.remove', 'false']
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    rewrite_tls(d / 'net.xml', w)
    types = ''.join(f'<vType id="{k}" vClass="passenger" {v}/>' if 'vClass' not in v else f'<vType id="{k}" {v}/>' for k, v in w.types.items())
    w.veh.sort(key=lambda x: x[0])
    (d / 'r.xml').write_text('<routes>' + types + ''.join(v for _, v in w.veh) + '</routes>')
    capacity = max(2000, 2 * len(w.veh))
    args = [a.cars, 'run', '--net', d / 'net.xml', '--routes', d / 'r.xml', '--dt', a.dt, '--begin', 0, '--end', cfg['end'], '--time-to-teleport', 0, '--seed', SIM_SEED,
            '--capacity', capacity, '--trip-csv', d / 'trips.csv', '--edge-csv', d / 'edges.csv', '--edge-interval', 60, '--summary-csv', d / 'summary.csv', '--report-json', d / 'rep.json', '--static-tls']
    fcd = cfg.get('fcd', 0)
    if fcd:
        fcd = max(fcd, a.dt)
        args += ['--fcd', d / 'fcd.csv', '--fcd-interval', fcd]
    for t in cfg.get('tune', []):
        args += ['--tune', t]
    args += shlex.split(a.flags)
    t0 = time.time()
    r = subprocess.run(list(map(str, args)), capture_output=True, text=True, env=ENV, timeout=a.timeout)
    (d / 'log.txt').write_text(r.stdout + r.stderr)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    wall = time.time() - t0
    run = Run(d, a)
    a.fcd = fcd
    try:
        import json
        run.rep = json.loads((d / 'rep.json').read_text())
    except Exception:
        run.rep = {}
    s = pd.read_csv(d / 'summary.csv')
    # Counter readbacks lag each other by a few steps, so single rows differ; a lost car shows as a mean that stays off.
    lost = round(float((s.inserted - s.arrived - s.running).iloc[len(s) // 2:].mean()), 1) if len(s) else 0
    print(f'# batch {name}: {len(w.veh)} trips, {len(w.edges)} edges, wall {wall:.0f} s, contacts {run.rep.get("collision_incidents")}, conservation worst {lost}', flush=True)
    book.verdict('L7', 'F007', f'{name}: inserted-arrived-running, contacts {run.rep.get("collision_incidents")}', 'exact', str(lost), '1', abs(lost) <= 1, seeds=f'sim {SIM_SEED}')
    for sc in scenes:
        try:
            sc.measure(run, book, st)
        except Exception as e:
            import traceback
            book.row(','.join(sc.names), '', f'scene error: {e!r}'[:120], '', '', '', 'ERROR')
            traceback.print_exc()
    if fcd and not a.keep:
        (d / 'fcd.csv').unlink(missing_ok=True)


ORDER = ['signal', 'lane', 'ring', 'sringon', 'sringoff', 'signal_long', 'xone', 'give', 'give2', 'lc', 'lc2', 'drop', 'drop_city', 'slow', 'net', 'net_long', 'n9', 'n10', 'miss60', 'miss120', 'miss0', 'block1', 'block25', 'block0', 'grid', 'grid_sig']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--driver', choices=['physical', 'human'], required=True)
    p.add_argument('--dt', type=float, default=1.0)
    p.add_argument('--only', default='')
    p.add_argument('--skip', default='')
    p.add_argument('--cars', default='')
    p.add_argument('--flags', default=None)
    p.add_argument('--out', default='')
    p.add_argument('--tag', default='')
    p.add_argument('--timeout', type=int, default=3000)
    p.add_argument('--keep', action='store_true', help='keep trajectories')
    a = p.parse_args()
    a.cars = a.cars or str(BINS[a.driver])
    a.flags = FLAGS[a.driver] if a.flags is None else a.flags
    tag = f'{a.driver}_{a.dt:g}' + (f'_{a.tag}' if a.tag else '')
    out = Path(a.out or f'/tmp/theory-scenes/{tag}')
    out.mkdir(parents=True, exist_ok=True)
    only = set(x for x in a.only.split(',') if x)
    skip = set(x for x in a.skip.split(',') if x)
    book = Book(a.driver, a.dt)
    print(f"{'scene':7} {'id':5} {'quantity':46} {'forecast':>10} {'measured':>12} {'spread':>17} {'tolerance':>11} verdict")
    st = {}
    res = ROOT / 'results/theory' / f'{tag}.csv'
    res.parent.mkdir(parents=True, exist_ok=True)
    res_old = pd.read_csv(res, dtype=str, keep_default_na=False) if only and res.exists() else None
    for name in ORDER:
        scenes = [s for s in Scene.registry if s.batch == name and (not only or only & set(s.names)) and not (skip & set(s.names))]
        if not scenes:
            continue
        try:
            run_batch(name, scenes, a, book, st, out)
        except Exception as e:
            book.row(name, '', f'batch failed: {e!r}'[:200], '', '', '', 'ERROR')
        new = pd.DataFrame(book.rows)
        # A partial run replaces its own scenes in the table and leaves the rest.
        if only and res_old is not None and len(new):
            new = pd.concat([res_old[~res_old.scene.isin(set(new.scene))], new], ignore_index=True)
        new.to_csv(res, index=False)
    d = pd.DataFrame(book.rows)
    if not len(d):
        return
    rated = d[d.verdict.isin(['pass', 'FAIL', 'ERROR'])]
    print(f"\n{(rated.verdict == 'pass').sum()} pass, {(rated.verdict == 'FAIL').sum()} fail, {(rated.verdict == 'ERROR').sum()} error of {len(rated)} lines; written {res}")
    if (rated.verdict != 'pass').any():
        sys.exit(1)


if __name__ == '__main__':
    main()
