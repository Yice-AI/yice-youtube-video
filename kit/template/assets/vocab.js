/* Adapted registry motion patterns. Origins/license: ../../docs/vocabulary-origins.md.
   All animation is on the parent GSAP timeline; no wall clock / CSS animation. */
(function(){
  'use strict';
  const Y=window.YF, NS='http://www.w3.org/2000/svg';
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
  function news(c,p){
    header(c,p.headline||'原文作证',p.source+' · 采集 '+p.date);
    const w=p.zoom?1280:1650,h=w*1080/1920,box=card(c,135,215,w,h,-.65);
    tape(box,22,-18,-4);tape(box,w-160,-18,4);
    const clip=rect(node('div','v-clip',box),14,14,w-28,h-28),world=node('div','v-world',clip),scale=(w-28)/1920;
    const shot=media(c,p.shot,world);gsap.set(world,{scale});settle(c,box);
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
  }
  function laptop(c,p){
    header(c,p.title||'放到桌上，开始用');
    const rig=rect(node('div','',c.cam),320,170,1280,770);style(rig,{perspective:'1800px'});
    const shell=rect(node('div','v-browser',rig),0,0,1280,690);gsap.set(shell,{rotationY:p.angle??-7,rotationX:5,transformPerspective:1800});
    const screen=rect(node('div','v-clip',shell),10,8,1260,660);media(c,p.media,screen);markDecor(node('div','v-glare',shell));
    const base=rect(node('div','',rig),-70,707,1420,62);style(base,{background:'var(--st-dark)',clipPath:'polygon(5% 0,95% 0,100% 70%,94% 100%,6% 100%,0 70%)',boxShadow:'18px 28px 32px var(--rule)'});markDecor(base);
    const hinge=rect(node('div','',rig),440,714,400,8);hinge.style.background='var(--sub)';markDecor(hinge);
    settle(c,rig);c.tl.to(rig,{scale:1+(p.dolly??.08),duration:Math.max(.3,c.dur-.5),ease:'sine.inOut'},.5);
  }
  function filmed(c,p){
    header(c,p.title||'回看操作过程');const box=rect(node('div','v-browser',c.cam),170,190,1560,760),clip=rect(node('div','v-clip',box),0,0,1560,760);media(c,p.media,clip);
    const scan=rect(node('div','',box),0,0,1560,760);style(scan,{background:'repeating-linear-gradient(0deg,transparent 0 3px,var(--paper-ink) 3px 4px)',opacity:String((p.moire??.3)*.11),pointerEvents:'none'});markDecor(scan);markDecor(node('div','v-glare',box));
    clock(c,t=>{const a=p.handheld??.3;gsap.set(box,{rotationY:1.4+Math.sin(t*1.2)*a,rotationX:-.7+Math.cos(t*.9)*a,x:Math.sin(t*2.1)*a*3,y:Math.cos(t*1.7)*a*2,transformPerspective:1800});});
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
      for(const item of values){const {name,av,bv,value}=item,ai=ar.indexOf(name),bi=br.indexOf(name),pos=(ai<0?count:ai)+((bi<0?count:bi)-(ai<0?count:ai))*k,row=rows[name];row.row.style.top=(top+pos*94)+'px';row.row.style.opacity=av&&bv?'1':av?String(1-k):bv?String(k):'0';const labels=ai===bi&&ai>=0?1:raw<.12?(av?1-raw/.12:0):raw>.88?(bv?(raw-.88)/.12:0):0;row.label.style.opacity=String(labels);row.value.style.opacity=String(labels);row.bar.style.width=(950*value/max*growth)+'px';row.bar.style.background=(k<.5?ar:br)[0]===name?'var(--hl)':'var(--paper-ink)';const display=(raw>=.88?bv:av)||bv||av;row.value.textContent=(display?.value||0).toLocaleString('zh-CN',{maximumFractionDigits:1})+(display?.unit||'');}
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
      p.kind==='underline'?`M ${x} ${y+h} Q ${x+w*.3} ${y+h-5},${x+w*.6} ${y+h+2} T ${x+w} ${y+h}`:
      p.kind==='box'?`M ${x+3} ${y+2} L ${x+w} ${y} L ${x+w+2} ${y+h} L ${x} ${y+h+3} Z`:
      `M ${Math.max(130,x-180)} ${y-90} Q ${x-45} ${y-110},${x+w/2} ${y+h/2} M ${x+w/2-36} ${y+h/2-8} L ${x+w/2} ${y+h/2} L ${x+w/2-8} ${y+h/2-36}`;
    const path=shape(svg(c.cam),'path',{d,fill:'none',stroke:color,'stroke-width':5,'stroke-linecap':'round','stroke-linejoin':'round'});drawn(c,path,.35,.5);
    clock(c,t=>gsap.set(path,{x:Math.sin(t*12)*.2,y:Math.cos(t*9)*.2}));
    if(p.label){const label=rect(node('div','',c.cam,p.label),clamp(x,116,1450),clamp(y+h+26,140,930),400,70);style(label,{font:'30px var(--f-sans)',color});gsap.set(label,{rotation:-2});c.tl.fromTo(label,{opacity:0},{opacity:1,duration:.3},.7);}
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
  const RECIPES={'news-card':news,'social-post':social,'chat-bubble':chat,'device-stage':device,'laptop-3d':laptop,'filmed-screen':filmed,'cursor-zoom':cursor,'terminal-run':terminal,'code-diff':diff,'bar-compare':bars,'progress-ring':ring,'rank-race':race,'concept-hub':hub,'photo-path':photos,'hand-mark':hand,'word-swap':swap,'headline-slam':slam};
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
  function render(name,c){c.root.classList.add('yv');Y.stage(c);RECIPES[name](c,c.spec.props||{});Y.hud(c);Y.finish(c);}
  window.YV={render,transitions,layers,recipes:Object.keys(RECIPES)};
})();
