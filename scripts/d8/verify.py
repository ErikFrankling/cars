#!/usr/bin/env python3
"""Parts run on CPU Vulkan, sampled again on the RX 7900 XT, so the tables can say how far the two agree."""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runs import D8, GATE, run_case

cars = sys.argv[1]
work = Path('/tmp/d8/verifywork')
work.mkdir(parents=True, exist_ok=True)
rng = random.Random(8)
out = D8 / 'verify.jsonl'
with out.open('w') as f:
    for part, n in (('stalls', 3), ('t', 4), ('grid', 6), ('meter_seeds', 6)):
        rows = [json.loads(l) for l in (D8 / f'{part}.jsonl').read_text().splitlines()]
        for r in rng.sample(rows, n):
            g = run_case(r['case'], work, cars)
            f.write(json.dumps(dict(part=part, case=r['case'], cpu=r['result'], gpu=g)) + '\n')
            f.flush()
            print(part, r['case']['net'], r['case']['demand'], r['case']['mode'], r['case'].get('meter', 0), 'flow', r['result']['flow'], g.get('flow'), 'overlap', r['result']['overlap'], g.get('overlap'), flush=True)
GATE.leave()
