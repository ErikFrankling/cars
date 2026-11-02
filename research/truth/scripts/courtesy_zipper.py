"""Turn taking at the I-80 on-ramp: order of ramp and main-lane cars through the end of the ramp lane. Writes courtesy/zipper.json."""
import sys; sys.path.insert(0,'research/truth/scripts')
from courtesy_lib import *
d=ngsim(C/'ngsim-20261101'/'i-80.csv'); d=d[d['lane']>0]
M=pd.read_csv(OUT/'merge_cars_i-80.csv.gz'); s_end=float(np.percentile(M['s_c'],99.5)); sx=s_end+15.0
ramp=set(zip(M['run'],M['id']))
d=d.sort_values(['run','id','t'])
g=d[d['lane']==6]
# first frame beyond the line in lane 6
cross=g[g['s']>=sx].groupby(['run','id'],sort=False).agg(t=('t','first'),v=('v','first')).reset_index()
cross['ramp']=[(r,i) in ramp for r,i in zip(cross['run'],cross['id'])]
cross=cross.sort_values(['run','t'])
print('crossings',len(cross),'ramp',int(cross['ramp'].sum()),'s_end',s_end)
out={'crossings':int(len(cross)),'ramp':int(cross['ramp'].sum()),'s_end_m':s_end,'line_m':sx,'runs':{}}
runs=[]
for r,c in cross.groupby('run'):
    t0=c['t'].min(); c=c.assign(w=((c['t']-t0)/(10*300)).astype(int))
    w=[]
    for k,x in c.groupby('w'):
        if len(x)<20: continue
        n=int(len(x)); m=int(x['ramp'].sum()); w.append(dict(window=int(k),veh=n,ramp=m,main=n-m,ratio_main_per_ramp=round((n-m)/max(m,1),2),share_ramp=round(m/n,3),mean_speed=round(float(x['v'].mean()),2),flow_vph=round(n/300*3600)))
    out['runs'][int(r)]=w
    a=c['ramp'].values; idx=np.where(a)[0]; rl=np.diff(idx)-1
    runs+=rl.tolist()
    print('run',r,len(c),'share ramp',round(a.mean(),3))
rl=np.array(runs); out['main_between_ramp']={'n':int(len(rl)),'dist':{int(k):int((rl==k).sum()) for k in range(0,8)},'over7':int((rl>7).sum()),'mean':round(float(rl.mean()),2),'median':float(np.median(rl))}
p=out['ramp']/out['crossings']
out['geometric_if_random']={int(k):round(float(len(rl)*p*(1-p)**k),1) for k in range(0,8)}
print(json.dumps(out['main_between_ramp']),json.dumps(out['geometric_if_random']))
for r,w in out['runs'].items(): print(r,[(x['window'],x['ratio_main_per_ramp'],x['mean_speed'],x['flow_vph']) for x in w])
save('zipper',out)
