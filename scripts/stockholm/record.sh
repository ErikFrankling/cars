#!/usr/bin/env bash
set -euo pipefail
data=${1:-/home/erikf/projects/personal/cars-data/stockholm}
videos=$(dirname "$data")/videos
mkdir -p "$videos"
flock /tmp/cars-gpu.lock target/release/cars record --net "$data/stockholm.net.xml" \
 --routes "$data/stockholm.rou.gz" --capacity 200000 --time-to-teleport 120 --ignore-junction-blocker 20 --dt 1 --begin 0 --end 86400 --steps-per-frame 72 \
 --fps 30 --width 1920 --height 1080 --fit --out "$videos/stockholm_day.mp4" \
 --title 'Stockholm: an estimated weekday' --subtitle 'Demand fitted to city traffic counts | OpenStreetMap contributors'
flock /tmp/cars-gpu.lock target/release/cars record --net "$data/stockholm.net.xml" \
 --routes "$data/stockholm.rou.gz" --capacity 200000 --time-to-teleport 120 --ignore-junction-blocker 20 --dt 1 --begin 25200 --end 26400 --steps-per-frame 1 \
 --fps 30 --width 1920 --height 1080 --camera "$data/slussen.camera.json" \
 --out "$videos/stockholm_slussen.mp4" --title 'Slussen: estimated morning traffic' \
 --subtitle 'Count fitted demand, not observed journeys | OpenStreetMap contributors'
ffmpeg -threads 2 -i "$videos/stockholm_day.mp4" -ss 20 -frames:v 1 -threads 2 -y "$videos/stockholm_day.png"
