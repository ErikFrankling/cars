# Sliding-window ONNX OBB vehicle detection. Args: model, tile dir, out dir, gsd (m/px to resample to, 0.16 = native).
import sys,json,os,glob,time,math,numpy as np,onnxruntime as ort
from PIL import Image,ImageDraw
model,tiles,out,gsd=sys.argv[1],sys.argv[2],sys.argv[3],float(sys.argv[4])
os.makedirs(out,exist_ok=True)
o=ort.SessionOptions();o.intra_op_num_threads=3
s=ort.InferenceSession(model,o,providers=['CPUExecutionProvider'])
mean=np.array([.485,.456,.406],dtype=np.float32);std=np.array([.229,.224,.225],dtype=np.float32)
VEH={1:'bus',2:'car',3:'other',4:'taxi',5:'truck'}
W=384;STEP=320
def degrade(I):
    if abs(gsd-.16)<1e-6: return I
    w,h=I.size;f=.16/gsd
    return I.resize((round(w*f),round(h*f)),Image.BOX).resize((w,h),Image.BICUBIC)
tot=0;t0=time.time()
for f in sorted(glob.glob(tiles+'/*.jpg')):
    n=os.path.basename(f)[:-4]
    if n in('wmstest','probe_out') or os.path.exists(f'{out}/{n}.json'): continue
    I=degrade(Image.open(f).convert('RGB'));A=np.asarray(I,dtype=np.float32)/255
    H,Wd=A.shape[:2];R=[]
    for y in list(range(0,H-W,STEP))+[H-W]:
        for x in list(range(0,Wd-W,STEP))+[Wd-W]:
            X=((A[y:y+W,x:x+W]-mean)/std).transpose(2,0,1)[None]
            d,l,an=s.run(None,{'input':X})
            p=1/(1+np.exp(-l[0]));c=p[:,:6].argmax(1);sc=p[:,:6].max(1)
            for i in np.where(sc>.15)[0]:
                cx,cy,w,h=d[0][i]*W
                if not(10<cx<W-10 and 10<cy<W-10) and not(x in(0,) or y in(0,)): pass
                R.append(dict(x=float(cx+x),y=float(cy+y),w=float(w),h=float(h),a=float(an[0][i][0]),s=float(sc[i]),c=int(c[i])))
            tot+=1
    R.sort(key=lambda r:-r['s']);K=[]
    for r in R:
        if r['c'] not in VEH: continue
        if any((r['x']-k['x'])**2+(r['y']-k['y'])**2<(0.55*max(k['w'],k['h'],14))**2 for k in K): continue
        K.append(r)
    json.dump(K,open(f'{out}/{n}.json','w'))
    V=I.copy();D=ImageDraw.Draw(V)
    for r in K:
        if r['s']<.25: continue
        col=(255,255,0) if r['s']>=.5 else (255,0,255)
        q=10;D.rectangle([r['x']-q-6,r['y']-q-6,r['x']+q+6,r['y']+q+6],outline=col,width=2)
    V.save(f'{out}/{n}.png' if False else f'{out}/{n}_ov.jpg',quality=88)
    print(n,'dets>=.5',sum(r['s']>=.5 for r in K),'>=.3',sum(r['s']>=.3 for r in K),flush=True)
print('windows',tot,'sec',round(time.time()-t0,1),'s/window',round((time.time()-t0)/max(tot,1),3))
