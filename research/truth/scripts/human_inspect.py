from pathlib import Path
p=Path('/home/erikf/projects/personal/cars-data/truth/trajectories/human-20261031-pneuma/20181024_d1_0830_0900.csv')
with p.open() as f:
 print(next(f)); print(next(f)[:1500])
