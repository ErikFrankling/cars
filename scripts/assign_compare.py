#!/usr/bin/env python3
"""flows A.csv B.csv: per-edge flow agreement between two runs (columns edge,flow).
cells TRUTH.csv CALIBRATED.csv: does a calibrated OD recover known truth, against its prior?
pair A_cells.csv B_cells.csv: two calibrations from different priors. Similar counts with different OD means unidentified."""
import csv, json, sys
import numpy as np


def table(path, key, val):
    with open(path) as f:
        return {r[key]: float(r[val]) for r in csv.DictReader(f)}


def stats(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return {"n": len(a), "corr": float(np.corrcoef(a, b)[0, 1]), "sum_ratio": float(a.sum() / max(b.sum(), 1e-9)), "wape": float(np.abs(a - b).sum() / max(b.sum(), 1e-9)), "rmse_over_mean": float(np.sqrt(((a - b) ** 2).mean()) / max(b.mean(), 1e-9))}


def pair_key(c):
    return int(c) >> 16


def by_pair(tbl):
    out = {}
    for c, v in tbl.items():
        out[pair_key(c)] = out.get(pair_key(c), 0.0) + v
    return out


def main():
    mode = sys.argv[1]
    if mode == "flows":
        a, b = table(sys.argv[2], "edge", "flow"), table(sys.argv[3], "edge", "flow")
        keys = [k for k in a if k in b and (a[k] > 0 or b[k] > 0)]
        print(json.dumps(stats([a[k] for k in keys], [b[k] for k in keys]), indent=1))
    elif mode == "cells":
        truth = by_pair(table(sys.argv[2], "cell", "q"))
        fit = by_pair(table(sys.argv[3], "cell", "q"))
        prior = by_pair(table(sys.argv[3], "cell", "q0"))
        keys = sorted(set(truth) | set(fit))
        g = lambda t: [t.get(k, 0.0) for k in keys]
        print(json.dumps({"prior_vs_truth": stats(g(prior), g(truth)), "calibrated_vs_truth": stats(g(fit), g(truth))}, indent=1))
    elif mode == "pair":
        a, b = by_pair(table(sys.argv[2], "cell", "q")), by_pair(table(sys.argv[3], "cell", "q"))
        keys = sorted(set(a) | set(b))
        print(json.dumps(stats([a.get(k, 0.0) for k in keys], [b.get(k, 0.0) for k in keys]), indent=1))


main()
