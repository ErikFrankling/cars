"""F110: the T1 floor for F101. For each real window, the real follower of another vehicle whose window is nearest in
initial spacing, initial speed and leader speed profile; then the 30 s RMSE between the two spacing changes (each from
its own start, as a rollout starts from the recorded state). How much two real drivers differ behind similar leaders.

    python3 -I scripts/replay/floor_t1.py
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from rpl import OUT
import numpy as np

SITE = os.environ.get('F101_SITE', 'I90mov')
D = f'{OUT}/f101' if SITE == 'I90mov' else f'{OUT}/f101_{SITE}'
w = np.load(f'{D}/windows.npz')
s, v, vl, fid, lid, run = w['s'].astype(float), w['v'].astype(float), w['vl'].astype(float), w['fid'], w['lid'], w['run']
N = s.shape[1]
F = np.vstack([vl[::10], v[:1] * 3, s[:1] / 2]).T   # leader speed every second, the start weighted up
mu, sd = F.mean(0), F.std(0) + 1e-9
Z = (F - mu) / sd
out = {}
for k_best in (1, 5):
    drift, lead_mis, start_mis = [], [], []
    sq = (Z ** 2).sum(1)
    for a in range(0, N, 512):
        d = sq[a:a + 512, None] + sq[None, :] - 2 * Z[a:a + 512] @ Z.T
        for r, i in enumerate(range(a, min(a + 512, N))):
            bad = (fid == fid[i]) | (lid == lid[i]) | (fid == lid[i]) | (lid == fid[i])
            d[r, bad] = np.inf
        nn = np.argsort(d, 1)[:, :k_best]
        for r, i in enumerate(range(a, min(a + 512, N))):
            for j in nn[r]:
                drift.append(np.mean(((s[:, j] - s[0, j]) - (s[:, i] - s[0, i])) ** 2))
                lead_mis.append(np.sqrt(np.mean((vl[:, j] - vl[:, i]) ** 2)))
                start_mis.append(abs(v[0, j] - v[0, i]))
    drift = np.array(drift)
    out[f'nearest_{k_best}'] = dict(pairs=len(drift), drift_rmse_30s=float(np.sqrt(drift.mean())),
                                    leader_speed_mismatch_rms=dict(p50=float(np.median(lead_mis)), p90=float(np.percentile(lead_mis, 90))),
                                    start_speed_mismatch=dict(p50=float(np.median(start_mis)), p90=float(np.percentile(start_mis, 90))))
# The same drift measure for the simulated followers, so the floor and the model are read in one unit.
for tag in sys.argv[1:] or ('main_s0', 'sumo_s0'):
    p = f'{D}/{tag}.roll.npz'
    if os.path.exists(p):
        S = np.load(p)['S']; ok = np.isfinite(S).all(0)
        out[f'{tag}_drift_rmse_30s'] = float(np.sqrt(np.mean(((S[:, ok] - S[0, ok]) - (s[:, ok] - s[0, ok])) ** 2)))
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(REPO, 'research/truth/replay', 'f110.json' if SITE == 'I90mov' else f'f110_{SITE}.json'), 'w'), indent=1)
