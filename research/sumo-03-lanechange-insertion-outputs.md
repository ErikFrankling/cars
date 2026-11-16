# SUMO 1.28.0: lane changes, insertion, metrics and demand

Contains excerpts of the Eclipse SUMO 1.28 source code, Copyright (C) German Aerospace Center (DLR) and others, under the [Eclipse Public License 2.0](https://www.eclipse.org/legal/epl-2.0/).

Source root `S=/home/erikf/projects/personal/thesis-src/sumo/src`; docs root `D=S/../docs/web/docs`. The checkout reports tag `v1_28_0`. Citations below are relative to S unless prefixed D. Units: metres, seconds, m/s; `TS` is step length in seconds, `DELTA_T` in integer simulation ticks. `STEPS2TIME` converts ticks to seconds. Appendix algorithms are normative, line-numbered extracts: they supply the complete branch ordering and equations rather than requiring the implementer to open SUMO. Debug-only code and standalone comments are omitted; original line numbers are retained. C++ container operations translate directly to indexed arrays; car-following calls are contracts with the separately implemented car-following model, not constants to replace with a fixed gap.

## A. Lane changes

### Execution and safety

Process vehicles from downstream to upstream across an edge, selecting the largest position among current lane candidates. Keep processed leaders and hopped vehicles as well as the unprocessed followers: later decisions see earlier changes. Check right first, then left; a successful right change returns immediately. Continue an ongoing maneuver before ordinary decisions; stopped-on-lane, already-changed and inactive vehicles skip ordinary decisions (inactive vehicles can still obey TraCI). Adapt best-lane occupation to the lane changer's working densities before querying motivations. See complete scheduler, `change`, neighborhood resolution and safety algorithms in A1 (`microsim/MSLaneChanger.cpp:190-448,579-1167`).

`offset=-1` means right, `+1` left. Permission requires both target `allowsVehicleClass(vClass)` and source directional `allowsChangingRight/Left(vClass)`; adjacency and global edge changing permission also apply. Do not treat every lane of an edge as interchangeable (`microsim/MSLaneChanger.cpp:311-326`). Best-lane continuation construction separately checks vehicle permissions (`microsim/MSVehicle.cpp:6160-6201`).

A negative target front/back net gap sets the corresponding leader/follower blocked bit plus `LCA_OVERLAPPING`. Otherwise compare target gaps to the appropriate **follower's** car-follow model `getSecureGap`, multiplied by ego lane-change safety factor. LC2013 factor is `1/lcAssertive`; default assertive=1. For asynchronous action steps extrapolate speeds conservatively with `tauRemainder=max(headway-TS,0)` (zero for ordinary per-step actions). Additional checks include target continuation leaders, pedestrians and available distance for continuous maneuvers; preserve the exact A1 ordering (`microsim/MSLaneChanger.cpp:799-1167`; `microsim/lcmodels/MSLCM_LC2013.cpp:2080-2088`).

`getRealLeader/Follower` are not simple binary searches in the old target lane: they reconcile processed leaders, hopped vehicles, unprocessed candidates, partial occupiers and connected lanes. Gap conventions subtract the relevant follower minGap; retain body lengths separately for overlap checks. Exact algorithms A1 (`microsim/MSLaneChanger.cpp:579-779`).

Default `lanechange.duration=0` makes changes instantaneous; positive duration maintains source/target overlap and switches primary lane around the maneuver midpoint. `continueChange` advances lateral progress, registers shadow occupation and ends when complete. Changes update vehicle lane membership, move reminders, best lanes, lateral coordinates, maneuver state and lane-change model state; lane containers are replaced after the sweep. Do not only change a lane ID (`microsim/MSFrame.cpp:500-501`; A1 `MSLaneChanger.cpp:250-268,502-576`; A3 `MSAbstractLaneChangeModel.cpp:314-499`).

### LC2013 state and exact decision rules

LC2013 has four interacting motivations: strategic route/stopping continuity, cooperative assistance, speed gain, and keeping right. It is a discrete lane model; sublane continuous lateral positioning is a separate lane changer/model path. Direction, motivation, urgency and blocking are independent bit fields, not a single enum result. All flag values and masks are transcribed in A4 (`utils/xml/SUMOXMLDefinitions.h:2182-2260`). LC2013 cooperation bits (migrated into the public enum in this version) are also in A4. `wantsChange` wraps `_wantsChange`; preserve that wrapper, the state carried across steps, cancellation, and speed patching. A2 contains the entire model's behavioral implementation through `hasFreeLane`, including `informLeader`, `informFollower`, `slowDownForBlocked`, prepare/reset/change hooks and anticipation (`microsim/lcmodels/MSLCM_LC2013.cpp:48-2132`).

Core strategic equations (the exceptions and definitions of `currentDist`, `best`, `changeToBest`, stop distance, and internal-lane indexing are in A2):

```text
h = actionStepLengthSeconds
if speed > lookAheadSpeed: lookAheadSpeed = speed
else: m = 1 - (1 - 0.9)*h
      lookAheadSpeed = max(0, m*lookAheadSpeed + (1-m)*speed)
laDist = lookAheadSpeed*10*lcStrategic*(right ? 1 : lcLookaheadLeft)
         + 2*lengthWithGap
# negative lcStrategic overrides laDist to -1000
currentDist += roundaboutBonus; neighDist += roundaboutBonus
usableDist = max(currentDist - position - best.occupation*1, driveToNextStop)
urgentStrategic = changeToBest && bestLaneOffset == curr.bestLaneOffset
                  && usableDist/abs(bestLaneOffset) < laDist
leftSpace = currentDist - position
remainingLanes = max(1, abs(bestLaneOffset))
remainingSeconds = max(STEPS2TIME(TS),
    leftSpace/max(lookAheadSpeed,NUMERICAL_EPS)/remainingLanes/2)
# opposite direction uses 5 instead of 2; TraCI uses request remaining time
```

The `STEPS2TIME(TS)` expression above intentionally reproduces the source, including its unusual conversion of TS. Do not silently replace it while claiming exactness. Urgency is a boolean comparison plus a negotiation time budget; it is not a continuous normalized score. Stopped leaders, route-ending lanes, stops, roundabouts and neighbor lane suitability override ordinary strategic requests or produce `STAY`. Exact cases A2 (`MSLCM_LC2013.cpp:1119-1550`; `MSLCM_LC2013.h:197-202`).

Speed advantage is based on anticipated safe speed, not posted speed. With `P=10^7`, `r=(neighborSafe-currentSafe)/max(neighborSafe,10)`:

```text
TL = trunc(0.2/lcSpeedGain * P)
TR = trunc((0.2/lcSpeedGainRight)/lcSpeedGain * P)
# lcSpeedGain<=0 -> both thresholds INT64_MAX
right: if currentSafe-5/3.6 > neighborSafe: PR=trunc(PR*0.5^h)
       else: PR += trunc(h*r*P); update keepRight accumulator
left:  if currentSafe > neighborSafe: PL=trunc(PL*0.5^h)
       elif equal: PL=trunc(PL*0.8^h)
       else: PL += trunc(h*r*P)
requestSpeedGainRight = PR>TR && neighDist/max(0.1,speed)>20
requestSpeedGainLeft = PL>TL && (r>EPS || avoidRightOvertakeImpulse)
                       && neighDist/max(0.1,speed)>20
speedGainUrgent = selectedAccumulator > 50*P
```

These are persistent signed accumulators, not fresh random probabilities. For keep-right, default `acceptanceTime=7*(vMax/laneLimit)*max(1,speed)`; full-speed seconds are limited by neighbor lane end, braking distance, secure gap to its leader and right-overtaking restrictions. `deltaProb=TR*(fullSpeedSeconds/acceptanceTime)/5`; `PK -= trunc(h*deltaProb)`; request when `trunc(PK*lcKeepRight)<-TR`. All reset to zero on `changed`. Exact acceptance-time override, near-follower correction and branches A2 (`MSLCM_LC2013.cpp:1085-1115,1718-1907`).

Cooperation is essential for merge throughput: urgent ego computes `remainingSeconds`, informs neighbor leader and follower, reserves blocker lengths, and receives speed advice. This advice can accelerate to pass a leader, brake to fall behind a leader, ask a follower to brake, or permit the follower to pass while ego yields. `patchSpeed` combines advice with CF bounds and strategic/cooperative state. Advice is acceleration over an action step, derived from requested speed; it is not an immediate arbitrary assignment. Preserve speed coupling even if message passing becomes GPU reductions. Exact decision tree, including refusal to help, max braking and cut-in conditions, A2+A3 (`MSLCM_LC2013.cpp:200-1043,1494-1699,1980-2034`; `MSAbstractLaneChangeModel.cpp:1114-1198`).

Defaults are authoritative in A2 constructor and A3 base constructor: strategic/cooperative/speedGain/keepRight/opposite=1; lookaheadLeft=2; speedGainRight=.1; speedGainLookahead=0; speedGainRemainTime=20; speedGainUrgency=50; cooperativeRoundabout and cooperativeSpeed inherit cooperative; keepRightAcceptanceTime=-1; overtakeDeltaSpeedFactor=0; experimental1=0; strategicLookahead=-1; sigma=0; overtakeRight=0; assertive=1; cooperativeHelpTime=60; cooperativeHelpThreshold=-1; cooperativeMinSpeed=0; maxSpeedLatStanding inherits vType maxSpeedLat; maxSpeedLatFactor=1; maxDistLatStanding=1.6 except bicycle/motorcycle/moped use maximum double. The model constants (LOOK_FORWARD, JAM_FACTOR, help speeds, turn-lane/on-ramp thresholds, fixed-point precision) are included verbatim in A2 (`MSLCM_LC2013.cpp:48-150`; `MSAbstractLaneChangeModel.cpp:139-150`).

### Best lanes and recommended GPU representation

`LaneQ` includes lane pointer, usable continuation `length`, `occupation`, signed `bestLaneOffset`, `allowsContinuation`, ordered `bestContinuations` and `nextOccupation`. Construction walks route edges, scores feasible continuations backwards, propagates offsets and handles required stops/arrival lanes; within the same edge it refreshes occupation/current best lane instead of rebuilding. `nextOccupation` sums downstream continuation gross vehicle lengths; current occupation gets lane-changer working density plus next occupation. Exact construction and tie handling A5 (`microsim/MSVehicle.cpp:6018-6538,6737-6738`).

Default lookahead continues only while **both** conditions hold: `(seen<=4 || seenLength<max(maxBrakeDist,3000))` and `(seen<=8 || seenLength<max(maxBrakeDist,200) || railway)`, and route remains. Custom lookahead uses `seen<=2 || seenLength<lookahead`. Thus neither 'next edge only' nor 'always 3000m' reproduces it (`MSVehicle.cpp:6208-6217`).

**Proposal/inference:** an edge-entry good-lane bitmask plus one distance does not reproduce this behavior. Retain, per route segment and vClass, each lane's continuation length, signed offset, next-lane index and continuation-valid bit; add per-step lane occupation reductions and query downstream continuation sums. Cache structural data by route suffix; invalidate for stops, route changes and permission changes. A bitmask alone loses unequal usable lengths, multiple required lane changes, stop-specific target lanes, continuation chains and changing congestion. This follows from the dependencies in A2 and A5, not a measured claim of equivalence.

**Proposed simultaneous GPU scheme (not SUMO behavior):**

```text
1 snapshot sorted lane arrays after longitudinal movement
2 compute current/downstream occupations; update persistent motivation state
3 each active vehicle emits at most one adjacent-lane proposal:
  target lane, old follower+leader IDs, projected body interval,
  secure front/back bounds, urgency/reason, distance-to-required-change
4 group by (targetLane, oldFollowerID, oldLeaderID)
  choose one proposal: urgent strategic first, then smallest distance per
  required lane change, then longest blocked age, then stable randomized ID
5 resolve conflicts between neighboring groups and opposite-direction swaps:
  accept only proposals whose body+secure-gap reservations do not intersect
  any accepted arrival or any vehicle staying in that lane; conservatively
  retain departures as occupied during this arbitration
6 revalidate accepted vehicles against final target neighbors; reject failures
7 commit lane membership once; rebuild lane order; reduce cooperative speed
  advice to per-vehicle CF-bounded acceleration for the following step
```

**Reasoning/inference:** one winner per old gap prevents two arrivals using the same gap, but is insufficient by itself for adjacent gaps, occupied departure gaps or crossing swaps; reservation conflicts and final-neighbor checks close these holes. Conservative retention can reduce lane-change frequency; calibrate against lane utilization, merge discharge, weaving completion and missed-turn counts over several random seeds. Rotate tie priority to prevent starvation; do not assume simultaneous updates are statistically neutral (compare sequential algorithm A1).

Drop order, least to greatest expected macroscopic impact (engineering judgment): (1) debug/TraCI if unused, lateral animation under default zero duration; (2) opposite passing and sublane details only for scenarios without those modes; (3) detailed pedestrian and stopped-obstacle branches only after removing those demand modes; (4) elaborate leader/follower negotiation in favor of one bounded yield request plus blocked-age fairness; (5) roundabout bonus and fine keep-right acceptance corrections; (6) keep-right and speed-gain hysteresis; (7) strategic offsets, occupation-aware urgency and cooperative yielding. Preserve the last group first: the source explicitly uses them for route completion, counter-changing reservations and opening merge gaps (A2). Never drop permissions, overlap exclusion or final secure-gap checks (A1).

## B. Insertion

Default lane is first allowed (rightmost permitted), not a random/balanced lane; default front position `base=min(vehicleLength+POSITION_EPS, edgeMinLength)`, reduced by a stop on the starting edge; default speed is zero. Global depart defaults can override procedures. Exact selectors B1 (`MSEdge.cpp:700-775`; `MSLane.cpp:607-657`; `MSBaseVehicle.cpp:1415-1424`).

| Attribute | Value | Meaning |
|---|---|---|
| departLane | numeric | specified index, reject invalid/forbidden |
| | random | uniform from vClass-allowed lanes |
| | free | choose free lane using insertion-position bound |
| | allowed | free among lanes reaching next route edge (single-edge route: free) |
| | best | free among maximum-continuation lanes, capped at 3000m after depart-position correction |
| | best_prob | deterministic gap selection with a speed-factor restriction among those best lanes |
| | first/default | first allowed lane |
| departPos | numeric | front position; negative counts back from lane end |
| | random | one uniform lane-position draw |
| | random_free | up to 10 random attempts then free-space search |
| | free | systematic free-space search |
| | last | last-position insertion algorithm |
| | base/default | front at basePos, not front at zero |
| departSpeed | numeric | requested speed, cannot patch downward to fit traffic |
| | random | uniform up to vehicle/lane maximum; may reduce for safety |
| | max | vehicle/lane maximum; may reduce for safety |
| | desired | same initial maximum; may not reduce for safety |
| | speedLimit | vehicle/lane maximum divided by chosen speedFactor; may not reduce |

All table rules and precise free/probable-lane tie algorithms are in B1 (`MSLane.cpp:482-818`; `MSEdge.cpp:700-775` and lane-selection helpers included below). Procedures belong to their attribute: `free` is not a departSpeed value (`utils/vehicle/SUMOVehicleParameter.cpp:397-559`).

Insertion checks CF safety to leader and follower, overlap/minGap, maximum attainable safe speed to future stops/lane endings/red signals/links, permissions and downstream leaders. A position that is free now can still fail because braking ahead is impossible. `patchSpeed` controls whether infrastructure/traffic constraints reduce requested speed or reject insertion. Successful insertion enters lane containers and fires departed notifications. Exact B1 `isInsertionSuccess`, including check-mask exceptions, is normative (`MSLane.cpp:819-1423`).

Pending departures preserve refusal order; retries precede newly due departures. Default `eager-insert=false` caches failed lane indices on the edge for that step and skips later attempts selecting the same lane; this is an optimization and head-of-line effect, not a universal strict per-edge FIFO across all lane procedures. `eager-insert=true` checks each vehicle. No fixed one-vehicle-per-edge-per-step rule exists. `max-num-vehicles=-1` means no running-count cap. `max-depart-delay=-1` never expires; otherwise discard on failed insertion only when `time-scheduledDepart > maxDelay`, strictly greater. Failed vehicles are retained for next step except discarded/aborted/vaporized/invalid-start cases. B2 gives complete scheduling and B1 the edge failure cache (`MSInsertionControl.cpp:127-315`; `MSEdge.cpp:780-945`; defaults `MSFrame.cpp:434,482-489`).

Flow expansion copies parameters into `flowID.index` vehicles, resolves route and vType distributions per generated vehicle, and puts due departures into the same queue. Deterministic repetitions use a while-loop and can expand multiple due vehicles per step; probabilistic flows do one Bernoulli trial with `probability*TS` per step (before scale quota duplication). Scaling, random departure offsets and distributions alter expansion; exact B2 plus B3 flow-parameter increment/parser (`MSInsertionControl.cpp:231-315`; `SUMOVehicleParameter.cpp` and `SUMOVehicleParserHelper.cpp` extracts below). A probability flow is not an arbitrary Poisson count per step.

## C. Output contracts

### Tripinfo

```text
duration = (arrived ? arrivalStep : currentStep) - actualDeparture
routeLength = accumulatedDepartCorrectedLaneLengths +
              (arrived ? arrivalPos : currentPos)
departDelay = actualDeparture - requestedDeparture
# unfinished undeparted output: currentStep-requestedDeparture
on movement callback:
  if isStopped && newSpeed<=0.1: stopTime+=TS
  elif !isStopped && newSpeed<=0.1 && lowAcceleration:
    waitingTime+=TS
    if !amWaiting: waitingCount++; amWaiting=true
  elif !isStopped: amWaiting=false
# parking uses its own start/stop clock; idle callback counts waiting
on longitudinal time-loss update, only if !isStopped:
  vmax=min(updatedLane.vehicleMaxSpeed, max(myStopSpeed,vNext))
  if vmax>0: timeLoss+=TS*(vmax-vNext)/vmax
```

`waitingCount` counts episodes, not steps. Stop branches do not reset `amWaiting`. Low acceleration means acceleration <= 0.5*CF.maxAccel (`microsim/MSVehicle.h:2100-2102`), so threshold speed alone is insufficient. Length accumulates actual traversed lane lengths and departure correction, not the route-edge list's nominal total. Full movement/leave callbacks and formulas C1 (`MSDevice_Tripinfo.cpp:169-377`; `MSVehicle.cpp:4308-4317`; `StdDefs.h:62`).

### Summary

`inserted` and `ended` are cumulative counters (`inserted=running+ended-discarded`; `ended` includes discarded vehicles; `microsim/MSVehicleControl.h:254-285`), `running` current running count including teleporting vehicles, `waiting` pending insertion queue size. `halting` counts on-road or remote-controlled vehicles with speed **<0.1** (tripinfo uses **<=0.1**). Mean speed averages on-road/remote vehicles **excluding scheduled stopped vehicles**; relative speed averages each vehicle speed divided by its edge speed limit, not average speed divided by one limit; absent vehicles -> both -1. Summary `duration` is wall-clock simulation-step execution time in milliseconds (`microsim/MSNet.cpp:842,972`), emitted only with execution timing enabled, not trip duration. Exact C2 (`MSNet.cpp:696-743`; `MSVehicleControl.cpp:550-585`; counter update functions below; `MSInsertionControl.cpp:317-320`).

### edgeData / MSMeanData_Net

Use separate integrals for front-on-lane and any-body-overlap; let `T` interval seconds, `L` aggregation lane length, `N` lane count, `SF` front sample seconds, `S` overlap sample seconds, `DF` front travelled distance, `D` overlap travelled distance, `O` integral of actual body length occupying lane. Exact clipping/interpolation and aggregation are C3 (`MSMeanData.cpp:87-256,650-780`; `MSMeanData_Net.cpp:99-363`).

```text
sampledSeconds = S = sum(timeOnLane)
speed = D/S                         # space/time mean
frontSpeed = DF/SF
density = SF/T*1000/L                # veh/km across edge
laneDensity = density/N
occupancy = O/T/L/N*100              # percent, no minGap
flow = density*frontSpeed*3.6         # veh/hour, NOT nVehEntered*3600/T
traveltime = min(maxTravelTime,L*SF/DF) when DF>EPS and samples sufficient
# tracker mode numVehicles>0: traveltime=S/numVehicles
```

Discrete-lane densities are capped at `1000*N/minimalLengthWithGap`; overlap density uses S instead of SF. Occupation increments `meanLengthOnLane*TS` including partial body occupancy, not `vehicleLength*frontOnLane`. at edge aggregation sum lane integrals before deriving values; for differing lane lengths follow C3's normalization exactly. Entered/left are junction entry/exit notifications; departed/arrived are separate counters; lane-change counts are separate and do not inflate entered/left. A vehicle straddling two successive lanes/edges can contribute body-overlap seconds to both. Exact C3 also defines lane-change reminder persistence (`MSMeanData_Net.cpp:129-250`; `MSMeanData.cpp:87-256`).

Output attributes have sample/default masks: `haveSamples = S > minSamples` (strict); no samples can omit attributes or use configured defaults. In the parent-backed writer flow is passed an omission condition `!haveSamples || numVehicles==0`: flow may therefore be absent in ordinary untracked output even though the formula exists. Do not invent `entered/T` when it is absent. `excludeEmpty=true` suppresses empty records, false includes them, defaults/default enables default values, modified prints modified speeds with defaults; emptiness checks event counters as well as sample seconds. C3 includes all branches (`MSMeanData_Net.cpp:248-363`; `MSMeanData.cpp:401-435,650-780`).

### E1 induction loops

A point loop detects front crossing at lane position and rear clearing that position; nonzero detector length extends rear exit position. Substep crossing uses CF `passingTime`, not only step boundary counts. A fully contributing vehicle speed is `(vehicleLength+detectorLength)/max(exitTime-entryTime,EPS)`. Early lane changes/removals can contribute occupancy without contributing a complete passage. Position normalization/validation is in C4 (`MSInductLoop.cpp:150-263,595-600`; `NLDetectorBuilder.cpp` extracts).

```text
nVehContrib = count completed, non-leftEarly vehicle records
flow = 3600*nVehContrib/T
speed = arithmetic mean(recordSpeed), else -1
occupancy = 100/T * [sum completed/early clipped occupation durations
                    + sum stillPresent(stopTime-max(startTime,entryTime))]
```

An E1 is a time-mean crossing detector; its speed differs from edgeData's distance/time mean. `nVehEntered` can exceed `nVehContrib`. C4 contains reset/interval treatment and exact clipping (`MSInductLoop.cpp:486-526`).

### FCD

Per-step vehicle records use actual position, navigation angle, type, speed, longitudinal position, lane and slope; options/attribute masks select additional fields (3D z, signals, acceleration, distance, leader IDs/gap/speed, lateral position/speed, person/container counts and custom params). Geographic coordinates are converted when configured. Do not assume all fields are unconditional or replace navigation angle with mathematical radians. C5 transcribes the complete exporter and attribute selection, including meso/person branches so the schema is explicit (`MSFCDExport.cpp:45-350`).

## D. Demand and scenario compatibility

`<vehicle>` binds ID, departure, vType and either referenced route/distribution or embedded route; `<route>` is an ordered edge sequence with optional stops; `<routeDistribution>` samples weighted routes; `<vTypeDistribution>` samples weighted type definitions/references, not averaged parameters. `<flow>` expands repetition/probability demand; `<trip>` supplies from/via/to routing waypoints. Exact D1 handlers and B3 parser distinguish missing route, disconnected waypoint route and valid complete route (`MSRouteHandler.cpp:105-261,265-379,404-782,986-1104`).

From/to trips set `VEHPARS_FORCE_REROUTE`: they need an initial route computation, not a direct link between origin and destination. Routing-device construction supports this forced route independently of ordinary optional device assignment. Periodic en-route rerouting is separately controlled: default period=0 disables periodic rerouting, pre-period=60 allows predeparture updates for equipped vehicles. Thus 'one-shot routing at insertion' is an approximation to the initial routing lifecycle, not a universal exact trigger. Assignment probability is configurable; do not hardcode 100% and do not mistake probability=0 for no initial routing of trips. Exact D2 routing-device construction/pre-insertion callbacks and D1 trip closure (`MSDevice_Routing.cpp:47-116` and behavioral functions below; `MSRouteHandler.cpp:1095-1104`).

**Scope decision/proposal:** if persons are ignored, explicitly remove their transport demand and interactions, including passenger-triggered vehicle stops; ignoring them can change buses waiting for passengers and pedestrian conflicts. Bus stops still need lane/position/duration/until and route progression for buses even without persons, or traffic capacity and trip stopTime change. Stops constrain best lanes and insertion base position as shown in A5/B1; person plans and stop parsing D1/D3 establish what is being omitted.

Scenario evidence boundary: bundled docs describe Bologna, TAPAS Cologne, LuST, MoST and BeST but do not include a version-pinned feature census of their route/config files. Do not assert a particular flow count, distribution usage or rerouting probability for all releases. D4 reproduces the local scenario descriptions and TAPAS package inventory with citations. **Implementation recommendation/inference:** support vehicles+routes+flows, route/vType distributions, stops/public transport and initial trip routing before claiming general city-scenario support; parse configuration rerouting probability/period and demand stop rules rather than guessing by scenario name. For a selected release, inventory XML tags, departure procedures, vClass/type distributions, stops, persons, additional-file rerouters and config device assignments; record exclusions before statistical comparison. The parser capabilities in D1–D3 are the implementation baseline, not evidence every scenario uses every feature.

## Normative algorithm transcription

The following compact source algorithms complete the branch-level specification above. Each numbered line is a file:line citation under its enclosing file heading. Preserve integer truncation, strict versus inclusive inequalities and evaluation order. These are algorithms to translate to WGSL/data preprocessing, not a request to link SUMO. CF, junction and routing engines remain external subsystem contracts.

### A1. Sequential lane changing — `microsim/MSLaneChanger.cpp:190-1168`

```cpp
190: MSLaneChanger::laneChange(SUMOTime t) {
195:     initChanger();
196:     try {
197:         while (vehInChanger()) {
198:             const bool haveChanged = change();
199:             updateChanger(haveChanged);
200:         }
201:         updateLanes(t);
202:     } catch (const ProcessError&) {
204:         for (ChangerIt ce = myChanger.begin(); ce != myChanger.end(); ++ce) {
205:             ce->lane->releaseVehicles();
206:         }
207:         throw;
208:     }
209: }
212: void
213: MSLaneChanger::initChanger() {
215:     for (ChangerIt ce = myChanger.begin(); ce != myChanger.end(); ++ce) {
216:         ce->lead = nullptr;
217:         ce->hoppedVeh = nullptr;
218:         ce->lastBlocked = nullptr;
219:         ce->firstBlocked = nullptr;
220:         ce->lastStopped = nullptr;
221:         ce->dens = 0;
222:         ce->lastBlockedBackPos = -1;
223:         ce->lastBlockedWaitingTime = -1;
224:         ce->lane->getVehiclesSecure();
227:     }
228: }
231: void
232: MSLaneChanger::updateChanger(bool vehHasChanged) {
233:     assert(veh(myCandi) != 0);
238:     if (!vehHasChanged) {
240:         myCandi->lead = veh(myCandi);
241:     }
243:     MSLane::VehCont& vehicles = myCandi->lane->myVehicles;
244:     vehicles.pop_back();
246: }
249: void
250: MSLaneChanger::updateLanes(SUMOTime t) {
259:     for (ChangerIt ce = myChanger.begin(); ce != myChanger.end(); ++ce) {
261:         ce->lane->swapAfterLaneChange(t);
262:         ce->lane->releaseVehicles();
263:         if (ce->firstBlocked != nullptr) {
264:             ce->lastBlockedBackPos = ce->firstBlocked->getBackPositionOnLane();
265:             ce->lastBlockedWaitingTime = ce->firstBlocked->getWaitingTime();
266:         }
267:     }
268: }
271: MSLaneChanger::ChangerIt
272: MSLaneChanger::findCandidate() {
275:     ChangerIt max = myChanger.end();
280:     for (ChangerIt ce = myChanger.begin(); ce != myChanger.end(); ++ce) {
281:         if (veh(ce) == nullptr) {
282:             continue;
283:         }
288:         if (max == myChanger.end()) {
292:             max = ce;
293:             continue;
294:         }
295:         assert(veh(ce)  != 0);
296:         assert(veh(max) != 0);
297:         if (veh(max)->getPositionOnLane() < veh(ce)->getPositionOnLane()) {
301:             max = ce;
302:         }
303:     }
304:     assert(max != myChanger.end());
305:     assert(veh(max) != 0);
306:     return max;
307: }
310: bool
311: MSLaneChanger::mayChange(int direction) const {
312:     if (direction == 0) {
313:         return true;
314:     }
315:     if (!myAllowsChanging) {
316:         return false;
317:     }
318:     SUMOVehicleClass svc = veh(myCandi)->getVClass();
319:     if (direction == -1) {
320:         return myCandi->mayChangeRight && (myCandi - 1)->lane->allowsVehicleClass(svc) && myCandi->lane->allowsChangingRight(svc);
321:     } else if (direction == 1) {
322:         return myCandi->mayChangeLeft && (myCandi + 1)->lane->allowsVehicleClass(svc) && myCandi->lane->allowsChangingLeft(svc);
323:     } else {
324:         return false;
325:     }
326: }
329: bool
330: MSLaneChanger::change() {
344:     myCandi = findCandidate();
345:     MSVehicle* vehicle = veh(myCandi);
346:     vehicle->getLaneChangeModel().clearNeighbors();
348:     if (vehicle->getLaneChangeModel().isChangingLanes() && !vehicle->getLaneChangeModel().alreadyChanged()) {
349:         return continueChange(vehicle, myCandi);
350:     }
351:     if (!myAllowsChanging || vehicle->getLaneChangeModel().alreadyChanged() || vehicle->isStoppedOnLane()) {
352:         registerUnchanged(vehicle);
353:         if (vehicle->isStoppedOnLane()) {
354:             myCandi->lastStopped = vehicle;
355:         }
356:         return false;
357:     }
359:     if (!vehicle->isActive()) {
365:         bool changed = false;
366:         const int oldstate = vehicle->getLaneChangeModel().getOwnState();
368:         checkTraCICommands(vehicle);
369:         if (oldstate != vehicle->getLaneChangeModel().getOwnState()) {
370:             changed = applyTraCICommands(vehicle);
371:         }
372:         if (!changed) {
373:             registerUnchanged(vehicle);
374:         }
375:         return changed;
376:     }
379:     std::pair<MSVehicle* const, double> leader = getRealLeader(myCandi);
380:     if (myChanger.size() == 1 || vehicle->getLaneChangeModel().isOpposite() || (!mayChange(-1) && !mayChange(1))) {
381:         if (changeOpposite(vehicle, leader, myCandi->lastStopped)) {
382:             return true;
383:         }
384:         registerUnchanged(vehicle);
385:         return false;
386:     }
388:     vehicle->updateBestLanes(); // needed?
389:     for (int i = 0; i < (int) myChanger.size(); ++i) {
390:         vehicle->adaptBestLanesOccupation(i, myChanger[i].dens);
391:     }
393:     const std::vector<MSVehicle::LaneQ>& preb = vehicle->getBestLanes();
395:     int stateRight = 0;
396:     if (mayChange(-1)) {
397:         stateRight = checkChangeWithinEdge(-1, leader, preb);
399:         if ((stateRight & LCA_RIGHT) != 0 && (stateRight & LCA_BLOCKED) == 0) {
400:             vehicle->getLaneChangeModel().setOwnState(stateRight);
401:             return startChange(vehicle, myCandi, -1);
402:         }
403:         if ((stateRight & LCA_RIGHT) != 0 && (stateRight & LCA_URGENT) != 0) {
404:             (myCandi - 1)->lastBlocked = vehicle;
405:             if ((myCandi - 1)->firstBlocked == nullptr) {
406:                 (myCandi - 1)->firstBlocked = vehicle;
407:             }
408:         }
409:     }
412:     int stateLeft = 0;
413:     if (mayChange(1)) {
414:         stateLeft = checkChangeWithinEdge(1, leader, preb);
416:         if ((stateLeft & LCA_LEFT) != 0 && (stateLeft & LCA_BLOCKED) == 0) {
417:             vehicle->getLaneChangeModel().setOwnState(stateLeft);
418:             return startChange(vehicle, myCandi, 1);
419:         }
420:         if ((stateLeft & LCA_LEFT) != 0 && (stateLeft & LCA_URGENT) != 0) {
421:             (myCandi + 1)->lastBlocked = vehicle;
422:             if ((myCandi + 1)->firstBlocked == nullptr) {
423:                 (myCandi + 1)->firstBlocked = vehicle;
424:             }
425:         }
426:     }
428:     if ((stateRight & LCA_URGENT) != 0 && (stateLeft & LCA_URGENT) != 0) {
431:         stateLeft = 0;
432:     }
433:     vehicle->getLaneChangeModel().setOwnState(stateRight | stateLeft);
437:     if ((vehicle->getVClass() == SVC_EMERGENCY
438:             || hasOppositeStop(vehicle))
439:             && changeOpposite(vehicle, leader, myCandi->lastStopped)) {
440:         return true;
441:     }
443:     registerUnchanged(vehicle);
444:     return false;
445: }
448: void
449: MSLaneChanger::registerUnchanged(MSVehicle* vehicle) {
451:     myCandi->lane->myTmpVehicles.insert(myCandi->lane->myTmpVehicles.begin(), veh(myCandi));
452:     myCandi->dens += vehicle->getVehicleType().getLengthWithGap();
453:     vehicle->getLaneChangeModel().unchanged();
454: }
458: void
459: MSLaneChanger::checkTraCICommands(MSVehicle* vehicle) {
463:     vehicle->getLaneChangeModel().checkTraCICommands();
476: }
479: bool
480: MSLaneChanger::applyTraCICommands(MSVehicle* vehicle) {
482:     bool changed = false;
483:     const int state = vehicle->getLaneChangeModel().getOwnState();
484:     const int dir = (state & LCA_RIGHT) != 0 ? -1 : ((state & LCA_LEFT) != 0 ? 1 : 0);
485:     const bool execute = dir != 0 && ((state & LCA_BLOCKED) == 0);
486:     if (execute) {
487:         ChangerIt to = myCandi + dir;
488:         bool continuous = vehicle->getLaneChangeModel().startLaneChangeManeuver(myCandi->lane, to->lane, dir);
489:         if (continuous) {
490:             changed = continueChange(vehicle, myCandi);
491:         } else {
493:             to->registerHop(vehicle);
494:             changed = true;
495:         }
496:     }
497:     return changed;
498: }
501: bool
502: MSLaneChanger::startChange(MSVehicle* vehicle, ChangerIt& from, int direction) {
503:     if (vehicle->isRemoteControlled()) {
504:         registerUnchanged(vehicle);
505:         return false;
506:     }
507:     ChangerIt to = from + direction;
511:     const bool continuous = vehicle->getLaneChangeModel().startLaneChangeManeuver(from->lane, to->lane, direction);
512:     if (continuous) {
513:         return continueChange(vehicle, myCandi);
514:     } else {
515:         to->registerHop(vehicle);
516:         to->lane->requireCollisionCheck();
517:         return true;
518:     }
519: }
521: bool
522: MSLaneChanger::continueChange(MSVehicle* vehicle, ChangerIt& from) {
523:     MSAbstractLaneChangeModel& lcm = vehicle->getLaneChangeModel();
524:     const int direction = lcm.isOpposite() ? -lcm.getLaneChangeDirection() : lcm.getLaneChangeDirection();
525:     const bool pastMidpoint = lcm.updateCompletion(); // computes lcm.mySpeedLat as a side effect
526:     const double speedLat = lcm.isOpposite() ? -lcm.getSpeedLat() : lcm.getSpeedLat();
527:     vehicle->myState.myPosLat += SPEED2DIST(speedLat);
528:     vehicle->myCachedPosition = Position::INVALID;
530:     if (pastMidpoint) {
531:         MSLane* source = myCandi->lane;
532:         MSLane* target = source->getParallelLane(direction);
533:         vehicle->myState.myPosLat -= direction * 0.5 * (source->getWidth() + target->getWidth());
534:         lcm.primaryLaneChanged(source, target, direction);
535:         if (&source->getEdge() == &target->getEdge()) {
536:             ChangerIt to = from + direction;
537:             to->registerHop(vehicle);
538:         }
539:         target->requireCollisionCheck();
540:     } else {
541:         from->registerHop(vehicle);
542:         from->lane->requireCollisionCheck();
543:     }
544:     if (!lcm.isChangingLanes()) {
545:         vehicle->myState.myPosLat = 0;
546:         lcm.endLaneChangeManeuver();
547:     }
548:     lcm.updateShadowLane();
549:     if (lcm.getShadowLane() != nullptr && &lcm.getShadowLane()->getEdge() == &vehicle->getLane()->getEdge()) {
551:         myChanger[lcm.getShadowLane()->getIndex()].hoppedVeh = vehicle;
552:         lcm.getShadowLane()->requireCollisionCheck();
553:     }
554:     vehicle->myAngle = vehicle->computeAngle();
555:     if (lcm.isOpposite()) {
556:         vehicle->myAngle += M_PI;
557:     }
574:     return pastMidpoint && lcm.getShadowLane() == nullptr;
575: }
578: std::pair<MSVehicle* const, double>
579: MSLaneChanger::getRealLeader(const ChangerIt& target) const {
580:     assert(veh(myCandi) != 0);
581:     MSVehicle* vehicle = veh(myCandi);
588:     MSVehicle* neighLead = target->lead;
599:     if (target->hoppedVeh != nullptr) {
600:         double hoppedPos = target->hoppedVeh->getPositionOnLane();
606:         if (hoppedPos > vehicle->getPositionOnLane() && (neighLead == nullptr || neighLead->getPositionOnLane() > hoppedPos)) {
607:             neighLead = target->hoppedVeh;
609:         }
610:     }
612:     const bool checkBidi = target->lane->getBidiLane() != nullptr && target->lane->getBidiLane()->getVehicleNumberWithPartials() > 0;
613:     if (neighLead == nullptr || checkBidi) {
621:         MSLane* targetLane = target->lane;
622:         const double egoBack = vehicle->getBackPositionOnLane();
623:         double leaderBack = targetLane->getLength();
624:         if (neighLead != nullptr) {
625:             leaderBack = neighLead->getBackPositionOnLane(targetLane);
626:         }
627:         for (MSVehicle* pl : targetLane->myPartialVehicles) {
628:             double plBack = pl->getBackPositionOnLane(targetLane);
629:             if (pl->isBidiOn(targetLane)) {
630:                 plBack -= pl->getVehicleType().getLengthWithGap();
631:             }
632:             const double plPos = plBack + pl->getVehicleType().getLength();
638:             if (plBack < leaderBack && plPos + pl->getVehicleType().getMinGap() >= egoBack) {
639:                 neighLead = pl;
640:                 leaderBack = plBack;
641:             }
642:         }
643:         if (neighLead != nullptr) {
649:             const double gap = leaderBack - vehicle->getPositionOnLane() - vehicle->getVehicleType().getMinGap();
650:             return std::pair<MSVehicle*, double>(neighLead, gap);
651:         }
652:         double seen = myCandi->lane->getLength() - vehicle->getPositionOnLane();
653:         double speed = vehicle->getSpeed();
654:         double dist = vehicle->getCarFollowModel().brakeGap(speed) + vehicle->getVehicleType().getMinGap();
655:         if (target->lane->getBidiLane() != nullptr) {
656:             dist += target->lane->getBidiLane()->getMaximumBrakeDist();
657:         }
659:         if (seen > dist && !myCandi->lane->isInternal()) {
665:             return std::pair<MSVehicle* const, double>(static_cast<MSVehicle*>(nullptr), -1);
666:         }
667:         const std::vector<MSLane*>& bestLaneConts = vehicle->getBestLanesContinuation(targetLane);
669:         std::pair<MSVehicle* const, double> result = target->lane->getLeaderOnConsecutive(dist, seen, speed, *vehicle, bestLaneConts);
675:         return result;
676:     } else {
682:         return std::pair<MSVehicle* const, double>(neighLead, neighLead->getBackPositionOnLane(target->lane) - vehicle->getPositionOnLane() - vehicle->getVehicleType().getMinGap());
683:     }
684: }
687: std::pair<MSVehicle* const, double>
688: MSLaneChanger::getRealFollower(const ChangerIt& target) const {
689:     assert(veh(myCandi) != 0);
690:     MSVehicle* vehicle = veh(myCandi);
696:     const double candiPos = vehicle->getPositionOnLane();
697:     MSVehicle* neighFollow = nullptr;
698:     if (target != myCandi) {
699:         neighFollow = veh(target);
700:     } else {
702:         if (target->lane->myVehicles.size() > 1) {
703:             neighFollow = target->lane->myVehicles[target->lane->myVehicles.size() - 2];
704:         }
705:     }
727:     neighFollow = getCloserFollower(candiPos, neighFollow, target->hoppedVeh);
739:     neighFollow = getCloserFollower(candiPos, neighFollow, target->lane->getPartialBehind(vehicle));
741:     if (neighFollow == nullptr) {
742:         CLeaderDist consecutiveFollower = target->lane->getFollowersOnConsecutive(vehicle, vehicle->getBackPositionOnLane(), true)[0];
752:         return std::make_pair(const_cast<MSVehicle*>(consecutiveFollower.first), consecutiveFollower.second);
753:     } else {
759:         return std::pair<MSVehicle* const, double>(neighFollow,
760:                 vehicle->getPositionOnLane() - vehicle->getVehicleType().getLength() - neighFollow->getPositionOnLane() - neighFollow->getVehicleType().getMinGap());
761:     }
762: }
765: MSVehicle*
766: MSLaneChanger::getCloserFollower(const double maxPos, MSVehicle* follow1, MSVehicle* follow2) {
767:     if (follow1 == nullptr || follow1->getPositionOnLane() > maxPos) {
768:         return follow2;
769:     } else if (follow2 == nullptr || follow2->getPositionOnLane() > maxPos) {
770:         return follow1;
771:     } else {
772:         if (follow1->getPositionOnLane() > follow2->getPositionOnLane()) {
773:             return follow1;
774:         } else {
775:             return follow2;
776:         }
777:     }
778: }
780: int
781: MSLaneChanger::checkChangeWithinEdge(
782:     int laneOffset,
783:     const std::pair<MSVehicle* const, double>& leader,
784:     const std::vector<MSVehicle::LaneQ>& preb) const {
786:     std::pair<MSVehicle*, double> follower = getRealFollower(myCandi);
787:     std::pair<MSVehicle* const, double> neighLead = getRealLeader(myCandi + laneOffset);
788:     std::pair<MSVehicle*, double> neighFollow = getRealFollower(myCandi + laneOffset);
789:     if (neighLead.first != nullptr && neighLead.first == neighFollow.first) {
792:         neighFollow.first = 0;
793:     }
794:     ChangerIt target = myCandi + laneOffset;
795:     return checkChange(laneOffset, target->lane, leader, follower, neighLead, neighFollow, preb);
796: }
798: int
799: MSLaneChanger::checkChange(
800:     int laneOffset,
801:     const MSLane* targetLane,
802:     const std::pair<MSVehicle* const, double>& leader,
803:     const std::pair<MSVehicle* const, double>& follower,
804:     const std::pair<MSVehicle* const, double>& neighLead,
805:     const std::pair<MSVehicle* const, double>& neighFollow,
806:     const std::vector<MSVehicle::LaneQ>& preb) const {
808:     MSVehicle* vehicle = veh(myCandi);
818:     int blocked = 0;
819:     int blockedByLeader = (laneOffset == -1 ? LCA_BLOCKED_BY_RIGHT_LEADER : LCA_BLOCKED_BY_LEFT_LEADER);
820:     int blockedByFollower = (laneOffset == -1 ? LCA_BLOCKED_BY_RIGHT_FOLLOWER : LCA_BLOCKED_BY_LEFT_FOLLOWER);
822:     if (neighFollow.first != nullptr && neighFollow.second < 0) {
823:         blocked |= (blockedByFollower | LCA_OVERLAPPING);
834:     }
835:     if (neighLead.first != nullptr && neighLead.second < 0) {
836:         blocked |= (blockedByLeader | LCA_OVERLAPPING);
846:     }
847:     double secureFrontGap = MSAbstractLaneChangeModel::NO_NEIGHBOR;
848:     double secureBackGap = MSAbstractLaneChangeModel::NO_NEIGHBOR;
849:     double secureOrigFrontGap = MSAbstractLaneChangeModel::NO_NEIGHBOR;
851:     const double tauRemainder = vehicle->getActionStepLength() == DELTA_T ? 0 : MAX2(vehicle->getCarFollowModel().getHeadwayTime() - TS, 0.);
853:     if ((blocked & blockedByFollower) == 0 && neighFollow.first != nullptr) {
861:         const double vNextFollower = neighFollow.first->getSpeed() + MAX2(0., tauRemainder * neighFollow.first->getAcceleration());
862:         const double vNextLeader = vehicle->getSpeed() + MIN2(0., tauRemainder * vehicle->getAcceleration());
864:         secureBackGap = neighFollow.first->getCarFollowModel().getSecureGap(neighFollow.first, vehicle, vNextFollower,
865:                         vNextLeader, vehicle->getCarFollowModel().getMaxDecel());
879:         if (neighFollow.second < secureBackGap * vehicle->getLaneChangeModel().getSafetyFactor()) {
880:             if (vehicle->getLaneChangeModel().isOpposite()
881:                     && neighFollow.first->getLaneChangeModel().getLastLaneChangeOffset() == laneOffset) {
891:             } else {
892:                 blocked |= blockedByFollower;
893:             }
894:         }
895:     }
898:     if ((blocked & blockedByLeader) == 0 && neighLead.first != nullptr) {
906:         const double vNextFollower = vehicle->getSpeed() + MAX2(0., tauRemainder * vehicle->getAcceleration());
907:         const double vNextLeader = neighLead.first->getSpeed() + MIN2(0., tauRemainder * neighLead.first->getAcceleration());
909:         secureFrontGap = vehicle->getCarFollowModel().getSecureGap(vehicle, neighLead.first, vNextFollower,
910:                          vNextLeader, neighLead.first->getCarFollowModel().getMaxDecel());
924:         if (neighLead.second < secureFrontGap * vehicle->getLaneChangeModel().getSafetyFactor()) {
925:             blocked |= blockedByLeader;
926:         }
927:     }
928:     if (blocked == 0 && targetLane->hasPedestrians()) {
929:         PersonDist nextLeader = targetLane->nextBlocking(vehicle->getBackPositionOnLane(),
930:                                 vehicle->getRightSideOnLane(targetLane), vehicle->getRightSideOnLane(targetLane) + vehicle->getVehicleType().getWidth(),
931:                                 ceil(vehicle->getSpeed() / vehicle->getCarFollowModel().getMaxDecel()));
932:         if (nextLeader.first != 0) {
933:             const double brakeGap = vehicle->getCarFollowModel().brakeGap(vehicle->getSpeed());
935:             const double gap = nextLeader.second - vehicle->getVehicleType().getLengthWithGap();
941:             if (brakeGap > gap) {
942:                 blocked |= blockedByLeader;
948:             }
949:         }
950:     }
952:     if (leader.first != nullptr) {
953:         secureOrigFrontGap = vehicle->getCarFollowModel().getSecureGap(vehicle, leader.first, vehicle->getSpeed(), leader.first->getSpeed(), leader.first->getCarFollowModel().getMaxDecel());
954:     }
956:     MSAbstractLaneChangeModel::MSLCMessager msg(leader.first, neighLead.first, neighFollow.first);
957:     int state = blocked | vehicle->getLaneChangeModel().wantsChange(
958:                     laneOffset, msg, blocked, leader, follower, neighLead, neighFollow, *targetLane, preb, &(myCandi->lastBlocked), &(myCandi->firstBlocked));
960:     if (blocked == 0 && (state & LCA_WANTS_LANECHANGE) != 0 && neighLead.first != nullptr) {
966:         const double seen = myCandi->lane->getLength() - vehicle->getPositionOnLane();
967:         const double speed = vehicle->getSpeed();
968:         const double dist = vehicle->getCarFollowModel().brakeGap(speed) + vehicle->getVehicleType().getMinGap();
969:         if (seen < dist || myCandi->lane->isInternal()) {
970:             std::pair<MSVehicle* const, double> neighLead2 = targetLane->getCriticalLeader(dist, seen, speed, *vehicle);
971:             if (neighLead2.first != nullptr && neighLead2.first != neighLead.first) {
972:                 const double secureGap = vehicle->getCarFollowModel().getSecureGap(vehicle, neighLead2.first, vehicle->getSpeed(),
973:                                          neighLead2.first->getSpeed(), neighLead2.first->getCarFollowModel().getMaxDecel());
974:                 const double secureGap2 = secureGap * vehicle->getLaneChangeModel().getSafetyFactor();
981:                 if (neighLead2.second < secureGap2) {
982:                     state |= blockedByLeader;
983:                 }
984:             }
985:         }
986:     }
987:     if (blocked == 0 && (state & LCA_WANTS_LANECHANGE)) {
989:         double targetZipperDist = 0;
990:         if (laneOffset == 0) {
991:             targetZipperDist = myCandi->zipperDist;
992:         } else if (laneOffset == 1) {
993:             if ((myCandi + 1) != myChanger.end()) {
994:                 targetZipperDist = (myCandi + 1)->zipperDist;
995:             }
996:         } else if (laneOffset == -1) {
997:             if (myCandi > myChanger.begin()) {
998:                 targetZipperDist = (myCandi - 1)->zipperDist;
999:             }
1000:         }
1001:         if (vehicle->unsafeLinkAhead(targetLane, targetZipperDist)) {
1002:             state |= blockedByLeader;
1003:         }
1004:     }
1006:     if ((state & LCA_BLOCKED) == 0 && (state & LCA_WANTS_LANECHANGE) != 0 && MSGlobals::gLaneChangeDuration > DELTA_T) {
1009:         const double distToNeighLane = 0.5 * (vehicle->getLane()->getWidth() + targetLane->getWidth());
1011:         const MSAbstractLaneChangeModel& lcm = vehicle->getLaneChangeModel();
1012:         const double assumedDecel = lcm.getAssumedDecelForLaneChangeDuration();
1013:         const double estimatedLCDuration = lcm.estimateLCDuration(vehicle->getSpeed(), distToNeighLane, assumedDecel, (state & LCA_URGENT) != 0);
1014:         if (estimatedLCDuration == -1) {
1024:             state |= LCA_INSUFFICIENT_SPEED;
1025:         } else {
1027:             const double decel = vehicle->getCarFollowModel().getMaxDecel() * estimatedLCDuration;
1028:             const double avgSpeed = 0.5 * (
1029:                                         MAX2(0., vehicle->getSpeed() - ACCEL2SPEED(vehicle->getCarFollowModel().getMaxDecel())) +
1030:                                         MAX2(0., vehicle->getSpeed() - decel));
1032:             const double space2change = avgSpeed * estimatedLCDuration;
1034:             double seen = myCandi->lane->getLength() - vehicle->getPositionOnLane();
1047:             const std::vector<MSLane*>& bestLaneConts = vehicle->getBestLanesContinuation();
1048:             int view = 1;
1049:             const MSLane* nextLane = vehicle->getLane();
1050:             std::vector<MSLink*>::const_iterator link = MSLane::succLinkSec(*vehicle, view, *nextLane, bestLaneConts);
1051:             while (!nextLane->isLinkEnd(link) && seen <= space2change) {
1052:                 if ((*link)->getDirection() == LinkDirection::LEFT || (*link)->getDirection() == LinkDirection::RIGHT
1055:                         || (nextLane->getEdge().isInternal() && (*link)->getViaLaneOrLane()->getEdge().isInternal())
1056:                    ) {
1057:                     state |= LCA_INSUFFICIENT_SPACE;
1058:                     break;
1059:                 }
1060:                 if ((*link)->getViaLane() == nullptr) {
1061:                     view++;
1062:                 }
1063:                 nextLane = (*link)->getViaLaneOrLane();
1064:                 seen += nextLane->getLength();
1066:                 link = MSLane::succLinkSec(*vehicle, view, *nextLane, bestLaneConts);
1067:             }
1073:             if (nextLane->isLinkEnd(link) && seen < space2change) {
1079:                 state |= LCA_INSUFFICIENT_SPACE;
1080:             }
1082:             if ((state & LCA_BLOCKED) == 0) {
1085:                 const double speed = vehicle->getSpeed();
1086:                 seen = myCandi->lane->getLength() - vehicle->getPositionOnLane();
1087:                 nextLane = vehicle->getLane();
1088:                 view = 1;
1089:                 const double dist = vehicle->getCarFollowModel().brakeGap(speed) + vehicle->getVehicleType().getMinGap();
1090:                 std::vector<MSLink*>::const_iterator nextLink = MSLane::succLinkSec(*vehicle, view, *nextLane, bestLaneConts);
1091:                 while (!nextLane->isLinkEnd(nextLink) && seen <= space2change && seen <= dist) {
1092:                     nextLane = (*nextLink)->getViaLaneOrLane();
1093:                     const MSLane* const parallelLane = nextLane->getParallelLane(laneOffset);
1094:                     if (parallelLane == nullptr) {
1095:                         state |= LCA_INSUFFICIENT_SPACE;
1096:                         break;
1097:                     } else {
1098:                         std::pair<MSVehicle* const, double> neighLead2 = parallelLane->getLeader(vehicle, -seen, std::vector<MSLane*>());
1099:                         if (neighLead2.first != nullptr && neighLead2.first != neighLead.first
1100:                                 && (neighLead2.second < vehicle->getCarFollowModel().getSecureGap(vehicle, neighLead2.first,
1101:                                         vehicle->getSpeed(), neighLead2.first->getSpeed(), neighLead2.first->getCarFollowModel().getMaxDecel()))) {
1102:                             state |= blockedByLeader;
1103:                             break;
1104:                         }
1105:                     }
1106:                     if ((*nextLink)->getViaLane() == nullptr) {
1107:                         view++;
1108:                     }
1109:                     seen += nextLane->getLength();
1111:                     nextLink = MSLane::succLinkSec(*vehicle, view, *nextLane, bestLaneConts);
1112:                 }
1113:             }
1114:         }
1115:     }
1117:     if (checkOpened && (state & LCA_BLOCKED) == 0 && (state & LCA_WANTS_LANECHANGE) != 0
1118:             && vehicle->getLane()->isNormal()
1119:             && vehicle->getBestLanesContinuation().size() > 1) {
1120:         const MSLink* link = vehicle->getLane()->getLinkTo(vehicle->getBestLanesContinuation()[1]);
1121:         if (link != nullptr && link->isEntryLink()) {
1122:             const MSLink* link2 = link->getParallelLink(laneOffset);
1123:             if (link2 != nullptr) {
1124:                 auto api = link->getApproachingPtr(vehicle);
1125:                 if (api != nullptr) {
1126:                     if (!link2->opened(api->arrivalTime, api->arrivalSpeed, api->leaveSpeed, vehicle->getLength(),
1127:                                        vehicle->getImpatience(), vehicle->getCarFollowModel().getMaxDecel(), vehicle->getWaitingTime(), vehicle->getLateralPositionOnLane(),
1128:                                        nullptr, false, vehicle, api->dist)) {
1130:                         state |= LCA_BLOCKED;
1131:                     }
1132:                 }
1133:             }
1134:         }
1135:     }
1137:     const int oldstate = state;
1139:     state = vehicle->influenceChangeDecision(state);
1140:     blocked = state & LCA_BLOCKED;
1153:     if (state & LCA_WANTS_LANECHANGE && blocked == 0) {
1154:         blocked = vehicle->getLaneChangeModel().checkChangeBeforeCommitting(vehicle, state);
1155:         state |= blocked;
1156:     }
1157:     vehicle->getLaneChangeModel().saveLCState(laneOffset, oldstate, state);
1158:     if (blocked == 0 && (state & LCA_WANTS_LANECHANGE)) {
1160:         vehicle->getLaneChangeModel().setFollowerGaps(neighFollow, secureBackGap);
1161:         vehicle->getLaneChangeModel().setLeaderGaps(neighLead, secureFrontGap);
1162:         vehicle->getLaneChangeModel().setOrigLeaderGaps(leader, secureOrigFrontGap);
1163:     }
1164:     if (laneOffset != 0) {
1165:         vehicle->getLaneChangeModel().saveNeighbors(laneOffset, neighFollow, neighLead);
1166:     }
1167:     return state;
1168: }
```

### A2. LC2013 complete behavior — `microsim/lcmodels/MSLCM_LC2013.cpp:48-2132`

```cpp
48: #define LOOK_FORWARD 10.
50: #define JAM_FACTOR 1.
52: #define LCA_RIGHT_IMPATIENCE -1.
53: #define CUT_IN_LEFT_SPEED_THRESHOLD 27.
55: #define LOOK_AHEAD_MIN_SPEED 0.0
56: #define LOOK_AHEAD_SPEED_MEMORY 0.9
58: #define HELP_DECEL_FACTOR 1.0
60: #define HELP_OVERTAKE  (10.0 / 3.6)
61: #define MIN_FALLBEHIND  (7.0 / 3.6)
63: #define RELGAIN_NORMALIZATION_MIN_SPEED 10.0
64: #define URGENCY 2.0
65: #define OPPOSITE_URGENCY 5.0
67: #define KEEP_RIGHT_TIME 5.0 // the number of seconds after which a vehicle should move to the right lane
69: #define KEEP_RIGHT_HEADWAY 2.0
70: #define MAX_ONRAMP_LENGTH 200.
71: #define TURN_LANE_DIST 200.0 // the distance at which a lane leading elsewhere is considered to be a turn-lane that must be avoided
73: #define LC_RESOLUTION_SPEED_LAT 0.5 // the lateral speed (in m/s) for a standing vehicle which was unable to finish a continuous LC in time (in case mySpeedLatStanding==0), see #3771
75: #define REACT_TO_STOPPED_DISTANCE 100
76: #define BLOCKER_IS_BLOCKED_TIME_THRESHOLD 5 // the time after which a blocking neighbor is treated similar to a stopped vehicle
78: #define HYST_PRECISION 10000000
93: #define DEBUG_COND (myVehicle.isSelected())
99: MSLCM_LC2013::MSLCM_LC2013(MSVehicle& v) :
100:     MSAbstractLaneChangeModel(v, LaneChangeModel::LC2013),
101:     mySpeedGainProbabilityLeft(0),
102:     mySpeedGainProbabilityRight(0),
103:     myKeepRightProbability(0),
104:     myLeadingBlockerLength(0),
105:     myLeftSpace(0),
106:     myLookAheadSpeed(LOOK_AHEAD_MIN_SPEED),
107:     myDontBrake(false),
108:     myStrategicParam(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_STRATEGIC_PARAM, 1)),
109:     myCooperativeParam(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_COOPERATIVE_PARAM, 1)),
110:     mySpeedGainParam(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_SPEEDGAIN_PARAM, 1)),
111:     myKeepRightParam(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_KEEPRIGHT_PARAM, 1)),
112:     myOppositeParam(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_OPPOSITE_PARAM, 1)),
113:     myLookaheadLeft(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_LOOKAHEADLEFT, 2.0)),
114:     mySpeedGainRight(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_SPEEDGAINRIGHT, 0.1)),
115:     mySpeedGainLookahead(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_SPEEDGAIN_LOOKAHEAD, 0)),
116:     mySpeedGainRemainTime(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_SPEEDGAIN_REMAIN_TIME, 20)),
117:     mySpeedGainUrgency(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_SPEEDGAIN_URGENCY, 50)),
118:     myRoundaboutBonus(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_COOPERATIVE_ROUNDABOUT, myCooperativeParam)),
119:     myCooperativeSpeed(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_COOPERATIVE_SPEED, myCooperativeParam)),
120:     myKeepRightAcceptanceTime(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_KEEPRIGHT_ACCEPTANCE_TIME, -1)),
121:     myOvertakeDeltaSpeedFactor(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_OVERTAKE_DELTASPEED_FACTOR, 0)),
122:     myExperimentalParam1(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_EXPERIMENTAL1, 0)) {
123:     initDerivedParameters();
135: }
137: MSLCM_LC2013::~MSLCM_LC2013() {
138:     changed();
139: }
142: void
143: MSLCM_LC2013::initDerivedParameters() {
144:     if (mySpeedGainParam <= 0) {
145:         myChangeProbThresholdRight = std::numeric_limits<long long int>::max();
146:         myChangeProbThresholdLeft = std::numeric_limits<long long int>::max();
147:     } else {
148:         myChangeProbThresholdRight = (long long int)((0.2 / mySpeedGainRight) / mySpeedGainParam * HYST_PRECISION);
149:         myChangeProbThresholdLeft = (long long int)(0.2 / mySpeedGainParam * HYST_PRECISION);
150:     }
151: }
154: bool
155: MSLCM_LC2013::debugVehicle() const {
156:     return DEBUG_COND;
157: }
160: int
161: MSLCM_LC2013::wantsChange(
162:     int laneOffset,
163:     MSAbstractLaneChangeModel::MSLCMessager& msgPass,
164:     int blocked,
165:     const std::pair<MSVehicle*, double>& leader,
166:     const std::pair<MSVehicle*, double>& follower,
167:     const std::pair<MSVehicle*, double>& neighLead,
168:     const std::pair<MSVehicle*, double>& neighFollow,
169:     const MSLane& neighLane,
170:     const std::vector<MSVehicle::LaneQ>& preb,
171:     MSVehicle** lastBlocked,
172:     MSVehicle** firstBlocked) {
188:     const int result = _wantsChange(laneOffset, msgPass, blocked, leader, follower, neighLead, neighFollow, neighLane, preb, *lastBlocked, *firstBlocked);
196:     return result;
197: }
200: double
201: MSLCM_LC2013::patchSpeed(const double min, const double wanted, const double max, const MSCFModel& cfModel) {
219:     const double newSpeed = _patchSpeed(MAX2(min, 0.0), wanted, max, cfModel);
229:     return newSpeed;
230: }
233: double
234: MSLCM_LC2013::_patchSpeed(double min, const double wanted, double max, const MSCFModel& cfModel) {
235:     int state = myOwnState;
248:     double nVSafe = wanted;
249:     bool gotOne = false;
251:     if (myLeadingBlockerLength != 0) {
252:         double space = myLeftSpace - myLeadingBlockerLength - POSITION_EPS;
258:         if (space > 0 && (myVehicle.getLane()->isNormal() || myVehicle.getCurrentEdge()->isRoundabout())) {
260:             const double vMinEmergency = myVehicle.getCarFollowModel().minNextSpeedEmergency(myVehicle.getSpeed(), &myVehicle);
261:             double safe = cfModel.stopSpeed(&myVehicle, myVehicle.getSpeed(), space, MSCFModel::CalcReason::LANE_CHANGE);
262:             max = MIN2(max, MAX2(safe, vMinEmergency));
264:             if (safe < wanted) {
266:                 if (safe < min) {
267:                     if (safe >= vMinEmergency) {
269:                         min = MAX2(vMinEmergency, safe);
270:                     }
271:                 }
277:                 nVSafe = MAX2(min, safe);
278:                 gotOne = true;
279:             }
280:         }
281:     }
283:     const double coopWeight = MAX2(0.0, MIN2(1.0, myCooperativeSpeed));
284:     int filter = (
285:             ((myOwnState & LCA_LEFT) != 0 ? LCA_MLEFT : 0) |
286:             ((myOwnState & LCA_RIGHT) != 0 ? LCA_MRIGHT : 0));
287:     for (auto i : myLCAccelerationAdvices) {
288:         double a = i.first;
289:         double v = myVehicle.getSpeed() + ACCEL2SPEED(a);
291:         if (v >= min && v <= max && (MSGlobals::gSemiImplicitEulerUpdate
297:                                      || v != -1)) {
298:             if (i.second & LCA_CHANGE_TO_HELP) {
299:                 nVSafe = MIN2(v * coopWeight + (1 - coopWeight) * wanted, nVSafe);
300:             } else if ((i.second & filter) != filter) {
308:                 continue;
309:             } else {
311:                 nVSafe = MIN2(v, nVSafe);
312:             }
313:             gotOne = true;
319:         } else {
320:             if (v < min) {
326:             } else {
332:             }
333:         }
334:     }
336:     if (gotOne && !myDontBrake) {
342:         return nVSafe;
343:     }
346:     if ((state & LCA_WANTS_LANECHANGE) != 0 && (state & LCA_BLOCKED) != 0) {
347:         if ((state & LCA_STRATEGIC) != 0) {
355:             return (max + wanted) /  2.0;
356:         } else if ((state & LCA_COOPERATIVE) != 0) {
358:             if ((state & LCA_BLOCKED_BY_LEADER) != 0) {
364:                 if (wanted >= 0.) {
365:                     return (MAX2(0., min) + wanted) /  2.0;
366:                 } else {
367:                     return wanted;
368:                 }
369:             }
370:             if ((state & LCA_BLOCKED_BY_FOLLOWER) != 0) {
376:                 return (max + wanted) /  2.0;
377:             }
384:         }
385:     }
416:     if ((state & LCA_AMBLOCKINGLEADER) != 0 && myCooperativeSpeed >= 0) {
422:         return (max + wanted) /  2.0;
423:     }
425:     if ((state & LCA_AMBLOCKINGFOLLOWER_DONTBRAKE) != 0) {
438:     }
439:     if (!myVehicle.getLane()->getEdge().hasLaneChanger()) {
441:         changed();
442:     }
443:     return wanted;
444: }
447: void*
448: MSLCM_LC2013::inform(void* info, MSVehicle* sender) {
449:     UNUSED_PARAMETER(sender);
450:     Info* pinfo = (Info*)info;
451:     assert(pinfo->first >= 0 || !MSGlobals::gSemiImplicitEulerUpdate);
452:     addLCSpeedAdvice(pinfo->first, LCA_CHANGE_TO_HELP);
453:     myOwnState |= pinfo->second;
464:     delete pinfo;
465:     return (void*) true;
466: }
468: double
469: MSLCM_LC2013::overtakeDistance(const MSVehicle* follower, const MSVehicle* leader, const double gap, double followerSpeed, double leaderSpeed) {
470:     followerSpeed = followerSpeed == INVALID_SPEED ? follower->getSpeed() : followerSpeed;
471:     leaderSpeed = leaderSpeed == INVALID_SPEED ? leader->getSpeed() : leaderSpeed;
472:     double overtakeDist = (gap // drive to back of leader
473:                            + leader->getVehicleType().getLengthWithGap() // drive to front of leader
474:                            + follower->getVehicleType().getLength() // follower back reaches leader front
475:                            + leader->getCarFollowModel().getSecureGap( // save gap to leader
476:                                leader, follower, leaderSpeed, followerSpeed, follower->getCarFollowModel().getMaxDecel()));
477:     return MAX2(overtakeDist, 0.);
478: }
481: double
482: MSLCM_LC2013::informLeader(MSAbstractLaneChangeModel::MSLCMessager& msgPass,
483:                            int blocked,
484:                            int dir,
485:                            const std::pair<MSVehicle*, double>& neighLead,
486:                            double remainingSeconds) {
487:     double plannedSpeed = myVehicle.getSpeed();
488:     if (!isOpposite()) {
489:         plannedSpeed = MIN2(plannedSpeed,
490:                             myVehicle.getCarFollowModel().stopSpeed(&myVehicle, myVehicle.getSpeed(), myLeftSpace - myLeadingBlockerLength));
491:     }
492:     for (auto i : myLCAccelerationAdvices) {
493:         const double a = i.first;
494:         if (a >= -myVehicle.getCarFollowModel().getMaxDecel()) {
495:             plannedSpeed = MIN2(plannedSpeed, myVehicle.getSpeed() + ACCEL2SPEED(a));
496:         }
497:     }
505:     const MSVehicle* const nv = neighLead.first;
506:     if (nv == nullptr) {
508:         return plannedSpeed;
509:     }
510:     const double neighNextSpeed = MIN2(nv->getSpeed() - ACCEL2SPEED(MAX2(1.0, -nv->getAcceleration())),
512:             nv->nextStopDist() <= nv->getLane()->getLength() ? nv->getCarFollowModel().minNextSpeed(nv->getSpeed(), nv) : nv->getSpeed());
513:     double neighNextGap;
514:     if (MSGlobals::gSemiImplicitEulerUpdate) {
515:         neighNextGap = neighLead.second + SPEED2DIST(neighNextSpeed - plannedSpeed);
516:     } else {
517:         neighNextGap = neighLead.second + SPEED2DIST((nv->getSpeed() + neighNextSpeed) / 2) - SPEED2DIST((myVehicle.getSpeed() + plannedSpeed) / 2);
518:     }
519:     if ((blocked & LCA_BLOCKED_BY_LEADER) != 0) {
520:         if (MSLCHelper::divergentRoute(myVehicle, *nv)) {
522:             return plannedSpeed;
523:         }
531:         double overtakeTime;
532:         const double overtakeDist = overtakeDistance(&myVehicle, nv, neighLead.second);
533:         const double dv = plannedSpeed - nv->getSpeed();
535:         if (dv > myOvertakeDeltaSpeedFactor * myVehicle.getLane()->getSpeedLimit()) {
536:             overtakeTime = overtakeDist / dv;
537:         } else if (nv->getWaitingSeconds() > BLOCKER_IS_BLOCKED_TIME_THRESHOLD
538:                    && !isOpposite()
539:                    && (myVehicle.getVehicleType().getLengthWithGap() + nv->getVehicleType().getLengthWithGap()) <= myLeftSpace) {
541:             overtakeTime = remainingSeconds - 1;
542:         } else {
544:             overtakeTime = remainingSeconds + 1;
545:         }
561:         if ((dv < myOvertakeDeltaSpeedFactor * myVehicle.getLane()->getSpeedLimit()
563:                 || (dir == LCA_MLEFT && avoidOvertakeRight(neighLead.first))
565:                 || (MSGlobals::gSemiImplicitEulerUpdate && myLeftSpace - myLeadingBlockerLength - myVehicle.getCarFollowModel().brakeGap(myVehicle.getSpeed()) < overtakeDist)
567:                 || (!MSGlobals::gSemiImplicitEulerUpdate && myLeftSpace - myLeadingBlockerLength - myVehicle.getCarFollowModel().brakeGap(myVehicle.getSpeed(), getCarFollowModel().getMaxDecel(), 0.) < overtakeDist)
569:                 || (remainingSeconds < overtakeTime && (MSGlobals::gSemiImplicitEulerUpdate || !nv->isStopped())))
571:                 && (!neighLead.first->isStopped() || (isOpposite() && neighLead.second >= 0))) {
573:             msgPass.informNeighLeader(new Info(std::numeric_limits<double>::max(), dir | LCA_AMBLOCKINGLEADER), &myVehicle);
576:             double targetSpeed = MAX3(myVehicle.getCarFollowModel().minNextSpeed(myVehicle.getSpeed(), &myVehicle),
577:                                       getCarFollowModel().followSpeed(&myVehicle, myVehicle.getSpeed(), neighNextGap, neighNextSpeed, nv->getCarFollowModel().getMaxDecel()),
579:                                       (myVehicle.getLane()->isNormal() || myVehicle.getCurrentEdge()->isRoundabout()) ? 0 : ACCEL2SPEED(myVehicle.getCarFollowModel().getMaxAccel()));
580:             if (targetSpeed < myVehicle.getSpeed()) {
582:                 const double decel = remainingSeconds == 0. ? myVehicle.getCarFollowModel().getMaxDecel() :
583:                                      MIN2(myVehicle.getCarFollowModel().getMaxDecel(),
584:                                           MAX2(MIN_FALLBEHIND, (myVehicle.getSpeed() - targetSpeed) / remainingSeconds));
585:                 const double nextSpeed = MIN2(plannedSpeed, MAX2(0.0, myVehicle.getSpeed() - ACCEL2SPEED(decel)));
605:                 addLCSpeedAdvice(nextSpeed, dir);
606:                 return nextSpeed;
607:             } else {
627:                 addLCSpeedAdvice(targetSpeed, dir);
628:                 return plannedSpeed;
629:             }
630:         } else {
646:             if (nv->getWaitingSeconds() <= BLOCKER_IS_BLOCKED_TIME_THRESHOLD) {
647:                 msgPass.informNeighLeader(new Info(nv->getSpeed(), dir | LCA_AMBLOCKINGLEADER), &myVehicle);
648:             }
649:             return -1;  // XXX: using -1 is ambiguous for the ballistic update! Currently this is being catched in patchSpeed() (Leo), consider returning INVALID_SPEED, refs. #2577
650:         }
651:     } else { // (remainUnblocked)
653:         const double targetSpeed = MAX2(
654:                                        myVehicle.getCarFollowModel().minNextSpeed(myVehicle.getSpeed(), &myVehicle),
655:                                        getCarFollowModel().followSpeed(&myVehicle, myVehicle.getSpeed(), neighNextGap, neighNextSpeed, nv->getCarFollowModel().getMaxDecel()));
656:         addLCSpeedAdvice(targetSpeed, dir);
669:         return MIN2(targetSpeed, plannedSpeed);
670:     }
671: }
673: void
674: MSLCM_LC2013::informFollower(MSAbstractLaneChangeModel::MSLCMessager& msgPass,
675:                              int blocked,
676:                              int dir,
677:                              const std::pair<MSVehicle*, double>& neighFollow,
678:                              double remainingSeconds,
679:                              double plannedSpeed) {
681:     MSVehicle* nv = neighFollow.first;
682:     const double plannedAccel = SPEED2ACCEL(MAX2(MIN2(getCarFollowModel().getMaxAccel(), plannedSpeed - myVehicle.getSpeed()), -getCarFollowModel().getMaxDecel()));
692:     if (nv != nullptr && MSLCHelper::unwillingToHelp(myVehicle, plannedSpeed, *nv)) {
699:         return;
700:     }
702:     if ((blocked & LCA_BLOCKED_BY_FOLLOWER) != 0 && nv != nullptr) {
703:         if (MSLCHelper::divergentRoute(myVehicle, *nv)) {
705:             return;
706:         }
714:         if (MAX2(plannedSpeed, 0.) - nv->getSpeed() >= HELP_OVERTAKE) {
715:             const double neededGap = nv->getCarFollowModel().getSecureGap(nv, &myVehicle, nv->getSpeed(), plannedSpeed, myVehicle.getCarFollowModel().getMaxDecel());
716:             if ((neededGap - neighFollow.second) / remainingSeconds < (MAX2(plannedSpeed, 0.) - nv->getSpeed())) {
724:                 msgPass.informNeighFollower(new Info(MAX2(plannedSpeed, 0.) - HELP_OVERTAKE, dir | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
725:                 return;
726:             }
727:         }
734:         const double helpDecel = nv->getCarFollowModel().getMaxDecel() * HELP_DECEL_FACTOR;
737:         double neighNewSpeed;
739:         double neighNewSpeed1s;
741:         double dv, decelGap;
743:         if (MSGlobals::gSemiImplicitEulerUpdate) {
745:             neighNewSpeed = MAX2(0., nv->getSpeed() - ACCEL2SPEED(helpDecel));
746:             neighNewSpeed1s = MAX2(0., nv->getSpeed() - helpDecel); // TODO: consider introduction of a configurable anticipationTime here (see far below in the !blocked part). Refs. #2578
749:             dv = plannedSpeed - neighNewSpeed1s; // XXX: what is this quantity (if TS!=1)?
756:             decelGap = neighFollow.second + dv;
757:         } else {
762:             neighNewSpeed = nv->getSpeed() - ACCEL2SPEED(helpDecel);
763:             neighNewSpeed1s = nv->getSpeed() - helpDecel;
765:             dv = myVehicle.getSpeed() - nv->getSpeed(); // current velocity difference
766:             decelGap = getCarFollowModel().gapExtrapolation(1., neighFollow.second, myVehicle.getSpeed(),
767:                        nv->getSpeed(), plannedAccel, -helpDecel, myVehicle.getMaxSpeedOnLane(), nv->getMaxSpeedOnLane());
768:         }
770:         const double secureGap = nv->getCarFollowModel().getSecureGap(nv, &myVehicle, MAX2(neighNewSpeed1s, 0.),
771:                                  MAX2(plannedSpeed, 0.), myVehicle.getCarFollowModel().getMaxDecel());
773:         const double onRampThreshold = myVehicle.getLane()->getSpeedLimit() * 0.8 * myExperimentalParam1 * (1 - myVehicle.getImpatience());
791:         if (dir == LCA_MLEFT
792:                 && myVehicle.getLane()->isAccelLane()
793:                 && neighNewSpeed1s < onRampThreshold) {
794:             return;
795:         }
797:         if (decelGap > 0 && decelGap >= secureGap) {
805:             double vsafe, vsafe1;
807:             if (MSGlobals::gSemiImplicitEulerUpdate) {
810:                 vsafe1 = MAX2(neighNewSpeed, nv->getCarFollowModel().followSpeed(
811:                                   nv, nv->getSpeed(), neighFollow.second + SPEED2DIST(plannedSpeed), plannedSpeed, getCarFollowModel().getMaxDecel()));
812:                 vsafe = MAX2(neighNewSpeed, nv->getCarFollowModel().followSpeed(
813:                                  nv, nv->getSpeed(), neighFollow.second + SPEED2DIST(plannedSpeed - vsafe1), plannedSpeed, getCarFollowModel().getMaxDecel()));
815:             } else {
821:                 double nextGap = getCarFollowModel().gapExtrapolation(TS,
822:                                  neighFollow.second, myVehicle.getSpeed(),
823:                                  nv->getSpeed(), plannedAccel, 0,
824:                                  myVehicle.getMaxSpeedOnLane(), nv->getMaxSpeedOnLane());
832:                 vsafe1 = MIN2(nv->getSpeed(), MAX2(neighNewSpeed,
833:                                                    nv->getCarFollowModel().followSpeed(nv,
834:                                                            nv->getSpeed(), nextGap,
835:                                                            MAX2(0., plannedSpeed),
836:                                                            getCarFollowModel().getMaxDecel())));
840:                 double decel2 = SPEED2ACCEL(nv->getSpeed() - vsafe1);
841:                 nextGap = getCarFollowModel().gapExtrapolation(TS,
842:                           neighFollow.second, myVehicle.getSpeed(),
843:                           nv->getSpeed(), plannedAccel, -decel2,
844:                           myVehicle.getMaxSpeedOnLane(), nv->getMaxSpeedOnLane());
850:                 vsafe = MIN2(nv->getSpeed(), MAX2(neighNewSpeed,
851:                                                   nv->getCarFollowModel().followSpeed(nv,
852:                                                           nv->getSpeed(), nextGap,
853:                                                           MAX2(0., plannedSpeed),
854:                                                           getCarFollowModel().getMaxDecel())));
856:                 assert(vsafe >= vsafe1 - NUMERICAL_EPS);
869:                 double nextSecureGap = nv->getCarFollowModel().getSecureGap(nv, &myVehicle, vsafe, plannedSpeed, getCarFollowModel().getMaxDecel());
871:                 if (nextGap < nextSecureGap) {
873:                     vsafe = neighNewSpeed;
874:                 }
884:             }
885:             msgPass.informNeighFollower(
886:                 new Info(vsafe, dir | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
899:         } else if ((MSGlobals::gSemiImplicitEulerUpdate && dv > 0 && dv * remainingSeconds > (secureGap - decelGap + POSITION_EPS))
900:                    || (!MSGlobals::gSemiImplicitEulerUpdate && dv > 0 && dv * (remainingSeconds - 1) > secureGap - decelGap + POSITION_EPS)
901:                   ) {
916:             msgPass.informNeighFollower(new Info(neighNewSpeed, dir | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
922:         } else if (dir == LCA_MRIGHT && nv->getLaneChangeModel().avoidOvertakeRight(&myVehicle)) {
924:             const double vhelp = MAX2(neighNewSpeed, HELP_OVERTAKE);
925:             msgPass.informNeighFollower(new Info(vhelp, dir | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
931:         } else {
932:             double vhelp = MAX2(nv->getSpeed(), myVehicle.getSpeed() + HELP_OVERTAKE);
935:             if (nv->getSpeed() > myVehicle.getSpeed() &&
936:                     ((dir == LCA_MRIGHT && myVehicle.getWaitingSeconds() > LCA_RIGHT_IMPATIENCE) // NOTE: it might be considered to use myVehicle.getAccumulatedWaitingSeconds() > LCA_RIGHT_IMPATIENCE instead (Leo). Refs. #2578
937:                      || (dir == LCA_MLEFT && plannedSpeed > CUT_IN_LEFT_SPEED_THRESHOLD) // VARIANT_22 (slowDownLeft)
939:                      || (dir == LCA_MLEFT && myVehicle.getLane()->getLength() > MAX_ONRAMP_LENGTH)
940:                     )) {
946:                 vhelp = MAX2(neighNewSpeed, myVehicle.getSpeed() + HELP_OVERTAKE);
954:                 if (MSGlobals::gSemiImplicitEulerUpdate) {
956:                     if ((nv->getSpeed() - myVehicle.getSpeed()) / helpDecel < remainingSeconds) {
969:                         msgPass.informNeighFollower(new Info(vhelp, dir | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
970:                         return;
971:                     }
972:                 } else {
979:                     const double gapAfterRemainingSecs = getCarFollowModel().gapExtrapolation(
980:                             remainingSeconds, neighFollow.second, myVehicle.getSpeed(), nv->getSpeed(), 0, -helpDecel, myVehicle.getMaxSpeedOnLane(), nv->getMaxSpeedOnLane());
981:                     const double secureGapAfterRemainingSecs = nv->getCarFollowModel().getSecureGap(nv, &myVehicle,
982:                             MAX2(nv->getSpeed() - remainingSeconds * helpDecel, 0.), myVehicle.getSpeed(), myVehicle.getCarFollowModel().getMaxDecel());
983:                     if (gapAfterRemainingSecs >= secureGapAfterRemainingSecs) { // XXX: here it would be wise to check whether there is enough space for eventual braking if the maneuver doesn't succeed
991:                         msgPass.informNeighFollower(new Info(neighNewSpeed, dir | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
992:                         return;
993:                     }
994:                 }
997:             }
1009:             msgPass.informNeighFollower(new Info(vhelp, dir | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
1011:             const double overtakeDist = overtakeDistance(nv, &myVehicle, neighFollow.second, vhelp, plannedSpeed);
1013:             const double needDV = overtakeDist / remainingSeconds;
1015:             addLCSpeedAdvice(MAX2(vhelp - needDV, myVehicle.getSpeed() - ACCEL2SPEED(myVehicle.getCarFollowModel().getMaxDecel())), dir);
1030:         }
1031:     } else if (neighFollow.first != nullptr && (blocked & LCA_BLOCKED_BY_LEADER)) {
1033:         const double vsafe = MSLCHelper::getSpeedPreservingSecureGap(myVehicle, *neighFollow.first, neighFollow.second, plannedSpeed);
1034:         msgPass.informNeighFollower(new Info(vsafe, dir), &myVehicle);
1041:     }
1042: }
1045: void
1046: MSLCM_LC2013::prepareStep() {
1047:     MSAbstractLaneChangeModel::prepareStep();
1049:     if (!isChangingLanes()) {
1050:         myOwnState = (myOwnState & LCA_STRATEGIC) ? (myOwnState & LCA_WANTS_LANECHANGE) : 0;
1051:     }
1052:     myLeadingBlockerLength = 0;
1053:     myLeftSpace = 0;
1054:     myLCAccelerationAdvices.clear();
1055:     myDontBrake = false;
1057:     if (mySigma > 0 && !isChangingLanes()) {
1059:         const double maxDist = SPEED2DIST(myVehicle.getVehicleType().getMaxSpeedLat());
1060:         const double oldPosLat = myVehicle.getLateralPositionOnLane();
1061:         const double overlap = myVehicle.getLateralOverlap();
1062:         double scaledDelta;
1063:         if (overlap > 0) {
1065:             scaledDelta = MIN2(overlap, maxDist);
1066:             if (myVehicle.getLateralPositionOnLane() > 0) {
1067:                 scaledDelta *= -1;
1068:             }
1069:         } else {
1071:             double deltaPosLat = OUProcess::step(oldPosLat,
1072:                                                  myVehicle.getActionStepLengthSecs(),
1073:                                                  MAX2(NUMERICAL_EPS, (1 - mySigma) * 100), mySigma) - oldPosLat;
1074:             deltaPosLat = MAX2(MIN2(deltaPosLat, maxDist), -maxDist);
1075:             scaledDelta = deltaPosLat * myVehicle.getSpeed() / myVehicle.getLane()->getSpeedLimit();
1076:         }
1077:         myVehicle.setLateralPositionOnLane(oldPosLat + scaledDelta);
1078:         setSpeedLat(DIST2SPEED(scaledDelta));
1079:     } else {
1080:         resetSpeedLat();
1081:     }
1082: }
1085: void
1086: MSLCM_LC2013::changed() {
1087:     myOwnState = 0;
1088:     mySpeedGainProbabilityLeft = 0;
1089:     mySpeedGainProbabilityRight = 0;
1090:     myKeepRightProbability = 0;
1091:     if (myVehicle.getBestLaneOffset() == 0) {
1094:         myLeadingBlockerLength = 0;
1095:         myLeftSpace = 0;
1096:     }
1097:     myLookAheadSpeed = LOOK_AHEAD_MIN_SPEED;
1098:     myLCAccelerationAdvices.clear();
1099:     myDontBrake = false;
1100:     myLeadingBlockerLength = 0;
1101: }
1104: void
1105: MSLCM_LC2013::resetState() {
1106:     myOwnState = 0;
1107:     mySpeedGainProbabilityLeft = 0;
1108:     mySpeedGainProbabilityRight = 0;
1109:     myKeepRightProbability = 0;
1110:     myLeadingBlockerLength = 0;
1111:     myLeftSpace = 0;
1112:     myLookAheadSpeed = LOOK_AHEAD_MIN_SPEED;
1113:     myLCAccelerationAdvices.clear();
1114:     myDontBrake = false;
1115: }
1118: int
1119: MSLCM_LC2013::_wantsChange(
1120:     int laneOffset,
1121:     MSAbstractLaneChangeModel::MSLCMessager& msgPass,
1122:     int blocked,
1123:     const std::pair<MSVehicle*, double>& leader,
1124:     const std::pair<MSVehicle*, double>& follower,
1125:     const std::pair<MSVehicle*, double>& neighLead,
1126:     const std::pair<MSVehicle*, double>& neighFollow,
1127:     const MSLane& neighLane,
1128:     const std::vector<MSVehicle::LaneQ>& preb,
1129:     MSVehicle* lastBlocked,
1130:     MSVehicle* firstBlocked) {
1131:     assert(laneOffset == 1 || laneOffset == -1);
1132:     const SUMOTime currentTime = MSNet::getInstance()->getCurrentTimeStep();
1134:     MSVehicle::LaneQ curr, neigh, best;
1135:     int bestLaneOffset = 0;
1140:     double currentDist = 0;
1141:     double neighDist = 0;
1142:     int currIdx = 0;
1143:     const bool checkOpposite = &neighLane.getEdge() != &myVehicle.getLane()->getEdge();
1144:     const MSLane* prebLane = myVehicle.getLane();
1145:     if (prebLane->getEdge().isInternal()) {
1147:         if (isOpposite()) {
1148:             prebLane = prebLane->getNormalPredecessorLane();
1149:         } else {
1150:             prebLane = prebLane->getLinkCont()[0]->getLane();
1151:         }
1152:     }
1154:     const int prebOffset = laneOffset;
1155:     for (int p = 0; p < (int) preb.size(); ++p) {
1159:         if (preb[p].lane == prebLane && p + laneOffset >= 0) {
1160:             assert(p + prebOffset < (int)preb.size());
1161:             curr = preb[p];
1162:             neigh = preb[p + prebOffset];
1163:             currentDist = curr.length;
1164:             neighDist = neigh.length;
1165:             bestLaneOffset = curr.bestLaneOffset;
1166:             if (bestLaneOffset == 0 && preb[p + prebOffset].bestLaneOffset == 0 && !checkOpposite) {
1176:                 bestLaneOffset = prebOffset;
1177:             }
1178:             best = preb[p + bestLaneOffset];
1179:             currIdx = p;
1180:             break;
1181:         }
1182:     }
1183:     assert(curr.lane != nullptr);
1184:     assert(neigh.lane != nullptr);
1185:     assert(best.lane != nullptr);
1187:     const bool right = (laneOffset == -1);
1188:     const double posOnLane = getForwardPos();
1189:     double driveToNextStop = -std::numeric_limits<double>::max();
1190:     if (myVehicle.nextStopDist() < std::numeric_limits<double>::max()
1191:             && &myVehicle.getNextStop().lane->getEdge() == &myVehicle.getLane()->getEdge()) {
1195:         driveToNextStop = myVehicle.nextStopDist();
1196:         const double stopPos = posOnLane + myVehicle.nextStopDist() - myVehicle.getLastStepDist();
1208:         currentDist = MAX2(currentDist, stopPos);
1209:         neighDist = MAX2(neighDist, stopPos);
1210:     }
1211:     const int lca = (right ? LCA_RIGHT : LCA_LEFT);
1212:     const int myLca = (right ? LCA_MRIGHT : LCA_MLEFT);
1213:     const int lcaCounter = (right ? LCA_LEFT : LCA_RIGHT);
1214:     bool changeToBest = (right && bestLaneOffset < 0) || (!right && bestLaneOffset > 0);
1216:     int ret = (myOwnState & 0xffff0000);
1217:     int req = 0; // the request to change or stay
1219:     ret = slowDownForBlocked(lastBlocked, ret);
1220:     if (lastBlocked != firstBlocked) {
1221:         ret = slowDownForBlocked(firstBlocked, ret);
1222:     }
1257:     if (myVehicle.getSpeed() > myLookAheadSpeed) {
1258:         myLookAheadSpeed = myVehicle.getSpeed();
1259:     } else {
1261:         const double memoryFactor = 1. - (1. - LOOK_AHEAD_SPEED_MEMORY) * myVehicle.getActionStepLengthSecs();
1262:         assert(memoryFactor > 0.);
1263:         myLookAheadSpeed = MAX2(LOOK_AHEAD_MIN_SPEED,
1264:                                 (memoryFactor * myLookAheadSpeed + (1 - memoryFactor) * myVehicle.getSpeed()));
1265:     }
1266:     double laDist = myLookAheadSpeed * LOOK_FORWARD * myStrategicParam * (right ? 1 : myLookaheadLeft);
1267:     laDist += myVehicle.getVehicleType().getLengthWithGap() *  2.;
1268:     const bool hasStoppedLeader = leader.first != 0 && leader.first->isStopped() && leader.second < (currentDist - posOnLane);
1269:     const bool hasBidiLeader = myVehicle.getLane()->getBidiLane() != nullptr && MSLCHelper::isBidiLeader(leader.first, curr.bestContinuations);
1270:     const bool hasBidiNeighLeader = neighLane.getBidiLane() != nullptr && MSLCHelper::isBidiLeader(neighLead.first, neigh.bestContinuations);
1271:     const bool hasJunctionLeader = leader.first != nullptr && leader.first == neighLead.first;
1273:     if (bestLaneOffset == 0 && hasBidiLeader) {
1275:         laDist = 0;
1276:     } else if (bestLaneOffset == 0 && hasStoppedLeader) {
1280:         laDist = 0.5 * (myVehicle.getVehicleType().getLengthWithGap()
1281:                         + leader.first->getVehicleType().getLengthWithGap()
1282:                         + leader.second);
1283:     } else if (bestLaneOffset == laneOffset && neighLead.first != 0 && (neighLead.first->isStopped() || hasBidiNeighLeader) && neighLead.second < (currentDist - posOnLane)) {
1285:         if (isOpposite()) {
1287:             laDist = (myVehicle.getVehicleType().getLengthWithGap()
1288:                       + neighLead.first->getVehicleType().getLengthWithGap()
1289:                       + neighLead.second);
1290:         } else if (!hasStoppedLeader &&
1291:                    ((neighLead.second + myVehicle.getVehicleType().getLengthWithGap() + neighLead.first->getVehicleType().getLengthWithGap()) < (currentDist - posOnLane)
1292:                     || hasBidiNeighLeader)) {
1295:             changeToBest = false;
1296:         }
1297:     }
1298:     if (myStrategicParam < 0) {
1299:         laDist = -1e3; // never perform strategic change
1300:     }
1313:     const double roundaboutBonus = MSLCHelper::getRoundaboutDistBonus(myVehicle, myRoundaboutBonus, curr, neigh, best);
1314:     currentDist += roundaboutBonus;
1315:     neighDist += roundaboutBonus;
1317:     const double usableDist = MAX2(currentDist - posOnLane - best.occupation * JAM_FACTOR, driveToNextStop);
1319:     const double maxJam = MAX2(preb[currIdx + prebOffset].occupation, preb[currIdx].occupation);
1320:     const double vMax = myVehicle.getLane()->getVehicleMaxSpeed(&myVehicle);
1321:     const double neighVMax = neighLane.getVehicleMaxSpeed(&myVehicle);
1323:     double thisLaneVSafe = vMax;
1324:     const bool checkOverTakeRight = avoidOvertakeRight(neighLead.first, true);
1326:     double neighLeftPlace = MAX2(0.0, neighDist - posOnLane - maxJam);
1327:     if (neighLead.first != 0 && neighLead.first->isStopped()) {
1328:         neighLeftPlace = MIN2(neighLeftPlace, neighLead.second);
1329:     }
1352:     bool changeLeftToAvoidOvertakeRight = false;
1353:     if (changeToBest && bestLaneOffset == curr.bestLaneOffset
1354:             && currentDistDisallows(usableDist, bestLaneOffset, laDist)) {
1356:         ret = ret | lca | LCA_STRATEGIC | LCA_URGENT;
1357:     } else {
1359:         if (neighLead.first != 0 && checkOverTakeRight && !right) {
1362:             const MSVehicle* nv = neighLead.first;
1363:             double deltaV = 0.;
1364:             double vSafe = 0.;
1365:             if (canOvertakeRight(nv, neighLead.second, vMax - neighLane.getVehicleMaxSpeed(nv), HELP_OVERTAKE, vSafe, deltaV)) {
1366:                 if (mySpeedGainProbabilityLeft < myChangeProbThresholdLeft) {
1367:                     vSafe = MAX2(vSafe, nv->getSpeed());
1368:                 }
1369:                 thisLaneVSafe = MIN2(thisLaneVSafe, vSafe);
1370:                 addLCSpeedAdvice(vSafe, myLca);
1372:                 const double deltaGapFuture = deltaV * 8;
1373:                 const double vSafeFuture = getCarFollowModel().followSpeed(
1374:                                                &myVehicle, myVehicle.getSpeed(), neighLead.second - deltaGapFuture, nv->getSpeed(), nv->getCarFollowModel().getMaxDecel());
1375:                 if (vSafeFuture < vSafe) {
1376:                     const double relativeGain = deltaV / MAX2(vMax,
1377:                                                 RELGAIN_NORMALIZATION_MIN_SPEED);
1378:                     mySpeedGainProbabilityLeft += (long long int)(myVehicle.getActionStepLengthSecs() * relativeGain * HYST_PRECISION);
1379:                     changeLeftToAvoidOvertakeRight = true;
1380:                 }
1393:             }
1394:         }
1395:         const bool currFreeUntilNeighEnd = leader.first == nullptr || neighDist - posOnLane <= leader.second;
1396:         const double overtakeDist = (leader.first == 0 || hasBidiLeader ? -1 :
1397:                                      leader.second + myVehicle.getVehicleType().getLength() + leader.first->getVehicleType().getLengthWithGap());
1398:         const double overtakeDist2 = (neighLead.first == 0 || !neighLead.first->isStopped() ? -1 :
1399:                                       neighLead.second + myVehicle.getVehicleType().getLength() + neighLead.first->getVehicleType().getLengthWithGap());
1400:         if (leader.first != 0 && (leader.first->isStopped() || hasBidiLeader) && leader.second < REACT_TO_STOPPED_DISTANCE
1402:                 && MIN2(neighDist, currentDist) - posOnLane > overtakeDist
1404:                 && (!checkOverTakeRight || !right)
1405:                 && myStrategicParam >= 0
1406:                 && (neighLead.first == 0 || !neighLead.first->isStopped()
1408:                     || neighLead.second > overtakeDist
1410:                     || (overtakeDist2 > leader.second && hasFreeLane(laneOffset, neighLead)))) {
1412:             currentDist = myVehicle.getPositionOnLane() + leader.second;
1424:             ret = ret | lca | LCA_STRATEGIC | LCA_URGENT;
1425:         } else if (!changeToBest && currentDistDisallows(neighLeftPlace, abs(bestLaneOffset) + 2, laDist) && !hasBidiLeader) {
1437:             ret = ret | LCA_STAY | LCA_STRATEGIC;
1438:         } else if (bestLaneOffset == 0 && (neighLeftPlace * 2. < laDist)) {
1448:             ret = ret | LCA_STAY | LCA_STRATEGIC;
1449:         } else if (bestLaneOffset == 0
1450:                    && (leader.first == 0 || !leader.first->isStopped())
1451:                    && !hasBidiLeader
1452:                    && neigh.bestContinuations.back()->getLinkCont().size() != 0
1453:                    && roundaboutBonus == 0
1454:                    && !checkOpposite
1455:                    && ((myStrategicParam >= 0 && neighDist < TURN_LANE_DIST)
1457:                        || (myStrategicParam < 0 && currFreeUntilNeighEnd))
1458:                   ) {
1467:             ret = ret | LCA_STAY | LCA_STRATEGIC;
1468:         }
1469:     }
1477:     getCanceledState(laneOffset) |= ret | blocked;
1478:     ret = myVehicle.influenceChangeDecision(ret);
1479:     if ((ret & lcaCounter) != 0) {
1481:         ret &= ~(LCA_TRACI | lcaCounter | LCA_URGENT);
1482:     }
1489:     if ((ret & LCA_STAY) != 0) {
1491:         ret = getCanceledState(laneOffset);
1492:         return ret;
1493:     }
1494:     if ((ret & LCA_URGENT) != 0) {
1497:         myLeftSpace = currentDist - posOnLane;
1498:         if (changeToBest && abs(bestLaneOffset) > 1 && myVehicle.getNumRemainingEdges() > 1) {
1500:             myLeadingBlockerLength = MAX2(getExtraReservation(bestLaneOffset, neighDist - currentDist), myLeadingBlockerLength);
1506:         }
1510:         const bool canContinue = curr.bestContinuations.size() > 1;
1511:         bool canReserve = MSLCHelper::updateBlockerLength(myVehicle, neighLead.first, lcaCounter, myLeftSpace - POSITION_EPS, canContinue, myLeadingBlockerLength);
1512:         if (firstBlocked != neighLead.first) {
1513:             canReserve &= MSLCHelper::updateBlockerLength(myVehicle, firstBlocked, lcaCounter, myLeftSpace - POSITION_EPS, canContinue, myLeadingBlockerLength);
1514:         }
1520:         if (!canReserve && !isOpposite()) {
1523:             myDontBrake = canContinue;
1524:         }
1526:         const int remainingLanes = MAX2(1, abs(bestLaneOffset));
1527:         const double urgency = isOpposite() ? OPPOSITE_URGENCY : URGENCY;
1528:         const double remainingSeconds = ((ret & LCA_TRACI) == 0 ?
1530:                                          MAX2(STEPS2TIME(TS), myLeftSpace / MAX2(myLookAheadSpeed, NUMERICAL_EPS) / remainingLanes / urgency) :
1531:                                          myVehicle.getInfluencer().changeRequestRemainingSeconds(currentTime));
1532:         if (!hasBidiNeighLeader && !hasJunctionLeader) {
1533:             const double plannedSpeed = informLeader(msgPass, blocked, myLca, neighLead, remainingSeconds);
1536:             if (plannedSpeed >= 0 || (!MSGlobals::gSemiImplicitEulerUpdate && plannedSpeed != -1)) {
1538:                 const bool hasBidiNeighFollower = neighLane.getBidiLane() != nullptr && MSLCHelper::isBidiFollower(&myVehicle, neighFollow.first);
1539:                 if (!hasBidiNeighFollower) {
1540:                     informFollower(msgPass, blocked, myLca, neighFollow, remainingSeconds, plannedSpeed);
1541:                 }
1542:             }
1553:         } else {
1564:         }
1568:         ret = getCanceledState(laneOffset);
1569:         return ret;
1570:     }
1574:     const bool acceleratingLeader = (neighLead.first != 0 && neighLead.first->getAcceleration() > 0)
1575:                                     || (leader.first != 0 && leader.first->getAcceleration() > 0);
1576:     double neighLaneVSafe = MIN2(neighVMax, anticipateFollowSpeed(neighLead, neighDist, neighVMax, acceleratingLeader));
1577:     thisLaneVSafe = MIN2(thisLaneVSafe, anticipateFollowSpeed(leader, currentDist, vMax, acceleratingLeader));
1586:     double inconvenience = laneOffset < 0
1587:                            ? (double)mySpeedGainProbabilityLeft / (double)myChangeProbThresholdRight
1588:                            : (double)mySpeedGainProbabilityRight / (double)myChangeProbThresholdLeft;
1590:     const double relSpeedDiff = thisLaneVSafe == 0 ? 0 : (thisLaneVSafe - neighLaneVSafe) / MAX2(thisLaneVSafe, neighLaneVSafe);
1591:     inconvenience = MAX2(relSpeedDiff, inconvenience);
1592:     inconvenience = MIN2(1.0, inconvenience);
1594:     const bool speedGainInconvenient = inconvenience > myCooperativeParam;
1595:     const bool neighOccupancyInconvenient = neigh.lane->getBruttoOccupancy() > curr.lane->getBruttoOccupancy();
1611:     if (roundaboutBonus > 0) {
1624:         if (lca == LCA_LEFT) {
1627:             if (MSGlobals::gSemiImplicitEulerUpdate || !neighOccupancyInconvenient) {
1629:                 req = ret | lca | LCA_COOPERATIVE;
1630:             }
1631:         } else {
1633:             if (MSGlobals::gSemiImplicitEulerUpdate || neighOccupancyInconvenient) {
1635:                 req = ret | LCA_STAY | LCA_COOPERATIVE;
1636:             }
1637:         }
1638:         if (!cancelRequest(req, laneOffset)) {
1639:             return ret | req;
1640:         }
1641:     }
1645:     if (right) {
1646:         if (bestLaneOffset == 0 && myVehicle.getLane()->getSpeedLimit() > 80. / 3.6 && myLookAheadSpeed > SUMO_const_haltingSpeed) {
1652:             req = ret | LCA_STAY | LCA_STRATEGIC;
1653:             if (!cancelRequest(req, laneOffset)) {
1654:                 return ret | req;
1655:             }
1656:         }
1657:     }
1668:     if (amBlockingFollowerPlusNB()
1669:             && (!speedGainInconvenient)
1670:             && ((myOwnState & myLca) != 0) // VARIANT_6 : counterNoHelp
1671:             && (changeToBest || currentDistAllows(neighDist, abs(bestLaneOffset) + 1, laDist))) {
1684:         req = ret | lca | LCA_COOPERATIVE | LCA_URGENT ;//| LCA_CHANGE_TO_HELP;
1685:         if (!cancelRequest(req, laneOffset)) {
1686:             if ((blocked & LCA_BLOCKED_BY_LEFT_FOLLOWER) && !right && mySpeedGainProbabilityLeft > (long long int)(mySpeedGainUrgency * HYST_PRECISION)) {
1687:                 MSVehicle* nv = neighFollow.first;
1688:                 const bool hasBidiNeighFollower = neighLane.getBidiLane() != nullptr && MSLCHelper::isBidiFollower(&myVehicle, nv);
1689:                 if (nv != nullptr && !hasBidiNeighFollower && !MSLCHelper::unwillingToHelp(myVehicle, myVehicle.getSpeed(), *nv)) {
1690:                     const double helpSpeed = MAX2(nv->getCarFollowModel().minNextSpeed(nv->getSpeed(), nv), myVehicle.getSpeed() - 1);
1691:                     msgPass.informNeighFollower(new Info(helpSpeed, myLca | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
1692:                 }
1693:             }
1694:             return ret | req;
1695:         }
1696:     }
1713:     if (neighLane.getEdge().getPersons().size() > 0) {
1715:         adaptSpeedToPedestrians(myVehicle.getLane(), thisLaneVSafe);
1716:         adaptSpeedToPedestrians(&neighLane, neighLaneVSafe);
1717:     }
1719:     const double relativeGain = (neighLaneVSafe - thisLaneVSafe) / MAX2(neighLaneVSafe,
1720:                                 RELGAIN_NORMALIZATION_MIN_SPEED);
1735:     if (right) {
1737:         if (thisLaneVSafe - 5 / 3.6 > neighLaneVSafe) {
1739:             mySpeedGainProbabilityRight = (long long int)((double)mySpeedGainProbabilityRight * pow(0.5, myVehicle.getActionStepLengthSecs()));
1741:         } else {
1743:             mySpeedGainProbabilityRight += (long long int)(myVehicle.getActionStepLengthSecs() * relativeGain * HYST_PRECISION);
1746:             const double roadSpeedFactor = vMax / myVehicle.getLane()->getSpeedLimit(); // differse from speedFactor if vMax < speedLimit
1747:             double acceptanceTime;
1748:             if (myKeepRightAcceptanceTime == -1) {
1751:                 acceptanceTime = 7 * roadSpeedFactor * MAX2(1.0, myVehicle.getSpeed());
1752:             } else {
1753:                 acceptanceTime = myKeepRightAcceptanceTime * roadSpeedFactor;
1754:                 if (follower.first != nullptr && follower.second < 2 * follower.first->getCarFollowModel().brakeGap(follower.first->getSpeed())) {
1756:                     if (follower.first->getSpeed() >= myVehicle.getSpeed()) {
1757:                         acceptanceTime *= MAX2(1.0, myVehicle.getSpeed()) / MAX2(1.0, follower.first->getSpeed());
1758:                         const double fRSF = follower.first->getLane()->getVehicleMaxSpeed(follower.first) / follower.first->getLane()->getSpeedLimit();
1759:                         if (fRSF > roadSpeedFactor) {
1760:                             acceptanceTime /= fRSF;
1761:                         }
1762:                     }
1763:                 }
1764:             }
1765:             double fullSpeedGap = MAX2(0., neighDist - myVehicle.getCarFollowModel().brakeGap(vMax));
1766:             double fullSpeedDrivingSeconds = MIN2(acceptanceTime, fullSpeedGap / vMax);
1767:             if (neighLead.first != 0 && neighLead.first->getSpeed() < vMax) {
1768:                 fullSpeedGap = MAX2(0., MIN2(fullSpeedGap,
1769:                                              neighLead.second - myVehicle.getCarFollowModel().getSecureGap(&myVehicle, neighLead.first,
1770:                                                      vMax, neighLead.first->getSpeed(), neighLead.first->getCarFollowModel().getMaxDecel())));
1771:                 fullSpeedDrivingSeconds = MIN2(fullSpeedDrivingSeconds, fullSpeedGap / (vMax - neighLead.first->getSpeed()));
1772:             }
1774:             if (checkOverTakeRight && leader.first != 0
1775:                     && leader.first->getLane()->getVehicleMaxSpeed(leader.first) < vMax) {
1776:                 fullSpeedGap = MIN2(fullSpeedGap, leader.second);
1777:                 fullSpeedDrivingSeconds = MIN2(fullSpeedDrivingSeconds, fullSpeedGap / (vMax - leader.first->getSpeed()));
1778:             }
1780:             const double deltaProb = (myChangeProbThresholdRight == std::numeric_limits<long long int>::max()) ? 0 :
1781:                                      ((double)myChangeProbThresholdRight * (fullSpeedDrivingSeconds / acceptanceTime) / KEEP_RIGHT_TIME);
1782:             myKeepRightProbability -= (long long int)(myVehicle.getActionStepLengthSecs() * deltaProb);
1810:             if ((long long int)((double)myKeepRightProbability * myKeepRightParam) < -myChangeProbThresholdRight) {
1811:                 req = ret | lca | LCA_KEEPRIGHT;
1812:                 if (!cancelRequest(req, laneOffset)) {
1813:                     return ret | req;
1814:                 }
1815:             }
1816:         }
1833:         if (mySpeedGainProbabilityRight > myChangeProbThresholdRight
1834:                 && neighDist / MAX2(.1, myVehicle.getSpeed()) > mySpeedGainRemainTime) { //./MAX2( .1, myVehicle.getSpeed())) { // -.1
1835:             req = ret | lca | LCA_SPEEDGAIN;
1836:             if (mySpeedGainProbabilityRight > (long long int)(mySpeedGainUrgency * HYST_PRECISION)) {
1837:                 req |= LCA_URGENT;
1838:             }
1839:             if (!cancelRequest(req, laneOffset)) {
1840:                 return ret | req;
1841:             }
1842:         }
1843:     } else {
1845:         if (thisLaneVSafe > neighLaneVSafe) {
1847:             mySpeedGainProbabilityLeft = (long long int)((double)mySpeedGainProbabilityLeft * pow(0.5, myVehicle.getActionStepLengthSecs()));
1848:         } else if (thisLaneVSafe == neighLaneVSafe) {
1849:             mySpeedGainProbabilityLeft = (long long int)((double)mySpeedGainProbabilityLeft * pow(0.8, myVehicle.getActionStepLengthSecs()));
1850:         } else {
1851:             mySpeedGainProbabilityLeft += (long long int)(myVehicle.getActionStepLengthSecs() * relativeGain * HYST_PRECISION);
1852:         }
1878:         if (mySpeedGainProbabilityLeft > myChangeProbThresholdLeft
1879:                 && (relativeGain > NUMERICAL_EPS || changeLeftToAvoidOvertakeRight)
1880:                 && neighDist / MAX2(.1, myVehicle.getSpeed()) > mySpeedGainRemainTime) { // .1
1881:             req = ret | lca | LCA_SPEEDGAIN;
1882:             if (mySpeedGainProbabilityLeft > (long long int)(mySpeedGainUrgency * HYST_PRECISION)) {
1883:                 req |= LCA_URGENT;
1884:             }
1885:             if (!cancelRequest(req, laneOffset)) {
1886:                 if ((req & LCA_URGENT) && (blocked & LCA_BLOCKED_BY_LEFT_FOLLOWER)) {
1887:                     MSVehicle* nv = neighFollow.first;
1888:                     const bool hasBidiNeighFollower = neighLane.getBidiLane() != nullptr && MSLCHelper::isBidiFollower(&myVehicle, nv);
1889:                     if (nv != nullptr && !hasBidiNeighFollower && !MSLCHelper::unwillingToHelp(myVehicle, myVehicle.getSpeed(), *nv)) {
1890:                         const double helpSpeed = MAX2(nv->getCarFollowModel().minNextSpeed(nv->getSpeed(), nv), myVehicle.getSpeed() - 1);
1891:                         msgPass.informNeighFollower(new Info(helpSpeed, myLca | LCA_AMBLOCKINGFOLLOWER), &myVehicle);
1892:                     }
1893:                 }
1894:                 return ret | req;
1895:             }
1896:         }
1897:     }
1899:     if (changeToBest && bestLaneOffset == curr.bestLaneOffset
1900:             && myStrategicParam >= 0
1901:             && relativeGain >= 0
1902:             && (right ? mySpeedGainProbabilityRight : mySpeedGainProbabilityLeft) > 0) {
1904:         req = ret | lca | LCA_STRATEGIC;
1905:         if (!cancelRequest(req, laneOffset)) {
1906:             return ret | req;
1907:         }
1908:     }
1922:     return ret;
1923: }
1926: double
1927: MSLCM_LC2013::anticipateFollowSpeed(const std::pair<MSVehicle*, double>& leaderDist, double dist, double vMax, bool acceleratingLeader) {
1928:     const MSVehicle* leader = leaderDist.first;
1929:     const double gap = leaderDist.second;
1930:     double futureSpeed;
1931:     if (acceleratingLeader) {
1933:         const double maxSpeed1s = (myVehicle.getSpeed() + myVehicle.getCarFollowModel().getMaxAccel()
1934:                                    - ACCEL2SPEED(myVehicle.getCarFollowModel().getMaxAccel()));
1935:         if (leader == nullptr) {
1936:             if (hasBlueLight()) {
1938:                 futureSpeed = vMax;
1939:             } else {
1940:                 futureSpeed = getCarFollowModel().followSpeed(&myVehicle, maxSpeed1s, dist, 0, 0);
1941:             }
1942:         } else {
1943:             futureSpeed = getCarFollowModel().followSpeed(&myVehicle, maxSpeed1s, gap, leader->getSpeed(), leader->getCarFollowModel().getMaxDecel());
1944:         }
1945:     } else {
1947:         if (leader == nullptr) {
1948:             if (hasBlueLight()) {
1950:                 futureSpeed = vMax;
1951:             } else {
1952:                 futureSpeed = getCarFollowModel().maximumSafeStopSpeed(dist, getCarFollowModel().getMaxDecel(), myVehicle.getSpeed(), true);
1953:             }
1954:         } else {
1955:             futureSpeed = getCarFollowModel().maximumSafeFollowSpeed(gap, myVehicle.getSpeed(), leader->getSpeed(), leader->getCarFollowModel().getMaxDecel(), true);
1956:         }
1957:     }
1958:     futureSpeed = MIN2(vMax, futureSpeed);
1959:     if (leader != nullptr && gap > 0 && mySpeedGainLookahead > 0) {
1960:         const double futureLeaderSpeed = acceleratingLeader ? leader->getLane()->getVehicleMaxSpeed(leader) : leader->getSpeed();
1961:         const double deltaV = vMax - futureLeaderSpeed;
1962:         if (deltaV > 0 && gap > 0) {
1963:             const double secGap = getCarFollowModel().getSecureGap(&myVehicle, leader, futureSpeed, leader->getSpeed(), getCarFollowModel().getMaxDecel());
1964:             const double fullSpeedGap = gap - secGap;
1965:             if (fullSpeedGap / deltaV < mySpeedGainLookahead) {
1968:                 const double gapClosingTime = MAX2(0.0, fullSpeedGap / deltaV);
1969:                 const double foreCastTime = mySpeedGainLookahead * 2;
1971:                 futureSpeed = MIN2(futureSpeed, (gapClosingTime * futureSpeed + (foreCastTime - gapClosingTime) * futureLeaderSpeed) / foreCastTime);
1973:             }
1974:         }
1975:     }
1976:     return futureSpeed;
1977: }
1980: int
1981: MSLCM_LC2013::slowDownForBlocked(MSVehicle* blocked, int state) {
1983:     if (blocked != nullptr) {
1984:         double gap = blocked->getPositionOnLane() - blocked->getVehicleType().getLength() - myVehicle.getPositionOnLane() - myVehicle.getVehicleType().getMinGap();
1994:         if (gap > POSITION_EPS) {
1998:             if (myVehicle.getSpeed() < myVehicle.getCarFollowModel().getMaxDecel()
2000:                ) {
2001:                 if (blocked->getSpeed() < SUMO_const_haltingSpeed) {
2002:                     state |= LCA_AMBACKBLOCKER_STANDING;
2003:                 } else {
2004:                     state |= LCA_AMBACKBLOCKER;
2005:                 }
2006:                 addLCSpeedAdvice(getCarFollowModel().followSpeed(
2007:                                      &myVehicle, myVehicle.getSpeed(),
2008:                                      gap - POSITION_EPS, blocked->getSpeed(),
2009:                                      blocked->getCarFollowModel().getMaxDecel()), LCA_CHANGE_TO_HELP);
2022:             } /*else if ((*blocked)->getWaitingSeconds() > 30 && gap > myVehicle.getBrakeGap()) {
2025:                 state |= LCA_AMBACKBLOCKER;
2026:                 addLCSpeedAdvice(getCarFollowModel().followSpeed(
2027:                             &myVehicle, myVehicle.getSpeed(),
2028:                             (gap - POSITION_EPS), (*blocked)->getSpeed(),
2029:                             (*blocked)->getCarFollowModel().getMaxDecel()));
2030:             } */
2031:         }
2032:     }
2033:     return state;
2034: }
2037: void
2038: MSLCM_LC2013::adaptSpeedToPedestrians(const MSLane* lane, double& v) {
2039:     if (lane->hasPedestrians()) {
2045:         PersonDist leader = lane->nextBlocking(myVehicle.getPositionOnLane(),
2046:                                                myVehicle.getRightSideOnLane(), myVehicle.getRightSideOnLane() + myVehicle.getVehicleType().getWidth(),
2047:                                                ceil(myVehicle.getSpeed() / myVehicle.getCarFollowModel().getMaxDecel()));
2048:         if (leader.first != 0) {
2049:             const double stopSpeed = myVehicle.getCarFollowModel().stopSpeed(&myVehicle, myVehicle.getSpeed(), leader.second - myVehicle.getVehicleType().getMinGap());
2050:             v = MIN2(v, stopSpeed);
2056:         }
2057:     }
2058: }
2061: double
2062: MSLCM_LC2013::computeSpeedLat(double latDist, double& maneuverDist, bool urgent) const {
2063:     double result = MSAbstractLaneChangeModel::computeSpeedLat(latDist, maneuverDist, urgent);
2069:     if (myLeftSpace > POSITION_EPS || !urgent) {
2070:         double speedBound = myMaxSpeedLatStanding + myMaxSpeedLatFactor * myVehicle.getSpeed();
2071:         if (isChangingLanes()) {
2072:             speedBound = MAX2(LC_RESOLUTION_SPEED_LAT, speedBound);
2073:         }
2074:         result = MAX2(-speedBound, MIN2(speedBound, result));
2075:     }
2076:     return result;
2077: }
2080: double
2081: MSLCM_LC2013::getSafetyFactor() const {
2082:     return 1 / myAssertive;
2083: }
2085: double
2086: MSLCM_LC2013::getOppositeSafetyFactor() const {
2087:     return myOppositeParam <= 0 ? std::numeric_limits<double>::max() : 1 / myOppositeParam;
2088: }
2090: bool
2091: MSLCM_LC2013::saveBlockerLength(double length, double foeLeftSpace) {
2092:     const bool canReserve = MSLCHelper::canSaveBlockerLength(myVehicle, length, myLeftSpace);
2093:     if (!isOpposite() && (canReserve || myLeftSpace > foeLeftSpace)) {
2094:         myLeadingBlockerLength = MAX2(length, myLeadingBlockerLength);
2100:         if (myLeftSpace == 0 && foeLeftSpace < 0) {
2102:             myLeftSpace = myVehicle.getBestLanes()[myVehicle.getLane()->getIndex()].length - myVehicle.getPositionOnLane();
2103:         }
2104:         return true;
2105:     } else {
2106:         return false;
2107:     }
2108: }
2111: bool
2112: MSLCM_LC2013::hasFreeLane(int laneOffset, const std::pair<MSVehicle*, double>& neighLeadStopped) const {
2113:     if (neighLeadStopped.first == nullptr) {
2114:         return true;
2115:     }
2116:     int dir = (laneOffset > 0 ? 1 : -1);
2117:     const MSLane* neigh = myVehicle.getLane()->getParallelLane(laneOffset);
2118:     if (dir > 0 && !neigh->allowsChangingLeft(myVehicle.getVClass())) {
2119:         return false;
2120:     } else if (dir < 0 && !neigh->allowsChangingRight(myVehicle.getVClass())) {
2121:         return false;
2122:     }
2123:     int nextOffset = laneOffset + dir;
2124:     const MSLane* next = myVehicle.getLane()->getParallelLane(nextOffset);
2125:     if (next == nullptr || !next->allowsVehicleClass(myVehicle.getVClass())) {
2126:         return false;
2127:     }
2128:     const double overtakeDist = neighLeadStopped.second + neighLeadStopped.first->getVehicleType().getLengthWithGap() + myVehicle.getLength() + POSITION_EPS;
2129:     std::pair<MSVehicle* const, double> nextLead = next->getLeader(&myVehicle, myVehicle.getPositionOnLane(), myVehicle.getBestLanesContinuation(next), overtakeDist);
2130:     return nextLead.first == nullptr || nextLead.second >= overtakeDist || hasFreeLane(nextOffset, nextLead);
2131: }
```

### A3. Base parameters — `microsim/lcmodels/MSAbstractLaneChangeModel.cpp:139-150`

```cpp
139:     myStrategicLookahead(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_STRATEGIC_LOOKAHEAD, UNDEFINED_LOOKAHEAD)),
140:     myMaxSpeedLatStanding(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_MAXSPEEDLATSTANDING, v.getVehicleType().getMaxSpeedLat())),
141:     myMaxSpeedLatFactor(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_MAXSPEEDLATFACTOR, 1)),
142:     myMaxDistLatStanding(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_MAXDISTLATSTANDING,
144:                          (v.getVClass() & (SVC_BICYCLE | SVC_MOTORCYCLE | SVC_MOPED)) != 0 ? std::numeric_limits<double>::max() : 1.6)),
145:     mySigma(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_SIGMA, 0.0)),
146:     myOvertakeRightParam(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_OVERTAKE_RIGHT, 0)),
147:     myAssertive(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_ASSERTIVE, 1)),
148:     myCooperativeHelpTime(TIME2STEPS(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_COOPERATIVE_HELPTIME, 60))),
149:     myCooperativeHelpThreshold(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_COOPERATIVE_HELPTHRESHOLD, -1)),
150:     myCooperativeMinSpeed(v.getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_COOPERATIVE_MINSPEED, 0)),
```

### A3. Maneuver bookkeeping — `microsim/lcmodels/MSAbstractLaneChangeModel.cpp:290-499`

```cpp
290: MSAbstractLaneChangeModel::avoidOvertakeRight(const MSVehicle* const neighLeader, const bool allowProb) const {
291:     return (!myAllowOvertakingRight  // the highway case
292:             && !myVehicle.congested()
293:             && myVehicle.getVehicleType().getVehicleClass() != SVC_EMERGENCY
294:             && (!allowProb || myOvertakeRightParam == 0 || myOvertakeRightParam < RandHelper::rand(myVehicle.getRNG()))) ||
295:            (neighLeader != nullptr && neighLeader->isStopped()  // the bus stop case
296:             && neighLeader->getStops().front().busstop != nullptr
297:             && !StringUtils::toBool(neighLeader->getStops().front().busstop->getParameter("allowOvertakeRight", "true")));
298: }
300: bool
301: MSAbstractLaneChangeModel::predInteraction(const std::pair<MSVehicle*, double>& leader) {
302:     if (leader.first == 0) {
303:         return false;
304:     }
306:     if (leader.first->getSpeed() < (80.0 / 3.6)) {
307:         return false;
308:     }
309:     return leader.second < getCarFollowModel().interactionGap(&myVehicle, leader.first->getSpeed());
310: }
313: bool
314: MSAbstractLaneChangeModel::startLaneChangeManeuver(MSLane* source, MSLane* target, int direction) {
315:     if (MSGlobals::gLaneChangeDuration > DELTA_T) {
316:         myLaneChangeCompletion = 0;
317:         myLaneChangeDirection = direction;
318:         setManeuverDist((target->getWidth() + source->getWidth()) * 0.5 * direction);
319:         myVehicle.switchOffSignal(MSVehicle::VEH_SIGNAL_BLINKER_RIGHT | MSVehicle::VEH_SIGNAL_BLINKER_LEFT);
320:         myVehicle.switchOnSignal(((direction == 1) != MSGlobals::gLefthand) ? MSVehicle::VEH_SIGNAL_BLINKER_LEFT : MSVehicle::VEH_SIGNAL_BLINKER_RIGHT);
321:         if (myLCOutput) {
322:             memorizeGapsAtLCInit();
323:         }
324:         return true;
325:     } else {
326:         primaryLaneChanged(source, target, direction);
327:         return false;
328:     }
329: }
331: void
332: MSAbstractLaneChangeModel::memorizeGapsAtLCInit() {
333:     myDontResetLCGaps = true;
334: }
336: void
337: MSAbstractLaneChangeModel::clearGapsAtLCInit() {
338:     myDontResetLCGaps = false;
339: }
341: void
342: MSAbstractLaneChangeModel::primaryLaneChanged(MSLane* source, MSLane* target, int direction) {
343:     initLastLaneChangeOffset(direction);
344:     myVehicle.leaveLane(MSMoveReminder::NOTIFICATION_LANE_CHANGE, target);
345:     source->leftByLaneChange(&myVehicle);
346:     laneChangeOutput("change", source, target, direction); // record position on the source edge in case of opposite change
347:     if (&source->getEdge() != &target->getEdge()) {
348:         changedToOpposite();
354:         myVehicle.setTentativeLaneAndPosition(target, source->getOppositePos(myVehicle.getPositionOnLane()), -myVehicle.getLateralPositionOnLane());
355:         target->forceVehicleInsertion(&myVehicle, myVehicle.getPositionOnLane(), MSMoveReminder::NOTIFICATION_LANE_CHANGE, myVehicle.getLateralPositionOnLane());
356:     } else if (myAmOpposite) {
362:         myAlreadyChanged = true;
363:         myVehicle.setTentativeLaneAndPosition(target, myVehicle.getPositionOnLane(), myVehicle.getLateralPositionOnLane());
364:         if (!MSGlobals::gSublane) {
367:             target->forceVehicleInsertion(&myVehicle, myVehicle.getPositionOnLane(), MSMoveReminder::NOTIFICATION_LANE_CHANGE, myVehicle.getLateralPositionOnLane());
368:         }
369:     } else {
370:         myVehicle.enterLaneAtLaneChange(target);
371:         target->enteredByLaneChange(&myVehicle);
372:     }
375:     myVehicle.updateDriveItems();
376:     changed();
377: }
379: void
380: MSAbstractLaneChangeModel::laneChangeOutput(const std::string& tag, MSLane* source, MSLane* target, int direction, double maneuverDist) {
381:     if (myLCOutput) {
382:         OutputDevice& of = OutputDevice::getDeviceByOption("lanechange-output");
383:         of.openTag(tag);
384:         of.writeAttr(SUMO_ATTR_ID, myVehicle.getID());
385:         of.writeAttr(SUMO_ATTR_TYPE, myVehicle.getVehicleType().getID());
386:         of.writeAttr(SUMO_ATTR_TIME, time2string(MSNet::getInstance()->getCurrentTimeStep()));
387:         of.writeAttr(SUMO_ATTR_FROM, source->getID());
388:         of.writeAttr(SUMO_ATTR_TO, target->getID());
389:         of.writeAttr(SUMO_ATTR_DIR, direction);
390:         of.writeAttr(SUMO_ATTR_SPEED, myVehicle.getSpeed());
391:         of.writeAttr(SUMO_ATTR_POSITION, myVehicle.getPositionOnLane());
392:         of.writeAttr("reason", toString((LaneChangeAction)(myOwnState & ~(
393:                                             LCA_RIGHT | LCA_LEFT
394:                                             | LCA_AMBLOCKINGLEADER | LCA_AMBLOCKINGFOLLOWER
395:                                             | LCA_MRIGHT | LCA_MLEFT
396:                                             | LCA_AMBACKBLOCKER | LCA_AMBACKBLOCKER_STANDING))) + myVehicle.getParameter().getParameter("lcReason"));
397:         of.writeAttr("leaderGap", myLastLeaderGap == NO_NEIGHBOR ? "None" : toString(myLastLeaderGap), myLastLeaderGap == NO_NEIGHBOR);
398:         of.writeAttr("leaderSecureGap", myLastLeaderSecureGap == NO_NEIGHBOR ? "None" : toString(myLastLeaderSecureGap), myLastLeaderSecureGap == NO_NEIGHBOR);
399:         of.writeAttr("leaderSpeed", myLastLeaderSpeed == NO_NEIGHBOR ? "None" : toString(myLastLeaderSpeed), myLastLeaderSpeed == NO_NEIGHBOR);
400:         of.writeAttr("followerGap", myLastFollowerGap == NO_NEIGHBOR ? "None" : toString(myLastFollowerGap), myLastFollowerGap == NO_NEIGHBOR);
401:         of.writeAttr("followerSecureGap", myLastFollowerSecureGap == NO_NEIGHBOR ? "None" : toString(myLastFollowerSecureGap), myLastFollowerSecureGap == NO_NEIGHBOR);
402:         of.writeAttr("followerSpeed", myLastFollowerSpeed == NO_NEIGHBOR ? "None" : toString(myLastFollowerSpeed), myLastFollowerSpeed == NO_NEIGHBOR);
403:         of.writeAttr("origLeaderGap", myLastOrigLeaderGap == NO_NEIGHBOR ? "None" : toString(myLastOrigLeaderGap), myLastOrigLeaderGap == NO_NEIGHBOR);
404:         of.writeAttr("origLeaderSecureGap", myLastOrigLeaderSecureGap == NO_NEIGHBOR ? "None" : toString(myLastOrigLeaderSecureGap), myLastOrigLeaderSecureGap == NO_NEIGHBOR);
405:         of.writeAttr("origLeaderSpeed", myLastOrigLeaderSpeed == NO_NEIGHBOR ? "None" : toString(myLastOrigLeaderSpeed), myLastOrigLeaderSpeed == NO_NEIGHBOR);
406:         if (MSGlobals::gLateralResolution > 0) {
407:             const double latGap = direction < 0 ? myLastLateralGapRight : myLastLateralGapLeft;
408:             of.writeAttr("latGap", latGap == NO_NEIGHBOR ? "None" : toString(latGap), latGap == NO_NEIGHBOR);
409:             if (maneuverDist != 0) {
410:                 of.writeAttr("maneuverDistance", toString(maneuverDist));
411:             }
412:         }
413:         if (myLCXYOutput) {
414:             of.writeAttr(SUMO_ATTR_X, myVehicle.getPosition().x());
415:             of.writeAttr(SUMO_ATTR_Y, myVehicle.getPosition().y());
416:         }
417:         of.closeTag();
418:         if (MSGlobals::gLaneChangeDuration > DELTA_T) {
419:             clearGapsAtLCInit();
420:         }
421:     }
422: }
425: double
426: MSAbstractLaneChangeModel::computeSpeedLat(double /*latDist*/, double& maneuverDist, bool /*urgent*/) const {
427:     if (myVehicle.getVehicleType().wasSet(VTYPEPARS_MAXSPEED_LAT_SET)) {
428:         int stepsToChange = (int)ceil(fabs(maneuverDist) / SPEED2DIST(myVehicle.getVehicleType().getMaxSpeedLat()));
429:         return DIST2SPEED(maneuverDist / stepsToChange);
430:     } else {
431:         return maneuverDist / STEPS2TIME(MSGlobals::gLaneChangeDuration);
432:     }
433: }
436: double
437: MSAbstractLaneChangeModel::getAssumedDecelForLaneChangeDuration() const {
438:     return MAX2(LC_ASSUMED_DECEL, -myVehicle.getAcceleration());
439: }
441: void
442: MSAbstractLaneChangeModel::setSpeedLat(double speedLat) {
443:     myAccelerationLat = SPEED2ACCEL(speedLat - mySpeedLat);
444:     mySpeedLat = speedLat;
445: }
448: void
449: MSAbstractLaneChangeModel::resetSpeedLat() {
450:     if (MSGlobals::gLaneChangeDuration > 0 && !isChangingLanes()) {
451:         setSpeedLat(0);
452:     }
453: }
456: bool
457: MSAbstractLaneChangeModel::updateCompletion() {
458:     const bool pastBefore = pastMidpoint();
460:     double maneuverDist = getManeuverDist();
461:     setSpeedLat(computeSpeedLat(0, maneuverDist, (myOwnState & LCA_URGENT) != 0));
462:     myLaneChangeCompletion += (SPEED2DIST(mySpeedLat) / myManeuverDist);
463:     return !pastBefore && pastMidpoint();
464: }
467: void
468: MSAbstractLaneChangeModel::endLaneChangeManeuver(const MSMoveReminder::Notification reason) {
469:     UNUSED_PARAMETER(reason);
470:     myLaneChangeCompletion = 1;
471:     cleanupShadowLane();
472:     cleanupTargetLane();
473:     myNoPartiallyOccupatedByShadow.clear();
474:     myVehicle.switchOffSignal(MSVehicle::VEH_SIGNAL_BLINKER_RIGHT | MSVehicle::VEH_SIGNAL_BLINKER_LEFT);
475:     myVehicle.fixPosition();
476:     if (myAmOpposite && reason != MSMoveReminder::NOTIFICATION_LANE_CHANGE) {
477:         if (reason == MSMoveReminder::NOTIFICATION_PARKING && myVehicle.getNextStop().isOpposite) {
479:         } else {
486:             changedToOpposite();
487:         }
488:     }
489: }
492: MSLane*
493: MSAbstractLaneChangeModel::getShadowLane(const MSLane* lane, double posLat) const {
494:     if (std::find(myNoPartiallyOccupatedByShadow.begin(), myNoPartiallyOccupatedByShadow.end(), lane) == myNoPartiallyOccupatedByShadow.end()) {
496:         const double overlap = myVehicle.getLateralOverlap(posLat, lane);
```

### A3. Cancellation — `microsim/lcmodels/MSAbstractLaneChangeModel.cpp:571-604`

```cpp
571: MSAbstractLaneChangeModel::cancelRequest(int state, int laneOffset) {
573:     getCanceledState(laneOffset) |= state;
574:     int ret = myVehicle.influenceChangeDecision(state);
575:     return ret != state;
576: }
578: double
579: MSAbstractLaneChangeModel::getMaxSpeedLat2() const {
580:     return MAX2(myVehicle.getVehicleType().getMaxSpeedLat(), myMaxSpeedLatStanding);
581: }
583: void
584: MSAbstractLaneChangeModel::initLastLaneChangeOffset(int dir) {
585:     if (dir > 0) {
586:         myLastLaneChangeOffset = 1;
587:     } else if (dir < 0) {
588:         myLastLaneChangeOffset = -1;
589:     }
590: }
592: void
593: MSAbstractLaneChangeModel::updateShadowLane() {
594:     if (!MSGlobals::gSublane) {
596:         return;
597:     }
598:     if (myShadowLane != nullptr) {
604:         myShadowLane->resetPartialOccupation(&myVehicle);
```

### A3. Advice and overtaking helpers — `microsim/lcmodels/MSAbstractLaneChangeModel.cpp:1114-1200`

```cpp
1114: MSAbstractLaneChangeModel::addLCSpeedAdvice(const double vSafe, int flag) {
1115:     const double accel = SPEED2ACCEL(vSafe - myVehicle.getSpeed());
1116:     myLCAccelerationAdvices.push_back({accel, flag});
1117: }
1120: bool
1121: MSAbstractLaneChangeModel::canOvertakeRight(const MSVehicle* const nv, const double dist, const double maxSpeedDiff, const double helpOvertakeSpeed, double& vSafe, double& deltaV) const {
1122:     deltaV = MAX2(maxSpeedDiff, myVehicle.getSpeed() - nv->getSpeed());
1123:     if (deltaV > 0) {
1124:         const double vMaxDecel = getCarFollowModel().getSpeedAfterMaxDecel(myVehicle.getSpeed());
1125:         const double vSafeFollow = getCarFollowModel().followSpeed(
1126:                                         &myVehicle, myVehicle.getSpeed(), dist, nv->getSpeed(), nv->getCarFollowModel().getMaxDecel());
1127:         const double vStayBehind = nv->getSpeed() - helpOvertakeSpeed;
1128:         if (vSafeFollow >= vMaxDecel) {
1129:             vSafe = vSafeFollow;
1130:         } else {
1131:             vSafe = MAX2(vMaxDecel, vStayBehind);
1132:         }
1133:         return true;
1134:     }
1135:     return false;
1136: }
1139: void
1140: MSAbstractLaneChangeModel::saveState(OutputDevice& out) const {
1141:     std::vector<double> lcState;
1142:     lcState.push_back((double)myOwnState);
1143:     for (const auto& item : myLCAccelerationAdvices) {
1144:         lcState.push_back(item.first);
1145:         lcState.push_back((double)item.second);
1146:     }
1147:     out.writeAttr(SUMO_ATTR_LCSTATE_BASE, lcState);
1149:     if (MSGlobals::gLaneChangeDuration > 0) {
1150:         out.writeAttr(SUMO_ATTR_LCSTATE, std::vector<double> {mySpeedLat, myLaneChangeCompletion, (double)myLaneChangeDirection});
1151:     }
1152: }
1154: void
1155: MSAbstractLaneChangeModel::loadState(const SUMOSAXAttributes& attrs) {
1156:     if (attrs.hasAttribute(SUMO_ATTR_LCSTATE_BASE)) {
1157:         std::istringstream bis(attrs.getString(SUMO_ATTR_LCSTATE_BASE));
1158:         double token;
1159:         bis >> token;
1160:         myOwnState = (int)token; // double is suffciently precise
1161:         double prev = std::numeric_limits<double>::max();
1162:         while (bis >> token) {
1163:             if (prev != std::numeric_limits<double>::max()) {
1164:                 myLCAccelerationAdvices.push_back(std::make_pair(prev, (int)token));
1165:                 prev = std::numeric_limits<double>::max();
1166:             }
1167:             prev = token;
1168:         }
1169:     }
1170:     if (attrs.hasAttribute(SUMO_ATTR_LCSTATE)) {
1171:         std::istringstream bis(attrs.getString(SUMO_ATTR_LCSTATE));
1172:         bis >> mySpeedLat;
1173:         bis >> myLaneChangeCompletion;
1174:         bis >> myLaneChangeDirection;
1175:     }
1176: }
1179: double
1180: MSAbstractLaneChangeModel::getExtraReservation(int bestLaneOffset, double neighExtraDist) const {
1181:     if (neighExtraDist > myVehicle.getVehicleType().getLengthWithGap()) {
1182:         return 0;
1183:     }
1184:     if (bestLaneOffset < -1) {
1185:         return 20;
1186:     } else if (bestLaneOffset > 1) {
1187:         return 40;
1188:     }
1189:     return 0;
1190: }
1193: double
1194: MSAbstractLaneChangeModel::getCooperativeHelpSpeed(const MSLane* lane, double distToLaneEnd) const {
1195:     if (myCooperativeHelpTime >= 0) {
1196:         std::pair<double, SUMOTime> backAndWaiting = lane->getEdge().getLastBlocked(lane->getIndex());
1197:         if (backAndWaiting.second >= myCooperativeHelpTime) {
1198:             double gap = distToLaneEnd - lane->getLength() + backAndWaiting.first - myVehicle.getVehicleType().getMinGap() - NUMERICAL_EPS;
1199:             if (backAndWaiting.first < 0) {
1200:                 if (myVehicle.getLane()->getToJunction() == lane->getFromJunction()) {
```

### A3. Cooperation and roundabout helpers — `microsim/lcmodels/MSLCHelper.cpp:44-425`

```cpp
44: MSLCHelper::getRoundaboutDistBonus(const MSVehicle& veh,
45:                                    double bonusParam,
46:                                    const MSVehicle::LaneQ& curr,
47:                                    const MSVehicle::LaneQ& neigh,
48:                                    const MSVehicle::LaneQ& best) {
49:     if (veh.getLaneChangeModel().isOpposite()) {
50:         return 0;
51:     }
52:     const MSVehicle::LaneQ& inner = neigh.lane->getIndex() > curr.lane->getIndex() ? neigh : curr;
66:     if (neigh.lane == inner.lane && curr.bestContinuations.size() < neigh.bestContinuations.size()) {
68:         return 0;
69:     }
71:     int roundaboutJunctionsAhead = 0;
72:     bool enteredRoundabout = false;
73:     double seen = -veh.getPositionOnLane();
76:     for (int i = 0; i < (int)best.bestContinuations.size(); i++) {
77:         const MSLane* lane = best.bestContinuations[i];
78:         if (lane == nullptr) {
79:             lane = veh.getLane();
80:         }
81:         if ((!enteredRoundabout || lane->getEdge().isRoundabout()) && i >= (int)inner.bestContinuations.size()) {
88:             return 0;
89:         }
90:         if (seen > 300) {
97:             return 0;
98:         }
99:         const MSJunction* junction = lane->getEdge().getToJunction();
100:         if (lane->getEdge().isRoundabout()) {
101:             enteredRoundabout = true;
102:             if (junction->getIncoming().size() + junction->getOutgoing().size() > 2) {
103:                 roundaboutJunctionsAhead++;
104:             }
105:         } else if (enteredRoundabout) {
107:             break;
108:         }
109:         seen += lane->getLength();
110:     }
112:     if (roundaboutJunctionsAhead < 2) {
118:         return 0;
119:     }
122:     double occupancyOuter = 0;
123:     double occupancyInner = 0;
124:     double distanceInRoundabout = 0;
125:     MSLane* prevNormal = nullptr;
126:     MSLane* prevInner = nullptr;
127:     enteredRoundabout = false;
128:     for (int i = 0; i < (int)best.bestContinuations.size(); i++) {
129:         MSLane* lane = best.bestContinuations[i];
130:         if (lane == nullptr) {
131:             continue;
132:         }
133:         if (lane->getEdge().isRoundabout()) {
134:             enteredRoundabout = true;
135:         } else if (enteredRoundabout) {
137:             break;
138:         }
139:         MSLane* via = nullptr;
140:         if (prevNormal != nullptr) {
141:             for (MSLink* link : prevNormal->getLinkCont()) {
142:                 if (link->getLane() == lane) {
143:                     via = link->getViaLane();
144:                 }
145:             }
146:         }
147:         if (enteredRoundabout) {
148:             distanceInRoundabout += lane->getLength();
149:             if (via != nullptr) {
150:                 distanceInRoundabout += via->getLength();
151:             }
152:         }
154:         const double upstreamDiscount = &lane->getEdge() == &veh.getLane()->getEdge()
155:                                         ? (lane->getLength() - veh.getPositionOnLane()) / lane->getLength() : 1;
156:         prevNormal = lane;
157:         occupancyOuter += upstreamDiscount * lane->getBruttoVehLenSum();
163:         if (via != nullptr) {
164:             occupancyOuter += via->getBruttoVehLenSum();
170:         }
171:         if (i < (int)inner.bestContinuations.size()) {
172:             MSLane* innerLane = inner.bestContinuations[i];
173:             occupancyInner += upstreamDiscount * innerLane->getBruttoVehLenSum();
179:             if (prevInner != nullptr) {
180:                 for (MSLink* link : prevInner->getLinkCont()) {
181:                     if (link->getLane() == innerLane && link->getViaLane() != nullptr) {
182:                         occupancyInner += link->getViaLane()->getBruttoVehLenSum();
188:                     }
189:                 }
190:             }
191:             prevInner = innerLane;
192:         }
193:     }
204:     if (abs(curr.bestLaneOffset) > 1 && enteredRoundabout) {
205:         const double bGap = veh.getCarFollowModel().brakeGap(veh.getSpeed() + ACCEL2SPEED(veh.getCarFollowModel().getMaxAccel()), veh.getCarFollowModel().getMaxDecel(), veh.getActionStepLengthSecs());
206:         const double reservation = veh.getLaneChangeModel().getExtraReservation(curr.bestLaneOffset);
207:         const double leftSpace = distanceInRoundabout - reservation - veh.getPositionOnLane();
213:         if (bGap > leftSpace) {
214:             return 0;
215:         }
216:     }
218:     const double maxOccupancy = MAX2(occupancyInner, occupancyOuter);
220:     const double bonus = roundaboutJunctionsAhead * 7.5;
221:     const double relativeJam = (occupancyOuter - occupancyInner + bonus) / (maxOccupancy + bonus);
223:     double jamFactor = MAX2(0.0, relativeJam);
224:     if (veh.getLane()->getEdge().isRoundabout() && curr.lane->getIndex() > neigh.lane->getIndex()) {
227:         jamFactor = 1;
228:     }
229:     const double result = distanceInRoundabout * jamFactor * bonusParam * 9; // the 9 is abitrary and only there for backward compatibility
238:     return result;
239: }
242: bool
243: MSLCHelper::updateBlockerLength(const MSVehicle& veh,  MSVehicle* blocker, int lcaCounter, double leftSpace, bool reliefConnection, double& leadingBlockerLength) {
253:     if (blocker != nullptr && (blocker->getLaneChangeModel().getOwnState() & lcaCounter) != 0) {
255:         const double required = blocker->getVehicleType().getLengthWithGap() + veh.getVehicleType().getMinGap();
256:         const double potential = leftSpace - veh.getCarFollowModel().brakeGap(
257:                                      veh.getSpeed(), veh.getCarFollowModel().getMaxDecel(), 0);
258:         if (required <= potential) {
260:             leadingBlockerLength = MAX2(required, leadingBlockerLength);
272:         } else {
275:             const double required2 = veh.getVehicleType().getLengthWithGap() + blocker->getVehicleType().getMinGap();
276:             const double foeLeftSpace = leftSpace - veh.getPositionOnLane() + blocker->getPositionOnLane() - POSITION_EPS;
277:             const bool canReserve = blocker->getLaneChangeModel().saveBlockerLength(required2, foeLeftSpace);
293:             if (!canReserve && !reliefConnection) {
294:                 const int blockerState = blocker->getLaneChangeModel().getOwnState();
295:                 if ((blockerState & LCA_STRATEGIC) != 0
296:                         && (blockerState & LCA_URGENT) != 0) {
298:                     leadingBlockerLength = MAX2(required, leadingBlockerLength);
304:                 }
305:             }
306:             return canReserve;
307:         }
308:     }
309:     return true;
310: }
313: bool
314: MSLCHelper::canSaveBlockerLength(const MSVehicle& veh, double requested, double leftSpace) {
315:     const double potential = leftSpace - veh.getCarFollowModel().brakeGap(veh.getSpeed(), veh.getCarFollowModel().getMaxDecel(), veh.getActionStepLengthSecs());
321:     return potential >= requested;
322: }
325: bool
326: MSLCHelper::divergentRoute(const MSVehicle& v1, const MSVehicle& v2) {
328:     return (v1.getLane()->isInternal() && v2.getLane()->isInternal()
329:             && v1.getLane()->getEdge().getFromJunction() == v2.getLane()->getEdge().getFromJunction()
330:             && &v1.getLane()->getEdge() != &v2.getLane()->getEdge());
331: }
334: double
335: MSLCHelper::getSpeedPreservingSecureGap(const MSVehicle& leader, const MSVehicle& follower, double currentGap, double leaderPlannedSpeed) {
339:     const double nextGap = currentGap + SPEED2DIST(leaderPlannedSpeed - follower.getSpeed());
340:     double sGap = follower.getCarFollowModel().getSecureGap(&follower, &leader, follower.getSpeed(), leaderPlannedSpeed, leader.getCarFollowModel().getMaxDecel());
341:     if (nextGap >= sGap) {
343:         const double nextGapMin = currentGap + SPEED2DIST(leaderPlannedSpeed - follower.getCarFollowModel().maxNextSpeed(follower.getSpeed(), &follower));
344:         const double vSafe = follower.getCarFollowModel().followSpeed(
345:                                  &follower, follower.getSpeed(), nextGapMin, leaderPlannedSpeed, leader.getCarFollowModel().getMaxDecel());
346:         return MAX2(vSafe, follower.getSpeed());
347:     } else {
349:         const double vSafe = follower.getCarFollowModel().followSpeed(
350:                                  &follower, follower.getSpeed(), nextGap, leaderPlannedSpeed, leader.getCarFollowModel().getMaxDecel());
352:         return MAX2(vSafe, follower.getCarFollowModel().minNextSpeed(follower.getSpeed(), &follower));
353:     }
354: }
357: bool
358: MSLCHelper::isBidiLeader(const MSVehicle* leader, const std::vector<MSLane*>& cont) {
359:     if (leader == nullptr) {
360:         return false;
361:     }
362:     const MSLane* lane1 = leader->getLane()->getNormalSuccessorLane()->getBidiLane();
363:     const MSLane* lane2 = leader->getLane()->getNormalPredecessorLane()->getBidiLane();
364:     if (lane1 == nullptr && lane2 == nullptr) {
365:         return false;
366:     }
367:     bool result = std::find(cont.begin(), cont.end(), lane1) != cont.end();
368:     if (!result && lane1 != lane2 && lane2 != nullptr) {
369:         result = std::find(cont.begin(), cont.end(), lane2) != cont.end();
370:     }
371:     return result;
372: }
375: bool
376: MSLCHelper::isBidiFollower(const MSVehicle* ego, const MSVehicle* follower) {
377:     if (follower == nullptr) {
378:         return false;
379:     }
380:     bool result = false;
381:     const MSLane* lane1 = follower->getLane()->getNormalSuccessorLane()->getBidiLane();
382:     const MSLane* lane2 = follower->getLane()->getNormalPredecessorLane()->getBidiLane();
383:     const ConstMSEdgeVector& route = ego->getRoute().getEdges();
384:     if (lane1 != nullptr) {
385:         result = std::find(route.begin(), route.end(), &lane1->getEdge()) != route.end();
386:     }
387:     if (!result && lane1 != lane2 && lane2 != nullptr) {
388:         result = std::find(route.begin(), route.end(), &lane2->getEdge()) != route.end();
389:     }
390:     return result;
391: }
394: bool
395: MSLCHelper::unwillingToHelp(const MSVehicle& ego, double plannedSpeed, const MSVehicle& nv) {
396:     if (nv.getLaneChangeModel().getCooperativeHelpTime() < 0 || ego.getWaitingTime() < nv.getLaneChangeModel().getCooperativeHelpTime()) {
398:         if (nv.getLaneChangeModel().getCooperativeHelpThreshold() >= 0 && (nv.getSpeed() - plannedSpeed) > nv.getLaneChangeModel().getCooperativeHelpThreshold()) {
405:             return true;
406:         }
407:         const double nvLaneMax = nv.getLane()->getVehicleMaxSpeed(&nv);
408:         if (nv.getSpeed() / nvLaneMax < nv.getLaneChangeModel().getCooperativeMinSpeed()) {
415:             return true;
416:         }
417:     }
418:     return false;
419: }
```

### A4. Public lane-change bits — `utils/xml/SUMOXMLDefinitions.h:2182-2255`

```cpp
2184:     LCA_NONE = 0,
2186:     LCA_STAY = 1 << 0,
2188:     LCA_LEFT = 1 << 1,
2190:     LCA_RIGHT = 1 << 2,
2192:     LCA_STRATEGIC = 1 << 3,
2194:     LCA_COOPERATIVE = 1 << 4,
2196:     LCA_SPEEDGAIN = 1 << 5,
2198:     LCA_KEEPRIGHT = 1 << 6,
2200:     LCA_TRACI = 1 << 7,
2202:     LCA_URGENT = 1 << 8,
2204:     LCA_UNKNOWN = 1 << 30,
2210:     LCA_BLOCKED_BY_LEFT_LEADER = 1 << 9,
2212:     LCA_BLOCKED_BY_LEFT_FOLLOWER = 1 << 10,
2214:     LCA_BLOCKED_BY_RIGHT_LEADER = 1 << 11,
2216:     LCA_BLOCKED_BY_RIGHT_FOLLOWER = 1 << 12,
2218:     LCA_OVERLAPPING = 1 << 13,
2220:     LCA_INSUFFICIENT_SPACE = 1 << 14,
2222:     LCA_SUBLANE = 1 << 15,
2224:     LCA_INSUFFICIENT_SPEED = 1 << 28,
2226:     LCA_WANTS_LANECHANGE = LCA_LEFT | LCA_RIGHT,
2228:     LCA_WANTS_LANECHANGE_OR_STAY = LCA_WANTS_LANECHANGE | LCA_STAY,
2230:     LCA_BLOCKED_LEFT = LCA_BLOCKED_BY_LEFT_LEADER | LCA_BLOCKED_BY_LEFT_FOLLOWER,
2232:     LCA_BLOCKED_RIGHT = LCA_BLOCKED_BY_RIGHT_LEADER | LCA_BLOCKED_BY_RIGHT_FOLLOWER,
2234:     LCA_BLOCKED_BY_LEADER = LCA_BLOCKED_BY_LEFT_LEADER | LCA_BLOCKED_BY_RIGHT_LEADER,
2236:     LCA_BLOCKED_BY_FOLLOWER = LCA_BLOCKED_BY_LEFT_FOLLOWER | LCA_BLOCKED_BY_RIGHT_FOLLOWER,
2238:     LCA_BLOCKED = LCA_BLOCKED_LEFT | LCA_BLOCKED_RIGHT | LCA_INSUFFICIENT_SPACE | LCA_INSUFFICIENT_SPEED,
2240:     LCA_CHANGE_REASONS = (LCA_STRATEGIC | LCA_COOPERATIVE | LCA_SPEEDGAIN | LCA_KEEPRIGHT | LCA_SUBLANE | LCA_TRACI),
2248:     LCA_AMBLOCKINGLEADER = 1 << 16,
2249:     LCA_AMBLOCKINGFOLLOWER = 1 << 17,
2250:     LCA_MRIGHT = 1 << 18,
2251:     LCA_MLEFT = 1 << 19,
2253:     LCA_AMBLOCKINGFOLLOWER_DONTBRAKE = 1 << 21,
2255:     LCA_CHANGE_TO_HELP = 1 << 23,
```

### A4. LC2013 private bits and helpers — `microsim/lcmodels/MSLCM_LC2013.h:40-205`

```cpp
45: class MSLCM_LC2013 : public MSAbstractLaneChangeModel {
46: public:
48:     MSLCM_LC2013(MSVehicle& v);
50:     virtual ~MSLCM_LC2013();
53:     LaneChangeModel getModelID() const override {
54:         return LaneChangeModel::LC2013;
55:     }
58:     void initDerivedParameters();
60:     bool debugVehicle() const override;
70:     int wantsChange(
71:         int laneOffset,
72:         MSAbstractLaneChangeModel::MSLCMessager& msgPass, int blocked,
73:         const std::pair<MSVehicle*, double>& leader,
74:         const std::pair<MSVehicle*, double>& follower,
75:         const std::pair<MSVehicle*, double>& neighLead,
76:         const std::pair<MSVehicle*, double>& neighFollow,
77:         const MSLane& neighLane,
78:         const std::vector<MSVehicle::LaneQ>& preb,
79:         MSVehicle** lastBlocked,
80:         MSVehicle** firstBlocked) override;
82:     void* inform(void* info, MSVehicle* sender) override;
94:     double patchSpeed(const double min, const double wanted, const double max,
95:                       const MSCFModel& cfModel) override;
97:     void changed() override;
99:     void resetState() override;
101:     double getSafetyFactor() const override;
103:     double getOppositeSafetyFactor() const override;
105:     void prepareStep() override;
108:     std::string getParameter(const std::string& key) const override;
111:     void setParameter(const std::string& key, const std::string& value) override;
114:     double computeSpeedLat(double latDist, double& maneuverDist, bool urgent) const override;
119:     virtual void saveState(OutputDevice& out) const override;
124:     virtual void loadState(const SUMOSAXAttributes& attrs) override;
126: protected:
129:     double _patchSpeed(double min, const double wanted, double max,
130:                        const MSCFModel& cfModel);
133:     int _wantsChange(
134:         int laneOffset,
135:         MSAbstractLaneChangeModel::MSLCMessager& msgPass, int blocked,
136:         const std::pair<MSVehicle*, double>& leader,
137:         const std::pair<MSVehicle*, double>& follower,
138:         const std::pair<MSVehicle*, double>& neighLead,
139:         const std::pair<MSVehicle*, double>& neighFollow,
140:         const MSLane& neighLane,
141:         const std::vector<MSVehicle::LaneQ>& preb,
142:         MSVehicle* lastBlocked,
143:         MSVehicle* firstBlocked);
149:     double informLeader(MSAbstractLaneChangeModel::MSLCMessager& msgPass,
150:                         int blocked, int dir,
151:                         const std::pair<MSVehicle*, double>& neighLead,
152:                         double remainingSeconds);
155:     void informFollower(MSAbstractLaneChangeModel::MSLCMessager& msgPass,
156:                         int blocked, int dir,
157:                         const std::pair<MSVehicle*, double>& neighFollow,
158:                         double remainingSeconds,
159:                         double plannedSpeed);
171:     static double overtakeDistance(const MSVehicle* follower, const MSVehicle* leader, const double gap, double followerSpeed = INVALID_SPEED, double leaderSpeed = INVALID_SPEED);
174:     int slowDownForBlocked(MSVehicle* blocked, int state);
177:     double anticipateFollowSpeed(const std::pair<MSVehicle*, double>& leaderDist, double dist, double vMax, bool acceleratingLeader);
180:     void adaptSpeedToPedestrians(const MSLane* lane, double& v);
183:     bool saveBlockerLength(double length, double foeLeftSpace) override;
185:     inline bool amBlockingLeader() {
186:         return (myOwnState & LCA_AMBLOCKINGLEADER) != 0;
187:     }
188:     inline bool amBlockingFollower() {
189:         return (myOwnState & LCA_AMBLOCKINGFOLLOWER) != 0;
190:     }
191:     inline bool amBlockingFollowerNB() {
192:         return (myOwnState & LCA_AMBLOCKINGFOLLOWER_DONTBRAKE) != 0;
193:     }
194:     inline bool amBlockingFollowerPlusNB() {
195:         return (myOwnState & (LCA_AMBLOCKINGFOLLOWER | LCA_AMBLOCKINGFOLLOWER_DONTBRAKE)) != 0;
196:     }
197:     inline bool currentDistDisallows(double dist, int laneOffset, double lookForwardDist) {
198:         return dist / (abs(laneOffset)) < lookForwardDist;
199:     }
200:     inline bool currentDistAllows(double dist, int laneOffset, double lookForwardDist) {
201:         return dist / abs(laneOffset) > lookForwardDist;
202:     }
205:     bool hasFreeLane(int laneOffset, const std::pair<MSVehicle*, double>& neighLeadStopped) const;
```

### A5. Best lanes — `microsim/MSVehicle.cpp:6018-6540`

```cpp
6018: MSVehicle::updateBestLanes(bool forceRebuild, const MSLane* startLane) {
6024:     if (startLane == nullptr) {
6025:         startLane = myLane;
6026:     }
6027:     assert(startLane != 0);
6028:     if (myLaneChangeModel->isOpposite()) {
6032:         if (isOppositeLane(startLane)) {
6034:             startLane = startLane->getEdge().getOppositeEdge()->getLanes().back();
6035:             assert(startLane != 0);
6041:         }
6042:     }
6043:     if (forceRebuild) {
6044:         myLastBestLanesEdge = nullptr;
6045:         myLastBestLanesInternalLane = nullptr;
6046:     }
6047:     if (myBestLanes.size() > 0 && !forceRebuild && myLastBestLanesEdge == &startLane->getEdge()) {
6048:         updateOccupancyAndCurrentBestLane(startLane);
6054:         return;
6055:     }
6056:     if (startLane->getEdge().isInternal()) {
6057:         if (myBestLanes.size() == 0 || forceRebuild) {
6059:             updateBestLanes(true, startLane->getLogicalPredecessorLane());
6060:         }
6061:         if (myLastBestLanesInternalLane == startLane && !forceRebuild) {
6067:             return;
6068:         }
6071:         const MSEdge* nextEdge = startLane->getNextNormal();
6072:         assert(!nextEdge->isInternal());
6073:         for (std::vector<std::vector<LaneQ> >::iterator it = myBestLanes.begin(); it != myBestLanes.end();) {
6074:             std::vector<LaneQ>& lanes = *it;
6075:             assert(lanes.size() > 0);
6076:             if (&(lanes[0].lane->getEdge()) == nextEdge) {
6078:                 std::vector<LaneQ> oldLanes = lanes;
6079:                 lanes.clear();
6080:                 const std::vector<MSLane*>& sourceLanes = startLane->getEdge().getLanes();
6081:                 for (std::vector<MSLane*>::const_iterator it_source = sourceLanes.begin(); it_source != sourceLanes.end(); ++it_source) {
6082:                     for (std::vector<LaneQ>::iterator it_lane = oldLanes.begin(); it_lane != oldLanes.end(); ++it_lane) {
6083:                         if ((*it_source)->getLinkCont()[0]->getLane() == (*it_lane).lane) {
6084:                             lanes.push_back(*it_lane);
6085:                             break;
6086:                         }
6087:                     }
6088:                 }
6089:                 assert(lanes.size() == startLane->getEdge().getLanes().size());
6091:                 for (int i = 0; i < (int)lanes.size(); ++i) {
6092:                     if (i + lanes[i].bestLaneOffset < 0) {
6093:                         lanes[i].bestLaneOffset = -i;
6094:                     }
6095:                     if (i + lanes[i].bestLaneOffset >= (int)lanes.size()) {
6096:                         lanes[i].bestLaneOffset = (int)lanes.size() - i - 1;
6097:                     }
6098:                     assert(i + lanes[i].bestLaneOffset >= 0);
6099:                     assert(i + lanes[i].bestLaneOffset < (int)lanes.size());
6100:                     if (lanes[i].bestContinuations[0] != 0) {
6102:                         lanes[i].bestContinuations.insert(lanes[i].bestContinuations.begin(), (MSLane*)nullptr);
6103:                     }
6104:                     if (startLane->getLinkCont()[0]->getLane() == lanes[i].lane) {
6105:                         myCurrentLaneInBestLanes = lanes.begin() + i;
6106:                     }
6107:                     assert(&(lanes[i].lane->getEdge()) == nextEdge);
6108:                 }
6109:                 myLastBestLanesInternalLane = startLane;
6110:                 updateOccupancyAndCurrentBestLane(startLane);
6116:                 return;
6117:             } else {
6119:                 it = myBestLanes.erase(it);
6120:             }
6121:         }
6122:         assert(false); // should always find the next edge
6123:     }
6125:     myLastBestLanesInternalLane = nullptr;
6126:     myLastBestLanesEdge = &startLane->getEdge();
6127:     myBestLanes.clear();
6130:     MSRouteIterator nextStopEdge = myRoute->end();
6131:     const MSLane* nextStopLane = nullptr;
6132:     double nextStopPos = 0;
6133:     if (!myStops.empty()) {
6134:         const MSStop& nextStop = myStops.front();
6135:         nextStopLane = nextStop.lane;
6136:         if (nextStop.isOpposite) {
6138:             nextStopLane = nextStopLane->getEdge().getOppositeEdge()->getLanes().back();
6139:         }
6140:         nextStopEdge = nextStop.edge;
6141:         nextStopPos = nextStop.pars.startPos;
6142:     }
6144:     if (myParameter->arrivalLaneProcedure >= ArrivalLaneDefinition::GIVEN && nextStopEdge == myRoute->end() && myArrivalLane >= 0) {
6145:         nextStopEdge = (myRoute->end() - 1);
6146:         nextStopLane = (*nextStopEdge)->getLanes()[myArrivalLane];
6147:         nextStopPos = myArrivalPos;
6148:     }
6149:     if (nextStopEdge != myRoute->end()) {
6152:         nextStopPos = MAX2(POSITION_EPS, MIN2((double)nextStopPos, (double)(nextStopLane->getLength() - 2 * POSITION_EPS)));
6153:         if (nextStopLane->isInternal()) {
6155:             nextStopPos = (*nextStopEdge)->getLength();
6156:         }
6157:     }
6163:     int seen = 0;
6164:     double seenLength = 0;
6165:     bool progress = true;
6167:     const double maxBrakeDist = startLane->getLength() + getCarFollowModel().getHeadwayTime() * getMaxSpeed() + getCarFollowModel().brakeGap(getMaxSpeed()) + getVehicleType().getMinGap();
6168:     const double lookahead = getLaneChangeModel().getStrategicLookahead();
6169:     for (MSRouteIterator ce = myCurrEdge; progress;) {
6170:         std::vector<LaneQ> currentLanes;
6171:         const std::vector<MSLane*>* allowed = nullptr;
6172:         const MSEdge* nextEdge = nullptr;
6173:         if (ce != myRoute->end() && ce + 1 != myRoute->end()) {
6174:             nextEdge = *(ce + 1);
6175:             allowed = (*ce)->allowedLanes(*nextEdge, myType->getVehicleClass());
6176:         }
6177:         const std::vector<MSLane*>& lanes = (*ce)->getLanes();
6178:         for (std::vector<MSLane*>::const_iterator i = lanes.begin(); i != lanes.end(); ++i) {
6179:             LaneQ q;
6180:             MSLane* cl = *i;
6181:             q.lane = cl;
6182:             q.bestContinuations.push_back(cl);
6183:             q.bestLaneOffset = 0;
6184:             q.length = cl->allowsVehicleClass(myType->getVehicleClass()) ? (*ce)->getLength() : 0;
6185:             q.currentLength = q.length;
6187:             q.allowsContinuation = allowed == nullptr || std::find(allowed->begin(), allowed->end(), cl) != allowed->end();
6188:             q.occupation = 0;
6189:             q.nextOccupation = 0;
6190:             currentLanes.push_back(q);
6191:         }
6193:         if (nextStopEdge == ce
6195:                 && !(ce == myCurrEdge && myLane != nullptr && myLane->isInternal())) {
6196:             const MSLane* normalStopLane = nextStopLane->getNormalPredecessorLane();
6197:             for (std::vector<LaneQ>::iterator q = currentLanes.begin(); q != currentLanes.end(); ++q) {
6198:                 if (nextStopLane != nullptr && normalStopLane != (*q).lane) {
6199:                     (*q).allowsContinuation = false;
6200:                     (*q).length = nextStopPos;
6201:                     (*q).currentLength = (*q).length;
6202:                 }
6203:             }
6204:         }
6206:         myBestLanes.push_back(currentLanes);
6207:         ++seen;
6208:         seenLength += currentLanes[0].lane->getLength();
6209:         ++ce;
6210:         if (lookahead >= 0) {
6211:             progress &= (seen <= 2 || seenLength < lookahead); // custom (but we need to look at least one edge ahead)
6212:         } else {
6213:             progress &= (seen <= 4 || seenLength < MAX2(maxBrakeDist, 3000.0)); // motorway
6214:             progress &= (seen <= 8 || seenLength < MAX2(maxBrakeDist, 200.0) || isRailway(getVClass()));  // urban
6215:         }
6216:         progress &= ce != myRoute->end();
6222:     }
6225:     if (myBestLanes.size() != 0) {
6226:         double bestLength = -1;
6228:         int bestThisIndex = 0;
6229:         int bestThisMaxIndex = 0;
6230:         int index = 0;
6231:         std::vector<LaneQ>& last = myBestLanes.back();
6232:         for (std::vector<LaneQ>::iterator j = last.begin(); j != last.end(); ++j, ++index) {
6233:             if ((*j).length > bestLength) {
6234:                 bestLength = (*j).length;
6235:                 bestThisIndex = index;
6236:                 bestThisMaxIndex = index;
6237:             } else if ((*j).length == bestLength) {
6238:                 bestThisMaxIndex = index;
6239:             }
6240:         }
6241:         index = 0;
6242:         bool requiredChangeRightForbidden = false;
6243:         int requireChangeToLeftForbidden = -1;
6244:         for (std::vector<LaneQ>::iterator j = last.begin(); j != last.end(); ++j, ++index) {
6245:             if ((*j).length < bestLength) {
6246:                 if (abs(bestThisIndex - index) < abs(bestThisMaxIndex - index)) {
6247:                     (*j).bestLaneOffset = bestThisIndex - index;
6248:                 } else {
6249:                     (*j).bestLaneOffset = bestThisMaxIndex - index;
6250:                 }
6251:                 if (!(*j).allowsContinuation) {
6252:                     if ((*j).bestLaneOffset < 0 && (!(*j).lane->allowsChangingRight(getVClass())
6253:                                 || !(*j).lane->getParallelLane(-1, false)->allowsVehicleClass(getVClass())
6254:                                 || requiredChangeRightForbidden)) {
6256:                         requiredChangeRightForbidden = true;
6257:                         (*j).length = 0;
6258:                     } else if ((*j).bestLaneOffset > 0 && (!(*j).lane->allowsChangingLeft(getVClass())
6259:                                 || !(*j).lane->getParallelLane(1, false)->allowsVehicleClass(getVClass()))) {
6261:                         requireChangeToLeftForbidden = (*j).lane->getIndex();
6262:                     }
6263:                 }
6264:             }
6265:         }
6266:         for (int i = requireChangeToLeftForbidden; i >= 0; i--) {
6267:             if (last[i].bestLaneOffset > 0) {
6268:                 last[i].length = 0;
6269:             }
6270:         }
6280:     }
6283:     for (std::vector<std::vector<LaneQ> >::reverse_iterator i = myBestLanes.rbegin() + 1; i != myBestLanes.rend(); ++i) {
6284:         std::vector<LaneQ>& nextLanes = (*(i - 1));
6285:         std::vector<LaneQ>& clanes = (*i);
6286:         MSEdge* const cE = &clanes[0].lane->getEdge();
6287:         int index = 0;
6288:         double bestConnectedLength = -1;
6289:         double bestLength = -1;
6290:         for (const LaneQ& j : nextLanes) {
6291:             if (j.lane->isApproachedFrom(cE) && bestConnectedLength < j.length) {
6292:                 bestConnectedLength = j.length;
6293:             }
6294:             if (bestLength < j.length) {
6295:                 bestLength = j.length;
6296:             }
6297:         }
6299:         int bestThisIndex = 0;
6300:         int bestThisMaxIndex = 0;
6301:         if (bestConnectedLength > 0) {
6302:             index = 0;
6303:             for (LaneQ& j : clanes) {
6304:                 const LaneQ* bestConnectedNext = nullptr;
6305:                 if (j.allowsContinuation) {
6306:                     for (const LaneQ& m : nextLanes) {
6307:                         if ((m.lane->allowsVehicleClass(getVClass()) || m.lane->hadPermissionChanges())
6308:                                 && m.lane->isApproachedFrom(j.lane, getVClass())) {
6309:                             if (betterContinuation(bestConnectedNext, m)) {
6310:                                 bestConnectedNext = &m;
6311:                             }
6312:                         }
6313:                     }
6314:                     if (bestConnectedNext != nullptr) {
6315:                         if (bestConnectedNext->length == bestConnectedLength && abs(bestConnectedNext->bestLaneOffset) < 2) {
6316:                             j.length += bestLength;
6317:                         } else {
6318:                             j.length += bestConnectedNext->length;
6319:                         }
6320:                         j.bestLaneOffset = bestConnectedNext->bestLaneOffset;
6321:                     }
6322:                 }
6323:                 if (bestConnectedNext != nullptr && (bestConnectedNext->allowsContinuation || bestConnectedNext->length > 0)) {
6324:                     copy(bestConnectedNext->bestContinuations.begin(), bestConnectedNext->bestContinuations.end(), back_inserter(j.bestContinuations));
6325:                 } else {
6326:                     j.allowsContinuation = false;
6327:                 }
6328:                 if (clanes[bestThisIndex].length < j.length
6329:                         || (clanes[bestThisIndex].length == j.length && abs(clanes[bestThisIndex].bestLaneOffset) > abs(j.bestLaneOffset))
6330:                         || (clanes[bestThisIndex].length == j.length && abs(clanes[bestThisIndex].bestLaneOffset) == abs(j.bestLaneOffset) &&
6331:                             nextLinkPriority(clanes[bestThisIndex].bestContinuations) < nextLinkPriority(j.bestContinuations))
6332:                    ) {
6333:                     bestThisIndex = index;
6334:                     bestThisMaxIndex = index;
6335:                 } else if (clanes[bestThisIndex].length == j.length
6336:                            && abs(clanes[bestThisIndex].bestLaneOffset) == abs(j.bestLaneOffset)
6337:                            && nextLinkPriority(clanes[bestThisIndex].bestContinuations) == nextLinkPriority(j.bestContinuations)) {
6338:                     bestThisMaxIndex = index;
6339:                 }
6340:                 index++;
6341:             }
6344:             if (getDevice(typeid(MSDevice_ElecHybrid)) != nullptr) {
6345:                 index = 0;
6346:                 for (const LaneQ& j : clanes) {
6347:                     std::string overheadWireSegmentID = MSNet::getInstance()->getStoppingPlaceID(j.lane, j.currentLength / 2., SUMO_TAG_OVERHEAD_WIRE_SEGMENT);
6348:                     if (overheadWireSegmentID != "") {
6349:                         bestThisIndex = index;
6350:                         bestThisMaxIndex = index;
6351:                     }
6352:                     index++;
6353:                 }
6354:             }
6356:         } else {
6358:             int bestNextIndex = 0;
6359:             int bestDistToNeeded = (int) clanes.size();
6360:             index = 0;
6361:             for (std::vector<LaneQ>::iterator j = clanes.begin(); j != clanes.end(); ++j, ++index) {
6362:                 if ((*j).allowsContinuation) {
6363:                     int nextIndex = 0;
6364:                     for (std::vector<LaneQ>::const_iterator m = nextLanes.begin(); m != nextLanes.end(); ++m, ++nextIndex) {
6365:                         if ((*m).lane->isApproachedFrom((*j).lane, getVClass())) {
6366:                             if (bestDistToNeeded > abs((*m).bestLaneOffset)) {
6367:                                 bestDistToNeeded = abs((*m).bestLaneOffset);
6368:                                 bestThisIndex = index;
6369:                                 bestThisMaxIndex = index;
6370:                                 bestNextIndex = nextIndex;
6371:                             }
6372:                         }
6373:                     }
6374:                 }
6375:             }
6376:             clanes[bestThisIndex].length += nextLanes[bestNextIndex].length;
6377:             copy(nextLanes[bestNextIndex].bestContinuations.begin(), nextLanes[bestNextIndex].bestContinuations.end(), back_inserter(clanes[bestThisIndex].bestContinuations));
6379:         }
6381:         index = 0;
6382:         bool requiredChangeRightForbidden = false;
6383:         int requireChangeToLeftForbidden = -1;
6384:         for (std::vector<LaneQ>::iterator j = clanes.begin(); j != clanes.end(); ++j, ++index) {
6385:             if ((*j).length < clanes[bestThisIndex].length
6386:                     || ((*j).length == clanes[bestThisIndex].length && abs((*j).bestLaneOffset) > abs(clanes[bestThisIndex].bestLaneOffset))
6387:                     || (nextLinkPriority((*j).bestContinuations)) < nextLinkPriority(clanes[bestThisIndex].bestContinuations)
6388:                ) {
6389:                 if (abs(bestThisIndex - index) < abs(bestThisMaxIndex - index)) {
6390:                     (*j).bestLaneOffset = bestThisIndex - index;
6391:                 } else {
6392:                     (*j).bestLaneOffset = bestThisMaxIndex - index;
6393:                 }
6394:                 if ((nextLinkPriority((*j).bestContinuations)) < nextLinkPriority(clanes[bestThisIndex].bestContinuations)) {
6396:                     (*j).length = (*j).currentLength;
6397:                 }
6398:                 if (!(*j).allowsContinuation) {
6399:                     if ((*j).bestLaneOffset < 0 && (!(*j).lane->allowsChangingRight(getVClass())
6400:                                 || !(*j).lane->getParallelLane(-1, false)->allowsVehicleClass(getVClass())
6401:                                 || requiredChangeRightForbidden)) {
6403:                         requiredChangeRightForbidden = true;
6404:                         if ((*j).length == (*j).currentLength) {
6405:                             (*j).length = 0;
6406:                         }
6407:                     } else if ((*j).bestLaneOffset > 0 && (!(*j).lane->allowsChangingLeft(getVClass())
6408:                                 || !(*j).lane->getParallelLane(1, false)->allowsVehicleClass(getVClass()))) {
6410:                         requireChangeToLeftForbidden = (*j).lane->getIndex();
6411:                     }
6412:                 }
6413:             } else {
6414:                 (*j).bestLaneOffset = 0;
6415:             }
6416:         }
6417:         for (int idx = requireChangeToLeftForbidden; idx >= 0; idx--) {
6418:             if (clanes[idx].length == clanes[idx].currentLength) {
6419:                 clanes[idx].length = 0;
6420:             };
6421:         }
6424:         if (static_cast<MSDevice_ElecHybrid*>(getDevice(typeid(MSDevice_ElecHybrid))) != 0) {
6425:             index = 0;
6426:             std::string overheadWireID = MSNet::getInstance()->getStoppingPlaceID(clanes[bestThisIndex].lane, (clanes[bestThisIndex].currentLength) / 2, SUMO_TAG_OVERHEAD_WIRE_SEGMENT);
6427:             if (overheadWireID != "") {
6428:                 for (std::vector<LaneQ>::iterator j = clanes.begin(); j != clanes.end(); ++j, ++index) {
6429:                     (*j).bestLaneOffset = bestThisIndex - index;
6430:                 }
6431:             }
6432:         }
6444:     }
6445:     if (myBestLanes.front().front().lane->isInternal()) {
6447:         if (myLane != nullptr) {
6448:             startLane = myLane;
6449:         } else {
6451:             startLane = myBestLanes.front().front().lane;
6452:         }
6453:     }
6454:     updateOccupancyAndCurrentBestLane(startLane);
6460: }
6462: void
6463: MSVehicle::updateLaneBruttoSum() {
6464:     if (myLane != nullptr) {
6465:         myLane->markRecalculateBruttoSum();
6466:     }
6467: }
6469: bool
6470: MSVehicle::betterContinuation(const LaneQ* bestConnectedNext, const LaneQ& m) const {
6471:     if (bestConnectedNext == nullptr) {
6472:         return true;
6473:     } else if (m.lane->getBidiLane() != nullptr && bestConnectedNext->lane->getBidiLane() == nullptr) {
6474:         return false;
6475:     } else if (bestConnectedNext->lane->getBidiLane() != nullptr && m.lane->getBidiLane() == nullptr) {
6476:         return true;
6477:     } else if (bestConnectedNext->length < m.length) {
6478:         return true;
6479:     } else if (bestConnectedNext->length == m.length) {
6480:         if (abs(bestConnectedNext->bestLaneOffset) > abs(m.bestLaneOffset)) {
6481:             return true;
6482:         }
6483:         const double contRight = getVehicleType().getParameter().getLCParam(SUMO_ATTR_LCA_CONTRIGHT, 1);
6484:         if (contRight < 1
6487:                 && (m.lane->getIndex() - bestConnectedNext->lane->getIndex()) == 1
6488:                 && RandHelper::rand(getRNG()) > contRight) {
6489:             return true;
6490:         }
6491:     }
6492:     return false;
6493: }
6496: int
6497: MSVehicle::nextLinkPriority(const std::vector<MSLane*>& conts) {
6498:     if (conts.size() < 2) {
6499:         return -1;
6500:     } else {
6501:         const MSLink* const link = conts[0]->getLinkTo(conts[1]);
6502:         if (link != nullptr) {
6503:             return link->havePriority() ? 1 : 0;
6504:         } else {
6506:             return -1;
6507:         }
6508:     }
6509: }
6512: void
6513: MSVehicle::updateOccupancyAndCurrentBestLane(const MSLane* startLane) {
6514:     std::vector<LaneQ>& currLanes = *myBestLanes.begin();
6515:     std::vector<LaneQ>::iterator i;
6519:     for (i = currLanes.begin(); i != currLanes.end(); ++i) {
6520:         double nextOccupation = 0;
6521:         for (std::vector<MSLane*>::const_iterator j = (*i).bestContinuations.begin() + 1; j != (*i).bestContinuations.end(); ++j) {
6522:             nextOccupation += (*j)->getBruttoVehLenSum();
6523:         }
6524:         (*i).nextOccupation = nextOccupation;
6530:         if ((*i).lane == startLane) {
6531:             myCurrentLaneInBestLanes = i;
6535:         }
6536:     }
6540: }
```

### B1. Lane insertion — `microsim/MSLane.cpp:482-1423`

```cpp
482: MSLane::lastInsertion(MSVehicle& veh, double mspeed, double posLat, bool patchSpeed) {
483:     double pos = getLength() - POSITION_EPS;
484:     MSVehicle* leader = getLastAnyVehicle();
486:     double leaderBack;
487:     if (leader == nullptr) {
489:         veh.setTentativeLaneAndPosition(this, pos, posLat);
490:         veh.updateBestLanes(false, this);
491:         std::pair<MSVehicle* const, double> leaderInfo = getLeader(&veh, pos, veh.getBestLanesContinuation(), veh.getCarFollowModel().brakeGap(mspeed));
492:         leader = leaderInfo.first;
493:         leaderBack = pos + leaderInfo.second + veh.getVehicleType().getMinGap();
494:     } else {
495:         leaderBack = leader->getBackPositionOnLane(this);
497:     }
498:     if (leader == nullptr) {
500:         return isInsertionSuccess(&veh, mspeed, pos, posLat, patchSpeed, MSMoveReminder::NOTIFICATION_DEPARTED);
501:     } else {
503:         const double frontGapNeeded = veh.getCarFollowModel().getSecureGap(&veh, leader, mspeed, leader->getSpeed(), leader->getCarFollowModel().getMaxDecel()) + veh.getVehicleType().getMinGap() + POSITION_EPS;
504:         if (leaderBack >= frontGapNeeded) {
505:             pos = MIN2(pos, leaderBack - frontGapNeeded);
506:             bool result = isInsertionSuccess(&veh, mspeed, pos, posLat, patchSpeed, MSMoveReminder::NOTIFICATION_DEPARTED);
508:             return result;
509:         }
511:     }
512:     return false;
513: }
516: bool
517: MSLane::freeInsertion(MSVehicle& veh, double mspeed, double posLat,
518:                       MSMoveReminder::Notification notification) {
520:     double maxPos = myLength;
521:     if (veh.hasStops() && veh.getNextStop().edge == veh.getCurrentRouteEdge()) {
522:         maxPos = MAX2(0.0, veh.getNextStop().getEndPos(veh));
523:     }
524:     const double minPos = (notification == MSMoveReminder::NOTIFICATION_TELEPORT ?
525:                            MIN2(maxPos, veh.getVehicleType().getLength()) : 0);
526:     veh.setTentativeLaneAndPosition(this, minPos, 0);
527:     if (myVehicles.size() == 0) {
529:         const double backOffset = minPos - veh.getVehicleType().getLength();
530:         const double missingRearGap = getMissingRearGap(&veh, backOffset, mspeed);
531:         if (missingRearGap > 0) {
532:             if (minPos + missingRearGap <= maxPos) {
539:                 return isInsertionSuccess(&veh, mspeed, minPos + missingRearGap, posLat, true, notification);
540:             }
541:             return false;
542:         } else {
543:             return isInsertionSuccess(&veh, mspeed, minPos, posLat, true, notification);
544:         }
546:     } else {
548:         const MSVehicle* const leader = myVehicles.back(); // @todo reproduction of bogus old behavior. see #1961
549:         const double leaderPos = leader->getBackPositionOnLane(this);
550:         const double speed = leader->getSpeed();
551:         const double frontGapNeeded = veh.getCarFollowModel().getSecureGap(&veh, leader, speed, leader->getSpeed(), leader->getCarFollowModel().getMaxDecel()) + veh.getVehicleType().getMinGap();
552:         if (leaderPos >= frontGapNeeded) {
553:             const double tspeed = MIN2(veh.getCarFollowModel().insertionFollowSpeed(&veh, mspeed, frontGapNeeded, leader->getSpeed(), leader->getCarFollowModel().getMaxDecel(), leader), mspeed);
555:             if (isInsertionSuccess(&veh, tspeed, minPos, posLat, true, notification)) {
557:                 return true;
558:             }
559:         }
560:     }
562:     MSLane::VehCont::iterator predIt = myVehicles.begin();
563:     while (predIt != myVehicles.end()) {
566:         const MSVehicle* leader = predIt != myVehicles.end() - 1 ? *(predIt + 1) : nullptr;
567:         if (leader == nullptr && myPartialVehicles.size() > 0) {
568:             leader = myPartialVehicles.front();
569:         }
570:         const MSVehicle* follower = *predIt;
573:         double speed = mspeed;
574:         if (leader != nullptr) {
575:             speed = MIN2(leader->getSpeed(), mspeed);
576:         }
579:         double frontMax = maxPos;
580:         if (leader != nullptr) {
581:             double leaderRearPos = leader->getBackPositionOnLane(this);
582:             double frontGapNeeded = veh.getCarFollowModel().getSecureGap(&veh, leader, speed, leader->getSpeed(), leader->getCarFollowModel().getMaxDecel()) + veh.getVehicleType().getMinGap();
583:             frontMax = MIN2(maxPos, leaderRearPos - frontGapNeeded);
584:         }
586:         const double followPos = follower->getPositionOnLane() + follower->getVehicleType().getMinGap();
587:         const double backGapNeeded = follower->getCarFollowModel().getSecureGap(follower, &veh, follower->getSpeed(), veh.getSpeed(), veh.getCarFollowModel().getMaxDecel());
588:         const double backMin = followPos + backGapNeeded + veh.getVehicleType().getLength();
591:         if (frontMax > minPos && backMin + POSITION_EPS < frontMax) {
593:             if (isInsertionSuccess(&veh, speed, backMin + POSITION_EPS, posLat, true, notification)) {
595:                 return true;
596:             }
597:         }
598:         ++predIt;
599:     }
602:     return false;
603: }
606: double
607: MSLane::getDepartSpeed(const MSVehicle& veh, bool& patchSpeed) {
608:     double speed = 0;
609:     const SUMOVehicleParameter& pars = veh.getParameter();
610:     DepartSpeedDefinition dsd = pars.departSpeedProcedure;
611:     if (dsd == DepartSpeedDefinition::DEFAULT) {
612:         dsd = myDefaultDepartSpeedDefinition;
613:         if (dsd == DepartSpeedDefinition::GIVEN) {
614:             speed = myDefaultDepartSpeed;
615:         }
616:     } else if (dsd == DepartSpeedDefinition::GIVEN) {
617:         speed = pars.departSpeed;;
618:     }
619:     switch (dsd) {
620:         case DepartSpeedDefinition::GIVEN:
621:             patchSpeed = false;
622:             break;
623:         case DepartSpeedDefinition::RANDOM:
624:             speed = roundDecimal(RandHelper::rand(getVehicleMaxSpeed(&veh)), gPrecisionRandom);
625:             patchSpeed = true;
626:             break;
627:         case DepartSpeedDefinition::MAX:
628:             speed = getVehicleMaxSpeed(&veh);
629:             patchSpeed = true;
630:             break;
631:         case DepartSpeedDefinition::DESIRED:
632:             speed = getVehicleMaxSpeed(&veh);
633:             patchSpeed = false;
634:             break;
635:         case DepartSpeedDefinition::LIMIT:
636:             speed = getVehicleMaxSpeed(&veh) / veh.getChosenSpeedFactor();
637:             patchSpeed = false;
638:             break;
639:         case DepartSpeedDefinition::LAST: {
640:             MSVehicle* last = getLastAnyVehicle();
641:             speed = getVehicleMaxSpeed(&veh);
642:             if (last != nullptr) {
643:                 speed = MIN2(speed, last->getSpeed());
644:                 patchSpeed = false;
645:             }
646:             break;
647:         }
648:         case DepartSpeedDefinition::AVG: {
649:             speed = MIN2(getVehicleMaxSpeed(&veh), getMeanSpeed());
650:             if (getLastAnyVehicle() != nullptr) {
651:                 patchSpeed = false;
652:             }
653:             break;
654:         }
655:         case DepartSpeedDefinition::DEFAULT:
656:         default:
658:             patchSpeed = false; // @todo check
659:             break;
660:     }
661:     return speed;
662: }
665: double
666: MSLane::getDepartPosLat(const MSVehicle& veh) {
667:     const SUMOVehicleParameter& pars = veh.getParameter();
668:     switch (pars.departPosLatProcedure) {
669:         case DepartPosLatDefinition::GIVEN:
670:             return pars.departPosLat;
671:         case DepartPosLatDefinition::RIGHT:
672:             return -getWidth() * 0.5 + veh.getVehicleType().getWidth() * 0.5;
673:         case DepartPosLatDefinition::LEFT:
674:             return getWidth() * 0.5 - veh.getVehicleType().getWidth() * 0.5;
675:         case DepartPosLatDefinition::RANDOM: {
676:             const double raw = RandHelper::rand(getWidth() - veh.getVehicleType().getWidth()) - getWidth() * 0.5 + veh.getVehicleType().getWidth() * 0.5;
677:             return roundDecimal(raw, gPrecisionRandom);
678:         }
679:         case DepartPosLatDefinition::CENTER:
680:         case DepartPosLatDefinition::DEFAULT:
685:         default:
686:             return 0;
687:     }
688: }
691: bool
692: MSLane::insertVehicle(MSVehicle& veh) {
693:     double pos = 0;
694:     bool patchSpeed = true; // whether the speed shall be adapted to infrastructure/traffic in front
695:     const SUMOVehicleParameter& pars = veh.getParameter();
696:     double speed = getDepartSpeed(veh, patchSpeed);
697:     double posLat = getDepartPosLat(veh);
700:     switch (pars.departPosProcedure) {
701:         case DepartPosDefinition::GIVEN:
702:             pos = pars.departPos;
703:             if (pos < 0.) {
704:                 pos += myLength;
705:             }
706:             break;
707:         case DepartPosDefinition::RANDOM:
708:             pos = roundDecimal(RandHelper::rand(getLength()), gPrecisionRandom);
709:             break;
710:         case DepartPosDefinition::RANDOM_FREE: {
711:             for (int i = 0; i < 10; i++) {
713:                 pos = RandHelper::rand(getLength());
714:                 posLat = getDepartPosLat(veh); // could be random as well
715:                 if (isInsertionSuccess(&veh, speed, pos, posLat, patchSpeed, MSMoveReminder::NOTIFICATION_DEPARTED)) {
716:                     MSNet::getInstance()->getInsertionControl().retractDescheduleDeparture(&veh);
717:                     return true;
718:                 }
719:             }
721:             bool success = freeInsertion(veh, speed, posLat);
722:             if (success) {
723:                 MSNet::getInstance()->getInsertionControl().retractDescheduleDeparture(&veh);
724:             }
725:             return success;
726:         }
727:         case DepartPosDefinition::FREE:
728:             return freeInsertion(veh, speed, posLat);
729:         case DepartPosDefinition::LAST:
730:             return lastInsertion(veh, speed, posLat, patchSpeed);
731:         case DepartPosDefinition::STOP:
732:             if (veh.hasStops() && veh.getNextStop().edge == veh.getCurrentRouteEdge()) {
734:                 pos = MAX2(0.0, veh.getNextStop().getEndPos(veh));
735:                 break;
736:             }
737:             FALLTHROUGH;
738:         case DepartPosDefinition::BASE:
739:         case DepartPosDefinition::DEFAULT:
740:         case DepartPosDefinition::SPLIT_FRONT:
741:         default:
742:             if (pars.departProcedure == DepartDefinition::SPLIT) {
743:                 pos = getLength();
745:                 AnyVehicleIterator end = anyVehiclesEnd();
746:                 for (AnyVehicleIterator it = anyVehiclesBegin(); it != end; ++it) {
747:                     const MSVehicle* cand = *it;
748:                     if (cand->isStopped() && cand->getNextStopParameter()->split == veh.getID()) {
749:                         if (pars.departPosProcedure == DepartPosDefinition::SPLIT_FRONT) {
750:                             pos = cand->getPositionOnLane() + cand->getVehicleType().getMinGap() + veh.getLength();
751:                         } else {
752:                             pos = cand->getBackPositionOnLane() - veh.getVehicleType().getMinGap();
753:                         }
754:                         break;
755:                     }
756:                 }
757:             } else {
758:                 pos = veh.basePos(myEdge);
759:             }
760:             break;
761:     }
763:     if (MSGlobals::gLateralResolution > 0) {
764:         switch (pars.departPosLatProcedure) {
765:             case DepartPosLatDefinition::RANDOM_FREE: {
766:                 for (int i = 0; i < 10; i++) {
768:                     posLat = RandHelper::rand(getWidth()) - getWidth() * 0.5;
769:                     if (isInsertionSuccess(&veh, speed, pos, posLat, patchSpeed, MSMoveReminder::NOTIFICATION_DEPARTED)) {
770:                         return true;
771:                     }
772:                 }
773:                 FALLTHROUGH;
774:             }
776:             case DepartPosLatDefinition::FREE: {
778:                 double posLatMin = -getWidth() * 0.5 + veh.getVehicleType().getWidth() * 0.5;
779:                 double posLatMax = getWidth() * 0.5 - veh.getVehicleType().getWidth() * 0.5;
780:                 for (posLat = posLatMin; posLat < posLatMax; posLat += MSGlobals::gLateralResolution) {
781:                     if (isInsertionSuccess(&veh, speed, pos, posLat, patchSpeed, MSMoveReminder::NOTIFICATION_DEPARTED)) {
782:                         return true;
783:                     }
784:                 }
785:                 return false;
786:             }
787:             default:
788:                 break;
789:         }
790:     }
792:     const bool success = isInsertionSuccess(&veh, speed, pos, posLat, patchSpeed, MSMoveReminder::NOTIFICATION_DEPARTED);
798:     if (success && myExtrapolateSubstepDepart && veh.getDepartDelay() > 0) {
799:         SUMOTime relevantDelay = MIN2(DELTA_T, veh.getDepartDelay());
801:         speed = veh.getSpeed(); // may have been adapted in isInsertionSuccess
802:         double dist = speed * STEPS2TIME(relevantDelay);
803:         std::pair<MSVehicle* const, double> leaderInfo = getLeader(&veh, pos, veh.getBestLanesContinuation());
804:         if (leaderInfo.first != nullptr) {
805:             MSVehicle* leader = leaderInfo.first;
806:             const double frontGapNeeded = veh.getCarFollowModel().getSecureGap(&veh, leader, speed, leader->getSpeed(),
807:                                           leader->getCarFollowModel().getMaxDecel());
808:             dist = MIN2(dist, leaderInfo.second - frontGapNeeded);
809:         }
810:         if (dist > 0) {
811:             veh.executeFractionalMove(dist);
812:         }
813:     }
814:     return success;
815: }
818: bool
819: MSLane::checkFailure(const MSVehicle* aVehicle, double& speed, double& dist, const double nspeed, const bool patchSpeed, const std::string errorMsg, InsertionCheck check) const {
820:     if (nspeed < speed) {
821:         if (patchSpeed) {
822:             speed = MIN2(nspeed, speed);
823:             dist = aVehicle->getCarFollowModel().brakeGap(speed) + aVehicle->getVehicleType().getMinGap();
824:         } else if (speed > 0) {
825:             if ((aVehicle->getInsertionChecks() & (int)check) == 0) {
826:                 return false;
827:             }
828:             if (MSGlobals::gEmergencyInsert) {
830:                 double emergencyBrakeGap = 0.5 * speed * speed / aVehicle->getCarFollowModel().getEmergencyDecel();
831:                 if (emergencyBrakeGap <= dist) {
834:                     WRITE_WARNINGF(TL("Vehicle '%' is inserted in an emergency situation, time=%."), aVehicle->getID(), time2string(SIMSTEP));
835:                     return false;
836:                 }
837:             }
839:             if (errorMsg != "") {
840:                 WRITE_ERRORF(TL("Vehicle '%' will not be able to depart on lane '%' with speed % (%), time=%."),
841:                              aVehicle->getID(), getID(), speed, errorMsg, time2string(SIMSTEP));
842:                 MSNet::getInstance()->getInsertionControl().descheduleDeparture(aVehicle);
843:             }
844:             return true;
845:         }
846:     }
847:     return false;
848: }
851: bool
852: MSLane::isInsertionSuccess(MSVehicle* aVehicle,
853:                            double speed, double pos, double posLat, bool patchSpeed,
854:                            MSMoveReminder::Notification notification) {
855:     int insertionChecks = aVehicle->getInsertionChecks();
856:     if (pos < 0 || pos > myLength) {
858:         WRITE_WARNINGF(TL("Invalid departPos % given for vehicle '%', time=%. Inserting at lane end instead."),
859:                        pos, aVehicle->getID(), time2string(SIMSTEP));
860:         pos = myLength;
861:     }
876:     aVehicle->setTentativeLaneAndPosition(this, pos, posLat);
877:     aVehicle->updateBestLanes(false, this);
878:     const MSCFModel& cfModel = aVehicle->getCarFollowModel();
879:     const std::vector<MSLane*>& bestLaneConts = aVehicle->getBestLanesContinuation(this);
880:     std::vector<MSLane*>::const_iterator ri = bestLaneConts.begin();
881:     double seen = getLength() - pos; // == distance from insertion position until the end of the currentLane
882:     double dist = cfModel.brakeGap(speed) + aVehicle->getVehicleType().getMinGap();
883:     const bool isRail = aVehicle->isRail();
884:     if (isRail && insertionChecks != (int)InsertionCheck::NONE
885:             && aVehicle->getParameter().departProcedure != DepartDefinition::SPLIT
886:             && MSRailSignalControl::isSignalized(aVehicle->getVClass())
887:             && isRailwayOrShared(myPermissions)) {
888:         const MSDriveWay* dw = MSDriveWay::getDepartureDriveway(aVehicle);
889:         MSEdgeVector occupied;
893:         if (dw->foeDriveWayOccupied(false, aVehicle, occupied)) {
894:             setParameter("insertionBlocked:" + aVehicle->getID(), dw->getID());
901:             return false;
902:         }
906:     }
907:     if (getBidiLane() != nullptr && isRail) {
909:         if (getBidiLane()->getVehicleNumberWithPartials() > 0 && (insertionChecks & (int)InsertionCheck::BIDI) != 0) {
915:             return false;
916:         }
918:         double backLength = aVehicle->getLength() - pos;
919:         if (backLength > 0 && (insertionChecks & (int)InsertionCheck::BIDI) != 0) {
920:             MSLane* pred = getLogicalPredecessorLane();
921:             MSLane* bidi = pred == nullptr ? nullptr : pred->getBidiLane();
922:             while (backLength > 0 && bidi != nullptr) {
923:                 if (bidi->getVehicleNumberWithPartials() > 0) {
929:                     return false;
930:                 }
931:                 backLength -= bidi->getLength();
932:                 pred = pred->getLogicalPredecessorLane();
933:                 bidi = pred == nullptr ? nullptr : pred->getBidiLane();
934:             }
935:         }
936:     }
937:     MSLink* firstRailSignal = nullptr;
938:     double firstRailSignalDist = -1;
940:     const bool patchSpeedSpecial = patchSpeed || aVehicle->getParameter().departSpeedProcedure != DepartSpeedDefinition::GIVEN;
944:     if (aVehicle->hasStops()) {
945:         const MSStop& nextStop = aVehicle->getNextStop();
946:         if (nextStop.lane == this) {
947:             std::stringstream msg;
948:             double distToStop, safeSpeed;
949:             if (nextStop.pars.speed > 0) {
950:                 msg << "scheduled waypoint on lane '" << myID << "' too close";
951:                 distToStop = MAX2(0.0, nextStop.pars.startPos - pos);
952:                 safeSpeed = cfModel.freeSpeed(aVehicle, speed, distToStop, nextStop.pars.speed, true, MSCFModel::CalcReason::FUTURE);
953:             } else {
954:                 msg << "scheduled stop on lane '" << myID << "' too close";
955:                 distToStop = nextStop.pars.endPos - pos;
956:                 safeSpeed = cfModel.stopSpeed(aVehicle, speed, distToStop, MSCFModel::CalcReason::FUTURE);
957:             }
958:             if (checkFailure(aVehicle, speed, dist, MAX2(0.0, safeSpeed), patchSpeedSpecial, msg.str(), InsertionCheck::STOP)) {
960:                 return false;
961:             }
962:         }
963:     }
966:     const MSLeaderInfo leaders = getLastVehicleInformation(aVehicle, 0, pos);
968:     const double nspeed = safeInsertionSpeed(aVehicle, -pos, leaders, speed);
969:     if (nspeed == INVALID_SPEED || checkFailure(aVehicle, speed, dist, nspeed, patchSpeed, "", InsertionCheck::LEADER_GAP)) {
984:         return false;
985:     }
992:     const MSRoute& r = aVehicle->getRoute();
993:     MSRouteIterator ce = r.begin();
994:     int nRouteSuccs = 1;
995:     MSLane* currentLane = this;
996:     MSLane* nextLane = this;
997:     SUMOTime arrivalTime = MSNet::getInstance()->getCurrentTimeStep() + TIME2STEPS(seen / MAX2(speed, SUMO_const_haltingSpeed));
998:     while ((seen < dist || (isRail && firstRailSignal == nullptr)) && ri != bestLaneConts.end()) {
1000:         std::vector<MSLink*>::const_iterator link = succLinkSec(*aVehicle, nRouteSuccs, *currentLane, bestLaneConts);
1002:         if (currentLane->isLinkEnd(link)) {
1003:             if (&currentLane->getEdge() == r.getLastEdge()) {
1005:                 if (aVehicle->getParameter().arrivalSpeedProcedure == ArrivalSpeedDefinition::GIVEN) {
1006:                     const double remaining = seen + aVehicle->getArrivalPos() - currentLane->getLength();
1007:                     const double fspeed = cfModel.freeSpeed(aVehicle, speed, remaining, aVehicle->getParameter().arrivalSpeed, true, MSCFModel::CalcReason::FUTURE);
1008:                     if (checkFailure(aVehicle, speed, dist, fspeed,
1009:                                      patchSpeedSpecial, "arrival speed too low", InsertionCheck::ARRIVAL_SPEED)) {
1011:                         return false;
1012:                     }
1013:                 }
1014:                 if (mayContinue(aVehicle) && hasUnsafeLink()) {
1016:                     if (checkFailure(aVehicle, speed, dist, cfModel.insertionStopSpeed(aVehicle, speed, seen),
1017:                                      patchSpeedSpecial, "junction '" + currentLane->getEdge().getToJunction()->getID() + "' too close", InsertionCheck::JUNCTION)) {
1019:                         return false;
1020:                     }
1021:                 }
1022:             } else {
1024:                 if (checkFailure(aVehicle, speed, dist, cfModel.insertionStopSpeed(aVehicle, speed, seen),
1025:                                  patchSpeedSpecial, "junction '" + currentLane->getEdge().getToJunction()->getID() + "' too close", InsertionCheck::JUNCTION)) {
1027:                     return false;
1028:                 }
1029:             }
1030:             break;
1031:         }
1032:         if (isRail && firstRailSignal == nullptr) {
1033:             std::string constraintInfo;
1034:             bool isInsertionOrder;
1035:             if (MSRailSignal::hasInsertionConstraint(*link, aVehicle, constraintInfo, isInsertionOrder)) {
1036:                 setParameter((isInsertionOrder ? "insertionOrder" : "insertionConstraint:")
1037:                              + aVehicle->getID(), constraintInfo);
1043:                 return false;
1044:             }
1045:         }
1048:         if (firstRailSignal == nullptr && (*link)->getTLLogic() != nullptr) {
1049:             firstRailSignal = *link;
1050:             firstRailSignalDist = seen;
1051:         }
1052:         nextLane = (*link)->getViaLaneOrLane();
1053:         if (!(*link)->opened(arrivalTime, speed, speed, aVehicle->getVehicleType().getLength(), aVehicle->getImpatience(),
1054:                              cfModel.getMaxDecel(), 0, posLat, nullptr, false, aVehicle)
1055:                 || (*link)->railSignalWasPassed()
1056:                 || !(*link)->havePriority()
1057:                 || (*link)->getState() == LINKSTATE_ZIPPER) {
1059:             std::string errorMsg = "";
1060:             const LinkState state = (*link)->getState();
1061:             if (state == LINKSTATE_MINOR
1062:                     || state == LINKSTATE_EQUAL
1063:                     || state == LINKSTATE_STOP
1064:                     || state == LINKSTATE_ALLWAY_STOP) {
1066:                 errorMsg = "unpriorised junction too close";
1067:             } else if ((*link)->getTLLogic() != nullptr && !(*link)->getTLLogic()->getsMajorGreen((*link)->getTLIndex())) {
1069:                 errorMsg = "tlLogic '" + (*link)->getTLLogic()->getID() + "' link " + toString((*link)->getTLIndex()) + " never switches to 'G'";
1070:             }
1071:             const double laneStopOffset = MAX2(getVehicleStopOffset(aVehicle),
1072:                                                aVehicle->getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_STOPLINE_CROSSING_GAP, MSPModel::SAFETY_GAP) - (*link)->getDistToFoePedCrossing());
1073:             const double remaining = seen - laneStopOffset;
1074:             if (checkFailure(aVehicle, speed, dist, cfModel.insertionStopSpeed(aVehicle, speed, remaining),
1075:                              patchSpeedSpecial, errorMsg, InsertionCheck::JUNCTION)) {
1090:                 return false;
1091:             }
1099:             if (seen >= aVehicle->getVehicleType().getMinGap()) {
1100:                 break;
1101:             }
1102:         } else if (nextLane->isInternal()) {
1103:             double tmp = 0;
1104:             bool dummyReq = true;
1111:             double nSpeed = speed;
1112:             aVehicle->checkLinkLeader(nextLane->getLinkCont()[0], nextLane, seen + nextLane->getLength(), nullptr, nSpeed, tmp, tmp, dummyReq);
1116:             if (checkFailure(aVehicle, speed, dist, nSpeed, patchSpeed, "", InsertionCheck::LEADER_GAP)) {
1123:                 return false;
1124:             }
1125:         }
1127:         if (nextLane != nullptr) {
1130:             if (firstRailSignal == nullptr && nextLane->getBidiLane() != nullptr && nextLane->getBidiLane()->getVehicleNumberWithPartials() > 0) {
1131:                 if ((insertionChecks & (int)InsertionCheck::ONCOMING_TRAIN) != 0) {
1137:                     return false;
1138:                 }
1139:             }
1143:             if (aVehicle->hasStops()) {
1144:                 const MSStop& nextStop = aVehicle->getNextStop();
1145:                 if (nextStop.lane == nextLane) {
1146:                     std::stringstream msg;
1147:                     msg << "scheduled stop on lane '" << nextStop.lane->getID() << "' too close";
1148:                     const double distToStop = seen + nextStop.pars.endPos;
1149:                     if (checkFailure(aVehicle, speed, dist, cfModel.insertionStopSpeed(aVehicle, speed, distToStop),
1150:                                      patchSpeedSpecial, msg.str(), InsertionCheck::STOP)) {
1152:                         return false;
1153:                     }
1154:                 }
1155:             }
1158:             const MSLeaderInfo nextLeaders = nextLane->getLastVehicleInformation(aVehicle, 0, 0);
1159:             if (nextLeaders.hasVehicles()) {
1160:                 const double nextLaneSpeed = nextLane->safeInsertionSpeed(aVehicle, seen, nextLeaders, speed);
1166:                 if (nextLaneSpeed == INVALID_SPEED || checkFailure(aVehicle, speed, dist, nextLaneSpeed, patchSpeed, "", InsertionCheck::LEADER_GAP)) {
1182:                     return false;
1183:                 }
1184:             }
1185:             if (!nextLane->checkForPedestrians(aVehicle, speed, dist, -seen, patchSpeed)) {
1186:                 return false;
1187:             }
1189:             const double freeSpeed = cfModel.freeSpeed(aVehicle, speed, seen, nextLane->getVehicleMaxSpeed(aVehicle), true, MSCFModel::CalcReason::FUTURE);
1190:             if (freeSpeed < speed) {
1191:                 if (patchSpeedSpecial) {
1192:                     speed = freeSpeed;
1193:                     dist = cfModel.brakeGap(speed) + aVehicle->getVehicleType().getMinGap();
1194:                 } else {
1195:                     if ((insertionChecks & (int)InsertionCheck::SPEED_LIMIT) != 0) {
1196:                         if (!MSGlobals::gCheckRoutes) {
1197:                             WRITE_WARNINGF(TL("Vehicle '%' is inserted too fast and will violate the speed limit on a lane '%', time=%."),
1198:                                            aVehicle->getID(), nextLane->getID(), time2string(SIMSTEP));
1199:                         } else {
1201:                             WRITE_ERRORF(TL("Vehicle '%' will not be able to depart using the given velocity (slow lane ahead), time=%."), aVehicle->getID(), time2string(SIMSTEP));
1202:                             MSNet::getInstance()->getInsertionControl().descheduleDeparture(aVehicle);
1203:                             return false;
1204:                         }
1205:                     }
1206:                 }
1207:             }
1211:             const SUMOTime leaveTime = (*link)->getLeaveTime(arrivalTime, speed, speed, aVehicle->getVehicleType().getLength());
1212:             if ((*link)->hasApproachingFoe(arrivalTime, leaveTime, speed, cfModel.getMaxDecel())) {
1213:                 if (checkFailure(aVehicle, speed, dist, cfModel.insertionStopSpeed(aVehicle, speed, seen), patchSpeed, "", InsertionCheck::JUNCTION)) {
1215:                     return false;
1216:                 }
1217:             }
1218:             arrivalTime += TIME2STEPS(nextLane->getLength() / MAX2(speed, NUMERICAL_EPS));
1219:             seen += nextLane->getLength();
1220:             currentLane = nextLane;
1221:             if ((*link)->getViaLane() == nullptr) {
1222:                 nRouteSuccs++;
1223:                 ++ce;
1224:                 ++ri;
1225:             }
1226:         }
1227:     }
1229:     const MSLeaderDistanceInfo& followers = getFollowersOnConsecutive(aVehicle, aVehicle->getBackPositionOnLane(), false);
1230:     for (int i = 0; i < followers.numSublanes(); ++i) {
1231:         const MSVehicle* follower = followers[i].first;
1232:         if (follower != nullptr) {
1233:             const double backGapNeeded = follower->getCarFollowModel().getSecureGap(follower, aVehicle, follower->getSpeed(), speed, cfModel.getMaxDecel());
1234:             if (followers[i].second < backGapNeeded
1235:                     && ((insertionChecks & (int)InsertionCheck::FOLLOWER_GAP) != 0
1236:                         || (followers[i].second < 0 && (insertionChecks & (int)InsertionCheck::COLLISION) != 0))) {
1252:                 return false;
1253:             }
1254:         }
1255:     }
1257:     if (!checkForPedestrians(aVehicle, speed, dist, pos, patchSpeed)) {
1258:         return false;
1259:     }
1261:     MSLane* shadowLane = aVehicle->getLaneChangeModel().getShadowLane(this);
1267:     if (shadowLane != nullptr) {
1268:         const MSLeaderDistanceInfo& shadowFollowers = shadowLane->getFollowersOnConsecutive(aVehicle, aVehicle->getBackPositionOnLane(), false);
1269:         for (int i = 0; i < shadowFollowers.numSublanes(); ++i) {
1270:             const MSVehicle* follower = shadowFollowers[i].first;
1271:             if (follower != nullptr) {
1272:                 const double backGapNeeded = follower->getCarFollowModel().getSecureGap(follower, aVehicle, follower->getSpeed(), speed, cfModel.getMaxDecel());
1273:                 if (shadowFollowers[i].second < backGapNeeded
1274:                         && ((insertionChecks & (int)InsertionCheck::FOLLOWER_GAP) != 0
1275:                             || (shadowFollowers[i].second < 0 && (insertionChecks & (int)InsertionCheck::COLLISION) != 0))) {
1292:                     return false;
1293:                 }
1294:             }
1295:         }
1296:         const MSLeaderInfo& ahead = shadowLane->getLastVehicleInformation(nullptr, 0, aVehicle->getPositionOnLane(), false);
1297:         for (int i = 0; i < ahead.numSublanes(); ++i) {
1298:             const MSVehicle* veh = ahead[i];
1299:             if (veh != nullptr) {
1300:                 const double gap = veh->getBackPositionOnLane(shadowLane) - aVehicle->getPositionOnLane() - aVehicle->getVehicleType().getMinGap();
1301:                 const double gapNeeded = aVehicle->getCarFollowModel().getSecureGap(aVehicle, veh, speed, veh->getSpeed(), veh->getCarFollowModel().getMaxDecel());
1302:                 if (gap <  gapNeeded
1303:                         && ((insertionChecks & (int)InsertionCheck::LEADER_GAP) != 0
1304:                             || (gap < 0 && (insertionChecks & (int)InsertionCheck::COLLISION) != 0))) {
1321:                     return false;
1322:                 }
1323:             }
1324:         }
1325:     }
1326:     if (followers.numFreeSublanes() > 0) {
1328:         const double backOffset = pos - aVehicle->getVehicleType().getLength();
1329:         const double missingRearGap = getMissingRearGap(aVehicle, backOffset, speed);
1330:         if (missingRearGap > 0
1331:                 && (insertionChecks & (int)InsertionCheck::LEADER_GAP) != 0) {
1346:             return false;
1347:         }
1348:     }
1349:     if (insertionChecks == (int)InsertionCheck::NONE) {
1350:         speed = MAX2(0.0, speed);
1351:     }
1353:     if (speed < 0) {
1366:         return false;
1367:     }
1368:     const int bestLaneOffset = aVehicle->getBestLaneOffset();
1369:     const double extraReservation = aVehicle->getLaneChangeModel().getExtraReservation(bestLaneOffset);
1370:     if (extraReservation > 0) {
1371:         std::stringstream msg;
1372:         msg << "too many lane changes required on lane '" << myID << "'";
1374:         double distToStop = aVehicle->getBestLaneDist() - pos - extraReservation - speed * aVehicle->getActionStepLengthSecs();
1375:         if (distToStop >= 0) {
1376:             double stopSpeed = cfModel.stopSpeed(aVehicle, speed, distToStop, MSCFModel::CalcReason::FUTURE);
1384:             if (checkFailure(aVehicle, speed, distToStop, MAX2(0.0, stopSpeed),
1385:                              patchSpeedSpecial, msg.str(), InsertionCheck::LANECHANGE)) {
1387:                 return false;
1388:             }
1389:         }
1390:     }
1392:     incorporateVehicle(aVehicle, pos, speed, posLat, find_if(myVehicles.begin(), myVehicles.end(), [&](MSVehicle * const v) {
1393:         return v->getPositionOnLane() >= pos;
1394:     }), notification);
1410:     if (isRail) {
1411:         unsetParameter("insertionConstraint:" + aVehicle->getID());
1412:         unsetParameter("insertionOrder:" + aVehicle->getID());
1413:         unsetParameter("insertionBlocked:" + aVehicle->getID());
1416:         if (firstRailSignal != nullptr && firstRailSignal->getJunction()->getType() == SumoXMLNodeType::RAIL_SIGNAL) {
1417:             aVehicle->registerInsertionApproach(firstRailSignal, firstRailSignalDist);
1418:         }
1419:     }
1420:     return true;
1421: }
```

### B1. Edge insertion — `microsim/MSEdge.cpp:700-945`

```cpp
700: MSLane*
701: MSEdge::getDepartLane(MSVehicle& veh) const {
702:     DepartLaneDefinition dld = veh.getParameter().departLaneProcedure;
703:     int departLane = veh.getParameter().departLane;
704:     if (dld == DepartLaneDefinition::DEFAULT) {
705:         dld = myDefaultDepartLaneDefinition;
706:         departLane = myDefaultDepartLane;
707:     }
708:     switch (dld) {
709:         case DepartLaneDefinition::GIVEN:
710:             if ((int) myLanes->size() <= departLane || !(*myLanes)[departLane]->allowsVehicleClass(veh.getVClass())) {
711:                 return nullptr;
712:             }
713:             return (*myLanes)[departLane];
714:         case DepartLaneDefinition::RANDOM:
715:             return RandHelper::getRandomFrom(*allowedLanes(veh.getVehicleType().getVehicleClass()));
716:         case DepartLaneDefinition::FREE:
717:             return getFreeLane(nullptr, veh.getVehicleType().getVehicleClass(), getDepartPosBound(veh, false));
718:         case DepartLaneDefinition::ALLOWED_FREE:
719:             if (veh.getRoute().size() == 1) {
720:                 return getFreeLane(nullptr, veh.getVehicleType().getVehicleClass(), getDepartPosBound(veh, false));
721:             } else {
722:                 return getFreeLane(allowedLanes(**(veh.getRoute().begin() + 1), veh.getVehicleType().getVehicleClass()), veh.getVehicleType().getVehicleClass(), getDepartPosBound(veh, false));
723:             }
724:         case DepartLaneDefinition::BEST_FREE:
725:         case DepartLaneDefinition::BEST_PROB: {
726:             veh.updateBestLanes(false, myLanes->front());
727:             const std::vector<MSVehicle::LaneQ>& bl = veh.getBestLanes();
728:             double bestLength = -1;
729:             for (std::vector<MSVehicle::LaneQ>::const_iterator i = bl.begin(); i != bl.end(); ++i) {
730:                 if ((*i).length > bestLength) {
731:                     bestLength = (*i).length;
732:                 }
733:             }
737:             double departPos = 0;
738:             if (bestLength > BEST_LANE_LOOKAHEAD) {
739:                 departPos = getDepartPosBound(veh);
740:                 bestLength = MIN2(bestLength - departPos, BEST_LANE_LOOKAHEAD);
741:             }
742:             std::vector<MSLane*>* bestLanes = new std::vector<MSLane*>();
743:             for (std::vector<MSVehicle::LaneQ>::const_iterator i = bl.begin(); i != bl.end(); ++i) {
744:                 if (((*i).length - departPos) >= bestLength) {
745:                     if (isInternal()) {
746:                         for (MSLane* lane : *myLanes) {
747:                             if (lane->getNormalSuccessorLane() == (*i).lane && lane->allowsVehicleClass(veh.getVClass())) {
748:                                 bestLanes->push_back(lane);
749:                             }
750:                         }
751:                     } else if ((*i).lane->allowsVehicleClass(veh.getVClass())) {
752:                         bestLanes->push_back((*i).lane);
753:                     }
754:                 }
755:             }
756:             MSLane* ret = nullptr;
757:             if (veh.getParameter().departLaneProcedure == DepartLaneDefinition::BEST_FREE) {
758:                 ret = getFreeLane(bestLanes, veh.getVehicleType().getVehicleClass(), getDepartPosBound(veh, false));
759:             } else {
760:                 ret = getProbableLane(bestLanes, veh.getVehicleType().getVehicleClass(), getDepartPosBound(veh, false), getVehicleMaxSpeed(&veh));
761:             }
762:             delete bestLanes;
763:             return ret;
764:         }
765:         case DepartLaneDefinition::DEFAULT:
766:         case DepartLaneDefinition::FIRST_ALLOWED:
767:             return getFirstAllowed(veh.getVehicleType().getVehicleClass());
768:         default:
769:             break;
770:     }
771:     if (!(*myLanes)[0]->allowsVehicleClass(veh.getVehicleType().getVehicleClass())) {
772:         return nullptr;
773:     }
774:     return (*myLanes)[0];
775: }
778: MSLane*
779: MSEdge::getFirstAllowed(SUMOVehicleClass vClass, bool defaultFirst, int routingMode) const {
780:     for (std::vector<MSLane*>::const_iterator i = myLanes->begin(); i != myLanes->end(); ++i) {
781:         if ((*i)->allowsVehicleClass(vClass, routingMode)) {
782:             return *i;
783:         }
784:     }
785:     return defaultFirst && !myLanes->empty() ? myLanes->front() : nullptr;
786: }
789: bool
790: MSEdge::validateDepartSpeed(SUMOVehicle& v) const {
791:     const SUMOVehicleParameter& pars = v.getParameter();
792:     const MSVehicleType& type = v.getVehicleType();
793:     if (pars.departSpeedProcedure == DepartSpeedDefinition::GIVEN) {
795:         double vMax = getVehicleMaxSpeed(&v) + SPEED_EPS;
796:         if (pars.departSpeed > vMax) {
798:             MSLane* departLane = MSGlobals::gMesoNet ? getDepartLaneMeso(v) : getDepartLane(dynamic_cast<MSVehicle&>(v));
799:             if (departLane != nullptr) {
800:                 vMax = departLane->getVehicleMaxSpeed(&v);
801:                 if (pars.wasSet(VEHPARS_SPEEDFACTOR_SET)) {
803:                     vMax *= (1 + SPEED_EPS);
804:                 }
806:                 vMax += SPEED_EPS;
807:                 if (pars.departSpeed > vMax) {
808:                     if (type.getSpeedFactor().getParameter(1) > 0.) {
809:                         v.setChosenSpeedFactor(type.computeChosenSpeedDeviation(pars.speedFactor, nullptr, pars.departSpeed / MIN2(getSpeedLimit(), type.getDesiredMaxSpeed() - SPEED_EPS)));
810:                         if (v.getChosenSpeedFactor() > type.getSpeedFactor().getParameter(0) + 2 * type.getSpeedFactor().getParameter(1)) {
812:                             WRITE_WARNINGF(TL("Choosing new speed factor % for vehicle '%' to match departure speed % (max %)."),
813:                                            toString(v.getChosenSpeedFactor()), pars.id, pars.departSpeed, vMax);
814:                         }
815:                     } else {
816:                         return false;
817:                     }
818:                 }
819:             }
820:         }
821:     }
822:     return true;
823: }
826: bool
827: MSEdge::insertVehicle(SUMOVehicle& v, SUMOTime time, const bool checkOnly, const bool forceCheck) const {
829:     if (isVaporizing() || isTazConnector()
830:             || v.getRouteValidity(true, checkOnly) != MSBaseVehicle::ROUTE_VALID) {
831:         return checkOnly;
832:     }
833:     const SUMOVehicleParameter& pars = v.getParameter();
834:     if (!validateDepartSpeed(v)) {
835:         if (MSGlobals::gCheckRoutes) {
836:             throw ProcessError(TLF("Departure speed for vehicle '%' is too high for the departure edge '%', time=%.",
837:                                    pars.id, getID(), time2string(time)));
838:         } else {
839:             WRITE_WARNINGF(TL("Departure speed for vehicle '%' is too high for the departure edge '%', time=%."),
840:                            pars.id, getID(), time2string(time));
841:         }
842:     }
843:     if (MSGlobals::gUseMesoSim) {
844:         if (!forceCheck && myLastFailedInsertionTime == time) {
845:             return false;
846:         }
847:         double pos = 0.0;
848:         switch (pars.departPosProcedure) {
849:             case DepartPosDefinition::GIVEN:
850:                 if (pars.departPos >= 0.) {
851:                     pos = pars.departPos;
852:                 } else {
853:                     pos = pars.departPos + getLength();
854:                 }
855:                 if (pos < 0 || pos > getLength()) {
856:                     WRITE_WARNINGF(TL("Invalid departPos % given for vehicle '%', time=%. Inserting at lane end instead."),
857:                                    pos, v.getID(), time2string(time));
858:                     pos = getLength();
859:                 }
860:                 break;
861:             case DepartPosDefinition::RANDOM:
862:             case DepartPosDefinition::RANDOM_FREE:
863:                 pos = RandHelper::rand(getLength());
864:                 break;
865:             default:
866:                 break;
867:         }
868:         bool result = false;
869:         MESegment* segment = MSGlobals::gMesoNet->getSegmentForEdge(*this, pos);
870:         MEVehicle* veh = static_cast<MEVehicle*>(&v);
871:         int qIdx;
872:         if (pars.departPosProcedure == DepartPosDefinition::FREE) {
873:             while (segment != nullptr && !result) {
874:                 if (checkOnly) {
875:                     result = segment->hasSpaceFor(veh, time, qIdx, true) == time;
876:                 } else {
877:                     result = segment->initialise(veh, time);
878:                 }
879:                 segment = segment->getNextSegment();
880:             }
881:         } else {
882:             if (checkOnly) {
883:                 result = segment->hasSpaceFor(veh, time, qIdx, true) == time;
884:             } else {
885:                 result = segment->initialise(veh, time);
886:             }
887:         }
888:         return result;
889:     }
890:     if (checkOnly) {
891:         DepartLaneDefinition dld = v.getParameter().departLaneProcedure;
892:         if (dld == DepartLaneDefinition::DEFAULT) {
893:             dld = myDefaultDepartLaneDefinition;
894:         }
895:         switch (dld) {
896:             case DepartLaneDefinition::GIVEN:
897:             case DepartLaneDefinition::DEFAULT:
898:             case DepartLaneDefinition::FIRST_ALLOWED: {
899:                 MSLane* insertionLane = getDepartLane(static_cast<MSVehicle&>(v));
900:                 if (insertionLane == nullptr) {
901:                     WRITE_WARNINGF(TL("Could not insert vehicle '%' on any lane of edge '%', time=%."),
902:                                    v.getID(), getID(), time2string(time));
903:                     return false;
904:                 }
905:                 const double occupancy = insertionLane->getBruttoOccupancy();
906:                 return (occupancy == 0 || occupancy * myLength + v.getVehicleType().getLengthWithGap() <= myLength ||
907:                         v.getParameter().departProcedure == DepartDefinition::SPLIT);
908:             }
909:             default:
910:                 for (std::vector<MSLane*>::const_iterator i = myLanes->begin(); i != myLanes->end(); ++i) {
911:                     const double occupancy = (*i)->getBruttoOccupancy();
912:                     if (occupancy == 0 || occupancy * myLength + v.getVehicleType().getLengthWithGap() <= myLength ||
913:                             v.getParameter().departProcedure == DepartDefinition::SPLIT) {
914:                         return true;
915:                     }
916:                 }
917:         }
918:         return false;
919:     }
920:     MSLane* insertionLane = getDepartLane(static_cast<MSVehicle&>(v));
921:     if (insertionLane == nullptr) {
922:         return false;
923:     }
925:     if (!forceCheck) {
926:         if (myLastFailedInsertionTime == time) {
927:             if (myFailedInsertionMemory.count(insertionLane->getIndex())) {
929:                 return false;
930:             }
931:         } else {
933:             myFailedInsertionMemory.clear();
934:         }
935:     }
937:     bool success = insertionLane->insertVehicle(static_cast<MSVehicle&>(v));
939:     if (!success) {
941:         if (!insertionLane->hasParameter("insertionOrder" + v.getID())) {
942:             myFailedInsertionMemory.insert(insertionLane->getIndex());
943:         }
944:     }
945:     return success;
```

### B2. Demand scheduler — `microsim/MSInsertionControl.cpp:47-320`

```cpp
47: MSInsertionControl::MSInsertionControl(MSVehicleControl& vc,
48:                                        SUMOTime maxDepartDelay,
49:                                        bool eagerInsertionCheck,
50:                                        int maxVehicleNumber,
51:                                        SUMOTime randomDepartOffset) :
52:     myVehicleControl(vc),
53:     myMaxDepartDelay(maxDepartDelay),
54:     myEagerInsertionCheck(eagerInsertionCheck),
55:     myMaxVehicleNumber(maxVehicleNumber),
56:     myPendingEmitsUpdateTime(SUMOTime_MIN),
57:     myFlowRNG("flow") {
58:     myMaxRandomDepartOffset = randomDepartOffset;
59:     RandHelper::initRandGlobal(&myFlowRNG);
60: }
63: MSInsertionControl::~MSInsertionControl() {
64:     for (const Flow& f : myFlows) {
65:         delete (f.pars);
66:     }
67: }
70: void
71: MSInsertionControl::add(SUMOVehicle* veh) {
72:     myAllVeh.add(veh);
73: }
76: bool
77: MSInsertionControl::addFlow(SUMOVehicleParameter* const pars, int index) {
78:     if (myFlowIDs.count(pars->id) > 0) {
79:         return false;
80:     }
81:     const bool loadingFromState = index >= 0;
82:     Flow flow{pars, loadingFromState ? index : 0, initScale(pars->vtypeid)};
83:     if (!loadingFromState && pars->repetitionProbability < 0 && pars->repetitionOffset < 0) {
85:         flow.pars->incrementFlow(flow.scale, &myFlowRNG);
86:         flow.pars->repetitionsDone--;
87:     }
88:     myFlows.emplace_back(flow);
89:     myFlowIDs.insert(std::make_pair(pars->id, flow.index));
90:     return true;
91: }
94: double
95: MSInsertionControl::initScale(const std::string vtypeid) {
96:     MSVehicleControl& vc = MSNet::getInstance()->getVehicleControl();
97:     if (vc.hasVTypeDistribution(vtypeid)) {
98:         double result = -1;
99:         const RandomDistributor<MSVehicleType*>* dist = vc.getVTypeDistribution(vtypeid);
100:         for (const MSVehicleType* t : dist->getVals()) {
101:             if (result == -1) {
102:                 result = t->getParameter().scale;
103:             } else if (result != t->getParameter().scale) {
105:                 return -1;
106:             }
107:         }
108:         return result;
109:     } else {
111:         return vc.getVType(vtypeid, nullptr, true)->getParameter().scale;
112:     }
113: }
116: void
117: MSInsertionControl::updateScale(const std::string vtypeid) {
118:     for (Flow& f : myFlows) {
119:         if (f.pars->vtypeid == vtypeid) {
120:             f.scale = initScale(vtypeid);
121:         }
122:     }
123: }
126: int
127: MSInsertionControl::emitVehicles(SUMOTime time) {
129:     const bool havePreChecked = MSRoutingEngine::isEnabled();
130:     if (myPendingEmits.empty() || (havePreChecked && myEmitCandidates.empty())) {
131:         return 0;
132:     }
133:     int numEmitted = 0;
138:     MSVehicleContainer::VehicleVector refusedEmits;
141:     MSNet::getInstance()->lockPendingEmits();
142:     MSVehicleContainer::VehicleVector::const_iterator veh;
143:     for (veh = myPendingEmits.begin(); veh != myPendingEmits.end(); veh++) {
144:         if (havePreChecked && (myEmitCandidates.count(*veh) == 0)) {
145:             refusedEmits.push_back(*veh);
146:         } else {
147:             numEmitted += tryInsert(time, *veh, refusedEmits);
148:         }
149:     }
150:     myEmitCandidates.clear();
151:     myPendingEmits = refusedEmits;
152:     MSNet::getInstance()->unlockPendingEmits();
153:     return numEmitted;
154: }
157: int
158: MSInsertionControl::tryInsert(SUMOTime time, SUMOVehicle* veh,
159:                               MSVehicleContainer::VehicleVector& refusedEmits) {
160:     assert(veh->getParameter().depart <= time);
161:     const MSEdge& edge = *veh->getEdge();
162:     if (veh->isOnRoad()) {
163:         return 1;
164:     }
165:     if ((myMaxVehicleNumber < 0 || (int)MSNet::getInstance()->getVehicleControl().getRunningVehicleNo() < myMaxVehicleNumber)
166:             && edge.insertVehicle(*veh, time, false, myEagerInsertionCheck || veh->getParameter().departProcedure == DepartDefinition::SPLIT)) {
168:         return 1;
169:     }
170:     if (myMaxDepartDelay >= 0 && time - veh->getParameter().depart > myMaxDepartDelay) {
172:         myVehicleControl.deleteVehicle(veh, true);
173:     } else if (edge.isVaporizing()) {
175:         myVehicleControl.deleteVehicle(veh, true);
176:     } else if (myAbortedEmits.count(veh) > 0) {
178:         myAbortedEmits.erase(veh);
179:         myVehicleControl.deleteVehicle(veh, true);
180:     } else if ((veh->getRouteValidity(false) & (
181:                     MSBaseVehicle::ROUTE_START_INVALID_LANE
182:                     | MSBaseVehicle::ROUTE_START_INVALID_PERMISSIONS)) != 0) {
183:         myVehicleControl.deleteVehicle(veh, true);
184:     } else {
186:         refusedEmits.push_back(veh);
187:     }
188:     edge.setLastFailedInsertionTime(time);
189:     return 0;
190: }
193: void
194: MSInsertionControl::checkCandidates(SUMOTime time, const bool preCheck) {
195:     if (myMaxDepartDelay >= 0) {
196:         for (auto it = myPendingEmits.begin(); it != myPendingEmits.end();) {
197:             SUMOVehicle* veh = *it;
198:             if (time - veh->getParameter().depart > myMaxDepartDelay) {
200:                 myVehicleControl.deleteVehicle(veh, true);
201:                 it = myPendingEmits.erase(it);
202:             } else {
203:                 it++;
204:             }
205:         }
206:     }
207:     while (myAllVeh.anyWaitingBefore(time)) {
208:         const MSVehicleContainer::VehicleVector& top = myAllVeh.top();
209:         copy(top.begin(), top.end(), back_inserter(myPendingEmits));
210:         myAllVeh.pop();
211:     }
212:     if (preCheck) {
213:         MSVehicleContainer::VehicleVector::const_iterator veh;
214:         for (veh = myPendingEmits.begin(); veh != myPendingEmits.end(); veh++) {
215:             SUMOVehicle* const v = *veh;
216:             const MSEdge* const edge = v->getEdge();
217:             if (edge->insertVehicle(*v, time, true, myEagerInsertionCheck)) {
218:                 myEmitCandidates.insert(v);
219:             } else {
220:                 MSDevice_Routing* dev = static_cast<MSDevice_Routing*>(v->getDevice(typeid(MSDevice_Routing)));
221:                 if (dev != nullptr) {
222:                     dev->skipRouting(time);
223:                 }
224:             }
225:         }
226:     }
227: }
230: void
231: MSInsertionControl::determineCandidates(SUMOTime time) {
232:     MSVehicleControl& vehControl = MSNet::getInstance()->getVehicleControl();
234:     for (std::vector<Flow>::iterator i = myFlows.begin(); i != myFlows.end();) {
235:         MSVehicleType* vtype = nullptr;
236:         SUMOVehicleParameter* const pars = i->pars;
237:         double typeScale = i->scale;
238:         if (typeScale < 0) {
240:             vtype = vehControl.getVType(pars->vtypeid, MSRouteHandler::getParsingRNG());
241:             typeScale = vtype->getParameter().scale;
242:         }
243:         const double scale = vehControl.getScale() * typeScale;
244:         const long long int scaledRepetitions = pars->repetitionNumber == std::numeric_limits<long long int>::max() ? std::numeric_limits<long long int>::max() :
245:                                                 (long long int)((double)pars->repetitionNumber * scale + 0.5);
246:         bool tryEmitByProb = pars->repetitionProbability > 0;
247:         while (scale > 0 && ((pars->repetitionProbability < 0
248:                               && pars->repetitionsDone < scaledRepetitions
249:                               && pars->depart + pars->repetitionTotalOffset <= time)
250:                              || (tryEmitByProb
251:                                  && pars->depart <= time
252:                                  && pars->repetitionEnd > time
254:                                  && RandHelper::rand(&myFlowRNG) < (pars->repetitionProbability * TS))
255:                             )) {
256:             tryEmitByProb = false; // only emit one per step
257:             SUMOVehicleParameter* const newPars = new SUMOVehicleParameter(*pars);
258:             newPars->id = pars->id + "." + toString(i->index);
259:             newPars->depart = pars->repetitionProbability > 0 ? time : pars->depart + pars->repetitionTotalOffset + computeRandomDepartOffset();
260:             pars->incrementFlow(scale, &myFlowRNG);
261:             myFlowIDs[pars->id] = i->index;
264:             if (vehControl.getVehicle(newPars->id) == nullptr) {
265:                 ConstMSRoutePtr const route = MSRoute::dictionary(pars->routeid);
266:                 if (vtype == nullptr) {
267:                     vtype = vehControl.getVType(pars->vtypeid, MSRouteHandler::getParsingRNG());
268:                 }
269:                 SUMOVehicle* const vehicle = vehControl.buildVehicle(newPars, route, vtype, !MSGlobals::gCheckRoutes);
272:                 int quota = pars->repetitionProbability < 0 ? 1 : vehControl.getQuota(scale);
273:                 if (quota > 0) {
274:                     vehControl.addVehicle(newPars->id, vehicle);
275:                     if (pars->departProcedure == DepartDefinition::GIVEN || pars->departProcedure == DepartDefinition::BEGIN) {
276:                         add(vehicle);
277:                     }
278:                     i->index++;
279:                     while (--quota > 0) {
280:                         SUMOVehicleParameter* const quotaPars = new SUMOVehicleParameter(*pars);
281:                         quotaPars->id = pars->id + "." + toString(i->index);
282:                         quotaPars->depart = pars->repetitionProbability > 0 ? time :
283:                                             pars->depart + pars->repetitionsDone * pars->repetitionTotalOffset + computeRandomDepartOffset();
284:                         SUMOVehicle* const quotaVehicle = vehControl.buildVehicle(quotaPars, route, vtype, !MSGlobals::gCheckRoutes);
285:                         vehControl.addVehicle(quotaPars->id, quotaVehicle);
286:                         if (pars->departProcedure == DepartDefinition::GIVEN || pars->departProcedure == DepartDefinition::BEGIN) {
287:                             add(quotaVehicle);
288:                         }
289:                         pars->repetitionsDone++;
290:                         i->index++;
291:                     }
292:                 } else {
293:                     vehControl.deleteVehicle(vehicle, true);
294:                 }
295:             } else {
296:                 if (MSGlobals::gStateLoaded) {
298:                     break;
299:                 }
300:                 throw ProcessError(TLF("Another vehicle with the id '%' exists.", newPars->id));
301:             }
302:             vtype = nullptr;
303:         }
304:         if (time >= pars->repetitionEnd || pars->repetitionsDone >= scaledRepetitions) {
305:             i = myFlows.erase(i);
306:             MSRoute::checkDist(pars->routeid);
307:             delete pars;
308:         } else {
309:             ++i;
310:         }
311:     }
312:     checkCandidates(time, MSRoutingEngine::isEnabled());
313: }
316: int
317: MSInsertionControl::getWaitingVehicleNo() const {
318:     return (int)myPendingEmits.size();
319: }
```

### B3. Departure procedure parsing — `utils/vehicle/SUMOVehicleParameter.cpp:397-559`

```cpp
397:                 error = "Invalid " + attr + " time for " + element + ". Must be one of (\"triggered\", \"containerTriggered\", \"now\", or a float >= 0)";
398:             } else {
399:                 error = "Invalid " + attr + " time for " + element + " '" + id + "';\n must be one of (\"triggered\", \"containerTriggered\", \"now\", or a float >= 0)";
400:             }
401:             return false;
402:         }
403:     }
404:     return true;
405: }
408: bool
409: SUMOVehicleParameter::parseDepartLane(const std::string& val, const std::string& element, const std::string& id,
410:                                       int& lane, DepartLaneDefinition& dld, std::string& error) {
411:     bool ok = true;
412:     lane = 0;
413:     dld = DepartLaneDefinition::GIVEN;
414:     if (val == "random") {
415:         dld = DepartLaneDefinition::RANDOM;
416:     } else if (val == "free") {
417:         dld = DepartLaneDefinition::FREE;
418:     } else if (val == "allowed") {
419:         dld = DepartLaneDefinition::ALLOWED_FREE;
420:     } else if (val == "best") {
421:         dld = DepartLaneDefinition::BEST_FREE;
422:     } else if (val == "best_prob") {
423:         dld = DepartLaneDefinition::BEST_PROB;
424:     } else if (val == "first") {
425:         dld = DepartLaneDefinition::FIRST_ALLOWED;
426:     } else {
427:         try {
428:             lane = StringUtils::toInt(val);
429:             if (lane < 0) {
430:                 ok = false;
431:             }
432:         } catch (...) {
433:             ok = false;
434:         }
435:     }
436:     if (!ok) {
437:         if (id.empty()) {
438:             error = "Invalid departLane definition for " + element + ". Must be one of (\"random\", \"free\", \"allowed\", \"best\", \"best_prob\", \"first\", or an int>=0)";
439:         } else {
440:             error = "Invalid departLane definition for " + element + " '" + id + "';\n must be one of (\"random\", \"free\", \"allowed\", \"best\", \"best_prob\", \"first\", or an int>=0)";
441:         }
442:     }
443:     return ok;
444: }
447: bool
448: SUMOVehicleParameter::parseDepartPos(const std::string& val, const std::string& element, const std::string& id,
449:                                      double& pos, DepartPosDefinition& dpd, std::string& error) {
450:     bool ok = true;
451:     pos = 0.;
452:     dpd = DepartPosDefinition::GIVEN;
453:     if (val == "random") {
454:         dpd = DepartPosDefinition::RANDOM;
455:     } else if (val == "random_free") {
456:         dpd = DepartPosDefinition::RANDOM_FREE;
457:     } else if (val == "random_location") {
458:         dpd = DepartPosDefinition::RANDOM_LOCATION;
459:     } else if (val == "free") {
460:         dpd = DepartPosDefinition::FREE;
461:     } else if (val == "base") {
462:         dpd = DepartPosDefinition::BASE;
463:     } else if (val == "last") {
464:         dpd = DepartPosDefinition::LAST;
465:     } else if (val == "splitFront") {
466:         dpd = DepartPosDefinition::SPLIT_FRONT;
467:     } else if (val == "stop") {
468:         dpd = DepartPosDefinition::STOP;
469:     } else {
470:         try {
471:             pos = StringUtils::toDouble(val);
472:         } catch (...) {
473:             ok = false;
474:         }
475:     }
476:     if (!ok) {
477:         if (id.empty()) {
478:             error = "Invalid departPos definition for " + element + ". Must be one of (\"random\", \"random_free\", \"free\", \"base\", \"last\" or a float)";
479:         } else {
480:             error = "Invalid departPos definition for " + element + " '" + id + "';\n must be one of (\"random\", \"random_free\", \"free\", \"base\", \"last\" or a float)";
481:         }
482:     }
483:     return ok;
484: }
487: bool
488: SUMOVehicleParameter::parseDepartPosLat(const std::string& val, const std::string& element, const std::string& id,
489:                                         double& pos, DepartPosLatDefinition& dpd, std::string& error) {
490:     bool ok = true;
491:     pos = 0.;
492:     dpd = DepartPosLatDefinition::GIVEN;
493:     if (val == "random") {
494:         dpd = DepartPosLatDefinition::RANDOM;
495:     } else if (val == "random_free") {
496:         dpd = DepartPosLatDefinition::RANDOM_FREE;
497:     } else if (val == "free") {
498:         dpd = DepartPosLatDefinition::FREE;
499:     } else if (val == "right") {
500:         dpd = DepartPosLatDefinition::RIGHT;
501:     } else if (val == "center") {
502:         dpd = DepartPosLatDefinition::CENTER;
503:     } else if (val == "left") {
504:         dpd = DepartPosLatDefinition::LEFT;
505:     } else {
506:         try {
507:             pos = StringUtils::toDouble(val);
508:         } catch (...) {
509:             ok = false;
510:         }
511:     }
512:     if (!ok) {
513:         if (id.empty()) {
514:             error = "Invalid departPosLat definition for " + element + ". Must be one of (\"random\", \"random_free\", \"free\", \"right\", \"center\", \"left\", or a float)";
515:         } else {
516:             error = "Invalid departPosLat definition for " + element + " '" + id + "';\n must be one of (\"random\", \"random_free\", \"free\", \"right\", \"center\", \"left\", or a float)";
517:         }
518:     }
519:     return ok;
520: }
523: bool
524: SUMOVehicleParameter::parseDepartSpeed(const std::string& val, const std::string& element, const std::string& id,
525:                                        double& speed, DepartSpeedDefinition& dsd, std::string& error) {
526:     bool ok = true;
527:     speed = -1.;
528:     dsd = DepartSpeedDefinition::GIVEN;
529:     if (val == "random") {
530:         dsd = DepartSpeedDefinition::RANDOM;
531:     } else if (val == "max") {
532:         dsd = DepartSpeedDefinition::MAX;
533:     } else if (val == "desired") {
534:         dsd = DepartSpeedDefinition::DESIRED;
535:     } else if (val == "speedLimit") {
536:         dsd = DepartSpeedDefinition::LIMIT;
537:     } else if (val == "last") {
538:         dsd = DepartSpeedDefinition::LAST;
539:     } else if (val == "avg") {
540:         dsd = DepartSpeedDefinition::AVG;
541:     } else {
542:         try {
543:             speed = StringUtils::toDouble(val);
544:             if (speed < 0) {
545:                 ok = false;
546:             }
547:         } catch (...) {
548:             ok = false;
549:         }
550:     }
551:     if (!ok) {
552:         if (id.empty()) {
553:             error = "Invalid departSpeed '" + val + "' definition for " + element + ". Must be one of (\"random\", \"max\", or a float>=0)";
554:         } else {
555:             error = "Invalid departSpeed definition '" + val + "' for " + element + " '" + id + "';\n must be one of (\"random\", \"max\", or a float>=0)";
556:         }
557:     }
558:     return ok;
559: }
```

### C1. Tripinfo callbacks and writer — `microsim/devices/MSDevice_Tripinfo.cpp:169-377`

```cpp
169: MSDevice_Tripinfo::notifyIdle(SUMOTrafficObject& veh) {
170:     if (veh.isVehicle()) {
171:         myWaitingTime += DELTA_T;
172:         if (!myAmWaiting) {
173:             myWaitingCount++;
174:             myAmWaiting = true;
175:         }
176:     }
177:     return true;
178: }
181: bool
182: MSDevice_Tripinfo::notifyMove(SUMOTrafficObject& veh, double /*oldPos*/,
183:                               double /*newPos*/, double newSpeed) {
184:     if (veh.isStopped()) {
185:         if (newSpeed <= SUMO_const_haltingSpeed) {
186:             myStoppingTime += DELTA_T;
187:         }
188:     } else if (newSpeed <= SUMO_const_haltingSpeed && lowAcceleration(veh)) {
189:         myWaitingTime += DELTA_T;
190:         if (!myAmWaiting) {
191:             myWaitingCount++;
192:             myAmWaiting = true;
193:         }
194:     } else {
195:         myAmWaiting = false;
196:     }
197:     return true;
198: }
201: bool
202: MSDevice_Tripinfo::lowAcceleration(const SUMOTrafficObject& veh) {
203:     if (MSGlobals::gUseMesoSim) {
205:         return false;
206:     } else {
207:         const MSVehicle& v = dynamic_cast<const MSVehicle&>(veh);
208:         return v.getAcceleration() <= v.accelThresholdForWaiting();
209:     }
210: }
213: void
214: MSDevice_Tripinfo::notifyMoveInternal(const SUMOTrafficObject& veh,
215:                                       const double /* frontOnLane */,
216:                                       const double timeOnLane,
217:                                       const double /* meanSpeedFrontOnLane */,
218:                                       const double meanSpeedVehicleOnLane,
219:                                       const double /* travelledDistanceFrontOnLane */,
220:                                       const double /* travelledDistanceVehicleOnLane */,
221:                                       const double /* meanLengthOnLane */) {
224:     const double vmax = veh.getEdge()->getVehicleMaxSpeed(&veh);
225:     if (vmax > 0) {
226:         myMesoTimeLoss += TIME2STEPS(timeOnLane * (vmax - meanSpeedVehicleOnLane) / vmax);
227:     }
228:     myWaitingTime += veh.getWaitingTime();
229:     if (veh.getWaitingTime() >= TIME2STEPS(1)) {
231:         myWaitingCount++;
232:     }
233: }
236: void
237: MSDevice_Tripinfo::recordMesoParkingTimeLoss(SUMOTime waitingTime) {
238:     myMesoTimeLoss += waitingTime;
239:     myWaitingTime += waitingTime;
240:     myWaitingCount++;
241: }
243: void
244: MSDevice_Tripinfo::updateParkingStopTime() {
245:     if (myParkingStarted >= 0) {
246:         myStoppingTime += (MSNet::getInstance()->getCurrentTimeStep() - myParkingStarted);
247:         myParkingStarted = -1;
248:     }
249: }
251: bool
252: MSDevice_Tripinfo::notifyEnter(SUMOTrafficObject& veh, MSMoveReminder::Notification reason, const MSLane* /* enteredLane */) {
253:     if (reason == MSMoveReminder::NOTIFICATION_DEPARTED) {
254:         if (!MSGlobals::gUseMesoSim) {
255:             myDepartLane = static_cast<MSVehicle&>(veh).getLane()->getID();
256:             myDepartPosLat = static_cast<MSVehicle&>(veh).getLateralPositionOnLane();
257:         } else {
258:             myDepartLane = veh.getEdge()->getFirstAllowed(veh.getVClass(), true)->getID();
259:         }
260:         myDepartSpeed = veh.getSpeed();
261:         myRouteLength = -veh.getPositionOnLane();
262:     } else if (reason == MSMoveReminder::NOTIFICATION_PARKING) {
265:         updateParkingStopTime();
266:     }
267:     return true;
268: }
271: bool
272: MSDevice_Tripinfo::notifyLeave(SUMOTrafficObject& veh, double /*lastPos*/,
273:                                MSMoveReminder::Notification reason, const MSLane* /* enteredLane */) {
274:     if (reason >= MSMoveReminder::NOTIFICATION_ARRIVED) {
275:         myArrivalTime = MSNet::getInstance()->getCurrentTimeStep();
276:         myArrivalReason = reason;
277:         if (!MSGlobals::gUseMesoSim) {
278:             myArrivalLane = static_cast<MSVehicle&>(veh).getLane()->getID();
279:             myArrivalPosLat = static_cast<MSVehicle&>(veh).getLateralPositionOnLane();
280:         } else {
281:             myArrivalLane = veh.getEdge()->getFirstAllowed(veh.getVClass(), true)->getID();
282:         }
286:         if (reason > MSMoveReminder::NOTIFICATION_TELEPORT_ARRIVED) {
288:             myArrivalPos = veh.getPositionOnLane();
289:         } else {
290:             myArrivalPos = myHolder.getArrivalPos();
291:         }
292:         myArrivalSpeed = veh.getSpeed();
293:         updateParkingStopTime();
294:     } else if (reason == MSMoveReminder::NOTIFICATION_PARKING) {
295:         myParkingStarted = MSNet::getInstance()->getCurrentTimeStep();
296:     } else if (reason == NOTIFICATION_JUNCTION
297:                || reason == NOTIFICATION_TELEPORT
298:                || reason == NOTIFICATION_TELEPORT_CONTINUATION) {
299:         if (MSGlobals::gUseMesoSim) {
300:             myRouteLength += myHolder.getCurrentEdge()->getLength();
301:         } else {
302:             const MSLane* lane = static_cast<MSVehicle&>(veh).getLane();
303:             if (lane != nullptr) {
304:                 myRouteLength += lane->getLength();
305:             }
306:         }
307:     }
308:     return true;
309: }
312: void
313: MSDevice_Tripinfo::generateOutput(OutputDevice* tripinfoOut) const {
314:     const SUMOTime timeLoss = MSGlobals::gUseMesoSim ? myMesoTimeLoss : static_cast<MSVehicle&>(myHolder).getTimeLoss();
315:     const double routeLength = myRouteLength + (myArrivalTime == NOT_ARRIVED ? myHolder.getPositionOnLane() : myArrivalPos);
316:     SUMOTime duration = 0;
317:     if (myHolder.hasDeparted()) {
318:         duration = (myArrivalTime == NOT_ARRIVED ? SIMSTEP : myArrivalTime) - myHolder.getDeparture();
319:         const SUMOTime drivingDuration = duration - myStoppingTime;
320:         const double speed = drivingDuration > 0 ? routeLength / STEPS2TIME(drivingDuration) : 0;
321:         if (myHolder.getVClass() == SVC_BICYCLE) {
322:             myBikeCount++;
323:             myTotalBikeRouteLength += routeLength;
324:             myTotalBikeSpeed += speed;
325:             myTotalBikeDuration += duration;
326:             myTotalBikeWaitingTime += myWaitingTime;
327:             myTotalBikeTimeLoss += timeLoss;
328:             myTotalBikeDepartDelay += myHolder.getDepartDelay();
329:         } else {
330:             myVehicleCount++;
331:             myTotalRouteLength += routeLength;
332:             myTotalSpeed += speed;
333:             myTotalDuration += duration;
334:             myTotalWaitingTime += myWaitingTime;
335:             myTotalTimeLoss += timeLoss;
336:             myTotalDepartDelay += myHolder.getDepartDelay();
337:         }
338:     }
340:     myPendingOutput.erase(this);
341:     if (tripinfoOut == nullptr) {
342:         return;
343:     }
345:     OutputDevice& os = *tripinfoOut;
346:     os.openTag("tripinfo").writeAttr("id", myHolder.getID());
347:     os.writeAttr("depart", myHolder.hasDeparted() ? time2string(myHolder.getDeparture()) : "-1");
348:     os.writeAttr("departLane", myDepartLane);
349:     os.writeAttr("departPos", myHolder.getDepartPos());
350:     if (MSGlobals::gLateralResolution > 0) {
351:         os.writeAttr("departPosLat", myDepartPosLat);
352:     }
353:     os.writeAttr("departSpeed", myDepartSpeed);
354:     SUMOTime departDelay = myHolder.getDepartDelay();
355:     const SUMOVehicleParameter& param = myHolder.getParameter();
356:     if (!myHolder.hasDeparted()) {
357:         assert(param.depart <= SIMSTEP || param.departProcedure != DepartDefinition::GIVEN);
358:         departDelay = SIMSTEP - param.depart;
359:     }
360:     os.writeAttr("departDelay", time2string(departDelay));
361:     os.writeAttr("arrival", time2string(myArrivalTime));
362:     os.writeAttr("arrivalLane", myArrivalLane);
363:     os.writeAttr("arrivalPos", myArrivalPos);
364:     if (MSGlobals::gLateralResolution > 0) {
365:         os.writeAttr("arrivalPosLat", myArrivalPosLat);
366:     }
367:     os.writeAttr("arrivalSpeed", myArrivalSpeed);
368:     os.writeAttr("duration", time2string(duration));
369:     os.writeAttr("routeLength", routeLength);
370:     os.writeAttr(SUMO_ATTR_WAITINGTIME, time2string(myWaitingTime));
371:     os.writeAttr(SUMO_ATTR_WAITINGCOUNT, myWaitingCount);
372:     os.writeAttr(SUMO_ATTR_STOPTIME, time2string(myStoppingTime));
373:     os.writeAttr(SUMO_ATTR_TIMELOSS, time2string(timeLoss));
374:     os.writeAttr("rerouteNo", myHolder.getNumberReroutes());
375:     os.writeAttr("devices", toString(myHolder.getDevices()));
376:     os.writeAttr("vType", myHolder.getVehicleType().getID());
377:     os.writeAttr("speedFactor", myHolder.getChosenSpeedFactor());
```

### C1. Vehicle time loss — `microsim/MSVehicle.cpp:4308-4317`

```cpp
4308: MSVehicle::updateTimeLoss(double vNext) {
4310:     if (!isStopped()) {
4312:         const double vmax = MIN2(myLane->getVehicleMaxSpeed(this), MAX2(myStopSpeed, vNext));
4313:         if (vmax > 0) {
4314:             myTimeLoss += TS * (vmax - vNext) / vmax;
4315:         }
4316:     }
4317: }
```

### C2. Summary writer — `microsim/MSNet.cpp:696-744`

```cpp
696: MSNet::writeSummaryOutput(bool finalStep) {
698:     const OptionsCont& oc = OptionsCont::getOptions();
699:     const bool hasOutput = oc.isSet("summary-output");
700:     const bool hasPersonOutput = oc.isSet("person-summary-output");
701:     if (hasOutput || hasPersonOutput) {
702:         const SUMOTime period = string2time(oc.getString("summary-output.period"));
703:         const SUMOTime begin = string2time(oc.getString("begin"));
704:         if ((period > 0 && (myStep - begin) % period != 0 && !finalStep)
706:                 || (finalStep && (period <= 0 || (myStep - begin) % period == 0))) {
707:             return;
708:         }
709:     }
710:     if (hasOutput) {
711:         OutputDevice& od = OutputDevice::getDeviceByOption("summary-output");
712:         int departedVehiclesNumber = myVehicleControl->getDepartedVehicleNo();
713:         const double meanWaitingTime = departedVehiclesNumber != 0 ? myVehicleControl->getTotalDepartureDelay() / (double) departedVehiclesNumber : -1.;
714:         int endedVehicleNumber = myVehicleControl->getEndedVehicleNo();
715:         const double meanTravelTime = endedVehicleNumber != 0 ? myVehicleControl->getTotalTravelTime() / (double) endedVehicleNumber : -1.;
716:         od.openTag("step");
717:         od.writeAttr("time", time2string(myStep));
718:         od.writeAttr("loaded", myVehicleControl->getLoadedVehicleNo());
719:         od.writeAttr("inserted", myVehicleControl->getDepartedVehicleNo());
720:         od.writeAttr("running", myVehicleControl->getRunningVehicleNo());
721:         od.writeAttr("waiting", myInserter->getWaitingVehicleNo());
722:         od.writeAttr("ended", myVehicleControl->getEndedVehicleNo());
723:         od.writeAttr("arrived", myVehicleControl->getArrivedVehicleNo());
724:         od.writeAttr("collisions", myVehicleControl->getCollisionCount());
725:         od.writeAttr("teleports", myVehicleControl->getTeleportCount());
726:         od.writeAttr("halting", myVehicleControl->getHaltingVehicleNo());
727:         od.writeAttr("stopped", myVehicleControl->getStoppedVehiclesCount());
728:         od.writeAttr("meanWaitingTime", meanWaitingTime);
729:         od.writeAttr("meanTravelTime", meanTravelTime);
730:         std::pair<double, double> meanSpeed = myVehicleControl->getVehicleMeanSpeeds();
731:         od.writeAttr("meanSpeed", meanSpeed.first);
732:         od.writeAttr("meanSpeedRelative", meanSpeed.second);
733:         od.writeAttr("discarded", myVehicleControl->getDiscardedVehicleNo());
734:         if (myLogExecutionTime) {
735:             od.writeAttr("duration", mySimStepDuration);
736:         }
737:         od.closeTag();
738:     }
739:     if (hasPersonOutput) {
740:         OutputDevice& od = OutputDevice::getDeviceByOption("person-summary-output");
741:         MSTransportableControl& pc = getPersonControl();
742:         od.openTag("step");
743:         od.writeAttr("time", time2string(myStep));
744:         od.writeAttr("loaded", pc.getLoadedNumber());
```

### C2. Counter updates — `microsim/MSVehicleControl.cpp:136-228`

```cpp
136: MSVehicleControl::scheduleVehicleRemoval(SUMOVehicle* veh, bool checkDuplicate) {
137:     assert(myRunningVehNo > 0);
138:     if (!checkDuplicate || !isPendingRemoval(veh)) {
139:         myPendingRemovals.push_back(veh);
140:     }
141: }
144: bool
145: MSVehicleControl::isPendingRemoval(SUMOVehicle* veh) {
146: #ifdef HAVE_FOX
147:     return myPendingRemovals.contains(veh);
148: #else
149:     return std::find(myPendingRemovals.begin(), myPendingRemovals.end(), veh) == myPendingRemovals.end();
150: #endif
151: }
154: void
155: MSVehicleControl::removePending() {
156:     OutputDevice* const tripinfoOut = OptionsCont::getOptions().isSet("tripinfo-output") ? &OutputDevice::getDeviceByOption("tripinfo-output") : nullptr;
157: #ifdef HAVE_FOX
158:     std::vector<SUMOVehicle*>& vehs = myPendingRemovals.getContainer();
159: #else
160:     std::vector<SUMOVehicle*>& vehs = myPendingRemovals;
161: #endif
162:     std::sort(vehs.begin(), vehs.end(), ComparatorNumericalIdLess());
163:     for (SUMOVehicle* const veh : vehs) {
164:         myTotalTravelTime += STEPS2TIME(MSNet::getInstance()->getCurrentTimeStep() - veh->getDeparture());
165:         myRunningVehNo--;
166:         MSNet::getInstance()->informVehicleStateListener(veh, MSNet::VehicleState::ARRIVED);
168:         const bool hasTripinfo = veh->getDevice(typeid(MSDevice_Tripinfo)) != nullptr;
169:         for (MSVehicleDevice* const dev : veh->getDevices()) {
170:             dev->generateOutput(hasTripinfo ? tripinfoOut : nullptr);
171:         }
172:         if (tripinfoOut != nullptr && hasTripinfo) {
174:             tripinfoOut->closeTag();
175:         }
176:         if (myKeepTime == 0) {
177:             deleteVehicle(veh);
178:         } else {
179:             deleteKeptVehicle(veh);
180:         }
181:     }
182:     vehs.clear();
183:     if (tripinfoOut != nullptr) {
185:         tripinfoOut->flush();
186:     }
187: #ifdef HAVE_FOX
188:     myPendingRemovals.unlock();
189: #endif
190: }
193: void
194: MSVehicleControl::deleteKeptVehicle(SUMOVehicle* veh) {
195:     myEndedVehNo++;
196:     MSNet::getInstance()->getEndOfTimestepEvents()->addEvent(new DeleteKeptVehicle(veh), SIMSTEP + myKeepTime);
197: }
199: void
200: MSVehicleControl::vehicleDeparted(const SUMOVehicle& v) {
201:     ++myRunningVehNo;
202:     myTotalDepartureDelay += STEPS2TIME(v.getDeparture() - STEPFLOOR(v.getParameter().depart));
203:     MSNet::getInstance()->informVehicleStateListener(&v, MSNet::VehicleState::DEPARTED);
204:     myMaxSpeedFactor = MAX2(myMaxSpeedFactor, v.getChosenSpeedFactor());
205:     myMaxMinGap = MAX2(myMaxMinGap, v.getVehicleType().getMinGap());
206:     const double maxDecel = v.getVehicleType().getCarFollowModel().getMaxDecel();
207:     if ((v.getVClass() & (SVC_PEDESTRIAN | SVC_NON_ROAD)) == 0) {
209:         myMinDeceleration = MIN2(myMinDeceleration, maxDecel);
210:     } else if ((v.getVClass() & SVC_RAIL_CLASSES) != 0) {
211:         myMinDecelerationRail = MIN2(myMinDecelerationRail, maxDecel);
212:         if ((v.getEdge()->getPermissions() & SVC_ROAD_MOTOR_CLASSES) != 0) {
214:             myMinDeceleration = MIN2(myMinDeceleration, maxDecel);
215:         }
216:     }
217: }
220: void
221: MSVehicleControl::setState(int runningVehNo, int loadedVehNo, int endedVehNo, double totalDepartureDelay, double totalTravelTime, double maxSpeedFactor, double minDecel) {
222:     myRunningVehNo = runningVehNo;
223:     myLoadedVehNo = loadedVehNo;
224:     myEndedVehNo = endedVehNo;
225:     myTotalDepartureDelay = totalDepartureDelay;
226:     myTotalTravelTime = totalTravelTime;
227:     myMaxSpeedFactor = maxSpeedFactor;
228:     myMinDeceleration = minDecel;
```

### C2. Instantaneous means — `microsim/MSVehicleControl.cpp:550-585`

```cpp
550: MSVehicleControl::getHaltingVehicleNo() const {
551:     int result = 0;
552:     for (MSVehicleControl::constVehIt it = loadedVehBegin(); it != loadedVehEnd(); ++it) {
553:         const SUMOVehicle* veh = it->second;
554:         if ((veh->isOnRoad() || veh->isRemoteControlled()) && veh->getSpeed() < SUMO_const_haltingSpeed)  {
555:             result++;
556:         }
557:     }
558:     return result;
559: }
562: std::pair<double, double>
563: MSVehicleControl::getVehicleMeanSpeeds() const {
564:     double speedSum = 0;
565:     double relSpeedSum = 0;
566:     int count = 0;
567:     for (MSVehicleControl::constVehIt it = loadedVehBegin(); it != loadedVehEnd(); ++it) {
568:         const SUMOVehicle* veh = it->second;
569:         if ((veh->isOnRoad() || veh->isRemoteControlled()) && !veh->isStopped()) {
570:             count++;
571:             speedSum += veh->getSpeed();
572:             relSpeedSum += veh->getEdge()->getSpeedLimit() > 0 ? veh->getSpeed() / veh->getEdge()->getSpeedLimit() : 0;
573:         }
574:     }
575:     if (count > 0) {
576:         return std::make_pair(speedSum / count, relSpeedSum / count);
577:     } else {
578:         return std::make_pair(-1, -1);
579:     }
580: }
583: int
584: MSVehicleControl::getQuota(double frac, int loaded) const {
585:     frac = frac < 0 ? myScale : frac;
```

### C3. Integrals and metric writer — `microsim/output/MSMeanData_Net.cpp:76-363`

```cpp
76: MSMeanData_Net::MSLaneMeanDataValues::reset(bool) {
77:     nVehDeparted = 0;
78:     nVehArrived = 0;
79:     nVehEntered = 0;
80:     nVehLeft = 0;
81:     nVehVaporized = 0;
82:     nVehTeleported = 0;
83:     nVehLaneChangeFrom = 0;
84:     nVehLaneChangeTo = 0;
85:     sampleSeconds = 0.;
86:     travelledDistance = 0;
87:     waitSeconds = 0;
88:     timeLoss = 0;
89:     frontSampleSeconds = 0;
90:     frontTravelledDistance = 0;
91:     vehLengthSum = 0;
92:     occupationSum = 0;
93:     minimalVehicleLength = INVALID_DOUBLE;
94:     resetTime = SIMSTEP;
95: }
98: void
99: MSMeanData_Net::MSLaneMeanDataValues::addTo(MSMeanData::MeanDataValues& val) const {
100:     MSLaneMeanDataValues& v = (MSLaneMeanDataValues&) val;
101:     v.nVehDeparted += nVehDeparted;
102:     v.nVehArrived += nVehArrived;
103:     v.nVehEntered += nVehEntered;
104:     v.nVehLeft += nVehLeft;
105:     v.nVehVaporized += nVehVaporized;
106:     v.nVehTeleported += nVehTeleported;
107:     v.nVehLaneChangeFrom += nVehLaneChangeFrom;
108:     v.nVehLaneChangeTo += nVehLaneChangeTo;
109:     v.sampleSeconds += sampleSeconds;
110:     v.travelledDistance += travelledDistance;
111:     v.waitSeconds += waitSeconds;
112:     v.timeLoss += timeLoss;
113:     v.frontSampleSeconds += frontSampleSeconds;
114:     v.frontTravelledDistance += frontTravelledDistance;
115:     v.vehLengthSum += vehLengthSum;
116:     v.occupationSum += occupationSum;
117:     if (v.minimalVehicleLength == INVALID_DOUBLE) {
118:         v.minimalVehicleLength = minimalVehicleLength;
119:     } else {
120:         v.minimalVehicleLength = MIN2(minimalVehicleLength, v.minimalVehicleLength);
121:     }
122:     if (mySubData != nullptr) {
123:         mySubData->addTo(*val.getSubData());
124:     }
125: }
128: void
129: MSMeanData_Net::MSLaneMeanDataValues::notifyMoveInternal(
130:     const SUMOTrafficObject& veh, const double frontOnLane,
131:     const double timeOnLane, const double /* meanSpeedFrontOnLane */,
132:     const double meanSpeedVehicleOnLane,
133:     const double travelledDistanceFrontOnLane,
134:     const double travelledDistanceVehicleOnLane,
135:     const double meanLengthOnLane) {
148:     if (myParent != nullptr && !myParent->vehicleApplies(veh)) {
149:         return;
150:     }
151:     sampleSeconds += timeOnLane;
152:     travelledDistance += travelledDistanceVehicleOnLane;
153:     vehLengthSum += veh.getVehicleType().getLength() * timeOnLane;
154:     if (MSGlobals::gUseMesoSim) {
158:         occupationSum += veh.getVehicleType().getLength() * timeOnLane;
159:     } else {
162:         occupationSum += meanLengthOnLane * TS;
163:     }
164:     if (!veh.isStopped()) {
165:         if (myParent != nullptr && (meanSpeedVehicleOnLane < myParent->myHaltSpeed
166:                                     || (myParent->myHaltSpeedRel > 0 && meanSpeedVehicleOnLane / veh.getCurrentEdge()->getSpeedLimit(veh.getVClass()) < myParent->myHaltSpeedRel))) {
167:             waitSeconds += timeOnLane;
168:         } else if (MSGlobals::gUseMesoSim) {
169:             waitSeconds += STEPS2TIME(veh.getWaitingTime());
170:         }
171:         const double vmax = veh.getLane() == nullptr ? veh.getEdge()->getVehicleMaxSpeed(&veh) : veh.getLane()->getVehicleMaxSpeed(&veh);
172:         if (vmax > 0) {
173:             timeLoss += timeOnLane * MAX2(0.0, vmax - meanSpeedVehicleOnLane) / vmax;
174:         }
175:     }
176:     frontSampleSeconds += frontOnLane;
177:     frontTravelledDistance += travelledDistanceFrontOnLane;
178:     if (minimalVehicleLength == INVALID_DOUBLE) {
179:         minimalVehicleLength = veh.getVehicleType().getLengthWithGap();
180:     } else {
181:         minimalVehicleLength = MIN2(minimalVehicleLength, veh.getVehicleType().getLengthWithGap());
182:     }
187: }
190: bool
191: MSMeanData_Net::MSLaneMeanDataValues::notifyLeave(SUMOTrafficObject& veh, double /*lastPos*/, MSMoveReminder::Notification reason, const MSLane* /* enteredLane */) {
192:     if ((myParent == nullptr || myParent->vehicleApplies(veh)) && (
193:                 getLane() == nullptr || !veh.isVehicle() || getLane() == static_cast<MSVehicle&>(veh).getLane())) {
194: #ifdef HAVE_FOX
195:         ScopedLocker<> lock(myNotificationMutex, MSGlobals::gNumSimThreads > 1);
196: #endif
197:         if (MSGlobals::gUseMesoSim) {
198:             removeFromVehicleUpdateValues(veh);
199:         }
200:         if (reason == MSMoveReminder::NOTIFICATION_ARRIVED) {
201:             ++nVehArrived;
202:         } else if (reason == MSMoveReminder::NOTIFICATION_LANE_CHANGE) {
203:             ++nVehLaneChangeFrom;
204:         } else if (myParent == nullptr || reason != MSMoveReminder::NOTIFICATION_SEGMENT) {
205:             ++nVehLeft;
206:             if (reason == MSMoveReminder::NOTIFICATION_TELEPORT || reason == MSMoveReminder::NOTIFICATION_TELEPORT_ARRIVED) {
207:                 ++nVehTeleported;
208:             } else if (reason >= MSMoveReminder::NOTIFICATION_VAPORIZED_CALIBRATOR) {
209:                 ++nVehVaporized;
210:             }
211:         }
212:     }
213:     if (MSGlobals::gUseMesoSim || !veh.isVehicle()) {
215:         return false;
216:     }
217:     return reason == MSMoveReminder::NOTIFICATION_JUNCTION;
218: }
221: bool
222: MSMeanData_Net::MSLaneMeanDataValues::notifyEnter(SUMOTrafficObject& veh, MSMoveReminder::Notification reason, const MSLane* enteredLane) {
228:     if (myParent == nullptr || myParent->vehicleApplies(veh)) {
229:         if (getLane() == nullptr || !veh.isVehicle() || getLane() == static_cast<MSVehicle&>(veh).getLane()) {
230: #ifdef HAVE_FOX
231:             ScopedLocker<> lock(myNotificationMutex, MSGlobals::gNumSimThreads > 1);
232: #endif
233:             if (reason == MSMoveReminder::NOTIFICATION_DEPARTED) {
234:                 ++nVehDeparted;
235:             } else if (reason == MSMoveReminder::NOTIFICATION_LANE_CHANGE) {
236:                 ++nVehLaneChangeTo;
237:             } else if (myParent == nullptr || reason != MSMoveReminder::NOTIFICATION_SEGMENT) {
238:                 ++nVehEntered;
239:             }
240:         }
241:         return true;
242:     }
243:     return false;
244: }
247: bool
248: MSMeanData_Net::MSLaneMeanDataValues::isEmpty() const {
249:     return sampleSeconds == 0 && nVehDeparted == 0 && nVehArrived == 0 && nVehEntered == 0
250:            && nVehLeft == 0 && nVehVaporized == 0 && nVehTeleported == 0 && nVehLaneChangeFrom == 0 && nVehLaneChangeTo == 0;
251: }
253: double
254: MSMeanData_Net::MSLaneMeanDataValues::getOccupancy(SUMOTime period, int numLanes) const {
255:     return occupationSum / STEPS2TIME(period) / myLaneLength / (double)numLanes * 100.;
256: }
258: void
259: MSMeanData_Net::MSLaneMeanDataValues::write(OutputDevice& dev, const SumoXMLAttrMask& attributeMask, const SUMOTime period,
260:         const int numLanes, const double speedLimit, const double defaultTravelTime, const int numVehicles) const {
262:     double density = frontSampleSeconds / STEPS2TIME(period) * 1000. / myLaneLength;
263:     double overlapDensity = sampleSeconds / STEPS2TIME(period) * 1000. / myLaneLength;
264:     if (MSGlobals::gLateralResolution < 0) {
266:         density = MIN2(density, 1000 * (double)numLanes / MAX2(minimalVehicleLength, NUMERICAL_EPS));
267:         overlapDensity = MIN2(overlapDensity, 1000 * (double)numLanes / MAX2(minimalVehicleLength, NUMERICAL_EPS));
268:     }
269:     const double laneDensity = density / (double)numLanes;
270:     const double occupancy = getOccupancy(period, numLanes);
283:     if (myParent == nullptr) {
284:         const double speed = sampleSeconds == 0 ? 0. : travelledDistance / sampleSeconds;
285:         const double frontSpeed = frontSampleSeconds == 0 ? 0. : frontTravelledDistance / frontSampleSeconds;
286:         dev.writeOptionalAttr(SUMO_ATTR_DENSITY, density, attributeMask, sampleSeconds == 0);
287:         dev.writeOptionalAttr(SUMO_ATTR_LANEDENSITY, laneDensity, attributeMask, sampleSeconds == 0);
288:         dev.writeOptionalAttr(SUMO_ATTR_OCCUPANCY, occupancy, attributeMask, sampleSeconds == 0);
289:         dev.writeOptionalAttr(SUMO_ATTR_WAITINGTIME, waitSeconds, attributeMask, sampleSeconds == 0);
290:         dev.writeOptionalAttr(SUMO_ATTR_TIMELOSS, timeLoss, attributeMask, sampleSeconds == 0);
291:         dev.writeOptionalAttr(SUMO_ATTR_SPEED, speed, attributeMask, sampleSeconds == 0);
292:         dev.writeOptionalAttr(SUMO_ATTR_SPEEDREL, speedLimit == 0. || sampleSeconds == 0 ? 0. : travelledDistance / sampleSeconds / speedLimit,
293:                               attributeMask, sampleSeconds == 0);
294:         dev.writeOptionalAttr(SUMO_ATTR_DEPARTED, nVehDeparted, attributeMask);
295:         dev.writeOptionalAttr(SUMO_ATTR_ARRIVED, nVehArrived, attributeMask);
296:         dev.writeOptionalAttr(SUMO_ATTR_ENTERED, nVehEntered, attributeMask);
297:         dev.writeOptionalAttr(SUMO_ATTR_LEFT, nVehLeft, attributeMask);
298:         dev.writeOptionalAttr(SUMO_ATTR_VAPORIZED, nVehVaporized, attributeMask, nVehVaporized == 0);
299:         dev.writeOptionalAttr(SUMO_ATTR_TELEPORTED, nVehTeleported, attributeMask, nVehTeleported == 0);
300:         dev.writeOptionalAttr(SUMO_ATTR_FLOW, density * frontSpeed * 3.6, attributeMask, frontSampleSeconds == 0);
301:         dev.writeOptionalAttr(SUMO_ATTR_DISTANCE, frontTravelledDistance, attributeMask);
302:         dev.closeTag();
303:         return;
304:     }
305:     const bool haveSamples = sampleSeconds > myParent->myMinSamples;
306:     const bool haveFrontSamples = frontSampleSeconds > myParent->myMinSamples;
307:     const bool haveSamplesOrDefault = haveSamples || defaultTravelTime >= 0.;
308:     bool haveTravelTime = haveSamplesOrDefault;
309:     double traveltime = myParent->myMaxTravelTime;
310:     if (haveSamples) {
311:         if (numVehicles > 0) {
312:             traveltime = sampleSeconds / numVehicles;
313:         } else {
314:             traveltime = myParent->myMaxTravelTime;
315:             if (frontTravelledDistance > NUMERICAL_EPS) {
316:                 traveltime = MIN2(traveltime, myLaneLength * frontSampleSeconds / frontTravelledDistance);
317:             } else if (defaultTravelTime >= 0.) {
318:                 traveltime = defaultTravelTime;
319:             } else {
320:                 haveTravelTime = false;
321:             }
322:         }
323:     } else if (defaultTravelTime >= 0.) {
324:         traveltime = defaultTravelTime;
325:     }
326:     dev.writeOptionalAttr(SUMO_ATTR_TRAVELTIME, traveltime, attributeMask, !haveTravelTime);
327:     double overlapTraveltime = myParent->myMaxTravelTime;
328:     if (travelledDistance > 0.) {
331:         overlapTraveltime = MIN2(overlapTraveltime, (myLaneLength + vehLengthSum / sampleSeconds) * sampleSeconds / travelledDistance);
332:     }
333:     dev.writeOptionalAttr(SUMO_ATTR_OVERLAPTRAVELTIME, overlapTraveltime, attributeMask, !haveSamples || numVehicles > 0);
334:     dev.writeOptionalAttr(SUMO_ATTR_DENSITY, density, attributeMask, !haveSamples || numVehicles > 0);
335:     dev.writeOptionalAttr(SUMO_ATTR_OVERLAPDENSITY, overlapDensity, attributeMask, sampleSeconds == 0);
336:     dev.writeOptionalAttr(SUMO_ATTR_LANEDENSITY, laneDensity, attributeMask, !haveSamples || numVehicles > 0);
337:     dev.writeOptionalAttr(SUMO_ATTR_OCCUPANCY, occupancy, attributeMask, !haveSamples || numVehicles > 0);
338:     dev.writeOptionalAttr(SUMO_ATTR_WAITINGTIME, waitSeconds, attributeMask, !haveSamples);
339:     dev.writeOptionalAttr(SUMO_ATTR_TIMELOSS, timeLoss, attributeMask, !haveSamples);
340:     double speed = 0.;
341:     double frontSpeed = 0.;
342:     if (haveSamples) {
343:         speed = travelledDistance / sampleSeconds;
344:     } else if (defaultTravelTime > 0.) {
345:         speed = myLaneLength / defaultTravelTime;
346:     }
347:     if (haveFrontSamples) {
348:         frontSpeed = frontTravelledDistance / frontSampleSeconds;
349:     } else if (defaultTravelTime > 0.) {
350:         frontSpeed = myLaneLength / defaultTravelTime;
351:     }
352:     dev.writeOptionalAttr(SUMO_ATTR_SPEED, speed, attributeMask, !haveSamplesOrDefault);
353:     dev.writeOptionalAttr(SUMO_ATTR_SPEEDREL, speedLimit == 0. ? 0. : speed / speedLimit, attributeMask, !haveSamplesOrDefault);
354:     dev.writeOptionalAttr(SUMO_ATTR_DEPARTED, nVehDeparted, attributeMask);
355:     dev.writeOptionalAttr(SUMO_ATTR_ARRIVED, nVehArrived, attributeMask);
356:     dev.writeOptionalAttr(SUMO_ATTR_ENTERED, nVehEntered, attributeMask);
357:     dev.writeOptionalAttr(SUMO_ATTR_LEFT, nVehLeft, attributeMask);
358:     dev.writeOptionalAttr(SUMO_ATTR_LANECHANGEDFROM, nVehLaneChangeFrom, attributeMask);
359:     dev.writeOptionalAttr(SUMO_ATTR_LANECHANGEDTO, nVehLaneChangeTo, attributeMask);
360:     dev.writeOptionalAttr(SUMO_ATTR_VAPORIZED, nVehVaporized, attributeMask, nVehVaporized == 0);
361:     dev.writeOptionalAttr(SUMO_ATTR_TELEPORTED, nVehTeleported, attributeMask, nVehTeleported == 0);
362:     dev.writeOptionalAttr(SUMO_ATTR_FLOW, density * frontSpeed * 3.6, attributeMask, !haveSamples || numVehicles == 0);
363:     dev.writeOptionalAttr(SUMO_ATTR_DISTANCE, frontTravelledDistance, attributeMask);
```

### C3. Partial body occupancy — `microsim/output/MSMeanData.cpp:87-256`

```cpp
87: MSMeanData::MeanDataValues::notifyMove(SUMOTrafficObject& veh, double oldPos, double newPos, double newSpeed) {
90:     const double oldSpeed = veh.getPreviousSpeed();
91:     double enterSpeed = MSGlobals::gSemiImplicitEulerUpdate ? newSpeed : oldSpeed; // NOTE: For the euler update, the vehicle is assumed to travel at constant speed for the whole time step
92:     double leaveSpeed = newSpeed, leaveSpeedFront = newSpeed;
95:     double timeOnLane = TS;
96:     double frontOnLane = oldPos > myLaneLength ? 0. : TS;
97:     bool ret = true;
100:     double timeBeforeEnter = 0.;
101:     double timeBeforeEnterBack = 0.;
102:     double timeBeforeLeaveFront = newPos <= myLaneLength ? TS : 0.;
103:     double timeBeforeLeave = TS;
106:     if (oldPos < 0 && newPos >= 0) {
108:         timeBeforeEnter = MSCFModel::passingTime(oldPos, 0, newPos, oldSpeed, newSpeed);
109:         timeOnLane = TS - timeBeforeEnter;
110:         frontOnLane = timeOnLane;
111:         enterSpeed = MSCFModel::speedAfterTime(timeBeforeEnter, oldSpeed, newPos - oldPos);
112:     }
114:     const double oldBackPos = oldPos - veh.getVehicleType().getLength();
115:     const double newBackPos = newPos - veh.getVehicleType().getLength();
118:     if (oldBackPos < 0. && newBackPos > 0.) {
119:         timeBeforeEnterBack = MSCFModel::passingTime(oldBackPos, 0., newBackPos, oldSpeed, newSpeed);
120:     } else if (newBackPos <= 0) {
121:         timeBeforeEnterBack = TS;
122:     } else {
123:         timeBeforeEnterBack = 0.;
124:     }
127:     if (newBackPos > myLaneLength // vehicle's back has left the lane
128:             && oldBackPos <= myLaneLength) { // and hasn't left the lane before
129:         assert(!MSGlobals::gSemiImplicitEulerUpdate || newSpeed != 0); // how could it move across the lane boundary otherwise
131:         timeBeforeLeave = MSCFModel::passingTime(oldBackPos, myLaneLength, newBackPos, oldSpeed, newSpeed);
132:         const double timeAfterLeave = TS - timeBeforeLeave;
133:         timeOnLane -= timeAfterLeave;
134:         leaveSpeed = MSCFModel::speedAfterTime(timeBeforeLeave, oldSpeed, newPos - oldPos);
136:         if (fabs(timeOnLane) < NUMERICAL_EPS) { // reduce rounding errors
137:             timeOnLane = 0.;
138:         }
139:         ret = veh.hasArrived();
140:     }
143:     if (newPos > myLaneLength && oldPos <= myLaneLength) {
145:         assert(!MSGlobals::gSemiImplicitEulerUpdate || newSpeed != 0);
146:         timeBeforeLeaveFront = MSCFModel::passingTime(oldPos, myLaneLength, newPos, oldSpeed, newSpeed);
147:         const double timeAfterLeave = TS - timeBeforeLeaveFront;
148:         frontOnLane -= timeAfterLeave;
150:         if (fabs(frontOnLane) < NUMERICAL_EPS) { // reduce rounding errors
151:             frontOnLane = 0.;
152:         }
153:         leaveSpeedFront = MSCFModel::speedAfterTime(timeBeforeLeaveFront, oldSpeed, newPos - oldPos);
154:     }
156:     assert(frontOnLane <= TS);
157:     assert(timeOnLane <= TS);
159:     if (timeOnLane < 0) {
160:         WRITE_ERRORF(TL("Negative vehicle step fraction for '%' on lane '%'."), veh.getID(), getLane()->getID());
161:         return veh.hasArrived();
162:     }
163:     if (timeOnLane == 0) {
164:         return veh.hasArrived();
165:     }
188:     assert(timeBeforeEnter <= MIN2(timeBeforeEnterBack, timeBeforeLeaveFront));
189:     assert(timeBeforeLeave >= MAX2(timeBeforeEnterBack, timeBeforeLeaveFront));
191:     double vehLength = veh.getVehicleType().getLength();
193:     double lengthOnLaneAtStepStart = MAX2(0., MIN4(myLaneLength, vehLength, vehLength - (oldPos - myLaneLength), oldPos));
195:     double lengthOnLaneAtStepEnd = MAX2(0., MIN4(myLaneLength, vehLength, vehLength - (newPos - myLaneLength), newPos));
196:     double integratedLengthOnLane = 0.;
197:     if (timeBeforeEnterBack < timeBeforeLeaveFront) {
200:         double lengthOnLaneAtBackEnter = MIN2(veh.getVehicleType().getLength(), newPos);
202:         integratedLengthOnLane += (timeBeforeEnterBack - timeBeforeEnter) * (lengthOnLaneAtBackEnter + lengthOnLaneAtStepStart) * 0.5;
205:         integratedLengthOnLane += (timeBeforeLeaveFront - timeBeforeEnterBack) * vehLength;
207:         integratedLengthOnLane += (timeBeforeLeave - timeBeforeLeaveFront) * (vehLength + lengthOnLaneAtStepEnd) * 0.5;
208:     } else if (timeBeforeEnterBack >= timeBeforeLeaveFront) {
211:         double lengthOnLaneAtLeaveFront;
212:         if (timeBeforeLeaveFront == timeBeforeEnter) {
214:             lengthOnLaneAtLeaveFront = lengthOnLaneAtStepStart;
215:         } else if (timeBeforeLeaveFront == timeBeforeLeave) {
217:             lengthOnLaneAtLeaveFront = lengthOnLaneAtStepEnd;
218:         } else {
219:             lengthOnLaneAtLeaveFront = myLaneLength;
220:         }
225:         integratedLengthOnLane += (timeBeforeLeaveFront - timeBeforeEnter) * (lengthOnLaneAtLeaveFront + lengthOnLaneAtStepStart) * 0.5;
227:         integratedLengthOnLane += (timeBeforeEnterBack - timeBeforeLeaveFront) * lengthOnLaneAtLeaveFront;
229:         integratedLengthOnLane += (timeBeforeLeave - timeBeforeEnterBack) * (lengthOnLaneAtLeaveFront + lengthOnLaneAtStepEnd) * 0.5;
230:     }
232:     double meanLengthOnLane = integratedLengthOnLane / TS;
243:     const double travelledDistanceFrontOnLane = MSGlobals::gSemiImplicitEulerUpdate ? frontOnLane * newSpeed
244:             : MAX2(0., MIN2(newPos, myLaneLength) - MAX2(oldPos, 0.));
245:     const double travelledDistanceVehicleOnLane = MSGlobals::gSemiImplicitEulerUpdate ? timeOnLane * newSpeed
246:             : MIN2(newPos, myLaneLength) - MAX2(oldPos, 0.) + MIN2(MAX2(0., newPos - myLaneLength), veh.getVehicleType().getLength());
251: #ifdef HAVE_FOX
252:     ScopedLocker<> lock(myNotificationMutex, MSGlobals::gNumSimThreads > 1);
253: #endif
254:     notifyMoveInternal(veh, frontOnLane, timeOnLane, (enterSpeed + leaveSpeedFront) / 2., (enterSpeed + leaveSpeed) / 2., travelledDistanceFrontOnLane, travelledDistanceVehicleOnLane, meanLengthOnLane);
255:     return ret;
256: }
```

### C3. Empty/default controls — `microsim/output/MSMeanData.cpp:401-435`

```cpp
401:                        const bool useLanes, const std::string& excludeEmpty, const bool withInternal,
402:                        const bool trackVehicles,
403:                        const int detectPersons,
404:                        const double maxTravelTime,
405:                        const double minSamples,
406:                        const std::string& vTypes,
407:                        const std::string& writeAttributes,
408:                        const std::vector<MSEdge*>& edges,
409:                        AggregateType aggregate) :
410:     MSDetectorFileOutput(id, vTypes, "", detectPersons),
411:     myMinSamples(minSamples),
412:     myMaxTravelTime(maxTravelTime),
413:     myAmEdgeBased(!useLanes),
414:     myDumpBegin(dumpBegin),
415:     myDumpEnd(dumpEnd),
416:     myInitTime(SUMOTime_MAX),
417:     myLastResetTime(dumpBegin),
418:     myEdges(edges),
419:     myDumpInternal(withInternal && MSGlobals::gUsingInternalLanes),
420:     myTrackVehicles(trackVehicles),
421:     myWrittenAttributes(OutputDevice::parseWrittenAttributes(StringTokenizer(writeAttributes).getVector(), "meandata '" + id + "'")),
422:     myAggregate(aggregate) {
423:     try {
424:         myDumpEmpty = !StringUtils::toBool(excludeEmpty);
425:     } catch (const BoolFormatException&) {
426:         if (excludeEmpty == "default" || excludeEmpty == "defaults") {
427:             myPrintDefaults = true;
428:         } else if (excludeEmpty == "modified") {
429:             myDumpEmpty = false;
430:             myPrintDefaults = true;
431:             myPrintModified = true;
432:         } else {
433:             throw;
434:         }
435:     }
```

### C3. Edge and lane aggregation — `microsim/output/MSMeanData.cpp:650-780`

```cpp
650:             MSEdge* edge = myEdges[i];
651:             if (connected.count(edge) != 0) {
652:                 std::vector<MeanDataValues*>& edgeValues = myMeasures[i];
653:                 if (MSGlobals::gUseMesoSim) {
654:                     MESegment* s = MSGlobals::gMesoNet->getSegmentForEdge(*edge);
655:                     while (s != nullptr) {
656:                         for (MeanDataValues* meanData : edgeValues) {
657:                             s->prepareDetectorForWriting(*meanData);
658:                             meanData->addTo(*sumData);
659:                         }
660:                         s = s->getNextSegment();
661:                     }
662:                 } else {
663:                     for (MeanDataValues* meanData : edgeValues) {
664:                         meanData->addTo(*sumData);
665:                     }
666:                 }
667:             }
668:         }
669:         if (myDumpEmpty || !sumData->isEmpty()) {
670:             writePrefix(dev, *sumData, SUMO_TAG_EDGE, taz->getID());
671:             dev.writeAttr(SUMO_ATTR_NUMEDGES, connected.size());
672:             for (MeanDataValues* data = sumData; data != nullptr; data = data->getSubData()) {
673:                 data->write(dev, myWrittenAttributes, stopTime - startTime, laneNumber, speedSum / (double)connected.size(),
674:                             myPrintDefaults ? totalTT : -1.);
675:             }
676:             dev.closeTag();
677:         }
678:         delete sumData;
679:     }
681:     if (!MSNet::getInstance()->skipFinalReset()) {
682:         for (const std::vector<MeanDataValues*>& edgeValues : myMeasures) {
683:             for (MeanDataValues* meanData : edgeValues) {
684:                 meanData->reset();
685:             }
686:         }
687:     }
688: }
691: void
692: MSMeanData::writeEdge(OutputDevice& dev,
693:                       const std::vector<MeanDataValues*>& edgeValues,
694:                       const MSEdge* const edge, SUMOTime startTime, SUMOTime stopTime) {
695:     if (MSGlobals::gUseMesoSim) {
696:         int idx = 0;
697:         for (MeanDataValues* const data : edgeValues) {
698:             MESegment* s = MSGlobals::gMesoNet->getSegmentForEdge(*edge);
699:             while (s != nullptr) {
700:                 s->prepareDetectorForWriting(*data, myAmEdgeBased ? -1 : idx);
701:                 s = s->getNextSegment();
702:             }
703:             idx++;
704:         }
705:         if (myAmEdgeBased) {
706:             MeanDataValues* const data = edgeValues.front();
707:             if (myDumpEmpty || (myPrintModified && edge->getLanes()[0]->isSpeedModified()) || !data->isEmpty()) {
708:                 writePrefix(dev, *data, SUMO_TAG_EDGE, getEdgeID(edge));
709:                 for (MeanDataValues* d = data; d != nullptr; d = d->getSubData()) {
710:                     d->write(dev, myWrittenAttributes, stopTime - startTime,
711:                              edge->getNumDrivingLanes(),
712:                              edge->getSpeedLimit(),
713:                              myPrintDefaults ? edge->getLength() / edge->getSpeedLimit() : -1.);
714:                 }
715:                 dev.closeTag();
716:             }
717:             if (!MSNet::getInstance()->skipFinalReset()) {
718:                 data->reset(true);
719:             }
720:             return;
721:         }
722:     }
723:     if (!myAmEdgeBased) {
724:         bool writeCheck = myDumpEmpty;
725:         if (!writeCheck) {
726:             for (const MeanDataValues* const laneData : edgeValues) {
727:                 if (!laneData->isEmpty() || (myPrintModified && laneData->getLane()->isSpeedModified())) {
728:                     writeCheck = true;
729:                     break;
730:                 }
731:             }
732:         }
733:         if (writeCheck) {
734:             dev.openTag(SUMO_TAG_EDGE).writeAttr(SUMO_ATTR_ID, edge->getID());
735:         }
736:         for (MeanDataValues* const laneData : edgeValues) {
737:             const MSLane* const lane = laneData->getLane();
738:             if (myDumpEmpty || (myPrintModified && lane->isSpeedModified()) || !laneData->isEmpty()) {
739:                 writePrefix(dev, *laneData, SUMO_TAG_LANE, lane->getID());
740:                 for (MeanDataValues* data = laneData; data != nullptr; data = data->getSubData()) {
741:                     data->write(dev, myWrittenAttributes, stopTime - startTime, 1, lane->getSpeedLimit(),
742:                                 myPrintDefaults ? lane->getLength() / lane->getSpeedLimit() : -1.);
743:                 }
744:                 dev.closeTag();
745:             }
746:             if (!MSNet::getInstance()->skipFinalReset()) {
747:                 laneData->reset(true);
748:             }
749:         }
750:         if (writeCheck) {
751:             dev.closeTag();
752:         }
753:     } else {
754:         if (myTrackVehicles) {
755:             MeanDataValues* meanData = *edgeValues.begin();
756:             if (myDumpEmpty || !meanData->isEmpty()) {
757:                 writePrefix(dev, *meanData, SUMO_TAG_EDGE, edge->getID());
758:                 for (MeanDataValues* data = meanData; data != nullptr; data = data->getSubData()) {
759:                     data->write(dev, myWrittenAttributes, stopTime - startTime, edge->getNumDrivingLanes(), edge->getSpeedLimit(),
760:                                 myPrintDefaults ? edge->getLength() / edge->getSpeedLimit() : -1.);
761:                 }
762:                 dev.closeTag();
763:             }
764:             if (!MSNet::getInstance()->skipFinalReset()) {
765:                 meanData->reset(true);
766:             }
767:         } else {
768:             MeanDataValues* sumData = createValuesSubData(nullptr, edge->getLength(), false);
769:             bool writeCheck = myDumpEmpty;
770:             for (MeanDataValues* const laneData : edgeValues) {
771:                 laneData->addTo(*sumData);
772:                 if (myPrintModified && laneData->getLane()->isSpeedModified()) {
773:                     writeCheck = true;
774:                 }
775:                 if (!MSNet::getInstance()->skipFinalReset()) {
776:                     laneData->reset();
777:                 }
778:             }
779:             if (writeCheck || !sumData->isEmpty()) {
780:                 writePrefix(dev, *sumData, SUMO_TAG_EDGE, getEdgeID(edge));
```

### C4. Loop detection — `microsim/output/MSInductLoop.cpp:115-263`

```cpp
115: MSInductLoop::notifyEnter(SUMOTrafficObject& veh, Notification reason, const MSLane* /* enteredLane */) {
117:     if (!vehicleApplies(veh) && (veh.isPerson() || myDetectPersons <= (int)PersonMode::WALK)) {
118:         return false;
119:     }
120:     if (MSGlobals::gUseMesoSim) {
121:         MEVehicle* mesoveh = dynamic_cast<MEVehicle*>(&veh);
122:         assert(mesoveh != nullptr);
123:         const MESegment* seg = mesoveh->getSegment();
124:         if (seg != nullptr && (seg->numQueues() == 1 || mesoveh->getQueIndex() == myLane->getIndex())) {
125:             const SUMOTime onSegTime = mesoveh->getEventTime() - mesoveh->getLastEntryTime();
127:             const SUMOTime exLeaveTime = mesoveh->getLastEntryTime() + (SUMOTime)((double)onSegTime * mySegmentPos / seg->getLength());
129:             myNextMesoLeaveTimes.push(exLeaveTime);
130:         }
131:         return true;
132:     }
133:     if (reason != NOTIFICATION_JUNCTION) { // the junction case is handled in notifyMove
134:         if (veh.getBackPositionOnLane(myLane) >= myPosition) {
135:             return false;
136:         }
137:         if (veh.getPositionOnLane() >= myPosition) {
138: #ifdef HAVE_FOX
139:             ScopedLocker<> lock(myNotificationMutex, myNeedLock);
140: #endif
141:             myVehiclesOnDet[&veh] = SIMTIME;
142:             myEnteredVehicleNumber++;
143:         }
144:     }
145:     return true;
146: }
149: bool
150: MSInductLoop::notifyMove(SUMOTrafficObject& veh, double oldPos,
151:                          double newPos, double newSpeed) {
152:     if (newPos < myPosition) {
154:         return true;
155:     }
156:     if (myDetectPersons > (int)PersonMode::WALK && !veh.isPerson()) {
157:         bool keep = false;
158:         MSBaseVehicle& v = dynamic_cast<MSBaseVehicle&>(veh);
159:         for (MSTransportable* p : v.getPersons()) {
160:             keep = notifyMove(*p, oldPos, newPos, newSpeed);
161:         }
162:         return keep;
163:     }
164: #ifdef HAVE_FOX
165:     ScopedLocker<> lock(myNotificationMutex, myNeedLock);
166: #endif
167:     const double oldSpeed = veh.getPreviousSpeed();
168:     if (newPos >= myPosition && oldPos < myPosition) {
170:         const double timeBeforeEnter = MSCFModel::passingTime(oldPos, myPosition, newPos, oldSpeed, newSpeed);
171:         myVehiclesOnDet[&veh] = SIMTIME + timeBeforeEnter;
172:         myEnteredVehicleNumber++;
178:     }
179:     double oldBackPos = oldPos - veh.getVehicleType().getLength();
180:     double newBackPos = newPos - veh.getVehicleType().getLength();
181:     if (newBackPos > myEndPosition) {
185:         if (oldBackPos <= myEndPosition) {
186:             const std::map<SUMOTrafficObject*, double>::iterator it = myVehiclesOnDet.find(&veh);
187:             if (it != myVehiclesOnDet.end()) {
188:                 const double entryTime = it->second;
189:                 const double leaveTime = SIMTIME + MSCFModel::passingTime(oldBackPos, myEndPosition, newBackPos, oldSpeed, newSpeed);
190:                 myVehiclesOnDet.erase(it);
191:                 assert(entryTime <= leaveTime);
192:                 myVehicleDataCont.push_back(VehicleData(veh, entryTime, leaveTime, false, myEndPosition - myPosition));
193:                 myLastLeaveTime = leaveTime;
199:             } else {
205:             }
206:         } else {
209:             myVehiclesOnDet.erase(&veh);
215:         }
216:         return false;
217:     }
219:     return true;
220: }
223: bool
224: MSInductLoop::notifyLeave(SUMOTrafficObject& veh, double lastPos, MSMoveReminder::Notification reason, const MSLane* /* enteredLane */) {
225:     if (veh.isPerson() && myDetectPersons != (int)PersonMode::NONE) {
226:         const int lastDir = lastPos < 0 ? MSPModel::BACKWARD : MSPModel::FORWARD;
227:         notifyMovePerson(dynamic_cast<MSTransportable*>(&veh), lastDir, lastPos);
228:     }
229:     if (MSGlobals::gUseMesoSim && reason <= MSMoveReminder::NOTIFICATION_SEGMENT && vehicleApplies(veh)) {
230:         MEVehicle* mesoveh = dynamic_cast<MEVehicle*>(&veh);
231:         assert(mesoveh != nullptr);
232:         const MESegment* seg = mesoveh->getSegment();
233:         if (seg != nullptr && (seg->numQueues() == 1 || mesoveh->getQueIndex() == myLane->getIndex())) {
238:             const SUMOTime inLeaveTime = mesoveh->getEventTime() - TIME2STEPS((seg->getLength() - mySegmentPos - mesoveh->getLength()) / myLane->getSpeedLimit());
240:             auto q = seg->getQueue(mesoveh->getQueIndex());
241:             if (q.size() > 1 && vehicleApplies(*q[q.size() - 2])) {
242:                 myLastMesoLeaveTimes.push(inLeaveTime + TIME2STEPS(seg->getLastHeadwaySeconds()));
244:             }
245:             myLastMesoLeaveTimes.push(inLeaveTime);
246:             myEnteredVehicleNumber++;
247:         }
248:         return false;
249:     }
250:     if (reason != MSMoveReminder::NOTIFICATION_JUNCTION || (veh.isPerson() && myDetectPersons != (int)PersonMode::NONE)) {
251: #ifdef HAVE_FOX
252:         ScopedLocker<> lock(myNotificationMutex, myNeedLock);
253: #endif
254:         const std::map<SUMOTrafficObject*, double>::iterator it = myVehiclesOnDet.find(&veh);
255:         if (it != myVehiclesOnDet.end()) {
256:             const double entryTime = it->second;
257:             const double leaveTime = SIMTIME + TS;
258:             myVehiclesOnDet.erase(it);
259:             myVehicleDataCont.push_back(VehicleData(veh, entryTime, leaveTime, true));
260:             myLastLeaveTime = leaveTime;
261:         }
262:         return false;
263:     }
```

### C4. Loop output — `microsim/output/MSInductLoop.cpp:486-526`

```cpp
486: MSInductLoop::writeXMLOutput(OutputDevice& dev, SUMOTime startTime, SUMOTime stopTime) {
487:     if (dev.isNull()) {
488:         reset();
489:         return;
490:     }
491:     const double t(STEPS2TIME(stopTime - startTime));
492:     double occupancy = 0.;
493:     double speedSum = 0.;
494:     double lengthSum = 0.;
495:     int contrib = 0;
497:     double inverseSpeedSum = 0.;
498:     for (const VehicleData& vData : myVehicleDataCont) {
499:         const double timeOnDetDuringInterval = vData.leaveTimeM - MAX2(STEPS2TIME(startTime), vData.entryTimeM);
500:         occupancy += MIN2(timeOnDetDuringInterval, t);
501:         if (!vData.leftEarlyM) {
502:             speedSum += vData.speedM;
503:             assert(vData.speedM > 0.);
504:             inverseSpeedSum += 1. / vData.speedM;
505:             lengthSum += vData.lengthM;
506:             contrib++;
507:         }
508:     }
509:     if (MSGlobals::gUseMesoSim) {
510:         contrib = myEnteredVehicleNumber;
511:     }
512:     const double flow = (double)contrib / t * 3600.;
513:     for (std::map< SUMOTrafficObject*, double >::const_iterator i = myVehiclesOnDet.begin(); i != myVehiclesOnDet.end(); ++i) {
514:         occupancy += STEPS2TIME(stopTime) - MAX2(STEPS2TIME(startTime), i->second);
515:     }
516:     occupancy *= 100. / t;
517:     const double meanSpeed = contrib != 0 ? speedSum / (double)contrib : -1;
518:     const double harmonicMeanSpeed = contrib != 0 ? (double)contrib / inverseSpeedSum : -1;
519:     const double meanLength = contrib != 0 ? lengthSum / (double)contrib : -1;
520:     dev.openTag(SUMO_TAG_INTERVAL).writeTime(SUMO_ATTR_BEGIN, startTime).writeTime(SUMO_ATTR_END, stopTime);
521:     dev.writeAttr(SUMO_ATTR_ID, StringUtils::escapeXML(getID())).writeAttr("nVehContrib", contrib);
522:     dev.writeAttr("flow", flow).writeAttr("occupancy", occupancy).writeAttr("speed", meanSpeed).writeAttr("harmonicMeanSpeed", harmonicMeanSpeed);
523:     dev.writeAttr("length", meanLength).writeAttr("nVehEntered", myEnteredVehicleNumber).closeTag();
524:     reset();
525: }
```

### C4. Passage speed — `microsim/output/MSInductLoop.cpp:595-600`

```cpp
595: MSInductLoop::VehicleData::VehicleData(const SUMOTrafficObject& v, double entryTimestep,
596:                                        double leaveTimestep, const bool leftEarly, const double detLength)
597:     : idM(v.getID()), lengthM(v.getVehicleType().getLength()), entryTimeM(entryTimestep), leaveTimeM(leaveTimestep),
598:       speedM((v.getVehicleType().getLength() + detLength) / MAX2(leaveTimestep - entryTimestep, NUMERICAL_EPS)), typeIDM(v.getVehicleType().getID()),
599:       leftEarlyM(leftEarly) {}
```

### C5. FCD fields — `microsim/output/MSFCDExport.cpp:45-350`

```cpp
45: #include "MSFCDExport.h"
51: void
52: MSFCDExport::write(OutputDevice& of, const SUMOTime timestep, const SumoXMLTag tag) {
53:     MSDevice_FCD::initOnce();
54:     const SUMOTime period = MSDevice_FCD::getPeriod();
55:     const SUMOTime begin = MSDevice_FCD::getBegin();
56:     if ((period > 0 && (timestep - begin) % period != 0) || timestep < begin) {
57:         return;
58:     }
59:     const SumoXMLAttrMask& mask = MSDevice_FCD::getWrittenAttributes();
60:     const bool useGeo = MSDevice_FCD::useGeo();
61:     const bool useUTM = MSDevice_FCD::useUTM();
62:     const double maxLeaderDistance = MSDevice_FCD::getMaxLeaderDistance();
63:     const std::vector<std::string>& params = MSDevice_FCD::getParamsToWrite();
64:     MSNet* net = MSNet::getInstance();
65:     MSVehicleControl& vc = net->getVehicleControl();
66:     const double radius = MSDevice_FCD::getRadius();
67:     const bool filter = MSDevice_FCD::getEdgeFilter().size() > 0;
68:     const bool shapeFilter = MSDevice_FCD::hasShapeFilter();
69:     std::set<const Named*> inRadius;
70:     if (radius > 0) {
72:         for (MSVehicleControl::constVehIt it = vc.loadedVehBegin(); it != vc.loadedVehEnd(); ++it) {
73:             const SUMOVehicle* veh = it->second;
74:             if (isVisible(veh) && hasOwnOutput(veh, filter, shapeFilter)) {
75:                 PositionVector shape;
76:                 shape.push_back(veh->getPosition());
77:                 libsumo::Helper::collectObjectsInRange(libsumo::CMD_GET_VEHICLE_VARIABLE, shape, radius, inRadius);
78:                 libsumo::Helper::collectObjectsInRange(libsumo::CMD_GET_PERSON_VARIABLE, shape, radius, inRadius);
79:             }
80:         }
81:     }
83:     bool wroteTimestep = false;
84:     auto openTimestep = [&]() {
85:         if (!wroteTimestep) {
86:             of.openTag("timestep").writeTime(SUMO_ATTR_TIME, timestep);
87:             wroteTimestep = true;
88:         }
89:     };
90:     if (!MSDevice_FCD::skipEmpty()) {
91:         openTimestep();
92:     }
93:     for (MSVehicleControl::constVehIt it = vc.loadedVehBegin(); it != vc.loadedVehEnd(); ++it) {
94:         const SUMOVehicle* const veh = it->second;
95:         if (isVisible(veh)) {
96:             const bool hasOutput = (tag == SUMO_TAG_NOTHING || tag == SUMO_TAG_VEHICLE) && hasOwnOutput(veh, filter, shapeFilter, (radius > 0 && inRadius.count(veh) > 0));
97:             if (hasOutput) {
98:                 openTimestep();
99:                 const MSVehicle* const microVeh = MSGlobals::gUseMesoSim ? nullptr : static_cast<const MSVehicle*>(veh);
100:                 Position pos = veh->getPosition();
101:                 if (useGeo) {
102:                     of.setPrecision(gPrecisionGeo);
103:                     GeoConvHelper::getFinal().cartesian2geo(pos);
104:                 } else if (useUTM) {
105:                     pos.sub(GeoConvHelper::getFinal().getOffset());
106:                 }
107:                 of.openTag(SUMO_TAG_VEHICLE);
108:                 of.writeAttr(SUMO_ATTR_ID, veh->getID());
109:                 of.writeOptionalAttr(SUMO_ATTR_X, pos.x(), mask);
110:                 of.writeOptionalAttr(SUMO_ATTR_Y, pos.y(), mask);
111:                 of.setPrecision(gPrecision);
112:                 of.writeOptionalAttr(SUMO_ATTR_Z, pos.z(), mask);
113:                 of.writeFuncAttr(SUMO_ATTR_ANGLE, [ = ]() {
114:                     return GeomHelper::naviDegree(veh->getAngle());
115:                 }, mask);
116:                 of.writeFuncAttr(SUMO_ATTR_TYPE, [ = ]() {
117:                     return veh->getVehicleType().getID();
118:                 }, mask);
119:                 of.writeFuncAttr(SUMO_ATTR_SPEED, [ = ]() {
120:                     return veh->getSpeed();
121:                 }, mask);
122:                 of.writeFuncAttr(SUMO_ATTR_SPEEDREL, [ = ]() {
123:                     const double speedLimit = veh->getEdge()->getSpeedLimit();
124:                     return speedLimit > 0 ? veh->getSpeed() / speedLimit : 0.;
125:                 }, mask);
126:                 of.writeFuncAttr(SUMO_ATTR_POSITION, [ = ]() {
127:                     return veh->getPositionOnLane();
128:                 }, mask);
129:                 of.writeFuncAttr(SUMO_ATTR_LANE, [ = ]() {
130:                     return MSGlobals::gUseMesoSim ? "" : microVeh->getLane()->getID();
131:                 }, mask, MSGlobals::gUseMesoSim);
132:                 of.writeFuncAttr(SUMO_ATTR_EDGE, [ = ]() {
133:                     return veh->getCurrentEdge()->getID();
134:                 }, mask, !MSGlobals::gUseMesoSim);
135:                 of.writeFuncAttr(SUMO_ATTR_SLOPE, [ = ]() {
136:                     return veh->getSlope();
137:                 }, mask);
138:                 if (!MSGlobals::gUseMesoSim) {
139:                     of.writeFuncAttr(SUMO_ATTR_SIGNALS, [ = ]() {
140:                         return microVeh->getSignals();
141:                     }, mask);
142:                     of.writeFuncAttr(SUMO_ATTR_ACCELERATION, [ = ]() {
143:                         return microVeh->getAcceleration();
144:                     }, mask);
145:                     of.writeFuncAttr(SUMO_ATTR_ACCELERATION_LAT, [ = ]() {
146:                         return microVeh->getLaneChangeModel().getAccelerationLat();
147:                     }, mask);
148:                     of.writeFuncAttr(SUMO_ATTR_SPEED_VEC, [ = ]() {
149:                         return GeomHelper::vectorize(microVeh->getSpeed(), microVeh->getAngle());
150:                     }, mask);
151:                     of.writeFuncAttr(SUMO_ATTR_ACCEL_VEC, [ = ]() {
152:                         return GeomHelper::vectorize(microVeh->getAcceleration(), microVeh->getAngle());
153:                     }, mask);
154:                 }
155:                 of.writeFuncAttr(SUMO_ATTR_DISTANCE, [ = ]() {
156:                     double lanePos = veh->getPositionOnLane();
157:                     if (!MSGlobals::gUseMesoSim && microVeh->getLane()->isInternal()) {
158:                         lanePos = microVeh->getRoute().getDistanceBetween(0., lanePos, microVeh->getEdge()->getLanes()[0], microVeh->getLane(),
159:                                   microVeh->getRoutePosition());
160:                     }
161:                     return veh->getEdge()->getDistanceAt(lanePos);
162:                 }, mask);
163:                 of.writeFuncAttr(SUMO_ATTR_ODOMETER, [ = ]() {
164:                     return veh->getOdometer();
165:                 }, mask);
166:                 of.writeFuncAttr(SUMO_ATTR_POSITION_LAT, [ = ]() {
167:                     return veh->getLateralPositionOnLane();
168:                 }, mask);
169:                 if (!MSGlobals::gUseMesoSim) {
170:                     of.writeFuncAttr(SUMO_ATTR_SPEED_LAT, [ = ]() {
171:                         return microVeh->getLaneChangeModel().getSpeedLat();
172:                     }, mask);
173:                 }
174:                 if (maxLeaderDistance >= 0 && !MSGlobals::gUseMesoSim) {
175:                     const std::pair<const MSVehicle* const, double> leader = microVeh->getLeader(maxLeaderDistance);
176:                     if (leader.first != nullptr) {
177:                         of.writeFuncAttr(SUMO_ATTR_LEADER_ID, [ = ]() {
178:                             return leader.first->getID();
179:                         }, mask);
180:                         of.writeFuncAttr(SUMO_ATTR_LEADER_SPEED, [ = ]() {
181:                             return leader.first->getSpeed();
182:                         }, mask);
183:                         of.writeFuncAttr(SUMO_ATTR_LEADER_GAP, [ = ]() {
184:                             return leader.second + microVeh->getVehicleType().getMinGap();
185:                         }, mask);
186:                     } else {
187:                         of.writeFuncAttr(SUMO_ATTR_LEADER_ID, [ = ]() {
188:                             return "";
189:                         }, mask);
190:                         of.writeFuncAttr(SUMO_ATTR_LEADER_SPEED, [ = ]() {
191:                             return -1;
192:                         }, mask);
193:                         of.writeFuncAttr(SUMO_ATTR_LEADER_GAP, [ = ]() {
194:                             return -1;
195:                         }, mask);
196:                     }
197:                 }
198:                 for (const std::string& key : params) {
199:                     std::string error;
200:                     const std::string value = static_cast<const MSBaseVehicle*>(veh)->getPrefixedParameter(key, error);
201:                     if (value != "") {
202:                         of.writeAttr(StringUtils::escapeXML(key), StringUtils::escapeXML(value));
203:                     }
204:                 }
205:                 of.writeFuncAttr(SUMO_ATTR_ARRIVALDELAY, [ = ]() {
206:                     const double arrivalDelay = static_cast<const MSBaseVehicle*>(veh)->getStopArrivalDelay();
207:                     if (arrivalDelay == INVALID_DOUBLE) {
209:                         return 0.;
210:                     }
211:                     return arrivalDelay;
212:                 }, mask);
213:                 of.writeFuncAttr(SUMO_ATTR_DELAY, [ = ]() {
214:                     const double delay = static_cast<const MSBaseVehicle*>(veh)->getStopDelay();
215:                     if (delay < 0) {
217:                         return 0.;
218:                     }
219:                     return delay;
220:                 }, mask);
221:                 if (MSGlobals::gUseMesoSim) {
222:                     const MEVehicle* mesoVeh = static_cast<const MEVehicle*>(veh);
223:                     of.writeFuncAttr(SUMO_ATTR_SEGMENT, [ = ]() {
224:                         return mesoVeh->getSegmentIndex();
225:                     }, mask);
226:                     of.writeFuncAttr(SUMO_ATTR_QUEUE, [ = ]() {
227:                         return mesoVeh->getQueIndex();
228:                     }, mask);
229:                     of.writeFuncAttr(SUMO_ATTR_ENTRYTIME, [ = ]() {
230:                         return mesoVeh->getLastEntryTimeSeconds();
231:                     }, mask);
232:                     of.writeFuncAttr(SUMO_ATTR_EVENTTIME, [ = ]() {
233:                         return mesoVeh->getEventTimeSeconds();
234:                     }, mask);
235:                     of.writeFuncAttr(SUMO_ATTR_BLOCKTIME, [ = ]() {
236:                         return mesoVeh->getBlockTime() == SUMOTime_MAX ? -1.0 : mesoVeh->getBlockTimeSeconds();
237:                     }, mask);
238:                 }
239:                 of.writeFuncAttr(SUMO_ATTR_TAG, [ = ]() {
240:                     return toString(SUMO_TAG_VEHICLE);
241:                 }, mask);
242:                 of.writeOptionalAttr(SUMO_ATTR_PERSON_NUMBER, veh->getPersonNumber(), mask);
243:                 of.writeOptionalAttr(SUMO_ATTR_CONTAINER_NUMBER, veh->getContainerNumber(), mask);
244:                 MSEmissionExport::writeEmissions(of, static_cast<const MSBaseVehicle*>(veh), false, mask);
245:                 of.closeTag();
246:             }
248:             if (tag == SUMO_TAG_NOTHING || tag == SUMO_TAG_PERSON) {
249:                 const MSEdge* edge = MSGlobals::gUseMesoSim ? veh->getEdge() : &veh->getLane()->getEdge();
250:                 for (const MSTransportable* const person : veh->getPersons()) {
251:                     if (hasOwnOutput(person, filter, shapeFilter, inRadius.count(person) > 0)) {
252:                         openTimestep();
253:                         writeTransportable(of, edge, person, veh, SUMO_TAG_PERSON, useGeo, mask);
254:                     }
255:                 }
256:                 for (const MSTransportable* const container : veh->getContainers()) {
257:                     if (hasOwnOutput(container, filter, shapeFilter, inRadius.count(container) > 0)) {
258:                         openTimestep();
259:                         writeTransportable(of, edge, container, veh, SUMO_TAG_CONTAINER, useGeo, mask);
260:                     }
261:                 }
262:             }
263:         }
264:     }
265:     if (tag == SUMO_TAG_NOTHING || tag == SUMO_TAG_PERSON) {
266:         if (net->hasPersons() && net->getPersonControl().hasTransportables()) {
268:             for (const MSEdge* const e : net->getEdgeControl().getEdges()) {
269:                 if (filter && MSDevice_FCD::getEdgeFilter().count(e) == 0) {
270:                     continue;
271:                 }
272:                 for (const MSTransportable* const person : e->getSortedPersons(timestep)) {
273:                     if (hasOwnOutput(person, filter, shapeFilter, inRadius.count(person) > 0)) {
274:                         openTimestep();
275:                         writeTransportable(of, e, person, nullptr, SUMO_TAG_PERSON, useGeo, mask);
276:                     }
277:                 }
278:             }
279:         }
280:         if (net->hasContainers() && net->getContainerControl().hasTransportables()) {
282:             for (const MSEdge* const e : net->getEdgeControl().getEdges()) {
283:                 if (filter && MSDevice_FCD::getEdgeFilter().count(e) == 0) {
284:                     continue;
285:                 }
286:                 for (MSTransportable* container : e->getSortedContainers(timestep)) {
287:                     if (hasOwnOutput(container, filter, shapeFilter, inRadius.count(container) > 0)) {
288:                         openTimestep();
289:                         writeTransportable(of, e, container, nullptr, SUMO_TAG_CONTAINER, useGeo, mask);
290:                     }
291:                 }
292:             }
293:         }
294:     }
295:     if (wroteTimestep) {
296:         of.closeTag();
297:     }
298: }
301: bool
302: MSFCDExport::isVisible(const SUMOVehicle* veh) {
303:     return veh->isOnRoad() || veh->isParking() || veh->isRemoteControlled();
304: }
307: bool
308: MSFCDExport::hasOwnOutput(const SUMOVehicle* veh, bool filter, bool shapeFilter, bool isInRadius) {
309:     return ((!filter || MSDevice_FCD::getEdgeFilter().count(veh->getEdge()) > 0)
310:             && (!shapeFilter || MSDevice_FCD::shapeFilter(veh))
311:             && ((veh->getDevice(typeid(MSDevice_FCD)) != nullptr) || isInRadius));
312: }
315: bool
316: MSFCDExport::hasOwnOutput(const MSTransportable* p, bool filter, bool shapeFilter, bool isInRadius) {
317:     return ((!filter || MSDevice_FCD::getEdgeFilter().count(p->getEdge()) > 0)
318:             && (!shapeFilter || MSDevice_FCD::shapeFilter(p))
319:             && ((p->getDevice(typeid(MSTransportableDevice_FCD)) != nullptr) || isInRadius));
320: }
323: void
324: MSFCDExport::writeTransportable(OutputDevice& of, const MSEdge* const e, const MSTransportable* const p, const SUMOVehicle* const v,
325:                                 const SumoXMLTag tag, const bool useGeo, const SumoXMLAttrMask mask) {
326:     Position pos = p->getPosition();
327:     if (useGeo) {
328:         of.setPrecision(gPrecisionGeo);
329:         GeoConvHelper::getFinal().cartesian2geo(pos);
330:     }
331:     of.openTag(tag);
332:     of.writeAttr(SUMO_ATTR_ID, p->getID());
333:     of.writeOptionalAttr(SUMO_ATTR_X, pos.x(), mask);
334:     of.writeOptionalAttr(SUMO_ATTR_Y, pos.y(), mask);
335:     of.setPrecision(gPrecision);
336:     of.writeOptionalAttr(SUMO_ATTR_Z, pos.z(), mask);
337:     of.writeOptionalAttr(SUMO_ATTR_ANGLE, GeomHelper::naviDegree(p->getAngle()), mask);
338:     of.writeOptionalAttr(SUMO_ATTR_TYPE, p->getVehicleType().getID(), mask);
339:     of.writeOptionalAttr(SUMO_ATTR_SPEED, p->getSpeed(), mask);
340:     of.writeOptionalAttr(SUMO_ATTR_SPEEDREL, e->getSpeedLimit() > 0 ? p->getSpeed() / e->getSpeedLimit() : 0., mask);
341:     of.writeOptionalAttr(SUMO_ATTR_POSITION, p->getEdgePos(), mask);
342:     of.writeOptionalAttr(SUMO_ATTR_LANE, "", mask, true);
343:     of.writeOptionalAttr(SUMO_ATTR_EDGE, e->getID(), mask);
344:     of.writeOptionalAttr(SUMO_ATTR_SLOPE, e->getLanes()[0]->getShape().slopeDegreeAtOffset(p->getEdgePos()), mask);
345:     of.writeOptionalAttr(SUMO_ATTR_VEHICLE, v == nullptr ? "" : v->getID(), mask);
346:     of.writeOptionalAttr(SUMO_ATTR_STAGE, p->getCurrentStageDescription(), mask);
347:     of.writeOptionalAttr(SUMO_ATTR_TAG, toString(tag), mask);
348:     of.closeTag();
349: }
```

### D1. Route waypoints and distributions — `microsim/MSRouteHandler.cpp:105-379`

```cpp
105: MSRouteHandler::parseFromViaTo(SumoXMLTag tag, const SUMOSAXAttributes& attrs) {
106:     const std::string element = toString(tag);
107:     myActiveRoute.clear();
108:     bool useTaz = OptionsCont::getOptions().getBool("with-taz");
109:     if (useTaz && !myVehicleParameter->wasSet(VEHPARS_FROM_TAZ_SET) && !myVehicleParameter->wasSet(VEHPARS_TO_TAZ_SET)) {
110:         WRITE_WARNINGF(TL("Taz usage was requested but no taz present in % '%'!"), element, myVehicleParameter->id);
111:         useTaz = false;
112:     }
113:     bool ok = true;
114:     const std::string rid = "for " + element + " '" + myVehicleParameter->id + "'";
115:     SUMOVehicleClass vClass = SVC_PASSENGER;
116:     auto& vc = MSNet::getInstance()->getVehicleControl();
117:     if (!vc.getVTypeDistribution(myVehicleParameter->vtypeid)) {
118:         MSVehicleType* const type = vc.getVType(myVehicleParameter->vtypeid, &myParsingRNG);
119:         if (type != nullptr) {
120:             vClass = type->getParameter().vehicleClass;
121:         }
122:     }
124:     if ((useTaz || (!attrs.hasAttribute(SUMO_ATTR_FROM) && !attrs.hasAttribute(SUMO_ATTR_FROMXY) && !attrs.hasAttribute(SUMO_ATTR_FROMLONLAT))) &&
125:             (attrs.hasAttribute(SUMO_ATTR_FROM_TAZ) || attrs.hasAttribute(SUMO_ATTR_FROM_JUNCTION))) {
126:         const bool useJunction = attrs.hasAttribute(SUMO_ATTR_FROM_JUNCTION);
127:         const std::string tazType = useJunction ? "junction" : "taz";
128:         const std::string tazID = attrs.get<std::string>(useJunction ? SUMO_ATTR_FROM_JUNCTION : SUMO_ATTR_FROM_TAZ, myVehicleParameter->id.c_str(), ok);
129:         const MSEdge* fromTaz = MSEdge::dictionary(tazID + "-source");
130:         if (fromTaz == nullptr) {
131:             throw ProcessError("Source " + tazType + " '" + tazID + "' not known " + rid + "!"
132:                                + (useJunction ? JUNCTION_TAZ_MISSING_HELP : ""));
133:         } else if (fromTaz->getNumSuccessors() == 0 && tag != SUMO_TAG_PERSON) {
134:             throw ProcessError("Source " + tazType + " '" + tazID + "' has no outgoing edges " + rid + "!");
135:         } else {
136:             myActiveRoute.push_back(fromTaz);
137:         }
138:     } else if (attrs.hasAttribute(SUMO_ATTR_FROMXY)) {
139:         parseGeoEdges(attrs.get<PositionVector>(SUMO_ATTR_FROMXY, myVehicleParameter->id.c_str(), ok), false, vClass, myActiveRoute, rid, true, ok);
140:         if (myMapMatchTAZ && ok) {
141:             myVehicleParameter->fromTaz = myActiveRoute.back()->getID();
142:             myVehicleParameter->parametersSet |= VEHPARS_FROM_TAZ_SET;
143:         }
144:     } else if (attrs.hasAttribute(SUMO_ATTR_FROMLONLAT)) {
145:         parseGeoEdges(attrs.get<PositionVector>(SUMO_ATTR_FROMLONLAT, myVehicleParameter->id.c_str(), ok), true, vClass, myActiveRoute, rid, true, ok);
146:         if (myMapMatchTAZ && ok) {
147:             myVehicleParameter->fromTaz = myActiveRoute.back()->getID();
148:             myVehicleParameter->parametersSet |= VEHPARS_FROM_TAZ_SET;
149:         }
150:     } else {
151:         MSEdge::parseEdgesList(attrs.getOpt<std::string>(SUMO_ATTR_FROM, myVehicleParameter->id.c_str(), ok),
152:                                myActiveRoute, rid);
153:     }
154:     if (!ok) {
155:         throw ProcessError();
156:     }
159:     if (!attrs.hasAttribute(SUMO_ATTR_VIA) && !attrs.hasAttribute(SUMO_ATTR_ROUTE)) {
160:         myInsertStopEdgesAt = (int)myActiveRoute.size();
161:     }
162:     ConstMSEdgeVector viaEdges;
163:     if (attrs.hasAttribute(SUMO_ATTR_VIAXY)) {
164:         parseGeoEdges(attrs.get<PositionVector>(SUMO_ATTR_VIAXY, myVehicleParameter->id.c_str(), ok), false, vClass, viaEdges, rid, false, ok);
165:     } else if (attrs.hasAttribute(SUMO_ATTR_VIALONLAT)) {
166:         parseGeoEdges(attrs.get<PositionVector>(SUMO_ATTR_VIALONLAT, myVehicleParameter->id.c_str(), ok), true, vClass, viaEdges, rid, false, ok);
167:     } else if (attrs.hasAttribute(SUMO_ATTR_VIAJUNCTIONS)) {
168:         for (std::string junctionID : attrs.get<std::vector<std::string> >(SUMO_ATTR_VIAJUNCTIONS, myVehicleParameter->id.c_str(), ok)) {
169:             const MSEdge* viaSink = MSEdge::dictionary(junctionID + "-sink");
170:             if (viaSink == nullptr) {
171:                 throw ProcessError("Junction-taz '" + junctionID + "' not found." + JUNCTION_TAZ_MISSING_HELP);
172:             } else {
173:                 viaEdges.push_back(viaSink);
174:             }
175:         }
176:     } else {
177:         MSEdge::parseEdgesList(attrs.getOpt<std::string>(SUMO_ATTR_VIA, myVehicleParameter->id.c_str(), ok),
178:                                viaEdges, rid);
179:     }
180:     if (!viaEdges.empty()) {
181:         myHaveVia = true;
182:     }
183:     for (const MSEdge* e : viaEdges) {
184:         myActiveRoute.push_back(e);
185:         myVehicleParameter->via.push_back(e->getID());
186:     }
189:     if ((useTaz || (!attrs.hasAttribute(SUMO_ATTR_TO) && !attrs.hasAttribute(SUMO_ATTR_TOXY) && !attrs.hasAttribute(SUMO_ATTR_TOLONLAT))) &&
190:             (attrs.hasAttribute(SUMO_ATTR_TO_TAZ) || attrs.hasAttribute(SUMO_ATTR_TO_JUNCTION))) {
191:         const bool useJunction = attrs.hasAttribute(SUMO_ATTR_TO_JUNCTION);
192:         const std::string tazType = useJunction ? "junction" : "taz";
193:         const std::string tazID = attrs.get<std::string>(useJunction ? SUMO_ATTR_TO_JUNCTION : SUMO_ATTR_TO_TAZ, myVehicleParameter->id.c_str(), ok, true);
194:         const MSEdge* toTaz = MSEdge::dictionary(tazID + "-sink");
195:         if (toTaz == nullptr) {
196:             throw ProcessError("Sink " + tazType + " '" + tazID + "' not known " + rid + "!"
197:                                + (useJunction ? JUNCTION_TAZ_MISSING_HELP : ""));
198:         } else if (toTaz->getNumPredecessors() == 0 && tag != SUMO_TAG_PERSON) {
199:             throw ProcessError("Sink " + tazType + " '" + tazID + "' has no incoming edges " + rid + "!");
200:         } else {
201:             myActiveRoute.push_back(toTaz);
202:         }
203:     } else if (attrs.hasAttribute(SUMO_ATTR_TOXY)) {
204:         parseGeoEdges(attrs.get<PositionVector>(SUMO_ATTR_TOXY, myVehicleParameter->id.c_str(), ok, true), false, vClass, myActiveRoute, rid, false, ok);
205:         if (myMapMatchTAZ && ok) {
206:             myVehicleParameter->toTaz = myActiveRoute.back()->getID();
207:             myVehicleParameter->parametersSet |= VEHPARS_TO_TAZ_SET;
208:         }
209:     } else if (attrs.hasAttribute(SUMO_ATTR_TOLONLAT)) {
210:         parseGeoEdges(attrs.get<PositionVector>(SUMO_ATTR_TOLONLAT, myVehicleParameter->id.c_str(), ok, true), true, vClass, myActiveRoute, rid, false, ok);
211:         if (myMapMatchTAZ && ok) {
212:             myVehicleParameter->toTaz = myActiveRoute.back()->getID();
213:             myVehicleParameter->parametersSet |= VEHPARS_TO_TAZ_SET;
214:         }
215:     } else {
216:         MSEdge::parseEdgesList(attrs.getOpt<std::string>(SUMO_ATTR_TO, myVehicleParameter->id.c_str(), ok, "", true),
217:                                myActiveRoute, rid);
218:     }
219:     myActiveRouteID = "!" + myVehicleParameter->id;
220:     if (myVehicleParameter->routeid == "") {
221:         myVehicleParameter->routeid = myActiveRouteID;
222:     }
223: }
226: void
227: MSRouteHandler::myStartElement(int element, const SUMOSAXAttributes& attrs) {
228:     try {
229:         if (myActiveTransportablePlan != nullptr && myActiveTransportablePlan->empty() && myVehicleParameter->departProcedure == DepartDefinition::TRIGGERED
230:                 && element != SUMO_TAG_RIDE && element != SUMO_TAG_TRANSPORT && element != SUMO_TAG_PARAM) {
231:             const std::string mode = myActiveType == ObjectTypeEnum::PERSON ? "ride" : "transport";
232:             throw ProcessError("Triggered departure for " + myActiveTypeName + " '" + myVehicleParameter->id + "' requires starting with a " + mode + ".");
233:         }
234:         if (myVehicleParameter == nullptr) {
235:             myActiveTypeName = toString((SumoXMLTag)element);
236:             myHaveVia = false;
237:         }
238:         SUMORouteHandler::myStartElement(element, attrs);
239:         switch (element) {
240:             case SUMO_TAG_PERSONFLOW:
241:                 addTransportable(attrs, true);
242:                 break;
243:             case SUMO_TAG_CONTAINERFLOW:
244:                 addTransportable(attrs, false);
245:                 break;
246:             case SUMO_TAG_FLOW:
247:                 if (myVehicleParameter) {
248:                     parseFromViaTo((SumoXMLTag)element, attrs);
249:                 }
250:                 break;
251:             case SUMO_TAG_TRIP:
252:                 parseFromViaTo((SumoXMLTag)element, attrs);
253:                 break;
254:             default:
255:                 break;
256:         }
257:     } catch (ProcessError&) {
258:         deleteActivePlanAndVehicleParameter();
259:         throw;
260:     }
261: }
264: void
265: MSRouteHandler::openVehicleTypeDistribution(const SUMOSAXAttributes& attrs) {
266:     bool ok = true;
267:     myCurrentVTypeDistributionID = attrs.get<std::string>(SUMO_ATTR_ID, nullptr, ok);
268:     if (ok) {
269:         myCurrentVTypeDistribution = new RandomDistributor<MSVehicleType*>();
270:         if (attrs.hasAttribute(SUMO_ATTR_VTYPES)) {
271:             std::vector<double> probs;
272:             if (attrs.hasAttribute(SUMO_ATTR_PROBS)) {
273:                 StringTokenizer st(attrs.get<std::string>(SUMO_ATTR_PROBS, myCurrentVTypeDistributionID.c_str(), ok));
274:                 while (st.hasNext()) {
275:                     probs.push_back(StringUtils::toDoubleSecure(st.next(), 1.0));
276:                 }
277:             }
278:             const std::string vTypes = attrs.get<std::string>(SUMO_ATTR_VTYPES, myCurrentVTypeDistributionID.c_str(), ok);
279:             StringTokenizer st(vTypes);
280:             int probIndex = 0;
281:             while (st.hasNext()) {
282:                 const std::string& vtypeID = st.next();
283:                 const RandomDistributor<MSVehicleType*>* const dist = MSNet::getInstance()->getVehicleControl().getVTypeDistribution(vtypeID);
284:                 if (dist != nullptr) {
285:                     const double distProb = ((int)probs.size() > probIndex ? probs[probIndex] : 1.) / dist->getOverallProb();
286:                     std::vector<double>::const_iterator probIt = dist->getProbs().begin();
287:                     for (MSVehicleType* const type : dist->getVals()) {
288:                         myCurrentVTypeDistribution->add(type, distProb * *probIt);
289:                         probIt++;
290:                     }
291:                 } else {
292:                     MSVehicleType* const type = MSNet::getInstance()->getVehicleControl().getVType(vtypeID, &myParsingRNG);
293:                     if (type == nullptr) {
294:                         throw ProcessError("Unknown vtype '" + vtypeID + "' in distribution '" + myCurrentVTypeDistributionID + "'.");
295:                     }
296:                     const double prob = ((int)probs.size() > probIndex ? probs[probIndex] : type->getDefaultProbability());
297:                     myCurrentVTypeDistribution->add(type, prob);
298:                 }
299:                 probIndex++;
300:             }
301:             if (probs.size() > 0 && probIndex != (int)probs.size()) {
302:                 WRITE_WARNING("Got " + toString(probs.size()) + " probabilities for " + toString(probIndex) +
303:                               " types in vTypeDistribution '" + myCurrentVTypeDistributionID + "'");
304:             }
305:         }
306:     }
307: }
310: void
311: MSRouteHandler::closeVehicleTypeDistribution() {
312:     if (myCurrentVTypeDistribution != nullptr) {
313:         if (MSGlobals::gStateLoaded && MSNet::getInstance()->getVehicleControl().hasVTypeDistribution(myCurrentVTypeDistributionID)) {
314:             myCurrentVTypeDistribution = nullptr;
315:             delete myCurrentVTypeDistribution;
316:             return;
317:         }
318:         if (myCurrentVTypeDistribution->getOverallProb() == 0) {
319:             delete myCurrentVTypeDistribution;
320:             throw ProcessError(TLF("Vehicle type distribution '%' is empty.", myCurrentVTypeDistributionID));
321:         }
322:         if (!MSNet::getInstance()->getVehicleControl().addVTypeDistribution(myCurrentVTypeDistributionID, myCurrentVTypeDistribution)) {
323:             delete myCurrentVTypeDistribution;
324:             throw ProcessError(TLF("Another vehicle type (or distribution) with the id '%' exists.", myCurrentVTypeDistributionID));
325:         }
326:         myCurrentVTypeDistribution = nullptr;
327:     }
328: }
331: void
332: MSRouteHandler::openRoute(const SUMOSAXAttributes& attrs) {
333:     myActiveRoute.clear();
334:     myInsertStopEdgesAt = -1;
336:     std::string rid;
337:     if (myCurrentRouteDistribution != nullptr) {
338:         myActiveRouteID = myCurrentRouteDistributionID + "#" + toString(myCurrentRouteDistribution->getProbs().size()); // !!! document this
339:         rid =  "distribution '" + myCurrentRouteDistributionID + "'";
340:     } else if (myVehicleParameter != nullptr) {
343:         myActiveRouteID = "!" + myVehicleParameter->id; // !!! document this
344:         if (attrs.hasAttribute(SUMO_ATTR_ID)) {
345:             WRITE_WARNINGF(TL("Ids of internal routes are ignored (vehicle '%')."), myVehicleParameter->id);
346:         }
347:     } else {
348:         bool ok = true;
349:         myActiveRouteID = attrs.get<std::string>(SUMO_ATTR_ID, nullptr, ok, false);
350:         if (!ok) {
351:             return;
352:         }
353:         rid = "'" + myActiveRouteID + "'";
354:     }
355:     if (myVehicleParameter != nullptr) { // have to do this here for nested route distributions
356:         rid =  "for vehicle '" + myVehicleParameter->id + "'";
357:     }
358:     bool ok = true;
359:     if (attrs.hasAttribute(SUMO_ATTR_EDGES)) {
360:         MSEdge::parseEdgesList(attrs.get<std::string>(SUMO_ATTR_EDGES, myActiveRouteID.c_str(), ok), myActiveRoute, rid);
361:     }
362:     myActiveRouteRefID = attrs.getOpt<std::string>(SUMO_ATTR_REFID, myActiveRouteID.c_str(), ok, "");
363:     if (myActiveRouteRefID != "" && MSRoute::dictionary(myActiveRouteRefID, &myParsingRNG) == nullptr) {
364:         throw ProcessError(TLF("Invalid reference to route '%' in route %.", myActiveRouteRefID, rid));
365:     }
366:     myActiveRouteProbability = attrs.getOpt<double>(SUMO_ATTR_PROB, myActiveRouteID.c_str(), ok, DEFAULT_VEH_PROB);
367:     myActiveRouteColor = attrs.hasAttribute(SUMO_ATTR_COLOR) ? new RGBColor(attrs.get<RGBColor>(SUMO_ATTR_COLOR, myActiveRouteID.c_str(), ok)) : nullptr;
368:     myActiveRouteRepeat = attrs.getOpt<int>(SUMO_ATTR_REPEAT, myActiveRouteID.c_str(), ok, 0);
369:     myActiveRouteReplacedAtTime = attrs.getOptSUMOTimeReporting(SUMO_ATTR_REPLACED_AT_TIME, myActiveRouteID.c_str(), ok, -1);
370:     myActiveRouteReplacedIndex = attrs.getOpt<int>(SUMO_ATTR_REPLACED_ON_INDEX, myActiveRouteID.c_str(), ok, 0);
371:     myActiveRoutePeriod = attrs.getOptSUMOTimeReporting(SUMO_ATTR_CYCLETIME, myActiveRouteID.c_str(), ok,
373:                           attrs.getOptSUMOTimeReporting(SUMO_ATTR_PERIOD, myActiveRouteID.c_str(), ok, 0));
374:     myActiveRoutePermanent = attrs.getOpt<bool>(SUMO_ATTR_STATE, myActiveRouteID.c_str(), ok, false);
375:     if (attrs.hasAttribute(SUMO_ATTR_PERIOD)) {
376:         WRITE_WARNING(TL("Attribute 'period' is deprecated for route. Use 'cycleTime' instead."));
377:     }
378:     myCurrentCosts = attrs.getOpt<double>(SUMO_ATTR_COST, myActiveRouteID.c_str(), ok, -1);
379:     if (ok && myCurrentCosts != -1 && myCurrentCosts < 0) {
```

### D1. Route and vehicle closure — `microsim/MSRouteHandler.cpp:404-782`

```cpp
404: MSRouteHandler::closeRoute(const bool mayBeDisconnected) {
405:     std::string type = "vehicle";
406:     if (mayBeDisconnected) {
407:         if (myVehicleParameter->repetitionNumber >= 0) {
408:             type = "flow";
409:         } else {
410:             type = "trip";
411:         }
412:     }
414:     try {
415:         const bool mustReroute = myActiveRoute.size() == 0 && myActiveRouteStops.size() != 0;
416:         if (mustReroute) {
418:             for (const SUMOVehicleParameter::Stop& stop : myActiveRouteStops) {
419:                 myActiveRoute.push_back(MSEdge::dictionary(stop.edge));
420:             }
421:         }
422:         if (myActiveRoute.size() == 0) {
423:             delete myActiveRouteColor;
424:             myActiveRouteColor = nullptr;
425:             if (myActiveRouteRefID != "" && myCurrentRouteDistribution != nullptr) {
426:                 ConstMSRoutePtr route = MSRoute::dictionary(myActiveRouteRefID, &myParsingRNG);
427:                 if (route != nullptr) {
428:                     myCurrentRouteDistribution->add(route, myActiveRouteProbability);
429:                 }
430:                 myActiveRouteID = "";
431:                 myActiveRouteRefID = "";
432:                 return;
433:             }
434:             if (myVehicleParameter != nullptr) {
435:                 throw ProcessError("The route for " + type + " '" + myVehicleParameter->id + "' has no edges.");
436:             } else {
437:                 throw ProcessError(TLF("Route '%' has no edges.", myActiveRouteID));
438:             }
439:         }
440:         if (myActiveRoute.size() == 1 && myActiveRoute.front()->isTazConnector()) {
441:             throw ProcessError("The routing information for " + type + " '" + myVehicleParameter->id + "' is insufficient.");
442:         }
443:         if (myActiveRouteRepeat > 0) {
445:             ConstMSEdgeVector tmpEdges = myActiveRoute;
446:             auto tmpStops = myActiveRouteStops;
448:             if (MSGlobals::gCheckRoutes) {
449:                 SUMOVehicleClass vClass = SVC_IGNORING;
450:                 std::string errSuffix = ".";
451:                 if (myVehicleParameter != nullptr) {
452:                     MSVehicleControl& vehControl = MSNet::getInstance()->getVehicleControl();
453:                     MSVehicleType* vtype = vehControl.getVType(myVehicleParameter->vtypeid, &myParsingRNG);
454:                     if (vtype != nullptr) {
455:                         vClass = vtype->getVehicleClass();
456:                         errSuffix = TLF(" for vehicle '%' with vClass %.", myVehicleParameter->id, getVehicleClassNames(vClass));
457:                     }
458:                 }
459:                 if (myActiveRoute.size() > 0 && !myActiveRoute.back()->isConnectedTo(*myActiveRoute.front(), vClass)) {
460:                     if (tmpStops.size() == 0 || tmpStops.back().jump < 0) {
461:                         throw ProcessError(TLF("Disconnected route '%' when repeating. Last edge '%' is not connected to first edge '%'%",
462:                                                myActiveRouteID, myActiveRoute.back()->getID(), myActiveRoute.front()->getID(), errSuffix));
463:                     }
464:                 }
465:             }
466:             for (int i = 0; i < myActiveRouteRepeat; i++) {
467:                 myActiveRoute.insert(myActiveRoute.begin(), tmpEdges.begin(), tmpEdges.end());
468:                 for (SUMOVehicleParameter::Stop stop : tmpStops) {
469:                     if (stop.until > 0) {
470:                         if (myActiveRoutePeriod <= 0) {
471:                             const std::string description = myVehicleParameter != nullptr
472:                                                             ?  "for " + type + " '" + myVehicleParameter->id + "'"
473:                                                             :  "'" + myActiveRouteID + "'";
474:                             throw ProcessError(TLF("Cannot repeat stops with 'until' in route % because no cycleTime is defined.", description));
475:                         }
476:                         stop.until += myActiveRoutePeriod * (i + 1);
477:                     }
478:                     if (stop.arrival > 0) {
479:                         if (myActiveRoutePeriod <= 0) {
480:                             const std::string description = myVehicleParameter != nullptr
481:                                                             ?  "for " + type + " '" + myVehicleParameter->id + "'"
482:                                                             :  "'" + myActiveRouteID + "'";
483:                             throw ProcessError(TLF("Cannot repeat stops with 'arrival' in route % because no cycleTime is defined.", description));
484:                         }
485:                         stop.arrival += myActiveRoutePeriod * (i + 1);
486:                     }
487:                     stop.index = STOP_INDEX_REPEAT;
488:                     myActiveRouteStops.push_back(stop);
489:                 }
490:             }
491:             if (myActiveRouteStops.size() > 0) {
493:                 myActiveRouteStops.back().jump = -1;
494:             }
495:         }
496:         MSRoute* const route = new MSRoute(myActiveRouteID, myActiveRoute,
497:                                            myAmLoadingState ? myActiveRoutePermanent : myVehicleParameter == nullptr,
498:                                            myActiveRouteColor, myActiveRouteStops,
499:                                            myActiveRouteReplacedAtTime, myActiveRouteReplacedIndex);
500:         route->setPeriod(myActiveRoutePeriod);
501:         route->setCosts(myCurrentCosts);
502:         route->setReroute(mustReroute);
503:         myActiveRoute.clear();
504:         ConstMSRoutePtr constRoute = std::shared_ptr<const MSRoute>(route);
505:         if (!MSRoute::dictionary(myActiveRouteID, constRoute)) {
506:             if (!MSGlobals::gStateLoaded) {
507:                 if (myVehicleParameter != nullptr) {
508:                     if (MSNet::getInstance()->getVehicleControl().getVehicle(myVehicleParameter->id) == nullptr) {
509:                         throw ProcessError("Another route for " + type + " '" + myVehicleParameter->id + "' exists.");
510:                     } else {
511:                         throw ProcessError(TLF("A vehicle with id '%' already exists.", myVehicleParameter->id));
512:                     }
513:                 } else {
514:                     throw ProcessError(TLF("Another route (or distribution) with the id '%' exists.", myActiveRouteID));
515:                 }
516:             }
517:         } else {
518:             if (myCurrentRouteDistribution != nullptr) {
519:                 myCurrentRouteDistribution->add(constRoute, myActiveRouteProbability);
520:             }
521:         }
522:         myActiveRouteID = "";
523:         myActiveRouteColor = nullptr;
524:         myActiveRouteStops.clear();
525:         myActiveRouteRepeat = 0;
526:     } catch (ProcessError&) {
527:         deleteActivePlanAndVehicleParameter();
528:         throw;
529:     }
530: }
533: void
534: MSRouteHandler::openRouteDistribution(const SUMOSAXAttributes& attrs) {
536:     if (myVehicleParameter != nullptr) {
539:         myCurrentRouteDistributionID = "!" + myVehicleParameter->id; // !!! document this
541:         myVehicleParameter->routeid = myCurrentRouteDistributionID;
542:     } else {
543:         bool ok = true;
544:         myCurrentRouteDistributionID = attrs.get<std::string>(SUMO_ATTR_ID, nullptr, ok);
545:         if (!ok) {
546:             return;
547:         }
548:     }
549:     myCurrentRouteDistribution = new RandomDistributor<ConstMSRoutePtr>();
550:     std::vector<double> probs;
551:     if (attrs.hasAttribute(SUMO_ATTR_PROBS)) {
552:         bool ok = true;
553:         StringTokenizer st(attrs.get<std::string>(SUMO_ATTR_PROBS, myCurrentRouteDistributionID.c_str(), ok));
554:         while (st.hasNext()) {
555:             probs.push_back(StringUtils::toDoubleSecure(st.next(), 1.0));
556:         }
557:     }
558:     if (attrs.hasAttribute(SUMO_ATTR_ROUTES)) {
559:         bool ok = true;
560:         StringTokenizer st(attrs.get<std::string>(SUMO_ATTR_ROUTES, myCurrentRouteDistributionID.c_str(), ok));
561:         int probIndex = 0;
562:         while (st.hasNext()) {
563:             std::string routeID = st.next();
564:             ConstMSRoutePtr route = MSRoute::dictionary(routeID, &myParsingRNG);
565:             if (route == nullptr) {
566:                 throw ProcessError("Unknown route '" + routeID + "' in distribution '" + myCurrentRouteDistributionID + "'.");
567:             }
568:             const double prob = ((int)probs.size() > probIndex ? probs[probIndex] : 1.0);
569:             myCurrentRouteDistribution->add(route, prob, false);
570:             probIndex++;
571:         }
572:         if (probs.size() > 0 && probIndex != (int)probs.size()) {
573:             WRITE_WARNING("Got " + toString(probs.size()) + " probabilities for " + toString(probIndex) +
574:                           " routes in routeDistribution '" + myCurrentRouteDistributionID + "'");
575:         }
576:     }
577: }
580: void
581: MSRouteHandler::closeRouteDistribution() {
582:     if (myCurrentRouteDistribution != nullptr) {
583:         const bool haveSameID = MSRoute::dictionary(myCurrentRouteDistributionID, &myParsingRNG) != nullptr;
584:         if (MSGlobals::gStateLoaded && haveSameID) {
585:             delete myCurrentRouteDistribution;
586:             myCurrentRouteDistribution = nullptr;
587:             return;
588:         }
589:         if (haveSameID) {
590:             delete myCurrentRouteDistribution;
591:             throw ProcessError(TLF("Another route (or distribution) with the id '%' exists.", myCurrentRouteDistributionID));
592:         }
593:         if (myCurrentRouteDistribution->getOverallProb() == 0) {
594:             delete myCurrentRouteDistribution;
595:             throw ProcessError(TLF("Route distribution '%' is empty.", myCurrentRouteDistributionID));
596:         }
597:         MSRoute::dictionary(myCurrentRouteDistributionID, myCurrentRouteDistribution, myVehicleParameter == nullptr);
598:         myCurrentRouteDistribution = nullptr;
599:     }
600: }
603: void
604: MSRouteHandler::closeVehicle() {
606:     const std::string embeddedRouteID = "!" + myVehicleParameter->id;
607:     ConstMSRoutePtr route = nullptr;
608:     if (myReplayRerouting) {
609:         RandomDistributor<ConstMSRoutePtr>* rDist = MSRoute::distDictionary(embeddedRouteID);
610:         if (rDist != nullptr && rDist->getVals().size() > 0) {
611:             route = rDist->getVals().front();
612:         }
613:     }
614:     if (route == nullptr) {
615:         route = MSRoute::dictionary(embeddedRouteID, &myParsingRNG);
616:     }
617:     MSVehicleControl& vehControl = MSNet::getInstance()->getVehicleControl();
618:     if (myVehicleParameter->departProcedure == DepartDefinition::GIVEN) {
620:         if (!(myAddVehiclesDirectly || checkLastDepart()) || (myVehicleParameter->depart <= MSNet::getInstance()->getStateLoaderTime() && !myAmLoadingState)) {
621:             mySkippedVehicles.insert(myVehicleParameter->id);
622:             return;
623:         }
624:     }
627:     MSVehicleType* vtype = nullptr;
629:     try {
630:         if (myVehicleParameter->vtypeid != "") {
631:             vtype = vehControl.getVType(myVehicleParameter->vtypeid, &myParsingRNG);
632:             if (vtype == nullptr) {
633:                 throw ProcessError("The vehicle type '" + myVehicleParameter->vtypeid + "' for vehicle '" + myVehicleParameter->id + "' is not known.");
634:             }
635:             if (vtype->getVehicleClass() == SVC_PEDESTRIAN) {
636:                 WRITE_WARNINGF(TL("Vehicle type '%' with vClass=pedestrian should only be used for persons and not for vehicle '%'."), vtype->getID(), myVehicleParameter->id);
637:             }
638:         } else {
640:             vtype = vehControl.getVType(DEFAULT_VTYPE_ID, &myParsingRNG);
641:         }
642:         if (myVehicleParameter->wasSet(VEHPARS_ROUTE_SET)) {
644:             if (route != nullptr && !myAmLoadingState) {
645:                 WRITE_WARNINGF(TL("Ignoring child element 'route' for vehicle '%' because attribute 'route' is set."), myVehicleParameter->id);
646:             }
647:             route = MSRoute::dictionary(myVehicleParameter->routeid, &myParsingRNG);
648:         }
649:         if (route == nullptr) {
651:             if (myVehicleParameter->routeid != "") {
652:                 throw ProcessError("The route '" + myVehicleParameter->routeid + "' for vehicle '" + myVehicleParameter->id + "' is not known.");
653:             } else {
654:                 throw ProcessError(TLF("Vehicle '%' has no route.", myVehicleParameter->id));
655:             }
656:         }
657:         myActiveRouteID = "";
659:     } catch (ProcessError&) {
660:         deleteActivePlanAndVehicleParameter();
661:         throw;
662:     }
663:     if (route->mustReroute()) {
664:         myVehicleParameter->parametersSet |= VEHPARS_FORCE_REROUTE;
665:         if (myVehicleParameter->stops.size() > 0) {
666:             route = addVehicleStopsToImplicitRoute(route, false);
667:         }
668:     }
669:     if (myVehicleParameter->departEdgeProcedure != RouteIndexDefinition::DEFAULT) {
670:         if ((myVehicleParameter->parametersSet & VEHPARS_FORCE_REROUTE) == 0 &&
671:                 myVehicleParameter->departEdgeProcedure == RouteIndexDefinition::GIVEN &&
672:                 myVehicleParameter->departEdge >= (int)route->getEdges().size()) {
673:             throw ProcessError("Vehicle '" + myVehicleParameter->id + "' has invalid departEdge index "
674:                                + toString(myVehicleParameter->departEdge) + " for route with " + toString(route->getEdges().size()) + " edges.");
675:         }
676:     }
677:     if (myVehicleParameter->arrivalEdgeProcedure != RouteIndexDefinition::DEFAULT) {
678:         if ((myVehicleParameter->parametersSet & VEHPARS_FORCE_REROUTE) == 0 &&
679:                 myVehicleParameter->arrivalEdgeProcedure == RouteIndexDefinition::GIVEN &&
680:                 myVehicleParameter->arrivalEdge >= (int)route->getEdges().size()) {
681:             throw ProcessError("Vehicle '" + myVehicleParameter->id + "' has invalid arrivalEdge index "
682:                                + toString(myVehicleParameter->arrivalEdge) + " for route with " + toString(route->getEdges().size()) + " edges.");
683:         }
684:     }
687:     SUMOVehicle* vehicle = nullptr;
688:     if (vehControl.getVehicle(myVehicleParameter->id) == nullptr) {
689:         MSVehicleControl::VehicleDefinitionSource source = (myAmLoadingState) ? MSVehicleControl::VehicleDefinitionSource::STATE : MSVehicleControl::VehicleDefinitionSource::ROUTEFILE;
690:         try {
691:             vehicle = vehControl.buildVehicle(myVehicleParameter, route, vtype, !MSGlobals::gCheckRoutes, source, !myAmLoadingState);
692:         } catch (const ProcessError& e) {
693:             myVehicleParameter = nullptr;
694:             if (!MSGlobals::gCheckRoutes) {
695:                 WRITE_WARNING(e.what());
696:                 vehControl.deleteVehicle(vehicle, true);
697:                 myVehicleParameter = nullptr;
698:                 vehicle = nullptr;
699:                 return;
700:             } else {
701:                 throw;
702:             }
703:         }
704:         const SUMOTime origDepart = myVehicleParameter->depart;
706:         int quota = myAmLoadingState ? 1 : vehControl.getQuota(vehControl.getScale() * vtype->getParameter().scale);
707:         if (quota > 0) {
708:             registerLastDepart();
709:             myVehicleParameter->depart += MSNet::getInstance()->getInsertionControl().computeRandomDepartOffset();
710:             vehControl.addVehicle(myVehicleParameter->id, vehicle);
711:             if (myReplayRerouting) {
712:                 RandomDistributor<ConstMSRoutePtr>* rDist = MSRoute::distDictionary(embeddedRouteID);
713:                 if (rDist != nullptr) {
714:                     for (int i = 0; i < (int)rDist->getVals().size() - 1; i++) {
715:                         SUMOTime replacedAt = rDist->getVals()[i]->getReplacedTime();
716:                         auto* cmd = new Command_RouteReplacement(vehicle->getID(), rDist->getVals()[i + 1]);
717:                         if (replacedAt >= 0 && replacedAt == myVehicleParameter->depart) {
719:                             MSNet::getInstance()->getEndOfTimestepEvents()->addEvent(cmd, replacedAt);
720:                         } else {
721:                             MSNet::getInstance()->getBeginOfTimestepEvents()->addEvent(cmd, replacedAt);
722:                         }
723:                     }
724:                 }
725:             }
726:             int offset = 0;
727:             for (int i = 1; i < quota; i++) {
728:                 if (vehicle->getParameter().departProcedure == DepartDefinition::GIVEN || vehicle->getParameter().departProcedure == DepartDefinition::BEGIN) {
729:                     MSNet::getInstance()->getInsertionControl().add(vehicle);
730:                 }
731:                 SUMOVehicleParameter* newPars = new SUMOVehicleParameter(*myVehicleParameter);
732:                 newPars->id = myVehicleParameter->id + myScaleSuffix + toString(i + offset);
733:                 while (vehControl.getVehicle(newPars->id) != nullptr) {
734:                     offset += 1;
735:                     newPars->id = myVehicleParameter->id + myScaleSuffix + toString(i + offset);
736:                 }
737:                 newPars->depart = origDepart + MSNet::getInstance()->getInsertionControl().computeRandomDepartOffset();
738:                 if (vehControl.hasVTypeDistribution(myVehicleParameter->vtypeid)) {
740:                     vtype = vehControl.getVType(myVehicleParameter->vtypeid, &myParsingRNG);
741:                 }
742:                 vehicle = vehControl.buildVehicle(newPars, route, vtype, !MSGlobals::gCheckRoutes, source, !myAmLoadingState);
743:                 vehControl.addVehicle(newPars->id, vehicle);
744:             }
745:             myVehicleParameter = nullptr;
746:         } else {
747:             vehControl.deleteVehicle(vehicle, true);
748:             myVehicleParameter = nullptr;
749:             vehicle = nullptr;
750:         }
751:     } else {
753:         if (!MSGlobals::gStateLoaded) {
756:             std::string veh_id = myVehicleParameter->id;
757:             deleteActivePlanAndVehicleParameter();
758:             std::string scaleWarning = "";
759:             if (vehControl.getScale() * vtype->getParameter().scale > 1 && veh_id.find(myScaleSuffix) != std::string::npos) {
760:                 scaleWarning = "\n   (Possibly duplicate id due to using option --scale. Set option --scale-suffix to prevent this)";
761:             }
762:             throw ProcessError("Another vehicle with the id '" + veh_id + "' exists." + scaleWarning);
763:         } else {
765:             vehicle = nullptr;
766:         }
767:     }
770:     if (vehicle != nullptr) {
771:         if (vehicle->getParameter().departProcedure == DepartDefinition::GIVEN || vehicle->getParameter().departProcedure == DepartDefinition::BEGIN) {
772:             MSNet::getInstance()->getInsertionControl().add(vehicle);
773:         }
774:     }
775: }
778: ConstMSRoutePtr
779: MSRouteHandler::addVehicleStopsToImplicitRoute(ConstMSRoutePtr route, bool isPermanent) {
```

### D1. Flow and trip closure — `microsim/MSRouteHandler.cpp:986-1104`

```cpp
986: MSRouteHandler::closeVType() {
987:     MSVehicleType* vehType = nullptr;
988:     if (myCurrentVTypeRef.empty()) {
989:         vehType = MSVehicleType::build(*myCurrentVType, getFileName());
990:         vehType->check();
991:         if (!MSNet::getInstance()->getVehicleControl().addVType(vehType)) {
992:             const std::string id = vehType->getID();
993:             delete vehType;
994:             if (!MSGlobals::gStateLoaded) {
995:                 throw ProcessError(TLF("Another vehicle type (or distribution) with the id '%' exists.", id));
996:             }
997:         }
998:     }
999:     if (myCurrentVTypeDistribution != nullptr) {
1000:         if (!myCurrentVTypeRef.empty()) {
1001:             const RandomDistributor<MSVehicleType*>* const dist = MSNet::getInstance()->getVehicleControl().getVTypeDistribution(myCurrentVTypeRef);
1002:             if (dist != nullptr) {
1003:                 const double distProb = (myCurrentVTypeProbability >= 0 ? myCurrentVTypeProbability : 1) / dist->getOverallProb();
1004:                 std::vector<double>::const_iterator probIt = dist->getProbs().begin();
1005:                 for (MSVehicleType* const type : dist->getVals()) {
1006:                     myCurrentVTypeDistribution->add(type, distProb * *probIt);
1007:                     probIt++;
1008:                 }
1009:                 return;
1010:             } else {
1011:                 vehType = MSNet::getInstance()->getVehicleControl().getVType(myCurrentVTypeRef);
1012:             }
1013:         }
1014:         double probability = myCurrentVTypeProbability >= 0 ? myCurrentVTypeProbability : vehType->getDefaultProbability();
1015:         myCurrentVTypeDistribution->add(vehType, probability);
1016:     }
1017: }
1020: void
1021: MSRouteHandler::closeFlow() {
1022:     myInsertStopEdgesAt = -1;
1023:     if (myVehicleParameter->repetitionNumber == 0) {
1024:         delete myVehicleParameter;
1025:         myVehicleParameter = nullptr;
1026:         return;
1027:     }
1029:     myVehicleParameter->repetitionsDone = 0;
1030:     if (myVehicleParameter->repetitionProbability < 0) {
1031:         const SUMOTime offsetToBegin = string2time(OptionsCont::getOptions().getString("begin")) - myVehicleParameter->depart;
1032:         while (myVehicleParameter->repetitionTotalOffset < offsetToBegin) {
1033:             myVehicleParameter->incrementFlow(1, &myParsingRNG);
1034:             if (myVehicleParameter->repetitionsDone == myVehicleParameter->repetitionNumber) {
1035:                 delete myVehicleParameter;
1036:                 myVehicleParameter = nullptr;
1037:                 return;
1038:             }
1039:         }
1040:     }
1041:     if (MSNet::getInstance()->getVehicleControl().getVType(myVehicleParameter->vtypeid, &myParsingRNG) == nullptr) {
1042:         throw ProcessError("The vehicle type '" + myVehicleParameter->vtypeid + "' for flow '" + myVehicleParameter->id + "' is not known.");
1043:     }
1044:     if (myVehicleParameter->routeid[0] == '!' && MSRoute::dictionary(myVehicleParameter->routeid, &myParsingRNG) == nullptr) {
1045:         myVehicleParameter->parametersSet |= VEHPARS_FORCE_REROUTE;
1046:         closeRoute(true);
1047:     }
1048:     ConstMSRoutePtr route = MSRoute::dictionary(myVehicleParameter->routeid, &myParsingRNG);
1049:     if (route == nullptr) {
1050:         throw ProcessError("The route '" + myVehicleParameter->routeid + "' for flow '" + myVehicleParameter->id + "' is not known.");
1051:     }
1052:     if (route->mustReroute()) {
1053:         myVehicleParameter->parametersSet |= VEHPARS_FORCE_REROUTE;
1054:         if (myVehicleParameter->stops.size() > 0) {
1055:             route = addVehicleStopsToImplicitRoute(route, true);
1056:             myVehicleParameter->routeid = route->getID();
1057:         }
1058:     }
1059:     if (myVehicleParameter->departEdgeProcedure != RouteIndexDefinition::DEFAULT) {
1060:         if ((myVehicleParameter->parametersSet & VEHPARS_FORCE_REROUTE) == 0 &&
1061:                 myVehicleParameter->departEdgeProcedure == RouteIndexDefinition::GIVEN &&
1062:                 myVehicleParameter->departEdge >= (int)route->getEdges().size()) {
1063:             throw ProcessError("Flow '" + myVehicleParameter->id + "' has invalid departEdge index "
1064:                                + toString(myVehicleParameter->departEdge) + " for route with " + toString(route->getEdges().size()) + " edges.");
1065:         }
1066:     }
1067:     if (myVehicleParameter->arrivalEdgeProcedure != RouteIndexDefinition::DEFAULT) {
1068:         if ((myVehicleParameter->parametersSet & VEHPARS_FORCE_REROUTE) == 0 &&
1069:                 myVehicleParameter->arrivalEdgeProcedure == RouteIndexDefinition::GIVEN &&
1070:                 myVehicleParameter->arrivalEdge >= (int)route->getEdges().size()) {
1071:             throw ProcessError("Flow '" + myVehicleParameter->id + "' has invalid arrivalEdge index "
1072:                                + toString(myVehicleParameter->arrivalEdge) + " for route with " + toString(route->getEdges().size()) + " edges.");
1073:         }
1074:     }
1075:     myActiveRouteID = "";
1079:     if (myAddVehiclesDirectly || checkLastDepart()) {
1080:         if (MSNet::getInstance()->getInsertionControl().addFlow(myVehicleParameter)) {
1081:             registerLastDepart();
1082:         } else {
1083:             if (MSGlobals::gStateLoaded) {
1084:                 delete myVehicleParameter;
1085:             } else {
1086:                 throw ProcessError(TLF("Another flow with the id '%' exists.", myVehicleParameter->id));
1087:             }
1088:         }
1089:     }
1090:     myVehicleParameter = nullptr;
1091: }
1094: void
1095: MSRouteHandler::closeTrip() {
1096:     myVehicleParameter->parametersSet |= VEHPARS_FORCE_REROUTE;
1097:     closeRoute(true);
1098:     closeVehicle();
1099: }
1101: void
1102: MSRouteHandler::addRide(const SUMOSAXAttributes& attrs) {
1103:     addRideOrTransport(attrs, SUMO_TAG_RIDE);
1104: }
```

### D4. Scenario descriptions — `../docs/web/docs/Data/Scenarios.md:1-141`

```cpp
1: ---
2: title: Scenarios
3: ---
5: # We need your Help!
7: Building a scenario is a lot of work. If you have built a SUMO scenario
8: you can share (under a sufficiently open license), please
9: [contact us](../Contact.md).
11: # Alicante-Murcia highway scenario
12: Large-scale and high-accuracy traffic simulation scenario that models 9 full days of traffic over a 97 km freeway section, with mixed traffic (light and heavy vehicles). The simulation scenario has been calibrated using a unique dataset provided by the Spanish road authority and a novel learning-based and iterative traffic demand calibration technique for SUMO.
14: More info at: https://github.com/msepulcre/Alicante-Murcia-SUMO-Scenario
16: # Berlin
18: - [Mosaic Berlin Sumo Traffic (BeST) Scenario on GitHub](https://github.com/mosaic-addons/best-scenario)
20: # Bologna
22: A small-scale scenario based on the city of Bologna. The large
23: roundabout can be found at 44.494554,11.314393. These scenarios were
24: developed as part of the [iTETRIS project](https://www.ict-itetris.eu). A
25: [publication](https://elib.dlr.de/89354) on these scenarios was presented
26: at [SUMO
27: Conference 2014](https://sumo.dlr.de/docs/Publications.html#SUMO_2014): L.
28: Bieker, D. Krajzewicz, A. Morra, C. Michelacci and F. Cartolano,
29: "Traffic simulation for all: a real world traffic scenario from the city
30: of Bologna", SUMO2014, p 19-26
32: - [Bologna Scenario on GitHub](https://github.com/DLR-TS/sumo-scenarios/tree/main/bologna/)
33: - (Old release) [Download .zip files from SourceForge](https://sourceforge.net/projects/sumo/files/traffic_data/scenarios/Bologna_small)
35: # Braunschweig
37: - [Brunswick Scenario on GitHub](https://github.com/DLR-TS/sumo-scenarios/tree/main/brunswick)
39: # Dublin - Irish Motorway, National road and city centre
41: - [Main Page](https://github.com/maxime-gueriau/ITSC2020_CAV_impact)
42: - Publication: Quantifying the impact of connected and autonomous vehicles on traffic efficiency and safety in mixed traffic" by Maxime Gueriau and Ivana Dusparic, presented at the 23rd IEEE International Conference on Intelligent Transportation Systems (ITSC 2020)
44: # Geneva - Digital Twin - Geneva Motorway (DT-GM)
46: - [Repository](https://github.com/SiLab-group/DigitalTwin_GenevaMotorway)
48: Everyone (after registering at ODPMS) can get access to fine-grained (minute resolution) real-time traffic data from traffic counters and use it as input in DT-GM.
49: The details of modelling and results will also be publicly available in two papers, which for the moment we only mentioned in the README file since they are under review process. (if need it we can provide you preprint of the paper "Building a Motorway Digital Twin in SUMO: Real-Time Simulation of Continuous Data Stream from Traffic Counters")
51: # Ingolstadt traffic scenario
52: ## InTAS
54: - [Main Page](https://github.com/silaslobo/InTAS)
55: - [Presentation video](https://www.youtube.com/watch?v=UgPeBxXzDHc)
57: ## SUMO Ingolstadt
58: Created in the SAVe:, SAVeNoW and KIVI research projects
59: - [Main Page](https://github.com/TUM-VT/sumo_ingolstadt)
61: # Luxembourg SUMO Traffic (LuST)
63: - [Main Page](https://github.com/lcodeca/LuSTScenario)
64: - [Releases](https://github.com/lcodeca/LuSTScenario/releases)
65: - [Documentation](https://github.com/lcodeca/LuSTScenario/blob/master/docs/LuSTDocumentation.md)
66: - Publication: Lara CODECA, Raphael FRANK, Thomas ENGEL. December 2015. Luxembourg SUMO Traffic (LuST) Scenario: 24 Hours of Mobility
67: for Vehicular Networking Research in Proceedings of the 7th IEEE
68: Vehicular Networking Conference (VNC15).
70: # Monaco SUMO Traffic (MoST)
72: - [Main Page](https://github.com/lcodeca/MoSTScenario)
73: - [Releases](https://github.com/lcodeca/MoSTScenario/releases)
74: - Publication: L. Codeca, J. Härri, "Towards Multimodal Mobility
75: Simulation of C-ITS: The Monaco SUMO Traffic Scenario" VNC 2017,
76: IEEE Vehicular Networking Conference November 27-29, 2017, Torino,
77: Italy.
79: # Stuttgart Open Motorway Project (STOMP)
81: - [Main Page](https://github.com/boschresearch/stuttgart-sumo-traffic-scenario)
82: - Publication: David Förster, Hans Löhr, Anne Grätz, Jonathan Petit, and Frank Kargl, "An Evaluation of Pseudonym Changes for Vehicular Networks in Large-scale, Realistic Traffic Scenarios", IEEE Transactions on Intelligent Transportation Systems 19.10 (2017): 3400-3405, doi: [10.1109/TITS.2017.2775519](https://doi.org/10.1109/TITS.2017.2775519).
84: # Toronto
86: - [**TorontoSUMONetworks on GitHub**](https://github.com/Jahandad-Baloch/TorontoSUMONetworks)
88: TorontoSUMONetworks is an open-source platform designed for creating, manipulating, and simulating traffic networks in Toronto using SUMO. This tool provides a realistic simulation environment for transportation research, urban planning, and traffic management. Its flexibility makes it valuable for diverse research areas, including Intelligent Transportation Systems (ITS), Reinforcement Learning for Adaptive Traffic Signal Control (ATSC), and more.
90: Key Features:
91: - Realistic traffic simulations based on the Toronto network, including major arterials and local streets.
92: - Multi-modal transportation support, simulating private vehicles, buses, bicycles, and pedestrians.
93: - Utilizes real-world data from the City of Toronto Open Data Portal for accurate simulations.
94: - Highly configurable, supporting detectors like inductionloop, lanearea, and multi-entry/exit for traffic management.
96: This project offers a comprehensive platform for researchers, urban planners, and engineers aiming to improve urban mobility and optimize traffic systems through advanced simulation and analysis.
98: # Turin SUMO Traffic (TuST)
99: A large-scale mesoscopic traffic simulation of a 600-sqkm area around the Municipality of Turin.
101: - [Main Page](https://github.com/marcorapelli/TuSTScenario)
102: - Publications:
103:   - M. Rapelli, C. Casetti and G. Gagliardi, “Vehicular Traffic Simulation in the City of Turin from Raw Data” in IEEE Transactions on Mobile Computing, April 2021. DOI: 10.1109/TMC.2021.3075985 [pre-print](https://ieeexplore.ieee.org/document/9416842)
104:   - M. Rapelli, C. Casetti and G. Gagliardi, "TuST: from Raw Data to Vehicular Traffic Simulation in Turin," 2019 IEEE/ACM 23rd International Symposium on Distributed Simulation and Real Time Applications (DS-RT), Cosenza, Italy, 2019, pp. 1-8, doi: 10.1109/DS-RT47707.2019.8958652. [pre-print](https://ieeexplore.ieee.org/document/8958652)
106: !!! note
107:     It requires [git-lfs](https://git-lfs.github.com/) to download
109: ![TuST.png](../images/TuST.gif "TuST")
111: # TAPASCologne
113: ![ssnap_TapasCologne_0.1.gif](../images/Ssnap_TapasCologne_0.1.gif
114: "TAPAS Cologne")
115: The "TAPAS Cologne" simulation scenario
116: describes the traffic within the city of Cologne, Germany for a whole
117: day. The original demand data stems from TAPAS, a system which computes
118: mobility wishes for an area population generated based on information
119: about travelling habits of Germans and on information about the
120: infrastructure of the area they live in.
122: More information about the system can be found within this [publication
123: on TAPAS](https://elib.dlr.de/45058/02/SRL_81_-_Beitrag_Varschen.pdf).
124: The original data was using a closed-source road network and was mapped
125: onto one stemming from the [OpenStreetMap
126: project](https://www.openstreetmap.de/).
128: There is further information about
129: [TAPASCologne](../Data/Scenarios/TAPASCologne.md).
131: # TAVF-Hamburg
133: A scenario from the [TAVF](https://new-mobility-solutions.de/en/tavf/) test track for automated and
134: connected driving in Hamburg.
136: - [TAVF-Hamburg Scenario on GitHub](https://github.com/DLR-TS/sumo-scenarios/tree/main/TAVF-Hamburg)
138: # Boston, Lisbon, Los Angeles, Rio de Janeiro, San Francisco
140: [SUMO simulation files for running 24h of car traffic in five large-scale cities](https://www.research-collection.ethz.ch/handle/20.500.11850/584669)
```

### D4. TAPAS package — `../docs/web/docs/Data/Scenarios/TAPASCologne.md:25-83`

```cpp
25: The "TAPAS Cologne" simulation scenario describes the traffic within the
26: city of Cologne (Germany) for a whole day. The original demand data
27: stems from TAPAS, a system which computes mobility wishes for an area
28: population generated based on information about travelling habits of
29: Germans and on information about the infrastructure of the area they
30: live in. More information about the system can be found within this
31: [publication on
32: TAPAS](https://elib.dlr.de/45058/02/SRL_81_-_Beitrag_Varschen.pdf). The
33: original data was using a closed-source road network and was mapped onto
34: one stemming from the [OpenStreetMap
35: project](https://www.openstreetmap.de/).
37: As is, TAPASCologne is only hardly usable. Work must be put into
38: improving the network quality, as well as into verification of the
39: process how routes were mapped on the OSM network and on the routes
40: themselves. We hope to gain participants responsible for the works that
41: must be done. A list of possible [work packages on
42: TAPASCologne](#next_steps) is available.
44: ### Contents
46: The TAPASCologne scenario package includes:
48: - Road networks imported from OSM
49: - POIs and Polygons imported from OSM
50: - The mapped trips for time between 6:00 and 8:00 (am)
51: - The mapped trips for time between 00:00 and 24:00 (in a separate file)
52: - The SUMO-configuration file
54: As OSM data contains information about streets, railways, ways for
55: pedestrians only, etc. Release 0.0.3 only includes the network for road
56: vehicles (road). Other network selections can be created with the script
57: build.py in the release.
59: - "passenger_\*" which contains only roads passenger vehicles are
60:   allowed to use
61: - "roadvehicles_\*" which contains roads for road vehicles (those
62:   used by pedestrians, trains, and bicycles were removed)
63: - "all_\*" which contains all roads
65: The idea behind this is to have a fast road network ("passenger_\*")
66: for DUA computation and for scenarios which only consider passenger
67: traffic retrieved by TAPAS. Then, in a second step, which is not yet
68: started, additional traffic such as public transport or delivery
69: vehicles may be added and used in combination with "roadvehicles_\*"
70: networks. "all_\*" networks are meant to be used by people who want it
71: all......
73: Each of the road networks is again available in two versions - one with
74: internal lanes (default since version 0.10.1) and one without. Again,
75: choosing the proper network is a matter of personal interest.
77: The supplied routes are given for the "passenger_\*"-network. Though
78: not tested, yet, we assume that they can not be used directly with other
79: networks from the package. Still, computing correct routes should be
80: possible by starting [duarouter](../../duarouter.md) with the
81: appropriate network and **--repair** option.
83: The following images show the scenario area with polygons and points of
```

### B1. Free lane selectors — `microsim/MSEdge.cpp:571-599`

```cpp
571: MSEdge::getFreeLane(const std::vector<MSLane*>* allowed, const SUMOVehicleClass vclass, double departPos) const {
572:     if (allowed == nullptr) {
573:         allowed = allowedLanes(vclass);
574:     }
575:     MSLane* res = nullptr;
576:     if (allowed != nullptr) {
577:         double largestGap = 0;
578:         MSLane* resByGap = nullptr;
579:         double leastOccupancy = std::numeric_limits<double>::max();
580:         for (std::vector<MSLane*>::const_iterator i = allowed->begin(); i != allowed->end(); ++i) {
581:             const double occupancy = (*i)->getBruttoOccupancy();
582:             if (occupancy < leastOccupancy) {
583:                 res = (*i);
584:                 leastOccupancy = occupancy;
585:             }
586:             const MSVehicle* last = (*i)->getLastFullVehicle();
587:             const double lastGap = (last != nullptr ? last->getPositionOnLane() : myLength) - departPos;
588:             if (lastGap > largestGap) {
589:                 largestGap = lastGap;
590:                 resByGap = (*i);
591:             }
592:         }
593:         if (resByGap != nullptr) {
595:             res = resByGap;
596:         }
597:     }
598:     return res;
599: }
```

### B1. Free lane selectors — `microsim/MSEdge.cpp:603-637`

```cpp
603: MSEdge::getProbableLane(const std::vector<MSLane*>* allowed, const SUMOVehicleClass vclass, double departPos, double maxSpeed) const {
604:     if (allowed == nullptr) {
605:         allowed = allowedLanes(vclass);
606:     }
607:     MSLane* res = nullptr;
608:     if (allowed != nullptr) {
609:         double largestGap = 0;
610:         double largestSpeed = 0;
611:         MSLane* resByGap = nullptr;
612:         double leastOccupancy = std::numeric_limits<double>::max();
613:         int aIndex = 0;
614:         for (std::vector<MSLane*>::const_iterator i = allowed->begin(); i != allowed->end(); ++i, aIndex++) {
615:             const double occupancy = (*i)->getBruttoOccupancy();
616:             if (occupancy < leastOccupancy) {
617:                 res = (*i);
618:                 leastOccupancy = occupancy;
619:             }
620:             const MSVehicle* last = (*i)->getLastFullVehicle();
621:             double lastGap = (last != nullptr ? last->getPositionOnLane() : myLength) - departPos;
623:             if (lastGap > largestGap && maxSpeed >= largestSpeed) {
624:                 largestGap = lastGap;
625:                 resByGap = (*i);
626:             }
627:             if (last != nullptr) {
628:                 largestSpeed = MAX2(largestSpeed, getVehicleMaxSpeed(last));
629:             }
630:         }
631:         if (resByGap != nullptr) {
633:             res = resByGap;
634:         }
635:     }
636:     return res;
637: }
```

### B3. Flow timing — `utils/vehicle/SUMOVehicleParameter.cpp:1108-1121`

```cpp
1108: SUMOVehicleParameter::incrementFlow(double scale, SumoRNG* rng) {
1109:     repetitionsDone++;
1111:     if (repetitionProbability < 0) {
1112:         if (repetitionOffset >= 0) {
1113:             repetitionTotalOffset += (SUMOTime)((double)repetitionOffset / scale);
1114:         } else {
1115:             assert(poissonRate > 0);
1117:             const double r = RandHelper::randExp(poissonRate, rng);
1118:             repetitionTotalOffset += TIME2STEPS(r / scale);
1119:         }
1120:     }
1121: }
```

### B3. Flow XML parsing — `utils/vehicle/SUMOVehicleParserHelper.cpp:56-329`

```cpp
56: SUMOVehicleParserHelper::parseFlowAttributes(SumoXMLTag tag, const SUMOSAXAttributes& attrs, const bool hardFail, const bool needID,
57:         const SUMOTime beginDefault, const SUMOTime endDefault, const bool allowInternalRoutes) {
59:     const std::string id = attrs.hasAttribute(SUMO_ATTR_ID) ? parseID(attrs, tag) : "";
61:     if (!needID || !id.empty()) {
62:         if (needID && !SUMOXMLDefinitions::isValidVehicleID(id)) {
63:             return handleVehicleError(hardFail, nullptr, "Invalid flow id '" + id + "'.");
64:         }
66:         const bool hasPeriod = attrs.hasAttribute(SUMO_ATTR_PERIOD);
67:         const bool hasVPH = attrs.hasAttribute(SUMO_ATTR_VEHSPERHOUR);
68:         const bool hasPPH = attrs.hasAttribute(SUMO_ATTR_PERSONSPERHOUR);
69:         const bool hasCPH = attrs.hasAttribute(SUMO_ATTR_CONTAINERSPERHOUR);
70:         const bool hasPH = attrs.hasAttribute(SUMO_ATTR_PERHOUR);
71:         const bool hasXPH = hasVPH || hasPPH || hasCPH || hasPH;
72:         const bool hasProb = attrs.hasAttribute(SUMO_ATTR_PROB);
73:         const bool hasNumber = attrs.hasAttribute(SUMO_ATTR_NUMBER);
74:         const bool hasBegin = attrs.hasAttribute(SUMO_ATTR_BEGIN);
75:         const bool hasEnd = attrs.hasAttribute(SUMO_ATTR_END);
76:         SumoXMLAttr PERHOUR = SUMO_ATTR_PERHOUR;
77:         if (hasVPH) {
78:             PERHOUR = SUMO_ATTR_VEHSPERHOUR;
79:         }
80:         if (hasPPH) {
81:             PERHOUR = SUMO_ATTR_PERSONSPERHOUR;
82:         }
83:         if (hasCPH) {
84:             PERHOUR = SUMO_ATTR_CONTAINERSPERHOUR;
85:         }
86:         if (hasXPH && !(hasVPH ^ hasPPH ^ hasCPH ^ hasPH)) {
87:             return handleVehicleError(hardFail, nullptr,
88:                                       "At most one of '" + attrs.getName(SUMO_ATTR_PERHOUR) +
89:                                       "', '" + attrs.getName(SUMO_ATTR_VEHSPERHOUR) +
90:                                       "', '" + attrs.getName(SUMO_ATTR_PERSONSPERHOUR) +
91:                                       "' and '" + attrs.getName(SUMO_ATTR_CONTAINERSPERHOUR) +
92:                                       "' has to be given in the definition of " + toString(tag) + " '" + id + "'.");
93:         }
94:         if (hasPeriod && hasXPH) {
95:             return handleVehicleError(hardFail, nullptr,
96:                                       "At most one of '" + attrs.getName(SUMO_ATTR_PERIOD) +
97:                                       "' and '" + attrs.getName(PERHOUR) +
98:                                       "' has to be given in the definition of "
99:                                       + toString(tag) + " '" + id + "'.");
100:         }
101:         if (hasPeriod && hasProb) {
102:             return handleVehicleError(hardFail, nullptr,
103:                                       "At most one of '" + attrs.getName(SUMO_ATTR_PERIOD) +
104:                                       "' and '" + attrs.getName(SUMO_ATTR_PROB) +
105:                                       "' has to be given in the definition of "
106:                                       + toString(tag) + " '" + id + "'.");
107:         }
108:         if (hasProb && hasXPH) {
109:             return handleVehicleError(hardFail, nullptr,
110:                                       "At most one of '" + attrs.getName(SUMO_ATTR_PROB) +
111:                                       "' and '" + attrs.getName(PERHOUR) +
112:                                       "' has to be given in the definition of "
113:                                       + toString(tag) + " '" + id + "'.");
114:         }
115:         if (hasPeriod || hasXPH || hasProb) {
116:             if (hasEnd && hasNumber) {
117:                 return handleVehicleError(hardFail, nullptr,
118:                                           "If '" + attrs.getName(SUMO_ATTR_PERIOD) +
119:                                           "', '" + attrs.getName(SUMO_ATTR_VEHSPERHOUR) +
120:                                           "', '" + attrs.getName(SUMO_ATTR_PERSONSPERHOUR) +
121:                                           "', '" + attrs.getName(SUMO_ATTR_CONTAINERSPERHOUR) +
122:                                           "', '" + attrs.getName(SUMO_ATTR_PERHOUR) +
123:                                           "' or '" + attrs.getName(SUMO_ATTR_PROB) +
124:                                           "' are given at most one of '" + attrs.getName(SUMO_ATTR_END) +
125:                                           "' and '" + attrs.getName(SUMO_ATTR_NUMBER) +
126:                                           "' are allowed in "
127:                                           + toString(tag) + " '" + id + "'.");
128:             }
129:         } else {
130:             if (!hasNumber) {
131:                 return handleVehicleError(hardFail, nullptr,
132:                                           "At least one of '" + attrs.getName(SUMO_ATTR_PERIOD) +
133:                                           "', '" + attrs.getName(SUMO_ATTR_VEHSPERHOUR) +
134:                                           "', '" + attrs.getName(SUMO_ATTR_PERSONSPERHOUR) +
135:                                           "', '" + attrs.getName(SUMO_ATTR_CONTAINERSPERHOUR) +
136:                                           "', '" + attrs.getName(SUMO_ATTR_PERHOUR) +
137:                                           "', '" + attrs.getName(SUMO_ATTR_PROB) +
138:                                           "', and '" + attrs.getName(SUMO_ATTR_NUMBER) +
139:                                           "' is needed in "
140:                                           + toString(tag) + " '" + id + "'.");
141:             }
142:         }
144:         SUMOVehicleParameter* flowParameter = new SUMOVehicleParameter();
146:         flowParameter->tag = tag;
148:         flowParameter->id = id;
149:         if (tag == SUMO_TAG_PERSONFLOW) {
150:             flowParameter->vtypeid = DEFAULT_PEDTYPE_ID;
151:         }
152:         if (tag == SUMO_TAG_CONTAINERFLOW) {
153:             flowParameter->vtypeid = DEFAULT_CONTAINERTYPE_ID;
154:         }
156:         try {
157:             parseCommonAttributes(attrs, flowParameter, tag, allowInternalRoutes);
158:         } catch (ProcessError& attributeError) {
160:             if (hardFail) {
161:                 throw ProcessError(attributeError.what());
162:             } else {
163:                 return nullptr;
164:             }
165:         }
167:         bool poissonFlow = false;
168:         if (hasPeriod) {
169:             bool ok = true;
170:             const std::string description = attrs.get<std::string>(SUMO_ATTR_PERIOD, id.c_str(), ok);
171:             const std::string distName = description.substr(0, description.find('('));
172:             if (distName == "exp") {
174:                 double rate = -1;
176:                 try {
177:                     rate = StringUtils::toDouble(description.substr(distName.size() + 1, description.size() - distName.size() - 2));
178:                 } catch (ProcessError& attributeError) {
180:                     if (hardFail) {
181:                         throw ProcessError(attributeError.what());
182:                     } else {
183:                         return nullptr;
184:                     }
185:                 }
186:                 if (rate <= 0) {
187:                     return handleVehicleError(hardFail, flowParameter, "Invalid rate parameter for exponentially distributed period in the definition of " + toString(tag) + " '" + id + "'.");
188:                 }
189:                 flowParameter->poissonRate = rate;
190:                 poissonFlow = true;
191:             } else {
192:                 flowParameter->repetitionOffset = attrs.getSUMOTimeReporting(SUMO_ATTR_PERIOD, id.c_str(), ok);
193:             }
194:             if (!ok) {
195:                 return handleVehicleError(hardFail, flowParameter);
196:             } else {
197:                 flowParameter->parametersSet |= VEHPARS_PERIOD_SET;
198:             }
199:         }
201:         if (hasXPH) {
202:             bool ok = true;
203:             const double vph = attrs.get<double>(PERHOUR, id.c_str(), ok);
204:             if (!ok) {
205:                 return handleVehicleError(hardFail, flowParameter);
206:             } else if (vph <= 0) {
207:                 return handleVehicleError(hardFail, flowParameter, "Invalid repetition rate in the definition of " + toString(tag) + " '" + id + "'.");
208:             } else {
209:                 if (vph != 0) {
210:                     flowParameter->repetitionOffset = TIME2STEPS(3600. / vph);
211:                 }
212:                 flowParameter->parametersSet |= VEHPARS_VPH_SET;
213:             }
214:         }
216:         if (hasProb) {
217:             bool ok = true;
218:             flowParameter->repetitionProbability = attrs.get<double>(SUMO_ATTR_PROB, id.c_str(), ok);
219:             if (!ok) {
220:                 return handleVehicleError(hardFail, flowParameter);
221:             } else if (flowParameter->repetitionProbability <= 0 || flowParameter->repetitionProbability > 1) {
222:                 return handleVehicleError(hardFail, flowParameter, "Invalid repetition probability in the definition of " + toString(tag) + " '" + id + "'.");
223:             } else {
224:                 flowParameter->parametersSet |= VEHPARS_PROB_SET;
225:             }
226:         }
228:         flowParameter->depart = beginDefault;
230:         if (hasBegin) {
232:             bool ok = true;
233:             const std::string begin = attrs.get<std::string>(SUMO_ATTR_BEGIN, id.c_str(), ok);
234:             if (!ok) {
235:                 return handleVehicleError(hardFail, flowParameter);
236:             } else {
238:                 std::string errorMsg;
239:                 if (!SUMOVehicleParameter::parseDepart(begin, toString(tag), id, flowParameter->depart, flowParameter->departProcedure, errorMsg, "begin")) {
240:                     return handleVehicleError(hardFail, flowParameter, errorMsg);
241:                 }
242:             }
243:         }
244:         if (flowParameter->depart < 0) {
245:             return handleVehicleError(hardFail, flowParameter, "Negative begin time in the definition of " + toString(tag) + " '" + id + "'.");
246:         }
248:         flowParameter->repetitionEnd = endDefault;
249:         if (flowParameter->repetitionEnd < 0) {
250:             flowParameter->repetitionEnd = SUMOTime_MAX;
251:         }
253:         if (hasEnd) {
254:             bool ok = true;
255:             flowParameter->repetitionEnd = attrs.getSUMOTimeReporting(SUMO_ATTR_END, id.c_str(), ok);
256:             if (!ok) {
257:                 return handleVehicleError(hardFail, flowParameter);
258:             } else {
259:                 flowParameter->parametersSet |= VEHPARS_END_SET;
260:             }
261:         } else if (flowParameter->departProcedure == DepartDefinition::TRIGGERED) {
262:             if (!hasNumber) {
263:                 return handleVehicleError(hardFail, flowParameter, toString(tag) + " '" + id + "' with triggered begin must define 'number'.");
264:             } else {
265:                 flowParameter->repetitionEnd = flowParameter->depart;
266:             }
267:         } else if ((endDefault == SUMOTime_MAX || endDefault < 0) && (!hasNumber || (!hasProb && !hasPeriod && !hasXPH))) {
268:             WRITE_WARNINGF(TL("Undefined end for % '%', defaulting to 24hour duration."), toString(tag), id);
269:             flowParameter->repetitionEnd = flowParameter->depart + TIME2STEPS(24 * 3600);
270:         }
271:         if (flowParameter->repetitionEnd < flowParameter->depart) {
272:             std::string flow = toString(tag);
273:             flow[0] = (char)::toupper((char)flow[0]);
274:             return handleVehicleError(hardFail, flowParameter, flow + " '" + id + "' ends before its begin time.");
275:         }
277:         if (hasNumber) {
278:             bool ok = true;
279:             flowParameter->repetitionNumber = attrs.get<long long int>(SUMO_ATTR_NUMBER, id.c_str(), ok);
280:             if (!ok) {
281:                 return handleVehicleError(hardFail, flowParameter);
282:             } else {
283:                 flowParameter->parametersSet |= VEHPARS_NUMBER_SET;
284:                 if (flowParameter->repetitionNumber == 0) {
285:                     std::string flow = toString(tag);
286:                     flow[0] = (char)::toupper((char)flow[0]);
287:                     WRITE_WARNING(flow + " '" + id + "' has no instances; will skip it.");
288:                     flowParameter->repetitionEnd = flowParameter->depart;
289:                 } else {
290:                     if (flowParameter->repetitionNumber < 0) {
291:                         return handleVehicleError(hardFail, flowParameter, "Negative repetition number in the definition of " + toString(tag) + " '" + id + "'.");
292:                     }
293:                     if (flowParameter->repetitionOffset < 0 && !hasProb) {
294:                         if (poissonFlow) {
295:                             flowParameter->repetitionEnd = SUMOTime_MAX;
296:                         } else {
297:                             flowParameter->repetitionOffset = (flowParameter->repetitionEnd - flowParameter->depart) / flowParameter->repetitionNumber;
298:                         }
299:                     }
300:                 }
301:             }
302:         } else {
304:             if (flowParameter->repetitionProbability > 0) {
305:                 flowParameter->repetitionNumber = std::numeric_limits<long long int>::max();
306:             } else {
307:                 if (flowParameter->repetitionOffset <= 0) {
308:                     if (poissonFlow) {
310:                         flowParameter->repetitionNumber = std::numeric_limits<long long int>::max();
311:                     } else {
312:                         return handleVehicleError(hardFail, flowParameter, "Invalid repetition rate in the definition of " + toString(tag) + " '" + id + "'.");
313:                     }
314:                 } else {
315:                     if (flowParameter->repetitionEnd == SUMOTime_MAX) {
316:                         flowParameter->repetitionNumber = std::numeric_limits<long long int>::max();
317:                     } else {
318:                         const SUMOTime repLength = flowParameter->repetitionEnd - flowParameter->depart;
319:                         flowParameter->repetitionNumber = (long long int)ceil((double)repLength / (double)flowParameter->repetitionOffset);
320:                     }
321:                 }
322:             }
323:         }
325:         return flowParameter;
326:     } else {
327:         return handleVehicleError(hardFail, nullptr, toString(tag) + " cannot be created");
328:     }
329: }
```

### D2. Rerouting lifecycle — `microsim/devices/MSDevice_Routing.cpp:48-114`

```cpp
48: MSDevice_Routing::insertOptions(OptionsCont& oc) {
49:     insertDefaultAssignmentOptions("rerouting", "Routing", oc);
51:     oc.doRegister("device.rerouting.period", new Option_String("0", "TIME"));
52:     oc.addSynonyme("device.rerouting.period", "device.routing.period", true);
53:     oc.addDescription("device.rerouting.period", "Routing", TL("The period with which the vehicle shall be rerouted"));
55:     oc.doRegister("device.rerouting.pre-period", new Option_String("60", "TIME"));
56:     oc.addSynonyme("device.rerouting.pre-period", "device.routing.pre-period", true);
57:     oc.addDescription("device.rerouting.pre-period", "Routing", TL("The rerouting period before depart"));
59:     oc.doRegister("device.rerouting.adaptation-weight", new Option_Float(0));
60:     oc.addSynonyme("device.rerouting.adaptation-weight", "device.routing.adaptation-weight", true);
61:     oc.addDescription("device.rerouting.adaptation-weight", "Routing", TL("The weight of prior edge weights for exponential moving average"));
63:     oc.doRegister("device.rerouting.adaptation-steps", new Option_Integer(180));
64:     oc.addSynonyme("device.rerouting.adaptation-steps", "device.routing.adaptation-steps", true);
65:     oc.addDescription("device.rerouting.adaptation-steps", "Routing", TL("The number of steps for moving average weight of prior edge weights"));
67:     oc.doRegister("device.rerouting.adaptation-interval", new Option_String("1", "TIME"));
68:     oc.addSynonyme("device.rerouting.adaptation-interval", "device.routing.adaptation-interval", true);
69:     oc.addDescription("device.rerouting.adaptation-interval", "Routing", TL("The interval for updating the edge weights"));
71:     oc.doRegister("device.rerouting.cch-update-threshold.factor", new Option_Float(1));
72:     oc.addDescription("device.rerouting.cch-update-threshold.factor", "Routing", TL("Only propagate an arc weight into the CCH metric if it changed by more than the given factor"));
74:     oc.doRegister("device.rerouting.cch-update-threshold.constant", new Option_String("0", "TIME"));
75:     oc.addDescription("device.rerouting.cch-update-threshold.constant", "Routing", TL("Only propagate an arc weight into the CCH metric if it changed by more than the given TIME"));
76:     oc.doRegister("device.rerouting.cch-ensemble", new Option_Integer(1));
77:     oc.addDescription("device.rerouting.cch-ensemble", "Routing", TL("Keep this many frozen weights.random-factor realizations (CCH metrics) per vehicle type and assign vehicles to them by a stable id hash"));
79:     oc.doRegister("device.rerouting.threshold.factor", new Option_Float(1));
80:     oc.addDescription("device.rerouting.threshold.factor", "Routing", TL("Only reroute if the new route is faster than the current route by the given factor"));
82:     oc.doRegister("device.rerouting.threshold.constant", new Option_String("0", "TIME"));
83:     oc.addDescription("device.rerouting.threshold.constant", "Routing", TL("Only reroute if the new route is faster than the current route by the given TIME"));
85:     oc.doRegister("device.rerouting.invalidation", new Option_Bool(false));
86:     oc.addDescription("device.rerouting.invalidation", "Routing", TL("Only perform a periodic reroute when the current route's remaining cost has drifted beyond the threshold (cheap re-scoring gate before the full reroute)"));
88:     oc.doRegister("device.rerouting.with-taz", new Option_Bool(false));
89:     oc.addSynonyme("device.rerouting.with-taz", "device.routing.with-taz", true);
90:     oc.addSynonyme("device.rerouting.with-taz", "with-taz");
91:     oc.addDescription("device.rerouting.with-taz", "Routing", TL("Use zones (districts) as routing start- and endpoints"));
93:     oc.doRegister("device.rerouting.mode", new Option_String("0"));
94:     oc.addDescription("device.rerouting.mode", "Routing", TL("Set routing flags (8 ignores temporary blockages)"));
96:     oc.doRegister("device.rerouting.init-with-loaded-weights", new Option_Bool(false));
97:     oc.addDescription("device.rerouting.init-with-loaded-weights", "Routing", TL("Use weight files given with option --weight-files for initializing edge weights"));
99:     oc.doRegister("device.rerouting.threads", new Option_Integer(0));
100:     oc.addSynonyme("device.rerouting.threads", "routing-threads");
101:     oc.addDescription("device.rerouting.threads", "Routing", TL("The number of parallel execution threads used for rerouting"));
103:     oc.doRegister("device.rerouting.synchronize", new Option_Bool(false));
104:     oc.addDescription("device.rerouting.synchronize", "Routing", TL("Let rerouting happen at the same time for all vehicles"));
106:     oc.doRegister("device.rerouting.railsignal", new Option_Bool(false));
107:     oc.addDescription("device.rerouting.railsignal", "Routing", TL("Allow rerouting triggered by rail signals."));
109:     oc.doRegister("device.rerouting.bike-speeds", new Option_Bool(false));
110:     oc.addDescription("device.rerouting.bike-speeds", "Routing", TL("Compute separate average speeds for bicycles"));
112:     oc.doRegister("device.rerouting.output", new Option_FileName());
113:     oc.addDescription("device.rerouting.output", "Routing", TL("Save adapting weights to FILE"));
114: }
```

### D2. Rerouting lifecycle — `microsim/devices/MSDevice_Routing.cpp:151-168`

```cpp
151: MSDevice_Routing::buildVehicleDevices(SUMOVehicle& v, std::vector<MSVehicleDevice*>& into) {
152:     const OptionsCont& oc = OptionsCont::getOptions();
153:     const bool equip = equippedByDefaultAssignmentOptions(oc, "rerouting", v, false);
154:     if (v.getParameter().wasSet(VEHPARS_FORCE_REROUTE) || equip) {
159:         const SUMOTime period = (equip || (
160:                                      oc.isDefault("device.rerouting.probability") &&
161:                                      v.getFloatParam("device.rerouting.probability") == oc.getFloat("device.rerouting.probability"))
162:                                  ? v.getTimeParam("device.rerouting.period") : 0);
163:         const SUMOTime prePeriod = MAX2((SUMOTime)0, v.getTimeParam("device.rerouting.pre-period"));
164:         MSRoutingEngine::initWeightUpdate();
166:         into.push_back(new MSDevice_Routing(v, "routing_" + v.getID(), period, prePeriod));
167:     }
168: }
```

### D2. Rerouting lifecycle — `microsim/devices/MSDevice_Routing.cpp:174-197`

```cpp
174: MSDevice_Routing::MSDevice_Routing(SUMOVehicle& holder, const std::string& id,
175:                                    SUMOTime period, SUMOTime preInsertionPeriod) :
176:     MSVehicleDevice(holder, id),
177:     myPeriod(period),
178:     myPreInsertionPeriod(preInsertionPeriod),
179:     myLastRouting(-1),
180:     mySkipRouting(-1),
181:     myRerouteCommand(nullptr),
182:     myRerouteRailSignal(holder.getBoolParam("device.rerouting.railsignal", true)),
183:     myLastLaneEntryTime(-1),
184:     myRerouteAfterStop(false),
185:     myThresholdFactor(holder.getFloatParam("device.rerouting.threshold.factor", true, 1)),
186:     myThresholdTime(STEPS2TIME(holder.getTimeParam("device.rerouting.threshold.constant", true, 0))),
187:     myActive(true),
188:     myInvalidation(OptionsCont::getOptions().getBool("device.rerouting.invalidation")),
189:     myLastRouteCost(-1.) {
190:     if (myPreInsertionPeriod > 0 || holder.getParameter().wasSet(VEHPARS_FORCE_REROUTE)) {
192:         myRerouteCommand = new WrappingCommand<MSDevice_Routing>(this, &MSDevice_Routing::preInsertionReroute);
194:         const SUMOTime execTime = MSRoutingEngine::hasEdgeUpdates() ? holder.getParameter().depart : -1;
195:         MSNet::getInstance()->getInsertionEvents()->addEvent(myRerouteCommand, execTime);
196:     }
197: }
```

### D2. Rerouting lifecycle — `microsim/devices/MSDevice_Routing.cpp:209-234`

```cpp
209: MSDevice_Routing::notifyEnter(SUMOTrafficObject& /*veh*/, MSMoveReminder::Notification reason, const MSLane* enteredLane) {
210:     if (reason == MSMoveReminder::NOTIFICATION_DEPARTED) {
211:         if (myRerouteCommand == nullptr && myPreInsertionPeriod > 0 && myHolder.getDepartDelay() > myPreInsertionPeriod) {
214:             myHolder.reroute(MSNet::getInstance()->getCurrentTimeStep(), "device.rerouting",
215:                              MSRoutingEngine::getRouterTT(myHolder.getRNGIndex(), myHolder.getVClass()),
216:                              true, MSRoutingEngine::withTaz(), false);
217:         }
219:         rebuildRerouteCommand(SIMSTEP + myPeriod);
220:     }
221:     if (MSGlobals::gWeightsSeparateTurns > 0 && enteredLane != nullptr) {
222:         if (reason == MSMoveReminder::NOTIFICATION_JUNCTION) {
223:             const SUMOTime t = SIMSTEP;
224:             if (myLastLaneEntryTime >= 0 && enteredLane->isInternal()) {
226:                 MSRoutingEngine::addEdgeTravelTime(enteredLane->getEdge(), t - myLastLaneEntryTime);
227:             }
228:             myLastLaneEntryTime = t;
229:         }
230:         return true;
231:     } else {
232:         return false;
233:     }
234: }
```

### D2. Rerouting lifecycle — `microsim/devices/MSDevice_Routing.cpp:265-298`

```cpp
265: MSDevice_Routing::preInsertionReroute(const SUMOTime currentTime) {
266:     if (mySkipRouting == currentTime) {
267:         return DELTA_T;
268:     }
269:     if (myPreInsertionPeriod == 0) {
271:         myRerouteCommand = nullptr;
272:     }
273:     const MSEdge* source = *myHolder.getRoute().begin();
274:     const MSEdge* dest = myHolder.getRoute().getLastEdge();
275:     if (source->isTazConnector() && dest->isTazConnector()) {
276:         ConstMSRoutePtr cached = MSRoutingEngine::getCachedRoute(std::make_pair(source, dest));
277:         if (cached != nullptr && cached->size() > 2) {
278:             myHolder.replaceRoute(cached, "device.rerouting", true);
279:             return myPreInsertionPeriod;
280:         }
281:     }
282:     try {
283:         std::string msg;
284:         if (myHolder.hasValidRouteStart(msg)) {
285:             reroute(currentTime, true);
286:         }
287:     } catch (ProcessError&) {
288:         myRerouteCommand = nullptr;
289:         throw;
290:     }
293:     if (myPreInsertionPeriod > 0 && !source->isTazConnector() && myHolder.getParameter().departLaneProcedure != DepartLaneDefinition::BEST_FREE) {
294:         myRerouteCommand = nullptr;
295:         return 0;
296:     }
297:     return myPreInsertionPeriod;
298: }
```

### D2. Rerouting lifecycle — `microsim/devices/MSDevice_Routing.cpp:313-345`

```cpp
313: MSDevice_Routing::reroute(const SUMOTime currentTime, const bool onInit) {
314:     MSRoutingEngine::initEdgeWeights(myHolder.getVClass());
316:     if (myLastRouting >= MSRoutingEngine::getLastAdaptation() || !myActive) {
317:         return;
318:     }
325:     const bool canGate = myInvalidation && !onInit && myHolder.isOnRoad();
326:     if (canGate && myLastRouteCost >= 0.) {
327:         MSVehicleRouter& router = MSRoutingEngine::getRouterTT(myHolder.getRNGIndex(), myHolder.getVClass());
328:         const ConstMSEdgeVector remaining(myHolder.getCurrentRouteEdge(), myHolder.getRoute().end());
329:         if (!remaining.empty()) {
330:             const double costNow = router.recomputeCosts(remaining, &myHolder, currentTime);
331:             if (costNow - myLastRouteCost <= myThresholdTime && costNow <= myLastRouteCost * myThresholdFactor) {
332:                 myLastRouting = currentTime;  // route still good enough; skip the search
333:                 myLastRouteCost = costNow;
334:                 return;
335:             }
336:         }
337:     }
338:     myLastRouting = currentTime;
339:     MSRoutingEngine::reroute(myHolder, currentTime, "device.rerouting", onInit);
340:     if (myInvalidation && myHolder.isOnRoad()) {
341:         MSVehicleRouter& router = MSRoutingEngine::getRouterTT(myHolder.getRNGIndex(), myHolder.getVClass());
342:         const ConstMSEdgeVector remaining(myHolder.getCurrentRouteEdge(), myHolder.getRoute().end());
343:         myLastRouteCost = remaining.empty() ? -1. : router.recomputeCosts(remaining, &myHolder, currentTime);
344:     }
345: }
```

### D3. Stop parser — `microsim/MSRouteHandler.cpp:1257-1467`

```cpp
1257: MSRouteHandler::addStop(const SUMOSAXAttributes& attrs) {
1258:     Parameterised* result = nullptr;
1259:     try {
1260:         std::string errorSuffix;
1261:         if (myActiveType == ObjectTypeEnum::PERSON) {
1262:             errorSuffix = " in person '" + myVehicleParameter->id + "'";
1263:         } else if (myActiveType == ObjectTypeEnum::CONTAINER) {
1264:             errorSuffix = " in container '" + myVehicleParameter->id + "'";
1265:         } else if (myVehicleParameter != nullptr) {
1266:             errorSuffix = " in vehicle '" + myVehicleParameter->id + "'";
1267:         } else {
1268:             errorSuffix = " in route '" + myActiveRouteID + "'";
1269:         }
1270:         SUMOVehicleParameter::Stop stop;
1271:         bool ok = parseStop(stop, attrs, errorSuffix, MsgHandler::getErrorInstance());
1272:         if (!ok) {
1273:             if (MSGlobals::gCheckRoutes) {
1274:                 throw ProcessError();
1275:             }
1276:             return result;
1277:         }
1278:         const MSEdge* edge = nullptr;
1280:         if (stop.chargingStation != "") {
1281:             const MSChargingStation* cs = dynamic_cast<MSChargingStation*>(MSNet::getInstance()->getStoppingPlace(stop.chargingStation, SUMO_TAG_CHARGING_STATION));
1282:             const MSParkingArea* pa = cs->getParkingArea();
1283:             if (pa != nullptr) {
1284:                 stop.parkingarea = pa->getID();
1285:                 stop.parking = ParkingType::OFFROAD;
1286:             }
1287:         }
1288:         MSStoppingPlace* toStop = retrieveStoppingPlace(attrs, errorSuffix, &stop);
1290:         if (toStop != nullptr) {
1291:             const MSLane& l = toStop->getLane();
1292:             stop.lane = l.getID();
1293:             if ((stop.parametersSet & STOP_END_SET) == 0) {
1294:                 stop.endPos = toStop->getEndLanePosition();
1295:             } else {
1296:                 stop.endPos = attrs.get<double>(SUMO_ATTR_ENDPOS, nullptr, ok);
1297:             }
1298:             stop.startPos = toStop->getBeginLanePosition();
1299:             edge = &l.getEdge();
1300:         } else {
1303:             stop.lane = attrs.getOpt<std::string>(SUMO_ATTR_LANE, nullptr, ok, "");
1304:             stop.edge = attrs.getOpt<std::string>(SUMO_ATTR_EDGE, nullptr, ok, "");
1305:             if (ok && stop.edge != "") { // edge is given directly
1306:                 edge = MSEdge::dictionary(stop.edge);
1307:                 if (edge == nullptr || (edge->isInternal() && !MSGlobals::gUsingInternalLanes)) {
1308:                     throw ProcessError(TLF("The edge '%' for a stop is not known%.", stop.edge, errorSuffix));
1309:                 }
1310:             } else if (ok && stop.lane != "") { // lane is given directly
1311:                 MSLane* stopLane = MSLane::dictionary(stop.lane);
1312:                 if (stopLane == nullptr) {
1314:                     stopLane = MSBaseVehicle::interpretOppositeStop(stop);
1315:                     if (stopLane != nullptr) {
1316:                         edge = MSEdge::dictionary(stop.edge);
1317:                     }
1318:                 } else {
1319:                     edge = &stopLane->getEdge();
1320:                 }
1321:                 if (stopLane == nullptr || (stopLane->isInternal() && !MSGlobals::gUsingInternalLanes)) {
1322:                     throw ProcessError(TLF("The lane '%' for a stop is not known%.", stop.lane, errorSuffix));
1323:                 }
1324:             } else if (ok && ((attrs.hasAttribute(SUMO_ATTR_X) && attrs.hasAttribute(SUMO_ATTR_Y))
1325:                               || (attrs.hasAttribute(SUMO_ATTR_LON) && attrs.hasAttribute(SUMO_ATTR_LAT)))) {
1326:                 Position pos;
1327:                 bool geo = false;
1328:                 if (attrs.hasAttribute(SUMO_ATTR_X) && attrs.hasAttribute(SUMO_ATTR_Y)) {
1329:                     pos = Position(attrs.get<double>(SUMO_ATTR_X, myVehicleParameter->id.c_str(), ok), attrs.get<double>(SUMO_ATTR_Y, myVehicleParameter->id.c_str(), ok));
1330:                 } else {
1331:                     pos = Position(attrs.get<double>(SUMO_ATTR_LON, myVehicleParameter->id.c_str(), ok), attrs.get<double>(SUMO_ATTR_LAT, myVehicleParameter->id.c_str(), ok));
1332:                     geo = true;
1333:                 }
1334:                 PositionVector positions;
1335:                 positions.push_back(pos);
1336:                 ConstMSEdgeVector geoEdges;
1337:                 SUMOVehicleClass vClass = SVC_PASSENGER;
1338:                 auto& vc = MSNet::getInstance()->getVehicleControl();
1339:                 if (!vc.getVTypeDistribution(myVehicleParameter->vtypeid)) {
1340:                     MSVehicleType* const type = vc.getVType(myVehicleParameter->vtypeid, &myParsingRNG);
1341:                     if (type != nullptr) {
1342:                         vClass = type->getParameter().vehicleClass;
1343:                     }
1344:                 }
1345:                 parseGeoEdges(positions, geo, vClass, geoEdges, myVehicleParameter->id, true, ok, true);
1346:                 if (ok) {
1347:                     edge = geoEdges.front();
1348:                     if (geo) {
1349:                         GeoConvHelper::getFinal().x2cartesian_const(pos);
1350:                     }
1351:                     stop.parametersSet |= STOP_END_SET;
1352:                     stop.endPos = edge->getLanes()[0]->getShape().nearest_offset_to_point2D(pos, false);
1353:                 } else {
1354:                     throw ProcessError(TLF("Could not map stop position '%' to the network%.", pos, errorSuffix));
1355:                 }
1356:             } else {
1357:                 if (myActiveTransportablePlan && !myActiveTransportablePlan->empty()) { // use end of movement before
1358:                     toStop = myActiveTransportablePlan->back()->getDestinationStop();
1359:                     if (toStop != nullptr) { // use end of movement before definied as a stopping place
1360:                         edge = &toStop->getLane().getEdge();
1361:                         stop.lane = toStop->getLane().getID();
1362:                         stop.endPos = toStop->getEndLanePosition();
1363:                         stop.startPos = toStop->getBeginLanePosition();
1364:                     } else { // use end of movement before definied as lane/edge
1365:                         edge = myActiveTransportablePlan->back()->getDestination();
1366:                         stop.lane = edge->getLanes()[0]->getID();
1367:                         stop.endPos = myActiveTransportablePlan->back()->unspecifiedArrivalPos() ?
1368:                                       MSStage::ARRIVALPOS_UNSPECIFIED : myActiveTransportablePlan->back()->getArrivalPos();
1369:                         stop.startPos = MAX2(0., stop.endPos - MIN_STOP_LENGTH);
1370:                     }
1371:                 } else {
1372:                     const std::string msg = TLF("A stop must be placed on a busStop, a chargingStation, an overheadWireSegment, a containerStop, a parkingArea, an edge or a lane%.", errorSuffix);
1373:                     if (MSGlobals::gCheckRoutes) {
1374:                         throw ProcessError(msg);
1375:                     } else {
1376:                         WRITE_WARNING(msg);
1377:                         return result;
1378:                     }
1379:                 }
1380:             }
1381:             stop.endPos = attrs.getOpt<double>(SUMO_ATTR_ENDPOS, nullptr, ok, edge->getLength());
1382:             if (attrs.hasAttribute(SUMO_ATTR_POSITION)) {
1383:                 WRITE_WARNINGF(TL("Deprecated attribute 'pos' in description of stop%."), errorSuffix);
1384:                 stop.endPos = attrs.getOpt<double>(SUMO_ATTR_POSITION, nullptr, ok, stop.endPos);
1385:             }
1386:             if (stop.endPos < 0) {
1387:                 stop.endPos += edge->getLength();
1388:             }
1389:             stop.startPos = attrs.getOpt<double>(SUMO_ATTR_STARTPOS, nullptr, ok, MAX2(0., stop.endPos - MIN_STOP_LENGTH));
1390:             if (!myAmLoadingState) {
1391:                 const bool friendlyPos = attrs.getOpt<bool>(SUMO_ATTR_FRIENDLY_POS, nullptr, ok, !attrs.hasAttribute(SUMO_ATTR_STARTPOS) && !attrs.hasAttribute(SUMO_ATTR_ENDPOS))
1392:                                          || !MSGlobals::gCheckRoutes;
1393:                 if (!ok || (checkStopPos(stop.startPos, stop.endPos, edge->getLength(), 0, friendlyPos) != StopPos::STOPPOS_VALID)) {
1394:                     throw ProcessError(TLF("Invalid start or end position for stop on %'%.",
1395:                                            stop.lane != "" ? ("lane '" + stop.lane) : ("edge '" + stop.edge), errorSuffix));
1396:                 }
1397:             }
1398:         }
1399:         stop.edge = edge->getID();
1400:         if (myActiveTransportablePlan) {
1401:             if (myActiveTransportablePlan->empty()) {
1402:                 double departPos = toStop == nullptr || myVehicleParameter->wasSet(VEHPARS_DEPARTPOS_SET)
1403:                                    ? myVehicleParameter->departPos
1404:                                    : (toStop->getBeginLanePosition() + toStop->getEndLanePosition()) / 2;
1405:                 myActiveTransportablePlan->push_back(new MSStageWaiting(
1406:                         edge, toStop, -1, myVehicleParameter->depart, departPos, "start", true));
1407:             } else if (myActiveTransportablePlan->back()->getDestination() != edge) {
1408:                 if (myActiveTransportablePlan->back()->getDestination()->isTazConnector()) {
1409:                     myActiveTransportablePlan->back()->setDestination(edge, toStop);
1410:                 } else if (myActiveTransportablePlan->back()->getJumpDuration() < 0) {
1411:                     throw ProcessError(TLF("Disconnected plan for % '%' (%!=%).", myActiveTypeName, myVehicleParameter->id,
1412:                                            edge->getID(), myActiveTransportablePlan->back()->getDestination()->getID()));
1413:                 }
1414:             }
1416:             else if (myActiveTransportablePlan->back()->getStageType() == MSStageType::WAITING
1417:                      && (attrs.hasAttribute(SUMO_ATTR_ENDPOS) || attrs.hasAttribute(SUMO_ATTR_STARTPOS))) {
1418:                 const double start = SUMOVehicleParameter::interpretEdgePos(stop.startPos, edge->getLength(), SUMO_ATTR_STARTPOS, "stopping at " + edge->getID());
1419:                 const double end = SUMOVehicleParameter::interpretEdgePos(stop.endPos, edge->getLength(), SUMO_ATTR_ENDPOS, "stopping at " + edge->getID());
1420:                 const double prevAr = myActiveTransportablePlan->back()->getArrivalPos();
1421:                 if (start > prevAr + NUMERICAL_EPS || end < prevAr - NUMERICAL_EPS) {
1422:                     WRITE_WARNINGF(TL("Disconnected plan for % '%' (stop range %-% does not cover previous arrival position %)."),
1423:                                    myActiveTypeName, myVehicleParameter->id, toString(start), toString(end), toString(prevAr));
1424:                 }
1425:             }
1426:             std::string actType = attrs.getOpt<std::string>(SUMO_ATTR_ACTTYPE, nullptr, ok, "");
1427:             double pos = (stop.startPos + stop.endPos) / 2.;
1428:             if (!myActiveTransportablePlan->empty() && myActiveTransportablePlan->back()->getJumpDuration() < 0) {
1429:                 pos = myActiveTransportablePlan->back()->unspecifiedArrivalPos() ?
1430:                       MSStage::ARRIVALPOS_UNSPECIFIED : myActiveTransportablePlan->back()->getArrivalPos();
1431:             }
1432:             myActiveTransportablePlan->push_back(new MSStageWaiting(edge, toStop, stop.duration, stop.until, pos, actType, false, stop.jump));
1433:             result = myActiveTransportablePlan->back();
1435:         } else if (myVehicleParameter != nullptr) {
1436:             myVehicleParameter->stops.push_back(stop);
1437:             result = &myVehicleParameter->stops.back();
1438:         } else {
1439:             myActiveRouteStops.push_back(stop);
1440:             result = &myActiveRouteStops.back();
1441:         }
1442:         if (myInsertStopEdgesAt >= 0) {
1444:             if (edge->isInternal()) {
1445:                 if (myInsertStopEdgesAt > 0 && *(myActiveRoute.begin() + (myInsertStopEdgesAt - 1)) != edge->getNormalBefore()) {
1446:                     myActiveRoute.insert(myActiveRoute.begin() + myInsertStopEdgesAt, edge->getNormalBefore());
1447:                     myInsertStopEdgesAt++;
1448:                 }
1449:                 myActiveRoute.insert(myActiveRoute.begin() + myInsertStopEdgesAt, edge->getNormalSuccessor());
1450:                 myInsertStopEdgesAt++;
1451:             } else {
1452:                 myActiveRoute.insert(myActiveRoute.begin() + myInsertStopEdgesAt, edge);
1453:                 myInsertStopEdgesAt++;
1454:             }
1455:         } else if (myHaveVia) {
1457:             if (std::find(myActiveRoute.begin(), myActiveRoute.end(), edge) == myActiveRoute.end()) {
1458:                 WRITE_WARNINGF(TL("Stop edge '%' missing in attribute 'via' for % '%'."),
1459:                                edge->getID(), myActiveTypeName, myVehicleParameter->id);
1460:             }
1461:         }
1462:     } catch (ProcessError&) {
1463:         deleteActivePlanAndVehicleParameter();
1464:         throw;
1465:     }
1466:     return result;
1467: }
```

### C4. Loop position validation — `netload/NLDetectorBuilder.cpp:99-127`

```cpp
99: NLDetectorBuilder::buildInductLoop(const std::string& id,
100:                                    const std::string& lane, double pos, double length, SUMOTime splInterval,
101:                                    const std::string& device, bool friendlyPos,
102:                                    const std::string name,
103:                                    const std::string& vTypes,
104:                                    const std::string& nextEdges,
105:                                    bool mesoTLS,
106:                                    int detectPersons) {
107:     checkSampleInterval(splInterval, SUMO_TAG_E1DETECTOR, id);
109:     MSLane* clane = getLaneChecking(lane, SUMO_TAG_E1DETECTOR, id);
111:     pos = getPositionChecking(pos, clane, friendlyPos, SUMO_TAG_E1DETECTOR, id);
112:     if (length < 0) {
113:         throw InvalidArgument("The length of " + toString(SUMO_TAG_E1DETECTOR) + " '" + id + "' cannot be negative");
114:     } else if (length > 0 && pos + length > clane->getLength()) {
115:         if (friendlyPos) {
116:             length = MIN2(length, clane->getLength());
117:             pos = clane->getLength() - length;
118:         } else {
119:             throw InvalidArgument("The length of " + toString(SUMO_TAG_E1DETECTOR) + " '" + id + "' puts it beyond the lane's '" + clane->getID() + "' end.");
120:         }
121:     }
123:     MSDetectorFileOutput* loop = createInductLoop(id, clane, pos, length, name, vTypes, nextEdges, detectPersons, true, mesoTLS);
125:     myNet.getDetectorControl().add(SUMO_TAG_INDUCTION_LOOP, loop, device, splInterval);
126:     return loop;
127: }
```

### C4. Loop position validation — `netload/NLDetectorBuilder.cpp:624-632`

```cpp
624: NLDetectorBuilder::checkSampleInterval(SUMOTime splInterval, SumoXMLTag type, const std::string& id) {
625:     if (splInterval < 0) {
626:         throw InvalidArgument("Negative sampling frequency (in " + toString(type) + " '" + id + "').");
627:     }
628:     if (splInterval == 0) {
629:         throw InvalidArgument("Sampling frequency must not be zero (in " + toString(type) + " '" + id + "').");
630:     }
631:     checkStepLengthMultiple(splInterval, " (in " + toString(type) + " '" + id + "')");
632: }
```

## Boundary and helper details

`best_prob` does not perform a random draw: it chooses the largest positive departure gap while disallowing insertion to the left of a vehicle with larger maximum desired speed; least occupancy is the fallback (`microsim/MSEdge.cpp:603-637`). `free` first maximizes that gap, with least occupancy fallback (`MSEdge.cpp:571-599`).

Permission predicates require the full requested class bits: `(permissions & vclass)==vclass`, with separate masks for directional changes (`MSLane.h:956-970`). Detector negative positions are relative to the lane end; `friendlyPos` clamps out-of-bounds placement according to the following validator (`netload/NLDetectorBuilder.cpp:480-504`). Edge aggregation uses `edge->getLength()` with summed lane integrals and `getNumDrivingLanes()`, not an average of separately computed lane densities (`MSMeanData.cpp:767-787`). XML null values suppress attributes; other output formatters may encode null (`utils/iodevices/OutputDevice.h:284-307`).

Initial routing assignment default is internally -1 (avoids an RNG draw); do not substitute this sentinel directly into a Bernoulli test (`microsim/devices/MSDevice.cpp:157-170`). Default probability assignment is resolved by the device assignment helper; forced trips still obtain the device (D2).

### Public flag tail — `utils/xml/SUMOXMLDefinitions.h:2256-2260`

```cpp
2258:     LCA_AMBACKBLOCKER = 1 << 26,
2259:     LCA_AMBACKBLOCKER_STANDING = 1 << 27
```

### Permission masks — `microsim/MSLane.h:950-974`

```cpp
951:     /** @brief Sets the permissions for changing to the right neighbour lane
952:      * @param[in] permissions The new permissions
953:      */
954:     void setChangeRight(SVCPermissions permissions);
956:     inline bool allowsVehicleClass(SUMOVehicleClass vclass) const {
957:         return (myPermissions & vclass) == vclass;
958:     }
960:     bool allowsVehicleClass(SUMOVehicleClass vclass, int routingMode) const;
962:     /** @brief Returns whether the given vehicle class may change left from this lane */
963:     inline bool allowsChangingLeft(SUMOVehicleClass vclass) const {
964:         return (myChangeLeft & vclass) == vclass;
965:     }
967:     /** @brief Returns whether the given vehicle class may change left from this lane */
968:     inline bool allowsChangingRight(SUMOVehicleClass vclass) const {
969:         return (myChangeRight & vclass) == vclass;
970:     }
972:     void addIncomingLane(MSLane* lane, MSLink* viaLink);
```

### Best-lane occupation override — `microsim/MSVehicle.cpp:6734-6739`

```cpp
6734: void
6735: MSVehicle::adaptBestLanesOccupation(int laneIndex, double density) {
6736:     std::vector<MSVehicle::LaneQ>& preb = myBestLanes.front();
6737:     assert(laneIndex < (int)preb.size());
6738:     preb[laneIndex].occupation = density + preb[laneIndex].nextOccupation;
6739: }
```

### Base departure position — `microsim/MSBaseVehicle.cpp:1415-1424`

```cpp
1415: MSBaseVehicle::basePos(const MSEdge* edge) const {
1416:     double result = MIN2(getVehicleType().getLength() + POSITION_EPS, edge->getMinLength());
1417:     if (hasStops()
1418:             && myStops.front().edge == myRoute->begin()
1419:             && (&myStops.front().lane->getEdge()) == *myStops.front().edge) {
1420:         result = MIN2(result, MAX2(0.0, myStops.front().getEndPos(*this)));
1421:     }
1422:     return result;
1423: }
```

### Departure delay — `microsim/MSBaseVehicle.cpp:818-833`

```cpp
818: MSBaseVehicle::onDepart() {
819:     myDeparture = MSNet::getInstance()->getCurrentTimeStep();
820:     myDepartPos = getPositionOnLane();
821:     MSNet::getInstance()->getVehicleControl().vehicleDeparted(*this);
822: }
825: SUMOTime
826: MSBaseVehicle:: getDepartDelay() const {
827:     const SUMOTime dep = getParameter().depart;
828:     if (dep < 0) {
829:         return 0;
830:     }
831:     return hasDeparted() ? getDeparture() - dep : SIMSTEP - dep;
832: }
```

### Waiting acceleration bound — `microsim/MSVehicle.h:2099-2103`

```cpp
2100:     inline double accelThresholdForWaiting() const {
2101:         return 0.5 * getCarFollowModel().getMaxAccel();
2102:     }
```

### Mean-data edge aggregation tail — `microsim/output/MSMeanData.cpp:777-805`

```cpp
777:                 }
778:             }
779:             if (writeCheck || !sumData->isEmpty()) {
780:                 writePrefix(dev, *sumData, SUMO_TAG_EDGE, getEdgeID(edge));
781:                 for (MeanDataValues* data = sumData; data != nullptr; data = data->getSubData()) {
782:                     data->write(dev, myWrittenAttributes, stopTime - startTime, edge->getNumDrivingLanes(), edge->getSpeedLimit(),
783:                                 myPrintDefaults ? edge->getLength() / edge->getSpeedLimit() : -1.);
784:                 }
785:                 dev.closeTag();
786:             }
787:             delete sumData;
788:         }
789:     }
790: }
793: void
794: MSMeanData::openInterval(OutputDevice& dev, const SUMOTime startTime, const SUMOTime stopTime) {
795:     dev.openTag(SUMO_TAG_INTERVAL).writeAttr(SUMO_ATTR_BEGIN, time2string(startTime)).writeAttr(SUMO_ATTR_END, time2string(stopTime));
796:     dev.writeAttr(SUMO_ATTR_ID, myID);
797: }
800: void
801: MSMeanData::writePrefix(OutputDevice& dev, const MeanDataValues& values, const SumoXMLTag tag, const std::string id) const {
802:     dev.openTag(tag);
803:     dev.writeAttr(SUMO_ATTR_ID, id);
804:     dev.writeOptionalAttr(SUMO_ATTR_SAMPLEDSECONDS, values.getSamples(), myWrittenAttributes);
805: }
```

### Samples getter — `microsim/output/MSMeanData.cpp:280-282`

```cpp
280: MSMeanData::MeanDataValues::getSamples() const {
281:     return sampleSeconds;
282: }
```

### XML attribute omission — `utils/iodevices/OutputDevice.h:284-307`

```cpp
284:     OutputDevice& writeOptionalAttr(const SumoXMLAttr attr, const T& val, const bool isNull = false, const bool escape = false) {
285:         if (myFormatter->getType() == OutputFormatterType::XML && isNull) {
286:             return *this;
287:         }
288:         return writeAttr(attr, val, isNull, escape);
289:     }
291:     /** @brief writes a named attribute unless filtered
292:      *
293:      * @param[in] attr The attribute (name)
294:      * @param[in] val The attribute value
295:      * @param[in] attributeMask The filter that specifies whether the attribute shall be written
296:      * @param[in] isNull Whether the value should be represented as None / null in output formats which support it
297:      * @param[in] escape Whether the value should be processed by the escaping mechanism to filter invalid characters
298:      * @return The OutputDevice for further processing
299:      */
300:     template <typename T>
301:     OutputDevice& writeOptionalAttr(const SumoXMLAttr attr, const T& val, const SumoXMLAttrMask& attributeMask,
302:                                     const bool isNull = false, const bool escape = false) {
303:         assert(attributeMask.none() || (int)attr <= (int)attributeMask.size());
304:         if (attributeMask.none() || attributeMask.test(attr)) {
305:             return writeOptionalAttr(attr, val, isNull, escape);
306:         }
307:         return *this;
```

### Detector position validator — `netload/NLDetectorBuilder.cpp:480-511`

```cpp
480: NLDetectorBuilder::getPositionChecking(double pos, MSLane* lane, bool friendlyPos,
481:                                        SumoXMLTag tag,
482:                                        const std::string& detid) {
484:     if (pos < 0) {
485:         pos += lane->getLength();
486:     }
488:     if (pos > lane->getLength()) {
489:         if (friendlyPos) {
490:             pos = lane->getLength();
491:         } else {
492:             throw InvalidArgument("The position of " + toString(tag) + " '" + detid + "' lies beyond the lane's '" + lane->getID() + "' end.");
493:         }
494:     }
495:     if (pos < 0) {
496:         if (friendlyPos) {
497:             pos = 0.;
498:         } else {
499:             throw InvalidArgument("The position of " + toString(tag) + "  '" + detid + "' lies before the lane's '" + lane->getID() + "' begin.");
500:         }
501:     }
502:     return pos;
503: }
506: void
507: NLDetectorBuilder::createEdgeLaneMeanData(const std::string& id, SUMOTime frequency,
508:         SUMOTime begin, SUMOTime end, const std::string& type,
509:         const bool useLanes, const std::string& excludeEmpty,
510:         const bool withInternal, const bool trackVehicles, const int detectPersons,
511:         const double maxTravelTime, const double minSamples,
```

### Cooperative-help speed — `microsim/lcmodels/MSAbstractLaneChangeModel.cpp:1194-1232`

```cpp
1194: MSAbstractLaneChangeModel::getCooperativeHelpSpeed(const MSLane* lane, double distToLaneEnd) const {
1195:     if (myCooperativeHelpTime >= 0) {
1196:         std::pair<double, SUMOTime> backAndWaiting = lane->getEdge().getLastBlocked(lane->getIndex());
1197:         if (backAndWaiting.second >= myCooperativeHelpTime) {
1198:             double gap = distToLaneEnd - lane->getLength() + backAndWaiting.first - myVehicle.getVehicleType().getMinGap() - NUMERICAL_EPS;
1199:             if (backAndWaiting.first < 0) {
1200:                 if (myVehicle.getLane()->getToJunction() == lane->getFromJunction()) {
1201:                     if (myVehicle.getLane()->isInternal()) {
1203:                         gap = -1;
1204:                     } else {
1206:                         gap = myVehicle.getLane()->getLength() - myVehicle.getPositionOnLane();
1207:                     }
1208:                 }
1209:             }
1210:             if (gap > 0) {
1211:                 double stopSpeed = myVehicle.getCarFollowModel().stopSpeed(&myVehicle, myVehicle.getSpeed(), gap);
1215:                 if (stopSpeed >= myVehicle.getCarFollowModel().minNextSpeed(myVehicle.getSpeed(), &myVehicle)) {
1217:                     return stopSpeed;
1218:                 }
1219:             }
1220:         }
1221:     }
1223:     return std::numeric_limits<double>::max();
1224: }
```

### Device assignment defaults — `microsim/devices/MSDevice.cpp:157-177`

```cpp
157: MSDevice::insertDefaultAssignmentOptions(const std::string& deviceName, const std::string& optionsTopic, OptionsCont& oc, const bool isPerson) {
158:     const std::string prefix = (isPerson ? "person-device." : "device.") + deviceName;
159:     const std::string object = isPerson ? "person" : "vehicle";
160:     oc.doRegister(prefix + ".probability", new Option_Float(-1.0));// (default: no need to call RNG)
161:     oc.addDescription(prefix + ".probability", optionsTopic, "The probability for a " + object + " to have a '" + deviceName + "' device");
163:     oc.doRegister(prefix + ".explicit", new Option_StringVector());
164:     oc.addSynonyme(prefix + ".explicit", prefix + ".knownveh", true);
165:     oc.addDescription(prefix + ".explicit", optionsTopic, "Assign a '" + deviceName + "' device to named " + object + "s");
167:     oc.doRegister(prefix + ".deterministic", new Option_Bool(false));
168:     oc.addDescription(prefix + ".deterministic", optionsTopic, "The '" + deviceName + "' devices are set deterministic using a fraction of 1000");
169: }
172: std::string
173: MSDevice::getDeviceName(const std::string& id) {
174:     if (StringUtils::startsWith(id, "routing_")) {
176:         return "rerouting";
177:     } else if (StringUtils::startsWith(id, "driverstate")) {
```

Counter interpretation: `running` includes vehicles temporarily in the teleporter (`MSVehicleControl.h:272-277`); `ended` includes discarded vehicles; `arrived=ended-discarded`, `inserted=running+ended-discarded` (`MSVehicleControl.h:254-285`). A port that derives ended solely from successful destination arrivals will disagree when vehicles are discarded. Execution timing uses `getCurrentMillis()` difference (`MSNet.cpp:842,972`).
