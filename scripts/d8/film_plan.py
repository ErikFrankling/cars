#!/usr/bin/env python3
"""Clips for the planned approach (research/truth/09d). Same arrivals old and new. Usage: film_plan.py [--only a,b] [--out dir].
Uses CARS_ADAPTER if set (llvmpipe on the worker) and the GPU lock otherwise."""
import argparse, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runs import GATE

ROOT = Path(__file__).resolve().parents[2]
NETS = ROOT / 'research/truth/fig/09-nets'
CARS = ROOT / 'target/release/cars'
WORK = Path('/tmp/d8/filmplan')


def demand(net, d, mix, end, seed=0):
    rou = WORK / f'{net}_{d}_{mix}_{seed}.rou.xml'
    p = NETS / f'{net}.net.xml'
    subprocess.run([sys.executable, str(ROOT / 'scripts/d8/demand.py'), '--net', str(p), '--out', str(rou), '--demand', str(d), '--mix', mix, '--end', str(end), '--seed', str(seed)], check=True)
    return p, rou


def record(out, net, rou, begin, end, plan, title, sub, overlay, mpp, w, h, sim_end=None, seed=0, junction='B1', cj='B1', keep_seed=False, center=None, teleport=False):
    cmd = [str(CARS), 'record', '--net', str(net), '--routes', str(rou), '--dt', '0.1', '--sim-end', str(sim_end or end + 2), '--time-to-teleport', '120' if teleport else '0',
           '--metres-per-pixel', str(mpp), '--seed', str(seed), '--overlay', overlay, '--color', 'speed', '--width', str(w), '--height', str(h),
           '--title', title, '--subtitle', sub, '--begin', str(begin), '--end', str(end), '--speed', '1', '--fps', '25', '--out', str(out)]
    if teleport:
        cmd += ['--ignore-junction-blocker', '20']
    if junction:
        cmd += ['--junction', junction]
    if center:
        cmd += ['--center', center]
    if cj:
        cmd += ['--cj', cj, '--cj-plan', 'off' if plan == 'sig' else plan]
    GATE.enter()
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(out.name, r.returncode, r.stderr.strip().splitlines()[-1][:160] if r.stderr.strip() else '', flush=True)
    if r.returncode:
        print(r.stderr[-1500:], flush=True)
        raise SystemExit(1)


def stack(parts, out):
    inputs = []
    for p in parts:
        inputs += ['-i', str(p)]
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-threads', '2', '-filter_threads', '2', *inputs, '-filter_complex', ''.join(f'[{i}:v]' for i in range(len(parts))) + f'vstack=inputs={len(parts)}[v]',
                    '-map', '[v]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'veryfast', '-threads', '2', str(out)], check=True)
    for p in parts:
        Path(p).unlink()


def hstack(parts, out):
    inputs = []
    for p in parts:
        inputs += ['-i', str(p)]
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-threads', '2', '-filter_threads', '2', *inputs, '-filter_complex', ''.join(f'[{i}:v]' for i in range(len(parts))) + f'hstack=inputs={len(parts)}[v]',
                    '-map', '[v]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'veryfast', '-threads', '2', str(out)], check=True)
    for p in parts:
        Path(p).unlink()


def versus(name, d, mix, begin, end, out, mpp=0.31):
    net, rou = demand('j2', d, mix, end + 5)
    a = WORK / f'{name}_old.mp4'
    b = WORK / f'{name}_new.mp4'
    mix_text = {'M': '20% turns', 'H': '35% turns', 'T': 'straight only'}[mix]
    record(a, net, rou, begin, end, 'off', 'Today: drive flat out, brake late', f'{d} veh/h, 2 lanes, {mix_text}, no signal, same arrivals', 'brake', mpp, 1920, 540)
    record(b, net, rou, begin, end, 'route', 'Planned: everyone knows everyone\'s arrival', 'colour is speed, red is braking over 1 m/s2, bright over 2.5', 'brake', mpp, 1920, 540)
    stack([a, b], out / f'{name}.mp4')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--out', default='/home/erikf/projects/personal/cars-data/videos/gallery/d8/plan')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(',')))
    want = lambda n: not only or n in only
    if want('versus_3000'):
        versus('versus_3000', 3000, 'M', 100, 160, out)
    if want('versus_5200'):
        versus('versus_5200', 5200, 'M', 180, 240, out)
    if want('arrivals_3000'):
        net, rou = demand('j2', 3000, 'M', 165)
        record(out / 'arrivals_3000.mp4', net, rou, 100, 160, 'route', 'Every car says when it will reach the line, to the millisecond',
               '3000 veh/h, 2 lanes, 20% turns. Slots fill up long before the cars get there', 'brake,arrivals', 0.31, 1920, 1080)
    if want('grid_24000'):
        p = NETS / 'grid2.net.xml'
        rou = WORK / 'grid2_24000.rou.xml'
        subprocess.run([sys.executable, str(ROOT / 'scripts/d8/demand.py'), '--net', str(p), '--out', str(rou), '--demand', '24000', '--mix', 'M', '--end', '400', '--seed', '0'], check=True)
        js = ','.join(f'{x}{y}' for x in 'BCD' for y in '123')
        parts = []
        for plan, title, sub in (('off', 'Today, overloaded grid', '24000 veh/h offered, each junction on its own'), ('route', 'Planning across junctions', 'storage credit: a slot here waits for room there')):
            f_ = WORK / f'grid_{plan}.mp4'
            record(f_, p, rou, 300, 345, plan, title, sub, 'brake,events', 0.65, 960, 1080, junction='C2', cj=js, keep_seed=True)
            parts.append(f_)
        hstack(parts, out / 'grid_24000.mp4')
    if want('stockholm'):
        w = Path('/home/erikf/projects/personal/cars-data/truth/d8/st2')
        net = w / 'district.net.xml'
        rou = w / 'district_1.0_0_av.rou.xml'
        parts = []
        for plan, title, sub, extra in (('sig', 'Generated signals', 'Sveavagen district, report 02 demand at 60%', ()), ('off', 'Signal-free today', 'same arrivals', ()), ('route', 'Planning across junctions', 'same arrivals', ())):
            f_ = WORK / f'st_{plan}.mp4'
            record(f_, net, rou, 1500, 1545, plan, title, sub, 'brake,events', 0.75, 640, 1080, junction=None, cj=None if plan == 'sig' else 'all', keep_seed=True, center='22600,16400', teleport=True)
            parts.append(f_)
        hstack(parts, out / 'stockholm_60pct.mp4')
    if want('close_3000'):
        net, rou = demand('j2', 3000, 'M', 165)
        p = []
        for plan, title in (('off', 'Today, close up'), ('route', 'Planned, close up')):
            f = WORK / f'close_{plan}.mp4'
            record(f, net, rou, 120, 150, plan, title, 'same arrivals, last 90 m of each approach', 'brake', 0.095, 1920, 540)
            p.append(f)
        stack(p, out / 'close_3000.mp4')


if __name__ == '__main__':
    try:
        main()
    finally:
        GATE.leave()
