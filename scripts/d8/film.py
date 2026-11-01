#!/usr/bin/env python3
"""The D8 clips. Each takes the GPU lock for itself. Usage: film.py [--only name,name] [--preview]
Real runs, no hidden teleports: time_to_teleport 0, the auditor on, its count on the HUD."""
import argparse, fcntl, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NETS = ROOT / 'research/truth/fig/09-nets'
OUT = Path('/home/erikf/projects/personal/cars-data/videos/gallery/d8')
WORK = Path('/tmp/d8/filmwork')


def demand(net, d, mix, end, seed=0, typ='av', ctl=None):
    rou = WORK / f'{net}_{d}_{mix}_{seed}_{typ}.rou.xml'
    p = NETS / f'{net}.net.xml'
    cmd = [sys.executable, str(ROOT / 'scripts/d8/demand.py'), '--net', str(p), '--out', str(rou), '--demand', str(d), '--mix', mix, '--end', str(end), '--seed', str(seed), '--type', typ]
    subprocess.run(cmd, check=True)
    return p, rou


def record(cars, name, net, rou, begin, end, sim_end, title, sub, cj='B1', extra=(), overlay='events', mpp=0.075, speed=1.0, w=1920, h=1080, junction='B1', preview=False, out=None):
    out = out or OUT / f'{name}.mp4'
    cmd = [str(cars), 'record' if not preview else 'shot', '--net', str(net), '--routes', str(rou), '--dt', '0.1', '--sim-end', str(sim_end), '--time-to-teleport', '0',
           '--junction', junction, '--metres-per-pixel', str(mpp), '--cj', cj, '--overlay', overlay, '--color', 'paint', '--width', str(w), '--height', str(h),
           '--title', title, '--subtitle', sub, *map(str, extra)]
    if preview:
        cmd += ['--at', f'{begin + 3},{begin + 6}', '--out', str(WORK / f'{name}.png')]
    else:
        cmd += ['--begin', str(begin), '--end', str(end), '--speed', str(speed), '--out', str(out)]
    f = open('/tmp/cars-gpu.lock', 'a')
    if not preview:
        fcntl.flock(f, fcntl.LOCK_EX)
    r = subprocess.run(cmd, capture_output=True, text=True)
    fcntl.flock(f, fcntl.LOCK_UN)
    print(name, r.returncode, r.stderr.strip().splitlines()[-1][:160] if r.stderr.strip() else '', flush=True)
    if r.returncode:
        print(r.stderr[-1500:])
    return out


def stack(paths, out):
    inputs = []
    for p in paths:
        inputs += ['-i', str(p)]
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-threads', '2', '-filter_threads', '2', *inputs, '-filter_complex', ''.join(f'[{i}:v]' for i in range(len(paths))) + f'hstack=inputs={len(paths)}[v]', '-map', '[v]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'veryfast', '-threads', '2', '-movflags', '+faststart', str(out)], check=True)
    for p in paths:
        Path(p).unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--cars', default=str(ROOT / 'target/release/cars'))
    ap.add_argument('--preview', action='store_true')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(',')))
    want = lambda n: not only or n in only
    c = a.cars
    pv = a.preview
    if want('weave'):
        net, rou = demand('j1', 5000, 'T', 360)
        record(c, 'weave', net, rou, 300, 325, 360, 'No signal: streams thread through each other', '5000 veh/h, 1 lane each way, Level A, half speed, auditor on', speed=0.5, mpp=0.06, preview=pv)
    if want('weave_turns'):
        net, rou = demand('j2', 5200, 'M', 360)
        record(c, 'weave_turns', net, rou, 300, 330, 360, 'No signal, 2 lanes with 20% turns', '5200 veh/h, Level A, real time, auditor on', mpp=0.08, preview=pv)
    if want('versus'):
        net, rou = demand('j2', 5200, 'M', 400)
        hroute = demand('j2', 5200, 'M', 400, typ='human')[1]
        parts = []
        common = dict(mpp=0.16, w=640, h=720, overlay='grants', preview=pv)
        parts.append(record(c, 'v_free', net, rou, 300, 360, 400, 'No signal', '+19% capacity against a fair signal', extra=['--cj-warm', '0'], out=WORK / 'v_free.mp4', **common))
        parts.append(record(c, 'v_sig', net, rou, 300, 360, 400, 'AV signal', 'same cars, same arrivals', extra=['--cj-mode', 'signal', '--cj-sig-max', '30', '--cj-sig-gap', '1'], out=WORK / 'v_sig.mp4', **common))
        parts.append(record(c, 'v_hum', net, hroute, 300, 360, 400, 'Human signal', 'tau 1.4 s, 4 s lost per switch', extra=['--cj-mode', 'signal', '--cj-human', '--cj-sig-max', '60', '--cj-sig-gap', '1'], out=WORK / 'v_hum.mp4', **common))
        if not pv:
            stack(parts, OUT / 'versus_signal.mp4')
    if want('loss'):
        net, rou = demand('j2', 4000, 'M', 400)
        record(c, 'loss_70pct', net, rou, 300, 340, 400, '70% of messages lost', 'a lost grant costs a slot, never safety. 4000 veh/h, Level A', extra=['--cj-loss', '0.7'], overlay='grants,channel,events', mpp=0.1, preview=pv)
    if want('crash'):
        net, rou = demand('j2', 3000, 'M', 400)
        record(c, 'coordinator_crash', net, rou, 305, 375, 400, 'Coordinator down from 310 to 350 s', 'grants stand, everyone stops, oldest goes first with the box to itself', extra=['--cj-crash', '310,350'], overlay='grants,channel,events', mpp=0.1, preview=pv)
    if want('slots'):
        net, rou = demand('j2', 4200, 'M', 400)
        record(c, 'paths_and_slots', net, rou, 300, 330, 400, 'Planned paths and granted slots', '4200 veh/h, 2 lanes with turns, half speed', overlay='grants,paths,events', speed=0.5, mpp=0.07, preview=pv)
    if want('exit'):
        net, rou = demand('j2', 3000, 'M', 400)
        record(c, 'exit_blocked', net, rou, 305, 345, 400, 'Exit closed: the box stays clear', 'exit to the east closed from 250 s, credits and point-of-no-return check on', extra=['--cj-exit-fault', 'B1C1:250:800'], overlay='grants,events', mpp=0.1, preview=pv)
        record(c, 'exit_blocked_unprotected', net, rou, 305, 345, 400, 'Same, with the exit checks off', 'the box locks up and bodies collide. This is the test that detects it', extra=['--cj-exit-fault', 'B1C1:250:800', '--cj-no-exit-check'], overlay='grants,events', mpp=0.1, preview=pv)
    if want('stall'):
        net, rou = demand('j2', 3000, 'M', 400)
        record(c, 'stall_level_a', net, rou, 260, 330, 400, 'A car stalls in the box, Level A', 'an injected failure. The specified rule does not cover this', extra=['--cj-stall-rate', '120', '--cj-warm', '250'], overlay='grants,events', mpp=0.09, preview=pv)
        record(c, 'stall_level_b', net, rou, 260, 330, 400, 'A car stalls in the box, Level B', 'the stall-tolerant margin. Fewer collisions, less capacity', extra=['--cj-stall-rate', '120', '--cj-warm', '250', '--cj-level-b'], overlay='grants,events', mpp=0.09, preview=pv)
    if want('grid'):
        js = ','.join(f'{x}{y}' for x in 'BCD' for y in '123')
        net, rou = demand('grid2', 20000, 'M', 300)
        record(c, 'grid', net, rou, 200, 240, 300, '9 signal-free junctions', '20000 veh/h offered, 2 lanes, Level A', cj=js, junction='C2', extra=['--cj-warm', '0'], overlay='events', mpp=0.45, preview=pv)
        net, rou = demand('grid2', 24000, 'M', 300)
        parts = [record(c, 'g_free', net, rou, 230, 270, 300, 'Past critical load, no metering', '24000 veh/h offered. The auditor finds contacts', cj=js, junction='C2', overlay='events', mpp=0.8, w=960, h=1080, preview=pv, out=WORK / 'g_free.mp4'),
                 record(c, 'g_meter', net, rou, 230, 270, 300, 'Same demand, metered at the edge', 'at most 240 cars inside, the rest wait outside', cj=js, junction='C2', extra=['--cj-meter', '240'], overlay='events', mpp=0.8, w=960, h=1080, preview=pv, out=WORK / 'g_meter.mp4')]
        if not pv:
            stack(parts, OUT / 'grid_overload_metering.mp4')


if __name__ == '__main__':
    main()
