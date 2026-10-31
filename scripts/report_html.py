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


def main():
    data = chart_data()
    tpl = (ROOT / "scripts/report_template.html").read_text()
    figs = sorted(p.name for p in FIG.glob("*.png"))
    ph = sorted(p.name for p in (ROOT / "results/phenomena").glob("*.png"))
    prefix = str(FIG) + "/" if ABS else "figures/"
    prefix2 = str(ROOT / "results/phenomena") + "/" if ABS else "../results/phenomena/"
    gallery = "".join(f'<figure><img src="{prefix}{f}" loading="lazy" alt="{f}"><figcaption>{f[:-4]}</figcaption></figure>' for f in figs)
    gallery2 = "".join(f'<figure><img src="{prefix2}{f}" loading="lazy" alt="{f}"><figcaption>{f[:-4]}</figcaption></figure>' for f in ph)
    html = tpl.replace("__DATA__", json.dumps(data)).replace("__GALLERY__", gallery).replace("__PHENOMENA__", gallery2)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ROOT / "report/index.html"
    out.write_text(html)
    print("wrote", out, len(html))


if __name__ == "__main__":
    main()
