"""What are the no-conflict signals? Walk downstream from each to see whether a real uncontrolled intersection follows."""
import sys,pickle,collections,json
N=pickle.load(open(sys.argv[1],'rb'));E,C,J,T=N['E'],N['C'],N['J'],N['T']
ext=lambda e:E[e]['fn'] is None
inc=collections.defaultdict(set)
for e,v in E.items():
    if ext(e): inc[v['to']].add(e)
tl=collections.defaultdict(set)
for e,cs in C.items():
    if not e.startswith(':'):
        for c in cs:
            if c['tl']: tl[c['tl']].add(e)
ty=collections.Counter()
rows=[]
for t,app in tl.items():
    straight=all(all(c['dir'] in('s','t') for c in C[e] if c['tl']==t) for e in app)
    if not straight and len(app)>1: ty['real intersection (turns or >=3 arms)']+=1; continue
    if not straight and len(app)==1: pass
    # follow downstream up to 60 m to the first junction with several real inputs that the signal does not control.
    found=None
    for e in app:
        for c in C[e]:
            cur=c['to'];dist=0
            for _ in range(8):
                j=E[cur]['to'];dist+=E[cur]['lanes'][0]['length']
                if dist>60: break
                others=[x for x in inc[j] if x!=cur and x!=('-'+cur if not cur.startswith('-') else cur[1:])]
                if len(others)>=1 and J[j]['type'] in('priority','right_before_left','priority_stop','allway_stop') :
                    found=(j,J[j]['type'],dist);break
                if j in T: break
                nx=[k['to'] for k in C.get(cur,[]) if k['dir']=='s']
                if not nx: break
                cur=nx[0]
            if found: break
        if found: break
    if found: ty[f'pre-signal {len(app)} approach, uncontrolled {found[1]} within 60 m']+=1; rows.append((t,found))
    elif len(app)==1: ty['isolated mid-block, one direction']+=1
    else: ty['isolated mid-block, both directions']+=1
print(json.dumps(ty,indent=1,ensure_ascii=False))
print(rows[:10])
