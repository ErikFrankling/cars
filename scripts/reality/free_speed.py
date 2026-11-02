#!/usr/bin/env python3
"""real_free_speed.csv: free speed by road class from night and early morning, probes closed against loops."""
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rcommon import *

P = probes()
KEYS = [str(k) for k in P['keys']]
IDX = {k: i for i, k in enumerate(KEYS)}
MED, HM, VOL, FREE = P['med'], P['hm'], P['vol'], P['free']
N = net()
E = len(KEYS)
kind = np.array([N['edges'][k]['type'].replace('highway.', '') for k in KEYS])
mid = np.array([np.mean([l['shape'].mean(axis=0) for l in N['edges'][k]['lanes']], axis=0) for k in KEYS])
limit = np.array([max(l['speed'] for l in N['edges'][k]['lanes']) * 3.6 for k in KEYS])
length = np.array([N['edges'][k]['lanes'][0]['length'] for k in KEYS])
box = (mid[:, 0] >= BOX[0]) & (mid[:, 0] < BOX[2]) & (mid[:, 1] >= BOX[1]) & (mid[:, 1] < BOX[3])
SIM = {'motorway': 68, 'arterial': 34, 'local': 28}
C3 = {'motorway': ('motorway', 'motorway_link', 'trunk', 'trunk_link'), 'arterial': ('primary', 'primary_link', 'secondary', 'secondary_link'), 'local': ('tertiary', 'tertiary_link', 'residential', 'unclassified', 'living_street')}
BANDS = {'night_01_05': range(1, 5), 'early_05_06': [5], 'hour_06_07': [6], 'peak_08_09': [8]}


def stat(mask, hours):
    ids = np.where(mask)[0]
    q = [h * 4 + i for h in hours for i in range(4)]
    m, H, v = MED[ids][:, :, q], HM[ids][:, :, q], VOL[ids][:, :, q]
    ok = np.isfinite(m) & (v > 0)
    w = v[ok]
    day = [np.average(m[:, d][ok[:, d]], weights=v[:, d][ok[:, d]]) for d in range(m.shape[1])]
    dayh = [np.average(H[:, d][ok[:, d]], weights=v[:, d][ok[:, d]]) for d in range(m.shape[1])]
    e_mean = np.nanmean(np.where(ok, m, np.nan), axis=(1, 2))
    trust = ok & (v >= 5)
    lw = np.repeat(length[ids][:, None], m.shape[1] * m.shape[2], axis=1).reshape(ok.shape)
    return dict(edges=len(ids), edges_with_data=int(ok.any(axis=(1, 2)).sum()), intervals=int(ok.sum()), probe_volume_per_edge_interval=round(float(w.mean()), 1), v_med_volume_weighted=round(float(np.average(m[ok], weights=w)), 1), v_med_day_min=round(min(day), 1), v_med_day_max=round(max(day), 1), v_hm_volume_weighted=round(float(np.average(H[ok], weights=w)), 1), v_hm_day_min=round(min(dayh), 1), v_hm_day_max=round(max(dayh), 1), v_med_unweighted_edges=round(float(np.nanmean(e_mean)), 1), v_med_volume_ge5=round(float(np.average(m[trust], weights=v[trust])), 1) if trust.any() else np.nan, v_med_harmonic_vkm=round(float(lw[ok].sum() / (lw[ok] / m[ok]).sum()), 1), v_free_p90_median=round(float(np.median(FREE[ids])), 1), limit_median=round(float(np.median(limit[ids])), 1))


rows = []
for scope, sc in (('district', box), ('berlin_main', np.ones(E, bool))):
    for c3, kinds in C3.items():
        mask = sc & np.isin(kind, kinds)
        if not mask.any():
            continue
        for band, hours in BANDS.items():
            rows.append(dict(scope=scope, road_class=c3, level='class3', band=band, sim_10pct_kmh=SIM[c3] if scope == 'district' else np.nan, **stat(mask, hours)))
        for k in kinds:
            mk = sc & (kind == k)
            if mk.sum() >= 5:
                for band in ('night_01_05', 'early_05_06'):
                    rows.append(dict(scope=scope, road_class=k, level='osm', band=band, **stat(mk, BANDS[band])))
t = pd.DataFrame(rows)

# closure on the sites' own edges
s = sites()
l = pd.concat([loops(), unsplit_loops()], ignore_index=True)
s['ei'] = s.edge.map(IDX)
rec = []
for x in s.dropna(subset=['ei']).itertuples():
    i = int(x.ei)
    g = l[l.site == x.site]
    for r in g.itertuples():
        d = DAYS.index(r.date)
        q = slice(r.hour * 4, r.hour * 4 + 4)
        m, H, v = MED[i, d, q], HM[i, d, q], VOL[i, d, q]
        ok = np.isfinite(m) & (v > 0)
        if ok.sum() and np.isfinite(r.speed):
            rec.append((x.site, x.scope, x.road_class, r.date, r.hour, r.speed, r.flow, np.average(m[ok], weights=v[ok]), np.average(H[ok], weights=v[ok]), v[ok].sum()))
j = pd.DataFrame(rec, columns=['site', 'scope', 'cls', 'date', 'hour', 'loop', 'flow', 'vmed', 'vhm', 'vol'])
j['band'] = np.select([j.hour.between(1, 4), j.hour == 5, j.hour == 6, j.hour.isin([7, 8, 15, 16])], ['night_01_05', 'early_05_06', 'hour_06_07', 'peak'], 'other')
cl = []
for (c, b), g in j.groupby(['cls', 'band']):
    site = g.groupby('site').agg(loop=('loop', 'mean'), vmed=('vmed', 'mean'), vhm=('vhm', 'mean'))
    cl.append(dict(scope='closure_at_sites', road_class=c, level='closure', band=b, sites=len(site), loop_kmh=round(g.loop.mean(), 1), probe_v_med_kmh=round(g.vmed.mean(), 1), probe_v_hm_kmh=round(g.vhm.mean(), 1), ratio_loop_over_med_median=round(float((site.loop / site.vmed).median()), 3), ratio_loop_over_med_p10=round(float((site.loop / site.vmed).quantile(.1)), 3), ratio_loop_over_med_p90=round(float((site.loop / site.vmed).quantile(.9)), 3), ratio_loop_over_hm_median=round(float((site.loop / site.vhm).median()), 3), corr_hourly=round(float(g.loop.corr(g.vmed)), 2)))
t = pd.concat([t, pd.DataFrame(cl)], ignore_index=True)
t.to_csv(OUT / 'real_free_speed.csv', index=False)
pd.set_option('display.width', 250)
print(t[(t.level == 'class3') & (t.scope == 'district')][['road_class', 'band', 'edges_with_data', 'probe_volume_per_edge_interval', 'v_med_volume_weighted', 'v_med_day_min', 'v_med_day_max', 'v_hm_volume_weighted', 'v_med_unweighted_edges', 'v_med_volume_ge5', 'v_med_harmonic_vkm', 'v_free_p90_median', 'limit_median', 'sim_10pct_kmh']].to_string())
print(t[(t.level == 'class3') & (t.scope != 'district')][['road_class', 'band', 'edges_with_data', 'v_med_volume_weighted', 'v_hm_volume_weighted', 'limit_median']].to_string())
print(t[t.level == 'osm'][t.scope == 'district'][['road_class', 'band', 'edges', 'v_med_volume_weighted', 'v_hm_volume_weighted', 'v_med_volume_ge5', 'limit_median', 'probe_volume_per_edge_interval']].to_string())
print(pd.DataFrame(cl)[['road_class', 'band', 'sites', 'loop_kmh', 'probe_v_med_kmh', 'probe_v_hm_kmh', 'ratio_loop_over_med_median', 'ratio_loop_over_med_p10', 'ratio_loop_over_med_p90', 'ratio_loop_over_hm_median', 'corr_hourly']].to_string())
