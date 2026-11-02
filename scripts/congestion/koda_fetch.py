#!/usr/bin/env python3
"""Download KoDa daily archives (CC0, needs a free Trafiklab key in TRAFIKLAB_KEY).

    TRAFIKLAB_KEY=... python3 -I koda_fetch.py --out DIR --dates 2025-10-07,2025-10-08
    TRAFIKLAB_KEY=... python3 -I koda_fetch.py --out DIR --dates 2025-10-07 --feed static

Sequential on purpose: Trafiklab asks for at most 2 or 3 files at once. HTTP 202
means the archive is being built, which takes 1 to 60 minutes; poll every 30 s.
"""
import argparse, os, sys, time, urllib.error, urllib.request

BASE = "https://api.koda.trafiklab.se/KoDa/api/v2"


def fetch(url, path, max_wait):
    t0 = time.time()
    while True:
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                if r.status == 202:
                    raise urllib.error.HTTPError(url, 202, "building", r.headers, None)
                tmp = path + ".part"
                with open(tmp, "wb") as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
                os.replace(tmp, path)
                return os.path.getsize(path)
        except urllib.error.HTTPError as e:
            if e.code != 202:
                raise RuntimeError("HTTP %d" % e.code) from None
        if time.time() - t0 > max_wait:
            raise TimeoutError("archive not ready after %d s" % max_wait)
        time.sleep(30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dates", required=True)
    ap.add_argument("--operator", default="sl")
    ap.add_argument("--feed", default="VehiclePositions",
                    help="VehiclePositions, TripUpdates, ServiceAlerts or static")
    ap.add_argument("--max-wait", type=int, default=3900)
    a = ap.parse_args()
    key = os.environ.get("TRAFIKLAB_KEY")
    if not key:
        sys.exit("set TRAFIKLAB_KEY")
    os.makedirs(a.out, exist_ok=True)
    for date in a.dates.split(","):
        if a.feed == "static":
            url = f"{BASE}/gtfs-static/{a.operator}?date={date}&key={key}"
            name = f"{a.operator}-static-{date}.zip"
        else:
            url = f"{BASE}/gtfs-rt/{a.operator}/{a.feed}?date={date}&key={key}"
            name = f"{a.operator}-{a.feed}-{date}.7z"
        path = os.path.join(a.out, name)
        if os.path.exists(path):
            print("have", name)
            continue
        print(name, fetch(url, path, a.max_wait), "bytes", flush=True)


if __name__ == "__main__":
    main()
