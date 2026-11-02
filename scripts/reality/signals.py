#!/usr/bin/env python3
"""real_signals.csv: cycle and green share by local hour from the Hamburg recording, plus Berlin's published corridor. Only primary_signal is read."""
import datetime as dt
import glob
import gzip
import subprocess
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rcommon import *

ROOT = DATA / 'datasets/hamburg-signals'
TZ = ZoneInfo('Europe/Berlin')
GREEN, HOLD = '3', '36'
MIN_ROWS_FULL_DAY = 2_000_000


def read_day(path):
    light, stream, t, res = [], [], [], []
    with gzip.open(path, 'rt') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 5 and p[1] == 'primary_signal':
                light.append(p[0]); stream.append(p[2]); t.append(p[3]); res.append(p[4])
    x = pd.DataFrame(dict(light=light, stream=stream, t=pd.to_datetime(t, format='%Y-%m-%dT%H:%M:%SZ', utc=True), res=res))
    return x.drop_duplicates(['stream', 't']).sort_values(['stream', 't'])


def cycles(x):
    rows = []
    for (light, stream), g in x.groupby(['light', 'stream'], sort=False):
        t = g.t.astype('int64').to_numpy() / (1e9 if str(g.t.dtype).endswith('[ns, UTC]') else 1e6 if '[us' in str(g.t.dtype) else 1)
        r = g.res.to_numpy()
        starts = []
        for i in range(1, len(r)):
            if r[i] == GREEN and r[i - 1] not in ('3', '5', '6'):
                j = i + 1
                while j < len(r) and r[j] in HOLD:
                    j += 1
                starts.append((t[i], t[j] - t[i] if j < len(r) else np.nan))
        for (a, g0), (b, _) in zip(starts, starts[1:]):
            c = b - a
            if 20 <= c <= 300 and np.isfinite(g0) and g0 <= c:
                rows.append((light, stream, a, c, g0 / c))
    return rows


def main():
    frames, days_used = [], []
    for f in sorted(glob.glob(str(ROOT / 'days/*.tsv.gz'))):
        x = read_day(f)
        n = len(x)
        print(f.rsplit('/', 1)[1], n, x.light.nunique(), flush=True)
        if x.light.nunique() < 40 or x.t.dt.hour.nunique() < 24 or (x.groupby('light').t.max().min() - x.t.min()).total_seconds() < 80000:
            print('  partial, left out', flush=True)
            continue
        days_used.append(f.rsplit('/', 1)[1][:10])
        c = pd.DataFrame(cycles(x), columns=['light', 'stream', 'a', 'cycle', 'green'])
        l = pd.to_datetime(c.a, unit='s', utc=True).dt.tz_convert(TZ)
        c['weekend'] = l.dt.weekday >= 5
        c['hour'] = l.dt.hour
        frames.append(c[['light', 'stream', 'weekend', 'hour', 'cycle', 'green']])
    c = pd.concat(frames)
    rows = []
    for (we, h), g in c.groupby(['weekend', 'hour']):
        conn = g.groupby(['light', 'stream'])
        iqr = conn.cycle.quantile(.75) - conn.cycle.quantile(.25)
        iqr = iqr[conn.size() >= 4]
        # main-phase: per light, the connection with the longest median green share
        best = conn.green.median().groupby('light').max()
        rows.append(dict(city='Hamburg', source='measured 2026 report 26', day_type='weekend' if we else 'weekday', hour=h, n_cycles=len(g), n_connections=conn.ngroups, n_lights=g.light.nunique(), cycle_p10=g.cycle.quantile(.1), cycle_p50=g.cycle.median(), cycle_p90=g.cycle.quantile(.9), within_connection_iqr_p50=iqr.median(), green_share_p10=round(g.green.quantile(.1), 3), green_share_p50=round(g.green.median(), 3), green_share_p90=round(g.green.quantile(.9), 3), longest_green_per_light_p10=round(best.quantile(.1), 3), longest_green_per_light_p50=round(best.median(), 3), longest_green_per_light_p90=round(best.quantile(.9), 3), note=''))
    r = pd.DataFrame(rows)
    # day-to-day: weekday-hour median per day isn't kept above, so the spread between lights is what the table carries
    extra = [dict(city='Berlin', source='Senate answer S19-12905, report 23', day_type='weekday', hour=np.nan, cycle_p50=v, note=f'one corridor B1/B5, coordinated, {t}. Which hours carry which cycle not read here') for v, t in ((90, 'published cycle'), (110, 'published cycle'), (100, 'published cycle'))]
    r = pd.concat([r, pd.DataFrame(extra)])
    r.to_csv(OUT / 'real_signals.csv', index=False)
    print('days', days_used)
    print(r[r.city == 'Hamburg'].drop(columns=['city', 'source', 'note']).to_string())


main()
