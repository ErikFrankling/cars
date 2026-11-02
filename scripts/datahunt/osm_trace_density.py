"""Counts public OSM GPS points per 0.1-degree tile by bisecting the 5000-point pages of the trackpoints API."""
import csv, sys, time, urllib.request
UA = "cars-research-probe/0.1 (read-only density check)"
def count(b, page):
    url = f"https://api.openstreetmap.org/api/0.6/trackpoints?bbox={b[0]:.2f},{b[1]:.2f},{b[2]:.2f},{b[3]:.2f}&page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            time.sleep(1.0)
            return data.count(b"<trkpt")
        except Exception as e:
            err = e; time.sleep(5)
    print("ERR", url, err, file=sys.stderr); return -1
def total(b):
    n = count(b, 0)
    if n < 5000: return n
    lo, hi = 0, 1
    while True:
        n = count(b, hi)
        if 0 <= n < 5000: break
        lo, hi = hi, hi * 2
        if hi > 8192: return -1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if 0 <= count(b, m) < 5000: hi = m
        else: lo = m
    return hi * 5000 + count(b, hi)
out = csv.writer(open(sys.argv[1], "w", newline="")); out.writerow("left bottom right top points".split())
L, B, R, T = map(float, sys.argv[2:6])
x = L
while x < R - 1e-6:
    y = B
    while y < T - 1e-6:
        b = (x, y, x + .1, y + .1); n = total(b); print(b, n, flush=True); out.writerow([*map(lambda v: round(v, 2), b), n])
        y += .1
    x += .1
