"""Where and when a replay area locks, from a `cars run --trace --why` trace (research/truth/replay/LOCK.md).

    python3 -I scripts/replay/lock_chain.py holds TRACE ROUTES [--min 60] [--sim-only]
        every stop of a simulated car of at least --min seconds, first first: where, how long, what held it
        (share of ticks by decider), whom it blamed at the start, and the junction it stood before
    python3 -I scripts/replay/lock_chain.py timeline TRACE ROUTES [--min 60] [--step 30]
        cars standing at least --min seconds, by junction, every --step seconds
    python3 -I scripts/replay/lock_chain.py car TRACE CAR [--begin T] [--end T]
        one car tick by tick: lane, pos, speed, decider, blame, closed link and foe, link state
"""
import os, sys, json
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import numpy as np
from dbg.run import Run, KINDS, CLOSED, NONE32, denial, trips_of, lanes_of, pos_of, speeds_of, blame_text, link_state

HALT = 0.1


def sim_trips(routes):
    import xml.etree.ElementTree as ET
    return {v.get('id') for v in ET.parse(routes).getroot().iter('vehicle') if v.get('type') == 'drv'}


def arg(name, default):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return type(default)(sys.argv[i + 1])
    return default


def series(run, keep=None):
    """Per trip: arrays of frame index, lane, pos, speed, decider, blame, closed, foe_trip, first_link."""
    out = defaultdict(lambda: defaultdict(list))
    for i in range(len(run.frames)):
        rec, why = run.read(i)
        tr = trips_of(rec)
        ln, ps, sp = lanes_of(rec), pos_of(rec), speeds_of(rec)
        for k in range(len(rec)):
            name = run.name(tr[k])
            if keep is not None and name not in keep:
                continue
            d = out[name]
            d['i'].append(i); d['lane'].append(int(ln[k])); d['pos'].append(float(ps[k])); d['v'].append(float(sp[k]))
            if why is not None and len(why) == len(rec):
                w = why[k]
                d['dec'].append(int(w['decider'])); d['blame'].append(int(w['blame'])); d['closed'].append(int(w['closed']))
                d['foe'].append(int(w['foe_trip'])); d['link'].append(int(w['first_link'])); d['deny'].append(denial(run, w) or '')
            else:
                d['deny'].append('')
                for c in ('dec', 'blame', 'closed', 'foe', 'link'):
                    d[c].append(NONE32 if c in ('blame', 'foe', 'link') else 0)
    return {k: {c: np.array(v) for c, v in d.items()} for k, d in out.items()}


def stops(d, times, min_s):
    """(first, last) row of every run of standing at least min_s seconds."""
    st = d['v'] < HALT
    out, a = [], None
    for r in range(len(st) + 1):
        if r < len(st) and st[r]:
            if a is None:
                a = r
        elif a is not None:
            if times[d['i'][r - 1]] - times[d['i'][a]] >= min_s:
                out.append((a, r - 1))
            a = None
    return out


def holds(trace, routes, min_s):
    run = Run(trace)
    sims = sim_trips(routes)
    S = series(run, sims)
    T = run.times
    rows = []
    for name, d in S.items():
        for a, b in stops(d, T, min_s):
            dec = Counter(KINDS[x] if x < len(KINDS) else '?' for x in d['dec'][a:b + 1])
            lane = d['lane'][a]
            j = run.net.junction_of_lane(lane)
            first_blame = next((blame_text(run, d['blame'][r]) for r in range(a, b + 1) if d['blame'][r] != NONE32), '')
            closed = Counter(CLOSED[c] for c in d['closed'][a:b + 1] if c)
            foes = Counter(run.name(f) for f, c in zip(d['foe'][a:b + 1], d['closed'][a:b + 1]) if c == 3 and f != NONE32)
            foes.update(x for x in d['deny'][a:b + 1] if x)
            rows.append(dict(car=name, t0=float(T[d['i'][a]]), t1=float(T[d['i'][b]]), held=float(T[d['i'][b]] - T[d['i'][a]]),
                             to_end=bool(d['i'][b] == len(T) - 1), lane=run.net.lane_name(lane), pos=round(float(d['pos'][a]), 1),
                             lane_len=round(float(run.net.lane_length[lane]), 1), junction=j,
                             deciders={k: round(v / (b - a + 1), 2) for k, v in dec.most_common(4)}, first_blame=first_blame,
                             closed=dict(closed), foes=dict(foes.most_common(3))))
    rows.sort(key=lambda r: r['t0'])
    return rows


def timeline(trace, routes, min_s, step):
    run = Run(trace)
    sims = sim_trips(routes)
    S = series(run, sims)
    T = run.times
    held = defaultdict(lambda: Counter())
    for name, d in S.items():
        for a, b in stops(d, T, min_s):
            j = run.net.junction_of_lane(d['lane'][a])
            t_from = T[d['i'][a]] + min_s
            for t in np.arange(np.ceil(t_from / step) * step, T[d['i'][b]] + 1e-6, step):
                held[float(t)][j] += 1
    return held


def car(trace, name, begin, end):
    run = Run(trace)
    tr = run.trip(name)
    for i in run.window(begin, end):
        rec, why = run.read(i)
        hit = np.nonzero(trips_of(rec) == tr)[0]
        if not len(hit):
            continue
        k = hit[0]
        ln = int(lanes_of(rec)[k])
        s = f'{run.times[i]:8.1f} {run.net.lane_name(ln):28s} {pos_of(rec)[k]:6.1f} v {speeds_of(rec)[k]:5.2f}'
        if why is not None and len(why) == len(rec):
            w = why[k]
            s += f'  {KINDS[w["decider"]]:12s} {blame_text(run, w["blame"]):40s}'
            if denial(run, w):
                s += f' DENIED {denial(run, w)}'
            if w['closed']:
                s += f' closed {CLOSED[w["closed"]]} foe {run.name(w["foe_trip"]) if w["foe_trip"] != NONE32 else "-"}'
            if w['first_link'] != NONE32:
                s += f' [{run.net.link_name(w["first_link"])} {link_state(run, i, w["first_link"])}]'
            if w['leader'] != NONE32:
                s += f' L {run.name(w["leader"])} {w["leader_gap"]:.1f}'
        print(s)


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'holds':
        rows = holds(sys.argv[2], sys.argv[3], arg('--min', 60.0))
        if '--json' in sys.argv:
            print(json.dumps(rows, indent=0))
        else:
            for r in rows:
                print(f"{r['t0']:8.0f} {r['held']:5.0f}{'*' if r['to_end'] else ' '} {r['car']:12s} {r['lane']:18s} {r['pos']:5.1f}/{r['lane_len']:5.1f} "
                      f"{r['junction'][:28]:28s} {r['deciders']} {r['first_blame']} {r['closed'] or ''} {r['foes'] or ''}")
    elif c == 'timeline':
        held = timeline(sys.argv[2], sys.argv[3], arg('--min', 60.0), arg('--step', 30.0))
        for t in sorted(held):
            print(f'{t:8.0f} {sum(held[t].values()):4d}  ' + '  '.join(f'{j[:22]} {n}' for j, n in held[t].most_common(6)))
    elif c == 'car':
        car(sys.argv[2], sys.argv[3], arg('--begin', 0.0) or None, arg('--end', 0.0) or None)
