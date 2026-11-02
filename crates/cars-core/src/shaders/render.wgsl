struct Camera { center: vec2f, size: vec2f, mpp: f32, mode: u32, capacity:u32, time:f32, close:f32, blend:f32, step_time:f32, pad:f32 }
struct Range { start: u32, count: u32, length: f32, turn: u32 }
struct Point { xy: vec2f, distance: f32, pad: f32 }
struct RenderType { length: f32, width: f32, automated: f32, pad: f32 }
struct Signal { xy: vec2f, dir: vec2f, tl: u32, index: u32, width: f32, turn: u32 }
struct Instance { xy: vec2f, dir: vec2f, length: f32, width: f32, ratio: f32, alive: f32, detail: f32, seed: f32, pad: vec2f }
struct History { prev_xy:vec2f, prev_dir:vec2f, cur_xy:vec2f, cur_dir:vec2f, drawn:vec2f, lat:f32, changed:f32, time:f32, lane:u32, valid:u32, pad:f32 }
@group(0) @binding(0) var<uniform> cam: Camera;
@group(0) @binding(1) var<storage,read> vehicles: array<Veh>;
@group(0) @binding(2) var<storage,read> lanes: array<Lane>;
@group(0) @binding(3) var<storage,read> ranges: array<Range>;
@group(0) @binding(4) var<storage,read> points: array<Point>;
@group(0) @binding(5) var<storage,read> types: array<RenderType>;
@group(0) @binding(6) var<storage,read> globals: Globals;
@group(0) @binding(7) var<storage,read_write> instances: array<Instance>;
@group(0) @binding(8) var<storage,read_write> stats: array<atomic<u32>>;
@group(0) @binding(9) var<storage,read> signals:array<Signal>;
@group(0) @binding(10) var<storage,read> lights:array<TlsState>;
@group(0) @binding(11) var<storage,read> light_phases:array<TlsPhase>;
@group(0) @binding(12) var<storage,read> light_states:array<u32>;
@group(0) @binding(13) var<storage,read_write> history:array<History>;
@group(0) @binding(14) var<storage,read> render_links:array<vec4u>;
@group(0) @binding(15) var<storage,read> render_routes:array<u32>;
const CHANGE_SECONDS: f32 = 3.0;
fn lane_seg(lane:u32,pos:f32)->u32 {
 let r=ranges[lane];let d=clamp(pos/max(lanes[lane].length,0.001),0.0,1.0)*r.length;
 var lo=0u;var hi=r.count-1u;
 loop {if(hi-lo<=1u){break;}let m=(lo+hi)/2u;if(points[r.start+m].distance<d){lo=m;}else{hi=m;}}
 return r.start+lo;
}
fn lane_xy(lane:u32,pos:f32)->vec2f {
 let k=lane_seg(lane,pos);let d=clamp(pos/max(lanes[lane].length,0.001),0.0,1.0)*ranges[lane].length;
 let a=points[k];let b=points[k+1u];
 return mix(a.xy,b.xy,clamp((d-a.distance)/max(b.distance-a.distance,0.001),0.0,1.0));
}
fn lane_dir(lane:u32,pos:f32)->vec2f {
 let k=lane_seg(lane,pos);let a=points[k].xy;let b=points[k+1u].xy;
 return (b-a)/max(distance(a,b),0.001);
}
fn prepare_signal(i:u32,si:u32) {
 let s=signals[si];let t=lights[s.tl];let state=light_states[light_phases[t.first_phase+t.phase].state_start+s.index];
 var code=0.0;
 if(state==121u || state==89u || state==117u){code=1.0;}
 if(state==71u){code=2.0;}
 if(state==103u){code=3.0;}
 if(state==111u || state==79u){code=4.0;}
 instances[i]=Instance(s.xy,s.dir,1.7,s.width,code,2.0,f32(s.turn),0.0,vec2f(0.0));
}
@compute @workgroup_size(64) fn prepare(@builtin(global_invocation_id) id: vec3u) {
 let i=id.x; if(i>=arrayLength(&instances)){return;}
 instances[i].alive=0.0;
 if(i>=cam.capacity){prepare_signal(i,i-cam.capacity);return;}
 if(i>=globals.n_active){return;} let v=vehicles[i];
 if((v.flags & (F_REMOVED|F_SHADOW))!=0u || v.replica!=0u || v.lane>=arrayLength(&ranges)){return;}
 let r=ranges[v.lane]; if(r.count<2u || r.length<=0.0){return;}
 let l=lanes[v.lane]; let rt=types[v.vtype]; let body=rt.length;
 let front=lane_xy(v.lane,v.pos);
 var rear=lane_xy(v.lane,v.pos-body);
 if(v.pos<body && v.prev_lane<arrayLength(&ranges) && v.prev_lane!=v.lane && ranges[v.prev_lane].count>=2u){
  // A lane change keeps prev_lane, so only follow it when the two lanes actually meet.
  let pr=ranges[v.prev_lane];
  if(distance(points[pr.start+pr.count-1u].xy,points[r.start].xy)<2.0){rear=lane_xy(v.prev_lane,lanes[v.prev_lane].length+v.pos-body);}
 }
 var dir=lane_dir(v.lane,v.pos);
 if(distance(front,rear)>0.2*body){dir=normalize(front-rear);}
 let n=vec2f(-dir.y,dir.x); let center=front-dir*body*0.5;
 var h=history[v.trip];
 if(h.valid==0u){
  h=History(center,dir,center,dir,center,0.0,-1e9,cam.step_time,v.lane,1u,0.0);
 } else if(cam.step_time>h.time){
  let elapsed=cam.step_time-h.time;
  h.prev_xy=h.cur_xy;h.prev_dir=h.cur_dir;
  if(distance(center,h.cur_xy)>(v.speed+10.0)*elapsed*1.5+6.0){
   h.prev_xy=center;h.prev_dir=dir;h.lat=0.0;
  } else if(h.lane!=v.lane && lanes[h.lane].edge==l.edge){
   let u=clamp((h.time-h.changed)/CHANGE_SECONDS,0.0,1.0);
   let old=h.cur_xy+vec2f(-h.cur_dir.y,h.cur_dir.x)*h.lat*(1.0-u*u*(3.0-2.0*u));
   h.lat=dot(old-center,n);
   h.prev_xy=h.cur_xy+n*dot(center-h.cur_xy,n);
   h.changed=h.time;
  }
  h.cur_xy=center;h.cur_dir=dir;h.time=cam.step_time;h.lane=v.lane;
 }
 let b=mix(h.prev_xy,h.cur_xy,cam.blend);
 var d=mix(h.prev_dir,h.cur_dir,cam.blend);
 d=select(h.cur_dir,normalize(d),length(d)>0.2);
 let dn=vec2f(-d.y,d.x);
 let u=clamp((cam.time-h.changed)/CHANGE_SECONDS,0.0,1.0);
 var xy=b+dn*h.lat*(1.0-u*u*(3.0-2.0*u));
 var yaw=clamp(atan2(-h.lat*6.0*u*(1.0-u)/CHANGE_SECONDS,max(v.speed,2.0)),-0.35,0.35);
 if(rt.pad>0.0){
  // Physical mode: the engine knows where the car is sideways.
  xy=b; yaw=0.0;
  if((v.phys>>30u)!=0u){
   let w=l.width; var v_lat=rt.pad; if((v.flags&F_LAT_FAST)!=0u){v_lat=1.0;}
   let total=w/v_lat+1.0; let t=f32((v.phys>>16u)&0x3fffu)/16383.0*total;
   var done=v_lat*(t-0.5);
   if(t<1.0){done=v_lat*(t*0.5-sin(3.14159265*t)/6.2831853);}
   if(t>total-1.0){let r=total-t;done=w-v_lat*(r*0.5-sin(3.14159265*r)/6.2831853);}
   let side=select(1.0,-1.0,(v.phys>>30u)==1u);
   xy=b+dn*side*(w-done);
   yaw=clamp(atan2(-side*v_lat,max(v.speed,2.0)),-0.21,0.21);
  }
 }
 let drawn_dir=d*cos(yaw)+dn*sin(yaw);
 h.drawn=xy;
 history[v.trip]=h;
 var ratio=clamp(v.speed/max(l.speed,0.01),0.0,1.0);
 if(cam.mode==1u){ratio=select(0.15,0.85,rt.automated>0.5);}
 if(cam.mode==2u){ratio=1.0-clamp(v.wait/60.0,0.0,1.0);}
 var detail=select(0u,1u,v.acc < -0.5 || v.speed<0.1);
 if((v.lc_own&1u)!=0u){detail|=2u;}
 if((v.lc_own&2u)!=0u){detail|=4u;}
 if(u<1.0 && h.lat>0.3){detail|=4u;}
 if(u<1.0 && h.lat< -0.3){detail|=2u;}
 if((l.flags&1u)!=0u){
  detail|=r.turn;
 } else if(v.route_i+1u<v.route_end && l.length-v.pos<60.0){
  let edge=render_routes[v.route_i+1u];
  for(var k=0u;k<l.links_count;k++){let link=render_links[l.links_start+k];if(link.x==edge){detail|=link.y;break;}}
 }
 instances[i]=Instance(xy,drawn_dir,body,rt.width,ratio,1.0,f32(detail),fract(f32(v.trip)*0.61803398),vec2f(0.0));
 atomicAdd(&stats[0],1u); atomicAdd(&stats[1],u32(max(v.speed,0.0)*100.0));
}
fn clip(xy:vec2f)->vec4f { return vec4f((xy-cam.center)/(cam.size*cam.mpp)*2.0,0.0,1.0); }
struct Out { @builtin(position) pos: vec4f, @location(0) uv:vec2f, @location(1) color:vec3f, @location(2) alpha:f32, @location(3) halfsize:vec2f }
fn palette(t:f32)->vec3f {
 if(t<0.25){return mix(vec3f(1.0,0.025,0.065),vec3f(1.0,0.32,0.035),t*4.0);}
 if(t<0.5){return mix(vec3f(1.0,0.32,0.035),vec3f(1.0,0.82,0.16),(t-0.25)*4.0);}
 if(t<0.8){return mix(vec3f(1.0,0.82,0.16),vec3f(0.04,0.8,0.77),(t-0.5)/0.3);}
 return mix(vec3f(0.04,0.8,0.77),vec3f(0.64,0.94,1.0),(t-0.8)*5.0);
}
@vertex fn road(@location(0) xy:vec2f,@location(1) normal:vec2f,@location(2) width:f32,@location(3) tint:f32)->Out {
 var o:Out; let w=max(width,cam.mpp*0.7); o.pos=clip(xy+normal*w*0.5);
 o.uv=vec2f(0.0); o.color=vec3f(0.025,0.042,0.065)*tint; o.alpha=clamp(width/w,0.22,1.0); o.halfsize=vec2f(1.0); return o;
}
@fragment fn road_frag(o:Out)->@location(0) vec4f { return vec4f(o.color*o.alpha,1.0); }
@vertex fn car(@builtin(vertex_index) vid:u32,@location(0) xy:vec2f,@location(1) dir:vec2f,@location(2) body:f32,@location(4) ratio:f32,@location(5) alive:f32)->Out {
 let q=vec2f(f32((vid<<1u)&2u),f32(vid&2u))*2.0-1.0;
 let signal=alive>1.5;
 let h=max(select(vec2f(body,1.8),vec2f(0.8),signal)*0.5,vec2f(cam.mpp*2.5));
 let offset=q*h; var o:Out; o.pos=clip(xy+dir*offset.x+vec2f(-dir.y,dir.x)*offset.y);
 if(alive<0.5 || (signal && cam.mpp>2.0)){o.pos=vec4f(4.0,4.0,0.0,1.0);}
 var c=ratio; if(signal){c=select(select(0.0,0.45,ratio==1.0),0.8,ratio==2.0||ratio==3.0);}
 o.uv=q; o.color=palette(c); o.alpha=clamp(cam.mpp/1.5,0.0,1.0); o.halfsize=h/cam.mpp; return o;
}
@fragment fn car_frag(o:Out)->@location(0) vec4f {
 let p=abs(o.uv)*o.halfsize; let radius=max(0.6,min(o.halfsize.x,o.halfsize.y)*0.4); let edge=length(max(p-(o.halfsize-vec2f(radius)),vec2f(0.0)))-radius;
 let body=1.0-smoothstep(-0.5,0.5,edge);
 let dot=exp(-dot(o.uv,o.uv)*5.0)*1.8;
 return vec4f(o.color*mix(body,dot,o.alpha),1.0);
}
// Close-up style. Colours are sRGB; lin() undoes the tone map so they come out as authored.
fn lin(c:vec3f)->vec3f { return -log(max(vec3f(1.0)-pow(c,vec3f(2.2)),vec3f(0.002)))/1.3; }
struct CloseRoad { @builtin(position) pos: vec4f, @location(0) color:vec4f, @location(1) dash:vec2f }
@vertex fn close_road(@location(0) xy:vec2f,@location(1) normal:vec2f,@location(2) width:f32,@location(3) dash:vec2f,@location(4) color:vec4f)->CloseRoad {
 var o:CloseRoad; o.pos=clip(xy+normal*max(width,select(0.0,cam.mpp*1.3,width>0.0))*0.5); o.color=color; o.dash=dash; return o;
}
@fragment fn close_road_frag(o:CloseRoad)->@location(0) vec4f {
 var a=cam.close*o.color.a;
 if(o.dash.y>0.0){
  let f=fract(o.dash.x); let w=fwidth(o.dash.x)*0.75;
  a*=smoothstep(-w,w,f)*(1.0-smoothstep(o.dash.y-w,o.dash.y+w,f))+smoothstep(1.0-w,1.0+w,f);
 }
 return vec4f(lin(o.color.rgb)*a,a);
}
fn paint(seed:f32)->vec3f {
 let k=u32(seed*11.0);
 switch k {
  case 0u {return vec3f(0.92,0.92,0.90);}
  case 1u {return vec3f(0.70,0.72,0.74);}
  case 2u {return vec3f(0.36,0.38,0.42);}
  case 3u {return vec3f(0.14,0.15,0.17);}
  case 4u {return vec3f(0.74,0.12,0.12);}
  case 5u {return vec3f(0.12,0.26,0.62);}
  case 6u {return vec3f(0.36,0.62,0.80);}
  case 7u {return vec3f(0.10,0.42,0.28);}
  case 8u {return vec3f(0.88,0.58,0.12);}
  case 9u {return vec3f(0.84,0.80,0.66);}
  default {return vec3f(0.48,0.20,0.46);}
 }
}
struct CloseCar { @builtin(position) pos: vec4f, @location(0) p:vec2f, @location(1) half_body:vec2f, @location(2) color:vec3f, @location(3) @interpolate(flat) detail:u32, @location(4) shadow:vec2f, @location(5) scale:f32 }
@vertex fn close_car(@builtin(vertex_index) vid:u32,@location(0) xy:vec2f,@location(1) dir:vec2f,@location(2) body:f32,@location(3) width:f32,@location(4) ratio:f32,@location(5) alive:f32,@location(6) detail:f32,@location(7) seed:f32)->CloseCar {
 var o:CloseCar;
 if(alive<0.5 || alive>1.5){o.pos=vec4f(4.0,4.0,0.0,1.0);return o;}
 let q=vec2f(f32((vid<<1u)&2u),f32(vid&2u))*2.0-1.0;
 let n=vec2f(-dir.y,dir.x);
 let half_body=max(vec2f(body,width)*0.5,vec2f(cam.mpp*1.5));
 let h=half_body+vec2f(1.0);
 let p=q*h;
 o.pos=clip(xy+dir*p.x+n*p.y); o.p=p; o.half_body=half_body;
 o.color=select(palette(ratio),paint(seed),cam.mode==3u);
 o.detail=u32(detail);
 let sun=vec2f(0.32,-0.42);
 o.shadow=vec2f(dot(sun,dir),dot(sun,n)); o.scale=1.0;
 return o;
}
fn round_box(p:vec2f,h:vec2f,r:f32)->f32 {
 let q=abs(p)-h+vec2f(r);
 return length(max(q,vec2f(0.0)))+min(max(q.x,q.y),0.0)-r;
}
@fragment fn close_car_frag(o:CloseCar)->@location(0) vec4f {
 let h=o.half_body; let p=o.p; let aa=cam.mpp*0.75;
 let sd=round_box(p,h,min(0.42,h.y*0.45));
 let body=1.0-smoothstep(-aa,aa,sd);
 let shade=(1.0-smoothstep(-0.3,0.45,round_box(p-o.shadow,h,0.4)))*0.5;
 let f=h.x-p.x; let r=p.x+h.x; let y=abs(p.y); let long=h.x>3.4;
 var c=o.color;
 c=mix(c,c*0.72,1.0-smoothstep(0.0,0.3,h.y-y));
 let glass=vec3f(0.07,0.11,0.15);
 if(long){
  if(f>0.28 && f<0.95 && y<h.y*0.84){c=glass;}
  if(f>2.3 && f<2.45){c=vec3f(0.1);}
 } else if(h.x>0.9) {
  let side=h.y*0.86-(f-1.2)*0.08;
  if(f>1.2 && f<1.9 && y<side){c=glass;}
  if(r>0.55 && r<0.98 && y<h.y*0.78){c=glass;}
  if(f>1.95 && r>1.02 && y>h.y*0.68 && y<h.y*0.86){c=mix(glass,c,0.25);}
 }
 var lamp=vec3f(0.0);
 if(f<0.2 && y>h.y*0.42){c=vec3f(0.98,0.96,0.80);}
 let braking=(o.detail&1u)!=0u;
 if(r<0.18 && y>h.y*0.35){
  if(braking){lamp=vec3f(9.0,0.05,0.03);}else{c=vec3f(0.48,0.04,0.04);}
 }
 let blink=fract(cam.time*1.5)<0.55;
 if(blink && ((o.detail&2u)!=0u && p.y>h.y*0.5 || (o.detail&4u)!=0u && p.y< -h.y*0.5)){
  if(f<0.42 || r<0.42){lamp=vec3f(7.0,2.4,0.03);}
 }
 var glow=0.0;
 if(braking){
  let e=vec2f(p.x+h.x,y-h.y*0.65);
  glow=exp(-dot(e,e)*5.0)*0.3;
 }
 let lit=select(lin(c),lamp,lamp.x>0.0);
 let a=body+(1.0-body)*shade;
 return vec4f((lit*body+vec3f(1.4,0.02,0.02)*glow*(1.0-body))*cam.close,a*cam.close);
}
struct CloseSignal { @builtin(position) pos: vec4f, @location(0) p:vec2f, @location(1) half_body:vec2f, @location(2) @interpolate(flat) code:u32, @location(3) @interpolate(flat) turn:u32 }
@vertex fn close_signal(@builtin(vertex_index) vid:u32,@location(0) xy:vec2f,@location(1) dir:vec2f,@location(2) body:f32,@location(3) width:f32,@location(4) ratio:f32,@location(5) alive:f32,@location(6) detail:f32)->CloseSignal {
 var o:CloseSignal;
 if(alive<1.5){o.pos=vec4f(4.0,4.0,0.0,1.0);return o;}
 let q=vec2f(f32((vid<<1u)&2u),f32(vid&2u))*2.0-1.0;
 let scale=max(1.0,cam.mpp/0.14);
 let half_body=vec2f(body,width)*0.5;
 let p=q*half_body;
 let world=xy+dir*(p.x*scale-(scale-1.0)*0.85)+vec2f(-dir.y,dir.x)*p.y*min(scale,1.3);
 o.pos=clip(world); o.p=p; o.half_body=half_body; o.code=u32(ratio); o.turn=u32(detail);
 return o;
}
fn arrow_glyph(f:f32,s:f32)->f32 {
 let shaft=abs(s)<0.14 && f> -0.62 && f<0.1;
 let head=f>=0.1 && f<0.72 && abs(s)<0.72-f;
 return select(0.0,1.0,shaft||head);
}
@fragment fn close_signal_frag(o:CloseSignal)->@location(0) vec4f {
 var lit=vec3f(1.0,0.05,0.03);
 if(o.code==1u){lit=vec3f(1.0,0.72,0.03);}
 if(o.code==2u){lit=vec3f(0.05,1.0,0.25);}
 if(o.code==3u){lit=vec3f(0.35,0.85,0.25);}
 if(o.code==4u){lit=vec3f(0.5,0.5,0.5);}
 let p=o.p; let h=o.half_body; let aa=cam.mpp*0.75;
 let bar=1.0-smoothstep(-aa,aa,round_box(p-vec2f(-h.x+0.28,0.0),vec2f(0.28,h.y-0.04),0.02));
 let c=vec2f(0.32,0.0);
 let box_half=vec2f(0.55,min(h.y-0.04,0.62));
 let housing=1.0-smoothstep(-aa,aa,round_box(p-c,box_half,0.14));
 let radius=min(box_half.y-0.08,0.5);
 let lamp=1.0-smoothstep(-aa,aa,length(p-c)-radius);
 let q=(p-c)/radius;
 var glyph=arrow_glyph(q.x,q.y);
 if(o.turn==2u){glyph=arrow_glyph(q.y,-q.x);}
 if(o.turn==4u){glyph=arrow_glyph(-q.y,q.x);}
 var c2=lin(vec3f(0.05))*housing;
 c2=mix(c2,lit*5.0,lamp);
 c2=mix(c2,vec3f(0.0),lamp*glyph);
 c2=mix(c2,lit*2.2,bar);
 let a=max(max(housing,bar),lamp)*cam.close;
 return vec4f(c2*cam.close,a);
}
