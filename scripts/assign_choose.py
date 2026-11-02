#!/usr/bin/env python3
"""Which run to open the test rows on: lowest selection-row WAPE, from an evaluation or a calibration round.
No test row is read. usage: assign_choose.py BASE_RUN CAL_RUN [CAL_RUN ...]  prints the chosen run directory."""
import json, os, sys

best = None
base = json.load(open(os.path.join(sys.argv[1], "eval_unseen4.json")))
errs = [s["errors"]["selection"]["wape"] for s in base["seeds"]]
scores = [(sum(errs) / len(errs), sys.argv[1], "uncalibrated")]
for d in sys.argv[2:]:
    p = os.path.join(d, "calibration.json")
    if os.path.exists(p):
        rounds = json.load(open(p))["rounds"]
        if rounds:
            scores.append((min(r["selection_wape"] for r in rounds), d, "calibrated"))
scores.sort()
print(json.dumps(scores), file=sys.stderr)
print(scores[0][1])
