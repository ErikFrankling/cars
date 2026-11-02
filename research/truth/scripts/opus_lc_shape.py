"""Which time profile matches measured lateral motion: logistic or quintic smoothstep, each with free onset and duration per event."""
import sys,pickle; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from scipy.optimize import least_squares
ev=pickle.load(open(CACHE/'lc_events_curves.pkl','rb'))
def quint(t,tc,D):
    u=np.clip((t-tc)/D+.5,0,1); return 10*u**3-15*u**4+6*u**5
def logi(t,tc,k):
    return .5*(1+np.tanh((t-tc)/k))
def lin(t,tc,D):
    return np.clip((t-tc)/D+.5,0,1)
rows=[]
for e in ev:
    if e['tanh_rms']>.35 or e['mono']<-.15 or not .3<e['d1090']<12 or e['type']!=1: continue
    t,y=e['curve']; t=t[::3].astype('f8');y=y[::3].astype('f8')
    r=[]
    for f,x0,lo,hi in ((quint,[0,10],[-6,1],[6,40]),(logi,[0,2.4],[-6,.2],[6,10]),(lin,[0,6],[-6,.5],[6,30])):
        so=least_squares(lambda p:f(t,*p)-y,x0,bounds=(lo,hi)); r+= [float(np.sqrt(np.mean(so.fun**2))),float(so.x[1])]
    rows.append(r+[e['width'],e['speed'],e['peak']])
R=np.array(rows)
out=dict(n=len(R),rmse_normalised=dict(quintic=q(R[:,0],(25,50,75)),logistic=q(R[:,2],(25,50,75)),constant_speed=q(R[:,4],(25,50,75))),quintic_full_D=q(R[:,1],(5,25,50,75,95)),logistic_k=q(R[:,3],(5,25,50,75,95)),constant_speed_D=q(R[:,5],(5,25,50,75,95)),logistic_better_frac=float((R[:,2]<R[:,0]).mean()),quintic_beats_constant_frac=float((R[:,0]<R[:,4]).mean()))
out['peak_implied_quintic']=q(1.875*R[:,6]/R[:,1],(25,50,75));out['peak_implied_logistic']=q(R[:,6]/(2*R[:,3]),(25,50,75));out['peak_measured']=q(R[:,8],(25,50,75));out['log_quintic_D']=dict(mu=float(np.log(R[:,1]).mean()),sd=float(np.log(R[:,1]).std()))
out['log_logistic_k']=dict(mu=float(np.log(R[:,3]).mean()),sd=float(np.log(R[:,3]).std()))
save('lc_shape',out);print(json.dumps(out)[:1500])
