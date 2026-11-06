# Signals read from stop-line crossings: the reader and its error

6-7 November 2026. Forecasts F500-F505 in `foundations/forecasts.csv`, written before the reader ran. Code `scripts/replay/signals.py`, numbers [signals.json](signals.json).

pNEUMA and Songdo log no signals, so their greens have to be read from the traffic. PLAN.md calls that circular unless the reading is scored where the controller's states are known, and its error carried as a band on every result that uses it. This is that score.

## The reader

It sees only per-vehicle tracks along one signal group's path: time, front position relative to the stop line, speed, lateral offset, class (car, or two- and three-wheeler). Dataset code decides which vehicles use the group.

- **Stop line**: where queue heads stand. A head is a standing car with no car standing ahead of it in its lane within 25 m that crosses within 20 s of starting (parked and blocked cars don't). The line is the median of the densest 4 m of head positions, plus 1 m.
- **Onset, per cycle**: a head that stood at least 2 s within 10 m of the line and starts (passes 1.5 m/s). Heads starting within 6 s of each other are one onset (lanes start together). Onset = their median start minus `d_start`.
- **End, per cycle**: the last car crossing faster than 2 m/s before the first car that comes to stand at the line after the onset, minus `d_end`.
- **Fixed time** (pre-timed controllers; Athens is pre-timed): the cycle is the longest period in 40-180 s whose circular concentration of head starts is within 5% of the best (so a harmonic is not taken). The onset phase is their circular mean. The end is either the start of the longest empty arc of moving car crossings (`arc`) or the next onset at the same junction minus the intergreen (`next onset`).
- `d_start` and `d_end` are biases measured on another site, never on the scored one: DLR UT and SinD swap. For the fixed-time end, Tianjin and Chongqing swap.

## Scores

Truth: DLR UT's controller log (24 h, 1 Hz, signal groups 1 and 3-9, scored 06-22 h; group 2 has no users in the tracks) and SinD's light logs (Tianjin and Chongqing, 20 min each). Changchun's log is several seconds off (measure/RESULTS.md); Xi'an is held out. Neither was read.

| | DLR UT (actuated, Sunday) | SinD Tianjin + Chongqing (fixed time, weekday) |
|---|---|---|
| Greens scored | 5,421, of which 2,698 had a car standing at onset | 195, of which 71 had a car standing |
| Bias used | `d_start` 2.0 s (from SinD) | `d_start` 1.83 s (from DLR UT) |
| **Onset error, car standing at onset** | **median 0.58 s, p90 1.38 s**, bias −0.17 s | **median 0.59 s, p90 2.26 s**, bias +0.17 s |
| Missed, car standing at onset | 7.7% | 7.0% |
| False greens among read | 0.3% | 0 |
| Greens with nobody standing | 2,723; 2% read | 124; 7% read |
| End per cycle | 8.0 s even with 4+ standing (206 cycles): the controller gaps out after the queue | 17.6 s |
| Stop line found from heads, moved from the documented / first guess | 4.3-6.8 m behind DLR UT's documented points | 0.4-3 m; 38-41 m on Tianjin approach 2, where a parked car had dragged the first guess |

Onset error by queue at onset, DLR UT: 1-3 standing 0.58 s (2,282 greens), 4 or more 0.58 s (206), oversaturated 0.98 s (1). SinD had queues of 1-3 cars only.

Why greens are missed (DLR UT, 209): the car standing nearest the line was more than 10 m back (101), its track ended before the line (86, tracker fragments or a turn), or it stood under 2 s (20).

**Fixed-time fits** (SinD, 9 groups with a constant cycle; DLR UT is actuated, so none there):

| | Median of group medians | p90 of group medians |
|---|---|---|
| Cycle length error | 0.05 s | 0.13 s |
| Onset error | 0.56 s | 1.37 s |
| End error, empty arc of crossings | 2.64 s | 5.07 s |
| End error, next onset minus intergreen | 1.06 s | 19.7 s |

- The `arc` end biases differ by city: Tianjin +0.26 s, Chongqing −2.17 s. Each was applied to the other.
- `next onset` is 0.5-2.1 s wherever every phase at the junction has a read approach. On two Chongqing groups one phase had no approach read, so it jumped a whole phase (19-21 s). It can only be used where all phases are seen.
- Intergreen: Tianjin 4.0 s, Chongqing 3.0 s.

## The band carried by every result that uses read signals

| | Band |
|---|---|
| Green onset | ±0.6 s median, ±1.4 s p90 (per cycle or fixed time, either kind of site) |
| Green end (fixed time, empty arc) | ±2.6 s median, ±5 s p90; the cross-site bias itself spans 2.4 s |
| Cycle length | ±0.05 s over 20 minutes |
| Missed greens | 7-8% of cycles with a car standing, when read per cycle. Fixed-time programs miss none |

What this means downstream:
- A discharge error per cycle smaller than about 2.6 s × saturation flow (about 1-1.5 cars at 2-2.6 s per car) can't be told from a misread end.
- A start-up lost time can't be tested on read signals to better than ±0.6 s.
- The onset is unbiased (±0.2 s) once `d_start` from the other site is applied. So the reading doesn't make a driver's launch look early or late on average.

pNEUMA uses `d_start` 1.9 s (the mean of DLR UT's 1.83 and SinD's 2.0) and the fixed-time `arc` end with `d_end` −0.95 s (the mean of SinD's two cities). The spread between those sources is part of the band above. The band comes from German Sunday traffic and Chinese mixed traffic; Athens is a third kind and has no truth here.

## Rerun

```sh
python3 -I scripts/replay/signals.py dlrut; python3 -I scripts/replay/signals.py sind; python3 -I scripts/replay/signals.py score
```
