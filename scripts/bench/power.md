# Power of the benchmark

Written by `bench.py knownbad`. Each row is a configuration known to be wrong, run on the simulator. Baseline: the human driver.

| # | Configuration | Driver | Caught | By |
|---:|---|---|---|---|
| 1 | Krauss SUMO defaults, dt 0.1 | main | yes | JS2 z 2.27585 (baseline FAIL 1.87993), C3 z 1.96986 (baseline FAIL 3.17213) |
| 2 | Krauss defaults, dt 1 | main | yes | M6 z 1.40102 (baseline FLOOR 0.79199), V5 z 4.69031 (baseline FAIL 2.36451) |
| 3 | Calibrated IDM | main | yes | JS1 z 8.58558 (baseline FAIL 3.71805), M6 z 3.06521 (baseline FLOOR 0.79199) |
| 4 | Calibrated Krauss, decel 0.33 | main | yes | JS6 z 11.11111 (baseline FLOOR 0.54973), JS1 z 8.1389 (baseline FAIL 3.71805); did not fire: M12 FLOOR z 0.0 |
| 5 | Instant lane changes | main | yes | M7 z 13.5 (baseline FAIL 2.15429) |
| 6 | SUMO secure gap test | main | yes | M8 z 2.5 (baseline FAIL 13.96974); did not fire: M9 FAIL z 1.25489 |
| 7 | Lane changing off | human | yes | M8 z 6.5 (baseline FAIL 13.96974) |
| 8 | Acceleration noise 0.53 m/s2 | human53 | yes | M3 z 4.24954 (baseline FAIL 4.5903); did not fire: V2 FLOOR z 0.0 |
| 9 | Car length 3 m, demand raised to match flow | main | yes | M4 z 2.17518 (baseline FLOOR 0.17776); did not fire: JS1 FAIL z 8.11217 |
| 10 | Reaction time cut 30%, demand raised to match flow | main | yes | M3 z 15.06277 (baseline FAIL 9.9211), JS2 z 3.91183 (baseline FAIL 2.27585), C3 z 6.70258 (baseline FAIL 1.96986) |
| 11 | Demand x0.6 | main (engine test) | yes | N1 z 7.96264 (baseline FLOOR 0.25725), N5 z 3.52957 (baseline FLOOR 0.47533), V8 z 999.0 (baseline None None) |
| 12 | Demand x1.2 | main (engine test) | yes | N1 z 4.12124 (baseline FLOOR 0.25725); did not fire: N14 FAIL z 10.38613, V6 None z None |
| 13 | Demand clock +1 h | main (engine test) | yes | N3 z 5.22811 (baseline FLOOR 0.50424); did not fire: N4 INCONCLUSIVE z 1.0 |
| 14 | Flat departure curve | main (engine test) | yes | N3 z 4.03628 (baseline FLOOR 0.50424), N9 z 2.53191 (baseline FLOOR 0.56038) |
| 15 | Fixed 90 s signals, offset 0 | human | yes | JS7 z 2.83437 (baseline FAIL 1.63293) |
| 16 | Signals removed | human | yes | JS7 z 2.73325 (baseline FAIL 1.63293) |
| 17 | Teleports on at 120 s | human | yes | V1 z 999.0 (baseline FLOOR 0.0) |
| 18 | Free-flow-only routes | main (engine test) | yes | N8 z 18.824 (baseline FLOOR 0.42301); did not fire: N10 NEAR z 1.19275 |
| 19 | Desired speed x1.3 | main (engine test) | yes | N12 z 17.76238 (baseline FAIL 4.4984) |
| 20 | Replay real schedules | - | yes | refused by bench |

Metrics that caught at least one: C3, JS1, JS2, JS6, JS7, M3, M4, M6, M7, M8, N1, N12, N3, N5, N8, N9, V1, V5, V8.
