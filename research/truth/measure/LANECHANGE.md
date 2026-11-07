# Lane changes, measured

7 November 2026. Written after the measurements (F700-F708) and before any scene or replay test of the code. Numbers are in [lc_decision.json](lc_decision.json); scripts are `scripts/measure/lc_decision.py` (states and fits) and `scripts/replay/lc_merge.py` (harness). Held out, unread: exiD location 5 and highD location 6 ([HOLDOUT.md](HOLDOUT.md)). Applies to the one driver (physical motion, `hd_phys`), **off by default**: `--tune lc_measured=1` turns it on. Three T0 rows that pass with the old rules fail with it (Results). Without the switch a run is the old code's. The human driver and `--sumo-compat` are unchanged.

## What the recordings can and cannot say

- **The event is the start of the sideways motion.** That is the last frame before the centre crosses where the car has done under 10% of its lateral move. The simulator commits a change at that moment: the label moves and followers react.
  - exiD on-ramps are measured against the marking the acceleration lane shares with the main road, from the acceleration lane's own centre. A plateau measured 6 s back lies on the ramp, which converges on the marking.
- **Free-flow recordings do not identify gap acceptance.**
  - exiD mergers start almost as soon as they reach the acceleration lane: time to its end is 8.7 s median at the start against 9.5 s over all their seconds there.
  - Offered gaps are rarely tight, so refusals hardly exist.
  - A joint fit of start law and lognormal critical gaps on 2,445 exiD starts (5 sites, 7,140 car-seconds) is degenerate: both critical medians go to about 0, with intervals over orders of magnitude.
  - 8% of starts have a car still alongside behind and 7% one alongside ahead. Drivers start before the gap exists, as report 18 found.
  - F700-F703 cannot be answered on exiD.
- **Congested merging is absent from exiD and highD.** 47 of 4,482 exiD merges and 147 of 12,234 highD changes happen under 15 m/s. Lane-end share and alternation therefore come from I-80 (report 14), the one non-held-out recording with them.
- **Where refusals exist:** the must-change cohorts of report 14. On I-80 (610 cars, 22.6 s median wait) and US-101 (349 cars), every 0.5 s beside the target lane is a gap taken or refused. The joint likelihood is fitted there.
- **The A39 check (DLR HT, 2,000 ramp cars, not used in the fit):**
  - crossing hazard per 0.5 s 0.048 predicted against 0.045 observed;
  - accepted lag p5 0.92 against 0.76 s, lead p5 1.20 against 1.04 s;
  - medians too long (lag p50 6.2 against 3.2 s), because A39 drivers take the first gap.
  - This check was run after the fit and without a forecast, so it is information, not a pass.

## The decision law

**1. Must-change start** (a lane that ends, or the lane a route needs, once LC2013's strategic urgency is on):

`per 0.5 s: P(start) = sigmoid(A0 + AT * tte / 10) * P(lag accepted) * P(lead accepted)`

- `tte` is the time to the end of the lane: metres left over own speed, floored at 1 m/s, capped at 60 s.
- `AT` = −1.119 per 10 s (95% CI −1.33 to −0.94), fitted with `a0` = −0.825 on I-80 and US-101 (959 cars) at the crossing.
- The intercept is moved to the start by the measured 2.0 s from start to crossing: `A0 = a0 − AT · 0.2 = −0.601`. Nothing is tuned.
- It replaces report 18's B2: its intercept 0.4 was tuned in closed loop and its driver term 0.5 was invented. Both are gone.
- The gap terms (0.133, 0.164 per s) are replaced by the acceptance below.

**2. Gap acceptance, every change** (must-change and discretionary): lognormal critical time gaps, drawn afresh every 0.5 s as the fit assumes.

| | ln median | per m/s of closing speed | log-SD | median at no closing |
|---|---:|---:|---:|---:|
| Lag (bumper gap over the follower's speed) | −0.908 (−1.49 to 0.16) | +0.551 (0.34 to 0.81) | 1.68 (1.09 to 2.82) | 0.40 s |
| Lead (bumper gap over own speed) | −2.004 (−2.43 to 2.53) | +0.453 (0.33 to 0.90) | 1.37 (0.90 to 6.1) | 0.14 s |

- A body alongside (lag or lead ≤ 0) refuses.
- Closing speed is well determined. A follower 3 m/s faster raises the median critical lag fivefold, to 2.1 s.
- The medians are weakly determined, and the two sites disagree: I-80 alone gives a 0.15 s lag median, US-101 0.56 s. I-80 has no lane line, so its "crossing" is a place, not a decision (report 18).
- This replaces three earlier rules:
  - the fitted floor of certificate × 0.35;
  - the published critical gaps of Lee and Ahmed for the lead;
  - for a discretionary change behind a physical follower, the follower's own desired gap × 0.6 (Vissim).

**3. Discretionary desire stays LC2013's** (speed gain, keep right). A per-second hazard was fitted on highD and DLR HT (`lc_decision.json`, `highD`, `dlrht`). It is not ported in this round, because no scene or harness test yet shows a gap in LC2013's desire; LC6 is the candidate (below).

## The follower

- **Before the start, the measured follower barely acts.** On exiD (1,044 merges, F707):
  - 11.9% (9.9 to 13.9) of new followers slow 0.3 m/s² or more beyond speed-matched followers with no merger, in the 3 s before the start;
  - against a 6.4% baseline;
  - an excess of 5.5 points.
  - Report 14 on I-80: +5.8 to +8.3 points, by speed 6-6.5 points at 2-15 m/s, about 0 above 25 m/s.
- **Courtesy share stays at the provisional 0.4** (report 14's I-80 sweep). F707 is not this share.
  - The simulator's share applies only when a blocked must-changer is alongside. F707 counts braking per merge, mostly in free flow where nobody is blocked.
  - Set to 0.055, lane-end waits were three times I-80's: LC8 p99 187 s against 72.7, median 68 against 22.6.
  - At 0.4: 76.5 s and 24 s.
  - The share of chances in which a blocked merger is let in is the measurement that would set it. Report 14 has it for I-80 (59%), but not yet in the simulator's terms.
- **Rules dropped for a measured follower or leader**, because no recording shows them:
  - SUMO's "keep a secure gap behind the merger's planned speed" for followers of a blocked changer (MSLCHelper::getSpeedPreservingSecureGap);
  - the request that the target lane's leader hold its speed while a changer overtakes it;
  - the follower help for an urgent speed-gain changer.
- **After the start the follower follows the merger** with the full car-following law. Report 18 measures a share of 0.39-0.68 of the asked braking. A share inside car following belongs to the car-following law, which is not this job's, so this is left open.

## Lateral motion

Measured from the start (10%):

| | exiD merges, 20-25 m/s (1,480) | highD, 25-30 m/s (1,124) | DLR HT, 25-30 m/s (6,178) |
|---|---|---|---|
| Start to body on the marking | 0.80 s | 0.84 s | 1.6 s |
| Start to centre over the marking | 1.96 s | 1.96 s | 2.8 s |
| Body straddling the marking | 2.40 s | 2.32 s | 2.8 s |
| Start to body clear of the old lane | 3.24 s | 3.20 s | 4.2 s |
| 10% to 90% | 4.68 s | 4.40 s | 5.8 s |

- **The physical change is near-constant sideways speed with 1 s ends.** Both drone sets give 0.71 m/s:
  - from the 1.4 m between 10% of the lane and the marking, covered in 1.96 s;
  - from the 2.3 m to a clear body, covered in 3.2-3.3 s.
- **The value was 0.6.** The simulator's shadow (both lanes occupied) now ends 4.2 s after the commit at 3.5 m lanes, against 4.9 s before.
- **DLR HT's slower 0.47-0.52** is a 5 Hz road-frame reconstruction against 25 Hz drone boxes. It is not used, and it is left as a disagreement.
- **A change runs on over a plain link** (no junction box, no foes, no signal).
  - Before, the one driver had to finish a change before its lane's end, or not start it.
  - On a lane cut into short sections, as on exiD's merged lanelets, every merger at speed was refused for room and stopped at the end of the acceleration lane: harness baseline, 98% in the last tenth at 0 m/s.
  - Across a junction box it still finishes first.

## Fitted numbers and their sources

| Number | Value | Source | Status |
|---|---|---|---|
| Start law a0, AT | −0.825, −1.119 per 10 s | I-80 + US-101 must-change cohorts (report 14 tables), joint likelihood | Measured; a0 moved by the measured 2.0 s |
| Critical lag: ln median, closing slope, log-SD | −0.908, 0.551, 1.676 | same fit | Measured; median weakly determined |
| Critical lead: same | −2.004, 0.453, 1.374 | same fit | Measured; median weakly determined |
| Courtesy share | 0.4 | report 14, I-80 sweep for the human driver | Provisional: F707 (5.5 points per merge on exiD) is a different quantity |
| Sideways speed | 0.71 m/s | exiD merges, highD | Measured |
| Start to crossing used for the shift | 2.0 s | exiD, highD | Measured |
| Strategic urgency window (LC2013 lookahead, report 18 B1's 43 s) | unchanged | LMRS | Established, not re-measured |
| Discretionary desire | LC2013 | SUMO | Not measured here; fit available |

All were frozen in `world.rs` before the first test run. Two changes were made after it, each with its forecast written first:
- F727 held the closing-speed terms at the p95 of their data. It gave no gain and was reverted.
- F728 put courtesy back at 0.4 after the 0.055 of round 1.

## Results (F720-F728)

**Harness, exiD 00, setting 1** (121 on-ramp mergers released where they enter the acceleration lane, everyone else replayed; dt 0.25, 2 seeds; `lc_merge.py`). Old rules against measured rules, with the same cars in the recording:

| | Recorded | Old rules | Measured rules |
|---|---:|---:|---:|
| Metres left at the crossing, median | 123 | 2.3 | 110 |
| Share in the last tenth of the lane | 0.075 | 0.98 | 0.21 |
| Entering the lane to crossing, median | 4.5 s | 23.3 s | 5.5 s |
| Speed at the crossing, median | 22.8 m/s | 0 | 22.1 m/s |
| Lag time gap at the crossing, p5 / p50 | 0.47 / 0.72 s (n 13) | | 0.24 / 0.91 s |
| Lead time gap at the crossing, p5 / p50 | 0.38 / 0.97 s (n 27) | | −0.12 / 1.50 s |
| Overlaps with replayed cars per merger-run | | 6.4 | 1.2 |

- **Paired by car:** the median crossing is 0.75 s later than recorded and 10 m earlier on the lane.
- **The late tail is a transfer limit.** A start law fitted on exiD alone, with the acceptance held, starts 2.3 times as often at 10 s to the end. But exiD's slope is undetermined (by site −5.4 to +8.9).
- **The negative lead p5** comes from mergers that commit near the end and finish their move past the lane's end, beside the recorded leader.
- **Setting 2** (the ramp and the rightmost lane simulated):
  - measured rules 119 m left (recorded 111), 14% in the last tenth (7%), 5.5 s (4.5);
  - old rules 9.6 m, 69%, 23.8 s.
  - Both arms show tens of thousands of contacts, from released main-lane cars meeting replayed cars that change into their lane. That is a harness artefact of this setting, so follower braking is not scored from it.

**T0 lane-change rows, dt 0.25, physical driver** (`results/theory/physical_0.25_final.csv`, against `physical_0.25.csv`):

| Row | Old rules | Measured rules (final) |
|---|---|---|
| LC1 F021 wait / F263 passes | 9.6 s pass / 0.075 pass | 3.7 s pass / 0.077 pass |
| LC2 F022 on the move, 100 / 300 m | 0.98 / 0.96 pass | 0.58 / 0.93 pass |
| LC3 F023 stopped head (floor 724) | 969 pass | 554 **fail** |
| LC3 F024 share both saturated | 0.715 fail | **0.503 pass** |
| LC8 F028 wait p99 / max (I-80 72.7 / 79) | 36 / 44 pass | 61 / 64 pass |
| LC4 F025 capacity with changes (0.91) | 0.99 fail | 0.74 fail |
| LC5 F026 void dv 5 / F264 ratio / F403 dv 5 / F403 dv 10 | fail / pass / pass / fail | fail / **fail** / **fail** / fail |
| LC6 F027 drop at 100 km/h (5-15%) | 21.9 fail | 17.0 fail (seeds −31 to 42) |
| C-S6 F036 total / share / longest wait | 1,377 fail / 0.708 fail / 50 s pass | 1,130 fail / **0.482 pass** / 79 s pass |
| LC7, C-S3, C-S4, C-S4b, C-S5 | pass | pass |
| Contacts lc / lc2 / drop / drop_city | 1 / 7 / 2 / 1 | 0 / 1 / 1 / 1 |

- **Two fixed:** the merge shares, which round 1 had fixed already.
- **Three regressed:** LC3 F023, LC5 F264 and LC5 F403 dv 5.
- **Why LC3 F023 fails:** its floor assumes a deterministic tc of 4 s. The code's own acceptance is lognormal with a log-SD of 1.68, and its capacity was not recomputed before the run.
- **Why LC4, LC5 and the C-S6 total fail:** the measured acceptance has a low tail, and a follower behind a short accepted lag brakes with its full car-following response. Real followers apply 0.39-0.68 of it (report 18 B7). That response sits in the car-following law, which is not this job's.
- **Why the measured rules stay off by default:** these regressions.

**What was tried on the lane-end waits, and stopped (rule 9):**
- Round 1: the closing-speed term extrapolated to 98 s lags for a head standing beside a 10 m/s stream. Capping it at the data's p95 (F727) changed nothing and raised contacts 15-fold. Reverted.
- Round 2: the waits came from the courtesy share (F728), not from acceptance.

## Open

- **Follower response after the commit:** a share of the asked braking (report 18 B7, w 0.39-0.68), so that measured short lags do not cost capacity. This belongs in the car-following law.
- **A start law that carries from congested to free-flow merging.** Time to the end alone does not; ramp-to-main speed difference is the candidate (report 18 C).
- **The courtesy share in the simulator's own terms:** let-in per chance in an I-80-shaped scene, against 59% (report 14).
- **Discretionary desire:** the highD/DLR HT hazard (`lc_decision.json`) is ready to replace LC2013's speed gain once a scene or replay shows the gap. LC6's cut-ins in the queue are the candidate.
- **Held-out sites (exiD location 5, highD location 6) were not opened:** step 4 does not pass.
