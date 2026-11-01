#!/usr/bin/env python3
"""A real junction and a district of the Stockholm net, signal-free against its own signals.

No count data: demand_net.py loads the cut with through traffic. The net has no crossing edges, so no pedestrians
exist here, whatever is true on the street. Results in research/truth/fig/d8/stockholm.jsonl."""
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runs import GATE, D8, ROOT, key

NET = '/home/erikf/projects/personal/cars-data/truth/maps/builds/v5_inventory/net.xml'
JUNCTION = 'cluster_1363066780_1363066782_1363066783_1363066785_1363066786_6024866893'
PLACES = {
    'district': dict(box='22100,15900,23100,16900', cj='all', demands=(1500, 3000, 5000, 8000), meter=150),
    'junction': dict(box='21900,16200,22600,16750', cj=None, demands=(800, 1500, 2500, 4000), meter=120),
    # Chained OSM nodes merged into one junction by netconvert, so that short lanes inside them no longer refuse a coordinator.
    'district_joined': dict(box='22100,15900,23100,16900', cj='all', demands=(1500, 3000, 5000, 8000), meter=150, join=True),
}


def net_for(place, work):
    out = work / f'{place}.net.xml'
    if not out.exists():
        subprocess.run(['netconvert', '-s', NET, '--keep-edges.in-boundary', PLACES[place]['box'], '--keep-edges.components', '1', '--no-warnings', 'true', *(['--junctions.join', 'true', '--junctions.join-dist', '25'] if PLACES[place].get('join') else []), '-o', str(out)], check=True)
    return out


def junction_id(net):
    for line in open(net):
        if '<junction id="cluster_1363066780_1363066782' in line:
            return line.split('"')[1]
    raise SystemExit('junction missing')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cars', default=str(ROOT / 'target/release/cars'))
    ap.add_argument('--work', default='/home/erikf/projects/personal/cars-data/truth/d8')
    ap.add_argument('--end', type=float, default=900.0)
    ap.add_argument('--seeds', default='0,1')
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    path = D8 / 'stockholm.jsonl'
    done = {json.loads(l)['key'] for l in path.read_text().splitlines()} if path.exists() else set()
    for place, p in PLACES.items():
        net = net_for(place, work)
        cj = p['cj'] or junction_id(net)
        for d in p['demands']:
            for seed in map(int, a.seeds.split(',')):
                plan = ('av_plan', 'av', ['--cj', cj, '--cj-plan', 'full'])
                free = ('av_free', 'av', ['--cj', cj])
                policies = (('krauss_signals', 'krauss', []), free, plan) if p.get('join') else (
                    ('krauss_signals', 'krauss', []), ('av_signals', 'av', []),
                    ('av_signal_baseline', 'av', ['--cj', cj, '--cj-mode', 'signal', '--cj-sig-max', '30', '--cj-sig-gap', '2']),
                    free, ('av_free_b', 'av', ['--cj', cj, '--cj-level-b']),
                    ('av_free_meter', 'av', ['--cj', cj, '--cj-meter', str(p['meter'])]), plan)
                for name, typ, args in policies:
                    c = dict(place=place, demand=d, seed=seed, policy=name, end=a.end)
                    k = key(c)
                    if k in done:
                        continue
                    routes = work / f'{k}.rou.xml'
                    subprocess.run([sys.executable, str(ROOT / 'scripts/d8/demand_net.py'), '--net', str(net), '--out', str(routes), '--demand', str(d), '--seed', str(seed), '--end', str(a.end), '--type', typ], check=True, capture_output=True)
                    GATE.enter()
                    r = subprocess.run([a.cars, 'av', '--net', str(net), '--routes', str(routes), '--end', str(a.end), '--cj-warm', '200', '--seed', str(seed)] + args, capture_output=True, text=True)
                    routes.unlink(missing_ok=True)
                    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else dict(error=r.stderr[-800:])
                    out.pop('profile', None)
                    with path.open('a') as f:
                        f.write(json.dumps(dict(key=k, case=c, result=out)) + '\n')
                    print(place, d, seed, name, 'flow', round(out.get('flow', -1)), 'loss', round(out.get('time_loss', -1), 1), 'overlap', out.get('overlap'), 'coll', out.get('collisions'), 'tele', out.get('teleports'), 'inv', out.get('invariant'), 'stuck', out.get('stuck'), 'coordinated', out.get('junctions'), out.get('error', '')[:200], flush=True)
    GATE.leave()


if __name__ == '__main__':
    main()
