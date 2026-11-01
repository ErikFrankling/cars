import re, sys, collections
import numpy as np
exec(open('/tmp/brake/an.py').read().split("for p in sys.argv")[0])
for p in sys.argv[1:]:
    d=load(p); ch=[]; firm=[]; big=[]; stc=collections.Counter(); bystate=collections.Counter(); peak_by=collections.Counter()
    for trip,r in d.items():
        r=np.array(r)
        if r[0,1]<270 or r[-1,1]>3: continue
        t,dd,v,a,s,tl=r[:,0],r[:,1],r[:,2],r[:,3],r[:,4].astype(int),r[:,5]
        m=(s>0)&(tl>0)&(tl<1e6)
        dtl=np.abs(np.diff(tl[m])); ch.append((dtl>0.05).sum()); big.append(dtl.sum())
        # distance from the line when it first got a firm grant
        f=np.where(s==2)[0]
        if len(f): firm.append(dd[f[0]])
        # where hard braking (>2 m/s2) happens, by planning state
        for i in range(len(a)):
            if a[i]<-2: bystate[int(s[i])]+=1
    print(p,'plan changes per car, median',np.median(ch),' p90',np.percentile(ch,90),' total slot movement s, median',round(np.median(big),2),' p90',round(np.percentile(big,90),2))
    print(' first firm grant distance m, p10/50/90',np.percentile(firm,[10,50,90]).round(0))
    print(' hard-braking steps by state (0 none,1 advised?,2 pending?,3 firm?)',dict(bystate))
