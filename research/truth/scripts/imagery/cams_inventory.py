# Fetches each Trafik Stockholm camera once in sequence (1 per 0.2 s), saves images and metadata.
import re,json,sys,time,os,urllib.request,math
html,out=sys.argv[1],sys.argv[2]
s=open(html,encoding='utf8',errors='replace').read()
i=s.find('{"cameras":[');dec=json.JSONDecoder();o,_=dec.raw_decode(s[i:])
cams={}
for c in o['cameras']: cams.setdefault(c['imageUrl'],c)
os.makedirs(out,exist_ok=True);rows=[]
for u,c in cams.items():
    n=re.search(r'TrafficFlowCamera_(\d+)',u);n=n.group(1) if n else c['cameraId']
    r={'cam':n,'id':c['cameraId'],'name':c['name'],'road':c['road'],'pos':c['wgs84Position']['coordinates'],'url':u}
    try:
        q=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(q,timeout=20) as f:
            b=f.read();r.update(status=f.status,bytes=len(b),phototime=f.headers.get('phototime'),lastmod=f.headers.get('last-modified'))
        open(f'{out}/{n}.jpg','wb').write(b)
    except Exception as e: r['status']=str(e)[:80]
    rows.append(r);time.sleep(.2)
json.dump(rows,open(f'{out}/inventory.json','w'),ensure_ascii=False,indent=0)
print(len(rows))
