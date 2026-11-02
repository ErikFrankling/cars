#!/usr/bin/env python3
"""Is the signal file independent of the plate reads? How does the month-long virtual loop file compare with reads? Argument: dataset dir."""
import bisect, collections as C, csv, datetime as dt, os, statistics as st, sys
d = sys.argv[1]
def rows(n):
    with open(os.path.join(d, n), newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f): yield {k.strip(): v for k, v in r.items()}
def t(s): return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").timestamp()
T0, T1 = t("2020-09-09 07:00:00.0"), t("2020-09-09 08:00:00.0")
L = [r for r in rows("lpr.csv") if r["vid"] != "dcaf69f4cf4e2e521459b25bf6e7a0d0"]
G = C.defaultdict(list)
for r in rows("signal.csv"): G[r["dir"]].append((t(r["ftime"]), t(r["ttime"])))
for v in G.values(): v.sort()
reads = C.Counter(); tot = 0
hits = C.defaultdict(C.Counter)
for r in L:
    k = r["up_turns"]
    if "#" in k or k not in G: continue
    x = t(r["up_time"]); v = G[k]; i = bisect.bisect_right(v, (x, 1e18)) - 1
    if i >= 0 and v[i][1] >= x: hits[k][i] += 1
empty = n = 0; empt_by = []
act = [k for k, v in G.items() if k in hits and sum(hits[k].values()) >= 20]
for k in act:
    v = G[k]; idx = [i for i, (a, b) in enumerate(v) if a >= T0 and b <= T1 and b - a < 150]
    e = sum(1 for i in idx if hits[k][i] == 0); empty += e; n += len(idx); empt_by.append(e / max(1, len(idx)))
print(f"busy movements {len(act)} intervals {n}: intervals with zero reads {empty/n:.3f}; if derived only from reads this would be near 0")
# cycle regularity per junction
nodes = C.defaultdict(list)
for k, v in G.items(): nodes[k.split('_')[1]].append(v)
cv = []; cyc = []
for k, v in G.items():
    a = [x for x, y in v if T0 <= x <= T1 and y - x < 150]
    if len(a) < 10: continue
    dif = [a[i+1]-a[i] for i in range(len(a)-1)]; m = st.mean(dif); cv.append(st.pstdev(dif)/m); cyc.append(st.median(dif))
cv.sort(); cyc.sort()
print(f"movement cycle stats n={len(cv)} median cycle {st.median(cyc)} p10 {cyc[len(cyc)//10]} p90 {cyc[int(.9*len(cyc))]}; cv of cycle p10,50,90 {cv[len(cv)//10]:.3f} {cv[len(cv)//2]:.3f} {cv[int(.9*len(cv))]:.3f}")
top = C.Counter(c for c in cyc); print("most common cycle s", top.most_common(8))
# virtual loop
days, hour, sp = C.Counter(), C.Counter(), C.defaultdict(lambda: [0.0, 0.0])
linkvis = C.Counter(); ids = set(); rowsn = 0
for r in rows("loop.csv"):
    rowsn += 1; c = int(float(r["COUNT"])); ft = r["FTIME"]; ids.add(r["ROAD_ID"])
    days[ft[:10]] += c; h = ft[11:13]; hour[h] += c
    try:
        hs = float(r["HARM_SPD"])
        if hs > 0: sp[h][0] += c; sp[h][1] += c / hs
    except: pass
    if ft[:13] == "2020-09-09 07": linkvis[r["ROAD_ID"]] += c
print("loop rows", rowsn, "roads", len(ids), "days", len(days), "first/last", min(days), max(days))
print("loop vehicle-passages per day:", [(k[5:], days[k]) for k in sorted(days)][:31])
print("hour totals + harmonic m/s", [(h, hour[h], round(sp[h][0]/sp[h][1], 2) if sp[h][1] else 0) for h in sorted(hour)])
lp = C.Counter(r["up_rd"] for r in L if r["up_time"][:13] == "2020-09-09 07")
com = [(linkvis[k], lp[k]) for k in linkvis if lp[k] >= 50]
rat = sorted(a / b for a, b in com)
print(f"links compared {len(com)}: virtual loop count / plate reads 07-08 on Sep 9: p10 {rat[len(rat)//10]:.2f} median {rat[len(rat)//2]:.2f} p90 {rat[int(.9*len(rat))]:.2f}")
