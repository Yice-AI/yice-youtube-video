const slots=all('.slots i'), wires=all('.data-wire');
all('.token').forEach((chip,i)=>{
  const wire=wires[i], comet=all('.comet')[i], slot=slots[i], start=dur*(.08+i*.13), travel=dur*.33;
  const length=wire.getTotalLength();
  tl.set(chip,{x:0,y:i*83+5,autoAlpha:0},0);
  tl.set(comet,{attr:{cx:718,cy:336+i*83}},0);
  tl.to(chip,{autoAlpha:1,duration:travel*.13},start);
  // Bake the curve into the parent timeline so export and backwards seeking share the same pose.
  const steps=18;
  for(let step=1;step<=steps;step++){
    const t=step/steps;
    const eased=t*t*(3-2*t);
    const point=wire.getPointAtLength(length*eased);
    const at=start+travel*(step-1)/steps;
    tl.to(chip,{x:point.x-696,y:point.y-331,duration:travel/steps,ease:'none'},at);
    tl.to(comet,{attr:{cx:point.x+22,cy:point.y},duration:travel/steps,ease:'none'},at);
  }
  tl.fromTo(wire,{strokeDashoffset:1,opacity:0},{strokeDashoffset:0,opacity:1,duration:travel,ease:'power2.inOut'},start);
  tl.fromTo(comet,{opacity:0},{opacity:1,duration:travel*.10},start);
  tl.to(comet,{opacity:0,duration:travel*.2},start+travel);
  tl.to(wire,{opacity:.28,duration:travel*.35},start+travel);
  tl.to(slot,{'--lock-opacity':1,borderColor:'#74eaff',duration:.14},start+travel-.05);
  tl.fromTo(slot,{scale:1,boxShadow:'0 0 0px #38bdf800'},{scale:1.025,boxShadow:'0 0 24px #38bdf8aa',duration:.12,yoyo:true,repeat:1},start+travel);
});
