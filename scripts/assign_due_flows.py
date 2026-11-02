#!/usr/bin/env python3
"""Per-edge flow implied by SUMO route files, the static comparison for a published assignment.
usage: assign_due_flows.py OUT.csv ROUTES.rou.xml [...]"""
import collections, re, sys

rx_v = re.compile(r"<vehicle\b")
rx_e = re.compile(r'<route\b[^>]*edges="([^"]*)"')
flow = collections.Counter()
for p in sys.argv[2:]:
    pending = False
    with open(p) as f:
        for line in f:
            if rx_v.search(line):
                pending = True
            m = rx_e.search(line)
            if m and pending:
                flow.update(m[1].split())
                pending = False
with open(sys.argv[1], "w") as w:
    w.write("edge,flow\n")
    for e, n in sorted(flow.items()):
        w.write(f"{e},{n}\n")
print(len(flow), "edges", sum(flow.values()), "passages")
