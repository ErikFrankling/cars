"""Edge flows by bin from a SUMO route file, for comparison with count-fitted demand. usage: routes_flow.py net.npz routes.rou.gz OUT.npz"""
import sys,gzip,re,numpy as np
N=np.load(sys.argv[1]);ix={e:i for i,e in enumerate(N['ids'])};F=np.zeros((5,len(ix)))
R={};miss=0;veh=0
rx=re.compile(r'depart="([\d.]+)".*route="([^"]+)"')
def b(s):
    h=(s/3600)%24
    return 0 if 6<=h<6.5 else 1 if 6.5<=h<9 else 2 if 9<=h<15 else 3 if 15<=h<18.5 else 4
cnt={}
with gzip.open(sys.argv[2],'rt') as f:
    for l in f:
        if l.startswith('<route '):
            m=re.match(r'<route id="([^"]+)" edges="([^"]*)"',l);a=[ix.get(e,-1) for e in m[2].split()];miss+=a.count(-1);R[m[1]]=np.array([x for x in a if x>=0],dtype=np.int32)
        elif l.startswith('<vehicle'):
            m=rx.search(l);k=(b(float(m[1])),m[2]);cnt[k]=cnt.get(k,0)+1;veh+=1
for (bi,r),n in cnt.items(): np.add.at(F[bi],R[r],n)
np.savez_compressed(sys.argv[3],F=F);print('vehicles',veh,'routes',len(R),'missing edge refs',miss,F.sum(1))
