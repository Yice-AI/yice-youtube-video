// 编辑部看板：title / 1–4 card / footer。三阶克制配色 + 均衡纵向留白 + 自适应胶囊标签。
CLIPS.t7_editorial_board = (() => {
  const PINE = { bg:'#172322', surface:'#21312f', ink:'#f6f0df', sub:'#b5c9a9', accent:'#ff745a', accent2:'#7aaba0' };
  const twoDigits = n => String(n).padStart(2,'0');

  function panel(c,x,y,w,h,fill,stroke,radius=14,lineWidth=1.5) {
    c.beginPath();
    c.roundRect(x,y,w,h,radius);
    if (fill) {
      c.fillStyle=fill;
      c.fill();
    }
    if (stroke) {
      c.strokeStyle=stroke;
      c.lineWidth=lineWidth;
      c.stroke();
    }
  }

  function fontSpec(size,weight,face) {
    const family=face==='song'?'"Yice Song", "Songti SC", "Noto Serif SC", serif'
      :face===true?'"Yice Mono", ui-monospace, SFMono-Regular, Menlo, monospace'
      :'"Yice Sans", "PingFang SC", system-ui, sans-serif';
    return `${weight} ${size}px ${family}`;
  }

  function fitText(c,value,width,desired,weight=600,face='sans',minSize=24) {
    const text=String(value??'').trim();
    if (!text || width<20) return { shown:'', size:minSize, width:0 };
    c.font=fontSpec(desired,weight,face);
    const rawW=Math.max(1,c.measureText(text).width);
    const size=Math.max(minSize,Math.min(desired,Math.floor(desired*width/rawW)));
    c.font=fontSpec(size,weight,face);
    let shown=text;
    if (c.measureText(shown).width>width) {
      const chars=[...shown];
      while (chars.length && c.measureText(chars.join('')+'…').width>width) chars.pop();
      shown=chars.length?chars.join('')+'…':'';
    }
    return { shown, size, width:shown?c.measureText(shown).width:0 };
  }

  function label(c,value,x,y,width,desired,color,weight=600,face='sans',align='left') {
    const fit=fitText(c,value,width,desired,weight,face,24);
    if (!fit.shown) return 0;
    c.font=fontSpec(fit.size,weight,face);
    c.fillStyle=color;
    c.textAlign='left';
    c.textBaseline='middle';
    const drawX=align==='center'?x+(width-fit.width)/2:align==='right'?x+width-fit.width:x;
    c.fillText(fit.shown,drawX,y);
    return fit.width;
  }

  function tagPill(c,text,rightX,centerY,maxW,fill,stroke,ink,face='sans',weight=650) {
    const clean=String(text??'').trim();
    if (!clean || maxW<56) return 0;
    const fit=fitText(c,clean,maxW-28,24,weight,face,24);
    if (!fit.shown) return 0;
    const pillW=Math.min(maxW,Math.max(68,Math.ceil(fit.width+28)));
    const pillH=34;
    const x=rightX-pillW;
    const y=centerY-pillH/2;
    panel(c,x,y,pillW,pillH,fill,stroke,9,1);
    label(c,fit.shown,x,centerY,pillW,fit.size,ink,weight,face,'center');
    return pillW;
  }

  function badRow(c,text,x,centerY,width,progress,tokens,boxed=false,boxH=58) {
    if (!text || progress<=0 || width<80) return;
    c.save();
    c.globalAlpha*=progress;
    if (boxed) {
      panel(c,x,centerY-boxH/2,width,boxH,tokens.badBg,tokens.badBorder,11,1);
    }
    const padX=boxed?18:4;
    const iconSize=boxed?26:25;
    label(c,'✗',x+padX,centerY,28,iconSize,tokens.badMark,800,'sans');
    const textX=x+padX+34;
    const drawn=label(c,text,textX,centerY,width-(textX-x)-16,boxed?28:26,tokens.badInk,560,'sans');
    if (drawn>0) {
      c.strokeStyle=PAL.alpha(tokens.badMark,0.72);
      c.lineWidth=2;
      c.beginPath();
      c.moveTo(textX,centerY+1);
      c.lineTo(textX+drawn*U.clamp((progress-0.2)/0.8,0,1),centerY+1);
      c.stroke();
    }
    c.restore();
  }

  function goodRow(c,text,x,centerY,width,progress,tokens,boxH=60,desiredSize=28) {
    if (!text || progress<=0 || width<80) return;
    c.save();
    c.globalAlpha*=progress;
    const topY=centerY-boxH/2;
    panel(c,x,topY,width,boxH,tokens.goodBg,tokens.goodBorder,12,1.25);
    const chip=Math.min(32,Math.max(26,boxH-24));
    const chipX=x+16;
    panel(c,chipX,centerY-chip/2,chip,chip,tokens.goodChipBg,null,8,0);
    label(c,'✓',chipX,centerY,chip,24,tokens.goodChipInk,850,'sans','center');
    const textX=chipX+chip+14;
    label(c,text,textX,centerY,width-(textX-x)-18,desiredSize,tokens.goodInk,740,'sans');
    c.restore();
  }

  function arrangement(left,top,width,height,count,layout) {
    const gap=20;
    if (layout==='featured' && count>1 && width>=900) {
      const leadW=Math.round(width*0.495);
      const rightW=width-leadW-gap;
      const rightCount=count-1;
      const cardH=(height-gap*(rightCount-1))/rightCount;
      return [
        {x:left,y:top,w:leadW,h:height,lead:true},
        ...Array.from({length:rightCount},(_,i)=>({x:left+leadW+gap,y:top+i*(cardH+gap),w:rightW,h:cardH,lead:false}))
      ];
    }
    const columns=layout==='columns' && width>=900;
    const w=columns?(width-gap*(count-1))/count:width;
    const h=columns?height:(height-gap*(count-1))/count;
    return Array.from({length:count},(_,i)=>({
      x:left+(columns?i*(w+gap):0),
      y:top+(columns?0:i*(h+gap)),
      w,
      h,
      lead:false
    }));
  }

  function cardTokens(p,dark,heroDark,active) {
    if (heroDark) {
      return {
        surface:'#151922',
        border:active?p.accent:'#2A3140',
        shadow:'rgba(15,18,26,0.14)',
        ink:'#F8FAFC',
        sub:'#94A3B8',
        divider:'rgba(248,250,252,0.11)',
        badgeFill:active?p.accent:'rgba(248,250,252,0.12)',
        badgeStroke:active?null:'rgba(248,250,252,0.22)',
        badgeInk:'#FFFFFF',
        tagFill:'rgba(248,250,252,0.08)',
        tagStroke:'rgba(248,250,252,0.18)',
        tagInk:'#CBD5E1',
        badBg:'rgba(248,250,252,0.04)',
        badBorder:'rgba(248,250,252,0.09)',
        badMark:'#F87171',
        badInk:'#94A3B8',
        goodBg:'rgba(52,211,153,0.11)',
        goodBorder:'rgba(52,211,153,0.34)',
        goodChipBg:'#10B981',
        goodChipInk:'#FFFFFF',
        goodInk:'#F8FAFC'
      };
    }
    if (dark) {
      const surface=active?PAL.mix(p.surface,p.ink,0.09):p.surface;
      const chipInk=PAL.on(p.accent2,['#FFFFFF','#11161B',p.bg]);
      return {
        surface,
        border:active?p.accent:PAL.mix(p.bg,p.sub,0.34),
        shadow:null,
        ink:p.ink,
        sub:p.sub,
        divider:PAL.alpha(p.ink,0.10),
        badgeFill:active?p.accent:PAL.alpha(p.ink,0.09),
        badgeStroke:active?null:PAL.alpha(p.ink,0.18),
        badgeInk:active?PAL.on(p.accent,['#FFFFFF','#11161B',p.bg]):p.ink,
        tagFill:PAL.alpha(p.ink,0.07),
        tagStroke:PAL.alpha(p.ink,0.15),
        tagInk:p.sub,
        badBg:PAL.alpha(p.accent,0.09),
        badBorder:PAL.alpha(p.accent,0.22),
        badMark:p.accent,
        badInk:p.sub,
        goodBg:PAL.alpha(p.accent2,0.14),
        goodBorder:PAL.alpha(p.accent2,0.34),
        goodChipBg:p.accent2,
        goodChipInk:chipInk,
        goodInk:p.ink
      };
    }
    return {
      surface:p.surface,
      border:active?p.accent:PAL.mix(p.surface,p.ink,0.14),
      shadow:'rgba(17,20,28,0.055)',
      ink:p.ink,
      sub:p.sub,
      divider:PAL.alpha(p.ink,0.08),
      badgeFill:active?p.accent:PAL.mix(p.surface,p.bg,0.85),
      badgeStroke:active?null:PAL.mix(p.surface,p.ink,0.16),
      badgeInk:active?'#FFFFFF':p.ink,
      tagFill:PAL.mix(p.surface,p.bg,0.72),
      tagStroke:PAL.mix(p.surface,p.ink,0.13),
      tagInk:p.sub,
      badBg:PAL.mix(p.surface,p.bg,0.45),
      badBorder:PAL.alpha(p.ink,0.08),
      badMark:p.accent,
      badInk:PAL.mix(p.sub,p.surface,0.12),
      goodBg:PAL.mix(p.surface,p.bg,0.58),
      goodBorder:PAL.mix(p.surface,p.ink,active?0.18:0.11),
      goodChipBg:'#0F766E',
      goodChipInk:'#FFFFFF',
      goodInk:p.ink
    };
  }

  function card(c,time,ctx,p,config,row,index,current,featured) {
    const reveal=ctx.p(time,config.at,0.36);
    if (reveal<=0) return;
    const {x,y,w,h,lead}=row;
    const meta=config.data||{};
    const active=index===current;
    const dark=PAL.dark(p);
    const heroDark=!dark && lead;
    const tok=cardTokens(p,dark,heroDark,active);
    const ease=1-(1-reveal)**3;
    const slideY=(1-ease)*10;

    c.save();
    c.globalAlpha=(dark && index<current?0.86:1)*ease;
    c.translate(0,slideY);

    if (tok.shadow) panel(c,x,y+6,w,h,tok.shadow,null,16,0);
    panel(c,x,y,w,h,tok.surface,tok.border,16,active?2:1.5);

    const badgeText=meta.badge||twoDigits(index+1);
    const padX=lead?32:26;
    const hasTag=Boolean(meta.tag && time>=config.at+0.18);
    const pBad=ctx.p(time,config.at+0.08,0.26);
    const pGood=ctx.p(time,config.at+0.20,0.26);

    if (h>=380) {
      // 高卡（featured 主卡 / columns 分栏）：顶栏徽章与标签 + 标题论点区 + 分割线 + 底部正反对照区
      const headerY=y+44;
      panel(c,x+padX,headerY-18,58,36,tok.badgeFill,tok.badgeStroke,9,1);
      label(c,badgeText,x+padX,headerY,58,24,tok.badgeInk,780,true,'center');
      if (hasTag) {
        tagPill(c,meta.tag,x+w-padX,headerY,Math.min(180,w-140),tok.tagFill,tok.tagStroke,tok.tagInk);
      }

      const titleY=y+Math.round(h*0.235);
      const subY=titleY+Math.round(Math.min(68,h*0.12));
      label(c,config.text,x+padX,titleY,w-padX*2,lead?52:40,tok.ink,800,lead && !dark?'song':'sans');
      if (config.sub) {
        label(c,config.sub,x+padX,subY,w-padX*2,lead?29:26,tok.sub,520,'sans');
      }

      const hasCompare=Boolean(meta.bad || meta.good);
      if (hasCompare) {
        const divY=y+Math.round(h*0.47);
        c.strokeStyle=tok.divider;
        c.lineWidth=1;
        c.beginPath();
        c.moveTo(x+padX,divY);
        c.lineTo(x+w-padX,divY);
        c.stroke();

        const zoneTop=divY+22;
        const zoneBottom=y+h-30;
        const zoneH=zoneBottom-zoneTop;
        if (meta.bad && meta.good) {
          const badH=Math.min(72,Math.max(54,Math.round(zoneH*0.36)));
          const goodH=Math.min(92,Math.max(64,Math.round(zoneH*0.46)));
          const gapY=Math.max(14,Math.round((zoneH-badH-goodH)/2));
          const badCenter=zoneTop+badH/2+Math.max(0,Math.round((zoneH-badH-goodH-gapY)/2));
          const goodCenter=badCenter+badH/2+gapY+goodH/2;
          badRow(c,meta.bad,x+padX,badCenter,w-padX*2,pBad,tok,true,badH);
          goodRow(c,meta.good,x+padX,goodCenter,w-padX*2,pGood,tok,goodH,lead?31:28);
        } else if (meta.good) {
          goodRow(c,meta.good,x+padX,zoneTop+zoneH/2,w-padX*2,pGood,tok,Math.min(88,zoneH),lead?31:28);
        } else {
          badRow(c,meta.bad,x+padX,zoneTop+zoneH/2,w-padX*2,pBad,tok,true,Math.min(72,zoneH));
        }
      }
    } else if (h>=235) {
      // 中高卡（featured 右侧双叠卡 / 2 行横排）：顶栏序号+标题+右上角标签 + 副标题 + 干净正反对照
      const headerY=y+42;
      panel(c,x+padX,headerY-17,54,34,tok.badgeFill,tok.badgeStroke,9,1);
      label(c,badgeText,x+padX,headerY,54,24,tok.badgeInk,780,true,'center');
      const tagW=hasTag?tagPill(c,meta.tag,x+w-padX,headerY,156,tok.tagFill,tok.tagStroke,tok.tagInk):0;
      const titleX=x+padX+68;
      const titleW=w-(titleX-x)-padX-(tagW?tagW+14:0);
      label(c,config.text,titleX,headerY,titleW,35,tok.ink,760,'sans');

      if (config.sub) {
        label(c,config.sub,x+padX,y+90,w-padX*2,26,tok.sub,520,'sans');
      }

      c.strokeStyle=tok.divider;
      c.lineWidth=1;
      c.beginPath();
      c.moveTo(x+padX,y+118);
      c.lineTo(x+w-padX,y+118);
      c.stroke();

      if (meta.bad && meta.good) {
        const badY=y+150;
        const goodH=Math.min(64,Math.max(52,Math.round(h-212)));
        const goodY=y+h-24-goodH/2;
        badRow(c,meta.bad,x+padX,badY,w-padX*2,pBad,tok,false);
        goodRow(c,meta.good,x+padX,goodY,w-padX*2,pGood,tok,goodH,28);
      } else if (meta.good) {
        goodRow(c,meta.good,x+padX,y+Math.round((124+h-22)/2),w-padX*2,pGood,tok,60,28);
      } else if (meta.bad) {
        badRow(c,meta.bad,x+padX,y+Math.round((124+h-22)/2),w-padX*2,pBad,tok,false);
      }
    } else {
      // 紧凑横向卡（3–4 行 rows 或 featured 右侧 3 叠卡）：左半标题副标 + 右半正反对照
      const hasCompare=Boolean(meta.bad || meta.good);
      const splitRatio=hasCompare?0.48:0.82;
      const headerY=y+Math.min(40,Math.max(30,Math.round(h*0.32)));
      panel(c,x+22,headerY-16,50,32,tok.badgeFill,tok.badgeStroke,8,1);
      label(c,badgeText,x+22,headerY,50,24,tok.badgeInk,760,true,'center');

      const leftEnd=x+Math.round(w*splitRatio);
      const titleX=x+84;
      const tagReserve=(!hasCompare && hasTag)?136:0;
      label(c,config.text,titleX,headerY,leftEnd-titleX-14-tagReserve,31,tok.ink,750,'sans');
      if (config.sub && h>=128) {
        const subY=Math.min(y+h-26,headerY+42);
        label(c,config.sub,titleX,subY,leftEnd-titleX-14,25,tok.sub,510,'sans');
      }
      if (!hasCompare && hasTag) {
        tagPill(c,meta.tag,x+w-22,y+h/2,124,tok.tagFill,tok.tagStroke,tok.tagInk);
      }
      if (hasCompare) {
        const compX=leftEnd+12;
        const tagW=(hasTag && w>=1100)?tagPill(c,meta.tag,x+w-22,y+h/2,124,tok.tagFill,tok.tagStroke,tok.tagInk):0;
        const compW=x+w-22-(tagW?tagW+14:0)-compX;
        if (meta.bad && meta.good) {
          const badY=y+Math.round(h*0.31);
          const goodH=Math.min(52,Math.max(44,Math.round(h*0.36)));
          const goodY=y+h-Math.max(16,Math.round(h*0.11))-goodH/2;
          badRow(c,meta.bad,compX,badY,compW,pBad,tok,false);
          goodRow(c,meta.good,compX,goodY,compW,pGood,tok,goodH,26);
        } else if (meta.good) {
          goodRow(c,meta.good,compX,y+h/2,compW,pGood,tok,50,26);
        } else {
          badRow(c,meta.bad,compX,y+h/2,compW,pBad,tok,false);
        }
      }
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
      const p={...(ctx.pal||PINE),line:ctx.pal?PAL.mix(ctx.pal.bg,ctx.pal.sub,0.28):'#465750'};
      const dark=PAL.dark(p);
      const left=Math.max(safe.left,88), right=W-Math.max(safe.right,88), width=right-left;
      const top=Math.max(safe.top,64), bottom=H-Math.max(safe.bottom,172);
      const title=cues.find(cue=>cue.kind==='title');
      const cards=cues.filter(cue=>cue.kind==='card');
      const footer=cues.find(cue=>cue.kind==='footer');
      const current=cards.reduce((idx,cue,i)=>time>=cue.at?i:idx,-1);
      const gridY=top+174;
      const gridBottom=bottom-(footer?68:12);
      const height=gridBottom-gridY;
      const rows=arrangement(left,gridY,width,height,cards.length,data.layout);

      c.fillStyle=p.bg;
      c.fillRect(0,0,W,H);

      c.strokeStyle=dark?PAL.alpha(p.ink,0.045):PAL.alpha(p.ink,0.035);
      c.lineWidth=1;
      c.beginPath();
      for(let x=left;x<=right;x+=64){c.moveTo(x,top);c.lineTo(x,bottom);}
      for(let y=top;y<=bottom;y+=64){c.moveTo(left,y);c.lineTo(right,y);}
      c.stroke();

      // 顶部刊头与进度胶囊
      if (data.eyebrow) {
        c.fillStyle=p.accent;
        c.beginPath();
        c.roundRect(left,top+15,8,16,2);
        c.fill();
        label(c,data.eyebrow,left+18,top+23,width-180,25,p.sub,650,'sans');
      }
      const counterText=`${twoDigits(Math.max(0,current+1))} / ${twoDigits(cards.length)}`;
      panel(c,right-128,top+5,128,36,dark?PAL.alpha(p.ink,0.06):p.surface,p.line,18,1);
      label(c,counterText,right-128,top+23,128,24,p.sub,700,true,'center');

      if (!title || time>=title.at) {
        label(c,title?.text||data.title,left,top+88,width,62,p.ink,800,'song');
        if (title?.sub) {
          label(c,title.sub,left,top+140,width,28,p.sub,520,'sans');
        }
      }

      cards.forEach((cue,i)=>card(c,time,ctx,p,cue,rows[i],i,current,data.layout==='featured' && cards.length>1));

      // 底部收束结语：极简刊眉细线 + 强调色圆点导引（拒绝厚重双层底栏与下方字幕胶囊打架）
      if (footer && time>=footer.at) {
        const footAlpha=ctx.p(time,footer.at,0.28);
        c.save();
        c.globalAlpha*=footAlpha;
        const lineY=bottom-46;
        c.strokeStyle=PAL.alpha(p.ink,dark?0.14:0.10);
        c.lineWidth=1;
        c.beginPath();
        c.moveTo(left,lineY);
        c.lineTo(right,lineY);
        c.stroke();
        c.fillStyle=p.accent;
        c.beginPath();
        c.arc(left+6,bottom-19,4.5,0,Math.PI*2);
        c.fill();
        label(c,footer.text,left+20,bottom-19,width-28,26,p.ink,650,'sans');
        c.restore();
      }
    }
  };
})();
