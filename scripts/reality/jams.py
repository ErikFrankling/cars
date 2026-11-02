#!/usr/bin/env python3
"""real_jams.csv, its noise, and the jam clusters. Definitions in foundations/R-reality-table.md."""
import collections
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rcommon import *

MINVOL = 5
PERIODS = {'am': (20, 44), 'pm': (48, 84)}
P = probes()
KEYS = [str(k) for k in P['keys']]
IDX = {k: i for i, k in enumerate(KEYS)}
MED, VOL, FREE = P['med'], P['vol'], P['free']
E, D, Q = MED.shape
N = net()
EDGES = N['edges']


def edge_info():
    start, end, length, kind, name, lanes, mid = [None] * E, [None] * E, np.zeros(E), [''] * E, [''] * E, np.zeros(E, int), np.zeros((E, 2))
    for i, k in enumerate(KEYS):
        e = EDGES[k]
        cl = [l for l in e['lanes'] if (not l['allow'] or {'passenger', 'all'} & set(l['allow'].split())) and 'passenger' not in l['disallow'].split()] or e['lanes']
        start[i], end[i], length[i], kind[i], name[i], lanes[i] = e['start'], e['end'], cl[0]['length'], e['type'].replace('highway.', ''), e['name'], len(cl)
        mid[i] = cl[len(cl) // 2]['shape'].mean(axis=0)
    return start, end, length, kind, name, lanes, mid


START, END, LEN, KIND, NAME, LANES, MID = edge_info()
INBOX = (MID[:, 0] >= BOX[0]) & (MID[:, 0] < BOX[2]) & (MID[:, 1] >= BOX[1]) & (MID[:, 1] < BOX[3])
OUTS = collections.defaultdict(list)
INS = collections.defaultdict(list)
for i in range(E):
    OUTS[START[i]].append(i)
    INS[END[i]].append(i)
SUCC = [[j for j in OUTS[END[i]] if END[j] != START[i]] for i in range(E)]
ALL_OUT, ALL_IN = collections.defaultdict(list), collections.defaultdict(list)
for k, e in EDGES.items():
    ALL_OUT[e['start']].append(k)
    ALL_IN[e['end']].append(k)


MAIN = np.array([k.startswith(('motorway', 'trunk', 'primary', 'secondary', 'tertiary')) for k in KIND])
MW = np.array([k.startswith(('motorway', 'trunk')) for k in KIND])
LIMIT = np.array([max(l['speed'] for l in EDGES[k]['lanes']) * 3.6 for k in KEYS])


def road_class3(t):
    if t.startswith(('motorway', 'trunk')):
        return 'motorway'
    if t.startswith(('primary', 'secondary')):
        return 'arterial'
    return 'local'


def jam_mask(frac):
    with np.errstate(invalid='ignore'):
        return (MED < FREE[:, None, None] * frac) & (VOL >= MINVOL)


def episodes(j):
    """Keep runs of 2 or more intervals."""
    a = j[:, :, :-1] & j[:, :, 1:]
    k = np.zeros_like(j)
    k[:, :, :-1] |= a
    k[:, :, 1:] |= a
    return k


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def places(ep, days, min_days):
    """Recurring edges by period, joined when adjacent and overlapping in time on some day. Returns a list of dicts."""
    out = []
    dd = list(days)
    for per, (q0, q1) in PERIODS.items():
        w = ep[:, dd, q0:q1]
        count = w.any(axis=2).sum(axis=1)
        rec = np.where(count >= min_days)[0]
        s = set(rec.tolist())
        u = UF()
        for i in rec:
            u.find(int(i))
            for j in SUCC[i]:
                if j in s and MAIN[i] == MAIN[j] and MW[i] == MW[j] and (w[i] & w[j]).any():
                    u.union(int(i), j)
        comps = collections.defaultdict(list)
        for i in rec:
            comps[u.find(int(i))].append(int(i))
        for members in comps.values():
            out.append(dict(period=per, q0=q0, edges=members))
    return out


def describe(pl, ep, threshold):
    m = pl['edges']
    q0 = pl['q0']
    per = pl['period']
    q1 = PERIODS[per][1]
    w = ep[m][:, :, q0:q1]
    any_t = w.any(axis=0)
    dayhit = any_t.any(axis=1)
    starts = [q0 + int(np.argmax(any_t[d])) for d in range(D) if dayhit[d]]
    ends = [q0 + int(any_t.shape[1] - np.argmax(any_t[d][::-1])) for d in range(D) if dayhit[d]]
    dd = w.any(axis=2).sum(axis=1)
    mset = set(m)
    downstream_free = [i for i in m if not any(j in mset for j in SUCC[i])]
    head = max(downstream_free or m, key=lambda i: (dd[m.index(i)], LEN[i]))
    junc = N['junctions'].get(END[head], ('', 0, 0))
    per_day_len = [LEN[np.array(m)[w[:, d].any(axis=1)]].sum() / 1000 for d in range(D) if dayhit[d]]
    with np.errstate(invalid='ignore'):
        r = MED[m][:, :, q0:q1] / FREE[m][:, None, None]
    # cause only where the map plainly shows it
    cause = ''
    outs = [k for k in ALL_OUT[END[head]] if EDGES[k]['end'] != START[head]]
    in_kinds = [EDGES[k]['type'].replace('highway.', '') for k in ALL_IN[END[head]]]
    out_lanes = [len(EDGES[k]['lanes']) for k in outs]
    if len(outs) == 1 and out_lanes[0] < LANES[head] and len(ALL_IN[END[head]]) == 1:
        cause = f'lane drop {LANES[head]} to {out_lanes[0]}'
    elif KIND[head].startswith('motorway') and len(ALL_IN[END[head]]) >= 2 and any('link' in t for t in in_kinds):
        cause = 'motorway merge'
    elif KIND[head].startswith('motorway') and len(outs) >= 2:
        cause = 'motorway diverge'
    names = [NAME[i] for i in m if NAME[i]]
    hj = ep[head]
    hd = hj[:, q0:q1]
    hs = [q0 + int(np.argmax(hd[d])) for d in range(D) if hd[d].any()]
    he = [q0 + int(hd.shape[1] - np.argmax(hd[d][::-1])) for d in range(D) if hd[d].any()]
    day_share = float(np.median(hj[:, 28:76].mean(axis=1)))
    with np.errstate(invalid='ignore'):
        head_low = float(np.nanmedian(MED[head][hj]))
    med_len = float(np.median(per_day_len))
    vol_med = int(np.median(VOL[m][:, :, q0:q1]))
    tier = 'C_local_unverified' if not MAIN[head] else 'A' if (dayhit.sum() >= 4 and med_len >= .2 and vol_med >= 10) else 'B'
    return dict(source='probe', threshold=threshold, period=per, place=' / '.join(x for x, _ in collections.Counter(names).most_common(3)), head_edge=KEYS[head], road_class=KIND[head], class3=road_class3(KIND[head]), in_district=bool(INBOX[head]), x=round(MID[head, 0]), y=round(MID[head, 1]), days_of_8=int(dayhit.sum()), start_median=fmt(np.median(starts)), start_min=fmt(min(starts)), start_max=fmt(max(starts)), end_median=fmt(np.median(ends)), end_min=fmt(min(ends)), end_max=fmt(max(ends)), edges=len(m), extent_km_2plus_days=round(float(LEN[m].sum()) / 1000, 2), extent_km_median_day=round(float(np.median(per_day_len)), 2), min_ratio_median=round(float(np.nanmedian(np.nanmin(r, axis=(0, 2)))), 2), probe_volume_median=int(np.median(VOL[m][:, :, q0:q1])), head_junction=junc[0], head_lanes=int(LANES[head]), cause=cause, tier=tier, head_start_median=fmt(np.median(hs)) if hs else '', head_end_median=fmt(np.median(he)) if he else '', head_share_of_07_19_jam=round(day_share, 2), pattern='all_day' if day_share >= .5 else 'peak', head_jam_kmh=round(head_low, 1), head_free_kmh=round(float(FREE[head]), 1), head_limit_kmh=round(float(LIMIT[head])), flag_parallel_road=bool(not MW[head] and FREE[head] > 1.4 * LIMIT[head]))


def fmt(q):
    return f'{int(q // 4):02d}:{int(round((q % 4) * 15)):02d}'


def noise(ep, threshold, group):
    rows = []
    box = np.where(INBOX & (MAIN if group == 'main' else ~MAIN))[0]
    pairs = []
    for per, (q0, q1) in PERIODS.items():
        w = ep[box][:, :, q0:q1]
        eany = w.any(axis=2)
        for a in range(D):
            for b in range(a + 1, D):
                inter = (eany[:, a] & eany[:, b]).sum()
                union = (eany[:, a] | eany[:, b]).sum()
                ah = w[:, a].sum()
                hh = (w[:, a] & w[:, b]).sum()
                # edge-intervals jam at both, within plus or minus one interval
                pairs.append(dict(group=group, threshold=threshold, period=per, a=DAYS[a], b=DAYS[b], jaccard_edges=inter / max(union, 1), a_edge_hours_also_b=hh / max(ah, 1), edges_a=int(eany[:, a].sum()), edges_b=int(eany[:, b].sum()), top20=_top(w, a, b)))
    return pd.DataFrame(pairs)


def _top(w, a, b):
    sa, sb = w[:, a].sum(axis=1), w[:, b].sum(axis=1)
    ta, tb = np.argsort(-sa)[:20], np.argsort(-sb)[:20]
    return len(set(ta.tolist()) & set(tb.tolist())) / 20


def tier_a(ps, ep, days, need):
    out = []
    for p in ps:
        m = p['edges']
        if not MAIN[m[0]] or not INBOX[m].any():
            continue
        q0, q1 = p['q0'], PERIODS[p['period']][1]
        w = ep[m][:, days][:, :, q0:q1]
        hit = w.any(axis=(0, 2))
        if hit.sum() < need:
            continue
        ln = [LEN[np.array(m)[w[:, d].any(axis=1)]].sum() / 1000 for d in range(len(days)) if hit[d]]
        if np.median(ln) >= .2 and np.median(VOL[m][:, :, q0:q1]) >= 10:
            out.append(p)
    return out


def split_half(ep):
    A, B = [0, 2, 4, 6], [1, 3, 5, 7]
    res = {}
    for label, x, y in (('even_vs_odd', A, B), ('odd_vs_even', B, A)):
        pa = tier_a(places(ep, x, 2), ep, x, 2)
        pb = tier_a(places(ep, y, 2), ep, y, 2)
        ea = [set(p['edges']) for p in pa]
        eb = [set(p['edges']) for p in pb]
        ub = set().union(*eb) if eb else set()
        ua = set().union(*ea) if ea else set()
        res[label] = dict(places_a=len(ea), places_b=len(eb), a_found_in_b=float(np.mean([bool(s & ub) for s in ea])) if ea else None, b_found_in_a=float(np.mean([bool(s & ua) for s in eb])) if eb else None, jaccard_edges=len(ua & ub) / max(len(ua | ub), 1))
    return res


def leave_one_day(ep):
    """The floor for 'jam list caught, false': one real day against a list from the other 7."""
    rows = []
    for d in range(D):
        others = [x for x in range(D) if x != d]
        lst = tier_a(places(ep, others, 2), ep, others, 4)
        today = tier_a(places(ep, [d], 1), ep, [d], 1)
        ul = set().union(*[set(p['edges']) for p in lst]) if lst else set()
        ut = set().union(*[set(p['edges']) for p in today]) if today else set()
        rows.append(dict(day=DAYS[d], list_places=len(lst), day_places=len(today), list_caught=float(np.mean([bool(set(p['edges']) & ut) for p in lst])), day_false=float(np.mean([not (set(p['edges']) & ul) for p in today]))))
    return pd.DataFrame(rows)


def clusters(j, threshold, group):
    """Space-time components per day in the box, all hours."""
    rows = []
    box = np.where(INBOX & (MAIN if group == 'main' else ~MAIN))[0]
    inbox = set(box.tolist())
    for d in range(D):
        u = UF()
        cells = [(int(i), int(t)) for i, t in zip(*np.nonzero(j[box][:, d]))]
        cells = [(int(box[i]), t) for i, t in cells]
        cs = set(cells)
        for i, t in cells:
            u.find((i, t))
            if (i, t + 1) in cs:
                u.union((i, t), (i, t + 1))
            for k in SUCC[i]:
                if k in inbox:
                    for dt in (0, 1, -1):
                        if (k, t + dt) in cs:
                            u.union((i, t), (k, t + dt))
        comp = collections.defaultdict(list)
        for c in cells:
            comp[u.find(c)].append(c)
        for v in comp.values():
            t = [x[1] for x in v]
            rows.append(dict(group=group, threshold=threshold, day=DAYS[d], duration_min=(max(t) - min(t) + 1) * 15, size_edge_intervals=len(v), peak_edges=max(collections.Counter(t).values()), km_min=float(sum(LEN[x[0]] for x in v)) / 1000 * 15, start=min(t)))
    return pd.DataFrame(rows)


def tail(x, xmin):
    x = np.asarray(x, float)
    x = x[x >= xmin]
    if len(x) < 20:
        return np.nan, len(x)
    return 1 + len(x) / np.log(x / (xmin - .5)).sum(), len(x)


def loop_rows():
    l = loops()
    s = sites().set_index('site')
    fr = site_free(l)
    l = l.assign(r=l.speed / l.site.map(fr))
    rows = []
    for frac, name in ((1 / 3, 'third'), (.5, 'half')):
        q = l[(l.r < frac) & (l.flow >= 50)]
        for (site), g in q.groupby('site'):
            for per, (h0, h1) in (('am', (5, 11)), ('pm', (12, 21))):
                z = g[g.hour.between(h0, h1 - 1)]
                if z.date.nunique() < 2:
                    continue
                by = z.groupby('date').hour
                st, en = by.min(), by.max() + 1
                x = s.loc[site]
                rows.append(dict(source='loop', threshold=name, period=per, place=x.street, head_edge=x.edge, site=site, scope=x.scope, road_class=x.road_class, class3=road_class3(x.road_class), in_district=x.scope == 'district', x=round(x.x), y=round(x.y), days_of_8=int(z.date.nunique()), start_median=f'{int(st.median()):02d}:00', start_min=f'{st.min():02d}:00', start_max=f'{st.max():02d}:00', end_median=f'{int(en.median()):02d}:00', end_min=f'{en.min():02d}:00', end_max=f'{en.max():02d}:00', min_ratio_median=round(float(z.groupby('date').r.min().median()), 2)))
    return pd.DataFrame(rows)


def main():
    out = []
    noise_tab, clus = [], []
    summ = {}
    for frac, name in ((1 / 3, 'third'), (.5, 'half')):
        j = jam_mask(frac)
        ep = episodes(j)
        pl = places(ep, range(D), 2)
        out += [describe(p, ep, name) for p in pl]
        one = places(ep, range(D), 1)
        noise_tab += [noise(ep, name, 'main'), noise(ep, name, 'local')]
        clus += [clusters(j, name, 'main'), clusters(j, name, 'local')]
        summ[name] = dict(split_half=split_half(ep), leave_one_day=leave_one_day(ep).to_dict('records'), one_day_only_places=int(sum(1 for p in one if not ep[p['edges']][:, :, p['q0']:PERIODS[p['period']][1]].any(axis=2).sum(axis=1).max() >= 2)))
        print(name, 'places', len(pl), flush=True)
    t = pd.concat([pd.DataFrame(out), loop_rows()], ignore_index=True)
    t = t.sort_values(['source', 'threshold', 'days_of_8', 'extent_km_2plus_days'], ascending=[True, False, False, False])
    t.to_csv(OUT / 'real_jams.csv', index=False)
    nt = pd.concat(noise_tab)
    nt.to_csv(OUT / 'real_jams_noise.csv', index=False, float_format='%.3f')
    c = pd.concat(clus)
    rows = []
    for (grp, name), g in c.groupby(['group', 'threshold']):
        for metric, xmin in (('duration_min', 30), ('size_edge_intervals', 2), ('peak_edges', 2)):
            a, n = tail(g[metric], xmin)
            per_day = [tail(x[metric], xmin)[0] for _, x in g.groupby('day')]
            vals, counts = np.unique(g[metric], return_counts=True)
            rows.append(dict(group=grp, threshold=name, metric=metric, xmin=xmin, n=n, clusters=len(g), exponent=round(a, 2), exponent_day_min=round(np.nanmin(per_day), 2), exponent_day_max=round(np.nanmax(per_day), 2), p50=g[metric].median(), p90=g[metric].quantile(.9), p99=g[metric].quantile(.99), max=g[metric].max(), share_over_60min=round(float((g.duration_min > 60).mean()), 3), share_over_180min=round(float((g.duration_min > 180).mean()), 3)))
    pd.DataFrame(rows).to_csv(OUT / 'real_jam_clusters.csv', index=False)
    c.to_pickle('/tmp/rung1/clusters.pkl')
    json.dump(summ, open('/tmp/rung1/jam_summary.json', 'w'), indent=1, default=float)
    print(pd.DataFrame(rows).to_string())
    print(nt.groupby(['group', 'threshold', 'period'])[['jaccard_edges', 'a_edge_hours_also_b', 'top20', 'edges_a']].agg(['median', 'min', 'max']).round(2).to_string())
    for k, v in summ.items():
        print(k, json.dumps(v['split_half']['even_vs_odd']), v['one_day_only_places'])
        print(pd.DataFrame(v['leave_one_day']).round(2).to_string())
    pr = t[t.source == 'probe']
    print(pr.groupby(['threshold', 'in_district', 'tier', 'pattern']).agg(n=('place', 'size'), km=('extent_km_median_day', 'sum'), days=('days_of_8', 'median')).round(1).to_string())
    cols = ['threshold', 'period', 'place', 'road_class', 'days_of_8', 'head_start_median', 'head_end_median', 'pattern', 'head_share_of_07_19_jam', 'extent_km_median_day', 'edges', 'head_jam_kmh', 'head_free_kmh', 'probe_volume_median', 'head_junction', 'cause']
    print(pr[(pr.threshold == 'third') & pr.in_district & (pr.tier == 'A')].sort_values(['days_of_8', 'extent_km_median_day'], ascending=False).head(45)[cols].to_string())
    print(pr[(pr.threshold == 'third') & (pr.class3 == 'motorway') & (pr.tier != 'B')].sort_values(['days_of_8', 'extent_km_median_day'], ascending=False).head(20)[cols + ['in_district']].to_string())
    print(t[t.source == 'loop'][['threshold', 'period', 'site', 'place', 'scope', 'days_of_8', 'start_median', 'end_median', 'min_ratio_median']].query("threshold=='third'").to_string())


main()
