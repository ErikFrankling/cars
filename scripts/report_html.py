#!/usr/bin/env python3
"""report/index.html: the summary page with hoverable charts and the figure gallery."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/home/erikf/projects/personal/cars-data")
FIG = ROOT / "report/figures"
ABS = "--absolute" in sys.argv


def summary_xml(path):
    rows = []
    try:
        for _, el in ET.iterparse(path):
            if el.tag == "step":
                rows.append((float(el.get("time")), int(el.get("running")), int(el.get("arrived")), int(el.get("teleports"))))
                el.clear()
    except ET.ParseError:
        pass
    return pd.DataFrame(rows, columns=["time", "running", "arrived", "teleports"])


def series(df, col, step):
    d = df[(df.time % step) == 0]
    return [[float(t), float(v)] for t, v in zip(d.time, d[col])]


def chart_data():
    out = {}
    c_s = summary_xml(DATA / "charlottenburg/out/summary.xml")
    c_g = pd.read_csv(ROOT / "runs/char/summary.csv")
    out["char"] = {"SUMO": series(c_s, "running", 900), "cars": series(c_g, "running", 900)}
    sumo_b = DATA / "best/out/summary2.xml"
    if not sumo_b.exists():
        sumo_b = DATA / "best/out/summary.xml"
    b_s = summary_xml(sumo_b)
    b_g = pd.read_csv(ROOT / "runs/berlin/morning_summary.csv")
    out["berlin"] = {"SUMO": series(b_s, "running", 300), "cars": series(b_g[b_g.time <= b_s.time.max()], "running", 300)}
    d = pd.read_csv(ROOT / "runs/berlin/day_summary.csv")
    out["day"] = {"cars": series(d, "running", 900)}
    thesis = pd.read_csv("/home/erikf/projects/personal/thesis-src/bachelor/results/processed/metrics.csv")
    sweeps = {}
    for s in ("ring", "glosa_two_signal", "i80_vsl", "bologna"):
        f = ROOT / f"results/thesis/{s}.csv"
        if not f.exists():
            continue
        a = pd.read_csv(f)
        sweeps[s] = {}
        for tier in a.tier.unique():
            x = a[a.tier == tier].groupby("penetration").speed.mean()
            y = thesis[(thesis.scenario == s) & (thesis.tier == tier)].groupby("penetration").speed.mean()
            sweeps[s][tier] = {"SUMO": [[float(k), float(v)] for k, v in y.items()], "cars": [[float(k), float(v)] for k, v in x.items()]}
    out["sweeps"] = sweeps
    return out


TILES = [
    ("148 s", "Berlin, 24 hours, 2.25M car trips, on one RX 7900 XT"),
    ("about 7 h", "the same day in SUMO, as published with BeST, 3.4 GHz CPU"),
    ("341 s", "all 1,134 runs of the thesis sweeps; SUMO needs 8.2 h on the same PC"),
    ("788.1 s / 789.0 s", "mean trip, Berlin 05:00-10:00, cars / SUMO"),
]


def row(*cells):
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def tables():
    out = ["<h2>Same trips, same numbers</h2><p>Mean over all completed trips, then the 95th percentile. Cars has no fitted parameters against these runs.</p>"]
    out.append("<table><tr><th>Scenario</th><th>Metric</th><th>SUMO</th><th>cars</th><th>SUMO p95</th><th>cars p95</th></tr>")
    for name, f in (("Berlin 05:00-10:00", "berlin"), ("Mitte, whole day", "mitte"), ("Charlottenburg, whole day", "charlottenburg")):
        path = ROOT / f"results/{f}_trip_stats.csv"
        if not path.exists():
            continue
        for r in pd.read_csv(path).itertuples():
            out.append(row(name, r.metric, r.sumo_mean, r.cars_mean, r.sumo_p95, r.cars_p95))
    out.append("</table>")
    e = pd.read_csv(ROOT / "results/thesis/errors.csv")
    out.append("<h2>Thesis sweeps: mean absolute error against SUMO</h2><p>Averaged over all 21 AV shares, 3 seeds each.</p><table><tr><th>Scenario</th><th>Model</th><th>Speed</th><th>Travel time</th><th>Waiting</th><th>Time loss</th></tr>")
    pct = lambda v: "n/a" if pd.isna(v) else f"{v * 100:.1f}%"
    for r in e.itertuples():
        out.append(row(r.scenario, r.tier, pct(r.speed), pct(r.travel_time), pct(r.waiting_time), pct(r.time_loss)))
    out.append("</table>")
    out.append("""<h2>Speed</h2><p>SUMO single-threaded on the same PC. Small single scenarios are about even: the GPU wins by running thousands of replicas in one world, and on big networks.</p>
<table><tr><th>Job</th><th>SUMO</th><th>cars</th><th>Factor</th></tr>""")
    for a, b, c, d in SPEED:
        out.append(row(a, b, c, d))
    out.append("</table>")
    return "".join(out)


SPEED = [
    ("Bologna sweep, 315 runs", "6.4 h", "195 s", "118x"),
    ("I-80 sweep, 252 runs", "58 min", "69 s", "50x"),
    ("Ring sweep, 252 runs", "40 min", "50 s", "48x"),
    ("Two-signal sweep, 315 runs", "7.5 min", "26 s", "17x"),
    ("Berlin 05:00-06:00, single run", "177 s", "5.0 s", "35x"),
    ("Berlin 24 h, single run", "about 7 h (published)", "148 s", "about 170x"),
    ("Bologna, single run", "73 s", "42 s", "1.8x"),
    ("I-80, single run", "14 s", "14 s", "1x"),
    ("Ring, 200 cars, single run", "1.5 s", "2.3 s", "0.6x"),
]


def main():
    data = chart_data()
    tpl = (ROOT / "scripts/report_template.html").read_text()
    figs = sorted(p.name for p in FIG.glob("*.png"))
    ph = sorted(p.name for p in (ROOT / "results/phenomena").glob("*.png"))
    prefix = str(FIG) + "/" if ABS else "figures/"
    prefix2 = str(ROOT / "results/phenomena") + "/" if ABS else "../results/phenomena/"
    gallery = "".join(f'<figure><img src="{prefix}{f}" loading="lazy" alt="{f}"><figcaption>{f[:-4]}</figcaption></figure>' for f in figs)
    gallery2 = "".join(f'<figure><img src="{prefix2}{f}" loading="lazy" alt="{f}"><figcaption>{f[:-4]}</figcaption></figure>' for f in ph)
    tiles = "".join(f'<div class="tile"><b>{a}</b><span>{b}</span></div>' for a, b in TILES)
    html = tpl.replace("__DATA__", json.dumps(data)).replace("__GALLERY__", gallery).replace("__PHENOMENA__", gallery2).replace("__TILES__", tiles).replace("__MORE__", tables())
    out = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ROOT / "report/index.html"
    out.write_text(html)
    print("wrote", out, len(html))


if __name__ == "__main__":
    main()
