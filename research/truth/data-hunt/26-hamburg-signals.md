# 26. Hamburg live signals: collector and first cycle numbers

Grades: MEASURED = counted from data I opened on 2026-11-02. Nothing here is a claim about Stockholm.

## The collector

- **Source:** `https://tld.iot.hamburg.de/v1.1` (OGC SensorThings, no key). Licence **dl-de/by-2.0**, attribution "Freie und Hansestadt Hamburg, zuständige Behörde" (read from the Transparenzportal record's `terms_of_use`, MEASURED). I found no stated rate limit, so it runs sequentially at about 5 requests per second at most and backs off on 429 and 5xx.
- **Static data, saved once:** `/home/erikf/projects/personal/cars-data/datasets/hamburg-signals/static/` has all 20,086 lane connections (Things) with their datastreams (including each `signal_program` stream) and the geometry of ingress lane, egress lane and route (Locations), plus Sensors and ObservedProperties. 3.7 MB. The program content itself is only a program id per second in the `signal_program` stream; the API has no plan tables.
- **District:** `district.json`. 50 lights that had signal data in the last hour (535 of 796 were live), the 50 nearest each other around seed light 86, radius 1.27 km, 1,557 lane connections. "Densest roads" is approximated by packing: the smallest circle holding 50 live lights.
- **What is polled:** per light, the `primary_signal`, `signal_program`, `detector_car`, `detector_pt` and `detector_bike` layers, one filtered Observations query per light and layer.
- **Storage:** `days/YYYY-MM-DD.tsv.gz`, columns light, layer, stream id, UTC time, result. Appended as gzip members, so a crash loses at most one chunk. `state.json` holds a per-light-and-layer cursor with 5 minutes of overlap; a restart resumes there. Rows can repeat after a crash; deduplicate on (stream, time).
- **Script:** `scripts/hamburg_signals.py` (`static`, `pick`, `run`, `stats`). Standard library only.
- **Job:** `agent-job run hamburg-signals -- bash -c 'while true; do python3 -u scripts/hamburg_signals.py run; sleep 60; done'`. It is a systemd user unit, so it survives T3 restarts. It does not survive a reboot of the PC; re-run the command. Stop it with `agent-job stop hamburg-signals`.
- **Cost:** about 1-5% of one core, about 30 MB of memory. A full day is about 4 million rows, roughly 15 to 20 MB gzipped (MEASURED on the backfill so far), far under 1 GB.
- **Backfill:** each round moves every light and layer forward two hours, and takes about 5 minutes, so catching up on nine days takes about 9 hours. The oldest hours of history will expire before they are read. After that it polls every 10 minutes.

## First numbers

Source: the 44 lights read so far (1,052 lane connections), mostly Sat 24 Oct to Mon 26 Oct 2026 only, so **weekday rows are one Monday and mostly one light between 11:00 and 19:00**. Cycle = spacing of green starts per connection, kept if 20 to 300 s. Green share = green (plus flashing green) time over that cycle. Script: `scripts-26/cycles_by_hour.py`. Rerun after the week is complete.

| Local hour, day type | Cycle median, s | Cycle p10 to p90, s | Median within-connection spread (IQR), s | Green share p10 / p50 / p90 |
|---|---|---|---|---|
| 00-05, any day | 75 | 60 to 85 | 0 to 4 | 0.15 / 0.30 / 0.52 |
| 06, weekday | 74 | 60 to 92 | 11 | 0.16 / 0.32 / 0.53 |
| 07-19, weekday | 90 | 73 to 110 (up to 117 at 19:00) | 11 to 31 | 0.15 / 0.31 / 0.58 to 0.61 |
| 20-23, weekday | 75 | 60 to 90 | 4 to 10 | 0.15 / 0.31 / 0.53 |
| 07-19, weekend | 75 | 60 to 90 | 4 to 15 | 0.15 / 0.32 / 0.52 |

What it says (MEASURED, thin sample): the cycle is a clock schedule, **75 s at night and on weekends, 90 s from 07:00 to 20:00 on weekdays**, which matches the earlier one-Friday result in report 11 (median 90, p10 to p90 75 to 150). The spread inside one connection rises from near zero at night to 11 to 31 s by day, so by day many connections skip or extend phases (actuation) rather than run a fixed cycle. Green share barely moves by hour; the daytime change is a longer upper tail.

## Open count or speed data for the same junctions

- **Detectors in this feed:** `detector_car` streams are "signal change request" events, not vehicle counts (report 13). No speed.
- **Live traffic state (opened):** WFS `https://geodienste.hamburg.de/wfs_hh_verkehrslage` returns road segments with `zustandsklasse` (words such as "dicht"), `zeitstempel_utc`, `strassenklasse`; refreshed every 5 minutes. Four classes, not speeds, and the service keeps no history, so it would need its own collector. It is a candidate for one, not part of this job. Licence dl-de-by-2.0 in the portal record.
- **Counts (opened):** WFS `HH_WFS_Verkehrsmengen` lists only annual averages: `verkehrsmengen_dtv_hvs_2019`, `dtv_bab_2019`, `dtvw_hvs_2014`, `dtvw_bab_2013`. Modelled from the city's traffic model, not measured per junction and with no time of day (portal text, not checked further).
- **Permanent counters:** the portal's "Dauerzählstellen" hits I opened were bicycle counters.
- I did not find per-junction hourly car counts or speeds. Not verified: any separate loop-detector feed behind a request.

Nobody was contacted.
