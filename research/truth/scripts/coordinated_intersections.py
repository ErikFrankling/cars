"""CPU-only queueing thought experiment; no empirical calibration or trajectory claims.
Run python3 research/truth/scripts/coordinated_intersections.py
Outputs restricted to research/truth/fig/09-*; standard library only.
"""
from collections import deque
from pathlib import Path
import random, statistics, csv, sys
DT=.1
WARM=600
END=2400
OUT=Path(__file__).resolve().parents[1]/'fig'

def arrivals(demand, seed, shares=(.25,)*4):
    rng=random.Random(seed); events=[]
    for lane,p in enumerate(shares):
        t=0
        while p:
            t+=rng.expovariate(demand*p/3600)
            if t>=END: break
            events.append((t,lane))
    return sorted(events)

def run(events, policy, h=2., minimum=5., maximum=40., gap=2., cross=1.2, blocked=False):
    q=[deque() for _ in range(4)]; ready=[0.]*4; last=[-1e9]*2
    phase=0; began=0.; unavailable=0.; last_depart=0.; idx=0
    delays=[]; served=0; total_served=0; area=0.; q0=None; trace=[]
    for tick in range(1,int(END/DT)+1):
        t=round(tick*DT,6)
        while idx<len(events) and events[idx][0]<=t:
            a,l=events[idx];q[l].append(a);idx+=1
        if tick==int(WARM/DT): q0=sum(map(len,q))
        counts=[len(q[0])+len(q[2]),len(q[1])+len(q[3])]
        if policy=='fcfs':
            heads=[(q[l][0],l) for l in range(4) if q[l]]
            chosen=min(heads)[1]%2 if heads else phase
            phase=chosen
        elif t>=unavailable:
            other=1-phase
            if policy=='signal':
                switch=counts[other] and t-began>=minimum and (t-began>=maximum or (t-last_depart>=gap and counts[phase]==0))
                if switch:
                    phase=other; unavailable=t+4.+1.5; began=unavailable;last_depart=unavailable
            else:
                oldest=[min([q[l][0] for l in (a,a+2) if q[l]],default=t) for a in (0,1)]
                switch=counts[other] and ((not counts[phase]) or t-began>=8. or t-oldest[other]>=20.)
                if switch: phase=other;began=t
        for l in (phase,phase+2):
            if not q[l] or ready[l]>t+1e-7: continue
            if blocked and l==0 and 1200<=t<1260: continue
            if policy=='signal':
                if t<unavailable: continue
            elif t-last[1-phase]<cross-1e-7: continue
            assert t-last[1-phase]>=cross-1e-7
            a=q[l].popleft();total_served+=1;ready[l]=t+h;last[phase]=t;last_depart=t
            if t>=WARM: served+=1
            if a>=WARM: delays.append(t-a)
        if t>=WARM: area+=sum(map(len,q))*DT
        if tick%100==0:trace.append((t,sum(map(len,q))))
    # Integrated queue includes warm-up survivors and unfinished vehicles; unlike
    # departure-only delay, it cannot hide an oversaturated controller's backlog.
    offered=sum(WARM<=a<END for a,l in events)
    assert idx==len(events)
    assert idx==sum(map(len,q))+total_served
    return dict(flow=served*3600/(END-WARM),delay=statistics.mean(delays) if delays else 0,
                p95=sorted(delays)[int(.95*(len(delays)-1))] if delays else 0,
                queue_delay=area/max(1,offered),pending=sum(map(len,q)),queue_growth=(sum(map(len,q))-q0)/(END-WARM),trace=trace)

def main():
    # Mechanical correctness checks with no cross traffic and no randomized demand.
    e=[(10.,0),(10.,2),(10.,1)]
    a=run(e,'batch');assert a['pending']==0
    for policy in ('signal','fcfs','batch'):
        assert run([(1.,0)],policy)['pending']==0
    assert run([], 'batch')['pending']==0
    rows=[]
    for scenario,shares in [('balanced',(.25,)*4),('arterial',(.4,.1,.4,.1))]:
        for demand in (400,1200,2200,3000,3600,4400):
            train=[arrivals(demand,s,shares) for s in (101,102)]
            options=[(mn,mx,g) for mn in (3.,5.,8.) for mx in (20.,40.,60.) for g in (1.,2.)]
            best=min(options,key=lambda p:sum(run(e,'signal',minimum=p[0],maximum=p[1],gap=p[2])['queue_delay'] for e in train))
            for policy,h in [('signal',2.),('fcfs',2.),('batch',2.),('batch_short',1.)]:
                results=[run(arrivals(demand,s,shares),'batch' if policy=='batch_short' else policy,h=h,minimum=best[0],maximum=best[1],gap=best[2]) for s in range(8)]
                row=dict(scenario=scenario,demand=demand,policy=policy,headway=h,signal_params=str(best))
                for k in ('flow','delay','p95','queue_delay','pending','queue_growth'):
                    vals=[r[k] for r in results];row[k]=statistics.mean(vals);row[k+'_sd']=statistics.stdev(vals)
                rows.append(row)
    OUT.mkdir(exist_ok=True)
    with (OUT/'09-model.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    # Standalone vector plot, no third-party plotting or server.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="460" viewBox="0 0 1000 460"><rect width="1000" height="460" fill="white"/><style>text{font:14px sans-serif}</style><text x="35" y="25">Independent queue model: balanced four-way, straight only (8 seeds)</text>']
    colors={'signal':'#bb4433','fcfs':'#8877bb','batch':'#147788','batch_short':'#229944'}
    for panel,key,ymax,title in [(0,'flow',5000,'Realized departures (veh/h)'),(1,'queue_delay',500,'Queue integral / offered vehicles (s)')]:
        x0=65+panel*500;y0=370
        svg.append(f'<path d="M{x0},55 V{y0} H{x0+390}" stroke="black" fill="none"/><text x="{x0}" y="48">{title}</text>')
        for y in range(6):
            val=y*ymax/5; yy=y0-y*300/5
            svg.append(f'<text x="{x0-48}" y="{yy+5}">{val:.0f}</text>')
        for p,c in colors.items():
            data=[r for r in rows if r['scenario']=='balanced' and r['policy']==p]
            pts=' '.join(f'{x0+r["demand"]/5000*390},{y0-min(ymax,r[key])/ymax*300}' for r in data)
            svg.append(f'<polyline points="{pts}" stroke="{c}" stroke-width="3" fill="none"/>')
        for d in (0,1200,2400,3600,4800):svg.append(f'<text x="{x0+d/5000*390-15}" y="395">{d}</text>')
    for i,(p,c) in enumerate(colors.items()):svg.append(f'<text x="{40+i*240}" y="435" fill="{c}">{p}</text>')
    svg.append('</svg>');(OUT/'09-model.svg').write_text(''.join(svg))
    print('scenario demand policy flow queue_delay pending')
    for r in rows: print(r['scenario'],r['demand'],r['policy'],*(round(r[k],2) for k in ('flow','queue_delay','pending')))
def sensitivity():
    rows=[]
    for cross in (1.2,2.,3.,4.):
        for policy in ('signal','fcfs','batch'):
            results=[run(arrivals(3000,seed),policy,cross=cross) for seed in range(4)]
            rows.append(dict(cross=cross,policy=policy,
                             flow=statistics.mean(r['flow'] for r in results),
                             queue_delay=statistics.mean(r['queue_delay'] for r in results)))
    with (OUT/'09-sensitivity.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    for row in rows: print(row)

if __name__=='__main__':
    if '--sensitivity' in sys.argv: sensitivity()
    else: main()
