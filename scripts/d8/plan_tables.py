#!/usr/bin/env python3
"""Tables for research/truth/09d from research/truth/fig/d8/plan/*.jsonl. Writes plan/tables.md."""
import collections, json
from pathlib import Path
import numpy as np

D8 = Path(__file__).resolve().parents[2] / 'research/truth/fig/d8'
P = D8 / 'plan'


def load(name):
    p = P / f'{name}.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def good(rows):
    return [r for r in rows if 'error' not in r['result']]


def group(rows, *keys):
    g = collections.defaultdict(list)
    for r in good(rows):
        g[tuple(r['case'].get(k) for k in keys)].append(r['result'])
    return g


def m(L, f):
    v = [f(x) for x in L]
    v = [x for x in v if x is not None]
    return float(np.mean(v)) if v else float('nan')


def hard(x):
    return x.get('hard_plan', 0) + x.get('hard_stop_curve', 0) + x.get('hard_leader', 0) + x.get('hard_yield', 0) + x.get('hard_hold', 0) + x.get('hard_stall', 0)


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out) + '\n'


def capacity():
    g = group(load('capacity'), 'net', 'mix', 'plan')
    rows = []
    for (n, mx, p) in sorted(g):
        if p != 'off':
            continue
        a, b = g[(n, mx, 'off')], g.get((n, mx, 'route'), [])
        fa, fb = m(a, lambda x: x['flow']), m(b, lambda x: x['flow'])
        rows.append((n, mx, len(b), f'{fa:.0f}', f'{fb:.0f}', f'{100 * (fb / fa - 1):+.1f}%', f"{m(a, lambda x: x['delay']):.0f} / {m(b, lambda x: x['delay']):.0f}",
                     f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}", f"{m(a, hard):.0f} / {m(b, hard):.0f}", f"{m(a, lambda x: x['aborts']):.0f} / {m(b, lambda x: x['aborts']):.0f}"))
    return table(('Net', 'Mix', 'Seeds', 'Today', 'Planned', 'Change', 'Delay s', 'Overlaps', 'Hard brakes per run', 'Grants dropped per run'), rows)


def tier(L, t, k):
    return m(L, lambda x: x['brake'][t].get(k) if x['brake'][t].get('n') else None)


def demand(name='demand', keys=('net', 'mix', 'demand')):
    g = group(load(name), *keys, 'plan')
    rows = []
    for k in sorted(g):
        if k[-1] != 'off':
            continue
        a, b = g[k], g.get(k[:-1] + ('route',), [])
        if not b:
            continue
        rows.append((*k[:-1], f"{m(a, lambda x: x['flow']):.0f} / {m(b, lambda x: x['flow']):.0f}", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}",
                     f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}",
                     f"{tier(a, 'all', 'speed_lost'):.2f} / {tier(b, 'all', 'speed_lost'):.2f} / {tier(b, 'all', 'gentlest'):.2f}",
                     f"{tier(a, 'all', 'wh'):.1f} / {tier(b, 'all', 'wh'):.1f} / {tier(b, 'all', 'gentlest_wh'):.1f}",
                     f"{tier(a, 'all', 'over3') * 100:.0f} / {tier(b, 'all', 'over3') * 100:.0f}", f"{tier(b, 'all', 'over1') * 100:.0f} / {tier(b, 'all', 'over15') * 100:.0f} / {tier(b, 'all', 'over2') * 100:.0f}",
                     f"{m(a, hard):.0f} / {m(b, hard):.0f}"))
    return table((*keys, 'Flow today / planned', 'Delay s', 'Overlaps', 'Speed lost today / planned / gentlest', 'Wh today / planned / gentlest', '% over 3 m/s2 today / planned', 'Planned % over 1 / 1.5 / 2', 'Hard brakes per run'), rows)


def tiers(name='demand'):
    g = group(load(name), 'net', 'mix', 'demand', 'plan')
    rows = []
    for k in sorted(g):
        if k[-1] != 'off' or k[0] != 'j2' or k[1] != 'M' or k[2] not in (3000, 5200):
            continue
        a, b = g[k], g[k[:-1] + ('route',)]
        for t in ('all', 'straight', 'turning'):
            rows.append((k[2], t, f"{tier(a, t, 'speed_lost'):.2f} / {tier(b, t, 'speed_lost'):.2f} / {tier(b, t, 'gentlest'):.2f}", f"{tier(a, t, 'wh'):.1f} / {tier(b, t, 'wh'):.1f} / {tier(b, t, 'gentlest_wh'):.1f}",
                         f"{tier(a, t, 'peak50'):.1f} / {tier(b, t, 'peak50'):.1f}", f"{tier(a, t, 'peak99'):.1f} / {tier(b, t, 'peak99'):.1f}", f"{tier(a, t, 'jerk90'):.0f} / {tier(b, t, 'jerk90'):.0f}",
                         f"{tier(a, t, 'over1') * 100:.0f}/{tier(a, t, 'over2') * 100:.0f}/{tier(a, t, 'over3') * 100:.0f} , {tier(b, t, 'over1') * 100:.0f}/{tier(b, t, 'over2') * 100:.0f}/{tier(b, t, 'over3') * 100:.0f}",
                         f"{tier(a, t, 'changes50'):.0f}, {tier(a, t, 'changes90'):.0f} / {tier(b, t, 'changes50'):.0f}, {tier(b, t, 'changes90'):.0f}", f"{tier(a, t, 'firm50'):.0f} / {tier(b, t, 'firm50'):.0f}"))
    return table(('veh/h', 'Cars', 'Speed lost m/s today / planned / gentlest', 'Wh', 'Peak decel median', 'p99', 'Braking jerk p90', '% over 1/2/3 today , planned', 'Slot changes p50, p90 today / planned', 'First firm m'), rows)


def where():
    g = group(load('demand'), 'net', 'mix', 'demand', 'plan')
    rows = []
    for k in sorted(g):
        if k[0] == 'j2' and k[1] == 'M' and k[2] in (3000, 5200):
            w = np.mean([x['brake']['all']['where'] for x in g[k]], axis=0)
            rows.append((k[2], k[3], *[f'{100 * v:.0f}%' for v in w]))
    return table(('veh/h', 'Plan', '0-50 m', '50-100', '100-150', '150-200', '200-250', '250+'), rows)


def ablation():
    rows_ = load('ablation')
    g = group(rows_, 'demand', 'plan')
    rows = []
    order = ('off', 'profile', 'stable', 'full', 'route', 'cubic', 'dr')
    for d in sorted({k[0] for k in g}):
        for p in order:
            L = g.get((d, p))
            if not L:
                continue
            tr = 'brake' in L[0]
            rows.append((d, p, f"{m(L, lambda x: x['flow']):.0f}", f"{m(L, lambda x: x['delay']):.1f}", sum(x['overlap'] for x in L), f"{m(L, hard):.0f}", f"{m(L, lambda x: x['aborts']):.0f}",
                         f"{tier(L, 'all', 'speed_lost'):.2f}" if tr else '', f"{tier(L, 'all', 'over3') * 100:.0f}" if tr else '', f"{tier(L, 'all', 'changes50'):.0f}" if tr else ''))
    return table(('veh/h', 'Factor', 'Flow', 'Delay s', 'Overlaps', 'Hard brakes', 'Dropped', 'Speed lost', '% over 3', 'Slot changes p50'), rows)


def length():
    g = group(load('length'), 'net', 'demand', 'plan')
    rows = []
    for k in sorted(g, key=lambda k: (int(k[0][1:]), k[1], k[2])):
        if k[2] != 'off':
            continue
        a, b = g[k], g.get(k[:2] + ('route',), [])
        if not b:
            continue
        tr = 'brake' in a[0]
        rows.append((k[0][1:], k[1], f"{m(a, lambda x: x['flow']):.0f} / {m(b, lambda x: x['flow']):.0f}", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}",
                     f"{tier(a, 'all', 'speed_lost'):.2f} / {tier(b, 'all', 'speed_lost'):.2f} / {tier(b, 'all', 'gentlest'):.2f}" if tr else '', f"{tier(a, 'all', 'over3') * 100:.0f} / {tier(b, 'all', 'over3') * 100:.0f}" if tr else '',
                     f"{tier(b, 'all', 'over15') * 100:.0f}" if tr else '', f"{m(a, hard):.0f} / {m(b, hard):.0f}"))
    return table(('Approach m', 'veh/h', 'Flow today / planned', 'Delay s', 'Overlaps', 'Speed lost today / planned / gentlest', '% over 3 today / planned', 'Planned % over 1.5', 'Hard brakes'), rows)


def faults(name='faults'):
    g = group(load(name), 'demand', 'fault', 'plan')
    rows = []
    for k in sorted(g, key=str):
        if k[2] != 'off':
            continue
        a, b = g[k], g.get(k[:2] + ('route',), [])
        if not b:
            continue
        rows.append((k[0], k[1], f"{m(a, lambda x: x['flow']):.0f} / {m(b, lambda x: x['flow']):.0f}", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}",
                     f"{m(a, hard):.0f} / {m(b, hard):.0f}", f"{m(a, lambda x: x['aborts']):.0f} / {m(b, lambda x: x['aborts']):.0f}"))
    return table(('veh/h', 'Fault', 'Flow today / planned', 'Delay s', 'Overlaps', 'Hard brakes', 'Dropped'), rows)


def loss():
    g = group(load('loss'), 'demand', 'fault', 'plan')
    rows = []
    for k in sorted(g, key=str):
        if k[2] != 'off':
            continue
        a, b = g[k], g.get(k[:2] + ('route',), [])
        if b:
            rows.append((k[0], k[1][4:], f"{m(a, lambda x: x['flow']):.0f} / {m(b, lambda x: x['flow']):.0f}", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}",
                         f"{tier(a, 'all', 'speed_lost'):.2f} / {tier(b, 'all', 'speed_lost'):.2f}", f"{tier(a, 'all', 'over3') * 100:.0f} / {tier(b, 'all', 'over3') * 100:.0f}", f"{m(b, lambda x: x.get('bytes_up', 0)) / max(m(b, lambda x: x.get('arrived', 1)), 1):.0f}"))
    return table(('veh/h', 'Loss', 'Flow today / planned', 'Delay s', 'Overlaps', 'Speed lost', '% over 3', 'Bytes up per car'), rows)


def timing():
    g = group(load('timing'), 'demand', 'fault')
    rows = []
    for k in sorted(g, key=str):
        L = g[k]
        h = np.sum([x['err_hist'] for x in L], axis=0)
        n = max(h.sum(), 1)
        c = np.cumsum(h) / n
        rows.append((k[0], k[1], f"{m(L, lambda x: x['flow']):.0f}", f"{m(L, lambda x: x['delay']):.1f}", sum(x['overlap'] for x in L), f"{m(L, hard):.0f}", f"{1000 * m(L, lambda x: x['err_mean_abs']):.0f}", f'{100 * c[0]:.0f}', f'{100 * c[2]:.0f}', f'{100 * c[4]:.0f}', f'{100 * c[6]:.0f}', f"{sum(x['err_big'] for x in L)}"))
    return table(('veh/h', 'Case', 'Flow', 'Delay s', 'Overlaps', 'Hard brakes', 'Mean arrival error ms', '% within 1 ms', '5 ms', '20 ms', '100 ms', 'Big misses'), rows)


def grid():
    g = group(load('grid'), 'net', 'demand', 'plan')
    rows = []
    for k in sorted(g):
        if k[2] != 'off':
            continue
        a, b = g[k], g.get(k[:2] + ('route',), [])
        if b:
            rows.append((k[0], k[1], f"{m(a, lambda x: x['flow']):.0f} / {m(b, lambda x: x['flow']):.0f}", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}", f"{m(a, hard):.0f} / {m(b, hard):.0f}"))
    return table(('Net', 'veh/h', 'Flow today / planned', 'Delay s', 'Overlaps, 3 seeds', 'Hard brakes'), rows)


def grid_meter():
    g = group(load('grid_meter'), 'net', 'demand', 'meter', 'plan')
    rows = []
    for k in sorted(g):
        if k[3] != 'off':
            continue
        a, b = g[k], g.get(k[:3] + ('route',), [])
        if b:
            rows.append((k[0], k[1], k[2], f"{m(a, lambda x: x['flow']):.0f} / {m(b, lambda x: x['flow']):.0f}", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}", f"{m(a, hard):.0f} / {m(b, hard):.0f}"))
    return table(('Net', 'veh/h', 'Held at', 'Flow today / planned', 'Delay s', 'Overlaps, 3 seeds', 'Hard brakes'), rows)


def route_grid():
    g = group(load('route_grid'), 'net', 'demand', 'plan')
    rows = []
    tot = [0, 0]
    for k in sorted(g):
        if k[2] != 'off':
            continue
        a, b = g[k], g.get(k[:2] + ('route',), [])
        if b:
            oa, ob = sum(x['overlap'] for x in a), sum(x['overlap'] for x in b)
            tot[0] += oa
            tot[1] += ob
            fa, fb = m(a, lambda x: x['flow']), m(b, lambda x: x['flow'])
            rows.append((k[0], k[1], len(b), f"{fa:.0f} / {fb:.0f}", f"{100 * (fb / fa - 1):+.1f}%", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{oa} / {ob}", ' '.join(str(x['overlap']) for x in b), f"{m(a, hard):.0f} / {m(b, hard):.0f}"))
    rows.append(('all', '', '', '', '', '', f"{tot[0]} / {tot[1]}", '', ''))
    return table(('Net', 'veh/h', 'Seeds', 'Flow today / route', 'Change', 'Delay s', 'Contacts', 'Route, per seed', 'Hard brakes'), rows)


def route_faults():
    g = group(load('route_faults'), 'fault', 'plan')
    rows = []
    for k in sorted({x[0] for x in g}):
        a, b = g[(k, 'off')], g[(k, 'route')]
        rows.append((k, len(b), f"{m(a, lambda x: x['flow']):.0f} / {m(b, lambda x: x['flow']):.0f}", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}", f"{m(a, hard):.0f} / {m(b, hard):.0f}"))
    return table(('Fault', 'Seeds', 'Flow today / route', 'Delay s', 'Contacts', 'Hard brakes'), rows)


def loss_heavy():
    g = group(load('loss_heavy'), 'demand', 'fault', 'plan')
    rows = []
    for d, f in sorted({x[:2] for x in g}):
        a, b = g[(d, f, 'off')], g[(d, f, 'route')]
        fa, fb = m(a, lambda x: x['flow']), m(b, lambda x: x['flow'])
        rows.append((d, f.replace('loss', ''), len(b), f"{fa:.0f} / {fb:.0f}", f"{100 * (fb / fa - 1):+.1f}%", f"{m(a, lambda x: x['delay']):.1f} / {m(b, lambda x: x['delay']):.1f}", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}", f"{m(a, hard):.0f} / {m(b, hard):.0f}"))
    return table(('veh/h', 'Loss', 'Seeds', 'Flow today / route', 'Change', 'Delay s', 'Contacts', 'Hard brakes'), rows)


def capacity_chan():
    g = group(load('capacity_chan'), 'net', 'mix', 'plan')
    rows = []
    for n, mx in sorted({x[:2] for x in g}):
        a, b = g[(n, mx, 'off')], g[(n, mx, 'route')]
        fa, fb = m(a, lambda x: x['flow']), m(b, lambda x: x['flow'])
        rows.append((n, mx, len(b), f"{fa:.0f} / {fb:.0f}", f"{100 * (fb / fa - 1):+.1f}%", f"{sum(x['overlap'] for x in a)} / {sum(x['overlap'] for x in b)}"))
    return table(('Net', 'Mix', 'Seeds', 'Flow today / route', 'Change', 'Contacts'), rows)


def lateral():
    g = group(load('lateral'), 'net', 'mix', 'fault')
    base = group(load('capacity'), 'net', 'mix', 'plan')
    rows = []
    for k in sorted({x[:2] for x in g}):
        o = m(base.get(k + ('off',), []), lambda x: x['flow'])
        cells = []
        for f in ('old_table', 'peak4', 'alat3', 'alat5.5'):
            v = m(g.get(k + (f,), []), lambda x: x['flow'])
            cells.append(f"{v:.0f} ({100 * (v / o - 1):+.1f}%), {sum(x['overlap'] for x in g.get(k + (f,), []))}")
        rows.append((*k, f'{o:.0f}', *cells))
    return table(('Net', 'Mix', 'Today', 'Old corner speed', 'Peak 4 m/s2, speed up after the apex', 'a_lat 3', 'a_lat 5.5, the map'), rows)


def gate_route():
    rows_ = load('gate_route')
    g = group(rows_, 'net', 'mix', 'demand', 'fault')
    base = group(load('capacity'), 'net', 'mix', 'plan')
    rows = []
    for k in sorted(g, key=str):
        L = g[k]
        o = base.get((k[0], k[1], 'off'))
        ch = ''
        if o and k[2] > 6000 and k[0].startswith('j'):
            ch = f"{100 * (m(L, lambda x: x['flow']) / m(o, lambda x: x['flow']) - 1):+.1f}%"
        rows.append((*k, len(L), f"{m(L, lambda x: x['flow']):.0f}", ch, f"{m(L, lambda x: x['delay']):.1f}", sum(x['overlap'] for x in L), f"{m(L, hard):.0f}"))
    return table(('Net', 'Mix', 'veh/h', 'Case', 'Seeds', 'Flow', 'Against today', 'Delay s', 'Contacts', 'Hard brakes'), rows)


def stockholm2():
    p = P / 'stockholm2.jsonl'
    if not p.exists():
        return ''
    g = collections.defaultdict(list)
    for l in p.read_text().splitlines():
        r = json.loads(l)
        c = r['case']
        if 'error' not in r['result']:
            g[(c['place'], c['scale'], c['policy'])].append(r['result'])
    rows = []
    names = ('krauss_signals', 'av_signals', 'av_free', 'av_full', 'av_route')
    for pl, sc in sorted({k[:2] for k in g}):
        for n in names:
            L = g.get((pl, sc, n))
            if not L:
                continue
            rows.append((pl, f'{sc * 60:.0f}%', L[0].get('n_trips'), n, len(L), f"{m(L, lambda x: x['flow']):.0f}", f"{m(L, lambda x: x['time_loss']):.1f}", f"{m(L, lambda x: x['teleports']):.0f}", sum(x['overlap'] for x in L), sum(x.get('collisions', 0) for x in L), f"{m(L, hard):.0f}", f"{L[0].get('junctions')} of {L[0].get('junctions', 0) + L[0].get('refused', 0)}"))
    return table(('Net', 'Demand, of the fit', 'Trips', 'Policy', 'Seeds', 'Flow', 'Time lost s', 'Teleports', 'Contacts', 'Collisions', 'Hard brakes', 'Coordinated'), rows)


def stockholm():
    g = collections.defaultdict(list)
    for l in (D8 / 'stockholm.jsonl').read_text().splitlines():
        r = json.loads(l)
        c = r['case']
        if 'error' not in r['result']:
            g[(c['place'], c['demand'], c['policy'])].append(r['result'])
    rows = []
    for k in sorted(g):
        if k[2] != 'av_plan':
            continue
        p, f, s = g[k], g[(k[0], k[1], 'av_free')], g[(k[0], k[1], 'krauss_signals')]
        rows.append((k[0], k[1], f"{m(s, lambda x: x['flow']):.0f}", f"{m(f, lambda x: x['flow']):.0f}", f"{m(p, lambda x: x['flow']):.0f}", f"{m(s, lambda x: x['time_loss']):.0f} / {m(f, lambda x: x['time_loss']):.0f} / {m(p, lambda x: x['time_loss']):.0f}",
                     f"{sum(x['overlap'] for x in f)} / {sum(x['overlap'] for x in p)}", f"{sum(x.get('collisions', 0) for x in f)} / {sum(x.get('collisions', 0) for x in p)}", f"{p[0].get('junctions')} of {p[0].get('junctions', 0) + p[0].get('refused', 0)}"))
    return table(('Place', 'veh/h', 'Real signals', 'Free, today', 'Free, planned', 'Time lost s signals / today / planned', 'Overlaps today / planned, 2 seeds', 'Collisions', 'Coordinated'), rows)


def main():
    parts = dict(capacity=capacity, tiers=tiers, demand=demand, where=where, ablation=ablation, length=length, loss=loss, timing=timing, faults=faults, grid_meter=grid_meter, loss_heavy=loss_heavy, capacity_chan=capacity_chan, route_grid=route_grid, route_faults=route_faults, lateral=lateral, gate_route=gate_route, stockholm2=stockholm2)
    out = []
    for name, f in parts.items():
        try:
            out.append(f'## {name}\n\n{f()}')
        except Exception as e:
            out.append(f'## {name}\n\nnot ready: {e!r}\n')
    (P / 'tables.md').write_text('\n'.join(out))
    print('\n'.join(out))


if __name__ == '__main__':
    main()
