"""Paired bootstrap of the exact specification against calibrated Krauss and SUMO defaults, clustered by 300 s traffic block."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_models import *
from opus_fit import split,mk,SUM_KR
from opus_eval import per_window,boot_ci,clusters
SPEC=dict(k1=.011,k2=.52,T=1.30,s0=2.8,m=.5,amax=1.8,bmax=4.5,tau_a=1.0);out={}
for tag,us in (('all',False),('us',True)):
    res=json.loads((OUT/f'fit_params_{tag}.json').read_text());g=json.loads((OUT/'fit_params_all.json').read_text())['helly_sqrt_s0fix_tau1']['params']['gamma']
    tr,va,te=split(us);del tr
    for sn,b in te.items():
        if us and sn!='HT_all_external': continue
        S,V=helly(b,{**SPEC,'v0':g*b.meta['vref'][None,:]});es,ev,_=per_window(b,S,V);cl=clusters(b);o={}
        for name,fn in (('krauss_dt1',lambda:mk('krauss_dt1')[0](b,res['krauss_dt1']['params'])),('krauss_dt01',lambda:mk('krauss_dt01')[0](b,res['krauss_dt01']['params'])),('idm',lambda:mk('idm')[0](b,res['idm']['params'])),('krauss_default_dt1',lambda:krauss(b,{**SUM_KR,'v0':b.meta['vref'][None,:]},1.0)),('krauss_default_dt01',lambda:krauss(b,{**SUM_KR,'v0':b.meta['vref'][None,:]},0.1))):
            S2,V2=fn();rs,rv,_=per_window(b,S2,V2)
            o[name]=dict(spacing=[float(np.sqrt(es.mean())),float(np.sqrt(rs.mean()))],speed=[float(np.sqrt(ev.mean())),float(np.sqrt(rv.mean()))],spacing_ci=boot_ci(es,rs,cl,n=1000),speed_ci=boot_ci(ev,rv,cl,n=1000),windows_better_spacing=float((es<rs).mean()))
        out[sn]=dict(n=b.N,clusters=int(len(np.unique(cl))),cmp=o,median_window_spacing_rmse=float(np.median(np.sqrt(es))),q90_window_spacing_rmse=float(np.percentile(np.sqrt(es),90)))
        print(sn,{k:(round(v['spacing'][0],2),round(v['spacing'][1],2),[round(x,2) for x in v['spacing_ci']],[round(x,2) for x in v['speed_ci']],round(v['windows_better_spacing'],2)) for k,v in o.items()},flush=True)
save('spec_ci',out)
