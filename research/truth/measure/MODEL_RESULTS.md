# The measured driver: fit, held-out tests and T0

7 November 2026. Model: [MODEL.md](MODEL.md). Forecasts F300-F329 in `foundations/forecasts.csv`, each written and committed before its run. Branch `t3/e08c6418`.

## Fit (recordings not held out)

| | Forecast | Result | Verdict |
|---|---|---|---|
| F300 K | 2.5-4.5 m/s | 2.69 (2.60-2.78); by table 0.9-4.2 | pass |
| F301 c_a | 0.4-1.1 | 0.51 (0.49-0.52) | pass |
| F302 k_g | 0.2-0.5 | 0.28 (0.23-0.32) | pass |
| F303 k_p | 0.005-0.05 | 0.025 (0.023-0.029) | pass |
| F304 next second against constant speed | lower on all five tables | about half the error on each | pass |
| F305 noise | σ 0.1-0.4, τ 1-6 s | median 0.97 m/s², 0.1 s; German tables 0.23-0.34 over 1.5-2 s, TGSIM white | miss |
| F306 launch | a0 1.9-2.3, r_1 0.6-1.2 s | 2.025 (the table's own), 0.78 s | pass |
| F307 kernel against its twin | under 0.02 m/s | 0.0047 m/s RMS | pass |
| F308 30 s, I-294 L1, against the one driver | lower | 17.6-19.3 m against 13.6 | miss: desired speed draw, then the cap below |
| F309 next second, I-294 L1 | under null and one driver | 0.236 against 0.400 and 0.783 | pass |
| F310 slow terms on 30 s rollouts | | k_p 0.15, T_v 1 s | not adopted: k_p contradicts DRIVER.md's band |
| F311 launch law only without a leader within 100 m | 30 s at most 8.5 m | 8.42 m; refit inside every band | pass |

One structural change came out of the fit, before any held-out recording was read: the vehicle's launch law (a0 − a1 v, floor 0.7 m/s²) held every following command at speed. It now holds only a car with no leader within 100 m (F310, F311). Desired speeds in the one-follower tests are the measured spread cut below at each follower's release speed, for both drivers: a follower that kept up with its leader was not one of the slow drivers.

## Held-out tests

| Recording | Test | Measured driver | One driver | Real floor | Verdict |
|---|---|---|---|---|---|
| TGSIM I-90/94 moving | 30 s spacing (F323) | 7.33 m (7.21-7.44) | 5.80 | 5.67 | **fail** (bound 6.17) |
| | 10 s / 5 s spacing | 3.22 / 1.48 m | 3.56 / 2.06 | | |
| | next-second CRPS (F324) | **0.211** (0.201-0.222) | 0.648 | 0.174 | **pass** (null 0.368) |
| | classifier (F325) | 0.827 (0.822-0.833) | 0.865 | 0.64-0.68 | **fail** (bound 0.70) |
| DLR HT 14-16 UTC | 30 s spacing (F326) | 20.06 m (19.73-20.48) | 17.10 | 14.76 | **fail** (bound 16.24) |
| | 10 s / 5 s spacing | 5.91 / 2.21 m | 7.76 / 3.72 | | |
| | next-second CRPS (F327) | **0.234** (0.227-0.241) | 0.871 | 0.174 | **pass** (null 0.343) |
| highD location 6 | 10 s spacing (F328) | **4.33 m** (4.17-4.38) | 7.95 | 6.00 | **pass** |
| | next-second CRPS (F329) | **0.156** (0.149-0.163) | 0.895 | 0.132 | **pass** (null 0.257) |

5 seeds for spacing, 10 for CRPS; intervals are over seeds, or block bootstraps where marked in the JSON files (`replay/f101*.json`, `f109_*`, `f110_*`, `classifier.json`).

What this says:

- **The response is now human.** On all three held-out recordings the next second beats constant speed by a third or more, and sits 0.02-0.06 m/s over the real floor; the one driver is two to three times worse than constant speed. Up to 10 s the measured driver follows its leader better than the one driver everywhere (by 10-45%).
- **Over 30 s it drifts.** Its personal spreads and its weak pull let a gap that opens stay open (bias +8 to +20 m at speed, F308); the one driver, which steers to its gap, drifts less. On highD's 10 s windows that has no time to show.
- **The classifier still sees it**, now by jerk: the frozen command noise is near-white (0.97 m/s², 0.1 s), taken from the TGSIM tables, where German drone tables give 0.2-0.3 m/s² over 1.5-2 s. The distance to real fell (MMD 0.011 against 0.038).
- Not done: SinD Xi'an launch (no approach built); a classifier floor for DLR HT and highD pairings.

## T0 scenes at dt 0.25

91 pass, 95 fail of 186 (the one driver 124, 62, 1 error). Forecasts from the driver's own equations (F312-F321), emergent rows reported (F322):

| Row | Result |
|---|---|
| L1 capacity 50 / 100 km/h | 1,155 / 1,098 veh/h (real 1,640-1,900) |
| L4 start wave | 26.7 km/h |
| W1 | no coherent wave: the dip shrinks down the platoon (+2.6 m/s at car 30, as forecast) |

Most new fails have one cause, the same as the 30 s drift: **the law closes an open gap slowly** (k_p 0.025 m/s² per s; nothing measured at standstill). Placed queues do not compact (jam spacing 7.23 m), discharge is slow (S1 2.93 s), a ring stays far under its band (1,066 veh/h), followers through one gap hang back (G1 5.2 s), and N9's Hamburg links leave cars standing after the feed ends (F294: 440-1,000 cars), which needs its own look before anything else changes.

## What is left

1. **Closing up at low speed and from standstill is unmeasured.** DRIVER.md's band comes from following above 5 m/s. Queue creep and discharge gaps (rounD and inD queues, SinD, I-90/94 stationary under 5 m/s) are the recordings to measure it on, as a behaviour of its own, not as a fit to the scenes.
2. **The tension on k_p:** 30 s rollouts want 0.1 (F310); the one-second response and DRIVER.md's band say 0.025. A pull that grows with time spent too far, rather than with the error alone, would be one reading; it needs a measurement first.
3. **Noise:** German drone tables and TGSIM disagree (F305). The classifier's jerk cue says the white part is too much.
4. **N9 cars left standing** and the extra C-S0 locks: find the mechanism (`cars why`).
5. SinD Xi'an launch; classifier floors for DLR HT and highD.
