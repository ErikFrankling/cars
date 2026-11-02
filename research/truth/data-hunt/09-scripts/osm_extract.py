# Stream the OSM XML clip; keep tags of ways used by the given net extracts, plus nodes' turn-relevant tags. usage: osm_extract.py clip.osm.xml out.json net1.json net2.json
import sys,json,re
from lxml import etree
osm,out,*nets=sys.argv[1:]
W=set()
for n in nets:
    for e in json.load(open(n))['E']:
        W.add(re.sub(r'#.*','',e).lstrip('-'))
R=[];T={}
for ev,el in etree.iterparse(osm,events=('end',),tag=('way','relation','node'),huge_tree=True):
    if el.tag=='way' and el.get('id') in W:
        T[el.get('id')]=dict(tags={t.get('k'):t.get('v') for t in el.findall('tag')},nd=[n.get('ref') for n in el.findall('nd')][:1]+[n.get('ref') for n in el.findall('nd')][-1:])
    elif el.tag=='relation':
        tg={t.get('k'):t.get('v') for t in el.findall('tag')}
        if tg.get('type')=='restriction':
            R.append(dict(id=el.get('id'),tags=tg,m=[(m.get('type'),m.get('ref'),m.get('role')) for m in el.findall('member')]))
    el.clear()
    while el.getprevious() is not None: del el.getparent()[0]
json.dump(dict(ways=T,restr=R),open(out,'w'))
print(len(T),len(R))
