#!/usr/bin/env python3
"""Stockholm inputs for the assignment loop, on one net: OD repaired from the old route file, measured Arstrafik
counts matched to edges, with the frozen hold-out sites marked as test and never fitted.

usage: assign_stockholm_inputs.py NET OLD_NET OLD_ROUTES ARSTRAFIK HOLDOUT_CSV OUT_DIR"""
import collections, csv, gzip, hashlib, json, math, re, sys
import xml.etree.ElementTree as ET
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

NET, OLD_NET, OLD_ROUTES, ARSTRAFIK, HOLDOUT, OUT = sys.argv[1:7]
FIT_YEARS = ("2023", "2024")
HELD_YEAR = "2025"
MIN_DAYS = 5
PEAK = (15, 18)


def read_net(path):
    """Passenger edges: midpoint, shape, name. The XML is big, so edges are read as they pass."""
    edges = {}
    loc = None
    for ev, el in ET.iterparse(path, events=("end",)):
        if el.tag == "location":
            loc = dict(el.attrib)
        elif el.tag == "edge":
            if el.get("function") is None:
                lanes = el.findall("lane")
                ok = [l for l in lanes if "passenger" in (l.get("allow") or "passenger") and "passenger" not in (l.get("disallow") or "")]
                if ok:
                    shape = np.array([[float(v) for v in p.split(",")[:2]] for p in ok[0].get("shape").split()])
                    edges[el.get("id")] = {"shape": shape, "name": el.get("name") or "", "mid": shape[len(shape) // 2], "len": float(ok[0].get("length")), "lanes": len(ok)}
            el.clear()
        elif el.tag in ("connection", "junction", "tlLogic", "roundabout"):
            el.clear()
    return edges, loc


def write_travellers(new, old, out):
    ids = list(new)
    tree = cKDTree(np.array([new[e]["mid"] for e in ids]))
    way = collections.defaultdict(list)
    for e in ids:
        way[e.split("#")[0]].append(e)
    stats = collections.Counter()
    cache = {}

    def repair(e):
        if e in cache:
            return cache[e]
        if e in new:
            stats["same_edge"] += 1
            cache[e] = e
            return e
        if e not in old:
            stats["lost"] += 1
            cache[e] = None
            return None
        p = old[e]["mid"]
        c = way.get(e.split("#")[0])
        if c:
            stats["same_way"] += 1
            cache[e] = min(c, key=lambda x: float(np.hypot(*(new[x]["mid"] - p))))
        else:
            stats["nearest"] += 1
            cache[e] = ids[tree.query(p)[1]]
        return cache[e]

    routes = {}
    rx_r = re.compile(r'<route id="([^"]+)" edges="([^"]*)"')
    rx_v = re.compile(r'<vehicle id="([^"]+)"[^>]*depart="([^"]+)"[^>]*route="([^"]+)"')
    n = kept = same_od = 0
    with gzip.open(OLD_ROUTES, "rt") as f, gzip.open(out, "wt") as w:
        wr = csv.writer(w)
        wr.writerow("id,class,o_edge,d_edge,desired_arrival_s,depart_s,earliest_s,latest_s,tour,tour_seq,vtype".split(","))
        for line in f:
            if line.startswith("<route "):
                m = rx_r.match(line)
                es = m[2].split()
                routes[m[1]] = (es[0], es[-1])
            elif line.startswith("<vehicle"):
                m = rx_v.match(line)
                n += 1
                o, d = routes[m[3]]
                a, b = repair(o), repair(d)
                if a is None or b is None:
                    continue
                if a == b:
                    same_od += 1
                    continue
                dep = float(m[2])
                wr.writerow([kept, 0, a, b, "nan", dep, max(0.0, dep - 3600), dep + 900, kept, 0, "passenger"])
                kept += 1
    return {"vehicles": n, "written": kept, "dropped_same_od": same_od, "edge_repair": dict(stats)}


def features(path):
    text = open(path, encoding="utf-8").read()
    dec = json.JSONDecoder()
    i = text.index('"features":[') + len('"features":[')
    while text[i] != "]":
        f, i = dec.raw_decode(text, i)
        yield f
        if text[i] == ",":
            i += 1


def bearing_vec(coords_xy):
    v = np.zeros(2)
    for seg in coords_xy:
        v += seg[-1] - seg[0]
    return v / max(np.hypot(*v), 1e-9)


def main():
    new, loc = read_net(NET)
    print("net passenger edges", len(new), loc)
    old, _ = read_net(OLD_NET)
    print("old edges", len(old))
    trav = write_travellers(new, old, f"{OUT}/travellers.csv.gz")
    print(trav)
    del old
    offset = [float(v) for v in loc["netOffset"].split(",")]
    proj = Transformer.from_crs("EPSG:4326", loc["projParameter"], always_xy=True)
    roles = {r["site"]: r for r in csv.DictReader(open(HOLDOUT, encoding="utf-8"))}
    ids = list(new)
    tree = cKDTree(np.array([new[e]["mid"] for e in ids]))
    # By direction and year: record lists.
    recs = collections.defaultdict(list)
    seen = collections.Counter()
    for f in features(ARSTRAFIK):
        p = f["properties"]
        year = str(p.get("datum_för_slut_av_perioden") or "")[:4]
        site = p.get("mätplats")
        if year not in FIT_YEARS + (HELD_YEAR,) or site not in roles or f["geometry"] is None:
            continue
        seen["records"] += 1
        if p.get("metod_för_datainsamling") != "Uppmätt":
            seen["not_measured"] += 1
            continue
        if (p.get("antal_mätdygn") or 0) < MIN_DAYS:
            seen["under_min_days"] += 1
            continue
        if str(p.get("riktningsuppdelad")) != "true":
            seen["not_direction_split"] += 1
            continue
        hours = []
        for h in range(24):
            hours.append(p.get(f"trafikflöde_{h:02d}-{h + 1:02d}__fordon_dygn__alla_fordon"))
        if any(v is None for v in hours):
            seen["missing_hours"] += 1
            continue
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        segs = []
        for ln in lines:
            a = np.array([c[:2] for c in ln])
            x, y = proj.transform(a[:, 0], a[:, 1])
            segs.append(np.column_stack([x + offset[0], y + offset[1]]))
        rec = dict(site=site, year=year, days=p.get("antal_mätdygn") or 0, dir=p.get("riktning"), desc=p.get("riktningsbeskrivning") or "", name=(p.get("namn") or "").split(" 20")[0], hours=hours, segs=segs)
        recs[(site, p.get("riktning"), p.get("riktningsbeskrivning") or "")].append(rec)
    print(dict(seen), "site directions", len(recs))
    norm = lambda s: re.sub(r"[^a-z0-9åäö]", "", s.lower())
    rows = []
    match_stats = collections.Counter()
    match_log = []
    two_year = []
    for (site, dirn, desc), rr in recs.items():
        r0 = rr[0]
        sign = -1.0 if dirn == "Mot" else 1.0
        b = bearing_vec(r0["segs"]) * sign
        centre = np.concatenate(r0["segs"]).mean(axis=0)
        cand = tree.query_ball_point(centre, 60.0)
        best, score_best = None, -1e9
        for i in cand:
            e = new[ids[i]]
            d = e["shape"][-1] - e["shape"][0]
            dn = np.hypot(*d)
            if dn < 1:
                continue
            cosang = float((d / dn) @ b)
            if cosang < 0.7:
                continue
            dist = float(np.min(np.hypot(*(e["shape"] - centre).T)))
            same = norm(e["name"]) and (norm(e["name"]) in norm(r0["name"]) or norm(r0["name"]) in norm(e["name"]))
            score = (100 if same else 0) + 20 * cosang - dist + min(e["len"], 100) * 0.05
            if score > score_best:
                best, score_best = ids[i], score
        if best is None:
            match_stats["no_edge_in_direction"] += 1
            continue
        same_name = bool(norm(new[best]["name"]) and (norm(new[best]["name"]) in norm(r0["name"]) or norm(r0["name"]) in norm(new[best]["name"])))
        match_stats["name_match" if same_name else "name_differs"] += 1
        if not same_name:
            # A flow on the wrong road is worse than no flow: without a name match only busy roads are unambiguous.
            continue
        role_site = roles[site]["role"]
        cell = roles[site]["cell"]
        fit = [x for x in rr if x["year"] in FIT_YEARS]
        held = [x for x in rr if x["year"] == HELD_YEAR]
        h = int(hashlib.sha256(("assign-v1" + cell).encode()).hexdigest(), 16)
        tag = f"{site}:{dirn}:{hashlib.sha1(desc.encode()).hexdigest()[:6]}"
        corridor = norm(r0["name"]) or cell
        match_log.append((tag, best, r0["name"], new[best]["name"], role_site, cell))
        if fit:
            w = np.array([max(x["days"], 1) for x in fit], float)
            mean = sum(np.array(x["hours"], float) * d for x, d in zip(fit, w)) / w.sum()
            by_year = {x["year"]: np.array(x["hours"], float) for x in fit}
            if len(by_year) == 2 and role_site == "calibrate":
                two_year.append((by_year["2023"], by_year["2024"]))
            if role_site == "holdout_space":
                base = "test"
            else:
                base = "selection" if h % 4 == 0 else "train"
            peak_held = base == "train" and int(hashlib.sha256(("peak" + tag).encode()).hexdigest(), 16) % 4 == 0
            for hour in range(24):
                role = "held_peak" if (peak_held and PEAK[0] <= hour < PEAK[1]) else base
                rows.append((tag, best, "measured", hour * 3600, (hour + 1) * 3600, "weekday", f"{mean[hour]:.1f}", "all", "measured", role, corridor))
        for x in held:
            w_tag = tag + "@2025"
            for hour in range(24):
                rows.append((w_tag, best, "measured", hour * 3600, (hour + 1) * 3600, "weekday", f"{x['hours'][hour]:.1f}", "all", "measured", "test_other", corridor))
    print(dict(match_stats))
    with open(f"{OUT}/counts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow("site,edge,dir,t0_s,t1_s,day_type,vehicles,class,source,role,corridor".split(","))
        w.writerows(rows)
    with open(f"{OUT}/site_matches.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["site", "edge", "site_name", "edge_name", "role", "cell"])
        w.writerows(match_log)
    role_counts = collections.Counter(r[9] for r in rows)
    sites = collections.defaultdict(set)
    for r in rows:
        sites[r[9]].add(r[0])
    # Noise floor from the data itself: the same calibration site, 2023 against 2024, hourly. Annual means, so a lower bound.
    if two_year:
        a = np.array([x[0] for x in two_year]).ravel()
        b = np.array([x[1] for x in two_year]).ravel()
        floor = float(np.abs(a - b).sum() / b.sum())
    else:
        floor = None
    report = dict(travellers=trav, records=dict(seen), match=dict(match_stats), rows=dict(role_counts), sites={k: len(v) for k, v in sites.items()},
                  year_to_year_wape=floor, year_to_year_pairs=len(two_year),
                  note="Floor is 2023 against 2024 at calibration sites, on annual weekday means. Stockholm has no dated days, so true day-to-day noise is not measured here; Berlin lane-hour median difference is 8.7%.")
    json.dump(report, open(f"{OUT}/inputs.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))


main()
