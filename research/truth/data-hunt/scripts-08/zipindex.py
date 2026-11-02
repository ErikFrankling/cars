import sys,struct,urllib.request
URL='https://ndownloader.figshare.com/files/57749911'
def rng(a,b):
    r=urllib.request.Request(URL,headers={'Range':f'bytes={a}-{b}','User-Agent':'curl/8'});return urllib.request.urlopen(r,timeout=60).read()
SIZE=9636699448
tail=rng(SIZE-70000,SIZE-1)
i=tail.rfind(b'PK\x05\x06');cdn=struct.unpack('<H',tail[i+10:i+12])[0];cds,cdo=struct.unpack('<II',tail[i+12:i+20])
j=tail.rfind(b'PK\x06\x06')
if j>=0: cdn,cds,cdo=struct.unpack('<QQQ',tail[j+32:j+56])
print('entries',cdn,'cd size',cds,'offset',cdo)
cd=rng(cdo,cdo+cds-1)
p=0;names=[]
while p<len(cd) and cd[p:p+4]==b'PK\x01\x02':
    meth,=struct.unpack('<H',cd[p+10:p+12]);cs,us=struct.unpack('<II',cd[p+20:p+28]);n,e,c=struct.unpack('<HHH',cd[p+28:p+34]);off,=struct.unpack('<I',cd[p+42:p+46])
    name=cd[p+46:p+46+n].decode('utf8','replace');ex=cd[p+46+n:p+46+n+e]
    q=0
    while q<len(ex):
        h,l=struct.unpack('<HH',ex[q:q+4])
        if h==1:
            d=ex[q+4:q+4+l];k=0
            if us==0xffffffff: us,=struct.unpack('<Q',d[k:k+8]);k+=8
            if cs==0xffffffff: cs,=struct.unpack('<Q',d[k:k+8]);k+=8
            if off==0xffffffff: off,=struct.unpack('<Q',d[k:k+8]);k+=8
        q+=4+l
    names.append((name,meth,cs,us,off));p+=46+n+e+c
open(sys.argv[1],'w').write('\n'.join(f'{a}\t{b}\t{c}\t{d}\t{e}' for a,b,c,d,e in names))
print(len(names));
import re
tops=set(n.split('/')[0] for n,*_ in names);print('tops',list(tops)[:10])
hits=[x for x in names if re.search(r'stockholm|_SE_',x[0],re.I)]
seen=sorted(set(x[0].split('/')[-2] if x[0].count('/')>=1 else x[0] for x in hits))
print(len(hits));print(seen[:80])
for x in hits:
    if re.search(r'stockholm',x[0],re.I):print(x)
