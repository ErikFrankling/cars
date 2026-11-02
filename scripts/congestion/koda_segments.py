#!/usr/bin/env python3
"""Bus travel time and speed by hour between gates, from GTFS-RT VehiclePositions files.

    python3 -I koda_segments.py --pb-dir EXTRACTED --gates corridors.csv --out seg.csv

A gate is a point on a road. A bus passes it at its closest GPS sample within
--radius metres, interpolated to the nearest point of the sampled track. A
segment is two consecutive gates of a corridor passed in order by one trip.
Standard library only, so it can run with -I on untrusted archives. A full SL
day is many files: over about 10 minutes of CPU, run it with `heavy`.
"""
import argparse, collections, csv, math, os, statistics, sys, time


def varint(b, i):
    v = s = 0
    while True:
        c = b[i]
        i += 1
        v |= (c & 0x7f) << s
        if c < 0x80:
            return v, i
        s += 7


def fields(b):
    """Yield (field number, wire type, value). Length-delimited values stay bytes."""
    i, n = 0, len(b)
    while i < n:
        tag, i = varint(b, i)
        f, w = tag >> 3, tag & 7
        if w == 0:
            v, i = varint(b, i)
        elif w == 1:
            v, i = b[i:i + 8], i + 8
        elif w == 2:
            l, i = varint(b, i)
            v, i = b[i:i + l], i + l
        elif w == 5:
            v, i = b[i:i + 4], i + 4
        else:
            raise ValueError("wire type %d" % w)
        yield f, w, v


def f32(b):
    import struct
    return struct.unpack("<f", b)[0]


def vehicle_positions(data, bbox):
    """FeedMessage.entity(2).vehicle(4): trip(1).trip_id(1), position(2), timestamp(5), vehicle(8).id(1)."""
    for f, _, ent in fields(data):
        if f != 2:
            continue
        for g, _, veh in fields(ent):
            if g != 4:
                continue
            trip = vid = lat = lon = ts = None
            for h, _, v in fields(veh):
                if h == 1:
                    for k, _, x in fields(v):
                        if k == 1:
                            trip = x.decode("utf-8", "replace")
                elif h == 2:
                    for k, _, x in fields(v):
                        if k == 1:
                            lat = f32(x)
                        elif k == 2:
                            lon = f32(x)
                elif h == 5:
                    ts = v
                elif h == 8:
                    for k, _, x in fields(v):
                        if k == 1:
                            vid = x.decode("utf-8", "replace")
            if None in (trip, lat, lon, ts):
                continue
            if bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]:
                yield trip, vid, ts, lat, lon


def metres(lat0, lon0, lat, lon):
    return ((lon - lon0) * 111320 * math.cos(math.radians(lat0)), (lat - lat0) * 110574)


def crossing(track, gate, radius):
    """Closest approach of a sorted track [(t, lat, lon)] to a gate: (t, distance) or None."""
    best = None
    for (t0, a0, o0), (t1, a1, o1) in zip(track, track[1:]):
        x0, y0 = metres(gate[0], gate[1], a0, o0)
        x1, y1 = metres(gate[0], gate[1], a1, o1)
        dx, dy = x1 - x0, y1 - y0
        l2 = dx * dx + dy * dy
        u = 0.0 if l2 == 0 else min(1.0, max(0.0, -(x0 * dx + y0 * dy) / l2))
        d = math.hypot(x0 + u * dx, y0 + u * dy)
        if d <= radius and (best is None or d < best[1]):
            best = (t0 + u * (t1 - t0), d)
    return best


def read_gates(path):
    out = collections.defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            out[r["corridor"]].append((r["gate"], float(r["lat"]), float(r["lon"])))
    return out


def iter_pb(root):
    for d, _, names in os.walk(root):
        for n in sorted(names):
            if n.endswith(".pb"):
                yield os.path.join(d, n)


def segments(tracks, gates, radius, max_gap):
    """Yield one travel per trip and consecutive gate pair. Long sampling gaps are rejected."""
    for (trip, _), pts in tracks.items():
        pts = sorted(set(pts))
        if len(pts) < 2:
            continue
        for corridor, gs in gates.items():
            passes = [crossing(pts, (g[1], g[2]), radius) for g in gs]
            for i in range(len(gs) - 1):
                a, b = passes[i], passes[i + 1]
                if a and b and b[0] > a[0]:
                    in_seg = [p[0] for p in pts if a[0] <= p[0] <= b[0]]
                    if not in_seg or max(y - x for x, y in zip([a[0]] + in_seg, in_seg + [b[0]])) > max_gap:
                        continue
                    x, y = metres(gs[i][1], gs[i][2], gs[i + 1][1], gs[i + 1][2])
                    yield corridor, gs[i][0], gs[i + 1][0], trip, a[0], b[0] - a[0], math.hypot(x, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pb-dir", required=True)
    ap.add_argument("--gates", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--radius", type=float, default=60.0)
    ap.add_argument("--max-gap", type=float, default=60.0, help="reject segments with a longer GPS gap, s")
    ap.add_argument("--tz", default="Europe/Stockholm")
    a = ap.parse_args()
    os.environ["TZ"] = a.tz
    time.tzset()
    gates = read_gates(a.gates)
    allg = [g for gs in gates.values() for g in gs]
    m = 0.01
    bbox = (min(g[1] for g in allg) - m, min(g[2] for g in allg) - m,
            max(g[1] for g in allg) + m, max(g[2] for g in allg) + m)
    tracks = collections.defaultdict(list)
    files = 0
    for p in iter_pb(a.pb_dir):
        with open(p, "rb") as f:
            data = f.read()
        files += 1
        for trip, vid, ts, lat, lon in vehicle_positions(data, bbox):
            tracks[(trip, vid)].append((ts, lat, lon))
    hours = collections.defaultdict(list)
    for corridor, g0, g1, trip, t0, dt, dist in segments(tracks, gates, a.radius, a.max_gap):
        lt = time.localtime(t0)
        hours[(corridor, g0, g1, time.strftime("%Y-%m-%d", lt), lt.tm_hour, round(dist))].append(dt)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["corridor", "from_gate", "to_gate", "date", "hour", "crow_m", "n", "median_s", "p15_s", "p85_s", "median_kmh"])
        for k in sorted(hours):
            v = sorted(hours[k])
            q = lambda p: v[min(len(v) - 1, int(p * len(v)))]
            med = statistics.median(v)
            w.writerow(list(k) + [len(v), round(med, 1), round(q(.15), 1), round(q(.85), 1), round(k[5] / med * 3.6, 1)])
    print(f"{files} files, {len(tracks)} tracks, {sum(map(len, hours.values()))} segment passes", file=sys.stderr)


if __name__ == "__main__":
    main()
