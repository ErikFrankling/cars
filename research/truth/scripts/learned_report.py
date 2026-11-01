#!/usr/bin/env python3
"""Tables and figures for research/truth/13-learned-drivers.md, from research/truth/learned/."""
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import learned_drivers as ld  # noqa: E402

L = ld.OUT
FIG = L.parent / "fig"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"


def load(*names):
    d = {}
    for n in names:
        p = L / f"{n}.json"
        if p.exists():
            d.update(json.loads(p.read_text()))
    return d


def group(d, prefix):
    return [k for k in d if k.startswith(prefix)]


def stat(d, keys, cond, field):
    x = [d[k][cond][field] for k in keys if cond in d[k]]
    return float(np.mean(x)), float(np.std(x)) if len(x) > 1 else 0.0


ROWS = [
    ("IDM human in the AV's seat", ["IDM (no noise)"]),
    ("FollowerStopper, oracle speed", ["FollowerStopper, oracle U"]),
    ("PI with saturation", ["PI with saturation"]),
    ("ES, reward with 1 s floor", "es_tg_s"),
    ("ES, 1 s floor, trained on L = 220–320", "es_tgrange_s"),
    ("PPO, reward with 1 s floor", "ppo_tg_s"),
    ("DAgger from PI", "dagger_pi_s"),
    ("BC from PI, no correction", "bc_pi_s"),
    ("ES, no floor", "es_ema_s"),
    ("PPO, no floor", "ppo_s"),
    ("ES, no floor, no memory input", "es_none_s"),
    ("ES, no floor, learned memory", "es_learned_s"),
    ("ES, no floor, trained under the rule", "es_shield_s"),
    ("ES, speed-only reward", "es_speedonly_s"),
    ("ES, energy-only reward", "es_energyonly_s"),
]
EV = ("eval-es-ema", "eval-es-tg", "eval-ppo", "eval-memory", "eval-shield-range", "eval-tgrange-dagger", "eval-bc-hacks")


def fmt(m, s, nd=0):
    return f"{m:,.{nd}f}" + (f" ± {s:.{nd}f}" if s > 0 and (s >= 10 ** -nd * 0.5) else "")


def ring_table(d):
    print("| Car in the AV seat | Seeds | Flow, veh/h | Speed SD, m/s | Wh/km | AV gap, m | AV time under 1 s | Min AV gap, m | Contact, % of replicas |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    c = "test seeds"
    for name, keys in ROWS:
        k = keys if isinstance(keys, list) else group(d, keys)
        k = [x for x in k if x in d]
        if not k:
            continue
        print(
            f"| {name} | {len(k)} | {fmt(*stat(d, k, c, 'flow'))} | {fmt(*stat(d, k, c, 'sd'), 2)} | {fmt(*stat(d, k, c, 'wh_km'))} | "
            f"{fmt(*stat(d, k, c, 'gap'), 1)} | {stat(d, k, c, 'under_1s')[0]:.0%} | {min(d[x][c]['min_gap'] for x in k):.2f} | {100 * stat(d, k, c, 'coll')[0]:.0f} |"
        )


def general_table(d):
    conds = ["test seeds", "test seeds, shield", "L=220", "L=240", "L=300", "L=400", "humans a=1.6", "humans b=2.5", "humans T=0.9", "noise x2", "hetero humans", "Krauss humans", "dt=0.05", "dt=0.5", "dt=1.0", "k=3 of 22", "k=11 of 22", "k=22 of 22"]
    cols = [("IDM", ["IDM (no noise)"]), ("PI-sat", ["PI with saturation"]), ("ES", "es_tg_s"), ("ES range", "es_tgrange_s"), ("PPO", "ppo_tg_s"), ("DAgger", "dagger_pi_s")]
    print("| Test | " + " | ".join(c[0] for c in cols) + " |")
    print("|---|" + "---:|" * len(cols))
    for cond in conds:
        cells = []
        for _, keys in cols:
            k = keys if isinstance(keys, list) else group(d, keys)
            k = [x for x in k if x in d and cond in d[x]]
            if not k:
                cells.append("–")
                continue
            f = stat(d, k, cond, "flow")[0]
            s = stat(d, k, cond, "sd")[0]
            co = stat(d, k, cond, "coll")[0]
            cells.append(f"{f:,.0f} / {s:.2f}" + (f" / **{100 * co:.0f}%**" if co > 0 else ""))
        print(f"| {cond} | " + " | ".join(cells) + " |")


def curves(prefix):
    out = []
    for p in sorted(L.glob(f"{prefix}*.npz")):
        out.append(json.loads(str(np.load(p)["curve"])))
    return out


def samples_table():
    print("| Method | Seed | Updates to flow ≥ 2,000, SD ≤ 0.5, no contact | Same, final | Final flow | Final SD |")
    print("|---|---:|---:|---:|---:|---:|")
    for name, pre in (("ES", "es_tg_s"), ("PPO", "ppo_tg_s")):
        for i, cv in enumerate(curves(pre)):
            hit = next((r for r in cv if r["flow"] >= 2000 and r["sd"] <= 0.5 and r["coll"] == 0), None)
            last = cv[-1]
            print(f"| {name} | {i} | {hit['updates'] / 1e6:.0f} M | {hit['wall'] if hit else float('nan'):.0f} s | {last['flow']:.0f} | {last['sd']:.2f} |" if hit else f"| {name} | {i} | never | | {last['flow']:.0f} | {last['sd']:.2f} |")


def fig_learning():
    fig, ax = plt.subplots(figsize=(7.2, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    b = json.loads((L / "eval-es-ema.json").read_text())["IDM (no noise)"]["test seeds"]["flow"]
    for pre, col, name in (("es_tg_s", BLUE, "ES"), ("ppo_tg_s", ORANGE, "PPO")):
        cs = curves(pre)
        for c in cs:
            ax.plot([r["updates"] / 1e6 for r in c], [r["flow"] for r in c], color=col, lw=1.0, alpha=0.35)
        xs = np.array([r["updates"] / 1e6 for r in cs[0]])
        ys = np.mean([[r["flow"] for r in c][: len(xs)] for c in cs], axis=0)
        ax.plot(xs, ys, color=col, lw=2, label=f"{name}, mean of {len(cs)} seeds")
    ax.axhline(b, color=MUTED, lw=1, ls="--")
    ax.text(880, b + 18, f"IDM humans only, {b:,.0f}", color=MUTED, ha="right", fontsize=9)
    ue = ld.uniform_speed(260 / 22 - 5, ld.HUMAN) * 22 / 260 * 3600
    ax.axhline(ue, color=MUTED, lw=1, ls=":")
    ax.text(880, ue + 18, f"Uniform flow, {ue:,.0f}", color=MUTED, ha="right", fontsize=9)
    ax.set_xlabel("Vehicle updates, millions", color=INK)
    ax.set_ylabel("Flow on validation seeds, veh/h", color=INK)
    ax.set_title("Ring, one learned car among 22: both methods learn to remove the wave", color=INK, fontsize=11, loc="left")
    ax.legend(frameon=False, loc="lower right", labelcolor=INK)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", lw=0.6)
    ax.set_ylim(0, 2400)
    ax.set_xlim(0, 900)
    fig.tight_layout()
    fig.savefig(FIG / "13-ring-learning.png", dpi=160, facecolor=SURFACE)


def fig_law():
    theta = np.load(L / "es_tg_s0.npz")["theta"]
    net = ld.Net(theta[None])
    gaps = np.linspace(1, 25, 96)
    dvs = np.linspace(-4, 4, 80)
    v = 6.8
    G, D = np.meshgrid(gaps, dvs)
    o = np.zeros((1, G.size, ld.IN))
    vl = v + D.ravel()
    o[0, :, 0] = v / 20
    o[0, :, 1] = vl / 20
    o[0, :, 2] = np.minimum(G.ravel(), 40) / 40
    o[0, :, 3] = D.ravel() / 5
    o[0, :, 4] = 1
    o[0, :, 8] = v / 20
    o[0, :, 9] = 8.0 / 40
    A = ld.out_to_accel(net(o)[..., 0])[0].reshape(G.shape)
    H = np.clip(ld.idm(v, vl, G.ravel(), ld.HUMAN), -6, 3).reshape(G.shape)
    fig, axs = plt.subplots(1, 2, figsize=(9.4, 3.7), sharey=True, facecolor=SURFACE)
    for ax, Z, t in ((axs[0], A, "Learned car (ES, 1 s floor, seed 0)"), (axs[1], H, "IDM human in this report")):
        im = ax.pcolormesh(G, D, Z, cmap="RdBu", vmin=-3, vmax=3, shading="auto")
        ax.contour(G, D, Z, levels=[0], colors=INK, linewidths=1)
        ax.set_title(t, color=INK, fontsize=10, loc="left")
        ax.set_xlabel("Bumper gap, m", color=INK)
    axs[0].set_ylabel("Leader speed − own speed, m/s", color=INK)
    cb = fig.colorbar(im, ax=axs, shrink=0.9)
    cb.set_label("Commanded acceleration, m/s² (clipped at ±3)", color=INK)
    fig.savefig(FIG / "13-learned-law.png", dpi=160, facecolor=SURFACE, bbox_inches="tight")


def fig_merge():
    files = [("merge_v2x_s1", BLUE, "ES, warm start from ring")]
    fig, ax = plt.subplots(figsize=(7.2, 4.0), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for tag, col, name in files + [("merge_shield_s0", AQUA, "Same, trained under the rule"), ("merge_scratch_s0", ORANGE, "ES from scratch, raw")]:
        p = L / f"{tag}.npz"
        if not p.exists():
            continue
        c = json.loads(str(np.load(p)["curve"]))
        ax.plot([r["gen"] for r in c], [r["outflow"] for r in c], color=col, lw=2, label=name)
    ax.set_xlabel("Generation", color=INK)
    ax.set_ylabel("Outflow on validation seeds, veh/h", color=INK)
    ax.set_title("Merge, 10% learned cars: the curriculum learns, the scratch run parks", color=INK, fontsize=11, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", lw=0.6)
    ax.legend(frameon=False, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(FIG / "13-merge-learning.png", dpi=160, facecolor=SURFACE)


def main():
    d = load(*EV)
    print("### ring")
    ring_table(d)
    print("\n### general")
    general_table(d)
    print("\n### samples")
    samples_table()
    b = L / "eval-brake.json"
    if b.exists():
        print("\n### brake")
        print("| Car | Contact, % of replicas | Survived | Flow | Rule override |")
        print("|---|---:|---:|---:|---:|")
        for k, v in json.loads(b.read_text()).items():
            print(f"| {k} | {100 * v['coll']:.0f} | {100 * v['survived']:.0f}% | {v['flow']:.0f} | {100 * v['shield']:.2f}% |")
    m = L / "eval-merge.json"
    if m.exists():
        md = json.loads(m.read_text())
        print("\n### merge")
        print("| Car | Outflow | Delay/veh, s | Queue left | Wh/km | Contact % | Override % | Min AV gap |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|")
        for k, v in md.items():
            for c in ("test", "test, shield"):
                if c in v:
                    s = v[c]
                    print(f"| {k} {'+ rule' if 'shield' in c else ''} | {s['outflow']:.0f} | {s['delay_per_veh']:.0f} | {s['queue']:.0f} | {s['wh_km']:.0f} | {100 * s['coll']:.0f} | {100 * s['shield']:.1f} | {s['min_gap_av']:.1f} |")
        print("\n### merge general")
        keys = list(next(iter(md.values())).keys())
        tags = list(md.keys())
        print("| Test | " + " | ".join(tags) + " |")
        print("|---|" + "---:|" * len(tags))
        for c in keys:
            print(f"| {c} | " + " | ".join(f"{md[t][c]['outflow']:.0f} / {md[t][c]['delay_per_veh']:.0f}" + (f" / **{100 * md[t][c]['coll']:.0f}%**" if md[t][c]["coll"] > 0 else "") for t in tags) + " |")
    FIG.mkdir(exist_ok=True)
    fig_learning()
    fig_law()
    fig_merge()


if __name__ == "__main__":
    main()
