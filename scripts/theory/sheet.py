import math as m
print("== one lane")
for vk in (30,50,100):
    v=vk/3.6
    for T,s in ((1.0,6.5),(1.0,8.0),(1.3,7.25),(1.4,7.5),(1.6,6.5),(1.6,8.0)):
        h=T+s/v; print(f"v={vk} T={T} s={s}: h={h:.2f} q={3600/h:.0f} kc={1000/(s+v*T):.1f} vc={v*3.6:.0f} kj={1000/s:.0f} w={s/T*3.6:.1f}")
print("== ring test T=1.4 s=7.5 v=13.89: k -> v,q")
T,s,v=1.4,7.5,50/3.6
for k in (10,20,36,50,70,100,120):
    K=k/1000; q=min(K*v,(1-K*s)/T); print(k,round(q*3600),round(q/K*3.6,1))
print("== Newell+constant accel discharge: t_n, h_n")
def dis(T,s,v,a,tr,d0,N=16):
    def tau(x):
        xa=v*v/(2*a)
        return m.sqrt(2*x/a) if x<xa else v/a+(x-xa)/v
    ts=[tr+(n-1)*T+tau((n-1)*s+d0) for n in range(1,N+1)]
    hs=[ts[0]]+[b-a_ for a_,b in zip(ts,ts[1:])]
    H=T+s/v; L=tr+v/(2*a)+d0/v-H
    # lost time first 4 by HCM-like definition: sum over first four of (h_i - h_sat)
    l4=sum(h-H for h in hs[:4])
    return ts,hs,H,L,l4
for lab,args in (("T1.4 s7.5 v50 a1.8 tr1.0 d0 2",(1.4,7.5,13.89,1.8,1.0,2)),("T1.4 s7.5 v50 a1.5 tr1.5 d0 2",(1.4,7.5,13.89,1.5,1.5,2)),("T1.2 s7.0 v50 a1.8 tr1.0 d0 2",(1.2,7.0,13.89,1.8,1.0,2)),("T1.4 s7.5 v30 a1.5 tr1.5 d0 2",(1.4,7.5,8.33,1.5,1.5,2))):
    ts,hs,H,L,l4=dis(*args)
    print(lab,"t1..t6",[round(t,2) for t in ts[:6]],"h",[round(x,2) for x in hs[:10]],f"Hsat {H:.2f} S {3600/H:.0f} lostAsym {L:.2f} l4 {l4:.2f} first-at-vf n={next(i+1 for i,x in enumerate(hs) if abs(x-H)<.01)}")
print("== signal S=1800 C=90 g=40 kj=1/7.5 w=20km/h vf=50")
def sig(q,S,C,g,kj=1/7.5,w=20/3.6,uf=50/3.6,Tp=.25):
    q1=q/3600; S1=S/3600; x=q1*C/(S1*g); r=C-g; ka=q1/uf
    u=q1/(kj-ka); ts=r*w/(w-u); L=u*ts; N=L*kj; gs=r*q1/(S1-q1) if q1<S1 else float('inf')
    d1=C*(1-g/C)**2/(2*(1-q1/S1)) if x<1 else r/2
    web=(d1+x**2/(2*q1*(1-x))-.65*(C/q1**2)**(1/3)*x**(2+5*g/C)) if x<1 else float('inf')
    cap=S*g/C; CT=cap*Tp; x0=.67+S1*g/600
    Q0=CT/4*((x-1)+m.sqrt((x-1)**2+12*max(x-x0,0)/CT)) if x>x0 else 0
    return dict(x=round(x,2),cap=round(cap),u_kmh=round(u*3.6,1),tstar=round(ts,1),tgreen=round(ts-r,1),L=round(L,1),N=round(N,1),gs=round(gs,1),d1=round(d1,1),web=round(web,1),Q0=round(Q0,2),akc=round(d1+Q0/cap*3600,1),x0=round(x0,3))
for q in (300,450,600,720,780,900): print(q,sig(q,1800,90,40))
print("webster C0",[(L,Y,round((1.5*L+5)/(1-Y),1)) for L,Y in ((8,.5),(12,.6),(12,.8),(16,.7))])
print("overflow x=1.1 cap 800 q=880: queue growth",80,"veh/h; d after 15 min (Akcelik) ",sig(880,1800,90,40))
print("== give way")
def harders(q,tc,tf): q/=3600; return 3600*q*m.exp(-q*tc)/(1-m.exp(-q*tf)) if q>0 else 3600/tf
def sieg(q,tc,tf): return 3600/tf*m.exp(-q/3600*(tc-tf/2))
def badprint(q,tc,tf): return 3600/tf*m.exp(-q/3600*tc)
def tanner(q,tc,tf,tm=2): q/=3600; return 3600*(1-q*tm)*q*m.exp(-q*(tc-tm))/(1-m.exp(-q*tf)) if q>0 else 3600/tf
def cowan(q,tc,tf,tm,alpha):
    q/=3600; 
    if q==0: return 3600/tf
    l=alpha*q/(1-tm*q); return 3600*alpha*q*m.exp(-l*(tc-tm))/(1-m.exp(-l*tf))
for name,tc,tf in (("HBS S5 right 5.9/3.0",5.9,3.0),("HBS S5 left major 5.5/2.8",5.5,2.8),("HBS S5 cross 6.7/3.3",6.7,3.3),("HBS S5 left minor 6.5/3.2",6.5,3.2),("HCM right 6.2/3.3",6.2,3.3),("HCM through 6.5/4.0",6.5,4.0),("HCM left minor 7.1/3.5",7.1,3.5),("HCM left major 4.1/2.2",4.1,2.2),("HCM6 rdb 1-1 4.99/2.609",4.99,2.609),("WisDOT 4.7/2.6",4.7,2.6)):
    print(name,"Sieg",[round(sieg(q,tc,tf)) for q in (0,200,400,800,1200)],"Hard",[round(harders(q,tc,tf)) for q in (0,200,400,800,1200)],"Tanner2",[round(tanner(q,tc,tf)) for q in (0,200,400,800,1200)],"Cowan1,.75",[round(cowan(q,tc,tf,1.0,.75)) for q in (0,200,400,800,1200)])
print("misprint 8.33 right turn",[round(badprint(q,5.9,3.0)) for q in (0,200,400,800,1200)])
def kh(q,c,T=1.0):
    a=q/c; return 3600/c+900*T*((a-1)+m.sqrt((a-1)**2+(3600/c*a)/(450*T)))
print("Kimber-Hollis wait (T=0.25h), c=451:",[(q,round(kh(q,451,.25),1)) for q in (100,200,300,400,450,500)])
print("Kimber-Hollis wait (T=1h), c=451:",[(q,round(kh(q,451,1),1)) for q in (100,200,300,400,450,500)])
print("polus tc(tw)",[(tw,round((10.34-.03742*tw)/2.509,2)) for tw in (0,15,30,60,120)],"logit scale",round(1/2.509,3),"sd",round(m.pi/m.sqrt(3)/2.509,2))
print("p0 chain example: rank2 left major q=150 G=1000 p0=",1-150/1000)
for py in (1,.9,.8,.6,.4): print(" pz(py)",py,round(.65*py-py/(py+3)+.6*m.sqrt(py),3))
print("RVL C0 tf=3.9",round(3600/3.9),"tf 3.5,4.5",round(3600/3.5),round(3600/4.5))
