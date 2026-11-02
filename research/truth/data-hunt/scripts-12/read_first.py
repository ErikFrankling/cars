import json,sys
D=sys.argv[1]
for a in ['18737165','18700553','18737183']:
    d=json.load(open(f'{D}/xuancheng/art_{a}.json'))
    print(a,d['title'],'|',d['license']['name'],'|',d.get('description','')[:300])
    for f in d['files']: print('  ',f['name'],f['size'],f['download_url'])
for n in ['archive_list','archive_jt','archive_old']:
    d=json.load(open(f'{D}/hk-td/{n}.json')); print(n,{k:(v if not isinstance(v,list) else (len(v),v[:2],v[-1:])) for k,v in d.items()})
d=json.load(open(f'{D}/hamburg-tld/ckan_search.json')); print(d['result']['count'])
for r in d['result']['results']: print(' ',r['title'][:110],'|',r.get('license_title'),'|',sorted({x.get('format') for x in r['resources'] if x.get('format')})[:6])
