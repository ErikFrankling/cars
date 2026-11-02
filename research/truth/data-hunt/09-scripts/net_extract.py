# Stream a SUMO net; keep edges and connections in a bbox. usage: net_extract.py net.xml out.json
import sys,json
from lxml import etree
import pyproj
BB=(17.97,59.295,18.13,59.365)
net,out=sys.argv[1:3]
E={};C=[];J={};off=None
tf=None
def inb(x,y):
    lon,lat=tf.transform(x-off[0],y-off[1]); return BB[0]<=lon<=BB[2] and BB[1]<=lat<=BB[3]
for ev,el in etree.iterparse(net,events=('end',),tag=('location','edge','junction','connection','lane'),huge_tree=True):
    t=el.tag
    if t=='lane': continue
    if t=='location':
        off=[float(v) for v in el.get('netOffset').split(',')]
        tf=pyproj.Transformer.from_proj(pyproj.Proj(el.get('projParameter')),'EPSG:4326',always_xy=True)
    elif t=='edge':
        if el.get('function') in (None,'normal'):
            L=[]
            for l in el.findall('lane'):
                L.append(dict(i=int(l.get('index')),sp=float(l.get('speed')),allow=l.get('allow'),dis=l.get('disallow'),w=l.get('width'),len=float(l.get('length')),shape=l.get('shape')))
            if L:
                mid=L[0]['shape'].split()
                m=mid[len(mid)//2].split(',')
                if inb(float(m[0]),float(m[1])):
                    E[el.get('id')]=dict(fr=el.get('from'),to=el.get('to'),name=el.get('name'),type=el.get('type'),lanes=L)
    elif t=='junction':
        if not el.get('id').startswith(':') and el.get('type')!='internal':
            x,y=float(el.get('x')),float(el.get('y'))
            if inb(x,y): J[el.get('id')]=dict(type=el.get('type'),x=x,y=y,inc=el.get('incLanes'))
    elif t=='connection':
        if el.get('from') in E and not el.get('from').startswith(':'):
            C.append((el.get('from'),el.get('to'),int(el.get('fromLane')),int(el.get('toLane')),el.get('dir'),el.get('state'),el.get('tl')))
    el.clear()
    while el.getprevious() is not None: del el.getparent()[0]
json.dump(dict(off=off,E=E,C=C,J=J),open(out,'w'))
print(len(E),len(C),len(J))
