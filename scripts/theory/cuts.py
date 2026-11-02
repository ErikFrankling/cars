# Daganzo & Geroliminis 2008 practical cuts, eqs (3),(4b),(5b), by simulating the observer on a periodic or random street.
import random, math
def forward(l,C,G,delta,uf,eps,w=None,n=4000,seed=None,rand=False,lens=None):
    # observer at speed uf (or w if w given, moving against signal order) stopping on red extended by eps*G at the front.
    # Signal j green window in cycle time: [off_j, off_j+(1-eps)G) usable, true green up to off_j+G
    rnd=random.Random(seed)
    t=0.0; moved=0.0; fext=0.0; speed=w if w else uf
    x=0
    for j in range(n):
        L=rnd.choice(lens) if lens else l
        t+=L/speed; moved+=L
        off=rnd.uniform(0,C) if rand else (j*delta)%C
        ph=(t-off)%C
        usable=(1-eps)*G
        if ph>=usable:
            wait=C-ph            # wait to the next green start
            # part of the wait inside the true green is extended red
            ext=max(0,G-ph)
            fext+=ext
            t+=wait
    return moved/t, fext/t, (moved/speed)/t
def mfd(l,C,G,delta,uf,w,kj,s,rand=False,lens=None,seed=1):
    r=kj*w
    fw=[];bw=[]
    qB=s*G/C
    for e in [i/40 for i in range(0,41)]:
        u,f,_=forward(l,C,G,delta,uf,e,seed=seed,rand=rand,lens=lens)
        fw.append((u,s*f))           # q<=k u + s f
        u,b,m=forward(l,C,G,-delta,uf,e,w=w,seed=seed+1,rand=rand,lens=lens)
        bw.append((-u,s*b+r*m))      # q<=-k u + s b + r m
    cuts=fw+bw+[(0.0,qB)]
    def Q(k): return min(a*k+b for a,b in cuts)
    ks=[i*kj/2000 for i in range(0,2001)]
    qs=[Q(k) for k in ks]
    qm=max(qs); i0=qs.index(qm)
    # plateau
    pl=[k for k,q in zip(ks,qs) if q>=qm*0.999]
    return dict(qB=qB,qmax=qm,k_lo=pl[0],k_hi=pl[-1],v_at_lo=qm/pl[0] if pl[0] else None,v_at_hi=qm/pl[-1] if pl[-1] else None,uf_eff=fw[0][0],k_gridlock=next((k for k,q in zip(ks,qs) if k>pl[-1] and q<=1e-6),None),Q=Q,ks=ks,qs=qs)
def show(name,**a):
    m=mfd(**a)
    print(f"{name:42s} qB={m['qB']*3600:5.0f} qmax={m['qmax']*3600:5.0f} veh/h/lane  k*={m['k_lo']*1000:5.1f}-{m['k_hi']*1000:5.1f} veh/km/lane  v*={m['v_at_lo']*3.6 if m['v_at_lo'] else 0:5.1f}-{m['v_at_hi']*3.6 if m['v_at_hi'] else 0:5.1f} km/h  v_free={m['uf_eff']*3.6:5.1f} km/h gridlock_k={(m['k_gridlock'] or 0)*1000:5.0f}")
    return m
print("Check against Daganzo & Geroliminis Table 1 and Fig 6")
for dl in (2.6,9.17-2.6,9.17+2.6,-2.6):
    show(f"SF l=122.9 C=60 G=21 delta={dl}",l=122.9,C=60,G=21,delta=dl,uf=13.4,w=5.4,kj=0.13,s=0.5)
show("Yokohama l=154 C=130 G=49 delta=0",l=154,C=130,G=49,delta=0,uf=13.9,w=5.0,kj=0.14,s=0.5)
show("Yokohama random offsets",l=154,C=130,G=49,delta=0,uf=13.9,w=5.0,kj=0.14,s=0.5,rand=True)
print()
print("Berlin-like: random offsets")
for (l,C,gc,s,uf,w,kj,lab) in [
 (300,90,.45,1800/3600,12.5,5.4,1/7.5,"base l=300 C=90 G/C=.45 s=1800"),
 (300,90,.31,1800/3600,12.5,5.4,1/7.5,"G/C=.31 Hamburg median"),
 (300,90,.60,1800/3600,12.5,5.4,1/7.5,"G/C=.60 Hamburg p90"),
 (200,90,.45,1800/3600,12.5,5.4,1/7.5,"l=200"),
 (460,90,.45,1800/3600,12.5,5.4,1/7.5,"l=460 route mean"),
 (300,110,.45,1800/3600,12.5,5.4,1/7.5,"C=110"),
 (300,70,.45,1800/3600,12.5,5.4,1/7.5,"C=70"),
 (300,90,.45,1636/3600,12.5,5.4,1/7.5,"s=1636 real median"),
 (300,90,.45,2000/3600,12.5,5.4,1/7.5,"s=2000"),
 (300,90,.45,1800/3600,12.5,5.4,1/7.0,"kj=1/7"),
]:
    show(lab,l=l,C=C,G=gc*C,delta=0,uf=uf,w=w,kj=kj,s=s,rand=True)
print('Good offsets (green wave, delta=l/uf) vs bad (delta=l/uf+C/2)')
show('wave l=300',l=300,C=90,G=.45*90,delta=300/12.5,uf=12.5,w=5.4,kj=1/7.5,s=.5)
show('anti-wave l=300',l=300,C=90,G=.45*90,delta=300/12.5+45,uf=12.5,w=5.4,kj=1/7.5,s=.5)
m=mfd(l=300,C=90,G=.45*90,delta=0,uf=12.5,w=5.4,kj=1/7.5,s=.5,rand=True)
# Granular correction eq (7),(8): link of N positions with binomial occupancy
def granular(m,kj,N,kbar):
    rho=kbar/kj
    if rho<=0: return 0
    var=rho*(1-rho)/N; sd=math.sqrt(var)
    tot=wsum=0
    for z in [i/20-3 for i in range(0,121)]:
        w=math.exp(-z*z/2); r=max(0,min(1,rho+z*sd))
        tot+=w*m['Q'](r*kj); wsum+=w
    return tot/wsum
N=40
best=max(((granular(m,1/7.5,N,k),k) for k in [i*0.0002 for i in range(5,650)]))
print(f"granular (N={N} positions per link): qmax={best[0]*3600:.0f} veh/h/lane at k={best[1]*1000:.1f} veh/km/lane, v={best[0]/best[1]*3.6:.1f} km/h")
# scale
print()
D_major_box=507.3; A=49
for lab,mm in (("no granular",dict(q=m['qmax'],k=m['k_lo'])),("granular",dict(q=best[0],k=best[1]))):
    print(lab,"P*=",round(mm['q']*3.6*D_major_box*1000/1000*1000/1000*1000)/1000 if False else round(mm['q']*3600*D_major_box),"veh-km/h on major roads in box; N*=",round(mm['k']*1000*D_major_box),"veh;",round(mm['q']*3600*D_major_box/A),"veh-km/h/km2",round(mm['k']*1000*D_major_box/A),"veh/km2")
# Loder model
import math as M
for R,I,bc,B,lab in [(10.35,0.46,0.084,147,"Berlin box R, I; sample b_c,B"),(10.35,0.46,0.084,0,"no buses"),(23.46,0.385,0.084,147,"Loder sample means"),(50,0.2,M.exp(-2),8/60 and 50/(8/60),"Fig 5 base")]:
    n=-292.73+24.40*R-5.34*R*I-140.67*M.log(bc)+0.307*B
    n2=-292.73+24.40*R-5.34*R*I-140.67*bc+0.307*B
    P=1282.29+18.63*n-6.64*B
    print(f"{lab:32s} n*={n:6.1f} veh/km2 P*={P:7.0f} veh-km/h/km2 v*={P/n:5.1f} km/h q*/lane={P/R:5.0f} k*/lane={n/R:5.1f} | with b_c taken literally n*={n2:6.1f}")
