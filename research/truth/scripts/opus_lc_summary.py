"""Summarises lane change events: duration under several definitions, lateral speed, accepted gaps, SUMO secure-gap test, conditional acceptance logit."""
import sys,pickle; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from scipy.optimize import minimize
ev=pickle.load(open(CACHE/'lc_events_curves.pkl','rb'))  # excludes I-395, whose lateral coordinate failed screening
print(len(ev))
D=pd.DataFrame([{k:v for k,v in e.items() if k not in('rows','curve')} for e in ev])
D['tanh1090']=D['tanh_k']*2.1972
good=D[(D['tanh_rms']<.35)&(abs(D['tanh_w'].abs()-D['width'])<1.0)&(D['d1090']>.3)&(D['d1090']<12)&(D['mono']>-.15)&(D['tanh1090']<14)]
out={'source':['https://data.transportation.gov/d/97n2-kuqi','https://data.transportation.gov/d/9uas-hf8b','https://data.transportation.gov/d/6a6e-vfvi','https://data.transportation.gov/d/7zjf-a4zf','https://data.transportation.gov/d/tpsq-zrwa'],'events_all':len(D),'events_screened':len(good),'by_site_all':D['site'].value_counts().to_dict(),'by_site_screened':good['site'].value_counts().to_dict()}
def tab(g):
    return dict(n=len(g),d1090=q(g['d1090'],(5,10,25,50,75,90,95)),d0595=q(g['d0595'],(5,25,50,75,95)),tanh1090=q(g['tanh1090'],(5,25,50,75,95)),peak_lat=q(g['peak'],(5,25,50,75,95)),width=q(g['width'],(5,50,95)),speed=q(g['speed'],(5,50,95)))
out['all']=tab(good)
for s,g in good.groupby('site'): out['site_'+s]=tab(g)
out['discretionary_cars']=tab(good[(good['ramp']==0)&(good['type']==1)])
out['ramp_or_weave_cars']=tab(good[(good['ramp']>0)&(good['type']==1)])
out['large_vehicles']=tab(good[good['type']==2])
for lo,hi in [(0,5),(5,10),(10,15),(15,25),(25,40)]:
    g=good[(good['speed']>=lo)&(good['speed']<hi)&(good['type']==1)]; out[f'speed_{lo}_{hi}']=tab(g)
cars=good[good['type']==1]
out['corr_d1090_speed']=float(np.corrcoef(cars['speed'],cars['d1090'])[0,1])
lg=np.log(cars['d1090']);out['lognormal_d1090']=dict(mu=float(lg.mean()),sd=float(lg.std()),median=float(np.exp(lg.mean())))
lt=np.log(cars['tanh1090']);out['lognormal_tanh1090']=dict(mu=float(lt.mean()),sd=float(lt.std()),median=float(np.exp(lt.mean())))
# Quintic mapping: full duration for equal 10-90
out['quintic_full_D_median_from_d1090']=float(np.exp(lg.mean())/.5067271)
# filter sensitivity: what a 2 s moving average does to a tanh lane change of the measured median
t=np.arange(-20,20,.01);k=np.exp(lt.mean())/2.1972;y=.5*(1+np.tanh(t/k));yf=np.convolve(y,np.ones(200)/200,'same')
a=lambda z:t[np.argmax(z>=.9)]-t[np.argmax(z>=.1)]
out['filter_sensitivity']=dict(raw=float(a(y)),after_2s_moving_average=float(a(yf)),after_1s=float(a(np.convolve(y,np.ones(100)/100,'same'))))
# gaps. spacing as in the data; lead gap = spacing to target leader, lag gap = spacing to target follower
rows=[]
gi=set(good.index)
for i,e in enumerate(ev):
    if i not in gi or e['type']!=1: continue
    D0=e['d1090']
    for r in e['rows']:
        rows.append((i,e['site'],int(e['ramp']>0),e['speed'])+tuple(r))
G=pd.DataFrame(rows,columns='ev site ramp speed dt v lead vlead lag vlag own vown'.split())
at=G[G['dt']==0].copy()
L=5.0
at['lag_gap']=at['lag']-L; at['lead_gap']=at['lead']-L
at['lag_tg']=at['lag_gap']/at['vlag'].clip(lower=.5); at['lead_tg']=at['lead_gap']/at['v'].clip(lower=.5)
at['dv_lag']=at['vlag']-at['v']; at['dv_lead']=at['v']-at['vlead']
out['accepted_at_crossing']=dict(lag_spacing=q(at['lag'],(1,5,10,25,50,75,90)),lead_spacing=q(at['lead'],(1,5,10,25,50,75,90)),lag_time_gap=q(at['lag_tg'],(1,5,10,25,50,75)),lead_time_gap=q(at['lead_tg'],(1,5,10,25,50,75)),dv_lag=q(at['dv_lag'],(5,25,50,75,95)),dv_lead=q(at['dv_lead'],(5,25,50,75,95)))
for k,lab in ((0,'discretionary'),(1,'ramp')):
    z=at[at['ramp']==k]; out['accepted_'+lab]=dict(n=len(z),lag_spacing=q(z['lag'],(5,10,50,90)),lead_spacing=q(z['lead'],(5,10,50,90)),lag_tg=q(z['lag_tg'],(5,10,50,90)),lead_tg=q(z['lead_tg'],(5,10,50,90)))
# SUMO default secure gap (ballistic form, tau 1, decel 4.5, leader 4.5, min gap 2.5, length 5) applied to real accepted lane changes
def sg(vf,vl,tau=1.0,b=4.5,bl=4.5,mg=2.5): return np.maximum(0,vf*tau+vf*vf/(2*b)-vl*vl/(2*bl))+mg
m=at.dropna(subset=['lag','lead'])
for name,tt in (('at_crossing',m),):
    lagok=(tt['lag_gap']>=sg(tt['vlag'],tt['v']))
    leadok=(tt['lead_gap']>=sg(tt['v'],tt['vlead']))
    out['sumo_default_secure_gap_test']=dict(n=len(tt),lag_ok=float(lagok.mean()),lead_ok=float(leadok.mean()),both_ok=float((lagok&leadok).mean()),note='fraction of observed changes that SUMO default secure gaps would allow at label crossing; crossing is mid-manoeuvre so this is a lower bound on the gap at decision time')
# imposed deceleration under IDM(+) on the new follower
def idm_dec(g,v,vl,a=1.5,b=2.0,T=1.2,s0=2.0): 
    ss=s0+np.maximum(0,v*T+v*(v-vl)/(2*np.sqrt(a*b)));return a*(1-(ss/np.maximum(g,.5))**2)
m2=at.dropna(subset=['lag'])
out['imposed_accel_on_new_follower_idm']=q(idm_dec(m2['lag_gap'],m2['vlag'],m2['v']),(1,5,10,25,50,75))
# conditional logit: state 2 s before crossing (decision proxy) vs state 6-10 s before; only subject vehicles that do change lane
G['lag_gap']=G['lag']-L; G['lead_gap']=G['lead']-L
G['lagtg']=G['lag_gap']/G['vlag'].clip(lower=.5); G['leadtg']=G['lead_gap']/G['v'].clip(lower=.5)
pos=G[G['dt']==-2].dropna(subset=['lag','lead']); neg=G[G['dt']<=-6].dropna(subset=['lag','lead'])
X=np.r_[pos[['lagtg','leadtg']].clip(upper=8).values,neg[['lagtg','leadtg']].clip(upper=8).values];y=np.r_[np.ones(len(pos)),np.zeros(len(neg))]
Xb=np.c_[np.ones(len(X)),X,np.r_[pos['vlag'].sub(pos['v']).values,neg['vlag'].sub(neg['v']).values],np.r_[pos['v'].sub(pos['vlead']).values,neg['v'].sub(neg['vlead']).values]]
def nll(b): 
    z=Xb@b; return np.sum(np.logaddexp(0,-z*(2*y-1)))+1e-3*b@b
r=minimize(nll,np.zeros(Xb.shape[1]),method='BFGS')
out['logit_accept_vs_earlier']=dict(n_pos=len(pos),n_neg=len(neg),coef=dict(zip(['const','lag_time_gap','lead_time_gap','lag_closing','lead_closing'],r.x.tolist())),note='conditional on the same vehicles later changing; earlier states are candidates for rejection, not proven rejected')
# bins of gap where accepted vs earlier states occur
b=[0,.5,1,1.5,2,3,4,6,20]
for nm,col in (('lag','lagtg'),('lead','leadtg')):
    ch=[];
    for lo,hi in zip(b[:-1],b[1:]):
        a_=((pos[col]>=lo)&(pos[col]<hi)).sum();r_=((neg[col]>=lo)&(neg[col]<hi)).sum()
        ch.append(dict(bin=[lo,hi],accepted=int(a_),earlier=int(r_),share=float(a_/(a_+r_/5)) if a_+r_ else None))
    out['accept_share_by_'+nm+'_time_gap']=ch
save('lane_change',out); print(json.dumps({k:out[k] for k in ('events_all','events_screened','by_site_all','by_site_screened','all','discretionary_cars','ramp_or_weave_cars','large_vehicles','lognormal_d1090','lognormal_tanh1090','filter_sensitivity','corr_d1090_speed','sumo_default_secure_gap_test','accepted_at_crossing','imposed_accel_on_new_follower_idm','logit_accept_vs_earlier')},indent=0)[:6000])
