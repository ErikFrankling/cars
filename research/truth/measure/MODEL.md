# The measured driver: model

7 November 2026, written before the kernel code. Every number comes from [DRIVER.md](DRIVER.md) or is fitted on recordings that are not held out ([HOLDOUT.md](HOLDOUT.md)). The fit is `scripts/measure/fit_driver.py`, its numbers are in [model_fit.json](model_fit.json). The kernel twin is `md_*` in `crates/cars-core/src/shaders/common.wgsl`. Held-out and T0 results: [MODEL_RESULTS.md](MODEL_RESULTS.md).

## Why a new law

The one driver of `foundations/scenes-log.md` §3 is Krauss with a physics certificate. It steers towards one target gap at every step. The recordings say drivers do not: they answer closing speed and the leader's acceleration, with a lag of about 0.5 s, and barely react to the gap until they are well too close. So the gap is where the following dynamics leave it, not a set point.

## The law

Each step of length dt, for the speed v, the realised acceleration a of the last step, and a leader at bumper gap g with speed v_l and acceleration a_l:

1. **Desired gap.** g\*(v) = max(s0, f_i T(v) v). T(v) runs linearly through DRIVER.md's medians: 1.6 s at 6.5 m/s, 1.4 at 12.5, 1.2 at 17.5, 1.1 at 22.5, 0.95 at 30, 0.8 at 40, flat outside. s0 = 1.7 m. f_i is the driver's own factor.
2. **Gap error in seconds.** e = (g − g\*) / max(v, 1 m/s).
3. **Command behind this leader.**

   a_f = K · min(Δv, Δv_max) / max(g, 1 m) + c_a · a_l + k_p · max(e, 0) − k_g · max(−e − 0.5 s, 0),

   with Δv = v_l − v. The first term is the inverse time-to-collision: the rate at which the leader's image grows, Δv/g, times a speed K. It makes one gain cover both regimes, since motorway gaps are long and congested gaps short.
4. **Free driving.** a_free = min((v_des − v)/T_v, engine), with v_des the lane limit times the driver's speed factor. With no car within 100 m ahead on the lane (the range the law was fitted on), also at most the launch law a_drv = a0 − a1 v (floor 0.7 m/s²). A follower answers its leader with what the engine gives. (First draft: a_drv · (1 − (v/v_des)⁴) always. It capped every following command at 0.37-0.7 m/s² above 10 m/s, and followers fell 8-20 m behind in 30 s, F308-F311.)
5. **The driver's command.** a_cmd = min(a_f over every leader, a_free) + n(t). n is an Ornstein-Uhlenbeck noise with SD σ_n and correlation time τ_n, frozen while standing.
6. **Response.** a ← a + (1 − e^(−dt/τ_r)) (a_cmd − a), and v' = v + a dt. Because every constraint goes through the same filter from the same state, the lowest of them is the filtered lowest command.
7. **Bounds, in this order.** The vehicle's power, traction and brakes (`ph_a_cap`, `ph_floor`). Stopping for what stands or for a line: the measured stop law of report 19 (`ph_stop_comfort`, mean 1.3, peak 2.2 m/s²), unchanged. The hard safety bound: the certificate `ph_v_cert`, which keeps a stop possible behind the leader whatever it does, assuming it brakes no harder than this driver can (8.3 m/s² dry). It is a bound, not a behaviour.

**The safety bound in normal following.** With equal speeds the certificate asks for 0.5 m + (t_r λ² + dt)/2 · v + v dt/2 of bumper gap: 0.40 v + 0.5 m at dt 0.25 (t_r 0.3 s, λ 1). That is a time gap of 0.42 s at 30 m/s and 0.48 s at 10 m/s. Real followers sit above it 95% of the time (highD p5 0.47 s), and the law's own braking starts 0.5 s below the driver's gap, so it acts only on the tightest few percent and in emergencies. The scene and replay runs count how often it decides (`C_CERT_FLOOR` and the `cars why` probe `leader` against the certificate).

**Start from standstill.** A standing car starts its clock when the way opens: 1.0 s after the car ahead moves (report 05, DLR UT; Lankershim and Peachtree agree), and for the first car at a light a reaction r_1 after green. Then the law runs from a = 0. So the first car passes 1.5 m/s after r_1 plus the time the 0.5 s response takes to get there.

## How each measured number enters

| DRIVER.md | Enters as |
|---|---|
| Time gap against speed, 1.6 → 0.8 s | T(v), the table above |
| Personal time gap, log-SD 0.27, kept for the trip; r −0.41 with free speed | f_i = exp(0.27 z_T), drawn per trip with corr(z_T, z_v) = −0.41, where z_v is the trip's standardised speed factor |
| Desired speed spread CV 0.12-0.20 | speedDev 0.17 (the median of the six sites) when the vType leaves SUMO's 0.1 |
| Gap error: nothing from 0.5 s too close to 1.75 s too far; braking 0.2-0.5 m/s² per s beyond 0.75 s too close | the zero band [−0.5 s, 0] and k_g (fitted, forecast 0.2-0.5); the far side's weak pull k_p (fitted, forecast under 0.05 m/s² at 1.75 s) |
| Closing speed linear, no dead zone, 0.11-0.2 /s motorway, 0.3-0.4 /s congestion, flat above +1.5 m/s | K Δv / g, Δv_max = 1.5 m/s. No dead zone, no perception threshold |
| 0.25-0.65 of the leader's acceleration within 1 s | c_a (fitted). Through the 0.5 s response, c_a shows as 0.57 c_a in the next second's mean |
| Response lag: first order 0.48-0.56 s, dead time under 0.3 s | τ_r = 0.5 s. No dead time beyond the one step the update order gives |
| Standstill bumper gap 1.7 m | s0, and minGap 1.7 when the vType leaves SUMO's 2.5 |
| First car 2.0 s after green to 1.5 m/s; peak 1.77 m/s² | a0 (fitted so the filtered launch peaks at 1.77) and r_1 = 2.0 s minus the time to 1.5 m/s |
| Give-way follow-up 2.7 / 3.2 / 4.9 s, roundabout 2.76 s; critical gaps 6.9 / 3.9 / 3.0 s; no impatience | the give-way values below |

## Numbers fitted inside the model

All on the five follower tables of `scripts/measure/follow.py`: highD without location 6, DLR HT 06:00-14:00 UTC, TGSIM I-90/94 stationary, I-294 L1, I-395. Equal weight per dataset, one query per second of following, scored on the speed change over the next second when the model is run from the recorded state behind the recorded leader. Frozen before any held-out recording is opened.

| Number | What it is | Forecast before the fit |
|---|---|---|
| K | closing-speed gain, a speed | 2.5-4.5 m/s (gain × gap is 2.0-2.8 on highD, 2.3-3.8 on DLR HT, 3.3-5.4 on I-90/94 stationary) |
| c_a | share of the leader's acceleration | 0.4-1.1 |
| k_g | braking per s too close, beyond 0.5 s | 0.2-0.5 m/s² per s |
| k_p | pull per s too far | 0.005-0.05 m/s² per s |
| T_v | free relaxation to the desired speed (F311, 30 s rollouts of I-294 L1, I-90/94 stationary, I-395) | 1-4 s |
| σ_n, τ_n | the command noise left over | σ_n 0.1-0.4 m/s², τ_n 1-6 s |
| a0, r_1 | launch: SinD Tianjin, Chongqing, Changchun | a0 1.9-2.3 m/s², r_1 0.6-1.2 s |

## Frozen values (model_fit.json)

| Number | Value | 95% CI by follower | Per table (highD, DLR HT, I-90/94 st., I-294 L1, I-395) |
|---|---|---|---|
| K | 2.69 m/s | 2.60-2.78 | 3.1, 3.8, 4.2, 2.0, 0.9 |
| c_a | 0.51 | 0.49-0.52 | 0.48, 0.28, 0.23, 0.74, 0.68 |
| k_g | 0.28 m/s² per s | 0.23-0.32 | 0.62, 0.07, 0.29, 0.27, 0.19 |
| k_p | 0.025 m/s² per s | 0.023-0.029 | 0.018, 0.017, 0.049, 0.030, 0.013 |
| σ_n, τ_n | 0.97 m/s², 0.1 s | median over tables | German tables 0.23-0.34 over 1.5-2 s; TGSIM 0.97-1.29 white (F305) |
| T_v | 1.0 s | flat from 0.5 to 2 s | |
| a0, r_1 | 2.025 m/s² (the table's own 2.02), 0.78 s | | |

The law halves the next-second error of constant speed on all five tables (F304). On 30 s rollouts the one-second k_p is weaker than the rollouts want (0.1 would cut the pooled error from 8.4 to 7.0 m) but DRIVER.md measured under 0.05 m/s² at 1.75 s too far, so 0.025 stands; this tension is open.

## Give-way values

Critical gap by movement from inD and rounD (DRIVER.md), replacing HBS: minor road left 6.9 s, minor road straight 6.6 s, left off the priority road 3.9 s, roundabout entry 3.0 s. Right from the minor road was not measurable on inD and keeps HBS's 5.9 s, as do the HBS terms for a stop sign and a fast major. Follow-up is not a parameter of this driver: it comes out of the start law and the corner speed, and G1 tests it against 2.7-3.2 s.

## What it leaves out, on purpose

- No perception threshold, no dead zone: none was found.
- No impatience: none was found.
- Free speed is kept for the whole trip, though it drifts in reality (r 0.5 at 3 km). The scenes and replays are shorter than that.
- The slower part of the time gap that belongs to a leader pair (e-folding 1.2 km) is not modelled.
- Urban desired speed is not measured; urban lanes use the lane limit times the factor.

## Round 2, 7 November ([ROUND2.md](ROUND2.md))

Two parts change, each from a measurement on recordings not held out. Everything else stays frozen as above.

1. **Desired gap from standstill.** g\*(v) = s0 + f_i (T(v') − s0/v') v with v' = max(v, 6.5 m/s). Above 6.5 m/s this is f_i T(v) v + (1 − f_i) s0, the same as before for the median driver. Below, spacing grows as s0 + 1.34 s × v. Measured on rounD, inD, SinD, Lankershim and TGSIM: 2.7-3.9 m at 1 m/s, 4.0-4.8 at 2, 5.1-5.9 at 3 (queues.json, F611). Round 1's max(s0, T v) asked for 1.7 m at 1 m/s.
2. **Command noise** 0.38 m/s² with correlation time 0.75 s: the driver's part of the next-second residual once TGSIM's speed error is split off (noise2.json, F615). Round 1's 0.97 m/s² near-white was mostly the tracker.

Kept, with the round 2 evidence: k_p 0.025, since 10 and 30 s rollouts give 0.035 and 0.044 and real open gaps close no faster than the law closes them (F604-F608). Also kept: K, c_a, k_g, s0 1.7 m (rounD 1.83), the start reaction of 1.0 s (the twin's delay at 1 m/s is 1.25 s, measured 1.08-1.37), and no creep rule (77-85% of stopped cars do not creep). Roundabout entries take rounD's critical gap of drivers who stopped at the line, 4.97 s (4.40-5.60), for both physical drivers: the give-way rule counts gaps for a head standing at its line. The 3.0 s of all seen arrivals, mostly rolling, was tried first and missed (F631, F634).

Twin: `fit_driver.command` (MD_LOWGAP=0 gives round 1), `md_platoon.py`, `md_twin.py`; kernel `md_cmd` in common.wgsl; constants `MD_NOISE_SD`, `MD_NOISE_T` in world.rs.

## Round 3, 7 November ([STRUCTURE.md](STRUCTURE.md))

The law above is unchanged. Round 3 tested whether another structure reproduces every measured pattern at once: the current law refitted, Newell-anchored, full velocity difference, IDM, two regimes, and a closing gain that saturates at small gaps (K/(g + g_1), from F801) or scales with speed. Each was fitted on the next second, the 30 s windows and the queue launches jointly, then scored on every pattern. None survives. The conflict is the same in every structure: real drivers close up near standstill (1.7-1.9 m) and keep up during a launch, but barely close an open gap at speed (25-41% in 30 s), and each law has one pull for both. Measured on the way: the closing gain decays more slowly than 1/g inside each table, and launches have no leader-acceleration share (F801).
