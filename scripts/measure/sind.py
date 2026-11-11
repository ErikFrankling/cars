"""Part 7: launch and discharge at signals with recorded light states, on weekdays (SinD), against DLR UT's Sunday (F146).

SinD light codes, read from the sequences in the files: 1 green, 3 yellow (3 s), 0 red, then 1 s all-red; there is no
red-yellow, so the first driver has no warning a German driver gets. Xi'an is held out (HOLDOUT.md) and never read.

Per recording: motor vehicles (car, truck, bus) only. Approach = cluster of entry directions (4); movement from the
heading change (left over 45 degrees, right under -45, else straight; left is positive here, checked against Tianjin's
own CrossType labels). Along each approach, s = position projected on its entry direction. Stop line = 95th percentile
of s over first-in-queue stops (cars standing 2 s or more still heading along the approach, front used).
Which light governs an approach and movement: the light whose green onsets are followed, within 0-10 s, by the most
starts of cars of that approach and movement that stood at the onset.
At each green onset of that light: the queue is the cars of the approach and movement standing (under 0.5 m/s) within
60 m of the line, chained lane by lane (lateral offset within 1.5 m, front-to-front spacing under 15 m), the first within
12 m of the line. Headway: position 1 from green to its front crossing the line, then front to front. Start delay: green
to the first car passing 1.5 m/s. Launch: the first car's peak acceleration in the first 8 s (1 s quadratic of speed).

    python3 -I scripts/measure/sind.py       # -> research/truth/measure/sind.json
"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from holdout import HOLD

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
D = '/home/erikf/projects/personal/cars-data/datasets/jt25-sind/'
REC = {'Tianjin': ('Tianjin_8_2_1_Veh_smoothed_tracks.csv', 'Tianjin_8_2_1_TrafficLight_8_2_1.csv'),
       'Changchun': ('Changchun_changchun_pudong_507_009_Veh_smoothed_tracks.csv', 'Changchun_changchun_pudong_507_009_Traffic_Lights.csv'),
       'Chongqing': ('Chongqing_6_22_NR_1_Veh_smoothed_tracks.csv', 'Chongqing_6_22_NR_1_TrafficLight_06_22_NR1_add_plight.csv')}
MOTOR = {'car', 'truck', 'bus'}
rng = np.random.default_rng(3)


def lights(path):
    L = pd.read_csv(D + path)
    cols = [c for c in L.columns if 'light' in c.lower() and 'pedestrian' not in c.lower()]
    ts = L['timestamp(ms)'].to_numpy(float).copy(); fr = L['RawFrameID'].to_numpy(float)
    ok = np.isfinite(ts)
    if (~ok).any():
        k = np.polyfit(fr[ok], ts[ok], 1); ts[~ok] = np.polyval(k, fr[~ok])
    onsets = {}
    for c in cols:
        s = L[c].to_numpy()
        on = [ts[i] / 1000 for i in range(1, len(s)) if s[i] == 1 and s[i - 1] != 1]
        dur = [(ts[j] - ts[i]) / 1000 for i in range(len(s)) for j in [i + 1] if j < len(s) and s[i] == 3]
        onsets[c] = dict(green=np.array(on), yellow_s=dur)
    return onsets


def tracks(path):
    t = pd.read_csv(D + path, usecols=['track_id', 'timestamp_ms', 'agent_type', 'x', 'y', 'vx', 'vy', 'length'])
    t = t[t.agent_type.isin(MOTOR)].sort_values(['track_id', 'timestamp_ms']).reset_index(drop=True)
    t['t'] = t.timestamp_ms / 1000.0
    t['v'] = np.hypot(t.vx, t.vy)
    a = np.full(len(t), np.nan)
    ids = t.track_id.to_numpy(); cut = np.flatnonzero(np.diff(ids)) + 1
    for s, e in zip(np.r_[0, cut], np.r_[cut, len(t)]):
        if e - s >= 11:
            a[s:e] = savgol_filter(t.v.to_numpy()[s:e], 11, 2, deriv=1, delta=0.1)
    t['a'] = a
    return t


def describe_tracks(t):
    rows = []
    for i, g in t.groupby('track_id'):
        mv = g[g.v > 1.0]
        if len(mv) < 20:
            continue
        h0 = np.arctan2(mv.vy.iloc[:10].mean(), mv.vx.iloc[:10].mean()); h1 = np.arctan2(mv.vy.iloc[-10:].mean(), mv.vx.iloc[-10:].mean())
        turn = np.rad2deg(np.angle(np.exp(1j * (h1 - h0))))
        rows.append((i, h0, turn, 'left' if turn > 45 else 'right' if turn < -45 else 'straight', float(g.length.median())))
    return pd.DataFrame(rows, columns=['id', 'h0', 'turn', 'mv', 'L']).set_index('id')


def approaches(T):
    """Four entry directions by k-means on the unit circle."""
    u = np.c_[np.cos(T.h0), np.sin(T.h0)]
    c = np.array([[1, 0], [0, 1], [-1, 0], [0, -1]], float)
    hist = np.histogram(T.h0, bins=72, range=(-np.pi, np.pi))[0]
    rot = np.argmax(hist) * 2 * np.pi / 72 - np.pi
    R = np.array([[np.cos(rot), -np.sin(rot)], [np.sin(rot), np.cos(rot)]]); c = c @ R.T
    for _ in range(20):
        lab = np.argmax(u @ c.T, 1)
        for k in range(4):
            if (lab == k).any():
                m = u[lab == k].mean(0); c[k] = m / np.linalg.norm(m)
    return lab, c


def analyse(city):
    tp, lp = REC[city]
    t = tracks(tp); L = lights(lp)
    T = describe_tracks(t)
    lab, C = approaches(T)
    T['app'] = lab
    t = t[t.track_id.isin(T.index)].copy()
    t['app'] = T.app.reindex(t.track_id).values; t['mv'] = T.mv.reindex(t.track_id).values
    u = C[t.app.to_numpy()]
    t['s'] = t.x * u[:, 0] + t.y * u[:, 1] + t.length / 2           # front along the approach
    t['lat'] = -t.x * u[:, 1] + t.y * u[:, 0]
    # Is the car still heading along its approach (before its turn)?
    hd = np.arctan2(t.vy, t.vx)
    along = np.cos(hd - np.arctan2(u[:, 1], u[:, 0])) > 0.9
    out = {'yellow_s': {c: (round(float(np.median(v['yellow_s'])), 2) if v['yellow_s'] else None) for c, v in L.items()},
           'green_onsets': {c: len(v['green']) for c, v in L.items()}, 'cars': int(len(T))}
    groups = {}
    for (app, mv), g in t.groupby(['app', 'mv']):
        if mv == 'right':
            continue
        ids = g.track_id.unique()
        if len(ids) < 15:
            continue
        # Stops: runs of v < 0.5 lasting 2 s or more while still heading along the approach.
        stops = []
        for i, gg in g.groupby('track_id'):
            st = (gg.v.to_numpy() < 0.5)
            if st.sum() < 20:
                continue
            k = np.flatnonzero(st)
            stops.append((i, float(gg.s.to_numpy()[k].max()), float(gg.t.to_numpy()[k[0]]), float(gg.t.to_numpy()[k[-1]])))
        if len(stops) < 5:
            continue
        S = pd.DataFrame(stops, columns=['id', 's', 't0', 't1'])
        s_line = float(np.percentile(S.s, 95))
        # Which light: starts of standing cars within 0-10 s after its green onsets.
        best, score = None, -1
        for c, v in L.items():
            n = sum(int(((S.t1 >= gon - 0.5) & (S.t1 <= gon + 10) & (S.t0 < gon)).sum()) for gon in v['green'])
            if n > score:
                best, score = c, n
        groups[(app, mv)] = (g, S, s_line, best, score)
    rows = []
    for (app, mv), (g, S, s_line, light, score) in groups.items():
        gi = {i: gg for i, gg in g.groupby('track_id')}
        for gon in L[light]['green']:
            at = g[(np.abs(g.t - gon) < 0.06)]
            q_ = at[(at.v < 0.5) & (at.s > s_line - 60) & (at.s < s_line + 2)].sort_values('s', ascending=False)
            if not len(q_) or q_.s.iloc[0] < s_line - 12:
                continue
            # Chain lane by lane from the car nearest the line.
            used = set(); lanes = []
            for _, r in q_.iterrows():
                if r.track_id in used:
                    continue
                chain = [r]; used.add(r.track_id)
                for _, r2 in q_.iterrows():
                    if r2.track_id in used:
                        continue
                    if abs(r2.lat - chain[-1].lat) < 1.5 and 0 < chain[-1].s - r2.s < 15:
                        chain.append(r2); used.add(r2.track_id)
                if chain[0].s >= s_line - 12:
                    lanes.append(chain)
            for chain in lanes:
                prev = gon
                for pos, r in enumerate(chain, 1):
                    gg = gi[r.track_id]
                    after = gg[gg.t >= gon]
                    cr = after[after.s >= s_line]
                    if not len(cr):
                        break
                    tc = float(cr.t.iloc[0])
                    mvg = after[after.v > 1.5]
                    t_move = float(mvg.t.iloc[0]) if len(mvg) else np.nan
                    early = after[after.t <= gon + 8]
                    rows.append(dict(city=city, app=int(app), mv=mv, light=light, green=gon, pos=pos, id=int(r.track_id),
                                     headway=tc - prev, cross=tc - gon, start_delay=t_move - gon, v_line=float(cr.v.iloc[0]),
                                     peak_acc=float(np.nanmax(early.a)) if len(early) else np.nan, s_stop=float(r.s - s_line)))
                    prev = tc
        out[f'app{app} {mv}'] = dict(light=light, starts_matched=score, stop_line_s=round(s_line, 1), stops=len(S))
    return out, pd.DataFrame(rows)


def boot_median(x, reps=400):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 5:
        return None
    b = [np.median(x[rng.integers(0, len(x), len(x))]) for _ in range(reps)]
    return [round(float(np.median(x)), 2), round(float(np.percentile(b, 2.5)), 2), round(float(np.percentile(b, 97.5)), 2), int(len(x))]


def summarise(R):
    res = {}
    for name, k in [('all', R)] + [(c, g) for c, g in R.groupby('city')] + [(f'movement {m}', g) for m, g in R.groupby('mv')]:
        r = {'queues': int(k[k.pos == 1].shape[0]), 'cars': int(len(k))}
        r['headway_by_position'] = {int(p): boot_median(g.headway) for p, g in k.groupby(np.minimum(k.pos, 8))}
        r['saturation_headway_pos4plus'] = boot_median(k[k.pos >= 4].headway)
        r['saturation_headway_pos5plus'] = boot_median(k[k.pos >= 5].headway)
        f = k[k.pos == 1]
        r['first_car_start_delay_s'] = boot_median(f.start_delay)
        r['first_car_start_delay_p10_p90'] = [round(float(f.start_delay.quantile(.1)), 2), round(float(f.start_delay.quantile(.9)), 2)] if len(f) > 5 else None
        r['first_car_peak_acc'] = boot_median(f.peak_acc)
        r['first_car_peak_acc_p5_p95'] = [round(float(f.peak_acc.quantile(.05)), 2), round(float(f.peak_acc.quantile(.95)), 2)] if len(f) > 5 else None
        r['speed_at_line_by_position'] = {int(p): round(float(g.v_line.median()), 1) for p, g in k.groupby(np.minimum(k.pos, 8))}
        sat = k[k.pos >= 4].headway.median()
        if np.isfinite(sat):
            lost = (k[k.pos <= 4].groupby('pos').headway.median() - sat).clip(lower=0).sum()
            r['lost_time_first4_s'] = round(float(lost), 2)
        res[name] = r
    return res


def clock_split(R):
    """Changchun's light log looks offset by several seconds (cars on light 2 keep crossing about 4 s past the logged
    red and every queue head starts 4-7.5 s after the logged green), so numbers that need the green onset come from
    Tianjin and Chongqing only; headways from position 2 on and launch acceleration need no clock and use all three."""
    clk = R[R.city.isin(['Tianjin', 'Chongqing'])]
    f = clk[clk.pos == 1]
    out = dict(clock_cities=['Tianjin', 'Chongqing'], queue_heads=int(len(f)),
               first_car_start_delay_s=boot_median(f.start_delay), first_car_start_delay_p10_p90=[round(float(f.start_delay.quantile(.1)), 2), round(float(f.start_delay.quantile(.9)), 2)],
               first_headway_s=boot_median(f.headway),
               by_city={c: dict(start_delay=boot_median(g[g.pos == 1].start_delay), first_headway=boot_median(g[g.pos == 1].headway)) for c, g in clk.groupby('city')})
    a = R[R.pos >= 2]
    out['clock_free'] = dict(headway_by_position={int(p): boot_median(g.headway) for p, g in a.groupby(np.minimum(a.pos, 6))},
                             saturation_pos4plus=boot_median(a[a.pos >= 4].headway),
                             saturation_pos4plus_by_city={c: boot_median(g[g.pos >= 4].headway) for c, g in a.groupby('city')},
                             first_car_peak_acc=boot_median(R[R.pos == 1].peak_acc),
                             first_car_peak_acc_by_city={c: boot_median(g[g.pos == 1].peak_acc) for c, g in R.groupby('city')},
                             first_car_peak_acc_p5_p95=[round(float(R[R.pos == 1].peak_acc.quantile(.05)), 2), round(float(R[R.pos == 1].peak_acc.quantile(.95)), 2)])
    return out


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'summary':
        R = pd.read_csv('/home/erikf/projects/personal/cars-data/measure/sind/queues.csv')
        res = json.load(open(os.path.join(RES, 'sind.json'))); res['clock_split'] = clock_split(R)
        json.dump(res, open(os.path.join(RES, 'sind.json'), 'w'), indent=1); print(json.dumps(res['clock_split'], indent=0)); sys.exit(0)
    assert not (set(REC) & HOLD['sind'])
    info, rows = {}, []
    for city in REC:
        o, r = analyse(city)
        info[city] = o; rows.append(r)
        print(city, json.dumps(o)[:800], len(r), flush=True)
    R = pd.concat(rows, ignore_index=True)
    os.makedirs('/home/erikf/projects/personal/cars-data/measure/sind', exist_ok=True)
    R.to_csv('/home/erikf/projects/personal/cars-data/measure/sind/queues.csv', index=False)
    res = dict(recordings=info, summary=summarise(R), clock_split=clock_split(R),
               dlr_ut_sunday_report05=dict(headway_by_position=[3.62, 2.4, 2.2, 2.2, 2.0, 2.0, 2.0], start_after_green=1.62, peak_acc=1.80, saturation=2.0, lost_time=2.74))
    json.dump(res, open(os.path.join(RES, 'sind.json'), 'w'), indent=1)
    print(json.dumps(res['summary'], indent=0)[:4000])
