# Downloads open Stockholm WFS layers (no key). Usage: maps_wfs_fetch.py OUTDIR LAYER... Writes OUTDIR/LAYER.geojson as data only.
import sys,json,time,urllib.request,urllib.parse,hashlib
from pathlib import Path
B='https://apigw.stockholm.se/Open/VirtialOpenDataGeoServerDMZ.svc/Rest/api/wfs'
out=Path(sys.argv[1]);mp=out/'manifest.json';man=json.loads(mp.read_text()) if mp.exists() else []
for L in sys.argv[2:]:
    t0=time.time();u=B+'?'+urllib.parse.urlencode(dict(service='WFS',version='1.1.0',request='GetFeature',typeName='od_gis:'+L,outputFormat='application/json'),safe=':')
    p=out/(L+'.geojson')
    with urllib.request.urlopen(u,timeout=500) as r:p.write_bytes(r.read())
    n=len(json.loads(p.read_text())['features'])
    man.append(dict(layer=L,url=u,features=n,bytes=p.stat().st_size,sha256=__import__('hashlib').sha256(p.read_bytes()).hexdigest(),seconds=round(time.time()-t0),fetched=time.strftime('%Y-%m-%dT%H:%M:%S')))
    print(L,n,p.stat().st_size,flush=True);mp.write_text(json.dumps(man,indent=1));time.sleep(1)
