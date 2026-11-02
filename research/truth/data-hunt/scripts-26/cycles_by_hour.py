#!/usr/bin/env python3
# Cycle length and green share by local hour from hamburg-signals day files. Usage: cycles_by_hour.py ROOT [light ...]
import sys,gzip,glob,collections,statistics as st,datetime as dt
from zoneinfo import ZoneInfo
root=sys.argv[1];only=set(sys.argv[2:]);tz=ZoneInfo('Europe/Berlin')
seq=collections.defaultdict(list)
for f in sorted(glob.glob(root+'/days/*.tsv.gz')):
    for line in gzip.open(f,'rt'):
        p=line.rstrip('\n').split('\t')
        if len(p)<5 or p[1]!='primary_signal' or (only and p[0] not in only):continue
        t=dt.datetime.strptime(p[3],'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc).timestamp()
        seq[(p[0],p[2])].append((t,p[4]))
H=collections.defaultdict(lambda:collections.defaultdict(list));seen=set()
for (l,s),o in seq.items():
    o=sorted(set(o));gs=[]
    for i in range(1,len(o)):
        if o[i][1]=='3' and o[i-1][1] not in '356':
            j=i+1
            while j<len(o) and o[j][1] in '36':j+=1
            gs.append((o[i][0],(o[j][0]-o[i][0]) if j<len(o) else None))
    for (a,g),(b,_) in zip(gs,gs[1:]):
        if not 20<=b-a<=300 or g is None or g>b-a:continue
        d=dt.datetime.fromtimestamp(a,tz);key=(d.weekday()>=5,d.hour)
        H[key]['cyc'].append((l,s,b-a,g/(b-a)));seen.add((l,s))
def q(x,p):x=sorted(x);return x[min(len(x)-1,int(p*len(x)))]
print('connections',len(seen),'lights',len({l for l,_ in seen}))
print('daytype hour n_cycles median p10 p90 per-conn-spread(median IQR) greenshare p10 p50 p90')
for k in sorted(H):
    c=[v[2] for v in H[k]['cyc']];gsr=[v[3] for v in H[k]['cyc']];bc=collections.defaultdict(list)
    for l,s,v,_ in H[k]['cyc']:bc[(l,s)].append(v)
    iq=[q(v,.75)-q(v,.25) for v in bc.values() if len(v)>=4]
    print('weekend' if k[0] else 'weekday',k[1],len(c),round(st.median(c)),q(c,.1),q(c,.9),round(st.median(iq),1) if iq else '-',round(q(gsr,.1),2),round(st.median(gsr),2),round(q(gsr,.9),2))
