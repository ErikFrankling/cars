import json,numpy as np
from scipy.optimize import brentq
from pathlib import Path
p=Path('research/truth');j=json.loads((p/'human-highsim-lateral.json').read_text());x=np.array([e['duration10_90_s'] for e in j['events']]);u=brentq(lambda u:10*u**3-15*u**4+6*u**5-.1,0,1);factor=1-2*u
out=dict(n=len(x),distinct_tracks=len({e['id'] for e in j['events']}),median_10_90=float(np.median(x)),log_mu_10_90=float(np.log(x).mean()),log_sd_10_90=float(np.log(x).std(ddof=1)),quintic_10_90_factor=factor,full_D_log_mu=float(np.log(x/factor).mean()),full_D_median=float(np.exp(np.log(x/factor).mean())))
(p/'human-lateral-fit.json').write_text(json.dumps(out,indent=2));print(out)
