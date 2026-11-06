"""Part 3: does one driver keep their time gap and free speed along a trip? (F136, F137)

DLR HT (A39, about 6.5 km, Monday 06:00-10:00 UTC, blocks from dlrht.py): each car track is cut into 20 s windows.
A window is *following* when a same-lane leader is within 100 m in every sample and |dv| < 1.5 m/s in 80% of them; its
value is the median log time gap (bumper gap from box lengths, which are plausible here: car median 4.43 m).
A window is *free* when no same-lane vehicle is within 150 m ahead in any sample; its value is the mean speed.
Each window value has the mean of its cell (250 m of road x 20-minute block x lane) removed, so a place or a traffic
state shared by everyone is not counted as persistence. Then the correlation between two windows of one track is taken
over all pairs at separation d, with a 95% interval from resampling tracks.
highD (420 m of road): the first and last 4 s of each track that follows (or is free) in both.

    python3 -I scripts/measure/persist.py     # -> research/truth/measure/persist.json
"""
import os, sys, json, glob
import numpy as np, pandas as pd
from scipy.optimize import curve_fit

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import levelx as LX

RES = os.path.join(HERE, '..', '..', 'research', 'truth', 'measure')
BLK = '/home/erikf/projects/personal/cars-data/measure/dlrht'
rng = np.random.default_rng(7)
W = 100  # 20 s at 5 Hz


def windows_ht():
    rows = []
    for p in sorted(glob.glob(f'{BLK}/b*.npz')):
        blk = int(os.path.basename(p)[1:3])
        zf = np.load(p); z = {k: zf[k] for k in zf.files}
        ids = z['id']; cut = np.flatnonzero(np.diff(ids)) + 1
        for a, b in zip(np.r_[0, cut], np.r_[cut, len(ids)]):
            if b - a < 2 * W or z['tr'][a] or z['L'][a] > 7:
                continue
            for w0 in range(a, b - W + 1, W):
                sl = slice(w0, w0 + W)
                cc, v, vl, L, Ll, s, ln = z['cc'][sl], z['v'][sl], z['vl'][sl], z['L'][sl], z['Ll'][sl], z['s'][sl], z['lane'][sl]
                if np.any(~np.isfinite(s)) or np.median(v) < 15:
                    continue
                gap = cc - (L + Ll) / 2
                foll = np.all(np.isfinite(cc) & (cc < 100)) and np.mean(np.abs(vl - v) < 1.5) >= 0.8 and np.all(gap > 1)
                free = np.all(~np.isfinite(cc) | (cc > 150))
                if not (foll or free):
                    continue
                lids, cnt = np.unique(z['lid'][sl], return_counts=True)
                rows.append((int(ids[a]) + blk * 10 ** 17, blk, float(np.mean(s)), float(z['ti'][w0 + W // 2]) / 5.0, int(np.median(ln)),
                             'follow' if foll else 'free', float(np.median(np.log(gap / v))) if foll else np.nan, float(np.mean(v)),
                             int(lids[np.argmax(cnt)]) if foll else -1))
    return pd.DataFrame(rows, columns=['tid', 'blk', 's', 't', 'lane', 'kind', 'logtg', 'v', 'lead'])


def decorrelate(w, col):
    cell = (w.s // 250).astype(int).astype(str) + '_' + w.blk.astype(str) + '_' + w.lane.astype(str)
    return w[col] - w.groupby(cell)[col].transform('mean')


def pair_corr(w, col, edges, diff_leader=False):
    """Correlation of a window value between two windows of the same track, by their distance apart."""
    x = w[col].to_numpy(); s = w.s.to_numpy(); t = w.t.to_numpy(); tid = w.tid.to_numpy(); ld = w.lead.to_numpy()
    order = np.argsort(tid, kind='stable'); x, s, t, tid, ld = x[order], s[order], t[order], tid[order], ld[order]
    cut = np.flatnonzero(np.diff(tid)) + 1
    I, J, G = [], [], []
    for g, (a, b) in enumerate(zip(np.r_[0, cut], np.r_[cut, len(tid)])):
        if b - a < 2:
            continue
        ii, jj = np.triu_indices(b - a, 1)
        I.append(ii + a); J.append(jj + a); G.append(np.full(len(ii), g))
    I, J, G = np.concatenate(I), np.concatenate(J), np.concatenate(G)
    if diff_leader:
        k = ld[I] != ld[J]; I, J, G = I[k], J[k], G[k]
    d = np.abs(s[J] - s[I]); dt = np.abs(t[J] - t[I])
    out = []
    ng = G.max() + 1
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (d >= lo) & (d < hi)
        if m.sum() < 30:
            continue
        xi, xj, g = x[I[m]], x[J[m]], G[m]
        r = np.corrcoef(np.r_[xi, xj], np.r_[xj, xi])[0, 1]
        # Bootstrap over tracks: weight each pair by how many times its track is drawn.
        bs = []
        for _ in range(200):
            cnt = np.bincount(rng.integers(0, ng, ng), minlength=ng)[g]
            if cnt.sum() < 10:
                continue
            ww = np.r_[cnt, cnt].astype(float); a_ = np.r_[xi, xj]; b_ = np.r_[xj, xi]
            ma, mb = np.average(a_, weights=ww), np.average(b_, weights=ww)
            cov = np.average((a_ - ma) * (b_ - mb), weights=ww)
            bs.append(cov / np.sqrt(np.average((a_ - ma) ** 2, weights=ww) * np.average((b_ - mb) ** 2, weights=ww)))
        out.append(dict(d_km=[lo / 1000, hi / 1000], pairs=int(m.sum()), tracks=int(len(np.unique(g))), r=round(float(r), 3),
                        ci=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                        dt_s=round(float(np.median(dt[m])), 1)))
    return out


def fit_decay(tab):
    d = np.array([np.mean(r['d_km']) for r in tab]); r = np.array([r['r'] for r in tab]); n = np.array([r['pairs'] for r in tab])
    f = lambda x, A, ell, F: A * np.exp(-x / ell) + F
    try:
        p, cov = curve_fit(f, d, r, p0=[0.4, 1.0, 0.2], bounds=([0, 0.05, 0.0], [1.5, 50, 1]), sigma=1 / np.sqrt(n))
        e = np.sqrt(np.diag(cov))
        return dict(A=round(float(p[0]), 3), e_folding_km=round(float(p[1]), 2), floor=round(float(p[2]), 3),
                    se=[round(float(x), 3) for x in e], r_at_0=round(float(p[0] + p[2]), 3))
    except Exception as ex:
        return dict(error=str(ex))


def highd_ends():
    """First and last 4 s of each highD car track: time gap when following steadily in both, speed when free in both."""
    rows = []
    for _, m in LX.recordings('highD').iterrows():
        rec = int(m.rec)
        d = LX.tracks('highD', rec)
        cls = LX.tracks_meta('highD', rec).set_index('id')['class']
        ids, st, en = LX.by_track(d)
        v = np.abs(d.vx.to_numpy()); dhw = d.dhw.to_numpy(); prec = d.prec.to_numpy(); xc = d.xc.to_numpy()
        pv = d.set_index(['frame', 'id']).vx.abs()
        for i, a, b in zip(ids, st, en):
            if cls.get(i) != 'Car' or b - a < 250:
                continue
            A = slice(a, a + 100); B = slice(b - 100, b)
            def state(sl):
                if np.median(v[sl]) < 15:
                    return None
                if np.all(prec[sl] > 0) and np.all((dhw[sl] > 1) & (dhw[sl] < 100)):
                    return ('follow', float(np.median(np.log(dhw[sl] / v[sl]))))
                if np.all((prec[sl] == 0) | (dhw[sl] > 150)):
                    return ('free', float(np.mean(v[sl])))
                return None
            sa, sb = state(A), state(B)
            if sa and sb and sa[0] == sb[0]:
                rows.append((rec, int(m.site), sa[0], sa[1], sb[1], abs(xc[b - 50] - xc[a + 50])))
    w = pd.DataFrame(rows, columns=['rec', 'site', 'kind', 'a', 'b', 'dist'])
    out = {}
    for kind, g in w.groupby('kind'):
        # Remove site-recording means so a recording's traffic state is not counted as persistence.
        a = g.a - g.groupby('rec').a.transform('mean'); b = g.b - g.groupby('rec').b.transform('mean')
        r = float(np.corrcoef(a, b)[0, 1])
        bs = []
        for _ in range(400):
            k = rng.integers(0, len(g), len(g)); bs.append(np.corrcoef(a.values[k], b.values[k])[0, 1])
        out[kind] = dict(tracks=len(g), r=round(r, 3), ci=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                         distance_m=round(float(g.dist.median()), 0),
                         by_site={int(s): round(float(np.corrcoef(a[g.site == s], b[g.site == s])[0, 1]), 3) for s in g.site.unique() if (g.site == s).sum() > 50})
    return out


def highsim():
    """HIGH-SIM sample (I-75, 90 tracks, congested): 20 s windows, log time gap when following (spacing column minus the
    leader's length), pairs on one track by distance, all and with different leaders. Feet converted to metres."""
    import zipfile, xml.etree.ElementTree as E
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    a = []
    with zipfile.ZipFile('/home/erikf/projects/personal/cars-data/truth/trajectories/human-20261031-highsim/1-90.xlsx') as z:
        with z.open('xl/worksheets/sheet1.xml') as f:
            for _, e in E.iterparse(f, events=('end',)):
                if e.tag == ns + 'row':
                    a.append([float(c.find(ns + 'v').text) if c.find(ns + 'v') is not None else np.nan for c in e]); e.clear()
    n = max(len(r) for r in a); a = np.array([r + [np.nan] * (n - len(r)) for r in a])
    a = a[np.isfinite(a[:, 0]) & np.isfinite(a[:, 1])]
    L = {i: np.nanmedian(a[a[:, 0] == i, 8]) * .3048 for i in np.unique(a[:, 0])}
    rows = []
    for i in np.unique(a[:, 0]):
        t = a[a[:, 0] == i]; t = t[np.argsort(t[:, 1])]
        dtm = np.median(np.diff(t[:, 1])); w = int(round(20 / dtm))
        y = t[:, 4] * .3048; v = t[:, 10] * .3048; ld = t[:, 13]; sp = t[:, 14] * .3048
        for w0 in range(0, len(t) - w + 1, w):
            sl = slice(w0, w0 + w)
            if np.median(v[sl]) < 3 or np.any(ld[sl] <= 0):
                continue
            gap = sp[sl] - np.array([L.get(x, np.nan) for x in ld[sl]])
            if np.any(~np.isfinite(gap)) or np.any(gap <= 0.5) or np.any(gap > 100):
                continue
            vals, cnt = np.unique(ld[sl], return_counts=True)
            rows.append((int(i), 0, float(np.mean(y[sl])), float(t[w0, 1]), 0, 'follow', float(np.median(np.log(gap / np.maximum(v[sl], 0.5)))),
                         float(np.mean(v[sl])), int(vals[np.argmax(cnt)])))
    w = pd.DataFrame(rows, columns=['tid', 'blk', 's', 't', 'lane', 'kind', 'logtg', 'v', 'lead'])
    w['x'] = w.logtg - w.groupby((w.s // 300).astype(int)).logtg.transform('mean')
    edges = np.array([0, 300, 600, 1000, 1500, 2500])
    return dict(tracks=int(w.tid.nunique()), windows=len(w), units_check=dict(v_median=round(float(w.v.median()), 2)),
                by_distance=pair_corr(w, 'x', edges), different_leaders=pair_corr(w, 'x', edges, diff_leader=True))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'highsim':
        r = highsim(); print(json.dumps(r, indent=0))
        res = json.load(open(os.path.join(RES, 'persist.json'))); res['highsim'] = r
        json.dump(res, open(os.path.join(RES, 'persist.json'), 'w'), indent=1); sys.exit(0)
    w = windows_ht()
    res = {'dlrht': {'windows': {k: int(v) for k, v in w.kind.value_counts().items()}, 'tracks': int(w.tid.nunique())}}
    edges = np.array([0, 250, 500, 1000, 1500, 2000, 3000, 4000, 5000, 6500])
    for kind, col in (('follow', 'logtg'), ('free', 'v')):
        k = w[w.kind == kind].copy()
        k['x'] = decorrelate(k, col)
        tab = pair_corr(k, 'x', edges)
        raw = pair_corr(k.assign(x=k[col]), 'x', edges)
        res['dlrht'][kind] = dict(by_distance=tab, decay_fit=fit_decay(tab), raw_without_cell_means=[(r['d_km'], r['r']) for r in raw],
                                  value_sd=round(float(k.x.std()), 4))
        if kind == 'follow':
            dl = pair_corr(k, 'x', edges, diff_leader=True)
            res['dlrht'][kind]['different_leaders'] = dict(by_distance=dl, decay_fit=fit_decay(dl))
        else:
            d0 = np.array([np.mean(r['d_km']) for r in tab if r['pairs'] > 200]); r0 = np.array([r['r'] for r in tab if r['pairs'] > 200])
            c = np.polyfit(d0, np.log(r0), 1)
            res['dlrht'][kind]['no_floor_fit'] = dict(r_at_0=round(float(np.exp(c[1])), 3), e_folding_km=round(float(-1 / c[0]), 2))
        print(kind, json.dumps(res['dlrht'][kind])[:1500], flush=True)
    # Mixed: is a driver who follows close also fast when free? Same track, any distance.
    f = w[w.kind == 'follow'].groupby('tid').logtg.mean(); v = w[w.kind == 'free'].groupby('tid').v.mean()
    both = pd.concat([f, v], axis=1, join='inner')
    res['dlrht']['tg_vs_free_speed_same_track'] = dict(tracks=len(both), r=round(float(np.corrcoef(both.logtg, both.v)[0, 1]), 3))
    res['highD_track_ends'] = highd_ends()
    print(json.dumps(res['highD_track_ends']))
    json.dump(res, open(os.path.join(RES, 'persist.json'), 'w'), indent=1)
