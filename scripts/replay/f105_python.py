"""F105: report 05's own Python Krauss (SUMO defaults, dt 0.1, v0 = site p99) on exactly the windows the GPU run completed."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
os.chdir(REPO); sys.path.insert(0, 'research/truth/scripts'); sys.path.insert(0, HERE)
import numpy as np
from opus_windows import windows
from opus_models import krauss
from opus_fit import SUM_KR
from rpl import OUT
b = windows('I90mov')
S, V = krauss(b, {**SUM_KR, 'v0': b.meta['vref'][None, :]}, 0.1)
S, V = S[:300, 0], V[:300, 0]
out = {}
for tag in ('sumo_s0', 'main_s0'):
    r = np.load(f'{OUT}/f101/{tag}.roll.npz'); ok = np.isfinite(r['S']).all(0)
    py = float(np.sqrt(np.mean((S[:, ok] - b.s[:300, ok]) ** 2)))
    gpu = float(np.sqrt(np.mean((r['S'][:, ok] - b.s[:300, ok]) ** 2)))
    out[tag] = dict(windows=int(ok.sum()), python_krauss_default=py, gpu=gpu, python_all_windows=float(np.sqrt(np.mean((S - b.s[:300]) ** 2))),
                    mean_abs_gpu_minus_python_spacing=float(np.mean(np.abs(r['S'][:, ok] - S[:, ok]))))
print(json.dumps(out, indent=1))
json.dump(out, open('research/truth/replay/f105.json', 'w'), indent=1)
