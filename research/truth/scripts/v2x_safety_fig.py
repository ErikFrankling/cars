#!/usr/bin/env python3
"""Required bumper gap against speed for the stop-line rule, from v2x_safety_attack.py's closed form."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TD, A, J, E, AGE = 0.25, 1.0, 12.7, 1.0, 0.1


def s_plus(v, b):
    v1 = v + A * TD
    vp = v1 + A * A / (2 * J)
    return v * TD + 0.5 * A * TD * TD + v1 * A / J + A**3 / (3 * J * J) + vp * b / (2 * J) + vp * vp / (2 * b)


def gap(v, b, B):
    return np.maximum(0.5, s_plus(v, b) - v * v / (2 * B) + v * AGE + E)


v = np.linspace(0.5, 40, 200)
series = [
    ("Brick-wall leader, b=6", gap(v, 6, 1e9), "#6250d6"),
    ("No trust, b=6, B=12", gap(v, 6, 12), "#2a78d6"),
    ("No trust, b=7.5, B=10", gap(v, 7.5, 10), "#1baf7a"),
    ("Signed certificate, b=Bc=6", gap(v, 6, 6), "#eb6834"),
]
fig, ax = plt.subplots(figsize=(8.4, 4.8), dpi=150)
for name, g, c in series:
    ax.plot(v, g, color=c, linewidth=2)
    ax.annotate(name, (v[-1], g[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color="#0b0b0b")
r157v = np.array([2.0, 2.78, 5.56, 8.33, 11.11, 13.89, 16.67])
r157g = np.array([2.0, 3.1, 6.7, 10.8, 15.6, 20.8, 26.7])
ax.plot(r157v, r157g, linestyle="none", marker="o", markersize=5, color="#52514e")
ax.annotate("UN R157 minimum (2021 text)", (r157v[-1], r157g[-1]), xytext=(-150, 22), textcoords="offset points", fontsize=9, color="#52514e", arrowprops=dict(arrowstyle="-", color="#a8a7a0", linewidth=0.8))
ax.set_xlim(0, 40)
ax.set_ylim(0, 190)
ax.set_xlabel("Speed of both cars (m/s)")
ax.set_ylabel("Required bumper gap (m)")
ax.set_title("Gap needed so that no leader manoeuvre within the bound causes contact", fontsize=11, loc="left")
ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
ax.set_axisbelow(True)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
fig.subplots_adjust(right=0.74, left=0.08, top=0.92, bottom=0.11)
out = ROOT / "fig" / "08-required-gap.png"
fig.savefig(out)
print(out)
