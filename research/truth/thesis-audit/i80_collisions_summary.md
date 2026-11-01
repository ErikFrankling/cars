# I-80 collision records, thesis configuration

SUMO 1.26, `dt` 1 s, 100% share, seed 0, with `--collision-output`. A separate run from `sumo_ledger.csv`, without the edge output, which is why the counts differ slightly from that file (31,613 against 32,899 for CACC).

| | CACC | Krauss |
|---|---:|---:|
| Collision events | 31,613 | 3,773 |
| Threshold | gap < 0.1 m (factor 0.1 × minGap 1.0) | gap < 1.5 m (factor 1.0 × minGap 1.5) |
| Vehicles involved as collider | 11,260 (46% of 24,242) | 3,773 (16%) |
| Most for one vehicle | 10 | 1 |
| Collider speed, p50 and p95 | 8.0, 15.2 m/s | 1.5, 11.5 m/s |
| Closing speed, p50 and p95 | 6.6, 11.2 m/s | 1.45, 3.6 m/s |
| Share closing above 3 m/s | 91% | 9% |
| Types | 30,883 collision, 712 junction, 16 side | 3,772 collision, 1 junction |
| Most-hit lanes | `edge_up_78_2` 3,708; `edge_down_78_2` 2,472; `edge_up_75_2` 2,241 | `edge_merge_72_0` 1,174; `edge_merge_78_0` 1,117; `edge_merge1_75_0` 658 |
| By simulated hour | 1: 2,449; 2: 22,873; 3: 6,289 | not tabulated |

Thresholds: `MSCFModel_CACC.cpp:101`, `MSCFModel.cpp:62`, `MSLane.cpp:1998` in the SUMO source.
