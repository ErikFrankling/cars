from pathlib import Path
import csv,shutil,re
root=Path(__file__).resolve().parents[1];out=root/'results/phenomena'
for d in (root/'runs/phenomena').iterdir():
 if (d/'manifest.json').exists():shutil.copy(d/'manifest.json',out/(d.name+'_manifest.json'))
for d in (root/'runs/phenomena').iterdir():
 if (d/'cars.log').exists():
  m=re.search(r'lane changes (\d+), teleports (\d+), collisions (\d+)(?: \([^)]*\))?, overflow (\d+), items full (\d+)',(d/'cars.log').read_text())
  if m:
   with (out/(d.name+'_diagnostics.csv')).open('w') as f:
    w=csv.writer(f,lineterminator='\n');w.writerow(['lane_changes','teleports','collisions','overflow_counter','items_full']);w.writerow(m.groups())
text='''# Traffic phenomena measurements

This suite remains incomplete. A completed recording is not evidence that its named phenomenon occurred. See the explicit failures below.

Reproduce inside `nix develop`: `python scripts/phenomena.py SCENARIO --measure --seed 42` (repeat with 43 and 44), then `--video`. GPU commands acquire `/tmp/cars-gpu.lock`. Generate run traces with `python scripts/phenomena_spread.py`, and lane-drop detector diagnostics with `python scripts/phenomena_capacity.py`. Raw outputs are under `runs/phenomena/`; videos are outside git.

Decisions made in this pass:

- Phantom jam uses 22 IDM drivers on a 330 m ring, accel 0.3 m/s², decel 1.5 m/s², tau 1 s, maximum speed 8.333 m/s, stopped initial insertion, and v0 shifted forward 3 m. No continuing obstacle or forced braking. The 230 m Krauss baseline and a 330 m low-acceleration Krauss trial did not develop waves. An exactly symmetric IDM start stayed symmetric; a position perturbation was necessary. This is a synthetic unstable IDM example, not a calibration to Sugiyama's human experiment.
- Ring runs last 1800 s; wave measurements exclude the first 600 s. Time-space panels use both engines with a shared speed scale. Wave speed maximizes spatial correlation between adjacent 10 s speed fields with 66 periodic spatial bins, searching shifts in both directions. Resolution is 1.8 km/h for the 330 m ring; this is an exploratory estimate, not a front-fit confidence interval. Stopped means speed below 0.5 m/s. Trajectory CSVs retain every fifth row to keep files small; wave analysis and figures use the full snapshots.
- Seeds are independent engine seeds, not synchronized noise realizations. IDM is deterministic here, so repeated ring seeds give identical outcomes and do not establish uncertainty over human driver parameters. Other scenarios retain Krauss sigma 0.5. Explicit departure schedules are shared.
- Thesis generators now load actual bachelor/config networks and demand, with human vTypes, rather than raising NotImplementedError. They are human baselines. The ring thesis disturbance is still absent: existing shader F_SCRIPTED uses Params.script_t0, a 60 s cap and 300 s recovery; merely loading the route does not enable it. The I-80 baseline here uses dt 0.1 s in both engines rather than sweep.rs’s 1 s. SUMO reports speed-factor adjustments for departures faster than the sampled type permits; identical XML does not guarantee identical speed-factor handling. No shader files were changed.
- Recorder uses software libx264, two encoder/decoder/filter threads and the veryfast preset. All videos are 1920×1080; ordinary recordings are approximately 40 s. Signal discharge records only 0–90 simulation seconds (30 s video), because its forty-car initial queue empties long before the measurement ends. Cameras are saved in `cameras/`. Videos show cars only, not a SUMO replay.

Interval observations use 30 s Edie measurements: density = vehicle seconds / (30 × lane length); flow = distance / (30 × lane length). Production = total distance / 30, excluding internal edges. Empty edges stay in the geometry denominator. Edge accumulation includes boundary overlap in SUMO and can exceed physical counts. The spread plots retain each seed separately; MFD loading is the first half of the demand schedule and recovery the second, using solid and dashed lines. These labels do not establish a hysteresis effect.

| Scenario | Requested phenomenon demonstrated, SUMO / cars | seeds with paired results | Mean speed SUMO (m/s), seed 42 | Mean speed cars (m/s), seed 42 |
|---|---|---|---:|---:|
'''
for p in sorted(out.glob('*_summary.csv')):
 name=p.stem.removesuffix('_summary')
 if '_seed' in name or name=='run':continue
 with p.open() as f:r={x['simulator']:x for x in csv.DictReader(f)}
 if 'SUMO' not in r:continue
 seeds=['42']+[str(s) for s in [43,44] if (out/f'{name}_seed{s}_summary.csv').exists()]
 shown='Yes / Yes' if name in ['phantom_jam','signal_discharge','onramp_merge','bologna_rush','i80_day','mfd'] else 'No / No'
 text+=f"| {name} | {shown} | {', '.join(seeds)} | {float(r['SUMO']['space_mean_speed_m_s']):.3f} | {float(r['cars']['space_mean_speed_m_s']):.3f} |\n"
text+='\nHere No means the requested behavior is absent or not demonstrated by the available measurements. Yes for Bologna and I-80 refers to baseline rush/corridor traffic, and for MFD to loading/recovery, not controller equivalence or proven hysteresis.\n\nRing wave results:\n\n| Engine | Stopped fraction | Speed SD (m/s) | Backward wave (km/h) |\n|---|---:|---:|---:|\n'
for r in csv.DictReader((out/'phantom_jam_waves.csv').open()):text+=f"| {r['simulator']} | {float(r['stopped_fraction']):.3f} | {float(r['speed_sd_m_s']):.3f} | {float(r['wave_km_h']):.1f} |\n"
text+='''
The ring waves agree across engines but propagate substantially slower than the −15 to −20 km/h literature target. This is not a successful match to that empirical range.

Outstanding requirements and failed checks:

- one_av still uses its earlier static long-headway vehicle. There is no switch-on experiment or verified damping result.
- brake_wave still has a persistent slow section. It is not a lead-car brake pulse; amplitude by vehicle index is absent.
- capacity_drop has no sustained breakdown in any of the three seeds in either engine (upstream speed below 15 m/s for three consecutive 30 s bins). Detector CSV leaves pre/post/drop blank; no numerical drop is manufactured. The diagnostic uses downstream edge-entry counts, a 300 s prewindow and 600 s postwindow after 60 s transition exclusion when breakdown exists.
- freeway_fd does not demonstrate a congested branch at the offered demand. No fitted congested branch is claimed.
- signal_discharge shows queue release but queue-position headways and saturation-flow estimates are missing.
- spillback lacks blocked-green time and spillback-extent measurements.
- gridlock lacks with/without keep-clear interventions. Grid loading is not proof of cyclic deadlock.
- MFD run traces distinguish loading and recovery; equal-accumulation branch inference and uncertainty remain absent.
- The thesis scenarios have no verified videos or disturbance/controller comparison.
- Existing overflow counters are nonzero in gridlock, MFD and on-ramp runs. These are simulator diagnostics needing investigation; no fix was attempted in shaders. Paired results remain provisional.

Video inventory (frames extracted at 20 s and visually inspected; visual framing does not validate the phenomenon):

'''
for name in ['phantom_jam','one_av','brake_wave','capacity_drop','freeway_fd','signal_discharge','onramp_merge','spillback','gridlock','mfd']:
 p=Path('/home/erikf/projects/personal/cars-data/videos')/(name+'.mp4')
 if p.exists():text+=f'- `{p}`\n'
text+='\nGPU diagnostics:\n\n| Run | Overflow events | Collisions | Teleports |\n|---|---:|---:|---:|\n'
for p in sorted(out.glob('*_diagnostics.csv')):
 with p.open() as f:r=next(csv.DictReader(f))
 text+=f"| {p.stem.removesuffix('_diagnostics')} | {r['overflow_counter']} | {r['collisions']} | {r['teleports']} |\n"
(out/'README.md').write_text(text)
