#!/usr/bin/env python3
"""Check a simulated day against the normal-day bands in research/truth/data-hunt/14-normal-day.md.

Usage: normal_day_gate.py RUN.json POPULATION CARS [RUN.json POPULATION CARS ...]
RUN.json comes from normal_day_runs.py. PASS is inside the plausible band, WARN is outside it but
inside the hard band, FAIL is outside the hard band ("this isn't a real city").
Bands marked None are one-sided.
"""
import json
import sys

# name, value function, plausible low, plausible high, hard low, hard high
BANDS = [
    ("AM peak hour, share of daily km", lambda r, p, c: r["shape_vkm"]["am_peak_hour"], 0.05, 0.085, 0.045, 0.10),
    ("PM peak hour, share of daily km", lambda r, p, c: r["shape_vkm"]["pm_peak_hour"], 0.055, 0.095, 0.05, 0.11),
    ("AM peak / midday hour", lambda r, p, c: r["shape_vkm"]["am_over_midday"], 1.0, 1.4, 0.9, 1.7),
    ("PM peak / midday hour", lambda r, p, c: r["shape_vkm"]["pm_over_midday"], 1.0, 1.55, 0.95, 1.9),
    ("Night 22-06, share of daily km", lambda r, p, c: r["shape_vkm"]["night_22_06"], 0.055, 0.125, 0.04, 0.17),
    ("07-19, share of daily km", lambda r, p, c: r["shape_vkm"]["h07_19"], 0.70, 0.82, 0.65, 0.85),
    ("Lowest hour / midday hour", lambda r, p, c: r["shape_vkm"]["lowest_over_midday"], 0.04, 0.16, 0.02, 0.20),
    ("Vehicle-km per person per weekday", lambda r, p, c: r["total_vkm"] / p, 8.0, 15.0, 6.0, 20.0),
    ("Vehicles on road at peak, share of cars", lambda r, p, c: r["peak_running"] / c, 0.05, 0.11, 0.035, 0.15),
    ("Mean network speed, km/h", lambda r, p, c: r["speed_mean"], 28.0, 46.0, 20.0, 55.0),
    ("Worst hour 06-22 / night speed", lambda r, p, c: min(r["speed_by_hour"][6:23]) / r["speed_dip"]["night_02_05"], 0.51, 0.745, 0.42, 0.84),
    ("Worst hour 06-22 / midday speed", lambda r, p, c: min(r["speed_by_hour"][6:23]) / r["speed_dip"]["midday_10_15"], 0.735, 0.90, 0.67, 0.95),
    ("Hour of worst speed (local, 24h)", lambda r, p, c: min(range(6, 23), key=lambda h: r["speed_by_hour"][h]), 8, 18, 7, 19),
    ("Hours with travel-time index above 1.3", lambda r, p, c: sum(1 for x in r["tti_by_hour"] if x and x > 1.3), 6, 15, 2, 17),
    ("Mean trip length, km", lambda r, p, c: r["trips"]["mean_km"], 7.0, 13.0, 5.0, 19.0),
    ("Mean trip duration, min", lambda r, p, c: r["trips"]["mean_min"], 16.0, 30.0, 13.0, 35.0),
    ("Mean trip speed, km/h", lambda r, p, c: r["trips"]["mean_trip_speed_kmh"], 20.0, 35.0, 16.0, 40.0),
]


def main_road(r):
    main = [c for c in r["vkm_by_class"] if c in ("trunk", "primary", "secondary", "tertiary")]
    lane = sum(r["lane_km"][c] for c in main)
    km = sum(r["vkm_by_class"][c] for c in main)
    hours = sum(r["veh_h_by_class"][c] for c in main)
    peak = sum(r["vkm_by_class"][c] * r["shape_vkm_by_class"][c]["pm_peak_hour"] for c in main)
    return peak / lane, peak / lane / (km / hours), km / hours


MAIN = [
    ("Main-road peak flow / capacity 521 veh/h/lane", lambda r: main_road(r)[0] / 521, 0.50, 1.05, 0.40, 1.2),
    ("Main-road peak density / critical 27.8 veh/km/lane", lambda r: main_road(r)[1] / 27.8, 0.40, 1.05, 0.30, 1.4),
    ("Main-road daily mean speed, km/h", lambda r: main_road(r)[2], 19.0, 36.0, 15.0, 40.0),
]


def grade(v, lo, hi, hlo, hhi):
    if lo <= v <= hi:
        return "PASS"
    if hlo <= v <= hhi:
        return "WARN"
    return "FAIL"


args = sys.argv[1:]
for i in range(0, len(args), 3):
    r = json.load(open(args[i]))
    p, c = float(args[i + 1]), float(args[i + 2])
    print(f"## {r['name']}")
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    rows = [(n, f(r, p, c), lo, hi, hlo, hhi) for n, f, lo, hi, hlo, hhi in BANDS]
    rows += [(n, f(r), lo, hi, hlo, hhi) for n, f, lo, hi, hlo, hhi in MAIN]
    for n, v, lo, hi, hlo, hhi in rows:
        g = grade(v, lo, hi, hlo, hhi)
        counts[g] += 1
        print(f"| {n} | {v:.3g} | {lo:g} to {hi:g} | {hlo:g} to {hhi:g} | {g} |")
    print(counts)
