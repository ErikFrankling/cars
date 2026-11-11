"""`cars why`: for a car and a tick, which limit decided its speed, with the value of each limit, and who blocks it."""
import argparse
import json
import os

import numpy as np

from .run import (BLAME_LANE, BLAME_LINK, CLOSED, denial, HALT, K, KINDS, LANE_CHANGED, NONE32, PLAIN, Run, accs_of, blame_text, flags_of, lanes_of, lc_words, limit_value, link_state, pos_of, speeds_of, trips_of,
                  waits_of)


def lc_side(run, side, state, gap, fgap, leader, follower):
    if state == 0:
        return None
    words = lc_words(state)
    out = {'state': words}
    if gap < 1e8:
        out['leader_gap'] = round(float(gap), 2)
    if fgap < 1e8:
        out['follower_gap'] = round(float(fgap), 2)
    if leader != NONE32:
        out['leader'] = run.name(leader)
    if follower != NONE32:
        out['follower'] = run.name(follower)
    return out


def wrong_lane(net, lane, wanted):
    """Which lanes of this road go where the route asks, and whether the markings let the car reach them."""
    e = int(net.lane_edge[lane])
    first, count = int(net.edge_first[e]), int(net.edge_lanes[e])
    to = net.edge_index.get(wanted)
    good = [l - first for l in range(first, first + count) if to in net.link_to_edge[int(net.lane_links_start[l]):int(net.lane_links_start[l] + net.lane_links_count[l])]]
    here = lane - first
    out = dict(wants_road=wanted, on_lane=here, lanes_that_go_there=good)
    bit = 64
    reach = {here}
    for step, masks in ((-1, net.lane_change_right), (1, net.lane_change_left)):
        at = here
        while 0 <= at + step < count and masks[first + at] & bit and net.lane_allow[first + at + step] & bit:
            at += step
            reach.add(at)
    out['lanes_it_may_change_to'] = sorted(reach)
    out['verdict'] = 'reachable: it should change lane' if set(good) & reach else 'impossible: line markings forbid every way to those lanes' if good else 'no lane of this road leads there'
    return out


def explain(run, i, rec, why, index):
    """Everything known about one record, as plain data."""
    r = rec[index]
    net = run.net
    lane = int(lanes_of(rec[index:index + 1])[0])
    flags = int(flags_of(rec[index:index + 1])[0])
    out = {
        'time': float(run.times[i]), 'car': run.name(trips_of(rec[index:index + 1])[0]), 'lane': net.lane_name(lane),
        'pos': round(float(pos_of(rec[index:index + 1])[0]), 2), 'lane_length': round(float(net.lane_length[lane]), 1) if lane < net.n_lanes else None,
        'speed': round(float(speeds_of(rec[index:index + 1])[0]), 3), 'acc': round(float(accs_of(rec[index:index + 1])[0]), 3),
        'wait_s': float(waits_of(rec[index:index + 1])[0]), 'lane_speed_limit': round(float(net.lane_speed[lane]), 2) if lane < net.n_lanes else None,
    }
    out['flags'] = [n for b, n in ((1, 'lane_changed'), (2, 'teleport'), (4, 'collision'), (8, 'will_pass'), (16, 'have_to_wait'), (128, 'on_junction')) if flags & b]
    if why is None:
        return out
    w = why[index]
    d = KINDS[w['decider']] if w['decider'] < len(KINDS) else str(w['decider'])
    p = KINDS[w['plan']] if w['plan'] < len(KINDS) else str(w['plan'])
    out.update(decider=d, decider_plain=PLAIN.get(d, d), planned_by=p, v_safe=round(float(w['v_safe']), 3), blame=blame_text(run, w['blame']), blame_gap=round(float(w['blame_gap']), 2))
    out['limits'] = {KINDS[k]: round(limit_value(v), 3) for k, v in enumerate(w['limits'][:len(KINDS)]) if limit_value(v) is not None}
    if w['leader'] != NONE32:
        out['leader'] = dict(who=blame_text(run, w['leader']), gap=round(float(w['leader_gap']), 2), speed=round(float(w['leader_speed']), 3))
    if w['first_link'] != NONE32:
        k = int(w['first_link'])
        out['next_link'] = dict(link=net.link_name(k), state=link_state(run, i, k), metres_to_it=round(float(w['first_dist']), 1), junction=net.junction_of_lane(lane), junction_type=net.junction_type.get(net.junction_of_lane(lane), ''))
    elif w['item'] != 255 and w['decider']:
        out['next_link'] = dict(link=None, metres_to_it=round(float(w['first_dist']), 1), note='no link from this lane on its route, or route ends')
        if w['closed'] == 0 and w['foe_link'] != NONE32 and int(w['foe_link']) < len(net.edge_ids) and lane < net.n_lanes:
            out['route_blocked'] = wrong_lane(net, lane, net.edge_ids[int(w['foe_link'])])
    if denial(run, w):
        out['denied'] = denial(run, w)
    if w['closed']:
        out['link_closed'] = dict(reason=CLOSED[w['closed']], foe=run.name(w['foe_trip']) if w['foe_trip'] != NONE32 else None, foe_link=net.link_name(w['foe_link']) if w['foe_link'] != NONE32 else None,
                                  foe_arrives_after_s=round(float(w['foe_gap']), 2))
    right = lc_side(run, 'right', w['lc_right'], w['right_gap'], w['right_follow_gap'], w['right_leader'], w['right_follower'])
    left = lc_side(run, 'left', w['lc_left'], w['left_gap'], w['left_follow_gap'], w['left_leader'], w['left_follower'])
    lc = {}
    if right:
        lc['right'] = right
    if left:
        lc['left'] = left
    if w['lc_chosen']:
        lc['chosen'] = 'left' if w['lc_chosen'] > 0 else 'right'
        lc['result'] = 'changed' if flags & LANE_CHANGED else 'lost the space to another changer'
    if lc:
        out['lane_change'] = lc
    return out


def print_tick(e):
    print(f"t={e['time']:.2f}  car {e['car']}  on {e['lane']}  pos {e['pos']}/{e['lane_length']}  speed {e['speed']} m/s  acc {e['acc']} m/s2  waiting {e['wait_s']:.0f} s  {' '.join(e['flags'])}")
    if 'decider' not in e:
        print('  no .why file: trace with `cars run --trace f --why` to see reasons')
        return
    print(f"  decided by: {e['decider']} ({e['decider_plain']})" + (f"  planned by: {e['planned_by']}" if e['planned_by'] != e['decider'] else '') + (f"  because of {e['blame']}" if e['blame'] else '') + (f", {e['blame_gap']} m to it" if e['blame'] and e['blame_gap'] else ''))
    if 'dawdle' in e['limits']:
        print(f"  plan allowed {e['v_safe']} m/s, the driver dawdled to {e['limits']['dawdle']}")
    print('  limits, m/s, lowest first:  ' + '  '.join(f'{k} {v}' for k, v in sorted(e['limits'].items(), key=lambda x: x[1])))
    if 'leader' in e:
        print(f"  leader: {e['leader']['who']}  gap {e['leader']['gap']} m  speed {e['leader']['speed']} m/s")
    else:
        print('  leader: none within its plan')
    if 'next_link' in e:
        n = e['next_link']
        print(f"  next link: {n.get('link')}  state {n.get('state', '')}  {n['metres_to_it']} m ahead  {n.get('junction_type', '')} {n.get('junction', '')} {n.get('note', '')}")
    if 'route_blocked' in e:
        b = e['route_blocked']
        print(f"  route wants {b['wants_road']}: lanes that go there {b['lanes_that_go_there']}, it is on lane {b['on_lane']} and may change to {b['lanes_it_may_change_to']}. {b['verdict']}")
    if 'denied' in e:
        print(f"  arbiter held it: {e['denied']}")
    if 'link_closed' in e:
        c = e['link_closed']
        print(f"  link closed: {c['reason']}" + (f"  foe {c['foe']} on {c['foe_link']}, arrives {c['foe_arrives_after_s']} s after this car would" if c['foe'] else ''))
    lc = e.get('lane_change')
    if lc:
        for side in ('right', 'left'):
            s = lc.get(side)
            if s:
                print(f"  lane change {side}: {' '.join(s['state'])}" + (f"  leader {s.get('leader')} {s.get('leader_gap')} m" if 'leader_gap' in s else '') + (f"  follower {s.get('follower')} {s.get('follower_gap')} m" if 'follower_gap' in s else ''))
        if 'chosen' in lc:
            print(f"  lane change chosen: {lc['chosen']}, {lc['result']}")
    else:
        print('  lane change: no wish')


def find_car(rec, trip):
    hits = np.nonzero(trips_of(rec) == trip)[0]
    return int(hits[0]) if len(hits) else None


def timeline(run, trip, begin, end):
    rows = []
    for i in run.window(begin, end):
        rec, why = run.read(i)
        at = find_car(rec, trip)
        if at is None:
            continue
        rows.append((i, rec[at:at + 1].copy(), None if why is None else why[at:at + 1].copy()))
    return rows


def table(run, rows):
    """Consecutive ticks with the same reason and blame become one row."""
    out = []
    for i, r, w in rows:
        t = float(run.times[i])
        d = KINDS[w['decider'][0]] if w is not None else '-'
        b = blame_text(run, w['blame'][0]) if w is not None else ''
        lane = run.net.lane_name(lanes_of(r)[0])
        if out and out[-1]['decider'] == d and out[-1]['blame'] == b and out[-1]['lane'] == lane:
            o = out[-1]
            o['to'], o['pos1'], o['v1'] = t, float(pos_of(r)[0]), float(speeds_of(r)[0])
            o['a_min'], o['a_max'] = min(o['a_min'], float(accs_of(r)[0])), max(o['a_max'], float(accs_of(r)[0]))
        else:
            out.append(dict(frm=t, to=t, lane=lane, pos0=float(pos_of(r)[0]), pos1=float(pos_of(r)[0]), v0=float(speeds_of(r)[0]), v1=float(speeds_of(r)[0]), a_min=float(accs_of(r)[0]), a_max=float(accs_of(r)[0]), decider=d, blame=b))
    return out


def chart(run, rows, path, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = np.array([run.times[i] for i, _, _ in rows])
    v = np.array([speeds_of(r)[0] for _, r, _ in rows])
    a = np.array([accs_of(r)[0] for _, r, _ in rows])
    has = rows[0][2] is not None
    fig, ax = plt.subplots(3 if has else 2, 1, figsize=(13, 8.5 if has else 6), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.2, 1.2] if has else [3, 1.2]))
    tab = plt.get_cmap('tab20')
    colour = {n: tab(i % 20) for i, n in enumerate(KINDS)}
    if has:
        dec = np.array([w['decider'][0] for _, _, w in rows])
        lim = np.array([w['limits'][0][:len(KINDS)] for _, _, w in rows], dtype=float)
        lim[lim == 0xffff] = np.nan
        lim /= 128.0
        vmax = max(v.max() * 1.3, 3.0)
        used = sorted(set(dec.tolist()) | {k for k in range(min(len(KINDS), lim.shape[1])) if np.isfinite(lim[:, k]).any() and np.nanmin(lim[:, k]) < vmax})
        for k in used:
            if k == 0 or not np.isfinite(lim[:, k]).any():
                continue
            ax[0].plot(t, lim[:, k], lw=0.9, alpha=0.75, color=colour[KINDS[k]], label=KINDS[k], drawstyle='steps-post')
        ax[0].set_ylim(0, vmax)
        step = np.median(np.diff(t)) if len(t) > 1 else 1.0
        for k in sorted(set(dec.tolist())):
            on = dec == k
            ax[0].bar(t[on], vmax * 0.04, width=step, bottom=0, color=colour[KINDS[k]], align='edge', lw=0)
    ax[0].plot(t, v, color='black', lw=1.8, label='speed', drawstyle='steps-post')
    ax[0].set_ylabel('m/s (band at the bottom: the limit that decided)')
    ax[0].legend(ncol=5, fontsize=8, loc='upper right')
    ax[0].set_title(title)
    ax[1].plot(t, a, color='#444', lw=1.0, drawstyle='steps-post')
    ax[1].axhline(0, color='#bbb', lw=0.6)
    ax[1].set_ylabel('acc m/s2')
    if has:
        gap = np.array([w['leader_gap'][0] if w['leader'][0] != NONE32 else np.nan for _, _, w in rows], dtype=float)
        dist = np.array([w['first_dist'][0] if w['first_link'][0] != NONE32 else np.nan for _, _, w in rows], dtype=float)
        ax[2].plot(t, gap, lw=1.0, color='#1f77b4', label='gap to leader')
        ax[2].plot(t, dist, lw=1.0, color='#d62728', label='metres to next link')
        ax[2].set_ylabel('m')
        ax[2].legend(fontsize=8)
        ax[2].set_ylim(0, min(150.0, np.nanmax(np.r_[gap, dist, 10.0]) * 1.05))
    ax[-1].set_xlabel('simulation time, s')
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(argv):
    a = argparse.ArgumentParser(prog='cars why', description=__doc__)
    a.add_argument('--trace', required=True)
    a.add_argument('--car', required=True, help='trip id, as in the route file or a flow vehicle like f4.6')
    a.add_argument('--at', type=float, help='one tick')
    a.add_argument('--begin', type=float)
    a.add_argument('--end', type=float)
    a.add_argument('--net', help='needed only if <trace>.net.json is not there')
    a.add_argument('--out', help='directory for the chart and CSV of a time range. Default why_<car>')
    a.add_argument('--json', action='store_true')
    a = a.parse_args(argv)
    run = Run(a.trace, a.net)
    trip = run.trip(a.car)
    if a.at is not None:
        i = run.frame_at(a.at)
        rec, why = run.read(i)
        at = find_car(rec, trip)
        if at is None:
            raise SystemExit(f'car {a.car} is not on the road in frame t={run.times[i]}')
        e = explain(run, i, rec, why, at)
        print(json.dumps(e, indent=1)) if a.json else print_tick(e)
        return
    rows = timeline(run, trip, a.begin, a.end)
    if not rows:
        raise SystemExit(f'car {a.car} is not in that time range')
    out = a.out or f'why_{a.car}'
    os.makedirs(out, exist_ok=True)
    rowsum = table(run, rows)
    shares = {}
    for _, _, w in rows:
        if w is not None:
            k = KINDS[w['decider'][0]]
            shares[k] = shares.get(k, 0) + 1
    if a.json:
        print(json.dumps(dict(ticks=len(rows), shares=shares, rows=rowsum), indent=1))
    else:
        print(f'car {a.car}: {len(rows)} ticks, t={run.times[rows[0][0]]:.1f} to {run.times[rows[-1][0]]:.1f}')
        if shares:
            print('share of ticks by what decided: ' + '  '.join(f'{k} {100 * n / len(rows):.0f}%' for k, n in sorted(shares.items(), key=lambda x: -x[1])))
        print(f"{'from':>8} {'to':>8} {'lane':<26} {'pos':>13} {'speed':>13} {'acc min..max':>13}  decided by, because of")
        for o in rowsum:
            print(f"{o['frm']:8.1f} {o['to']:8.1f} {o['lane'][:26]:<26} {o['pos0']:6.1f}..{o['pos1']:<5.1f} {o['v0']:6.2f}..{o['v1']:<5.2f} {o['a_min']:6.2f}..{o['a_max']:<5.2f}  {o['decider']} {o['blame']}")
    csv = os.path.join(out, 'timeline.csv')
    with open(csv, 'w') as f:
        f.write('time,lane,pos,speed,acc,wait,decider,plan,blame,blame_gap,v_safe,leader,leader_gap,leader_speed,first_dist,' + ','.join(KINDS[1:]) + '\n')
        for i, r, w in rows:
            base = f'{run.times[i]},{run.net.lane_name(lanes_of(r)[0])},{pos_of(r)[0]:.2f},{speeds_of(r)[0]:.3f},{accs_of(r)[0]:.3f},{waits_of(r)[0]:.0f}'
            if w is None:
                f.write(base + '\n')
                continue
            lim = ['' if limit_value(x) is None else f'{limit_value(x):.3f}' for x in w['limits'][0][1:len(KINDS)]]
            f.write(f"{base},{KINDS[w['decider'][0]]},{KINDS[w['plan'][0]]},{blame_text(run, w['blame'][0])},{w['blame_gap'][0]:.2f},{w['v_safe'][0]:.3f},{blame_text(run, w['leader'][0])},{w['leader_gap'][0]:.2f},{w['leader_speed'][0]:.3f},{w['first_dist'][0]:.1f}," + ','.join(lim) + '\n')
    png = os.path.join(out, 'timeline.png')
    chart(run, rows, png, f'car {a.car}: speed, every limit, and which one decided')
    print(f'chart {png}\ntable {csv}')
