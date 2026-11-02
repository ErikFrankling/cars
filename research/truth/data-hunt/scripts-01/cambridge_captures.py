#!/usr/bin/env python3
"""Sum daily ANPR captures per site over Cambridge OD workbooks, stopping at each sheet's first total. Args: xlsx paths."""
import re, sys, zipfile, xml.etree.ElementTree as E
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
sites = {}
for p in sys.argv[1:]:
    z = zipfile.ZipFile(p)
    ss = []
    with z.open("xl/sharedStrings.xml") as f:
        for ev, el in E.iterparse(f):
            if el.tag == NS + "si":
                ss.append("".join(t.text or "" for t in el.iter(NS + "t"))); el.clear()
    wb = E.fromstring(z.read("xl/workbook.xml")); rel = E.fromstring(z.read("xl/_rels/workbook.xml.rels")); tgt = {r.get("Id"): r.get("Target") for r in rel}
    for s in wb.find(NS + "sheets"):
        name = s.get("name")
        if not re.fullmatch(r"\d+[A-Z]?", name): continue
        with z.open("xl/" + tgt[s.get(RID)].lstrip("/").replace("xl/", "")) as f:
            for ev, el in E.iterparse(f):
                if el.tag == NS + "row":
                    vals = []
                    for c in el:
                        v = c.find(NS + "v")
                        if v is not None: vals.append(ss[int(v.text)] if c.get("t") == "s" else v.text)
                    el.clear()
                    if vals and str(vals[0]) == "Total":
                        sites[name] = (int(float(vals[1])), int(float(vals[2])), int(float(vals[3])), int(float(vals[4]))); break
    print(p[-16:], "done", len(sites), flush=True)
print("sites", len(sites), "captures", sum(v[2] for v in sites.values()), "first matched column sum", sum(v[3] for v in sites.values()))
print("largest", sorted(sites.items(), key=lambda kv: -kv[1][2])[:5])
