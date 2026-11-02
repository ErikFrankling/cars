"""Yield rates by speed, relative speed and gap, with the matched-control baseline subtracted. Writes courtesy/events_summary.json."""
import sys, glob; sys.path.insert(0, 'research/truth/scripts')
from courtesy_lib import *

VB = [0, 2, 5, 10, 15, 25, 60]
GB = [-100, 0, 5, 10, 20, 40, 1000]
DB = [-100, -3, -1, 1, 3, 100]


def flag(df, col, gcol='gfl_4'):
    """Own braking opened at least 2 m or 15% of the follower-to-leader gap. The second test follows Yang et al.'s 15% rule."""
    thr = np.maximum(2.0, 0.15 * np.nan_to_num(df[gcol].values, nan=0.0))
    return (df[col].values >= thr)


def bins(x, b): return np.digitize(np.nan_to_num(x, nan=-1e9), b) - 1


def strata(d):
    """Follower speed, gap to its leader, relative speed to it, and what that leader does next: a control pair in the same cell has the same reason to brake."""
    return (bins(d['vf'].values, VB) * 1000 + bins(d['gfl_4'].values, [-1e9, 5, 10, 20, 40, 1e9]) * 100 + bins((d['vl_4'] - d['vf']).values, [-1e9, -1.5, 0, 1.5, 1e9]) * 10 + bins(d['dL_pre'].values, [-1e9, -3, -1, 1, 3, 1e9]))


def cell_table(ct):
    t = {}
    for s, c in ct.groupby('site'):
        g = pd.DataFrame(dict(k=strata(c), f_pre=flag(c, 'dF_pre'), f_post=flag(c, 'dF_post'), d_pre=c['dF_pre'].values, d_post=c['dF_post'].values)).groupby('k')
        m = g.mean(); m['n'] = g.size(); t[s] = m[m['n'] >= 8]
    return t


def block(ev, CT, label=''):
    """Observed minus expected: the expected value is the control mean of the event's own cell, at the event's own site."""
    o = {'n': int(len(ev))}
    if len(ev) < 15: return o
    rows = []
    for s, e in ev.groupby('site'):
        if s not in CT: continue
        k = strata(e); t = CT[s]; ok = np.isin(k, t.index.values)
        c = t.reindex(k[ok])
        rows.append(pd.DataFrame(dict(y_pre=flag(e, 'dF_pre')[ok], y_post=flag(e, 'dF_post')[ok], x_pre=e['dF_pre'].values[ok], x_post=e['dF_post'].values[ok], c_y_pre=c['f_pre'].values, c_y_post=c['f_post'].values, c_x_pre=c['d_pre'].values, c_x_post=c['d_post'].values)))
    if not rows: return o
    r = pd.concat(rows, ignore_index=True); o['matched'] = int(len(r))
    if len(r) < 15: return o
    rng = np.random.default_rng(11)
    diffs = r[['y_pre', 'y_post', 'x_pre', 'x_post']].astype(float).values - r[['c_y_pre', 'c_y_post', 'c_x_pre', 'c_x_post']].values
    bs = np.array([diffs[rng.integers(0, len(diffs), len(diffs))].mean(0) for _ in range(400)])
    ci = lambda i: [round(float(np.percentile(bs[:, i], 2.5)), 3), round(float(np.percentile(bs[:, i], 97.5)), 3)]
    o['open_before'] = dict(rate=round(float(r['y_pre'].mean()), 3), control=round(float(r['c_y_pre'].mean()), 3), excess=round(float(diffs[:, 0].mean()), 3), ci=ci(0))
    o['open_after'] = dict(rate=round(float(r['y_post'].mean()), 3), control=round(float(r['c_y_post'].mean()), 3), excess=round(float(diffs[:, 1].mean()), 3), ci=ci(1))
    o['holdback_before_m'] = dict(obs=round(float(r['x_pre'].mean()), 3), control=round(float(r['c_x_pre'].mean()), 3), excess=round(float(diffs[:, 2].mean()), 3), ci=ci(2))
    o['holdback_after_m'] = dict(obs=round(float(r['x_post'].mean()), 3), control=round(float(r['c_x_post'].mean()), 3), excess=round(float(diffs[:, 3].mean()), 3), ci=ci(3))
    y1 = flag(ev, 'dF_pre'); y2 = flag(ev, 'dF_post')
    o['coop'] = round(float(y1.mean()), 3); o['forced'] = round(float((~y1 & y2).mean()), 3); o['free'] = round(float((~y1 & ~y2).mean()), 3)
    o['lag0'] = q(ev['lag0']); o['lead0'] = q(ev['lead0']); o['vf'] = q(ev['vf'])
    o['alongside_at_-4'] = round(float((ev['lag_4'] < 0).mean()), 3)
    o['brake_when_yield'] = q(ev['minacc'][y1 | y2]); o['drop_when_yield'] = q(ev['v_drop'][y1 | y2])
    return o


def load(sites):
    E, K = [], []
    for s in sites:
        e = pd.read_csv(OUT / f'events_{s}.csv.gz'); k = pd.read_csv(OUT / f'controls_{s}.csv.gz')
        E.append(e[e['f_same'] == 1]); K.append(k)
    return pd.concat(E, ignore_index=True), pd.concat(K, ignore_index=True)


def main(sites):
    E, K = load(sites)
    out = {'sites': sites, 'events': int(len(E)), 'controls': int(len(K))}
    L = E[(E['L'] >= 0) & (E['l_same'] == 1) & E['gfl_4'].notna()]
    K2 = K[K['l_same'] == 1]; CT = cell_table(K2)
    out['by_site'] = {s: block(L[L['site'] == s], CT) for s in sites}
    out['all'] = block(L, CT)
    out['by_speed'] = {f'{VB[i]}-{VB[i+1]}': block(L[bins(L['vf'].values, VB) == i], CT) for i in range(len(VB) - 1)}
    dv = (L['vf'] - L['ve_4']).values
    out['by_relspeed_follower_minus_changer'] = {f'{DB[i]}..{DB[i+1]}': block(L[bins(dv, DB) == i], CT) for i in range(len(DB) - 1)}
    out['by_lag_gap_-4s'] = {f'{GB[i]}..{GB[i+1]}': block(L[bins(L['lag_4'].values, GB) == i], CT) for i in range(len(GB) - 1)}
    forced = {'i-80': (7, 6), 'us-101': (6, 5)}
    for site, (a, b) in forced.items():
        if site in sites: out['forced_' + site] = block(L[(L['site'] == site) & (L['old'] == a) & (L['new'] == b)], CT)
    if 'ht' in sites: out['forced_ht'] = block(L[(L['site'] == 'ht') & (((L['old'] == -9) & (L['new'] == -10)) | ((L['old'] == 10) & (L['new'] == 11)))], CT)
    # everything except these, at low speed
    urban = L[L['site'].isin(['lankershim', 'peachtree'])]; fw = L[~L['site'].isin(['lankershim', 'peachtree'])]
    out['ht_only_excluded_from_us'] = block(L[L['site'] != 'ht'], CT)
    out['urban'] = block(urban, CT); out['freeway'] = block(fw, CT)
    # event-locked mean acceleration against the control, in 1 s bins
    acols = [c for c in E.columns if c.startswith('a_')]
    prof = {}
    for lab, a, b in (('v<5', 0, 5), ('5-15', 5, 15), ('15+', 15, 60)):
        ev = L[(L['vf'] >= a) & (L['vf'] < b)]; ct = K2[(K2['vf'] >= a) & (K2['vf'] < b)]
        rng = np.random.default_rng(3); bs = []
        for _ in range(300):
            x = ev[acols].values[rng.integers(0, len(ev), len(ev))]; bs.append(np.nanmean(x, 0) - ct[acols].mean().values)
        bs = np.array(bs)
        prof[lab] = dict(n=int(len(ev)), bins=acols, excess=np.round(np.nanmean(ev[acols].values, 0) - ct[acols].mean().values, 3).tolist(), lo=np.round(np.percentile(bs, 2.5, 0), 3).tolist(), hi=np.round(np.percentile(bs, 97.5, 0), 3).tolist())
    out['accel_profile'] = prof
    # smallest accepted gaps at the label crossing, as the physically observed lower bound
    mins = {}
    for i in range(len(VB) - 1):
        m = L[bins(L['ve0'].values, VB) == i]
        mins[f'{VB[i]}-{VB[i+1]}'] = {'lag': q(m['lag0'], (1, 5, 25, 50)), 'lead': q(m['lead0'], (1, 5, 25, 50)), 'lag_tg': q(m['lag0'] / np.maximum(m['vf0'], .1), (1, 5, 25, 50)), 'lead_tg': q(m['lead0'] / np.maximum(m['ve0'], .1), (1, 5, 25, 50))}
    out['accepted_gap_by_speed'] = mins
    # logistic: did the follower open the gap before the crossing, controlling for the state at -4 s
    F = L[['vf', 've_4', 'lag_4', 'gfl_4', 'dL_pre']].copy(); F['y'] = flag(L, 'dF_pre').astype(float); F['site'] = L['site'].values; F['F'] = L['F'].values
    F = F.dropna(); F = F[(F['lag_4'] > -30) & (F['lag_4'] < 80) & (F['gfl_4'] < 100)]
    X = np.c_[F['vf'] / 10, (F['vf'] - F['ve_4']) / 3, F['lag_4'] / 10, F['gfl_4'] / 10, F['dL_pre'] / 5]
    out['logit_open_before'] = dict(n=int(len(F)), coef=logit_boot(X, F['y'].values, F['site'].astype(str) + F['F'].astype(str), ['v_per10', 'closing_per3', 'lag_per10m', 'gapFL_per10m', 'leader_pull_per5m'], n=100))
    return out


if __name__ == '__main__':
    sites = sys.argv[2:]
    save(sys.argv[1], main(sites))
