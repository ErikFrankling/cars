# How humans merge: what was tried, what real tracks show, and a build spec

Date: 2026-11-02. CPU only, no GPU. No simulator was run: the "simulator" columns are saved traces of the `accept3` build (1 November). Numbers come from [`merging/`](merging/), scripts from [`scripts/merging/`](scripts/merging/).

Grades: **MEASURED** my calculation on real tracks. **PROVIDER CLAIM** the source says so and I read it. **MODELLED** a model or simulation result. **UNVERIFIED** I could not open the source, or saw only a snippet or abstract. Spec classes as in `HUMAN.md`: **ESTABLISHED**, **ADAPTED**, **INVENTED**.

## The answer

Erik is right that the rules are too simple, and right about three specific things. Two of his points need correcting, and one earlier target was partly wrong.

**What he is right about**

1. **Real drivers change their speed before merging.** They follow the target-lane car ahead 1.5 to 7 times as strongly as a through driver does. They also ease toward the middle of the gap, by about 0.03 to 0.08 m/s². Through cars show neither.
2. **Real drivers start sideways before the gap exists.** In queues, 32-41% start moving sideways with a target-lane car overlapping them. The simulator does this **0%** of the time.
3. **The car behind does slow.** It applies about 60% of the braking that following the merger would ask for. About 1 in 7 slow noticeably beyond comparable cars.

**What needs correcting**

4. **The blinker is not shown to do anything.** Followers start responding around the moment the merger's body nears the line. Nothing shows up seconds earlier. No open dataset can separate the blinker from the sideways motion.
5. **"Humans never ride alongside" is not true in queues.** Real drivers in queues spend about half the time before moving overlapped with a target-lane car, and the last 110 m of lane look much the same as the simulator. Riding alongside is a free-flow fault: the simulator's free-flow scene holds parallel for a median 10.5 s, 47% of episodes nearly locked in speed, against 0.9 s and 0% on the A39. Part of this is the scene itself, which gives every car the same desired speed (`speedDev="0"`).

**A correction to the brief**

6. **"Real I-80 drivers merge with 0.9 m left, ours 80 m early" compares the wrong things.** There is no lane line there at all. Choudhury 2007: "there are no physical lane markings separating the on-ramp vehicles from the mainline vehicles", and the merge point is an imaginary line where the wide lane narrows to 3.6 m. So 0.9 m is where a label flips, not a place drivers chose. The paths of cars close from 6.4 m to 2.7 m apart, and only about the last 54 m works as a change. Our test scene is a parallel lane 225 m long. The body first reaches the line about 7 m before the end. I-395, which no one had used for this, has the same shape of paths and gives 31 m. Part of the "80 m early" failure is the scene, not the driver, and report 14's and 16's target of 0.9 m should go.

**The biggest rule change.** Urgency by remaining distance fails badly when moved to another site. Fit on I-80 and US-101, it predicts that A39 drivers merge at the very end, 0 m left, against a real 319 m. Using time to the lane end predicts 327 m (333 m when scored only inside the merge zone). LMRS already has this, and so does the time form I fitted here.

## Ranked: what to build

| # | Behaviour | Evidence | Now in the simulator | Effect if fixed |
|---:|---|---|---|---|
| 1 | Urgency from time to the lane end, not distance | MEASURED, held out on two sites | Distance only | Fixes merging "at the last second" at speed |
| 2 | Follower applies a share of the asked braking, tapering when very close | MEASURED, held out on four sites | Share 0.76-0.95, real 0.39-0.68 | Should lower let-in from 83-88%, not yet tested |
| 3 | Start sideways on a gap that will exist, with a small edge-in | MEASURED, Choudhury's anticipated gap | Never starts with an overlap | Real tight merges, real follower pressure |
| 4 | Speed match in both directions, as a weight and not a minimum | MEASURED, held out | Braking side only, as a minimum | "Speed up" half is missing |
| 5 | Gap steering | MEASURED, small | None | Cars move out of side-by-side |
| 6 | Test scenes with real taper, ramp speed difference and speed spread | MEASURED geometry | Parallel lane, same speeds | Honest targets |

## 1. People who tried

### Models

| Source | What it models | Validated against | Fit | Grade |
|---|---|---|---|---|
| **LMRS**, Schakel, Knoop, van Arem 2012 | One desire value `d` per direction. Free, synchronised and cooperative bands at 0.365, 0.577, 0.788. Mandatory desire rises as `max(1 − x/(n·x0), 1 − x/(n·v·t0))`, x0 295 m, t0 43 s. Follower's headway relaxes, Tmin 0.56, Tmax 1.2 s, τ 25 s. Synchronise and cooperate by following the other car with a relaxed headway, then a **minimum** with own following | Not read | Not read | Formula and defaults PROVIDER CLAIM, read in the [OpenTrafficSim code](https://github.com/averbraeck/opentrafficsim) and [docs](https://opentrafficsim.readthedocs.io/en/latest/06-behavior/lane-change/) (the same group's implementation). The [paper](https://repository.tudelft.nl/file/File_03abfeb9-d9a7-4904-9e7d-8a31c3166d83) refused connections from this machine and from web fetch, and Wayback has no copy, so **validation is UNVERIFIED** |
| **Choudhury 2007**, Modeling Driving Decisions with Latent Plans, MIT thesis, ch. 5 read in full (local copy `practice/humans-20261101/choudhury2007.pdf`) | Normal, then courtesy, then forced. Courtesy read from an **anticipated gap** after time τ, τ normal(1.87, 1.44) cut to 0-4 s. A forced merge starts with a logit of −6.41 plus an aggressiveness term | I-80 estimation: 540 cases, 17,352 obs. MITSIMLab on US-101, 8:20-8:35 | Log likelihood −1,609.65, ρ̄² 0.88 against 0.87 without plans. Lane counts RMSPE 7.52% against 12.18%, speeds 22.26% against 24.27%, merge locations better | PROVIDER CLAIM. Report 16's re-implementation scored poorly and said it was unfair to him. MITSIMLab calibrates yield share and constants per site |
| **Toledo, Choudhury, Ben-Akiva 2005** | Explicit target lane, gap acceptance as the action | Trajectories, joint likelihood | Via Choudhury ch. 4: 442 drivers, 15,632 obs, log likelihood −875.81, ρ̄² 0.37 | Paper UNVERIFIED, thesis chapter read |
| **Ahmed 1999** | Forced merge: once started it completes, no further gap test | Trajectories | Not read | Scan has no text layer. Described in Choudhury ch. 2, UNVERIFIED directly |
| **Hidas 2002, 2005** | Free, forced, cooperative classes, with a target gap and a yield chance | Video | Observed shares not read | ScienceDirect closed, OpenAlex lists no open copy. His 2005 WIT paper opened: it compares simulators on hypothetical scenes. **Observed counts UNVERIFIED** |
| **Kesting, Treiber, Helbing 2007, MOBIL** ([paper](https://mtreiber.de/publications/MOBIL_TRB.pdf)) | Advantage to self plus politeness × neighbours' loss. p 0-1, threshold 0.1 m/s², bsafe 4 m/s², bias 0.3 | Simulated traffic only | None on tracks | PROVIDER CLAIM. No target gap, no sideways phase |
| **Laval & Daganzo 2006** | Lane changers as particles with bounded acceleration, leaving voids | Capacity drop and moving bottleneck relation | Qualitative | [Abstract](https://ideas.repec.org/a/eee/transb/v40y2006i3p251-264.html) and report 15, full text UNVERIFIED |
| **Sun & Elefteriadou 2014** ([abstract](https://ideas.repec.org/a/inm/ortrsc/v48y2014i2p184-205.html)) | Urban lane changes, driver types, "hand-shaking negotiations" | In-vehicle field runs, CORSIM | Not read | UNVERIFIED beyond the abstract |
| **Kondyli & Elefteriadou** ([seminar slides](https://filelist.tudelft.nl/CiTG/Over%20faculteit/Sub%20Sites/TTS%20Lab/TU%20Delft%20Seminar_Kondyli_102621.pdf)) | Free, cooperative, forced at ramps. Focus groups, instrumented car, 31 participants. Freeway cars prefer changing lane; decelerating is the least preferred | Their own runs | Cooperation MNL adj. R² 21.6%, forced logit adj. R² 61.9% with share of acceleration lane used at +21.64 | Slides read, papers UNVERIFIED |
| **Marczak, Daamen, Buisson 2013** | Two sites, accepted and rejected gaps. Logit on gap and speed difference. Distance to the end matters at one site only | Dutch and French trajectories | Not read | Abstract only, HAL blocked by a bot check. UNVERIFIED numbers |
| **Daamen, Loot, Hoogendoorn 2010** | Shortest accepted gap 0.75-1.0 s, falling toward the lane end | Dutch ramp | | Second hand in a snippet, UNVERIFIED |
| **Wan et al. 2014** ([14-3695](https://files.topslab.wisc.edu/publications/2014/Modeling%20Vehicle%20Interactions%20during%20Freeway%20Ramp%20Merging%20in%20Congested%20Weaving%20Section%20(14-3695).pdf), [14-5685](https://files.topslab.wisc.edu/publications/2014/How%20Merging%20Vehicles%20Choose%20and%20Approach%20Their%20Desired%20Merge%20Position%20in%20Congested%20Merge%20Area%20(14-5685).pdf)) | US-101: 398 mergers, 38.65% do not take the first gap, 151 go forward, 5 back | NGSIM | Descriptive | Read. My US-101 agrees, section 2.C |
| **Zheng 2014 review** | Sorts decision models and models of lane-change effects | | | [Abstract](https://ideas.repec.org/a/eee/transb/v60y2014icp16-32.html) only, UNVERIFIED |

### Commercial tools

| Tool | What it does | Fit reached |
|---|---|---|
| **Vissim 2025** ([help](https://cgi.ptvgroup.com/vision-help/VISSIM_2025_ENG/Content/4_BasisdatenSim/FahrverhaltensparameterFahrstreifenwechsel_bearb.htm), read) | Accepted braking for self and trailer, falling with distance from the emergency stop position. Safety distance × 0.6 during a change. `CoopDecel` −3 m/s²: 0-50% of desired deceleration before the leader starts changing, then from 50% of desired up to the maximum during. Cooperative lane change: the follower moves over, with example limits of 3 m/s speed difference and 10 s collision time. **Zipper merging** option: cars brake to stagger with the adjacent lane, with a minimum speed and an overtaking-time distribution | No published fit in the help. PROVIDER CLAIM. The lateral behaviour page returned 404 under the URL I guessed |
| **Aimsun** (report 15) | Zones by distance, cooperation percentage, forward, adjacent or backward gap, two-leader following with a negative gap | No published fit read. The user manual page itself did not open this time, so this rests on report 15 |
| **TransModeler** | No manual found | **UNVERIFIED**, open searches returned nothing from Caliper |

### Learned approaches

| Source | What it shows | Does it beat rules at merging? |
|---|---|---|
| WOSAC 2024 table in [Systematic Benchmarking of SUMO](https://arxiv.org/pdf/2512.18537), read | Realism meta metric: SMART 0.7511, BehaviorGPT 0.7473, SUMO SL2015 0.6532 (86.9% of the best). minADE 1.54 m against 5.83 m. Few seconds long, from logged starts | Better overall on short clips. **Nothing here is merge-specific**, and short log-seeded clips are not a day of traffic |
| [Kuefler 2017](https://arxiv.org/pdf/1701.06699), [PS-GAIL 2018](https://arxiv.org/pdf/1803.01044), [GAIL 2020](https://arxiv.org/pdf/2006.06412), read in part | Imitation on NGSIM, better emergent lane-change rates than behaviour cloning | Not on held-out sites. I saw no test against LMRS or Choudhury |
| Report 13 | A small network on this simulator does not beat a good formula | Same conclusion |

**Decision.** Stay with rules. A learned model cannot prove itself here, and rules are what a kernel can run. The tracks give the rule's numbers.

### What no one did that we needed

No source I could open gives a follower's response against same-state controls, aligned on the merger's sideways start, across several sites, with a formula tested on sites it was not fit on. Section 2 does.

## 2. Measurements

### Data

| Set | Cars used | Role | Limits |
|---|---|---|---|
| NGSIM I-80 | 615 ramp cars (lane 7 to 6), 2,336 changes | **Train** | Lateral position noisy, some acceleration noise, smoothed over 1 s. Known missing cars |
| NGSIM US-101 | 232 ramp cars (aux lane 6 to 5, clean windows; report 14 used 349 on looser rules), 1,606 changes | **Train** | Same |
| TGSIM I-395 | **1,992 ramp cars (lane −2 to −3), not used as a merge cohort before**, 4,456 changes | **Held out** | 6.2 m default length on 76% of tracks: overlap is overstated, so I also give the figure with a 1.5 m allowance |
| DLR A39 | 2,030 ramp cars, 7,382 changes in sample | **Held out** | Lanes are reconstructed, the lane end is estimated (99th percentile of crossings within 400 m), so its distances are rough. CC BY-NC-SA |
| TGSIM I-90/94 moving, I-294 | 419 and 503 changes | **Held out**, follower only | No lane ends. I-90 bumper lengths suspect |
| Simulator traces, `accept3` | I-80 scene 1,068 merges (`sim`), open merge 1,200 (`simo`), free flow 149 (`simf`) | Current state | Sampled at 1 or 2 Hz, cooperation 0.25 and 0.5, older than the current build |

Dropped: TGSIM I-90 stationary, which has no lane end and whose cache job would not finish while the PC was overloaded. Report 14 covers its followers.

**Method.** Sideways position is measured as distance from the target-lane centre, per 20 m of road, so taper is handled. "**Sideways start**" is the last time the car is within 10% of a lane width of its own lane's usual path. "**Body over the line**" is when the car's centre is 2.65 m from the target-lane centre, "**centre over the line**" 1.75 m. "**Overlap**" means a target-lane car's front is past our rear, or our front past its rear. Acceleration comes from smoothed speed at every site. "Plain following" is report 05's feedback law with its 1 s lag.

### A. Lane shape comes first

| Site | Lane centre spacing along the lane | Lane speed, m/s: ramp against target | Usable zone |
|---|---|---|---|
| I-80 | 6.4 → 5.9 → 5.0 → 4.0 → 3.3 → 2.7 m, every 20 m. **No lane line** | 2.9 / 3.0 | Last ~54 m |
| I-395 | 6.3 → 5.5 → 4.6 → 3.7 → 3.0 → 2.6 m | 6.0 / 7.2, then equal | Last ~63 m |
| US-101 | 3.3-3.9 m, parallel, 216 m | **13.6-17.5 / 10-12** | All of it |
| A39 | Parallel | Ramp slower | All of it |
| Simulator I-80 scene | Parallel 225 m at 3.2 m, a lane line throughout | Similar | All of it, **unlike the site** |

The zone is where centre spacing falls below about 4 m, and the earliest crossings (p5) fall there. MEASURED from vehicle paths. For I-80 the [thesis](#1-people-who-tried) confirms the road: no lane line between ramp and main lane, and "the absence of a physical lane demarcation over a long stretch made it difficult to specify when a lane change has occurred", so it defines a merge as the vehicle's centre crossing an imaginary line. PROVIDER CLAIM. For I-395 I have only the paths and the provider's boundary file, which I did not interpret.

### B. When along the lane end do they merge?

Metres before the end, p25 / p50 / p75. MEASURED.

| Site | Speed at label change, m/s | Lane label flips | Body over the line | Centre over the line | Sideways start | Stopped first |
|---|---:|---|---|---|---|---:|
| I-80 | 4.5 | 0.7 / **0.9** / 1.0 | −4 / **7** / 22 | −14 / −6 / 11 | | 26% |
| I-395, held out | 8.4 | 9 / 23 / 37 | 20 / **31** / 43 | −4 / 13 / 28 | 16 / 35 / 66 | 0.5% |
| US-101 | 12.0 | 65 / 119 / 158 | 79 / **138** / 174 | 66 / 119 / 158 | 97 / 158 / 183 | 0 |
| A39, held out | 25.5 | 256 / 277 / 285 | 316 / **325** / 335 | 266 / 292 / 300 | 291 / 306 / 331 | 0 |
| **Simulator, I-80 scene** | 6.3 | 33 / 94 / 142 | 44 / **108** / 156 | 34 / 96 / 142 | 49 / 112 / 160 | 21% |
| **Simulator, open merge** | 5.9 | 20 / 92 / 140 | 28 / **105** / 152 | 20 / 92 / 141 | 30 / 108 / 156 | 39% |

- **Reading it.** I-80's lane label flips at a fixed spot on an imaginary line, so "0.9 m" is a location, not a decision. Negative numbers mean the centre reached its target line after the label had already flipped.
- **By time, not distance.** From the medians, body over the line comes about 1.6 s before the end at I-80, 3.7 s at I-395, 11.5 s at US-101 and 12.8 s at the A39. Slow traffic uses the end of the lane, and fast traffic uses the start.
- **By flow.** In my 5-minute bins flow does not order the sites or the cars: I-395's centre-over-line median is 5, 15 and 1 m at 856, 1,169 and 1,524 veh/h, US-101's 87 and 120 m at 1,344 and 1,573 veh/h. The range of flows inside any site is small, so this does not rule out a flow effect across a wider range.
- **Lane speed is why.** A US-101 driver runs 3-6 m/s faster than the target lane and picks a gap early, then brakes into it. See D.
- **Sideways start at I-80** is not given: about half the cars (318 of 615) have no separate start, because the narrowing lane carries them across.

### C. Which gap: adjacent, ahead or behind?

Where the gap they finally took lay, before the sideways start. Share adjacent / ahead / behind. MEASURED.

| Site | 5 s before | 10 s before |
|---|---|---|
| I-80 | 54 / **19** / 27 | 41 / 24 / 35 |
| I-395 | 52 / 9 / 40 | 40 / 13 / 47 |
| US-101 | 34 / **62** / 4 | 11 / **88** / 2 |
| A39 | 75 / 1 / 24 | 58 / 0 / 42 (26 cars) |
| **Simulator, I-80 scene** | 79 / **0** / 21 | 67 / 2 / 31 |
| **Simulator, open merge** | 75 / **0** / 25 | 63 / 3 / 33 |

- It depends on which lane is faster: a faster ramp means gaps ahead, a slower ramp means gaps that come from behind.
- **Simulator cars almost never gain on the target lane before merging.** Real ones do, 9-24% at the queue sites and 62-88% at US-101.
- Wan's 151 forward against 5 back fits. This says where the gap ended up, not what the driver chose: which gap a driver aims for is latent, and the data can't show it directly.

### D. Before the merge, does acceleration leave plain following?

Excess over ordinary following at the same speed and gap, m/s², by time relative to the sideways start. Must-change cars, 95% CI in brackets. MEASURED.

| Site | −10 to −5 s | −5 to −2 s | −2 to 0 s | 0 to +2 s |
|---|---|---|---|---|
| I-80 | +0.01 (ns) | +0.08 (0.01, 0.14) | +0.17 (0.10, 0.24) | −0.11 (−0.20, −0.03) |
| I-395 | +0.04 (0.01, 0.07) | −0.07 (−0.11, −0.04) | −0.10 (−0.14, −0.05) | −0.15 (−0.20, −0.11) |
| US-101 | +0.32 (0.07, 0.55) | −0.06 (ns) | **−0.42** (−0.56, −0.27) | **−0.78** (−0.96, −0.60) |
| A39 | +0.22 (0.03, 0.42) | **+0.41** (0.36, 0.46) | **+0.52** (0.47, 0.56) | **+0.57** (0.51, 0.63) |
| Simulator I-80 scene | −0.08 | −0.12 | −0.03 (ns) | 0.00 (ns) |

- **Starting how far back:** 5-10 s before the sideways start.
- **Which way:** the way that matches the target lane. Slower ramp speeds up, faster ramp slows down, equal speeds do little. Same state, opposite signs, so a single fixed rule for all sites is wrong.
- **Discretionary changers are different:** at I-80, I-395 and the A39 they hang back at about −0.12 m/s² for 10 s, which is about 6 m, then accelerate into the gap (I-80 +0.40, US-101 +0.49, A39 +0.84). They make their own room behind before moving out.

**Is it aimed at the gap? Test against a placebo.** I regressed next-2-second acceleration beyond plain following on the target-lane state, for must-change cars and for through cars on the far side of the same lane, which have no reason to care. CIs by resampling cars. MEASURED.

| Site | Following the target leader: must-change | Through | Gap centring: must-change, 5-15 s before | Through |
|---|---:|---:|---:|---:|
| I-80 | **0.124** (0.103, 0.142) | 0.083 (0.076, 0.091) | **+0.076** (0.049, 0.123) | −0.012 (−0.025, −0.001) |
| US-101 | **0.222** (0.162, 0.298) | 0.066 (0.059, 0.074) | +0.066 (−0.139, 0.254) | +0.004 (ns) |
| I-395, held out | **0.175** (0.162, 0.189) | 0.051 (0.040, 0.061) | **+0.030** (0.008, 0.044) | +0.009 (ns) |
| A39, held out | **0.555** (0.464, 0.657) | 0.075 (0.045, 0.109) | −0.011 (ns) | +0.024 (ns) |
| Simulator I-80 scene | 0.036 (0.031, 0.039) | no through lane | +0.026 (ns) | |

- **Speed matching is real.** Must-change drivers follow the target leader 1.5 to 7 times as strongly as through drivers. Through drivers aren't at zero, because lanes share traffic waves, which is why the placebo matters.
- **Steering toward a gap is real but small.** 0.03-0.08 m/s² at full lean is about 0.5 m/s and 2.5 m over 10 s. That is enough to clear a car alongside slowly, in line with Erik's "slightly". Only I-80 and I-395 show it clearly. A39 doesn't need it.
- **Being overlapped adds nothing beyond this:** the overlap terms are zero within error at all four real sites.
- **The weight rises as the car's own change nears.** Time left to its crossing, 0-3 s: 0.35, 0.72, 0.40, 0.46 (I-80, US-101, I-395, A39). 6-12 s: 0.11, 0.11, 0.19, 0.24. Beyond 25 s: 0.13, none, 0.01, −0.09. By time to the lane end, which a model can see, there is no common trend: I-395 rises toward the end (0.01 to 0.43), I-80 is flat (0.09-0.17), US-101 and the A39 are mixed. So I did not fit a law on it, and the spec uses a constant.
- **Both directions.** Weight when the target leader asks for less, and more, than own following: I-80 0.08 and 0.24, US-101 0.23 and 0.84, I-395 0.19 and 0.07, A39 0.84 (rare, 1.6% of steps) and 0.26. **The simulator: 0.08 and −0.03 to 0.11.** Its "speed up" half is close to missing, because advice can only lower a speed.

**LMRS's full minimum fails.** RMSE of next-2-second acceleration, m/s², open loop. Fit on I-80 and US-101 only. MEASURED.

| Site | Plain following | Plain + weight 0.15 | LMRS / Aimsun minimum |
|---|---:|---:|---:|
| I-80 | 0.696 | 0.674 | 1.346 |
| US-101 | 1.356 | 1.212 | 2.352 |
| I-395, held out | 0.595 | 0.582 | 0.811 |
| A39, held out | 0.817 | 0.714 | 0.813 |

Taking the minimum is worse than ignoring the target lane at three of four sites. `hu_two_leaders` does take it, though only over part of the state space, so its measured weight stays low.

### E. How often do they hold parallel, and for how long?

Continuous overlap with one target-lane car. "Locked" means at least 3 s with mean speed difference under 0.5 m/s. MEASURED.

| | Episode p50 / p90, s | ≥5 s | ≥10 s | Locked | Mean speed difference p50, m/s | Longest per car p50 / p90, s |
|---|---|---:|---:|---:|---:|---|
| I-80 must-change | 2.5 / 13.4 | 33% | 15% | **6.8%** | 1.56 | 8 / 22 |
| I-80 through | 2.5 / 7.5 | 21% | 6% | 1.1% | 3.28 | 11 / 20 |
| I-395 must-change | 2.5 / 9.5 | 26% | 10% | 2.9% | 4.14 | 7.5 / 17 |
| I-395 through | 2.5 / 8.0 | 23% | 7% | 1.0% | 3.71 | 7 / 16 |
| US-101 must-change | 1.5 / 3.0 | 4% | 0.3% | 0 | 6.30 | 2 / 4.5 |
| US-101 through | 3.0 / 9.5 | 30% | 9% | 1.8% | 2.47 | 10 / 19 |
| A39 must-change | 0.9 / 2.1 | 0.8% | 0.2% | 0 | 8.40 | 1.3 / 2.5 |
| A39 through | 0.9 / 1.7 | 0.8% | 0.2% | 0.1% | 9.69 | 1.3 / 2.9 |
| I-294 through | 5.0 / 19.5 | 53% | 26% | 1.8% | 2.97 | 9.5 / 32 |
| **Simulator, I-80 scene** | 3.5 / 16.5 | 36% | 19% | 4.0% | 2.16 | **16.5 / 41** |
| Same, last 110 m only | 4.0 / 14.4 | 45% | 22% | 7.1% | 1.51 | 5 / 16 |
| **Simulator, free flow** | **10.5 / 17** | **83%** | **55%** | **47%** | **0.52** | 12.5 / 17.5 |

Share of time overlapped before the sideways start, −10 to −5 s and −5 to 0 s: I-80 58%, 46%. I-395 49%, 45%. US-101 39%, 42%. A39 2%, 1%. **Simulator I-80 scene 34%, 12%. Free flow 23%, 3%.**

- **In a queue, parallel is normal.** At I-80 and I-395, cars that must merge sit alongside as much as or more than through cars. At I-80 their speed difference is half a through car's (1.56 against 3.28 m/s). At I-395 it isn't overall, but in long episodes it narrows from 2.76 to 1.96 m/s while through cars stay at 2.6-2.7. Not at US-101 or the A39, where they pass through quickly.
- **In queues the simulator's fault is the opposite of Erik's report:** in the last 5 s it clears the overlap before moving (12%) where real cars do not (45%).
- **Free flow is Erik's complaint, at full strength.** The free-flow scene gives 47% locked against 0-7% for every real set, and 0-2% away from queues. Cause: cars have the same desired speed in that scene (`speedDev="0"`), its ramp lane is 1,096 m long, and it has no speed difference to resolve. So **part of what Erik saw may be the scene** and the demand files. Check what his clip used.

### F. Sideways before the gap exists

Share overlapped with a target-lane car at each stage, must-change cars. In brackets the share with more than 1.5 m of overlap, which is the safe reading for I-395. MEASURED.

| Site, n | Sideways start | Body over line | Centre over line | Label flips, all cars |
|---|---:|---:|---:|---:|
| I-80, 297 | **32%** (16%) | 14% (5%) | 4% (0.3%) | 17% |
| I-395, 1,663 | **41%** (29%) | 35% (23%) | 22% (13%) | 27% |
| US-101, 221 | **13%** (7%) | 3% (2%) | 0.5% (0) | 0 |
| A39, 2,000 | 0.4% | 0.5% | 0.1% | 0 |
| **Simulator, all scenes** | **0** | **0** | **0** | **0** |

95% CI at the start: I-80 27-37%, I-395 39-43%, US-101 9-18%. Discretionary changers behave alike: 30%, 37%, 12%, 2%, I-90 49%, I-294 8%.

**How far they edge in** while overlapped, as a share of lane width: I-80 median 0.13, p95 0.37. I-395 0.12, 0.39. US-101 −0.02, 0.19. A39 −0.04, 0.21. **Simulator 0.** About 0.45 m typical, up to 1.3 m. Going back after edging is rare: 0.1-2.7%.

**Gaps at the start against the middle of the crossing**, median, and lower quartile, in metres:

| Site | Lag at start → centre over line | Lead at start → centre over line | Lag p25 start | Lead p25 start | Lag time-gap p25, s |
|---|---|---|---:|---:|---:|
| I-80 | 4.4 → 6.0 | 3.0 → 5.5 | 1.6 | 0.5 | 0.47 |
| I-395 | 7.4 → 10.0 | 5.4 → 7.4 | 2.1 | 0.05 | 0.30 |
| US-101 | 5.7 → 10.6 | 11.6 → 8.7 | 3.0 | 5.2 | 0.30 |
| **Simulator I-80 scene** | 8.9 → 9.7 | 9.2 → 10.5 | **6.7** | **6.5** | **1.26** |

So **a real gap is about half made when the car starts to move.** Median growth over the crossing, same pair of neighbours: I-80 lag +1.0 m, lead +1.6 m in 4.3 s. I-395 +1.4, +2.8 in 2.9 s. US-101 +3.4, −2.3 in 2.3 s (rolling forward into the gap). Simulator +0.5, +0.7 in 1.5 s, because its gap is already there. Its lower-quartile lag at the start is two to four times the real one, and its lead gap more than that.

**Who makes the room, when the body reaches the line with lag under 1 m?**

| Site, n | Lag at body over line → label | Follower slows by >0.3 m/s | Merger gains >0.3 m/s | Merger's speed advantage |
|---|---|---:|---:|---:|
| I-80, 101 | 0.06 → 1.35 in 1.5 s | 25% | 32% | 0.67 m/s |
| I-395, 384 | −1.39 → −0.71 in 1.0 s | 11% | 57% | 0.78 m/s |
| I-90, 29 | −0.09 → 0.68 in 0.5 s | 21% | 28% | 0.48 m/s |
| Simulator | under 1 m: 2 cases of 1,064 | | | |

**The room comes mostly from the merger already moving faster than the follower, not from the follower braking.** Followers slow no more often here than at lag 1-5 m (I-80 25% against 34%, I-395 11% against 11%, I-90 21% against 20%). This qualifies Erik's "forced to slow down": it happens, but mostly at larger gaps while closing, not when nosed in. See G.

### G. The follower

For each change, the target-lane follower is compared with **cars in the same state that have an adjacent car ahead that does not change lane**: same speed, same lag, same closing speed, same gap to their own leader, and the same behaviour by that leader next. Aligned on the merger's body reaching the line. "Lost" is extra speed lost from −1 to +4 s, m/s. "Extra responders" is the share losing more than the control's top 20%, minus 20%. MEASURED.

| Site | n | Extra speed lost (95% CI) | Extra responders, points | Extra acceleration 0-3 s, m/s² | Starts, s relative to body over line |
|---|---:|---|---:|---|---:|
| I-80 | 1,744 | **0.50** (0.43, 0.59) | **+15.6** | −0.11 (−0.14, −0.10) | −1.0 |
| US-101 | 999 | **0.62** (0.50, 0.72) | **+15.5** | −0.14 (−0.16, −0.12) | −1.0 |
| I-294, held out | 375 | **0.49** (0.25, 0.76) | **+14.1** | −0.12 (−0.19, −0.06) | −0.5 |
| I-90 moving, held out | 243 | 0.20 (−0.04, 0.41) | +15.0 | −0.04 (ns) | none clear |
| I-395 whole site, held out | 2,554 | −0.19 | +5.8 | +0.04 | biased, below |
| I-395 ramp cars, controls on the same stretch | 81 | 0.42 (0.02, 0.83) | +13.3 | −0.09 (−0.17, 0.00) | |
| A39 all, held out | 4,109 | −0.04 (−0.08, 0.00) | +0.7 | 0.01 | none |
| A39 ramp merges | 232 | 0.31 (0.16, 0.48) | +8.9 | −0.06 (−0.10, −0.03) | |
| **Simulator, I-80 scene** | 1,026 | **−0.37** (−0.49, −0.23) | +6.1 | **+0.08** | |
| **Simulator, open merge** | 1,148 | **−0.53** | +0.7 | +0.11 | |
| **Simulator, free flow** | 493 | **−1.04** | −1.7 | +0.21 | |

Against report 14's "about 1 in 16": that one used a different control and flagged a follower that opened 2 m or 15% against its own leader over 4 s. This one asks who lost unusually much speed, aligned on the sideways motion, against same-state cars. 1 in 7 here is a stricter comparison on a broader question. The two don't contradict each other, and the mean is still small either way.

I-395's whole-site row is biased: the ramp cars cluster where the target lane is speeding up out of a queue, and controls come from the whole site. Same-stretch controls are few (29), so the 81-car row has a wide interval.

**What it depends on.** Extra speed lost, then extra responders.

| Merger relative to follower | I-80 | US-101 | I-395 | I-90 | I-294 | A39 | Simulator |
|---|---|---|---|---|---|---|---|
| Follower closing, over 1 m/s | **1.38**, +33 | **0.87**, +18 | **0.85**, +26 | **1.31**, +42 | 0.73, +21 | 0.22, +7 | 1.83, +43 |
| Within 1 m/s | 0.47, +15 | 0.70, +16 | −0.10, +6 | 0.44, +18 | 0.98, +19 | −0.47, −4 | −0.05, +7 |
| Merger pulling away | −0.31, 0 | 0.31, +13 | −0.88, −4 | −0.73, −4 | 0.21, +10 | −0.17, −4 | −2.31, −17 |

By follower speed at I-80: under 2 m/s −0.28, 2-5 m/s 0.24, 5-10 m/s 0.51, 10-15 m/s **1.76** (+39). By lag at I-80: under 0: 0.24, 0-2 m: 0.12, 2-5 m: 0.26, 5-10 m: 0.51, 10-20 m: **0.85**, over 20 m: −0.10. US-101: 2-5 m **1.28**, 5-10 m 0.77, 10-20 m 0.71, over 20 m −0.10.

**A formula that held out.** Let `own` be plain following of its own leader, `mer` plain following of the merger, `asked = min(mer − own, 0)`. The follower does `own + w · asked`. Fit on I-80 and US-101, from the body reaching the line. RMSE of next-second acceleration, m/s². MEASURED.

| Site | Ignores merger | Follows merger fully | Flat w 0.62 | Taper, below | Site's own w |
|---|---:|---:|---:|---:|---:|
| I-80 | 0.875 | 0.817 | 0.764 | **0.750** | 0.60 |
| US-101 | 0.822 | 0.732 | 0.705 | **0.689** | 0.68 |
| I-395, held out | 0.797 | 0.913 | 0.742 | **0.692** | 0.39 |
| I-90, held out | 0.873 | 0.847 | 0.785 | **0.763** | 0.55 |
| I-294, held out | 1.014 | 0.992 | 0.959 | **0.954** | 0.56 |
| A39, held out | 0.693 | 0.713 | 0.628 | **0.618** | 0.47 |
| **Simulator, I-80 scene** | 0.682 | 0.508 | | | **0.95** |
| **Simulator, open merge** | 0.730 | 0.579 | | | **0.85** |
| **Simulator, free flow** | 0.798 | 0.566 | | | **0.76** |

Taper: `w = 0.756 · clamp(0.2 + lag / 5, 0.2, 1) · (0.5 if closing over 3 m/s, else 1)`. Measured weight by lag, I-80, I-395, I-90: lag under 1 m 0.17, 0.15, 0.24. 1-3 m 0.46, 0.20, 0.39. 3-6 m 0.65, 0.34, 0.75. 6-10 m 0.68, 0.44, 0.65. By closing over 3 m/s: 0.34, 0.23, 0.0. It also ramps in: 0.51 in the first second at I-80, 0.70 by the fourth.

- **It beats both extremes on every held-out site.** Following the merger fully is worse than ignoring it at I-395 and the A39.
- **Simulated followers give way almost fully, at 0.76-0.95, against a real 0.39-0.68.** That fits let-in being too high at 83-88%, but this was not run in closed loop, so it is not yet shown to be the cause.
- **A close follower barely responds.** This is the opposite of a hold-back rule for close cars. A car 2 m behind can't do much, and if it brakes, the queue behind pays.

**The time series**, extra acceleration m/s² by seconds from the body reaching the line, in steps of 1 s: I-80, −4 to +6: 0.08, 0.12, 0.04, −0.05, −0.09, −0.16, −0.09, −0.11, −0.04, 0.00, −0.01. Full curves per site with standard errors are in `merging/follow_*.json`.

### H. Blinkers

**None of these datasets records them.** What can be said:

- **Timing, from tracks.** On the sites where the start can be read, follower response starts 0 to 1.5 s after the sideways start (I-80 +0.5, US-101 0, I-294 +1.5), and extra acceleration in the 3 s before it is not negative (+0.11, +0.03, +0.05). MEASURED.
- **From Gothenburg**: [Jokhio et al.](https://arxiv.org/pdf/2305.16401), 103 drivers, read: signal before the start in about 60%, after it in 33%, never in 7%. Median blinker to start 0.7 s.
- **Together.** A follower reacting to a blinker on 0.7 s ahead, with a 1-2 s reaction, and one reacting to sideways motion with a 0.5 s reaction, look identical. **The tracks can't separate them.** But there is no sign of an early response seconds ahead of the motion.
- **Signal use is lower than the model's 93% reads.** That 93% includes the 33% who signal only after starting. Advance signal is 60%. In NHTSA's commuter study ([Lee, Olsen, Wierwille 2004](https://rosap.ntl.bts.gov/view/dot/4191/dot_4191_DS1.pdf), summary read), signals came on 44% of lane changes, 48% left and 35% right, ranging from 0 to 92% between drivers.
- **No field study of blinker state and follower response was found** after two further searches, one extended. Closest: lab and simulator studies in report 14 (Jokhio TRF, Li 2025, Haar 2022, Kitahara 2025). A US-based [Safety Pilot paper](https://pubs.lib.uiowa.edu/driving/article/28351/galley/136643/view) blocked my fetch, UNVERIFIED.

**Consequence for the spec:** no blinker-only yield. Keep a blinker flag and a switch with zero default effect, until data says otherwise.

### I. Transfer: when does the sideways motion start?

Per-second chance of the body reaching the line. Fit on **I-80 and US-101**, then scored on sites never seen. Log likelihood per car, higher is better, and predicted against real quartiles of metres left. MEASURED.

| Urgency form | I-395 | A39 | I-395 predicted (real 17, 28, 40) | A39 predicted (real 299, 319, 328) |
|---|---:|---:|---|---|
| Distance alone | −2.68 | −3.72 | 35, 47, 56 | 178, 324, 377 |
| Distance + gaps in metres | −2.57 | −5.05 | 36, 48, 56 | 322, 363, 393 |
| Gaps in seconds, no urgency | −2.73 | **−2.71** | 36, 48, 56 | 324, 370, 401 |
| **Time to the end + gaps in seconds** | **−2.32** | −3.32 | 31, 43, 53 | **295, 333, 385** |
| LMRS desire + gaps in seconds | −2.54 | −3.40 | 31, 44, 54 | 281, 331, 384 |

That is scored only inside the merge zone. **Over the whole lane, without the zone, distance collapses:** A39 −7.36 and predicted median **0 m**, against time −3.53 and predicted 327 m. On I-395 distance predicts 77 m and time 74 m, against a real 29 m.

- With time to the end, the driver has the same urgency on a slow lane and a fast one. Fitted law: `logit p = −1.23 − 1.544 · tte/10 + 0.133 · tlag + 0.164 · tlead`, tte in seconds, capped 60; tlag and tlead are time gaps clipped to −3..8.
- **It does not fully pass.** Leaving one site out, gap-only is slightly ahead on total log likelihood (−11.93 against −12.59), because A39 drivers mostly take the first gap and I weigh this as a close rival. I chose the time form for its A39 position and for I-395. Every form still merges I-80 drivers too early inside the zone (predicted median 39-43 m, real 6 m), and I-395 15-20 m early. Something holds drivers near the end at I-80 that this doesn't capture, likely the same missing lane line: with no line, there is nothing to cross until the lane has narrowed.
- **Gap coefficients are small.** Gap size barely moves the start decision. This agrees with report 16's finding that Lee's gaps aren't what binds.

## 3. Law and instruction

[Trafikförordningen (1998:1276)](https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/trafikforordning-19981276_sfs-1998-1276/), chapter 3, read at Riksdagen.

| § | Text | What it means for the model |
|---|---|---|
| **43 §** | "En förare får ... byta körfält ... endast om det kan ske utan fara eller onödigt hinder." "En förare som uppmärksammar att någon annan förare avser att köra in i det körfält han eller hon färdas i skall anpassa hastigheten så att inkörningen underlättas." | **The follower has a legal duty to help** once it notices. It is a stated rule, not a right of way |
| **44 §** | "Om två körfält löper samman till ett skall förarna under ömsesidigt hänsynstagande anpassa sig till de nya förhållandena." | Lanes that join: mutual consideration. **No statute says zipper** |
| **23 §** | "En förare som färdas i ett accelerationsfält skall anpassa hastigheten till trafiken i det körfält som han eller hon avser att köra in i. Föraren skall lämna accelerationsfältet så snart det kan ske utan fara eller onödigt hinder." | **Speed matching is the law**, and leaving **early** is too. The opposite of a late merge |
| **21 §** | Without an acceleration lane, the one entering has väjningsplikt | Keep as a yield line |
| **9 §** | With dense queues in all lanes, only drivers in the rightmost lane may change lane, except to stop or park, or to position for a junction | Not modelled. Should be, for Sweden, with unknown compliance |
| **65-66 §§** | Signal in good time; signalling doesn't give a right to the manoeuvre | Supports no automatic yield to a blinker |

- **Zipper.** [Vi Bilägare](https://www.vibilagare.se/bilfragan/bilfragan-blixtlasprincipen-vid-farthinder) says no statute prescribes the zipper or alternating method, and only additional signs recommend it. [Sign F25](https://www.transportstyrelsen.se/sv/vagtrafik/trafikregler-och-vagmarken/vagmarken/lokaliseringsmarken-for-vagvisning/korfalt-upphor/) marks a closed lane with no driver instruction on the page. Germany's StVO § 7(4) (report 14) does require alternating immediately before the narrowing. So Germany and Sweden may differ in law.
- **Acceleration lanes.** [Vi Bilägare quoting Transportstyrelsen](https://www.vibilagare.se/bilfragan/vad-galler-vid-pafarten-till-motorvagen): the main responsibility is on the driver entering, nobody has väjningsplikt, and the same rules apply as for an ordinary lane change. Help from motorway drivers is "en bonus, inte något man ska ta för givet".
- **Driving school.** [Zutobi's course](https://zutobi.com/se/bil/motorvag-motortrafikled) gives five steps: signal in good time, adapt speed, find a gap, check mirrors and blind spot, leave the acceleration lane when you can. Also that main-lane drivers can help by moving left. This is what Erik describes. I did not reach Trafikverket's own material, UNVERIFIED.
- **Compliance. No Swedish measurement found.** US work zones (report 14): drivers merge early regardless of the lane control strategy, and closed-lane use is under 15% at 940 veh/h. The [Iowa pooled-fund study](https://swzdi.intrans.iastate.edu/wp-content/uploads/2025/01/improving_effectiveness_zipper_merge_w_cvr.pdf) says familiarity and comfort drive behaviour. Forum accounts in Sweden conflict and I don't use them.

## 4. The spec

Scope: `MODEL_HUMAN`, must-change wishes (`LCA_URGENT`) unless stated. No GPU kernel gets a function-local array; all of this runs off `LcNeighbors`, which already holds target leader and follower. Names are proposed `--tune` and `--human-off` entries.

### State

| Field | Size | Use |
|---|---|---|
| `lc_bias: f32` in `Veh` and its `world.rs` twin | 4 B | Extra acceleration this driver wants (rule B5, B6), written by `lc_evaluate`, read by the human step, cleared when the wish ends |
| `lc_edge: f32` | 4 B | Sideways offset before the lane commit (rule B3), so the car can be partly over without owning the target lane |

Per-driver draws by `h01(trip, k)`: free. Cost is a handful of float operations per car with a wish, per step. Check `#[repr(C)]` padding before adding.

### Behaviours

**B0. Scenes, before any tuning. ADAPTED.** Test scenes must copy the site: at I-80 and I-395 a wide lane that narrows, where a merge counts as the centre crossing the imaginary line (merge zone 54 m and 63 m), parallel 216 m aux lane at US-101 with the ramp 3-6 m/s faster, an A39 acceleration lane with a slower ramp. Real spread of desired speeds, not `speedDev="0"`: A39 p5-p95 26-48 m/s is the only measured range here, report 05. Otherwise every target below is unfair. Stockholm's real shape comes from the net and is not this report's job, but **if a real lane drop in the net is drawn as a long parallel lane with no merge zone, these numbers will not fit it.**

**B1. Urgency by time to the end. ADAPTED** (LMRS form, [OpenTrafficSim](https://github.com/averbraeck/opentrafficsim); fit here). Replaces distance in `hu_urgency` and in the `d` term of `hu_critical_*`.

```wgsl
fn hu_tte(e: Veh) -> f32 {
    let rem = max(e.best_cur - e.pos, 0.0) / f32(max(1, abs(unpack_off(e.best_off))));
    return min(rem / max(e.speed, 1.0), 60.0);
}
// urgency for anything that shrinks with it
let u = clamp(1.0 - hu_tte(e) / TTE0, 0.0, 1.0);      // TTE0 = 43 s, LMRS's t0
```
Waiting time stays out: report 14 found no effect, and this is time *left*, not time waited.

**B2. Start decision. ADAPTED** (form from Lee and Choudhury's per-second gap decision; coefficients fit here on I-80 and US-101). Replaces the shifted Lee critical gaps, which report 16 showed don't bind anyway. Physical floor stays separate.

```wgsl
let lag  = n.f_gap + ft.min_gap;   let lead = n.gap + ty.min_gap;
let tlag  = clamp(lag / max(n.f_speed, 1.0), -3.0, 8.0);
let tlead = clamp(lead / max(e.speed, 1.0), -3.0, 8.0);
let eta = S0 + S_T * hu_tte(e) / 10.0 + S_LAG * tlag + S_LEAD * tlead;
let p_step = 1.0 - pow(1.0 - 1.0 / (1.0 + exp(-eta)), dt);
let want = h01(e.trip ^ pcg(step), 31u) < p_step;
```
`S0 −1.23, S_T −1.544, S_LAG 0.133, S_LEAD 0.164`. Fit on the body reaching the line, so a car using this as its sideways start will be about 1-2 s early. Tune `S0` only, in closed loop, and report the shift. A driver term, as Lee and Choudhury have, stays per-driver: `S0 + 0.5 · logit01(h01(trip, 37u))`, **INVENTED** size.

**B3. Sideways before the gap exists. ADAPTED** (Choudhury's anticipated gap; Ahmed's forced merge continues once begun; size measured). Two stages:

1. *Edge.* When `want` is true and speed is under `V_EDGE`, the car drifts sideways by up to `q_edge · W` in `lc_edge`, staying in its lane's label. No shadow, no target-lane ownership.
2. *Commit.* Change label and start the existing change when the **anticipated** gaps pass, from `lag_a = lag + (v − vF)·τ + ½(a − aF)·τ²`, `lead_a` likewise.

```wgsl
let tau = TAU_A_MEAN + TAU_A_SD * hu_normal(e.trip, 33u);   // 1.87, 1.44, clamped 0..4. Choudhury eq. 5.39
let lag_a  = lag  + (e.speed - n.f_speed) * tau + 0.5 * (e.acc - n.f_acc) * tau * tau;
let lead_a = lead + (n.speed - e.speed) * tau + 0.5 * (n.acc - e.acc) * tau * tau;
let go = lag_a >= floor_lag && lead_a >= floor_lead;       // floors below
```

- `q_edge`: per-driver lognormal, median 0.13, log-SD 0.65, so p95 0.38. Magnitude MEASURED, shape **INVENTED**.
- `V_EDGE` 15 m/s. Overlap at the start is 32-41% at 4-7 m/s (I-80, I-395), 13% at 14 m/s (US-101), under 2% at 25-34 m/s (A39). I-294, mixed speeds, 8%. ADAPTED.
- Cap sideways offset at `W − width − 0.2`, keeping 0.2 m to a car alongside. **INVENTED.**
- Floors at commit: certificate × `lc_safety` as now, evaluated on anticipated speeds, down to `S_MIN`. A real lane change with lag under 1 m at body-over-line happens only with the merger faster than the follower: require `e.speed >= n.f_speed` when `lag < 1.0`. MEASURED. Physics must still not overlap: if real bumpers overlap, the commit waits.
- **Going back**: at most 3%, MEASURED. Abort if the anticipated gap falls below zero while edging, and cool down 2 s. **INVENTED.**
- **Why not just shrink the gaps?** Because a smaller gap test still has no sideways stage, no pressure on the follower, and no visible nosing.

**B4. Stop near the end. ESTABLISHED** (LMRS "never stop before we can actually merge", OpenTrafficSim `Synchronization.PASSIVE`; offset stops already from Trafikverket). Don't brake for a target leader so hard the car stops before the merge zone. Keep the current offset stop points.

**B5. Speed match. ADAPTED** (LMRS and Aimsun name the mechanism; both use a minimum, which fails on tracks). Replaces the `min(planned, adapted)` in `hu_two_leaders`.

```wgsl
if (lead > 0.0 && lead < 60.0) {
    let a_tgt = hu_target(e.speed, lead, n.speed, vmax, hu_s0);
    let diff = a_tgt - e.acc;
    if (diff < 0.0) { lc_advice(e.trip, e.speed + (e.acc + W_S_NEG * diff) * dt); }   // brake side
    else { bias += W_S_POS * diff; }                                                  // speed-up side, through lc_bias
}
```
`W_S_NEG` 0.12 (fit on I-80, US-101, own-site range 0.08-0.23). `W_S_POS` 0.25 (median of the four sites: 0.24, 0.84, 0.07, 0.26; **no held-out test**, ADAPTED and flagged). Guard and own following still apply, so `lc_bias` can never push through a leader. Clamp to ±0.8 m/s². **INVENTED** clamp.

**B6. Gap steering. ADAPTED** (Toledo's and Hidas's target gap; form is mine; size MEASURED).

```wgsl
let l = clamp(lag, -10.0, 60.0); let d = clamp(lead, -10.0, 60.0);
bias += K_C * clamp((d - l) / (abs(d + l) + 5.0), -1.0, 1.0);    // only if hu_tte(e) < 30 s
```
`K_C` 0.05 (I-80 0.076, I-395 0.030). Nothing explicit about choosing a gap ahead or behind: **C shows that comes from lane speed**, so B5 and B6 should produce it. Check against the C table. If they don't, add Choudhury's forward or backward gap choice as a separate rule.

**B7. Follower response. ADAPTED** (mechanism: Vissim's cooperative braking below a limit, LMRS's relaxed following of the merger; numbers fit here and held out on four sites). Replaces the share and `hu_request`'s decision. In the requester's kernel, once the merger's sideways offset is at least 10% of a lane (or commit), plus `T_F`.

```wgsl
let mer = hu_target(vf, max(lag, 0.5), e.speed, limit, ft_s0);   // follower's own law, on the merger
let asked = min(mer - n.f_acc, 0.0);
let gl = clamp(0.2 + lag / 5.0, 0.2, 1.0);
let gc = select(1.0, 0.5, vf - e.speed > 3.0);
let wd = W_F_DRIVER(n.f_trip);
let a_new = n.f_acc + W_F * wd * gl * gc * asked;
lc_advice(n.f_trip, vf + max(a_new, -B_F) * dt);
```
- `W_F` 0.756, MEASURED and held out.
- `T_F` 0.5 s. Response starts 0-1.5 s after the 10% point, MEASURED.
- `B_F` Vissim's 3 m/s². ESTABLISHED.
- `W_F_DRIVER`: mean 1, spread **INVENTED**. Uniform 0.3-1.7 to start. A per-driver term can't be measured from anonymous tracks. A mixture fit reads a responding share of 0.65-0.86, weakly identified.
- `cooperation` becomes unused. Let-in and passes then have to emerge. If they don't, say so, and don't bring the share back without data.
- Sweden 43 §: the same rule. Law says it should happen; tracks say how much.

**B8. Blinker. ADAPTED, off by default.** Keep `P_SIG` flag. 60% signal before the start, 33% after, 7% never (Jokhio). The only effect now is on rendering and on measuring. A blinker-only yield is a `--tune` switch at 0: no field evidence for it.

**B9. Relaxation after the cut-in. ESTABLISHED, stays.** Report 16's item passes.

**B10. Region rules, `--region sweden`. ESTABLISHED as law, compliance unknown.** 3 kap. 9 §: in dense queues in all lanes, a discretionary change is allowed only from the rightmost lane, with a compliance share. **INVENTED** compliance. 23 §: no change, since B1 already produces the early merge at speed. 44 §: no zipper rule is imposed; offset stops remain.

### Build order

Small to big, one job at a time, dt 0.5 and 0.1, with each rule switchable. On software GPU first.

1. B0 scenes and the measuring pipeline on simulated traces: `scripts/merging/mg_sim.py` and `mg_events.py` already read `--fcd`.
2. B1 and B2. Check section B.
3. B7. Check section G, then let-in.
4. B3. Check section F. Then crash and contact checks on all scenes.
5. B5, B6. Check sections C, D, E.
6. Whole table below. Then a road with a real lane drop. Only then a city.
7. Ablation: off one at a time, listed in `HUMAN.md`. Sensitivity on every INVENTED number, as report 16 does.

## 5. Acceptance targets

Train: I-80, US-101. **Held out, not to be tuned on: I-395, A39, I-90, I-294.** Tune against train scenes, then report held-out results once. Any band is the real value with its uncertainty, and a miss is reported as a miss. "Now" is the `accept3` build on the parallel scene, so it isn't a fair baseline until B0 is done. Traces at dt 0.5, trace sampled at 2 Hz or better.

| # | Measure | I-80 train | US-101 train | I-395 **held out** | A39 **held out** | Now (I-80 / free scene) |
|---:|---|---|---|---|---|---|
| 1 | Body over the line, metres left, median | 7 ± 10 | 138 ± 30 | 31 ± 10 | 325 ± 40, on its lane end | 108 / 98 |
| 2 | Stopped below 1 m/s first | 26% ± 8 | 0-2% | 0-3% | 0-1% | 21% / 0 |
| 3 | Overlap at sideways start | 32% ± 8 | 13% ± 6 | 41% ± 10, allow 29-41 | under 2% | **0** / **0** |
| 4 | Overlap at centre over line | 4% ± 4 | under 2% | 22% ± 10, allow 13-22 | under 1% | 0 / 0 |
| 5 | Lower quartile lag at start, m | 1.6 ± 1 | 3.0 ± 1 | 2.1 ± 1 | n/a | **6.7** / 37 |
| 6 | Edge distance while overlapped, median, p95, lanes | 0.13, 0.37 | 0, 0.19 | 0.12, 0.39 | 0, 0.21 | **0, 0** |
| 7 | Gap position 5 s before start, ahead / behind | 19 / 27 ± 8 | 62 / 4 ± 10 | 9 / 40 ± 8 | 1 / 24 ± 10 | **0** / 21; 0 / 1 |
| 8 | Episodes ≥5 s, locked share | 33%, 6.8% | 4%, 0 | 26%, 2.9% | 0.8%, 0 | 36%, 4.0%; **83%, 47%** |
| 9 | Time overlapped in last 5 s before start | 46% ± 10 | 42% ± 10 | 45% ± 10 | 1% ± 2 | **12%**; 3% |
| 10 | Excess acceleration −2 to 0 s before start, m/s² | +0.17 ± 0.08 | −0.42 ± 0.15 | −0.10 ± 0.06 | +0.52 ± 0.1 | −0.03 |
| 11 | Weight on target leader, must-change minus through car | 0.04 | 0.16 | 0.12 | 0.48 | through scene needed |
| 12 | Speed-up weight | 0.24 ± 0.1 | 0.84 ± 0.3 | 0.07 ± 0.05 | 0.26 ± 0.1 | **−0.03 to 0.11** |
| 13 | Follower extra speed lost, m/s | 0.50 ± 0.1 | 0.62 ± 0.15 | 0.42 ± 0.4, same stretch | ramp 0.31 ± 0.2 | **−0.37** |
| 14 | Follower extra responders, points | +15.6 ± 3 | +15.5 ± 4 | +13 ± 8 | ramp +9 ± 6 | +6 |
| 15 | Follower weight `w` | 0.60 ± 0.1 | 0.68 ± 0.1 | 0.39 ± 0.1 | 0.47 ± 0.1 | **0.95**; 0.76 |
| 16 | Lag under 1 m at body over line, share of changes | 4.7% ± 2 | under 2% | 10.7% ± 4 | 0 | **0.2%** |
| 17 | Lane change 10-90 time, peak lateral speed | Report 05 bands | | | | pass (report 16) |
| 18 | I-80 lane-end let-in, passes, waits, turn order | Report 14 bands, kept | | | | let-in, passes **fail** |

Also: I-294 and I-90 follower, rows 13-15, on a multi-lane moving scene: I-294 lost 0.49 ± 0.25, +14; I-90 lost 0.20 ± 0.25, +15. None of this goes through the validation gate on its own: passing here is a road-scale result. Network checks in `VALIDATION-GATE.md` are still what count.

**Safety checks that must not get worse:** overlaps under 0.5% of windows, guard use under 1% of steps, no collisions at a lane end, no teleports. Report the contact count on the I-395-shaped scene first, since B3 is the rule most likely to create them.

## 6. Clips

Render with `cars record` and `cars shot` from the simulator, and from a track replay for the real one, same camera, same scale, top-down at 5× zoom, with lane lines. A track replay of real data needs a small converter from the cache to `cars replay`'s input, which doesn't exist yet.

| Clip | Shows | Real event: site, id, crossing time in s from run start (ids from `mg_cache.py`) | Should look like |
|---|---|---|---|
| Nose-in at crawl | Rule B3 | I-395 run 0: 556 at 41.0 s, 571 at 58.2 s. I-80 run 0: 68 at 82.4 s, 202 at 138.0 s. I-80 has no lane line, so draw the imaginary line | Sideways begins with a car still overlapping, room opens as the merger rolls ahead. No stop-and-jump |
| Rolling into a slower lane | B5 | US-101 run 0: 92 at 1,839.7 s, 165 at 33.5 s. I-395 run 0: 901 at 279.5 s | Runs fast, slows just before crossing to match the target car |
| Speeding up to a faster lane | B5, speed-up side | A39 ramp: 100 at 25,239.4 s (26.6 to 30.7 m/s), 135 at 25,288.4 s. I-395 run 0: 553 at 39.0 s | Accelerates through the crossing |
| Follower slows | B7 | I-80 run 0: id 220 with follower 219 at 143.0 s, 372 with follower 379 at 206.2 s. I-395: 543 with 542 at 24.5 s | Follower eases off about a second before the body crosses |
| Close follower doesn't brake | B7 taper | I-80: run 0, id 1184 with follower 1193 at 570.5 s; run 1, 2094 with 2095 at 929.9 s. I-395 run 0: 581 with 583 at 59.7 s | No hard brake, gap opens because the merger is faster |
| Free-flow parallel, before and after | B0, B1, B5 | `accept3/rest/merge_free`, compared with A39 ramp | Before: cars lock alongside for 10+ s. After: passes through in 1-2 s |
| Lane end, whole | Everything | I-395 whole lane end, 5 minutes from s 400 to 520 | Many crossings in the last 60 m, cars side by side, and no one stopped |

Each clip gets a caption with what it shows and which measured number it should match. A clip is not a test: row numbers in section 5 are.

## 7. What can't be known yet

| Question | Data that would answer it | Who |
|---|---|---|
| Does a blinker alone make the follower slow, before any sideways motion? | **SHRP2 NDS** or **UDRIVE**: instrumented cars with signal state and forward and side video. Follower must be seen from a rear camera, or the instrumented car must be the follower seeing a signal ahead | Erik applies |
| Does one driver yield or force consistently? | SHRP2 or UDRIVE: repeat trips | Erik |
| Refusal against never asked | Same, with eye or gaze data. Lab work for now | Erik |
| A second, clean, German merge, with maps | **exiD** seven sites. **highD** for lateral on cleaner geometry | Erik: form |
| Swedish compliance with zipper and 43 § | Nothing open. A camera at a real Stockholm lane drop, an hour in a peak, could count order and stops | Erik: he could film it from a bridge, subject to the rules on filming people |
| Heavy urban queues, lane change into a standing lane | Nothing good open here: CitySim or NGSIM-class data with long queues | Erik: form for CitySim |

Access routes are in report 05, section 11.

**Drafts for Erik.** Short. He sends them himself. Facts to check before sending: the contact person and form fields, whether it's for non-commercial research, and the project description.

*exiD and highD form, purpose field:*

> I'm building an open traffic simulator as a personal research project. I want to use exiD and highD to test how drivers merge at motorway ramps and how the car behind responds. I need trajectories and lane data only. It's non-commercial and I won't redistribute the data.

*UDRIVE or SHRP2 data request:*

> Hi, I work on a traffic simulator and I'm trying to find out if a turn signal changes what the car behind does in a lane change. Open trajectory data has no signal state, so I can't test it. Could I get access to lane change events with signal state and follower behaviour, or is there already a study on this I should read? I only need event-level data. Thanks, Erik

## 8. Caveats on this work

- **The simulator traces are older than the current build** and were recorded at low rate. Their follower "lost" is relative to controls drawn in the same scene, with fewer real interactions. Weights and overlaps are safe to compare; treat speed-lost as indicative.
- **NGSIM noise.** Lateral position is noisy at I-80 and US-101, smoothed 1 s. So an edge distance of 0.13 lanes is near the noise at I-80. I-395 from TGSIM agrees at 0.12.
- **I-395 overlap is overstated** by default car length. I give the 1.5 m allowance beside it.
- **I-395's "whole-site" follower row is biased**, and the same-stretch row is thin.
- **A39 lanes and lane ends are reconstructed**, and its distances are rough. Its discretionary "premax" share is lane-label noise and I don't quote it.
- **Scenes differ by more than behaviour**: time-of-day, country, truck mix. Four sites can't separate those.
- **Open loop.** Every formula here is tested on observed states, not in a simulation. Closed-loop behaviour can differ, as report 16 found with Lee.
- **The gap-steering placebo is imperfect**: through cars on the far side see the same lane but not the same geometry.
- **Merge-zone lengths are read from vehicle paths**, not from road plans.
- **Licence.** DLR A39 is CC BY-NC-SA, and Erik's decision on non-commercial sources (report 05) applies. A39 enters one spec number: `W_S_POS`, the median of four sites including it. Everything else is fit on I-80 and US-101, and A39 is a held-out check. I-80 and US-101 are CC BY-SA in DOT's metadata, TGSIM CC0.

## 9. Dead ends

- `repository.tudelft.nl` refuses connections from here. [Wayback](https://archive.org/wayback/available?url=repository.tudelft.nl/file/File_03abfeb9-d9a7-4904-9e7d-8a31c3166d83) has none. Read LMRS through the OpenTrafficSim source.
- ScienceDirect and Elsevier 403, `rosap` 403 with curl but works through web fetch (the PDF then lands in the tool results folder). HAL and `pubs.lib.uiowa.edu` use a bot check. OpenAlex lists both Hidas papers as closed.
- `heavy` deletes worker files missing locally, on the next sync. Pull results first, and pull by file name, not folder. A 7 M row site doesn't fit in a `heavy bg` service.
- The `busy` test in `mg_events.py` ignores position, and over a 6 km site it rejects nearly every control. A39 needs `mg_ctrl_ht.py`.
- `q`, the offset from a lane's usual path, doesn't find a sideways start where a lane narrows: half of I-80's cars never leave the path. Use distance to the target-lane centre.

## 10. New directions

- **Is the same true at a real lane drop in a city?** Lankershim and Peachtree have too few cars. If open video appears, redo sections F and G.
- **Does a follower move over instead?** Kondyli's focus groups say freeway drivers prefer that, and Vissim has it. Wan counts 51 of about 3,000. Not measured here, and cheap to add: follower's next lane change within 5 s of a merge against controls.
- **Capacity drop.** Report 16 can't produce it. Laval's voids come from slow lane changers leaving holes. B3's slower real lateral with a follower that eases off leaves exactly such holes, so test capacity drop again after B3 and B7.

## 11. Reproduce

```sh
# repo root; dev-env.sh replaces nix develop
source /home/erikf/projects/personal/cars-data/dev-env.sh
export MG_DATA=/home/erikf/projects/personal/cars-data/truth/merging-20261102/work/data PYTHONUNBUFFERED=1
S=research/truth/scripts/merging
python3 -I $S/mg_cache.py i-80 us-101 I395 I90mov I294L1 ht       # needs the source CSVs; ht about 1.2 GB
python3 -I $S/mg_sim.py sim; python3 -I $S/mg_sim.py simo merge_open_c0.25 merge_open_c0.5; python3 -I $S/mg_simf.py
python3 -I $S/mg_events.py i-80 I395 us-101 ht I90mov I294L1 sim simo simf   # homelab: heavy bg, about 15 min
python3 -I $S/mg_more.py i-80 us-101 I395 I90mov I294L1; python3 -I $S/mg_ctrl_ht.py
for s in i-80 I395 us-101 ht I90mov I294L1 sim simo simf; do python3 -I $S/mg_analyse.py $s; python3 -I $S/mg_follow.py $s; done
python3 -I $S/mg_follow_zone.py; python3 -I $S/mg_seek.py both; python3 -I $S/mg_replay.py; python3 -I $S/mg_replay2.py; python3 -I $S/mg_replay3.py; python3 -I $S/mg_examples.py
```
Cache and events: `/home/erikf/projects/personal/cars-data/truth/merging-20261102/`. Source text and PDFs: `papers/` there, with `ledger.tsv`.
