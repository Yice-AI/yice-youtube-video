// 每个系列保留原量纲，游标按对应 cue 入点推进。
CLIPS.t5_data_ruler = {
  safe:true,
  draw(c,time,{W,H,box,data,cues,dur}){
    const series=data.series||[], left=box.x+100, width=box.w-220, top=box.y+110;
    c.fillStyle='#172322';c.fillRect(0,0,W,H);
    c.fillStyle='#eee7d4';c.font='bold 68px sans-serif';c.fillText(data.title||'',left,top,width);
    const max=Math.max(1,...series.map(row=>row.value));
    const rows=cues.filter(q=>q.kind==='bar'||q.kind==='point');
    for(const [i,row] of series.entries()){
      const y=top+140+i*Math.min(155,(box.h-190)/Math.max(series.length,1));
      const progress=Math.max(0,Math.min(1,(Math.min(time,dur*.72)-(rows[i]?.at??0))/.8));
      c.fillStyle='#d3dcce';c.font='32px sans-serif';c.fillText(row.label,left,y);
      c.fillStyle='#577069';
      for(let k=0;k<=60;k++)c.fillRect(left+width*k/60,y+19,2,k%5?12:24);
      const tip=left+width*row.value/max*progress;
      c.fillStyle=i===series.length-1?'#ff846c':'#b0cbbb';
      c.fillRect(left,y+47,tip-left,9);c.fillRect(tip-2,y+13,4,46);
      c.font='bold 37px monospace';c.textAlign='right';
      c.fillText(String(row.value)+' '+(data.unit||''),left+width,y);
      c.textAlign='left';
    }
  }
};
