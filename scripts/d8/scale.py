#!/usr/bin/env python3
"""Compute cost (build spec, test 11): ms per step against vehicles and coordinated junctions, kernel by kernel."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runs import GATE, D8, ROOT

W = Path('/home/erikf/projects/personal/cars-data/truth/d8')
NETS = ROOT / 'research/truth/fig/09-nets'
CASES = [(NETS / 'j2.net.xml', 5200, 'M', 'B1'), (NETS / 'grid2.net.xml', 16000, 'M', ','.join(f'{x}{y}' for x in 'BCD' for y in '123')),
         (W / 'scale20.net.xml', 25000, 'M', 'all'), (W / 'scale50.net.xml', 80000, 'M', 'all')]
cars = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'target/release/cars')
out = D8 / 'scale.jsonl'
with out.open('w') as f:
    for net, d, mix, cj in CASES:
        rou = Path('/tmp/d8') / f'scale_{net.stem}.rou.xml'
        subprocess.run([sys.executable, str(ROOT / 'scripts/d8/demand.py'), '--net', str(net), '--out', str(rou), '--demand', str(d), '--mix', mix, '--end', '300'], check=True)
        for with_cj in (True, False):
            GATE.enter()
            args = [cars, 'av', '--net', str(net), '--routes', str(rou), '--end', '300', '--cj-warm', '60', '--profile-at', '200']
            if with_cj:
                args += ['--cj', cj]
            r = subprocess.run(args, capture_output=True, text=True)
            GATE.leave()
            res = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else dict(error=r.stderr[-500:])
            f.write(json.dumps(dict(net=net.stem, demand=d, cj=with_cj, result=res)) + '\n')
            f.flush()
            print(net.stem, with_cj, {k: res.get(k) for k in ('junctions', 'mean_active', 'ms_per_step', 'gpu_mb', 'coord_mb', 'overlap', 'flow', 'collisions', 'error')}, flush=True)
