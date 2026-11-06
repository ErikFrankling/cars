"""F100 on levelX scenes (scripts/measure/levelx_scene.py): every vehicle replayed, with its lateral offset, and the
simulator's output compared with the recording: lane coordinates against the keys, and the 2D centre (lane point at
the centre plus the lateral offset along the lane's left normal) against the recorded centre.

    python3 -I scripts/replay/levelx_f100.py SCENE_DIR [--gpu] [--dt 0.2]
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from rpl import run_cars, lane_shapes, Polyline
import numpy as np, pandas as pd


def centre_xy(poly, pos_c, offset):
    p = poly
    s = np.clip(np.asarray(pos_c, float) / p.scale, 0, p.cum[-1])
    i = np.clip(np.searchsorted(p.cum, s, side='right') - 1, 0, len(p.seg) - 1)
    t = s - p.cum[i]
    x = p.p[i, 0] + t * p.u[i, 0]; y = p.p[i, 1] + t * p.u[i, 1]
    return x - offset * p.u[i, 1], y + offset * p.u[i, 0]


def main(scene, gpu=False, dt=0.2):
    meta = json.load(open(f'{scene}/scene.json'))
    fcd = f'{scene}/f100.fcd.csv'
    args = ['--net', f'{scene}/net.xml', '--routes', f'{scene}/routes.xml', '--replay', f'{scene}/all.rpl', '--dt', dt,
            '--begin', 0, '--end', meta['end'], '--time-to-teleport', 0, '--fcd', fcd, '--fcd-interval', dt]
    log = run_cars(args, gpu=gpu, log=f"{scene}/f100.log") if "--score" not in sys.argv else open(f"{scene}/f100.log").read()
    rl = [l for l in log.splitlines() if l.startswith('replay')]
    m = pd.read_csv(f'{scene}/matched.csv.gz')
    fps = 1.0 / meta['key_dt']; tb = meta['recording_time_of_scene_zero_s']
    m['trip'] = m.id.astype(int).astype(str) + '_' + m.piece.astype(str)
    m['k'] = np.round((m.ti / fps - tb) / dt).astype(int)
    m = m[np.abs((m.ti / fps - tb) / dt - m.k) < 1e-3]
    f = pd.read_csv(fcd, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'length', 'offset'])
    f['k'] = np.round(f.time / dt).astype(int)
    # A replayed trip's first output step is its insertion: depart state, before the replay pass has put it on its
    # keys (the pass runs before insertion in a step). Counted, with how late it came in, and left out of the errors.
    first = f.groupby('trip').k.transform('min') == f.k
    t0 = m.groupby('trip').ti.min() / fps - tb
    ins_delay = (f[first].set_index('trip').time - t0.reindex(f[first].trip).values).dropna()
    f = f[~first]
    j = m.merge(f, on=['trip', 'k'], how='left')
    k = j[j.pos.notna()].copy()
    LS = lane_shapes(f'{scene}/net.xml')
    poly = {l: Polyline(v['shape'], v['length']) for l, v in LS.items()}
    x = np.zeros(len(k)); y = np.zeros(len(k)); cx = np.zeros(len(k)); cy = np.zeros(len(k)); con = np.zeros(len(k), bool)
    Ls = k.length_y.values if 'length_y' in k else k.length.values
    for l, g in k.groupby('lane'):
        if l not in poly:
            continue
        ix = k.index.get_indexer(g.index)
        # the simulator keeps the front; the centre is compared where it is on the same lane (not behind its start)
        x[ix], y[ix] = centre_xy(poly[l], g.pos.values, g.offset.values)
        cx[ix], cy[ix] = centre_xy(poly[l], g.pos.values - Ls[ix] / 2, g.offset.values)
        con[ix] = g.pos.values - Ls[ix] / 2 >= 0
    Lr = k.length_x.values if 'length_x' in k else k.length.values
    h = np.deg2rad(k.heading.values)
    if meta['dataset'] == 'highD':
        # image frame, y down; the net has y up
        rx, ry = k.xc.values + 0.5 * Lr * np.cos(h), -k.yc.values
    else:
        rx, ry = k.xc.values + 0.5 * Lr * np.cos(h), k.yc.values + 0.5 * Lr * np.sin(h)
    d2 = np.hypot(x - rx, y - ry)
    c2 = np.hypot(cx - k.xc.values, cy - (-k.yc.values if meta['dataset'] == 'highD' else k.yc.values))[con]
    same = k.lane == k.lane_id
    q = lambda v: {f'p{p}': round(float(np.percentile(v, p)), 4) for p in (50, 90, 99, 100)} if len(v) else None
    res = dict(scene=os.path.basename(scene), dataset=meta['dataset'], recording=meta['recording'], dt=dt, replay_log=rl,
               insertion_steps_left_out=int(first.sum()), insertion_delay_s={f'p{p}': round(float(np.percentile(ins_delay, p)), 2) for p in (50, 90, 99, 100)},
               samples_on_grid=int(len(j)), in_output=int(len(k)), missing=int(j.pos.isna().sum()),
               missing_first_or_last_key_of_piece=int(((j.ti == j.groupby('trip').ti.transform('max')) | (j.ti == j.groupby('trip').ti.transform('min')))[j.pos.isna()].sum()),
               lane_mismatch=round(float((~same).mean()), 5),
               lane_mismatch_within_1m_of_marking=round(float(((~same) & (np.abs(k.lat_left) > 0.5 * 3.5 - 1.0)).sum() / max((~same).sum(), 1)), 3),
               harness_pos_abs_m=q((k.pos - k.s).abs()[same]), harness_lat_abs_m=q((k.offset - k.lat_left).abs()[same]),
               centre_2d_m=q(c2), centre_on_its_lane_share=round(float(con.mean()), 3), front_2d_m=q(d2), map_lateral_abs_m=q(k.lat.abs()), pieces_per_vehicle=meta.get('pieces_per_vehicle'))
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(REPO, 'research/truth/replay', f'f100_{os.path.basename(scene)}.json'), 'w'), indent=1)
    return res


if __name__ == '__main__':
    dt = float(sys.argv[sys.argv.index('--dt') + 1]) if '--dt' in sys.argv else 0.2
    main(sys.argv[1].rstrip('/'), '--gpu' in sys.argv, dt)
