#!/usr/bin/env python3
"""Print the parts of a compare.json that the report uses. usage: show.py RUN_DIR..."""
import json
import sys


def brief(v):
    return {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()} if isinstance(v, dict) else v


for run in sys.argv[1:]:
    r = json.load(open(f"{run}/compare.json"))
    print("#####", run)
    for k in ("routes_in_sample", "teleports", "trips_arrived", "trips_arrived_share", "max_running", "paired_trips", "clean_trajectory_share"):
        print(k, r.get(k))
    print("counts_hour", brief(r.get("counts_edge_hour")))
    print("counts_day", brief(r.get("counts_edge_day")))
    print("sim/data passes by hour", r.get("simulated_share_of_data_passes_by_hour"))
    print("paired_all", brief(r.get("paired_all")))
    print("paired_clean", brief(r.get("paired_clean")))
    for k, v in (r.get("paired_clean_by_length") or {}).items():
        print("  clean", k, brief(v))
    print("clean by hour (trips, real km/h, sim km/h)", {h: (v["trips"], round(v["real_kmh"], 1), round(v["sim_kmh"], 1)) for h, v in (r.get("paired_clean_by_hour") or {}).items() if v})
    print("leg speed pct", brief(r.get("leg_speed_kmh_pct")))
    print("robust by hour", r.get("speed_robust_by_hour_kmh"))
    print("robust by class", {c: (round(v["data_median"], 1), round(v["sim"], 1), v["passes"]) for c, v in (r.get("speed_robust_by_class_8_19_kmh") or {}).items()})
    print("robust edge-hour", brief(r.get("speed_robust_edge_hour")))
    print("space-mean by hour", r.get("speed_by_hour_kmh"))
    print("per edge 8-19", brief(r.get("speed_per_edge_8_19")))
    print("summary", r.get("summary_tail"))
