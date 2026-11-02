out=[]
def add(sc,t,p,s,v='',st='',a=''): out.append(f"{sc},{t},{p},{s},{v},{st},{a}")
V={'sd0':'speedDev=0','tau06':'tau=0.6','gap15':'minGap=1.5','acc':'accel=3.5;decel=2.2','tau_gap':'tau=0.6;minGap=1.5','all':'tau=0.6;minGap=1.5;speedDev=0;accel=3.5;decel=2.2'}
H=(('cacc','tau=1.0;minGap=2.5;param:headwayTimeACC=1.0'),('acc','tau=1.0;minGap=2.5'),('krauss','tau=1.0;minGap=2.5'),('idm','tau=1.0;minGap=2.5'))
T4='krauss idm acc cacc'.split()
# priority 1: endpoints, safety ledger, all scenarios
for s in (0,1,2): add('i80_vsl','acc','0.0',s)
for t in T4:
  for s in (0,1,2): add('i80_vsl',t,'1.0',s)
add('ring','acc','0.0',0)
for t in T4: add('ring',t,'1.0',0)
add('glosa_two_signal','acc','0.0',0)
for t in T4+['glosa']: add('glosa_two_signal',t,'1.0',0)
for s in (0,1): add('bologna','acc','0.0',s)
for t in T4+['glosa']:
  for s in (0,1): add('bologna',t,'1.0',s)

# priority 1b: AV with Waymo-fitted spacing (Chen et al. 2026, s=1.32v+9.05), all else human
W='tau=1.32;minGap=4.05;speedDev=0;accel=2.6;decel=2.0'
for s in (0,1):
  for p in ('0.5','1.0'): add('i80_vsl','idm',p,s,W)
for p in ('0.5','1.0'): add('ring','idm',p,0,W); add('bologna','idm',p,0,W)
add('glosa_two_signal','idm','1.0',0,W)
for s in (0,1): add('i80_vsl','human','1.0',s,'tau=1.01;minGap=3.71')
add('bologna','human','1.0',0,'tau=1.01;minGap=3.71'); add('ring','human','1.0',0,'tau=1.01;minGap=3.71')
add('i80_vsl','cacc','1.0',0,'','0.2'); add('i80_vsl','acc','0.0',0,'','0.2'); add('i80_vsl','krauss','1.0',0,'','0.2'); add('i80_vsl','idm','1.0',0,'','0.2')
# priority 2: ring and I-80 attribution
for v in V.values(): add('ring','human','1.0',0,v)
for t,v in H: add('ring',t,'1.0',0,v)
for v in V.values():
  for s in (0,1): add('i80_vsl','human','1.0',s,v)
for t,v in H:
  for s in (0,1): add('i80_vsl',t,'1.0',s,v)
for s in (0,1): add('i80_vsl','cacc','1.0',s,'','','warn')
# priority 3: mid penetration ledger
for p in ('0.3','0.5'):
  for t in T4:
    for s in (0,1): add('i80_vsl',t,p,s)
for t in T4+['glosa']: add('bologna',t,'0.5',0)
# priority 4: Bologna attribution, step length
for v in V.values(): add('bologna','human','1.0',0,v)
for t,v in H: add('bologna',t,'1.0',0,v)
add('i80_vsl','cacc','1.0',0,'','0.5')
add('i80_vsl','acc','1.0',0,'','0.2'); add('i80_vsl','cacc','1.0',1,'','0.2')
print('\n'.join(out))
