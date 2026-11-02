#!/usr/bin/env python3
"""Convergence plots from assign runs: gap, trip time, unfinished trips, count error, per iteration.
usage: assign_plots.py OUT.png RUN_DIR[:LABEL] [RUN_DIR[:LABEL] ...]"""
import csv, os, sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": MUTED, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.8})


def read(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return {k: [float(r[k]) if r[k] not in ("", "NaN") else float("nan") for r in rows] for k in rows[0]} if rows else None


def panel(ax, title, curves, ylabel=None, ref=None, log=False):
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    for label, xs, ys, color, style in curves:
        ax.plot(xs, ys, color=color, linestyle=style, label=label)
    if ref is not None:
        ax.axhline(ref[0], color=MUTED, linewidth=1, linestyle=":")
        ax.annotate(ref[1], (1, ref[0]), xycoords=("axes fraction", "data"), ha="right", va="bottom", fontsize=8, color=MUTED)
    if log:
        ax.set_yscale("symlog", linthresh=0.01)
        ax.set_ylim(bottom=0)
    ax.set_xlabel("iteration")
    if ylabel:
        ax.set_ylabel(ylabel)
    if len(curves) > 1:
        ax.legend(frameon=False, fontsize=8)


def main(out, args):
    runs = []
    for a in args:
        d, _, label = a.partition(":")
        r = read(os.path.join(d, "iters.csv"))
        if r:
            runs.append((label or os.path.basename(d), r))
    has_counts = any(max(r["train_wape"]) > 0 for _, r in runs)
    cols = 3 if has_counts else 2
    rows = 2
    fig, ax = plt.subplots(rows, cols, figsize=(5.0 * cols, 3.4 * rows), squeeze=False, constrained_layout=True)
    color = {i: SERIES[i % len(SERIES)] for i in range(len(runs))}
    many = len(runs) > 1
    name = lambda label, what: f"{label}: {what}" if many else what
    panel(ax[0][0], "Relative gap", sum(([(name(l, "unseen seed"), r["iter"], [x * 100 for x in r["gap_unseen"]], color[i], "-"), (name(l, "on smoothed costs"), r["iter"], [x * 100 for x in r["gap_memory"]], color[i], "--")] for i, (l, r) in enumerate(runs)), []), "% of trip cost", (2.0, "target 2%"))
    panel(ax[0][1], "Mean trip time, insertion wait and unfinished trips charged", [(l, r["iter"], r["mean_travel_s"], color[i], "-") for i, (l, r) in enumerate(runs)], "s")
    valve = any(max(r["teleports"]) > 0 for _, r in runs)
    panel(ax[1][0], "Unfinished trips at the horizon, " + ("teleports on: a labelled workaround" if valve else "teleports off"), [(l, r["iter"], [x * 100 for x in r["unfinished_share"]], color[i], "-") for i, (l, r) in enumerate(runs)], "% of requested", (0.1, "limit 0.1%"), log=True)
    if valve:
        panel(ax[1][1], "Teleports per day", [(l, r["iter"], r["teleports"], color[i], "-") for i, (l, r) in enumerate(runs)], "teleports")
    else:
        panel(ax[1][1], "Peak vehicles on the network", [(l, r["iter"], r["peak_active"], color[i], "-") for i, (l, r) in enumerate(runs)], "vehicles")
    if has_counts:
        curves = []
        for i, (l, r) in enumerate(runs):
            curves.append((name(l, "train"), r["iter"], [x * 100 for x in r["train_wape"]], color[i], "--"))
            curves.append((name(l, "selection"), r["iter"], [x * 100 for x in r["selection_wape"]], color[i], ":"))
            curves.append((name(l, "held-out test"), r["iter"], [x * 100 for x in r["test_wape"]], color[i], "-"))
        panel(ax[0][2], "Count error, WAPE", curves, "%")
        panel(ax[1][2], "Simulated over observed count, held-out test", [(l, r["iter"], r["count_ratio_test"], color[i], "-") for i, (l, r) in enumerate(runs)], "ratio", (1.0, "observed"))
    fig.savefig(out, dpi=150, facecolor="#fcfcfb")


main(sys.argv[1], sys.argv[2:])
