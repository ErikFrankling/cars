# Requirements for the communicating self-driving model

From Erik, binding on whoever builds it.

## Communication
- Every automated car and every roadside unit communicates. No car or junction is left out unless the experiment says so.
- Cars broadcast position, speed, heading, acceleration, braking capability and their intended trajectory ahead of time. Roadside units and traffic lights broadcast signal state, timing and junction layout, and receive car data.
- Message types, fields, rates and sizes follow real standards as closely as the evidence allows. See `12-v2x-messages-and-rsu.md`. State every departure from a standard.
- "Exact" is a goal, not an assumption: broadcast values carry modelled position error, age and loss. Real channel limits apply, including congestion when many cars share the air. Safety never relies on a message arriving.

## Safety
- From first principles, using braking capability. Spec in `08-v2x-and-safety-first-principles.md`.
- Zero collisions and zero teleports are hard pass or fail tests, checked in 2D including junctions. Gridlock is reported as a failure with its location.

## Visualise
- Show the communication in clips: who is broadcasting, range, links, lost messages, roadside units, planned trajectories, granted crossing slots.
- Rendered from recorded data with `cars replay`, never at a cost to simulation speed.

## Measure every feature on and off
Each communication and coordination feature is a factor that can be switched independently, compared against a baseline with identical demand, seeds and network:

1. No communication (sensors only)
2. Status broadcast, vehicle to vehicle
3. Plus intended trajectories
4. Plus traffic light data to cars (signal timing, speed advisory)
5. Plus cars to traffic lights (adaptive signals from car data)
6. Plus coordinated crossing without signals
7. Each of the above at several message loss levels and several shares of automated cars, down to and including no humans

Report for each: travel time, delay, congestion (queue length, stopped time, throughput), energy use per km and per trip from the physics layer, number of stops, safety margins, and channel load.

Report the gain or loss of each feature honestly, including when a feature does nothing or makes things worse. Field evidence says many simulated gains have been artefacts.

## Several kinds of self-driving car, compared statistically
Erik: "implement multiple self-driving cars, make one that is legit ML, a real neural network trained for this. It of course has perfect input and output, so it's much easier than the real-world problem, but it might give some insight. Let's see in statistics how many different types of AI cars behave and affect stats."

Each type is a selectable model and a factor in the experiments, at every share of automated cars:
- Sensor-only safe driver, no communication.
- ACC and CACC style, as in the thesis.
- Communicating planner: shares intent, negotiates lane changes and crossings.
- A real trained neural network, run as a learned policy on the GPU. See `13-learned-drivers.md`. Report it with and without the safety rule on top, so the raw behaviour is visible.
- Add more when there's a reason, for example a selfish one and a fleet-optimising one.

Self-driving cars ask to be let in by communicating.

## Human courtesy
Erik: "human drivers should always let people in eventually. That's how human traffic works. Maybe chances decrease with higher numbers and relative speeds, but humans do follow rules and react to someone blinking."

A waiting car signals, and sooner or later a driver lets it in. The chance depends on speed, relative speed, how many have passed and how long it has waited. Spec with real measurements in `14-human-courtesy.md`. No gap should be waited for forever.

## Model tiers
Erik: "I want proper AV models built, many of them, tiers, each one built with more features, and deterministic normal programming and some ML."

Each tier is its own selectable model, adding one capability to the tier below, so the gain from each capability can be measured on its own. All tiers obey the safety rule unless marked raw.

Deterministic, normal programming:
- D1 Safe sensor driver: gap from braking physics, smooth control, no communication.
- D2 Predictive: looks several cars ahead by sensor, damps stop-and-go waves.
- D3 Connected follower: receives neighbours' status and verified braking capability.
- D4 Negotiating: broadcasts intended paths, asks and answers for lane changes and merges.
- D5 Signal aware: receives traffic light timing, adjusts speed to arrive on green.
- D6 Signal partner: also feeds traffic lights, which adapt to the cars coming.
- D7 Platooning: signed stop-line promises allow shorter gaps. Severity tradeoff reported.
- D8 Signal-free crossing: coordinated conflict slots with exit-clear checks.
- D9 Network coordinated: junctions share spillback credit, fleet routing.

Machine learning, real trained networks:
- M1 Learned following: sensor inputs only, trained on stop-and-go, merges.
- M2 Learned driving: following and lane changes with neighbours' status.
- M3 Learned cooperation: receives intents, negotiates merges and crossings.
- M4 Learned communication: if research supports it, learns what to send.
- Each with and without the safety rule on top (raw), and variants trained for a selfish reward and a fleet reward.

Every tier runs at every share of automated cars, including mixed tiers and no humans. Tier numbering may change with evidence, but each capability stays separately switchable.
