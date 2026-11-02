import json,sys,re,html
for f in sys.argv[1:]:
    j=json.load(open(f)); m=j['metadata']
    print('==',j['id'],m['title'],'|',m.get('publication_date'),'| lic',m.get('license'))
    print(re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',m.get('description',''))))[:3000])
    s=0
    for x in j['files'][:40]:
        print('  ',x['key'],x['size'],x['links']['self']); s+=x['size']
    print(' total',s,len(j['files']))
