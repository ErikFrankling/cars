"""Low-speed hole sizes, timing of the hold-back and braking of yielding followers, site by site. Writes courtesy/final_stats.json."""
import sys; sys.path.insert(0,'research/truth/scripts')
from courtesy_lib import *
import courtesy_events_summary as S
sites=['us-101','i-80','I294L1','I395','I90mov','I90stat','ht','lankershim','peachtree']
E,K=S.load(sites); L=E[(E['L']>=0)&(E['l_same']==1)&E['gfl_4'].notna()].copy(); K2=K[K['l_same']==1].copy()
out={}
out['n_events_all']=int(len(pd.concat([pd.read_csv(OUT/f'events_{s}.csv.gz',usecols=['site']) for s in sites])))
out['events_by_site']={s:int(len(pd.read_csv(OUT/f'events_{s}.csv.gz',usecols=['site']))) for s in sites}
out['matched_used_by_site']={s:int((L['site']==s).sum()) for s in sites}
hole={}
for s in sites+['clean_tgsim','ngsim']:
    m=L if s in('clean_tgsim','ngsim') else L[L['site']==s]
    if s=='clean_tgsim': m=L[L['site'].isin(['I395','I90mov','I90stat','I294L1'])]
    if s=='ngsim': m=L[L['site'].isin(['us-101','i-80'])]
    m=m[(m['vf0']<3)&(m['ve0']<3)]
    if len(m)<15: continue
    h=m['lag0']+m['lead0']+m['Le']
    hole[s]=dict(n=int(len(m)),lag=q(m['lag0'],(5,25,50,75)),lead=q(m['lead0'],(5,25,50,75)),hole=q(h,(5,25,50,75)),neg_lag=round(float((m['lag0']<0).mean()),3),neg_lead=round(float((m['lead0']<0).mean()),3),share_below_10m=round(float((h<10).mean()),3))
out['low_speed_hole']=hole
stand={}
for s in ['I395','I90mov','I90stat','I294L1','i-80','us-101']:
    k=K2[(K2['site']==s)&(K2['vf']<0.5)&(K2['vl_4']<0.5)]
    if len(k)>20: stand[s]=q(k['gfl_4'],(5,25,50,75))
out['standstill_bumper_gap_controls']=stand
# timing: hold-back in the last 2 s against the first 2 s of the 4 s before the crossing
tim={}
CT=S.cell_table(K2)
for lab,sel in (('congested_all',L['vf'].between(2,15)),('tgsim_2_15',L['vf'].between(2,15)&L['site'].isin(['I395','I90mov','I90stat','I294L1'])),('ngsim_2_15',L['vf'].between(2,15)&L['site'].isin(['us-101','i-80']))):
    e=L[sel]; rows=[]
    for s,g in e.groupby('site'):
        if s not in CT: continue
        c=K2[K2['site']==s]
        tc=pd.DataFrame(dict(k=S.strata(c),a=c['dF_pre2'].values,b=c['dF_pre'].values)).groupby('k').agg(a=('a','mean'),b=('b','mean'),n=('a','size')); tc=tc[tc['n']>=8]
        k=S.strata(g); ok=np.isin(k,tc.index.values); cc=tc.reindex(k[ok])
        rows.append(pd.DataFrame(dict(a=g['dF_pre2'].values[ok]-cc['a'].values,b=g['dF_pre'].values[ok]-cc['b'].values)))
    r=pd.concat(rows); tim[lab]=dict(n=int(len(r)),last2s_excess_m=round(float(r['a'].mean()),3),all4s_excess_m=round(float(r['b'].mean()),3))
out['timing']=tim
y=S.flag(L,'dF_pre')|S.flag(L,'dF_post')
br={}
for s in ['I395','I90mov','I90stat','I294L1']:
    m=(L['site']==s)&y
    br[s]=dict(n=int(m.sum()),minacc=q(L['minacc'][m],(5,25,50,75,95)),v_drop=q(L['v_drop'][m],(5,25,50,75,95)))
m=L['site'].isin(['I395','I90mov','I90stat','I294L1'])&y
br['all_tgsim']=dict(n=int(m.sum()),minacc=q(L['minacc'][m],(5,25,50,75,95)),v_drop=q(L['v_drop'][m],(5,25,50,75,95)))
c=K2['site'].isin(['I395','I90mov','I90stat','I294L1'])
br['control_all_pairs']=dict(n=int(c.sum()),minacc=q(K2['minacc'][c],(5,25,50,75,95)))
out['yield_braking']=br
save('final_stats',out); print(json.dumps(out)[:6000])
