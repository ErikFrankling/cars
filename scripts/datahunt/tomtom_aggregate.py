#!/usr/bin/env python3
"""Quantiles of TomTom Traffic Index 2025 hourly speed metrics, by city group.

Usage: tomtom_aggregate.py DATA_DIR OUT.json  (DATA_DIR holds tomtom_cities.json, tomtom_rows_part*.jsonl)
"""
import glob
import json
import os
import statistics as st
import sys

data, out = sys.argv[1:3]
cities = {c["key"]: c for c in json.load(open(os.path.join(data, "tomtom_cities.json")))}
rows = []
for fn in sorted(glob.glob(os.path.join(data, "tomtom_rows_part*.jsonl"))):
    for line in open(fn):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "metro" in r and r["key"] in cities:
            rows.append(r)
TURKEY_RU = {"TR", "RU", "UA", "BY"}


def group(c):
    if c["continent"] == "EUROPE" and c["country"] not in TURKEY_RU:
        if 500_000 <= c["population"] <= 4_000_000:
            return "europe_0.5_4M"
        if c["population"] < 500_000:
            return "europe_under_0.5M"
        return "europe_over_4M"
    return "rest_of_world"


def metrics(a):
    v = a.get("tue_thu_v")
    if not v:
        return None
    m = {
        "base_v": a["base_v"],
        "base_c": a["base_c"],
        "base_fv": a["base_fv"],
        "ampm_v": a.get("ampm_v"),
        "ampm_c": a.get("ampm_c"),
        "night_v": a["night_v"],
        "midday_v": a["midday_v"],
        "worst_am_v": a["worst_am_v"],
        "worst_pm_v": a["worst_pm_v"],
        "worst_over_night": a["worst_over_night"],
        "worst_over_midday": a["worst_over_midday"],
        "worst_over_best": min(v[6:20]) / max(v),
        "hours_c_over_30": a["hours_c_over_30"],
        "hours_c_over_50": a["hours_c_over_50"],
        "weekend_over_tue_thu_midday": sum(a["weekend_v"][10:15]) / sum(v[10:15]),
        "worst_c": max(a["tue_thu_c"]),
        "worst_hour": min(range(6, 20), key=lambda h: v[h]),
    }
    hw, nh = a.get("highways"), a.get("nonHighways")
    if hw and nh:
        m.update(
            hw_v=hw["v"],
            hw_fv=hw["fv"],
            hw_ampm_v=hw["ampm_v"],
            hw_ampm_over_fv=hw["ampm_v"] / hw["fv"] if hw["ampm_v"] else None,
            nh_v=nh["v"],
            nh_fv=nh["fv"],
            nh_ampm_v=nh["ampm_v"],
            nh_ampm_over_fv=nh["ampm_v"] / nh["fv"] if nh["ampm_v"] else None,
        )
        if hw.get("km") and nh.get("km"):
            m["hw_km_share"] = hw["km"] / (hw["km"] + nh["km"])
    if a.get("am_km") and a.get("pm_km") and a.get("base_km"):
        mean_hour = a["base_km"] / 8760
        m["am_km_over_mean_hour"] = a["am_km"] / mean_hour
        m["pm_km_over_mean_hour"] = a["pm_km"] / mean_hour
    return m


res = {"cities_parsed": len(rows)}
groups = {}
detail = {}
for r in rows:
    c = cities[r["key"]]
    g = group(c)
    for area in ("metro", "center"):
        a = r.get(area)
        if not a:
            continue
        m = metrics(a)
        if m is None:
            continue
        groups.setdefault((g, area), []).append(m)
        detail.setdefault(r["key"], {"population": c["population"], "country": c["country"], "group": g})[area] = m
        if r["key"] in ("stockholm", "berlin", "hamburg", "munich", "vienna", "copenhagen", "oslo", "helsinki", "zurich", "amsterdam", "prague", "gothenburg", "paris", "london"):
            detail[r["key"]][area + "_hourly_v"] = a["tue_thu_v"]
            detail[r["key"]][area + "_hourly_fv"] = a["tue_thu_fv"]
            detail[r["key"]][area + "_hourly_c"] = a["tue_thu_c"]
res["groups"] = {}
for (g, area), ms in sorted(groups.items()):
    q = {}
    for k in sorted({k for m in ms for k in m}):
        x = sorted(m[k] for m in ms if m.get(k) is not None)
        if x:
            q[k] = {p: round(x[int(f * (len(x) - 1))], 3) for p, f in (("p05", 0.05), ("p25", 0.25), ("p50", 0.5), ("p75", 0.75), ("p95", 0.95))}
    res["groups"][f"{g}/{area}"] = {"n": len(ms), "q": q}
res["cities"] = detail
json.dump(res, open(out, "w"), indent=1)
for g, b in res["groups"].items():
    print(g, b["n"])
    for k in ("base_v", "ampm_v", "night_v", "midday_v", "worst_over_night", "worst_over_midday", "worst_over_best", "hours_c_over_30", "hours_c_over_50", "hw_v", "hw_ampm_v", "nh_v", "nh_ampm_v", "hw_km_share", "worst_hour", "am_km_over_mean_hour", "pm_km_over_mean_hour"):
        if k in b["q"]:
            print(" ", k, b["q"][k])
print(st.mean(len(v) for v in groups.values()))
