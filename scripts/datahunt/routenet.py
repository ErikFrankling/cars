"""Road graph from Overpass JSON, an HMM map matcher (Newson & Krumm) and link-based Dijkstra with turn costs."""
import heapq, json, math, re
from collections import defaultdict

DEFAULT_KMH = {"motorway": 105, "trunk": 90, "primary": 65, "secondary": 55, "tertiary": 45, "unclassified": 40,
               "residential": 30, "living_street": 10, "road": 30, "motorway_link": 60, "trunk_link": 50,
               "primary_link": 40, "secondary_link": 35, "tertiary_link": 30}
SIGNAL_S = 15.0
TURN_S = {"left": 5.0, "right": 2.0, "sharp": 8.0}


def parse_speed(tag, hw):
    if tag:
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(mph)?", tag)
        if m:
            v = float(m.group(1)) * (1.609 if m.group(2) else 1)
            if v > 0:
                return v
    return DEFAULT_KMH.get(hw, 30)


class Net:
    def __init__(self, path):
        data = json.load(open(path))["elements"]
        nodes = {e["id"]: e for e in data if e["type"] == "node"}
        ways = list({e["id"]: e for e in data if e["type"] == "way"}.values())
        rels = list({e["id"]: e for e in data if e["type"] == "relation"}.values())
        del data
        lat0 = sum(n["lat"] for n in nodes.values()) / len(nodes)
        lon0 = sum(n["lon"] for n in nodes.values()) / len(nodes)
        self.lat0, self.lon0 = lat0, lon0
        self.kx = 111320 * math.cos(math.radians(lat0))
        self.ky = 110540
        usable = []
        for w in ways:
            t = w.get("tags", {})
            if t.get("access") in ("no", "private") or t.get("motor_vehicle") in ("no", "private") or t.get("motorcar") == "no":
                continue
            if t.get("area") == "yes":
                continue
            usable.append(w)
        use = defaultdict(int)
        for w in usable:
            nd = w["nodes"]
            for n in nd:
                use[n] += 1
            use[nd[0]] += 1
            use[nd[-1]] += 1
        signal = {i for i, n in nodes.items() if n.get("tags", {}).get("highway") == "traffic_signals"}
        self.u, self.v, self.length, self.ff, self.hw, self.way, self.poly, self.cum, self.rev = [], [], [], [], [], [], [], [], []
        self.signal_end = []
        out_at = defaultdict(list)
        in_at = defaultdict(list)
        way_in, way_out = defaultdict(list), defaultdict(list)

        def add(way, seq, kmh, hw):
            xy = [self.xy(nodes[n]["lat"], nodes[n]["lon"]) for n in seq]
            cum = [0.0]
            for a, b in zip(xy, xy[1:]):
                cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
            if cum[-1] < 0.5:
                return None
            i = len(self.u)
            self.u.append(seq[0]); self.v.append(seq[-1]); self.length.append(cum[-1]); self.poly.append(xy); self.cum.append(cum)
            self.ff.append(cum[-1] / (kmh / 3.6)); self.hw.append(hw); self.way.append(way); self.rev.append(-1)
            self.signal_end.append(seq[-1] in signal)
            out_at[seq[0]].append(i); in_at[seq[-1]].append(i)
            way_in[(way, seq[-1])].append(i); way_out[(way, seq[0])].append(i)
            return i

        for w in usable:
            t = w.get("tags", {})
            hw = t["highway"]
            if hw == "service":
                continue
            kmh = parse_speed(t.get("maxspeed"), hw)
            one = t.get("oneway")
            fwd_only = one in ("yes", "1", "true") or hw == "motorway" or t.get("junction") in ("roundabout", "circular")
            bwd_only = one in ("-1", "reverse")
            nd = w["nodes"]
            start = 0
            for k in range(1, len(nd)):
                if k == len(nd) - 1 or use[nd[k]] >= 2 or nd[k] in signal:
                    seq = nd[start:k + 1]
                    a = b = None
                    if not bwd_only:
                        a = add(w["id"], seq, kmh, hw)
                    if not fwd_only:
                        b = add(w["id"], seq[::-1], kmh, hw)
                    if a is not None and b is not None:
                        self.rev[a] = b; self.rev[b] = a
                    start = k
        self.n = len(self.u)
        self.banned = set()
        only = defaultdict(set)
        self.rel_used = self.rel_skipped = 0
        for r in rels:
            res = r.get("tags", {}).get("restriction", "")
            ms = r.get("members", [])
            fr = [m["ref"] for m in ms if m["role"] == "from" and m["type"] == "way"]
            to = [m["ref"] for m in ms if m["role"] == "to" and m["type"] == "way"]
            via = [m["ref"] for m in ms if m["role"] == "via" and m["type"] == "node"]
            if not (res and fr and to and via):
                self.rel_skipped += 1
                continue
            self.rel_used += 1
            for a in way_in.get((fr[0], via[0]), []):
                for b in way_out.get((to[0], via[0]), []):
                    if res.startswith("no_"):
                        self.banned.add((a, b))
                    elif res.startswith("only_"):
                        only[a].add(b)
        self.adj = [[] for _ in range(self.n)]
        self.turns = 0
        for a in range(self.n):
            outs = out_at.get(self.v[a], [])
            for b in outs:
                if (a, b) in self.banned or (a in only and b not in only[a]):
                    continue
                if self.rev[a] == b and len(outs) > 1:
                    continue
                self.adj[a].append((b, self.turn_cost(a, b)))
        self.grid = defaultdict(list)
        self.cell = 100.0
        for i, xy in enumerate(self.poly):
            for s, (p, q) in enumerate(zip(xy, xy[1:])):
                x0, x1 = sorted((p[0], q[0])); y0, y1 = sorted((p[1], q[1]))
                for cx in range(int(x0 // self.cell), int(x1 // self.cell) + 1):
                    for cy in range(int(y0 // self.cell), int(y1 // self.cell) + 1):
                        self.grid[(cx, cy)].append((i, s))

    def xy(self, lat, lon):
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def turn_cost(self, a, b):
        pa, pb = self.poly[a], self.poly[b]
        d1 = (pa[-1][0] - pa[-2][0], pa[-1][1] - pa[-2][1])
        d2 = (pb[1][0] - pb[0][0], pb[1][1] - pb[0][1])
        ang = math.degrees(math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1[0] * d2[0] + d1[1] * d2[1]))
        c = SIGNAL_S if self.signal_end[a] else 0.0
        if abs(ang) > 150:
            c += TURN_S["sharp"]
        elif ang > 30:
            c += TURN_S["left"]
        elif ang < -30:
            c += TURN_S["right"]
        return c

    def candidates(self, x, y, r, k=6):
        cx, cy = int(x // self.cell), int(y // self.cell)
        span = int(r // self.cell) + 1
        best = {}
        for i in range(cx - span, cx + span + 1):
            for j in range(cy - span, cy + span + 1):
                for link, s in self.grid.get((i, j), ()):
                    p, q = self.poly[link][s], self.poly[link][s + 1]
                    dx, dy = q[0] - p[0], q[1] - p[1]
                    l2 = dx * dx + dy * dy
                    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - p[0]) * dx + (y - p[1]) * dy) / l2))
                    d = math.hypot(p[0] + t * dx - x, p[1] + t * dy - y)
                    if d <= r and (link not in best or d < best[link][0]):
                        best[link] = (d, self.cum[link][s] + t * math.sqrt(l2))
        return [(l, *v) for l, v in sorted(best.items(), key=lambda kv: kv[1][0])[:k]]

    def bounded(self, a, pos_a, targets, limit):
        """Road distance from (a,pos_a) to the start of each target link, bounded. Returns dist and parent."""
        start = self.length[a] - pos_a
        dist = {a: start}
        parent = {a: None}
        heap = [(start, a)]
        found = {}
        need = set(targets)
        while heap:
            d, l = heapq.heappop(heap)
            if d > dist.get(l, 1e18) or d > limit:
                continue
            for m, _ in self.adj[l]:
                nd = d + self.length[m]
                if m in need and m not in found and d <= limit:
                    found[m] = d
                    parent.setdefault(m, l)
                    if parent[m] != l and m not in dist:
                        parent[m] = l
                if nd < dist.get(m, 1e18):
                    dist[m] = nd
                    parent[m] = l
                    heapq.heappush(heap, (nd, m))
        return found, parent

    def match(self, pts, sigma=12.0, beta=30.0, radius=40.0, back_tol=15.0):
        """pts: list of (x,y). Returns segments: each a dict with links, start_pos, end_pos, first and last point index and residuals."""
        cands = [self.candidates(x, y, radius) for x, y in pts]
        segs = []
        cur = None  # list of step records

        def finish(cur):
            if cur is None or len(cur["cand"]) < 2:
                return
            scores = cur["score"][-1]
            k = max(scores, key=lambda z: scores[z])
            idx = [k]
            for t in range(len(cur["cand"]) - 1, 0, -1):
                k = cur["back"][t][k]
                idx.append(k)
            idx.reverse()
            links = []
            per_step = [0.0]
            res = []
            for t, i in enumerate(idx):
                c = cur["cand"][t][i]
                res.append(c[1])
                if t == 0:
                    links.append(c[0])
                    continue
                p = cur["cand"][t - 1][idx[t - 1]]
                path = self.path_between(p, c, cur["limit"][t])
                if path is None:
                    return
                links.extend(path)
            c0, c1 = cur["cand"][0][idx[0]], cur["cand"][-1][idx[-1]]
            segs.append({"links": links, "start_pos": c0[2], "end_pos": c1[2], "t0": cur["first"], "t1": cur["first"] + len(idx) - 1,
                         "res": res, "chosen": [cur["cand"][t][i] for t, i in enumerate(idx)], "limits": cur["limit"]})

        for t, (pt, cs) in enumerate(zip(pts, cands)):
            if not cs:
                finish(cur); cur = None
                continue
            emis = [-0.5 * (c[1] / sigma) ** 2 for c in cs]
            if cur is None:
                cur = {"first": t, "cand": [cs], "score": [{i: e for i, e in enumerate(emis)}], "back": [None], "limit": [0]}
                continue
            prev_cs = cur["cand"][-1]
            prev_score = cur["score"][-1]
            gc = math.hypot(pt[0] - pts[t - 1][0], pt[1] - pts[t - 1][1])
            limit = max(3 * gc, gc + 300)
            target_links = [c[0] for c in cs]
            scores, back = {}, {}
            for i, a in enumerate(prev_cs):
                if i not in prev_score:
                    continue
                found, _ = self.bounded(a[0], a[2], target_links, limit)
                for j, b in enumerate(cs):
                    if b[0] == a[0] and b[2] >= a[2] - back_tol:
                        rd = max(0.0, b[2] - a[2])
                    elif b[0] in found:
                        rd = found[b[0]] + b[2]
                    else:
                        continue
                    if rd > limit:
                        continue
                    s = prev_score[i] - abs(rd - gc) / beta + emis[j]
                    if j not in scores or s > scores[j]:
                        scores[j] = s; back[j] = i
            if not scores:
                finish(cur)
                cur = {"first": t, "cand": [cs], "score": [{i: e for i, e in enumerate(emis)}], "back": [None], "limit": [0]}
                continue
            cur["cand"].append(cs); cur["score"].append(scores); cur["back"].append(back); cur["limit"].append(limit)
        finish(cur)
        return segs

    def path_between(self, a, b, limit):
        if a[0] == b[0] and b[2] >= a[2] - 15.0:
            return []
        found, parent = self.bounded(a[0], a[2], [b[0]], limit)
        if b[0] not in found:
            return None
        chain = []
        l = b[0]
        while l is not None and l != a[0]:
            chain.append(l)
            l = parent.get(l)
        chain.reverse()
        return chain

    def route(self, src, dst, cost, turn=True, extra=None):
        """Least-cost link sequence from link src to link dst. cost: per-link list. Excludes partial-link trimming."""
        if src == dst:
            return [src], 0.0
        dist = {src: 0.0}
        parent = {src: None}
        heap = [(0.0, src)]
        while heap:
            d, l = heapq.heappop(heap)
            if d > dist[l]:
                continue
            if l == dst:
                seq = []
                while l is not None:
                    seq.append(l); l = parent[l]
                return seq[::-1], d
            for m, tc in self.adj[l]:
                nd = d + cost[m] + (tc if turn else 0.0)
                if nd < dist.get(m, 1e18):
                    dist[m] = nd; parent[m] = l
                    heapq.heappush(heap, (nd, m))
        return None, None

    def cost_of(self, links, cost, turn=True):
        t = sum(cost[l] for l in links[1:])
        if turn:
            for a, b in zip(links, links[1:]):
                tc = next((c for m, c in self.adj[a] if m == b), None)
                t += tc if tc is not None else 0.0
        return t

    def route_length(self, links, sp=0.0, ep=None):
        if not links:
            return 0.0
        if ep is None:
            ep = self.length[links[-1]]
        if len(links) == 1:
            return max(0.0, ep - sp)
        return self.length[links[0]] - sp + sum(self.length[l] for l in links[1:-1]) + ep


def overlap(net, a, b):
    """Share of the length of route a whose directed links also lie on route b."""
    sb = set(b)
    la = sum(net.length[l] for l in a)
    return sum(net.length[l] for l in a if l in sb) / la if la else 0.0
