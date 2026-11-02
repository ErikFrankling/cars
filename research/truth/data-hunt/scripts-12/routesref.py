import gzip,csv,sys,collections
r=list(csv.DictReader(gzip.open(sys.argv[1],'rt')))
p={(x['from_node'],x['to_node']) for x in r};h=collections.Counter(int(x['hour']) for x in r)
print('routes-ref rows',len(r),'distinct routes',len(p),'hours',sorted(h.items()))
m=collections.defaultdict(list)
for x in r:m[int(x['hour'])].append(float(x['mean']))
print({k:round(sum(v)/len(v),1) for k,v in sorted(m.items())})
