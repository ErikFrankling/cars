"""One line of metrics per factorial run. usage: sthlm_metrics.py RUN [RUN...] (dir names under factorial/)."""
import sys,csv,gzip,re,json,collections,os
from pathlib import Path
T=Path('/home/erikf/projects/personal/cars-data/truth/stockholm/factorial')
sched_cache={}
def schedule(path):
    if path in sched_cache: return sched_cache[path]
    h=collections.Counter();rx=re.compile(r'depart="([\d.]+)"');o=gzip.open if path.endswith('.gz') else open
    with o(path,'rt') as f:
        for l in f:
            if l.startswith('<vehicle'): h[int(float(rx.search(l)[1])//60)]+=1
    sched_cache[path]=h;return h
def run(name):
    d=T/name;cfg=dict(x.split('=',1) for x in (d/'config.txt').read_text().split('\n')[0].split(' ') if '=' in x and x.split('=')[0] in('net','routes','begin','end'))
    end=float(cfg['end']);S=schedule(cfg['routes'])
    rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(open(d/'summary.csv'))]
    cum=collections.Counter();c=0
    for m in range(int(end//60)+2):
        c+=S[m];cum[m]=c
    first=next((r['time'] for r in rows if r['teleports']>0),None)
    hrs=collections.defaultdict(dict);back=0;peak=0;vh=0
    prev=None
    for r in rows:
        b=cum[int(r['time']//60)-1]-r['inserted'];back+=max(b,0)*60/3600;peak=max(peak,r['running']);vh+=r['running']*60/3600
        h=int((r['time']-1)//3600);hrs[h]=dict(run=r['running'],ins=r['inserted'],arr=r['arrived'],tp=r['teleports'],backlog=b)
    hours=sorted(hrs);lock=None;p=dict(ins=0,tp=0);byh={}
    for h in hours:
        q=hrs[h];di=q['ins']-p['ins'];dt=q['tp']-p['tp'];byh[h]=dict(ins=di,tp=dt,run=q['run'],backlog=q['backlog'])
        if lock is None and di>500 and dt/max(di,1)>=0.01: lock=h
        p=q
    last=rows[-1]
    sd=collections.Counter();ss=collections.Counter()
    for r in csv.DictReader(open(d/'edges.csv')):
        h=int(float(r['begin'])//3600);sd[h]+=float(r['distance']);ss[h]+=float(r['samples'])
    spd={h:sd[h]/ss[h]*3.6 for h in ss if ss[h]}
    wait=loss=dur=n=0;dist=0
    for r in csv.DictReader(open(d/'trips.csv')):
        n+=1;dur+=float(r['duration']);wait+=float(r['waiting']);loss+=float(r['time_loss']);dist+=float(r['route_length'])
    tot=sum(ss.values());dtot=sum(sd.values())
    lg=(d/'log.txt').read_text() if (d/'log.txt').exists() else ''
    m=re.search(r'teleports (\d+), collisions (\d+) .*?teleports jam (\d+) yield (\d+) wrong lane (\d+)',lg)
    return dict(name=name,end=end,scheduled=cum[int(end//60)],inserted=last['inserted'],arrived=last['arrived'],running=last['running'],peak_running=peak,
      teleports=last['teleports'],tp_per_1k=last['teleports']/max(last['inserted'],1)*1000,first_tp=first,lock_hour=lock,backlog_end=cum[int(end//60)]-last['inserted'],backlog_veh_h=back,veh_h=vh,
      speed=dtot/max(tot,1)*3.6,mean_loss=loss/max(n,1),mean_wait=wait/max(n,1),mean_dur=dur/max(n,1),mean_len=dist/max(n,1),vkm=dtot/1000,
      jam=int(m[3]) if m else None,yield_=int(m[4]) if m else None,wrong=int(m[5]) if m else None,collisions=int(m[2]) if m else None,by_hour=byh,speed_by_hour=spd)
if __name__=='__main__':
    res=[run(a) for a in sys.argv[1:]]
    keys=['name','inserted','arrived','running','peak_running','teleports','tp_per_1k','first_tp','lock_hour','backlog_end','speed','mean_loss','mean_wait','mean_len','jam','yield_','wrong','collisions']
    print(' | '.join(keys))
    for r in res: print(' | '.join(f'{r[k]:.1f}' if isinstance(r[k],float) else str(r[k]) for k in keys))
    p=T/'metrics.jsonl'
    with open(p,'a') as w:
        for r in res: w.write(json.dumps(r)+'\n')
