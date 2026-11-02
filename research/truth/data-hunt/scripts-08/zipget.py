import sys,struct,urllib.request,zlib,os
URL='https://ndownloader.figshare.com/files/57749911'
def rng(a,b):
    r=urllib.request.Request(URL,headers={'Range':f'bytes={a}-{b}','User-Agent':'curl/8'});return urllib.request.urlopen(r,timeout=120).read()
idx=[l.rstrip('\n').split('\t') for l in open(sys.argv[1])]
out=sys.argv[2];pats=sys.argv[3:]
os.makedirs(out,exist_ok=True)
for n,m,cs,us,off in idx:
    if not any(p in n for p in pats) or n.endswith('/'): continue
    m,cs,us,off=int(m),int(cs),int(us),int(off)
    h=rng(off,off+29);nl,el=struct.unpack('<HH',h[26:30])
    d=rng(off+30+nl+el,off+30+nl+el+cs-1)
    d=zlib.decompress(d,-15) if m==8 else d
    assert len(d)==us
    fn=os.path.join(out,n.replace('WorldCommuting-OD/','').replace('/','__'));open(fn,'wb').write(d);print(fn,len(d))
