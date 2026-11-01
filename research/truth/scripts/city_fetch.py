"""Bounded, serial curl evidence acquisition; never executes downloaded material."""
import datetime, hashlib, json, pathlib, resource, subprocess, sys
resource.setrlimit(resource.RLIMIT_AS, (1500*1024**2,1500*1024**2))
base=pathlib.Path('/home/erikf/projects/personal/cars-data/truth/city-ground-truth')
base.mkdir(parents=True,exist_ok=True)
dest=base/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
dest.mkdir()
items=[
('stockholm-capabilities','https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&request=GetCapabilities'),
('berlin-index','https://api.viz.berlin.de/daten/verkehrsdetektion'),
('madrid-live','https://informo.madrid.es/informo/tmadrid/pm.xml'),
('madrid-catalog','https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico'),
('paris-sample','https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?limit=5'),
('zurich-catalog','https://data.stadt-zuerich.ch/api/3/action/package_show?id=sid_dav_verkehrszaehlung_miv_od2031'),
('utd19','https://utd19.ethz.ch/'),
('finland-stations','https://tie.digitraffic.fi/api/tms/v1/stations'),
('finland-data','https://tie.digitraffic.fi/api/tms/v1/stations/1/data'),
('ndw-speeds','https://opendata.ndw.nu/trafficspeed.xml.gz'),
('ndw-times','https://opendata.ndw.nu/traveltime.xml.gz'),
('norway-doc','https://trafikkdata-api.atlas.vegvesen.no/'),
('webtris-sites','https://webtris.highwaysengland.co.uk/api/v1.0/sites'),
('pems','https://pems.dot.ca.gov/'),
('intas-readme','https://raw.githubusercontent.com/silaslobo/InTAS/master/README.md'),
('lust-readme','https://raw.githubusercontent.com/lcodeca/LuSTScenario/master/README.md'),
('cologne-doc','https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html'),
('pneuma','https://open-traffic.epfl.ch/'),
('pneuma-fetch-source','https://raw.githubusercontent.com/EPFL-ENAC/pNEUMA/main/data_processing/fetch_data.py'),
('i24-data','https://i24motion.org/data'),
]
if len(sys.argv)>1:
 items=json.loads(pathlib.Path(sys.argv[1]).read_text())
log=[]
for name,url in items:
 p=dest/(name+'.body')
 cmd=['curl','--silent','--show-error','--location','--connect-timeout','10','--max-time','35','--max-filesize','12000000','--dump-header',str(dest/(name+'.headers')),'--output',str(p),'--write-out','%{http_code} %{size_download} %{url_effective}',url]
 cmd.insert(1,'--compressed')
 if name=='norway-post':
  cmd[1:1]=['--header','Content-Type: application/json','--data','{"query":"{trafficRegistrationPoints{id name}}"}']
 if name=='norway-volume':
  cmd[1:1]=['--header','Content-Type: application/json','--data',json.dumps({'query':'{trafficData(trafficRegistrationPointId:"52742V2282262"){volume{byHour(from:"2024-01-01T00:00:00+01:00",to:"2024-01-02T00:00:00+01:00"){edges{node{from to total{volumeNumbers{volume}}}}}}}}'})]
 if name.endswith('-large'):
  cmd[cmd.index('12000000')]='180000000'
  cmd[cmd.index('35')]='90'
 if name.endswith('-range'):
  cmd[1:1]=['--range','0-65535']
 r=subprocess.run(cmd,capture_output=True,text=True)
 b=p.read_bytes() if p.exists() else b''
 row=dict(name=name,url=url,curl_exit=r.returncode,result=r.stdout,error=r.stderr,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),command=cmd)
 log.append(row)
 print(json.dumps(row),flush=True)
(dest/'manifest.json').write_text(json.dumps(log,indent=2))
print('DIRECTORY',dest,flush=True)
