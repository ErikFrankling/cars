import numpy as np,pandas as pd
from pathlib import Path
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
O=Path('research/truth/berlin-review'); S=Path('research/truth/berlin-snapshot')
E=pd.read_csv(O/'edges.csv',keep_default_na=False,dtype={'edge':str},usecols=['edge','fr','to','speed','length']); idx={k:i for i,k in enumerate(E.edge)}
e=pd.read_csv(S/'day_edges.csv',usecols=['begin','edge','samples','distance','teleports']); e=e[e.edge.isin(idx)]; e['i']=e.edge.map(idx); e['h']=(e.begin//3600).astype(int); j=pd.concat([E.fr,E.to]).unique(); jid={k:i for i,k in enumerate(j)}; a=E.fr.map(jid).values; b=E.to.map(jid).values; sp=E.speed.values; L=E.length.values
for th in (.10,.25,.40):
  for h in (16,18,19,20):
    q=e[e.h==h]; v=q.distance.values/np.maximum(q.samples.values,1); ii=q.i.values; sl=(v<th*sp[ii])&(q.samples.values>=900); cg=np.zeros(len(E),bool); cg[ii[sl]]=True
    G=coo_matrix((np.ones(cg.sum()),(a[cg],b[cg])),shape=(len(jid),len(jid))); _,lab=connected_components(G,directed=False); lc=lab[a[cg]]; top=np.argmax(np.bincount(lc)); big=np.where(cg)[0][lc==top]
    print(th,h,'cong',int(cg.sum()),'largest',len(big),'km',round(L[big].sum()/1000,1),'teleport share',round(q[q.i.isin(big)].teleports.sum()/q.teleports.sum(),3))
