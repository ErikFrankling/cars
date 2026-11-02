# Brightened raw crop (no detector boxes) with the measured-site centreline drawn, for unbiased hand labelling.
import sys,json,numpy as np
from PIL import Image,ImageDraw
from pyproj import Transformer
base=sys.argv[1]
T=Transformer.from_crs(4326,3006,always_xy=True)
rows=json.load(open(base+'/caps/central_sites.json'));S=json.load(open(base+'/caps/sites_selected.json'))
for s in S:
    r=[x for x in rows if x['site']==s['site'] and x['year']==s['year'] and x['dir']==s['dir']][0]
    I=Image.open(f"{base}/tiles/{s['slug']}.jpg").convert('RGB')
    a=np.asarray(I,dtype=np.float32)/255;a=np.clip(a**.62,0,1);V=Image.fromarray((a*255).astype(np.uint8));D=ImageDraw.Draw(V)
    x0=s['E']-s['S']*.16/2;y1=s['N']+s['S']*.16/2
    n=0
    for x_ in rows:
        if x_['site']!=s['site'] or x_['year']!=s['year']: continue
        for l in x_['geom']:
            p=[]
            for lon,lat,*_ in l:
                E,N=T.transform(lon,lat);p.append(((E-x0)/.16,(y1-N)/.16))
            D.line(p,fill=(255,0,0),width=1);n+=1
    V.save(f"{base}/tiles_view_{s['slug']}.jpg",quality=90)
    print(s['slug'],n)
