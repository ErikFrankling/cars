# Pages the Hamburg TLD Things and summarises junctions, lane connections, datastream layers. Writes JSON next to the data.
import json,sys,urllib.request,collections,time
out=sys.argv[1]
base='https://tld.iot.hamburg.de/v1.1/Things?$top=1000&$select=name,properties&$orderby=%40iot.id+asc'
url=base; things=[]
while url and len(things)<30000:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60) as r:
        d=json.load(r)
    things+=d['value']; url=d.get('@iot.nextLink'); time.sleep(0.1)
j=collections.Counter(); lt=collections.Counter(); upd=collections.Counter()
for t in things:
    p=t.get('properties') or {}
    j[p.get('trafficLightsID')]+=1; lt[p.get('laneType')]+=1; upd[(p.get('infoLastUpdate') or '')[:7]]+=1
json.dump({'things':len(things),'junctions':len(j),'median_conn_per_junction':sorted(j.values())[len(j)//2],'laneType':lt.most_common(20),'infoLastUpdate':upd.most_common(12)},open(out,'w'),indent=1)
print(open(out).read())
