#!/usr/bin/env python3
"""List junction cameras, ranked by incoming edge samples or incoming lane count."""
import argparse
import csv
import json
import xml.etree.ElementTree as ET
from collections import defaultdict


def busiest(net, edge_csv=None):
    weights=defaultdict(float)
    if edge_csv:
        with open(edge_csv) as f:
            for r in csv.DictReader(f):weights[r['edge']]+=float(r['samples'])
    edges={};lanes={};junctions=[];roundabouts=set()
    for _,e in ET.iterparse(net,events=('end',)):
        if e.tag=='edge':
            edges[e.get('id')]=dict(e.attrib)
            for l in e.findall('lane'):lanes[l.get('id')]=e.get('id')
            e.clear()
        elif e.tag=='roundabout':roundabouts.update(e.get('edges','').split());e.clear()
        elif e.tag=='junction':junctions.append(dict(e.attrib));e.clear()
    result=[]
    for j in junctions:
        inc=j.get('incLanes','').split(); incoming={lanes.get(l,'') for l in inc};kind=j.get('type','')
        if not inc or kind in ('internal','dead_end'):continue
        if incoming & roundabouts:kind='roundabout'
        elif kind.startswith('traffic_light'):kind='signal'
        elif kind=='zipper':kind='zipper'
        elif len(incoming)>1 and any('motorway' in edges.get(e,{}).get('type','') for e in incoming):kind='ramp'
        elif kind.startswith('priority'):kind='priority'
        score=sum(weights[e] for e in incoming) if edge_csv else len(inc)
        result.append(dict(id=j['id'],type=kind,x=float(j['x']),y=float(j['y']),score=score))
    return sorted(result,key=lambda r:(-r['score'],r['id']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--net',required=True);p.add_argument('--edge-csv');p.add_argument('--type');p.add_argument('--limit',type=int,default=20);a=p.parse_args()
    print(json.dumps([r for r in busiest(a.net,a.edge_csv) if not a.type or r['type']==a.type][:a.limit],indent=2))
