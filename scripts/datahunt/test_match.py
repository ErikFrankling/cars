"""Tests the matcher on synthetic noisy traces drawn on the network itself."""
import sys, random, math, time
sys.path.insert(0, "/home/erikf/.t3/projects/cars/scripts/datahunt")
from routenet import Net, overlap
net = Net(sys.argv[1]); step_s=float(sys.argv[2]); noise=float(sys.argv[3]); N=int(sys.argv[4])
print("links", net.n, "banned turns", len(net.banned), "restrictions used", net.rel_used, "skipped", net.rel_skipped)
random.seed(4); ov=[]; t0=time.time(); ok=0; tries=0; fail=0
while ok<N and tries<N*20:
    tries+=1
    a,b=random.randrange(net.n),random.randrange(net.n)
    r,_=net.route(a,b,net.ff)
    if not r: continue
    L=sum(net.length[l] for l in r)
    if not 2000<L<12000: continue
    pts=[]; v=12.0
    for l in r:
        pass
    # walk the route
    s=0.0; xs=[]; cum=0.0
    pts=[]; want=0.0
    for l in r:
        poly=net.poly[l]; c=net.cum[l]; ll=net.length[l]
        while want<cum+ll:
            d=want-cum
            for i in range(len(c)-1):
                if c[i+1]>=d:
                    f=(d-c[i])/max(1e-6,c[i+1]-c[i]); x=poly[i][0]+f*(poly[i+1][0]-poly[i][0]); y=poly[i][1]+f*(poly[i+1][1]-poly[i][1]); break
            pts.append((x+random.gauss(0,noise),y+random.gauss(0,noise))); want+=v*step_s
        cum+=ll
    segs=net.match(pts,sigma=max(noise,8),beta=30 if step_s<8 else 60,radius=max(40,noise*3.5))
    if not segs: fail+=1; ok+=1; ov.append(0.0); continue
    seg=max(segs,key=lambda s:len(s["links"]))
    m=seg["links"]
    ov.append(min(overlap(net,r,m),overlap(net,m,r))); ok+=1
ov.sort()
print(f"step={step_s}s noise={noise}m n={len(ov)} fails={fail} mean={sum(ov)/len(ov):.3f} p10={ov[len(ov)//10]:.3f} med={ov[len(ov)//2]:.3f} share>=.95={sum(o>=.95 for o in ov)/len(ov):.3f} sec={time.time()-t0:.0f}")
