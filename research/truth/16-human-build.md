# The human driver on the GPU: what was built and how it measures

Date: 2026-11-01. Everything here ran on the GPU kernel unless marked **software GPU** (llvmpipe, used only for quick debugging). Raw results are in `/home/erikf/projects/personal/cars-data/truth/humans/`. Provenance of every rule and number: [`crates/cars-core/src/shaders/HUMAN.md`](../../crates/cars-core/src/shaders/HUMAN.md).

Run it with `cars run --humans`, or `carFollowModel="Human"` on a vType, in physical mode. `--human-off RULE` switches a rule off, `--tune name=value` moves a number, `--region sweden` uses Trafikverket's values. `--sumo-compat` never sees any of it.

## What changed after the review

Report 15's Part 3 was applied:

- **Gone:** the side-by-side swap, the forced yield at 90 s, the 60 s wait term, the pair hash. Courtesy and urgency have no time terms.
- **In:** stop points 5 and 12 m short of a lane end on alternate lanes (Trafikverket), Aimsun's two-leader anticipation, a cooperation share, rerouting with lost-car counts and `t_miss` as a per-driver draw, exit-clear compliance (shared with the physics branch).

## Decision on the merge model

**Lee 2006 replaces report 14's logit.** Theses read in full through the DSpace API: Lee 2006, Choudhury 2007 (ch. 5). Ahmed 1999 is scanned, so its discretionary table is taken as tabulated in Lee. Files in `cars-data/truth/practice/humans-20261101/`.

Held-out log likelihood per car, per second decisions ([merge_models.json](human-build/merge_models.json)):

| Model | I-80 later runs (420 cars) | US-101, other site (349) |
|---|---:|---:|
| Report 14's start logit, refit on I-80's first run | **−2.60** | −15.52 |
| Lee 2006, published I-80 coefficients | −5.09 | **−3.33** |
| Lee's form, refit on the same run | −4.27 | −9.21 |
| Choudhury 2007, published, as I could implement it | −11.50 | −5.39 |

- On another site Lee beats the logit by 12.2 nats per car (paired 95% CI 11.5 to 12.8). On the same site the logit wins by 2.5 (2.0 to 3.0). We run in other cities, so the transfer test decides.
- **My Choudhury result is not a fair test of his model.** He reports −2.98 per car and I get −11.5 on I-80. His density and lead acceleration are approximated, and table values come from OCR. The latent plan model is not ruled out. Lee's −5.09 is also worse than his own −3.04, for similar reasons.
- **Lee's published constants do not transfer to this kernel in closed loop.** Waits are 60 s against 22.6 s at I-80's flows. Both authors recalibrate constants per site. Shifting lead by −6 and lag by −2 in log metres passes the wait bands, but a shift that size means the certificate floor decides most acceptance, not Lee's gaps. Lee's distance form stays. His gap sizes are in practice not what binds.
- **Cooperation is a share of drivers**, as Aimsun and MITSIMLab, with no published value. 0.4 here.

## Bugs the closed loop found in report 05's spec

Report 05's queue tests started from a formed queue, so three things never showed:

1. The feedback, fitted on following moving cars, made cars crawl towards anything standing: about 1.6 m/s from 50 m. Replaced by Gipps' rule below 0.5 m/s. Replay did not change.
2. The closing guard brakes from any distance, so a car started slowing for a stop line 300 m ahead.
3. `a_t > 0.05` leaves a stopped car up to 4.5 m short for good, since `k1` is so small.

The guard also needed a change: assuming the leader can brake at b_hi held time gaps above 1.2 s at 34 m/s, against 0.8 s measured, and A39 replay error at 18.7 m against 11.3 m. The human guard now assumes the leader brakes no harder than the driver can.
