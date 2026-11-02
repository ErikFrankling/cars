import json,sys,datetime as dt,collections,math
r=json.load(open(sys.argv[1]))
print(len(r),collections.Counter(str(x.get('status')) for x in r).most_common(5))
from PIL import Image
sz=collections.Counter();age=[]
now=dt.datetime.now(dt.timezone.utc)
for x in r:
    try:
        im=Image.open(sys.argv[1].rsplit('/',1)[0]+f"/{x['cam']}.jpg");sz[im.size]+=1
        age.append((now-dt.datetime.fromisoformat(x['phototime'])).total_seconds())
    except Exception as e: pass
print(sz.most_common(6));age.sort();print('age s p10,50,90,max',age[len(age)//10],age[len(age)//2],age[9*len(age)//10],age[-1])
print(collections.Counter(x['road'] for x in r).most_common(25))
near=[x for x in r if 17.97<x['pos'][0]<18.11 and 59.30<x['pos'][1]<59.36]
print('central',len(near));print([(x['name'],x['road'][:18]) for x in near][:50])
