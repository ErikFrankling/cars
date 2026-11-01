# The human driver on the GPU: what was built and how it measures

Date: 2026-11-01. Everything here ran on the GPU kernel unless marked **software GPU** (llvmpipe, used only for quick debugging). Raw results are in `/home/erikf/projects/personal/cars-data/truth/humans/`. Provenance of every rule and number: [`crates/cars-core/src/shaders/HUMAN.md`](../../crates/cars-core/src/shaders/HUMAN.md).

Run it with `cars run --humans`, or `carFollowModel="Human"` on a vType, in physical mode. `--human-off RULE` switches a rule off, `--tune name=value` moves a number, `--region sweden` uses Trafikverket's values. `--sumo-compat` never sees any of it.

## What changed after the review

Report 15's Part 3 was applied:

- **Gone:** the side-by-side swap, the forced yield at 90 s, the 60 s wait term, the pair hash. Courtesy and urgency have no time terms.
- **In:** stop points 5 and 12 m short of a lane end on alternate lanes (Trafikverket), Aimsun's two-leader anticipation, a cooperation share, rerouting with lost-car counts and `t_miss` as a per-driver draw, exit-clear compliance (shared with the physics branch).

## Decision on the merge model

**Lee 2006 replaces report 14's logit.** Theses read in full through the DSpace API: Lee 2006, Choudhury 2007 (ch. 5). Ahmed 1999 is scanned, so its discretionary table is taken as tabulated in Lee. Files in `cars-data/truth/practice/humans-20261101/`.

Held-out log likelihood per car, per second decisions ([merge_models.json](human-build/merge_models.json)):

| Model | I-80 later runs (420 cars) | US-101, other site (349) |
|---|---:|---:|
| Report 14's start logit, refit on I-80's first run | **−2.60** | −15.52 |
| Lee 2006, published I-80 coefficients | −5.09 | **−3.33** |
| Lee's form, refit on the same run | −4.27 | −9.21 |
| Choudhury 2007, published, as I could implement it | −11.50 | −5.39 |

- On another site Lee beats the logit by 12.2 nats per car (paired 95% CI 11.5 to 12.8). On the same site the logit wins by 2.5 (2.0 to 3.0). We run in other cities, so the transfer test decides.
- **My Choudhury result is not a fair test of his model.** He reports −2.98 per car and I get −11.5 on I-80. His density and lead acceleration are approximated, and table values come from OCR. The latent plan model is not ruled out. Lee's −5.09 is also worse than his own −3.04, for similar reasons.
- **Lee's published constants do not transfer to this kernel in closed loop.** Waits are 60 s against 22.6 s at I-80's flows. Both authors recalibrate constants per site. Shifting lead by −6 and lag by −2 in log metres passes the wait bands, but a shift that size means the certificate floor decides most acceptance, not Lee's gaps. Lee's distance form stays. His gap sizes are in practice not what binds.
- **Cooperation is a share of drivers**, as Aimsun and MITSIMLab, with no published value. 0.4 here.

## Bugs the closed loop found in report 05's spec

Report 05's queue tests started from a formed queue, so three things never showed:

1. The feedback, fitted on following moving cars, made cars crawl towards anything standing: about 1.6 m/s from 50 m. Replaced by Gipps' rule below 0.5 m/s. Replay did not change.
2. The closing guard brakes from any distance, so a car started slowing for a stop line 300 m ahead.
3. `a_t > 0.05` leaves a stopped car up to 4.5 m short for good, since `k1` is so small.

The guard also needed a change: assuming the leader can brake at b_hi held time gaps above 1.2 s at 34 m/s, against 0.8 s measured, and A39 replay error at 18.7 m against 11.3 m. The human guard now assumes the leader brakes no harder than the driver can.

## Acceptance test of report 05, on the GPU

At `--dt 0.1` unless stated, final build. Run with `scripts/human_replay.py` and `scripts/human_tests.py`; outputs in `truth/humans/accept2` and `accept3`.

| # | Test | Target, band | Result | |
|---:|---|---|---|---|
| 1 | Replay spacing RMSE, I-395 later | Python 5.93 ±5%, below Krauss | 5.94 (dt 1: 6.14) | **pass** |
| 2 | Same, I-90/94 run 6 | 4.15 | 4.13 (4.22) | **pass** |
| 3 | Same, I-90/94 moving | 4.00 | 3.98 (4.05) | **pass** |
| 4 | Same, A39 later | 11.30 | 11.22 (11.51) | **pass** |
| 5 | Replay speed RMSE | 0.64, 0.57, 0.63, 1.06 ±5% | 0.64, 0.58, 0.63, 1.05 | **pass** |
| 6 | Chain SD position 8 ÷ 1 | 0.90-1.15 | 1.04 (1.06) | **pass** |
| 7 | Chain wave speed | 27-43 km/h | 34.4 (34.4) | **pass** |
| 8 | Chain time gap p5, p50, p95 | 0.92, 1.96, 3.87 ±20% | 0.85, 1.94, 3.63 | **pass** |
| 9 | Ring, 22 cars 230 m | over 10% stopped, 15-30 km/h | 66-76% stopped, 22-25 km/h; dt 1: 20-49%, 28-34 km/h | **pass at dt 0.1 and 0.5**, marginal at dt 1. Mean speed 0.4 m/s is far below Sugiyama's: too jammed |
| 10 | Saturation headway | 1.8-2.2 s | 2.36 (dt 0.5: 2.29, dt 1: 2.33) | **fail**, 5-7% over. The Gipps limit below cost 0.1 s at dt 0.5 |
| 11 | Lost time, first 4 | 2.2-3.6 s | 2.68 (dt 0.5: 2.30, dt 1: 0.99) | **pass** at 0.1 and 0.5, fail at dt 1 |
| 12 | Standing spacing | 7.0-8.2 m | 7.41 (dt 0.5: 6.53, dt 1: 6.77) | **pass** at dt 0.1, fail at 0.5 and 1 |
| 13 | Lane change 10-90 time | 4.8-6.0 s | 5.09 free, 4.77 congested | **pass**, congested just under |
| 14 | Both-lane time | 2.4-3.2 s | 2.83, 2.65 | **pass** |
| 15 | Peak lateral speed | 0.6-0.9 m/s | 0.60, 0.64 | **pass**, at the bottom of the band |
| 16 | Accepted gaps, congested: lag p5, lead p5 | 0.56, 0.33 s ±30% | 0.66, 0.43 | **pass**, lead on the edge |
| 17 | Same, free flow | 0.70, 0.61 s ±30% | 0.37, 0.79 | **fail** on lag, pass on lead |
| 18 | Yellow: half stop at | 4.5-5.7 s | 4.90, slope 0.40 s. Stopping braking median 1.68, p95 3.47 m/s². 33% of goers cross after red, p95 1.5 s (measured 25%, 1.0 s) | **pass** |
| 19 | Roundabout critical gap, follow-up | 2.65-3.25, 2.3-3.1 s | 2.95, 3.0 at the inflow whose rejection share matches the Swiss sites (300 veh/h per arm, 12%). 2.40 and 3.5 at 250, 4.07 and 3.5 at 350 | **pass at 300 veh/h only**, strongly flow dependent, see below |
| 20 | Overlaps and guard | under 0.5% of windows, guard under 1% of steps | overlaps at most 0.06%, guard at most 0.16% at dt 0.1. Cities at dt 1 not yet remeasured on this driver | **pass at dt 0.1**, earlier fail at dt 1 stands |

**Item 19, what changed.** The earlier 5.60 and 4.0 were mostly the estimator. `scripts/human_roundabout.py` now uses the definitions of `research/truth/scripts/opus_roundabout.py`, the Swiss analysis: arrival within reach of the line, crossing at the ring's outer edge, ring cars counted where they pass the entry and not if they left before it, follow-ups only with no ring car between. Raising the corner floor from 6 to 8 m/s then brought the median to 2.95. Measured on software GPU, 3 seeds, dt 0.5:

| Inflow, veh/h per arm | Rejected any | Critical gap, log SD | Follow-up | Accepted p05, p50 | Wait p50, p90 |
|---:|---:|---|---:|---|---|
| 200 | 5% | 2.02, 0.57 | 3.5 | 3.5, 13.0 | 1.5, 4.5 |
| 250 | 10% | 2.40, 0.65 | 3.5 | 4.0, 11.5 | 1.5, 7.5 |
| 300 | 12% | 2.95, 0.59 | 3.0 | 4.0, 10.5 | 2.0, 9.0 |
| 350 | 22% | 4.07, 0.57 | 3.5 | 4.5, 11.5 | 2.5, 16.0 |
| Swiss sites F1, F2, L1 | 9-23% | 2.65-3.25, 0.23-0.25 | 2.5-3.15 | 3.3-3.8, 6.4-7.8 | 1.2-1.6, 2.1-4.2 |

So the median can be hit, but the model's spread is more than twice the measured one, long waits are too common, it depends on flow where the data barely do, and accepted gaps are too long. `gap_roundabout` still barely moves any of this: lowering it to 0.5 raises rejections. Partly that is horizon: a ring car at 6 m/s only announces itself about 3 s ahead, and announcing it 6 s ahead changed nothing here, so that was removed again.

## Trafikverket's values, `--region sweden`, on the GPU

| Quantity | TRVMB | dt 1 | dt 0.1 | |
|---|---:|---:|---:|---|
| Through, per green hour | 1,900 | 1,782 | 1,858 | fail at dt 1 (−6%), pass at 0.1 |
| Right, left | 1,700 | 1,449, 1,569 (dt 0.5: 1,413, 1,502, with the 8 m/s corner floor) | 1,452, 1,434 with the 6 m/s floor | **fail**, −8 to −17% |
| Double turn | 1,500 | 1,548 | 1,199 | pass at dt 1 only |
| Jam spacing | 7.43 m | 7.9-8.2 | 8.4 | **fail**, +0.5 to +1 m |
| Minor road across major at 100, 300 veh/h | Siegloch 1,056, 856 | 924, 864 | 921, 897 | pass |
| At 600, 900 veh/h | 626, 455 | 468, 243 | 498, 270 | **fail** at high major flow, −25 to −47% |

Fitting these took T × 0.55, which is not what replay finds on US and German roads. Whether Swedish drivers follow that close is not known: these are design values, not measurements.

## Courtesy tests of report 14

**A. Lane end shaped like I-80** (cooperation 0.25-0.5, two seeds each, final build):

| Measure | Band | Result | |
|---|---|---|---|
| Wait median, p90, p99, max | 21-24.5, 41-46, 62-77, under 100 | 21-22.5, 40-43.5, 51-53, 55-57 | median, p90 and max **pass**, p99 **fail**: too few long waits |
| KS to the 610 I-80 waits | at most 0.15 | 0.07-0.09 | **pass** |
| Main-lane cars between ramp cars | mode 1, 0 under 35%, 1 over 35%, mean 1.25 ± 0.3 | 14-15%, 64-65%, 1.08-1.10 | **pass** |
| Passes per car | 0 for 50-65%, max at most 8 | 77-82%, max 1-2 | **fail**: too few passed |
| Let in per resolved vehicle | 0.59 ± 0.08, 0.9 falling to 0.35 with closing | 0.83-0.88 on the final driver | **fail**, see small scene fixes |
| Stopped first | 25-50% | 33-35% after the Gipps limit | **pass** |
| Failed to get in | 0 | 0 | **pass** |

**B. Followers, on simulated traces** (simplified from `courtesy_events.py`): see `accept2/lc01`. Peak braking median about −1 m/s² is in band. Excess hold-back is not: followers here do not visibly hold back more than matched pairs. **Fail.**

**C. Free flow on the A39 shape:** median wait 9.5 s against 3.4 s. **Fail.** All cars get in.

**D. Stuck cases, five signal approaches and four deadlock units:** no teleports, no collisions, no unfinished units. Deadlock units all finish, and the side-by-side pair resolves through the offset stops. The approaches with a 2 m/s neck ahead do not drain within the run, which is the neck's capacity, not a lock, except 30 m at 2,000 veh/h: 36 vehicles stuck, wrong-lane wait up to 2,971 s, 4 s × speed does not fit a 30 m lane. **That one fails.** The owner dropped the comparison with SUMO, so "no worse than LC2013" was not run.

**Cooperation sweep, as Hidas warned.** No throughput loss here: from 0 to 1 at an open merge, flow goes from 2,279 to 2,364 veh/h (+4%) and main road speed from 5.14 to 5.84 m/s. At I-80's flows, waits fall from 22 to 19.5 s. So the sign is the opposite of Hidas's ARTEMiS result in this model. Passes barely respond, so the share of drivers is not what sets the let-in rate here: the gaps are.

## Capacity drop, relaxation, hysteresis, on the GPU

- **Relaxation: pass.** Time gap after a cut-in at 0, 2, 5, 10, 15, 20, 25 s: 0.73, 0.84, 0.93, 1.08, 1.21, 1.34, 1.42. Measured on I-395: 0.72, 0.75, 0.88, 1.09, 1.22, 1.31, 1.41.
- **Capacity drop: fail, not produced.** Queue discharge is 5-14% above the flow before breakdown, at about 1,430 veh/h per lane. On a free single lane this model tops out near 1,640 veh/h, not far above its queue discharge. So there is no high pre-breakdown state to fall from. Keane & Gao's relaxation is there, but the top of the fundamental diagram is not. Treat any city result on bottleneck throughput with that in mind.
- **Hysteresis: no target.** A slow car entering a stream at 1,500 veh/h drops flow to about 880-1,300 veh/h in the wave, and it recovers to 1,400-1,650 at lower density. Open and closed branches differ, but no data-based band exists.

## Small scene fixes after the review of the misses

All **software GPU** (llvmpipe), dt 0.5 unless stated, then repeated on the GPU only through the city runs. Commits 4b920ba to 2a8b319.

**A short lane with no way on.** At 10% of Stockholm's demand, heads had waited since the first minutes. Two read closely wanted lane 0 of an edge 2.9 and 6.6 m long while their junction lane fed lane 1. The offset stop point, 5 or 12 m before the lane end, lay back on the junction lane, where the missed-turn rule does not look, so each stood for good and blocked the junction behind. Stockholm has 11,015 lanes under 15 m of 82,709, Berlin 4,722 of 84,546. Now the stop point stays on the lane, and a driver who reaches the end of a lane under 15 m gives the route up at once. `scripts/human_tests.py stub_lane`: on a 5 m stub, 7 of 96 inserted cars arrived in 1,200 s before, and 140 of 140 now, 20 of them lost. No contacts.

Cost, on the old demand on the GPU: Stockholm at 10% stuck at the end 2,658 → 970, arrived 22,933 → 25,142, jam and yield cases 658, 255 → 156, 110. At full demand arrived 96,780 → 110,912, stuck at the end 75,906 → 70,520. These two runs also carry the physics merge, so they do not separate its share. Contacts rose: 5,709 → 7,293 at full demand, same lane 251 → 719, lane start 662 → 1,089. Not explained yet; small scenes show none. Route patches rose to about 20 for each lost car at 10% demand, 21,963 for 1,091 cars: the router works on edges, so a new route can meet the next short wrong lane.

**Queue formation.** A queue formed with half the cars 1 m or less apart and braking to −8 m/s². The closing rule trusts the leader to keep its speed, so followers brake late as a leader slows and each brakes harder. A Gipps limit behind a moving leader fixes the spacing and leaves replay in band, and lowers guard use in replay from at most 0.75% to at most 0.16%. It sits apart from `hu_target`: inlined in every lane change kernel, llvmpipe's JIT took over 10 minutes on the first lane change.

| | Saturation headway, 1.8-2.2 | Lost time, 2.2-3.6 | Standing spacing, 7.0-8.2 |
|---|---|---|---|
| Before, dt 0.1 / 0.5 / 1 | 2.32 / 2.16 / 2.34 | 2.29 / 2.21 / 0.54 | 6.13 / 5.98 / 6.49 |
| After | 2.36 / 2.29 / 2.33 | 2.68 / 2.30 / 0.99 | 7.41 / 6.53 / 6.77 |

Discharge is the remaining miss: it does not close up after the start, because the fitted spacing term `k1` is so weak. Lower `T` barely helps with the limit on. Spacing and discharge pull against each other here.

**Let-in, 0.83-0.88 against 0.59.** A grid over the critical gap shifts, safety factor and cooperation found the cause: real I-80 drivers cross with 0.9 m of lane left and are passed on the way, and here they cross 80 m early. Larger gaps far from the lane end move them down the lane, and with low cooperation let-in reaches band, but they queue for the lane end and waits miss. No setting tried passes both:

| Setting | Wait p50, p90 (22.6, 43.7) | KS, max 0.15 | Unpassed (57%) | Let-in (0.51-0.67) | Stopped (25-50%) | Left at crossing, m (0.9) |
|---|---|---:|---:|---:|---:|---:|
| Default | 20.5-22, 42-43 | 0.04-0.08 | 83-89% | 0.83-0.88 | 33-35% | 79-85 |
| `lead_far=-1,lag_far=-1,cooperation=0.1`, neck 20 m/s | 27.5, 43 | 0.16 | 70% | 0.76 | 32% | 29 |
| `lead_far=0,lag_far=0,cooperation=0.1` | 38, 53.5 | 0.42 | 55% | 0.66 | 42% | 15 |
| `lead_far=0,lag_far=0,cooperation=0` | 40, 57 | 0.43 | 49% | 0.61 | 49% | 15 |

The default stays, because waits are the measured quantity most tied to Erik's question. **Let-in and passes remain a fail.**

**Capacity drop: still not produced.** Three seeds on the final driver, flow before breakdown 2,460-2,604 veh/h, discharge 2,770-2,786: 7-13% above, not below. Upstream speed falls from the start, at about 1,200 veh/h per lane: there is no high flow state to fall from. `T` × 0.7, the Swedish values and switching off courtesy and anticipation do not change the sign. One earlier seed read +7.8%, from the 5 minute noise in the maximum. A method for this needs a state with short headways at high speed that this fit has no term for.

**Why the latest physics commits are not in this build.** Merging the 6 commits now on `t3/1c6fee50` (including `908f4b8` and `cafce4d`) builds, but a kernel spins on the I-80 scene between t = 1,180 and 1,200 s. Under gdb the hot thread, on seed 1, is in JITed kernel code. Seeds 2 and 3 also do not finish in 30 s, where the previous build takes 8 s. It survives `exit_clear=0`, `arbiter=0`, `lc_path=0`, `rewind=0`, `zone_time=0` and `--human-off miss`, and does not appear with demand ending at 400 s. The cause is not found. The merge was aborted and that binary was never put on the GPU, where a kernel like this could stall the desktop.

## Sensitivity of the invented numbers

**Software GPU**, one seed, dt 0.5, final driver. Queue at a signal, lane end at 800 and 600 veh/h, give-way at 600 and 500 veh/h. No collisions in any case.

| Number | Value | Saturation headway s | Lost time s | Standing spacing m | Lane end wait p50 / p90 s | Minor road flow veh/h | Collisions |
|---|---:|---:|---:|---:|---|---:|---:|
| default |  | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| b_approach | 0.9 | 2.53 | 0.81 | 6.70 | 24 / 63 | 360 | 0 |
| b_approach | 1.6 | 2.24 | 1.95 | 6.32 | 28 / 74 | 342 | 0 |
| tau_approach | 1.5 | 2.29 | 1.73 | 5.72 | 22 / 66 | 348 | 0 |
| tau_approach | 3.0 | 2.59 | 1.37 | 7.14 | 26 / 65 | 366 | 0 |
| overshoot | 0.7 | 2.38 | 1.02 | 6.15 | 28 / 59 | 357 | 0 |
| overshoot | 2.1 | 2.32 | 2.36 | 6.43 | 22 / 62 | 366 | 0 |
| standing | 0.2 | 2.33 | 1.31 | 6.58 | 24 / 57 | 375 | 0 |
| standing | 1.0 | 2.53 | 1.67 | 5.67 | 27 / 68 | 333 | 0 |
| see | 15 | 2.37 | 1.45 | 6.51 | 26 / 63 | 324 | 0 |
| see | 60 | 2.37 | 1.45 | 6.51 | 26 / 63 | 318 | 0 |
| lc_slope | 0.42 | 2.37 | 1.45 | 6.51 | 24 / 58 | 354 | 0 |
| lc_slope | 1.73 | 2.37 | 1.45 | 6.51 | 23 / 60 | 354 | 0 |
| stop_s0 | 0.5 | 2.37 | 1.36 | 6.51 | 24 / 65 | 336 | 0 |
| stop_s0 | 2.0 | 2.37 | 1.60 | 6.54 | 20 / 61 | 351 | 0 |
| comfort | 1.0 | 2.37 | 1.45 | 6.51 | 23 / 60 | 336 | 0 |
| comfort | 2.5 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| turn_min | 4 | 2.37 | 1.45 | 6.51 | 26 / 63 | 327 | 0 |
| turn_min | 8 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| t_miss | 60 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| t_miss | 240 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| gap_junction | 0.5 | 2.37 | 1.45 | 6.51 | 26 / 63 | 375 | 0 |
| gap_junction | 1.0 | 2.37 | 1.45 | 6.51 | 26 / 63 | 273 | 0 |
| gap_roundabout | 1.0 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| gap_roundabout | 2.5 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| stub | 5 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |
| stub | 30 | 2.37 | 1.45 | 6.51 | 26 / 63 | 354 | 0 |

Largest effects: `turn_min` and `gap_junction` on the minor road, `b_approach`, `tau_approach` and `standing` on lost time and spacing. `see` moves the minor road by about 10%, both ways down, so 30 m is not obviously right. `t_miss`, `gap_roundabout` and `stub` do not move these scenes at all, so their sensitivity is only known from cities, the roundabout scene and `stub_lane`.

## Cities

**Stockholm on report 02's recipe: not run yet.** Net `truth/stockholm/factorial/n7_ramps.net.xml`, routes `v2_c4.rou.gz`, 60% demand, morning 06:00-10:00 and then the full day, in `truth/humans/city5/table.jsonl`. This is the run that tests the driver and not the demand. Everything below used demand since shown to be the top cause of lockup, so it says little about the driver.

**Dropped at the orchestrator's request, because full-demand gridlock swamps a one-rule difference:** Berlin morning `humans`, `no-courtesy`, `no-offset`, `no-miss`, `no-anticipate`, `no-gate`, `no-yellow`, `no-shrink`, `tmiss30`, `tmiss240`, `coop0`, `coop1.0`, `comply1.0`; `berlin-day`; Stockholm's second sweep on the fixed driver; the two U-turn demand variants; the trace runs on the fixed driver. Requeue only on demand that does not lock.

So **how many of the 9,930 "waiting for a gap" cases vanish in the Berlin day is not answered.**

Earlier driver, before the stub fix, dt 1, teleports off:

| | Inserted | Arrived | Stuck: jam, yield, gap | Stuck at end | Contacts | Mu/s |
|---|---:|---:|---|---:|---:|---:|
| Berlin morning, Krauss physical | 286,323 | 49,367 | 10,935, 7,252, 720 | 222,559 | 3,837 | 3.2 |
| Berlin morning, humans | 277,844 | 65,124 | 13,401, 9,336, 251 | 198,201 | 2,097 | 2.4-3.3 |
| Stockholm old demand, Krauss physical | 183,829 | 100,834 | 5,258, 2,625, 283 | 77,641 | 7,731 | 5.9 |
| Stockholm old demand, humans | 177,763 | 96,780 | 6,046, 3,024, 106 | 75,906 | 5,709 | 4.9 |
| Stockholm old demand, humans, stub fix and physics merge | 187,560 | 110,912 | 5,966, 2,974, 98 | 70,520 | 7,293 | 2.7 |

The "gap" class falls 65%, while the jam and yield classes, which dominate, grow. All are gridlocked. On that Stockholm demand no rule moved the stuck count by much: without courtesy 72,006, `t_miss` 30 and 240 gave 73,635 and 74,737, cooperation 0 and 1 gave 72,040 and 71,338, stuck at the end. Speed cost is noisy under shared use and is not a clean measure: the 2.7 Mu/s run shared the machine.

A demand finding on the way: 127,029 of 275,935 repaired Stockholm routes contain a U-turn on the same road, 27,250 of them at the first step. Cycles there are mostly a lane and its reverse. Report 02 now covers this ground.

**Physics QA**, on traces of the earlier driver. No backward steps and no teleports in either. Stockholm, 55,455 vehicles: 59 samples brake harder than −4.5, none past the dry limit; 3,864 lateral samples over 8 m/s² on 2,372 lanes, kinked net geometry. Berlin box: braking at most −4.11; 19 samples over 8 m/s² on 15 lanes, peak 16.1 with 21.6 km/h corners on radii of 2-3 m, which is the corner floor. Raising that floor to 8 m/s will worsen this; not remeasured. The courtesy scene has two hard failures: forward acceleration over capability, 4 of 61,450 samples by 0.067 m/s², from noise, where a clamp stopped cars starting and was removed; and lateral speed, 16 of 2,048 samples up to 2.5 m/s where the lane is running out.

Clips, from the earlier driver and old demand, in `cars-data/videos/gallery/humans/`: `gridlock_stockholm_verkstadsgatan.mp4`, `gridlock_berlin_cycle.mp4`, `courtesy_i80_0.mp4`, `courtesy_i80_1.mp4`. The gridlock frames show ordinary long queues at give-way junctions, at 1-2 km/h city mean.

## Replay against Wiedemann and Gipps

Spacing / speed RMSE over 30 s on the same frozen windows ([replay_w99.json](human-build/replay_w99.json)). Lower is better:

| Model | I-395 later | I-90 run 6 | I-90 moving | I-294 | A39 later |
|---|---|---|---|---|---|
| `MODEL_HUMAN`, GPU kernel | **5.94** / 0.64 | **4.13** / 0.58 | **3.98** / 0.63 | **10.65** / 1.47 | **11.22** / 1.05 |
| Gipps, calibrated | 6.16 / 0.68 | 5.04 / 0.71 | 5.05 / 0.70 | 11.55 / 1.31 | 12.92 / 1.25 |
| Wiedemann 99, calibrated | 6.39 / 0.72 | 5.25 / 0.68 | 5.36 / 0.70 | 13.30 / 1.49 | 13.34 / 1.29 |
| Wiedemann 99, Vissim defaults | 7.71 / 0.85 | 6.52 / 0.78 | 6.36 / 0.77 | 14.83 / 1.65 | 16.29 / 1.58 |

Fit with a smaller search than report 05's (1,200 windows, 25 generations), so the incumbents had less search. W99 is deterministic here, from the published form with Vissim's parameter names.
