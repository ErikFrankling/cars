# Runs the ONNX OBB detector on one crop at several scales and prints detections, saves overlay.
import sys,json,numpy as np,onnxruntime as ort,math,time
from PIL import Image,ImageDraw
m,img,x0,y0,crop,out=sys.argv[1],sys.argv[2],*map(int,sys.argv[3:6]),sys.argv[6]
s=ort.InferenceSession(m,providers=['CPUExecutionProvider'],sess_options=(lambda o:(setattr(o,'intra_op_num_threads',3),o)[1])(ort.SessionOptions()))
meta=s.get_modelmeta().custom_metadata_map;names=json.loads(meta['names'])
I=Image.open(img).convert('RGB').crop((x0,y0,x0+crop,y0+crop)).resize((384,384),Image.BICUBIC)
a=np.asarray(I,dtype=np.float32)/255
mean=np.array([.485,.456,.406],dtype=np.float32);std=np.array([.229,.224,.225],dtype=np.float32)
X=((a-mean)/std).transpose(2,0,1)[None]
t=time.time();d,l,ang=s.run(None,{'input':X});print('time',round(time.time()-t,3))
print(d.shape,l.shape,ang.shape,'dets range',d.min(),d.max(),'lab range',l.min(),l.max(),'ang',ang.min(),ang.max())
p=1/(1+np.exp(-l[0]))
cls=p[:,:6].argmax(1) if p.shape[1]>=6 else p.argmax(1);sc=p.max(1)
o=np.argsort(-sc)[:25]
for i in o[:12]: print(round(float(sc[i]),3),p[i].argmax(),np.round(d[0][i],3),round(float(ang[0][i][0]),2))
D=ImageDraw.Draw(I)
for i in o:
    if sc[i]<.3: continue
    cx,cy,w,h=d[0][i]*(384 if d.max()<2 else 1);D.rectangle([cx-w/2,cy-h/2,cx+w/2,cy+h/2],outline=(255,0,0))
I.save(out)
