"""What the GUI's trust labels can read: per driver, the latest run's status per level and gate check, with no total.
Written to <served>/bench/trust.json by the dashboard build. A label moves up only on the gate's evidence."""
import json
from pathlib import Path

import score


def build(runs):
    out = {}
    for r in runs:
        if r.get('overrides'):
            continue
        d = r['driver']
        if d in out and r['run_id'] < out[d]['run_id']:
            continue
        gates = {}
        for m in r['metrics'].values():
            if m['tag'] in 'PW':
                gates.setdefault(m['gate'], []).append(m['status'])
        gate = {g: score.worst(v) for g, v in gates.items()}
        allpass = all(s in score.PASSING for s in gate.values())
        out[d] = dict(run_id=r['run_id'], commit=r['commit'], config=r['config_hash'], mode=r['mode'], levels={k: v['status'] for k, v in r['levels'].items()}, gates=gate, matches_real_day=False if not allpass else None,
                      note='No scenario earns matches_real_day from here until every gate check passes on held-out data, through an approved reveal.')
    return out
