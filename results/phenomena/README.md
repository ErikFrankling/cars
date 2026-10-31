# Traffic phenomena measurements

One seed (42), dt 0.1 s, Krauss sigma 0.5, speedDev 0. Same explicit departures and vTypes in both engines. Teleportation disabled. No confidence intervals or equivalence claim.

Flow = distance / (30 s × lane length); density = vehicle seconds / (30 s × lane length). Production includes external edges only. Speed is distance / vehicle seconds. Empty edges remain in network denominators. These are interval Edie measurements, not stop-line detector discharge.

| Scenario | Metric | Literature | SUMO | cars | cars − SUMO |
|---|---|---|---:|---:|---:|
| brake_wave | space_mean_speed_m_s | No transferable value | 11.241 | 11.186 | -0.056 |
| brake_wave | peak_accumulation_veh | No transferable value | 235.420 | 234.700 | -0.720 |
| brake_wave | peak_production_veh_m_s | No transferable value | 2254.042 | 2237.342 | -16.700 |
| capacity_drop | space_mean_speed_m_s | No transferable value | 32.763 | 32.692 | -0.071 |
| capacity_drop | peak_accumulation_veh | No transferable value | 161.636 | 161.500 | -0.136 |
| capacity_drop | peak_production_veh_m_s | No transferable value | 4887.773 | 4870.521 | -17.252 |
| freeway_fd | space_mean_speed_m_s | No transferable value | 33.265 | 33.202 | -0.063 |
| freeway_fd | peak_accumulation_veh | No transferable value | 108.595 | 108.400 | -0.195 |
| freeway_fd | peak_production_veh_m_s | No transferable value | 3612.945 | 3599.229 | -13.715 |
| gridlock | space_mean_speed_m_s | No transferable value | 7.594 | 7.503 | -0.091 |
| gridlock | peak_accumulation_veh | No transferable value | 696.291 | 681.400 | -14.891 |
| gridlock | peak_production_veh_m_s | No transferable value | 5769.044 | 5508.471 | -260.574 |
| mfd | space_mean_speed_m_s | No transferable value | 7.605 | 7.516 | -0.089 |
| mfd | peak_accumulation_veh | No transferable value | 696.344 | 681.500 | -14.844 |
| mfd | peak_production_veh_m_s | No transferable value | 5765.923 | 5521.212 | -244.711 |
| one_av | space_mean_speed_m_s | No transferable value | 4.014 | 3.949 | -0.065 |
| one_av | peak_accumulation_veh | No transferable value | 22.872 | 22.000 | -0.872 |
| one_av | peak_production_veh_m_s | No transferable value | 91.944 | 87.029 | -4.915 |
| onramp_merge | space_mean_speed_m_s | No transferable value | 19.812 | 19.765 | -0.046 |
| onramp_merge | peak_accumulation_veh | No transferable value | 242.507 | 242.400 | -0.107 |
| onramp_merge | peak_production_veh_m_s | No transferable value | 5271.932 | 5257.600 | -14.332 |
| phantom_jam | space_mean_speed_m_s | No transferable value | 2.867 | 2.800 | -0.067 |
| phantom_jam | peak_accumulation_veh | No transferable value | 22.946 | 22.000 | -0.946 |
| phantom_jam | peak_production_veh_m_s | No transferable value | 65.854 | 61.792 | -4.062 |
| signal_discharge | space_mean_speed_m_s | No transferable value | 7.358 | 7.411 | +0.052 |
| signal_discharge | peak_accumulation_veh | No transferable value | 39.867 | 39.300 | -0.567 |
| signal_discharge | peak_production_veh_m_s | No transferable value | 339.779 | 321.337 | -18.442 |
| spillback | space_mean_speed_m_s | No transferable value | 2.068 | 2.327 | +0.259 |
| spillback | peak_accumulation_veh | No transferable value | 77.003 | 74.433 | -2.570 |
| spillback | peak_production_veh_m_s | No transferable value | 260.464 | 276.329 | +15.865 |

Important: SUMO edge sampledSeconds can include vehicles overlapping edge boundaries; edge-based accumulation is a proxy and can exceed the physical count. Ring trajectory CSVs count front positions explicitly. Do not interpret the difference as lost vehicles without checking insertion and arrival logs.

Published anchors and experiment specifications: [research report](../../research/validation-and-phenomena.md). Freeway ideal reference is 2400 pc/h/lane; signal ideal reference is 1900 pc/h/lane; backward waves commonly −10 to −20 km/h. None is substituted for a measurement.

Current limitations: videos show cars only, explicitly labelled; no SUMO trajectory replay. Ring wave fits, pre/post capacity drop, queue-position headways, blocked-green time, and MFD branch uncertainty are not yet implemented. one_av uses a static longer headway from time zero, not feedback control or a before/after switch. brake_wave uses a persistent bottleneck, not a pulse. Grid clearing is an outcome, not guaranteed. Thesis scenarios fail explicitly rather than silently substituting a different experiment.

GPU diagnostics (nonzero overflow requires investigation; results are provisional):

| Scenario | Overflow counter | Collisions | Teleports |
|---|---:|---:|---:|
| brake_wave | 0 | 0 | 0 |
| capacity_drop | 0 | 0 | 0 |
| freeway_fd | 0 | 0 | 0 |
| gridlock | 2379173 | 0 | 0 |
| mfd | 4782716 | 0 | 0 |
| one_av | 0 | 0 | 0 |
| onramp_merge | 320659 | 0 | 0 |
| phantom_jam | 0 | 0 | 0 |
| signal_discharge | 0 | 0 | 0 |
| spillback | 0 | 0 | 0 |

Video status: phantom_jam.mp4 completed at 1920×1080, 30 fps, 40 seconds; inspected frame shows visible cars and readable captions, but no clear jam. one_av recording failed because lag-guard killed ffmpeg during desktop memory/disk pressure; further local recordings stopped. No completed side-by-side SUMO videos.
