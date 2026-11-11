"""Cars leaving each edge, simulation against recording (research/truth/replay/LOCK.md): where the simulated stream
carries less than the real one, and from when.

    python3 -I scripts/replay/lock_flow.py SCENE_DIR FCD [--edges E1,E2] [--bin 90]
SCENE_DIR holds matched.csv.gz and routes_mix.xml; FCD is a mix run's output (1 s). Counts cars, taxis, medium and
heavy vehicles leaving each edge (their next sample on another non-internal edge); the recording counts every one of
them, the simulation only the simulated ones (replayed ones of these classes are few: their later pieces).
"""
import os, sys, json
import numpy as np, pandas as pd

SIM_TYPES = {0, 1, 3, 4}


def leaves(df, t, veh, edge):
    o = np.lexsort((t, veh))
    t, veh, edge = t[o], veh[o], edge[o]
    k = np.flatnonzero((veh[1:] == veh[:-1]) & (edge[1:] != edge[:-1]))
    return pd.DataFrame(dict(edge=edge[k], to=edge[k + 1], t=t[k + 1]))


def main():
    D, fcd = sys.argv[1], sys.argv[2]
    b = float(next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--bin'), 90))
    names = json.load(open(f'{D}/names.json'))
    meta = json.load(open(f'{D}/scene.json'))
    m = pd.read_csv(f'{D}/matched.csv.gz', usecols=['vid', 'ti', 'type', 'lane', 'internal'])
    m = m[m.type.isin(SIM_TYPES) & ~m.internal.astype(bool)]
    m['edge'] = m.lane.str.rsplit('_', n=1).str[0]
    R = leaves(m, m.ti.values * 0.2, m.vid.values, m.edge.values)
    import xml.etree.ElementTree as ET
    sims = {v.get('id') for v in ET.parse(f'{D}/routes_mix.xml').getroot().iter('vehicle') if v.get('type') == 'drv'}
    f = pd.read_csv(fcd, usecols=['time', 'trip', 'lane'])
    f = f[f.trip.isin(sims) & ~f.lane.str.startswith(':')]
    f['edge'] = f.lane.str.rsplit('_', n=1).str[0]
    S = leaves(f, f.time.values, f.trip.values, f.edge.values)
    t0 = meta['begin']
    edges = next((sys.argv[i + 1].split(',') for i, a in enumerate(sys.argv) if a == '--edges'), None)
    if edges is None:
        edges = R.edge.value_counts().index[:24].tolist()
    nb = int(np.ceil((meta['end'] - t0) / b))
    print(f'cars leaving each edge per {b:.0f} s, recording / simulation')
    for e in edges:
        r = np.bincount(((R.t[R.edge == e] - t0) // b).astype(int).clip(0, nb - 1), minlength=nb)
        s = np.bincount(((S.t[S.edge == e] - t0) // b).astype(int).clip(0, nb - 1), minlength=nb)
        print(f'{e:15s} {names.get(e, "")[:12]:12s} {r.sum():4d}/{s.sum():4d}  ' + ' '.join(f'{x:2d}/{y:<2d}' for x, y in zip(r, s)))


if __name__ == '__main__':
    main()
