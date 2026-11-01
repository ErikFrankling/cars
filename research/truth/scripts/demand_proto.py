"""Self-written prototype of the demand and assignment loop for research/truth/06-demand-and-route-choice.md.

A spatial-queue simulator (finite storage, spillback, FIFO head blocking) on a synthetic grid, a time-dependent
router, and the iterative assignment, departure-time, calibration, feasibility and en-route experiments. It uses
no SUMO code or tools. It is a model of a model: results settle design questions about the loop, not facts about
any real city, and the simulator is mesoscopic, not the cars GPU kernel.

Run from the repo root, one experiment at a time:
  nix develop --command python3 -I research/truth/scripts/demand_proto.py E1 [--quick]
Results go to research/truth/demand-proto/<experiment>.json.
"""

import argparse
import heapq
import json
import os
import random
import sys
import time
from collections import deque

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import maximum_flow

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demand-proto")
DT = 5.0
BIN = 300.0
ROUTE_BIN = 600.0
INF = 1e12
NET_N = 12
BASE_TRIPS = 24000


class Net:
    def __init__(self, n=8, spacing=400.0, bridges=None, arterial_every=3):
        self.n = n
        self.nn = n * n
        fr, to, ln, sp_, lanes = [], [], [], [], []

        def nid(r, c):
            return r * n + c

        def add(a, b, art):
            fr.append(a)
            to.append(b)
            ln.append(spacing)
            sp_.append(16.7 if art else 11.1)
            lanes.append(2 if art else 1)

        for r in range(n):
            for c in range(n):
                if c + 1 < n:
                    art = r % arterial_every == 1
                    add(nid(r, c), nid(r, c + 1), art)
                    add(nid(r, c + 1), nid(r, c), art)
                if r + 1 < n:
                    if bridges is not None and r == n // 2 - 1 and c not in bridges:
                        continue
                    art = c % arterial_every == 1
                    add(nid(r, c), nid(r + 1, c), art)
                    add(nid(r + 1, c), nid(r, c), art)
        self.fr = np.array(fr)
        self.to = np.array(to)
        self.length = np.array(ln)
        self.nl = len(fr)
        self.ff = self.length / np.array(sp_)
        lanes = np.array(lanes)
        # Signalised urban approach: about 900 veh/h per lane of green-weighted discharge.
        self.cap = lanes * 900.0 / 3600.0
        self.store = np.maximum(3, (self.length * lanes / 7.5).astype(int))
        self.out = [[] for _ in range(self.nn)]
        self.inn = [[] for _ in range(self.nn)]
        for l in range(self.nl):
            self.out[fr[l]].append(l)
            self.inn[to[l]].append(l)
        self.perms = [np.random.default_rng(i).permutation(self.nl).tolist() for i in range(16)]
        self.bridges = bridges

    def zone(self, node, zdiv=2):
        return (node // self.n // zdiv) * (self.n // zdiv + (self.n % zdiv > 0)) + (node % self.n) // zdiv

    def nzones(self, zdiv=2):
        m = self.n // zdiv + (self.n % zdiv > 0)
        return m * m


class Demand:
    """Fixed travellers: origin node, destination node, desired arrival, chosen departure."""

    def __init__(self, o, d, tstar, dep):
        self.o, self.d, self.tstar, self.dep = o, d, tstar, dep
        self.n = len(o)

    def copy(self):
        return Demand(self.o.copy(), self.d.copy(), self.tstar.copy(), self.dep.copy())


def gravity_weights(net, cross_bias=0.0):
    n = net.n
    rr, cc = np.divmod(np.arange(net.nn), n)
    centre = np.hypot(rr - (n - 1) / 2, cc - (n - 1) / 2)
    home = 0.3 + centre / centre.max()
    work = np.exp(-centre / (0.35 * n))
    dist = np.abs(rr[:, None] - rr[None, :]) + np.abs(cc[:, None] - cc[None, :])
    w = home[:, None] * work[None, :] * np.exp(-dist / (0.6 * n))
    np.fill_diagonal(w, 0)
    if cross_bias:
        w = w * (1 + cross_bias * ((rr[:, None] < n // 2) != (rr[None, :] < n // 2)))
    return w / w.sum()


def make_demand(net, trips, rng, weights=None, peak=4500.0, sigma=1500.0, horizon_dep=10800.0):
    w = gravity_weights(net) if weights is None else weights
    idx = rng.choice(w.size, size=trips, p=w.ravel())
    o, d = np.divmod(idx, net.nn)
    tstar = np.clip(rng.normal(peak, sigma, trips), 300, horizon_dep)
    dep = np.clip(tstar - 600 - rng.normal(0, 60, trips), 0, horizon_dep)
    return Demand(o, d, tstar, dep)


def simulate(net, dem, routes, seed=0, horizon=21600.0, teleport=None, jitter=30.0, closed=None, nav=None,
             stall_limit=1800.0, dep_override=None):
    """One day of spatial-queue traffic. routes[i] is a list of link ids, or empty for an unroutable trip."""
    rng = random.Random(seed)
    nl, n = net.nl, dem.n
    nb = int(horizon // BIN) + 2
    ent = np.zeros((nl, nb))
    lft = np.zeros((nl, nb))
    req = np.zeros((nl, nb))
    ins = np.zeros((nl, nb))
    vs = np.zeros((nl, nb))
    dep = dem.dep if dep_override is None else dep_override
    jit = np.random.default_rng(seed + 991).normal(0, jitter, n) if jitter else np.zeros(n)
    planned = np.clip(dep + jit, 0, None)
    order = np.argsort(planned).tolist()
    cap = (net.cap * DT).tolist()
    capmax = [max(1.0, c) for c in cap]
    acc = [0.0] * nl
    ff = net.ff.tolist()
    store = net.store.tolist()
    q = [deque() for _ in range(nl)]
    wait = [deque() for _ in range(nl)]
    occ = [0] * nl
    exit_t = [0.0] * n
    pos = [0] * n
    arrive = np.full(n, np.nan)
    insert = np.full(n, np.nan)
    blocked_since = [None] * nl
    teleports = 0
    teleported_trip = np.zeros(n, bool)
    ptr, t, active = 0, 0.0, 0
    live_routes = routes if nav is None else [list(r) for r in routes]
    moved_at = 0.0
    fail = None
    nav_rng = np.random.default_rng(seed + 77)
    is_nav = None
    if nav is not None:
        is_nav = nav_rng.random(n) < nav["p"]
    reroutes = 0
    next_nav = 0.0
    capnow = cap
    while t < horizon:
        b = int(t // BIN)
        if closed is not None and closed["t0"] <= t < closed["t1"]:
            capnow = list(cap)
            for l in closed["links"]:
                capnow[l] = cap[l] * closed["factor"]
        elif closed is not None:
            capnow = cap
        if nav is not None and t >= next_nav:
            next_nav = t + nav["period"]
            reroutes += nav_epoch(net, live_routes, pos, insert, arrive, is_nav, q, occ, capnow, nav)
        while ptr < n and planned[order[ptr]] <= t:
            i = order[ptr]
            ptr += 1
            r = live_routes[i]
            if r:
                wait[r[0]].append(i)
                req[r[0], b] += 1
        for l in net.perms[int(t / DT) % 16]:
            if not q[l]:
                if acc[l] < capmax[l]:
                    acc[l] = min(capmax[l], acc[l] + capnow[l])
                continue
            acc[l] = min(capmax[l], acc[l] + capnow[l])
            ql = q[l]
            while ql and acc[l] >= 1.0:
                i = ql[0]
                if exit_t[i] > t:
                    break
                r = live_routes[i]
                k = pos[i] + 1
                if k >= len(r):
                    ql.popleft()
                    occ[l] -= 1
                    lft[l, b] += 1
                    arrive[i] = t
                    acc[l] -= 1.0
                    active -= 1
                    moved_at = t
                    blocked_since[l] = None
                    continue
                nx = r[k]
                if occ[nx] >= store[nx]:
                    if blocked_since[l] is None:
                        blocked_since[l] = t
                    if teleport is None or t - blocked_since[l] < teleport:
                        break
                    teleports += 1
                    teleported_trip[i] = True
                blocked_since[l] = None
                ql.popleft()
                occ[l] -= 1
                lft[l, b] += 1
                occ[nx] += 1
                ent[nx, b] += 1
                exit_t[i] = t + ff[nx]
                q[nx].append(i)
                pos[i] = k
                acc[l] -= 1.0
                moved_at = t
        for l in range(nl):
            w = wait[l]
            while w and occ[l] < store[l]:
                i = w.popleft()
                occ[l] += 1
                ent[l, b] += 1
                ins[l, b] += 1
                exit_t[i] = t + ff[l]
                q[l].append(i)
                pos[i] = 0
                insert[i] = t
                active += 1
                moved_at = t
            vs[l, b] += occ[l] * DT
        t += DT
        if ptr >= n and active == 0 and not any(wait[l] for l in range(0, nl)):
            break
        if t - moved_at > stall_limit and ptr >= n:
            fail = "gridlock_stall"
            break
    routed = np.array([bool(r) for r in live_routes])
    return {
        "arrive": arrive, "insert": insert, "planned": planned, "ent": ent, "lft": lft, "req": req, "ins": ins,
        "vs": vs, "teleports": teleports, "teleported_trip": teleported_trip, "end": t, "fail": fail, "routed": routed,
        "reroutes": reroutes,
    }


def nav_epoch(net, routes, pos, insert, arrive, is_nav, q, occ, capnow, nav):
    """Epoch-based en-route patching, the form a GPU world could execute: pause, read positions, patch suffixes."""
    nl = net.nl
    tnow = [max(net.ff[l], occ[l] / max(capnow[l] / DT, 1e-3)) for l in range(nl)]
    trees = {}
    changed = 0
    for l in range(nl):
        for i in q[l]:
            if not is_nav[i]:
                continue
            r = routes[i]
            k = pos[i]
            if k >= len(r) - 1:
                continue
            node = net.to[r[k]]
            dest = net.to[r[-1]]
            cur = sum(tnow[x] for x in r[k + 1:])
            tree = trees.get(dest)
            if tree is None:
                tree = reverse_tree(net, dest, tnow)
                trees[dest] = tree
            best = tree[0][node]
            if cur - best > max(nav["min_saving"], nav["min_rel"] * cur):
                suffix = []
                nd = int(node)
                nh = tree[1]
                while nd != dest:
                    x = nh[nd]
                    suffix.append(x)
                    nd = int(net.to[x])
                routes[i] = r[: k + 1] + suffix
                changed += 1
    return changed


def reverse_tree(net, dest, tnow):
    dist = [INF] * net.nn
    nxt = [-1] * net.nn
    dist[dest] = 0.0
    h = [(0.0, int(dest))]
    fr = net.fr
    while h:
        d, u = heapq.heappop(h)
        if d > dist[u]:
            continue
        for l in net.inn[u]:
            v = fr[l]
            nd = d + tnow[l]
            if nd < dist[v]:
                dist[v] = nd
                nxt[v] = l
                heapq.heappush(h, (nd, int(v)))
    return dist, nxt


def cost_table(net, res, horizon=21600.0, estimator="queue"):
    """Time-dependent link cost per bin from aggregate counters only. E0 compares three estimators."""
    nl = net.nl
    nb = res["ent"].shape[1]
    tt = np.tile(net.ff[:, None], (1, nb))
    if estimator == "littles":
        # Vehicle-seconds over vehicles leaving in the same bin: the sumo edgeData shape of estimate.
        lft = res["lft"]
        vs = res["vs"]
        with np.errstate(divide="ignore", invalid="ignore"):
            est = np.where(lft > 0, vs / lft, net.ff[:, None])
        return np.maximum(tt, est), entry_wait(net, res, horizon)
    edges = BIN * np.arange(nb + 1)
    if estimator == "queue":
        # Vertical queue at each bin midpoint, drained at the larger of observed outflow and nominal capacity.
        cin = np.concatenate([np.zeros((nl, 1)), np.cumsum(res["ent"], axis=1)], axis=1)
        cout = np.concatenate([np.zeros((nl, 1)), np.cumsum(res["lft"], axis=1)], axis=1)
        mids = edges[:-1] + BIN / 2
        for l in range(nl):
            if cin[l, -1] == 0:
                continue
            ffl = net.ff[l]
            q = np.maximum(0.0, np.interp(mids - ffl, edges, cin[l]) - np.interp(mids, edges, cout[l]))
            rate = np.maximum(res["lft"][l] / BIN, 0.25 * net.cap[l])
            tt[l] = ffl + q / rate
        return tt, entry_wait(net, res, horizon)
    for l in range(nl):
        cin = np.concatenate([[0.0], np.cumsum(res["ent"][l])])
        cout = np.concatenate([[0.0], np.cumsum(res["lft"][l])])
        if cin[-1] == 0:
            continue
        mid_c = 0.5 * (cin[:-1] + cin[1:])
        mid_t = edges[:-1] + BIN / 2
        # Index of the first time the outflow curve reaches the cohort's cumulative position.
        idx = np.searchsorted(cout, mid_c, side="left")
        out_t = np.full(nb, np.nan)
        ok = idx <= nb
        rise = np.maximum(cout[np.minimum(idx, nb)] - cout[np.maximum(idx - 1, 0)], 1e-9)
        frac = (mid_c - cout[np.maximum(idx - 1, 0)]) / rise
        out_t[ok] = edges[np.maximum(idx - 1, 0)[ok]] + frac[ok] * BIN
        censored = ~ok | (cout[-1] < mid_c)
        remaining = np.maximum(mid_c - cout[-1], 0.0) / net.cap[l]
        out_t = np.where(censored, res["end"] + remaining, out_t)
        tt[l] = np.maximum(net.ff[l], out_t - mid_t)
    return tt, entry_wait(net, res, horizon)


def entry_wait(net, res, horizon):
    """Insertion delay per link and bin, the part of the journey a teleport-free ledger must not drop."""
    nl = net.nl
    nb = res["req"].shape[1]
    w = np.zeros((nl, nb))
    edges = BIN * np.arange(nb + 1)
    for l in np.nonzero(res["req"].sum(axis=1))[0]:
        creq = np.concatenate([[0.0], np.cumsum(res["req"][l])])
        cins = np.concatenate([[0.0], np.cumsum(res["ins"][l])])
        mid_c = 0.5 * (creq[:-1] + creq[1:])
        idx = np.searchsorted(cins, mid_c, side="left")
        ok = idx <= nb
        rise = np.maximum(cins[np.minimum(idx, nb)] - cins[np.maximum(idx - 1, 0)], 1e-9)
        frac = (mid_c - cins[np.maximum(idx - 1, 0)]) / rise
        t = np.where(ok, edges[np.maximum(idx - 1, 0)] + frac * BIN, res["end"])
        w[l] = np.maximum(0.0, t - (edges[:-1] + BIN / 2))
    return w


class Router:
    """Time-dependent shortest paths: one forward tree per (origin, departure bin), reused for all destinations."""

    def __init__(self, net, tt, wait=None):
        self.net = net
        self.tt = tt.tolist()
        self.wait = wait.tolist() if wait is not None else None
        self.nb = tt.shape[1]
        self.to = net.to.tolist()
        self.cache = {}
        self.calls = 0

    def tree(self, origin, b):
        key = (origin, b)
        tree = self.cache.get(key)
        if tree is not None:
            return tree
        self.calls += 1
        net, tt, nb, to = self.net, self.tt, self.nb, self.to
        t0 = (b + 0.5) * ROUTE_BIN
        lab = [INF] * net.nn
        pred = [-1] * net.nn
        lab[origin] = t0
        h = [(t0, origin)]
        first = True
        while h:
            d, u = heapq.heappop(h)
            if d > lab[u]:
                continue
            for l in net.out[u]:
                c = tt[l][min(int(d // BIN), nb - 1)]
                if first and self.wait is not None:
                    c += self.wait[l][min(int(d // BIN), nb - 1)]
                nd = d + c
                v = to[l]
                if nd < lab[v]:
                    lab[v] = nd
                    pred[v] = l
                    heapq.heappush(h, (nd, v))
            first = False
        self.cache[key] = (lab, pred)
        return lab, pred

    def path(self, origin, dest, b):
        lab, pred = self.tree(origin, b)
        if lab[dest] >= INF:
            return [], INF
        p = []
        n = dest
        while n != origin:
            l = pred[n]
            p.append(l)
            n = int(self.net.fr[l])
        p.reverse()
        return p, lab[dest] - (b + 0.5) * ROUTE_BIN

    def eval_route(self, route, b):
        t = (b + 0.5) * ROUTE_BIN
        t0 = t
        tt, nb = self.tt, self.nb
        for j, l in enumerate(route):
            k = min(int(t // BIN), nb - 1)
            t += tt[l][k]
            if j == 0 and self.wait is not None:
                t += self.wait[l][k]
        return t - t0


def freeflow_routes(net, dem):
    nb = 8
    tt = np.tile(net.ff[:, None], (1, nb))
    rt = Router(net, tt)
    return [rt.path(int(o), int(d), 0)[0] for o, d in zip(dem.o, dem.d)]


def dep_bin(dep):
    return np.minimum((dep // ROUTE_BIN).astype(int), 35)


def gap_and_costs(rt, dem, routes, dep=None):
    bins = dep_bin(dem.dep if dep is None else dep)
    cur = np.zeros(dem.n)
    best = np.zeros(dem.n)
    for i in range(dem.n):
        r = routes[i]
        if not r:
            continue
        b = int(bins[i])
        lab, _ = rt.tree(int(dem.o[i]), b)
        best[i] = lab[int(dem.d[i])] - (b + 0.5) * ROUTE_BIN
        cur[i] = rt.eval_route(r, b)
    tot = cur.sum()
    return (cur - best).sum() / max(tot, 1.0), cur, best


def update_routes(rt, dem, routes, cur, best, policy, k, rng, dep=None, memory=None, theta=0.05):
    bins = dep_bin(dem.dep if dep is None else dep)
    n = dem.n
    u = rng.random(n)
    if policy == "aon":
        sw = np.ones(n, bool)
    elif policy == "fixed10":
        sw = u < 0.10
    elif policy == "msa":
        sw = u < 1.0 / (k + 2)
    elif policy == "gapprop":
        rel = (cur - best) / np.maximum(cur, 1.0)
        sw = u < np.minimum(1.0, 2.0 * rel)
    elif policy == "gapcap":
        rel = (cur - best) / np.maximum(cur, 1.0)
        sw = u < np.minimum(0.15, 2.0 * rel)
    elif policy == "gapdecay":
        rel = (cur - best) / np.maximum(cur, 1.0)
        sw = u < np.minimum(0.25 / (1.0 + k / 5.0), 2.0 * rel)
    elif policy == "bounded":
        saving = cur - best
        sw = (u < 0.2) & (saving > np.maximum(30.0, 0.05 * cur))
    elif policy == "logit":
        # Remembered routes and a logit choice, the shape of SUMO's duaIterate without its code.
        sw = np.zeros(n, bool)
        new = list(routes)
        for i in range(n):
            mem = memory[i]
            b = int(bins[i])
            p, _ = rt.path(int(dem.o[i]), int(dem.d[i]), b)
            if p and p not in mem:
                mem.append(p)
                if len(mem) > 5:
                    mem.pop(0)
            if u[i] < 0.5 or not mem:
                continue
            c = np.array([rt.eval_route(m, b) for m in mem])
            pr = np.exp(-theta * (c - c.min()))
            new[i] = mem[int(rng.choice(len(mem), p=pr / pr.sum()))]
        return new, int(sum(1 for i in range(n) if new[i] is not routes[i]))
    else:
        raise ValueError(policy)
    new = list(routes)
    for i in np.nonzero(sw)[0]:
        p, _ = rt.path(int(dem.o[i]), int(dem.d[i]), int(bins[i]))
        if p:
            new[i] = p
    return new, int(sw.sum())


def experience(dem, res, horizon=21600.0):
    arr, plan = res["arrive"], res["planned"]
    done = ~np.isnan(arr)
    unfinished = int((~done & res["routed"]).sum())
    # Censored trips are charged their time so far, so a stuck trip can never look fast.
    tt = np.where(done, arr - plan, res["end"] - plan)
    return {
        "unfinished": unfinished, "unfinished_share": unfinished / max(dem.n, 1), "mean_tt_s": float(tt.mean()),
        "p95_tt_s": float(np.percentile(tt, 95)), "teleports": int(res["teleports"]),
        "teleported_trips": int(res["teleported_trip"].sum()), "end_s": float(res["end"]), "fail": res["fail"],
        "max_insert_wait_s": float(np.nanmax(res["insert"] - plan)) if np.any(~np.isnan(res["insert"])) else None,
    }


def assign(net, dem, iters, policy="gapcap", seed=0, replicas=1, routes=None, teleport=None, memory_w=0.3,
           estimator="queue", horizon=21600.0, log=True, stop_gap=None, dep=None):
    """The core loop: simulate, build costs, measure gap, update a share of travellers, repeat."""
    rng = np.random.default_rng(seed)
    routes = list(freeflow_routes(net, dem) if routes is None else routes)
    memory = [[r] for r in routes] if policy == "logit" else None
    hist = []
    table = None
    wait_tab = None
    for k in range(iters):
        t0 = time.time()
        results = [simulate(net, dem, routes, seed=seed * 1000 + k * 37 + j, teleport=teleport, horizon=horizon,
                            dep_override=dep) for j in range(replicas)]
        tabs = [cost_table(net, r, horizon=horizon, estimator=estimator) for r in results]
        tt = np.mean([t[0] for t in tabs], axis=0)
        wt = np.mean([t[1] for t in tabs], axis=0)
        if table is None or memory_w >= 1.0:
            table, wait_tab = tt, wt
        else:
            table = (1 - memory_w) * table + memory_w * tt
            wait_tab = (1 - memory_w) * wait_tab + memory_w * wt
        rt = Router(net, table, wait_tab)
        gap, cur, best = gap_and_costs(rt, dem, routes, dep)
        routes, nsw = update_routes(rt, dem, routes, cur, best, policy, k, rng, dep, memory)
        ex = experience(dem, results[0], horizon)
        ex.update(iter=k, gap=float(gap), switched=nsw, wall_s=time.time() - t0, trees=rt.calls)
        hist.append(ex)
        if log:
            print(f"  it {k:3d} gap {gap:.4f} tt {ex['mean_tt_s']:7.1f} p95 {ex['p95_tt_s']:7.0f} unfin {ex['unfinished']:5d} "
                  f"sw {nsw:5d} wall {ex['wall_s']:.2f}s", flush=True)
        if stop_gap is not None and gap < stop_gap and k >= 3:
            break
    return routes, hist, table, wait_tab


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump(obj, f, indent=1, default=float)
    print("wrote", name)


def indep_gap(net, dem, routes, seeds=(9001, 9002, 9003, 9004)):
    """Gap of a fixed route set against a cost table averaged over seeds unseen by the algorithm."""
    ress = [simulate(net, dem, routes, seed=s) for s in seeds]
    tabs = [cost_table(net, r) for r in ress]
    rt = Router(net, np.mean([t[0] for t in tabs], axis=0), np.mean([t[1] for t in tabs], axis=0))
    g, _, _ = gap_and_costs(rt, dem, routes)
    ex = [experience(dem, r) for r in ress]
    return {"gap": float(g), "mean_tt_s": float(np.mean([e["mean_tt_s"] for e in ex])),
            "tt_sd_between_seeds": float(np.std([e["mean_tt_s"] for e in ex])),
            "unfinished": float(np.mean([e["unfinished"] for e in ex]))}


# E0: which aggregate estimator predicts experienced trip times? Decides what the GPU must output.
def e0(a):
    out = {}
    for scale in (1.0, 2.0, 3.0):
        rng = np.random.default_rng(1)
        net = Net(NET_N)
        dem = make_demand(net, int(BASE_TRIPS * scale), rng)
        routes, _, _, _ = assign(net, dem, 8, "gapcap", log=False)
        res = simulate(net, dem, routes, seed=5)
        actual = res["arrive"] - res["planned"]
        ok = ~np.isnan(actual)
        out[str(scale)] = {"mean_actual_s": float(actual[ok].mean()), "finished_share": float(ok.mean())}
        for est in ("cumulative", "queue", "littles"):
            tt, wt = cost_table(net, res, estimator=est)
            rt = Router(net, tt, wt)
            pred = np.array([rt.eval_route(routes[i], res["planned"][i] / ROUTE_BIN - 0.5) if routes[i] else np.nan
                             for i in range(dem.n)])
            e = pred[ok] - actual[ok]
            m = ~np.isnan(e)
            out[str(scale)][est] = {"bias_s": float(e[m].mean()), "mae_s": float(np.abs(e[m]).mean()),
                                    "corr": float(np.corrcoef(pred[ok][m], actual[ok][m])[0, 1])}
        print(scale, out[str(scale)], flush=True)
    save("E0_cost_estimator", out)


# E1: which update rule converges at a load where the network is actually congested?
def e1(a):
    iters = a.iters
    trips = int(BASE_TRIPS * a.scale)
    name = f"E1_update_rule_s{a.scale}_{a.tag}"
    out = {"net": f"{NET_N}x{NET_N}", "trips": trips, "iters": iters, "policies": {}}
    for spec in a.policies.split(","):
        pol, _, mem = spec.partition(":")
        mem = float(mem) if mem else 1.0
        key = f"{pol}:{mem}"
        out["policies"][key] = {}
        for seed in range(a.seeds):
            rng = np.random.default_rng(100 + seed)
            net = Net(NET_N)
            dem = make_demand(net, trips, rng)
            routes, hist, _, _ = assign(net, dem, iters, pol, seed=seed, memory_w=mem, log=False)
            fin = indep_gap(net, dem, routes)
            out["policies"][key][seed] = {
                "gap": [h["gap"] for h in hist], "mean_tt": [h["mean_tt_s"] for h in hist], "unfinished": [h["unfinished"] for h in hist],
                "switched": [h["switched"] for h in hist], "final_indep": fin,
                "wall_per_iter_s": float(np.mean([h["wall_s"] for h in hist])),
            }
            print(key, seed, "gap", [round(h["gap"], 3) for h in hist[:: max(1, iters // 6)]], "final", {k: round(v, 3) for k, v in fin.items()},
                  round(out["policies"][key][seed]["wall_per_iter_s"], 1), flush=True)
            save(name, out)


# E2: for a fixed simulation budget, are replicas per iteration better than more iterations?
def e2(a):
    budget = 48
    out = {"budget_sim_days": budget, "runs": {}}
    trips = int(BASE_TRIPS * a.scale)
    for spec in a.reps.split(","):
        k_rep, iters = map(int, spec.split("x"))
        rows = []
        for seed in range(2):
            rng = np.random.default_rng(200 + seed)
            net = Net(NET_N)
            dem = make_demand(net, trips, rng)
            routes, hist, _, _ = assign(net, dem, iters, "gapcap", seed=seed, replicas=k_rep, log=False)
            fin = indep_gap(net, dem, routes)
            rows.append({"seed": seed, "final": fin, "gap_trace": [h["gap"] for h in hist]})
            print(k_rep, iters, fin, flush=True)
            out["runs"][f"{k_rep}x{iters}"] = rows
            save(f"E2_replicas_s{a.scale}_{a.tag}", out)


# E3: why does a simulated city gridlock? Scale demand under each level of adaptation, with and without teleports.
def e3(a):
    out = {"net": f"{NET_N}x{NET_N}", "base_trips": BASE_TRIPS, "rows": []}
    scales = [float(x) for x in a.scales.split(",")]
    tag = a.tag
    for s in scales:
        rng = np.random.default_rng(300)
        net = Net(NET_N)
        trips = int(BASE_TRIPS * s)
        dem = make_demand(net, trips, rng)
        ffr = freeflow_routes(net, dem)
        row = {"scale": s, "trips": trips}
        row["freeflow_noteleport"] = experience(dem, simulate(net, dem, ffr, seed=1))
        row["freeflow_teleport300"] = experience(dem, simulate(net, dem, ffr, seed=1, teleport=300.0))
        routes, hist, _, _ = assign(net, dem, 15, "gapcap", seed=3, log=False)
        row["assigned_noteleport"] = experience(dem, simulate(net, dem, routes, seed=1))
        row["assigned_teleport300"] = experience(dem, simulate(net, dem, routes, seed=1, teleport=300.0))
        row["assigned_gap"] = hist[-1]["gap"]
        row["gap_trace"] = [h["gap"] for h in hist]
        out["rows"].append(row)
        print(s, {k: (row[k]["unfinished"], round(row[k]["mean_tt_s"]), row[k]["teleports"]) for k in row if isinstance(row[k], dict)},
              "gap", round(row["assigned_gap"], 3), flush=True)
        save(f"E3_gridlock_{tag}", out)


def depart_step(rt, dem, routes, dep, rng, alpha, beta, gamma, shift=900.0, frac=0.15, tol=30.0):
    """Let a share of travellers try one bin earlier or later, on generalised schedule cost."""
    newdep = dep.copy()
    newroutes = list(routes)
    changed = 0
    earliest = dem.tstar - 3600.0
    latest = dem.tstar + 900.0
    for i in np.nonzero(rng.random(dem.n) < frac)[0]:
        o, d, ts = int(dem.o[i]), int(dem.d[i]), dem.tstar[i]
        bestc, bestt, bestp = None, None, None
        for off in (0.0, -shift, shift):
            t = dep[i] + off
            if t < 0 or t < earliest[i] or t > latest[i]:
                continue
            b = int(min(t // ROUTE_BIN, 35))
            p, tt = rt.path(o, d, b)
            if not p:
                continue
            arr = t + tt
            c = alpha * tt + beta * max(0.0, ts - arr) + gamma * max(0.0, arr - ts)
            if off == 0.0:
                c0 = c
            if bestc is None or c < bestc:
                bestc, bestt, bestp = c, t, p
        if bestt is not None and bestt != dep[i] and bestc < c0 - tol:
            newdep[i] = bestt
            newroutes[i] = bestp
            changed += 1
    return newroutes, newdep, changed


def schedule_cost(dem, res, alpha, beta, gamma):
    arr = res["arrive"]
    plan = res["planned"]
    a = np.where(np.isnan(arr), res["end"], arr)
    tt = a - plan
    return float(np.mean(alpha * tt + beta * np.maximum(0, dem.tstar - a) + gamma * np.maximum(0, a - dem.tstar)))


# E4: departure-time adaptation at the demand level where route choice alone stops being enough.
def e4(a):
    out = {"rows": []}
    alpha, beta, gamma = 1.0, a.beta, a.gamma
    for s in [float(x) for x in a.scales.split(",")]:
        rng = np.random.default_rng(400)
        net = Net(NET_N)
        trips = int(BASE_TRIPS * s)
        dem = make_demand(net, trips, rng)
        routes, hist, table, wt = assign(net, dem, 12, "gapcap", seed=4, log=False)
        res0 = simulate(net, dem, routes, seed=7)
        before = experience(dem, res0)
        # Control: the same number of further iterations with routes only.
        rctl, hctl, _, _ = assign(net, dem, 15, "gapcap", seed=44, routes=routes, log=False)
        res_ctl = simulate(net, dem, rctl, seed=7)
        route_only = experience(dem, res_ctl)
        hist_dep0 = np.histogram(dem.dep, bins=np.arange(0, 14401, 900))[0].tolist()
        dep = dem.dep.copy()
        if a.reinit:
            # Start from a schedule consistent with experienced times, instead of a fixed lead on every trip.
            res_i = res_ctl
            tt_i = np.where(np.isnan(res_i["arrive"]), res_i["end"], res_i["arrive"]) - res_i["planned"]
            dep = np.clip(dem.tstar - tt_i, 0, None)
            routes = rctl
        trace = []
        rngd = np.random.default_rng(41)
        for k in range(15):
            res = simulate(net, dem, routes, seed=500 + k, dep_override=dep)
            tt, w = cost_table(net, res)
            rt = Router(net, tt, w)
            g, cur, best = gap_and_costs(rt, dem, routes, dep)
            routes, _ = update_routes(rt, dem, routes, cur, best, "gapcap", k, rngd, dep)
            routes, dep, ch = depart_step(rt, dem, routes, dep, rngd, alpha, beta, gamma, shift=a.shift, frac=a.depfrac)
            ex = experience(dem, res)
            trace.append({"iter": k, "gap": float(g), "shifted": ch, "mean_tt": ex["mean_tt_s"], "unfinished": ex["unfinished"],
                          "sched_cost": schedule_cost(dem, res, alpha, beta, gamma)})
        resf = simulate(net, dem, routes, seed=7, dep_override=dep)
        after = experience(dem, resf)
        hist_dep1 = np.histogram(dep, bins=np.arange(0, 14401, 900))[0].tolist()
        move = np.abs(dep - dem.dep)
        out["rows"].append({"scale": s, "trips": trips, "before": before, "route_only": route_only, "after": after,
                            "sched_route_only": schedule_cost(dem, res_ctl, alpha, beta, gamma), "dep_hist_before": hist_dep0,
                            "dep_hist_after": hist_dep1, "share_moved": float((move > 0).mean()),
                            "mean_abs_shift_min": float(move[move > 0].mean() / 60) if (move > 0).any() else 0.0,
                            "share_within_15min": float((move <= 900).mean()),
                            "share_at_window_edge": float(((dep <= dem.tstar - 3599) | (dep >= dem.tstar + 899)).mean()),
                            "peak_dep_before": max(hist_dep0), "peak_dep_after": max(hist_dep1),
                            "sched_before": schedule_cost(dem, res0, alpha, beta, gamma),
                            "sched_after": schedule_cost(dem, resf, alpha, beta, gamma), "trace": trace})
        r = out["rows"][-1]
        print(s, "before", before["unfinished"], round(before["mean_tt_s"]), "route_only", route_only["unfinished"], round(route_only["mean_tt_s"]),
              "route+dep", after["unfinished"], round(after["mean_tt_s"]), "moved", round(r["share_moved"], 3), "meanshift_min", round(r["mean_abs_shift_min"], 1),
              "within15", round(r["share_within_15min"], 3), "edge", round(r["share_at_window_edge"], 3), "peak", r["peak_dep_before"], r["peak_dep_after"],
              "sched", round(r["sched_route_only"]), round(r["sched_after"]), flush=True)
        save(f"E4_departure_time_{a.tag}", {"alpha": alpha, "beta": beta, "gamma": gamma, "shift_s": a.shift, **out})


def zonal(net, dem, zdiv=2, tbin=1800.0, nt=7):
    z = net.nzones(zdiv)
    zo = np.array([net.zone(int(x), zdiv) for x in dem.o])
    zd = np.array([net.zone(int(x), zdiv) for x in dem.d])
    tb = np.minimum((dem.tstar // tbin).astype(int), nt - 1)
    return (zo * z + zd) * nt + tb, z * z * nt


def counts_matrix(net, res, tbins=12, tb=900.0):
    ent = res["ent"]
    per = int(tb // BIN)
    return np.stack([ent[:, i * per:(i + 1) * per].sum(axis=1) for i in range(tbins)], axis=1)


def assignment_matrix(net, dem, routes, res, cells, ncells, tbins=12, tb=900.0):
    """Link-time passes per OD-time cell from the actual simulated run: the sparse A in y = A q."""
    rows, cols = [], []
    bin_tt = cost_table(net, res)[0].tolist()
    nb = len(bin_tt[0])
    for i in range(dem.n):
        r = routes[i]
        if not r:
            continue
        t = res["planned"][i]
        for l in r:
            k = int(t // tb)
            if k < tbins:
                rows.append(l * tbins + k)
                cols.append(cells[i])
            t += bin_tt[l][min(int(t // BIN), nb - 1)]
    data = np.ones(len(rows))
    return sp.csr_matrix((data, (rows, cols)), shape=(net.nl * tbins, ncells))


def sample_from_cells(net, q, rng, zdiv, tbin=1800.0, nt=7):
    """Draw travellers from an OD-time cell table using a node-level pick inside each zone."""
    q = np.maximum(q, 0)
    k = rng.poisson(q)
    idx = np.repeat(np.arange(q.size), k)
    z = net.nzones(zdiv)
    tcell = idx % nt
    od = idx // nt
    zo, zd = np.divmod(od, z)
    nodes_by_zone = [[] for _ in range(z)]
    for n in range(net.nn):
        nodes_by_zone[net.zone(n, zdiv)].append(n)
    o = np.array([rng.choice(nodes_by_zone[int(x)]) for x in zo], dtype=int)
    d = np.array([rng.choice(nodes_by_zone[int(x)]) for x in zd], dtype=int)
    keep = o != d
    tstar = (tcell[keep] + rng.random(keep.sum())) * tbin
    dep = np.clip(tstar - 600, 0, None)
    return Demand(o[keep], d[keep], tstar, dep)


def factor_fit(A, y, q0, train, grid, lam, sweeps=200):
    """Low-dimensional fit: q = q0 * f_origin * f_dest * f_time, log factors with a pull back to one."""
    z, nt = grid
    nc = q0.size
    idx = np.arange(nc)
    t = idx % nt
    zo, zd = np.divmod(idx // nt, z)
    fo, fd, ft = np.ones(z), np.ones(z), np.ones(nt)
    Atr = A[train]
    ytr = y[train]
    for _ in range(sweeps):
        q = q0 * fo[zo] * fd[zd] * ft[t]
        pred = Atr @ q
        ratio = (ytr + 1) / (pred + 1)
        g = Atr.T @ ratio
        norm = Atr.T @ np.ones_like(ytr)
        with np.errstate(divide="ignore", invalid="ignore"):
            m = np.where(norm > 0, g / norm, 1.0)
        lm = np.log(np.maximum(m, 1e-6))
        w = q0 * norm
        for arr, key, n in ((fo, zo, z), (fd, zd, z), (ft, t, nt)):
            sw = np.bincount(key, weights=w, minlength=n)
            step = np.bincount(key, weights=w * lm, minlength=n) / np.maximum(sw + lam, 1e-9)
            arr *= np.exp(np.clip(0.5 * step, -0.3, 0.3))
            arr[:] = np.clip(arr, 0.33, 3.0)
    return q0 * fo[zo] * fd[zd] * ft[t], {"fo_range": [float(fo.min()), float(fo.max())], "fd_range": [float(fd.min()), float(fd.max())]}


def cell_fit(A, y, q0, train, lam, sweeps=200):
    """Per-OD-cell multiplicative fit; lam=0 is what the Stockholm generator does in spirit, lam>0 a pull to the prior."""
    Atr = A[train]
    ytr = y[train]
    q = q0.copy() + 1e-6
    norm = np.asarray(Atr.T @ np.ones_like(ytr)).ravel()
    for _ in range(sweeps):
        pred = Atr @ q
        ratio = (ytr + 1e-3) / (pred + 1e-3)
        g = Atr.T @ ratio
        with np.errstate(divide="ignore", invalid="ignore"):
            m = np.where(norm > 0, g / norm, 1.0)
        if lam > 0:
            m = (m * norm + lam * (q0 + 1e-6) / q) / (norm + lam)
        q = q * np.maximum(m, 1e-3)
    return q


def metrics_od(q, qtrue, net, zdiv, nt=7):
    pos = (qtrue > 0) | (q > 0.5)
    # Compare at day level (zone pair) as well as OD-time cell level.
    z = net.nzones(zdiv)
    day = q.reshape(z * z, nt).sum(axis=1)
    dayt = qtrue.reshape(z * z, nt).sum(axis=1)
    return {
        "total_ratio": float(q.sum() / qtrue.sum()),
        "cell_rmse_rel_mean": float(np.sqrt(np.mean((q[pos] - qtrue[pos]) ** 2)) / max(qtrue[pos].mean(), 1e-9)),
        "pair_rmse_rel_mean": float(np.sqrt(np.mean((day - dayt) ** 2)) / max(dayt.mean(), 1e-9)),
        "pair_corr": float(np.corrcoef(day, dayt)[0, 1]),
    }


def wape(a, b):
    return float(np.abs(a - b).sum() / max(b.sum(), 1.0))


# E5: how well can OD be recovered from counts? Known synthetic truth, held-out links, several priors and coverages.
def e5(a):
    zdiv, nt = 2, 7
    net = Net(8)
    z = net.nzones(zdiv)
    rng = np.random.default_rng(500)
    w = gravity_weights(net)
    # Truth: gravity plus unmodelled lognormal structure on zone pairs and times.
    base = make_demand(net, 8000, rng, w)
    cells, nc = zonal(net, base, zdiv)
    qg = np.bincount(cells, minlength=nc).astype(float)
    pair_noise = np.exp(rng.normal(0, 0.6, z * z))
    qtrue = qg * np.repeat(pair_noise, nt)
    qtrue *= 8000 / qtrue.sum()
    dem_true = sample_from_cells(net, qtrue, rng, zdiv)
    routes_true, _, _, _ = assign(net, dem_true, 10, "gapcap", seed=5, log=False)
    res_true = simulate(net, dem_true, routes_true, seed=11)
    tb = 12
    yfull = counts_matrix(net, res_true, tb).ravel().astype(float)
    # Observations carry one noisy day, the truth table is the expectation.
    priors = {
        "gravity_right_total": qg * (8000 / qg.sum()),
        "gravity_30pct_high": qg * (8000 / qg.sum()) * 1.3,
        "uniform_right_total": np.full(nc, 8000 / nc),
    }
    for name in list(priors):
        priors[name] = priors[name] * (qg > 0) if name != "uniform_right_total" else priors[name]
    # A small probe panel: a random sample of real trips, combined with the gravity prior as a pseudo-count of 2%.
    cells_t, _ = zonal(net, dem_true, zdiv)
    g = qg * (8000 / qg.sum())
    for share in (0.02, 0.10):
        s = np.random.default_rng(int(share * 1000)).random(dem_true.n) < share
        panel = np.bincount(cells_t[s], minlength=nc).astype(float)
        kappa = 0.02
        priors[f"probe_{int(share*100)}pct_plus_gravity"] = (panel + kappa * g) / (share + kappa)
    # Noise floor: what the same truth scores against itself on another seed, and on another sampled day.
    ydiff = counts_matrix(net, simulate(net, dem_true, routes_true, seed=12), tb).ravel().astype(float)
    dem_day2 = sample_from_cells(net, qtrue, np.random.default_rng(77), zdiv)
    routes_day2, _, _, _ = assign(net, dem_day2, 10, "gapcap", seed=5, log=False)
    yday2 = counts_matrix(net, simulate(net, dem_day2, routes_day2, seed=13), tb).ravel().astype(float)
    out = {"truth_trips": dem_true.n, "cells": nc, "tbins": tb, "links": net.nl, "rows": [],
           "noise_floor_wape_other_seed": wape(ydiff, yfull), "noise_floor_wape_other_day": wape(yday2, yfull)}
    print("noise floor", out["noise_floor_wape_other_seed"], out["noise_floor_wape_other_day"], flush=True)
    wanted = a.priors.split(",") if a.priors else list(priors)
    coverages = (0.1, 0.3, 0.6)
    perm = np.random.default_rng(55).permutation(net.nl)
    hold_links = perm[: net.nl // 4]
    rest = perm[net.nl // 4:]
    hold = np.isin(np.repeat(np.arange(net.nl), tb), hold_links)
    for name, q0 in priors.items():
        if name not in wanted:
            continue
        for cov in coverages:
            tl = rest[: int(cov * net.nl)]
            train = np.isin(np.repeat(np.arange(net.nl), tb), tl)
            for method in ("none", "cell_lam0", "cell_prior", "factors"):
                q = q0.copy()
                dem = sample_from_cells(net, q, np.random.default_rng(1), zdiv)
                routes, _, _, _ = assign(net, dem, 6, "gapcap", seed=6, log=False)
                info = {}
                outer = 1 if method == "none" else 3
                for ou in range(outer):
                    res = simulate(net, dem, routes, seed=20 + ou)
                    cells_i, _ = zonal(net, dem, zdiv)
                    Araw = assignment_matrix(net, dem, routes, res, cells_i, nc, tb)
                    denom = np.maximum(np.bincount(cells_i, minlength=nc).astype(float), 1.0)
                    A = (Araw @ sp.diags(1.0 / denom)).tocsr()
                    if method == "none":
                        qn = q
                    elif method == "cell_lam0":
                        qn = cell_fit(A, yfull, q, train, 0.0)
                    elif method == "cell_prior":
                        qn = cell_fit(A, yfull, q, train, 0.5)
                    else:
                        qn, info = factor_fit(A, yfull, q, train, (z, nt), 5.0)
                    if method != "none":
                        q = 0.5 * q + 0.5 * qn
                        dem = sample_from_cells(net, q, np.random.default_rng(2 + ou), zdiv)
                        routes, _, _, _ = assign(net, dem, 3, "gapcap", seed=7 + ou, log=False)
                resf = simulate(net, dem, routes, seed=99)
                y = counts_matrix(net, resf, tb).ravel().astype(float)
                vkt = float(sum(len(r) for r in routes) * 0.4)
                vkt_t = float(sum(len(r) for r in routes_true) * 0.4)
                row = {"prior": name, "coverage": cov, "method": method, "train_wape": wape(y[train], yfull[train]),
                       "heldout_wape": wape(y[hold], yfull[hold]), "vkt_ratio": vkt / vkt_t, **metrics_od(q, qtrue, net, zdiv), **info}
                out["rows"].append(row)
                print(name, cov, method, {k: round(v, 3) for k, v in row.items() if isinstance(v, float)}, flush=True)
            save(f"E5_od_from_counts_{a.tag}", out)


# E6: can impossible demand be told apart from a bad assignment before and after simulating?
def e6(a):
    out = {"rows": []}
    for bridges, label in (((1, 4, 7), "3 bridges"), ((1,), "1 bridge"), (None, "no river")):
        net = Net(8, bridges=bridges)
        for trips in (4000, 8000, 12000, 16000):
            rng = np.random.default_rng(600)
            w = gravity_weights(net, cross_bias=1.0)
            dem = make_demand(net, trips, rng, w)
            window = 7200.0
            in_win = np.abs(dem.tstar - 4500.0) <= window / 2
            # Two necessary conditions: single-commodity max flow, and demand against capacity across a named cut.
            unmet = flow_bound(net, dem, in_win, window)
            routes, hist, _, _ = assign(net, dem, 12, "gapcap", seed=6, log=False)
            res = simulate(net, dem, routes, seed=3)
            ex = experience(dem, res)
            cut = cut_bound(net, dem, in_win, window) if bridges is not None else None
            row = {"net": label, "trips": trips, "window_trips": int(in_win.sum()), "maxflow_unmet": unmet, "cut": cut,
                   "gap_final": hist[-1]["gap"], "unfinished": ex["unfinished"], "mean_tt_s": ex["mean_tt_s"], "p95_tt_s": ex["p95_tt_s"],
                   "end_s": ex["end_s"], "fail": ex["fail"], "gap_trace": [h["gap"] for h in hist]}
            out["rows"].append(row)
            print(label, trips, "unmet", unmet, "cut", cut, "unfinished", ex["unfinished"], "tt", round(ex["mean_tt_s"]), flush=True)
            save("E6_impossible_demand", out)


def flow_bound(net, dem, mask, window):
    """Trips in the window minus single-commodity max flow. E6 shows this relaxation is too weak to rely on."""
    n = net.nn
    S, T = n * 2, n * 2 + 1
    rows, cols, caps = [], [], []
    # Split nodes so a trip cannot be credited twice: source -> origin copy, destination copy -> sink.
    o = np.bincount(dem.o[mask], minlength=n)
    d = np.bincount(dem.d[mask], minlength=n)
    for l in range(net.nl):
        rows.append(int(net.fr[l]))
        cols.append(int(net.to[l]))
        caps.append(int(net.cap[l] * window))
    for i in range(n):
        if o[i]:
            rows.append(S)
            cols.append(i)
            caps.append(int(o[i]))
        if d[i]:
            rows.append(i)
            cols.append(T)
            caps.append(int(d[i]))
    m = sp.csr_matrix((np.array(caps, dtype=np.int32), (rows, cols)), shape=(2 * n + 2, 2 * n + 2))
    flow = maximum_flow(m, S, T).flow_value
    return int(mask.sum() - flow)


def cut_bound(net, dem, mask, window):
    n = net.n
    rr = dem.o // n
    rd = dem.d // n
    north_south = (rr < n // 2) & (rd >= n // 2) & mask
    south_north = (rr >= n // 2) & (rd < n // 2) & mask
    fr_r = net.fr // n
    to_r = net.to // n
    capns = float(net.cap[(fr_r < n // 2) & (to_r >= n // 2)].sum() * window)
    capsn = float(net.cap[(fr_r >= n // 2) & (to_r < n // 2)].sum() * window)
    return {"n_to_s": int(north_south.sum()), "cap_n_to_s": capns, "s_to_n": int(south_north.sum()), "cap_s_to_n": capsn,
            "unmet": max(0, int(north_south.sum() - capns)) + max(0, int(south_north.sum() - capsn))}


# E7: en-route rerouting: a normal day and an incident, for rising navigator share.
def e7(a):
    out = {"rows": []}
    rng = np.random.default_rng(700)
    net = Net(NET_N)
    dem = make_demand(net, int(BASE_TRIPS * a.scale), rng)
    routes, hist, table, _ = assign(net, dem, 15, "gapcap", seed=8, log=False)
    # Close the arterial segments carrying most of the flow to 20% capacity for 45 minutes during the peak.
    base = simulate(net, dem, routes, seed=1)
    busiest = np.argsort(-base["ent"].sum(axis=1))[:4].tolist()
    incident = {"t0": 3600.0, "t1": 6300.0, "links": busiest, "factor": 0.2}
    for name, closed in (("normal", None), ("incident", incident)):
        for p in (0.0, 0.1, 0.3, 0.6, 1.0):
            res_list = []
            for s in (1, 2):
                nav = {"p": p, "period": 300.0, "min_saving": 60.0, "min_rel": 0.1} if p > 0 else None
                res_list.append(simulate(net, dem, routes, seed=s, closed=closed, nav=nav))
            ex = [experience(dem, r) for r in res_list]
            row = {"scenario": name, "nav_share": p, "mean_tt_s": float(np.mean([e["mean_tt_s"] for e in ex])),
                   "p95_tt_s": float(np.mean([e["p95_tt_s"] for e in ex])), "unfinished": float(np.mean([e["unfinished"] for e in ex])),
                   "reroutes_per_navigator": float(np.mean([r["reroutes"] for r in res_list]) / max(p * dem.n, 1)),
                   "flow_on_incident_links": float(np.mean([r["ent"][busiest].sum() for r in res_list]))}
            out["rows"].append(row)
            print(row, flush=True)
            save(f"E7_en_route_s{a.scale}", out)


# E8: repeat the loop at rising scale to measure how the prototype's own work grows, and report per-iteration parts.
def e8(a):
    out = {"rows": []}
    for n, trips in ((6, 3000), (8, 8000), (12, 24000)):
        rng = np.random.default_rng(800)
        net = Net(n)
        dem = make_demand(net, trips, rng)
        t0 = time.time()
        routes = freeflow_routes(net, dem)
        tff = time.time() - t0
        t0 = time.time()
        res = simulate(net, dem, routes, seed=1)
        tsim = time.time() - t0
        t0 = time.time()
        tt, wt = cost_table(net, res)
        ttab = time.time() - t0
        t0 = time.time()
        rt = Router(net, tt, wt)
        g, cur, best = gap_and_costs(rt, dem, routes)
        trout = time.time() - t0
        row = {"n": n, "links": net.nl, "trips": trips, "route_ff_s": tff, "sim_s": tsim, "cost_table_s": ttab, "gap_routing_s": trout,
               "trees": rt.calls, "gap0": float(g)}
        out["rows"].append(row)
        print(row, flush=True)
    save("E8_scale", out)


EXPS = {"E0": e0, "E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E6": e6, "E7": e7, "E8": e8}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", choices=sorted(EXPS))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--scale", type=float, default=1.5)
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--policies", default="gapcap,fixed10")
    ap.add_argument("--tag", default="a")
    ap.add_argument("--scales", default="1.0,1.5,2.0")
    ap.add_argument("--beta", type=float, default=0.5)
    ap.add_argument("--shift", type=float, default=300.0)
    ap.add_argument("--depfrac", type=float, default=0.15)
    ap.add_argument("--priors", default="")
    ap.add_argument("--reps", default="1x48,2x24,4x12,8x6")
    ap.add_argument("--reinit", action="store_true")
    ap.add_argument("--gamma", type=float, default=2.0)
    args = ap.parse_args()
    t = time.time()
    EXPS[args.exp](args)
    print(f"{args.exp} done in {time.time() - t:.0f}s", file=sys.stderr)
