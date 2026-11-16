#!/usr/bin/env bash
# City videos: Berlin and Stockholm. One at a time; each holds the GPU lock while it runs.
cd "$(dirname "$0")/.." || exit 1
BIN=/tmp/cars-video
cp target/release/cars $BIN
D=/home/erikf/projects/personal/cars-data
V=$D/videos
B="--net $D/best/berlin.net.xml --routes $D/best/berlin.rou.gz --dt 1 --time-to-teleport 120 --ignore-junction-blocker 20 --capacity 300000 --fps 30 --width 1920 --height 1080"
S="--net $D/stockholm/stockholm.net.xml --routes $D/stockholm/stockholm60.rou.gz --dt 1 --time-to-teleport 120 --ignore-junction-blocker 20 --capacity 300000 --fps 30 --width 1920 --height 1080"
rec() { echo "== $1"; shift; flock /tmp/cars-gpu.lock $BIN record "$@" 2>&1 | tail -1 | cut -c1-160; }
rec berlin_day $B --begin 0 --end 86400 --steps-per-frame 48 --camera results/videos/berlin_day.json --out $V/berlin_day.mp4 --title 'Berlin, one working day' --subtitle 'BeST scenario, 2.25 million car trips, GPU simulation'
rec berlin_zoom $B --sim-begin 21600 --begin 27000 --end 29000 --steps-per-frame 2 --camera results/videos/berlin_zoom.json --out $V/berlin_zoom.mp4 --title 'From the whole city to one roundabout' --subtitle 'Every car in Berlin is moving while we zoom'
rec berlin_hero $B --sim-begin 21600 --begin 27900 --end 27960 --realtime --speed 2 --camera results/videos/berlin_hero.json --out $V/readme/berlin_hero.mp4 --title 'Berlin, every car at once' --subtitle 'BeST scenario: 2.25 million car trips a day, simulated on one GPU'
rec berlin_wait $B --sim-begin 21600 --begin 28800 --end 30600 --steps-per-frame 2 --color wait --fit --out $V/berlin_wait.mp4 --title 'Where Berlin waits at 08:00' --subtitle 'Red: stopped for a minute or more'
rec berlin_a100 $B --sim-begin 21600 --begin 27000 --end 28800 --steps-per-frame 2 --camera results/videos/berlin_a100.json --out $V/berlin_a100.mp4 --title 'A motorway on-ramp at the morning peak' --subtitle 'Zipper merge, 1100 cars per hour from two lanes'
rec stockholm_day $S --begin 0 --end 86400 --steps-per-frame 72 --fit --out $V/stockholm_day.mp4 --title 'Stockholm: an estimated weekday' --subtitle 'Demand fitted to city traffic counts | OpenStreetMap contributors'
rec stockholm_slussen $S --sim-begin 21600 --begin 27000 --end 28200 --steps-per-frame 1 --camera $D/stockholm/slussen.camera.json --out $V/stockholm_slussen.mp4 --title 'Slussen: estimated morning traffic' --subtitle 'Count fitted demand, not observed journeys | OpenStreetMap contributors'
