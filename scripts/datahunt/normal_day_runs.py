#!/usr/bin/env python3
"""Network-level metrics of one simulated day, for research/truth/data-hunt/14-normal-day.md.

Usage: normal_day_runs.py NAME NET.xml EDGES.csv TRIPS.csv SUMMARY.csv OUT.json
edges.csv columns: begin,edge,samples,distance,entered,teleports (samples are vehicle-seconds at dt 1).
"""
import csv
import json
import re
import sys
from collections import defaultdict

name, net, edges_csv, trips_csv, summary_csv, out = sys.argv[1:7]

CLASS = {
    "motorway": "motorway",
    "motorway_link": "motorway",
    "trunk": "trunk",
    "trunk_link": "trunk",
    "primary": "primary",
    "primary_link": "primary",
    "secondary": "secondary",
    "secondary_link": "secondary",
    "tertiary": "tertiary",
    "tertiary_link": "tertiary",
    "residential": "local",
    "living_street": "local",
    "unclassified": "local",
    "service": "local",
    "road": "local",
}

edge_re = re.compile(r'<edge id="([^"]+)"([^>]*)>')
type_re = re.compile(r'type="([^"]*)"')
func_re = re.compile(r'function="([^"]*)"')
lane_re = re.compile(r'<lane id="[^"]+"([^>]*)')
speed_re = re.compile(r'speed="([0-9.]+)"')
length_re = re.compile(r'length="([0-9.]+)"')

info = {}
current = None
with open(net, encoding="utf-8", errors="replace") as f:
    for line in f:
        s = line.lstrip()
        if s.startswith("<edge "):
            m = edge_re.search(s)
            if not m or func_re.search(m.group(2)):
                current = None
                continue
            t = type_re.search(m.group(2))
            t = t.group(1) if t else ""
            short = t.split("|")[0].split(".")[-1]
            current = {"class": CLASS.get(short, "other"), "lanes": 0, "len": 0.0, "speed": 0.0}
            info[m.group(1)] = current
        elif s.startswith("<lane ") and current is not None:
            a = lane_re.search(s).group(1)
            current["lanes"] += 1
            current["len"] = float(length_re.search(a).group(1))
            current["speed"] = max(current["speed"], float(speed_re.search(a).group(1)))
        elif s.startswith("</edge>"):
            current = None

road_km = defaultdict(float)
lane_km = defaultdict(float)
for e in info.values():
    road_km[e["class"]] += e["len"] / 1000
    lane_km[e["class"]] += e["len"] * e["lanes"] / 1000

H = range(24)
vs = defaultdict(lambda: [0.0] * 24)
vkm = defaultdict(lambda: [0.0] * 24)
ent = defaultdict(lambda: [0.0] * 24)
freeflow_s = defaultdict(lambda: [0.0] * 24)
slow_km = defaultdict(lambda: [0.0] * 24)
fine_vs = defaultdict(float)
fine_vkm = defaultdict(float)
unknown_km = 0.0
total_all = 0.0

# --diagnose-at merges the output bin before each diagnosis into the next one: its begin is missing
# and the following bin holds two bins' worth. Those are split evenly back into both.
with open(edges_csv) as f:
    seen = sorted({int(float(row["begin"])) for row in csv.DictReader(f)})
width = min(b - a for a, b in zip(seen, seen[1:])) if len(seen) > 1 else 3600
stamped = {b for a, b in zip(seen, seen[1:]) if b - a == 2 * width}

with open(edges_csv) as f:
    for row in csv.DictReader(f):
        begin = int(float(row["begin"]))
        if begin // 3600 > 23:
            continue
        d_all = float(row["distance"])
        sam_all = float(row["samples"])
        ent_all = float(row["entered"])
        total_all += d_all
        parts = [(begin - width, 0.5), (begin, 0.5)] if begin in stamped else [(begin, 1.0)]
        e = info.get(row["edge"])
        for b, w in parts:
            h = b // 3600
            d = d_all * w
            sam = sam_all * w
            if e is None:
                unknown_km += d
                c = "junction"
            else:
                c = e["class"]
                if e["speed"] > 0:
                    freeflow_s[c][h] += d / e["speed"]
                if sam > 0 and d / sam < 0.5 * e["speed"]:
                    slow_km[c][h] += d
            vs[c][h] += sam
            vkm[c][h] += d
            ent[c][h] += ent_all * w
            fine_vs[b] += sam
            fine_vkm[b] += d


def sum_h(table, hours):
    return sum(sum(table[c][h] for h in hours) for c in table)


def shares(row):
    tot = sum(row) or 1.0
    am = max(row[6:10])
    pm = max(row[15:19])
    mid = sum(row[10:15]) / 5
    return {
        "am_peak_hour": am / tot,
        "pm_peak_hour": pm / tot,
        "am_07_09": sum(row[7:9]) / tot,
        "pm_16_18": sum(row[16:18]) / tot,
        "night_22_06": (sum(row[22:24]) + sum(row[0:6])) / tot,
        "h06_18": sum(row[6:18]) / tot,
        "h18_22": sum(row[18:22]) / tot,
        "h07_19": sum(row[7:19]) / tot,
        "am_over_midday": am / mid if mid else None,
        "pm_over_midday": pm / mid if mid else None,
        "lowest_over_midday": min(row) / mid if mid else None,
    }


classes = sorted(vkm)
result = {"name": name, "edges_in_net": len(info), "unknown_edge_km": unknown_km / 1000}
result["merged_bins_split"] = sorted(stamped)
running = [(float(r["time"]), float(r["running"])) for r in csv.DictReader(open(summary_csv))]
result["peak_running"] = max(x for _, x in running)
result["peak_running_hour"] = max(running, key=lambda p: p[1])[0] / 3600
result["total_vkm"] = total_all / 1000
result["road_km"] = dict(road_km)
result["lane_km"] = dict(lane_km)
result["total_road_km"] = sum(road_km.values())
result["total_lane_km"] = sum(lane_km.values())
result["vkm_by_class"] = {c: sum(vkm[c]) / 1000 for c in classes}
result["vkm_share_by_class"] = {c: sum(vkm[c]) / total_all for c in classes}
result["veh_h_by_class"] = {c: sum(vs[c]) / 3600 for c in classes}

all_vkm = [sum(vkm[c][h] for c in classes) for h in H]
all_vs = [sum(vs[c][h] for c in classes) for h in H]
all_ent = [sum(ent[c][h] for c in classes) for h in H]
result["vkm_by_hour"] = [x / 1000 for x in all_vkm]
result["shape_vkm"] = shares(all_vkm)
result["shape_entries"] = shares(all_ent)
result["shape_vkm_by_class"] = {c: shares(vkm[c]) for c in classes if sum(vkm[c]) > 0}
result["speed_by_hour"] = [3.6 * d / s if s else None for d, s in zip(all_vkm, all_vs)]
result["speed_mean"] = 3.6 * sum(all_vkm) / sum(all_vs)
result["speed_by_class_hour"] = {
    c: [3.6 * d / s if s else None for d, s in zip(vkm[c], vs[c])] for c in classes
}
result["speed_by_class"] = {c: 3.6 * sum(vkm[c]) / sum(vs[c]) for c in classes if sum(vs[c])}
result["tti_by_hour"] = [
    (sum(vs[c][h] for c in classes if c != "junction") / sum(freeflow_s[c][h] for c in classes if c != "junction"))
    if sum(freeflow_s[c][h] for c in classes if c != "junction")
    else None
    for h in H
]
result["share_km_below_half_limit_by_hour"] = [
    sum(slow_km[c][h] for c in classes) / all_vkm[h] if all_vkm[h] else None for h in H
]
sp = [x for x in result["speed_by_hour"][10:15] if x]
peak = [result["speed_by_hour"][h] for h in (7, 8, 16, 17)]
night = [result["speed_by_hour"][h] for h in (2, 3, 4)]
result["speed_dip"] = {
    "night_02_05": sum(night) / 3,
    "midday_10_15": sum(sp) / len(sp),
    "worst_hour": min(x for x in result["speed_by_hour"] if x),
    "peak_07_09_16_18": sum(peak) / 4,
    "worst_over_night": min(x for x in result["speed_by_hour"] if x) / (sum(night) / 3),
}
lane_total = result["total_lane_km"]
road_total = result["total_road_km"]
result["vkm_per_road_km_day"] = result["total_vkm"] / road_total
result["vkm_per_lane_km_day"] = result["total_vkm"] / lane_total
result["vkm_per_lane_km_day_by_class"] = {c: sum(vkm[c]) / 1000 / lane_km[c] for c in classes if lane_km.get(c)}
result["vkm_per_road_km_day_by_class"] = {c: sum(vkm[c]) / 1000 / road_km[c] for c in classes if road_km.get(c)}

mfd = []
bins = sorted(fine_vs)
step = bins[1] - bins[0] if len(bins) > 1 else 3600
for b in bins:
    k = fine_vs[b] / step / lane_total
    q = fine_vkm[b] / 1000 / (step / 3600) / lane_total
    mfd.append({"begin": b, "accum": fine_vs[b] / step, "veh_per_lane_km": k, "veh_h_per_lane": q})
result["mfd_step_s"] = step
result["mfd"] = mfd
result["peak_accumulation"] = max(m["accum"] for m in mfd)
result["peak_density_veh_lane_km"] = max(m["veh_per_lane_km"] for m in mfd)
result["peak_flow_veh_h_lane"] = max(m["veh_h_per_lane"] for m in mfd)
mi = {c: sum(vkm[c]) for c in classes}

dur = len_ = wait = loss = n = 0.0
dep = [0] * 24
bins_km = [0, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 50, 1e9]
hist = [0] * (len(bins_km) - 1)
lengths = []
durs = []
with open(trips_csv) as f:
    for row in csv.DictReader(f):
        try:
            d = float(row["duration"])
            l = float(row["route_length"])
        except (ValueError, KeyError):
            continue
        h = int(float(row["depart"])) // 3600
        if 0 <= h < 24:
            dep[h] += 1
        dur += d
        len_ += l
        wait += float(row["waiting"])
        loss += float(row["time_loss"])
        n += 1
        lengths.append(l)
        durs.append(d)
        km = l / 1000
        for i in range(len(hist)):
            if bins_km[i] <= km < bins_km[i + 1]:
                hist[i] += 1
                break
lengths.sort()
durs.sort()


def q(arr, p):
    return arr[int(p * (len(arr) - 1))]


result["trips"] = {
    "completed": n,
    "mean_km": len_ / n / 1000,
    "median_km": q(lengths, 0.5) / 1000,
    "p90_km": q(lengths, 0.9) / 1000,
    "mean_min": dur / n / 60,
    "median_min": q(durs, 0.5) / 60,
    "p90_min": q(durs, 0.9) / 60,
    "mean_trip_speed_kmh": (len_ / 1000) / (dur / 3600),
    "mean_wait_s": wait / n,
    "mean_loss_s": loss / n,
    "loss_share_of_duration": loss / dur,
    "by_depart_hour": dep,
    "shape_departures": shares(dep),
    "length_hist_edges_km": bins_km[:-1],
    "length_hist": hist,
}
with open(out, "w") as f:
    json.dump(result, f, indent=1)
print(json.dumps({k: result[k] for k in ("total_vkm", "total_road_km", "total_lane_km", "speed_mean", "speed_dip", "shape_vkm", "peak_accumulation", "peak_density_veh_lane_km", "peak_flow_veh_h_lane", "vkm_per_lane_km_day", "vkm_per_road_km_day", "vkm_share_by_class", "speed_by_class", "trips")}, indent=0)[:3500])
