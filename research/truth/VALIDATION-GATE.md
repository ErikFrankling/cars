# Human-only validation gate

Binding. From Erik:

"We should only do a simulation if we know it's good and accurate. Don't include things because we used them in our bachelor, or like Stockholm. Are you sure the trips data we are trying to simulate is accurate? Are you sure the traffic light timings are accurate, and 500 other things? If our results at a network level consistently, significantly differ from what you would expect from real-world traffic, we are very wrong."

"It's pointless to be testing out our new fancy AV models if we can't prove that with only the human-like cars we get somewhat close to real metrics of a real measured day in some city."

## Rule
1. **Human-only comes first.** No AV result counts, and no AV work gets GPU time, until a scenario with only human-like cars passes this gate.
2. **A scenario earns its place with evidence.** Having used it before, in the thesis or anywhere, is no reason to keep it. Scenarios that can't pass are benchmarks for speed only, and are labelled so everywhere, or dropped.
3. **Every input is labelled** measured, estimated or invented, with its source. See `data-hunt/16-input-audit.md`.
4. **Test on a real measured day, with data the model never saw.** Compare one simulated day against one real day, in the same units and with the same measuring method as the real data.

## What must match
Thresholds come from `data-hunt/14-normal-day.md` and `15-how-to-match-reality.md`. The basic bar is report 04's: the simulation may differ from a real day by no more than one real day differs from another, and where it can't reach that, the gap is reported as a failure.

| Check | Question |
|---|---|
| Nothing stuck | At normal demand, with teleports off, does the day finish with no gridlock? |
| Day shape | Do hourly flows have the real morning peak, midday, evening peak and night? |
| Volume | Do flows at real sensors match, site by site, and does total distance driven match? |
| Speed by hour | Do speeds by road class and hour match real probe speeds, including the rush-hour dip? |
| Travel times | Do real routes take the real time, at each hour? |
| Where and when | Do jams form in the places and at the times they really do, and clear when they really clear? |
| Network curve | Does the network's load against output look like the real one? |
| Trips | Do trip lengths and durations match surveys or trajectories? |

A scenario that passes some checks and fails others reports exactly that. No overall "validated" label without all of them.
