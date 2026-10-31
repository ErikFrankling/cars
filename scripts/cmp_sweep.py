#!/usr/bin/env python3
"""A thesis sweep against the thesis's SUMO results, tier by tier."""

import sys

import pandas as pd

THESIS = "/home/erikf/projects/personal/thesis-src/bachelor/results/processed/metrics.csv"
COLS = ["speed", "travel_time", "time_loss", "waiting_time", "completed"]


def main():
    a = pd.read_csv(sys.argv[1])
    b = pd.read_csv(THESIS)
    b = b[b.scenario == a.scenario.iloc[0]]
    j = a.groupby(["tier", "penetration"])[COLS].mean().join(b.groupby(["tier", "penetration"])[COLS].mean(), lsuffix="_g", rsuffix="_s", how="inner")
    ps = sorted(a.penetration.unique())
    show = [p for p in ps if p in (0.0, 0.25, 0.5, 0.75, 1.0)]
    print(j[j.index.get_level_values(1).isin(show)][[x + s for x in COLS for s in ("_g", "_s")]].round(1).to_string())
    for tier, t in j.groupby(level=0):
        err = ((t.speed_g - t.speed_s).abs() / t.speed_s).mean()
        tt = ((t.travel_time_g - t.travel_time_s).abs() / t.travel_time_s).mean()
        print(f"{tier}: mean abs error speed {err:.1%}, travel time {tt:.1%}")


if __name__ == "__main__":
    main()
