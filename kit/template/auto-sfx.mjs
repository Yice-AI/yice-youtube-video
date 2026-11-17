import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {recordAsset} from './asset-ledger.mjs';

export const AUTO_SFX_FILES={whoosh:'whoosh.wav',tick:'fast-tick.wav',pop:'mouse-click.wav',thump:'stamp.wav',swipe:'underline.wav'};
const TYPES=new Set(Object.keys(AUTO_SFX_FILES));
const hash=value=>createHash('sha256').update(value).digest('hex');

export function planAutoSfx(scenes,{density=1}={}){
  if(!Number.isFinite(density)||density<0||density>1)throw new Error('auto_sfx.density 必须为 0–1');
  const events=[];
  for(const scene of scenes){
    const base=scene.start??scene.B??0,end=scene.E??scene.end,duration=end-base,p=scene.props||{};
    if(!Number.isFinite(base)||!Number.isFinite(end)||duration<=0)throw new Error('自动音效需要有效镜头时间：'+scene.id);
    if(scene.sfx===false)continue;
    const cue=(name,at,key=false,reason='')=>{
      if(!TYPES.has(name))throw new Error('未知自动音效类型：'+name);
      const time=base+Number(at);
      if(!Number.isFinite(time))throw new Error('音效时间无效：'+scene.id);
      if(time>=0&&time<end)events.push({scene:scene.id,name,time:+time.toFixed(3),key,auto:true,reason});
    };
    if(Array.isArray(scene.sfx)){for(const e of scene.sfx)cue(e.name,e.at,e.key??e.name==='thump','幕表显式节拍');continue;}
    if(base>0&&scene.enter&&scene.enter!=='cut')cue('whoosh',0,false,'关系转场');
    if(['bar-compare','progress-ring','rank-race','counter','big-number'].includes(scene.recipe)){
      if(scene.recipe==='rank-race'&&p.frames?.length)for(const [i,frame] of p.frames.entries())cue('tick',frame.at??frame.time??i,false,'排名/数字变化');
      else for(let at=.45;at<Math.min(duration-.2,2.5);at+=1)cue('tick',at,false,'数字滚动');
    }
    if(scene.recipe==='chat-bubble')for(const [i,turn] of (p.turns||[]).entries())cue('pop',turn.at??.3+i*.8,false,'对话气泡');
    if(['news-card','social-post','quote-card','card-grid','checklist','code-diff'].includes(scene.recipe))cue('pop',.3,false,'证据/卡片入场');
    if(scene.recipe==='cutout-stack')for(const [i] of (p.items||[]).entries())cue('pop',i*(p.stagger??.2),false,'照片/剪报入场');
    if(['sticker-text','reaction-cutout'].includes(scene.recipe))cue('pop',p.at??.3,false,'反应贴纸入场');
    for(const layer of scene.layers||[])if(layer.kind==='notification-stack')for(const [i,item] of (layer.items||[]).entries())cue('pop',item.at??.3+i,false,'通知卡片');
    if(scene.recipe==='paper-break')cue('thump',(p.changeAt??.7)+(p.changeDuration??1)-.12,true,'变形物件落定');
    else if(['stamp-proof','paper-evidence','stamp'].includes(scene.recipe)||p.stamp)cue('thump',p.stampAt??.6,true,'盖章/物件落定');
    if(scene.recipe==='hand-mark'||p.highlight?.length)cue('swipe',p.highlightAt??.6,false,'高亮划线');
  }
  return events.filter(e=>density===1||(density>0&&parseInt(hash(e.scene+'|'+e.name+'|'+e.time).slice(0,8),16)/0x100000000<density)).sort((a,b)=>a.time-b.time);
}

export function spaceSfx(events,identity=e=>e.src||e.name){
  const last=new Map(),kept=[],dropped=[];
  for(const event of [...events].sort((a,b)=>a.time-b.time||Number(a.auto)-Number(b.auto))){
    const key=identity(event);
    if(event.time-(last.get(key)??-Infinity)<1-1e-8){dropped.push({...event,reason:'同一音效 1 秒内不重复'});continue;}
    kept.push(event);last.set(key,event.time);
  }
  return {events:kept,dropped};
}

export function prepareAutoSfx({root,scenes,config,resolve,manualEvents=[]}){
  if(!config.auto_sfx?.enabled)return {events:manualEvents,dropped:[],enabled:false};
  const options=config.auto_sfx,planned=planAutoSfx(scenes,options),assets={};
  fs.mkdirSync(path.join(root,'assets/audio/sfx'),{recursive:true});
  for(const name of new Set(planned.map(e=>e.name))){
    const metadata=options.bank?.[name]||{},src=metadata.src||config.sfx_files?.[name]||path.join(config.sfx_dir||'',AUTO_SFX_FILES[name]);
    const original=resolve(src),bytes=fs.readFileSync(original),sha256=hash(bytes);
    const relative=`assets/audio/sfx/${name}-${sha256.slice(0,12)}${path.extname(original)}`;
    if(path.resolve(original)!==path.resolve(root,relative))fs.copyFileSync(original,path.join(root,relative));
    assets[name]={src:relative,original,sha256};
    recordAsset(root,{id:'auto-sfx-'+name+'-'+sha256.slice(0,12),kind:'sound',sourceType:'local_existing',sourceUrl:metadata.sourceUrl||pathToFileURL(original).href,creator:metadata.creator||'本地既有素材库',license:metadata.license||'本地已有素材，用户授权本项目使用；未声明CC0',licenseUrl:metadata.licenseUrl||null,capturedAt:new Date().toISOString(),path:relative,sha256,usage:'自动音效 '+name,modified:false});
  }
  const combined=[...manualEvents,...planned.map(e=>({...e,src:assets[e.name].src}))];
  // 用文件内容去重：两个不同名字指向同一音效也不能在 1 秒内重复。
  const identities=new Map();
  const result=spaceSfx(combined,e=>{const src=e.src||config.sfx_files?.[e.name]||path.join(config.sfx_dir||'',e.name+'.wav');const file=resolve(src);if(!identities.has(file))identities.set(file,hash(fs.readFileSync(file)));return identities.get(file);});
  const report={enabled:true,density:options.density??1,minimumRepeatSeconds:1,levels:{normalBelowVoiceDb:config.sfx_normal_below_voice_db??18,keyBelowVoiceDb:config.sfx_key_below_voice_db??12},...result,assets};
  fs.writeFileSync(path.join(root,'auto-sfx-report.json'),JSON.stringify(report,null,2)+'\n');
  return report;
}
