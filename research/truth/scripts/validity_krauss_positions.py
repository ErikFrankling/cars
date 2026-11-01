#!/usr/bin/env python3
"""SUMO 1.28 Krauss defaults at 50 km/h, same definitions as validity_dlrut_discharge.py.

Front-bumper crossing of a line at the stop line, headway per queue position, and the speed at
which the start of motion travels back through the stored queue. CPU only, no GPU.
Writes 04-krauss-positions.json next to the report.
"""
import json, subprocess, tempfile, xml.etree.ElementTree as ET
from pathlib import Path
from statistics import median
import numpy as np

OUT = Path(__file__).resolve().parents[1] / '04-krauss-positions.json'
SPEED, RED = 13.89, 30


def run(cmd, d):
    subprocess.run([str(c) for c in cmd], cwd=d, check=True, capture_output=True, timeout=120)


res = {}
with tempfile.TemporaryDirectory(prefix='validity-') as tmp:
    d = Path(tmp)
    (d / 'n.xml').write_text('<nodes><node id="a" x="0" y="0"/><node id="b" x="500" y="0" type="traffic_light"/><node id="c" x="1500" y="0"/></nodes>')
    (d / 'e.xml').write_text(f'<edges><edge id="e0" from="a" to="b" numLanes="1" speed="{SPEED}"/><edge id="e1" from="b" to="c" numLanes="1" speed="{SPEED}"/></edges>')
    run(['netconvert', '-n', 'n.xml', '-e', 'e.xml', '-o', 'net.xml', '--no-turnarounds', '--junctions.corner-detail', '0'], d)
    tls = ET.parse(d / 'net.xml').getroot().find('tlLogic').get('id')
    (d / 'a.xml').write_text(f'<additional><tlLogic id="{tls}" type="static" programID="p" offset="0"><phase duration="{RED}" state="r"/><phase duration="400" state="G"/></tlLogic>'
                             '<instantInductionLoop id="stop" lane="e0_0" pos="499.5" file="stop.xml"/></additional>')
    veh = ''.join(f'<vehicle id="q{i}" type="h" route="r" depart="0" departPos="{490-i*7.5}" departSpeed="0"/>' for i in range(30))
    (d / 'r.xml').write_text('<routes><vType id="h" carFollowModel="Krauss" sigma="0.5" speedDev="0" maxSpeed="60" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1"/><route id="r" edges="e0 e1"/>' + veh + '</routes>')
    for step in (1.0, 0.5, 0.1):
        pos, wave, spacing, react, stored = {}, [], [], [], []
        for seed in range(1, 11):
            run(['sumo', '-n', 'net.xml', '-r', 'r.xml', '-a', 'a.xml', '--step-length', step, '--end', 200, '--seed', seed, '--time-to-teleport', -1, '--no-step-log', 'true', '--no-warnings', 'true',
                 '--fcd-output', 'fcd.xml', '--device.fcd.period', step], d)
            t = sorted(float(x.get('time')) for x in ET.parse(d / 'stop.xml').getroot() if x.get('state') == 'enter')
            prev = RED
            for i, c in enumerate(t[:20], 1):
                if c < RED:
                    continue
                pos.setdefault(i, []).append(c - prev)
                prev = c
            first, stop = {}, {}
            for ts in ET.parse(d / 'fcd.xml').getroot():
                now = float(ts.get('time'))
                for x in ts:
                    i, v, p = x.get('id'), float(x.get('speed')), float(x.get('pos'))
                    if now < RED:
                        stop[i] = (p, v)
                    elif i not in first and v > 1:
                        first[i] = now
            ids = [f'q{i}' for i in range(30) if f'q{i}' in first and f'q{i}' in stop and stop[f'q{i}'][1] < .1]
            stored.append(len(ids))
            tm, dist = [first[i] for i in ids], [stop[ids[0]][0] - stop[i][0] for i in ids]
            wave.append(float(np.polyfit(tm, dist, 1)[0] * 3.6))
            spacing.append(float(np.mean(np.diff(dist))))
            react.append(tm[0] - RED)
        res[str(step)] = dict(headway_by_position={k: round(median(v), 3) for k, v in sorted(pos.items()) if k <= 8},
                              start_wave_kmh_median=round(median(wave), 1), start_wave_kmh_min_max=[round(min(wave), 1), round(max(wave), 1)],
                              spacing_m=round(median(spacing), 2), first_move_after_green_s=round(median(react), 2), stored_cars_median=median(stored), seeds=10)
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res))
