import urllib.request,pathlib,subprocess
r=pathlib.Path(pathlib.Path('research/truth/berlin-snapshot/download-dir.txt').read_text())
urls={'srv2018.pdf':'https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsdaten/zahlen-und-fakten/mobilitaet-in-staedten-srv-2018/berlin_tabellen_berlin_gesamt.pdf', 'svz2019.pdf':'https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsmanagement/verkehrserhebungen/ergebnisbericht-2019-teil-a.pdf'}
for name,url in urls.items():
 try:
  d=urllib.request.urlopen(url,timeout=40).read(25_000_001); assert len(d)<25_000_001; (r/name).write_bytes(d); print(name,len(d),url)
  subprocess.run(['pdftotext','-layout',str(r/name),str(r/(name+'.txt'))],stderr=subprocess.DEVNULL)
 except Exception as e: print(e)
