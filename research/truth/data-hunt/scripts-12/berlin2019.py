# Berlin May 2019 cross-sections: network hourly flow and speed per weekday, day-to-day spread.
import csv,gzip,sys,collections,datetime as dt,json,statistics as st
path,out=sys.argv[1],sys.argv[2]
rows=collections.defaultdict(dict); sites=set(); hdr=None
with gzip.open(path,'rt',encoding='utf-8',errors='replace') as f:
    r=csv.reader(f,delimiter=';'); hdr=next(r); ix={h.strip():i for i,h in enumerate(hdr)}
    for x in r:
        try:
            s=x[ix['mq_name']];d=x[ix['tag']];h=int(x[ix['stunde']]);q=float(x[ix['q_kfz_mq_hr']]);v=float(x[ix['v_kfz_mq_hr']])
        except Exception: continue
        sites.add(s); rows[(d,h)][s]=(q,v)
days=sorted({k[0] for k in rows})
def parse(d):
    for fmt in('%d.%m.%Y','%Y-%m-%d'):
        try: return dt.datetime.strptime(d,fmt).date()
        except ValueError: pass
hol={dt.date(2019,5,1),dt.date(2019,5,30),dt.date(2019,5,31),dt.date(2019,5,8)}
wk=[d for d in days if parse(d) and parse(d).weekday() in(1,2,3) and parse(d) not in hol]
# balanced panel: sites with q>=0 in all 24 hours on all chosen days
panel=None
for d in wk:
    ss=None
    for h in range(24):
        c=set(rows.get((d,h),{}))
        ss=c if ss is None else ss&c
    panel=ss if panel is None else panel&ss
print('header',hdr); print('sites',len(sites),'days',len(days),'Tue-Thu',wk,'balanced panel',len(panel))
prof={}
for d in wk:
    p=[]
    for h in range(24):
        qs=[rows[(d,h)][s] for s in panel]
        Q=sum(q for q,_ in qs); V=[(q,v) for q,v in qs if v>0 and q>0]
        hm=sum(q for q,_ in V)/sum(q/v for q,v in V) if V else 0
        p.append((Q,round(hm,1)))
    prof[d]=p
ref=wk[len(wk)//2]
print('ref',ref)
print('hour flow speed (ref) | flow pct spread across Tue-Thu')
for h in range(24):
    fl=[prof[d][h][0] for d in wk]; sp=[prof[d][h][1] for d in wk]
    print(h,int(prof[ref][h][0]),prof[ref][h][1],'flow min/max',int(min(fl)),int(max(fl)),'cv%.1f'%(100*st.pstdev(fl)/st.mean(fl)),'spd',min(sp),max(sp))
tot={d:sum(q for q,_ in prof[d]) for d in wk}; print('daily totals',{d:int(v) for d,v in tot.items()})
json.dump({'sites':len(sites),'weekdays':wk,'panel':len(panel),'profile':prof},open(out,'w'))
