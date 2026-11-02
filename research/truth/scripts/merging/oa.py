"""OpenAlex lookup for open copies. Prints title, oa status and pdf url per DOI. Network only; writes nothing but stdout."""
import json, sys, urllib.request, urllib.parse
for line in open(sys.argv[1]):
    line = line.strip()
    if not line: continue
    n, doi = line.split(None, 1)
    u = 'https://api.openalex.org/works/doi:' + urllib.parse.quote(doi)
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'research'}), timeout=30))
        locs = [l for l in d.get('locations', []) if l.get('pdf_url') or l.get('is_oa')]
        urls = [(l.get('pdf_url') or l.get('landing_page_url')) for l in locs]
        print(n, '|', (d.get('title') or '')[:70], '|', d.get('publication_year'), '| cited', d.get('cited_by_count'), '| oa', d.get('open_access', {}).get('oa_status'), '|', urls[:3], flush=True)
    except Exception as e:
        print(n, 'ERR', str(e)[:80], flush=True)
