"""Figures for report 02 from the factorial runs."""
import csv,json,pickle,collections,re
from pathlib import Path
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
T=Path('/home/erikf/projects/personal/cars-data/truth/stockholm/factorial');F=Path('research/truth/fig')
INK='#0b0b0b';MUT='#52514e';GRID='#e6e5e0';C=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300']
plt.rcParams.update({'font.size':10,'axes.edgecolor':GRID,'axes.labelcolor':MUT,'xtick.color':MUT,'ytick.color':MUT,'axes.grid':True,'grid.color':GRID,'grid.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb','savefig.dpi':170,'savefig.bbox':'tight','savefig.pad_inches':.15,'legend.frameon':False})
M={}
for l in open(T/'metrics.jsonl'):
    r=json.loads(l);M[r['name']]=r
def summ(n):
    return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(open(T/n/'summary.csv'))]
# 1 ablations at the same demand
rows=[('Baseline: random pool, original net','w_r0_n0',0),('Signals fixed-time instead of actuated','w_r0_static',0),('accel 2.6 instead of 1.5','w_r0_a26',0),('U-turn spurs removed','w_r1_n0',0),('SUMO recommended signal flags','w_r0_on_n2',0),('Same vkm, thinned to 61.5%','w_r0_d37',1),('Same OD, shortest paths','w_r2_n0',1),('Shortest paths + turn-lanes flag','w_r2_n1_turnlanes',2),('Shortest paths + no turnarounds','w_r2_n3_noturn',2),('Shortest paths + join-dist 15 m','w_r2_n4_join15',2),('Shortest paths + all flags together','w_r2_n5_all',2),('Shortest paths + signal flags','w_r2_n2_tlsrec',2)]
rows=sorted(rows,key=lambda x:M[x[1]]['teleports'])
fig,ax=plt.subplots(figsize=(9,4.8));y=np.arange(len(rows))
ax.barh(y,[M[r[1]]['teleports'] for r in rows],color=[C[r[2]] for r in rows],height=.62)
ax.set_yticks(y,[r[0] for r in rows]);ax.set_xscale('log');ax.set_xlabel('Teleports by 10:00, log scale (60% demand file, same departures)')
for i,r in enumerate(rows): ax.text(M[r[1]]['teleports']*1.08,i,f"{M[r[1]]['teleports']:,.0f}",va='center',color=INK,fontsize=9)
ax.grid(axis='y',visible=False);ax.set_xlim(200,90000)
h=[plt.Rectangle((0,0),1,1,color=C[i]) for i in range(3)];ax.legend(h,['Random route pool','Volume or route shape','Net flag, on shortest-path routes'],loc='lower right')
fig.tight_layout();fig.savefig(F/'stockholm-ablations.png');plt.close(fig)
# 2 ladder: same distance driven, different route quality
fig,ax=plt.subplots(figsize=(8,4.6))
for name,runs,c in [('Random route pool, original net',['w_r0_d15','w_r0_d30','w_r0_d37','w_r0_d45','w_r0_n0','w_r0_d100'],C[0]),('Long count-fitted trips, ramp-fixed net',['v2_s40','v2_s60','v2_s80','v2_s100'],C[1]),('Same at 60%, accel 2.6: before and after route feedback',['v2_c3','v2_c0'],C[2])]:
    xs=[M[r]['vkm']/1e6 for r in runs];ys=[M[r]['teleports'] for r in runs]
    ax.plot(xs,ys,color=c,lw=2,marker='o',ms=6,label=name)
ax.set_yscale('log');ax.set_xlabel('Vehicle-km actually driven 00:00-10:00 (million)');ax.set_ylabel('Teleports by 10:00, log scale');ax.legend(loc='upper left')
fig.tight_layout();fig.savefig(F/'stockholm-ladder.png');plt.close(fig)
# 3 running vehicles by time
fig,ax=plt.subplots(figsize=(8,4.2))
for n,l,c in [('w_r0_n0','Baseline 60% file',C[0]),('w_r2_n2_tlsrec','Shortest paths + signal flags, 60% file',C[1]),('v2_s100','Long count-fitted trips, ramp-fixed net',C[2]),('v2_c3','Same at 60%, accel 2.6, route feedback',C[3])]:
    if (T/n/'summary.csv').exists():
        s=summ(n);ax.plot([r['time']/3600 for r in s],[r['running'] for r in s],color=c,lw=2,label=l)
ax.set_xlabel('Hour');ax.set_ylabel('Running vehicles');ax.legend(loc='upper left');ax.set_xlim(0,10)
fig.tight_layout();fig.savefig(F/'stockholm-running.png');plt.close(fig)
# 4 class fit
cf=json.load(open('research/truth/stockholm-classfit.json'))['stockholm.rou.gz']['classes'];rp=json.load(open(T/'v2_fit.json'))['by_class']
cl=['motorway','trunk','primary','secondary','tertiary','unclassified','residential']
fig,ax=plt.subplots(figsize=(8,4));x=np.arange(len(cl));w=.36
ax.bar(x-w/2-.01,[cf[k]['ratio'] for k in cl],w,color=C[0],label='Current pool, 2.92M trips, 2.43 km')
ax.bar(x+w/2+.01,[rp[k]['ratio'] for k in cl],w,color=C[1],label='Replacement pool, 1.32M trips, 8.0 km')
ax.axhline(1,color=MUT,lw=1);ax.set_xticks(x,cl);ax.set_ylabel('Fitted / target vehicle-km on counted edges');ax.legend(loc='upper left',bbox_to_anchor=(0,1.16),ncol=2);ax.grid(axis='x',visible=False)
fig.tight_layout();fig.savefig(F/'stockholm-classfit.png');plt.close(fig)
# 5 map
N=pickle.load(open(T/'n0.idx.pkl','rb'));E=N['E']
seg=[];w=[]
for e,v in E.items():
    if v['fn'] is None and (v['type'] or '').split('.')[-1] in('motorway','trunk','primary','secondary'):
        p=[tuple(map(float,q.split(','))) for q in v['lanes'][0]['shape'].split()];seg.append(p)
def pts(n,idx,h0,h1):
    Ex=pickle.load(open(idx,'rb'))['E'];c=collections.Counter()
    for r in csv.DictReader(open(T/n/'edges.csv')):
        if h0<=float(r['begin'])<h1 and int(r['teleports']): c[r['edge']]+=int(r['teleports'])
    X=[];Y=[];S=[]
    for e,k in c.items():
        if e in Ex:
            q=Ex[e]['lanes'][0]['shape'].split()[0].split(',');X.append(float(q[0]));Y.append(float(q[1]));S.append(k)
    return X,Y,S
fig,axs=plt.subplots(1,3,figsize=(13,4.6),sharex=True,sharey=True)
for ax,(n,i,t,h0,h1) in zip(axs,[('base60',T/'n0.idx.pkl','Night 00-05, baseline: light load, already stuck',0,18000),('w_r0_n0',T/'n0.idx.pkl','07-10, baseline',25200,36000),('w_r2_n2_tlsrec',T/'n2_tlsrec.idx.pkl','07-10, shortest paths + signal flags',25200,36000)]):
    ax.add_collection(LineCollection(seg,colors='#cfcfca',linewidths=.3));X,Y,S=pts(n,i,h0,h1)
    ax.scatter(X,Y,s=np.minimum(np.array(S)*(3 if h0==0 else .4)+2,160),color=C[1],alpha=.55,linewidths=0);ax.set_title(f'{t}\n{sum(S):,} teleports',fontsize=10,color=INK,loc='left');ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([]);ax.grid(False)
axs[0].set_xlim(4000,30000);axs[0].set_ylim(3000,28000)
fig.tight_layout();fig.savefig(F/'stockholm-teleport-map.png');plt.close(fig)
