#!/usr/bin/env python3
"""Speed check against HERE probe speeds (MeTS-10 method, May 2019 only), real day against real day and sim against real.

    step6_probes.py [RUN NETDIR]

Reads berlin2019/probes/edge_hour.csv.gz: edge, day, hour, kmh, volume, free_flow. Probes are median speeds per 15 min joined to the
sim's own edges and averaged by hour. Derived probe data stays out of the repository: the licence does not allow sharing it.
Without RUN, prints the floor. Writes probes/floor.json and runs/RUN/probe_score.json.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

DAYS = ['2019-05-07', '2019-05-14', '2019-05-15', '2019-05-16', '2019-05-21', '2019-05-22', '2019-05-23', '2019-05-28']
HOURS = range(6, 21)
CLASSES = {'motorway': ('motorway', 'motorway_link', 'trunk', 'trunk_link'), 'arterial': ('primary', 'primary_link', 'secondary', 'secondary_link'), 'local': ('tertiary', 'tertiary_link', 'residential', 'unclassified', 'living_street')}


def by_class(d, klass):
    d = d[d.edge.isin(klass)]
    return d.groupby('hour').apply(lambda x: np.average(x.kmh, weights=x.volume.clip(lower=1)), include_groups=False)


def main():
    p = pd.read_csv(B19 / 'probes/edge_hour.csv.gz')
    box = json.load(open(B19 / 'step0/district.json'))['box']
    nd = sys.argv[2] if len(sys.argv) > 2 else 'm10'
    net = read_net(B19 / 'district' / nd / 'net.net.xml', B19 / 'district' / nd / 'net.pkl')
    kinds = {}
    for k, e in net['edges'].items():
        if not car_lanes(e):
            continue
        m = car_lanes(e)[0]['shape'].mean(axis=0)
        if box[0] <= m[0] < box[2] and box[1] <= m[1] < box[3]:
            t = e['type'].replace('highway.', '')
            for c, ts in CLASSES.items():
                if t in ts:
                    kinds.setdefault(c, set()).add(k)
    p = p[p.day.isin(DAYS) & p.hour.isin(HOURS)]
    out = {}
    for c, ks in kinds.items():
        tab = {d: by_class(p[p.day == d], ks) for d in DAYS}
        ref = pd.concat(tab, axis=1)
        pairs = [float((ref[a] - ref[b]).abs().div(ref[b]).mean()) for i, a in enumerate(DAYS) for b in DAYS[i + 1:] if a in ref and b in ref]
        out[c] = dict(edges=len(ks), edges_with_probes=int(p[p.edge.isin(ks)].edge.nunique()), real_kmh_by_hour={int(h): round(float(v), 1) for h, v in ref.mean(axis=1).items()}, floor_mean_abs_pct_median=100 * float(np.median(pairs)), floor_mean_abs_pct_worst=100 * float(np.max(pairs)), dip_real=float(ref.mean(axis=1).min() / ref.mean(axis=1).max()))
    (B19 / 'probes/floor.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({c: {k: v for k, v in x.items() if k != 'real_kmh_by_hour'} for c, x in out.items()}, indent=1))
    if len(sys.argv) > 1 and sys.argv[1] != '-':
        e = pd.read_csv(B19 / 'runs' / sys.argv[1] / 'edges.csv')
        e['hour'] = (e.begin // 3600).astype(int)
        g = e[e.hour.isin(HOURS)].groupby(['edge', 'hour']).agg(d=('distance', 'sum'), t=('samples', 'sum')).reset_index()
        g = g[g.t > 0]
        g['kmh'] = 3.6 * g.d / g.t
        g['volume'] = g.t
        res = {}
        for c, ks in kinds.items():
            s = by_class(g, ks)
            r = pd.Series(out[c]['real_kmh_by_hour'])
            r.index = r.index.astype(int)
            res[c] = dict(sim_kmh_by_hour={int(h): round(float(v), 1) for h, v in s.items()}, mean_abs_pct=100 * float((s - r).abs().div(r).mean()), bias_pct=100 * float((s - r).div(r).mean()), dip_sim=float(s.min() / s.max()), dip_real=out[c]['dip_real'], floor_median=out[c]['floor_mean_abs_pct_median'], floor_worst=out[c]['floor_mean_abs_pct_worst'], real_kmh_by_hour=out[c]['real_kmh_by_hour'])
        (B19 / 'runs' / sys.argv[1] / 'probe_score.json').write_text(json.dumps(res, indent=1))
        print(json.dumps({c: {k: v for k, v in x.items() if 'by_hour' not in k} for c, x in res.items()}, indent=1))


if __name__ == '__main__':
    main()
