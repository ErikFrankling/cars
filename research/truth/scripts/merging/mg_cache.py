"""Compact per-site cache for the merging study: one table per site, smoothed speed, acceleration from speed, lateral position, lane-centre offset.
Usage: mg_cache.py SITE [SITE...] from the repo root. Inputs are inert CSVs. One site at a time."""
import sys; sys.path.insert(0, 'research/truth/scripts')
from courtesy_lib import *
import courtesy_lib
if os.environ.get('MG_DATA'):
    courtesy_lib.T = pathlib.Path(os.environ['MG_DATA']) / 'T'; courtesy_lib.C = pathlib.Path(os.environ['MG_DATA']) / 'C'
    T = courtesy_lib.T; C = courtesy_lib.C
OUTC = pathlib.Path(os.environ.get('MG_DATA', '/home/erikf/projects/personal/cars-data/truth/merging-20261102')) / 'cache'

def load(site):
    if site in ('us-101', 'i-80'):
        d = ngsim(C / 'ngsim-20261101' / f'{site}.csv'); d = d[d['lane'] > 0]; d = d[d['cls'] != 1]; return d, 10
    if site == 'ht':
        d = ht(); d = d[d['tr'] == 0]; return d, 5
    d = tgsim(site); d = d[d['auto'] == 0]; return d, 10

def smooth(x, n):
    k = np.ones(n) / n; pad = n // 2
    return np.convolve(np.r_[np.full(pad, x[0]), x, np.full(n - 1 - pad, x[-1])], k, 'valid')

def run(site):
    d, hz = load(site)
    cols = ['run', 't', 'id', 'lane', 's', 'v', 'L', 'lat']
    d = d[cols].sort_values(['run', 'id', 't']).reset_index(drop=True)
    R, T_, I, LA, S, V, LL, LT = [d[c].values for c in cols]
    print(site, 'rows', len(d), flush=True)
    bins = (S / 20).astype('i4')
    # lane centre by run, lane and 20 m bin; I-90 stationary and others keep one frame per run
    cen = pd.DataFrame(dict(r=R, l=LA, b=bins, x=LT)).groupby(['r', 'l', 'b'])['x'].agg(['median', 'size']).reset_index()
    cen = cen[cen['size'] >= 10]
    new = np.r_[True, (I[1:] != I[:-1]) | (R[1:] != R[:-1]) | (np.diff(T_) != 1)]
    st = np.where(new)[0]; en = np.r_[st[1:], len(d)]
    vs = V.astype('f4').copy(); ac = np.zeros(len(d), 'f4'); ls = LT.astype('f4').copy()
    n = hz + (1 - hz % 2)
    for a, b in zip(st, en):
        if b - a < n: continue
        v = smooth(V[a:b].astype('f8'), n); vs[a:b] = v
        g = np.gradient(v) * hz; ac[a:b] = smooth(g, n)
        ls[a:b] = smooth(LT[a:b].astype('f8'), n)
    np.savez(OUTC / f'{site}.npz', run=R.astype('i2'), t=T_.astype('i4'), id=I.astype('i4'), lane=LA.astype('i2'), s=S.astype('f4'), v=vs, a=ac, L=LL.astype('f4'), lat=ls, hz=hz)
    cen.to_csv(OUTC / f'{site}.centres.csv.gz', index=False, float_format='%.3f')
    cnt = d.groupby('lane')['id'].nunique()
    print(site, 'done; vehicles by lane', cnt.to_dict(), flush=True)

for s in sys.argv[1:]: run(s)
