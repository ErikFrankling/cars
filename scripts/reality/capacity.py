#!/usr/bin/env python3
"""real_capacity.csv: highest flow per lane per site, queue hours apart, graded by how sure the queue was present."""
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rcommon import *

P = probes()
IDX = {str(k): i for i, k in enumerate(P['keys'])}
MED, VOL, FREE = P['med'], P['vol'], P['free']
s = sites().set_index('site')
l = pd.concat([loops(), unsplit_loops()], ignore_index=True)
assert not set(l.site) & LOCKED
fr = site_free(l)
det = detectors(l)
nd = det[det.q > 0].groupby(['site', 'date', 'hour']).agg(nd=('det', 'nunique'), top_lane=('q', 'max')).reset_index()
x = l.merge(nd, on=['site', 'date', 'hour'], how='inner')
x['per_lane'] = x.flow / x.nd
x['free'] = x.site.map(fr)
x['r'] = x.speed / x.free


def probe_low(site, date, hour):
    i = IDX.get(str(s.loc[site].edge))
    if i is None:
        return np.nan
    w = MED[i, DAYS.index(date), hour * 4:hour * 4 + 4]
    if not np.isfinite(w).any():
        return np.nan
    with np.errstate(invalid='ignore'):
        return int((w < FREE[i] / 2).sum())


x['probe_low'] = [probe_low(a, b, c) for a, b, c in zip(x.site, x.date, x.hour)]
x['queue'] = (x.r < JAM_FRACTION) & (x.flow >= 50)


def grade(r):
    if not (r.r < JAM_FRACTION and r.flow >= 50):
        return 'none'
    if r.r < .5 and r.probe_low >= 2:
        return 'A'
    if r.probe_low >= 1:
        return 'B'
    return 'C'


x['grade'] = [grade(r) for r in x.itertuples()]
net_ = net()
J = net_['junctions']
rows = []
for site, g in x.groupby('site'):
    m = s.loc[site]
    e = net_['edges'].get(m.edge)
    end_j = J.get(e['end'], ('', 0, 0))[0] if e else ''
    to_end = (m.edge_len - m.pos_m) if pd.notna(m.pos_m) else np.nan
    q = g[g.queue]
    f = g[~g.queue]
    row = dict(site=site, scope=m.scope, street=m.street, road_class=m.road_class, position=m.position, lanes_on_map=m.car_lanes, detectors=m.n_det, covers_all=m.covers_all, free_kmh=g.free.iloc[0], days=g.date.nunique(), edge=m.edge, edge_end_junction=end_j, loop_to_edge_end_m=round(to_end) if pd.notna(to_end) else np.nan)
    for name, z in (('queue', q), ('free', f)):
        if len(z):
            b = z.loc[z.per_lane.idxmax()]
            row.update({f'{name}_max_per_lane': round(b.per_lane), f'{name}_max_date': b.date, f'{name}_max_hour': int(b.hour), f'{name}_max_speed': b.speed, f'{name}_p95_per_lane': round(z.per_lane.quantile(.95)), f'{name}_hours': len(z)})
            if name == 'queue':
                row['queue_max_grade'] = b.grade
        else:
            row.update({f'{name}_hours': 0})
    for gr in 'AB':
        z = q[q.grade == gr]
        row[f'queue_hours_grade_{gr}'] = len(z)
        row[f'queue_max_per_lane_grade_{gr}'] = round(z.per_lane.max()) if len(z) else np.nan
    # day-to-day spread of the daily maximum, in whatever state
    row['daily_max_median'] = round(g.groupby('date').per_lane.max().median())
    row['daily_max_min'] = round(g.groupby('date').per_lane.max().min())
    row['top_single_lane'] = g.top_lane.max()
    z = q[q.grade.isin(list('AB'))]
    row['measures_capacity'] = 'yes' if len(z) >= 3 and z.date.nunique() >= 2 else 'weak' if len(q) else 'no'
    rows.append(row)
t = pd.DataFrame(rows)
# Hamburg main-phase share for the bound on s
sig = pd.read_csv(OUT / 'real_signals.csv')
sig = sig[(sig.city == 'Hamburg') & (sig.day_type == 'weekday') & sig.hour.between(7, 18)]
g50, g10, g90 = sig.longest_green_per_light_p50.median(), sig.longest_green_per_light_p10.median(), sig.longest_green_per_light_p90.median()
near = (t.edge_end_junction == 'traffic_light') & (t.loop_to_edge_end_m <= 300)
t['near_signal'] = near
best = t[['queue_max_per_lane', 'free_max_per_lane']].max(axis=1)
t['s_bound_at_g50'] = np.where(near, (best / g50).round(), np.nan)
t['s_bound_at_g90'] = np.where(near, (best / g90).round(), np.nan)
t.to_csv(OUT / 'real_capacity.csv', index=False)
x[['site', 'date', 'hour', 'flow', 'speed', 'free', 'r', 'nd', 'per_lane', 'top_lane', 'probe_low', 'queue', 'grade']].to_pickle('/tmp/rung1/cap_hours.pkl')
print('g/C', g10, g50, g90, len(t), t.scope.value_counts().to_dict())
print(x.grade.value_counts().to_dict())
print(t.measures_capacity.value_counts().to_dict())
print(t.groupby('road_class')[['queue_max_per_lane', 'free_max_per_lane', 'top_single_lane']].describe().T.round().to_string()[:1800])
y = t[t.scope != 'unsplit']
for name, z in (('near signal', y[y.near_signal]), ('near, measures', y[y.near_signal & (y.measures_capacity == 'yes')]), ('not near', y[~y.near_signal])):
    b = z[['queue_max_per_lane', 'free_max_per_lane']].max(axis=1)
    print(name, len(z), 'best p50', b.median(), 'p90', b.quantile(.9), 'max', b.max(), 'top lane p50', z.top_single_lane.median(), 'p90', z.top_single_lane.quantile(.9), 'max', z.top_single_lane.max(), 'queue max p50', z.queue_max_per_lane.median(), 'p90', z.queue_max_per_lane.quantile(.9))
    print('   share over 1640*g50', (b > 1640 * g50).mean(), ' over 1900*g50', (b > 1900 * g50).mean(), ' s bound p90', (b / g50).quantile(.9), 'top lane bound p90', (z.top_single_lane / g50).quantile(.9), 'share top lane over 1640*g90', (z.top_single_lane > 1640 * g90).mean())
print(y[y.near_signal].sort_values('top_single_lane').tail(12)[['site', 'street', 'road_class', 'detectors', 'lanes_on_map', 'free_kmh', 'loop_to_edge_end_m', 'queue_max_per_lane', 'queue_max_grade', 'free_max_per_lane', 'top_single_lane', 'measures_capacity']].to_string())
print(t[t.scope == 'unsplit'].T.to_string()[:800])
print('share of top-flow hour with queue, near signal', (y[y.near_signal].queue_max_per_lane >= y[y.near_signal].free_max_per_lane).mean())
print(x[x.site != 'TE002'].groupby('grade').per_lane.describe().round().to_string())
