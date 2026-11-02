"""Where each lane starts and ends, and how cars leave it. Finds lanes that must be left. Usage: mg_structure.py SITE [SITE...]"""
import sys; sys.path.insert(0, 'research/truth/scripts/merging')
from mg_lib import *
out = {}
for name in sys.argv[1:]:
    st = Site(name); rows = {}
    S, LA, R, I, T = st.S, st.LA, st.R, st.I, st.T
    send = float(np.percentile(S, 99.5)); sbeg = float(np.percentile(S, 0.5))
    ch = np.where((I[1:] == I[:-1]) & (R[1:] == R[:-1]) & (LA[1:] != LA[:-1]))[0]
    for l in np.unique(LA):
        m = LA == l
        ss = S[m]
        lc = ch[LA[ch] == l]
        tgt = pd.Series(LA[lc + 1]).value_counts().to_dict()
        # last row of each track in this lane: how far along the view did it end?
        last = np.r_[(I[1:] != I[:-1]) | (R[1:] != R[:-1]), True]
        endm = last & m
        rows[int(l)] = dict(rows=int(m.sum()), s_p1=float(np.percentile(ss, 1)), s_p50=float(np.percentile(ss, 50)), s_p99=float(np.percentile(ss, 99)),
                            tracks_end_here=int(endm.sum()), ends_s_p50=float(np.percentile(S[endm], 50)) if endm.sum() else None,
                            out=tgt, out_s=(q(S[lc]) if len(lc) else None), v_p50=float(np.median(st.V[m])))
    out[name] = dict(view=(sbeg, send), runs=[int(x) for x in np.unique(R)], lanes=rows)
    print(name, json.dumps(out[name]['view']), flush=True)
    for l, r in rows.items():
        print(' ', l, r['rows'], 's', round(r['s_p1']), round(r['s_p99']), 'v', round(r['v_p50'], 1), 'end_here', r['tracks_end_here'], 'at', r['ends_s_p50'] and round(r['ends_s_p50']), 'out', r['out'], 'out_s', r['out_s'] and (r['out_s'].get('p05'), r['out_s'].get('p50'), r['out_s'].get('p95')), flush=True)
save('structure', out)
