# Streams the cached Arstrafik GeoJSON, keeps recent measured directional records in central Stockholm. Low memory.
import json,sys
src,dst=sys.argv[1],sys.argv[2]
LON=(17.97,18.11);LAT=(59.30,59.36)
sep='{"type":"Feature",'
buf='';rows=[];n=0
def handle(t):
    global n
    t=t.rstrip().rstrip(',').rstrip(']}').rstrip() if False else t
    d=json.JSONDecoder()
    o,_=d.raw_decode(t);n+=1
    p=o['properties'];end=int(p['datum_för_slut_av_perioden'][:4])
    if end<2022 or p.get('metod_för_datainsamling')!='Uppmätt': return
    c=o['geometry']['coordinates']
    flat=[x for l in c for x in l]
    lon=sum(x[0] for x in flat)/len(flat);lat=sum(x[1] for x in flat)/len(flat)
    if not(LON[0]<lon<LON[1] and LAT[0]<lat<LAT[1]): return
    h=[p.get(f'trafikflöde_{i:02d}-{i+1:02d}__fordon_dygn__alla_fordon') or 0 for i in range(24)]
    v=[p.get(f'trafikflöde_{i:02d}-{i+1:02d}__fordon_dygn__tunga_fordon') or 0 for i in range(24)]
    rows.append(dict(site=p['mätplats'],name=p['namn'],year=end,dir=p.get('riktning'),split=p.get('riktningsuppdelad'),days=p['antal_mätdygn'],adt=sum(h),h=h,heavy=v,v_mean=p.get('hastighet_medel'),v_p85=p.get('hastighet_85-percentil'),lon=round(lon,6),lat=round(lat,6),geom=c,nvdb=p.get('nvdb_key')))
with open(src,encoding='utf8') as f:
    while True:
        b=f.read(1<<22)
        if not b: break
        buf+=b
        parts=buf.split(sep)
        buf=parts.pop()
        for t in parts:
            if t.strip().startswith('{') or t.strip()=='' : continue
            handle(sep+t)
    if buf: handle(sep+buf)
print(n,'features;',len(rows),'kept')
json.dump(rows,open(dst,'w'),ensure_ascii=False)
seen=set()
rows.sort(key=lambda r:-r['adt'])
for r in rows:
    k=(r['site'],r['year'],r['dir'])
    if k in seen or r['days']<3: continue
    seen.add(k)
    if len(seen)<=70: print(r['adt'],r['days'],r['year'],r['site'],r['name'][:70],r['dir'],'h10',r['h'][10],'hv10',r['heavy'][10],'v',r['v_mean'],r['lon'],r['lat'])
