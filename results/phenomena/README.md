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
| one_av | space_mean_speed_m_s | No transferable value | 7.031 | 6.911 | -0.119 |
| one_av | peak_accumulation_veh | No transferable value | 17.666 | 17.000 | -0.666 |
| one_av | peak_production_veh_m_s | No transferable value | 124.070 | 118.008 | -6.062 |
| phantom_jam | space_mean_speed_m_s | No transferable value | 8.246 | 8.184 | -0.062 |
| phantom_jam | peak_accumulation_veh | No transferable value | 14.592 | 14.000 | -0.592 |
| phantom_jam | peak_production_veh_m_s | No transferable value | 120.600 | 114.892 | -5.708 |

Published anchors and experiment specifications: [research report](../../research/validation-and-phenomena.md). Freeway ideal reference is 2400 pc/h/lane; signal ideal reference is 1900 pc/h/lane; backward waves commonly −10 to −20 km/h. None is substituted for a measurement.

Current limitations: videos show cars only, explicitly labelled; no SUMO trajectory replay. Ring wave fits, pre/post capacity drop, queue-position headways, blocked-green time, and MFD branch uncertainty are not yet implemented. one_av uses a static longer headway from time zero, not feedback control or a before/after switch. brake_wave uses a persistent bottleneck, not a pulse. Grid clearing is an outcome, not guaranteed. Thesis scenarios fail explicitly rather than silently substituting a different experiment.
