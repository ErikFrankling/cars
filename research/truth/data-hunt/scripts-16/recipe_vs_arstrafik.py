"""Recipe day (v2_day2) and old baseline against measured Arstrafik, by hour and road class. Skips role=test rows: they stay blind.
Usage: recipe_vs_arstrafik.py counts.csv edges.csv net.xml OUT.json"""
import collections as C, csv, json, re, statistics as S, sys, resource
resource.setrlimit(resource.RLIMIT_AS,(1800*1024**2,1800*1024**2))
count=C.defaultdict(float); edge_sites=C.defaultdict(set); role={}
for r in csv.DictReader(open(sys.argv[1])):
    if r['role']=='test' or r['day_type']!='weekday': continue
    h=int(float(r['t0_s'])//3600); count[(r['site'],r['edge'],h)]+=float(r['vehicles']); role[r['site']]=r['role']
sites={(s,e) for s,e,_ in count}; edges={e for _,e in sites}
sim=C.defaultdict(float)
for r in csv.DictReader(open(sys.argv[2])):
    if r['edge'] in edges: sim[(r['edge'],int(float(r['begin'])//3600))]+=float(r['entered'])
typ={}
for l in open(sys.argv[3],errors='replace'):
    s=l.lstrip()
    if s.startswith('<edge ') and 'function="' not in s:
        m=re.search(r' id="([^"]*)"',s); t=re.search(r' type="([^"]*)"',s)
        if m[1] in edges: typ[m[1]]=(t[1].split('.')[-1].replace('_link','') if t else 'none')
hm=[0.]*24; hs=[0.]*24; bycl=C.defaultdict(lambda:[0.,0.,0.]); err=0.; obs=0.; geh=[]
persite=C.defaultdict(lambda:[[0.]*24,[0.]*24])
for (s,e,h),v in count.items():
    x=sim.get((e,h),0.); hm[h]+=v; hs[h]+=x; err+=abs(x-v); obs+=v
    c=typ.get(e,'none'); bycl[c][0]+=v; bycl[c][1]+=x; bycl[c][2]+=abs(x-v)
    geh.append((2*(x-v)**2/max(x+v,1))**.5)
    persite[(s,e)][0][h]=v; persite[(s,e)][1][h]=x
out={'site_directions':len(sites),'rows':len(count),'observed':round(obs),'simulated':round(sum(hs)),'ratio':round(sum(hs)/obs,3),'wape':round(err/obs,3),'hourly_geh_lt5':round(sum(g<5 for g in geh)/len(geh),3)}
out['hour_ratio']=[round(hs[h]/max(hm[h],1),2) for h in range(24)]
out['hour_share_measured_pct']=[round(100*x/sum(hm),2) for x in hm]; out['hour_share_sim_pct']=[round(100*x/sum(hs),2) for x in hs]
out['by_class']={c:dict(rows_observed=round(v[0]),ratio=round(v[1]/max(v[0],1),3),wape=round(v[2]/max(v[0],1),3)) for c,v in sorted(bycl.items())}
rm=[];rs=[];site_ratio=[];shape=[]
for (s,e),(m,x) in persite.items():
    if sum(m)<3000: continue
    site_ratio.append(sum(x)/sum(m))
    am=max(m[6:10]);pm=max(m[14:19]);ax=max(x[6:10]);px=max(x[14:19])
    if pm>0 and px>0 and sum(x)>500: rm.append(am/pm); rs.append(ax/px)
    if sum(x)>500: shape.append(sum(abs(m[h]/sum(m)-x[h]/sum(x)) for h in range(24))/2)
q=lambda a:[round(S.quantiles(a,n=10)[i],2) for i in(0,4,8)]
out.update(busy_sites=len(site_ratio),site_daily_ratio_q10_50_90=q(site_ratio),within_20pct=round(sum(.8<=x<=1.2 for x in site_ratio)/len(site_ratio),3),am_pm_measured_q10_50_90=q(rm),am_pm_sim_q10_50_90=q(rs),shape_distance_q10_50_90=q(shape))
if len(rm)>2:
    mx,my=S.mean(rm),S.mean(rs); out['am_pm_corr_site']=round(sum((a-mx)*(b-my) for a,b in zip(rm,rs))/(sum((a-mx)**2 for a in rm)*sum((b-my)**2 for b in rs))**.5,3)
json.dump(out,open(sys.argv[4],'w'),indent=1); print(json.dumps(out))
