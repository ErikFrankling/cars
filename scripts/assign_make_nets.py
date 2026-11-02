#!/usr/bin/env python3
"""Small networks and demand for the assignment loop: a grid, and a grid split by a river with few bridges.
usage: assign_make_nets.py OUT_DIR"""
import csv, gzip, os, subprocess, sys
import numpy as np

VTYPES = '<additional><vType id="passenger" vClass="passenger" accel="2.6" decel="4.5" sigma="0.5" tau="1" length="5" minGap="2.5" speedDev="0.1"/></additional>\n'


def grid(out, n, spacing=300.0, name="grid", lanes=1, remove=()):
    net = f"{out}/{name}.net.xml"
    subprocess.run(["netgenerate", "--grid", "--grid.number", str(n), "--grid.length", str(spacing), "--default.lanenumber", str(lanes), "--default.speed", "13.89",
                    "--default-junction-type", "priority", "--no-turnarounds", "true", "--seed", "1", "-o", net, "--no-warnings"], check=True)
    if remove:
        subprocess.run(["netconvert", "-s", net, "--remove-edges.explicit", ",".join(remove), "-o", net, "--no-warnings"], check=True)
    return net


def name(r, c):
    return f"{chr(65 + c)}{r}"


def edges(n, skip=()):
    out = []
    for r in range(n):
        for c in range(n):
            for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                r2, c2 = r + dr, c + dc
                if 0 <= r2 < n and 0 <= c2 < n:
                    e = name(r, c) + name(r2, c2)
                    if e not in skip:
                        out.append((e, r, c, r2, c2))
    return out


def demand(path, es, trips, rng, tau_cells=5.0, peak=4500.0, sigma=1500.0, keep=lambda a, b: True):
    pos = np.array([[e[1] + e[3], e[2] + e[4]] for e in es], float) / 2
    out = []
    while len(out) < trips:
        a, b = rng.integers(len(es), size=(2, 20000))
        d = np.abs(pos[a] - pos[b]).sum(axis=1)
        ok = (a != b) & (rng.random(20000) < np.exp(-d / tau_cells)) & (d >= 2)
        for i, j in zip(a[ok], b[ok]):
            if keep(es[i], es[j]):
                out.append((i, j))
    deps = np.clip(rng.normal(peak, sigma, trips), 0, 3 * peak)
    order = np.argsort(deps)
    with gzip.open(path, "wt") as f:
        w = csv.writer(f)
        w.writerow("id,class,o_edge,d_edge,desired_arrival_s,depart_s,earliest_s,latest_s,tour,tour_seq,vtype".split(","))
        for k, t in enumerate(order):
            i, j = out[t]
            dep = float(deps[t])
            w.writerow([k, 0, es[i][0], es[j][0], "nan", f"{dep:.1f}", f"{max(0, dep - 3600):.1f}", f"{dep + 900:.1f}", k, 0, "passenger"])


def main(out):
    os.makedirs(out, exist_ok=True)
    with open(f"{out}/vtypes.add.xml", "w") as f:
        f.write(VTYPES)
    rng = np.random.default_rng(7)
    n = 13
    grid(out, n)
    es = edges(n)
    for load, trips in (("100", 12000), ("150", 18000), ("200", 24000), ("300", 36000)):
        demand(f"{out}/grid_{load}.csv.gz", es, trips, rng)
    # River between rows 5 and 6: only some columns have bridges.
    for label, bridges, trips_list in (("river1", (6,), (4000, 8000, 16000)), ("river3", (2, 6, 10), (16000,))):
        rm = []
        for c in range(n):
            if c not in bridges:
                rm += [name(5, c) + name(6, c), name(6, c) + name(5, c)]
        grid(out, n, name=label, remove=rm)
        es2 = edges(n, skip=set(rm))
        for trips in trips_list:
            demand(f"{out}/{label}_{trips}.csv.gz", es2, trips, rng, tau_cells=8.0, sigma=1200.0)
        with open(f"{out}/{label}.cuts.csv", "w") as f:
            f.write("cut,edge,dir\n")
            for c in bridges:
                f.write(f"river,{name(5, c)}{name(6, c)},s\nriver,{name(6, c)}{name(5, c)},n\n")


main(sys.argv[1])
