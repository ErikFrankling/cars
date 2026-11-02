#!/usr/bin/env python3
# Summarises Hamburg signal observations: green-start spacing, green, yellow, red-amber. Usage: hamburg_stats.py hamburg_raw.json OUT.json
import sys,json,datetime as dt,collections,statistics as st
D=json.load(open(sys.argv[1]));print('lights in register',D['lights'],'primary streams',D['streams'])
def ts(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
W=collections.defaultdict(list);Y=[];RA=[];empty=0;lights=set();nobs=0
for r in D['rows']:
    o=r['obs'];nobs+=len(o)
    if len(o)<20:empty+=1;continue
    t=[(ts(a),b) for a,b in o];starts=[];greens=[]
    for (a,x),(b,y) in zip(t,t[1:]):
        d=b-a
        if x==3:greens.append(d);starts.append(a)
        if x==2 and d<10:Y.append(d)
        if x==4 and d<6:RA.append(d)
    cy=[b-a for a,b in zip(starts,starts[1:]) if 10<b-a<400]
    if len(cy)<4:empty+=1;continue
    lights.add(r['light'])
    c50=st.median(cy);so=sorted(cy);iqr=so[int(.75*len(so))]-so[int(.25*len(so))]
    g=st.median(greens)
    W[r['win']].append((c50,iqr,g,g/c50,r['light'],max(cy)))
def q(x,p):x=sorted(x);return x[min(len(x)-1,int(p*len(x)))]
Out=dict(lights=D['lights'],streams=D['streams'],obs=nobs,sampled_lights_with_data=len(lights),empty_windows=empty)
for w,v in W.items():
    c=[a[0] for a in v];iq=[a[1] for a in v];s=[a[3] for a in v];g=[a[2] for a in v]
    Out[w]=dict(n=len(v),cycle_p10=q(c,.1),cycle_p50=q(c,.5),cycle_p90=q(c,.9),cycle_max=max(c),iqr_p50=q(iq,.5),fixed_share=round(sum(i<=2 for i in iq)/len(iq),3),green_p10=q(g,.1),green_p50=q(g,.5),green_p90=q(g,.9),gshare_p10=round(q(s,.1),3),gshare_p50=round(q(s,.5),3),gshare_p90=round(q(s,.9),3),hist=sorted(collections.Counter(int(round(x/10)*10) for x in c).items()))
Out['yellow_p50']=q(Y,.5);Out['redamber_p50']=q(RA,.5);json.dump(Out,open(sys.argv[2],'w'),indent=0);print(json.dumps(Out))
