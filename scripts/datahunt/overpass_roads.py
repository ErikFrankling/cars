"""Fetches drivable OSM ways, signals and turn restrictions for a bbox from Overpass as JSON."""
import sys, urllib.request, urllib.parse, time
out, S, W, N, E = sys.argv[1:6]
q = f"""[out:json][timeout:300][bbox:{S},{W},{N},{E}];
(way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|road|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"];)->.w;
(.w;>;)->.a;
relation["type"="restriction"](bw.w)->.r;
.a out body; .w out body; .r out body;"""
for u in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
    try:
        d = urllib.request.urlopen(urllib.request.Request(u, urllib.parse.urlencode({"data": q}).encode(), {"User-Agent": "cars-research/0.1"}), timeout=320).read()
        if len(d) > 10000:
            open(out, "wb").write(d); print(u, len(d)); break
        print(u, "short", d[:300])
    except Exception as e:
        print(u, e); time.sleep(10)
