#!/usr/bin/env python3
"""Fetch URLs listed in argv[2:] as name=url into argv[1]/raw, keep a ledger. Files are data only."""
import json, os, sys, time, urllib.request, hashlib, ssl
root = sys.argv[1]
raw = os.path.join(root, "raw"); os.makedirs(raw, exist_ok=True)
led = os.path.join(root, "ledger.jsonl")
ctx = ssl.create_default_context()
for a in sys.argv[2:]:
    name, url = a.split("=", 1)
    rec = {"name": name, "url": url, "t": time.strftime("%FT%TZ", time.gmtime())}
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/140.0", "Accept": "*/*"})
        d = urllib.request.urlopen(r, timeout=45, context=ctx).read()
        ext = ".pdf" if d[:4] == b"%PDF" else ".html"
        p = os.path.join(raw, name + ext)
        open(p, "wb").write(d)
        rec |= {"ok": True, "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()[:16], "file": p}
    except Exception as e:
        rec |= {"ok": False, "err": str(e)[:160]}
    open(led, "a").write(json.dumps(rec) + "\n")
    print(name, rec.get("bytes"), rec.get("err", ""))
