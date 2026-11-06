#!/usr/bin/env python3
"""Tables for the macro engine. prepare.py NETDIR BASE DEMAND OUT. DEMAND: a route file (district pieces, first and last edge, departure, class only; no route is read).
Free speed per class: edges not ending at a signal and over 60 m, median of probe free_flow per road class and limit. Junction delay stays out because those edges have none. MEASURED, HERE May 2019."""
import collections
import csv
import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mtable as mt

DATA = Path('/home/erikf/projects/personal/cars-data/berlin2019')
def export(T, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    # free speeds
    # 05-06 h, R 3: deep-night probes are not free
    z = np.load(DATA / 'probes/edge_15min.npz', allow_pickle=True)
    with np.errstate(invalid='ignore', divide='ignore'):
        w = np.nan_to_num(z['vol'][:, :, 20:24])
        m = np.nan_to_num(z['med'][:, :, 20:24])
        pr = pd.Series((w * m).sum(axis=(1, 2)) / np.maximum(w.sum(axis=(1, 2)), 1e-9), index=[str(k) for k in z['keys']])
        pr = pr[w.sum(axis=(1, 2)) >= 40]
    sig = {k for k, j in T['junc'].items() if j['type'].startswith('traffic_light')}
    rows = []
    for k, e in T['edges'].items():
        if k in pr.index and e['to'] not in sig and e['L'] > 60 and e['car']:
            rows.append((e['type'], round(e['v'] * 3.6 / 10) * 10, pr[k], e['L']))
    fs = pd.DataFrame(rows, columns=['type', 'limit', 'free', 'L'])
    tab = fs.groupby(['type', 'limit']).agg(free=('free', 'median'), n=('free', 'size')).reset_index()
    tab = tab[tab.n >= 8]
    tab['ratio'] = tab.free / tab.limit
    print(tab.round(2).to_string())
    tab.to_csv(out / 'free_speeds.csv', index=False)
    ratio = {(r.type, r.limit): r.ratio for r in tab.itertuples()}
    gen = fs.assign(r=fs.free / fs.limit).groupby('limit').r.median().to_dict()
    BETA = {'residential': .30, 'living_street': .30, 'unclassified': .10, 'tertiary': .10, 'tertiary_link': .10}

    ids = sorted((k for k, e in T['edges'].items() if e['any']), key=str)
    idx = {k: i for i, k in enumerate(ids)}
    rev = {}
    for k in ids:
        e = T['edges'][k]
        rev.setdefault((e['frm'], e['to']), k)
    with open(out / 'edges.tsv', 'w') as f:
        f.write('id\tL\tv\tlanes\tmotorway\tbeta\tmask\trev\tmidblock\n')
        for k in ids:
            e = T['edges'][k]
            lim = round(e['v'] * 3.6 / 10) * 10
            r = ratio.get((e['type'], lim), gen.get(lim, 1.0))
            v = e['v'] * r
            if k in pr.index and e['to'] not in sig and e['L'] > 60:
                v = pr[k] / 3.6
            m = mt._or(l['mask'] for l in e['any'])
            o = rev.get((e['to'], e['frm']))
            n = max(len(e['car']), 1)
            f.write(f"{k}\t{e['L']:.2f}\t{v:.3f}\t{n}\t{int(e['type'] in mt.RAMPS)}\t{BETA.get(e['type'], 0.0)}\t{m}\t{idx[o] if o in idx else -1}\t{mt.midblock(e['v']):.1f}\n")

    pd.DataFrame([dict(id=k, type=T['edges'][k]['type'], x=T['edges'][k]['xy'][0], y=T['edges'][k]['xy'][1], L=T['edges'][k]['L']) for k in ids]).to_csv(out / 'edge_meta.csv', index=False)
    # arcs sorted by from edge
    moves = [m for m in T['moves'] if m['frm'] in idx and m['to'] in idx]
    moves.sort(key=lambda m: idx[m['frm']])
    aid = {m['id']: i for i, m in enumerate(moves)}
    ctrl = {c: i for i, c in enumerate(sorted(T['tl']))}
    with open(out / 'arcs.tsv', 'w') as f:
        f.write('id\tfrom\tto\tmask\tgroup\tuturn\n')
        for i, m in enumerate(moves):
            f.write(f"{i}\t{idx[m['frm']]}\t{idx[m['to']]}\t{m['mask']}\t{T['gof'][m['id']]}\t{int(m['dir'] in ('t', 'T'))}\n")
    with open(out / 'conns.tsv', 'w') as f:
        f.write('arc\tlane\tkind\tctrl\tidx\tf\ttg\ttf\tfoes\tfoe_yield\tpair_store\tpair_inner\n')
        for m in moves:
            e = T['edges'][m['frm']]
            for c in m['conns']:
                fd = mt.F_DIR.get(c['dir'], 1.0)
                if c['ctrl']:
                    kind, tg, tf = 1, *mt.GAPS['perm']
                elif c['state'] in ('M', 'O', 'o') or (not c['foe_m'] and not c.get('outside')):
                    kind, tg, tf = 0, 0, 0
                elif (e['type'] in mt.RAMPS and e['v'] >= 11) or c.get('merge'):
                    kind, tg, tf = 3, 0, 0
                else:
                    kind, (tg, tf) = 2, mt.GAPS[mt.gap_key(c, e['type'])]
                foes = ' '.join(str(aid[x]) for x in c['foe_m'] if x in aid)
                fy = ' '.join(str(aid[x]) for x in c['foe_yield'] if x in aid)
                sto, inn = 0.0, 0
                if c['ctrl'] and c['dir'] == 's':
                    t = T['edges'][c['to']]
                    if t['L'] < 50 and t['frm'] in sig and t['to'] in sig:
                        sto = max(t['L'] / mt.SPACING, 0.5)
                    if e['L'] < 50 and e['frm'] in sig and e['to'] in sig:
                        inn = 1
                f.write(f"{aid[m['id']]}\t{c['fl']}\t{kind}\t{ctrl[c['ctrl']] if c['ctrl'] else -1}\t{c['idx']}\t{fd}\t{tg}\t{tf}\t{foes}\t{fy}\t{sto:.2f}\t{inn}\n")
    with open(out / 'ctrls.tsv', 'w') as f:
        f.write('ctrl\tdur\tstate\n')
        for c, i in ctrl.items():
            for d, s in T['tl'][c]:
                f.write(f'{i}\t{d}\t{s}\n')

    # sites: all of them for the reveal; the scorer reads tuning sites only
    sens = {}
    for r in csv.reader(open(DATA / 'district/m12/sensors.csv')):
        e, l = r[1].rsplit('_', 1)
        sens.setdefault(r[0], [e, [], float(r[2])])[1].append(int(l))
    with open(out / 'sites.tsv', 'w') as f:
        f.write('site\tedge\tlanes\tpos\n')
        for s, (e, ls, pos) in sens.items():
            f.write(f"{s}\t{e}\t{' '.join(map(str, ls))}\t{pos}\n")
    json.dump({str(m['id']): aid[m['id']] for m in moves}, open(out / 'arc_of_move.json', 'w'))
    pd.DataFrame([dict(arc=aid[m['id']], frm=m['frm'], to=m['to'], lanes=' '.join(map(str, m['lanes'])), dir=m['dir'], kinds='+'.join(m['kinds'])) for m in moves]).to_csv(out / 'arcs_info.csv', index=False)



def main():
    netdir, base, demand, out = sys.argv[1:5]
    T = mt.read(DATA / 'district' / netdir / 'net.net.xml')
    mt.repair(T, mt.read(DATA / 'district' / base / 'net.net.xml'), [], None, mt.read_none_lanes(DATA / 'district' / netdir / 'lane_tags.csv'))
    mt.index_lanes(T)
    mt.lane_groups(T)
    export(T, out)
    CL = {'car': (0, 1.0), 'van': (1, 1.2), 'truck8t': (2, 2.0), 'truck18t': (2, 2.0), 'truck40t': (3, 2.0)}
    pat = re.compile(r'type="([^"]+)" depart="([^"]+)".*edges="([^"]+)"')
    n = bad = 0
    kinds = collections.Counter()
    with gzip.open(demand, 'rt') as fi, open(Path(out) / 'legs.tsv', 'w') as w:
        w.write('o\td\tdep\tclass\tpce\tw\n')
        for line in fi:
            m = pat.search(line)
            if not m:
                continue
            r = m[3].split()
            if len(r) < 2:
                bad += 1
                continue
            c, pce = CL[m[1]]
            kinds[m[1]] += 1
            w.write(f"{r[0]}\t{r[-1]}\t{float(m[2]):.0f}\t{c}\t{pce}\t10\n")
            n += 1
    print('legs', n, 'one-edge pieces left out', bad, dict(kinds))


if __name__ == '__main__':
    main()
