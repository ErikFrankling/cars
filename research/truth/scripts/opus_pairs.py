"""Builds validated leader-follower segments from TGSIM files; writes cache pairs_<site>.npz and QC json."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
SITES={'I395':('y',None),'I90stat':('x','av'),'I90mov':('x','av'),'I294L1':('x','acc'),'I294L2':('x','acc')}
CAR={'I395':[1]}
def load(name):
    d=pd.read_csv(TG/f'{name}.csv',dtype={'lane_kf':'float32'})
    d.columns=[c.strip().lower().replace('-','_') for c in d.columns]
    d=d.rename(columns={'vehicle_id':'id','track_id':'id'})
    if 'run_index' not in d: d['run_index']=0
    if not pd.api.types.is_numeric_dtype(d['type_most_common']):
        d['type_most_common']=d['type_most_common'].map(lambda x:{'small-vehicle':1,'large-vehicle':2}.get(x,9)).astype(int)
    for c in ('av','acc'):
        if c in d and not pd.api.types.is_numeric_dtype(d[c]): d[c]=d[c].map(lambda x:0 if str(x).strip().lower() in('no','0','false','nan','') else 1).astype(int)
    return d
def run(name,minseg=15.0):
    axis,flag=SITES[name]; d=load(name)
    d=d.drop_duplicates(['run_index','id','time'])
    d['ti']=np.round(d['time']*10).astype(int)
    # direction of travel per (run,lane) from median velocity sign of the road axis
    key='yloc_kf' if axis=='y' else 'xloc_kf'
    d=d.sort_values(['run_index','id','ti'])
    d['ds']=d.groupby(['run_index','id'])[key].diff()
    sign=d.groupby(['run_index','id'])['ds'].transform('median'); d['sgn']=np.sign(sign).fillna(0)
    d['s']=d[key]*d['sgn']
    d=d[d['sgn']!=0]
    # order vehicles in each frame+lane+direction along the road
    d=d.sort_values(['run_index','ti','lane_kf','sgn','s']).reset_index(drop=True)
    same=(d['run_index'].values[1:]==d['run_index'].values[:-1])&(d['ti'].values[1:]==d['ti'].values[:-1])&(d['lane_kf'].values[1:]==d['lane_kf'].values[:-1])&(d['sgn'].values[1:]==d['sgn'].values[:-1])
    idx=np.where(same)[0]
    f,l=idx,idx+1
    A=d
    cc=np.hypot(A['xloc_kf'].values[l]-A['xloc_kf'].values[f],A['yloc_kf'].values[l]-A['yloc_kf'].values[f])
    P=pd.DataFrame(dict(run=A['run_index'].values[f],t=A['ti'].values[f],fid=A['id'].values[f],lid=A['id'].values[l],lane=A['lane_kf'].values[f],cc=cc.astype('f4'),
        vf=A['speed_kf'].values[f].astype('f4'),vl=A['speed_kf'].values[l].astype('f4'),af=A['acceleration_kf'].values[f].astype('f4'),al=A['acceleration_kf'].values[l].astype('f4'),
        Lf=A['length_smoothed'].values[f].astype('f4'),Ll=A['length_smoothed'].values[l].astype('f4'),tf=A['type_most_common'].values[f].astype('i2'),tl=A['type_most_common'].values[l].astype('i2'),
        xf=A['xloc_kf'].values[f].astype('f4'),yf=A['yloc_kf'].values[f].astype('f4')))
    if flag: P['autof']=A[flag].values[f].astype('i2'); P['autol']=A[flag].values[l].astype('i2')
    else: P['autof']=(P['tf']==4).astype('i2'); P['autol']=(P['tl']==4).astype('i2')
    P=P.sort_values(['run','fid','lid','t']).reset_index(drop=True)
    brk=(P['run'].diff()!=0)|(P['fid'].diff()!=0)|(P['lid'].diff()!=0)|(P['t'].diff()!=1)|(P['lane'].diff()!=0)
    P['seg']=brk.cumsum()
    n=P.groupby('seg')['t'].transform('size')
    P=P[n>=int(minseg*10)].reset_index(drop=True)
    P['seg']=P['seg'].rank(method='dense').astype(int)-1
    qc={'site':name,'rows':len(d),'ids':int(d['id'].nunique()),'runs':int(d['run_index'].nunique()),'segments':int(P['seg'].max()+1) if len(P) else 0,'pair_seconds':len(P)/10,'length_all':q(d.drop_duplicates(['run_index','id'])['length_smoothed']),
        'types':d.drop_duplicates(['run_index','id'])['type_most_common'].value_counts().to_dict(),'auto_followers_segments':int(P.groupby('seg')['autof'].first().sum())}
    # QC: gap derivative should equal vl-vf
    g=P.groupby('seg'); dcc=g['cc'].diff()/0.1; res=(dcc-(P['vl']-P['vf']))
    qc['spacing_rate_vs_speeddiff_abs']=q(abs(res))
    # jam spacing: both slow
    sl=P[(P['vf']<0.3)&(P['vl']<0.3)]
    qc['stopped_samples']=len(sl); qc['stopped_center_spacing_m']=q(sl['cc']); qc['stopped_bbox_gap_m']=q(sl['cc']-(sl['Lf']+sl['Ll'])/2)
    qc['neg_bbox_gap_frac']=float(((P['cc']-(P['Lf']+P['Ll'])/2)<0).mean())
    np.savez_compressed(CACHE/f'pairs_{name}.npz',**{k:P[k].values for k in P.columns})
    return qc
if __name__=='__main__':
    out={}
    for s in sys.argv[1:]:
        out[s]=run(s); print(json.dumps(out[s])[:1100],flush=True)
    save('tgsim_pairs_qc_'+'_'.join(sys.argv[1:]),out)
