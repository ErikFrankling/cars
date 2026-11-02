#!/usr/bin/env python3
"""Stop-to-stop bus times from a sl_departures_collect.py log.

    python3 -I sl_departures_segments.py LOG.csv STOP_POINTS.json OUT.csv

Takes the last value seen of `expected` for each journey at each stop point. It keeps
a call only if the bus was being tracked (a *PROGRESS state) and the last poll was
within the settle time (argument 4, default 120 s), since other values are timetable or stale
predictions. Then it pairs consecutive stops of a journey and reports actual and
scheduled time by hour. Distance is straight line between stop points, so speeds are
lower bounds.
"""
import collections, csv, datetime as dt, json, math, statistics, sys


def main():
    log, stops, out = sys.argv[1:4]
    settle = float(sys.argv[4]) if len(sys.argv) > 4 else 120.0
    tracked = {"NORMALPROGRESS", "FASTPROGRESS", "SLOWPROGRESS", "NOPROGRESS"}
    pos = {s["id"]: (s["lat"], s["lon"], s.get("name", "")) for s in json.load(open(stops))}
    last = {}
    with open(log) as f:
        for r in csv.DictReader(f):
            if r["expected"] and r["journey"] and r["stop_point"]:
                last[(r["journey"], r["line"], int(r["stop_point"]))] = r
    journeys = collections.defaultdict(list)
    dropped = 0
    for (j, line, sp), r in last.items():
        seen = dt.datetime.fromisoformat(r["poll_utc"].replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        if r["journey_state"] not in tracked or abs((dt.datetime.fromisoformat(r["expected"]) - seen).total_seconds()) > settle:
            dropped += 1
            continue
        journeys[(j, line, r["direction_code"])].append((dt.datetime.fromisoformat(r["expected"]), dt.datetime.fromisoformat(r["scheduled"]), sp, r["journey_state"], r["state"]))
    rows = collections.defaultdict(list)
    for (j, line, d), calls in journeys.items():
        calls.sort()
        for a, b in zip(calls, calls[1:]):
            actual = (b[0] - a[0]).total_seconds()
            sched = (b[1] - a[1]).total_seconds()
            if actual <= 0 or a[2] not in pos or b[2] not in pos:
                continue
            la0, lo0, n0 = pos[a[2]]
            la1, lo1, n1 = pos[b[2]]
            m = math.hypot((lo1 - lo0) * 111320 * math.cos(math.radians(la0)), (la1 - la0) * 110574)
            rows[(line, d, n0, n1, a[0].hour, round(m))].append((actual, sched))
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "direction", "from_stop", "to_stop", "hour", "crow_m", "n", "median_actual_s", "median_sched_s", "crow_kmh_actual"])
        for k in sorted(rows):
            a = statistics.median(x[0] for x in rows[k])
            s = statistics.median(x[1] for x in rows[k])
            w.writerow(list(k) + [len(rows[k]), round(a), round(s), round(k[5] / a * 3.6, 1)])
    print(len(last), "calls seen;", dropped, "dropped as unsettled;", len(journeys), "journeys;", sum(map(len, rows.values())), "stop pairs;", len(rows), "rows", file=sys.stderr)


if __name__ == "__main__":
    main()
