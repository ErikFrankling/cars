"""Assembles research/truth/data-hunt/25-junction-targets.csv from the rows of every analysis, adds cross-site spreads, published cross-checks,
held-out stubs with no values, and NO DATA lines, so that a missing type can never read as a pass."""
import csv
import glob
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
import pandas as pd
from common import OUT, COLS, spread_of

DST = pathlib.Path(__file__).resolve().parents[2] / 'research/truth/data-hunt/25-junction-targets.csv'
# metrics worth a site-to-site row: name, movement filter
CROSS = ['critical_gap_median', 'critical_gap_those_who_rejected', 'critical_gap_stopped_and_rejected', 'gap_acceptance_share', 'follow_up_headway_median', 'saturation_headway', 'saturation_flow', 'stop_share', 'entry_flow_total', 'junction_flow_total', 'entry_speed_unstopped_median', 'exit_speed_median',
         'merge_position_share_p50', 'merge_last_third_share', 'merge_speed_median', 'accepted_time_gap_new_follower_p50', 'accepted_time_gap_new_leader_p50', 'alternation_share', 'minor_delay_mean', 'approach_delay_mean', 'entered_ahead_under_2s_share', 'queue_len_p95', 'discharge_headway_pos4plus', 'core_speed_median', 'queue_headway_by_position', 'full_stop_share', 'ring_speed_median', 'flow_per_lane', 'speed_median', 'diverge_speed_median']
XCHECK = [
    ('critical_gap_design', 'roundabout_single', 'TRVMB', 3.4, 's', 'Trafikverket TRVMB Kapacitet och framkomlighetseffekter, section 6.2.4: T = min(5.66 + corrections, 3.4)', 'https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf'),
    ('follow_up_design', 'roundabout_single', 'TRVMB', 2.4, 's', 'TRVMB 6.2.4: T0 = 2.4 + 1.1(heavy share - 0.061)', 'https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf'),
    ('critical_gap_design', 'roundabout_single', 'WI_FDM', 4.2, 's', 'Wisconsin FDM, as quoted in the WisDOT statewide study 2020', 'https://www.wisconsindot.gov/dtsdManuals/traffic-ops/programs/analysis/roundabout-analysis.pdf'),
    ('follow_up_design', 'roundabout_single', 'WI_FDM', 2.8, 's', 'Same study', 'https://www.wisconsindot.gov/dtsdManuals/traffic-ops/programs/analysis/roundabout-analysis.pdf'),
    ('critical_gap_measured_elsewhere', 'roundabout_single', 'Wisconsin_1lane', 3.8, 's', 'WisDOT 2020 table 15, one-lane entry, one circulating lane, with exiting cars handled, method 2. Without that handling 4.6. HCM 6 column 5.0', 'https://www.wisconsindot.gov/dtsdManuals/traffic-ops/programs/analysis/roundabout-analysis.pdf'),
    ('critical_gap_design', 'priority_giveway', 'TRVMB_50kmh', 5.0, 's', 'TRVMB table 3, give way, major road 50 km/h, minor right turn. Other movements 5.1 and up; left from the major road 4.8', 'https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf'),
    ('critical_gap_design', 'priority_stop', 'TRVMB_50kmh', 5.7, 's', 'TRVMB table 3, stop, major road 50 km/h, minor right turn. Follow-up is 0.6 of it', 'https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf'),
    ('saturation_flow_design', 'signal', 'TRVMB', 1900, 'veh/h/lane', 'TRVMB design value per green hour, as read in report 20', 'https://bransch.trafikverket.se/globalassets/dokument/trvmb_kapacitet_och_framkomlighetseffekter.pdf'),
    ('saturation_flow_design', 'signal', 'FHWA_STM', 1900, 'veh/h/lane', 'FHWA Signal Timing Manual: 1,900 ideal, 1,800 for planning, as read in report 05', 'https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm'),
]
HELDOUT = [
    ('roundabout_single', 'rdb2', 'OpenDD v3 https://l3pilot.eu/data/opendd.html', 'zip on disk, map read, tracks unread'),
    ('roundabout_single', 'rdb3', 'OpenDD v3 https://l3pilot.eu/data/opendd.html', 'zip on disk, map read, tracks unread'),
    ('roundabout_single', 'rdb4', 'OpenDD v3 https://l3pilot.eu/data/opendd.html', 'zip on disk, map read, tracks unread'),
    ('roundabout_single', 'L1', 'Swiss roundabouts https://zenodo.org/records/15077435', 'Report 05 printed values for it with the old rule, so it is a weak hold-out'),
    ('signal', 'dlr_ut_sid7', 'DLR Urban Traffic https://zenodo.org/records/20919480', 'locked.toml dlrut-sid7'),
    ('signal', 'athens_d3_d6_d8', 'pNEUMA https://zenodo.org/records/10491409', 'never downloaded; hash rule'),
    ('signal', 'athens_day_20181029', 'pNEUMA https://zenodo.org/records/10491409', 'never downloaded; lowest hash of the four days'),
    ('signal', 'songdo', 'Songdo Traffic https://doi.org/10.5281/zenodo.13828383', 'locked.toml songdo-sessions; not opened'),
    ('roundabout_unknown', 'helsinki_A_C', 'Helsinki drones https://zenodo.org/records/19684712', 'locked.toml helsinki-trajectories; not opened; ring lanes unknown'),
    ('signal', 'helsinki_E_F_G_H', 'Helsinki drones https://zenodo.org/records/19684712', 'locked.toml; not opened; control types not checked on the data'),
    ('priority_giveway', 'pully', 'Pully drones https://zenodo.org/records/12568873', 'report 22 section 9; OSM lists give-way nodes in the area; not opened beyond report 20 sample'),
]
NODATA = [
    ('roundabout_multi', 'No two-lane ring in OpenDD or the Swiss set. rounD (pending) would fill it; Helsinki unknown and locked'),
    ('right_before_left', 'No verified site. Two Athens crossings are unsigned candidates only. inD (pending) names one such site'),
    ('zipper', 'No true urban zipper. Congested lane ends on I-80 and I-395 give a proxy, see alternation_share. exiD and TUMDOT unopened'),
]


SITE_NOTES = {
    'athens_slip_d7': 'WEAK: a slip road 14 m from a signal, so delay and the 6.5 s gap are mixed up with the signal queue. Do not use as a clean give-way target.',
    'athens_unsigned_d10a': 'WEAK: rule not seen on the ground, and almost no conflict was seen.',
    'athens_unsigned_d10b': 'Rule not seen on the ground. Behaves like a priority road: one arm stops 17 times as often, and the right-hand car goes first only half the time.',
    'athens_stop_d5': 'OSM stop node. Athens drivers, three weekdays. Mostly right turns.',
    'foggy_H_22nd': 'THIN: the only all-way stop, two approaches on one-way streets, under 300 cars, pedestrians near 83% of entries.',
    'sind_changchun': 'Long queue headways here (2.8 s) may be local or may be the lane clustering. Not checked against the map.',
    'us101_ventura_cahuenga_weave': 'THIN as a type: the only weave here.',
}


def main():
    rows = []
    for f in sorted(glob.glob(str(OUT / 'rows_*.csv'))):
        rows += list(csv.DictReader(open(f)))
    df = pd.DataFrame(rows, columns=COLS)
    df['junction_type'] = df['junction_type'].replace({'unsigned_candidate': 'priority_unsigned'})
    for site, text in SITE_NOTES.items():
        m = df['site'] == site
        df.loc[m, 'note'] = (df.loc[m, 'note'].fillna('') + ' ' + text).str.strip()
    df['note'] = df['note'].fillna('').str.replace('last 60 m against the movement p15', 'last 50 to 60 m against the movement p15')
    df['v'] = pd.to_numeric(df['value'], errors='coerce')
    # A 31 s critical gap on the slip road is the signal queue, not a choice
    df = df[~((df['site'] == 'athens_slip_d7') & df['metric'].isin(['critical_gap_those_who_rejected', 'critical_gap_stopped_and_rejected']))]
    out = df.drop(columns='v').to_dict('records')
    extra = []
    for (jt, m, mv), g in df[df['metric'].isin(CROSS) & (df['split'] == 'tune') & (df['spread_kind'] != 'day_to_day')].groupby(['junction_type', 'metric', 'movement']):
        v = g.groupby('site')['v'].median().dropna()
        if len(v) < 2:
            continue
        extra.append(dict(metric=m, junction_type=jt, site='ALL_TUNING_SITES', value=round(float(v.median()), 4), spread=round(float(spread_of(v)), 4), source='; '.join(sorted({s.split(' http')[0] for s in g['source']})), split='tune', unit=g['unit'].iloc[0], n=int(pd.to_numeric(g['n']).sum()), spread_kind='site_to_site', lo=round(float(v.min()), 4), hi=round(float(v.max()), 4), movement=mv, bench_id=g['bench_id'].iloc[0], grade='MEASURED', note=f'{len(v)} sites. value is the median of site values, lo and hi the lowest and highest site'))
    for m, jt, site, val, u, note, src in XCHECK:
        extra.append(dict(metric=m, junction_type=jt, site=site, value=val, spread='', source=src, split='crosscheck', unit=u, n=0, spread_kind='none', lo='', hi='', movement='all', bench_id='', grade='PROVIDER CLAIM', note=note + '. Cross-check only, never a target'))
    for jt, site, src, note in HELDOUT:
        extra.append(dict(metric='sealed', junction_type=jt, site=site, value='', spread='', source=src, split='heldout', unit='', n=0, spread_kind='none', lo='', hi='', movement='all', bench_id='', grade='', note=note + '. Compute with the same scripts at an approved reveal'))
    for jt, note in NODATA:
        extra.append(dict(metric='NO_DATA', junction_type=jt, site='none', value='', spread='', source='', split='none', unit='', n=0, spread_kind='none', lo='', hi='', movement='all', bench_id='', grade='', note=note))
    # the closest thing to a zipper: congested lane ends. Same numbers under their own type, labelled as a proxy
    for r in out:
        if r['site'] in ('i80_powell_onramp', 'i395_aux_lane_end') and r['metric'] in ('alternation_share', 'merge_physical_last_third_share', 'merge_speed_median', 'accepted_time_gap_new_follower_p50', 'accepted_time_gap_new_leader_p50', 'stopped_in_source_lane_share'):
            extra.append({**r, 'junction_type': 'zipper_proxy', 'bench_id': 'JZ1', 'note': (str(r['note']) + ' Freeway lane end in congestion, not a signed urban zipper.').strip()})
    all_rows = out + extra
    all_rows.sort(key=lambda r: (str(r['junction_type']), str(r['metric']), str(r['site']), str(r['movement'])))
    with open(DST, 'w', newline='') as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(all_rows)
    d = pd.DataFrame(all_rows)
    print('rows', len(d), d.groupby(['junction_type', 'split']).size().to_dict())


if __name__ == '__main__':
    main()
