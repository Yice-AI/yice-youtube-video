// 瑞士网格的行级揭示，全镜保持同一底色。
CLIPS.t6_swiss_card = {
  safe:true,
  draw(c,time,{W,H,box,data,cues}){
    const x=box.x+92, w=box.w-184;
    c.fillStyle='#e9e4d7';c.fillRect(0,0,W,H);
    const rows=cues.filter(q=>q.kind!=='title');
    const title=data.title||cues.find(q=>q.kind==='title')?.text||'';
    c.fillStyle='#192b29';c.font='bold 75px sans-serif';c.fillText(title,x,box.y+120,w);
    const h=Math.min(140,(box.h-210)/Math.max(rows.length,1));
    rows.forEach((q,i)=>{
      const p=Math.max(0,Math.min(1,(time-q.at)/.48));
      if(!p)return;
      const y=box.y+196+i*h;
      c.save();c.globalAlpha=p;c.strokeStyle='#727d71';c.beginPath();c.moveTo(x,y);c.lineTo(x+w,y);c.stroke();
      c.fillStyle='#ac4539';c.font='bold 35px monospace';c.fillText(String(i+1).padStart(2,'0'),x,y+60);
      c.fillStyle='#172925';c.font='bold 49px sans-serif';c.fillText(q.text||'',x+142,y+60+(1-p)*18,w-142);c.restore();
    });
  }
};
