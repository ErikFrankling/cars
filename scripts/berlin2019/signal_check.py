#!/usr/bin/env python3
"""A net's signal programs against Hamburg's measured cycles and green shares (report 26): cycle 73/90/110 s, green share .15/.31/.6, weekdays 07-19. signal_check.py NET..."""
import sys
from xml.etree.ElementTree import iterparse
import numpy as np
for net in sys.argv[1:]:
    cyc, top, share = [], [], []
    for _, el in iterparse(net, events=('end',)):
        if el.tag == 'tlLogic':
            ph = [(float(p.get('duration')), p.get('state'), p.get('maxDur')) for p in el.findall('phase')]
            c = sum(a for a, _, _ in ph)
            cyc.append(c)
            top.append(sum(float(m) if m else a for a, _, m in ph))
            for i in range(len(ph[0][1])):
                g = sum(a for a, s, _ in ph if s[i] in 'Gg')
                if g > 0:
                    share.append(g / c)
            el.clear()
        elif el.tag in ('edge', 'connection', 'junction'):
            el.clear()
    q = lambda v: [round(float(x), 2) for x in np.percentile(v, [10, 50, 90])]
    print(net.split('/')[-2], 'controllers', len(cyc), 'nominal cycle', q(cyc), 'largest possible', q(top), 'green share', q(share))
