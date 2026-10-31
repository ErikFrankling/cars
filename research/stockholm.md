# Stockholm scenario: incomplete preliminary network

The BBBike Stockholm extract was downloaded on 2026-10-31 from https://download.bbbike.org/osm/bbbike/Stockholm/Stockholm.osm.pbf. Its OpenStreetMap data requires ODbL attribution. It is untrusted data and was not executed. The local city WFS file contains 16,698 street segments with heterogeneous annual average weekday counts, including estimates; these are not observations of a single day.

Commands run from the repository root:

```sh
cd /home/erikf/projects/personal/cars-data/stockholm
curl -fL --retry 2 --connect-timeout 15 --max-time 120 -o Stockholm.osm.pbf https://download.bbbike.org/osm/bbbike/Stockholm/Stockholm.osm.pbf
cd /home/erikf/.t3/projects/cars
nix develop --command bash -c 'cd /home/erikf/projects/personal/cars-data/stockholm && osmium extract -b 17.75,59.20,18.25,59.45 Stockholm.osm.pbf -o clip.osm.pbf --overwrite && osmium cat clip.osm.pbf -o clip.osm.xml --overwrite && netconvert --osm-files clip.osm.xml -o stockholm.net.xml --keep-edges.by-vclass passenger --tls.guess-signals --ramps.guess --junctions.join --roundabouts.guess --geometry.remove --tls.discard-simple --remove-edges.isolated --keep-edges.components 1 --junctions.corner-detail 3 --proj.utm'
```

The preliminary net contains 73,733 external edges, 78,802 external lanes, 8,735.5 external lane-km and 488 traffic-light programs, counted from XML. Passenger-class filtering does not establish that every retained lane is passenger accessible. It has not been checked against the requested road-type restriction, visually inspected, or validated for motorway, bridge and tunnel continuity. The simulator ignores pedestrian and bicycle lanes. Netconvert warned about malformed layer values, missing restriction members, lane connections and incomplete roundabouts; these require investigation. Clipping can omit boundary relations and approaches.

No count mapping, demand, routes, hourly fit, simulation or validation was completed. Consequently no GEH, R², teleports, peak running count or trip total is available. The network must not be treated as a finished scenario. A next pass should audit road types and geometry, preserve conversion logs, map flows including directional ambiguity, generate and fit a one-hour demand first, then validate before expanding to 24 hours.
