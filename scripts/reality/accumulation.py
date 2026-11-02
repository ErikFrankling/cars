#!/usr/bin/env python3
"""real_accumulation.csv: cars on the road by hour. F043 on model vehicle-km, F046 from real counts and speeds only."""
import collections
import gzip
import re
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rcommon import *
from pyproj import Transformer

P = probes()
KEYS = [str(k) for k in P['keys']]
IDX = {k: i for i, k in enumerate(KEYS)}
MED, HM, VOL = P['med'], P['hm'], P['vol']
ND = B19 / 'district/m10'
nm = pickle.loads((ND / 'net.pkl').read_bytes())


def car(e):
    return [l for l in e['lanes'] if (not l['allow'] or {'passenger', 'all'} & set(l['allow'].split())) and 'passenger' not in l['disallow'].split()]


E = {k: e for k, e in nm['edges'].items() if car(e)}
names = list(E)
ei = {k: i for i, k in enumerate(names)}
M = len(names)
L = np.array([car(E[k])[0]['length'] for k in names]) / 1000
kind = np.array([E[k]['type'].replace('highway.', '') for k in names])
lim = np.array([car(E[k])[0]['speed'] * 3.6 for k in names])
mid = np.array([car(E[k])[0]['shape'].mean(axis=0) for k in names])
INBOX = (mid[:, 0] >= BOX[0]) & (mid[:, 0] < BOX[2]) & (mid[:, 1] >= BOX[1]) & (mid[:, 1] < BOX[3])
C = np.select([np.char.startswith(kind, 'motorway') | np.char.startswith(kind, 'trunk'), np.char.startswith(kind, 'primary') | np.char.startswith(kind, 'secondary')], ['motorway', 'arterial'], 'local')
MAINROAD = C != 'local'


def base_id(k):
    return k if k in IDX else k.split('+')[0] if k.split('+')[0] in IDX else None


pi = np.array([IDX.get(base_id(k), -1) if base_id(k) else -1 for k in names])
print('m10 edges', M, 'with probes', int((pi >= 0).sum()), flush=True)


def hourly(arr):
    """edge, day, hour: volume-weighted speed. NaN where no data."""
    out = np.full((M, len(DAYS), 24), np.nan)
    ok = pi >= 0
    a, v = arr[pi[ok]], VOL[pi[ok]]
    good = np.isfinite(a) & (v > 0)
    x = (np.where(good, a * v, 0).reshape(a.shape[0], a.shape[1], 24, 4)).sum(axis=3)
    w = (np.where(good, v, 0).reshape(a.shape[0], a.shape[1], 24, 4)).sum(axis=3)
    with np.errstate(invalid='ignore', divide='ignore'):
        out[ok] = np.where(w > 0, x / w, np.nan)
    return out, ok, w


def fill(sp):
    """Edge with no value: class speed in that hour, same day; class speeds harmonic over edges by length."""
    res = sp.copy()
    cl = {}
    for c in ('motorway', 'arterial', 'local'):
        m = C == c
        with np.errstate(invalid='ignore'):
            cl[c] = np.nansum(L[m, None, None] * np.isfinite(sp[m]), axis=0) / np.nansum(L[m, None, None] * np.isfinite(sp[m]) / sp[m], axis=0)
        res[m] = np.where(np.isfinite(sp[m]), sp[m], cl[c][None])
    return res, cl


med_h, ok, _ = hourly(MED)
hm_h, _, _ = hourly(HM)
med_f, cl_med = fill(med_h)
hm_f, cl_hm = fill(hm_h)
hm_mean = np.nanmean(hm_f, axis=1)
med_mean = np.nanmean(med_f, axis=1)

cache = Path('/tmp/rung1/qeh.npy')
if cache.exists():
    q = np.load(cache)
else:
    tt = (L[:, None] / hm_mean * 3600)
    tt = np.where(np.isfinite(tt), tt, 30)
    ttl = tt.tolist()
    q = [[0] * 30 for _ in range(M)]
    n = 0
    with gzip.open(ND / 'routes_f10.rou.gz', 'rt') as f:
        pat = re.compile(r'depart="([^"]+)".*?edges="([^"]+)"')
        pat2 = re.compile(r'edges="([^"]+)"')
        dep = None
        for line in f:
            if '<vehicle' in line:
                m = re.search(r'depart="([^"]+)"', line)
                dep = float(m[1]) if m else dep
            m = pat2.search(line)
            if m and dep is not None:
                t = dep
                for k in m[1].split():
                    i = ei.get(k)
                    if i is None:
                        t += 5
                        continue
                    h = int(t // 3600)
                    if h >= 30:
                        break
                    q[i][h] += 1
                    t += ttl[i][h % 24]
                n += 1
    q = np.array(q)
    np.save(cache, q)
    print('vehicles', n, flush=True)
q24 = q[:, :24].astype(float)
q24[:, :6] += q[:, 24:30]
print('veh-km day cut', (q24 * L[:, None]).sum() / 1e6, 'box', (q24[INBOX] * L[INBOX, None]).sum() / 1e6, flush=True)

# ratio of real counts to model at tuning sites, by class and hour
sens = pd.read_csv(ND / 'sensors.csv', header=None, names=['site', 'lane', 'pos'])
sens['edge'] = sens.lane.str.rsplit('_', n=1).str[0]
se = sens.drop_duplicates('site').set_index('site').edge
s = sites()
d = loops()
d = d[d.site.isin(DISTRICT_TUNING)]
real = d.groupby(['site', 'hour']).flow.mean().unstack('hour').reindex(columns=range(24))
real_days = d.pivot_table(index=['site', 'date'], columns='hour', values='flow')
classes = s.set_index('site').road_class
rat = {}
for c, kinds in (('arterial', ('primary', 'secondary')), ('local', ('tertiary',))):
    st = [x for x in real.index if classes[x] in kinds and x in se.index and se[x] in ei]
    mod = np.array([q24[ei[se[x]]] for x in st])
    rr = real.loc[st].to_numpy()
    rat[c] = np.nansum(rr, axis=0) / mod.sum(axis=0)
    print(c, 'sites', len(st), 'real/model by hour', np.round(rat[c], 2).tolist(), 'day', round(float(np.nansum(rr) / mod.sum()), 3), flush=True)
rat['motorway'] = np.ones(24)
scale = np.ones((M, 24))
for c in ('motorway', 'arterial', 'local'):
    scale[C == c] = rat[c]

# hand calculation, as forecast: class speeds from floor.json
fl = json.load(open(B19 / 'probes/floor.json'))
HAND = {c: {int(h): v for h, v in fl[c]['real_kmh_by_hour'].items()} for c in fl}
HAND_ROUND = {'arterial': {7: 32, 8: 28}, 'motorway': {7: 56, 8: 47}, 'local': {7: 28, 8: 25}}
rows = []


def record(var, net_, label, f):
    for h in range(24):
        vals = f(h)
        if not np.isfinite(np.sum(vals)):
            continue
        rows.append(dict(variant=var, network=net_, input_label=label, hour=h, cars=round(float(np.mean(vals))), cars_day_min=round(float(np.min(vals))), cars_day_max=round(float(np.max(vals)))))


for net_, mask in (('cut_all', np.ones(M, bool)), ('box_all', INBOX), ('box_main', INBOX & MAINROAD), ('box_main_no_motorway', INBOX & (C == 'arterial'))):
    Lm, qm, Cm = L[mask], q24[mask], C[mask]
    def a(h):
        tot = 0
        for c in ('motorway', 'arterial', 'local'):
            v = HAND_ROUND[c][h] if h in (7, 8) else HAND[c].get(h, np.nan)
            if np.isnan(v):
                return [np.nan]
            tot += (qm[Cm == c, h] * Lm[Cm == c]).sum() / v
        return [tot]
    def var(sp, sc):
        return lambda h: [(qm[:, h] * sc[mask, h] * Lm / sp[mask, dd, h]).sum() for dd in range(len(DAYS))]
    record('a_hand_class_speeds', net_, 'model veh-km; probe class speed', a)
    record('b_edge_v_med', net_, 'model veh-km; probe edge speed median over cells', var(med_f, np.ones((M, 24))))
    record('c_edge_v_hm', net_, 'model veh-km; probe edge speed harmonic over cells', var(hm_f, np.ones((M, 24))))
    record('d_edge_v_hm_scaled_to_counts', net_, 'model veh-km scaled by class and hour to tuning loops; probe speed', var(hm_f, scale))

# F046 (e): SVZ official veh-km in the box, real hourly share from tuning loops, speed on the same roads
svz_km = json.load(open(ND / 'static.json'))['svz_count_network_in_box_M'] * 1e6
sh_days = real_days.div(real_days.sum(axis=1), axis=0)
share = sh_days.groupby('date').median().pipe(lambda x: x.div(x.sum(axis=1), axis=0))
main = INBOX & MAINROAD
for label, sp in (('v_med', med_f), ('v_hm', hm_f)):
    def e(h):
        out = []
        for dd, day in enumerate(DAYS):
            if day not in share.index:
                continue
            v = (L[main] * q24[main].sum(axis=1)).sum() / ((L[main] * q24[main].sum(axis=1)) / sp[main, dd, h]).sum()
            out.append(svz_km * share.loc[day, h] / v)
        return out
    record(f'e_svz_{label}', 'box_main', 'SVZ 2019 veh-km measured or official; loop hourly share; probe speed, weighted by route km over edges (model weights only here)', e)

# F046 (f): Edie per road-km: k=q/v at tuning sites by OSM class, times directed road-km per class in the box. No MATSim.
# Directed km per class counts one direction of carriageway per edge.
sites_e = [x for x in real.index if x in se.index and se[x] in ei]
for label, sp in (('v_hm', hm_f), ('v_med', med_f), ('loop', None)):
    def f(h):
        out = []
        for dd, day in enumerate(DAYS):
            ks = collections.defaultdict(list)
            for x in sites_e:
                z = d[(d.site == x) & (d.date == day) & (d.hour == h)]
                if z.empty or not np.isfinite(z.flow.iloc[0]):
                    continue
                qv = z.flow.iloc[0]
                v = sp[ei[se[x]], dd, h] if sp is not None else z.speed.iloc[0]
                if np.isfinite(v) and v > 0:
                    ks[classes[x]].append(qv / v)
            tot = 0
            for c, vals in ks.items():
                km = L[INBOX & np.char.startswith(kind, c)].sum()
                tot += np.mean(vals) * km
            out.append(tot)
        return out
    record(f'f_edie_sites_{label}', 'box_main_no_motorway', 'loop q/v at tuning sites times directed road-km per class; no MATSim', f)
t = pd.DataFrame(rows)
t.to_csv(OUT / 'real_accumulation.csv', index=False)
print({c: round(float(L[INBOX & (C == c)].sum())) for c in ('motorway', 'arterial', 'local')}, 'directed km in box')
print('vkm day box', {c: round((q24[INBOX & (C == c)] * L[INBOX & (C == c), None]).sum() / 1e6, 3) for c in ('motorway', 'arterial', 'local')}, 'cut', {c: round((q24[C == c] * L[C == c, None]).sum() / 1e6, 3) for c in ('motorway', 'arterial', 'local')})
print('vkm/h cut 7 8', [round((q24[:, h] * L).sum()) for h in (7, 8)], 'box main', [round((q24[INBOX & MAINROAD, h] * L[INBOX & MAINROAD]).sum()) for h in (7, 8, 16)], 'svz', [round(svz_km * share[h].mean()) for h in (7, 8, 16)])
