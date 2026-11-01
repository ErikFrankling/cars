# Tested curl retrieval ledger

2026-10-31. Full commands as executed; replay into a new empty directory by changing output/header paths. A 200 HTML page is not an observation sample. Byte counts below are stored payload bytes; compressed HTTP transfer sizes can differ.

| Request | curl exit / HTTP | Stored bytes | SHA-256 |
|---|---|---:|---|
| [stockholm-capabilities](https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&request=GetCapabilities) | 0 / 200 | 89769 | `fc414d918f87b868ca72de984681fe3efcec0599f717e361f89470251796bd28` |
| [berlin-index](https://api.viz.berlin.de/daten/verkehrsdetektion) | 0 / 200 | 1389 | `9bb114ee7e488909c8f91fb34cb430f33e71ca0d2f9681ec218318ff3131c796` |
| [madrid-live](https://informo.madrid.es/informo/tmadrid/pm.xml) | 0 / 200 | 2189821 | `f929d5b48a7b2d40e31864009fdac33d842aab93600d8414578886405cdb167a` |
| [madrid-catalog](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico) | 0 / 200 | 301062 | `86602fa0d530264166fcb446f0be35f589d2556ef7ad971204e4ec83c10d6740` |
| [paris-sample](https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?limit=5) | 0 / 200 | 3065 | `8b57ee39c3c077aaaa87e8e43722f4f014b31d9353fd15595f0d855c7070b080` |
| [zurich-catalog](https://data.stadt-zuerich.ch/api/3/action/package_show?id=sid_dav_verkehrszaehlung_miv_od2031) | 0 / 200 | 62689 | `a0926bcb27e49f54cfe88855df48ff33307e1593848489ee30ef540965219ee3` |
| [utd19](https://utd19.ethz.ch/) | 0 / 200 | 39530 | `6d8bc72c916f262b172a5c4140184fa269bd397c64cbe0d67832f3e861164720` |
| [finland-stations](https://tie.digitraffic.fi/api/tms/v1/stations) | 0 / 406 | 70 | `f1195aff3280286844e4147adb76129911c0554cfbba10a4c0ab2527fd9be71c` |
| [finland-data](https://tie.digitraffic.fi/api/tms/v1/stations/1/data) | 0 / 406 | 70 | `f1195aff3280286844e4147adb76129911c0554cfbba10a4c0ab2527fd9be71c` |
| [ndw-speeds](https://opendata.ndw.nu/trafficspeed.xml.gz) | 0 / 200 | 1023707 | `f741cb42ecc06af1d07a9ca44911428fa8a0ca2f3507b9c190f736ee324afba0` |
| [ndw-times](https://opendata.ndw.nu/traveltime.xml.gz) | 0 / 200 | 2292696 | `7e77b4dc2ab0448af38838ae5c9ab7c22f83197e53dc2342dd1a9c4398d49b47` |
| [norway-doc](https://trafikkdata-api.atlas.vegvesen.no/) | 0 / 410 | 141 | `4136cdfb2e2e6152bb7679875398ba36f40d4ae0ecbea5f3751baed36b5ee63d` |
| [webtris-sites](https://webtris.highwaysengland.co.uk/api/v1.0/sites) | 0 / 200 | 4387233 | `ff358e67ab1383c302752907024f52cafb77a1950dd948ff1967d8094e007070` |
| [pems](https://pems.dot.ca.gov/) | 0 / 200 | 22289 | `a2f14a75670de059906fb96a99a74c6001e35703ceca8cd716521f4494a95438` |
| [intas-readme](https://raw.githubusercontent.com/silaslobo/InTAS/master/README.md) | 0 / 200 | 2304 | `8ae4272b997fb68d3806f8414172844b8015cf44f81723a5d8d11412b241e87c` |
| [lust-readme](https://raw.githubusercontent.com/lcodeca/LuSTScenario/master/README.md) | 0 / 200 | 1776 | `3836e71b27148bdd9e4571b9fffc622a7886719e76d0c08fc424bb969f511aa6` |
| [cologne-doc](https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html) | 0 / 200 | 29618 | `ad36955f8aaba1698fcd030101a31ddea5bd210a8f05e41b66b0bd86ef902b8c` |
| [pneuma](https://open-traffic.epfl.ch/) | 0 / 200 | 136063 | `6549239eb7d21558c8c5ccd43883dc58a3756c8f06d5b52766f84891c6ab7182` |
| [pneuma-fetch-source](https://raw.githubusercontent.com/EPFL-ENAC/pNEUMA/main/data_processing/fetch_data.py) | 0 / 200 | 2648 | `350783986b566f26e16dae5898b1d54de59cbc063fd8e6fa16619acb5b17820c` |
| [i24-data](https://i24motion.org/data) | 60 / 000 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [stockholm-features](https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:Trafikflode_Motorfordon&maxFeatures=3&outputFormat=application/json) | 0 / 200 | 5056 | `e3a902f819f81f2714a451973c4b5d2959f01156c8098901f7d2a4ec9b573caf` |
| [berlin-list](https://mdhopendata.blob.core.windows.net/verkehrsdetektion/?restype=container&comp=list&maxresults=40) | 0 / 200 | 25148 | `ba5006ff93f206d48bbe5ba2569e2fd49d1d161efd63895fe55b7a2dbdd1750f` |
| [berlin-data](https://mdhopendata.blob.core.windows.net/verkehrsdetektion/2015/alte_qualitaetssicherung/Fahrstreifendetektoren/det_val_hr_2015_01.csv.gz) | 0 / 200 | 4634033 | `83c2e9d7bd58d262e89269041dbbfb3d774e1cfb16a3dd8b7188fd899a2d1713` |
| [madrid-api](https://datos.madrid.es/api/3/action/package_show?id=208627-0-transporte-ptomedida-historico) | 0 / 200 | 238319 | `516f8e219b34b43ce407bc6f5d3621dfa490801a9d36f3ddc6380e3fc0e63d08` |
| [madrid-doc](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-81-transporte-ptomedida-historico/download/208627-81-transporte-ptomedida-historico.pdf) | 0 / 200 | 991314 | `17562978ce1b7930c6c720db37f055cb3459e30b8cec50d2a671682b215b9de9` |
| [paris-valid](https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?where=q%20is%20not%20null&limit=5) | 0 / 200 | 3121 | `2c9f4d1c683a1fc153cf45aa6df9dbd6c609fd37751ce8ffa0ca12eee9d21772` |
| [zurich-range](https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031/download/sid_dav_verkehrszaehlung_miv_OD2031_2012.csv) | 0 / 206 | 65536 | `ab4dc711c5889412d5831f67a279340d7a2db764c9e7f36c6cbc24fa9274fb91` |
| [finland-stations](https://tie.digitraffic.fi/api/tms/v1/stations) | 0 / 200 | 209849 | `b078a5afd9df3793db79b09e65d8c62ca73a17e1865c51c413edaaacff58d2a8` |
| [finland-data](https://tie.digitraffic.fi/api/tms/v1/stations/1/data) | 0 / 404 | 208 | `e248e4d07d4fa80d0beda5b400dd7d782d38258ebbb109897ffa3c5224c2c294` |
| [finland-raw](https://tie.digitraffic.fi/api/tms/v1/history/raw/lamraw_101_24_1.csv) | 0 / 200 | 1673804 | `aa103d7ca8cbc1b42f1d4bef267f74b3494e5d14819bc9644e9c1c28b25a7248` |
| [norway-explorer](https://www.trafikkdata.no/graphql) | 0 / 200 | 3091 | `c0f5bee739630a9b494f2b4a35821110651da398500c1ace691ba75efd5425d4` |
| [webtris-report](https://webtris.highwaysengland.co.uk/api/v1.0/reports/Daily?sites=1&start_date=01062024&end_date=01062024&page=1&page_size=10) | 0 / 204 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [pneuma-zenodo](https://zenodo.org/api/records/7426506) | 0 / 200 | 8904 | `159c922a639211c09096460b8d8401e4a4bcfc296477f2e6a6bb522ce667c023` |
| [i24-www](https://www.i24motion.org/data) | 6 / 000 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [ndw-config](https://opendata.ndw.nu/reistijden_configuratie_meetlocaties.xml.gz) | 0 / 200 | 2935159 | `ea5a4beecdf5dc1e74ee4154b7d3c5c46b8a2ee5d49b043d71042e1438217749` |
| [ndw-speed-config](https://opendata.ndw.nu/snelheden_en_intensiteiten_configuratie_meetlocaties.xml.gz) | 0 / 200 | 1843832 | `612e4285544704a5dac0e94d3ea7abe2d7c310fb4971507b7670843c7d54904e` |
| [madrid-large](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-0-transporte-ptomedida-historico-zip/download/208627-0-transporte-ptomedida-historico-zip.zip) | 0 / 200 | 79348668 | `52af4a4afef4172522d80974cc5c248fc2ab4afcf65d7751f50a7b6ab9729444` |
| [finland-station-data](https://tie.digitraffic.fi/api/tms/v1/stations/101/data) | 0 / 404 | 212 | `3660fa76eb08a65591acd8515ad6d9f763a89de2c62ab6a8e90f2dd00b0a418c` |
| [pneuma-original-meta](https://zenodo.org/api/records/10491409) | 0 / 200 | 6450 | `be6ea5a33609396eb1c9eaa34b80e92c2469c8257e4629793f5c965aa277a36e` |
| [norway-points](https://trafikkdata-api.atlas.vegvesen.no/?query=%7BtrafficRegistrationPoints%7Bid%20name%7D%7D) | 0 / 410 | 141 | `4136cdfb2e2e6152bb7679875398ba36f40d4ae0ecbea5f3751baed36b5ee63d` |
| [melbourne-api](https://opendata.transport.vic.gov.au/api/3/action/package_show?id=traffic-signal-volume-data) | 0 / 200 | 93962 | `dfb04f24bd2f99528cc5e9221b81ed600d096585e86c674b033c2d7fa67361d9` |
| [melbourne-large](https://opendata.transport.vic.gov.au/dataset/331b846b-1e18-415f-a3f3-ce4198d86c82/resource/001ace40-280b-462d-b580-7a79e70185fb/download/traffic_signal_volume_data_october_2026.zip) | 0 / 200 | 127428210 | `40067ebbdc3bd3c8241641d7ef5ce4ac744b2f6e2dd663c51346e5ded83d321b` |
| [pneuma-readme](https://zenodo.org/records/10491409/files/README.html?download=1) | 0 / 200 | 4252 | `3f6b24677ee49fdefec1e86fa1b0c0e112ab49f2682c591d385811338298b85d` |
| [berlin-readme-list](https://mdhopendata.blob.core.windows.net/verkehrsdetektion/?restype=container&comp=list&prefix=read&maxresults=20) | 0 / 200 | 230 | `779f89f5164aaf48e2b7b31f64b4b9b3fb38296252f60039b6f31938f3e95724` |
| [norway-new-points](https://www.trafikkdata.no/api/?query=%7BtrafficRegistrationPoints%7Bid%20name%7D%7D) | 0 / 200 | 3091 | `c0f5bee739630a9b494f2b4a35821110651da398500c1ace691ba75efd5425d4` |
| [paris-metadata](https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents) | 0 / 200 | 18570 | `2f0c95dd42051b17c91ca0ac2e5aa895dcad2901146a58990bc9858d31985760` |
| [norway-api-doc](https://www.trafikkdata.no/graphql) | 0 / 200 | 3091 | `c0f5bee739630a9b494f2b4a35821110651da398500c1ace691ba75efd5425d4` |
| [norway-post](https://trafikkdata-api.atlas.vegvesen.no/) | 0 / 200 | 487914 | `50369263d1aa8cb61578a6b4542b725471f304d224d39d29aaea04990ea40017` |
| [norway-volume](https://trafikkdata-api.atlas.vegvesen.no/) | 0 / 200 | 2942 | `d01e6f2733708558efd8bc170a35d31c06918b49811777a0c8117471e970fe1d` |

Total stored response bodies: 230,621,047 bytes.

## Exact commands

### stockholm-capabilities

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/stockholm-capabilities.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/stockholm-capabilities.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&request=GetCapabilities'
```

Result: `200 89769 https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&request=GetCapabilities`. 

### berlin-index

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/berlin-index.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/berlin-index.body --write-out '%{http_code} %{size_download} %{url_effective}' https://api.viz.berlin.de/daten/verkehrsdetektion
```

Result: `200 1389 https://api.viz.berlin.de/daten/verkehrsdetektion`. 

### madrid-live

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/madrid-live.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/madrid-live.body --write-out '%{http_code} %{size_download} %{url_effective}' https://informo.madrid.es/informo/tmadrid/pm.xml
```

Result: `200 2189821 https://informo.madrid.es/informo/tmadrid/pm.xml`. 

### madrid-catalog

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/madrid-catalog.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/madrid-catalog.body --write-out '%{http_code} %{size_download} %{url_effective}' https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico
```

Result: `200 301062 https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico`. 

### paris-sample

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/paris-sample.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/paris-sample.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?limit=5'
```

Result: `200 3065 https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?limit=5`. 

### zurich-catalog

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/zurich-catalog.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/zurich-catalog.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://data.stadt-zuerich.ch/api/3/action/package_show?id=sid_dav_verkehrszaehlung_miv_od2031'
```

Result: `200 62689 https://data.stadt-zuerich.ch/api/3/action/package_show?id=sid_dav_verkehrszaehlung_miv_od2031`. 

### utd19

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/utd19.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/utd19.body --write-out '%{http_code} %{size_download} %{url_effective}' https://utd19.ethz.ch/
```

Result: `200 39530 https://utd19.ethz.ch/`. 

### finland-stations

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/finland-stations.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/finland-stations.body --write-out '%{http_code} %{size_download} %{url_effective}' https://tie.digitraffic.fi/api/tms/v1/stations
```

Result: `406 70 https://tie.digitraffic.fi/api/tms/v1/stations`. 

### finland-data

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/finland-data.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/finland-data.body --write-out '%{http_code} %{size_download} %{url_effective}' https://tie.digitraffic.fi/api/tms/v1/stations/1/data
```

Result: `406 70 https://tie.digitraffic.fi/api/tms/v1/stations/1/data`. 

### ndw-speeds

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/ndw-speeds.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/ndw-speeds.body --write-out '%{http_code} %{size_download} %{url_effective}' https://opendata.ndw.nu/trafficspeed.xml.gz
```

Result: `200 1023707 https://opendata.ndw.nu/trafficspeed.xml.gz`. 

### ndw-times

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/ndw-times.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/ndw-times.body --write-out '%{http_code} %{size_download} %{url_effective}' https://opendata.ndw.nu/traveltime.xml.gz
```

Result: `200 2292696 https://opendata.ndw.nu/traveltime.xml.gz`. 

### norway-doc

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/norway-doc.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/norway-doc.body --write-out '%{http_code} %{size_download} %{url_effective}' https://trafikkdata-api.atlas.vegvesen.no/
```

Result: `410 141 https://trafikkdata-api.atlas.vegvesen.no/`. 

### webtris-sites

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/webtris-sites.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/webtris-sites.body --write-out '%{http_code} %{size_download} %{url_effective}' https://webtris.highwaysengland.co.uk/api/v1.0/sites
```

Result: `200 4387233 https://webtris.highwaysengland.co.uk/api/v1.0/sites`. 

### pems

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/pems.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/pems.body --write-out '%{http_code} %{size_download} %{url_effective}' https://pems.dot.ca.gov/
```

Result: `200 22289 https://pems.dot.ca.gov/`. 

### intas-readme

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/intas-readme.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/intas-readme.body --write-out '%{http_code} %{size_download} %{url_effective}' https://raw.githubusercontent.com/silaslobo/InTAS/master/README.md
```

Result: `200 2304 https://raw.githubusercontent.com/silaslobo/InTAS/master/README.md`. 

### lust-readme

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/lust-readme.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/lust-readme.body --write-out '%{http_code} %{size_download} %{url_effective}' https://raw.githubusercontent.com/lcodeca/LuSTScenario/master/README.md
```

Result: `200 1776 https://raw.githubusercontent.com/lcodeca/LuSTScenario/master/README.md`. 

### cologne-doc

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/cologne-doc.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/cologne-doc.body --write-out '%{http_code} %{size_download} %{url_effective}' https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html
```

Result: `200 29618 https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html`. 

### pneuma

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/pneuma.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/pneuma.body --write-out '%{http_code} %{size_download} %{url_effective}' https://open-traffic.epfl.ch/
```

Result: `200 136063 https://open-traffic.epfl.ch/`. 

### pneuma-fetch-source

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/pneuma-fetch-source.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/pneuma-fetch-source.body --write-out '%{http_code} %{size_download} %{url_effective}' https://raw.githubusercontent.com/EPFL-ENAC/pNEUMA/main/data_processing/fetch_data.py
```

Result: `200 2648 https://raw.githubusercontent.com/EPFL-ENAC/pNEUMA/main/data_processing/fetch_data.py`. 

### i24-data

```bash
curl --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/i24-data.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215816927389Z/i24-data.body --write-out '%{http_code} %{size_download} %{url_effective}' https://i24motion.org/data
```

Result: `000 0 https://i24motion.org/data`. curl: (60) SSL certificate OpenSSL verify result: unable to get local issuer certificate (20) More details here: https://curl.se/docs/sslcerts.html  curl failed to verify the legitimacy of the server and therefore could not establish a secure connection to it. To learn more about this situation and how to fix it, please visit the webpage mentioned above. 

### stockholm-features

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/stockholm-features.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/stockholm-features.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:Trafikflode_Motorfordon&maxFeatures=3&outputFormat=application/json'
```

Result: `200 5056 https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=od_gis:Trafikflode_Motorfordon&maxFeatures=3&outputFormat=application/json`. 

### berlin-list

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/berlin-list.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/berlin-list.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://mdhopendata.blob.core.windows.net/verkehrsdetektion/?restype=container&comp=list&maxresults=40'
```

Result: `200 25148 https://mdhopendata.blob.core.windows.net/verkehrsdetektion/?restype=container&comp=list&maxresults=40`. 

### berlin-data

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/berlin-data.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/berlin-data.body --write-out '%{http_code} %{size_download} %{url_effective}' https://mdhopendata.blob.core.windows.net/verkehrsdetektion/2015/alte_qualitaetssicherung/Fahrstreifendetektoren/det_val_hr_2015_01.csv.gz
```

Result: `200 4634033 https://mdhopendata.blob.core.windows.net/verkehrsdetektion/2015/alte_qualitaetssicherung/Fahrstreifendetektoren/det_val_hr_2015_01.csv.gz`. 

### madrid-api

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/madrid-api.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/madrid-api.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://datos.madrid.es/api/3/action/package_show?id=208627-0-transporte-ptomedida-historico'
```

Result: `200 17494 https://datos.madrid.es/api/3/action/package_show?id=208627-0-transporte-ptomedida-historico`. 

### madrid-doc

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/madrid-doc.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/madrid-doc.body --write-out '%{http_code} %{size_download} %{url_effective}' https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-81-transporte-ptomedida-historico/download/208627-81-transporte-ptomedida-historico.pdf
```

Result: `200 991314 https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-81-transporte-ptomedida-historico/download/208627-81-transporte-ptomedida-historico.pdf`. 

### paris-valid

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/paris-valid.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/paris-valid.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?where=q%20is%20not%20null&limit=5'
```

Result: `200 495 https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents/records?where=q%20is%20not%20null&limit=5`. 

### zurich-range

```bash
curl --range 0-65535 --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/zurich-range.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/zurich-range.body --write-out '%{http_code} %{size_download} %{url_effective}' https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031/download/sid_dav_verkehrszaehlung_miv_OD2031_2012.csv
```

Result: `206 65536 https://83025b28472d6aa2bf5ae59f3724aa78.eu.r2.cloudflarestorage.com/dx-zurich-prod/resources/a0af24df-7b7f-4951-a08b-9391778c92d7/sid_dav_verkehrszaehlung_miv_od2031_2012.csv?response-content-disposition=attachment%3B%20filename%3Dsid_dav_verkehrszaehlung_miv_od2031_2012.csv&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=11772c53446ee7a3eccef5a7678c2da5%2F20261031%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20261031T215928Z&X-Amz-Expires=60&X-Amz-SignedHeaders=host&X-Amz-Signature=28a2edf1f05c2dd5ea67f5a61d2de472ce49e1672233d8943ed547a82a51d7e4`. 

### finland-stations

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/finland-stations.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/finland-stations.body --write-out '%{http_code} %{size_download} %{url_effective}' https://tie.digitraffic.fi/api/tms/v1/stations
```

Result: `200 22886 https://tie.digitraffic.fi/api/tms/v1/stations`. 

### finland-data

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/finland-data.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/finland-data.body --write-out '%{http_code} %{size_download} %{url_effective}' https://tie.digitraffic.fi/api/tms/v1/stations/1/data
```

Result: `404 208 https://tie.digitraffic.fi/api/tms/v1/stations/1/data`. 

### finland-raw

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/finland-raw.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/finland-raw.body --write-out '%{http_code} %{size_download} %{url_effective}' https://tie.digitraffic.fi/api/tms/v1/history/raw/lamraw_101_24_1.csv
```

Result: `200 1673804 https://tie.digitraffic.fi/api/tms/v1/history/raw/lamraw_101_24_1.csv`. 

### norway-explorer

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/norway-explorer.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/norway-explorer.body --write-out '%{http_code} %{size_download} %{url_effective}' https://www.trafikkdata.no/graphql
```

Result: `200 1174 https://trafikkdata.atlas.vegvesen.no/graphql`. 

### webtris-report

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/webtris-report.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/webtris-report.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://webtris.highwaysengland.co.uk/api/v1.0/reports/Daily?sites=1&start_date=01062024&end_date=01062024&page=1&page_size=10'
```

Result: `204 0 https://webtris.highwaysengland.co.uk/api/v1.0/reports/Daily?sites=1&start_date=01062024&end_date=01062024&page=1&page_size=10`. 

### pneuma-zenodo

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/pneuma-zenodo.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/pneuma-zenodo.body --write-out '%{http_code} %{size_download} %{url_effective}' https://zenodo.org/api/records/7426506
```

Result: `200 2595 https://zenodo.org/api/records/7426506`. 

### i24-www

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/i24-www.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T215922059847Z/i24-www.body --write-out '%{http_code} %{size_download} %{url_effective}' https://www.i24motion.org/data
```

Result: `000 0 https://www.i24motion.org/data`. curl: (6) Could not resolve host: www.i24motion.org 

### ndw-config

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/ndw-config.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/ndw-config.body --write-out '%{http_code} %{size_download} %{url_effective}' https://opendata.ndw.nu/reistijden_configuratie_meetlocaties.xml.gz
```

Result: `200 2935159 https://opendata.ndw.nu/reistijden_configuratie_meetlocaties.xml.gz`. 

### ndw-speed-config

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/ndw-speed-config.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/ndw-speed-config.body --write-out '%{http_code} %{size_download} %{url_effective}' https://opendata.ndw.nu/snelheden_en_intensiteiten_configuratie_meetlocaties.xml.gz
```

Result: `200 1843832 https://opendata.ndw.nu/snelheden_en_intensiteiten_configuratie_meetlocaties.xml.gz`. 

### madrid-large

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 90 --max-filesize 180000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/madrid-large.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/madrid-large.body --write-out '%{http_code} %{size_download} %{url_effective}' https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-0-transporte-ptomedida-historico-zip/download/208627-0-transporte-ptomedida-historico-zip.zip
```

Result: `200 79348668 https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-0-transporte-ptomedida-historico-zip/download/208627-0-transporte-ptomedida-historico-zip.zip`. 

### finland-station-data

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/finland-station-data.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/finland-station-data.body --write-out '%{http_code} %{size_download} %{url_effective}' https://tie.digitraffic.fi/api/tms/v1/stations/101/data
```

Result: `404 212 https://tie.digitraffic.fi/api/tms/v1/stations/101/data`. 

### pneuma-original-meta

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/pneuma-original-meta.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/pneuma-original-meta.body --write-out '%{http_code} %{size_download} %{url_effective}' https://zenodo.org/api/records/10491409
```

Result: `200 2217 https://zenodo.org/api/records/10491409`. 

### norway-points

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/norway-points.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/norway-points.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://trafikkdata-api.atlas.vegvesen.no/?query=%7BtrafficRegistrationPoints%7Bid%20name%7D%7D'
```

Result: `410 119 https://trafikkdata-api.atlas.vegvesen.no/?query=%7BtrafficRegistrationPoints%7Bid%20name%7D%7D`. 

### melbourne-api

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/melbourne-api.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220007319062Z/melbourne-api.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://opendata.transport.vic.gov.au/api/3/action/package_show?id=traffic-signal-volume-data'
```

Result: `200 93962 https://opendata.transport.vic.gov.au/api/3/action/package_show?id=traffic-signal-volume-data`. 

### melbourne-large

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 90 --max-filesize 180000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/melbourne-large.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/melbourne-large.body --write-out '%{http_code} %{size_download} %{url_effective}' https://opendata.transport.vic.gov.au/dataset/331b846b-1e18-415f-a3f3-ce4198d86c82/resource/001ace40-280b-462d-b580-7a79e70185fb/download/traffic_signal_volume_data_october_2026.zip
```

Result: `200 127428210 https://opendata.transport.vic.gov.au/dataset/331b846b-1e18-415f-a3f3-ce4198d86c82/resource/001ace40-280b-462d-b580-7a79e70185fb/download/traffic_signal_volume_data_october_2026.zip`. 

### pneuma-readme

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/pneuma-readme.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/pneuma-readme.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://zenodo.org/records/10491409/files/README.html?download=1'
```

Result: `200 1984 https://zenodo.org/records/10491409/files/README.html?download=1`. 

### berlin-readme-list

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/berlin-readme-list.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/berlin-readme-list.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://mdhopendata.blob.core.windows.net/verkehrsdetektion/?restype=container&comp=list&prefix=read&maxresults=20'
```

Result: `200 230 https://mdhopendata.blob.core.windows.net/verkehrsdetektion/?restype=container&comp=list&prefix=read&maxresults=20`. 

### norway-new-points

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/norway-new-points.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220107059368Z/norway-new-points.body --write-out '%{http_code} %{size_download} %{url_effective}' 'https://www.trafikkdata.no/api/?query=%7BtrafficRegistrationPoints%7Bid%20name%7D%7D'
```

Result: `200 1174 https://trafikkdata.atlas.vegvesen.no/api/?query=%7BtrafficRegistrationPoints%7Bid%20name%7D%7D`. 

### paris-metadata

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220800936381Z/paris-metadata.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220800936381Z/paris-metadata.body --write-out '%{http_code} %{size_download} %{url_effective}' https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents
```

Result: `200 4488 https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/comptages-routiers-permanents`. 

### norway-api-doc

```bash
curl --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220800936381Z/norway-api-doc.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220800936381Z/norway-api-doc.body --write-out '%{http_code} %{size_download} %{url_effective}' https://www.trafikkdata.no/graphql
```

Result: `200 1174 https://trafikkdata.atlas.vegvesen.no/graphql`. 

### norway-post

```bash
curl --header 'Content-Type: application/json' --data '{"query":"{trafficRegistrationPoints{id name}}"}' --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220840868992Z/norway-post.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220840868992Z/norway-post.body --write-out '%{http_code} %{size_download} %{url_effective}' https://trafikkdata-api.atlas.vegvesen.no/
```

Result: `200 177634 https://trafikkdata-api.atlas.vegvesen.no/`. 

### norway-volume

```bash
curl --header 'Content-Type: application/json' --data '{"query": "{trafficData(trafficRegistrationPointId:\"52742V2282262\"){volume{byHour(from:\"2024-01-01T00:00:00+01:00\",to:\"2024-01-02T00:00:00+01:00\"){edges{node{from to total{volumeNumbers{volume}}}}}}}}"}' --compressed --silent --show-error --location --connect-timeout 10 --max-time 35 --max-filesize 12000000 --dump-header /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220908835813Z/norway-volume.headers --output /home/erikf/projects/personal/cars-data/truth/city-ground-truth/20261031T220908835813Z/norway-volume.body --write-out '%{http_code} %{size_download} %{url_effective}' https://trafikkdata-api.atlas.vegvesen.no/
```

Result: `200 375 https://trafikkdata-api.atlas.vegvesen.no/`. 
