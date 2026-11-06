"""F102, F103, F106: classifier two-sample test (Lopez-Paz and Oquab 2017) on 10 s car-following windows.

Real windows are report 05's I-90/94 moving windows; simulated ones are the F101 rollouts behind the same recorded
leaders. Both pass through one instrument before features are taken: positions sampled at 10 Hz, the tracker's own
leftover noise added to the simulated ones, then the same local-quadratic smoother (1 s) on both. Features are simple
statistics of speed, acceleration, jerk, spacing, time gap and closing speed (no lateral position: one lane each).
Gradient boosting is a small histogram implementation in numpy. Accuracy is held out by 5-fold CV over 60 s chunks
of one run, so a real window and its simulated twin are always in the same fold; the 95% interval bootstraps blocks.

    python3 -I scripts/replay/classifier.py            # needs cars-data/replay/f101/main_s0.roll.npz
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from rpl import OUT
import numpy as np

D = os.path.join(OUT, 'f101')
SUB = 100  # 10 s at 0.1 s


# ---------------------------------------------------------------- instrument

def smooth_kernel(half=5):
    """Local quadratic fit over 2*half+1 samples, value at the centre (Savitzky-Golay)."""
    t = np.arange(-half, half + 1, dtype=float)
    A = np.vstack([np.ones_like(t), t, t * t]).T
    return np.linalg.pinv(A)[0]


def smooth(x, half=5):
    k = smooth_kernel(half)
    xp = np.pad(x, ((half, half), (0, 0)), mode='edge')
    return np.stack([np.convolve(xp[:, j], k[::-1], mode='valid') for j in range(x.shape[1])], 1)


def tracker_noise(x):
    """Leftover noise of positions about a 1 s local quadratic: the instrument's floor, measured on real data."""
    r = x - smooth(x)
    return float(np.std(r[5:-5]))


def instrument(xf, xl, sigma, rng):
    """Positions in, then what the recording's pipeline would give: noisy positions, smoothed, differentiated."""
    if sigma > 0:
        # The recording's speeds are the tracker's smooth ones; its noise shows in spacing, so it goes there.
        xl = xl + rng.normal(0, sigma, xl.shape)
    xf = smooth(xf); xl = smooth(xl)
    v = np.gradient(xf, 0.1, axis=0); vl = np.gradient(xl, 0.1, axis=0)
    return xl - xf, smooth(v), smooth(vl)


# ---------------------------------------------------------------- features

NAMES = []


def feats(s, v, vl):
    """s, v, vl: (T, N) at 0.1 s, T = 300; returns (3N, F) for the three 10 s sub-windows."""
    out = []
    for k in range(3):
        a0, a1 = k * SUB, (k + 1) * SUB
        S, V, VL = s[a0:a1], v[a0:a1], vl[a0:a1]
        A = (V[10:] - V[:-10]) / 1.0
        J = (A[10:] - A[:-10]) / 1.0
        dv = VL - V
        tg = (S - 5.0) / np.maximum(V, 0.5)
        hf = np.diff(V, 2, axis=0)
        c0 = np.array([np.corrcoef(A[:, i], dv[5:-5, i])[0, 1] if A[:, i].std() > 1e-6 and dv[:, i].std() > 1e-6 else 0 for i in range(V.shape[1])])
        c1 = np.array([np.corrcoef(A[10:, i], dv[5:-15, i])[0, 1] if A[10:, i].std() > 1e-6 and dv[:, i].std() > 1e-6 else 0 for i in range(V.shape[1])])
        F = dict(v_mean=V.mean(0), v_sd=V.std(0), v_min=V.min(0), v_max=V.max(0),
                 a_mean=A.mean(0), a_sd=A.std(0), a_p5=np.percentile(A, 5, 0), a_p95=np.percentile(A, 95, 0), a_absmean=np.abs(A).mean(0),
                 jerk_sd=J.std(0), jerk_p95=np.percentile(np.abs(J), 95, 0), v_hf_sd=hf.std(0),
                 s_mean=S.mean(0), s_sd=S.std(0), s_min=S.min(0), tgap_med=np.median(tg, 0),
                 dv_mean=dv.mean(0), dv_sd=dv.std(0), dv_absmean=np.abs(dv).mean(0),
                 corr_a_dv=np.nan_to_num(c0), corr_a_dv_lag1=np.nan_to_num(c1))
        if not NAMES:
            NAMES.extend(F)
        out.append(np.stack([F[n] for n in NAMES], 1))
    return np.vstack(out)


# ---------------------------------------------------------------- gradient boosting

class GBM:
    def __init__(self, rounds=150, depth=3, lr=0.1, bins=32, min_leaf=20, lam=1.0):
        self.r, self.d, self.lr, self.nb, self.ml, self.lam = rounds, depth, lr, bins, min_leaf, lam

    def _bin(self, X):
        return np.stack([np.searchsorted(self.edges[j], X[:, j]) for j in range(X.shape[1])], 1).astype(np.int16)

    def fit(self, X, y):
        self.edges = [np.unique(np.quantile(X[:, j], np.linspace(0, 1, self.nb + 1)[1:-1])) for j in range(X.shape[1])]
        B = self._bin(X); n, m = B.shape
        self.f0 = np.log(y.mean() / (1 - y.mean())); f = np.full(n, self.f0)
        self.trees = []; self.gain = np.zeros(m)
        for _ in range(self.r):
            p = 1 / (1 + np.exp(-f)); g = p - y; h = p * (1 - p)
            tree = self._grow(B, g, h, np.arange(n), 0)
            self.trees.append(tree)
            f += self.lr * self._pred_tree(tree, B)
        return self

    def _grow(self, B, g, h, idx, depth):
        G, H = g[idx].sum(), h[idx].sum()
        leaf = ('leaf', -G / (H + self.lam))
        if depth >= self.d or len(idx) < 2 * self.ml:
            return leaf
        best = (0, None)
        base = G * G / (H + self.lam)
        for j in range(B.shape[1]):
            b = B[idx, j]
            gs = np.bincount(b, g[idx], self.nb + 1); hs = np.bincount(b, h[idx], self.nb + 1); cs = np.bincount(b, minlength=self.nb + 1)
            gl, hl, cl = np.cumsum(gs)[:-1], np.cumsum(hs)[:-1], np.cumsum(cs)[:-1]
            ok = (cl >= self.ml) & (len(idx) - cl >= self.ml)
            if not ok.any():
                continue
            gain = gl ** 2 / (hl + self.lam) + (G - gl) ** 2 / (H - hl + self.lam) - base
            gain[~ok] = -1
            k = int(np.argmax(gain))
            if gain[k] > best[0]:
                best = (gain[k], (j, k))
        if best[1] is None:
            return leaf
        j, k = best[1]
        self.gain[j] += best[0]
        m = B[idx, j] <= k
        return ('split', j, k, self._grow(B, g, h, idx[m], depth + 1), self._grow(B, g, h, idx[~m], depth + 1))

    def _pred_tree(self, t, B):
        out = np.zeros(len(B))
        stack = [(t, np.arange(len(B)))]
        while stack:
            node, idx = stack.pop()
            if node[0] == 'leaf':
                out[idx] = node[1]; continue
            _, j, k, l, r = node
            m = B[idx, j] <= k
            stack.append((l, idx[m])); stack.append((r, idx[~m]))
        return out

    def predict(self, X):
        B = self._bin(X)
        f = np.full(len(B), self.f0)
        for t in self.trees:
            f += self.lr * self._pred_tree(t, B)
        return f > 0


def two_sample(X0, X1, g0, g1, seed=0, folds=5):
    """Held-out accuracy of telling X0 from X1, grouped CV over blocks; 95% interval by block bootstrap."""
    X = np.vstack([X0, X1]); y = np.r_[np.zeros(len(X0)), np.ones(len(X1))]; grp = np.r_[g0, g1]
    u = np.unique(grp); rng = np.random.default_rng(seed)
    fold_of = dict(zip(u, rng.permutation(len(u)) % folds))
    fo = np.array([fold_of[x] for x in grp])
    correct = np.zeros(len(y), bool); gain = np.zeros(X.shape[1])
    for k in range(folds):
        tr, te = fo != k, fo == k
        m = GBM().fit(X[tr], y[tr])
        correct[te] = m.predict(X[te]) == y[te]
        gain += m.gain
    # Balanced accuracy: mean recall of the two classes, so a fold's class mix cannot move it.
    gi = np.searchsorted(u, grp)
    c = [np.bincount(gi[y == k], correct[y == k], len(u)) for k in (0, 1)]
    n = [np.bincount(gi[y == k], minlength=len(u)) for k in (0, 1)]
    bal = lambda w: 0.5 * sum((w * c[k]).sum() / max((w * n[k]).sum(), 1) for k in (0, 1))
    bs = [bal(np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))) for _ in range(1000)]
    imp = gain / gain.sum()
    top = sorted(zip(NAMES, imp), key=lambda r: -r[1])[:6]
    return dict(accuracy=float(bal(np.ones(len(u)))), raw_accuracy=float(correct.mean()), ci95=[float(x) for x in np.percentile(bs, [2.5, 97.5])], n=[int(len(X0)), int(len(X1))],
                blocks=int(len(u)), top_features={n: round(float(v), 3) for n, v in top})


def main():
    w = np.load(f'{D}/windows.npz')
    s, v, vl = w['s'].astype(float), w['v'].astype(float), w['vl'].astype(float)
    N = s.shape[1]
    xf = np.vstack([np.zeros((1, N)), np.cumsum((v[1:] + v[:-1]) * 0.05, 0)]); xl = xf + s
    blk = np.array([f'{r}:{int(t // 60)}' for r, t in zip(w['run'], w['t'])])  # 60 s chunks: the day has only 7 blocks of 300 s
    rng = np.random.default_rng(3)
    sigma = tracker_noise(xl - xf)
    sR, vR, vlR = instrument(xf, xl, 0.0, rng)
    XR = feats(sR, vR, vlR); gR = np.tile(blk, 3); runR = np.tile(w['run'], 3)
    res = dict(tracker_leftover_noise_m=sigma, features=list(NAMES))
    # F102: real against real. Exchangeable halves (blocks drawn at random), and the harder one: other runs, other times.
    ub = np.unique(blk); reps = []
    for rep in range(5):
        half = dict(zip(ub, rng.permutation(len(ub)) % 2)); h = np.array([half[b] for b in gR])
        reps.append(two_sample(XR[h == 0], XR[h == 1], gR[h == 0], gR[h == 1], seed=rep))
    acc = [r['accuracy'] for r in reps]
    res['F102_real_vs_real_random_halves'] = dict(accuracy_mean=float(np.mean(acc)), accuracy_each=acc, ci95_each=[r['ci95'] for r in reps], top_features_first=reps[0]['top_features'])
    a = np.isin(runR, [1, 2])
    res['real_vs_real_runs_1_2_vs_3_4'] = two_sample(XR[a], XR[~a], gR[a], gR[~a])
    print(json.dumps(res, indent=1), flush=True)
    for tag in ('main_s0', 'sumo_s0'):
        p = f'{D}/{tag}.roll.npz'
        if not os.path.exists(p):
            continue
        r = np.load(p); S, V = r['S'].astype(float), r['V'].astype(float)
        ok = np.isfinite(S).all(0) & np.isfinite(V).all(0)
        xfs = np.vstack([np.zeros((1, N)), np.cumsum((V[1:] + V[:-1]) * 0.05, 0)])
        xls = xfs + S
        k = np.tile(ok, 3)
        sS, vS, vlS = instrument(xfs[:, ok], xls[:, ok], sigma, rng)
        XS = feats(sS, vS, vlS); gS = np.tile(blk[ok], 3)
        res[f'F103_{tag}_vs_real_instrument'] = two_sample(XR[k], XS, gR[k], gS)
        XS0 = feats(S[:, ok], V[:, ok], vl[:, ok])
        XR0 = feats(s, v, vl)
        res[f'F106_{tag}_vs_real_no_instrument'] = two_sample(XR0[k], XS0, gR[k], gS)
        print(tag, json.dumps({x: res[x] for x in res if tag in x}, indent=1), flush=True)
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay/classifier.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
