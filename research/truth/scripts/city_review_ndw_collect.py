"""Minute collector for NDW open v3 feeds, keeps only sites inside a bbox and appends raw records to daily gz files.
Usage: city_review_ndw_collect.py outdir minutes [lat0 lat1 lon0 lon1]. minutes=1 is a single test pass; 0 is forever.
Untrusted XML is parsed, never executed. No retries beyond the next minute."""
import datetime as T, gzip, io, pathlib, re, subprocess, sys, time, xml.etree.ElementTree as E
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); n = int(sys.argv[2])
B = [float(x) for x in sys.argv[3:7]] or [52.30, 52.45, 4.70, 5.00]
U = 'https://opendata.ndw.nu/'
FEEDS = {'tt': ('reistijden_meetgegevens.xml.gz', 'reistijden_configuratie_meetlocaties.xml.gz'),
         'q': ('snelheden_en_intensiteiten_meetgegevens.xml.gz', 'snelheden_en_intensiteiten_configuratie_meetlocaties.xml.gz')}
def get(name, cap=200000000):
    r = subprocess.run(['curl', '--silent', '--show-error', '--fail', '--max-time', '50', '--max-filesize', str(cap), U+name], capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr.decode()[:200])
    return gzip.decompress(r.stdout)
loc = lambda t: t.rsplit('}', 1)[-1]
def sites(cfg):
    keep = set()
    for ev, e in E.iterparse(io.BytesIO(get(cfg))):
        if loc(e.tag) != 'measurementSite': continue
        la = [float(x.text) for x in e.iter() if loc(x.tag) == 'latitude']; lo = [float(x.text) for x in e.iter() if loc(x.tag) == 'longitude']
        for x in e.iter():
            if loc(x.tag) == 'posList' and x.text:
                v = [float(a) for a in x.text.split()]; la += v[0::2]; lo += v[1::2]
        if la and all(B[0] < a < B[1] for a in la) and all(B[2] < o < B[3] for o in lo): keep.add(e.attrib['id'])
        e.clear()
    return keep
K = {k: sites(v[1]) for k, v in FEEDS.items()}
print({k: len(v) for k, v in K.items()}, flush=True)
(out/'site_ids.txt').write_text('\n'.join(f'{k} {s}' for k, v in K.items() for s in sorted(v))+'\n')
i = 0
while n == 0 or i < n:
    t0 = time.time(); i += 1
    for k, (data, _) in FEEDS.items():
        try:
            raw = get(data); kept = 0
            day = T.datetime.now(T.timezone.utc).strftime('%Y-%m-%d')
            stamp = re.search(rb'publicationTime>([^<]+)<', raw[:2000]).group(1).decode()
            with gzip.open(out/f'{k}_{day}.xml.gz', 'at', encoding='utf-8') as f:
                f.write(f'<snapshot t="{stamp}">\n')
                for ev, e in E.iterparse(io.BytesIO(raw)):
                    if loc(e.tag) == 'siteMeasurements':
                        ref = next((x.attrib.get('id') for x in e if loc(x.tag) == 'measurementSiteReference'), None)
                        if ref in K[k]:
                            f.write(re.sub(r' xmlns:\w+="[^"]+"', '', E.tostring(e, encoding='unicode'))+'\n'); kept += 1
                        e.clear()
                f.write('</snapshot>\n')
            print(k, stamp, kept, flush=True)
        except Exception as x:
            print('ERR', k, x, flush=True)
    if n == 0 or i < n: time.sleep(max(1, 60-(time.time()-t0)))
