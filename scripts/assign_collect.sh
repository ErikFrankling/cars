#!/usr/bin/env bash
# Copy what each assign run decided into results/assign and draw its convergence plot. Run inside nix develop.
# usage: assign_collect.sh RUNS_DIR
set -u
runs=$1; out=results/assign; mkdir -p "$out"
for d in "$runs"/*/; do
    n=$(basename "$d")
    [ -f "$d/iters.csv" ] || [ -f "$d/verdict.json" ] || ls "$d"eval_*.json >/dev/null 2>&1 || continue
    mkdir -p "$out/$n"
    for f in iters.csv convergence.json checks.json manifest.json verdict.json calibration.json incident.json routebench.json replicas.json test_opened.json; do
        [ -f "$d/$f" ] && cp "$d/$f" "$out/$n/"
    done
    for f in "$d"eval_*.json "$d"depart_*.json; do [ -f "$f" ] && cp "$f" "$out/$n/"; done
    [ -f "$d/iters.csv" ] && python3 -I scripts/assign_plots.py "$out/$n/convergence.png" "$d:$n"
    for c in "$d"cal_*/; do
        [ -d "$c" ] || continue
        m=$n/$(basename "$c"); mkdir -p "$out/$m"
        for f in iters.csv calibration.json test_opened.json; do [ -f "$c/$f" ] && cp "$c/$f" "$out/$m/"; done
        for f in "$c"eval_*.json; do [ -f "$f" ] && cp "$f" "$out/$m/"; done
        [ -f "$c/iters.csv" ] && python3 -I scripts/assign_plots.py "$out/$m/convergence.png" "$c:$(basename "$c")"
    done
done
python3 -I scripts/assign_plots.py "$out/control_everyone_vs_capped.png" "$runs/grid_200:capped 15%, memory 0.3" "$runs/grid_200_everyone:everyone switches"
