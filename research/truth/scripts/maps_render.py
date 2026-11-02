# Renders each site: aerial, aerial+net+real signal heads, OSM ways with tags, net lanes/connections/controllers. Usage: maps_render.py NET TAG SITES.csv [names...]
import sys;sys.path.insert(0,'research/truth/scripts')
from maps_lib import *
import json,csv,math,time,urllib.request,io,hashlib
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
netp,tag,sitesf=sys.argv[1:4];only=set(sys.argv[4:])
sites=[r for r in csv.DictReader(open(sitesf)) if not only or r['site'] in only]
loc=None
for e in stream(netp,'location'):
    loc=dict(e.attrib);break
fake=dict(location=loc);fwd,back=net_tf(fake)
to3857=Transformer.from_crs('EPSG:4326','EPSG:3857',always_xy=True)
def M(lon,lat):return to3857.transform(lon,lat)
def NM(x,y):return M(*back(x,y))
for s in sites:
    s['lat']=float(s['lat']);s['lon']=float(s['lon']);s['r']=float(s['r']);s['cx'],s['cy']=fwd(s['lon'],s['lat'])
def near(pts,s,mar=1.15):
    R=s['r']*mar
    return any(abs(p[0]-s['cx'])<R and abs(p[1]-s['cy'])<R for p in pts)
parse=lambda sh:[tuple(map(float,p.split(',')[:2])) for p in sh.split()]
for s in sites:s.update(lanes=[],internal=[],juncs=[],conns=[])
owner={}
for e in stream(netp,('edge','junction','connection')):
    a=e.attrib
    if e.tag=='edge':
        f=a.get('function');eid=a['id'];internal=bool(f) or eid.startswith(':')
        for l in e.findall('lane'):
            pts=parse(l.get('shape'));alw,dis=l.get('allow'),l.get('disallow')
            pc=passenger(dict(allow=alw,disallow=dis));d=dict(id=l.get('id'),pts=pts,pc=pc,w=float(l.get('width',3.2)),speed=float(l.get('speed')),allow=alw,fn=f,edge=eid,name=a.get('name',''),to=a.get('to'),lanes=len(e.findall('lane')))
            for s in sites:
                if near(pts,s):(s['internal'] if internal else s['lanes']).append(d)
    elif e.tag=='junction':
        if a['id'].startswith(':'):continue
        pts=parse(a.get('shape','')) if a.get('shape') else [(float(a['x']),float(a['y']))]
        for s in sites:
            if near(pts,s):s['juncs'].append(dict(id=a['id'],type=a['type'],pts=pts,x=float(a['x']),y=float(a['y'])))
    else:
        if a['from'].startswith(':'):continue
        for s in sites:
            s.setdefault('eids',{l['edge'] for l in s['lanes']});s['conns'].append(dict(a)) if a['from'] in s['eids'] else None
osm=load_osm(MAPS/'builds/osm/highway.osm.xml')
t3011=Transformer.from_crs('EPSG:3011','EPSG:4326',always_xy=True)
heads=[]
for f in json.loads((MAPS/'wfs-20261031/Signallykta.geojson').read_text())['features']:
    if f['geometry']:
        c=f['geometry']['coordinates'];lon,lat=t3011.transform(c[0],c[1]);p=f['properties'];heads.append((lon,lat,p.get('anläggnings-id'),p.get('typ') or '',p.get('namn') or ''))
TD=MAPS/'esri-tiles-20261031'
def tile(z,x,y):
    p=TD/f'{z}_{x}_{y}.jpg'
    if not p.exists():
        u=f'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'cars-research/1'}),timeout=60) as r:p.write_bytes(r.read())
        time.sleep(.1)
    return plt.imread(p,format='jpg')
def basemap(ax,x0,y0,x1,y1):
    span=max(x1-x0,y1-y0);z=19
    while z>14 and span/(40075016.68/2**z)>5:z-=1
    w=40075016.68/2**z;o=20037508.34
    xs=range(int((x0+o)//w),int((x1+o)//w)+1);ys=range(int((o-y1)//w),int((o-y0)//w)+1)
    for X in xs:
        for Y in ys:
            try:
                im=tile(z,X,Y);ax.imshow(im,extent=(X*w-o,(X+1)*w-o,o-(Y+1)*w,o-Y*w),zorder=0,interpolation='bilinear')
            except Exception as ex:print('tile',X,Y,ex)
    return z
DIRC={'s':'#111111','r':'#1f77b4','R':'#1f77b4','l':'#d62728','L':'#d62728','t':'#9467bd'}
tlcols=['#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00','#a65628','#f781bf','#17becf','#bcbd22','#666666']
for s in sites:
    cxm,cym=M(s['lon'],s['lat']);k=1/math.cos(math.radians(s['lat']));R=s['r']*k;x0,x1,y0,y1=cxm-R,cxm+R,cym-R,cym+R
    fig,axs=plt.subplots(2,2,figsize=(15,15));(a0,a1),(a2,a3)=axs
    z=basemap(a0,x0,y0,x1,y1);basemap(a1,x0,y0,x1,y1)
    a0.set_title(f"Aerial: Esri World Imagery, z{z} ({2*s['r']:.0f} m square)")
    a1.set_title('Aerial + net lanes + city signal heads (red vehicle, cyan ped, lime bike, orange prio)',fontsize=9)
    seg=[[NM(*p) for p in l['pts']] for l in s['lanes'] if l['pc']];a1.add_collection(LineCollection(seg,colors='yellow',linewidths=.9,zorder=3))
    seg=[[NM(*p) for p in l['pts']] for l in s['lanes'] if not l['pc']];a1.add_collection(LineCollection(seg,colors='magenta',linewidths=.9,zorder=3))
    seg=[[NM(*p) for p in l['pts']] for l in s['internal'] if l['pc']];a1.add_collection(LineCollection(seg,colors='white',linewidths=.4,zorder=3))
    insts=set()
    for lon,lat,inst,ty,nm in heads:
        x,y=M(lon,lat)
        if x0<x<x1 and y0<y<y1:
            c='red' if nm.startswith(('Fordon','F ')) or ty.startswith('Fordon') else 'cyan' if ty.startswith('G') else 'lime' if ty.startswith('Cykel') else 'orange'
            a1.plot(x,y,'o',ms=3.5,mfc=c,mec='k',mew=.3,zorder=5);insts.add(str(inst))
            a2.plot(x,y,'o',ms=2.5,mfc=c,mec='none',zorder=5)
    # OSM
    for wid,w in osm['ways'].items():
        pts=[osm['nodes'].get(n) for n in w['nds']]
        pts=[p for p in pts if p]
        xy=[M(*p) for p in pts]
        if not any(x0<x<x1 and y0<y<y1 for x,y in xy):continue
        t=w['tags'];h=t['highway'];drv=h not in('footway','path','cycleway','steps','pedestrian','service','track','corridor','bridleway','platform','construction','proposed','busway')
        n=t.get('lanes');a2.plot(*zip(*xy),color='#333333' if drv else '#bbbbbb',lw=(1+.7*int(n)) if (n and n.isdigit()) else (1.2 if drv else .5),alpha=.8 if drv else .5,zorder=2,ls='-' if t.get('tunnel') in(None,'no') and t.get('layer','0') in('0',) else '--')
        if drv:
            mid=len(xy)//2;i=max(mid-1,0);(ax_,ay),(bx,by)=xy[i],xy[min(i+1,len(xy)-1)];mx,my=(ax_+bx)/2,(ay+by)/2
            if x0<mx<x1 and y0<my<y1:
                lab=[n and f'L{n}',t.get('turn:lanes') or t.get('turn:lanes:forward') and 'f:'+t['turn:lanes:forward'],t.get('turn:lanes:backward') and 'b:'+t['turn:lanes:backward'],t.get('psv:lanes') and 'psv:'+t['psv:lanes'],t.get('lanes:psv') and 'lpsv'+t['lanes:psv'],t.get('maxspeed'),t.get('junction')]
                lab=' '.join(x for x in lab if x)
                if lab:a2.text(mx,my,lab.replace('through','T').replace('left','L').replace('right','R').replace('slight_','s').replace('none','-'),fontsize=5,color='#003399',zorder=6)
            if t.get('oneway') in('yes','1') and len(xy)>1:a2.annotate('',xy=(bx,by),xytext=(ax_,ay),arrowprops=dict(arrowstyle='->',color='#555555',lw=.7),zorder=2)
    for i,n in osm['tagged'].items():
        x,y=M(n['lon'],n['lat'])
        if x0<x<x1 and y0<y<y1:
            h=n['tags'].get('highway')
            if h=='traffic_signals':a2.plot(x,y,'s',ms=5,mfc='none',mec='red',mew=1,zorder=7)
            elif h=='crossing' and n['tags'].get('crossing')=='traffic_signals':a2.plot(x,y,'^',ms=4,mfc='none',mec='purple',mew=.8,zorder=7)
            elif h in('give_way','stop'):a2.plot(x,y,'v',ms=4,mfc='orange',mec='k',mew=.3,zorder=7)
    a2.set_title('OSM: lanes as width, tags blue, □ traffic_signals, △ signalled crossing, ▽ give_way/stop',fontsize=9)
    # net panel
    for j in s['juncs']:
        if len(j['pts'])>2:a3.add_patch(Polygon([NM(*p) for p in j['pts']],closed=True,fc={'traffic_light':'#ffd6d6','priority':'#e8e8e8','right_before_left':'#d6ecff','zipper':'#d6ffd6'}.get(j['type'],'#eeeeee'),ec='#888888',lw=.4,zorder=1))
    for l in s['lanes']:
        a3.plot(*zip(*[NM(*p) for p in l['pts']]),color='#222222' if l['pc'] else '#cc33cc',lw=1.1,zorder=3,alpha=.9)
    for l in s['internal']:
        if l['pc']:a3.plot(*zip(*[NM(*p) for p in l['pts']]),color='#999999',lw=.45,zorder=2)
    edge_end={l['id']:l for l in s['lanes']}
    tlmap={};seen=set()
    for c in s['conns']:
        lid=f"{c['from']}_{c['fromLane']}";l=edge_end.get(lid)
        if not l:continue
        x,y=NM(*l['pts'][-1]);px,py=NM(*l['pts'][-2]);L=math.hypot(x-px,y-py) or 1;ux,uy=(x-px)/L,(y-py)/L;d=c.get('dir');sc=k*7
        rot={'s':0,'r':-55,'R':-25,'l':55,'L':25,'t':150}.get(d,0);ca,sa=math.cos(math.radians(rot)),math.sin(math.radians(rot))
        vx,vy=ux*ca-uy*sa,ux*sa+uy*ca
        if (lid,d) in seen:continue
        seen.add((lid,d))
        a3.annotate('',xy=(x-ux*2+vx*sc,y-uy*2+vy*sc),xytext=(x-ux*2,y-uy*2),arrowprops=dict(arrowstyle='-|>',color=DIRC.get(d,'k'),lw=.8,mutation_scale=6),zorder=6)
        if c.get('tl'):
            t=c['tl'];tlmap.setdefault(t,tlcols[len(tlmap)%len(tlcols)])
            a3.plot([x],[y],'s',ms=4.5,mfc=tlmap[t],mec='k',mew=.3,zorder=7)
    h=[Line2D([],[],marker='s',ls='',mfc=c,mec='k',ms=5,label=(t if len(t)<26 else t[:24]+'…')) for t,c in list(tlmap.items())[:10]]
    if h:a3.legend(handles=h,fontsize=6,loc='lower left',title=f'{len(tlmap)} net controllers here')
    a3.set_title(f'Net ({tag}): arrows = connections (black s, blue r, red l, purple t), squares = controllers, magenta = no cars',fontsize=9)
    for ax in axs.flat:
        ax.set_xlim(x0,x1);ax.set_ylim(y0,y1);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([])
    fig.suptitle(f"{s['site']}: {s['label']}  {s['lat']:.5f},{s['lon']:.5f}  signal register ids here: {sorted(insts)}  | Imagery: Esri, Vantor, Earthstar Geographics, GIS User Community",fontsize=11)
    fig.tight_layout();out=Path('research/truth/fig/maps07')/f"{s['site']}_{tag}.png";fig.savefig(out,dpi=105);plt.close(fig);print(out,len(s['lanes']),len(s['internal']),len(s['conns']),len(tlmap),len(insts),flush=True)
