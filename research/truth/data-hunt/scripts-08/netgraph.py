"""Compact routing graph from a SUMO net: normal edges and edge-to-edge connections, streamed. usage: netgraph.py NET.xml OUT.npz"""
import sys,numpy as np
from lxml import etree
ids=[];L=[];V=[];LN=[];NM=[];TY=[];FR=[];TO=[];A=[];B=[];CAR=[];ix={};con=[]
for ev,el in etree.iterparse(sys.argv[1],events=('end',),tag=('edge','connection','location')):
    if el.tag=='location':
        print(dict(el.attrib))
    elif el.tag=='edge':
        if el.get('function') in (None,'normal'):
            ls=el.findall('lane');l0=ls[0]
            car=any(('passenger' in (x.get('allow') or 'passenger')) and 'passenger' not in (x.get('disallow') or '') for x in ls)
            sh=l0.get('shape').split();a=tuple(map(float,sh[0].split(',')));b=tuple(map(float,sh[-1].split(',')))
            ix[el.get('id')]=len(ids);ids.append(el.get('id'));L.append(float(l0.get('length')));V.append(float(l0.get('speed')));LN.append(len(ls));NM.append(el.get('name') or '');TY.append((el.get('type') or '').split('.')[-1]);FR.append(el.get('from'));TO.append(el.get('to'));A.append(a);B.append(b);CAR.append(car)
    else:
        f,t=el.get('from'),el.get('to')
        if f in ix and t in ix: con.append((ix[f],ix[t]))
    el.clear()
    while el.getprevious() is not None: del el.getparent()[0]
con=np.array(sorted(set(con)),dtype=np.int32)
np.savez_compressed(sys.argv[2],ids=np.array(ids),L=np.array(L,dtype=np.float32),V=np.array(V,dtype=np.float32),LN=np.array(LN,dtype=np.int16),name=np.array(NM),type=np.array(TY),A=np.array(A),B=np.array(B),car=np.array(CAR),con=con)
print(len(ids),'edges',len(con),'conns',sum(CAR),'car edges',np.array(A).min(0),np.array(A).max(0))
