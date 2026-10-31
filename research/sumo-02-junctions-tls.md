# SUMO 1.28 junctions, signals, jams: implementation specification

Source root: `/home/erikf/projects/personal/thesis-src/sumo/src`. Citations below are relative to that root; ranges identify the implementing branch, not documentation paraphrases. Scope: microscopic road vehicles with internal lanes; pedestrian, railway, opposite-driving and sublane exceptions are explicitly identified. **GPU recommendations are proposals/inferences, not SUMO guarantees.** Statistical comparability requires measuring the proposed approximations against the chosen networks and demand.

## 1. Import and static topology

### Objects and indices

- An edge owns ordered lane objects; a lane carries ID, speed, friction, declared simulation length, geometric shape, width, vehicle permissions, lane-change permissions and lane index. Preserve simulation length independently of polyline length. `NLEdgeControlBuilder::addLane` constructs the lane on the active edge and appends it; do not sort by ID. [netload/NLEdgeControlBuilder.cpp:90–101; netload/NLHandler.cpp:536–591]
- Edge function distinguishes normal/internal/crossing/walking area. Internal edges are actual simulation edges/lanes, not just turning labels; disabling internal lanes skips their connections. Edge priority is explicitly loaded “only for visualization”: runtime priority comes from connections/requests, not a comparison of edge priority integers. [netload/NLHandler.cpp:443–494,1422–1430]
- `<junction id type x y [z] [shape] incLanes="..." intLanes="...">`: resolve whitespace-separated IDs in the supplied order. `incLanes` is the incoming-lane traversal order; `intLanes` is a separate ordered association used below, not an unordered set. Internal junctions need no polygon. [netload/NLHandler.cpp:610–669; microsim/MSRightOfWayJunction.cpp:60–74,128–150]
- `<connection from to fromLane toLane via tl linkIndex dir state [keepClear] [visibility]>`: `from/to` select edges, lane attributes select indices within those edges, `via` selects the immediate internal lane, while `to` still identifies the eventual target lane. Build `Link{before,target,via,dir,state,length,visibility,keepClear,tls,tlsIndex}` and append to `before.links` in input order. Link length = via simulation length; otherwise crossing target length, otherwise distance between source-shape end and target-shape start. `via` gets the incoming-link association, or target gets it when there is no via. Defaults: keepClear=true; visibility=100 m for zipper, otherwise 4.5 m. [netload/NLHandler.cpp:1420–1514]
- `tl`/`linkIndex` are signal-controller group addressing, **not request-matrix addressing**. Multiple physical links can share a TLS group; validate index against phase-string length and register link with controller. `dir` and `state` use the enumerated XML dictionaries, not arbitrary strings. [netload/NLHandler.cpp:1435–1443,1466–1477,1507–1514,1560–1580; microsim/traffic_lights/MSTrafficLightLogic.cpp:402–411]

### Request matrix: exact mapping

`<request index="i" response="..." foes="..." cont="0|1"/>` is loaded in sequential index order. Both strings have equal matrix width. They become `std::bitset`; **rightmost character is bit 0**. `cont` defaults false. [netload/NLHandler.cpp:763–779; netload/NLJunctionControlBuilder.cpp:373–410]

Road-only import pseudocode (walking-area exclusions follow the cited loops):

```text
L = concatenate(lane.links for lane in junction.incLanes in stored order)
# exclude links into walking areas, and walking-area -> non-crossing links
for i, link in enumerate(L):
    R = response[i]; F = foes[i]
    link.foeLinks = []
    for c in setBits(R):
        link.foeLinks += L[c]
        # include approach at a second stop line too
        if L[c].via and L[c].via.links[0].via:
            link.foeLinks += L[c].via.links[0]
    link.foeInternalLanes = []
    li = 0
    for c in range(len(L)):
        if L[c].target == null: continue
        if F[c]:
            lane = junction.intLanes[li]
            link.foeInternalLanes += lane
            if link.target.isCrossing or R[c] or L[c].indirect or bidiConflict:
                if lane has exactly one incoming lane and that lane is internal:
                    link.foeInternalLanes += lane.incoming[0].lane
        li += 1
    link.requestIndex = i
    link.hasFoes = junction.logic.hasFoes()  # junction-level, not len(foeLinks)>0
    link.cont = cont[i]
    if link.via and not link.cont:
        exit = link.via.links[0]
        exit.setRequest(i, hasFoes=false, cont=false,
                        foeLinks=[], foeInternalLanes=link.foeInternalLanes,
                        internalLaneBefore=link.via)
```

This is the algorithm in [microsim/MSRightOfWayJunction.cpp:60–174]. In addition a local `foes` vector is built from F, including second-stage links; do not confuse that geometric conflict collection with the R-derived `myLinkFoeLinks`. [microsim/MSRightOfWayJunction.cpp:93–125]

Interpretation: R is directed yielding against *approaching* traffic; F is physical interference used to see traffic *inside* the junction, including traffic whose current signal is now red. R need not be symmetric; reducing F to R loses occupied-junction protection. [microsim/MSRightOfWayJunction.cpp:93–159; microsim/MSLink.cpp:1598–1632]

### Internal junction / second stop point

`cont=true` means the entry link may proceed to a further decision point inside the junction: after the red gate, `opened` immediately returns true for a cont link when internal lanes are enabled. It does **not** mean the whole turn is unconditionally clear. The first internal lane ends at an `MSInternalJunction`, followed by another internal via lane and its exit. [microsim/MSLink.cpp:856–863; microsim/MSRightOfWayJunction.cpp:153–159; microsim/MSInternalJunction.cpp:60–68,117–122]

Internal-junction initialization uses its first incoming lane as the special controlled lane. Read that lane's incoming link's request index in the parent ROW junction. For its `intLanes`: if a lane's outgoing link has a via, include the lane before the second stop only if parent response has its entry-index bit (or indirect bicycle exception); include the post-stop via regardless, deduplicated. Without a via include the lane itself. For incoming lanes after the first, include links whose corresponding entry index is in parent response, plus their second-stage links. Set the special lane's outgoing link to `(ownIndex,true,false,internalLinkFoes,internalLaneFoes)`; give the final exit no approach foes but the same internal-lane foes. [microsim/MSInternalJunction.cpp:60–122]

### Worked four-way priority example (constructed, straight-only)

Take a right-hand four-arm intersection with one incoming lane per arm, only straight connections. North/south is the priority road. Explicitly choose `incLanes="N_in_0 E_in_0 S_in_0 W_in_0"`; connections then give indices 0=N→S, 1=E→W, 2=S→N, 3=W→E. Assume opposing straights occupy disjoint lanes, perpendicular straights intersect, and `intLanes=":J_0_0 :J_1_0 :J_2_0 :J_3_0"`. This is an illustrative valid matrix, not a claim about netconvert's automatic compass ordering. Mapping rules: [microsim/MSRightOfWayJunction.cpp:60–74,93–159].

```xml
<request index="0" response="0000" foes="1010" cont="0"/>
<request index="1" response="0101" foes="0101" cont="0"/>
<request index="2" response="0000" foes="1010" cont="0"/>
<request index="3" response="0101" foes="0101" cont="0"/>
```

Set states `[M,m,M,m]`. Link 1 yields to approaching links `[0,2]`, but its internal foes are `[:J_0_0,:J_2_0]`; link 0 has no approaching foes yet still has internal foes `[:J_1_0,:J_3_0]`. Major traffic can therefore drive through a pending side-road request while still braking for a side-road vehicle physically in its way. With a foe 0 window [10,12] s and ego 1 window [11,13], ego is blocked. With ego [8,9] and default gap 1 s, `10 > 9+1` is false: equality still blocks. Ego leave=8.9 permits going first if there is no merge-speed conflict. [microsim/MSLink.cpp:950–958,1190–1235,1598–1632]

For a left-turn variant, split its internal path at the crossing of the opposing straight, set its entry request `cont=1`, and build the internal junction as above. Entry may advance into the turn, then the second link yields to the opposing straight. Replacing that path by one indivisible entry reservation loses internal waiting capacity. [microsim/MSInternalJunction.cpp:60–122; microsim/MSLink.cpp:860–863]

## 2. Approach registration, permission and temporal conflicts

### Time and records

SUMOTime is milliseconds, independent of `DELTA_T`; seconds conversion is `/1000`, and `Q(x)=TIME2STEPS(x)` rounds `1000*x` to nearest integer, away from zero at halves. Do not round every arrival to the simulation-step boundary. [utils/common/SUMOTime.h:58–65]

Each approaching vehicle registers the following per link:

```text
{vehicleID, arrivalTime, leavingTime, arrivalSpeed, leaveSpeed,
 willPass=setRequest, arrivalSpeedBraking, waitingTime,
 dist=distanceToLink, speed=currentSpeed, latOffset}
leavingTime = arrivalTime + Q((link.length + vehicle.length)
                             / max((arrivalSpeed+leaveSpeed)/2, NUMERICAL_EPS))
# MAX arrival sentinel propagates unchanged
```

The microscopic container is keyed by vehicle pointer and `emplace` keeps the first registration if a looped route visits the link multiple times. It is not a single “next vehicle” variable. Registration iterates the entire planned drive-item vector, including downstream links, removes previous records on action steps, and retains records on non-action steps. At all-way stops it adds a random 0 or 1 **millisecond** to arrival to break ties. [microsim/MSLink.cpp:726–766,845–847; microsim/MSVehicle.cpp:5495–5506]

Arrival is `t-DELTA_T + CF.minimalArrivalTime(distance, v, arrivalSpeed)` for Euler (v is this step's planned speed), using current speed for ballistic; add remaining scheduled-stop duration if stopped. Arrival speed incorporates visibility-related slowing at minor links; leave speed estimates acceleration over link length capped by the via/target vehicle speed limit. Braking arrival speed is zero if stopping is feasible, otherwise the CF minimal arrival speed, capped by normal arrival speed for Euler. [microsim/MSVehicle.cpp:2968–2993,3023–3063,3169–3183]

`willPass=false` is meaningful: a vehicle can have an approach record but must not block a foe's temporal conflict check. It is a planned request, not an irrevocable award of entry. `waitingTime` controls stop obligations and precedence; arrival/leave speeds also control merge safety. `dist` and current `speed` support impatience and zipper extrapolation. [microsim/MSLink.cpp:1128–1235,2176–2298]

### opened and blockedByFoe

Ordinary road path, in branch order:

```text
opened(ego):
    if redOrRedYellow and not ignoreRed: false
    if cont and internalLanes: true
    compute ego leaveTime
    check lateral/sublane conflicts if enabled
    if (priority or rememberedContMajorGreen or exitOfContWithEntryG)
       and state != Z: true
    if state==w and waitingTime < Q(jmAllwayStopWait default TS): false
    if state==s and waitingTime < Q(jmStopSignWait default TS): false
    for foeLink in responseDerivedFoeLinks:
        if foeLink.blockedAtTime(egoWindow, sameTargetLane, ...): false
    true
```

With `collectFoes` the routine accumulates blockers instead of early return. Bidirectional and pedestrian checks add exceptions. The remembered cont state allows clearing the turn after its entry signal changes. [microsim/MSLink.cpp:852–1038]

Exact vehicle conflict test, with `(a,l,va,vl)` ego and `(fa,fl,fva,fvl)` foe, `h=Q(jmTimegapMinor default 1 s)`; on a **foe link** of state Z, h=16 s:

```text
if !foe.willPass: return false
if foeLink.state == w:
    delta = now - foe.lastActionTime
    if ego.wait > foe.wait + delta: return false
    if ego.wait == foe.wait + delta and a < fa + delta: return false
faEffective = impatienceAdjustedArrival(fa) # below, otherwise fa
if fl < a:
    return sameTarget && (a-fl < h || unsafe(fvl, va, foeDecel, egoDecel))
else if faEffective > l+h:
    return sameTarget && unsafe(vl, foeBrakingArrivalSpeed, egoDecel, foeDecel)
else:
    return true
unsafe(vLeader,vFollower,bLeader,bFollower) =
    vLeader²/bLeader <= vFollower²/bFollower
```

Crucial asymmetry: for crossing paths a foe that has **already cleared** does not need a trailing 1-second buffer. The buffer applies when ego goes before the foe; same-target merges additionally use both speed/deceleration checks. Comparisons are strict as shown. [microsim/MSLink.cpp:1128–1235; microsim/MSLink.h:732–735; microsim/MSLink.cpp:72–74]

`blockedAtTime` skips ego itself, implements probabilistic ignoring by `jmIgnoreFoeProb`/`jmIgnoreFoeSpeed`, and after a remembered cont-red ignores halting foes. Pedestrian windows instead use symmetric overlap expanded by h and a braking-feasibility check. `hasApproachingFoe(a,l,v,b)` checks R-derived foe windows with zero impatience/wait and also returns true if *any* F-derived foe lane has full or partial vehicles. This is more conservative than geometric leader filtering. [microsim/MSLink.cpp:1041–1123,1304–1316]

### Impatience arithmetic

Actual impatience is clamp(type.impatience + influencer.extraImpatience + waitingTime/timeToImpatience,0,1); omit the growth term when timeToImpatience is nonpositive. The registered default is **180 seconds**, despite its description saying 300. Preserve this growth for normal drivers. [microsim/MSBaseVehicle.cpp:1234–1237; microsim/MSFrame.cpp:543–544,1182]

Only if `I>0 && a<fa`, compute a delayed foe arrival under assumed braking. If `floor(a/DELTA_T)==floor(fa/DELTA_T)`, return fa unchanged. Otherwise ceil a to next simulation step, and, in seconds:

```text
m = foe.maxDecel * I
D = seconds(fa-a); d = D*m; A = D*d/2
v = foe.dist / seconds(fa-now+DELTA_T)
xDist = foe.dist - v*seconds(a-now)
if v²/(2*m) <= xDist:
    faBrake = fa + Q(30); foeBrakingArrivalSpeed = 0
else:
    x = (-0.5*sqrt(4*(v-d)²-8*m*A)-d+v)/m
    foeBrakingArrivalSpeed = v-(D+x)*m
    faBrake = fa + Q(x)
faEffective = integerCast((1-I)*fa + I*faBrake)
```

The original foe leaving time is unchanged. Thus impatience is not “subtract h”: it assumes the priority vehicle can brake and interpolates the delayed arrival. The caller uses I=1 if ego cannot brake normally. [microsim/MSLink.cpp:1171–1194,1240–1299; microsim/MSVehicle.cpp:3796–3803]

Constants: NUMERICAL_EPS=0.001 and halting speed=0.1 m/s. [config.h.cmake:236; utils/common/StdDefs.h:62]

### State alphabet and special control

All enum values and characters are listed below. Uppercase A–Z is the actual `havePriority()` test, so `Y`, `O`, `Z` satisfy it; Z is explicitly excluded from unconditional opening. [utils/xml/SUMOXMLDefinitions.h:2072–2102; microsim/MSLink.h:473–497; microsim/MSLink.cpp:950–972]

|State|Vehicle treatment|
|---|---|
|G major green|priority, subject to downstream/internal physical obstruction|
|g minor green|yield to response foes|
|r red; u red-yellow|closed unless explicit ignore-red logic|
|Y major yellow; y minor yellow|stop if feasible; vehicle caller permits proceeding when yellow cannot be stopped for|
|o off blinking|minor/yield branch|
|O off no signal|priority branch|
|M major|priority branch|
|m minor|yield branch|
|= equal priority|yield via response matrix, with circular-yield deadlock handling|
|s stop|stop-sign wait first, then yield|
|w all-way stop|stop wait first; longer waiting time wins, then earlier arrival|
|Z zipper|collect blockers and adapt speed to merge|
|- dead end|no uppercase priority; normally no usable continuation|

[netbuild/NBNode.cpp:2591–2626] There is no extra `priority-stop` LinkState: priority-stop junctions express their minor-road obligation with state s and their through-road priority with M. `mustStop()` recognizes s,w. [utils/xml/SUMOXMLDefinitions.h:2072–2102; microsim/MSLink.h:496–497; microsim/MSLink.cpp:959–967]

Right-before-left is encoded by the loaded response matrix. For `=` with waiting time>0, follow closest requesting foes up to 100 links to detect a cycle. On returning to own link, withdraw request with probability .25 for straight, .75 otherwise. A GPU implementation that only applies deterministic simultaneous yielding can deadlock forever. Minor movements also slow before the visibility point (default 4.5 m), even if no foe ultimately blocks. [microsim/MSVehicle.cpp:2969–3020,3842–3872]

Zipper is a speed negotiation rather than a stop-only conflict. Beyond `max(visibility,CF.brakeGap(vSafe,b,TS))`, return vSafe. Among collected foes ignore one arriving later unless ego can easily brake behind it; also ignore a foe that can brake behind ego. Equal arrival and distance favor smaller ego lane index. For each retained foe estimate terminal speeds by acceleration over remaining distance; round time to arrival upward to TS, with minimum 1 second. Target ego arrival is foe arrival estimate plus ego headway. Compute acceleration to avoid earlier arrival, normal followSpeed on virtual gap `egoDist-foeLength-egoMinGap-foeDist`, then:

```text
vSafeGap=max(vFollow, egoV + aAvoid*TS)
w=min(1,egoEstimatedArrivalSeconds/10)
bBlend=w*normalDecel+(1-w)*emergencyDecel
vZipper=max(vFollow,egoV-bBlend*TS,vSafeGap)
vSafe=min(vSafe,vZipper)
```

This and its braking-order predicates are implemented in [microsim/MSLink.cpp:2176–2298]; caller selects this branch when `opened` fails for Z [microsim/MSVehicle.cpp:3895–3897]. A simple alternating merge is a proposed approximation, not the source algorithm.

### Keep-clear and exit storage

`opened()` alone does not prevent blocking the box. Vehicle planning runs `checkRewindLinkLanes`: available space starts at negative lengths of vehicles ahead. For internal via lanes with keep-clear enabled subtract their gross vehicle length occupancy **without adding internal lane length**; without keep-clear add space until the last standing vehicle. For empty normal exit lanes add lane length; occupied normal exits contribute space to standing vehicles, with further handling for oncoming traffic and braking. Propagate downstream space backward only over allowed continuations, stopping propagation at stopped traffic/closed links. [microsim/MSVehicle.cpp:5257–5357,5380–5425]

If stopped traffic is found and `availableSpace - ego.lengthWithGap < 0`, mark requests from that link onward for cancellation when keep-clear applies. Cancel if distance >= normal brakeGap+POSITION_EPS; preserve the exit request if entry is already requested, and do not rewind the first link of a vehicle already internal. This avoids trapping a vehicle after granting entry. `keepClear(link)` requires both link.hasFoes and connection.keepClear; `jmIgnoreKeepClearTime` default -1 preserves it indefinitely, otherwise disables it after accumulated waiting reaches that threshold. [microsim/MSVehicle.cpp:5428–5488,7598–7603]

GPU baseline proposal: use downstream standing-queue storage minus upstream commitments, not merely `exitLane.vehicleCount==0`. Reserve length+gap for entrants to the same exit in a separate allocation pass; otherwise individually valid admissions can overfill the exit. Preserve physical internal occupancy after entry. The need for these conditions follows from the space and request-rewind branches above; the reservation algorithm is a GPU design choice.

## 3. Vehicles already inside: geometric leaders

`getLeaderInfo` normally applies to links starting at internal lanes (exit links and second-stop links), not the external entry link. It examines every full/partial vehicle on each foe lane. Distance to crossing on ego path is `dCross=dist-conflict.lengthBehindCrossing`; foe crossing coordinate is `sFoe=foeLane.length-conflict.foeLengthBehindCrossing`. Same source/target gets zero crossing width, with separate merge logic. [microsim/MSLink.cpp:1598–1635,1680–1698]

Conflict geometry is precomputed from shape intersections and lane widths; angle-dependent width factors move the conflict start backward by half the resulting width; geometric offsets are converted to lane positions. For angle difference theta, widthFactor=2/max(sin(theta),0.2)-1 and conflictSize=min(foeWidth*widthFactor,egoLaneLength). Subtract half this width from the intersection offset, clamp at zero and convert geometry offsets to simulation lane positions. Store both path coordinates, widths and conflict flags per lane pair, not a single junction center. [microsim/MSLink.cpp:340–417]

Core road-vehicle screening:

```text
backDist = sFoe - (foe.backPositionOnFoeLane - jmExtraGap)
sagitta = radius - sqrt(radius² - .25*(ego.length+2)²) # curved ego path
past = backDist + foeCrossingWidth + sagitta < 0
entered = backDist < foe.length
ignore own vehicle
ignore ordinary nonmerging foe if past
ignore crossing once ego is past it and foe is not in the way
# retain same-target/source and cont-lane exceptions
virtualGap = dCross - ego.minGap - backDist - foeCrossingWidth
```

The returned items feed car-following constraints; a cont-lane blocker can force gap=-infinity rather than an ordinary following gap. Vehicles stopped before a conflict with `willPass=false` can be ignored, but a vehicle physically in the way cannot simply disappear because it stopped requesting. `jmExtraGap` defaults 0. Long-waiting blockers are ignored after gIgnoreJunctionBlocker; default -1 means never and is converted to maximum SUMOTime. [microsim/MSFrame.cpp:401–402,1178–1179] [microsim/MSLink.cpp:1622–1635,1680–1763,1856–1905]

**Effect estimate (inference):** low load with protected greens can often be matched by approach windows alone; permissive left turns, wide junctions, short exits and signal transitions require these leaders to reproduce clearance and spillback. Blocking every conflicting internal lane until empty is safe but too conservative: it forbids movement after a foe's rear has passed the actual crossing. Ignoring internal lanes is optimistic and can create overlap/gridlock artifacts. These conclusions follow from the `past`/`entered` tests and lane association above, not from a measured SUMO benchmark.

## 4. Traffic lights

Base `MSTrafficLightLogic` owns link groups and applies `phase.state[i]` to every link registered with TLS index i. Indexing is left-to-right from character zero, unlike request bitstrings. Signal changes call `MSLink::setTLState`, maintaining last-change time. [microsim/traffic_lights/MSTrafficLightLogic.cpp:402–411; microsim/MSLink.cpp:1345–1355]

`MSSimpleTrafficLightLogic` advances to explicit first `next` phase when present, otherwise increments modulo phase count; returns new phase duration for next switch. Yellow/all-red are ordinary explicitly supplied phases; do not synthesize transitions between arbitrary state strings. [microsim/traffic_lights/MSSimpleTrafficLightLogic.cpp:80–109]

For duration sum C, initial cycle position is `positiveModulo(now-offset,C)`; positive offset delays the program. Subtract phase durations while position>=duration; selected phase's next switch is `now+duration-position`. This handles nonzero simulation begin, negative offsets and exact boundaries. [netload/NLJunctionControlBuilder.cpp:218–255]

On approach, use:

```text
bStop = max(min(tls.yellow.min-decel, emergencyDecel), normalDecel)
# default tls.yellow.min-decel = 3 m/s²
canStopAtLine = distance-stopOffset >= CF.brakeGap(speed,bStop,0)
```

Planning stops for red/yellow when feasible. Execution separately uses `canBrake = distance>CF.brakeGap(speed,normalDecel,0)` or (Euler and speed<normalDecel*TS). A yellow with canBrake and no ignore-red uses waiting speed; otherwise the yellow caller bypasses `opened`. Red/red-yellow remain closed in `opened`. Preserve these two stages: replacing them with “always stop yellow” changes lost time and causes abrupt braking. [microsim/MSFrame.cpp:521–522; microsim/MSVehicle.cpp:2792–2807,2935–2946,3773–3803; microsim/MSLink.cpp:856–863]

`jmDriveAfterRedTime` default -1 disables red running. For a nonnegative value, yellow is always ignored; on red, ignore if cannot brake or elapsed time since state change is strictly less than the parameter. It describes permission shortly **after red begins**, not permission after waiting at red for a long time. With disabled red running, `jmDriveAfterYellowTime` default 0 optionally permits yellow for its initial duration or when braking is impossible. Beyond the stop line is also an ignore-red case. [microsim/MSVehicle.cpp:3781–3783,7610–7649]

### Actuated and delay-based

Actuated defaults `max-gap=3 s`, `detector-gap=2 s`; detector positioning, usable links and jam detection affect which detector is relevant. Ordinary `gapControl`: only green phases can extend; no extension at maxDuration, max link duration or latest permitted end. Examine detectors serving current phase; an unjammed detector with actual gap<its maxGap keeps the phase alive. Default single-successor mode returns an extension; otherwise choose the next configured phase. Queue vehicles that passed the detector in earlier phases are not directly seen by gap control, which is why minDur must flush them. Custom conditions, multiple successor targets and per-link timing add behaviour beyond this minimal mode. [microsim/traffic_lights/MSActuatedTrafficLightLogic.cpp:59–64,155–250,818–873,942–985]

Proposed simple GPU implementation:

```text
if elapsed<minDur: hold
else if elapsed>=maxDur: next
else if green && any(servedDetector.gap<maxGap && !jammed): hold until next tick
else: next
```

Keep detector occupancy/last detection from vehicle crossing events, not number of queued vehicles at the stop line. Fixed yellow/all-red durations remain unchanged. This is an approximation of the cited simple branch; evaluate green split and throughput distributions before accepting it.

Delay-based uses lane-area detector vehicles and estimates passage time/time loss, not induction-loop gap alone. At green, propose an extension, clamp upward by `minDur-elapsed`; if competing approaches are empty allow at least 1 s extension, otherwise cap to maxDur. Unless `extendMaxDur=true`, cap to maxDur even when others are empty. On expiry advance modulo phase count, initially schedule the next phase by its minDur/earliest constraints. [microsim/traffic_lights/MSDelayBasedTrafficLightLogic.cpp:48–61,130–200,205–259]

### Additional-file tlLogic

Additional definitions go through the same builder after the network is loaded. Key programs by `(tlsID,programID)`; do **not** claim that an additional full program with the same key silently replaces the net. A preexisting ordinary program with a new full set of phases raises duplicate-program error; an empty-phase definition may modify its offset. A different programID creates another program and makes it active: the builder uses newDefault=true, copies controlled-link associations, deactivates the old program, activates the new one and applies its state. [microsim/traffic_lights/MSTLLogicControl.h:260–261; microsim/traffic_lights/MSTLLogicControl.cpp:104–146,601–611] Railway preexisting programs instead update parameters. Thus to override net timings load a distinct program ID, which becomes active through loading; preserve controlled links across programs. [netload/NLJunctionControlBuilder.cpp:207–255,498–504; netload/NLHandler.cpp:684–688]

## 5. Teleports, collisions and insertion queues

Defaults: `time-to-teleport=300 s`; nonpositive disables normal jam teleport. `time-to-teleport.highways=0` (disabled), disconnected=-1 (disabled), `time-to-teleport.remove=false`. `collision.action=teleport`, pedestrian collision action=warn. `max-depart-delay=-1` means never discard a departure merely for lateness. [microsim/MSFrame.cpp:410–420,449–483]

Lane movement chooses `firstNotStopped`: first eligible vehicle in its downstream-first scan that is not in a scheduled stop and whose front lane is this lane. After movement, teleport when waiting time is **strictly > threshold**, with type-specific overrides, disconnected/highway/bidi/rail branches. This is not “teleport every queued vehicle older than 300 s” in parallel. Reason labels distinguish wrong lane, yield, jam, blocked; remove from lane then call transfer unless remove-gridlocked is enabled. [microsim/MSLane.cpp:2390–2459]

Transfer pseudocode, excluding parking/jumps/taxis:

```text
startTeleport(v):
    removeFromNetwork(v)
    if no next route edge: schedule removal; return
    advance route cursor to next edge virtually
    transfers += {v, proceedTime=-1}
eachStep:
    process transfers in numerical vehicle ID order
    choose least occupied lane permitting continuation to next route edge
    try freeInsertion(speed=min(laneLimit,vehMax), positionArgument=0)
    if successful: remove transfer; emit end-teleport
    else if proceedTime<0:
        proceedTime=now+Q(currentEdge.currentTravelTime(minSpeed=1m/s))
    else if proceedTime<now:
        if route ends: remove vehicle
        else advance virtually one edge and schedule next virtual traversal
```

Teleport does not respawn on the blocked lane or instantly vanish permanently: it can skip along the route while trying insertion. The 1 m/s is a floor for virtual travel-time estimation, not reinsertion speed. [microsim/MSVehicleTransfer.cpp:43,56–75,96–102,161–207]

Departure lateness is checked by insertion control with strict `time-depart>maxDepartDelay` when the limit>=0. Keep a distinct not-yet-inserted queue and account for discarded vehicles separately from congestion teleports. [microsim/MSInsertionControl.cpp:166–174,195–204]

Inference for experiments: teleporting is a congestion relief mechanism that changes observed jam lifetime and vehicle counts. Match these settings between CPU/GPU runs and report teleports, arrivals and failed departures alongside throughput; otherwise a simulator that artificially removes jams can look faster. The mechanisms motivating this recommendation are the lane/transfer/insertion branches above.

## 6. Rerouters, ring routes and repeated edges

Triggered rerouters parse time intervals, destination alternatives, route alternatives, closures of edges/lanes, and additional choices such as via/parking. Route alternatives are weighted distributions over existing route IDs. Closures can temporarily change permissions; route choice uses routes avoiding closed edges. On entering a trigger, test active interval and application probability, then possibly replace the vehicle's route. Rerouting is not implicit at every intersection. [microsim/trigger/MSTriggeredRerouter.cpp:130–235,359–407,503–528,675–683]

A ring topology alone does **not** make a vehicle circulate indefinitely: the route is an ordered sequence and ends. A route may repeat edges; keep `(routeID,routePosition)` rather than locating progress by edge ID. `<route edges="a b c" repeat="N">` expands to N additional copies, after checking final-to-first connectivity; stops with absolute until/arrival need cycleTime to repeat. It is finite, not an infinity flag. [microsim/MSRouteHandler.cpp:366–378,445–492]

Concrete finite experiment: connected ring edges `[a,b,c,d]`, use `edges="a b c d" repeat="100000"` with horizon short enough that no vehicle exhausts the expanded route. Avoid repeating a single edge unless a self-connection exists. For truly unbounded GPU operation, use a cyclic route cursor modulo ring length as an explicit extension, or renew routes at a rerouter; validate against the finite long SUMO route. Repeated visits to the *same link in one lookahead* must preserve only the first arrival per vehicle, matching microscopic emplace. [microsim/MSRouteHandler.cpp:459–467; microsim/MSLink.cpp:741–750; microsim/trigger/MSTriggeredRerouter.cpp:675–683]

## 7. GPU architecture and approximation budget (proposed)

### Static buffers

```text
Link[i] = {beforeLane,targetLane,viaLane,requestIndex,tlsID,tlsGroup,
           dir,baseState,cont,keepClear,hasFoes,length,visibility,
           foeBegin,foeCount,internalFoeBegin,internalFoeCount}
foeLinkIDs[]      # CSR: concatenate directed R lists, including second-stop links
internalFoeIDs[]  # separate CSR: F lanes and selected first-stage predecessors
Conflict[]       # paired path positions, crossing widths/flags, curvature if retained
TLS[] + Phases[] + phaseStateBytes[]
Approach[link][K] # ID + all temporal fields in §2
```

Do not compact R and F into one list, or use tlsGroup as requestIndex. These distinctions are required by the import algorithms. [netload/NLHandler.cpp:1466–1514; microsim/MSRightOfWayJunction.cpp:93–159]

### Two semantic phases, multiple dispatches

```text
snapshot positions, speeds, lane occupancy, routes and TLS state
clear per-link counts/overflow flags
PHASE 1 (parallel per vehicle):
    generate drive items over braking/lookahead route horizon
    compute free/stop speeds, visibility slowing, arrival/leave estimates
    compute keep-clear request flags from snapshot exit storage
    for each distinct upcoming link: # retain first occurrence
        slot=atomicAdd(count[link],1)
        if slot<K: write complete record to Approach[link][slot]
        else: overflow[link]=1; append to overflow buffer
END DISPATCH # WGSL workgroupBarrier is NOT a device-wide barrier
optional gather/sort/resolve overflow; barrier at dispatch boundary
PHASE 2 (parallel per vehicle):
    apply red/yellow/stop/priority/cont branch ordering
    inspect foe slots read-only using exact asymmetric temporal arithmetic
    inspect geometric internal occupancy, normal leaders and exit capacity
    choose speed/entry request
resolve competing exit capacity and deterministic lane ordering
integrate all vehicles simultaneously into next-state buffers
```

This preserves the approach-then-decision dependency visible in registration/opened, but is not a claim that SUMO itself uses this exact parallel schedule. Decisions should not recursively modify foe records within phase 2. A resolved entry denial becomes next step's request update; otherwise GPU dispatch order leaks into traffic outcomes. Physical storage allocation must happen before integration, especially where priority links bypass temporal checking. [microsim/MSVehicle.cpp:5495–5506,3773–3803; microsim/MSLink.cpp:950–958]

### How large must K be?

**No finite universal K=3 or 4 reproduces SUMO.** SUMO iterates an unconstrained per-link approaching-vehicle container and registers many drive items per vehicle, including nonpassing records and repeated-route handling. A downstream link can be approached from several upstream lanes. Counting only the nearest vehicle per source lane is therefore not equivalent. [microsim/MSLink.cpp:726–766,1043–1068; microsim/MSVehicle.cpp:5499–5506]

Use K=4 as an initial fast-path allocation **only with complete overflow fallback**. At load/run time, measure per-link simultaneous registration maxima, number of willPass records, and overflow frequency by demand regime. For a workload to run with no fallback, K must be at least the maximum number of relevant simultaneous registered vehicles on every link throughout that workload; there is no source-supported numerical “practical K” independent of demand, lookahead, action step and topology. The zipper lookahead of 16 s makes truncation particularly risky compared with ordinary 1 s conflicts. [microsim/MSLink.cpp:72–74,1043–1068,1190–1194]

Atomic append order is arbitrary, so retaining the first K arriving GPU threads is unacceptable. Optional optimization: retain earliest arrivals using deterministic `(arrivalTime,vehicleID)` ordering, but still retain overflow records or rerun overflow links through a count/prefix-sum CSR gather. Even earliest K can miss a later-arriving foe that overlaps a later ego window, or a waiting-time winner at all-way stop. [microsim/MSLink.cpp:1150–1168,1203–1235]

Overflow choices, in descending fidelity:

1. Count+prefix-sum gather all records into global CSR; exact, bounded by total generated drive items, requires additional dispatches.
2. K fast path plus overflow CSR, read both; exact if overflow allocation itself cannot drop records.
3. Set overflow links closed conservatively for affected minor movements; prevents optimistic conflicts but depresses throughput and may create artificial gridlock.
4. Drop overflow silently; can miss blocking vehicles, admit conflicting traffic, misorder stop/zipper traffic and overstate flow. Never accept this for comparability.

These are design alternatives inferred from SUMO's all-record iteration and branch predicates, not measured claims. Also maintain internal-lane occupancy independently: adding more approach slots cannot substitute for vehicles' rear-position crossing tests. [microsim/MSLink.cpp:1043–1068,1680–1698,1856–1905]

### Ranked implementation priorities / validation

The ranking is engineering judgment based on the source dependencies, not a measured sensitivity study.

|Priority|Keep / approximate|Expected affected observables and source basis|
|---|---|---|
|1|Keep phase timing, G vs g, yellow feasibility, request indexing and directed R|green split, lost time, side-road gaps and junction throughput; §1–2, §4|
|1|Keep CF queue discharge and visibility slowing; use vehicle length in leaveTime|saturation flow, start-up and minor-road acceptance; MSVehicle.cpp:2969–2993; MSLink.cpp:845–847|
|1|Keep internal lanes, second stops, geometric crossing clearance and exit keep-clear storage|permissive turns, storage, spillback/gridlock; MSInternalJunction.cpp:60–122; MSVehicle.cpp:5257–5488|
|1|Keep teleport/departure settings matched and count their effects|jam duration, density and conservation; MSFrame.cpp:449–483; MSVehicleTransfer.cpp:161–207|
|2|Keep asymmetric 1 s window and merge speed/decel checks|priority gap acceptance and merging; MSLink.cpp:1190–1235|
|2|Keep stop/all-way waiting and random tie breaking, RBL cycle breaking|stop throughput and false deadlocks; MSLink.cpp:959–967,1150–1168; MSVehicle.cpp:2999–3020,5502–5506|
|2|Keep zipper speed adaptation where present; initially approximate by ordered merge plus virtual CF leader|merge flow and braking waves; MSLink.cpp:2176–2298|
|2|Simple actuated detector gap-out with true min/max duration; use full delay-based only if scenario uses it|phase splits and queues; MSActuatedTrafficLightLogic.cpp:942–985; MSDelayBasedTrafficLightLogic.cpp:205–259|
|3|Keep default impatience growth; omit nondefault ignore-red/ignore-foe customisations unless input uses them|aggressive acceptance, rare conflicts; MSLink.cpp:1059–1068,1171–1194; MSVehicle.cpp:7610–7649|
|3|Drop lateral-shadow, pedestrian/railway/opposite-driving exceptions only in explicitly car-only networks that exclude them|otherwise not comparable for those modes; MSLink.cpp:867–944,979–1010,1076–1120,1930–2005|

Validation proposal: paired networks/demand with multiple independent seeds; compare per-movement discharge headways, throughput, accepted minor gaps, wait/queue distributions, occupied internal-lane time, green splits, spillback duration, teleports and vehicle conservation. Include the constructed four-way fixture, permissive left-turn second stop, all-way ties, four-car right-before-left cycle, saturated zipper, blocked short exit, yellow dilemma zone, and dense closed ring. Sweep K and verify **zero lost records**, then compare distributions rather than trajectories. No claim of statistical equivalence is established by this document alone.

### Additional precise predicates used above

- Direction alphabet: `s` straight, `t` turn, `T` left-hand turn, `l/r` left/right, `L/R` partial left/right. [utils/xml/SUMOXMLDefinitions.cpp:1553–1561]
- Zipper `couldBrakeForLeader(f,l,F,L)` is exactly `f>l && f-l>F.speed-F.maxDecel-L.speed`: this predicate uses a fixed one-second intuition rather than TS-scaled deceleration. [microsim/MSLink.cpp:2326–2332]
- A blocked junction leader suppresses ego's request if planned speed<0.1 m/s and the leader has the same logical predecessor, is on the next lane, is in a scheduled stop, or has waited>5 s (`JUNCTION_BLOCKAGE_TIME`). This is separate from keep-clear space accounting. [microsim/MSVehicle.cpp:122,3673–3697]
- Junction-leader speed adaptation uses CF.followSpeed for nonnegative virtual gap; a negative leader gap stops before entering the occupied lane. If advancement to the crossing is permitted, let `tClear=(dCross-gap)/max(foe.speed,0.1)`, `vFinal=max(ego.speed,2*(dCross-ego.minGap)/tClear-ego.speed)`, `v2=ego.speed+TS*(vFinal-ego.speed)/tClear`; relax the leader constraint up to `min(v2,CF.stopSpeed(dCross-ego.minGap))`. For gap=-infinity the special branch allows driving up to the crossing and stopping. These are needed to avoid stopping all traffic at the external stop line when the conflict is farther inside. [microsim/MSVehicle.cpp:3386–3470]
