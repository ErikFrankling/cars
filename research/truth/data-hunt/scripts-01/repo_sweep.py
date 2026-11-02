#!/usr/bin/env python3
"""Search open data repositories without keys for plate-reader, vehicle-identification and all-vehicle trajectory releases."""
import json, re, time, urllib.parse as U, urllib.request as R
def get(u, data=None, hdr=None):
    q = R.Request(u, data=data, headers={"User-Agent": "cars-data-hunt", "Accept": "application/json", **(hdr or {})})
    return json.load(R.urlopen(q, timeout=40))
TERMS = ["license plate recognition trajectories", "automatic number plate recognition", "ANPR journey time", "automatic vehicle identification trajectories",
         "city-scale vehicle trajectories camera", "drone vehicle trajectories urban network", "roadside lidar vehicle trajectories", "bluetooth reidentification vehicle travel time",
         "electronic toll individual vehicle trips", "aerial vehicle trajectories helicopter"]
seen = set()
def show(src, title, url, extra=""):
    k = re.sub(r"\W+", "", (title or "").lower())[:60]
    if k in seen: return
    seen.add(k); print(f"[{src}] {title[:120]} | {url} | {extra}")
for term in TERMS:
    print("#", term)
    try:
        d = get("https://zenodo.org/api/records?" + U.urlencode({"q": term, "size": 12, "type": "dataset", "sort": "bestmatch"}))
        for h in d["hits"]["hits"]:
            m = h["metadata"]; show("zenodo", m["title"], h["links"]["self_html"], m.get("publication_date", "") + " " + str((m.get("license") or {}).get("id", "")))
    except Exception as e: print("zenodo err", e)
    try:
        d = get("https://api.figshare.com/v2/articles/search", json.dumps({"search_for": term, "item_type": 3, "page_size": 12}).encode(), {"Content-Type": "application/json"})
        for a in d: show("figshare", a["title"], a["url_public_html"], a.get("published_date", "")[:10])
    except Exception as e: print("figshare err", e)
    try:
        d = get("https://dataverse.harvard.edu/api/search?" + U.urlencode({"q": term, "type": "dataset", "per_page": 8}))
        for a in d["data"]["items"]: show("dataverse", a["name"], a["url"], a.get("published_at", "")[:10])
    except Exception as e: print("dataverse err", e)
    time.sleep(1)
print("# government portals")
for name, base in [("uk", "https://ckan.publishing.service.gov.uk/api/3/action/package_search"), ("us", "https://catalog.data.gov/api/3/action/package_search"),
                   ("ie", "https://data.gov.ie/api/3/action/package_search"), ("au", "https://data.gov.au/data/api/3/action/package_search"), ("ca", "https://open.canada.ca/data/api/3/action/package_search")]:
    for q in ["ANPR", "number plate journey", "bluetooth travel time individual", "license plate reader"]:
        try:
            d = get(base + "?" + U.urlencode({"q": q, "rows": 8}))
            for p in d["result"]["results"]:
                show("gov-" + name, p["title"], p.get("url") or p.get("name"), (p.get("organization") or {}).get("title", ""))
        except Exception as e: print(name, q, "err", str(e)[:80])
for q in ["ANPR", "number plate recognition", "kenteken herkenning", "Kennzeichenerfassung", "reconnaissance plaques", "trängselskatt", "restid kamera"]:
    try:
        d = get("https://data.europa.eu/api/hub/search/search?" + U.urlencode({"q": q, "filter": "dataset", "limit": 8}))
        for p in d["result"]["results"]:
            t = p.get("title") or {}; t = t.get("en") or next(iter(t.values()), "") if isinstance(t, dict) else t
            show("eu", t, "https://data.europa.eu/data/datasets/" + p["id"], str((p.get("catalog") or {}).get("id", "")))
    except Exception as e: print("eu", q, "err", str(e)[:80])
