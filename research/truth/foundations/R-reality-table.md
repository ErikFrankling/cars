# R: The reality table (rung 1)

Status: definitions only, committed before any table is computed. Results follow below once computed. Reference is reality. No simulation and no GPU.

## Definitions, written before computing

**Days.** The 8 frozen tuning days in `step1/freeze.json`, all May 2019. No other month is opened.

**Sites.** Loop stations with quality `trusted` that aren't in `locked_sites_all_berlin`. Scope `district` is the 63 `tuning_sites`. Scope `berlin` is the unlocked trusted stations outside the box, needed because the district has no motorway loop. The loader drops locked rows before anything else reads them. Faulty site-days stay dropped, as in `real_days.csv.gz`.

**Probes.** HERE Traffic4cast May 2019, 8 tuning days, joined to the v6.4 edges by MeTS-10's cell join and trust filter, kept at 15 minutes. Two speeds per edge and interval: `v_med`, the median over the edge's cells (MeTS-10, as in `edge_hour.csv.gz`), and `v_hm`, the harmonic mean over cells, which is what a car crossing the edge would average. An edge's free speed `v_free` is its 90th percentile of 15-minute `v_med` over the 8 days. Raw and per-edge probe data stays out of the repo; only derived tables go in.

### 1. `real_jams.csv`

- **Jam interval (probes):** `v_med < v_free / 3` (FHWA 2019's rule of thumb) with volume at least 5 in the 15 minutes.
- **Jam episode:** 2 or more consecutive jam intervals on an edge on a day (30 minutes, the width of Gomes' onset windows).
- **Check on a sample, before the list is read.** At tuning sites, take site-hours where the loop's hourly speed is under half its own free speed. If the one-third rule on the same edge's probes misses more than half of these, the primary threshold becomes `v_free / 2`, and the report says so. Both thresholds are always computed.
- **A place:** edges joined when their jam episodes overlap in time on the same day and one edge flows into the next, within an AM (05-11 h) or PM (12-21 h) period. Across days, places are joined if they share an edge. The **head** is the most downstream edge jammed on the most days. Extent is the km of edges jammed on at least 2 days, and also the median per day.
- **Start, end:** per day, first and last jam interval of the place; median and full range over days.
- **Repeatability:** days of 8 with an episode at the place. A row needs at least 2 days. One-day rows go to a count, not the list.
- **Loop rows:** site-hours where hourly speed is under a third (and separately under half) of the site's free speed, on tuning sites, with flow of at least 50/h. Listed with `source=loop`.
- **Cause:** filled only if the map plainly shows it at the head: lane drop, motorway merge or diverge. The head's junction type is a separate column (`signal` isn't a cause by itself). Otherwise blank.
- **Noise:** all 28 day pairs: Jaccard of jam edges by period, share of day A's jam edge-hours also jam on day B, top-20 heads shared. Also the list built from 4 days against the other 4.

### 2. `real_capacity.csv`

- **Flow per lane:** station flow over detectors reporting, per hour. Also the highest single lane, from the per-detector file.
- **Queue present:** hourly loop speed `< 0.7 × site free`, where site free is the site's 90th percentile hour (`metrics.py`'s frozen definition and constant), with flow of at least 50/h. **Confirmed** when the same edge's probes also have at least one 15-minute interval below half of `v_free` in that hour (FHWA accepts 15 minutes to an hour of queue).
- **Columns apart:** highest flow in hours with a queue, confirmed or not, and in hours without one. Only queue hours measure capacity. Hours without a queue give only a lower bound.
- **Saturation flow:** loops are hourly and Berlin has no signal plans, so a loop can't measure `s` directly. For sites whose edge ends at or close to a signal: `s >= q / (g/C)` with `g/C` from Hamburg's longest-green connection per junction at that hour. This is a bound and is labelled as such.

### 3. `real_free_speed.csv`

- **Night:** 01:00-04:59. **Early:** 05:00-05:59. Also 06:00-06:59, the hour used so far.
- By OSM class and by the three classes used so far (motorway includes trunk and links; arterial primary and secondary; local the rest). Weighted by probe volume as `step6_probes.py` does, and also unweighted over edges, with `v_med` and `v_hm`.
- **Closure:** at tuning sites, loop hourly speed against the speed on the same edge in the same hour, by class and hour. Loop is a point time mean; probes are a moving-fleet sample along the edge. The ratio is the closure, and it isn't assumed to be 1.
- **The question:** does the gap with the 10% day's 68, 34, 28 km/h survive? The sim numbers are quoted, and no run is made.

### 4. `real_accumulation.csv`

- **Formula:** Little's law on links, `N(h) = sum over edges of q(e,h) L(e) / v(e,h)`, with `v` the 8-day speed for that edge and hour, class speed where the edge has no probes. Per day for the spread. Over the cut, and over the box.
- **Variants:** (a) the hand calculation with class speeds, to recheck F043; (b) edge speeds `v_med`; (c) edge speeds `v_hm`; (d) as (c), with route veh-km scaled by class and hour to real counts at tuning sites; (e) main roads only, with SVZ 2019 official veh-km and the real hourly share from counts, which uses no MATSim.
- **Labels:** route veh-km is MODELLED, speeds and counts MEASURED, the mix ESTIMATED.

### 5. `real_signals.csv`

- Hamburg `primary_signal`, weekdays and weekends apart, by local hour. Cycle as spacing of green starts per connection, 20-300 s. Green share over that cycle. Every full day on disk, deduplicated on (stream, time). Also the longest-green connection per light. `detector_car` isn't used: it holds signal requests, not counts.
- Berlin's published corridor figures from report 23 as separate rows.

### 6. Jam recovery

Space-time clusters per day: jam intervals joined when the edge is the same or adjacent and the interval the same or next, at both thresholds. Duration and size (edge-intervals) distributions, with a tail exponent by maximum likelihood. On the same 15-minute bins any later run can use.
