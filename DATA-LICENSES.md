# Data licences

The code is under the [EPL-2.0](LICENSE). Files derived from recorded traffic data keep the licence of their source, listed below. The recordings themselves are not in the repo; [research/data-inventory.md](research/data-inventory.md) and `research/truth/data-hunt/` say where they come from.

| Source | In this repo | Licence |
|---|---|---|
| NGSIM I-80, US-101, Lankershim and Peachtree (US DOT, FHWA) | per-event tables in `research/truth/courtesy/` and `research/truth/merging/`, statistics, figures, the I-80 GIF in the README | CC BY-SA 3.0 |
| DLR Urban Traffic and DLR Highway Traffic datasets (German Aerospace Center) | `research/truth/04-dlrut-discharge.csv`, `research/truth/replay/scene_dlrut_sg6.json`, `research/truth/courtesy/*_ht.csv.gz`, statistics | CC BY-NC-SA 4.0 |
| TGSIM (US DOT, FHWA) | per-event tables in `research/truth/courtesy/`, statistics | public domain |
| pNEUMA (Barmpounakis and Geroliminis, EPFL) | statistics, `research/truth/human-pneuma-proxies.npz`, figures | CC BY 4.0 |
| HIGH-SIM | statistics, plots of the public sample tracks | see the dataset's terms |
| OpenDD | per-site statistics in the junction targets | CC BY-ND 4.0 |
| SinD | statistics | CC0 1.0 |
| DRaT, Swiss roundabouts, CN+ Bremen | statistics | CC BY 4.0 |
| highD, exiD, inD, rounD (levelX) | statistics only, no recorded data | levelX research licence |
| Berlin traffic detectors (VIZ Berlin) | site-hour aggregates | Datenlizenz Deutschland – Namensnennung 2.0 |
| Hamburg traffic signals | cycle statistics | Datenlizenz Deutschland – Namensnennung 2.0 |
| Stockholm stad open data, NVDB | counts, signal positions | CC0 |
| Paris and Zurich open data | daily count aggregates | ODbL, Zurich open data terms |
| OpenStreetMap | network geometry and tags | ODbL, © OpenStreetMap contributors |
| BeST (DCAITI, TU Berlin), LuST | statistics on their networks, simulation output | see each scenario |
| Eclipse SUMO | source excerpts in `research/sumo-0*.md` | EPL-2.0 |
