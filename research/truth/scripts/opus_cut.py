"""Cuts frozen train, validation and test windows once, so later stages need under 1 GB."""
import sys,pickle; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
import opus_fit
def pack(b):
    return dict(s=b.s.astype('f4'),v=b.v.astype('f4'),vl=b.vl.astype('f4'),a0=b.a0.astype('f4'),meta=b.meta)
for tag,us in (('all',False),('us',True)):
    tr,va,te=opus_fit.split(us)
    r=np.random.default_rng(1);tr=tr.subset(r.choice(tr.N,6000,replace=False))
    pickle.dump(dict(train=pack(tr),val=pack(va),test={k:pack(v) for k,v in te.items()}),open(sys.argv[1]+f'/split_{tag}.pkl','wb'),protocol=4)
    print(tag,tr.N,va.N,{k:v.N for k,v in te.items()},flush=True)
