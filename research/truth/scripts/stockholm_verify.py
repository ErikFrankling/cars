import json,re,os
from pathlib import Path
O=Path('research/truth');s=(O/'02-stockholm-why-overloaded.md').read_text();missing=[]
for dest in re.findall(r'\]\(([^)]+)\)',s):
    if '://' not in dest and not (O/dest).exists():missing.append(dest)
for f in (O/'scripts').glob('stockholm_*.py'):compile(f.read_text(),str(f),'exec')
a=json.load(open(O/'stockholm-audit.json'));assert a['scheduled']['stockholm.rou.gz']==2919242;assert a['uturn_scheduled']==1356108;assert a['capacity']['over_full']==0
changed=[]
for r in json.load(open(O/'stockholm-input-manifest.json')):
    st=Path(r['file']).stat()
    if st.st_size!=r['size'] or st.st_mtime_ns!=r['mtime_ns']:changed.append(r['file'])
assert not missing,missing
assert not changed,changed
figures=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',s);assert len(figures)>=3
out=dict(local_links_ok=True,source_sizes_and_mtimes_unchanged=True,figures=len(figures),scripts_compile=True,report_words=len(s.split()))
(O/'stockholm-verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
