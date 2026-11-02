# Shared streaming readers for the 07 report's map checks. Plain data; no simulator.
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/tmp/cars-mpl')
import pickle,collections,resource
resource.setrlimit(resource.RLIMIT_AS,(3500*2**20,3500*2**20))
from pathlib import Path
from lxml import etree as E
from pyproj import Transformer
DATA=Path(os.environ.get('CARS_DATA','/home/erikf/projects/personal/cars-data'))
MAPS=DATA/'truth/maps'
def stream(p,tags):
    for _,e in E.iterparse(str(p),events=('end',),tag=tags):
        yield e
        e.clear()
        while e.getprevious() is not None:del e.getparent()[0]
def load_net(path,cache=True):
    path=Path(path);pk=MAPS/'builds/cache'/(path.parent.name+'-'+path.stem+'.pkl');pk.parent.mkdir(exist_ok=True,parents=True)
    if cache and pk.exists() and pk.stat().st_mtime>path.stat().st_mtime:return pickle.loads(pk.read_bytes())
    n=dict(edges={},junctions={},tls={},conns=[],location={},internal=0,internal_len={})
    for e in stream(path,('location','edge','junction','tlLogic','connection')):
        a=e.attrib
        if e.tag=='location':n['location']=dict(a)
        elif e.tag=='edge':
            if a.get('function') or a['id'].startswith(':'):
                n['internal']+=1
                for l in e.findall('lane'):n['internal_len'][l.get('id')]=(float(l.get('length')),float(l.get('speed')))
                continue
            n['edges'][a['id']]=dict(frm=a.get('from'),to=a.get('to'),type=a.get('type',''),name=a.get('name',''),prio=int(a.get('priority','-1')),
                lanes=[dict(i=int(l.get('index')),speed=float(l.get('speed')),length=float(l.get('length')),allow=l.get('allow'),disallow=l.get('disallow'),width=float(l.get('width',3.2)),shape=l.get('shape')) for l in e.findall('lane')])
        elif e.tag=='junction':
            if not a['id'].startswith(':'):n['junctions'][a['id']]=dict(type=a['type'],x=float(a['x']),y=float(a['y']),shape=a.get('shape',''),rt=a.get('rightOfWay',''))
        elif e.tag=='tlLogic':
            ps=[(float(p.get('duration')),p.get('state'),p.get('minDur'),p.get('maxDur')) for p in e.findall('phase')]
            n['tls'][a['id']+'|'+a.get('programID','0')]=dict(id=a['id'],prog=a.get('programID'),type=a.get('type'),offset=float(a.get('offset',0)),phases=ps)
        else:
            if a['from'].startswith(':'):continue
            n['conns'].append((a['from'],a['to'],int(a['fromLane']),int(a['toLane']),a.get('dir'),a.get('state'),a.get('tl'),int(a.get('linkIndex',-1)),a.get('via')))
    if cache:pk.write_bytes(pickle.dumps(n,protocol=5))
    return n
def passenger(l):
    al,dis=l['allow'],l['disallow']
    if al is not None:return 'passenger' in al.split() or 'all' in al.split()
    return dis is None or 'passenger' not in dis.split()
def net_tf(net):
    loc=net['location'];ox,oy=map(float,loc['netOffset'].split(','))
    f=Transformer.from_crs('EPSG:4326',loc['projParameter'],always_xy=True);b=Transformer.from_crs(loc['projParameter'],'EPSG:4326',always_xy=True)
    return (lambda lon,lat:(lambda p:(p[0]+ox,p[1]+oy))(f.transform(lon,lat))),(lambda x,y:b.transform(x-ox,y-oy))
def load_osm(xml):
    xml=Path(xml);pk=xml.with_suffix('.pkl')
    if pk.exists() and pk.stat().st_mtime>xml.stat().st_mtime:return pickle.loads(pk.read_bytes())
    ways={};need=set()
    for e in stream(xml,'way'):
        t={x.get('k'):x.get('v') for x in e.findall('tag')}
        if 'highway' not in t:continue
        r=[int(x.get('ref')) for x in e.findall('nd')];ways[int(e.get('id'))]=dict(tags=t,nds=r);need.update(r)
    nodes={};sig={}
    for e in stream(xml,'node'):
        i=int(e.get('id'))
        ts=e.findall('tag')
        if i in need or ts:
            t={x.get('k'):x.get('v') for x in ts}
            if i in need:nodes[i]=(float(e.get('lon')),float(e.get('lat')))
            if t.get('highway') in ('traffic_signals','crossing','give_way','stop','motorway_junction','mini_roundabout') or 'traffic_signals' in t or t.get('crossing')=='traffic_signals' or t.get('name'):sig[i]=dict(lon=float(e.get('lon')),lat=float(e.get('lat')),tags=t,on_way=i in need)
    o=dict(ways=ways,nodes=nodes,tagged=sig);pk.write_bytes(pickle.dumps(o,protocol=5));return o
KEEP=('highway','name','lanes','lanes:forward','lanes:backward','oneway','junction','maxspeed','psv:lanes','psv:lanes:forward','psv:lanes:backward','bus:lanes','bus:lanes:forward','bus:lanes:backward','turn:lanes','turn:lanes:forward','turn:lanes:backward')
def load_osm_tags():
    pk=MAPS/'builds/cache/osm-tags.pkl'
    if pk.exists():return pickle.loads(pk.read_bytes())
    ways={}
    for e in stream(MAPS/'builds/osm/highway.osm.xml','way'):
        t={x.get('k'):x.get('v') for x in e.findall('tag') if x.get('k') in KEEP}
        if 'highway' in t:ways[int(e.get('id'))]=dict(tags=t)
    pk.write_bytes(pickle.dumps(ways,protocol=5));return ways
