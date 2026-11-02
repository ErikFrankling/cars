"""Keep only `calibrate` sites, 2023 and 2024. Held-out rows are dropped before any value is read. usage: arstrafik_cal.py body holdout.csv OUT.csv"""
import sys,csv,json,re,collections as C
role={r['site']:r for r in csv.DictReader(open(sys.argv[2],encoding='utf-8'))}
keep={k for k,r in role.items() if r['role']=='calibrate'}
H=[f'trafikflöde_{i:02d}-{i+1:02d}__fordon_dygn__' for i in range(24)]
out=C.defaultdict(list);n=0;dropped=0
buf='';f=open(sys.argv[1],encoding='utf-8');sep='{"type":"Feature"'
def do(t):
    global n,dropped
    t=t.rstrip().rstrip(',').rstrip(']}').rstrip()
    m=re.search(r'"mätplats":"([^"]+)"',t)
    if not m: return
    s=m[1]
    if s not in keep: dropped+=1;return
    y=re.search(r'"datum_för_slut_av_perioden":"(\d{4})',t)
    if not y or y[1] not in('2023','2024'): return
    p=t[t.index('"properties":')+13:]
    try: d=json.loads(p[:p.rindex('}')+1])
    except Exception: return
    if (d.get('antal_mätdygn') or 0)<5: return
    a=sum(d.get(h+'alla_fordon') or 0 for h in H);h=sum(d.get(h+'tunga_fordon') or 0 for h in H);n+=1
    amax=sum((d.get(H[i]+'alla_fordon') or 0) for i in (6,7,8));out[s].append((y[1],d.get('riktning'),a,h,d.get('antal_mätdygn'),d.get('namn','')))
while True:
    c=f.read(1<<22)
    if not c: break
    buf+=c;parts=buf.split(sep);buf=parts.pop()
    for t in parts: do(t)
do(buf)
print('kept features',n,'dropped non-calibrate',dropped,'sites',len(out))
w=csv.writer(open(sys.argv[3],'w',newline='',encoding='utf-8'));w.writerow(['site','name','lon','lat','year','dir','adt','heavy','days'])
for s,v in out.items():
    r=role[s]
    for y,di,a,h,dy,nm in v: w.writerow([s,r['name'],r['lon'],r['lat'],y,di,a,h,dy])
