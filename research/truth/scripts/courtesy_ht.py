"""DLR HT (A39, Germany): road frame and lane labels with opus_ht's own functions, frames saved for chosen hours. Usage: courtesy_ht.py HOUR [HOUR...]"""
import sys,time
hours=[int(a) for a in sys.argv[1:]]
sys.argv=['x','1']
sys.path.insert(0,'research/truth/scripts')
src=open('research/truth/scripts/opus_ht.py').read().split('def fit_tanh')[0]
exec(src)
OUTD='/home/erikf/projects/personal/cars-data/truth/courtesy/derived-20261101/'
for hour in [0]+hours:
    t0=time.time(); parts=[read(n) for n in fs[hour*4:hour*4+4]]
    d=pd.concat(parts,ignore_index=True); del parts
    if refs is None: refs=mkrefs(d)
    if hour==0 and 0 not in hours: continue
    d=frame(d); Cn=centres(d); d=lane_label(d,Cn)
    print('hour',hour,len(d),'lanes',{(int(a),int(b)):int(n) for (a,b),n in d.groupby(['dir','lane']).size().items() if n>500},round(time.time()-t0),flush=True)
    np.savez_compressed(OUTD+f'ht_{hour:02d}.npz',id=d['id'].values,ti=d['ti'].values,s=d['s'].values.astype('f4'),lane=d['lane'].values,dir=d['dir'].values,v=d['v'].values,L=d['L'].values,tr=d['tr'].values,rel=d['rel'].values.astype('f4'))
