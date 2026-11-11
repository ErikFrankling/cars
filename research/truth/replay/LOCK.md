# Why pNEUMA areas lock with every car simulated: lock chains and counterfactuals

7-11 November 2026. Forecasts F900-F915 in `foundations/forecasts.csv`, each written before its run. Tools: `scripts/replay/lock_chain.py` (holds, timeline, one car tick by tick), `lock_heads.py` (what holds the head of each lane), `lock_flow.py` (cars leaving each edge per 90 s, simulation against recording), and four new `--why` probes that name why the junction arbiter held a car (below). Runs: main's driver, dt 0.25, 5 seeds, GPU. Scenes and runs in `cars-data/replay/pneuma/scene-d{8,6}-20181029-0900[-variant]/` and `cars-data/replay/lock/`.

## The answer

There is no single first cause. Each of the four locks traced starts at a different thing that differs from the recording, and each repair is real but worth only a few points. Under them sits one finding that none of them touches: **Patision south, simulated alone on an otherwise empty net with its read signals, carries 62 % of the recorded flow** (F913). That flow is about 40 % of the lanes' capacity at the read greens. The corridor has nine junction nodes in 250 m (J60, J15, J69, J4, J75, J42, J0, J26, J41), and its cars are held there by conflict zones between Patision's own paths inside the boxes, by tails standing in 16 m internal lanes, and by lane changes on 30 m edges. That is junction-chain geometry and the driver, not other traffic, replay or signals.

| Run | Drone 8 entered | Travel time MAE | Approach delay MAE (floor 1.5-2.3) | Route travel time MAE (floor 7.6-10.9) |
|---|---|---|---|---|
| F524, before | 39-41 % | 106-134 s | 89-112 s | 92-142 s |
| F914, fixes kept | 52-55 % | 91-108 s | 68-78 s | 72-100 s |

| Run | Drone 6 entered | Travel time MAE | Approach delay MAE | Route travel time MAE |
|---|---|---|---|---|
| F525, before | 43-45 % | 138-188 s | 104-141 s | |
| F915, fixes kept | 49 % | 109-143 s | 65-72 s | 87-111 s (5-7 routes) |

Both are still 30-50 times the noise floor on approach delay and 7-15 times on route travel time.

## The lock chains

Seed 0, traced with `--why`. "First" means the first car held over 60 s, not at red, that is part of a lock that never clears.

**1. J54, Metsovou into Patision north (drone 8).** Car 31_54 stands at the Metsovou line from the first second to the end (990 s), `exit_full` on lane 0 of 1447239028#0. The net connects the one lane of Patision north (243850915) only to lane 0 of the next edge, so the whole Patision stream queues in the lane the Metsovou right-turners need, and Patision has priority. In the recording 116 of 118 Patision cars took lanes 1-2 there, and the 13 Metsovou cars stood 3.6 s on average (max 25 s). First cause: **the net's lane mapping** (class a). Gone with the recorded mapping (F901).

**2. J60, Patision south at Gkyilfordou (drone 8).** Car 159_274, head of Patision lane 0, stands 60 s at a green from the start. The arbiter holds it: a replayed motorcycle (165_284) stands 42 s on Gkyilfordou's right-turn path inside the box and holds a conflict zone. The net makes Patision lane 0 merge with Gkyilfordou into lane 0 after J60; real cars moved one lane left at J60 (124 of 191 from lane 0 went to lane 1), leaving the new kerb lane to Gkyilfordou. First causes: **a replayed vehicle standing where real cars passed it** (b), on **a lane mapping that creates a conflict reality did not have** (a).

**3. J75 and J69, Patision south below Alexandras (drone 8).** Patision south passes 10-20 cars per 90 s through J69 and J75 against 48-71 recorded, from the first 90 s on, while its stop-line queues are short (0.5-2 standing per lane): the lights are starved. Following it upstream led through a sequence of holds, each repaired in turn (below): yellows of 9-20 s per cycle from a bug in the signal programs (F902), a keep-clear wait at J15, a node with no conflicting movement (F904), two standing heads at J69 that livelocked over a merge zone while every lane ahead was empty for 255 s (F912). None of them restored the flow, and the isolations (F909, F913) show why: the corridor alone carries 62 %. Class (a) first, then (e).

**4. Omonoia square (drone 6).** Car 152_334 stands 888 s behind replayed motorcycle 101, which the recording has standing 900 s at the centre of Omonoia's kerb lane (24218743_0, lateral offset 0.12 m, so on the car path). In the recording 108 cars passed it inside that lane (median offset −1.15 m). In the simulation it closes the lane for the run. First cause: **a replayed vehicle standing where real cars passed it** (b). Not repaired (open, below).

None of the four starts at an unread link (c), as F900 forecast.

## Counterfactuals

Each removes one cause on top of the previous kept state, 5 seeds, drone 8. "Entered" is the share of 1,845 simulated cars that get in; the recording has all of them.

| Line | Change | Forecast entered | Result | Verdict | Kept |
|---|---|---|---|---|---|
| F901 | Recorded lane mapping (22 edge pairs, 2,730 recorded movements the net sent to another lane) | 55-85 % | 45-46 %, end-of-run stuck heads 24 → 1-8, J54 lock gone | miss | yes, scene default |
| F902 | Signal programs written right | 60-90 % | 41-43 % | miss | yes, a bug |
| F903 | Both | 70-95 % | 48-50 % | miss | yes |
| F904 | Keep-clear only on links with foes | 60-85 % | 49-50 %; J69 Patision 148 → 184 | miss | yes |
| F905 | Bus lanes opened where 20+ recorded cars drive (12 lanes, 491 vehicles, 23-61 % taxis) | 60-80 % | 49-52 %; Alexandras west at real flow for 6 minutes, then held from J69 | miss | yes, scene default |
| F906 | All replayed vehicles removed (sizing) | 65-90 % | 55-60 %; Patision through J69 unchanged | miss | no (sizing) |
| F907 | Unread links get the complement of their read foes | within 5 points | 46-50 %, Alexandras through J62 collapses (Mavromataion's read is doubtful) | partial | no |
| F908 | Crossing greens separated by a 3.5 s intergreen | 60-80 % | 48-51 % | miss | no (option `ig`) |
| F909 | Patision south alone simulated, rest replayed | 85-100 % of 637 | 34-36 % | miss | no (isolation) |
| F910 | Standstill gap 1.7 m (sizing) | 55-70 % | 51-53 % | miss | no (driver's) |
| F911 | Crossing zones released by rear gap (`zone_time=2`) | 55-75 % | 51-55 % | miss | no |
| F912 | A standing head keeps the zone it won | 65-90 % | 51-54 % | miss | yes, narrowed (below) |
| F913 | Patision south alone on an empty net | 95-100 % of 637 | 66-72 %, J69 387 of 629 | miss | no (isolation) |

Signals: two rounds without gain (F907, F908), stopped by rule 9. What the signal work did find, and keeps as numbers for anyone who reads pNEUMA signals again: crossing read greens overlap on 13 of 14 conflicting pairs on drone 8 (0.7-52 s a cycle) and 20 of 20 on drone 6 (0.8-35 s), and approaches of one controller read slightly different cycles (Mavromataion 89.18 s against Alexandras 90.03 s at J62), which drift 9 s over a run.

## What changed

**Harness and scene** (`scripts/replay/pneuma_scene.py`):
- **Signal programs** (bug): change points were rounded to 0.1 s while each phase's state was taken 1 ms after its rounded start against unrounded bounds. A phase whose bound rounded down took the previous state for its whole length: yellows of 9-20 s a cycle, and whole greens turned red (J74 Patision north had 42 % green against a read 75 %, J41 Patision south 43 % against 76 %, J62 Alexandras 48 % against 72 %). Bounds are now rounded first and each phase is sampled at its middle. Every T3 result before this (F524, F525) ran on the broken programs.
- **Recorded lane mapping** (default; `nolanemap` turns it off): for every pair of edges with 20+ recorded car movements, each from-lane is connected to the to-lanes that 3+ cars and 15 %+ of its movements took. netconvert lines lanes up from the kerb; drivers keep their lateral place where lane counts change. Drone 8: 22 pairs, 16 connections deleted, 38 added. Drone 6: 28 pairs, 23 deleted, 51 added.
- **Lanes opened where recorded cars drive** (default; `noopen`): a lane the net closes to cars is opened when 20+ recorded cars, taxis, medium or heavy vehicles drive on it. Drone 8: 12 Alexandras bus lanes. Drone 6: none.
- **Options for counterfactuals**, each its own scene folder: `--variant=` with `ig` (F908), `unread` (F907), `only=EDGE,...` (T2 isolation, F909), and the command `tls` that rewrites only a scene's signal programs.

**Kernel** (`step.wgsl`, `ph_bid`), both junction logic:
- **Keep-clear only where the link has foes.** The physical arbiter held a car before a box whenever the far side lacked room, even at nodes where no movement conflicts (J15 on Patision south). SUMO's `checkRewindLinkLanes` and our own Krauss path ask for `hasFoes() && keepClear()`; `ph_bid` now asks the same of the junction's entry link.
- **A tie goes to the car that won last step and still stands.** The tie-break hash changed every step, so two standing heads tied in rank and arrival each won every other step; a lost step restarts the start reaction (`ph_start_hold`), so neither went. Traced at J69 on F906's scene: Patision lanes 0 and 1, whose paths merge into lane 0 after J69, plus an Alexandras head, held 255 s with every lane ahead empty. Such a car now bids the lowest tie-break value (2). Bids that do not tie are ordered as before. A first version gave such cars rank 1, which also let them beat bids of higher priority; it changed plain runs where nobody tied and was narrowed (F912's runs used it; F914 and F915 use the narrowed rule).

**Debugging**: `--why` names why the arbiter held a car when no foe closed the link: zone taken by a foe lane (1), onward zone of a stub taken (2), no room past it (3, keep-clear), lost the bid to a zone foe (4). Word 11 of the record, code in the top 3 bits (`why.wgsl` `why_deny`, probes in `why.rs`). `cars why` prints it as "arbiter held it". Before, these holds showed as `yield` with no foe, or as `accel` and `dawdle` when a start reaction was reset.

## Plain runs and T0

- `plain_identical.py` (the small junction scene of `test_debug_tools.py`, llvmpipe, 5 runs each): main's kernel and this branch's give the same bytes (one hash, `5d5104a0ef1f`, in all 10). The keep-clear change and the narrowed tie rule alone each give it too. The first, rank-1 version of the grant rule did not (`83d8f50220d2`).
- These are junction fixes meant to change traffic where they act, so plain runs differ wherever a node with no foes holds a car outside its box, or two standing heads tie for a zone.
- T0 junction and signal rows (G1-G9, N1-N10, C-S7, C-S8, S1-S8; 116 lines), dt 0.25, physical driver, GPU, one binary with main's shaders and with this branch's: **78 pass with main's, 76 with this branch's.** Lines that move:

| Scene, line | Main | Branch | Which change |
|---|---|---|---|
| N3 bottleneck discharge (built for 720 veh/h) | 60 | 590 | the tie rule (564 with it alone; keep-clear alone 0) |
| N3 F029 storage at spill, forecast 51.2 cars | 45.2 pass | 38.2 fail | the tie rule |
| N3 F029 time to spill | fail | fail | |
| N3b discharge (built for 810 veh/h) | 156 | 647 | the tie rule (732 alone; keep-clear alone 84) |
| N3b F271 storage at spill, forecast 105 | 95 pass | 86 fail | the tie rule |
| N3b F271 time to spill | pass | fail | the tie rule |
| N3b F271 tail speed | fail (none) | pass | the tie rule |
| N5 F273, F404, F275; N6 F276; G5 F259; N10 F049 d | | within their spread, verdicts unchanged | |

Main's N3 and N3b bottlenecks show J69's livelock in a test scene, by every sign though not traced there: the tie rule alone restores them, and before it the bottleneck passed 60 and 156 veh/h of the 720 and 810 it was built for. Their storage and spill rows passed on that. With the bottleneck discharging, the queue spills while it still moves and stores fewer cars than 2 lanes x length x kj; those forecasts assumed a standing queue and need a second look (scenes log section 8).

## For the other agents

- **Lane changes** (not changed here): on Patision south's 30 m edges between J60, J15 and J69, heads stand 52-127 frames per 300 with `lane_change` as the decider (F913's empty net, seed 0), and 192-218 cars per run miss a turn on drone 8. The scene: `scene-d8-20181029-0900-lanemap+open+only=1447459732+empty`, `lock_heads.py` on edges 1447459732,661184019,390115233#0.
- **Car following and start from rest** (not changed here): the standstill gap is not what limits these corridors (F910: 1.7 m instead of 2.5 m gains 1-2 points). Where cars do leave a lane on Patision south, they leave at a median of 2-3 s apart (F905's scene, seed 0), so the discharge of a moving queue is not the limit either. What the empty-net scene leaves open is whether a start from rest repeated at up to nine nodes in 250 m, each with a reaction (`ph_start_hold`), costs real drivers as much; that is for the following-law agent to test on this scene.

## Open

- **Replayed vehicles standing where real cars passed them.** Two of the four chains start there (J60, Omonoia). A rule to try: a replayed vehicle that stands while recorded cars pass it inside the same lane leaves the car path for that time (counted, as F521 does for filtering). Not built.
- **The junction chain itself** (F913). The next step is a T2 test of Patision south alone on drone 8 with the conflict zones between paths of one approach examined one by one: which zones between parallel or merging internal lanes of one approach exist in reality, and how a queue stores through 16 m internal lanes.
- **The lane mapping after a 0.2 m stub edge.** Most recorded movements after J69 are matched straight onto 758432181#1, past the 0.2 m 758432181#0, so the mapping there rests on 62 movements and keeps a merge of lanes 0 and 1 into lane 0 that the recording probably does not have.
- **Signal reads** with overlapping crossing greens and per-approach cycles that drift.

## Rerun

```sh
source /home/erikf/projects/personal/cars-data/dev-env.sh; cargo build --release -p cars-cli
# scene builds read 1-2 GB from the pNEUMA zip: run them alone, under nice -n 15 ionice -c3
python3 -I scripts/replay/pneuma_scene.py build 8 20181029 0900          # recorded lane mapping and opened lanes by default
python3 -I scripts/replay/pneuma_scene.py mix 8 20181029 0900            # F914
python3 -I scripts/replay/pneuma_scene.py build 6 20181029 0900 && python3 -I scripts/replay/pneuma_scene.py mix 6 20181029 0900   # F915
# counterfactuals: --variant=nolanemap+noopen, ig, unread, only=1447459732; tls rewrites a scene's programs; mix takes --tune=K=V
python3 -I scripts/replay/lock_chain.py holds TRACE ROUTES --min 60        # first held cars
python3 -I scripts/replay/lock_heads.py TRACE EDGE,EDGE --all-states       # what holds each lane's head
python3 -I scripts/replay/lock_flow.py SCENE_DIR FCD --edges E1,E2         # flow per edge against the recording
```
