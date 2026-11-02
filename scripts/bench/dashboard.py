"""A static page: scorecard, worst gaps first, the climb over time. Built from the result files and the history."""
import html
import json
from pathlib import Path

import score

LEVELS = {'0': 'Is the run even valid?', '1': 'Every car, tick by tick', '2': 'At each kind of junction', '3': 'Along a road', '4': 'Across the city'}
EXPLAIN = {
    'FLOOR': 'As close to reality as one real day is to another',
    'NEAR': 'Within what an odd real day does',
    'CREDIBLE': 'Published-best territory, still further off than real days are',
    'INCONCLUSIVE': 'Median looks fine, but not proven',
    'THIN': 'Close, but too little real data to call it a pass',
    'NO DATA': 'Cannot be judged yet: no real data or no scene. Never a pass',
    'INVALID': 'The benchmark itself cannot judge this',
    'FAIL': 'Further from reality than real days are from each other',
}
ICON = {'FLOOR': '●', 'NEAR': '◐', 'CREDIBLE': '◔', 'INCONCLUSIVE': '?', 'THIN': '…', 'NO DATA': '–', 'INVALID': '!', 'FAIL': '✕'}
CSS = """
.viz-root{color-scheme:light;--surface:#fcfcfb;--page:#f4f3ef;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;--line:#e4e3de;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#008300;--warn:#b07a00;--bad:#d03232;--mute:#8a8984}
@media (prefers-color-scheme:dark){.viz-root{color-scheme:dark;--surface:#1a1a19;--page:#111110;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e85;--line:#34332f;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#3fb950;--warn:#d9a400;--bad:#e66767;--mute:#8f8e85}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,'Segoe UI',sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 6px}h2{font-size:18px;margin:32px 0 8px}h3{font-size:15px;margin:18px 0 6px}
p{margin:6px 0;color:var(--ink2);max-width:75ch}.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:10px}.big{font-size:22px;font-weight:600}.mut{color:var(--ink3);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;color:var(--ink2);font-weight:500;border-bottom:1px solid var(--line);padding:5px 6px}td{border-bottom:1px solid var(--line);padding:5px 6px;vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}.st{white-space:nowrap;font-weight:600}.FLOOR,.NEAR{color:var(--good)}.CREDIBLE,.THIN,.INCONCLUSIVE{color:var(--warn)}.FAIL,.INVALID{color:var(--bad)}.NODATA{color:var(--mute)}
details summary{cursor:pointer}.tabs{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.tabs button{font:inherit;padding:5px 12px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink);cursor:pointer}.tabs button.on{background:var(--ink);color:var(--surface)}
.chart{position:relative}.tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--surface);font-size:12px;padding:4px 7px;border-radius:5px;display:none;white-space:nowrap;z-index:5}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--ink2);margin:4px 0}.key{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}
code{font-size:13px}
"""
JS = r"""
const D=JSON.parse(document.getElementById('data').textContent);
const NS='http://www.w3.org/2000/svg';
const colors={main:'var(--s1)',physics:'var(--s2)',human:'var(--s3)'};
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
function chart(id,title,field,lower){
  const box=document.getElementById(id);const W=Math.min(box.clientWidth||900,980),H=220,m={l:44,r:14,t:24,b:26};
  const runs=D.history.filter(r=>r[field]!=null);
  if(!runs.length){box.textContent='No runs yet.';return}
  const svg=el('svg',{width:W,height:H,viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':title},box);
  const xs=runs.map((r,i)=>i);const n=Math.max(runs.length-1,1);
  const ys=runs.map(r=>r[field]);let y1=Math.max(...ys,1),y0=0;
  const sx=i=>m.l+(W-m.l-m.r)*i/n,sy=v=>H-m.b-(H-m.t-m.b)*(v-y0)/(y1-y0||1);
  for(let k=0;k<=4;k++){const v=y0+(y1-y0)*k/4;el('line',{x1:m.l,x2:W-m.r,y1:sy(v),y2:sy(v),stroke:'var(--line)','stroke-width':1},svg);const t=el('text',{x:m.l-6,y:sy(v)+4,'text-anchor':'end','font-size':11,fill:'var(--ink3)'},svg);t.textContent=(y1<10?v.toFixed(1):Math.round(v))}
  for(const i of (runs.length>1?[0,runs.length-1]:[0])){const t=el('text',{x:sx(i),y:H-8,'text-anchor':i?'end':'start','font-size':11,fill:'var(--ink3)'},svg);t.textContent=runs[i].created.slice(0,16).replace('T',' ')}
  const tip=document.createElement('div');tip.className='tip';box.appendChild(tip);
  for(const d of D.drivers){
    const pts=runs.map((r,i)=>[i,r]).filter(([i,r])=>r.driver===d);if(!pts.length)continue;
    el('path',{d:pts.map(([i,r],k)=>(k?'L':'M')+sx(i)+' '+sy(r[field])).join(' '),fill:'none',stroke:colors[d],'stroke-width':2,'stroke-linecap':'round'},svg);
    for(const [i,r] of pts){const c=el('circle',{cx:sx(i),cy:sy(r[field]),r:4.5,fill:colors[d],stroke:'var(--surface)','stroke-width':2},svg);
      const hit=el('circle',{cx:sx(i),cy:sy(r[field]),r:13,fill:'transparent'},svg);
      hit.addEventListener('mouseenter',()=>{tip.style.display='block';tip.style.left=Math.min(sx(i)+8,W-210)+'px';tip.style.top=(sy(r[field])-30)+'px';tip.textContent=`${r.driver} ${r.mode}, ${r.commit}: ${(+r[field]).toFixed(y1<10?2:0)}`});
      hit.addEventListener('mouseleave',()=>{tip.style.display='none'})}
    const [li,lr]=pts[pts.length-1];const lab=el('text',{x:li>runs.length/2?sx(li)-4:sx(li)+4,y:sy(lr[field])-9,'text-anchor':li>runs.length/2?'end':'start','font-size':12,fill:'var(--ink2)'},svg);lab.textContent=d;
  }
}
chart('c1','Metrics at the real-data noise floor or near it, per run','pass');chart('c2','Metrics failing, per run','fail');chart('c3','Worst gap, per run','worst');
for(const b of document.querySelectorAll('.tabs button')){b.addEventListener('click',()=>{for(const x of document.querySelectorAll('.tabs button'))x.classList.toggle('on',x===b);for(const p of document.querySelectorAll('.pane'))p.style.display=p.dataset.d===b.dataset.d?'':'none'})}
"""


def num(x, d=2):
    return '' if x is None else (f'{x:.{d}f}' if abs(x) < 100 else f'{x:.0f}')


def status(s):
    return f'<span class="st {s.replace(" ", "")}">{ICON[s]} {s}</span>'


def counts(res):
    n = {}
    for m in res['metrics'].values():
        n[m['status']] = n.get(m['status'], 0) + 1
    return n


def cell_rows(m):
    rows = []
    for sub, c in sorted(m['cells'].items(), key=lambda kv: -(kv[1].get('z') or 0)):
        val = f"value {num(c['value'])}" if c.get('value') is not None else ''
        rows.append(f"<tr><td>{html.escape(sub)}</td><td>{status(c['status'])}</td><td class=n>{num(c.get('S'), 3)}</td><td class=n>{num(c.get('F'), 3)}</td><td class=n>{num(c.get('N'), 3)}</td><td class=n>{num(c.get('z'))}</td><td>{val} {html.escape(c.get('note') or '')}</td></tr>")
    return '<table><tr><th>Part</th><th>Status</th><th class=n>Gap</th><th class=n>Ruler</th><th class=n>Null</th><th class=n>Gap ÷ ruler</th><th>Note</th></tr>' + ''.join(rows) + '</table>'


def scorecard(res):
    ms = list(res['metrics'].values())
    gaps = sorted([m for m in ms if m['z'] is not None and m['status'] not in ('FLOOR', 'NO DATA')], key=lambda m: -m['z'])
    out = [f"<p class=mut>{html.escape(res['driver'])}, {res['mode']} mode. Run <code>{res['run_id']}</code>, commit <code>{res['commit'][:8]}</code>, binary <code>{res['binary_sha']}</code>, configuration <code>{res['config_hash']}</code>, seeds {res['seeds']}.</p>"]
    n = counts(res)
    out.append('<div class=card>' + ' &nbsp; '.join(f'{status(s)} {n[s]}' for s in score.ORDER[::-1] if n.get(s)) + '</div>')
    out.append('<div class=grid3>')
    for lv, x in res['levels'].items():
        c = x['counts']
        out.append(f"<div class=card><div class=mut>Level {lv}</div><b>{LEVELS[lv]}</b><div>{status(x['status'])}</div><div class=mut>{c.get('FLOOR', 0) + c.get('NEAR', 0)} passing, {c.get('FAIL', 0)} failing, {c.get('NO DATA', 0)} no data. A level is as good as its worst metric.</div></div>")
    out.append('</div><h3>Worst gaps first</h3><p>Gap ÷ ruler: 1 means as far from reality as real days are from each other. 10 means ten times further.</p>')
    out.append('<div class=card><table><tr><th>Metric</th><th>Status</th><th class=n>Gap ÷ ruler</th><th>What it asks</th></tr>')
    for m in gaps[:15]:
        out.append(f"<tr><td><b>{m['id']}</b> {html.escape(m['name'])}</td><td>{status(m['status'])}</td><td class=n>{num(m['z'])}</td><td>{html.escape(m['plain'])}</td></tr>")
    out.append('</table></div><h3>Every metric</h3>')
    for lv, x in res['levels'].items():
        out.append(f'<h3>Level {lv}: {LEVELS[lv]}</h3><div class=card>')
        for m in [m for m in ms if str(m['level']) == lv]:
            tag = {'P': 'must pass', 'W': 'witness: must pass, never tuned on', 'D': 'reported only'}[m['tag']]
            out.append(f"<details><summary><b>{m['id']}</b> {html.escape(m['name'])} {status(m['status'])} <span class=mut>{num(m['z'])}</span></summary><p>{html.escape(m['plain'])}. <span class=mut>{tag}, gate check: {m['gate']}.</span></p>{cell_rows(m)}</details>")
        out.append('</div>')
    return ''.join(out)


def knownbad_section(path):
    if not Path(path).exists():
        return '<p>Known-bad configurations not run yet.</p>'
    k = json.loads(Path(path).read_text())
    caught = sum(1 for r in k['rows'] if r['caught'])
    rows = ''.join(f"<tr><td class=n>{r['n']}</td><td>{html.escape(r['name'])}</td><td>{'<b class=FLOOR>caught</b>' if r['caught'] else '<b class=FAIL>MISSED</b>'}</td><td>{html.escape(r.get('by', ''))}</td><td>{html.escape(r.get('note', ''))}</td></tr>" for r in k['rows'])
    return f"<p>Each is a configuration known to be wrong. The benchmark must fail each one on the named metric, and do so beyond the baseline driver's own value. {caught} of {len(k['rows'])} caught.</p><div class=card><table><tr><th class=n>#</th><th>Configuration</th><th>Result</th><th>Caught by</th><th>Note</th></tr>{rows}</table></div>"


def build(res_dir, hist, serve, knownbad=None):
    serve = Path(serve)
    serve.mkdir(parents=True, exist_ok=True)
    runs = [json.loads(p.read_text()) for p in sorted(Path(res_dir).glob('*.json'))]
    latest = {}
    for r in runs:
        if r.get('overrides'):
            continue
        k = r['driver']
        if k not in latest or (r['mode'] == 'full', r['run_id']) >= (latest[k]['mode'] == 'full', latest[k]['run_id']):
            latest[k] = r
    history = []
    if Path(hist).exists():
        for line in Path(hist).read_text().splitlines():
            r = json.loads(line)
            st = list(r['statuses'].values())
            zs = [v for v in r['zs'].values() if v is not None]
            history.append(dict(driver=r['driver'], mode=r['mode'], commit=r['commit'][:8], run=r['run_id'], created=r['created'], **{'pass': sum(s in score.PASSING for s in st), 'fail': sum(s == 'FAIL' for s in st), 'worst': min(max(zs), 100.0) if zs else None}))
    drivers = [d for d in ('main', 'physics', 'human') if d in latest]
    tabs = ''.join(f'<button data-d="{d}" class="{"on" if i == 0 else ""}">{d}</button>' for i, d in enumerate(drivers))
    panes = ''.join(f'<div class=pane data-d="{d}" style="{"" if i == 0 else "display:none"}">{scorecard(latest[d])}</div>' for i, d in enumerate(drivers))
    legend = ''.join(f'<span><span class=key style="background:var(--s{i + 1})"></span>{d}</span>' for i, d in enumerate(['main', 'physics', 'human']))
    summary = ''
    for d in drivers:
        n = counts(latest[d])
        summary += f"<div class=card><div class=mut>{d}, {latest[d]['mode']} mode</div><div class=big>{n.get('FLOOR', 0) + n.get('NEAR', 0)} pass, {n.get('FAIL', 0)} fail</div><div class=mut>of {len(latest[d]['metrics'])} metrics; {n.get('NO DATA', 0)} have no data yet and count as no pass</div></div>"
    key = ''.join(f'<tr><td>{status(s)}</td><td>{html.escape(EXPLAIN[s])}</td></tr>' for s in score.ORDER[::-1])
    data = json.dumps(dict(history=history, drivers=drivers))
    table = ''.join(f"<tr><td>{h['created'][:16]}</td><td>{h['driver']}</td><td>{h['mode']}</td><td><code>{h['commit']}</code></td><td class=n>{h['pass']}</td><td class=n>{h['fail']}</td><td class=n>{num(h['worst'])}</td></tr>" for h in history[::-1][:40])
    page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Is the simulation true to life?</title><style>{CSS}</style>
<div class="viz-root"><div class=wrap>
<h1>Is the simulation true to life?</h1>
<p>A simulation is true to life when real data can't tell it apart from another real day, at every scale at once, with one set of settings, on data it never saw. Each metric below compares one simulated day with one real day. The ruler is how far real days differ from each other, and each must also beat a model that knows nothing. <b>There is no total score</b>, because a total would let a good number hide a bad one.</p>
<div class=grid3>{summary}</div>
<h2>Progress</h2><div class=legend>{legend}</div>
<div class=card><b>Metrics passing, per run</b> <span class=mut>higher is better</span><div class=chart id=c1></div></div>
<div class=card><b>Metrics failing, per run</b> <span class=mut>lower is better</span><div class=chart id=c2></div></div>
<div class=card><b>Worst gap, per run</b> <span class=mut>gap ÷ ruler of the worst metric, capped at 100, lower is better</span><div class=chart id=c3></div></div>
<details class=card><summary>Runs as a table</summary><table><tr><th>When</th><th>Driver</th><th>Mode</th><th>Commit</th><th class=n>Pass</th><th class=n>Fail</th><th class=n>Worst gap</th></tr>{table}</table></details>
<h2>What the words mean</h2><div class=card><table>{key}</table></div>
<h2>Scorecards</h2><div class=tabs>{tabs}</div>{panes}
<h2>Can the benchmark catch a wrong simulation?</h2>{knownbad_section(knownbad or Path(res_dir).parent / 'knownbad.json')}
</div></div><script type="application/json" id=data>{data}</script><script>{JS}</script>"""
    (serve / 'index.html').write_text(page)
