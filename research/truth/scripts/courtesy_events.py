"""Event study: what the target-lane follower does around a real lane change, against matched follower-leader controls with no cut-in.
Usage: courtesy_events.py SITE [SITE...]. Writes research/truth/courtesy/events_SITE.csv.gz and controls_SITE.csv.gz."""
import sys; sys.path.insert(0, 'research/truth/scripts')
from courtesy_lib import *

TAU = np.arange(-8, 8.01, 0.5)
AB = [(-8, -6), (-6, -5), (-5, -4), (-4, -3), (-3, -2), (-2, -1), (-1, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]


def load(site):
    if site in ('us-101', 'i-80'):
        d = ngsim(C / 'ngsim-20261101' / f'{site}.csv'); return d[d['lane'] > 0], lambda a, b: abs(a - b) == 1 and max(a, b) <= 7
    if site in ('lankershim', 'peachtree'):
        d = ngsim(T / 'opus-20261031-ngsim' / f'{site}.csv', urban=True)
        d = d[(d['int_id'] == 0) & d['dirn'].isin([2, 4]) & d['lane'].isin([1, 2, 3, 4, 11, 12])].copy()
        d['s'] = (d['s'] * np.where(d['dirn'] == 2, 1, -1)).astype('f4')
        d['lane'] = (d['lane'].astype('i4') + 100 * d['dirn'].astype('i4')).astype('i2')
        def adj(a, b):
            if a // 100 != b // 100: return False
            x, y = sorted((a % 100, b % 100))
            return (y - x == 1 and y <= 4) or (x, y) == (1, 11) or (x, y) == (11, 12)
        return d, adj
    if site == 'ht':
        d = ht(); d = d[d['tr'] == 0]
        return d, lambda a, b: abs(a - b) == 1 and a * b > 0
    d = tgsim(site); d = d[d['auto'] == 0]
    return d, lambda a, b: abs(a - b) == 1 and a * b > 0 and {abs(a), abs(b)} not in ({3, 4}, {12, 13}) and max(abs(a), abs(b)) < 20


def series_row(fr, r, tc, f, l, ego=None):
    """Series of follower f and leader l around frame tc, taking tau in seconds."""
    tq = tc + np.round(TAU * fr.hz).astype('i4')
    vf, sf, af, lf = fr.series(r, f, tq); vl, sl, al, ll = fr.series(r, l, tq) if l is not None else [np.full(len(tq), np.nan)] * 4
    return tq, vf, sf, af, lf, vl, sl, al, ll


def own_brake(v, i0, i1, dt=0.5):
    """Metres the vehicle fell behind its own speed at i0 between i0 and i1."""
    return float(np.nansum((v[i0] - v[i0:i1 + 1]) * dt))


def idx(t): return int(round((t - TAU[0]) / 0.5))


def metrics(r, new, tc, vf, sf, af, lf, vl, sl, ll, Ll, e=None):
    i_4, i0, i4, i_6, i6 = idx(-4), idx(0), idx(4), idx(-6), idx(6)
    gfl = sl - Ll - sf
    m = dict(run=r, t=tc, vf=vf[i_4], vf0=vf[i0], gfl_4=gfl[i_4], gfl0=gfl[i0], gfl4=gfl[i4], vl_4=vl[i_4],
             dF_pre=own_brake(vf, i_4, i0), dF_post=own_brake(vf, i0, i4), dL_pre=-own_brake(vl, i_4, i0), dL_post=-own_brake(vl, i0, i4),
             dF_pre2=own_brake(vf, idx(-2), i0), minacc=np.nanmin(af[i_4:i4 + 1]), minacc_pre=np.nanmin(af[i_4:i0 + 1]),
             v_drop=vf[i_4] - np.nanmin(vf[i_4:i4 + 1]), f_same=int(np.all(lf[i_4:i4 + 1] == new)), l_same=int(np.all(ll[i_4:i4 + 1] == new)))
    for a, b in AB:
        m[f'a_{a}_{b}'] = float(np.nanmean(af[idx(a):idx(b) + 1]))
    return m


def run(site):
    d, adj = load(site)
    fr = Frames(d, 5 if site == 'ht' else 10)
    print(site, 'rows', len(d), 'vehicles', len(fr.veh), flush=True)
    lcs = lane_changes(fr, adj)
    print(site, 'lane changes', len(lcs), flush=True)
    ev = []
    for r, vid, tc, old, new in lcs:
        tk = tc
        ve0, se0, ae0, le0 = fr.series(r, vid, np.array([tc]))
        if not np.isfinite(se0[0]): continue
        fi, li = fr.neighbours(r, tc, new, float(se0[0]), vid)
        if fi < 0: continue
        F = int(fr.ID[fi]); L = int(fr.ID[li]) if li >= 0 else None
        tq, vf, sf, af, lf, vl, sl, al, ll = series_row(fr, r, tc, F, L)
        Le = fr.vL[fr.track(r, vid)[0]]; Lf = fr.LEN[fi]; Ll = fr.LEN[li] if li >= 0 else np.nan
        m = metrics(r, new, tc, vf, sf, af, lf, vl, sl, ll, Ll)
        ve, se, ae, le = fr.series(r, vid, tq)
        i_4, i0, i_2 = idx(-4), idx(0), idx(-2)
        lat = None
        m.update(id=vid, old=old, new=new, F=F, L=-1 if L is None else L, ve_4=ve[i_4], ve0=ve[i0], lag_4=se[i_4] - Le - sf[i_4], lag_2=se[i_2] - Le - sf[i_2], lag0=se[i0] - Le - sf[i0],
                 lead_4=sl[i_4] - Ll - se[i_4], lead_2=sl[i_2] - Ll - se[i_2], lead0=sl[i0] - Ll - se[i0], vl0=vl[i0], ae_pre=float(np.nanmean(ae[i_4:i0 + 1])), Le=Le, Lf=Lf)
        ev.append(m)
    ev = pd.DataFrame(ev); ev['site'] = site
    ev.to_csv(OUT / f'events_{site}.csv.gz', index=False, float_format='%.3f')
    # controls: follower-leader pairs that stay together for the whole window, drawn at random frames
    rng = np.random.default_rng(7)
    busy = {}
    for r, vid, tc, old, new in lcs:
        busy.setdefault((r, new), []).append(tc)
    busy = {k: np.sort(v) for k, v in busy.items()}
    n_all = len(fr.R); ct = []; tries = 0; target = max(6000, 4 * len(ev))
    while len(ct) < target and tries < target * 30:
        tries += 1
        i = int(rng.integers(0, n_all - 1))
        if fr.K[i] != fr.K[i + 1]: continue
        r, tc, lane, F, L = int(fr.R[i]), int(fr.TT[i]), int(fr.LA[i]), int(fr.ID[i]), int(fr.ID[i + 1])
        b = busy.get((r, lane))
        if b is not None:
            j = np.searchsorted(b, tc); near = False
            for jj in (j - 1, j):
                if 0 <= jj < len(b) and abs(int(b[jj]) - tc) <= 10 * fr.hz: near = True
            if near: continue
        tq, vf, sf, af, lf, vl, sl, al, ll = series_row(fr, r, tc, F, L)
        if not (np.all(lf[idx(-4):idx(4) + 1] == lane) and np.all(ll[idx(-4):idx(4) + 1] == lane)): continue
        m = metrics(r, lane, tc, vf, sf, af, lf, vl, sl, ll, fr.LEN[i + 1])
        m.update(lane=lane)
        ct.append(m)
    ct = pd.DataFrame(ct); ct['site'] = site
    ct.to_csv(OUT / f'controls_{site}.csv.gz', index=False, float_format='%.3f')
    print(site, 'events', len(ev), 'controls', len(ct), 'tries', tries, flush=True)


for s in sys.argv[1:]: run(s)
