#!/usr/bin/env python3
"""Stop-line discharge of SUMO 1.28 Krauss on one lane, 40 stored cars, CPU only, no GPU.

Answers: is the 1.20 s headway in results/phenomena an artefact of the 120 km/h fixture?
Saturation headway is the median over queue positions 5-20, as HCM-style field counts use
positions after the first four. Start-up lost time is the sum of (h_i - h_s) over positions 1-4,
with h_1 measured from start of green. Writes 04-krauss-discharge.csv next to the report.
"""
import csv, subprocess, tempfile, xml.etree.ElementTree as ET
from pathlib import Path
from statistics import median, mean

OUT = Path(__file__).resolve().parents[1] / '04-krauss-discharge.csv'
SPEEDS = [8.33, 13.89, 19.44, 33.33]
STEPS = [1.0, 0.5, 0.1]
TAUS = [1.0, 1.5, 2.0]
RED = 30
LOOP = 499.0


def run(cmd, d):
    subprocess.run([str(c) for c in cmd], cwd=d, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


rows = []
with tempfile.TemporaryDirectory(prefix='validity-') as tmp:
    for speed in SPEEDS:
        d = Path(tmp) / f'v{speed}'
        d.mkdir()
        (d / 'n.xml').write_text('<nodes><node id="a" x="0" y="0"/><node id="b" x="500" y="0" type="traffic_light"/><node id="c" x="1500" y="0"/></nodes>')
        (d / 'e.xml').write_text(f'<edges><edge id="e0" from="a" to="b" numLanes="1" speed="{speed}"/><edge id="e1" from="b" to="c" numLanes="1" speed="{speed}"/></edges>')
        run(['netconvert', '-n', 'n.xml', '-e', 'e.xml', '-o', 'net.xml', '--no-turnarounds', '--junctions.corner-detail', '0', '--tls.left-green.time', '0'], d)
        tls = ET.parse(d / 'net.xml').getroot().find('tlLogic')
        (d / 'add.xml').write_text(f'<additional><tlLogic id="{tls.get("id")}" type="static" programID="p" offset="0"><phase duration="{RED}" state="r"/><phase duration="400" state="G"/></tlLogic>'
                                   f'<instantInductionLoop id="stop" lane="e0_0" pos="{LOOP}" file="stop.xml"/></additional>')
        for tau in TAUS:
            for step in STEPS:
                for seed in range(1, 11):
                    veh = ''.join(f'<vehicle id="q{i}" type="h" route="r" depart="0" departPos="{490-i*7.5}" departSpeed="0"/>' for i in range(40))
                    (d / 'r.xml').write_text(f'<routes><vType id="h" carFollowModel="Krauss" sigma="0.5" speedDev="0" maxSpeed="60" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="{tau}"/><route id="r" edges="e0 e1"/>{veh}</routes>')
                    run(['sumo', '-n', 'net.xml', '-r', 'r.xml', '-a', 'add.xml', '--step-length', step, '--end', 400, '--seed', seed, '--time-to-teleport', -1, '--no-step-log', 'true', '--no-warnings', 'true'], d)
                    t = sorted(float(x.get('time')) for x in ET.parse(d / 'stop.xml').getroot() if x.get('state') == 'leave')
                    if len(t) < 21:
                        continue
                    h = [t[0] - RED] + [b - a for a, b in zip(t, t[1:])]
                    hs = median(h[4:20])
                    rows.append(dict(speed=speed, tau=tau, step=step, seed=seed, n=len(t), first_s=round(h[0], 2),
                                     sat_headway=round(hs, 3), sat_flow=round(3600 / hs), lost=round(sum(x - hs for x in h[:4]), 2),
                                     mean_late=round(mean(h[4:20]), 3)))
with open(OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
agg = {}
for r in rows:
    agg.setdefault((r['speed'], r['tau'], r['step']), []).append(r)
print('speed_ms speed_kmh tau step n sat_headway sat_flow lost first')
for k, v in sorted(agg.items()):
    print(k[0], round(k[0] * 3.6), k[1], k[2], len(v), round(mean(x['sat_headway'] for x in v), 3), round(mean(x['sat_flow'] for x in v)), round(mean(x['lost'] for x in v), 2), round(mean(x['first_s'] for x in v), 2))
