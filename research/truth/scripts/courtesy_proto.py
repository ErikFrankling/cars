"""CPU prototype of the courtesy spec in 14-human-courtesy.md, on the same geometries as courtesy_sumo.py and courtesy_sumo_signal.py.
It is a mechanism test: Krauss following at 1 s, instantaneous lane changes, the spec's yield, gap and fallback rules. Not a validation of the GPU code.
Usage: courtesy_proto.py merge NAME MAIN RAMP NECK [SEED] | signal NAME APPROACH VPH SPILL [SEED] | hold NAME [SEED]; add off=1 for no courtesy."""
import sys, json, math, pathlib
import numpy as np

P = dict(tau=1.0, b=4.5, a=2.6, sigma=0.5, L=5.0, mingap=2.5, dt=1.0,
         # yield logit, fitted on I-80 (courtesy_merge_summary.py) with the constant shifted by c0 to count only requested let-ins
         b0=2.14, b_v=1.73, b_close=-1.44, b_lag=1.24, b_rem=-2.08, rem_cap=200.0,
         # share of the unit logistic noise given to the driver and to the pair
         s_driver=0.7, s_pair=0.7,
         # signal stage
         sig_react=1.0, p_sig_before=0.60, p_sig_late=0.33, nosignal_eta=-1.0,
         # urgency and gap shrink
         R_urg=100.0, T_u0=30.0, T_u1=90.0, tau_min=0.3, b_em=7.5, s_min=0.5,
         # yield effect
         b_yield=1.5, b_yield_max=3.0,
         # guarantee
         T_force=90.0, T_miss=120.0, head_only=False, T_swap=5.0)


def h(a, b=0):
    x = (a * 2654435761 + b * 40503 + 12345) & 0xffffffff
    x ^= x >> 16; x = (x * 2246822519) & 0xffffffff; x ^= x >> 13; x = (x * 3266489917) & 0xffffffff; x ^= x >> 16
    return (x + 0.5) / 4294967296.0


def logistic(u): return math.log(u / (1 - u))


class Car:
    __slots__ = ('i', 'lane', 'pos', 'v', 'need', 'wait', 'sig', 'lc_wait', 't0', 'tlc', 'lagseen', 'passes', 'stopwrong', 'wtime', 'done', 'kind', 'last', 'missed', 'first_wrong')

    def __init__(s, i, lane, pos, v, need, t0, kind):
        s.i, s.lane, s.pos, s.v, s.need, s.t0, s.kind = i, lane, pos, v, need, t0, kind
        s.wait = 0.0; s.sig = 0.0; s.lc_wait = 0.0; s.tlc = None; s.lagseen = []; s.passes = 0; s.stopwrong = 0.0; s.wtime = 0.0; s.done = False; s.last = None; s.missed = False; s.first_wrong = None


def follow(v, vl, g):
    g = max(g, 0.0)
    tb = P['tau'] * P['b']
    return max(0.0, -tb + math.sqrt(tb * tb + vl * vl + 2 * P['b'] * g))


class Sim:
    def __init__(s, nlanes, off, seed):
        s.lanes = [[] for _ in range(nlanes)]; s.off = off; s.adv = {}; s.t = 0.0; s.cross = []; s.coll = 0; s.hard = 0; s.commits = []; s.yields = 0; s.requests = 0; s.seed = seed; s.overlaps = []
        s.misses = 0; s.teleports = 0; s.cars = []; s.swaps = 0

    def add(s, c):
        s.lanes[c.lane].append(c); s.cars.append(c)

    def neighbours(s, lane, c):
        lag = lead = None
        for o in s.lanes[lane]:
            if o.pos <= c.pos and (lag is None or o.pos > lag.pos): lag = o
            if o.pos > c.pos and (lead is None or o.pos < lead.pos): lead = o
        return lag, lead

    def urgency(s, c, rem):
        u1 = max(0.0, 1.0 - rem / P['R_urg'])
        u2 = max(0.0, min(1.0, (c.lc_wait - P['T_u0']) / (P['T_u1'] - P['T_u0'])))
        return max(u1, u2)

    def gap_needed(s, vf, vl, u, c):
        # driver's own tau at no urgency, the physical limit at full urgency. Some drivers start nearer the limit.
        k = 0.7 + 0.6 * h(c.i, 7)
        tau_e = P['tau'] * k * (1 - u) + P['tau_min'] * u
        b_e = P['b'] * (1 - u) + P['b_em'] * u
        return P['s_min'] + (P['mingap'] - P['s_min']) * (1 - u) + max(0.0, vf * tau_e + (vf * vf - vl * vl) / (2 * b_e))

    def try_change(s, c, target, rem):
        lag, lead = s.neighbours(target, c)
        u = s.urgency(c, rem)
        if not s.off and P['T_swap'] > 0 and c.lc_wait >= P['T_swap']:
            # counter-wish: side by side and each wants the other's lane, after both have waited. Exchange lanes.
            for o in (lag, lead):
                if o is not None and abs(o.pos - c.pos) < P['L'] and o.lc_wait >= P['T_swap'] and o.need is not None and o.lane != o.need:
                    d_o = 1 if o.need > o.lane else -1
                    if o.lane + d_o == c.lane:
                        ok = True
                        for q, tl in ((c, o.lane), (o, c.lane)):
                            for x in s.lanes[tl]:
                                if x is c or x is o: continue
                                if abs(x.pos - q.pos) < P['L'] + P['s_min']: ok = False
                        if ok:
                            s.lanes[c.lane].remove(c); s.lanes[o.lane].remove(o)
                            c.lane, o.lane = o.lane, c.lane
                            s.lanes[c.lane].append(c); s.lanes[o.lane].append(o)
                            c.lc_wait = 0.0; o.lc_wait = 0.0; c.sig = 0.0; o.sig = 0.0; c.tlc = s.t; o.tlc = s.t; s.swaps += 1
                            return True
        back = c.pos - P['L']
        lg = (back - lag.pos) if lag else 1e9
        ld = (lead.pos - P['L'] - c.pos) if lead else 1e9
        if not s.off:
            need_lag = s.gap_needed(lag.v, c.v, u, c) if lag else -1e9
            need_lead = s.gap_needed(c.v, lead.v, u, c) if lead else -1e9
        else:
            # LC2013-like fixed secure gap: no time term, no yield
            need_lag = P['mingap'] + max(0.0, lag.v * P['tau'] + (lag.v ** 2 - c.v ** 2) / (2 * P['b'])) if lag else -1e9
            need_lead = P['mingap'] + max(0.0, c.v * P['tau'] + (c.v ** 2 - lead.v ** 2) / (2 * P['b'])) if lead else -1e9
        if lg >= need_lag and ld >= need_lead:
            s.lanes[c.lane].remove(c); c.lane = target; s.lanes[target].append(c); c.tlc = s.t; c.lc_wait = 0.0; c.sig = 0.0
            s.commits.append((s.t, lg if lag else None, ld if lead else None, c.v))
            return True
        if s.off or lag is None: return False
        # only the car at the head of its own queue, or one moving freely, asks. A car behind others would stop the target lane for nothing.
        if P['head_only']:
            own_ahead = [o for o in s.lanes[c.lane] if o.pos > c.pos and o.pos - P['L'] - c.pos < 8.0]
            if own_ahead: return False
        # a car alongside, or too close to ever fit behind, can only pass: holding it would block the very space that is needed
        if lg <= P['s_min'] + 0.2: return False
        # request: the lag vehicle decides, drawn once per pair so a car is not asked again every step
        if c.sig < P['sig_react'] and not (h(c.i, 3) > P['p_sig_before'] + P['p_sig_late']): return False
        s.requests += 1
        eta = P['b0'] + P['b_v'] * lag.v / 10 + P['b_close'] * (lag.v - c.v) / 3 + P['b_lag'] * max(lg, -5) / 10 + P['b_rem'] * min(rem, P['rem_cap']) / 50
        if h(c.i, 3) > P['p_sig_before'] + P['p_sig_late']: eta += P['nosignal_eta']
        forced = c.lc_wait >= P['T_force']
        z = P['s_driver'] * logistic(h(lag.i, 1)) + P['s_pair'] * logistic(h(lag.i, c.i + 1))
        if not forced and z > eta + 6.0 * max(0.0, (c.lc_wait - P['T_u0'] * 2) / P['T_u0']): return False
        s.yields += 1
        by = P['b_yield'] + (P['b_yield_max'] - P['b_yield']) * u
        target_v = follow(lag.v, c.v, lg - P['s_min'] - 0.5)
        cap = max(target_v, lag.v - by * P['dt'], 0.0) if not forced else max(target_v, lag.v - P['b'] * P['dt'], 0.0)
        s.adv[lag.i] = min(s.adv.get(lag.i, 1e9), cap)
        return False


def step_lane(sim, lane, end_of, vmax_of, stop_at=None):
    cars = sorted(sim.lanes[lane], key=lambda x: -x.pos)
    lead = None
    for c in cars:
        vm = vmax_of(c.pos)
        v = min(vm, c.v + P['a'] * P['dt'])
        if lead is not None:
            g = lead.pos - P['L'] - c.pos - P['mingap']
            v = min(v, follow(c.v, lead.v, g))
        end = end_of(c)
        if end is not None:
            v = min(v, follow(c.v, 0.0, end - c.pos - 0.5))
        if c.i in sim.adv: v = min(v, sim.adv[c.i])
        v = max(v, 0.0)
        if v > 0.1 and P['sigma'] > 0:
            v = max(0.0, v - P['sigma'] * P['a'] * P['dt'] * np.random.random())
        if lead is not None:
            v = min(v, max(0.0, (lead.pos + lead.v * P['dt'] - P['L'] - c.pos) / P['dt'] - 1e-3))
        if c.v - v > P['b_em'] * P['dt'] + 1e-6: sim.hard += 1
        c.v = v; c.pos += v * P['dt']
        c.wait = c.wait + P['dt'] if v < 0.1 else 0.0
        if lead is not None and lead.pos - P['L'] - c.pos < -1e-6: sim.coll += 1
        lead = c
    sim.adv = {k: v for k, v in sim.adv.items() if False} if lane == -1 else sim.adv


def summarize(sim, wrong, name, extra):
    w = np.array([x for x in wrong], float)
    return dict(name=name, off=sim.off, **extra, collisions=sim.coll, decel_over_limit=sim.hard, requests=sim.requests, yields=sim.yields, commits=len(sim.commits))


def run_merge(name, main, ramp, neck, seed, off, T=1800):
    np.random.seed(seed)
    sim = Sim(2, off, seed)
    # lane 0 ramp lane, lane 1 main; ramp cars may change on [800,1004] and must stop at 1004
    t = 0.0; nid = 0; next_m = 0.0; next_r = 0.0; rcars = []
    def vmax_of(x): return neck if 1304 <= x < 1404 else 20.0
    while t < T + 1200:
        sim.t = t
        if t < T:
            if t >= next_m:
                ok = all(o.pos > 30 for o in sim.lanes[1])
                if ok:
                    sim.add(Car(nid, 1, 0.0, 15.0, 1, t, 'main')); nid += 1; next_m = t + 3600.0 / main
            if t >= next_r:
                ok = all(o.pos > 30 for o in sim.lanes[0])
                if ok:
                    c = Car(nid, 0, 0.0, 15.0, 1, t, 'ramp'); sim.add(c); rcars.append(c); nid += 1; next_r = t + 3600.0 / ramp
        sim.adv = {}
        for c in list(sim.lanes[0]):
            if c.pos < 800: continue
            if c.first_wrong is None: c.first_wrong = t
            c.sig += P['dt']; c.lc_wait += P['dt']
            rem = 1004 - c.pos
            # queue membership is visible on lag vehicles
            lag, _ = sim.neighbours(1, c)
            if lag is not None and lag.i not in c.lagseen: c.lagseen.append(lag.i)
            sim.try_change(c, 1, rem)
        step_lane(sim, 0, lambda c: 1004.0, vmax_of)
        step_lane(sim, 1, lambda c: None, vmax_of)
        for c in list(sim.lanes[1]):
            if c.pos >= 1100 and c.last is None:
                c.last = t; sim.cross.append((t, c.kind))
            if c.pos > 2000: sim.lanes[1].remove(c); c.done = True
        for c in sim.lanes[0]:
            if c.wait > 120: sim.teleports += 1; c.wait = 0.0
        t += P['dt']
    W = np.array([c.tlc - c.first_wrong for c in rcars if c.tlc is not None and c.first_wrong is not None])
    a = np.array([k == 'ramp' for _, k in sorted(sim.cross)], bool); idx = np.where(a)[0]; rl = np.diff(idx) - 1 if len(idx) > 1 else np.array([0])
    return dict(name=name, off=off, seed=seed, main=main, ramp=ramp, neck=neck, ramp_cars=len(rcars), never=sum(c.tlc is None for c in rcars), wait={k: round(float(np.percentile(W, p)), 1) for k, p in (('p10', 10), ('p50', 50), ('p90', 90), ('p99', 99))}, wait_max=float(W.max()),
                main_between_ramp={int(k): int((rl == k).sum()) for k in range(8)}, rl_mean=round(float(rl.mean()), 2), flow_vph=round(len(sim.cross) / T * 3600), collisions=sim.coll, decel_over_limit=sim.hard, wait_over_120=sim.teleports, requests=sim.requests, yields=sim.yields,
                lag_commit=np.round(np.percentile([x[1] for x in sim.commits if x[1] is not None], [5, 25, 50]), 2).tolist() if sim.commits else [], lead_commit=np.round(np.percentile([x[2] for x in sim.commits if x[2] is not None], [5, 25, 50]), 2).tolist() if sim.commits else [])


def run_signal(name, La, vph, spill, seed, off, T=1800):
    np.random.seed(seed)
    sim = Sim(3, off, seed)
    # up to 150 m, approach to 150+La, signal at the end with a 90 s cycle, 40 s green. Lane 1 feeds a through edge that may spill back.
    end = 150.0 + La; nid = 0; rng = np.random.default_rng(seed)
    arr = np.sort(rng.uniform(0, T, int(vph * T / 3600)))
    k = 0; t = 0.0; waiting = []
    all_c = []
    def vmax_of(x):
        return 13.9
    downstream = [[], [], []]
    while t < T + 1200:
        sim.t = t
        green = (t % 90) < 40
        while k < len(arr) and arr[k] <= t:
            need = 2 if rng.random() < .3 else (0 if rng.random() < 2 / 7 else 1)
            waiting.append((nid, need)); nid += 1; k += 1
        for j in list(waiting):
            l = int(rng.integers(0, 3))
            if all(o.pos > 12 for o in sim.lanes[l]):
                c = Car(j[0], l, 5.0, 10.0, j[1], t, 'x'); sim.add(c); all_c.append(c); waiting.remove(j)
        sim.adv = {}
        for c in sorted([x for L in sim.lanes for x in L], key=lambda x: -x.pos):
            if c.lane != c.need:
                c.wtime += P['dt']
                if c.v < 0.1: c.stopwrong += P['dt']
                c.sig += P['dt']; c.lc_wait += P['dt']
                tgt = c.lane + (1 if c.need > c.lane else -1)
                rem = (end - c.pos) / abs(c.need - c.lane)
                sim.try_change(c, tgt, rem)
                # missed turn: own lane moves on when the signal is green and the target has not opened for T_miss
                if c.lane != c.need and c.wait >= P['T_miss'] and end - c.pos < 15.0 and green and not off:
                    c.need = c.lane; c.missed = True; sim.misses += 1
        # through lane capacity at the stop line when spilling: 1 car per 8 s beyond the first 300 m; left and right run free
        for l in range(3):
            step_lane(sim, l, lambda c, l=l: (end if (not green or (l == 1 and len(downstream[1]) >= 40)) or c.lane != c.need else None) if c.pos <= end else None, vmax_of)
            for c in list(sim.lanes[l]):
                if c.pos >= end:
                    sim.lanes[l].remove(c); c.done = True
                    downstream[l].append(c)
                elif c.wait > 120 and not off:
                    pass
                elif c.wait > 120:
                    if c.lane != c.need and off:
                        sim.teleports += 1; sim.lanes[l].remove(c); c.done = True; downstream[l].append(c)
        if spill and downstream[1] and t % 4 < P['dt']: downstream[1].pop(0)
        if not spill: downstream[1].clear()
        downstream[0].clear(); downstream[2].clear()
        t += P['dt']
    wt = np.array([c.wtime for c in all_c if c.wtime > 0] or [0.0]); sw = np.array([c.stopwrong for c in all_c] or [0.0])
    return dict(name=name, off=off, seed=seed, approach=La, vph=vph, spill=spill, cars=len(all_c), unfinished=sum(not c.done for c in all_c), wrong_time=dict(p50=float(np.percentile(wt, 50)), p90=float(np.percentile(wt, 90)), p99=float(np.percentile(wt, 99)), max=float(wt.max())),
                stopped_wrong=dict(p90=float(np.percentile(sw, 90)), p99=float(np.percentile(sw, 99)), max=float(sw.max())), share_stopped_wrong=round(float((sw > 0).mean()), 3), wrong_lane_teleports=sim.teleports, missed_turns=sim.misses, swaps=sim.swaps, collisions=sim.coll, decel_over_limit=sim.hard, requests=sim.requests, yields=sim.yields)


def run_hold(name, seed, off):
    """No physical solution for the first 300 s: the target lane stands still. It must stay collision free, then clear after the lane moves."""
    np.random.seed(seed)
    sim = Sim(2, off, seed)
    for i in range(30): sim.add(Car(i, 1, 400 - i * 7.6, 0.0, 1, 0.0, 'main'))
    m = Car(99, 0, 300.0, 0.0, 1, 0.0, 'ramp'); sim.add(m)
    commit = None; t = 0.0
    while t < 900:
        sim.t = t; sim.adv = {}
        m.sig += 1; m.lc_wait += 1
        if m.lane == 0: sim.try_change(m, 1, 5.0)
        if m.lane == 1 and commit is None: commit = t
        step_lane(sim, 0, lambda c: 305.0, lambda x: 13.9)
        step_lane(sim, 1, lambda c: 401.0 if sim.t < 300 else None, lambda x: 13.9)
        t += 1
    return dict(name=name, off=off, commit_time=commit, collisions=sim.coll, decel_over_limit=sim.hard)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith(('off=', 'swap='))]; off = any(x == 'off=1' for x in sys.argv)
    if any(x == 'swap=0' for x in sys.argv): P['T_swap'] = 0.0; a[1] += '_noswap'
    if a[0] == 'merge': r = run_merge(a[1], int(a[2]), int(a[3]), float(a[4]), int(a[5]) if len(a) > 5 else 7, off)
    elif a[0] == 'signal': r = run_signal(a[1], int(a[2]), int(a[3]), int(a[4]), int(a[5]) if len(a) > 5 else 7, off)
    else: r = run_hold(a[1], int(a[2]) if len(a) > 2 else 7, off)
    p = pathlib.Path('research/truth/courtesy/proto'); p.mkdir(exist_ok=True); (p / (r['name'] + ('_off' if off else '') + '.json')).write_text(json.dumps(r, indent=1)); print(json.dumps(r))
