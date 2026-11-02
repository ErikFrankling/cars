"""Compact print of mg_analyse results. Usage: mg_show.py SITE [SITE...]"""
import json, sys
def s(v):
    return f"{v.get('n')}: {v.get('p05')} {v.get('p25')} {v.get('p50')} {v.get('p75')} {v.get('p95')}" if isinstance(v, dict) and 'p50' in v else v
for name in sys.argv[1:]:
    r = json.load(open(f'research/truth/merging/{name}.json'))
    print('=====', name, 'events', r['events'], 'must', r['must'], 's_end', r['s_end'])
    if 'location' in r:
        for k, v in r['location'].items(): print(' loc', k, s(v))
    for x in r.get('by_flow', []): print(' flow', x['flow'], 'n', x['n'], 'rem', s(x['rem']), 'vtgt', round(x['v_tgt'], 1), 'flow', round(x['flow_mean']))
    for g, d in r.get('gaps', {}).items():
        print(' GAPS', g)
        for w in ('at_lateral_start', 'at_touch', 'at_centre', 'at_label'):
            x = d[w]; print('  ', w, 'n', x['n'], 'lag', s(x['lag']), '| lead', s(x['lead']), '| free', s(x['total_free']))
            print('     tlag', s(x['lag_time']), '| tlead', s(x['lead_time']), '| overlap', round(x['overlap_share'], 3), 'noroom', round(x['no_room_share'], 3), '| closing', s(x['closing_lag']), '| v', s(x['v']))
        print('   adj_final', round(d['already_adjacent_final_gap_at_start'], 3), 'growth', {k: s(v) if isinstance(v, dict) else v for k, v in d['growth_same_pair'].items()})
        print('   speedchange', {k: s(v) for k, v in d['speed_change_start_to_centre'].items()})
        print('   maxq_overlap', s(d['max_q_while_overlapping']), 'premax', s(d['premax_q_before_final_start']), 'probe25', d['probe_share_q25'], 'lat_time', s(d['lateral_time_start_to_label']))
    for g, d in r.get('target_gap', {}).items():
        print(' TARGET', g, {k: (v['n'], round(v['adjacent'], 3), round(v['gap_ahead'], 3), round(v['gap_behind'], 3)) for k, v in d.items()})
    for g, d in r.get('pre_accel_excess', {}).items():
        print(' PREACC', g, {k: (v['n'], v['excess'], v['lo'], v['hi']) for k, v in d.items()})
    for g, d in r.get('parallel', {}).items():
        print(' PARALLEL', g, 'cars', d['cars'], 'eps', d['episodes'], 'dur', s(d['dur']) , 'ge2/5/10', round(d['share_ge2'], 3), round(d['share_ge5'], 3), round(d['share_ge10'], 3), 'locked3/5', round(d['locked_3s'], 3), round(d['locked_5s'], 3))
        print('    dur_raw', d['dur'], 'mdv', s(d['mean_abs_dv']), 'car_longest', d['car_longest'], 'long_dv', s(d['long_dv_start']), '->', s(d['long_dv_end']), 'with_lean', d['moves_with_lean'])
    print(' OVERLAP share', r.get('overlap_time_share_before_start'))
    f = r.get('follower', {})
    for k, v in f.items():
        if k == 'tau' or 'excess_a' not in v: 
            if k != 'tau': print(' FOLLOW', k, v)
            continue
        print(' FOLLOW', k, 'n', v['n'], 'lost', v['speed_lost_excess'], 'resp', v['responders_excess_over_20pct'], 'pre', v['pre_start_excess'], 'post', v['post_start_excess'])
    if 'all' in f and 'excess_a' in f['all']:
        print(' CURVE tau', f['tau']); print(' CURVE all', f['all']['excess_a'])
        if 'must' in f and 'excess_a' in f['must']: print(' CURVE must', f['must']['excess_a'])
