#!/usr/bin/env python3
"""Weekday shape, weekend ratio and day-to-day variation from Zurich's permanent counters.

Usage: normal_day_zurich.py ZH2025.csv OUT.json
Term-time Tue-Thu only for the shape (excludes Swiss school and public holidays roughly by month).
"""
import csv
import datetime as dt
import json
import statistics as st
import sys
from collections import defaultdict

path, out = sys.argv[1:3]
TERM = {3, 4, 5, 9, 10, 11}
hour = defaultdict(lambda: defaultdict(lambda: [0.0] * 24))
hour_seen = defaultdict(lambda: defaultdict(lambda: [0] * 24))
daily = defaultdict(lambda: defaultdict(float))
with open(path, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if row["AnzFahrzeuge"] in ("", "NA") or row["AnzFahrzeugeStatus"] != "Gemessen":
            continue
        t = row["MessungDatZeit"]
        date, h = t[:10], int(t[11:13])
        site = row["MSID"]
        v = float(row["AnzFahrzeuge"])
        hour[site][date][h] += v
        hour_seen[site][date][h] += 1

complete = defaultdict(dict)
for site, days in hour.items():
    for date, v in days.items():
        if min(hour_seen[site][date]) >= 1:
            complete[site][date] = v


def weekday(date):
    return dt.date.fromisoformat(date).weekday()


def in_term(date):
    d = dt.date.fromisoformat(date)
    return d.month in TERM


def shape(v):
    tot = sum(v)
    mid = sum(v[10:15]) / 5
    return dict(
        am=max(v[6:10]) / tot,
        pm=max(v[15:19]) / tot,
        night=(sum(v[22:]) + sum(v[:6])) / tot,
        h07_19=sum(v[7:19]) / tot,
        am_mid=max(v[6:10]) / mid,
        pm_mid=max(v[15:19]) / mid,
        min_mid=min(v) / mid,
        peak_hour=max(range(24), key=lambda h: v[h]),
    )


rows = []
network_days = defaultdict(float)
network_count = defaultdict(int)
site_shapes = {}
for site, days in complete.items():
    good = [d for d in days if weekday(d) in (1, 2, 3) and in_term(d)]
    if len(good) < 30:
        continue
    mean = [sum(days[d][h] for d in good) / len(good) for h in range(24)]
    adt = sum(mean)
    if adt < 500:
        continue
    totals = [sum(days[d]) for d in good]
    cv = st.pstdev(totals) / st.mean(totals)
    med = st.median(totals)
    abs_dev = st.median(abs(x - med) / med for x in totals)
    hour_dev = []
    for h in (8, 12, 17):
        vals = [days[d][h] for d in good]
        m = st.median(vals)
        if m > 0:
            hour_dev.append(st.median(abs(x - m) / m for x in vals))
    sat = [sum(v) for d, v in days.items() if weekday(d) == 5 and in_term(d)]
    sun = [sum(v) for d, v in days.items() if weekday(d) == 6 and in_term(d)]
    s = shape(mean)
    s.update(
        site=site,
        adt=adt,
        peak_flow=max(mean),
        cv=cv,
        mad=abs_dev,
        hour_mad=st.mean(hour_dev),
        days=len(good),
        sat_ratio=st.mean(sat) / adt if sat else None,
        sun_ratio=st.mean(sun) / adt if sun else None,
    )
    rows.append(s)

stable = {r["site"] for r in rows}
dates = sorted({d for s in stable for d in complete[s]})
coverage = {d: sum(1 for s in stable if d in complete[s]) for d in dates}
always = [s for s in stable if sum(1 for d in dates if weekday(d) in (1, 2, 3) and in_term(d) and d in complete[s]) >= 0.95 * sum(1 for d in dates if weekday(d) in (1, 2, 3) and in_term(d))]
net = {}
net_h = {}
for d in dates:
    have = [s for s in always if d in complete[s]]
    if len(have) >= 0.97 * len(always):
        scale = len(always) / len(have)
        net[d] = scale * sum(sum(complete[s][d]) for s in have)
        net_h[d] = [scale * sum(complete[s][d][h] for s in have) for h in range(24)]

term_mid = [d for d in net if weekday(d) in (1, 2, 3) and in_term(d)]
vals = [net[d] for d in term_mid]
mean_shape = [st.mean(net_h[d][h] for d in term_mid) for h in range(24)]
weeks = defaultdict(list)
for d in term_mid:
    weeks[dt.date.fromisoformat(d).isocalendar()[1]].append(net[d])
wk = [st.mean(v) for v in weeks.values()]
res = {
    "sites_used": len(rows),
    "sites_network": len(always),
    "days_network": len(term_mid),
    "network_shape": shape(mean_shape),
    "network_hour_mean": mean_shape,
    "network_day_cv": st.pstdev(vals) / st.mean(vals),
    "network_day_mad": st.median(abs(x - st.median(vals)) / st.median(vals) for x in vals),
    "network_week_cv": st.pstdev(wk) / st.mean(wk),
    "network_min_over_mean": min(vals) / st.mean(vals),
    "network_max_over_mean": max(vals) / st.mean(vals),
    "weekend": {
        "sat_over_midweek": st.mean(net[d] for d in net if weekday(d) == 5 and in_term(d)) / st.mean(vals),
        "sun_over_midweek": st.mean(net[d] for d in net if weekday(d) == 6 and in_term(d)) / st.mean(vals),
        "mon_over_midweek": st.mean(net[d] for d in net if weekday(d) == 0 and in_term(d)) / st.mean(vals),
        "fri_over_midweek": st.mean(net[d] for d in net if weekday(d) == 4 and in_term(d)) / st.mean(vals),
    },
    "site_quantiles": {},
}
for k in ("am", "pm", "night", "h07_19", "am_mid", "pm_mid", "min_mid", "cv", "mad", "hour_mad", "adt", "peak_flow", "sat_ratio", "sun_ratio"):
    x = sorted(r[k] for r in rows if r[k] is not None)
    res["site_quantiles"][k] = [x[int(p * (len(x) - 1))] for p in (0.1, 0.25, 0.5, 0.75, 0.9)]
tiers = {"big>15k": lambda r: r["adt"] > 15000, "mid5-15k": lambda r: 5000 <= r["adt"] <= 15000, "small<5k": lambda r: r["adt"] < 5000}
res["by_flow_tier"] = {}
for name, f in tiers.items():
    sub = [r for r in rows if f(r)]
    if sub:
        res["by_flow_tier"][name] = {
            "n": len(sub),
            **{k: st.median(r[k] for r in sub) for k in ("am", "pm", "night", "am_mid", "pm_mid", "cv", "hour_mad", "peak_flow")},
        }
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "network_hour_mean"}, indent=0)[:3000])
