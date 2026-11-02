#!/usr/bin/env python3
# Summarises Stockholm's signal register per installation. Usage: register_groups.py Signallykta.geojson Tryckknapp.geojson OUT.csv
import sys,json,re,collections,csv
A=collections.defaultdict(lambda:collections.defaultdict(set));ty=collections.Counter();names=collections.Counter()
for f in json.load(open(sys.argv[1]))['features']:
    p=f['properties'];i=str(p.get('anläggnings-id')).lstrip('0');n=p.get('namn') or '';names[re.sub(r'[0-9:]+','#',n)]+=1;ty[p.get('typ')]+=1
    m=re.search(r'\b([A-ZÅÄÖ]{1,3})\s?(\d+)?(?::\d+)?\s*$',n)
    kind=n.split()[0] if n else '?'
    g=re.search(r'([A-ZÅÄÖ]+)(\d+)(?::\d+)?',n)
    A[i][g.group(1) if g else kind].add(g.group(2) if g else n)
    A[i]['_typ'].add(p.get('typ'))
print(names.most_common(25));print(ty.most_common(25))
rows=[]
for i,d in A.items():
    F=len(d.get('F',()));G=len(d.get('G',()));C=len(d.get('C',()));B=len(d.get('B',()))
    rows.append((i,F,G,C,B,';'.join(sorted(k for k in d if k not in('F','G','C','B','_typ')))))
csv.writer(open(sys.argv[3],'w')).writerows([('id','F','G','C','B','other')]+rows)
c=collections.Counter(min(r[1],13) for r in rows);print('F groups per installation',sorted(c.items()))
print('with F>=1',sum(r[1]>0 for r in rows),'F=0',sum(r[1]==0 for r in rows),'F=1',sum(r[1]==1 for r in rows),'F=2',sum(r[1]==2 for r in rows),'G per inst',sorted(collections.Counter(min(r[2],13) for r in rows).items()),'C',sorted(collections.Counter(min(r[3],9) for r in rows).items()),'B',sorted(collections.Counter(min(r[4],9) for r in rows).items()))
