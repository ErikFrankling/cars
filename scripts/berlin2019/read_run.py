#!/usr/bin/env python3
"""Turn one run into recipe step 2's exit test and the file the benchmark scores.

    read_run.py RUN_NAME [--demand FACTOR]

Writes runs/NAME/site_hour.csv (site, hour, flow, speed, long, lanes; all sites, integer flow and whole-km/h
speed like the source) and runs/NAME/exit.json. Prints only tuning sites: locked sites are not read here.
Sim clock: seconds from local midnight of a normal weekday.
"""
import argparse
import gzip
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import metrics


def planned_departures(path):
    out = {}
    with gzip.open(path, 'rt') as f:
        for line in f:
            m = re.search(r'<vehicle id="([^"]+)"[^>]* depart="([^"]+)"', line)
            if m:
                out[m[1]] = float(m[2])
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('name')
    p.add_argument('--routes')
    a = p.parse_args()
    run = B19 / 'runs' / a.name
    out = {'run': a.name, 'cmd': (run / 'cmd.txt').read_text().strip()}
    s = pd.read_csv(run / 'sensors.csv')
    s['hour'] = (s.begin // 3600).astype(int)
    g = s.assign(vs=s['count'] * s.speed).groupby(['site' if 'site' in s else 'sensor', 'hour']).agg(flow=('count', 'sum'), vs=('vs', 'sum'), long=('long', 'sum'), lanes=('lane', 'nunique')).reset_index().rename(columns={'sensor': 'site'})
    g['speed'] = (3.6 * g.vs / g.flow.where(g.flow > 0)).round()
    site_hour = g[['site', 'hour', 'flow', 'speed', 'long', 'lanes']]
    site_hour.to_csv(run / 'site_hour.csv', index=False)

    # exit test
    summ = pd.read_csv(run / 'summary.csv')
    last = summ.iloc[-1]
    routes = a.routes or re.search(r'--routes (\S+)', out['cmd'])[1]
    plan = planned_departures(routes)
    trips = pd.read_csv(run / 'trips.csv')
    done = set(trips.trip)
    n = len(plan)
    t_end = float(last.time)
    late = trips.depart - trips.trip.map(plan)
    stuck = dict(planned=n, finished=int(len(trips)), unfinished=int(n - len(trips)), unfinished_share=float(1 - len(trips) / n), run_end_s=t_end, running_at_end=int(last.running), peak_running=int(summ.running.max()), peak_running_time_h=float(summ.time[summ.running.idxmax()] / 3600), teleports=int(last.teleports), late_over_15min_share=float((late > 900).mean()), late_p95_s=float(late.quantile(.95)), never_inserted=int(n - int(last.inserted)), mean_trip_s=float(trips.duration.mean()), mean_wait_s=float(trips.waiting.mean()), mean_loss_s=float(trips.time_loss.mean()))
    out['nothing_stuck'] = stuck

    # persistent queues from the 15-minute edge file: speed under 30% of the limit with real load, an hour or more
    net = read_net(B19 / 'district/net.net.xml', B19 / 'district/net.pkl')
    e = pd.read_csv(run / 'edges.csv')
    e = e[e.samples > 0]
    limit = {k: car_lanes(v)[0]['speed'] for k, v in net['edges'].items() if car_lanes(v)}
    e['v'] = e.distance / e.samples
    e['limit'] = e.edge.map(limit)
    e = e.dropna(subset=['limit'])
    e['slow'] = (e.v < .3 * e['limit']) & (e.samples >= 300)
    rows = []
    for k, q in e[e.slow].groupby('edge'):
        b = np.sort(q.begin.values)
        groups = np.split(b, np.where(np.diff(b) != 900)[0] + 1)
        longest = max(groups, key=len)
        rows.append(dict(edge=k, name=net['edges'][k]['name'], type=net['edges'][k]['type'].replace('highway.', ''), slow_bins=len(b), longest_h=len(longest) * .25, start_h=float(longest[0] / 3600), end_h=float((longest[-1] + 900) / 3600), mean_v=float(q.v.mean()), limit=float(limit[k])))
    q = pd.DataFrame(rows)
    if len(q):
        q = q.sort_values('longest_h', ascending=False)
        q.to_csv(run / 'queues.csv', index=False)
    persistent = q[q.longest_h >= 1] if len(q) else q
    out['persistent_queues'] = dict(edges_over_1h=int(len(persistent)), edges_over_3h=int((q.longest_h >= 3).sum()) if len(q) else 0, edges_any=int(len(q)), worst=persistent.head(12).to_dict('records') if len(persistent) else [])
    day = e[e.begin < 86400].copy()
    day['hour'] = (day.begin // 3600).astype(int)
    day['type'] = day.edge.map(lambda k: net['edges'][k]['type'].replace('highway.', ''))
    v = day.groupby(['type', 'hour']).agg(d=('distance', 'sum'), t=('samples', 'sum'))
    v['kmh'] = 3.6 * v.d / v.t
    out['network_speed_by_class'] = {t: {int(h): round(float(x), 1) for h, x in g2.kmh.droplevel(0).items() if h in (3, 8, 12, 16, 19)} for t, g2 in v.groupby('type') if g2.d.sum() > 1e7}
    out['km_M_day'] = float(day.distance.sum() / 1e9)
    # score on tuning sites and tuning days only, one row per other day, same code as the floor
    freeze = json.load(open(B19 / 'step1/freeze.json'))
    real = pd.read_csv(B19 / 'step1/real_days.csv.gz')
    classes = dict(zip(*(lambda d: (d.site, d.road_class))(pd.read_csv(B19 / 'step0/sites.csv'))))
    tuning = set(freeze['tuning_sites'])
    c = site_hour[site_hour.site.isin(tuning) & (site_hour.hour < 24)][['site', 'hour', 'flow', 'speed']]
    scores = {}
    for d in freeze['tuning_days']:
        r = real[(real.date == d) & real.site.isin(tuning)][['site', 'hour', 'flow', 'speed']]
        scores[d] = metrics.score(c, r, classes)
    out['scores_tuning_sites'] = scores
    (run / 'exit.json').write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ('nothing_stuck', 'km_M_day')}, indent=1, default=float))
    print('persistent queue edges: over 1 h', out['persistent_queues']['edges_over_1h'], 'over 3 h', out['persistent_queues']['edges_over_3h'], 'any', out['persistent_queues']['edges_any'])
    if len(persistent):
        print(persistent.head(15).to_string())
    m = scores['2019-05-14']
    print('vs 14 May:', {k: round(m['volume_07_18'].get(k, float('nan')), 3) for k in ('rmsn', 'wape', 'r2', 'slope', 'bias', 'geh_lt5')}, 'day shape', {k: m.get('day_shape', {}).get(k) for k in ('mean_abs_share_points', 'peak_am_ref', 'peak_am_cand', 'peak_pm_ref', 'peak_pm_cand', 'total_ratio')})
    print('speed bias', m.get('speed_bias_kmh'), 'median abs', m.get('speed_site_median_abs_kmh'), 'jam', m['where_when'])
    print('network speed by class', out['network_speed_by_class'])


if __name__ == '__main__':
    main()
