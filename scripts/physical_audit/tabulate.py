#!/usr/bin/env python3
"""Print the audit's simulated numbers as compact tables. python3 tabulate.py --root LOCAL [--dt 1]"""
import argparse
import json
from pathlib import Path

D = ['main', 'phys', 'hum']


def m(root, scene, drv, dt):
    p = Path(root) / 'out' / f'{scene}_{drv}_dt{dt}' / 'metrics.json'
    return json.loads(p.read_text()) if p.exists() else None


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--root', required=True)
    a.add_argument('--dt', default='1')
    a = a.parse_args()
    for scene in ['signal', 'mix', 'speeds', 'lanedrop', 'merge', 'junction', 'priority', 'wall', 'curves', 'free', 'city']:
        print('=====', scene, 'dt', a.dt)
        for d in D:
            x = m(a.root, scene, d, a.dt)
            if not x:
                print(d, 'none')
                continue
            print(f"-- {d} veh {x['vehicles']} acc {x['acc_max']} {x['acc_min']} raw {x['raw_max']} {x['raw_min']} jerk {x['jerk']} max {x['jerk_max']} rep {x.get('report')}")
            print('  dec>', x['share_dec_gt'], 'acc>', x['share_acc_gt'])
            print('  by_speed', {k: (v['acc'] and (v['acc']['p50'], v['acc']['p95']), v['dec'] and (v['dec']['p50'], v['dec']['p95'], v['dec']['p99'])) for k, v in x['by_speed'].items()})
            if 'stops' in x:
                print('  stops', x['stops']['n'], 'mean', x['stops']['mean'], 'peak', x['stops']['peak'])
                print('   by_v0', x['stops']['by_v0'])
            if 'launches' in x:
                print('  launch', x['launches'])
            if x.get('time_gap'):
                print('  tg', {k: (v['p5'], v['p50'], v['p95']) for k, v in x['time_gap'].items()})
            print('  stand', x.get('standing_gap'), 'lc', x.get('lc'))
            for k in ['signal', 'free', 'curves', 'wall', 'mix']:
                if k in x:
                    print(' ', k, json.dumps(x[k])[:1800])


if __name__ == '__main__':
    main()
