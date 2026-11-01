"""Fetch public schema trees for chosen Trafikverket object types; prints compact property tables.
Usage: city_review_tvtree.py schema.json outdir Name..."""
import json, pathlib, subprocess, sys, urllib.parse
L = {x['objectTypeName']: x for x in json.load(open(sys.argv[1], encoding='utf-8'))}
out = pathlib.Path(sys.argv[2])
def walk(o, d=0):
    if isinstance(o, dict):
        n = o.get('name') or o.get('propertyName') or o.get('Name')
        desc = o.get('description') or o.get('annotation') or o.get('documentation')
        t = o.get('type') or o.get('dataType')
        if n: print(' '*d + str(n), '|', t if isinstance(t, str) else '', '|', (str(desc) if desc else '').replace('\n', ' ')[:220])
        for k, v in o.items():
            if isinstance(v, (dict, list)): walk(v, d+1)
    elif isinstance(o, list):
        for v in o: walk(v, d)
for n in sys.argv[3:]:
    x = L[n]; ns = x['namespace']; v = x['versions'][-1]
    u = 'https://data.trafikverket.se/apb/prod/schematree/' + urllib.parse.quote(f'{ns}.{n}') + f'/{v}/data?annotations=true'
    f = out/('tvtree-'+n.encode('ascii','replace').decode().replace('?','_')+'.body')
    r = subprocess.run(['curl','--silent','--max-time','40','--max-filesize','8000000','-o',str(f),'-w','%{http_code}',u],capture_output=True,text=True)
    print('=====', n, ns, v, r.stdout, u)
    try: walk(json.load(open(f, encoding='utf-8')))
    except Exception as e: print('parse fail', e, f.read_bytes()[:300])
