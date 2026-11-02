# Blind contact sheets: Esri imagery crops of sections/junctions without any net attributes. usage: sheets.py items.json outdir prefix cell_px span_m cols rows
import sys,json,math,io,os,time,urllib.request
from PIL import Image,ImageDraw
items,outd,pre,cell,span,cols,rows=sys.argv[1:8];cell=int(cell);span=float(span);cols=int(cols);rows=int(rows)
I=json.load(open(items));os.makedirs(outd,exist_ok=True);os.makedirs(outd+'/t',exist_ok=True)
Z=19
def tile(z,x,y):
    p=f'{outd}/t/{z}_{x}_{y}.jpg'
    if not os.path.exists(p):
        u=f'https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'research'}),timeout=30) as f: open(p,'wb').write(f.read())
    return Image.open(p).convert('RGB')
def crop(lon,lat):
    n=2**Z;x=(lon+180)/360*n;y=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n
    mpp=156543.03*math.cos(math.radians(lat))/n
    h=span/mpp/2
    x0,x1,y0,y1=x-h/256,x+h/256,y-h/256,y+h/256
    im=Image.new('RGB',(int((math.floor(x1)-math.floor(x0)+1)*256),int((math.floor(y1)-math.floor(y0)+1)*256)))
    for tx in range(int(x0),int(x1)+1):
        for ty in range(int(y0),int(y1)+1):
            im.paste(tile(Z,tx,ty),((tx-int(x0))*256,(ty-int(y0))*256))
    box=((x0-int(x0))*256,(y0-int(y0))*256,(x1-int(x0))*256,(y1-int(y0))*256)
    return im.crop(tuple(map(int,box))).resize((cell,cell),Image.LANCZOS),(x0,y0,(x1-x0))
for s in range(0,len(I),cols*rows):
    sh=Image.new('RGB',(cols*cell+cols-1,rows*cell+rows-1),'white')
    for k,it in enumerate(I[s:s+cols*rows]):
        im,(x0,y0,w)=crop(it['lon'],it['lat']);d=ImageDraw.Draw(im)
        if it.get('line'):
            n=2**Z
            P=[(((lo+180)/360*n-x0)/w*cell,((1-math.asinh(math.tan(math.radians(la)))/math.pi)/2*n-y0)/w*cell) for lo,la in it['line']]
            d.line(P,fill=(0,255,255),width=1)
            for a,b in zip(P,P[1:]):
                if 40<a[0]<cell-40 and 40<a[1]<cell-40 and math.dist(a,b)>12:
                    u=(b[0]-a[0],b[1]-a[1]);m=math.hypot(*u);u=(u[0]/m,u[1]/m);c=(a[0]+u[0]*12,a[1]+u[1]*12)
                    d.line([c,(c[0]-u[0]*7-u[1]*4,c[1]-u[1]*7+u[0]*4)],fill=(255,255,0),width=2);d.line([c,(c[0]-u[0]*7+u[1]*4,c[1]-u[1]*7-u[0]*4)],fill=(255,255,0),width=2)
        d.rectangle((0,0,44,13),fill='black');d.text((2,1),it['id'],fill='yellow')
        if not it.get('line'):
            c=cell//2;d.line((c-7,c,c-3,c),fill='red');d.line((c+3,c,c+7,c),fill='red');d.line((c,c-7,c,c-3),fill='red');d.line((c,c+3,c,c+7),fill='red')
        sh.paste(im,((k%cols)*(cell+1),(k//cols)*(cell+1)))
    sh.save(f'{outd}/{pre}_{s//(cols*rows)+1:02d}.jpg',quality=85)
    print(f'{pre}_{s//(cols*rows)+1:02d}.jpg')
