#!/usr/bin/env python3
"""real_signal_pairs.csv: consecutive close-spaced lights in the Hamburg recording, F048. Definitions in R-reality-table.md."""
import collections
import datetime as dt
import glob
import gzip
import math
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rcommon import *

ROOT = DATA / 'datasets/hamburg-signals'
TZ = ZoneInfo('Europe/Berlin')
SAT = 0.5  # cars per second per lane, order of 1,800/h
V = 8.3


def connections():
    dist = json.load(open(ROOT / 'district.json'))['lights']
    mx, my = 111320 * math.cos(math.radians(53.55)), 110950
    C = {}
    for line in gzip.open(ROOT / 'static/things.jsonl.gz', 'rt'):
        t = json.loads(line)
        p = t['properties']
        L = p.get('trafficLightsID')
        ty = p.get('laneType') or ''
        if L not in dist or 'KFZ' not in ty or not t.get('Locations'):
            continue
        ds = [d for d in t['Datastreams'] if d['properties'].get('layerName') == 'primary_signal']
        g = t['Locations'][0]['location']['geometry']
        if not ds or g['type'] != 'MultiLineString' or len(g['coordinates']) != 3:
            continue
        C[t['name']] = dict(light=L, stream=str(ds[0]['@iot.id']), sg=ds[0]['properties'].get('signalGroupID'), lines=[np.array([[a[0] * mx, a[1] * my] for a in c]) for c in g['coordinates']])
    return C


def project(pl, p):
    seg = np.diff(pl, axis=0)
    n = np.linalg.norm(seg, axis=1)
    a = np.r_[0, np.cumsum(n)]
    best = (None, 1e9, None)
    for i in range(len(pl) - 1):
        if n[i] < .01:
            continue
        u = seg[i] / n[i]
        t = (p - pl[i]) @ u
        t2 = min(max(t, 0), n[i] + (150 if i == len(pl) - 2 else 0))
        d = np.linalg.norm(pl[i] + u * t2 - p)
        if d < best[1]:
            best = (a[i] + t2, d, u)
    return best


def pairs(C):
    rows = []
    for kc, c in C.items():
        path, eg = c['lines'][1], c['lines'][2]
        S = path[0]
        s_eg = project(path, eg[0])[0]
        for kd, d in C.items():
            if kd == kc:
                continue
            Sd = d['lines'][1][0]
            if np.linalg.norm(Sd - S) > 260:
                continue
            s, lat, u = project(path, Sd)
            if s is None or lat > 4.5 or s < 8:
                continue
            ud = d['lines'][1][min(2, len(d['lines'][1]) - 1)] - Sd
            nn = np.linalg.norm(ud)
            if nn < .1 or ud @ u / nn < math.cos(math.radians(35)):
                continue
            uc = path[min(2, len(path) - 1)] - S
            turn = math.degrees(math.acos(max(-1, min(1, uc @ ud / (np.linalg.norm(uc) * nn)))))
            rows.append(dict(turn_deg=turn, c=kc, d=kd, lc=c['light'], ld=d['light'], gc=c['sg'], gd=d['sg'], sc=c['stream'], sd=d['stream'], stop_to_stop=s, link=s - s_eg, lateral=lat))
    return pd.DataFrame(rows)


def greens(streams):
    """stream -> day -> arrays of (start, end) epoch seconds. Full weekdays only."""
    out = collections.defaultdict(list)
    used = []
    for f in sorted(glob.glob(str(ROOT / 'days/*.tsv.gz'))):
        day = f.rsplit('/', 1)[1][:10]
        if dt.date.fromisoformat(day).weekday() >= 5:
            continue
        seq = collections.defaultdict(dict)
        lights = set()
        times = []
        with gzip.open(f, 'rt') as h:
            for line in h:
                p = line.rstrip('\n').split('\t')
                if len(p) < 5 or p[1] != 'primary_signal':
                    continue
                lights.add(p[0])
                if p[2] in streams:
                    seq[p[2]][p[3]] = p[4]
        print(day, len(lights), len(seq), flush=True)
        if len(lights) < 40 or sum(len(v) for v in seq.values()) < 300000:
            print('  partial, left out', flush=True)
            continue
        used.append(day)
        for st, ev in seq.items():
            ts = sorted(ev)
            sec = pd.to_datetime(ts, format='%Y-%m-%dT%H:%M:%SZ', utc=True).astype('int64') // 10**9 if False else np.array([dt.datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc).timestamp() for x in ts])
            r = [ev[x] for x in ts]
            on = None
            for t, v in zip(sec, r):
                g = v in ('3', '6')
                if g and on is None:
                    on = t
                elif not g and on is not None:
                    out[st].append((on, t))
                    on = None
    return {k: np.array(v) for k, v in out.items()}, used


def band_of(sec):
    d = dt.datetime.fromtimestamp(sec, TZ)
    return d.hour


def analyse(G, P):
    rows = []
    for r in P.itertuples():
        a, b = G.get(r.sc), G.get(r.sd)
        if a is None or b is None or len(a) < 50 or len(b) < 50:
            continue
        hours = np.array([band_of(x) for x in a[:, 0]])
        for band, m in (('day_07_19', (hours >= 7) & (hours < 19)), ('am_07_09', (hours >= 7) & (hours < 9)), ('pm_15_18', (hours >= 15) & (hours < 18)), ('night_22_05', (hours >= 22) | (hours < 5))):
            x = a[m]
            if len(x) < 30:
                continue
            # cycles
            cy_a = np.diff(a[:, 0])
            cy_a = np.median(cy_a[(cy_a >= 20) & (cy_a <= 300)][m[:-1][(cy_a >= 20) & (cy_a <= 300)]]) if m[:-1].any() else np.nan
            bs = b[:, 0]
            i = np.searchsorted(bs, x[:, 0])
            prev = np.clip(i - 1, 0, len(bs) - 1)
            nxt = np.clip(i, 0, len(bs) - 1)
            dp, dn = bs[prev] - x[:, 0], bs[nxt] - x[:, 0]
            off = np.where(np.abs(dp) < np.abs(dn), dp, dn)
            good = np.abs(off) <= 150
            hd = b[(b[:, 0] >= x[0, 0] - 300) & (b[:, 0] <= x[-1, 0] + 300), 0]
            cy_b = np.diff(hd)
            cy_b = np.median(cy_b[(cy_b >= 20) & (cy_b <= 300)]) if len(cy_b) else np.nan
            # overlap, per c green
            over, tail, gl = [], [], []
            lo = np.searchsorted(b[:, 1], x[:, 0], side='right')
            for k, (s, e) in enumerate(x):
                ov = 0.0
                j = lo[k]
                t_end = 0.0
                while j < len(b) and b[j, 0] < e:
                    ov += min(e, b[j, 1]) - max(s, b[j, 0])
                    if b[j, 0] <= e <= b[j, 1]:
                        t_end = b[j, 1] - e
                    j += 1
                if j < len(b) and b[j, 0] <= e <= b[j, 1]:
                    t_end = b[j, 1] - e
                over.append(ov)
                tail.append(t_end)
                gl.append(e - s)
            over, tail, gl = np.array(over), np.array(tail), np.array(gl)
            feed = gl - over
            clear_t = np.maximum(r.stop_to_stop, 0) / V
            store = max(r.link, 7.5) / 7.5
            fits = feed * SAT <= store
            tail_ok = tail >= clear_t
            cl = tail_ok | fits
            q25, q50, q75 = np.percentile(off[good], [25, 50, 75]) if good.any() else (np.nan,) * 3
            same = r.lc == r.ld
            same_cycle = abs(cy_a - cy_b) <= 1 if np.isfinite(cy_a) and np.isfinite(cy_b) else False
            linked = bool(same or (same_cycle and q75 - q25 <= 5))
            rows.append(dict(movement='through' if r.turn_deg <= 30 else 'turn', turn_deg=round(r.turn_deg), pair=f'{r.c}>{r.d}', light_c=r.lc, light_d=r.ld, group_c=r.gc, group_d=r.gd, one_controller=same, band=band, link_m=round(r.link, 1), stop_to_stop_m=round(r.stop_to_stop, 1), cycles=len(x), cycle_c=cy_a, cycle_d=cy_b, same_cycle=same_cycle, offset_p50=round(q50, 1), offset_iqr=round(q75 - q25, 1), linked=linked, green_c=np.median(gl), overlap_share=round(float(np.median(over / np.maximum(gl, 1))), 3), overlap_p10=round(float(np.percentile(over / np.maximum(gl, 1), 10)), 3), overlap_p90=round(float(np.percentile(over / np.maximum(gl, 1), 90)), 3), red_feed_s=np.median(feed), red_feed_p90=np.percentile(feed, 90), tail_s=np.median(tail), clear_needed_s=round(clear_t, 1), storage_cars=round(store, 1), share_tail_ok=round(float(tail_ok.mean()), 3), share_fits=round(float(fits.mean()), 3), share_clears=round(float(cl.mean()), 3)))
    return pd.DataFrame(rows)


def sumband(d):
    def f(g):
        # one row per signal-group pair per band, then equal weight per light pair for the headline
        return pd.Series(dict(conn_pairs=len(g), group_pairs=g.groupby(['light_c', 'group_c', 'light_d', 'group_d']).ngroups, light_pairs=g.groupby(['light_c', 'light_d']).ngroups, one_controller=g.one_controller.mean(), linked=g.linked.mean(), same_cycle=g.same_cycle.mean(), offset_p50=g.offset_p50.median(), offset_p25=g.offset_p50.quantile(.25), offset_p75=g.offset_p50.quantile(.75), offset_iqr=g.offset_iqr.median(), overlap=g.overlap_share.median(), overlap_p10=g.overlap_share.quantile(.1), overlap_p90=g.overlap_share.quantile(.9), red_feed=g.red_feed_s.median(), red_feed_p90=g.red_feed_s.quantile(.9), tail=g.tail_s.median(), clear_needed=g.clear_needed_s.median(), storage=g.storage_cars.median(), clears=g.share_clears.median(), clears_mostly=(g.share_clears >= .8).mean(), tail_ok=g.share_tail_ok.median(), fits=g.share_fits.median()))
    return d.groupby(['link_band', 'band']).apply(f, include_groups=False).round(2)


def main():
    C = connections()
    P = pairs(C)
    print('car connections', len(C), 'geometric pairs', len(P), flush=True)
    G, used = greens(set(P.sc) | set(P.sd))
    print('days', used, flush=True)
    a = analyse(G, P)
    a['link_band'] = pd.cut(a.link_m, [-500, 0, 30, 50, 150, 500], labels=['inside_junction', 'lt30', '30_50', '50_150', 'gt150'], right=False).astype(str)
    pd.set_option('display.width', 280)
    pd.set_option('display.max_columns', 60)
    a['overlap_class'] = np.select([a.overlap_share >= .8, a.overlap_share <= .2], ['together', 'opposed'], 'partial')
    # group pairs are the independent unit
    g = a.groupby(['band', 'movement', 'link_band', 'light_c', 'group_c', 'light_d', 'group_d']).agg(one_controller=('one_controller', 'first'), linked=('linked', 'mean'), same_cycle=('same_cycle', 'mean'), offset=('offset_p50', 'median'), iqr=('offset_iqr', 'median'), overlap=('overlap_share', 'median'), feed=('red_feed_s', 'median'), green=('green_c', 'median'), tail=('tail_s', 'median'), need=('clear_needed_s', 'median'), store=('storage_cars', 'median'), clears=('share_clears', 'median'), link=('link_m', 'median')).reset_index()
    g['cls'] = np.select([g.overlap >= .8, g.overlap <= .2], ['together', 'opposed'], 'partial')
    for band in ('day_07_19', 'am_07_09', 'pm_15_18', 'night_22_05'):
        z = g[g.band == band]
        t = z.groupby(['movement', 'link_band']).agg(groups=('link', 'size'), lights=('light_c', 'nunique'), one=('one_controller', 'mean'), linked=('linked', 'mean'), same_cycle=('same_cycle', 'mean'), off_p25=('offset', lambda x: x.quantile(.25)), off_p50=('offset', 'median'), off_p75=('offset', lambda x: x.quantile(.75)), iqr=('iqr', 'median'), overlap=('overlap', 'median'), together=('cls', lambda x: (x == 'together').mean()), opposed=('cls', lambda x: (x == 'opposed').mean()), feed=('feed', 'median'), feed_p90=('feed', lambda x: x.quantile(.9)), tail=('tail', 'median'), need=('need', 'median'), store=('store', 'median'), clears=('clears', 'median'), clear80=('clears', lambda x: (x >= .8).mean())).round(2)
        print(band)
        print(t.to_string())
    z = g[(g.band == 'day_07_19') & (g.movement == 'through') & g.link_band.isin(['lt30', '30_50'])]
    print(z.sort_values('link')[['light_c', 'group_c', 'light_d', 'group_d', 'link', 'one_controller', 'linked', 'same_cycle', 'offset', 'iqr', 'green', 'overlap', 'feed', 'tail', 'need', 'store', 'clears']].to_string())
    print(z.groupby('cls').agg(n=('link', 'size'), off=('offset', 'median'), offmin=('offset', 'min'), offmax=('offset', 'max'), feed=('feed', 'median'), tail=('tail', 'median'), link=('link', 'median'), clears=('clears', 'median')).round(1).to_string())
    g.drop(columns=['cls']).assign(overlap_class=g.cls).round(3).to_csv(OUT / 'real_signal_pairs.csv', index=False)
    g.to_csv('/tmp/rung1/pairs_groups.csv', index=False)
    a.to_pickle('/tmp/rung1/pairs.pkl')
    json.dump(dict(days=used), open('/tmp/rung1/pairs_days.json', 'w'))


main()
