"""Stream SySMo Activity_travel.csv. Writes car-driver trips touching the study box, plus kommun commuting and hourly profiles. usage: sysmo_extract.py Activity.csv Person.csv OUT.npz"""
import sys,csv,numpy as np,collections as C,json,time
X0,Y0=651972.09,6565003.78
BX=(X0-60000,X0+95000,Y0-60000,Y0+90000)  # about 60 km beyond the net in every direction
K={};home={}
t0=time.time()
kom=C.Counter()
with open(sys.argv[2]) as f:
    r=csv.reader(f);next(r)
    for row in r:
        kom[row[9][:4]]+=1
print('persons',sum(kom.values()),time.time()-t0,flush=True)
def flush(buf,chunks):
    if buf:
        chunks.append(np.array(buf,dtype=np.float32));buf.clear()
buf=[];chunks=[];pidb=[];pc=[]
cm=C.Counter();cmcar=C.Counter();hours=C.Counter();purp=C.Counter();modec=C.Counter();persons_with=C.Counter();tripkm=C.Counter();pers_car=C.Counter()
PUR={'Home':0,'Work':1,'School':2,'Other':3}
n=0;last=None;prev=None;homek=None;workdone=False;ncar=0;all_ok=True
pc=[]
kcode={}
def kid(s):
    if s not in kcode: kcode[s]=len(kcode)
    return kcode[s]
cur=None;px=py=pe=pk=None;ph=None
with open(sys.argv[1]) as f:
    f.readline()
    for line in f:
        n+=1
        a=line.rstrip('\n').split(',')
        pid=a[0]
        if len(a)!=11: raise SystemExit(('bad row',line))
        x,y=float(a[8]),float(a[9]);st=float(a[3]);en=float(a[4]);pu=a[2];mo=a[5];k=a[10][:4]
        if pid!=cur:
            cur=pid;homek=k if pu=='Home' else None;workdone=False;px,py,pe,pk=x,y,en,k
            if homek is None and pu=='Home': homek=k
            if len(a)>0: persons_with[k]+=1
            first=True
            ph=pu
        else:
            modec[mo]+=1
            if pu=='Home' and homek is None: homek=k
            if pu=='Work' and not workdone:
                workdone=True
                if homek: cm[(homek,k)]+=1
                if homek and mo=='Car': cmcar[(homek,k)]+=1
            if mo=='Car':
                purp[pu]+=1
                h=int(pe%24);hours[h]+=1
                d=((x-px)**2+(y-py)**2)**.5
                tripkm[pk]+=d/1000
                pers_car[pk]+=1
                ok=(BX[0]<=px<=BX[1] and BX[2]<=py<=BX[3]) or (BX[0]<=x<=BX[1] and BX[2]<=y<=BX[3])
                if ok:
                    buf.append((px,py,x,y,pe,st,PUR.get(pu,3),PUR.get(ph,3),kid(pk),kid(k),kid(homek or '0000')))
                    if len(buf)>=500000:
                        flush(buf,chunks);print(n,len(chunks),time.time()-t0,flush=True)
            px,py,pe,pk=x,y,en,k;ph=pu
flush(buf,chunks)
A=np.concatenate(chunks);print('rows',n,'car trips kept',len(A),time.time()-t0)
np.savez_compressed(sys.argv[3],A=A,kcode=np.array(list(kcode.keys())))
json.dump(dict(rows=n,pop=kom,cm={f'{a}|{b}':c for (a,b),c in cm.items()},cmcar={f'{a}|{b}':c for (a,b),c in cmcar.items()},hours=hours,purp=purp,mode=modec,tripkm=tripkm,cartrips=pers_car),open(sys.argv[3]+'.json','w'))
print(modec,purp)
