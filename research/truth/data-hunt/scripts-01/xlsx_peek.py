#!/usr/bin/env python3
"""Print sheets and first rows of an xlsx with only the standard library. Args: path [rows-per-sheet] [max-sheets]."""
import re, sys, zipfile, xml.etree.ElementTree as E
ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
z = zipfile.ZipFile(sys.argv[1]); N = int(sys.argv[2]) if len(sys.argv) > 2 else 12; M = int(sys.argv[3]) if len(sys.argv) > 3 else 6
ss = []
if "xl/sharedStrings.xml" in z.namelist():
    for si in E.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
        ss.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
wb = E.fromstring(z.read("xl/workbook.xml"))
rel = E.fromstring(z.read("xl/_rels/workbook.xml.rels"))
tgt = {r.get("Id"): r.get("Target") for r in rel}
sheets = [(s.get("name"), tgt[s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]) for s in wb.find("m:sheets", ns)]
print("sheets:", len(sheets), [s[0] for s in sheets][:60])
import os
W=os.environ.get("SHEETS"); L=int(os.environ.get("CELL","40"))
for name, t in ([s for s in sheets if s[0] in W.split(",")] if W else sheets[:M]):
    p = "xl/" + t.lstrip("/").replace("xl/", "")
    info = z.getinfo(p); print(f"\n--- {name} ({info.file_size} bytes xml)")
    n = 0; rows = 0
    with z.open(p) as f:
        for ev, el in E.iterparse(f):
            if el.tag.endswith("}row"):
                rows += 1
                if n < N:
                    vals = []
                    for c in el:
                        v = c.find("m:v", ns)
                        if v is None: continue
                        vals.append(ss[int(v.text)] if c.get("t") == "s" else v.text)
                    if vals: print(" | ".join(str(x)[:L] for x in vals[:18])); n += 1
                el.clear()
    print("rows:", rows)
