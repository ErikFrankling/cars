#!/usr/bin/env python3
"""Sidelink capacity arithmetic for report 12. Usage: v2x_capacity.py sizes.json density.jsonl out.json [fcd.csv ...]

Occupancy is counted in sub-channel slots, the unit CBR is defined on (TS 38.215 5.1.27, TS 103 574 5.2).
Load to CBR is calibrated on Qualcomm's 20 MHz LTE-V2X runs: 19.2/38.4/96% offered load gave CBR 25/48/87%.
"""
import json, math, sys, csv, collections

sz = json.load(open(sys.argv[1]))
dens = [json.loads(l) for l in open(sys.argv[2])]
SEC_DIGEST = 95   # COER of signed data with a digest, by field, see report section 1.7
CERT_EXTRA = 139  # certificate 145 B + 3 list bytes, minus the 9 B digest choice
GN_BTP = 44       # GN SHB 40 (EN 302 636-4-1 table 13) + BTP-B 4
L2 = 12           # SL-SCH 3, MAC sub 3, RLC 1, PDCP 2, CRC 3
PROFILES = {
    "LTE-V2X, MCS 11, 1 retx (fielded)": dict(kind="lte", ntx=2),
    "NR mode 2, 16QAM R.37 (MCS 11), 1 retx": dict(kind="nr", b_per_re=4 * 378 / 1024, ntx=2),
    "NR mode 2, 16QAM R.64 (MCS 16), 1 retx": dict(kind="nr", b_per_re=4 * 658 / 1024, ntx=2),
    "NR mode 2, 64QAM R.55 (MCS 20), no retx": dict(kind="nr", b_per_re=6 * 567 / 1024, ntx=1),
}
NR_PRB = {10: 24, 20: 51, 40: 106}  # TS 38.101-1 table 5.3.2-1, 30 kHz
CALIB = 1.25
CAPS = {"CBR .25 (SAE-style CC, as fielded)": .25, "CBR .30 (TS 103 574, no CR limit)": .30, "CBR .65 (TS 103 574, CR .03 to .02)": .65}


def per_msg(profile, mhz, bytes_air):
    """Fraction of one second of the pool's sub-channel slots used by one message."""
    p = PROFILES[profile]
    if p["kind"] == "lte":
        if mhz == 40:
            return None
        rb_total = {10: 50, 20: 100}[mhz]
        nsub = rb_total // 10
        bits_per_rb = (383 + L2) * 8 / 20  # 383 B payload took 20 RB at MCS 11 (Qualcomm 8.2)
        k = max(1, math.ceil(bytes_air * 8 / bits_per_rb / 10))
        if k > nsub:
            return None
        return k * p["ntx"] / (nsub * 1000)
    prb = NR_PRB[mhz]
    nsub = prb // 10
    re_needed = bytes_air * 8 / p["b_per_re"] + 240 + 40  # PSCCH 2 symbols over 10 PRB, SCI-2
    k = max(1, math.ceil(re_needed / 120 / 10))  # 12 x (14 - AGC - guard - 2 DMRS) = 120 RE per PRB
    if k > nsub:
        return None
    return k * p["ntx"] / (nsub * 2000)


CAM = sz["CAM high-frequency only"]
MSG = {
    "CAM status only": CAM,
    "CAM + 5 s intent, 10 pts": CAM + sz["PathPredictionContainer, 10 points with time: wrapped"],
    "CAM + 8 s intent, 16 pts": CAM + sz["PathPredictionContainer, 16 points with time: wrapped"],
    "CAM + 16 pts with position confidence": CAM + sz["PathPredictionContainer, 16 points with time and position confidence: wrapped"],
    "CAM + 40 pts": CAM + sz["PathPredictionContainer, 40 points with time: wrapped"],
    "TS 22.186 cooperative collision avoidance, 2000 B": 2000,
}


def air(payload, cert=False):
    return payload + SEC_DIGEST + (CERT_EXTRA if cert else 0) + GN_BTP + L2


def domain_budget(profile, mhz, payload, cap):
    """Cars x Hz the pool carries at this CBR. Certificates once a second per car, per TS 103 097 7.1.1."""
    d = per_msg(profile, mhz, air(payload))
    c = per_msg(profile, mhz, air(payload, True))
    if d is None or c is None:
        return None
    usable = cap / CALIB
    return dict(digest_only=usable / d, frac_per_msg=d, frac_cert=c, usable=usable)


def rate_for(profile, mhz, payload, cap, cars):
    b = domain_budget(profile, mhz, payload, cap)
    if not b:
        return None
    # cars*(r*d + 1*(c-d)) = usable when r >= 1
    r = (b["usable"] / cars - (b["frac_cert"] - b["frac_per_msg"])) / b["frac_per_msg"]
    if r >= 1:
        return r
    return b["usable"] / cars / b["frac_cert"]  # every message then carries a certificate


out = {"air_bytes": {k: {"digest": air(v), "with_cert": air(v, True), "payload": v} for k, v in MSG.items()}}
tab = {}
for prof in PROFILES:
    for mhz in (10, 20, 40):
        for capn, cap in CAPS.items():
            for mn, mv in MSG.items():
                row = {}
                b = domain_budget(prof, mhz, mv, cap)
                if b is None:
                    continue
                row["msgs_per_s_digest"] = b["digest_only"]
                row["mbit_s_air"] = b["digest_only"] * air(mv) * 8 / 1e6
                for n in (100, 200, 500, 1000, 2000, 3000):
                    row[f"hz_{n}"] = rate_for(prof, mhz, mv, cap, n)
                tab[f"{prof} | {mhz} MHz | {capn} | {mn}"] = row
out["table"] = tab

# Calibration check against the source's own figures
out["calibration"] = {"offered": [.192, .384, .96], "cbr_measured": [.25, .48, .87],
                      "model": [min(1, CALIB * x) for x in (.192, .384, .96)]}
out["qualcomm_net_mbit"] = {n: n * 10 * 383 * 8 / 1e6 for n in (50, 100, 250)}

out["cars_in_disc"] = {}
for d in dens:
    for R in (300, 500, 800):
        q = d[f"disc_{R}"]
        for occ, v in (("20/lane-km", 20), ("50/lane-km", 50), ("133/lane-km jam", 133)):
            out["cars_in_disc"][f"{d['label']} r={R} {occ}"] = {k: round(q[k] * v) for k in ("p50_lane_km", "p95_lane_km", "p99_lane_km", "max_lane_km")}
    out[f"lane_km_per_km2_{d['label']}"] = d["lane_km_per_km2"]

# CAM rate from the TS 103 900 6.1.2 triggers applied to recorded FCD. Heading is not in the FCD, so this is a lower bound.
rates = {}
for path in sys.argv[4:]:
    rows = collections.defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[r["trip"]].append((float(r["time"]), r["lane"], float(r["pos"]), float(r["speed"])))
    sent = dur = 0
    all_steps = []
    for vid, tr in rows.items():
        tr.sort()
        if len(tr) < 3:
            continue
        dt = tr[1][0] - tr[0][0]
        last_t, last_v, travelled = tr[0][0], tr[0][3], 0
        tgen = 1.0
        n = 1
        burst = 0
        for (t0, l0, p0, v0), (t1, l1, p1, v1) in zip(tr, tr[1:]):
            travelled += (v0 + v1) / 2 * (t1 - t0)
            el = t1 - last_t
            dyn = el >= .0999 and (travelled > 4 or abs(v1 - last_v) > .5)
            per = el >= tgen - 1e-6
            if dyn or per:
                n += 1
                last_t, last_v, travelled = t1, v1, 0
                if dyn:
                    tgen, burst = max(el, .1), 3
                else:
                    burst -= 1
                    if burst <= 0:
                        tgen = 1.0
        sent += n
        dur += tr[-1][0] - tr[0][0]
    rates[path.split("/")[-2]] = {"vehicles": len(rows), "mean_hz_per_vehicle": sent / max(dur, 1), "dt_s": dt}
out["cam_rate_from_fcd"] = rates
json.dump(out, open(sys.argv[3], "w"), indent=1)

print(json.dumps(out["air_bytes"], indent=0))
print(json.dumps(out["cam_rate_from_fcd"], indent=0))
print(json.dumps(out["cars_in_disc"], indent=0)[:2500])
for mhz in (10, 20, 40):
    print("==", mhz)
    for prof in PROFILES:
        for capn in CAPS:
            for mn in ("CAM status only", "CAM + 8 s intent, 16 pts", "CAM + 40 pts"):
                k = f"{prof} | {mhz} MHz | {capn} | {mn}"
                if k in tab:
                    r = tab[k]
                    print(f"{prof[:24]:24s} {capn[:8]} {mn[:16]:16s} msgs/s {r['msgs_per_s_digest']:7.0f} air {r['mbit_s_air']:5.1f} Mb/s  Hz@200 {r['hz_200']:5.2f} @500 {r['hz_500']:5.2f} @1000 {r['hz_1000']:5.2f} @2000 {r['hz_2000']:5.2f}")
