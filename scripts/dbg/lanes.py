"""`cars lanes`: walk every route lane by lane against links and line markings, and list the ones no driver can complete without breaking them. With --edge-csv, how many of a run's teleports happened on those roads."""
import argparse
import collections
import gzip
import json
import os
import re

import numpy as np

from .run import Net


class Lanes:
    def __init__(self, net, bit, change_seconds=0.0):
        self.net, self.bit, self.change_seconds = net, bit, change_seconds
        self.memo = {}

    def lanes_of(self, e):
        first = int(self.net.edge_first[e])
        return range(first, first + int(self.net.edge_lanes[e]))

    def spread(self, start):
        """All lanes a car on these may change to, on this road."""
        n, bit = self.net, self.bit
        seen = set(start)
        l0 = next(iter(start))
        # A road crossed quicker than this leaves no time to change on it.
        if float(n.lane_length[l0]) < float(n.lane_speed[l0]) * self.change_seconds:
            return seen
        todo = list(start)
        while todo:
            l = todo.pop()
            i = int(n.lane_index[l])
            if i > 0 and n.lane_change_right[l] & bit and n.lane_allow[l - 1] & bit and l - 1 not in seen:
                seen.add(l - 1)
                todo.append(l - 1)
            if i + 1 < int(n.edge_lanes[n.lane_edge[l]]) and n.lane_change_left[l] & bit and n.lane_allow[l + 1] & bit and l + 1 not in seen:
                seen.add(l + 1)
                todo.append(l + 1)
        return seen

    def step(self, e, start, f):
        """Lanes of road f it can arrive on, from lanes `start` of road e."""
        key = (e, start, f)
        hit = self.memo.get(key)
        if hit is None:
            n = self.net
            out = set()
            for l in self.spread(start):
                s, c = int(n.lane_links_start[l]), int(n.lane_links_count[l])
                for k in range(s, s + c):
                    if int(n.link_to_edge[k]) == f:
                        out.add(int(n.link_to_lane[k]))
            hit = self.memo[key] = frozenset(out)
        return hit

    def check(self, route):
        """None if it can be driven. Otherwise where it first fails."""
        n = self.net
        at = None
        for name, next_name in zip(route, route[1:]):
            e, f = n.edge_index.get(name), n.edge_index.get(next_name)
            if e is None or f is None:
                return None
            if at is None:
                at = frozenset(l for l in self.lanes_of(e) if n.lane_allow[l] & self.bit)
            arrive = self.step(e, at, f)
            if not arrive:
                return name, next_name, sorted(int(n.lane_index[l]) for l in at)
            at = arrive
        return None


def routes_in(path):
    """(edges, how many trips) over a route file, with shared routes and inline ones."""
    named = {}
    counts = collections.Counter()
    inline = collections.Counter()
    with (gzip.open(path, 'rt') if path.endswith('.gz') else open(path)) as f:
        for line in f:
            s = line.strip()
            if s.startswith('<route '):
                m = re.search(r'edges="([^"]+)"', s)
                i = re.search(r' id="([^"]+)"', s)
                if m and i:
                    named[i.group(1)] = m.group(1)
                elif m:
                    inline[m.group(1)] += 1
            elif s.startswith('<vehicle') or s.startswith('<flow'):
                r = re.search(r'route="([^"]+)"', s)
                if r:
                    counts[r.group(1)] += 1
                else:
                    m = re.search(r'edges="([^"]+)"', s)
                    if m:
                        inline[m.group(1)] += 1
    for name, c in counts.items():
        if name in named:
            yield named[name].split(), c
    for edges, c in inline.items():
        yield edges.split(), c


def main(argv):
    a = argparse.ArgumentParser(prog='cars lanes', description=__doc__)
    a.add_argument('--net', required=True, help='<trace>.net.json or `cars netinfo` output')
    a.add_argument('--routes', required=True)
    a.add_argument('--vclass-bit', type=int, default=6, help='bit of the vehicle class, 6 is passenger')
    a.add_argument('--change-seconds', type=float, default=0.0, help='a lane change needs this long on a road at its limit: 0 for what the markings allow, 1 for one simulated step, 5 for what report 05 measured')
    a.add_argument('--edge-csv', help='`cars run --edge-csv` output, to count teleports on what this finds')
    a.add_argument('--top', type=int, default=20)
    a.add_argument('--json', action='store_true')
    a = a.parse_args(argv)
    net = Net(a.net)
    w = Lanes(net, 1 << a.vclass_bit, a.change_seconds)
    trips = routes_total = 0
    bad_trips = 0
    bad_routes = 0
    where = collections.Counter()
    samples = {}
    for route, count in routes_in(a.routes):
        trips += count
        routes_total += 1
        fail = w.check(route)
        if fail:
            bad_routes += 1
            bad_trips += count
            key = (fail[0], fail[1])
            where[key] += count
            samples.setdefault(key, fail[2])
    tele = {}
    total_tp = 0
    if a.edge_csv:
        import pandas as pd
        d = pd.read_csv(a.edge_csv, usecols=['edge', 'teleports'])
        tele = d.groupby('edge')['teleports'].sum().to_dict()
        total_tp = float(sum(tele.values()))
    rows = []
    for (e, f), c in where.most_common():
        i = net.edge_index[e]
        first = int(net.edge_first[i])
        going = [int(net.lane_index[l]) for l in range(first, first + int(net.edge_lanes[i])) if net.edge_index[f] in net.link_to_edge[int(net.lane_links_start[l]):int(net.lane_links_start[l] + net.lane_links_count[l])]]
        rows.append(dict(edge=e, next=f, trips=c, can_arrive_on=samples[(e, f)], lanes_that_go_there=going, length=round(float(net.lane_length[first]), 1), teleports=int(tele.get(e, 0)), x=round(float(net.lane_x1[first]), 0), y=round(float(net.lane_y1[first]), 0)))
    on_bad = sum(int(tele.get(e, 0)) for e in {k[0] for k in where})
    report = dict(routes=routes_total, trips=trips, impossible_routes=bad_routes, impossible_trips=bad_trips, share_of_trips=round(bad_trips / max(trips, 1), 5), places=len(where), teleports_in_run=int(total_tp), teleports_on_those_roads=on_bad, share_of_teleports=round(on_bad / total_tp, 3) if total_tp else None, top=rows[:a.top])
    if a.json:
        print(json.dumps(report, indent=1))
        return
    print(f"with {a.change_seconds:g} s needed to change lane:")
    print(f"{bad_trips} of {trips} trips ({100 * report['share_of_trips']:.2f}%), {bad_routes} of {routes_total} routes, cannot be driven lane by lane, at {len(where)} places.")
    if total_tp:
        print(f"{on_bad} of {int(total_tp)} teleports in that run ({100 * report['share_of_teleports']:.1f}%) were on those roads.")
    print(f"{'trips':>7} {'teleports':>9} {'road':<24} {'then':<22} {'length':>7} {'can be on':<12} {'needs lane':<11} at")
    for r in rows[:a.top]:
        print(f"{r['trips']:7} {r['teleports']:9} {r['edge'][:24]:<24} {r['next'][:22]:<22} {r['length']:7.1f} {str(r['can_arrive_on']):<12} {str(r['lanes_that_go_there']):<11} ({r['x']:.0f},{r['y']:.0f})")
