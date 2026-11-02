"""The simulator's free-flow lane end (accept3 merge_free: 3 lanes then 2, 33 m/s, 300 + 1500 veh/h). Same output format as mg_sim, label from lateral position."""
import os, pathlib, re
import numpy as np, pandas as pd
B = pathlib.Path('/home/erikf/projects/personal/cars-data/truth/humans/accept3/rest/merge_free')
OUT = pathlib.Path(os.environ['MG_DATA']) / 'cache'; W = 3.2
net = (B / 'net.xml').read_text()
Ln = {m.group(1): float(m.group(2)) for m in re.finditer(r'<lane id="([\w:]+)"[^>]*?length="([\d.]+)"', net)}
Lu, Lm = Ln['up_0'], Ln['merge_0']; parts = []
for run, seed in enumerate(('s0', 's1')):
    d = pd.read_csv(B / f'{seed}.fcd.csv', usecols=['time', 'trip', 'lane', 'pos', 'speed', 'acc', 'length', 'offset'])
    la = d['lane'].values; pos = d['pos'].values.astype('f8'); s = np.full(len(d), np.nan); idx = np.zeros(len(d), 'i2')
    for k in range(3):
        m = la == f'up_{k}'; s[m] = pos[m] - Lu; idx[m] = k
        m = la == f'merge_{k}'; s[m] = pos[m]; idx[m] = k
    for k in range(2):
        m = la == f'out_{k}'; s[m] = pos[m] + Lm; idx[m] = k + 1
    ok = np.isfinite(s); d = d[ok]; s = s[ok]; idx = idx[ok]
    lat = idx * W + d['offset'].values
    lab = np.clip(np.round(lat / W), 0, 3).astype('i2') + 1
    parts.append(pd.DataFrame(dict(run=run, t=np.round(d['time'].values * 2).astype('i4'), id=pd.factorize(d['trip'])[0], lane=lab, s=s, v=d['speed'].values, a=d['acc'].values, L=d['length'].values, lat=lat)))
d = pd.concat(parts, ignore_index=True).sort_values(['run', 'id', 't']).reset_index(drop=True)
np.savez(OUT / 'simf.npz', run=d['run'].values.astype('i2'), t=d['t'].values, id=d['id'].values.astype('i4'), lane=d['lane'].values.astype('i2'), s=d['s'].values.astype('f4'), v=d['v'].values.astype('f4'), a=d['a'].values.astype('f4'), L=d['L'].values.astype('f4'), lat=d['lat'].values.astype('f4'), hz=2)
b = (d['s'] / 20).astype('i4')
pd.DataFrame(dict(r=d['run'], l=d['lane'], b=b, x=d['lat'])).groupby(['r', 'l', 'b'])['x'].agg(['median', 'size']).reset_index().to_csv(OUT / 'simf.centres.csv.gz', index=False)
print('simf rows', len(d), 'Lu', Lu, 'Lm', Lm, d.groupby('lane')['id'].nunique().to_dict())
