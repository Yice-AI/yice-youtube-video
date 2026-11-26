// Spatial-pan-stations and svg-path-draw share a single path with its traveling pen.
const nodes=all('.node'), focus=nodes[data.focus_step], last=data.steps.at(-1).at;
const thread=q('.thread'), pen=q('.pen-tip'), length=thread.getTotalLength();
const ink={fraction:0};
function draw() {
  const point=thread.getPointAtLength(length*ink.fraction);
  thread.style.strokeDashoffset=1-ink.fraction;
  pen.setAttribute('cx',point.x);pen.setAttribute('cy',point.y);
}
draw();
tl.to(ink,{fraction:1,duration:Math.max(last+.25,dur*.59),ease:'power1.inOut',onUpdate:draw},0);
nodes.forEach((node,i)=>tl.fromTo(node,{scale:.75,y:38,z:-45,opacity:.3,'--dof':'3px'},
  {scale:1,y:0,z:12,opacity:1,'--dof':'0px',duration:Math.min(.75,dur*.19),ease:'back.out(1.65)'},data.steps[i].at));
const begin=Math.min(dur*.8,Math.max(dur*.6,last+.15));
const x=focus.offsetLeft+144,y=focus.offsetTop+87;
tl.fromTo(cam,{z:-115,rx:5,ry:-4},{z:0,rx:0,ry:0,duration:begin,ease:'power2.inOut',onUpdate:applyCamera},0);
tl.to(cam,{x:960-x,y:540-y,z:580,rx:1,ry:-2,duration:dur-begin,ease:'power4.out',onUpdate:applyCamera},begin);
tl.fromTo(q('.streak'),{x:-380,opacity:0},{x:500,opacity:.7,yoyo:true,repeat:1,duration:(dur-begin)*.22},begin);
nodes.forEach(node=>{if(node!==focus)tl.to(node,{'--dof':'4px',duration:dur-begin},begin)});
