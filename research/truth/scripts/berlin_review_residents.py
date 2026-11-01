# Is BeST the set of MATSim trips made by people who live inside the network? Also lane curves, windowed lag and shape shares.
import os,json
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,pandas as pd
from pyproj import Transformer
O=Path('research/truth/berlin-review'); C=O/'cache'; S=Path('research/truth/berlin-snapshot'); M=Path('/home/erikf/projects/personal/cars-data/truth/berlin/opus-review-20261031/matsim')
loc=json.loads((O/'net_location.json').read_text()); off=np.array(list(map(float,loc['netOffset'].split(',')))); tr=Transformer.from_crs('EPSG:31468',loc['projParameter'],always_xy=True); G=1000; xmin,ymin,xmax,ymax=map(float,loc['convBoundary'].split(','))
g=np.load(O/'od_grid.npz'); netc=g['net']; nx,ny=netc.shape
ins=lambda x,y,mask:(lambda a,b:((a>=0)&(a<nx)&(b>=0)&(b<ny))&mask[np.clip(a,0,nx-1),np.clip(b,0,ny-1)])(((x-xmin)//G).astype(int),((y-ymin)//G).astype(int))
t=pd.read_csv(M/'berlin-v5.5.3-10pct.output_trips.csv.gz',sep=';',usecols=['person','trip_number','dep_time','traveled_distance','main_mode','start_activity_type','start_x','start_y','end_x','end_y'],dtype={'person':str})
print(t.person.str.extract(r'^(\d|[a-zA-Z]+)')[0].value_counts().head(6).to_dict()); 
home=t[t.start_activity_type.str.startswith('home')].groupby('person').first()[['start_x','start_y']]; first=t.sort_values('trip_number').groupby('person').first()[['start_x','start_y']]; hh=home.reindex(t.person.unique()); hh=hh.fillna(first); hx,hy=tr.transform(hh.start_x.values,hh.start_y.values); res=pd.Series(ins(hx+off[0],hy+off[1],netc),index=hh.index)
print('persons with trips',len(hh),'home in net cells x10',10*int(res.sum()))
c=t[t.main_mode.isin(['car','freight'])].copy(); x,y=tr.transform(c.start_x.values,c.start_y.values); c['si']=ins(x+off[0],y+off[1],netc); x,y=tr.transform(c.end_x.values,c.end_y.values); c['ei']=ins(x+off[0],y+off[1],netc); c['res']=c.person.map(res).fillna(False).astype(bool)
c['ok']=c.si&c.ei; a=c.dep_time.str.split(':',expand=True).astype(int); c['dep']=a[0]*3600+a[1]*60+a[2]
print('x10 both ends in net: residents',10*int((c.ok&c.res).sum()),'non-residents',10*int((c.ok&~c.res).sum()),'; crossing residents',10*int(((c.si^c.ei)&c.res).sum()),'non-res',10*int(((c.si^c.ei)&~c.res).sum()),'; all resident car trips',10*int(c.res.sum()))
print('km x10 resident inside',c[c.ok&c.res].traveled_distance.sum()/100,'mean',c[c.ok&c.res].traveled_distance.mean()/1000)
mm=np.load(C/'route_meta.npy'); dep=mm[:,0]; hb=np.bincount((dep//3600).astype(int),minlength=24)[:24]; hr=np.bincount((c[c.ok&c.res].dep.values//3600).astype(int),minlength=30)[:24]*10
print('BeST',hb.tolist()); print('res ',hr.tolist()); print('ratio',np.round(hb/np.maximum(hr,1),3).tolist()); print('corr',np.corrcoef(hb,hr)[0,1])
# trip length percentile comparison
print('BeST ext km pct',np.percentile(mm[:,4]/1000,[10,25,50,75,90,99]).round(2).tolist(),'MATSim inside km pct',np.percentile(c[c.ok].traveled_distance/1000,[10,25,50,75,90,99]).round(2).tolist(),'resident inside',np.percentile(c[c.ok&c.res].traveled_distance/1000,[10,25,50,75,90,99]).round(2).tolist())
print('MATSim 0-km car trips',(c.traveled_distance<100).mean())
# Published "real" against lanes
b=pd.read_csv(O/'best_plot_digitised.csv'); l=pd.read_csv(O/'detector_lane_hourly.csv'); v=pd.read_csv(O/'detector_all_hourly.csv')
for pl,si in [('altmoabit-east','TE452'),('treskowallee-south','TE129'),('siemensdamm-east','TE106')]:
    r=b[(b['plot']==pl)&(b.series=='real')].set_index('hour').value; print(pl,'published real day',round(r.sum()),'sumo',round(b[(b['plot']==pl)&(b.series=='sumo')].value.sum()),'matsim',round(b[(b['plot']==pl)&(b.series=='matsim')].value.sum()))
    st=v[v.site==si].set_index('hour').real; print(' 2024 section day',round(st.sum()),'shape r',round(np.corrcoef(r.reindex(range(24)),st.reindex(range(24)))[0,1],3))
    for d,q in l[l.site==si].groupby('detector'):
        qq=q.set_index('hour').qkfz.reindex(range(24)); print('  lane',d,round(qq.sum()),'r',round(np.corrcoef(r.reindex(range(24)),qq.fillna(0))[0,1],3),'rmse to published',round(np.sqrt(((r.reindex(range(24))-qq)**2).mean())))
# Windowed lag tests, fractional shift
cc=pd.read_csv(S/'balanced_compare.csv'); h=cc.groupby('hour')[['real','cars']].sum(); fr=pd.read_csv(S/'freight.csv'); ps=fr[fr.site.isin(cc.site.unique())].groupby('hour')[['qkfz','qpkw','qlkw']].sum()
def lag(a,b,win):
    best=None; xs=np.arange(-3,3.01,.25); out=[]
    for s in xs:
        sh=np.interp((np.arange(24)-s)%24,np.arange(25),np.r_[b,b[0]]); w=list(win); out.append(np.corrcoef(a[w],sh[w])[0,1])
    return xs[int(np.argmax(out))],max(out)
r=h.real.values; cv=h.cars.values; print('lag all',lag(r,cv,range(24)),'am 3-11',lag(r,cv,range(3,12)),'day 6-20',lag(r,cv,range(6,21)),'pm 14-23',lag(r,cv,range(14,24)))
pk=ps.qpkw.values; print('passenger only: lag all',lag(pk,cv,range(24)),'am',lag(pk,cv,range(3,12)),'pm',lag(pk,cv,range(14,24)))
sh=pd.DataFrame({'real_share':r/r.sum()*100,'pkw_share':pk/pk.sum()*100,'cars_share':cv/cv.sum()*100,'best_dep_share':hb/hb.sum()*100}); sv=pd.read_csv(S/'survey_comparison.csv'); sh['srv_miv']=sv.SrV_MIV_percent.values; sh['lkw_share']=ps.qlkw.values/ps.qlkw.sum()*100; sh['lkw_of_hour']=ps.qlkw.values/ps.qkfz.values*100; sh.to_csv(O/'shape_shares.csv',float_format='%.3f'); print(sh.round(2).to_string())
print('8h / peak: real',r[8]/r.max(),'pkw',pk[8]/pk.max(),'cars',cv[8]/cv.max(),' 10h / 8h real',r[10]/r[8],'cars',cv[10]/cv[8],'pm peak hour real',r.argmax(),'cars',cv.argmax())
print('shape error (mean abs percentage points): cars vs real',np.abs(sh.cars_share-sh.real_share).mean(),'cars vs pkw',np.abs(sh.cars_share-sh.pkw_share).mean(),'cars vs srv',np.abs(sh.cars_share-sh.srv_miv).mean(),'real vs srv',np.abs(sh.real_share-sh.srv_miv).mean())
print('night share 0-4 real',r[:5].sum()/r.sum(),'cars',cv[:5].sum()/cv.sum())
F=pd.read_csv(O/'svz_match.csv'); print('class 0 links',F[F.klasse.astype(str)=='0'][['name','dtv','L','static']].head(8).to_string())
