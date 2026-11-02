# Data hunt 08: demand from who lives and works where

Research date: 2026-11-02. Grades: MEASURED, PROVIDER CLAIM, MODELLED, UNVERIFIED. Scripts and raw results are in [scripts-08/](scripts-08/) and [scripts-08/results/](scripts-08/results/).

## The answer

**Yes, believable Stockholm demand can be built from open data, and most of the work is already published.** Chalmers' SySMo release gives every person in Sweden a weekday plan: building-level coordinates, start and end times, and travel mode, including "car, as driver". It is CC BY 4.0. For the Stockholm region its destinations come from Trafikverket's Sampers regional model (Samm). Earlier reports listed Sampers as "needs Erik", but a sample drawn from it can simply be downloaded.

I routed SySMo's car-driver trips on our Stockholm net and scored them against measured 2018 traffic that was used in no fit of ours.

- **Level:** it reaches 90% of measured traffic on the six screenlines I trust most (the geometric mean of the ratios). Our count-fitted `v8_full` reaches 69%.
- **Essingeleden:** it carries 77% of the measured flow; `v8_full` carries 43%.
- **Commuting:** against SCB's register of who works where, it scores CPC 0.93. Plain gravity scores 0.84. The learned global dataset scores 0.44.
- **Where it loses:** on individual street counts the count-fitted demand is better, which is what fitting to counts should give. See the limits below.

**Learned OD generators are not useful for Stockholm today.** The Tsinghua global dataset does contain Stockholm, but it does much worse than gravity against SCB's register.

**The numbers are modelled and the test is small.** SySMo inherits Sampers, so this is not independent of Trafikverket's calibration. There are only six screenlines, the assignment here is static, and it has not yet been run in `cars`.

## Ranked results

| # | Source | Grade | Verdict |
|---|---|---|---|
| 1 | **SySMo population and plans** (Mendeley) | MODELLED | Best open demand prior for Stockholm. Use it |
| 2 | **Stockholm's traffic report for 2018**: screenlines, bridges, speeds | MEASURED | Missed by earlier reports. Five named measured counts plus car speeds, same year as SySMo |
| 3 | **SCB open data**: 1 km population, commuting matrix, jobs per municipality | MEASURED (register) | Independent commuting test, and enough for a gravity fallback |
| 4 | **SySMo trajectories** (Zenodo, 18 GB) | MODELLED | Simulated second-by-second routes. A third of agents removed. Comparison only, not truth |
| 5 | **Gravity from SCB and OSM** (my prototype) | MODELLED | Portable fallback. Clearly worse than SySMo, about level with count-fitting on screenlines |
| 6 | **MATSim-Sweden** | MODELLED | Long-distance only, but carries SAMGODS freight. Possible truck class |
| 7 | **Global commuting OD** (Rong et al.) | MODELLED | Has Stockholm. Worse than gravity. Don't use |
| 8 | MATSim Berlin v6.4, eqasim, ActivitySim, TAPAS, SILO | Tools | No Swedish input of their own. No gain over SySMo for Stockholm |

## The prototype

Everything was routed on our existing net (76,609 edges, turn rules respected). Trips went between 1 km zones (250 m for one run), with a road-capacity penalty in the peaks. Trips leaving the net enter at a major road. **This is a static assignment, not a run in `cars`.** Compute ran on the homelab.

### Candidates

- **SySMo:** car-driver legs only. 1,209,564 weekday trips touch the net. No count was used by me. For comparison, the replacement count-fit in report 02 has 1,318,869.
- **Gravity G1:** SCB 1 km population, SCB municipality commuting matrix, jobs placed using SCB workplace areas and 33,109 OSM points, plus other trips by gravity. Car shares and trip rates are my assumptions, so its overall level means little.
- **G1W:** the work trips of G1 alone, the fair twin of a commuting-only generator.
- **G0:** population only, with a distance decay.
- **Global:** the Tsinghua Stockholm matrix, sent both ways. Car share is an assumption, so again only its shape matters.
- **`v8_full`, `v2_full`, `stockholm`:** existing route files, used as they are.

### Test 1: measured 2018 traffic

MEASURED: [Stockholms trafikutveckling 2018, tables 1–3](https://start.stockholm/globalassets/start/om-stockholms-stad/utredningar-statistik-och-fakta/utredningar-och-rapporter/trafik-och-stadsmiljo/motortrafik/stockholms-trafikutveckling-2019-motorfordorn.pdf). October weekdays, all vehicles. Each cell is simulated flow divided by measured flow. SySMo and G1 include the peak penalty; G0, Global and the 250 m run do not; the three route files are counted as they stand.

| Screenline | Measured | SySMo | SySMo 250 m, no peak penalty | G1 | G0 | Global | `v8_full` | `v2_full` | `stockholm` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Inner city, all day | 412,100 | .85 | .83 | 1.07 | 1.28 | .34 | .82 | .74 | .60 |
| Inner city, 06:30–18:30 | 311,500 | .89 | .87 | 1.21 | 1.45 | .37 | .82 | .74 | .59 |
| Essingeleden, Gröndalsbron | 170,500 | **.77** | .78 | .96 | 1.27 | .36 | **.43** | .43 | .34 |
| Centralbron | 99,000 | .94 | .95 | 1.37 | 1.48 | .42 | .61 | .57 | .47 |
| Västerbron | 22,000 | .86 | .66 | 1.82 | 2.47 | .88 | .67 | .76 | .63 |
| City cordon | 227,500 | 1.20 | 1.28 | 1.76 | 1.77 | .46 | 1.00 | .76 | 1.08 |
| Regional centre boundary | 974,200 | .86 | .85 | .98 | 1.05 | .37 | .72 | .66 | .51 |
| Water line, whole | 310,200 | .87 | .90 | 1.21 | 1.50 | .43 | .55 | .55 | .44 |
| Södra länken, Åby *(suspect)* | 107,200 | .33 | .30 | .27 | .32 | .18 | .17 | .16 | .16 |
| Munkbroleden *(suspect)* | 13,000 | .09 | .35 | .40 | .17 | 0 | .46 | .36 | .32 |
| Skeppsbron *(suspect)* | 5,500 | 4.6 | 5.7 | 5.6 | 8.5 | 2.2 | 2.9 | 3.6 | 2.4 |
| **Level k**, six trusted lines | | **.90** | .87 | 1.28 | 1.49 | .44 | .69 | .64 | .57 |
| **Shape error**, six trusted lines, after removing k | | **11%** | 16% | 25% | 24% | 28% | 20% | 17% | 29% |

The six trusted lines are inner city all day, Essingeleden, Centralbron, Västerbron, city and regional centre. Without the peak penalty, 1 km SySMo scores k .87 and 14%; G1 scores 1.20 and 20%; G1W scores 0.55 and 18.5%.

**How to read it:**

- **k = .90 leaves room for what SySMo lacks.** It models residents' private car trips only. Vans, trucks, taxis, buses and visitors are missing, so it should come in somewhat under 1. Heavy vehicles were 3.9% of flow at the street sites I used (MEASURED). The van share is UNVERIFIED.
- **The shape advantage is modest.** With one line left out, SySMo ranges 4–12% and `v2_full` 10–20%, so the ranges overlap. Six correlated lines cannot settle this. The clear gap is in level, and on Essingeleden.
- **Time of day is close.** Measured share of inner-city traffic in 06:30–18:30 is 75.6%, SySMo gives 78.8% from its own schedules, `v8_full` 75.4%. The count-fits had their daily profile imposed.
- **Södra länken is low for every candidate**, from .16 to .33, while Essingeleden reaches .77 under SySMo. A problem that hits all demands equally points to the net or my edge choice, not demand. I didn't find out which.
- **Munkbroleden and Skeppsbron** are small streets, and my way of picking their edges is crude. They are excluded from the score.
- **`v2_full` and `v8_full` are slightly understated here:** 32,208 and 20,259 of their route edge references don't exist on the base net I used, as they were built on a modified net.

**Vehicle-km.** Stockholm's own figure for the municipality is 10.50 million per weekday, for all vehicles (MODELLED, by the city). SySMo gives 6.41 million and `v8_full` 5.74 million. Trips inside one zone never reach the road, so this undercounts local driving for SySMo. On the whole net, SySMo has 13.25 million and `v8_full` 10.55 million.

### Test 2: who commutes where

MEASURED truth: [SCB register matrix](https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__AM__AM0207__AM0207Z/AM0207PendlKomA04N/), 2019, municipality by municipality, Stockholm county. CPC is the common part of commuters: 1 means identical shares.

| Candidate | CPC, all pairs | CPC, between municipalities only | Rank correlation |
|---|---:|---:|---:|
| SySMo | **.93** | **.91** | .96 |
| Gravity to SCB job and worker totals | .84 | .88 | .90 |
| Gravity on population only | .83 | .78 | .82 |
| Global learned OD | **.44** | .62 | .55 |

Restricted to the 24 municipalities the global dataset covers, it scores .47 and .65. Those 24 hold 93% of county commuters.

For commuters both living and working in Stockholm municipality, SCB has 385,081, SySMo 293,259, gravity 355,670 and the global dataset 40,300. The gravity was not tuned (a fixed 10 km decay), so a fitted one could improve.

SySMo has 76% as many workers as SCB (900,138 against 1,183,416). That would fit it modelling who works on a given weekday rather than who has a job, but I didn't verify that. Sampers is itself built on register data, so this test is not fully independent for SySMo. It is independent for the global dataset.

### Test 3: street counts

Årstrafik, `calibrate` sites only, 2023–24, at least 5 measured days, 298 sites matched by street name. **The frozen hold-out was not touched.** Rows from non-calibrate sites (40,941) were dropped by site ID before any value was read. I used no 2025 data, and no site in the `holdout_space` role.

| Candidate | Sites with no flow | Median ratio | Total ratio | Median error after scaling | Within 50% |
|---|---:|---:|---:|---:|---:|
| SySMo | 24 | .64 | .89 | 61% | 42% |
| SySMo 250 m | 10 | .63 | .89 | 54% | 47% |
| G1 | 21 | .77 | 1.16 | 65% | 40% |
| G0 | 37 | .88 | 1.47 | 79% | 35% |
| Global | 179 | .00 | .35 | 100% | 0% |
| `v8_full` | 0 | 1.01 | .92 | **31%** | **64%** |
| `v2_full` | 3 | .93 | .85 | 35% | 64% |
| `stockholm` | 5 | .98 | .86 | 34% | 61% |

Count-fitted demand wins here, as expected, since it was fitted to counts on many of the same streets (not the same dataset). Total flow is close for SySMo but the median site gets about 64%, so small streets are short: everyone takes one shortest path, and trips are bundled into zones. Finer zones helped somewhat.

Log-count R² only runs from .33 to .38 across SySMo, G0 and G1, despite very different demand. That agrees with report 06: **site counts say little about OD.**

### Test 4: the toll total

Transportstyrelsen, September 2018: 8,487,800 passages over 20 days, so 424,390 a day (MEASURED). The source has no per-station, hourly or vehicle-class breakdown.

- **With the old hand-drawn polygon** (report 02's operator) plus the Essingeleden line: SySMo 1.18, `v8_full` .96, `v2_full` .88.
- **That polygon flatters.** It counts 5 Norra Länken edges, but the 2018 report (p.13) says through traffic on Norra länken passes with no charge. Removing Norra länken and Essingeleden from it gives the inner-city row above, where SySMo is .89.
- **A link list keyed to OSM ways:** I found one in a public [student MATSim repo](https://github.com/FNaqavi/Stockholm_MATSim/blob/main/src/main/resources/toll_osm.xml). Only 42 of its ways match our net, so it undercounts: SySMo .68, `v8_full` .56, `v2_full` .50. Provenance UNVERIFIED. A lead for replacing the polygon, not a result.

## Top 3 recommendations

1. **Make SySMo the Stockholm demand prior.** Write `scripts/stockholm/sysmo_demand.py`: read `Activity_travel.csv`, keep `Travel_Mode == Car`, depart at the previous activity's end, snap ends to edges, clip at the net edge with gates on major roads. [`sysmo_extract.py`](scripts-08/sysmo_extract.py) and [`assignlib.py`](scripts-08/assignlib.py) already do most of it. Then route it and run it in `cars`. Add a separate class for non-resident and commercial traffic, sized from the `calibrate` sites only. That full run is the real test, and whether Stockholm stops gridlocking is the question this report can't answer.
2. **Adopt the 2018 screenlines as Stockholm's standing test.** Put the six trusted lines and the car speeds into the validation scripts: 26.2 and 24.6 km/h in the inner city, 41.4 and 40.6 km/h in the outer city, morning and afternoon (MEASURED by navigation data, provider changed that year, so treat them as rough). Drop the polygon in `sthlm_cordon.py` that counts Norra länken. Find out why Södra länken is a third of measured under every demand.
3. **Keep gravity as the fallback for other cities, and skip learned generators for now.** [`build_demands.py`](scripts-08/build_demands.py) needs only register data. For freight, look at MATSim-Sweden's SAMGODS demand as a through-truck class. I read its README only, so check it covers Stockholm in useful detail first.

## What only Erik can do

I wrote no finished drafts: the Executor server was down, so I could not load `erik-writing-style`, and nothing has been sent. Points to cover if you write them:

- **Trafikverket, Sampers:** ask for the Samm base-year car OD matrices with zones, the matching Samgods truck matrices, and the reuse terms. This would check SySMo directly and give real trucks.
- **Chalmers, SySMo authors (Yuan Liao, Çağlar Tozluoğlu, Sonia Yeh):** ask whether SySMo was ever compared with road counts in Stockholm. I found no such test in the model documentation or thesis text I searched. Ask also what the feasibility filter removes, and whether there is a newer base year.
- **Lastkajen account**, as in report 02: official toll station coordinates would replace both the polygon and the student link list.

## Dataset records

**SySMo plans.** [Mendeley 10.17632/9n29p7rmn5.2](https://data.mendeley.com/datasets/9n29p7rmn5/2), [paper](https://research.chalmers.se/publication/535909), [documentation](https://research.chalmers.se/publication/531094).
- *Measures:* synthetic, from SCB, national travel survey 2011–16, Sampers OD, Lantmäteriet buildings. MODELLED.
- *Area, period:* all Sweden, base year 2018, average weekday.
- *Share of vehicles:* none observed. Models all 10,203,820 residents; no freight, service or visitors.
- *Sampling, route level:* trip ends at buildings, times in hundredths of an hour; no routes.
- *Validation:* authors report car person-km of 98 billion against Trafikanalys 95–116 and survey 113 (PROVIDER CLAIM). Mean home-to-work car distance 12.3 km against Sampers 9.6 km, in western Sweden. Survey-based and Sampers-based checks only.
- *Access:* open, CC BY 4.0, commercial use allowed. Covers Sweden.
- *Downloaded:* yes, `cars-data/datasets/sysmo-sweden/`, Person and Activity (4.7 GB), not Household. 41,642,332 rows read.
- *Serves:* demand. *Enables:* a full `cars` Stockholm day with no count fit. *Work:* about 1–2 days.
- *My checks:* 0.64 car-driver trips per person per weekday in the county, 0.53 in Stockholm municipality. [RVU 2025](https://www.regionstockholm.se/49f3b8/contentassets/5bd6e9799a2a4cfdac623b71243fd011/rapport-resvaneundersokning-region-stockholm-2025.pdf) has 2.0 trips on weekdays and 42% by car including passengers, over the whole week, so around 0.84 for the car category at ages 15–95. Plausible, perhaps high for the city. Straight-line mean of 12 km per car trip looks long next to RVU's 60% of work trips under 10 km; that is an all-mode figure, so unresolved.

**Stockholm traffic report 2018.** Linked above.
- *Measures:* tube counters, toll system counts, motorway sensors. MEASURED. All vehicles passing those lines, Oct weekdays.
- *Share of vehicles:* intended as all on those links; no accuracy figure given.
- *Sampling:* mean weekday, link and cordon level, not route.
- *Access:* open PDF; licence not stated. *Downloaded:* yes, read in full.
- *Serves:* congestion truth, demand test. *Work:* small.
- *Caution:* later editions may overlap the frozen 2025 period. Don't use those without checking `01`.

**SySMo trajectories.** [Zenodo 10648078](https://zenodo.org/records/10648078), CC BY 4.0, 18.1 GB, code in [`sysmo-data`](https://github.com/TheYuanLiao/sysmo-data).
- *Measures:* MATSim output at one-second resolution on OSM 2023, in 10 separately simulated batches. MODELLED, not observed.
- *Downloaded:* one plans file and the population table on the homelab, inspected, deleted. Events not downloaded.
- *Found:* `feasibility` is 1 for 66.2% of agents in the file, while the description says 73%. Plans include walk, bike and public transport despite the "car agents" wording. Batch 0: 676,993 agents, 1,094,035 car legs.
- *Use:* route comparison only. Prefer the Mendeley table for demand, as it keeps everyone.

**SCB open data.** [Grid](https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/statistik-pa-rutor/), DeSO, [workplace areas](https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/statistiska-verksamhetsomraden/), commuting and jobs through the API.
- *Measures:* registers. MEASURED. Grid is 1 km; workplace areas carry employees, but cover only 24% of Stockholm municipality's jobs (173,450 of 708,729; different years).
- *Access:* free, no account. Licence page not opened. *Downloaded:* yes, `cars-data/datasets/scb-open/`.
- *Serves:* demand inputs and test. Commuting is by residence and workplace, not daily attendance or car use.

**Global commuting OD.** [Figshare 28350107](https://springernature.figshare.com/articles/dataset/A_Global_Commuting_Origin-Destination_Flow_Dataset_for_Urban_Sustainable_Development/28350107), CC BY, 9.6 GB, [paper](https://arxiv.org/abs/2505.17111), [code](https://github.com/tsinghua-fib-lab/generate-od-pubtools).
- *Measures:* generated by a diffusion model from WorldPop, satellite images and POIs. MODELLED, commuting only, no time of day.
- *Downloaded:* only Stockholm and its features, by range requests, `cars-data/datasets/worldod-stockholm/`. 229 regions, median 13 km², 638,160 commuters.
- *Authors' validation:* CPC 0.572 against census (PROVIDER CLAIM). An [independent benchmark](https://arxiv.org/abs/2609.00661) finds CPC at most 0.122 for US-trained models on 14 global cities, below the roughly 0.32 it cites for gravity on US data. Those scores are at a finer level than mine, so not directly comparable.
- *Oddity:* its population feature sums to 39.4 million where SCB has 2.1 million in the same polygons (correlation .97). May be a scaling choice or a bug; not determined.

**MATSim-Sweden.** [Repo](https://github.com/matsim-scenarios/matsim-sweden). Long-distance cars and trucks, from Sampers and Samgods, 1% and 10% samples. README read only; no licence shown in repo metadata. Not downloaded.

**Others, metadata or snippets only.**
- [MATSim Berlin](https://github.com/matsim-scenarios/matsim-berlin): v6.4 in 1, 3 and 10% samples, CC BY 4.0 data, README read. See report 03.
- [eqasim](https://ile-de-france.readthedocs.io): France-based pipeline, GPL. No Swedish version found.
- [ActivitySim](https://github.com/ActivitySim/activitysim) (BSD), [TAPAS](https://github.com/DLR-VF/TAPAS) (MIT), [SILO](https://github.com/msmobility/silo) (GPL): engines needing local inputs.
- KTH Stockholm MATSim model: search snippet says an uncalibrated prototype. UNVERIFIED, the wiki page would not open, and I found no public release.
- LargeCommutingOD (Rong et al.): US areas, snippets only, not opened.
- Overture places: not tried; OSM was used instead.

## Corrections to earlier reports

- **`02`:** "97% of real cordon traffic" is flattered, as the polygon counts Norra länken. On measured 2018 lines, `v2_full` is .74 on the inner city and .43 on Essingeleden.
- **`06` §8.3:** a Sampers-derived demand needs no licence for a first version. Raw matrices still do.
- **`01`:** its Stockholm row lists no public travel speeds. The city's yearly report gives area-wide car speeds, though not dated days or per-link values.
- **Report 02's RVU link** now returns 404, as does the 2019 edition. The 2025 edition above opens.

## Dead ends

- **GitHub's `WorldCommuting-OD` has no Swedish Stockholm.** `268_US_Stockholm` is a town in the USA. Sweden's is `GHSL-678_SWE_Stockholm`, only in the Figshare zip.
- **No open 250 m SCB grid.** The 250 m result in searches is Norway's.
- **No open jobs per DeSO found.** AMPAK is paid, per report 02.
- **Transportstyrelsen's public pages** have no station, hour or class split.
- **[Zenodo 7549847](https://zenodo.org/records/7549847)** covers western Sweden only.
- **`FNaqavi/Stockholm_MATSim`** has code and config but no plans or network, and its plans file is named for 2040.
- **Finer zones** don't fix the street counts by themselves.

## New directions not covered

- **Natural experiment:** Essingeleden got its charge on 1 January 2016, and the report series gives before and after screenlines. A demand and route model could be tested on the shift.
- **Gothenburg as a second test city:** SySMo uses Sampers there too, and it has a congestion tax. Traffic data not checked.
- **Multi-day plans:** the SySMo thesis lists work on synthetic multi-day plans; not read.
- **Trip frequency:** Transportstyrelsen gives vehicles taxed per month (676,300 Swedish in September 2024), which could test how often the same cars pass.

## Limits of this work

- Static assignment. Real congestion, spillback and departure shifts are absent.
- SySMo is 2018, before the pandemic. Toll passages were 424,390 a day then and 400,976 in September 2024.
- Screenline edges are chosen by me from names and hand-drawn shapes.
- The company brain was unreachable (Executor server down), so I neither searched it first nor published this.
- SySMo extraction and all assignments ran on the homelab. SCB fetches, screenline setup and the last scoring steps ran on the PC at low priority. Downloads were data only and nothing in them was executed.
