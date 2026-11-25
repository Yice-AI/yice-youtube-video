// 依次点亮架构模块。箭头、节点与脉冲使用同一条可重放的曲线路径。
CLIPS.t4_blueprint_arch = (() => {
  const DEFAULT = { bg:'#10202b',surface:'#183240',ink:'#e4ece8',sub:'#a5c7cc',accent:'#ffd078',accent2:'#68d8eb' };
  const mixPoint=(a,b,u)=>({x:a.x+(b.x-a.x)*u,y:a.y+(b.y-a.y)*u});
  const curvePoint=(route,u)=>{
    const a=mixPoint(route[0],route[1],u),b=mixPoint(route[1],route[2],u),c=mixPoint(route[2],route[3],u);
    return mixPoint(mixPoint(a,b,u),mixPoint(b,c,u),u);
  };

  function label(c,value,x,y,width,size,color,weight=550,mono=false) {
    const text=String(value??'').trim();
    if (!text || width<24) return;
    const family=mono?'monospace':'system-ui, sans-serif';
    c.font=`${weight} ${size}px ${family}`;
    const fitted=Math.max(24,Math.min(size,Math.floor(size*width/Math.max(1,c.measureText(text).width))));
    c.font=`${weight} ${fitted}px ${family}`;
    const shown=[...text],length=shown.length;
    while(shown.length && c.measureText(shown.join('')+(shown.length<length?'…':'')).width>width) shown.pop();
    c.fillStyle=color;
    c.textBaseline='middle';
    c.fillText(shown.join('')+(shown.join('')===text?'':'…'),x,y);
  }

  function connect(c,a,b,p,time,active) {
    const sameRow=a.row===b.row;
    const dir=b.x>=a.x?1:-1;
    const start=sameRow?{x:dir>0?a.x+a.w:a.x,y:a.y+a.h/2}:{x:a.x+a.w/2,y:a.y+a.h};
    const end=sameRow?{x:dir>0?b.x:b.x+b.w,y:b.y+b.h/2}:{x:b.x+b.w/2,y:b.y};
    const control=sameRow?[
      {x:start.x+(end.x-start.x)*.5,y:start.y-21},
      {x:start.x+(end.x-start.x)*.5,y:end.y+21},
    ]:[
      {x:start.x,y:start.y+(end.y-start.y)*.52},
      {x:end.x,y:start.y+(end.y-start.y)*.48},
    ];
    const route=[start,...control,end];
    c.beginPath();
    c.moveTo(start.x,start.y);
    c.bezierCurveTo(control[0].x,control[0].y,control[1].x,control[1].y,end.x,end.y);
    c.strokeStyle=PAL.alpha(p.accent2,active?.74:.23);
    c.lineWidth=active?3:2;
    c.stroke();
    const tail=curvePoint(route,.85),angle=Math.atan2(end.y-tail.y,end.x-tail.x);
    c.beginPath();
    c.moveTo(end.x,end.y);
    c.lineTo(end.x-13*Math.cos(angle-.46),end.y-13*Math.sin(angle-.46));
    c.lineTo(end.x-13*Math.cos(angle+.46),end.y-13*Math.sin(angle+.46));
    c.closePath();
    c.fillStyle=PAL.alpha(p.accent2,active?.85:.33);
    c.fill();
    if (!active) return;
    const u=((time-a.at)*.70)%1;
    const dot=curvePoint(route,u);
    c.beginPath();
    c.arc(dot.x,dot.y,15,0,Math.PI*2);
    c.fillStyle=PAL.alpha(p.accent,.18*Math.sin(u*Math.PI));
    c.fill();
    c.beginPath();
    c.arc(dot.x,dot.y,6,0,Math.PI*2);
    c.fillStyle=PAL.alpha(p.accent,Math.min(1,.2+Math.sin(u*Math.PI)));
    c.fill();
  }

  return {
    safe:true,
    draw(c,time,{W,H,safe,data,cues,pal,p}) {
      const colors=pal||DEFAULT;
      const nodes=cues.filter(q=>q.kind!=='title');
      const left=Math.max(safe.left,94),right=W-Math.max(safe.right,94),width=right-left;
      const top=Math.max(safe.top,68),bottom=H-Math.max(safe.bottom,172);
      const title=data.title||cues.find(q=>q.kind==='title')?.text;
      c.fillStyle=colors.bg;
      c.fillRect(0,0,W,H);
      c.strokeStyle=PAL.mix(colors.bg,colors.sub,.15);
      c.lineWidth=1;
      c.beginPath();
      for(let x=left;x<=right;x+=46){c.moveTo(x,top);c.lineTo(x,bottom);}
      for(let y=top;y<=bottom;y+=46){c.moveTo(left,y);c.lineTo(right,y);}
      c.stroke();
      label(c,data.eyebrow,left,top+23,width,27,colors.accent2,700,true);
      label(c,title,left,top+102,width,66,colors.ink,780);
      const subtitle=cues.find(q=>q.kind==='title')?.sub;
      label(c,subtitle,left,top+157,width,29,colors.sub);
      const cols=Math.max(1,Math.min(width>=1300?4:3,nodes.length));
      const rows=Math.max(1,Math.ceil(nodes.length/cols)),gap=38;
      const w=(width-(cols-1)*gap)/cols;
      const start=top+202, available=bottom-start-22;
      const h=Math.min(282,(available-(rows-1)*gap)/rows);
      const y0=start+(available-(h*rows+gap*(rows-1)))/2;
      const layout=nodes.map((q,i)=>{
        const row=Math.floor(i/cols),column=i%cols;
        const x=left+(row%2?cols-1-column:column)*(w+gap);
        return {...q,x,y:y0+row*(h+gap),w,h,row};
      });
      layout.slice(0,-1).forEach((node,i)=>connect(c,node,layout[i+1],colors,time,time>=node.at));
      const current=layout.reduce((index,node,i)=>time>=node.at?i:index,-1);
      layout.forEach((node,i)=>{
        const {x,y,w,h}=node;
        const revealed=time>=node.at;
        const on=i===current;
        const progress=revealed?p(time,node.at,.38):0;
        c.beginPath();
        c.roundRect(x,y,w,h,19);
        c.fillStyle=on?PAL.mix(colors.surface,colors.accent2,.13):colors.surface;
        c.fill();
        c.strokeStyle=PAL.alpha(on?colors.accent2:colors.sub,on?.86:.40);
        c.lineWidth=on?3:2;
        c.stroke();
        c.fillStyle=PAL.alpha(colors.accent2,on?.9:.46);
        c.fillRect(x+22,y+17,Math.max(18,(w-44)*progress),3);
        if (!revealed) return;
        const labelWidth=w-48;
        const badge=node.data?.stage||node.data?.label||String(i+1).padStart(2,'0');
        label(c,badge,x+24,y+Math.min(48,h*.24),labelWidth,26,colors.accent2,700,true);
        label(c,node.text||String(node.data?.value??''),x+24,y+h*.52,labelWidth,Math.min(42,h*.27),colors.ink,760);
        label(c,node.sub,x+24,y+h*.77,labelWidth,Math.min(28,h*.20),colors.sub);
      });
    }
  };
})();
