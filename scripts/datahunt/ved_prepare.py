"""Streams VED weekly CSVs into one compact point file with one row per distinct GPS fix."""
import csv, glob, gzip, sys, os
src, out = sys.argv[1:3]
w = gzip.open(out, "wt", compresslevel=3); w.write("veh,trip,day,t_s,lat,lon,kmh\n")
nrow = nout = 0; lat_min=lon_min=1e9; lat_max=lon_max=-1e9
vehs=set(); trips=set()
for f in sorted(glob.glob(os.path.join(src, "*.csv"))):
    with open(f, newline="") as h:
        r = csv.reader(h); next(r); last=None
        for row in r:
            nrow += 1
            key=(row[1],row[2],row[4],row[5])
            if key==last: continue
            last=key
            lat,lon=float(row[4]),float(row[5])
            lat_min=min(lat_min,lat);lat_max=max(lat_max,lat);lon_min=min(lon_min,lon);lon_max=max(lon_max,lon)
            vehs.add(row[1]); trips.add((row[1],row[2]))
            w.write(f"{row[1]},{row[2]},{row[0]},{float(row[3])/1000:.1f},{row[4]},{row[5]},{row[6]}\n"); nout+=1
    print(os.path.basename(f), nrow, nout, flush=True)
w.close()
print("rows",nrow,"fixes",nout,"vehicles",len(vehs),"trips",len(trips),"bbox",lat_min,lon_min,lat_max,lon_max)
