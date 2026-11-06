# Lane changes, measured

7 November 2026. Written after the measurements (F700-F708) and before any scene or replay test of the code. Numbers are in [lc_decision.json](lc_decision.json); scripts are `scripts/measure/lc_decision.py` (states and fits) and `scripts/replay/lc_merge.py` (harness). Held out, unread: exiD location 5 and highD location 6 ([HOLDOUT.md](HOLDOUT.md)). Applies to the one driver (physical motion, `hd_phys`); `--tune lc_measured=0` gives the old rules back. The human driver and `--sumo-compat` are unchanged.

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
- **Courtesy share 0.055.** It replaces the provisional 0.4. A follower drawn courteous brakes as before (report 14's yield, up to 1.5 m/s², more near the lane end).
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
| Courtesy share | 0.055 | exiD sites 0, 2, 3, 4, 6, F707 | Measured |
| Sideways speed | 0.71 m/s | exiD merges, highD | Measured |
| Start to crossing used for the shift | 2.0 s | exiD, highD | Measured |
| Strategic urgency window (LC2013 lookahead, report 18 B1's 43 s) | unchanged | LMRS | Established, not re-measured |
| Discretionary desire | LC2013 | SUMO | Not measured here; fit available |

All were frozen in `world.rs` before the first test run of this code.
