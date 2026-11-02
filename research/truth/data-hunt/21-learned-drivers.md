# 21. From real data to a driver: trained, rules or hybrid?

Research date: 2026-11-02. No GPU was used. Papers were downloaded and read as text (`cars-data/datasets/learned-driver-papers/`), mostly by searching the text for methods and result tables and reading those parts, not every page. Each row below says what its numbers are.

Grades: **MEASURED** a calculation on real tracks, here or by the authors. **MODELLED** a simulation result. **PROVIDER CLAIM** authors' own statement I could not check. **UNVERIFIED** not opened in full.

## The answer

**No, don't train one end-to-end network as the driver. Keep the physics and the structure as rules, and learn the few parts where rules demonstrably fail: mainly the lane-change decision and gap acceptance. Fit those as probabilities, from data, as small models. That is cheap enough on our GPU to be almost free: about 0.05 ns per car for a lane-change model that fires once a second (estimate), 0.44 ns for a car-following residual (measured, roughly), against about 15 ns for a whole step.**

Four findings decide it:

1. **Nobody has shown what Erik wants from a learned driver.** I found no learned simulator validated against sensors, travel times or jams on a network. The longest learned rollouts I read are 60 s on a map about 1 km around the car (SceneDiffuser++, called "city-scale"), 800 s across pNEUMA's Athens drone area, and one hour at one roundabout (NeuralNDE). The field's benchmark, Waymo's Sim Agents challenge, is **8 seconds** with up to 128 agents and has no flow, capacity or travel-time metric.
2. **Rules are closer than the field's framing suggests.** When someone finally ran SUMO on that same benchmark it scored 0.653, against 0.751 for the same-generation SMART and about 0.77–0.79 for the best: 87% of SMART's score with about 100 parameters. At 60 s, SUMO went off-road a third as often as SMART (0.73% against 2.06%), with similar collisions (0.47% against 0.35%). TrafficBots v1.5 collided in 25% of cases. ([Liang 2025](https://arxiv.org/abs/2512.18537), a single-author preprint.)
3. **Our own evidence and the transport literature agree.** On car following, an 8-parameter equation beat our closed-loop network on 6 of 7 data splits (it lost only I-395), and plain imitation hit collisions in up to 50% of windows ([report 13](../13-learned-drivers.md)). Published networks usually beat calibrated formulas on replay error, and also collide. Almost nobody tests them in closed loop in traffic.
4. **Where rules really are weak is the decision, not the motion.** MOBIL, the classic lane-change rule, scored 37.6% balanced accuracy on held-out NGSIM drivers, against about 50% for a plain logit and 67.4% for a 16-input one ([NOVA](https://arxiv.org/pdf/2606.10583), preprint, open loop). Only 35% of real congested US lane changes pass SUMO's secure-gap test ([report 05](../05-real-human-driving.md)). **Our pilot, section 7:** On US freeway tracks, a 201-parameter network clearly beat fitted formulas on roads it had trained on (11 of 12 comparisons). On a road it had never seen it no longer won reliably (2 better, 4 worse, 6 tied), and a 3-parameter MOBIL-shaped formula kept up. Every model explained only a small part of the decision, and predicted lane-change rates on unseen roads were off by up to 2.2×.

**Erik's instinct is half right.** Static rules with hand-picked numbers are wrong for lane changing, and data should replace those numbers. A small network may well earn a place in that one decision, if it survives unseen roads. But what the evidence supports is a small fitted probability sitting inside physical motion, not a network that drives.

**A warning about priorities.** A better driver won't rescue a wrong network. Data-hunt report [15](15-how-to-match-reality.md) lists hourly site error around 77% (metric still to confirm), about −60% vehicle-km on Berlin, and Stockholm locking at 100% demand. Those are demand and network faults first. The strongest network-level number in the GPU-simulator papers I read comes from rules: MOSS with IDM and MOBIL and camera-derived real demand reached 8.5 km/h road-speed error, against 16 km/h for CityFlow with the same kind of rules (PROVIDER CLAIM). **The implementation and the demand moved that number, not learning.**

## Answer, piece by piece

| Piece | Decision | What gets learned | Why, in one line |
|---|---|---|---|
| **Car following** | **Rule** (`MODEL_HUMAN`), residual only if it earns it | Nothing at first. Later a small residual on acceleration, inside the guard | Equation beats our network on 6 of 7 splits. Residual is the only learned form with repeated wins, and it starts from the equation |
| **Lane-change decision** | **Hybrid** | A probability per second of starting a change, from gaps, speeds and lane advantage. Logit first, 200-parameter network only if it beats the logit on unseen roads. Our pilot: it wins on known roads and not yet on unseen ones | The clearest failure of rules, and the one piece where a network might earn its place. Decision and motion are separable |
| **Lane-change motion** | **Rule** | Fitted shape and duration, already done | 5.2 s smoothstep measured on about 36,000 events. Nothing to gain and a lot to break |
| **Gap choice** | **Hybrid** | A speed- and urgency-dependent acceptance curve, on top of a hard physical floor | Real drivers accept gaps rules forbid: 0.56 s to the new follower at p5 in congestion |
| **Merging** | **Rule structure, fitted numbers** | Urgency against distance to lane end, plus the courtesy rate | Report [14](../14-human-courtesy.md): urgency follows distance, and most courtesy is tolerating a tight gap. A forced move needs a guarantee the car eventually moves |
| **Junction gaps** | **Rule structure, fitted numbers** | Critical gap and follow-up time per movement, as distributions | Right of way is a law, not a behaviour to imitate. The acceptance around it is data: 2.95 s critical gap from 7,131 decisions |
| **Route choice** | **Not a driver network at all** | Coefficients of a logit or a cost correction, fitted to observed routes, then ordinary routing | Google's Maps routing does this at world scale (15.9% route-match lift for driving). Runs before the sim, no per-step cost |
| **Variation between drivers** | **Fitted distribution** | Time gap, standstill gap, launch acceleration, drawn per car. Nothing else | Report 05: 30 s of track does not identify a driver, and only time gap persists. Any "personality" network is fitting noise until it beats this |

**End to end?** Only as a research comparison, never as the driver in the benchmark configuration. If the hybrid plateaus above the noise floor on the micro level, the next step is to widen the learned parts one at a time, not to swap the car.

## Ranked: what the community has tried, best fit for us first

| Rank | Approach | Example | Evidence for us | Network tested? |
|---:|---|---|---|---|
| 1 | **Rule motion, fitted or learned decision** | NOVA, Xie 2019 (structure), report 05 | Beats MOBIL in open loop. Parameters few, transfers | Not tested. **That's the opening** |
| 2 | **Equation plus learned residual** | [PERL](https://arxiv.org/pdf/2309.15284), [IDM-Follower](https://arxiv.org/pdf/2210.10965) | Best on prediction in those papers, especially with under 500 samples | No |
| 3 | **Physics in the loss** | [Mo PIDL](https://arxiv.org/pdf/2012.13376), [RACER](https://arxiv.org/pdf/2312.07003), [KIDL](https://arxiv.org/pdf/2504.14241) | Better with sparse data. Zero constraint violations in RACER. Output is still a network with no guarantee in new states | No |
| 4 | **Learned distributions over parameters** | [Zhang & Sun](https://arxiv.org/pdf/2210.03571), report 05 | Honest uncertainty, cheap, no drift | No |
| 5 | **Closed-loop imitation with history removed** | [HMMIL](https://arxiv.org/pdf/2306.06401) | The only learned model I read scored on density and speed over minutes, on data we partly hold | **Partly:** 800 s, Athens |
| 6 | **Learned generator plus safety layer** | [NeuralNDE](https://www.nature.com/articles/s41467-023-37677-5) | Hour-long, reproduces crash rate. One roundabout at a time, on a CPU cluster | Site only |
| 7 | **Token or diffusion generators** | SMART, CAT-K, Trajeglish, SceneDiffuser | Best short realism in the field, thousands of times too costly per car, needs the Waymo-style data we don't hold | No |
| 8 | **Adversarial imitation** | GAIL, PS-GAIL, RAIL | Superseded. In HMMIL's table they trail it on every metric, and trail plain SUMO on density and off-road | No |

## 1. Learned multi-agent simulators

| System | Data and input | Horizon, agents | Result | Limit |
|---|---|---|---|---|
| [WOSAC](https://arxiv.org/pdf/2305.12032) (the benchmark) | Waymo WOMD, 1.1 s history, map | **8 s, up to 128 agents**, 32 rollouts | Composite 0.645 MVTE, oracle 0.722, constant velocity 0.287 (2023 scale) | Authors note likelihood metrics reward diversity, and that open-loop methods can prune collisions. Metrics changed by year, so don't compare across years |
| [TrafficSim](https://arxiv.org/pdf/2101.06557) | ATG4D, map, joint latent | 12 s, 8 s labelled, 0.5 s tick | Lower collision than imitation baselines | Closed-loop training with a common-sense term |
| [SimNet](https://arxiv.org/pdf/2105.12332) | Lyft, **1,000 h** | 5 s | ADE at 5 s: 4.28 m with 10 h, 3.19 m with 100 h, 2.99 m with 1,000 h | Data helps, then barely. Reacts in 95–97% of a static-car test |
| [Symphony](https://arxiv.org/pdf/2205.03195) | Waymo proprietary and WOMD | 10 s, also 20 s | BC collision 16.65%, BC + tree search 1.84%, real playback 0.99% | Beam search each 2 s of sim |
| [BITS](https://arxiv.org/pdf/2208.12403) | nuScenes, Lyft | 20 s | Failure rate 9.97%, TrafficSim 26.98%, logged data 18.36% on the same metric | Rule-based cost function picks actions. Logged data "fails" too, so tracking noise is in the metric |
| [TrafficBots](https://arxiv.org/pdf/2303.04116) | WOMD, destination plus personality latent | 9 s | About 10 ms a step for 16 parallel sims on a 2080Ti. v1.5 scores 0.6988 | **25% collision at 60 s** (Liang) |
| [Trajeglish](https://arxiv.org/pdf/2312.04535) | WOMD, motion tokens | 8 s, shown to 20 s | 0.6451 in SMART's 2023 table | Offline, needs intra-step coupling |
| [SMART](https://arxiv.org/pdf/2405.15677) | WOMD, 7–102 M parameters | 8 s | 0.7591–0.7614. **Zero-shot from nuPlan 0.7210**, minADE 2.57 against 1.41 m | 5–20 ms per step per scene, authors' hardware |
| [CtRL-Sim](https://arxiv.org/pdf/2403.19918) | WOMD plus factored rewards in physics Nocturne | 8 s | Tilt behaviour by return, 1,000 test scenes | Controllability, not long horizons |
| [GUMP](https://arxiv.org/pdf/2407.02797) | WOMD, nuPlan, 523 M parameters | 8 s | 0.7431 | Bigger than rivals, no better |
| [CAT-K](https://arxiv.org/pdf/2412.05334) | SMART-tiny fine-tuned closed loop | 8 s | **0.7702**, first on 2024 board. Cuts planning-task collisions by 25.7% | Pre-training alone is 10 epochs at 2.6 h each |
| [SceneDiffuser++](https://arxiv.org/pdf/2506.21976) | WOMD with maps enlarged to 1 km radius | **60 s at 10 Hz** | JS divergence from logs, composite: 0.23–0.29 with SceneDiffuser++ as the world, 0.42–0.48 with IDM. Best on spawning and exit realism. **Worse on collision-rate divergence** (0.42–0.49 against IDM worlds' 0.10–0.37). Traffic lights simulated as well | "City-scale" means trip-level around one car. No sensors, no flow |
| [Scoring 2025: TrajTok](https://arxiv.org/abs/2506.21618) | SMART with new tokens | 8 s | 0.7852, second place by its authors' report (abstract read) | Same benchmark |

**Does any run for hours or a city?** Hours: only NeuralNDE, at one roundabout, 3,600 s episodes at 0.4 s, vehicles entering by a calibrated Poisson process, and a hand-trained safety mapper. Its crash rate of 1.25 × 10⁻⁴ per km against 1.21 × 10⁻⁴ measured is real and striking (MEASURED against MODELLED; the paper's text extraction shows "× 104", which I read as a superscript minus sign lost in extraction). City: none. **Do any validate at network level?** Only in a weak form: HMMIL on pNEUMA, section 2. Everything else scores likelihoods of kinematics.

**Fair point for the learned side.** At 8 s they are clearly more realistic, which matters to self-driving testing. And SMART at 60 s does not fall apart. The field simply isn't trying to solve our problem. Liang also needed hand-written logic to make SUMO work on WOMD at all, including holding some agents still, which flatters collision and off-road counts. It is an unreviewed preprint.

## 2. Imitation and closed-loop drift

**How badly drift hurts.** Theory: with error ε per step, plain cloning can make up to `T²ε` mistakes over `T` steps ([Ross et al.](https://arxiv.org/pdf/1011.0686)). In practice:

| Evidence | Plain cloning | With a fix | Fix |
|---|---|---|---|
| [HMMIL](https://arxiv.org/pdf/2306.06401), pNEUMA, 800 s | **42.15% off-road** | 0.51% | Mask history, perturb state, in multi-agent |
| [Symphony](https://arxiv.org/pdf/2205.03195), Waymo proprietary | 16.65% collision | 1.84% (real logs 0.99%) | Tree search during training and use |
| [Imitation Is Not Enough](https://arxiv.org/pdf/2212.11419) | | Over 38% fewer failures on the hardest scenarios | Add RL with simple rewards, 100k miles. [RTR](https://arxiv.org/pdf/2311.01394) does the same in closed loop; numbers not extracted |
| [CAT-K](https://arxiv.org/pdf/2412.05334) | 0.7591 | 0.7702 | Closed-loop fine-tune |
| Report 13, our ring | BC: 563 veh/h, contact in 21% | DAgger fixes the nominal case, then is the least robust | Train on a mix of humans |
| Report 13, real pairs | **BC 50% of windows collide** | ES on closed-loop error 0.3% | Train on rollouts, never one-step |
| [Waymax](https://arxiv.org/pdf/2310.08710) | Trained against IDM, tested on logs: 25.15% collision against 6.50% | | Don't train against an easy partner |

**The fixes all share one idea: the loss has to see the model's own mistakes.** Pure supervised one-step training is dead for this purpose.

**GAIL family.** [Kuefler](https://arxiv.org/pdf/1701.06699) (NGSIM, single agent, long horizon) showed GAIL beating cloning on emergent behaviour except hard brakes. [PS-GAIL](https://arxiv.org/pdf/1803.01044) added shared parameters and a curriculum up to 100 agents, scored over **20 s**. [RAIL](https://arxiv.org/pdf/1903.05766) added penalties and improved lane-change count, time gap and speed distributions, shown in figures. [The later journal paper](https://arxiv.org/pdf/2006.06412) extends these to driving styles. On a harder test, HMMIL's comparison has PS-GAIL 13.24% and RAIL 2.92% off-road at 800 s.

**The HMMIL result, closely, because it's the nearest thing to our question:**

| 800 s on pNEUMA, last day held out | Road density RMSE, veh/km | Road speed RMSE, m/s | Off-road |
|---|---:|---:|---:|
| SUMO, IDM + MOBIL, IDM fitted to acceleration | 52.70 | 5.52 | 0% |
| PS-GAIL | 54.06 | 4.03 | 13.24% |
| RAIL | 54.45 | 3.89 | 2.92% |
| BC | 61.51 | 5.38 | 42.15% |
| HMMIL | **48.71** | **3.55** | 0.51% |

So learned beats SUMO by 8% on density and 36% on speed. Read it carefully:

- Density error of about 50 veh/km is large for every model, including the best.
- SUMO's fit was to acceleration MSE, which [report 05](../05-real-human-driving.md) and its sources find a weak way to calibrate. A trajectory calibration could close some of that.
- **They skip collisions on purpose**: "the dataset does not provide accurate vehicle size and heading". Traffic lights are estimated, not measured. Vehicles replay their real entry time and route, so the demand is given.
- Three seeds, one team, one city.

It is still real evidence that a learned policy can stay stable for minutes on a city grid. **No run has gone longer than that, and no one tested it on another city.** Worth reproducing, on our data, not worth building on yet.

## 3. Data-driven car following and lane changing in transport research

| Work | Result | Closed loop in traffic? | Comment |
|---|---|---|---|
| [FollowNet](https://arxiv.org/pdf/2306.05381) | Spacing MSE on HighD: LSTM 22.90, GHR 23.76, NN 24.06, IDM 27.50. NGSIM: LSTM 23.86, IDM 54.97. **Collisions:** NN up to 116‰ (291), LSTM up to 110‰ (274), GHR and IDM **0** | Replay of a real leader | The best single benchmark. On the clean, single-regime HighD it's a tie. Authors say a model trained on one dataset may not do as well on another |
| [Zhu 2018](https://arxiv.org/pdf/1901.00569) | Spacing error 18%, speed 5%, better than IDM on Shanghai naturalistic pairs | Replay | RL with a reward fitted to a driver. 2,000 periods |
| [Mo PIDL](https://arxiv.org/pdf/2012.13376) | Physics in the loss beats either part, more so with little data, on NGSIM. On simulated data, MSE down 1.26–16.8% depending on regime | Replay | Benefit shrinks as data grows |
| [PERL](https://arxiv.org/pdf/2309.15284) | Newell plus LSTM residual beats pure network and PINN, faster training, fewer parameters, especially under 500 samples | Short prediction | Prediction, not a sim |
| [Hart et al.](https://arxiv.org/pdf/2109.14268) | RL with an IDM-like reward: string stable, crash-free on a 5-car platoon, better fit than calibrated IDM | **5 cars** | Training on synthetic leaders. A rare stability test |
| [KIDL](https://arxiv.org/pdf/2504.14241) | Adds stability to the loss, as a condition checked at all equilibrium states | Analytic stability | Stability had to be put in by hand |
| [NOVA](https://arxiv.org/pdf/2606.10583) | Symbolic law: speed RMSE at 30 s 5.30 against IDM 9.15. **Raw crashes 44.5%, with a TTC override 2.5%, IDM 0.01%.** Platoon amplification 1.06 against IDM 1.72. Lane change, above | 30 s replay, 13-car platoon | Preprint. A formula with a safety override, not a network. Their calibrated IDM has v₀ 40 m/s and b 6 m/s², outside what report 05 would accept, so it's a harsh baseline |
| [RACER](https://arxiv.org/pdf/2312.07003) | Zero violations of rational-driving constraints, on ACC data | Replay | Not human data |
| [Xie 2019](https://doi.org/10.1016/j.trc.2019.07.002) | Decision network plus execution LSTM on NGSIM | **Abstract only; UNVERIFIED** | Its two-part split matches ours |
| Wang 2018, Zhou 2017, Huang 2018, Zhang 2019 | Claim LSTM accuracy over formulas | **UNVERIFIED**, paywalled, abstract at most | Cited for existence only |
| [Salles et al., calibrated EIDM](https://arxiv.org/pdf/2408.03722) | Calibrating 486 real driver–car combinations from drones gave a capacity drop and stop-and-go in simulation, with **zero collisions**. Calibrated Krauss: 13,829 emergency stops and 6 collisions. Authors say the macro results still need checking against measurements | **Yes, on a loop and one junction, in SUMO** | Also says outright: "no sophisticated traffic simulator for data-driven CFMs exists", which blocks macro validation. It's physics-based. **We could be that simulator** |

**Do they beat calibrated models on held-out data once in closed loop?** On replay error, usually, by a modest margin that depends on the data set and on how badly the formula was fit. In closed loop among themselves, I found no paper showing a network beating a well-calibrated formula across waves, discharge and collisions together. Report 13's test is the closest and the network lost. **Calling this settled would overclaim: mostly the test hasn't been run.**

**Lane change evidence is thinner than car following.** Almost everything is NGSIM, which report 05 cites as badly flawed. Most reports classification accuracy on balanced samples, which says little about rate. Nobody I read shows a learned lane-change model producing the right lane-change rate per vehicle-km in closed loop. A search summary mentions a deep-RL paper reporting 0.81 veh/km/lane against NGSIM's 0.63–0.80 (UNVERIFIED, not opened).

## 4. Hybrids

| Type | Example | What works | What fails |
|---|---|---|---|
| Rules plus residual | PERL, IDM-Follower | Fewer parameters, less data, inherits physics | Residual still leaves its data. Needs the guard |
| Learned decision over physical motion | NOVA lane-change logit, Xie, BITS (learned goals, rule planner), Symphony's hierarchy | Motion stays legal and smooth | The decision can still be wrong in closed loop, untested |
| Learned parameter distribution | Report 05, Zhang & Sun, EIDM per-car calibration, TrafficBots personality | No drift. Cheap | Identifying a driver from a short track fails (report 05) |
| Physics in the loss | Mo, RACER, KIDL | Helps with sparse data | No hard guarantee |
| Learned policy with a safety layer | NeuralNDE, our "rule" mode, NOVA's override | Our data: every arm 0% contact | Training under the rule teaches dependence: 94% contact when removed (report 13) |

Every system with a real long-horizon result has a rule or a physics layer somewhere. Liang's paper ends by calling for exactly this hybrid.

## 5. GPU and city-scale simulators

| Simulator | Scale reported | Cost | Driver | Validated? |
|---|---|---|---|---|
| [MOSS](https://arxiv.org/pdf/2405.12520) | 2,464,950 vehicles, 3,600 1 s steps, 37.70 s, RTX 4090 plus 32 threads | **At least 4.2 ns per vehicle-step**, if every vehicle were active all hour, which isn't so | IDM + random MOBIL. **No learned driver.** Learning is in OD generation only | Shenzhen 8–9 am, 156,856 trips, 1,341 roads: RMSE 8.5 km/h, r 0.77. CityFlow 16, 0.53 |
| [LPSim](https://arxiv.org/pdf/2406.08496) | 9.01 M trips, 143 s on 2 A100s, 113× a CPU | No per-step figure I could extract | IDM, lane change, gap acceptance | No validation found on a text search |
| [GPUDrive](https://arxiv.org/pdf/2408.01584) (report 13) | 2.3 M agent steps/s peak, about 200,000 controlled | About 5 µs per controlled agent-step | Learned, self-play | Goal reach, not human-like by design |
| [Waymax](https://arxiv.org/pdf/2310.08710) | Up to 128 objects | 0.92 ms a step on one V100, 2.86 ms for 16 scenes, so 1.4–7 µs per object-step, no policy | Logged, IDM, or yours | Collision and off-road on logs |
| [CityFlowER](https://arxiv.org/pdf/2402.06127) | ML embedded in a C++ sim, 30×30 grid in its demo | Authors claim little slowdown | Learned from simulator logs, so it copies rules | Recovers SUMO behaviours, not reality |
| [TransWorldNG](https://arxiv.org/pdf/2305.15743) | Graph model, one signalised junction of 768 vehicles in the shown test | | Learned from SUMO's output | Compared with SUMO, not reality |
| **cars** (13b) | 100,012 cars | **15.9 ns per car whole step** with a 212-float network, 0.44 ns of it in the network (rough) | `MODEL_NN` on branch `t3/aea36e36` | Not yet |

**Surprise:** I found no GPU city-scale simulator running a learned per-vehicle driver, validated or not. Our measured 0.44 ns kernel may be the only per-car learned inference on a non-CUDA GPU in this literature, though that's absence from what I read, not proof.

## 6. Cost per car on our GPU

Measured baseline: 15.3 ns per car, 65 M updates/s at 100,000 cars, RX 7900 XT. With the 12-8-8-4 network: +0.44 ns in its kernel from one timed step, about +3.5% overall (13b). Report 13 had estimated 3–10 ns, so this came in lower. **Scaling below is ESTIMATE**, from 2.3 ps per multiply-add at that one measurement, ignoring cache effects.

| Form | Size | ns per car-step | Effect on a step | Fits the kernel rules? |
|---|---|---:|---:|---|
| Lane-change logit, every second at dt 0.1 | 15 floats | about 0.01 | None | Yes |
| Lane-change net 14-8-8-1, every second at dt 0.1 | 201 floats | about 0.05 plus inputs already in `lc_evaluate` | Under 1% | Yes, as existing mat4 blocks |
| Car-following residual 12-8-8-4 | 212 floats | **0.44 measured** | +3.5% | Yes, exists |
| Larger MLP 32-64-64-4 | About 6,500 floats | About 15 | Doubles | Awkward: no function-local arrays, generated code |
| GRU, 32 units | About 4,700 floats | About 11, plus 128 B per car | +70% | Awkward |
| Attention over neighbours | Small | 50+, a guess, not derived | ×4 or more | Needs a loop over neighbours, breaks one-lookup locality |
| TrafficBots style | | At best about 6 µs (10 ms ÷ 16 scenes ÷ about 100 agents; my reading of an ambiguous sentence and my assumption on agents), on a 2080Ti | **×400 or more** | No |
| SMART style | 7 M | Over 78 µs (10 ms ÷ 128 agents), authors' hardware | **×5,000** | No. O(N²) in agents, per scene |

**A million cars at 15 ns is about 15 ms a step. At SMART's cost, about 78 s a step.** Training costs little: Torch on CPU was already 854,000 samples/s, the data below is small, and ES on the GPU was 16–45 M updates/s, limited by the shared lock, not speed.

## 7. Pilot on data we hold

**Why:** so the proposal rests on real counts and a real held-out comparison, not on reading alone. **MEASURED on real tracks, open loop, no simulation, not yet proof of anything at network level.** Script: [`scripts-21/lc_pilot.py`](scripts-21/lc_pilot.py). Results: [`21-lc-pilot.json`](21-lc-pilot.json). One thread, 3 minutes once samples are cached, under 2 GB.

**Task.** Each second, for each car and each side with a neighbouring lane in view: will this car's lane label change to that side between 2 and 3 s from now? The offset is there because the label flips mid-manoeuvre, and a change takes about 5 s. Inputs are 14 numbers: own speed, gap and speed difference to the leader, the same to the leader and follower in the target lane, time gaps, inverse gaps, and two IDM terms (MOBIL's gain and the new follower's braking). Cars only, automated vehicles excluded, 60 m from view edges, position along a fitted road axis for each run.

**Data.** TGSIM only. I-395 is out, because its lane labels failed report 05's screening. A39 and others are for the builder.

| Site | Tracks | Lane changes | Vehicle-km | Changes per vehicle-km | Samples, positive |
|---|---:|---:|---:|---:|---:|
| I-90/94 stationary | 9,955 | 1,495 | 2,622 | **0.57** | 462,504, 1,227 |
| I-90/94 moving, other day | 2,435 | 469 | 910 | **0.52** | 234,163, 404 |
| I-294 L1 | 1,158 | 516 | 1,701 | **0.30** | 100,763, 435 |

**Scores on data not used for fitting.** Skill is the share of log-loss removed against a constant rate from training, so 0 means no better than constant. `AUC / skill`, networks as the mean of two seeds.

| Trained on | Tested on | Rule-shaped logit, 3 params | Logit, 15 | Logit with squares, 29 | Network, 201 | Network, 1,537 |
|---|---|---:|---:|---:|---:|---:|
| I-90 and I-294 | I-90 stationary, later run | 0.68 / .032 | 0.73 / .058 | 0.77 / .081 | 0.79 / .100 | **0.81 / .117** |
| I-90 and I-294 | I-90 moving, other day | 0.72 / .042 | 0.79 / .096 | 0.80 / .103 | 0.83 / .127 | **0.84 / .136** |
| I-90 and I-294 | I-294, later runs | 0.72 / .080 | 0.72 / .078 | 0.72 / .080 | 0.75 / .110 | **0.77 / .123** |
| I-90 stationary | I-90 moving, other day | 0.72 / .038 | 0.79 / .087 | 0.81 / .099 | 0.82 / **.106** | 0.82 / **.106** |
| **I-90 stationary** | **I-294, never seen** | 0.73 / .069 | 0.75 / .059 | 0.75 / .072 | 0.75 / **.076** | 0.77 / .061 |
| **I-294** (227 events) | **I-90 stationary, never seen** | 0.67 / .036 | 0.71 / .034 | 0.73 / .033 | 0.71 / **.041** | 0.70 / .038 |
| **I-294** (227 events) | **I-90 moving, never seen** | 0.71 / .068 | 0.79 / **.111** | 0.76 / .083 | 0.77 / .106 | 0.74 / .094 |

**Predicted over observed rate on unseen roads**, which is what a closed-loop run would inherit:

| Trained on, tested on | Rule-shaped | Logit | Logit with squares | Network, 201 (two seeds) | Network, 1,537 (two seeds) |
|---|---:|---:|---:|---:|---:|
| I-90 stationary, I-294 | **0.82** | 1.70 | 1.46 | 1.67, 1.14 | 2.24, 1.81 |
| I-294, I-90 stationary | **0.92** | 0.52 | 0.57 | 0.62, 0.57 | 0.59, 0.66 |
| I-294, I-90 moving | 1.55 | 0.61 | 0.63 | **0.84**, 0.70 | 0.68, 0.77 |

**What this says:**

- **I expected a logit to tie the network. On known roads it didn't.** Network seeds beat the better logit in 11 of 12 same-road comparisons, with bootstrap intervals excluding zero. So there is real nonlinear structure in the decision, and a network can find it. That is a point for Erik's instinct.
- **On unseen roads the win goes away.** Against the better logit on each test: 2 network seeds better, 4 worse, 6 tied. This may be data rather than the method. The I-294 model trained on 227 events, the I-90 one on 828, and one more seed changes results. **A39's 16,000+ events could change this, and step 2 of section 11 must test it.**
- **A 3-parameter rule-shaped logit is hard to beat on rate.** It had the smallest rate error on 2 of 3 unseen-road tests. Note this is MOBIL's *terms*, fitted as a probability. It is not MOBIL's fixed thresholds.
- **Most of the decision stays unexplained.** Skill stays at or below about 0.14 and AUC at or below 0.84. The obvious missing input is intent: these tracks don't say where a car is going, and the pilot has no distance to a ramp. Better intent inputs may help more than a bigger network.
- **Two terms stay stable between roads.** In the 14-input logit, MOBIL's speed-gain term gets a standardised weight of 0.78–0.82 and the new follower's braking term about 0.72, whichever road it is fitted on. So more gain and less braking forced on the new follower raise the rate. That likely explains why the small rule-shaped model travels. The other inputs are correlated and move between fits (time gap to the target leader −0.25 to −1.17), so don't read them one by one. Weights are in the JSON.
- **A site-level rate correction looks unavoidable.** Measured rates differ almost 2× between roads (0.30 against 0.57 per vehicle-km). No model trained elsewhere got that right on its own, so section 10's few scalars by road class must include one for lane-change rate.

**Limits.** Open loop, so it says nothing yet about stability or the network. Freeways only, US only. Intervals resample vehicles, not time blocks, so they are too narrow, and there are many comparisons. Networks got 40 epochs of Adam with early stopping and no tuning. Curved runs (I-90 stationary runs 1, 3, 5) make gaps approximate along a straight axis. Lane labels are the provider's, with no human check.

**A mistake worth recording.** My first version took x as the along-road axis, as earlier scripts do. On I-90 stationary run 5 that gave no samples at all and squeezed gaps elsewhere. Only a crash on an empty validation set revealed it. Its numbers were thrown away. Any script using `SITES`'s fixed axis on these runs should check this.

## 8. What data, how much

| Piece | Data we hold | Count | Is it enough? |
|---|---|---|---|
| Car following | TGSIM I-395, I-90/94, I-294, DLR A39 (`opus-…-cache/pairs_*.npz`, `split_all.pkl`) | 6,000 train windows, 14,000+ test | Yes. Report 13's network reached this already |
| Lane decision | TGSIM I-90/94 and I-294; DLR A39 (`ht_lc.csv`, tracks in the 3.4 GB zip, lanes reconstructed) | About 1,000 screened US events, 16,622 in 4 h of A39 | **US side is thin.** A logit is fine. A 200-parameter net wants the A39 too |
| Gap acceptance | Same plus `lc_events*.pkl` | Same. Rejected gaps can't be observed directly, because intent is invisible | Fit a rate model, not a gap test |
| Merging | Report 14's controls (`courtesy/controls_*.csv.gz`, including I-80), DRaT 45 usable events | 610 cars at I-80 | Enough to fit a few numbers. Not a network |
| Junction gaps | `roundabout_decisions.csv`, 7,131 decisions, 3 Swiss sites; Foggy Bottom; DLR UT 27,196 tracks with real signals | | Fit distributions per movement |
| Urban all-vehicle | One pNEUMA file (`20181024_d1_0830_0900.csv`) | 82 MB | Too little for HMMIL's split. Full set is 15.76 GB, open |
| Route choice | `flowsense-se`, Jinan (`jinan-yu2023`), Cambridge ANPR; see [report 06](../06-demand-and-route-choice.md) | | Separate task |
| Nordic test | Helsinki sample, one zip (`helsinki-drones-2026`). [Full set](https://zenodo.org/records/19684712) about 170,000 tracks, 2.2 GB, CC BY per [data-hunt report 13](13-repositories-and-other-languages.md); the Zenodo page itself did not open from here under load | | **Download it. Test only** |

**How much?** SimNet's table says ten times the data buys 25%, then 6%. Report 13's network converged on 6,000 windows. For our small models the limit is variety of places and congestion, not samples. **Rule of thumb, my opinion: 10 events per parameter, and add a site before adding a parameter.** The pilot's 1,055 training events support about 100 parameters, so its 201-parameter net is already past that, and the A39 fixes it. Not at all enough for transformers, which is one more reason not to go there.

## 9. What would prove it's better

**Never** training loss, one-step accuracy, or AUC alone. The bar comes from [VALIDATION-GATE.md](../VALIDATION-GATE.md) and data-hunt report 15. Each row is scored on data the model never saw, with the same configuration everywhere.

| Level | Test | Rules (today) against hybrid must show |
|---|---|---|
| Replay | Report 05's frozen splits, A39 refit on US only | Not worse on any split, CI excludes zero on the ones claimed |
| Chains | Flat fluctuation, 34 km/h wave, gap spread, 8-car chains | All within measured range. Report 05's numbers are the reference |
| Junction | Saturation headway 2.0 s, lost time 2.7 s, critical gap 2.95 s | Within measured intervals, **in closed loop** |
| Lane changing | **Changes per vehicle-km, by lane, by density, and where along the road**; gaps accepted; time since last change. Measured so far: 0.30–0.57 per vehicle-km on three freeway sites | Within site-to-site spread. **I found no one publishing this for a learned model. It's the test that matters most** |
| Physical | `19-physical-realism` distributions | No worse, no new outliers |
| Corridor | Queue and travel time on a held-out corridor | Better than rules, seeds paired |
| **Long-run drift** | Same world run for 1 h, 6 h, 24 h: speed, gaps, change rate, contacts by hour at fixed demand | **No trend.** No published learned model is reported to pass this. We can run it |
| Network | Data-hunt report 15's table against the real-day floor | **Improves or holds every row; regressions kill it** |
| Transfer | Train without Nordic data, score on Helsinki, and on a German site after US-only training | Beats rules on the unseen site |

**Kill rule:** if a network can't beat the fitted logit on two unseen sites at the lane-change-rate row, keep the logit and stop. If the logit can't beat today's rules there either, drop the change. Keep 12 or more paired seeds, report contacts without the guard too, and count guard overrides: above a few percent means the rule is driving, not the model (report 13's tailgaters reached 36–62%).

## 10. Would it generalise to Stockholm?

**Structure probably yes. Exact numbers no. No Swedish trajectory data is available to check it**, so this stays a stated risk.

- **Small models travel.** Report 05: US-only fit, tested in Germany, beat Krauss by 17%. NOVA: 3 points of R² lost between two California freeways (a weak test). [Rossi and colleagues](https://wctrs-society.com/wp-content/uploads/abstracts/lisbon/general/02160.pdf) study moving gap-acceptance logits between sites with a small local sample (search result, UNVERIFIED).
- **Big models lose more.** SMART zero-shot: −5% on the score, minADE about 83% higher, and that's only between two US-heavy AV datasets. [UniTraj](https://arxiv.org/pdf/2403.15098) reports a large performance drop between datasets and that more diverse data helps. [Bahari et al.](https://arxiv.org/pdf/2112.03909) find over 60% of Argoverse scenes can be turned into new, realistic scenes where a trained predictor fails.
- **Local differences in our own data.** Gap to the new follower at p50: 1.67 s in congested US, 2.33 s on a free-flowing German motorway. That mixes country with congestion, and we can't separate them yet.
- **Not covered by anything we hold:** Swedish winters, Stockholm's weaving and bus lanes, tunnels. Helsinki helps only with a Nordic urban junction setting in September.

**So:** train on everything non-Nordic. Test on Helsinki. Allow only a few physically meaningful scalars to shift by road class, like speed factor and time gap median, and fit them on Stockholm's tuning data, never its held-out data. Then judge Stockholm on its network sensors. Any per-city fit of network weights is out, because it can't be validated and it games the benchmark.

## 11. Prototype a builder can start tomorrow

**Name:** Hybrid lane-change decision, compared with rules on the benchmark. Python first, no GPU until step 4. Base on [`scripts-21/lc_pilot.py`](scripts-21/lc_pilot.py), which already runs on the TGSIM sites.

| Step | Do | Input | Pass |
|---|---|---|---|
| 0 | Freeze splits, committed before any fit. Keep the pilot's splits, add A39 by time, hold back Helsinki | Section 8 | Written down |
| 1 | Extract the A39 lane-change decision set, using `opus_ht.py`'s lanes and the pilot's features. Add a distance-to-ramp input from TGSIM centreline files, which the pilot lacks | DLR zip, `tgsim-att` | 10,000+ events, one script |
| 2 | Fit rate models in order: constant, MOBIL-shaped, logit, 14-8-8-1 net, several seeds. Add distance to ramp and urgency for forced moves from report 14. Score open loop, both skill and rate, leaving out one whole road at a time, with intervals by time block | Step 1 | A model beats the simpler one on **every** left-out road, or stop at the simpler. The pilot says this is a real question: same-road wins don't count |
| 3 | Closed-loop in Python: a 3–4 lane stretch using `MODEL_HUMAN` from report 05, measured inflow and lane shares, real lane-change motion of 5.2 s. Compare with I-90/94 and A39, including rate per vehicle-km | Steps 1, 2 | Change rate, lane split and gaps within site spread. **Most likely place for it to fail** |
| 4 | GPU. Rebase `crates/cars-core/src/nn.rs`, `shaders/nn.wgsl`, `shaders/nn_net.wgsl` and `train` from `t3/aea36e36`. `lc_evaluate` already calls `nn_lane_choice`. Change the output to a rate, sample it each second. Keep the secure-gap floor as the guard, with a measured floor rather than SUMO's | | Parity Python ↔ WGSL under 1e-5, kernel cost measured, `--dt` sensitivity |
| 5 | Corridor, then benchmark | Report 22's benchmark, when built | Section 9 |
| 6 | Only now, if steps 1–5 pass: gap acceptance at junctions the same way. Then car-following residual, trained by ES on chain rollouts and on rings | | Same table |

**Effort, my guess:** steps 0–3 two days of an agent's CPU time, step 4 one day plus a GPU turn. Steps 0–3 need no GPU, no flake change and under 2 GB, so they can run now while self-driving work stays paused. This serves the human-only gate directly: it is a human driver model.

**Rejected for now:** reproducing HMMIL (needs 15.76 GB of pNEUMA and Torch; do it after step 3, as a comparison, if the hybrid stalls on urban streets). Waymo data (licence and Waymo-only benchmark, wrong question). Any transformer.

## Top 3 recommendations

1. **Decide: hybrid. Keep `MODEL_HUMAN` for following, fit a small lane-change rate model.** Next step: run section 11, steps 0–3.
2. **Add two tests no one publishes to the benchmark: lane-change rate per vehicle-km in closed loop, and a 24-hour drift test.** Next step: give section 9's table to the benchmark builder. These tests also make the rules honest.
3. **Download Helsinki (2.2 GB) and keep it test-only for transfer.** Next step: `curl` the Zenodo files to `cars-data/datasets/helsinki-drones-2026/` and don't look at it during fitting.

## What only Erik can do

Nothing blocks the prototype. Optional, later: highD, exiD, inD and rounD need account forms (report 05, section 11), and they'd add clean decision data with ramps, so I'd apply if step 2 runs short of variety. The Trafikverket INRIX request from [data-hunt report 05](05-sweden-kth.md) helps route choice only. No new draft is needed here.

## Dead ends

- **An end-to-end network as the benchmark driver.** Cost ×400–5,000 if generative. No network-level evidence.
- **Plain behaviour cloning, in any form.** Report 13, HMMIL, Symphony.
- **Using WOSAC's score as evidence of accuracy for us.** 8 s, no flow. SUMO's 0.653 shows how little separates a rule from the field on kinematic likelihoods at 8 s.
- **Reading "city-scale" in titles as a network result.** SceneDiffuser++ is 60 s and CityFlowER plus TransWorldNG learn from simulators.
- **Report 13's merge and ring reward results as a human model.** They were about AV control.
- **Per-driver networks or personalities.** Report 05: population beats own fit. Reopen only with tracks long enough to identify a driver.
- **`pdftotext` on a 19 MB PDF under load 60.** Use arXiv's HTML version.
- **Same-road test scores for lane changing.** They flatter networks. See section 7.

## New directions I couldn't cover

- **Symbolic regression** (NOVA, in Rust). It writes small formulas that fit our kernel directly. The search engine could run on our own decision data, and a formula beats a net on speed and on being read. Worth one try at step 2.
- **Differentiable or ES calibration of the hybrid's few parameters against corridor measurements.** Queue item in PLAN. Data-hunt report 15 warns about over-fitting.
- **A mid-size generator for insertion only.** SceneDiffuser++'s real gain is spawning and exit realism, which is an open boundary-condition problem for us at sensor-limited edges.
- **Learned speed-limit or free-speed maps** from FlowSense. Possibly a bigger win than any driver change. Belongs in Track A.
- **Long lidar deployments** such as LADDMS (report 01) to observe rare events for drivers.

## Reading record

**Read as text:** WOSAC, Waymax, TrafficSim, SimNet, Symphony, BITS, TrafficBots, Trajeglish, SMART, CtRL-Sim, CAT-K, GUMP, SceneDiffuser, SceneDiffuser++, RTR, Imitation Is Not Enough, Kuefler, PS-GAIL, RAIL, Bhattacharyya journal, DAgger, Mo, FollowNet, PERL, IDM-Follower, Zhu, MOSS, LPSim, CityFlowER, TransWorldNG, Google RHIP, Bahari, UniTraj, HMMIL, Salles EIDM, NOVA, KIDL, Hart, RACER, Liang (HTML), NeuralNDE (PDF). **Abstract only:** TrajTok, Xie 2019, Zhang & Sun (two, so the row in section 4 rests on their stated method only). **Search result only, UNVERIFIED:** Wang 2018, Rossi, frequency RL paper. **Not opened:** Zhou 2017, Huang 2018, Zhang 2019. **From reports 13/13b, not re-read:** GPUDrive, HR-PPO, Cornelisse.

Numbers in figures only (RAIL, Bhattacharyya, PS-GAIL, Kuefler) are described in words. I searched these texts for methods and tables, so a caveat elsewhere in a paper could have escaped me.
