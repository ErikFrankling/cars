import urllib.request, pathlib, datetime, json, subprocess
root=pathlib.Path('/home/erikf/projects/personal/cars-data/truth/berlin')/('forensics-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')); root.mkdir(parents=True,exist_ok=False)
urls={
'matsim2019.pdf':'https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2019/19-01/ZiemkeEtAl2019OpenBerlinScenarioVSPWP.pdf',
'matsim2024.pdf':'https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2024/24-22/RakowEtAl_MATSimBerlinEWGT.pdf',
'best-readme.md':'https://raw.githubusercontent.com/mosaic-addons/best-scenario/main/README.md',
'bus2025.pdf':'https://www.tib-op.org/ojs/index.php/scp/article/download/2613/2808',
'mid.pdf':'https://www.bmv.de/SharedDocs/DE/Anlage/G/mid-ergebnisbericht.pdf?__blob=publicationFile',
'detector-readme.txt':'https://api.viz.berlin.de/daten/verkehrsdetektion/ReadMe.txt'}
manifest=[]
for name,url in urls.items():
 try:
  with urllib.request.urlopen(url,timeout=45) as r: data=r.read(25_000_001)
  if len(data)>25_000_000: raise ValueError('25 MB per-file cap')
  (root/name).write_bytes(data); print(name,len(data),data[:20])
  manifest.append(dict(name=name,url=url,bytes=len(data)))
  if data.startswith(b'%PDF'): subprocess.run(['pdftotext','-layout',str(root/name),str(root/(name+'.txt'))],check=True)
 except Exception as e: print(name,str(e)); manifest.append(dict(name=name,url=url,error=str(e)))
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)); pathlib.Path('research/truth/berlin-snapshot/download-dir.txt').write_text(str(root)); print(root)
