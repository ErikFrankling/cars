# Spatial match of v6.4 calibration count stations (network links) to Berlin public detector cross-sections.
import gzip,sys,re,csv,json,zipfile,math,collections
countsp,geomp,stammp,mqp,out=sys.argv[1:6]
def ll2utm(lat,lon,zone=32):
    a=6378137.0;f=1/298.257222101;k0=0.9996;e2=f*(2-f);ep=e2/(1-e2)
    la=math.radians(lat);lo=math.radians(lon);l0=math.radians(zone*6-183)
    N=a/math.sqrt(1-e2*math.sin(la)**2);T=math.tan(la)**2;C=ep*math.cos(la)**2;A=(lo-l0)*math.cos(la)
    M=a*((1-e2/4-3*e2**2/64-5*e2**3/256)*la-(3*e2/8+3*e2**2/32+45*e2**3/1024)*math.sin(2*la)+(15*e2**2/256+45*e2**3/1024)*math.sin(4*la)-(35*e2**3/3072)*math.sin(6*la))
    x=k0*N*(A+(1-T+C)*A**3/6+(5-18*T+T*T+72*C-58*ep)*A**5/120)+500000
    y=k0*(M+N*math.tan(la)*(A*A/2+(5-T+9*C+4*C*C)*A**4/24+(61-58*T+T*T+600*C-330*ep)*A**6/720))
    return x,y
xml=gzip.open(countsp,'rt',encoding='utf8').read()
locs=dict(re.findall(r'<location refId="([^"]+)" name="([^"]+)"',xml))
geom={}
with open(geomp,newline='') as f:
    r=csv.DictReader(f); print('geom fields',r.fieldnames)
    idk=r.fieldnames[0]; gk=r.fieldnames[-1]
    for row in r:
        if row[idk] in locs: geom[row[idk]]=row[gk]
print('count links',len(locs),'with geometry',len(geom),'sample',list(geom.items())[:1])
def pts(s):
    n=[float(x) for x in re.findall(r'-?\d+\.\d+|-?\d+',s)]
    return list(zip(n[0::2],n[1::2]))
cp=[]
for k,g in geom.items():
    p=pts(g)
    if len(p)>=1:
        x0,y0=p[0];x1,y1=p[-1]; cp.append((k,p,math.atan2(y1-y0,x1-x0)))
z=zipfile.ZipFile(stammp)
ss=[re.sub(r'<[^>]+>','',m) for m in re.findall(r'<si>(.*?)</si>',z.read('xl/sharedStrings.xml').decode('utf8'),re.S)]
rows=[]
for r in re.findall(r'<row [^>]*>(.*?)</row>',z.read('xl/worksheets/sheet1.xml').decode('utf8'),re.S):
    row={}
    for ref,attrs,v in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<f>.*?</f>)?<v>(.*?)</v>',r,re.S):
        row[ref]=ss[int(v)] if 't="s"' in attrs else v
    rows.append(row)
mqpos={}
for r in rows[1:]:
    try: mqpos.setdefault(r['A'],(float(r['M']),float(r['L']),r.get('F',''),r.get('I','')))
    except (KeyError,ValueError): pass
active=set()
with gzip.open(mqp,'rt',errors='replace') as f:
    rd=csv.reader(f,delimiter=';');next(rd)
    for x in rd: active.add(x[0])
head={'Nord':90,'Nordost':45,'Ost':0,'Südost':-45,'Süd':-90,'Südwest':-135,'West':180,'Nordwest':135}
res=[]
for m in sorted(active):
    if m not in mqpos: res.append((m,None,None,None,'?','?'));continue
    lat,lon,st,di=mqpos[m];x,y=ll2utm(lat,lon);best=(1e12,None);bestdir=(1e12,None)
    for k,p,ang in cp:
        d=min(math.hypot(x-a,y-b) for a,b in p)
        if d<best[0]:best=(d,k)
        if di in head:
            dang=abs((math.degrees(ang)-head[di]+180)%360-180)
            if dang<=60 and d<bestdir[0]: bestdir=(d,k)
    res.append((m,round(best[0]),locs.get(best[1]),round(bestdir[0]) if bestdir[1] else None,st,di))
import statistics as s
d=[r[1] for r in res if r[1] is not None]; dd=[r[3] for r in res if r[3] is not None]
print('active MQ',len(active),'with position',len(d),'median nearest count link m (any direction)',s.median(d))
for t in (50,100,200,300,500,1000):
    print('within',t,'m any dir',sum(x<=t for x in d),'same dir',sum(x<=t for x in dd))
print('sample far',[r for r in res if r[1] and r[1]>1000][:8])
print('sample near',[r for r in res if r[1] is not None and r[1]<=50][:6])
json.dump(res,open(out,'w'),ensure_ascii=False,indent=0)
