import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
from lxml import etree
from pyproj import Transformer
import urllib.request,json
r=Path(Path('research/truth/berlin-snapshot/download-dir.txt').read_text()); ids={'855402073#0','4444437','334005620','138614363'}; rows=[]; transform=Transformer.from_crs('EPSG:32633','EPSG:4326',always_xy=True)
for _,e in etree.iterparse('/home/erikf/projects/personal/cars-data/best/berlin.net.xml',tag='edge',resolve_entities=False,no_network=True):
 if e.get('id') in ids:
  lane=e.find('lane'); x,y=map(float,lane.get('shape').split()[0].split(',')[:2]); lon,lat=transform.transform(x+372355.98,y+5804722.35); a=dict(e.attrib,lon=lon,lat=lat,lanes=len(e.findall('lane')),length=lane.get('length')); rows.append(a)
 e.clear()
 while e.getprevious() is not None: del e.getparent()[0]
for a in rows:
 w=a['id'].split('#')[0].lstrip('-'); u='https://api.openstreetmap.org/api/0.6/way/'+w; a['source']=u
 try:
  d=urllib.request.urlopen(u,timeout=12).read(1000000); (r/('hotspot-way-'+w+'.xml')).write_bytes(d); a['tags']={z.get('k'):z.get('v') for z in etree.fromstring(d).findall('.//tag')}
 except Exception as e: a['error']=str(e)
print(json.dumps(rows,indent=2)); Path('research/truth/berlin-snapshot/hotspots.json').write_text(json.dumps(rows,indent=2))
