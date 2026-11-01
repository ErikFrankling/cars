# Reruns the 07 report's generators in a scratch dir, so no existing file in research/truth is overwritten.
import os,sys,runpy,shutil
from pathlib import Path
R=Path.cwd()/'research/truth/scripts'
S=Path(sys.argv[1]);(S/'research/truth/fig').mkdir(parents=True,exist_ok=True)
os.chdir(S)
for n in ('maps_audit','maps_detail','maps_report'):
    print('RUN',n,flush=True);runpy.run_path(str(R/(n+'.py')),run_name='__main__')
