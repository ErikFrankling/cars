#!/usr/bin/env python3
"""Trajectory-level CPU oracle for coordinated junctions on real SUMO junction geometry.

Replaces the point-queue model in coordinated_intersections.py. Vehicles have length, width, bounded
acceleration and braking; conflicts come from swept paths computed on SUMO internal-lane shapes; queues
start from rest; exits have finite storage; messages can be lost; an independent auditor tests oriented
rectangles for overlap every step and the stop-before-zone invariant.

Run from the repo root: nix develop --command python3 -I research/truth/scripts/ci_model.py test
"""
import csv, json, math, random, sys, time, zlib, xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NETS = ROOT / 'fig' / '09-nets'
DT = 0.1


def default_cfg():
    return dict(
        net='j2', policy='wspt', demand=3000.0, left=0.1, right=0.1, ew_share=0.5, seed=0,
        warm=300.0, end=1200.0,
        # vehicle
        L=5.0, W=1.8, s0=2.0, tau=0.8, a=2.6, b_plan=2.5, b_curve=2.5, b_s=4.5, b_e=7.0, T_r=0.3, a_lat=2.5,
        # conflict geometry and timing
        m_lat=0.5, m_t=0.3, level='A',
        # coordinator
        tick=0.5, T_firm=4.0, K_lane=6, R=32, A_max=90.0, h_ref=1.2, K_max=16, gap_batch=2.5, D_req=60.0,
        # signal
        sig_min=4.0, sig_max=30.0, sig_gap=2.0, sig_lost=0.0, sig_start=0.0,
        # faults
        p_loss=0.0, blackout=None, crash=None, fallback='awsc', stall_rate=0.0, stall_T=30.0,
        exit_cap=None, exit_block=None, exit_check=True, exit_aware=False, ponr=True, perception=True, adaptive=False, intent=False, cong_v=8.0, cong_x=60.0, audit=True, trace=None, debug=False,
    )


HUMAN = dict(tau=1.4, s0=2.5, T_r=1.0, b_plan=2.5, b_curve=2.5, sig_lost=4.0, sig_start=1.0, m_t=0.5)


# ---------------------------------------------------------------------------- geometry

def polyline(shape):
    return np.array([[float(c) for c in p.split(',')] for p in shape.split()])


def resample(pts, ds=0.25):
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.arange(0, cum[-1] + 1e-6, ds)
    return s, np.column_stack([np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])]), cum[-1]


class Lane:
    __slots__ = 'id edge idx length speed shape cars movs source sink junction_end junction_from jam cap_next'.split()


class Movement:
    __slots__ = ('id from_lane to_lane dir P vm vk s xy conf tin tout vout tt_cache group junction lane_i '
                 'tail_in t_clear').split()


class Junction:
    pass


def load_net(cfg):
    root = ET.parse(NETS / f"{cfg['net']}.net.xml").getroot()
    lanes, internal = {}, {}
    for e in root.findall('edge'):
        for l in e.findall('lane'):
            if e.get('function') == 'internal':
                internal[l.get('id')] = dict(shape=polyline(l.get('shape')), speed=float(l.get('speed')))
            else:
                x = Lane()
                x.id, x.edge, x.idx = l.get('id'), e.get('id'), int(l.get('index'))
                x.length, x.speed = float(l.get('length')), float(l.get('speed'))
                x.shape = polyline(l.get('shape'))
                x.cars, x.movs, x.source, x.sink = [], [], False, False
                x.junction_end, x.junction_from = None, None
                lanes[x.id] = x
    edges_from = {e.get('id'): e.get('from') for e in root.findall('edge') if e.get('function') != 'internal'}
    edges_to = {e.get('id'): e.get('to') for e in root.findall('edge') if e.get('function') != 'internal'}
    conn_by_internal = {}
    conns = []
    for c in root.findall('connection'):
        if c.get('from').startswith(':'):
            conn_by_internal[f"{c.get('from')}_{c.get('fromLane')}"] = c
        else:
            conns.append(c)
    tls = {t.get('id'): [p.get('state') for p in t.findall('phase')] for t in root.findall('tlLogic')}
    controlled = []
    in_edges = {}
    for e, to in edges_to.items():
        in_edges.setdefault(to, set()).add(e)
    out_edges = {}
    for e, fr in edges_from.items():
        out_edges.setdefault(fr, set()).add(e)
    for j, es in in_edges.items():
        if len(es) >= 3 and j in tls:
            controlled.append(j)
    if cfg['net'].startswith('j'):
        controlled = ['B1']
    elif cfg['net'].startswith('grid'):
        controlled = [j for j in controlled if j[0] in 'BCD' and j[1] in '123']
    juncs = {}
    for j in controlled:
        J = Junction()
        J.id, J.movs, J.lanes, J.out_lanes = j, [], [], {}
        juncs[j] = J
    for c in conns:
        fe, te = c.get('from'), c.get('to')
        j = edges_to[fe]
        if j not in juncs or c.get('dir') == 't':
            continue
        J = juncs[j]
        fl = lanes[f"{fe}_{c.get('fromLane')}"]
        tl = lanes[f"{te}_{c.get('toLane')}"]
        pts = []
        speed = 1e9
        via = c.get('via')
        while via:
            seg = internal[via]
            pts.append(seg['shape'])
            speed = min(speed, seg['speed'])
            nxt = conn_by_internal.get(via)
            via = nxt.get('via') if nxt is not None else None
        P = np.vstack(pts)
        m = Movement()
        m.id, m.from_lane, m.to_lane, m.dir = len(J.movs), fl, tl, c.get('dir')
        m.group = phase_groups(tls[j], int(c.get('linkIndex')))
        m.s, m.xy, m.P = resample(P)
        vlane = fl.speed
        m.vm = vlane if speed >= vlane - 1e-3 else speed * math.sqrt(cfg['a_lat'] / 5.5)
        m.junction = J
        J.movs.append(m)
        fl.movs.append(m)
        fl.junction_end = J
        tl.junction_from = J
        J.out_lanes[tl.id] = True
        if fl not in J.lanes:
            J.lanes.append(fl)
    for J in juncs.values():
        J.groups = sorted({g for m in J.movs for g in m.group})
        build_conflicts(J, cfg)
    return lanes, juncs, edges_from, edges_to, in_edges, out_edges, controlled


def phase_groups(states, idx):
    return tuple(i for i, s in enumerate(states) if s[idx] in 'Gg' and 'y' not in s)


def build_conflicts(J, cfg):
    W = cfg['W'] + cfg['m_lat']
    mv = J.movs
    n = len(mv)
    J.pair_rev = []
    conf = [[] for _ in mv]
    box = cfg['policy'] == 'fcfs_box'
    J.div, J.merge, J.hcache = {}, {}, {}
    regions = {}
    for i in range(n):
        for j in range(i + 1, n):
            a, b = mv[i], mv[j]
            if box:
                regions[i, j] = ((0.0, a.P), (0.0, b.P))
                continue
            d = np.hypot(a.xy[:, None, 0] - b.xy[None, :, 0], a.xy[:, None, 1] - b.xy[None, :, 1])
            hit = d <= W
            if not hit.any():
                continue
            ia, ib = np.where(hit.any(axis=1))[0], np.where(hit.any(axis=0))[0]
            sa, sb = (a.s[ia[0]], a.s[ia[-1]]), (b.s[ib[0]], b.s[ib[-1]])
            # shared entry and shared exit are follow-the-leader relations, handled by pair_headway
            if a.from_lane is b.from_lane:
                J.div[i, j] = J.div[j, i] = (sa[1], sb[1])
                continue
            if a.to_lane is b.to_lane:
                J.merge[i, j], J.merge[j, i] = a.P - sa[0], b.P - sb[0]
                # a gap-filling calendar can reorder at a merge, so it needs the merge as a resource
                if cfg['policy'] != 'fcfs_conf':
                    continue
                sa, sb = (sa[0], a.P), (sb[0], b.P)
            regions[i, j] = (sa, sb)
    J.regions = regions
    pid = 0
    for (i, j), (sa, sb) in regions.items():
        conf[i].append((pid, j, sa))
        conf[j].append((pid + 1, i, sb))
        J.pair_rev += [pid + 1, pid]
        pid += 2
    J.npairs = pid
    fr = (1.0, 0.8, 0.6, 0.4, 0.2, 0.0)
    for m in mv:
        m.vk = [m.vm * f for f in fr]
        m.conf = conf[m.id]
        m.tin, m.tout, m.vout, m.tail_in = [], [], [], []
        m.t_clear = []
        for v0 in m.vk:
            m.tin.append([travel_time(m, v0, r[0], cfg) for (_, _, r) in m.conf])
            m.tout.append([travel_time(m, v0, r[1] + cfg['L'], cfg) for (_, _, r) in m.conf])
            m.vout.append(speed_at(m, v0, m.P, cfg))
            m.tail_in.append(travel_time(m, v0, m.P, cfg))
            m.t_clear.append(travel_time(m, v0, m.P + cfg['L'], cfg))
        m.tt_cache = {}


def travel_time(m, v0, s, cfg):
    a, vmax = cfg['a'], m.from_lane.speed
    if s <= 0:
        return 0.0
    t, v = 0.0, v0
    for cap, seg in ((m.vm, min(s, m.P)), (vmax, max(0.0, s - m.P))):
        if seg <= 0:
            continue
        if v < cap:
            da = (cap * cap - v * v) / (2 * a)
            if da >= seg:
                vn = math.sqrt(v * v + 2 * a * seg)
                t += (vn - v) / a
                v = vn
                continue
            t += (cap - v) / a
            seg -= da
            v = cap
        t += seg / max(v, 1e-3)
    return t


def travel_time_cap(m, v0, s, cap, cfg):
    # as travel_time, but the exit will not let the car exceed cap until its rear is out of the box
    a = cfg['a']
    if s <= 0:
        return 0.0
    c1 = min(m.vm, cap)
    v = min(v0, c1)
    d = (c1 * c1 - v * v) / (2 * a)
    if d >= s:
        return (math.sqrt(v * v + 2 * a * s) - v) / a
    return (c1 - v) / a + (s - d) / max(c1, 1e-3)


def speed_at(m, v0, s, cfg):
    a = cfg['a']
    return min(m.vm, math.sqrt(v0 * v0 + 2 * a * s))


def speed_along(m, v0, s, cfg):
    a = cfg['a']
    if s <= m.P:
        return min(m.vm, math.sqrt(v0 * v0 + 2 * a * s))
    vp = min(m.vm, math.sqrt(v0 * v0 + 2 * a * m.P))
    return min(m.from_lane.speed, math.sqrt(vp * vp + 2 * a * (s - m.P)))


def pair_headway(J, p, kp, m, k, exit_rel, cfg):
    # smallest t_m - t_p keeping m behind p by L + s0 + v tau over the whole shared stretch
    key = (p.id, kp, m.id, k, exit_rel)
    h = J.hcache.get(key)
    if h is not None:
        return h
    L0 = cfg['L'] + cfg['s0']
    h = -1e9
    if exit_rel:
        # coordinates measured from each path's box end
        x0 = -max(J.merge.get((m.id, p.id), 0.0), 0.0)
        for x in np.arange(x0, 60.01, 1.0):
            sm = m.P + x
            vm = speed_along(m, m.vk[k], max(sm, 0.0), cfg)
            sp = p.P + x + L0 + vm * cfg['tau']
            h = max(h, travel_time(p, p.vk[kp], sp, cfg) - travel_time(m, m.vk[k], max(sm, 0.0), cfg))
    else:
        div = J.div.get((p.id, m.id))
        end = (div[1] if div else m.P + 60.0)
        for sm in np.arange(0.0, end + 0.01, 1.0):
            vm = speed_along(m, m.vk[k], sm, cfg)
            sp = sm + L0 + vm * cfg['tau']
            h = max(h, travel_time(p, p.vk[kp], sp, cfg) - travel_time(m, m.vk[k], sm, cfg))
    h = float(h)
    J.hcache[key] = h
    return h


def earliest(d, v, vk, vmax, a, b):
    if v <= vk:
        if (vk * vk - v * v) / (2 * a) > d + 1e-6:
            return None
    elif (v * v - vk * vk) / (2 * b) > d + 1e-6:
        return None
    vp2 = (2 * a * b * d + b * v * v + a * vk * vk) / (a + b)
    vp = math.sqrt(max(vp2, 0.0))
    if vp <= vmax:
        return max(vp - v, 0.0) / a + max(vp - vk, 0.0) / b
    return ((vmax - v) / a + (vmax - vk) / b +
            (d - (vmax * vmax - v * v) / (2 * a) - (vmax * vmax - vk * vk) / (2 * b)) / vmax)


def latest(d, v, vk, a, b):
    C = d - v * v / (2 * b) - vk * vk / (2 * a)
    if C >= 0:
        return math.inf
    K = 1 / (2 * b) + 1 / (2 * a)
    vc = math.sqrt(-C / K)
    if vc > min(v, vk):
        return None
    return (v - vc) / b + (vk - vc) / a


# ---------------------------------------------------------------------------- simulator

class Sim:
    def __init__(self, cfg):
        self.c = cfg
        self.rng = random.Random(cfg['seed'])
        self.lanes, self.juncs, self.edges_from, self.edges_to, self.in_edges, self.out_edges, self.ctrl = load_net(cfg)
        cap = 6000
        self.alive = np.zeros(cap, bool)
        self.odo = np.zeros(cap)
        self.v = np.zeros(cap)
        self.acc = np.zeros(cap)
        self.leader = -np.ones(cap, int)
        self.off = np.zeros(cap)
        self.mode = np.zeros(cap, int)  # 0 ungranted, 1 advised, 2 firm, 3 past the line, 4 run-off to sink
        self.tg = np.zeros(cap)
        self.vg = np.zeros(cap)
        self.vc = np.zeros(cap)
        self.odo_line = np.full(cap, 1e12)
        self.odo_box = np.full(cap, 1e12)
        self.vcap = np.zeros(cap)
        self.vcap2 = np.zeros(cap)
        self.hold = np.full(cap, 1e12)
        self.stalled = np.zeros(cap, bool)
        self.seq = np.zeros(cap, np.int64)
        self.yield_at = np.full(cap, 1e12)
        self.box_cap = np.full(cap, 1e9)
        self.exit_plan = {}
        self.armed = np.zeros(cap, bool)
        self.next_seq = 0
        self.free = list(range(cap - 1, -1, -1))
        self.mov = [None] * cap
        self.klass = [0] * cap
        self.lane = [None] * cap
        self.enter_t = np.zeros(cap)
        self.trip_t0 = np.zeros(cap)
        self.free_time = np.zeros(cap)
        self.pending = {}
        self.acked = set()
        self.grant_rec = {}
        self.t = 0.0
        self.step_i = 0
        self.m = dict(late_set=set(), ponr_abort=0, exited=0, offered=0, loss=0.0, stops=0, overlap=0, overlap_pairs=set(), invariant=0, line_err=[],
                      late=0, aborts=0, wasted=0, a2=0.0, a2n=0, exit_delays=[], peakq=0, grants=0, cf_inbox=0,
                      box_block=0, stall_coll=0, stalls=0, minmargin=9.9)
        self.q_at_warm = None
        self.was_moving = np.zeros(cap, bool)
        self.srcq = {}
        self.events = []
        self.sink_ready = {}
        self.J_state = {}
        for J in self.juncs.values():
            s = dict(rel=[-1e9] * J.npairs, rel_exit={x: None for x in J.out_lanes}, last={l.id: None for l in J.lanes},
                     committed={x: 0 for x in J.out_lanes}, phase=0, phase_t=0.0, switch_t=-1e9, active=J.groups[0] if J.groups else 0,
                     served=0, group_last=-1e9, ivals=[[] for _ in range(J.npairs)], down=False, was_down=False, frozen=[], cong={}, armed={x: 0 for x in J.out_lanes})
            self.J_state[J.id] = s
        self.make_demand()
        self.next_tick = 0.0
        self.trace = open(cfg['trace'], 'w') if cfg['trace'] else None

    # ----- demand
    def make_demand(self):
        c = self.c
        srcs = []
        for edge, fr in self.edges_from.items():
            to = self.edges_to[edge]
            if to in self.juncs and fr not in self.juncs:
                srcs.append(edge)
        self.src_edges = srcs
        ew = c['ew_share']
        for e in srcs:
            horiz = self.is_horizontal(e)
            share = (ew if horiz else 1 - ew) / 2 * (4 / max(len(srcs), 1))
            rate = c['demand'] * share / 3600
            t = 0.0
            r = random.Random(zlib.crc32(f"{e}/{c['seed']}".encode()))
            while rate > 0:
                t += r.expovariate(rate)
                if t >= c['end']:
                    break
                self.events.append((t, e))
        self.events.sort()
        self.ev_i = 0

    def is_horizontal(self, edge):
        lane = self.lanes[f'{edge}_0']
        return abs(lane.shape[-1, 0] - lane.shape[0, 0]) > abs(lane.shape[-1, 1] - lane.shape[0, 1])

    def pick_dir(self):
        u = self.rng.random()
        if u < self.c['left']:
            return 'l'
        if u < self.c['left'] + self.c['right']:
            return 'r'
        return 's'

    def pick_lane(self, edge, d):
        opts = [l for l in self.edge_lanes(edge) if any(m.dir == d for m in l.movs)]
        if not opts:
            opts = self.edge_lanes(edge)
        return min(opts, key=lambda l: len(self.srcq.get(l.id, ())) + len(l.cars) + 0.001 * l.idx)

    def edge_lanes(self, edge):
        out, i = [], 0
        while f'{edge}_{i}' in self.lanes:
            out.append(self.lanes[f'{edge}_{i}'])
            i += 1
        return out

    def pick_mov(self, lane, d=None):
        if not lane.movs:
            return None
        if d is None:
            d = self.pick_dir()
        match = [m for m in lane.movs if m.dir == d]
        if not match:
            match = [m for m in lane.movs if m.dir == 's'] or lane.movs
        return match[0] if len(match) == 1 else self.rng.choice(match)

    # ----- insertion
    def insert(self):
        c = self.c
        while self.ev_i < len(self.events) and self.events[self.ev_i][0] <= self.t:
            t0, e = self.events[self.ev_i]
            self.ev_i += 1
            d = self.pick_dir()
            lane = self.pick_lane(e, d)
            self.srcq.setdefault(lane.id, []).append((t0, d))
            if t0 >= c['warm']:
                self.m['offered'] += 1
        for lid, q in self.srcq.items():
            if not q:
                continue
            lane = self.lanes[lid]
            v_ins = lane.speed
            if lane.cars:
                tail = lane.cars[-1]
                x = self.lane_x(tail, lane)
                gap = x - c['L']
                # the upstream queue discharges at the equilibrium headway of the tail's speed
                v_ins = min(lane.speed, float(self.v[tail]) + 1.0)
                if gap < c['s0'] + 0.5 + v_ins * c['tau']:
                    continue
            t0, d = q.pop(0)
            self.spawn(lane, t0, d, v_ins)

    def lane_x(self, i, lane):
        if self.mode[i] == 3 or self.odo_line[i] >= 1e11:
            return self.odo[i] - self.odo_box[i]
        return lane.length - (self.odo_line[i] - self.odo[i])

    def spawn(self, lane, t0, d, v):
        i = self.free.pop()
        self.alive[i] = True
        self.odo[i] = 0.0
        self.v[i] = v
        self.acc[i] = 0.0
        self.mode[i] = 0
        self.stalled[i] = False
        self.hold[i] = 1e12
        self.odo_line[i] = lane.length
        self.odo_box[i] = 1e12
        self.vcap[i] = lane.speed
        self.lane[i] = lane
        self.mov[i] = self.pick_mov(lane, d)
        self.klass[i] = 0
        self.enter_t[i] = self.t
        self.trip_t0[i] = t0
        self.free_time[i] = 0.0
        if self.t - t0 > 2.0 and self.t >= self.c['warm']:
            self.m['stops'] += 1
        if lane.cars:
            self.set_leader(i, lane.cars[-1])
        else:
            self.leader[i] = -1
        lane.cars.append(i)

    def set_leader(self, i, l):
        self.leader[i] = l
        self.off[i] = self.odo_line[i] - self.odo_line[l] if self.mode[l] < 3 else 0.0

    # ----- coordinator: candidate timing
    def cand_time(self, st, m, d, v, now, scratch, last, rel_exit, min_t, ivals=None, kmin=0):
        c = self.c
        mt = c['m_t']
        a, b = c['a'], c['b_plan']
        vmax = m.from_lane.speed
        prev = last[m.from_lane.id]
        tx = m.to_lane.id
        for k, vk in enumerate(m.vk):
            if k < kmin:
                continue
            te = earliest(d, v, vk, vmax, a, b)
            if te is None:
                continue
            tl = latest(d, v, vk, a, b)
            if tl is None:
                continue
            t = max(now + te, min_t)
            if prev is not None:
                pm, pk, pt = prev
                t = max(t, pt + pair_headway(m.junction, pm, pk, m, k, False, c))
            px = rel_exit[tx]
            if px is not None:
                pm, pk, pt = px
                t = max(t, pt + pair_headway(m.junction, pm, pk, m, k, True, c))
            # the exit tail may slow for its own next junction: assume it holds its present speed,
            # and be clear of the box behind it at that pace
            x = m.to_lane
            if x.cars:
                tail = x.cars[-1]
                vt = self.tail_speed(tail)
                if vt > 0.5:
                    gap_need = 2 * c['L'] + c['s0'] + m.vout[k] * c['tau'] - self.exit_x(tail, x)
                    if gap_need > 0:
                        t = max(t, now + gap_need / vt - m.t_clear[k])
            margin = mt
            mb = c['T_r'] + max(vk, 2.0) / (2 * c['b_e'])
            if c['level'] == 'B':
                margin += mb
            tin, tout = m.tin[k], m.tout[k]
            cap = 1e9
            if c['exit_aware'] and x.cars:
                vt = float(self.v[x.cars[-1]])
                if vt < m.from_lane.speed - 0.5 and self.exit_x(x.cars[-1], x) < 80.0:
                    cap = max(vt, 2.0)
                    if cap < m.vm or vt < m.from_lane.speed - 0.5:
                        tin = [travel_time_cap(m, vk, r[0], cap, c) for (_, _, r) in m.conf]
                        tout = [travel_time_cap(m, vk, r[1] + c['L'], cap, c) for (_, _, r) in m.conf]
            if ivals is None:
                cong = st['cong']
                for j, (pid, f, r) in enumerate(m.conf):
                    x = scratch[pid] + margin - tin[j]
                    # a foe bound for a congested exit may be slowed in the box: take the stall-tolerant spacing
                    if c['level'] == 'A' and c['adaptive'] and cong.get(m.junction.movs[f].to_lane.id):
                        x += mb
                    if x > t:
                        t = x
            else:
                moved = True
                while moved:
                    moved = False
                    for j, (pid, f, r) in enumerate(m.conf):
                        for s0, s1 in ivals[pid]:
                            if t + tin[j] < s1 + margin and t + tout[j] + mt > s0:
                                t = s1 + margin - tin[j]
                                moved = True
            if t - now > tl + 1e-6:
                continue
            self.exit_plan[m.junction.id, m.id, k] = (cap, tout)
            return t, k
        return None

    def commit_scratch(self, m, k, t, scratch, last, rel_exit):
        c = self.c
        cap, tout = self.exit_plan.get((m.junction.id, m.id, k), (1e9, m.tout[k]))
        for j, (pid, f, r) in enumerate(m.conf):
            rv = m.junction.pair_rev[pid]
            x = t + tout[j]
            if x > scratch[rv]:
                scratch[rv] = x
        last[m.from_lane.id] = (m, k, t)
        rel_exit[m.to_lane.id] = (m, k, t)

    def exit_clear_now(self, m):
        # worst case: the last car past the box brakes comfortably to rest, and everyone
        # already beyond their point of no return stacks behind it. My rear must clear the box.
        c = self.c
        x = m.to_lane
        unit = c['L'] + c['s0'] + 1.0
        st = self.J_state[m.junction.id]
        ahead = st['armed'][x.id]
        tail = None
        for q in reversed(x.cars):
            if self.mode[q] == 3 and self.odo[q] < self.odo_box[q]:
                ahead += 1
            else:
                tail = q
                break
        if tail is None:
            return (ahead + 1) * unit <= x.length
        xt = self.exit_x(tail, x) - c['L']
        have = xt + float(self.v[tail]) ** 2 / (2 * c['b_curve']) - ahead * unit
        return have >= unit

    def tail_speed(self, tail):
        # exit cars publish their plan for their next junction; use the slower of speed and intent
        v = float(self.v[tail])
        if self.c['intent'] and self.mode[tail] in (1, 2):
            v = min(v, float(self.vc[tail]))
        return v

    def update_congestion(self, J, st):
        c = self.c
        unit = c['L'] + c['s0'] + 1.0
        cong = st['cong']
        for xid in J.out_lanes:
            x = self.lanes[xid]
            flag = False
            if x.cars:
                tail = x.cars[-1]
                flag = self.tail_speed(tail) < c['cong_v'] and self.exit_x(tail, x) < c['cong_x']
                flag = flag or (len(x.cars) + st['committed'][xid]) * unit > 0.5 * x.length
            cong[xid] = flag

    def exit_ok(self, st, m, k):
        c = self.c
        if not c['exit_check']:
            return True
        x = m.to_lane
        # a real standing queue packs a little looser than L + s0
        unit = c['L'] + c['s0'] + 1.0
        n = len(x.cars) + st['committed'][x.id]
        if (n + 1) * unit > x.length:
            return False
        if x.cars:
            tail = x.cars[-1]
            # a tail shuffling forward can stop again, so any slow tail counts
            if self.v[tail] < 5.0:
                xt = self.exit_x(tail, x) - c['L'] + self.v[tail] ** 2 / (2 * c['b_s'])
                vo = m.vout[k]
                need = unit + c['T_r'] * vo + vo * vo / (2 * c['b_s'])
                if xt - st['committed'][x.id] * unit < need:
                    return False
        return True

    # ----- coordinator: tick
    def tick(self):
        c = self.c
        now = self.t
        for J in self.juncs.values():
            st = self.J_state[J.id]
            if st.get('freeze'):
                continue
            if self.coord_down(J):
                st['was_down'] = True
                if c['fallback'] == 'awsc':
                    self.awsc(J, st, now)
                continue
            st['was_down'] = False
            self.update_congestion(J, st)
            if c['policy'] in ('sig_h', 'sig_av'):
                self.signal_tick(J, st, now)
            elif c['policy'] in ('fcfs_conf', 'fcfs_box', 'fcfs_scalar'):
                self.fcfs_tick(J, st, now)
            else:
                self.list_tick(J, st, now)

    def coord_down(self, J):
        cr = self.c['crash']
        return cr is not None and cr[0] <= self.t < cr[1]

    def radio_ok(self):
        bl = self.c['blackout']
        return not (bl is not None and bl[0] <= self.t < bl[1])

    def state_ok(self):
        if not self.radio_ok():
            return False
        p = self.c['p_loss']
        return p <= 0 or self.rng.random() >= p

    def heads(self, lane):
        out, n = [], 0
        for i in lane.cars:
            if self.mode[i] >= 3:
                continue
            # nothing goes firm behind a car whose own grant is unconfirmed
            if i in self.pending:
                break
            if self.mode[i] == 2:
                continue
            out.append(i)
            n += 1
            if n >= self.c['K_lane']:
                break
        return out

    def do_firm(self, i, m, k, t, st):
        c = self.c
        self.commit_scratch(m, k, t, st['rel'], st['last'], st['rel_exit'])
        st['committed'][m.to_lane.id] += 1
        self.m['grants'] += 1
        self.grant_rec[i] = (m, k, t)
        self.next_seq += 1
        self.seq[i] = self.next_seq
        self.box_cap[i] = self.exit_plan.get((m.junction.id, m.id, k), (1e9,))[0]
        if c['p_loss'] <= 0 and c['blackout'] is None:
            self.deliver(i, m, k, t)
        else:
            self.pending[i] = (m, k, t)

    def deliver(self, i, m, k, t):
        self.mode[i] = 2
        self.tg[i] = t
        self.vg[i] = m.vk[k]
        self.klass[i] = k
        self.acked.add(i)

    def list_tick(self, J, st, now):
        c = self.c
        policy = c['policy']
        scratch = list(st['rel'])
        last = dict(st['last'])
        rel_exit = dict(st['rel_exit'])
        cands = {l.id: self.heads(l) for l in J.lanes}
        ptr = {l.id: 0 for l in J.lanes}
        cache = {}
        plan = []
        active, served, gl = st['active'], st['served'], st['group_last']
        total = 0
        def eval_lane(lid):
            q = cands[lid]
            p = ptr[lid]
            if p >= len(q):
                return None
            i = q[p]
            m = self.mov[i]
            d = max(self.odo_line[i] - self.odo[i], 0.0)
            r = self.cand_time(st, m, d, float(self.v[i]), now, scratch, last, rel_exit, now + 0.1)
            if r is None:
                return None
            t, k = r
            if policy == 'wspt':
                n = 1
                dp = d
                for j in q[p + 1:]:
                    dj = self.odo_line[j] - self.odo[j]
                    if (dj - dp) / max(float(self.v[j]), 3.0) > c['gap_batch']:
                        break
                    n += 1
                    dp = dj
                score = (t - now + n * c['h_ref']) / n
            else:
                score = t
            if now - self.enter_t[i] > c['A_max']:
                score -= 1e6
            return score, t, k, i, m
        while total < c['R']:
            best = None
            for lid in cands:
                r = cache.get(lid, 0)
                if r == 0:
                    r = eval_lane(lid)
                    cache[lid] = r
                if r is None:
                    continue
                if policy == 'poll':
                    g = r[4].group
                    in_active = active in g
                    if in_active and served < c['K_max'] and (gl < -1e8 or r[1] - gl <= c['gap_batch'] + 1.0):
                        sc = (0, r[1])
                    else:
                        sc = (1, -len(cands[lid]) + ptr[lid], r[1])
                    if best is None or sc < best[0]:
                        best = (sc, r, lid)
                else:
                    if best is None or r[0] < best[1][0]:
                        best = (None, r, lid)
            if best is None:
                break
            _, r, lid = best
            score, t, k, i, m = r
            if policy == 'poll':
                if active not in m.group:
                    active = m.group[0]
                    served = 0
                elif served >= c['K_max']:
                    others = [g for g in m.group if g != active]
                    if others:
                        active = others[0]
                    served = 0
                elif gl > -1e8 and t - gl > c['gap_batch'] + 1.0:
                    served = 0
                served += 1
                gl = t
            self.commit_scratch(m, k, t, scratch, last, rel_exit)
            plan.append((i, m, k, t))
            ptr[lid] += 1
            total += 1
            cache = {l: v for l, v in cache.items() if l != lid and not self.mov_conflicts(m, lid)}
        # advisories then firm grants on the real table, in list order
        blocked = set()
        for i, m, k, t in plan:
            lid = m.from_lane.id
            d = self.odo_line[i] - self.odo[i]
            v = float(self.v[i])
            if self.mode[i] == 0:
                self.mode[i] = 1
            self.tg[i] = t
            self.vg[i] = m.vk[k]
            horizon = d <= v * v / (2 * c['b_curve']) + v * (c['tick'] + 0.3) + 5.0 or t - now <= c['T_firm']
            if not horizon or lid in blocked or not self.state_ok():
                blocked.add(lid)
                continue
            r = self.firm_time(st, m, max(d, 0.0), v, now)
            if r is None:
                blocked.add(lid)
                continue
            t2, k2 = r
            self.do_firm(i, m, k2, t2, st)
            if policy == 'poll':
                if st['active'] not in m.group:
                    st['active'] = m.group[0]
                    st['served'] = 0
                st['served'] += 1
                st['group_last'] = t2
        if policy == 'poll':
            if st['group_last'] < now - c['gap_batch']:
                st['served'] = c['K_max']

    def firm_time(self, st, m, d, v, now):
        c = self.c
        kmin = 0
        while kmin < len(m.vk):
            r = self.cand_time(st, m, d, v, now, st['rel'], st['last'], st['rel_exit'], now + 0.1, kmin=kmin)
            if r is None or r[0] - now > c['T_firm'] + 1.0:
                return None
            if self.exit_ok(st, m, r[1]):
                return r
            kmin = r[1] + 1
        return None

    def mov_conflicts(self, m, lid):
        lane = self.lanes[lid]
        if lane is m.from_lane:
            return True
        J = m.junction
        for x in lane.movs:
            if (m.id, x.id) in J.regions or (x.id, m.id) in J.regions:
                return True
            if x.to_lane is m.to_lane:
                return True
        return False

    def fcfs_tick(self, J, st, now):
        c = self.c
        gap_fill = c['policy'] == 'fcfs_conf'
        order = []
        for l in J.lanes:
            for i in l.cars:
                if self.mode[i] >= 2 or i in self.pending:
                    continue
                if self.odo_line[i] - self.odo[i] <= c['D_req']:
                    order.append((self.enter_t[i], i, l))
                break
        order.sort()
        for _, i, l in order:
            while True:
                if any(j in self.pending for j in l.cars[:l.cars.index(i)]):
                    break
                m = self.mov[i]
                d = max(self.odo_line[i] - self.odo[i], 0.0)
                if d > c['D_req'] or not self.state_ok():
                    break
                r = self.cand_time(st, m, d, float(self.v[i]), now, st['rel'], st['last'], st['rel_exit'], now + 0.1,
                                   ivals=st['ivals'] if gap_fill else None)
                if r is None or not self.exit_ok(st, m, r[1]):
                    break
                t, k = r
                if gap_fill:
                    for j, (pid, f, rr) in enumerate(m.conf):
                        rv = J.pair_rev[pid]
                        st['ivals'][rv].append((t + m.tin[k][j], t + m.tout[k][j]))
                        if len(st['ivals'][rv]) > 64:
                            st['ivals'][rv] = [x for x in st['ivals'][rv] if x[1] > now]
                self.do_firm(i, m, k, t, st)
                idx = l.cars.index(i)
                nxt = None
                for j in l.cars[idx + 1:]:
                    if j in self.pending:
                        break
                    if self.mode[j] < 2:
                        nxt = j
                        break
                if nxt is None:
                    break
                i = nxt

    def awsc(self, J, st, now):
        c = self.c
        best = None
        for l in J.lanes:
            for i in l.cars:
                if self.mode[i] >= 3:
                    continue
                if self.mode[i] == 2 or i in self.pending:
                    break
                if self.odo_line[i] - self.odo[i] < 3.0 and self.v[i] < 0.5:
                    if best is None or self.enter_t[i] < best[0]:
                        best = (self.enter_t[i], i)
                break
        if best is None:
            return
        i = best[1]
        m = self.mov[i]
        busy = any(self.mode[x] == 3 and self.odo[x] < self.odo_box[x] + c['L'] for l in J.lanes for x in [] )
        k = len(m.vk) - 1
        for j, (pid, f, r) in enumerate(m.conf):
            pass
        t0 = st.get('awsc_free', -1e9)
        if now < t0:
            return
        t = now + 0.5
        d = max(self.odo_line[i] - self.odo[i], 0.0)
        r = self.cand_time(st, m, d, float(self.v[i]), now, st['rel'], st['last'], st['rel_exit'], now + 0.5)
        if r is None or not self.exit_ok(st, m, r[1]):
            return
        t, k = r
        st['awsc_free'] = t + travel_time(m, m.vk[k], m.P + c['L'], c) + 1.0
        self.commit_scratch(m, k, t, st['rel'], st['last'], st['rel_exit'])
        st['committed'][m.to_lane.id] += 1
        self.grant_rec[i] = (m, k, t)
        self.next_seq += 1
        self.seq[i] = self.next_seq
        self.deliver(i, m, k, t)

    def signal_tick(self, J, st, now):
        c = self.c
        groups = J.groups
        cur = groups[st['phase'] % len(groups)]
        def lanes_of(g):
            return [l for l in J.lanes if any(g in m.group for m in l.movs)]
        def head_time(l):
            for i in l.cars:
                if self.mode[i] >= 3:
                    continue
                if self.mode[i] == 2:
                    continue
                d = self.odo_line[i] - self.odo[i]
                return d / max(float(self.v[i]), 1.0)
            return math.inf
        def has_demand(g, horizon=60.0):
            return any(head_time(l) < horizon for l in lanes_of(g))
        el = now - st['phase_t']
        ext = any(head_time(l) <= c['sig_gap'] for l in lanes_of(cur))
        other = [g for g in groups if g != cur and has_demand(g)]
        if other and el >= c['sig_min'] and (not ext or el >= c['sig_max']) and now >= st['switch_t']:
            st['phase'] = groups.index(other[0])
            st['phase_t'] = now + c['sig_lost']
            st['switch_t'] = now + c['sig_lost']
            cur = other[0]
        if now < st['switch_t']:
            return
        for l in J.lanes:
            for i in l.cars:
                if i in self.pending:
                    break
                if self.mode[i] >= 2:
                    continue
                m = self.mov[i]
                if cur not in m.group:
                    break
                d = max(self.odo_line[i] - self.odo[i], 0.0)
                v = float(self.v[i])
                horizon = d <= v * v / (2 * c['b_curve']) + v * (c['tick'] + 0.3) + 5.0
                extra = c['sig_start'] if v < 0.5 and now - st['phase_t'] < c['tick'] * 1.5 else 0.0
                kmin, r = 0, None
                while kmin < len(m.vk):
                    r = self.cand_time(st, m, d, v, now, st['rel'], st['last'], st['rel_exit'], now + 0.1 + extra, kmin=kmin)
                    if r is None or self.exit_ok(st, m, r[1]):
                        break
                    kmin, r = r[1] + 1, None
                if r is None:
                    break
                t, k = r
                if not (horizon or t - now <= c['T_firm']) or t - now > c['T_firm'] + 1.0:
                    break
                self.do_firm(i, m, k, t, st)

    # ----- messages at 10 Hz
    def messages(self):
        if not self.pending:
            return
        for i in list(self.pending):
            if not self.alive[i]:
                del self.pending[i]
                continue
            if not self.state_ok():
                continue
            m, k, t = self.pending.pop(i)
            d = self.odo_line[i] - self.odo[i]
            v = float(self.v[i])
            te = earliest(max(d, 0.0), v, m.vk[k], m.from_lane.speed, self.c['a'], self.c['b_plan'])
            tl = latest(max(d, 0.0), v, m.vk[k], self.c['a'], self.c['b_plan'])
            ok = te is not None and tl is not None and self.t + te <= t + 0.15 and t - self.t <= tl
            if ok:
                self.deliver(i, m, k, t)
            else:
                self.abort(i)

    def abort(self, i):
        m, k, t = self.grant_rec.pop(i)
        st = self.J_state[m.junction.id]
        st['committed'][m.to_lane.id] -= 1
        self.m['aborts'] += 1
        if self.armed[i]:
            self.armed[i] = False
            st['armed'][m.to_lane.id] -= 1
        self.mode[i] = 0
        self.pending.pop(i, None)

    # ----- physics
    def step(self):
        c = self.c
        idx = np.nonzero(self.alive)[0]
        if len(idx) == 0:
            return
        v = self.v[idx]
        a_max, b_p = c['a'], c['b_plan']
        mode = self.mode[idx]
        d = self.odo_line[idx] - self.odo[idx]
        a_cmd = np.minimum((self.vcap[idx] - v) / DT, a_max)
        a_cmd = np.where(a_cmd < -b_p, -b_p, a_cmd)
        # stop curve for anyone without a confirmed grant
        ung = mode < 2
        if ung.any():
            bc, tr_ = c['b_curve'], c['T_r']
            vs = bc * (np.sqrt(tr_ * tr_ + 2 * np.maximum(d - 0.5, 0.0) / bc) - tr_)
            a_stop = np.clip((vs - v) / DT, -c['b_s'], a_max)
            a_cmd = np.where(ung, np.minimum(a_cmd, a_stop), a_cmd)
        # time tracking for advised and firm cars
        tr = (mode == 1) | (mode == 2)
        if tr.any():
            ti = idx[tr]
            if self.step_i % 2 == 0:
                self.plan_vc(ti)
            vi = self.v[ti]
            di = np.maximum(self.odo_line[ti] - self.odo[ti], 0.0)
            ve = self.vg[ti]
            rate = np.where(ve > vi, a_max, b_p)
            D3 = np.abs(ve * ve - vi * vi) / (2 * rate)
            # a car waiting close to the line must not start its final acceleration before its time
            T3 = np.abs(ve - vi) / rate
            go = (di <= D3 + vi * DT) & ((ve < vi) | (self.tg[ti] - self.t <= T3 + 0.2))
            target = np.where(go, ve, np.where(di <= D3 + vi * DT, np.minimum(vi, self.vc[ti]), self.vc[ti]))
            at = np.clip((target - vi) / DT, -c['b_s'], a_max)
            a_cmd[tr] = np.minimum(a_cmd[tr], at)
            # never cross well ahead of the slot
            Tg = self.tg[ti] - self.t
            early = (self.mode[ti] == 2) & (Tg > 0.3) & (di < 8.0) & (vi > 1.5 * di / np.maximum(Tg, 0.3))
            if early.any():
                a_cmd[tr] = np.where(early, np.minimum(a_cmd[tr], (1.5 * di / np.maximum(Tg, 0.3) - vi) / DT), a_cmd[tr])
            late = (self.mode[ti] == 2) & (self.tg[ti] < self.t)
            if late.any():
                a_cmd[tr] = np.where(late, np.minimum((self.vcap[ti] - vi) / DT, a_max), a_cmd[tr])
        # car following on the current lane order
        l = self.leader[idx]
        has = l >= 0
        if has.any():
            li = l[has]
            ii = idx[has]
            gap = self.odo[li] + self.off[ii] - self.odo[ii] - c['L']
            vl = self.v[li]
            vi = self.v[ii]
            bs, tr_ = c['b_s'], c['T_r']
            vsafe = -bs * tr_ + np.sqrt((bs * tr_) ** 2 + vl * vl + 2 * bs * np.maximum(gap - 0.5 * c['s0'], 0.0))
            asafe = (vsafe - vi) / DT
            acf = 0.3 * (gap - c['s0'] - vi * c['tau']) + 0.8 * (vl - vi)
            # a car holding a firm slot, or inside the box, flies its schedule under the safety filter alone
            md = self.mode[ii]
            inbox = (md == 3) & (self.odo[ii] < self.odo_box[ii])
            acf = np.where((md == 2) | inbox, asafe, np.minimum(acf, asafe))
            a_cmd[has] = np.minimum(a_cmd[has], acf)
        # sink capacity or blocked exit
        for lid, ready in self.sink_ready.items():
            pass
        hold = self.odo[idx] < self.hold[idx]
        hd = self.hold[idx] < 1e11
        if hd.any():
            dd = np.maximum(self.hold[idx] - self.odo[idx] - 0.3, 0.05)
            ah = np.where(hd, -v * v / (2 * dd), 0.0)
            a_cmd = np.where(hd & (v > 0.05), np.minimum(a_cmd, ah), a_cmd)
            a_cmd = np.where(hd & (v <= 0.05) & (dd < 1.0), 0.0, a_cmd)
        ya = self.yield_at[idx]
        yd = ya < 1e11
        if yd.any():
            dd = np.maximum(ya - self.odo[idx], 0.05)
            a_y = -(v * v) / (2 * dd)
            a_cmd = np.where(yd, np.minimum(a_cmd, a_y), a_cmd)
        st = self.stalled[idx]
        if st.any():
            a_cmd = np.where(st, -c['b_e'], a_cmd)
        a_cmd = np.maximum(a_cmd, -c['b_e'])
        vn = np.maximum(v + a_cmd * DT, 0.0)
        self.odo[idx] += 0.5 * (v + vn) * DT
        self.v[idx] = vn
        self.acc[idx] = a_cmd
        # metrics
        if self.t >= c['warm']:
            vref = np.maximum(self.vcap[idx], 1.0)
            self.m['loss'] += float(np.sum(1 - np.minimum(vn / vref, 1.0))) * DT
            self.m['loss'] += sum(len(q) for q in self.srcq.values()) * DT
            self.m['a2'] += float(np.sum(a_cmd * a_cmd))
            self.m['a2n'] += len(idx)
            moving = self.was_moving[idx]
            stopped = vn < 0.5
            self.m['stops'] += int(np.sum(moving & stopped))
            inbox = (self.mode[idx] == 3) & (self.odo[idx] < self.odo_box[idx]) & stopped & ~self.stalled[idx]
            self.m['box_block'] += float(np.sum(inbox)) * DT
        self.was_moving[idx] = np.where(vn > 2.0, True, np.where(vn < 0.5, False, self.was_moving[idx]))
        self.events_after_step(idx)

    def perceive(self):
        # independent of the schedule: a car that sees a foe body still inside a conflict it is about
        # to enter brakes for it if it can. Needs sensing, not messages.
        c = self.c
        self.yield_at[:] = 1e12
        for J in self.juncs.values():
            occ = []
            for x in J.out_lanes:
                for i in self.lanes[x].cars:
                    if self.mode[i] == 3 and self.alive[i]:
                        m = self.path_of.get(i)
                        if m is None:
                            continue
                        s = self.odo[i] - (self.odo_box[i] - m.P)
                        if s - c['L'] < m.P:
                            occ.append((i, m, s))
            if not occ:
                continue
            for i, m, s in occ:
                vi = float(self.v[i])
                for pid, f, r in m.conf:
                    if s - c['L'] >= r[1]:
                        continue
                    if s < r[0] - 0.5:
                        continue
                    t_clear = (r[1] + c['L'] - s) / max(vi, 0.5)
                    fm = J.movs[f]
                    rf = J.regions.get((f, m.id))
                    rf0 = rf[0][0] if rf else J.regions[m.id, f][1][0]
                    for q in fm.from_lane.cars + fm.to_lane.cars:
                        if q == i or self.path_of.get(q) is not fm or not self.alive[q] or self.mode[q] not in (2, 3):
                            continue
                        base = self.odo_line[q] if self.mode[q] == 2 else self.odo_box[q] - fm.P
                        at = base + rf0
                        to_conf = at - self.odo[q]
                        if to_conf <= 0.5 or to_conf > 80.0:
                            continue
                        vq = max(float(self.v[q]), 0.5)
                        if t_clear > to_conf / vq - 0.1 and to_conf >= float(self.v[q]) * c['T_r'] + float(self.v[q]) ** 2 / (2 * c['b_e']):
                            self.yield_at[q] = min(self.yield_at[q], at - 0.5)

    def plan_vc(self, ti):
        c = self.c
        v = self.v[ti]
        d = np.maximum(self.odo_line[ti] - self.odo[ti], 0.0)
        T = np.maximum(self.tg[ti] - self.t, 0.01)
        ve = self.vg[ti]
        a, b = c['a'], c['b_plan']
        lo = np.zeros(len(ti)) + 0.02
        hi = np.maximum(self.vcap[ti], 1.0)
        for _ in range(12):
            vc = 0.5 * (lo + hi)
            r1 = np.where(vc > v, a, b)
            r3 = np.where(ve > vc, a, b)
            D1 = np.abs(vc * vc - v * v) / (2 * r1)
            D3 = np.abs(ve * ve - vc * vc) / (2 * r3)
            rem = d - D1 - D3
            t = np.abs(vc - v) / r1 + np.abs(ve - vc) / r3 + rem / vc
            slow = np.where(rem >= 0, t > T, vc < np.maximum(v, ve))
            lo = np.where(slow, vc, lo)
            hi = np.where(slow, hi, vc)
        self.vc[ti] = 0.5 * (lo + hi)

    def events_after_step(self, idx):
        c = self.c
        # invariant: ungranted cars must be able to stop before the line
        ung = idx[self.mode[idx] < 2]
        if len(ung):
            d = self.odo_line[ung] - self.odo[ung]
            v = self.v[ung]
            need = v * c['T_r'] + v * v / (2 * c['b_s'])
            if not getattr(self, 'stall_list', None):
                self.m['invariant'] += int(np.sum((d < need - 0.5) & (v > 0.1)))
        # line crossing
        cross = idx[(self.mode[idx] < 3) & (self.odo[idx] >= self.odo_line[idx] - 1e-3)]
        for i in cross:
            self.cross_line(int(i))
        # box exit and lane end
        box = idx[(self.mode[idx] == 3) & (self.odo[idx] >= self.odo_box[idx])]
        for i in box:
            self.leave_box(int(i))
        end = idx[(self.mode[idx] == 4) & (self.odo[idx] >= self.odo_line[idx] - 0.5)]
        for i in end:
            self.reach_end(int(i))
        # a firm car that can no longer make its slot and can still stop aborts; past that point it flies on
        if self.step_i % 2 == 0:
            firm = idx[self.mode[idx] == 2]
            for i in firm:
                i = int(i)
                d = float(self.odo_line[i] - self.odo[i])
                v = float(self.v[i])
                T = self.tg[i] - self.t
                if T > 6.0:
                    continue
                stop_d = v * c['T_r'] + v * v / (2 * c['b_s'])
                if c['ponr'] and not self.armed[i] and d <= stop_d + 2.0:
                    # the exit must be clear at the point of no return, not only when the grant was issued
                    m = self.mov[i]
                    if self.exit_clear_now(m):
                        self.armed[i] = True
                        self.J_state[m.junction.id]['armed'][m.to_lane.id] += 1
                    elif d >= stop_d + 0.5:
                        self.abort(i)
                        self.m['ponr_abort'] += 1
                        continue
                te = earliest(max(d, 0.0), v, float(self.vg[i]), self.vcap[i], c['a'], c['b_plan'])
                if te is None:
                    te = d / max(v, 0.5) if d > 1.0 else 0.0
                if te <= T + 0.15:
                    continue
                if d >= v * c['T_r'] + v * v / (2 * c['b_s']) + 0.5:
                    self.abort(i)
                    self.m['late'] += 1
                else:
                    self.m['late_set'].add(i)

    def cross_line(self, i):
        c = self.c
        lane = self.lane[i]
        m = self.mov[i]
        if self.mode[i] != 2:
            if m is None:
                self.mode[i] = 4
                return
            self.m['invariant'] += 1
        if m is None:
            self.finish(i)
            return
        rec = self.grant_rec.pop(i, None)
        if self.armed[i]:
            self.armed[i] = False
            self.J_state[m.junction.id]['armed'][m.to_lane.id] -= 1
        if rec is not None:
            self.m['line_err'].append(self.t - rec[2])
            if self.c.get('debug'):
                self.lat = getattr(self, 'lat', {})
                self.lat[i] = self.t - rec[2]
            st = self.J_state[m.junction.id]
            st['committed'][m.to_lane.id] -= 1
        if i in lane.cars:
            lane.cars.remove(i)
        follower = lane.cars[0] if lane.cars else None
        self.mode[i] = 3
        self.odo_box[i] = self.odo_line[i] + m.P
        self.vcap[i] = min(m.vm, self.box_cap[i]) if self.box_cap[i] < 1e8 else m.vm
        self.box_cap[i] = 1e9
        x = m.to_lane
        # the exit lane's order is commit order; paths differ in length, so line-crossing order can differ
        at = len(x.cars)
        if rec is not None:
            # cars already past the box are physically ahead whatever their later grants say
            while at > 0 and self.mode[x.cars[at - 1]] == 3 and self.seq[x.cars[at - 1]] > self.seq[i]:
                at -= 1
        if at > 0:
            self.link_exit(i, x.cars[at - 1], x)
        else:
            self.leader[i] = -1
        if at < len(x.cars):
            self.link_exit(x.cars[at], i, x)
        x.cars.insert(at, i)
        self.lane[i] = x

    def link_exit(self, f, l, x):
        xl = self.exit_x(l, x)
        xf = self.exit_x(f, x)
        self.leader[f] = l
        self.off[f] = xl - xf - (self.odo[l] - self.odo[f])

    def exit_x(self, i, x):
        if self.mode[i] == 3 or self.odo_line[i] >= 1e11:
            return self.odo[i] - self.odo_box[i]
        return x.length - (self.odo_line[i] - self.odo[i])

    def leave_box(self, i):
        x = self.lane[i]
        self.vcap[i] = x.speed
        base = self.odo_box[i] + x.length
        self.odo_line[i] = base
        self.mode[i] = 0 if x.junction_end is not None else 4
        if x.junction_end is not None:
            self.mov[i] = self.pick_mov(x)
        else:
            self.mov[i] = None
        self.enter_t[i] = self.t

    def reach_end(self, i):
        x = self.lane[i]
        bl = self.c['exit_block']
        if bl is not None and bl[0] <= self.t < bl[1] and x.id.startswith(bl[2]):
            return
        cap = self.c['exit_cap']
        if cap is not None and x.id.startswith(cap[0]):
            if self.t < self.sink_ready.get(x.id, 0.0):
                return
            self.sink_ready[x.id] = self.t + 3600.0 / cap[1]
        self.finish(i)

    def finish(self, i):
        lane = self.lane[i]
        if i in lane.cars:
            lane.cars.remove(i)
        self.alive[i] = False
        self.leader[self.leader == i] = -1
        self.pending.pop(i, None)
        self.free.append(i)
        if self.t >= self.c['warm']:
            self.m['exited'] += 1
            self.m['exit_delays'].append(self.t - self.trip_t0[i])

    def apply_end_blocks(self):
        c = self.c
        bl, cap = c['exit_block'], c['exit_cap']
        if bl is None and cap is None:
            return
        for x in self.lanes.values():
            if x.junction_end is not None or not x.cars:
                continue
            head = x.cars[0]
            blocked = False
            if bl is not None and bl[0] <= self.t < bl[1] and x.id.startswith(bl[2]):
                blocked = True
            if cap is not None and x.id.startswith(cap[0]) and self.t < self.sink_ready.get(x.id, 0.0):
                blocked = True
            if self.mode[head] == 4:
                self.hold[head] = self.odo_line[head] - 0.3 if blocked else 1e12

    # ----- faults
    def stall_faults(self):
        c = self.c
        if c['stall_rate'] <= 0 or self.t < c['warm']:
            return
        if self.rng.random() >= c['stall_rate'] / 3600 * DT:
            return
        inbox = np.nonzero(self.alive & (self.mode == 3) & (self.odo < self.odo_box))[0]
        if len(inbox) == 0:
            return
        i = int(self.rng.choice(list(inbox)))
        self.stalled[i] = True
        self.m['stalls'] += 1
        rec_m = None
        for J in self.juncs.values():
            for l in J.lanes:
                pass
        self.stall_list = getattr(self, 'stall_list', [])
        self.stall_list.append((i, self.t + c['T_r'], self.t + c['stall_T']))

    def stall_response(self):
        c = self.c
        for rec in list(getattr(self, 'stall_list', [])):
            i, t_detect, t_end = rec
            if self.t < t_detect or not self.alive[i]:
                if not self.alive[i]:
                    self.stall_list.remove(rec)
                continue
            lane = self.lane[i]
            J = self.stall_junction(i)
            if J is None:
                continue
            st = self.J_state[J.id]
            st['freeze'] = True
            if self.t >= t_end:
                self.stalled[i] = False
                self.stall_list.remove(rec)
                self.hold[self.hold < 1e11] = 1e12
                continue
            sm = self.path_of.get(i)
            xs = self.odo[i] - self.odo_box[i]
            ss = xs + sm.P
            for mv in J.movs:
                crossing = (mv.id, sm.id) in J.regions or (sm.id, mv.id) in J.regions
                reg = J.regions.get((mv.id, sm.id))
                rs = reg[0][0] if reg else (J.regions[sm.id, mv.id][1][0] if crossing else None)
                for q in mv.from_lane.cars + mv.to_lane.cars:
                    if not self.alive[q] or q == i or self.path_of.get(q) is not mv:
                        continue
                    if self.mode[q] < 3:
                        base = self.odo_line[q]
                    elif self.mode[q] == 3 and self.odo[q] < self.odo_box[q]:
                        base = self.odo_box[q] - mv.P
                    else:
                        continue
                    vq = float(self.v[q])
                    d_brake = vq * c['T_r'] + vq * vq / (2 * c['b_e'])
                    # the stalled body on this car's own path, ahead of it
                    if mv.to_lane is sm.to_lane:
                        at = base + mv.P + xs - c['L'] - 1.0
                        if self.odo[q] < at + 1.0:
                            self.hold[q] = min(self.hold[q], at)
                    elif mv.from_lane is sm.from_lane and ss - c['L'] < J.div.get((sm.id, mv.id), (0.0,))[0]:
                        at = base + ss - c['L'] - 1.0
                        if self.odo[q] < at + 1.0:
                            self.hold[q] = min(self.hold[q], at)
                    elif crossing:
                        at = base + rs - 0.5
                        if self.odo[q] < at and at - self.odo[q] >= d_brake:
                            self.hold[q] = min(self.hold[q], at)
                    if self.mode[q] < 3 and self.odo_line[q] - self.odo[q] >= d_brake:
                        self.hold[q] = min(self.hold[q], self.odo_line[q] - 0.5)
                        if self.mode[q] == 2:
                            self.abort(q)
        for J in self.juncs.values():
            st = self.J_state[J.id]
            if st.get('freeze') and not any(self.alive[i] and self.stalled[i] for i in range(0)):
                busy = getattr(self, 'stall_list', None) and any(self.stall_junction(r[0]) is J for r in self.stall_list)
                if not busy and not self.box_occupied(J):
                    st['freeze'] = False

    def stall_junction(self, i):
        m = self.path_of.get(i)
        return m.junction if m is not None else None

    def box_occupied(self, J):
        for x in J.out_lanes:
            for q in self.lanes[x].cars:
                if self.alive[q] and self.mode[q] == 3 and self.odo[q] < self.odo_box[q]:
                    return True
        return False

    # ----- audit
    def audit(self):
        c = self.c
        pairs_new = 0
        for J in self.juncs.values():
            ids = []
            for x in J.out_lanes:
                for i in self.lanes[x].cars:
                    if self.mode[i] == 3 and self.odo[i] < self.odo_box[i] + c['L'] + 1 and self.alive[i]:
                        ids.append(i)
            if len(ids) < 2:
                continue
            poly = {}
            for i in ids:
                m = self.movs_by_car(i)
                if m is None:
                    continue
                s = self.odo[i] - (self.odo_box[i] - m.P)
                poly[i] = rect_on_path(m, s, c)
            keys = list(poly)
            for a in range(len(keys)):
                for b in range(a + 1, len(keys)):
                    i, j = keys[a], keys[b]
                    if overlap(poly[i], poly[j]):
                        key = (min(i, j), max(i, j), int(self.t // 10))
                        if key not in self.m['overlap_pairs']:
                            self.m['overlap_pairs'].add(key)
                            self.m['overlap'] += 1
                            if self.c.get('debug'):
                                mi, mj = self.path_of[i], self.path_of[j]
                                print('OVERLAP t', round(self.t, 1), 'dirs', mi.dir, mj.dir, mi.id, mj.id, 'pair', (mi.id, mj.id) in J.regions or (mj.id, mi.id) in J.regions,
                                      'same-in', mi.from_lane is mj.from_lane, 'same-out', mi.to_lane is mj.to_lane,
                                      's', round(float(self.odo[i] - (self.odo_box[i] - mi.P)), 1), round(float(self.odo[j] - (self.odo_box[j] - mj.P)), 1),
                                      'v', round(float(self.v[i]), 1), round(float(self.v[j]), 1), 'lat', round(float(self.lat.get(i, 0)), 2), round(float(self.lat.get(j, 0)), 2))

    def movs_by_car(self, i):
        return self.path_of.get(i)

    def run(self):
        c = self.c
        self.path_of = {}
        n_steps = int(c['end'] / DT)
        for s in range(n_steps):
            self.t = s * DT
            self.step_i = s
            self.insert()
            if self.t >= self.next_tick:
                self.tick()
                self.next_tick += c['tick']
            self.messages()
            self.apply_end_blocks()
            self.stall_faults()
            self.stall_response()
            self.remember_paths()
            if c['perception']:
                self.perceive()
            self.step()
            if c['audit']:
                self.audit()
            if self.trace is not None and s % 2 == 0:
                self.write_trace()
            if self.q_at_warm is None and self.t >= c['warm']:
                self.q_at_warm = self.queue_now()
            if s % 10 == 0 and self.t >= c['warm']:
                self.m['peakq'] = max(self.m['peakq'], self.queue_now())
        return self.results()

    def remember_paths(self):
        # the auditor needs the path each car actually took; kept outside the movement slot which advances
        for i in np.nonzero(self.alive & (self.mode < 3))[0]:
            m = self.mov[i]
            if m is not None:
                self.path_of[int(i)] = m

    def queue_now(self):
        n = sum(len(q) for q in self.srcq.values())
        return n + int(np.sum(self.alive & (self.v < 2.0)))

    def write_trace(self):
        idx = np.nonzero(self.alive)[0]
        rows = [[round(self.t, 1), int(i), self.lane[i].id, int(self.mode[i]), round(float(self.odo[i]), 2),
                 round(float(self.odo_line[i]), 2), round(float(self.v[i]), 2)] for i in idx]
        self.trace.write('\n'.join(json.dumps(r) for r in rows) + '\n')

    def results(self):
        c = self.c
        m = self.m
        span = c['end'] - c['warm']
        pend = sum(len(q) for q in self.srcq.values()) + int(np.sum(self.alive))
        delays = np.array(m['exit_delays']) if m['exit_delays'] else np.array([0.0])
        err = np.array(m['line_err']) if m['line_err'] else np.array([0.0])
        return dict(flow=m['exited'] * 3600 / span, offered=m['offered'] * 3600 / span,
                    delay=m['loss'] / max(m['offered'], 1), stops=m['stops'] / max(m['exited'], 1),
                    p95=float(np.percentile(delays, 95)), trip=float(delays.mean()), pending=pend,
                    growth=(self.queue_now() - (self.q_at_warm or 0)) / span * 3600,
                    overlap=m['overlap'], invariant=m['invariant'], late=m['late'], late_committed=len(m['late_set']), aborts=m['aborts'],
                    rms_a=math.sqrt(m['a2'] / max(m['a2n'], 1)), peakq=m['peakq'], grants=m['grants'],
                    err_p99=float(np.percentile(np.abs(err), 99)), err_mean=float(err.mean()), stalls=m['stalls'],
                    p99=float(np.percentile(delays, 99)), box_block=m['box_block'], ponr_abort=m['ponr_abort'])


def rect_on_path(m, s, c):
    f = point_at(m, s)
    r = point_at(m, s - c['L'])
    ax = f - r
    n = math.hypot(*ax)
    if n < 1e-6:
        ax = np.array([1.0, 0.0])
        n = 1.0
    u = ax / n
    p = np.array([-u[1], u[0]]) * c['W'] / 2
    return np.array([f + p, f - p, r - p, r + p])


def point_at(m, s):
    if s <= 0:
        u = m.xy[1] - m.xy[0]
        u = u / max(np.hypot(*u), 1e-9)
        return m.xy[0] + u * s
    if s >= m.P:
        u = m.xy[-1] - m.xy[-2]
        u = u / max(np.hypot(*u), 1e-9)
        return m.xy[-1] + u * (s - m.P)
    t = s / 0.25
    i = min(int(t), len(m.xy) - 2)
    return m.xy[i] + (m.xy[i + 1] - m.xy[i]) * (t - i)


def overlap(a, b):
    for poly in (a, b):
        for i in range(2):
            e = poly[(i + 1) % 4] - poly[i]
            ax = np.array([-e[1], e[0]])
            pa, pb = a @ ax, b @ ax
            if pa.max() <= pb.min() or pb.max() <= pa.min():
                return False
    return True


def run_cfg(over):
    c = default_cfg()
    c.update(over)
    if c['policy'] == 'sig_h':
        for k, v in HUMAN.items():
            c.setdefault(k, v)
            c[k] = over.get(k, v)
    t0 = time.time()
    r = Sim(c).run()
    r['wall'] = time.time() - t0
    return r


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        for pol in ('sig_h', 'sig_av', 'fcfs_box', 'fcfs_conf', 'ges', 'wspt', 'poll'):
            r = run_cfg(dict(policy=pol, net='j1', demand=1200, end=500, warm=100))
            print(pol, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
