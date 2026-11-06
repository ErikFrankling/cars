"""Round 2 of the measured driver, part 4: command noise with the instrument's noise taken out (F615, F616).

F615. Round 1's residual of the next-second speed change (model_fit.json 'residual': SD and autocorrelation at 1, 2, 3,
5 s, per table) is split into two parts:
  driver       Ornstein-Uhlenbeck command noise (sigma_n, tau_n) through the 0.5 s first-order response, as the kernel has it
  instrument   an error in the recorded speed with its own correlation time tau_m; a one-second change of it has a
               negative lag-1 autocorrelation (-0.5 when white)
The three shape numbers (driver share of the variance, tau_n, tau_m) are fitted to the four autocorrelations of each
table; sigma_n follows from the SD and the driver share.

F616. The recorded speed of cars about a 2 s local quadratic of the same track (follower tables, 5 Hz): what the
tracker adds on 0.2-1 s scales.

    python3 -I scripts/measure/noise2.py      # -> research/truth/measure/noise2.json
"""
import os, sys, json
import numpy as np
from scipy.optimize import least_squares
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fit_driver as FD
import follow as F

OUT = os.path.join(FD.RES, 'noise2.json')
LAGS = (1, 2, 3, 5)


def driver_acf(tn, dt=0.05, n=6000, seed=3):
    """SD per unit sigma and autocorrelation at LAGS of the one-second speed change from OU command noise through the
    0.5 s response (the kernel's averaging of the noise over a step)."""
    steps = int(14 / dt); rho = np.exp(-dt / tn); beta = 1 - np.exp(-dt / FD.TAU_R)
    scale = np.sqrt(2 * (tn / dt) ** 2 * (dt / tn - 1 + np.exp(-dt / tn)))
    x = np.zeros(n); a = np.zeros(n); v = np.zeros(n); vs = []
    z = np.random.default_rng(seed).standard_normal((steps, n))
    per = int(round(1 / dt))
    for k in range(steps):
        x = rho * x + np.sqrt(1 - rho * rho) * z[k]
        a = a + beta * (scale * x - a); v = v + a * dt
        if k % per == 0:
            vs.append(v.copy())
    dv = np.diff(np.array(vs)[3:], axis=0)
    sd = dv.std()
    acf = [np.mean([np.corrcoef(dv[j], dv[j + L])[0, 1] for j in range(len(dv) - L)]) for L in LAGS]
    return sd, np.array(acf)


def instr_acf(tm):
    """Autocorrelation of one-second changes of a speed error with exponential autocorrelation exp(-|t|/tm)."""
    r = lambda L: np.exp(-abs(L) / max(tm, 1e-6))
    den = 2 * (1 - r(1))
    return np.array([(2 * r(L) - r(L - 1) - r(L + 1)) / den for L in LAGS])


def main():
    J = json.load(open(FD.OUTJ))['residual']
    grid_tn = (0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)
    D = {tn: driver_acf(tn) for tn in grid_tn}
    out = {'per_table': {}}
    for name, r in J.items():
        sd = r['sd_1s_speed_change']
        acf = np.array([r['autocorr_by_lag_s'][str(L)] for L in LAGS])
        best = None
        for tn in grid_tn:
            s1, ad = D[tn]
            for tm in (0.01, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5):
                ai = instr_acf(tm)
                for w in np.linspace(0, 1, 101):
                    pred = w * ad + (1 - w) * ai
                    err = float(np.sum((pred - acf) ** 2))
                    if best is None or err < best[0]:
                        best = (err, tn, tm, w, s1, pred)
        err, tn, tm, w, s1, pred = best
        out['per_table'][name] = dict(residual_sd=sd, acf=acf.round(3).tolist(), fit_acf=np.round(pred, 3).tolist(), sse=round(err, 4),
                                      driver_share=round(float(w), 2), tau_n=tn, tau_m=tm,
                                      sigma_n=round(float(np.sqrt(w) * sd / s1), 3),
                                      instrument_sd_of_1s_change=round(float(np.sqrt(1 - w) * sd), 3))
        print(name, out['per_table'][name], flush=True)
    # F616: recorded speed about a 2 s local quadratic, cars at 5-30 m/s, per table.
    trk = {}
    for name in F.DSETS:
        d = F.load(name)
        seg = d.seg.to_numpy(); v = d.vf.to_numpy(float)
        cut = np.flatnonzero(np.diff(seg)) + 1
        res = []
        for b, e in zip(np.r_[0, cut], np.r_[cut, len(v)]):
            if e - b >= 25:
                sm = savgol_filter(v[b:e], 11, 2)
                res.append((v[b:e] - sm)[5:-5])
            if len(res) > 20000:
                break
        x = np.concatenate(res)
        trk[name] = dict(sd_m_s=round(float(np.std(x)), 4), mad_sd=round(float(1.4826 * np.median(np.abs(x - np.median(x)))), 4), samples=int(len(x)))
        print(name, trk[name], flush=True)
    out['speed_about_2s_quadratic'] = trk
    tabs = out['per_table']
    out['driver_noise_pooled'] = dict(sigma_n_median=float(np.median([t['sigma_n'] for t in tabs.values()])),
                                      tau_n_median=float(np.median([t['tau_n'] for t in tabs.values()])))
    json.dump(out, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
