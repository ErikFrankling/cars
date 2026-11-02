#!/usr/bin/env python3
"""How long turning cars are held by pedestrians and cyclists at one real signal junction.

DLR Urban Traffic, AIM Research Intersection, Braunschweig, Sunday 24 Sep 2023. Reads the zip in
place, one 15 minute file at a time, thinned to 2 Hz.

A turning vehicle has a heading change of 45-135 deg between its first and last 15 m of travel.
Its turn starts where heading has changed 10% of the total and ends where it has changed 100%.
Held: below 1.5 m/s inside the turn.
Held by a road user: on that second, a moving pedestrian or cyclist (over 0.3 m/s) lies 0-12 m
ahead and within 4 m to the side. Held otherwise: nothing of that kind there.

usage: dlr_vru_block.py first_hhmm last_hhmm out.json
"""
import io
import json
import re
import sys
import zipfile

import numpy as np
import pandas as pd

Z = "/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-dlrut/DLR-Urban-Traffic-dataset_v1-3-1.zip"
COLS = ["timestamp", "id", "center_easting", "center_northing", "velocity_magnitude", "dimension_length",
        "classifications_car", "classifications_van", "classifications_truck",
        "classifications_pedestrian", "classifications_bicycle"]


def load(z, name):
    with z.open(name) as f:
        d = pd.read_csv(io.TextIOWrapper(f), usecols=COLS)
    t = pd.to_datetime(d.timestamp, utc=True, format="ISO8601")
    d["t"] = (t - t.iloc[0].normalize()).dt.total_seconds()
    d["bin"] = (d.t * 2).astype(np.int64)
    d = d.drop_duplicates(["id", "bin"]).drop(columns=["timestamp"])
    d = d.rename(columns={"center_easting": "x", "center_northing": "y", "velocity_magnitude": "v", "dimension_length": "L"})
    return d


def heading(x, y, a, b):
    return np.arctan2(y[b] - y[a], x[b] - x[a])


def analyse(d):
    veh = d[(d.classifications_car + d.classifications_van + d.classifications_truck > 0.5) & d.L.between(3, 12)]
    vru = d[(d.classifications_pedestrian + d.classifications_bicycle > 0.5) & (d.v > 0.3)]
    ped = d[d.classifications_pedestrian > 0.5].id.nunique()
    bike = d[d.classifications_bicycle > 0.5].id.nunique()
    vru_at = {b: g[["x", "y"]].values for b, g in vru.groupby("bin")}
    out = []
    n_all_cars = veh.id.nunique()
    for i, g in veh.groupby("id"):
        g = g.sort_values("t")
        x, y = g.x.values, g.y.values
        if len(x) < 8:
            continue
        s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
        if s[-1] < 40:
            continue
        a1 = int(np.searchsorted(s, 15))
        b0 = int(np.searchsorted(s, s[-1] - 15))
        if a1 >= b0:
            continue
        h0, h1 = heading(x, y, 0, a1), heading(x, y, b0, len(x) - 1)
        turn = (h1 - h0 + np.pi) % (2 * np.pi) - np.pi
        if not (np.radians(45) <= abs(turn) <= np.radians(135)):
            continue
        # Smoothed heading along the track, by 6 m stretches.
        hs = []
        for k in range(len(x)):
            u = int(np.searchsorted(s, s[k] + 3))
            w = int(np.searchsorted(s, s[k] - 3))
            u = min(u, len(x) - 1)
            hs.append(np.arctan2(y[u] - y[w], x[u] - x[w]) if u > w else np.nan)
        hs = np.array(hs)
        ch = np.abs((hs - h0 + np.pi) % (2 * np.pi) - np.pi)
        ok = np.where(ch >= 0.1 * abs(turn))[0]
        end = np.where(ch >= 0.95 * abs(turn))[0]
        if not len(ok) or not len(end) or end[0] <= ok[0]:
            continue
        i0, i1 = ok[0], end[0]
        v = g.v.values
        bins = g.bin.values
        held = 0.0
        held_vru = 0.0
        for k in range(i0, i1 + 1):
            if v[k] >= 1.5:
                continue
            held += 0.5
            pts = vru_at.get(bins[k])
            if pts is None or not np.isfinite(hs[k]):
                continue
            rx, ry = pts[:, 0] - x[k], pts[:, 1] - y[k]
            al = rx * np.cos(hs[k]) + ry * np.sin(hs[k])
            la = -rx * np.sin(hs[k]) + ry * np.cos(hs[k])
            if np.any((al > 0) & (al < 12) & (np.abs(la) < 4)):
                held_vru += 0.5
        # In east-north coordinates a negative heading change is a right turn.
        out.append(dict(side="right" if turn < 0 else "left", held=held, held_vru=held_vru,
                        turn_s=float(g.t.values[i1] - g.t.values[i0])))
    return out, ped, bike, n_all_cars


def save(first, upto, files, cars, peds, bikes, rows, path):
    res = dict(window=[first, upto], files=files, hours=files / 4, vehicles=cars,
               pedestrian_ids=peds, bicycle_ids=bikes)
    t = pd.DataFrame(rows)
    for side in ("right", "left"):
        q = t[t.side == side]
        h = q.held_vru[q.held_vru > 0]
        res[side] = dict(
            n=len(q),
            share_held_any=float((q.held > 0).mean()),
            share_held_by_vru=float((q.held_vru > 0).mean()),
            mean_held_s=float(q.held.mean()),
            mean_held_vru_s=float(q.held_vru.mean()),
            median_held_vru_when_held=float(h.median()) if len(h) else None,
            p90_held_vru_when_held=float(h.quantile(0.9)) if len(h) else None,
            median_turn_s=float(q.turn_s.median()),
        )
    with open(path, "w") as f:
        json.dump(res, f, indent=1)
    return res


def main():
    first, last, path = sys.argv[1:4]
    z = zipfile.ZipFile(Z)
    names = sorted(n for n in z.namelist() if "raw_data/trajectories/trajectories_" in n)
    rows, peds, bikes, cars, files = [], 0, 0, 0, 0
    for n in names:
        m = re.search(r"230924-(\d{4})\d\d_", n)
        if not m or not (first <= m.group(1) < last):
            continue
        d = load(z, n)
        r, p, b, c = analyse(d)
        rows += r
        peds += p
        bikes += b
        cars += c
        files += 1
        print(m.group(1), len(r), p, b, c, file=sys.stderr, flush=True)
        res = save(first, m.group(1), files, cars, peds, bikes, rows, path)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
