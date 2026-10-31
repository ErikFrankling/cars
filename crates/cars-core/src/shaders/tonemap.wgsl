@group(0) @binding(0) var scene:texture_2d<f32>;
@vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f { return vec4f(vec2f(f32((i<<1u)&2u),f32(i&2u))*2.0-1.0,0.0,1.0); }
@fragment fn fs(@builtin(position) p:vec4f)->@location(0) vec4f {
 let xy=vec2i(p.xy); let sz=vec2i(textureDimensions(scene)); var glow=vec3f(0.0);
 for(var y=-2;y<=2;y++){for(var x=-2;x<=2;x++){let c=textureLoad(scene,clamp(xy+vec2i(x,y)*2,vec2i(0),sz-1),0).rgb; glow+=max(c-vec3f(0.45),vec3f(0.0))/25.0;}}
 let c=textureLoad(scene,xy,0).rgb+glow*0.22+vec3f(0.0008,0.0015,0.003);
 return vec4f(pow(vec3f(1.0)-exp(-c*1.3),vec3f(1.0/2.2)),1.0);
}
