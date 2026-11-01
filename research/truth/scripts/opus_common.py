"""Shared paths and helpers for the verified human-driving study."""
import os
os.environ.setdefault('OMP_NUM_THREADS','2'); os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import numpy as np, pandas as pd, json, pathlib
B=pathlib.Path('/home/erikf/projects/personal/cars-data/truth/trajectories')
TG=B/'opus-20261031-tgsim'; TGA=B/'opus-20261031-tgsim-att'; NG=B/'opus-20261031-ngsim'; UT=B/'opus-20261031-dlrut'
HT=B/'opus-20261031-dlrht'; SW=B/'opus-20261031-swiss'; DR=B/'opus-20261031-drat'; CACHE=pathlib.Path(os.environ.get('OPUS_CACHE',str(B/'opus-20261031-cache')))
OUT=pathlib.Path('research/truth/human-v2'); OUT.mkdir(exist_ok=True)
def q(x,ps=(5,25,50,75,95)):
    x=np.asarray(x,float); x=x[np.isfinite(x)]
    return {'n':int(len(x)),**{f'p{p:02d}':round(float(np.percentile(x,p)),3) for p in ps},'mean':round(float(x.mean()),3),'sd':round(float(x.std()),3)} if len(x) else {'n':0}
def save(name,obj):
    (OUT/f'{name}.json').write_text(json.dumps(obj,indent=1,default=float)); print('wrote',name)
