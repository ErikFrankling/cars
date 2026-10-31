#!/usr/bin/env python3
"""Compare a sweep CSV from cars against the thesis's SUMO metrics."""
import sys
import pandas as pd

a = pd.read_csv(sys.argv[1])
b = pd.read_csv("/home/erikf/projects/personal/thesis-src/bachelor/results/processed/metrics.csv")
scen = a.scenario.iloc[0]
b = b[(b.scenario == scen) & (b.tier.isin(a.tier.unique())) & (b.penetration.isin(a.penetration.unique()))]
cols = sys.argv[2].split(",") if len(sys.argv) > 2 else ["speed", "edge_flow", "density", "travel_time", "waiting_time", "time_loss", "completed"]
ga = a.groupby(["tier", "penetration"])[cols].mean()
gb = b.groupby(["tier", "penetration"])[cols].mean()
j = ga.join(gb, lsuffix="_g", rsuffix="_s")
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 500)
print(j[[f"{c}_{s}" for c in cols for s in "gs"]].round(2))
err = ((ga - gb).abs() / gb.abs().clip(lower=1e-6)).mean()
print("mean abs relative error:")
print(err.round(4))
