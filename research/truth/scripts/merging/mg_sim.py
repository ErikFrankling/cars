"""Turn the simulator's own I-80 lane-end traces (accept3 build, cooperation 0.25 and 0.5, two seeds) into the same cache format, so the same pipeline measures them.
Lane label is rebuilt from lateral position, as in real data: it flips when the car's centre crosses the line, not when the simulator commits."""
import os, sys, pathlib, re
import numpy as np, pandas as pd
B = pathlib.Path('/home/erikf/projects/personal/cars-data/truth/humans/accept3/coop')
OUT = pathlib.Path(os.environ.get('MG_DATA', '/home/erikf/projects/personal/cars-data/truth/merging-20261102')) / 'cache'
W = 3.2
parts = []; run = 0
TAG = sys.argv[1] if len(sys.argv) > 1 else 'sim'
for c in (sys.argv[2:] or ['merge_i80_c0.25', 'merge_i80_c0.5']):
    net = (B / c / 'net.xml').read_text()
    Ln = {m.group(1): float(m.group(2)) for m in re.finditer(r'<lane id="([\w:]+)"[^>]*?length="([\d.]+)"', net)}
    for seed in ('s0', 's1'):
        d = pd.read_csv(B / c / f'{seed}.fcd.csv', usecols=['time', 'trip', 'lane', 'pos', 'speed', 'acc', 'length', 'offset'])
        Lm = Ln['merge_1']; Lc = Ln.get(':c_0_0', 0.0)
        la = d['lane'].values; pos = d['pos'].values.astype('f8')
        s = np.full(len(d), np.nan); idx = np.ones(len(d), 'i2')
        for name, base, ii in (('up_0', -Ln['up_0'], 2), ('on_0', -Ln['on_0'], 1), ('merge_0', 0.0, 1), ('merge_1', 0.0, 2), (':c_0_0', Lm, 2), ('down_0', Lm + Lc, 2), (':b_0_0', -Ln.get(':b_0_0', 0), 1), (':b_1_0', -Ln.get(':b_1_0', 0), 2)):
            m = la == name; s[m] = pos[m] + base; idx[m] = ii
        ok = np.isfinite(s)
        d = d[ok]; s = s[ok]; idx = idx[ok]
        lat = idx * W + d['offset'].values  # continuous across the commit
        lab = np.where(lat < 1.5 * W, 1, 2)
        lab = np.where(idx == 2, np.where(lat < 1.5 * W, 1, 2), 1)
        f = pd.DataFrame(dict(run=run, t=np.floor(d['time'].values).astype('i4'), id=pd.factorize(d['trip'])[0], lane=lab.astype('i2'), s=s, v=d['speed'].values, a=d['acc'].values, L=d['length'].values, lat=lat, ramp=d['trip'].str.startswith('ramp').values))
        parts.append(f); run += 1
d = pd.concat(parts, ignore_index=True).sort_values(['run', 'id', 't']).reset_index(drop=True)
np.savez(OUT / f'{TAG}.npz', run=d['run'].values.astype('i2'), t=d['t'].values, id=d['id'].values.astype('i4'), lane=d['lane'].values.astype('i2'), s=d['s'].values.astype('f4'), v=d['v'].values.astype('f4'), a=d['a'].values.astype('f4'), L=d['L'].values.astype('f4'), lat=d['lat'].values.astype('f4'), hz=1)
b = (d['s'] / 20).astype('i4')
cen = pd.DataFrame(dict(r=d['run'], l=d['lane'], b=b, x=d['lat'])).groupby(['r', 'l', 'b'])['x'].agg(['median', 'size']).reset_index()
cen.to_csv(OUT / f'{TAG}.centres.csv.gz', index=False)
print('rows', len(d), 'runs', run, 'Lm', Lm, d.groupby('lane')['id'].nunique().to_dict(), 'ramp cars', d[d.ramp].groupby('run')['id'].nunique().to_dict())
