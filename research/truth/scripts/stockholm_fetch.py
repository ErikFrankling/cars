import urllib.request,urllib.error,json,hashlib,datetime
from pathlib import Path
D=Path('/home/erikf/projects/personal/cars-data/truth/stockholm')/('audit-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));D.mkdir(parents=True,exist_ok=False)
urls={
'city-count-sample.json':'https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:Trafikflode_Motorfordon&maxFeatures=3&outputFormat=application/json&srsName=EPSG:4326',
'rvu2024.pdf':'https://www.regionstockholm.se/49e914/contentassets/d6c4da12e11843c0ab8249c297dfd8fe/resvaneundersokning_for_stockholmsregionen_2024.pdf',
'city-climate2024.pdf':'https://meetingspublic.stockholm.se/welcome-sv/namnder-styrelser/miljo-och-halsoskyddsnamnden/mote-2025-06-10/agenda/13-2025-10981-bilaga-1-uppfoljning-av-stockholms-stads-klimatmal-2023-och-2024pdf?downloadMode=open',
'cordon2024.html':'https://www.transportstyrelsen.se/sv/om-oss/statistik-och-analys/statistik-inom-vagtrafik/trangselskatt-statistik/stockholm/statistik-2024/',
'api-info.html':'https://www.trafikverket.se/e-tjanster/trafikverkets-oppna-api-for-trafikinformation/',
'api-data.html':'https://data.trafikverket.se/',
'nvdb.html':'https://www.nvdb.se/sv/kund/hamta-aktuella-data/',
'vti969.pdf':'https://trafikverket.diva-portal.org/smash/get/diva2%3A1699487/FULLTEXT01.pdf',
'scb-api-root.json':'https://api.scb.se/OV0104/v1/doris/sv/ssd/AM',
'scb-deso.html':'https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/demografiska-statistikomraden-deso/deso-tabellerna-i-ssd--information-och-instruktioner/',
'kilometres.html':'https://www.trafa.se/vagtrafik/korstrackor/',
'vkm.html':'https://www.trafa.se/vagtrafik/trafikarbete/',
'sampers.html':'https://bransch.trafikverket.se/tjanster/system-och-verktyg/Prognos--och-analysverktyg/Sampers/',
'tomtom.html':'https://www.tomtom.com/traffic-index/city/stockholm/',
'post-kth.html':'https://www.byv.kth.se/en/avd/transportvetenskap/forskning-urban-mobi/prediktions-och-scenariobaserad-trafikledning-post-1.876335',
}
manifest=[];total=0
for name,url in urls.items():
    row=dict(file=name,url=url)
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'StockholmResearch/1.0'}),timeout=35) as r:
            body=r.read(25*1024*1024+1)
            if len(body)>25*1024*1024:raise ValueError('25 MiB per-file cap')
            total+=len(body)
            if total>5*1024**3:raise ValueError('5 GiB total cap')
            (D/name).write_bytes(body);row.update(status=r.status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),content_type=r.headers.get('Content-Type'),final_url=r.url)
    except Exception as e:row['error']=str(e)
    manifest.append(row);print(name,row.get('status',row.get('error')),row.get('bytes',0),flush=True)
(D/'manifest.json').write_text(json.dumps(manifest,indent=2));Path('research/truth/stockholm-fetch-manifest.json').write_text(json.dumps(dict(directory=str(D),total_bytes=total,fetches=manifest),indent=2));print(D)
