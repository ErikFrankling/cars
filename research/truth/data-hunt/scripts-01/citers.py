#!/usr/bin/env python3
"""List papers citing given DOIs via OpenAlex; flag ones that look like data releases."""
import json, re, sys, urllib.parse, urllib.request
DOIS = {
 "Yu2023 camera trajectories": "10.1038/s41597-023-02589-y",
 "Wang2023 Xuancheng holographic": "10.1038/s41597-022-01850-0",
 "pNEUMA 2020": "10.1016/j.trc.2019.11.023",
 "I-24 MOTION": "10.1016/j.trc.2023.104311",
}
KW = re.compile(r"dataset|data set|open data|publicly available|trajector|license plate|licen[sc]e-plate|LPR|ANPR|AVI\b|camera|drone|UAV|lidar|whole|city-scale|citywide|city-wide", re.I)
STRONG = re.compile(r"\bdataset\b|data set|publicly available|open[- ]source data|we (release|publish|provide)", re.I)
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": "cars-data-hunt"})
    return json.load(urllib.request.urlopen(r, timeout=40))
def abstract(w):
    ii = w.get("abstract_inverted_index") or {}
    pos = {}
    for k, v in ii.items():
        for p in v: pos[p] = k
    return " ".join(pos[i] for i in sorted(pos))
for name, doi in DOIS.items():
    w = get("https://api.openalex.org/works/doi:" + doi)
    print(f"\n=== {name}: {w.get('display_name')} cited_by={w.get('cited_by_count')}")
    cur, seen = "*", []
    while cur and len(seen) < 600:
        q = urllib.parse.urlencode({"filter": "cites:" + w["id"].split("/")[-1], "per-page": 200, "cursor": cur,
                                    "select": "display_name,doi,publication_year,abstract_inverted_index,primary_location"})
        d = get("https://api.openalex.org/works?" + q)
        seen += d["results"]; cur = d["meta"].get("next_cursor")
        if not d["results"]: break
    n = 0
    for s in sorted(seen, key=lambda s: -(s.get("publication_year") or 0)):
        t, a = s.get("display_name") or "", abstract(s)
        if STRONG.search(t) or (STRONG.search(a) and KW.search(t + a) and re.search(r"(we|this paper|this study).{0,60}(present|release|introduc|publish|provide|collect|construct).{0,60}(dataset|data set|data)", a, re.I)):
            n += 1
            print(f"[{s.get('publication_year')}] {t} | {s.get('doi')}")
    print(f"-- {len(seen)} citing, {n} flagged")
