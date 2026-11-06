"""TGSIM I-90/94: a replay scene from one run. Net from the provider's lane centrelines, tracks map-matched to
their recorded lane. F100 replays every vehicle and compares the output with the recording.

    python3 -I scripts/replay/tgsim_scene.py build I90mov 1      # writes cars-data/replay/tgsim-I90mov-1/
    python3 -I scripts/replay/tgsim_scene.py f100 I90mov 1       # runs cars on it, all replayed, and scores
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rpl import *

TG = '/home/erikf/projects/personal/cars-data/truth/trajectories/opus-20261031-tgsim'
TGA = TG + '-att'
GEOM = {'I90mov': 'I90mov/I-90-moving-Run_{}-geometry-with-ramps.csv', 'I90stat': 'I90stat/I-90-stationary-Run_{}-geometry-with-ramps.csv'}
EXTEND = 400.0
NL = 6  # lane_kf 1 is leftmost, 6 rightmost: SUMO index 6 - lane_kf


def lane_id(kf):
    return f'E_{NL - int(kf)}'


def centrelines(site, run):
    c = pd.read_csv(os.path.join(TGA, GEOM[site].format(run)))
    P = {i: c[[f'x_{i}', f'y_{i}']].to_numpy(float) for i in range(1, NL + 1)}
    for i, (a, b) in ((1, (2, 3)), (6, (5, 4))):
        m = np.isnan(P[i][:, 0])
        P[i][m] = P[a][m] + (P[a][m] - P[b][m])
    good = ~np.any([np.isnan(P[i][:, 0]) for i in P], axis=0)
    out = {}
    for i in P:
        q = P[i][good]
        # Tracks run past the provider's centrelines: carry each lane on along its end tangents.
        u0 = q[0] - q[min(30, len(q) - 1)]; u1 = q[-1] - q[-min(31, len(q))]
        u0 /= np.linalg.norm(u0); u1 /= np.linalg.norm(u1)
        out[i] = np.vstack([q[0] + EXTEND * u0, q, q[-1] + EXTEND * u1])
    return out


def build(site, run, out=None):
    out = out or os.path.join(OUT, f'tgsim-{site}-{run}')
    os.makedirs(out, exist_ok=True)
    P = centrelines(site, run)
    step = max(1, (len(P[3]) - 2) // 400)
    pts = {i: np.vstack([P[i][:-1][::step], P[i][-1:]]) for i in P}
    mid = (pts[3] + pts[4]) / 2
    with open(f'{out}/plain.nod.xml', 'w') as f:
        f.write(f'<nodes>\n  <node id="A" x="{mid[0,0]:.3f}" y="{mid[0,1]:.3f}"/>\n  <node id="B" x="{mid[-1,0]:.3f}" y="{mid[-1,1]:.3f}"/>\n</nodes>\n')
    with open(f'{out}/plain.edg.xml', 'w') as f:
        f.write(f'<edges>\n  <edge id="E" from="A" to="B" numLanes="{NL}" speed="30" shape="{fmt_shape(mid)}">\n')
        for kf in range(1, NL + 1):
            f.write(f'    <lane index="{NL - kf}" width="3.75" shape="{fmt_shape(pts[kf])}"/>\n')
        f.write('  </edge>\n</edges>\n')
    netconvert(f'{out}/plain', f'{out}/net.xml')
    lanes = lane_shapes(f'{out}/net.xml')
    poly = {lid: Polyline(v['shape'], v['length']) for lid, v in lanes.items()}

    d = pd.read_csv(f'{TG}/{site}.csv', usecols=['ID', 'time', 'xloc_kf', 'yloc_kf', 'lane_kf', 'speed_kf', 'run_index', 'type_most_common', 'av', 'length_smoothed'])
    d = d[d.run_index == run].drop_duplicates(['ID', 'time']).sort_values(['ID', 'time']).reset_index(drop=True)
    d['ti'] = np.round(d.time * 10).astype(int)
    d['lane'] = [lane_id(k) for k in d.lane_kf]
    d['s'] = 0.0; d['lat'] = 0.0
    for lid, g in d.groupby('lane'):
        s, lat = poly[lid].project(g.xloc_kf.values, g.yloc_kf.values)
        d.loc[g.index, 's'] = s; d.loc[g.index, 'lat'] = lat
    # A track is cut where its samples are not 0.1 s apart or it jumps more than one lane; the pieces are fragments.
    li = d.lane_kf.values
    brk = (d.ID.diff() != 0) | (d.ti.diff() != 1) | (np.abs(np.diff(li, prepend=li[0])) > 1)
    d['piece'] = brk.cumsum()
    lane_list = sorted(lanes)
    lidx = {l: k for k, l in enumerate(lane_list)}
    t_begin = float(np.floor(d.time.min()) - 1.0)
    tracks, trips = [], []
    for p, g in d.groupby('piece'):
        if len(g) < 2:
            continue
        large = g.type_most_common.iloc[0] == 'large-vehicle'
        tid = f'{g.ID.iloc[0]}_{p}'
        L = float(np.median(g.length_smoothed)) if large else 5.0
        tracks.append((tid, float(g.ti.iloc[0]) / 10, 0.1, INF, [lidx[l] for l in g.lane], g.s.values, g.speed_kf.values))
        trips.append((float(g.ti.iloc[0]) / 10, tid, int(g.lane.iloc[0].split('_')[1]), float(g.s.iloc[0]), float(g.speed_kf.iloc[0]), L))
    trips.sort()
    lens = sorted({round(t[5], 1) for t in trips})
    with open(f'{out}/routes.xml', 'w') as f:
        f.write('<routes>\n')
        for L in lens:
            f.write(f'  <vType id="rep{L}" length="{L}" lcStrategic="-1" lcCooperative="0" lcSpeedGain="0" lcKeepRight="0"/>\n')
        for t0, tid, ln, s, v, L in trips:
            f.write(f'  <trip id="{tid}" type="rep{round(L,1)}" depart="{t0:.1f}" from="E" to="E" departLane="{ln}" departPos="{s:.3f}" departSpeed="{max(v,0):.3f}"/>\n')
        f.write('</routes>\n')
    write_rpl(f'{out}/all.rpl', lane_list, tracks)
    d[['ID', 'piece', 'ti', 'lane', 's', 'lat', 'xloc_kf', 'yloc_kf', 'speed_kf']].to_csv(f'{out}/matched.csv.gz', index=False)
    meta = dict(site=site, run=run, begin=t_begin, end=float(d.time.max()) + 1.0, rows=len(d), vehicles=int(d.ID.nunique()), tracks=len(tracks),
                fragments_extra=len(tracks) - int(d.ID.nunique()), lanes=lane_list,
                lateral_abs_m=dict(p50=float(np.median(np.abs(d.lat))), p95=float(np.percentile(np.abs(d.lat), 95)), p99=float(np.percentile(np.abs(d.lat), 99))))
    json.dump(meta, open(f'{out}/scene.json', 'w'), indent=1)
    print(json.dumps(meta))
    return out


def f100(site, run, gpu=False):
    out = os.path.join(OUT, f'tgsim-{site}-{run}')
    meta = json.load(open(f'{out}/scene.json'))
    log = run_cars(['--net', f'{out}/net.xml', '--routes', f'{out}/routes.xml', '--replay', f'{out}/all.rpl', '--dt', '0.1',
                    '--begin', meta['begin'], '--end', meta['end'], '--time-to-teleport', '0', '--fcd', f'{out}/f100.fcd.csv', '--fcd-interval', '0.1'],
                   gpu=gpu, log=f'{out}/f100.log')
    print(log[-800:])
    score(out, 'f100.fcd.csv', 'f100.json')


def score(out, fcd_name, res_name):
    m = pd.read_csv(f'{out}/matched.csv.gz')
    m['trip'] = m.ID.astype(str) + '_' + m.piece.astype(str)
    f = read_fcd(f'{out}/{fcd_name}')
    f['ti'] = np.round(f.time * 10).astype(int)
    j = m.merge(f, on=['trip', 'ti'], how='left', suffixes=('', '_sim'))
    seen = j.pos.notna()
    lanes = lane_shapes(f'{out}/net.xml')
    poly = {lid: Polyline(v['shape'], v['length']) for lid, v in lanes.items()}
    k = j[seen].copy()
    k['dpos'] = (k.pos - k.s).abs()
    k['lane_ok'] = k.lane_sim == k.lane
    k['dv'] = (k.speed - k.speed_kf).abs()
    x = np.zeros(len(k)); y = np.zeros(len(k))
    for lid, g in k.groupby('lane_sim'):
        px, py = poly[lid].point(g.pos.values)
        x[k.index.get_indexer(g.index)] = px; y[k.index.get_indexer(g.index)] = py
    k['d2'] = np.hypot(x - k.xloc_kf, y - k.yloc_kf)
    # Samples missing from the output: the first of each track can be one step late if two trips share a lane queue step.
    miss = j[~seen]
    q = lambda v: {f'p{p}': round(float(np.percentile(v, p)), 4) for p in (50, 90, 99, 100)}
    res = dict(samples=int(len(j)), in_output=int(seen.sum()), missing=int((~seen).sum()),
               missing_first_of_track=int((miss.groupby('trip').ti.transform('min') == miss.ti).sum()),
               lane_mismatch=float(1 - k.lane_ok.mean()), harness_pos_abs_m=q(k.dpos), harness_speed_abs=q(k.dv),
               map_2d_m=q(k.d2), map_lateral_abs_m=q(k.lat.abs()))
    json.dump(res, open(f'{out}/{res_name}', 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    cmd, site, run = sys.argv[1], sys.argv[2], int(sys.argv[3])
    if cmd == 'build':
        build(site, run)
    elif cmd == 'f100':
        f100(site, run, gpu='--gpu' in sys.argv)
