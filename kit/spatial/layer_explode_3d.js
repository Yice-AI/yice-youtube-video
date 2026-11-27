tl.set(q('.model'),{rotationX:0,rotationZ:0,z:0},0);
tl.to(q('.model'),{rotationX:34,rotationZ:6,x:112,y:58,z:10,scale:.75,duration:dur*.56,ease:'power2.inOut'},dur*.04);
tl.fromTo(q('.skeleton'),{z:0,opacity:0},{z:125,y:-45,opacity:1,duration:dur*.52,ease:'power3.out'},dur*.23);
tl.fromTo(q('.letters'),{z:0,opacity:0},{z:265,y:-112,opacity:1,duration:dur*.58,ease:'back.out(1.13)'},dur*.26);
const chips=all('.chip');
tl.fromTo(chips,{opacity:0,z:-25},{opacity:1,z:7,duration:dur*.18,stagger:{amount:dur*.39},ease:'power2.out'},dur*.28);
tl.fromTo(all('.guide'),{opacity:0},{opacity:.8,duration:dur*.32},dur*.32);
const count = {value: 0};
const wordTimed = typeof data.count_at === 'number';
tl.to(count, {
  value: data.count, duration: wordTimed ? .18 : dur * .46, ease: 'power2.out',
  onUpdate: () => { q('.meter strong').textContent = Math.round(count.value); }
}, data.count_at ?? dur * .07);
tl.fromTo(q('.meter'), {scale: .84, opacity: wordTimed ? 0 : .2},
  {scale: 1, opacity: 1, duration: wordTimed ? .18 : dur * .59, ease: 'back.out(1.2)'},
  data.count_at ?? dur * .1);
tl.to(cam,{x:34,y:8,z:78,rx:14,ry:-7,duration:dur*.6,ease:'power2.inOut',onUpdate:applyCamera},0);
tl.to(cam,{x:16,z:105,rx:12,ry:-7,duration:dur*.4,ease:'power4.out',onUpdate:applyCamera},dur*.6);
tl.to(q('.base img'),{'--dof':'2px',duration:dur*.56},dur*.25);
tl.fromTo(q('.meter strong'),{scale:.81},{scale:1.12,duration:dur*.46,ease:'power2.in'},dur*.17);
tl.to(q('.meter strong'),{scale:1,duration:dur*.31,ease:'elastic.out(1,.6)'},dur*.63);

tl.to(q('.base .face'),{opacity:0,duration:dur*.25},dur*.23);

tl.fromTo(all('.plate-tag'),{autoAlpha:0},{autoAlpha:1,duration:dur*.20},dur*.44);

tl.fromTo(q('.letters'),{'--scan-y':'7%','--scan-alpha':0},{'--scan-y':'88%','--scan-alpha':.7,duration:dur*.50,ease:'sine.inOut'},dur*.30);
