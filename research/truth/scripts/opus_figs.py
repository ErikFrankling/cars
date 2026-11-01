"""Figures for section 05, from the JSON results only."""
import sys,json,pickle; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
C=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#6250d6','#e34948'];INK='#0b0b0b';SEC='#52514e';SURF='#fcfcfb'
plt.rcParams.update({'figure.facecolor':SURF,'axes.facecolor':SURF,'savefig.facecolor':SURF,'text.color':INK,'axes.labelcolor':SEC,'xtick.color':SEC,'ytick.color':SEC,'axes.edgecolor':'#c9c8c2','axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.color':'#ecebe6','grid.linewidth':.8,'font.size':10,'axes.titlesize':11,'axes.titleweight':'bold','legend.frameon':False})
FIG=pathlib.Path('research/truth/fig'); J=lambda n:json.loads((OUT/f'{n}.json').read_text())
# lane change
ev=pickle.load(open(CACHE/'lc_events_curves.pkl','rb'));D=pd.DataFrame([{k:v for k,v in e.items() if k not in('rows','curve')} for e in ev]);good=D[(D['tanh_rms']<.35)&(D['d1090']>.3)&(D['d1090']<12)&(D['mono']>-.15)&(D['type']==1)]
ht=pd.read_csv(CACHE/'ht_lc.csv');h=ht[(ht['rms']<.3)&(ht['mono']>-.15)&(ht['d1090']<12)&(ht['truck']==0)]
fig,ax=plt.subplots(1,3,figsize=(13.5,3.9),layout='constrained')
b=np.arange(0,13,.5)
ax[0].hist(good['d1090'],b,density=True,histtype='step',lw=2,color=C[0],label=f'TGSIM freeways, US (n={len(good):,})');ax[0].hist(h['d1090'],b,density=True,histtype='step',lw=2,color=C[1],label=f'DLR HT, A39 Germany (n={len(h):,})')
ax[0].axvline(5.816,color=SEC,ls=':',lw=1.5);ax[0].text(5.95,.27,'old report: 5.8 s\n(18 events)',color=SEC,fontsize=8.5)
ax[0].set(xlabel='10–90% lateral displacement time (s)',ylabel='Density',title='Lane change duration');ax[0].legend(fontsize=8.5,loc='upper right')
ax[1].hist(good['peak'],np.arange(0,2.2,.1),density=True,histtype='step',lw=2,color=C[0],label='TGSIM');ax[1].hist(h['peak'],np.arange(0,2.2,.1),density=True,histtype='step',lw=2,color=C[1],label='DLR HT')
ax[1].set(xlabel='Peak lateral speed, 1 s (TGSIM) or 0.8 s (HT) average (m/s)',ylabel='Density',title='Peak lateral speed');ax[1].legend(fontsize=8.5)
T=np.linspace(-9,9,121);M=[]
for e in ev:
    if e['tanh_rms']>.35 or e['mono']<-.15 or e['type']!=1: continue
    t,y=e['curve'];M.append(np.interp(T,t-e['tc_fit'],y))
M=np.array(M);med=np.median(M,axis=0);lo,hi=np.percentile(M,[10,90],axis=0)
S=J('lc_shape');Dq=np.exp(S['log_quintic_D']['mu']);u=np.clip(T/Dq+.5,0,1)
ax[2].fill_between(T,lo,hi,color=C[0],alpha=.18,lw=0,label='Measured 10–90% band');ax[2].plot(T,med,color=C[0],lw=2,label='Measured median');ax[2].plot(T,10*u**3-15*u**4+6*u**5,color=C[1],lw=2,ls='--',label=f'Quintic, D={Dq:.1f} s');u2=np.clip(T/np.exp(np.log(S['constant_speed_D']['p50']))+.5,0,1);ax[2].plot(T,u2,color=C[2],lw=2,ls=':',label='Constant lateral speed (SUMO option)')
ax[2].set(xlabel='Time from fitted centre (s)',ylabel='Share of lane offset',title='Lateral profile');ax[2].legend(fontsize=8.5,loc='upper left')
fig.savefig(FIG/'05v2-lane-change.png',dpi=150);plt.close(fig)
# tournament
Tt=J('tournament_all');tb=dict(Tt['table']);Us=J('tournament_us')['table'];tb['HT_all_external']=Us['HT_all_external']
show=[('krauss_default_dt01','Krauss, SUMO defaults, 0.1 s'),('krauss_default_dt1','Krauss, SUMO defaults, 1 s'),('krauss_dt01','Krauss, calibrated, 0.1 s'),('krauss_dt1','Krauss, calibrated, 1 s'),('gipps','Gipps, calibrated'),('idm','IDM, calibrated'),('idmplus','IDM+, calibrated'),('hdm','HDM core, calibrated'),('helly','Gap-speed feedback, linear, no lag'),('helly_sqrt_s0fix','Gap-scaled feedback, no lag'),('helly_sqrt_s0fix_tau1','Chosen: gap-scaled feedback, 1 s lag'),('newell','Newell shift'),('speed_copy','Copy leader speed')]
sets=['I395_late','I90stat_run6','I90mov','I294L1_runs','HT_late','HT_all_external']
labels=dict(I395_late='I-395, later period',I90stat_run6='I-90/94, held-out run',I90mov='I-90/94, other day',I294L1_runs='I-294, held-out runs',HT_late='A39, later hours',HT_all_external='A39, fit on US only')
fig,ax=plt.subplots(1,2,figsize=(13.5,5),layout='constrained',sharey=True)
y=np.arange(len(show))[::-1]
for a,key,tit,xl in ((ax[0],'spacing_rmse_30s','Spacing error over 30 s','Spacing RMSE (m)'),(ax[1],'speed_rmse_30s','Speed error over 30 s','Speed RMSE (m/s)')):
    for i,s in enumerate(sets):
        xs=[tb[s].get(m,{}).get(key,np.nan) for m,_ in show]
        a.plot(xs,y,'o',color=C[i],ms=7,label=labels[s],mec=SURF,mew=1)
    a.set_title(tit);a.set_xlabel(xl);a.set_yticks(y);a.set_yticklabels([n for _,n in show]);a.grid(axis='x');a.set_xlim(left=0)
ax[0].legend(fontsize=8.5,loc='lower right')
fig.savefig(FIG/'05v2-tournament.png',dpi=150);plt.close(fig)
# queue and yellow
U=J('ut_queue');Q2=J('queue_second_sites');Dy=J('dynamics_final');QF=J('queue_final');SP=J('spec_score');Dy['spec_full']=SP['spec_full']
fig,ax=plt.subplots(1,3,figsize=(13.5,3.9),layout='constrained')
ps=list(range(1,9));tab=U['tables']['all_movements_car']['by_position']
ax[0].plot(ps,[tab[str(p)]['h'].get('p50',np.nan) if tab[str(p)]['n']>=5 else np.nan for p in ps],'o-',color=INK,lw=2,label='DLR UT, measured (real signal)')
for s,cc in zip(Q2[:1],[SEC]):
    bp=s['by_pos'];ax[0].plot(ps,[bp.get(str(p),{}).get('h',{}).get('p50',np.nan) if bp.get(str(p),{}).get('n',0)>=5 else np.nan for p in ps],'s--',color=SEC,lw=1.5,label='Lankershim, measured (no phase)')
for i,(m,lab) in enumerate([('krauss_default_dt1','Krauss defaults, 1 s'),('krauss_default_dt01','Krauss defaults, 0.1 s'),('idm_calibrated','IDM calibrated'),('spec_start06','Chosen model')]):
    ax[0].plot(ps,QF[m]['h'][:8],'-',color=C[i],lw=2,label=lab)
ax[0].set(xlabel='Position in queue',ylabel='Stop line headway (s)',title='Queue discharge',ylim=(0,6));ax[0].legend(fontsize=8)
Y=J('ut_yellow');tt=Y['stop_prob_by_time_to_line'];x=[.5,1.5,2.5,3.5,4.5,5.5,7];k=['0-1','1-2','2-3','3-4','4-5','5-6','6-8']
ax[1].plot(x,[tt[i]['p_stop'] for i in k],'o-',color=C[0],lw=2);ax[1].axvline(3,color=SEC,ls=':');ax[1].text(3.08,.82,'yellow is 3 s',color=SEC,fontsize=8.5)
ax[1].set(xlabel='Time to stop line at yellow onset (s)',ylabel='Share that stop',title=f"Yellow: stop or go (n={Y['decisions']:,})",ylim=(-.03,1))
Lc=J('lane_change')['sumo_default_secure_gap_test'];Hg=J('ht_gaps');labs=['Gap to new follower','Gap to new leader','Both gaps'];y=np.arange(3)[::-1]
us=[Lc['lag_ok'],Lc['lead_ok'],Lc['both_ok']];de=[Hg['secure']['lag_ok'],Hg['secure']['lead_ok'],Hg['secure']['both_ok']]
ax[2].barh(y+.18,[v*100 for v in us],height=.32,color=C[0],label=f"US congested freeways (n={Lc['n']:,})");ax[2].barh(y-.18,[v*100 for v in de],height=.32,color=C[1],label=f"A39 Germany, free flow (n={Hg['both_known']:,})")
for i,(a_,b_) in zip(y,zip(us,de)):
    ax[2].text(a_*100+1.5,i+.18,f'{a_*100:.0f}%',va='center',color=INK,fontsize=9);ax[2].text(b_*100+1.5,i-.18,f'{b_*100:.0f}%',va='center',color=INK,fontsize=9)
ax[2].set_yticks(y);ax[2].set_yticklabels(labs);ax[2].set(xlabel='Share of real changes SUMO default gaps allow (%)',title='Real lane changes vs SUMO secure gap',xlim=(0,112));ax[2].grid(axis='y',visible=False);ax[2].legend(fontsize=8,loc='lower center',bbox_to_anchor=(.5,-.42))
fig.savefig(FIG/'05v2-junction-gap.png',dpi=150);plt.close(fig)
# platoon
fig,ax=plt.subplots(1,2,figsize=(13.5,4.2),layout='constrained')
pos=list(range(1,9));ms=Dy['measured_heldout']['sd']
ax[0].plot(pos,[ms[str(p)] for p in pos],'o-',color=INK,lw=2.5,label='Measured chains')
sel=[('krauss_default_dt1','Krauss defaults, 1 s'),('krauss_calibrated_dt01','Krauss calibrated, 0.1 s'),('idm_calibrated','IDM calibrated'),('feedback_no_lag','Feedback, no lag'),('spec_full','Chosen model')]
for i,(m,lab) in enumerate(sel):
    ax[0].plot(pos,[Dy[m]['heldout']['sd'][str(p)] for p in pos],'-',color=C[i],lw=2,label=lab)
ax[0].set(xlabel='Vehicle position behind the replayed head vehicle',ylabel='Speed SD over 40 s (m/s)',title='Speed fluctuation down real platoons');ax[0].legend(fontsize=8.5)
for i,(m,lab) in enumerate(sel):
    ax[1].plot(pos,[Dy[m]['heldout']['s'][str(p)] for p in pos],'-',color=C[i],lw=2,label=lab)
ax[1].set(xlabel='Vehicle position behind the replayed head vehicle',ylabel='Spacing RMSE (m)',title='Spacing error down the platoon, closed loop');ax[1].legend(fontsize=8.5)
fig.savefig(FIG/'05v2-platoon.png',dpi=150);plt.close(fig)
print('figures done')
