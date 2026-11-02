#!/usr/bin/env python3
"""Fold the per-node programs of one installation into one controller: same 90 s cycle, states concatenated, link indices renumbered.
Each node keeps its own valid program, so no green is lost to a neighbour it does not conflict with. Usage: merge_tls.py IN.net.xml OUT.net.xml"""
import sys, collections
from lxml import etree as E
t = E.parse(sys.argv[1]); r = t.getroot()
groups = collections.defaultdict(list)
for x in r.findall('tlLogic'):
    groups[x.get('id').split('__')[0]].append(x)
offs = {}; merged = 0; cycles = collections.Counter()
for g, ms in groups.items():
    if len(ms) == 1 and '__' not in ms[0].get('id'):
        continue
    width = 0; tl = []
    for m in ms:
        ph = [(float(p.get('duration')), p.get('state')) for p in m.findall('phase')]
        offs[m.get('id')] = (g, width); width += len(ph[0][1]); tl.append(ph)
    cyc = [sum(d for d, _ in ph) for ph in tl]
    L = max(cyc)
    # Cycles match by construction (90 s); a shorter one is stretched on its last phase so the two stay in step.
    for ph, c in zip(tl, cyc):
        if c < L:
            ph[-1] = (ph[-1][0] + L - c, ph[-1][1])
    cuts = sorted({round(sum(d for d, _ in ph[:i + 1]), 3) for ph in tl for i in range(len(ph))})
    def state(ph, t0):
        a = 0.0
        for d, s in ph:
            a += d
            if t0 < a - 1e-6:
                return s
        return ph[-1][1]
    keep = ms[0]; idx = list(r).index(keep)
    new = E.Element('tlLogic', id=g, type='static', programID=keep.get('programID', '0'), offset='0')
    prev = 0.0
    for c in cuts:
        E.SubElement(new, 'phase', duration=f'{c - prev:g}', state=''.join(state(ph, prev) for ph in tl)); prev = c
    new.tail = '\n'
    for m in ms:
        r.remove(m)
    r.insert(idx, new); merged += 1; cycles[L] += 1
for c in r.findall('connection'):
    tid = c.get('tl')
    if tid in offs:
        g, w = offs[tid]; c.set('tl', g); c.set('linkIndex', str(int(c.get('linkIndex')) + w))
t.write(sys.argv[2], encoding='UTF-8', xml_declaration=True)
print('merged controllers', merged, 'cycles', dict(cycles), 'total', len(r.findall('tlLogic')))
