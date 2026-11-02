# How many of Berlin's measuring cross-sections are in MATSim v6.4's calibration counts file.
import gzip,sys,re,csv
xml=gzip.open(sys.argv[1],'rt',encoding='utf8').read()
locs=re.findall(r'<location refId="([^"]+)" name="([^"]+)"',xml)
print('count locations',len(locs),'year',re.search(r'year="(\d+)"',xml).group(1),'examples',[n for _,n in locs[:3]],'hourly blocks',xml.count('interval="3600"'))
ids={re.match(r'\d+',n).group(0) for _,n in locs if re.match(r'\d+',n)}
mq=set()
with gzip.open(sys.argv[2],'rt',errors='replace') as f:
    r=csv.reader(f,delimiter=';');next(r)
    for x in r: mq.add(x[0])
digits={m:re.search(r'(\d{4,6})',m).group(1) for m in mq if re.search(r'(\d{4,6})',m)}
hit=[m for m,d in digits.items() if d in ids]
print('mq sample',sorted(mq)[:5],'n',len(mq),'| numeric ids in counts',len(ids),sorted(ids)[:5])
print('mq with id in counts',len(hit),'not in counts',len(mq)-len(hit),'sample',sorted(set(mq)-set(hit))[:10])
