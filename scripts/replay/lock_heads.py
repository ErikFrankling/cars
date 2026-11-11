"""What holds the standing head of each lane of some edges, per frame, while its next link shows green
(research/truth/replay/LOCK.md). Reads a `cars run --trace --why` trace.

    python3 -I scripts/replay/lock_heads.py TRACE EDGE[,EDGE...] [--end T] [--all-states]
"""
import os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import numpy as np
from dbg.run import Run, KINDS, NONE32, denial, trips_of, lanes_of, pos_of, speeds_of, blame_text, link_state


def kind_of(name):
    return 'rep' if 'm' in name.split('_')[-1] else 'sim'


def main():
    run = Run(sys.argv[1])
    edges = sys.argv[2].split(',')
    end = float(next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--end'), 1e12))
    allst = '--all-states' in sys.argv
    net = run.net
    C, moving = {}, Counter()
    for i in range(len(run.frames)):
        if run.times[i] > end:
            break
        rec, why = run.read(i)
        ln, ps, sp = lanes_of(rec), pos_of(rec), speeds_of(rec)
        for e in edges:
            for l in net.lanes_of_edge(e):
                idx = np.nonzero(ln == l)[0]
                if not len(idx):
                    continue
                h = idx[np.argmax(ps[idx])]
                w = why[h]
                st = link_state(run, i, w['first_link']) if w['first_link'] != NONE32 else '-'
                if not allst and st not in 'GgMm':
                    continue
                if sp[h] > 0.1:
                    moving[net.lane_name(l)] += 1
                    continue
                d = denial(run, w)
                b = d or blame_text(run, w['blame'])
                if b.startswith('car '):
                    b = 'car ' + kind_of(b[4:]) + ' ' + b[4:]
                C.setdefault(net.lane_name(l), Counter())[(KINDS[w['decider']], b[:70])] += 1
    for l in sorted(set(C) | set(moving)):
        c = C.get(l, Counter())
        print(f'{l:22s} green frames: head moving {moving[l]:4d}, standing {sum(c.values()):4d}')
        for (k, b), n in c.most_common(6):
            print(f'      {n:4d}  {k:12s} {b}')


if __name__ == '__main__':
    main()
