# SUMO 1.28 microscopic stepping and longitudinal motion

Contains excerpts of the Eclipse SUMO 1.28 source code, Copyright (C) German Aerospace Center (DLR) and others, under the [Eclipse Public License 2.0](https://www.eclipse.org/legal/epl-2.0/).

Source root: `/home/erikf/projects/personal/thesis-src/sumo/src`. All citations below are relative to that root; line numbers refer to this supplied checkout. Units: metres, seconds, m/s, m/s². `dt=TS`; `DELTA_T` is the integer simulation tick duration, not seconds. `ACCEL2SPEED(a)=a*dt`, `SPEED2DIST(v)=v*dt`, `SPEED2ACCEL(v)=v/dt`, `DIST2SPEED(s)=s/dt`, `ACCEL2DIST(a)=a*dt²`. These conversions are normative throughout the algorithms below. [utils/common/SUMOTime.h:38-70]

The numbered sections give equations and GPU scheduling guidance. The final algorithm annex supplies the exact branch-heavy arithmetic and decisions, with diagnostics/comments removed, so the implementer need not open SUMO. Annex code is a specification reference, not WGSL to compile directly: replace pointers by indices, vectors by spans, and getters by the corresponding state fields. Preserve branch order and calls with state side effects. References to omitted rail, sublane, TraCI, parking and pedestrian helpers are feature boundaries, not implied implementations of those subsystems. [microsim/MSVehicle.cpp:2276-3114,3744-3975; microsim/cfmodels/MSCFModel.cpp:87-260]

## 1. One simulation step and its barriers

Normal micro-simulation sequence (mesoscopic mode excluded):

```text
process TraCI commands; optionally save state
begin-of-step events; rail signal update; wait for routing; event collision checks
TLS check2Switch(t)
patchActiveLanes()
planMovements(t)                 // all lanes complete
setJunctionApproaches()          // all requests visible
executeMovements(t)              // all motion complete, then integrate lane buffers
movement collision checks
changeLanes(t)
lane-change collision checks
removePending(); loadRoutes()
process waiting persons/containers, pending routing; reset rail wait relations
determine insertion candidates; insertion events; wait for routing; emitVehicles(t)
insertion collision checks; transfer/teleport insertions
end-of-step events
postMoveStep()                   // outputs, bookkeeping, advance time
```

`onlyMove` defers postMoveStep and the next simulationStep completes it and returns. TLS switches BEFORE planning, lane changing AFTER longitudinal movement, ordinary insertion AFTER lane changing. A newly inserted vehicle does not travel in this tick. [microsim/MSNet.cpp:808-961; microsim/MSNet.cpp:964-1045; microsim/cfmodels/MSCFModel.cpp:895-902]

| Phase | Reads | Writes | Parallel interpretation |
|---|---|---|---|
| TLS | clock, program/event state, previous detector observations | signal states | Barrier before planning; no per-vehicle Jacobi interpretation |
| planMovements | pre-movement positions/speeds, lane order, route/best-lane continuation, TLS, old controller state | drive-item arrays, stop constraints, next turn, CF controller memory | Kinematics effectively Jacobi; per-lane front-to-back traversal builds leaders and cumulative occupied length. Not globally pure: controller calls mutate own memory and junction blockage logic may inspect other plans |
| setJunctionApproaches | completed drive items | link approach records, requests, arrival/leave estimates | Gather/scatter barrier; do not test priority before all requests exist |
| executeMovements | planned drive items + approach records + current junction state, old own kinematics | speed, position, lane/route progress, waiting, loss, reminders, link bookkeeping | Serial implementation is front-to-back and observably ordered; buffered lane transfer prevents moving a newly transferred vehicle twice. Not safe to call the entire phase pure Jacobi |
| integrate | target-lane buffers after execution | sorted lane membership and occupancy | Barrier before lane changing |
| changeLanes | updated longitudinal positions, changing lane leader/follower caches | memberships, LC state, reservations | Gauss-Seidel within edge: earlier decisions update changer state used by later vehicles |
| insertion | post-move/post-LC occupancy, earlier successful insertions | new lane occupants, departure state, pending candidates | Gauss-Seidel for competing insertions; independent-lane candidates may be parallelized |

Evidence: lane planning merges full, partial and reserved vehicles front-to-back and adds each leader after planning; execution also iterates reverse lane order; transferred vehicles enter `myVehBuffer`, integrated only after the complete lane execution pass. [microsim/MSLane.cpp:1595-1678,2318-2370,2605-2635; microsim/MSEdgeControl.cpp:137-193,197-269; microsim/MSLaneChanger.cpp:190-255; microsim/MSInsertionControl.cpp:120-260]

GPU design inference: double-buffer kinematics for the planning kernel; materialize all drive items, then all approach records, then resolve junction permission, then integrate motion, then resolve LC and insertion conflicts. Treat controller evaluation as one deterministic owner per vehicle: several leader/lookahead calls in one tick are not independent controller-state updates. Fully simultaneous junction decisions/LC/insertion are approximations requiring flow validation, not algebraic equivalents of a serial vehicle loop. [microsim/MSVehicle.cpp:2162-2225,3744-3975; microsim/cfmodels/MSCFModel_ACC.cpp:244-313; microsim/cfmodels/MSCFModel_CACC.cpp:367-500]

## 2. Planning and lane lookahead

`planMove` updates driver state when present, raises the cached stop-speed bound by maxNextSpeed, and checks the action clock. Non-action ticks remove passed drive items and reuse the plan. Action ticks swap old/new plans, call planMoveInternal, rewind requests for downstream space, and reset drive-item cursors. [microsim/MSVehicle.cpp:2162-2273]

Ordinary forward-driving pseudocode (special features retain their annex branches):

```text
maxV = CF.maxNextSpeed(speed)
maxVD = max(vehicleMax, min(maxV, desiredMax))
laneLimit = max(lane.vehicleMaxSpeed(ego,maxVD), CF.minNextSpeed(speed))
v = CF.maximumLaneSpeedCF(ego,maxV,laneLimit)
horizon = maxV*dt + CF.brakeGap(maxV)
seen = lane.length - position
vLinkPass = min(estimateSpeedAfterDistance(seen,v,accel),laneLimit)
for lane along best-lane continuation, including via/internal lanes:
    adaptToLeaders(ahead,seen,lastItem)  // updates v and vLinkPass
    apply stops, pedestrians, shadow-lane/oncoming/conflict restrictions if enabled
    if route final edge:
        arrivalV = specified arrivalSpeed, else laneLimit
        d = seen + arrivalPos - lane.length - arrivalV*dt
        v = min(v, max(eps, CF.freeSpeed(speed,d,arrivalV)))
        append terminal item; break
    if dead end: cap by CF.stopSpeed(speed,seen); append terminal item; break
    compute stopping-line waiting bound, request, signal/conflict-leader bounds
    compute arrival speed/time, braking arrival speed, estimated leave speed
    append link item
    if stop/request/horizon termination AND enough downstream storage seen: break
    advance to viaLaneOrLane; cap v for its limit via CF.freeSpeed
    ahead = nextLane.getLastVehicleInformation(nullptr,0)
    seen += nextLane.length
    vLinkPass = min(estimateSpeedAfterDistance(nextLane.length,v,accel),nextLimit)
```

The horizon is not a hard distance cap. Termination requires `(!setRequest || v<=0 || seen>horizon) && hadNonInternal && seenNonInternal>max(5*vehicleLength, vehicleLength+seenInternal) && foundRailSignal`. Thus a passenger car can inspect beyond braking range to assess at least downstream storage; internal lanes do not advance route edge index. [microsim/MSVehicle.cpp:120,2276-2375,2748-2795,3060-3114]

Leader gaps passed to most CF models already subtract ego minGap. On current lane: `gap=leaderBack-position-minGap`; on a following lane: `gap=leaderBack+seen-lane.length-minGap`. `leaderBack` accounts for partial occupation across lanes. Evaluate all laterally overlapping leaders (one ordinary lane leader without sublanes), take the minimum safe speed. `adaptToLeader` uses leader speed and **current apparent deceleration**, not leader emergencyDecel; an off-route rear in a merge can instead become a stop-before-conflict constraint. It also evaluates FUTURE follow speed using the previous item's accelerated speed and lowers that item's leave speed. [microsim/MSVehicle.cpp:3188-3265,3300-3378]

`checkLinkLeader` asks the link for conflict-area leaders and distinguishes a preceding leader from a crossing foe; it computes crossing clearance/stop constraints, adapts pass/wait speeds, and may withdraw the request when blocked. This is not just searching the next lane's occupant array. See annex for exact conflict branches. [microsim/MSVehicle.cpp:3568-3718]

Drive item semantic contract: `vLinkPass` and `vLinkWait` are ego's candidate speed this tick if a link can/cannot be passed, not simply the speed physically at the link; `arrivalSpeed` is the separate predicted entry speed. Item also stores link index, arrivalTime, arrivalSpeedBraking, distance, leave speed/accelV and downstream availableSpace. `setRequest` means requesting junction priority, not that entry is already granted. Available space is accumulated along the approached lanes, adjusted for standing queues and their length-with-gap, propagated backward, then compared with ego length-with-gap; inadequate storage rewinds requests and caps upstream item speeds to avoid blocking junctions. [microsim/MSVehicle.h:1985-2042; microsim/MSVehicle.cpp:2913-3064,5180-5525]

Arrival-time origin is `t-dt`, not `t`: Euler calls minimal-arrival-time with planned `v`; ballistic uses old current speed. Arrival position is a removal threshold, not by default a mandatory zero-speed stop: final-edge planning targets specified arrivalSpeed or the lane limit. [microsim/MSVehicle.cpp:2748-2770,3169-3185,1130-1136]

## 3. Execution, integration and accounting

On action ticks, processLinkApproaches walks drive items in route order: yellow + able to stop selects wait speed; requested links call `opened` with approach arrival/leave estimates, length, impatience, decel and waiting time. An open link selects pass speed, with priority/minimum-speed and zipper adjustments; closed/non-requested links select wait speed and terminate. Certain uncontrolled-link emergency cases allow continuing when stopping is impossible. It changes waiting/junction-entry bookkeeping while resolving permission. Preserve these branches from the annex; replacing all junctions with a red/green boolean loses priority/yield capacity. [microsim/MSVehicle.cpp:3744-3975]

On non-action ticks `vSafe=v+acceleration*dt`; no new CF finalization. Action ticks call finalizeSpeed then enforce a positive junction minimum if applicable. Very small speeds are zeroed; Euler clips negative vNext, ballistic preserves it until displacement computation. TraCI and special power limits follow. updateState precedes waiting-time accounting; lane traversal updates lane/route and stop progress, then loss is computed using the updated lane. Reminders (including GLOSA) run at the end. [microsim/MSVehicle.cpp:4635-4790,4817-4913]

```text
Euler:     dx = max(0,vNext)*dt
ballistic: a = (vNext-vOld)/dt
           dx = (vOld+vNext)*dt/2              if vNext>=0
           dx = -vOld²/(2*a)                  otherwise (stop inside tick)
stored acceleration = (max(0,vNext)-vOld)/dt
previousSpeed=vOld; speed=max(0,vNext); position+=dx
```

Negative ballistic speed is a stop-time encoding, never actual backward travel. Crossing several short lanes consumes excess longitudinal distance through successive via/route links; maintain further-lane rear occupancy until the vehicle clears it. Arrivals are detected on the last/explicit arrival edge at `pos>min(laneLength,arrivalPos)-POSITION_EPS`, unless a scheduled stop there prevents removal. MSLane schedules removal and transfers other moved vehicles through buffers. [microsim/MSVehicle.cpp:3722-3741,4360-4630,4967-5018,1130-1136; microsim/MSLane.cpp:2327-2356]

Waiting: if `vNext<=haltingSpeed && (!scheduledStopped || idling) && acceleration<=accelThresholdForWaiting`, add dt; otherwise reset consecutive wait to zero. A separate collector preserves intervals for accumulated waiting over a memory window; don't confuse the two counters. Loss, when not scheduled-stopped: `vmax=min(updatedLane.vehicleMaxSpeed, max(stopSpeed,vNext)); if vmax>0: loss+=dt*(vmax-vNext)/vmax`. [microsim/MSVehicle.cpp:208-241,4293-4317]

## 4. Shared car-following arithmetic

Let `b=decel`, `B=emergencyDecel`, `T=tau`, `g` be the net gap after minGap subtraction, `vL` leader speed, `bL` leader apparentDecel. Defaults: T=1, apparentDecel=b, startupDelay=0, collisionMinGapFactor=1. Model-specific overrides are below. [microsim/cfmodels/MSCFModel.cpp:55-69]

Braking distance:

```text
Euler: q=b*dt; n=int(v/q)
       BG(v,b,T)=dt*(n*v-q*n*(n+1)/2)+v*T
ballistic: BG=0 if v<=0 else v*T+v²/(2*b)
secureGap=max(0,BG(v,b,T)-BG(vL,max(b,bL),0))
```

Lane-change secure-gap checks can reduce the gap when ego is already braking, divided by LC safetyFactor; see exact annex. `minNextSpeed=max(0,v-b*dt)` Euler, `v-b*dt` ballistic. Emergency variant substitutes B. `getSpeedAfterMaxDecel` always clips to zero, even ballistic. Base patchSpeedBeforeLC returns vMax. [microsim/cfmodels/MSCFModel.cpp:87-109,178-195,330-350; microsim/cfmodels/MSCFModel.h:120-124,447-449]

Euler safe stop (do not substitute continuous sqrt formula):

```text
g=maxGap-eps; if g<0 return 0
q=b*dt; h=(headway>=0 ? headway : T)
n=floor(0.5-(h-0.5*sqrt(dt²+4*(dt*(2*g/q-h)+h²)))/dt)
d=0.5*n*(n-1)*q*dt+n*q*h
return n*q+(g-d)/(n*dt+h)
```

Ballistic safe stop: g=max(0,gap-eps), h=specified headway or T. On insertion return `-b*h+sqrt((b*h)²+2*b*g)`. Otherwise use `h=dt` if h=0, v0=max(0,currentSpeed). If `g<=v0*h/2`, return `-B*dt` at zero gap with positive v0, zero if also v0=0, otherwise `v0-v0²*dt/(2*g)`. Else `v1=-b*h/2+sqrt((b*h/2)²+b*(2*g-h*v0)); return v0+(v1-v0)*dt/h`. [microsim/cfmodels/MSCFModel.cpp:860-954]

Safe following first calls safeStop on `g+BG(vL,max(b,bL),0)` with decel b and headway T, emergency relaxation disabled. Negative gap outside LC instead requests emergency braking. If requested braking exceeds b, and not inserting/computing LC, replace it by amplified exact emergency deceleration, bounded below by b and above by the original request. Stop-speed emergency relaxation is analogous but enabled by its caller. These calculations do not universally clamp to B; finalizeSpeed supplies its lower speed bound. Annex includes the complete emergency calculation and amplifier definition. [microsim/cfmodels/MSCFModel.cpp:807-856,958-1095]

`freeSpeed` anticipates a target speed at a distance without following headway. Euler uses a discrete braking staircase; ballistic solves the quadratic including current speed and action-step duration. Exact formulas in annex are required at both dt values. [microsim/cfmodels/MSCFModel.cpp:112-174,353-361]

Finalize order:

```text
vStop=min(vPos,processNextStop(vPos))
vE=minNextSpeedEmergency(vOld)
vMin=min(minNextSpeed(vOld), max(vPos,vE))
f=1 if friction==1 else -0.3491*friction²+0.8922*friction+0.4493
aMax=(max(lane.vehicleMaxSpeed,vPos)*f-vOld)/actionStepSeconds
vMax=max(vMin,min(vOld+aMax*dt,maxNextSpeed(vOld),vStop))
v=patchSpeedBeforeLC(vMin,vMax)    // Krauss dawdle here
v=LC.patchSpeed(vMin,v,vMax)
v=applyStartupDelay(vMin,v)
```

maxNextSpeed evaluates desired/max acceleration profiles; maximumLaneSpeedCF returns min(maxNextSpeed,laneLimit), then applies optional own-speed perception error. See annex for acceleration arithmetic. [microsim/cfmodels/MSCFModel.cpp:269-328; microsim/cfmodels/MSCFModel.h:245-249]

## 5. Required longitudinal models

### Krauss (current Krauss, not KraussOrig1)

followSpeed=min(safeFollow(g,v,vL,bL),maxNextSpeed(v)); ballistic additionally floors it by minNextSpeedEmergency. stopSpeed=min(safeStop(g,b,v,headway=actionStepSeconds),maxNextSpeed(v)); emergency relaxation disabled for FUTURE use. Perception errors are optional driver-state effects. [microsim/cfmodels/MSCFModel_Krauss.cpp:127-151]

At patchSpeedBeforeLC draw U uniform [0,1). If ballistic speed bound is negative, preserve it without drawing. Otherwise subtract `dt*sigma*U*(speed if speed<accel else accel)`, clip to zero, and floor by vMin. This is not a fixed speed subtraction independent of dt, and the low-speed branch compares speed numerically with accel. sigma defaults .5; minor-junction sigma may override it. [microsim/cfmodels/MSCFModel_Krauss.cpp:94-123,155-175; microsim/cfmodels/MSCFModel_KraussOrig1.cpp:40-44]

sigmaStep defaults dt and is rounded to the nearest tick. With sigmaStep>dt, sample a held acceleration rather than independent noise every tick: cache accelDawdle, updateOffset, cap the held acceleration to reach the lane limit over sigmaStep, and bound subsequent ticks by the new safe speed. Initial accelDawdle=1e6 and offset=`SIMSTEP % sigmaStep + DELTA_T`; exact update code in annex. No extra Krauss state is allocated for the ordinary per-tick-noise path beyond RNG/state shared with the vehicle. [microsim/cfmodels/MSCFModel_Krauss.cpp:43-62,94-123; microsim/cfmodels/MSCFModel_Krauss.h:92-111]

### IDM

Defaults delta=4, stepping=.25 s, collisionMinGapFactor=.1. N=max(1,int(dt/stepping+.5)), h=dt/N: N=1 at .1 s and N=4 at 1 s. Plain IDM has no dynamic CF memory; IDMM optionally has levelOfService. [microsim/cfmodels/MSCFModel_IDM.cpp:38-50,94-101]

```text
u=v; z=g+minGap if respectMinGap else g
repeat N:
    s=max(0,u*T+u*(u-vL)/(2*sqrt(accel*decel)))
    if respectMinGap: s+=minGap
    z=max(eps,z)
    a=accel*(1-(u/max(eps,desiredSpeed))^delta-(s/z)^2)
    u=max(0,u+a*h)
    z-=max(0,(u-vL)*h)  // gap never grows in internal integration
return max(0,u)
```

followSpeed uses lane vehicle max as desiredSpeed and respectMinGap=true. secureGap=`max(0,v*T+v*(v-vL)/(2*sqrt(accel*decel)))`, without minGap. stopSpeed uses stationary leader, respectMinGap=false; gap<.01 returns zero, a near-rest inability to advance falls back to shared safeStop; bound by gap/dt to prevent overshoot. [microsim/cfmodels/MSCFModel_IDM.cpp:131-135,179-201,218-268]

freeSpeed preserves negative target speed. If speed<=target, call IDM with gap=1e6 and leader speed=target. Else use gap=max(seen,secureGap(target,0)), leader speed=0. Desired speed in both cases remains current lane vehicle maximum. If seen<secureGap(target,0), cap result by target. finalizeSpeed calls base; IDMM then integrates levelOfService toward vNext/laneMax with adaptationTime=600 s and adaptationFactor=1.8 (plain IDM factor=1 and no update). IDM minNextSpeed uses `max(decel,min(emergencyDecel,1.5))`, then Euler/ballistic clipping convention. [microsim/cfmodels/MSCFModel_IDM.cpp:38-48,80-128]

### EIDM (summary only)

EIDM extends IDM with internal integration, reaction/action timing, stochastic perception/estimation, acceleration smoothing and startup behavior; it is not plain IDM with a changed delta. Keep it a separate unsupported model until its stateful temporal behavior is implemented. This is a scope recommendation, not an assertion that plain IDM reproduces EIDM. Defaults include reaction=.5 s, preview=4 s, persistence driving=3 s and estimation=10 s, coolness=.99, leader/gap/error noise=.02/.1/.04, max jerk=3, acceleration threshold=1, startup max-acceleration time=1.2 s, flatness=2 and begin=.7. Its serialized state includes minaccel, wouldacc, lastacc, realacc, lastrealacc, realleaderacc, lastleaderacc, v0_int, v0_old, t_off, three correlated noise variables, estimated leader/ego speeds and gap, respectMinGap and action-update state. [microsim/cfmodels/MSCFModel_EIDM.cpp:45-160; microsim/cfmodels/MSCFModel_EIDM.h:180-300]

### ACC

Defaults: speed gain=-.4; gap closing (speed,space)=(.8,.04); gap control=(.07,.23); collision avoidance=(.23,.8); thresholds 120/100 m; safety override=2 m/s; applyDriverState=false; collisionMinGapFactor=.1. [microsim/cfmodels/MSCFModel_ACC.cpp:58-91]

Let eV=v-desiredSpeed, dv=vL-v, d0=clamp(75/v-5,0,2) (at v=0 take the positive-infinity limit), eG=g-T*v-d0.

```text
speed_control_accel = -.4*eV
 gap_control_accel = .07*dv+.23*eG    if abs(eG)<.2 AND abs(eV)<.1
                  = .23*dv+.8*eG     else if eG<0
                  = .8*dv+.04*eG     otherwise
mode: g>120 -> speed; g<100 -> gap; otherwise previous mode
rawNext=max(0,v+modeAccel*dt)
followNext=min(rawNext,safeFollow+2)
```

Mode/lastUpdateTime mutate only on the first _v invocation at a new simulation timestamp. Desired speed in ACC followSpeed is `min(lane.speedLimit,vehicle.maxSpeed)`. secureGap=.07*(v-vL)/.23+T*v, without clamping and without d0. stopSpeed is shared safeStop with action-step headway, capped by maxNextSpeed; freeSpeed/finalizeSpeed inherited. Interaction gap=250 m. State: ACC_ControlMode and lastUpdateTime; no integral speed-error accumulator. [microsim/cfmodels/MSCFModel_ACC.cpp:122-158,192-313; microsim/cfmodels/MSCFModel_ACC.h:135-192]

### CACC

Defaults: speed gain=-.4; gap closing (gap,gapDot)=(.005,.05); gap=(.45,.0125); avoidance=(.45,.05); headwayTimeACC=1; speedControlMinGap=1.66; safety override=2; driverState=false; collisionMinGapFactor=.1. Embedded ACC's tau is replaced with headwayTimeACC. [microsim/cfmodels/MSCFModel_CACC.cpp:56-102]

```text
eV=v-desiredLaneVehicleSpeed; eG=g-T*v; timeGap=g/max(eps,v)
if commOverride==0:
    timeGap>2 AND eG>1.66 -> speed mode
    timeGap<1.5 -> gap mode
    otherwise retain previous CACC mode
commOverride==1 -> speed mode
commOverride==2 -> embedded ACC
commOverride==3 -> force cooperative gap law
speed law: next=v+(-.4*eV)*dt
normal gap mode:
    no leader -> speed law
    leader CF model != CACC -> embedded ACC
    else cooperative law
cooperative law:
    eDot=vL-v-T*egoStoredAcceleration
    0<eG<.2 AND eV<.1 -> next=v+.45*eG+.0125*eDot
    eG<0             -> next=v+.45*eG+.05*eDot
    otherwise        -> next=v+.005*eG+.05*eDot
if dt<.1: next=v+(next-v)*10*dt
next=max(0,next)
safe=sharedSafeFollow(g,v,vL,bL,onInsertion=true)
return min(next,max(0,safe+min(2,g)))
```

The last return expresses the source's conditional override: if safe+min(2,g)>=next, return next unchanged. Both .1 s and 1 s use the unscaled cooperative increments; do NOT multiply those gap-law increments by dt. Only the speed-control law has dt inherently. The derivative uses **ego acceleration**, not leader acceleration, nor an integral speed error. Leader inputs are speed, model identity, apparentDecel for the safety check and the leader pointer for embedded ACC selection. There is no speedErrorInt in this version's CACC fields. [microsim/cfmodels/MSCFModel_CACC.cpp:147-175,285-500; microsim/cfmodels/MSCFModel_CACC.h:190-239]

State: inherited ACC_ControlMode,lastUpdateTime plus CACC_ControlMode and communications override (initially 0). Vehicle acceleration is common kinematic state. Output caccVehicleMode is informational. getSecureGap=max(baseSecureGap, T*v for CACC leader; else embedded ACC equilibrium gap with headwayTimeACC); stopSpeed shared stop bound with action headway; freeSpeed delegates base and may update informational mode. [microsim/cfmodels/MSCFModel_CACC.cpp:135-145,179-208,385-461; microsim/cfmodels/MSCFModel_CACC.h:190-239]

## 6. GLOSA

Opt-in device, micro mode only. Defaults range=100 m, max-speedfactor=1.1, min-speed=5 m/s, add-switchtime=0 s, use-queue=false, override-safety=false, ignore-cfmodel=false. `<param key="has.glosa.device" value="true"/>` on vType equips its vehicles; it is a boolean generic parameter, not a vType XML attribute nor a percentage. A vehicle-level parameter overrides type assignment; explicit device vehicle IDs take precedence. `device.glosa.range` is a floating-point generic parameter: vehicle > type > global option. At a TLS it is min(vehicle-configured range,TLS range), with absent TLS range=1e10. Range does not equip the device by itself. [microsim/devices/MSDevice_GLOSA.cpp:45-86,310-355; microsim/devices/MSDevice.h:200-259; utils/vehicle/SUMOTrafficObject.cpp:33-86]

GLOSA runs in the movement reminder, reducing remaining distance and considering the next TLS only within range. It predicts earliest arrival and upcoming phases; for a reachable green it may increase chosenSpeedFactor up to configured max-speedfactor, otherwise it computes a red-phase approach maneuver. Queue option uses clearance factor=.21 s/m plus a 3 s startup offset. Phase prediction and green-end distance-dependent slack are algorithmic branches, included in the annex. It changes chosen speed factor for subsequent planning by default, rather than directly adding an acceleration to the already integrated tick. On TLS transition/finishing advice it restores original factor. [microsim/MSVehicle.cpp:4907-4913; microsim/devices/MSDevice_GLOSA.cpp:97-355]

Red-approach equation: a=maxAccel, d=maxDecel, w=laneLimit*originalFactor, u=minSpeed, s=distance, t=timeToSwitch+add-switchtime, v=currentSpeed. First `R0=a²*t²-2*a*w*t+2*a*s`, `vConst=sqrt(R0)-a*t+w` if R0>=0 else 0; if v<vConst set d=a. Then `R=a*d*(2*d*(s-w*t)-(v-w)²+a*(d*t²+2*(s-t*v)))`, `x=(a*(v-d*t)+d*w+sqrt(R))/(d+a)`, y=abs(v-x)/d. For admissible x in [u,w], y<t, target=max(x,minNextSpeed(v)), duration=max(y,dt). Default sets chosenSpeedFactor=target/laneLimit. Negative R, too-low x, end-of-maneuver and unsolvable cases have distinct solved/reset semantics: preserve annex branches. ignore-cfmodel instead installs a speed timeline; override-safety alters junction-priority/TLS influence. [microsim/devices/MSDevice_GLOSA.cpp:501-609,97-120]

## 7. Default vehicle types

| class | length | minGap | accel | decel | emergencyDecel | apparentDecel | sigma | tau | speedFactor normal std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| passenger | 5 | 2.5 | 2.6 | 4.5 | 9 | 4.5 | .5 | 1 | .1 |
| bus | 12 | 2.5 | 1.2 | 4 | 7 | 4 | .5 | 1 | 0 |
| truck | 7.1 | 2.5 | 1.3 | 4 | 7 | 4 | .5 | 1 | .05 |
| bicycle | 1.6 | .5 | 1.2 | 3 | 7 | 3 | .5 | 1 | .1 |
| pedestrian | .215 | .25 | 1.5 | 2 | 5 | 2 | .5 | 1 | .1 |

Sources for every table cell: [utils/common/SUMOVehicleClass.cpp:566-616; utils/vehicle/SUMOVTypeParameter.cpp:65-124,160-205,278-284,907-1040; microsim/cfmodels/MSCFModel.cpp:55-69]. Pedestrian CF defaults describe the type parameter fallback, not a claim that walking persons use road-car Krauss; normal person movement is handled by person control. [microsim/MSNet.cpp:907-911]

Normal mean=1, lower=.2, upper=2. `normc` is rejection sampling until inside the interval, NOT saturating/clamping a Gaussian draw to its endpoints. A type's zero std returns the mean. Per-vehicle chosen factor is sampled then max(minDev,sample) and rounded to random precision unless an override is supplied; store it, do not redraw every timestep. Global default.speeddev can override class deviations. Passenger std=.1, bus remains zero in this checkout. [utils/vehicle/SUMOVTypeParameter.cpp:77,184-199,278-284,383-399; utils/distribution/Distribution_Parameterized.cpp:110-129; microsim/MSVehicleType.cpp:92-97]

Default carFollowModel=Krauss; laneChangeModel=DEFAULT resolves to LC2013 for ordinary non-sublane simulation (sublane model selected when lateral resolution is enabled). actionStepLength defaults to simulation step (so .1 and 1 s imply different action intervals); an explicit default action interval can cause automatic ballistic selection unless the integration method was explicitly set. Tau remains 1 s at either dt. [utils/vehicle/SUMOVTypeParameter.cpp:328-345; microsim/lcmodels/MSAbstractLaneChangeModel.cpp:60-110; microsim/MSFrame.cpp:382-383,552-553,1213-1225]

Shared constants: NUMERICAL_EPS=.001, POSITION_EPS=.1 m, NUMERICAL_EPS_SPEED=.1*NUMERICAL_EPS*TS, haltingSpeed=.1 m/s, emergency-deceleration amplifier=1.2, random rounding precision=4 decimal places. Waiting acceleration threshold=.5*maxAccel. Preserve these distinctions in float32; do not replace all with machine epsilon. [config.h.cmake:233-244; microsim/MSVehicle.cpp:127; utils/common/StdDefs.h:62; utils/common/StdDefs.cpp:30; microsim/cfmodels/MSCFModel.h:35; microsim/MSVehicle.h:2100-2102]

Additional shared acceleration semantics: getCurrentAccel starts with accel, then caps by linearly interpolated desired and maximal acceleration profiles when present. maxNextSpeed=min(v+getCurrentAccel(v)*dt,type.maxSpeed). Current apparentDecel equals the model's configured apparentDecel; the alternative max(actual braking,apparentDecel) is commented out and must NOT be implemented. [microsim/cfmodels/MSCFModel.cpp:323-325,1167-1179; microsim/MSVehicle.cpp:8024-8027]

## Algorithm annex: exact arithmetic and branch reference

The following are source-derived kernels with comments and compile-time diagnostics removed. Each block cites the complete original function range. `MAX2/MIN2/MIN3` are scalar max/min, EPS constants are numeric tolerances, `SIMSTEP` is current integer tick, and CURRENT/FUTURE distinguish current control evaluation from prediction. The kernels retain C++ notation to expose operation order; they are not an additional implementation to maintain.

### MSCFModel::freeSpeed

[microsim/cfmodels/MSCFModel.cpp:112-174]

```cpp
MSCFModel::freeSpeed(const double currentSpeed, const double decel, const double dist, const double targetSpeed, const bool onInsertion, const double actionStepLength) {
    if (MSGlobals::gSemiImplicitEulerUpdate) {
        const double v = SPEED2DIST(targetSpeed);
        if (dist < v) {
            return targetSpeed;
        }
        const double b = ACCEL2DIST(decel);
        const double y = MAX2(0.0, ((sqrt((b + 2.0 * v) * (b + 2.0 * v) + 8.0 * b * dist) - b) * 0.5 - v) / b);
        const double yFull = floor(y);
        const double exactGap = (yFull * yFull + yFull) * 0.5 * b + yFull * v + (y > yFull ? v : 0.0);
        const double fullSpeedGain = (yFull + (onInsertion ? 1. : 0.)) * ACCEL2SPEED(decel);
        return DIST2SPEED(MAX2(0.0, dist - exactGap) / (yFull + 1)) + fullSpeedGain + targetSpeed;
    } else {
        assert(currentSpeed >= 0);
        assert(targetSpeed >= 0);
        const double dt = onInsertion ? 0 : actionStepLength; 
        const double v0 = currentSpeed;
        const double vT = targetSpeed;
        const double b = decel;
        const double d = dist - NUMERICAL_EPS; 
        if (0.5 * (v0 + vT)*dt >= d) {
            return v0 + TS * (vT - v0) / actionStepLength;
        } else {
            const double q = ((dt * v0 - 2 * d) * b - vT * vT); 
            const double p = 0.5 * b * dt;
            const double vN = -p + sqrt(p * p - q); 
            return v0 + TS * (vN - v0) / actionStepLength;
        }
    }
}
```

### MSCFModel::freeSpeed

[microsim/cfmodels/MSCFModel.cpp:353-360]

```cpp
MSCFModel::freeSpeed(const MSVehicle* const veh, double speed, double seen, double maxSpeed, const bool onInsertion, const CalcReason ) const {
    if (maxSpeed < 0.) {
        return maxSpeed;
    }
    double vSafe = freeSpeed(speed, myDecel, seen, maxSpeed, onInsertion, veh->getActionStepLengthSecs());
    return vSafe;
}
```

### MSCFModel::calculateEmergencyDeceleration

[microsim/cfmodels/MSCFModel.cpp:1038-1086]

```cpp
MSCFModel::calculateEmergencyDeceleration(double gap, double egoSpeed, double predSpeed, double predMaxDecel) const {
    if (gap <= 0.) {
        return myEmergencyDecel;
    }
    const double predBrakeDist = 0.5 * predSpeed * predSpeed / predMaxDecel;
    const double b1 = 0.5 * egoSpeed * egoSpeed / (gap + predBrakeDist);
    if (b1 <= predMaxDecel) {
        return b1;
    }
    const double b2 = 0.5 * (egoSpeed * egoSpeed - predSpeed * predSpeed) / gap;
    return b2;
}
```

### MSCFModel::maximumSafeFollowSpeed

[microsim/cfmodels/MSCFModel.cpp:958-1034]

```cpp
MSCFModel::maximumSafeFollowSpeed(double gap, double egoSpeed, double predSpeed, double predMaxDecel, bool onInsertion) const {
    const double headway = myHeadwayTime;
    double x;
    if (gap >= 0 || MSGlobals::gComputeLC) {
        x = maximumSafeStopSpeed(gap + brakeGap(predSpeed, MAX2(myDecel, predMaxDecel), 0), myDecel, egoSpeed, onInsertion, headway, false);
    } else {
        x = egoSpeed - ACCEL2SPEED(myEmergencyDecel);
        if (MSGlobals::gSemiImplicitEulerUpdate) {
            x = MAX2(x, 0.);
        }
    }
    if (myDecel != myEmergencyDecel && !onInsertion && !MSGlobals::gComputeLC) {
        double origSafeDecel = SPEED2ACCEL(egoSpeed - x);
        if (origSafeDecel > myDecel + NUMERICAL_EPS) {
            double safeDecel = EMERGENCY_DECEL_AMPLIFIER * calculateEmergencyDeceleration(gap, egoSpeed, predSpeed, predMaxDecel);
            safeDecel = MAX2(safeDecel, myDecel);
            safeDecel = MIN2(safeDecel, origSafeDecel);
            x = egoSpeed - ACCEL2SPEED(safeDecel);
            if (MSGlobals::gSemiImplicitEulerUpdate) {
                x = MAX2(x, 0.);
            }
        }
    }
    assert(x >= 0 || !MSGlobals::gSemiImplicitEulerUpdate);
    assert(!std::isnan(x));
    return x;
}
```

### MSCFModel::maxNextSpeed

[microsim/cfmodels/MSCFModel.cpp:324-326]

```cpp
MSCFModel::maxNextSpeed(double speed, const MSVehicle* const ) const {
    return MIN2(speed + (double) ACCEL2SPEED(getCurrentAccel(speed)), myType->getMaxSpeed());
}
```

### MSVehicle::getArrivalTime

[microsim/MSVehicle.cpp:3169-3184]

```cpp
MSVehicle::getArrivalTime(SUMOTime t, double seen, double v, double arrivalSpeed) const {
    const MSCFModel& cfModel = getCarFollowModel();
    SUMOTime arrivalTime;
    if (MSGlobals::gSemiImplicitEulerUpdate) {
        arrivalTime = t - DELTA_T + cfModel.getMinimalArrivalTime(seen, v, arrivalSpeed);
    } else {
        arrivalTime = t - DELTA_T + cfModel.getMinimalArrivalTime(seen, myState.mySpeed, arrivalSpeed);
    }
    if (isStopped()) {
        arrivalTime += MAX2((SUMOTime)0, myStops.front().duration);
    }
    return arrivalTime;
}
```

### MSVehicle::checkLinkLeader

[microsim/MSVehicle.cpp:3584-3718]

```cpp
MSVehicle::checkLinkLeader(const MSLink* link, const MSLane* lane, double seen,
                           DriveProcessItem* const lastLink, double& v, double& vLinkPass, double& vLinkWait, bool& setRequest,
                           bool isShadowLink) const {
    const MSLink::LinkLeaders linkLeaders = link->getLeaderInfo(this, seen, nullptr, isShadowLink);
    for (MSLink::LinkLeaders::const_iterator it = linkLeaders.begin(); it != linkLeaders.end(); ++it) {
        const MSVehicle* leader = (*it).vehAndGap.first;
        if (leader == nullptr) {
            if (getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_IGNORE_JUNCTION_FOE_PROB, 0) > 0
                    && getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_IGNORE_JUNCTION_FOE_PROB, 0) >= RandHelper::rand(getRNG())) {
                continue;
            }
            adaptToJunctionLeader(std::make_pair(this, -1), seen, lastLink, lane, v, vLinkPass, it->distToCrossing);
            if (v < SUMO_const_haltingSpeed && getWaitingTime() > TIME2STEPS(JUNCTION_BLOCKAGE_TIME)) {
                setRequest = false;
            }
        } else if (isLeader(link, leader, (*it).vehAndGap.second) || (*it).inTheWay()) {
            if (getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_IGNORE_JUNCTION_FOE_PROB, 0) > 0
                    && getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_IGNORE_JUNCTION_FOE_PROB, 0) >= RandHelper::rand(getRNG())) {
                continue;
            }
            if (MSGlobals::gLateralResolution > 0 &&
                    &leader->getLane()->getEdge() == &lane->getEdge()) {
                const MSLane* conflictLane = link->getInternalLaneBefore();
                MSLeaderInfo linkLeadersAhead = MSLeaderInfo(conflictLane->getWidth());
                linkLeadersAhead.addLeader(leader, false, 0); 
                const double latOffset = isShadowLink ? (getLane()->getRightSideOnEdge() - myLaneChangeModel->getShadowLane()->getRightSideOnEdge()) : 0;
                adaptToLeaders(linkLeadersAhead, latOffset, seen, lastLink, leader->getLane(), v, vLinkPass);
            } else {
                adaptToJunctionLeader(it->vehAndGap, seen, lastLink, lane, v, vLinkPass, it->distToCrossing);
            }
            if (lastLink != nullptr) {
                v = MAX2(v, lastLink->myVLinkWait);
            }
            if (v < SUMO_const_haltingSpeed
                    && (leader->getLane()->getLogicalPredecessorLane() == myLane->getLogicalPredecessorLane()
                        || leader->getLane()->getLogicalPredecessorLane() == myLane
                        || leader->isStopped()
                        || leader->getWaitingTime() > TIME2STEPS(JUNCTION_BLOCKAGE_TIME))) {
                setRequest = false;
                if (lastLink != nullptr && leader->getLane()->getLogicalPredecessorLane() == myLane) {
                    lastLink->mySetRequest = false;
                }
            }
        }
    }
    vLinkWait = MIN2(vLinkWait, v);
}
```

### MSVehicle::processLinkApproaches

[microsim/MSVehicle.cpp:3744-4023]

```cpp
MSVehicle::processLinkApproaches(double& vSafe, double& vSafeMin, double& vSafeMinDist) {
    const MSCFModel& cfModel = getCarFollowModel();
    double vSafeZipper = std::numeric_limits<double>::max();
    myHaveToWaitOnNextLink = false;
    bool canBrakeVSafeMin = false;
    assert(myLFLinkLanes.size() != 0 || isRemoteControlled());
    for (const DriveProcessItem& dpi : myLFLinkLanes) {
        MSLink* const link = dpi.myLink;
        if (link != nullptr && dpi.mySetRequest) {
            const LinkState ls = link->getState();
            const bool yellow = link->haveYellow();
            const bool canBrake = (dpi.myDistance > cfModel.brakeGap(myState.mySpeed, cfModel.getMaxDecel(), 0.)
                                   || (MSGlobals::gSemiImplicitEulerUpdate && myState.mySpeed < ACCEL2SPEED(cfModel.getMaxDecel())));
            assert(link->getLaneBefore() != nullptr);
            const bool beyondStopLine = dpi.myDistance < link->getLaneBefore()->getVehicleStopOffset(this);
            const bool ignoreRedLink = ignoreRed(link, canBrake) || beyondStopLine;
            if (yellow && canBrake && !ignoreRedLink) {
                vSafe = dpi.myVLinkWait;
                myHaveToWaitOnNextLink = true;
                break;
            }
            const bool influencerPrio = (myInfluencer != nullptr && !myInfluencer->getRespectJunctionPriority());
            MSLink::BlockingFoes collectFoes;
            bool opened = (yellow || influencerPrio
                           || link->opened(dpi.myArrivalTime, dpi.myArrivalSpeed, dpi.getLeaveSpeed(),
                                           getVehicleType().getLength(),
                                           canBrake ? getImpatience() : 1,
                                           cfModel.getMaxDecel(),
                                           getWaitingTimeFor(link), getLateralPositionOnLane(),
                                           ls == LINKSTATE_ZIPPER ? &collectFoes : nullptr,
                                           ignoreRedLink, this, dpi.myDistance));
            if (opened && myLaneChangeModel->getShadowLane() != nullptr) {
                const MSLink* const parallelLink = dpi.myLink->getParallelLink(myLaneChangeModel->getShadowDirection());
                if (parallelLink != nullptr) {
                    const double shadowLatPos = getLateralPositionOnLane() - myLaneChangeModel->getShadowDirection() * 0.5 * (
                                                    myLane->getWidth() + myLaneChangeModel->getShadowLane()->getWidth());
                    opened = yellow || influencerPrio || (opened && parallelLink->opened(dpi.myArrivalTime, dpi.myArrivalSpeed, dpi.getLeaveSpeed(),
                                                          getVehicleType().getLength(),
                                                          canBrake ? getImpatience() : 1,
                                                          cfModel.getMaxDecel(),
                                                          getWaitingTimeFor(link), shadowLatPos, nullptr,
                                                          ignoreRedLink, this, dpi.myDistance));
                }
            }
            double visibilityDistance = link->getFoeVisibilityDistance();
            bool determinedFoePresence = dpi.myDistance <= visibilityDistance;
            if (opened && !influencerPrio && !link->havePriority() && !link->lastWasContMajor() && !link->isCont() && !ignoreRedLink) {
                if (!determinedFoePresence && (canBrake || !yellow)) {
                    vSafe = dpi.myVLinkWait;
                    myHaveToWaitOnNextLink = true;
                    break;
                } else {
                    vSafeMinDist = dpi.myDistance; 
                    if (MSGlobals::gSemiImplicitEulerUpdate) {
                        vSafeMin = MIN3((double)DIST2SPEED(vSafeMinDist + POSITION_EPS), dpi.myVLinkPass, cfModel.maxNextSafeMin(getSpeed(), this));
                    } else {
                        vSafeMin = MIN3((double)DIST2SPEED(2 * vSafeMinDist + NUMERICAL_EPS) - getSpeed(), dpi.myVLinkPass, cfModel.maxNextSafeMin(getSpeed(), this));
                    }
                    canBrakeVSafeMin = canBrake;
                }
            }
            if (opened) {
                vSafe = dpi.myVLinkPass;
                if (vSafe < cfModel.getMaxDecel() && vSafe <= dpi.myVLinkWait && vSafe < cfModel.maxNextSpeed(getSpeed(), this)) {
                    myHaveToWaitOnNextLink = true;
                }
                if (link->mustStop() && determinedFoePresence && myHaveStoppedFor == nullptr) {
                    myHaveStoppedFor = link;
                }
            } else if (link->getState() == LINKSTATE_ZIPPER) {
                vSafeZipper = MIN2(vSafeZipper,
                                   link->getZipperSpeed(this, dpi.myDistance, dpi.myVLinkPass, dpi.myArrivalTime, &collectFoes));
            } else if (!canBrake
                       && link->getTLLogic() == nullptr
                       && dpi.myDistance < cfModel.brakeGap(myState.mySpeed, cfModel.getEmergencyDecel(), 0.)) {
                vSafe = dpi.myVLinkPass;
            } else {
                vSafe = dpi.myVLinkWait;
                myHaveToWaitOnNextLink = true;
                break;
            }
            if (myLane->isInternal() && myJunctionEntryTime == SUMOTime_MAX) {
                myJunctionEntryTime = SIMSTEP;;
            }
        } else {
            if (link != nullptr && link->getInternalLaneBefore() != nullptr && myLane->isInternal() && link->getJunction() == myLane->getEdge().getToJunction()) {
                myJunctionEntryTime = SUMOTime_MAX;
                myJunctionConflictEntryTime = SUMOTime_MAX;
            }
            vSafe = dpi.myVLinkWait;
            if (link != nullptr || myStopDist < (myLane->getLength() - getPositionOnLane())) {
                if (vSafe < getSpeed()) {
                    myHaveToWaitOnNextLink = true;
                } else if (vSafe < SUMO_const_haltingSpeed) {
                    myHaveToWaitOnNextLink = true;
                }
            }
            if (link == nullptr && myLFLinkLanes.size() == 1
                    && getBestLanesContinuation().size() > 1
                    && getBestLanesContinuation()[1]->hadPermissionChanges()
                    && myLane->getFirstAnyVehicle() == this) {
                updateBestLanes(true);
            }
            break;
        }
    }
    if ((MSGlobals::gSemiImplicitEulerUpdate && vSafe + NUMERICAL_EPS < vSafeMin)
            || (!MSGlobals::gSemiImplicitEulerUpdate && (vSafe + NUMERICAL_EPS < vSafeMin && vSafeMin != 0))) { 
        if (canBrakeVSafeMin && vSafe < getSpeed()) {
            vSafe = MIN2(vSafe, MAX2(getCarFollowModel().minNextSpeed(getSpeed(), this),
                                     getCarFollowModel().stopSpeed(this, getSpeed(), vSafeMinDist)));
            vSafeMin = 0;
            myHaveToWaitOnNextLink = true;
        } else {
            vSafeMin = vSafe;
        }
    }
    if (myLane->getEdge().isRoundabout()) {
        myHaveToWaitOnNextLink = false;
    }
    vSafe = MIN2(vSafe, vSafeZipper);
}
```

### MSVehicle::processLaneAdvances

[microsim/MSVehicle.cpp:4471-4630]

```cpp
MSVehicle::processLaneAdvances(std::vector<MSLane*>& passedLanes, std::string& emergencyReason) {
    for (std::vector<MSLane*>::reverse_iterator i = myFurtherLanes.rbegin(); i != myFurtherLanes.rend(); ++i) {
        passedLanes.push_back(*i);
    }
    if (passedLanes.size() == 0 || passedLanes.back() != myLane) {
        passedLanes.push_back(myLane);
    }
    bool reverseTrain = false;
    checkReversal(reverseTrain);
    if (reverseTrain) {
        myAmReversed = !myAmReversed;
        myState.myPos += 2 * (myLane->getLength() - myState.myPos) + myType->getLength() + NUMERICAL_EPS;
        myState.mySpeed = 0;
    }
    if (myState.myPos > myLane->getLength()) {
        if (myCurrEdge != myRoute->end() - 1) {
            MSLane* approachedLane = myLane;
            myNextDriveItem = myLFLinkLanes.begin();
            while (myNextDriveItem != myLFLinkLanes.end() && approachedLane != nullptr && myState.myPos > approachedLane->getLength()) {
                const MSLink* link = myNextDriveItem->myLink;
                const double linkDist = myNextDriveItem->myDistance;
                ++myNextDriveItem;
                if (approachedLane->mustCheckJunctionCollisions()) {
                    MSNet::getInstance()->getEdgeControl().checkCollisionForInactive(approachedLane);
                }
                if (link != nullptr) {
                    if ((getVClass() & SVC_RAIL_CLASSES) != 0
                            && !myLane->isInternal()
                            && myLane->getBidiLane() != nullptr
                            && link->getLane()->getBidiLane() == myLane
                            && !reverseTrain) {
                        emergencyReason = " because it must reverse direction";
                        approachedLane = nullptr;
                        break;
                    }
                    if ((getVClass() & SVC_RAIL_CLASSES) != 0
                            && myState.myPos < myLane->getLength() + NUMERICAL_EPS
                            && hasStops() && getNextStop().edge == myCurrEdge) {
                        approachedLane = myLane;
                        myState.myPos = myLane->getLength();
                        break;
                    }
                    approachedLane = link->getViaLaneOrLane();
                    if (myInfluencer == nullptr || myInfluencer->getEmergencyBrakeRedLight()) {
                        bool beyondStopLine = linkDist < link->getLaneBefore()->getVehicleStopOffset(this);
                        if (link->haveRed() && !ignoreRed(link, false) && !beyondStopLine && !reverseTrain) {
                            emergencyReason = " because of a red traffic light";
                            break;
                        }
                    }
                    if (reverseTrain && approachedLane->isInternal()) {
                        myState.myPos += approachedLane->getLength();
                    }
                } else if (myState.myPos < myLane->getLength() + NUMERICAL_EPS) {
                    approachedLane = myLane;
                    myState.myPos = myLane->getLength();
                } else if (reverseTrain) {
                    approachedLane = (*(myCurrEdge + 1))->getLanes()[0];
                    link = myLane->getLinkTo(approachedLane);
                    assert(link != 0);
                    while (link->getViaLane() != nullptr) {
                        link = link->getViaLane()->getLinkCont()[0];
                    }
                    --myNextDriveItem;
                } else {
                    emergencyReason = " because there is no connection to the next edge";
                    approachedLane = nullptr;
                    break;
                }
                if (approachedLane != myLane && approachedLane != nullptr) {
                    leaveLane(MSMoveReminder::NOTIFICATION_JUNCTION, approachedLane);
                    myState.myPos -= myLane->getLength();
                    assert(myState.myPos > 0);
                    enterLaneAtMove(approachedLane);
                    if (link->isEntryLink()) {
                        myJunctionEntryTime = MSNet::getInstance()->getCurrentTimeStep();
                        myJunctionEntryTimeNeverYield = myJunctionEntryTime;
                        myHaveStoppedFor = nullptr;
                    }
                    if (link->isConflictEntryLink()) {
                        myJunctionConflictEntryTime = MSNet::getInstance()->getCurrentTimeStep();
                        myJunctionEntryTime = myJunctionEntryTimeNeverYield;
                    }
                    if (link->isExitLink()) {
                        myJunctionEntryTime = SUMOTime_MAX;
                        myJunctionEntryTimeNeverYield = SUMOTime_MAX;
                        myJunctionConflictEntryTime = SUMOTime_MAX;
                    }
                    if (hasArrivedInternal()) {
                        break;
                    }
                    if (myLaneChangeModel->isChangingLanes()) {
                        if (link->getDirection() == LinkDirection::LEFT || link->getDirection() == LinkDirection::RIGHT) {
                            WRITE_WARNINGF("Vehicle '%' could not finish continuous lane change (turn lane) time=%.", getID(), time2string(SIMSTEP));
                            myLaneChangeModel->endLaneChangeManeuver();
                        }
                    }
                    if (approachedLane->getEdge().isVaporizing()) {
                        leaveLane(MSMoveReminder::NOTIFICATION_VAPORIZED_VAPORIZER);
                        break;
                    }
                    passedLanes.push_back(approachedLane);
                }
            }
        } else if (!hasArrivedInternal() && myState.myPos < myLane->getLength() + NUMERICAL_EPS) {
            myState.myPos = myLane->getLength();
        }
    }
}
```

### MSVehicle::checkRewindLinkLanes

[microsim/MSVehicle.cpp:5257-5491]

```cpp
MSVehicle::checkRewindLinkLanes(const double lengthsInFront, DriveItemVector& lfLinks) const {
    if (MSGlobals::gUsingInternalLanes && !myLane->getEdge().isRoundabout() && !myLaneChangeModel->isOpposite()) {
        double seenSpace = -lengthsInFront;
        bool foundStopped = false;
        for (int i = 0; i < (int)lfLinks.size(); ++i) {
            DriveProcessItem& item = lfLinks[i];
            if (item.myLink == nullptr || foundStopped) {
                if (!foundStopped) {
                    item.availableSpace += seenSpace;
                } else {
                    item.availableSpace = seenSpace;
                }
                continue;
            }
            const MSLane* approachedLane = item.myLink->getViaLane();
            if (approachedLane != nullptr) {
                if (keepClear(item.myLink)) {
                    seenSpace = seenSpace - approachedLane->getBruttoVehLenSum();
                    if (approachedLane == myLane) {
                        seenSpace += getVehicleType().getLengthWithGap();
                    }
                } else {
                    seenSpace = seenSpace + approachedLane->getSpaceTillLastStanding(this, foundStopped);
                }
                item.availableSpace = seenSpace;
                continue;
            }
            approachedLane = item.myLink->getLane();
            const MSVehicle* last = approachedLane->getLastAnyVehicle();
            if (last == nullptr || last == this) {
                if (approachedLane->getLength() > getVehicleType().getLength()
                        || keepClear(item.myLink)) {
                    seenSpace += approachedLane->getLength();
                }
                item.availableSpace = seenSpace;
            } else {
                bool foundStopped2 = false;
                double spaceTillLastStanding = approachedLane->getSpaceTillLastStanding(this, foundStopped2);
                if (approachedLane->getBidiLane() != nullptr) {
                    const MSVehicle* oncomingVeh = approachedLane->getBidiLane()->getFirstFullVehicle();
                    if (oncomingVeh) {
                        const double oncomingGap = approachedLane->getLength() - oncomingVeh->getPositionOnLane();
                        const double oncomingBGap = oncomingVeh->getBrakeGap(true);
                        const double oncomingMove = STEPS2TIME(item.myArrivalTime - SIMSTEP) * oncomingVeh->getSpeed();
                        const double spaceTillOncoming = oncomingGap - oncomingBGap - oncomingMove;
                        spaceTillLastStanding = MIN2(spaceTillLastStanding, spaceTillOncoming);
                        if (spaceTillOncoming <= getVehicleType().getLengthWithGap()) {
                            foundStopped = true;
                        }
                    }
                }
                seenSpace += spaceTillLastStanding;
                if (foundStopped2) {
                    foundStopped = true;
                    item.hadStoppedVehicle = true;
                }
                item.availableSpace = seenSpace;
                if (last->myHaveToWaitOnNextLink || last->isStopped()) {
                    foundStopped = true;
                    item.hadStoppedVehicle = true;
                }
            }
        }
        for (int i = ((int)lfLinks.size() - 1); i > 0; --i) {
            DriveProcessItem& item = lfLinks[i - 1];
            DriveProcessItem& nextItem = lfLinks[i];
            const bool canLeaveJunction = item.myLink->getViaLane() == nullptr || nextItem.myLink == nullptr || nextItem.mySetRequest;
            const bool opened = (item.myLink != nullptr
                                 && (canLeaveJunction || (
                                         nextItem.myLink != nullptr && nextItem.myLink->isInternalJunctionLink() && nextItem.myLink->haveRed()))
                                 && (
                                     item.myLink->havePriority()
                                     || i == 1 
                                     || (myInfluencer != nullptr && !myInfluencer->getRespectJunctionPriority())
                                     || item.myLink->opened(item.myArrivalTime, item.myArrivalSpeed,
                                             item.getLeaveSpeed(), getVehicleType().getLength(),
                                             getImpatience(), getCarFollowModel().getMaxDecel(), getWaitingTime(), getLateralPositionOnLane(), nullptr, false, this)));
            bool allowsContinuation = (item.myLink == nullptr || item.myLink->isCont() || opened) && !item.hadStoppedVehicle;
            if (!opened && item.myLink != nullptr) {
                foundStopped = true;
                if (i > 1) {
                    DriveProcessItem& item2 = lfLinks[i - 2];
                    if (item2.myLink != nullptr && item2.myLink->isCont()) {
                        allowsContinuation = true;
                    }
                }
            }
            if (allowsContinuation) {
                item.availableSpace = nextItem.availableSpace;
            }
        }
        int removalBegin = -1;
        for (int i = 0; foundStopped && i < (int)lfLinks.size() && removalBegin < 0; ++i) {
            const DriveProcessItem& item = lfLinks[i];
            if (item.myLink == nullptr) {
                continue;
            }
            const double leftSpace = item.availableSpace - getVehicleType().getLengthWithGap();
            if (leftSpace < 0) {
                double impatienceCorrection = 0;
                if (leftSpace < -impatienceCorrection / 10. && keepClear(item.myLink)) {
                    removalBegin = i;
                }
            }
        }
        if (removalBegin != -1 && !(removalBegin == 0 && myLane->getEdge().isInternal())) {
            const double brakeGap = getCarFollowModel().brakeGap(myState.mySpeed, getCarFollowModel().getMaxDecel(), 0.);
            while (removalBegin < (int)(lfLinks.size())) {
                DriveProcessItem& dpi = lfLinks[removalBegin];
                if (dpi.myLink == nullptr) {
                    break;
                }
                dpi.myVLinkPass = dpi.myVLinkWait;
                if (dpi.myDistance >= brakeGap + POSITION_EPS) {
                    if (!dpi.myLink->isExitLink() || !lfLinks[removalBegin - 1].mySetRequest) {
                        dpi.mySetRequest = false;
                    }
                }
                ++removalBegin;
            }
        }
    }
}
```

### MSDevice_GLOSA::notifyMove

[microsim/devices/MSDevice_GLOSA.cpp:122-306]

```cpp
MSDevice_GLOSA::notifyMove(SUMOTrafficObject& , double oldPos,
                           double newPos, double ) {
    myDistance -= (newPos - oldPos);
    if (myNextTLSLink != nullptr && myDistance <= myRange) {
        const double vMax = myVeh.getLane()->getVehicleMaxSpeed(&myVeh);
        double timeToJunction = earliest_arrival(myDistance, vMax);
        int countOld = 0;
        double timeToSwitch = getTimeToSwitch(myNextTLSLink, countOld);
        bool currentPhaseGreen = false;
        bool currentPhaseStop = false;
        bool solved = false;
        double nextSwitch = 0;
        nextSwitch = timeToSwitch;
        double QueueLength = 0;
        double greenTime = 0;
        double additionalJunctionTime = 0;
        double factor = 0.21;
        double addition = 3;
        int switchOffset = 0;
        if (myNextTLSLink->haveGreen()) {
            currentPhaseGreen = true;
        } else if (myNextTLSLink->haveRed() || myNextTLSLink->haveYellow()) {
            currentPhaseStop = true;
        }
        if (myUseQueue) {
            QueueLength = myNextTLSLink->getTLLogic()->getTLQueueLength(myNextTLSLink->getLaneBefore()->getID());
            if (currentPhaseGreen) {
                greenTime = timeGreen(myNextTLSLink);
                additionalJunctionTime = (QueueLength * factor + addition) - greenTime;
                if ((additionalJunctionTime > 0) && (additionalJunctionTime < nextSwitch)) {
                    timeToJunction += additionalJunctionTime;
                } else {
                    additionalJunctionTime = 0;
                }
            }
            if (currentPhaseStop) {
                nextSwitch += QueueLength * factor + addition;
            }
        }
        for (int countwhile = 1; countwhile < 11; countwhile++) {
            if (currentPhaseGreen) {
                if (countwhile == 2 && myUseQueue) {
                    nextSwitch -= QueueLength * factor + addition;
                }
                if (mySpeedAdviceActive && myOriginalSpeedFactor > myVeh.getChosenSpeedFactor()) {
                    myVeh.setChosenSpeedFactor(myOriginalSpeedFactor);
                    mySpeedAdviceActive = false;
                }
                if (timeToJunction > nextSwitch) {
                    if (myMaxSpeedFactor > myOriginalSpeedFactor) {
                        const double vMax2 = vMax / myVeh.getChosenSpeedFactor() * myMaxSpeedFactor;
                        const double timetoJunction2 = earliest_arrival(myDistance, vMax2) + additionalJunctionTime;
                        const double yellowSlack = myVeh.getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_DRIVE_AFTER_YELLOW_TIME, 0);
                        if (timetoJunction2 <= (nextSwitch + yellowSlack)) {
                            myVeh.setChosenSpeedFactor(myMaxSpeedFactor);
                            mySpeedAdviceActive = true;
                            break; 
                        } else {
                        }
                    } else {
                    }
                } else {
                    break; 
                }
            } else if (currentPhaseStop) {
                if (countwhile == 2 && myUseQueue) {
                    nextSwitch += QueueLength * factor + addition;
                }
                adaptSpeed(myDistance, timeToJunction, nextSwitch + myAddSwitchTime, solved);
                if (countwhile == 2 && myUseQueue) {
                    nextSwitch -= QueueLength * factor + addition;
                    timeToJunction -= additionalJunctionTime;
                }
                if (solved) {
                    break; 
                }
            }
            nextSwitch += getTimeToNextSwitch(myNextTLSLink, currentPhaseGreen, currentPhaseStop, countOld);
            if (nextSwitch > 80.) {
                nextSwitch += (double)switchOffset;
                switchOffset = 6;
                nextSwitch -= (double)switchOffset;
            } else if (nextSwitch > 60.) {
                nextSwitch += (double)switchOffset;
                switchOffset = 4;
                nextSwitch -= (double)switchOffset;
            } else if (nextSwitch > 40.) {
                nextSwitch += (double)switchOffset;
                switchOffset = 3;
                nextSwitch -= (double)switchOffset;
            } else if (nextSwitch > 20.) {
                nextSwitch += (double)switchOffset;
                switchOffset = 2;
                nextSwitch -= (double)switchOffset;
            }
        }
    }
    return true; 
}
```

### MSDevice_GLOSA::notifyEnter

[microsim/devices/MSDevice_GLOSA.cpp:310-360]

```cpp
MSDevice_GLOSA::notifyEnter(SUMOTrafficObject& , MSMoveReminder::Notification , const MSLane* ) {
    const MSLink* prevLink = myNextTLSLink;
    myNextTLSLink = nullptr;
    const MSLane* lane = myVeh.getLane();
    if (myVeh.getDeparture() < SIMSTEP) {
        myVeh.updateBestLanes();
    }
    const std::vector<MSLane*>& bestLaneConts = myVeh.getBestLanesContinuation(lane);
    double seen = lane->getLength() - myVeh.getPositionOnLane();
    int view = 1;
    std::vector<MSLink*>::const_iterator linkIt = MSLane::succLinkSec(myVeh, view, *lane, bestLaneConts);
    while (!lane->isLinkEnd(linkIt)) {
        if (!lane->getEdge().isInternal()) {
            if ((*linkIt)->isTLSControlled()) {
                myNextTLSLink = *linkIt;
                myDistance = seen;
                break;
            }
        }
        lane = (*linkIt)->getViaLaneOrLane();
        if (!lane->getEdge().isInternal()) {
            view++;
        }
        seen += lane->getLength();
        linkIt = MSLane::succLinkSec(myVeh, view, *lane, bestLaneConts);
    }
    if (prevLink != nullptr && myNextTLSLink == nullptr) {
        myVeh.setChosenSpeedFactor(myOriginalSpeedFactor);
        mySpeedAdviceActive = false;
    } else if (myNextTLSLink != nullptr && prevLink != myNextTLSLink) {
        double tlsRange = 1e10;
        const std::string val = myNextTLSLink->getTLLogic()->getParameter("device.glosa.range", "1e10");
        try {
            tlsRange = StringUtils::toDouble(val);
        } catch (const NumberFormatException&) {
            WRITE_WARNINGF(TL("Invalid value '%' for parameter 'device.glosa.range' of traffic light '%'"),
                           val, myNextTLSLink->getTLLogic()->getID());
        }
        myRange = MIN2(myVeh.getFloatParam("device.glosa.range", true), tlsRange);
    }
    return true; 
}
```

### MSDevice_GLOSA::getTimeToSwitch

[microsim/devices/MSDevice_GLOSA.cpp:364-384]

```cpp
MSDevice_GLOSA::getTimeToSwitch(const MSLink* tlsLink, int& countOld) {
    assert(tlsLink != nullptr);
    const MSTrafficLightLogic* const tl = tlsLink->getTLLogic();
    assert(tl != nullptr);
    const auto& phases = tl->getPhases();
    const int n = (int)phases.size();
    const int cur = tl->getCurrentPhaseIndex();
    SUMOTime result = tl->getNextSwitchTime() - SIMSTEP;
    for (int i = 1; i < n; i++) {
        const auto& phase = phases[(cur + i) % n];
        const char ls = phase->getState()[tlsLink->getTLIndex()];
        if (((tlsLink->haveRed() || tlsLink->haveYellow()) && (ls == 'g' || ls == 'G'))
                || (tlsLink->haveGreen() && ls != 'g' && ls != 'G')) {
            countOld = cur + i;
            break;
        }
        result += phase->duration;
    }
    return STEPS2TIME(result);
}
```

### MSDevice_GLOSA::getTimeToNextSwitch

[microsim/devices/MSDevice_GLOSA.cpp:388-414]

```cpp
MSDevice_GLOSA::getTimeToNextSwitch(const MSLink* tlsLink, bool& currentPhaseGreen, bool& currentPhaseStop, int& countOld) {
    assert(tlsLink != nullptr);
    const MSTrafficLightLogic* const tl = tlsLink->getTLLogic();
    assert(tl != nullptr);
    const auto& phases = tl->getPhases();
    const int n = (int)phases.size();
    const int cur = countOld;
    SUMOTime result = 0;
    for (int i = 0; i < n; i++) {
        const auto& phase = phases[(cur + i) % n];
        const char ls = phase->getState()[tlsLink->getTLIndex()];
        if (currentPhaseGreen && (ls == 'g' || ls == 'G')) {
            countOld = (cur + i) % n;
            break;
        }
        if (currentPhaseStop && (ls != 'g' && ls != 'G')) {
            countOld = (cur + i) % n;
            break;
        }
        result += phase->duration;
    }
    currentPhaseGreen = !currentPhaseGreen;
    currentPhaseStop = !currentPhaseStop;
    return STEPS2TIME(result);
}
```

### MSDevice_GLOSA::timeGreen

[microsim/devices/MSDevice_GLOSA.cpp:417-437]

```cpp
MSDevice_GLOSA::timeGreen(const MSLink* tlsLink) {
    assert(tlsLink != nullptr);
    const MSTrafficLightLogic* const tl = tlsLink->getTLLogic();
    assert(tl != nullptr);
    const auto& phases = tl->getPhases();
    const int n = (int)phases.size();
    const int cur = tl->getCurrentPhaseIndex();
    SUMOTime result = tl->getSpentDuration();
    for (int i = 1; i < n; i++) {
        const auto& phase = phases[(cur - i) % n];
        const char ls = phase->getState()[tlsLink->getTLIndex()];
        if (ls != 'g' && ls != 'G') {
            break;
        }
        result += phase->duration;
    }
    return STEPS2TIME(result);
}
```

### MSDevice_GLOSA::earliest_arrival

[microsim/devices/MSDevice_GLOSA.cpp:442-450]

```cpp
MSDevice_GLOSA::earliest_arrival(double distance, double vMax) {
    const double v = myVeh.getSpeed();
    const double a = myVeh.getCarFollowModel().getMaxAccel();
    const double accel_time = MIN2((vMax - v) / a, time_to_junction_at_continuous_accel(distance, v));
    const double remaining_dist = distance - distance_at_continuous_accel(v, accel_time);
    const double remaining_time = remaining_dist / vMax;
    return accel_time + remaining_time;
}
```

### MSDevice_GLOSA::distance_at_continuous_accel

[microsim/devices/MSDevice_GLOSA.cpp:480-486]

```cpp
MSDevice_GLOSA::distance_at_continuous_accel(double speed, double time) {
    const double v = speed;
    const double t = time;
    const double a = myVeh.getCarFollowModel().getMaxAccel();
    return v * t + a * t * t / 2;
}
```

### MSDevice_GLOSA::time_to_junction_at_continuous_accel

[microsim/devices/MSDevice_GLOSA.cpp:490-497]

```cpp
MSDevice_GLOSA::time_to_junction_at_continuous_accel(double d, double v) {
    const double a = myVeh.getCarFollowModel().getMaxAccel();
    const double p_half = v / a;
    const double t = -p_half + sqrt(p_half * p_half + 2 * d / a);
    return t;
}
```

### MSDevice_GLOSA::adaptSpeed

[microsim/devices/MSDevice_GLOSA.cpp:501-609]

```cpp
MSDevice_GLOSA::adaptSpeed(double distance, double , double timeToSwitch, bool& solved) {
    const double vMax = myVeh.getLane()->getSpeedLimit() * myOriginalSpeedFactor;
    const double t = timeToSwitch;
    const double a = myVeh.getCarFollowModel().getMaxAccel();
    const double u = myMinSpeed;
    const double w = vMax;
    const double s = distance;
    const double v = myVeh.getSpeed();
    const double rootConst = a * a * t * t - 2.0 * a * w * t + 2 * a * s;
    double vConst = 0;
    if (rootConst >= 0) {
        vConst = sqrt(rootConst) - a * t + w;
    }
    double d = myVeh.getCarFollowModel().getMaxDecel();
    if (v < vConst) {
        d = a;
    }
    const double sign0 = -1; 
    const double root_argument = a * d * ((2.0 * d * (s - (w * t))) - ((v - w) * (v - w)) + (a * ((d * (t * t)) + (2.0 * (s - (t * v))))));
    if (root_argument < 0) {
        solved = true;
        return;
    }
    const double x = (((a * (v - (d * t))) + (d * w) - sign0 * sqrt(root_argument)) / (d + a));
    double y = (v - x) / d;
    if (v < x) {
        y = (x - v) / d;
    }
    if (s < (w * w - x * x) / 2.0 / a) {
        if (myIgnoreCFModel) {
            std::vector<std::pair<SUMOTime, double> > speedTimeLine;
            speedTimeLine.push_back(std::make_pair(MSNet::getInstance()->getCurrentTimeStep(), myVeh.getSpeed()));
            speedTimeLine.push_back(std::make_pair(MSNet::getInstance()->getCurrentTimeStep() + TIME2STEPS(w - x / a), vMax));
            myVeh.getInfluencer().setSpeedTimeLine(speedTimeLine);
        } else {
            myVeh.setChosenSpeedFactor(myOriginalSpeedFactor);
        }
        mySpeedAdviceActive = false;
        return;
    }
    if (!(x >= u && x <= w && y < t)) {
        if (x < u) {
            solved = true;
        }
        if (x > w) {
        }
        return;
    }
    const double targetSpeed = MAX2(x, myVeh.getCarFollowModel().minNextSpeed(myVeh.getSpeed(), &myVeh));
    const double duration = MAX2(y, TS);
    solved = true;
    if (myIgnoreCFModel) {
        std::vector<std::pair<SUMOTime, double> > speedTimeLine;
        speedTimeLine.push_back(std::make_pair(MSNet::getInstance()->getCurrentTimeStep(), myVeh.getSpeed()));
        speedTimeLine.push_back(std::make_pair(MSNet::getInstance()->getCurrentTimeStep() + TIME2STEPS(duration), targetSpeed));
        myVeh.getInfluencer().setSpeedTimeLine(speedTimeLine);
    } else {
        myVeh.setChosenSpeedFactor(targetSpeed / myVeh.getLane()->getSpeedLimit());
    }
    mySpeedAdviceActive = true;
}
```

### MSCFModel_Krauss::patchSpeedBeforeLC

[microsim/cfmodels/MSCFModel_Krauss.cpp:94-123]

```cpp
MSCFModel_Krauss::patchSpeedBeforeLC(const MSVehicle* veh, double vMin, double vMax) const {
    const double sigma = (veh->passingMinor()
                          ? veh->getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_SIGMA_MINOR, myDawdle)
                          : myDawdle);
    double vDawdle;
    if (myDawdleStep > DELTA_T) {
        VehicleVariables* vars = (VehicleVariables*)veh->getCarFollowVariables();
        if (SIMSTEP % myDawdleStep == vars->updateOffset) {
            const double vD = MAX2(vMin, dawdle2(vMax, sigma, veh->getRNG()));
            const double a1 = SPEED2ACCEL(vMax - veh->getSpeed());
            const double a2 = SPEED2ACCEL(vD - vMax);
            const double accelMax = (veh->getLane()->getVehicleMaxSpeed(veh) - veh->getSpeed()) / STEPS2TIME(myDawdleStep);
            vars->accelDawdle = MIN2(a1, accelMax) + a2;
            vDawdle = veh->getSpeed() + ACCEL2SPEED(vars->accelDawdle);
        } else {
            const double safeAccel = SPEED2ACCEL(vMax - veh->getSpeed());
            const double accel = MIN2(safeAccel, vars->accelDawdle);
            vDawdle = MAX2(vMin, MIN2(vMax, veh->getSpeed() + ACCEL2SPEED(accel)));
        }
    } else {
        vDawdle = MAX2(vMin, dawdle2(vMax, sigma, veh->getRNG()));
    }
    return vDawdle;
}
```

### MSVehicle::planMoveInternal

[microsim/MSVehicle.cpp:2276-3122]

```cpp
MSVehicle::planMoveInternal(const SUMOTime t, MSLeaderInfo ahead, DriveItemVector& lfLinks, double& newStopDist, double& newStopSpeed, std::pair<double, const MSLink*>& nextTurn) const {
    lfLinks.clear();
    newStopDist = std::numeric_limits<double>::max();
    const MSCFModel& cfModel = getCarFollowModel();
    const double vehicleLength = getVehicleType().getLength();
    const double maxV = cfModel.maxNextSpeed(myState.mySpeed, this);
    const double maxVD = MAX2(getMaxSpeed(), MIN2(maxV, getDesiredMaxSpeed()));
    const bool opposite = myLaneChangeModel->isOpposite();
    double laneMaxV = myLane->getVehicleMaxSpeed(this, maxVD);
    const double vMinComfortable = cfModel.minNextSpeed(getSpeed(), this);
    double lateralShift = 0;
    if (isRail()) {
        for (MSLane* l : myFurtherLanes) {
            laneMaxV = MIN2(laneMaxV, l->getVehicleMaxSpeed(this, maxVD));
        }
    }
    laneMaxV = MAX2(laneMaxV, vMinComfortable);
    if (myInfluencer && !myInfluencer->considerSpeedLimit()) {
        laneMaxV = std::numeric_limits<double>::max();
    }
    double v = cfModel.maximumLaneSpeedCF(this, maxV, laneMaxV);
    if (MSGlobals::gModelParkingManoeuver && !manoeuvreIsComplete()) {
        v = NUMERICAL_EPS_SPEED;
    }
    if (myInfluencer != nullptr) {
        const double vMin = MAX2(0., cfModel.minNextSpeed(myState.mySpeed, this));
        v = myInfluencer->influenceSpeed(t, v, v, vMin, maxV);
        v = myInfluencer->gapControlSpeed(t, this, v, v, vMin, maxV);
    }
    const double dist = SPEED2DIST(maxV) + cfModel.brakeGap(maxV);
    const std::vector<MSLane*>& bestLaneConts = getBestLanesContinuation();
    assert(bestLaneConts.size() > 0);
    bool hadNonInternal = false;
    double seen = opposite ? myState.myPos : myLane->getLength() - myState.myPos;
    nextTurn.first = seen;
    nextTurn.second = nullptr;
    bool encounteredTurn = (MSGlobals::gLateralResolution <= 0); 
    double seenNonInternal = 0;
    double seenInternal = myLane->isInternal() ? seen : 0;
    double vLinkPass = MIN2(cfModel.estimateSpeedAfterDistance(seen, v, cfModel.getMaxAccel()), laneMaxV); 
    int view = 0;
    DriveProcessItem* lastLink = nullptr;
    bool slowedDownForMinor = false; 
    double mustSeeBeforeReversal = 0;
    const MSLane* lane = opposite ? myLane->getParallelOpposite() : myLane;
    assert(lane != 0);
    const MSLane* leaderLane = myLane;
    bool foundRailSignal = !isRail();
    bool planningToStop = false;
    const double sfp = getVehicleType().getParameter().speedFactorPremature;
    if (v > vMinComfortable && hasStops() && myStops.front().pars.arrival >= 0 && sfp > 0
            && v > myLane->getSpeedLimit() * sfp
            && !myStops.front().reached) {
        const double vSlowDown = slowDownForSchedule(vMinComfortable);
        v = MIN2(v, vSlowDown);
    }
    auto stopIt = myStops.begin();
    while (true) {
        if (opposite &&
                (leaderLane->getVehicleNumberWithPartials() > 1
                 || (leaderLane != myLane && leaderLane->getVehicleNumber() > 0))) {
            ahead.clear();
            const double backOffset = leaderLane == myLane ? getPositionOnLane() : leaderLane->getLength();
            const double gapOffset = leaderLane == myLane ? 0 : seen - leaderLane->getLength();
            const MSLeaderDistanceInfo cands = leaderLane->getFollowersOnConsecutive(this, backOffset, true, backOffset, MSLane::MinorLinkMode::FOLLOW_NEVER);
            MSLeaderDistanceInfo oppositeLeaders(leaderLane->getWidth(), this, 0.);
            const double minTimeToLeaveLane = MSGlobals::gSublane ? MAX2(TS, (0.5 *  myLane->getWidth() - getLateralPositionOnLane()) / getVehicleType().getMaxSpeedLat()) : TS;
            for (int i = 0; i < cands.numSublanes(); i++) {
                CLeaderDist cand = cands[i];
                if (cand.first != 0) {
                    if ((cand.first->myLaneChangeModel->isOpposite() && cand.first->getLaneChangeModel().getShadowLane() != leaderLane)
                            || (!cand.first->myLaneChangeModel->isOpposite() && cand.first->getLaneChangeModel().getShadowLane() == leaderLane)) {
                        oppositeLeaders.addLeader(cand.first, cand.second + gapOffset - getVehicleType().getMinGap() + cand.first->getVehicleType().getMinGap() - cand.first->getVehicleType().getLength());
                    } else {
                        const bool assumeStopped = cand.first->isStopped() || cand.first->getWaitingSeconds() > 1;
                        const double predMaxDist = cand.first->getSpeed() + (assumeStopped ? 0 : cand.first->getCarFollowModel().getMaxAccel()) * minTimeToLeaveLane;
                        if (cand.second >= 0 && (cand.second - v * minTimeToLeaveLane - predMaxDist < 0 || assumeStopped)) {
                            oppositeLeaders.addLeader(cand.first, cand.second + gapOffset - predMaxDist - getVehicleType().getMinGap());
                        }
                    }
                }
            }
            adaptToLeaderDistance(oppositeLeaders, 0, seen, lastLink, v, vLinkPass);
        } else {
            if (MSGlobals::gLateralResolution > 0 && myLaneChangeModel->getShadowLane() == nullptr) {
                const double rightOL = getRightSideOnLane(lane) + lateralShift;
                const double leftOL = getLeftSideOnLane(lane) + lateralShift;
                const bool outsideLeft = leftOL > lane->getWidth();
                if (rightOL < 0 || outsideLeft) {
                    MSLeaderInfo outsideLeaders(lane->getWidth());
                    int sublaneOffset = 0;
                    if (outsideLeft) {
                        sublaneOffset = MIN2(-1, -(int)ceil((leftOL - lane->getWidth()) / MSGlobals::gLateralResolution));
                    } else {
                        sublaneOffset = MAX2(1, (int)ceil(-rightOL / MSGlobals::gLateralResolution));
                    }
                    outsideLeaders.setSublaneOffset(sublaneOffset);
                    for (const MSVehicle* cand : lane->getVehiclesSecure()) {
                        if ((lane != myLane || cand->getPositionOnLane() > getPositionOnLane())
                                && ((!outsideLeft && cand->getLeftSideOnEdge() < 0)
                                    || (outsideLeft && cand->getLeftSideOnEdge() > lane->getEdge().getWidth()))) {
                            outsideLeaders.addLeader(cand, true);
                        }
                    }
                    lane->releaseVehicles();
                    if (outsideLeaders.hasVehicles()) {
                        adaptToLeaders(outsideLeaders, lateralShift, seen, lastLink, leaderLane, v, vLinkPass);
                    }
                }
            }
            adaptToLeaders(ahead, lateralShift, seen, lastLink, leaderLane, v, vLinkPass);
        }
        if (lastLink != nullptr) {
            lastLink->myVLinkWait = MIN2(lastLink->myVLinkWait, v);
        }
        if (myLaneChangeModel->getShadowLane() != nullptr) {
            const MSLane* shadowLane = myLaneChangeModel->getShadowLane(leaderLane);
            if (shadowLane != nullptr
                    && (MSGlobals::gLateralResolution > 0 || getLateralOverlap() > POSITION_EPS
                        || myLaneChangeModel->getLaneChangeCompletion() < 0.5)) {
                if ((&shadowLane->getEdge() == &leaderLane->getEdge() || myLaneChangeModel->isOpposite())) {
                    double latOffset = getLane()->getRightSideOnEdge() - myLaneChangeModel->getShadowLane()->getRightSideOnEdge();
                    if (myLaneChangeModel->isOpposite()) {
                        latOffset = ((myLane->getWidth() + shadowLane->getWidth()) * 0.5
                                     - 2 * getLateralPositionOnLane());
                    }
                    MSLeaderInfo shadowLeaders = shadowLane->getLastVehicleInformation(this, latOffset, lane->getLength() - seen);
                    if (myLaneChangeModel->isOpposite()) {
                        shadowLeaders.removeOpposite(shadowLane);
                    }
                    const double turningDifference = MAX2(0.0, leaderLane->getLength() - shadowLane->getLength());
                    adaptToLeaders(shadowLeaders, latOffset, seen - turningDifference, lastLink, shadowLane, v, vLinkPass);
                } else if (shadowLane == myLaneChangeModel->getShadowLane() && leaderLane == myLane) {
                    MSLeaderDistanceInfo shadowLeaders = shadowLane->getFollowersOnConsecutive(this, myLane->getOppositePos(getPositionOnLane()), true);
                    const double latOffset = 0;
                    shadowLeaders.fixOppositeGaps(true);
                    adaptToLeaderDistance(shadowLeaders, latOffset, seen, lastLink, v, vLinkPass);
                }
            }
        }
        if (lane->getEdge().getPersons().size() > 0 && lane->hasPedestrians()) {
            const double relativePos = lane->getLength() - seen;
            const double stopTime = MAX2(1.0, ceil(getSpeed() / cfModel.getMaxDecel()));
            PersonDist leader = lane->nextBlocking(relativePos,
                                                   getRightSideOnLane(lane), getRightSideOnLane(lane) + getVehicleType().getWidth(), stopTime);
            if (leader.first != 0) {
                const double stopSpeed = cfModel.stopSpeed(this, getSpeed(), leader.second - getVehicleType().getMinGap());
                v = MIN2(v, stopSpeed);
            }
        }
        if (lane->getBidiLane() != nullptr) {
            const MSLane* bidiLane = lane->getBidiLane();
            if (bidiLane->getEdge().getPersons().size() > 0 && bidiLane->hasPedestrians()) {
                const double relativePos = seen;
                const double stopTime = ceil(getSpeed() / cfModel.getMaxDecel());
                const double leftSideOnLane = bidiLane->getWidth() - getRightSideOnLane(lane);
                PersonDist leader = bidiLane->nextBlocking(relativePos,
                                    leftSideOnLane - getVehicleType().getWidth(), leftSideOnLane, stopTime, true);
                if (leader.first != 0) {
                    const double stopSpeed = cfModel.stopSpeed(this, getSpeed(), leader.second - getVehicleType().getMinGap());
                    v = MIN2(v, stopSpeed);
                }
            }
        }
        if (!opposite && lane->getEdge().hasLaneChanger()) {
            const double vHelp = myLaneChangeModel->getCooperativeHelpSpeed(lane, seen);
            v = MIN2(v, vHelp);
        }
        bool foundRealStop = false;
        while (stopIt != myStops.end()
                && ((&stopIt->lane->getEdge() == &lane->getEdge())
                    || (stopIt->isOpposite && stopIt->lane->getEdge().getOppositeEdge() == &lane->getEdge()))
                && stopIt->edge == myCurrEdge + view) {
            double stopDist = std::numeric_limits<double>::max();
            const MSStop& stop = *stopIt;
            const bool isFirstStop = stopIt == myStops.begin();
            stopIt++;
            if (!stop.reached || (stop.getSpeed() > 0 && keepStopping())) {
                bool isWaypoint = stop.getSpeed() > 0;
                double endPos = stop.getEndPos(*this) + NUMERICAL_EPS;
                if (stop.parkingarea != nullptr) {
                    const double brakePos = getBrakeGap() + lane->getLength() - seen;
                    endPos = stop.parkingarea->getLastFreePosWithReservation(t, *this, brakePos);
                } else if (isWaypoint && !stop.reached) {
                    endPos = stop.pars.startPos;
                }
                stopDist = seen + endPos - lane->getLength();
                double stopSpeed = laneMaxV;
                if (isWaypoint) {
                    bool waypointWithStop = false;
                    if (stop.getUntil() > t) {
                        SUMOTime time2end = 0;
                        if (stop.reached) {
                            time2end = TIME2STEPS((stop.pars.endPos - myState.myPos) / stop.getSpeed());
                        } else {
                            time2end = TIME2STEPS(
                                           stopDist / ((getSpeed() + stop.getSpeed()) / 2)
                                           + (stop.pars.endPos - stop.pars.startPos) / stop.getSpeed());
                        }
                        if (stop.getUntil() > t + time2end) {
                            double distToEnd = stopDist;
                            if (!stop.reached) {
                                distToEnd += stop.pars.endPos - stop.pars.startPos;
                            }
                            stopSpeed = MAX2(cfModel.stopSpeed(this, getSpeed(), distToEnd), vMinComfortable);
                            waypointWithStop = true;
                            if (stopSpeed <= SUMO_const_haltingSpeed) {
                                const_cast<MSStop&>(stop).waypointWithStop = true;
                            }
                        }
                    }
                    if (stop.reached) {
                        stopSpeed = MIN2(stop.getSpeed(), stopSpeed);
                        if (myState.myPos >= stop.pars.endPos && !waypointWithStop) {
                            stopDist = std::numeric_limits<double>::max();
                        }
                    } else {
                        stopSpeed = MIN2(MAX2(cfModel.freeSpeed(this, getSpeed(), stopDist, stop.getSpeed()), vMinComfortable), stopSpeed);
                        if (!stop.reached) {
                            stopDist += stop.pars.endPos - stop.pars.startPos;
                        }
                        if (lastLink != nullptr) {
                            lastLink->adaptLeaveSpeed(cfModel.freeSpeed(this, vLinkPass, endPos, stop.getSpeed(), false, MSCFModel::CalcReason::FUTURE));
                        }
                    }
                } else {
                    stopSpeed = cfModel.stopSpeed(this, getSpeed(), stopDist);
                    if (!instantStopping()) {
                        stopSpeed = MAX2(stopSpeed, vMinComfortable);
                    } else if (myInfluencer && !myInfluencer->hasSpeedTimeLine(SIMSTEP)) {
                        std::vector<std::pair<SUMOTime, double> > speedTimeLine;
                        speedTimeLine.push_back(std::make_pair(SIMSTEP, getSpeed()));
                        speedTimeLine.push_back(std::make_pair(SIMSTEP + DELTA_T, stopSpeed));
                        myInfluencer->setSpeedTimeLine(speedTimeLine);
                    }
                    if (lastLink != nullptr) {
                        lastLink->adaptLeaveSpeed(cfModel.stopSpeed(this, vLinkPass, endPos, MSCFModel::CalcReason::FUTURE));
                    }
                }
                if (stopSpeed < getSpeed() && getSpeed() > SUMO_const_haltingSpeed) {
                    newStopSpeed = MIN2(newStopSpeed, stopSpeed);
                } else if (getSpeed() < SUMO_const_haltingSpeed) {
                    newStopSpeed = std::numeric_limits<double>::max();
                }
                v = MIN2(v, stopSpeed);
                if (lane->isInternal()) {
                    std::vector<MSLink*>::const_iterator exitLink = MSLane::succLinkSec(*this, view + 1, *lane, bestLaneConts);
                    assert(!lane->isLinkEnd(exitLink));
                    bool dummySetRequest;
                    double dummyVLinkWait;
                    checkLinkLeaderCurrentAndParallel(*exitLink, lane, seen, lastLink, v, vLinkPass, dummyVLinkWait, dummySetRequest);
                }
                if (isFirstStop) {
                    newStopDist = stopDist;
                    if (!isWaypoint) {
                        planningToStop = true;
                        if (!isRail()) {
                            lfLinks.emplace_back(v, stopDist);
                            foundRealStop = true;
                            break;
                        }
                    }
                }
            }
        }
        if (foundRealStop) {
            break;
        }
        std::vector<MSLink*>::const_iterator link = MSLane::succLinkSec(*this, view + 1, *lane, bestLaneConts);
        if (lane->isLinkEnd(link) && myLaneChangeModel->hasBlueLight() && myCurrEdge != myRoute->end() - 1) {
            const int currentIndex = lane->getIndex();
            const MSLane* bestJump = nullptr;
            for (const LaneQ& preb : getBestLanes()) {
                if (preb.allowsContinuation &&
                        (bestJump == nullptr
                         || abs(currentIndex - preb.lane->getIndex()) < abs(currentIndex - bestJump->getIndex()))) {
                    bestJump = preb.lane;
                }
            }
            if (bestJump != nullptr) {
                const MSEdge* nextEdge = *(myCurrEdge + 1);
                for (auto cand_it = bestJump->getLinkCont().begin(); cand_it != bestJump->getLinkCont().end(); cand_it++) {
                    if (&(*cand_it)->getLane()->getEdge() == nextEdge) {
                        link = cand_it;
                        break;
                    }
                }
            }
        }
        if (!encounteredTurn) {
            if (!lane->isLinkEnd(link) && lane->getLinkCont().size() > 1) {
                LinkDirection linkDir = (*link)->getDirection();
                switch (linkDir) {
                    case LinkDirection::STRAIGHT:
                    case LinkDirection::NODIR:
                        break;
                    default:
                        nextTurn.first = seen;
                        nextTurn.second = *link;
                        encounteredTurn = true;
                }
            }
        }
        if (myCurrEdge + view + 1 == myRoute->end()
                || (myParameter->arrivalEdge >= 0 && getRoutePosition() + view == myParameter->arrivalEdge)) {
            const double arrivalSpeed = (myParameter->arrivalSpeedProcedure == ArrivalSpeedDefinition::GIVEN ?
                                         myParameter->arrivalSpeed : laneMaxV);
            const double distToArrival = seen + myArrivalPos - lane->getLength() - SPEED2DIST(arrivalSpeed);
            const double va = MAX2(NUMERICAL_EPS, cfModel.freeSpeed(this, getSpeed(), distToArrival, arrivalSpeed));
            v = MIN2(v, va);
            if (lastLink != nullptr) {
                lastLink->adaptLeaveSpeed(va);
            }
            lfLinks.push_back(DriveProcessItem(v, seen, lane->getEdge().isFringe() ? 1000 : 0));
            break;
        }
        if (lane->isLinkEnd(link)
                || (MSGlobals::gSublane && brakeForOverlap(*link, lane))
                || (opposite && (*link)->getViaLaneOrLane()->getParallelOpposite() == nullptr
                    && !myLaneChangeModel->hasBlueLight())) {
            double va = cfModel.stopSpeed(this, getSpeed(), seen);
            if (lastLink != nullptr) {
                lastLink->adaptLeaveSpeed(va);
            }
            if (myLaneChangeModel->getCommittedSpeed() > 0) {
                v = MIN2(myLaneChangeModel->getCommittedSpeed(), v);
            } else {
                v = MIN2(va, v);
            }
            if (lane->isLinkEnd(link)) {
                lfLinks.emplace_back(v, seen);
                break;
            }
        }
        lateralShift += (*link)->getLateralShift();
        const bool yellowOrRed = (*link)->haveRed() || (*link)->haveYellow();
        double laneStopOffset;
        const double majorStopOffset = MAX2(getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_STOPLINE_GAP, DIST_TO_STOPLINE_EXPECT_PRIORITY), lane->getVehicleStopOffset(this));
        const double stopDecel = yellowOrRed && !isRail() ? MAX2(MIN2(MSGlobals::gTLSYellowMinDecel, cfModel.getEmergencyDecel()), cfModel.getMaxDecel()) : cfModel.getMaxDecel();
        const double brakeDist = cfModel.brakeGap(myState.mySpeed, stopDecel, 0);
        const bool canBrakeBeforeLaneEnd = seen >= brakeDist;
        const bool canBrakeBeforeStopLine = seen - lane->getVehicleStopOffset(this) >= brakeDist;
        if (yellowOrRed) {
            laneStopOffset = majorStopOffset;
        } else if ((*link)->havePriority()) {
            laneStopOffset = MIN2((*link)->getFoeVisibilityDistance() - POSITION_EPS, majorStopOffset);
        } else {
            double minorStopOffset = MAX2(lane->getVehicleStopOffset(this),
                                          getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_STOPLINE_CROSSING_GAP, MSPModel::SAFETY_GAP) - (*link)->getDistToFoePedCrossing());
            if ((*link)->getState() == LINKSTATE_ALLWAY_STOP) {
                minorStopOffset = MAX2(minorStopOffset, getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_STOPLINE_GAP, 0));
            } else {
                minorStopOffset = MAX2(minorStopOffset, getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_STOPLINE_GAP_MINOR, 0));
            }
            laneStopOffset = MIN2((*link)->getFoeVisibilityDistance() - POSITION_EPS, minorStopOffset);
        }
        if (canBrakeBeforeLaneEnd) {
            laneStopOffset = MIN2(laneStopOffset, seen - brakeDist);
        }
        laneStopOffset = MAX2(POSITION_EPS, laneStopOffset);
        double stopDist = MAX2(0., seen - laneStopOffset);
        if (yellowOrRed && getDevice(typeid(MSDevice_GLOSA)) != nullptr
                && static_cast<MSDevice_GLOSA*>(getDevice(typeid(MSDevice_GLOSA)))->getOverrideSafety()
                && static_cast<MSDevice_GLOSA*>(getDevice(typeid(MSDevice_GLOSA)))->isSpeedAdviceActive()) {
            stopDist = std::numeric_limits<double>::max();
        }
        if (newStopDist != std::numeric_limits<double>::max()) {
            stopDist = MAX2(stopDist, newStopDist);
        }
        if (isRail()
                && !lane->isInternal()) {
            if (lane->getBidiLane() != nullptr
                    && (*link)->getLane()->getBidiLane() == lane) {
                double vMustReverse = getCarFollowModel().stopSpeed(this, getSpeed(), seen - POSITION_EPS);
                if (seen < 1) {
                    mustSeeBeforeReversal = 2 * seen + getLength();
                }
                v = MIN2(v, vMustReverse);
            }
            foundRailSignal |= ((*link)->getTLLogic() != nullptr
                                && (*link)->getTLLogic()->getLogicType() == TrafficLightType::RAIL_SIGNAL
                                && seen > SPEED2DIST(v));
        }
        bool canReverseEventually = false;
        const double vReverse = checkReversal(canReverseEventually, laneMaxV, seen);
        v = MIN2(v, vReverse);
        if (myLaneChangeModel->isChangingLanes()) {
            if (    
                ((*link)->getDirection() == LinkDirection::LEFT || (*link)->getDirection() == LinkDirection::RIGHT) ||
                (myLaneChangeModel->getShadowLane() != nullptr &&
                 (*link)->getViaLaneOrLane()->getParallelLane(myLaneChangeModel->getShadowDirection()) == nullptr)) {
                const double timeRemaining = STEPS2TIME(myLaneChangeModel->remainingTime());
                assert(timeRemaining != 0);
                const double va = MAX2(cfModel.stopSpeed(this, getSpeed(), seen - POSITION_EPS),
                                       (seen - POSITION_EPS) / timeRemaining);
                v = MIN2(va, v);
            }
        }
        const bool leavingCurrentIntersection = myLane->getEdge().isInternal() && lastLink == nullptr;
        const bool abortRequestAfterMinor = slowedDownForMinor && (*link)->getInternalLaneBefore() == nullptr;
        bool setRequest = (v > NUMERICAL_EPS_SPEED && !abortRequestAfterMinor) || (leavingCurrentIntersection);
        double stopSpeed = cfModel.stopSpeed(this, getSpeed(), stopDist, stopDecel, MSCFModel::CalcReason::CURRENT_WAIT);
        double vLinkWait = MIN2(v, stopSpeed);
        if (yellowOrRed && canBrakeBeforeStopLine && !ignoreRed(*link, canBrakeBeforeStopLine) && seen >= mustSeeBeforeReversal) {
            if (lane->isInternal()) {
                checkLinkLeaderCurrentAndParallel(*link, lane, seen, lastLink, v, vLinkPass, vLinkWait, setRequest);
            }
            const SUMOTime arrivalTime = getArrivalTime(t, seen, v, vLinkPass);
            lfLinks.push_back(DriveProcessItem(*link, v, vLinkWait, false, arrivalTime, vLinkWait, 0, seen, -1));
            break;
        }
        const MSLink* entryLink = (*link)->getCorrespondingEntryLink();
        if (entryLink->haveRed() && ignoreRed(*link, canBrakeBeforeStopLine) && STEPS2TIME(t - entryLink->getLastStateChange()) > 2) {
            const double redSpeed = MIN2(v, getVehicleType().getParameter().getJMParam(SUMO_ATTR_JM_DRIVE_RED_SPEED, v));
            const double va = MAX2(redSpeed, cfModel.freeSpeed(this, getSpeed(), seen, redSpeed));
            v = MIN2(va, v);
        }
        checkLinkLeaderCurrentAndParallel(*link, lane, seen, lastLink, v, vLinkPass, vLinkWait, setRequest);
        if (lastLink != nullptr) {
            lastLink->adaptLeaveSpeed(laneMaxV);
        }
        double arrivalSpeed = vLinkPass;
        const double visibilityDistance = (*link)->getFoeVisibilityDistance();
        const double determinedFoePresence = seen <= visibilityDistance;
        const bool couldBrakeForMinor = !(*link)->havePriority() && brakeDist < seen && !(*link)->lastWasContMajor();
        if (couldBrakeForMinor && !determinedFoePresence) {
            double maxSpeedAtVisibilityDist = cfModel.maximumSafeStopSpeed(visibilityDistance, cfModel.getMaxDecel(), myState.mySpeed, false, 0., false);
            double maxArrivalSpeed = cfModel.estimateSpeedAfterDistance(visibilityDistance, maxSpeedAtVisibilityDist, cfModel.getMaxAccel());
            arrivalSpeed = MIN2(vLinkPass, maxArrivalSpeed);
            slowedDownForMinor = true;
        } else if ((*link)->getState() == LINKSTATE_EQUAL && myWaitingTime > 0) {
            std::pair<const SUMOVehicle*, const MSLink*> blocker = (*link)->getFirstApproachingFoe(*link);
            int n = 100;
            while (blocker.second != nullptr && blocker.second != *link && n > 0) {
                blocker = blocker.second->getFirstApproachingFoe(*link);
                n--;
            }
            if (n == 0) {
                WRITE_WARNINGF(TL("Suspicious right_before_left junction '%'."), lane->getEdge().getToJunction()->getID());
            }
            if (blocker.second == *link) {
                const double threshold = (*link)->getDirection() == LinkDirection::STRAIGHT ? 0.25 : 0.75;
                if (RandHelper::rand(getRNG()) < threshold) {
                    setRequest = false;
                }
            }
        }
        const SUMOTime arrivalTime = getArrivalTime(t, seen, v, arrivalSpeed);
        if (couldBrakeForMinor && determinedFoePresence && (*link)->getLane()->getEdge().isRoundabout()) {
            const bool wasOpened = (*link)->opened(arrivalTime, arrivalSpeed, arrivalSpeed,
                                                   getLength(), getImpatience(),
                                                   getCarFollowModel().getMaxDecel(),
                                                   getWaitingTime(), getLateralPositionOnLane(),
                                                   nullptr, false, this);
            if (!wasOpened) {
                slowedDownForMinor = true;
            }
        }
        double arrivalSpeedBraking = 0;
        const double bGap = cfModel.brakeGap(v);
        if (seen < bGap && !isStopped() && !planningToStop) { 
            if (MSGlobals::gSemiImplicitEulerUpdate) {
                arrivalSpeedBraking = cfModel.getMinimalArrivalSpeedEuler(seen, v);
                arrivalSpeedBraking = MIN2(arrivalSpeedBraking, arrivalSpeed);
            } else {
                arrivalSpeedBraking = cfModel.getMinimalArrivalSpeed(seen, myState.mySpeed);
            }
        }
        const double estimatedLeaveSpeed = MIN2((*link)->getViaLaneOrLane()->getVehicleMaxSpeed(this, maxVD),
                                                getCarFollowModel().estimateSpeedAfterDistance((*link)->getLength(), arrivalSpeed, getVehicleType().getCarFollowModel().getMaxAccel()));
        lfLinks.push_back(DriveProcessItem(*link, v, vLinkWait, setRequest,
                                           arrivalTime, arrivalSpeed,
                                           arrivalSpeedBraking,
                                           seen, estimatedLeaveSpeed));
        if ((*link)->getViaLane() == nullptr) {
            hadNonInternal = true;
            ++view;
        }
        if ((!setRequest || v <= 0 || seen > dist) && hadNonInternal && seenNonInternal > MAX2(vehicleLength * CRLL_LOOK_AHEAD, vehicleLength + seenInternal) && foundRailSignal) {
            break;
        }
        lane = (*link)->getViaLaneOrLane();
        laneMaxV = lane->getVehicleMaxSpeed(this, maxVD);
        if (myInfluencer && !myInfluencer->considerSpeedLimit()) {
            laneMaxV = std::numeric_limits<double>::max();
        }
        const double va = MAX2(cfModel.freeSpeed(this, getSpeed(), seen, laneMaxV), vMinComfortable - NUMERICAL_EPS);
        v = MIN2(va, v);
        if (lane->getEdge().isInternal()) {
            seenInternal += lane->getLength();
        } else {
            seenNonInternal += lane->getLength();
        }
        leaderLane = opposite ? lane->getParallelOpposite() : lane;
        if (leaderLane == nullptr) {
            break;
        }
        ahead = opposite ? MSLeaderInfo(leaderLane->getWidth()) : leaderLane->getLastVehicleInformation(nullptr, 0);
        seen += lane->getLength();
        vLinkPass = MIN2(cfModel.estimateSpeedAfterDistance(lane->getLength(), v, cfModel.getMaxAccel()), laneMaxV); 
        lastLink = &lfLinks.back();
    }
}
```

### MSVehicle::setApproachingForAllLinks

[microsim/MSVehicle.cpp:5495-5551]

```cpp
MSVehicle::setApproachingForAllLinks() {
    if (!myActionStep) {
        return;
    }
    removeApproachingInformation(myLFLinkLanesPrev);
    for (DriveProcessItem& dpi : myLFLinkLanes) {
        if (dpi.myLink != nullptr) {
            if (dpi.myLink->getState() == LINKSTATE_ALLWAY_STOP) {
                dpi.myArrivalTime += (SUMOTime)RandHelper::rand((int)2, getRNG()); 
            }
            dpi.myLink->setApproaching(this, dpi.myArrivalTime, dpi.myArrivalSpeed, dpi.getLeaveSpeed(),
                                       dpi.mySetRequest, dpi.myArrivalSpeedBraking, getWaitingTimeFor(dpi.myLink), dpi.myDistance, getLateralPositionOnLane());
        }
    }
    if (isRail()) {
        for (DriveProcessItem& dpi : myLFLinkLanes) {
            if (dpi.myLink != nullptr && dpi.myLink->getTLLogic() != nullptr && dpi.myLink->getTLLogic()->getLogicType() == TrafficLightType::RAIL_SIGNAL) {
                MSRailSignalControl::getInstance().notifyApproach(dpi.myLink);
            }
        }
    }
    if (myLaneChangeModel->getShadowLane() != nullptr) {
        for (const DriveProcessItem& dpi : myLFLinkLanes) {
            if (dpi.myLink != nullptr) {
                MSLink* parallelLink = dpi.myLink->getParallelLink(myLaneChangeModel->getShadowDirection());
                if (parallelLink == nullptr && getLaneChangeModel().isOpposite() && dpi.myLink->isEntryLink()) {
                    parallelLink = dpi.myLink->getOppositeDirectionLink();
                }
                if (parallelLink != nullptr) {
                    const double latOffset = getLane()->getRightSideOnEdge() - myLaneChangeModel->getShadowLane()->getRightSideOnEdge();
                    parallelLink->setApproaching(this, dpi.myArrivalTime, dpi.myArrivalSpeed, dpi.getLeaveSpeed(),
                                                 dpi.mySetRequest, dpi.myArrivalSpeedBraking, getWaitingTimeFor(dpi.myLink), dpi.myDistance,
                                                 latOffset);
                    myLaneChangeModel->setShadowApproachingInformation(parallelLink);
                }
            }
        }
    }
}
```

### MSCFModel::applyStartupDelay

[microsim/cfmodels/MSCFModel.cpp:269-285]

```cpp
MSCFModel::applyStartupDelay(const MSVehicle* veh, const double vMin, const double vMax, const SUMOTime addTime) const {
    UNUSED_PARAMETER(vMin);
    if (veh->getTimeSinceStartup() > 0 && veh->getTimeSinceStartup() - DELTA_T < myStartupDelay + addTime) {
        assert(veh->getSpeed() <= SUMO_const_haltingSpeed);
        const SUMOTime remainingDelay = myStartupDelay + addTime - (veh->getTimeSinceStartup() - DELTA_T);
        if (remainingDelay >= DELTA_T) {
            return 0;
        } else {
            return (double)(DELTA_T - remainingDelay) / (double)DELTA_T * vMax;
        }
    }
    return vMax;
}
```

### MSCFModel_ACC::insertionFollowSpeed

[microsim/cfmodels/MSCFModel_ACC.cpp:161-187]

```cpp
MSCFModel_ACC::insertionFollowSpeed(const MSVehicle* const v, double speed, double gap2pred, double predSpeed, double predMaxDecel, const MSVehicle* const ) const {
    const int max_iter = 50;
    int n_iter = 0;
    const double tol = 0.1;
    const double damping = 0.1;
    double res = speed;
    while (n_iter < max_iter) {
        const double a = SPEED2ACCEL(followSpeed(v, res, gap2pred, predSpeed, predMaxDecel, nullptr, CalcReason::FUTURE) - res);
        res = res + damping * a;
        if (fabs(a) < tol) {
            break;
        } else {
            n_iter++;
        }
    }
    return res;
}
```

### MSCFModel_CACC::insertionFollowSpeed

[microsim/cfmodels/MSCFModel_CACC.cpp:212-245]

```cpp
MSCFModel_CACC::insertionFollowSpeed(const MSVehicle* const veh, double speed, double gap2pred, double predSpeed, double predMaxDecel, const MSVehicle* const pred) const {
    const int max_iter = 50;
    int n_iter = 0;
    const double tol = 0.1;
    double damping = 0.8;
    double res = speed;
    while (n_iter < max_iter) {
        const double vCACC = _v(veh, pred, gap2pred, res, predSpeed, speed, true);
        const double vSafe = maximumSafeFollowSpeed(gap2pred, res, predSpeed, predMaxDecel, true);
        const double a = MIN2(vCACC, vSafe) - res;
        res = res + damping * a;
        damping *= 0.9;
        if (fabs(a) < tol) {
            break;
        } else {
            n_iter++;
        }
    }
    return res;
}
```

Acceleration profile interpolation uses piecewise linear interpolation, with endpoint values outside its domain; base getCurrentAccel(v)=min(accel, desiredProfile(v) if present, maxProfile(v) if present). This cap is shared by all maxNextSpeed calls, while IDM's internal acceleration expression uses its scalar accel. [microsim/cfmodels/MSCFModel.cpp:1167-1178; microsim/cfmodels/MSCFModel_IDM.cpp:254]

## 8. Minimal GPU state and approximation priorities

Implementation recommendation, derived from the read/write sets above: immutable type table holds geometry, CF/LC model IDs and parameters; route/lane/link/TLS tables are shared. Per-vehicle fixed-size record: IDs/type/route and route cursor; lane/front position, previous/current speed, stored acceleration, previous displacement; chosen/original speedFactor; action clock/flag; consecutive waiting, optional accumulated-wait ring indices, timeLoss; next stop index/reached/startup time/stopSpeed/stopDist; junction wait/entry timestamps, impatience and request flags; RNG counter; LC state/shadow/target; drive-item pool offset/count/current cursor; rear-lane span offset/count. Controller union: Krauss held acceleration+offset if sigmaStep>dt; IDM none, IDMM levelOfService; ACC mode+lastUpdateTime; CACC adds cooperative mode+communications override. GLOSA adds next TLS index, distance/range, original factor, advice-active and option flags. [microsim/MSVehicle.cpp:2162-2225,4293-4317,4635-5018; microsim/cfmodels/MSCFModel_Krauss.cpp:43-62; microsim/cfmodels/MSCFModel_IDM.cpp:94-101; microsim/cfmodels/MSCFModel_ACC.cpp:98-118; microsim/cfmodels/MSCFModel_CACC.h:190-239; microsim/devices/MSDevice_GLOSA.cpp:97-120]

A fixed per-vehicle record is possible; a universally sufficient fixed **embedded lookahead array** is not justified. Horizon grows with braking distance and may span arbitrarily many short internal/ordinary lanes. Use bounded shared pools with overflow detection/fallback, not silent truncation. Same concern applies to rear occupancy across several short lanes and waiting-history intervals. [microsim/MSVehicle.cpp:2332-2333,3076-3114,4785-4815,208-241]

Ranked recommendations (engineering inference; validate statistical equivalence with distributions of throughput, travel time, queue length, discharge headway, speed and emergency-braking rates at BOTH dt values):

1. Preserve minGap/length, speedFactor heterogeneity, tau/decel/apparentDecel, model-specific dt equations and action timing. These directly determine equilibrium spacing, capacity, braking waves and free-flow speed. [microsim/cfmodels/MSCFModel.cpp:87-195,860-1015; microsim/cfmodels/MSCFModel_IDM.cpp:225-268]
2. Preserve TLS order, complete approach barrier, downstream storage, conflict priority, lane-change effects and insertion competition. These determine bottleneck discharge, gridlock and demand admission; removing them can dominate any CF tuning. [microsim/MSNet.cpp:873-932; microsim/MSVehicle.cpp:3744-3975,5180-5525]
3. Preserve Krauss stochastic effect statistically, IDM substeps, ACC/CACC hysteresis and CACC's source dt asymmetry. Counter RNG can replace SUMO's sequence if its temporal/spatial correlations are checked; byte identity is unnecessary. [microsim/cfmodels/MSCFModel_Krauss.cpp:94-175; microsim/cfmodels/MSCFModel_IDM.cpp:38-48,245-268; microsim/cfmodels/MSCFModel_ACC.cpp:244-313; microsim/cfmodels/MSCFModel_CACC.cpp:385-500]
4. Include GLOSA when enabled by scenarios; it changes arrival timing and signal utilization. Drop it only for unequipped demand. [microsim/devices/MSDevice_GLOSA.cpp:76-86,122-295,501-609]
5. Initially omit emission/GUI/reminder output machinery, detailed angle smoothing, warning text, CF serialization, and accumulated-wait history when only consecutive waiting and aggregate travel statistics are measured. These omissions are much lower risk than altering speed/junction equations. EIDM, rail, oncoming driving, continuous/sublane LC and walking require explicit scenario exclusions or separate specs, not silent substitution. [microsim/MSVehicle.cpp:4967-5018,4817-4913; microsim/cfmodels/MSCFModel_IDM.cpp:57-76; microsim/MSNet.cpp:899-925]

