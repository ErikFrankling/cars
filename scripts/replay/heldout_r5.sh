#!/usr/bin/env bash
# Round 5 held-out tests (F854-F860): round 1's harness, the round 5 law, tag r5. GPU runs take /tmp/cars-gpu.lock in rpl.run_cars.

cd "$(dirname "$0")/../.."
export F101_FLAGS='--tune measured=1' F101_COND=1
for site in I90mov HT1416 highD6; do
  extra=(); [ "$site" = highD6 ] && extra=(F101_W=100 F109_RELEASE=30,55,80)
  d=/home/erikf/projects/personal/cars-data/replay/f101; [ "$site" != I90mov ] && d=${d}_$site
  for s in 0 1 2 3 4; do [ -f $d/r5_s$s.roll.npz ] || env F101_SITE=$site "${extra[@]}" python3 -I scripts/replay/f101.py run r5 $s --gpu | tail -1; done
  env F101_SITE=$site "${extra[@]}" python3 -I scripts/replay/f101.py score | grep "^r5\|^md\b\|^onec\b\|^main\b"
  env F101_SITE=$site "${extra[@]}" python3 -I scripts/replay/f109.py run r5 0..9 --gpu | tail -1
  env F101_SITE=$site "${extra[@]}" python3 -I scripts/replay/f109.py score r5 | head -12
done
python3 -I scripts/replay/classifier.py r5_s0 md_s0 | tail -20
