"""Screenlines from Stockholm's 2018 traffic report, as edge sets on the SUMO net. usage: screens.py net.npz DeSO.gpkg OUT.npz"""
import sys;sys.path.insert(0,'/home/erikf/projects/personal/cars-data/d08-work')
import numpy as np,collections as C,gpk,re
from matplotlib.path import Path
from pyproj import Transformer
N=np.load(sys.argv[1],allow_pickle=False);A,B=N['A'],N['B'];name=N['name'];ty=N['type'];L=N['L']
OX,OY=651972.09,6565003.78
tr=Transformer.from_crs('EPSG:4326','+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs',always_xy=True)
def ll(p):
    a=np.array([tr.transform(*q) for q in p]);return a-[OX,OY]
POLY=[(18.012,59.313),(18.012,59.343),(18.036,59.353),(18.052,59.368),(18.07,59.375),(18.12,59.365),(18.115,59.33),(18.112,59.313),(18.095,59.3075),(18.075,59.3047),(18.06,59.3085),(18.045,59.312),(18.025,59.3125)]
def cross_poly(xy):
    p=Path(xy);a=p.contains_points(A);b=p.contains_points(B);return a!=b
S={}
inner=cross_poly(ll(POLY));S['toll_op']=inner.copy()
isnl=np.array([bool(re.search('norra länken|essingeleden',n.lower())) for n in name])
print('cordon edges',inner.sum(),C.Counter(name[inner]).most_common(45))
S['inner']=inner&~isnl
isess=np.char.startswith(name,'Essingeleden')
_,ly=tr.transform(18.0,59.3245);ly-=OY
S['ess_op']=isess&((A[:,1]-ly)*(B[:,1]-ly)<0)
# Gröndalsbron: Essingeleden between Stora Essingen and Gröndal
_,gy=tr.transform(18.0,59.3165);gy-=OY
S['ess_grondal']=isess&((A[:,1]-gy)*(B[:,1]-gy)<0)
print('ess op',S['ess_op'].sum(),'grondal',S['ess_grondal'].sum(), name[S['ess_grondal']][:8])
for nm in ('Västerbron','Centralbron','Munkbroleden','Skeppsbron','Söderledstunneln'):
    m=name==nm;print(nm,m.sum(),'len',L[m].sum(),'x',A[m,0].min() if m.any() else None,A[m,1].min() if m.any() else None,A[m,1].max() if m.any() else None)
for k,pat in dict(b_vasterbron='^Västerbron$',b_centralbron='^Centralbron$',b_munkbroleden='^Munkbroleden$',b_skeppsbron='^Skeppsbron$').items():
    S[k]=np.array([bool(re.search(pat,n)) for n in name]);print(k,S[k].sum(),[int(x) for x in N['LN'][S[k]][:8]])
# Södra länken east of Åby, read from the net: tunnel edges crossing x of Åby
ax=23600.0
isl=np.isin(name,['Hammarbytunneln','Årstatunneln'])
S['sodra_aby']=isl&((A[:,0]-ax)*(B[:,0]-ax)<0);print('sodra_aby',S['sodra_aby'].sum(),name[S['sodra_aby']],N['LN'][S['sodra_aby']])
# City cordon from the named streets
def ext(n):
    m=name==n;return (A[m].min(0),A[m].max(0)) if m.any() else None
for n in('Kammakargatan','Birger Jarlsgatan','Strömgatan','Vasagatan','Klarabergsviadukten','Klara Södra Kyrkogata'): print(n,ext(n))
inv=Transformer.from_crs('+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs','EPSG:4326',always_xy=True)
city=[(18.0548,59.3400),(18.0690,59.3400),(18.0752,59.3320),(18.0740,59.3285),(18.0560,59.3285)]
S['city']=cross_poly(ll(city));print('city edges',S['city'].sum(),C.Counter(name[S['city']]).most_common(30))
# Region centre: outer boundary of Stockholm, Solna, Sundbyberg
pp=[]
for (k,),rs in gpk.read(sys.argv[2],['kommunkod']):
    if k in('0180','0184','0183'):
        for r in rs: pp.append(Path(r-[OX,OY]))
def inreg(P):
    o=np.zeros(len(P),bool)
    for p in pp:o|=p.contains_points(P)
    return o
ia,ib=inreg(A),inreg(B);S['region']=ia!=ib;print('region edges',S['region'].sum(),C.Counter(ty[S['region']]).most_common(12))
print('within city vkm mask: edges',(ia&ib).sum())
S['in_stockholm_region']=ia&ib
ps=[]
for (k,),rs in gpk.read(sys.argv[2],['kommunkod']):
    if k=='0180':
        for r in rs: ps.append(Path(r-[OX,OY]))
oa=np.zeros(len(A),bool);ob=np.zeros(len(A),bool)
for p in ps:oa|=p.contains_points(A);ob|=p.contains_points(B)
S['in_stockholm_kommun']=oa&ob
np.savez_compressed(sys.argv[3],**S)
