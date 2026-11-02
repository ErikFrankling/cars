import json,numpy as np
S=json.load(open('out/scores2.json'))
ind=['innerstad_dygn','essingeleden_grondal','centralbron','vasterbron','citysnittet','regioncentrum']
for k,v in S.items():
    r=v['ratios'];x=np.log([r[n] for n in ind]);kk=np.exp(x.mean());res=np.exp(x-x.mean())-1
    print(k,'k6=%.3f shape6=%.1f share0630=%.3f'%(kk,np.mean(np.abs(res))*100,r['innerstad_0630_1830']*311500/(r['innerstad_dygn']*412100)),{n:round(r[n]/kk,2) for n in ind})
