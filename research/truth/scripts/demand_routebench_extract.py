"""Extract the Berlin edge graph and trips into flat binaries for demand_routebench.rs. Reads SUMO XML as text only."""

import gzip
import re
import struct
import sys

import numpy as np

net_path, rou_path, out = sys.argv[1:4]
attr = re.compile(r'([\w:]+)="([^"]*)"')
ids, length, speed = {}, [], []
pairs = []
cur, cl, cs = None, [], []


def flush():
    if cur is not None and cl:
        ids[cur] = len(length)
        length.append(min(cl))
        speed.append(max(cs))


with open(net_path, encoding="utf-8") as f:
    for line in f:
        s = line.lstrip()
        if s.startswith("<edge "):
            flush()
            a = dict(attr.findall(s))
            cl, cs = [], []
            cur = a["id"] if a.get("function", "normal") == "normal" and "from" in a else None
        elif s.startswith("<lane ") and cur is not None:
            a = dict(attr.findall(s))
            if "passenger" in a.get("allow", "passenger") and "passenger" not in a.get("disallow", ""):
                cl.append(float(a["length"]))
                cs.append(float(a["speed"]))
        elif s.startswith("<connection "):
            a = dict(attr.findall(s))
            pairs.append((a["from"], a["to"]))
flush()
n = len(length)
adj = sorted({(ids[a], ids[b]) for a, b in pairs if a in ids and b in ids})
print("edges", n, "turns", len(adj), flush=True)
first = np.zeros(n + 1, dtype=np.uint32)
for a, _ in adj:
    first[a + 1] += 1
first = np.cumsum(first).astype(np.uint32)
to = np.array([b for _, b in adj], dtype=np.uint32)
dep_re = re.compile(r'depart="([^"]+)"')
edges_re = re.compile(r'edges="([^"]+)"')
oo, dd, tt = [], [], []
n_routes = total_edges = 0
dep = None
with gzip.open(rou_path, "rt", encoding="utf-8") as f:
    for line in f:
        if "<vehicle" in line:
            m = dep_re.search(line)
            dep = float(m.group(1)) if m else None
        m = edges_re.search(line)
        if m and dep is not None:
            e = m.group(1).split()
            n_routes += 1
            total_edges += len(e)
            if e[0] in ids and e[-1] in ids:
                oo.append(ids[e[0]])
                dd.append(ids[e[-1]])
                tt.append(dep)
oo, dd, tt = np.array(oo, dtype=np.int64), np.array(dd, dtype=np.int64), np.array(tt)
print("trips", n_routes, "mean edges per route", round(total_edges / max(n_routes, 1), 2), "kept", len(oo), flush=True)
for binw in (300, 900, 3600):
    b = (tt // binw).astype(np.int64)
    print("bin", binw, "distinct origin-bin", len(np.unique(oo * 1000 + b)), "distinct od-bin", len(np.unique((oo * n + dd) * 1000 + b)), flush=True)
print("distinct origins", len(np.unique(oo)), "distinct destinations", len(np.unique(dd)), "distinct od", len(np.unique(oo * n + dd)), flush=True)
with open(out, "wb") as f:
    f.write(struct.pack("<QQQ", n, len(to), len(oo)))
    np.array(length, dtype=np.float32).tofile(f)
    np.array(speed, dtype=np.float32).tofile(f)
    first.tofile(f)
    to.tofile(f)
    oo.astype(np.uint32).tofile(f)
    dd.astype(np.uint32).tofile(f)
    tt.astype(np.float32).tofile(f)
