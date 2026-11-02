#!/usr/bin/env python3
"""Thesis ring, p=1 per tier: mean and spread of detector speed in time windows around the perturbation."""
import importlib.util, os, sys, tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
here = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("audit", here / "10_thesis_audit.py")
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
WIN = ((1000, 2000), (2000, 2400), (2400, 3000), (3000, 4000))
CASES = (("human", "acc", 0.0, ""), ("krauss", "krauss", 1.0, ""), ("idm", "idm", 1.0, ""), ("acc", "acc", 1.0, ""), ("cacc", "cacc", 1.0, ""),
         ("waymo_fit", "idm", 1.0, "tau=1.32;minGap=4.05;speedDev=0;accel=2.6;decel=2.0"))
print("label,tier,window,mean_speed,sd_all,sd_between_detector_means,min_speed", flush=True)
for label, tier, p, variant in CASES:
    with tempfile.TemporaryDirectory(prefix="ring-") as tmp:
        tmp = Path(tmp)
        routes, adds = a.prepare_routes("ring", tier, p, 0, tmp)
        adds = [a.patched_vtypes(x, tier, variant, tmp / "vtypes.xml") if x.name == "vtypes.xml" else x for x in adds]
        det = tmp / "det.xml"
        (tmp / "m.add.xml").write_text("<additionals>" + "".join(f'<inductionLoop id="d{i}" lane="e{i}_0" pos="25" period="50" file="{det}"/>' for i in range(80)) + "</additionals>")
        adds.append(tmp / "m.add.xml")
        config, _, _, end = a.scenario_files("ring")
        a.run_ring(["sumo", "-c", str(config), "--route-files", ",".join(map(str, routes)), "--additional-files", ",".join(map(str, adds)),
                    "--seed", "0", "--no-step-log", "true", "--no-warnings", "true"], end)
        rows = [(float(x.get("begin")), x.get("id"), float(x.get("speed"))) for x in ET.parse(det).getroot().findall("interval") if float(x.get("speed")) >= 0]
    for lo, hi in WIN:
        sp = [s for t, _, s in rows if lo <= t < hi]
        m = sum(sp) / len(sp)
        print(f"{label},{tier},{lo}-{hi},{m:.3f},{(sum((s-m)**2 for s in sp)/len(sp))**.5:.3f},,{min(sp):.2f}", flush=True)
