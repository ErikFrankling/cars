import sys,glob; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from opus_roundabout import load_file,tracks,geometry,REF
fig,ax=plt.subplots(1,3,figsize=(15,5))
for a,f in zip(ax,['D1_AM1_F2.csv','D1_AM2_F1.csv','D2_AM1_L1.csv']):
    d,_,_=load_file(SW/f); ts=tracks(d)
    for i,typ,t,x,y in ts[:300]:
        a.plot(x[::10],y[::10],lw=.2,c='k')
    cx,cy,ri=geometry(ts,REF[f.split('_')[-1][:-4]][1]); a.plot(cx,cy,'rx'); a.add_patch(plt.Circle((cx,cy),ri,fill=False,color='r')); a.add_patch(plt.Circle((cx,cy),ri+3,fill=False,color='b')); a.set_title(f"{f} {cx:.1f},{cy:.1f} r{ri:.1f}"); a.set_xlim(cx-30,cx+30); a.set_ylim(cy-30,cy+30); a.set_aspect('equal'); a.grid()
fig.savefig('/tmp/rb_map.png',dpi=110)
