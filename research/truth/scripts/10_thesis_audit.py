#!/usr/bin/env python3
"""Re-run thesis SUMO cases with the safety ledger the thesis pipeline dropped.

Reads the thesis repo, never writes to it. Prints one CSV row per case.
Case: scenario,tier,p,seed,variant,step,collision_action
variant: empty, or attr=value;attr=value applied to the tier's vType.
"""
import argparse, csv, os, subprocess, sys, tempfile, time
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

THESIS = Path(os.environ.get("THESIS", "/home/erikf/projects/personal/thesis-src/bachelor"))
sys.path.insert(0, str(THESIS / "scripts"))
sys.dont_write_bytecode = True
from experiment import TIER_TYPES  # noqa: E402
from prepare_routes import prepare_routes, scenario_files  # noqa: E402

TIER_TYPES = dict(TIER_TYPES, human="human")
FIELDS = ("scenario tier p seed variant step collision_action wall_s loaded inserted running waiting "
          "completed travel_time waiting_time time_loss route_length speed_tripmean depart_delay "
          "tele_total tele_jam tele_yield tele_wronglane collisions emergency_stops emergency_braking "
          "mean_speed_summary running_mean edge_flow_mean veh_km_edge speed_post2000 speed_sd_post2100 min_speed_post2100").split()


def patched_vtypes(path, tier, variant, out):
    tree = ET.parse(path)
    for vt in tree.getroot().findall("vType"):
        if vt.get("id") == TIER_TYPES[tier]:
            for kv in filter(None, variant.split(";")):
                k, v = kv.split("=")
                if k.startswith("param:"):
                    for p in vt.findall("param"):
                        if p.get("key") == k[6:]:
                            p.set("value", v)
                else:
                    vt.set(k, v)
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return out


def run_ring(cmd, end_time):
    import contextlib, io
    sys.path.insert(0, os.path.join(os.environ["SUMO_HOME"], "tools"))
    import traci
    with contextlib.redirect_stdout(io.StringIO()):
        traci.start(cmd)
    try:
        capped = restoring = False
        original = cap = None
        while traci.simulation.getTime() < end_time and traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            t = traci.simulation.getTime()
            if "v0" not in traci.vehicle.getIDList():
                continue
            if not capped and t >= 2000:
                original = traci.vehicle.getMaxSpeed("v0")
                cap = min(original, max(5, traci.vehicle.getSpeed("v0") - 5))
                traci.vehicle.setMaxSpeed("v0", cap)
                capped = True
            if capped and not restoring and t >= 2060:
                restoring = True
            if restoring:
                traci.vehicle.setMaxSpeed("v0", cap + (original - cap) * min(1, (t - 2060) / 300))
    finally:
        traci.close()


def mean(x):
    x = list(x)
    return sum(x) / len(x) if x else float("nan")


def one(case):
    scenario, tier, p, seed, variant, step, action = case
    t0 = time.time()
    row = dict(zip(FIELDS[:7], case))
    with tempfile.TemporaryDirectory(prefix="ta-") as tmp:
        tmp = Path(tmp)
        routes, adds = prepare_routes(scenario, "acc" if tier == "human" else tier, float(p) if tier != "human" else 0.0, int(seed), tmp)
        if tier == "human" and float(p) > 0:
            # variant of the human type driven by every car: routes already all human
            pass
        adds = [patched_vtypes(a, tier, variant, tmp / "vtypes.xml") if a.name == "vtypes.xml" else a for a in adds]
        edge, det, trip, summ, stat = (tmp / f"{n}.xml" for n in ("edge", "det", "trip", "summary", "stat"))
        lines = ["<additionals>", f'<edgeData id="edge_flow" file="{edge}" freq="60" excludeEmpty="false"/>']
        if scenario == "ring":
            lines += [f'<inductionLoop id="d{i}" lane="e{i}_0" pos="25" period="50" file="{det}"/>' for i in range(80)]
        (tmp / "m.add.xml").write_text("\n".join(lines + ["</additionals>"]))
        adds.append(tmp / "m.add.xml")
        config, _, _, end_time = scenario_files(scenario)
        cmd = ["sumo", "-c", str(config), "--route-files", ",".join(map(str, routes)),
               "--additional-files", ",".join(map(str, adds)), "--tripinfo-output", str(trip),
               "--summary-output", str(summ), "--statistic-output", str(stat), "--seed", str(seed),
               "--no-step-log", "true", "--no-warnings", "true"]
        if step:
            cmd += ["--step-length", str(step)]
        if action:
            cmd += ["--collision.action", action]
        if scenario == "ring":
            run_ring(cmd, end_time)
        else:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        s = ET.parse(stat).getroot()
        v, te, sa, vt = (s.find(k) for k in ("vehicles", "teleports", "safety", "vehicleTripStatistics"))
        row.update(loaded=v.get("loaded"), inserted=v.get("inserted"), running=v.get("running"), waiting=v.get("waiting"),
                   tele_total=te.get("total"), tele_jam=te.get("jam"), tele_yield=te.get("yield"), tele_wronglane=te.get("wrongLane"),
                   collisions=sa.get("collisions"), emergency_stops=sa.get("emergencyStops"), emergency_braking=sa.get("emergencyBraking"),
                   route_length=vt.get("routeLength"), speed_tripmean=vt.get("speed"), depart_delay=vt.get("departDelay"))
        trips = ET.parse(trip).getroot().findall("tripinfo")
        row.update(completed=len(trips),
                   travel_time=mean(float(x.get("duration")) for x in trips),
                   waiting_time=mean(float(x.get("waitingTime")) for x in trips),
                   time_loss=mean(float(x.get("timeLoss")) for x in trips))
        steps = [x for x in ET.parse(summ).getroot().findall("step") if float(x.get("running", 0)) > 0 and float(x.get("meanSpeed", 0)) >= 0]
        row.update(mean_speed_summary=mean(float(x.get("meanSpeed")) for x in steps),
                   running_mean=mean(float(x.get("running")) for x in steps),
                   speed_post2000=mean(float(x.get("meanSpeed")) for x in steps if float(x.get("time")) >= 2000))
        flows = []
        vkm = 0.0
        for _, el in ET.iterparse(edge, events=("end",)):
            if el.tag == "edge":
                f = float(el.get("flow", "nan"))
                if f == f:
                    flows.append(f)
                vkm += float(el.get("sampledSeconds", 0)) * float(el.get("speed", 0)) / 1000.0
            el.clear()
        row.update(edge_flow_mean=mean(flows), veh_km_edge=vkm)
        if scenario == "ring" and det.exists():
            sp = [float(x.get("speed")) for x in ET.parse(det).getroot().findall("interval")
                  if float(x.get("begin")) >= 2100 and float(x.get("speed")) >= 0]
            m = mean(sp)
            row.update(speed_sd_post2100=(mean((a - m) ** 2 for a in sp)) ** .5 if sp else "", min_speed_post2100=min(sp) if sp else "")
    row["wall_s"] = round(time.time() - t0, 1)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("out")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    cases = [tuple((l.rstrip("\n").split(",") + [""] * 7)[:7]) for l in open(a.cases) if l.strip() and not l.startswith("#")]
    new = not Path(a.out).exists()
    done = set()
    if not new:
        done = {tuple(r[k] for k in FIELDS[:7]) for r in csv.DictReader(open(a.out))}
    cases = [c for c in cases if c not in done]
    with open(a.out, "a", newline="") as fh, ProcessPoolExecutor(a.jobs) as pool:
        w = csv.DictWriter(fh, FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        futs = {pool.submit(one, c): c for c in cases}
        for f in as_completed(futs):
            try:
                w.writerow(f.result()); fh.flush()
                print("done", futs[f], flush=True)
            except Exception as e:
                print("FAILED", futs[f], repr(e), flush=True)


if __name__ == "__main__":
    main()
