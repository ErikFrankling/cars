"""exiD on-ramp merges in the harness (research/truth/measure/LANECHANGE.md, F720 onwards).

Setting 1 (one merger simulated): each car that merges off an acceleration lane is released when its front first enters
that lane; everyone else is replayed. Mergers are split into groups whose releases are at least GAP_S apart, one run per
group, so no two simulated mergers meet. Setting 2 (ramp and rightmost lane simulated): every car on an acceleration lane
or on the main lane beside it is released when it enters that edge section; the rest are replayed.

Compared with the same cars in the recording: where the centre crosses the marking (metres before the end of the
acceleration lane, share of its length), the lag and lead time gaps there, time from entering the lane to crossing.
Overlaps of a simulated car with a replayed one are counted (harness artefact, README.md), never scored as behaviour.

    python3 -I scripts/replay/lc_merge.py run REC TAG [--setting 1|2] [--gpu] [--flags "..."] [--seeds 0,1,2]
    python3 -I scripts/replay/lc_merge.py score TAG
"""
import os, sys, json, argparse, xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rpl import run_cars, write_rpl, INF
import numpy as np, pandas as pd

DATA = '/home/erikf/projects/personal/cars-data/replay'
WORK = '/home/erikf/projects/personal/cars-data/replay/lc_merge'
DT = 0.25
GAP_S = 12.0


def net_info(D):
    r = ET.parse(f'{D}/net.xml').getroot()
    lanes = {}
    for e in r.iter('edge'):
        if e.get('function') == 'internal':
            continue
        n = len(list(e.iter('lane')))
        for l in e.iter('lane'):
            lanes[l.get('id')] = dict(edge=e.get('id'), index=int(l.get('index')), length=float(l.get('length')), width=float(l.get('width', 3.2)), n=n)
    succ, pred = {}, {}
    for c in r.iter('connection'):
        if c.get('from', '').startswith(':'):
            continue
        a = f"{c.get('from')}_{c.get('fromLane')}"; b = f"{c.get('to')}_{c.get('toLane')}"
        succ.setdefault(a, []).append(b); pred.setdefault(b, []).append(a)
    # Acceleration lanes: index 0 of a multi-lane edge whose chain of index-0 successors ends without a way on.
    chains = []
    for l, v in lanes.items():
        if v['index'] == 0 and v['n'] > 1 and l not in succ:
            ch = [l]
            while True:
                p = [x for x in pred.get(ch[0], []) if lanes.get(x, {}).get('index') == 0 and lanes[x]['n'] > 1 and len(succ.get(x, [])) == 1]
                if len(p) != 1 or p[0] in ch:
                    break
                ch.insert(0, p[0])
            start = np.cumsum([0] + [lanes[x]['length'] for x in ch[:-1]])
            chains.append(dict(lanes=ch, start=dict(zip(ch, start)), length=float(start[-1] + lanes[ch[-1]]['length'])))
    return lanes, chains


def build(rec, setting):
    D = f'{DATA}/levelx-exiD-{rec:02d}-merged'
    lanes, chains = net_info(D)
    acc = {l: c for c in chains for l in c['lanes']}
    beside = {f"{lanes[l]['edge']}_1": c for c in chains for l in c['lanes']}
    m = pd.read_csv(f'{D}/matched.csv.gz')
    m['trip'] = m.id.astype(int).astype(str) + '_' + m.piece.astype(str)
    meta = json.load(open(f'{D}/scene.json')); fps = 1.0 / meta['key_dt']; tb = meta['recording_time_of_scene_zero_s']
    m['t'] = m.ti / fps - tb
    m = m.sort_values(['trip', 'ti']).reset_index(drop=True)
    # A lane cut at the edge of the view also dead-ends in the net: an acceleration lane is one that most cars leave
    # by moving over, not by leaving the view.
    keep = []
    for c in chains:
        S = set(c['lanes']); moved = ended = 0
        for _, g in m[m.lane_id.isin(S)].groupby('trip', sort=False):
            last = g.index[-1]
            nxt = m.lane_id.get(last + 1) if (last + 1) in m.index and m.trip.get(last + 1) == g.trip.iloc[0] else None
            if nxt is None:
                ended += 1
            elif lanes.get(nxt, {}).get('index') == 1:
                moved += 1
        if moved > ended:
            keep.append(c)
    chains = keep
    acc = {l: c for c in chains for l in c['lanes']}
    beside = {f"{lanes[l]['edge']}_1": c for c in chains for l in c['lanes']}
    rel, kind, cof = {}, {}, {}
    for trip, g in m.groupby('trip', sort=False):
        ln = g.lane_id.to_numpy()
        on = np.flatnonzero([x in acc for x in ln])
        if setting == 1:
            if not len(on):
                continue
            k = on[-1] + 1
            if k < len(ln) and lanes.get(ln[k], {}).get('index') == 1 and lanes[ln[k]]['edge'] == lanes[ln[on[-1]]]['edge']:
                rel[trip] = float(g.t.iloc[on[0]]); kind[trip] = 'merger'; cof[trip] = id(acc[ln[on[0]]])
        else:
            nb = np.flatnonzero([x in acc or x in beside for x in ln])
            if len(nb):
                rel[trip] = float(g.t.iloc[nb[0]]); kind[trip] = 'merger' if len(on) else 'main'
    # Groups: setting 1 needs mergers far apart in time; setting 2 is one run.
    groups = []
    if setting == 1:
        for trip in sorted(rel, key=rel.get):
            for g in groups:
                if all(abs(rel[trip] - rel[x]) >= GAP_S or cof[x] != cof[trip] for x in g):
                    g.append(trip); break
            else:
                groups.append([trip])
    else:
        groups = [list(rel)]
    return D, m, lanes, chains, acc, rel, kind, groups, meta


def write_group(D, out, k, members, rel):
    import struct
    src = open(f'{D}/routes.xml').read()
    mem = set(members)
    lines = []
    for line in src.splitlines():
        if '<vehicle ' in line:
            vid = line.split('id="')[1].split('"')[0]
            if vid in mem:
                L = line.split('type="rep')[1].split('"')[0]
                line = line.replace(f'type="rep{L}"', f'type="drv{L}"')
        lines.append(line)
        if line.strip() == '<routes>':
            for L in sorted({x.split('type="rep')[1].split('"')[0] for x in src.splitlines() if '<vehicle ' in x and x.split('id="')[1].split('"')[0] in mem}):
                lines.append(f'  <vType id="drv{L}" length="{L}"/>')
    open(f'{out}/routes_{k}.xml', 'w').write('\n'.join(lines) + '\n')
    # The same tracks with release times: read the scene's RPL2 and rewrite the release field.
    with open(f'{D}/all.rpl', 'rb') as f:
        b = f.read()
    o = 4; n_l = struct.unpack_from('<I', b, o)[0]; o += 4
    for _ in range(n_l):
        ln = struct.unpack_from('<H', b, o)[0]; o += 2 + ln
    n_t = struct.unpack_from('<I', b, o)[0]; o += 4
    rec_size = 16 if b[:4] == b'RPL2' else 12
    out_b = bytearray(b)
    for _ in range(n_t):
        ln = struct.unpack_from('<H', b, o)[0]; tid = b[o + 2:o + 2 + ln].decode(); o += 2 + ln
        t0, kdt, r0, n = struct.unpack_from('<fffI', b, o)
        if tid in mem:
            struct.pack_into('<f', out_b, o + 8, rel[tid])
        o += 16 + n * rec_size
    open(f'{out}/g{k}.rpl', 'wb').write(bytes(out_b))


def run(a):
    rec = int(a.rec)
    D, m, lanes, chains, acc, rel, kind, groups, meta = build(rec, a.setting)
    out = f'{WORK}/{a.tag}/exiD{rec:02d}_s{a.setting}'
    os.makedirs(out, exist_ok=True)
    json.dump(dict(rel=rel, kind=kind, groups=groups, chains=[dict(c, start={k: float(v) for k, v in c['start'].items()}) for c in chains]), open(f'{out}/plan.json', 'w'))
    print(f'exiD {rec}: {sum(1 for v in kind.values() if v == "merger")} mergers, {len(groups)} runs', flush=True)
    for k, g in enumerate(groups):
        write_group(D, out, k, g, rel)
        for sd in a.seeds:
            fcd = f'{out}/g{k}_s{sd}.fcd.csv'
            if os.path.exists(fcd):
                continue
            args = ['--net', f'{D}/net.xml', '--routes', f'{out}/routes_{k}.xml', '--replay', f'{out}/g{k}.rpl', '--dt', DT, '--begin', 0,
                    '--end', meta['end'], '--time-to-teleport', 0, '--seed', sd, '--fcd', fcd + '.tmp', '--fcd-interval', DT] + a.flags.split()
            log = run_cars(args, gpu=a.gpu, log=f'{out}/g{k}_s{sd}.log')
            os.replace(fcd + '.tmp', fcd)
            print(k, sd, [l for l in log.splitlines() if 'replay' in l or 'contact' in l.lower()][:3], flush=True)


def crossings(f, sims, lanes, acc, chains):
    """Per simulated (or recorded) trip: time, metres left, lane-length share and gaps when the centre crosses from an
    acceleration lane onto the lane beside it. f: time, trip, lane, pos (front), speed, length, lat (centre offset, left +)."""
    out = []
    f = f.sort_values(['trip', 'time'])
    by_t = {t: g for t, g in f.groupby('time')}
    for trip, g in f[f.trip.isin(sims)].groupby('trip', sort=False):
        ln = g.lane.to_numpy(); lat = g.lat.to_numpy()
        on = np.array([x in acc for x in ln])
        if not on.any():
            continue
        # The simulator moves the label at the start; the centre crosses where offset from the new lane's centre passes
        # minus half a lane. The recording labels the centre's lane.
        nx = np.flatnonzero(on[:-1] & ~on[1:]) + 1
        if not len(nx):
            out.append(dict(trip=trip, merged=False)); continue
        k = nx[0]; c = acc[ln[k - 1]]
        if lanes.get(ln[k], {}).get('index') != 1:
            continue
        # The change may run on over the next section: follow the car until its centre is over the marking.
        wd = np.array([lanes.get(x, {}).get('width', 3.5) for x in ln[k:]])
        ix = np.array([lanes.get(x, {}).get('index', -1) for x in ln[k:]])
        j = k + np.flatnonzero((ix >= 1) & (lat[k:] > -0.5 * wd))[:1]
        if not len(j):
            continue
        j = int(j[0]); dest = ln[j]
        row = g.iloc[j]; t = row.time
        a0 = dest.rsplit('_', 1)[0] + '_0'
        s_acc = (c['start'][a0] if a0 in c['start'] else c['length']) + row.pos - 0.5 * row.length
        t_on = g.time.iloc[np.flatnonzero(on)[0]]
        nb = by_t[t]; nb = nb[(nb.lane == dest) & (nb.trip != trip)]
        ahead = nb[nb.pos > row.pos]; behind = nb[nb.pos <= row.pos]
        lead = (ahead.pos - ahead.length - row.pos).min() if len(ahead) else np.nan
        if len(behind):
            bb = behind.loc[behind.pos.idxmax()]; lag = row.pos - row.length - bb.pos; lag_v = bb.speed
        else:
            lag, lag_v = np.nan, np.nan
        out.append(dict(trip=trip, merged=True, t_cross=t, t_label=g.time.iloc[k], left=c['length'] - s_acc, share=s_acc / c['length'], acc_len=c['length'],
                        v=row.speed, lag=lag, lag_v=lag_v, lead=lead, lag_tg=lag / max(lag_v, 1.0) if np.isfinite(lag) else np.nan,
                        lead_tg=lead / max(row.speed, 1.0) if np.isfinite(lead) else np.nan, t_on_to_cross=t - t_on))
    return pd.DataFrame(out)


def score(a):
    res = {}
    for d in sorted(x for x in os.listdir(f'{WORK}/{a.tag}') if x.startswith('exiD')):
        out = f'{WORK}/{a.tag}/{d}'
        rec = int(d[4:6]); setting = int(d.split('_s')[1])
        D, m, lanes, chains, acc, rel, kind, groups, meta = build(rec, setting)
        mergers = {t for t, k in kind.items() if k == 'merger'}
        real = m.drop(columns=['lat']).rename(columns={'t': 'time', 'trip': 'trip', 'lane_id': 'lane', 's': 'pos', 'v': 'speed', 'lat_left': 'lat'})
        real['time'] = np.round(real.time / DT) * DT
        real = real.drop_duplicates(['trip', 'time'])
        R = crossings(real[['time', 'trip', 'lane', 'pos', 'speed', 'length', 'lat']], mergers, lanes, acc, chains)
        sims = []
        for k, g in enumerate(groups):
            for sd in a.seeds:
                p = f'{out}/g{k}_s{sd}.fcd.csv'
                if not os.path.exists(p):
                    continue
                f = pd.read_csv(p, usecols=['time', 'trip', 'lane', 'pos', 'speed', 'length', 'offset']).rename(columns={'offset': 'lat'})
                S = crossings(f, set(g) & mergers, lanes, acc, chains); S['seed'] = sd
                # Overlaps: a simulated car's bumper gap below zero to any vehicle on its lane.
                f = f.sort_values(['time', 'lane', 'pos'])
                same = (f.lane.values[1:] == f.lane.values[:-1]) & (f.time.values[1:] == f.time.values[:-1])
                gap = f.pos.values[1:] - f.length.values[1:] - f.pos.values[:-1]
                sim = f.trip.isin(set(g)).values
                ov = same & (gap < 0) & (sim[1:] | sim[:-1])
                S.attrs['overlap_pairs'] = int(len(set(zip(f.trip.values[1:][ov], f.trip.values[:-1][ov]))))
                sims.append((S, S.attrs['overlap_pairs']))
        if not sims:
            continue
        S = pd.concat([s for s, _ in sims])
        res[d] = summarise(R, S, sum(o for _, o in sims), len(mergers))
    json.dump(res, open(f'{WORK}/{a.tag}/score.json', 'w'), indent=1)
    print(json.dumps(res, indent=1))


def qs(v, ps=(5, 25, 50, 75, 95)):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return {f'p{p}': round(float(np.percentile(v, p)), 3) for p in ps} | {'n': int(len(v))} if len(v) else {'n': 0}


def summarise(R, S, overlaps, n):
    Rm = R[R.merged == True]; Sm = S[S.merged == True]
    out = dict(mergers=n, real_merged=len(Rm), sim_merged=len(Sm), sim_runs=len(S), overlap_pairs=overlaps)
    for col in ('left', 'share', 'lag_tg', 'lead_tg', 'v', 't_on_to_cross'):
        out[col] = dict(real=qs(Rm[col]), sim=qs(Sm[col]))
    out['last_tenth'] = dict(real=round(float((Rm.share > 0.9).mean()), 3), sim=round(float((Sm.share > 0.9).mean()), 3))
    # Paired: the same car, simulated against recorded.
    j = Sm.merge(Rm, on='trip', suffixes=('_s', '_r'))
    out['paired_left_diff_m'] = qs(j.left_s - j.left_r)
    out['paired_t_diff_s'] = qs(j.t_cross_s - j.t_cross_r)
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('cmd'); p.add_argument('rec', nargs='?'); p.add_argument('tag', nargs='?')
    p.add_argument('--setting', type=int, default=1); p.add_argument('--gpu', action='store_true'); p.add_argument('--flags', default='')
    p.add_argument('--seeds', default='0')
    a = p.parse_args()
    a.seeds = [int(x) for x in a.seeds.split(',')]
    if a.cmd == 'score':
        a.tag = a.rec
        score(a)
    else:
        run(a)
