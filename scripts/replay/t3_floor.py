"""T3 noise floor (PLAN, How a pass is decided, item 1): the recording against itself, by the metric code a run is
scored with (t3_metrics). (i) two halves of one session, (ii) the same drone and half hour on other mornings.
Approaches and their free speeds come from the reference session, so both sides are measured the same way.

    python3 -I scripts/replay/t3_floor.py 8 0900 20181029 20181024,20181030,20181101
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import pneuma_scene as PS, t3_metrics as TM


def tables(dr, day, hh, apps):
    D = PS.outdir(dr, day, hh); meta = json.load(open(f'{D}/scene.json'))
    st, rec = PS.recording_side(D, meta)
    dl = TM.approach_delays(rec, apps, meta['begin'])
    tt = pd.DataFrame(dict(route=st.edge + '>' + st.exit_edge, tt=st.exit_t - st.t_seen, t_out=st.exit_t, kind=st.kind))
    tt = tt[tt.kind != 'snapshot']
    return meta, dl, tt


def main(dr, hh, ref, others):
    D = PS.outdir(dr, ref, hh); meta = json.load(open(f'{D}/scene.json'))
    st, rec = PS.recording_side(D, meta)
    lanes, conn, links = PS.net_info(f'{D}/net.xml')
    lengths = {d['edge']: d['length'] for l, d in lanes.items() if not d['internal']}
    apps = TM.approaches(rec, lengths, sorted({a for a, b in conn}))
    m0, dl0, tt0 = tables(dr, ref, hh, apps)
    mid = 0.5 * (m0['begin'] + m0['end'])
    out = dict(reference=f'd{dr} {ref} {hh}', approaches=len(apps))
    h1, h2 = dl0[dl0.t_out < mid], dl0[dl0.t_out >= mid]
    t1, t2 = tt0[tt0.t_out < mid], tt0[tt0.t_out >= mid]
    out['halves'] = dict(delay=TM.compare_means(TM.session_delay(h1, 30), TM.session_delay(h2, 30), 30),
                         delay_10=TM.compare_means(TM.session_delay(h1, 10), TM.session_delay(h2, 10), 10),
                         travel_time=TM.compare_means(TM.route_tt(t1), TM.route_tt(t2)))
    out['days'] = {}
    for day in others:
        m, dl, tt = tables(dr, day, hh, apps)
        out['days'][day] = dict(delay=TM.compare_means(TM.session_delay(dl0, 30), TM.session_delay(dl, 30), 30),
                                delay_10=TM.compare_means(TM.session_delay(dl0, 10), TM.session_delay(dl, 10), 10),
                                travel_time=TM.compare_means(TM.route_tt(tt0), TM.route_tt(tt)),
                                mean_delay_s=round(float(dl.delay.mean()), 2), cars=int(len(tt)))
    out['reference_mean_delay_s'] = round(float(dl0.delay.mean()), 2)
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(REPO, 'research/truth/replay', f'f526_floor_d{dr}_{hh}.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4].split(','))
