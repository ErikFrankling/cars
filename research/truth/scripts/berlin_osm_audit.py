import pathlib,urllib.request,xml.etree.ElementTree as ET,json
r=pathlib.Path(pathlib.Path('research/truth/berlin-snapshot/download-dir.txt').read_text()); out=[]
for w in ['81629728','43336764','674133616','50339906','25041360','414866491']:
 u='https://api.openstreetmap.org/api/0.6/way/'+w
 try:
  d=urllib.request.urlopen(u,timeout=15).read(1000000); (r/('osm-way-'+w+'.xml')).write_bytes(d); t=ET.fromstring(d); tags={x.get('k'):x.get('v') for x in t.findall('.//tag')}; out.append(dict(way=w,url=u,tags=tags)); print(w,tags)
 except Exception as e: print(w,e)
pathlib.Path('research/truth/berlin-snapshot/osm-audit.json').write_text(json.dumps(out,indent=2))
