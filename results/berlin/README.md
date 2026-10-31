# Berlin detector comparison

Re-run (paths may be replaced):

```sh
nix develop --command python3 -I scripts/berlin_detectors.py map
nix develop --command python3 -I scripts/berlin_detectors.py profile
nix develop --command python3 -I scripts/berlin_detectors.py compare --cars /home/erikf/.t3/projects/cars/runs/berlin/day_edges.csv --sumo /home/erikf/projects/personal/cars-data/best/out/edge900.xml
```

## Method and coverage

Metadata: actual workbook has one lane table with WGS84 coordinates, old detector names and eight compass directions (not the GK4 sheets described in the inventory). Transform using network projParameter and netOffset. External passenger-compatible edges only; closest polyline segment bearing. Score = distance metres + 0.5 × bearing error degrees + 20 × lane-count mismatch. Accept distance ≤40 m, bearing error ≤45°, exact passenger lane count and runner-up score margin ≥10. Reject repeated accepted edge assignments. Automated matches have not had manual bridge/parallel-road review.

292 cross-sections considered; 155 accepted; 137 rejected. Profile retains 103 sites / 2399 site-hours. Daily total uses 93 sites with all 24 real hours, held fixed for all curves. This is a sum of detector passages, not unique city trips or all Berlin traffic.

September 2024 is the only locally downloaded month, selected as a recent ordinary working-month baseline, not a reconstruction of the scenario's original year. Monday–Friday; Berlin summer break ended August 30 and autumn break begins October 21; no September Berlin public holidays. Provider docs contain no calendar exclusion mechanism; calendar basis: https://www.berlin.de/sen/bjf/service/kalender/ferien/ . No incident/weather filtering. At least five complete dates per site-hour. Every metadata lane must have finite nonnegative qkfz, completeness ≥75 (archive units are percent), hist_cor ≥0.5. Hist_cor cutoff is our moderate positive-correlation heuristic, not a provider recommendation; it may preferentially retain typical traffic. Z-scores are not thresholded because documented rejection cutoffs are absent. Sum lanes on each common date before averaging dates. Missing lanes never become zero observations. Profile standard deviation and sample days are supplied.

Counts are all motor vehicles. Simulation entered counts are at upstream edge boundaries, not physical detector crossings; travel delay, mid-edge departures and queues cause differences. Sparse simulator edge omissions within a complete interval mean zero. Cars CSV is assumed to contain complete hourly intervals; it has no end marker. SUMO accepts only closed 900-second intervals and four quarters per hour, discarding truncated tails and incomplete hours, without extrapolation. Clock assumes simulation zero is local midnight. SUMO missing hours remain missing. Current cars input is an intermediate engine build and must be rerun later. No GPU was used.

## Independence and limitations

[BeST upstream documentation](https://github.com/mosaic-addons/best-scenario) states demand was extracted from MATSim Open Berlin and routes re-calibrated to user equilibrium. It also compares selected street counts against Digitale Plattform Berlin, the same provider as this archive. It does not establish which detector-years were used or that this September 2024 sample was held out. Thus a good fit is an external temporal consistency check, **not proven independent validation**. Demand year, fleet mix, bus support, road changes since metadata (2022), direction quantization and automatic matching all limit conclusions. No calibration was done here. Six examples span observed daily-volume quantiles; they are not selected by fit. SUMO coverage differs from the full-day cars run; compare common hours for simulator ranking.

Real data attribution: Digitale Plattform Stadtverkehr Berlin / Verkehrsdetektion Berlin, Datenlizenz Deutschland – Namensnennung 2.0. BeST: Schrab, Protzmann, Radusch (2023), CC BY 4.0.

## Results

R² = 1 − SSE/SST (may be negative); slope is least squares through origin, simulated on real. GEH = sqrt(2(S−O)²/(S+O)); both zero →0. Shares weight site-hours equally; no acceptance target is asserted.

|Simulator|Hour|Sites|GEH <5 share|R²|Slope|
|---|---:|---:|---:|---:|---:|
|cars|0|100|0.050|-0.258|0.004|
|cars|1|100|0.080|-0.150|0.005|
|cars|2|100|0.150|-2.088|0.053|
|cars|3|101|0.158|-0.203|0.022|
|cars|4|100|0.170|-0.383|0.057|
|cars|5|101|0.188|-0.231|0.342|
|cars|6|100|0.180|-0.135|0.488|
|cars|7|98|0.153|-0.594|0.469|
|cars|8|99|0.111|-0.754|0.477|
|cars|9|100|0.120|-0.620|0.537|
|cars|10|100|0.170|-0.458|0.545|
|cars|11|99|0.202|-0.474|0.467|
|cars|12|98|0.143|-0.694|0.408|
|cars|13|100|0.080|-1.003|0.348|
|cars|14|100|0.080|-1.340|0.291|
|cars|15|100|0.030|-1.673|0.233|
|cars|16|100|0.040|-1.946|0.204|
|cars|17|100|0.070|-2.127|0.191|
|cars|18|100|0.050|-2.184|0.181|
|cars|19|100|0.040|-1.652|0.193|
|cars|20|101|0.059|-1.063|0.196|
|cars|21|100|0.130|-0.672|0.216|
|cars|22|101|0.208|-0.356|0.225|
|cars|23|101|0.287|-0.161|0.259|
|SUMO|5|101|0.198|-0.274|0.326|
|SUMO|6|100|0.180|-0.136|0.487|
|SUMO|7|98|0.153|-0.595|0.470|
|SUMO|8|99|0.111|-0.753|0.476|

cars: pooled GEH<5 12.3%; simulated/real total 0.386, over 2399 site-hours.

SUMO: pooled GEH<5 16.1%; simulated/real total 0.492, over 398 site-hours.

## Quality cutoff sensitivity

Coverage only (changing populations, not paired fit):

```csv
hist_cor,sites,site_hours,mean_real
0.0,109,2509,498.9893072937425
0.5,103,2399,504.8782200917049
0.8,77,1658,486.95824065138726
```
Repeat profile with --hist-cor 0, 0.5 and 0.8 in separate --out directories containing detector_map.csv. Means are unweighted over retained site-hours, not a paired volume comparison.

Verification: synthetic XML checks passed for four-quarter aggregation, sparse zero edges, truncated final interval discard and zero/zero GEH. Representative-series and residual-map PNGs were visually inspected. CSVs are below 3 MB each.
