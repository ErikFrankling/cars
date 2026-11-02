"""Print the topology around edge or junction ids from a pickled net index."""
import sys,pickle
N=pickle.load(open(sys.argv[1],'rb'));E,C,J,T=N['E'],N['C'],N['J'],N['T']
def show(e):
    d=E[e]
    print(f"EDGE {e} name={d['name']} type={d['type']} {d['frm']} -> {d['to']} lanes={len(d['lanes'])} len={d['lanes'][0]['length']:.1f} v={d['lanes'][0]['speed']*3.6:.0f}km/h")
    for c in C.get(e,[]):
        tgt=E.get(c['to'],{})
        print(f"   lane{c['fromLane']} -> {c['to']}_{c['toLane']} dir={c['dir']} st={c['state']} tl={c['tl']} idx={c['linkIndex']} via={c['via']} toName={tgt.get('name')} toLen={tgt['lanes'][0]['length'] if tgt else 0:.1f}")
for a in sys.argv[2:]:
    if a in E:
        show(a)
        print(' inc:',[(k) for k,v in C.items() if not k.startswith(':') and any(c['to']==a for c in v)])
    elif a in J:
        j=J[a];print('JUNCTION',a,j['type'],j['x'],j['y'],'inc',j['inc'][:400])
        inc=sorted({l.rsplit('_',1)[0] for l in j['inc'].split()})
        for e in inc:
            if e in E: show(e)
        if a in T: print(' TLS',T[a]['phases'])
