"""Figures for 14-human-courtesy.md."""
import json,pathlib
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=pathlib.Path('research/truth/courtesy'); F=pathlib.Path('research/truth/fig')
Z=json.load(open(O/'zipper.json')); M=json.load(open(O/'merge_summary.json')); Ev=json.load(open(O/'events_summary.json'))
S2=json.load(open(O/'sumo/s5/result.json')); P2=json.load(open(O/'proto/m6_s7.json'))
SURF='#fcfcfb';T1='#0b0b0b';T2='#52514e';GR='#e4e3df';C1='#2a78d6';C2='#eb6834'
plt.rcParams.update({'font.size':9,'axes.edgecolor':GR,'axes.labelcolor':T2,'xtick.color':T2,'ytick.color':T2,'text.color':T1,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':SURF,'axes.facecolor':SURF})
def share(d):
    v=np.array([float(d.get(str(k),d.get(k,0))) for k in range(8)]); return v/v.sum()
# turn taking
fig,ax=plt.subplots(1,4,figsize=(9.6,2.7),sharey=True)
rows=[('I-80, measured\nn=%d'%Z['main_between_ramp']['n'],share(Z['main_between_ramp']['dist'])),('If order were random\n(same ramp share)',share(Z['geometric_if_random'])),('SUMO LC2013, same shape\nn=%d'%sum(S2['main_between_ramp'].values()),share(S2['main_between_ramp'])),('Spec prototype, same shape\nn=%d'%sum(P2['main_between_ramp'].values()),share(P2['main_between_ramp']))]
for a,(t,v) in zip(ax,rows):
    a.bar(range(8),v*100,color=C1,width=.72); a.set_title(t,fontsize=9,loc='left',color=T1); a.set_xticks(range(8)); a.grid(axis='y',color=GR,lw=.6); a.set_axisbelow(True)
    k=int(np.argmax(v)); a.text(k,v[k]*100+1.2,f'{v[k]*100:.0f}%',ha='center',color=T1)
ax[0].set_ylabel('share of ramp entries, %'); ax[0].set_ylim(0,80)
fig.supxlabel('main-lane cars between two successive ramp cars at the end of the ramp lane',fontsize=9,color=T2)
fig.tight_layout(); fig.savefig(F/'14-turn-taking.png',dpi=160); plt.close(fig)
# let-in and active yield
i=M['i-80']
fig,ax=plt.subplots(1,3,figsize=(9.6,3.0))
def bars(a,d,xl,order=None,title=''):
    ks=list(d.keys()); v=[d[k]['p']*100 for k in ks]; n=[d[k]['n'] for k in ks]
    a.bar(range(len(ks)),v,color=C1,width=.72); a.set_xticks(range(len(ks))); a.set_xticklabels([k.replace('-50..','<').replace('..500','+').replace('..50','+').replace('..','–') for k in ks],fontsize=8); a.set_xlabel(xl); a.set_ylim(0,110); a.grid(axis='y',color=GR,lw=.6); a.set_axisbelow(True); a.set_title(title,fontsize=9,loc='left')
    for x,(p,m) in enumerate(zip(v,n)): a.text(x,p+2,f'{p:.0f}%\nn={m}',ha='center',fontsize=7,color=T2)
bars(ax[0],i['p_letin_by_closing'],'target-lane car minus waiting car, m/s',title='I-80: let in, by relative speed')
bars(ax[1],i['p_letin_by_lag0'],'first gap behind the waiting car, m',title='I-80: let in, by gap')
ax[0].set_ylabel('let in, % of cars resolved')
b=Ev['by_speed']; ks=[k for k in b if k not in('0-2','25-60')]; x=np.arange(len(ks))
r=[b[k]['open_before']['rate']*100 for k in ks]; c=[b[k]['open_before']['control']*100 for k in ks]
ax[2].plot(x,r,'-o',color=C1,lw=2,ms=6,label='target-lane follower of a real change'); ax[2].plot(x,c,'-s',color=C2,lw=2,ms=6,label='matched pair, no change')
ax[2].set_xticks(x); ax[2].set_xticklabels([k.replace('-','–') for k in ks],fontsize=8); ax[2].set_xlabel('follower speed, m/s'); ax[2].set_ylim(0,28); ax[2].grid(axis='y',color=GR,lw=.6); ax[2].set_title('8 sites: own braking opened 2 m or 15%',fontsize=9,loc='left'); ax[2].set_ylabel('% of cases, 4 s before the crossing'); ax[2].legend(frameon=False,fontsize=7.5,loc='upper right')
fig.tight_layout(); fig.savefig(F/'14-letin-yield.png',dpi=160); plt.close(fig)
