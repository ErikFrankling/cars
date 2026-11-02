"""Assign a saved demand. usage: run_od.py net.npz d_X.npz LABEL [msa]"""
import sys;sys.path.insert(0,'.')
import numpy as np,assignlib as al,time,os
net=al.Net(sys.argv[1]);D=np.load(sys.argv[2]);lab=sys.argv[3]
uo,ud,W,info=al.zones(net,D['ox'],D['oy'],D['dx'],D['dy'],D['w'],cell=float(os.environ.get('CELL',1000)));print(lab,info,'trips',W.sum(),flush=True)
t=time.time();F=net.assign(uo,ud,W,net.t0);np.savez_compressed(f'out/flow_{lab}_ff.npz',F=F);print(lab,'ff done',time.time()-t,flush=True)
if len(sys.argv)>4:
    for b,h in((1,2.5),(3,3.5)):
        v=F[b].copy()
        for i in range(2):
            c=al.bpr(net,v*1.3,h);y=net.assign(uo,ud,W[[b]],c)[0];v+=(y-v)/(i+2)
        F[b]=v;print(lab,'bin',b,'done',time.time()-t,'max v/c',float((v*1.3/(net.cap*h)).max()),flush=True)
    np.savez_compressed(f'out/flow_{lab}_msa.npz',F=F)
