#!/usr/bin/env python3
"""Real tracks as a `cars replay` trace, so real and simulated cars go through the same renderer on the same road.

    python3 scripts/real_tracks_trace.py --cache DIR/i-80 --template sim.trace --run 0 --begin 60 --end 200 --end-s 204 \
        --old 7 --new 6 --out real.trace

The template is a short trace of the scene, for its header and lane numbers. Only the merging lane and the lane it joins
are drawn. Road position is kept to the metre, aligned on the lane end, and sideways position is scaled to the scene's lane
width, so the lane's narrowing at the real site shows as a car moving over. Heading is worked out by `cars replay` from
the sideways motion. The data has no blinkers, so none are drawn.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cars_trace

NO_LINK = 63


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cache', required=True, help='path without extension, of NAME.npz and NAME.centres.csv.gz')
    p.add_argument('--template', required=True)
    p.add_argument('--run', type=int, default=0)
    p.add_argument('--begin', type=float, required=True, help='seconds from the start of the run')
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--end-s', type=float, required=True, help='road position of the lane end at the site')
    p.add_argument('--old', type=int, required=True)
    p.add_argument('--new', type=int, required=True)
    p.add_argument('--fps', type=float, default=5.0)
    p.add_argument('--width', type=float, default=3.2)
    p.add_argument('--smooth', type=int, default=5, help='frames of the running mean of position, both ways. The tracks shake by more than a car moves in a frame')
    p.add_argument('--alongside', type=float, default=200.0, help='metres before the zone where the scene has the lanes side by side')
    p.add_argument('--out', required=True)
    a = p.parse_args()

    z = np.load(a.cache + '.npz')
    hz = int(z['hz'])
    keep = (z['run'] == a.run) & np.isin(z['lane'], [a.old, a.new])
    t0 = z['t'][z['run'] == a.run].min()
    d = pd.DataFrame({k: z[k][keep] for k in ('t', 'id', 'lane', 's', 'v', 'a', 'lat')})
    d['time'] = (d['t'] - t0) / hz
    d = d[d.time.between(a.begin, a.end)]
    step = max(1, int(round(hz / a.fps)))
    d = d[(d['t'] - t0) % step == 0].sort_values(['id', 't'])
    # An id can come back later, on a lane not drawn in between. Each unbroken stretch is one car.
    d['id'] = d['id'].astype('i8') * 1000 + (d.groupby('id')['t'].diff() != step).groupby(d['id']).cumsum()

    cen = pd.read_csv(a.cache + '.centres.csv.gz')
    cen = cen[cen.r == a.run]

    def centre(lane, s):
        g = cen[cen.l == lane].sort_values('b')
        return np.interp(s, g.b.values * 20.0 + 10.0, g['median'].values)

    tmpl = cars_trace.Trace(a.template)
    index = {v: k for k, v in tmpl.lanes.items()}
    head = dict(tmpl.header)
    length = dict(pd.DataFrame(tmpl.table(tmpl.frames[0]['time'], tmpl.frames[-1]['time'])).groupby('lane').pos.max())
    net = {}
    import re
    text = Path(a.template.replace('.trace', '.net.xml')).read_text()
    for m in re.finditer(r'<lane id="([\w:]+)"[^>]*?length="([\d.]+)"', text):
        net[m.group(1)] = float(m.group(2))
    L = net['merge_1']

    # Everything in one road coordinate, and sideways in lanes from the lane that ends, so there is no lane to jump between:
    # upstream of the zone the scene's lanes run alongside, and a car on the ending lane is drawn offset on the through lane.
    d['s'] = d.groupby('id')['s'].transform(lambda v: v.rolling(a.smooth, center=True, min_periods=1).mean())
    s_m = d.s.values - a.end_s + L
    q = (d.lat.values - centre(a.old, d.s.values)) / (centre(a.new, d.s.values) - centre(a.old, d.s.values))
    d['q'] = np.clip(q, -0.4, 1.4)
    d['q'] = d.groupby('id')['q'].transform(lambda v: v.rolling(a.smooth, center=True, min_periods=1).mean())
    off = (d.q.values - 1.0) * a.width
    keep = s_m >= -a.alongside
    d, s_m, off = d[keep], s_m[keep], off[keep]
    order = [('up_0', -net['up_0'], 0.0), ('merge_1', 0.0, L), ('down_0', L, L + net['down_0']), ('neck_0', L + net['down_0'], L + net['down_0'] + net['neck_0']), ('out_0', L + net['down_0'] + net['neck_0'], 1e9)]
    lanes = np.empty(len(d), object)
    pos = np.zeros(len(d))
    for lane, start, stop in order:
        m = (s_m >= start) & (s_m < stop)
        lanes[m] = lane
        pos[m] = s_m[m] - start

    dt = step / hz
    head.update(dt=dt, sim_begin=float(d.time.min()), begin=float(d.time.min()), end=float(d.time.max()), stride=1)
    data = json.dumps(head).encode()
    data += b' ' * (-(len(data) + 12) % 8)
    ids = {v: i for i, v in enumerate(pd.unique(d.id))}
    n_tls = len(head['tls'])
    phase_bytes = (n_tls * 2 + 3) // 4 * 4
    seen_lanes, seen_trips = set(), set()

    def name(key, s):
        b = s.encode()
        return struct.pack('<II', key, len(b)) + b + b'\0' * (-len(b) % 4)

    with open(a.out, 'wb') as out:
        out.write(cars_trace.MAGIC + struct.pack('<I', len(data)) + data)
        times = sorted(d.time.unique())
        frame_index = np.searchsorted(times, d.time.values)
        for k, tm in enumerate(times):
            m = frame_index == k
            names = b''
            rec = np.zeros(int(m.sum()), cars_trace.RECORD)
            for j, i in enumerate(np.where(m)[0]):
                lane = lanes[i]
                li = index[lane]
                tid = ids[d.id.values[i]]
                if li not in seen_lanes:
                    seen_lanes.add(li)
                    names += name(cars_trace.NAME_LANE | li, lane)
                if tid not in seen_trips:
                    seen_trips.add(tid)
                    names += name(tid, f'real{d.id.values[i]}')
                rec[j] = (tid, li, cars_trace.NONE_LANE, int(round(pos[i] * 256)) | NO_LINK << 24, int(np.clip(d.a.values[i] * 256, -32768, 32767)), int(np.clip(d.v.values[i] * 512, 0, 65535)), int(np.clip(off[i] * 256, -32768, 32767)), 0)
            out.write(struct.pack('<4s6If', cars_trace.FRAME, k + 1, len(rec), len(names), 0, 0, len(rec), float(d.v.values[m].mean())))
            out.write(names)
            out.write(b'\0' * phase_bytes)
            out.write(rec.tobytes())
    print('frames', len(times), 'cars', len(ids), 'from', float(d.time.min()), 'to', float(d.time.max()))


if __name__ == '__main__':
    main()
