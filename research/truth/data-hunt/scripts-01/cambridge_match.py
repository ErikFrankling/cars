#!/usr/bin/env python3
"""Find match-rate and manual-count summaries in each Cambridge OD site sheet. Arg: xlsx path."""
import re, sys, zipfile, xml.etree.ElementTree as E
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
z = zipfile.ZipFile(sys.argv[1])
ss = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in E.fromstring(z.read("xl/sharedStrings.xml")).findall(NS + "si")]
wb = E.fromstring(z.read("xl/workbook.xml")); rel = E.fromstring(z.read("xl/_rels/workbook.xml.rels")); tgt = {r.get("Id"): r.get("Target") for r in rel}
rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
rx = re.compile(r"match|MCC|manual|capture|flow|total", re.I)
for name, t in [(s.get("name"), tgt[s.get(rid)]) for s in wb.find(NS + "sheets")]:
    if not re.fullmatch(r"\d+[A-Z]?", name): continue
    seen = 0
    with z.open("xl/" + t.lstrip("/").replace("xl/", "")) as f:
        for ev, el in E.iterparse(f):
            if el.tag == NS + "row":
                vals = []
                for c in el:
                    v = c.find(NS + "v")
                    if v is not None: vals.append(ss[int(v.text)] if c.get("t") == "s" else v.text)
                el.clear()
                if vals and rx.search(str(vals[0])) and seen < 8:
                    print(name, "|", " | ".join(str(x)[:22] for x in vals[:14])); seen += 1
