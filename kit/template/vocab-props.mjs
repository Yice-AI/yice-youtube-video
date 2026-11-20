// 首批视觉词汇的公开 props 接口；媒体统一进入既有 build/video 管线。
export const RECORDING_CONTAINERS = ['device-stage','laptop-3d','filmed-screen','cursor-zoom'];
export const VOCAB_TRANSITIONS = ['directional-wipe','cinematic-zoom','grid-pixelate-wipe','halftone-dissolve','flash-through-white','chromatic-aberration-wipe'];
export const VOCAB_LAYERS = ['grain-overlay','light-sweep-pass','notification-stack'];
export const VOCAB_RECIPES = {
  'news-card':{family:'A',origin:'news-card-prototype',slots:['shot']},
  'social-post':{family:'A',origin:'reddit-post',slots:['avatar','image']},
  'chat-bubble':{family:'A',origin:'chat-message',slots:[]},
  'device-stage':{family:'B',origin:'browser-device-stage',slots:['media','swap']},
  'laptop-3d':{family:'B',origin:'app-showcase',slots:['media']},
  'filmed-screen':{family:'B',origin:'filmed-screen',slots:['media']},
  'cursor-zoom':{family:'B',origin:'cursor-zoom-follow',slots:['media']},
  'terminal-run':{family:'C',origin:'code-terminal-run',slots:[]},
  'code-diff':{family:'C',origin:'code-diff',slots:[]},
  'bar-compare':{family:'D',origin:'animated-bar-chart / chart-story',slots:[]},
  'progress-ring':{family:'D',origin:'conic-progress-ring',slots:[]},
  'rank-race':{family:'D',origin:'bar-chart-race',slots:[]},
  'concept-hub':{family:'E',origin:'constellation-hub',slots:[]},
  'photo-path':{family:'E',origin:'carousel-path-2',slots:['images']},
  'hand-mark':{family:'F',origin:'hw-arrow / hw-callout-circle / hw-underline / hw-box-label',slots:['media']},
  'word-swap':{family:'G',origin:'kinetic-type-swap',slots:[]},
  'headline-slam':{family:'G',origin:'headline-slam',slots:[]},
  'action-montage':{family:'H',origin:'T02',slots:['clips']},
  'quote-fragments':{family:'H',origin:'T04',slots:['image']},
  'visual-contrast':{family:'H',origin:'T05',slots:['left','right']},
  'cutout-stack':{family:'H',origin:'T08',slots:['items']},
  'paper-break':{family:'H',origin:'T11',slots:['items']},
  'brand-hero':{family:'H',origin:'official-brand',slots:['logo','background']},
  'sticker-text':{family:'H',origin:'seq112',slots:['background']},
  'reaction-cutout':{family:'H',origin:'seq113',slots:['person','background']},
  'shot-wall':{family:'D',origin:'ep03-shot-wall',slots:[]},
  'broll-caption':{family:'H',origin:'ep03-broll-caption',slots:['media']},
  'phone-cam':{family:'H',origin:'ep03-phone-cam',slots:['media']},
  'split-compare':{family:'I',origin:'gold60-split-compare',slots:['left','right']},
  'blueprint-diagram':{family:'I',origin:'gold60-blueprint-diagram',slots:[]},
  'cinematic-broll':{family:'I',origin:'gold60-cinematic-broll',slots:['media']},
  'terminal-over-footage':{family:'I',origin:'gold60-terminal-over-footage',slots:['media']},
  'suspect-focus':{family:'I',origin:'gold60-suspect-focus',slots:['media']},
  'footage-bigword':{family:'I',origin:'gold60-footage-bigword',slots:['media']},
  'desk-dispatch':{family:'I',origin:'gold60-desk-dispatch',slots:[]},
  'ruler-measure':{family:'I',origin:'gold60-ruler-measure',slots:[]},
};
const STAGES = ['paper-cool','paper-warm','charcoal'];
const number=(v,name,min=-Infinity,max=Infinity)=>{
  if(!Number.isFinite(v)||v<min||v>max)throw new Error(`${name} 必须为 ${min}–${max} 的有限数值`);
};
const text=(v,name)=>{if(typeof v!=='string'||!v.trim())throw new Error(`${name} 不能为空`);};
const list=(v,name,min=1,max=Infinity)=>{if(!Array.isArray(v)||v.length<min||v.length>max)throw new Error(`${name} 需要 ${min}–${max} 项`);};
function box(v,name){if(!v)throw new Error(`${name} 缺少框`);for(const k of ['x','y','w','h'])number(v[k],`${name}.${k}`,k==='w'||k==='h'?1:0,k==='x'||k==='w'?1920:1080);}

export function vocabLayout(scene) {
  const plain={'shot-wall':'shot-wall','broll-caption':'footage-caption','phone-cam':'full-footage','device-stage':'screen-frame','laptop-3d':'device-object','filmed-screen':'full-screen','cursor-zoom':'full-screen','photo-path':'photo-wall','headline-slam':'statement','word-swap':'statement','hand-mark':'marked-document','news-card':'document','social-post':'post','chat-bubble':'conversation','terminal-run':'terminal','code-diff':'code-panel','bar-compare':'chart','progress-ring':'chart','rank-race':'chart','concept-hub':'relation','split-compare':'comparison','blueprint-diagram':'blueprint','cinematic-broll':'cinematic-footage','terminal-over-footage':'terminal-footage','suspect-focus':'evidence-focus','footage-bigword':'statement-footage','desk-dispatch':'dispatch-desk','ruler-measure':'measurement'};
  const titleBar=VOCAB_RECIPES[scene.recipe]?!['headline-slam','word-swap'].includes(scene.recipe)&&scene.props?.showTitle!==false:Boolean(scene.spec?.title);
  return {titleBar,layoutSkeleton:titleBar?'top-title-center':plain[scene.recipe]||`legacy:${scene.recipe}`};
}

export function validateVocab(recipe,p,stage='paper-cool') {
  if(!VOCAB_RECIPES[recipe])return;
  if(!p||typeof p!=='object'||Array.isArray(p))throw new Error(`${recipe} 需要 props 对象`);
  if(!STAGES.includes(p.stage||stage))throw new Error('新配方只用 paper-cool / paper-warm / charcoal');
  if(p.showTitle!==undefined&&typeof p.showTitle!=='boolean')throw new Error('showTitle 必须为布尔值');
  if(recipe==='news-card'){
    text(p.source,'source');text(p.date,'date');
    for(const h of p.highlight||[])box(h,'highlight');if(p.zoom)box(p.zoom,'zoom');
    if(p.focusRect)box(p.focusRect,'focusRect');
    for(const jump of p.cutZoom||[]){number(jump.at,'cutZoom.at',0);number(jump.scale,'cutZoom.scale',1,4);if(jump.rect)box(jump.rect,'cutZoom.rect');}
  }
  if(recipe==='social-post')text(p.text,'text');
  if(recipe==='chat-bubble'){
    list(p.turns,'turns',1,6);for(const turn of p.turns){text(turn.text,'turn.text');if(!['user','ai'].includes(turn.role))throw new Error('turn.role 只能为 user / ai');}
  }
  if(recipe==='device-stage'&&p.chrome&&!['browser','window','phone'].includes(p.chrome))throw new Error('chrome 只能为 browser / window / phone');
  if(recipe==='laptop-3d'){number(p.angle??-7,'angle',-12,12);number(p.dolly??.08,'dolly',0,.15);}
  if(p.push&&p.push!==true){number(p.push.from??1,'push.from',1,2);number(p.push.to??1.17,'push.to',1,2);number(p.push.duration??3,'push.duration',.1,30);}
  if(recipe==='action-montage'){list(p.clips,'clips',4,6);for(const clip of p.clips)number(clip.duration??.75,'clip.duration',.5,.9);}
  if(recipe==='quote-fragments'){text(p.text,'text');list(p.keywords,'keywords',1,4);p.keywords.forEach(k=>text(k,'keyword'));number(p.fadeDuration??.5,'fadeDuration',.4,.7);}
  if(recipe==='visual-contrast'){if(!p.left||!p.right)throw new Error('visual-contrast 需要两件素材');number(p.leftHeight??.72,'leftHeight',.2,.8);number(p.rightHeight??.54,'rightHeight',.1,.72);}
  if(recipe==='cutout-stack'){list(p.items,'items',1,30);number(p.stagger??.2,'stagger',.15,.25);number(p.enterDuration??.3,'enterDuration',.25,.45);if(p.showTitle!==false)text(p.title,'title');}
  if(recipe==='paper-break'){if(!['zip','tear','stamp'].includes(p.mode||'zip'))throw new Error('paper-break mode 只能为 zip / tear / stamp');number(p.changeDuration??1,'changeDuration',.8,6);}
  if(recipe==='brand-hero'){if(!p.logo)throw new Error('brand-hero 需要官方logo');number(p.logoHeight??.38,'logoHeight',.3,.45);text(p.line,'line');}
  if(['sticker-text','reaction-cutout'].includes(recipe)){text(p.text,'text');number(p.stroke??10,'stroke',8,12);number(p.angle??-3,'angle',-4,4);if(!['highlight','stamp','blue'].includes(p.ink||'highlight'))throw new Error('贴纸只用荧光/红章/蓝墨');}
  if(recipe==='reaction-cutout'&&!p.person&&!p.personRef)throw new Error('reaction-cutout 需要人物或人物库引用');
  if(recipe==='hand-mark')number(p.labelHeight??.08,'labelHeight',.06,.14);
  if(recipe==='shot-wall'){
    number(p.window??60,'window',5,600);list(p.rows,'rows',1,4);
    for(const row of p.rows){text(row.label,'row.label');list(row.shots,'row.shots',1,200);let sum=0;for(const shot of row.shots){number(shot.d,'shot.d',.04,600);if(!['real','screen','graphic'].includes(shot.k))throw new Error('shot.k 只能为 real / screen / graphic');sum+=shot.d;}
      if(sum>(p.window??60)+.5)throw new Error('row.shots 总时长超过 window');if(row.sweep!==undefined)number(row.sweep,'row.sweep',.5,20);if(row.focus!==undefined)number(row.focus,'row.focus',0,row.shots.length-1);}
    if(p.zoom){number(p.zoom.scale??1.6,'zoom.scale',1.1,2.5);number(p.zoom.row??0,'zoom.row',0,p.rows.length-1);}
    if(p.stamp)text(p.stamp.text,'stamp.text');
  }
  if(recipe==='broll-caption'){
    const lines=Array.isArray(p.caption)?p.caption:[p.caption];list(lines,'caption',1,2);lines.forEach(v=>text(v,'caption'));
    if(lines.some(v=>[...v].length>12))throw new Error('broll-caption 每行最多12字');
    number(p.fontSize??(lines.length>1?78:96),'fontSize',64,140);if(p.side&&!['left','right'].includes(p.side))throw new Error('side 只能为 left / right');
    if(p.cutZoom){list(p.cutZoom,'cutZoom',1,2);for(const jump of p.cutZoom){number(jump.scale,'cutZoom.scale',1,2.5);if(jump.rect)box(jump.rect,'cutZoom.rect');}}
    if(p.mark){if(!['underline','circle'].includes(p.mark.kind||'underline'))throw new Error('mark.kind 只能为 underline / circle');if(p.mark.kind==='circle')box(p.mark.target,'mark.target');}
  }
  if(recipe==='phone-cam'){
    number(p.crop??1.04,'crop',1,1.2);if(p.focus){box(p.focus,'focus');number(p.focus.scale??1.6,'focus.scale',1.1,2.5);}
    if(p.speed!==undefined)number(p.speed,'speed',1,32);if(p.stamp)text(p.stamp.text,'stamp.text');if(p.moire!==undefined)throw new Error('phone-cam 是真拍，不加模拟摩尔纹');
  }
  if(recipe==='filmed-screen'){number(p.moire??.3,'moire',0,1);number(p.handheld??.3,'handheld',0,1);}
  if(recipe==='cursor-zoom'){
    number(p.zoom??1.7,'zoom',1.4,2.2);
    if(typeof p.cursorLog!=='string'){
      list(p.cursorLog,'cursorLog');let prior=-1;
      for(const point of p.cursorLog){number(point.t,'cursorLog.t',0);number(point.x,'cursorLog.x',0,1920);number(point.y,'cursorLog.y',0,1080);if(point.t<prior)throw new Error('cursorLog.t 必须递增');prior=point.t;}
    }
  }
  if(recipe==='terminal-run'){
    list(p.lines,'lines',1,12);for(const line of p.lines){text(line.text,'line.text');if(!line.cmd&&!line.out)throw new Error('line 需要 cmd 或 out');}number(p.speed??1,'speed',.1,10);
  }
  if(recipe==='code-diff'){text(p.before,'before');text(p.after,'after');}
  if(recipe==='bar-compare'){
    list(p.items,'items',1,6);for(const item of p.items){text(item.label,'item.label');number(item.value,'item.value',0);}number(p.highlight??0,'highlight',0,p.items.length-1);
  }
  if(recipe==='progress-ring'){number(p.value,'value',0,100);number(p.from??0,'from',0,100);text(p.label,'label');}
  if(recipe==='rank-race'){
    text(p.title,'title');text(p.source,'source');list(p.frames,'frames',2);let prior=-1;
    for(const frame of p.frames){number(frame.t,'frame.t',0);if(frame.t<=prior)throw new Error('frames.t 必须严格递增');prior=frame.t;list(frame.items,'frame.items',1,6);
      const names=frame.items.map(item=>{text(item.label,'item.label');number(item.value,'item.value',0);return item.label;});
      if(new Set(names).size!==names.length)throw new Error('同一帧的排名对象不能重复');if(frame.label!==undefined)text(frame.label,'frame.label');}
  }
  if(recipe==='concept-hub'){text(p.center,'center');list(p.nodes,'nodes',1,6);p.nodes.forEach(v=>text(typeof v==='string'?v:v.text,'node'));}
  if(recipe==='photo-path'){list(p.images,'images',2,60);number(p.focus??0,'focus',0,p.images.length-1);}
  if(recipe==='hand-mark'){if(!['arrow','circle','underline','box'].includes(p.kind))throw new Error('未知手写标注 kind');box(p.target,'target');if(p.color&&!['stamp','blue-ink'].includes(p.color))throw new Error('标注只用 stamp / blue-ink');}
  if(recipe==='word-swap'){list(p.words,'words',1,8);p.words.forEach(v=>text(v,'word'));number(p.interval??.8,'interval',.35,10);}
  if(recipe==='headline-slam'){text(p.text,'text');if([...p.text].length>10)throw new Error('headline-slam 最多10字');}
  if(recipe==='split-compare'){
    if(!p.left||!p.right)throw new Error('split-compare 需要 left/right 两个完整视窗');
    for(const side of ['left','right']){if(p[side].aspect!==undefined&&Math.abs(Number(p[side].aspect)-16/9)>.02)throw new Error(`${side}.aspect 必须为16:9`);}
    if(p.focusTimeline){list(p.focusTimeline,'focusTimeline',1,20);for(const item of p.focusTimeline){if(!['left','right','both'].includes(item.side))throw new Error('focusTimeline.side 只能为 left / right / both');number(item.at,'focusTimeline.at',0);}}
  }
  if(recipe==='blueprint-diagram'){
    if(!['flow','hub','layers','versus'].includes(p.topology||'flow'))throw new Error('blueprint-diagram topology 无效');
    list(p.nodes,'nodes',1,16);p.nodes.forEach(node=>{text(typeof node==='string'?node:node.title,'node.title');number(node.at??0,'node.at',0);});
    if(p.edges){list(p.edges,'edges',0,32);p.edges.forEach(edge=>{text(edge.from,'edge.from');text(edge.to,'edge.to');number(edge.at??0,'edge.at',0);});}
  }
  if(['cinematic-broll','terminal-over-footage','suspect-focus','footage-bigword'].includes(recipe)){
    if(!p.media)throw new Error(`${recipe} 需要 media`);
    if(p.redactions){list(p.redactions,'redactions',0,20);for(const r of p.redactions)box(r,'redactions');}
  }
  if(recipe==='footage-bigword'){text(p.text,'text');if([...p.text].length>4)throw new Error('footage-bigword 最多4字');}
  if(recipe==='desk-dispatch'){list(p.items,'items',2,6);p.items.forEach(item=>{text(item.label,'item.label');if(item.media){} });}
  if(recipe==='ruler-measure'){list(p.rows,'rows',1,20);p.rows.forEach(row=>{text(row.label,'row.label');number(row.value,'row.value',0,100);});}
}

export function prepareVocab(scene) {
  const definition=VOCAB_RECIPES[scene.recipe]||(scene.recipe==='stock-shot'?{slots:[]}:null);
  if(!definition)return {props:scene.props,media:scene.media||[]};
  // 兼容阶段A的 news-card spec；新工程统一写 props。
  let p=structuredClone(scene.props||(scene.recipe==='stock-shot'?scene.spec:{} )||{});
  if(scene.recipe==='news-card'&&!scene.props){
    const old=scene.spec||{},h=old.highlight;
    p={...old,shot:{m:0},highlight:h?.box?[{x:h.box.x,y:h.box.y,w:h.box.width??h.box.w,h:h.box.height??h.box.h,at:h.at}]:[]};
    delete p.zoom;
  }
  validateVocab(scene.recipe,p,scene.stage||'paper-cool');
  const media=structuredClone(scene.media||[]);
  function slot(value,key){
    if(value==null)return value;
    if(Number.isInteger(value))value={m:value};
    if(Number.isInteger(value.m)){if(value.m<0||value.m>=media.length)throw new Error(`${key} 引用不存在的 media`);return value;}
    const m=typeof value==='string'?{src:value}:value;
    if(!m.src)throw new Error(`${key} 需要文件路径或 {src,start,rate}`);
    media.push(m);return {m:media.length-1};
  }
  for(const key of definition.slots){p[key]=['images','items','clips'].includes(key)?(p[key]||[]).map((value,i)=>({...((typeof value==='object')?value:{}),...slot(value,`${key}[${i}]`)})):slot(p[key],key);}
  if(scene.recipe==='desk-dispatch')p.items=(p.items||[]).map((item,i)=>({...item,...(item.media?{media:slot(item.media,`items[${i}].media`)}:{})}));
  if(p.overlays)p.overlays=p.overlays.map((o,i)=>({...o,...(o.media?{media:slot(o.media,`overlays[${i}].media`)}:{})}));
  if(scene.recipe==='action-montage'){let at=0;for(const clip of p.clips){const duration=clip.duration??.75;Object.assign(media[clip.m],{at,duration});clip.at=at;clip.duration=duration;at+=duration;}if(scene.dur&&at>scene.dur+.001)throw new Error('action-montage 素材时长超过镜头');}
  if((RECORDING_CONTAINERS.includes(scene.recipe)||['broll-caption','phone-cam'].includes(scene.recipe))&&!p.media)throw new Error(`${scene.recipe} 缺少 media`);
  if(scene.recipe==='news-card'&&!p.shot)throw new Error('news-card 缺少 shot');
  for(const layer of scene.layers||[]){if(!VOCAB_LAYERS.includes(layer.kind))throw new Error(`未知质感层 ${layer.kind}`);}
  return {props:p,media};
}
