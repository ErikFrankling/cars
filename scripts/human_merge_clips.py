#!/usr/bin/env python3
"""Merging clips of report 18, into the gallery. Everything goes through `cars replay`: real tracks, simulated cars.

    python3 scripts/human_merge_clips.py --out DIR [--gallery DIR]

1. i80_real_vs_sim: real I-80 tracks above, the simulated driver below, same road and camera. The real data has no
   blinkers. It also has no lane line there (report 18), so the line drawn is the scene's.
2. motorway_two_into_one: two loaded lanes into one at motorway speed.
3. lane_drop_closeup: the end of a lane at a crawl, close up.
Stills beside each clip, for looking at.
"""
import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

import human_merge as hm

MG = os.environ.get('MG_DATA', '/home/erikf/projects/personal/cars-data/truth/merging-20261102')
GALLERY = '/home/erikf/projects/personal/cars-data/videos/gallery/humans'
HERE = Path(__file__).resolve().parent
DROP = dict(zone=400, up=1500, main=1000, ramp=900, v=30, von=30, neck=30, dev=0.15)


def centre(net, lane, at=0.5):
    m = re.search(rf'<lane id="{lane}"[^>]*?shape="([^"]+)"', Path(net).read_text())
    pts = [tuple(map(float, p.split(','))) for p in m.group(1).split()]
    a, b = pts[0], pts[-1]
    return f'{a[0] + (b[0] - a[0]) * at:.1f},{a[1] + (b[1] - a[1]) * at:.1f}'


def scene(d, sc, begin, end):
    d.mkdir(parents=True, exist_ok=True)
    hm.build(d, sc)
    hm.routes(d, sc, end)
    hm.run([hm.BIN, 'run', '--net', d / 'net.xml', '--routes', d / 'r.xml', '--dt', 0.1, '--end', end, '--seed', 1, '--report-json', d / 's.json', '--trace', d / 'sim.trace', '--trace-begin', begin, '--trace-end', end, '--time-to-teleport', 0])
    shutil.copy(d / 'net.xml', d / 'sim.net.xml')


def replay(net, trace, out, c, mpp, w, h, begin, end, title, speed=1.0):
    hm.run([hm.BIN, 'replay', '--net', net, '--trace', trace, '--center', c, '--metres-per-pixel', mpp, '--width', w, '--height', h, '--begin', begin, '--end', end, '--speed', speed, '--fps', 25, '--title', title, '--out', out])


def still(net, trace, out, c, mpp, w, h, at):
    hm.run([hm.BIN, 'replay', '--net', net, '--trace', trace, '--center', c, '--metres-per-pixel', mpp, '--width', w, '--height', h, '--at', at, '--out', out])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='/tmp/human-merge-clips')
    p.add_argument('--gallery', default=GALLERY)
    p.add_argument('what', nargs='*', default=['i80', 'drop', 'close'])
    a = p.parse_args()
    out = Path(a.out)
    gal = Path(a.gallery)
    gal.mkdir(parents=True, exist_ok=True)
    if 'i80' in a.what or 'close' in a.what:
        d = out / 'i80'
        scene(d, hm.SCENES['i80'], 300, 500)
        net = d / 'net.xml'
        c = centre(net, 'merge_1')
    if 'i80' in a.what:
        hm.run(['python3', HERE / 'real_tracks_trace.py', '--cache', f'{MG}/cache/i-80', '--template', d / 'sim.trace', '--run', 0, '--begin', 70, '--end', 170, '--end-s', 204, '--old', 7, '--new', 6, '--out', d / 'real.trace'])
        replay(net, d / 'real.trace', d / 'real.mp4', c, 0.14, 1400, 330, 70, 150, 'Real I-80, lanes 6 and 7 (no blinkers in the data)')
        replay(net, d / 'sim.trace', d / 'sim.mp4', c, 0.14, 1400, 330, 350, 430, 'Simulated human driver')
        hm.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', d / 'real.mp4', '-i', d / 'sim.mp4', '-filter_complex', 'vstack=inputs=2:shortest=1', '-c:v', 'libx264', '-crf', 20, '-pix_fmt', 'yuv420p', gal / 'merge_i80_real_vs_sim.mp4'])
        for t in (90, 110, 130):
            still(net, d / 'real.trace', gal / f'merge_i80_real_{t}.png', c, 0.14, 1400, 330, t)
        for t in (370, 390, 410):
            still(net, d / 'sim.trace', gal / f'merge_i80_sim_{t}.png', c, 0.14, 1400, 330, t)
    if 'close' in a.what:
        ce = centre(net, 'merge_1', 0.75)
        replay(net, d / 'sim.trace', gal / 'merge_lane_drop_closeup.mp4', ce, 0.05, 1200, 500, 350, 410, 'Lane end, close up. Blinkers, brake lights, a car edging in', speed=0.5)
        for t in (360, 375, 390):
            still(net, d / 'sim.trace', gal / f'merge_lane_drop_{t}.png', ce, 0.05, 1200, 500, t)
    if 'drop' in a.what:
        d = out / 'drop'
        scene(d, DROP, 200, 330)
        net = d / 'net.xml'
        ce = centre(net, 'merge_1', 0.65)
        replay(net, d / 'sim.trace', gal / 'merge_motorway_two_into_one.mp4', ce, 0.22, 1500, 300, 220, 300, 'Two lanes into one, 108 km/h limit')
        for t in (240, 260, 280):
            still(net, d / 'sim.trace', gal / f'merge_motorway_{t}.png', ce, 0.22, 1500, 300, t)
    print('done')


if __name__ == '__main__':
    main()
