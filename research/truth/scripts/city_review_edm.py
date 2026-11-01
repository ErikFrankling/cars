"""Stream-read first sheet of EDM2018VIAJES.xlsx without external libs; also signal head census. Usage: city_review_edm.py run_dir out.json"""
import collections as C, json, pathlib, re, resource, sys, xml.etree.ElementTree as E, zipfile
resource.setrlimit(resource.RLIMIT_AS, (2900*1024**2, 2900*1024**2))
d = pathlib.Path(sys.argv[1]); out = {}
z = zipfile.ZipFile(d/'edm18-viajes.body'); print([ (i.filename, i.file_size) for i in z.infolist()][:12])
ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
ss = []
for ev, e in E.iterparse(z.open('xl/sharedStrings.xml')):
    if e.tag == ns+'si': ss.append(''.join(t.text or '' for t in e.iter(ns+'t'))); e.clear()
sheet = 'xl/worksheets/sheet1.xml'
hdr = None; n = 0; first = None; col = {}
hogar = set(); zo = C.Counter(); modes = C.Counter(); hrs = C.Counter(); elev = 0.0
for ev, e in E.iterparse(z.open(sheet)):
    if e.tag == ns+'row':
        vals = {}
        for c in e:
            ref = re.match(r'[A-Z]+', c.attrib['r']).group(0); v = c.find(ns+'v')
            if v is None: continue
            vals[ref] = ss[int(v.text)] if c.attrib.get('t') == 's' else v.text
        if hdr is None:
            hdr = {k: v for k, v in vals.items()}; col = {v: k for k, v in hdr.items()}
        else:
            n += 1; first = first or {hdr.get(k, k): v for k, v in vals.items()}
        e.clear()
print('rows', n); print(list(hdr.values())); print(first)
out.update(rows=n, columns=list(hdr.values()), first=first)
pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
l = json.load(open(d/'sthlm-lykta-all.body', encoding='utf-8'))['features']
print('heads', len(l), 'installations', len({f['properties'].get('anläggnings-id') for f in l}), C.Counter((f['properties'].get('typ') or '')[:18] for f in l).most_common(8))
