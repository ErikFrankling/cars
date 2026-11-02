# Scores detections against hand labels within road corridors, and compares counts with flow/speed from measured Arstrafik.
# Hand labels are displayed-image coordinates (scale 2048/1932). Labelled by the agent from brightened raw images before scoring.
import json,sys,math,os
base=sys.argv[1]
SC=2048/1932
SITES={
'essingeleden_kristineberg':dict(hw=85,line=[(1055,0),(1050,200),(1030,400),(1005,600),(975,800),(950,1000),(950,1200),(950,1400),(950,1600),(965,1932)],
  gt=[(1036,130),(1094,145),(1040,357),(1075,367),(1052,385),(1025,552),(1040,602),(990,712),(1006,767),(975,900),(995,910),(932,970),(968,1075),(923,1088),(905,1122),(980,1285),(998,1278),(923,1367),(985,1376),(1003,1420),(928,1520),(945,1518),(1012,1560),(937,1634),(955,1693),(958,1925)],hour=9,v=70,vsrc='posted limit assumed',flow='TS 08 both directions',sites=[('TS 08',2025,'Med'),('TS 08',2025,'Mot')]),
'johanneshovsbron':dict(hw=70,line=[(460,0),(700,640),(850,900),(1000,1250),(1130,1450),(1300,1680),(1450,1932)],
  gt=[(535,290),(660,412),(660,547),(650,582),(707,672),(1090,1315),(1030,1357),(1300,1672)],hour=10,v=60,vsrc='assumed 50-70',flow='TS 04 both directions',sites=[('TS 04',2025,'Mot'),('TS 04',2025,'Med')]),
'klarastrandsleden':dict(hw=60,line=[(0,760),(500,890),(1000,985),(1500,1085),(1932,1180)],
  gt=[(57,760),(387,857),(525,915),(577,905),(703,930),(948,972),(1040,1012),(1095,998),(1240,1050),(1297,1037),(1553,1085),(1703,1120),(1732,1155),(1893,1178)],hour=10,v=47,vsrc='measured 2024 site 01035253',flow='TS 10 total',sites=[('TS 10',2025,'Båda')]),
'drottningholmsvagen':dict(hw=75,line=[(0,650),(1932,1215)],gt=[(190,712),(415,723),(335,776),(1025,905),(1510,1048),(1570,1120)],hour=9,v=65,vsrc='measured',flow='06230103 both',sites=[('06230103',2025,'Mot'),('06230103',2025,'Med')]),
'stadsgardsleden':dict(hw=85,line=[(0,640),(500,840),(900,1000),(1300,1130),(1932,1290)],gt=[(65,590),(918,1021),(1250,1105),(1440,1160),(1567,1215),(1638,1210),(1755,1236),(1785,1270),(1775,1288),(1915,1268)],hour=10,v=35,vsrc='measured',flow='03160897 total',sites=[('03160897',2025,'Båda')]),
'hornsgatan':dict(hw=95,line=[(0,1255),(1932,675)],gt=[(x/SC,y/SC) for x,y in[(816,1102),(498,1195),(246,1272),(154,1333),(117,1346),(63,1363),(31,1372),(3,1381),(179,1292),(1886,731),(1829,767),(1766,808),(1556,873)]],hour=10,v=35,vsrc='measured',flow='03090203 total',sites=[('03090203',2025,'Båda')]),
'sveavagen':dict(hw=85,line=[(730,620),(880,850),(1000,1150),(1100,1450),(1240,1932)],gt=[(x/SC,y/SC) for x,y in[(759,669),(835,682),(852,677),(869,711),(859,731),(937,756),(905,799),(852,824),(839,835),(926,903),(1065,1138),(1011,1240),(1155,1452),(1293,1907)]],hour=10,v=34,vsrc='measured',flow='0115X001 total',sites=[('0115X001',2025,'Båda')]),
}
def seg(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)));return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def dist(p,L): return min(seg(p,L[i],L[i+1]) for i in range(len(L)-1))
rows=json.load(open(base+'/caps/central_sites.json'))
def flow(s,h):
    tot=0;tot2=[]
    for site,y,d in s['sites']:
        c=[r for r in rows if r['site']==site and r['year']==y and r['dir']==d]
        c.sort(key=lambda r:-r['days']);tot+=c[0]['h'][h];tot2.append(c[0]['days'])
    return tot,min(tot2)
res={}
for tag,g in(('det016',.16),('det032',.32),('det050',.50)):
    agg={}
    for th in(.25,.3,.4,.5,.6):
        TP=FP=FN=0;per={}
        for n,s in SITES.items():
            f=f'{base}/{tag}/{n}.json'
            if not os.path.exists(f): continue
            D=[d for d in json.load(open(f)) if d['s']>=th and dist((d['x']/SC,d['y']/SC),s['line'])<=s['hw']]
            G=[(x*SC,y*SC) for x,y in s['gt']];used=set();tp=0
            for d in sorted(D,key=lambda d:-d['s']):
                b=None;bd=22
                for i,q in enumerate(G):
                    if i in used: continue
                    dd=math.hypot(d['x']-q[0],d['y']-q[1])
                    if dd<bd: bd=dd;b=i
                if b is not None: used.add(b);tp+=1
            fp=len(D)-tp;fn=len(G)-tp;TP+=tp;FP+=fp;FN+=fn
            per[n]=dict(gt=len(G),det=len(D),tp=tp,fp=fp,fn=fn)
        agg[th]=dict(tp=TP,fp=FP,fn=FN,recall=round(TP/max(TP+FN,1),3),precision=round(TP/max(TP+FP,1),3),per=per)
        print(tag,th,'TP',TP,'FP',FP,'FN',FN,'R',agg[th]['recall'],'P',agg[th]['precision'],'count/gt',round((TP+FP)/max(TP+FN,1),3))
    res[tag]=agg
print()
tab=[]
for n,s in SITES.items():
    L=sum(math.hypot(s['line'][i+1][0]-s['line'][i][0],s['line'][i+1][1]-s['line'][i][1]) for i in range(len(s['line'])-1))*SC*.16
    q,dd=flow(s,s['hour']);exp=q/s['v']*L/1000;G=len(s['gt'])
    D=res['det016'][.3]['per'][n]['det'] if n in res['det016'][.3]['per'] else None
    r=dict(site=n,L_m=round(L),hour=s['hour'],weekday_flow_vph=q,meas_days=dd,v_kmh=s['v'],v_source=s['vsrc'],expected_weekday=round(exp,1),hand=G,detector_t03=D,hand_over_expected=round(G/exp,2),poisson_sd_hand=round(G**.5,1))
    tab.append(r);print(r)
tot_h=sum(r['hand'] for r in tab);tot_e=sum(r['expected_weekday'] for r in tab)
print('sum hand',tot_h,'sum expected',round(tot_e,1),'ratio',round(tot_h/tot_e,2))
json.dump(dict(score=res,table=tab),open(base+'/evaluation.json','w'),indent=1)
