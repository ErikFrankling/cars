"""Pickle a compact index of a SUMO net: edges, lanes, connections, junctions, tls."""
import sys,pickle,xml.etree.ElementTree as ET
net,out=sys.argv[1],sys.argv[2]
E={};C={};J={};T={}
for _,el in ET.iterparse(net,events=['end']):
    if el.tag=='edge':
        i=el.get('id')
        ls=[dict(id=l.get('id'),speed=float(l.get('speed')),length=float(l.get('length')),allow=l.get('allow'),disallow=l.get('disallow'),shape=l.get('shape')) for l in el.findall('lane')]
        E[i]=dict(id=i,fn=el.get('function'),frm=el.get('from'),to=el.get('to'),name=el.get('name'),type=el.get('type'),prio=el.get('priority'),lanes=ls,shape=el.get('shape'))
        el.clear()
    elif el.tag=='connection':
        k=el.get('from')
        C.setdefault(k,[]).append({a:el.get(a) for a in('fromLane','to','toLane','via','tl','linkIndex','dir','state')})
        el.clear()
    elif el.tag=='junction':
        J[el.get('id')]=dict(type=el.get('type'),x=float(el.get('x')),y=float(el.get('y')),inc=el.get('incLanes'),req=len(el.findall('request')))
        el.clear()
    elif el.tag=='tlLogic':
        T[el.get('id')]=dict(type=el.get('type'),phases=[(float(p.get('duration')),p.get('state'),p.get('minDur'),p.get('maxDur')) for p in el.findall('phase')])
        el.clear()
pickle.dump(dict(E=E,C=C,J=J,T=T),open(out,'wb'),protocol=4)
print(len(E),sum(len(v) for v in C.values()),len(J),len(T))
