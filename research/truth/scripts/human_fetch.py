import urllib.request, struct, io, zipfile, pathlib, json, hashlib, zlib
root=pathlib.Path('/home/erikf/projects/personal/cars-data/truth/trajectories/human-20261031-pneuma')
root.mkdir(parents=True,exist_ok=False)
u='https://zenodo.org/records/10491409/files/pNEUMA_dataset.zip'
size=15759302461
used=0
def fetch(a,b):
 global used
 req=urllib.request.Request(u,headers={'Range':f'bytes={a}-{b}','User-Agent':'cars-research/1.0'})
 with urllib.request.urlopen(req,timeout=90) as r:
  if r.status!=206: raise RuntimeError(f'Range unsupported: {r.status}')
  d=r.read(b-a+2)
 if len(d)!=b-a+1: raise RuntimeError('range length mismatch')
 used+=len(d)
 if used>500_000_000: raise RuntimeError('budget')
 return d
tail=fetch(size-131072,size-1)
p=tail.rfind(b'PK\x05\x06')
e=struct.unpack_from('<4s4H2LH',tail,p)
cdsize,offset=e[5:7]
if offset==0xffffffff:
 loc=struct.unpack_from('<4sLQL',tail,p-20)
 z=fetch(loc[2],loc[2]+55)
 fields=struct.unpack('<4sQ2H2L4Q',z)
 cdsize,offset=fields[-2:]
cd=fetch(offset,offset+cdsize-1)
# ZipFile reads central directory from a synthetic empty-body archive; offsets remain metadata.
fake=cd+struct.pack('<4s4H2LH',b'PK\x05\x06',0,0,0,0,len(cd),0,0)
z=zipfile.ZipFile(io.BytesIO(fake))
infos=z.infolist()
(root/'archive-index.json').write_text(json.dumps([{'name':i.filename,'size':i.file_size,'compressed':i.compress_size,'offset':i.header_offset} for i in infos],indent=2))
print([(i.filename,i.compress_size,i.header_offset) for i in infos[:10]],flush=True)
i=next(i for i in infos if '20181024_d1_0830_0900.csv' in i.filename)
# synthetic archive causes ZipFile to rebase original offsets; read actual offset from raw directory
pos=0
while cd[pos:pos+4]==b'PK\x01\x02':
 h=struct.unpack_from('<4s6H3L5H2L',cd,pos); n,x,c=h[10:13]
 name=cd[pos+46:pos+46+n].decode()
 if name==i.filename:
  off=h[-1]; break
 pos+=46+n+x+c
header=fetch(off,off+29)
h=struct.unpack('<4s5H3L2H',header)
start=off+30+h[-2]+h[-1]
compressed=fetch(start,start+i.compress_size-1)
data=zlib.decompress(compressed,-15) if i.compress_type==8 else compressed
assert len(data)==i.file_size and zlib.crc32(data)==i.CRC
out=root/pathlib.Path(i.filename).name
out.write_bytes(data)
manifest={'source':u,'member':i.filename,'bytes_downloaded':used,'bytes_csv':len(data),'sha256':hashlib.sha256(data).hexdigest(),'path':str(out)}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest),flush=True)
