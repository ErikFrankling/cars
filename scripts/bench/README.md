# The benchmark: what "true to life" means

A simulation is true to life when one frozen configuration, with no per-scene dials, produces output that real data can't tell apart from another real day, at every scale at once, on data it never saw, through the same instrument. The spec is `research/truth/data-hunt/22-what-true-to-life-means.md`.

It reports a vector, never a total. About 70 metrics on five levels, each one simulated day against one real day, ruled by how far real data differs from itself, and each must also beat a null model. A level is as good as its worst metric. A metric without data says so and is never a pass.

## One command

Run from any directory other than a data folder, in the dev environment:

```sh
source /home/erikf/projects/personal/cars-data/dev-env.sh
B=scripts/bench/bench.py
scripts/bench/build_driver.sh human       # pins the driver to its branch head, plus the instrument patch
python3 -I $B selftest                    # no simulator: corruptions of real days, must keep passing
python3 -I $B run --driver human --mode fast     # one seed, small scenes
python3 -I $B run --driver human --mode full     # six seeds, longer scenes, drift and capacity drop
python3 -I $B run --driver human --mode fast --gpu --berlin-factor 10   # adds the Berlin district, whole demand
python3 -I $B run --driver human --mode fast --reuse RUN --berlin-runs NAME   # scores an existing district run
python3 -I $B compare RUN_A RUN_B          # per metric: better, worse, same, with paired intervals
python3 -I $B knownbad                     # the 20 known-bad configurations, on the simulator
python3 -I $B history
python3 -I $B dashboard                    # /home/erikf/projects/personal/cars-data/report/bench/
```

Drivers are `configs/*.toml`: `main` (today's main, the physical driver), `sumo` (main with `--sumo-compat`, the old driver), `physics` (`t3/1c6fee50`), `human` (`t3/1b36c9cf`). `CARS_ADAPTER=llvmpipe` is the default so runs don't touch the desktop GPU; `--gpu` goes through `flock /tmp/cars-gpu.lock`. Long runs on the homelab: `scripts/bench/homelab.sh human full`, which goes through `heavy --big -- scripts/d8/worker.sh`.

## Layout

| Path | What |
|---|---|
| `bench.py` | The command line |
| `registry.toml` | Every metric: level, tag P/W/D, gate check, plain words. Committed before the first simulated score |
| `configs/` | One configuration per driver. Its hash is on every result |
| `scenes.py` | Test scenes. A scene with a driver number in it is refused (`check_clean`). The chain rig's head and followers are the one marked exception |
| `instrument/` | The `--sensors` point detector, as a patch per driver. Part of the benchmark, not the simulator. From the Berlin build |
| `metrics/extract.py` | The drone view: 1 s differences, centre spacing, lane logic, queue positions, as report 05 does on real tracks |
| `metrics/levels.py` | Levels 0 to 3, one function per metric |
| `metrics/trackio.py`, `metrics/junction25.py` | Adapter from simulator output to plain tracks, and level 2 against report 25, using its own `scripts/junction_targets/` code on simulated tracks. `floors/junction_targets.csv` holds its tuning rows only, so held-out sites can't be read |
| `network.py`, `berlin.py` | Level 4, one function for real and simulated days. `read_sensors` is the virtual detector |
| `floors.py`, `floors/` | Real against real. `selftest`, tick floors per tracker and block, signal targets, real leaders |
| `score.py` | Statuses of report 22 section 6, skill rule, paired comparison |
| `suite.py` | Runs the scenes and assembles one result |
| `knownbad.py`, `power.md` | Report 22 section 12, and which metric caught what |
| `reveal.py`, `splits/`, `ledger.tsv` | Locked data, approvals, the ledger |
| `dashboard.py` | The static page |

Results live in `/home/erikf/projects/personal/cars-data/bench/`: `results/<run>.json` per run, `history.jsonl` append-only with each line chained to the hash of the one before, `knownbad.json`. Each result has commit, binary hash, configuration hash, instrument patch, seeds, and per metric cell the gap `S`, ruler `F`, null `N`, `D(i, j)` and status. Baselines are copied to `results/true-to-life/` in this repo.

## How a metric is scored

`D(i, j)` is replicate `i` against real day or block `j`, never a seed average. `S` is its median, `F` the 97th percentile of real against real on the same sites and hours.

| Status | Means |
|---|---|
| `FLOOR` | `S <= F`, upper bound under 1.25 F, p90 under 1.5 F: as close as one real day is to another |
| `NEAR` | `S <= 1.25 F`: what an odd real day does |
| `CREDIBLE` | Above that, but within its credible limit and closing half the gap from the null to real noise |
| `INCONCLUSIVE` | Median inside, bound or spread outside. Not a pass |
| `THIN` | Would be `FLOOR`, with fewer than 8 real days or blocks or a soft floor. Not a pass |
| `NO DATA` | No real data, or no scene for it yet. Not a pass, ever |
| `INVALID` | The benchmark can't judge it |
| `FAIL` | Otherwise, and whenever it does no better than the null |

Null models. Level 4: class mean profile as report 22 section 5; where that knows the answer by construction, something that knows less: a flat day 50% too high for total and day shape, free flow all day for class speeds. Levels 1 to 3: a driver with nothing in it, such as no acceleration, no lane changes, instant starts, a 1 s headway. Level 0 has none, by nature.

A metric given as a real band (M4, JS1 to JS6, JR, C3, C4) is scored as distance from the band's middle, ruled by half its width, so inside the band is `FLOOR`. `z` is `S / F`. Compare: `D` is paired by seed and day, with report 22's margin; `better`, `same`, `worse` per cell, then BETTER, SAME, WORSE or TRADE-OFF overall.

## Held-out data

`splits/locked.toml` lists the locked sets. Nothing there is downloaded before use. The bench reads only Berlin's tuning sites, using the one list frozen by report 23 (`splits/locked_sites.txt`), and all 8 May days. An earlier dry run of the selftest and a wire test used a different hash and so read some of those sites in aggregate; no site-level number was looked at and no simulated score came from it.

**15 May 2019 is not blind.** Report 12 read it while proposing it as the gate day, so it's tuning data like the other 7 days, and every score uses all 8 days. The blind tests are the unopened months.

A reveal needs a written reason and an approval only Erik can give: `bench.py approve --locked SET --reason "..."` refuses without a real terminal or inside an agent session, and needs the set's name typed back. `bench.py reveal` then appends to `ledger.tsv` and prints only each level's status and z rounded to 0.25. At most 5 per set, then the set is spent and a new month opens. That is discipline, not cryptography: an agent could forge the file, and that's a rule broken in plain sight rather than a thing prevented.

## For the GUI

`/bench/trust.json` next to the dashboard gives, per driver, the latest run's status per level and gate check. `crates/cars-gui/registry.toml`'s trust labels can read it. `matches_real_day` stays false until every gate check passes on held-out data.

## State of the first baselines

Copies are in `results/true-to-life/`. Fast mode, one seed, pinned to main d4a92cb9, physics 883f923c, human f69d6947. All 20 known-bad configurations are caught, by at least one named metric each (`power.md`). `selftest` passes.

Not done yet:

- **Full mode has not been run to the end on any driver**, so `M14` drift and `JO3` capacity drop have no score, and with one seed `U` and `S90` have no spread between seeds.
- **Berlin district is scored on main only, at 10% of demand with flows multiplied up**, which `V8` fails by design. It reproduces report 23's WAPE and RMSN. Physics and human runs were stopped at about 30%. No 100% day exists.
- `reveal` has no scorer: it refuses without spending anything. No locked set has been opened.
- Known-bad cases 1 to 5 and 12 to 20 ran before the last metric additions and the switch to one locked site list. Cases 6 to 11 ran after the additions, before the switch. Their named metrics did not change.
- Some named metrics stay quiet: M12 on case 4, M9 on case 6, V2 on case 8, JS1 on case 9, N14 and V6 on case 12, N4 on case 13, N10 on case 18.

## Known limits

- Test scenes are generic geometry with real rates and real signal timings, not rebuilt places. A pass at level 2 on them is weaker than on a rebuilt junction.
- `dt` is 0.1 at levels 1 to 3 and 1 s on the district, because a day at 0.1 is too slow today. That is one setting differing by scale, recorded in the config and tested by `V5`, `JS2` and `C3` at both steps.
- `NO DATA` lists its reason in each cell. The biggest holes: right-before-left, off-ramps and weaves without a scene, travel times until Cambridge has a scene and its other seven days, replay `M5`, which needs a kernel only one driver has.
- `mini_day` feeds real site flows to separate roads. It lets demand-side known-bad cases run in minutes, and because its demand comes from the data that scores it, it's labelled an engine test and is never in a driver's scorecard.
