#!/usr/bin/env python3
"""Keep each program's phases, move green between them so no lane is much fuller than another. Signal timing ESTIMATED from model flows.
retime.py IN.net.xml lane_load.csv.gz OUT.net.xml [--cycle C] [--type static|actuated] [--hours 7,16]
Flows are MATSim's at the peak hours, never counts. Minimum green 5 s. Prints lanes over capacity before and after: green share x 1,900/h."""
import argparse
import collections
import re
from xml.etree.ElementTree import iterparse

import numpy as np
import pandas as pd

SAT = 1900.0
p = argparse.ArgumentParser()
p.add_argument('net')
p.add_argument('load')
p.add_argument('out')
p.add_argument('--cycle', type=float, default=90)
p.add_argument('--type', default='static')
p.add_argument('--hours', default='7,16')
p.add_argument('--scale', type=float, default=1.0)
a = p.parse_args()
hours = [int(x) for x in a.hours.split(',')]
d = pd.read_csv(a.load)
d = d[d.h.isin(hours)]
Q = (d.groupby(['edge', 'next']).q.sum() / len(hours) * a.scale).to_dict()
tl, conns, lanes_for = {}, collections.defaultdict(list), collections.defaultdict(set)
for _, el in iterparse(a.net, events=('end',)):
    if el.tag == 'tlLogic':
        tl[el.get('id')] = [(float(x.get('duration')), x.get('state')) for x in el.findall('phase')]
        el.clear()
    elif el.tag == 'connection':
        if el.get('via') or el.get('tl'):
            lanes_for[(el.get('from'), el.get('to'))].add(int(el.get('fromLane')))
        if el.get('tl'):
            conns[el.get('tl')].append((el.get('from'), el.get('to'), int(el.get('fromLane')), int(el.get('linkIndex'))))
        el.clear()
    elif el.tag in ('edge', 'junction'):
        el.clear()


def lane_flows(cs):
    fl = collections.Counter()
    links = collections.defaultdict(list)
    for f, t, ln, i in cs:
        n = max(1, len(lanes_for[(f, t)]))
        fl[(f, ln)] += Q.get((f, t), 0.0) / n
        links[(f, ln)].append(i)
    return fl, links


def evaluate(ph, fl, links, C):
    vc = {}
    for lane, idx in links.items():
        g = sum(dur for dur, s in ph if any(s[i] in 'Gg' for i in idx))
        vc[lane] = fl[lane] / max(1e-6, SAT * g / C)
    return vc


blocks = {}
over0 = over1 = heavy = 0
worst0, worst1 = [], []
for t, ph in tl.items():
    cs = conns[t]
    if not cs:
        continue
    fl, links = lane_flows(cs)
    C0 = sum(x for x, _ in ph)
    greens = [k for k, (x, s) in enumerate(ph) if 'G' in s or 'g' in s]
    fixed = sum(x for k, (x, _) in enumerate(ph) if k not in greens)
    ph = list(ph)
    vc0 = evaluate(ph, fl, links, C0)
    if len(greens) >= 1:
        C = max(a.cycle, fixed + 5 * len(greens))
        # scale to the target cycle first
        room = C - fixed
        tot = sum(ph[k][0] for k in greens)
        for k in greens:
            ph[k] = (max(5.0, ph[k][0] * room / tot), ph[k][1])
        # move a second at a time from the phase whose lanes are emptiest to the fullest lane's phase
        for _ in range(int(room) * 3):
            vc = evaluate(ph, fl, links, C)
            if not vc:
                break
            worst = max(vc, key=vc.get)
            idx = links[worst]
            give = [k for k in greens if any(ph[k][1][i] in 'Gg' for i in idx)]
            take = [k for k in greens if k not in give and ph[k][0] > 5.0]
            if not give or not take:
                break
            def pain(k):
                return max((vc[l] for l, ii in links.items() if any(ph[k][1][i] in 'Gg' for i in ii)), default=0.0)
            k_from = min(take, key=pain)
            if pain(k_from) >= vc[worst] * .98:
                break
            ph[k_from] = (ph[k_from][0] - 1, ph[k_from][1])
            ph[give[0]] = (ph[give[0]][0] + 1, ph[give[0]][1])
    else:
        C = C0
    vc1 = evaluate(ph, fl, links, C)
    heavy += sum(fl[l] > 100 for l in links)
    over0 += sum(vc0[l] > 1 and fl[l] > 100 for l in links)
    over1 += sum(vc1[l] > 1 and fl[l] > 100 for l in links)
    worst0.append(max(vc0.values()))
    worst1.append(max(vc1.values()))
    blocks[t] = f'    <tlLogic id="{t}" type="{a.type}" programID="0" offset="0">\n' + '\n'.join(f'        <phase duration="{round(x)}" state="{s}"' + (f' minDur="5" maxDur="{round(x * 1.5)}"' if a.type == 'actuated' and k in greens else '') + '/>' for k, (x, s) in enumerate(ph)) + '\n    </tlLogic>\n'
print(f'lanes over capacity at these flows, of {heavy} carrying over 100/h: before {over0}, after {over1}; worst lane per controller p50/p90 before {np.percentile(worst0, 50):.2f}/{np.percentile(worst0, 90):.2f}, after {np.percentile(worst1, 50):.2f}/{np.percentile(worst1, 90):.2f}')
n = 0
with open(a.net) as f, open(a.out, 'w') as o:
    skip = False
    for line in f:
        if '<tlLogic ' in line:
            m = re.search(r' id="([^"]*)"', line).group(1)
            o.write(blocks.get(m, ''))
            skip = '</tlLogic>' not in line
            n += 1
            continue
        if skip:
            skip = '</tlLogic>' not in line
            continue
        o.write(line)
print('rewrote', n)
