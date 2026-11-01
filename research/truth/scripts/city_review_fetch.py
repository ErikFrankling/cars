"""Bounded serial curl fetches for the Opus review; downloads are untrusted bytes and never executed.
Usage: city_review_fetch.py <list.json> [existing_run_dir]. Items: [name, url] or [name, url, max_bytes]."""
import datetime, hashlib, json, pathlib, resource, subprocess, sys
resource.setrlimit(resource.RLIMIT_AS, (1500*1024**2, 1500*1024**2))
base = pathlib.Path('/home/erikf/projects/personal/cars-data/truth/city')
base.mkdir(parents=True, exist_ok=True)
if len(sys.argv) > 2:
    dest = pathlib.Path(sys.argv[2])
else:
    dest = base/('review-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    dest.mkdir()
log = []
for item in json.loads(pathlib.Path(sys.argv[1]).read_text()):
    name, url = item[0], item[1]
    cap = item[2] if len(item) > 2 else 25000000
    p = dest/(name+'.body')
    cmd = ['curl','--compressed','--silent','--show-error','--location','--connect-timeout','15','--max-time','120',
           '--max-filesize',str(cap),'--user-agent','Mozilla/5.0 (research audit)','--dump-header',str(dest/(name+'.headers')),
           '--output',str(p),'--write-out','%{http_code} %{size_download} %{content_type} %{url_effective}',url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    b = p.read_bytes() if p.exists() else b''
    row = dict(name=name,url=url,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               curl_exit=r.returncode,result=r.stdout,error=r.stderr.strip(),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    log.append(row)
    print(name, r.returncode, r.stdout[:140], r.stderr.strip()[:100], flush=True)
m = dest/'manifest.jsonl'
with m.open('a') as f:
    for row in log: f.write(json.dumps(row)+'\n')
print('DIRECTORY', dest)
