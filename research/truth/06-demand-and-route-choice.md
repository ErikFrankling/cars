# Demand, route choice, and a believable city simulation

Research date: 2026-10-31, reviewed and extended 2026-11-01. This report contains evidence, a small prototype, and a build spec. No GPU job or simulator run on a real network was made for it.

**Erik's question: are there better data on what trips people take?** Yes, but no city we use has them for free. Mobile-network and probe OD samples, regional demand models and survey microdata all beat road counts by a wide margin for this purpose, and each needs a licence or a request. In our prototype, a 10% sample of real trips recovered zone-to-zone demand better than counters on 60% of links.

**"People get to work every day, so it does work."** Largely right [opinion resting on §4, §5 and §7], and that is the most useful finding here. Real drivers spread out over routes, shift a few minutes, and sit just below the network's critical load. A simulation with fixed routes has none of that. In the prototype, the same demand at twice the base load averages 19 minutes on empty-network routes and 4 minutes after assignment. Two limits apply. Real cities do collapse above their critical accumulation, and route choice does not move that point much. And our Berlin run gridlocks while carrying only about 58% of the counted traffic, so that collapse is not a demand problem.

**Five findings:**

1. **How you reroute matters more than whether you do.** In the prototype, rerouting everyone each iteration leaves a relative gap near 84% and a 1,557 s mean trip at 150% load, with gridlock in some seeds. Capping the share at 15% with cost memory reaches 1.4% and 191 s. [Modelled, §7 E1]
2. **Counts validate but do not identify OD.** A prior with zone-pair correlation of only 0.70 scores 25.8% on held-out counts, against 25.3% for a different day of the true demand. So the counts cannot tell them apart. An unregularised fit made OD worse. [Modelled, §7 E5; in line with Marzano et al. and UK TAG M3.1]
3. **Teleports can hide gridlock entirely.** At 250% load, 17,910 unfinished trips become 0 with a 300 s teleport rule, leaving only 2,985 teleports as evidence. [Modelled, §7 E3]
4. **Real behaviour is close to shortest time, but rarely exact.** 13.5% of commutes follow the modelled shortest-time path exactly, yet about half of all trips lose under 30 s and almost 90% under 5 minutes. Google moved under 2% of trips by about 30 s each and measured +2% speed on targeted segments, but only +0.35% across affected segments and −0.69% in trip time. [Measured, §4]
5. **A full pipeline is an overnight job on one RX 7900 XT, not interactive.** About 5–6 minutes per iteration and 5–6 hours per calibrated city. The Berlin day runs at 12.8 million updates/s, not the 50 million plateau, so cost per day is mostly per-lane. Routing 15% of trips with ALT on the real Berlin graph took 1.7 ms per path. [Calculated with measured parts, §8.11]

**Recommendation [opinion]:** build the loop in §8, in its stated order. Fix supply and the kernel first, then route assignment, then departure time, then calibration, keeping an untouched validation set throughout. Faster simulation makes falsification affordable. It does not make link counts identify people's trips.

## Evidence convention and limits

- **Measured:** observations, surveys, field experiments, or directly inspected primary documentation. A provider's documented product specification is marked “provider”, and is not independent evidence of accuracy.
- **Modelled:** simulation experiments, synthetic demand, inferred behaviour, or calculations conditional on assumptions. These are not measurements of actual drivers. Everything from the prototype is modelled.
- **Opinion:** this report's engineering recommendations, hypotheses, and proposed thresholds.

External sources were opened in this session unless the text says otherwise, and §9 lists every one that could not be. Where only an abstract was read, the text says so. Local findings cite `file:` URLs or relative links; these are observations of code and output files, not proof of runtime behaviour.

## 1. What “real trip data” can mean

A useful procurement distinction [opinion] is between **observed locations**, **inferred journeys**, and **expanded population demand**. Ask for all three definitions separately. An OD table of people is not an OD table of cars; a route query is not a completed journey; several vehicles crossing a sequence of counters are not several different trips.

| Source | What is available and evidence grade | Bias, accuracy, and recommended role [opinion unless explicitly attributed] | Access/cost verified in this session |
|---|---|---|---|
| Household travel diaries / travel surveys | **Measured:** purpose, modes and traveller characteristics in Sweden's RVU; Trafikanalys calls it the source describing these dimensions together. Germany's MiD 2023 sampled about **421,000 people / 218,000 households**. [RVU evaluation](https://www.trafa.se/etiketter/transportovergripande/hur-val-kan-mobilnatsdata-beskriva-vara-resvanor-14193/), [MiD ministry](https://www.bmv.de/SharedDocs/DE/Artikel/G/mobilitaet-in-deutschland.html) | Best anchor for daily schedules, non-work trips, occupancy, purpose and mode. Audit non-response, recall, omitted short trips, geographic sample size and weights. Do not expect a complete street-level OD matrix. | Public summaries; MiD anonymised datasets are available through BASt's MobilityData Campus for scientific/public applications. Fine RVU microdata access and fees were not verified. Same primary links. |
| Census / administrative commuting matrices | **Measured administrative relationship:** SCB's table links residence municipality with workplace municipality; this is its definition of commuting. [SCB table and notes](https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__AM__AM0207__AM0207Z/AM0207PendlKomA04N/) | Anchor work-location marginals. This is not daily attendance, departure times, route, or car mode. Apply attendance/remote-work, mode and occupancy models before generating cars. | Public aggregate table opened; the particular verified series is **2019–2021**, not a claim that it is the latest series. Finer current tables require separate verification. |
| Mobile network signalling / CDR | **Provider:** Telia aggregates and expands subscriber movements to Sweden's population. **Measured agency evaluation:** Trafikanalys found mobile data a possible complement for national and county totals, and useful by month, with results “inte helt tillförlitliga” at finer breakdowns; its 2025 page states shortcomings for travel relations, and that work combines mobile and survey data. [Telia](https://www.telia.se/en/business/iot/crowd-insights), [2025 agency findings](https://www.trafa.se/transportmonster/kombinerade-mobilnatsdata-och-enkatdata-beskriver-resmonster-15129/) | Operator market share, multiple SIMs, sparse signalling, tower geography, staypoint thresholds and mode inference require auditing. Use broad OD/time patterns with survey anchors; not a directly measured car trajectory. | Commercial; no price verified. Aalto's purchased dataset includes Stockholm-area municipalities, hourly OD at resolutions down to **250 m**, and suppression below **five devices**. This describes that licensed release, not every Telia offering. [Purchaser's dataset record](https://datahub.aalto.fi/en/data-sources/telia-crowdinsights) |
| GPS probes / smartphone panels | **Measured positions, modelled trips:** Microsoft's GeoLife release has **182 users**, **17,621 trajectories**; **91%** are dense, typically 1–5 seconds or 5–10 metres. [Microsoft release](https://www.microsoft.com/en-us/download/details.aspx?id=52367) | High spatial detail does not imply population representativeness. Device/app selection, missing pings, urban-canyon errors, battery policies and inferred stop definitions matter. Useful for route shares, travel times and trip-length distributions after matching. | GeoLife downloadable; current city-representative panels and licences must be checked individually. Historical small panels are algorithm benchmarks, not contemporary Stockholm demand. |
| Connected-car / fleet data | **Provider:** TomTom uses navigation devices, in-dash systems and apps for historical FCD; StreetLight describes GPS, location-based services and connected-vehicle inputs. [TomTom documentation](https://docs.tomtom.com/traffic-stats/documentation/product-information/introduction), [StreetLight methods](https://learn.streetlightdata.com/hubfs/White%20Papers/Methodology%20and%20Data%20Sources/StreetLight%20Data_Methodology%20and%20Data%20Sources.pdf?hsLang=en) | OEM/model-year, fleet and commercial-driver selection can bias routes and times. Validate penetration by road class/time rather than expanding a single global fraction. Full trips are more valuable than speeds alone, but endpoint trimming can affect short-trip OD. | Commercial; no comparable Sweden price verified. StreetLight's opened methodology says US/Canada inputs, with connected-vehicle data US-only. Do not assume Sweden coverage. Same sources. |
| ANPR / toll gantries | **Measured:** Stockholm congestion charging photographs plates and identifies vehicle owners. [Transportstyrelsen](https://www.transportstyrelsen.se/sv/vagtrafik/fordon/skatter-och-avgifter/trangselskatt/) | Matched passages can constrain crossing-to-crossing movements and travel times, not origins inside unsensed areas or trips avoiding gantries. Plate observations concern vehicles, not person purpose or occupancy. Obtain aggregate crossing matrices, not owner identities. | No permission to access linked individual passages or research price was verified. Public existence of charging does not establish public access to trajectories. |
| Google | **Measured product specification:** Routes API returns directions, travel times and distances for supplied locations; it is not a published count of observed OD demand. Historical Community Mobility reports stopped adding data on **15 October 2022**. [Routes API](https://developers.google.com/maps/documentation/routes), [Google status](https://support.google.com/covid19-mobility/?hl=en) | Travel-time validation may be possible under the relevant API agreement. Do not infer trip volumes by requesting a route matrix, or treat old regional mobility indicators as an OD survey. | API access/terms must be checked for the planned storage and analysis. No bulk city OD product, research entitlement or price was verified. |
| Apple | **Measured status:** COVID Mobility Trends reports ended **14 April 2022**. [Apple notice](https://covid19.apple.com/mobility) | Do not build the demand pipeline around a discontinued indicator. No current public Apple population-OD dataset was verified. | No current OD access or price verified. |
| Replica | **Modelled/provider:** Places generates synthetic populations and typical weekday/weekend activity patterns across US megaregions; it calibrates outputs against observations. [Replica methodology](https://documentation.replicahq.com/docs/seasonal-mobility-model-methodology-summary-places) | A useful example of the desired fused product, not raw observed trips and not independent truth. Request withheld validation and lineage before using both its demand and its fitted counts as validation. | No Sweden product or public price verified. The opened methodology specifies US coverage. |
| StreetLight | **Modelled/provider:** proprietary processing performs trip identification, map matching and expansion. [Methods, 2025](https://learn.streetlightdata.com/hubfs/White%20Papers/Methodology%20and%20Data%20Sources/StreetLight%20Data_Methodology%20and%20Data%20Sources.pdf?hsLang=en) | Useful OD/select-link product where covered. Sample counts and expanded vehicle counts must remain distinct; inferred purpose is not a diary answer. | US/Canada documented; Sweden access unverified. No public project price verified. |
| TomTom | **Provider:** OD Analysis reconstructs trips from time-stamped device traces; Traffic Stats supplies historical road conditions. **Measured purchaser specification:** Netherlands NDW describes approximately **10–20%** FCD coverage varying with time/place. [OD product](https://www.tomtom.com/newsroom/product-focus/tomtom-origin-destination-analysis-explained/), [NDW](https://docs.ndw.nu/en/handleidingen/hbtool/) | Strong candidate for probe travel-time and broad route/OD distributions. The Dutch fraction is not a Sweden penetration estimate or an accuracy percentage. Demand expansion needs local validation. | Commercial; no Stockholm extract, licence terms, sampling table or price verified. |
| Uber Movement | **Measured historical status:** Uber launched street speeds in five cities in 2019. A primary academic replication archive says the Movement site was unavailable as of **1 October 2023**; this session's direct open also failed. [authors' archive](https://zenodo.org/records/10479336). Uber's own [announcement](https://www.uber.com/us/en/newsroom/movement-street-speeds/) refused the automated fetch in review, so the 2019 launch and five-city claims are carried over, unverified | Treat as a historical archive, not a dependable live acquisition service. Uber travel times describe the covered fleet, not total population demand. | No accessible live service verified. No official shutdown date/statement found; do not turn “unavailable by October 2023” into a claimed formal termination date. |

**Academic/public releases [measured availability, modelled where noted]:** MeTS-10 gives segment speeds in **10 cities**, **15-minute** bins, **108–361 days** in 2019–2021; it compares against detectors, and explains coverage/binning differences. It supports road-speed validation, not direct reconstruction of every traveller's OD. NYC TLC publishes pickup/drop-off times and locations, but cautions about accuracy/completeness of supplied FHV records; these are for-hire trips, not all city car demand. TAPAS Cologne is explicitly synthetic activity-derived demand; its page specifies non-commercial conditions and asks users to inform the project. None is a drop-in observed demand file for any city. [MeTS-10 authors](https://arxiv.org/abs/2302.08761), [TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), [DLR scenario](https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html).

**Erik's question, answered [opinion]:** yes, better data on real trips exist, and none is free, complete or simply downloadable for one of our cities. In value order for this project: a licensed mobile or probe OD sample; a base-year regional model; survey microdata; then counts. E5 in §7 shows why counts come last.

### EU and Sweden: usable does not mean unrestricted

**Measured regulatory guidance:** Sweden's IMY says truly anonymous information falls outside GDPR, but anonymisation itself is processing governed by GDPR; pseudonymisation remains personal data. Synthetic data is outside GDPR only if no personal data remains and the originals cannot be reconstructed. Hashing plate/device IDs is therefore not sufficient evidence of anonymisation. [IMY, updated October 2026](https://www.imy.se/verksamhet/dataskydd/innovationsportalen/vi-guidar-dig/vi-hanterar-bara-anonymiserade-personuppgifter-da-kan-vi-val-bortse-fran-gdpr/).

**Measured EU guidance:** EDPB connected-vehicle guidance discusses ePrivacy consent for access to terminal information, narrow necessary-service exceptions, a GDPR legal basis for subsequent processing, purpose-specific consent and restrictions on further processing. Permission to provide navigation is not automatically permission to sell location histories for a different purpose. [EDPB guidelines, version 2.0 of 9 March 2021](https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-012020-processing-personal-data-context_en); the review opened the guideline page, the paragraph references are the original report's and were not re-read.

**Recommendation [opinion]:** prefer licensed aggregate OD/time tables with documented expansion, suppression and uncertainty; retain licence/version/provenance alongside outputs. For identifiable traces, require controller/processor roles, legal basis, permitted research/reuse, retention and deletion, security and any transfer/DPIA review before ingestion. This session did **not** determine Swedish telecom-secrecy exceptions, ethical-review applicability to a particular project, current camera rules, or a legal entitlement to ANPR records. No vendor privacy claim was independently audited. Do not describe any proposed personal-data purchase as legally cleared.

**Cost conclusion [opinion]:** begin with public aggregate statistics and an existing licensed demand model if available. Commercial OD might save more work than it costs, but this research found no defensible like-for-like EUR/SEK price. A purchase decision needs a city/date/resolution-specific quote and sample validation; there is no substantiated “€X buys accurate Stockholm OD” number here.

## 2. Activity-based versus trip-based: choose structure, not a brand

**Measured definitions:** activity-based models represent daily sequences with activity location, duration and start time, joined by trips. MATSim repeatedly executes, scores and replans agent plans, with selection from remembered plans and mutation. ActivitySim exposes daily activity-pattern, tour-frequency and trip components. These address different layers from a lane-level traffic kernel. [VALFRAM](https://jasss.soc.surrey.ac.uk/19/3/5.html), [MATSim terminology](https://matsim.org/docs/userguide/terminology.html), [ActivitySim documentation](https://activitysim.github.io/activitysim/v1.0.4/index.html).

| System | Verified role / primary source | Project implication [opinion] |
|---|---|---|
| MATSim | **Modelled framework:** plan execution, scoring and replanning; experienced plan utility drives selection. [Developer guide](https://matsim.org/docs/userguide/terminology.html) | Borrow daily-plan memory and adaptive assignment; an initial population/demand prior is still necessary. It does not observe missing trips for us. |
| ActivitySim | **Provider/open-source specification:** activity-based travel behaviour software, distributed without charge, including tour/trip models. [Project documentation](https://activitysim.github.io/activitysim/v1.0.4/index.html) | Candidate upstream demand generator; network skims and calibration remain separate work. Its tour-based structure is not a microscopic traffic engine. |
| SimMobility | **Modelled framework:** integrated long-, mid- and short-term models; pre-day schedules, within-day choice and day-to-day feedback. [MIT authors' framework](https://web.mit.edu/cami/Public/CLA_SimMobility_Framework_TRB_2016.pdf) | Strong architecture reference for separating demand, learning and physical motion; too large a dependency to recreate just to repair assignment. |
| Sampers | **Agency specification:** Swedish multimodal passenger-demand system; regional-model documentation uses tours and survey estimation. [Trafikverket](https://bransch.trafikverket.se/tjanster/system-och-verktyg/Prognos--och-analysverktyg/Sampers/), [regional estimation](https://bransch.trafikverket.se/contentassets/ef39a7c8e2964def82ee114d4d3798b5/2024/sampers-4---skattning-av-regionala-efterfragemodeller-implementationsdokumentation-2024-04-02.pdf) | Seek compatible base-year OD/purpose/mode tables. Calling it simply a four-step model misses its tour structure; calling it a full second-by-second activity scheduler also overstates it. |
| TAPAS | **Developer specification:** DLR agent-based demand model; Cologne demand is generated from population, habits and infrastructure. [Code](https://github.com/DLR-VF/TAPAS), [scenario](https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html) | Natural source of daily demand compatible with the SUMO ecosystem. Check scenario-specific licence and calibration; synthetic demand is not measured truth. |
| Visum | **Provider specification:** supports activity-based demand, households/persons/tours/trips and simulation-based assignment. [PTV](https://www.ptvgroup.com/en/products/ptv-visum) | A platform that can host several methods, not one uniquely defined trip-based competitor to ABM. No price or independent accuracy guarantee verified. |
| Aimsun | **Provider specification:** supports stochastic route choice and DUE; DUE can add paths and redistribute flow with MSA/WMSA/gradient methods. [Assignment note](https://www.aimsun.com/technical-notes/connecting-centroids-to-multiple-sections/), [hybrid note](https://www.aimsun.com/technical-notes/hybrid-macro-meso-simulation-in-aimsun-next/) | Primarily relevant as assignment/loading reference here; it does not resolve the absence of an OD prior. No price verified. |

### What evaluations actually establish

**Modelled comparison, independent academic thesis:** a TU Delft production-model comparison reports aggregate deviations of **2% activity-based, 6% tour-based, 15% trip-based** against Statline-derived totals; richer models were more sensitive to training inputs. This is a limited trip-production comparison, not evidence of those errors for whole-network congestion forecasts, nor a head-to-head test of the seven products above. [Original thesis, summary and production-model assessment](https://repository.tudelft.nl/file/File_b3c4b06d-4949-4588-ac0f-34812bddced6?preview=1). The server refused connections during review, so these numbers are carried over, unverified.

**Measured-versus-modelled academic validation:** Hwang et al. compared FEATHERS Seoul outputs with smartcard and navigation data rather than just the estimation survey. Agreement varied spatially; low network provision/less attractive land uses produced systematic discrepancies, especially in public transport. Their comparison excluded children and regular work commutes because of data limitations. This supports independent multi-source validation, not universal ABM superiority. [Authors' manuscript, conclusion](https://e-space.mmu.ac.uk/617926/1/Hwang%20et%20al._2017_TBS.pdf). The manuscript redirected to a repository handle that returned nothing during review, so this is carried over, unverified.

**Modelled calibration, commissioned rather than independent:** Sampers 4's Skåne exercise moved from **43%** of targets within target intervals to roughly **55–60%** after three global iterations; it explicitly discusses uncertain survey targets rather than demanding exact fit. These are calibration results, not out-of-sample forecast accuracy. [WSP/Trafikverket method report §5.2](https://bransch.trafikverket.se/contentassets/ef39a7c8e2964def82ee114d4d3798b5/2024/kalibreringsmetod-for-sampers-4---wsp-2022-11-14.pdf).

**Opinion:** use an activity/tour representation because it constrains impossible schedules and ties morning outbound trips to later activities and return journeys. Start with tour-consistent trip tables; do not require a complete ABM before introducing assignment. No credible independent, common-data, common-network, out-of-sample ranking covering MATSim, ActivitySim, SimMobility, Sampers, TAPAS, Visum and Aimsun was verified. Vendor capability pages cannot establish such a ranking.

## 3. OD estimation from counts: a good fit can be a wrong city

### Identifiability and inflation

**Modelled mathematical example:** for fixed route proportions, counts satisfy `y = A q + ε`. With 100 zones, excluding intrazonals, there are **9,900 OD cells per time interval**. Two hundred independent count observations impose at most 200 independent constraints: the nullspace has dimension at least **9,700** before extra information. More repeated counts need not add rank. Congestion makes `A` depend on demand and assignment rather than curing the information deficit. This is an illustrative rank calculation, not a Stockholm measurement; the bi-level formulation and distinction between fitting counts and recovering demand are demonstrated in the [original DODE comparison](https://arxiv.org/abs/2202.00099).

**Opinion, constructive example:** one 1,000-vehicle flow that crosses counters A and B yields `(1000,1000)`. Two separate 1,000-vehicle flows each crossing only A or only B yield the same counts with twice as many trips. Conversely, favouring very long routes through many counters can understate trip totals or inflate vehicle-kilometres. Count fitting is not inherently inflationary: direction depends on route support, priors, objective and congestion response. The example explains the ambiguity; it is not an empirical twofold-error claim. The same [DODE paper](https://arxiv.org/abs/2202.00099) shows fitted counts with wrong demand, but only for its machine-learning surrogates: they “reproduce the arc counts well but are in no way similar to the ground-truth demands”.

**Measured code observation:** Stockholm's script constructs four candidate random walks per counted edge, attempts up to 60 extensions per direction, avoids revisiting edges, and uses random length thresholds of 3–12 km. It balances route weights for **300 iterations**, separately for **06–18, 18–22, 22–06**, then chooses departure hours uniformly within each band. Its incidence matrix counts route passages irrespective of the time needed to reach each counter. It labels all vehicles passenger proxies, and explicitly says the route fit is not simulated validation. These are exact implementation observations, not assertions that the data's units are wrong. [Inspected primary script](file:///home/erikf/.t3/projects/cars/scripts/stockholm/demand.py).

**Opinion/hypothesis for Stockholm:** this construction can produce arbitrary origins, destinations, activity purposes and route lengths, with no return-tour constraint or congestion-consistent timing. A poor capacity/route pool can then leave demand trapped. Test this alongside lane/turn connectivity, priorities, signals, vehicle mix and count units. It is not yet verified that OD inflation caused Stockholm's gridlock. The prior project record also flags junction-model discrepancies, so demand should not absorb all error. [Project session record](https://brain.erikfrankling.duckdns.org/e/built-cars-gpu-traffic-simulator-matching-sumo-berlin-24-h-i).

### How well it really works

**The honest position: almost nobody can check.** OD flows are unobservable on real networks “except from closed highway systems”, which is why benchmarks use synthetic test beds. [Antoniou et al. 2016, abstract](https://upcommons.upc.edu/entities/publication/2c776acb-593d-4b4b-abec-a004b0b1f086) So most published success is either synthetic or on motorways, and fit to counts stands in for truth elsewhere. [Cascetta et al. 2013](https://www.iris.unina.it/handle/11588/552094) is the motorway case with real data; its page returned 403, so its results are not used here.

| Evidence | Finding | Grade |
|---|---|---|
| [Marzano, Papola & Simonelli](https://tristanconference.org/system/tristan-vi/cd-content/Papers/123Marzano.pdf) (TRISTAN version of the TR-C 2009 paper) | With 870 OD pairs and 208 links, r = 4.94 unknowns per independent equation, and using *all* link counts, correction is “always very poor”. With 208 OD pairs, r = 1.08, results are “satisfactory” except for strongly random errors. They conclude the method “may lead to significant biases in the practice”. Dynamic counts help only with assumptions limiting how OD varies over time. | Modelled, laboratory, known truth |
| [DODE comparison](https://arxiv.org/abs/2202.00099) | See table below. Gradients recover demand with sensors everywhere; surrogates fit counts with wrong demand. | Modelled |
| [Ma & Qian](https://arxiv.org/pdf/1901.09266), three years of real data | Link-flow R² of 0.87, with cross-validation on a route-choice matrix, not against true OD. | Measured counts; OD itself unverified |
| [UK TAG M3.1, May 2026](https://assets.publishing.service.gov.uk/media/6a033d074fb0713aa63ea802/tag-m3-1-highway-assignment-modelling.pdf), §3.3.3, §8.3, Table 5 | Matrix estimation “should not be allowed to make significant changes to the prior matrices”, it cannot create trips in zero cells, and limits are cell slope 0.98–1.02 with R² over 0.95. Where validation cannot be met inside those limits, report a lower standard. | Government guidance |
| Prototype E5, §7 | 3.7% noise from random seed, 25.3% from a different day. A prior with zone-pair correlation 0.70 cannot be told from truth on counts. An unregularised fit moved correlation from 0.70 to 0.57. A uniform prior fit improved count error from 88% to 41%, with correlation 0.25. A 10% trip sample reached 0.85 with no counts. | Modelled |

**Conclusion [opinion]:** counts validate; they do not identify. They can correct a total, and check a prior against independent sites. They cannot find the OD. A calibration that moves far from a good prior to fit counts is more likely to be wrong than right. Where a repo script fits only counts, as `scripts/stockholm/demand.py` does, treat its OD as unknown.

### Estimators and best practice

| Approach | What primary evidence supports | What to use here [opinion] |
|---|---|---|
| Cascetta / generalized least squares | Cascetta, Inaudi and Marquis (1993) combine counts with old matrices/surveys, distinguish simultaneous and sequential estimates, and test against known motorway OD. The publisher blocked the review's fetch, so this is carried over, unverified. [Original publisher abstract](https://pubsonline.informs.org/doi/10.1287/trsc.27.4.363) | Weight the prior and observation errors; do not minimize only count residuals. A motorway with known OD is not proof of identifiability in a sparse urban network. |
| Structure-preserving / activity factors | Cantelmo, Qurashi, Prakash, Antoniou and Viti incorporate trip chains into a Kalman state-space estimator, jointly adjusting related trips and using morning information to predict later demand; tested on toy and larger networks. **Modelled improvement.** [Authors' manuscript](https://orbilu.uni.lu/bitstream/10993/40090/1/ISTTT23_2018%20Cantelmo%20et%20al%20FV.pdf) | Couple outbound and return legs; preserve productions, attractions and activity durations. The original advice to estimate factors first was not supported by E5, where they did not beat a cell fit with a prior pull. |
| Bilevel simulation-based estimation | The DODE comparison nests SUMO's mesoscopic assignment inside demand estimation. Assignment-matrix gradients recover demand best, RMSE 1.25–1.34, against SPSA 2.03–9.02 and ML surrogates about 9.6. That favourable result assumes sensors on 100% of arcs, error-free counts, 4 fifteen-minute slices and an artificial network, so it says little about real sparse sensing. **Modelled.** [Original study](https://arxiv.org/abs/2202.00099) | Alternate a sufficiently converged inner assignment with small outer demand changes. Compare low-dimensional SPSA against a sparse sensitivity method; do not assume neural networks are more accurate. |
| Bayesian / state-space | The chain-aware Kalman method explicitly uses prior structure and observations recursively. [Authors](https://arxiv.org/abs/1910.00400) | Represent uncertainty in factors and counts; use ensemble approximate posteriors, not a claim to recover individual trips. Posterior uncertainty is conditional on the model and prior. |
| Sparse OD | Menon et al. propose fine zoning, sparse regularisation and evaluation on **held-out link flows**. [Original author-hosted manuscript](https://akmenon.github.io/papers/od-estimation/od-estimation-paper.pdf) | Sparse corrections to a prior or grouped factors are safer starting points than assuming most real OD cells are zero. Regularisation selects among explanations; it does not create evidence. No numerical error guarantee transferred here. |
| Computational graphs / differentiable assignment | Ma, Pi and Qian (2020) represent multiclass dynamic OD and assignment on computational graphs; they use approximate link-time sensitivities and tree cumulative curves. [Authors' full manuscript](https://ira.lib.polyu.edu.hk/bitstream/10397/88227/1/Ma_Estimating_multi_class.pdf) | Record provenance from OD/departure cohort to link/time observations. This is more informative than independent per-counter multiplicative corrections. |
| Recent differentiable physical models | Seo's 2026 UNsim uses a link-transmission model at Δt 33.3 s, near-deterministic logit dynamic user optimum route choice, and reverse-mode AD. Its Chicago-Sketch toll experiment has about **2,500 links, 1 million vehicles, 3 hours, 15,000 variables**. v3 reports a good solution in **3,000 iterations, about 40 minutes**; the full run is **10,000 iterations, 8,373 s** on an NVIDIA GH200 with 96 GB, at 0.2 s forward and 0.6 s reverse per evaluation. **Modelled/preprint, not an OD-recovery benchmark.** [Original preprint, v3](https://arxiv.org/pdf/2604.11380v3) | Potential coarse calibration/surrogate stage. It is not evidence that discrete WGSL lane changes, sorting, insertion and gridlock handling are directly differentiable. |

**Recommendation [opinion, superseded in detail by §8.8]:** minimize a composite loss over *simulated passage-time* counts, speeds/travel times, and survey/tour summaries, with uncertainty weights, robust residuals, prior divergence, smooth temporal factors and hard structural constraints. Keep sensor outliers separate from demand changes. Penalise movement away from a plausible prior, but allow previously unobserved OD with explicit small positive support; a structural zero must mean impossible, not merely unobserved.

**Scale calculation [modelled]:** 1,000 zones × 999 destinations × 96 quarter-hour departure bins gives **95,904,000** OD-time cells, about **384 MB** for just one float32 array. A dense map from these cells to 10,000 sensors × 96 observation bins needs about **368 TB** of float32 values, before classes or paths. This is arithmetic, not a benchmark. Use sparse path incidence, coarse factors, active OD support and windowed observations; assess effective sensitivity rank, not merely the number of counters. Computational-graph/tree methods are a relevant design precedent. [Ma et al.](https://ira.lib.polyu.edu.hk/bitstream/10397/88227/1/Ma_Estimating_multi_class.pdf).

**Diagnostics [opinion]:** audit vehicles/hour versus vehicles/band, weekday versus annual mean, direction, dates, road matching and duplicate counters before fitting. Track total trips, vehicle-km, mean trip length, production/attraction marginals and each factor's bound hits. Refit from several priors: similar held-out counts but wildly different OD means non-identifiability. Use synthetic recovery experiments with known injected OD, and check gradients against finite differences in a small network before trusting large estimates. See the holdout emphasis in [Menon et al.](https://akmenon.github.io/papers/od-estimation/od-estimation-paper.pdf).

## 4. What real people do: route choice, departure time and navigation apps

Three distinct mechanisms get mixed up. Route equilibrium means no driver can gain by switching route for the same departure. Departure-time adaptation trades travel time against arriving early or late. Day-to-day learning is the process that may or may not reach those states; the TRB primer stresses that unconverged model output is not the same thing as real disequilibrium, and that real learning can converge, cycle or behave chaotically depending on assumptions. [TRB DTA Primer, "Disequilibrium versus nonconvergence"](https://onlinepubs.trb.org/onlinepubs/circulars/ec153.pdf)

### Measured: people do not take the shortest path, but they are close

| Finding | Number | Grade and limit | Source |
|---|---:|---|---|
| Trips exactly on the modelled shortest-time path | **34%** of all trips, **13.5%** of commutes | Measured GPS routes against a modelled shortest path, Minneapolis–St. Paul, 2008-era. Before phone navigation was common. | [Zhu & Levinson 2015](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0134322) |
| Same, allowing 10% non-overlap | **40%** of all trips, **21.7%** of commutes | Same | Same |
| Chosen route's excess time over the shortest | Under **30 s** for about **50%** of trips; under **5 min** for almost **90%** | Same. 5 min is one fifth of the 24-minute mean commute there. | Same |
| Repetition day to day | "most travelers follow the same route during commute trips on successive days" | Measured GPS, same region; abstract read | [Tang et al. working paper](https://ideas.repec.org/p/nex/wpaper/multiday.html) |

**What this means for the model [opinion]:** real traffic is a boundedly rational equilibrium, not a strict one. Drivers settle on one route and tolerate small losses, so a target relative gap of zero is wrong for a realistic run. The same data also say something reassuring: the spread around the shortest time is small. An equilibrium with a tolerance of roughly 30 s to a few percent is a defensible first model of real flows. That tolerance is my reading of one pre-smartphone city, not a measured behavioural constant.

### Measured: navigation apps and intervention experiments

**Google's 10-city experiment [measured, by Google].** Over six months, a switchback design in 10 US cities added a cost to about 100 congested segments **per city** (81–120, [Table 1](https://www.nature.com/articles/s44284-026-00443-x/tables/1)), 1,012 in total. The abstract's "~100 highly congested road segments across 10 major US cities" reads as 100 overall; the body and table show otherwise. **Under 2%** of observed trips were rerouted. Rerouted trips got routes projected about **30 s** slower on average. Median effects: about **+2%** speed on targeted segments, **+3.30%** in Atlanta and **+4.56%** in Los Angeles, **+0.35%** on all affected segments (**+0.50%** in peaks), and **−0.69%** trip travel time for trips through affected segments. The affected set covers about 80% of traffic in each city. All authors are or were affiliated with Google Research, outcomes come only from Google mobility data, and the authors flag that long-run induced demand could erode the gain. An author correction only fixed Atlanta highway route numbers. [Nature Cities, Arora et al. 2026](https://www.nature.com/articles/s44284-026-00443-x), [correction](https://doi.org/10.1038/s44284-026-00480-6)

**What this shows and does not show [opinion].** It proves real drivers respond to app guidance at scale, and that a small shift on near-equal alternatives produces a measurable network effect. It does not give the share of drivers who follow guidance: the paper says compliance is in its Supplementary Information, which I did not open.

**Swedish self-report [measured, non-probability].** VTI's survey of 1,890 drivers recruited on Facebook and Instagram, 84.1% men, mean age 62.8, reports navigation use for **30.2%** of the time when commuting or on known roads and **75.7%** on unfamiliar roads. The authors say the sample is probably skewed. This describes stated use by this sample. It is not a Swedish live-rerouting share. [VTI PM 2024:8](https://vti.diva-portal.org/smash/get/diva2%3A1846883/FULLTEXT01.pdf)

**Route concentration [modelled].** A Pisa group simulated Florence, Milan and Rome with real GPS trips and route suggestions from real services. Routes from different services overlap 70–97%. Up to an adoption of about 25–50%, route diversity rises slightly; at 100% adoption it falls **3.8–14.3%** by city and service. Only the [2024 preprint](https://arxiv.org/html/2407.20004v1) was read. Press pages describe a 2026 Nature Communications version, which I could not open.

**Metropolitan rerouting [modelled].** Mobiliti's San Francisco Bay Area run has 19 million trip legs. At 60% eligibility **317,000** legs (2.8% of eligible) reroute, at 100% **374,000** (2%). Validation favoured the 60% run. A rerouted trip saves 16 minutes on average at 100%, against a baseline of free-speed routes. Those are effects relative to a poor baseline, not what a real driver gains relative to a habitual route. [Chan et al. 2023, Table 2 and §4](https://escholarship.org/content/qt43r1046c/qt43r1046c.pdf)

**Not verified.** Search results quoted compliance figures such as 46% stated versus 88% and 31% revealed, and 50% in an Amsterdam trial, but the [Springer page](https://link.springer.com/article/10.1007/s42421-024-00099-w), the Aalto record and the TU Delft report were blocked when opened. Those numbers are therefore not used as evidence. No representative present-day compliance rate for real drivers was verified for any country.

### Measured: departure time moves a little, and schedule costs are not universal

| Study | Finding | Grade |
|---|---|---|
| [Karlström & Franklin 2009](https://ideas.repec.org/a/eee/transa/v43y2009i3p283-296.html), Stockholm trial | "most people choose a departure time within 15 min both before and during the trial"; some peak spreading, mainly later. Toll-cordon car drivers switched to transit 15 percentage points more than others. | Measured panel; abstract read |
| [Kreindler 2024 / NBER w30903](https://www.nber.org/system/files/working_papers/w30903/w30903.pdf), Bangalore field experiment with GPS | Peak charges moved departures about **3–4 minutes** earlier before the peak. Route charges raised detour use **27 percentage points**, persisting after charges ended. No effect on number of trips. Estimated value of time 609 INR/h, early schedule cost 552 INR/h (91% of VOTT, higher than Small 1982), late 344 INR/h (about 56%). | Measured experiment plus structural estimates; one megacity |
| [Small's review](https://www.economics.uci.edu/files/docs/workingpapers/2014-15/14-15-06.pdf) of the standard bottleneck model | Small (1982) is often summarised as β/α = 0.5, γ/α = 2. | Secondary summary of an estimate; original paper not opened |
| [Kreindler, same paper](https://www.nber.org/system/files/working_papers/w30903/w30903.pdf) | Deadweight loss of peak congestion is 5.9% of non-free-flow commuter cost in his model, against 50% in the bottleneck benchmark, because schedules are inflexible and the delay curve is moderate. | Modelled with measured parameters |

**Together [opinion].** A commuter's departure time is much stiffer than the classic bottleneck model implies. Route is the main short-run release valve, departure time second, and trip suppression small in these two studies. So departure shift in the model must be small (the ±15-minute step in the spec) and must never be used to make impossible demand fit.

### Measured: what happens after a big shock

The collapse of Minneapolis's I-35W bridge removed the usual route of about 140,000 daily trips; "it took several weeks for the network to re-equilibrate". [Zhu et al., abstract](https://experts.umn.edu/en/publications/the-traffic-and-behavioral-effects-of-the-i-35w-mississippi-river/) A review of over 60 case studies of capacity reduction found great variability and, excluding exceptional cases, overall reductions of **16%** of traffic on treated roads or areas. [Cairns et al. 1998, TRID abstract](https://trid.trb.org/view/484127) So real demand has some give on a timescale of weeks, and a same-day en-route model cannot represent it.

## 5. Why simulated cities gridlock when real ones mostly do not

Erik's point holds, with one amendment: real cities do collapse, just rarely. Olmos et al. study six cities, opening with real mega-jams of tens of hours, and find three traffic states and a collapse at a city-specific number of commuters. Their demand and travel diaries are measured; the network dynamics are modelled, including a calibrated Melbourne DTA. [PNAS 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6294880) Empirically, urban regions have a reproducible critical accumulation: over 40 cities, network topology explains about 90% of its variation. [Loder et al. 2019](https://www.nature.com/articles/s41598-019-51539-5), and the first field evidence is [Geroliminis & Daganzo's Yokohama experiment](https://its.berkeley.edu/publications/existence-urban-scale-macroscopic-fundamental-diagrams-some-experimental-findings-0). Real cities live just below that point. The ways a simulation falls over it, in order of how strong the evidence is:

| Cause | Evidence | Grade |
|---|---|---|
| **Broken supply** | TAPAS Cologne ships with `--scale 0.3`: "Due to the above problems with the simulation network ... This reduces the demand to 30% of the realistic value to avoid network-wide traffic jams". Its page lists missing turn lanes, unjoined junctions, invented signal programs and "no DUE". It also says "we even have not tested the data, completely". 30% is a workaround for those defects, never a measured capacity of Cologne. | [Developer statement](https://sumo.dlr.de/docs/Data/Scenarios/TAPASCologne.html) |
| **Our own kernel, on Berlin** | BeST carries about 58% of the counted traffic, yet the cars run gridlocks from 17:00 with 23,715 teleports, while published SUMO on the same demand does not. Too much demand cannot be the cause. | [Local audit](03-berlin-forensics.md), modelled against measured |
| **Empty-network routing and no assignment** | SUMO warns that "all vehicles take the fastest path under the assumption that they are alone in the network", and that run time is dominated by "jammed" early iterations. E3 below reproduces the effect. | [SUMO documentation](https://sumo.dlr.de/docs/Demand/Dynamic_User_Assignment.html); modelled |
| **Reacting too hard** | Rerouting everyone to yesterday's best road can be worse than not rerouting at all. E1 below measured this: gridlock with no way back. | Modelled |
| **Invalid trips** | 46.45% of Stockholm's scheduled trips contain a reversal onto the opposite edge. | [Local census](02-stockholm-why-overloaded.md) |
| **Inelastic insertion** | Simulated vehicles depart whatever happens. Real drivers shift a little in time, change route, or skip the trip, as in §4. | Opinion resting on §4 |
| **Teleports as a pressure valve** | SUMO's default gridlock wait is 300 s and it notes a teleport removes the blockage. Our Berlin day ran with `--time-to-teleport 120 --ignore-junction-blocker 20`, tighter than the default, so its results already include that release. | [SUMO](https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html), [local script](file:///home/erikf/.t3/projects/cars/scripts/berlin_day.sh) |
| **Driver behaviour at blocked junctions** | Real drivers squeeze, yield out of turn and clear boxes in ways car-following rules do not. Whether this matters here is untested. | Opinion, see [human driving report](05-real-human-driving.md) |

**Order to test [opinion]:** fix supply first, then routes, then demand. Reducing demand first can hide all the others, which is what TAPAS openly did and what any fitted scale factor would silently do.

## 6. What fast GPU simulation makes possible — and what already exists

| Prior work | Verified result and grade | Relation to this project [opinion] |
|---|---|---|
| MOSS toolchain | **Modelled/provider-research:** GPU microscopic simulation plus learned OD generation from public geographic data. [Authors](https://arxiv.org/abs/2405.12520) | Fast simulation and generating plausible demand are established research directions; generated OD still needs local truth. |
| MOSS optimization benchmark | **Modelled:** reports **84.09 Hz**, **2,464,950 vehicles**, **88.92×** versus its best CityFlow baseline, with optimization experiments in four cities. [Authors](https://arxiv.org/abs/2406.10661) | Hardware, scenario, time step and physical model differ. Do not compare its Hz directly with cars' vehicle-updates/s. |
| LPSim | **Modelled:** reports **2.82 million trips in 6.28 minutes** on one GPU and **9.01 million in 21.16 minutes** on two. [Authors](https://arxiv.org/abs/2406.08496) | Prior art for GPU metropolitan traffic propagation/assignment infrastructure. A throughput result alone does not show converged behavioural equilibrium. |
| Mobiliti | **Modelled:** mesoscopic distributed simulation of rerouting and large parameter sweeps. [Authors](https://escholarship.org/content/qt43r1046c/qt43r1046c.pdf) | Routing infrastructure and sensitivity sweeps are useful precedents; distinct physical fidelity and CPU/HPC architecture. |
| UNsim | **Modelled/preprint:** automatic differentiation through aggregate network loading and endogenous dynamic route choice; a good toll solution in 3,000 iterations, about 40 minutes (v3), the full 10,000 in 8,373 s, on a 96 GB GPU. Apache-2.0. [Authors](https://arxiv.org/abs/2604.11380), [code](https://github.com/toruseo/UNsim) | Precedent for many iterations and gradients; not microscopic calibration truth. Its route choice is instantaneous, so it is not a day-to-day equilibrium. A forward pass of 0.2 s suggests a coarse warm-start stage, untested. |
| Ma–Pi–Qian; Cantelmo et al. | **Modelled:** computational-graph dynamic OD and trip-chain-aware online Kalman estimation. [Ma](https://ira.lib.polyu.edu.hk/bitstream/10397/88227/1/Ma_Estimating_multi_class.pdf), [Cantelmo](https://arxiv.org/abs/1910.00400) | Support a calibrated offline prior plus rolling updates of a small state, rather than rebuilding millions of independent OD values online. |

**Proposals [opinion]:** use replicas for independent stochastic seeds, demand/capacity hypotheses, parameter perturbations, ensemble calibration and simulation-based inference. An ABC or likelihood-free calibration can condition tour factors on counts, trip-time quantiles and survey summaries, but computational affordability and posterior calibration still need demonstration. Sequential Monte Carlo or an ensemble filter can update departure-intensity factors using real-time counts; hidden queues and signal state must be included to avoid attributing every discrepancy to new demand.

**Crucial dependency [opinion, tested in E2]:** iteration `k+1` needs costs from `k`; replicas cannot execute dependent iterations at once. At a fixed budget of 48 simulated days, 8 replicas × 6 iterations gives a gap of 7.6% against 1.3% for 1 × 48. Replicas are for seeds, candidates and scenarios. No verified publication was found demonstrating this exact Rust/WGSL replicated-world assignment/calibration architecture, nor city-scale, calibrated microscopic simulation-based inference on one RX 7900 XT. These are proposed experiments, not novelty claims.

## 7. What the prototype settled

[`scripts/demand_proto.py`](scripts/demand_proto.py) is about 1,100 lines of self-written Python with no SUMO code: a spatial-queue simulator with finite storage, spillback and FIFO head blocking on a 12×12 synthetic grid (528 links, 24,000 trips is "100% load"; OD tests use 8×8, 224 links, 8,000 trips), a time-dependent router and the full loop. **Everything in this section is modelled.** It settles design questions about the loop. It says nothing about any real city and it is not the cars kernel. Raw results are in [`demand-proto/`](demand-proto/); [`scripts/demand_proto_report.py`](scripts/demand_proto_report.py) rebuilds the tables and figure.

![Left: relative gap per iteration for four update rules at 150% load. Rerouting everyone stays near 85%, while a capped share with cost memory falls to about 1%. Right: mean trip time against demand for empty-network routes and assigned routes. Assigned routes stay near 3 to 7 minutes until about 225% load, while empty-network routes reach 32 minutes.](fig/demand-assignment.png)

### E1. Update rule: the single most important choice

| Rule, at 150% load, 2 seeds, 30 iterations | Peak gap | Iterations until gap stays below 5% / 2% | Gap on unseen seeds | Mean trip | Unfinished |
|---|---:|---:|---:|---:|---:|
| Everyone switches to the best route | 92% | never / never | 84% | 1,557 s | 1,467 |
| Share set by gap, uncapped (`min(1, 2·rel)`) | 72% | never / never | 18% | 232 s | 0 |
| Logit over 5 remembered routes, half of travellers (shape of duaIterate, not its code) | 40% | never / never | 12% | 212 s | 0 |
| MSA, `1/(k+2)` | 40% | 8 / never | 2.6% | 192 s | 0 |
| Fixed 10% | 40% | 4 / never | 2.5% | 191 s | 0 |
| Capped `min(0.15, 2·rel)` | 40% | 3 / never | 2.1% | 191 s | 0 |
| Bounded: 20% chance, only if saving beats max(30 s, 5%) | 40% | 3 / never | 1.6% | 191 s | 0 |
| **Capped, plus cost memory 0.3** | **40%** | **6 / 15** | **1.4%** | **191 s** | **0** |

At 200% load the difference is starker. The uncapped rule gridlocks and stays there: gap 95%, 24,369 of 48,000 trips unfinished. The capped rule with memory completes everything at 222 s, with gap 7.1% on unseen seeds after 25–30 iterations. For comparison, empty-network routes at 200% average 1,158 s. **Decision: capped share 15%, gap-proportional, cost memory 0.3.** Reacting hard is what creates a gridlock that no later iteration can undo. Also, the gap measured in-sample understates: 0.9% in-sample was 1.4% on unseen seeds at 150%, and 3.9% was 7.1% at 200%. Always report it on seeds the loop did not see.

### E3. Why the simulated city gridlocks: routes, and the teleport mask

| Load | Empty-network routes: mean trip, unfinished | Assigned routes: mean trip, unfinished | Assigned plus 300 s teleports: mean trip, unfinished, teleports |
|---:|---:|---:|---:|
| 100% | 181 s, 0 | 181 s, 0 | 181 s, 0, 0 |
| 150% | 338 s, 0 | 194 s, 0 | 194 s, 0, 0 |
| 175% | 650 s, 0 | 214 s, 0 | 214 s, 0, 0 |
| 200% | 1,158 s, 0 | 257 s, 0 | 257 s, 0, 0 |
| 225% | 1,923 s, 0 | 432 s, 0 | 431 s, 0, 39 |
| **250%** | 3,397 s, **26,519** | 2,190 s, **17,910** | 1,835 s, **0**, 2,985 |
| 275% | 4,079 s, 34,623 | 2,885 s, 25,950 | 4,440 s, 3,517, 10,961 |
| 300% | 4,411 s, 43,073 | 3,783 s, 38,021 | 8,123 s, 31,546, 22,185 |

Three things follow:

1. **Routes decide delay well below collapse.** At 200% load, assignment cuts the mean trip 4.5 times. This is the mechanism behind "people do get to work every day".
2. **Assignment barely moves the collapse point here.** It lies between 225% and 250% with either route set. Once real capacity is exceeded, route choice cannot help. That is the honest limit of Erik's intuition.
3. **Teleports hide gridlock completely at the threshold.** At 250%, turning on 300 s teleports turns 17,910 unfinished trips into zero. The only trace is 2,985 teleports, about 5% of 60,000 trips. A clean-looking completion count means nothing with teleports on.

**The gap misleads inside gridlock.** At 250%, 300% and 350% load the assigned gap falls, 30%, 20% and 16%, because when everything is stuck, all routes are equally bad. Gap may only be read together with the ledger.

### E0. What the GPU must output

Three estimators of per-bin edge time, built only from aggregate counters, predicting whole-trip times (mean bias, mean absolute error, correlation):

| Estimator | 100% load | 200% load | 300% load, 44% finished |
|---|---|---|---|
| Queue: `free flow + Q/rate`, `Q = N_in(t−ff) − N_out(t)`, `rate = max(outflow, 0.25·capacity)` | +7 s, 14 s, 0.985 | +3 s, 24 s, 0.990 | −6 s, 35 s, 0.952 |
| Little: vehicle-seconds ÷ vehicles leaving | +1 s, 7 s, 0.994 | +7 s, 24 s, 0.838 | 0 s, 30 s, 0.924 |
| Differencing cumulative curves | +31 s, 35 s, 0.902 | +16 s, 31 s, 0.986 | +136 s, 157 s, 0.448 |

**Decision:** queue estimator. It needs only entered and left per edge per bin, so no per-vehicle log. My first choice, differencing cumulative curves, was badly biased and I rejected it. Cost is per edge: this toy has one queue per edge, so what per-lane queues in a real microsimulator do to this estimator is not tested.

### E2. Replicas: more iterations beat more replicas

Same budget of 48 simulated days, 2 seeds, gap on unseen seeds and mean trip:

| Replicas × iterations | 150% load | 200% load |
|---:|---:|---:|
| 1 × 48 | 1.3%, 190 s | 6.3%, 219 s |
| 2 × 24 | 1.4%, 190 s | 8.0%, 223 s |
| 4 × 12 | 3.3%, 191 s | 24.9%, 277 s |
| 8 × 6 | 7.6%, 196 s | 47.1%, 393 s |

**Decision:** assignment iterations are sequential because iteration k+1 needs costs from k, and iteration count is what matters. Spend replicas on what really is parallel: unseen-seed evaluation, calibration candidates and scenarios. Two replicas per iteration come close to twice the iterations (1.4% against 1.3%, 8.0% against 6.3%) and halve the routing work, so use K=2 only if the GPU runs two worlds for under about 1.3 times one (unmeasured, see §8.11).

### E4. Departure-time adaptation: useful, and unstable near collapse

Route-only continuation against route plus departure adaptation, with 5-minute shifts within −60/+15 minutes of desired arrival:

| Load, schedule weights (early, late, per unit travel time) | Share changing per iteration | Route only: mean trip, unfinished, schedule cost | Route + departure: mean trip, unfinished, schedule cost |
|---|---:|---|---|
| 200%, 0.5 / 2.0 | 15% | 222 s, 0, 415 | 237 s, 0, 345 |
| 200%, 0.5 / 2.0 | 5%, consistent start | 222 s, 0, 415 | 235 s, 0, 306 |
| 200%, 0.91 / 0.56 | 15% | 222 s, 0, 568 | 240 s, 0, 344 |
| 200%, 0.91 / 0.56 | 5%, consistent start | 222 s, 0, 568 | 229 s, 0, 262 |
| 225%, 0.5 / 2.0 | 15% | 275 s, 0, 473 | 655 s, 0, 1,389 |
| 225%, 0.5 / 2.0 | 5%, consistent start | 275 s, 0, 473 | 1,371 s, **7,961**, 3,554 |
| 225%, 0.91 / 0.56 | 15% | 275 s, 0, 591 | 1,858 s, **12,372**, 2,792 |
| 225%, 0.91 / 0.56 | 5%, consistent start | 275 s, 0, 591 | 501 s, 0, 657 |

Below collapse, schedule cost falls 17–54% for a small rise in travel time, the expected trade. Mean shifts are 5–7 minutes, near Bangalore's 3–4 minutes, though the step limit partly forces that. **Near collapse it made every run worse than route-only, and two of four gridlocked.** Departures bunched: the peak quarter-hour grew 4–10%. A lower share did not fix it reliably. With 15-minute steps almost nobody moves (0–0.5%), because the schedule penalty dwarfs the saving; that run is not among the kept result files.

**Decision:** departure time goes last, behind a guard that rejects any batch which worsens the ledger or total generalised cost. This also corrects the concern in the original report: in this toy, departure adaptation does not mask impossible demand. It breaks first.

### E5. How well counts recover OD, with known truth

8×8 network, 16 zones, 7 half-hour slices, 1,792 cells; 25% of links held out; counts in 15-minute bins. Truth is gravity times lognormal(0, 0.6) noise on zone pairs. **Noise floor: the same truth on another random seed scores 3.7% WAPE on link counts; another sampled day scores 25.3%.**

| Prior | Link coverage | Method | Count error, train / held-out | Total trips ÷ truth | Zone-pair RMSE ÷ mean | Zone-pair correlation |
|---|---:|---|---:|---:|---:|---:|
| Gravity, right total | any | none | 29–33% / **25.8%** | 1.00 | 0.63 | 0.70 |
| Gravity, right total | 30% | cell fit, no prior pull | 25.5% / 33.1% | 1.09 | 0.98 | 0.57 |
| Gravity, right total | 30% | **cell fit with prior pull** | 25.3% / **25.4%** | 1.00 | 0.59 | 0.75 |
| Gravity, right total | 60% | cell fit with prior pull | 25.9% / 24.9% | 1.00 | 0.57 | 0.77 |
| Gravity, right total | 30% | zone and time factors only | 25.7% / 29.9% | 0.98 | 0.66 | 0.67 |
| Gravity, 30% too high | any | none | 40–42% / 38.8% | 1.30 | 0.73 | 0.70 |
| Gravity, 30% too high | 10% | cell fit with prior pull | 29.1% / 34.3% | 1.22 | 0.68 | 0.71 |
| Gravity, 30% too high | 30% | cell fit with prior pull | 25.5% / 25.9% | 1.12 | 0.61 | 0.75 |
| Gravity, 30% too high | 60% | cell fit with prior pull | 25.1% / 26.6% | 1.09 | 0.57 | 0.77 |
| Uniform (no information) | any | none | 92–93% / 88.3% | 1.00 | 0.89 | none |
| Uniform | 30% | cell fit, no prior pull | 34.7% / **40.7%** | 1.03 | 1.01 | **0.25** |
| 10% probe sample + gravity | any | **none, no counts at all** | 30–31% / 26.0% | 0.97 | **0.49** | **0.85** |
| 10% probe sample + gravity | 60% | cell fit with prior pull | 25.9% / 26.9% | 1.00 | 0.44 | 0.88 |
| 2% probe sample + gravity | 30% | cell fit with prior pull | 26.5% / 27.3% | 0.98 | 0.62 | 0.75 |

What this says:

1. **Counts cannot distinguish a mediocre prior from the truth.** A gravity prior with zone-pair correlation 0.70 already scores 25.8% against a day-to-day floor of 25.3%. No count fit can significantly improve that.
2. **An unregularised fit makes OD worse while improving the fit.** Pair RMSE 0.63 → 0.98, correlation 0.70 → 0.57, and held-out error rises from 25.8% to 33.1%. That is the shape of the Stockholm generator.
3. **A good-looking fit can be a wrong city.** From a uniform prior, count error falls from 88% to 41% while zone-pair correlation stays at 0.25.
4. **Counts do fix the total,** given enough coverage: a 30% scale error falls to 22% with 10% of links, and to 9–12% with 30–60%.
5. **A 10% sample of real trips beats 60% link coverage.** Pair correlation 0.85 with no counts at all, against 0.77 with counts on 60% of links. Combined, 0.88. This is the toy's answer to Erik's first question: real trip samples are worth far more than more counters. A 2% panel adds little at this size, because each cell has very few trips. The result is about value per data type in one toy; the panel was unbiased, which real panels are not.
6. **Zone and time factors did not beat cell fit with a prior pull.** They were sometimes worse and left total at 0.77 from a uniform prior. The original report's preference for low-dimensional factors is not supported here. It remains a scaling option for cities with too many cells.

### E6. Telling impossible demand from bad assignment

Grid split by a river with 1 or 3 bridges, two-hour window. "Cut bound" is trips that must cross minus bridge capacity × window, for each direction:

| Network, trips | Single-commodity max-flow shortfall | Directional cut shortfall | Unfinished after assignment | Mean trip |
|---|---:|---:|---:|---:|
| 3 bridges, 16,000 | 0 | 0 | 0 | 156 s |
| 1 bridge, 8,000 | 0 | 0 | 0 | 383 s |
| 1 bridge, 12,000 | 0 | 0 (3,217 and 3,339 against 3,600) | 0 | 1,104 s |
| **1 bridge, 16,000** | **0** | **1,581** | **7,569** | 3,331 s |
| No river, 16,000 | 0 | n/a | 0 | 137 s |

**Decision:** directional cut checks, not max flow. A static single-commodity max flow never flagged the impossible case, because it lets northbound and southbound trips cancel against each other's destinations. The cut bound flagged the one impossible case and gave no false alarm in the other 7 river cases. Its 1,581 is smaller than the 7,569 unfinished, and that difference is useful: it separates vehicles that cannot cross from vehicles caught in the spillback they create.

### E7. En-route rerouting: for surprises, not for normal days

Morning peak at 175% load, equilibrium routes from assignment, epochs every 300 s, rerouting only if the saving exceeds max(60 s, 10%):

| Navigator share | Normal day: mean trip, reroutes per navigator | Incident, 4 busiest links at 20% capacity for 45 min: mean trip, p95, reroutes per navigator |
|---:|---:|---:|
| 0% | 207.3 s, 0 | 636 s, 2,534 s, 0 |
| 10% | 206.8 s, 0.011 | 562 s, 2,303 s, 0.21 |
| 30% | 205.9 s, 0.011 | 428 s, 1,810 s, 0.16 |
| 60% | 205.4 s, 0.009 | 296 s, 969 s, 0.13 |
| 100% | 204.6 s, 0.008 | 256 s, 673 s, 0.11 |

**Decision:** en-route rerouting adds 1.3% on a normal day over equilibrium routes, so leave it out of baseline days. It is worth 2.5 times in mean trip time for an incident. No herding appeared even at 100%, but that is with the hysteresis on and in one incident on one toy network.

## 8. Build spec

Status: **proposal, not implemented or calibrated.** Constants marked *(E#)* come from the prototype and must be re-checked on a real network; they are starting values. Facts about the code were read in this checkout. Build it in the order of §8.12.

### 8.1 Files

| New or changed | Purpose |
|---|---|
| `crates/cars-core/src/assign/population.rs` | `Traveller`, plans, route arena, CSV load/save |
| `crates/cars-core/src/assign/costs.rs` | Per-edge, per-bin cost table from GPU counters |
| `crates/cars-core/src/assign/route.rs` | Time-dependent ALT A*; port of [`demand_routebench.rs`](scripts/demand_routebench.rs) |
| `crates/cars-core/src/assign/update.rs` | Route and departure update rules, gap |
| `crates/cars-core/src/assign/ledger.rs` | Conservation ledger, verdicts |
| `crates/cars-core/src/assign/cuts.rs` | Cut family, bound check |
| `crates/cars-core/src/assign/calibrate.rs` | Sparse assignment matrix, cell fit, splits |
| `crates/cars-core/src/world.rs`, `sim.rs` | `World::rewrite_demand`, `Sim::reset`, `Sim::write_demand`, en-route patching |
| `crates/cars-core/src/shaders/step.wgsl` | Wider edge accumulator, see 8.4 |
| `crates/cars-cli/src/bin/assign.rs` | CLI: `assign --scenario x.toml --iters 30 --out dir` |

No new function-local arrays in WGSL. All struct changes need their `#[repr(C)]` twin. Keep `Sim::run` submissions short, keep 3 GB VRAM spare, run one GPU job at a time.

### 8.2 Inputs

`scenario.toml` names and hashes these. Keep raw files unmodified, and store unit, date range, direction, and day type next to each.

| File | Columns | Required |
|---|---|---|
| Network | SUMO `.net.xml`, read by `Net::load` | Yes |
| `zones.csv` | `zone, wkt, population, jobs` | For the prior |
| `access.csv` | `zone, edge, weight` (edges with `passenger` allowed, in the zone) | For the prior |
| `travellers.csv.gz` | see 8.3 | Yes |
| `counts.csv` | `site, edge, dir, t0_s, t1_s, day_type, vehicles, class, source` | For calibration |
| `speeds.csv` | `edge, t0_s, t1_s, speed_mps, n_obs, source` | For validation |
| `od_sample.csv` | `zone_o, zone_d, t_bin, trips, source, sampling_share` | Optional, very valuable *(E5)* |
| `cuts.csv` | `cut, edge, dir`; rivers, rail, ring roads | Optional, auto-generated too |

Reject at load: counts whose direction was inferred by halving two-way flow unless `dir=split_assumed` is set, and annual-mean sources with `day_type` missing. Stockholm's 16,698 "Skattad trafik" features are estimates and must carry `source=estimated`; they cannot be validation. [Audit](02-stockholm-why-overloaded.md)

### 8.3 Prior demand

**Hard rule: build the prior without any count that will be used for validation.** WebTAG's practice supports this ordering: matrix estimation "should not be allowed to make significant changes to the prior matrices in order that the validation standards are met". [TAG M3.1, May 2026, §3.3.3 and Table 5](https://assets.publishing.service.gov.uk/media/6a033d074fb0713aa63ea802/tag-m3-1-highway-assignment-modelling.pdf)

Use the highest rung available, and record which:

1. A licensed base-year OD by purpose and time, such as Sampers regional tables. Needs Erik (§9).
2. Mobile-network or probe OD, scaled against survey totals. Commercial; needs Erik.
3. Otherwise, built from public statistics:
   - **Trip ends:** population and jobs per zone. Car-driver trip rate by purpose from the travel survey. People are not cars, so use driver trips, not person trips.
   - **Work trips:** doubly constrained to SCB's municipality-level commuting matrix, with a gravity deterrence `exp(−c/τ)` fitted so that trip length matches the survey distribution.
   - **Other purposes:** gravity against land use, with the survey length distribution.
   - **Time:** desired arrival drawn from the survey's start-time histogram per purpose. This replaces invented hourly bands.
   - **Tours:** every home→work trip gets a linked return, with duration drawn from the survey.
   - **Other classes, explicit:** trucks, external and through traffic (from cordon counts or a national model), buses as fixed lines.
4. For testing only: reuse an existing file's OD and departures, discarding its routes, and set desired arrival to depart + free-flow time + 10%. This runs on BeST and LuST today.

```rust
struct Traveller {
    id: u32, class: u8, o_edge: u32, d_edge: u32,
    desired_arrival_s: f32, depart_s: f32, earliest_s: f32, latest_s: f32,
    tour: u32, tour_seq: u8,          // linked legs shift together
    plan: [u32; 5], n_plan: u8, cur: u8, // indices into a deduplicated route arena
    vtype: u32, cell: u32,            // OD-time cell for calibration
}
```

Keep up to 5 routes per traveller, matching SUMO's default limit. [SUMO](https://sumo.dlr.de/docs/Demand/Dynamic_User_Assignment.html)

**Checks before any simulation:** total trips, vehicle-km, mean trip length, productions and attractions per zone against sources; share of routes with an immediate reversal must be 0 (Stockholm's is 46.45%); every OD reachable for its vehicle class.

### 8.4 GPU output

Today `edge_acc` holds per edge four `u32`: samples, distance in 1/8 m, entered, teleports leaving the edge (the shader comment says "spare", but [`step.wgsl`](file:///home/erikf/.t3/projects/cars/crates/cars-core/src/shaders/step.wgsl) line 1289 counts teleports). Insertions are not counted as entered. `EdgeLog` keeps per-edge detail only for replica 0.

Change:

1. Widen `edge_acc` to 8 `u32` per edge: `samples, dist8, entered, teleports, left, inserted, spare, spare`. `left` increments when a vehicle leaves a normal lane and on arrival. `inserted` increments in `try_insert`, and `entered` is not touched, so `N_in = entered + inserted`. Update `sim.rs` buffer size (`n_edges * 32`), `take_edge_acc` (`[u32; 8]`), `metrics.rs`, and the four index expressions in `step.wgsl` (lines 1248, 1289, 1930, 1931).
2. Drain at every 300 simulated seconds: `sim.run` to the bin edge, then `take_edge_acc`. Store for all replicas, normal edges only.
3. Add `n_requested` per edge per bin on the CPU from `depart_step`. Insertion delay comes from `inserted` against that.
4. `GpuTripOut.depart_step` holds the actual insertion step, and `metrics.rs` computes travel time from it, so **reported travel time omits insertion waiting**. The ledger uses `arrive_step − trip.depart_step` instead. Trips that never arrive have `flags & 1 == 0`.
5. Add a per-replica teleport total by summing slot 3. `C_TELEPORTS` is global.

Memory: Berlin has 71,324 normal passenger edges; 288 bins × 16 kept bytes per edge is 329 MB per replica-day on the CPU.

### 8.5 Costs and routing

Per bin `b` of 300 s, per edge *(E0)*:

```
ff      = length / (lane speed × mean speed factor of class)
Q       = max(0, N_in(t_mid − ff) − N_out(t_mid))      // interpolated in the cumulative curves
rate    = max(left_b / 300, 0.25 × cap_e)              // cap_e = highest 5-min outflow over the day, floor 0.1 veh/s
cost[e][b]  = ff + Q / rate
wait[e][b]  = insertion delay on e from requested against inserted curves
C[e][b] = 0.7 × C_prev[e][b] + 0.3 × cost[e][b]        // memory (E1)
```

Vehicles still in the network at the end must not disappear from `Q`. For an edge with no traffic, `cost = ff`. Enforce FIFO from the last bin backwards: `C[e][b] = min(C[e][b], 300 + C[e][b+1])`. For replicas, average the counters first.

Routing is time-dependent A* on the edge graph from `net.conns` per vClass, as `router.rs` builds it, with ALT bounds from 16 farthest-point landmarks using free-flow costs. Every cost is at least free flow, so the bound stays admissible. The cost of a path is `wait[o][bin(dep)]` plus each edge's `C` at the arrival time. Add to it tolls, if any, and a 10 s turnaround penalty to keep reversals out.

**Measured on the real Berlin graph, one CPU thread on the agent-capped PC, synthetic costs up to 3× free flow, 20,080 real ODs** ([bench](scripts/demand_routebench.rs)):

| Search | Time per query | Edges settled | Mean cost |
|---|---:|---:|---:|
| Plain time-dependent Dijkstra, early stop | 2.5–4.0 ms | 10,378 | 676 s |
| **ALT, 16 landmarks** | **1.7 ms** | **2,146** | **675.8 s** |
| ALT, 4 landmarks | 2.1 ms | 3,512 | 675.8 s |
| Full tree | 17.5–32 ms | 71,133 | n/a |

The graph has 71,324 edges and 148,263 turns. Timing ran under other agents' load, so treat these as pessimistic but noisy. Do not cache trees: among 2,248,884 Berlin trips there are 2,175,971 distinct edge ODs and 1,168,868 distinct origin-and-15-minute-bin pairs, so sharing gains almost nothing.

### 8.6 The assignment loop

```
routes = free-flow route per traveller              // or warm start
for k in 0..K:
    simulate day, teleports OFF, abort on stall     // 8.9
    update C from counters
    sample 15% of travellers; for each:             // cap (E1)
        best, c_best = route(o, d, depart, C)
        c_cur = evaluate(current route, depart, C)
        rel = (c_cur − c_best) / c_cur
        accumulate gap numerator and denominator    // the sample doubles as gap estimate
        with probability min(1, 2·rel / 0.15): switch to best, adding it to the plan
    if converged(): break
```

Sampling first and accepting after gives the same switching probability as `min(0.15, 2·rel)`, while routing only 15% of trips.

**Convergence is three conditions together (opinion):**

1. **Gap:** `RG = Σ(c_cur − c_best) / Σ c_cur`, the standard DTA definition, on the sample. [TRB Primer](https://onlinepubs.trb.org/onlinepubs/circulars/ec153.pdf) Target **RG < 2%** on seeds the loop has not seen. Static-model practice asks for 0.1% [(TAG M3.1 §3.4.12)](https://assets.publishing.service.gov.uk/media/6a033d074fb0713aa63ea802/tag-m3-1-highway-assignment-modelling.pdf); no such standard was found for stochastic microsimulation. Below about 1–2% the toy hits noise and a realistic tolerance (§4) anyway.
2. **Stability:** under 1% change in total generalised cost and held-back screenline flows over 5 iterations. [SUMO's own check](https://sumo.dlr.de/docs/Demand/Dynamic_User_Assignment.html), the relative deviation of mean travel time, is this kind of test, and can pass while routes still churn.
3. **Ledger clean:** unfinished under 0.1% at the clearance horizon, teleports off. **Gap is meaningless otherwise** *(E3)*.

Budget 30 iterations, then 100 if progress continues. Exhausting the budget reports `not converged`, never equilibrium. For a behavioural run after convergence, switch to the bounded rule, so that residual gap reflects the 30 s tolerance in §4.

**Reset without rebuild.** `World::build` is too slow to call per iteration on a city, and pipelines need not recompile. Add `Sim::reset` (clear vehicle, queue, TLS, counter, trip-out buffers, reset globals to `step: u32::MAX`, re-upload initial slots) and `World::rewrite_demand`. All buffers already have `COPY_DST`. `routes` stores absolute edge IDs per replica, `edge + edge0`, so preallocate 1.3× and refuse to overrun. Queues are per departure edge and `queue_trips` must be sorted by `depart_step`, because `insert` stops at the first future trip; re-sort when departures change. `bestlanes::depart_mask` is cached per `(route, vtype)` and must be recomputed for new routes only.

### 8.7 Departure time

Only after route convergence, and only with a guard *(E4)*:

- Start from a consistent schedule: `depart = desired_arrival − experienced travel time`, if no observed departure exists.
- Cost: `travel + β·max(0, t* − arrival) + γ·max(0, arrival − t*)`, in seconds of travel time. Sweep `(β, γ)` over `(0.5, 2)` [(Small, as summarised)](https://www.economics.uci.edu/files/docs/workingpapers/2014-15/14-15-06.pdf) and `(0.91, 0.56)` [(Kreindler, Bangalore)](https://www.nber.org/system/files/working_papers/w30903/w30903.pdf). Neither is a Swedish value. Use class-specific windows, with tight ones for work and school.
- Each iteration, 5% of travellers try ±5 minutes, within `earliest..latest` (default −60/+15 min). Accept if the generalised saving exceeds 30 s. Tours shift together.
- **Guard:** snapshot before each batch. If unfinished rises by more than 0.1% of trips, or total generalised cost rises over 2%, restore the snapshot, halve the share and retry. After two rejections stop and report `departure adaptation unstable at this load`.
- Track the share at the window edge. A rising share means demand wants to leave the window: report it as evidence of excess demand, never widen the window.

### 8.8 Calibration and held-out validation

**Split first, and freeze.** Cluster counters within 500 m along connected roads, then assign whole clusters, and whole corridors where named: 60% train, 20% selection, 20% final test. Hold out at least one peak. Open the final test once. Keep date-compatible sources only.

**Noise floor first.** From real data, compute WAPE between the same site's counts on comparable weekdays in different weeks. **That is the floor. Stop calibrating when selection-set error reaches it.** In the toy, the prior was already there *(E5)*.

**Update, from a converged assignment:**

1. Walk each traveller's route through `C` to get passage times, and build sparse `A` (rows: site × 15-minute bin; columns: cell = zone pair × 30-minute slice), normalised per trip in the cell. Counts are compared at the passage time, not the departure time. Stockholm's fit ignores that.
2. Cell fit with prior pull, 200 sweeps *(E5)*:
   ```
   m = (Σ_i A_ij · y_i / (A q)_i + λ · q0_j / q_j) / (Σ_i A_ij + λ)
   q_j ← q_j · m,    λ = 0.5 passes per trip, tune on the selection set
   ```
3. `q ← 0.5 q + 0.5 q_new`. Add or remove travellers by Poisson-sampling the change per cell. Prefer cloning a traveller in the cell with its plan, keep tours whole, and treat a cell with zero prior as a structural zero unless `od_sample` supports it.
4. Re-assign with 8 warm iterations (toy: 3), then repeat. Up to 3 outer rounds.

**Guards, reported with every result**, using TAG M3.1 Table 5 as the default limit on change from prior: cell regression slope 0.98–1.02, intercept near zero, R² over 0.95; trip ends slope 0.99–1.01, R² over 0.98; trip length mean and standard deviation within 5%; sector-to-sector within 5%. WebTAG's instruction when these conflict with the flow criteria is to respect the limits and report the lower validation standard. So do that. Also track total trips, vehicle-km, peak accumulation and bound hits. Refit from at least two priors: similar held-out error with different OD means the OD is unidentified, and the report must say so.

**Validation report:** held-out WAPE and GEH against the floor, count criteria from TAG Table 2 (within 100 veh/h under 700 veh/h, 15% from 700–2,700, 400 veh/h above, and GEH < 5, in over 85% of cases, which WebTAG says is for confidence, not a target to force). Also speed-profile error against probe speeds, queue onset and clearance, with seeds shown as bands. Never quote training error as validation.

**Not tested, worth trying later:** [Cadyts](https://www.strc.ch/2009/Floetteroed.pdf) adjusts plan choice probabilities from counts by a Bayesian update, without changing OD. It is GPLv3 and Java, so reimplement the idea, not the code. [UNsim](https://arxiv.org/abs/2604.11380) (Apache-2.0) could give fast gradients on a coarse model, but its route choice is instantaneous-DUO logit, not day-to-day equilibrium, and I did not check how far OD calibration has been shown on it.

### 8.9 Detecting impossible demand

**Teleports are off for every run that counts.** `time_to_teleport: 0.0` already disables them. A teleport-on run may be kept as a labelled diagnostic. Also leave `ignore_blocker` off, unless the run is explicitly labelled a workaround. Note that the Berlin day used `--time-to-teleport 120 --ignore-junction-blocker 20`.

**Ledger**, per replica at each drain: `requested = arrived + active + waiting_to_insert + not_yet_due`. Assert exact equality; `removed` or `teleported` must be 0 in a counted run. Count insertion delay in cost. Trips unfinished at the end are charged their elapsed time, never dropped. Horizon: demand end + 2 hours (or, for a day run, 26 h).

**Stall abort**, because jammed iterations dominate run time [(SUMO)](https://sumo.dlr.de/docs/Demand/Dynamic_User_Assignment.html): if active > 0 and no vehicle arrives for 15 simulated minutes, stop the day, and use its counters as they are. The queue estimator charges those edges their queues. This is a costed outcome, not a failure of the loop.

**Verdict ladder, in this order:**

1. **`network_suspect`:** gridlock at ≤50% of expected demand, or first persistent queue on a link with isolated discharge under half nominal. Fix the network. Do not touch demand.
2. **`demand_exceeds_cut`:** for a cut family, trips that must cross in a sliding 1-hour window exceed `capacity × window + free storage`. Cut family: river and ring cuts from `cuts.csv`; bisections of zone clusters at k = 2, 4, 8, 16; and cuts built from the current run, the boundary of each connected set of persistently queued edges. Directed. Use measured discharge per link from isolated tests, not nominal. Report the cut, the shortfall and its window. **Single-commodity max flow is not sufficient** *(E6)*.
3. **`unstable_or_unconverged`:** no cut violated, yet gap does not fall or the ledger fails. Try lower cap and more iterations. Only this outcome is a loop problem.
4. **`feasible_but_congested`:** cuts hold, ledger clean, delays high. A valid result, as with 12,000 trips over one bridge *(E6)*.
5. **`incompatible_with_observations`:** feasible in the model, but no variant reproduces observed clearance. Report the conflict; do not call the demand impossible.

**Never** scale demand, widen departure windows, delete trips or raise teleports to pass. A scale factor is permitted only as a labelled diagnostic. The output table is `verdict.json`: requested, unfinished, teleports, first queues, cuts violated, and minimum unmet demand.

### 8.10 En-route rerouting

Optional, off for baseline days, on for incident scenarios *(E7)*.

Every 300 simulated seconds, pause at the bin edge. Read `cur` for `lane, route_i, route_end, trip, replica`, about 7 MB for 40,000 active vehicles. For the navigator share (sweep 0, 30%, 60%, since no real share is known), compute instantaneous `tnow[e] = ff + occupancy/rate` from the last bin and find a route from the vehicle's **next** edge.

Patch only if the saving is above max(60 s, 10%). Rules for legality:

- **Keep the vehicle's next edge fixed.** Its lane choice already targets that turn, so the new suffix starts there.
- Skip vehicles on internal lanes. `route_i` advances only when a link has no via lane.
- Append `[current edge, next edge, suffix…]` to a route arena at the end of `routes`, via `queue.write_buffer`, then set that vehicle's `route_i` and `route_end` at its current index in `cur`. Sorting cannot move it during a pause. Set `F_BEST_DIRTY` so `lc_best` recomputes.
- Size the arena from E7: at most about 0.2 reroutes per navigator per day, at a mean 48 edges per route. Berlin at 60%: 2.25M × 0.6 × 0.2 × 48 × 4 B = 52 MB.

Validate on an incident in SUMO with `--device.rerouting.*` as a reference run; SUMO's period defaults to 0, off. [SUMO](https://sumo.dlr.de/docs/Demand/Automatic_Routing.html)

### 8.11 Runtime on one RX 7900 XT

**Correcting the input assumption.** "About 50 million vehicle updates per second" is the plateau at very many vehicles. The Berlin day is not on it. From the frozen run: mean 21,833 running vehicles × 86,400 steps ÷ 147.5 s = **12.8 million updates/s**, or 1.7 ms per step, of which roughly 0.4 ms is per-vehicle at the plateau rate. The other 1.3 ms or so goes on scanning 257,426 lanes and on dispatch. [Run summary](berlin-snapshot/day_summary.csv), [run script](file:///home/erikf/.t3/projects/cars/scripts/berlin_day.sh). Per-day cost is therefore mostly per-lane, not per-vehicle, for a city.

| Step, Berlin-sized | Time | Basis |
|---|---:|---|
| Simulate one day, `dt` = 1 s | 150 s | Measured |
| Doubling vehicles to true counts | +35 s | Calculated at the plateau rate, 22,000 × 86,400 ÷ 54 M/s |
| Routing 15% of 2.25M trips | 142 s on 4 threads, 71 s on 8 | 337,000 × 1.7 ms, measured per query |
| Cost table, route rewrite, upload | 10–30 s | Estimate, not measured |
| **One iteration** | **about 5–6 min** | Sum |
| 30 iterations | **2.5–3 h** | Sum; toy needed 15–30 |
| 3 calibration rounds × 8 warm iterations | 2–2.5 h | Sum |
| Final evaluation, 8 seeds | Up to 20 min | Additive upper bound |
| **Whole pipeline, one city** | **about 5–6 h: overnight** | Sum, unmeasured as a whole |

For comparison, BeST's route file header shows duaIterate step 103 with `gawron.beta 0.9, a 0.5`, 900 s weights and at most 5 alternatives. [Local route file header](file:///home/erikf/projects/personal/cars-data/best/berlin.rou.gz) At the 7 h per day the project's brain record quotes for published SUMO, 103 iterations would be about 30 days, if they were microscopic runs, which I could not establish.

**VRAM (calculated from struct sizes, not measured):** per Berlin replica about 0.95 GB at capacity 100,000: routes 434 MB, trips 144 MB, trip outputs 72 MB, lane-state 97 MB, link-state 146 MB, vehicles 67 MB. Peak running was only 38,439, so the 600,000 capacity used in that run is far too large. With 17 GB usable, that allows **about 8 Berlin replicas with margin.**

**Replica time is unknown: first thing to measure.** GPU work was forbidden in this session. Time K = 1, 2, 4 Berlin replicas for one hour of day at 08:00. If per-step cost is per-lane, K replicas cost K times. If dispatch dominates, much less. Thesis sweeps show large replica counts are efficient on small networks (252 replicas at 55.7 M updates/s), but that does not transfer. Use K=2 in assignment only if the cost is under about 1.3×.

Replicas during assignment are per iteration only. Each replica's routes differ only if each has its own arena. To average counters, `edge_id = r × n_edges_per_replica + e`, as `EdgeLog` already does.

### 8.12 Build order and acceptance tests

| Milestone | Build | Passes when |
|---|---|---|
| 0 | Port the prototype's tests; `Sim::reset`, wider `edge_acc`, ledger | Same seed gives identical counters to `World::build` after reset; ledger balances exactly on LuST and ring; golden and thesis comparisons unchanged |
| 1 | Cost table, ALT router, loop on LuST | Router cost equals plain Dijkstra on 10,000 ODs. Everyone-switches control is worse than capped, as in E1. RG falls below 5% in 15 iterations |
| 2 | Compare with SUMO on LuST | Flows per edge against `DUERoutes` in `cars-data/lust`, correlation over 0.9, mean trip within 5%. Thresholds are my proposal |
| 3 | Berlin with no teleports, replica timing test | Runtime table above confirmed within 50%; evening gridlock either gone or attributed. If still there, junction work comes first. Report which |
| 4 | Cuts and verdicts | River test from E6 on a real bridge subset: flags impossible demand, no false alarm on known-feasible load |
| 5 | Departure time with guard | Guard catches an injected near-collapse run; schedule cost falls below collapse |
| 6 | Real prior, calibration, split | Synthetic recovery first: inject known OD, recover totals to within 10%; then real counts with the noise floor reported |
| 7 | En-route | Incident on LuST compared with SUMO's rerouting device, mean trip within 10% |

Do not start Milestone 6 on Stockholm until reversals are gone and real counts exist. The present source is estimated. Do not treat agreement with training counts at any stage as evidence of a correct city.

## 9. What remains unverified, and what only Erik can do

**Could not open in this review, carried over or unused:** the TU Delft thesis (connection refused), Hwang et al. (repository handle returned nothing), Cascetta 1993 and 2013 (403), the Springer page and Aalto record on compliance (blocked), TU Delft's Amsterdam trial (timed out), Uber's newsroom page (refused), the published Nature Communications version of the Pisa study and Google's Supplementary Information (not reached). TomTom, Replica, Visum, Aimsun and Telia pages opened and match in general, but their product details were only spot-checked. Their use is provider description only.

**Not established:**

- Real-driver compliance with live guidance, in any representative sample, and any Swedish share.
- The right tolerance and the right schedule weights for Swedish commuters. The sources disagree by a large factor (early 0.5 or 0.91 of travel time).
- Replica cost on a city network, and whether K Berlin replicas cost K times one. This needs a GPU timing run.
- How the queue-cost estimator and the 15% cap behave on the cars microscopic kernel. The prototype is a queueing toy on a grid, with one FIFO queue per edge, no turn pockets and no signals beyond capacity. Whether per-edge costs suffice or per-turn costs are needed is unknown.
- That the 2–3× load range in the prototype maps to anything in a real city. Its loads are relative to its own base.
- Quantitative demand error for Stockholm, and the cause of Berlin's evening gridlock. The audit attributes it most likely to our kernel, which this report did not test.
- Legal entitlement to person-linked mobile, probe, connected-car or ANPR data. No project-specific legal claim is made here.

**Only Erik can:**

- **Pick the first target city.** My default is LuST to prove the loop, then Berlin, because real counts and a published comparison exist. Stockholm comes last, until real time-resolved counts exist.
- **Approve data requests or purchases,** and send them, or approve the exact wording. Most useful, in order: a Sampers regional base-year table from Trafikverket; RVU survey microdata from Region Stockholm or Trafikanalys; a sample mobile OD extract with penetration and suppression metadata from Telia; hourly directional counts with dates from Stockholm and from Trafikverket. No account was created and nobody was contacted.
- **Accept licences.** TAPAS Cologne is CC BY-NC-SA, excludes commercial use, and asks users to tell the project.
- **Allow overnight GPU time** for the timing test and first city run.

## Reviewed by Opus

This report was written by another model and reviewed by Claude Opus 5.5 on 2026-11-01. I opened the key sources, corrected the file, deepened §3–5, wrote the prototype and benchmark, and replaced the old §6 with the build spec.

**What held:**

- **TAPAS Cologne at 30%.** The page says exactly that, attributes it to “problems with the simulation network”, lists no DUE, and warns the data is untested. The reading as a workaround, not a capacity finding, is right. Added: about 1.2 million daily trips, and the licence.
- **Mobiliti's rerouting table,** LPSim, MOSS, MeTS-10 and the arithmetic on OD size.
- **Sampers Skåne,** 43% to 55–60%, in the WSP report.
- **Dates and specifications:** Apple 14 April 2022, Google 15 October 2022, Uber Movement unavailable from 1 October 2023, NDW 10–20%, MiD 421,000 people and 218,000 households, GeoLife 182 users, 17,621 trajectories and 91% dense, Telia 250 m and K5, StreetLight's US-only connected-vehicle data, VTI's 1,890 responses.
- **The main advice:** validation held out, no fitting to counts alone, teleports treated as failures, supply before demand.

**What was wrong or misleading, now corrected:**

| Claim | Problem | Now |
|---|---|---|
| Berlin throughput "50 million updates/s" used to build the runtime table | The Berlin day ran at **12.8 million/s**. The table's formula gives 38 s for that load against the measured 148 s, off by 4×. The 50 M plateau needs far more vehicles | §8.11 rebuilt from measured parts |
| Google: "roughly 100 congested segments in 10 US cities" | About 100 **per city**, per body and Table 1, despite the abstract's wording | §4 |
| Google: 2% speed and 0.7% travel time presented without context | Omitted: under 2% of trips rerouted, 30 s detour, and only +0.35% across affected segments | §4 |
| UNsim: "10,000 iterations in about two hours" | That is v1's abstract. v3's says 3,000 iterations in about 40 minutes; the full 10,000 took 8,373 s. Omitted: 96 GB GPU, and route choice that is instantaneous rather than equilibrium | §3, §6 |
| DODE: fitted counts with wrong demand, presented as general | True only of the ML surrogates. Gradients recovered demand, but under 100% sensor coverage and error-free counts | §3 |
| MiD "randomly assigned reporting day" | Not on the cited ministry page | Removed |
| EDPB PDF link | Returned 404 | Guideline page linked |
| Preference for low-dimensional demand factors | E5 did not support it: factors did not beat a cell fit with prior pull | §3, §8.8 |
| Stopping gate of RG < 1% | Too tight for a stochastic run, and gap alone is unsafe: it falls inside gridlock | §8.6 |
| ±15-minute departure steps as first choice | With them almost nobody moves in the toy. 5-minute steps work below collapse | §8.7 |
| Concern that departure time would mask impossible demand | In the toy it did the opposite: near collapse it made every run worse, and two of four gridlocked | §7 E4, §8.7 |

Two of my own first choices also failed in testing: the cumulative-curve cost estimator, and a static max-flow feasibility check. Both are recorded in §7. A review note for the reader: the prototype is one synthetic grid and few seeds. I would trust its orderings, such as capped versus uncapped, more than its numbers.

**What remains unknown:** see §9. The largest open items are replica cost on the GPU, whether the loop's settings transfer from a queueing toy to the microscopic kernel, what share of real drivers follow live guidance, and what the Berlin evening gridlock is.
