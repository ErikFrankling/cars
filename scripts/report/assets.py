"""Page furniture for the big report: styles and the chart, video and filter code."""

CSS = r"""
@font-face{font-family:Overpass;src:url(fonts/overpass-regular.otf);font-weight:400;font-display:swap}
@font-face{font-family:Overpass;src:url(fonts/overpass-italic.otf);font-weight:400;font-style:italic;font-display:swap}
@font-face{font-family:Overpass;src:url(fonts/overpass-semibold.otf);font-weight:600;font-display:swap}
@font-face{font-family:Overpass;src:url(fonts/overpass-bold.otf);font-weight:700;font-display:swap}
@font-face{font-family:Overpass;src:url(fonts/overpass-extrabold.otf);font-weight:800;font-display:swap}
:root{--asphalt:#23272b;--asphalt2:#2c3136;--asphalt3:#383e44;--paint:#f4f3ee;--ink2:#c5c8c7;--ink3:#9aa4ad;--yellow:#f5c518;--sign:#0b4f9e;
--red:#ff5a52;--amber:#ffb627;--green:#3ddc84;--ours:#3987e5;--human:#d95926;--av:#199e70;--alt:#9085e9;--old:#9aa4ad;--real:#f4f3ee}
*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--asphalt);color:var(--paint);font-family:Overpass,system-ui,sans-serif;font-size:18px;line-height:1.55;font-variant-numeric:tabular-nums}
a{color:var(--yellow)}
a:focus-visible,button:focus-visible,summary:focus-visible,input:focus-visible{outline:3px solid var(--yellow);outline-offset:2px}
.page{max-width:760px;margin:0 auto;padding:0 18px}
.wide{max-width:1040px;margin-left:auto;margin-right:auto}
h3{font-size:1.45rem;line-height:1.2;font-weight:800;margin:2.4rem 0 .6rem}
h4{font-size:1.1rem;font-weight:700;margin:1.8rem 0 .4rem}
p{margin:.7rem 0}
.answer{font-size:1.32rem;line-height:1.38;font-weight:600;margin:1.4rem 0 1.2rem}
.small{font-size:.86rem;color:var(--ink2)}

/* top bar: a stretch of road with a car on it */
.bar{position:sticky;top:0;z-index:20;background:var(--asphalt);border-bottom:1px solid #000}
.bar-in{display:flex;align-items:center;gap:10px;padding:8px 14px;max-width:1040px;margin:0 auto}
.bar-title{flex:1;min-width:0;font-weight:700;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar button{font:inherit;font-weight:700;font-size:.9rem;background:var(--sign);color:#fff;border:2px solid #fff;border-radius:7px;padding:3px 12px 1px;cursor:pointer}
.road{position:relative;height:12px;background:#17191c;border-top:1px solid #4a5056}
.road:before{content:"";position:absolute;left:0;right:0;top:5px;height:2px;background:repeating-linear-gradient(90deg,var(--paint) 0 14px,transparent 14px 34px);opacity:.75}
.car{position:absolute;top:2px;left:0;width:18px;height:8px;background:var(--yellow);border-radius:3px 4px 4px 3px;margin-left:-9px}
.route{position:fixed;inset:0;z-index:30;background:rgba(10,12,14,.72);display:none}
.route.open{display:block}
.route-in{position:absolute;right:0;top:0;bottom:0;width:min(420px,92vw);background:var(--asphalt2);overflow:auto;padding:14px}
.route a{display:flex;gap:12px;align-items:baseline;padding:10px 8px;border-bottom:1px solid var(--asphalt3);color:var(--paint);text-decoration:none;font-weight:600;line-height:1.25}
.route a b{flex:none;min-width:2.4em;color:var(--yellow)}
.route button{font:inherit;font-weight:700;background:none;color:var(--paint);border:2px solid var(--ink3);border-radius:7px;padding:3px 12px 1px;float:right;cursor:pointer}

/* hero */
.hero{position:relative;min-height:88vh;display:flex;align-items:flex-end;overflow:hidden;background:#101214}
.hero video,.hero>img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.72}
.hero:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(35,39,43,0) 35%,rgba(35,39,43,.92) 88%,var(--asphalt) 100%)}
.hero-in{position:relative;z-index:1;padding:0 18px 30px;max-width:1040px;margin:0 auto;width:100%}
.hero h1{font-size:clamp(3.1rem,13.5vw,8.6rem);line-height:.9;font-weight:800;letter-spacing:-.025em;margin:0 0 .22em}
.hero p{font-size:clamp(1.15rem,3.6vw,1.55rem);line-height:1.32;max-width:34em;margin:.3em 0 0;font-weight:600}
.hero .when{font-size:.9rem;font-weight:400;color:var(--ink2);margin-top:1em}

/* the gantry over each chapter */
.gantry{margin:4.6rem -18px 1.2rem;padding:0 18px;position:relative;scroll-margin-top:60px}
.gantry:before{content:"";position:absolute;left:0;right:0;top:14px;height:9px;background:#6b7278;box-shadow:0 2px 0 #000}
.sign{position:relative;background:var(--sign);color:#fff;border-radius:11px;padding:4px;box-shadow:0 5px 0 rgba(0,0,0,.45)}
.sign-in{border:3px solid #fff;border-radius:8px;padding:14px 16px 12px;position:relative}
.sign h2{font-size:clamp(1.75rem,6.6vw,2.7rem);line-height:1.04;font-weight:800;margin:0;padding-right:3.4em;letter-spacing:-.01em}
.sign .dest{margin:.45em 0 0;font-size:1.02rem;line-height:1.3;font-weight:600;opacity:.95}
.sign .exit{position:absolute;top:-3px;right:-3px;background:#fff;color:var(--sign);font-weight:800;font-size:.95rem;padding:5px 11px 2px;border-radius:0 8px 0 8px}

/* traffic-light evidence */
.key{display:grid;gap:8px;margin:1rem 0 0}
.key div{display:flex;gap:10px;align-items:center;font-size:.95rem;line-height:1.25}
.lamp{flex:none;width:17px;height:43px;background:#0c0d0f;border-radius:5px;padding:2.5px 0;display:flex;flex-direction:column;align-items:center;justify-content:space-between;border:1px solid #4a5056}
.lamp i{display:block;width:10.5px;height:10.5px;border-radius:50%;background:#2b2e32}
.lamp.r i:nth-child(1){background:var(--red);box-shadow:0 0 7px var(--red)}
.lamp.a i:nth-child(2){background:var(--amber);box-shadow:0 0 7px var(--amber)}
.lamp.g i:nth-child(3){background:var(--green);box-shadow:0 0 7px var(--green)}
.facts{list-style:none;padding:0;margin:1rem 0}
.facts li{display:flex;gap:12px;padding:.68rem 0;border-top:1px solid var(--asphalt3)}
.facts li:last-child{border-bottom:1px solid var(--asphalt3)}
.facts .bk{flex:none;width:17px;height:17px;border:2px solid var(--ink3);border-radius:3px;margin:4px 0 0;position:relative}
.facts .bk:after{content:"";position:absolute;left:6px;top:0;bottom:0;width:1px;background:var(--ink3)}
.tag{display:inline-block;font-size:.76rem;line-height:1.3;color:var(--ink2);border:1px solid #5c636a;border-radius:4px;padding:2px 5px 0;margin-left:3px;white-space:nowrap}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}

/* the verdict board */
.board{display:grid;gap:18px;margin:1.6rem 0}
.panel{background:var(--asphalt2);border-radius:13px;padding:16px 16px 8px;position:relative}
.panel h3{margin:0 0 .2rem;font-size:1.3rem}
.panel .head{display:flex;gap:12px;align-items:center;margin-bottom:.3rem}
.panel .big{transform:scale(1.28);transform-origin:left center;margin-right:6px}
.panel.g{box-shadow:inset 0 3px 0 var(--green)}.panel.a{box-shadow:inset 0 3px 0 var(--amber)}.panel.r{box-shadow:inset 0 3px 0 var(--red)}
.panel ul{list-style:none;padding:0;margin:.5rem 0}
.panel li{padding:.62rem 0;border-top:1px solid var(--asphalt3);line-height:1.38;font-size:1.02rem}
.panel li b{font-weight:700}

/* stats */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px 18px;margin:1.5rem 0}
.stat b{display:block;font-size:2.35rem;line-height:1;font-weight:800;letter-spacing:-.01em}
.stat span{display:block;font-size:.92rem;line-height:1.28;color:var(--ink2);margin-top:.3rem}
.vs{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:1.3rem 0}
.vs>div{background:var(--asphalt2);border-radius:11px;padding:12px 14px}
.vs b{display:block;font-size:2.1rem;line-height:1.02;font-weight:800}
.vs span{display:block;font-size:.9rem;line-height:1.25;color:var(--ink2);margin-top:.3rem}

/* callouts */
.note{border-left:4px solid var(--yellow);padding:.2rem 0 .2rem 14px;margin:1.3rem 0}
.note.bad{border-color:var(--red)}
.note b:first-child{display:block}
ol.steps{padding-left:1.4em}ol.steps li{margin:.45rem 0}

/* charts */
.chart{margin:1.6rem 0 1.9rem;position:relative}
.chart .ct{font-weight:700;font-size:1.05rem;line-height:1.25;margin-bottom:.15rem}
.chart .cs{font-size:.88rem;line-height:1.3;color:var(--ink2);margin-bottom:.55rem}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.84rem;color:var(--ink2);margin:0 0 6px;line-height:1.3}
.legend i{display:inline-block;width:15px;height:4px;border-radius:2px;margin-right:6px;vertical-align:3px}
.legend i.d{background-image:repeating-linear-gradient(90deg,currentColor 0 4px,transparent 4px 7px)!important}
.chart svg{display:block;width:100%;overflow:visible;touch-action:pan-y}
.chart text{font-family:Overpass,system-ui,sans-serif;fill:var(--ink2);font-size:12px}
.tip{position:absolute;z-index:5;pointer-events:none;background:#101214;border:1px solid #5c636a;border-radius:7px;padding:6px 9px 4px;font-size:.82rem;line-height:1.35;display:none;max-width:260px;box-shadow:0 3px 10px rgba(0,0,0,.5)}
.tip b{display:block;font-weight:700}
.tip i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}
details.nums{margin-top:.3rem;font-size:.86rem}
details.nums summary,details.all summary{cursor:pointer;color:var(--ink2)}
.tbl{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:1rem 0}
table{border-collapse:collapse;width:100%;font-size:.92rem;line-height:1.3}
th,td{text-align:right;padding:6px 8px 4px;border-bottom:1px solid var(--asphalt3);white-space:nowrap}
th{font-weight:600;color:var(--ink2)}
th:first-child,td:first-child{text-align:left;white-space:normal;min-width:7em}
td.w,th.w{white-space:normal;text-align:left;min-width:12em}

/* video */
.clip{margin:1.5rem 0}
.clip .frame{position:relative;display:block;width:100%;padding:0;border:0;background:#101214;border-radius:9px;overflow:hidden;cursor:pointer}
.clip img,.clip video{display:block;width:100%;height:auto}
.clip .play{position:absolute;left:50%;top:50%;width:68px;height:68px;margin:-34px 0 0 -34px;border-radius:50%;background:rgba(11,79,158,.94);border:3px solid #fff}
.clip .play:after{content:"";position:absolute;left:25px;top:17px;border-left:21px solid #fff;border-top:13px solid transparent;border-bottom:13px solid transparent}
.clip .ti{font-weight:700;margin:.5rem 0 0;line-height:1.25}
.clip .ca{font-size:.93rem;line-height:1.36;color:var(--ink2);margin:.15rem 0 0}
.clips2{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:4px 18px}
.clips2 .clip{margin:.9rem 0}
.clips2 .play{transform:scale(.72)}
figure{margin:1.5rem 0}
figure img{display:block;width:100%;height:auto;border-radius:8px;background:#fff}
figcaption{font-size:.9rem;line-height:1.35;color:var(--ink2);margin-top:.4rem}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin:.8rem 0 1rem}
.chips button{font:inherit;font-size:.88rem;font-weight:600;color:var(--paint);background:var(--asphalt2);border:1px solid #5c636a;border-radius:18px;padding:5px 12px 2px;cursor:pointer}
.chips button[aria-pressed=true]{background:var(--sign);border-color:#fff}
input.q{font:inherit;width:100%;padding:9px 11px 6px;border-radius:8px;border:1px solid #5c636a;background:var(--asphalt2);color:var(--paint);margin:.6rem 0}
.sim{padding:.6rem 0;border-top:1px solid var(--asphalt3);font-size:.93rem;line-height:1.35}
.sim b{font-weight:700}.sim div{color:var(--ink2);font-size:.84rem}
details.all{margin:1rem 0;border-top:1px solid var(--asphalt3);padding-top:.6rem}
details.all>summary{font-weight:700;font-size:1.08rem;color:var(--paint)}
footer{margin:5rem 0 4rem;font-size:.88rem;color:var(--ink2)}
@media (min-width:860px){.board{grid-template-columns:1fr 1fr 1fr;max-width:1040px}.boardwrap{margin-left:calc(50% - min(50vw,520px) + 18px);margin-right:calc(50% - min(50vw,520px) + 18px)}
.widen{margin-left:-110px;margin-right:-110px}}
@media (max-width:420px){body{font-size:17px}.sign .exit{font-size:.82rem;padding:4px 8px 1px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

JS = r"""
const COL={ours:'#3987e5',human:'#d95926',av:'#199e70',alt:'#9085e9',old:'#9aa4ad',real:'#f4f3ee'};
const NS='http://www.w3.org/2000/svg';
const fmt=v=>v==null?'none':(typeof v==='number'?v.toLocaleString('en-US',{maximumFractionDigits:3}):v);
const fmtS=v=>{if(v==null)return'';const a=Math.abs(v);if(a>=1e6)return(v/1e6).toFixed(a>=1e7?0:1)+'M';if(a>=10000)return Math.round(v/1000)+'k';return fmt(v)};
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')}
function niceTicks(lo,hi,n){const st=(hi-lo)/n,m=Math.pow(10,Math.floor(Math.log10(st))),e=st/m,k=e<1.5?1:e<3?2:e<7?5:10,s=k*m,o=[];for(let t=Math.ceil(lo/s)*s;t<=hi+s*.001;t+=s)o.push(+t.toFixed(10));return o}
function logTicks(lo,hi){const o=[],few=Math.log10(hi/lo)<2.2;for(let p=Math.floor(Math.log10(lo));p<=Math.ceil(Math.log10(hi));p++){for(const k of few?[1,2,5]:[1]){const t=k*Math.pow(10,p);if(t>=lo*.999&&t<=hi*1.001)o.push(t)}}return o}
function initChart(box){
 const S=JSON.parse(box.dataset.spec),host=box.querySelector('.plot'),tip=box.querySelector('.tip');
 function render(){
  const W=Math.max(host.clientWidth,260);host.innerHTML='';
  if(S.t==='hbars')return hbars(W);
  const n=S.x.length,all=S.s.flatMap(s=>s.v).filter(v=>v!=null);
  if(S.ref)all.push(S.ref.v);
  const H=S.h||(W<520?250:320),m={l:50,r:12,t:10,b:S.xl?46:28};
  const iw=W-m.l-m.r,ih=H-m.t-m.b;
  let lo=S.log?Math.min(...all.filter(v=>v>0))*.8:Math.min(0,...all),hi=Math.max(...all)*(S.log?1.25:1.06);
  if(S.ymin!=null)lo=S.ymin;if(S.ymax!=null)hi=S.ymax;
  const Y=v=>S.log?m.t+ih*(1-(Math.log10(Math.max(v,lo))-Math.log10(lo))/(Math.log10(hi)-Math.log10(lo))):m.t+ih*(1-(v-lo)/(hi-lo));
  const num=S.xn,xs=num?S.x.map(Number):null,xlo=num?Math.min(...xs):0,xhi=num?Math.max(...xs):0;
  const LX=v=>S.xlog?(Math.log10(v)-Math.log10(xlo))/(Math.log10(xhi)-Math.log10(xlo)):(v-xlo)/(xhi-xlo);
  const X=i=>S.t==='bars'?m.l+iw*(i+.5)/n:(num?m.l+iw*LX(xs[i]):m.l+iw*(n>1?i/(n-1):.5));
  let g='';
  for(const t of (S.log?logTicks(lo,hi):niceTicks(lo,hi,W<520?4:5))){g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(t)}" y2="${Y(t)}" stroke="rgba(255,255,255,.1)"/><text x="${m.l-7}" y="${Y(t)+4}" text-anchor="end">${fmtS(t)}</text>`}
  const every=Math.max(1,Math.ceil(n/(W<520?6:12)));
  S.x.forEach((x,i)=>{if(i%every&&i!==n-1)return;if(i===n-1&&(n-1)%every&&n>7)return;const parts=String(typeof x==='number'&&x>=10000?fmtS(x):x).split('|');parts.forEach((p,k)=>{g+=`<text x="${X(i)}" y="${H-m.b+16+k*13}" text-anchor="middle">${esc(p)}</text>`})});
  if(S.xl)g+=`<text x="${m.l+iw/2}" y="${H-3}" text-anchor="middle">${esc(S.xl)}</text>`;
  if(S.ref){g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(S.ref.v)}" y2="${Y(S.ref.v)}" stroke="#f4f3ee" stroke-width="1.5" stroke-dasharray="5 4"/><text x="${W-m.r}" y="${Y(S.ref.v)-6}" text-anchor="end" style="fill:#f4f3ee">${esc(S.ref.l)}</text>`}
  if(S.t==='bars'){
   const k=S.s.length,slot=iw/n*.84,gap=Math.min(2,slot/k*.2),bw=Math.min(slot/k-gap,34);
   S.s.forEach((s,j)=>{s.v.forEach((v,i)=>{if(v==null)return;const x=X(i)-(k*(bw+gap)-gap)/2+j*(bw+gap),y=Y(v),b=Y(S.log?lo:0),h=Math.max(b-y,1),r=Math.min(3.5,bw/2,h);
    g+=`<path d="M${x} ${b}V${y+r}Q${x} ${y} ${x+r} ${y}H${x+bw-r}Q${x+bw} ${y} ${x+bw} ${y+r}V${b}Z" fill="${COL[s.c]}"/>`})});
   if(lo<0)g+=`<line x1="${m.l}" x2="${W-m.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="#9aa4ad"/>`;
  }else{
   S.s.forEach(s=>{let d='',on=false;s.v.forEach((v,i)=>{if(v==null||(S.log&&v<=0)){on=false;return}d+=(on?'L':'M')+X(i)+' '+Y(v);on=true});
    g+=`<path d="${d}" fill="none" stroke="${COL[s.c]}" stroke-width="${s.c==='real'?3:2.2}" stroke-linejoin="round" stroke-linecap="round" ${s.d?'stroke-dasharray="6 5"':''}/>`;
    if(n<=16)s.v.forEach((v,i)=>{if(v==null||(S.log&&v<=0))return;g+=`<circle cx="${X(i)}" cy="${Y(v)}" r="3.6" fill="${COL[s.c]}" stroke="#23272b" stroke-width="1.5"/>`});
   });
  }
  g+=`<line class="cross" y1="${m.t}" y2="${H-m.b}" stroke="#f4f3ee" stroke-opacity=".5" style="display:none"/>`;
  host.innerHTML=`<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="${esc(S.title)}">${g}</svg>`;
  const svg=host.firstChild,cross=svg.querySelector('.cross');
  const pick=e=>{const r=svg.getBoundingClientRect(),px=e.clientX-r.left;let b=0,d=1e9;for(let i=0;i<n;i++){const q=Math.abs(X(i)-px);if(q<d){d=q;b=i}}return b};
  const show=e=>{const i=pick(e),r=box.getBoundingClientRect(),s=svg.getBoundingClientRect();cross.setAttribute('x1',X(i));cross.setAttribute('x2',X(i));cross.style.display='';
   tip.innerHTML=`<b>${esc(String(S.x[i]).replace('|',' '))}${S.xl?' '+esc(S.xu||''):''}</b>`+S.s.map(q=>`<div><i style="background:${COL[q.c]}"></i>${esc(q.n)}: ${fmt(q.v[i])}</div>`).join('');
   tip.style.display='block';const tw=tip.offsetWidth;let left=X(i)+s.left-r.left+12;if(left+tw>r.width)left=X(i)+s.left-r.left-tw-12;tip.style.left=Math.max(0,left)+'px';tip.style.top=(s.top-r.top+8)+'px'};
  svg.addEventListener('pointermove',show);svg.addEventListener('pointerdown',show);
  svg.addEventListener('pointerleave',()=>{tip.style.display='none';cross.style.display='none'});
 }
 function hbars(W){
  const rows=S.x.length,k=S.s.length,bh=k>1?11:16,gap=3,rowH=20+k*(bh+gap)+11,H=rows*rowH+6;
  const all=S.s.flatMap(s=>s.v).filter(v=>v!=null);if(S.ref)all.push(S.ref.v);
  const m={l:1,r:58};const lo=S.log?Math.min(...all.filter(v=>v>0))*.5:0,hi=Math.max(...all)*(S.log?1.2:1);
  const X=v=>S.log?m.l+(W-m.l-m.r)*(Math.log10(Math.max(v,lo))-Math.log10(lo))/(Math.log10(hi)-Math.log10(lo)):m.l+(W-m.l-m.r)*(v-lo)/(hi-lo);
  let g='';
  S.x.forEach((x,i)=>{const y0=i*rowH;g+=`<text x="0" y="${y0+14}" style="fill:#f4f3ee;font-size:13px">${esc(x)}</text>`;
   S.s.forEach((s,j)=>{const v=s.v[i];if(v==null)return;const y=y0+20+j*(bh+gap),w=Math.max(X(v)-m.l,1.5);
    g+=`<rect x="${m.l}" y="${y}" width="${w}" height="${bh}" rx="3" fill="${COL[(S.cols&&S.cols[i])||s.c]}"/><text x="${m.l+w+6}" y="${y+bh-1}" style="font-size:12px">${fmt(v)}${S.unit||''}</text>`})});
  if(S.ref)g+=`<line x1="${X(S.ref.v)}" x2="${X(S.ref.v)}" y1="0" y2="${H-4}" stroke="#f4f3ee" stroke-width="1.5" stroke-dasharray="5 4"/>`;
  host.innerHTML=`<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="${esc(S.title)}">${g}</svg>`;
 }
 render();let tm;new ResizeObserver(()=>{clearTimeout(tm);tm=setTimeout(render,120)}).observe(host);
}
document.querySelectorAll('.chart').forEach(initChart);

document.addEventListener('click',e=>{const f=e.target.closest('button.frame');if(!f)return;
 const v=document.createElement('video');v.src=f.dataset.src;v.controls=true;v.autoplay=true;v.playsInline=true;v.muted=true;v.poster=f.dataset.poster;v.style.aspectRatio=f.dataset.ar;
 f.replaceWith(v);v.play().catch(()=>{})});

const hero=document.querySelector('.hero video');
if(hero&&matchMedia('(prefers-reduced-motion:reduce)').matches){hero.pause();hero.removeAttribute('autoplay')}

const car=document.querySelector('.car'),ttl=document.querySelector('.bar-title'),heads=[...document.querySelectorAll('.gantry')];
function onScroll(){const h=document.documentElement,p=h.scrollTop/Math.max(h.scrollHeight-h.clientHeight,1);car.style.left=(p*100)+'%';
 let cur=null;for(const g of heads){if(g.getBoundingClientRect().top<90)cur=g}ttl.textContent=cur?cur.dataset.t:'The report'}
addEventListener('scroll',onScroll,{passive:true});onScroll();
const route=document.querySelector('.route');
document.querySelector('.bar button').onclick=()=>route.classList.add('open');
route.addEventListener('click',e=>{if(e.target===route||e.target.tagName==='BUTTON'||e.target.closest('a'))route.classList.remove('open')});
addEventListener('keydown',e=>{if(e.key==='Escape')route.classList.remove('open')});

document.querySelectorAll('.chips').forEach(c=>{const grid=document.querySelector(c.dataset.for);
 c.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;c.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));
  const k=b.dataset.k;grid.querySelectorAll('[data-k]').forEach(x=>{x.style.display=(k==='all'?x.dataset.k!=='debug':x.dataset.k===k)?'':'none'})});
 const first=c.querySelector('[aria-pressed=true]');if(first)first.click()});
const q=document.querySelector('input.q');
if(q)q.addEventListener('input',()=>{const t=q.value.toLowerCase();document.querySelectorAll('.sim').forEach(s=>{s.style.display=s.textContent.toLowerCase().includes(t)?'':'none'})});
"""
