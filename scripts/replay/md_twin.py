"""F307: the measured driver's kernel against its Python twin, one follower behind its replayed leader (f101.py windows of
a site that is not held out). Noise, the personal time gap and the desired speed spread are off, the engine nominal, so
both sides are deterministic. The twin has the harness's order: the plan sees the leader where the recording has it at
the start of the step, and its acceleration as the slope of the key interval it is in.

    F101_SITE=I294L1 F101_MAXN=1000 python3 -I scripts/replay/f101.py build
    F101_SITE=I294L1 python3 -I scripts/replay/md_twin.py [--gpu]
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(REPO, 'scripts', 'measure'))
os.environ.setdefault('F101_SITE', 'I294L1')
import f101
from rpl import run_cars
import numpy as np, pandas as pd
import fit_driver as FD

J = json.load(open(FD.OUTJ))['pooled']
P = [J['K'], J['c_a'], J['k_g'], J['k_p']]
DT, L = 0.1, 5.0
BIND = []


def ph_force(u, mu=0.85):
    pw = 0.775 * 90000 / 1650; load = 0.25 + 110 / 146; power = 0.5 + 64 / 127.5
    return (1 / 1.05) * (np.minimum(pw * power / (load * np.maximum(u, 10.0)), mu * 0.55 * 9.81) - 0.0105 * 9.81 - 0.5 * 1.225 * 0.68 / 1650 * u * u / load)


def a_cap(v):
    return ph_force(v + 0.5 * np.maximum(ph_force(v), 0) * DT)


def stop_comfort(gap, v):
    g = np.maximum(gap, 0.0)
    v1 = 1.2 * np.maximum(g - v * DT, 0) ** 0.6
    v2 = 1.2 * np.maximum(g - 0.5 * (v + v1) * DT, 0) ** 0.6
    late = v - DT * np.maximum(2.2, 1.1 * v * v / (2 * np.maximum(g, 0.1)))
    return np.where(g <= 0.1, 0.0, np.minimum(np.maximum(v2, late), np.maximum(g - v * DT * 0.5, 0) / DT))


def cert(gb, v, vl, a_prev, b=8.3, t_r=0.3):
    """ph_v_cert with the leader assumed to brake no harder than this driver (8.3 m/s2 on dry road)."""
    along = vl * vl / (2 * b)
    jerk = b / t_r if DT >= t_r else b / (t_r + DT)
    d_lo = np.maximum(0, -a_prev - jerk * DT); lam = np.maximum(0, 1 - d_lo / b)
    h = (t_r * lam * lam + DT) * 0.5
    q = gb - 0.5 + along - v * DT * 0.5
    return b * (-h + np.sqrt(h * h + 2 * np.maximum(q, 0) / b))


def twin(w, x0, xl, vl, v0):
    N = xl.shape[1]; W = xl.shape[0]
    beta = 1 - np.exp(-DT / FD.TAU_R)
    x = np.full(N, x0); v = v0.copy(); a = np.zeros(N); steps = np.zeros(N, int)
    al = np.vstack([np.diff(vl, axis=0) / DT, np.zeros((1, N))])
    X = [x.copy()]; V = [v.copy()]
    vdes = float(w['vref'])
    for k in range(W - 1):
        g = xl[k] - L - x
        cmd = FD.command(v, g, vl[k], al[k], P, a_cap=np.full(N, 1e9))
        # leader within 100 m in every window: no launch law, the desired speed relaxes in T_v (F311)
        free = np.minimum((vdes - v) / json.load(open(FD.OUTJ))['slow']['T_v'], a_cap(v))
        cmd = np.minimum(cmd, free)
        an = a + beta * (cmd - a)
        vn = np.maximum(v + an * DT, 0.0)
        slow = vl[k] < 0.5 * v
        vn = np.where(slow, np.minimum(vn, stop_comfort(g - FD.S0 + vl[k] ** 2 / 2.6, v)), vn)
        c = cert(g, v, vl[k], a)
        BIND.append(c < vn)
        vn = np.where(c <= 0, -1.0, np.minimum(np.maximum(vn, 0.0), c))
        # exec: the brakes come on and off at a limited rate (ph_floor, ph_release)
        jerk = 8.3 / (0.3 + DT)
        floor = v - np.minimum(8.3, np.maximum(0, -a) + 8.3 * DT / (0.3 + DT)) * DT
        release = np.where(a >= 0, 1e9, v + (a + jerk * DT) * DT)
        vn = np.where(vn < 0, floor, np.maximum(np.minimum(vn, release), floor))
        # ph_start_hold: a standing car goes 1.0 s after the way opens, and never while the car ahead stands within 15 m
        stand = v < 0.05
        still = (vl[k] < 1e-3) & (g < 15.0)
        steps = np.where(stand & still, 0, np.where(stand & (vn > 0), steps + 1, steps))
        waited = steps * DT
        held = np.where(still | (steps == 0) | (waited + DT <= 1.0 + 1e-3), 0.0, np.where(waited < 1.0 - 1e-3, vn * (waited + DT - 1.0) / DT, vn))
        vn = np.where(stand, held, vn)
        acc = (vn - v) / DT
        vn = np.maximum(vn, 0.0)
        ds = np.where(vn > 0, v * DT + 0.5 * acc * DT * DT, np.where(acc < 0, v * v / (2 * np.maximum(-acc, 1e-9)), 0.0))
        a = np.where(vn > 0, acc, 0.0)
        x = x + ds; v = vn
        X.append(x.copy()); V.append(v.copy())
    return np.array(X), np.array(V)


def main(gpu=False):
    D = f101.D
    w = np.load(f'{D}/windows.npz')
    # The kernel side: nominal engine, everything random off.
    src = open(f'{D}/routes_main.xml').read()
    src = src.replace('<vType id="drv" carFollowModel="Krauss"/>', '<vType id="drv" carFollowModel="Krauss"><param key="phys.nominal" value="1"/></vType>')
    open(f'{D}/routes_twin.xml', 'w').write(src)
    out = f'{D}/twin'
    run_cars(['--net', f'{D}/net.xml', '--routes', f'{D}/routes_twin.xml', '--replay', f'{D}/windows.rpl', '--dt', '0.1', '--begin', 0,
              '--end', f101.T0 + f101.W * 0.1, '--seed', 0, '--time-to-teleport', '0', '--fcd', f'{out}.fcd.csv', '--fcd-begin', f101.T0 - 0.05,
              '--fcd-interval', '0.1', '--tune', 'measured=1', '--tune', 'md_noise=0', '--tune', 'md_gap_sd=0', '--tune', 'md_speed_dev=0'], gpu=gpu, log=f'{out}.log')
    f101.rollout(out)
    r = np.load(f'{out}.roll.npz'); S, V = r['S'], r['V']
    # The twin from the same leader track the harness replays.
    import rpl
    b = f101.windows()
    xl = f101.X0 + b.xl[:f101.W]; vl = b.vl[:f101.W]
    X, Vt = twin(w, f101.X0, xl, vl, b.v[0].astype(float))
    St = xl - X
    ok = np.isfinite(S).all(0) & np.isfinite(V).all(0)
    dv = V[:, ok] - Vt[:, ok]; ds = S[:, ok] - St[:, ok]
    res = dict(windows=int(len(ok)), compared=int(ok.sum()), speed_rms_diff=float(np.sqrt(np.mean(dv ** 2))), speed_max_diff=float(np.abs(dv).max()),
               spacing_rms_diff=float(np.sqrt(np.mean(ds ** 2))), spacing_max_diff=float(np.abs(ds).max()),
               worst_window=int(np.flatnonzero(ok)[np.argmax(np.abs(dv).max(0))]),
               certificate_decides_share_of_steps=float(np.mean(BIND)), windows_where_it_decides=float(np.mean(np.array(BIND).any(0))))
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay/md_twin.json'), 'w'), indent=1)
    np.savez(f'{out}.cmp.npz', V=V, Vt=Vt, S=S, St=St)


if __name__ == '__main__':
    main(gpu='--gpu' in sys.argv)
