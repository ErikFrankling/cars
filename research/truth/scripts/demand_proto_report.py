"""Summarise research/truth/demand-proto/*.json into the tables and figure used in 06-demand-and-route-choice.md."""

import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "demand-proto")
FIG = os.path.join(HERE, "..", "fig")


def load(pat):
    return [(os.path.basename(f), json.load(open(f))) for f in sorted(glob.glob(os.path.join(D, pat)))]


rules = {}
for name, data in load("E1_update_rule_s*"):
    scale = name.split("_s")[1].split("_")[0]
    for key, seeds in data["policies"].items():
        if seeds:
            rules.setdefault((scale, key), []).extend(seeds.values())
print("E1 scale,rule,seeds,gap_iter0,gap_max,iters_to_5pct,iters_to_2pct,last_gap,indep_gap,mean_tt,unfinished")
for (scale, key), runs in sorted(rules.items()):
    n = min(len(r["gap"]) for r in runs)
    m = np.array([r["gap"][:n] for r in runs]).mean(axis=0)
    first = lambda th: next((i for i in range(len(m)) if (m[i:] < th).all()), None)
    print(scale, key, len(runs), round(m[0], 3), round(m.max(), 3), first(0.05), first(0.02), round(m[-1], 3),
          round(np.mean([r["final_indep"]["gap"] for r in runs]), 3), round(np.mean([r["final_indep"]["mean_tt_s"] for r in runs]), 1),
          round(np.mean([r["final_indep"]["unfinished"] for r in runs])))
print("E2 scale,replicas x iterations,seeds,indep gap,mean tt")
for name, data in load("E2_replicas*"):
    for k, rows in data["runs"].items():
        print(name.split("_s")[1].split("_")[0], k, len(rows), round(np.mean([r["final"]["gap"] for r in rows]), 4), round(np.mean([r["final"]["mean_tt_s"] for r in rows]), 1))
e3 = []
for name, data in load("E3_gridlock*"):
    e3 += data["rows"]
e3.sort(key=lambda r: r["scale"])
print("E3 load,trips,free-flow TT,free-flow unfinished,free-flow tele300 TT,tele300 unfinished,tele300 teleports,assigned TT,assigned unfinished,assigned tele300 TT,tele300 unfinished,teleports,gap")
for r in e3:
    a, b, c, d = (r[k] for k in ("freeflow_noteleport", "freeflow_teleport300", "assigned_noteleport", "assigned_teleport300"))
    print(r["scale"], r["trips"], round(a["mean_tt_s"]), a["unfinished"], round(b["mean_tt_s"]), b["unfinished"], b["teleports"], round(c["mean_tt_s"]), c["unfinished"], round(d["mean_tt_s"]), d["unfinished"], d["teleports"], round(r["assigned_gap"], 3))
print("E5 prior,coverage,method,train,heldout,total ratio,pair rmse,pair corr,vkt")
seen = set()
for name, data in load("E5_od_from_counts*"):
    if "noise_floor_wape_other_seed" in data and "floor" not in seen:
        seen.add("floor")
        print("noise floor other seed", round(data["noise_floor_wape_other_seed"], 3), "other day", round(data["noise_floor_wape_other_day"], 3), "cells", data["cells"], "links", data["links"], "trips", data["truth_trips"])
    for r in data["rows"]:
        print(r["prior"], r["coverage"], r["method"], round(r["train_wape"], 3), round(r["heldout_wape"], 3), round(r["total_ratio"], 3), round(r["pair_rmse_rel_mean"], 3), None if r["pair_corr"] != r["pair_corr"] else round(r["pair_corr"], 3), round(r["vkt_ratio"], 3))

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e8e7e3", "#fcfcfb"
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
plt.rcParams.update({"font.size": 10, "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.edgecolor": GRID, "font.family": "DejaVu Sans"})
fig, ax = plt.subplots(1, 2, figsize=(11, 4.8), facecolor=SURFACE)
for a in ax:
    a.set_facecolor(SURFACE)
    a.grid(True, color=GRID, linewidth=0.8)
    a.spines[["top", "right"]].set_visible(False)
series = [("aon:1.0", "Everyone switches", S[1]), ("gapprop:1.0", "Share set by gap, no cap", S[3]), ("fixed10:1.0", "Fixed 10%", S[2]), ("gapcap:0.3", "Capped at 15%, cost memory", S[0])]
for key, label, col in series:
    runs = rules.get(("1.5", key))
    if runs:
        n = min(len(r["gap"]) for r in runs)
        m = np.array([r["gap"][:n] for r in runs]).mean(axis=0)
        ax[0].plot(100 * m, color=col, linewidth=2, label=label)
ax[0].set_yscale("log")
ax[0].set_yticks([1, 3, 10, 30, 100], ["1%", "3%", "10%", "30%", "100%"])
ax[0].minorticks_off()
ax[0].set_xlabel("Assignment iteration")
ax[0].set_ylabel("Relative gap")
ax[0].set_title("Rerouting everyone never converges (150% load)", loc="left", fontsize=11)
ax[0].legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)
x = [r["scale"] * 100 for r in e3]
ax[1].plot(x, [r["freeflow_noteleport"]["mean_tt_s"] / 60 for r in e3], color=S[1], linewidth=2, marker="o", markersize=5, label="Empty-network routes")
ax[1].plot(x, [r["assigned_noteleport"]["mean_tt_s"] / 60 for r in e3], color=S[0], linewidth=2, marker="o", markersize=5, label="Assigned routes")
ax[1].set_xlabel("Demand, % of base load")
ax[1].set_ylabel("Mean trip time, minutes")
ax[1].set_title("Routes decide delay well below collapse", loc="left", fontsize=11)
ax[1].legend(frameon=False, loc="upper left")
fig.tight_layout()
os.makedirs(FIG, exist_ok=True)
fig.savefig(os.path.join(FIG, "demand-assignment.png"), dpi=160, facecolor=SURFACE)
