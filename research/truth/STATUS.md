# Status board

The orchestrator keeps this current. Agents work on the top of the critical path. A thread whose work doesn't move a number here within two rounds gets stopped or redirected.

## Goal
Human-only traffic on the Berlin district (49 km²): teleports off, full demand, report 15's Credible thresholds on held-out sites. Reaching that is the milestone; everything else serves it or waits.

## Numbers that count
| Number | Now | Target |
|---|---|---|
| Berlin district, old driver, cars running at 07:30, 10% demand | 1,403, finishes | Done, the reference for "healthy" |
| Same, 50% demand | 14,792 with one program per junction (healthy 7,015; SUMO on same inputs 22,515) | Near 7,015, no persistent queue |
| Same, with assigned routes (`cars-assign`) | 13,691; assignment from a jam stalls, 38-55% unfinished; stepped run queued | Relative gap under 2%, no persistent queue |
| Physical driver, cars running at 07:30, 10% / 50% | 2,948 / 31,955 | Same as healthy: 1,403 / 7,015 |
| Human driver, cars running at 07:30, 10% | 11,088 | 1,403 |
| Saturation flow 50 km/h, old / physical / human | 1,895 / 1,714 / 1,500 | 1,800-2,100 |
| Motorway flow per lane, old / physical / human | 2,001 / 1,590 / 1,503 | 1,800-2,300 |
| Give-way capacity against Siegloch, old driver | 57-66% of reference | Near 100% |
| Berlin district, 100% demand | Stopped, 2.6 x at 06:30 | Finishes, under 0.5% unfinished |
| Hourly flow GEH<5, tuning sites | 23% (10% day x10) | Credible 60%, real floor 93% |
| Rush-hour dip, motorway, lowest / highest hour | 0.96 | Real 0.46 |
| Jam hours caught / false alarms | 25% / 88% | Credible 60% / 40% |
| Benchmark, fast mode, failures (human driver) | 31 fail, 16 at floor, 37 no data | Fails falling every round |

## Critical path
1. Capacity in band for the physical driver, then human decisions on top of it. Until then the old driver is only the instrument for testing the map.
2. Berlin 50%: base map with one program per junction, boundary test with a larger cut, seed junctions, turn and bus lanes.
3. Routes on this map's lanes: 268-317 edges carry over 900 vehicles per lane per hour at full demand, traffic sits on roads smaller than in reality.
4. 100% with teleports off.
5. Open locked sites once. Then Madrid.

## Not on the critical path, parked
- Stockholm: back when data requests deliver. No more Stockholm runs.
- Self-driving tiers, neural tiers, signal-free junctions: until the milestone.
- Learned-driver prototype: after the milestone, per report 21.
- Jinan: done as a congestion cross-check.
- Signal generators: two rounds with no gain at 50%. Back when Hamburg gives real cycles and greens.

## Rules against rabbit holes
- Fix a cause only if it moves a number above or a benchmark metric ranked in the worst gaps.
- Two rounds with no gain on a problem: stop, write down what was tried, take the next item.
- Merge to main often. One base, no long-lived branches.
- At most 5 agents at once, because the PC can't take more.
