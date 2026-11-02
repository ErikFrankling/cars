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
    dict(n=8, name='Acceleration noise 0.53 m/s2', driver='human53', ov={}, scenes=['road', 'signal'], must=['V2', 'M3'], need='any'),
    dict(n=9, name='Car length 3 m, demand raised to match flow', driver=BASE, ov={'length': 3.0}, scenes=['signal'], must=['M4', 'JS1'], need='any', mini={'length': 3.0}, note='The point of this case: N1 may pass while levels 1 and 2 fail'),
    dict(n=10, name='Reaction time cut 30%, demand raised to match flow', driver=BASE, ov={'flags': ['--tune', 't_scale=0.7']}, scenes=['road', 'signal'], must=['M3', 'JS2', 'C3'], need='any', mini={'tau': .7}, note='The point of this case: N1 may pass while levels 1 to 3 fail'),
    dict(n=11, name='Demand x0.6', driver=None, ov={'demand_scale': .6}, scenes=[], must=['N1', 'N5', 'V8'], need='all', mini={'demand_scale': .6}),
    dict(n=12, name='Demand x1.2', driver=None, ov={'demand_scale': 1.2}, scenes=[], must=['N1', 'N14', 'V6'], need='any', mini={'demand_scale': 1.2}),
    dict(n=13, name='Demand clock +1 h', driver=None, ov={'clock': 1}, scenes=[], must=['N3', 'N4'], need='any', mini={'clock': 1}),
    dict(n=14, name='Flat departure curve', driver=None, ov={'flat': True}, scenes=[], must=['N3', 'N9'], need='all', mini={'flat': True}),
    dict(n=15, name='Fixed 90 s signals, offset 0', driver=BASE, ov={'signals': 'fixed90'}, scenes=['signal_real'], must=['JS7'], need='any'),
    dict(n=16, name='Signals removed', driver=BASE, ov={'signals': 'none'}, scenes=['signal_real'], must=['JS7'], need='any'),
    dict(n=17, name='Teleports on at 120 s', driver=BASE, ov={'teleport': 120}, scenes=['road'], must=['V1'], need='any'),
    dict(n=18, name='Free-flow-only routes', driver=None, ov={'free_routes': True}, scenes=[], must=['N8', 'N10'], need='any', mini={'free_routes': True}, note='on separate roads, with 80% of slow-road flow moved to the fast road beside it'),
    dict(n=19, name='Desired speed x1.3', driver=None, ov={'speed_factor': 1.3}, scenes=[], must=['N12'], need='any', mini={'speed_factor': 1.3}),
    dict(n=20, name='Replay real schedules', driver=None, ov={'replay': True}, scenes=[], must=[], need='refused'),
]


def refuse_replay(ov):
    if ov.get('replay'):
        raise SystemExit('refused: replaying real schedules is an engine test and can never count as validation (report 22 section 9)')


def worst_cell(M, i):
    cells = {k: c for k, c in (M.get(i) or {}).items() if c['status'] != 'NO DATA'}
    if not cells:
        return None, None
    ro = score.rollup(cells)
    return ro['status'], ro['z']


def differs(M, B, i):
    """Is this configuration really somewhere else than the baseline on this metric, by more than the ruler?"""
    for sub, c in (M.get(i) or {}).items():
        b = (B.get(i) or {}).get(sub)
        if not b or c.get('F') in (None, 0):
            continue
        x, y = c.get('value', c.get('S')), b.get('value', b.get('S'))
        if x is not None and y is not None and abs(x - y) > c['F']:
            return True
    return False


def human_fast():
    runs = sorted((runner.STORE / 'results').glob('*-human-fast.json'))
    if not runs:
        raise SystemExit('run the human baseline first')
    return {i: m['cells'] for i, m in json.loads(runs[-1].read_text())['metrics'].items()}


def mini_base(store, gpu, log):
    """The engine test uses main's binary: demand-side cases do not depend on the driver, and it is four times cheaper on the CPU."""
    p = store / 'knownbad_mini_base.json'
    cfg = runner.load_config('main')
    if p.exists():
        b = json.loads(p.read_text())
        if b.get('commit') == cfg['commit']:
            return b['M']
    M, _ = B.engine_test(cfg, {}, gpu=gpu, log=log)
    p.write_text(json.dumps(dict(commit=cfg['commit'], M=suite._clean(M))))
    return suite._clean(M)


def main(a):
    store = runner.STORE
    only = {int(x) for x in a.only.split(',')} if a.only else None
    out_p = store / 'knownbad.json'
    rows = {r['n']: r for r in json.loads(out_p.read_text())['rows']} if out_p.exists() else {}
    log = lambda s: print('   ', s, flush=True)
    base = human_fast()
    for it in BAD:
        if only and it['n'] not in only:
            continue
        print(f"#{it['n']} {it['name']}", flush=True)
        t = time.time()
        rec = dict(n=it['n'], name=it['name'], must=it['must'], note=it.get('note', ''), driver=it['driver'] or ('main (engine test)' if it.get('mini') else None), metrics={})
        if it['need'] == 'refused':
            try:
                refuse_replay(it['ov'])
                rec.update(caught=False, by='not refused')
            except SystemExit as e:
                rec.update(caught=True, by='refused by bench', note=str(e))
        else:
            M = {}
            if it['scenes']:
                M, _, _ = suite.evaluate(runner.load_config(it['driver']), True, ov=it['ov'], seeds=[1], gpu=a.gpu, only=it['scenes'], log=log)
                M = suite._clean(M)
            mini = {}
            if it.get('mini'):
                mini, _ = B.engine_test(runner.load_config('main'), it['mini'], gpu=a.gpu, log=log)
                mini = suite._clean(mini)
            mbase = mini_base(store, a.gpu, log) if it.get('mini') else {}
            hits = []
            for i in it['must']:
                st, z = worst_cell(M, i)
                src, ref = M, base
                if st is None and i in mini:
                    st, z = worst_cell(mini, i)
                    src, ref = mini, mbase
                bst, bz = worst_cell(ref, i)
                distinct = bst != 'FAIL' or differs(src, ref, i)
                hit = st == 'FAIL' and distinct
                rec['metrics'][i] = dict(status=st, z=z, base_status=bst, base_z=bz, hit=hit)
                if hit:
                    hits.append(i)
            rec['caught'] = len(hits) == len(it['must']) if it['need'] == 'all' else bool(hits)
            fired = ', '.join(f"{i} z {rec['metrics'][i]['z']} (baseline {rec['metrics'][i]['base_status']} {rec['metrics'][i]['base_z']})" for i in hits)
            quiet = ', '.join(f"{i} {rec['metrics'][i]['status']} z {rec['metrics'][i]['z']}" for i in it['must'] if i not in hits)
            rec['by'] = fired + (f'; did not fire: {quiet}' if quiet else '')
            if it.get('mini'):
                n1 = (mini.get('N1') or {}).get('value') or {}
                rec['N1'] = dict(status=n1.get('status'), z=n1.get('z'))
                rec['note'] = (rec['note'] + f" N1 on the engine test: {n1.get('status')}, z {n1.get('z')}.").strip()
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
