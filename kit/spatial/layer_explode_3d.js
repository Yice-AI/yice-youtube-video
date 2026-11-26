tl.set(q('.model'),{rotationX:0,rotationZ:0,z:0},0);
tl.to(q('.model'),{rotationX:48,rotationZ:-20,x:70,y:58,z:30,duration:dur*.56,ease:'power2.inOut'},dur*.04);
tl.fromTo(q('.skeleton'),{z:0,opacity:0},{z:95,opacity:.96,duration:dur*.52,ease:'power3.out'},dur*.23);
tl.fromTo(q('.letters'),{z:0,opacity:0},{z:192,opacity:1,duration:dur*.58,ease:'back.out(1.13)'},dur*.26);
const chips=all('.chip');
tl.fromTo(chips,{opacity:0,z:-25},{opacity:1,z:7,duration:dur*.18,stagger:{amount:dur*.39},ease:'power2.out'},dur*.28);
tl.fromTo(all('.guide'),{opacity:0},{opacity:.8,duration:dur*.32},dur*.32);
const count={value:0};tl.to(count,{value:data.count,duration:dur*.71,ease:'power2.inOut',onUpdate:()=>{q('.meter strong').textContent=Math.round(count.value)}},dur*.14);
tl.fromTo(q('.meter'),{scale:.84,opacity:.2},{scale:1,opacity:1,duration:dur*.59,ease:'back.out(1.2)'},dur*.1);
tl.to(cam,{x:34,y:8,z:78,rx:14,ry:-12,duration:dur*.6,ease:'power2.inOut',onUpdate:applyCamera},0);
tl.to(cam,{x:16,z:105,rx:12,ry:-8,duration:dur*.4,ease:'power4.out',onUpdate:applyCamera},dur*.6);
tl.to(q('.base img'),{'--dof':'2px',duration:dur*.56},dur*.25);
tl.fromTo(q('.meter strong'),{scale:.81},{scale:1.12,duration:dur*.46,ease:'power2.in'},dur*.17);
tl.to(q('.meter strong'),{scale:1,duration:dur*.31,ease:'elastic.out(1,.6)'},dur*.63);

tl.to(q('.base .face'),{opacity:0,duration:dur*.25},dur*.23);
