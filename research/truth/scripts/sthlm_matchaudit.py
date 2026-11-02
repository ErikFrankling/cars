"""Audit count-to-edge matching: name agreement and spread among features averaged on the same edge."""
import sys,json,csv,pickle,collections,re,unicodedata
import numpy as np
N=pickle.load(open(sys.argv[1],'rb'));E=N['E']
D=sys.argv[2]
fs={f['id']:f['properties'] for f in json.load(open(D+'/trafikflode_motorfordon.geojson'))['features']}
def norm(s): return re.sub(r'[^a-z0-9åäö]','',(s or '').lower())
rows=list(csv.DictReader(open(D+'/count_matches.csv')))
cl=lambda e:(E[e]['type'] or 'none').split('.')[-1].replace('_link','')
st=collections.defaultdict(collections.Counter);by=collections.defaultdict(list);clean=[]
for r in rows:
    e=r['edge'];p=fs[r['feature']];a,b=norm(p.get('gatunamn')),norm(E[e]['name'])
    k=cl(e)
    if not a or not b: tag='unnamed'
    elif a==b or a in b or b in a: tag='same_name'
    else: tag='other_name'
    st[k][tag]+=1;st['ALL'][tag]+=1;by[e].append((float(r['daily']),tag))
    if tag!='other_name': clean.append(r)
print({k:dict(v) for k,v in st.items()})
sp=collections.defaultdict(list)
for e,v in by.items():
    d=[x[0] for x in v]
    if len(d)>1: sp[cl(e)].append(max(d)/max(min(d),1))
for k,v in sp.items(): print(k,'edges with >1 feature',len(v),'median max/min',round(float(np.median(v)),2),'p90',round(float(np.quantile(v,.9)),1),'share >5x',round(float(np.mean(np.array(v)>5)),3))
ta=collections.defaultdict(float);tc=collections.defaultdict(float);old=collections.defaultdict(list);new=collections.defaultdict(list)
for r in rows: old[r['edge']].append(float(r['daily']))
for r in clean: new[r['edge']].append(float(r['daily']))
for e in old:
    l=E[e]['lanes'][0]['length']/1000
    ta[cl(e)]+=np.mean(old[e])*l
    if e in new: tc[cl(e)]+=np.mean(new[e])*l
print('target vkm old vs clean',{k:(round(ta[k]),round(tc[k])) for k in ta},'total',round(sum(ta.values())),round(sum(tc.values())))
print('edges old',len(old),'clean',len(new))
with open(sys.argv[3],'w') as w:
    wr=csv.DictWriter(w,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(clean)
print(len(rows),len(clean))
