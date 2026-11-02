# Builds the Stockholm municipality ring from the OSM relation 398021. Usage: maps_kommun.py KOMMUN.osm.xml OUT.json
import sys,json
from lxml import etree as E
r=E.parse(sys.argv[1]).getroot()
N={n.get('id'):(float(n.get('lon')),float(n.get('lat'))) for n in r.findall('node')};W={w.get('id'):[x.get('ref') for x in w.findall('nd')] for w in r.findall('way')}
segs=[W[m.get('ref')] for m in r.find('relation').findall('member') if m.get('type')=='way' and m.get('role') in('outer','') and m.get('ref') in W];rings=[]
while segs:
    cur=segs.pop()
    while True:
        for i,s in enumerate(segs):
            if s[0]==cur[-1]:cur=cur+s[1:];segs.pop(i);break
            if s[-1]==cur[-1]:cur=cur+s[::-1][1:];segs.pop(i);break
        else:break
    rings.append(cur)
json.dump([[N[i] for i in x if i in N] for x in rings],open(sys.argv[2],'w'));print([(len(x),x[0]==x[-1]) for x in rings])
