#!/usr/bin/env python3
"""Stockholm per-lane curvature, turn-speed and rough grade statistics for research/truth/11-vehicle-physics.md.

Usage: physics_stockholm.py NET_XML OSM_XML TILE_TIF [TILE_TIF ...] OUT_JSON

Grade comes from Copernicus GLO-30, a surface model, so it is a screening estimate: buildings and
trees inflate it, tunnels and bridges are wrong. It decides whether grade matters, not the final field.
"""
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib

import numpy as np
from pyproj import Transformer


def read_tiff(path):
    d = open(path, "rb").read()
    bo = "<" if d[:2] == b"II" else ">"
    assert struct.unpack(bo + "H", d[2:4])[0] == 42
    off = struct.unpack(bo + "I", d[4:8])[0]
    n = struct.unpack(bo + "H", d[off : off + 2])[0]
    tags = {}
    sz = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 11: 4, 12: 8}
    fm = {1: "B", 3: "H", 4: "I", 11: "f", 12: "d"}
    for i in range(n):
        e = d[off + 2 + 12 * i : off + 14 + 12 * i]
        tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
        size = sz.get(typ, 1) * cnt
        raw = e[8:12] if size <= 4 else d[struct.unpack(bo + "I", e[8:12])[0] :][:size]
        tags[tag] = raw if typ == 2 else struct.unpack(bo + str(cnt) + fm[typ], raw[: size])
    w, h = tags[256][0], tags[257][0]
    tw, th = tags[322][0], tags[323][0]
    assert tags[259][0] in (8, 32946), "expected deflate"
    pred = tags.get(317, (1,))[0]
    out = np.zeros((h, w), np.float32)
    per = (w + tw - 1) // tw
    for k, (o, c) in enumerate(zip(tags[324], tags[325])):
        raw = zlib.decompress(d[o : o + c])
        if pred == 3:
            b = np.frombuffer(raw, np.uint8).reshape(th, tw * 4).copy()
            b = np.cumsum(b, axis=1, dtype=np.uint8)
            # TIFF floating predictor: each row holds byte planes, most significant first.
            t = np.frombuffer(b.reshape(th, 4, tw).transpose(0, 2, 1).tobytes(), ">f4").reshape(th, tw).astype(np.float32)
        else:
            t = np.frombuffer(raw, bo + "f4").reshape(th, tw)
        r, q = k // per, k % per
        y0, x0 = r * th, q * tw
        hh, ww = min(th, h - y0), min(tw, w - x0)
        out[y0 : y0 + hh, x0 : x0 + ww] = t[:hh, :ww]
    sx, sy = tags[33550][:2]
    _, _, _, lon0, lat0, _ = tags[33922]
    return out, lon0, lat0, sx, sy


def min_filter(z, r):
    from scipy.ndimage import minimum_filter

    return minimum_filter(z, size=2 * r + 1)


def main():
    net_path, osm_path, *tiles, out_path = sys.argv[1:]
    grids = [read_tiff(t) for t in tiles]
    grids_min = [min_filter(g[0], 1) for g in grids]

    def sample(lon, lat, use_min):
        z = np.full(lon.shape, np.nan)
        for g, gm in zip(grids, grids_min):
            a, lon0, lat0, sx, sy = g
            arr = gm if use_min else a
            col = np.nan_to_num((lon - lon0) / sx - 0.5, nan=-1.0, posinf=-1.0, neginf=-1.0)
            row = np.nan_to_num((lat0 - lat) / sy - 0.5, nan=-1.0, posinf=-1.0, neginf=-1.0)
            ok = (col >= 0) & (row >= 0) & (col < a.shape[1] - 1) & (row < a.shape[0] - 1)
            c0, r0 = col[ok].astype(int), row[ok].astype(int)
            fc, fr = col[ok] - c0, row[ok] - r0
            z[ok] = (
                arr[r0, c0] * (1 - fc) * (1 - fr)
                + arr[r0, c0 + 1] * fc * (1 - fr)
                + arr[r0 + 1, c0] * (1 - fc) * fr
                + arr[r0 + 1, c0 + 1] * fc * fr
            )
        return z

    tr = None
    off = None
    internal, normal = [], []
    grade_len, grade_raw, grade_lo, grade_sp = [], [], [], []
    tangent_jumps = []
    lane_end_dir = {}
    lane_start_dir = {}
    conns = []
    for ev, e in ET.iterparse(net_path, events=("end",)):
        if e.tag == "location":
            off = [float(x) for x in e.get("netOffset").split(",")]
            tr = Transformer.from_crs(e.get("projParameter"), "EPSG:4326", always_xy=True)
        elif e.tag == "connection":
            if e.get("via"):
                conns.append((e.get("from") + "_" + e.get("fromLane"), e.get("via"), e.get("to") + "_" + e.get("toLane")))
        elif e.tag == "edge":
            fn = e.get("function")
            is_int = fn == "internal"
            for lane in e.findall("lane"):
                allow = lane.get("allow")
                disallow = lane.get("disallow", "")
                if allow and "passenger" not in allow:
                    continue
                if "passenger" in disallow.split():
                    continue
                s = lane.get("shape")
                p = np.array([[float(v) for v in c.split(",")[:2]] for c in s.split()])
                if len(p) < 2:
                    continue
                d = np.diff(p, axis=0)
                seg = np.hypot(d[:, 0], d[:, 1])
                keep = seg > 1e-3
                if keep.sum() < 1:
                    continue
                d, seg = d[keep], seg[keep]
                ang = np.arctan2(d[:, 1], d[:, 0])
                lane_start_dir[lane.get("id")] = ang[0]
                lane_end_dir[lane.get("id")] = ang[-1]
                L = float(lane.get("length"))
                v = float(lane.get("speed"))
                if len(ang) > 1:
                    dth = np.abs((np.diff(ang) + np.pi) % (2 * np.pi) - np.pi)
                    ds = 0.5 * (seg[:-1] + seg[1:])
                    kap = dth / np.maximum(ds, 0.5)
                    # radius over a 10 m moving chord: raw polyline vertices overstate curvature.
                    s_mid = np.cumsum(ds)
                    kmax = 0.0
                    smax = 0.0
                    wnd = 10.0
                    for i in range(len(dth)):
                        j = np.searchsorted(s_mid, s_mid[i] + wnd)
                        span = max(s_mid[min(j, len(dth) - 1)] - s_mid[i] + ds[i], wnd)
                        k = dth[i : j + 1].sum() / span
                        if k > kmax:
                            kmax, smax = k, s_mid[i]
                    total = dth.sum()
                else:
                    kmax, smax, total = 0.0, 0.0, 0.0
                rec = (L, v, kmax, smax, total)
                (internal if is_int else normal).append(rec)
                if not is_int and L >= 30 and tr is not None:
                    n = max(2, int(L // 10) + 1)
                    cum = np.concatenate([[0], np.cumsum(seg)])
                    q = np.linspace(0, cum[-1], n)
                    pk = p[np.r_[True, keep]]
                    x = np.interp(q, cum, pk[:, 0]) - off[0]
                    y = np.interp(q, cum, pk[:, 1]) - off[1]
                    lon, lat = tr.transform(x, y)
                    for use_min, sink in ((False, grade_raw), (True, grade_lo)):
                        z = sample(np.asarray(lon), np.asarray(lat), use_min)
                        if np.isnan(z).any():
                            sink.append(np.nan)
                            continue
                        w = 11
                        if len(z) > w:
                            zs = np.convolve(z, np.ones(w) / w, mode="valid")
                            sink.append(np.max(np.abs(np.diff(zs))) / (q[1] - q[0]))
                        else:
                            sink.append(abs(z[-1] - z[0]) / max(L, 1.0))
                    grade_len.append(L)
                    grade_sp.append(v)
            e.clear()
        elif e.tag == "tlLogic" or e.tag == "junction" or e.tag == "request":
            e.clear()

    for a, via, b in conns:
        if a in lane_end_dir and via in lane_start_dir:
            tangent_jumps.append(abs((lane_end_dir[a] - lane_start_dir[via] + np.pi) % (2 * np.pi) - np.pi))
        if via in lane_end_dir and b in lane_start_dir:
            tangent_jumps.append(abs((lane_end_dir[via] - lane_start_dir[b] + np.pi) % (2 * np.pi) - np.pi))
    tangent_jumps = np.degrees(np.array(tangent_jumps))

    def pct(x, w=None, q=(5, 25, 50, 75, 95, 99)):
        x = np.asarray(x, float)
        if w is None:
            return dict(zip(map(str, q), np.round(np.percentile(x, q), 4).tolist()))
        i = np.argsort(x)
        cw = np.cumsum(np.asarray(w)[i]) / np.sum(w)
        return {str(k): round(float(x[i][np.searchsorted(cw, k / 100)]), 4) for k in q}

    I = np.array(internal)
    N = np.array(normal)
    res = {"n_internal": len(I), "n_normal": len(N), "km_internal": float(I[:, 0].sum() / 1e3), "km_normal": float(N[:, 0].sum() / 1e3)}
    turn = I[(I[:, 4] > np.radians(30)) & (I[:, 2] > 0)]
    ay = turn[:, 1] ** 2 * turn[:, 2]
    res["internal_turns"] = {
        "n": len(turn),
        "speed_mps": pct(turn[:, 1]),
        "radius_m": pct(1 / turn[:, 2]),
        "ay_at_lane_speed_mps2": pct(ay),
        "ay_gt_3": float((ay > 3).mean()),
        "ay_gt_5_5": float((ay > 5.5).mean()),
        "ay_gt_dry_8": float((ay > 8).mean()),
    }
    for name, A in (("normal", N), ("internal_all", I)):
        k = A[A[:, 2] > 0]
        ay2 = A[:, 1] ** 2 * A[:, 2]
        res[name + "_curve"] = {
            "share_lanes_curve_cap_below_limit_ay2": float((ay2 > 2).mean()),
            "share_lanes_curve_cap_below_limit_ay3": float((ay2 > 3).mean()),
            "share_lanes_curve_cap_below_limit_ay5_5": float((ay2 > 5.5).mean()),
            "share_km_ay3": float(A[ay2 > 3, 0].sum() / A[:, 0].sum()),
            "ay_at_limit": pct(ay2),
        }
    res["tangent_jump_deg"] = {**pct(tangent_jumps), "n": int(len(tangent_jumps)), "gt5": float((tangent_jumps > 5).mean()), "gt15": float((tangent_jumps > 15).mean()), "gt30": float((tangent_jumps > 30).mean())}

    gl = np.array(grade_len)
    for name, g in (("dsm_raw", grade_raw), ("dsm_min3", grade_lo)):
        g = np.array(g, float)
        ok = np.isfinite(g)
        res["grade_" + name] = {
            "n": int(ok.sum()),
            "km_weighted_abs_max_grade": pct(g[ok], gl[ok]),
            "km_share_gt_3pct": float(gl[ok][g[ok] > 0.03].sum() / gl[ok].sum()),
            "km_share_gt_5pct": float(gl[ok][g[ok] > 0.05].sum() / gl[ok].sum()),
            "km_share_gt_8pct": float(gl[ok][g[ok] > 0.08].sum() / gl[ok].sum()),
            "unsampled_share": float(1 - ok.mean()),
        }

    highway = re.compile(r'k="highway" v="(motorway|trunk|primary|secondary|tertiary|unclassified|residential|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|living_street|service)')
    counts = {"ways": 0, "bridge": 0, "tunnel": 0, "incline": 0, "layer": 0, "surface": 0}
    in_way = False
    tags = []
    with open(osm_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "<way " in line:
                in_way, tags = True, []
            elif in_way:
                if "<tag " in line:
                    tags.append(line)
                elif "</way>" in line:
                    in_way = False
                    t = "".join(tags)
                    if highway.search(t):
                        counts["ways"] += 1
                        counts["bridge"] += 'k="bridge"' in t
                        counts["tunnel"] += 'k="tunnel"' in t
                        counts["incline"] += 'k="incline"' in t
                        counts["layer"] += 'k="layer"' in t
                        counts["surface"] += 'k="surface"' in t
    res["osm_highway_tag_counts"] = counts
    json.dump(res, open(out_path, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
