#!/usr/bin/env python3
"""Build directed corridor gates from a SUMO net, so measured and simulated roads match.

    python3 -I make_corridors.py NET.xml corridors.csv corridors_edges.csv

Writes gates about every --spacing metres along each named road, both directions,
and one summary row per direction with the share of length on edges that have a
bus-only lane in the net. Urban names are limited to the inner city, since
the same street names recur in the suburbs.
"""
import argparse, collections, csv, math, re, sys

CORRIDORS = {
    "essingeleden": ("motorway", ["Essingeleden"]),
    "sodra-lanken": ("motorway", ["Södra länken"]),
    "norra-lanken": ("motorway", ["Norra länken"]),
    "nynasvagen": ("motorway", ["Nynäsvägen"]),
    "varmdoleden": ("motorway", ["Värmdöleden"]),
    "roslagsvagen": ("arterial", ["Roslagsvägen", "Norrtäljevägen"]),
    "uppsalavagen": ("motorway", ["Uppsalavägen"]),
    "sodertaljevagen": ("motorway", ["Södertäljevägen"]),
    "drottningholmsvagen": ("arterial", ["Drottningholmsvägen"]),
    "vasterbron": ("arterial", ["Västerbron"]),
    "centralbron": ("motorway", ["Centralbron"]),
    "hornsgatan": ("urban", ["Hornsgatan"]),
    "ringvagen": ("urban", ["Ringvägen"]),
    "gotgatan": ("urban", ["Götgatan"]),
    "folkungagatan": ("urban", ["Folkungagatan"]),
    "sveavagen": ("urban", ["Sveavägen"]),
    "birger-jarlsgatan": ("urban", ["Birger Jarlsgatan"]),
    "valhallavagen": ("urban", ["Valhallavägen"]),
    "odengatan": ("urban", ["Odengatan"]),
    "sankt-eriksgatan": ("urban", ["Sankt Eriksgatan"]),
    "hantverkargatan": ("urban", ["Hantverkargatan"]),
    "lidingovagen": ("urban", ["Lidingövägen"]),
    "klarastrandsleden": ("arterial", ["Klarastrandsleden"]),
    "johanneshovsbron": ("arterial", ["Johanneshovsbron", "Skanstullsbron"]),
}

EDGE = re.compile(r'<edge id="([^"]+)"([^>]*)>')
ATTR = re.compile(r'(\w+)="([^"]*)"')
LANE = re.compile(r'<lane ([^>]*)/?>')


def utm33_to_wgs(e, n):
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    b2 = f * (2 - f)
    e1 = (1 - math.sqrt(1 - b2)) / (1 + math.sqrt(1 - b2))
    x, m = e - 500000.0, n / k0
    mu = m / (a * (1 - b2 / 4 - 3 * b2 ** 2 / 64 - 5 * b2 ** 3 / 256))
    p = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
         + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    ep2 = b2 / (1 - b2)
    c1, t1 = ep2 * math.cos(p) ** 2, math.tan(p) ** 2
    nu = a / math.sqrt(1 - b2 * math.sin(p) ** 2)
    r1 = a * (1 - b2) / (1 - b2 * math.sin(p) ** 2) ** 1.5
    d = x / (nu * k0)
    lat = p - (nu * math.tan(p) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                         + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(p)
    return math.degrees(lat), 15.0 + math.degrees(lon)


def bus_only(lane):
    allow = lane.get("allow", "").split()
    if allow:
        return "bus" in allow and "passenger" not in allow
    deny = lane.get("disallow", "").split()
    return "passenger" in deny and "bus" not in deny


def inner(lat, lon):
    return 59.300 <= lat <= 59.362 and 17.98 <= lon <= 18.125


def parse(net, wanted):
    ox = oy = None
    out = collections.defaultdict(list)
    cur = None
    with open(net, encoding="utf-8") as f:
        for line in f:
            s = line.lstrip()
            if s.startswith("<location") and ox is None:
                ox, oy = [float(v) for v in dict(ATTR.findall(s))["netOffset"].split(",")]
            elif s.startswith("<edge "):
                m = EDGE.match(s)
                a = dict(ATTR.findall(m.group(2))) if m else {}
                cur = None
                if m and a.get("function") is None and a.get("name", "").casefold() in wanted:
                    cur = {"id": m.group(1), "name": a["name"], "lanes": [], "shape": a.get("shape")}
                    out[a["name"].casefold()].append(cur)
            elif s.startswith("<lane ") and cur is not None:
                cur["lanes"].append(dict(ATTR.findall(s)))
    return (ox, oy), out


def points(edge):
    shape = edge["shape"] or edge["lanes"][0]["shape"]
    return [tuple(float(v) for v in p.split(",")[:2]) for p in shape.split()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("net")
    ap.add_argument("gates_csv")
    ap.add_argument("edges_csv")
    ap.add_argument("--spacing", type=float, default=1000.0)
    ap.add_argument("--min-length", type=float, default=600.0)
    a = ap.parse_args()
    wanted = {n.casefold() for _, ns in CORRIDORS.values() for n in ns}
    (ox, oy), by_name = parse(a.net, wanted)
    with open(a.gates_csv, "w", newline="") as gf, open(a.edges_csv, "w", newline="") as ef:
        g = csv.writer(gf)
        e = csv.writer(ef)
        g.writerow(["corridor", "gate", "lat", "lon", "class"])
        e.writerow(["corridor", "class", "edges", "length_m", "bus_lane_length_share", "mean_lanes", "start_lat", "start_lon", "end_lat", "end_lon"])
        for name, (cls, roads) in CORRIDORS.items():
            edges = [x for r in roads for x in by_name.get(r.casefold(), []) if x["lanes"]]
            if cls == "urban":
                edges = [x for x in edges if all(inner(*utm33_to_wgs(p[0] - ox, p[1] - oy)) for p in points(x))]
            if not edges:
                print("no edges for", name, file=sys.stderr)
                continue
            mids = [p for x in edges for p in points(x)]
            mx, my = sum(p[0] for p in mids) / len(mids), sum(p[1] for p in mids) / len(mids)
            sxx = sum((p[0] - mx) ** 2 for p in mids)
            syy = sum((p[1] - my) ** 2 for p in mids)
            sxy = sum((p[0] - mx) * (p[1] - my) for p in mids)
            th = 0.5 * math.atan2(2 * sxy, sxx - syy)
            ax = (math.cos(th), math.sin(th))
            proj = lambda p: (p[0] - mx) * ax[0] + (p[1] - my) * ax[1]
            for sign, tag in ((1, "a"), (-1, "b")):
                dirn = []
                for x in edges:
                    pts = points(x)
                    if (proj(pts[-1]) - proj(pts[0])) * sign > 0:
                        dirn.append((proj(pts[0]) * sign, x, pts))
                dirn.sort(key=lambda t: t[0])
                if not dirn:
                    continue
                length = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for _, _, pts in dirn for p, q in zip(pts, pts[1:]))
                lanes = sum(sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:])) * len(x["lanes"])
                            for _, x, pts in dirn)
                bus = sum(sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))
                          for _, x, pts in dirn if any(bus_only(ln) for ln in x["lanes"]))
                track = [p for _, _, pts in dirn for p in pts]
                if max(proj(p) for p in track) - min(proj(p) for p in track) < a.min_length or length < a.min_length:
                    continue
                track.sort(key=lambda p: proj(p) * sign)
                cid = f"{name}-{tag}"
                last = None
                n = 0
                sel = []
                for p in track:
                    if last is None or (proj(p) - last) * sign >= a.spacing:
                        sel.append(p)
                        last = proj(p)
                if (proj(track[-1]) - proj(sel[-1])) * sign > a.spacing / 3:
                    sel.append(track[-1])
                for p in sel:
                    la, lo = utm33_to_wgs(p[0] - ox, p[1] - oy)
                    g.writerow([cid, f"g{n:02d}", round(la, 6), round(lo, 6), cls])
                    n += 1
                s, t = utm33_to_wgs(track[0][0] - ox, track[0][1] - oy), utm33_to_wgs(track[-1][0] - ox, track[-1][1] - oy)
                e.writerow([cid, cls, len(dirn), round(length), round(bus / length, 3), round(lanes / length, 2),
                            round(s[0], 6), round(s[1], 6), round(t[0], 6), round(t[1], 6)])


if __name__ == "__main__":
    main()
