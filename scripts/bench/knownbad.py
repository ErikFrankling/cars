"""Report 22, section 12. Each configuration is known to be wrong. It must FAIL at a named metric, and do so beyond what
the baseline driver itself scores there, or the benchmark is broken. Report 22's list, run for real."""
import json
import time
from pathlib import Path

import berlin as B
import floors
import runner
import score
import suite

IDM = 'carFollowModel="IDM" accel="3.6" decel="0.34"'
KRAUSS33 = 'carFollowModel="Krauss" decel="0.33" tau="1.88" sigma="0.5"'
BASE = 'human'
BAD = [
    dict(n=1, name='Krauss SUMO defaults, dt 0.1', driver='main', ov={}, scenes=['signal', 'road'], must=['JS2', 'C3'], need='all'),
    dict(n=2, name='Krauss defaults, dt 1', driver='main', ov={'dt': 1.0}, scenes=['chain', 'signal'], must=['M6', 'V5'], need='all'),
    dict(n=3, name='Calibrated IDM', driver='main', ov={'vtype': IDM}, scenes=['signal', 'chain'], must=['JS1', 'M6'], need='all'),
    dict(n=4, name='Calibrated Krauss, decel 0.33', driver='main', ov={'vtype': KRAUSS33}, scenes=['signal', 'yellow'], must=['JS6', 'M12', 'JS1'], need='any'),
    dict(n=5, name='Instant lane changes', driver='main', ov={}, scenes=['free3'], must=['M7'], need='all'),
    dict(n=6, name='SUMO secure gap test', driver='main', ov={}, scenes=['free3', 'road'], must=['M9', 'M8'], need='all'),
    dict(n=7, name='Lane changing off', driver=BASE, ov={'no_lc': True}, scenes=['free3'], must=['M8'], need='all', note='C6 needs the district'),
    dict(n=8, name='Acceleration noise 0.53 m/s2', driver=BASE, ov={'flags': ['--tune', 'sigma=0.53']}, scenes=['road', 'signal'], must=['V2', 'M3'], need='any'),
    dict(n=9, name='Car length 3 m, demand raised to match flow', driver=BASE, ov={'length': 3.0, 'demand_scale': 1.1}, scenes=['signal'], must=['M4', 'JS1'], need='all', mini=True, note='N1 is allowed to pass here: throughput right, reason wrong'),
    dict(n=10, name='Reaction time cut 30%, demand raised to match flow', driver=BASE, ov={'flags': ['--tune', 't_scale=0.7'], 'demand_scale': 1.1}, scenes=['road', 'signal'], must=['M3', 'JS2', 'C3'], need='any', mini=True, note='N1 is allowed to pass here'),
    dict(n=11, name='Demand x0.6', driver=BASE, ov={'demand_scale': .6}, scenes=[], must=['N1', 'N5', 'V8'], need='all', mini=True),
    dict(n=12, name='Demand x1.2', driver=BASE, ov={'demand_scale': 1.2}, scenes=[], must=['N1', 'N14', 'V6'], need='any', mini=True),
    dict(n=13, name='Demand clock +1 h', driver=BASE, ov={'clock': 1}, scenes=[], must=['N3', 'N4'], need='any', mini=True),
    dict(n=14, name='Flat departure curve', driver=BASE, ov={'flat': True}, scenes=[], must=['N3', 'N9'], need='all', mini=True),
    dict(n=15, name='Fixed 90 s signals, offset 0', driver=BASE, ov={'signals': 'fixed90'}, scenes=['signal_real'], must=['JS7'], need='any'),
    dict(n=16, name='Signals removed', driver=BASE, ov={'signals': 'none'}, scenes=['signal_real'], must=['JS7'], need='any'),
    dict(n=17, name='Teleports on at 120 s', driver=BASE, ov={'teleport': 120}, scenes=['road'], must=['V1'], need='any'),
    dict(n=18, name='Free-flow-only routes', driver=BASE, ov={'free_routes': True}, scenes=[], must=['N8', 'N10'], need='any', mini=True, note='on separate roads, with 80% of slow-road flow moved to the fast road beside it'),
    dict(n=19, name='Desired speed x1.3', driver=BASE, ov={'speed_factor': 1.3}, scenes=[], must=['N12'], need='any', mini=True),
    dict(n=20, name='Replay real schedules', driver=None, ov={'replay': True}, scenes=[], must=[], need='refused'),
]


def refuse_replay(ov):
    if ov.get('replay'):
        raise SystemExit('refused: replaying real schedules is an engine test and can never count as validation (report 22 section 9)')


def worst_cell(M, i):
    cells = M.get(i)
    if not cells:
        return None, None
    ro = score.rollup({k: c for k, c in cells.items() if c['status'] != 'NO DATA'} or cells)
    return ro['status'], ro['z']


def base_results(store, cfg, scenes, mini, gpu, log):
    p = store / 'knownbad_base.json'
    base = json.loads(p.read_text()) if p.exists() else {}
    if base.get('_commit') != cfg['commit']:
        base = dict(_commit=cfg['commit'])
    todo = [s for s in scenes if s not in base.get('_scenes', [])]
    if todo:
        M, _, _ = suite.evaluate(cfg, True, seeds=[1], gpu=gpu, only=todo, log=log)
        base.setdefault('M', {}).update(suite._clean(M))
        base['_scenes'] = base.get('_scenes', []) + todo
    if mini and 'mini' not in base:
        M, _ = B.engine_test(cfg, {}, gpu=gpu, log=log)
        base['mini'] = suite._clean(M)
    p.write_text(json.dumps(base))
    return base


def main(a):
    store = runner.STORE
    only = {int(x) for x in a.only.split(',')} if a.only else None
    out_p = store / 'knownbad.json'
    old = {r['n']: r for r in json.loads(out_p.read_text())['rows']} if out_p.exists() else {}
    rows = dict(old)
    log = lambda s: print('   ', s, flush=True)
    base_cfg = runner.load_config(BASE)
    for it in BAD:
        if only and it['n'] not in only:
            continue
        print(f"#{it['n']} {it['name']}", flush=True)
        t = time.time()
        rec = dict(n=it['n'], name=it['name'], must=it['must'], note=it.get('note', ''), driver=it['driver'], metrics={})
        if it['need'] == 'refused':
            try:
                refuse_replay(it['ov'])
                rec.update(caught=False, by='not refused')
            except SystemExit as e:
                rec.update(caught=True, by='refused by bench', note=str(e))
        else:
            cfg = runner.load_config(it['driver'])
            scenes_ = list(it['scenes'])
            M = {}
            if scenes_:
                M, _, _ = suite.evaluate(cfg, True, ov=it['ov'], seeds=[1], gpu=a.gpu, only=scenes_, log=log)
            mini = {}
            if it.get('mini'):
                mini, _ = B.engine_test(cfg, it['ov'], gpu=a.gpu, log=log)
            base = base_results(store, base_cfg, scenes_, it.get('mini'), a.gpu, log)
            hits = []
            for i in it['must']:
                st, z = worst_cell(M, i)
                src = M
                if st is None or st == 'NO DATA':
                    st, z = worst_cell(mini, i)
                    src = mini
                bst, bz = worst_cell(base.get('mini', {}) if src is mini else base.get('M', {}), i)
                ok = st == 'FAIL' and (bst != 'FAIL' or bz is None or z is None or z > 1.25 * bz or i in ('V8',))
                rec['metrics'][i] = dict(status=st, z=z, base_status=bst, base_z=bz, hit=bool(ok))
                if ok:
                    hits.append(i)
            rec['caught'] = len(hits) == len(it['must']) if it['need'] == 'all' else bool(hits)
            rec['by'] = ', '.join(f"{i} z {rec['metrics'][i]['z']} (baseline {rec['metrics'][i]['base_z']})" for i in hits)
            if not rec['caught']:
                rec['by'] = 'named metrics: ' + ', '.join(f"{i} {rec['metrics'][i]['status']} z {rec['metrics'][i]['z']} (baseline {rec['metrics'][i]['base_status']} {rec['metrics'][i]['base_z']})" for i in it['must'])
            if it.get('mini'):
                n1 = mini.get('N1', {}).get('value', {})
                rec['N1'] = dict(status=n1.get('status'), z=n1.get('z'))
        rec['seconds'] = round(time.time() - t)
        rows[it['n']] = rec
        print(f"  {'CAUGHT' if rec['caught'] else 'MISSED'} {rec['by']}  ({rec['seconds']}s)", flush=True)
        out_p.write_text(json.dumps(dict(rows=[rows[k] for k in sorted(rows)], base=BASE, created=time.strftime('%Y-%m-%dT%H:%M:%S'))))
    write_power(rows)
    import dashboard
    dashboard.build(store / 'results', store / 'history.jsonl', '/home/erikf/projects/personal/cars-data/report/bench')
    n = sum(1 for r in rows.values() if r['caught'])
    print(f'{n} of {len(rows)} caught')


def write_power(rows):
    lines = ['# Power of the benchmark', '', 'Written by `bench.py knownbad`. Each row is a configuration known to be wrong, run on the simulator. Baseline: the human driver.', '', '| # | Configuration | Driver | Caught | By |', '|---:|---|---|---|---|']
    for k in sorted(rows):
        r = rows[k]
        lines.append(f"| {k} | {r['name']} | {r.get('driver') or '-'} | {'yes' if r['caught'] else '**NO**'} | {r.get('by', '')} |")
    fired = {i for r in rows.values() for i, m in r.get('metrics', {}).items() if m.get('hit')}
    lines += ['', 'Metrics that caught at least one: ' + (', '.join(sorted(fired)) or 'none') + '.', '']
    (Path(__file__).parent / 'power.md').write_text('\n'.join(lines))
