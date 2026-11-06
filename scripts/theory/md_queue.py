"""The measured driver's queue discharge from its own equations (platoon twin, md_platoon.py), scored with the same
definitions as scripts/measure/queues.py: start delay at 1 m/s, follower peak acceleration in 10 s, bumper gap when the
follower passes 5 and 8 m/s, headway at the line 1 m past the head's standing front. Read against queues.json (F617).

    python3 -I scripts/theory/md_queue.py [--tune k=v ...]
"""
import sys, json, math
import numpy as np
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_platoon as MP


def run(seeds=20, n=12, kmh=50, dt=0.25):
    rows = []
    for s in range(seeds):
        T, X, V = MP.platoon(MP.queue(n, 1.0), np.zeros(n), kmh / 3.6, 60.0, dt=dt, green=0.0, seed=s, line=0.0)
        A = np.gradient(V, dt, axis=0)
        go = np.array([np.interp(1.0, V[:, i], T) if V[:, i].max() >= 1 and (np.diff(V[:np.argmax(V[:, i] >= 1) + 1, i]) >= 0).all()
                       else T[np.argmax(V[:, i] >= 1.0)] for i in range(n)])
        line = X[0, 0] + 1.0
        cr = MP.crossings(T, X, line)
        for i in range(1, n):
            k0 = np.argmax(V[:, i] >= 1.0)
            gap = X[:, i - 1] - MP.L - X[:, i]
            g5 = gap[np.argmax(V[:, i] >= 5)] if (V[:, i] >= 5).any() else np.nan
            g8 = gap[np.argmax(V[:, i] >= 8)] if (V[:, i] >= 8).any() else np.nan
            rows.append(dict(seed=s, pos=i + 1, delay=go[i] - go[i - 1], peak=A[k0:k0 + int(10 / dt), i].max(), g5=g5, g8=g8, hw=cr[i] - cr[i - 1]))
    import pandas as pd
    d = pd.DataFrame(rows)
    out = dict(start_delay=round(float(d.delay.median()), 2), start_delay_by_pos={int(p): round(float(g.delay.median()), 2) for p, g in d.groupby('pos')},
               peak_acc=round(float(d.peak.median()), 2), gap_5=round(float(d.g5.median()), 2), gap_8=round(float(d.g8.median()), 2),
               headway_by_pos={int(p): round(float(g.hw.median()), 2) for p, g in d.groupby('pos')})
    return out


if __name__ == '__main__':
    for a in sys.argv[1:]:
        k, v = a.split('=')
        setattr(MP, k, float(v))
    print(json.dumps(run(), indent=1))
