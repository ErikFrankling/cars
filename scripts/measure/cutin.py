"""F853: the shipped law (round 5, MODEL.md) after a cut-in, in report 18's terms (research/truth/18-how-humans-merge.md,
B7): own = the law behind the old leader, mer = the law behind the merger at the lag gap, the follower does own + w (mer - own)
with the asked part capped at 0. Report 18's follower rows (research/truth/scripts/merging), on its sites that are not held
out here (HOLDOUT.md): I-80, US-101, I-395, I-294 L1. I-90/94 moving and DLR HT are skipped.

    python3 -I scripts/measure/cutin.py          # -> research/truth/measure/cutin.json
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, 'research', 'truth', 'scripts', 'merging'))
import fit_driver as FD
import pathlib
import mg_replay_lib as RL
RL.EV = pathlib.Path('/home/erikf/projects/personal/cars-data/truth/merging-20261102/work/data')   # report 18's event series
follower_rows = RL.follower_rows

P = FD.r5_params()


def law(g, v, vl):
    return np.clip(FD.command_r5(v, np.maximum(g, 0.5), vl, 0.0, P), -8.3, 2.5)


def main():
    out = {}
    for n in ['i-80', 'us-101', 'I395', 'I294L1']:
        d = follower_rows(n)
        own = law(d['g'].where(d['g'] < 80).fillna(1e3).values, d['v'].values, d['vl'].values)
        mer = law(d['lag'].values, d['v'].values, d['ve'].values)
        x = np.minimum(mer - own, 0.0); y = d['a'].values - own
        ok = np.isfinite(x) & np.isfinite(y)
        x, y = x[ok], y[ok]
        w = float(np.sum(y * x) / np.sum(x * x))
        r = lambda e: round(float(np.sqrt(np.mean(e ** 2))), 3)
        # bootstrap by event
        ev = d['e'].values[ok]; u, inv = np.unique(ev, return_inverse=True); mem = [np.flatnonzero(inv == j) for j in range(len(u))]
        rng = np.random.default_rng(853); bs = []
        for _ in range(300):
            ii = np.concatenate([mem[j] for j in rng.integers(0, len(u), len(u))])
            bs.append(np.sum(y[ii] * x[ii]) / np.sum(x[ii] ** 2))
        out[n] = dict(events=int(len(u)), rows=int(ok.sum()), w=[round(w, 3), round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                      rmse_ignore=r(y), rmse_full=r(y - x), rmse_best_w=r(y - w * x),
                      full_over_best=round(float(np.sqrt(np.mean((y - x) ** 2)) / np.sqrt(np.mean((y - w * x) ** 2))), 3),
                      median_asked=round(float(np.median(x[x < 0])), 3) if (x < 0).any() else None)
        print(n, out[n], flush=True)
    json.dump(out, open(os.path.join(REPO, 'research/truth/measure/cutin.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
