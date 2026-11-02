#!/usr/bin/env python3
"""Keep the vehicles of a route file that depart in [BEGIN, END). usage: window.py SRC DST BEGIN END"""
import re,sys
src,dst,a,b=sys.argv[1],sys.argv[2],float(sys.argv[3]),float(sys.argv[4])
pat=re.compile(r'depart="([0-9.]+)"')
n=0
with open(src) as f, open(dst,'w') as o:
    for line in f:
        m=pat.search(line)
        if m:
            t=float(m.group(1))
            if t<a or t>=b: continue
            n+=1
        o.write(line)
print(dst,n)
