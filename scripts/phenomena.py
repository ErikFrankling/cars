#!/usr/bin/env python3
"""Reproducible traffic comparisons. Run inside nix develop; no flags generates inputs.

--measure runs both engines sequentially; --video records cars (explicitly labelled).
Raw logs live under runs/, compact interval observations under results/.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THESIS = Path('/home/erikf/projects/personal/thesis-src/bachelor')
SEED = 42
OUT = ROOT / 'results/phenomena'
VIDEOS = Path('/home/erikf/projects/personal/cars-data/videos')
SCENARIOS = {}


def scenario(f):
    SCENARIOS[f.__name__] = f
    return f


def command(args, log=None):
    args = list(map(str, args))
    print(' '.join(args), flush=True)
    if log:
        with open(log, 'w') as f:
            subprocess.run(args, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True, timeout=600)
    else:
        subprocess.run(args, cwd=ROOT, check=True, timeout=600)


def write(d, name, text):
    (d / name).write_text(text)


def network(d, nodes, edges):
    write(d, 'nodes.xml', '<nodes>' + ''.join(nodes) + '</nodes>')
    write(d, 'edges.xml', '<edges>' + ''.join(edges) + '</edges>')
    command(['netconvert', '-n', d/'nodes.xml', '-e', d/'edges.xml', '-o', d/'net.xml',
             '--no-turnarounds', '--junctions.corner-detail', '0'], d/'netconvert.log')


def demand(d, body, speed=33.33, extra=''):
    write(d, 'routes.xml', f'<routes><vType id="human" carFollowModel="Krauss" sigma="0.5" '
          f'speedDev="0" maxSpeed="{speed}" length="5" minGap="2.5" accel="2.6" decel="4.5" tau="1"/>'
          + extra + body + '</routes>')


def ring(d, circumference, count, end=600, one=False):
    r = circumference/(2*math.pi)
    nodes = [f'<node id="n{i}" x="{r*math.cos(i*math.pi)}" y="0" type="unregulated"/>' for i in range(2)]
    edges = []
    for half in range(2):
        shape = ' '.join(f'{r*math.cos((half+i/64)*math.pi):.6f},{r*math.sin((half+i/64)*math.pi):.6f}' for i in range(65))
        edges.append(f'<edge id="e{half}" from="n{half}" to="n{1-half}" shape="{shape}" length="{circumference/2}" speed="8.333333" numLanes="1" spreadType="center"/>')
    network(d, nodes, edges)
    body = '<route id="r0" edges="' + ' '.join(['e0','e1']*1000) + '"/><route id="r1" edges="' + ' '.join(['e1','e0']*1000) + '"/>'
    for i in range(count):
        body += f'<vehicle id="v{i}" type="{"buffer" if one and i == 0 else "human"}" route="r{int(i*2/count)}" depart="0" departPos="{(i*circumference/count)%(circumference/2)}" departSpeed="0"/>'
    demand(d, body, 8.333333, '<vType id="buffer" carFollowModel="IDM" tau="2" speedDev="0" maxSpeed="8.333333" length="5" minGap="2.5" accel="2.6" decel="4.5"/>')
    return dict(end=end, ring=True, note='Long-headway vehicle present from start; not the Stern feedback controller.' if one else '22 drivers on a ring. This run shows whether waves emerge without an obstacle.')


@scenario
def phantom_jam(d):
    cfg=ring(d, 330, 22, 1800)
    root=ET.parse(d/'routes.xml')
    human=root.getroot().find('vType')
    human.set('accel','0.3')
    human.set('carFollowModel','IDM')
    human.set('decel','1.5')
    root.getroot().find('vehicle').set('departPos','3')
    root.write(d/'routes.xml')
    cfg['note']='22 IDM drivers, 330 m ring; 3 m initial perturbation grows into stop-and-go waves.'
    return cfg


@scenario
def one_av(d):
    return ring(d, 260, 22, 900, True)


def road(d, name, lengths, lanes, rates, end, signal=False, ramp=False, pulse=False):
    nodes = [f'<node id="n{i}" x="{sum(lengths[:i])}" y="0" type="{"traffic_light" if signal and 0 < i < len(lengths) else "priority"}"/>' for i in range(len(lengths)+1)]
    edges = [f'<edge id="e{i}" from="n{i}" to="n{i+1}" numLanes="{lanes[i]}" speed="{5 if pulse and i == 1 else 33.33}"/>' for i in range(len(lengths))]
    if ramp:
        nodes += ['<node id="r" x="2000" y="-400"/>']
        edges += ['<edge id="ramp" from="r" to="n1" numLanes="1" speed="20"/>']
    network(d, nodes, edges)
    route = ' '.join(f'e{i}' for i in range(len(lengths)))
    body = f'<route id="main" edges="{route}"/>'
    # Explicit departure schedules, identical across engines (no stochastic flows).
    for stage, rate in enumerate(rates):
        begin, finish = stage*end/len(rates), (stage+1)*end/len(rates)
        for j in range(int((finish-begin)*rate/3600)):
            body += f'<vehicle id="s{stage}v{j}" type="human" route="main" depart="{begin+j*3600/rate:.3f}" departLane="free" departSpeed="max"/>'
    if ramp:
        body += '<route id="r" edges="ramp ' + ' '.join(f'e{i}' for i in range(1,len(lengths))) + '"/>'
        for j in range(int(end/4)):
            body += f'<vehicle id="r{j}" type="human" route="r" depart="{j*4+0.01}" departSpeed="max"/>'
    # SUMO requires time-sorted vehicles.
    root = ET.fromstring('<routes>'+body+'</routes>')
    ordered = [x for x in root if x.tag == 'route'] + sorted([x for x in root if x.tag == 'vehicle'], key=lambda x:float(x.get('depart')))
    demand(d, ''.join(ET.tostring(x, encoding='unicode') for x in ordered))
    return dict(end=end, ring=False, note=name)


@scenario
def brake_wave(d):
    return road(d, 'Persistent short slow section; not a temporary brake pulse.', [2450,100,2450], [1,1,1], [1800,2200,2200], 1800, pulse=True)


@scenario
def capacity_drop(d):
    return road(d, 'Demand crosses a two-to-one lane bottleneck.', [3000,3000], [2,1], [1600,2000,2600,3000,2000,1400], 3600)


@scenario
def freeway_fd(d):
    return road(d, 'Offered demand increases from 1000 to 2600 vehicles per hour.', [2500,2500], [1,1], list(range(1000,2601,200)), 8100)


@scenario
def signal_discharge(d):
    cfg = road(d, 'A red light stores a queue before discharge.', [500,500], [1,1], [1200], 1800, signal=True)
    net = ET.parse(d/'net.xml').getroot()
    tls = net.find('tlLogic')
    phases = list(tls)
    green = next(p.get('state') for p in phases if 'G' in p.get('state'))
    write(d, 'signals.xml', f'<additional><tlLogic id="{tls.get("id")}" type="static" programID="phenomena" offset="0"><phase duration="30" state="{"r"*len(green)}"/><phase duration="30" state="{green}"/></tlLogic></additional>')
    # Forty physically queued vehicles fit into the 500 m approach.
    root = ET.parse(d/'routes.xml').getroot()
    for v in list(root.findall('vehicle')):
        root.remove(v)
    for i in range(40):
        ET.SubElement(root, 'vehicle', id=f'q{i}', type='human', route='main', depart='0', departPos=str(490-i*7.5), departSpeed='0')
    ET.ElementTree(root).write(d/'routes.xml')
    return cfg


@scenario
def onramp_merge(d):
    return road(d, 'Ramp inflow meets rising mainline demand.', [2500,2500], [2,2], [1600,2400,3200,3800], 1800, ramp=True)


@scenario
def spillback(d):
    cfg = road(d, 'Downstream green serves only one fifth of each cycle.', [500,150,500], [1,1,1], [1200], 1800, signal=True)
    net = ET.parse(d/'net.xml').getroot()
    programs = []
    for i,tls in enumerate(net.findall('tlLogic')):
        green = next(p.get('state') for p in tls if 'G' in p.get('state'))
        g = 30 if i == 0 else 12
        programs.append(f'<tlLogic id="{tls.get("id")}" type="static" programID="phenomena" offset="0"><phase duration="{60-g}" state="{"r"*len(green)}"/><phase duration="{g}" state="{green}"/></tlLogic>')
    write(d, 'signals.xml', '<additional>'+''.join(programs)+'</additional>')
    return cfg


def grid(d, end):
    command(['netgenerate','--grid','--grid.number','5','--grid.length','250','--default.speed','13.89','--tls.guess','true','--tls.guess.threshold','0','--no-turnarounds','-o',d/'net.xml'], d/'netconvert.log')
    net = ET.parse(d/'net.xml').getroot()
    # Straight boundary-to-boundary trips; deterministic routing with no randomTrips dependency.
    edges = {e.get('id'):e for e in net.findall('edge') if e.get('function') != 'internal'}
    nodes = {n.get('id'):(float(n.get('x')),float(n.get('y'))) for n in net.findall('junction') if n.get('type') != 'internal'}
    routes = []
    for e in edges.values():
        a,b = nodes[e.get('from')],nodes[e.get('to')]
        dx,dy = b[0]-a[0], b[1]-a[1]
        if any(nodes[x.get('from')] == (a[0]-dx,a[1]-dy) and x.get('to') == e.get('from') for x in edges.values()):
            continue
        path=[e.get('id')]; cur=e
        while True:
            p=nodes[cur.get('to')]
            nxt=next((x for x in edges.values() if x.get('from') == cur.get('to') and nodes[x.get('to')] == (p[0]+dx,p[1]+dy)),None)
            if nxt is None: break
            path.append(nxt.get('id'));cur=nxt
        if len(path)>=3: routes.append(path)
    body=''.join(f'<route id="r{i}" edges="{" ".join(r)}"/>' for i,r in enumerate(routes))
    vehicles=[]
    for stage,rate in enumerate([200,400,650,900,900,650,400,200]):
        for i in range(len(routes)):
            for j in range(int(end/8*rate/3600)):
                t=stage*end/8+j*3600/rate+i*.001
                vehicles.append((t,f'<vehicle id="s{stage}r{i}v{j}" type="human" route="r{i}" depart="{t:.3f}" departSpeed="max"/>'))
    demand(d,body+''.join(v for _,v in sorted(vehicles)),13.89)
    return dict(end=end, ring=False, note='Boundary demand rises and falls; recovery is measured, not assumed.')


@scenario
def gridlock(d): return grid(d,3600)


@scenario
def mfd(d): return grid(d,7200)


def thesis_inputs(d, net, routes, end, note, additional=()):
    base=THESIS/'config'
    shutil.copy(base/net,d/'net.xml')
    root=ET.parse(base/routes).getroot()
    types=ET.parse(base/'vtypes.xml').getroot()
    for v in root.findall('vehicle'):
        v.set('type','human')
    for t in types.findall('vType'):
        root.insert(0,t)
    ET.ElementTree(root).write(d/'routes.xml')
    if additional:
        shutil.copy(base/additional[0],d/'signals.xml')
    return dict(end=end,ring=False,note=note)


@scenario
def thesis_ring(d):
    return thesis_inputs(d,'networks/ring.net.xml','demand/ring.rou.xml',4000,
                        'Thesis ring human baseline; scripted disturbance is not enabled.')


@scenario
def bologna_rush(d):
    return thesis_inputs(d,'scenarios/bologna/joined_buslanes.net.xml',
                        'scenarios/bologna/bologna_cars.rou.xml',5400,
                        'Bologna thesis human baseline during rush demand.',
                        ['scenarios/bologna/joined_tls.add.xml'])


@scenario
def i80_day(d):
    return thesis_inputs(d,'networks/i80_vsl.net.xml','demand/i80_vsl.rou.xml',18000,
                        'I-80 thesis human baseline; demand increases then recedes.')


def geometry(d):
    root=ET.parse(d/'net.xml').getroot()
    return {e.get('id'):sum(float(l.get('length')) for l in e.findall('lane')) for e in root.findall('edge') if e.get('function') != 'internal'}


def measure(d,cfg,name):
    lengths=geometry(d)
    additional = [d/'edge.add.xml'] + ([d/'signals.xml'] if (d/'signals.xml').exists() else [])
    write(d,'edge.add.xml','<additional><edgeData id="edges" freq="30" file="sumo_edges.xml" excludeEmpty="false"/></additional>')
    common=['--net-file',d/'net.xml','--route-files',d/'routes.xml','--step-length','0.1','--end',cfg['end'],'--seed',str(SEED),'--time-to-teleport','-1','--no-step-log','true']
    
    if cfg.get('ring'): common += ['--fcd-output', d/'sumo_fcd.xml', '--device.fcd.period', '1']
    command(['flock','/tmp/cars-sumo.lock','sumo',*common,'--additional-files',','.join(map(str,additional)),'--tripinfo-output',d/'sumo_trips.xml'],d/'sumo.log')
    cars=[ROOT/'target/release/cars','run','--net',d/'net.xml','--routes',d/'routes.xml','--dt','.1','--end',cfg['end'],'--seed',str(SEED),'--time-to-teleport','0','--edge-csv',d/'cars_edges.csv','--edge-interval','30','--trip-csv',d/'cars_trips.csv','--summary-csv',d/'cars_summary.csv']
    if cfg.get('ring'): cars += ['--fcd',d/'cars_fcd.csv','--fcd-interval','1']
    if (d/'signals.xml').exists(): cars+=['--additional',d/'signals.xml']
    command(['flock','/tmp/cars-gpu.lock',*cars],d/'cars.log')
    rows=[]
    for _,elem in ET.iterparse(d/'sumo_edges.xml',events=['end']):
        if elem.tag=='interval':
            for e in elem.findall('edge'):
                if e.get('id') not in lengths: continue
                sample=float(e.get('sampledSeconds',0));speed=float(e.get('speed',0))
                rows.append(['SUMO',float(elem.get('begin')),e.get('id'),sample,sample*speed,float(e.get('entered',0))])
            elem.clear()
    with open(d/'cars_edges.csv') as f:
        for r in csv.DictReader(f):
            if r['edge'] in lengths: rows.append(['cars',float(r['begin']),r['edge'],float(r['samples']),float(r['distance']),float(r['entered'])])
    OUT.mkdir(parents=True,exist_ok=True)
    with open(OUT/f'{name}_edges.csv','w') as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(['simulator','begin_s','edge','vehicle_seconds','distance_m','entered']);w.writerows(rows)
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['axes.prop_cycle'] = matplotlib.cycler(color=['#eb6834','#2a78d6'])
    data=pd.DataFrame(rows,columns=['simulator','time','edge','samples','distance','entered'])
    data['length']=data.edge.map(lengths)
    data['density']=data.samples/30/data.length*1000
    data['flow']=data.distance/30/data.length*3600
    fig,axs=plt.subplots(2,2,figsize=(12,8))
    summary=[]
    for sim,g in data.groupby('simulator'):
        agg=g.groupby('time')[['samples','distance','entered']].sum()
        # Include empty edges in denominator; edge files may omit them.
        agg['N']=agg.samples/30
        agg['P']=agg.distance/30
        axs[0,0].plot(agg.index,agg.N,label=sim)
        axs[0,1].plot(agg.index,agg.P,label=sim)
        axs[1,0].scatter(g.density,g.flow,s=4,alpha=.5,label=sim)
        axs[1,1].plot(agg.N,agg.P,label=sim)
        speed=g.distance.sum()/g.samples.sum() if g.samples.sum() else float('nan')
        summary.append([sim,speed,float(agg.N.max()),float(agg.P.max())])
    for ax,x,y in zip(axs.flat,['Time (s)','Time (s)','Density (veh/km/lane)','Accumulation (veh)'],['Accumulation (veh)','Production (veh m/s)','Flow (veh/h/lane)','Production (veh m/s)']):
        ax.set(xlabel=x,ylabel=y);ax.legend();ax.grid(alpha=.2)
    if name=='freeway_fd': axs[1,0].axhline(2400,color='black',ls='--',label='Ideal reference 2400');axs[1,0].legend()
    fig.suptitle(name+' | one seed; no equivalence claim');fig.tight_layout();fig.savefig(OUT/f'{name}.png',dpi=140);plt.close(fig)
    with open(OUT/f'{name}_summary.csv','w') as f:
        w=csv.writer(f,lineterminator="\n");w.writerow(['simulator','space_mean_speed_m_s','peak_accumulation_veh','peak_production_veh_m_s']);w.writerows(summary)
    if cfg.get("ring"): trajectories(d,name)
    diagnostics = re.search(r'lane changes (\d+), teleports (\d+), collisions (\d+)(?: \([^)]*\))?, overflow (\d+), items full (\d+)', (d/'cars.log').read_text())
    if diagnostics:
        with open(OUT/f'{name}_diagnostics.csv','w') as f:
            w=csv.writer(f,lineterminator="\n");w.writerow(['lane_changes','teleports','collisions','overflow_counter','items_full']);w.writerow(diagnostics.groups())



def trajectories(d,name):
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    net=ET.parse(d/'net.xml').getroot()
    lengths={e.get('id'):float(e.find('lane').get('length')) for e in net.findall('edge') if e.get('function')!='internal'}
    offsets={};offset=0
    for e in sorted(lengths): offsets[e]=offset;offset+=lengths[e]
    rows=[]
    for _,elem in ET.iterparse(d/'sumo_fcd.xml',events=['end']):
        if elem.tag=='timestep':
            for v in elem.findall('vehicle'):
                edge=v.get('lane').rsplit('_',1)[0]
                if edge in offsets: rows.append(['SUMO',float(elem.get('time')),v.get('id'),offsets[edge]+float(v.get('pos')),float(v.get('speed'))])
            elem.clear()
    with open(d/'cars_fcd.csv') as f:
        for v in csv.DictReader(f):
            edge=v['lane'].rsplit('_',1)[0]
            if edge in offsets: rows.append(['cars',float(v['time']),v['trip'],offsets[edge]+float(v['pos']),float(v['speed'])])
    data=pd.DataFrame(rows,columns=['simulator','time_s','vehicle','position_m','speed_m_s'])
    metrics=[]
    for sim,g in data.groupby('simulator'):
        g=g[g.time_s>=600]
        if g.empty: continue
        field=g.assign(t=(g.time_s//10).astype(int),x=(g.position_m/offset*66).astype(int)%66).pivot_table(index='t',columns='x',values='speed_m_s',aggfunc='mean').reindex(columns=range(66))
        field=field.interpolate(axis=1,limit_direction='both').to_numpy()
        scores=[]
        shifts=range(-15,16)
        for shift in shifts:
            a=field[:-1].ravel();b=np.roll(field[1:],-shift,axis=1).ravel()
            mask=np.isfinite(a)&np.isfinite(b)
            scores.append(np.corrcoef(a[mask],b[mask])[0,1] if mask.sum()>10 else float('nan'))
        shift=list(shifts)[int(np.nanargmax(scores))]
        metrics.append([sim,float((g.speed_m_s<.5).mean()),float(g.speed_m_s.std()),shift*offset/66/10*3.6,max(scores)])
    with open(OUT/f'{name}_waves.csv','w') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['simulator','stopped_fraction','speed_sd_m_s','wave_km_h','correlation']);w.writerows(metrics)
    data.iloc[::5].to_csv(OUT/f'{name}_trajectories.csv',index=False,float_format='%.3f')
    fig,axs=plt.subplots(2,2,figsize=(13,8),sharex=True)
    for col,(sim,g) in enumerate(data.groupby('simulator',sort=False)):
        for _,v in g.groupby('vehicle'):
            pos=v.position_m.to_numpy();unwrap=np.unwrap(pos*2*np.pi/offset)*offset/(2*np.pi)
            axs[0,col].plot(v.time_s,unwrap,lw=.4,color={'SUMO':'#eb6834','cars':'#2a78d6'}[sim])
        sc=axs[1,col].scatter(g.time_s,g.position_m,c=g.speed_m_s,s=2,vmin=0,vmax=8.33,cmap='RdYlGn')
        axs[0,col].set(title=sim,ylabel='Unwrapped position (m)')
        axs[1,col].set(xlabel='Time (s)',ylabel='Ring position (m)')
        fig.colorbar(sc,ax=axs[1,col],label='Speed (m/s)')
    fig.suptitle(name+' | stopped start | initial position perturbation only')
    fig.tight_layout();fig.savefig(OUT/f'{name}.png',dpi=140);plt.close(fig)
    # Common axes retain an explicit SUMO/cars overlay for the comparison.
    fig,ax=plt.subplots(figsize=(9,4))
    for sim,g in data.groupby('simulator'):
        v=g.groupby('time_s').speed_m_s.agg(['mean','std'])
        ax.plot(v.index,v['std'],label=sim,color={'SUMO':'#eb6834','cars':'#2a78d6'}[sim],lw=1)
    ax.set(xlabel='Time (s)',ylabel='Across-vehicle speed SD (m/s)',title='Wave amplitude (one seed)');ax.legend();fig.tight_layout();fig.savefig(OUT/f'{name}_variance.png',dpi=140);plt.close(fig)


def video(d,cfg,name):
    cfg=dict(cfg)
    if name=='signal_discharge': cfg['end']=90
    VIDEOS.mkdir(parents=True,exist_ok=True)
    camera={'captions':[{'from':0,'to':cfg['end']/3,'text':cfg['note']},{'from':cfg['end']/3,'to':cfg['end']*2/3,'text':'Color shows speed: red vehicles are stopped or slow.'},{'from':cfg['end']*2/3,'to':cfg['end'],'text':'Follow slow red vehicles as traffic evolves.'}]}
    if not cfg.get('ring') and name not in ('gridlock','mfd','bologna_rush','i80_day','thesis_ring'):
        net=ET.parse(d/'net.xml').getroot()
        lane=next(e.find('lane') for e in net.findall('edge') if e.get('id')=='e0')
        point=list(map(float,lane.get('shape').split()[-1].split(',')))
        camera['keyframes']=[{'time':0,'center':point,'metres_per_pixel':.6},{'time':cfg['end'],'center':point,'metres_per_pixel':.35}]
    camera_dir=OUT/'cameras'; camera_dir.mkdir(parents=True,exist_ok=True)
    write(camera_dir,name+'.json',json.dumps(camera,indent=2))
    write(d,'camera.json',json.dumps(camera))
    cmd=[ROOT/'target/release/cars','record','--net',d/'net.xml','--routes',d/'routes.xml','--dt','.1','--end',cfg['end'],'--seed',str(SEED),'--steps-per-frame',max(1,math.ceil(cfg['end']/.1/1200)),'--fps','30','--width','1920','--height','1080','--camera',d/'camera.json','--color','speed','--title',name.replace('_',' ').title(),'--subtitle','cars GPU simulation | identical inputs measured against SUMO','--out',VIDEOS/f'{name}.mp4']
    if cfg.get('ring') or name in ('gridlock','mfd','bologna_rush','i80_day','thesis_ring'): cmd+=['--fit']
    if (d/'signals.xml').exists(): cmd+=['--additional',d/'signals.xml']
    command(['flock','/tmp/cars-gpu.lock',*cmd],d/'record.log')
    command(['ffmpeg','-y','-threads','2','-ss','20','-i',VIDEOS/f'{name}.mp4','-frames:v','1','-threads','2',d/'inspection.png'],d/'inspection.log')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('name',choices=SCENARIOS)
    p.add_argument('--measure',action='store_true');p.add_argument('--video',action='store_true')
    p.add_argument('--seed',type=int,default=42)
    a=p.parse_args()
    global SEED
    SEED=a.seed
    d=ROOT/'runs/phenomena'/(a.name if SEED==42 else f'{a.name}_seed{SEED}');d.mkdir(parents=True,exist_ok=True)
    cfg=SCENARIOS[a.name](d)
    manifest=dict(scenario=a.name,seed=SEED,dt=.1,**cfg,inputs={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in d.glob('*.xml')},sumo_version=subprocess.check_output(['sumo','--version'],text=True),git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    write(d,'manifest.json',json.dumps(manifest,indent=2))
    OUT.mkdir(parents=True,exist_ok=True);shutil.copy(d/'manifest.json',OUT/(f'{a.name}_manifest.json' if SEED==42 else f'{a.name}_seed{SEED}_manifest.json'))
    if a.measure:
        name=a.name if SEED==42 else f'{a.name}_seed{SEED}'
        measure(d,cfg,name)
    if a.video: video(d,cfg,a.name)
    size=sum(x.stat().st_size for x in (ROOT/'runs').rglob('*') if x.is_file())
    if size>3e9: raise RuntimeError('runs/ exceeds 3 GB; remove raw outputs before continuing')


if __name__=='__main__': main()
