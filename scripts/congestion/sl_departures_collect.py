#!/usr/bin/env python3
"""Poll SL Transport departures (no key) and log one row per bus call per poll.

Short tests only: SL's API terms forbid building your own transcript of the
data, and Trafiklab asks for GTFS Regional or KoDa (CC0, free key) for volume.
Use koda_fetch.py and koda_segments.py for any real collection.

    python3 -I sl_departures_collect.py --out DIR --minutes 60 --sites 9117,1270
"""
import argparse, csv, json, os, sys, time, urllib.request

API = "https://transport.integration.sl.se/v1/sites/%d/departures?forecast=%d"
UA = "cars-research-probe/0.1"
COLS = ["poll_utc", "site", "line", "direction_code", "destination", "journey", "journey_state",
        "prediction_state", "stop_point", "stop_name", "scheduled", "expected", "state"]


def fetch(site, forecast):
    req = urllib.request.Request(API % (site, forecast), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--sites", required=True, help="comma-separated site ids")
    ap.add_argument("--cycle", type=float, default=60.0, help="seconds per full round of sites")
    ap.add_argument("--forecast", type=int, default=30)
    a = ap.parse_args()
    if a.minutes > 180:
        sys.exit("refusing over 3 h: this feed is for short tests, use KoDa for collection")
    sites = [int(s) for s in a.sites.split(",")]
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, time.strftime("sl_departures_%Y%m%dT%H%M.csv"))
    end = time.time() + a.minutes * 60
    gap = a.cycle / len(sites)
    polls = errors = rows = 0
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        while time.time() < end:
            for s in sites:
                t0 = time.time()
                try:
                    d = fetch(s, a.forecast)
                    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    for x in d.get("departures", []):
                        if x.get("line", {}).get("transport_mode") != "BUS":
                            continue
                        j = x.get("journey", {})
                        sp = x.get("stop_point", {})
                        w.writerow([now, s, x["line"].get("designation"), x.get("direction_code"),
                                    x.get("destination"), j.get("id"), j.get("state"),
                                    j.get("prediction_state"), sp.get("id"), sp.get("name"),
                                    x.get("scheduled"), x.get("expected"), x.get("state")])
                        rows += 1
                    polls += 1
                except Exception as e:
                    errors += 1
                    print("poll failed", s, e, file=sys.stderr)
                    if getattr(e, "code", None) == 429:
                        time.sleep(60)
                time.sleep(max(0.0, gap - (time.time() - t0)))
            f.flush()
    print(json.dumps({"path": path, "polls": polls, "errors": errors, "rows": rows}))


if __name__ == "__main__":
    main()
