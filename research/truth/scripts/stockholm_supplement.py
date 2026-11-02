import json,urllib.request,hashlib,datetime
from pathlib import Path
O=Path('research/truth');D=Path('/home/erikf/projects/personal/cars-data/truth/stockholm')/('supplement-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));D.mkdir(parents=True,exist_ok=False)
urls={
'sampers-stockholm-validation2018.pdf':'https://bransch.trafikverket.se/contentassets/d7cf7d727fb2488aab9fa9d24387c7c8/externa-rapporter/2018/validering_o_kansl_analys_sampers_stockholm_ver1p1_180410.pdf',
'dynameq-stockholm-manual.pdf':'https://bransch.trafikverket.se/contentassets/38911a0f4c0e4ee9a507272aba8d640c/dynameq-storstockholm-anvandarhandledning.pdf',
'vissim-stockholm2010.pdf':'https://kth.diva-portal.org/smash/get/diva2%3A321836/FULLTEXT01.pdf',
'national-rvu2024.pdf':'https://www.trafa.se/globalassets/statistik/resvanor/2025/resvanor-i-sverige-2024.pdf',
'mcs-tms-map.html':'https://vtf.trafikverket.se/SeTrafikfloden',
'api-datamodel.html':'https://data.trafikverket.se/documentation/datacache/data-model',
'scb-rams.json':'https://api.scb.se/OV0104/v1/doris/sv/ssd/AM/AM0207',
}
manifest=[]
for name,url in urls.items():
    row=dict(file=name,url=url)
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'StockholmResearch/1.0'}),timeout=30) as r:
            b=r.read(25*1024*1024+1)
            if len(b)>25*1024*1024:raise ValueError('cap')
            (D/name).write_bytes(b);row.update(status=r.status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),content_type=r.headers.get('Content-Type'))
    except Exception as e:row['error']=str(e)
    manifest.append(row);print(name,row,flush=True)
(O/'stockholm-supplement-manifest.json').write_text(json.dumps(dict(directory=str(D),fetches=manifest),indent=2));(D/'manifest.json').write_text(json.dumps(manifest,indent=2))
files=['stockholm.net.xml','stockholm.rou.gz','stockholm60.rou.gz','trafikflode_motorfordon.geojson','count_matches.csv','demand_fit.json','cars.summary.csv','cars.edges.csv','cars.trips.csv','cars.log']
P=Path('/home/erikf/projects/personal/cars-data/stockholm');out=[]
for name in files:
    p=P/name;s=p.stat();h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    out.append(dict(file=str(p),size=s.st_size,mtime_ns=s.st_mtime_ns,sha256=h.hexdigest()))
(O/'stockholm-input-manifest.json').write_text(json.dumps(out,indent=2))
