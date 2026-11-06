# The measured driver, round 2: gap closing, low speed, standstill, noise

7 November 2026. Branch `md2-gap-closing`. Forecasts F600-F633 in `foundations/forecasts.csv`, each committed before its run (06e750b for the measurements, 1f4ec7d for the model and T0). No held-out recording was read for any number here ([HOLDOUT.md](HOLDOUT.md)). Scripts: `scripts/measure/gapclose.py`, `queues.py`, `noise2.py`; `scripts/theory/md_queue.py`, `md_platoon.py`. Numbers: [gapclose.json](gapclose.json), [queues.json](queues.json), [noise2.json](noise2.json), [model_fit.json](model_fit.json) key `round2`.

## 1. The N9 cars left standing (F600, F601): explained, no code fault

Round 1 reported 440-1,000 cars left on N9's Hamburg links after the feed ends. Two things:

- **The line counted FCD rows, not cars.** It took every sample at 2,890-2,899 s, about ten per car. Fixed in `scenes.py`: 101 / 44 / 87 cars (offset 0, Hamburg overlap .65, Hamburg end +4).
- **Those cars are backlog, not a lock.** The feed is 1,000 / 650 / 1,000 veh/h for 1,800 s. The measured driver discharges 13.1 / 9.2 / 13.4 cars per 90 s cycle against the one driver's 20.5, so in 2,800 s it moves 397 / 281 / 413 of 500 / 325 / 500 cars. Forecast from that arithmetic: 93 / 39 / 83, measured 101 / 44 / 87. No car stands over 61 s, and the discharge rate after the feed ends equals the rate before (0.99-1.05).

So N9 is the same miss as lane capacity: the measured driver's saturation flow (section 5).

## 2. Gap closing on its own timescale (F602-F608)

Tables: follow.py's highD without location 6, DLR HT 06-14 UTC, TGSIM I-90/94 stationary, I-294 L1, I-395. Rollouts are the kernel's twin at 5 Hz from the recorded state behind the recorded leader, noise off. The driver's own time gap factor is taken four ways, because a driver who prefers a long gap and a driver who has not yet closed one look the same:

- population: f = 1;
- other leaders: the driver's median steady time gap behind its other leaders, relative to T(v);
- shrunk: the same, pulled towards 1 by its reliability (DRIVER.md's persistent log-SD 0.27 against 0.47 between 10 s windows, one window per 10 s of other steady following);
- own track: the median over its whole track, this window and its future included. That is an upper bound: the target is where the driver ended up.

| k_p, m/s² per s of time gap too far | 1 s | 10 s | 30 s |
|---|---|---|---|
| population | 0.025 (0.023-0.029), round 1 | 0.032 (0.027-0.040) | 0.038 (0.033-0.044) |
| shrunk own reference | | 0.035 (0.028-0.042) | **0.044 (0.039-0.049)** |
| raw other-leader reference | | 0.036 | 0.057 |
| own track, future included | | 0.084 (0.072-0.096) | 0.139 (0.129-0.163) |

- **Identification (point 1 of the brief): not confirmed.** The one-second objective does see k_p. Refitting K, c_a and k_g at each k_p, its minimum is at 0.025-0.05 and k_p 0.15 is 4.2% worse in RMSE, 7% in MAE (F604). Ten and thirty seconds give the same small pull. Round 1's 0.1-0.15 on 30 s rollouts (F310) had f = 1 on report 05's windows; here only a target read from the future reaches that range.
- **Open gaps close slowly in the recordings** (F607). Followers starting 1 s or more above T(v), same leader for 30 s: the median excess goes 1.44 → 0.98 s (DLR HT), 1.65 → 1.19 (I-90/94 stationary), 1.64 → 1.23 (I-294 L1), 1.57 → 0.93 (I-395). None halves in 30 s.
- **The round 1 law already closes them as fast or faster** (F608): behind the same leaders it leaves 0.88 / 0.79 / 1.03 / 0.73 s after 30 s. With k_p 0.044 it halves them in 14-29 s. A stronger pull would make the 30 s drift worse.
- **The drift on highD is a pull, and a weak one.** The mean change of time gap over the next 10 s falls steadily from +0.15 s at 0.35 s to −0.6 s at 2.95 s, with no flat stretch. Read as a steady closing speed, it gives k_p about 0.027.
- The joint fit on 1 + 10 + 30 s moves K to 3.85, k_g to 0.01 and k_p to 0.034, and changes the next-second error by under 2% on each table. Not adopted: k_g has its own measurement (DRIVER.md, 0.2-0.5).

**Selection (point 2): confirmed, for the time gap, not for the pull** (F602, F603). At 25-35 m/s the median over all following is 1.23 s on highD and 1.60 s on DLR HT, against 0.96 and 1.10 s in steady windows. At 15-25 m/s on TGSIM it is 0.24-0.37 s higher. The steady windows pick the coupled followers. On highD the time gap with zero mean drift over 10 s is 1.15 s (1.09 with the leader's speed steady), 0.13-0.19 s above the steady median. DLR HT shows a second selection: pairs that stay together 10 s drift apart at every gap, because a faster follower overtakes and ends its pair. TGSIM's attractors are wide and disagree (0.90, 1.55, 1.51 s).

## 3. Low speed and standstill (F609-F614)

`queues.py`: followers found in each frame (nearest car ahead on the heading line, within 1.5 m across) on rounD and inD (locations and days not held out), SinD Tianjin, Chongqing, Changchun, NGSIM Lankershim (first use; the signal archive on disk is only aerial photos, so no phases) and TGSIM I-90/94 stationary (follower table; centre spacing minus 5 m).

| | rounD | inD | SinD Changchun | Lankershim | TGSIM I-90/94 st. |
|---|---|---|---|---|---|
| Standstill bumper gap, m | **1.83** (1.74-1.89), 596 | 1.83-1.96 at positions 2-4 (all stops 2.59: parked cars) | 2.32 (2.22-2.45), 426 | 2.72 (2.58-2.85), 1,018 | 3.06 (centre − 5 m) |
| Creep: share moving ≥ 0.5 m while the leader stands | 17% | (parked cars) | 16% | 23% | 19% |
| Gap at first stop → before the leader moves, m | 1.88 → 1.73 | | 2.41 → 2.35 | 2.74 → 2.65 | 2.82 → 2.66 |
| Gap at 1 / 2 / 3 / 5 m/s, m | 2.7 / 4.0 / 5.1 / 6.1 | 3.2 / 4.1 / 5.3 / 8.1 | 2.8 / 4.5 / 5.9 / 8.4 | 3.5 / 4.6 / 5.3 / 6.7 | 3.9 / 4.8 / 5.9 / 8.6 |
| Start delay at 1 m/s after the car ahead, s | 1.20 (1.14-1.25) | 1.37 | 1.62 | **1.08** (1.03-1.15), flat over positions 1-6 | 1.60 |
| Follower peak acceleration, m/s² | 2.10 | 1.76 | 1.78 | 2.74 (noisy) | 1.43 |
| Gap passing 5 / 8 m/s, m | 6.5 / – | 9.2 / – | 11.3 / 16.0 | 9.7 / 12.9 | 12.1 / 16.9 |
| Headway at the line by position, s | 3.2, 2.9 (yield line) | 3.8, 2.8 | 4.1, 3.3, 2.8, 3.3, 2.6, 2.4 | 3.0, 2.3, …, 2.0 at 6 | outflow 3.0 (50 m on, with restops) |

- **Standstill: 1.7 m stands for German queues** (rounD 1.83, inD 1.83-1.96). US and Chinese queues stand 0.6-1 m further apart.
- **Queues compact as cars stop, not after.** 77-85% do not creep. Those that do move about 1 m, and more often the larger the gap (Lankershim 11% under 1 m, 42% at 6-7 m). The driver's start hold (no start while the car ahead stands within 15 m) matches this. No creep rule was added.
- **Spacing from standstill is s0 + T v with T about 1.0-1.3 s, not max(s0, T v).** At 1 m/s real cars keep 2.7-3.9 m. Round 1's law asked for 1.7 m.
- **Start delays are 1.1-1.4 s on German and US urban queues and flat with position.** SinD and TGSIM jams give 1.6 s.
- **Followers fall back while they launch.** At 8 m/s they are 13-17 m behind the car ahead, more than the 10-12 m they keep at that speed in steady following.

## 4. Noise (F615, F616)

Round 1's residual of the next-second speed change has a lag-1 autocorrelation of 0.00-0.32 on the TGSIM tables. White command noise through a 0.5 s response cannot go below 0.34; only noise outside the driver can. `noise2.py` splits the residual into OU command noise through the response and a recorded-speed error with its own correlation time, fitted to the autocorrelations at 1, 2, 3 and 5 s:

| | highD | DLR HT | I-90/94 st. | I-294 L1 | I-395 |
|---|---:|---:|---:|---:|---:|
| Instrument share of the variance | 0 | 0 | 52% | 46% | 36% |
| Driver sigma_n, m/s² | 0.24 | 0.39 | 0.38 | 0.41 | 0.28 |
| Driver tau_n, s | 1.5 | 0.75 | 0.5 | 0.75 | 2.0 |
| Speed about a 2 s quadratic, m/s (F616) | 0.003 | 0.006 | 0.045 | 0.029 | 0.107 |

TGSIM's recorded speed scatters 10-38 times as much as highD's, and its instrument part is white. Once that part is removed, the five tables agree on the driver: 0.24-0.41 m/s² over 0.5-2 s. Frozen: the median, **0.38 m/s² over 0.75 s**. Round 1's 0.97 m/s² white was the tracker.

## 5. The model, round 2

Each new measurement enters as a measured part (MODEL.md, "Round 2"):

| Part | Round 1 | Round 2 | Source |
|---|---|---|---|
| Desired gap | max(s0, f T(v) v) | **s0 + f (T(v') − s0/v') v**, v' = max(v, 6.5 m/s): equal to T(v) v above 6.5 m/s, s0 + 1.34 s × v below | queues.json F611 |
| Command noise | 0.97 m/s², 0.1 s | **0.38 m/s², 0.75 s** | noise2.json F615 |
| k_p | 0.025 | 0.025, kept | 1, 10 and 30 s agree within 0.025-0.044; recordings close no faster (F604-F608) |
| K, c_a, k_g | 2.69, 0.51, 0.28 | kept | the joint multi-horizon fit drops k_g, which has its own measurement |
| Standstill gap | 1.7 m | kept | rounD 1.83, inD 1.83-1.96 (F609) |
| Creep | none (no start while the car ahead stands within 15 m) | kept | 77-85% do not creep (F610) |
| Start reaction | 1.0 s after the car ahead moves | kept; the twin's delay at 1 m/s is 1.25 s against 1.08-1.37 measured | F612, F617 |
| Roundabout entry critical gap | 3.0 s (measured driver only) | **4.97 s for both physical drivers**: rounD's drivers who stopped at the line, the case the give-way rule models (3.0 s tried first, F631) | gaps_rounD.json |

The 30 s rollouts on table windows not held out move by −0.8% (13.12 against 13.23 m pooled; F633).

### Launch from rest at a give-way line (orchestrator's item)

Of the 1.7 s between a major car crossing and the first minor car entering, about 0.7 s is the launch from rest over the last 0.6 m. The recordings bound it. A standing car reaches 1 m/s 1.1-1.4 s after the way opens (queues.json, the car ahead as the trigger). Its peak acceleration is 1.8-2.1 m/s², reached through a response of about 0.5 s (rounD 2.10, inD 1.76, SinD 1.77-1.78). Through that response, 0.6 m from rest takes about 1.15 s (2 m/s² behind a 0.5 s lag). The one driver takes 0.7-0.8 s because its 2.02 m/s² comes as a step. So the measured launch is not faster than the code's; the launch does not explain a too-slow entry.

## 6. Checks and T0 (F617-F635)

| | Forecast | Result | Verdict |
|---|---|---|---|
| F617 queue twin against the measured launches | inside the sites' spread | start delay 1.25 s, peak 1.60 m/s², gap at 5 m/s 9.4 m; at 8 m/s **17.5 m** against 12.9-16.9; headway from position 6 2.3-2.9 s | partial miss |
| F618 kernel against twin, I-294 L1 | under 0.02 m/s | 0.003 m/s | pass |
| F619 I-294 L1 one follower, 30 s, 5 seeds | under round 1's 17.6-19.3, at most 15.6 | 14.70 m (14.25-15.15); one driver 13.6; round 1 after F311 13.9 | pass as written, no gain over round 1 |
| F633 30 s table rollouts, not held out | within 2% of round 1 | 13.12 against 13.23 m | pass |
| F620-F629 T0 lines from the round 2 equations | md_platoon_r2.json | L1 30 km/h 1,055 (1,124); L3 7.38 (6.7-8.0); S1 2.98 (2.69 ± 0.29); S2 6 of 9; W1 +2.39 (1.57 ± 1.01); G1 5.17 (3.48); L2 ring 1,061 (2,413); L6 427 (687) | L3 S1 W1 pass; L1 L2 L6 G1 miss |
| F630 realism | results | **L1 1,104 / 1,052 veh/h** at 50 / 100 km/h against 1,640-1,900; S1 2.98 s against 2.0 | fail |
| F631, F634 roundabout entry | Tanner at own tc within 15% | 3.0 s: 636 / 268 / 137 against 821 / 483 / 315. 4.97 s: **582** / 254 / 137 against **669** / 319 / 203 | 4.97 s passes at 400; at 800 and 1,200 the ring locks in some seeds with any tc |
| F632 whole suite | more than 91, fewer than 142 | **100 pass, 99 fail of 199** | pass |
| F635 c_a on launches | 0.6-1.0 | rounD 0.30, inD 0.37, SinD Changchun 0.44 | miss |

**Why capacity stays far off, with every part measured.** The discharge parts agree with the recordings one at a time: start delay, peak acceleration, the gap at 5 m/s, standstill, creep. But the law rolled over 222 recorded launches behind their own leaders falls back where real followers do not. The median gap error is +0.6 m at 2 s, +1.5-2.0 m at 4 s and +1.4-3.4 m at 8 s on rounD, inD and SinD Changchun (queues.json `launch_rollout_8s`). So the part responsible is **the follower's acceleration in the first four seconds after it starts to move**.

- The share of the leader's acceleration is not it: measured on the launches it is 0.30-0.44, below 0.51 (F635).
- The 1.5 m/s cap on closing speed is not it: lifting it moves the twin's gap at 8 m/s by 1 m only.

As with the 30 s drift, the next-second fit is unbiased while seconds of small errors add up. The next measurement is a multi-second fit on launches, to find which term: the response from rest, the closing gain at low speed, or the gap term at low speed. Nothing was tuned to capacity (rule 9: two rounds on this problem, F635 and the launch rollout, stopped).

**Ring and L6.** At the 1.63 m/s limit a follower cannot go faster than the car ahead, so it keeps whatever gap its launch left: 8.7 m against the 3.9 m it wants. The same launch fault, not a separate one. The ring (L2) stays at half its band as in round 1.

**Held-out tests (step 6) were not run.** The realism rows fail, so the gate to open the held-out set is closed. HOLDOUT.md is unchanged; no held-out recording was read in this round.

**Default.** The measured driver stays off (`--tune measured=1`). The one driver (`measured=0`) is unchanged except at roundabout entries, which now take 4.97 s instead of HBS's 5.9-6.7 s, as the orchestrator asked. G8 is the only scene built as a roundabout. Rerun alone, its scored lines move F402's pass from 800 to 400, so the count stays 142 / 60 by that reckoning; the rest of the suite was not rerun on the default driver.
