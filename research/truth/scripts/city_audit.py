import collections,csv,gzip,io,json,pathlib,resource,xml.etree.ElementTree as E,zipfile
resource.setrlimit(resource.RLIMIT_AS,(1800*1024**2,1800*1024**2))
base=pathlib.Path('/home/erikf/projects/personal/cars-data/truth/city-ground-truth')
def find(name):
 return next(p for d in sorted(base.iterdir(),reverse=True) if (p:=d/(name+'.body')).exists() and p.stat().st_size)
out={}
with gzip.open(find('berlin-data'),'rt') as f:
 r=csv.DictReader(f,delimiter=';'); ids=set(); n=0; first=None
 for row in r:
  n+=1; ids.add(row['detid_15']); first=first or row
 out['berlin']={'rows':n,'detector_ids':len(ids),'first':first}
p=find('madrid-large')
with zipfile.ZipFile(p) as z:
 out['madrid_zip']=[{'name':x.filename,'bytes':x.file_size} for x in z.infolist()]
 name=next(x.filename for x in z.infolist() if x.filename.endswith('.csv'))
 with z.open(name) as f:
  r=csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig'),delimiter=';'); ids=set(); n=0; errors=collections.Counter(); dates=set(); first=None
  for row in r:
   n+=1; ids.add(row.get('id')); errors[row.get('error')]+=1; dates.add(row.get('fecha','').split()[0]); first=first or row
  out['madrid']={'rows':n,'point_ids':len(ids),'dates':len(dates),'errors':errors,'first':first}
for name in ['ndw-config','ndw-speed-config']:
 with gzip.open(find(name),'rb') as f: root=E.parse(f).getroot()
 sites=[e for e in root.iter() if e.tag.endswith('}measurementSite')]
 ams=[e for e in sites if any('A10' in ''.join(c.itertext()) for c in e if c.tag.endswith('}measurementSiteName'))]
 ns='{http://datex2.eu/schema/3/locationReferencing}'
 bbox=[e for e in sites if any(52.30<float(x.text)<52.45 for x in e.iter(ns+'latitude')) and any(4.7<float(x.text)<5.0 for x in e.iter(ns+'longitude'))]
 out[name]={'sites_national':len(sites),'a10_name_matches':len(ams),'amsterdam_bbox_point_records':len(bbox),'bbox_lat_lon':[52.30,52.45,4.7,5.0],'a10_example':E.tostring(ams[0],encoding='unicode')[:4000] if ams else None}
out['finland_raw']={'first_lines':find('finland-raw').read_text().splitlines()[:3]}
out['madrid_live']={'points':len(E.parse(find('madrid-live')).getroot().findall('pm'))}
out['bytes_stored']=sum(p.stat().st_size for p in base.glob('*/*'))
pathlib.Path('research/truth/01-city-sample-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps(out,indent=2,ensure_ascii=False)[:14000])
