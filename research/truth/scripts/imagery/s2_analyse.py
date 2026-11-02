# Sentinel-2 moving-vehicle test on the open L2A bands: blue->green->red offset signature along roads.
import sys,json,numpy as np
from scipy import ndimage as ni
from PIL import Image
base,sid=sys.argv[1],sys.argv[2]
d=np.load(f'{base}/s2/{sid}.npz',allow_pickle=False);B,G,R,N=[d[k].astype(np.float32) for k in('B02','B03','B04','B08')]
tr=d['transform']
print('transform',tr)
# Fisser et al. style indices: normalised differences and local background anomaly.
def nd(a,b): return (a-b)/(a+b+1)
bg=ni.uniform_filter(B,size=9);gg=ni.uniform_filter(G,size=9);rg=ni.uniform_filter(R,size=9)
dB,dG,dR=B-bg,G-gg,R-rg
bwhite=nd(B,R);rwhite=nd(R,B)
blue=(dB>250)&(bwhite>.05)
red=(dR>250)&(rwhite>.05)
lb,n=ni.label(blue)
print('blue blobs',n,'red px',red.sum(),'blue px',blue.sum())
cnt=0;out=[]
for i,(y,x) in enumerate(ni.center_of_mass(blue,lb,range(1,n+1))):
    y=int(round(y));x=int(round(x))
    y0,y1,x0,x1=max(0,y-4),y+5,max(0,x-4),x+5
    rr=np.argwhere(red[y0:y1,x0:x1])
    if len(rr)==0: continue
    rr=rr+[y0,x0];dist=np.hypot(rr[:,0]-y,rr[:,1]-x);j=dist.argmin()
    if 1<=dist[j]<=4:
        m=np.array([y,x])+(rr[j]-[y,x])//2
        if dG[m[0],m[1]]>100:
            E=tr[2]+tr[0]*(x+.5);Nn=tr[5]+tr[4]*(y+.5)
            out.append((x,y,int(rr[j][1]),int(rr[j][0]),float(dist[j]),E,Nn));cnt+=1
print('candidates with blue-green-red offset within 1-4 px',cnt)
json.dump(out,open(f'{base}/s2/{sid}_cands.json','w'))
v=np.clip(np.dstack([R,G,B])/3000,0,1)**.6
I=Image.fromarray((v*255).astype(np.uint8))
# zoom: Essingeleden crossing / Fredhall-Stora Essingen
Y0,Y1,X0,X1=200,450,120,360
I.crop((X0,Y0,X1,Y1)).resize(((X1-X0)*6,(Y1-Y0)*6),Image.NEAREST).save(f'{base}/s2/{sid}_essing_zoom.png')
from collections import Counter
print('dist',Counter(round(o[4],0) for o in out).most_common(6))
