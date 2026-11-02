#!/usr/bin/env python3
"""Braking on the approach, from a `cars av --trace` log. Generalises brake_orig/an2.py and churn.py.

Speed lost is every m/s taken off between entering the approach and the line. The gentlest profile that
reaches the same place at the same time and takes the corner at its speed loses only
v0 - min(average speed to the line, turn speed, v0). Reported for all, straight and turning cars.
Usage: brake.py <net.xml> <trace.log>..."""
import collections, json, re, sys
import numpy as np
import xml.etree.ElementTree as ET

M = 1500.0
PAT = re.compile(r'tr t=([\d.]+) trip (\d+) lane (\S+) pos ([\d.\-]+) v ([\d.\-]+) a ([\d.\-]+) st (\S+) link \S+ seq \d+ tl ([\d.\-]+)')


def net_info(path, junction='B1'):
    root = ET.parse(path).getroot()
    speed, length, app = {}, {}, set()
    for e in root.findall('edge'):
        for l in e.findall('lane'):
            speed[l.get('id')] = float(l.get('speed'))
            length[l.get('id')] = float(l.get('length'))
        if e.get('function') != 'internal' and e.get('to') == junction:
            app.add(e.get('id'))
    return speed, length, app


def pct(x, q):
    return float(np.percentile(x, q)) if len(x) else None


def read(log, speed, length, app, junction='B1'):
    cars = collections.defaultdict(list)
    turn = {}
    for line in open(log):
        if not line.startswith('tr '):
            continue
        m = PAT.match(line)
        if not m:
            continue
        t, trip, lane, pos, v, a, st, tl = m.groups()
        trip = int(trip)
        if lane.startswith(f':{junction}_'):
            turn.setdefault(trip, speed.get(lane, 13.89))
        elif lane.rsplit('_', 1)[0] in app:
            d = length[lane] - float(pos)
            cars[trip].append((float(t), d, float(v), float(a), int(st, 16) & 7, float(tl)))
    return cars, turn


def analyse(net, log, junction='B1', min_len=None):
    speed, length, app = net_info(net, junction)
    cars, turn = read(log, speed, length, app, junction)
    L = max((length[l] for l in length if l.rsplit('_', 1)[0] in app), default=0.0)
    rows = []
    for trip, r in cars.items():
        r = np.array(r)
        if r[0, 1] < L - 10 or r[-1, 1] > 3 or trip not in turn:
            continue
        t, d, v, a, st, tl = r.T
        dv = np.diff(v)
        lost = -dv[dv < 0].sum()
        ke = 0.5 * M * np.maximum(v[:-1] ** 2 - v[1:] ** 2, 0).sum() / 3600
        T = t[-1] - t[0]
        vc = d[0] / max(T, 0.1)
        vk = min(vc, turn[trip], v[0])
        jerk = np.diff(a) / np.maximum(np.diff(t), 1e-3)
        bins = np.zeros(6)
        for i in np.nonzero(dv < 0)[0]:
            bins[min(int(d[i] // 50), 5)] -= dv[i]
        m = (st > 0) & (tl > 0)
        dtl = np.abs(np.diff(tl[m]))
        f = np.nonzero(st == 2)[0]
        rows.append(dict(trip=trip, turning=turn[trip] < 13, lost=lost, ideal=v[0] - vk, wh=ke, ideal_wh=0.5 * M * (v[0] ** 2 - vk ** 2) / 3600,
                         peak=-a.min(), jerk=-jerk.min() if len(jerk) else 0.0, bins=bins, changes=int((dtl > 0.05).sum()), moved=float(dtl.sum()),
                         firm=float(d[f[0]]) if len(f) else None, stopped=bool(v.min() < 0.5), T=T, free=d[0] / 13.89))
    out = {}
    for name, keep in (('all', lambda c: True), ('straight', lambda c: not c['turning']), ('turning', lambda c: c['turning'])):
        c = [x for x in rows if keep(x)]
        if not c:
            out[name] = dict(n=0)
            continue
        col = lambda k: np.array([x[k] for x in c], float)
        bins = np.sum([x['bins'] for x in c], axis=0)
        peak = col('peak')
        firm = [x['firm'] for x in c if x['firm'] is not None]
        out[name] = dict(n=len(c), speed_lost=float(col('lost').mean()), gentlest=float(col('ideal').mean()), wh=float(col('wh').mean()),
                         gentlest_wh=float(col('ideal_wh').mean()), peak50=pct(peak, 50), peak90=pct(peak, 90), peak99=pct(peak, 99),
                         over1=float((peak > 1).mean()), over15=float((peak > 1.5).mean()), over2=float((peak > 2).mean()), over3=float((peak > 3).mean()),
                         jerk90=pct(col('jerk'), 90), jerk99=pct(col('jerk'), 99), where=[float(x) for x in bins / max(bins.sum(), 1e-9)],
                         changes50=pct(col('changes'), 50), changes90=pct(col('changes'), 90), moved50=pct(col('moved'), 50), moved90=pct(col('moved'), 90),
                         firm10=pct(firm, 10), firm50=pct(firm, 50), firm90=pct(firm, 90), stopped=float(col('stopped').mean()),
                         extra=float((col('T') - col('free')).mean()))
    return out


if __name__ == '__main__':
    for log in sys.argv[2:]:
        r = analyse(sys.argv[1], log)
        print(log)
        for name, m in r.items():
            if m['n']:
                print(f" {name:9s} n={m['n']:4d} lost {m['speed_lost']:.2f} gentlest {m['gentlest']:.2f} Wh {m['wh']:.1f}/{m['gentlest_wh']:.1f} peak50/90/99 {m['peak50']:.2f} {m['peak90']:.2f} {m['peak99']:.2f}"
                      f" >1 {m['over1']:.2f} >1.5 {m['over15']:.2f} >2 {m['over2']:.2f} >3 {m['over3']:.2f} jerk90 {m['jerk90']:.1f} changes {m['changes50']:.0f}/{m['changes90']:.0f} moved {m['moved50']:.1f}/{m['moved90']:.1f}"
                      f" firm {m['firm50'] or 0:.0f} extra {m['extra']:.1f} where {[round(x, 2) for x in m['where']]}")
