import json,sys
d=json.load(open(sys.argv[1]))
for f in d['features']:
    p=f['properties']
    print(f['id'],f['collection'],{k:p[k] for k in p if k not in('proj:bbox','proj:geometry','proj:transform','proj:shape')})
    for k,a in f['assets'].items(): print('   ',k,a.get('href'),a.get('type'),a.get('roles'),a.get('title'))
