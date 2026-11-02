"""Audit NDW config + live feeds near Amsterdam (untrusted gz XML, streamed). Usage: city_review_ndw.py run_dir out.json"""
import collections as C, gzip, json, math, pathlib, re, resource, sys
import xml.etree.ElementTree as E
resource.setrlimit(resource.RLIMIT_AS, (2800*1024**2, 2800*1024**2))
d = pathlib.Path(sys.argv[1]); out = {}
B = (52.30, 52.45, 4.70, 5.00)
loc = lambda t: t.rsplit('}', 1)[-1]
def sites(fn):
    with gzip.open(d/fn, 'rb') as f:
        for ev, e in E.iterparse(f):
            if loc(e.tag) == 'measurementSite':
                yield e; e.clear()
def tx(e, name):
    return [x.text for x in e.iter() if loc(x.tag) == name and x.text]
def inb(a, o): return B[0] < a < B[1] and B[2] < o < B[3]
# Travel-time routes
tt = []; eq = C.Counter(); eq_nat = C.Counter()
for s in sites('ndw-tt-config.body'):
    equip = ';'.join(tx(s, 'value')[:1]) or '?'
    # first <value> under measurementEquipmentTypeUsed
    for c in s:
        if loc(c.tag) == 'measurementEquipmentTypeUsed': equip = ''.join(c.itertext()).strip()
    name = ''
    for c in s:
        if loc(c.tag) == 'measurementSiteName': name = ''.join(c.itertext()).strip()
    pos = [float(v) for p in tx(s, 'posList') for v in p.split()]
    pts = list(zip(pos[0::2], pos[1::2]))
    eq_nat[equip] += 1
    if pts and all(inb(*p) for p in pts):
        L = sum(math.hypot((a[0]-b[0])*111200, (a[1]-b[1])*67700) for a, b in zip(pts, pts[1:]))
        tt.append((s.attrib.get('id'), equip, name, L))
        eq[equip] += 1
out['tt_national_by_equipment'] = eq_nat.most_common()
out['tt_amsterdam_all_vertices_in_bbox'] = len(tt); out['tt_amsterdam_by_equipment'] = eq.most_common()
a10 = [t for t in tt if re.search(r'\bA10\b', t[2])]
out['tt_a10_named'] = len(a10); out['tt_a10_by_equipment'] = C.Counter(t[1] for t in a10).most_common()
out['tt_a10_prefixes'] = C.Counter(t[0].split('_')[0] for t in a10).most_common(10)
out['tt_a10_chord_km_sum_fcd'] = round(sum(t[3] for t in a10 if t[1] == 'fcd')/1000, 1)
out['tt_a10_examples'] = [t[:3] for t in a10[:12]]
out['tt_ams_prefixes'] = C.Counter(t[0].split('_')[0] for t in tt).most_common(15)
# Point sites
pt = []; eqp = C.Counter()
for s in sites('ndw-point-config.body'):
    la = [float(x) for x in tx(s, 'latitude')]; lo = [float(x) for x in tx(s, 'longitude')]
    if not la: continue
    equip = name = ''; lanes = None
    for c in s:
        t = loc(c.tag)
        if t == 'measurementEquipmentTypeUsed': equip = ''.join(c.itertext()).strip()
        if t == 'measurementSiteName': name = ''.join(c.itertext()).strip()
        if t == 'measurementSiteNumberOfLanes': lanes = c.text
    kinds = C.Counter(tx(s, 'specificMeasurementValueType'))
    pid = s.attrib.get('id')
    a, o = la[0], lo[0]
    if inb(a, o): pt.append((pid, equip, name, lanes, a, o, kinds.get('trafficFlow', 0), kinds.get('trafficSpeed', 0)))
out['point_ams'] = len(pt); out['point_ams_equipment'] = C.Counter(p[1] for p in pt).most_common(8)
out['point_ams_prefix'] = C.Counter(p[0].split('_')[0] for p in pt).most_common(15)
out['point_ams_with_flow'] = sum(p[6] > 0 for p in pt); out['point_ams_with_speed'] = sum(p[7] > 0 for p in pt)
mon = [p for p in pt if 'MONIBAS' in p[0] or p[0].startswith('RWS')]
out['point_ams_rws'] = len(mon); out['point_ams_rws_lanes'] = C.Counter(p[3] for p in mon).most_common(8)
mo = [p for p in pt if 'a0100' in p[0].lower() or '_0100' in p[0]]
out['point_a10_monibas_id'] = len(mo); out['point_a10_examples'] = [p[0:4] for p in mo[:8]]
out['point_examples'] = [p[0:4] for p in pt[:6]]
pathlib.Path('/tmp/ndw_points.json').write_text(json.dumps(pt))
# Live speed snapshot: share of amsterdam sites that report
ids = {p[0] for p in pt}; flow = {}; speed = {}; ts = C.Counter(); total = 0
with gzip.open(d/'ndw-speed-live.body', 'rb') as f:
    for ev, e in E.iterparse(f):
        if loc(e.tag) in ('siteMeasurements', 'measuredValues', 'physicalQuantity') and loc(e.tag) == 'siteMeasurements':
            sid = None
            for c in e.iter():
                t = loc(c.tag)
                if t == 'measurementSiteReference': sid = c.attrib.get('id')
                if t == 'measurementTimeDefault': ts[c.text] += 1
            total += 1
            if sid in ids:
                fl = [x.text for x in e.iter() if loc(x.tag) == 'vehicleFlowRate']
                sp = [x.text for x in e.iter() if loc(x.tag) == 'speed']
                flow[sid] = fl; speed[sid] = sp
            e.clear()
out['live_sites_total'] = total; out['live_time'] = ts.most_common(2)
out['live_ams_reporting'] = len(flow); out['live_ams_flow_positive'] = sum(any(float(x) > 0 for x in v) for v in flow.values())
# Live TT: type/share
kinds = C.Counter(); nv = []; ttime = {}
ttid = {t[0] for t in tt}
with gzip.open(d/'ndw-tt-live.body', 'rb') as f:
    for ev, e in E.iterparse(f):
        if loc(e.tag) == 'siteMeasurements':
            sid = None; v = None; ty = None
            for c in e.iter():
                t = loc(c.tag)
                if t == 'measurementSiteReference': sid = c.attrib.get('id')
                if t == 'duration': v = c.text
                if t == 'travelTimeType': ty = c.text
                if c.attrib.get('numberOfInputValuesUsed'): nv.append(int(float(c.attrib['numberOfInputValuesUsed'])))
            kinds[ty] += 1
            if sid in ttid: ttime[sid] = v
            e.clear()
out['tt_live_type'] = kinds.most_common(); out['tt_live_ams'] = len(ttime); out['tt_live_ams_valid'] = sum(1 for v in ttime.values() if v and float(v) > 0)
out['tt_live_numberOfInputValues'] = C.Counter(nv).most_common(6)
print(json.dumps(out, ensure_ascii=False, indent=1)); pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
