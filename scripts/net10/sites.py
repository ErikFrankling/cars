#!/usr/bin/env python3
"""Draws the same place in several nets, with the register's lanterns. Usage: sites.py OUT_DIR TAG=NET ... Report data-hunt/10."""
import sys, os
os.environ['MPLCONFIGDIR'] = '/tmp/net10-mpl'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
SITES = {'norr_malarstrand': (59.3282, 18.0274, 170, 'Norr Mälarstrand at Rålambshovsleden'), 'fleminggatan': (59.33448, 18.03253, 130, "S:t Eriksgatan x Fleminggatan"),
         'fridhemsplan': (59.33213, 18.0312, 140, 'Fridhemsplan'), 'tegelbacken': (59.32856, 18.06118, 170, 'Tegelbacken'), 'sankt_eriksplan': (59.3397, 18.0372, 130, 'Sankt Eriksplan'), 'sveavagen': (59.3405, 18.0585, 170, 'Sveavägen x Odengatan')}
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
nets = [a.split('=') for a in sys.argv[2:]]
reg = register(); N = [(t, load_net(p)) for t, p in nets]
rows = []
for key, (la, lo, rad, title) in SITES.items():
    fig, axs = plt.subplots(1, len(N), figsize=(5.2 * len(N), 5.4), squeeze=False)
    for ax, (tag, n) in zip(axs[0], N):
        fwd, back = tf_from_location(n['location'])
        cx, cy = fwd(lo, la)
        tl_there = set(); short = 0; ne = 0
        for e, d in n['edges'].items():
            for l in d['lanes']:
                s = np.array(l['shape'])
                if np.min(np.hypot(s[:, 0] - cx, s[:, 1] - cy)) > rad * 1.2:
                    continue
                pas = passenger(l)
                col = '#b0413e' if pas and l['length'] < 7.5 else ('#e0a030' if pas and l['length'] < 25 else ('#9db8d9' if pas else '#c9c9c9'))
                ax.plot(s[:, 0], s[:, 1], color=col, lw=2.2 if pas and l['length'] < 25 else 1.2, solid_capstyle='butt', zorder=2)
                if pas and np.min(np.hypot(s[:, 0] - cx, s[:, 1] - cy)) <= rad:
                    ne += 1; short += l['length'] < 7.5
        cmap = plt.get_cmap('tab10'); idx = {}
        for c in n['conns']:
            if not c['tls'] or c['frm'] not in n['edges']:
                continue
            j = n['edges'][c['frm']]['to']
            if j not in n['junctions']:
                continue
            x, y = n['junctions'][j]['x'], n['junctions'][j]['y']
            if math.hypot(x - cx, y - cy) > rad:
                continue
            tl_there.add(c['tls'])
            k = idx.setdefault(c['tls'], len(idx))
            ax.scatter([x], [y], s=70, color=cmap(k % 10), zorder=4, edgecolor='k', lw=.5)
        here = set()
        for i, v in reg.items():
            for p in v['veh']:
                x, y = fwd(*p)
                if abs(x - cx) < rad and abs(y - cy) < rad:
                    ax.scatter([x], [y], marker='x', s=16, color='k', zorder=5); here.add(i)
        ax.set_xlim(cx - rad, cx + rad); ax.set_ylim(cy - rad, cy + rad); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f'{tag}: {len(tl_there)} controllers, register {len(here)}, lanes <7.5 m: {short}', fontsize=10)
        rows.append(dict(site=key, net=tag, controllers=len(tl_there), register=len(here), lanes=ne, under_7_5=short))
    fig.suptitle(f'{title}. Dots: signal nodes, colour = controller. Crosses: register vehicle lanterns. Red lane <7.5 m, orange <25 m, grey bus-only.', fontsize=10)
    fig.tight_layout(); fig.savefig(out / f'{key}.png', dpi=110); plt.close(fig)
(out / 'sites.json').write_text(json.dumps(rows, indent=0))
for r in rows:
    print(r)
