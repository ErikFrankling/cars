"""Single long-lived process under nix develop: runs queued scripts with python -I, avoids repeated flake evaluation."""
import os,sys,time,subprocess,glob,shlex
Q='/tmp/opus_queue'; os.makedirs(Q,exist_ok=True)
running={}
t0=time.time()
while time.time()-t0<6*3600:
    if os.path.exists(Q+'/STOP'): break
    for f in sorted(glob.glob(Q+'/*.job')):
        cmd=open(f).read().strip(); log=f[:-4]+'.log'
        p=subprocess.Popen([sys.executable,'-I']+shlex.split(cmd),stdout=open(log,'w'),stderr=subprocess.STDOUT,env={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})
        running[f]=p; os.rename(f,f[:-4]+'.started')
    for f,p in list(running.items()):
        if p.poll() is not None:
            open(f[:-4]+'.done','w').write(str(p.returncode)); del running[f]
    time.sleep(1)
for p in running.values(): p.terminate()
