import urllib.request,pathlib,subprocess,xml.etree.ElementTree as ET,re
from lxml import html
r=pathlib.Path(pathlib.Path('research/truth/berlin-snapshot/download-dir.txt').read_text())
urls={
'srv-page.html':'https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsdaten/zahlen-und-fakten/mobilitaet-in-staedten-srv-2018/',
'bus-page.html':'https://www.tib-op.org/ojs/index.php/scp/article/view/2613',
'best2023.pdf':'https://publica-rest.fraunhofer.de/server/api/core/bitstreams/ec00a2d5-a123-4a5d-90e2-25f3612c37b4/content'}
listing=ET.parse('/home/erikf/projects/personal/cars-data/berlin-detectors/list.xml')
for b in listing.findall('.//Blob'):
 if 'readme' in b.findtext('Name','').lower(): urls['detector-readme.txt']=b.findtext('Url')
for name,url in list(urls.items()):
 try:
  data=urllib.request.urlopen(url,timeout=35).read(25_000_001); assert len(data)<25_000_001
  (r/name).write_bytes(data); print(name,url,len(data))
  if data.startswith(b'%PDF'): subprocess.run(['pdftotext','-layout',str(r/name),str(r/(name+'.txt'))],stderr=subprocess.DEVNULL)
  if name.endswith('.html'):
   doc=html.fromstring(data)
   for a in doc.xpath('//a[@href]'):
    u=a.get('href')
    if ('tabellen' in u and '.pdf' in u) or '/article/view/2613/' in u or '/article/download/2613/' in u: print('LINK',u)
 except Exception as e: print(e)
