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
| Gipps limit behind a moving, slower leader: 4.5 m/s², 0.4 s, down to s0 | ADAPTED | Gipps 1981, as in Aimsun. Without it a queue forms with half the cars 1 m or less apart and braking to −8 m/s²: the closing rule above it trusts the leader to keep its speed. The rule is established, the two numbers are chosen so replay stays in band and p5 of time gaps stays low. 0.7 s lifts A39 replay by 9% and p5 of time gaps to 1.31 s | `gipps_b`, `gipps_tau` |
| Guard is the physics certificate, with the leader assumed to brake no harder than the driver can | ADAPTED | Report 11 certificate; against SUMO's own settings report 05 asked for a lax guard. With leader braking at b_hi it held time gaps above 1.2 s at 34 m/s, against 0.8 s measured | - |
| Desired speed = lane limit × speedFactor | ESTABLISHED | SUMO, TfL | - |

## Lane changing (`lc.wgsl`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Reasons to change, look-ahead | ESTABLISHED | LC2013 strategic stage | - |
| Critical gaps for a mandatory change: lognormal, one driver term, remaining distance | ESTABLISHED | Lee 2006 table 5.1, I-80 | - |
| Constants of those gaps shifted, lead −6, lag −2 | ADAPTED | Lee and Choudhury (section 5.4.2) recalibrate constants per site in MITSIMLab. The size here is large, and the certificate floor then binds most of the time | `lead_shift`, `lag_shift` |
| The shifts can differ far from the lane end, moving to lead −6, lag −2 within `r_urg`. Default: no difference | INVENTED | Real I-80 drivers merge with 0.9 m left; here they merge 80 m early, which is why too few are passed. `lead_far=0,lag_far=0,cooperation=0.1` gives let-in 0.66 and 55% unpassed, both in band, and median wait 38 s against 22.6 s, out of band. So it stays off | `lead_far`, `lag_far` |
| Critical gaps for a discretionary change | ESTABLISHED | Ahmed 1999, as tabulated in Lee table 2.3 | - |
| Physical floor under any gap: the certificate × 0.6 | ADAPTED | Vissim's factor 0.6 during a change, on our certificate | `lc_safety` |
| Urgency by remaining distance only, no time terms | ESTABLISHED | Rao, Lee, Aimsun zones, TRANSIMS, I-80 in report 14 | `r_urg` |
| Follower yields by a fixed share of drivers | ESTABLISHED | Aimsun "cooperation creating a gap", Choudhury's "probability of yielding". Value 0.4 from the I-80 sweep | `cooperation` |
| Yield limited by a deceleration | ESTABLISHED | Vissim CoopDecel −3 m/s² | `coop_decel` |
| Two-leader anticipation, with limited deceleration | ESTABLISHED | Aimsun. No advice when the leader is alongside and not getting ahead, else side by side cars hold each other | off with `--human-off anticipate` |
| Blinker: 93% signal, 1 s reaction | ADAPTED | Field share Sweden, 103 drivers; reaction is ours. No time term beyond this | `sig_react` |
| Lane change duration, quintic, per-driver lognormal | ADAPTED | Report 05 fit on 36,000 events; profile against constant speed. Runs faster if the lane is running out | - |
| Steering limit 45° at a crawl | INVENTED | Lets a queue-bound car nose in. With 12° or 25° wrong-lane waits rose several-fold on signal approaches; no measurement | `lc_slope` |
| Offset stop points at a lane end: 5 m, 12 m on every second lane | ESTABLISHED | Handbok för kapacitetsanalys med simulering, p. 106 (Trafikverket). Kept on the lane with no way on: on a short lane the point would otherwise lie back in the junction | `stop_base`, `stop_offset`, off with `--human-off offset` |
| Removed: side-by-side swap, forced yield at 90 s, the wait term, the pair hash | | Report 15 rows 17, 18, 20, 21 | - |

## Missed turns

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Give up the turn, carry on in the lane, new route; counted as lost | ESTABLISHED | Aimsun Lost Inside and Outside, TfL | off with `--human-off miss` |
| Time at standstill, per-driver draw | ADAPTED | Aimsun's per-vehicle give-way time | |
| Mean 120 s, 0.5-1.5 × per driver | INVENTED | No source; sensitivity swept in cities | `t_miss` |
| Nobody waits on a lane shorter than 15 m, the route is given up on reaching its end | INVENTED | 11,015 of 82,709 lanes in Stockholm and 4,722 of 84,546 in Berlin are under 15 m, most of them stubs between two junctions, where no one can change lanes. Waiting there blocks the junction behind | `stub` |

## Junctions and signals (`step.wgsl`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Yellow: stop if time to line ≥ driver's threshold, logistic 5.1 s, 0.54 s | ADAPTED | DLR Urban Traffic, one Sunday, report 05. Those who go keep going into red for at most 2.5 s to the line | off with `--human-off yellow` |
| Gap acceptance in place of SUMO's arrival windows | ESTABLISHED | TRVMB, Aimsun, HCM family | - |
| Critical gap per link, by movement, sign and major road speed | ESTABLISHED | TRVMB Kapacitet table 3, held per link by the physics (`Link::tc`, less 1.2 s for clearing). Applied everywhere: no Berlin table is open | `tc_scale`, `tc_clear` |
| Those gaps × 0.65 for the human, then × the driver's lognormal factor | ADAPTED | With the driver's spread, 1.0 gives half of Siegloch's capacity at major flows over 600 veh/h; 0.65 keeps it within 25%. Log-SD 0.26 from the Swiss roundabouts | `gap_junction` |
| Gap test from when the car would reach the line, in place of SUMO's arrival windows | ESTABLISHED | TRVMB, Aimsun, HCM family | - |
| Roundabout: 2.95 s target, entry test value 1.5 s | ADAPTED | Swiss roundabouts, report 05, one day. The value is by analogy with the factor above; the estimator on simulated traces does not reach the target (see report 16) | `gap_roundabout` |
| Lowest corner speed 8 m/s, on the shape limit and up to twice the lane limit | INVENTED | netconvert's corners give 2 to 4 m/s under the driver curve rule. 8 puts the roundabout's critical gap and follow-up on the Swiss 2.95 and 3.0 s at 300 veh/h per arm, right turns at 1,449 and left at 1,569 per green hour against TRVMB's 1,700. On a lane radius of 5 m it asks 12.8 m/s² of the shape, which the lane's drawn shape overstates; this shows in QA as lateral findings | `turn_min` |
| Sees a give-way line from 30 m | INVENTED | SUMO's 9 m makes every car slow to walking pace with no one coming | constant |
| Exit-clear compliance 90% | ESTABLISHED | Vissim percentage, physics branch | `exit_comply` |

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
