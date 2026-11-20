/* Adapted registry motion patterns & Skill v2 Cinema Studio Craft.
   Origins/license: ../../docs/vocabulary-origins.md.
   All animation is on the parent GSAP timeline; no wall clock / CSS animation. */
(function(){
  'use strict';
  const Y=window.YF, NS='http://www.w3.org/2000/svg';
  const CINEMA_RECIPES=new Set(['split-compare','blueprint-diagram','cinematic-broll','terminal-over-footage','suspect-focus','footage-bigword','desk-dispatch','ruler-measure']);
  function node(tag,cls,parent,text){const e=document.createElement(tag);e.className=cls||'';if(text!=null)e.textContent=text;if(parent)parent.appendChild(e);return e;}
  function style(e,values){Object.assign(e.style,values);return e;}
  function rect(e,x,y,w,h){return style(e,{position:'absolute',left:x+'px',top:y+'px',width:w+'px',height:h+'px'});}
  function svg(parent){const e=document.createElementNS(NS,'svg');e.setAttribute('viewBox','0 0 1920 1080');rect(e,0,0,1920,1080);e.style.pointerEvents='none';e.dataset.layoutIgnore='true';parent.appendChild(e);return e;}
  function shape(parent,tag,attrs){const e=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);parent.appendChild(e);return e;}
  function markDecor(e){e.dataset.layoutIgnore='true';return e;}
  function header(c,title,source){
    const nodes=[],show=c.spec.props?.showTitle!==false;
    if(show&&title)nodes.push(node('div','v-heading',c.cam,title));
    if(source){const el=node('div','v-source',c.cam,source);if(!show)style(el,{top:'auto',bottom:'88px'});nodes.push(el);}
    if(nodes.length){c.tl.fromTo(nodes,{opacity:0,y:6},{opacity:1,y:0,duration:.15,ease:'power3.out'},.35);c.tl.to(nodes,{opacity:0,y:-8,duration:.12,ease:'power3.in'},Math.max(.65,c.dur-.7));}
  }
  function tag(c,text){if(text)node('div','v-tag',c.cam,text);}
  function card(c,x,y,w,h,rotation=0){const e=rect(node('div','v-card',c.cam),x,y,w,h);if(rotation)gsap.set(e,{rotation});return e;}
  function tape(parent,x,y,angle){const e=rect(node('div','yf-tape',parent),x,y,145,42);gsap.set(e,{rotation:angle});markDecor(e);}
  function settle(c,e,at=0){c.tl.fromTo(e,{y:28,scale:.97},{y:0,scale:1,duration:.5,ease:'power3.out',immediateRender:false},at);}
  function media(c,ref,parent){const e=ref&&c.m(ref.m);if(!e)throw new Error('配方缺少媒体槽');e.classList.add('v-media');parent.appendChild(e);return e;}
  function clock(c,fn){const state={t:0};fn(0);c.tl.to(state,{t:c.dur,duration:c.dur,ease:'none',onUpdate:()=>fn(state.t)},0);}
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function counter(c,e,value,at=.4,from=0,suffix='',duration=.9){const n={v:from};e.textContent=from+suffix;c.tl.to(n,{v:value,duration,ease:'power3.out',onUpdate:()=>e.textContent=n.v.toLocaleString('zh-CN',{maximumFractionDigits:Number.isInteger(value)?0:2})+suffix},at);}
  function drawn(c,e,at=.5,d=.5){const len=e.getTotalLength();gsap.set(e,{strokeDasharray:len,strokeDashoffset:len});c.tl.to(e,{strokeDashoffset:0,duration:d,ease:'power3.out'},at);}
  function push(c,e,value=true){const p=value===true?{}:value||{};e.dataset.camera='push';c.tl.fromTo(e,{scale:p.from??1},{scale:p.to??1.17,duration:Math.min(c.dur,p.duration??3),ease:'none',transformOrigin:'50% 50%',immediateRender:false},0);}
  function overlays(c,p){if(p.overlays?.length)c.root.classList.add('yv');for(const o of p.overlays||[]){
    const w=1920*(o.width??.42),h=o.height??420,box=card(c,o.x??(1920-w-140),o.y??220,w,h,o.angle??-2);
    if(o.media){const clip=rect(node('div','v-clip',box),12,12,w-24,h-24);media(c,o.media,clip);}
    if(o.text){const text=rect(node('div','',box,o.text),35,30,w-70,h-60);style(text,{font:'900 68px/1.2 var(--f-song)',color:'var(--paper-ink)',display:'grid',placeItems:'center'});}
    c.tl.fromTo(box,{y:80,scale:.94,opacity:0},{y:0,scale:1,opacity:1,duration:o.duration??.3,ease:'power3.out'},c.at(o.at,.8));
  }}

  /* ---------- Cinema Studio Shared Helpers ---------- */
  function cinemaAtmosphere(c,variant=''){
    const bg=markDecor(node('div','v-cinema-stage'+(variant?' '+variant:''),c.cam));
    const vig=markDecor(node('div','v-cinema-vignette',c.root));
    const grain=markDecor(node('div','v-cinema-grain',c.root));
    clock(c,t=>{
      const f=Math.floor(t*30);
      grain.style.transform=`translate(${(f*17)%36-18}px, ${(f*11)%28-14}px)`;
    });
    return {bg,vig,grain};
  }
  function cinemaChip(c,parent,text,at=.12,{dot=true,strikeAt=null}={}){
    if(!text)return null;
    const chip=node('div','v-cinema-chip',parent);
    if(dot)node('i','dot',chip);
    node('span','',chip,text);
    const strikeEl=node('i','strike',chip);
    c.tl.fromTo(chip,{opacity:0,x:-16},{opacity:1,x:0,duration:.24,ease:'power2.out'},at);
    if(strikeAt!=null)c.tl.to(strikeEl,{scaleX:1,duration:.24,ease:'power2.inOut'},c.at(strikeAt,at+.6));
    return chip;
  }
  function cinemaStamp(c,parent,text,x,y,at,{ivory=false,angle=-6,shakeTarget=null,fontSize=56}={}){
    const st=node('div','v-cinema-stamp'+(ivory?' ivory':''),parent,text);
    style(st,{left:x+'px',top:y+'px',fontSize:fontSize+'px',transform:'translate(-50%,-50%)'});
    c.tl.fromTo(st,{opacity:0,scale:1.78,rotation:angle-4},{opacity:.96,scale:1,rotation:angle,duration:.15,ease:'power4.in'},at);
    if(shakeTarget)c.tl.fromTo(shakeTarget,{x:0},{x:4,duration:.04,yoyo:true,repeat:3,ease:'none'},at+.15);
    return st;
  }
  function redactionLayer(c,items,parent=c.cam){
    for(const r of items||[]){
      const e=rect(node('div','v-redact',parent),r.x,r.y,r.w,r.h);
      markDecor(e);
      if(r.from!=null)c.tl.fromTo(e,{opacity:0},{opacity:1,duration:.08},c.at(r.from,0));
      if(r.to!=null)c.tl.to(e,{opacity:0,duration:.08},c.at(r.to,c.dur-.15));
    }
  }

  /* ---------- Existing Batch 1 / Batch 2 / EP03 Recipes ---------- */
  function news(c,p){
    header(c,p.headline||'原文作证',p.source+' · 采集 '+p.date);
    const w=p.zoom?1280:1650,h=w*1080/1920,box=card(c,135,215,w,h,-.65);
    tape(box,22,-18,-4);tape(box,w-160,-18,4);
    const clip=rect(node('div','v-clip',box),14,14,w-28,h-28),world=node('div','v-world',clip),scale=(w-28)/1920;
    const shot=media(c,p.shot,world);gsap.set(world,{scale});settle(c,box);
    if(p.focusRect){
      const view=z=>{const k=Math.min((w-28)/z.w,(h-28)/z.h);return {scale:k,x:(w-28-z.w*k)/2-z.x*k,y:(h-28-z.h*k)/2-z.y*k};};
      gsap.set(world,view(p.focusRect));world.dataset.camera='focus';
      for(const jump of p.cutZoom||[]){const z=jump.rect||{x:p.focusRect.x+p.focusRect.w*(1-1/jump.scale)/2,y:p.focusRect.y+p.focusRect.h*(1-1/jump.scale)/2,w:p.focusRect.w/jump.scale,h:p.focusRect.h/jump.scale};c.tl.set(world,view(z),c.at(jump.at,1.2));}
    }
    for(const h of p.highlight||[]){const mark=rect(node('div','v-highlight',world),h.x,h.y,h.w,h.h);c.tl.fromTo(mark,{scaleX:0},{scaleX:1,duration:.5,ease:'power3.out'},c.at(h.at,.55));}
    if(p.zoom){
      const z=p.zoom,zs=1.6,zw=Math.min(620,z.w*zs),zh=Math.min(520,z.h*zs),zx=1160,zy=360;
      const zoom=card(c,zx,zy,zw,zh),crop=rect(node('div','v-clip',zoom),0,0,zw,zh),copy=shot.cloneNode(true);
      zoom.style.border='2px solid var(--blue)';copy.id=c.sid+'-detail-media';crop.appendChild(copy);rect(copy,-z.x*zs,-z.y*zs,1920*zs,1080*zs);
      const line=shape(svg(c.cam),'path',{d:`M ${135+z.x*scale} ${215+z.y*scale} L ${zx} ${zy+zh/2}`,fill:'none',stroke:'var(--blue)','stroke-width':1});drawn(c,line,.8,.5);
      c.tl.fromTo(zoom,{x:-300,y:-70,scale:.625,opacity:0},{x:0,y:0,scale:1,opacity:1,duration:.55,ease:'power3.out'},.85);
    }
    tag(c,p.highlight?.length?'荧光标出原文 · 来源可核对':'来源保留在画面与素材账本');
  }
  function social(c,p){
    header(c,'需求原文',p.source||'原文排版 · 个人信息已隐去');
    const textHeight=p.text.split('\n').reduce((sum,line)=>sum+Math.max(1,Math.ceil([...line].length/26))*49,0),imageY=180+textHeight+24,height=p.image?imageY+335:280+textHeight;
    const box=card(c,450,Math.max(210,(1080-height)/2+10),1020,height,-.5),avatar=rect(node('div','v-avatar'+(p.publicAccount?'':' redacted'),box),40,42,64,64);
    if(p.avatar)media(c,p.avatar,avatar);
    node('div','v-post-name',box,p.publicAccount?(p.name||'公开机构'):'某位用户');node('div','v-post-handle',box,p.publicAccount?(p.handle||'公开账号'):'@已隐去');
    node('div','v-post-text',box,p.text);
    if(p.image){const shot=rect(node('div','v-clip',box),48,imageY,924,235);media(c,p.image,shot);}
    const meta=node('div','v-post-meta',box);node('span','',meta,p.time||'');
    for(const [key,label]of [['likes','赞'],['reposts','转'],['comments','评']])if(Number.isFinite(p.metrics?.[key])){const e=node('span','',meta);counter(c,e,p.metrics[key],.4,0,' '+label,.8);}
    settle(c,box);c.tl.to(box,{rotation:.3,duration:Math.max(.2,c.dur-.6),ease:'sine.inOut'},.6);
  }
  function chat(c,p){
    header(c,p.title||'把需求说清楚');let top=210;
    p.turns.forEach((turn,i)=>{
      const lines=Math.max(1,Math.ceil([...turn.text].length/31)),h=70+lines*48,w=1280,x=turn.role==='user'?440:200;
      const bubble=rect(node('div','v-bubble '+turn.role,c.cam),x,top,w,h),text=node('span','',bubble,turn.text),at=c.at(turn.at,i*.85);
      c.tl.fromTo(bubble,{opacity:0,y:18,scale:.98},{opacity:1,y:0,scale:1,duration:.35,ease:'power3.out'},at);
      if(p.typing){const dots=node('div','v-typing',bubble);for(let j=0;j<3;j++){const dot=node('i','',dots);c.tl.fromTo(dot,{opacity:.25,y:0},{opacity:1,y:-5,duration:.15,yoyo:true,repeat:1,ease:'sine.inOut'},at+j*.12);}c.tl.set(dots,{display:'none'},at+.6);c.tl.fromTo(text,{opacity:0},{opacity:1,duration:.1},at+.6);}
      top+=h+30;
    });
  }
  function device(c,p){
    header(c,p.title||'真实操作',p.url||'');
    const phone=p.chrome==='phone',w=phone?510:1600,h=phone?800:770,box=rect(node('div','v-browser',c.cam),(1920-w)/2,180,w,h);
    const bar=node('div','v-browser-bar',box);for(let i=0;i<3;i++)node('i','',bar);node('span','v-address',bar,p.chrome==='window'?'本机窗口':p.chrome==='phone'?'移动视图':p.url||'本地应用');
    const clip=rect(node('div','v-clip',box),0,62,w,h-62),first=media(c,p.media,clip);settle(c,box);
    if(p.swap){const second=media(c,p.swap,clip),at=c.at(p.swapAt,c.dur*.55);c.tl.fromTo(second,{x:w},{x:0,duration:.5,ease:'power3.out'},at);c.tl.to(first,{x:-w,duration:.5,ease:'power2.in'},at);}
    markDecor(node('div','v-glare',box));
    if(p.push)push(c,box,p.push);overlays(c,p);redactionLayer(c,p.redactions);
  }
  function laptop(c,p){
    header(c,p.title||'放到桌上，开始用');
    const rig=rect(node('div','',c.cam),320,170,1280,770);style(rig,{perspective:'1800px'});
    const shell=rect(node('div','v-browser',rig),0,0,1280,690);gsap.set(shell,{rotationY:p.angle??-7,rotationX:5,transformPerspective:1800});
    const screen=rect(node('div','v-clip',shell),10,8,1260,660);media(c,p.media,screen);markDecor(node('div','v-glare',shell));
    const base=rect(node('div','',rig),-70,707,1420,62);style(base,{background:'var(--st-dark)',clipPath:'polygon(5% 0,95% 0,100% 70%,94% 100%,6% 100%,0 70%)',boxShadow:'18px 28px 32px var(--rule)'});markDecor(base);
    const hinge=rect(node('div','',rig),440,714,400,8);hinge.style.background='var(--sub)';markDecor(hinge);
    if(p.dolly!==undefined&&!p.push){settle(c,rig);c.tl.to(rig,{scale:1+p.dolly,duration:Math.max(.3,c.dur-.5),ease:'sine.inOut'},.5);}else push(c,rig,p.push??true);
    redactionLayer(c,p.redactions,screen);
  }
  function filmed(c,p){
    header(c,p.title||'回看操作过程');const box=rect(node('div','v-browser',c.cam),170,190,1560,760),clip=rect(node('div','v-clip',box),0,0,1560,760);media(c,p.media,clip);
    const scan=rect(node('div','',box),0,0,1560,760);style(scan,{background:'repeating-linear-gradient(0deg,transparent 0 3px,var(--paper-ink) 3px 4px)',opacity:String((p.moire??.3)*.11),pointerEvents:'none'});markDecor(scan);markDecor(node('div','v-glare',box));
    clock(c,t=>{const a=p.handheld??.3;gsap.set(box,{rotationY:1.4+Math.sin(t*1.2)*a,rotationX:-.7+Math.cos(t*.9)*a,x:Math.sin(t*2.1)*a*3,y:Math.cos(t*1.7)*a*2,transformPerspective:1800});});
    redactionLayer(c,p.redactions,clip);
  }
  function cursor(c,p){
    header(c,p.title||'跟着操作看重点');const clip=rect(node('div','v-browser',c.cam),146,190,1600,780),world=node('div','v-world',clip);media(c,p.media,world);
    const log=p.cursorLog,samples=[];let x=log[0].x,y=log[0].y;
    for(let f=0;f<=Math.ceil(c.dur*60);f++){
      const t=f/60;let i=0;while(i+1<log.length&&log[i+1].t<t)i++;const a=log[i],b=log[Math.min(i+1,log.length-1)],k=clamp((t-a.t)/(b.t-a.t||1),0,1);
      x+=(a.x+(b.x-a.x)*k-x)*.12;y+=(a.y+(b.y-a.y)*k-y)*.12;samples.push({x,y});
    }
    const ink=svg(world),pointer=shape(ink,'path',{d:'M 0 0 L 0 32 L 9 24 L 17 40 L 24 36 L 15 21 L 29 21 Z',fill:'var(--paper-ink)',stroke:'var(--card)','stroke-width':2});
    for(const point of log.filter(v=>v.click)){
      const ring=shape(ink,'circle',{cx:point.x,cy:point.y,r:5,fill:'none',stroke:'var(--blue)','stroke-width':4});
      c.tl.fromTo(ring,{attr:{r:5},opacity:0},{attr:{r:42},opacity:1,duration:.18,ease:'power3.out'},point.t);c.tl.to(ring,{opacity:0,duration:.12},point.t+.18);
    }
    redactionLayer(c,p.redactions,world);
    clock(c,t=>{const point=samples[Math.min(samples.length-1,Math.floor(t*60))],z=1600/1920*(1+((p.zoom??1.7)-1)*clamp(t/.65,0,1));gsap.set(world,{scale:z,x:clamp(800-point.x*z,1600-1920*z,0),y:clamp(390-point.y*z,780-1080*z,0)});pointer.setAttribute('transform',`translate(${point.x} ${point.y})`);});
  }
  function terminal(c,p){
    header(c,p.title||'命令与结果');const height=76+Math.max(6,p.lines.length)*50+(p.success===false?0:90),box=rect(node('div','v-terminal',c.cam),250,Math.round((1080-height)/2)+35,1420,height);settle(c,box);
    p.lines.forEach((line,i)=>{const row=node('div','v-terminal-row',box);if(line.cmd)node('b','',row,'$');node('span','',row,line.text);c.tl.fromTo(row,{opacity:0,y:8},{opacity:1,y:0,duration:.12,ease:'power3.out'},.4+i*.06/(p.speed||1));});
    c.tl.to(box,{opacity:0,duration:.12},Math.max(.65,c.dur-.7));
    if(p.success!==false){const stamp=rect(node('div','v-terminal-stamp',box),1030,height-94,300,66);style(stamp,{color:'var(--stamp)',background:'var(--card)',border:'4px solid var(--stamp)',font:'34px var(--f-song)',textAlign:'center',paddingTop:'8px'});stamp.textContent='✓ 通过';c.tl.fromTo(stamp,{scale:1.3,opacity:0,rotation:-6},{scale:1,opacity:1,rotation:-4,duration:.25,ease:'power3.out'},Math.min(c.dur-.5,.6+p.lines.length*.06));}
  }
  function diff(c,p){
    header(c,p.title||'改了哪里',p.lang||'');
    const before=p.before.split('\n'),after=p.after.split('\n');
    [['修改前',before,'del',116],['修改后',after,'add',994]].forEach(([title,lines,kind,x])=>{
      const box=card(c,x,230,810,650);box.classList.add('v-code');node('div','v-code-label',box,title);
      lines.forEach((line,i)=>{const changed=kind==='del'?!after.includes(line):!before.includes(line),row=node('div','v-code-row'+(changed?' '+kind:''),box);node('span','no',row,String(i+1));node('span','',row,line);if(changed)c.tl.fromTo(row,{opacity:0,x:kind==='add'?18:-18},{opacity:1,x:0,duration:.45,ease:'power3.out'},.4+i*.06);});settle(c,box);
    });
  }
  function bars(c,p){
    header(c,p.title||'同一批素材，前后对比',p.source||'');const box=card(c,215,220,1490,660),max=Math.max(1,...p.items.map(x=>x.value)),step=1290/p.items.length,width=140,centers=[];
    for(let i=0;i<=5;i++){const line=rect(node('div','',box),100,80+i*94,1290,1);line.style.background='var(--rule)';markDecor(line);}
    p.items.forEach((item,i)=>{const x=100+i*step+(step-width)/2,h=420*item.value/max,bar=rect(node('div','v-bar-column',box),x,530-h,width,h);centers.push(x+width/2);bar.style.backgroundColor=i===(p.highlight??0)?'var(--hl)':'color-mix(in srgb,var(--paper-ink) 85%,transparent)';gsap.set(bar,{transformOrigin:'50% 100%'});c.tl.fromTo(bar,{scaleY:0},{scaleY:1,duration:.9,ease:'power3.out'},.3+i*.08);
      const value=rect(node('div','v-number',box),x-45,470-h,width+130,65);counter(c,value,item.value,.3+i*.08,0,item.unit||'');rect(node('div','v-label',box,item.label),x-30,560,width+110,70);
    });
    if(p.items.length===2&&p.items[0].value>0){
      const x=centers[0]+width/2+24,w=centers[1]-width/2-24-x,delta=(p.items[1].value/p.items[0].value-1)*100,line=rect(node('div','v-measure-line',box),x,300,w,3);line.style.background='var(--blue)';
      for(const edge of [0,w-2]){const cap=rect(node('div','',line),edge,-9,2,21);cap.style.background='var(--blue)';}
      const label=rect(node('div','v-measure-label',box,(delta<0?'−':'+')+Math.abs(delta).toFixed(1)+'%'),x+(w-320)/2,220,320,70);style(label,{font:'52px var(--f-mono)',color:'var(--blue)',textAlign:'center',background:'var(--card)'});c.tl.fromTo([line,label],{opacity:0},{opacity:1,duration:.25},.6);c.tl.to([line,label],{opacity:0,duration:.12},Math.max(.65,c.dur-.7));
    }
    settle(c,box);
  }
  function ring(c,p){
    header(c,p.title||'看得见的变化');const root=svg(c.cam),r=320,len=2*Math.PI*r;
    shape(root,'circle',{cx:960,cy:540,r,fill:'none',stroke:'var(--rule)','stroke-width':28});
    const circle=shape(root,'circle',{cx:960,cy:540,r,fill:'none',stroke:'var(--blue)','stroke-width':28,'stroke-linecap':'round',transform:'rotate(-90 960 540)'});gsap.set(circle,{strokeDasharray:len,strokeDashoffset:len*(1-(p.from||0)/100)});c.tl.to(circle,{strokeDashoffset:len*(1-p.value/100),duration:.9,ease:'power3.out'},.3);
    const n=rect(node('div','',c.cam),560,425,800,190);style(n,{font:'900 160px/1 var(--f-song)',textAlign:'center'});counter(c,n,p.value,.3,p.from||0,'%');style(rect(node('div','v-label',c.cam,p.label),560,625,800,70),{textAlign:'center'});
    const seal=rect(node('div','',c.cam,'完成'),1270,720,170,70);style(seal,{border:'5px solid var(--stamp)',color:'var(--stamp)',font:'44px var(--f-song)',textAlign:'center'});c.tl.fromTo(seal,{scale:1.4,rotation:-12,opacity:0},{scale:1,rotation:-8,opacity:1,duration:.25,ease:'power3.out'},1.2);
  }
  function race(c,p){
    header(c,p.title,p.source);
    const count=Math.max(...p.frames.map(f=>f.items.length)),hasLabels=p.frames.some(f=>f.label),height=64+count*94+(hasLabels?56:0),box=card(c,160,Math.round((1080-height)/2)+35,1600,height),names=[...new Set(p.frames.flatMap(f=>f.items.map(x=>x.label)))],rows={};
    box.classList.add('v-race-card');box.style.overflow='hidden';
    const phase=hasLabels?rect(node('div','v-label v-race-phase',box),30,22,1500,48):null,top=32+(hasLabels?56:0);
    names.forEach(name=>{const row=rect(node('div','v-race-row',box),30,top,1540,82),label=rect(node('div','v-label',row,name),0,20,340,60),bar=rect(node('div','v-race-bar',row),350,12,0,62),value=rect(node('div','v-number',row),1320,14,210,70);row.dataset.label=name;rows[name]={row,label,bar,value};});
    clock(c,t=>{
      const local=Math.max(0,t-.35);let fi=0;while(fi+1<p.frames.length&&p.frames[fi+1].t<=local)fi++;
      const a=p.frames[Math.max(0,fi-1)],b=p.frames[fi],raw=fi===0?1:clamp((local-b.t)/.28,0,1),k=raw*raw*(3-2*raw),rank=f=>[...f.items].sort((x,y)=>y.value-x.value).map(x=>x.label),ar=rank(a),br=rank(b),growth=1-Math.pow(1-clamp((t-.15)/.65,0,1),3);
      const values=names.map(name=>{const av=a.items.find(i=>i.label===name),bv=b.items.find(i=>i.label===name);return {name,av,bv,value:(av?.value||0)+((bv?.value||0)-(av?.value||0))*k};}),max=Math.max(1,...values.map(x=>x.value));
      if(phase)phase.textContent=(k<.5?a:b).label||'';
      for(const item of values){const {name,av,bv,value}=item,ai=ar.indexOf(name),bi=br.indexOf(name),pos=(ai<0?count:ai)+((bi<0?count:bi)-(ai<0?count:ai))*k,row=rows[name];row.row.style.top=(top+pos*94)+'px';row.row.style.opacity=av&&bv?'1':av?String(1-k):bv?String(k):'0';const labels=ai===bi&&ai>=0?1:raw<.12?(av?1-raw/.12:0):raw>.88?(bv?(raw-.88)/.12:0):0;row.label.style.opacity=String(labels);row.value.style.opacity=String(labels);row.bar.style.width=(950*value/max*growth)+'px';row.bar.style.background=(k<.5?ar:br)[0]===name?'var(--hl)':'var(--paper-ink)';const display=(raw>=.88?bv:av)||bv||av;row.value.style.opacity=String(labels);row.value.textContent=(display?.value||0).toLocaleString('zh-CN',{maximumFractionDigits:1})+(display?.unit||'');}
    });
  }
  function hub(c,p){
    header(c,p.title||'把关系连起来');const root=svg(c.cam),order=p.order||p.nodes.map((_,i)=>i);
    p.nodes.forEach((value,i)=>{const angle=-Math.PI/2+i*2*Math.PI/p.nodes.length,x=960+Math.cos(angle)*600,y=570+Math.sin(angle)*300;
      const line=shape(root,'path',{d:`M 960 570 L ${x} ${y}`,fill:'none',stroke:'var(--blue)','stroke-width':2}),at=.35+Math.max(0,order.indexOf(i))*.3;drawn(c,line,at,.3);
      const box=card(c,x-160,y-55,320,110,-.4+i*.16);style(box,{display:'grid',placeItems:'center',font:'34px var(--f-sans)'});box.textContent=typeof value==='string'?value:value.text;c.tl.fromTo(box,{opacity:0,scale:.9},{opacity:1,scale:1,duration:.3,ease:'power3.out'},at);c.tl.to(box,{backgroundColor:'var(--hl)',duration:.2},at+.25);
      if(i!==order.at(-1))c.tl.to(box,{backgroundColor:'var(--card)',duration:.2},at+.55);
    });
    const center=card(c,750,480,420,180,.6);style(center,{display:'grid',placeItems:'center',font:'900 60px var(--f-song)'});center.textContent=p.center;settle(c,center);
  }
  function photos(c,p){
    header(c,p.title||'真实素材，逐张看',p.images.length+' 张素材');const frames=[];
    p.images.forEach((ref,i)=>{const f=card(c,0,0,340,250,(i%5-2)*2),clip=rect(node('div','v-clip',f),12,12,316,226);media(c,ref,clip).style.objectFit='cover';frames.push(f);});
    const focus=p.focus||0,at=c.at(p.focusAt,1.05),pos=(i,t)=>{const u=((i-focus)*.145+.5-t*.12)%1.45;return {x:u*2250-320,y:500+Math.sin(u*Math.PI*2)*155};};
    clock(c,t=>{const k=clamp((t-at)/.6,0,1),ease=1-(1-k)**3;frames.forEach((f,i)=>{const a=pos(i,Math.min(t,at));if(i===focus){gsap.set(f,{x:a.x+(528-a.x)*ease,y:a.y+(230-a.y)*ease,scale:1+(864/340-1)*ease,rotation:(i%5-2)*2*(1-ease),transformOrigin:'0 0',zIndex:20});}else gsap.set(f,{x:a.x,y:a.y,filter:`brightness(${1-.4*ease})`});});});
  }
  function hand(c,p){
    header(c,p.title||'重点，画出来');if(p.media){const clip=rect(node('div','v-clip',c.cam),116,195,1688,740);media(c,p.media,clip);}
    const b=p.target,color=p.color==='stamp'?'var(--stamp)':'var(--blue)',x=b.x,y=b.y,w=b.w,h=b.h;
    let d=p.kind==='circle'?`M ${x+w} ${y+h/2} C ${x+w+8} ${y-h/3},${x-w/6} ${y-h/3},${x} ${y+h/2} S ${x+w} ${y+h*1.4},${x+w-8} ${y+h/2+5}`:
      p.kind==='underline'?`M ${x} ${y+h} Q ${x+w*.3} ${y+h-5},${x+w*.6} ${x+w} ${y+h}`:
      p.kind==='box'?`M ${x+3} ${y+2} L ${x+w} ${y} L ${x+w+2} ${y+h} L ${x} ${y+h+3} Z`:
      `M ${Math.max(130,x-180)} ${y-90} Q ${x-45} ${y-110},${x+w/2} ${y+h/2} M ${x+w/2-36} ${y+h/2-8} L ${x+w/2} ${y+h/2} L ${x+w/2-8} ${y+h/2-36}`;
    if(p.kind==='underline')d=`M ${x} ${y+h} Q ${x+w*.3} ${y+h-5},${x+w*.6} ${y+h+2} T ${x+w} ${y+h}`;
    const path=shape(svg(c.cam),'path',{d,fill:'none',stroke:color,'stroke-width':5,'stroke-linecap':'round','stroke-linejoin':'round'});drawn(c,path,.35,.5);
    clock(c,t=>gsap.set(path,{x:Math.sin(t*12)*.2,y:Math.cos(t*9)*.2}));
    if(p.label){const size=1080*(p.labelHeight??.08),width=Math.min(1600,Math.max(500,[...p.label].length*size)),label=rect(node('div','',c.cam,p.label),clamp(x,116,1804-width),clamp(y+h+26,140,945-size),width,size*1.2);style(label,{font:`900 ${size}px/1.1 var(--f-sans)`,color});gsap.set(label,{rotation:-2});c.tl.fromTo(label,{opacity:0,scale:.93},{opacity:1,scale:1,duration:.2,ease:'power3.out'},.7);}
  }
  function swap(c,p){
    const prefix=p.prefix||'',pw=[...prefix].length*125,left=Math.max(116,(1920-pw-720)/2),base=rect(node('div','',c.cam),left,430,pw+760,180);style(base,{font:'900 120px/1.25 var(--f-song)',whiteSpace:'nowrap'});node('span','',base,prefix);
    const slot=rect(node('div','',base),pw,0,760,170);style(slot,{overflow:'hidden',background:'var(--hl)',color:'var(--paper-ink)'});
    p.words.forEach((word,i)=>{const e=rect(node('div','v-swap-word',slot,word),16,0,728,170),at=i*(p.interval||.8);e.style.background='var(--hl)';if(i)c.tl.fromTo(e,{y:180},{y:0,duration:.35,ease:'power3.out'},at);if(i<p.words.length-1)c.tl.to(e,{y:-180,duration:.35,ease:'power2.in'},(i+1)*(p.interval||.8));});
  }
  function slam(c,p){
    const line=node('div','v-slam',c.cam);[...p.text].forEach((ch,i)=>{const e=node('span','',line,ch);c.tl.fromTo(e,{scale:1.18,y:-25},{scale:1,y:0,duration:.18,ease:'power3.out',immediateRender:false},i*.012);});
    c.tl.to(line,{x:2,y:2,duration:.04},.22).to(line,{x:0,y:0,duration:.08},.26);tag(c,p.sub||'一句结论，留下重点');
  }
  function fullMedia(c,ref,parent=c.cam){const box=rect(node('div','v-clip v-full-media',parent),0,0,1920,1080);media(c,ref,box);return box;}
  function montage(c,p){
    p.clips.forEach((clip,i)=>{const frame=fullMedia(c,clip);gsap.set(frame,{opacity:0,scale:1.02});c.tl.set(frame,{opacity:1},clip.at);if(i<p.clips.length-1)c.tl.set(frame,{opacity:0},clip.at+clip.duration);c.tl.fromTo(frame,{scale:1.02},{scale:1.12,duration:Math.min(.32,clip.duration*.45),ease:'power3.out'},clip.at);c.tl.to(frame,{scale:1.05,duration:Math.min(.2,clip.duration*.25),ease:'power2.out'},clip.at+Math.min(.32,clip.duration*.45));});
    if(p.label){const e=rect(node('div','v-montage-label',c.cam,p.label),130,770,1640,180);style(e,{font:'900 132px/1.1 var(--f-song)',color:'var(--card)',textShadow:'0 3px 18px #232327'});}
  }
  function quote(c,p){
    const full=rect(node('div','',c.cam,p.text),180,250,1560,420);style(full,{font:'900 82px/1.4 var(--f-song)'});
    const at=p.keywordAt??1.0,photoAt=p.photoAt??at+1.3;
    c.tl.to(full,{opacity:0,duration:p.fadeDuration??.5},at);
    if(p.image){const picture=fullMedia(c,p.image);gsap.set(picture,{opacity:0});c.tl.set(picture,{opacity:1},photoAt);push(c,picture,{duration:c.dur,to:1.12});}
    const keys=rect(node('div','v-quote-keys',c.cam,p.keywords.join(' · ')),150,680,1620,180);style(keys,{font:'900 125px/1.1 var(--f-song)',color:'var(--ink)'});
    if(p.image)c.tl.set(keys,{color:'var(--card)',textShadow:'0 2px 16px #232327'},photoAt);
    c.tl.fromTo(keys,{opacity:0},{opacity:1,duration:.25},at+.15);tag(c,p.source||'');
    if(p.stamp)Y.stamp(c.cam,c.tl,p.stamp,{x:p.stampX??1260,y:p.stampY??560},c.at(p.stampAt,photoAt+.8),{size:p.stampSize??118});
  }
  function contrast(c,p){
    [[p.left,p.leftHeight??.72,210,p.leftLabel],[p.right,p.rightHeight??.54,1120,p.rightLabel]].forEach(([ref,height,x,label],i)=>{
      const h=height*1080,box=rect(node('div','v-contrast-object',c.cam),x,950-h,620,h);media(c,ref,box);style(box,{filter:'drop-shadow(12px 18px 20px rgba(28,32,36,.18))'});
      c.tl.fromTo(box,{y:50,opacity:0},{y:0,opacity:1,duration:.3,ease:'power3.out'},i*.2);
      if(label){const t=rect(node('div','',c.cam,label),x,118,620,100);style(t,{font:'900 76px/1.1 var(--f-song)',textAlign:'center'});}
    });push(c,c.cam,{duration:c.dur,to:1.035});
    if(p.title){const title=rect(node('div','v-contrast-title',c.cam,p.title),240,72,1440,110);style(title,{font:'900 82px/1.1 var(--f-song)',textAlign:'center',color:'var(--paper-ink)'});c.tl.fromTo(title,{y:-18,opacity:0},{y:0,opacity:1,duration:.25,ease:'power3.out'},.15);}
    if(Array.isArray(p.countdown)){p.countdown.forEach((value,i)=>{const e=rect(node('div','v-contrast-countdown',c.cam,value),860,360,200,180);style(e,{font:'900 168px/1 var(--f-song)',textAlign:'center',color:'var(--stamp)'});c.tl.fromTo(e,{scale:1.5,opacity:0},{scale:1,opacity:1,duration:.18,ease:'back.out(1.5)'},c.at(p.countdownAt??.65)+i*.65);c.tl.to(e,{opacity:0,duration:.1},c.at(p.countdownAt??.65)+i*.65+.48);});}
    if(p.stamp){const stamps=Array.isArray(p.stamp)?p.stamp:[{text:p.stamp}];stamps.forEach((stamp,i)=>{const x=i===0?390:1270;Y.stamp(c.cam,c.tl,stamp.text,{x,y:570},c.at(stamp.at??1.95+i*.12),{size:126});});}
  }
  function stacked(c,p,animated=true){
    const rng=Y.rng(c.sid),group=rect(node('div','',c.cam),0,0,1920,1080);
    p.items.forEach((item,i)=>{const count=p.items.length,columns=count>10?7:count>4?4:count,w=item.width??(count>10?340:580),x=item.x??(135+(i%columns)*(1650-w)/Math.max(1,columns-1)+(rng()-.5)*90),y=item.y??(180+Math.floor(i/columns)*(count>10?125:150)),h=item.height??w*.8;
      const frame=rect(node('div','v-cutout-object',group),x,y,w,h);media(c,item,frame);style(frame,{zIndex:10+(item.depth??i%3),filter:'drop-shadow(9px 16px 14px rgba(28,32,36,.18))'});gsap.set(frame,{rotation:item.angle??(rng()-.5)*12});
      if(animated)c.tl.fromTo(frame,{x:(i%2?1:-1)*900,y:160,opacity:0,scale:.8},{x:0,y:0,opacity:1,scale:1,duration:p.enterDuration??.3,ease:'power3.out'},i*(p.stagger??.2));
    });return group;
  }
  function stack(c,p){
    const group=stacked(c,p);push(c,group,{duration:c.dur,to:1.07});
    if(p.showTitle===false)return;
    const title=rect(node('div','v-stack-title',c.cam,p.title),130,735,1660,210);style(title,{font:'900 164px/1.1 var(--f-song)',color:'var(--paper-ink)',textShadow:'0 3px 0 var(--card),0 8px 26px var(--card)',textAlign:'center'});
    c.tl.fromTo(title,{y:80,scale:1.2,opacity:0},{y:0,scale:1,opacity:1,duration:.22,ease:'back.out(1.2)'},p.titleAt??Math.min(c.dur-.5,(p.items.length-1)*(p.stagger??.2)+.3));
  }
  function paper(c,p){
    const mode=p.mode||'zip',at=p.changeAt??.7,d=p.changeDuration??1;
    const group=p.items?.length?stacked(c,p,false):card(c,480,250,960,570,-2);
    if(!p.items?.length){const t=rect(node('div','',group,p.objectLabel||'文件'),60,140,840,220);style(t,{font:'900 150px/1.2 var(--f-song)',color:'var(--paper-ink)',textAlign:'center'});}
    if(mode==='zip'){
      c.tl.to(group,{scaleX:.08,scaleY:.06,x:750,y:250,opacity:0,duration:d,ease:'power3.in',transformOrigin:'50% 50%'},at);
      const zip=card(c,660,240,600,560,1),stripe=rect(node('div','v-zip-teeth',zip),281,0,38,270);markDecor(stripe);
      const text=rect(node('div','',zip,p.fileLabel||'photos.zip'),30,310,540,150);style(text,{font:'900 75px/1.2 var(--f-song)',color:'var(--paper-ink)',textAlign:'center'});
      c.tl.fromTo(zip,{scale:.2,opacity:0,y:80},{scale:1,opacity:1,y:0,duration:.3,ease:'back.out(1.4)'},at+d-.12);
    }else if(mode==='stamp')Y.stamp(c.cam,c.tl,p.stamp||'完成',{x:650,y:360},at,{size:150});
    else {
      const second=group.cloneNode(true);for(const e of second.querySelectorAll('[id]'))e.removeAttribute('id');c.cam.appendChild(second);group.style.clipPath='polygon(0 0,53% 0,48% 20%,53% 40%,48% 60%,53% 80%,48% 100%,0 100%)';second.style.clipPath='polygon(53% 0,100% 0,100% 100%,48% 100%,53% 80%,48% 60%,53% 40%,48% 20%)';
      c.tl.to(group,{x:-500,rotation:-12,duration:d,ease:'power2.in'},at);c.tl.to(second,{x:500,rotation:12,duration:d,ease:'power2.in'},at);
    }
    if(p.caption){const t=rect(node('div','',c.cam,p.caption),140,860,1640,120);style(t,{font:'900 90px/1.1 var(--f-song)',textAlign:'center'});c.tl.fromTo(t,{opacity:0,y:20},{opacity:1,y:0,duration:.2},at+d);}
    push(c,c.cam,{duration:c.dur,to:1.035});
  }
  function brand(c,p){
    if(p.background){const bg=fullMedia(c,p.background);push(c,bg,{duration:c.dur,to:1.17});const shade=rect(node('div','',c.cam),0,0,1920,1080);style(shade,{background:'rgba(20,20,22,.45)'});markDecor(shade);}
    const h=1080*(p.logoHeight??.38),logo=rect(node('div','v-brand-logo',c.cam),460,170,1000,h);media(c,p.logo,logo);
    c.tl.fromTo(logo,{scale:.85,opacity:0},{scale:1,opacity:1,duration:.25,ease:'power3.out'},.05);
    const line=rect(node('div','',c.cam,p.line),150,220+h,1620,180);style(line,{font:'900 124px/1.15 var(--f-song)',textAlign:'center'});c.tl.fromTo(line,{y:25,opacity:0},{y:0,opacity:1,duration:.22},.35);
    if(!p.background)push(c,c.cam,{duration:c.dur,to:1.045});tag(c,p.source||'官方品牌标志');
  }
  function stickerLabel(c,p,parent=c.cam){
    const e=rect(node('div','v-sticker',parent,p.text),p.x??150,p.y??650,p.width??1620,230),colors={highlight:'var(--hl)',stamp:'var(--stamp)',blue:'var(--blue)'};
    style(e,{color:colors[p.ink||'highlight'],font:`900 ${p.fontSize??150}px/1.12 var(--f-sans)`,webkitTextStroke:`${p.stroke??10}px var(--card)`,paintOrder:'stroke fill',filter:'drop-shadow(7px 10px 1px rgba(28,32,36,.3))',textAlign:'center'});
    gsap.set(e,{rotation:p.angle??-3});c.tl.fromTo(e,{scale:.65,opacity:0},{scale:1,opacity:1,duration:.15,ease:'back.out(1.5)'},c.at(p.at,.3));return e;
  }
  function sticker(c,p){if(p.background){const bg=fullMedia(c,p.background);push(c,bg,{duration:c.dur,to:1.12});}stickerLabel(c,p);}
  function reaction(c,p){
    if(p.background){const bg=fullMedia(c,p.background);push(c,bg,{duration:c.dur,to:1.08});}
    const figure=rect(node('div','v-reaction-person',c.cam),p.personX??1060,160,690,810);media(c,p.person,figure);c.tl.fromTo(figure,{x:220,opacity:0},{x:0,opacity:1,duration:.22,ease:'power3.out'},.1);
    stickerLabel(c,{...p,x:p.x??130,y:p.y??600,width:p.width??1100,fontSize:p.fontSize??122});tag(c,p.commentaryLabel||'我们的评论 · 人物未为本产品代言');
  }
  const SHOT_COLORS={real:'var(--sw-real)',screen:'var(--sw-screen)',graphic:'var(--sw-graphic)'};
  function shotWall(c,p){
    const world=rect(node('div','v-world',c.cam),0,0,1920,1080),win=p.window||60,X0=480,TW=1040,px=TW/win,rows=p.rows,rowH=p.rowHeight||(rows.length>3?118:rows.length>2?138:160),top=p.top??Math.round(590-rows.length*rowH/2);
    c.tl.fromTo(world,{scale:1},{scale:1.035,duration:c.dur,ease:'none',transformOrigin:'55% 50%'},0);
    const ruler=rect(node('div','v-sw-ruler',world),X0,top-74,TW,40);markDecor(ruler);
    for(let s=0;s<=win;s++){const t=rect(node('i','',ruler),s*px,s%10?26:s%5?18:6,s%5?1:2,s%10?14:34);markDecor(t);}
    for(let s=0;s<=win;s+=10){const l=rect(node('div','v-sw-tc',world,String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')),X0+s*px-60,top-122,120,34);style(l,{textAlign:'center'});}
    rows.forEach((row,ri)=>{
      const y=top+ri*rowH,at=row.done?0:c.at(row.at,.25+ri*.2),sweep=row.sweep??Math.min(4,Math.max(1.2,c.dur-at-.9)),shots=row.shots,total=shots.reduce((a,b)=>a+b.d,0),realTotal=shots.filter(x=>x.k==='real').reduce((a,b)=>a+b.d,0);
      const group=rect(node('div','v-sw-row',world),0,y,1920,rowH-26);
      rect(node('div','v-sw-name',group,row.label),116,0,340,58);rect(node('div','v-sw-sub',group,row.sub||(Math.round(total)+' 秒 · '+shots.length+' 镜')),116,58,340,40);
      const track=rect(node('div','v-sw-track',group),X0,0,TW,rowH-30);let x=0;const blocks=[];
      shots.forEach(shot=>{const w=Math.max(2,shot.d*px-3),b=rect(node('div','v-sw-block',track),x*px,0,w,rowH-30),fill=node('div','v-sw-fill',b);fill.style.background=SHOT_COLORS[shot.k]||SHOT_COLORS.graphic;blocks.push({b,fill,start:x,end:x+shot.d,k:shot.k});
        const lit=at+(x/win)*sweep;if(row.done)gsap.set(fill,{opacity:1});else{c.tl.fromTo(fill,{opacity:0},{opacity:1,duration:.06,ease:'none',immediateRender:true},lit);if(shot.k==='real')c.tl.fromTo(b,{scaleY:1.22},{scaleY:1,duration:.22,ease:'power3.out',immediateRender:false},lit);}
        x+=shot.d;});
      const big=rect(node('div','v-sw-count',group),1548,-6,300,64),pct=rect(node('div','v-sw-pct',group),1548,58,300,40);
      const show=v=>{big.textContent=v.toFixed(1)+' s';pct.textContent='真东西 '+Math.round(v/total*100)+'%';};
      if(row.done){show(realTotal);}else{
        const head=rect(node('div','v-sw-head',track),0,-14,3,rowH-2);const state={t:0};show(0);
        c.tl.fromTo(head,{opacity:0},{opacity:1,duration:.05,immediateRender:true},at);c.tl.to(head,{opacity:0,duration:.15},at+sweep+.25);
        c.tl.to(state,{t:1,duration:sweep,ease:'none',onUpdate:()=>{const pos=state.t*win;head.style.left=(pos*px)+'px';let v=0;for(const b of blocks)if(b.k==='real')v+=Math.max(0,Math.min(pos,b.end)-b.start);show(v);}},at);
        c.tl.fromTo(group,{opacity:0,y:24},{opacity:1,y:0,duration:.3,ease:'power3.out',immediateRender:true},Math.max(0,at-.3));
      }
      if(row.focus!==undefined){const f=blocks[row.focus],s=Y.svg(world);markDecor(s);Y.ellipse(s,c.tl,{x:X0+f.start*px,y:y,w:Math.max(24,(f.end-f.start)*px),h:rowH-30},c.at(row.focusAt,at+sweep+.15),{w:6});}
    });
    if(p.legend!==false){const lg=rect(node('div','v-sw-legend',world),X0,top+rows.length*rowH+8,1400,40);[['real','实拍 · 照片 · 抠图'],['screen','截图 · 录屏'],['graphic','图形 · 文字']].forEach(([k,t])=>{const i=node('span','',lg);const sw=node('b','',i);sw.style.background=SHOT_COLORS[k];node('em','',i,t);});}
    if(p.zoom){const z=p.zoom,r=z.row??0,cx=X0+(z.second??win/2)*px,cy=top+r*rowH+rowH/2;world.style.transformOrigin=cx+'px '+cy+'px';c.tl.to(world,{scale:z.scale??1.6,duration:.3,ease:'power2.inOut'},c.at(z.at,1.5));if(z.back!==undefined)c.tl.to(world,{scale:1,duration:.35,ease:'power2.inOut'},c.at(z.back,3));}
    if(p.stamp)Y.stamp(world,c.tl,p.stamp.text,{x:p.stamp.x??1460,y:p.stamp.y??(top+rows.length*rowH+30)},c.at(p.stamp.at,c.dur*.6),{size:p.stamp.size??64});
    if(p.showSource!==false)tag(c,p.source||'自测逐镜数据 · 不含原片画面');
  }
  function brollCaption(c,p){
    const side=p.side||'left',frame=rect(node('div','v-bc-frame',c.cam),80,54,1760,990),clip=rect(node('div','v-clip v-full-media',frame),0,0,1760,990),m=media(c,p.media,clip);gsap.set(frame,{rotation:p.angle??-.6});
    const kb=p.kb||{};m.dataset.camera='push';c.tl.fromTo(m,{scale:kb.from??1},{scale:kb.to??1.08,duration:c.dur,ease:'none',transformOrigin:kb.origin||'50% 50%',immediateRender:true},0);
    for(const jump of p.cutZoom||[]){const r=jump.rect;c.tl.set(clip,{scale:jump.scale,transformOrigin:r?`${(r.x+r.w/2)/1920*100}% ${(r.y+r.h/2)/1080*100}%`:'50% 50%'},c.at(jump.at,1.6));}
    c.tl.fromTo(frame,{opacity:0,y:30},{opacity:1,y:0,duration:.3,ease:'power3.out',immediateRender:true},0);
    const lines=Array.isArray(p.caption)?p.caption:[p.caption],fs=p.fontSize??(lines.length>1?78:96),w=p.captionWidth??Math.min(1180,Math.max(...lines.map(l=>[...l].length))*fs*1.02+90),h=lines.length*fs*1.22+70,x=side==='left'?150:1920-150-w,y=p.captionY??(1000-h);
    const strip=card(c,x,y,w,h,side==='left'?-2.2:2);tape(strip,w/2-72,-22,side==='left'?-4:5);
    const at=c.at(p.at,.3);c.tl.fromTo(strip,{opacity:0,y:30,rotation:side==='left'?-5:5},{opacity:1,y:0,rotation:side==='left'?-2.2:2,duration:.35,ease:'back.out(1.3)',immediateRender:true},at);
    lines.forEach((line,i)=>{const t=rect(node('div','v-bc-line',strip),45,35+i*fs*1.22,w-90,fs*1.22);style(t,{fontSize:fs+'px'});Y.write(c.tl,t,line,at+.15+i*.35);});
    if(p.mark){const s=Y.svg(c.cam);markDecor(s);const ma=c.at(p.mark.at,at+.6+lines.length*.35);
      if((p.mark.kind||'underline')==='underline')Y.underline(s,c.tl,{x:x+45,y:y+h-26,w:Math.min(w-90,[...lines[lines.length-1]].length*fs)},ma,{w:7});
      else Y.ellipse(s,c.tl,p.mark.target,ma,{w:7});}
    if(p.credit){const cr=node('div','v-bc-credit',c.cam,p.credit);style(cr,{position:'absolute',right:'150px',top:'952px'});}
  }
  function phoneCam(c,p){
    const box=fullMedia(c,p.media),m=box.querySelector('.v-media'),crop=p.crop??1.04;
    const world=box;m.dataset.camera='push';box.dataset.camera='focus';const push2=p.push||{};c.tl.fromTo(m,{scale:crop*(push2.from??1)},{scale:crop*(push2.to??1.06),duration:Math.min(c.dur,push2.duration??c.dur),ease:'none',transformOrigin:'50% 50%',immediateRender:true},0);
    if(p.focus){const r=p.focus,k0=r.scale??1.6,fa=c.at(r.at,1.2);c.tl.to(world,{scale:k0,x:(960-(r.x+r.w/2))*k0,y:(540-(r.y+r.h/2))*k0,duration:.32,ease:'power2.inOut'},fa);
      const s=Y.svg(c.cam);markDecor(s);const k=r.scale??1.6,cx=960,cy=540,bw=r.w*k,bh=r.h*k;Y.ellipse(s,c.tl,{x:cx-bw/2,y:cy-bh/2,w:bw,h:bh},fa+.4,{w:7});}
    const scrim=rect(node('div','v-pc-scrim',c.cam),0,0,1920,1080);markDecor(scrim);
    const badge=rect(node('div','v-pc-badge',c.cam),116,72,330,56);node('i','',badge);node('span','',badge,p.badge||'手机实拍');
    c.tl.fromTo(badge.querySelector('i'),{opacity:1},{opacity:.25,duration:.5,repeat:Math.max(0,Math.floor(c.dur/.5)-1),yoyo:true,ease:'steps(1)'},0);
    if(p.speed){const sp=rect(node('div','v-pc-speed',c.cam,'×'+p.speed+' 快进'),1920-116-260,72,260,56);sp.style.textAlign='right';}
    if(p.label){const l=rect(node('div','v-pc-label',c.cam,p.label),116,1080-84-120,1200,110);c.tl.fromTo(l,{opacity:0,y:20},{opacity:1,y:0,duration:.25,ease:'power3.out',immediateRender:true},c.at(p.labelAt,.5));}
    if(p.stamp)Y.stamp(c.cam,c.tl,p.stamp.text,{x:p.stamp.x??1380,y:p.stamp.y??560},c.at(p.stamp.at,c.dur*.55),{size:p.stamp.size??160});
  }

  /* ============== Skill v2 Cinema Studio Recipes (I-Family) ============== */

  /* 1. split-compare：双 16:9 完整画幅动态聚焦对照（严禁竖裁横屏） */
  function splitCompare(c,p){
    cinemaAtmosphere(c);
    const world=rect(node('div','v-world v-split-stage',c.cam),0,0,1920,1080);
    c.tl.fromTo(world,{scale:1},{scale:1.03,duration:c.dur,ease:'none',transformOrigin:'50% 52%'},0);
    cinemaChip(c,c.cam,p.kicker||'同题盲测对照',.08);
    if(p.showTitle!==false&&p.title){
      const t=node('div','v-cinema-title',c.cam,p.title);
      c.tl.fromTo(t,{opacity:0,y:12},{opacity:1,y:0,duration:.28,ease:'power3.out'},.12);
    }
    if(p.source)node('div','v-cinema-source',c.cam,p.source);

    const W=864,H=486,topY=(p.showTitle!==false&&p.title)?296:266;
    const layout={left:{x:72,y:topY},right:{x:984,y:topY}};
    const frames={},medias={};
    for(const side of ['left','right']){
      const box=rect(node('div','v-split-window',world),layout[side].x,layout[side].y,W,H);
      const clip=rect(node('div','v-clip',box),0,0,W,H);
      const m=media(c,p[side],clip);
      m.style.objectFit='cover';
      m.dataset.camera='push';
      c.tl.fromTo(m,{scale:1.0},{scale:1.06,duration:c.dur,ease:'none',transformOrigin:'50% 50%'},0);
      markDecor(node('div','v-split-sheen',box));
      const tagEl=node('div','v-split-label',box);
      node('b','',tagEl,side==='left'?'A':'B');
      const customLabel=side==='left'?p.leftLabel:p.rightLabel;
      if(customLabel)node('span','',tagEl,customLabel);
      c.tl.fromTo(box,{opacity:0,y:28,scale:.97},{opacity:1,y:0,scale:1,duration:.36,ease:'power3.out'},side==='left'?0:.08);
      frames[side]=box;medias[side]=m;
    }

    for(const focus of p.focusTimeline||[]){
      const at=c.at(focus.at,.6);
      for(const side of ['left','right']){
        const box=frames[side];
        if(focus.side==='both'){
          c.tl.to(box,{scale:1,x:0,y:0,filter:'brightness(1)',zIndex:5,duration:.42,ease:'power3.inOut',onStart:()=>box.classList.remove('is-active')},at);
        }else if(focus.side===side){
          c.tl.to(box,{scale:1.07,x:side==='left'?26:-26,y:-6,filter:'brightness(1.03)',zIndex:10,duration:.42,ease:'power3.inOut',onStart:()=>box.classList.add('is-active')},at);
        }else{
          c.tl.to(box,{scale:.92,x:side==='left'?-18:18,y:8,filter:'brightness(.36)',zIndex:2,duration:.42,ease:'power3.inOut',onStart:()=>box.classList.remove('is-active')},at);
        }
      }
    }

    if(p.countdown){
      const sec=Math.max(1,Math.min(5,Math.round(p.countdown.seconds||3)));
      const startAt=c.at(p.countdown.at,1.2);
      const cd=node('div','v-split-countdown',c.cam);
      gsap.set(cd,{opacity:0});
      const dial=document.createElementNS(NS,'svg');
      dial.setAttribute('viewBox','0 0 260 260');rect(dial,0,0,260,260);markDecor(dial);cd.appendChild(dial);
      shape(dial,'circle',{cx:130,cy:130,r:108,fill:'rgba(8,9,12,.82)',stroke:'rgba(239,232,220,.2)','stroke-width':5});
      const r=108,len=2*Math.PI*r;
      const arc=shape(dial,'circle',{cx:130,cy:130,r,fill:'none',stroke:'#ff4a2b','stroke-width':7,'stroke-linecap':'round',transform:'rotate(-90 130 130)'});
      gsap.set(arc,{strokeDasharray:len,strokeDashoffset:len});
      c.tl.set(cd,{opacity:1},startAt);
      for(let i=0;i<sec;i++){
        const t=startAt+i*.95;
        const num=node('div','v-split-cd-num',cd,String(sec-i));
        c.tl.fromTo(num,{opacity:0,scale:1.3},{opacity:1,scale:1,duration:.18,ease:'power3.out'},t);
        c.tl.to(num,{opacity:0,scale:.88,duration:.12},t+.82);
        c.tl.fromTo(arc,{strokeDashoffset:len},{strokeDashoffset:0,duration:.9,ease:'none',immediateRender:false},t);
      }
      c.tl.to(cd,{opacity:0,duration:.16},startAt+sec*.95);
    }

    for(const st of p.stamps||[]){
      const side=st.side==='right'?'right':'left';
      const target=frames[side];
      cinemaStamp(c,target,st.text,W/2,H/2+24,c.at(st.at,c.dur*.72),{angle:side==='left'?-6:5,shakeTarget:target,fontSize:58});
    }
    redactionLayer(c,p.redactions,world);
  }

  /* 2. blueprint-diagram：精密 SVG 工程蓝图动态图解（flow / hub / layers / versus） */
  function blueprint(c,p){
    cinemaAtmosphere(c,'blueprint');
    const world=rect(node('div','v-world',c.cam),0,0,1920,1080);
    c.tl.fromTo(world,{scale:1},{scale:1.045,duration:c.dur,ease:'none',transformOrigin:'50% 52%'},0);

    const bgSvg=svg(world);
    let gridPath='';
    for(let x=120;x<1920;x+=120)gridPath+=`M ${x} 0 V 1080 `;
    for(let y=120;y<1080;y+=120)gridPath+=`M 0 ${y} H 1920 `;
    shape(bgSvg,'path',{d:gridPath,stroke:'rgba(148,175,225,.09)','stroke-width':1});
    let cross='';
    for(let x=240;x<=1680;x+=480)for(let y=240;y<=840;y+=300)cross+=`M ${x-8} ${y} H ${x+8} M ${x} ${y-8} V ${y+8} `;
    shape(bgSvg,'path',{d:cross,stroke:'rgba(148,175,225,.28)','stroke-width':1.5});

    cinemaChip(c,c.cam,p.kicker||'系统蓝图',.08);
    const hasTitle=p.showTitle!==false&&p.title;
    if(hasTitle){
      const t=node('div','v-cinema-title',c.cam,p.title);
      c.tl.fromTo(t,{opacity:0,y:12},{opacity:1,y:0,duration:.28,ease:'power3.out'},.12);
    }
    if(p.source)node('div','v-cinema-source',c.cam,p.source);

    const rawNodes=(p.nodes||[]).map((item,i)=>typeof item==='string'?{id:item,title:item,at:.25+i*.22}:{...item,id:item.id||item.title});
    const topology=p.topology||'flow',n=rawNodes.length;
    const positions={},centerY=hasTitle?585:545;

    if(topology==='hub'){
      const core=rawNodes[0];
      positions[core.id]={x:960-215,y:centerY-92,w:430,h:184,accent:'accent-red'};
      const rest=rawNodes.slice(1),m=Math.max(1,rest.length);
      rest.forEach((item,i)=>{
        const ang=-Math.PI/2+i*2*Math.PI/m;
        const cx=960+Math.cos(ang)*600,cy=centerY+Math.sin(ang)*305;
        positions[item.id]={x:Math.round(cx-190),y:Math.round(cy-82),w:380,h:164,accent:i===rest.length-1?'accent-green':''};
      });
    }else if(topology==='layers'){
      const w=1220,h=Math.min(152,Math.floor(640/Math.max(1,n))-18),totalH=n*h+(n-1)*22,startY=Math.round(centerY-totalH/2);
      rawNodes.forEach((item,i)=>{positions[item.id]={x:350,y:startY+i*(h+22),w,h,accent:i===0?'accent-red':i===n-1?'accent-green':''};});
    }else if(topology==='versus'){
      const rows=Math.ceil(n/2),w=640,h=178,totalH=rows*h+(rows-1)*34,startY=Math.round(centerY-totalH/2);
      rawNodes.forEach((item,i)=>{
        const col=i%2,row=Math.floor(i/2);
        positions[item.id]={x:col===0?220:1060,y:startY+row*(h+34),w,h,accent:col===0?'accent-red':'accent-green'};
      });
    }else{
      const cols=n<=4?n:Math.ceil(n/2),rows=Math.ceil(n/cols);
      const w=cols>=4?376:430,gapX=cols>=4?48:74,h=196,gapY=54;
      const totalH=rows*h+(rows-1)*gapY,startY=Math.round(centerY-totalH/2);
      rawNodes.forEach((item,i)=>{
        const r=Math.floor(i/cols),col=i%cols,colsInRow=r===rows-1?n-r*cols:cols;
        const rowW=colsInRow*w+(colsInRow-1)*gapX,startX=Math.round((1920-rowW)/2);
        positions[item.id]={x:startX+col*(w+gapX),y:startY+r*(h+gapY),w,h,accent:i===n-1?'accent-green':''};
      });
    }

    const edgeSvg=svg(world);
    const edgeList=p.edges?.length?p.edges:(topology==='flow'?rawNodes.slice(0,-1).map((item,i)=>({from:item.id,to:rawNodes[i+1].id,at:(item.at??.25)+.18})):[]);
    for(const edge of edgeList){
      const a=positions[edge.from],b=positions[edge.to];if(!a||!b)continue;
      const sameRow=Math.abs((a.y+a.h/2)-(b.y+b.h/2))<60;
      const x1=sameRow?(a.x<b.x?a.x+a.w:a.x):a.x+a.w/2;
      const y1=sameRow?a.y+a.h/2:(a.y<b.y?a.y+a.h:a.y);
      const x2=sameRow?(a.x<b.x?b.x:b.x+b.w):b.x+b.w/2;
      const y2=sameRow?b.y+b.h/2:(a.y<b.y?b.y:b.y+b.h);
      const d=sameRow?`M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`:`M ${x1} ${y1} C ${x1} ${(y1+y2)/2}, ${x2} ${(y1+y2)/2}, ${x2} ${y2}`;
      const at=c.at(edge.at,.35);
      const glow=shape(edgeSvg,'path',{d,fill:'none',stroke:'rgba(94,162,255,.28)','stroke-width':10,'stroke-linecap':'round'});
      const line=shape(edgeSvg,'path',{d,fill:'none',stroke:'#5ea2ff','stroke-width':3.5,'stroke-linecap':'round'});
      drawn(c,glow,at,.55);drawn(c,line,at,.55);
      shape(edgeSvg,'circle',{cx:x1,cy:y1,r:5,fill:'#5ea2ff'});
      const endDot=shape(edgeSvg,'circle',{cx:x2,cy:y2,r:6,fill:'#7ee29a',opacity:0});
      c.tl.to(endDot,{opacity:1,duration:.15},at+.48);
      const pulse=shape(edgeSvg,'circle',{cx:x1,cy:y1,r:6,fill:'#efe8dc',opacity:0});
      const len=line.getTotalLength(),prog={u:0};
      c.tl.set(pulse,{opacity:1},at+.05);
      c.tl.to(prog,{u:1,duration:.75,ease:'power2.inOut',onUpdate:()=>{const pt=line.getPointAtLength(prog.u*len);pulse.setAttribute('cx',pt.x);pulse.setAttribute('cy',pt.y);}},at+.05);
      c.tl.to(pulse,{opacity:0,duration:.15},at+.8);
      if(edge.label){
        const lbl=node('div','v-blueprint-edge-label',world,edge.label);
        style(lbl,{left:((x1+x2)/2)+'px',top:((y1+y2)/2-18)+'px'});
        c.tl.fromTo(lbl,{opacity:0,scale:.85},{opacity:1,scale:1,duration:.22,ease:'power2.out'},at+.25);
      }
    }

    rawNodes.forEach((item,i)=>{
      const pos=positions[item.id];
      const accent=item.accent||pos.accent||'';
      const box=rect(node('div','v-blueprint-node'+(accent?' '+accent:''),world),pos.x,pos.y,pos.w,pos.h);
      const head=node('div','v-blueprint-head',box);
      node('span','v-blueprint-index',head,item.tag||('STEP '+String(i+1).padStart(2,'0')));
      if(item.status)node('span','v-blueprint-status',head,'● '+item.status);
      node('div','v-blueprint-title',box,item.title);
      if(item.subtitle||item.sub)node('div','v-blueprint-sub',box,item.subtitle||item.sub);
      const at=c.at(item.at,.18+i*.22);
      c.tl.fromTo(box,{opacity:0,y:24,scale:.94},{opacity:1,y:0,scale:1,duration:.34,ease:'power3.out'},at);
    });
  }

  /* 3. cinematic-broll：满屏 1080p 实拍 / ltx2 动态视频 / image2 概念摄影 */
  function cinematicBroll(c,p){
    cinemaAtmosphere(c);
    const frame=fullMedia(c,p.media),m=frame.querySelector('.v-media');
    m.dataset.camera='push';
    c.tl.fromTo(m,{scale:p.from??1.02},{scale:p.to??1.11,duration:c.dur,ease:'none',transformOrigin:p.origin||'50% 50%'},0);
    cinemaChip(c,c.cam,p.tag||p.badge||'纪实画面',.1);
    if(p.caption){
      const cap=rect(node('div','v-pc-label',c.cam,p.caption),72,900,1480,104);
      c.tl.fromTo(cap,{opacity:0,y:20},{opacity:1,y:0,duration:.28,ease:'power3.out'},c.at(p.captionAt,.35));
    }
    if(p.stamp)cinemaStamp(c,c.cam,p.stamp.text||p.stamp,p.stamp.x??1480,p.stamp.y??820,c.at(p.stamp.at,c.dur*.62),{shakeTarget:frame});
    redactionLayer(c,p.redactions,frame);
  }

  /* 4. terminal-over-footage：满屏动态实拍压暗底 + 毛玻璃等宽面板 + 朱红差值括号 */
  function terminalOverFootage(c,p){
    cinemaAtmosphere(c);
    const frame=fullMedia(c,p.media),m=frame.querySelector('.v-media');
    m.dataset.camera='push';
    c.tl.fromTo(m,{scale:1.08},{scale:1.0,duration:c.dur,ease:'none',transformOrigin:'45% 65%'},0);
    markDecor(rect(node('div','v-footage-shade',c.cam),0,0,1920,1080));
    cinemaChip(c,c.cam,p.kicker||'运行记录核对',.08);

    const lines=p.lines||[];
    const winW=1420,rowH=72,winH=96+Math.max(2,lines.length)*rowH+32,topY=Math.round((1080-winH)/2)+24;
    const box=rect(node('div','v-terminal-over',c.cam),250,topY,winW,winH);
    const bar=node('div','v-terminal-over-bar',box);
    for(let i=0;i<3;i++)node('i','',bar);
    node('span','',bar,p.windowTitle||p.title||'execution-ledger · zsh');
    const body=node('div','v-terminal-over-body',box);
    c.tl.fromTo(box,{opacity:0,y:34},{opacity:1,y:0,duration:.36,ease:'power3.out'},.12);
    c.tl.to(box,{scale:1.025,duration:Math.max(.5,c.dur-.4),ease:'none'},.35);

    lines.forEach((item,i)=>{
      const raw=typeof item==='string'?{text:item}:item;
      const row=node('div','v-terminal-over-row',body);
      node('span','prompt',row,raw.prefix||(raw.cmd!==false?'$':'›'));
      node('span','',row,raw.text);
      if(raw.note)node('span','accent',row,raw.note);
      const at=c.at(raw.at,.28+i*.34);
      c.tl.fromTo(row,{opacity:0,clipPath:'inset(0 100% 0 0)'},{opacity:1,clipPath:'inset(0 0% 0 0)',duration:.42,ease:'steps(20)'},at);
    });

    if(p.gapLabel&&lines.length>=2){
      const braceAt=c.at(p.gapAt,.45+lines.length*.3);
      const brace=node('div','v-terminal-brace',box);
      style(brace,{top:'96px',height:Math.max(88,(lines.length-1)*rowH)+'px'});
      const lbl=node('div','v-terminal-brace-label',box,p.gapLabel);
      style(lbl,{top:Math.round(96+(lines.length-1)*rowH/2-18)+'px'});
      c.tl.fromTo([brace,lbl],{opacity:0,scaleY:.4},{opacity:1,scaleY:1,duration:.28,ease:'power3.out'},braceAt);
    }
    redactionLayer(c,p.redactions,frame);
  }

  /* 5. suspect-focus：满屏证据画面 + 四直角朱红取景框缩进锁定 + 划线排除 */
  function suspectFocus(c,p){
    cinemaAtmosphere(c);
    const frame=fullMedia(c,p.media),m=frame.querySelector('.v-media');
    m.dataset.camera='push';
    c.tl.fromTo(m,{scale:1.0},{scale:1.1,duration:c.dur,ease:'none',transformOrigin:'50% 50%'},0);

    const bx=p.x??260,by=p.y??190,bw=p.w??1400,bh=p.h??700;
    const box=rect(node('div','v-suspect-box',c.cam),bx,by,bw,bh);
    markDecor(box);
    ['tl','tr','bl','br'].forEach(pos=>node('i','v-suspect-corner '+pos,box));
    const focusAt=c.at(p.at,.25);
    c.tl.fromTo(box,{opacity:0,scale:1.15},{opacity:1,scale:1,duration:.3,ease:'power3.out'},focusAt);
    const strikeAt=p.strike===false?null:(p.strikeAt??Math.min(c.dur-.35,focusAt+.85));
    cinemaChip(c,c.cam,p.label||'嫌疑项核查',Math.max(.08,focusAt-.1),{dot:true,strikeAt});
    redactionLayer(c,p.redactions,frame);
  }

  /* 6. footage-bigword：满屏证据底片压暗 + 思源宋巨字砸入微缩 */
  function footageBigword(c,p){
    cinemaAtmosphere(c);
    const frame=fullMedia(c,p.media),m=frame.querySelector('.v-media');
    m.dataset.camera='push';
    c.tl.fromTo(m,{scale:1.07},{scale:1.0,duration:c.dur,ease:'none',transformOrigin:'50% 50%'},0);
    const shade=markDecor(rect(node('div','v-footage-shade',c.cam),0,0,1920,1080));
    c.tl.fromTo(shade,{opacity:.35},{opacity:.85,duration:.35},0);

    const len=[...(p.text||'')].length;
    const fs=p.fontSize??(len===1?460:len===2?340:len===3?260:210);
    const topY=Math.round((1080-fs)/2)-(p.sub?36:10);
    const word=node('div','v-footage-bigword',c.cam,p.text);
    style(word,{top:topY+'px',fontSize:fs+'px',lineHeight:'1'});
    const at=c.at(p.at,.22);
    c.tl.fromTo(word,{opacity:0,scale:1.2},{opacity:.98,scale:1,duration:.36,ease:'power3.out'},at);
    c.tl.to(word,{scale:.96,duration:Math.max(.4,c.dur-at-.36),ease:'none'},at+.36);

    if(p.sub){
      const sub=node('div','v-footage-bigword-sub',c.cam,p.sub);
      style(sub,{top:(topY+fs+42)+'px'});
      c.tl.fromTo(sub,{opacity:0,letterSpacing:'.42em'},{opacity:.92,letterSpacing:'.18em',duration:.38,ease:'power2.out'},c.at(p.subAt,at+.45));
    }
    redactionLayer(c,p.redactions,frame);
  }

  /* 7. desk-dispatch：径向顶光桌面 + 真实窗口物件 + 锯齿工单飞跃 + REC 状态 + 盖章 */
  function deskDispatch(c,p){
    cinemaAtmosphere(c);
    const world=rect(node('div','v-world',c.cam),0,0,1920,1080);
    const items=p.items||[],n=items.length;
    const W=544,barH=38,bodyH=306,H=barH+bodyH; // body 544x306 = exact 16:9!
    const preset=n===2?[{x:290,y:350},{x:1086,y:350}]:
      n===3?[{x:120,y:390},{x:688,y:250},{x:1256,y:410}]:
      [{x:180,y:190},{x:1196,y:190},{x:180,y:585},{x:1196,y:585}];

    const wins=[];
    items.forEach((item,i)=>{
      const pos={x:item.x??preset[i%preset.length].x,y:item.y??preset[i%preset.length].y};
      const win=rect(node('div','v-dispatch-win',world),pos.x,pos.y,W,H);
      gsap.set(win,{rotation:item.angle??(i%2?1.2:-1.2)});
      const bar=node('div','v-dispatch-win-bar',win);
      for(let k=0;k<3;k++)node('i','',bar);
      node('span','',bar,item.windowTitle||item.role||item.label);
      const body=rect(node('div','v-dispatch-win-body v-clip',win),0,barH,W,bodyH);
      if(item.media){
        const m=media(c,item.media,body);
        m.style.objectFit='cover';
      }else{
        const fallback=rect(node('div','',body,item.previewText||item.label),32,96,W-64,120);
        style(fallback,{font:'700 34px/1.3 var(--f-mono)',color:'rgba(239,232,220,.78)',textAlign:'center'});
      }
      node('div','v-dispatch-tag',win,item.label);
      const live=node('div','v-dispatch-live'+(item.statusKind==='rec'?' rec':''),win);
      node('i','',live);node('span','',live,item.status||(item.statusKind==='rec'?'REC':'运行中'));
      gsap.set(live,{opacity:0});
      const at=c.at(item.at,.15+i*.32);
      c.tl.fromTo(win,{opacity:0,y:36,scale:.95},{opacity:1,y:0,scale:1,duration:.34,ease:'power3.out'},Math.max(0,at-.12));
      c.tl.to(live,{opacity:1,duration:.2},at+.22);
      wins.push({win,pos,cx:pos.x+W/2,cy:pos.y+H/2,at,item});
    });

    const camTo=(cx,cy,s)=>({x:960-s*cx,y:540-s*cy,scale:s});
    gsap.set(world,camTo(960,540,.96));
    if(wins.length>=2&&c.dur>=2.6){
      const stepDur=Math.min(.65,(c.dur-.9)/(wins.length+1));
      wins.slice(0,Math.min(3,wins.length)).forEach((w,i)=>{
        const t=.28+i*(stepDur+.25);
        c.tl.to(world,{...camTo(w.cx,w.cy,1.22),duration:stepDur,ease:'power3.inOut'},t);
        if(i+1<wins.length){
          const nxt=wins[i+1];
          const tk=node('div','v-dispatch-ticket',world);
          node('small','',tk,'TASK #'+(i+1));
          node('b','',tk,p.ticketTitle||(nxt.item.task||('派发 → '+nxt.item.label)));
          node('span','',tk,p.ticketSub||'按契约执行并回传物证');
          gsap.set(tk,{left:w.cx-120,top:w.pos.y+H-40,rotation:-3,opacity:0});
          c.tl.fromTo(tk,{opacity:0,scale:.76,y:24},{opacity:1,scale:1,y:0,duration:.24,ease:'back.out(1.5)'},t+stepDur*.5);
          c.tl.to(tk,{left:nxt.cx-180,top:nxt.pos.y+H-64,rotation:2,duration:stepDur,ease:'power3.inOut'},t+stepDur*.8);
          c.tl.to(tk,{opacity:0,scale:.9,y:24,duration:.22},t+stepDur*1.75);
        }
      });
      c.tl.to(world,{...camTo(960,550,.98),duration:.55,ease:'power3.out'},Math.max(.8,c.dur-1.15));
    }else{
      c.tl.to(world,{...camTo(960,535,1.04),duration:c.dur,ease:'none'},0);
    }

    cinemaChip(c,c.cam,p.kicker||'多代理流水线派单',.08);
    if(p.stamp!==false){
      cinemaStamp(c,world,p.stamp||'交付通过',1580,880,c.at(p.stampAt,Math.max(.6,c.dur-.75)),{angle:-7,shakeTarget:world,fontSize:54});
    }
    redactionLayer(c,p.redactions,world);
  }

  /* 8. ruler-measure：精密横向测量尺与对比轨 */
  function rulerMeasure(c,p){
    cinemaAtmosphere(c);
    const world=rect(node('div','v-world',c.cam),0,0,1920,1080);
    c.tl.fromTo(world,{scale:1},{scale:1.04,duration:c.dur,ease:'none',transformOrigin:'55% 50%'},0);
    cinemaChip(c,c.cam,p.kicker||'实测指标尺',.08);
    if(p.showTitle!==false&&p.title){
      const t=node('div','v-cinema-title',c.cam,p.title);
      c.tl.fromTo(t,{opacity:0,y:12},{opacity:1,y:0,duration:.28,ease:'power3.out'},.12);
    }
    if(p.source)node('div','v-cinema-source',c.cam,p.source);

    const rows=p.rows||[],maxVal=p.max||Math.max(100,...rows.map(r=>r.value));
    const wrap=node('div','v-ruler-wrap',world);
    const scale=node('div','v-ruler-scale',wrap);markDecor(scale);
    for(let i=0;i<=10;i++){
      const x=i*104,tick=node('i','',scale);
      style(tick,{left:x+'px',height:(i%2===0?22:12)+'px'});
      if(i%2===0){const sp=node('span','',scale,Math.round(maxVal*i/10)+(rows[0]?.unit||'%'));style(sp,{left:x+'px'});}
    }

    const sweepDur=Math.min(2.4,Math.max(.8,c.dur*.58));
    const ph=node('div','v-ruler-playhead',wrap);
    style(ph,{height:(64+rows.length*152)+'px',opacity:0});
    c.tl.set(ph,{opacity:1},.25);
    c.tl.fromTo(ph,{x:0},{x:1040,duration:sweepDur,ease:'power2.out'},.25);
    c.tl.to(ph,{opacity:0,duration:.2},.25+sweepDur+.15);

    rows.forEach((row,i)=>{
      const rowEl=node('div','v-ruler-row',wrap);
      const lbl=node('div','v-ruler-label',rowEl,row.label);
      if(row.sub)node('small','',lbl,row.sub);
      const track=node('div','v-ruler-track',rowEl);
      const isPrimary=row.highlight!==undefined?row.highlight:(i===0||row.value===Math.max(...rows.map(r=>r.value)));
      const fill=node('div','v-ruler-fill'+(isPrimary?'':' muted'),track);
      const val=node('div','v-ruler-val',rowEl,'0');
      const at=c.at(row.at,.25+i*.16);
      const targetW=Math.round(clamp(row.value/maxVal,0,1)*1040);
      c.tl.fromTo(rowEl,{opacity:0,y:20},{opacity:1,y:0,duration:.28,ease:'power3.out'},Math.max(0,at-.12));
      c.tl.to(fill,{width:targetW+'px',duration:sweepDur,ease:'power2.out'},at);
      counter(c,val,row.value,at,0,row.unit||'%',sweepDur);
    });
  }

  const RECIPES={'news-card':news,'social-post':social,'chat-bubble':chat,'device-stage':device,'laptop-3d':laptop,'filmed-screen':filmed,'cursor-zoom':cursor,'terminal-run':terminal,'code-diff':diff,'bar-compare':bars,'progress-ring':ring,'rank-race':race,'concept-hub':hub,'photo-path':photos,'hand-mark':hand,'word-swap':swap,'headline-slam':slam,'action-montage':montage,'quote-fragments':quote,'visual-contrast':contrast,'cutout-stack':stack,'paper-break':paper,'brand-hero':brand,'sticker-text':sticker,'reaction-cutout':reaction,'shot-wall':shotWall,'broll-caption':brollCaption,'phone-cam':phoneCam,'split-compare':splitCompare,'blueprint-diagram':blueprint,'cinematic-broll':cinematicBroll,'terminal-over-footage':terminalOverFootage,'suspect-focus':suspectFocus,'footage-bigword':footageBigword,'desk-dispatch':deskDispatch,'ruler-measure':rulerMeasure};
  function layers(c){if(c.spec.layers?.length)c.root.classList.add('yv');for(const p of c.spec.layers||[]){
    if(p.kind==='grain-overlay'){const e=node('div','v-grain',c.cam);e.style.opacity=String(p.strength??.06);markDecor(e);}
    if(p.kind==='light-sweep-pass'){const e=node('div','v-sweep',c.cam),band=node('div','v-sweep-band',e);markDecor(e);c.tl.fromTo(band,{x:0},{x:2300,duration:.6,ease:'power3.out'},c.at(p.at,.3));}
    if(p.kind==='notification-stack'){(p.items||[{text:'已完成'}]).slice(0,3).forEach((item,i)=>{const e=node('div','v-card v-notification',c.cam,item.text);e.style.bottom=(110+i*100)+'px';c.tl.fromTo(e,{x:55,opacity:0},{x:0,opacity:1,duration:.5,ease:'power3.out'},c.at(item.at??p.at,.5+i*.2));});}
  }}
  function transitions(c){
    const type=c.spec.enter,w=c.wrap,tl=c.tl,d=.5;
    if(type==='directional-wipe')tl.fromTo(w,{clipPath:'inset(0 100% 0 0)',x:60,scale:1.04},{clipPath:'inset(0 0% 0 0)',x:0,scale:1,duration:d,ease:'power3.out'},0);
    if(type==='cinematic-zoom')tl.fromTo(w,{scale:1.18,opacity:0},{scale:1,opacity:1,duration:d,ease:'power3.out'},0);
    if(type==='grid-pixelate-wipe'||type==='halftone-dissolve'){
      const defs=shape(svg(c.root),'defs',{}),mask=shape(defs,'clipPath',{id:c.sid+'-reveal',clipPathUnits:'userSpaceOnUse'});markDecor(defs.parentNode);
      for(let y=0;y<6;y++)for(let x=0;x<8;x++){
        const e=type==='grid-pixelate-wipe'?shape(mask,'rect',{x:x*240,y:y*180,width:240,height:180}):shape(mask,'circle',{cx:x*240+120,cy:y*180+90,r:151});
        const attr=type==='grid-pixelate-wipe'?{width:0,height:0}:{r:0},end=type==='grid-pixelate-wipe'?{width:240,height:180}:{r:151};tl.fromTo(e,{attr},{attr:end,duration:.4,ease:'power3.out'},((x+y)%5)*.025);
      }
      tl.set(w,{clipPath:`url(#${c.sid}-reveal)`},0);tl.set(w,{clipPath:'none'},.5);
    }
    if(type==='flash-through-white'){
      const flash=rect(node('div','',c.root),0,0,1920,1080);style(flash,{background:'var(--st-light)',zIndex:100});markDecor(flash);tl.fromTo(flash,{opacity:1},{opacity:0,duration:d,ease:'power2.in'},0);
    }
    if(type==='chromatic-aberration-wipe'){
      tl.fromTo(w,{clipPath:'inset(0 100% 0 0)',x:6},{clipPath:'inset(0 0% 0 0)',x:0,duration:d,ease:'power3.out'},0);
      ['var(--stamp)','var(--blue)'].forEach((color,i)=>{const edge=rect(node('div','',c.root),i*6,0,8,1080);style(edge,{background:color,zIndex:100});markDecor(edge);tl.to(edge,{x:1920,duration:.45,ease:'power3.out'},0);tl.to(edge,{opacity:0,duration:.1},.4);});
    }
  }
  function render(name,c){
    const isCinema=CINEMA_RECIPES.has(name);
    c.root.classList.add('yv');
    if(isCinema)c.root.classList.add('st-charcoal','is-cinema');
    Y.stage(c);
    RECIPES[name](c,c.spec.props||{});
    Y.hud(c);
    Y.finish(c);
  }
  window.YV={render,transitions,layers,overlays,push,recipes:Object.keys(RECIPES)};
})();
