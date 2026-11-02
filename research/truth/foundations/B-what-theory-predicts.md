# B. What theory lets us calculate before running anything

Checked 2026-11-02. Reading and small hand sums only: no simulation, no GPU, nobody contacted. Hand-sum scripts: `/tmp/foundations-b/scripts/` and `/tmp/foundations-b/scripts2/sheet.py`.

Rule of this file: every number here comes from a formula and measured inputs. The simulator must then reproduce it. SUMO and other simulators are not references. Only theory and measurements of real traffic are.

Labels: **[S]** the source says this. **[I]** I inferred or computed this from the source. Short names of sources resolve in section 7.

**What changes because of this sheet** is in section 0. Sections 1 to 5 are the formula sheet, smallest scale first. Each ends with tests that run in seconds on a small scene. Section 6 says where theory fails.

## 0. What this sheet says we should do differently

1. **Check theory before any big run.** About 30 scenes (L1–L7, S1–S8, G1–G9, LC1–LC8, N1–N8) cover every scale. Each has a computed answer and a tolerance. Each takes seconds. None needs a city.
2. **Screen every map and route set before running.** On m12 with today's routes (07–08 h), 22 approaches are over capacity at 50% and 315 at 100%. 12 and 227 of them spill inside 15 min. This takes minutes with no simulator (§5.5). Add an LTM pass for the cascade. **Then a lock in the micro run that LTM doesn't show is a driver or junction fault, and a lock in both is map and routes.**
3. **Check the top list of that screen against the real road first.** At 50% the worst overflows are main-road through movements coded to give way where OSM shows signals: Karl-Liebknecht-Straße, Rubensstraße, Straße des 17. Juni at Ernst-Reuter-Platz, Von-der-Heydt-Straße. They carry much of 50%'s overflow. Unproven, one look each (§5.5).
4. **Network capacity is not the limit.** From the map: top of the curve 262,000–318,000 veh-km/h on major roads (Loder), ≤ 410,900 (cuts). Critical accumulation 13,000–18,500 cars on those roads. Full demand peaks at 245,000, 6–15% above real counts. So every lock is local (§5.4).
5. **Give-way deficit is mostly follow-up time.** The physical driver's numbers fit t_f 4.41 s, t₀ 4.9 s. HBS: 3.0, 4.4. Fixing t_f alone gets 85–95% of HBS (§3). Don't touch gap acceptance first.
6. **Human's low saturation is launch, not time gap.** Its own wave speed gives T = 1.25 s, which predicts 1,983/h. 1,500/h needs cars crossing the line at 25 km/h (§1). Same fault family as item 5 and as lost time (§2): cars start too slowly from rest.
7. **A lane-changer needs relative speed and distance.** Gaps arrive at k·Δv, so zero at matched speed. At 900/h a 97 m block gives about 36% success at Δv 3. 95% needs about 660 m, or 190 m after slowing to Δv 6 (§4). Lane planning distance and slowing are capacity inputs.
8. **Healthy N is confirmed without a simulator.** Real speeds and route veh-km give 13,186–15,114 at 100%, so 7,015 at 50% stands (§5.1).

**Corrections to earlier work.**

- Monograph eq. 8.33 misprints t_c for t₀ (§3).
- Loder's Table 1 reproduces its own means only with ln(b_c): 625 against 653 (§5.4). C said its reading gave 265.
- C's 38,100 cars at Loder's critical point is 2.4–2.9× too high: Loder's R is major roads inside the area, 10.35 here, not 28.9 (§5.4).
- Quoted time gaps aren't Newell's T. Remove 2.5 m / v and real medians fit a constant 1.4 s (§1).

## 1. One lane

**Theory in one paragraph.** LWR: cars are conserved and flow is a function of density, so dk/dt + dq/dx = 0 with q = Q(k) (monograph ch. 5, §5.1, p. 5-2 onward). Newell 2002: in congestion each car copies its leader's trajectory, shifted back by a fixed distance s and a fixed time T. That is the same thing as a triangular Q(k). Wikipedia's summary of Newell gives τ = 1/(w·kj) and δ = 1/kj, "independent of the speed of the leading vehicle and the traffic state" ([Wikipedia, Newell's car-following model](https://en.wikipedia.org/wiki/Newell%27s_car-following_model)). I could not get Newell's paper itself (TR-B 36(3), 2002; paywalled). So three measured numbers (T, s, v) fix everything on one lane. **[S]** for the form, **[I]** for the sheet below.

**Definitions matter here.** Newell's T is not the time gap people quote. Raw time gap = (spacing − car length)/v. Newell's T = (spacing − s)/v. The difference is (s − L)/v, about 2.5 m / v. **[I]** Applied to report 19's real medians (congested motorways, a German autobahn at the top speeds; I assume its gap is bumper to bumper, which the file doesn't state in those words):

| Speed, m/s | Real p50 raw gap, s (report 19) | Minus 2.5 m / v | Newell T, s |
|---|---|---|---|
| 5–10 | 1.76–1.86 | 0.33 | 1.43–1.53 |
| 10–15 | 1.64–1.66 | 0.20 | 1.44–1.46 |
| 15–20 | 1.40–1.92 | 0.14 | 1.26–1.78 |
| 25–30 | 1.21–1.60 | 0.09 | 1.12–1.51 |
| 30–40 | 1.44 | 0.07 | 1.37 |

**[I] Real medians are consistent with one constant T of about 1.4 s across speeds.** The fall of raw gap with speed that report 19 notes is mostly the 2.5 m term. The next table uses T = 1.4 s, s = 7.5 m as the central case.

### Formula table

| Quantity | Formula | Inputs and measured range | Worked number | Test: scene, closeness |
|---|---|---|---|---|
| Capacity | q = 1/(T + s/v) | T: 1.0–1.6 s from your brief; medians 1.3–1.5 above. s: 7.0 (6.2–8.1) Braunschweig, 6.8–7.4 Lankershim, 8.1 I-90 (report 19). v: speed limit. Duret: 5–9 m for most of 180 pairs, I-80 lane 2 | 50 km/h, T 1.4, s 7.5: **1,856/h** (h = 1.94 s). Range T 1.0–1.6, s 6.5–8: 1,654–2,452. 100 km/h: **2,156/h**, range 1,907–2,917. 30 km/h: **1,565/h**, range 1,406–2,022 | L1. Queue released on a straight 500 m lane, count at 300 m over 5 min. Within 3% of the formula using the driver's own T and s |
| Critical density | kc = 1/(s + vT) | Same | 50 km/h: 37.1/km. 100 km/h: 21.6/km. 30 km/h: 52/km | L2. Ring, sweep density. Peak of q(k) within 5% |
| Jam density | kj = 1/s | s above | 7.5 m: 133/km. Range 125–154 | L3. Stopped queue. Mean spacing within 3% of the driver's s |
| Wave speed | w = s/T | Duret: mean 15.4 km/h, I-80 lane 2, individual values 0.5–13 m/s. Treiber & Kesting: −16 to −17 km/h extended jams, −18 isolated waves, about −20 on A5 (German motorways). San Francisco and Yokohama: 19.4 and 18 km/h (DG 2008, Table 1). Queue start wave 22.3 km/h, p10–p90 16–28, n = 22, one site (report 04) | 7.5/1.4 = 19.3 km/h. Range for your inputs 14.6–28.8 | L4. Queue release, time each car starts. Within 10% of s/T |
| Congested speed at given spacing | v = (spacing − s)/T | Same | Spacing 20 m: 8.9 m/s, 32 km/h | L2. Same ring. 5 densities above kc, within 5% |
| Back of queue growth (shock) | u = (q₂ − q₁)/(k₂ − k₁). Into a standing queue: u = qa/(kj − ka), ka = qa/v (Rankine-Hugoniot; monograph ch. 5 eq. 5.8) | qa, kj, v | qa 600/h, 50 km/h, kj 133: **4.9 km/h** upstream | L5. Block the lane, feed qa. Within 10% |
| Queue growing against a bottleneck | Number: dN/dt = qa − c. Length: u above with k₂, q₂ the discharge's congested state | qa, c | qa 900, c 600 per lane, w 19.3 km/h: 300 cars/h extra. Queue state k = 102/km (9.8 m spacing, 21 km/h). Tail moves **3.6 km/h**, not 300/133 = 2.3 km/h: a moving queue isn't at jam spacing | L6. Bottleneck by a lower speed limit or a held car. Within 10% |
| Accounting (Edie) | In any space-time box A: q = d(A)/\|A\|, k = t(A)/\|A\|, v = d(A)/t(A), so q = k·v always | d = total metres driven, t = total car-seconds, \|A\| = area in m·s. Edie 1963, cited by GD 2008 and DG 2008; original not read | Identity | L7. Any scene, any box. Exact to rounding. A failure means the instrument or the code loses cars |
| Cars conserved | N(x,t) counts never fall, and arrivals − departures = cars present | Identity | | L7. Exact |

**Check on real network data [I].** DG 2008 Table 1 gives San Francisco uf 13.4 m/s, w 5.4 m/s, κ 0.13/m. The triangle gives qm = κ·w·uf/(w + uf) = 0.500 veh/s. The table reports 0.5. Yokohama gives 0.515 against 0.5. T = 1/(κw) = 1.42 and 1.43 s, s = 7.7 and 7.1 m. So the formula, these inputs and urban saturation flow all agree.

### What the formula already says about our drivers

Report 23, section on isolated scenes, dt 1, gives saturation at 50 km/h, jam spacing and start wave for each driver. Those three measure T twice. If Newell holds, T = s/w and T = 3600/q − s/v must match. **[I]**

| Driver | s, m | w, km/h | T from wave | Predicted saturation | Observed | Speed at the line that explains the gap |
|---|---|---|---|---:|---:|---|
| Main (Krauss) | 7.1 | 20.9 | 1.22 s | 2,076 | 1,895 | 38 km/h |
| Physical default | 7.1 | 17.9 | 1.43 s | 1,857 | 1,714 | 38 km/h |
| Human | 7.9 | 22.8 | 1.25 s | 1,983 | **1,500** | **25 km/h** |

Reading: main and physical are near the line once you allow for cars not yet at 50 km/h at the stop line. **Human's deficit is not time gap: its wave says T = 1.25 s. A 2.4 s discharge headway with T = 1.25 needs cars crossing at 25 km/h.** So raising Human's capacity means fixing its launch and acceleration in the queue, not shortening T. Report 19's fix 10 (stronger low-speed start) points the same way. Measure speed at the line in test S1 to confirm. This is the sheet doing its job: three numbers, no city run, and it names the mechanism.

Status board note. "Saturation flow 50 km/h, physical 1,929 (branch)" gives h = 1.87 s. T = 1.4, s = 7.1 predicts 1.91 s. Inside the band.

## 2. One signal

**Theory.** The stop line is a bottleneck that switches between capacity and zero. Input-output queueing gives the car counts, LWR gives the queue's physical length. Fluid approximation is good at x below about 0.5 and well above 1. Near x = 1 randomness dominates (monograph ch. 9, §9.2, p. 9-3). **[S]**

| Quantity | Formula | Inputs and measured range | Worked number (S 1,800, C 90, g 40, 50 km/h, w 20 km/h, kj 133) | Test |
|---|---|---|---|---|
| Saturation headway | h_s = T + s/v_line. v_line reaches v after enough cars, see next row | Real 2.0 s (1.8–2.1); Lankershim 1.9, Peachtree 2.2 (report 19). FHWA: 1,500–2,000 commonly, 1,900 ideal, 2.2 s = 1,636 as example (STM §3.3.2, p. 3-6). HBS base 2,000/h confirmed by [BASt V324's summary](https://trid.trb.org/View/2573179), which also says speed limit matters | 1,856/h from T, s. Real median 1,800 | S1. Queue of 25, green long enough. Headway from car 10 on, within 5% of the driver's T + s/v |
| Discharge headway of car n **[I]** | Newell plus constant acceleration a. Crossing time t_n = t_r + (n−1)T + τ((n−1)s + d₀), τ(x) = √(2x/a) until v is reached, then v/a + (x − v²/2a)/v | t_r start reaction, d₀ stop-line distance, a launch rate. Real launch and first-car numbers in report 19 | T 1.4, s 7.5, a 1.8, t_r 1.0, d₀ 2: headways 2.49, 3.16, 2.50, 2.27, 2.15, 2.06, 2.00, 1.96, 1.94. **Steady only from car 9.** The usual "from car 4" rule measures 2.1, not 1.94 | S2. Same run. Headway of cars 2 to 12 within 0.2 s of the closed form using the driver's own a |
| Start-up lost time | l₁ = t_r + v/(2a) + d₀/v − h_s **[I]**, from the formula above. Monograph: 2–3 s, typical (§9.2, p. 9-2). STM: "approximately 2 seconds" | Real, first four cars: 2.74 (2.44–3.58), first car crossing 3.62 s (report 19). The model at a 1.8, t_r 1.0: 2.66 over first four, 3.06 over all | l₁ 3.06 s at 50 km/h, 2.22 s at 30 km/h with a 1.5, t_r 1.5. Lost time rises with speed limit | S3. Sum of (h_i − h_s). Within 0.5 s of 2.74 at 50 km/h. Report 19: main 0.2, physics 1.15, human 2.25 at dt 0.1, so this test fails today |
| Effective green, capacity | g = G + yellow + all-red − lost. c = S·g/C | HCM default 4 s lost per phase (STM §3.3.3, p. 3-7). End gain 2–4 s (monograph §9.2) | c = 1,800·40/90 = **800/h** | S4. Saturate 20 cycles. Count per cycle. Within 3% |
| Queue tail speed | u = qa/(kj − ka) (ch. 5, 5.8) | | qa 600: 4.9 km/h. qa 300: 2.4. qa 900: 7.8 | S5 |
| Start wave, reaches tail | t* = r·w/(w − u) after start of red; L_max = u·t*; N_max = kj·L_max (ch. 5, 5.9–5.11 in triangular form **[I]**) | w, r | qa 600: L_max **91 m**, **12.2 cars**, 16.4 s after green. qa 300: 37 m, 4.9 cars, 6.7 s. qa 780: 138 m, 18.3 cars, 24.8 s | S5. Uniform arrivals. Max queue length and car count, within 10% |
| Queue clears at the line | g_s = r·qa/(S − qa) | | qa 600: **25 s**, qa 300: 10 s, qa 720: 33 s | S5. Time when flow falls off S. Within 2 s |
| Max queue in input-output terms | qa·(r + g_s) | | qa 600: 12.5 cars | S5 |
| Uniform delay | d₁ = C(1 − g/C)²/[2(1 − qa/S)] for x below 1; (C − g)/2 for x ≥ 1 (ch. 9 eq. 9.63) | | qa 600: **20.8 s**. qa 300: 16.7. qa 720: 23.1 | S6. Uniform arrivals. Mean delay within 5% |
| Webster delay | d = d₁ + x²/[2qa(1 − x)] − 0.65(C/qa²)^(1/3)·x^(2+5g/C) (ch. 9 eq. 9.17, p. 9-6) | Poisson arrivals. Steady state | x .38: 17.8. x .56: 20.4. x .75: 24.7. x .90: 37.9. x .97: 105 | S7. Poisson arrivals, 200 cycles. Within 15% up to x = 0.9. Webster derived it partly from simulation (ch. 9), so 15% is about its own accuracy **[I]** |
| Overflow queue, time-dependent (Akçelik 1980) | x₀ = 0.67 + S·g/600 (S veh/s). Q₀ = (cT/4)[(x−1) + √((x−1)² + 12(x−x₀)/(cT))] if x above x₀, else 0. d = d₁ + Q₀/c (ch. 9 eq. 9.60–9.63, p. 9-14) | T analysis length, c capacity | T 15 min. x .75: Q₀ 0.3, 22 s. x .90: 2.4, 34 s. x .97: 5.3, 48 s. x 1.12: 16.4, 99 s | S8. Poisson, 15 min, x 0.9 and 1.12. Within 25%. Above x = 1 the counts are close to fluid, so require N at 15 min = (qa − c)·T within 10% |
| Oversaturated growth | dN/dt = qa − c. Tail moves at u | | qa 900, c 800: +100/h, after 15 min 25 cars more, or 188 m on one lane | S8 |
| Webster cycle (controller's choice) | C₀ = (1.5L + 5)/(1 − Y), Y = Σ critical qa/S (STM eq. 6-1, p. 6-32) | L lost per cycle | L 12, Y .6: 57.5 s. L 12, Y .8: 115 s | Input check only: sets a sanity range for generated programs |
| Green wave | Green can pass a platoon: offset = link length / v | | 300 m at 50 km/h: 21.6 s | Run in network scene N3 |

**Permitted left across opposing flow [I].** The left-turn lane's capacity during green is Siegloch's formula with the opposing flow's rate during its own green (qa·C/g), plus the turners who clear at the end. Monograph ch. 9 didn't give this; I combined it. Real sneakers at change of phase are not in the formula. Expect the formula to be 10–30% low at high opposing flow. Treat as a floor.

**Turn saturation [I].** s falls with turning radius. Using turn speed v = 1.28·R^0.505 (from an earlier report in this repo, not re-verified here) in h = T + s/v: R 10 m: 1,114/h, R 15: 1,245, R 20: 1,338, R 30: 1,468. HBS has radius reduction factors but [BASt V324's summary](https://trid.trb.org/View/2573179) finds them weaker than HBS assumes. Don't test harder than ±15%.

### Tests S1 to S8 share one scene

One lane, 500 m, one fixed-time signal, C 90, g 40. Feeds: queue only, uniform, Poisson. About 25 simulated minutes per case. Should run in seconds on CPU or GPU.

## 3. One give-way

**Theory.** Minor cars cross when a gap in the major stream is at least t_c. Followers use t_f each. The capacity follows from the gap distribution. Formula families differ by how they treat short major headways, and "the resulting differences are rather small" (ch. 8, §8.4.1, p. 8-14). **[S]**

**Correction to the monograph [I].** Eq. 8.33 is printed as q_m = (1/t_f)·e^(−q_p·t_c). Its own derivation from eqs. 8.29 and 8.31 gives t₀ = t_c − t_f/2 in the exponent: ∫_{t₀}^∞ q_p e^(−q_p t)·(t − t₀)/t_f dt·q_p = e^(−q_p t₀)/t_f. The HBS and HCM use t₀. Copying the printed version gives 623 where the correct one gives 736 (q_p 400, 5.9/3.0). Repo reports use t₀ correctly.

| Quantity | Formula | Inputs and measured range | Worked number at q_p 0 / 200 / 400 / 800 / 1,200 | Test |
|---|---|---|---|---|
| Capacity, Siegloch | c = (3600/t_f)·exp(−q_p(t_c − t_f/2)/3600). HBS 2015 uses this form (Brilon deck, Gl. S5-6) | HBS S5 urban t_g/t_f: right from minor **5.9/3.0**, left from major **5.5/2.8**, through **6.7/3.3**, left from minor **6.5/3.2** ([KNOBEL form, HBS 2015](https://www.muenchberg.de/buergerservice/stadtbauamt/bauleitplanungen/aktuelle-bauleitplaene/23-10-19-anlage-s-4-variante-1-qsv-kreuzung.pdf?cid=j4s)). HCM two-lane: right 6.2/3.3, through 6.5/4.0, left minor 7.1/3.5, left major 4.1/2.2 ([HCS TWSC guide, pp. 59–60](https://mctranswordpresssa.blob.core.windows.net/uploads/2022/01/TWSC.pdf)) | HBS right: **1,200 / 940 / 736 / 451 / 277**. Left major: 1,286 / 1,024 / 815 / 517 / 328. Through: 1,091 / 824 / 622 / 355 / 203. Left minor: 1,125 / 857 / 653 / 379 / 220 | G1. One minor lane always queued, Poisson major of given flow, 30 min each. Within 10% at each flow using the scene's own measured t_c, t_f |
| Capacity, Harders | c = q_p e^(−q_p t_c)/(1 − e^(−q_p t_f)) (eq. 8.32) | Same | HBS right: 1,200 / 939 / 733 / 443 / 266 | Band with Siegloch: shows how close the two families are |
| Tanner | c = (1 − q_p t_m)·q_p e^(−q_p(t_c − t_m))/(1 − e^(−q_p t_f)) (eq. 8.36) | t_m minimum major headway, 2 s in Fig. 8.9 | HBS right, t_m 2: 1,200 / 932 / 712 / 384 / 172 | G2. Major stream with real minimum headway. The Poisson test and this one bracket the answer at high q_p |
| Cowan M3 / Troutbeck | λ = αq_p/(1 − t_m q_p), c = αq_p e^(−λ(t_c − t_m))/(1 − e^(−λ t_f)) (eqs. 8.34–8.35) | α proportion free, t_m | α .75, t_m 1: 1,200 / 975 / 773 / 443 / 212 | Same |
| Multi-lane major | Sum lane flows in q_p when headways are exponential (eq. 8.82). Tanner 8.83–8.85 for dichotomised | | | G3. Two major lanes, half flow each. Within 15% of single-lane result |
| Gap acceptance | P(accept) rises with gap. t_c from Ashworth or maximum likelihood (§8.2.2), not from raw acceptance percentiles | Polus 2005: U = −10.34 + 0.03742 t_w + 2.509 t_g (eq. 7), 4.12 s at t_w 0, 3.67 at 30 s, 3.23 at 60 s, one site type (roundabout), accepted mean 5.85 s | Spread of logit: 0.72 s sd | G4. Log gaps offered and taken. Recover t_c within 0.3 s of the driver's setting |
| Variance effects | c × [1 + ½q_p²Var(t_c) + …] (Plank & Catchpole, eqs. 8.39–8.40). Distributions of t_c, t_f lower c. Realistic major headways raise it. "These effects compensate each other" (Grossmann, §8.4.1, p. 8-15) | | Net near zero | Use the simple formula as target |
| Rank 3 | c₃ = p₀·G₃, p₀ = 1 − x of the rank 2 stream (eqs. 8.50, 8.95). With short queues | | Left major q 150, G 1,000: p₀ .85, left minor 653 → 555 | G5. Cross with a left turner on the major. Within 15% |
| Rank 4 | p_z = 0.65p_y − p_y/(p_y + 3) + 0.6√p_y (eq. 8.97) | p_y = product of p₀ above | p_y .8 → .846, p_y .6 → .688 | G5 |
| Shared lane | c_s = 1/Σ(b_i/c_i), b_i share of stream i (§8.7.1, p. 8-35) | | Right 50% at 736, through 50% at 622: 674 | G6. One lane, two movements. Within 10% |
| Mean wait | w = 3600/c + 900T[(x−1) + √((x−1)² + (3600/c)x/(450T))], Kimber-Hollis form (§8.4.5). T in hours | Form as given by a Swiss-norm tool, which also finds T = 1 h fits its norm's curves ([KnotenCheck](https://github.com/pnfzygrzgf-svg/KnotenCheck), second-hand). HCM adds about 5 s for deceleration (from memory) | c 451, T 15 min: q 100: 10 s; 200: 14; 300: 22; 400: 45; 450: 67 | G7. Poisson minor at x .25–.9. Within 25% |
| Accepted gap vs wait | C says more. Waiting shrinks t_c about 0.45 s per 30 s (Polus) | | | See foundations/C |
| Roundabout entry | c = A·exp(−B·v_c), A = 3600/t_f, B = (t_c − t_f/2)/3600 (WisDOT Eq. 20.1–20.3). HCM 6th 1-1: t_c 4.99, t_f 2.609: c = 1,380·exp(−1.02×10⁻³ v_c). HCM 2010 1-1: 5.193, 3.186. Wisconsin 2020: 4.7, 2.6 ([MikeOnTraffic](https://www.mikeontraffic.com/hcm-6th-edition-roundabout/); [WisDOT](https://wisconsindot.gov/dtsdManuals/traffic-ops/manuals-and-standards/teops/16-15.pdf), Table 20.1, p. 13) | Lower values at some sites: Pratelli et al. got t_c 3.72 s in one case and t_f about 2.5 s ([WIT Press](https://www.witpress.com/Secure/elibrary/papers/SC21/SC21039FU1.pdf)). Treat as spread | HCM6: 1,380 / 1,124 / 916 / 608 / 404 at circulating 0 / 200 / 400 / 800 / 1,200 | G8. One-lane ring, four entries. Within 15% |
| Right before left | Wu 2003: C_i = (1 − x_{i+1})·C₀,i; C₀,i ≈ 3600/t_f, t_f 3.5–4.5, 3.9 used. Model is unverified against measurement, the paper says t_f must be measured | | C₀ = 923/h. All four arms equal: c = (1 + √(1 − 4a))/2 in units of C₀ **[I]**, no solution above a = ¼, so at most about 230/h per arm | G9. Four arms, no ranks. Within 20% of the model. Low confidence |

**What the formula says about our give-way today [I].** Fit t₀ and t_f from the physical default in report 23 (line 40 and line 47): 816 at q_p 0, then 474, 298, 159 at 400, 800, 1,200.

- t_f from the intercept: 3600/816 = **4.41 s**. HBS: 3.0 s.
- t₀ from the slope: 4.9 s over the whole range, 4.2–5.6 between neighbouring points. HBS: 5.9 − 1.5 = **4.4 s**.
- With t_f 4.41 and t₀ 4.9 the formula gives 816 / 474 / 279 / 162. It describes the driver almost exactly.
- **Fixing t_f alone, t₀ kept at 4.9, gives 1,200 / 696 / 404 / 234: 95%, 90%, 85% of HBS, up from 64%, 66%, 57%.** Fixing t₀ too gets the rest.

**So the physical driver's gap acceptance is about 0.5 s long, and most of the deficit is follow-up time.** The minor queue takes 4.4 s per car, not 3.0 s. A start from rest needs t_f ≈ t_r + √(2·s/a): with t_r 0.5, s 7.5 that is 4.37 s at a = 1.0, 3.39 at 1.8, 3.11 at 2.2. Real follow-up of 3.0 needs cars rolling up, not stopping for every gap. It is the same launch fault as Human's signal discharge and physical's lost time. Report 23's "follow-up time at give-way" is the right next item. Test G1 with t_f logged confirms.

Old driver: 436, 261, 152 at 400, 800, 1,200. Slope gives t₀ ≈ 4.6–4.9 s, again near right. Extrapolating to zero major flow gives about 720/h, t_f ≈ 5 s, though its free saturation is about 1,900. So old-driver cars discharge at 1.9 s with no foes and about 5 s with any foe. That reads as cars fully stopping at the line whenever a foe is near. **[I]**, needs G1 logs to confirm.

## 4. One lane-change section

**State of theory.** No source I read gives a validated closed form for the feasible rate of mandatory lane changes in city traffic. There are pieces: a capacity loss from lane changers occupying two lanes (Jin), a void from bounded acceleration (Laval & Daganzo), a merge split (Daganzo 1995), an empirical freeway weave capacity (HCM). The gap-offer formula below is mine, built from ch. 8 gap theory. **Treat it as a floor.** Real drivers open gaps and it omits that.

**The feasible rate is the smallest of four limits [I]:**

1. Gaps offered to the changers.
2. Stopped at the section's end: the give-way formula.
3. Room left on the target lane: capacity minus the loss from changing.
4. At saturation, the merge share.

| Quantity | Formula | Inputs and measured range | Worked number | Test |
|---|---|---|---|---|
| Gaps passing a moving changer **[I]** | λ = k·\|Δv\| = q·\|Δv\|/v per second. **At Δv = 0, λ = 0: a car matching the target lane's speed sees the same gap for ever** | k target density, Δv speed difference | q 900, v 10 m/s: 25 cars/km. Δv 3: 0.075 cars/s pass | LC1. One changer, fixed Δv, Poisson target. Count passes within 10% |
| Share of acceptable gaps | P = α·exp(−λ_c(h − t_m)), λ_c = αq/(1 − t_m q), Cowan M3 (ch. 8 §8.3.3, eq. 8.35). I use t_m 1 s, α = 1 − t_m q | h = lead + lag time + car length/v. **Measured h isn't in what I read.** Report 19: real following p5 is 0.4–0.9 s, so 1.7–3.3 s is a plausible range **[I]** | q 900: h 3.3: **P .42**. h 1.7: .63. q 1,500: h 3.4: .21, h 1.8: .42. q 1,800: h 4: .11, h 2: .30 | LC1. Same run, log gaps offered and taken |
| Hazard, mean wait | r = λ·P. Wait = 1/r | | q 900, Δv 3, h 3.3: r = .032/s, **32 s**. Δv 1: **95 s**. h 1.7: 21 s | LC1. Within 20% using the driver's own h |
| Success in a section | S = 1 − exp(−r·L/v_c), v_c = v − Δv | L section length | q 900, Δv 3, h 3.3: L 100 m: **.36**. L 300 m: **.74**. Δv 1, L 100: .11. q 1,500, v 8, Δv 2, h 3.4: L 100: .31. Motorway q 1,800, v 27.8, Δv 5, h 2, L 300: .30. Δv 10: .60 | LC2. 500 changers across lengths, share completed. Within .1 |
| Length needed for success S | L_need = v_c·ln(1/(1−S))/(k·Δv·P). **Scales with v_c/Δv, so slowing down pays twice** | | q 900, v 10, h 3.3, S .95: Δv 3: **660 m**. Δv 6: **190 m**. Median Berlin block: 97 m | Design rule: a driver's look-ahead must cover L_need, or it must slow. Checks route lane-planning distance |
| Flow of completed changes | Φ_gap = q_c·S | q_c arrivals wanting to change | q_c 300, S .36: 108/h complete on the way; 192/h reach the end | LC2 |
| At the end of the lane, stopped | c_end = Siegloch with q_p = target flow. Same as a give-way: gaps now arrive at q because Δv = v | t_c, t_f as h and a start from rest | t_c 4, t_f 2.5: q 600: **911**, 900: **724**, 1,500: **458**, 1,800: **364**. t_c 3, t_f 2: 1,290, 1,092, 782, 662 | LC3. Lane end, queue kept on the closing lane. Within 15% below saturation |
| Queue at the lane end | dN/dt = Φ_end − c_end, spill when N = storage | | q_c 192/h is well under c_end, so no queue at q 900. At q 1,800 with 500/h of changers: +136/h | LC3 |
| Target lane room | Φ ≤ c/(1 + ε) − q | c lane capacity | c 1,856, ε .1, q 900: Φ ≤ 787/h | LC4 |
| Capacity loss, occupying two lanes (Jin) | q = ρV((1 + ε)ρ), so capacity = C/(1 + ε). ε = N_LC·t_LC/(N·T) = (total time changing)/(total time travelling), eqs. 5–7, 12. Equal to e·v·t_LC for e changes per veh-m **[I]** | t_LC: Jin uses 2.5 s; 2.5–5.5 s in repo notes. e: 0.22–0.26/km US survey (report 04), about 0.3/km A39 (report 22) | Jin's weave: ε = 0.11, capacity ×.90. Motorway e .3/km, 100 km/h, 3 s: ε .025, ×.976. Urban e 1/km, 30 km/h, 5 s: ×.96. 300/h of 900 changing in 100 m at 10 m/s, 3 s: ε .10, ×.91. Same in 300 m: ×.97 | LC4. Two lanes, set rate of changes. Downstream capacity within 5% |
| Void from bounded acceleration (concept: Laval & Daganzo; number: me) **[I]** | Changer enters Δv slower, then accelerates at a. Void length Δv²/(2a). Cars lost per change n = k·Δv²/(2a). Flow lost = Φ·n | a about 1.5 m/s². τ = 3 s relaxation in L&D | k 30, Δv 5, Φ 300: void 8.3 m, .25 car, 75/h, 3.9%. Φ 600: 7.9%. Δv 10, Φ 300: 15.8%. **Goes as Δv²** | LC5. Same scene as LC4, vary Δv. Check the Δv² shape, within 25% |
| Capacity drop at a lane drop | Drop after queue forms: Δ = 1 − q_after/q_before. L&D's hybrid model 2,890 → 2,656, 8.3%. **Measured: 6–12% at M4 and I-494 (L&D §4.1); "in the order of 10%, even 20%" (Jin 2013 citing Persaud, Cassidy & Bertini, Bertini & Leal, Chung)** | Repo band 0–18% (report 04) | 3→2 lanes, 2,890: about 240/h lost | LC6. Lane drop, ramp up demand, read flow before and after breakdown. 5–15% and never negative. Report 23's negative numbers mean the scene had no pre-queue flow: fix the scene |
| Moving bottleneck | Q_m(v) rises with v above 30 mph; drop explained by voids (L&D §4.2) | Muñoz & Daganzo data via L&D Fig. 3 | Ratio ρ(v), read from the figure | LC7. Slow car at 5 speeds. Check ρ rises with v, not flat as plain LWR says |
| Freeway weave capacity (HCM 2010/6th) | c_IWL = c_IFL − 438.2(1 + VR)^1.6 + 0.0765·L_s + 119.8·N_WL per lane. c_IW = 2,400/VR (N_WL 2), 3,500/VR (N_WL 3). Take the lower. L_s in feet ([STRIDE J5 report](https://stride.ce.ufl.edu/wp-content/uploads/sites/153/2023/06/STRIDE-J5_Final-Report-2023.pdf) eq. 5-4. Its eq. 2-4 misprints .765) | VR weaving share. Freeway only. Report questions the method's validity | c_IFL 2,320, L_s 1,000 ft, N_WL 2: VR .2: **2,049**. VR .4: **1,885**. c_IW 12,000, 6,000 not binding | Cross-check only. LC4 at motorway speed within 15% |
| Merge share at saturation | Each approach gets a fixed share p_k once the outflow is the limit. Flows are the middle of three values (Daganzo 1995, §3, eq. 7) | p from lanes or zipper. 1:1 turn-taking reported in the merge literature (second-hand) | Target c 1,856, equal shares: 928 each | LC3. Saturate both. Share within .1 of p, **whatever the free-gap formula says** |
| Real wait | No formula. I-80 lane end: median 22.6 s, p99 72.7, max 79, 0 of 610 failed. Urban turners 4–5 s median, 27 p99, 33 max (report 14, via foundations/C) | | Free-gap formula at q 1,500 and h 3.4, Δv 2 gives 45 s mean, so about 135 s p95. Real max 79 s: **real drivers do better than the free-gap formula** | LC8. Compare wait distribution. p99 under 75 s on the same scene. A hold over 5 min on a small scene is a fault |

**Reading [I].** Three things follow without running anything.

1. On a 97 m block with no slowing a car gets across about a third of the time at q 900. So a route that needs a lane on the last block will often reach the end and stop, unless it plans 300 m or more back. A city with blocks this short only works if drivers plan ahead, slow down and get let in.
2. A driver who keeps pace with the target lane never gets a gap. Relative speed is what creates opportunities. Test LC1 exposes this at once.
3. Void loss goes as Δv² while opportunities go as Δv. So large speed differences cost the road more than they give the changer. I didn't derive an optimum.

**Coifman's point.** Followers of an entering car respond faster than followers of an exiting car (Xuan & Coifman 2012, abstract, confirming Wang & Coifman 2008). That asymmetry makes ripples that move upstream. Classic LWR "does not offer any mechanism" for stop-and-go. So one more test is possible, not yet quantified here: on a congested lane, followers' recovery time should differ between entering and exiting neighbours.

## 5. One road network

### 5.1 Accounting: true for any correct simulator, any day

| Quantity | Formula | Inputs | Worked number, Berlin box, 100% demand | Test |
|---|---|---|---|---|
| Edie over network | P = Σ q_i l_i = veh-km/h, N = Σ k_i l_i, V = P/N (Edie 1963; GD 2008 §2.2 forms, Yokohama) | Per link | | N6. Exact to rounding |
| Little's law | N = entry rate × mean time in network. Holds over a window much longer than a trip. Otherwise use the next row | Trips, times | Whole net, 07–08 h, probe speeds by class: **13,186 cars**. 08–09 h: **15,114**. **[I]**, by class: Σ (veh-km/h ÷ km/h), arterial 32, motorway 56, local 28 km/h, then 28/47/25 (from the earlier draft's numbers on the repo's probes; recheck) | |
| Differential form | dN/dt = e(t) − c(t), c = P/l, l mean trip length. Yokohama: P/c constant at about 2.3 km (GD 2008 §4.3, Fig. 8) | Berlin mean route 3.69 km, from routes | 50% run `f05_base` at 07:00: e 59,900/h, P/l = 37,924/h, predicted +21,976/h. Measured 07:00–07:30: +18,194/h. **Within 21%**, a good sign the run's accounting is sound | N6. Same on any run: within 10% over 30 min with l measured |
| Stopped share (Herman & Prigogine) | T_r = T_m^(1/(n+1))·T^(n/(n+1)); T_s = T − T_r | Texas central networks: T_m 1.75 min/mile, n 1.63, from a figure label in [Ardekani & Herman, CTR 304](https://library.ctr.utexas.edu/digitized/TexasArchive/phase2/304-1-summary-CTR.pdf); which city isn't clear from the text extraction | T 4 min/mile: stopped 27%. 6: 37% | Fit n, T_m from any run's per-car run and stop times. Compare with probe-derived values for Berlin, not Austin |

**Check on the status board [I]: the "healthy" target of 7,015 at 50% is confirmed without a simulator.** 13,186–15,114 at 100% is 6,593–7,557 at 50%. 7,015 is inside. At 10%: 1,319–1,511, with 1,403 inside.

### 5.2 From the map alone: capacity of every movement

Everything needs only OSM-grade data: lanes, length, speed limit, turn type, signal program, give-way code.

| Junction kind | Movement capacity per lane | Inputs | Berlin-like number |
|---|---|---|---|
| Signal, protected | c = min(S_dir, 3600/(T + s/v))·(G + 3 − 4 per green)/C | S_dir through 1,800, right 1,285 (R 12 m), left 1,600. Band 1,636–2,000 | 1,800, G/C .45: 810 |
| Signal, permitted left | Siegloch with q_p = opposing flow × C/g_opp, t_c 5.5, t_f 2.8, × share of green | Opposing flow, so depends on routes | q_opp 400 in g/C .45: q_p 889: 467/h during the permitted green |
| Priority, no foes | min(S_dir, 3600/(T + s/v)) | v | 50 km/h: 1,856 |
| Give-way | Siegloch, HBS t_c, t_f by turn. Multiply by p₀ for rank 3, p_z for rank 4 | q_p from the foes | §3 table |
| Right before left | C_i = (1 − x_(i+1))·3600/t_f, t_f 3.9 | Wu | 923/h, down to 230 |
| Shared lane | c_s = 1/Σ(b_i/c_i) (§8.7) | Turn shares | |
| Whole approach | x = max over any subset M of movements of Σ_M(Q_m/c_m)/lanes(M). Hall's bound, handles shared lanes **[I]** | Lane assignment | |

**Storage.** N_link = lanes × L / s. Box: 143,567 at 7.5 m in 1,077 lane-km. Median signal approach 92 m, 12 cars per lane. p10 25 m, 3 cars. **28% of signal approaches are under 50 m and 42% under 75 m** (m10, computed from the net). A 40 s green at 1,800/h moves 20 cars. So on those approaches a green can only be used if the next junction lets them through. "route or network capacity can be significantly smaller than the capacity of a single link as this is expressed by sG/C ... because of the correlations between successive arterial links, the creation of spillback queues and the effect of offsets ... congestion often occurs in the city centers with dense topology of short links" (Geroliminis & Boyacı 2012, §1). They find a drop up to 10% at G/C .6 with random offsets and no drop for G/C ≤ .3 (§5.2.1). **[S]**

### 5.3 Moving queues through the network

| Tool | Formula | Worked | Test |
|---|---|---|---|
| CTM (Daganzo 1994, 1995) | n_i(t+1) = n_i + y_i − y_(i+1). y_k = min(S_up, R_down). S = min(Q, n), R = min(Q, δ(N − n)), δ = w/v. Cell length = v·dt ([Daganzo 1995, eq. 2–4](https://escholarship.org/content/qt9pz309w7/qt9pz309w7.pdf)) | 50 km/h, dt 6 s: cell 83 m, N 11, Q 3 per step, δ .4. n 8: R = 1.2 per step = 720/h | N3 |
| LTM (Yperman 2007, via Boyles et al. §9.5.2, eq. 9.67 for R) | S = min(N↑(t + Δt − L/v_f) − N↓(t), qΔt). R = min(N↓(t + Δt − L/w) + k_j L − N↑(t), qΔt). Only link ends are computed, so long time steps are safe | One link, three parameters. Cheap: seconds for the whole district | N3 |
| Merge (Daganzo 1995, eq. 7) | y_k = mid{S_k, R − S_c, p_k R} | Target R 1,856, S 1,000 and 1,200, p .5: 928, 928 | N4 |
| Diverge, FIFO (Daganzo 1995, eq. 9) | y = min(S, R_E/β_E, R_C/β_C) | S 1,800, β_C .2, R_C 300: y = 1,500 | N5. Real multi-lane: only the blocked lane stops. Daganzo's footnote says so too. Use partial FIFO (Wright et al.) |
| General node (Tampère 2011) | Requirements: flows conserved, turn fractions kept, each flow actively restricted by a constraint, invariance under constant demand and supply, a supply constraint interaction rule. Read via [Wright et al.](https://arxiv.org/pdf/1707.09346) §2, not the original | For junction checks | N4, N5 |

**[I]** A CTM or LTM run on the map with fixed routes is arithmetic, not a second simulator to match. It is the theory solved. Its point: it computes the spill cascade the hand method can't. It takes seconds and can be run before every big test. It has no lane-change, gap or driver fault. So: **if LTM says a demand level is free of persistent queues and the micro run locks, the micro's junction or lane logic is at fault. If LTM locks too, the map and routes are at fault.** That is the separation the board has been missing.

### 5.4 Top of the network curve, from the map

**Method of cuts (Daganzo & Geroliminis 2008, §2.3).** Upper bound on network flow per lane at density k:

- q ≤ q_B = min S·G/C (stationary observer, eq. 3)
- q ≤ k·u(ε) + q_m·f(ε) (forward observer at u_f stopped on reds extended by εG, eq. 4b)
- q ≤ −k·w(ε) + q_m·b(ε) + r·w(ε)/w (backward observer, eq. 5b)
- Granularity: E(ρ) = ρ, var(ρ) ≈ ρ(1−ρ)/N_i; q ≈ E[Q(ρκ)] (eq. 7–8).

For real data see Yokohama: maximum at occupancy .3 and mean 13 km/h, hysteresis "notable for its absence" (GD 2008, §3). SF and Yokohama inputs are in Table 1 of DG 2008. My implementation (`cuts.py`) returns q_B 630 and 678/h as Table 1 implies, but I did not compare its full curves with their figures. **[I]**

**Inputs read from the map (box 49 km², m10):**

| Input | Value |
|---|---|
| Lane-km, all classes in box | 1,077 (22.0/km²). Whole net extends past the box: 1,415 |
| Trunk to tertiary incl. links (Loder's class) | 507.3 lane-km, R = **10.35**/km², 279.8 directed road-km |
| Motorway plus links | 71.1 lane-km |
| Junctions | 424 signals, 1,610 priority, 739 right-before-left |
| Signals per km of major-road route | 3.3 (303 m). All roads: 2.17 (460 m) |
| Cycle, G/C | C 90 s (one value, netconvert's). Flow-weighted G/C .46, link p10/50/90 .36/.47/.51 |
| Real G/C | Hamburg median .31, p90 .60 (earlier notes, not re-verified) |
| u_f, w, κ, S | 12.5 m/s (45 km/h on major), 5.4 m/s, 133/km, 1,800/h |

**Result per lane, random offsets:**

| Case | Top q, /h/lane | k from–to, /km/lane | Speed at start–end of plateau, km/h | Free running speed |
|---|---:|---|---|---|
| **Base l 300, C 90, G/C .45, S 1,800** | **810** | **36–73** | **22–11** | **29** |
| G/C .31 | 558 | 28–89 | 20–6 | 24 |
| G/C .60 | 1,080 | 42–60 | 26–18 | 34 |
| l 200 | 810 | 46–64 | 18–13 | 24 |
| l 460 | 810 | 30–80 | 27–10 | 33 |
| C 110 | 810 | 41–69 | 20–12 | 27 |
| C 70 | 810 | 32–77 | 25–11 | 31 |
| S 1,636 | 736 | 33–79 | 22–9 | 29 |
| S 2,000 | 900 | 41–67 | 22–14 | 29 |
| Green wave, offset l/u_f | 810 | 18–84 | 45–10 | 45 |
| Anti-wave, offset + C/2 | 810 | 52–60 | 16–14 | 16 |
| Granular, N 40 positions per link | 806 | peak at 55 | 15 | |

Reading **[I]**: **G/C sets the top. Length and offsets set the width and the free speed.** Cycle length has little effect. Offsets matter hugely below the top: free speed 45 against 16 km/h. Random granularity lowers the top by only 0.5% but moves the critical density from 36 to 55.

**Scaled to the district's major roads, D = 507.3 lane-km:**

| Quantity | Cuts (upper bound) | Loder regression (real data, 107 networks) | Reality, Berlin 2019 sites |
|---|---|---|---|
| P, veh-km/h | ≤ **410,900** | **262,000–318,000** | Demand from routes **[I]**: 230,500 at 07–08 h, 245,200 at 16–17 h |
| q per lane, /h | ≤ 810 | 516–627 | 396–455 (98 sites, 07–08 h to 16–17 h), p90 about 690, max 1,136 |
| N on these roads, cars | ≥ 18,466, plateau to 37,084 | **13,250–16,260** | About 455/37 × 507 = 6,200 |
| k per lane-km | 36–73 | 26–32 | 12 |
| V, km/h | 22–11 | **19.6** | 37–41 at detectors, 28–32 probes |

Loder form **[S]**: n* = −292.73 + 24.40R − 5.34R·I − 140.67b_c + 0.307B; P* = 1282.29 + 18.63n* − 6.64B (Table 1). Means in sample R 23.46, I .385, b_c .084, B 147; n* 653 ± 308, P* 12,236 ± 5,513; critical speed 18.8 km/h; critical accumulation up to a third of jam (detectors on trunk to tertiary only).

**[I] Correction to foundations/C and to the table's printed form.** With b_c as printed, the regression gives 265 at sample means, not 653, as C noticed. **With ln(b_c) it gives 625, and P* then gives 12,472 against 12,236. So b_c enters in logs.** The Table's label or the XML has lost this. I can't prove it from the paper alone. Using ln: n* = 353 − 55.3·I at R 10.35, B 147, b_c .084. I is ambiguous in the paper: .39 per lane-km over all classes, 1.5 per directed major road-km.

**[I] Second correction to C.** C line 39 gives Loder's critical point as 38,100 cars at 778/km², from 1,415 lane-km and an elasticity. Loder's R counts only trunk to tertiary inside the area. For the box R is 10.35, not 28.9. **The right estimate is 13,000–16,000 cars on major roads, 270–330/km²**, 2.4–2.9× lower than C. C's main finding stands anyway: 50% leaves the healthy curve at about 8/km/lane on these roads, a third of critical.

**Demand against the top.** Major-road demand at 100%, summed from `lane_load`: 230,500 veh-km/h at 07–08 h, 454/lane, against 396 measured, 15% high. 245,200 at 16–17 h, 483/lane, against 455 measured, 6% high. The peak is **60% of the cuts' bound and 77–94% of Loder's capacity**. Reality matches: it runs under critical, at 40–50% of k*. **So theory says 100% demand fits, narrowly. A healthy Berlin at 100% has no macroscopic reason to jam. Every lock we see must be local.**

Ambühl et al. 2020's smooth form q(k) = −λ·ln(e^(−uk/λ) + e^(−q_c/λ) + e^(−(κ−k)w/λ)) (formula from memory; I read only the abstract, [TR-B 137](https://econpapers.repec.org/RePEc:eee:transb:v:137:y:2020:i:c:p:119-132)) can turn cuts into a curve with one fitted parameter. It is a fit, not a prediction. I have no measured λ.

### 5.5 Given route flows: where queues form, how fast, when they spill

Steps. All are arithmetic on `net.net.xml` and `lane_load.csv.gz`. `screen.py` already does 1–5. It ran in under 2.5 minutes in this session on m12 with m10's load, 07–08 h.

1. Q_m for every movement = sum of route flows. Over any hour.
2. c_m from 5.2, with foe flows from step 1.
3. x from the Hall bound. Overflow = Q(1 − 1/x).
4. Queue growth = overflow. Tail speed = u from §1, per lane. Time to spill = lanes·L/s / overflow.
5. Sort by time to spill. The top of this list is the first seed of any lock.
6. Past first order: spilled queues cut upstream discharge and cut arrivals downstream. Run LTM to do this.

**Results, m12, 07–08 h (S 1,800/1,285/1,600):**

| Demand | Approaches loaded | x > 1 | By control | Overflow, veh/h | Spill under 15 min | Under 5 min | Median spill, min |
|---|---:|---:|---|---:|---:|---:|---:|
| 50% | 7,909 | **22** | 13 signal, 9 priority | 3,562 | **12** | **4** | 11.5 |
| 100% | 7,909 | **315** | 195 signal, 119 priority, 1 rbl | 95,269 | **227** | **148** | 5.5 |

Saturation is not what decides this: at 100%, S 1,636 gives 355, flat 1,900 gives 265. At 50% it gives 22 and 14. By road type at 100%: secondary 125, residential 62, primary 55, tertiary 54. Median x is only .44 on signal approaches and .20 on priority approaches.

**Worked example.** Karl-Liebknecht-Straße `318282850#0`, 50%: q 972, x 3.42, 3 lanes × 50 m = 20 cars, overflow 688/h. Spill in 1.8 min. By tail speed: per lane q 324, c 95, k₁ 6.5/km, k₂ 128/km, u = 1.9 km/h, 96 s. The two agree.

**[I] Paper prediction for 50%.** 3,562/h from 22 approaches, plus less in the hour before: about 2,000–3,000 cars above healthy by 07:30, before any spill. Measured: 14,792 − 7,015 = 7,777. So first-order overflow accounts for perhaps a third. With 12 spilling inside 15 min, the rest is plausibly cascade. LTM can test that directly.

**[I] The biggest overflows point to map errors.** Four of the top priority-coded clusters at 50% are main-road through movements that give way in the net, where OSM shows signals: Karl-Liebknecht / Spandauer (13 signal nodes within 70 m), Rubensstraße / Innsbrucker Platz (4), Straße des 17. Juni at Ernst-Reuter-Platz (18), Von-der-Heydt / Klingelhöferstraße (5). Overpass query, earlier session. Across m10, 13 through movements on primary, secondary or trunk with over 300 veh/h at 50% are coded to give way, e.g. Straße des 17. Juni 1,092, Hardenbergstraße 894, Hauptstraße 762, Bismarckstraße 728. **Caveat:** a signal within 70 m is not proof that it controls that movement, and my negative control on 14 random priority junctions crashed, so I have no false-positive rate. These need one look each at an aerial or OSM. All 9 priority-coded approaches over capacity, these included, carry 1,852 of the 3,562 veh/h of overflow at 50%.

At 100%, priority-coded primary, secondary and trunk approaches alone are 31 with 21,507 veh/h.

### 5.6 Uneven density

| What | Source | Number | Use |
|---|---|---|---|
| Random spread | DG 2008 eq. 7: var(ρ_i) ≈ ρ(1−ρ)/N_i. CV 15–45% at ρ .3 for N 10–100 | N 40, ρ .3: sd .072, CV 24% | **[I]** Compare measured spread of link density in a run with this baseline. Spread far above it means structural hot spots, not randomness. Free to compute |
| Flow falls with spread | Mazloumian, Geroliminis & Helbing (2010, [arXiv](https://arxiv.org/pdf/1101.4771)): "no invariant MFD" at K ≥ 40 veh/km in their simulated grid; S (sd of link density) and full-link count F explain it. Geroliminis & Sun 2011, Knoop et al. 2012 via Leclercq & Geroliminis 2013 §1: "average network flow is consistently higher when link density variance is low" | Their numbers are from one simulator, so shape, not values | Plot P against N coloured by S on every district run |
| Route choice bends the curve | Leclercq & Geroliminis 2013: semi-analytic with parallel hyperlinks. Wardrop and logit below system optimum. Irregular signal example 27% below the stationary cut ("unrealistic" by their own words) | | Bound on what offset or timing errors can cost: up to about a quarter in that example |
| Not all networks show an MFD | Ambühl STRC 2017 ([PDF](https://strc.ch/2017/Ambuehl_EtAl.pdf)): Bern shows no congested branch in data; London, Zurich do. Madrid speeds fall | | Don't expect a clean fall at real demand |
| Rigid routes jam | Daganzo, Gayah, Gonzales 2011 | C covers it | C's test |

### 5.7 Tests on small scenes

| Test | Scene | Theory says | Closeness |
|---|---|---|---:|
| N1 | Ring street of 8 signals, l 123 m, C 60, G 21, δ 2.6, u_f 13.4, w 5.4, κ 130, S 1,800 (SF, DG Table 1). No turns. 10 densities | q_B 630. Plateau k 30–48 by my cuts. Zero at 130/km | 5% on the top. Range 20% |
| N2 | Same with l 300, C 90, G 40.5, offsets wave and anti-wave | Free running 45 and 16 km/h. Top 810 | 5% |
| N3 | Link 200 m, 2 lanes, into one lane with c 720/h. Inflow 800 | 53 cars of storage, fill 40 min, tail about 0.4 km/h. LTM run matches | 15% |
| N3b | Same with inflow 1,200/h, 400 m, c 810 | 107 cars, 16 min, tail 1.9 km/h | 15% |
| N4 | Merge. Both saturated, p .5 | 928 each. One at 300: other takes 1,556 | .1 share |
| N5 | Diverge. Single lane, exit capacity 300, β .2 | Total 1,500. With exit closed: 0 on one lane. On a 3-lane approach with a dedicated turn lane: only that lane stops | 10% |
| N6 | Any scene | Conservation, Edie, dN/dt | Exact, or 10% for P/l |
| N7 | Closed grid, rigid routes (C's test) | C's numbers | C |
| N8 | Berlin run outputs against the screen, not a new run | x under .85: no persistent queue. x over 1: growth Q − c within 25% until spill | Per approach |

## 6. Where theory fails or is only approximate

| Scale | Claim | How it fails | What to do |
|---|---|---|---|
| One lane | One T, one s | Duret: pair by pair w ranges 0.5–13 m/s, s from under car length to over 10 m. Cassidy & Windover via Duret: drivers keep individual headways. Real p5 raw gap 0.4–0.9 s (report 19). The formula is for means | Test means. Test spread separately, against data, not theory |
| One lane | Triangular Q(k) | Fails near capacity: no capacity drop, no bounded acceleration. "Hydrodynamic theory does not offer any mechanism" for stop-and-go (Xuan & Coifman). Jin 2013: the drop needs an extra entropy condition | Don't test stop-and-go against LWR. Test wave speed and period against Treiber & Kesting data |
| One lane | w = s/T | Start wave 22.3 km/h with n 22 versus 15–20 km/h on motorways. Could be real: start-up delay per car may be shorter than the following T. Not settled | Band 16–28 km/h, report 04 |
| Signal | Webster | Partly fitted to simulation, steady state only, Poisson only. Blows up at x → 1 | Akçelik or fluid near and above x = 1. Tolerance 15–25% |
| Signal | Fixed S | Varies "cycle by cycle" (STM). HCM's "from car 4" hasn't reached steady state by Newell plus finite acceleration (§2). Short queues never reach it | Compare the whole headway curve (S2), not one number |
| Signal | Arrival | Formulas assume random arrivals. Real arrivals are platoons from upstream. Ch. 9 §9.5 has platoon factors, not read in detail. Uniform delay can halve or double with offset | Isolated scenes only for S tests; N2 for offsets |
| Give-way | Constant t_c, t_f, exponential major | Distributions lower capacity, realistic headways raise it, about cancelling (Grossmann, ch. 8). But a give-way **below an upstream signal** sees bunched gaps, and exponential is then wrong by a lot **[I]** | Test exponential first. For network, measure major headways |
| Give-way | No waiting effect | Polus: t_c falls .45 s per 30 s, roundabouts. C reports contrary results at other sites | Use C's measured targets. Don't put impatience in the formula until measured |
| Give-way | Priority obeyed | Formula has no forced entries, no courtesy, no priority reversal at high flows. German RVL model is unverified by its own author | Above q_p about 1,000 treat the formula as a floor |
| HBS, HCM | Norm values | Engineering values for design, on a safe side. BASt V324: real effects of heavy vehicles, gradient and radius are weaker than HBS | Treat as a ±15% band |
| Lane change | §4 gap formula | **Mine, not published as such.** Omits courtesy, speed adaptation, lead and lag separately. Real I-80 outperforms it. Merge split is a separate rule from gap acceptance, and no source joins them | A floor. Target real waits (LC8) |
| Lane change | HCM weave | Freeway only. STRIDE J5 questions its validity | Cross-check only |
| Network | Cuts | Upper bound, "not tightly" (DG §2.3). Homogeneous street, no turns. Real networks carry turns and pockets. Loder sits at 64–77% of the bound here | Require run under the bound, near Loder's. Never above the bound |
| Network | Loder | Regression, R² .88–.91, ± 47% scatter by C's reading. Detectors, biased near signals (Ambühl 2017 §methods). Means over cities, not this city. b_c form inferred. B and b_c not measured for Berlin | Use as a band. Compute real b_c from the map |
| Network | MFD itself | Needs homogeneous density. Depends on route choice (Leclercq & Geroliminis). Yokohama no hysteresis, others yes. Bern no congested branch | MFD is a description, not a law. Local screen comes first |
| Network | Little, P/l | Needs window longer than trip. Trip length l changes with congestion | Use differential form, measure l |
| Network | Screen §5.5 | First order: no cascade, no route change, fixed foes. Foe flows include what can't arrive. Short flares and turn pockets absent. Real G/C unknown for Berlin (C 90 is netconvert's) | LTM for cascade. Real timing from Hamburg or Berlin when available |
| Network | Spillback, gridlock | Theory says rigid routes eventually lock (C). Real drivers adapt. Timescale isn't predicted by what I read | C's test |

## 7. Sources

**Read, at least the cited parts:**

- Monograph (Gartner, Messer, Rathi, eds., Revised Monograph on Traffic Flow Theory, FHWA): [ch. 2 Hall](https://www.fhwa.dot.gov/publications/research/operations/tft/chap2.pdf), [ch. 5 Kühne & Michalopoulos](https://www.fhwa.dot.gov/publications/research/operations/tft/chap5.pdf), [ch. 8 Troutbeck & Brilon](https://www.fhwa.dot.gov/publications/research/operations/tft/chap8.pdf), [ch. 9 Rouphail, Tarko, Li](https://www.fhwa.dot.gov/publications/research/operations/tft/chap9.pdf). Webster, Tanner, Harders, Siegloch, Troutbeck, Akçelik are read through ch. 8 and 9, not in the original.
- [FHWA Signal Timing Manual, HOP-08-024](https://ops.fhwa.dot.gov/publications/fhwahop08024/fhwa_hop_08_024.pdf), §3.3, §6.
- [Daganzo 1995, CTM network](https://escholarship.org/content/qt9pz309w7/qt9pz309w7.pdf). Equations were images; I took the forms from its text.
- [Daganzo & Geroliminis 2008](https://escholarship.org/content/qt4cb8h3jm/qt4cb8h3jm.pdf). [Geroliminis & Daganzo 2008, Yokohama](https://escholarship.org/content/qt1b07t4q7/qt1b07t4q7.pdf). [Leclercq & Geroliminis 2013](https://infoscience.epfl.ch/record/188334/files/Lecl_Gerol_2013.pdf?version=1), parts. [Geroliminis & Boyacı 2012](https://infoscience.epfl.ch/record/182812/files/Gerol.Boyaci_2012.pdf?version=1), parts. [Mazloumian, Geroliminis, Helbing](https://arxiv.org/pdf/1101.4771), parts.
- [Loder et al. 2019](https://www.nature.com/articles/s41598-019-51539-5), [Table 1](https://www.nature.com/articles/s41598-019-51539-5/tables/1). [Ambühl et al. STRC 2017](https://strc.ch/2017/Ambuehl_EtAl.pdf), parts.
- [Laval & Daganzo working paper 2004](https://escholarship.org/uc/item/8w70q261), §3–4. Published as TR-B 2006. [Jin, kinematic wave of lane changing](https://arxiv.org/pdf/math/0503036). [Jin, Gan, Lebacq, capacity drop](https://arxiv.org/pdf/1310.2660). [Xuan & Coifman 2012](https://www.ocf.berkeley.edu/~xuanyg/doc/Xuan_Coifman_2012_JTE.pdf), abstract and introduction.
- [Duret et al.](https://www.ectri.org/wp-content/uploads/2019/01/Duret_A_Session3_Traffic2.pdf), [Treiber & Kesting, waves](https://arxiv.org/pdf/1008.1639), [Wikipedia on Newell](https://en.wikipedia.org/wiki/Newell%27s_car-following_model).
- [Polus et al., waiting time](https://journals.open.tudelft.nl/ejtir/article/download/4329/4227). [Wu 2003, right before left](https://homepage.rub.de/ning.wu/pdf/RechtsVorLinks_SVT_78_2003.pdf). [WisDOT TEOpS 16-15](https://wisconsindot.gov/dtsdManuals/traffic-ops/manuals-and-standards/teops/16-15.pdf). [HCS TWSC guide](https://mctranswordpresssa.blob.core.windows.net/uploads/2022/01/TWSC.pdf). [KNOBEL form, HBS 2015 S5](https://www.muenchberg.de/buergerservice/stadtbauamt/bauleitplanungen/aktuelle-bauleitplaene/23-10-19-anlage-s-4-variante-1-qsv-kreuzung.pdf?cid=j4s). [Brilon, VSVI deck on HBS 2015 S5](https://silo.tips/download/hbs-l5-s5-knotenpunkte-ohne-lichtsignalanlage-vorfahrt-werner-brilon). [Boyles et al., Transportation Network Analysis](https://arxiv.org/pdf/2502.05182), §9. [Wright et al., node models](https://arxiv.org/pdf/1707.09346), §2. [STRIDE J5](https://stride.ce.ufl.edu/wp-content/uploads/sites/153/2023/06/STRIDE-J5_Final-Report-2023.pdf). [MikeOnTraffic](https://www.mikeontraffic.com/hcm-6th-edition-roundabout/). [KnotenCheck](https://github.com/pnfzygrzgf-svg/KnotenCheck), a third-party reading of Swiss norms. [Ardekani & Herman](https://library.ctr.utexas.edu/digitized/TexasArchive/phase2/304-1-summary-CTR.pdf).
- Search snippet only: [BASt V324 record](https://trid.trb.org/View/2573179), [Ambühl 2020 abstract](https://econpapers.repec.org/RePEc:eee:transb:v:137:y:2020:i:c:p:119-132).
- Repo: reports 04, 14 (via C), 19, 22, 23, `foundations/C`. Map `cars-data/berlin2019/district/m10`, `m12`. Scripts `/tmp/foundations-b/scripts/` (`cuts.py`, `screen.py`, `net_stats.py`, `demand.py`, `real.py`, `numbers.py`, `through_m.py`, `overpass.py`) and `scripts2/`. Files in `/tmp` won't last; copy them into the repo if the screen and cuts become gates.

**Not reached, or second-hand only:**

- Books: Daganzo's *Fundamentals of Transportation and Traffic Operations*, Treiber & Kesting's *Traffic Flow Dynamics*. Neither is open. Their results reach this file only through papers.
- HCM and HBS directly. Numbers come from software guides, a DOT manual and a norm user's output. I could not read HBS S4 (signals) at all; the 2,000/h base comes from a BASt summary.
- Originals: Newell 2002, Webster 1958, Edie 1963, Tampère 2011 (via Wright), Yperman 2007 (via Boyles), Daganzo 1994.
- Capacity drop empirics: Hall & Agyemang-Duah 1991, Cassidy & Bertini 1999, Chung, Rhee & Cassidy 2007, Yuan et al. 2015 (site refused the download). All via Jin 2013 and Laval & Daganzo.
- Geroliminis & Sun 2011 (empty download), Knoop (via Leclercq & Geroliminis). Ambühl's 2020 formula is from memory.
- Measured lane-change gap acceptance (lead, lag, by flow). Needed as h in §4. NGSIM could supply it: Coifman & Li 2017 warn its raw trajectories have serious errors, so re-extract first.
- Real Berlin signal timings, so all signal numbers above are for netconvert's programs.
