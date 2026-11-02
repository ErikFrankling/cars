import json,sys,re,html
j=json.load(open(sys.argv[1]))
for h in j['hits']['hits']:
    m=h['metadata']; print('==',h['id'],m['title'],m.get('publication_date'),m.get('license'))
    print(re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',m.get('description',''))))[:1800])
    for x in h['files']: print('  ',x['key'],x['size'],x['links']['self'])
