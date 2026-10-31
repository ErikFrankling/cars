#!/usr/bin/env python3
"""Speed of cars against SUMO on this machine. Writes results/bench/*.csv."""

import csv
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARS = ROOT / "target/release/cars"
SWEEP = ROOT / "target/release/sweep"
OUT = ROOT / "results/bench"
THESIS = Path("/home/erikf/projects/personal/thesis-src/bachelor/config")
DATA = Path("/home/erikf/projects/personal/cars-data")
LOCK = "/tmp/cars-gpu.lock"
BERLIN_FLAGS = ["--time-to-teleport", "120", "--ignore-junction-blocker", "20"]
SUMO_FLAGS = ["--time-to-teleport", "120", "--ignore-junction-blocker", "20", "--route-steps", "200", "--seed", "1"]

CASES = {
    "ring_200": dict(net=THESIS / "networks/ring.net.xml", routes=[THESIS / "demand/ring.rou.xml"], add=[THESIS / "vtypes.xml"], dt=0.1, begin=0, end=600, flags=[]),
    "i80_thesis": dict(net=THESIS / "networks/i80_vsl.net.xml", routes=[THESIS / "demand/i80_vsl.rou.xml"], add=[THESIS / "vtypes.xml"], dt=0.1, begin=0, end=1800, flags=[]),
    "bologna_thesis": dict(net=THESIS / "scenarios/bologna/joined_buslanes.net.xml", routes=[THESIS / "scenarios/bologna/bologna_cars.rou.xml"], add=[THESIS / "vtypes.xml", THESIS / "scenarios/bologna/joined_tls.add.xml"], dt=0.1, begin=0, end=5400, flags=[]),
    "charlottenburg_0800": dict(net=DATA / "charlottenburg/charlottenburg.net.xml", routes=[DATA / "charlottenburg/charlottenburg.rou.gz"], add=[], dt=1, begin=28800, end=33300, flags=BERLIN_FLAGS),
    "berlin_0500": dict(net=DATA / "best/berlin.net.xml", routes=[DATA / "best/berlin.rou.gz"], add=[], dt=1, begin=18000, end=21600, flags=BERLIN_FLAGS),
}


def run_sumo(c, threads=1):
    cmd = ["sumo", "-n", c["net"], "-r", ",".join(map(str, c["routes"])), "--begin", c["begin"], "--end", c["end"], "--step-length", c["dt"], "--no-step-log", "true", "--no-warnings", "true", "--duration-log.statistics", "true", "--threads", threads]
    if c["add"]:
        cmd += ["-a", ",".join(map(str, c["add"]))]
    if c["flags"]:
        cmd += SUMO_FLAGS
    t = time.time()
    out = subprocess.run([str(x) for x in cmd], capture_output=True, text=True).stdout
    wall = time.time() - t
    dur = float(re.search(r"Duration: ([\d.]+)s", out).group(1))
    ups = float(re.search(r"UPS: ([\d.]+)", out).group(1))
    return dict(engine=f"SUMO {threads} thread" + ("s" if threads > 1 else ""), wall=wall, sim_wall=dur, ups=ups)


def run_cars(c):
    cmd = ["flock", LOCK, CARS, "run", "--net", c["net"], "--routes", ",".join(map(str, c["routes"])), "--dt", c["dt"], "--begin", c["begin"], "--end", c["end"], "--capacity", "400000", "--trusted"] + c["flags"]
    if c["add"]:
        cmd += ["--additional", ",".join(map(str, c["add"]))]
    t = time.time()
    r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
    wall = time.time() - t
    m = re.search(r"wall ([\d.]+)s, ([\d.]+) M updates/s", r.stdout + r.stderr)
    return dict(engine="cars GPU", wall=wall, sim_wall=float(m.group(1)), ups=float(m.group(2)) * 1e6)


def speed():
    with open(OUT / "single.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "engine", "sim_seconds", "dt", "wall_total", "wall_sim", "updates_per_s"])
        for name, c in CASES.items():
            for fn in (lambda x: run_sumo(x, 1), lambda x: run_sumo(x, 4), run_cars):
                r = fn(c)
                w.writerow([name, r["engine"], c["end"] - c["begin"], c["dt"], round(r["wall"], 2), round(r["sim_wall"], 2), round(r["ups"])])
                f.flush()
                print(name, r, flush=True)


def scale():
    """One GPU world of many Bologna replicas: how far does throughput go?"""
    with open(OUT / "replicas.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["replicas", "wall", "steps", "updates_per_s", "vehicles_peak"])
        for seeds in (1, 4, 16, 64, 256, 512, 1024):
            out = Path(f"/tmp/bench_rep_{seeds}.csv")
            cmd = ["flock", LOCK, SWEEP, "--scenario", "bologna", "--tiers", "krauss", "--penetrations", "0", "--seeds", ",".join(map(str, range(seeds))), "--end", "1800", "--out", out]
            t = time.time()
            r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
            wall = time.time() - t
            text = r.stdout + r.stderr
            m = re.search(r"wall_seconds=([\d.]+) steps=(\d+) replicas=(\d+) peak_vehicles=(\d+)", text)
            if not m:
                print("failed", seeds, text[-400:], flush=True)
                break
            u = re.search(r"([\d.]+) M updates/s", text)
            w.writerow([seeds, m.group(1), m.group(2), float(u.group(1)) * 1e6 if u else "", m.group(4)])
            f.flush()
            print(seeds, m.group(0), u.group(0) if u else "", flush=True)


def kernels():
    b = CASES["berlin_0500"]
    with open(OUT / "kernels.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vehicles", "kernel", "ms"])
        for at in (19000, 25000, 30000):
            cmd = ["flock", LOCK, CARS, "run", "--net", b["net"], "--routes", b["routes"][0], "--dt", 1, "--begin", 18000, "--end", at + 2, "--capacity", 400000, "--trusted", "--profile-at", at] + b["flags"]
            r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
            n = 0
            for line in r.stdout.splitlines():
                m = re.match(r"profile at t=\S+ with (\d+) vehicles", line)
                if m:
                    n = int(m.group(1))
                m = re.match(r"\s+(\S+)\s+([\d.]+) ms", line)
                if m:
                    w.writerow([n, m.group(1), m.group(2)])
            f.flush()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for what in sys.argv[1:] or ["speed", "scale", "kernels"]:
        globals()[what]()


if __name__ == "__main__":
    main()
