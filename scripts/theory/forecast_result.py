"""Write a result and verdict into a forecast line: python3 -I scripts/theory/forecast_result.py F300 "result" "verdict" """
import csv, sys
from pathlib import Path

F = Path(__file__).resolve().parents[2] / 'research/truth/foundations/forecasts.csv'
rows = list(csv.reader(open(F, newline='')))
fid, result, verdict = sys.argv[1:4]
hit = [r for r in rows if r and r[0] == fid]
if len(hit) != 1:
    sys.exit(f'{fid}: {len(hit)} lines')
r = hit[0]
while len(r) < 10:
    r.append('')
r[8], r[9] = result, verdict
with open(F, 'w', newline='') as f:
    csv.writer(f, lineterminator='\n').writerows(rows)
