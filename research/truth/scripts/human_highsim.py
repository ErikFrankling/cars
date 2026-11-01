from pathlib import Path
import urllib.request,hashlib,json,zipfile,xml.etree.ElementTree as E
r=Path('/home/erikf/projects/personal/cars-data/truth/trajectories/human-20261031-highsim');r.mkdir(parents=True,exist_ok=False)
base='https://raw.githubusercontent.com/CATS-Lab/Filed-Experiment-Data-HIGH_Sim/main/'
manifest=[]
for name in ['1-90.xlsx','data_description2026.docx','README.md']:
 with urllib.request.urlopen(base+name,timeout=60) as f:
  data=f.read(50_000_001)
 if len(data)>50_000_000: raise RuntimeError('cap')
 (r/name).write_bytes(data);manifest.append(dict(name=name,url=base+name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 if name.endswith('docx'):
  with zipfile.ZipFile(r/name) as z:
   t=E.fromstring(z.read('word/document.xml')); print(' '.join(t.itertext())[:12000])
 if name.endswith('xlsx'):
  with zipfile.ZipFile(r/name) as z:
   ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
   strings=[''.join(a.itertext()) for a in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
   t=E.fromstring(z.read('xl/worksheets/sheet1.xml'))
   for row in t.findall('.//s:row',ns)[:5]:
    print([(c.get('r'),strings[int(c.find('s:v',ns).text)] if c.get('t')=='s' else c.findtext('s:v',default='',namespaces=ns)) for c in row])
(r/'manifest.json').write_text(json.dumps(manifest,indent=2));print(manifest)
