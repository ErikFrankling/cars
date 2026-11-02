#!/usr/bin/env python3
"""Dump titles of papers citing a DOI via OpenAlex, one page, newest first, optional title regex."""
import json, re, sys, time, urllib.parse, urllib.request
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": "cars-data-hunt"})
    return json.load(urllib.request.urlopen(r, timeout=40))
doi, rx = sys.argv[1], re.compile(sys.argv[2] if len(sys.argv) > 2 else ".", re.I)
w = get("https://api.openalex.org/works/doi:" + doi)
print("#", w["display_name"], w["cited_by_count"])
for page in range(1, 4):
    q = urllib.parse.urlencode({"filter": "cites:" + w["id"].split("/")[-1], "per-page": 200, "page": page, "sort": "publication_year:desc",
                                "select": "display_name,doi,publication_year"})
    try:
        d = get("https://api.openalex.org/works?" + q)
    except Exception as e:
        print("stopped:", e); break
    if not d["results"]: break
    for s in d["results"]:
        if rx.search(s["display_name"] or ""):
            print(s["publication_year"], "|", s["display_name"], "|", s["doi"])
    time.sleep(1)
