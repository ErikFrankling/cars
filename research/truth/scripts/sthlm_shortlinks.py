"""Attribute teleports to short links, mid-block signals, turnarounds; output concentration table."""
import sys,csv,pickle,collections,json
N=pickle.load(open(sys.argv[1],'rb'));E,C,J,T=N['E'],N['C'],N['J'],N['T']
edges=sys.argv[2]; H=float(sys.argv[3]) if len(sys.argv)>3 else 1e9
L=lambda e:E[e]['lanes'][0]['length']
# junction -> min incident external length
near=collections.defaultdict(lambda:1e9)
for k,v in E.items():
    if v['fn'] is None:
        for j in(v['frm'],v['to']): near[j]=min(near[j],L(k))
def junction_of(e):
    if e.startswith(':'): return e[1:].rsplit('_',1)[0]
    return E[e]['to']
tot=0;site=collections.Counter();bins=collections.Counter();hours=collections.defaultdict(collections.Counter)
for r in csv.DictReader(open(edges)):
    t=int(r['teleports']);b=float(r['begin'])
    if not t or r['edge'] not in E: continue
    h=b//3600;tot+=t
    j=junction_of(r['edge']);ml=near[j]
    if not r['edge'].startswith(':'): ml=min(ml,L(r['edge']))
    c='<7.5m' if ml<7.5 else '<15m' if ml<15 else '<30m' if ml<30 else '>=30m'
    bins[c]+=t;hours[h][c]+=t;site[j]+=t
s=sorted(site.values(),reverse=True)
print(json.dumps(dict(total=tot,bins=dict(bins),sites=len(s),share_top10=sum(s[:10])/tot,share_top100=sum(s[:100])/tot,share_top1000=sum(s[:1000])/tot,by_hour={str(int(h)):dict(c) for h,c in sorted(hours.items())}),ensure_ascii=False))
print(site.most_common(15))
base=collections.Counter(('<7.5m' if near[j]<7.5 else '<15m' if near[j]<15 else '<30m' if near[j]<30 else '>=30m') for j in J if not j.startswith(':') and J[j]['type'] not in('internal','dead_end'))
print('junction base rates',dict(base))
