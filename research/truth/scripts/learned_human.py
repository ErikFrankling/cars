#!/usr/bin/env python3
"""A 212-float network imitating real followers, scored as the human-model tournament scores its candidates.

Windows: research/truth/human-v2 split (TGSIM and DLR HT pairs, 30 s, 0.1 s). Leaders are replayed.
  nix develop --command python3 -I research/truth/scripts/learned_human.py es --tag ...
  <torch env>/bin/python3 -I research/truth/scripts/learned_human.py bc --tag ...
  ... eval a.npz b.npz --out name
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import learned_drivers as ld  # noqa: E402

SPLIT = Path("/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-heavy/cache/split_all.pkl")
L_EFF = 5.0
DT = 0.1
USE_VREF = False  # set by --vref: lets the network see each site's free speed, as the fitted models do


def load():
    return pickle.load(open(SPLIT, "rb"))


def features(v, vl, gap, a_prev, vref=0.0):
    o = np.zeros(v.shape + (ld.IN,))
    o[..., 5] = vref / 30.0
    o[..., 0] = v / 20.0
    o[..., 1] = vl / 20.0
    o[..., 2] = np.minimum(np.maximum(gap, 0.0), 40.0) / 40.0
    o[..., 3] = (vl - v) / 5.0
    o[..., 4] = 1.0
    o[..., 11] = a_prev / ld.A_MAX
    return o


def rollout(theta, w, idx=None, stride=1):
    """theta [P,D]. Returns spacing and speed arrays [T,P,N]; first state and leader come from data."""
    s, v, vl = w["s"], w["v"], w["vl"]
    if idx is not None:
        s, v, vl = s[:, idx], v[:, idx], vl[:, idx]
    T, N = s.shape
    P = theta.shape[0]
    vref = w["meta"]["vref"][idx] if idx is not None else w["meta"]["vref"]
    vref = vref if USE_VREF else 0.0
    net = ld.Net(theta)
    xf = np.vstack([np.zeros((1, N)), np.cumsum((v[1:] + v[:-1]) * 0.5 * DT, axis=0)])
    xl = xf + s
    vs = np.tile(v[0].astype(np.float64), (P, 1))
    x = np.zeros((P, N))
    a = np.tile(w["a0"][idx] if idx is not None else w["a0"], (P, 1)).astype(np.float64)
    S = np.empty((T // stride + 1, P, N), np.float32)
    V = np.empty_like(S)
    for t in range(T):
        sp = xl[t] - x
        if t % stride == 0:
            S[t // stride], V[t // stride] = sp, vs
        o = features(vs, np.broadcast_to(vl[t], vs.shape), sp - L_EFF, a, vref)
        a = np.maximum(ld.out_to_accel(net(o)[..., 0]), -9.0)
        v1 = np.maximum(vs + a * DT, 0.0)
        a = (v1 - vs) / DT
        x += 0.5 * (vs + v1) * DT
        vs = v1
    return S[: T // stride], V[: T // stride]


def objective(theta, w, idx):
    S, V = rollout(theta, w, idx, stride=5)
    s = w["s"][::5, :][: S.shape[0]][:, idx][:, None, :]
    v = w["v"][::5, :][: S.shape[0]][:, idx][:, None, :]
    es = np.sqrt(np.mean((S - s) ** 2, axis=(0, 2)))
    ev = np.sqrt(np.mean((V - v) ** 2, axis=(0, 2)))
    bad = np.mean(S.min(axis=0) < L_EFF * 0.6 + 0.05, axis=1)
    return -(es + 2.0 * ev) - 50.0 * bad


def score(theta, w):
    S, V = rollout(theta[None], w)
    S, V = S[:, 0], V[:, 0]
    out = {}
    for h in (5, 10, 30):
        k = int(h / DT)
        out[f"spacing_rmse_{h}s"] = float(np.sqrt(np.nanmean((S[:k] - w["s"][:k]) ** 2)))
        out[f"speed_rmse_{h}s"] = float(np.sqrt(np.nanmean((V[:k] - w["v"][:k]) ** 2)))
    out["collision_frac"] = float(np.mean(np.nanmin(S, axis=0) < L_EFF * 0.6 + 0.05))
    return out


def cmd_es(a):
    global USE_VREF
    USE_VREF = a.vref
    d = load()
    tr, va = d["train"], d["val"]
    N = tr["s"].shape[1]
    rng = np.random.default_rng(a.seed)
    vidx = np.arange(va["s"].shape[1])

    def ro(th, seed):
        idx = np.random.default_rng(seed).choice(N, a.batch, replace=False)
        return objective(th, tr, idx), th.shape[0] * a.batch * tr["s"].shape[0]

    def val(th):
        s = score(th, va)
        return dict(score=-(s["spacing_rmse_30s"] + 2 * s["speed_rmse_30s"]) - 50 * s["collision_frac"], **s)

    def log(curve, best):
        np.savez(ld.OUT / f"{a.tag}.npz", theta=best, curve=json.dumps(curve), args=json.dumps(ld.argd(a)))

    best, curve = ld.es_train(ro, a.seed, a.gens, a.pairs, a.sigma, a.lr, a.eval_every, val, log=log)
    log(curve, best)


def cmd_bc(a):
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(a.seed)
    d = load()
    tr = d["train"]
    s, v, vl = tr["s"], tr["v"], tr["vl"]
    acc = np.diff(v, axis=0) / DT
    # Measured acceleration is noisy: smooth over 1 s before fitting, standard for these tracks.
    ker = np.ones(10) / 10
    acc = np.apply_along_axis(lambda x: np.convolve(x, ker, mode="same"), 0, acc)
    prev = np.vstack([acc[:1], acc[:-1]])
    o = features(v[:-1], vl[:-1], s[:-1] - L_EFF, prev).reshape(-1, ld.IN)
    y = acc.reshape(-1)
    pick = np.random.default_rng(a.seed).choice(o.shape[0], min(600000, o.shape[0]), replace=False)
    X, Y = torch.as_tensor(o[pick], dtype=torch.float32), torch.as_tensor(y[pick], dtype=torch.float32)
    H, IN, NO = ld.HID, ld.IN, ld.NOUT
    net = torch.nn.Sequential(torch.nn.Linear(IN, H), torch.nn.Tanh(), torch.nn.Linear(H, H), torch.nn.Tanh(), torch.nn.Linear(H, NO))
    opt = torch.optim.Adam(net.parameters(), lr=2e-3)
    t0 = time.time()
    for ep in range(a.epochs):
        perm = torch.randperm(X.shape[0])
        tot = 0.0
        for b in range(0, X.shape[0], 4096):
            ix = perm[b : b + 4096]
            x = torch.tanh(net(X[ix])[..., 0])
            pred = torch.where(x >= 0, ld.A_MAX * x, ld.B_POLICY * x)
            loss = ((pred - Y[ix]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss.detach()) * ix.shape[0]
        print(ep, tot / X.shape[0], time.time() - t0, flush=True)
    sd = net.state_dict()
    theta = np.concatenate([sd[k].numpy().ravel() for k in ("0.weight", "0.bias", "2.weight", "2.bias", "4.weight", "4.bias")])
    np.savez(ld.OUT / f"{a.tag}.npz", theta=theta, curve="[]", args=json.dumps(ld.argd(a)))


def ring_closed_loop(theta, n=22, length=260.0, horizon=600.0, R=16, seed=4242, b_h=None):
    """Every car in a ring is this network, starting from uniform flow with small noise."""
    gap0 = length / n - 5.0
    rng = np.random.default_rng(seed)
    x = np.tile(np.arange(n) * (length / n), (R, 1)) + rng.normal(0, 0.1, (R, n))
    v = np.full((R, n), 6.0)
    a = np.zeros((R, n))
    net = ld.Net(np.tile(theta, (R, 1)))
    alive = np.ones(R, bool)
    sds, vs = [], []
    steps = int(horizon / DT)
    for t in range(steps):
        lead = np.roll(x, -1, axis=1)
        vl = np.roll(v, -1, axis=1)
        gap = lead - x - 5.0
        gap[:, -1] += length
        hit = (gap < 0).any(axis=1)
        alive &= ~hit
        o = features(v, vl, gap, a, 25.0 if USE_VREF else 0.0)
        acc = np.maximum(ld.out_to_accel(net(o)[..., 0]) + rng.normal(0, 0.2, (R, n)), -9.0)
        v1 = np.maximum(v + acc * DT, 0.0)
        a = (v1 - v) / DT
        x = x + 0.5 * (v + v1) * DT
        v = v1
        if t * DT > 200:
            sds.append(v.std(axis=1, ddof=1))
            vs.append(v.mean(axis=1))
    sd = np.mean(sds, axis=0)
    mv = np.mean(vs, axis=0)
    return dict(survived=float(alive.mean()), speed=float(mv[alive].mean()) if alive.any() else None, flow=float(mv[alive].mean() * n / length * 3600) if alive.any() else None, sd=float(sd[alive].mean()) if alive.any() else None)


def cmd_eval(a):
    global USE_VREF
    d = load()
    splits = dict(train=d["train"], val=d["val"], **d["test"])
    res = {}
    for path in a.policies:
        z = np.load(path)
        tag = Path(path).stem
        USE_VREF = bool(json.loads(str(z["args"])).get("vref", False))
        res[tag] = {k: score(z["theta"], w) for k, w in splits.items()}
        res[tag]["ring"] = ring_closed_loop(z["theta"])
        print(tag, json.dumps({k: (round(v["spacing_rmse_30s"], 2), round(v["speed_rmse_30s"], 2), round(v["collision_frac"], 4)) for k, v in res[tag].items() if k != "ring"}), res[tag]["ring"], flush=True)
    p = ld.OUT / f"{a.out}.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(res)
    p.write_text(json.dumps(old, indent=1))


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("es"); e.set_defaults(fn=cmd_es)
    e.add_argument("--tag", required=True); e.add_argument("--seed", type=int, default=0)
    e.add_argument("--gens", type=int, default=200); e.add_argument("--pairs", type=int, default=32)
    e.add_argument("--batch", type=int, default=400); e.add_argument("--sigma", type=float, default=0.05)
    e.add_argument("--lr", type=float, default=0.02); e.add_argument("--vref", action="store_true"); e.add_argument("--eval-every", type=int, default=25)
    b = sp.add_parser("bc"); b.set_defaults(fn=cmd_bc)
    b.add_argument("--tag", required=True); b.add_argument("--seed", type=int, default=0); b.add_argument("--epochs", type=int, default=20)
    v = sp.add_parser("eval"); v.set_defaults(fn=cmd_eval)
    v.add_argument("policies", nargs="*"); v.add_argument("--out", required=True)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
