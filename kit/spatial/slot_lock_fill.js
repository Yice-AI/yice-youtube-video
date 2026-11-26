all('.token').forEach((chip,i)=>{
  const t=dur*(.1+i*.13);tl.set(chip,{y:i*83,opacity:0},0);
  tl.fromTo(chip,{x:0,y:i*83,opacity:0},{x:435,y:i*83-68,opacity:1,duration:dur*.16,ease:'power2.in'},t);
  tl.to(chip,{x:1025,y:i*83,scale:.94,duration:dur*.24,ease:'back.out(1.16)'},t+dur*.16);
});
all('.slots i').forEach((slot,i)=>{
  tl.fromTo(slot,{scale:1},{scale:.94,duration:.09,yoyo:true,repeat:1},dur*(.5+i*.13));
  tl.to(slot,{borderColor:'#e5bd83',duration:.14},dur*(.5+i*.13));
});
