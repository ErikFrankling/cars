"""`cars junction`: per junction, flow per movement, lost time, stops, queue, gaps accepted and rejected, blocked time and by what. Compares junctions of a type."""
import argparse
import json
import os

import numpy as np

from .run import HALT, K, KINDS, NONE32, Run, blame_text, flags_of, lanes_of, pos_of, speeds_of, trips_of, waits_of

STOP = 0.5


def pick(run, ids, jtype, top, bbox):
    """Junctions to study. With a type, the busiest by cars seen on their approaches in the first frames."""
    net = run.net
    if ids:
        return ids
    candidates = [j for j in net.junction_ids if net.junction_type.get(j) != 'internal' and (jtype is None or net.junction_type.get(j) == jtype or (jtype == 'signal' and 'traffic_light' in net.junction_type.get(j, '')))]
    if bbox:
        x0, y0, x1, y1 = bbox
        candidates = [j for j in candidates if x0 <= net.junction_xy[j][0] <= x1 and y0 <= net.junction_xy[j][1] <= y1]
    lane_to = _lane_map(net, candidates)
    counts = np.zeros(len(candidates) + 1)
    frames = list(run.window())
    for i in frames[:: max(len(frames) // 20, 1)]:
        rec, _ = run.read(i)
        l = lanes_of(rec)
        l = l[l < net.n_lanes]
        js = lane_to[l]
        np.add.at(counts, js[js >= 0], 1)
    order = np.argsort(-counts[:-1])
    if not len(order):
        raise SystemExit('no junction of that type here')
    return [candidates[o] for o in order[:top]]


def _lane_map(net, order):
    """Index into `order` of the junction each approach lane leads to, -1 for the rest."""
    names = {j: n for n, j in enumerate(order)}
    to = np.full(net.n_lanes, -1, dtype=np.int64)
    for e, jn in enumerate(net.edge_to):
        if jn in names and net.edge_func[e] != 'internal':
            to[int(net.edge_first[e]):int(net.edge_first[e] + net.edge_lanes[e])] = names[jn]
    return to


class Study:
    def __init__(self, net, junction):
        self.j = junction
        self.net = net
        self.approach = set()
        self.inside = set()
        for e, jn in enumerate(net.edge_to):
            if jn == junction and net.edge_func[e] != 'internal':
                self.approach.update(range(int(net.edge_first[e]), int(net.edge_first[e] + net.edge_lanes[e])))
        for lane in self.approach:
            start, count = int(net.lane_links_start[lane]), int(net.lane_links_count[lane])
            for k in range(start, start + count):
                n = int(net.link_next_lane[k])
                for _ in range(5):
                    if not net.lane_internal[n]:
                        break
                    self.inside.add(n)
                    s2, c2 = int(net.lane_links_start[n]), int(net.lane_links_count[n])
                    if not c2:
                        break
                    n = int(net.link_next_lane[s2])
        self.cars = {}
        self.moves = {}
        self.stops = 0
        self.lost = 0.0
        self.q_sum = 0.0
        self.q_max = 0
        self.q_m_max = 0.0
        self.frames = 0
        self.blocked = {}
        self.blockers = {}
        self.rejected = []
        self.accepted = []
        self.entry_times = []
        self.ever_waited_yield = set()

    def add(self, run, t, rec, why, trip, lane, pos, v, wait, dt):
        net = self.net
        on_app = np.array([l in self.approach for l in lane.tolist()], dtype=bool) if len(lane) else np.zeros(0, dtype=bool)
        on_in = np.array([l in self.inside for l in lane.tolist()], dtype=bool) if len(lane) else np.zeros(0, dtype=bool)
        here = np.nonzero(on_app | on_in)[0]
        queue = 0
        q_m = 0.0
        heads = {}
        for i in here:
            c = int(trip[i])
            l = int(lane[i])
            vmax = float(net.lane_speed[l])
            state = self.cars.get(c)
            if state is None:
                state = self.cars[c] = dict(lost=0.0, stops=0, was_stopped=False, from_edge=None, last_lane=l, waited_for=None, entered=None)
            state['seen'] = t
            state['lost'] += dt * max(0.0, 1.0 - float(v[i]) / max(vmax, 0.1))
            stopped = float(v[i]) < STOP
            if stopped and not state['was_stopped']:
                state['stops'] += 1
            state['was_stopped'] = stopped
            if on_app[i]:
                state['from_edge'] = int(net.lane_edge[l])
                if stopped:
                    queue += 1
                    q_m = max(q_m, float(net.lane_length[l]) - float(pos[i]))
                if l not in heads or pos[i] > pos[heads[l]]:
                    heads[l] = i
            elif state['entered'] is None:
                state['entered'] = t
                self.entry_times.append((t, state['from_edge']))
            state['last_lane'] = l
            if on_app[i] and why is not None and why['closed'][i] == 3 and stopped:
                g = float(why['foe_gap'][i])
                f = int(why['foe_trip'][i])
                if state.get('last_foe') != f:
                    state['last_foe'] = f
                    self.rejected.append(g)
                state['waited_for'] = 'foe'
        self.q_sum += queue
        self.q_max = max(self.q_max, queue)
        self.q_m_max = max(self.q_m_max, q_m)
        self.frames += 1
        if why is not None:
            for l, i in heads.items():
                if float(v[i]) >= STOP:
                    continue
                k = KINDS[why['plan'][i]] if why['plan'][i] < len(KINDS) else '?'
                self.blocked[k] = self.blocked.get(k, 0.0) + dt
                if why['blame'][i] != NONE32:
                    who = self.blame_place(run, int(why['blame'][i]), rec, why['closed'][i], why['foe_link'][i], k)
                    key = (k, who)
                    self.blockers[key] = self.blockers.get(key, 0.0) + dt

    def blame_place(self, run, b, rec, closed, foe_link, k):
        net = self.net
        if closed == 3 and foe_link != NONE32:
            return 'link ' + net.link_name(int(foe_link))
        return blame_text(run, b) if b >= 0x40000000 else 'a car'

    def finish(self, run, t, trip_now, lane_of_now):
        """Cars that have left: book their movement."""
        net = self.net
        gone = []
        for c, s in self.cars.items():
            if c in trip_now and lane_of_now[c] in self.approach | self.inside:
                continue
            gone.append(c)
            if s['from_edge'] is None:
                continue
            to = lane_of_now.get(c)
            name_to = net.edge_ids[int(net.lane_edge[to])] if to is not None and to < net.n_lanes else 'left the road or trace'
            mv = (net.edge_ids[s['from_edge']], name_to)
            m = self.moves.setdefault(mv, dict(flow=0, lost=0.0, stops=0))
            m['flow'] += 1
            m['lost'] += s['lost']
            m['stops'] += s['stops']
            self.stops += s['stops']
            self.lost += s['lost']
            if s['waited_for'] == 'foe' and s['entered'] is not None:
                self.accepted.append(s['entered'])
        for c in gone:
            del self.cars[c]

    def report(self, span):
        n = sum(m['flow'] for m in self.moves.values())
        rows = sorted(((a, b, m) for (a, b), m in self.moves.items()), key=lambda x: -x[2]['flow'])
        arrivals = np.array(sorted(t for t, _ in self.entry_times))
        accepted_gaps = []
        for t in self.accepted:
            later = arrivals[arrivals > t]
            if len(later):
                accepted_gaps.append(float(later[0] - t))
        total_blocked = sum(self.blocked.values())
        return dict(
            junction=self.j, type=self.net.junction_type.get(self.j, ''), xy=self.net.junction_xy.get(self.j), cars=n, flow_per_hour=round(n / max(span, 1e-9) * 3600.0, 0),
            lost_s_per_car=round(self.lost / max(n, 1), 1), stops_per_car=round(self.stops / max(n, 1), 2), queue_mean=round(self.q_sum / max(self.frames, 1), 2), queue_max=int(self.q_max), queue_max_m=round(self.q_m_max, 1),
            gaps_rejected=len(self.rejected), rejected_gap_median_s=round(float(np.median(self.rejected)), 2) if self.rejected else None, gaps_accepted=len(self.accepted), accepted_gap_median_s=round(float(np.median(accepted_gaps)), 2) if accepted_gaps else None,
            head_blocked_s=round(total_blocked, 0), blocked_by={k: round(v, 0) for k, v in sorted(self.blocked.items(), key=lambda x: -x[1])},
            blocked_top=[dict(kind=k, what=w, seconds=round(v, 0)) for (k, w), v in sorted(self.blockers.items(), key=lambda x: -x[1])[:5]],
            movements=[dict(frm=a, to=b, flow=m['flow'], flow_per_hour=round(m['flow'] / max(span, 1e-9) * 3600.0), lost_s=round(m['lost'] / max(m['flow'], 1), 1), stops=round(m['stops'] / max(m['flow'], 1), 2)) for a, b, m in rows],
        )


def main(argv):
    a = argparse.ArgumentParser(prog='cars junction', description=__doc__)
    a.add_argument('--trace', required=True)
    a.add_argument('--junction', help='ids, comma separated')
    a.add_argument('--type', help='compare the busiest of a type: traffic_light (or signal), priority, right_before_left, zipper, allway_stop')
    a.add_argument('--top', type=int, default=12)
    a.add_argument('--bbox', help='only junctions in x0,y0,x1,y1', type=lambda s: [float(x) for x in s.split(',')])
    a.add_argument('--begin', type=float)
    a.add_argument('--end', type=float)
    a.add_argument('--stride', type=int, default=1)
    a.add_argument('--net')
    a.add_argument('--out', default='junction')
    a.add_argument('--json', action='store_true')
    a = a.parse_args(argv)
    run = Run(a.trace, a.net)
    ids = a.junction.split(',') if a.junction else None
    if not ids and not a.type:
        raise SystemExit('give --junction or --type')
    chosen = pick(run, ids, a.type, a.top, a.bbox)
    for j in chosen:
        if j not in run.net.junction_xy:
            raise SystemExit(f'no junction {j}')
    studies = [Study(run.net, j) for j in chosen]
    wanted = np.zeros(run.net.n_lanes + 2, dtype=bool)
    for s in studies:
        wanted[list(s.approach | s.inside)] = True
    frames = list(run.window(a.begin, a.end))[:: max(a.stride, 1)]
    dt = run.dt * max(a.stride, 1)
    last_seen = set()
    for i in frames:
        rec, why = run.read(i)
        lane = lanes_of(rec)
        mask = (lane < len(wanted)) & wanted[np.minimum(lane, len(wanted) - 1)]
        trip_all = trips_of(rec)
        # Only cars that are or were near a studied junction matter, to find where they went.
        watched = mask | np.isin(trip_all, np.fromiter(last_seen, dtype=trip_all.dtype, count=len(last_seen)))
        r2, tr, la = rec[watched], trip_all[watched], lane[watched]
        w2 = why[watched] if why is not None else None
        po, sp, wa = pos_of(r2), speeds_of(r2), waits_of(r2)
        now = {int(c): int(l) for c, l in zip(tr, la)}
        for s in studies:
            s.add(run, float(run.times[i]), r2, w2, tr, la, po, sp, wa, dt)
            s.finish(run, float(run.times[i]), now, now)
        last_seen = set(int(c) for c in tr[mask[watched]]) if len(tr) else set()
    span = len(frames) * dt
    reports = [s.report(span) for s in studies]
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'junctions.json'), 'w') as f:
        json.dump(reports, f, indent=1)
    if a.json:
        print(json.dumps(reports, indent=1))
    else:
        print(f"{'junction':<22} {'type':<16} {'veh/h':>6} {'lost s':>7} {'stops':>6} {'q mean':>7} {'q max':>6} {'q m':>6} {'rej':>5} {'acc':>5} {'rej gap':>7}  head blocked by")
        for r in reports:
            top = ' '.join(f'{k} {v:.0f}s' for k, v in list(r['blocked_by'].items())[:3])
            print(f"{r['junction'][:22]:<22} {r['type'][:16]:<16} {r['flow_per_hour']:6.0f} {r['lost_s_per_car']:7.1f} {r['stops_per_car']:6.2f} {r['queue_mean']:7.2f} {r['queue_max']:6} {r['queue_max_m']:6.0f} {r['gaps_rejected']:5} {r['gaps_accepted']:5} {str(r['rejected_gap_median_s']):>7}  {top}")
        if len(reports) <= 3:
            for r in reports:
                print(f"\n{r['junction']} movements:")
                for m in r['movements'][:14]:
                    print(f"  {m['frm'][:26]:<26} -> {m['to'][:26]:<26} {m['flow']:5} cars {m['flow_per_hour']:6.0f} veh/h  lost {m['lost_s']:6.1f} s  stops {m['stops']:.2f}")
                for b in r['blocked_top']:
                    print(f"  blocked {b['seconds']:.0f} s by {b['kind']}: {b['what']}")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(16, max(4.0, 0.34 * len(reports) + 1.6)))
    names = [r['junction'][:18] for r in reports][::-1]
    axs[0].barh(names, [r['flow_per_hour'] for r in reports][::-1], color='#4c78a8')
    axs[0].set(title='Flow, veh/h')
    axs[1].barh(names, [r['lost_s_per_car'] for r in reports][::-1], color='#e45756')
    axs[1].set(title='Lost time, s per car')
    kinds = sorted({k for r in reports for k in r['blocked_by']})
    left = np.zeros(len(reports))
    tab = plt.get_cmap('tab20')
    for n, k in enumerate(kinds):
        vals = np.array([r['blocked_by'].get(k, 0.0) for r in reports][::-1])
        axs[2].barh(names, vals, left=left, label=k, color=tab(KINDS.index(k) % 20 if k in KINDS else n))
        left += vals
    axs[2].set(title='Head of lane blocked, seconds, by what')
    if kinds:
        axs[2].legend(fontsize=8)
    fig.tight_layout()
    path = os.path.join(a.out, 'junctions.png')
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"chart {path}\ntable {os.path.join(a.out, 'junctions.json')}")
