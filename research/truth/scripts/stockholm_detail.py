import json,csv,collections,gzip
from pathlib import Path
from lxml import etree as ET
from pyproj import Transformer
D=Path('/home/erikf/projects/personal/cars-data/stockholm');O=Path('research/truth'); audit=json.load(open(O/'stockholm-audit.json')); wanted=set(x[0] for x in audit['simulation']['top_teleports']+audit['simulation']['first_interval_teleports']); es={};js={};con=[];osm=collections.Counter();osm_lane=collections.Counter();tunnel=collections.Counter()
for _,e in ET.iterparse(str(D/'stockholm.net.xml'),events=('end',),tag=('edge','junction','connection')):
    if e.tag=='edge':
        a=dict(e.attrib);ls=e.findall('lane');a['lanes']=[dict(x.attrib) for x in ls];es[e.get('id')]=a
    elif e.tag=='junction':js[e.get('id')]=dict(e.attrib)
    else:con.append(dict(e.attrib))
    e.clear()
    while e.getprevious() is not None:del e.getparent()[0]
trans=Transformer.from_crs(32633,4326,always_xy=True);ox,oy=map(float,audit['network']['location']['netOffset'].split(','))
def coord(x,y):return trans.transform(float(x)-ox,float(y)-oy)
named={}
for key in wanted:
    a=es.get(key,{});j=js.get(a.get('to'),{});named[key]=dict(name=a.get('name'),type=a.get('type'),junction=a.get('to'),lanes=len(a.get('lanes',[])),position=coord(j['x'],j['y']) if j else None)
mt=[c for c in con if c.get('tl') and 'motorway' in es.get(c.get('from'),{}).get('type','')];through=set(c['from'] for c in mt if es[c['from']].get('type')=='highway.motorway');ramps=set(c['from'] for c in mt if es[c['from']].get('type')!='highway.motorway')
bounds=[coord(x,y) for x,y in [(0,0),(34380.08,30511.31)]]
for _,e in ET.iterparse(str(D/'clip.osm.xml'),events=('end',),tag=('way','node','relation')):
    if e.tag=='way':
        tags={t.get('k'):t.get('v') for t in e.findall('tag')}
        if tags.get('highway'):
            osm[tags['highway']]+=1
            if tags.get('highway') in ['motorway','motorway_link']:osm_lane['with_lanes' if 'lanes' in tags else 'missing_lanes']+=1;osm_lane['with_maxspeed' if 'maxspeed' in tags else 'missing_maxspeed']+=1
            if tags.get('tunnel') and tags.get('tunnel')!='no':tunnel[tags.get('name','unnamed')]+=1
    e.clear()
    while e.getprevious() is not None:del e.getparent()[0]
ss=list(csv.DictReader(open(D/'cars.summary.csv')))
r=dict(teleport_locations=named,signal_motorway_through=sorted(through),signal_motorway_ramps=len(ramps),projected_bbox_corners_lonlat=bounds,osm_highway_ways=dict(osm),osm_motorway_attributes=dict(osm_lane),osm_tunnel_way_names=tunnel.most_common(30),hourly_summary=[r for r in ss if float(r['time'])%3600==0])
(O/'stockholm-detail.json').write_text(json.dumps(r,indent=2,ensure_ascii=False));print(json.dumps(r,ensure_ascii=False)[:6000])
