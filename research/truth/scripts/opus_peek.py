import zipfile,sys,io,csv
z=zipfile.ZipFile(sys.argv[1])
n=z.namelist();print(len(n));
for x in n[:6]+[y for y in n if 'traffic_light' in y][:3]+[y for y in n if y.endswith('.xodr') or 'volume' in y][:3]: print(x,z.getinfo(x).file_size)
tr=[y for y in n if 'trajector' in y and y.endswith('.csv')];print(len(tr),sum(z.getinfo(y).file_size for y in tr))
for y in [t for t in tr if '12' in t][:1]+[t for t in n if 'traffic_light' in t and t.endswith('.csv')][:1]:
    with z.open(y) as f:
        for i,l in enumerate(io.TextIOWrapper(f)):
            if i>3: break
            print(y.split('/')[-1],l.strip()[:300])
