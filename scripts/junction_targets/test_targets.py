"""Checks on the targets table: columns, no value on a held-out row, no locked site anywhere, every requested type present, numbers where numbers belong."""
import csv
import pathlib
import sys

P = pathlib.Path(__file__).resolve().parents[2] / 'research/truth/data-hunt/25-junction-targets.csv'
R = list(csv.DictReader(open(P)))
assert list(R[0])[:7] == ['metric', 'junction_type', 'site', 'value', 'spread', 'source', 'split'], list(R[0])[:7]
assert {r['split'] for r in R} == {'tune', 'heldout', 'crosscheck', 'none'}, {r['split'] for r in R}
for r in R:
    if r['split'] in ('heldout', 'none'):
        assert r['value'] == '', r
    else:
        float(r['value'])
locked = ('rdb2', 'rdb3', 'rdb4', 'L1', 'sid7', 'helsinki', 'songdo', 'pully', 'd3', 'd6', 'd8', '20181029')
for r in R:
    if r['split'] in ('tune', 'crosscheck'):
        assert not any(k == r['site'] or k + '_' in r['site'] or '_' + k in r['site'] for k in locked), r['site']
types = {r['junction_type'] for r in R}
need = {'signal', 'priority_giveway', 'priority_stop', 'right_before_left', 'all_way_stop', 'roundabout_single', 'roundabout_multi', 'on_ramp', 'off_ramp', 'lane_drop', 'zipper', 'weaving'}
assert need <= types, need - types
print('ok', len(R), 'rows', len(types), 'types')
