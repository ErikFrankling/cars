# Runs the unmodified audit scripts against an isolated copy of their inputs. Only the output root changes.
import shutil,sys
from pathlib import Path
root='research/truth/berlin-review/rerun'; src_dir=Path('research/truth/berlin-snapshot'); dst=Path(root)/'berlin-snapshot'; dst.mkdir(parents=True,exist_ok=True); (Path(root)/'fig').mkdir(exist_ok=True)
for f in ['day_edges.csv','day_summary.csv','day_trips.csv','detector_map.csv','detector_compare.csv','detector_profile.csv','download-dir.txt']:
    if not (dst/f).exists(): shutil.copy(src_dir/f,dst/f)
for name in sys.argv[1:]:
    src=Path('research/truth/scripts/'+name).read_text()
    src=src.replace("B=Path('research/truth')","B=Path('%s')"%root)
    src=src.replace("Path('research/truth/berlin-snapshot')","Path('%s/berlin-snapshot')"%root)
    src=src.replace("Path('research/truth/fig')","Path('%s/fig')"%root)
    assert 'research/truth/berlin-snapshot' not in src.replace(root+'/berlin-snapshot','')
    print('=====',name,flush=True)
    exec(compile(src,name,'exec'),{'__name__':'__main__'})
