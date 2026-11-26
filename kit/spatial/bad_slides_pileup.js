all('.old-card').forEach((card,i)=>tl.fromTo(card,{x:-450,y:100,rotation:-10,opacity:0},{x:230+i*515,y:i%2?25:0,rotation:0,opacity:1,duration:dur*.26,ease:'back.out(1.12)'},i*dur*.14));
tl.fromTo(q('.warning'),{scale:1.65,rotation:-9,opacity:0},{scale:1,rotation:-3,opacity:1,duration:dur*.17,ease:'power3.out'},dur*.58);
tl.to(all('.old-card'),{x:'-=160',opacity:.46,duration:dur*.23,stagger:.08},dur*.7);
