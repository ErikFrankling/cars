# The human driver: where every rule and number comes from

Classes as in `research/truth/15-how-the-best-simulators-do-it.md` Part 2. **ESTABLISHED**: a named source does the same. **ADAPTED**: a named source, changed as stated. **INVENTED**: no source; always a parameter, with a sensitivity test. The physics underneath is in `research/physics-provenance.md`. Parameters are set with `cars run --tune name=value`, rules switched off with `--human-off`. Results: `research/truth/16-human-build.md`.

## Car following (`common.wgsl`, `MODEL_HUMAN`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Linear gap and speed feedback, 1 s response lag, correlated noise | ADAPTED | Stimulus-response family, MITSIM [Ahmed 1999]; report 05 fit. Kernel replay within 2% of report 05's Python on I-395, I-90, A39 | - |
| k1 0.011, k2 0.52, √(15/g), T 1.30, amax 1.80, σ 0.20, τ_a 1.0, t_start 0.6 | ADAPTED | Report 05 section 8, fitted or measured there. k2 √(15/g) and level of σ are flagged there | constants |
| Gipps' rule towards a stopped or nearly stopped target (below 0.5 m/s) | ADAPTED | Gipps, as in Aimsun. Replaces the feedback there, because the feedback, fitted only on following, crawled the last 100 m to a queue and left 12-15 m in queues. Report 05 never saw this: its queue tests started from a formed queue | - |
| Approach deceleration 1.2 m/s², reaction term 2 s, stop margin 1.4 m, 0.5 m/s threshold | INVENTED | Chosen to pass item 10-12 with replay unchanged. 1.2 agrees with "almost nobody brakes harder than 2 m/s²" and TGSIM's median yield of 1.27 m/s² | constants, not yet `--tune` |
| s0 median 2.8 m × 1.2 | ADAPTED | Report 05 median, scaled in closed loop to measured standing spacing | `s0_scale` |
| Guard is the physics certificate, with the leader assumed to brake no harder than the driver can | ADAPTED | Report 11 certificate; against SUMO's own settings report 05 asked for a lax guard. With leader braking at b_hi it held time gaps above 1.2 s at 34 m/s, against 0.8 s measured | - |
| Desired speed = lane limit × speedFactor | ESTABLISHED | SUMO, TfL | - |

## Lane changing (`lc.wgsl`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Reasons to change, look-ahead | ESTABLISHED | LC2013 strategic stage | - |
| Critical gaps for a mandatory change: lognormal, one driver term, remaining distance | ESTABLISHED | Lee 2006 table 5.1, I-80 | - |
| Constants of those gaps shifted, lead −6, lag −2 | ADAPTED | Lee and Choudhury (section 5.4.2) recalibrate constants per site in MITSIMLab. The size here is large, and the certificate floor then binds most of the time | `lead_shift`, `lag_shift` |
| Critical gaps for a discretionary change | ESTABLISHED | Ahmed 1999, as tabulated in Lee table 2.3 | - |
| Physical floor under any gap: the certificate × 0.6 | ADAPTED | Vissim's factor 0.6 during a change, on our certificate | `lc_safety` |
| Urgency by remaining distance only, no time terms | ESTABLISHED | Rao, Lee, Aimsun zones, TRANSIMS, I-80 in report 14 | `r_urg` |
| Follower yields by a fixed share of drivers | ESTABLISHED | Aimsun "cooperation creating a gap", Choudhury's "probability of yielding". Value 0.4 from the I-80 sweep | `cooperation` |
| Yield limited by a deceleration | ESTABLISHED | Vissim CoopDecel −3 m/s² | `coop_decel` |
| Two-leader anticipation, with limited deceleration | ESTABLISHED | Aimsun. No advice when the leader is alongside and not getting ahead, else side by side cars hold each other | off with `--human-off anticipate` |
| Blinker: 93% signal, 1 s reaction | ADAPTED | Field share Sweden, 103 drivers; reaction is ours. No time term beyond this | `sig_react` |
| Lane change duration, quintic, per-driver lognormal | ADAPTED | Report 05 fit on 36,000 events; profile against constant speed. Runs faster if the lane is running out | - |
| Steering limit 45° at a crawl | INVENTED | Lets a queue-bound car nose in. With 12° or 25° wrong-lane waits rose several-fold on signal approaches; no measurement | constant |
| Offset stop points at a lane end: 5 m, 12 m on every second lane | ESTABLISHED | Handbok för kapacitetsanalys med simulering, p. 106 (Trafikverket) | `stop_base`, `stop_offset`, off with `--human-off offset` |
| Removed: side-by-side swap, forced yield at 90 s, the wait term, the pair hash | | Report 15 rows 17, 18, 20, 21 | - |

## Missed turns

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Give up the turn, carry on in the lane, new route; counted as lost | ESTABLISHED | Aimsun Lost Inside and Outside, TfL | off with `--human-off miss` |
| Time at standstill, per-driver draw | ADAPTED | Aimsun's per-vehicle give-way time | |
| Mean 120 s, 0.5-1.5 × per driver | INVENTED | No source; sensitivity swept in cities | `t_miss` |

## Junctions and signals (`step.wgsl`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| Yellow: stop if time to line ≥ driver's threshold, logistic 5.1 s, 0.54 s | ADAPTED | DLR Urban Traffic, one Sunday, report 05. Those who go keep going into red for at most 2.5 s to the line | off with `--human-off yellow` |
| Gap acceptance in place of SUMO's arrival windows | ESTABLISHED | TRVMB, Aimsun, HCM family | - |
| Critical gap table by movement and sign, +0.45 s per 10 km/h | ESTABLISHED | TRVMB Kapacitet table 3. Applied everywhere: no Berlin table is open | - |
| Those gaps × 0.5 in the entry test | ADAPTED | The test runs from when the car would reach the line and foes count until they clear. With 0.5, minor road capacity meets Siegloch with TRVMB's 5.1 s, within 25% at major flows up to 640 veh/h | `gap_junction` |
| Roundabout: 2.95 s target, entry test value 1.5 s | ADAPTED | Swiss roundabouts, report 05, one day. Value by analogy with the factor above; the estimator on simulated traces does not reach the target (see 16) | `gap_roundabout` |
| Lowest corner speed 6 m/s, on the shape limit and up to twice the lane limit | INVENTED | netconvert's corners give 2 to 4 m/s under the driver curve rule. Brings turning flows from 700 to about 1,300 per green hour, against TRVMB's 1,700 | `turn_min` |
| Sees a give-way line from 30 m | INVENTED | SUMO's 9 m makes every car slow to walking pace with no one coming | constant |
| Exit-clear compliance 90% | ESTABLISHED | Vissim percentage, physics branch | `exit_comply` |

## Sweden (`--region sweden`)

| Rule or number | Class | Source and what changed | Parameter |
|---|---|---|---|
| T × 0.55, s0 × 0.47 | ADAPTED | Scaled to TRVMB's 1,900 per green hour and 7.43 m. These are design values there, not measurements. T this low is not what replay finds on US and German roads | `t_scale`, `s0_scale` |
