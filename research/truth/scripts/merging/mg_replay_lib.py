"""Follower rows shared by replay scripts."""
from mg_lib import *
def follower_rows(name):
    sc = pd.read_csv(EV / f'{name}.scalars.csv.gz'); z = np.load(EV / f'{name}.series.npz'); tau = z['tau']
    idx = sc['e'].values.astype(int); S = {k: z[k][idx] for k in ('edT', 'lag', 'fa', 'fv', 'fgap', 'fvl', 'ev', 'idF', 'fla')}
    rows = []
    for i in range(len(sc)):
        w = np.where(S['edT'][i] < 2.65)[0]; w = w[tau[w] <= 5]
        if not len(w): continue
        brk = np.where(np.diff(w) > 1)[0]; j0 = w[brk[-1] + 1] if len(brk) else w[0]
        if not (S['idF'][i, j0] == sc['F'].values[i]): continue
        for j in range(j0, min(j0 + 9, len(tau) - 2)):
            if S['fla'][i, j] != sc['new'].values[i]: continue
            rows.append((i, tau[j] - tau[j0], S['fa'][i, j + 2], S['lag'][i, j], S['fv'][i, j], S['ev'][i, j], S['fgap'][i, j], S['fvl'][i, j]))
    d = pd.DataFrame(rows, columns=['e', 't', 'a', 'lag', 'v', 've', 'g', 'vl']).dropna(subset=['a', 'v', 've', 'lag'])
    return d
