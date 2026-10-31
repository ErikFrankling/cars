struct Camera { center: vec2f, size: vec2f, mpp: f32, mode: u32, capacity:u32, time:f32 }
struct Range { start: u32, count: u32, length: f32, pad: f32 }
struct Point { xy: vec2f, distance: f32, pad: f32 }
struct Instance { xy: vec2f, dir: vec2f, length: f32, ratio: f32, alive: f32, spare: f32 }
@group(0) @binding(0) var<uniform> cam: Camera;
@group(0) @binding(1) var<storage,read> vehicles: array<Veh>;
@group(0) @binding(2) var<storage,read> lanes: array<Lane>;
@group(0) @binding(3) var<storage,read> ranges: array<Range>;
@group(0) @binding(4) var<storage,read> points: array<Point>;
@group(0) @binding(5) var<storage,read> types: array<VType>;
@group(0) @binding(6) var<storage,read> globals: Globals;
@group(0) @binding(7) var<storage,read_write> instances: array<Instance>;
@group(0) @binding(8) var<storage,read_write> stats: array<atomic<u32>>;
@group(0) @binding(9) var<storage,read> signals:array<vec4u>;
@group(0) @binding(10) var<storage,read> lights:array<TlsState>;
@group(0) @binding(11) var<storage,read> light_phases:array<TlsPhase>;
@group(0) @binding(12) var<storage,read> light_states:array<u32>;
struct History { xy:vec2f, offset:vec2f, lane:u32, valid:u32, changed:f32, time:f32 }
@group(0) @binding(13) var<storage,read_write> history:array<History>;
@group(0) @binding(14) var<storage,read> render_links:array<vec4u>;
@group(0) @binding(15) var<storage,read> render_routes:array<u32>;
fn lane_xy(lane:u32,pos:f32)->vec2f {
 let r=ranges[lane];let d=pos/max(lanes[lane].length,0.001)*r.length;
 var lo=0u;var hi=r.count-1u;
 loop {if(hi-lo<=1u){break;}let m=(lo+hi)/2u;if(points[r.start+m].distance<d){lo=m;}else{hi=m;}}
 let a=points[r.start+lo];let b=points[r.start+hi];
 return mix(a.xy,b.xy,(d-a.distance)/max(b.distance-a.distance,0.001));
}
@compute @workgroup_size(64) fn prepare(@builtin(global_invocation_id) id: vec3u) {
 let i=id.x; if(i>=arrayLength(&instances)){return;}
 instances[i].alive=0.0;
 if(i>=cam.capacity){
 let si=i-cam.capacity;if(si>=arrayLength(&signals) || cam.mpp>2.0){return;}
 let signal=signals[si];let r=ranges[signal.x];if(r.count<2u){return;}
 let b=points[r.start+r.count-1u].xy;let a=points[r.start+r.count-2u].xy;let dir=(b-a)/max(distance(a,b),0.001);
 let t=lights[signal.y];let state=light_states[light_phases[t.first_phase+t.phase].state_start+signal.z];
 var ratio=0.0;if(state==103u || state==71u){ratio=0.8;}if(state==121u || state==89u){ratio=0.45;}
 instances[i]=Instance(b+vec2f(-dir.y,dir.x)*1.5-dir*f32(signal.w)*0.9,dir,0.65,ratio,1.0,-1.0);return;
 }
 if(i>=globals.n_active){return;} let v=vehicles[i];
 if((v.flags & F_REMOVED)!=0u || v.replica!=0u || v.lane>=arrayLength(&ranges)){return;}
 let r=ranges[v.lane]; if(r.count<2u || r.length<=0.0){return;}
 let l=lanes[v.lane]; let length=types[v.vtype].length;
 let d=clamp((v.pos-length*0.5)/max(l.length,0.001),0.0,1.0)*r.length;
 var lo=0u; var hi=r.count-1u;
 loop { if(hi-lo<=1u){break;} let mid=(lo+hi)/2u; if(points[r.start+mid].distance<d){lo=mid;}else{hi=mid;} }
 let a=points[r.start+lo]; let b=points[r.start+hi];
 var rear=lane_xy(v.lane,v.pos-length);
 if(v.pos<length && v.prev_lane<arrayLength(&ranges) && v.prev_lane!=v.lane && ranges[v.prev_lane].count>=2u){rear=lane_xy(v.prev_lane,lanes[v.prev_lane].length+v.pos-length);}
 let front=lane_xy(v.lane,v.pos);
 let dir=(front-rear)/max(distance(front,rear),0.001);
 var ratio=clamp(v.speed/max(l.speed,0.01),0.0,1.0);
 if(cam.mode==1u){ratio=select(0.15,0.85,types[v.vtype].model>=2u);}
 if(cam.mode==2u){ratio=1.0-clamp(v.wait/60.0,0.0,1.0);}
 var xy=(front+rear)*0.5;
 if(cam.mpp<0.3 && cam.mode==0u){ratio=fract(f32(v.trip)*0.618034);}
 var h=history[v.trip];
 if(h.valid!=0u && h.lane!=v.lane && lanes[h.lane].edge==l.edge && cam.time>h.time){
   let n=vec2f(-dir.y,dir.x);h.offset=n*dot(h.xy-xy,n);h.changed=cam.time;
 }
 let u=clamp((cam.time-h.changed)/3.0,0.0,1.0);
 xy+=h.offset*(1.0-u*u*(3.0-2.0*u));
 history[v.trip]=History(xy,h.offset,v.lane,1u,h.changed,cam.time);
 var detail=select(0.0,1.0,v.acc < -0.3);
 var indicator=0u;
 if(v.best_off>0 || (v.lc_own&1u)!=0u){indicator=2u;}
 if(v.best_off<0 || (v.lc_own&2u)!=0u){indicator=4u;}
 if(v.route_i+1u<v.route_end && l.length-v.pos<40.0){
  let edge=render_routes[v.route_i+1u];
  for(var k=0u;k<l.links_count;k++){let link=render_links[l.links_start+k];if(link.x==edge){indicator|=link.y;break;}}
 }
 detail+=f32(indicator);
 instances[i]=Instance(xy,dir,length,ratio,1.0,detail);
 atomicAdd(&stats[0],1u); atomicAdd(&stats[1],u32(max(v.speed,0.0)*100.0));
}
fn clip(xy:vec2f)->vec4f { return vec4f((xy-cam.center)/(cam.size*cam.mpp)*2.0,0.0,1.0); }
struct Out { @builtin(position) pos: vec4f, @location(0) uv:vec2f, @location(1) color:vec3f, @location(2) alpha:f32, @location(3) halfsize:vec2f, @location(4) detail:f32 }
fn palette(t:f32)->vec3f {
 if(t<0.25){return mix(vec3f(1.0,0.025,0.065),vec3f(1.0,0.32,0.035),t*4.0);}
 if(t<0.5){return mix(vec3f(1.0,0.32,0.035),vec3f(1.0,0.82,0.16),(t-0.25)*4.0);}
 if(t<0.8){return mix(vec3f(1.0,0.82,0.16),vec3f(0.04,0.8,0.77),(t-0.5)/0.3);}
 return mix(vec3f(0.04,0.8,0.77),vec3f(0.64,0.94,1.0),(t-0.8)*5.0);
}
@vertex fn road(@location(0) xy:vec2f,@location(1) normal:vec2f,@location(2) width:f32,@location(3) tint:f32)->Out {
 var o:Out; let w=max(width,cam.mpp*0.7); o.pos=clip(xy+normal*w*0.5);
 o.uv=vec2f(0.0); o.color=select(vec3f(0.10,0.115,0.13)*tint,vec3f(0.85),tint<0.0); if(tint < -1.5){o.color=vec3f(1.,0.65,0.03);} if(tint < -3.5){o.color=vec3f(0.23,0.25,0.22);}
 o.alpha=select(clamp(width/w,0.22,1.0),1.0,width==0.0); o.halfsize=vec2f(1.0); o.detail=0.0; return o;
}
@fragment fn road_frag(o:Out)->@location(0) vec4f { return vec4f(o.color*o.alpha,1.0); }
@vertex fn car(@builtin(vertex_index) vid:u32,@location(0) xy:vec2f,@location(1) dir:vec2f,@location(2) length:f32,@location(3) ratio:f32,@location(4) alive:f32,@location(5) detail:f32)->Out {
 let q=vec2f(f32((vid<<1u)&2u),f32(vid&2u))*2.0-1.0;
 let h=max(select(vec2f(length,1.8),vec2f(0.65),detail<0.0)*0.5,vec2f(cam.mpp*2.5));
 let offset=q*h; var o:Out; o.detail=detail; o.pos=clip(xy+dir*offset.x+vec2f(-dir.y,dir.x)*offset.y);
 if(alive<0.5){o.pos=vec4f(4.0,4.0,0.0,1.0);}
 o.uv=q; o.color=palette(ratio); if(detail<0.0){o.color=select(select(vec3f(3.,0.02,0.01),vec3f(3.,1.4,0.01),ratio>0.3),vec3f(0.02,2.,0.08),ratio>0.6);} o.alpha=clamp(cam.mpp/1.5,0.0,1.0); o.halfsize=h/cam.mpp; return o;
}
@fragment fn car_frag(o:Out)->@location(0) vec4f {
 let p=abs(o.uv)*o.halfsize; let radius=max(0.6,min(o.halfsize.x,o.halfsize.y)*0.4); let edge=length(max(p-(o.halfsize-vec2f(radius)),vec2f(0.0)))-radius;
 let body=1.0-smoothstep(-0.5,0.5,edge);
 let dot=exp(-dot(o.uv,o.uv)*5.0)*1.8;
 var color=o.color;
 if(cam.mpp<0.3 && o.detail>=0.0){
   if(o.uv.x>0.2 && o.uv.x<0.55 && abs(o.uv.y)<0.78){color=vec3f(0.04,0.12,0.18);}
   if(o.uv.x < -0.78 && abs(o.uv.y)>0.48 && (u32(o.detail)&1u)!=0u){color=vec3f(3.0,0.01,0.01);}
   if(abs(o.uv.x)>0.7 && ((o.uv.y>0.65 && (u32(o.detail)&2u)!=0u) || (o.uv.y < -0.65 && (u32(o.detail)&4u)!=0u)) && fract(cam.time*1.5)<0.5){color=vec3f(3.0,0.7,0.01);}
 }
 return vec4f(color*mix(body,dot,o.alpha),1.0);
}
