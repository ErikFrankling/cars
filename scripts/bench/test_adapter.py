#!/usr/bin/env python3
"""The trace adapter gives the same tracks as trajectories, and a run measured through it matches known geometry. Uses llvmpipe."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('JT_OUT', tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd

import runner
import scenes
from metrics import trackio as T


def check(driver):
    cfg = runner.load_config(driver)
    d = Path(tempfile.mkdtemp())
    plan = scenes.free3(d, cfg, {}, True, 1)
    env = dict(os.environ, CARS_ADAPTER='llvmpipe', LP_NUM_THREADS='2')
    cmd = [cfg['binary'], 'run', '--net', d / 'net.xml', '--routes', plan['routes'], '--dt', '0.5', '--end', '120', '--time-to-teleport', '0', '--fcd', d / 'f.csv', '--fcd-interval', '0.5', '--trace', d / 't.trace', *cfg['flags']]
    subprocess.run(list(map(str, cmd)), check=True, capture_output=True, env=env)
    r = runner.Run(d, dict(end=120, fcd=.5), '', 0, cmd)
    r.fcd = d / 'f.csv'
    a = T.tracks(r.table(), d / 'net.xml')
    b = T.from_trace(d / 't.trace', d / 'net.xml')
    assert len(a) and abs(len(a) - len(b)) <= 3, (len(a), len(b))
    n = 0
    for x in a[:40]:
        near = [y for y in b if len(y[2]) and abs(y[2][0] - x[2][0]) < .6 and abs(y[3][0] - x[3][0]) < 3 and abs(y[4][0] - x[4][0]) < 3]
        n += bool(near)
    assert n >= 30, n
    ys = np.concatenate([x[4] for x in a])
    assert ys.max() - ys.min() < 12, 'free3 runs straight along x, three lanes wide'
    print(driver, 'ok:', len(a), 'tracks from trajectories,', len(b), 'from the trace')


if __name__ == '__main__':
    for drv in sys.argv[1:] or ['main']:
        check(drv)
