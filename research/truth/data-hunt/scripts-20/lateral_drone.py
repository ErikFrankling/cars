#!/usr/bin/env python3
"""Lateral behaviour measured from drone tracks, with no lane labels.

Input: Helsinki drone zip, or CSV files in Pully, Swiss roundabout or pNEUMA form.
For each file:
- tracks are cut into 1 s points in a local metric frame;
- a corridor is a 10 m cell plus a heading bin; within it, lateral position is measured
  across the mean heading;
- lanes are not assumed: stopped side-by-side pairs give the separation people choose,
  and cross-corridor spread gives how far cars sit from one line.

Measures:
  pair_sep_m: for pairs both slower than 0.5 m/s, same heading within 15 deg, overlapping
      lengthwise (|dlong| < 3 m), the centre to centre lateral distance. A two-abreast queue
      in one lane would show up below about 2.5 m.
  turn_spread_m: for movements (entry cell to exit cell), lateral SD of cars at 20 evenly
      spaced places along the movement's mean path, split into the straight and the turning.
  straight_spread_m: the same for movements with heading change under 15 deg.
  motion split: stopped pair share and two-wheeler share by type.

Run from another directory with python -I. Prints JSON.
"""
import csv
import io
import json
import math
import sys
import zipfile
from collections import defaultdict

CAR_TYPES = {"Car", "Taxi", "Medium Vehicle", "Van", "Heavy Vehicle", "Truck", "Bus"}


def read_rows(path):
    """Yields (name, iterator of (id, type, lon, lat, t, speed or None))."""
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        for n in sorted(z.namelist()):
            if n.endswith(".csv"):
                with z.open(n) as f:
                    yield n, parse_std(io.TextIOWrapper(f, encoding="utf-8"))
    else:
        with open(path, encoding="utf-8") as f:
            head = f.readline()
            f.seek(0)
            if head.startswith("track_id;"):
                yield path.rsplit("/", 1)[-1], parse_pneuma(f)
            else:
                yield path.rsplit("/", 1)[-1], parse_std(f)


def parse_time(s):
    s = s.strip()
    if " " in s:
        s = s.split(" ")[1]
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def parse_std(f):
    r = csv.DictReader(f)
    for row in r:
        idk = row.get("track_id") or row.get("veh_id")
        typ = row.get("type") or row.get("veh_type")
        t = row.get("time") or row.get("datetime")
        yield idk, typ, float(row["lon"]), float(row["lat"]), parse_time(t), None


def parse_pneuma(f):
    f.readline()
    for line in f:
        p = [x.strip() for x in line.strip().strip(";").split(";")]
        if len(p) < 10:
            continue
        idk, typ = p[0], p[1]
        vals = p[4:]
        # lat lon speed lon_acc lat_acc time, repeated. Keep one row per second of track.
        for i in range(0, len(vals) - 5, 6 * 25):
            yield idk, typ, float(vals[i + 1]), float(vals[i]), float(vals[i + 5]), float(vals[i + 2])


def tracks_1hz(rows):
    """Reduce to one point per second per track, in metres from the first point seen."""
    out = defaultdict(list)
    types = {}
    lon0 = lat0 = None
    last = {}
    for idk, typ, lon, lat, t, _sp in rows:
        if lon0 is None:
            lon0, lat0 = lon, lat
            kx = 111320.0 * math.cos(math.radians(lat0))
        if idk in last and t - last[idk] < 0.999:
            continue
        last[idk] = t
        types[idk] = typ
        out[idk].append((t, (lon - lon0) * kx, (lat - lat0) * 110574.0))
    return out, types


def angdiff(a, b):
    d = (a - b + math.pi) % (2 * math.pi) - math.pi
    return d


def analyse(tracks, types):
    # pairs at each second
    by_t = defaultdict(list)
    moving_tracks = {}
    for k, pts in tracks.items():
        if types.get(k) not in CAR_TYPES or len(pts) < 8:
            continue
        # heading from smoothed motion
        for i in range(len(pts)):
            t, x, y = pts[i]
            a = max(0, i - 3)
            b = min(len(pts) - 1, i + 3)
            dx, dy = pts[b][1] - pts[a][1], pts[b][2] - pts[a][2]
            dist = math.hypot(dx, dy)
            sp = 0.0
            if i > 0:
                sp = math.hypot(x - pts[i - 1][1], y - pts[i - 1][2]) / max(0.2, t - pts[i - 1][0])
            by_t[int(t)].append((k, x, y, sp, math.atan2(dy, dx) if dist > 2.0 else None))
        moving_tracks[k] = pts
    seps = []
    stopped_pairs = 0
    stopped_veh_seconds = 0
    abreast_veh_seconds = 0
    for t, vs in by_t.items():
        # headings for stopped cars come from the track's overall direction near the stop
        stopped = [v for v in vs if v[3] < 0.5]
        stopped_veh_seconds += len(stopped)
        grid = defaultdict(list)
        for v in stopped:
            grid[(int(v[1] // 8), int(v[2] // 8))].append(v)
        for v in stopped:
            near = False
            gx, gy = int(v[1] // 8), int(v[2] // 8)
            head = overall_heading(tracks[v[0]], v[1], v[2])
            if head is None:
                continue
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for w in grid[(gx + dx, gy + dy)]:
                        if w[0] <= v[0]:
                            continue
                        hw = overall_heading(tracks[w[0]], w[1], w[2])
                        if hw is None or abs(angdiff(head, hw)) > math.radians(15):
                            continue
                        rx, ry = w[1] - v[1], w[2] - v[2]
                        along = rx * math.cos(head) + ry * math.sin(head)
                        across = -rx * math.sin(head) + ry * math.cos(head)
                        if abs(along) < 3.0 and abs(across) < 6.0:
                            seps.append(abs(across))
                            stopped_pairs += 1
                            near = True
            if near:
                abreast_veh_seconds += 1
    # movements
    movements = defaultdict(list)
    CELL = 25.0
    for k, pts in moving_tracks.items():
        path = sum(math.hypot(pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]) for i in range(1, len(pts)))
        if path < 60:
            continue
        a, b = pts[0], pts[-1]
        movements[(round(a[1] / CELL), round(a[2] / CELL), round(b[1] / CELL), round(b[2] / CELL))].append(pts)
    straight, turning = [], []
    n_straight = n_turning = 0
    for key, group in movements.items():
        if len(group) < 8:
            continue
        res = movement_spread(group)
        if res is None:
            continue
        sd, turn_deg = res
        if turn_deg < 15:
            straight.append(sd)
            n_straight += len(group)
        elif turn_deg > 45:
            turning.append(sd)
            n_turning += len(group)
    return {
        "tracks": len(moving_tracks),
        "stopped_veh_seconds": stopped_veh_seconds,
        "stopped_pairs": stopped_pairs,
        "share_stopped_with_neighbour": abreast_veh_seconds / max(1, stopped_veh_seconds),
        "pair_sep_hist_0p5m": hist(seps, 0.5, 6.0),
        "pair_sep_under_2p5": sum(1 for s in seps if s < 2.5) / max(1, len(seps)),
        "pair_sep_under_1p9": sum(1 for s in seps if s < 1.9) / max(1, len(seps)),
        "pair_sep_median": percentile(seps, 50),
        "straight_movements": len(straight),
        "straight_cars": n_straight,
        "straight_sd_median": percentile(straight, 50),
        "straight_sd_p10_p90": [percentile(straight, 10), percentile(straight, 90)],
        "turning_movements": len(turning),
        "turning_cars": n_turning,
        "turning_sd_median": percentile(turning, 50),
        "turning_sd_p10_p90": [percentile(turning, 10), percentile(turning, 90)],
    }


_heading_memo = {}


def overall_heading(pts, x, y):
    key = (id(pts), round(x), round(y))
    if key not in _heading_memo:
        _heading_memo[key] = _overall_heading(pts, x, y)
    return _heading_memo[key]


def _overall_heading(pts, x, y):
    # Heading of the track's travel between 15 m before and 15 m after this place.
    best = None
    for i, (_t, px, py) in enumerate(pts):
        d = math.hypot(px - x, py - y)
        if best is None or d < best[0]:
            best = (d, i)
    i = best[1]
    a = b = i
    while a > 0 and math.hypot(pts[a][1] - x, pts[a][2] - y) < 15:
        a -= 1
    while b < len(pts) - 1 and math.hypot(pts[b][1] - x, pts[b][2] - y) < 15:
        b += 1
    dx, dy = pts[b][1] - pts[a][1], pts[b][2] - pts[a][2]
    if math.hypot(dx, dy) < 5:
        return None
    return math.atan2(dy, dx)


def resample(pts, n=30):
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + math.hypot(pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]))
    L = d[-1]
    if L < 1:
        return None
    out = []
    j = 0
    for k in range(n):
        s = L * k / (n - 1)
        while j < len(d) - 2 and d[j + 1] < s:
            j += 1
        f = 0 if d[j + 1] == d[j] else (s - d[j]) / (d[j + 1] - d[j])
        out.append((pts[j][1] + f * (pts[j + 1][1] - pts[j][1]), pts[j][2] + f * (pts[j + 1][2] - pts[j][2])))
    return out


def movement_spread(group):
    sampled = [r for r in (resample(p) for p in group) if r]
    if len(sampled) < 8:
        return None
    n = 30
    mean = [(sum(s[i][0] for s in sampled) / len(sampled), sum(s[i][1] for s in sampled) / len(sampled)) for i in range(n)]
    h0 = math.atan2(mean[5][1] - mean[0][1], mean[5][0] - mean[0][0])
    h1 = math.atan2(mean[-1][1] - mean[-6][1], mean[-1][0] - mean[-6][0])
    turn = abs(math.degrees(angdiff(h1, h0)))
    sds = []
    # Ignore the first and last 15%, where the 25 m start and end cells spread tracks.
    for i in range(5, n - 5):
        hx, hy = mean[i + 1][0] - mean[i - 1][0], mean[i + 1][1] - mean[i - 1][1]
        h = math.hypot(hx, hy)
        if h < 1e-6:
            continue
        lat = [-(s[i][0] - mean[i][0]) * hy / h + (s[i][1] - mean[i][1]) * hx / h for s in sampled]
        lat.sort()
        # Robust SD, so another lane's cars in the same cell do not widen it.
        q1 = lat[len(lat) // 4]
        q3 = lat[3 * len(lat) // 4]
        sds.append((q3 - q1) / 1.349)
    if not sds:
        return None
    sds.sort()
    return sds[len(sds) // 2], turn


def percentile(xs, p):
    if not xs:
        return None
    ys = sorted(xs)
    return round(ys[min(len(ys) - 1, int(len(ys) * p / 100))], 3)


def hist(xs, w, top):
    bins = [0] * int(top / w)
    for x in xs:
        i = int(x / w)
        if i < len(bins):
            bins[i] += 1
    return bins


def main():
    result = {}
    for path in sys.argv[1:]:
        for name, rows in read_rows(path):
            tracks, types = tracks_1hz(rows)
            counts = defaultdict(int)
            for k, t in types.items():
                counts[t] += 1
            r = analyse(tracks, types)
            r["types"] = dict(counts)
            result[name] = r
            print(name, json.dumps({k: r[k] for k in ("tracks", "pair_sep_under_1p9", "pair_sep_median", "straight_sd_median", "turning_sd_median")}), file=sys.stderr)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
