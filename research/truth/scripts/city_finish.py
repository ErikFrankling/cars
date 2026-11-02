import csv,gzip,io,json,pathlib,shlex,zipfile
base=pathlib.Path('/home/erikf/projects/personal/cars-data/truth/city-ground-truth')
rows=[]
for p in sorted(base.glob('*/manifest.json')):
 rows.extend(json.loads(p.read_text()))
lines=['# Tested curl retrieval ledger','', '2026-10-31. Full commands as executed; replay into a new empty directory by changing output/header paths. A 200 HTML page is not an observation sample. Byte counts below are stored payload bytes; compressed HTTP transfer sizes can differ.','', '| Request | curl exit / HTTP | Stored bytes | SHA-256 |','|---|---|---:|---|']
for r in rows:
 lines.append(f'| [{r["name"]}]({r["url"]}) | {r["curl_exit"]} / {r["result"].split()[0]} | {r["bytes"]} | `{r["sha256"]}` |')
lines+=['',f'Total stored response bodies: {sum(r["bytes"] for r in rows):,} bytes.','', '## Exact commands','']
for r in rows:
 lines += ['### '+r['name'],'','```bash',shlex.join(r['command']),'```','',f'Result: `{r["result"]}`. '+r['error'].replace('\n',' '),'']
pathlib.Path('research/truth/01-city-download-log.md').write_text('\n'.join(lines))
p=next(base.glob('*/melbourne-large.body'))
with zipfile.ZipFile(p) as z:
 with z.open(z.namelist()[0]) as f:
  r=csv.DictReader(io.TextIOWrapper(f)); sites=set(); n=0
  for row in r:
   sites.add(row['NB_SCATS_SITE']); n+=1
 extra={'melbourne_csv_members':len(z.namelist()),'sampled_day_file':z.namelist()[0],'sampled_day_rows':n,'sampled_day_sites_victoria':len(sites)}
extra['ndw_a10_tt']={'id':'ABM01_A10_HRL_CP_S102','seconds':184.1438,'timestamp':'2026-10-31T21:57:00Z','equipment':'fcd','type':'reconstituted'}
extra['total_stored_response_bytes']=sum(r['bytes'] for r in rows)
pathlib.Path('research/truth/01-city-extra-audit.json').write_text(json.dumps(extra,indent=2))
data=[('Amsterdam corridor',17),('Madrid',15),('Melbourne / Victoria',15),('Helsinki / Finland',14),('Berlin',12),('Zurich',12),('Paris',12),('Stockholm',8)]
html='<!doctype html><html><head><meta charset="utf-8"><style>body{font-family:var(--font-sans);color:var(--foreground)}p{color:var(--muted-foreground)}.row{display:grid;grid-template-columns:150px 1fr 36px;gap:8px;align-items:center;margin:10px 0;font-size:13px}.track{background:var(--secondary);height:16px;border-radius:3px}.bar{height:16px;background:var(--chart-1);border-radius:3px}</style></head><body><p>Evidence audit score /20 · judgement, not measured simulation accuracy</p>'
for name,n in data:
 html+=f'<div class="row"><span>{name}</span><div class="track"><div class="bar" style="width:{n*5}%"></div></div><span>{n}</span></div>'
html+='<p>Scores reward verified access, history, time detail, network scope and separate congestion evidence. Amsterdam still needs matched historical coverage; Stockholm needs dated observations.</p></body></html>'
pathlib.Path('research/truth/fig/01-city-evidence.html').write_text(html)
print(json.dumps(extra,indent=2))
