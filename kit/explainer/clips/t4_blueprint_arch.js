// 三工种与生产线的模块图，信号流在镜头尾段停稳。
CLIPS.t4_blueprint_arch = {
  safe: true,
  draw(c, time, {W,H,box,data,cues,dur}) {
    const nodes = cues.filter(q => q.kind !== 'title');
    const t = Math.min(time,dur*.72);
    c.fillStyle='#11232f'; c.fillRect(0,0,W,H);
    c.strokeStyle='#213b48'; c.lineWidth=1;
    for(let x=0;x<W;x+=40){c.beginPath();c.moveTo(x,0);c.lineTo(x,H);c.stroke();}
    for(let y=0;y<H;y+=40){c.beginPath();c.moveTo(0,y);c.lineTo(W,y);c.stroke();}
    const left=box.x+80, top=box.y+95, width=box.w-160, y=top+box.h*.41;
    c.fillStyle='#e4ece8'; c.font='bold 66px sans-serif';
    c.fillText(data.title || cues.find(q=>q.kind==='title')?.text || '',left,top,width);
    const step=width/Math.max(1,nodes.length);
    nodes.forEach((q,i)=>{
      if(t<q.at)return;
      const x=left+i*step, w=step*.78;
      c.fillStyle='#1b3742'; c.fillRect(x,y,w,146);
      c.strokeStyle='#6caaa8'; c.lineWidth=3; c.strokeRect(x,y,w,146);
      c.fillStyle='#c6e4d6';c.font='22px monospace';c.fillText(String(i+1).padStart(2,'0'),x+24,y+38);
      c.font='bold 39px sans-serif';c.fillText(q.text||'',x+24,y+100,w-48);
      if(i<nodes.length-1) {
        c.strokeStyle='#80c8bf';c.beginPath();c.moveTo(x+w,y+73);c.lineTo(x+step,y+73);c.stroke();
        const progress=Math.min(1,(t-q.at)/Math.max(.5,(nodes[i+1].at-q.at)));
        c.fillStyle='#ff9e75';c.beginPath();c.arc(x+w+(step-w)*progress,y+73,8,0,Math.PI*2);c.fill();
      }
    });
  }
};
