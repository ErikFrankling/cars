import sys
sys.argv=['x','/home/erikf/projects/personal/cars-data/datasets/dft-tra/tra0307-traffic-distribution-by-time-of-day.ods','0']
import zipfile
from lxml import etree
NS={'t':'urn:oasis:names:tc:opendocument:xmlns:table:1.0','x':'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
T='{%s}'%NS['t']
def sheets(fn):
    root=etree.fromstring(zipfile.ZipFile(fn).read('content.xml'))
    for tb in root.iter(T+'table'):
        rows=[]
        for r in tb.iter(T+'table-row'):
            cells=[]
            for c in r.findall(T+'table-cell'):
                rep=int(c.get(T+'number-columns-repeated','1'))
                txt=' '.join(''.join(p.itertext()) for p in c.findall('x:p',NS))
                val=c.get('{urn:oasis:names:tc:opendocument:xmlns:office:1.0}value')
                cells += [val if val else txt]*min(rep,40)
            if any(cells): rows.append(cells)
        yield tb.get(T+'name'),rows
D='/home/erikf/projects/personal/cars-data/datasets/dft-tra/'
S=dict(sheets(D+'tra0307-traffic-distribution-by-time-of-day.ods'))
rows=[r for r in S['TRA0307'] if r[0].isdigit()]
yrs=sorted({r[0] for r in rows}); print(yrs[0],yrs[-1])
print(S['Notes'][3][1][:300])
for y in ['2019','2024','2025']:
    rr=[r for r in rows if r[0]==y]
    if not rr: continue
    d={}
    for j,day in enumerate(['Mon','Tue','Wed','Thu','Fri','Sat','Sun']):
        v=[float(r[4+j]) for r in rr]; tot=sum(v)
        d[day]=v
        mid=sum(v[10:15])/5
        print(y,day,'tot',tot,'am',round(max(v[6:10])/tot,3),'pm',round(max(v[15:19])/tot,3),'night22-06',round((sum(v[22:])+sum(v[:6]))/tot,3),'07-19',round(sum(v[7:19])/tot,3),'am/mid',round(max(v[6:10])/mid,2),'pm/mid',round(max(v[15:19])/mid,2),'min/mid',round(min(v)/mid,3))
    print(y,'Wed',d['Wed'])
    print(y,'Sun',d['Sun'])
S=dict(sheets(D+'tra0306-traffic-distribution-by-day-of-week.ods'))
rows=[r for r in S['TRA0306'] if r[0].isdigit()]
y=max(r[0] for r in rows); print('tra0306',y)
for r in rows:
    if r[0]==y and r[1] in ('Urban road','Motorway','All road'): print(r[1],r[2],'cars',r[5],'all',r[10])
print(S['Notes'][3][1][:300])
S=dict(sheets(D+'tra8904-km-by-local-authority.ods'))
print(list(S))
for n,rows in S.items():
    if n.startswith('TRA'):
        hdr=[r for r in rows if r and 'Local Authority' in ' '.join(r[:4])][:1]; print(hdr[0][:8] if hdr else rows[4][:8])
        for r in rows:
            if any(k in ' '.join(r[:3]) for k in ('London','Manchester','Birmingham','Leeds','Bristol','Sheffield','Edinburgh','Glasgow')): print([x[:22] for x in r[:6]], r[-1][:10], r[-2][:10])
