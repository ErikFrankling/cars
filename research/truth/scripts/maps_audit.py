import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MPLCONFIGDIR='/home/erikf/.t3/projects/cars/research/truth/fig/.mpl')
import json,csv,re,hashlib,collections,math
from pathlib import Path
from lxml import etree as E
import numpy as np
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path('research/truth')
DATA=Path('/home/erikf/projects/personal/cars-data')
ANCHORS=[('Fredhäll ramp','ramp',59.3295,18.0030),('Kristineberg ramp','ramp',59.3365,18.0045),('Stora Essingen ramp','ramp',59.3210,17.9910),('Lilla Essingen ramp','ramp',59.3245,18.0065),('Nybohov ramp','ramp',59.3090,18.0030),('Slussen north','urban',59.3217,18.0720),('Slussen south','urban',59.3190,18.0735),('Norrtull','complex',59.3510,18.0430),('Sveaplan','urban',59.3518,18.0550),('Roslagstull','roundabout',59.3536,18.0582),('Fridhemsplan','urban',59.3320,18.0290),('S:t Eriksgatan/Fleminggatan','urban',59.3348,18.0315),('Lindhagensplan','roundabout',59.3310,18.0167),('Södra länken Årsta','ramp',59.2935,18.0445),('Södra länken Hammarby','ramp',59.2980,18.0950),('Södra länken Nynäsvägen','ramp',59.2920,18.0820),('Kungens kurva north','interchange',59.2780,17.9220),('Kungens kurva south','interchange',59.2680,17.9130),('Hornstull','urban',59.3155,18.0335),('Tegelbacken','urban',59.3282,18.0615)]
def stream(p,tags):
    for _,e in E.iterparse(str(p),events=('end',),tag=tags):
        yield e
        e.clear()
        while e.getprevious() is not None: del e.getparent()[0]
def write(name,rows):
    if rows:
        with open(OUT/name,'w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def audit(city,path):
    edges={};tls={};js={};types=collections.Counter();internals=0;stats=collections.defaultdict(lambda:[[],[]]);loc={}
    for e in stream(path,('location','edge','tlLogic','junction')):
        a=dict(e.attrib)
        if e.tag=='location':loc=a
        elif e.tag=='edge':
            if a.get('function') in ('internal','crossing','walkingarea') or a['id'].startswith(':'):internals+=1;continue
            ls=[dict(l.attrib) for l in e.findall('lane') if ('allow' not in l.attrib or 'passenger' in l.get('allow','').split() or 'all' in l.get('allow','').split()) and 'passenger' not in l.get('disallow','').split() and l.get('disallow')!='all']
            if not ls:continue
            a['lanes']=ls;edges[a['id']]=a;k=a.get('type','unknown');stats[k][0].append(len(ls));stats[k][1].extend(round(float(l['speed'])*3.6,2) for l in ls)
        elif e.tag=='junction':
            if not a['id'].startswith(':'):js[a['id']]=a;types[a['type']]+=1
        else:
            ps=[dict(p.attrib) for p in e.findall('phase')];cycle=sum(float(p['duration']) for p in ps);n=max([len(p['state']) for p in ps],default=0)
            ratios={}; protected={}
            for i in range(n):
                ratios[i]=sum(float(p['duration']) for p in ps if i<len(p['state']) and p['state'][i] in 'Gg')/max(cycle,1)
                protected[i]=sum(float(p['duration']) for p in ps if i<len(p['state']) and p['state'][i]=='G')/max(cycle,1)
            a.update(cycle=cycle,phases=ps,ratios=ratios,protected=protected);tls[a['id']]=a
    groups=collections.defaultdict(list)
    for e in stream(path,'connection'):
        if e.get('from') in edges:groups[e.get('from')].append(dict(e.attrib))
    caps=[];dedicated=0;sigapproach=0;badlinks=0
    for id,a in edges.items():
        allowed_indices={l['index'] for l in a['lanes']}
        cs=[c for c in groups[id] if c['fromLane'] in allowed_indices];lane_dirs=collections.defaultdict(set);lane_cs=collections.defaultdict(list)
        for c in cs:lane_dirs[c['fromLane']].add(c.get('dir',''));lane_cs[c['fromLane']].append(c)
        sig=any(c.get('tl') for c in cs);sigapproach+=sig
        dl=sum(bool(ds) and ds<=set('lLrR') for ds in lane_dirs.values());dedicated+=sig and dl>0
        upper=lower=0
        for lane in a['lanes']:
            cc=lane_cs[lane['index']]
            upper+=1900*max([tls[c['tl']]['ratios'].get(int(c.get('linkIndex',-1)),0) if c.get('tl') in tls else 1 for c in cc],default=0)
            lower+=1900*max([tls[c['tl']]['protected'].get(int(c.get('linkIndex',-1)),0) if c.get('tl') in tls else 1 for c in cc],default=0)
        badlinks+=sum(c.get('tl') in tls and int(c.get('linkIndex',-1)) not in tls[c['tl']]['ratios'] for c in cs)
        caps.append(dict(edge=id,name=a.get('name',''),junction=a.get('to',''),type=a.get('type',''),lanes=len(a['lanes']),length_m=float(a['lanes'][0]['length']),speed_kmh=max(float(l['speed'])*3.6 for l in a['lanes']),signalised=int(sig),turn_only_lanes=dl,cap_Gg_vph=round(upper,2),cap_G_only_vph=round(lower,2),fraction_ideal=round(upper/(1900*len(a['lanes'])),4),unconnected_lanes=len(a['lanes'])-len(lane_dirs)))
    write(city+'-map-link-capacity.csv',caps)
    jcap=collections.defaultdict(lambda:[0,0,0])
    for c in caps:
        v=jcap[c['junction']];v[0]+=c['cap_Gg_vph'];v[1]+=c['cap_G_only_vph'];v[2]+=c['lanes']
    write(city+'-map-junction-capacity.csv',[dict(junction=k,cap_Gg_sum_vph=v[0],cap_G_sum_vph=v[1],incoming_lanes=v[2]) for k,v in jcap.items()])
    road=[]
    for k,(ns,vs) in sorted(stats.items()):road.append(dict(road_class=k,edges=len(ns),lane_counts=json.dumps(dict(collections.Counter(ns))),speed_kmh_p05=float(np.percentile(vs,5)),speed_kmh_median=float(np.median(vs)),speed_kmh_p95=float(np.percentile(vs,95)),speed_counts=json.dumps(dict(collections.Counter(vs)))))
    write(city+'-map-road-classes.csv',road)
    write(city+'-map-signals.csv',[dict(id=k,type=t['type'],program=t.get('programID'),cycle=t['cycle'],offset=t.get('offset'),min_cycle=sum(float(p.get('minDur',p['duration'])) for p in t['phases']),max_cycle=sum(float(p.get('maxDur',p['duration'])) for p in t['phases']),green_min=min(t['ratios'].values(),default=0),green_max=max(t['ratios'].values(),default=0)) for k,t in tls.items()])
    low=sorted([c for c in caps if c['signalised'] and c['type'] in ['highway.primary','highway.secondary','highway.trunk','highway.motorway'] and c['fraction_ideal']>0],key=lambda c:c['fraction_ideal'])[:20]
    cy=[t['cycle'] for t in tls.values()]
    summary=dict(path=str(path),sha256=hashlib.file_digest(open(path,'rb'),'sha256').hexdigest(),edges=len(edges),external_junctions=len(js),junction_types=dict(types),internal_edges=internals,tls=len(tls),tls_types=dict(collections.Counter(t['type'] for t in tls.values())),cycles=dict(collections.Counter(cy)),zero_offsets=sum(float(t.get('offset',0))==0 for t in tls.values()),cycles_outside_30_180=sum(c<30 or c>180 for c in cy),signal_approaches=sigapproach,approaches_with_turn_only_lanes=dedicated,bad_link_indices=badlinks,disconnected_lanes=sum(c['unconnected_lanes'] for c in caps),low_capacity=low,road_classes=road,location=loc)
    if city=='stockholm':
        off=list(map(float,loc['netOffset'].split(',')));tr=Transformer.from_crs(loc['projParameter'],'EPSG:4326',always_xy=True);samples=[];used=set()
        inbound=collections.defaultdict(list);outbound=collections.Counter()
        for c in caps:inbound[c['junction']].append(c)
        for a in edges.values():outbound[a.get('from')]+=1
        rampnodes={a.get(end) for a in edges.values() if a.get('type') in ('highway.motorway_link','highway.trunk_link') for end in ('from','to')}
        for name,kind,lat,lon in ANCHORS:
            candidates=[]
            for id,j in js.items():
                if id in used or j['type']=='dead_end':continue
                if kind in ('ramp','interchange') and (id not in rampnodes or len(inbound[id])+outbound[id]<3):continue
                if kind=='urban' and (j['type']!='traffic_light' or len(inbound[id])<2):continue
                if kind in ('roundabout','complex') and len(inbound[id])+outbound[id]<3:continue
                req={'Sveaplan':['Sveavägen','Cedersdalsgatan'],'Roslagstull':['Roslagstull'],'Fridhemsplan':['Drottningholmsvägen','Sankt Eriksgatan'],'S:t Eriksgatan/Fleminggatan':['Sankt Eriksgatan','Fleminggatan']}.get(name,[])
                names={c['name'] for c in inbound[id]}
                if any(n not in names for n in req):continue
                lo,la=tr.transform(float(j['x'])-off[0],float(j['y'])-off[1]);d=math.hypot((lo-lon)*57000,(la-lat)*111000)
                if d<2000:candidates.append((d,id,la,lo))
            if not candidates:continue
            d,id,la,lo=min(candidates);used.add(id);inc=[c for c in caps if c['junction']==id]
            samples.append(dict(label=name,kind=kind,anchor_lat=lat,anchor_lon=lon,junction=id,lat=la,lon=lo,distance_m=round(d),jtype=js[id]['type'],approaches=len(inc),incoming_lanes=sum(c['lanes'] for c in inc),turn_only_lanes=sum(c['turn_only_lanes'] for c in inc),edges=' '.join(c['edge'] for c in inc),names=' / '.join(sorted(set(c['name'] for c in inc)))))
        write('stockholm-map-samples.csv',samples)
        osm={};wanted={re.match(r'-?(\d+)',c['edge']).group(1) for c in caps if c['signalised'] and re.match(r'-?(\d+)',c['edge'])}
        wanted.update(re.match(r'-?(\d+)',id).group(1) for s in samples for id in s['edges'].split() if re.match(r'-?(\d+)',id))
        for e in stream(DATA/'stockholm/clip.osm.xml','way'):
            if e.get('id') in wanted:osm[e.get('id')]={t.get('k'):t.get('v') for t in e.findall('tag')}
        comp=[]
        for c in caps:
            m=re.match(r'-?(\d+)',c['edge']);tags=osm.get(m.group(1),{}) if m else {};turn={k:v for k,v in tags.items() if k.startswith('turn:lanes')}
            if c['signalised'] or any(c['edge'] in s['edges'].split() for s in samples):comp.append(dict(edge=c['edge'],name=c['name'],signalised=c['signalised'],net_lanes=c['lanes'],net_turn_only=c['turn_only_lanes'],osm_way=m.group(1) if m else '',osm_lanes=tags.get('lanes',''),osm_lanes_forward=tags.get('lanes:forward',''),osm_lanes_backward=tags.get('lanes:backward',''),osm_turn_tags=json.dumps(turn),osm_oneway=tags.get('oneway',''),osm_maxspeed=tags.get('maxspeed','')))
        write('stockholm-map-osm-comparison.csv',comp);summary['osm_signal_approaches_with_turn_tags']=sum(bool(json.loads(c['osm_turn_tags'])) for c in comp if c['signalised']);summary['samples']=samples
    (OUT/(city+'-map-audit.json')).write_text(json.dumps(summary,indent=2,ensure_ascii=False));return summary
results=[audit('stockholm',DATA/'stockholm/stockholm.net.xml'),audit('berlin',DATA/'best/berlin.net.xml')]
fig,axs=plt.subplots(1,2,figsize=(11,4))
for ax,r in zip(axs,results):
    cs=r['cycles'];ax.bar([str(k) for k in cs],list(cs.values()));ax.set(title=r['path'].split('/')[-1],xlabel='Nominal cycle (seconds)',ylabel='Controllers');ax.tick_params(axis='x',rotation=90)
fig.tight_layout();fig.savefig(OUT/'fig/maps-cycles.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(11,4))
for ax,r in zip(axs,results):
    ts=r['junction_types'];ax.barh(list(ts),[100*v/r['external_junctions'] for v in ts.values()]);ax.set(title=r['path'].split('/')[-1],xlabel='External junctions (%)')
fig.tight_layout();fig.savefig(OUT/'fig/maps-junction-types.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(figsize=(10,6));ss=results[0]['samples'];ax.scatter([s['lon'] for s in ss],[s['lat'] for s in ss]);
for i,s in enumerate(ss):ax.annotate(str(i+1),(s['lon'],s['lat']))
ax.set(xlabel='Longitude',ylabel='Latitude',title='20 sampled net junctions; numbers match report (no imagery basemap)');fig.tight_layout();fig.savefig(OUT/'fig/maps-stockholm-samples.png',dpi=150)
print(json.dumps([{k:v for k,v in r.items() if k not in ('road_classes','samples','low_capacity')} for r in results],indent=2))
