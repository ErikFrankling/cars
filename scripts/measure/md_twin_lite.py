"""The physical bounds of the kernel that the measured driver's twin needs (scripts/replay/md_twin.py), with the step as an
argument and no replay harness: engine cap, the measured stop of report 19, and the certificate."""
import numpy as np


def ph_force(u, mu=0.85):
    pw = 0.775 * 90000 / 1650; load = 0.25 + 110 / 146; power = 0.5 + 64 / 127.5
    return (1 / 1.05) * (np.minimum(pw * power / (load * np.maximum(u, 10.0)), mu * 0.55 * 9.81) - 0.0105 * 9.81 - 0.5 * 1.225 * 0.68 / 1650 * u * u / load)


def a_cap(v, dt):
    return ph_force(v + 0.5 * np.maximum(ph_force(v), 0) * dt)


def stop_comfort(gap, v, dt):
    g = np.maximum(gap, 0.0)
    v1 = 1.2 * np.maximum(g - v * dt, 0) ** 0.6
    v2 = 1.2 * np.maximum(g - 0.5 * (v + v1) * dt, 0) ** 0.6
    late = v - dt * np.maximum(2.2, 1.1 * v * v / (2 * np.maximum(g, 0.1)))
    return np.where(g <= 0.1, 0.0, np.minimum(np.maximum(v2, late), np.maximum(g - v * dt * 0.5, 0) / dt))


def cert(gb, v, vl, a_prev, dt, b=8.3, t_r=0.3):
    along = vl * vl / (2 * b)
    jerk = b / t_r if dt >= t_r else b / (t_r + dt)
    d_lo = np.maximum(0, -a_prev - jerk * dt); lam = np.maximum(0, 1 - d_lo / b)
    h = (t_r * lam * lam + dt) * 0.5
    q = gb - 0.5 + along - v * dt * 0.5
    return b * (-h + np.sqrt(h * h + 2 * np.maximum(q, 0) / b))
