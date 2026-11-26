const files=all('.file-card');
files.forEach((card,i)=>{const a=(i-(files.length-1)/2);tl.set(card,{x:a*250,y:Math.abs(a)*24,z:i*18,rotationY:a*-12,rotationZ:a*7},0);
  tl.to(card,{x:45+i*7,y:260,z:-50,scale:.73,rotationZ:-3,rotationY:0,duration:dur*.49,ease:'power2.inOut'},dur*(.12+i*.045));});
tl.fromTo(q('.folder'),{rotationX:16,rotationY:-12,opacity:.8},{rotationX:0,rotationY:0,opacity:1,duration:dur*.73,ease:'power2.out'},dur*.16);
tl.to(q('.command'),{x:420,y:290,rotation:-5,scale:.58,duration:dur*.47,ease:'power2.inOut'},dur*.38);
