#!/usr/bin/env python3
"""Scale the fitted Stockholm demand and spread each source band over a typical weekday profile."""

import gzip
import random
import re
import sys

BANDS = [
    (6, 18, [0.06, 0.11, 0.10, 0.07, 0.06, 0.065, 0.07, 0.07, 0.075, 0.095, 0.125, 0.11]),
    (18, 22, [0.45, 0.25, 0.17, 0.13]),
    (22, 30, [0.35, 0.2, 0.12, 0.07, 0.05, 0.04, 0.07, 0.1]),
]


def retime(t, rng):
    h = t / 3600.0
    h2 = h + 24 if h < 6 else h
    for lo, hi, weights in BANDS:
        if lo <= h2 < hi:
            x = rng.random()
            for i, w in enumerate(weights):
                x -= w
                if x <= 0:
                    return ((lo + i + rng.random()) % 24) * 3600.0
    return t


def main():
    src, dst, keep = sys.argv[1], sys.argv[2], float(sys.argv[3])
    rng = random.Random(7)
    head, trips, tail = [], [], ["</routes>\n"]
    rx = re.compile(r'depart="([\d.]+)"')
    with gzip.open(src, "rt") as f:
        current = None
        for line in f:
            if "<vehicle" in line and "/>" in line:
                if rng.random() < keep:
                    t = retime(float(rx.search(line).group(1)), rng)
                    trips.append((t, rx.sub(f'depart="{t:.2f}"', line)))
            elif "<vehicle" in line:
                current = [line]
            elif current is not None:
                current.append(line)
                if "</vehicle>" in line:
                    if rng.random() < keep:
                        t = retime(float(rx.search(current[0]).group(1)), rng)
                        current[0] = rx.sub(f'depart="{t:.2f}"', current[0])
                        trips.append((t, "".join(current)))
                    current = None
            elif "</routes>" not in line:
                head.append(line)
    trips.sort(key=lambda x: x[0])
    with gzip.open(dst, "wt", compresslevel=3) as w:
        w.writelines(head)
        for _, text in trips:
            w.write(text)
        w.writelines(tail)
    print(len(trips), "trips")


if __name__ == "__main__":
    main()
