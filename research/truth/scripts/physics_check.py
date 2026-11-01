#!/usr/bin/env python3
"""Checks every equation in research/truth/11-vehicle-physics.md against published figures.

Usage: physics_check.py SRC_DIR OUT_JSON FIG_DIR
SRC_DIR holds greenncap.txt (WLTC tables, pdftotext -layout), wltc_au.html, tcl25.xlsx.
"""
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

G = 9.81
RHO = 1.225
KMH = 1 / 3.6
MPH = 0.44704
FT = 0.3048
LB = 0.45359237
HP = 745.7
SRC, OUT, FIG = sys.argv[1:4]
R = {}


# ---- capability model -------------------------------------------------------------------
class Veh:
    """rho_cda_m, crr: road load. p_m: effective wheel power per kg. a_launch: tyre or torque cap."""

    def __init__(s, name, m, p_kw, cda, crr, a_launch, kappa, b=8.5, t_r=0.15, inertia=1.05):
        s.name, s.m, s.p, s.cda, s.crr, s.a0, s.kappa, s.b, s.t_r, s.i = name, m, p_kw * 1e3, cda, crr, a_launch, kappa, b, t_r, inertia

    def a_cap(s, v, grade=0.0, mu=None):
        """Maximum forward acceleration at speed v, grade tan(theta). One sqrt-free closed form."""
        f_p = s.kappa * s.p / (s.m * max(v, 0.5))
        a = s.a0 if mu is None else min(s.a0, mu * s.drive_frac() * G)
        drive = min(a, f_p)
        road = (s.crr * G + 0.5 * RHO * s.cda * v * v / s.m) * math.cos(math.atan(grade))
        return (drive - road) / s.i - G * math.sin(math.atan(grade))

    def drive_frac(s):
        return 0.55

    def b_cap(s, grade=0.0, mu=1.1):
        return min(s.b, mu * G) + G * math.sin(math.atan(grade))


def launch(kappa, p_kw, m, f_d, mu=1.0, v_c=10.0):
    """Force plateau below corner speed v_c, capped by the driven axles' grip."""
    return min(kappa * p_kw * 1e3 / (m * v_c), mu * f_d * G)


def integrate(veh, v_target, dt=0.01, method="heun", grade=0.0):
    t, v, x = 0.0, 0.0, 0.0
    while v < v_target and t < 400:
        a0 = veh.a_cap(v, grade)
        if a0 <= 1e-4:
            return float("inf"), x
        if method == "heun":
            a = veh.a_cap(v + 0.5 * a0 * dt, grade)
        else:
            a = a0
        if v + a * dt >= v_target:
            h = (v_target - v) / a
            x += v * h + 0.5 * a * h * h
            return t + h, x
        x += v * dt + 0.5 * a * dt * dt
        v += a * dt
        t += dt
    return t, x


# ---- 1. value checks ---------------------------------------------------------------------
def nhtsa_d(v, b, tr):
    return v * tr / 2 + v * v / (2 * b) - b * tr * tr / 24


def check_values():
    out = {}
    adac = {"dry 100": (100, 43.3, 46.5), "wet asphalt 80": (80, 35.1, 40.7), "wet concrete 80": (80, 38.5, 46.6), "snow 30": (30, 9.9, 11.0), "ice 20": (20, 18.3, 21.6)}
    out["adac_b"] = {k: [round((v * KMH) ** 2 / (2 * d), 3) for d in (d0, d1)] for k, (v, d0, d1) in adac.items()}
    out["adac_mu"] = {k: [round(x / G, 3) for x in vs] for k, vs in out["adac_b"].items()}
    # 74 FR 37122 Table I: 16.8 ft/s2, 0.45 s; column checked against the published stopping distances
    rows = [(45, 144), (50, 176), (55, 212), (60, 250)]
    out["nhtsa_table1"] = [{"mph": m, "published_ft": d, "formula_ft": round(nhtsa_d(m * 88 / 60, 16.8, 0.45), 1)} for m, d in rows]
    # Numerical integration of linear ramp, to prove the 1/24 term
    v0, b, tr, h = 26.8224, 5.12, 0.45, 1e-4
    t, v, x = 0.0, v0, 0.0
    while v > 0:
        a = -b * min(t / tr, 1.0)
        x += v * h + 0.5 * a * h * h
        v += a * h
        t += h
    out["nhtsa_ramp_numeric_vs_formula_m"] = [round(x, 3), round(nhtsa_d(v0, b, tr), 3)]
    tests = {"Sterling+braked trailer 186 ft": (186, 0.78, 0.5), "Volvo+control trailer 249 ft": (249, 0.45, 0.4), "Peterbilt+control trailer 250 ft": (250, 0.52, 0.45)}
    out["nhtsa_vs_plots"] = {}
    for k, (ft, g, tr) in tests.items():
        v0 = 60 * MPH
        d = nhtsa_d(v0, g * G, tr) / FT
        # mean steady deceleration needed to reproduce the published distance with that rise
        lo, hi = 1.0, 12.0
        for _ in range(60):
            m = (lo + hi) / 2
            if nhtsa_d(v0, m, tr) > ft * FT:
                lo = m
            else:
                hi = m
        out["nhtsa_vs_plots"][k] = {"plot_g": g, "formula_ft_at_plot_g": round(d, 1), "implied_steady_g": round(hi / G, 3), "implied_steady_mps2": round(hi, 2)}
    # ARBOC measured stopping distances: quadratic fit gives steady b and lag
    v = np.array([20, 30, 40, 45]) * MPH
    d = np.array([23.19, 49.40, 82.05, 101.31]) * FT
    A = np.c_[v / 2, v * v / 2]
    (tr, inv_b), res, *_ = np.linalg.lstsq(A, d, rcond=None)
    out["altoona_van_brake_fit"] = {"t_r_s": round(float(tr), 3), "b_mps2": round(float(1 / inv_b), 2), "rmse_m": round(float(np.sqrt(np.mean((A @ [tr, inv_b] - d) ** 2))), 3), "published_ft": [23.19, 49.40, 82.05, 101.31]}
    return out


# ---- 2. Quintic and path geometry --------------------------------------------------------
def f5(u):
    return 10 * u**3 - 15 * u**4 + 6 * u**5


def f5inv(y):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if f5(m) < y:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def check_quintic():
    out = {}
    u = np.linspace(0, 1, 2000001)
    D, T = 3.5, 4.0
    d = D * f5(u)
    du = u[1] - u[0]
    v = np.gradient(d, du) / T
    a = np.gradient(v, du) / T
    j = np.gradient(a, du) / T
    out["numeric_peaks_T4"] = {"v": round(float(np.abs(v).max()), 4), "a": round(float(np.abs(a[10:-10]).max()), 4), "j": round(float(np.abs(j[50:-50]).max()), 3)}
    out["closed_forms_T4"] = {"v": 1.875 * D / T, "a": 10 * math.sqrt(3) / 3 * D / T**2, "j": 60 * D / T**3}
    out["endpoint_values"] = {"f(0)": 0.0, "f(1)": float(f5(1.0)), "f'(0)": 0.0, "f'(1)": 30 - 60 + 30, "f''(1)": 60 - 180 + 120, "jerk_at_endpoints_nonzero": 60}
    # Thiemann's window: body entirely in old lane to body entirely in new lane
    rows = []
    for w_lane, w_veh in ((3.5, 1.8), (3.66, 1.8), (3.25, 1.8), (3.5, 2.55)):
        y0 = (w_lane / 2 - w_veh / 2) / w_lane
        frac = 1 - 2 * f5inv(y0)
        rows.append({"lane_m": w_lane, "veh_m": w_veh, "centre_travel_m": w_veh, "occupied_fraction_of_T": round(frac, 3), "T_for_T_occ_4.01": round(4.01 / frac, 1), "T_for_T_occ_3.0": round(3.0 / frac, 1), "peak_vlat_T_occ_4.01": round(1.875 * w_lane / (4.01 / frac), 3), "peak_vlat_T_occ_3.0": round(1.875 * w_lane / (3.0 / frac), 3), "peak_alat_T_occ_3.0": round(5.7735 * w_lane / (3.0 / frac) ** 2, 3)})
    out["occupation"] = rows
    out["T4_occupation_s"] = round(4.0 * rows[0]["occupied_fraction_of_T"], 2)
    out["T6_occupation_s"] = round(6.0 * rows[0]["occupied_fraction_of_T"], 2)
    # 10-90% window of the same polynomial, compared with HIGH-SIM's 5.82 s median in human-lateral-fit.json
    out["ten_ninety_fraction"] = round(f5inv(0.9) - f5inv(0.1), 4)
    shapes = []
    for w_veh in (1.8,):
        y_lo, y_hi = (D - w_veh) / 2, (D + w_veh) / 2
        for T_ in (4.0, 6.28, 10.0, 11.0, 13.8):
            uu = np.linspace(0, 1, 200001)
            dd_ = D * f5(uu)
            tt = uu * T_
            occ = tt[np.argmax(dd_ >= y_hi)] - tt[np.argmax(dd_ >= y_lo)]
            t10 = tt[np.argmax(dd_ >= 0.1 * D)]
            t90 = tt[np.argmax(dd_ >= 0.9 * D)]
            shapes.append({"shape": "quintic", "T_s": T_, "straddle_s": round(float(occ), 2), "t10_90_s": round(float(t90 - t10), 2), "peak_vlat": round(1.875 * D / T_, 3), "peak_alat": round(5.7735 * D / T_**2, 3)})
        for v_lat in (0.45, 0.55, 0.6, 0.7):
            for t_a in (1.0,):
                T_ = D / v_lat + t_a
                n_ = 200001
                tt = np.linspace(0, T_, n_)
                vv = np.minimum.reduce([np.full(n_, v_lat), v_lat * (0.5 - 0.5 * np.cos(np.pi * np.clip(tt / t_a, 0, 1))), v_lat * (0.5 - 0.5 * np.cos(np.pi * np.clip((T_ - tt) / t_a, 0, 1)))])
                dd_ = np.cumsum(vv) * (tt[1] - tt[0])
                occ = tt[np.argmax(dd_ >= y_hi)] - tt[np.argmax(dd_ >= y_lo)]
                t10 = tt[np.argmax(dd_ >= 0.1 * D)]
                t90 = tt[np.argmax(dd_ >= 0.9 * D)]
                shapes.append({"shape": "trapezoid", "T_s": round(T_, 2), "travel_m": round(float(dd_[-1]), 3), "straddle_s": round(float(occ), 2), "t10_90_s": round(float(t90 - t10), 2), "peak_vlat": v_lat, "peak_alat": round(math.pi / 2 * v_lat / t_a, 3)})
    out["shapes"] = shapes
    # curved road inertial acceleration from report, tested by finite differencing a real path
    kap0, kap1 = 0.02, 1e-4
    s = lambda t: 3 * t + 0.1 * t * t
    sd = lambda t: 3 + 0.2 * t
    sdd = 0.2
    dd = lambda t: 0.4 * np.sin(0.5 * t)
    ddd = lambda t: 0.2 * np.cos(0.5 * t)
    dddd = lambda t: -0.1 * np.sin(0.5 * t)
    h = 1e-3
    t = np.arange(0, 20, h)
    ss = s(t)
    k = kap0 + kap1 * ss
    th = kap0 * ss + 0.5 * kap1 * ss * ss
    ds = np.gradient(ss)
    cx = np.cumsum(np.cos(th) * ds)
    cy = np.cumsum(np.sin(th) * ds)
    px = cx - dd(t) * np.sin(th)
    py = cy + dd(t) * np.cos(th)
    ax = np.gradient(np.gradient(px, h), h)
    ay = np.gradient(np.gradient(py, h), h)
    at_num = ax * np.cos(th) + ay * np.sin(th)
    an_num = -ax * np.sin(th) + ay * np.cos(th)
    at = (1 - k * dd(t)) * sdd - kap1 * dd(t) * sd(t) ** 2 - 2 * k * sd(t) * ddd(t)
    an = k * (1 - k * dd(t)) * sd(t) ** 2 + dddd(t)
    out["curvilinear_acc_rms_error"] = {"at": round(float(np.sqrt(np.mean((at - at_num)[100:-100] ** 2))), 5), "an": round(float(np.sqrt(np.mean((an - an_num)[100:-100] ** 2))), 5)}
    # Kinematic feasibility of a lane change across speed
    fe = []
    for v0 in (1, 2, 3, 5, 8, 14, 25):
        for T in (4, 6, 10):
            amax = 5.7735 * 3.5 / T**2
            vy = 1.875 * 3.5 / T
            kap = amax / max(v0 * v0, 1e-3)
            fe.append({"v": v0, "T": T, "heading_deg": round(math.degrees(math.atan2(vy, v0)), 1), "R_min_m": round(1 / kap, 1), "yaw_rate_deg_s": round(math.degrees(amax / v0), 1)})
    out["lane_change_feasibility"] = fe
    return out


# ---- 3. Cars, van, trucks against published figures --------------------------------------
# (name, EU kerb kg, kW, Nm, declared 0-100 s, vmax km/h, kind, a_launch)
CARS = [
    ("Dacia Sandero SCe 65", 1089, 49, 95, 16.7, 158, "ice", 0.55),
    ("VW Golf 1.5 TSI 85 kW", 1307, 85, 220, 9.9, 203, "ice", 0.55),
    ("Volvo XC90 3.2 AWD", 2202, 179, 320, 9.5, 210, "ice", 1.0),
    ("Volvo XC90 T6 AWD", 2060, 228, 400, 6.5, 230, "ice", 1.0),
    ("Tesla Model 3 RWD", 1836, 208, 420, 6.1, 201, "ev", 0.6),
]
CDA_BY = {"Dacia Sandero SCe 65": 0.72, "VW Golf 1.5 TSI 85 kW": 0.63, "Volvo XC90 3.2 AWD": 0.95, "Volvo XC90 T6 AWD": 0.95, "Tesla Model 3 RWD": 0.50}
CRR = 0.011


def mkcar(row, kappa_ice, kappa_ev, extra=100):
    name, m, kw, nm, t100, vmax, kind, f_d = row
    k = kappa_ice if kind == "ice" else kappa_ev
    return Veh(name, m + extra, kw, CDA_BY[name], CRR, launch(k, kw, m + extra, f_d), k)


def cars():
    out = {}
    # fit one kappa per drivetrain across all declared times
    def err(ki, ke):
        tot = 0
        for r in CARS:
            t, _ = integrate(mkcar(r, ki, ke), 100 * KMH)
            tot += (t - r[4]) ** 2 if r[6] == "ice" else 0
        return tot

    ks = np.arange(0.55, 1.0, 0.005)
    ki = ks[np.argmin([err(k, 0.9) for k in ks])]
    t_ev = {k: integrate(mkcar(CARS[4], ki, k), 100 * KMH)[0] for k in ks}
    ke = min(t_ev, key=lambda k: abs(t_ev[k] - 6.1))
    out["kappa_ice"], out["kappa_ev"] = round(float(ki), 3), round(float(ke), 3)
    rows = []
    for r in CARS:
        v = mkcar(r, ki, ke)
        t, _ = integrate(v, 100 * KMH)
        t1, _ = integrate(v, 100 * KMH, dt=1.0, method="heun")
        te, _ = integrate(v, 100 * KMH, dt=1.0, method="euler")
        # leave-one-out on ICE
        if r[6] == "ice":
            def err2(k):
                return sum((integrate(mkcar(q, k, ke), 100 * KMH)[0] - q[4]) ** 2 for q in CARS if q[6] == "ice" and q is not r)
            k2 = ks[np.argmin([err2(k) for k in ks])]
            t_loo = integrate(mkcar(r, k2, ke), 100 * KMH)[0]
        else:
            t_loo = None
        # top speed
        vs = np.linspace(20, 90, 7001)
        acc = np.array([v.a_cap(x) for x in vs])
        vtop = vs[np.argmax(acc <= 0)] if (acc <= 0).any() else 90
        a100 = v.a_cap(100 * KMH)
        rows.append({"car": r[0], "kg": r[1], "kW": r[2], "declared_0_100": r[4], "model_0_100": round(t, 2), "err_pct": round(100 * (t - r[4]) / r[4], 1), "loo_0_100": None if t_loo is None else round(t_loo, 2), "dt1_heun": round(t1, 2), "dt1_euler": round(te, 2), "declared_vmax": r[5], "model_vmax_kmh": round(vtop * 3.6, 0), "a_50": round(v.a_cap(50 * KMH), 2), "a_100": round(a100, 2)})
    out["cars"] = rows
    # torque-limited launch force from published ratios
    out["golf_first_gear_force_note"] = {"ratio": 3.62 * 4.06, "N_at_175Nm_r0.316": round(175 * 3.62 * 4.06 * 0.92 / 0.316), "a_m1300": round(175 * 3.62 * 4.06 * 0.92 / 0.316 / 1300, 2), "tyre_limit_fwd_mu1": round(0.55 * G, 2)}
    # ARBOC measured, 3,797 kg SLW, 3.6 L gasoline, 6 speed
    speed = np.array([10, 20, 30, 40, 50]) * MPH
    ccw = np.array([[2.40, 2.51, 2.58], [4.46, 4.47, 4.46], [6.56, 6.85, 6.41], [9.38, 9.25, 9.09], [13.33, 13.03, 12.83]])
    cw = np.array([[2.39, 2.44, 2.37], [4.38, 4.31, 4.28], [6.13, 6.37, 6.31], [8.89, 8.96, 8.87], [12.31, 12.26, 12.01]])
    measured = (ccw.mean(1) + cw.mean(1)) / 2
    m = 8370 * LB
    best = None
    for p in np.arange(60, 220, 4.0):
        for a0 in np.arange(1.6, 5.0, 0.2):
            v = Veh("ARBOC", m, p, 3.5, 0.011, a0, 1.0)
            t = np.array([integrate(v, x, dt=0.02)[0] for x in speed])
            e = float(((t - measured) ** 2).mean())
            if best is None or e < best[0]:
                best = (e, p, a0, t)
    out["arboc"] = {"mass_kg": round(m), "measured_s": np.round(measured, 2).tolist(), "fit_eff_wheel_kW": float(best[1]), "fit_a_launch": round(float(best[2]), 2), "model_s": np.round(best[3], 2).tolist(), "rmse_s": round(math.sqrt(best[0]), 2)}
    # Trucks: ITE table reproduced in Yang et al. 2016
    ite = {100: [2.9, 2.3, 2.2, 2.0, 1.6], 200: [1.8, 1.6, 1.5, 1.2, 1.0], 300: [1.3, 1.3, 1.2, 1.1, 0.6], 400: [1.3, 1.2, 1.1, 0.7, None]}
    inc = {100: [2.1, 1.5, 1.0, 0.6], 200: [1.3, 0.8, 0.5, 0.4], 300: [1.0, 0.6, 0.3, None], 400: [0.9, 0.4, None, None]}
    rows = []
    m = 36000
    for lbhp, vals in ite.items():
        p = m / LB / lbhp * HP / 1e3
        tr = Veh("truck", m, p, 6.0, 0.006, launch(0.85, p, m, 0.275, v_c=10.0), 0.85, inertia=1.08)
        row = {"lb_hp": lbhp, "kW_at_36t": round(p), "published_ft_s2": vals, "model_ft_s2": []}
        for i, mph in enumerate((10, 20, 30, 40, 50)):
            t, _ = integrate(tr, mph * MPH, dt=0.02)
            row["model_ft_s2"].append(round(mph * MPH / t / FT, 2) if t < 399 else None)
        row["inc_published"] = inc[lbhp]
        row["inc_model"] = []
        for lo in (20, 30, 40, 50):
            t0, _ = integrate(tr, lo * MPH, dt=0.02)
            t1, _ = integrate(tr, (lo + 10) * MPH, dt=0.02)
            row["inc_model"].append(round(10 * MPH / (t1 - t0) / FT, 2) if math.isfinite(t1) else None)
        rows.append(row)
    out["trucks_ite"] = rows
    # Yang 2016: heavy trucks, 0-500 ft, median 1.96 ft/s2 p15 1.56 p85 2.24 at metered ramps, no load data.
    rows = []
    for name, m, p in (("40 t 300 kW", 40000, 300), ("28 t 300 kW", 28000, 300), ("14 t 300 kW empty artic", 14000, 300), ("18 t 220 kW rigid", 18000, 220)):
        tr = Veh(name, m, p, 6.0, 0.006, launch(0.85, p, m, 0.275), 0.85, inertia=1.08)
        t = 0.0
        v = 0.0
        x = 0.0
        dt = 0.02
        while x < 500 * FT:
            a = tr.a_cap(v)
            x += v * dt + 0.5 * a * dt * dt
            v += a * dt
            t += dt
        rows.append({"veh": name, "avg_ft_s2_0_500ft": round(v * v / (2 * 500 * FT) / FT, 2), "exit_mph": round(v / MPH, 1)})
    out["yang2016"] = {"measured_heavy_median_ft_s2": 1.96, "p15": 1.56, "p85": 2.24, "measured_exit_mph": 31, "model": rows}
    # Crawl speed on grade
    rows = []
    for name, m, p in (("40 t 300 kW", 40000, 300), ("60 t 400 kW", 60000, 400), ("18 t 220 kW", 18000, 220), ("car 1,588 kg 90 kW", 1588, 90)):
        tr = Veh(name, m, p, 6.0 if m > 3000 else 0.65, 0.006 if m > 3000 else CRR, launch(0.85, p, m, 0.275 if m > 3000 else 0.55, v_c=3.0 if m > 3000 else 10.0), 0.85)
        row = {"veh": name}
        for g in (0.0, 0.02, 0.03, 0.05, 0.08):
            vs = np.linspace(1, 40, 3901)
            acc = np.array([tr.a_cap(x, g) for x in vs])
            ok = np.where(acc >= 0)[0]
            row[f"crawl_kmh_{int(g*100)}pct"] = "cannot start" if len(ok) == 0 else (">140" if ok[-1] == len(vs) - 1 else round(float(vs[ok[-1]] * 3.6), 1))
        rows.append(row)
    out["crawl"] = rows
    return out, ki, ke


# ---- 4. WLTC ------------------------------------------------------------------------------
def pairs_from(text):
    return {int(a): float(b) for a, b in re.findall(r"(?<![\d.])(\d{1,4})\s+(\d{1,3}\.\d)(?![\d])", text)}


def wltc():
    h = open(SRC + "/wltc_au.html", errors="ignore").read()
    t = re.sub(r"<[^>]+>", " ", h)
    t = re.sub(r"(&#xa0;|\s)+", " ", t)
    table = {}
    for k, nxt in ((7, 8), (9, 10), (11, 12), (12, 13)):
        start = [m.start() for m in re.finditer(rf"Table A1/{k} (This table is only applicable for Level 1A; )?WLTC", t)][-1]
        end = t.find(f"Table A1/{nxt} ", start + 10)
        chunk = t[start : end if end > 0 else start + 60000]
        chunk = chunk[chunk.index("km/h") :]
        table.update(pairs_from(chunk))
    # Both legal copies print second 538 as "13", without the decimal.
    table.setdefault(538, 13.0)
    trace = np.array([table.get(s, np.nan) for s in range(1801)])
    g = open(SRC + "/greenncap.txt", errors="ignore").read()
    idx = {k: g.index(f"Table A1/{k}\n") for k in (7, 8, 9, 10, 11, 12)}
    other = {}
    for k, nxt in ((7, 8), (9, 10), (11, 12)):
        other.update(pairs_from(g[idx[k] : idx[nxt]]))
    other.update(pairs_from(g[idx[12] : idx[12] + 12000]))
    common = [k for k in other if k <= 1800 and not np.isnan(trace[k])]
    diff = [abs(other[k] - trace[k]) for k in common]
    cross = {"au_samples": int(np.isfinite(trace).sum()), "greenncap_samples": len(common), "max_abs_diff_kmh": float(max(diff)), "mismatch_points": int(sum(d > 0.05 for d in diff)), "au_missing": [int(s) for s in np.where(np.isnan(trace))[0]][:20]}
    assert not np.isnan(trace).any(), cross
    v = trace * KMH
    acc = np.diff(v)
    central = (v[2:] - v[:-2]) / 2
    stat = {"a_max_central": round(float(central.max()), 3), "d_max_central": round(float(central.min()), 3), "seconds": len(v) - 1, "km": round(float(0.5 * (v[:-1] + v[1:]).sum() / 1e3), 3), "vmax_kmh": float(trace.max()), "a_max": round(float(acc.max()), 3), "d_max": round(float(acc.min()), 3), "v_at_amax_kmh": float(trace[np.argmax(acc)]), "idle_share": round(float((trace == 0).mean()), 3), "cross_check": cross}
    return v, stat


def track(veh, ref, dt, grade=0.0, jerk=None):
    """Replay the trace as desired speed. Ballistic update, capability-limited."""
    n = int(round((len(ref) - 1) / dt))
    tt = np.arange(n + 1) * dt
    r = np.interp(tt, np.arange(len(ref)), ref)
    v = r[0]
    x, xr = 0.0, 0.0
    errv, errx = [], []
    a_prev = 0.0
    e_pos = e_neg = 0.0
    sat = 0
    pmax = 0.0
    for i in range(n):
        want = (r[i + 1] - v) / dt
        cap = veh.a_cap(v + 0.5 * max(want, 0) * dt)
        b = veh.b_cap()
        a = min(max(want, -b), cap)
        if want > cap + 1e-6:
            sat += 1
        if jerk:
            a = np.clip(a, a_prev - jerk * dt, a_prev + jerk * dt)
        nv = max(0.0, v + a * dt)
        vm = 0.5 * (v + nv)
        F = veh.m * veh.i * a + veh.crr * veh.m * G + 0.5 * RHO * veh.cda * vm * vm
        P = F * vm
        if P > 0:
            e_pos += P * dt
        else:
            e_neg += P * dt
        pmax = max(pmax, P)
        x += vm * dt
        xr += 0.5 * (r[i] + r[i + 1]) * dt
        v = nv
        a_prev = a
        errv.append(abs(v - r[i + 1]))
        errx.append(x - xr)
    errv = np.array(errv) * 3.6
    return {
        "max_speed_err_kmh": round(float(errv.max()), 2),
        "share_gt_2kmh": round(float((errv > 2).mean()), 4),
        "share_saturated": round(float(sat / n), 4),
        "end_distance_err_m": round(float(errx[-1]), 1),
        "peak_wheel_kW": round(pmax / 1e3, 1),
        "wheel_Wh_per_km_pos": round(e_pos / 3600 / (xr / 1e3), 1),
        "wheel_Wh_per_km_neg": round(e_neg / 3600 / (xr / 1e3), 1),
    }


def wltc_runs(ki, ke, v):
    rows = []
    vehs = [mkcar(r, ki, ke) for r in CARS] + [
        Veh("fleet mean 1,588+75 kg 90 kW", 1663, 90, 0.68, CRR, launch(ki, 90, 1663, 0.55), ki),
        Veh("van 2.8 t 95 kW", 2800, 95, 1.6, 0.012, launch(ki, 95, 2800, 0.55), ki),
        Veh("truck 18 t 220 kW", 18000, 220, 5.0, 0.006, launch(0.85, 220, 18000, 0.4, v_c=3.0), 0.85, inertia=1.08),
        Veh("truck 40 t 300 kW", 40000, 300, 6.0, 0.006, launch(0.85, 300, 40000, 0.275, v_c=3.0), 0.85, inertia=1.08),
    ]
    for dt in (0.1, 1.0):
        for veh in vehs:
            rows.append({"veh": veh.name, "dt": dt, **track(veh, v, dt)})
    return rows


# ---- 5. EPA Test Car List --------------------------------------------------------------
def read_xlsx(path):
    z = zipfile.ZipFile(path)
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("a:si", ns):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["a"])))
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for r in sheet.iter("{%s}row" % ns["a"]):
        d = {}
        for c in r.findall("a:c", ns):
            ref = re.match(r"[A-Z]+", c.get("r")).group(0)
            v = c.find("a:v", ns)
            if v is None:
                continue
            d[ref] = ss[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(d)
    head = rows[0]
    return [{head.get(k, k): w for k, w in r.items()} for r in rows[1:]]


def epa():
    rows = read_xlsx(SRC + "/tcl25.xlsx")
    seen = {}
    for r in rows:
        try:
            key = (r.get("Represented Test Veh Make"), r.get("Represented Test Veh Model"), r.get("Rated Horsepower"), r.get("Equivalent Test Weight (lbs.)"))
            hp, etw = float(r["Rated Horsepower"]), float(r["Equivalent Test Weight (lbs.)"])
            a, b, c = float(r["Target Coef A (lbf)"]), float(r["Target Coef B (lbf/mph)"]), float(r["Target Coef C (lbf/mph**2)"])
        except (KeyError, TypeError, ValueError):
            continue
        if a <= 0 or c <= 0 or hp <= 0:
            continue
        seen[key] = (hp, etw, a, b, c, r.get("Represented Test Veh Make"), r.get("Represented Test Veh Model"))
    arr = np.array([s[:5] for s in seen.values()])
    hp, etw, a, b, c = arr.T
    m = etw * LB
    lbf = 4.44822
    f0 = a * lbf
    crr = f0 / (m * G)
    # C [lbf/mph^2] to N/(m/s)^2, then to CdA
    cda = c * lbf / MPH**2 / (0.5 * RHO)
    f100 = (a + b * (100 / 1.609344) + c * (100 / 1.609344) ** 2) * lbf
    pm = hp * HP / m
    q = (5, 25, 50, 75, 95)
    out = {
        "n_unique": len(arr),
        "etw_kg": np.round(np.percentile(m, q)).tolist(),
        "rated_kW": np.round(np.percentile(hp * HP / 1e3, q)).tolist(),
        "W_per_kg": np.round(np.percentile(pm, q), 1).tolist(),
        "A_over_mg": np.round(np.percentile(crr, q), 4).tolist(),
        "CdA_from_C_m2": np.round(np.percentile(cda, q), 3).tolist(),
        "F_at_100kmh_N": np.round(np.percentile(f100, q)).tolist(),
        "corr_log_m_log_kW": round(float(np.corrcoef(np.log(m), np.log(hp))[0, 1]), 3),
        "percentiles": list(q),
    }
    picks = []
    for s in seen.values():
        name = f"{s[5]} {s[6]}"
        if re.search(r"TESLA.*MODEL 3|Tesla.*Model 3|Golf|GOLF|Corolla|COROLLA|XC90", name):
            picks.append({"name": name, "hp": s[0], "etw_lb": s[1], "A": s[2], "B": s[3], "C": s[4]})
    out["examples"] = picks[:25]
    return out, picks


def tesla_energy(v, picks):
    """WLTC wheel energy with EPA road load, against ADAC's 13.2 kWh/100 km declared consumption."""
    p = next(x for x in picks if x["name"] == "Tesla Model 3 Long Range RWD")
    lbf = 4.44822
    a, b, c = p["A"] * lbf, p["B"] * lbf / MPH, p["C"] * lbf / MPH**2
    rows = {}
    for m in (1836 + 100.0, p["etw_lb"] * LB):
        pos = neg = 0.0
        for i in range(len(v) - 1):
            vm = 0.5 * (v[i] + v[i + 1])
            acc = v[i + 1] - v[i]
            F = m * acc + (a + b * vm + c * vm * vm if vm > 0 else 0.0)
            e = F * vm
            pos += max(e, 0.0)
            neg += min(e, 0.0)
        km = 0.5 * (v[:-1] + v[1:]).sum() / 1e3
        rows[f"m_{m:.0f}"] = {"pos_Wh_km": round(pos / 3600 / km, 1), "neg_Wh_km": round(neg / 3600 / km, 1), "battery_Wh_km_eta0.85_regen0.6": round((pos / 0.85 + 0.6 * 0.85 * neg) / 3600 / km, 1)}
    rows["declared_Wh_km"] = 132
    return rows


# ---- 6. discrete implied deceleration -----------------------------------------------------
def euler_stop(v0, b, dt):
    v, x, n = v0, 0.0, 0
    while v > 0:
        v = max(0.0, v - b * dt)
        x += v * dt
        n += 1
    return x


def ballistic_stop(v0, b, dt):
    v, x = v0, 0.0
    while v > 0:
        h = min(dt, v / b)
        x += v * h - 0.5 * b * h * h
        v -= b * h
        if v < 1e-9:
            break
    return x


def implied():
    rows = []
    for vk in (15, 30, 50, 70, 100):
        v0 = vk * KMH
        for b in (4.5, 7.0, 9.0):
            for dt in (1.0, 0.1):
                xe = euler_stop(v0, b, dt)
                ib = v0 * v0 / (2 * xe) if xe > 0 else float("inf")
                rows.append({"kmh": vk, "b": b, "dt": dt, "euler_m": round(xe, 2), "implied_b": round(ib, 2) if math.isfinite(ib) else "inf", "continuous_m": round(v0 * v0 / (2 * b), 2), "ballistic_m": round(ballistic_stop(v0, b, dt), 2)})
    return rows


# ---- 7. Krauss ports and safety certificate -----------------------------------------------
class T:
    def __init__(s, name, L, g0, a, b, e, tau=1.0, sigma=0.0, b_hi=None, b_lo=None, t_r=0.15, cap=None):
        s.name, s.L, s.g0, s.a, s.b, s.e, s.tau, s.sigma, s.cap, s.t_r = name, L, g0, a, b, e, tau, sigma, cap, t_r
        s.b_hi = b_hi or e
        s.b_lo = b_lo or e


def brake_gap(v, b, dt, head):
    r = b * dt
    n = math.floor(v / r)
    return dt * (n * v - r * n * (n + 1) * 0.5) + v * head


def safe_stop_euler(g, b, head, dt):
    g -= 1e-5
    if g < 0:
        return 0.0
    bb = b * dt
    n = math.floor(0.5 - ((head + math.sqrt(dt * dt + 4 * (dt * (2 * g / bb - head) + head * head)) * -0.5) / dt))
    h = 0.5 * n * (n - 1) * bb * dt + n * bb * head
    r = (g - h) / (n * dt + head)
    return n * bb + r


def krauss_euler(ty, g, v, vl, bl, dt):
    """safe_follow from common.wgsl, with SUMO's emergency relax."""
    if g >= 0:
        x = safe_stop_euler(g + brake_gap(vl, max(ty.b, bl), dt, 0.0), ty.b, ty.tau, dt)
    else:
        x = max(v - ty.e * dt, 0.0)
    orig = (v - x) / dt
    if ty.b != ty.e and orig > ty.b + 1e-5:
        if g <= 0:
            ed = ty.e
        else:
            pbd = 0.5 * vl * vl / bl
            b1 = 0.5 * v * v / (g + pbd)
            ed = b1 if b1 <= bl else 0.5 * (v * v - vl * vl) / g
        sd = min(max(1.2 * ed, ty.b), orig)
        x = max(v - sd * dt, 0.0)
    return x


def stop_ballistic(g, b, v0, tau, dt):
    """MSCFModel::maximumSafeStopSpeedBallistic."""
    g = max(0.0, g - 1e-5)
    tau = tau if tau > 0 else dt
    if g <= v0 * tau * 0.5:
        if g == 0.0:
            return -1e9 if v0 > 0 else 0.0
        return v0 - v0 * v0 / (2 * g) * dt
    bt = b * tau / 2
    v1 = -bt + math.sqrt(bt * bt + b * (2 * g - tau * v0))
    return v0 + (v1 - v0) / tau * dt


def a_des_car(v):
    """Long 2000 / Bonneson: a = 2.02 - 0.125 v at signals. Floor 0.7: Bosetti saw about 1 m/s2 on motorways."""
    return max(2.02 - 0.125 * v, 0.7)


def a_des_truck(v):
    """Yang et al. 2016: heavy trucks at metered ramps hold about 0.6 m/s2 over 0 to 500 ft."""
    return 0.6


def ramp_rate(b, t_r, dt):
    """Brake rate per second. The extra dt keeps a sample-and-hold staircase's lag at t_r/2."""
    return b / t_r if dt >= t_r else b / (t_r + dt)


def v_cert(g, v, vl, b_f_lo, b_l_hi, t_r, a_prev, dt, g_min=0.5):
    b = min(b_f_lo, b_l_hi)
    d_lo = max(0.0, -a_prev - ramp_rate(b, t_r, dt) * dt)
    lam = t_r * max(0.0, 1.0 - d_lo / b) ** 2
    h = 0.5 * (lam + dt)
    q = g - g_min + vl * vl / (2 * b_l_hi) - 0.5 * v * dt
    return b * (-h + math.sqrt(h * h + 2 * max(q, 0.0) / b)), q


def brake_floor(v, a_prev, b, t_r, dt):
    """Speed at t+dt under the hardest braking the ramp allows. Can go below zero: the stop is inside the tick."""
    d = max(0.0, -a_prev)
    if dt >= t_r:
        j = b / t_r
        t1 = max(b - d, 0.0) / j
        return v - (d * t1 + 0.5 * j * t1 * t1 + b * (dt - t1)) if b > d else v - b * dt
    return v - min(b, d + ramp_rate(b, t_r, dt) * dt) * dt


def safety(n=20000, seed=7):
    """Adversarial leader against the proposed certificate, across types, grades and surfaces."""
    rng = np.random.default_rng(seed)
    # name: length, follower lower bound b_lo, leader upper bound b_hi, brake rise t_r
    types = {
        "car": (4.3, 7.0, 11.3, 0.30),
        "van": (5.5, 6.0, 8.5, 0.47),
        "bus": (12.0, 4.5, 7.5, 0.45),
        "truck_full": (16.5, 4.4, 7.7, 0.45),
        "truck_empty": (16.5, 5.0, 7.7, 0.45),
    }
    names = list(types)
    res = {}
    for dt in (1.0, 0.1):
        coll = 0
        worst = 1e9
        trials = 0
        floor_hits = 0
        for k in range(n):
            f, l = rng.choice(names), rng.choice(names)
            _, bf, _, tr = types[f]
            _, _, bh, _ = types[l]
            grade = rng.uniform(-0.08, 0.08)
            mu = rng.choice([0.85, 0.54, 0.32, 0.073], p=[0.7, 0.2, 0.08, 0.02])
            gz = G * math.sin(math.atan(grade))
            b_f = min(bf, mu * G) + gz
            b_l = min(bh, 1.35 * mu * G) + gz
            if b_f <= 0.05 or b_l <= 0.05:
                continue  # no guaranteed braking: the road must refuse the state, not simulate it
            trials += 1
            vl = rng.uniform(0, 36)
            v = rng.uniform(0, 36)
            a_prev = rng.uniform(-b_f, 2.0)
            b = min(b_f, b_l)
            lam = tr * max(0.0, 1.0 - max(0.0, -a_prev - b / tr * dt) / b) ** 2
            g = v * v / (2 * b) + 0.5 * (lam + dt) * v + 0.5 * v * dt - vl * vl / (2 * b_l) + 0.5 + rng.uniform(0, 8)
            g = max(g, 0.6)
            onset = rng.uniform(0, dt)
            xl, xf, vL, vF, aF, t, mg, des = g, 0.0, vl, v, a_prev, 0.0, g, v
            sub = 40 if dt == 1.0 else 4
            h = dt / sub
            for step in range(int(600 / dt)):
                vc, q = v_cert(xl - xf, vF, vL, b_f, b_l, tr, aF, dt)
                # The certificate assumes braking at t+dt of at least d_lo, so release is rate limited.
                up = aF + ramp_rate(b, tr, dt) * dt if aF < 0 else 2.0
                want = min(des, vF + min(up, 2.0) * dt, vc)
                raw = brake_floor(vF, aF, b_f, tr, dt)
                floor_hits += want < raw - 1e-6
                # v_cert = 0 means stop now: hardest braking, stopping inside the tick, not stretched over dt.
                nv = raw if want <= 0.0 else max(want, raw)
                aF = (nv - vF) / dt
                for i in range(sub):
                    ab = -b_l if t + i * h >= onset else 0.0
                    n1 = max(0.0, vL + ab * h)
                    xl += 0.5 * (vL + n1) * h
                    vL = n1
                    n2 = max(0.0, vF + aF * h)
                    xf += 0.5 * (vF + n2) * h
                    vF = n2
                    mg = min(mg, xl - xf)
                t += dt
                if vF <= 0.0:
                    aF = 0.0
                if vF <= 0.0 and vL <= 0.0:
                    break
            if mg < worst:
                worst_case = {"f": str(f), "l": str(l), "grade": round(float(grade), 3), "mu": float(mu), "v": round(float(v), 2), "vl": round(float(vl), 2), "g0": round(float(g), 2), "a_prev": round(float(a_prev), 2), "min_gap": round(float(mg), 3)}
            worst = min(worst, mg)
            coll += mg < 0
        res[f"dt_{dt}"] = {"trials": trials, "collisions": int(coll), "min_gap_m": round(float(worst), 3), "brake_floor_active_steps": int(floor_hits), "worst": worst_case}
    return res


def krauss_adversary(n=20000, seed=3):
    """Today's Krauss constants against a leader using its physical emergency brake."""
    rng = np.random.default_rng(seed)
    res = {}
    for dt in (1.0, 0.1):
        coll = 0
        worst = 1e9
        for k in range(n):
            ty = T("car", 5, 2.5, 2.6, 4.5, 9.0)
            lead_e = rng.choice([9.0, 7.0])
            f_type = rng.choice(["car", "truck"], p=[0.8, 0.2])
            if f_type == "truck":
                ty = T("truck", 7.1, 2.5, 1.3, 4.0, 7.0)
            bl_app = 4.5
            v = rng.uniform(3, 30)
            # settle the follower at a Krauss-legal gap
            g = 0.0
            for _ in range(60):
                if krauss_euler(ty, g, v, v, bl_app, dt) >= v:
                    break
                g += 0.5
            xl, xf, vL, vF = g, 0.0, v, v
            mg = g
            for s in range(int(60 / dt)):
                nvL = max(0.0, vL - lead_e * dt)
                # Parallel update: follower sees old leader state, Euler position.
                x = krauss_euler(ty, xl - xf, vF, vL, bl_app, dt)
                nv = max(max(vF - ty.e * dt, 0.0), min(x, vF + ty.a * dt))
                xl += nvL * dt
                xf += nv * dt
                vL, vF = nvL, nv
                mg = min(mg, xl - xf)
                if vF == 0 and vL == 0:
                    break
            coll += mg < 0
            worst = min(worst, mg)
        res[f"dt_{dt}"] = {"trials": n, "collisions": int(coll), "share": round(coll / n, 4), "min_gap_m": round(float(worst), 2)}
    return res


# ---- 8. Traffic payoff --------------------------------------------------------------------
def queue_discharge(scn, dt, n=30, seed=1, sigma=0.0, sc=8):
    """Single lane queue released from a stop line, deterministic unless sigma>0."""
    rng = np.random.default_rng(seed)
    L = scn["L"]
    gap0 = scn["g0"]
    x = np.array([-1.0 - (i * (L[i % len(L)] + gap0)) for i in range(n)], float)
    lens = np.array([L[i % len(L)] for i in range(n)], float)
    v = np.zeros(n)
    a = np.zeros(n)
    tcross = np.full(n, np.nan)
    t = 0.0
    stop = 0.0
    for step in range(int(240 / dt)):
        nv = np.zeros(n)
        for i in range(n):
            ty = scn["types"][i % len(scn["types"])]
            amax = scn["acc"](i, v[i])
            des = scn["vmax"]
            if i == 0:
                vs = 1e9
            else:
                g = x[i - 1] - lens[i - 1] - x[i] - gap0
                if scn["ballistic"]:
                    # SUMO ballistic follow: stopping target gains leader's brake distance
                    vs = stop_ballistic(g + vL_stop(v[i - 1], ty, scn), ty.b, v[i], ty.tau, dt)
                else:
                    vs = krauss_euler(ty, g, v[i], v[i - 1], ty.b, dt)
                if scn.get("cert"):
                    vc, _ = v_cert(g + gap0, v[i], v[i - 1], ty.b_lo, scn["types"][(i - 1) % len(scn["types"])].b_hi, ty.t_r, a[i], dt)
                    vs = min(vs, vc)
            nvi = min(v[i] + amax * dt, vs, des)
            if sigma > 0:
                r = rng.random()
                nvi = max(nvi - dt * sigma * (ty.a if nvi >= ty.a else nvi) * r, 0.0)
            if scn.get("jerk"):
                ai = (nvi - v[i]) / dt
                ai = np.clip(ai, a[i] - scn["jerk"] * dt, a[i] + scn["jerk"] * dt)
                nvi = v[i] + ai * dt
            nv[i] = max(nvi, 0.0)
        na = (nv - v) / dt
        if scn["ballistic"]:
            nx = x + 0.5 * (v + nv) * dt
        else:
            nx = x + nv * dt
        crossed = (x < stop) & (nx >= stop) & np.isnan(tcross)
        tcross[crossed] = t + dt * ((stop - x[crossed]) / np.maximum(nx[crossed] - x[crossed], 1e-6))
        x, v, a = nx, nv, na
        t += dt
        if not np.isnan(tcross).any():
            break
    hw = np.diff(tcross)
    sat = np.nanmean(hw[sc:])
    lost = np.nansum(np.maximum(hw[:sc] - sat, 0)) + tcross[0]
    return float(sat), float(lost), float(tcross[0]), float(hw[0]) if len(hw) else np.nan


def vL_stop(vl, ty, scn):
    return vl * vl / (2 * max(ty.b, scn.get("bl", ty.b)))


def payoff(ki):
    car = T("car", 5, 2.5, 2.6, 4.5, 9.0, b_lo=7.0, b_hi=11.3, t_r=0.30)
    truck = T("truck", 16.5, 2.5, 1.3, 4.0, 7.0, b_lo=4.4, b_hi=7.7, t_r=0.45)
    phys_car = Veh("car", 1663, 90, 0.68, CRR, launch(ki, 90, 1663, 0.55), ki)
    phys_truck = Veh("truck", 40000, 300, 6.0, 0.006, launch(0.85, 300, 40000, 0.275, v_c=3.0), 0.85, inertia=1.08)
    sumo_acc = lambda ty: (lambda i, v: ty.a)
    desired = a_des_car
    out = []

    def scn(name, types, lens, acc, ballistic, dt, cert=False, jerk=None, sigma=0.0, vmax=13.89):
        s = {"types": types, "L": lens, "g0": 2.5, "acc": acc, "ballistic": ballistic, "vmax": vmax, "cert": cert, "jerk": jerk}
        sat, lost, first, h1 = queue_discharge(s, dt, sigma=sigma)
        out.append({"scenario": name, "dt": dt, "sat_headway_s": round(sat, 3), "veh_h_lane": round(3600 / sat), "lost_time_s": round(lost, 2), "first_cross_s": round(first, 2)})

    for dt in (1.0, 0.1):
        scn("A SUMO Krauss Euler a=2.6, sigma 0", [car], [5], sumo_acc(car), False, dt)
        scn("A2 SUMO Krauss Euler a=2.6, sigma 0.5", [car], [5], sumo_acc(car), False, dt, sigma=0.5)
        scn("B Ballistic, same constants", [car], [5], sumo_acc(car), True, dt)
        scn("C Ballistic, power cap only (min(2.6, cap))", [car], [5], lambda i, v: min(2.6, phys_car.a_cap(v)), True, dt)
        scn("D Ballistic, measured a=2.02-0.125v", [car], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)), True, dt)
        scn("E D plus certificate gap", [car], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)), True, dt, cert=True)
        scn("F E plus jerk 3 m/s3", [car], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)), True, dt, cert=True, jerk=3.0)
        scn("G E on +3% grade", [car], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)) - 0.03 * G, True, dt, cert=True)
        scn("H E on +6% grade", [car], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)) - 0.06 * G, True, dt, cert=True)
        car13 = T("car", 5, 2.5, 2.6, 4.5, 9.0, tau=1.35, b_lo=7.0, b_hi=11.3, t_r=0.30)
        scn("E2 E with driver tau 1.35 s", [car13], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)), True, dt, cert=True)
        scn("T1 turn at lane speed 6.13 m/s", [car], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)), True, dt, cert=True, vmax=6.13)
        scn("T2 turn at curve speed 4.66 m/s", [car], [5], lambda i, v: min(desired(v), phys_car.a_cap(v)), True, dt, cert=True, vmax=4.66)
        types = [car] * 9 + [truck]
        lens = [5] * 9 + [16.5]
        acc = lambda i, v: min(desired(v), phys_car.a_cap(v)) if i % 10 != 9 else min(a_des_truck(v), phys_truck.a_cap(v))
        scn("I E with 10% 40 t trucks", types, lens, acc, True, dt, cert=True)
        acc3 = lambda i, v: (min(desired(v), phys_car.a_cap(v)) - 0.03 * G) if i % 10 != 9 else min(a_des_truck(v) - 0.03 * G, phys_truck.a_cap(v, 0.03))
        scn("J I on +3% grade", types, lens, acc3, True, dt, cert=True)
        acc_s = lambda i, v: car.a if i % 10 != 9 else truck.a
        scn("K SUMO constants with 10% trucks", types, lens, acc_s, False, dt)
    return out


def grade_bottleneck(ki):
    """Open single lane: 1 km flat, 2 km of grade, then flat. Flow at the end at saturated inflow."""
    rows = []
    phys_car = Veh("car", 1663, 90, 0.68, CRR, launch(ki, 90, 1663, 0.55), ki)
    phys_truck = Veh("truck", 40000, 300, 6.0, 0.006, launch(0.85, 300, 40000, 0.275, v_c=3.0), 0.85, inertia=1.08)
    car = T("car", 5, 2.5, 2.6, 4.5, 9.0, b_lo=7.0, b_hi=11.3, t_r=0.30)
    truck = T("truck", 16.5, 2.5, 1.3, 4.0, 7.0, b_lo=4.4, b_hi=7.7, t_r=0.45, tau=1.5)
    for label, grade_pct, share, phys in (("constants, any grade, 10% trucks", 0, 0.1, False), ("physics flat, 10% trucks", 0, 0.1, True), ("physics 3%, 0% trucks", 3, 0.0, True), ("physics 3%, 10% trucks", 3, 0.1, True), ("physics 5%, 10% trucks", 5, 0.1, True), ("physics 3%, 5% trucks", 3, 0.05, True)):
        dt = 1.0
        rng = np.random.default_rng(11)
        vmax = 25.0
        xs, vs, ty = [], [], []
        passed = []
        t = 0.0
        next_in = 0.0
        L_tot = 4000.0
        while t < 2400:
            if (not xs or xs[-1] >= 20) and t >= next_in:
                tr = rng.random() < share
                xs.append(0.0)
                vs.append(min(vmax, vs[-1] if vs else vmax))
                ty.append(tr)
            nx = []
            nv = []
            for i in range(len(xs)):
                T_ = truck if ty[i] else car
                g_here = grade_pct / 100 if 1000 < xs[i] < 3000 else 0.0
                if phys:
                    amax = (phys_truck if ty[i] else phys_car).a_cap(vs[i], g_here)
                    if not ty[i]:
                        amax = min(amax, a_des_car(vs[i]) - g_here * G)
                    else:
                        amax = min(amax, a_des_truck(vs[i]) - g_here * G)
                else:
                    amax = T_.a
                if i == 0:
                    vsafe = 1e9
                else:
                    gap = xs[i - 1] - (16.5 if ty[i - 1] else 5.0) - xs[i] - 2.5
                    vsafe = krauss_euler(T_, gap, vs[i], vs[i - 1], T_.b, dt)
                # crawl: amax may be negative. Speed can't exceed its capability trajectory.
                v2 = max(0.0, min(vs[i] + amax * dt, vsafe, vmax))
                nv.append(v2)
                nx.append(xs[i] + v2 * dt)
            xs, vs = nx, nv
            while xs and xs[0] > L_tot:
                if t > 600:
                    passed.append(t)
                xs.pop(0)
                vs.pop(0)
                ty.pop(0)
            t += dt
        rows.append({"case": label, "flow_veh_h": round(len(passed) / (2400 - 600) * 3600)})
    return rows


# ---- figures ------------------------------------------------------------------------------
def figures(vtrace, ki, ke, car_res):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    t = np.arange(len(vtrace))
    a = np.diff(vtrace)
    ax[0].plot(vtrace[:-1] * 3.6, a, ".", ms=2, color="#888", label="WLTC class 3b demand")
    vs = np.linspace(0, 40, 200)
    for r, col in zip(CARS[:2] + CARS[4:], ("#c0392b", "#2980b9", "#27ae60")):
        v = mkcar(r, ki, ke)
        ax[0].plot(vs * 3.6, [v.a_cap(x) for x in vs], color=col, label=r[0])
    ax[0].plot(vs * 3.6, [Veh("t", 40000, 300, 6, 0.006, launch(0.85, 300, 40000, 0.275, v_c=3.0), 0.85, inertia=1.08).a_cap(x) for x in vs], color="#555", ls="--", label="40 t 300 kW")
    ax[0].plot(vs * 3.6, 2.02 - 0.125 * vs, color="k", ls=":", label="Measured at signals, 2.02-0.125v")
    ax[0].axhline(2.6, color="#aaa", lw=1)
    ax[0].text(3, 2.65, "SUMO default a=2.6", fontsize=8)
    ax[0].set(xlabel="speed, km/h", ylabel="m/s²", ylim=(-2, 5.5), title="Capability envelope against WLTC demand")
    ax[0].legend(fontsize=7)
    u = np.linspace(0, 1, 401)
    D = 3.5
    for T_, c in ((4, "#c0392b"), (6.28, "#e67e22"), (13.8, "#2980b9")):
        ax[1].plot(u * T_ - T_ / 2, D * f5(u), color=c, label=f"quintic T={T_} s, peak {1.875*D/T_:.2f} m/s")
    tt = np.linspace(0, 6.83, 800)
    vv = np.minimum.reduce([np.full(800, 0.6), 0.6 * (0.5 - 0.5 * np.cos(np.pi * np.clip(tt, 0, 1))), 0.6 * (0.5 - 0.5 * np.cos(np.pi * np.clip(6.83 - tt, 0, 1)))])
    ax[1].plot(tt - 6.83 / 2, np.cumsum(vv) * (tt[1] - tt[0]), color="k", lw=2, label="constant 0.6 m/s, T=6.8 s (proposed)")
    ax[1].axhline(0.85, color="#aaa", lw=1)
    ax[1].axhline(2.65, color="#aaa", lw=1)
    ax[1].text(-6.9, 2.7, "Body wholly in new lane", fontsize=8)
    ax[1].text(-6.9, 0.55, "Body wholly in old lane", fontsize=8)
    ax[1].set(xlabel="time from crossing, s", ylabel="lateral offset, m", title="Only near-constant lateral speed fits all durations")
    ax[1].legend(fontsize=7, loc="lower right")
    vk = np.array([15, 30, 50, 70, 100.0])
    for b, c in ((4.5, "#2980b9"), (9.0, "#c0392b")):
        ax[2].plot(vk, [(x / 3.6) ** 2 / (2 * euler_stop(x / 3.6, b, 1.0)) if euler_stop(x / 3.6, b, 1.0) > 0 else np.nan for x in vk], "o-", color=c, label=f"Euler dt=1, b={b}")
        ax[2].plot(vk, [(x / 3.6) ** 2 / (2 * euler_stop(x / 3.6, b, 0.1)) for x in vk], "s--", color=c, label=f"Euler dt=0.1, b={b}")
    ax[2].axhspan(8.3, 8.91, color="#ddd")
    ax[2].text(60, 9.15, "ADAC winter tyres on dry, 8.3 to 8.9", fontsize=8)
    ax[2].set(xlabel="initial speed, km/h", ylabel="v²/(2·stopping distance), m/s²", ylim=(0, 40), title="Deceleration the Euler position update implies")
    ax[2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG + "/11-physics-check.png", dpi=150)


def main():
    R["values"] = check_values()
    R["quintic"] = check_quintic()
    cr, ki, ke = cars()
    R["longitudinal"] = cr
    v, stat = wltc()
    R["wltc_stats"] = stat
    R["wltc_tracking"] = wltc_runs(ki, ke, v)
    ep, picks = epa()
    R["epa_tcl_2025"] = ep
    R["tesla_wltc_energy"] = tesla_energy(v, picks)
    R["euler_implied"] = implied()
    R["certificate"] = safety(n=12000)
    R["krauss_adversary"] = krauss_adversary(n=4000)
    R["payoff_queue"] = payoff(ki)
    R["payoff_grade"] = grade_bottleneck(ki)
    figures(v, ki, ke, cr)
    json.dump(R, open(OUT, "w"), indent=1, default=str)
    print(json.dumps(R, indent=1, default=str))


if __name__ == "__main__":
    main()
