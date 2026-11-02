# Status board

The orchestrator keeps this current. Agents work on the top of the critical path. A thread whose work doesn't move a number here within two rounds gets stopped or redirected.

## Goal
Human-only traffic on the Berlin district (49 km²): teleports off, full demand, report 15's Credible thresholds on held-out sites. Reaching that is the milestone; everything else serves it or waits.

## Numbers that count
| Number | Now | Target |
|---|---|---|
| Berlin district, teleports off, 10% demand | Finishes, 0 late | Done |
| Berlin district, 50% demand | Jams: 3.8 x the 10% level by 08:00 | No persistent queue |
| Berlin district, 100% demand | Stopped, 2.6 x at 06:30 | Finishes, under 0.5% unfinished |
| Hourly flow GEH<5, tuning sites | 23% (10% day x10) | Credible 60%, real floor 93% |
| Rush-hour dip, motorway, lowest / highest hour | 0.96 | Real 0.46 |
| Jam hours caught / false alarms | 25% / 88% | Credible 60% / 40% |
| Benchmark, fast mode, failures (human driver) | 31 fail, 16 at floor, 37 no data | Fails falling every round |

## Critical path
1. Route assignment on the Berlin district at 50% (does the map hold under sensible routes?).
2. Map and signals at 50%: one controller per junction, give-way capacity, generated signals.
3. Capacity per road class with the human and physical drivers.
4. 100% with teleports off.
5. Open locked sites once. Then Madrid.

## Not on the critical path, parked
- Stockholm: back when data requests deliver. No more Stockholm runs.
- Self-driving tiers, neural tiers, signal-free junctions: until the milestone.
- Learned-driver prototype: after the milestone, per report 21.
- Jinan: done as a congestion cross-check.

## Rules against rabbit holes
- Fix a cause only if it moves a number above or a benchmark metric ranked in the worst gaps.
- Two rounds with no gain on a problem: stop, write down what was tried, take the next item.
- Merge to main often. One base, no long-lived branches.
- At most 5 agents at once, because the PC can't take more.
