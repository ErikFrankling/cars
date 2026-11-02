#!/usr/bin/env python3
"""One line per hill-climb round: rounds.py ROUND RUN "what changed" "step" [--factor F] [--scale S]. Appends to research/truth/berlin2019/rounds.csv.
Running cars at fixed times against F x the 10% base run, and, for a day that finished, volume and speed on tuning sites.
Locked sites are never read. A run's site_hour.csv stays the benchmark's input."""
import argparse
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

BASE = 'final_m10_f01'
OUT = Path(__file__).resolve().parents[2] / 'research/truth/berlin2019/rounds.csv'
T = [21600, 23400, 25200, 27000, 28800]
COLS = ['round', 'run', 'step', 'change', 'factor', 'r0600', 'r0630', 'r0700', 'r0730', 'r0800', 'ratio_0730', 'last_time_h', 'teleports', 'stopped_edges_1h', 'unfinished_share', 'rmsn', 'wape', 'r2', 'slope', 'geh5', 'bias', 'shape_pts', 'speed_median_abs', 'probe_arterial_pct', 'probe_motorway_pct', 'jam_caught', 'jam_false']

p = argparse.ArgumentParser()
p.add_argument('round')
p.add_argument('run')
p.add_argument('change')
p.add_argument('step')
p.add_argument('--factor', type=float, default=5)
a = p.parse_args()
d = B19 / 'runs' / a.run
s = pd.read_csv(d / 'summary.csv')
b = pd.read_csv(B19 / 'runs' / BASE / 'summary.csv')
get = lambda f, t: int(f[f.time == t].running.iloc[0]) if (f.time == t).any() else ''
row = dict(round=a.round, run=a.run, step=a.step, change=a.change, factor=a.factor, last_time_h=round(float(s.time.max()) / 3600, 2), teleports=int(s.teleports.iloc[-1]))
for name, t in zip(['r0600', 'r0630', 'r0700', 'r0730', 'r0800'], T):
    row[name] = get(s, t)
if row['r0730'] != '':
    row['ratio_0730'] = round(row['r0730'] / (a.factor * get(b, 27000)), 2)
if (d / 'edges.csv').exists():
    e = pd.read_csv(d / 'edges.csv', on_bad_lines='skip')
    e = e[(e.samples >= 300) & (e.distance / e.samples.clip(lower=1) < .8) & (e.begin < e.begin.max())]
    n = 0
    for k, q in e.groupby('edge'):
        t = np.sort(q.begin.values)
        n += max(map(len, np.split(t, np.where(np.diff(t) != 900)[0] + 1))) >= 4
    row['stopped_edges_1h'] = int(n)
x = d / 'exit.json'
if x.exists():
    j = json.loads(x.read_text())
    row['unfinished_share'] = round(j['nothing_stuck']['unfinished_share'], 4)
    sc = j['scores_tuning_sites']
    med = lambda *path: round(float(np.median([(lambda v: v)(__import__('functools').reduce(lambda m, k: m.get(k, {}), path, day)) for day in sc.values()])), 3)
    row.update(rmsn=med('volume_07_18', 'rmsn'), wape=med('volume_07_18', 'wape'), r2=med('volume_07_18', 'r2'), slope=med('volume_07_18', 'slope'), geh5=med('volume_07_18', 'geh_lt5'), bias=med('volume_07_18', 'bias'), shape_pts=med('day_shape', 'mean_abs_share_points'), speed_median_abs=med('speed_site_median_abs_kmh'), jam_caught=med('where_when', 'caught'), jam_false=med('where_when', 'false_alarm'))
pr = d / 'probe_score.json'
if pr.exists():
    j = json.loads(pr.read_text())
    row.update(probe_arterial_pct=round(j['arterial']['mean_abs_pct'], 1), probe_motorway_pct=round(j['motorway']['mean_abs_pct'], 1))
new = not OUT.exists()
with open(OUT, 'a', newline='') as f:
    w = csv.DictWriter(f, COLS)
    if new:
        w.writeheader()
    w.writerow(row)
print(row)
