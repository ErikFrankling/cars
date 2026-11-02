"""Keeps a random fifth of DLR HT segments for model fitting on the small worker slot."""
import sys; sys.path.insert(0,'research/truth/scripts')
from opus_common import *
d=dict(np.load(CACHE/'pairs_HT.npz'))
u=np.unique(d['seg']);k=np.random.default_rng(5).choice(u,len(u)//5,replace=False);m=np.isin(d['seg'],k)
out={a:(b[m].astype('f4') if b.dtype==np.float64 else b[m]) for a,b in d.items()}
np.savez_compressed(sys.argv[1],**out);print(m.sum(),len(u))
