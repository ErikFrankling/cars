#!/usr/bin/env bash
# The whole of Berlin for 24 hours on the GPU.
cd /home/erikf/.t3/projects/cars
exec nix develop --command /tmp/cars-berlin run --net /home/erikf/projects/personal/cars-data/best/berlin.net.xml --routes /home/erikf/projects/personal/cars-data/best/berlin.rou.gz --dt 1 --begin 0 --end 86400 --time-to-teleport 120 --ignore-junction-blocker 20 --capacity 600000 --trusted --summary-csv runs/berlin/day_summary.csv --edge-csv runs/berlin/day_edges.csv --edge-interval 3600 --trip-csv runs/berlin/day_trips.csv
