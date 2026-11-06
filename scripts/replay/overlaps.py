"""Overlaps in a replay run: same-lane negative bumper gaps, by kind of pair. A simulated car overlapping a replayed
one is a harness artefact (replayed vehicles don't react); it ends that car's comparison.

    python3 -I scripts/replay/overlaps.py <fcd.csv> <matched.csv.gz>
"""
import sys, json
import numpy as np, pandas as pd
def find(fcd, matched):
    f = pd.read_csv(fcd, usecols=['time', 'trip', 'lane', 'pos', 'length']) if isinstance(fcd, str) else fcd
    m = pd.read_csv(matched) if isinstance(matched, str) else matched
    sim = set(m[m.sim].trip)
    f = f.sort_values(['time', 'lane', 'pos'])
    same = (f.time.values[1:] == f.time.values[:-1]) & (f.lane.values[1:] == f.lane.values[:-1])
    gap = f.pos.values[1:] - f.length.values[1:] - f.pos.values[:-1]
    k = np.where(same & (gap < 0))[0]
    fol, lead = f.trip.values[k], f.trip.values[k + 1]
    kind = np.where(np.isin(fol, list(sim)), 'sim', 'rep').astype(object) + '_behind_' + np.where(np.isin(lead, list(sim)), 'sim', 'rep')
    ev = pd.DataFrame(dict(t=f.time.values[k], fol=fol, lead=lead, kind=kind, gap=gap[k]))
    first = ev.sort_values('t').groupby(['fol', 'lead']).first().reset_index()
    mixed = {}
    for r in first.itertuples():
        if 'sim' in r.kind and 'rep' in r.kind:
            car = r.fol if r.fol in sim else r.lead
            mixed[car] = min(mixed.get(car, 1e18), float(r.t))
    return dict(samples_by_kind=ev.kind.value_counts().to_dict(), pairs_by_kind=first.kind.value_counts().to_dict(), first_overlap_with_replayed=mixed)


if __name__ == '__main__':
    print(json.dumps(find(sys.argv[1], sys.argv[2])))
