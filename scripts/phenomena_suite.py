#!/usr/bin/env python3
"""Sequential paired experiments; each measurement includes both engines."""
import argparse
import json
import hashlib
import subprocess
import shutil
import xml.etree.ElementTree as ET
import phenomena as p


def execute(name, seed, variant='', generate=None, video=False):
    p.SEED = seed
    label = name + variant + (f'_seed{seed}' if seed != 42 else '')
    d = p.ROOT/'runs/phenomena'/label
    d.mkdir(parents=True, exist_ok=True)
    p.OUT.mkdir(parents=True, exist_ok=True)
    cfg = (generate or p.SCENARIOS[name])(d)
    p.write(d, 'manifest.json', json.dumps(dict(scenario=name, variant=variant, seed=seed, dt=.1, git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), binary_sha256=hashlib.sha256((p.ROOT/'target/release/cars').read_bytes()).hexdigest(), inputs={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in d.glob('*.xml')}, **cfg), indent=2))
    shutil.copy(d/'manifest.json',p.OUT/(label+'_manifest.json'))
    p.measure(d, cfg, label)
    if video: p.video(d,cfg,name+variant)


def density(n):
    def generate(d):
        cfg = p.ring(d,2000,n,600)
        root = ET.parse(d/'routes.xml')
        root.getroot().find('vType').set('maxSpeed','30')
        root.write(d/'routes.xml')
        net = ET.parse(d/'net.xml')
        for lane in net.getroot().iter('lane'): lane.set('speed','30')
        net.write(d/'net.xml')
        cfg.update(ring=False, density_count=n, note=f'Closed 2 km ring at {n/2:g} vehicles/km; fixed density, no insertion bottleneck.')
        return cfg
    return generate


def main():
    a=argparse.ArgumentParser();a.add_argument('names',nargs='*');a.add_argument('--seeds',nargs='+',type=int,default=[42,43,44]);args=a.parse_args()
    for name in args.names or p.SCENARIOS:
        for seed in args.seeds:
            if name=='freeway_fd':
                for n in [10,30,60,90,120,150,180,210,240]: execute(name,seed,f'_n{n}',density(n))
            else:
                execute(name,seed)
                if name=='one_av': execute(name,seed,'_human',p.phantom_jam)
                if name=='gridlock': execute(name,seed,'_clear',lambda d:p.grid(d,900,True,True))

if __name__=='__main__':main()
