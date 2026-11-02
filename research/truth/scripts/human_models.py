import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np,json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('research/truth');v=np.linspace(.1,13.5,200);v0=13.89;s0=2.5;T=1
idm=(s0+T*v)/np.sqrt(1-(v/v0)**4)
fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
ax[0].plot(v,s0+v*T,label='Krauss continuous safety boundary, sigma=0');ax[0].plot(v,idm,label='IDM equilibrium, same T and s₀');ax[0].set(xlabel='Speed (m/s)',ylabel='Net bumper gap (m)',ylim=(0,55),title='Model calculation; NOT trajectory validation');ax[0].legend(fontsize=8)
u=np.linspace(0,1,201);D=4;w=3.5;y=w*(10*u**3-15*u**4+6*u**5);vy=w/D*(30*u**2-60*u**3+30*u**4)
ax[1].plot(u*D,y,label='lateral position (m)');ax[1].plot(u*D,vy,label='lateral speed (m/s)');ax[1].set(xlabel='Time (s)',title='Proposed 4 s lane change, 3.5 m lane');ax[1].legend()
fig.savefig(p/'fig/05-model-calculations.png',dpi=160)
print(json.dumps({'at_v10_krauss_boundary':12.5,'at_v10_idm_equilibrium':float(12.5/np.sqrt(1-(10/v0)**4)),'lane_change_vy_peak':1.875*w/D,'krauss_free_accel_mean':2.6*(1-.5/2)},indent=2))
