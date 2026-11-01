#!/usr/bin/env python3
"""Items 1-8 of research/truth/05-real-human-driving.md section 9, on the GPU kernel.

    nix develop --command python3 scripts/human_replay.py --out DIR [--dt 0.1] [--seeds 3]

Same frozen windows and chains as the report's Python, through `cars human-replay`.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'research/truth/scripts'))
import numpy as np
from opus_common import *
from opus_models import Batch, score
from opus_fit import split
from opus_dyn import chains, wave_lag
import opus_dyn4_helpers as H

SPEC = dict(T=1.30, s0=2.8, amax=1.8)
GAMMA = 1.4832894130646992
CARS = ROOT / 'target/release/cars'
PY_REPLAY = {'I395_late': (5.93, 0.64), 'I90stat_run6': (4.15, 0.57), 'I90mov': (4.00, 0.63), 'HT_late': (11.30, 1.06)}


def veh_row(x, v, a0, lead, T, s0, amax, v0, trip, af=None):
    r = np.zeros(12, dtype=np.float32)
    r[0] = x
    r[1] = v
    r[2] = a0 if af is None else af
    r[5] = a0
    b = r.tobytes()
    a = np.frombuffer(b, dtype=np.uint32).copy()
    a[4] = 0
    a[6] = np.int32(lead).astype(np.uint32)
    f = a.view(np.float32)
    f[7:11] = [T, s0, amax, v0]
    a[11] = trip
    return a


def gpu(veh, rec, samples, steps, dt, sigma, out, **kw):
    vp = out / 'veh.bin'
    rp = out / 'rec.bin'
    op = out / 'out.bin'
    vp.write_bytes(veh.tobytes())
    rp.write_bytes(rec.astype('f4').tobytes())
    flags = []
    for k, x in kw.items():
        flags += [f'--{k.replace("_", "-")}', str(x)] if x is not True else [f'--{k.replace("_", "-")}']
    r = subprocess.run([*( [] if os.environ.get('CARS_ADAPTER') or os.environ.get('CARS_GPU_HELD') else ['flock', '/tmp/cars-gpu.lock']), os.environ.get('CARS_BIN', CARS), 'human-replay', '--veh', vp, '--rec', rp, '--samples', str(samples), '--dt', str(dt), '--steps', str(steps), '--sigma', str(sigma), '--out', op, *flags], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-3000:])
    res = np.fromfile(op, dtype='f4').reshape(steps + 1, veh.shape[0], 2)
    return res, json.loads(r.stdout.strip().splitlines()[-1])


def replay(out, dt, len_guard):
    tr, va, te = split(False)
    del tr
    res = {}
    for name, b in {**te}.items():
        b.meta['vref']
        n = b.N
        T_ = b.T
        rec = np.stack([b.xl, b.vl], axis=-1).transpose(1, 0, 2)  # N, T, 2
        veh = np.stack([veh_row(0.0, b.v[0, i], b.a0[i], -1 - i, SPEC['T'], SPEC['s0'], SPEC['amax'], GAMMA * b.meta['vref'][i], i) for i in range(n)])
        steps = int((T_ - 1) * 0.1 / dt)
        R, g = gpu(veh, rec, T_, steps, dt, 0.0, out, len_guard=len_guard)
        k = max(1, int(round(dt / 0.1)))
        idx = np.arange(0, T_, k)[:steps + 1]
        S = np.full((T_, 1, n), np.nan)
        V = np.full((T_, 1, n), np.nan)
        xf = R[:, :, 0]
        vf = R[:, :, 1]
        for i in range(n):
            S[:, 0, i] = np.interp(np.arange(T_), idx, b.xl[idx, i] - xf[:len(idx), i])
            V[:, 0, i] = np.interp(np.arange(T_), idx, vf[:len(idx), i])
        sc = score(b, S, V)
        sc['guard_share'] = g['guard_steps'] / max(g['steps'], 1)
        res[name] = sc
        print(name, 'spacing', round(sc['spacing_rmse_30s'], 2), 'speed', round(sc['speed_rmse_30s'], 2), 'overlap', round(sc['collision_frac'], 4), 'guard', round(sc['guard_share'], 4), flush=True)
    return res


def chain_run(out, dt, seeds, len_guard, C):
    Rs = []
    pos = H.pos
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        rows = []
        rec = []
        where = []
        samples = C[0]['V'].shape[1]
        for ci, c in enumerate(C):
            K = c['V'].shape[0]
            xh = np.r_[0, np.cumsum((c['vh'][1:] + c['vh'][:-1]) * .05)]
            rec.append(np.stack([xh, c['vh']], axis=-1))
            x = -np.cumsum(c['S'][:, 0])
            start = len(rows)
            for k in range(K):
                T = float(np.clip(SPEC['T'] * np.exp(rng.normal(0, .25)), .6, 3))
                lead = -1 - ci if k == 0 else start + k - 1
                rows.append(veh_row(x[k], c['V'][k, 0], 0.0, lead, T, SPEC['s0'], SPEC['amax'], GAMMA * 30.0, ci * 100 + k + seed * 100000))
            where.append((start, K))
        veh = np.stack(rows)
        rec = np.stack(rec)
        steps = int((samples - 1) * 0.1 / dt)
        R, g = gpu(veh, rec, samples, steps, dt, 0.20, out, len_guard=len_guard)
        k = max(1, int(round(dt / 0.1)))
        idx = np.arange(0, samples, k)[:steps + 1]
        Vo, So, wv, ev, es = [], [], [], [], []
        overlaps = 0
        for (start, K), c in zip(where, C):
            xr = R[:, start:start + K, 0]
            vr_ = R[:, start:start + K, 1]
            xh = np.r_[0, np.cumsum((c['vh'][1:] + c['vh'][:-1]) * .05)]
            lx = np.vstack([xh[idx], xr[:len(idx), :-1].T]).T
            Sg = lx - xr[:len(idx)]
            VO = np.array([np.interp(np.arange(samples), idx, vr_[:len(idx), j]) for j in range(K)])
            SO = np.array([np.interp(np.arange(samples), idx, Sg[:, j]) for j in range(K)])
            Vo.append(VO)
            So.append(SO)
            ev.append(((VO - c['V']) ** 2).mean(1))
            es.append(((SO - c['S']) ** 2).mean(1))
            overlaps += int((SO.min(1) < 3.05).sum())
            tl = wave_lag(np.vstack([c['vh'], VO]))
            if tl:
                wv.append(SO.mean() / np.median(tl) * 3.6)
        Rs.append(dict(sd=H.prof(Vo), tg=H.tgq(So, Vo), wave=float(np.median(wv)), overlaps=overlaps, guard=g['guard_steps'] / max(g['steps'], 1), followers=len(rows), v={p: float(np.sqrt(np.mean([e[p - 1] for e in ev if len(e) >= p]))) for p in pos}, s={p: float(np.sqrt(np.mean([e[p - 1] for e in es if len(e) >= p]))) for p in pos}))
        print('chains seed', seed, {k: Rs[-1][k] for k in ('wave', 'overlaps', 'guard')}, 'sd', [round(Rs[-1]['sd'][p], 2) for p in (1, 4, 8)], 'tg', [round(Rs[-1]['tg'][q], 2) for q in ('p05', 'p50', 'p95')], flush=True)
    return dict(sd={p: float(np.mean([x['sd'][p] for x in Rs])) for p in pos}, tg={k: float(np.mean([x['tg'][k] for x in Rs])) for k in Rs[0]['tg']}, wave=float(np.mean([x['wave'] for x in Rs])), overlaps=float(np.mean([x['overlaps'] for x in Rs])), guard=float(np.mean([x['guard'] for x in Rs])), followers=Rs[0]['followers'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='/tmp/human-replay')
    p.add_argument('--dt', type=float, default=0.1)
    p.add_argument('--seeds', type=int, default=3)
    p.add_argument('--len-guard', type=float, default=3.0)
    p.add_argument('--skip-windows', action='store_true')
    p.add_argument('--skip-chains', action='store_true')
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    result = {}
    if not a.skip_windows:
        result['replay'] = replay(out, a.dt, a.len_guard)
    if not a.skip_chains:
        C = H.heldout_chains()
        print('chains', len(C), 'followers', sum(c['V'].shape[0] for c in C), flush=True)
        result['chains'] = chain_run(out, a.dt, a.seeds, a.len_guard, C)
    (out / f'replay_dt{a.dt}_g{a.len_guard}.json').write_text(json.dumps(result, indent=1, default=float))
    print(json.dumps(result.get('chains', {}), default=float))


if __name__ == '__main__':
    main()
