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
};
const STAGES = ['paper-cool','paper-warm','charcoal'];
const number=(v,name,min=-Infinity,max=Infinity)=>{
  if(!Number.isFinite(v)||v<min||v>max)throw new Error(`${name} 必须为 ${min}–${max} 的有限数值`);
};
const text=(v,name)=>{if(typeof v!=='string'||!v.trim())throw new Error(`${name} 不能为空`);};
const list=(v,name,min=1,max=Infinity)=>{if(!Array.isArray(v)||v.length<min||v.length>max)throw new Error(`${name} 需要 ${min}–${max} 项`);};
function box(v,name){if(!v)throw new Error(`${name} 缺少框`);for(const k of ['x','y','w','h'])number(v[k],`${name}.${k}`,k==='w'||k==='h'?1:0,k==='x'||k==='w'?1920:1080);}

export function vocabLayout(scene) {
  const plain={'device-stage':'screen-frame','laptop-3d':'device-object','filmed-screen':'full-screen','cursor-zoom':'full-screen','photo-path':'photo-wall','headline-slam':'statement','word-swap':'statement','hand-mark':'marked-document','news-card':'document','social-post':'post','chat-bubble':'conversation','terminal-run':'terminal','code-diff':'code-panel','bar-compare':'chart','progress-ring':'chart','rank-race':'chart','concept-hub':'relation'};
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
  }
  if(recipe==='social-post')text(p.text,'text');
  if(recipe==='chat-bubble'){
    list(p.turns,'turns',1,6);for(const turn of p.turns){text(turn.text,'turn.text');if(!['user','ai'].includes(turn.role))throw new Error('turn.role 只能为 user / ai');}
  }
  if(recipe==='device-stage'&&p.chrome&&!['browser','window','phone'].includes(p.chrome))throw new Error('chrome 只能为 browser / window / phone');
  if(recipe==='laptop-3d'){number(p.angle??-7,'angle',-12,12);number(p.dolly??.08,'dolly',0,.15);}
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
}

export function prepareVocab(scene) {
  const definition=VOCAB_RECIPES[scene.recipe];
  if(!definition)return {props:scene.props,media:scene.media||[]};
  // 兼容阶段A的 news-card spec；新工程统一写 props。
  let p=structuredClone(scene.props||{});
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
  for(const key of definition.slots){p[key]=key==='images'?(p[key]||[]).map((value,i)=>slot(value,`images[${i}]`)):slot(p[key],key);}
  if(RECORDING_CONTAINERS.includes(scene.recipe)&&!p.media)throw new Error(`${scene.recipe} 缺少 media`);
  if(scene.recipe==='news-card'&&!p.shot)throw new Error('news-card 缺少 shot');
  for(const layer of scene.layers||[]){if(!VOCAB_LAYERS.includes(layer.kind))throw new Error(`未知质感层 ${layer.kind}`);}
  return {props:p,media};
}
