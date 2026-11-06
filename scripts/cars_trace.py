#!/usr/bin/env python3
"""Reads files from `cars run --trace`. Layout in crates/cars-cli/RECORDING.md.

    python3 scripts/cars_trace.py info f.trace
    python3 scripts/cars_trace.py events f.trace --net n.xml
    python3 scripts/cars_trace.py signals f.trace --tls 123
"""
import argparse
import json
import struct

import numpy as np
import pandas as pd

MAGIC = b'CARSTRC2'
FRAME = b'TRFR'
NAME_LANE = 1 << 31
NONE_LANE = 0xffffff
LANE_CHANGED, TELEPORT, COLLISION, WILL_PASS, HAVE_TO_WAIT, WANT_LEFT, WANT_RIGHT, ON_JUNCTION = (1 << i for i in range(8))
RECORD = np.dtype([('trip_flags', '<u4'), ('lane_type', '<u4'), ('prev_wait', '<u4'), ('pos_link', '<u4'), ('acc', '<i2'), ('speed', '<u2'), ('lat', '<i2'), ('pad', '<u2')])


class Trace:
    """Headers and names are read at once, records only when asked for."""

    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        if self.f.read(8) != MAGIC:
            raise SystemExit(f'{path}: not a cars trace')
        size = struct.unpack('<I', self.f.read(4))[0]
        self.header = json.loads(self.f.read(size).rstrip(b' '))
        self.trips, self.lanes, self.frames = {}, {}, []
        n_tls = len(self.header['tls'])
        phase_bytes = (n_tls * 2 + 3) // 4 * 4
        while True:
            head = self.f.read(32)
            if len(head) < 32:
                break
            magic, step, records, names, teleports, collisions, running, speed = struct.unpack('<4s6If', head)
            if magic != FRAME:
                raise SystemExit(f'{path}: damaged frame')
            data = self.f.read(names)
            at = self.f.tell()
            body = phase_bytes + records * RECORD.itemsize
            self.f.seek(0, 2)
            if self.f.tell() < at + body or len(data) < names:
                break  # cut short while writing
            self.f.seek(at + body)
            p = 0
            while p + 8 <= names:
                key, length = struct.unpack_from('<II', data, p)
                text = data[p + 8:p + 8 + length].decode()
                if key & NAME_LANE:
                    self.lanes[key ^ NAME_LANE] = text
                else:
                    self.trips[key] = text
                p = (p + 8 + length + 3) // 4 * 4
            self.frames.append(dict(step=step, time=self.time_of(step), records=records, teleports=teleports, collisions=collisions, running=running, mean_speed=speed, at=at))

    def time_of(self, step):
        return round(self.header['sim_begin'] + (step - 1) * self.header['dt'], 4)

    def selected(self, begin=None, end=None):
        return [f for f in self.frames if (begin is None or f['time'] >= begin) and (end is None or f['time'] <= end)]

    def records(self, frame):
        n_tls = len(self.header['tls'])
        self.f.seek(frame['at'] + (n_tls * 2 + 3) // 4 * 4)
        return np.fromfile(self.f, RECORD, frame['records'])

    def phases(self, frame):
        self.f.seek(frame['at'])
        return np.fromfile(self.f, '<u2', len(self.header['tls']))

    def table(self, begin=None, end=None):
        """One row per record, with names and SI units, in the columns physics_qa knows from FCD."""
        frames = self.selected(begin, end)
        if not frames:
            return pd.DataFrame()
        rec = np.concatenate([self.records(f) for f in frames])
        times = np.repeat([f['time'] for f in frames], [f['records'] for f in frames])
        lane = rec['lane_type'] & 0xffffff
        prev = rec['prev_wait'] & 0xffffff
        vtype = rec['lane_type'] >> 24
        vtypes = self.header['vtypes']
        trip = rec['trip_flags'] & 0xffffff
        lane_names = _lookup(self.lanes, lane)
        return pd.DataFrame({
            'time': times,
            'trip': _lookup(self.trips, trip),
            'lane': lane_names,
            'pos': (rec['pos_link'] & 0xffffff) / 256.0,
            'speed': rec['speed'] / 512.0,
            'acc': rec['acc'] / 256.0,
            'wait': (rec['prev_wait'] >> 24).astype(float),
            'flags': rec['trip_flags'] >> 24,
            'length': np.array([t['length'] for t in vtypes], dtype=float)[vtype] if len(vtypes) else 0.0,
            'width': np.array([t['width'] for t in vtypes], dtype=float)[vtype] if len(vtypes) else 0.0,
            'prev_lane': _lookup(self.lanes, prev, missing=NONE_LANE),
            'depart_step': 0,
        })

    def events(self, begin=None, end=None):
        """Teleports and collisions in the frames kept, where the vehicle was just before."""
        rows = []
        for f in self.selected(begin, end):
            rec = self.records(f)
            flags = rec['trip_flags'] >> 24
            for r in rec[(flags & (TELEPORT | COLLISION)) != 0]:
                rows.append(dict(time=f['time'], kind='collision' if (r['trip_flags'] >> 24) & COLLISION else 'teleport',
                                 trip=self.trips.get(int(r['trip_flags'] & 0xffffff), ''), lane=self.lanes.get(int(r['lane_type'] & 0xffffff), ''),
                                 pos=(r['pos_link'] & 0xffffff) / 256.0, wait=float(r['prev_wait'] >> 24)))
        return pd.DataFrame(rows, columns=['time', 'kind', 'trip', 'lane', 'pos', 'wait'])

    def signals(self, tls=None):
        """Every change of phase, with its state string."""
        rows, last = [], {}
        for f in self.frames:
            for t, p in zip(self.header['tls'], self.phases(f)):
                if (tls is None or t['id'] == tls) and last.get(t['id']) != p:
                    last[t['id']] = p
                    rows.append(dict(time=f['time'], tls=t['id'], phase=int(p), state=t['phases'][p] if p < len(t['phases']) else ''))
        return pd.DataFrame(rows, columns=['time', 'tls', 'phase', 'state'])


def _lookup(names, indices, missing=None):
    """Names by index without a Python call per row."""
    top = int(indices.max()) if len(indices) else 0
    table = np.empty(top + 1, dtype=object)
    table[:] = ''
    for k, v in names.items():
        if k <= top:
            table[k] = v
    if missing is not None and missing <= top:
        table[missing] = ''
    return table[indices]


def lane_points(net, lanes, positions):
    """x, y of positions on lanes, reading only the wanted lanes from the net."""
    from lxml import etree
    wanted, shapes = set(lanes), {}
    with open(net, 'rb') as f:
        for _, e in etree.iterparse(f, events=('end',), tag='lane'):
            if e.get('id') in wanted:
                p = np.array([[float(v) for v in q.split(',')[:2]] for q in e.get('shape').split()])
                s = np.concatenate(([0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))))
                shapes[e.get('id')] = (p, s, float(e.get('length')))
            e.clear()
    out = []
    for lane, pos in zip(lanes, positions):
        p, s, length = shapes[lane]
        d = min(max(pos / max(length, 1e-3), 0.0), 1.0) * s[-1]
        out.append((float(np.interp(d, s, p[:, 0])), float(np.interp(d, s, p[:, 1]))))
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('what', choices=['info', 'events', 'signals'])
    a.add_argument('trace')
    a.add_argument('--net', help='also give x and y of events')
    a.add_argument('--tls')
    a.add_argument('--begin', type=float)
    a.add_argument('--end', type=float)
    a = a.parse_args()
    t = Trace(a.trace)
    if a.what == 'info':
        h = {k: v for k, v in t.header.items() if k not in ('vtypes', 'tls')}
        first, last = (t.frames[0], t.frames[-1]) if t.frames else (None, None)
        print(json.dumps(dict(h, vtypes=len(t.header['vtypes']), tls=len(t.header['tls']), frames=len(t.frames), records=sum(f['records'] for f in t.frames), trips=len(t.trips), lanes=len(t.lanes),
                              time=[first['time'], last['time']] if first else [],
                              teleports=last['teleports'] - first['teleports'] if first else 0, collisions=last['collisions'] - first['collisions'] if first else 0), indent=1))
    elif a.what == 'events':
        e = t.events(a.begin, a.end)
        if a.net and len(e):
            e[['x', 'y']] = lane_points(a.net, list(e['lane']), list(e['pos']))
        print(e.to_csv(index=False, float_format='%.2f'), end='')
    else:
        print(t.signals(a.tls).to_csv(index=False), end='')


if __name__ == '__main__':
    main()
