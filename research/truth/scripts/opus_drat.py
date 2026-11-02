"""DRaT drone tracks: lateral transitions on a raw 30 fps source with no Kalman smoothing claimed, a check on the filtered sources."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
d=pd.read_csv(DR/'drone_GT.csv',usecols=['track_id','timestamp','utm_x','utm_y','speed_mps','vehicle_class'])
xy=d[['utm_x','utm_y']].values;c=xy.mean(0);u,s,vt=np.linalg.svd(xy[::20]-c,full_matrices=False)
d['s']=(xy-c)@vt[0];d['l']=(xy-c)@vt[1]
rows=[];n=0
# remove any road curvature with a quadratic fit of l on s through all positions
cf=np.polyfit(d['s'],d['l'],2);d['l']=d['l']-np.polyval(cf,d['s'])
for i,g in d.groupby('track_id'):
    g=g.sort_values('timestamp');t=g['timestamp'].values;n+=1
    if t[-1]-t[0]<9: continue
    l=g['l'].values;t=t-t[0]
    a=np.median(l[t<1.5]);b=np.median(l[t>t[-1]-1.5]);W=b-a
    if not 2.6<abs(W)<4.8: continue
    qq=(l-a)/W
    i10=np.where(qq>=.1)[0];i90=np.where(qq>=.9)[0]
    if not len(i10) or not len(i90) or i90[0]<=i10[0]: continue
    if t[i10[0]]<1.5 or t[-1]-t[i90[0]]<1.5: continue
    mono=np.diff(pd.Series(qq[i10[0]:i90[0]+1]).rolling(4,min_periods=1).mean().values).min()
    if mono<-.08: continue
    rows.append((i,t[i90[0]]-t[i10[0]],abs(W),g['speed_mps'].median()))
R=np.array(rows)
out=dict(source='https://zenodo.org/records/20171110',tracks=n,events=len(R),d1090=q(R[:,1],(5,25,50,75,95)),width=q(R[:,2],(5,50,95)),speed=q(R[:,3],(5,50,95)),note='both ends must be visible in a 140 m section, so long manoeuvres at speed are censored and the sample is biased toward short ones')
save('drat_lc',out);print(out)
