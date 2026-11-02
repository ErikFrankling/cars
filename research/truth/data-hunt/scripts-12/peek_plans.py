# Reads at most 30 MB decompressed from a gzipped MATSim plans file: plans per person and leg modes.
import gzip,sys,re,collections
LIMIT=30_000_000
for p in sys.argv[1:]:
    try:
        with gzip.open(p,'rb') as f: s=f.read(LIMIT)
    except EOFError as e:
        print(p,'truncated',e); continue
    t=s.decode('utf8','replace'); people=t.count('<person '); plans=t.count('<plan ')
    print(p,'bytes read',len(t),'persons',people,'plans',plans,'plans/person %.2f'%(plans/max(1,people)),collections.Counter(re.findall(r'<leg mode="([^"]+)"',t)).most_common(6))
    i=t.find('<person '); print(t[i:i+700])
