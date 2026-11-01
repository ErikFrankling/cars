"""List a remote ZIP via HTTP range requests and save members whose name matches, bytes only, never executed.
Usage: city_review_rangezip.py url outdir [regex] [max_members]"""
import io, pathlib, re, sys, urllib.request, zipfile
class R(io.RawIOBase):
    def __init__(s, u):
        s.u = u; s.p = 0; s.n = 0
        q = urllib.request.Request(u, method='HEAD', headers={'User-Agent': 'research audit'})
        s.size = int(urllib.request.urlopen(q, timeout=60).headers['Content-Length'])
    def seekable(s): return True
    def readable(s): return True
    def seek(s, o, w=0):
        s.p = o if w == 0 else (s.p+o if w == 1 else s.size+o); return s.p
    def tell(s): return s.p
    def read(s, n=-1):
        if n < 0: n = s.size-s.p
        if n == 0 or s.p >= s.size: return b''
        q = urllib.request.Request(s.u, headers={'Range': f'bytes={s.p}-{s.p+n-1}', 'User-Agent': 'research audit'})
        b = urllib.request.urlopen(q, timeout=120).read(); s.p += len(b); s.n += len(b); return b
    def readinto(s, b):
        x = s.read(len(b)); b[:len(x)] = x; return len(x)
f = R(sys.argv[1]); z = zipfile.ZipFile(io.BufferedReader(f, 1 << 20))
il = z.infolist(); print('size', f.size, 'members', len(il)); print([ (i.filename, i.file_size) for i in il[:12]])
if len(sys.argv) > 3:
    out = pathlib.Path(sys.argv[2]); out.mkdir(exist_ok=True, parents=True); m = 0
    for i in il:
        if re.search(sys.argv[3], i.filename) and not i.is_dir():
            (out/pathlib.Path(i.filename).name).write_bytes(z.read(i)); print('saved', i.filename, i.file_size); m += 1
            if m >= int(sys.argv[4]): break
print('range bytes fetched', f.n)
