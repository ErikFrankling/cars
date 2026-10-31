# Data inventory (partial), 2026-10-31

Data root: `/home/erikf/projects/personal/cars-data/`. Downloads are untrusted; no downloaded scripts were executed. Counts below were obtained by streaming XML; listed lanes and edges include internal ones. Unique edge-sequence counts, lane permission statistics and detailed length distributions were not computed. Peak running is unknown.

## Berlin BeST v2

[Source](https://www.dcaiti.tu-berlin.de/research/simulation/downloads/get/best-scenario-v2.zip): `best/best-scenario-v2.zip`, exactly 461,101,293 bytes, matching the published size. Extracted under `best/`. `berlin.sumocfg` loads `berlin.net.xml`, `berlin.rou.gz`, `berlin_bus.rou.xml`, `berlin_bus_stops.add.xml`. Time 0–86400; step length is unspecified (SUMO default applies); route steps 200; no-internal-links false; ignore-junction-blocker 20; teleport 120 s, highway teleport 0; eager-insert false; seed 251920; device rerouting is not specified. Output summary and statistics enabled. The bus route file defines flows, embedded stops and types; an implementation requires flow generation, stops and bus-stop semantics. The network requires actuated signals and internal junction lanes. Explicit rerouting is not enabled by this config; do not assume it is required without checking vehicle types and options.

Network: 231,633 edge elements, 257,426 lanes including 172,880 internal lanes; 334,761 connections; 14,034.428 lane-km including internal; lane lengths 0.1–6,932.19 m. Junction types: right_before_left 9,878, priority 15,633, traffic_light 2,875, dead_end 74, zipper 87, internal 10,999. All 2,344 tlLogic elements are actuated.

## LuST v2.0

[Source](https://codeload.github.com/lcodeca/LuSTScenario/zip/refs/tags/v2.0): `lust/lust-v2.zip`, 42,516,065 bytes; extracted `lust/LuSTScenario-2.0/`. Both DUE variants include pre-generated route partitions; no route generation is needed for these files. Both set 1 s step, junction blocker 20 s, teleport 600 s, max departure delay 600 s and Dijkstra routing. Static adds `tll.static.xml`; actuated uses network signal logic. Both load buslines, transit, types, bus stops, and E1 detectors. Network: 19,027 edges, 24,575 lanes including 15,953 internal; 30,051 connections, 1,716.245 lane-km including internal, lengths 0.1–5,770.07 m. Junctions: priority 1,791; traffic_light 203; dead_end 236; unregulated 17; internal 1,855. Network tlLogic: 201 actuated. Static additional signal logic was not separately counted.

## XML census

Paths relative to data root. Counts omitted from a line are zero for vehicle, trip, flow, person, vType, vTypeDistribution, route, routeDistribution, stop, busStop and rerouter. Times are numeric departures or flow begin where present; nonnumeric SUMO time formats were not converted. `route` is element count, not unique routes. Polygon additional files are not included in this census.

best/berlin.rou.gz {'vType': 1, 'route': 2248884, 'vehicle': 2248884} [0.0, 86399.0]
best/berlin_bus.rou.xml {'vType': 1, 'stop': 9477, 'route': 344, 'flow': 344} None
best/berlin_bus_stops.add.xml {'busStop': 5468} None
lust/LuSTScenario-2.0/scenario/DUERoutes/local.actuated.1.rou.xml {'route': 72000, 'vehicle': 72000} [35619.0, 61781.0]
lust/LuSTScenario-2.0/scenario/DUERoutes/local.actuated.2.rou.xml {'route': 71526, 'vehicle': 71526} [61781.0, 86395.0]
lust/LuSTScenario-2.0/scenario/DUERoutes/local.static.0.rou.xml {'route': 72000, 'vehicle': 72000} [0.0, 35619.0]
lust/LuSTScenario-2.0/scenario/DUERoutes/local.static.2.rou.xml {'route': 71526, 'vehicle': 71526} [61781.0, 86395.0]
lust/LuSTScenario-2.0/scenario/DUERoutes/local.static.1.rou.xml {'route': 72000, 'vehicle': 72000} [35619.0, 61781.0]
lust/LuSTScenario-2.0/scenario/DUERoutes/local.actuated.0.rou.xml {'route': 72000, 'vehicle': 72000} [0.0, 35619.0]
lust/LuSTScenario-2.0/scenario/buslines.rou.xml {'route': 2240, 'stop': 37376, 'vehicle': 2240} [2.0, 84657.0]
lust/LuSTScenario-2.0/scenario/transit.rou.xml {'route': 70484, 'vehicle': 70484} [0.0, 86395.0]
lust/LuSTScenario-2.0/scenario/vtypes.add.xml {'vType': 7, 'vTypeDistribution': 1} None
lust/LuSTScenario-2.0/scenario/busstops.add.xml {'busStop': 561} None
lust/LuSTScenario-2.0/scenario/e1detectors.add.xml {} None
lust/LuSTScenario-2.0/scenario/tll.static.xml {} None

## Berlin observations

[Provider archive](https://api.viz.berlin.de/daten/verkehrsdetektion); listing `berlin-detectors/list.xml` contains all twelve months of 2024 with new quality control, but only January–June 2025. Thus 2024 is the latest complete year in this listing. September: `berlin-detectors/detektoren_2024_09.tgz` (6,703,337 bytes); metadata `berlin-detectors/Stammdaten_Verkehrsdetektion_2022_07_20.xlsx`; provider documentation `berlin-detectors/ReadMe.txt`. Attribution: Digitale Plattform Stadtverkehr Berlin / Verkehrsdetektion Berlin, Datenlizenz Deutschland – Namensnennung 2.0. Metadata DET links detector names to MQ and lane; MQ contains direction/orientation and Gauss–Krüger zone 4 coordinates.

Archive has one CSV per detector. Columns: Datum and Stunde are local date/hour; Vollständigkeit data completeness; ZScore_Det0/1/2 correlations to parallel detectors; hist_cor correlation with expected hourly traffic; localTime, month, utc are time fields; qkfz, qpkw, qlkw are hourly motor-vehicle, car and truck counts; vkfz, vpkw, vlkw are speeds in km/h. Missing values are NaN. `berlin-detectors/weekday_profile.csv` has 9,445 detector/hour rows, mean finite qkfz over Tuesday–Thursday and observation count, generated by `profile.py`. It does not impose an additional quality threshold or exclude school holidays; use quality fields before calibration.

For spatial matching transform metadata GK4 to WGS84 then UTM zone 33 WGS84, add SUMO netOffset (-372355.98,-5804722.35), and compare nearby external edge geometries and directional bearing. Review parallel carriageways, bridges and ambiguous direction manually. No mapping was computed.

## Stockholm

Anonymous [WFS capabilities](https://openstreetgs.stockholm.se/geoservice/api/wfs?service=WFS&request=GetCapabilities) returned HTTP 200. `stockholm/wfs.xml` and `stockholm/trafikflode_motorfordon.geojson` are saved. The latter has 16,698 features; properties include street, valid-from and update dates, estimated or measured collection method, annual average weekday flow, heavy-vehicle fraction, and 06–18 / 18–22 / 22–06 light and heavy flows. Example first feature is estimated, 2014 version, 200 vehicles/day. These are heterogeneous annual/estimated flows, not simultaneous ground truth. Fit an OD prior to directionally matched counts and time profiles; hold out locations for validation, and do not claim unique OD recovery.

The Geofabrik Sweden download received zero bytes and timed out on a separate 20-second HEAD request; an Overpass attempt returned HTTP 406. No Stockholm OSM extract or SUMO network was produced. Edge/lane counts remain unknown. Finish by acquiring an anonymous clip, then run netconvert with passenger class, TLS/ramp/junction/roundabout guessing and geometry removal, and inspect retained road types.

## Remaining work

Per-class permissions, lane-length quantiles, unique route sequences, precise flow time ranges, polygon/static TLS counts, detector-to-edge matches, complete configuration/default audit, and Stockholm network conversion remain uncompleted. `census.py` and `census.txt` are in the data root. The census totals count internal elements separately from road elements. No simulator run or peak-active measurement was performed.
