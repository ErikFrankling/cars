# Streams Xuancheng virtual loop.csv: network hourly flow and speed per day, day-to-day spread.
import csv,sys,collections,statistics as st
F=collections.defaultdict(lambda:[0]*24);S=collections.defaultdict(lambda:[0.0]*24);dets=set()
with open(sys.argv[1],newline='') as f:
    r=csv.reader(f);h=[x.strip() for x in next(r)];i={k:n for n,k in enumerate(h)}
    for x in r:
        try: t=x[i['FTIME']];d=t[:10];hr=int(t[11:13]);c=float(x[i['COUNT']]);v=float(x[i['HARM_SPD']])
        except (ValueError,IndexError): continue
        dets.add(x[i['DET_ID']]);F[d][hr]+=c
        if v>0:S[d][hr]+=c/v
days=sorted(F);print('detectors',len(dets),'days',len(days),days[0],days[-1])
print('daily totals',{d[5:]:int(sum(F[d])) for d in days})
wk=[d for d in days if __import__('datetime').date.fromisoformat(d).weekday() in(1,2,3)]
for h in (3,7,8,12,17,18,22):
    fl=[F[d][h] for d in wk];sp=[3.6*F[d][h]/S[d][h] for d in wk if S[d][h]>0]
    print(h,'flow mean %d cv %.1f%%'%(st.mean(fl),100*st.pstdev(fl)/st.mean(fl)),'speed km/h mean %.1f min %.1f max %.1f'%(st.mean(sp),min(sp),max(sp)))
