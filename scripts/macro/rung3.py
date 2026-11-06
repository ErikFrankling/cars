#!/usr/bin/env python3
"""Rung 3: movement table, static audits and the no-model test. Tuning sites only: other sites' counts are never loaded.

    rung3.py NETDIR [--flows MOVEFLOWS.csv.gz] [--greens GREENS.csv]

--flows: hour,m_from,m_to,q, foe flows for the second reading of the test. Without it, only the charitable bound (nothing to yield to).
--greens: controller,link,gp,gq,C,nst override of the invented program, for a retimed table.
Real flow is a lower bound on real capacity: for each tuning site, day and hour, real flow <= 1.1 x table capacity.
"""
import argparse
import collections
import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mtable as mt

DATA = Path('/home/erikf/projects/personal/cars-data/berlin2019')
SAT = (1640.0, 1750.0, 1900.0)


def load_greens(path):
    out = {}
    for r in csv.DictReader(open(path)):
        out[(r['ctrl'], int(r['idx']))] = (float(r['gp']), float(r['gq']), float(r['C']), int(r['nst']))
    return out


def load_flows(path):
    fl = collections.defaultdict(dict)
    with gzip.open(path, 'rt') as f:
        for r in csv.DictReader(f):
            fl[int(r['hour'])][(r['frm'], r['to'])] = float(r['q'])
    return fl


def edge_cap(T, e, n, s, Q=None, gr=None):
    """The n lanes that can pass the most, each with the best movement it can serve. Which physical lanes a detector covers is known only as
    rightmost, second from right; on a map with a bus lane that index does not carry over, so this stays charitable."""
    ed = T['edges'][e]
    per = []
    for l in ed['car']:
        best, bc = 0.0, None
        for c in T['by_lane'].get((e, l['i']), []):
            gs = gr.get((c['ctrl'], c['idx'])) if gr and c['ctrl'] else None
            v = mt.conn_capacity(c, ed, s, Q, gs)
            if v > best:
                best, bc = v, c
        per.append((best, bc))
    per.sort(key=lambda r: -r[0])
    return sum(r[0] for r in per[:n]), [r[1] for r in per[:n]]


def downstream_bound(T, e, n, s, Q=None, gr=None, depth=8):
    """Own stop line, walked on through plain chains (one way on, nothing to yield to)."""
    cap, cs = edge_cap(T, e, n, s, Q, gr)
    where = e
    cur = e
    whole = n >= len(T['edges'][e]['car'])
    for _ in range(depth):
        out = T['out'].get(cur, [])
        if len(out) != 1 or out[0]['conns'][0]['ctrl'] or out[0]['conns'][0]['foe_m']:
            break
        nxt = out[0]['to']
        ed = T['edges'][nxt]
        v, k = edge_cap(T, nxt, len(ed['car']), s, Q, gr)
        if whole and v < cap:
            cap, cs, where = v, k, nxt
        cur = nxt
    return cap, cs, where


def upstream_bound(T, e, s, Q=None, gr=None):
    """Everything that can flow onto this edge. Trips starting on the edge are left out, so read it only for whole edges."""
    inc = T['inc'].get(e, [])
    if not inc:
        return None
    tot = 0.0
    for m in inc:
        ed = T['edges'][m['frm']]
        best = {}
        for c in m['conns']:
            gs = gr.get((c['ctrl'], c['idx'])) if gr and c['ctrl'] else None
            best[c['fl']] = max(best.get(c['fl'], 0.0), mt.conn_capacity(c, ed, s, Q, gs))
        tot += sum(best.values())
    return tot


def audits(T, name, flows):
    """Connections with no green, under a few seconds; main-road movements under 50 veh/h at 08 h on the screen's foe flows; give-way through movements on main roads."""
    Q = None
    if flows:
        Q = {T['index'][k]: v for k, v in flows[8].items() if k in T['index']}
    no_green, short = [], []
    for c in T['conns']:
        if c['ctrl']:
            if c['gp'] + c['gq'] <= 0:
                no_green.append(c)
            elif c['gp'] + c['gq'] < 5:
                short.append(c)
    low = []
    prio = []
    for m in T['moves']:
        e = T['edges'][m['frm']]
        if e['type'] not in mt.MAIN or not e['car']:
            continue
        cap = {}
        for c in m['conns']:
            cap[c['fl']] = max(cap.get(c['fl'], 0.0), mt.conn_capacity(c, e, 1640.0, Q))
        tot = sum(cap.values())
        if tot < 50:
            low.append(dict(frm=m['frm'], to=m['to'], name=e['name'], type=e['type'], dir=m['dir'], kinds='+'.join(m['kinds']), cap=round(tot, 1), q08=round(Q.get(m['id'], 0.0)) if Q else ''))
        if m['dir'] == 's' and set(m['kinds']) & {'minor', 'stop', 'rbl'} and e['type'] in mt.MAIN[:8]:
            prio.append(dict(frm=m['frm'], to=m['to'], name=e['name'], type=e['type'], kinds='+'.join(m['kinds']), j=m['j'], x=T['junc'][m['j']]['x'] if m['j'] in T['junc'] else None, y=T['junc'][m['j']]['y'] if m['j'] in T['junc'] else None, cap=round(tot, 1), q08=round(Q.get(m['id'], 0.0)) if Q else ''))
    ng_main = [c for c in no_green if T['edges'][c['frm']]['type'] in mt.MAIN]
    print(f'[{name}] connections {len(T["conns"])} movements {len(T["moves"])} groups {len(T["groups"])}')
    print(f'[{name}] signal connections with no green {len(no_green)} (main roads {len(ng_main)}), green under 5 s {len(short)}')
    print(f'[{name}] main-road movements under 50 veh/h at s 1640, {"foes from the screen, 08 h" if Q else "no foe flow"}: {len(low)}')
    print(f'[{name}] give-way or rbl through movements on motorway..secondary: {len(prio)}')
    return dict(no_green=no_green, short=short, low=low, prio=prio)


def no_model(T, name, flows, gr, sensors, real, sites, out):
    res = {}
    rows = []
    for s in SAT:
        viol = collections.Counter()
        vs = collections.defaultdict(list)
        n = 0
        for site, d in real.groupby('site'):
            if site not in sensors:
                continue
            e, ls = sensors[site]
            n_lanes = min(len(ls), len(T['edges'][e]['car']))
            whole = n_lanes == len(T['edges'][e]['car'])
            for h, g in d.groupby('hour'):
                Q = None
                if flows:
                    Q = {T['index'][k]: v for k, v in flows[int(h)].items() if k in T['index']} if int(h) in flows else None
                cap_d, cs, where = downstream_bound(T, e, n_lanes, s, Q, gr)
                cap_u = upstream_bound(T, e, s, Q, gr) if whole else None
                cap_m = n_lanes * mt.midblock(T['edges'][e]['v'])
                cap = min(x for x in (cap_d, cap_u, cap_m) if x is not None)
                bound = 'stop_line' if cap == cap_d else 'feed' if cap == cap_u else 'mid_block'
                for q in g.flow.values:
                    if np.isnan(q):
                        continue
                    n += 1
                    if q > 1.1 * cap:
                        viol[site] += 1
                        vs[site].append((int(h), float(q), float(cap), bound, where))
        tot = sum(viol.values())
        res[s] = dict(site_hours=n, violations=tot, sites=len(viol))
        print(f'[{name}] s {s:.0f}: site-hours {n}, over 1.1 x capacity {tot} ({100 * tot / max(n, 1):.2f}%), sites {len(viol)}')
        for site in viol:
            e, ls = sensors[site]
            w = max(vs[site], key=lambda r: r[1] / max(r[2], 1))
            ed = T['edges'][w[4]]
            lanes = min(len(ls), len(T['edges'][e]['car']))
            _, cs, _ = downstream_bound(T, e, lanes, s, None, gr)
            kinds = sorted({mt.kind(c) for c in cs if c})
            sh = sorted({round((c['gp'] + c['gq']) / c['C'], 2) for c in cs if c and c['ctrl']})
            rows.append(dict(map=name, s=int(s), site=site, street=sites.street.get(site, ''), road_class=sites.road_class.get(site, ''), edge=e, lanes_used=lanes, map_lanes=len(T['edges'][e]['car']), det=int(sites.n_det.get(site, 0)), hours_over=viol[site], worst_hour=w[0], worst_real=round(w[1]), cap=round(w[2]), ratio=round(w[1] / max(w[2], 1), 2), bound=w[3], at=w[4], kinds='+'.join(kinds), gc=';'.join(map(str, sh)), need_gc=round(w[1] / (lanes * s), 2)))
    pd.DataFrame(rows).to_csv(out, index=False)
    return res


def write_table(T, path):
    """One row per movement: capacity at the three saturation flows with nothing to yield to, lanes, group, cycle, green, conflicts, storage, free time."""
    with gzip.open(path, 'wt') as f:
        w = csv.writer(f)
        w.writerow(['id', 'from', 'to', 'type', 'name', 'dir', 'kinds', 'lanes', 'n_lanes', 'group', 'cycle', 'gp', 'gq', 'cap_1285', 'cap_1640', 'cap_1895', 'conflicts', 'storage', 'free_s', 'junction'])
        for m in T['moves']:
            e = T['edges'][m['frm']]
            caps = []
            for s in SAT:
                b = {}
                for c in m['conns']:
                    b[c['fl']] = max(b.get(c['fl'], 0.0), mt.conn_capacity(c, e, s))
                caps.append(round(sum(b.values()), 1))
            c0 = m['conns'][0]
            g = T['groups'][T['gof'][m['id']]]
            foes = sorted({x for c in m['conns'] for x in c['foe_m']})
            w.writerow([m['id'], m['frm'], m['to'], e['type'], e['name'], m['dir'], '+'.join(m['kinds']), ' '.join(map(str, m['lanes'])), len(m['lanes']), g['id'], c0.get('C', ''), c0.get('gp', ''), c0.get('gq', ''), *caps, ' '.join(map(str, foes)), round(g['storage'], 1), round(e['L'] / max(e['v'], 1), 2), m['j']])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('netdir')
    p.add_argument('--flows')
    p.add_argument('--greens')
    p.add_argument('--tag', default='')
    p.add_argument('--repair', help='map before lane marking, to restore stranded lanes from')
    p.add_argument('--reopen', help='json list of [edge, lane, reason]')
    a = p.parse_args()
    name = a.netdir + a.tag
    T = mt.read(DATA / 'district' / a.netdir / 'net.net.xml')
    out = DATA / 'macro' / a.netdir
    out.mkdir(parents=True, exist_ok=True)
    if a.repair:
        rlog = []
        reopen = [tuple(x) for x in json.load(open(a.reopen))] if a.reopen else []
        n = mt.repair(T, mt.read(DATA / 'district' / a.repair / 'net.net.xml'), reopen, rlog, mt.read_none_lanes(DATA / 'district' / a.netdir / 'lane_tags.csv'))
        pd.DataFrame(rlog).to_csv(out / f'repairs{a.tag}.csv', index=False)
        print(f'[{name}] repairs: {n} connections restored from {a.repair}, {len(reopen)} lanes reopened')
    mt.index_lanes(T)
    mt.lane_groups(T)
    write_table(T, out / 'movements.csv.gz')
    flows = load_flows(a.flows) if a.flows else None
    gr = load_greens(a.greens) if a.greens else None
    au = audits(T, name, flows)
    pd.DataFrame(au['low']).to_csv(out / f'audit_low{a.tag}.csv', index=False)
    pd.DataFrame(au['prio']).to_csv(out / f'audit_prio{a.tag}.csv', index=False)
    freeze = json.load(open(DATA / 'step1/freeze.json'))
    tuning = set(freeze['tuning_sites'])
    real = pd.read_csv(DATA / 'step1/real_days.csv.gz')
    real = real[real.site.isin(tuning)]
    sensors = {}
    for r in csv.reader(open(DATA / 'district/m12/sensors.csv')):
        if r[0] in tuning:
            e, l = r[1].rsplit('_', 1)
            sensors.setdefault(r[0], (e, []))[1].append(int(l))
    sites = pd.read_csv(DATA / 'step0/sites.csv')
    sites = sites[sites.site.isin(tuning)].set_index('site')
    res = no_model(T, name, flows, gr, sensors, real, sites, out / f'no_model{a.tag}.csv')
    (out / f'no_model{a.tag}.json').write_text(json.dumps({str(k): v for k, v in res.items()}, indent=1))


if __name__ == '__main__':
    main()
