#!/usr/bin/env python3
"""Same pair measures on the invented programs of map m12, no simulation: through connection, short link, through connection."""
import collections
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from rcommon import *

NET = B19 / 'district/m12/net.net.xml'
tls, conns, edges, lens = {}, collections.defaultdict(list), {}, {}
for ev, el in ET.iterparse(NET, events=('end',)):
    if el.tag == 'tlLogic':
        tls[el.get('id')] = dict(offset=float(el.get('offset', 0)), ph=[(float(p.get('duration')), p.get('state')) for p in el.findall('phase')])
        el.clear()
    elif el.tag == 'edge' and el.get('function') != 'internal':
        l = el.find('lane')
        edges[el.get('id')] = dict(to=el.get('to'), fr=el.get('from'), L=float(l.get('length')), v=float(l.get('speed')), n=len(el.findall('lane')), type=el.get('type', ''))
        el.clear()
    elif el.tag == 'connection':
        if el.get('tl') and not el.get('from', '').startswith(':'):
            conns[el.get('from')].append((el.get('to'), el.get('tl'), int(el.get('linkIndex')), el.get('dir')))
        el.clear()


def greens(t, i):
    """Green windows of link i over one cycle, and the cycle."""
    tot, out, on = 0.0, [], None
    for d, st in t['ph']:
        g = st[i] in 'Gg'
        if g and on is None:
            on = tot
        if not g and on is not None:
            out.append((on, tot))
            on = None
        tot += d
    if on is not None:
        if out and out[0][0] == 0:
            out[0] = (on - tot, out[0][1])
        else:
            out.append((on, tot))
    return out, tot


def gmask(w, C, res=1.0):
    n = int(C)
    m = np.zeros(n, bool)
    for a, b in w:
        m[np.arange(int(a), int(b)) % n] = True
    return m


rows = []
for e, cl in conns.items():
    for to, tl, li, d in cl:
        if d != 's' or to not in conns or tl not in tls:
            continue
        L = edges[to]['L']
        if L >= 150:
            continue
        for to2, tl2, li2, d2 in conns[to]:
            if d2 != 's' or tl2 not in tls:
                continue
            ga, Ca = greens(tls[tl], li)
            gb, Cb = greens(tls[tl2], li2)
            if not ga or not gb or Ca < 10 or Cb < 10:
                continue
            same_c = abs(Ca - Cb) <= 1
            st_a, st_b = min(a for a, _ in ga), min(a for a, _ in gb)
            rec = dict(link=L, one=tl == tl2, same_cycle=same_c, cycle_a=Ca, cycle_b=Cb, offset=((st_b - st_a + Ca / 2) % Ca) - Ca / 2 if same_c else np.nan)
            if same_c:
                ma, mb = gmask(ga, Ca), gmask(gb, Ca)
                if ma.sum():
                    rec['overlap'] = (ma & mb).sum() / ma.sum()
                    rec['feed'] = (ma & ~mb).sum()
                    ends = max(b for _, b in ga)
                    t = 0
                    while t < Ca and mb[(int(ends) + t) % int(Ca)]:
                        t += 1
                    rec['tail'] = t
                    need = (L + 15) / 8.3
                    rec['clears'] = (t >= need) or (rec['feed'] * .5 <= max(L, 7.5) / 7.5)
            rows.append(rec)
a = pd.DataFrame(rows).drop_duplicates()
a['band'] = pd.cut(a.link, [0, 30, 50, 150], labels=['lt30', '30_50', '50_150'], right=False)
print(len(a), a.groupby('band', observed=True).agg(n=('link', 'size'), one=('one', 'mean'), same=('same_cycle', 'mean'), cyc=('cycle_a', 'median'), off25=('offset', lambda x: x.quantile(.25)), off=('offset', 'median'), off75=('offset', lambda x: x.quantile(.75)), overlap=('overlap', 'median'), together=('overlap', lambda x: (x >= .8).mean()), opposed=('overlap', lambda x: (x <= .2).mean()), feed=('feed', 'median'), feed90=('feed', lambda x: x.quantile(.9)), tail=('tail', 'median'), clears=('clears', 'mean')).round(2).T.to_string())
print('programs', len(tls), 'phases by state count', collections.Counter(len(t['ph']) for t in tls.values()).most_common(5))
