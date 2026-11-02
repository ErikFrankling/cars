#!/usr/bin/env python3
"""The debugging tools on a small signalised crossing, on llvmpipe: --why must not change a run, reasons must be true, and each tool must produce its files."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dbg.run import K, Run, lanes_of, pos_of, speeds_of, trips_of  # noqa: E402

CARS = str(ROOT / 'target/release/cars')
TOOLS = str(ROOT / 'scripts/cars_debug.py')
ENV = dict(os.environ, CARS_ADAPTER='llvmpipe', LP_NATIVE_VECTOR_WIDTH='128', VK_ICD_FILENAMES='/run/opengl-driver/share/vulkan/icd.d/lvp_icd.x86_64.json', CARS_BIN=CARS)
NODES = '<nodes><node id="c" x="0" y="0" type="traffic_light"/><node id="w" x="-400" y="0"/><node id="e" x="400" y="0"/><node id="n" x="0" y="400"/><node id="s" x="0" y="-400"/></nodes>'
EDGES = ('<edges><edge id="wc" from="w" to="c" numLanes="2" speed="13.89"/><edge id="cw" from="c" to="w" numLanes="2" speed="13.89"/><edge id="ec" from="e" to="c" numLanes="2" speed="13.89"/>'
         '<edge id="ce" from="c" to="e" numLanes="2" speed="13.89"/><edge id="nc" from="n" to="c" speed="13.89"/><edge id="cn" from="c" to="n" speed="13.89"/><edge id="sc" from="s" to="c" speed="13.89"/><edge id="cs" from="c" to="s" speed="13.89"/></edges>')
ROUTES = ('<routes><vType id="t" vClass="passenger" sigma="0.5" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1"/>'
          '<flow id="a" type="t" from="wc" to="ce" begin="0" end="240" vehsPerHour="1500" departLane="best"/><flow id="b" type="t" from="wc" to="cn" begin="0" end="240" vehsPerHour="400" departLane="0"/>'
          '<flow id="c" type="t" from="ec" to="cw" begin="0" end="240" vehsPerHour="1000" departLane="best"/><flow id="d" type="t" from="nc" to="cs" begin="0" end="240" vehsPerHour="500"/></routes>')


def sh(*cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=ENV)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def tool(name, *args):
    return sh(sys.executable, TOOLS, name, *args)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / 'n.nod.xml').write_text(NODES)
        (d / 'n.edg.xml').write_text(EDGES)
        (d / 'r.xml').write_text(ROUTES)
        sh('netconvert', '-n', d / 'n.nod.xml', '-e', d / 'n.edg.xml', '-o', d / 'net.xml', '--no-warnings', '--no-turnarounds')
        common = ['run', '--net', d / 'net.xml', '--routes', d / 'r.xml', '--dt', 1, '--end', 200]
        sh(CARS, *common, '--trace', d / 'plain.trace')
        sh(CARS, *common, '--trace', d / 'f.trace', '--why', '--edge-csv', d / 'edges.csv', '--edge-interval', 60)
        assert (d / 'plain.trace').read_bytes() == (d / 'f.trace').read_bytes(), '--why changed the simulation'
        print('ok  --why leaves the trace byte for byte the same')
        run = Run(str(d / 'f.trace'))
        checked = dict(leader=0, signal=0, gone=0)
        for i in run.window(40, 200):
            rec, why = run.read(i)
            trips, lanes, pos, v = trips_of(rec), lanes_of(rec), pos_of(rec), speeds_of(rec)
            where = {int(t): k for k, t in enumerate(trips)}
            for k in range(len(rec)):
                if why['decider'][k] == K['leader'] and why['blame'][k] < 0x40000000:
                    o = where.get(int(why['blame'][k]))
                    # The plan is from the start of the tick and positions from its end, so a leader may have just left the lane.
                    # Or arrived in this tick, and then it has no record.
                    if o is None:
                        checked['gone'] += 1
                    elif lanes[o] == lanes[k]:
                        assert pos[o] > pos[k], 'leader blame is behind the car it holds'
                        checked['leader'] += 1
                if why['decider'][k] == K['signal'] and why['first_link'][k] != 0xffffffff:
                    from dbg.run import link_state
                    assert link_state(run, i, why['first_link'][k]) in 'ryYu', 'held by a signal showing green'
                    checked['signal'] += 1
                assert why['decider'][k] != K['dawdle'], 'dawdling reported as the decider'
        assert checked['leader'] > 100 and checked['signal'] > 20 and checked['gone'] < 0.1 * checked['leader'], checked
        print('ok  reasons agree with positions and signal colours', checked)
        rec, why = run.read(run.frame_at(150))
        held = np.nonzero(speeds_of(rec) < 0.1)[0]
        car = run.name(trips_of(rec)[held[0]])
        assert 'decided by' in tool('why', '--trace', d / 'f.trace', '--car', car, '--at', 150)
        tool('why', '--trace', d / 'f.trace', '--car', car, '--begin', 100, '--end', 180, '--out', d / 'w')
        assert (d / 'w/timeline.png').exists() and (d / 'w/timeline.csv').exists()
        assert 'FIRST CAUSE' in tool('jam', '--trace', d / 'f.trace', '--car', car, '--at', 150)
        tool('jam', '--trace', d / 'f.trace', '--seeds', '--stride', 5, '--min-wait', 10, '--out', d / 'j')
        assert (d / 'j/seeds.png').exists() and json.loads((d / 'j/seeds.json').read_text())['frames'] > 0
        tool('tsd', '--trace', d / 'f.trace', '--route', 'wc,ce', '--by-lane', '--bin-t', 30, '--out', d / 't')
        assert (d / 't/tsd.png').exists() and (d / 't/heat.png').exists()
        tool('junction', '--trace', d / 'f.trace', '--junction', 'c', '--out', d / 'jn')
        report = json.loads((d / 'jn/junctions.json').read_text())[0]
        assert report['cars'] > 20 and report['blocked_by'].get('signal', 0) > 0, report
        assert (d / 'jn/junctions.png').exists()
        tool('dist', '--a', d / 'f.trace', '--b', d / 'f.trace', '--out', d / 'dd')
        same = json.loads((d / 'dd/dist.json').read_text())
        assert all(same[m]['distance'] == 0 for m in ('speed', 'acceleration', 'braking', 'gap', 'headway')), 'a run is not at distance 0 from itself'
        (d / 'ref.csv').write_text('sensor,edge,time,flow_vph,speed_kmh\n' + ''.join(f'S{e},{e},{t},600,30\n' for e in ('wc', 'ce', 'cn', 'cw') for t in (0, 60, 120)))
        tool('compare', '--sim', d / 'edges.csv', '--ref', d / 'ref.csv', '--net', d / 'f.trace.net.json', '--out', d / 'c')
        assert (d / 'c/map.png').exists()
        print('ok  every tool ran and wrote its files')
    print('ALL OK')


if __name__ == '__main__':
    main()
