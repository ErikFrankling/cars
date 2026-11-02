import sys;sys.path.insert(0,'.')
import numpy as np,assignlib as al
A=np.load('out/sysmo.npz')['A'];b=al.binof(A[:,4]);w=np.zeros((5,len(A)));w[b,np.arange(len(A))]=1
np.savez('out/d_S.npz',ox=A[:,0].astype(float)-al.OX,oy=A[:,1].astype(float)-al.OY,dx=A[:,2].astype(float)-al.OX,dy=A[:,3].astype(float)-al.OY,w=w);print('sysmo trips',len(A),w.sum(1))
