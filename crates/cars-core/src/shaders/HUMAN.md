# The human driver: where every rule and number comes from

Classes as in `research/truth/15-how-the-best-simulators-do-it.md` Part 2. **ESTABLISHED**: a named source does the same. **ADAPTED**: a named source, changed as stated. **INVENTED**: no source; always a parameter, with a sensitivity test. The physics underneath is in `research/physics-provenance.md`. Parameters are set with `cars run --tune name=value`, rules switched off with `--human-off`. Results: `research/truth/16-human-build.md`.

## Car following (`common.wgsl`, `MODEL_HUMAN`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Linear gap and speed feedback, 1 s response lag, correlated noise | ADAPTED | Stimulus-response family, MITSIM [Ahmed 1999]; report 05 fit. Kernel replay within 2% of report 05's Python on I-395, I-90, A39 | - |
| k1 0.011, k2 0.52, √(15/g), T 1.30, amax 1.80, σ 0.20, τ_a 1.0, t_start 0.6 | ADAPTED | Report 05 section 8, fitted or measured there. k2 √(15/g) and level of σ are flagged there | constants |
| Gipps' rule towards a stopped or nearly stopped target (below 0.5 m/s) | ADAPTED | Gipps, as in Aimsun. Replaces the feedback there, because the feedback, fitted only on following, crawled the last 100 m to a queue and left 12-15 m in queues. Report 05 never saw this: its queue tests started from a formed queue | - |
| Approach deceleration 1.2 m/s², reaction term 2 s, stop margin 1.4 m, 0.5 m/s threshold | INVENTED | Chosen to pass item 10-12 with replay unchanged. 1.2 agrees with "almost nobody brakes harder than 2 m/s²" and TGSIM's median yield of 1.27 m/s² | `b_approach`, `tau_approach`, `overshoot`, `standing` |
| s0 median 2.8 m × 1.2 | ADAPTED | Report 05 median, scaled in closed loop to measured standing spacing | `s0_scale` |
| Gipps limit behind a moving, slower leader: 3.0 m/s², 0.5 s, down to s0 | ADAPTED | Gipps 1981, as in Aimsun. Without it a queue forms with half the cars 1 m or less apart and braking to −8 m/s²: the closing rule above it trusts the leader to keep its speed. 3.0 is report 19 fix 5. That fix asks 0.7 s; 0.7 s lifts A39 replay by 9% and p5 of time gaps to 1.31 s, so 0.5 s is a choice, up from the first 0.4 | `gipps_b`, `gipps_tau` |
| Top acceleration is the lower of 1.80 m/s² and the vehicle class's own | ESTABLISHED | Report 19 fix 7: Yang 2016, Krašna, physics' table | - |
| Launch: below 2 m/s, leader pulling away, gap above s0 + T·v: accelerate as if free | ADAPTED | Report 19 fix 10 asks this below 5 m/s. Below 2 here, in the plan kernel, because of the bug in report 16's merging section: inside `hu_target` the rule made followers ignore leaders on llvmpipe, cause not found | - |
| Guard is the physics certificate, with the leader assumed to brake no harder than the driver can | ADAPTED | Report 11 certificate; against SUMO's own settings report 05 asked for a lax guard. With leader braking at b_hi it held time gaps above 1.2 s at 34 m/s, against 0.8 s measured | - |
| Desired speed = lane limit × speedFactor | ESTABLISHED | SUMO, TfL | - |
| Swedish free speed by limit: 40: .98, 50: .90, 60: .85, 70: .89 of the limit | ESTABLISHED | Report 19 fix 12, VTI rapport 1001. Only with `--region sweden` | `free_table` |

## Lane changing (`lc.wgsl`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Reasons to change, look-ahead | ESTABLISHED | LC2013 strategic stage | - |
| Critical gaps for a mandatory change: lognormal, one driver term, remaining distance | ESTABLISHED | Lee 2006 table 5.1, I-80 | - |
| Constants of those gaps shifted, lead −6, lag −2 | ADAPTED | Lee and Choudhury (section 5.4.2) recalibrate constants per site in MITSIMLab. The size here is large, and the certificate floor then binds most of the time | `lead_shift`, `lag_shift` |
| The shifts can differ far from the lane end, moving to lead −6, lag −2 within `r_urg`. Default: no difference | INVENTED | Real I-80 drivers merge with 0.9 m left; here they merge 80 m early, which is why too few are passed. `lead_far=0,lag_far=0,cooperation=0.1` gives let-in 0.66 and 55% unpassed, both in band, and median wait 38 s against 22.6 s, out of band. So it stays off | `lead_far`, `lag_far` |
| Critical gaps for a discretionary change | ESTABLISHED | Ahmed 1999, as tabulated in Lee table 2.3 | - |
| Physical floor under any gap: the certificate × 0.6 | ADAPTED | Vissim's factor 0.6 during a change, on our certificate | `lc_safety` |
| Urgency by remaining distance | ESTABLISHED | Rao, Lee, Aimsun zones, TRANSIMS, I-80 in report 14. Used when `tte` is off | `r_urg` |
| Follower yields by a fixed share of drivers | ESTABLISHED | Aimsun "cooperation creating a gap", Choudhury's "probability of yielding". Value 0.4 from the I-80 sweep | `cooperation` |
| Yield limited by a deceleration | ESTABLISHED | Vissim CoopDecel −3 m/s² | `coop_decel` |
| Two-leader anticipation, with limited deceleration | ESTABLISHED | Aimsun. No advice when the leader is alongside and not getting ahead, else side by side cars hold each other | off with `--human-off anticipate` |
| Blinker: 93% signal, 1 s reaction | ADAPTED | Field share Sweden, 103 drivers; reaction is ours. No time term beyond this | `sig_react` |
| Lane change duration, quintic, per-driver lognormal | ADAPTED | Report 05 fit on 36,000 events; profile against constant speed. Runs faster if the lane is running out | - |
| Steering limit 45° at a crawl | INVENTED | Lets a queue-bound car nose in. With 12° or 25° wrong-lane waits rose several-fold on signal approaches; no measurement | `lc_slope` |
| Offset stop points at a lane end: 5 m, 12 m on every second lane | ESTABLISHED | Handbok för kapacitetsanalys med simulering, p. 106 (Trafikverket). Kept on the lane with no way on: on a short lane the point would otherwise lie back in the junction | `stop_base`, `stop_offset`, off with `--human-off offset` |
| A stop point on a short lane leaves the whole body on it, as the physics' lane change rule requires | ADAPTED | Consequence of that rule; without it cars stood 0.1 m short of being allowed to change, for good | - |
| Sideways speed at most 1.3 m/s at the quintic's peak, also when short of road | ESTABLISHED | Report 19 fix 13, real p95 1.26 | - |
| Removed: side-by-side swap, forced yield at 90 s, the wait term, the pair hash | | Report 15 rows 17, 18, 20, 21 | - |

## Merging at a lane end (`lc.wgsl`, report 18 rules B1-B8)

Each rule off with `--human-off NAME`, each number with `--tune`. Fits are on I-80 and US-101 in report 18. Results and misses: report 16.

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| B1. Urgency is time left to the lane end, remaining distance over speed, from 43 s | ADAPTED | LMRS form and t0, OpenTrafficSim; report 18 fit. A distance cannot work both at a crawl and at motorway speed. Waiting time stays out, report 14 | `--human-off tte`, `tte0` |
| B2. Start decision: logit p = −1.23 − 1.544·tte/10 + .133·t_lag + .164·t_lead, per second | ADAPTED | Form from Lee and Choudhury, coefficients report 18. Replaces the shifted Lee gaps near the end. Physical floor stays separate | `--human-off start`, `s_0`, `s_t`, `s_lag`, `s_lead` |
| B2. Driver term in that decision, 0.5 × a normal draw | INVENTED | Report 18: Lee and Choudhury have a driver term, the size here has no source | `s_driver` |
| B3. Edge: under 15 m/s, a driver wanting in drifts sideways without taking the target lane | ADAPTED | Report 18 section F, overlap at the start 32-41% at 4-7 m/s, 13% at 14, under 2% at 25-34. Ahmed's forced merge, Choudhury's anticipated gap | `--human-off edge`, `v_edge` |
| B3. Edge size per driver: lognormal, median .13 of a lane, log-SD .65 | ADAPTED | Size measured in report 18, shape invented there | `q_edge` |
| B3. Edge rate min(0.4, 0.5·v) m/s, keeps 0.2 m to a car alongside | INVENTED | The cap is report 18's, the rate is mine: no faster than a slow start of a real change, and none at standstill | constants |
| B3. Commit on anticipated gaps, τ normal(1.87, 1.44) s clamped 0-4 | ADAPTED | Choudhury eq. 5.39 | `tau_a`, `tau_sd` |
| B4. A car that wants in does not stop before it can merge: a car that has started noses up to the lane's last metre | ESTABLISHED | LMRS, OpenTrafficSim `Synchronization.PASSIVE` | - |
| B4. Last stretch braked at up to 2.5 m/s² instead of the comfort stop | INVENTED | Sits inside real stops (report 19: mean 1.32, peak 2.23, p95 4.10). Sensitivity in report 16 | `b_end` |
| B5. Speed match: 12% of the braking a target leader asks, 25% of the speed-up, ±0.8 m/s² | ADAPTED | LMRS and Aimsun name the mechanism with a minimum, which fits worse than ignoring the target lane at three of four sites. Weights report 18; 0.25 has no held-out test | `--human-off match`, `w_s_neg`, `w_s_pos` |
| B5. Weight once its own change is near (edging, or start law true): .45 | ADAPTED | Report 18: .35-.72 in the last 3 s at four sites. .45 and the switch are chosen, as one step in place of a ramp. Sensitivity in report 16 | `w_s_near` |
| B6. Steer to the bigger gap: .05 × (lead − lag)/(\|lead + lag\| + 5), within 30 s of the end | ADAPTED | Toledo and Hidas name the target gap, form from report 18, size measured | `--human-off steer`, `k_c` |
| B7. Follower brakes for a merger at .756 × driver × g_lag × g_closing of what following the merger asks, g_lag = clamp(.2 + lag/5, .2, 1), g_closing .5 above 3 m/s closing | ADAPTED | Vissim's cooperative braking, LMRS's relaxed following. Numbers fit and held out in report 18. Replaces `cooperation`, unused while this is on | `--human-off follow`, `w_f` |
| B7. Driver term uniform 0.3-1.7 | INVENTED | Report 18: not measurable from anonymous tracks | constants |
| B7. Starts .5 s after 10% of a lane sideways, or commit | ADAPTED | Report 18, measured 0-1.5 s | `t_f` |
| B7. Limited to 3 m/s² | ESTABLISHED | Vissim | `b_f` |
| B8. Blinker: 60% before the start, 33% after, 7% never | ADAPTED | Jokhio, in report 18. Only drawn. Followers respond to sideways motion, no field evidence of a blinker-only yield | - |

Scenes `scripts/human_merge.py`, real tracks through the renderer `scripts/real_tracks_trace.py`, clips `scripts/human_merge_clips.py`.

## Corners (report 19 fix 1)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| v = min(limit, √(a_y·R)), per-driver a_y lognormal, median 2.2 m/s², log-SD .30, cap 4.3 | ADAPTED | Report 19's real turning, equal to its 1.28·√R at the mean. Replaces the 8 m/s floor, which asked 9.2 m/s² at p95 against a real 3.1 | `a_y` |
| Radius: a junction lane's length over its total turn; a road's tightest over 30 m; at least 5 m | ADAPTED | Instead of the tightest points of a drawn shape, whose kinks overstate curvature (report 19). 30 m is the audit's chord. Used only by this driver: corners of the physics drivers belong to the physics branch | - |

## Missed turns

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Give up the turn, carry on in the lane, new route; counted as lost | ESTABLISHED | Aimsun Lost Inside and Outside, TfL | off with `--human-off miss` |
| Time at standstill, per-driver draw | ADAPTED | Aimsun's per-vehicle give-way time | |
| Mean 120 s, 0.5-1.5 × per driver | INVENTED | No source; sensitivity swept in cities | `t_miss` |
| Nobody waits on a lane shorter than 7 m, the route is given up on reaching its end | INVENTED | Length of a car plus 2 m, too short to change lanes on. 15 m made cars lost who could have changed lane; 11,015 of 82,709 lanes in Stockholm are under 15 m. Waiting there blocks the junction behind | `stub` |

## Junctions and signals (`step.wgsl`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Yellow: stop if time to line ≥ driver's threshold, logistic 5.1 s, 0.54 s | ADAPTED | DLR Urban Traffic, one Sunday, report 05. Those who go keep going into red for at most 2.5 s to the line | off with `--human-off yellow` |
| Yellow: no stop that needs over 3 m/s² | ESTABLISHED | Braunschweig: 0.6% stop at 2-3, none above 3 (report 05, report 19) | - |
| Gap acceptance in place of SUMO's arrival windows | ESTABLISHED | TRVMB, Aimsun, HCM family | - |
| Critical gap per link, by movement, sign and major road speed | ESTABLISHED | TRVMB Kapacitet table 3, held per link by the physics (`Link::tc`, less 1.2 s for clearing). Applied everywhere: no Berlin table is open | `tc_scale`, `tc_clear` |
| Those gaps × 0.65 for the human, then × the driver's lognormal factor | ADAPTED | With the driver's spread, 1.0 gives half of Siegloch's capacity at major flows over 600 veh/h; 0.65 keeps it within 25%. Log-SD 0.26 from the Swiss roundabouts | `gap_junction` |
| Gap test from when the car would reach the line, in place of SUMO's arrival windows | ESTABLISHED | TRVMB, Aimsun, HCM family | - |
| Roundabout: 2.95 s target, entry test value 1.5 s | ADAPTED | Swiss roundabouts, report 05, one day. The value is by analogy with the factor above; the estimator on simulated traces does not reach the target (see report 16) | `gap_roundabout` |
| Sees a give-way line from 30 m | INVENTED | SUMO's 9 m makes every car slow to walking pace with no one coming | constant |
| Exit-clear compliance 90% | ESTABLISHED | Vissim percentage, physics branch | `exit_comply` |

## Physics rules touched

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| A body whose rear still stands on a foe lane does not wait for itself in the arbiter | ADAPTED | Correction of the arbiter on `t3/1c6fee50`, applies to every physical driver. Needed where a route leaves a junction over an edge shorter than the car | - |

## Sweden (`--region sweden`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| T × 0.55, s0 × 0.47 | ADAPTED | Scaled to TRVMB's 1,900 per green hour and 7.43 m. These are design values there, not measurements. T this low is not what replay finds on US and German roads | `t_scale`, `s0_scale` |

## Other invented numbers

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Standing target 1 m before a stop line | INVENTED | Keeps queue heads off the line, no measurement | `stop_s0` |
| 1.5 m/s² when slowing for a lower limit ahead | INVENTED | Matches "almost nobody brakes harder than 2 m/s²" in report 05 | `comfort` |

## Sensitivity of the invented numbers

`scripts/human_tests.py sensitivity`, one seed, dt 0.5, results in `cars-data/truth/humans/sens/results.json` and the table in `research/truth/16-human-build.md`. Each number low and high in a queue at a signal, a lane end and a give-way junction. City sensitivity to `t_miss` and `cooperation` is in the same report.
