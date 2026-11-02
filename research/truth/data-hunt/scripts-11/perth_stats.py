# Summarises Perth SCATS phase history from parquet. Usage: perth_stats.py DIR SITEPATHS
import sys
sys.path[:0]=[p for p in sys.argv[2].split(':') if p]
import glob,collections,statistics as st,json
import pyarrow.parquet as pq
R=[];shown=False
for f in sorted(glob.glob(sys.argv[1]+'/*.parquet')):
    try:t=pq.read_table(f)
    except Exception:continue
    if not shown:
        print(t.schema.names);print({k:str(v)[:40] for k,v in t.slice(0,1).to_pylist()[0].items()});shown=True
    names=t.column_names
    def col(*c):
        for x in c:
            if x in names:return x
    ts=col('Timestamp','TIMESTAMP','timestamp');cy=col('Actual Cycle Time');ph=[col(f'Phase Time {L}') for L in 'ABCDEFG']
    if not(ts and cy):continue
    d=t.select([ts,cy]+[p for p in ph if p]).to_pylist();seen=set();b=collections.defaultdict(list)
    for r in d:
        k=r[ts]
        if k in seen:continue
        seen.add(k)
        if not r[cy]:continue
        h=k.hour;wd=k.weekday()
        tag='peak' if wd<5 and h in(7,8,16,17) else 'night' if h<5 else 'day' if 9<=h<16 else 'other'
        b[tag].append(r)
    if len(seen)<100:continue
    o=dict(f=f.split('/')[-1],n=len(seen))
    for tag,x in b.items():
        c=sorted(r[cy] for r in x);o[tag+'_c50']=c[len(c)//2];o[tag+'_c90']=c[int(.9*len(c))];o[tag+'_c10']=c[int(.1*len(c))]
        o[tag+'_ph']=st.median(sum(1 for p in ph if p and (r.get(p) or 0)>0) for r in x)
        if tag=='peak':
            o['maxshare']=st.median(max((r.get(p) or 0) for p in ph if p)/r[cy] for r in x)
    R.append(o)
json.dump(R,open(sys.argv[1]+'/perth_summary.json','w'),indent=0)
for tag in('peak','day','night'):
    v=sorted(r[tag+'_c50'] for r in R if tag+'_c50' in r)
    if v:print(tag,'sites',len(v),'median cycle p10/50/90',v[int(.1*len(v))],v[len(v)//2],v[int(.9*len(v))],'median phases',st.median(r[tag+'_ph'] for r in R if tag+'_ph' in r))
print('peak largest phase share',st.median(r['maxshare'] for r in R if 'maxshare' in r))
print('peak cycle within-site p10-p90 spread',st.median(r['peak_c90']-r['peak_c10'] for r in R if 'peak_c90' in r))
