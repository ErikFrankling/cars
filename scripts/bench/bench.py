#!/usr/bin/env python3
"""The benchmark: what "true to life" means, in one command. See README.md and research/truth/data-hunt/22-what-true-to-life-means.md.

    bench.py selftest
    bench.py run --driver human --mode fast
    bench.py knownbad [--only 1,2,3]
    bench.py compare RUN_A RUN_B
    bench.py history
    bench.py dashboard
    bench.py reveal --locked SET --reason "..."      needs an approval only Erik can give
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.path.insert(0, str(Path(__file__).resolve().parent))

import runner
import score

HERE = Path(__file__).resolve().parent
STORE = runner.STORE
RES = STORE / 'results'
HIST = STORE / 'history.jsonl'
SERVE = Path('/home/erikf/projects/personal/cars-data/report/bench')


def bench_commit():
    if os.environ.get('BENCH_COMMIT'):
        return os.environ['BENCH_COMMIT']
    return subprocess.check_output(['git', '-C', str(HERE), 'rev-parse', 'HEAD'], text=True).strip()


def append_history(res, file=None):
    """Append-only, and each line carries the hash of the one before, so an edit shows."""
    HIST.parent.mkdir(parents=True, exist_ok=True)
    prev = ''
    if HIST.exists():
        lines = HIST.read_text().splitlines()
        prev = hashlib.sha256(lines[-1].encode()).hexdigest()[:16] if lines else ''
    row = dict(run_id=res['run_id'], created=res['created'], driver=res['driver'], mode=res['mode'], commit=res['commit'], bench_commit=res['bench_commit'], binary_sha=res['binary_sha'],
               config_hash=res['config_hash'], seeds=res['seeds'], levels=res['levels'], statuses={k: v['status'] for k, v in res['metrics'].items()}, zs={k: v['z'] for k, v in res['metrics'].items()}, prev=prev)
    with open(HIST, 'a') as f:
        f.write(json.dumps(row) + '\n')


def save(res):
    RES.mkdir(parents=True, exist_ok=True)
    (RES / f"{res['run_id']}.json").write_text(json.dumps(res))
    append_history(res)


def load(run_id):
    p = RES / f'{run_id}.json'
    if not p.exists():
        hits = sorted(RES.glob(f'*{run_id}*.json'))
        if not hits:
            raise SystemExit(f'no run {run_id}')
        p = hits[-1]
    return json.loads(p.read_text())


def cmd_selftest(a):
    import floors
    ok, res = floors.selftest(HERE / 'floors/selftest.json')
    for r in res['rows']:
        print(f"{r['over']:>3} over  {r['name']}  network: {','.join(r['network']) or 'none'}")
    for k, v in res['checks'].items():
        print('PASS' if v else 'FAIL', k)
    print('real days flagged', res['false_alarms'])
    if not ok:
        raise SystemExit(1)


def card(res, top=8):
    n = {}
    for m in res['metrics'].values():
        n[m['status']] = n.get(m['status'], 0) + 1
    print(f"{res['driver']} {res['mode']}  commit {res['commit'][:8]}  config {res['config_hash']}  seeds {res['seeds']}  run {res['run_id']}")
    print('  ' + '  '.join(f'{s} {n.get(s, 0)}' for s in score.ORDER if n.get(s)))
    for lv, x in res['levels'].items():
        print(f"  level {lv}: {x['status']:<13} top z {x['top_z']}")
    rows = sorted([m for m in res['metrics'].values() if m['z'] is not None and m['status'] != 'NO DATA'], key=lambda m: -m['z'])
    print('  worst gaps:')
    for m in rows[:top]:
        print(f"    {m['id']:<5} z {m['z']:>8.2f} {m['status']:<13} {m['name']}")


def cmd_run(a):
    import suite
    cfg = runner.load_config(a.driver)
    run_id = time.strftime('%Y%m%d-%H%M%S') + f'-{a.driver}-{a.mode}'
    only = a.scenes.split(',') if a.scenes else None
    berlin = None
    if a.berlin_factor or a.berlin_runs:
        import berlin as B
        berlin, secs = B.evaluate(cfg, gpu=a.gpu, factor=a.berlin_factor or '01', runs=a.berlin_runs.split(',') if a.berlin_runs else None)
    M, seconds, seeds = suite.evaluate(cfg, a.mode == 'fast', gpu=a.gpu, only=only if not a.reuse else [], berlin=berlin, log=lambda s: print(s, flush=True))
    if a.reuse:
        old = load(a.reuse)
        if old['driver'] != a.driver or old['commit'] != cfg['commit']:
            raise SystemExit('--reuse needs a run of the same driver and commit')
        for i, m in old['metrics'].items():
            if m['status'] == 'NO DATA':
                continue
            merged = dict(m['cells'])
            for k, c in M.get(i, {}).items():
                if k not in merged or merged[k]['status'] != 'FAIL':
                    merged[k] = c
            M[i] = merged
        seeds = old['seeds']
    res = suite.assemble(M, cfg, a.mode, seeds, seconds, suite.load_registry(), name=run_id, bench_commit=bench_commit())
    save(res)
    card(res)
    if not a.no_dashboard:
        import dashboard
        dashboard.build(RES, HIST, SERVE)


def cmd_compare(a):
    A, B = load(a.a), load(a.b)
    rows = []
    for i, m in B['metrics'].items():
        ma = A['metrics'].get(i)
        if not ma:
            continue
        for sub, c in m['cells'].items():
            ca = ma['cells'].get(sub)
            if not ca or 'D' not in c or 'D' not in ca:
                continue
            d = score.compare(ca, c)
            if d:
                rows.append(dict(id=i, sub=sub, tag=m['tag'], a=ca.get('S'), b=c.get('S'), za=ca.get('z'), zb=c.get('z'), sa=ca['status'], sb=c['status'], **d))
    better = [r for r in rows if r['verdict'] == 'better']
    worse = [r for r in rows if r['verdict'] == 'worse']
    pw_worse = [r for r in worse if r['tag'] in 'PW']
    if pw_worse and better:
        verdict = 'TRADE-OFF'
    elif pw_worse:
        verdict = 'WORSE'
    elif better:
        verdict = 'BETTER'
    else:
        verdict = 'SAME'
    print(f"{A['run_id']} -> {B['run_id']}: {verdict}. {len(better)} cells better, {len(worse)} worse, {len(rows) - len(better) - len(worse)} same.")
    for title, group in (('Better', better), ('Worse', worse)):
        if group:
            print(title + ':')
            for r in sorted(group, key=lambda r: r['hi'] if title == 'Better' else -r['lo']):
                print(f"  {r['id']:<5} {r['sub']:<22} S {r['a']} -> {r['b']}  z {r['za']} -> {r['zb']}  {r['sa']} -> {r['sb']}  [{r['lo']}, {r['hi']}] margin {r['eps']}")
    gone = [(i, A['metrics'][i]['status'], B['metrics'][i]['status']) for i in B['metrics'] if i in A['metrics'] and A['metrics'][i]['status'] != B['metrics'][i]['status']]
    if gone:
        print('Status changes: ' + ', '.join(f'{i} {x}->{y}' for i, x, y in gone))
    return verdict


def cmd_history(a):
    for line in HIST.read_text().splitlines():
        r = json.loads(line)
        n = {}
        for s in r['statuses'].values():
            n[s] = n.get(s, 0) + 1
        z = sorted([v for k, v in r['zs'].items() if v is not None], reverse=True)[:3]
        print(r['run_id'], r['commit'][:8], 'top z', z, ' '.join(f'{k}={v}' for k, v in sorted(n.items())))


def cmd_dashboard(a):
    import dashboard
    dashboard.build(RES, HIST, SERVE)
    print(SERVE / 'index.html')


def cmd_knownbad(a):
    import knownbad
    knownbad.main(a)


def cmd_reveal(a):
    import reveal
    reveal.reveal(a.locked, a.reason, a.run)


def cmd_approve(a):
    import reveal
    reveal.approve(a.locked, a.reason)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(required=True)
    s.add_parser('selftest').set_defaults(fn=cmd_selftest)
    r = s.add_parser('run')
    r.add_argument('--driver', required=True, choices=['main', 'sumo', 'physics', 'human', 'measured'])
    r.add_argument('--mode', choices=['fast', 'full'], default='fast')
    r.add_argument('--scenes')
    r.add_argument('--gpu', action='store_true', help='run on the real GPU, through the lock')
    r.add_argument('--berlin-factor', choices=['01', '05', '10'], help='also run the Berlin district at this demand; 10 is the whole demand')
    r.add_argument('--berlin-runs', help='score these existing runs under berlin2019/runs instead of running')
    r.add_argument('--reuse', help='keep the scene results of this earlier run of the same commit')
    r.add_argument('--no-dashboard', action='store_true')
    r.set_defaults(fn=cmd_run)
    k = s.add_parser('knownbad')
    k.add_argument('--only')
    k.add_argument('--gpu', action='store_true')
    k.set_defaults(fn=cmd_knownbad)
    c = s.add_parser('compare')
    c.add_argument('a')
    c.add_argument('b')
    c.set_defaults(fn=cmd_compare)
    s.add_parser('history').set_defaults(fn=cmd_history)
    s.add_parser('dashboard').set_defaults(fn=cmd_dashboard)
    x = s.add_parser('reveal')
    x.add_argument('--locked', required=True)
    x.add_argument('--reason', required=True)
    x.add_argument('--run', required=True, help='frozen tagged run to reveal for')
    x.set_defaults(fn=cmd_reveal)
    x = s.add_parser('approve')
    x.add_argument('--locked', required=True)
    x.add_argument('--reason', required=True)
    x.set_defaults(fn=cmd_approve)
    a = p.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
