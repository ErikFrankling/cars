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

**A short lane with no way on.** At 10% of Stockholm's demand, heads had waited since the first minutes. Two read closely wanted lane 0 of an edge 2.9 and 6.6 m long while their junction lane fed lane 1. The offset stop point, 5 or 12 m before the lane end, lay back on the junction lane, where the missed-turn rule does not look, so each stood for good and blocked the junction behind. Stockholm has 11,015 lanes under 15 m of 82,709, Berlin 4,722 of 84,546. Now the stop point stays on the lane, far enough along for a lane change to be allowed, and a driver who reaches the end of a lane under 7 m gives the route up at once. 15 m at first made cars lost who could have changed lane. `scripts/human_tests.py stub_lane`: on a 5 m stub, 7 of 96 inserted cars arrived in 1,200 s before, and 140 of 140 now, 20 of them lost. No contacts.

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
| default |  | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |
| b_approach | 0.9 | 2.53 | 0.81 | 6.70 | 26 / 57 | 360 | 0 |
| b_approach | 1.6 | 2.24 | 1.95 | 6.32 | 24 / 62 | 342 | 0 |
| tau_approach | 1.5 | 2.29 | 1.73 | 5.72 | 20 / 50 | 348 | 0 |
| tau_approach | 3.0 | 2.59 | 1.37 | 7.14 | 25 / 62 | 366 | 0 |
| overshoot | 0.7 | 2.38 | 1.02 | 6.15 | 24 / 62 | 357 | 0 |
| overshoot | 2.1 | 2.32 | 2.36 | 6.43 | 24 / 53 | 366 | 0 |
| standing | 0.2 | 2.33 | 1.31 | 6.58 | 22 / 66 | 375 | 0 |
| standing | 1.0 | 2.53 | 1.67 | 5.67 | 28 / 71 | 333 | 0 |
| see | 15 | 2.37 | 1.45 | 6.51 | 22 / 56 | 324 | 0 |
| see | 60 | 2.37 | 1.45 | 6.51 | 22 / 56 | 318 | 0 |
| lc_slope | 0.42 | 2.37 | 1.45 | 6.51 | 24 / 60 | 354 | 0 |
| lc_slope | 1.73 | 2.37 | 1.45 | 6.51 | 22 / 60 | 354 | 0 |
| stop_s0 | 0.5 | 2.37 | 1.36 | 6.51 | 22 / 58 | 336 | 0 |
| stop_s0 | 2.0 | 2.37 | 1.60 | 6.54 | 24 / 55 | 351 | 0 |
| comfort | 1.0 | 2.37 | 1.45 | 6.51 | 26 / 62 | 336 | 0 |
| comfort | 2.5 | 2.37 | 1.45 | 6.51 | 24 / 54 | 354 | 0 |
| turn_min | 4 | 2.37 | 1.45 | 6.51 | 22 / 56 | 327 | 0 |
| turn_min | 8 | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |
| t_miss | 60 | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |
| t_miss | 240 | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |
| gap_junction | 0.5 | 2.37 | 1.45 | 6.51 | 22 / 56 | 375 | 0 |
| gap_junction | 1.0 | 2.37 | 1.45 | 6.51 | 22 / 56 | 273 | 0 |
| gap_roundabout | 1.0 | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |
| gap_roundabout | 2.5 | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |
| stub | 5 | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |
| stub | 30 | 2.37 | 1.45 | 6.51 | 22 / 56 | 354 | 0 |

Largest effects: `turn_min` and `gap_junction` on the minor road, `b_approach`, `tau_approach` and `standing` on lost time and spacing. `see` moves the minor road by about 10%, both ways down, so 30 m is not obviously right. `t_miss`, `gap_roundabout` and `stub` do not move these scenes at all, so their sensitivity is only known from cities, the roundabout scene and `stub_lane`.

## Cities

**Stockholm on report 02's recipe.** Net `truth/stockholm/factorial/n7_ramps.net.xml`, routes `v2_c4.rou.gz`, 60% demand, 06:00-10:00, dt 1. Results in `truth/humans/city5/`. GPU runs are marked; the rest ran on the homelab on software GPU with 6 approach slots per link in place of 8, because of llvmpipe's 128 MB binding limit, so small differences are not meaningful.

| Driver, teleports | Arrived | Mean speed m/s | Inserted less arrived at 10:00 | Stuck over 300 s at 10:00 | Teleports |
|---|---:|---:|---:|---:|---:|
| SUMO copy, 120 s, ignore blockers 20 s | 193,579 | 11.59 | 8,693 | 0 | 669 (jam 104, yield 207, wrong lane 358) |
| SUMO copy, none, ignore blockers 20 s | 124,596 | 5.68 | 66,565 | 60,975 | 0 |
| SUMO copy, none | 119,745 | 5.52 | 70,903 | 65,548 | 0 |
| Human, none, after the fixes below | 62,059 | 3.19 | 111,672 | 104,922 | 0 |
| Human, none, before them (GPU) | 47,404 | 2.57 | 119,891 | 114,298 | 0 |
| Physical Krauss, none (GPU) | 25,113 | 1.61 | 134,933 | 132,453 | 0 |
| Human, 120 s, after the fixes | 147,803 | 5.13 | | 370 | 47,911 (jam 25,693, yield 19,123, wrong lane 3,095) |

**Does this demand lock without teleports for any driver? Yes, for all three here.** The SUMO copy, the driver the recipe was built on, reaches 0.55 m/s and 92% stuck by 10:00 with teleports off. Its 11.6 m/s depends on removing 669 cars in four hours, 0.3% of those inserted; 358 of them were in a wrong lane. So "a Stockholm that does not lock up" means one that does not lock up as long as teleports clear its seeds. Ignoring junction blockers does not save it.

**Is it also these drivers? Yes.** With the same 120 s rule the human needs 72 times the teleports of the SUMO copy and arrives 24% fewer. Without teleports it gets half the arrivals. After one hour it has 3,383 stuck against 1,281. Queue discharge explains some of this, at 1,782 per green hour through against 1,990 (software GPU, sigma 0.5, dt 1; right turn 1,449 against 1,424, left not measured). It does not obviously explain 19,123 yield teleports against 207, and give-way gaps are the next suspect. The contacts in the human 120 s run, 82,619 incidents with 17,408 on the same lane, show that teleport reinsertion was never fitted to physical mode, so that run's details are not to be leaned on.

**Where and when it starts: not a lone seed.** Stuck heads start waiting from about 06:02, with almost nobody on the road, in many places at once, then grow and join. This table is the human before the fixes on the GPU, and counts a lane once its head has waited 300 s:

| By | Stuck lanes | Cars on them | Separate areas (400 m cells), human | Largest, lanes | Same, Krauss |
|---|---:|---:|---:|---|---:|
| 06:10 | 9 | 41 | 4 | 4 | 10 |
| 06:15 | 35 | 184 | 13 | 8 | 30 |
| 06:25 | 194 | 1,636 | 21 | 28 | 53 |
| 06:40 | 475 | 4,704 | 30 | 60 | 53 |
| 07:10 | 1,260 | 14,846 | 28 | 285 | 40 |
| 08:00 | 4,222 | 50,793 | 19 | 3,364 | 24 |

The list holds at most 5,000 lanes, so the late rows undercount. Spread over the map like this, removing one blockage would not save the city; each kind of seed has to go.

**The first heads, and what they wait for.** Read with `--debug-lane` on a 25 minute run. Picture: `truth/humans/seed/first_seed_0614.png`.

| First stuck | Head | Waits for | Whose | State |
|---|---|---|---|---|
| 06:02, (22770,16512), both physical drivers | on `:1734187027_4_0`, about to enter the cluster | The arbiter denies a zone held by a car behind it in the same chain, which itself waits for this one. The left turn is built from two 0.2 m edges through a separate node beside the cluster | net and physics arbiter | **open**, physics agent's code |
| 06:02, (11725,17414), both | `24699166#0_0`, 2.7 m edge between two parts of one junction | Its own rear, still on the junction lane it now needs clear | arbiter | **fixed**, `zone_foe_is_self` |
| 06:03, human only | `636586780_0`, then `5376746#0_0`, `44674278_0` | Nothing it can reach: a new route answered seconds late overwrote the route of a car that had driven on | my rerouting | **fixed** |
| 06:00, human only, without the miss rule | `1039698245_1`, 8.5 m lane, wants lane 0 | Lane change refused: the offset stop left it at 4.91 m, and the physics asks for a 5 m body wholly on the lane first | my stop point against the physics rule | **fixed** |
| 06:05, both | `458964198_0`, `577190494#5_1`, lanes with no way on | Same, or a lane change that needs 15 m in Krauss | net, rule | fixed for humans, open for Krauss |

The SUMO copy has its own seeds at some of the same places, such as `43054916_0`, and wrong-lane heads such as `804598780_1`, waiting since about 06:05. Without the miss rule the human has 958 stuck after 15 minutes against 245 with it, on the same build.

Effect of the fixes, first hour, GPU before and software GPU after: stuck 7,006 → 3,383. Arrived 18,445 by 06:57 before, 23,070 by 07:00 after. Whole morning: arrived +31%, stuck −8%. With the arbiter off as well, 2,700 stuck, at the price of 1,708 contacts against 910, of which junction crossing 6 → 122. So the arbiter's zones make about a fifth of the first hour's stuck cars, and "next lane or right of way" still holds 8,466 of the heads at 10:00. Most of those are probably downstream queues by then, not seeds; I did not count them one by one.

How often the demand sets these traps: 34,219 of 790,967 vehicles (4.3%) have a route through a short edge where the lanes it arrives on do not lead on, and 83,604 (10.6%) a U-turn on the same road. Of the 74,599 road edges in this net, 1,661 are under 1 m and 4,374 under 7 m. Report 02 kept the turnarounds on purpose.

**The "other" contacts: net geometry, not driving.** "Other" means two cars on two different road edges, neither just entering. 99.1% of 19,403 such incidents in the fixed human morning are between lanes whose centre lines come within 1.8 m of each other, a car's width, so any two cars there overlap whatever they do. Across the 287 lane pairs the median closest distance is 1.04 m. 68% of the incidents are one pair of roads, `1156274841` and `747364395` at (13798,26155), which come within 0.2 m and stay within 1.8 m for 28-38 m before their shared node; the top 5 pairs hold 78%.

An incident is counted per pair of cars, so it grows with a queue on one lane times the stream passing it. That is why it rose from 2,007 to 9,055 between Krauss and the human: the human moves 2.6 times the vehicle kilometres (333,044 against 127,826), and Krauss freezes and stops making new pairs. It is also why the rate climbs through the morning, on the fixed driver from 3.9 per 1,000 km in the first hour to 41.9 over the morning, which is 19,403 incidents on 462,669 km. That queue times stream reading fits the counts but was not tested on its own. Fixing it means correcting these lane shapes or having the detector know them; I changed neither, so **the total contact count overstates real collisions by about ten to one**.

The rest are not explained away: same lane 253, neighbour lane 868, lane start 962, up from 173, 661, 510 before the fixes, with more traffic moved. These remain to be read. Zero collisions is not achieved.

One stall stays unexplained: a software GPU run of the fixed driver on the PC stopped progressing at t = 23,135 with one worker thread busy. The same code passed that time on the homelab, three times, so it is not reproduced. Rule-off runs and the full day (`hu-v2b`) were withdrawn as poor use of the queue on a scenario that locks.

**Dropped at the orchestrator's request, because full-demand gridlock swamps a one-rule difference:** Berlin morning `humans`, `no-courtesy`, `no-offset`, `no-miss`, `no-anticipate`, `no-gate`, `no-yellow`, `no-shrink`, `tmiss30`, `tmiss240`, `coop0`, `coop1.0`, `comply1.0`; `berlin-day`; Stockholm's second sweep on the fixed driver; the two U-turn demand variants; the trace runs on the fixed driver. Requeue only on demand that does not lock.

So **how many of the 9,930 "waiting for a gap" cases vanish in the Berlin day is not answered.**

Old demand, earlier driver, before the stub fix, dt 1, teleports off:

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

## Merging from report 18, and the audit in report 19

Frozen build `86f2256` on the software GPU at 128-bit vectors, dt 0.5 unless stated, two seeds. Not yet run on the real GPU: see the end of this section. Clips are in `cars-data/videos/gallery/humans/merge_*`.

**The driver does not yet merge like people. No site passes.** Contacts are zero at all four sites and nothing gridlocks, but the rows that describe the behaviour Erik asked about fail: cars stop too often, start moving over too rarely with a car alongside, and followers do not give way as measured.

| Row of report 18 | I-80 real / sim | US-101 | I-395 held out | A39 held out |
|---|---|---|---|---|
| Body over the line, m left | -3..17 / **14.2** | 108..168 / 46.2 | 21..41 / 16.9 | 285..365 / **286** |
| Stopped first | .18-.34 / .89 | 0-.02 / .40 | 0-.03 / .91 | 0-.01 / .06 |
| Overlap at sideways start | .24-.40 / .09 | .07-.19 / .01 | .29-.51 / .06 | 0-.02 / **.01** |
| Overlap at centre over line | 0-.08 / **0** | 0-.02 / **0** | .13-.32 / 0 | 0-.01 / **0** |
| Lag p25 at start, m | .6-2.6 / 3.2 | 2-4 / 5.7 | 1.1-3.1 / 3.5 | |
| Edge while overlapped p50, lanes | .03-.23 / 0 | -.1-.1 / **0** | .02-.22 / 0 | -.1-.1 / **0** |
| Edge while overlapped p95, lanes | .22-.52 / **.28** | .04-.34 / **.21** | .24-.54 / **.25** | .06-.36 / 0 |
| Gap ahead 5 s before | .11-.27 / .06 | .52-.72 / .07 | .01-.17 / **.05** | 0-.11 / **0** |
| Gap behind 5 s before | .19-.35 / **.33** | 0-.14 / .25 | .32-.48 / **.35** | .14-.34 / .13 |
| Alongside 5 s or more | .25-.41 / .83 | 0-.08 / **.07** | .18-.34 / .83 | 0-.03 / **.02** |
| Locked share | .03-.11 / **.04** | 0-.01 / **0** | .01-.05 / **.03** | 0-.01 / **0** |
| Overlapped in last 5 s | .36-.56 / .29 | .32-.52 / .13 | .35-.55 / .25 | 0-.03 / **.02** |
| Excess accel -2..0 s | .09-.25 / .06 | -.57..-.27 / .34 | -.16..-.04 / .15 | .42-.62 / none |
| Follower extra speed lost | .4-.6 / -.64 | .47-.77 / .03 | .02-.82 / -.97 | .11-.51 / -3.0 |
| Follower extra responders | .126-.186 / .12 | .115-.195 / .10 | .05-.21 / **.10** | .03-.15 / -.14 |
| Lag under 1 m at body over | .20-.48 / .04 | 0-.08 / **.01** | .14-.32 / .01 | 0-.01 / **0** |
| **In band** | **5 of 16** | **6 of 16** | **5 of 16** | **9 of 15** |
| Contacts | 0 | 0 | 0 | 0 |
| Share of steps on the guard, limit 1% | .7% | 1.6% | .9% | 8.9% |

I-395 and A39 were run once, on this build, with nothing tuned after. I-90 and I-294, also held out in report 18's spec, have no scene here and were not tested. Row 16's bands differ from report 18's table (4.7%, under 2%, 10.7%, 0.2%): its own pipeline gives 101 of 297 at I-80, 34%, so both sides now use the pipeline.

**The largest miss is throughput.** Past the end of the lane at I-80, real traffic carries 1,344 and 1,435 veh/h in the two runs. The scene carries 858 at the measured demand, about 60%. So a queue fills the scene and most cars stop first, whatever the merge rules say. The scene and the rows cannot be compared fairly until this closes. Report 05's T of 1.3 s gives about 1,350 veh/h at 6 m/s before any merge, so part of this is the following law at low speed, as noted under capacity above.

**Rules off, I-80, one seed.** No rule moves the table by much while the queue dominates. Edging and the start law move the rows they should. `tte` and `follow` off score one row more than everything on, so on this evidence neither has earned its place at this site. They stay on because report 18 measured them; this table does not confirm them.

| Case | Body | Stopped | Overlap start | Alongside 5 s | Overlap last 5 s | Excess accel | Speed lost | Responders | Rows in band |
|---|---|---|---|---|---|---|---|---|---|
| All on | 14.2 | .89 | .09 | .83 | .29 | .06 | -.64 | .12 | 5 |
| `tte` off | 17.0 | .88 | .08 | .83 | .29 | .05 | -.69 | .13 | 6 |
| `start` off | 6.0 | .84 | 0 | .77 | .39 | -.17 | -.60 | .08 | 5 |
| `edge` off | 11.6 | .88 | 0 | .81 | .23 | .09 | -1.28 | -.01 | 3 |
| `follow` off | 12.6 | .91 | .08 | .83 | .26 | .11 | -.56 | .14 | 6 |
| `match` off | 19.9 | .89 | .04 | .79 | .18 | .13 | -.29 | .12 | 4 |
| `steer` off | 13.3 | .87 | .08 | .82 | .29 | -.07 | -.72 | .10 | 5 |

**Sensitivity of the invented numbers, I-80, one seed.** `b_end` 1.5, 4 and `w_s_near` .25, .7 leave 5 rows in band. `s_driver` 0 gives 4, 1 gives 7, with overlap at start .07 and .16. `q_edge` .07 and .25 give 4 each, with overlap at start .05 and .19. A wider driver term helps most, and it has no source, so it stays at 0.5.

**What changed after the first training runs, none of it on held-out data.**

- The start law read today's gaps, but it was fitted on the body reaching the line. It now reads them τ s on.
- Report 18's going-back rule was true whenever a car was level alongside, and cancelled nearly every edge. It is gone.
- Followers answered only at 10% of a lane, which a third of drivers never reach. They now also answer a driver that has edged as far as it goes. Invented, in `HUMAN.md`.
- Scenes had a target lane at 520 veh/h, 40 m apart, with nobody to be alongside. They now use the measured flow of both lanes at each site.
- Sweeping the start law's intercept from -1.23 to 1.2 trades merge position against stops with no better total. It stays as fitted.

**The audit.** Fixes that touch this driver, with what they measure now:

| Fix | Measured | Target | |
|---|---|---|---|
| 1. Corner speed √(a_y R), road arcs, a_y median | 2.9 at R 10, 2.2 at R 20, 2.2 at R 50 m/s² | 2.2 | R 10 is over: a 30 m chord overstates that radius |
| 1. Same, p95 | 4.7, 3.7, 3.6 | real 3.1 | Over. The cap of 4.3 acts on the driver draw, not on a car's actual speed |
| 5. Softer stops | `gipps_b` 3.0, `gipps_tau` .5 | 3.0, .7 | .7 costs 9% on A39 replay, so .5 |
| 7. Launch by class | `hu_amax` capped by class | | Not separately measured |
| 10. Launch | Below 2 m/s, not 5. Queue headway 2.35 s at dt .1 | sat 1.8-2.2 | Miss. 5 m/s takes I-90 moving out of band for 2.30 s |
| 12. Swedish free speed | Table in, `--region sweden` | within .03 | Not measured on a free road |
| 13. Lateral cap | 1.3 m/s in the kernel. Real peak not measured on simulated tracks | under 1.3 | Not confirmed by measurement |
| Yellow, dt .5 | Stops 1.5%, 0%, 41%, 75%, 100% at 0-3, 3-4, 4-5, 5-6, 6-8 s; half at 4.81 s, scale .45; brake p95 3.2 | 5.1, .54; 35% at 4-5, 75% at 5-6 | Holds |
| Yellow, dt 1 | Stops 0%, 15%, 29%, 100%, 100%; half at 4.49 s, scale .29; brake p95 3.5 | same | 3-4 s over 5% on n=13, and it drifts |

**Removing the corner floor costs capacity, as expected.** The floor was unphysical, and it was also what held these numbers on target, on netconvert's tight corners. Inside-corner speed is now 3.7 m/s right and 4.5 left, where the audit's real turns (radius p50 29.6 m) give about 8.

| With `--region sweden`, dt .5 | With 8 m/s floor | Now | Target |
|---|---|---|---|
| Right turn, veh per green hour | 1,449 | 1,097 | 1,700 |
| Left turn | 1,569 | 1,209 | 1,700 |
| Through | | 1,770 | 1,900 |
| Roundabout critical gap, s | 2.95 | 5.36 | 2.95 |
| Roundabout follow-up, s | 3.0 | 5.0 | 3.0 |

The audit's fixes 2 and 3, rebuilding junction geometry and smoothing roads, belong to the physics agent and should bring these back. Until then these are misses. `path_radius` is used only by this driver; Krauss's `driver_lateral` is untouched.

**Replay, frozen build, dt .1.** I-395 5.69 / .63, I-90 run 6 4.18 / .59, I-90 moving 4.09 / .64, I-294 10.79 / 1.45, A39 11.70 / 1.08. All in band. p5 of time gaps 1.12 s against an upper band of 1.10, a small miss.

**Small scenes.** A follower catching a slow leader keeps at least 6.68 m at dt .1, .5 and 1, hardest braking 2.96 m/s². All five deadlock scenes arrive in full with no contacts, though 1 of 2 and 2 of 3 cars in two of them give up their route to do so. `stub_lane` at dt 1: 140 of 140 arrive on 1, 3, 5, 8 m stubs with 0, 1, 2, 2 contacts: three at the lane start, one on the same lane. On a 22 m stub 114 of 140 arrive within 1,200 s, 7 lost, none stuck; before the merge rules it was 140.

**Physics QA, I-80 and motorway traces.** No negative gaps and no junction overlaps. Hardest braking -8.3 and -6.0 m/s², p1 -1.1 and -2.4; 26 and 21 samples harder than the vehicle's type allows. No lateral samples over comfort at I-80, 46 on the motorway scene, none over 4 m/s². 13 over speed by 30% on the motorway scene. The lane-change rows in QA read the label jump of a whole lane, not motion.

**A fault in the software GPU, not in the driver.** llvmpipe's default 256-bit vectors silently mix up vehicles in the plan kernel. A car with another in the same dispatch brakes to a stop at the end of its final road and stands there: `stub_lane` arrived 3 of 103. Debug output showed an item with no link and a request flag, which no code path writes. At 128 bits the same binary arrives 140 of 140. An earlier result in this work, followers driving through leaders with a min gap of -91 m, is very likely the same fault, but that is unproven: the rule that seemed to cause it was moved to the plan kernel first, and its old place was not retested at 128 bits. A follower catching a slow leader now passes at 128 bits and is a regression test. `cars` now sets the width itself for llvmpipe. **All merge measurements made before this was found are discarded.** Earlier software GPU numbers in this report were made on older kernels at 256 bits and were not all rerun; the city runs are on the real GPU.

**How it looks.** By eye, frame by frame: queues stand on brake lights, blinkers flash front and rear on the side the car is merging towards, a head car noses in as room opens, and nobody overlaps. Three things look wrong to a driver. The sim is more crowded than the real panel, 11 km/h against 24, from the throughput miss. Cars mostly wait and then go, rather than rolling in beside someone. And a car starting from a crawl turns about 20° by eye, more than the real tracks show, because the sideways rate is capped but not tied to its speed at the start of a change. The real panel has no blinkers because the data has none. The two panels show different moments on the same road and scale.

## Clips, scene geometry, and a correction

**Correction to the numbers since the first merge of main.** The human model's id moved from 4 to 5 when the AV model took 4, and one line in `world.rs` still wrote 4. So every scene run between that merge and `b00788c` drove as the AV model. Rounds r0 to r3, including a throughput "pass" of 1,316 and 1,536 veh/h reported in passing, are void. The frozen `86f2256` tables above are from before that merge and are not affected. The clue was guard use of exactly zero and cars at exactly constant speed.

**What Erik saw.** Real cars jumped across the merge section in about a frame. `scripts/real_tracks_trace.py` put real positions on `up_0`, `merge_1` and `down_0`, whose ends are about 10 m apart in the drawn scene because netconvert puts a junction box between them, with nothing mapped to the box. Some cars also turned oddly at the taper, because the sideways scale changed when a car's lane label changed.

**The fix.**

- Scenes have no junction box. `human_merge.py` writes the geometry itself: lanes abut, length equals what is drawn, the ending lane runs out into a taper of max(40 m, 3 s at the limit), and the ramp runs alongside its last 200 m. netconvert had also made the 54 m I-80 zone 66.5 m long, with a `length` that disagreed with the shape. That is gone too.
- Real tracks are in one road coordinate and one sideways coordinate, so there is no lane to jump between. Position gets a 1 s running mean, as NGSIM positions shake (up to 5.3 m in a frame). An id that returns later in a run is a new car.
- `cars replay` takes sideways speed from where the car went, low-passed over 0.5 s. It used the lane offset, which jumps by a lane at a lane change with no motion. **So every earlier simulated clip had a one-frame heading flicker of up to 20° at each lane change.**
- The test found a driver bug: edging kept running after a change started, pulling the edge back to zero, so a car moved away from its target for a moment. Fixed in `hu_edge`.

**The test.** `cars replay --poses` writes what would be drawn, with no GPU, from the renderer's own pose code. `physics_qa.py` compares each car's move between frames with its speed × time and fails on a jump, on any `--trace`. `human_merge_clips.py` refuses to publish a clip that fails.

| Clip | Moves checked | Jumps | Worst excess | Fast rotations | Worst turn |
|---|---|---|---|---|---|
| Real I-80, before the fixes | | about 10 m in a frame | | | |
| Real I-80 | 15,509 | 0 | 0.23 m | 0 | 24°/s |
| Simulated I-80 and lane-end close-up | 199,494 | 0 | 0.27 m | 0 | 48°/s |
| Simulated two into one | 97,065 | 0 | 0.22 m | 0 | 41°/s |

**Does the geometry change results? Yes, by a modest amount, as expected.** Same driver, one seed:

| | I-80 box | I-80 road | US-101 box | US-101 road |
|---|---|---|---|---|
| Rows in band | 6 of 17 | 8 of 17 | 6 of 17 | 7 of 17 |
| Flow past the end, veh/h | 1,164 | 1,080 | 1,256 | 1,216 |
| Stopped first | .68 | .85 | .46 | .48 |
| Overlap at sideways start | .18 | .18 | .09 | .14 |
| Overlapped in last 5 s | .36 | .43 | .27 | .29 |

I-80's zone went from 66.5 m to the site's 54 m, which accounts for the lower flow and more stops. Those rows were flattered by the longer lane.

**Report 18's measurements are not affected.** Its real-side pipeline (`mg_cache.py`, `mg_events.py`, `mg_analyse.py`, `mg_follow.py`) reads raw NGSIM and TGSIM positions and never reads a scene net or this mapping, which was written after the report. The simulated side of this report's own table did use the scene: the frozen table above was measured on the 66.5 m I-80 zone with box internal lanes, and its flows were also over-demand. Its tables are valid as run but not for comparing with later rounds.

**The real GPU.** The frozen build gives 364 of 489 arrived on the I-80 scene, against 361 of 484 at 128 bits on the software GPU, no contacts in either, and 140 of 140 on the stub scene. The fault is in llvmpipe's 256-bit code alone. The t≈1,190 s spin no longer appears: the scene runs to 1,800 s with the human driver on main's base.

**I-395 and A39 are used up as held-out sites for this rule set**, having been opened once for the frozen table. A final claim needs fresh sites, from `data-hunt/25-junction-targets.md`.

## Rounds after that

The rounds below are on the merged physics base, human driver on, one seed, exact scene geometry. Real bands as in the table above. I-395 and A39 were not opened. Scope was two rounds on throughput and stopped-first, then stop.

**Why flow was low, in two parts.**

One lane with no merge, past a queue: 1,109 veh/h at a 9 m/s limit, 1,598 at 30 m/s, against a real 1,800-2,300 on motorways. This is the corner finding of the physics agent, 1,389 per green hour at 8.8 m/s, with its cause. T and s0 ask for about 42 m at 25 m/s, cars hold about 54. Report 05's k1 is so small that a car 5 m back accelerates at 0.055 m/s², and voids from a queue barely close. Raising k1 to 0.03 gave +6-8% and cost 9% on A39 replay, so it was dropped. Shortening T costs nothing on replay, because replay hardly pins it.

| T scale | Sat headway, s | One lane at 9 m/s | At 30 m/s | A39 replay, m | I-294 replay, m | p5 time gap, s |
|---|---|---|---|---|---|---|
| 1.0 | 2.35 | 1,109 | 1,598 | 11.89 | 11.65 | 1.12 |
| 0.85 | 2.28 | 1,138 | 1,714 | 11.61 | 11.37 | 1.11 |
| 0.7 | 2.22 | 1,152 | 1,850 | 11.62 | 11.22 | 1.08 |

At 9 m/s the slowest driver sets the lane, 7.4 m/s. The scene's limit was the mean of real speed past the end, so it was wrong: it is now the p90, 12 and 17 m/s.

The second part is a loop at the lane end, seen in `cars why` at US-101. Ramp-lane cars do 4-5 m/s where real ones do 14. 95% of their ticks they have not decided to start, as time to the end is distance over speed and at 4 m/s it reads 50 s. So they roll to the end and stop, which queues and slows those behind, which delays their start in turn. Report 18's law was fitted on the body reaching the line and it asks for the intercept to be tuned in closed loop.

| Round | Change | I-80 flow | Stopped | Rows | US-101 flow | Stopped | Rows |
|---|---|---|---|---|---|---|---|
| Base | Exact road, flows past the end | 1,080 | .85 | 8 of 17 | 1,216 | .48 | 7 of 17 |
| r10 | Scene limit at p90 of real speed | 1,152 | .72 | 4 | 1,236 | .49 | 6 |
| 1 | + T × 0.7 | 1,180 | .69 | 5 | 1,232 | .47 | 7 |
| | + S0 −0.4 | 1,176 | .66 | 6 | 1,328 | .37 | 7 |
| 2 | + S0 0.4 | **1,252** | **.49** | 4 | **1,468** | **.21** | **8** |
| Real | | 1,344-1,435 | .18-.34 | | about 1,539 | 0-.02 | |

Kept: T × 0.7, S0 0.4, scene limits. What it did not fix: I-80 still 7% short of the low end of real flow and stops at .49 against at most .34. Starting earlier also lowers overlap at the start there, .16 to .10 against a real .24-.40, and moves the body over the line to 32 m left against at most 17. So at I-80 the rows count fell from 5 to 4 while the two rows this round was for improved. That is a trade, not a clean gain.

**Stopped there, per the two-round rule.** Not done from the earlier list: the 20° turn from a crawl (real heading at 1-4 m/s has p95 5-8°, simulated 11-15°, from the 45° steering allowance `lc_slope`, whose lower values made wrong-lane waits rise several-fold at signals), and rerunning the give-way gap test behind the 72 times more teleports (run4 lost). Report 18's follower rows also still fail.

A one-token change inside `hu_target` (`0.85 *` in the gap term) made cars run off the end of their lane on llvmpipe at 128 bits, with `t_scale` giving the same effect cleanly. Kernel edits there need a sanity run; real-GPU confirmation of that edit is outstanding as the lock was busy.

**After the first benchmark of those rounds** (`e86a856`, 32 fails against 31 for the old human driver and 32 for main's physical driver), three more changes aimed at its regressions: launch needs the gap opened by 1 m (`JS5`: start wave 42 km/h, real 16-28), s0 scale 1.0 (`M4`, `JS2` turning), and `lc_safety` 0.35 (`JL1`: stopped in the source lane). With `lc_safety` at 0.35, US-101 reaches 1,532 veh/h with .065 stopped first and I-80 1,244 with .45, no contacts. Hard-braking requests go up, cert floor 11 to 32 at US-101.

## Capacity on the fixed test

`scripts/berlin2019/step3_capacity.py --flags=--humans --dt 1`, three seeds, on the merged base with Berlin's first gate. Measured earlier on this driver at f69d694 plus the merge rule: saturation 1,500, motorway 1,503 per lane.

| | Before | `9f75006` | Band |
|---|---|---|---|
| Saturation at 50 km/h, veh/h | 1,500 | **1,800** | 1,800-2,100 |
| Saturation at 30 km/h | | 1,612 | |
| Jam spacing, m | | 6.95, 7.53 | 6.5-8.2 |
| Start wave at 50 km/h, km/h | | 21.8 | 16-28 |
| Motorway, lane drop at 100 km/h, veh/h per lane | 1,503 | **1,220** | 1,800-2,300 |
| Give-way minor road at 400, 800, 1,200 veh/h major | | 472, 224, 70 | Siegloch 736, 451, 277 |

**Saturation is at the band's lower edge.** T had no effect at dt 1 (T × 0.6 stayed at 2.05 s). With the small gap gain, spacing is set by the acceleration phase: at k2 about 0.5 a follower pulling at 1.5 m/s² must stay about 3 m/s under its leader the whole way up, so its gap keeps opening for about 7 s. The launch rule at 7 m/s fixes that. 5 m/s gives 1,756, 10 m/s 1,946 but I-90 moving replay at 4.54 m against 4.20. At 7 m/s it is 4.30, 2% over, everything else in band.

**Motorway missed, and is below the earlier number: two rounds with no gain, stopped.** The test's up_0 ends and up_1 goes on, so it is a lane change. Downstream is free. All pairs at the exit, main to main too, have mean headway about 2.6 s at 11 m/s, where equilibrium is about 1.6 s, and 71% of target-lane cars stop in the last 200 m. Tried, one at a time, one seed:

| Change | Motorway veh/h per lane |
|---|---|
| Base | 1,221 |
| `follow` off (falls back on the old courtesy) | 1,224 |
| `match` off | 1,377 |
| `anticipate` off | 1,413 |
| `start` off | 1,401 |
| `edge` off, which also stops followers yielding at all | 1,467 |
| `edge` and `tte` off, launch to 10 m/s | 1,572 |
| `w_f` 0, launch to 10 m/s | 1,461 |
| `w_f` 0.3, launch to 10 m/s | 1,269 |
| k1 0.03, 0.08, 0.2 | 1,188, 1,224, 1,203 |
| `lc_safety` 0.6, 0.15 | 1,176, 1,245 |
| T × 0.55 with `edge`, `match`, `anticipate` off | 1,422 |
| Urgency from 15 or 8 s | 1,194 |

So followers yielding costs most, and even removing it stays well under the band. One lane on its own carries 1,850 at T × 0.7. Physical is at 1,767 on the benchmark's version. The cause of the remaining gap is not found. The queue's stop-and-go (`M13` swing 7.5 against a floor of 2.5) is the best lead. A real driver asked to yield near a lane end doesn't brake for a merger alongside, so that was taken out as correct in itself: it took 1,025 to 1,212 on one seed.

**Benchmark, fast, `9f75006`:** 33 fail, 14 at floor. Old human driver (f69d694) 31 and 16, main's physical 32 and 13.

| | Better than physical | Worse than physical |
|---|---|---|
| Status | `M6`, `M17`, `C4` to floor | `V5` (saturation at the two time steps), `M4`, `M13`, `JR5` |
| z | `M3` 14.1 to 5.6, `JS1` 7.0 to 4.4, `JZ1` 5.4 to 2.5, `JL2` 4.7 to 3.2, `M10` 8.2 to 6.3 | `C3` 1.5 to 2.7, `JL1` 6.1 to 31.8 (stopped in the source lane .79 against a real under .04) |

`V2` overlaps: 3 engine incidents in the four-way junction scene over 9,622 veh-km, 0 and 2 in the two runs before, 5 on main's physical. Against the old human driver, also worse: `JR2`, `JR4` (the corner floor, removed as asked), `JS5` (start wave 35.5 km/h on the benchmark's scene, 21.8 on the fixed test). `M8`: lane changes 0.84 per veh-km against a real 0.22-0.30, physical 0.11: the next item.

**Merging does not change main's default driver.** Trips from main's physical driver are byte for byte the same on this branch on six scenes: road, signal, four-way, lane drop, give-way, curves. Golden: ALL OK.
