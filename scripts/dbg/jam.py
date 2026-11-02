"""`cars jam`: from a stuck car or a congested road, walk who waits for whom back to the first cause. `--seeds` ranks them over a run."""
import argparse
import json
import os

import numpy as np

from .run import BLAME_LANE, BLAME_LINK, HALT, K, KINDS, NONE32, Run, blame_text, flags_of, lanes_of, lc_words, link_state, pos_of, prevs_of, speeds_of, trips_of, waits_of

# Reasons where the car holds still for something it names.
ROOT_KINDS = {K['signal']: 'signal', K['lane_end']: 'needs another lane', K['arrival']: 'arrival', K['free']: 'free', K['accel']: 'accelerating', K['next_limit']: 'limit', K['curve']: 'curve',
              K['dawdle']: 'dawdling', K['lane_change']: 'lane change', K['committed']: 'committed', K['brake_limit']: 'braking', K['power']: 'power', K['coordinator']: 'coordinator'}


class Frame:
    """One frame's waiting graph. next[i] is the record this record waits for, -1 if it names no car."""

    def __init__(self, run, i, stopped_speed=0.5):
        self.run, self.i = run, i
        self.rec, self.why = run.read(i)
        rec, why = self.rec, self.why
        self.n = len(rec)
        self.trips = trips_of(rec)
        self.lanes = lanes_of(rec)
        self.pos = pos_of(rec)
        self.v = speeds_of(rec)
        self.wait = waits_of(rec)
        self.flags = flags_of(rec)
        self.stopped = (self.v < stopped_speed) & ((self.flags & 6) == 0)
        self.kind = np.zeros(self.n, dtype=int) if why is None else why['plan'].astype(int).copy()
        if why is not None:
            # The decider says when a limit other than the plan's own moved the speed; waiting cars are the plan's.
            self.dec = why['decider'].astype(int)
        else:
            self.dec = self.kind
        self.next = np.full(self.n, -1, dtype=np.int64)
        order = np.argsort(self.trips)
        self._sorted_trips = self.trips[order]
        self._order = order
        if why is None:
            self._infer_same_lane()
        else:
            self._from_why()

    def lookup(self, trips):
        at = np.searchsorted(self._sorted_trips, trips)
        at = np.minimum(at, max(self.n - 1, 0))
        good = self._sorted_trips[at] == trips if self.n else np.zeros(len(trips), dtype=bool)
        out = np.full(len(trips), -1, dtype=np.int64)
        out[good] = self._order[at[good]]
        return out

    def _lane_ends(self):
        """For lanes as arrays: rear-most car on each, and a car whose body still hangs back onto each."""
        order = np.lexsort((self.pos, self.lanes))
        lanes, first = np.unique(self.lanes[order], return_index=True)
        rear = (lanes, order[first])
        lengths = np.array([t['length'] for t in self.run.trace.header['vtypes']], dtype=float)
        car_len = lengths[self.rec['lane_type'] >> 24]
        prev_all = prevs_of(self.rec)
        behind = (self.pos < car_len) & (prev_all != 0xffffff)
        idx = np.nonzero(behind)[0]
        lanes_hit, cars_hit = list(prev_all[idx]), list(idx)
        # A body long enough reaches back one lane more. The trace holds one previous lane, so that one comes from the net.
        net = self.run.net
        prev_len = net.lane_length[np.minimum(prev_all[idx], net.n_lanes - 1)]
        for at in idx[self.pos[idx] + prev_len < car_len[idx]]:
            for lane in net.lanes_before(int(prev_all[at])):
                lanes_hit.append(lane)
                cars_hit.append(at)
        lanes_hit = np.array(lanes_hit, dtype=np.int64)
        cars_hit = np.array(cars_hit, dtype=np.int64)
        o2 = np.argsort(lanes_hit, kind='stable')
        lanes2, first2 = np.unique(lanes_hit[o2], return_index=True)
        hang = (lanes2, cars_hit[o2[first2]])
        return rear, hang

    @staticmethod
    def _find(table, wanted):
        lanes, who = table
        out = np.full(len(wanted), -1, dtype=np.int64)
        if not len(lanes):
            return out
        at = np.minimum(np.searchsorted(lanes, wanted), len(lanes) - 1)
        hit = lanes[at] == wanted
        out[hit] = who[at[hit]]
        return out

    def _infer_same_lane(self):
        order = np.lexsort((self.pos, self.lanes))
        same = self.lanes[order[:-1]] == self.lanes[order[1:]]
        self.next[order[:-1][same]] = order[1:][same]
        self.kind[order[:-1][same]] = K['leader']

    def _from_why(self):
        why = self.why
        b = why['blame'].astype(np.int64)
        plain = (b < BLAME_LINK) & (b != NONE32)
        self.next[plain] = self.lookup(b[plain].astype(np.uint32))
        lane_blame = np.nonzero((b >= BLAME_LANE) & (b != NONE32))[0]
        if len(lane_blame):
            rear, hang = self._lane_ends()
            wanted = (b[lane_blame] & 0x7fffffff).astype(np.int64)
            from_rear = self._find(rear, wanted)
            from_hang = self._find(hang, wanted)
            tailish = (self.kind[lane_blame] == K['tail']) | (self.kind[lane_blame] == K['junction'])
            # A tail is that of a car ahead, never whoever is last on the lane.
            who = np.where(tailish, from_hang, np.where(from_rear >= 0, from_rear, from_hang))
            ok = (who >= 0) & (who != lane_blame)
            self.next[lane_blame[ok]] = who[ok]
        # At the end of a lane its route cannot leave: whoever blocks the lane change it needs.
        end = np.nonzero(self.kind == K['lane_end'])[0]
        for idx in end:
            w = why[idx]
            for state, lead, follow in ((w['lc_right'], w['right_leader'], w['right_follower']), (w['lc_left'], w['left_leader'], w['left_follower'])):
                wanted = state & 3
                if not wanted:
                    continue
                who = lead if state & 128 and lead != NONE32 else (follow if state & 256 and follow != NONE32 else NONE32)
                if who != NONE32:
                    hit = self.lookup(np.array([who], dtype=np.uint32))[0]
                    if hit >= 0:
                        self.next[idx] = hit
                        break

    def roots(self):
        """Root of each record. Chains follow only cars that are held still. -2 marks a record on a waiting cycle."""
        nxt = self.next.copy()
        idx = np.arange(self.n)
        linked = nxt >= 0
        mover = linked.copy()
        mover[linked] = self.stopped[nxt[linked]]
        cut = np.where(mover, nxt, idx)
        p = cut.copy()
        for _ in range(int(np.log2(max(self.n, 2))) + 2):
            p = p[p]
        # A record is on a cycle if it does not settle on a self-pointing root. One name per ring: its lowest trip.
        settled = cut[p] == p
        for start in np.unique(p[~settled]):
            ring, at = [], int(start)
            while at not in ring:
                ring.append(at)
                at = int(cut[at])
            name = min(ring, key=lambda k: int(self.trips[k]))
            p[np.isin(p, ring)] = name
        return p, ~settled

    def describe(self, idx):
        run = self.run
        lane = int(self.lanes[idx])
        x, y = run.net.lane_xy(lane, self.pos[idx])
        k = KINDS[self.kind[idx]] if self.kind[idx] < len(KINDS) else '?'
        out = dict(car=run.name(self.trips[idx]), time=float(run.times[self.i]), lane=run.net.lane_name(lane), lane_length=round(float(run.net.lane_length[lane]), 1), pos=round(float(self.pos[idx]), 1), x=round(x, 1), y=round(y, 1), speed=round(float(self.v[idx]), 2), wait=float(self.wait[idx]), kind=k)
        if self.why is not None:
            w = self.why[idx]
            out['decider'] = KINDS[w['decider']]
            if w['first_link'] != NONE32:
                out['link_state'] = link_state(run, self.i, w['first_link'])
                out['junction'] = run.net.junction_of_lane(lane)
            if w['closed'] == 3 and w['foe_trip'] != NONE32:
                out['foe'] = run.name(w['foe_trip'])
            if self.kind[idx] == K['lane_end']:
                out['wants'] = dict(right=lc_words(w['lc_right']), left=lc_words(w['lc_left']))
            if w['blame'] != NONE32:
                out['blame'] = blame_text(run, w['blame'])
        return out


def chain(fr, start):
    hops, seen = [], set()
    i = start
    while True:
        hops.append(i)
        seen.add(i)
        nxt = fr.next[i]
        if nxt < 0:
            return hops, 'end'
        if nxt in seen:
            hops.append(int(nxt))
            return hops, 'cycle'
        if not fr.stopped[nxt]:
            hops.append(int(nxt))
            return hops, 'moving'
        i = int(nxt)


def wait_start(run, trip, i):
    """The first frame of the stop this car is in now, by walking back while it holds still."""
    t = i
    while t > 0:
        rec, _ = run.read(t - 1)
        hit = np.nonzero(trips_of(rec) == trip)[0]
        if not len(hit) or speeds_of(rec)[hit[0]] >= 0.5:
            break
        t -= 1
    return t


def last_not_at_signal(run, trip, i):
    """The latest earlier frame when this car stopped for something other than the signal, that is, its last green."""
    t = i - 1
    while t >= 0:
        rec, why = run.read(t)
        hit = np.nonzero(trips_of(rec) == trip)[0]
        if not len(hit):
            return None
        if why is not None and why['plan'][hit[0]] != K['signal']:
            return t
        t -= 1
    return None


def walk(run, trip, i, out, depth=0, seen=None, max_depth=10):
    """The chain now. Then back: to a red-held car's last green, a ring's first stop, or when the root stopped."""
    seen = seen if seen is not None else set()
    fr = Frame(run, i)
    hit = np.nonzero(fr.trips == trip)[0]
    if not len(hit):
        out.append(dict(note=f'car {run.name(trip)} is not in frame t={run.times[i]}'))
        return None
    hops, end = chain(fr, int(hit[0]))
    steps = [fr.describe(h) for h in hops]
    held = hops[-2] if end == 'moving' and len(hops) > 1 else hops[-1]
    stage = dict(time=float(run.times[i]), hops=steps, end=end, root=fr.describe(held))
    out.append(stage)
    root_trip = int(fr.trips[held])
    key = (root_trip, int(fr.kind[held]), end)
    if depth >= max_depth or key in seen:
        return stage
    seen.add(key)
    if end == 'cycle':
        members = hops[hops.index(hops[-1]):-1]
        stage['cycle'] = [fr.describe(h)['car'] for h in members]
        starts = [(wait_start(run, int(fr.trips[m]), i), int(fr.trips[m])) for m in members]
        t0, root_trip = min(starts)
        stage['cycle_first_stop'] = dict(car=run.name(root_trip), time=float(run.times[t0]))
        stage['cycle_closed'] = dict(car=run.name(max(starts)[1]), time=float(run.times[max(starts)[0]]))
        if t0 < i:
            return walk(run, root_trip, t0, out, depth + 1, seen, max_depth)
        return stage
    if end == 'moving':
        return stage
    if fr.kind[held] == K['signal'] and fr.wait[held] >= 30:
        back = last_not_at_signal(run, root_trip, i)
        if back is not None:
            stage['last_green'] = float(run.times[back])
            return walk(run, root_trip, back, out, depth + 1, seen, max_depth)
        return stage
    t0 = wait_start(run, root_trip, i)
    if t0 < i:
        return walk(run, root_trip, t0, out, depth + 1, seen, max_depth)
    return stage


def print_walk(stages):
    for k, s in enumerate(stages):
        if 'note' in s:
            print(s['note'])
            continue
        print(f"{'NOW' if k == 0 else 'EARLIER'} t={s['time']:.1f}, {len(s['hops'])} cars in the chain, ends: {s['end']}")
        for h in s['hops']:
            more = ' '.join(f'{x}={h[x]}' for x in ('blame', 'link_state', 'foe', 'wants') if h.get(x))
            print(f"   car {h['car']:<14} on {h['lane']:<24} pos {h['pos']:>6}/{h['lane_length']:<6} at ({h['x']:.0f},{h['y']:.0f}) v {h['speed']:<5} waited {h['wait']:>3.0f}s  held by {h['kind']}  {more}")
        if 'last_green' in s:
            print(f"   held at red now; looking at its last green, t={s['last_green']:.1f}")
        if 'cycle' in s:
            print(f"   CYCLE of {len(s['cycle'])} cars: {' -> '.join(s['cycle'])}")
            if 'cycle_first_stop' in s:
                print(f"   first of them to stop: {s['cycle_first_stop']['car']} at t={s['cycle_first_stop']['time']:.1f}")
                print(f"   ring closed when the last of them stopped: {s['cycle_closed']['car']} at t={s['cycle_closed']['time']:.1f}")
    rings = [s for s in stages if 'cycle' in s]
    if rings:
        r = rings[0]
        print(f"DEADLOCK: ring of {len(r['cycle'])} cars closed at t={r['cycle_closed']['time']:.1f}: {' -> '.join(r['cycle'])}")
    last = next((s for s in reversed(stages) if 'hops' in s), None)
    if last:
        h = last['root']
        print(f"FIRST CAUSE: car {h['car']} on {h['lane']} pos {h['pos']}/{h['lane_length']} at ({h['x']:.0f},{h['y']:.0f}), t={last['time']:.1f}: held by {h['kind']}" + (f" ({h.get('blame')})" if h.get('blame') else '') + (f", link state {h['link_state']}" if h.get('link_state') else '') + (f", wants {h['wants']}" if h.get('wants') else '') + (', and what it waits for keeps moving' if last['end'] == 'moving' else ''))


def congested_car(run, edge, i):
    fr = Frame(run, i)
    lanes = run.net.lanes_of_edge(edge)
    on = np.nonzero(np.isin(fr.lanes, lanes) & fr.stopped)[0]
    if not len(on):
        raise SystemExit(f'no held car on {edge} at t={run.times[i]}')
    return int(fr.trips[on[np.argmax(fr.wait[on] + 1e-3 * fr.pos[on])]])


def seeds(run, begin, end, stride, min_wait, top, out_dir, signal_wait=150.0):
    """Across the run: which held cars were at the root, how many they held, and when."""
    table, merged = {}, {}
    first_blocked = None
    series_t, stuck_series = [], []
    frames = list(run.window(begin, end))[::max(stride, 1)]
    for i in frames:
        fr = Frame(run, i)
        root, on_cycle = fr.roots()
        held = fr.stopped & (fr.wait >= 1.0)
        ids, counts = np.unique(root[held], return_counts=True)
        t = float(run.times[i])
        series_t.append(t)
        stuck_series.append(int(held.sum()))
        for r, c in zip(ids, counts):
            r = int(r)
            cyc = bool(on_cycle[r])
            if fr.wait[r] < min_wait and not cyc:
                continue
            # A queue at a red light is no seed until it has outlasted any normal cycle.
            if fr.kind[r] == K['signal'] and fr.wait[r] < signal_wait:
                continue
            trip = int(fr.trips[r])
            kind = KINDS[fr.kind[r]] if not cyc else 'cycle'
            s = table.get(trip)
            if s is None:
                s = table[trip] = dict(trip=trip, first=t, last=t, peak=0, peak_at=t, car_seconds=0.0, cars=set(), kinds={}, where=fr.describe(r), series=[])
                if first_blocked is None:
                    first_blocked = trip
            s['last'] = t
            s['kinds'][kind] = s['kinds'].get(kind, 0) + 1
            if c > s['peak']:
                s['peak'], s['peak_at'] = int(c), t
            s['car_seconds'] += float(c) * run.dt * max(stride, 1)
            s['series'].append((t, int(c)))
            s['cars'].update(int(x) for x in fr.trips[held & (root == r)])
    # A seed whose root car is held behind another seed at some moment drains into that seed.
    rows = sorted(table.values(), key=lambda s: -len(s['cars']))
    held_by = {}
    for b in rows:
        for a in rows:
            if a is not b and a['trip'] in b['cars']:
                held_by.setdefault(b['trip'], []).append(a['trip'])
    for s in rows:
        s['eventual'] = len(s['cars']) + sum(len(table[t2]['cars']) for t2 in held_by.get(s['trip'], []))
    for s in sorted(rows, key=lambda s: -s['eventual'])[:200]:
        reach, todo, done = set(s['cars']), list(held_by.get(s['trip'], [])), {s['trip']}
        while todo:
            t2 = todo.pop()
            if t2 not in done:
                done.add(t2)
                reach |= table[t2]['cars']
                todo.extend(held_by.get(t2, []))
        s['eventual'] = len(reach)
        s['drains'] = len(done) - 1
    rows.sort(key=lambda s: (-s['eventual'], s['first']))
    report = dict(frames=len(frames), seeds=len(rows), first_blocked=run.name(first_blocked) if first_blocked is not None else None, top=[])
    print(f'{len(frames)} frames, {len(rows)} seeds with a root waiting at least {min_wait:.0f} s')
    if first_blocked is not None:
        s = table[first_blocked]
        print(f"first blocked head: car {run.name(first_blocked)} at t={s['first']:.0f} on {s['where']['lane']} pos {s['where']['pos']} ({s['where']['x']:.0f},{s['where']['y']:.0f}), held by {s['where']['kind']} {s['where'].get('blame', '')}")
    print(f"{'rank':>4} {'car':<14} {'eventually':>10} {'held':>6} {'peak':>5} {'veh-h':>7} {'first':>7} {'last':>7}  held by, on")
    for n, s in enumerate(rows[:top], 1):
        kinds = sorted(s['kinds'].items(), key=lambda x: -x[1])
        print(f"{n:4} {run.name(s['trip']):<14} {s['eventual']:10} {len(s['cars']):6} {s['peak']:5} {s['car_seconds'] / 3600:7.1f} {s['first']:7.0f} {s['last']:7.0f}  {kinds[0][0]} {s['where'].get('blame', '')} on {s['where']['lane']} ({s['where']['x']:.0f},{s['where']['y']:.0f})")
        report['top'].append(dict(rank=n, car=run.name(s['trip']), eventual=s['eventual'], held=len(s['cars']), peak=s['peak'], peak_at=s['peak_at'], vehicle_hours=round(s['car_seconds'] / 3600, 2), first=s['first'], last=s['last'], kinds=dict(kinds), where=s['where']))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'seeds.json'), 'w') as f:
        json.dump(report, f, indent=1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(15, 6.5))
    ax[0].plot(series_t, stuck_series, color='black', lw=1.5, label='all held cars')
    colors = plt.get_cmap('tab10')
    for n, s in enumerate(rows[:8]):
        tt, cc = zip(*s['series'])
        ax[0].plot(tt, cc, lw=1.1, color=colors(n), label=f"{run.name(s['trip'])} {s['where']['lane'][:18]}")
    ax[0].set(xlabel='simulation time, s', ylabel='cars held', title='Held cars, and those behind the top seeds')
    ax[0].legend(fontsize=7)
    net = run.net
    from matplotlib.collections import LineCollection
    road = net.lane_internal == 0
    ax[1].add_collection(LineCollection(np.stack([np.c_[net.lane_x0[road], net.lane_y0[road]], np.c_[net.lane_x1[road], net.lane_y1[road]]], axis=1), colors='#b8b8b8', linewidths=0.35))
    ax[1].autoscale()
    for n, s in enumerate(rows[:20]):
        ax[1].scatter(s['where']['x'], s['where']['y'], s=30 + 3 * np.sqrt(s['eventual']), color=colors(n % 10), edgecolor='black', lw=0.4, zorder=3)
        if n < 8:
            ax[1].annotate(str(n + 1), (s['where']['x'], s['where']['y']), fontsize=8, weight='bold')
    ax[1].set(aspect='equal', title='Where the top seeds are (size: cars eventually held)')
    fig.tight_layout()
    path = os.path.join(out_dir, 'seeds.png')
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"chart {path}\ntable {os.path.join(out_dir, 'seeds.json')}")
    return report


def main(argv):
    a = argparse.ArgumentParser(prog='cars jam', description=__doc__)
    a.add_argument('--trace', required=True)
    a.add_argument('--car')
    a.add_argument('--edge', help='start from the longest waiting car on this road')
    a.add_argument('--at', type=float)
    a.add_argument('--seeds', action='store_true')
    a.add_argument('--begin', type=float)
    a.add_argument('--end', type=float)
    a.add_argument('--stride', type=int, default=10, help='with --seeds, look at every nth frame')
    a.add_argument('--min-wait', type=float, default=60.0, help='a root counts as a seed once it has waited this long')
    a.add_argument('--signal-wait', type=float, default=150.0, help='a root at a red light counts only after this long')
    a.add_argument('--top', type=int, default=15)
    a.add_argument('--net')
    a.add_argument('--out', default='jam')
    a.add_argument('--json', action='store_true')
    a = a.parse_args(argv)
    run = Run(a.trace, a.net)
    if not run.has_why:
        print('no .why file: chains follow same-lane leaders only. Trace with `cars run --why` for the real reasons.')
    if a.seeds:
        seeds(run, a.begin, a.end, a.stride, a.min_wait, a.top, a.out, a.signal_wait)
        return
    i = run.frame_at(a.at if a.at is not None else run.times[-1])
    if a.car:
        trip = run.trip(a.car)
    elif a.edge:
        trip = congested_car(run, a.edge, i)
        print(f'longest waiting car on {a.edge}: {run.name(trip)}')
    else:
        raise SystemExit('give --car, --edge or --seeds')
    stages = []
    walk(run, trip, i, stages)
    if a.json:
        print(json.dumps(stages, indent=1))
    else:
        print_walk(stages)
