# 12. V2X messages, roadside units, capacity and energy

Research date: 2026-11-01. Fills the gap report [08](08-v2x-and-safety-first-principles.md) left open: it could not open J2735, J3224 or TS 103 300-3, and it never quantified security overhead or sub-channel granularity. No GPU was used and no production code was changed.

**Grades.** **FIELD** measured on real equipment. **LAB** cabled or bench. **SIM** simulated. **SPEC** specified, untested by that document. **PRESS** manufacturer or vendor statement with no method. **DERIVED** calculated here. **PROPOSED** a design choice here. **UNVERIFIED** could not be substantiated from text opened in this session.

**Reproduce.** [`scripts/v2x_msgsizes.py`](scripts/v2x_msgsizes.py) encodes messages with the ASN.1 ETSI publishes and writes [`v2x-msg-sizes.json`](v2x-msg-sizes.json). [`scripts/v2x_density.py`](scripts/v2x_density.py) measures the Stockholm and Berlin nets and writes [`v2x-density.jsonl`](v2x-density.jsonl). [`scripts/v2x_capacity.py`](scripts/v2x_capacity.py) writes [`v2x-capacity.json`](v2x-capacity.json). Fetches are logged in [`v2x-fetch-ledger.jsonl`](v2x-fetch-ledger.jsonl). Downloads are in `/home/erikf/projects/personal/cars-data/truth/v2x/`. Paywalled SAE and ISO standards were not read, only their abstracts and what public documents say about them.

## 1. The short answer

**Is it legitimate to broadcast intended trajectories?** Yes, today, under a published standard. [TS 103 900 V2.3.1 (May 2026)][cam2] adds a Path Prediction container to the CAM, and the data dictionary says its points form a "trajectory" when `pathDeltaTime` is present ([CDD ASN.1][cdd]). ETSI's own report says reference trajectories can go out in CAM version 2 ([TR 103 578, note in 5.2][tr578]). Report 08's "MCM is a draft" remains true, and it blocks negotiation, not intent.

**Can every car broadcast full intent in dense city traffic?** Not at 10 Hz. Yes at about 1 Hz, if the radio range is also cut.

| | Cars in range | Air load wanted | What 20 MHz carries | What 40 MHz carries |
|---|---:|---:|---:|---:|
| 10 Hz, 16-point intent, busy street | 1,000 | 24.2 Mbit/s | 3.2 Mbit/s | 6.3 Mbit/s |
| Same, full jam | 3,000 | 72.7 Mbit/s | 3.2 Mbit/s | 6.3 Mbit/s |
| 1 Hz intent, busy street | 1,000 | 3.5 Mbit/s | fits, 1.3 Hz available | fits, 2.6 Hz available |

DERIVED. NR sidelink, 16QAM, one retransmission, CBR up to 0.65. This setting has no NR field measurement behind it. The 3.2 and 6.3 Mbit/s are for 303 B messages. Certificates at 1 Hz still fit because they stay within the same two sub-channels, which is why the last row works. See §6.

**Top findings.**

1. **A status message costs nearly five times its content.** A CAM is 41 B of UPER. Signature, network and link headers add 151 B, and a certificate adds 139 B more once a second. A CAM with a 16-point trajectory is 303 B on air, or 442 B with a certificate. DERIVED from the published ASN.1.
2. **Today's fielded limit is very low.** Qualcomm's 20 MHz field study let cars back off until CBR held near 24%, which is 1.5 Mbit/s of net payload. At 1,000 cars in range that allows 0.33 Hz with intent. FIELD, vendor, plus DERIVED.
3. **Density is what bites.** In Stockholm and Berlin, a 500 m disc holds a p95 of about 20 to 23 lane-km. That is 450 cars at 20 per lane-km and 3,000 in a Stockholm jam, all of them in one contention domain unless power is reduced. DERIVED from the nets.
4. **Real signal-information savings are small at trip level.** Berkeley Lab's field evaluation found 10% to 20% per affected signal event, applicable to about 15% of arrivals, and under about 1% of fuel on an average trip. Ottawa measured 5% across a 7-vehicle fleet with OBD logging. A Dutch controlled pilot found no significant flow change. Test-road figures reach 22% to 38%.
5. **Nothing here supports coordinated crossing as a deployed standard.** [TR 103 578][tr578] describes the concept, and the MCM specification has sat at draft 0.0.10 since February 2025 ([ETSI][mcmwi]). SAE J3186 is published but V2V only (per [TR 103 578 A.6][tr578]). Coordinated crossing in the simulator is a proposal, mapped onto SREM and SSEM with stated departures.

**Message set chosen.** CAM with Path Prediction for cars, SPATEM and MAPEM from roadside units, SREM and SSEM repurposed for crossing slots, CPM from roadside units for unequipped cars, DENM for hazards. §8 gives fields and bytes.

**2035 assumption.** About 20 MHz of NR sidelink for automated driving at CBR up to 0.65, with transmit power control, status by the CAM dynamics rule, and intent near 1 Hz. Maps and slow data go over cellular. Uu multicast with edge aggregation as a separate tested option. Do not assume 10 Hz all-to-all, 40 points, single-digit-millisecond latency or 99.999% reliability. §6.6.

## 2. The real stacks and messages

### 2.1 Layers and bytes

**SPEC and DERIVED.** Message bytes come from encoding with [asn1tools](https://pypi.org/project/asn1tools/) against the [ETSI forge ASN.1][forge]. UPER size depends on which optional fields are present and list lengths, so these sizes are exact for the stated options. Two cross-checks: my CPM object is 34 B against 35 B in [TR 103 562 Table 3][tr562], and Qualcomm's test uses a 365 to 383 B secured BSM ([Qualcomm 8.2][qc]), the same order as my 331 B CAM with certificate.

| Layer | Bytes | Source and grade |
|---|---:|---|
| Facilities message | see §2.2 | ETSI ASN.1, DERIVED |
| Signed data, certificate digest as signer | 95 | §2.8, DERIVED by field |
| Extra when the certificate is attached | 139 | §2.8, DERIVED |
| GeoNetworking single-hop header | 40 | Basic 4, Common 8, position vector 24, media-dependent 4: [EN 302 636-4-1 Table 13][gn] |
| BTP-B | 4 | **UNVERIFIED**, the BTP spec was not opened. Assumed |
| Sidelink layer 2 and CRC | 12 | PROPOSED estimate. [TS 38.321][ts38321] confirms an SL-SCH subheader and per-SDU subheaders; I did not total them from the spec |

The US stack has no GeoNetworking, so its overhead is smaller. I could not open IEEE 1609.3 to quantify that.

### 2.2 ETSI message set, encoded

| Message | Standard, status | Rate rule | Encoded UPER bytes |
|---|---|---|---|
| CAM, status | [TS 103 900 V2.3.1, 2026-05][cam2]. Older [EN 302 637-2][cam1] | 1 to 10 Hz by dynamics, §2.3 | **41** high-frequency only |
| CAM low-frequency | Same | At least 500 ms apart | Whole CAM 43 with no path history, then 76 (5 pts), 108 (10), 193 (23), 303 (40) |
| CAM Path Prediction | Same, extension container | Recommended 950 ms, sooner if significant | 40 (5 pts), 72 (10), **111 (16)**, 204 (30), 269 (40). 62, 117, 184 with position confidence on each point |
| DENM | [TS 103 831 V2.3.1, 2025-11][denm2] | Event, with repetition | 43 |
| CPM | [TS 103 324 V2.1.1, 2023-06][cpm] | 100 to 1000 ms | About 36 plus **34 per object** with kinematics, size and class. 319 B for 10 objects, 635 B for 20 |
| VAM | [TS 103 300-3 V2.3.1, 2025-12][vam] | 100 to 5000 ms | 34, mandatory only |
| SPATEM | [TS 103 301 V2.3.1, 2026-04][is] | No fixed rate, §2.5 | 62 (4 groups), 102 (8), **183 (16)**, 345 (32), with min, max, likely, confidence |
| MAPEM | Same | Repeated | 227 (8 lanes), 364 (12), **519 (16)**, 840 (24), 1,311 (32). Smallest node offsets, so a floor |
| SREM | Same | On need, may repeat | 30, one request |
| SSEM | Same | On request or change | 29, one status. 138, eight |
| IVIM | Same | Repeated | Not encoded. Content varies too much for one number |

**Parking.** I searched for "CAPIM" and found nothing. It appears in none of the ETSI ASN.1 modules I fetched, nor in the specs I searched. ETSI has a Parking Availability service ([TS 103 916][ts916]) and Cooperative Parking TS 104 072 ([forge][forge]). Not relevant to flows. Treat CAPIM as **UNVERIFIED**.

### 2.3 CAM in detail

**SPEC,** [TS 103 900 6.1.2][cam2].

- Generation interval between 100 ms and 1000 ms.
- A CAM is triggered when at least `T_GenCam_Dcc` has elapsed and heading changed over 4°, position over 4 m, or speed over 0.5 m/s. Otherwise after `T_GenCam`, up to 1 s. After a dynamics trigger, the interval is kept for `N_GenCam`, default and maximum 3, messages.
- Single hop, never forwarded.
- Generation under 50 ms.
- A roadside unit's CAMs must be at least 500 ms apart ([6.1.3][cam2]).

**This rule has a large consequence.** Rate rises with speed as `v/4` Hz, and a stopped car sends at 1 Hz. So a queue, where density is worst, is automatically at the lowest rate. DERIVED: 50 km/h gives 3.5 Hz, 10 Hz needs 144 km/h or fast manoeuvring. Applying the triggers (without heading, which is not in the file) to recorded FCD at dt = 0.1 s on the `signal` fixture gives **2.2 Hz per vehicle**. The `stockholm-window` and `berlin-window` runs use dt = 1 s and cannot exceed about 1 Hz, so they give no valid rate.

Mandatory fields in the high-frequency container, from [CAM ASN.1][camasn]: `heading`, `speed`, `driveDirection`, `vehicleLength`, `vehicleWidth`, `longitudinalAcceleration`, `curvature`, `curvatureCalculationMode`, `yawRate`. Optional include `accelerationControl`, `lanePosition`, `steeringWheelAngle`, `lateralAcceleration`, `verticalAcceleration`. The basic container has station type and reference position.

**Braking capability is not in the message.** [AV-REQUIREMENTS](AV-REQUIREMENTS.md) asks cars to broadcast it. The [CDD][cdd] has brake status and engagement flags (`AccelerationControl`, `BrakeControl`), but I found no field for capability. It is a departure, §8.2.

### 2.4 Which messages carry intended future trajectories

| Message | Carries future motion? | Status | Evidence |
|---|---|---|---|
| ETSI CAM Path Prediction | **Yes.** Up to 16 points, extensible to 40. Time on each point makes it a trajectory, with `usageIndication` including `adasAd` and a `confidenceLevel` | **Published**, optional | [TS 103 900][cam2], [CDD][cdd] |
| ETSI MCM | Yes. Reference, alternative and request trajectories, horizon about 30 s in the joint proposal, plus cost values | **Draft.** TS 103 561 stable draft 0.0.10, 2025-02-17. A deliver path for it returned 404 | [Work item][mcmwi], [TR 103 578 A.2][tr578] |
| SAE J3186 MSCS | Yes. Target road resource as box or trajectory, with sub-manoeuvres | **Issued March 2023.** Paywalled, V2V only per ETSI | [SAE abstract][j3186], [TR 103 578 A.6][tr578] |
| SAE J2735 BSM Part II | Partly. Path Prediction is a circle of radius R, a first-order curvature estimate, not a timed trajectory | Published, paywalled | [NHTSA NPRM description][nprm] |
| China VIR | Listed in Phase II sets. Whether it has a planned path is **UNVERIFIED** | Standard not opened | [ITU slides][itu] |
| CPM, SDSM | No. Perceived objects now | Published | [TS 103 324][cpm], [SAE J3224][j3224] |
| SPATEM | Signal's future, not a vehicle's | Published | [TS 103 301][is] |

### 2.5 Traffic light messages

**SPEC.** [TS 103 301][is] defines SPATEM (signal state and timing), MAPEM (lane topology), SREM and SSEM (priority request and status), IVIM and RTCMEM, built on the DSRC module derived from ISO TS 19091 ([forge][forge]). I did not read ISO 19091 itself.

- **Default range:** 400 m radius, with latency under 100 ms ([Table 4][is]).
- **Rate:** the SPATEM profile shows `CSP_AvgADUrate` "255, 1 second (default)" and says the service does not repeat. So ETSI does not fix a rate. The application pushes messages. Field systems do differ: University of Michigan's deployment logs SPaT and BSM at 10 Hz ([UMich][umich]). A US fact sheet with the same claim would not open (403).
- **SPATEM fields** ([DSRC ASN.1][dsrc]): `id`, `revision`, `status`, `moy`, `timeStamp`, `states[signalGroup, state-time-speed[eventState, timing{startTime, minEndTime, maxEndTime, likelyTime, confidence, nextTime}, speeds]]`. `TimeMark` runs 0 to 36001. `speeds` is an advisory speed list, so GLOSA can be broadcast directly.
- **Actuated signals are the real problem.** A green with a measured mean of 40.55 s has σ = 14.78 s in LBNL's adaptive signal ([LBNL][lbnl]). Dutch field data show most non-yellow predictions were 40% to 80% reliable, and that fully vehicle-actuated control gave no stable predictions until the control was partly fixed ([Noord-Holland][nh]). FIELD.
- **SREM fields:** `requests[request{id, requestID, requestType, inBoundLane, outBoundLane}, minute, second, duration]`, `requestor`. **SSEM fields:** `sigStatus[requester, inboundOn, outboundOn, minute, second, duration, status]`, with status values including `granted`, `rejected`, `watchOtherTraffic` ([DSRC ASN.1][dsrc]).

### 2.6 US and China

| Item | What it is | Status |
|---|---|---|
| SAE J2735 | Message dictionary: BSM, SPaT, MAP, SRM, SSM. SDSM section per the [ANSI preview listing, search result only][j2735listing] | Paywalled. SAE page would not load here |
| SAE J2945/1 | V2V on-board requirements | [Revised 2020, stabilized March 2026][j29451] |
| SAE J3161/1 | LTE-V2X profile. Rate control per Qualcomm | [Cited in Qualcomm][qc]. Not read |
| SAE J3216 | Cooperation classes A to D: status, intent, agreement seeking, prescriptive. Described in [TR 103 578 §4.2][tr578] and [SAE J3256][j3256] | [Revised 2021][j3216] |
| SAE J3224 | Sensor sharing, SDSM | [Issued August 2022][j3224]. Fields not read |
| SAE J3256 | Infrastructure-based prescriptive merge, Class D. An information report with proof-of-concept tests in virtual and track settings | [Issued March 2024][j3256] |
| FMVSS 150 | Proposed V2V mandate | **[Withdrawn November 2023][nprmw].** No US mandate exists |
| China T/CSAE 53 | Application layer, Phase I | Named in [Viavi sheet][viavi]. Not opened |
| China Phase II | Scenario list includes Cooperative Intersection Passing, Platooning, and message set with RSC, SSM, VIR, PAM, PSM, RTCM | [ITU slides][itu]. Field content **UNVERIFIED**. T/CSAE 157 could not be found |

### 2.7 Coordinated crossing: maturity

| Item | Maturity | Grade |
|---|---|---|
| [TR 103 578][tr578] crossing concept (§5.2.5) and four-way case with an RSU proposing manoeuvres (§5.4.4) | Informative report, V2.1.1 April 2024. Annex A says proposed formats were tested in national and European projects | SPEC, concept |
| ETSI TS 103 561 | Stable draft only | Unpublished |
| SAE J3186 | Published, V2V | SPEC |
| SAE J3256 | Merge only, information report | SPEC |
| China Phase II "Cooperative Intersection Passing" | Named | UNVERIFIED |
| Report [09](09-coordinated-intersections.md) reservation results | Simulation and small tests | SIM |

**No opened source shows a deployed signal-free crossing for general traffic under any standard.** SREM and SSEM are published and deployed for priority, not for all cars.

### 2.8 Security

**SPEC.** [TS 103 097 V2.2.1 (March 2026)][sec] uses IEEE 1609.2 structures in canonical OER. For CAMs the signer is the certificate digest by default, and the certificate is included once, one second after its last inclusion, and at once when an unknown authorization ticket is seen (7.1.1). A VAM includes a certificate if 500 ms have passed ([TS 103 300-3][vam]). IEEE 1609.2 itself is paywalled. I used its ASN.1 from the [ETSI forge][forge]. asn1tools could not compile it because of information object classes, so the counts below are by hand and were not checked by an encoder.

**DERIVED, signed data with digest, in COER:**

| Part | Bytes |
|---|---:|
| Version 1, content choice 1, hash id 1 | 3 |
| `SignedDataPayload` preamble | 1 |
| Inner `Ieee1609Dot2Data`: version, choice, length | 3 to 4 |
| `HeaderInfo` preamble 1, PSID 2 to 3, generation time 8 | 11 to 12 |
| Signer choice 1 + `HashedId8` 8 | 9 |
| Signature choice 1, r choice 1, r 32, s 32 | 66 |
| **Total** | **93 to 96, 95 used** |

**Certificate, DERIVED: about 145 B,** with a compressed key and two permissions: version and type 2, issuer 9, to-be-signed about 68, signature 66. NHTSA expected 117 B ([NPRM footnote 158][nprm]). The difference comes from the permissions and options. So attaching a certificate adds about 139 B, and at 1 Hz every CAM carries one.

**Verification load.** NXP's SAF5400 states "up to 2000 messages/sec" ([NXP][nxp], PRESS). DERIVED: 200 cars at 10 Hz, or 1,000 at 2 Hz, reaches that. Verify-on-demand can reduce this, but I found no primary number. Simulator: count required verifications, no cryptography.

## 3. What 3GPP specifies

**SPEC, all targets, not measurements.**

| Release | Direct link | Source |
|---|---|---|
| Rel-14 | LTE-V2X PC5, mode 4 and its congestion control | [TS 103 574][cc], [TS 103 613][ts613] |
| Rel-16 | NR sidelink: broadcast, groupcast, unicast, HARQ feedback via PSFCH | [TS 38.300 5.7][ts38300], [TR 21.916 8.4][tr21916] |
| Rel-17 | Partial sensing and random selection for power saving, reliability and latency enhancements | [TR 21.917 8.3.1][tr21917] |
| Rel-18 | Sidelink carrier aggregation in n47, LTE and NR co-channel coexistence, unlicensed sidelink, ranging and sidelink positioning with SL-PRS, MBS for V2X over Uu | [TR 21.918 §9.3, §9.6, §16.1][tr21918] |

- **Mode 1 versus mode 2.** In mode 1 the network assigns resources and the UE must be RRC-connected. In mode 2 the UE selects from pools, inside or outside coverage ([TS 38.300][ts38300]). A city may run mode 2 for robustness and mode 1 where coverage is firm. I found no field comparison.
- **Groupcast** can use NACK-only feedback on a shared resource ([TS 38.300 5.7.4.1][ts38300]).
- **Bandwidth.** n47 is 5855 to 5925 MHz, 10, 20, 30 or 40 MHz at 15, 30 or 60 kHz. At 30 kHz, 10, 20, 40 MHz is 24, 51, 106 PRB ([TS 38.101-1 Tables 5.3.2-1 and 5.3.5-1][ts38101]).
- **Requirements** ([TS 22.186 V19.1][ts22186]): cooperative collision avoidance 2000 B, 100 msg/s, 10 ms, 99.99%, 10 Mbit/s. Emergency trajectory alignment 3 ms, 99.999%, 30 Mbit/s, 500 m. Platooning at highest automation 50 to 1200 B, 30 msg/s, 10 ms, 99.99%. Relative lateral position 0.1 m (R.5.1-007). Relative longitudinal position under 0.5 m for platooning (R.5.2-003). R.5.1-001 requires control of communication range, which §6.5 relies on.
- **5GAA asks** ([position paper][fivegaa], PRESS, industry): Collaborative ACC 400 B at 10 Hz per user. Cooperative manoeuvres 48 kbit/s per user. Dynamic intersection management 300 B at 10 Hz per vehicle and 8 kbit/s per intersection. They claim 10 to 20 MHz for day-1 and "an additional 40 MHz or more" for advanced services.

### Spectrum in force

| Region | Spectrum | Source |
|---|---|---|
| US | 5895 to 5925 MHz, **30 MHz**, 10 MHz channels combinable to 20 or 30. FCC says 30 MHz suffices for basic safety and additional spectrum isn't needed for that. DSRC sunset in two years. Waivers used 33 dBm EIRP | [FCC, FR 2024-28980][fcc] |
| EU | 5875 to 5915 MHz prioritised for road, **40 MHz**, plus 5915 to 5925 rail-priority. 5855 to 5875 non-safety. ITS-G5 already operates in the band | [5GAA band paper][fivegaa] summarising ECC decisions. EUR-Lex text returned empty, so **Decision 2020/1426 was not read** |
| China | 5905 to 5925 MHz, **20 MHz** per a NIST presentation search listing | **UNVERIFIED**, search result only |

So 40 MHz is a real option only in the EU, and only if all of it were available to one technology. Treat 40 MHz as the upper bound, not the plan.

### Congestion control

**SPEC.** LTE-V2X ([TS 103 574 Table 1][cc]). CR limit is a share of the pool per station:

| CBR | PPPP 1-2 | PPPP 3-5 | PPPP 6-8 |
|---|---|---|---|
| 0 to 0.3 | none | none | none |
| 0.3 to 0.65 | none | 0.03 | 0.02 |
| 0.65 to 0.8 | 0.02 | 0.006 | 0.004 |
| 0.8 to 1 | 0.02 | 0.003 | 0.002 |

CBR is the share of sub-channels above −94 dBm, over 100 ms. CR is over 1000 subframes. NR defines SL CBR and SL CR the same way over 100 × 2^µ slots ([TS 38.215 5.1.26 and 5.1.27][ts38215]).

**DERIVED.** One 303 B message with a retransmission at 2 sub-channels each, in a 5 sub-channel 20 MHz pool, uses 0.04% of the pool. CR 0.006 then allows 15 Hz and CR 0.003 allows 7.5 Hz, about 18 kbit/s of air per car. **CBR binds well before the per-car limit does.**

**ITS-G5** uses [TS 102 687][dcc]. **SAE** rate control sets inter-transmit time from vehicle density within 100 m, as used by [Qualcomm][qc]. The J2945/1 formula itself is paywalled.

**FIELD, vendor, the calibration for everything below.** [Qualcomm 2020 study][qc]: 20 MHz, 10 sub-channels of 10 RB, 383 B BSM at MCS 11 in 20 RB with one retransmission, 48 emulating devices plus 2 or 8 under test.

| Load | Offered load | CBR, control off | Interval with control on | CBR, control on | Mean PER |
|---|---:|---:|---:|---:|---|
| 1× (100 ms) | 19.2% | about 25% | about 100 ms | about 25% | under 1% |
| 2× (50 ms) | 38.4% | 48% | up to 300 ms | 24% | under 1% |
| 5× (20 ms) | 96% | 87% | 600 ms | 24% | 4 to 5% off, under 1% on |

DERIVED: net payload is 1.5, 3.1, 7.7 Mbit/s without control. Load to CBR is about 1.25 up to saturation. That is the factor §6 uses. This is a controlled track with mostly emulated load, not a city.

## 4. What's deployed

| Place | What exists | Rates and share | Effect found | Grade |
|---|---|---|---|---|
| **Audi TLI, US** | [Cloud over 4G LTE with TTS][audius], launched Las Vegas 2016. 10 cities, over 2,250 intersections. Audi later states over 10,000 in North America | Not direct radio | "Reduces stress". No measured number | PRESS |
| **Audi, Düsseldorf** | [About 150 signals from January 2020, target about 450 of 600][audidus], after Ingolstadt. Prediction two minutes ahead from program, sensors and history | Cellular | Audi cites 15% fuel in a pilot, no method | PRESS |
| **BMW** | Could not substantiate | | | UNVERIFIED |
| **NYC pilot** | [3,000 fleet vehicles, 457 RSUs, 2019 to 2021][nycmob] | Silent then active periods, 5% control group | "Little evidence" for mobility. Penetration insufficient for some applications ([same][nycmob]). 160,289 alert events; active alerts tied to less speeding and red-light running, no effect sizes in the abstract ([FHWA-JPO-22-937][nycsafe]) | FIELD |
| **Tampa pilot** | Connected-vehicle pilot | | Little evidence of mobility impact, applications not operational ([FHWA-JPO-22-923][theam]). Fuel drop attributed to fewer vehicles, about 240 kg CO2/year attributed to deployment ([FHWA-JPO-22-922][theae]) | FIELD |
| **Utah** | [866 RSUs, 752 at signals, 50% of UDOT signals, 527 OBUs][udot] on buses and snowplows | Transit and fleet, not general traffic | Not read | PRESS, agency |
| **Austria** | [ASFINAG 350 RSUs by end 2023, 525 planned by 2025][asfinag]. Over 20 signals on Vienna's Ring for tram tests ([AustriaTech][atvienna]). C-ITS "serving approx. 1.5 M equipped vehicles" ([AustriaTech 2025][atpnt]) with ambiguous scope | ITS-G5 | Not found | Agency |
| **Netherlands** | [6-week controlled pilot, 7 hybrid signals near Schiphol][nh], ITS-G5 and 4G. Allowed latency 100 ms | Advice given on 56% of passages | **No significant flow difference.** See §5 | FIELD |
| **Sweden** | NordicWay 3 planned signal-switch prognoses for Gothenburg and Stockholm ([tender][mercell]). [Goudappel][goud] studied them for RISE in simulation. In 2025 a national strategy "is still missing" ([SAFER][safer]) | No rollout rate found | Simulated only | SIM |
| **China** | Wuxi planned by end 2021: 595 dual-mode and 201 single-mode RSUs, 656 signal controllers upgraded, 400 km² ([5GAA][c5gaa]). Chongqing 470 intersections planned ([same][c5gaa]). Huawei's Wuxi claim: 170 km², 240 intersections, 12,000 users ([Huawei][huawei]) | No national RSU or penetration count found | Not found | PRESS, plans |

**US targets.** ITS America's proposal: 250,000 of 330,000 signals within 10 years, 100,000 within 5 ([plan][itsaplan]). The USDOT summary link now returns 404, so its targets are not cited.

**Penetration is the honest gap.** Nothing opened shows signal-data or V2V penetration above a few percent of traffic anywhere. A 100% city is a future scenario with no empirical base.

## 5. Measured benefits versus simulated claims

| Study | Setting | Result | Grade |
|---|---|---|---|
| [LBNL evaluation][lbnl] | Field, fixed-time and adaptive corridor | Equipped against adjacent unequipped: 10 to 20% per EAD event. Applies to about 15% of arrivals. **Under about 1% of fuel on an average trip.** Other table cells read 3 to 4% in a garbled extraction | FIELD |
| [Same, literature table][lbnl] | Hao 2019 Palo Alto, 10 signals: 2% all trips, 6% with less following. Meng 2015: 3 to 4%. Mintsis 2017, 341 taxis: 6 to 9.1%. Altan 2017: 2 to 46% vs drivers. Barth 2012, one signal: 13.6%. Koukoumidis 2011: 20.3% | As tabulated, originals not read | Secondary |
| [Ottawa EcoDrive II][ottawa] | 7 fleet vehicles, 23,980 km, 29,393 signals, OBD, actuated, cellular | Negligible to 14%. **Fleet average 5%** | FIELD |
| [Noord-Holland pilot][nh] | Control and test groups, low penetration | No significant flow change. Users are "hindered" by other drivers | FIELD |
| [Chen & Rakha B-GLOSA][bglosa] | Virginia Smart Road test facility, 30 drivers, diesel bus | 22.1% fuel, 6.1% time | FIELD, test road |
| [Eco-CACC, VTTI][ecocacc] | Test facility, automated | 37.8% fuel, 9.3% time | FIELD, test road |
| [UCR corridor EAD][ucr] | Corridor | 12% to 28% claimed from authors' simulation and field | Mixed |
| [DRIVE C2X][malone] | FOT data, scaled by simulation | GLOSA a very small delay increase at full equipment. Environment under 1%, −2.3% fuel and CO2 at high penetration, all functions | SIM scale-up |
| [Stahlmann et al.][stahlmann] | DRIVE C2X FOT | "Most simulation studies are too optimistic" | FIELD, technical |
| [Goudappel for RISE][goud] | Gothenburg, Stockholm, Uppsala, simulation | Fewer stops, emissions barely change, cars slow rather than stop and may emit more per km | SIM |
| Report [10](10-mixed-autonomy-transition.md) on the thesis | GLOSA in SUMO | Emergency braking events rose, no fuel measured | SIM |

**Reading.** Isolated test-road numbers are several times to 10× the fleet numbers. The gap has known causes: few arrivals are affected, queues and leaders block the advised speed, actuated signals don't predict well, drivers don't follow advice, and only 10% of EAD work was tested at all (LBNL's review). **DERIVED expectation for the simulator at moderate demand: 1% to 5% energy per km across all cars, more at isolated fixed-time signals.** If the simulator shows 20% across a city, suspect an artefact first.

### Position accuracy

**FIELD.** [UrbanNav, Hong Kong][urbannav], least-squares GNSS, RMSE with availability in brackets:

| Receiver | Medium urban | Deep urban | Harsh urban |
|---|---:|---:|---:|
| NovAtel FlexPak 6 | 2.73 m (38%) | 6.13 m (83%) | 45.5 m (69%) |
| u-blox F9P | 16.7 m (84%) | 14.6 m (100%) | 85.8 m (27%) |
| Xiaomi Mi 8 | 31.7 m (80%) | 52.7 m (98%) | 257 m (40%) |

- **Lidar-inertial** in the same paper gets to about 0.15 to 0.9 m in the middle-class urban scene, with drift elsewhere.
- [Humphreys et al.][humphreys]: carrier-phase differential GNSS, about 2 h around dense central Austin: 17 cm 3D at 95%, availability above 87%, with nearby reference data and no inertial aid. So it is possible, in a far milder city than Hong Kong, and 13% of the time there is no solution.
- [Noord-Holland][nh]: OBU distance to lane centre clusters near 1 m, smartphones spread up to 15 m and cannot replace loops.

**Lane-level reliably from GNSS alone in a canyon: no.** TS 22.186's 0.1 m relative lateral target has no field support here. Gap keeping relies on sensors, as report 08 requires.

## 6. Capacity

### 6.1 Bytes on air

| Message | Payload | With digest | With certificate |
|---|---:|---:|---:|
| CAM status | 41 | 192 | 331 |
| CAM + 5 s intent, 10 points | 113 | 264 | 403 |
| CAM + 8 s intent, 16 points | 152 | **303** | **442** |
| CAM + 16 points, position confidence | 225 | 376 | 515 |
| CAM + 40 points | 310 | 461 | 600 |
| TS 22.186 collision avoidance | 2,000 | 2,151 | 2,290 |

### 6.2 Cars in range

**DERIVED.** Lane-km from the nets, passenger lanes on a 250 m grid. `Stockholm` and `best/berlin` agree within 10%. Median cell 16 to 17 lane-km/km², p95 33 to 36, p99 46 to 50.

| Disc radius | Stockholm lane-km, p50 / p95 | 20 cars per lane-km | 50 | 133 (jam, 7.5 m) |
|---|---|---:|---:|---:|
| 300 m | 5.2 / 9.4 | 104 / 188 | 260 / 470 | 692 / 1,251 |
| 500 m | 13.1 / 22.6 | 262 / 451 | 655 / 1,128 | 1,741 / 3,000 |
| 800 m | 35.5 / 59.4 | 709 / 1,189 | 1,774 / 2,972 | 4,718 / 7,904 |

Occupancy levels are assumptions. A whole disc at 133 is an extreme gridlock. For reference, [TR 37.885][tr37885]'s urban grid has 4-lane streets on a 433 × 250 m block.

**Which disc applies?** The [TR 37.885][tr37885] urban NLOS model with 23 dBm, 3 dB antennas each and a −94 dBm threshold gives **243 m** behind a corner. DERIVED. Line of sight along the same street goes over a kilometre by the same arithmetic, so a street is effectively one domain. Antenna gain is an assumption here. **Use 300 to 500 m as the working contention radius,** and treat 800 m as an upper bound for wide-open areas.

### 6.3 How many messages fit

**Method, DERIVED.** Count sub-channel slots, as CBR is defined.

- **LTE:** 1000 subframes/s, 10 RB sub-channels. Bits per RB fixed by Qualcomm's 383 B in 20 RB at MCS 11.
- **NR:** 30 kHz, 2000 slots/s, 10 PRB sub-channels. 12 × 10 = 120 RE per PRB after AGC, guard and 2 DMRS symbols. Minus 240 RE PSCCH and 40 RE SCI-2. Modulation and rate from [TS 38.214 Table 5.1.3.1-1][ts38214]. Sub-channels round up.
- **CBR = 1.25 × offered,** from [Qualcomm][qc].
- **Certificates once a second per car** (TS 103 097).

Sensitivity: a 12 or 15 PRB sub-channel can shift rows by up to 25%. I did not verify the allowed set from TS 38.331. Blind retransmission is a choice. Results by rate are stepwise because of rounding.

**Rate per car, Hz, CAM + 16-point intent:**

| Profile | CBR limit | MHz | Air Mbit/s | 200 cars | 500 | 1,000 | 2,000 | 3,000 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| LTE-V2X, as fielded (FIELD anchor) | .25 | 20 | 1.2 | 2.0 | 0.7 | 0.33 | 0.17 | 0.11 |
| LTE-V2X | .65 | 20 | 3.2 | 6.0 | 2.1 | 0.87 | 0.43 | 0.29 |
| NR 16QAM R.64, 1 retx | .25 | 10 | 0.5 | 1.0 | 0.4 | 0.20 | 0.10 | 0.07 |
| | | 20 | 1.2 | 2.5 | 1.0 | 0.50 | 0.25 | 0.17 |
| | | 40 | 2.4 | 5.0 | 2.0 | 1.00 | 0.50 | 0.33 |
| NR 16QAM R.64, 1 retx | .65 | 10 | 1.3 | 2.6 | 1.0 | 0.52 | 0.26 | 0.17 |
| | | **20** | **3.2** | **6.5** | **2.6** | **1.30** | **0.65** | **0.43** |
| | | 40 | 6.3 | 13.0 | 5.2 | 2.60 | 1.30 | 0.87 |
| NR 64QAM R.55, no retx (no reliability evidence) | .65 | 10 | 5.0 | 9.4 | 3.2 | 1.08 | 0.52 | 0.35 |
| | | 20 | 12.6 | 25 | 9.4 | 4.2 | 1.6 | 0.87 |
| | | 40 | 25.2 | 51 | 19.8 | 9.4 | 4.2 | 2.5 |

**Congestion control degrades this directly.** Holding CBR at .25 rather than .65 cuts the allowed rate by 2.6×. Qualcomm's measured back-off went from 100 ms to 600 ms, and report 08 shows p95 gaps no better than the send interval: lower loss, older data.

**Feasible intent length.** 16 points over 8 s at 0.5 s steps is the working value, a PROPOSED judgement: a city plan past about 8 s rarely holds. Sub-channel rounding makes the byte cost lumpy. At MCS 16, 10, 16 and 40 points all fit two sub-channels at 20 MHz, so 40 points costs no more airtime there. At 64QAM without retransmission, 40 points doubles it. Length is cheap until a boundary is crossed, and the certificate and rate matter more.

**Rate per car, Hz, CAM status only:** LTE as fielded (CBR .25, 20 MHz): 4.0, 1.0, 0.50, 0.25, 0.17 at 200, 500, 1,000, 2,000, 3,000 cars. NR 16QAM R.64 at CBR .65, 20 MHz: 12, 4.2, 1.6, 0.65, 0.43. At 40 MHz: 25, 9.4, 4.2, 1.6, 0.87.

**The 16-point row matters most,** because the 1 s certificate dominates at low rate: below 1 Hz every message carries it.

Reliability at these loads:

- LTE, FIELD, vendor: under 1% to 48% CBR, 4 to 5% mean at 87%, per [Qualcomm][qc]. Report 08 lists worst links reaching 13 to 17%.
- NR mode 2: SIM only. [Bazzi et al. 2026][sic] and [TR 37.885][tr37885] are simulation or assumptions. 12.5 and 50 veh/km highway cases exist in Bazzi. I did not extract a CBR-to-PRR curve, and [Todisco et al.][todisco] would not open.
- NR-PC5 field: **still no measurement found,** matching report 08. An extended search for 2025 and 2026 work returned simulation, LTE field results or methodology.

### 6.4 Fan-out and verification

At 1,000 cars and 2 Hz, each radio hears up to 2,000 messages/s, the [SAF5400's][nxp] stated limit. So verification sits near the limit at the same density radio does. Verify-on-demand and prioritising the leader and crossing foes is necessary, not optional. PROPOSED.

### 6.5 What to do about the limit

**DERIVED and PROPOSED, in order of value.**

1. **Use the CAM dynamics rule, not fixed 10 Hz.** 2.2 Hz on the `signal` fixture, 3.5 Hz at a steady 50 km/h, 1 Hz stopped. This cuts demand by 3× to 10×.
2. **Cut the range when dense.** Capacity scales with 1/R². TR 37.885 exponents: 10 dB less power is 0.46× NLOS range and 0.25× LOS range. Going from 23 to 10 dBm cuts the corner range from 243 m to 90 m. In a street grid that is about 4× to 7× fewer cars per domain, and range itself falls, so links near the edge are lost. Requires TS 22.186 R.5.1-001, range control. A queued car needs its leader, not cars 500 m away.
3. **Send intent only when it matters.** Only within about 150 m of a conflict, or when the plan departs from what followers would infer, in line with the 950 ms recommendation and "significant change" rule. Stopped cars omit it.
4. **Use fewer points where it crosses a sub-channel boundary.** 8 points cost 59 B against 111 B, which only saves airtime if it drops a whole sub-channel. Parametric intents cut more but are a departure.
5. **Let the RSU aggregate at junctions.** Foe traffic can come from one RSU instead of every car. An RSU CPM at 34 B per object beats 20 CAMs at 192 B, and covers unequipped cars.
6. **Move slow data to cellular.** MAP, IVIM, and long-range intent.
7. **Split pools,** a smaller version of 5GAA's day-1 and advanced split: 10 MHz for status and hazards, 20 MHz for intent and coordination. PROPOSED.

### 6.6 Cellular and edge

| | PC5 sidelink | Uu + edge | Sources |
|---|---|---|---|
| **Latency** | LTE 18 to 52 ms, mean 35 (FIELD) | 5G private and public mean 17 to 21 ms, p90 20 to 25, max 694 ms (FIELD, [CICV5G][cicv]). Commercial with Rel-14 devices mean 43 to 61 ms. With handover mean 66 to 130 ms, jitter up to 4,799 ([Kutila][kutila]) | |
| **Capacity** | Shared over distance, §6.3 | ITU minimum dense urban 5.4 bit/s/Hz/TRxP uplink, 7.8 downlink, 5th percentile 0.15 and 0.225 ([M.2410][m2410]). SPEC, not field | |
| **Fan-out** | Free, broadcast | Unicast is N×M. Rel-18 MBS for V2X addresses it ([TR 21.918 16.1][tr21918]). No field data found | |
| **Coverage** | Works with none | Needs coverage. Outages exist per report 08 | |

**DERIVED.** Assume 100 MHz TDD with a 25% uplink share and the ITU minimum: 135 Mbit/s per sector. 1,000 cars × 442 B × 1 Hz = 3.5 Mbit/s, 3% of that. At 10 Hz: 24 Mbit/s, 18%. So uplink can carry it where the radio minimum holds. Downlink multicast of a compact state, 40 B per car at 1 Hz, is 320 kbit/s, about 1.4 MHz at 0.225 bit/s/Hz. **Uu plus edge can carry far more than sidelink in a city,** but it adds latency and handover spikes and depends on a network. Safety isn't affected, since report 08's rule needs no radio.

### 6.7 Verdict

| Assumption for 2035 | Verdict | Why |
|---|---|---|
| Status per CAM dynamics rule, mean 2 to 4 Hz | **Reasonable** | SPEC today, §6.3 fits with range control |
| Intent 1 Hz, 16 points, 8 s, near conflicts | **Reasonable** | Published. 1.3 Hz at 1,000 cars, 20 MHz, CBR .65 |
| 20 MHz NR for automated driving, 10 MHz day-1 | **Reasonable** | Within US and EU allocations. China 20 MHz total, unverified |
| Loss under 1% in range at moderate load, latency 20 to 50 ms | **Reasonable** | LTE field data. NR no worse is an assumption |
| Bursts, 3 s gaps at overload | **Reasonable to keep** | Field, report 08 |
| RSU at most signals in one city, 100% AVs | **Scenario, not forecast** | Largest direct-radio systems found cover hundreds of signals |
| Position 0.3 to 1 m in most places, 2 to 5 m tails in canyons | **Reasonable with sensors and maps** | Tails from UrbanNav. GNSS alone no |
| Uu + MBS edge aggregation | **Plausible, unproven** | SPEC. No field |
| 40 MHz dedicated | **Optimistic** | EU only at best |
| 10 Hz status and intent, all cars, jam, all-to-all | **Science fiction** at 300 to 500 m | 73 Mbit/s against 3 to 6 |
| 40-point trajectories at 10 Hz | **Science fiction** | 111 Mbit/s at 3,000 cars |
| 3 ms and 99.999% city-wide | **Science fiction** as an assumption | Never measured. Report 08 shows it buys under 1 m anyway |
| Raw sensor sharing by all cars | **Science fiction** | 25 to 1000 Mbit/s rows in TS 22.186, see report 08 |
| 64QAM no-retransmit reliability | **Unknown** | No evidence opened |

## 7. Energy

### 7.1 Measured evidence

**Signal information:** §5. **Trip-level field results run 1% to 5%. Isolated test-road results run 13% to 38%.**

**Platooning, FIELD, trucks.** [NREL track study][nrelsae], DSRC, 55 to 70 mph, 20 to 75 ft: lead 2.7% to 5.3%, trailing 2.8% to 9.7%, team 3.7% to 6.4%. Best team at 55 mph, 30 ft, 65,000 lb. [NREL 2020][nrelmixed] reports that lateral offset cost 3% to 4% of fuel savings against about 10% when aligned (an earlier paper in its series), and tests mixed traffic, curves, cut-ins and mismatched trailers: a measurable impact in some conditions, with basic trends retained. I did not extract its scenario tables. **Trucks on highways, not cars in cities.** I found no measured passenger-car platoon fuel result. Stern et al. on ring wave damping are in [report 10](10-mixed-autonomy-transition.md).

**Electric vehicles.** I found **no field measurement** of signal-data savings on an EV. [Wang et al., arXiv 2410.01685][evpaper] model EV eco-driving, and their field test used "a regular gasoline sedan", not an EV. They cite others' 4% to 7% energy savings. So any EV saving here is modelled.

**Physical reason for an expected difference, DERIVED.** An avoided stop saves kinetic energy `½mv²`. A 1,663 kg car at 50 km/h has 160 kJ, or 45 Wh at the wheel. With [report 11's](11-vehicle-physics.md) assumed 60% regen capture, an EV loses about 18 Wh of that at the wheel. Combustion loses all 45 Wh, plus idle fuel while waiting. **Expect a combustion car to save about 2.5× as much wheel energy per avoided stop as an EV,** and more at the source, since fuel costs far more than electricity per wheel-Wh. Road load, grade and regen limits change this. A model showing the opposite is broken.

### 7.2 Model

**Base: [report 11][r11].** Force balance gives wheel power each tick:

```
P_w = m(1+ε)·a·v + (Crr·m·g·cosθ + ½ρ·CdA·v² + m·g·sinθ)·v
```

**Electric, PROPOSED, parameters from report 11:**

```
P_batt = P_w/η_d + P_aux                        if P_w ≥ 0
P_batt = −η_r·min(−P_w, P_regen_max) + P_aux     if P_w < 0
```

`η_d` 0.85, `η_r` 0.60 (both assumed in report 11, which got +7% on one car's WLTC figure), `P_regen_max` by type, `P_aux` 0.5 kW assumption, swept 0.3 to 2 kW for heating. SUMO has a comparable model with propulsion and recuperation efficiency ([SUMO][sumoev]).

**Combustion, PROPOSED, Willans form:**

```
P_fuel = 0                     if decelerating with fuel cut (P_w < 0, v above cut speed) or engine stopped by start-stop
P_fuel = P_idle + P_w/η_e      if P_w ≥ 0
P_fuel = P_idle                if P_w < 0 and no cut, or idling
```

Two numbers per type, `P_idle` and `η_e`, calibrated to WLTC or EPA city and highway from report 11's list. I did not open a Willans primary, so this form rests on engineering practice and must pass the test below. `start_stop` and `fuel_cut` are per-type flags, default on for 2035 stock, off for a Swedish-fleet sensitivity. SUMO's documented alternatives, [HBEFA and PHEMlight][sumoem], can be applied offline to the same FCD as an independent check.

**Tests before reporting any number:**

| Test | Target | Source |
|---|---|---|
| I16 energy balance | Within 1% per trip | [Report 11][r11]. Euler mode fails by construction, so energy is reported only in physical mode |
| WLTC, per type | Declared consumption within ±10% | Report 11 |
| Stop against cruise at one signal | Field ratio 26.3 g / 16.6 g = **1.58** for a stopped arrival vs a cruise, same site | [LBNL table][lbnl], 2,747 and 2,549 events, totals check by multiplication. Different site means this is a sanity band, ±25% |
| Avoided stop, EV against combustion | Combustion gains more | §7.1 |
| Offline HBEFA comparison | Report difference, no target | [SUMO][sumoem] |

### 7.3 How to report

Per type and share: **wheel Wh/km, battery Wh/km for EVs, fuel L/100 km and tailpipe CO2/km for combustion,** per km and per trip. Also energy per stop avoided. Rules:

1. **All cars, not just equipped.** Followers hindered or smoothed count. Report equipped and unequipped separately too. Dutch and Goudappel results show why.
2. **Same trips completed.** Unfinished trips bias energy per km. Report throughput next to energy.
3. **Baseline identical** in demand, seed and network.
4. **Report the arrival share affected,** as LBNL does.
5. **Fleet mix stated:** Swedish fleet from report 11 and a 100% EV case, always both.
6. **Confidence intervals across seeds.** A gain inside the interval is reported as none.
7. **No fuel claim from time loss.** The thesis made one and report 10 caught it.

## 8. Build spec

**Departures are marked ⚠.** The goal: real names, real fields, real billed bytes. No radio physics per pair.

### 8.1 Design

- **Bill bytes as the real standard does, store far less.** A car stores a small state on the GPU. The channel is charged for the real message size in §6.1.
- **Stateless delivery by hash,** as report 08 specifies: `delivered = !burst && hash(sender, receiver, seq, epoch) > p_loss(class, d, CBR, size)`.
- **Receivers pull,** only for what they need: the leader from sorted lane order, conflict partners through the junction. No neighbour lists, no per-link state, no queues.
- **No function-local arrays** (AGENTS.md). All structs have `#[repr(C)]` twins. `P.comm == 0` keeps today's kernel bit-identical.

### 8.2 Messages

| Sim name | Real name | From, to | Real fields used | Sim fields | Billed payload | Rate |
|---|---|---|---|---|---:|---|
| `STATUS` | CAM TS 103 900, high-frequency | Car, broadcast | `referencePosition`, `heading`, `speed`, `longitudinalAcceleration`, `curvature`, `yawRate`, length, width, `stationType`, `accelerationControl` | pos, lane, speed, acc, vtype, flags | 41 B | Dynamics rule, §2.3 |
| `STATUS_LF` | CAM low-frequency | Car | `vehicleRole`, `exteriorLights`, `pathHistory` | Billed only | +2 B + 6.5/point, default 10 points | Every 500 ms |
| `BRAKE` ⚠ | No field in CAM. **Departure** | Car | Advertised `B`, certificate `Y_c` from report 08 | `y_cert` | 6 B in an extension, PROPOSED | With intent |
| `INTENT` | CAM Path Prediction | Car | `pathPredicted[deltaLat, deltaLon, pathDeltaTime]`, `usageIndication = adasAd`, `confidenceLevel` | Parametric plan, §8.5 ⚠ stored compressed | 111 B for 16 points, 8 s; configurable 72, 269 | ≥ 950 ms, or on change |
| `SPAT` | SPATEM | RSU | `states[signalGroup, eventState, minEndTime, maxEndTime, likelyTime, confidence, speeds]` | From `GpuTlsState`, predicted, §8.4 | 22 + 10.1/group | 1 Hz default, 10 Hz sweep |
| `MAP` | MAPEM | RSU | Lanes, connections, signal groups | **Not simulated as received** ⚠. Cars know the net. Billed | 519 B for 16 lanes | 1 Hz |
| `CPM_RSU` | CPM | RSU | Up to 20 objects | Unequipped cars at approaches | 36 + 34/object | 1 Hz, on with share < 100% |
| `HAZARD` | DENM | Car or RSU | Event | Lowers `Y` per report 08 | 43 B | Event, repeat 3 |
| `CROSS_REQ` ⚠ | SREM repurposed. Defined for priority | Car to RSU | `inBoundLane`, `outBoundLane`, `minute/second` as ETA, `duration` | Per report 09 | 30 B | On approach, repeat 1 Hz |
| `CROSS_GRANT` ⚠ | SSEM repurposed | RSU | `inboundOn`, `outboundOn`, `second`, `duration`, `status = granted/rejected` | Per report 09 | 29 + 15.6/request after the first | On change, 1 Hz |

Each billed message adds 95 B signature, 44 B network, 12 B link. Each car adds 139 B once a second for its certificate. **Other departures:** no CRLs or misbehaviour; no certificate changes or privacy; no GeoNetworking forwarding (none in CAM anyway); MCM not used, since draft; 4 m and 4° triggers use lane-path distance and chord heading; CR limits replaced by a pool-wide rate controller; RSU has 360° ideal install.

**US mapping,** for a label switch only: CAM→BSM, SPATEM→SPaT, MAPEM→MAP, SREM→SRM, SSEM→SSM, CPM→SDSM. Header 44 B falls to a smaller value, unverified.

### 8.3 Channel

**Link classes,** computed from topology, not ray tracing:

| Class | Test | Model, from [report 08](08-v2x-and-safety-first-principles.md) |
|---|---|---|
| `LOS_STREET` | Same edge, no large vehicle between | `R50` from 650 m with cliff width 15% |
| `NLOSV` | Same edge, truck or bus between | `LOS_STREET` plus report 08's blocker row: 47 to 60% loss at overload without congestion control, 2 to 3% with it |
| `CORNER` | Adjacent edges across a junction | `R50` about 243 m at 23 dBm, DERIVED here, or 470 m FIELD for NLOS per Kutila. Sweep both |
| `RSU` | One end is RSU | 400 m default, 33 dBm option |
| `FAR` | Otherwise | Not delivered |

**Loss:** `p_loss = 1 − (1−p_range)(1−p_size)(1−p_load)` with report 08's tables: `p_size` 0 to 500 B, .02 at 750, .06 at 1000. `p_load` .005 at CBR .25, .007 at .47, .13 at .82, interpolated. Burst state: one bit per sender.

**Latency:** LTE uniform 18 to 52 ms. Represented as one tick delay at `dt = 0.1` and none at `dt = 1`.

**Zones.** A grid of 250 m cells covering the net.

```
each tick, each tx:   atomicAdd(cell.occ, k · ntx)        // k sub-channels from billed size, table lookup
next tick:            CBR(cell) = 1.25 · Σ(3×3 cells) occ / (N_sub · slots_per_s · dt), capped at 1
controller:           r_cc = r_prev · CBR_target / CBR, floor 1/0.6 Hz
actual rate:          min(r_dyn, r_cc)
```

The 3×3 block sets a contention radius of about 375 m. Power control sets it smaller with a `k_range` factor. Controller floor is from [Qualcomm][qc]; proportional law is PROPOSED ⚠.

**Profiles:**

| Name | `N_sub`, slots/s | Grade |
|---|---|---|
| `lte20` | 10, 1000 | FIELD anchor, default |
| `nr10`, `nr20`, `nr40` | 2, 5, 10; 2000 | SPEC, labelled untested |
| `nr_ideal` | Report 08's 3 to 10 ms, 10⁻⁴ | SPEC stress, never a headline |
| `uu` | No CBR. Latency mean 19 ms, tail per CICV5G. Handover outage per Kutila | FIELD |
| `uu_edge` | `uu` + 40 B per car multicast, 1 Hz | PROPOSED, unmeasured |

### 8.4 Roadside unit

**What it is.** A fixed station at a signal or coordinated junction, wired to the controller. It:

- Sends SPAT at its rate, MAP at 1 Hz, CPM if enabled.
- Hears CAMs within range through the same channel class, with position error.
- Keeps per-approach counts from CAMs only, which adaptive control reads. Never ground truth.
- Runs report 09's arbiter for coordinated crossings: durable grants, silence never releases.

**SPaT honesty, required.** A car must not read the controller's true future when the signal is actuated.

- Fixed-time: `minEndTime = maxEndTime = likelyTime = true`.
- Actuated: `minEndTime` from min green, `maxEndTime` from max green, `likelyTime` from a recent-history average with error. `confidence` set from observed error. Sweep prediction error, with the Dutch 40% to 80% as the case to reach.

**GLOSA behaviour.** Cars with F4 get advice inside `R_spat`. AVs follow it, subject to the safety rule. Humans comply with a per-driver probability, default 0.5 (PROPOSED, no measured value), with Ottawa's negligible to 14% range as the target to check.

**Adaptive signals (F5).** Cars to lights: only counts from CAMs. At share `s`, the count is short by `1 − s`. Scale up with a known penetration option; otherwise biased, which is the realistic case. Noord-Holland: smartphone positions were too poor to replace loops, so a position error sweep goes here.

### 8.5 Buffers

| Buffer | Fields | Bytes | Per |
|---|---|---:|---|
| `GpuCommVeh` | `snap_pos f32`, `snap_speed f32`, `snap_acc_heading` (i16+u16), `snap_lane u32`, `seq u16`, `flags u16`, `last_tx_step u32`, `trig_pos f32`, `trig_speed f32` | 32 | Vehicle |
| `GpuIntent` ⚠ | `a1 i8`, `t1 u8`, `a2 i8`, `t2 u8`, `v_target u16`, `conf u8`, `seq u8`. Two-segment plan the receiver expands. Billed as 16 points | 8 | Vehicle |
| `GpuRxLeader` | `rx_pos f32`, `rx_speed f32`, `rx_seq u16`, `age u16`, `rx_intent_seq u16`, pad | 16 | Vehicle |
| Energy | `E_wheel_pos f32`, `E_brake f32`, `E_source f32` (fuel or battery) | 12 | Vehicle, in `GpuTripOut` at end |
| `GpuRsu` | `junction u32`, `spat_seq u32`, `next_min f32`, `next_max f32`, `next_likely f32`, `conf f32`, `flags u32`, pad | 32 | Junction |
| `GpuLaneRx` | `cam_stop u16`, `cam_app u16`, `eta_sum f32` | 8 | Approach lane |
| `GpuZone` | `occ atomic u32`, `cbr f32`, `tx u32`, `rx_lost u32` | 16 | 250 m cell |

Report 08's 24 B and report 09's 32 B are separate, and their `claim` and grant fields can be shared. **Total here: 68 B per vehicle,** 68 MB per million. A 30 km square at 250 m is 14,400 zones, 230 kB. Everything is small enough to keep 3 GB spare at any tested scale. Arithmetic, no benchmark.

**Compute.** One rate check, one zone add, and one hash per needed link per tick. No function-local arrays. Keep Sim::run's short submissions.

### 8.6 Feature flags

Per [AV-REQUIREMENTS](AV-REQUIREMENTS.md). Each independent, same demand, seed and net.

| # | Requirement | Flag | Turns on | Uses |
|---|---|---|---|---|
| 1 | No communication | `comm=0` | Nothing | Sensors, report 08 rule |
| 2 | Status V2V | `comm.status` | `STATUS`, `STATUS_LF`, `HAZARD` | Feedforward, earlier braking |
| 3 | Plus trajectories | `comm.intent` | `INTENT`, `BRAKE` | Smoother following, lane change. Certificate tier opt-in |
| 4 | Plus light data | `comm.spat` | RSU `SPAT`, `MAP` | GLOSA, time to green |
| 5 | Plus cars to lights | `comm.v2i` | RSU ingest | Adaptive control from CAM |
| 6 | Coordinated crossing | `comm.cross` | `CROSS_REQ`, `CROSS_GRANT` | Report 09 policy |
| 7 | Loss and share | `loss_mult`, `share` | Sweep .001, .01, .1, .5, 1 × table; 0, 10, 25, 50, 75, 100% | All |

Secondary factors, each on and off: `rate=dynamic|10hz`, `range_ctl`, `cpm_rsu`, `cert_tier`, `spat_pred_err`, `pos_err` (from §5: 0.3 m, 1 m, 3 m, canyon mixture), `profile`, `cc_target` (.25, .65).

**Test matrix first.** Report 08's attack tests must still pass with every flag. Status-off equals `comm=0` on safety outcomes (08 test 1).

### 8.7 Metrics

Per AV-REQUIREMENTS plus channel, with confidence intervals across seeds, by flag, per class and equipped status:

- **Flow:** travel time, delay, queue length, stopped time, throughput, stops per km, gridlock count and location.
- **Energy:** §7.3.
- **Safety:** collisions and teleports (must be 0), minimum margin `M`, hard-brake rate, `PREMISE_VIOLATED`.
- **Channel:** CBR distribution by zone and time, share of zone-seconds over .25 and .65, messages and Mbit/s by type, overhead share, rate achieved against rate wanted, age of leader data (mean, p95, max), consecutive losses, verifications needed per second against 2000.
- **Signals:** prediction error, share of arrivals affected, GLOSA advice share, compare Noord-Holland's 56%.
- **Crossing:** requests, grants, wasted slots, grant latency.

### 8.8 Visualisation

From recorded data through `cars replay`, never during simulation. Recorder: zone table per second, per-vehicle flags in FCD (`last_tx`, `rx_ok`, `intent_seq`), RSU events, grant log. Only sample link lines.

| Thing | Drawing |
|---|---|
| Broadcast | Brief expanding ring on tx, colour by message type |
| Range | Faint disc from class radius, for selected cars only |
| Links | Line from receiver to leader or RSU: solid if delivered, red × if lost, fade with age |
| Stale view | Ghost car where the follower believes the leader is |
| Intent | Polyline ahead with dots at time steps, colour by confidence |
| RSU | Icon at junction, pulse on SPAT, ring at 400 m, per-approach count |
| SPaT | Countdown over stop line, min-max bar for actuated |
| Grants | Coloured slot on conflict zone with time window, red on reject |
| Channel | CBR heat map per zone, gauge with .25 and .65 lines |
| Overlay | Flags on, loss, share, Mbit/s |

### 8.9 Build order

1. Python unit tests: bytes table, CBR calibration (19.2/38.4/96% offered gives 25/48/87% within a few points), rate rule against §2.3 in a single-lane trace.
2. `comm=0` bit-identical check, then zones and rate law with a CPU cross-check. No behaviour change.
3. Status and channel. Scale 1k → 100k vehicles, one GPU job at a time.
4. Intent, then SPaT with honest prediction, then V2I, then crossing per report 09.
5. Energy needs report 11's physical mode first.

## 9. What I could not verify

- **SAE J2735, J2945/1, J3161, J3186, J3216, J3224, IEEE 1609.2, 1609.3 and ISO 19091 full text.** Abstracts, the ETSI copy of 1609.2 ASN.1 and public descriptions only. Exact BSM and SDSM bytes are unknown here. J2735's SAE page would not load, and the ANSI preview returned 403.
- **ETSI TS 103 561 draft content.** TR 103 578 and the work item page only. The portal status can lag.
- **CAPIM.** Not found.
- **China's standards.** T/CSAE 53 and 157 contents. Whether VIR carries a planned path. China's 20 MHz from a search listing. No national RSU or penetration count. Sinocities' intersection counts were not cited because the piece doesn't name a city clearly.
- **EU Decision 2020/1426** itself. EUR-Lex returned empty, so the band plan is via 5GAA.
- **BMW's signal service.** No primary found. Audi's claims are press statements.
- **Stockholm SPaT in operation.** Only tender and simulation.
- **NR-PC5 in the field,** at any density. PRR against CBR for NR mode 2 was not extracted. Todisco et al. did not open.
- **Sidelink sub-channel size options.** The 10 PRB value is from Qualcomm's LTE config and assumed for NR. BTP size and L2 total are assumptions. Security bytes were hand-counted, not encoded.
- **Willans primary source, VT-CPFM paper.** Not opened. DOAJ returned 403. OSTI and original NREL hosts failed. NLR host worked.
- **LBNL slide extraction** is overlapped text. The event table was checked by arithmetic, and "3 to 4%" and "about 15% of arrivals" were read through overlap. Check the slide before quoting further.
- **C-Roads harmonised profiles.** Not opened, so C-Roads rates are not stated.
- **DRIVE C2X D11.4** full deliverable not opened. Summary paper only.
- **Everything capacity-related is arithmetic,** anchored on one vendor study and evaluation assumptions. City radio propagation is not measured here.
- **Nothing was benchmarked or simulated.**

## 10. What only Erik can do

None of these block the build.

1. **Buy SAE J2735 and J3186** if BSM-exact or J3186-exact bytes matter. The ETSI mapping works without them.
2. **Get TS 103 561's latest draft** through an ETSI portal account if MCM-exact coordination is wanted.
3. **Buy T/CSAE 157** if a China-faithful mode is wanted.
4. **Decide the headline profile.** I chose `lte20` as default since it alone has field data, with `nr20` next to it, labelled untested.

## Source register

All opened in this session, except where a row in §9 says otherwise. Local copies and the fetch log are as listed at the top. ETSI PDFs are free. SAE pages are abstracts.

**Standards, ETSI.**

[cam2]: https://www.etsi.org/deliver/etsi_ts/103900_103999/103900/02.03.01_60/ts_103900v020301p.pdf
[cam1]: https://www.etsi.org/deliver/etsi_en/302600_302699/30263702/01.04.01_60/en_30263702v010401p.pdf
[denm2]: https://www.etsi.org/deliver/etsi_ts/103800_103899/103831/02.03.01_60/ts_103831v020301p.pdf
[cpm]: https://www.etsi.org/deliver/etsi_ts/103300_103399/103324/02.01.01_60/ts_103324v020101p.pdf
[vam]: https://www.etsi.org/deliver/etsi_ts/103300_103399/10330003/02.03.01_60/ts_10330003v020301p.pdf
[is]: https://www.etsi.org/deliver/etsi_ts/103300_103399/103301/02.03.01_60/ts_103301v020301p.pdf
[sec]: https://www.etsi.org/deliver/etsi_ts/103000_103099/103097/02.02.01_60/ts_103097v020201p.pdf
[cc]: https://www.etsi.org/deliver/etsi_ts/103500_103599/103574/01.01.01_60/ts_103574v010101p.pdf
[dcc]: https://www.etsi.org/deliver/etsi_ts/102600_102699/102687/01.02.01_60/ts_102687v010201p.pdf
[ts613]: https://www.etsi.org/deliver/etsi_ts/103600_103699/103613/01.01.01_60/ts_103613v010101p.pdf
[ts916]: https://www.etsi.org/deliver/etsi_ts/103900_103999/103916/02.01.01_60/ts_103916v020101p.pdf
[tr578]: https://www.etsi.org/deliver/etsi_tr/103500_103599/103578/02.01.01_60/tr_103578v020101p.pdf
[tr562]: https://www.etsi.org/deliver/etsi_tr/103500_103599/103562/02.01.01_60/tr_103562v020101p.pdf
[gn]: https://www.etsi.org/deliver/etsi_en/302600_302699/3026360401/01.04.01_60/en_3026360401v010401p.pdf
[mcmwi]: https://portal.etsi.org/webapp/WorkProgram/Report_WorkItem.asp?WKI_ID=53496
[forge]: https://forge.etsi.org/rep/ITS/asn1
[camasn]: https://forge.etsi.org/rep/ITS/asn1/cam_ts103900
[cdd]: https://forge.etsi.org/rep/ITS/asn1/cdd_ts102894_2
[dsrc]: https://forge.etsi.org/rep/ITS/asn1/is_ts103301

[TS 103 900][cam2], [EN 302 637-2][cam1], [TS 103 831][denm2], [TS 103 324][cpm], [TS 103 300-3][vam], [TS 103 301][is], [TS 103 097][sec], [TS 103 574][cc], [TS 102 687][dcc], [TS 103 613][ts613], [TS 103 916][ts916], [TR 103 578][tr578], [TR 103 562][tr562], [EN 302 636-4-1][gn], [TS 103 561 work item][mcmwi], [ASN.1 forge][forge], [CAM ASN.1][camasn], [CDD ASN.1][cdd], [IS ASN.1][dsrc].

**3GPP, via ETSI.**

[ts22186]: https://www.etsi.org/deliver/etsi_ts/122100_122199/122186/19.01.00_60/ts_122186v190100p.pdf
[ts38300]: https://www.etsi.org/deliver/etsi_ts/138300_138399/138300/19.04.00_60/ts_138300v190400p.pdf
[ts38214]: https://www.etsi.org/deliver/etsi_ts/138200_138299/138214/18.08.00_60/ts_138214v180800p.pdf
[ts38215]: https://www.etsi.org/deliver/etsi_ts/138200_138299/138215/18.05.00_60/ts_138215v180500p.pdf
[ts38321]: https://www.etsi.org/deliver/etsi_ts/138300_138399/138321/19.03.00_60/ts_138321v190300p.pdf
[ts38101]: https://www.etsi.org/deliver/etsi_ts/138100_138199/13810101/19.07.00_60/ts_13810101v190700p.pdf
[tr21916]: https://www.etsi.org/deliver/etsi_tr/121900_121999/121916/16.02.00_60/tr_121916v160200p.pdf
[tr21917]: https://www.etsi.org/deliver/etsi_tr/121900_121999/121917/17.00.01_60/tr_121917v170001p.pdf
[tr21918]: https://www.etsi.org/deliver/etsi_tr/121900_121999/121918/18.00.00_60/tr_121918v180000p.pdf
[tr37885]: https://atisorg.s3.amazonaws.com/archive/3gpp-documents/Rel15/ATIS.3GPP.37.885.V1530.pdf

[TS 22.186][ts22186], [TS 38.300][ts38300], [TS 38.214][ts38214], [TS 38.215][ts38215], [TS 38.321][ts38321], [TS 38.101-1][ts38101], [TR 21.916][tr21916], [TR 21.917][tr21917], [TR 21.918][tr21918], [TR 37.885 via ATIS][tr37885].

**SAE abstracts, US rulemaking, spectrum, ITU.**

[j3186]: https://saemobilus.sae.org/content/J3186_202303
[j3224]: https://saemobilus.sae.org/content/J3224_202208
[j3216]: https://saemobilus.sae.org/content/J3216_202107
[j3256]: https://saemobilus.sae.org/content/J3256_202403/
[j29451]: https://saemobilus.sae.org/content/J2945/1_202004
[j2735listing]: https://webstore.ansi.org/preview-pages/SAE/preview_J2735_202409.pdf
[nprm]: https://www.govinfo.gov/content/pkg/FR-2017-01-12/html/2016-31059.htm
[nprmw]: https://www.govinfo.gov/content/pkg/FR-2023-11-20/pdf/2023-25519.pdf
[fcc]: https://www.govinfo.gov/content/pkg/FR-2024-12-13/html/2024-28980.htm
[fivegaa]: https://5gaa.org/content/uploads/2024/03/5gaa-position-paper-european-road-its-deployment.v3.pdf
[m2410]: https://www.itu.int/dms_pub/itu-r/opb/rep/R-REP-M.2410-2017-PDF-E.pdf
[itu]: https://fnc.itu.int/wp-content/uploads/2021/12/Wang-Jian.pdf
[viavi]: https://www.viavisolutions.com/en-us/literature/ttsuite-china-its-data-sheet-en.pdf
[nxp]: https://nxp.com/products/SAF5400

[J3186][j3186], [J3224][j3224], [J3216][j3216], [J3256][j3256], [J2945/1][j29451], [J2735 ANSI preview: search listing only, the fetch returned 403][j2735listing], [NHTSA NPRM][nprm], [withdrawal][nprmw], [FCC rule][fcc], [5GAA band paper][fivegaa], [ITU-R M.2410][m2410], [China ITU slides][itu], [Viavi][viavi], [NXP SAF5400][nxp].

**Radio field and simulation.**

[qc]: https://www.qualcomm.com/media/documents/files/c-v2x-congestion-control-study.pdf
[kutila]: https://5g-drive.eu/wp-content/uploads/2021/09/A-C-V2X-5G-Field.pdf
[cicv]: https://arxiv.org/pdf/2504.08255
[sic]: https://arxiv.org/pdf/2603.03039v1
[todisco]: https://cris.unibo.it/handle/11585/850504

[Qualcomm study][qc], [Kutila et al.][kutila], [CICV5G][cicv], [Bazzi et al. 2026][sic], [Todisco et al.: returned 403][todisco].

**Deployments.**

[audius]: https://theshopmag.com/news/audi-expands-traffic-light-information-10-cities/
[audidus]: https://www.automotiveworld.com/news/audi-networks-with-traffic-lights-in-dusseldorf/
[nycmob]: https://rosap.ntl.bts.gov/view/dot/62792/dot_62792_DS1.pdf
[nycsafe]: https://rosap.ntl.bts.gov/view/dot/63319
[theam]: https://rosap.ntl.bts.gov/view/dot/62786
[theae]: https://rosap.ntl.bts.gov/view/dot/61964
[udot]: https://itsa.org/wp-content/uploads/2025/10/UDOT-V2X-Accelerator-Webinar-10-02-25-1.pdf
[itsaplan]: https://itsa.org/wp-content/uploads/2023/04/V2XDeploymentPlan.pdf
[asfinag]: https://www.transport-community.org/wp-content/uploads/2023/09/ASFINAG__C-ITS_Deployment_on_Austrian_Motorways.pdf
[atvienna]: https://austriatech.at/en/c-its-international-guests-in-vienna/
[atpnt]: https://austria-in-space.at/resources/pdf/events/03-20250129-pole-position-with-satellite-navigation-pnt-meets-mobility-austriatech.pdf
[nh]: https://noord-holland.nl/bestanden/pdf/Eindrapportage%20pilot%20slimme%20verkeerslichten%20en%20GLOSA%20Green%20Light%20Optimised%20Speedadvice.pdf
[mercell]: https://www.mercell.com/permalink/157166937.aspx
[goud]: https://www.goudappel.nl/en/projects/evaluating-impact-glosa-nordicway-research
[safer]: https://www.saferresearch.com/node/4007
[c5gaa]: https://5gaa.org/content/uploads/2022/10/C-V2X-Pilot-and-Demonstration-Areas-in-China.pdf
[huawei]: https://www.huawei.com/en/news/2019/2/huawei-cellular-v2x-awarded
[umich]: https://traffic.engin.umich.edu/facilities-and-resources/open-data

[Audi US press][audius], [Audi Düsseldorf press][audidus], [NYC mobility assessment][nycmob], [NYC safety assessment][nycsafe], [Tampa mobility][theam], [Tampa environment][theae], [Utah][udot], [ITS America plan][itsaplan], [ASFINAG][asfinag], [AustriaTech Vienna][atvienna], [AustriaTech 2025][atpnt], [Noord-Holland GLOSA pilot][nh], [NordicWay 3 tender][mercell], [Goudappel][goud], [SAFER][safer], [5GAA China][c5gaa], [Huawei Wuxi][huawei], [UMich][umich].

**Benefits, position, energy.**

[lbnl]: https://www.energy.gov/eere/vehicles/articles/experimental-evaluation-eco-driving-strategies-0
[ottawa]: https://tac-atc.ca/fr/?p=18995
[bglosa]: https://vtechworks.lib.vt.edu/items/8943b031-966b-46f7-a936-4ac3b16730f2
[ecocacc]: https://rosap.ntl.bts.gov/view/dot/31162/dot_31162_DS1.pdf
[ucr]: https://www.cert.ucr.edu/media/8361/download
[malone]: https://publications.tno.nl/publication/34626189/TDtmAO/malone-2015-impact.pdf
[stahlmann]: https://cris.fau.de/publications/111343804/
[urbannav]: https://navi.ion.org/content/navi/70/4/navi.602.full.pdf
[humphreys]: https://arxiv.org/pdf/1906.09539
[nrelsae]: https://docs.nlr.gov/docs/fy15osti/62348.pdf
[nrelmixed]: https://docs.nlr.gov/docs/fy21osti/78218.pdf
[evpaper]: https://arxiv.org/pdf/2410.01685
[sumoev]: https://sumo.dlr.de/docs/Models/Electric.html
[sumoem]: https://sumo.dlr.de/docs/Models/Emissions.html
[r11]: 11-vehicle-physics.md

[LBNL slides][lbnl], [Ottawa EcoDrive II][ottawa], [Chen & Rakha][bglosa], [VTTI Eco-CACC][ecocacc], [UCR EAD][ucr], [DRIVE C2X impact paper][malone], [Stahlmann et al.][stahlmann], [UrbanNav][urbannav], [Humphreys et al.][humphreys], [NREL SAE 2014, NLR host][nrelsae], [NREL 2020, NLR host][nrelmixed], [EV eco-driving][evpaper], [SUMO electric][sumoev], [SUMO emissions][sumoem], [report 11][r11].

**Tried and not usable, no numbers taken:** USDOT plan summary (404), UVA SPaT fact sheet (403), ITS KRS pages (403), Alberta GLOSA thesis (script-rendered page, no text), EUR-Lex 2020/1426 (empty), Federal Register site (blocked, govinfo copy used), Autotalks figures (a secondary mention only), Todisco et al. (403), ROS MCM package docs (denied), SAE J2735 page (would not load), the taxonomy site for J3216 classes (no definitions on the page).
