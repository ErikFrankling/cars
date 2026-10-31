#!/usr/bin/env python3
"""Check artifact completeness and record reproducible video metadata."""
import csv
from fractions import Fraction
import hashlib
import json
import subprocess
from pathlib import Path
import phenomena as p


def main():
    missing=[]
    for name in p.SCENARIOS:
        for seed in [42,43,44]:
            variants=[f'_n{n}' for n in [10,30,60,90,120,150,180,210,240]] if name=='freeway_fd' else ['']
            if name=='one_av':variants+=['_human']
            if name=='gridlock':variants+=['_clear']
            for variant in variants:
                label=name+variant+(f'_seed{seed}' if seed!=42 else '')
                path=p.OUT/(label+'_summary.csv')
                if not path.exists():missing.append(label);continue
                assert {r['simulator'] for r in csv.DictReader(path.open())}=={'SUMO','cars'},label
                d=p.ROOT/'runs/phenomena'/label
                assert path.stat().st_mtime >= (d/'manifest.json').stat().st_mtime,label+' incomplete results'
                assert '\nwall ' in (d/'cars.log').read_text(),label+' incomplete GPU run'
                if name=='freeway_fd':
                    last=list(csv.DictReader((d/'cars_summary.csv').open()))[-1]
                    assert int(float(last['inserted']))==int(variant[2:]),label
                manifest=json.loads((d/'manifest.json').read_text())
                old_inputs=manifest.get('inputs',{})
                for filename in ['net.xml','routes.xml','signals.xml']:
                    candidate=d/filename
                    if filename in old_inputs and candidate.exists():
                        assert hashlib.sha256(candidate.read_bytes()).hexdigest()==old_inputs[filename],label+' changed inputs'
                manifest['inputs']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in d.glob('*.xml') if x.name in ['net.xml','routes.xml','signals.xml']}
                manifest['binary_sha256']=hashlib.sha256((p.ROOT/'target/release/cars').read_bytes()).hexdigest()
                (p.OUT/(label+'_manifest.json')).write_text(json.dumps(manifest,indent=2))
    for d in (p.ROOT/'runs/phenomena').glob('freeway_fd_n260*'):
        if not (d/'manifest.json').exists():continue
        manifest=json.loads((d/'manifest.json').read_text());manifest['population_validated']=False
        (p.OUT/(d.name+'_manifest.json')).write_text(json.dumps(manifest,indent=2))
    inventory=[]
    for name in p.SCENARIOS:
        path=p.VIDEOS/(name+'.mp4')
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,width,height,r_frame_rate','-of','json',str(path)],text=True))
        stream=info['streams'][0];duration=float(info['format']['duration'])
        assert stream['codec_name']=='h264' and (stream['width'],stream['height'])==(1920,1080),name
        assert 25<=duration<=60,(name,duration)
        assert 25<=float(Fraction(stream["r_frame_rate"]))<=60,name
        inventory.append(dict(scenario=name,path=str(path),duration_s=duration,**stream))
    (p.OUT/'video_inventory.json').write_text(json.dumps(inventory,indent=2))
    large=[str(x.relative_to(p.ROOT)) for x in p.OUT.glob('*.csv') if x.stat().st_size>=3_000_000]
    print(json.dumps(dict(missing=missing,large_csv=large,videos=len(inventory)),indent=2))
    if missing:raise SystemExit(1)

if __name__=='__main__':main()
