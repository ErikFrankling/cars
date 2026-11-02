#!/usr/bin/env python3
"""Recipe step 4's static checks on the unfitted v6.4 cut, with no simulation.

Whole-day route counts at factor 10 against tuning sites' real flow, vehicle-km and cordon against SVZ 2019.
Locked sites are not read. Writes district/static.json and district/static_sites.csv.
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from pyproj import Transformer

OUT = B19 / 'district'
SVZ = DATA / 'truth/berlin/opus-review-20261031/dtvw2019kfz.geojson'


def main():
    global OUT
    if len(sys.argv) > 1:
        OUT = OUT / sys.argv[1]
    net = read_net(OUT / 'net.net.xml', OUT / 'net.pkl')
    box = json.load(open(B19 / 'step0/district.json'))['box']
    freeze = json.load(open(B19 / 'step1/freeze.json'))
    edges = {k: e for k, e in net['edges'].items() if car_lanes(e)}
    def inside(e):
        p = car_lanes(e)[0]['shape'].mean(axis=0)
        return box[0] <= p[0] < box[2] and box[1] <= p[1] < box[3]
    in_box = {k for k, e in edges.items() if inside(e)}
    length = {k: car_lanes(e)[0]['length'] for k, e in edges.items()}
    count = collections.Counter()
    kinds = collections.Counter()
    with gzip.open(OUT / 'routes_f10.rou.gz', 'rt') as f:
        vt = None
        for line in f:
            m = re.search(r'type="([^"]+)"', line)
            if m and '<vehicle' in line:
                kinds[m[1]] += 1
            m = re.search(r'edges="([^"]+)"', line)
            if m:
                for e in m[1].split():
                    count[e] += 1
    km_all = sum(n * length[e] for e, n in count.items()) / 1000
    km_box = sum(n * length[e] for e, n in count.items() if e in in_box) / 1000
    by_type = collections.Counter()
    for e, n in count.items():
        if e in in_box:
            by_type[edges[e]['type'].replace('highway.', '')] += n * length[e] / 1000
    # SVZ: official working-day traffic on the count network, both directions
    g = json.load(open(SVZ))
    tr = Transformer.from_crs('EPSG:4326' if 'crs' not in g or '4326' in json.dumps(g.get('crs')) or 'CRS84' in json.dumps(g.get('crs')) else g['crs']['properties']['name'], net['location']['projParameter'], always_xy=True)
    off = np.array(list(map(float, net['location']['netOffset'].split(','))))
    keys = list(g['features'][0]['properties'].keys())
    dtv_key = next(k for k in keys if 'dtv' in k.lower() or 'kfz' in k.lower())
    svz_km = 0.0
    def in_box(q):
        return box[0] <= q[0] < box[2] and box[1] <= q[1] < box[3]
    svz_cordon = 0.0
    svz_rows = []
    for ft in g['features']:
        c = ft['geometry']['coordinates']
        lines = c if ft['geometry']['type'] == 'MultiLineString' else [c]
        v = ft['properties'].get(dtv_key)
        if v in (None, ''):
            continue
        v = float(v)
        for ln in lines:
            a = np.array([tr.transform(*p[:2]) for p in ln]) + off
            seg = np.linalg.norm(np.diff(a, axis=0), axis=1)
            mid = (a[:-1] + a[1:]) / 2
            ok = (mid[:, 0] >= box[0]) & (mid[:, 0] < box[2]) & (mid[:, 1] >= box[1]) & (mid[:, 1] < box[3])
            svz_km += float((seg[ok] * v).sum()) / 1000
            svz_cordon += v * sum(in_box(a[i]) != in_box(a[i + 1]) for i in range(len(a) - 1))
    cordon = 0
    for k, e in edges.items():
        sh = car_lanes(e)[0]['shape']
        if in_box(sh[0]) != in_box(sh[-1]) and e['type'].replace('highway.', '') not in ('residential', 'living_street', 'unclassified', 'service'):
            cordon += count.get(k, 0)
    # sites: tuning only
    sites = pd.read_csv(B19 / 'step0/sites.csv')
    real = pd.read_csv(B19 / 'step1/real_days.csv.gz')
    tuning = set(freeze['tuning_sites'])
    daily = real[real.site.isin(tuning)].groupby(['site', 'date']).flow.sum().groupby('site').mean()
    rows = []
    sn = pd.read_csv(OUT / 'sensors.csv', header=None, names=['site', 'lane', 'pos'])
    site_edge = dict(zip(sn.site, sn.lane.str.rsplit('_', n=1).str[0]))
    for s in sorted(tuning):
        e = site_edge.get(s, sites[sites.site == s].iloc[0].edge)
        rows.append(dict(site=s, edge=e, road_class=sites[sites.site == s].iloc[0].road_class, real_per_day=float(daily.get(s, np.nan)), route_count=count.get(e, 0)))
    d = pd.DataFrame(rows).dropna()
    d['ratio'] = d.route_count / d.real_per_day
    d.to_csv(OUT / 'static_sites.csv', index=False)
    res = dict(vehicles=sum(kinds.values()), by_type=dict(kinds), km_all_cut_M=km_all / 1e6, km_box_M=km_box / 1e6, km_box_by_road_M={k: round(v / 1e6, 3) for k, v in by_type.most_common()}, svz_count_network_in_box_M=svz_km / 1e6, svz_key=dtv_key, cordon_sim_veh_day=cordon, cordon_svz_veh_day=svz_cordon, cordon_ratio=cordon / max(svz_cordon, 1), tuning_sites=int(len(d)), sum_route_over_real=float(d.route_count.sum() / d.real_per_day.sum()), median_ratio=float(d.ratio.median()), ratio_quartiles=[float(d.ratio.quantile(.25)), float(d.ratio.quantile(.75))], within_20pct=float(((d.ratio > .8) & (d.ratio < 1.2)).mean()), under_half=float((d.ratio < .5).mean()), over_double=float((d.ratio > 2).mean()), r2_daily=float(np.corrcoef(d.route_count, d.real_per_day)[0, 1] ** 2))
    (OUT / 'static.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    print(d.sort_values('ratio').head(6).to_string())
    print(d.sort_values('ratio').tail(6).to_string())


if __name__ == '__main__':
    main()
