"""Every prototype experiment for research/truth/06-demand-and-route-choice.md, four at a time.

This takes well over 10 minutes, so run it with heavy. The kept results came from a mix of homelab and PC runs.
"""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "demand_proto.py")
JOBS = [
    ["E0"],
    ["E8"],
    ["E1", "--scale", "1.5", "--iters", "30", "--seeds", "2", "--tag", "unstable", "--policies", "aon,gapprop,msa"],
    ["E1", "--scale", "1.5", "--iters", "30", "--seeds", "2", "--tag", "capped", "--policies", "fixed10,gapcap,gapdecay"],
    ["E1", "--scale", "1.5", "--iters", "30", "--seeds", "2", "--tag", "memory", "--policies", "bounded,gapcap:0.3,gapdecay:0.3,fixed10:0.3,logit"],
    ["E1", "--scale", "2.0", "--iters", "30", "--seeds", "2", "--tag", "capped", "--policies", "gapprop,gapcap,gapcap:0.3,gapdecay:0.3"],
    ["E1", "--scale", "2.0", "--iters", "25", "--seeds", "1", "--tag", "local", "--policies", "gapcap:0.3"],
    ["E2", "--scale", "1.5", "--tag", "all"],
    ["E2", "--scale", "2.0", "--tag", "all"],
    ["E3", "--scales", "0.5,1.0,1.25,1.5,1.75,2.0", "--tag", "a"],
    ["E3", "--scales", "2.5,2.75,3.0,3.5", "--tag", "b"],
    ["E3", "--scales", "2.25", "--tag", "c"],
    ["E4", "--scales", "2.0,2.25", "--tag", "b05g2s5"],
    ["E4", "--scales", "2.0,2.25", "--tag", "b91g56s5", "--beta", "0.91", "--gamma", "0.56"],
    ["E4", "--scales", "2.0", "--tag", "b05g2s5f05r", "--reinit", "--depfrac", "0.05"],
    ["E4", "--scales", "2.0", "--tag", "b91g56s5f05r", "--beta", "0.91", "--gamma", "0.56", "--reinit", "--depfrac", "0.05"],
    ["E4", "--scales", "2.25", "--tag", "b05g2s5f05r225", "--reinit", "--depfrac", "0.05"],
    ["E4", "--scales", "2.25", "--tag", "b91g56s5f05r225", "--beta", "0.91", "--gamma", "0.56", "--reinit", "--depfrac", "0.05"],
    ["E5", "--tag", "a", "--priors", "gravity_right_total,uniform_right_total"],
    ["E5", "--tag", "b", "--priors", "gravity_30pct_high"],
    ["E5", "--tag", "c", "--priors", "probe_2pct_plus_gravity,probe_10pct_plus_gravity"],
    ["E6"],
    ["E7", "--scale", "1.75"],
]


def run(job):
    name = "_".join(job)
    log = os.path.join(HERE, "..", "demand-proto", f"log_{name.replace('.', 'p').replace(':', '').replace(',', '-')}.txt")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w") as f:
        rc = subprocess.call([sys.executable, "-I", SCRIPT, *job], stdout=f, stderr=subprocess.STDOUT)
    print(name, "exit", rc, flush=True)
    return rc


if __name__ == "__main__":
    with ThreadPoolExecutor(4) as ex:
        codes = list(ex.map(run, JOBS))
    sys.exit(max(codes))
