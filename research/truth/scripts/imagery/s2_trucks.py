# Sentinel-2 moving-vehicle test: reads B02,B03,B04,B08 via HTTP range from the open AWS COGs for a road window and flags blue/green/red displaced signatures.
import sys,json,numpy as np,rasterio,os
from rasterio.windows import from_bounds
from pyproj import Transformer
from PIL import Image
base=sys.argv[1];sid=sys.argv[2]
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',AWS_NO_SIGN_REQUEST='YES')
parts=sid.split('_');tile=parts[1];d=parts[2]
root=f"https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/{tile[:2]}/{tile[2]}/{tile[3:]}/{d[:4]}/{int(d[4:6])}/{sid}"
print(root)
A={}
for b in('B02','B03','B04','B08'):
    with rasterio.open(f'/vsicurl/{root}/{b}.tif') as r:
        T=Transformer.from_crs(4326,r.crs,always_xy=True)
        x0,y0=T.transform(17.97,59.30);x1,y1=T.transform(18.11,59.36)
        w=from_bounds(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1),r.transform).round_offsets().round_lengths()
        A[b]=r.read(1,window=w).astype(np.float32);tr=r.window_transform(w);crs=r.crs
print(A['B02'].shape)
rgb=np.dstack([A['B04'],A['B03'],A['B02']])
v=np.clip(rgb/2500,0,1)**.7
os.makedirs(base+'/s2',exist_ok=True)
Image.fromarray((v*255).astype(np.uint8)).save(f'{base}/s2/{sid}_rgb.png')
np.savez_compressed(f'{base}/s2/{sid}.npz',**A,transform=np.array(tr)[:6],crs=str(crs))
