"""Downloads pages of public OSM GPS points for one bbox, at most one request per second."""
import sys, time, urllib.request, pathlib
UA = "cars-research-probe/0.1 (read-only sample)"
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
L, B, R, T = sys.argv[2:6]; first, last = int(sys.argv[6]), int(sys.argv[7])
for p in range(first, last):
    f = out / f"p{p:05d}.gpx"
    if f.exists(): continue
    url = f"https://api.openstreetmap.org/api/0.6/trackpoints?bbox={L},{B},{R},{T}&page={p}"
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
                d = r.read()
            f.write_bytes(d); break
        except Exception as e:
            print("retry", p, e, flush=True); time.sleep(20)
    else:
        print("giving up at", p, flush=True); break
    n = d.count(b"<trkpt"); print(p, n, flush=True)
    if n < 5000: break
    time.sleep(1.0)
