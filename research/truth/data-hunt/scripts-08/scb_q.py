import json,sys,urllib.request
BASE='https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0207/AM0207Z/'
def meta(t): return json.load(urllib.request.urlopen(BASE+t,timeout=60))
m=meta('AM0207PendlKomA04N')
for v in m['variables']: print(v['code'],v.get('elimination'),v['values'][:4],v['valueTexts'][:3])
K=[c for c in m['variables'][0]['values'] if c[:2] in('01','03','04','05','18','19','20','21','22','09')]
print(len(K))
kon=[v for v in m['variables'] if v['code']=='Kon'][0]['values'][-1]
y=sys.argv[1]
def run(t,Q,out):
    r=urllib.request.Request(BASE+t,data=json.dumps(dict(query=Q,response=dict(format='json'))).encode(),headers={'Content-Type':'application/json'})
    d=json.load(urllib.request.urlopen(r,timeout=170));json.dump(d,open(out,'w'));print(out,len(d['data']),d['data'][:2])
f=lambda c,v:dict(code=c,selection=dict(filter='item',values=v))
run('AM0207PendlKomA04N',[f('Bostadskommun',K),f('Arbetsstallekommun',K),f('Kon',[kon]),f('Tid',[y])],f'commute_{y}.json')
json.dump(dict(zip(m['variables'][0]['values'],m['variables'][0]['valueTexts'])),open('kommun.json','w'),ensure_ascii=False)
for t,name in(('DagSni07KonKN','dag'),('NattSni07KonKN','natt')):
    mm=meta(t);reg=[v for v in mm['variables'] if v['code']=='Region'][0]['values'];reg=[c for c in reg if c in K]
    kk=[v for v in mm['variables'] if v['code']=='Kon'][0]['values']
    sni=[v for v in mm['variables'] if v['code']=='SNI2007'][0]['values']
    run(t,[f('Region',reg),f('Kon',kk),f('SNI2007',sni),f('Tid',[y])],f'{name}_{y}.json')
