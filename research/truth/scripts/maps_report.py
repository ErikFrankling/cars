from pathlib import Path
import json,csv,collections
O=Path('research/truth'); S=json.loads((O/'stockholm-map-audit.json').read_text());B=json.loads((O/'berlin-map-audit.json').read_text());D=json.loads((O/'maps-detail.json').read_text())
assert len(S['samples']) == 20 and len({s['junction'] for s in S['samples']}) == 20
for city,r in [('stockholm',S),('berlin',B)]:
 assert sum(r['junction_types'].values()) == r['external_junctions']
 assert len(list(csv.DictReader(open(O/f'{city}-map-link-capacity.csv')))) == r['edges']
sources={
'SNET':'file:///home/erikf/projects/personal/cars-data/stockholm/stockholm.net.xml',
'BNET':'file:///home/erikf/projects/personal/cars-data/best/berlin.net.xml',
'OSM':'file:///home/erikf/projects/personal/cars-data/stockholm/clip.osm.xml',
'READER':'file:///home/erikf/.t3/projects/cars/crates/cars-core/src/net.rs',
'WORLD':'file:///home/erikf/.t3/projects/cars/crates/cars-core/src/world.rs',
'IMPORT':'https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html',
'TLS':'https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html',
'PLAIN':'https://sumo.dlr.de/docs/Networks/PlainXML.html',
'FRAME':'https://github.com/eclipse-sumo/sumo/blob/v1_28_0/src/netbuild/NBFrame.cpp',
'EDGE':'https://github.com/eclipse-sumo/sumo/blob/v1_28_0/src/netbuild/NBEdge.cpp',
'NODE':'https://github.com/eclipse-sumo/sumo/blob/v1_28_0/src/netbuild/NBNodeCont.cpp',
'REQUEST':'https://github.com/eclipse-sumo/sumo/blob/v1_28_0/src/netbuild/NBRequest.cpp',
'INTERSECTIONS':'https://sumo.dlr.de/docs/Simulation/Intersections.html',
'FHWA':'https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm',
'SCOUNT':'https://insynsverige.se/documentHandler.ashx?did=2052842',
'BCOUNT':'https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsmanagement/ampeln-und-co/generaluebernehmer/',
'SHANDBOOK':'https://tillstand.stockholm/globalassets/foretag-och-organisationer/tillstand-och-regler/tillstand-regler-och-tillsyn/mark--och-gatuarbeten/teknisk-handbok-for-byggande-drift-och-underhall-pa-offentlig-mark/teknisk-handbok-del-6/tekniskhandbok---del-6-trafiksignaler.pdf',
'LASTKAJEN':'https://www.trafikverket.se/lastkajen',
'NVDB':'https://nvdbpakarta.trafikverket.se/assets/docs/Handledning_nvdb_pa_karta.pdf',
'BLSA':'https://daten.berlin.de/datensaetze/lichtsignalanlagen-wfs-2cbfacc6',
'BROADS':'https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsplanung/strassen-und-kfz-verkehr/uebergeordnetes-strassennetz/',
'BGEO':'https://www.berlin.de/sen/stadt/stadtdaten/geodaten-berlin/geoportal-daten-und-dienste/',
'LM':'https://www.lantmateriet.se/sv/geotorget-produktstod/om-tillhandahallandet/',
'OVERTURE':'https://docs.overturemaps.org/guides/transportation/roads/',
'LANELET':'https://github.com/fzi-forschungszentrum-informatik/lanelet2',
'OPENDRIVE':'https://www.asam.net/standards/detail/opendrive/',
'MAPILLARY':'https://help.mapillary.com/hc/en-us/articles/4407521157138-Downloading-map-data-via-the-Mapillary-web-app',
'TOMTOM':'https://docs.tomtom.com/tomtom-orbis-maps/documentation/introduction',
'HERE':'https://docs.here.com/intro-to-mapping-concepts/docs/catalogs-layers-partitions-and-tiles',
'PTV':'https://cgi.ptvgroup.com/vision-help/VISSIM_2026_EN-DE/en-us/Content/5_Netzbearbeiten/Konfliktflaechen_Attr.htm',
'AIMSUN':'https://docs.aimsun.com/next/latest/UsersManual/NodeEditing.html',
'AERIAL':'https://arxiv.org/abs/2312.13449'}
text='''# Maps, intersections and capacity: Stockholm and Berlin

Research audit, 2026-10-31. **Measured** means read or calculated from the supplied files, or explicitly reported by an authority; it does not mean measured on the street. **Modelled** means an analytical estimate with stated assumptions. **Opinion** marks recommendations or causal hypotheses. Every source URL below was opened in this session; local primary files use `file:///` URLs because these exact private extracts have no verified public download URL. Generated CSVs are reproducibility evidence, not independent confirmation.

## Findings and limits

1. **Measured:** Stockholm's build omitted `--osm.turn-lanes`; SUMO disables it by default. There are 556 signalised approach segments whose source ways have turn-lane tags. These tags were not used to guide connections. This is a concrete information loss in conversion, rather than evidence that OSM lacks all turn information. [SNET] [IMPORT] [FRAME]
2. **Measured:** Stockholm has 1,922 controllers, all actuated, all nominally 90 s, all offset 0. Berlin has 2,344 controllers, all actuated; 2,246 (95.82%) nominally 90 s, all offset 0. **Opinion:** these are strong default-program fingerprints; real timing and coordination are unverified. [SNET] [BNET] [TLS]
3. **Measured:** only 205/3,690 Stockholm signalised approach segments have any turn-only passenger lane in their connection sets (5.56%); Berlin has 2,352/8,000 (29.40%). These are map-segment counts, not independent physical approaches. **Opinion:** the difference warrants lane-level review; it is not a measured missing-lane rate. [SNET] [BNET]
4. **Modelled:** extreme major-road screens include Danderydsvägen at 802 veh/h across two nominal lanes, and Berlin edge `-437054297` at 207 veh/h. **Measured:** short links and lanes without outgoing connections contribute to some rankings. **Unverified:** none has been proven to be a bottleneck that exists only in the model; that requires real saturation observations plus matched demand. [SNET] [BNET] [FHWA]
5. **Measured:** Stockholm's authority reports **just over 500** installations in its 2024 investment report, p.27; Berlin's official management page reports **more than 2,100** citywide. The nets contain 1,922 and 2,344 controllers, but the extracts, dates and counting units differ. A numerical coverage or false-signal percentage would be unjustified. [SCOUNT] [BCOUNT] [SNET] [BNET]

**What this session could not verify:** the real dedicated-turn-lane retention fraction; a street/imagery/official-plan audit of all 20 sites; actual phase plans, offsets and detector layouts; whether the flagged bottlenecks are false in reality; citywide present-day counts on exactly the extract boundary. The 20 cases below have quantitative net and source-OSM inspections, not 20 completed field validations. No satellite pixels or official junction-specific as-built plans were obtained. This report deliberately does not label unobserved street layouts as wrong.

## Reproduction and scope

Run from the repo root, sequentially:

```sh
nix develop --command python3 -I research/truth/scripts/maps_audit.py
nix develop --command python3 -I research/truth/scripts/maps_detail.py
nix develop --command python3 -I research/truth/scripts/maps_report.py
```

The scripts stream XML with element clearing, use one numerical-library thread, and run no simulator or GPU kernels. No new dataset downloads were made; the existing 618 MB `clip.osm.xml` was read as data, rather than executing or converting the PBF. No accounts, forms, messages, commits or git-state changes were made by this work. Input hashes below identify the audited snapshots. [OSM] [SNET] [BNET]

'''
for city,r,key in [('Stockholm',S,'SNET'),('Berlin',B,'BNET')]:text+=f"- {city}: `{r['sha256']}`. [{key}]\n"
text+='''
Counts refer to normal edges with at least one passenger-permitted lane; internal/crossing/walking edges are excluded from road-class summaries. External junction counts exclude IDs beginning `:` but include geometry nodes, dead ends, and junctions without passenger approaches. A controller may control several junction nodes, so TLS count and signal-node count are separate. Road-class speed distributions weight lanes equally, not kilometres or traffic. [SNET] [BNET] [PLAIN]

## Quantitative network audit

| Quantity (measured) | Stockholm | Berlin |
|---|---:|---:|
'''
for label,k in [('Passenger road edges','edges'),('External junction nodes','external_junctions'),('Internal/crossing/walking edges','internal_edges'),('Unique TLS controllers','tls'),('Signalised passenger approach segments','signal_approaches'),('Approaches with a turn-only passenger lane','approaches_with_turn_only_lanes'),('Passenger lanes without outgoing connections','disconnected_lanes'),('Invalid TLS link indices found','bad_link_indices'),('Nominal cycles outside screening range 30–180 s','cycles_outside_30_180')]:text+=f"| {label} | {S[k]:,} | {B[k]:,} |\n"
text+='\nAll cells: [SNET] [BNET]. Zero outgoing connections includes legitimate network exits; it is a review flag, not a defect count. The 30–180 s range is an **opinion** screening threshold, not an HCM rule.\n\n| Junction type (measured) | Stockholm count (%) | Berlin count (%) |\n|---|---:|---:|\n'
for t in sorted(set(S['junction_types'])|set(B['junction_types'])):
 a=S['junction_types'].get(t,0);b=B['junction_types'].get(t,0);text+=f"| {t} | {a:,} ({100*a/S['external_junctions']:.2f}%) | {b:,} ({100*b/B['external_junctions']:.2f}%) |\n"
text+='\nSource for the entire table and figure: [SNET] [BNET].\n\n![Junction type shares](fig/maps-junction-types.png)\n\n### Lanes and speeds by road class\n\nMeasured distributions: lane count is passenger lanes per directed edge; speeds are lane-weighted km/h, rounded below. Full histograms, including all lane counts and speed values, are in [Stockholm CSV](stockholm-map-road-classes.csv) and [Berlin CSV](berlin-map-road-classes.csv). [SNET] [BNET]\n\n| City / class | Edges | 1 lane / 2 lanes / 3+ lanes | Speed p05 / median / p95 km/h |\n|---|---:|---:|---:|\n'
for city,r in [('Stockholm',S),('Berlin',B)]:
 for row in r['road_classes']:
  ns=json.loads(row['lane_counts']);one=ns.get('1',0);two=ns.get('2',0);more=sum(v for k,v in ns.items() if int(k)>2)
  text+=f"| {city} / {row['road_class'].replace('highway.','')} | {row['edges']:,} | {one:,} / {two:,} / {more:,} | {row['speed_kmh_p05']:.0f} / {row['speed_kmh_median']:.0f} / {row['speed_kmh_p95']:.0f} |\n"
text+='''
**Opinion:** rare very high urban-class speeds and abrupt lane changes deserve review, but road class alone cannot establish the legal speed. Compare official directional speed records at the edge's validity date before changing anything. [NVDB]

### Signal programs and coordination

**Measured:** Stockholm's embedded netconvert 1.28 configuration has `geometry.remove=true`, `roundabouts.guess=true`, `tls.guess-signals=true`, `tls.default-type=actuated`, `ramps.guess=true`, and `junctions.join=true`; no external signal plan import or `osm.turn-lanes` is recorded. Berlin's header records netedit 1.21, dated 2025-03-26, editing an existing BeST net; its original conversion history cannot be reconstructed from this header. [SNET] [BNET]

**Measured:** all Stockholm programs are nominally 90 s; Berlin nominal cycles range 50–164 s. No nominal cycles fail the 30–180 s opinion screen. Zero offsets are universal in both files. This establishes absence of staggered offsets in these net programs, not absence of every possible runtime coordination scheme or additional override. [SNET] [BNET]

![Nominal cycle distributions](fig/maps-cycles.png)

**Measured:** the per-controller CSVs provide cycle, offset, minimum/maximum phase-duration sums, and minimum/maximum link green share. For Stockholm, 1,147 controllers have minimum nominal `G`+`g` share 82/90=91.11%, whereas 318 have 42/90=46.67%. These are different program patterns, not equal green splits across the city. [SNET]

**Modelled:** a nominal duration sum is not an actuated cycle prediction. Green extensions, skipped phases and detector calls change realised split and cycle. An actuated controller's sum of minimum/maximum durations is only a descriptive envelope for traversing its listed phases, not proof that those cycles occur. The reader imports `minDur`, `maxDur`, `type`, offsets and params; `world.rs` enables actuation only when configured and `type=actuated`. Merely counting TLS objects says nothing about realised controller performance. [TLS] [READER] [WORLD]

**Opinion:** classify Stockholm timing as generated/unvalidated, and Berlin timing as default-like/unvalidated with some edits. Neither net contains provenance establishing imported real controller timing. Do not call Berlin's 98 non-90-second programs real solely because their cycles differ. [SNET] [BNET] [FRAME]

## Turn-lane retention and the 20 Stockholm cases

**Measured:** source OSM turn tags occur on 556 signalised segments. Direction can be resolved conservatively for '''+str(D['direction_known'])+''' segments using directional tags, or `turn:lanes` on forward one-way ways. In '''+str(D['turn_flags'])+''' of those, the source tags declare more exclusive turn lanes than the connection graph has. The complete list is [turn flags](stockholm-map-turn-flags.csv); all approach comparisons are [here](stockholm-map-osm-comparison.csv). Source: [OSM] [SNET].

**Important limit:** this is a conversion-consistency flag count, not '''+str(D['turn_flags'])+''' confirmed physical lane errors. One OSM way may produce several net segments and tags can apply only near its terminal junction. Shared movements, slight-turn classification and inaccessible movements can change the counts. No inference of geographic completeness or current street truth is made. **Opinion:** start with terminal segments having equal source/net directional lane counts and verify marked movements visually. [IMPORT] [OSM] [SNET]

The table is the proposed **20-case acceptance suite**, with measured selected net coordinates and geometry. Region labels are search targets; the selected node and approach names identify the actual sample. Selection prefers motorway/trunk ramp nodes for ramp targets, multi-approach TLS for urban targets, and exact street-name matches for Sveaplan, Roslagstull, Fridhemsplan and S:t Eriksgatan/Fleminggatan. “Turn-only” means a passenger lane whose connections all turn left/right (including slight turns), not a physically observed arrow. All rows: [SNET] [OSM].

| # / target type | Selected location, latitude / longitude | Net node | Approaches / lanes / turn-only | What needs checking against reality |
|---|---|---|---:|---|
'''
checks={'ramp':'Merge/diverge lane continuity, auxiliary-lane length, correct grade separation; unverified in imagery','interchange':'Ramp weaving/storage and lane drops; unverified in imagery','roundabout':'Circulatory lanes and entry conflicts; node is one part of the complex, not a full roundabout','complex':'Joined-node footprint, lane assignments and separate signal groups; official plan unavailable','urban':'Dedicated turns, stop lines, signal grouping and pedestrian phases; official plan unavailable'}
for i,s in enumerate(S['samples']):
 text+=f"| {i+1}. {s['label']} ({s['kind']}) | {s['names']}<br>{s['lat']:.6f}, {s['lon']:.6f} | `{s['junction']}` | {s['approaches']} / {s['incoming_lanes']} / {s['turn_only_lanes']} | {checks[s['kind']]} |\n"
text+='''
The [sample CSV](stockholm-map-samples.csv) includes anchor displacement, all approach edge IDs and exact coordinates. A geographically nearby node is not automatically the named intersection; use the actual street names in the table. The sampling and imagery gaps mean this is **not a completed 20-site real-layout accuracy survey**. In particular ramp samples may be one portal or ramp-end node in a much larger interchange. [SNET]

![20 sampled net approach geometries](fig/maps-20-approaches.png)

![Sample coordinates](fig/maps-stockholm-samples.png)

**Measured wrong in the build configuration:** available OSM turn markings were not enabled as a connection-building input. **Unverified at these 20 specific sites:** which physical turns, lane pockets or signal heads are missing. Satellite access was not obtained; I do not substitute an OSM basemap for independent aerial evidence. Official Stockholm material opened here establishes detector/as-built requirements, not a junction-by-junction inventory. [IMPORT] [SNET] [SHANDBOOK]

## Analytical capacity and candidate bottlenecks

**Primary reference:** FHWA's archived Signal Timing Manual describes HCM-style signalised capacity as saturation flow multiplied by effective green/cycle, gives ideal saturation flow 1,900 passenger cars/h/lane, and notes typical prevailing saturation rates around 1,500–2,000. These are reference assumptions, not Swedish or German observed capacities. The current licensed HCM edition was not obtained; no claim of a full current-HCM calculation is made. [FHWA]

**Modelled screen, every passenger edge:**

`c_edge = 1900 * Σ_passenger_lanes max_connected_movements(nominal_Gg_seconds / nominal_cycle)`.

Unsignalised connected lanes use green share 1; lanes without any outgoing connection use 0. A second column uses protected `G` only. Those two columns are green-service references, **not calibrated upper/lower capacity bounds**: permissive `g` requires a suitable gap; a shared lane cannot independently serve every movement at its maximum green; startup/clearance losses, gradients, pedestrians, heavy vehicles, lane utilisation and downstream storage are not modelled. The formula uses displayed nominal green rather than measured effective green. Unsignalised values are ideal lane-service references, not HCM gap-acceptance capacities or freeway capacities. [FHWA] [TLS]

**Modelled junction totals:** incoming edge references are summed per junction. This is an accounting total, not a max-flow solution under conflicting demands or proof that all approaches can discharge simultaneously. Full outputs: [Stockholm links](stockholm-map-link-capacity.csv), [Stockholm junctions](stockholm-map-junction-capacity.csv), [Berlin links](berlin-map-link-capacity.csv), [Berlin junctions](berlin-map-junction-capacity.csv). Inputs: [SNET] [BNET].

The following are the lowest nonzero major-road capacity fractions, not empirically established worst congestion sites. Ranking is `c_edge / (1900 * passenger_lanes)`; source IDs make each case traceable. All rows **modelled**, geometry and connection counts **measured**. [SNET] [BNET] [FHWA]

| City / edge | Street | Lanes; length m | Nominal screen veh/h | Fraction ideal | Lanes without outgoing connection |
|---|---|---:|---:|---:|---:|
'''
for city,r in [('Stockholm',S),('Berlin',B)]:
 for c in r['low_capacity'][:8]:text+=f"| {city} `{c['edge']}` | {c['name'] or '(not stored)'} | {c['lanes']}; {c['length_m']:.2f} | {c['cap_Gg_vph']:.0f} | {100*c['fraction_ideal']:.1f}% | {c['unconnected_lanes']} |\n"
text+='''
**Opinion:** the strongest candidates for artificial capacity loss are internal storage cut into sub-vehicle-length external links, lane connections that strand an otherwise usable lane, and missing exclusive turns that let a turning queue block through traffic. A one-lane reduction at 50% green corresponds to **modelled 950 veh/h** of ideal reference service; an extra turn pocket can preserve through flow without adding a through lane. This does not mean every listed short lane must be lengthened: geometry nodes and turn pockets require contextual review. [FHWA] [PLAIN]

**No causal finding yet:** a network-only audit cannot determine the largest bottlenecks that exist *only* in the model. Run the same demand and controller plans in cars and SUMO, measure saturated discharge at the head of a queue, then compare against real observed discharge under unblocked downstream conditions. A common failure in both simulators suggests shared inputs; a cars-only failure suggests implementation. Neither implication by itself proves the cause. This is the proposed next experiment, not a result from this audit. [INTERSECTIONS] [TLS]

## What netconvert guesses and how false bottlenecks can arise

Local source inspected: `NBFrame.cpp` defaults; `NBNodeCont.cpp` signal propagation around lines 2218–2305 and join clustering around 793–907; `NBEdge.cpp` turn-sign matching around 2780–2845 and connection generation; `NBRequest.cpp` loaded prohibitions and computed lane responses. Online v1.28 source URLs were also opened. These are implementation facts, not traffic observations. [FRAME] [NODE] [EDGE] [REQUEST]

| Mechanism | Verified behaviour | Potential false bottleneck (**opinion**, not proven here) |
|---|---|---|
| TLS guess vs guess-signals | `tls.guess-signals` interprets surrounding OSM signal nodes as stop-line positions; default distance 25 m, slack 0. It is different from arbitrary `tls.guess`. | Stop-line nodes can remain separate controllers or fail propagation to a central node; compare grouped physical installations, not raw nodes. [FRAME] [NODE] |
| Junction joining | Distance default 10 m; candidate clustering has exclusions and slip-lane pruning. Stockholm enabled joining. | Combining nearby independent queues can destroy storage or put nonconflicting traffic under one conflict logic; missing joins can duplicate queue/stop decisions. Defaults are heuristics, not proof of an error. [FRAME] [NODE] [SNET] |
| Lane connection guessing | Default OSM conversion guesses connections; turn restrictions influence them, turn arrows require `--osm.turn-lanes`. Sign application can fail when directions or target lanes disagree. | Loss of lane-specific arrows allows wrong shared movements and blocked through lanes; conversely an incorrect arrow can remove a legal movement. [IMPORT] [EDGE] |
| Ramp guessing | Stockholm explicitly enabled ramp guessing. | Inferred acceleration-lane geometry may differ from real auxiliary lanes; verify lengths and joins against plans rather than disabling ramps globally. [SNET] [IMPORT] |
| Internal lanes and right of way | SUMO carries connection paths, request/foes/response logic; NBRequest computes responses from priorities and crossing relationships. | Bad geometry or incorrect priorities create excessive yielding, slow turns or keep-clear blockage. Removing internal lanes suppresses realism rather than validating the geometry. [PLAIN] [REQUEST] [INTERSECTIONS] |
| Signals | Default nominal cycle is 90 s, green option 31 s, extra left green 6 s; all-red default 0. Generated actual splits depend on junction and phase construction. | Repeated default plans and offsets can create unrealistic platoon stopping; blanket all-green or blanket extra all-red changes cannot validate real capacity. [FRAME] [TLS] |

## Better data: what is available versus what is still gated or unverified

| Source | Primary-source evidence opened | Use in this project / limitations |
|---|---|---|
| Sweden NVDB / Lastkajen | Lastkajen distributes NVDB data; registration with a valid email and acceptance of a licence are required for packages/orders. NVDB's no-login map manual shows lane-count and speed products. [LASTKAJEN] [NVDB] | **Opinion:** authoritative directional lane counts and speed limits are the first enrichment layer. Confirm each chosen product's schema/coverage for turn restrictions and signal inventories; complete turn pockets, per-lane arrows and controller plans were **not verified** as downloadable products. |
| Trafikverket and Stockholm signals | Stockholm's technical handbook covers detector placement, detector protocols and delivery as as-built documents. [SHANDBOOK] | **Opinion:** seek controller IDs, group-to-movement mapping, day plans, intergreens, offsets, detector geometry and bus priority. A public bulk export of these plans was **not verified**. No one was contacted. |
| Berlin LSA WFS | Official catalogue describes locations and designations of signal installations. GetCapabilities was attempted; web tooling rejected its XML content type, and the bare endpoint returned 503. [BLSA] | **Opinion:** use inventory matching to resolve node/controller duplication. Inventory positions are not phase plans. No data count was inferred from the failed endpoint. |
| Berlin road hierarchy / orthophotos | Official city pages publish the **Übergeordnetes Straßennetz** hierarchy and a Geoportal containing aerial imagery. [BROADS] [BGEO] | “Überlandstraßen” is not the name of the Berlin layer verified here. Use the hierarchy for corridor selection and dated orthophotos for markings; no per-lane hierarchy product or signal timing feed was verified. |
| Swedish orthophotos | Lantmäteriet lists orthophotos among high-value datasets and describes free API/bulk provision with product-specific terms. [LM] | **Opinion:** use dated official aerial images to measure stop lines, pockets and lane continuity. Availability and resolution of exact Stockholm tiles were not tested. |
| Lanelet2 | Framework for maps for automated driving. [LANELET] | **Opinion:** suitable for a curated lane-level junction representation; it is a format/framework, not a supplied complete Stockholm/Berlin HD dataset. Local coverage was not verified. |
| ASAM OpenDRIVE | Standard encodes road/lane geometry, markings, junctions and signals. [OPENDRIVE] | **Opinion:** useful interchange for detailed test fixtures; importing a richer format cannot recover missing measurements. Signal objects alone do not establish controller timing. |
| Mapillary | Provider documents CV-derived traffic-sign and point-feature downloads and requires sign-in for download. [MAPILLARY] | **Opinion:** dated street imagery can independently check arrows and access. Automated detections require review; complete lane connectivity and current coverage at the 20 sites were not verified. |
| Overture | Road schema represents access/turn restrictions and explicit speed limits; implied speed limits are not enumerated. [OVERTURE] | **Opinion:** useful additional topology/restriction comparison. Do not treat this as an independent HD lane/phase-plan source. Exact local lane attributes and completeness were not verified. |
| TomTom Orbis | Provider describes combining open and proprietary sources using an Overture-aligned model. [TOMTOM] | **Opinion:** evaluate a licensed local sample for lane/turn attributes, junction IDs, update dates and export rights. Local coverage, cost and exact export entitlement remain unverified. |
| HERE HD Live Map | Provider documents road/lane geometry and topology layers. [HERE] | **Opinion:** richer potential lane evidence; seek a sample and terms before relying on it. City coverage, licence, price and controller-plan availability unverified. A separate HERE product PDF returned 403. |
| Aerial ML extraction | Yao et al.'s primary paper describes lane-line/topology extraction and an approximately 80 km annotated aerial dataset. [AERIAL] | **Opinion:** use as a proposal generator for visible markings, then validate topology and grade separation manually; transfer accuracy in Stockholm/Berlin, tunnels, occlusions and timing inference remain unverified. No ML run was performed. |

## Richer junction models and a GPU-compatible design

**Measured from vendor documentation:** Vissim conflict areas expose gap and priority behaviour; Aimsun computes editable conflict zones where turning connections overlap and evaluates conflicts between vehicles. These offer local overlap regions rather than treating an entire long connector as occupied. SUMO already has an explicit intersection model; a replacement is not automatically more accurate. [PTV] [AIMSUN] [INTERSECTIONS]

**Opinion/design:** keep SUMO net.xml as the baseline import and add a compiled junction layer: lane paths, stop/yield lines, overlap intervals along each movement, conflict priorities, manoeuvre-specific critical and follow-up gaps, downstream storage and signal-group mappings. Compute polygon overlaps offline on CPU, then pack variable-length lists into global storage buffers. This fits the project prohibition on function-local WGSL arrays outside `lc_best`; no kernel changes were made here. [READER] [PLAIN] [INTERSECTIONS]

**Opinion/design:** each GPU step can compute predicted conflict-entry/exit times for nearby leading vehicles, accept a manoeuvre only when all relevant conflict intervals and downstream space permit, and use deterministic ordering for contested entries. Separate phases are needed for proposals, arbitration and accepted movement so atomics do not make priority depend on execution order. Lane-centreline geometry can provide curvature and a lateral-acceleration speed cap `v <= sqrt(a_lat / |curvature|)`; select and calibrate `a_lat`, smoothing and driver variation rather than inventing a universal turn speed. This is a proposed implementation, with no measured performance or fidelity claim. Related mechanisms: [PTV] [AIMSUN] [INTERSECTIONS].

**Opinion/design:** a bounded state machine per controller and a reduction over actual detector lanes is GPU-suitable. Use minimum green, extension/gap-out, maximum green, intergreen, pedestrian calls, bus-priority rules and corridor reference time from actual controller plans. Retain separate movement-level gap parameters for permissive lefts, roundabout entries and merges. The data/state machine must be validated before claiming real actuation; synthetic loops are a model. [TLS] [SHANDBOOK]

## Concrete build and calibration pipeline

The following is an **opinion/proposed pipeline**, not a deployed network or claim of recovered capacity.

1. **Freeze evidence:** snapshot the OSM PBF plus extract polygon, timestamp and netconvert version; store hashes and source provenance per imported attribute. Obtain dated city inventory/orthophoto layers; for Sweden add authorised Lastkajen exports when Erik has access. Keep raw files read-only. [IMPORT] [LASTKAJEN] [BLSA] [LM] [BGEO]
2. **Conflate directionally:** match official segments to OSM using geometry, carriageway direction, junction endpoints and road names; preserve parallel/grade-separated roads. Apply official speed/lanes as explicit overrides only with a confident direction match. Keep conflicts for manual review rather than nearest-line overwrite. Do not sum two-way lane counts onto each direction. [NVDB] [PLAIN]
3. **Build an A/B pair:** reproduce Stockholm's embedded conversion settings as baseline; change only `--osm.turn-lanes true` for the first experiment, retaining the same input and demand. Preserve warning logs; specifically inspect rejected turn-sign matches. Export source tags with `--osm.all-attributes` in future builds. Later test joins/ramps separately with explicit junction overrides. [SNET] [IMPORT] [EDGE]
4. **Patch junction fixtures:** curate the 20 cases using dated aerial/street views and as-built plans. Store lane arrows, pocket lengths, connection IDs, stop lines, conflicts, signal IDs, timing provenance and a date. Keep official and inferred values distinct. [PLAIN] [SHANDBOOK]
5. **Compile controls:** import real plans when available; otherwise label generated plans and keep phase structure, saturation assumptions and coordination sensitivity explicit. Test detector events and green extensions against SUMO on identical inputs before city scale. [TLS] [READER] [WORLD]
6. **Reject build defects automatically:** fail any used TLS link index without a phase state, route movement without a permitted lane connection, accidentally duplicated controller installation, contradictory source lane directions, or unexpected grade crossing. Flag unmatched lane drops, sub-vehicle storage, implausible urban speeds and turn-only mismatches; review exemptions for exits and geometry nodes. Thresholds are proposed acceptance rules, not measured traffic laws. [PLAIN] [IMPORT] [TLS]
7. **Reject false bottlenecks using evidence:** measure lane-group discharge under persistent queue and free downstream space; estimate saturation headway after the initial queued vehicles, startup lost time and realised effective green. Fit by manoeuvre and lane group, then validate on held-out periods. Suggested acceptance target is within 10% of observed saturation discharge with uncertainty intervals; 10% is an opinion project target. Do not fit signal capacity to low-demand counts or hide failure by increasing demand/teleports. [FHWA]
8. **Scale validation:** first deterministic isolated movements, then interactions/actuation, then corridor platoons and spillback, then full city with matched demand. Hold demand fixed while testing network changes. Report queue lengths, per-lane use, accepted gaps, discharge and travel times, plus whether congestion occurs in both engines. No simulator tests were performed in this research session. [INTERSECTIONS] [TLS]

**Which city works today? Opinion:** the first reproducible conversion repair can be tested **today in Stockholm**, because the exact local OSM source and the ignored turn-marking input are available. It is not yet a validated Stockholm city model. **Berlin** is the stronger documented open-data path for signal-inventory reconciliation and aerial review, but fetching the inventory and obtaining actual controller plans remain work. Neither city has verified real-signal calibration in this report. [OSM] [SNET] [BLSA] [BGEO]

## Actions requiring Erik

- **Lastkajen:** register/sign in with a valid email and accept the licence if official bulk exports are wanted; then provide authorised regional exports. No account or form was created here. [LASTKAJEN]
- **Signal-plan requests:** Erik must approve and send any request for Stockholm/Trafikverket or Berlin controller plans, detector layouts, coordination schedules and timestamped saturation observations. Public bulk access to these was not verified. Stockholm's handbook shows that detector/as-built records exist in its engineering process; it does not grant this project access. [SHANDBOOK] [BLSA]
- **Commercial/imagery access:** sign-in is needed for Mapillary downloads; Erik would need to arrange any TomTom/HERE sample licence or gated imagery access he chooses. No purchase, coverage or licence eligibility was assumed. [MAPILLARY] [TOMTOM] [HERE]

## Source URLs opened during this session

'''
for key,url in sources.items():text+=f'[{key}]: {url}\n'
text+='\nMachine-readable audit results: [Stockholm](stockholm-map-audit.json), [Berlin](berlin-map-audit.json), [turn comparison details](maps-detail.json). Source URLs support the corresponding claims; generated measurements are reproducible from the identified local snapshots.\n'
comp={r['edge']:r for r in csv.DictReader(open(O/'stockholm-map-osm-comparison.csv'))}
flags={r['edge']:r for r in csv.DictReader(open(O/'stockholm-map-turn-flags.csv'))}
ledger='''### Per-site OSM comparison ledger (measured, not independently field verified)

Every selected approach was joined to its source way ID; source direction and turn strings remain available in the comparison CSV. The following records the exact arrows available for each site. Blank means no turn-lane tag was found on the selected source ways, not that there are no real turn lanes. Flags mean exclusive-turn count differs from source tags; they do not identify which stage of a multi-segment approach carries the physical marking. All rows: [OSM] [SNET].

| Case | Source turn-lane evidence on selected approaches | Flagged selected edges | Interpretation / what is wrong |
|---|---|---|---|
'''
for i,s in enumerate(S['samples']):
 evidence=[];ff=[]
 for edge in s['edges'].split():
  r=comp.get(edge,{})
  tags=json.loads(r.get('osm_turn_tags','{}'))
  if tags:evidence.append('`'+edge+'`: '+ '; '.join(k+'='+v.replace('|',' / ') for k,v in tags.items()))
  if edge in flags:ff.append('`'+edge+'`')
 msg='OSM/net turn-count inconsistency: review terminal segment and lane permissions' if ff else 'No established error from this evidence; real layout remains unverified'
 ledger+=f"| {i+1}. {s['label']} | {'<br>'.join(evidence) or 'No turn-lane tags on selected ways'} | {', '.join(ff) or 'None flagged'} | {msg} |\n"
text=text.replace('## Analytical capacity and candidate bottlenecks',ledger+'\n## Analytical capacity and candidate bottlenecks')
text=text.replace('No satellite pixels or official junction-specific as-built plans were obtained.', 'No satellite pixels or official junction-specific as-built plans were obtained. The existing XML was not independently checked for binary-source equivalence to `clip.osm.pbf`.')
text=text.replace('### Signal programs and coordination', '**Measured:** 937 Stockholm signalised junction nodes have just one passenger approach segment. This includes possible crossings and stop-line representations; it is not a count of false installations. [SNET]\n\n### Signal programs and coordination')
for image in ['maps-20-approaches.png','maps-stockholm-samples.png','maps-cycles.png','maps-junction-types.png']:
 assert (O/'fig'/image).is_file()
(O/'07-maps-and-intersections.md').write_text(text)
print('wrote',len(text),'characters;',len(S['samples']),'sample junctions')
