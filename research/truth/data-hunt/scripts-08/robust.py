import json,numpy as np,itertools
S=json.load(open('out/scores.json'));N=np.load('net.npz');L=N['L']
T=dict(toll_op_plus_ess=424390,innerstad_0630_1830=311500,innerstad_dygn=412100,saltsjo_malar=310200,essingeleden_grondal=170500,centralbron=99000,vasterbron=22000,sodra_lanken_aby=107200,citysnittet=227500,regioncentrum=974200)
ind=['innerstad_dygn','essingeleden_grondal','centralbron','vasterbron','citysnittet','regioncentrum']
for k,v in S.items():
    r=v['ratios'];x=np.log([r[n] for n in ind]);kk=np.exp(x.mean());res=np.exp(x-x.mean())-1
    # leave-one-out spread of the shape score
    loo=[]
    for i in range(len(ind)):
        y=np.delete(x,i);loo.append(np.mean(np.abs(np.exp(y-y.mean())-1))*100)
    tsh=r['innerstad_0630_1830']*311500/(r['innerstad_dygn']*412100)
    print(k,'k6=%.3f shape6=%.1f loo %.1f-%.1f share0630=%.3f'%(kk,np.mean(np.abs(res))*100,min(loo),max(loo),tsh),'scaled',{n:round(r[n]/kk,2) for n in ind})
for f in ['S_ff','S_msa','G1_msa','v8_full','v2_full','stockholm']:
    F=np.load(f'out/flow_{f}.npz')['F'];d=F.sum(0);print(f,'net Mvkm %.2f'%((d*L).sum()/1e9*1000/1000/1e0/1e-0/1e0/1000 if False else (d*L).sum()/1e9),'by bin share',np.round(F.sum(1)/F.sum(),3))
J=json.load(open('out/sysmo.npz.json'));print('rows',J['rows'],sum(J['pop'].values()));print('mode',J['mode'])
