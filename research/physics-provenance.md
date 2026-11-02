# Where every rule and number in physical mode comes from

Classes as in `research/truth/15-how-the-best-simulators-do-it.md` Part 2. **ESTABLISHED**: a named source does the same. **ADAPTED**: a named source, changed as stated. **INVENTED**: no source found, so it is a parameter with a switch or `--tune` name and a sensitivity test in `scripts/physics_sensitivity.py`. Short labels are links in that report's register; `11` is `research/truth/11-vehicle-physics.md`.

## Motion

| Rule or number | Class | Source, and what changed | Switch |
|---|---|---|---|
| Ballistic position update | ESTABLISHED | Treiber & Kanagaraj [ti], CityFlow [cf], SUMO's ballistic option | |
| Force balance, power and tyre limit, midpoint evaluation | ADAPTED | Long 2000, physics textbook form; midpoint from 11 §2.2 | |
| Vehicle mass, power, CdA, Crr tables | ADAPTED | 11 build table: some measured, most design values. No Swedish fleet data | `phys.*` on the vType |
| κ 0.775 / 0.83 fit | ADAPTED | Fitted in 11 to five declared 0-100 times | `phys.kappa` |
| Load and power drawn per vehicle | INVENTED ranges | Per-vehicle draws are universal in tools [vwm] [am]; the ranges are design values | table in `world.rs` |
| Driver acceleration a = 2.02 − 0.125 v, floor 0.7 | ADAPTED | Long 2000 measured at signals; floor is ours | `phys.a0`, `a1`, `a_floor` |
| Truck and bus a_des | ADAPTED | Yang 2016 measured for trucks; bus under Krašna's limit, design value | `phys.a0` |
| Driver gap law behind what moves, own braking b and assumed leader braking b̂ | ESTABLISHED | Gipps 1981, the core of Aimsun's model [am]; the ballistic form from SUMO's MSCFModel | model per vType |
| Stopping for what stands, or where a slowing leader comes to rest: v = 1.2 d^0.6, assuming the leader slows at 1.3 | ADAPTED | Form ours, fitted to report 19's real stops: mean 1.32, peak 2.23, little change with speed. Replaces b = 3 in stops. Report 19 asked for b 1.3 with a bell peaking at 2.2; this is a stateless form of that | |
| τ 0.65 s, b 3.0, b̂ 4.5 m/s² | ADAPTED, weak | Fitted to TRVMB's design flows 1,900 and 1,700. Report 19: a fit to design flow, not to braking. Now only behind moving leaders | `tau`, `driver_b`, `leader_b` |
| Certificate: closed-form safe speed, brake ramp, min(b_F, b_L) | ADAPTED | Gipps core [am], RSS [rs]; ours adds the ramp and response inside the tick. 11 §5 | `certificate` |
| Stop inside a step, release limit | ADAPTED | Consequence of ballistic plus ramp, 11 §5 | |
| Margin 0.5 m in the certificate | ESTABLISHED | Vissim MinClear 0.5 m [vlc] | |
| Brake limits b_lo, b_hi | ADAPTED | ADAC, NHTSA, Altoona as graded in 11. Car b_lo 8.3 is ADAC's worst tyre on dry, in place of 11's design value 7.0, which took capacity at dt 1 with no measurement behind it | `car_b_lo`, `phys.b_lo` |
| t_r 0.30 / 0.45 / 0.47 s | ADAPTED | 0.45 regulatory, 0.47 one measured vehicle, 0.30 design | `phys.t_r` |
| Surface friction table | ADAPTED | ADAC measured low bound; high bound design value. Global, not per lane | `--surface` |
| Lateral limit 0.5 μ g, combined limit | ADAPTED | 11 I9, I10 | |
| Driver corner speed: v = √(a_y R) on the tightest radius, each driver's a_y lognormal, median 2.2, σ 0.30, hard cap 4.3 | ESTABLISHED | Report 19: 3,584 real turns in 4 cities, peak median 2.19, p95 3.53, p99 4.26, flat with radius. Replaces Xu and the 4.0 cap, which was chosen for flow | `lateral_median`, `curve_cap` |
| Radius never read below 5 m | ADAPTED | A modern car's turning circle, report 19. A geometry limit, not a speed floor | `physics.rs` |
| Curvature over 30 m on roads, 10 m on junction lanes | ADAPTED | Report 19 cause 2: road polylines carry kinks a car steers through. On a real 10 m bend it reads wide: 5.4 m/s against the fix's 4.7 and a real 4.1 | `physics.rs` |
| Tightest stretch 1.2 × lowest limit | INVENTED | How far around the tightest point the limit holds | sensitivity |
| Never drive further this step than stopping next step leaves room for | INVENTED | Without it, a reaction time under dt overruns the gap. Binds only at low speed at dt 1 | |
| Dawdling held for a whole second, per trip | INVENTED | Keeps σ's effect independent of dt, where SUMO's scales with dt (11 §6) | vType `sigma` |

## Junctions

| Rule or number | Class | Source, and what changed | Switch |
|---|---|---|---|
| Right of way, gap logic, rewind | ESTABLISHED | SUMO's MSLink, kept | |
| Conflict zones from lane geometry | ADAPTED | Vissim conflict areas [vca], CityFlow cross points [cf]; ours are computed from swept paths. 09's census | |
| No zone between lanes that lie side by side by their own widths, or that run in opposite directions at least 1.4 m apart | ADAPTED | SUMO has no foe there. On narrow two-way streets, with 1.6 m lanes in the OSM data, a zone was a head-on standoff that never cleared. Bodies there can touch in the detector; the fault is the lane width in the net | 1.4 m INVENTED, in `physics.rs` |
| No waiting on a stub too short for a body | INVENTED | Two such cars, each with its tail across the approach, stood in each other's way for good | |
| Zone reach 2.6 m centre to centre | INVENTED | Two wide vehicles plus a little | `zone_distance` |
| Real widths at run time, margin 0.1 m | INVENTED | | `width_margin` |
| Bid by class, then arrival, then hash; lowest wins | ADAPTED | Priority claims, as in the lane-change kernel and LPSim's atomic writes, order-independent | `arbiter` |
| Committed vehicles always win | INVENTED | Point of no return; 15 row 9 | |
| Critical gaps per movement, give way and stop, +0.9 s at 70 km/h | ESTABLISHED | TRVMB Kapacitet [trv]. Used from the moment the first vehicle has cleared | `tc_scale` |
| 1.2 s for the first vehicle to clear the conflict point | INVENTED | A body length and zone at 50 km/h, from the gap test | `tc_clear` |
| Claim distance: v dt + v²/2b + v τ + 2 | INVENTED | Where a driver would start slowing anyway | `claim_scale` |
| Occupied until the rear has passed the zone | ADAPTED | Vissim conflict area rear gap [vca], with gap 0 | |
| A body out of the zone 0.5 s before we arrive does not hold it, at merges | ADAPTED | Vissim rear gap default 0.5 s [vca]. Holding a merge until the rear had cleared cost 30% or more at a roundabout | `zone_time` |
| A body that can stop short of a zone does not hold it, and asks for it when it nears it | ADAPTED | Vissim conflict area status [vca]. Off: it locked more junctions than it freed | `zones_ahead` |
| Held vehicles release their right of way | INVENTED | Otherwise a car waits for one that waits for it | |
| Exit-clear rule | ESTABLISHED | Vissim avoid blocking [vca], Aimsun yellow box [an], SUMO [si] | `exit_clear` |
| Blocker under 75% of desired speed | ESTABLISHED | Vissim [vca] | |
| Blocker under 2 m/s | ADAPTED | Vissim says 5 m/s [vca]. Cars leave a tight turn under 5 m/s, and the rule then cost 20% of right-turn flow at dt 1 and locked a roundabout | `queue_speed` |
| Vehicles on a roundabout ring exempt from exit-clear | ADAPTED | SUMO's rewind check skips roundabouts; otherwise the ring waits for itself | |
| Room needed: length + 0.5 m | ESTABLISHED | Vissim [vca] | |
| Adding those ahead and those committed to the exit | ADAPTED | 15 row 8 | |
| Compliance share per vehicle | ESTABLISHED form | Vissim's percentage [vca]. TfL lists real blocking as behaviour to observe [tfl] | |
| Compliance value 90% for humans | INVENTED | No measurement found. Automated models 100% | `exit_comply` |
| Roundabout entries always comply | INVENTED | Ring locks whole otherwise, seen in the fixture | |

## Signals and fleet

| Rule or number | Class | Source, and what changed | Switch |
|---|---|---|---|
| Yellow: stop if time to the line is over the driver's threshold, logistic 5.1 s, scale 0.54. Past 3 m/s² needed, go | ESTABLISHED | Report 05, 1,357 decisions at Braunschweig; report 19 fix 9 | |
| Past the point of stopping when red comes, carry on | ADAPTED | Report 05 sees real red entries; the 3 m/s² is from the same rule | |
| Fleet 81% car, 12% van, 5% truck, 1% bus, 1% motorcycle, by trip | ESTABLISHED share, ADAPTED use | Trafikanalys Körsträckor 2025, by distance. Heavy trucks not split into rigid and articulated: no count found | `--region sweden` |
| Demand files' accel, decel, sigma, tau, minGap dropped | ESTABLISHED by audit | Thesis-era values with no source, report 19 fix 8. Under `--region` | |
| Car 4.5 m + 3.0 m, van 5.5 m + 2.5 m | INVENTED | Design values; spacing stays 7.5 m. Report 19 fix 16. No registry data found | `--region sweden` |
| Free speed over limit: 40: 0.98, 50: 0.90, 60: 0.85, 70: 0.89 | ESTABLISHED | VTI rapport 1001, mean of all traffic at mid-block, Sweden 2018. Sweden only | `--region sweden` |

## Lane changes

| Rule or number | Class | Source, and what changed | Switch |
|---|---|---|---|
| LC2013 decisions | ESTABLISHED | SUMO [lc], kept. Its known deadlock remains [st] | |
| Finite duration, 0.6 m/s, 1 s ends | ESTABLISHED | SimMobility [sm], field 5-8 s [ld1] [ld2] [rm], 11 §4.2 | `phys.v_lat` |
| 1.0 m/s when short of road | ADAPTED | Report 19 fix 13: real p95 1.26, was 1.1 | |
| Shadow on the old lane | ADAPTED | SUMO shadow lane [sf]; ours is a sorted clone, limit read in the same step | |
| Below 0.5 m/s a change goes on at its own 0.6 m/s, whatever the forward speed | ADAPTED | SUMO's lcMaxSpeedLatStanding exists for this; report 11's I11 forbids it. Held to the 12° limit a car in a crawling queue stays across two lanes, which was the main cause of city lockup: on a 2 km cut of the recipe net (seeds 1-6) a mean 2,130 of 3,001 trips arrived with the limit and 2,880 without, on the priority fixture at dt 0.1, 16 against 253. Any value from 0.5 to 2 m/s did. 0.5 is ours, the least that works | `lc_crawl` |
| A change finishes before its lane ends, and waits at the line if it must | ADAPTED | Bodies crossing a junction half in another lane were 18 of the 50 sampled contacts on that cut. Report 05's human driver does the same. Costs some flow | `lc_carry` |
| Heading limit 12° | ADAPTED | 11 §4.2, I11 | |
| Old-lane leader must leave the forward travel a change takes | INVENTED | Stops a change halting across two lanes | `lc_path` |
| No stopping for lane-change reservation while a change is under way | INVENTED | LC2013's blocker would hold the car at a stand, where it cannot finish | |
| Lane-change acceptance: the driver's gap law at factor 0.6 | ESTABLISHED | Vissim's safety distance factor during a change, 0.6 [vlc] | `lc_gap` |
| Certificate on target-lane gaps | ADAPTED | Vissim's cooperative gap is laxer, factor 0.6 [vlc]. Ours is the full certificate | |
| Claims on target-lane cells | ADAPTED | TRANSIMS, LPSim; 15 row 29 | |
| Reach of claim: certificate gap | INVENTED | Two changers side by side respect each other | |
| Not while the tail hangs on the previous lane | INVENTED | | |

## Checking

| Rule or number | Class | Source | Switch |
|---|---|---|---|
| Oriented-rectangle check, counts and never repairs | ESTABLISHED | SUMO shape overlap [ss], SSAM [ss03] | `--detect-every` |
| Depth threshold 0.02 m | INVENTED | Float noise | |
| Lanes count as related only if they share an edge or node | INVENTED | Keeps bridges out; can hide geometry faults | |
| Grid cell 20 m | INVENTED | Longest vehicle | |
| Removal after waiting on a wrong lane, counted, off by default | ESTABLISHED | Vissim at the emergency stop [vlc]. Aimsun's missed turn is the better form and needs rerouting | `lost_after` |
| Low-demand check, very low then 50%, teleports off | ESTABLISHED | Trafikverket [tvh], TRB primer [ec] | `physics_gate.py` |
| Stuck over 180 s counts | INVENTED | Above the cycles in these nets; no guideline gives a number | `--gridlock-after` |
| Waiting-cycle report by lane | ADAPTED | FHWA and TfL ask for no unrealistic gridlock; ours names where | |
| Saturation targets 1,900 / 1,700 / 1,500, 7.43 m | ESTABLISHED | TRVMB [trv], guideline design values, not measured there | `physics_tests.py capacity` |
| Critical gaps 4.8-5.3 s | ESTABLISHED | TRVMB [trv] | `physics_tests.py gap` |
| Siegloch capacity form | ESTABLISHED | Textbook gap acceptance, HCM family | |
| Follow-up 3.1 s | ADAPTED | Common 0.6 × critical gap; TRVMB gives no give-way value in what 15 read | |
| TTC under 1.5 s, PET, rectangles | ESTABLISHED | SSAM [ss6] [sb] | `physics_conflicts.py` |
| Type by angle 30° and 85° | ESTABLISHED | SSAM defaults | |

## Energy

| Rule or number | Class | Source | Switch |
|---|---|---|---|
| Wheel, brake, road and height work from forces | ESTABLISHED | Longitudinal dynamics, 11 I16 | |
| Electric 85% with 60% regeneration | INVENTED | 11 §2.3 calls them assumptions, checked against one declared figure | `physics.rs` |
| Combustion efficiency, idle power | INVENTED | Chosen to give about 6 l/100 km for the fleet-mean car on WLTC | `physics.rs` |
