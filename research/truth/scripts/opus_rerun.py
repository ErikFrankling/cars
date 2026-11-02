"""Reruns the earlier report's scripts in a scratch directory and diffs their JSON against the committed outputs."""
import os,runpy,json,sys,time
repo=os.getcwd(); W='/tmp/opus_rerun/research/truth'; os.makedirs(W+'/fig',exist_ok=True); os.chdir('/tmp/opus_rerun')
sc=repo+'/research/truth/scripts/'
for s in ['human_highsim_measure','human_highsim_lateral','human_lateral_fit','human_measure','human_models']:
    t=time.time()
    try:
        runpy.run_path(sc+s+'.py',run_name='__main__'); print(s,'ok',round(time.time()-t),flush=True)
    except Exception as e: print(s,'FAILED',e,flush=True)
def flat(o,p=''):
    if isinstance(o,dict):
        for k,v in o.items(): yield from flat(v,p+'/'+str(k))
    elif isinstance(o,list):
        for i,v in enumerate(o): yield from flat(v,p+'/'+str(i))
    else: yield p,o
for f in ['human-highsim-summary.json','human-highsim-lateral.json','human-lateral-fit.json','human-pneuma-summary.json']:
    a=dict(flat(json.load(open(repo+'/research/truth/'+f))));
    try: b=dict(flat(json.load(open(W+'/'+f))))
    except Exception as e: print(f,'missing',e);continue
    diffs=[k for k in set(a)|set(b) if not(k in a and k in b) or (a[k]!=b[k] and not(isinstance(a[k],float) and abs(a[k]-b[k])<1e-6))]
    print(f,'keys',len(a),'differences',len(diffs),diffs[:5],flush=True)
