# City data for a GPU SUMO-compatible microsimulator

Research date: 31 October 2026. Local inputs inspected read-only. No simulation run or large scenario download was performed. HTTP checks below used `curl -sSLI --max-time 12` (follow redirects); metadata and configuration files were fetched with curl. A 200 on a repository page establishes public access, **not** successful retrieval of every large object. Unknowns are stated explicitly.

## Recommendation

**Primary: Berlin BeST v2.** It combines a complete day, roughly 2.25 million car trips, SUMO inputs, a usable licence, and an independently accessible archive of real traffic counts. It is the best fit for a convincing city-scale microscopic speed/accuracy benchmark. Use standalone SUMO, pin the scenario revision and SUMO version, and include the bus extension only when stops are supported. It is synthetic individual demand calibrated to observations, not a recording of every real vehicle.

**Fallback: Luxembourg LuST v2.0.** Smaller, but a complete established microscopic city scenario with explicit route/configuration variants. Its main disadvantage is validation tied to SUMO 0.26 and weaker directly verified raw ground truth. Use it for integration and a second city; revalidate on the chosen current SUMO version.

**Dublin urban is the fastest immediate local smoke benchmark**, with 418,078 explicit vehicles across 24h and 22,668 lane elements already present. It is not the strongest primary scientific dataset until its original measured demand and detector correspondence are audited. **TuST Turin is the most attractive additional million-trip case, but its shipped configuration enables mesoscopic simulation.** Running that configuration unchanged would invalidate a microscopic performance claim.

The primary BeST payload is **461,101,293 bytes**, above the requested 200 MB download limit. This research verified it by HEAD only. Full acquisition must be a subsequent explicitly budgeted step; none of the commands below that retrieve >200 MB were executed.

## Candidate comparison

Lane counts and lane-km are different measures. Local lane counts below include internal junction lanes and potentially non-car lanes; external published edge counts are not interchangeable with these. Peak active means simultaneously inserted and running, not daily trip count. Unless explicitly given, peak active and published wall time were not verified and should be measured.

| Candidate | Day/demand and readiness | Scale; lanes; peak active | Measurements / caveats | Access and licence; decision |
|---|---|---|---|---|
| **BeST Berlin** | 24h; 2,246,917 car trips plus 25,724 bus trips in current documentation; ready SUMO config | 800 km²; 71,651 edges; 2,249 signalised junctions. Lane count and peak active unverified | MATSim demand converted and assigned to equilibrium; published street-count comparisons; real Berlin archive available separately | Public ZIP HEAD 200, 461 MB; scenario CC BY 4.0. **Primary** |
| **LuST Luxembourg** | 24h; about 288,250 vehicles in original publication; shortest-path/rerouting and equilibrium variants | 155.95 km²; 5,959 road edges; **8,904 road lanes calculated from published lane multiplicities**, 1,568.9 lane-km; peak unverified | Validated with real data, but authors restrict that claim to SUMO 0.26. Simulation E1 loops are not measured ground truth | Public v2.0 archive HEAD 200; MIT. **Fallback** |
| **TuST Turin** | 24h; 2,202,814 departures; prepared net/routes | 602.61 km²; 66,296 edges; 7,723.4 lane-km; peak unverified (5,142 final running is not peak) | Real 5T OD and independent sensor-flow validation; real signal phases. **Config has `mesosim=true` and `no-internal-links=true`** | GPLv3; public LFS media HEAD 200. Route object **1,815,047,434 B**, net 62,524,505 B. Requires microscopic rerun/revalidation |
| TAPASCologne | Full-day demand available separately; old 06–08 release often mistaken for 24h | Commonly described as million-scale, roughly 11,455 lane-km; exact selected release trip count/peak not verified | Population/activity demand, not observed trajectories; official maintainers warn about junctions, coordination, jamming and travel times | 24h route archive HEAD 200 (~50 MB); net supplied separately. CC BY-NC-SA 3.0 per official scenario page, with attribution and a stated request to inform maintainers; noncommercial restriction makes it less suitable for product work |
| InTAS Ingolstadt | Upstream 24h; **local route subset only 9,290 departures through 18,009 s** | Local net: 33,204 lanes; peak/full upstream trip count unverified | Authors report 24 real measuring points and NRMSE 0.33, activity-based demand, buses/parking/pedestrians | Public repo 200; GPLv3. Good calibration case once complete inputs recovered |
| Dublin DCC urban | Local 24h; 418,078 explicit vehicles; ready local config | Local 20,289 edges / 22,668 lanes; peak unknown | Upstream says demand-generation datasets included; local detector files are POIs, not measured time series | Public repo 200; GPLv3 (`LICENSE.md`). Strong immediate local integration case |
| Dublin M50 | Local 24h; 346,287 vehicles | 309 edges / 911 lanes; corridor, not full city | 53 detector POIs locally; demand source audit still needed | Same Dublin repository/licence; valuable freeway complement |
| Stuttgart STOMP | 24h workday/Sunday; local workday 205,826 vehicles | 45 km A81 corridor; local 7,672 lanes (large number includes internal structure); peak unknown | Real 2013 authority link counts; ramp entry/exit demand estimated | Public repo 200. Net ODbL/DbCL; other data/config CC BY-SA 4.0. SUMO 0.25 era; not whole Stuttgart |
| Alicante–Murcia | Upstream nine days, **18 independently calibrated 12h chunks**; local chunk 75,955 vehicles | 97 km freeway; local 1,030 lanes; peak unknown | 82 measured loops, flow/speed/occupancy and light/heavy classes; very good corridor validation | Public repo 200; MIT. Need join consecutive chunks carefully for continuous day |
| Bologna Acosta | Local 1h, 8,622 cars; optional 157 buses | Local 650 lanes; small district | iTETRIS real-world case, detector definitions available; no measured intervals locally | Public DLR directory 200; directory-specific data licence not established. Not full-day city |
| MoST Monaco | Multimodal ready scenario; **current README example covers 36,000 s**, not evidence of 24h | Current example inserts 46,842 vehicles / 45,000 persons; older publications have smaller demand | Good complex-road-user compatibility test; not million-scale full-day evidence | Public repo 200; GPLv3; current README tested SUMO 1.14 |
| Barcelona | Public CoCi Eixample teaching scenario; larger published SUMOPy city work also exists | Teaching model covers city core, not demonstrated full city/full day; full-city counts/peak unverified | Activitygen/sociodemographic demand in teaching case; do not label count-calibrated. Research papers alone do not establish turnkey payload | CoCi and SUMOPy repos HEAD 200; CoCi EPL 2.0 / SUMOPy GPLv3 code; underlying large-city demand rights not established. Not selected |
| Vienna | Found Neubaugürtel SUMO/Unity research; no verified turnkey whole-city 24h demand | District example; full-city lane/trip/peak unknown | OSM topology does not establish measured demand; Austria West is a different regional mesoscopic case | No verified candidate payload or data licence. Not selected |
| Manhattan / NYC | TrafficClaw advertises Manhattan/Queens/Brooklyn 24h inputs; taxi demand is another public option | Full private-vehicle population and peak not verified | Taxi OD is real but incomplete traffic; operational benchmark is not automatically independently calibrated traffic | TrafficClaw repo HEAD 200; external large scenario payload/data licence not established. Not preferred over BeST |
| LA + ETH five-city SUMO collection | Official SUMO catalogue links 24h Boston/Lisbon/LA/Rio/SF inputs | Potentially very large; counts/lanes/peaks unverified | Need check demand provenance/calibration before equating city size with realism | ETH record 584669: curl **429**, web fetch 403; actual assets/licence unverified today. Not an accessible verified primary |
| MATSim Berlin / Zurich / other open scenarios | Daily activity plans, networks and sometimes counts; **not lane-level SUMO routes** | Large regional populations; samples often 1/10/100%, capacities scaled | Strong transport-model calibration possible; conversion loses lane geometry and signal realism | Open models catalogue 200; Berlin repo 200, inputs CC BY 4.0 / code GPLv2. Zurich asset and exact data licence not verified. BeST already solves Berlin conversion |
| UTD19 | Detector measurements, not OD or microscopic routes | 23,541 detectors / 40 cities, typically 3–5 min | Good independent flow/occupancy/speed source; observations not sufficient to identify unique routes | Portal 200; **sign up, accept research conditions, emailed download link**. Not anonymous downloadable scenario |
| PeMS | Archived freeway counts/speeds, no city microscopic demand | About 40,000 California detectors; >10 years | Strong LA/freeway validation source; imputation and faulty-sensor flags matter | Portal 200; **free account application, typically 1–2 business-day approval**, service terms; unrestricted redistribution licence not established |
| pNEUMA Athens | Real drone trajectories, morning sessions over five days, ~2.5h/day | ~1.3 km², >100 intersections, >0.5M trajectories **across collection**, not daily city trips | Excellent local microscopic behavior ground truth; incomplete view and track segmentation | Landing page 200, public download advertised; actual asset and redistribution licence not verified. Fails full-day/city requirement |

Sources: [official SUMO scenario catalogue](https://sumo.dlr.de/docs/Data/Scenarios.html), [BeST repository](https://github.com/mosaic-addons/best-scenario), [LuST data and configurations](https://github.com/lcodeca/LuSTScenario), [TuST repository](https://github.com/marcorapelli/TuSTScenario), [InTAS](https://github.com/silaslobo/InTAS), [Dublin](https://github.com/maxime-gueriau/ITSC2020_CAV_impact), [Alicante](https://github.com/msepulcre/Alicante-Murcia-SUMO-Scenario), [STOMP](https://github.com/boschresearch/stuttgart-sumo-traffic-scenario). Alternative/source-only candidates: [Barcelona CoCi](https://github.com/ethz-coss/CoCi-MooC-SUMO-scenarios), [SUMOPy](https://github.com/schwoz/sumopy), [TrafficClaw](https://github.com/usail-hkust/TrafficClaw), [MATSim catalogue](https://matsim.org/install/open-data-models/), [UTD19 terms](https://utd19.ethz.ch/), [Caltrans account requirements](https://dot.ca.gov/programs/traffic-operations/mpr/pems-source), [pNEUMA](https://open-traffic.epfl.ch/).

## What the local copies actually contain

Directory: `/home/erikf/projects/personal/thesis-src/kex/config/scenarios`. Sizes are disk usage rounded by `du -sh`. Counts were first checked with grep/rg count searches, then a streaming Perl tag counter (needed because some XML is minified and `grep -c` counts lines, not elements). Depart times are observed numeric departure minima/maxima, not a guarantee all vehicles can insert. No large files were printed in full.

| Local copy | Disk | Vehicles and departure seconds | Net edge/lane elements | Detectors and config reality |
|---|---:|---|---|---|
| alicante | 53 MiB | 75,955; 1–43,799 | 596 / 1,030 | Three files with 83 E1 definitions each (classes); no measured intervals. Five rerouters; config end 43,800 |
| bologna | 2 MiB | Cars 8,622, 0–3,598; separate 157 buses, 0–3,600 | 473 / 650 | 62 E1 definitions; seven static TLS. Config **does not load** bus routes/stops or detectors |
| dublin_m50 | 66 MiB | 346,287; 0–86,392.10 | 309 / 911 | 53 POIs; 23 route distributions; one static TLS; end 86,400 |
| dublin_urban | 100 MiB | 418,078; 0–86,382.00 | 20,289 / 22,668 | 480 POIs; 480 route distributions; net has 435 static TLS, additional file supplies 434 actuated TLS; end 86,400 |
| ingolstadt | 51 MiB | 9,290; 0–18,009 | 23,648 / 33,204 | 9,290 route distributions; 196 E1 definitions and 405 bus stops stored but **not loaded** by local config. Net has 76 actuated + 22 static TLS. End 86,400 does not make this full-day demand |
| stuttgart | 120 MiB | 205,826; 0.46–86,398.44 | 2,886 / 7,672 | No detector file locally, no TLS found; config end 93,600 permits two-hour clearance |

All six configurations use 0.5-second steps and a shared `../../vtypes.xml`, outside the scenario directories. These copies have already been adapted; they are not clean upstream reproductions. No `<flow>`, `<trip>`, `<person>` or `<vTypeDistribution>` elements were found in these six directories. That does not establish absence in the shared type file or complete upstream releases. Detector definitions and POIs are sensor locations/configuration, **not historical observations**. None of the six local directories contains measured detector interval series.

## Acquisition commands and verified access

These are reproducible instructions for a later acquisition, not commands already executed. Preserve licences and record commit SHAs and checksums. Avoid cloning all of DLR's repository or TuST's output traces. No account is needed for the public files below.

**BeST: requires lifting the 200 MB cap for a complete download.** HEAD verified ZIP content-type and 461,101,293-byte size, not just an HTML page. Direct URL omits the optional `?record=true` download counter used by the upstream Python script.

```bash
curl -fIL 'https://www.dcaiti.tu-berlin.de/research/simulation/downloads/get/best-scenario-v2.zip'
# Later, only with a download budget >461 MB:
curl -fL --retry 3 -o best-scenario-v2.zip \
  'https://www.dcaiti.tu-berlin.de/research/simulation/downloads/get/best-scenario-v2.zip'
unzip best-scenario-v2.zip -d best-v2
# Run berlin.sumocfg at its extracted location; documented version is SUMO 1.22.0.
sumo -c best-v2/berlin.sumocfg --summary-output best-summary.xml
```

**LuST fallback:** archive HEAD 200; compressed size was not advertised, so retain a hard transfer cap. If exceeded, do not call the partial file a valid archive.

```bash
curl -fL --max-filesize 200000000 -o lust-v2.zip \
  'https://codeload.github.com/lcodeca/LuSTScenario/zip/refs/tags/v2.0'
unzip lust-v2.zip
sumo -c LuSTScenario-2.0/scenario/due.actuated.sumocfg
```

LuST's configuration explicitly loads buses, three equilibrium route partitions, transit, vtypes, bus stops and E1s. The road-lane calculation above is 3,942 + 2×1,176 + 3×754 + 4×87; it excludes internal lanes absent from those published road-edge totals.

**TuST audit:** raw GitHub files for the network/routes are LFS pointers. Use the media endpoint for data. HEAD verified both media objects, and the pointer declared the same sizes. Do not download the route object under the current cap. A later selective checkout avoids many gigabytes of simulated traces:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/marcorapelli/TuSTScenario.git
cd TuSTScenario
# >1.8 GB later acquisition, outside current limit:
git lfs pull --include='Scenario/TuST.net.xml,Scenario/Routing.rou.xml'
# Must override the shipped mesoscopic model before a microscopic benchmark:
sumo -c Scenario/TuST.sumocfg --mesosim false
```

That override alone does not establish fidelity: review internal links/junction processing, teleport rules, output overhead and changed validation before publishing results.

**TAPAS full-day routes:** HEAD 200 after SourceForge redirect; ~50.1 MB listed. Network is in the separate base scenario, not necessarily this route-only archive.

```bash
curl -fL --max-filesize 200000000 -o cologne-24h.7z \
 'https://downloads.sourceforge.net/project/sumo/traffic_data/scenarios/TAPASCologne/TAPASCologne-0.24.0-24hRoutes.7z'
```

**Other repositories:** shallow/filtered clone first and inspect tree sizes before fetching data. These exact repository URLs returned curl HEAD 200: `https://github.com/silaslobo/InTAS`, `https://github.com/maxime-gueriau/ITSC2020_CAV_impact`, `https://github.com/msepulcre/Alicante-Murcia-SUMO-Scenario`, `https://github.com/boschresearch/stuttgart-sumo-traffic-scenario`, `https://github.com/lcodeca/MoSTScenario`. Bologna directory `https://github.com/DLR-TS/sumo-scenarios/tree/main/bologna` returned 200. They were not bulk cloned; full dependency integrity and transfer size remain untested.

## Ground truth and performance experiment

Berlin has an unusually useful independent source: [Digitale Plattform Stadtverkehr traffic-detection archive](https://api.viz.berlin.de/daten/verkehrsdetektion), curl HEAD 200. Licence is **Datenlizenz Deutschland – Namensnennung 2.0**, with attribution “Digitale Plattform Stadtverkehr Berlin / Verkehrsdetektion Berlin”. The provider warns that historical data was revised in 2025. Its file browser calls a public Azure Blob listing; curl GET verified that listing and returned actual filenames/sizes, e.g. January 2015 hourly lane-detector data at 4,634,033 bytes. This is stronger evidence than a paper's claim that counts once existed.

```bash
# Verified listing endpoint; inspect readmes, metadata and choose matching scenario year/day.
curl -fL 'https://mdhopendata.blob.core.windows.net/verkehrsdetektion/?restype=container&comp=list&include=metadata&maxresults=100'
# Exact object discovered in that listing; HEAD verified 200 for this exact object; download is optional:
curl -fIL 'https://mdhopendata.blob.core.windows.net/verkehrsdetektion/2015/alte_qualitaetssicherung/Fahrstreifendetektoren/det_val_hr_2015_01.csv.gz'
```

The example is an **old quality-control branch**, not a recommendation to mix 2015 observations with another scenario year. Resolve date, station metadata, directions, lanes and quality-control version first. The listing request can paginate; follow its continuation marker. No raw observations were fetched in this research. The official Cologne scenario page was also fetched with curl and identifies CC BY-NC-SA 3.0; no notification to its maintainers was sent.

1. Freeze scenario, SUMO version, seed, step length, types and controls. Establish a headless **microscopic** SUMO baseline with the exact same inputs as the GPU engine. Keep separate original and normalized-input baselines. Record every unsupported feature removed.
2. Select one representative non-holiday weekday and keep independent stations or days out of calibration. Match detector coordinates/direction to **external** lanes, manually review bridges/parallel carriageways. Check count units, classes, timestamps, DST, intervals, missing values and revised quality flags. A synthetic typical weekday cannot promise exact agreement with an arbitrary observed day.
3. Compare per-lane/site 5/15/60-minute counts, hourly GEH `sqrt(2*(sim-obs)^2/(sim+obs))`, MAE/RMSE, weighted absolute percentage error, and time-of-day peaks. Report zero-volume handling, coverage and rejected detectors. Compare speeds with matching time/space averaging; occupancy only if detector geometry/vehicle lengths are consistent. Plot held-out station curves and residual maps in the eventual benchmark.
4. Compare GPU vs SUMO separately: cumulative departures/arrivals, insertion backlog, active vehicles, travel-time distributions, queue lengths, per-edge flows, collisions and teleports. Preserve constraints on turns, lane changing, signal conflicts and downstream blocking. SUMO agreement measures implementation fidelity; real-count agreement measures empirical validity.
5. Derive **peak active** from `max(running)` in per-step summary output, including time of peak and waiting-to-insert separately. Do not estimate it from daily trips. Count external drivable lanes and internal lanes separately after obtaining the full primary net.
6. Time 24h plus an explicitly reported clearance period. Report wall time, real-time factor `86400/wall_seconds`, speedup over SUMO, vehicle-updates/s, CPU/GPU/RAM/VRAM, versions, step length, and output settings. Include preprocessing and transfers separately, warmup and repeated seeds. Match output overhead; full FCD can dominate.

**Published runtime:** BeST's current README reports **7 hours on a 3.4 GHz CPU without GUI**, about **3.4× real time**. CPU model, full timing method and variance are not specified there; this is an indicative historical reference, not a prediction for Erik's hardware. MoST's current README reports 3,407.14 s with real-time factor 10.566 (36,000 s simulated) on its stated Apple/Darwin build; this is not a 24h run. Reliable comparable wall times were not verified for the other candidates. No invented expected runtime is assigned to them.

## Compatibility requirements for the reimplementation

| Feature | Evidence and implementation consequence |
|---|---|
| Explicit vehicles, routes and route distributions | All local copies use vehicles; Dublin and InTAS reference route distributions. Resolve routes/types across all input files and sample alternatives reproducibly |
| Flows and type distributions | No local flow/vTypeDistribution elements; upstream STOMP starts from flows. Import `number`, rate/probability/period and begin/end correctly or pre-expand with documented seeds. Audit shared vtypes and upstream primary files before claiming support |
| Junctions and signals | Dublin/InTAS have actuated signals; LuST provides static/actuated alternatives. Need detector-triggered phases, minimum/maximum greens, clearance, offsets, right-of-way and internal-lane behavior. Freezing actuation changes congestion and cannot inherit validation |
| Stops, buses and parking | Bologna optional buses contain 542 stops; InTAS upstream uses buses/parking; LuST loads bus lines/stops; current BeST adds scheduled buses. Support dwell, stopped-lane blockage, vehicle dimensions and schedules. Do not silently discard buses |
| Pedestrians / cyclists / multimodal trips | Present upstream InTAS and MoST; absent in local six route subsets. Unsupported crossings can alter car capacity. Define and validate a car-only variant separately |
| Rerouting | Five Alicante rerouters; upstream InTAS tunes rerouting probability; LuST has rerouting and equilibrium choices. Offline fixed routes are an intentional model variant, not identical to dynamic routing |
| Teleports and insertion | BeST reports 2,332 teleports; local Alicante/InTAS permit 300 s; TuST 150 s. Match or disable consistently and report gridlock consequences, unfinished trips, delayed departures and max-depart-delay |
| Auxiliary geometry / detectors | Polygons can be ignored for physics; E1 measurement semantics must match when used for comparison; sensor POIs cannot substitute for measurements |

BeST's complete payload was not downloaded, so an exhaustive tag census for it is still pending. Its bus extension is documented, but flows/type distributions, signal logic types and rerouting settings must be scanned before scheduling the definitive benchmark.

## Stockholm: realistic route to the preferred city

**Verdict:** feasible as a research/calibration project; not currently verified as an anonymous-download, ready full-day city scenario. Start the GPU milestone with Berlin and develop Stockholm as a separate data pipeline. Counts constrain demand but do not uniquely reveal OD or individual trips.

### What exists and what access requires

- **Trafikverket real-time API:** official [registration instructions](https://www.trafikverket.se/e-tjanster/trafikverkets-oppna-api-for-trafikinformation/) returned curl 200. Requires account details, licence acceptance, email verification and an API key. The XML-query endpoint `https://api.trafikinfo.trafikverket.se/v2/data.json` returned **400 to an unauthenticated HEAD**, as expected for a service requiring POST/query/auth; no authenticated extraction was tested. Investigate `TrafficFlow` for measurement-site flow/speed and coordinates using the current official schema. Do not assume complete historical retention or full MCS coverage. Archive a whole day prospectively if historical export is unavailable.
- **MCS sensors / Trafik Stockholm:** MCS motorway measurements and floating-car/travel-time fusion are used in KTH/Mobile Millennium Stockholm work. Research access is not proof of an open bulk archive. [Trafik Stockholm's open-data page](https://trafiken.nu/stockholm/oppna-data/) returned 200 and directs users to Trafikverket, the city and Trafiklab rather than providing a complete microscopic demand file. DATEX II subscription is a separate route requiring an agreement; check which detector publication covers the needed MCS sites and historical period. Taxi GPS/FCD can require a separate commercial or research agreement.
- **Stockholms stad:** [open traffic/geodata](https://openstreetgs.stockholm.se/home/) returned 200 and describes public WMS/WFS/OGC services. Traffic-flow and annual-traffic layers exist; [ÅMVD visualization](https://openstreetws.stockholm.se/Home/Visualisering/AMVD) returned 200. These provide annual average weekday traffic and daily profiles, not necessarily simultaneous raw observations for one date. The [city's current open-data guidance](https://start.stockholm/om-stockholms-stad/utredningar-statistik-och-fakta/oppna-data/) explicitly says **BankID login is required for the detailed Trafikdata measurement system**. Erik must perform that login; we did not attempt it. Export actual dated counts/speeds and station metadata if available. Confirm the licence on each export; do not assume every city layer is CC0.
- **SUMO / MATSim / KTH:** [MATSim Sweden](https://github.com/matsim-scenarios/matsim-sweden) returned 200, but its stated focus is **long-distance cars and freight**, based on SAMPERS/SAMGODS, not complete urban Stockholm trips. KTH has Greater Stockholm MATSim/IHOP work and smaller SUMO/Kista studies, but no complete freely downloadable, calibrated 24h Stockholm SUMO bundle was verified. Neither publication access nor an open code repository proves underlying survey/OD data can be redistributed. A [2025 KTH thesis](https://kth.diva-portal.org/smash/get/diva2%3A1926397/FULLTEXT01.pdf) explicitly describes incomplete demand even for its Kista coverage; it is evidence of work needed, not a turnkey city dataset.
- **Official metropolitan model:** Trafikverket describes **Dynameq Storstockholm**, a regional mesoscopic model. [Official model information](https://bransch.trafikverket.se/for-dig-i-branschen/Planera-och-utreda/Samhallsekonomisk-analys-och-trafikanalys/trafikprognoser-och-trafikanalyser/trafikanalyser-och-vagkapacitetsanalyser/) documents boundaries/manuals and a contact for access. It is not a verified anonymous SUMO download. An OD export could help if supplied with rights; acquiring it would require Erik's approved contact, which this research did not initiate.

### Build plan

1. Define a Stockholm urban boundary plus approach-road buffer; retain bridges, tunnels and motorway interchanges. Choose an ordinary **24-hour weekday**, avoiding the DST transition, and consistent weather/incident conditions. Freeze an OSM extract and retain ODbL attribution. Use a clipped extract below the download cap rather than automatically downloading all Sweden.
2. Convert with `netconvert`, keeping car-access restrictions, lane counts, speeds and signal locations. Manually audit bridge/tunnel separation, turn restrictions, motorway ramps, bus lanes and bottleneck lane drops. Generated signals are assumptions until actual timings or measured discharge patterns support them.
3. Acquire dated city counts and motorway flows/speeds. Separate annual-profile constraints from same-day measurements. Obtain site coordinates, direction, lane/class coverage and quality flags. Clarify API data terms; travel-time metadata being CC0 does not establish the licence of every MCS/FCD product.
4. Generate geographically plausible candidate routes between boundary gates and residential/employment zones. Use demographic/activity priors or licensed OD if available; include internal-to-internal, incoming, outgoing and through traffic. SUMO `randomTrips` alone is only a prior, not measured demand. Run `duarouter` to generate connected candidates.
5. Map counts into interval edge/turn observations and use **routeSampler** to fit route multiplicities. Convert vehicles/hour rates into interval counts correctly. Hold out stations/days before fitting, regularize against implausible short routes and unobserved traffic, and preserve class/time profiles. Iterate assignment and signal/bottleneck corrections. routeSampler alone does not calibrate travel times or recover a unique OD matrix.
6. Run a SUMO baseline and compare held-out counts, corridor speeds/travel times, peak timing and queues. Include a clearance tail and report unmet insertion demand. Then run the GPU engine on exactly those frozen inputs. First deliver a motorway/inner-city subarea and expand only after its sensors match.

Illustrative commands after acquiring the inputs (not executed; filenames are pipeline contracts):

```bash
netconvert --osm-files stockholm.osm.xml -o stockholm.net.xml \
  --tls.guess true --tls.default-type actuated
# candidate-trips.xml must come from zones/OD/activity priors, not loop counts alone.
duarouter -n stockholm.net.xml -t candidate-trips.xml -o candidates.rou.xml
python "$SUMO_HOME/tools/routeSampler.py" \
  -r candidates.rou.xml --edgedata-files fit-counts.xml -o stockholm.rou.xml
```

Confirm options against the pinned tool version and validate all candidate routes. [SUMO observation-based demand tools](https://sumo.dlr.de/docs/Demand/Routes_from_Observation_Points.html) and [turn/count tools](https://sumo.dlr.de/docs/Tools/Turns.html) returned curl HEAD 200. The hard dependency is access to sufficiently dense, time-aligned observations and credible signal/OD priors. An engineering estimate is days for a preliminary OSM/count subarea, **weeks or longer** for a defensible full-city calibration; that is a planning estimate, not a published result.

## Verification limits

HTTP checks verify current transport accessibility, not full XML integrity or licence completeness. UTD19/PeMS/pNEUMA portals returned 200 but gated or external data objects were not fetched; Vienna/Zurich and the ETH five-city payload remain unresolved, rather than being presented as working downloads. Berlin/LuST are therefore the practical pair, with Dublin for immediate local execution and Alicante for controlled detector-based corridor checks. Exactly this research document was written; no scenario data, source code or commits were changed.
