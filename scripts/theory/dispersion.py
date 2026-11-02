# Are arrivals on a movement random, or bunched by copied trips? Variance over mean of 5-minute counts. Poisson gives 1. No simulation.
import sys, gzip, collections, statistics as st
import xml.etree.ElementTree as ET
net, t0, t1 = sys.argv[1], 7*3600, 8*3600
tt = {}
for ev, el in ET.iterparse(net, events=('end',)):
    if el.tag == 'edge' and el.get('function') != 'internal':
        l = el.find('lane')
        if l is not None: tt[el.get('id')] = float(l.get('length')) / float(l.get('speed'))
        el.clear()
    elif el.tag in ('junction', 'connection', 'tlLogic'): el.clear()
BIN = 300
for f in sys.argv[2:]:
    cnt = collections.defaultdict(lambda: collections.Counter())
    n = 0
    for ev, el in ET.iterparse(gzip.open(f), events=('end',)):
        if el.tag == 'vehicle':
            r = el.find('route')
            if r is not None:
                t = float(el.get('depart')); es = r.get('edges').split(); n += 1
                for a, b in zip(es, es[1:]):
                    t += 1.3 * tt.get(a, 0) + 3
                    if t0 <= t < t1: cnt[(a, b)][int((t - t0) // BIN)] += 1
                    if t > t1: break
            el.clear()
    bins = (t1 - t0) // BIN
    rows = []
    for k, c in cnt.items():
        v = [c.get(i, 0) for i in range(bins)]
        m = st.mean(v)
        if m * 12 >= 100: rows.append((m * 12, st.pvariance(v) / m))
    rows.sort()
    I = [r[1] for r in rows]
    print(f.split('/')[-1], 'vehicles', n, 'movements over 100/h', len(rows), 'var/mean p50 %.2f' % st.median(I) if I else '')
    for lo, hi in ((100, 200), (200, 400), (400, 800), (800, 9999)):
        s = [r[1] for r in rows if lo <= r[0] < hi]
        if s: print('  q %d-%d: n %d, median var/mean %.2f' % (lo, hi, len(s), st.median(s)))
