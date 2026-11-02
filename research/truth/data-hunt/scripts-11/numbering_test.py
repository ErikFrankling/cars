#!/usr/bin/env python3
# Tests the handbook rule: vehicle signal groups are numbered clockwise from the west. Usage: numbering_test.py Signallykta.geojson
import sys,json,re,math,collections
L=collections.defaultdict(list);V=collections.Counter();arrow=collections.defaultdict(set);right=collections.defaultdict(set);bus=collections.defaultdict(set);maker=collections.Counter();cnt=collections.Counter()
for f in json.load(open(sys.argv[1]))['features']:
    p=f['properties'];i=str(p.get('anläggnings-id')).lstrip('0');n=p.get('namn') or '';t=p.get('typ') or '';g=f['geometry']
    m=re.search(r'\bF(\d+)(?::(\d+))?',n)
    if not m:continue
    maker[p.get('lykthus-fabrikat')]+=1
    if 'v-pil' in t:arrow[i].add(int(m.group(1)))
    if 'h-pil' in t:right[i].add(int(m.group(1)))
    if 'ollektiv' in t or 'ollektiv' in n:bus[i].add(int(m.group(1)))
    if g:L[i].append((int(m.group(1)),int(m.group(2) or 1),g['coordinates'][0],g['coordinates'][1]))
res=collections.Counter();per=[]
for i,x in L.items():
    groups=collections.defaultdict(list)
    for g,k,e,n in x:groups[g].append((k,e,n))
    if len(groups)<3:continue
    # first lantern of each group is usually the primary, at the stop line of its approach
    cx=sum(a[2] for a in x)/len(x);cy=sum(a[3] for a in x)/len(x)
    ang={}
    for g,v in groups.items():
        k,e,n=min(v);ang[g]=(math.degrees(math.atan2(e-cx,n-cy))-270)%360   # clockwise bearing measured from west
    o=sorted(ang)
    A=[ang[g] for g in o]
    # count steps that advance clockwise, best over rotation is not used: the rule states the start point
    step=sum(((A[j+1]-A[j])%360)<180 for j in range(len(A)-1))/max(1,len(A)-1)
    # shuffled baseline is .5
    per.append((i,len(o),step,A[0]))
    res['n']+=1
import statistics as st
s=[p[2] for p in per];print('installations with 3+ F groups',len(per),'mean share of clockwise steps',round(st.mean(s),3),'median',st.median(s),'share with >=.75',round(sum(a>=.75 for a in s)/len(s),3))
for k in (3,4,5,6,7,8):
    z=[p for p in per if p[1]==k]
    if z:print(k,len(z),'mean clockwise',round(st.mean(a[2] for a in z),3),'F1 within 90deg of west',round(sum((a[3]<45 or a[3]>315) for a in z)/len(z),3))
b=[p[3] for p in per];print('first group bearing from west, by quadrant (0=W,90=N,180=E,270=S)',sorted(collections.Counter(int(((x+45)%360)//90)*90 for x in b).items()))
print('installations with left arrow group',len(arrow),'groups',sum(map(len,arrow.values())),'right arrow',len(right),'bus lanterns',len(bus))
print('counts of left-arrow groups per installation',sorted(collections.Counter(len(v) for v in arrow.values()).items()))
print('makers',maker.most_common(8))
