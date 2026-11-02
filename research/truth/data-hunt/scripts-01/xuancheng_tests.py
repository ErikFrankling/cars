#!/usr/bin/env python3
"""Cross-test Xuancheng LPR against its signal file, adjacency, and network. Argument: dataset dir."""
import bisect, collections as C, csv, datetime as dt, math, os, random, re, statistics as st, sys
d = sys.argv[1]
def rows(n):
    with open(os.path.join(d, n), newline="", encoding="utf-8", errors="replace") as f:
        yield from csv.DictReader(f)
def t(s): return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").timestamp()
# ---- network
seg = list(rows("road_network_segment_level.csv"))
nodes, xs, ys, L = set(), [], [], 0.0
for r in seg:
    a, b = r["cid"].split("_"); nodes |= {a, b}
    pts = [tuple(map(float, p.split())) for p in re.sub(r"LINESTRING\(|\)", "", r["geom"]).split(";")]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L += math.hypot((x1-x0)*96000, (y1-y0)*111000)
    xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
print(f"network: directed links={len(seg)} nodes={len(nodes)} directed km={L/1000:.0f} bbox lon {min(xs):.3f}..{max(xs):.3f} lat {min(ys):.3f}..{max(ys):.3f} "
      f"~{(max(xs)-min(xs))*96:.1f} x {(max(ys)-min(ys))*111:.1f} km")
print("lane zero share", sum(r['nlane']=='0' for r in seg)/len(seg), "lane counts", C.Counter(r['nlane'] for r in seg).most_common(8))
stream = list(rows("road_network_stream_level.csv"))
print("stream rows", len(stream), "turn mix", C.Counter(r['turn'] for r in stream).most_common(6), "links with lane-turn rows", len({r['cid'] for r in stream}))
adj = {r["cid"]: set(r["dnroad"].split("#")) for r in seg}
# ---- lpr
all_rows = list(rows("lpr.csv"))
cnt = C.Counter(r["vid"] for r in all_rows)
bad = {v for v, n in cnt.items() if n > 200}
print("outlier ids (>200 records/h):", {v: cnt[v] for v in bad})
Lp = [r for r in all_rows if r["vid"] not in bad]
print("records", len(Lp), "vehicles", len({r['vid'] for r in Lp}), "type", C.Counter(r['type'] for r in Lp))
adjok = sum(r["dn_rd"] in adj.get(r["up_rd"], ()) for r in Lp); same = sum(r["dn_rd"] == r["up_rd"] for r in Lp)
print(f"consecutive reads on adjacent links: {adjok/len(Lp):.3f}; same link: {same/len(Lp):.3f}")
cl = sorted(cnt[v] for v in cnt if v not in bad)
print("records per vehicle: median", st.median(cl), "p90", cl[int(.9*len(cl))], "max", cl[-1])
tt = [t(r["dn_time"]) - t(r["up_time"]) for r in Lp]; tt.sort()
print("seconds between consecutive reads: p10,50,90", tt[len(tt)//10], tt[len(tt)//2], tt[int(.9*len(tt))], "negative", sum(x<0 for x in tt))
print("links with reads", len({r['up_rd'] for r in Lp}|{r['dn_rd'] for r in Lp}), "of", len(seg))
# ---- signal
green = C.defaultdict(list)
for r in rows("signal.csv"):
    green[r["dir"]].append((t(r["ftime"]), t(r["ttime"])))
for v in green.values(): v.sort()
g_dur = [b-a for v in green.values() for a, b in v]; g_dur.sort()
print("movements", len(green), "intervals", len(g_dur), "duration s p10,50,90,99", g_dur[len(g_dur)//10], g_dur[len(g_dur)//2], g_dur[int(.9*len(g_dur))], g_dur[int(.99*len(g_dur))])
T0, T1 = t("2020-09-09 07:00:00.0"), t("2020-09-09 08:00:00.0")
print("nodes with signals", len({k.split('_')[1] for k in green}), "of network nodes", len(nodes))
# coverage and cycle per movement
gaps, shares = [], {}
for k, v in green.items():
    a = [max(x, T0) for x, y in v if y > T0 and x < T1]; b = [min(y, T1) for x, y in v if y > T0 and x < T1]
    shares[k] = sum(y-x for x, y in zip(a, b))/3600
    gaps += [a[i+1]-a[i] for i in range(len(a)-1)]
gaps.sort()
print("start-to-start s p10,50,90", gaps[len(gaps)//10], gaps[len(gaps)//2], gaps[int(.9*len(gaps))], "; share of hour in file state: median", st.median(shares.values()), "share ~always", sum(s>.98 for s in shares.values())/len(shares))
def inside(v, x, slack=0):
    i = bisect.bisect_right(v, (x, 1e18)) - 1
    return i >= 0 and v[i][0]-slack <= x <= v[i][1]+slack
# test: does the read at each intersection happen while that movement is listed?
rng = random.Random(1); obs, exp, n, mv = 0, 0.0, 0, 0
per_t = C.Counter(); per_n = C.Counter(); offs = []
samp = C.Counter(); rand_in = 0
for r in Lp:
    k = r["up_turns"]
    for one in k.split("#"):
        if one in green: break
    else:
        continue
    if "#" in k: mv += 1; continue
    x = t(r["up_time"])
    if shares.get(k, 1) > .98: continue
    v = green[k]; n += 1; hit = inside(v, x); obs += hit; exp += shares[k]; rand_in += inside(v, rng.uniform(T0, T1))
    turn = k.split("_")
    if hit:
        i = bisect.bisect_right(v, (x, 1e18)) - 1; offs.append(x - v[i][0])
print(f"single-movement reads tested={n} multi-movement skipped={mv}: inside listed state {obs/n:.3f}; expected if unrelated (time share) {exp/n:.3f}; shuffled time check {rand_in/n:.3f}")
if offs:
    offs.sort(); print("seconds after start of state, for reads inside: p10,50,90", offs[len(offs)//10], offs[len(offs)//2], offs[int(.9*len(offs))])
    h = C.Counter(min(int(o//5)*5, 60) for o in offs); print("histogram 5 s bins:", [h[b] for b in range(0, 65, 5)])
# ---- ring: flow hour by movement vs discharge sanity
flow = C.Counter(r["up_rd"] for r in Lp)
print("top link reads/h", flow.most_common(5))
