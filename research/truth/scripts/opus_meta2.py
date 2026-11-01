import json,sys
j=json.load(open(sys.argv[1]))
for r in j['results']:
    print(r['resource']['id'],r['resource']['name'],r['resource'].get('download_count'),r['link'])
