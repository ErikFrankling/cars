#!/usr/bin/env python3
"""What the sim can pass at the real sites: a jammed run's largest hourly flow per site against the most the real site passed that week.
site_capacity.py RUN [--hours A,B]. Tuning sites only. A site under the real value while cars queue behind it is a capacity fault with a place on the map."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

run = sys.argv[1]
d = B19 / 'runs' / run
tuning = set(json.load(open(B19 / 'step1/freeze.json'))['tuning_sites'])
real = pd.read_csv(B19 / 'step1/real_days.csv.gz')
real = real[real.site.isin(tuning)]
s = pd.read_csv(d / 'sensors.csv')
s['hour'] = (s.begin // 3600).astype(int)
s['vs'] = s['count'] * s.speed
g = s[s.sensor.isin(tuning)].groupby(['sensor', 'hour']).agg(q=('count', 'sum'), vs=('vs', 'sum')).reset_index().rename(columns={'sensor': 'site'})
g['v'] = 3.6 * g.vs / g.q.where(g.q > 0)
sim = g.groupby('site').agg(sim_max=('q', 'max'), sim_vmin=('v', 'min'))
rm = real.groupby('site').flow.max().rename('real_max')
rv = real.groupby('site').speed.min().rename('real_vmin')
t = pd.concat([sim, rm, rv], axis=1).dropna()
t['ratio'] = t.sim_max / t.real_max
sites = pd.read_csv(B19 / 'step0/sites.csv').set_index('site')
t = t.join(sites[['street', 'road_class', 'car_lanes']])
t['congested'] = t.sim_vmin < 15
print('sites', len(t), 'sum sim max / real max', round(t.sim_max.sum() / t.real_max.sum(), 3), 'median', round(t.ratio.median(), 2))
print('congested in the sim (lowest hour under 15 km/h):', int(t.congested.sum()), ' of those, under 80% of the real maximum:', int((t.congested & (t.ratio < .8)).sum()))
print(t[t.congested].sort_values('ratio').head(14)[['street', 'road_class', 'car_lanes', 'real_max', 'sim_max', 'ratio', 'sim_vmin', 'real_vmin']].round(2).to_string())
t.to_csv(d / 'site_capacity.csv')
