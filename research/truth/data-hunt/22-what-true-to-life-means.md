# 22: What "true to life" means, and the benchmark that tests it

Checked 2026-11-02. No GPU was used, no simulator was run and nobody was contacted. Every noise floor below is real data against real data. Scripts and outputs are in [scripts-22/](scripts-22/).

Grades: **MEASURED** means I calculated it from real data, or an earlier report did and I say which. **PROVIDER CLAIM** means an author's or agency's statement in a source I opened. **MODELLED** means simulated or inferred. **UNVERIFIED** means I couldn't open the source. Thresholds are **OPINION** unless a measured floor is given.

## The answer

**A simulation is true to life when one frozen configuration, with no per-scene dials, produces output that real data can't tell apart from another real day. That has to hold at every scale at once, on data it never saw, and through the same kind of instrument that recorded the real data.** Matching one number proves little, because many wrong models can match one number. This is the same problem ecology calls equifinality and climate science calls "right for the wrong reasons". Those fields have the same answer: use many independent patterns at different scales, make each one a filter that can reject a model, and never let a good score on one pay for a bad score on another.

So the benchmark is **a vector with no total**. It has about 70 metrics on five levels. Each is scored against how far real data differs from itself, and each ends in a status. A level is only as good as its worst metric. To compare two versions, nothing may get worse beyond its noise and something must get better beyond its noise. Hill climbing takes the largest gap first. Held-out data sits in months nobody has downloaded, and it only tells you whether you improved.

**I tested the idea with no simulator.** I corrupted real Berlin days in 16 ways, kept one uncorrupted control, and scored them:

- **Network metrics are blind to wrong places.** Shuffling traffic between sites of the same road class changed none of the 12 network-level metrics. 15 finer metrics caught it, by up to 13 times the floor. This is Erik's "the throughput looks right", measured.
- **Published-looking bars are weak.** A model that knows nothing about any road except its class scores 39% hourly error, or 0.50 RMSN (MEASURED). Report 15's "credible" 35% and 0.40 barely beat that. Every network metric therefore also has to beat a null model.
- **Some of report 15's targets are stricter than reality.** One real day catches 67% of another day's jam site-hours, with 33% false alarms, and shares 70% of its top-20 bottlenecks. "Good" there asks for 75%, 25% and 70%.

## Contents

1. [The definition](#1-the-definition)
2. [How other fields stopped right-for-the-wrong-reason](#2-how-other-fields-stopped-right-for-the-wrong-reason)
3. [What traffic guidance gives us](#3-what-traffic-guidance-gives-us)
4. [Learned simulators and Waymo's metric](#4-learned-simulators-and-waymos-metric)
5. [New measurements: the noise floors](#5-new-measurements-the-noise-floors)
6. [Benchmark: how every metric is scored](#6-benchmark-how-every-metric-is-scored)
7. [Benchmark: the metrics](#7-benchmark-the-metrics)
8. [Combining without hiding failures, and comparing versions](#8-combining-without-hiding-failures-and-comparing-versions)
9. [Tuning data and held-out data](#9-tuning-data-and-held-out-data)
10. [Rules against overfitting](#10-rules-against-overfitting)
11. [Sensitivity: which metric identifies which parameter](#11-sensitivity-which-metric-identifies-which-parameter)
12. [Can the benchmark detect failure?](#12-can-the-benchmark-detect-failure)
13. [Build order for the benchmark builder](#13-build-order-for-the-benchmark-builder)
14. [Ranked sources, recommendations, Erik, dead ends, new directions](#14-ranked-sources)

## 1. The definition

`cars` is true to life at a scale when **all five** of these hold. Report each one separately.

1. **Same settings.** One configuration file, one hash, for every scene. A scene supplies only measured inputs: map, signals, demand and arrivals, each labelled as gate rule 3 requires. No driver number varies by scene.
2. **Same instrument.** Simulated data goes through a virtual copy of the real instrument: a point detector, a probe sample, a camera pair or a drone view, with the same filter. Comparing an edge mean with a detector's point mean tests the wrong thing.
3. **Indistinguishable.** The gap between a simulated day and a real day is no larger than the gap between two real days. Where it is larger, that is reported as a failure.
4. **Every scale at once.** Metres, junctions, corridors and network, all in the same run configuration. A pass at one scale can't offset a failure at another.
5. **Unseen data.** The result holds on sites, days and cities never used for tuning, and on witness metrics that were never tuning targets.

This doesn't change `VALIDATION-GATE.md`. It adds levels below the gate's nine checks. The gate's "no overall validated label without all of them" stands.

## 2. How other fields stopped right-for-the-wrong-reason

| Field and source (what I opened) | Their problem | Their fix | What we take |
|---|---|---|---|
| **Ecology.** [Grimm & Railsback 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3223804/), full text. The 2005 *Science* paper wasn't opened | "Models can easily be calibrated to reproduce a single pattern of interest, but potentially for the wrong reasons" | Pattern-oriented modelling: multi-criteria design, selection and calibration. Each pattern is a filter that rejects parameter sets. Weak qualitative patterns count too. Keep secondary predictions as validation. Such models typically have 10–20 parameters | Multi-scale filters, not a fit. **Witness metrics.** A parameter budget |
| **Hydrology.** [Beven 2001](https://hess.copernicus.org/articles/5/1/2001/hess-5-1-2001.pdf), full text. Beven 2006 and Kirchner 2006 were refused | Equifinality: "it is the parameter set that is important", and a value is good or bad only given the others | GLUE: reject non-behavioural models, keep all behavioural ones in prediction | Keep **all** non-implausible settings and report their spread. Don't borrow parameter values one at a time |
| **Hydrology testing.** [Klemeš 1986 as described in the RAT note](https://hess.copernicus.org/articles/25/5013/2021/hess-25-5013-2021.pdf). The original wasn't opened | A split-sample test is necessary but weak | Test hierarchy: independent periods, neighbouring catchments, and **contrasting** periods | The differential test: tune on busy weekdays, test on Sundays and other cities |
| **Hydrology scores.** [Knoben et al. 2019](https://hess.copernicus.org/articles/23/4323/2019/hess-23-4323-2019.pdf) | A score threshold means little: KGE of −0.41 equals the mean-flow benchmark, not 0 | Compare with purpose-specific benchmarks | **Null models** on every network metric |
| **Cosmology, disease.** [Vernon, Goldstein & Bower 2014](https://arxiv.org/pdf/1405.4976), [Andrianakis et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4288726/) | 17 inputs, few runs, an imperfect simulator | History matching: implausibility `I² = |z − E f|² / (Var f + Var ε + Var e)`, where ε is structural discrepancy and e is observation error. Rule out by the maximum, and second and third highest, over outputs. Galform went from 14.9% to 0.039% of input space in 5 waves. "We may find χ(z) is empty, which is a strong warning" | Max, not mean. Declare discrepancy **before** tuning. **An empty set means fix the structure, not the numbers.** That matches Erik's "fix the cause" |
| **Model discrepancy.** [Kennedy & O'Hagan 2001](https://www.asc.ohio-state.edu/statistics/comp_exp/jour.club/kennedy01.pdf), abstract and intro. Brynjarsdóttir & O'Hagan was refused | Fitted parameters absorb structural error | Model the discrepancy explicitly | Calibrated numbers aren't physical facts. Report 05's calibrated Krauss `decel` of 0.33 m/s² is exactly this |
| **Climate.** [Hourdin et al. 2017](https://journals.ametsoc.org/view/journals/bams/98/3/bams-d-15-00135.1.pdf), full text | Tuning to a handful of metrics risks "unphysical behavior in metrics or processes that were not used in tuning, that is, we get some things 'right for the wrong reasons'". Tuning "can also risk masking fundamental problems" | Publish a tuning document with targets. Three levels: parameterisation, component, system. Prefer process-level adjustment | A public **tuning log**. Tune at the lowest level that can measure the thing |
| **Weather verification.** [Roberts & Lean 2008](https://journals.ametsoc.org/view/journals/mwre/136/1/2007mwr2123.1.pdf), [Davis et al. 2006](https://journals.ametsoc.org/view/journals/mwre/134/7/mwr3145.1.pdf) | Grid-to-grid match punishes a nearly right storm twice | Fractions Skill Score over widening neighbourhoods. Object-based attributes: place, size, timing | **Jam location score** with space and time tolerance, plus jam objects with onset and clearance. Report 15 found nobody publishes this for cities |
| **Forecast ensembles.** [Gneiting & Raftery 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf), [Hamill 2001](https://journals.ametsoc.org/view/journals/mwre/129/3/1520-0493_2001_129_0550_iorhfv_2.0.co_2.pdf) | Means hide distributions, and scores can be gamed | Strictly proper scores (CRPS, energy score). "A flat rank histogram… can still be generated from unreliable ensembles" | **CRPS plus rank share**, never rank alone. I reproduced Hamill's warning on Berlin, section 5 |
| **Simulation-based inference.** [Cranmer et al. 2020](https://arxiv.org/pdf/1911.01429), [Talts et al.](https://arxiv.org/pdf/1804.06788), [Hermans et al.](https://arxiv.org/pdf/2110.06581), [Cannon et al.](https://arxiv.org/pdf/2209.01845), [Frazier et al.](https://arxiv.org/pdf/1708.01974), abstracts and method sections | Fast posterior fits that can be overconfident. Under misspecification, Cannon finds "a profoundly deleterious effect" and no fix that works in all cases | Simulation-based calibration: recover known truth on synthetic data | **Twin test**: can the tuner recover a known configuration? Don't trust SBI posteriors while the model is misspecified |
| **Economics ABMs.** [Platt 2020](https://arxiv.org/pdf/1902.05938). Fagiolo 2007 and Cont 2001 were refused | Many ABMs reproduce the same stylised facts with different rules, so the facts don't discriminate. Popular distance methods recovered known parameters less well than surveys suggest, with large flat objective regions | Parameter recovery experiments on known truth | Stylised facts are necessary, not sufficient. Flat regions are expected |
| **Systems biology.** [Gutenkunst et al. 2007](https://journals.plos.org/ploscompbiol/article/file?id=10.1371/journal.pcbi.0030189&type=printable) | Sensitivities spread over many decades ("sloppy"), and parameters stay poorly constrained even with much data | Focus on predictions, not parameter values | Report predictive spread, and don't read tuned values as behaviour |
| **Identifiability.** Brun, Reichert & Künsch 2001, not opened. [FME documentation](https://rdrr.io/rforge/FME/man/collin.html), which cites it | Near-linear dependence between parameter effects | Collinearity index, with "less than about 20" as "identifiable" (documentation's rule of thumb) | Section 11 |
| **Statistics of validation.** [Robinson & Froese 2004](https://digitalcommons.mtu.edu/michigantech-p/6306), abstract only | With "no difference" as the null, "tests are more likely to validate a model if they have low power" | Equivalence tests: "they flip the burden of proof back onto the model" | **A pass needs a confidence bound under the margin.** Not being rejected isn't a pass |
| **Machine learning leaderboards.** [Blum & Hardt 2015](https://arxiv.org/pdf/1502.04585), [Dwork et al. 2015](https://arxiv.org/pdf/1506.02629), [Recht et al. 2019](https://arxiv.org/pdf/1902.10811) | Reusing a holdout adaptively overfits it. Recht adds that large drops on new test sets came from distribution shift, not adaptivity | The Ladder: release a new score only on a significant improvement, rounded to a step. Thresholdout | **Held-out reveal rule**, section 9. Also a warning: a new city will hurt more than a reused test |

**The common shape, in my words:** filter, don't fit. Use noise as the ruler. Keep the set of survivors. Treat an empty set as a verdict on the model. Hold out both data and patterns.

## 3. What traffic guidance gives us

| Source | Useful | Gap |
|---|---|---|
| [FHWA Toolbox III, 2004](https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol3/sect5.htm) (Dowling et al.), PROVIDER CLAIM | Parameters are "often highly correlated", and the analyst "can easily get trapped in a never-ending circular process". So work in order: capacity, then route choice, then system performance. Keep adjustable parameters as few as possible | Global match targets, no real-noise basis |
| [FHWA 2019](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm), PROVIDER CLAIM | Four criteria built on between-day difference: ±1.96σ band for 95% of outputs, ±1σ for two thirds, mean absolute error ≤ BDAE, absolute bias ≤ BDAE/3. Pick a real representative day: a synthetic average day is "not recommended". [Replications](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter6.htm): `N = (t·s/(e·x̄))²`, and if it asks for 20 or more, investigate instead, because it can signal gridlock | The only guidance tied to real variation. Means only, one measure at a time. No held-out rule |
| [MULTITUDE guideline, 2014](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC88526/2014_multitude_guidelines_on-line.pdf) (Antoniou, Barceló, Ciuffo, Punzo and others), full text searched | 19% of practitioners did no calibration. Of those who did, only 55% used guidelines. Models are "often over-parameterized", and most output variance comes from "a handful" of parameters. GEH is "inappropriate for calibration" because GEH 3 or 5 "can be obtained with a multiplicity of parameter combinations". Keep the **distribution** across replications: comparing only averages "produces choices based on partial or biased information". Existing guidelines misuse the term "sensitivity analysis" | Says what's missing, proposes no benchmark. **This report is that benchmark** |
| [Punzo, Montanino & Ciuffo 2015](https://publications.jrc.ec.europa.eu/repository/handle/JRC89193), abstract | On IDM with NGSIM, "the leader's trajectory is considerably more important than the parameters". Three of six parameters were enough | Car following only |
| [Azevedo et al. 2015](https://web.mit.edu/cami/Public/CLA_uncertainty_CLA_TRC_2015_preprint.pdf), full text searched | 101 parameters, grouped screening then full variance analysis: 11 parameters explain almost 90% of output variance, at 55,808 runs instead of 421,888. Poorly fitted trajectories undermine the safety outputs built on them | One motorway |
| [Trafikverket handbook 2014](https://bransch.trafikverket.se/contentassets/32ce05ecc3ac458bb8ecb802e8e2da54/handbok_for_kapacitetsanalys_med_hjalp_av_simulering.pdf), Swedish, sections 2.2, 2.7, 2.8 | Two datasets, one to calibrate and one to validate, to make sure the model isn't only tuned to the calibration data (my translation). A calibrated-only model has limited validity. Always add a sensitivity analysis. Complement squared-error comparison with a t-test or Kolmogorov–Smirnov test | KS and t-tests don't fit our data: millions of autocorrelated ticks reject everything, eight days reject nothing. We use real-against-real distances instead (section 6) |
| [TfL guidelines v4](https://content.tfl.gov.uk/traffic-modelling-guidelines.pdf), as in report 04 | Validation data "should be independent of the build data". Minimum 20 seeds, a continuous range. Saturation flows within 10% | Junction scale |
| UK TAG M3.1, via [report 04](../04-validity-of-traffic-simulation.md), not reopened | GEH<5 on more than 85%, journey times within 15% or 1 minute | Assignment, not behaviour |
| [Calibration Illusion, 2026](https://arxiv.org/pdf/2608.19642), working paper, via report 15's copy | Hidden manual work behind "automatic" calibration. Performance falls with size. Stop-and-go waves are "a distinct qualitative failure where waves degrade to non-existence", unlike throughput | So **wave existence** must be its own metric |
| [Toledo et al.](https://wctrs-society.com/wp-content/uploads/abstracts/istanbul/1361.pdf) (report 15's copies) | Two steps: estimate each model independently from disaggregate data, then calibrate and validate the whole on aggregate data | Matches our levels |
| Toledo & Koutsopoulos 2004, Hollander & Liu 2008, Barceló 2010, Ciuffo's Monte Carlo papers | **Not opened** (Sage, Springer, JRC refused). Nothing here rests on them | |

**Why the traffic field never got further.** Guidance sets match targets for one model and one site. It doesn't ask for one configuration across many scenes, and it rarely compares with real noise. Report 15 confirms that no published city micro model has passed on held-out data.

## 4. Learned simulators and Waymo's metric

[WOSAC](https://arxiv.org/pdf/2305.12032) (paper read, plus the [2025 page](https://waymo.com/open/challenges/2025/sim-agents/)). Given 1 s of history, submit 32 rollouts of 8 s per scene. For each of nine features (speed, acceleration, angular speed and acceleration, distance to nearest object, collisions, time to collision, distance to road edge, offroad; plus traffic-light violation from 2025), fit a histogram to the 32 samples and score the logged future's likelihood. Average the nine with hand-set weights, with collision and road departure doubled in the paper.

**What to borrow:** many rollouts per scene, closed-loop factorised agents, distributions rather than single futures, scoring per feature.

**What it misses:**

| Gap | Evidence | Our answer |
|---|---|---|
| 8 s horizon, no flow, capacity or travel time | Paper; report 21 | Levels 3 and 4, plus the 24 h drift test |
| Time is thrown away: samples are "time-independent" by design. Identical samples at different moments score the same | Paper, section 4.2.1; [Cornelisse 2026](https://daphnecornelisse.substack.com/p/how-to-think-about-human-likeness) | Time-resolved jam and queue metrics |
| Composite is a hand-weighted average, so failures trade off | Paper, equation 3 | No composite |
| Binary event likelihoods: collisions at every step in one rollout barely change the score | Cornelisse, blog, single author; she reads collision and offroad as 25% each, which differs from the paper's doubling. I didn't reconcile them | Rates per km, real-noise floor |
| Label noise in the "truth": 4.2% of trajectories contain a collision, 16.3% an off-road event | Cornelisse's sample of 5,000 scenes | Same real-against-real ruler, and physics separately |
| Collision rate alone can be zero for a static policy, so it isn't realism | Paper itself | Physics plus flow together |
| Rollouts come from the logged start. No insertion or deletion | Paper's future work | Full-day demand |
| Rules score high at this horizon: SUMO 0.653 against SMART 0.751. Scales changed: on 2023's, MVTE 0.645 and logged oracle 0.722 | Report 21 | It doesn't discriminate what we care about |

## 5. New measurements: the noise floors

**Data.** Berlin detectors, May 2019, 239 cross-sections complete on all 8 normal Tue–Thu days, 24 hours. Road classes in that panel: 119 slow urban (free speed under 50), 117 fast urban, **only 3 motorway**. Trajectories come from report 05's caches.

### Network, real day against real day (MEASURED)

56 ordered day pairs. p50, p90 and max across pairs. Hours 06–20 unless stated.

| Metric | p50 | p90 | max | Reading |
|---|---:|---:|---:|---|
| Network total, relative error | 0.9% | 2.3% | 2.8% | |
| Hourly share of day, RMSE, points | 0.09 | 0.13 | 0.14 | |
| AM / PM peak hour error, h | 0 / 0 | 0 / 1 | 0 / 1 | |
| Site-hour median GEH | 1.53 | 1.71 | 1.88 | |
| Site-hour GEH ≥ 5, share | 8.3% | 11.1% | 13.7% | So GEH<5 is 86–92% |
| Site-hour WAPE | 7.3% | 8.6% | 9.4% | |
| Site-hour RMSN | 0.116 | 0.144 | not computed | Report 15 had 0.19 on September 2024, with different sites and QC. **Compute the floor on the exact site list used** |
| Site-hour R² | 0.955 | p10 0.929 | | |
| Site-day total, median error | 2.8% | 3.6% | 4.1% | |
| Site-day total, p95 error | 22% | 32% | 38% | A few sites swing a lot |
| Site day shape, total variation | 0.030 | 0.031 | 0.033 | |
| Class × hour speed, mean abs. error, km/h | 2.6 | 4.8 | 5.3 | Inflated by the 3-site motorway class. An earlier run with two classes split at 55 km/h free speed gave 0.8, 1.5, 1.7 |
| Site-hour speed, mean abs. error, km/h | 3.4 | 3.9 | 4.0 | |
| Site-hour speed, p95 error, km/h | 12.5 | 14.2 | 15.0 | |
| Speed distribution W1, AM / midday / PM, km/h | 0.8 / 0.6 / 0.7 | 1.6 / 0.9 / 1.3 | 2.1 / 1.0 / 1.8 | |
| Rush-hour dip, median error, share of free speed | 0.059 | 0.067 | 0.071 | |
| Jam site-hours, abs. log ratio | 0.07 | 0.16 | 0.21 | About 530 jam site-hours per day at about 120 sites |
| **Jam location, 1 − FSS, exact site and hour** | 0.34 | 0.39 | 0.41 | **FSS 0.66** |
| **Same, ±1 h** | 0.22 | 0.28 | 0.30 | **FSS 0.78** |
| **Same, ±1 h and 1 km** | 0.14 | 0.18 | 0.19 | **FSS 0.86** |
| Jam hit rate / false alarm | 67% / 33% | p10–p90: 59–73% / 28–42% | | |
| Top-20 bottlenecks shared | 70% | p10–p90: 58–80% | | |
| Jam onset, mean abs. error, h | 0.58 | 0.67 | 0.74 | Hourly data, so coarse |
| Jam clearance, mean abs. error, h | 0.78 | 0.93 | 0.99 | |
| Network curve, flow / density nRMSE | 1.7% / 3.5% | 2.4% / 6.2% | 2.6% / 7.3% | |
| Peak density error | 2.5% | 5.7% | 6.8% | |
| Network curve loop area | 92% | 1,560% | 15,900% | **Useless as hourly metric. Dropped.** |

Definitions of jam, FSS and the rest are in section 7. [Full output](scripts-22/noise_berlin.json), [hit rate, nulls](scripts-22/noise_berlin_extra.json).

**Limits.** One month, one city, main-road sites, hourly. A single season understates what the floor would be across a year. Weather on these days wasn't checked. I tried the same for September 2024, but only 5 sites are complete on 6 days, so I threw that result away. A builder should allow missing hours rather than requiring complete sites.

### What a model that knows nothing scores (MEASURED)

Each is scored against a real day, built from the other days. "Class mean" gives every site its road class's average hourly profile, so it has the right network total and day shape and knows nothing else.

| Null model | WAPE | RMSN | R² | GEH<5 | Site-day Spearman | Jam hit | False alarm | Top-20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Network mean profile | 41% | 0.53 | 0.06 | 30% | −0.16 | 10% | 86% | 10% |
| **Class mean profile** | **39%** | **0.50** | **0.18** | **29%** | 0.16 | 10% | 69% | 15% |
| A real other day | 7.3% | 0.116 | 0.955 | 92% | | 67% | 33% | 70% |
| Same site, mean of other days | 5.6% | 0.084 | 0.976 | 95% | 0.995 | 72% | 24% | 75% |

Three things follow.

1. **Report 15's "credible" band is thin.** WAPE ≤35% and RMSN ≤0.40 are only just better than a class mean. Stockholm's audited day, at 66% hourly error (report 16), is further off than Berlin's null, though that compares two cities. Keep "credible", but require it to beat the null by a margin.
2. **Report 15's "good" jam targets exceed the floor.** Hit ≥75%, false ≤25% is better than one real day predicts another, and about what the average of seven real days achieves.
3. **Average-of-seeds cheats.** A mean of other days beats any one real day: RMSN 0.084 against 0.116. So a seed-averaged simulation gets an unfair advantage. This confirms report 04: compare **one replicate against one day**, as FHWA also prefers real days over synthetic means.

### Ticks and junctions (MEASURED)

Acceleration is the speed change over 1 s, jerk the change of that over 1 s, both computed identically on every source. Time gap `T = (spacing − 5 m) / v`. Blocks are TGSIM runs, or 15 min of one recording. W1 is in the metric's own units. This reproduces report 05's numbers: A39 at 25–40 m/s gives −0.69 / +0.62 against its −0.71 / +0.64, and I-90/94 at 5–10 m/s gives −1.03 / +0.91 against −1.06 / +0.94. [Output](scripts-22/noise_micro.json).

| Tracker, speed band m/s | Accel p5 / p95 | W1 accel, block vs block: p50 / max | Jerk abs p95 | W1 jerk: p50 / max | Time gap p5 / p50 / p95 | W1 gap: p50 / max |
|---|---|---:|---:|---:|---|---:|
| I-90/94 stat, 5–10 | −1.03 / 0.91 | 0.10 / 0.23 | 1.05 | 0.11 / 0.20 | 0.87 / 1.86 / 4.02 | 0.37 / 0.84 |
| I-90/94 stat, 10–15 | −0.92 / 0.80 | 0.12 / 0.14 | 0.98 | 0.20 / 0.31 | 0.71 / 1.64 / 4.10 | 0.14 / 0.25 |
| I-90/94 moving, 5–10 | −1.05 / 1.00 | 0.07 / 0.13 | 1.58 | 0.13 / 0.19 | 0.77 / 1.92 / 4.36 | 0.21 / 0.32 |
| I-90/94 moving, 10–15 | −1.04 / 1.01 | 0.08 / 0.14 | 2.02 | 0.16 / 0.24 | 0.61 / 1.72 / 4.36 | 0.18 / 0.33 |
| I-395, 5–10 | −0.58 / 0.62 | 0.04 / 0.13 | 0.36 | 0.04 / 0.08 | 0.57 / 1.76 / 4.36 | 0.07 / 0.17 |
| I-395, 10–15 | −0.74 / 1.15 | 0.10 / 0.15 | 0.85 | 0.06 / 0.11 | 0.53 / 1.66 / 3.98 | 0.09 / 0.18 |
| I-294 L1, 15–25 | −1.12 / 0.92 | 0.13 / 0.26 | 1.40 | 0.12 / 0.25 | 0.58 / 1.55 / 3.68 | 0.31 / 0.72 |
| I-294 L1, 25–40 | −1.12 / 1.07 | 0.10 / 0.23 | 1.52 | 0.09 / 0.40 | 0.49 / 1.31 / 2.91 | 0.13 / 0.26 |
| A39, 15–25 | −0.41 / 0.41 | 0.02 / 0.09 | 0.36 | 0.01 / 0.05 | 0.88 / 2.23 / 3.74 | 0.22 / 0.69 |
| A39, 25–40 | −0.69 / 0.62 | 0.03 / 0.07 | 0.52 | 0.01 / 0.03 | 0.60 / 1.44 / 2.86 | 0.09 / 0.38 |

Road against road at the same speed, 5 m/s and up: W1 accel 0.04–0.41, jerk 0.04–0.57, gap 0.07–0.85. Bands below 5 m/s are dominated by the far tail of `T`, so clip `T` at 10 s. I-395 above 15 m/s is camera noise per report 05, and is excluded.

**The tracker shows through.** At 5–10 m/s, jerk p95 is 0.36 on I-395 and 1.58 on I-90/94 moving: a factor of 4.4, which I read as filtering as much as drivers (not separated here). **So jerk can't be a matching target across trackers. It's a witness, tracker by tracker, plus a physical upper limit.**

| Junction quantity | Real value | Spread within the data | Source |
|---|---|---|---|
| Queue headway, positions 1, 2, 3, 4 | 3.62, 2.40, 2.20, 2.20 s | By signal group: 3.23–3.92, 2.20–2.60, 2.00–2.20, 2.00–2.20. By quarter of day: at most 0.2 (0.4 at position 4) | DLR UT, Sunday |
| First-car start after green | 1.62 s | 1.42–1.83 by group | DLR UT |
| Critical gap, by session | Site medians 3.23 F1, 2.61 F2, 2.76 L1 | Within site 3.05–3.48, 2.31–2.91, 2.45–2.80. **So session noise is about ±0.3 s, and site difference is about 0.6 s** | Swiss, 18 sessions with ≥100 decisions |
| Lane change 10–90%, A39 by hour | 5.6–5.8 s across 24 hour files, median | 0.2 s is the sampling step | DLR HT |
| Peak lateral speed, A39 by hour | 0.69–0.73 m/s | | DLR HT |
| Lane changes per vehicle-km, A39 | About 0.3 | 34,904–40,186 changes (screened, all). 18.2 M rows at 5 Hz × about 34 m/s gives about 124,000 veh-km. Rough, and not a rate by hour. Report 04's US survey value is 0.22–0.26 | Report 05's file |

### Did the metrics work? 16 corruptions and a control

A real day was corrupted, then scored against other real days. Count of the 27 metrics over the floor, using **1.25 × max** (the rule chosen below), and which ones. [Details](scripts-22/noise_berlin.json).

| Corruption | Over 1.25×max | Network metrics that noticed | Fine metrics that noticed |
|---|---:|---|---|
| Control: another real day | **0** | none | none |
| Flow ×0.97 | 1 | flow curve | |
| Flow ×0.95 | 3 | total, flow curve | site-day |
| Flow ×0.9 | 6 | total, flow and density curves | GEH, GEH share, site-day |
| Flow ×0.8 | 8 | total, curves, peak density | GEH, WAPE, site-day |
| Flow ×1.2 | 8 | same | same |
| Clock +1 h | 10 | hour share, AM peak, curves, AM speed | GEH, WAPE, day shape, onset |
| Clock −1 h | 8 | hour share, AM peak, curves | GEH, WAPE, day shape |
| Flat demand 06–20 | 10 | hour share, both peaks, curves | GEH, WAPE, day shape |
| **Sites shuffled within class** | **15** | **none** | all site-level flow, speed and jam metrics, up to 13× |
| **Speeds shuffled within class** | **9** | **none** | speed at site, dip, every jam metric |
| **Fast roads −25%, slow roads compensate** | **4** | **none** (peak density only at the looser rule) | GEH, GEH share, WAPE, site-day |
| Peaks clipped 15%, spread later | 3 | hour share, flow curve | day shape. Totals are unchanged |
| No rush-hour dip | 7 | PM speed distribution, density, peak density | dip, jams |
| Free flow all day | 14 | speed distributions, density, class speed | everything on speed and jams |
| Speed ×0.9 | 7 | speed distributions, density | site speed, jam count |
| **Jams clear 1 h late** | **0** | none | **none at this rule; 1 at max, 2 at p90** |

**Two false comforts this exposes.**

- **Network metrics alone would pass the three "wrong place" corruptions.** Those are precisely right-for-the-wrong-reason models. Report 14 found the same thing on a real run: `v2_day2`'s 42.8 km/h is inside the real range, yet it carries a third of the distance and barely slows at rush hour.
- **Hourly data can't catch a one-hour error in jam clearance.** That is a real weakness of this data, not of the idea. Madrid has 15-minute flows and MeTS-10 has 5-minute probe speeds. Until then, clearance is reported as low power, not as passed.

**Rank share and CRPS.** One real day against the other seven:

| Ensemble | CRPS flow, share of mean | CRPS speed, km/h | Rank in outer two of 8 bins (flat = 25%) |
|---|---:|---:|---:|
| Real days | 4.5% | 2.09 | 27.8% |
| Flow ×0.95 | 6.0% | 2.09 | 44% |
| Flow ×0.9 | 9.5% | 2.09 | 67% |
| Clock +1 h | 11.5% | 2.73 | 56% |
| **Sites shuffled** | **31.7%** | **5.58** | **25%, looks perfect** |
| Fast −25%, slow compensating | 25.7% | 2.09 | 90% |

So the real days look exchangeable: 27.8% against 25% expected here, on 3 held-out days, and 24.9% on all 8 days in my first full run. The rank test alone passes shuffled sites, as Hamill warns, because the shuffled ensemble is wide. CRPS catches it at seven times the floor. **Always report both.**

**False alarms.** Hold out a real day and treat it as the simulation, with floors from the remaining days. Count of metrics flagged per day, out of 27:

| Rule | 7 May | 14 May | 15 May | 16 May | 21 May | 22 May | 23 May | 28 May | Flags per metric-day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| p90 of pairs | 0 | 1 | 0 | 7 | 0 | 6 | 4 | 0 | 8.3% |
| max of pairs | 0 | 1 | 0 | 3 | 0 | 4 | 1 | 0 | 4.2% |
| **1.25 × max** | 0 | 1 | 0 | 1 | 0 | 2 | 0 | 0 | **1.9%** |

**A real day doesn't always pass.** Even at the loosest rule, 3 of 8 real days trip at least one metric. So pass/fail needs care: use a median over many replicate-day pairs (which a single odd real day doesn't have), keep the primary list short, and don't over-read a single flag. Hence the rule in section 6.

## 6. Benchmark: how every metric is scored

**Replicate.** One run: seed `i`, with one draw of day-to-day demand variation when the scene has that model. **Seeds aren't days.** Real day-to-day variation comes partly from different demand. A fixed demand with new seeds will likely be too narrow, so measure and report that (`N15`) until a demand-variation model exists.

**Pairs.** For metric `m`, run `R` replicates against `J` real days of the set in use, giving `D_m(i, j)`, one simulated day against one real day (gate rule 4). Never average seeds first.

- `S_m` = median of `D_m(i, j)` over all pairs.
- `S90_m` = 90th percentile.
- `F_m` = the floor: 97th percentile of `D_m(a, b)` over ordered real day pairs, a ≠ b, on the same sites and hours. With 8 days that is about the maximum of 56 pairs. Requires at least 8 days, or blocks for trajectory data. If fewer: status `THIN`.
- `U_m` = the upper limit of a 95% cluster bootstrap of `S_m`, resampling days and seeds. For trajectories, resample blocks.

**Status of a metric** (first that applies):

| Status | Condition | Meaning |
|---|---|---|
| `NO DATA` | No usable real source | The level can't claim a pass |
| `INVALID` | Real-day control fails, or instrument missing | Fix the benchmark first |
| `FLOOR` | `S_m ≤ F_m` and `U_m ≤ 1.25 F_m` and `S90_m ≤ 1.5 F_m` | Indistinguishable from real data within what we can measure |
| `INCONCLUSIVE` | `S_m ≤ F_m` but the other conditions fail | Burden of proof not met. Not a pass. Often means too few seeds, or an unstable model |
| `NEAR` | `S_m ≤ 1.25 F_m` | Within what a real odd day does (section 5) |
| `CREDIBLE` | Meets the credible threshold in section 7, and beats its null by the skill rule | Published-best territory, reported as a gap from the floor |
| `FAIL` | Otherwise | |

For peak-hour and other integer metrics use an absolute margin: ±1 h. For metrics with a floor from another study, the table says so.

**Skill rule.** Where a null exists: `S_m ≤ F_m + 0.5 (N_m − F_m)` is required for `CREDIBLE`. In words, the model must close at least half the gap from the null to real noise. On WAPE: 0.094 + 0.5(0.39 − 0.094) = 24%. On RMSN, using p90 because max wasn't computed: 0.144 + 0.5(0.50 − 0.144) = 0.32. In the other direction, for jam hit rate using p10: 0.59 − 0.5(0.59 − 0.10) = 35%. **This makes the "credible" flow bar 24% WAPE and 0.32 RMSN, tighter than report 15's 35% and 0.40.** OPINION, with the arithmetic shown, and it's the fairest reading of "credible" I can make given the null. Salt Lake's in-sample 0.32 sits right at that line, and report 15 lists no held-out city result that gets there.

**Distances.** Use these definitions everywhere.

- `W1(A,B)`: mean over `p = 0.01…0.99` of `|Q_A(p) − Q_B(p)|`. In the metric's own units, so a builder can read it. Same as the area validation metric (Ferson and Oberkampf, not opened). Sample size doesn't inflate it, unlike KS.
- `CRPS(y, ens)`: `mean|e − y| − ½ mean|e − e'|`, per site-hour, then averaged, normalised by mean flow for flows.
- `GEH(a,b)`: `sqrt(2(a−b)²/(a+b))`, hourly. Report it, never tune on it alone (MULTITUDE).
- `TV`: `½ Σ|p − q|` on hourly shares.
- `FSS(tr,km)`: fraction of jammed cells in a neighbourhood of ±`tr` hours and sites within `km`. `1 − Σ(Pa − Pb)² / (ΣPa² + ΣPb²)`. Reported as a loss, `1 − FSS`.

**Virtual instruments.** Each real source gets one. These are part of the benchmark, not the simulator.

| Instrument | Real example | Sim measures | Trap |
|---|---|---|---|
| Point detector | Berlin `q_kfz`, `v_kfz` | Vehicle front crossings at the detector's position, all lanes. **Arithmetic** mean of spot speeds (`noise.json` says "arithmetic mean at the detector"). Round to integers as the source does | `reference_day.py` compares with an edge mean. That is why its speed row is labelled "partial". Needs new per-position output, see section 13 |
| Probe sample | MeTS-10, TomTom, KoDa | Sample `p`% of cars, 5-min space-mean per segment, with same map match rule | Probe share isn't flat across road classes |
| Camera pair | Cambridge ANPR | Pass time at the two positions with a capture rate from the source | Unknown path between cameras |
| Drone view | TGSIM, DLR, Swiss | `cars run --trace` at 0.1 s, then the same 1 s differences and lane logic as real data | Kalman smoothing, default lengths: use centre spacing (report 05) |
| Survey | SrV | Trip length and duration with the survey's self-report rounding, if known | Not blind in Berlin |

**Cross-tracker closure.** Before using two real sources in one scene, compare them with each other (detector speed against probe speed on the same segment and hour). That gap is the observation discrepancy, and it's added to the floor for any metric mixing them. Erik's "diverse set of trackers" only works if the trackers agree.

**Reference day or all days?** FHWA picks one representative real day, and report 12 picks 15 May. I score against all days in the set. One representative day would let a model fit that day's odd features, and pairs over all days match gate rule 4 without being fixed to one.

## 7. Benchmark: the metrics

Columns: **Tag** `P` primary, must pass for the level. `D` diagnostic, reported only. `W` witness: must pass, and **never a tuning objective** (section 10). **Floor**: `S` in section 5 means measured there. "Compute" means measure with the same code first; don't invent a number.

### Level 0: is it even a valid run? (No reality check, all must pass)

| ID | Tag | Definition | Pass |
|---|---|---|---|
| V1 | P | Teleports, teleports off | 0 |
| V2 | P | Vehicle overlaps per veh-km, from `--trace` collision flag | 0 |
| V3 | P | Vehicles conserved: inserted = arrived + still running | Exact |
| V4 | P | Same seed twice, same adapter: bit-identical | Exact |
| V5 | P | Metric change between dt 0.1 and dt 0.05 at tier A | Under 25% of `F_m` (report 04: dt acts as a driver parameter) |
| V6 | P | At full demand, unfinished 2 h after demand ends | ≤0.5% (report 15 credible), ≤0.1% (good) |
| V7 | P | Waiting to enter over 15 min | ≤1%, ≤0.2% |
| V8 | P | No demand scaling used to pass | Scale recorded in input labels. Any below 0.95 of the estimate fails |

### Level 1: ticks and metres

Scene: real leader replay, chains from real heads, plus closed-loop road sections per tracker. Each metric is scored **per tracker, not pooled**.

| ID | Tag | Definition | Real data now | Floor | Pass |
|---|---|---|---|---|---|
| M1 | P | Acceleration distribution per speed band, 1 s difference. `W1` | TGSIM I-90/94 stat, moving, I-294 L1, I-395 under 15 m/s, DLR HT | S, table. Per band and tracker. Between roads 0.04–0.41 | `FLOOR` per tracker. Credible: within road-to-road band |
| M2 | W | Jerk distribution. `W1` per tracker, same filter | Same | S | Must not exceed the tracker's own value by 1.25×; **never compared across trackers** |
| M3 | P | Time gap `T` by speed band, clipped at 10 s. `W1` | Same | S | `FLOOR` |
| M4 | P | Standstill spacing, centre to centre | DLR UT 7.0 (6.2–8.1), Lankershim 6.8–7.4, I-90 8.0 (6.3–11), I-294 8.2 (report 05) | Band across sites | Median inside 6.5–8.2 |
| M5 | P | Open-loop replay: spacing and speed RMSE over 30 s, paired against calibrated Krauss | Report 05's frozen splits. Now **dev**, see section 9. A39 fit on US only | Krauss 5.43 m on I-90/94 other day, 14.05 on A39; ours 4.00, 11.64 | CI of paired difference excludes 0 on every split |
| M6 | P | Chain: speed SD at position 8 ÷ 1. Wave speed from lag | Report 05, 239 held-out chains | 1.00. 33.7 km/h (IQR 27.5–43) | Inside IQR for wave; ratio 0.9–1.15 (OPINION) |
| M7 | P | Lane change 10–90% duration, peak lateral speed | TGSIM, DLR HT | 5.0–5.8 s by site; 5.6–5.8 s by hour. 0.69–0.83 m/s | Inside range |
| M8 | P | **Lane changes per veh-km**, by lane, density band and place along road | DLR HT about 0.3 (rough), TGSIM, US survey 0.22–0.26 | Compute by hour and site. Report 21: "the test that matters most", nobody publishes it | Within site-to-site spread |
| M9 | P | Accepted gaps at the change: new follower, new leader. Time gap p5, p10, p50 | TGSIM congested: 0.56, 0.74, 1.67 and 0.33, 0.47, 1.13. A39 free: 0.70, 0.90, 2.33 and 0.61, 0.87, 4.14 (report 05) | Compute `W1` by block | `FLOOR` per regime |
| M10 | W | Relaxation of time gap after a gap change, curve at 2–25 s | Report 05, section 4.9 | Spread across three sites at each time, 0.1–0.5 s | Within spread |
| M11 | D | Free-speed distribution by limit | DLR HT, low-flow hours on Berlin detectors | Limit not verified on A39 | Report |
| M12 | P | Physical limits: `physics_qa.py`, report 19 when it lands | ADAC dry braking −8.91 m/s² etc. in that script | n/a | Zero past physical limit |
| M13 | W | Stop-and-go waves: exist or not, wave period, speed, amplitude on TGSIM-like congestion | Calibration Illusion: the methods it tested lose them at large scale | Compute on I-90/94 and I-294 runs | Exist at the same density range, speed within floor |
| M14 | P | **Drift:** 1, 6, 24 h at fixed demand. Trend of speed, gap, change rate, contacts per hour | None needed | Slope CI includes 0, change under floor (report 21) | No trend |

### Level 2: per junction type

**Scene rule.** The recorded place is rebuilt from its own geometry, real arrivals are injected at the edge, real signal states when known, and **the one frozen driver config**. Nothing tuned per site. A scene that can't be rebuilt scores `NO DATA`.

**Signals**

| ID | Tag | Definition | Data now | Floor | Pass |
|---|---|---|---|---|---|
| JS1 | P | Headway by queue position 1–7 | DLR UT with controller states. Lankershim, Peachtree, Foggy Bottom (positions 2+). **Sunday; discharge was a fit target in report 05, so DLR UT is tuning data only** | 3.62, 2.40, 2.20, 2.20, 2.0 s. By group: S | Within group range per position |
| JS2 | P | Saturation flow, median of positions ≥5 at 50 km/h | DLR UT (2.0 s, n=55), Lankershim 1.9, handbook 1,900. Weekday, many sites: Hamburg, Perth, Glasgow signal and detector data (reports 11, 13, 20), not yet analysed | Report 04: 1,800–2,100 veh/h | Inside band, **at both dt 0.1 and dt 1**. TfL: within 10% per movement |
| JS3 | P | Lost time, first 4 positions | DLR UT 2.74 s (2.44–3.58) | | Inside CI |
| JS4 | P | First car: start after green, peak acceleration, time to 5 m/s | 1.62 s (1.42–1.83), 1.80 m/s² (1.30–2.45), 4.0 s | Group spread | Inside |
| JS5 | P | Queue start wave | 22.3 km/h, p10–p90 16–28 (report 04, n=22) | Band | Inside |
| JS6 | W | Yellow: P(stop) against time to line. Stop share by required braking | 50% at 5.1 s. 0.6% at 2–3 m/s², 0 of 644 above 3. 25% of goers cross after red (report 05) | CI, one Sunday | Inside CI. Hard: SUMO's rule fails this |
| JS7 | P | Movement delay and stops per vehicle, distribution. `W1` | Compute on DLR UT by hour. Songdo and Athens locked | Compute | `FLOOR` |
| JS8 | D | Max queue per cycle | Songdo | Compute | Report |

**Priority (give way, no signal)**

| ID | Tag | Definition | Data now | Floor | Pass |
|---|---|---|---|---|---|
| JP1 | P | Critical gap: censored lognormal as in report 05, by movement | **No clean source in hand.** Foggy Bottom's one unsignalised junction unchecked; inD needs a form; Songdo, TUMDOT not yet scanned for priority junctions | `NO DATA` | The junction-targets agent decides |
| JP2 | P | Follow-up headway | Same | `NO DATA` | |
| JP3 | P | Minor-road delay against major flow | Same | `NO DATA` | |

**Roundabouts**

| ID | Tag | Definition | Data now | Floor | Pass |
|---|---|---|---|---|---|
| JR1 | P | Critical gap, same method on sim output, by site | Swiss F1, F2 for tuning; **L1 held out** | Session spread: ±0.3 s (S). 3.25, 2.65, 2.72 | Within site's session range |
| JR2 | P | Follow-up headway | F1 3.15 (n=106), F2 2.52 (20), L1 2.33 (23) | Thin | `THIN` until more |
| JR3 | W | Entry flow against circulating flow, per arm. Curve distance | Compute on Swiss | Compute | Within session spread |
| JR4 | D | Ring transit speed | Swiss | Compute | Report |

**On-ramp, lane drop, zipper**

| ID | Tag | Definition | Data now | Floor | Pass |
|---|---|---|---|---|---|
| JO1 | P | Merge position along the acceleration lane, as a share of its length. `W1` | TGSIM I-90/94 ramp events need tagging. MiTra, exiD, HDSVT not yet opened. Report 18 pending | Compute | `FLOOR` |
| JO2 | P | Accepted gaps at merge, speed difference at merge | TGSIM ramp or weave cars: 678 events (report 05) | Compute | `FLOOR` |
| JO3 | P | Downstream discharge and breakdown frequency. Capacity drop | Report 04: 0–18%. 3 Californian sites none | Band. Treat as a distribution | Inside band |
| JL1 | P | Lane drop: merge position against distance to the end | DRaT, 140 m section, Fort Worth, 5,278 tracks, 45 forced merges | Thin | `THIN` |
| JL2 | P | Discharge per lane past the drop | DRaT | Compute | `FLOOR` |
| JZ1 | P | Zipper: share of mergers using the last third of the lane; alternation (share of consecutive crossings from different lanes) | **No clean source yet.** Report 18 pending | `NO DATA` | |

### Level 3: corridor

| ID | Tag | Definition | Data now | Floor | Pass |
|---|---|---|---|---|---|
| C1 | P | Travel-time distribution per route and hour. `W1`, median, p90. FHWA criteria I–IV reported too | **Cambridge ANPR hop times: 13 June 2017 in hand, other 7 days fetchable** (report 01). Weak: Berlin `routes-ref`. Keyed: KoDa | Compute with other Cambridge days. Guidance: TAG 15% or 1 min; FHWA worked BDAE 1.84 min | `FLOOR`. Credible: TAG on ≥70% (report 15) |
| C2 | W | Speed field in time and space, `1 − FSS` for jam cells | TGSIM I-90/94 runs, DLR HT, Berlin neighbouring detectors. MiTra and SWIFTraj unopened | Compute run vs run | `FLOOR` |
| C3 | P | Motorway capacity, sustained per lane | Report 04: 1,800–2,300. Trafikverket 1,867–2,160 | Band | Inside, at real speeds, both dts |
| C4 | P | Wave speed, jam spacing | Report 04: −12 to −22 km/h on freeways; report 05: 17–29 from steady fits, 33.7 by lag | **The sources disagree, and methods differ.** Score each with its own method | Inside its own band |
| C5 | P | Queue length and spillback onset at named places | TfL: place and time, not length. Songdo. Named bottlenecks in Berlin | Compute | Right place, right ±1 h |
| C6 | D | Cross-lane flow split, by road | Berlin lane detectors (`det_val_hr`) | Compute | Report |

### Level 4: network

Scene: city or district day. Real data: **Berlin May 2019 detectors, tuning.** Berlin held-out and Madrid: section 9. All at virtual detectors, tuned sites and blind sites reported separately.

| ID | Gate check | Tag | Definition (`a` = sim replicate, `r` = real day) | Data | Floor (p50 / max, S) | Null, class mean | Credible |
|---|---|---|---|---|---|---:|---|
| N0 | All | P | Report 14's `normal_day_gate.py` sanity bands, including worst hour ÷ night speed (median 0.61 over 64 cities). Runs first, and is cheap | TomTom, counters (report 14) | Report 14's plausible band | n/a | Inside hard band |
| N1 | Volume | P | Network total on panel sites, abs. relative error | Detectors | 0.9% / 2.8% | n/a | ±10% (report 15) |
| N2 | Volume | P | Total veh-km against official 41.3 M km | Berlin, part estimated | Report 03 | n/a | ±10% |
| N3 | Day shape | P | Hourly share RMSE, points | Detectors, Zurich, Madrid | 0.09 / 0.14 | | ≤0.5 mean abs. (report 15) |
| N4 | Day shape | P | AM and PM peak hour | Same | 0, ±1 | | ±1 h |
| N5 | Volume | P | Site-hour WAPE, 06–20 | Detectors | 7.3% / 9.4% | 39% | ≤24% (skill rule) |
| N6 | Volume | P | Site-hour RMSN | Same | 0.116 / p90 0.144 | 0.50 | ≤0.32 |
| N7 | Volume | D | Median GEH; share GEH<5; R²; slope | Same | 1.53 / 1.88; 92% / 86%; 0.955 | 9.1; 29%; 0.18 | GEH<5 ≥60% |
| N8 | Volume | P | Site-day total: median, p95 error | Same | 2.8% / 4.1%; 22% / 38% | Spearman 0.16 | Report |
| N9 | Day shape | W | Site day shape, median TV | Same | 0.030 / 0.033 | Compute | Report |
| N10 | Speed | P | Class × hour speed error, mean and max. **Classes with ≥20 sites only** | Detectors, then MeTS-10 | 0.8 / 1.7 mean, 2 classes | | ±20% arterial, ±10% motorway |
| N11 | Speed | P | Site-hour speed: mean and p95 error | Detectors | 3.4 / 4.0; 12.5 / 15 | Compute | Report |
| N12 | Speed | P | `W1` speed distribution, AM, midday, PM | Same | 0.8 / 2.1; 0.6 / 1.0; 0.7 / 1.8 | | Report |
| N13 | Speed | P | Rush-hour dip: lowest 06–20 speed ÷ site free speed, median error | Same | 0.059 / 0.071 | | Report |
| N14 | Where and when | P | **Jam FSS loss:** jam = speed under 0.7 × site free speed (p90 of the real day, at the site). Exact; ±1 h; ±1 h and 1 km | Same; MeTS-10 for 5 min | 0.34 / 0.41; 0.22 / 0.30; 0.14 / 0.19 | Compute | ±1 h 1 km ≤0.30 (OPINION) |
| N15 | Spread | P | Replicate spread ÷ real spread, site-hour SD ratio; CRPS; rank outer share | Same | Rank share 27.8% (25% flat), CRPS 4.5%, 2.09 km/h | | Ratio 0.5–1.5 (OPINION) |
| N16 | Where and when | P | Jam hit rate; false alarms; jam site-hour log ratio | Same | 67% / 33% (p10–p90 59–73, 28–42); 0.07 / 0.21 | 10%, 69% | Hit ≥35%, false ≤55% (skill) |
| N17 | Where and when | P | Top-20 bottlenecks shared. Bottleneck = largest speed deficit below free speed over 06–20 | Same | 70% (58–80) | 15% | ≥36% (skill) |
| N18 | Where and when | W | Jam onset and clearance, mean abs. error, per matched jam, AM and PM | Same (low power hourly) | 0.58 / 0.74 h; 0.78 / 0.99 h | | ±1 h. **Report 15's ±30 min can't be tested on hourly data** |
| N19 | Network curve | W | Hourly flow against density, q/v. nRMSE of each; peak density error. Only "at sensors" | Same | 1.7% / 2.6%; 3.5% / 7.3%; 2.5% / 6.8% | | ±20% peak (report 15) |
| N20 | Trips | W | Trip length and duration distributions. `W1` on log | SrV (not blind); Jinan; Cambridge chains | Compute | | ±15% means (report 15) |
| N21 | Routes | W | Route share between camera pairs. VED for internal route shape | Cambridge | Compute | | Report |
| N22 | Transfer | W | Weekend and Sunday: real ratios against sim. Zurich Sun/midweek 0.76, Sat 0.94 | Berlin, Zurich | Compute | | Direction and size |

No loop-area metric: section 5 shows it's useless at hourly resolution.

**Coverage summary.** Today, **without new access**: L1 strong, L2 strong on signals and roundabouts, `NO DATA` on priority and zipper, thin on ramps and lane drop. L3 needs Cambridge. L4 strong on main-road Berlin, thin on motorways (3 sites) and on `Speed`, because probes need Erik's HERE form.

## 8. Combining without hiding failures, and comparing versions

**No weighted total, ever.** A total lets a model trade a bad jam location for a good speed, and every field in section 2 warns against that. Reporting produces:

1. **Scorecard.** Every metric with its status, `z_m = S_m / F_m`, and `U_m / F_m`. Grouped by level and gate check.
2. **Level status.** Worst status of its `P` and `W` metrics. A `NO DATA` level means no pass at that level, ever, however good the others are.
3. **Must-pass rule.** "Validated" for a scenario only if every gate check maps to at least one tested `P` metric at `FLOOR` or `NEAR`, on held-out data, in one configuration. Otherwise report precisely which passed. That is gate language.
4. **Leximax vector.** Sort all `z_m` descending, across all levels. This is the climb's direction. Vernon's first, second and third highest implausibility is the same idea. Track `(z₁, z₂, z₃, count FAIL, count CREDIBLE, count NEAR, count FLOOR)` per level. History per commit gives the climbing curve Erik asked for, **without a single score**: plot the worst z and the counts.
5. **Metrics that can't be scored stay visible.** `NO DATA` and `THIN` are counted and printed in the headline.

**Comparing version B with version A** on the tuning set, same seeds, same days (paired).

For each metric, `Δ_m = D_m^B(i, j) − D_m^A(i, j)`, 95% cluster bootstrap interval `[L_m, U_m]`, and margin `ε_m = max(0.25 F_m, F_m − p50 of real pairs)`.

| Verdict | Condition |
|---|---|
| **BETTER** | Every metric `U_m ≤ ε_m`, and at least one `U_m < −ε_m` |
| **SAME** | Every metric `|L_m|, |U_m| ≤ ε_m` |
| **WORSE** | Any `P` or `W` metric `L_m > ε_m` with no offsetting BETTER on a higher-z metric |
| **TRADE-OFF** | Some better, some worse beyond the margin |

**Report 20's rule applies:** each new mechanism (buses, crossings, parked vehicles) ships with a switch, so its effect can be measured by turning it off. Each comparison is then a controlled ablation.

**Rules.** Merge only BETTER, or SAME with a simpler model. A TRADE-OFF merges only when the **leximax** falls (the worst got better, and no metric crosses into `FAIL`) and the log names the cause of the regression. A change that improves network metrics while a level 1 or 2 metric regresses is presumed compensation and rejected until explained. Check the seed count with [FHWA's formula](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter6.htm): if 20 replicates aren't enough for a metric, the instability is the finding.

**The climb.** Take the top of leximax. Use report 16's input audit and the planned debugging tools to find the cause. Fix the cause at the lowest level that can measure it. Re-run everything. Log it. If the top won't move after a real fix, look at section 11's matrix to see which input owns it, since it's probably demand or signals.

## 9. Tuning data and held-out data

**Register first.** `bench/registry.toml` is committed with hashes of all metric code, thresholds and split lists **before the first simulated score at each stage**. Changing it creates `bench v2`, and any held-out data that v1 revealed is spent.

**A good property:** Berlin's archive lists every month of 2019 (MEASURED, I read the listing with no download, under `2019/alte_qualitaetssicherung/Messquerschnitte/`). Only May is on disk: I searched `cars-data` and this repo for the other months and found none. So held-out data is renewable, month by month.

| Split | Tuning: free to use and look at | Selection: compare candidates; small number of looks | Locked: pre-registered; never downloaded before use |
|---|---|---|---|
| **Day** | Berlin May 2019, 8 normal Tue–Thu days. **Includes 15 May**, which report 12 proposed as the gate day: it's been read, so it can't be blind | Berlin April 2019 before Easter | Berlin March 2019; June 2019 before the school holidays (check dates against the official list); then Sept and Oct 2019 as renewals |
| **Site** | 70% of Berlin sites, by `sha256(site + "cars-bench-v1")` per road class | Same sites, other days | 30% by hash, plus **all 24 stations more than 200 m from v6.4's calibration links** (report 12). Reported separately as the only blind flow result |
| **Time of day** | All hours for reporting | OD and departure-time fitting may use only **hours 00–13** of tuning days | PM peak 14–20 was never an input to any fit, so it tests the demand machinery |
| **City** | Berlin | | **Madrid** (blind flows, report 12). Helsinki trajectories at L1 and L2 (report 21). Jinan is an engine test only, see below |
| **Trajectories** | Report 05's train split | **Report 05's test splits are now selection, not held out**: its author picked lag and noise while looking at them, and says so | Helsinki, Athens, Songdo, TUMDOT, Pully: unscanned except for one sample zip each. **Pre-register by listing the session files now** |
| **Junction** | Swiss F1, F2. DLR UT 8 of 9 signal groups | | Swiss L1. DLR UT signal `sid` 7 (arbitrary, pre-registered here). Songdo sessions |

**Differential tests (Klemeš).** Reported separately, because they test something different. Same config, no refit: Sunday and Saturday in Berlin (and DLR UT is itself Sunday, so a weekday target is the hard direction); transfer from US-only tuning to A39 (report 05 did this); non-Nordic tuning to Helsinki (report 21). Natural experiments next: closures, the A100 opening (report 04), the Stockholm trial (report 15).

**Jinan and other replay.** Giving each car its real schedule and route is a supply test (report 15, LCSim). It can't count as validation: label `engine test`, and keep it out of the leximax. It's still the sharpest way to split a supply fault from a demand fault.

**Reveal rule for locked data (Ladder, adapted).**

1. `bench reveal --locked <set>` runs on a frozen tagged commit. It appends a line to `bench/ledger.tsv`: commit, config hash, date, reason.
2. It prints only: status per level, whether each level's leximax improved by more than step `η = 0.25` on z, and z rounded to multiples of `η`. Per-metric, per-site detail stays hidden.
3. **At most 5 reveals per set.** After that the set is spent, and it joins the tuning data. A new month is opened. Any look at raw held-out data also spends it.
4. The final report opens a never-used set once, and prints everything.

Ladder's guarantee assumes loss on independent samples, and days and sites here aren't independent. Treat this as discipline, not a theorem. Recht's result suggests the bigger loss will come from a new city, not reuse. So keep Madrid out of the reveal budget entirely until the end.

## 10. Rules against overfitting

| # | Rule | How it's enforced |
|---|---|---|
| 1 | **One configuration.** No per-scene or per-city behaviour number | `bench` refuses to run with a scene file containing driver parameters. A test diffs config hashes across a run's scenes |
| 2 | **Measured inputs first.** Fix map, signals, demand before any behaviour tuning (report 15's order; FHWA's capacity, routes, system) | Stage gate in `bench`; input labels required |
| 3 | **Bounds are measured ranges.** Each tunable has a source and range in `configs/human-v1.toml`. A result at a bound fails, and is logged | Report 05 shows why: calibrated Krauss reached `decel` 0.33 m/s². San Francisco's 24→21 ft car (report 15) is the classic case |
| 4 | **Parameter budget.** At most **15** free global driver parameters (OPINION: Grimm's typical 10–20, Fremont 35→10, Azevedo 11 of 101, Punzo 3 of 6), **and** `P ≤ r/2`, where `r` is the rank of the identification matrix above noise (section 11) | Printed in the scorecard |
| 5 | **Fixed per level.** Tune each parameter against the lowest level that measures it. Car-following against level 1, gap acceptance against level 2. City level may adjust only what levels 1–2 can't see | Hourdin's three levels. Logged |
| 6 | **Witness metrics.** Tag `W` metrics may never appear in an objective, fitting loop or threshold search. A failure there needs a named cause | Hourdin, Grimm. The tuner's API takes a metric list and refuses `W` |
| 7 | **Local fixes are counted.** A map or signal fix needs external evidence (photo, plan, OSM history) and a log line. Fewer than one per five held-out sites (report 15) | Counter in the scorecard |
| 8 | **Keep the survivors.** Don't report one best fit. Report the set of settings not ruled out (`z ≤ 1.25` on tuning metrics) and the spread of each prediction | History matching, GLUE. **An empty set stops tuning:** the structure is wrong |
| 9 | **Twin test before trusting a tuner.** Run config θ* as fake reality with real-sized noise, tune from the priors, and check recovery of outputs and θ* | Platt, SBC. If outputs recover but θ* doesn't, those parameters aren't identifiable |
| 10 | **No demand scaling to pass.** No teleports to pass. No fitting demand to the sensors that score it | V1, V8, and report 12's blind-station split. Report 15's San Francisco and Stockholm warnings |
| 11 | **Public tuning log.** `research/truth/TUNING-LOG.md`: each change, cause, evidence, effect on tuning and selection scores | Hourdin's recommendation for CMIP6 |
| 12 | **Declared discrepancy.** Before tuning, each level states the gap we expect to remain and why (no pedestrians, no weather) | Vernon's ε. Stops "fixing" an expected gap with a dial |

## 11. Sensitivity: which metric identifies which parameter

**Goal.** A table showing, for each metric, which parameter or input moves it by more than real noise. This prevents two things: tuning a parameter no metric sees, and blaming the driver for a demand fault.

**Factors.** Driver: `MODEL_HUMAN` report 05 section 8 (`k1`, `k2`, `T`, `s0`, lag, noise amplitude and time, launch acceleration, lane-change duration, the hybrid's lane-change terms from report 21, critical gap, follow-up, yellow threshold, desired speed factor). **Inputs too, because they usually dominate:** demand scale, route cost weight on main roads, departure-time shift, truck share, signal cycle, green split. Range: the measured range, or report 16's uncertainty for inputs.

**Method.**

1. **Morris screen** per scene tier: `r = 10` trajectories, 4 levels. `r(k+1)` runs, each 3 paired seeds. With `k = 25`: 260 runs × 3. Tiers A and B on replicas in one GPU world with `target/release/sweep`, at the normal rules: small first, one GPU job at a time.
2. **Variance-based** on the top 8 per level: Saltelli `N = 64`, `N(k+2) = 640` runs, tier C and a district day (Azevedo's multi-step approach).
3. **Identification matrix** `J`: rows metrics, columns factors, entries `(effect over its range) / F_m`. An entry over 1 means real data can see it.
4. **Collinearity** for tunable sets: normalise each column, `γ = 1 / sqrt(λ_min(JᵀJ))`, and require `γ < 20` (FME's rule of thumb, opinion). Singular values above 1 give `r` for the budget.

**What it decides.**

| Finding | Action |
|---|---|
| A parameter moves nothing above noise | Fix it at a measured or literature value. **Not tunable.** |
| Two parameters are collinear (`γ ≥ 20`) | Tune one combination, or fix one from independent measurement |
| A metric moves with no driver parameter, only inputs | It's a demand or network metric. Failure goes to report 16's list, not the driver |
| A metric moves with nothing | It has no power, or the scene doesn't exercise it. Fix or drop |
| A metric moves with everything | Not specific. Keep as a check, don't use for diagnosis |

**Expected before measuring (OPINION, to be replaced by `J`).**

| Metric group | Expect it to identify | Expect it to be blind to |
|---|---|---|
| M3 time gap, M4, JS1–JS2 saturation | `T`, `s0`, `k2` | Demand |
| M1, M2 | Noise, lag, tracker filter | `s0` |
| M6, C4 wave | Lag, `T` | Desired speed |
| M7–M9 lane change, JO | Lane-change terms, gap floor | Signals |
| JR, JP | Critical gap, follow-up | `k1` |
| N1, N3, N5–N8 flows | **Demand, routes.** Barely the driver until congestion | Lane-change detail |
| N10–N17 speed, jams | Demand × capacity. So `T`, `s0`, signals, map | Hard to separate: **expect collinearity between demand scale and capacity here** |

That last row is the equifinality Erik named. Demand and capacity trade off at network level, and only levels 1–3 fix capacity independently. **That's why levels 1–3 must pass first, with no city-level fit touching them.**

Punzo's result is worth repeating: the leader's trajectory mattered more than the parameters. Inputs dominate at every scale, so include them.

## 12. Can the benchmark detect failure?

**Already measured:** section 5's 16 corruptions and a control. This test must keep passing, and it runs without a simulator: `bench selftest`.

**Required on the simulator.** `bench knownbad` runs each of these at the lowest tier that applies. Each must produce the named `FAIL`. Metrics that never fire across this table have no power and get fixed or removed. Values from earlier reports show why each should fail. **None of this has been run yet.**

| # | Known-bad configuration | Why it's bad | Must fail at least |
|---|---|---|---|
| 1 | Krauss SUMO defaults, dt 0.1 | Saturation 2,286 at 50 km/h, motorway at least 19% over band (report 04) | JS2, C3 |
| 2 | Krauss defaults, dt 1 | Fluctuation grows 1.5× in 8 cars (report 05) | M6, V5 |
| 3 | Calibrated IDM | Saturation headway 3.00 s; wave 57 km/h (report 05) | JS1, M6 |
| 4 | Calibrated Krauss with `decel` 0.33 | Fits replay, nonsense in a network | JS6, M12 or JS1 |
| 5 | Instant lane changes | Real 5.2 s | M7 |
| 6 | SUMO secure gap test | 35% of US congested changes pass (report 05) | M9, M8 |
| 7 | Lane changing off | | M8, C6 |
| 8 | Acceleration noise 0.53 m/s² | Overlaps, gap p5 0.25 s (report 05) | V2, M3 |
| 9 | **Car length 3 m, demand raised to match flow** | Throughput right, reason wrong: San Francisco's trick (report 15) | M4, JS1, while N1 may pass |
| 10 | **τ cut 30%, demand raised to match flow** | Same | M3, JS2, C3, while N1 may pass |
| 11 | Demand ×0.6 | Stockholm's recipe (report 15) | N1, N5, V8 |
| 12 | Demand ×1.2 | | N1, N14 or V6 |
| 13 | Demand clock +1 h | | N3, N4 |
| 14 | Flat departure curve | | N3, N9 |
| 15 | Fixed 90 s signals at all junctions, offset 0 | Today's real inputs (report 16) | JS7 or N14, C5 |
| 16 | Signals removed | Stockholm's real deletions (report 16) | N14, C5 |
| 17 | Teleports on at 120 s | Hides queues (report 04) | V1 |
| 18 | Free-flow-only routes | Motorways starve (report 15) | N8, N10 |
| 19 | Desired speed ×1.3 | | N12, M11 |
| 20 | Replay real schedules | Legal as an engine test only | Refused by `bench` for validation |

**Passing test of the benchmark.**

- All 20 fail at the named metric.
- Items 9 and 10 fail at levels 1–3 **even though level 4 throughput looks right**. This is the whole point.
- Real-day control: no `FAIL`, and `NEAR` at most on 2 metrics per held-out real day (section 5's 1.25×max false alarm). Real trackers' block-vs-block control similarly.
- Power table `bench/power.md` is committed. Re-run when any metric changes.

## 13. Build order for the benchmark builder

Reuse `scripts/reference_day.py`: `read_net`, `match_sites`, `geh`, `f1`. It's a good v0 and its "least similar real weekday" is the same idea as `F_m`. What's new is pairs across replicates, statuses, instruments and levels.

```
scripts/bench/
  bench.py            selftest | knownbad | run --tier A..D | compare A B | reveal --locked SET | sensitivity
  registry.toml       metric id, level, tag P/W/D, gate check, floor source, thresholds, null; committed before scoring
  splits/             site hashes, day lists, session lists, locked manifest with sha256 once fetched
  metrics/            micro.py junction.py corridor.py network.py, one function per ID, one signature
  instruments.py      point detector, probe, camera pair, drone
  floors.py           the same metric functions, real against real
  nulls.py            class mean, network mean
  ledger.tsv          every locked reveal
configs/human-v1.toml every tunable: value, bounds, source, tag fixed or tuned
results/bench/<commit>/<scene>.json, history.tsv
research/truth/TUNING-LOG.md
```

**One function per metric, used for real and simulated data alike:** `metric(cand, ref) -> float`, where `cand` and `ref` have the same type, from the same instrument. [scripts-22/noise_berlin.py](scripts-22/noise_berlin.py) already has working code for 27 network metrics, the corruptions and false alarms. [noise_micro.py](scripts-22/noise_micro.py) has the level 1–2 floors.

**Result record:**

```json
{"id":"N14b","level":4,"tag":"P","gate":"where_when","scene":"berlin","set":"tune","commit":"…","config":"sha256…",
 "R":20,"J":8,"S":0.31,"S90":0.36,"U":0.33,"F":0.30,"z":1.03,"status":"NEAR","null":0.71,"n_sites":167,"blind":false,"note":""}
```

**Order.** Each step ends in something testable.

1. **Real against real.** `floors.py` and `selftest` on Berlin, with no GPU. Reproduce section 5. Allow missing hours. Also do Madrid, Zurich and Paris from report 14 when it lands.
2. **Registry and splits.** Commit before any simulated score. Fetch nothing locked.
3. **Virtual detector.** `cars run` needs point crossings with spot speeds at given lane positions. It has `--edge-csv`, `--summary` and `--trace` today (`crates/cars-cli/src/run.rs`). An edge mean isn't a detector.
4. **Tier A and B scenes**, level 0–2, signal and roundabout first. Run the known-bad list here, before any city. This is cheap and most of the failures show up.
5. **Compare and history**, plus a plot of leximax against commit.
6. **Sensitivity** at tiers A and B.
7. **Corridor.** Cambridge from OSM. Fetch the other seven days first, to get a floor.
8. **Network.** Report 15's district order, one small area, then bigger. 20 seeds if GPU time allows, and at least 12 paired (report 21). Follow `AGENTS.md`: 3 GB VRAM spare, one GPU job at a time.
9. **First locked reveal** only after levels 0–2 are mostly `FLOOR` or `NEAR`.

**Hardware.** Step 1 ran here in a couple of minutes once the machine was free: the trajectory floors took 40 s and 340 MB, and the three Berlin scripts about 90 s together. The real cost is city-day runs: at report 15's 148 s per Berlin day, 20 seeds × one config is under an hour, and sensitivity at city level is days, so keep it to the district.

## 14. Ranked sources

Ranked by usefulness to this benchmark, not generally. Share and access columns are the brief's.

| # | Source | What it measures | Area, period | Share of vehicles | Rate, level | Access, licence | Sweden | Downloaded | Serves | Test | Work |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Berlin detectors 2019** | Flow, point speed | 239 complete sites; May 2019 used; all months listed | All passing at sites; network share unknown | Hourly, link | Open, dl-de-by-2.0 per report 01 | No | May only, on purpose | 3 | L4 floors, skill, jam score | Done for May |
| 2 | **TGSIM, DLR HT, DLR UT, Swiss** | Trajectories | Report 05 | All in view | 0.1–0.2 s | CC0, CC BY-NC-SA, CC BY | No | Yes | Tick and junction truth | L1, L2 | Scenes |
| 3 | **Madrid loops + EDM2018** | 15-min flows, diary demand | Report 12 | All at sites | 15 min | CC BY 4.0 | No | Not by me | 1, 3 | Locked city | Weeks |
| 4 | **Cambridge ANPR** | Camera journeys, hop times | 8 days, June 2017 | Unknown (report 01) | Per vehicle | Report 01 | No | One day | 1, 2, 3 | C1, N20, N21 | Days |
| 5 | **MeTS-10 Berlin** | 5-min probes | Jan–Jun 2019 | Unknown | 5 min, segment | Form, non-commercial | No | No | 3 | Fine jam timing | 3–4 days |
| 6 | **Helsinki, Athens, Songdo, TUMDOT, Pully** | Drone tracks at junctions | See catalogue | All in view | 30 Hz | Various | No | Samples | Junction locked sets | L2 held out | Days each |
| 7 | **DRaT, MiTra, exiD, HDSVT, inD, rounD, OpenDD** | Merges, ramps, priority | Various | All in view | | Some form-gated; catalogue | No | DRaT only | Fill `NO DATA` | JP, JO, JL, JZ | Junction-targets agent |

### Top 3 recommendations

1. **Build steps 1 to 5 before any more city runs.** Next step: launch the benchmark builder with this report, starting with `floors.py` and `selftest`, which can reproduce section 5 with no GPU. Then run known-bad cases 9 and 10 at tier A and B, because they're the direct test of Erik's question.
2. **Adopt the changed thresholds.** Next step: gate and report 15's table get the skill rule, measured jam floors and the "report 15's Good exceeds floor" correction. Use 24% WAPE and 0.32 RMSN as credible. Drop hysteresis area. I haven't edited either file, because others share them; a coordinator should.
3. **Fill the three biggest data holes in order:** Erik's HERE form (fine jam timing and class speeds, motorways have only 3 detectors in the panel), Cambridge's other seven days (a real travel-time floor), then a priority-junction and zipper source (`NO DATA` otherwise forever). Next step: the junction-targets agent in `PLAN.md`'s queue picks up the last.

### What only Erik can do

- **HERE Traffic4cast form** for MeTS-10 (report 04 and 12 have the details). Without it, motorway and 5-minute checks stay weak. Accepting means non-commercial terms.
- **Decide whether the skill rule replaces report 15's credible numbers.** I recommend yes.
- **Decide the licence question for evidence:** DLR UT and HT are CC BY-NC-SA, so derived floors carry that (report 04).
- **Agree that "no data" stays a failed claim.** Priority junctions and zippers can't pass until someone finds real data. No drafts needed from me: existing drafts in reports 04, 05 and 12 cover the people to ask.

### Dead ends

| Tried | Result |
|---|---|
| Network loop area (hysteresis) on hourly data | Floor p50 92%, max 15,900%. Useless |
| Single reference day | One day can be odd: 16 and 22 May trip the most metrics. Use all pairs |
| p90 of real pairs as the pass bar | False-alarm 8.3% per metric-day, 4 of 8 real days fail. Too tight |
| Rank histogram alone | Passes shuffled sites. Needs CRPS |
| Berlin September 2024 complete panel | 5 complete sites on 6 days. Thrown away. Allow missing hours instead |
| Jerk across trackers | A factor 4.4 between trackers at the same speed. Probably filtering. Witness per tracker only |
| KS and t-tests (Trafikverket's advice) | Not run. Rejected on reasoning: reject everything at tick scale, nothing on eight days |
| Springer, Sage, Wiley, ScienceDirect, HAL, lem.sssup.it, tandfonline, OSTI | Refused from here. So **not opened**: Toledo & Koutsopoulos 2004, Hollander & Liu 2008, Beven 2006, Kirchner 2006, Fagiolo 2007, Cont 2001, Williamson 2013, Gleckler 2008, Ferson 2008, Brynjarsdóttir & O'Hagan, Buisson & Ladier, Klemeš 1986, Brun 2001, Barceló 2010. Nothing numeric here rests on them |
| `heavy` for these jobs | Queue of 17 min, and the data isn't in the repo. Ran locally at low priority under load 60–95 instead |

### New directions

- **A publishable jam score.** Report 15 found none at city scale. Real-against-real FSS 0.66, 0.78, 0.86 at three tolerances seems new (no search of this claim was exhaustive).
- **Emulators.** Vernon's approach would let us rule out most of parameter space with far fewer city runs. Only worth it once district runs are slow relative to the climb.
- **A demand-variation model** so a replicate is really a new day (N15). I have no measurement of how far seeds alone fall short.
- **Year-long floor.** Fetching all of 2019 gives seasonal noise and would widen the floor honestly, at the cost of spending months that are currently locked. Use 2018 or 2020 instead if open.
- **Report 15's question about a queue model** fits here: run it through the same benchmark, as the null a micro model must beat.

## Reproduce

From a directory that isn't the data folder, with the dev shell:

```
S=research/truth/data-hunt/scripts-22  D=$HOME/projects/personal/cars-data/datasets  T=$HOME/projects/personal/cars-data/truth/trajectories/opus-20261031-cache
python3 -I $S/noise_berlin.py $D/berlin-2019-detectors/mq_hr_2019_05.csv.gz $D/reference-days/berlin/sites.csv $S/noise_berlin.json
python3 -I $S/noise_berlin_extra.py $D/berlin-2019-detectors/mq_hr_2019_05.csv.gz $D/reference-days/berlin/sites.csv $S/noise_berlin_extra.json
python3 -I $S/noise_micro.py $T $S/noise_micro.json
python3 -I $S/show_micro.py $S/noise_micro.json
```

Random seed for shuffles: 20261102. Corruptions use a subset of day pairs and days because the machine was saturated (4 pairs per corruption, 3 days for the ensemble), so those values are medians of a small sample. Floors use all 56 pairs. Literature text is in `cars-data/datasets/validation-lit/`, fetched by [lit_fetch.sh](scripts-22/lit_fetch.sh). Most papers were searched for their method and result sections, and not read cover to cover.
