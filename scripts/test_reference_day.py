#!/usr/bin/env python3
"""Checks scripts/reference_day.py on a tiny made-up city. Run with python3 -I from the repo root."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parent / 'reference_day.py'
NET = '''<net><location netOffset="0.00,0.00" convBoundary="0,0,5000,5000" origBoundary="0,0,1,1" projParameter="+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"/>
{}
</net>'''


def edge(i, x0, y0, x1, y1, start, end, lanes=2):
    ls = ''.join(f'<lane id="e{i}_{n}" index="{n}" speed="13.89" length="1000" shape="{x0},{y0} {x1},{y1}"/>' for n in range(lanes))
    return f'<edge id="e{i}" from="{start}" to="{end}" type="highway.primary">{ls}</edge>'


def build(tmp):
    from pyproj import Transformer
    back = Transformer.from_crs('+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs', 'EPSG:4326', always_xy=True)
    edges = []
    sites = []
    n_sites = 30
    for i in range(n_sites):
        x = 200 + i * 150
        edges.append(edge(i, x, 100, x, 1100, f'a{i}', f'b{i}'))
        lon, lat = back.transform(x, 600)
        sites.append(dict(site=f's{i}', lat=lat, lon=lon, bearing_deg=0.0, direction='N', lanes=2, name='', road_class='urban', sensor='', qc='ok'))
    # good on geometry, opposite direction, far away and no direction on a two-way road
    edges.append(edge(100, 300, 2000, 300, 3000, 'c', 'd'))
    lon, lat = back.transform(300, 2500)
    sites.append(dict(site='wrong_way', lat=lat, lon=lon, bearing_deg=180.0, direction='S', lanes=2, name='', road_class='urban', sensor='', qc='ok'))
    lon, lat = back.transform(3000, 4000)
    sites.append(dict(site='far', lat=lat, lon=lon, bearing_deg=0.0, direction='N', lanes=2, name='', road_class='urban', sensor='', qc='ok'))
    edges.append(edge(101, 600, 2000, 600, 3000, 'e', 'f'))
    edges.append(edge(102, 600, 3000, 600, 2000, 'f', 'e'))
    lon, lat = back.transform(600, 2500)
    sites.append(dict(site='two_way', lat=lat, lon=lon, bearing_deg=np.nan, direction='', lanes=2, name='', road_class='urban', sensor='', qc='ok'))
    (tmp / 'net.xml').write_text(NET.format('\n'.join(edges)))
    ref = tmp / 'ref'
    ref.mkdir()
    pd.DataFrame(sites).to_csv(ref / 'sites.csv', index=False)
    rng = np.random.default_rng(1)
    profile = 100 + 800 * np.exp(-((np.arange(24) - 8) / 2) ** 2) + 900 * np.exp(-((np.arange(24) - 17) / 2.5) ** 2)
    rows = []
    dates = [f'2026-09-{d:02}' for d in (1, 2, 3, 8, 9, 10)]
    for s in sites:
        for date in dates:
            for h in range(24):
                rows.append(dict(site=s['site'], date=date, hour=h, flow=float(rng.poisson(profile[h])), speed=45 - 15 * profile[h] / profile.max() + rng.normal(0, 1)))
    d = pd.DataFrame(rows)
    d[d.date != dates[0]].to_csv(ref / 'other_days.csv.gz', index=False)
    d[d.date == dates[0]].drop(columns='date').to_csv(ref / 'reference_day.csv', index=False)
    (ref / 'noise.json').write_text(json.dumps(dict(city='test', reference_date=dates[0], normal_dates=dates)))
    return d, dates, profile


def run(tmp, *extra):
    out = subprocess.run([sys.executable, '-I', str(SCRIPT), '--ref', str(tmp / 'ref'), '--net', str(tmp / 'net.xml'), '--out', str(tmp / 'out'), *extra], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout, json.loads((tmp / 'out/report.json').read_text()), pd.read_csv(tmp / 'out/matches.csv')


def sim_csv(path, d, date, scale=1.0, shift=0, teleports=0):
    q = d[(d.date == date) & d.site.str.startswith('s')].copy()
    q['edge'] = 'e' + q.site.str[1:]
    q['begin'] = ((q.hour + shift) % 24) * 3600
    q['entered'] = (q.flow * scale).round()
    q['samples'] = q.entered * 72.0
    q['distance'] = q.samples * q.speed / 3.6
    q['teleports'] = teleports
    q[['begin', 'edge', 'samples', 'distance', 'entered', 'teleports']].to_csv(path, index=False)


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        d, dates, _ = build(tmp)
        (tmp / 'e.csv').parent.mkdir(exist_ok=True)
        sim_csv(tmp / 'e.csv', d, dates[2])
        text, rep, m = run(tmp, '--edges', str(tmp / 'e.csv'))
        q = m.set_index('site').quality
        assert q['s3'] == 'good'
        assert q['wrong_way'] == 'bad' and 'wrong_direction' in m.set_index('site').why['wrong_way']
        assert q['far'] == 'bad'
        assert q['two_way'] == 'bad' and 'no_direction_on_two_way_road' in m.set_index('site').why['two_way']
        assert rep['volume']['verdict'] == 'PASS', text
        assert rep['day_shape']['verdict'] == 'PASS', text
        assert rep['nothing_stuck']['verdict'] == 'PASS', text
        assert 'NOT TESTED' in text and 'Travel times' in text and 'validated' in text
        sim_csv(tmp / 'e.csv', d, dates[2], scale=.5)
        text, rep, _ = run(tmp, '--edges', str(tmp / 'e.csv'))
        assert rep['volume']['verdict'] == 'FAIL', text
        assert rep['day_shape']['verdict'] == 'PASS', text
        sim_csv(tmp / 'e.csv', d, dates[2], shift=2)
        text, rep, _ = run(tmp, '--edges', str(tmp / 'e.csv'))
        assert rep['day_shape']['verdict'] == 'FAIL', text
        assert 'shifted by' in text, text
        sim_csv(tmp / 'e.csv', d, dates[2], teleports=1)
        _, rep, _ = run(tmp, '--edges', str(tmp / 'e.csv'))
        assert rep['nothing_stuck']['verdict'] == 'FAIL'
        text, rep, _ = run(tmp, '--as-sim-day', dates[2])
        assert rep['volume']['verdict'] == 'PASS', text
    print('ok')


if __name__ == '__main__':
    main()
