# Stockholm: what route assignment and calibration got to

Parked 2026-11-02 by the status board. This is what exists; the rest is marked as not finished. Everything here ran with **teleports on (120 s) and the junction blocker on (20 s), a labelled workaround**, on the `cars` kernel before the physics layer. Code is `crates/cars-assign`, runs are in `cars-data/truth/assign/runs/`, per-iteration files and plots in `results/assign/`.

## Short answer

**The loop runs at city scale and helps a lot, but this Stockholm is not close to real, and calibration does not help.** On the full-scale demand, selection rows chose the uncalibrated run. Its test rows, opened once, give **67% WAPE, 46% of rows with GEH under 5, and 77% of the counted traffic**, against a noise floor of about 12%. Cut the demand no further and fit no harder: fitting makes unseen rows worse.

## The result that counts

Primary: replacement demand at full scale (`v2_a26.rou.gz`, 1,318,869 trips, 8 km mean) on `n7_ramps`, started from its fitted routes, 20 iterations. Counts are measured Arstrafik, matched to this net: train 340 sites, selection 69, frozen spatial hold-out 181, plus 2025 values at 451 sites. Test rows were kept out of everything until one evaluation (`test_opened.json`).

| On unseen seeds, 4 averaged | Train | Selection | Held peak | **Test** | 2025 values |
|---|---:|---:|---:|---:|---:|
| WAPE | 62.9% | 58.6% | 67.6% | **67.3%** | 62.3% |
| GEH under 5 | 45.9% | 51.6% | 25.8% | **46.0%** | 46.8% |
| Simulated over counted | 0.73 | 0.78 | 0.50 | **0.77** | 0.70 |

The floor is 12.2%: 2023 against 2024 at calibration sites, on annual weekday means. Stockholm has no dated days, so true day-to-day noise is unmeasured and this is a stand-in. Berlin's lane-hour median is 8.7%. Test error is 5.5 times the floor.

**Not converged.** Unseen-seed gap 34%, target 2%. Unfinished 9.3%, limit 0.1%. About 1.03 M teleports a day, or 78 per 100 trips. Mean trip 6,778 ± 1,019 s. Without the valve this net and demand would stall. Over the 20 iterations unfinished fell from 26% to 5.4% in the loop and selection error from 68% to about 60%, with no change to the OD.

## Calibration doesn't help

| Run, from the same state | Trips | Train | Selection | Unfinished | Limits on change |
|---|---:|---:|---:|---:|---|
| No fit | 1,318,869 | 62.8% | **58.4%** | 7.9% | n/a |
| Fit, TAG limits enforced | 1,318,869 | 62.4% | 60.0% | 5.6% | Pass, because no change passes: α = 0 |
| Fit, limits off, round 1 | 1,347,766 | 57.5% | 63.1% | 11.7% | Fail: cell R² 0.84, sector change 333% |
| Fit, limits off, round 2 | 1,357,619 | 57.5% | 64.6% | 15.3% | Fail: cell R² 0.71 |

Training error falls while selection error rises and more trips stay unfinished. **That is a fit explaining noise and demand the net cannot carry.** Asked what scale it wants, the fit adds only 3%: the shortfall against counts is what the jammed net fails to deliver, not missing trips. The fit took no scale factor and removed no one to pass.

## Other runs, for context

| Run | Iterations | Unfinished | Teleports/day | Selection WAPE | Notes |
|---|---:|---:|---:|---:|---|
| Prior A: old 60% ODs on v5, routes dropped | 20 | 0.6% | 33,000 | 74% | Short trips: carries a third of counted traffic. Test 79% was logged during its loop, so it isn't blind, though nothing used it |
| Same 1.32 M trips on v5 register net | **6 of 8** | 32% | 2.1 M | 74% | Sensitivity. Locks harder than n7 under the same OD. Which part is generated signal programs is not separated |
| Prior B: gravity on road length, 0.9 M trips, 13 km mean | 5 | 48% | 1.6 M | | Abandoned early by the new decision |

Without the valve, prior A at 3 iterations stalled at 21:00 with 65% unfinished.

## Not finished

- v5 sensitivity stopped at iteration 6 of 8, with no unseen-seed evaluation. Its test rows were never opened.
- Refit from a second prior, which the spec asks for, was not done on Stockholm, so OD identifiability is unknown there. The grid version was stopped too.
- Prior B never got a calibration. Prior A's calibrations were dropped.
- No speed or travel-time check: 49% of records have speed but none by peak hour. Rung 3 prior from public statistics was not built.
- Verdict ladder on the primary, labelled run: `network_suspect`. Eight of the first queued links discharge under half their nominal rate when tested alone, no cut is violated, and half the demand finishes with nobody left and an 882 s mean trip. That fits the Stockholm report: this is the map before it is the demand. It is one day and one seed.
