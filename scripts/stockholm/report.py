import sys,json,csv,xml.etree.ElementTree as ET
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D=Path(sys.argv[1]); fig,ax=plt.subplots()
for prefix,color in [('cars','#2a78d6'),('sumo','#eb6834')]:
    if prefix=='cars':
        rows=list(csv.DictReader(open(D/'cars.summary.csv')));times=[float(r['time'])/3600 for r in rows];running=[int(r['running']) for r in rows]
    else:
        rows=[e.attrib for _,e in ET.iterparse(D/'sumo.summary.xml') if e.tag=='step'];times=[float(r['time'])/3600 for r in rows];running=[int(r['running']) for r in rows]
    ax.plot(times,running,lw=.7,color=color,label=prefix)
    print(prefix,'peak running',max(running,default=0),'final',rows[-1] if rows else None)
ax.set(xlabel='Hour',ylabel='Running vehicles');ax.legend();fig.savefig('results/stockholm/running.png',dpi=160)
