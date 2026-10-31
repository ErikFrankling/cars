#!/usr/bin/env python3
"""Restartable intersection captures. Run inside nix develop; every GPU command holds cars-gpu.lock."""
import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from junctions import busiest

ROOT=Path(__file__).resolve().parents[1]
DATA=Path('/home/erikf/projects/personal/cars-data')


def run(args):
    print(' '.join(map(str,args)),flush=True);subprocess.run(list(map(str,args)),check=True)


def generate(d,kind):
    d.mkdir(parents=True,exist_ok=True)
    if (d/'net.xml').exists():return
    jt={'signal':'traffic_light','priority':'priority','all-way-stop':'allway_stop','zipper':'zipper'}.get(kind,'priority')
    nodes=[('c',0,0,jt),('w',-250,0,'priority'),('e',250,0,'priority'),('s',0,-250,'priority'),('n',0,250,'priority')]
    spec=[('wc','w','c',2,2),('ce','c','e',2,2),('ec','e','c',2,2),('cw','c','w',2,2),('sc','s','c',1,1),('cn','c','n',1,1),('nc','n','c',1,1),('cs','c','s',1,1)]
    routes=[('wc ce',800),('ec cw',800),('sc cn',400),('nc cs',400),('wc cn',180),('sc ce',150)]
    if kind in ('on-ramp','zipper','lane-drop'):
        spec=[('wc','w','c',2,2),('ce','c','e',2,1 if kind=='lane-drop' else 2),('sc','s','c',1,1)]
        nodes=[(i,(-150 if i=='s' else x),(-70 if i=='s' else y),t) for i,x,y,t in nodes]
        if kind=='lane-drop':spec=spec[:2]
        routes=[('wc ce',1800),('sc ce',600)] if kind!='lane-drop' else [('wc ce',2200)]
    if kind=='roundabout':
        nodes=[('a',-20,0,'priority'),('b',0,-20,'priority'),('c',20,0,'priority'),('d',0,20,'priority'),('w',-250,0,'priority'),('e',250,0,'priority'),('s',0,-250,'priority'),('n',0,250,'priority')]
        spec=[('ab','a','b',3,1),('bc','b','c',3,1),('cd','c','d',3,1),('da','d','a',3,1),('wa','w','a',1,1),('aw','a','w',1,1),('sb','s','b',1,1),('bs','b','s',1,1),('ec','e','c',1,1),('ce','c','e',1,1),('nd','n','d',1,1),('dn','d','n',1,1)]
        routes=[('wa ab bc ce',700),('sb bc cd dn',500),('ec cd da aw',700)]
    (d/'n.nod.xml').write_text('<nodes>'+''.join(f'<node id="{i}" x="{x}" y="{y}" type="{t}"/>' for i,x,y,t in nodes)+'</nodes>')
    (d/'n.edg.xml').write_text('<edges>'+''.join(f'<edge id="{i}" from="{a}" to="{b}" priority="{p}" numLanes="{n}" speed="{27.78 if kind=='on-ramp' and i in ('wc','ce') else 13.89}"/>' for i,a,b,p,n in spec)+('</edges>' if kind!='roundabout' else '<roundabout edges="ab bc cd da" nodes="a b c d"/></edges>'))
    run(['netconvert','-n',d/'n.nod.xml','-e',d/'n.edg.xml','-o',d/'net.xml','--no-turnarounds'])
    body='<vType id="k" sigma="0" speedDev="0"/>'
    for i,(edges,rate) in enumerate(routes):body+=f'<route id="r{i}" edges="{edges}"/><flow id="f{i}" type="k" route="r{i}" begin="0" end="300" vehsPerHour="{rate}" departLane="best" departSpeed="max"/>'
    (d/'routes.xml').write_text('<routes>'+body+'</routes>')


def peak(routes):
    counts={}
    with (gzip.open(routes,'rb') if str(routes).endswith('.gz') else open(routes,'rb')) as f:
        for _,e in ET.iterparse(f,events=('end',)):
            if e.tag in ('vehicle','trip','flow'):
                try:t=int(float(e.get('depart',e.get('begin','0'))))//900*900
                except ValueError:continue
                counts[t]=counts.get(t,0)+1;e.clear()
    return max(counts,key=counts.get) if counts else 0


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cars',type=Path,default=ROOT/'target/release/cars');p.add_argument('--out',type=Path,default=DATA/'videos/gallery');p.add_argument('--only',nargs='+');p.add_argument('--city-begin',type=float);p.add_argument('--duration',type=float,default=12);p.add_argument('--cities-per-type',type=int,default=1);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for kind in ['signal','priority','roundabout','all-way-stop','zipper','on-ramp','lane-drop']:
        if a.only and kind not in a.only:continue
        d=a.out/'fixtures'/kind;generate(d,kind);js=busiest(d/'net.xml');j=next((j for j in js if j['id']=='c'),js[0]);jobs.append((kind,d/'net.xml',d/'routes.xml',j,60.,False))
    for city,net,rou in [('berlin',DATA/'best/berlin.net.xml',DATA/'best/berlin.rou.gz'),('stockholm',DATA/'stockholm/stockholm.net.xml',DATA/'stockholm/stockholm60.rou.gz')]:
        if a.only and city not in a.only:continue
        run(['free','-g'])
        begin=a.city_begin if a.city_begin is not None else peak(rou)
        edge_csv=net.parent/'cars.edges.csv';js=busiest(net,edge_csv if edge_csv.exists() else None)
        for kind in ['signal','priority','roundabout','zipper','ramp']:
            for i,j in enumerate([j for j in js if j['type']==kind][:a.cities_per_type]):jobs.append((f'{city}-{kind}-{i}',net,rou,j,begin,True))
    for name,net,rou,j,begin,city in jobs:
        base=a.out/name;base.mkdir(exist_ok=True)
        (base/'camera.json').write_text(json.dumps({'junction':j,'begin':begin,'ranking':'incoming edge samples if available, otherwise lane count'}))
        common=[a.cars,'record','--net',net,'--routes',rou,'--dt',1 if city else .1,'--sim-begin',max(0,begin-300) if city else 0,'--junction',j['id'],'--metres-per-pixel',.08,'--width',1920,'--height',1080]
        if city:common+=['--capacity',300000,'--time-to-teleport',120,'--ignore-junction-blocker',20]
        output=base/'clip.mp4'
        if not output.exists():
            temporary=base/'clip.partial.mp4'
            run(['flock','/tmp/cars-gpu.lock']+common+['--begin',begin,'--end',begin+a.duration,'--fps',30,'--realtime','--title',name,'--out',temporary]);temporary.replace(output)
        for suffix,t in [('overview',0),('middle',a.duration/2),('end',a.duration-0.1)]:
            image=base/f'{suffix}.png'
            if not image.exists():run(['ffmpeg','-y','-v','error','-threads','1','-filter_threads','1','-ss',t,'-i',output,'-frames:v','1','-threads','1',image])

if __name__=='__main__':main()
