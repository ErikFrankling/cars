import sys,glob,zipfile,re,xml.etree.ElementTree as E,json
ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
for f in sorted(glob.glob(sys.argv[1]+'/*/*.xlsx')):
    print('=====',f.split('/')[-2:])
    z=zipfile.ZipFile(f)
    ss=[''.join(t.text or '' for t in si.iter(ns+'t')) for si in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    for name in z.namelist():
        if not name.startswith('xl/worksheets/sheet'): continue
        for row in E.fromstring(z.read(name)).iter(ns+'row'):
            out=[]
            for c in row:
                v=c.find(ns+'v'); t=c.get('t')
                if v is None:
                    i=c.find(ns+'is')
                    if i is not None: out.append(''.join(x.text or '' for x in i.iter(ns+'t')))
                    continue
                out.append(ss[int(v.text)] if t=='s' else v.text)
            if out: print(' | '.join(out)[:330])
for id in ['97n2-kuqi','7zjf-a4zf','9uas-hf8b','brzy-6zfh']:
    j=json.load(open(sys.argv[2]+f'/{id}.json'));print('=== DESC',id);print(j['description'])
