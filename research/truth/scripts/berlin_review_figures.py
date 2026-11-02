# Figures for the reviewed Berlin report.
import json
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from pyproj import Transformer
O=Path('research/truth/berlin-review'); F=Path('research/truth/fig'); S=Path('research/truth/berlin-snapshot'); C=O/'cache'
BL,OR,AQ='#2a78d6','#eb6834','#1baf7a'; INK,SEC,GRID='#0b0b0b','#52514e','#e4e3df'
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':SEC,'axes.labelcolor':SEC,'xtick.color':SEC,'ytick.color':SEC,'text.color':INK,'axes.titlesize':10,'axes.titleweight':'bold','axes.titlelocation':'left','figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb','axes.grid':True,'grid.color':GRID,'grid.linewidth':.6})
r=pd.read_csv(O/'running_sumo_vs_cars.csv'); s=pd.read_csv(S/'day_summary.csv')
f,ax=plt.subplots(figsize=(8.2,3.6)); ax.plot(r.hour,r.BeST/1000,color=OR,lw=2,label='SUMO 1.22, published (digitised)'); ax.plot(s.time/3600,s.running/1000,color=BL,lw=2,label='cars, frozen run'); ax.set(xlabel='Hour of day',ylabel='Running vehicles (thousands)',xlim=(0,24),xticks=range(0,25,2),ylim=(0,42),title='cars tracks published SUMO to 1% until 17:00, then diverges'); ax.legend(frameon=False,loc='upper left'); ax.annotate('2,090 teleports (SUMO)',(19.3,31.5),(12.4,12),color=SEC,arrowprops=dict(arrowstyle='-',color=SEC,lw=.6)); ax.annotate('23,715 teleports (cars)',(20.8,31),(21.0,39.5),color=SEC,arrowprops=dict(arrowstyle='-',color=SEC,lw=.6),ha='center'); f.tight_layout(); f.savefig(F/'berlin-review-sumo-vs-cars.png',dpi=170); plt.close(f)
L=[('Official 2019 count network\n(vehicle-km, 9,664 to 9,858 links)',.748,.498,.490),('148 detector sites, relaxed match\n(crossings, September 2024)',.965,.618,.608),('93 detector sites, strict match\n(crossings, September 2024)',.931,.586,.576)]
f,ax=plt.subplots(figsize=(8.2,3.5)); y=np.arange(3)[::-1]; h=.24
for k,(lab,col) in enumerate([('MATSim v5.5.3 10% x 10',AQ),('BeST route file, no simulation',OR),('cars day run',BL)]):
    v=[a[k+1] for a in L]; b=ax.barh(y+(1-k)*(h+.02),v,h,color=col,label=lab)
    for yy,vv in zip(y+(1-k)*(h+.02),v): ax.text(vv+.008,yy,f'{vv:.2f}',va='center',color=SEC,fontsize=8)
ax.axvline(1,color=INK,lw=1); ax.text(1.005,2.42,'Measured = 1',color=INK,fontsize=8,va='center'); ax.set_yticks(y,[a[0] for a in L]); ax.set(xlim=(0,1.14),xlabel='Fraction of measured traffic',title='Most volume is lost between MATSim and BeST'); ax.grid(axis='y',visible=False); ax.set_axisbelow(True); ax.legend(frameon=False,loc='upper center',bbox_to_anchor=(.45,-.17),ncol=3); f.tight_layout(); f.savefig(F/'berlin-review-volume-ladder.png',dpi=170); plt.close(f)
A=[('A 100 Stadtring',.68,.92),('A 103 Zehlendorf',.68,.94),('A 111 Hamburg',.34,.85),('A 113 Dresden',.36,.85),('A 115 Avus',.18,.70),('A 114 Prenzlau',.18,.71)]
f,ax=plt.subplots(figsize=(6.6,2.9)); y=np.arange(len(A))[::-1]
ax.hlines(y,[a[1] for a in A],[a[2] for a in A],color=GRID,lw=3); ax.scatter([a[2] for a in A],y,s=48,color=AQ,zorder=3,label='MATSim v5.5.3 10% x 10',edgecolor='#fcfcfb'); ax.scatter([a[1] for a in A],y,s=48,color=OR,zorder=3,label='BeST route file',edgecolor='#fcfcfb'); ax.set_yticks(y,[a[0] for a in A]); ax.set(xlim=(0,1.05),xlabel='Simulated / official DTVw 2019, length-weighted',title='BeST loses the motorways that leave the city'); ax.grid(axis='y',visible=False); ax.legend(frameon=False,loc='upper center',bbox_to_anchor=(.45,-.24),ncol=2); f.tight_layout(); f.savefig(F/'berlin-review-motorways.png',dpi=170); plt.close(f)
E=pd.read_csv(O/'edges.csv',keep_default_na=False,dtype={'edge':str}); shapes=json.loads((C/'shapes.json').read_text()); idx={k:i for i,k in enumerate(E.edge)}; loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(','))))
Pp=[np.array([list(map(float,q.split(',')))[:2] for q in shapes[e].split()])/1000 for e in E.edge]; mid=np.array([p.mean(axis=0)*1000 for p in Pp]); mainr=~E.type.str.contains('residential|living|service|unclass|pedestrian').values
e=pd.read_csv(S/'day_edges.csv',usecols=['begin','edge','samples','distance','teleports']); e=e[e.edge.isin(idx)]; e['i']=e.edge.map(idx); e['h']=(e.begin//3600).astype(int); juncs=pd.concat([E.fr,E.to]).unique(); jid={k:i for i,k in enumerate(juncs)}; a=E.fr.map(jid).values; b=E.to.map(jid).values; sp=E.speed.values
tw=Transformer.from_crs(loc['projParameter'],'EPSG:4326',always_xy=True); prev=None
f,axs=plt.subplots(1,4,figsize=(11,3.3),sharex=True,sharey=True)
hrs=[16,18,19,20]; ax_i=0
for h in range(15,22):
    q=e[e.h==h]; v=q.distance.values/np.maximum(q.samples.values,1); ii=q.i.values; sl=(v<.25*sp[ii])&(q.samples.values>=900); cg=np.zeros(len(E),bool); cg[ii[sl]]=True; G=coo_matrix((np.ones(cg.sum()),(a[cg],b[cg])),shape=(len(jid),len(jid))); _,lab=connected_components(G,directed=False); lc=lab[a[cg]]; top=np.argmax(np.bincount(lc)); cid=np.where(cg)[0]; big=cid[lc==top]; ce=mid[big].mean(axis=0); ln,la=tw.transform(ce[0]-off[0],ce[1]-off[1]); names=E.name.values[big]; nm=pd.Series(names[names!='']).value_counts().head(6).index.tolist()
    ov=len(set(big)&prev)/max(len(big),1) if prev is not None else float('nan'); prev=set(big)
    print(h,'largest cluster',len(big),'km',round(E.length.values[big].sum()/1000,1),'centre',round(la,4),round(ln,4),'overlap with previous hour',round(ov,3),'tele in cluster share',round(q[q.i.isin(big)].teleports.sum()/max(q.teleports.sum(),1),3),nm)
    if h in hrs:
        ax=axs[ax_i]; ax_i+=1; ax.add_collection(LineCollection([Pp[i] for i in np.where(mainr)[0][::1]],colors='#dcdbd6',linewidths=.25)); ax.add_collection(LineCollection([Pp[i] for i in cid if i not in set(big)],colors=OR,linewidths=.9)); ax.add_collection(LineCollection([Pp[i] for i in big],colors=BL,linewidths=1.3)); ax.set(title=f'{h}:00 to {h+1}:00',xlim=(0,40),ylim=(0,35),aspect='equal',xticks=[],yticks=[]); ax.grid(False)
        for sp_ in ax.spines.values(): sp_.set_visible(False)
        ax.text(.02,.02,f'largest cluster {len(big)} edges',transform=ax.transAxes,color=SEC,fontsize=8)
f.suptitle('cars congested edges (below 25% of limit): largest connected cluster in blue, others in orange',x=.01,ha='left',fontsize=10,fontweight='bold'); f.tight_layout(); f.savefig(F/'berlin-review-evening-cluster.png',dpi=170)
h=pd.read_csv(O/'shape_shares.csv',index_col=0)
f,ax=plt.subplots(figsize=(8.2,3.4)); ax.plot(h.index,h.real_share,color=AQ,lw=2,label='Detectors, 93 sites, all vehicles (measured)'); ax.plot(h.index,h.cars_share,color=BL,lw=2,label='cars, same sites'); ax.plot(h.index,h.srv_miv,color=OR,lw=2,label='SrV 2018 car-trip starts (survey, residents)'); ax.set(xlabel='Hour of day',ylabel='Share of daily total (%)',xlim=(0,23),xticks=range(0,24,2),ylim=(0,10.5),title='Road counts are flatter than the survey: SrV is further from the detectors than cars is'); ax.legend(frameon=False,loc='upper left'); f.tight_layout(); f.savefig(F/'berlin-review-shape.png',dpi=170)
