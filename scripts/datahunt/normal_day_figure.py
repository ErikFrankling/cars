import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O='research/truth/data-hunt/14-data/'
T=json.load(open(O+'tomtom_summary.json'))
g=T['groups']['europe_0.5_4M/metro']['q']; c=T['groups']['europe_0.5_4M/center']['q']
for k in ('hw_ampm_over_fv','nh_ampm_over_fv','weekend_over_tue_thu_midday','worst_c','base_c','ampm_c','hw_fv','nh_fv'):
    print('metro',k,g.get(k)); print('center',k,c.get(k))
print('parsed',T['cities_parsed'])
for k in ('stockholm','berlin','hamburg','munich','vienna','copenhagen','oslo','helsinki','gothenburg','zurich','amsterdam','prague','london','paris'):
    x=T['cities'].get(k)
    if not x: print(k,'missing'); continue
    m=x['metro']; ce=x['center']
    print(k,x['population'],'M',m['base_v'],m['night_v'].__round__(1),m['midday_v'].__round__(1),m['worst_am_v'].__round__(1),m['worst_pm_v'].__round__(1),round(m['worst_over_night'],2),round(m['worst_over_midday'],2),'c30',m['hours_c_over_30'],'hw',m.get('hw_v'),m.get('hw_ampm_v'),'nh',m.get('nh_v'),m.get('nh_ampm_v'),'hwshare',round(m.get('hw_km_share',0),2),'| C',ce['base_v'],ce.get('ampm_v'),round(ce['worst_over_night'],2))
# all full-day runs
rows=[json.loads(l) for l in open('/home/erikf/projects/personal/cars-data/truth/stockholm/factorial/metrics.jsonl')]
print(len(rows))
fd=[r for r in rows if r.get('end')==86400 and r.get('speed_by_hour')]
for r in fd:
    sp=[r['speed_by_hour'][str(h)] for h in range(24) if r['speed_by_hour'].get(str(h))]
    print(r['name'],r['scheduled'],round((r.get('vkm') or 0)/1e6,2),'M',round(r['speed'],1),'worst/best',round(min(sp)/max(sp),2),'worst',round(min(sp),1),'peakrun',r['peak_running'],'tp',r['teleports'])
v=json.load(open(O+'v2_day2.json')); b=json.load(open(O+'berlin_day.json'))
for n,r in (('v2',v),('berlin',b)):
    sc=r['speed_by_class_hour']
    print(n,'motorway peak/night',round(min(sc['motorway'][7],sc['motorway'][8],sc['motorway'][16],sc['motorway'][17])/sum(sc['motorway'][2:5])*3,2),'tertiary',round(min(sc['tertiary'][7],sc['tertiary'][8],sc['tertiary'][16],sc['tertiary'][17])/sum(sc['tertiary'][2:5])*3,2),'local',round(min(sc['local'][7],sc['local'][8],sc['local'][16],sc['local'][17])/sum(sc['local'][2:5])*3,2))
Z=json.load(open(O+'zurich.json'))['network_hour_mean']
sv=[11.8,7.4]
SW=[16.8,10.2,7.1,6.5,10.9,43.6,122.7,149.4,124.8,113.8,126.6,141.3,154.5,160.0,174.0,204.5,228.0,183.9,131.6,93.2,74.2,57.6,39.0,25.8]
GB=[12.3,8.1,6.8,7.8,13.4,39.4,94.4,171.7,191.9,148.8,139.6,144.3,150.9,152.6,165.8,189.5,208.2,205.4,155.1,108.4,75.9,56.2,39.8,22.3]
BE=None
import csv
from collections import defaultdict
q=defaultdict(lambda:[None]*24)
for r in csv.DictReader(open('research/truth/berlin-review/detector_all_hourly.csv')):
    q[r['site']][int(r['hour'])]=float(r['real'])
BE=[sum(q[s][h] for s in q if None not in q[s]) for h in range(24)]
share=lambda a:[100*x/sum(a) for x in a]
INK='#0b0b0b'; INK2='#52514e'; GRID='#e4e3df'; BG='#fcfcfb'
SIM='#eb6834'; REAL='#2a78d6'; R2='#1baf7a'; R3='#6250d6'; R4='#eda100'
plt.rcParams.update({'font.size':11,'font.family':'DejaVu Sans','axes.edgecolor':GRID,'text.color':INK,'axes.labelcolor':INK2,'xtick.color':INK2,'ytick.color':INK2})
fig,ax=plt.subplots(1,3,figsize=(15,4.8),dpi=130,facecolor=BG)
H=list(range(24))
def base(a,t,y):
    a.set_facecolor(BG); a.grid(axis='y',color=GRID,lw=.8); a.set_axisbelow(True)
    for s in('top','right','left'): a.spines[s].set_visible(False)
    a.set_title(t,loc='left',fontsize=12,color=INK,pad=10); a.set_ylabel(y); a.set_xlabel('Hour of day'); a.set_xticks(range(0,25,4)); a.tick_params(length=0)
st=T['cities']['stockholm']['metro_hourly_v']; be=T['cities']['berlin']['metro_hourly_v']
a=ax[0]; base(a,'Stockholm: speed by hour (Tue-Thu)','km/h')
a.plot(H,st,color=REAL,lw=2,label='TomTom 2025, metro'); a.plot(H,T['cities']['stockholm']['center_hourly_v'],color=R2,lw=2,label='TomTom 2025, city'); a.plot(H,v['speed_by_hour'],color=SIM,lw=2,label='cars v2_day2'); a.set_ylim(0,65); a.legend(frameon=False,fontsize=9.5,loc='lower left',ncol=1)
a=ax[1]; base(a,'Berlin: speed by hour (Tue-Thu)','km/h')
a.plot(H,be,color=REAL,lw=2,label='TomTom 2025, metro'); a.plot(H,T['cities']['berlin']['center_hourly_v'],color=R2,lw=2,label='TomTom 2025, city'); a.plot(H,b['speed_by_hour'],color=SIM,lw=2,label='cars Berlin day'); a.set_ylim(0,65); a.legend(frameon=False,fontsize=9.5,loc='upper right')
a=ax[2]; base(a,'Flow by hour, share of daily vehicle-km or counts','% of day')
a.plot(H,share(Z),color=REAL,lw=2,label='Zurich, 154 counters'); a.plot(H,share(BE),color=R2,lw=2,label='Berlin detectors'); a.plot(H,share(GB),color=R3,lw=2,label='Great Britain, Wed'); a.plot(H,share(SW),color=R4,lw=2,label='Sweden, urban index'); a.plot(H,share(v['vkm_by_hour']),color=SIM,lw=2.4,label='cars v2_day2'); a.legend(frameon=False,fontsize=9.5,loc='upper left'); a.set_ylim(0,13.5)
fig.tight_layout(); fig.savefig('research/truth/fig/normal-day-check.png',facecolor=BG)
print('saved')
