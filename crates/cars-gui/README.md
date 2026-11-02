# cars-gui

A window onto the simulator. Pick a scenario, set its variables, fly around while it runs.

```sh
scripts/cars-gui.sh
```

Run that from anywhere. The first time it builds the app, which takes a while. A small crossroads opens and starts driving straight away.

To start somewhere else:

```sh
scripts/cars-gui.sh --scenario phantom-jam
scripts/cars-gui.sh --scenario stockholm-new --speed 0
```

`--speed 0` means as fast as possible. `--help` lists the rest.

## How far to trust what you see

Every scenario has a label, in the list on the left and along the bottom of the window. It comes from the validation gate, `research/truth/VALIDATION-GATE.md`.

| Label | Meaning |
|---|---|
| matches a real day | Passed every check of the gate against a real measured day. |
| partly checked | Passed some of them. The note says which. |
| not checked against reality | A real place, never compared with a real measured day. |
| speed benchmark only | It can't pass: made-up roads, or demand known to be far off. Good for measuring speed. |

Today nothing is above the last two. Hover over a label to see why it has that label.

Runs start human-only. Automated cars are under their own heading with the label beside them, because no automated result counts until a human-only run passes the gate.

## The window

- **Left:** scenarios and variables.
- **Middle:** the map.
- **Right:** what you clicked, colours, live numbers and charts, overlays, and a junction list.
- **Top:** time and speed, colouring, camera, screenshot, clip.
- **Bottom:** which scenario is running, its label, who is driving, how long it took to load.

Press `Tab` to hide the panels and see only the map.

## Moving around

| Do this | To |
|---|---|
| Drag | Move the map |
| Wheel or pinch | Zoom around the pointer, from the whole city to one car |
| `W` `A` `S` `D` or arrows | Fly. Hold `Shift` to go faster |
| `+` `-` | Zoom at the middle of the view |
| `F` or `Home`, or **Fit map** | See the whole map |
| Double click | Zoom in on that spot |

Far out, roads are thin lines and cars are glowing dots. Below about 0.6 metres per pixel it fades into the real road: asphalt, lane markings, arrows, stop lines, signs, signal heads, and cars with lamps and indicators. The current zoom is at the top, and a scale bar is in the corner.

**Jump to a junction**, on the right, lists junctions biggest first. Type part of an id or a kind such as `signal` or `roundabout`, then click one to go there.

## Running time

| Do this | To |
|---|---|
| `Space` or **Play/Pause** | Pause or play |
| `.` or **Step** | One simulation step |
| Speed slider, `[` `]` | Slow motion up to 2000 times real time |
| `\` or **Fastest** | As fast as the card goes, with the window kept smooth |
| **Go to**, write `08:00` | Run quickly to that time of day |

Beside the clock you see how many times faster than real time it is really running, in steps per second and vehicle updates per second.

Going to an earlier time restarts the run, since the simulation only runs forwards.

## Variables

Change them on the left. A change takes effect when you press **Restart to apply**, which also lists what you changed. The camera stays where it is.

- **Demand:** 100% is the scenario's own trips. Below that a subset is kept. Above it, trips are copied, as SUMO's `--scale` does.
- **Step size:** seconds per simulation step.
- **Seed:** the same seed gives the same choice of trips.
- **Teleports:** whether a stuck car gets moved on, and after how long. With it off, gridlock stays gridlock.
- **Automated cars**, closed by default:
  - **Model:** which automated driver. Models that are not merged yet are listed in grey.
  - **Humans:** the share of cars driven by humans. Only ordinary cars change model; buses and lorries stay as they are.
  - With **D8 coordinated junctions**, every car is automated, because this build has no mixed mode. You also get **Junctions** (signal-free, or the coordinator's own signals as the baseline), **Planning** (off, full, route), **Message loss** and **Safety level** (A, or the stricter B). Use a step of 0.1 s with it.

## Looking at things

**Colour by:** speed, waiting, vehicle type, braking, or paint, which gives each car its own colour. Keys `1` to `5`. The right panel explains the colours. **Brake lights far out** makes braking cars show red even as dots; close up they always show their lamps.

**Click a car** to see its speed, acceleration, model, lane, time lost, leader and gap, and what is next on its route, which is drawn on the map. **Follow** or `G` keeps the camera on it. `Esc` lets go.

**Click a junction** to see its type, its size and each signal's live colours and next switch. With coordinated junctions you also see how many cars hold firm slots, are on advice, are in the box or have lost a grant.

**Overlays**, on the right:

- **Leader links:** who follows whom, and the gap.
- **Stopping distance:** where the car can stop, with a red tick for an emergency stop.
- **Speed labels:** km/h.
- **What each driver decided:** WAIT, GO or APPR, and metres to the link.
- **Foes at junctions:** who a car has to watch, and where the paths cross.
- **Events:** a red marker at teleports, collisions and overlaps, with a clickable list of the latest.

These need D8 coordinated junctions:

- **Grants and slot chart:** firm slots, speed advice, lost grants, and the live chart of who has the junction when.
- **Planned paths:** paths through the box, wide where a crossing foe needs the road too.
- **Who talks to whom:** the coordinator and the messages to it.
- **Broadcast arrivals:** each car's arrival to the millisecond, and a chart of slots 30 s ahead.
- **Brake totals:** a red tail on braking cars, with stops, hard brakes and energy thrown away.

Overlays have to read cars back from the graphics card. On a big map that is a large copy, so they update less often there, draw at most 700 cars, and wait until you zoom in.

**Live numbers** are vehicles running, mean speed, arrivals, teleports, collisions, cars stuck for over two minutes, standing and braking, with charts over simulated time. Hover a chart to read a value. These cost the simulation almost nothing.

## Keeping what you see

`P` or **Screenshot** saves a picture. `R` or **Record clip** starts a video and pressing it again stops it. Both go to `~/Videos/cars-gui`, and the window says where. They include your overlays, a scale bar, and the scenario's trust label.

## When something is wrong

Problems appear in the window. A missing file is named with its full path. If a big scenario needs more memory than is free, it says so and offers **Load anyway**; that check keeps 3 GB of graphics memory for the desktop. The window stays alive through a failed load, and the last scenario keeps running until the new one is ready for the card.

## Opening your own files

**Open any net and route file…**, under the scenario list, takes a `.net.xml`, route files and additional files, typed or browsed. They are labelled "not checked against reality".

## Adding a scenario

Add an entry to `crates/cars-gui/registry.toml`. It is read at every start, so no rebuild is needed.

```toml
[[scenario]]
id = "jinan"
name = "Jinan"
group = "Cities"
description = "Shown when you hover over it."
trust = "not_checked"
trust_note = "Why it has this label."
net = "$DATA/jinan/jinan.net.xml"
routes = ["$DATA/jinan/jinan.rou.gz"]
dt = 1.0
begin = 25200.0
end = 43200.0
capacity = 200000
```

`trust` is required. Move a scenario up only with the gate's evidence. `generate` is a command that builds missing files, see the test roads.

## Lighting up a model

When a model's branch merges, find its `[[model]]` entry in the same file. Set `status = "merged"` and give it a `vtype`: one `<vType>` with `id="gui_av"`. Add `coordinated = true` if it runs the signal-free coordinator.

## Good to know

- The simulation is the same one `cars run` uses. Nothing here changes a kernel, and a human-only run at 100% demand builds its world the same way.
- The app does not take `/tmp/cars-gpu.lock`. It keeps its GPU work in short pieces and shares the card, so heavy jobs from others will lower its frame rate.
- Set `CARS_ADAPTER=llvmpipe` to run without the graphics card, `CARS_DATA` and `CARS_THESIS` if your data lives elsewhere.
- `--perf-log file` writes frame times and speed once a second. `--quit-after seconds` ends the run, for measuring.
