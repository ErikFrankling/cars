import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
from opus_windows import *
for s in sys.argv[1:]:
    b=windows(s)
    if b is None: print(s,'none'); continue
    print(s,'windows',b.N,'runs',np.unique(b.meta['run'],return_counts=True),'followers',len(np.unique(b.meta['fid'])),'dyn',int(dynamic_mask(b).sum()),'v',np.percentile(b.v,[5,50,95]).round(1),'s',np.percentile(b.s,[5,50,95]).round(1))
    print(' tmin tmax',b.meta['t'].min(),b.meta['t'].max())
