// 编辑部看板：title / 1–4 card / footer。按当前口播放大信息权重，固定卡片外框。
CLIPS.t7_editorial_board = (() => {
  const PINE = { bg:'#172322', surface:'#21312f', ink:'#f6f0df', sub:'#b5c9a9', accent:'#ff745a', accent2:'#b5c9a9' };
  const twoDigits = number => String(number).padStart(2,'0');

  function panel(c,x,y,w,h,fill,stroke) {
    c.beginPath();
    c.roundRect(x,y,w,h,12);
    c.fillStyle=fill;
    c.fill();
    if (stroke) {
      c.strokeStyle=stroke;
      c.lineWidth=2;
      c.stroke();
    }
  }

  function label(c,value,x,y,width,desired,color,weight=550,mono=false) {
    const text=String(value??'').trim();
    if (!text || width<24) return 0;
    const family=mono?'monospace':'system-ui, sans-serif';
    c.font=`${weight} ${desired}px ${family}`;
    const size=Math.max(24,Math.min(desired,Math.floor(desired*width/Math.max(1,c.measureText(text).width))));
    c.font=`${weight} ${size}px ${family}`;
    let shown=text;
    if (c.measureText(shown).width>width) {
      const characters=[...shown];
      while (characters.length && c.measureText(characters.join('')+'…').width>width) characters.pop();
      shown=characters.join('')+'…';
    }
    c.fillStyle=color;
    c.textBaseline='middle';
    c.fillText(shown,x,y);
    return c.measureText(shown).width;
  }

  function comparison(c,text,x,y,width,value,isBad,p) {
    if (!text || value<=0) return;
    c.save();
    c.globalAlpha*=value;
    const accent=isBad?p.accent:p.accent2;
    label(c,isBad?'✗':'✓',x,y,27,27,accent,800);
    const drawn=label(c,text,x+33,y,width-33,27,isBad?p.sub:p.ink);
    if (isBad && drawn) {
      c.strokeStyle=accent;
      c.lineWidth=2;
      c.beginPath();
      c.moveTo(x+33,y);
      c.lineTo(x+33+drawn*U.clamp((value-.25)/.75),y);
      c.stroke();
    }
    c.restore();
  }

  function arrangement(left,top,width,height,count,layout) {
    const gap=18;
    if (layout==='featured' && count>1 && width>=900) {
      const lead=Math.round(width*.51);
      const h=(height-gap*(count-2))/(count-1);
      return [{x:left,y:top,w:lead,h:height,lead:true},
        ...Array.from({length:count-1},(_,i)=>({x:left+lead+gap,y:top+i*(h+gap),w:width-lead-gap,h}))];
    }
    const columns=layout==='columns' && width>=900;
    const w=columns?(width-gap*(count-1))/count:width;
    const h=columns?height:(height-gap*(count-1))/count;
    return Array.from({length:count},(_,i)=>({x:left+(columns?i*(w+gap):0),y:top+(columns?0:i*(h+gap)),w,h}));
  }

  function card(c,time,ctx,p,config,row,index,current) {
    const reveal=ctx.p(time,config.at,.36);
    if (reveal<=0) return;
    const {x,y,w,h,lead}=row;
    const meta=config.data||{};
    const active=index===current;
    c.save();
    c.globalAlpha=(index<current?.80:1)*(1-(1-reveal)**3);
    const dark=PAL.dark(p);
    const surface=active
      ? PAL.mix(p.surface,dark?p.ink:'#FFFFFF',.12)
      : dark?p.surface:PAL.mix(p.surface,p.bg,.20);
    panel(c,x,y,w,h,surface,active?p.accent:p.line);
    if (active) {
      c.fillStyle=p.accent;
      c.fillRect(x+6,y+12,6,(h-24)*reveal);
    }
    const titleY=y+(lead?104:36);
    const badgeX=x+23, badgeY=lead?y+29:titleY-17;
    const badge=meta.badge||twoDigits(index+1);
    if (active) panel(c,badgeX,badgeY,71,34,p.accent,null);
    const badgeInk=active?PAL.on(p.accent,[p.bg,p.ink,'#FFFFFF','#121619']):p.accent;
    label(c,badge,badgeX+11,badgeY+17,49,24,badgeInk,750,true);
    const compact=h<211 && w>=580;
    const start=lead?x+26:x+109;
    const textW=compact?w*.47-(start-x)-12:w-(start-x)-23;
    label(c,config.text,start,titleY,textW,lead?48:35,p.ink,740);
    label(c,config.sub,lead?start:(compact?start:x+24),titleY+(lead?69:42),compact?textW:w-48,lead?31:27,p.sub);
    const checkX=compact?x+w*.49:x+24;
    const checkY=compact?titleY:y+(lead?218:139);
    const checkWidth=w-(checkX-x)-24;
    comparison(c,meta.bad,checkX,checkY,checkWidth,ctx.p(time,config.at+.08,.26),true,p);
    comparison(c,meta.good,checkX,checkY+(meta.bad?37:0),checkWidth,ctx.p(time,config.at+.20,.24),false,p);
    if (meta.tag && time>=config.at+.21) {
      const tagW=Math.min(190,w-48);
      const tagX=x+w-tagW-22;
      const tagY=y+h-51;
      panel(c,tagX,tagY,tagW,36,PAL.mix(p.surface,p.accent2,.11),null);
      label(c,meta.tag,tagX+12,tagY+18,tagW-24,24,p.sub,680);
    }
    c.restore();
  }

  return {
    safe:true,
    init({cues,data}) {
      const count=cues.filter(cue=>cue.kind==='card').length;
      if (count<1 || count>4) throw new Error('t7_editorial_board 需要一至四张 card');
      if (data.layout!=null && !['rows','columns','featured'].includes(data.layout))
        throw new Error('t7_editorial_board 的 layout 须为 rows、columns 或 featured');
    },
    draw(c,time,ctx) {
      const {W,H,safe,cues,data}=ctx;
      const p={...(ctx.pal||PINE),line:ctx.pal?PAL.mix(ctx.pal.bg,ctx.pal.sub,.34):'#465750'};
      const left=Math.max(safe.left,80),right=W-Math.max(safe.right,80),width=right-left;
      const top=Math.max(safe.top,64),bottom=H-Math.max(safe.bottom,172);
      const title=cues.find(cue=>cue.kind==='title');
      const cards=cues.filter(cue=>cue.kind==='card');
      const footer=cues.find(cue=>cue.kind==='footer');
      const current=cards.reduce((index,cue,i)=>time>=cue.at?i:index,-1);
      const gridY=top+192,height=bottom-(footer?82:23)-gridY;
      const rows=arrangement(left,gridY,width,height,cards.length,data.layout);
      c.fillStyle=p.bg;
      c.fillRect(0,0,W,H);
      c.strokeStyle=ctx.pal?PAL.mix(p.bg,p.sub,.12):'#263833';
      c.lineWidth=1;
      c.beginPath();
      for(let x=left;x<=right;x+=64){c.moveTo(x,top);c.lineTo(x,bottom);}
      for(let y=top;y<=bottom;y+=64){c.moveTo(left,y);c.lineTo(right,y);}
      c.stroke();
      label(c,data.eyebrow,left,top+29,width-194,27,p.sub,650,true);
      panel(c,right-163,top+10,163,44,p.surface,p.line);
      label(c,`${twoDigits(current+1)} / ${twoDigits(cards.length)}`,right-144,top+32,130,26,p.sub,700,true);
      if (!title || time>=title.at) {
        label(c,title?.text||data.title,left,top+103,width,66,p.ink,760);
        label(c,title?.sub,left,top+156,width,31,p.sub);
      }
      cards.forEach((cue,i)=>card(c,time,ctx,p,cue,rows[i],i,current));
      if (footer && time>=footer.at) {
        panel(c,left,bottom-64,width,58,PAL.mix(p.surface,p.accent2,.09),p.line);
        label(c,footer.text,left+22,bottom-35,width-44,30,p.ink,650);
      }
    }
  };
})();
