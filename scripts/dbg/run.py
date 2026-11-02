"""A traced run as the debugging tools read it: trace, `.why` sidecar and net, frame by frame."""
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cars_trace import COLLISION, HAVE_TO_WAIT, LANE_CHANGED, NONE_LANE, ON_JUNCTION, RECORD, TELEPORT, Trace, WANT_LEFT, WANT_RIGHT, WILL_PASS  # noqa: E402,F401

WHY = np.dtype([
    ('decider', 'u1'), ('plan', 'u1'), ('item', 'u1'), ('closed', 'u1'), ('blame', '<u4'), ('blame_gap', '<f4'), ('v_safe', '<f4'),
    ('leader', '<u4'), ('leader_gap', '<f4'), ('leader_speed', '<f4'), ('first_link', '<u4'), ('first_dist', '<f4'),
    ('foe_trip', '<u4'), ('foe_link', '<u4'), ('foe_gap', '<f4'), ('lc_right', '<u4'), ('lc_left', '<u4'), ('lc_chosen', '<i4'),
    ('right_gap', '<f4'), ('right_follow_gap', '<f4'), ('left_gap', '<f4'), ('left_follow_gap', '<f4'),
    ('right_leader', '<u4'), ('right_follower', '<u4'), ('left_leader', '<u4'), ('left_follower', '<u4'), ('limits', '<u2', 22)])
KINDS = ['none', 'accel', 'free', 'next_limit', 'curve', 'leader', 'leader_ahead', 'tail', 'signal', 'yield', 'exit_full', 'junction', 'lane_end', 'arrival',
         'lane_change', 'zipper', 'dawdle', 'brake_limit', 'power', 'committed', 'coordinator']
K = {n: i for i, n in enumerate(KINDS)}
PLAIN = {
    'none': 'no plan this step', 'accel': 'acceleration limit', 'free': 'free speed on this lane', 'next_limit': 'lower limit on the next road', 'curve': 'junction lane speed (curve)',
    'leader': 'leader on this lane', 'leader_ahead': 'leader on a lane ahead', 'tail': 'tail of a car still hanging on a lane ahead', 'signal': 'signal (red or yellow)',
    'yield': 'stopping for a link it may not take yet', 'exit_full': 'no room past the junction', 'junction': 'car inside the junction', 'lane_end': 'end of lane, route needs another lane',
    'arrival': 'arriving at its destination', 'lane_change': 'lane change speed request', 'zipper': 'zipper merge', 'dawdle': 'driver imperfection (dawdle)',
    'brake_limit': 'brake limit: wanted to slow more', 'power': 'engine or power limit', 'committed': 'committed past the point of stopping', 'coordinator': 'junction coordinator',
}
CLOSED = ['', 'red', 'stop_sign', 'foe']
NONE32 = 0xffffffff
BLAME_LANE = 0x80000000
BLAME_LINK = 0x40000000
LCA = [(1, 'left'), (2, 'right'), (4, 'strategic'), (8, 'cooperative'), (16, 'speed_gain'), (32, 'keep_right'), (64, 'urgent'), (128, 'blocked_by_leader'), (256, 'blocked_by_follower'),
       (512, 'am_leader'), (1024, 'am_follower'), (8192, 'stay')]
HALT = 0.1


def lc_words(state):
    return [n for b, n in LCA if int(state) & b]


class Net:
    """Column arrays from `cars netinfo` or `<trace>.net.json`."""

    def __init__(self, path):
        with open(path) as f:
            d = json.load(f)
        self.lane_ids = d['lanes']['id']
        self.lane_by_id = {x: i for i, x in enumerate(self.lane_ids)}
        for k, v in d['lanes'].items():
            if k != 'id':
                setattr(self, 'lane_' + k, np.array(v))
        self.edge_ids = d['edges']['id']
        self.edge_index = {x: i for i, x in enumerate(self.edge_ids)}
        self.edge_func, self.edge_from, self.edge_to, self.edge_road = d['edges']['func'], d['edges']['from'], d['edges']['to'], d['edges']['road']
        self.edge_first = np.array(d['edges']['first_lane'])
        self.edge_lanes = np.array(d['edges']['lane_count'])
        for k, v in d['links'].items():
            setattr(self, 'link_' + k, np.array(v))
        self.junction_ids = d['junctions']['id']
        self.junction_type = dict(zip(d['junctions']['id'], d['junctions']['jtype']))
        self.junction_xy = {j: (x, y) for j, x, y in zip(d['junctions']['id'], d['junctions']['x'], d['junctions']['y'])}
        self.tls = d['tls']
        self.n_lanes = len(self.lane_ids)
        self._before = None

    def lanes_before(self, lane):
        """Lanes with a link straight onto this one."""
        if self._before is None:
            order = np.argsort(self.link_next_lane, kind='stable')
            self._before = (self.link_next_lane[order], self.link_from_lane[order])
        nexts, froms = self._before
        return froms[np.searchsorted(nexts, lane):np.searchsorted(nexts, lane, side='right')].tolist()

    def lane_name(self, lane):
        lane = int(lane)
        return self.lane_ids[lane] if 0 <= lane < self.n_lanes else f'#{lane}'

    def lane_xy(self, lane, pos):
        lane = int(lane)
        if not 0 <= lane < self.n_lanes:
            return (0.0, 0.0)
        t = min(max(float(pos) / max(float(self.lane_length[lane]), 1e-3), 0.0), 1.0)
        return (float(self.lane_x0[lane] + t * (self.lane_x1[lane] - self.lane_x0[lane])), float(self.lane_y0[lane] + t * (self.lane_y1[lane] - self.lane_y0[lane])))

    def junction_of_lane(self, lane):
        """The junction a lane leads to, or lies in."""
        lane = int(lane)
        e = int(self.lane_edge[lane])
        name = self.edge_ids[e]
        if name.startswith(':'):
            return name[1:].rsplit('_', 1)[0]
        return self.edge_to[e]

    def link_name(self, link):
        k = int(link)
        return f'{self.lane_name(self.link_from_lane[k])} -> {self.lane_name(self.link_to_lane[k])}'

    def lanes_of_edge(self, edge):
        e = self.edge_index[edge]
        return list(range(int(self.edge_first[e]), int(self.edge_first[e] + self.edge_lanes[e])))


def ensure_net(trace_path, net_arg=None, cars='cars'):
    side = f'{trace_path}.net.json'
    if os.path.exists(side):
        return side
    if net_arg is None:
        raise SystemExit(f'{side} is missing. Give --net, or trace with `cars run --why`.')
    if net_arg.endswith('.json'):
        return net_arg
    subprocess.run([os.environ.get('CARS_BIN', cars), 'netinfo', '--net', net_arg, '--out', side], check=True)
    return side


class Run:
    def __init__(self, trace_path, net=None):
        self.path = trace_path
        self.trace = Trace(trace_path)
        self.frames = self.trace.frames
        self.times = np.array([f['time'] for f in self.frames])
        self.dt = float(self.trace.header['dt']) * int(self.trace.header.get('stride', 1))
        self.trip_id = {v: k for k, v in self.trace.trips.items()}
        self.has_why = os.path.exists(trace_path + '.why')
        self.why_at = []
        if self.has_why:
            self.why_f = open(trace_path + '.why', 'rb')
            if self.why_f.read(8) != b'CARSWHY1':
                raise SystemExit(f'{trace_path}.why: not a why file')
            size = struct.unpack('<I', self.why_f.read(4))[0]
            head = json.loads(self.why_f.read(size).rstrip(b' '))
            if head['record'] != WHY.itemsize:
                raise SystemExit(f'{trace_path}.why: records of {head["record"]} bytes, this tool reads {WHY.itemsize}')
            at = self.why_f.tell()
            total = os.fstat(self.why_f.fileno()).st_size
            while at + 16 <= total:
                self.why_f.seek(at)
                magic, step, n, _ = struct.unpack('<4sIII', self.why_f.read(16))
                if magic != b'WHYF':
                    raise SystemExit(f'{trace_path}.why: damaged frame at byte {at}')
                if at + 16 + n * WHY.itemsize > total:
                    break
                self.why_at.append((at + 16, n))
                at += 16 + n * WHY.itemsize
            self.has_why = len(self.why_at) > 0
        self._net_arg = net
        self._net = None

    @property
    def net(self):
        if self._net is None:
            self._net = Net(ensure_net(self.path, self._net_arg))
        return self._net

    def name(self, trip):
        return self.trace.trips.get(int(trip), f'#{int(trip)}')

    def trip(self, name):
        if name in self.trip_id:
            return self.trip_id[name]
        raise SystemExit(f'car {name} is not in this trace. Trips look like: {", ".join(list(self.trip_id)[:5])}')

    def frame_at(self, t):
        i = int(np.searchsorted(self.times, t))
        if i >= len(self.times):
            i = len(self.times) - 1
        if i > 0 and abs(self.times[i - 1] - t) <= abs(self.times[i] - t):
            i -= 1
        return i

    def window(self, begin=None, end=None):
        a = 0 if begin is None else int(np.searchsorted(self.times, begin))
        b = len(self.times) if end is None else int(np.searchsorted(self.times, end, side='right'))
        return range(a, b)

    def read(self, i):
        """One frame's records, and its reasons when the run has them."""
        rec = self.trace.records(self.frames[i])
        why = None
        if self.has_why and i < len(self.why_at):
            at, n = self.why_at[i]
            self.why_f.seek(at)
            why = np.fromfile(self.why_f, WHY, n)
        return rec, why

    def phases(self, i):
        return self.trace.phases(self.frames[i])


def trips_of(rec):
    return rec['trip_flags'] & 0xffffff


def flags_of(rec):
    return rec['trip_flags'] >> 24


def lanes_of(rec):
    return rec['lane_type'] & 0xffffff


def vtypes_of(rec):
    return rec['lane_type'] >> 24


def prevs_of(rec):
    return rec['prev_wait'] & 0xffffff


def waits_of(rec):
    return (rec['prev_wait'] >> 24).astype(float)


def pos_of(rec):
    return (rec['pos_link'] & 0xffffff) / 256.0


def speeds_of(rec):
    return rec['speed'] / 512.0


def accs_of(rec):
    return rec['acc'] / 256.0


def limit_value(raw):
    return None if raw == 0xffff else raw / 128.0


def blame_text(run, b):
    b = int(b)
    if b == NONE32:
        return ''
    if b & BLAME_LANE:
        return 'lane ' + run.net.lane_name(b & 0x7fffffff)
    if b & BLAME_LINK:
        return 'link ' + run.net.link_name(b & 0x3fffffff)
    return 'car ' + run.name(b)


def link_state(run, i, link):
    """The letter a link shows in frame i: the signal's phase, or its fixed right of way."""
    net = run.net
    k = int(link)
    if k >= len(net.link_tl):
        return '?'
    tl = int(net.link_tl[k])
    if tl != NONE32:
        for slot, t in enumerate(run.trace.header['tls']):
            if t['index'] == tl:
                p = int(run.phases(i)[slot])
                s = t['phases'][p] if p < len(t['phases']) else ''
                idx = int(net.link_tl_index[k])
                return s[idx] if idx < len(s) else '?'
        return '?'
    return chr(int(net.link_state[k]) & 0xff)
