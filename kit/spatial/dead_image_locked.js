tl.fromTo(q('.locked-shot'),{rotationY:-15,scale:.91},{rotationY:0,scale:1,duration:dur*.42},0);
tl.to(q('.pointer'),{x:-340,y:-280,duration:dur*.4,ease:'power2.inOut'},.05);
tl.to(q('.locked-shot'),{x:14,repeat:5,yoyo:true,duration:.075},dur*.47);
tl.fromTo(q('.warning'),{y:42,opacity:0},{y:0,opacity:1,duration:dur*.32,ease:'back.out(1.4)'},dur*.48);
tl.to(q('.pointer'),{scale:.78,duration:.09,yoyo:true,repeat:1},dur*.44);
tl.fromTo(q('.ripple'),{scale:.2,opacity:.95},{scale:2.2,opacity:0,duration:dur*.24},dur*.46);
