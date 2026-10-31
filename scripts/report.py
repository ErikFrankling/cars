#!/usr/bin/env python3
"""Figures comparing cars with SUMO, from the CSVs in results/ and the raw SUMO outputs."""

import gzip
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "report/figures"
DATA = Path("/home/erikf/projects/personal/cars-data")
THESIS = Path("/home/erikf/projects/personal/thesis-src/bachelor/results/processed/metrics.csv")
SUMO = "#eb6834"
CARS = "#2a78d6"
REAL = "#1baf7a"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": "#c3c2b7", "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "font.size": 10,
    "lines.linewidth": 2, "legend.frameon": False, "figure.dpi": 130, "axes.axisbelow": True,
})


def save(name):
    plt.tight_layout()
    plt.savefig(FIG / f"{name}.png")
    plt.close("all")
    print("wrote", name)


def geh(a, b):
    return np.sqrt(2 * (a - b) ** 2 / np.maximum(a + b, 1e-9))


def read_summary(path):
    rows = []
    try:
        for _, el in ET.iterparse(path):
            if el.tag == "step":
                rows.append((float(el.get("time")), int(el.get("running")), int(el.get("inserted")), int(el.get("arrived")), int(el.get("teleports")), float(el.get("meanSpeed", 0))))
                el.clear()
    except ET.ParseError:
        pass
    return pd.DataFrame(rows, columns=["time", "running", "inserted", "arrived", "teleports", "speed"])


def read_edges(path):
    rows = []
    begin = None
    try:
        for ev, el in ET.iterparse(path, events=("start", "end")):
            if ev == "start" and el.tag == "interval":
                begin = float(el.get("begin"))
            elif ev == "end" and el.tag == "edge":
                if not el.get("id").startswith(":"):
                    ss = float(el.get("sampledSeconds", 0))
                    rows.append((begin, el.get("id"), ss, float(el.get("speed", 0)) * ss, float(el.get("entered", 0))))
                el.clear()
            elif ev == "end" and el.tag == "interval":
                el.clear()
    except ET.ParseError:
        pass
    return pd.DataFrame(rows, columns=["begin", "edge", "samples", "distance", "entered"])


def read_trips(path):
    rows = []
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rb") as f:
        try:
            for _, el in ET.iterparse(f):
                if el.tag == "tripinfo":
                    rows.append((float(el.get("depart")), float(el.get("duration")), float(el.get("waitingTime")), float(el.get("timeLoss")), float(el.get("routeLength"))))
                    el.clear()
        except (ET.ParseError, EOFError):
            pass
    return pd.DataFrame(rows, columns=["depart", "duration", "waiting", "time_loss", "route_length"])


def hour_labels(ax):
    t = ax.get_xticks()
    ax.set_xticks(t)
    ax.set_xticklabels([f"{int(x / 3600):02d}:00" for x in t])


# ---------------------------------------------------------------- whole city or district, day

def city(name, title, sumo_dir, cars_summary, cars_edges, cars_trips, sim_start=0):
    s = read_summary(sumo_dir / ("summary2.xml" if (sumo_dir / "summary2.xml").exists() else "summary.xml"))
    g = pd.read_csv(cars_summary)
    end = s.time.max()
    g0 = g[g.time <= end]

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(s.time, s.running, color=SUMO, label="SUMO")
    ax.plot(g0.time, g0.running, color=CARS, label="cars", linestyle="--")
    ax.set_title(f"{title}: vehicles on the road")
    ax.set_xlabel("simulated time")
    ax.set_ylabel("running vehicles")
    ax.set_xticks(np.arange(int(s.time.min() // 3600) * 3600, end + 1, 3600 if end - s.time.min() < 40000 else 7200))
    hour_labels(ax)
    ax.legend()
    save(f"{name}_running")

    fig, ax = plt.subplots(figsize=(9, 3.6))
    a0 = g0.arrived.iloc[0] if sim_start else 0
    ax.plot(s.time, s.arrived, color=SUMO, label="SUMO")
    ax.plot(g0.time, g0.arrived - (a0 if sim_start else 0), color=CARS, linestyle="--", label="cars")
    ax.set_title(f"{title}: trips completed")
    ax.set_xlabel("simulated time")
    ax.set_ylabel("cumulative arrivals")
    ax.set_xticks(np.arange(int(s.time.min() // 3600) * 3600, end + 1, 3600 if end - s.time.min() < 40000 else 7200))
    hour_labels(ax)
    ax.legend()
    save(f"{name}_arrivals")

    e_s = read_edges(sumo_dir / ("edge900b.xml" if (sumo_dir / "edge900b.xml").exists() else "edge900.xml"))
    e_g = pd.read_csv(cars_edges)
    if e_g.begin.nunique() and e_s.begin.nunique():
        step = float(np.median(np.diff(sorted(e_g.begin.unique()))))
        e_s = e_s.assign(bin=(e_s.begin // step) * step).groupby(["bin", "edge"])[["samples", "distance", "entered"]].sum().reset_index()
        e_g2 = e_g[~e_g.edge.str.startswith(":")].rename(columns={"begin": "bin"})
        m = e_s.merge(e_g2, on=["bin", "edge"], how="outer", suffixes=("_s", "_g")).fillna(0)
        m = m[m.bin <= e_s.bin.max() - step]
        m.to_pickle(f"/tmp/{name}_edges.pkl")
        by_edge = m.groupby("edge")[["entered_s", "entered_g", "samples_s", "samples_g", "distance_s", "distance_g"]].sum()
        fig, axs = plt.subplots(1, 2, figsize=(10, 4.4))
        ax = axs[0]
        lim = max(by_edge.entered_s.max(), by_edge.entered_g.max()) * 1.05
        ax.hexbin(by_edge.entered_s.clip(lower=1), by_edge.entered_g.clip(lower=1), gridsize=70, xscale="log", yscale="log", bins="log", cmap="Blues", mincnt=1)
        ax.plot([1, lim], [1, lim], color=MUTED, linewidth=1)
        r = np.corrcoef(by_edge.entered_s, by_edge.entered_g)[0, 1]
        ax.set_title(f"Vehicles entering each edge (r² = {r * r:.4f})")
        ax.set_xlabel("SUMO")
        ax.set_ylabel("cars")
        v = by_edge[(by_edge.samples_s > 500) & (by_edge.samples_g > 500)]
        ax = axs[1]
        vs = v.distance_s / v.samples_s
        vg = v.distance_g / v.samples_g
        ax.hexbin(vs, vg, gridsize=70, bins="log", cmap="Blues", mincnt=1)
        top = float(max(vs.max(), vg.max()))
        ax.plot([0, top], [0, top], color=MUTED, linewidth=1)
        r = np.corrcoef(vs, vg)[0, 1]
        ax.set_title(f"Mean speed on each edge, m/s (r² = {r * r:.3f})")
        ax.set_xlabel("SUMO")
        ax.set_ylabel("cars")
        fig.suptitle(title, x=0.02, ha="left", fontsize=11, color=INK2)
        save(f"{name}_edges")

        hourly = m.groupby(["bin", "edge"])[["entered_s", "entered_g"]].sum().reset_index()
        hourly = hourly[(hourly.entered_s + hourly.entered_g) > 0]
        fig, ax = plt.subplots(figsize=(9, 3.4))
        hourly["geh"] = geh(hourly.entered_g * 3600 / step, hourly.entered_s * 3600 / step)
        by = hourly.groupby("bin").geh.apply(lambda x: (x < 5).mean())
        ax.plot(by.index, by.values * 100, color=CARS)
        ax.set_ylim(0, 100)
        ax.set_title(f"{title}: share of edge flows with GEH < 5 against SUMO, per interval")
        ax.set_ylabel("% of edges")
        ax.set_xlabel("simulated time")
        hour_labels(ax)
        save(f"{name}_geh")

        tot = m.groupby("bin")[["samples_s", "samples_g", "distance_s", "distance_g"]].sum()
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(tot.index, tot.distance_s / tot.samples_s.clip(lower=1), color=SUMO, label="SUMO")
        ax.plot(tot.index, tot.distance_g / tot.samples_g.clip(lower=1), color=CARS, linestyle="--", label="cars")
        ax.set_title(f"{title}: network mean speed")
        ax.set_ylabel("m/s")
        ax.set_xlabel("simulated time")
        hour_labels(ax)
        ax.legend()
        save(f"{name}_speed")

        fig, ax = plt.subplots(figsize=(6, 4.6))
        ax.plot(tot.samples_s / step, tot.distance_s / step, color=SUMO, marker="o", markersize=3, linewidth=1, label="SUMO")
        ax.plot(tot.samples_g / step, tot.distance_g / step, color=CARS, marker="o", markersize=3, linewidth=1, label="cars")
        ax.set_title(f"{title}: macroscopic fundamental diagram")
        ax.set_xlabel("accumulation, vehicles")
        ax.set_ylabel("production, vehicle-m/s")
        ax.legend()
        save(f"{name}_mfd")

    tp = None
    for fn in ("tripinfo.xml.gz",):
        if (sumo_dir / fn).exists():
            tp = read_trips(sumo_dir / fn)
    if tp is not None and len(tp):
        gt = pd.read_csv(cars_trips)
        gt = gt[(gt.depart >= tp.depart.min()) & (gt.depart <= tp.depart.max())]
        fig, axs = plt.subplots(1, 2, figsize=(10, 4.2))
        ax = axs[0]
        for d, c, l, st in ((tp.duration, SUMO, "SUMO", "-"), (gt.duration, CARS, "cars", "--")):
            x = np.sort(d.values)
            ax.plot(x, np.linspace(0, 1, len(x)), color=c, label=l, linestyle=st)
        ax.set_xlim(0, np.percentile(tp.duration, 99.5))
        ax.set_title("Trip duration, cumulative share")
        ax.set_xlabel("seconds")
        ax.set_ylabel("share of trips")
        ax.legend()
        ax = axs[1]
        q = np.linspace(0.005, 0.999, 200)
        a = np.quantile(tp.duration, q)
        b = np.quantile(gt.duration, q)
        ax.plot(a, a, color=MUTED, linewidth=1)
        ax.plot(a, b, color=CARS, marker="o", markersize=2.5, linewidth=0)
        ax.set_title("Trip duration quantiles")
        ax.set_xlabel("SUMO, s")
        ax.set_ylabel("cars, s")
        fig.suptitle(title, x=0.02, ha="left", fontsize=11, color=INK2)
        save(f"{name}_trips")
        rows = []
        for c, label in (("duration", "duration s"), ("waiting", "waiting s"), ("time_loss", "time loss s"), ("route_length", "route length m")):
            rows.append((label, tp[c].mean(), gt[c].mean(), tp[c].quantile(0.95), gt[c].quantile(0.95)))
        pd.DataFrame(rows, columns=["metric", "sumo_mean", "cars_mean", "sumo_p95", "cars_p95"]).round(1).to_csv(ROOT / f"results/{name}_trip_stats.csv", index=False)
        print(rows, len(tp), len(gt))


# ---------------------------------------------------------------- thesis sweeps

def thesis():
    b = pd.read_csv(THESIS)
    labels = {"ring": "Ring road", "glosa_two_signal": "Two signals", "i80_vsl": "I-80 corridor", "bologna": "Bologna"}
    tier_names = {"krauss": "Krauss (AV as human)", "idm": "IDM", "acc": "ACC", "cacc": "CACC", "glosa": "GLOSA"}
    table = []
    for s, title in labels.items():
        path = ROOT / f"results/thesis/{s}.csv"
        if not path.exists():
            continue
        a = pd.read_csv(path)
        tiers = [t for t in tier_names if t in a.tier.unique()]
        for metric, ylabel in (("speed", "mean speed, m/s"), ("travel_time", "mean travel time, s"), ("waiting_time", "mean waiting, s")):
            if a[metric].abs().sum() == 0:
                continue
            fig, axs = plt.subplots(1, len(tiers), figsize=(2.6 * len(tiers), 3), sharey=True, squeeze=False)
            for ax, t in zip(axs[0], tiers):
                for d, c, l, st in ((b[(b.scenario == s) & (b.tier == t)], SUMO, "SUMO", "-"), (a[a.tier == t], CARS, "cars", "--")):
                    g = d.groupby("penetration")[metric].agg(["mean", "min", "max"])
                    ax.fill_between(g.index, g["min"], g["max"], color=c, alpha=0.18, linewidth=0)
                    ax.plot(g.index, g["mean"], color=c, label=l, linestyle=st)
                ax.set_title(tier_names[t], fontsize=10)
                ax.set_xlabel("AV share")
            axs[0][0].set_ylabel(ylabel)
            axs[0][-1].legend()
            fig.suptitle(f"{title}: thesis sweep, 3 seeds, SUMO results from the thesis", x=0.02, ha="left", fontsize=11)
            save(f"thesis_{s}_{metric}")
        c = ["speed", "travel_time", "waiting_time", "time_loss"]
        j = a.groupby(["tier", "penetration"])[c].mean().join(b[b.scenario == s].groupby(["tier", "penetration"])[c].mean(), lsuffix="_g", rsuffix="_s", how="inner")
        for t, x in j.groupby(level=0):
            row = dict(scenario=s, tier=t)
            for m in c:
                ok = x[f"{m}_s"].abs() > 1e-6
                row[m] = ((x[f"{m}_g"] - x[f"{m}_s"]).abs() / x[f"{m}_s"].abs())[ok].mean() if ok.any() else float("nan")
            table.append(row)
    t = pd.DataFrame(table)
    t.round(4).to_csv(ROOT / "results/thesis/errors.csv", index=False)
    print(t.round(3).to_string())
    fig, ax = plt.subplots(figsize=(8, 3.8))
    p = t.pivot(index="scenario", columns="tier", values="speed").reindex(list(labels)) * 100
    cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    w = 0.16
    for i, tier in enumerate(["krauss", "idm", "acc", "cacc", "glosa"]):
        if tier in p:
            ax.bar(np.arange(len(p)) + i * w, p[tier].fillna(0), w - 0.02, color=cols[i], label=tier_names[tier])
    ax.set_xticks(np.arange(len(p)) + 2 * w)
    ax.set_xticklabels([labels[x] for x in p.index])
    ax.set_ylabel("mean abs. speed error, %")
    ax.set_title("Thesis sweeps: speed against SUMO, averaged over penetrations")
    ax.legend(ncol=5, fontsize=8)
    save("thesis_errors")


# ---------------------------------------------------------------- performance

def bench():
    f = ROOT / "results/bench/single.csv"
    if f.exists():
        d = pd.read_csv(f)
        names = {"ring_200": "Ring, 200 cars", "i80_thesis": "I-80 corridor", "bologna_thesis": "Bologna", "charlottenburg_0800": "Charlottenburg", "berlin_0500": "Berlin 05:00-06:00"}
        p = d.pivot(index="case", columns="engine", values="updates_per_s").reindex([k for k in names if k in set(d.case)])
        fig, ax = plt.subplots(figsize=(8.6, 3.8))
        cols = {"SUMO 1 thread": SUMO, "SUMO 4 threads": "#eda100", "cars GPU": CARS}
        w = 0.26
        for i, e in enumerate(cols):
            if e in p:
                ax.bar(np.arange(len(p)) + i * w, p[e] / 1e6, w - 0.03, color=cols[e], label=e)
        ax.set_yscale("log")
        ax.set_xticks(np.arange(len(p)) + w)
        ax.set_xticklabels([names[x] for x in p.index], fontsize=9)
        ax.set_ylabel("million vehicle updates per s")
        ax.set_title("Throughput on the same PC, single scenario")
        ax.legend()
        save("bench_single")
    f = ROOT / "results/bench/replicas.csv"
    if f.exists():
        d = pd.read_csv(f)
        fig, ax = plt.subplots(figsize=(7, 3.8))
        ax.plot(d.vehicles_peak, d.updates_per_s / 1e6, color=CARS, marker="o", markersize=8, label="cars GPU")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("vehicles in the GPU world, peak")
        ax.set_ylabel("million vehicle updates per s")
        ax.set_title("Throughput against vehicle count, Bologna replicas in one world")
        ax.legend()
        save("bench_replicas")
    f = ROOT / "results/bench/kernels.csv"
    if f.exists():
        d = pd.read_csv(f)
        p = d.pivot_table(index="vehicles", columns="kernel", values="ms")
        top = p.mean().sort_values(ascending=False).index[:7]
        fig, ax = plt.subplots(figsize=(8, 3.6))
        bottom = np.zeros(len(p))
        cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
        for k, c in zip(top, cols):
            ax.barh(range(len(p)), p[k].values, left=bottom, color=c, label=k, height=0.6)
            bottom += p[k].values
        rest = p.drop(columns=top).sum(axis=1).values
        ax.barh(range(len(p)), rest, left=bottom, color="#c3c2b7", label="other", height=0.6)
        ax.set_yticks(range(len(p)))
        ax.set_yticklabels([f"{int(x):,} cars" for x in p.index])
        ax.set_xlabel("ms per step")
        ax.set_title("Berlin: time per step by GPU kernel")
        ax.legend(ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2))
        save("bench_kernels")
    s = ROOT / "runs/berlin/day_summary.csv"
    if s.exists():
        g = pd.read_csv(s)
        dt = g.time.diff()
        w = g.wall.diff()
        fig, ax = plt.subplots(figsize=(9, 3.4))
        ax.plot(g.time, (dt / w).rolling(10, min_periods=1).mean(), color=CARS)
        ax.set_title("Berlin day: simulated seconds per wall-clock second")
        ax.set_ylabel("speed-up over real time")
        ax.set_xlabel("simulated time")
        ax.set_xticks(np.arange(0, 86401, 7200))
        hour_labels(ax)
        save("bench_realtime")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    what = sys.argv[1:] or ["thesis", "bench", "char", "mitte", "berlin"]
    if "thesis" in what:
        thesis()
    if "bench" in what:
        bench()
    if "char" in what:
        city("charlottenburg", "Charlottenburg, whole day", DATA / "charlottenburg/out", ROOT / "runs/char/summary.csv", ROOT / "runs/char/edges.csv", ROOT / "runs/char/trips.csv")
    if "mitte" in what and (DATA / "mitte/out/summary.xml").exists() and (ROOT / "runs/mitte/summary.csv").exists():
        city("mitte", "Mitte, whole day", DATA / "mitte/out", ROOT / "runs/mitte/summary.csv", ROOT / "runs/mitte/edges.csv", ROOT / "runs/mitte/trips.csv")
    if "berlin" in what and (ROOT / "runs/berlin/morning_summary.csv").exists():
        city("berlin", "Berlin, 05:00-10:00", DATA / "best/out", ROOT / "runs/berlin/morning_summary.csv", ROOT / "runs/berlin/morning_edges.csv", ROOT / "runs/berlin/morning_trips.csv", sim_start=18000)


if __name__ == "__main__":
    main()
