# Rounds on the physical driver

One line per round: what changed, what moved. Benchmark is `bench.py run --driver physics --mode fast`. "Cut" is 05:00-07:00 at 50% around Ernst-Reuter-Platz (`cars cut`), 8,097 trips, arrived / stuck / contacts, two seeds; the old driver with teleports off arrives 7,500.

| Round | Change | Cut | Benchmark | Note |
|---|---|---|---|---|
| 0 | Report 19 fixes, merged | 2,469-2,515 / 1,991-2,052 / 49-79 | 30 fail, 14 at floor | Level 0 at floor |
| 1 | Hold point past the car's tail | 3,605-3,802 / 1,164-1,485 / 206-245 | | Cars were stopped by LC2013 with the tail still on the lane before, where a change can't start: a deadlock with itself |
| 2 | Lane-change requests lapse after 10 s; hold past the certificate margin; a stopped car may start a change needing a second | 5,486-5,571 / 679-776 / 416-535 | 32 fail, 13 at floor | V2 failed: 5 contacts at 0.19 m between opposing left turns, from the zone rule, not the holds |
| 3 | Opposing lanes of real width keep their zone; critical gaps × 0.7; 30 m view of a give-way line; dawdling 0.2 | 5,325-5,354 / 693-806 / 318-410 before the give-way part | 31 fail, 15 at floor, V2 back at floor, JP1 10.0 to 7.1 | Minor capacity 261/171 to 504/324 against Siegloch 736/451. Saturation 1,714 to 1,846 |

Tried without gain:
- `lc_strategic` 4: arrivals up 6% on the cut, stuck the same. Not adopted.
- Lateral speed tied to real steering at low speed: locks the cut, 650-1,160 arrivals. See below.
- `tau` 1.2 with `leader_b` 3: saturation down, motorway the same.
