"""Assign SySMo car-driver trips. usage: run_sysmo.py net.npz sysmo.npz OUT.npz [ncell=1000] """
import sys;sys.path.insert(0,'/home/erikf/projects/personal/cars-data/d08-work')
import numpy as np,assignlib as al,json
net=al.Net(sys.argv[1]);Z=np.load(sys.argv[2]);A=Z['A']
cell=float(sys.argv[4]) if len(sys.argv)>4 else 1000.0
ox,oy,dx,dy=A[:,0]-al.OX,A[:,1]-al.OY,A[:,2]-al.OX,A[:,3]-al.OY
b=al.binof(A[:,4]);w=np.zeros((5,len(A)))
w[b,np.arange(len(A))]=1
print('trips',len(A),'by bin',w.sum(1))
uo,ud,W,info=al.zones(net,ox.astype(float),oy.astype(float),dx.astype(float),dy.astype(float),w,cell=cell);print(info,flush=True)
F=al.run(net,uo,ud,W,k_cost=1.3,label='sysmo');np.savez_compressed(sys.argv[3],F=F);print(F.sum(1))
