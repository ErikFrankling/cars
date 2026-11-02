#!/usr/bin/env python3
"""Whole-day statistics of a Cambridge ANPR trip-chain workbook, standard library only. Arg: xlsx path."""
import collections as C, re, statistics as st, sys, zipfile, xml.etree.ElementTree as E
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
z = zipfile.ZipFile(sys.argv[1])
ss = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in E.fromstring(z.read("xl/sharedStrings.xml")).findall(NS + "si")]
wb = E.fromstring(z.read("xl/workbook.xml")); rel = E.fromstring(z.read("xl/_rels/workbook.xml.rels")); tgt = {r.get("Id"): r.get("Target") for r in rel}
rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
sheets = [(s.get("name"), tgt[s.get(rid)]) for s in wb.find(NS + "sheets")]
cl, hrs, ln, tot, hop, od, cams = C.Counter(), C.Counter(), C.Counter(), [], [], C.Counter(), set()
n = 0; per_origin = C.Counter()
for name, t in sheets:
    if not re.fullmatch(r"\d+[A-Z]?", name): continue
    with z.open("xl/" + t.lstrip("/").replace("xl/", "")) as f:
        for ev, el in E.iterparse(f):
            if el.tag == NS + "row":
                vals = []
                for c in el:
                    v = c.find(NS + "v")
                    vals.append((ss[int(v.text)] if c.get("t") == "s" else v.text) if v is not None else "")
                el.clear()
                if len(vals) >= 5 and re.match(r"\d\d/\d\d/\d{4} \d\d:", str(vals[0])) and ">" in str(vals[3]):
                    n += 1; cl[vals[1]] += 1; hrs[int(vals[0][11:13])] += 1; per_origin[name] += 1
                    ch = vals[3].split(">"); ln[min(len(ch), 12)] += 1; od[(ch[0], ch[-1])] += 1; cams |= set(ch)
                    try: tot.append(float(vals[2]))
                    except: pass
                    hop += [float(x) for x in re.findall(r"\(([\d.]+)\)", vals[4])]
print("chains", n, "origin sheets", len(per_origin), "camera+direction labels", len(cams), "distinct OD pairs", len(od))
print("class", cl.most_common()); print("by hour", [hrs[h] for h in range(24)])
print("cameras in chain", sorted(ln.items()))
tot.sort(); hop.sort()
print("trip min p10,50,90", tot[len(tot)//10], tot[len(tot)//2], tot[int(.9*len(tot))], "| hop min p10,50,90", hop[len(hop)//10], hop[len(hop)//2], hop[int(.9*len(hop))], "hops", len(hop))
print("top OD", od.most_common(6))
