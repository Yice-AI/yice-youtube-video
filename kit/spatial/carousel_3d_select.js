const cards = all('.orbit-card'), selected = data.selected_index, stop = data.select_at;
const angle = (index, progress) => (index-selected)*2*Math.PI/cards.length + (progress-1)*1.55;
function pose(i, progress) {
  const a = angle(i,progress), depth = Math.cos(a);
  return {x:690*Math.sin(a),y:108*depth-12,z:350*depth,rotationX:7,rotationY:-33*Math.sin(a),
    opacity:.47+.53*(depth+1)/2,'--light':.48+.52*(depth+1)/2,'--dof':((1-depth)*2.4)+'px'};
}
cards.forEach((card,i)=>{
  tl.set(card,pose(i,0),0);
  for(let tick=1;tick<=18;tick++) tl.to(card,{...pose(i,tick/18),duration:stop/18,ease:'none'},(tick-1)*stop/18);
  if(i!==selected) tl.to(card,{x:pose(i,1).x*1.45,y:pose(i,1).y*1.5,z:-590,opacity:0,'--dof':'8px',duration:(dur-stop)*.64,ease:'power2.in'},stop);
});
const hero=cards[selected];hero.classList.add('card-morph-anchor');
tl.to(hero,{x:0,y:-4,z:260,rotationX:0,rotationY:0,scale:2.48,'--light':1.05,'--dof':'0px',duration:dur-stop,ease:'power3.inOut'},stop);
tl.fromTo(cam,{x:-45,y:15,z:-150,rx:-6,ry:9},{x:0,y:0,z:0,rx:0,ry:0,duration:stop,ease:'power2.inOut',onUpdate:applyCamera},0);
tl.to(cam,{z:100,y:-14,duration:dur-stop,ease:'power4.out',onUpdate:applyCamera},stop);

tl.to(q('header'),{autoAlpha:0,y:-45,duration:Math.min(.50,stop*.22),ease:'power2.in'},stop*.76);
