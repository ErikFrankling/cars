import json,sys,re
d=json.load(open(sys.argv[1]))
cs=d['collections']
print(len(cs))
from collections import Counter
print(Counter(c.get('license') for c in cs))
lon,lat=18.06,59.33
hit=[c for c in cs if any(b[0]<=lon<=b[2] and b[1]<=lat<=b[3] for b in c['extent']['spatial']['bbox'])]
print(len(hit))
for c in sorted(hit,key=lambda c:c['id']):
    print(c['id'],c.get('license'),c['title'],c['extent']['temporal']['interval'][0][0][:10],'|',c.get('description','')[:200].replace('\n',' '))
print(sorted(set(re.sub(r'\d+','N',c['id']) for c in cs))[:60])
