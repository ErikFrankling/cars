from pathlib import Path
import urllib.request,re,json
from lxml import html
r=Path(Path('research/truth/berlin-snapshot/download-dir.txt').read_text()); u='https://www.berlin.de/umweltatlas/verkehr-laerm/verkehrsmengen/2019/einleitung/'; d=urllib.request.urlopen(u,timeout=25).read(2000000); (r/'vkm-page.html').write_bytes(d)
for x in html.fromstring(d).xpath('//*[@src or @href]'):
 v=x.get('src',x.get('href',''))
 if 'datawrapper' in v or 'dwcdn' in v:
  print(v)
  try:
   dd=urllib.request.urlopen(v,timeout=20).read(2000000); (r/('dw-'+re.sub('[^a-zA-Z0-9]','_',v)[-100:]+'.html')).write_bytes(dd)
   ss=html.fromstring(dd).text_content(); print(ss[-4500:])
  except Exception as e: print(e)
