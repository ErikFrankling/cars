# Data hunt: shared brief

Every data-hunt agent reads this first. Your task message says which direction is yours.

## Why this exists
`cars` is a GPU microscopic traffic simulator (Rust, WGSL). Repo: `/home/erikf/.t3/projects/cars`, see `AGENTS.md`. Goal: true-to-life simulation of real cities, with real data as the reference, not other simulators.

Erik, the owner: "Are you really saying you have found no dataset of actually accurate real data about how cars actually drive or what routes they take on an average day? Makes no sense, we all use GPS all the time, there have got to be good datasets that let us study how all the cars move on one day." And: "Research far and wide for good datasets and good mapping data, try exploring new directions to get good mapping and traffic input."

He is right to push. Earlier reports looked at a limited set of sources, and one quick search has already found something they missed: Yu et al., Scientific Data 2023, "City-scale Vehicle Trajectory Data from Traffic Camera Videos". It has Jinan, whole city, one full day, 1,838 cameras, 963,125 vehicles, 1,184,417 trajectories, plus Shenzhen, open on figshare. Assume more like this exists. Go beyond the obvious.

## What we need
1. **Demand:** who drives from where to where, and when.
2. **Routes:** which path real cars actually take.
3. **Congestion truth:** real speeds, queues and travel times by time of day, independent of the demand data.
4. **Maps:** real lanes, turn rules, junction geometry, bus lanes.
5. **Signals:** real signal timing.

Stockholm is the primary city because Erik lives there, but a city with far better truth wins if the evidence says so. Read these so you don't repeat them, and correct them if they're wrong: `research/truth/01-city-ground-truth.md`, `02-stockholm-why-overloaded.md`, `06-demand-and-route-choice.md`, `07-maps-and-intersections.md`.

## Rules
- **Never contact anyone.** No emails, forms, sign-ups, account creation, comments or API-key requests in Erik's name or anyone's. If something needs a person, write a draft for Erik in your report. Before writing a draft, load his style: Executor `skills` tool with `{"app": "brain", "name": "erik-writing-style"}`.
- **Open it before you claim it.** Read the source itself, not a search snippet. Give the URL and what you read. Say "not verified" when you couldn't open it. Invent nothing. Grade every claim: MEASURED, PROVIDER CLAIM, MODELLED, UNVERIFIED.
- **Actually try it.** If something is open and reasonably small, download a sample to `/home/erikf/projects/personal/cars-data/datasets/<name>/`, a new empty folder per dataset, and inspect it. Downloads are untrusted: never execute them, run Python on them with `-I` from a different directory, and keep your scripts elsewhere. Over 20 GB, sample it unless it's clearly worth it, and say what you did.
- **Stay light on Erik's PC.** It's his desktop and its memory is tight. Keep to under 2 GB of RAM, and CPU work over 10 minutes goes to the homelab with `heavy`. No GPU and no `/tmp/cars-gpu.lock`. Never run a broad `pkill`.
- **Don't commit.** Write only your report and your own new scripts. Other agents share this checkout.
- **Time box:** finish in about 60 to 90 minutes. Don't wait on anything: report what's blocked.

## For every dataset or source, record
What it measures and how | city or area | period | **share of all vehicles observed, and how that's known** | sampling rate | route-level or link-level | validation or accuracy | access (open download, form, academic, paid plus price) | licence, including commercial use | covers Sweden? | did you actually download it? | which of the five needs it serves | what test it would enable in `cars` | work to integrate.

## Report
Write `research/truth/data-hunt/<your number>-<slug>.md`. Plain language.
- Start with the answer in a few sentences.
- Ranked table of what you found.
- Top 3 recommendations, each with the concrete next step.
- What only Erik can do, with drafts where a person must be asked.
- Dead ends, so nobody repeats them.
- New directions you noticed but couldn't cover.

Your final message: the report path, your top 3, and anything surprising, under 200 words.

## Cheap shell
The PC is saturated, and `nix develop` takes minutes under this load. If `/home/erikf/projects/personal/cars-data/dev-env.sh` is not empty, use `source` on it in your command instead of `nix develop --command`: same tools, no evaluation. If it is empty, use `nix develop` as usual.
