# Logs chosen Trafik Stockholm cameras: one GET each per interval, saves a new JPEG only when PhotoTime changes. Stops by itself after --minutes.
import json,sys,time,os,urllib.request,argparse,re
a=argparse.ArgumentParser();a.add_argument('--inventory');a.add_argument('--out');a.add_argument('--names',default='');a.add_argument('--minutes',type=float,default=5);a.add_argument('--every',type=float,default=15);A=a.parse_args()
R=json.load(open(A.inventory));names=[n for n in A.names.split(',') if n]
C=[r for r in R if any(n.lower() in r['name'].lower() for n in names)] if names else R
os.makedirs(A.out,exist_ok=True);last={};log=open(A.out+'/log.jsonl','a');t_end=time.time()+A.minutes*60;n=0
while time.time()<t_end:
    t0=time.time()
    for c in C:
        try:
            with urllib.request.urlopen(urllib.request.Request(c['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as f:
                b=f.read();pt=f.headers.get('phototime')
            if pt!=last.get(c['cam']):
                last[c['cam']]=pt
                fn=f"{c['cam']}_{re.sub('[^0-9]','',pt)}.jpg";open(f'{A.out}/{fn}','wb').write(b);n+=1
                log.write(json.dumps(dict(cam=c['cam'],name=c['name'],phototime=pt,fetched=time.time(),bytes=len(b)),ensure_ascii=False)+'\n');log.flush()
        except Exception as e: log.write(json.dumps(dict(cam=c['cam'],err=str(e)[:80]))+'\n')
    time.sleep(max(0,A.every-(time.time()-t0)))
print('frames',n,'cams',len(C))
