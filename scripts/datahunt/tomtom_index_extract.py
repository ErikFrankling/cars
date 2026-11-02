#!/usr/bin/env python3
"""Extract TomTom Traffic Index city data from saved or freshly fetched public city pages.

Usage: tomtom_index_extract.py list PAGE.html > cities.json
       tomtom_index_extract.py one PAGE.html key > row.json
Page data is embedded as Astro island props: [0, x] is a scalar or object, [1, [...]] a list.
"""
import html
import json
import re
import sys

PROP = re.compile(r'props="([^"]*)"')


def de(x):
    if isinstance(x, list) and len(x) == 2 and x[0] in (0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11):
        return de(x[1])
    if isinstance(x, list):
        return [de(i) for i in x]
    if isinstance(x, dict):
        return {k: de(v) for k, v in x.items()}
    return x


def islands(path):
    s = open(path, encoding="utf8").read()
    for m in PROP.finditer(s):
        raw = m.group(1)
        if '&quot;traffic&quot;' in raw or '&quot;population&quot;' in raw:
            try:
                yield de(json.loads(html.unescape(raw)))
            except json.JSONDecodeError:
                continue


def find_key(o, key, depth=0):
    if depth > 14:
        return None
    if isinstance(o, dict):
        if key in o:
            return o[key]
        for v in o.values():
            r = find_key(v, key, depth + 1)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find_key(v, key, depth + 1)
            if r is not None:
                return r
    return None


def find_traffic(path):
    for isl in islands(path):
        t = find_key(isl, "traffic")
        if isinstance(t, dict) and "metro" in t:
            return t
    return None


def cities(path):
    best = {}
    s = html.unescape(open(path, encoding="utf8").read())
    for m in re.finditer(
        r'\{"key":\[0,"([^"]+)"\],"name":\[0,"([^"]+)"\],"country":\[0,"([^"]*)"\].{0,120}?"continent":\[0,"([^"]*)"\].{0,80}?"population":\[0,([0-9]+)\]',
        s,
    ):
        best[m.group(1)] = {
            "key": m.group(1),
            "name": m.group(2),
            "country": m.group(3),
            "continent": m.group(4),
            "population": int(m.group(5)),
        }
    return list(best.values())


DAYS = ("TUESDAY", "WEDNESDAY", "THURSDAY")


def hourly(week):
    table = {h: {"v": [], "fv": [], "c": []} for h in range(24)}
    weekend = {h: [] for h in range(24)}
    for e in week:
        day, h = e["time"].split("-")
        h = int(h)
        if day in DAYS:
            table[h]["v"].append(e["v"])
            table[h]["fv"].append(e["fv"])
            table[h]["c"].append(e["c"])
        elif day in ("SATURDAY", "SUNDAY"):
            weekend[h].append(e["v"])
    mean = lambda a: sum(a) / len(a) if a else None
    return (
        [mean(table[h]["v"]) for h in range(24)],
        [mean(table[h]["fv"]) for h in range(24)],
        [mean(table[h]["c"]) for h in range(24)],
        [mean(weekend[h]) for h in range(24)],
    )


def summarise(block):
    out = {}
    a = block["all"]
    out["base_v"] = a["base"]["v"]
    out["base_fv"] = a["base"]["fv"]
    out["base_c"] = a["base"]["c"]
    out["base_km"] = a["base"].get("s")
    for p in ("am", "pm", "ampm"):
        if p in a:
            out[p + "_v"] = a[p]["v"]
            out[p + "_c"] = a[p]["c"]
            if "time" in a[p]:
                out[p + "_hour"] = a[p]["time"]
            out[p + "_km"] = a[p].get("s")
    if a.get("weekHour"):
        v, fv, c, we = hourly(a["weekHour"])
        out["tue_thu_v"] = v
        out["tue_thu_fv"] = fv
        out["tue_thu_c"] = c
        out["weekend_v"] = we
        night = sum(v[h] for h in (2, 3, 4)) / 3
        mid = sum(v[h] for h in (10, 11, 12, 13, 14)) / 5
        wam = min(v[6:10])
        wpm = min(v[15:19])
        out["night_v"] = night
        out["midday_v"] = mid
        out["worst_am_v"] = wam
        out["worst_pm_v"] = wpm
        out["worst_over_night"] = min(wam, wpm) / night
        out["worst_over_midday"] = min(wam, wpm) / mid
        out["hours_c_over_30"] = sum(1 for x in c if x > 30)
        out["hours_c_over_50"] = sum(1 for x in c if x > 50)
    for cls in ("highways", "nonHighways"):
        if cls in block:
            b = block[cls]
            out[cls] = {
                "v": b["base"]["v"],
                "fv": b["base"]["fv"],
                "c": b["base"]["c"],
                "km": b["base"].get("s"),
                "am_v": b["am"]["v"] if "am" in b else None,
                "pm_v": b["pm"]["v"] if "pm" in b else None,
                "ampm_v": b["ampm"]["v"] if "ampm" in b else None,
            }
    return out


def one(path, key):
    t = find_traffic(path)
    if t is None:
        return {"key": key, "error": "no traffic"}
    row = {"key": key}
    for area in ("metro", "center"):
        if area in t:
            row[area] = summarise(t[area])
    return row


if __name__ == "__main__":
    if sys.argv[1] == "list":
        print(json.dumps(cities(sys.argv[2])))
    else:
        print(json.dumps(one(sys.argv[2], sys.argv[3])))
