#!/usr/bin/env python3
"""Print signal, wall, curve, speed and lane-change results for one dt. python3 show.py LOCAL DT"""
import json
import sys
O, dt = sys.argv[1] + '/out/', sys.argv[2]


def get(a, *ks):
    for k in ks:
        if a is None:
            return None
        a = a.get(k)
    return a


def load(s, x):
    try:
        return json.load(open(O + f'{s}_{x}_dt{dt}/metrics.json'))
    except Exception:
        return None


for x in ['main', 'phys', 'hum']:
    a = load('signal', x)
    if a:
        s = a['signal']
        print('SIGNAL', dt, x, 'acc', a['acc_max'], a['acc_min'], 'raw', a['raw_max'], a['raw_min'], 'jerk', a['jerk'], 'jmax', a['jerk_max'])
        print('   by_speed', {k: (v['acc'] and (v['acc']['p50'], v['acc']['p95']), v['dec'] and (v['dec']['p50'], v['dec']['p95'], v['dec']['p99'])) for k, v in a['by_speed'].items()})
        print('   stops', a['stops']['n'], a['stops']['mean'], a['stops']['peak'])
        print('   launch', a['launches']['peak'], 't5', get(a, 'launches', 't5', 'p50'), 'd5', get(a, 'launches', 'd5', 'p50'), 't10', get(a, 'launches', 't10', 'p50'), 'd10', get(a, 'launches', 'd10', 'p50'))
        print('   first', s.get('first_start'), 't5', s.get('first_t5'), 't10', s.get('first_t10'), 'peak', s.get('first_peak'), 'lag', s.get('start_lag'))
        print('   headway', [s['headway'].get(str(k), {}).get('median') for k in range(1, 11)], 'sat', s['sat_headway'], 'lost', s['lost_time'], 'stand', a['standing_gap'], 'dec>', a['share_dec_gt'], 'acc>', a['share_acc_gt'])
        print('   yellow', {k: v['stop'] for k, v in s['yellow']['stop_by_ttl'].items()}, 'n', s['yellow']['n'], 'need', s['yellow']['stop_need'], 'peak', s['yellow']['stop_peak'], 'red', s['yellow']['ran_red'])
for x in ['main', 'phys', 'hum']:
    a = load('wall', x)
    if a:
        print('WALL', dt, x, {k: (v['n'], v['dist_min'], v['peak_hardest'], v['peak_p50'], v['dist_p50']) for k, v in a['wall'].items()}, 'dec>', a['share_dec_gt'], 'raw', a['raw_min'])
for x in ['main', 'phys', 'hum']:
    a = load('curves', x)
    if a:
        print('CURV', dt, x, [(c['limit'], c['R'], c['v_mean'], c['ay']) for c in a['curves'] if c['limit'] == 50 or c['R'] <= 30])
for x in ['main', 'phys', 'hum']:
    a = load('speeds', x)
    if a:
        print('SPEEDS', dt, x, 'tg', {k: (v['p5'], v['p50'], v['p95']) for k, v in a['time_gap'].items()}, 'acc', a['acc_max'], a['acc_min'], 'raw', a['raw_min'], 'dec>', a['share_dec_gt'], 'by', {k: (v['dec'] and v['dec']['p95']) for k, v in a['by_speed'].items()}, 'jerk', a['jerk'])
for x in ['main', 'phys', 'hum']:
    a = load('mix', x)
    if a:
        print('MIX', dt, x, {k: dict(L=v.get('length'), stop=get(v, 'stops', 'peak', 'p50'), a=get(v, 'launches', 'peak', 'p50'), t5=get(v, 'launches', 't5', 'p50'), t10=get(v, 'launches', 't10', 'p50')) for k, v in a['mix'].items()})
for s in ['lanedrop', 'merge', 'junction', 'priority']:
    for x in ['main', 'phys', 'hum']:
        a = load(s, x)
        if a:
            print(s.upper(), dt, x, 'acc', a['acc_max'], a['acc_min'], 'raw', a['raw_max'], a['raw_min'], 'jerk95', a['jerk']['p95'], 'dec>', a['share_dec_gt'], 'rep', {k: v for k, v in (a.get('report') or {}).items() if v}, 'lc', {k: a['lc'][k] for k in a['lc'] if k != 'note'}, 'stop', get(a, 'stops', 'peak', 'p50'), get(a, 'stops', 'peak', 'p1'), 'launch', get(a, 'launches', 'peak', 'p50'), 'stand', get(a, 'standing_gap', 'p50'))
