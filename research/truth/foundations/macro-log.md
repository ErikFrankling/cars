# Macro log: rungs 3, 4, 5

Nobody contacted. No microscopic simulation, no GPU. Data in `cars-data/berlin2019/macro/`, scripts in `scripts/macro/`. Tuning sites and May 2019 only; locked sites and months not read.

Inputs: lanes ESTIMATED (OSM 2019, m17); signals INVENTED (netconvert structure); saturation MEASURED elsewhere (report 25, 1,285-1,895, not Berlin); give-way gaps from HBS; demand MODELLED (who, where, when, class from MATSim v6.4).

## Rung 3

Base map **m17** with table repairs: same edges as m12, has the 141 OSM signals and OSM 2019 turn and bus lanes. m12 at s 1640 has the same .13% one-way result, so the map choice does not rest on this test; m17 is chosen because it holds the measured 2019 facts.

Table repairs, each a named cause (`mt.repair`, log in `macro/m17/repairs_r.csv`). They live in the table, not in the net: `step2_lanes.py` should take the same rules before rung 6.

| Cause | Where | Effect |
|---|---|---|
| Detector lane index read as a lane of the map; a closed bus lane shifts it | 7 sites | Test counts the n best lanes |
| Tag `none` read as serving nothing, though it means no arrow | Schöneberger Ufer `left\|through\|none\|none`, others | Lane also serves straight on |
| Turn tag names a target not on the map, lane left with no way on | 55 connections restored, Tunnel Tiergarten `left\|through\|right\|right` | |
| Ramp or carriageway joining straight on read as a gap search | Bundesallee TE264: capacity 691 against 1,438 real; A100 ramps | Daganzo's merge |

Results: cuts first.

| Test | Result | Forecast |
|---|---|---|
| Cluster cuts k 2-16, peak hour against capacity + storage | 0 of 58 over; max peak/capacity .30 | F052 hit |
| Band min cut (400 m), k 2, 4, 8, s 1285, 1640, 1895 | 0 of 84 over; max v/c .61, .53, .49 | F055 hit |
| Real flow over a cut | 0 (few sites on cut links) | F053 hit |
| One-way, s 1640 | 16 of 11,948 site-hours, 2 sites: TE562 needs g/C .43, TE509 .44; both inside Hamburg's range, map programs are invented | F050 |
| One-way, s 1285 | 299, 9 sites; TE184 needs .69, TE370 .68, over Hamburg's p90 of .60 | F051 |
| One-way, s 1895 | 4, 1 site | F051 |
| Two-way at own stop line, s 1640 | median .56 | F054 miss |
| Two-way to the first signal straight on, s 1640 | median .62, 40 of 46 under .85, 1 over 1.1 | F056 miss |

Cut caveats: capacity sums each link's best movement with no shared green, so a pass is weak and a fail would have been proof. Gates are MATSim's until the region runs.

Two-way reading: real flow with a queue present is about 530 veh/lane/h at signal-bound sites. At s 1640 that is g/C .33. Hamburg's median is .31, the map's .46. So the map's invented greens are the leading cause, not proven: an hour flagged as queued may not discharge at saturation all hour, and a queue can be set further down. It gets re-tested on the rule below.

Audits: no signal connection without green, none under 5 s. Three main-road movements under 50 veh/h on screen foe flows, all permissive rights across heavy flow with almost no demand. Priority-coded through movements on main roads: 10 urban, one look each (`audit_prio_look.csv`), none has an OSM 2019 signal at the junction after m16; 7 are carriageways joining, 3 links crossing a road. Earlier suspects (Straße des 17. Juni, Hardenbergstraße, Karl-Liebknecht-Straße) are signals since m16.

Signal pairs under 50 m: 208 (`signal_pairs.csv`), 163 under 30 m, 166 on main roads, none on one controller, median storage 3.9 cars. Each gets one coordinated rule from Hamburg when the reality agent has measured it, fixed before any Berlin score.

Clean cross-sections: all 24 stations over 200 m from a calibration link are in the locked set (report 22's rule), 4 of them in the district. They are not read here. Macro writes their flows for the reveal.

## Rule fixed before any macro score (rule 8)

Signals, all 667 controllers, no site-level change, counts not used:
- Cycle 90 s 07-20 h, 75 s otherwise (Hamburg, report 26).
- Which movements share a stage: the map's program.
- Stage greens by equal degree of saturation on macro's own flows, per time block (06-10, 10-15, 15-19, rest), 7 s minimum, 4 s lost per stage.
- Saturation 1,640. Sweeps of s 1,285-1,895 and green share .31-.60 report sensitivity only.

Route cost: real free speeds per class from probes with junction delay left out; `β` residential and living street +.30, unclassified and tertiary +.10, other 0; perception noise σ .15 per edge and draw (D step 3, order of 10-20%). PCE car 1, van 1.2, trucks 2.
