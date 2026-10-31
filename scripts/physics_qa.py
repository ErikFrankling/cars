#!/usr/bin/env python3
"""Trajectory diagnostics; geometry-derived metrics are estimates, not collision adjudication."""
import argparse
import csv
import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def geometry(path):
    lanes = {}
    junctions = {}
    for _, e in ET.iterparse(path, events=('end',)):
        if e.tag == 'lane':
            pts = [tuple(map(float, p.split(','))) for p in e.get('shape', '').split()]
            ds = [0.]
            for a, b in zip(pts, pts[1:]):
                ds.append(ds[-1]+math.dist(a,b))
            lanes[e.get('id')] = (pts, ds, float(e.get('length', ds[-1])))
        if e.tag == 'junction':
            for lane in e.get('intLanes','').split(): junctions[lane] = e.get('id')
        if e.tag in ('edge','junction'): e.clear()
    return lanes, junctions


def pose(lanes, lane, pos):
    import bisect
    pts, ds, length = lanes[lane]
    if len(pts)<2: return 0.,0.,0.,0.
    d = max(0., min(1.,pos/max(length,1e-6)))*ds[-1]
    i = min(len(pts)-2,max(0,bisect.bisect_right(ds,d)-1))
    a,b=pts[i:i+2]; u=(d-ds[i])/max(ds[i+1]-ds[i],1e-6)
    heading=math.atan2(b[1]-a[1],b[0]-a[0])
    curvature=0.
    if i+2<len(pts):
        c=pts[i+2]; turn=math.atan2(math.sin(math.atan2(c[1]-b[1],c[0]-b[0])-heading),math.cos(math.atan2(c[1]-b[1],c[0]-b[0])-heading))
        curvature=abs(turn)/max((math.dist(a,b)+math.dist(b,c))/2,1e-6)
    return a[0]+u*(b[0]-a[0]),a[1]+u*(b[1]-a[1]),heading,curvature


def analyse(net,fcd,out):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    lanes,junctions=geometry(net)
    previous={}; per=defaultdict(lambda:defaultdict(int)); vehicle_values=defaultdict(lambda:defaultdict(list)); acc=[];jerk=[]; lateral=[];events=[]; badlanes=defaultdict(lambda:[0,0,0.])
    frame=[];time=None;overlaps=0;junction_overlaps=0; samples=0
    def overlap_frame(rows):
        nonlocal overlaps,junction_overlaps
        groups=defaultdict(list);cells=defaultdict(list)
        for r in rows:
            groups[r['lane']].append(r)
            j=junctions.get(r['lane'])
            if j:
                key=(j,math.floor(r['x']/10),math.floor(r['y']/10))
                for dx in (-1,0,1):
                    for dy in (-1,0,1):
                        for b in cells[(j,key[1]+dx,key[2]+dy)]:
                            if b['lane']==r['lane']:continue
                            # SAT on oriented vehicle rectangles, front position converted to centre.
                            def corners(v):
                                h=v['heading']; ux,uy=math.cos(h),math.sin(h);cx=v['x']-ux*v['length']/2;cy=v['y']-uy*v['length']/2
                                return [(cx+ux*a-uy*b,cy+uy*a+ux*b) for a,b in [(-v['length']/2,-v['width']/2),(v['length']/2,-v['width']/2),(v['length']/2,v['width']/2),(-v['length']/2,v['width']/2)]]
                            ca,cb=corners(r),corners(b); hit=True
                            for v in (r,b):
                                for h in (v['heading'],v['heading']+math.pi/2):
                                    axis=(math.cos(h),math.sin(h));aa=[x*axis[0]+y*axis[1] for x,y in ca];bb=[x*axis[0]+y*axis[1] for x,y in cb]
                                    if min(max(aa),max(bb))-max(min(aa),min(bb))<=0.05:hit=False
                            if hit:
                                junction_overlaps+=1;per[r['trip']]['junction_overlap_samples']+=1;events.append((r['time'],r['trip'],'junction_rectangle_overlap',r['lane']))
                cells[key].append(r)
        for lane, rs in groups.items():
            rs.sort(key=lambda r:r['pos'])
            for a,b in zip(rs,rs[1:]):
                if b['pos']-b['length']-a['pos'] < -0.05:
                    overlaps+=1;per[a['trip']]['negative_gap_samples']+=1;events.append((a['time'],a['trip'],'negative_gap',lane))
    with open(fcd) as f:
        for raw in csv.DictReader(f):
            if raw['lane'] not in lanes: continue
            r={k:float(raw[k]) for k in ('time','pos','speed','acc')};r.update(trip=raw['trip'],lane=raw['lane'],length=float(raw.get('length',5)),width=float(raw.get('width',1.8)),depart_step=raw.get('depart_step'))
            r['x'],r['y'],r['heading'],curve=pose(lanes,r['lane'],r['pos']); a_lat=r['speed']**2*curve
            samples+=1;per[r['trip']]['samples']+=1;acc.append(r['acc']);lateral.append(a_lat)
            vehicle_values[r['trip']]['acceleration'].append(r['acc']);vehicle_values[r['trip']]['lateral_acceleration'].append(a_lat)
            if a_lat>4:badlanes[r['lane']][0]+=1;per[r['trip']]['lateral_over_4']+=1
            if a_lat>8:badlanes[r['lane']][1]+=1;per[r['trip']]['lateral_over_8']+=1
            badlanes[r['lane']][2]=max(badlanes[r['lane']][2],a_lat)
            old=previous.get(r['trip'])
            if old:
                dt=r['time']-old['time']
                if dt<=0:raise ValueError('FCD must have increasing time per vehicle')
                reset=r['depart_step'] is not None and r['depart_step']!=old['depart_step']
                gap=dt>1.5*interval if (interval:=old.get('interval')) else False
                r['interval']=dt
                if reset or gap:per[r['trip']]['excluded_teleport_or_missing_intervals']+=1
                else:
                    j=(r['acc']-old['acc'])/dt;jerk.append(j);vehicle_values[r['trip']]['jerk'].append(j)
                    if abs(j)>10:per[r['trip']]['jerk_over_10']+=1
                    jump=math.hypot(r['x']-old['x'],r['y']-old['y'])
                    if jump>max(r['speed'],old['speed'])*dt+max(2.,0.5*9*dt*dt):
                        per[r['trip']]['continuity_jumps']+=1;events.append((r['time'],r['trip'],'continuity_jump',r['lane']))
                    if old['lane']!=r['lane']:
                        if old['lane'].rsplit('_',1)[0]==r['lane'].rsplit('_',1)[0]:per[r['trip']]['instant_lane_changes']+=1
                        else:
                            dh=abs(math.atan2(math.sin(r['heading']-old['heading']),math.cos(r['heading']-old['heading'])))
                            if dh>math.radians(30):per[r['trip']]['connector_heading_over_30deg']+=1
            previous[r['trip']]=r
            if time is not None and r['time']!=time:overlap_frame(frame);frame=[]
            time=r['time'];frame.append(r)
    overlap_frame(frame)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    totals={k:sum(v.get(k,0) for v in per.values()) for k in set(k for v in per.values() for k in v)}
    for k in ('continuity_jumps','instant_lane_changes','jerk_over_10','connector_heading_over_30deg','lateral_over_4','lateral_over_8','excluded_teleport_or_missing_intervals'):totals.setdefault(k,0)
    totals.update(vehicles=len(per),samples=samples,negative_gap_samples=overlaps,junction_rectangle_overlap_samples=junction_overlaps)
    stats={}
    for name,values in [('acceleration',acc),('jerk',jerk),('lateral_acceleration',lateral)]:
        stats[name]={k:float(x) for k,x in zip(('min','p50','p95','p99','max'),np.percentile(values,[0,50,95,99,100]))} if values else {}
    totals['acceleration_outside_minus9_plus4']=sum(x < -9 or x>4 for x in acc)
    (out/'summary.json').write_text(json.dumps(dict(totals=totals,distributions=stats),indent=2))
    for trip,metrics in vehicle_values.items():
        for name,values in metrics.items():
            for label,value in zip(('min','p50','p95','p99','max'),np.percentile(values,[0,50,95,99,100])):per[trip][name+'_'+label]=float(value)
    with (out/'vehicles.csv').open('w') as f:
        keys=sorted({k for v in per.values() for k in v});w=csv.writer(f);w.writerow(['trip']+keys)
        for trip,v in sorted(per.items()):w.writerow([trip]+[v.get(k,0) for k in keys])
    with (out/'events.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['time','trip','event','lane']);w.writerows(events)
    fig,axes=plt.subplots(1,3,figsize=(13,3.5))
    for ax,(name,values) in zip(axes,[('acceleration',acc),('jerk',jerk),('lateral acceleration',lateral)]):
        ax.hist(values,bins=80,log=True);ax.set_title(name);ax.set_xlabel('m/s²' if name!='jerk' else 'm/s³');ax.set_ylabel('samples')
    fig.tight_layout();fig.savefig(out/'distributions.png',dpi=160);plt.close(fig)
    lines=['# Physics QA',f'Net: `{net}`; FCD: `{fcd}`','', 'Counts are sampled observations, not distinct incidents. Bounds are screening thresholds (acceleration −9…4 m/s², |jerk| 10 m/s³, lateral 4/8 m/s²), not proof of unrealistic driving.', '', '## Overall', '']+[f'- {k}: {v}' for k,v in sorted(totals.items())]
    lines+=['','## Distributions','', 'Metric | min | p50 | p95 | p99 | max','---|---:|---:|---:|---:|---:']+[name+' | '+' | '.join(f'{v:.3f}' for v in vals.values()) for name,vals in stats.items()]
    lines+=['','![Distributions](distributions.png)','','## Turn lanes exceeding thresholds','','Lane | >4 samples | >8 samples | peak m/s²','---|---:|---:|---:']+[f'{lane} | {v[0]} | {v[1]} | {v[2]:.2f}' for lane,v in sorted(badlanes.items()) if v[0]]
    lines+=['','## Interpretation limits','','Curvature uses piecewise lane headings and adjacent segment lengths; coarse geometry can overestimate peaks. Connector headings include legitimate turns across the sampling interval. Junction overlaps use oriented rectangles; same-lane gaps use front position minus leader length. Width defaults to 1.8 m. Depart-step changes and missing intervals are excluded from continuity and jerk as teleport/reinsert candidates; old FCD without depart_step cannot identify every teleport. Instant lane changes count edge-preserving lane-id changes. See vehicles.csv and events.csv for attribution.']
    (out/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(totals))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--net',required=True);p.add_argument('--fcd',required=True);p.add_argument('--out',required=True);a=p.parse_args();analyse(a.net,a.fcd,a.out)
