import fs from 'node:fs';
import path from 'node:path';

const real=new Set(['real_video','photo','cutout','screenshot']);
export function sceneMediaClass(scene,media,ledger=[]){
  if(!media.some(m=>m.exists))return 'text';
  const source=ledger.filter(l=>media.some(m=>[l.path,l.sourcePath,...(l.files||[]).map(f=>f.path)].filter(Boolean).some(p=>p===m.file||p===m.url||p===m.cand)));
  if(source.length&&source.every(l=>/image2|generated|image_gen|text.to.image/i.test([l.sourceType,l.provider,l.type,l.generation?.model].join(' '))))return 'graphics';
  const recipe=scene.recipe;
  if(['brand-hero','sticker-text'].includes(recipe))return 'graphics';
  if(['cutout-stack','reaction-cutout'].includes(recipe))return 'cutout';
  if(['news-card','social-post','device-stage','laptop-3d','filmed-screen','cursor-zoom','hand-mark','doc-zoom','rec-zoom','editor'].includes(recipe))return 'screenshot';
  if(['stock-shot','action-montage','broll-caption','phone-cam'].includes(recipe))return media.some(m=>m.video)?'real_video':'photo';
  if(['photo-path','photo-word','quote-fragments'].includes(recipe))return 'photo';
  if(['paper-break','visual-contrast'].includes(recipe))return 'cutout';
  return real.has(scene.mediaClass)?scene.mediaClass:'graphics';
}

export function mediaCoverage(root,scenes,buildReport,episode={},ledger=[]){
  const totals={real_video:0,photo:0,cutout:0,screenshot:0,graphics:0,text:0},rows=[];
  for(const scene of scenes){
    const report=buildReport.find(r=>r.id===scene.id)||{},duration=scene.E-scene.B;
    const media=(report.media||[]).map(m=>{
      let file=m.url||m.cand||'';
      for(const [alias,dir]of Object.entries(episode.mediaRoots||{}))if(file.startsWith(alias))file=path.join(path.resolve(root,dir),file.slice(alias.length));
      if(file.startsWith('@vo/'))file=path.join(path.resolve(root,episode.voiceDir||'voice'),file.slice(4));
      file=path.resolve(root,file);return {...m,file,exists:fs.existsSync(file)&&fs.statSync(file).isFile(),video:m.video||/\.(mp4|mov|webm)$/i.test(file)};
    });
    const kind=sceneMediaClass(scene,media,ledger);let seconds=duration;
    if(scene.recipe==='quote-fragments')seconds=Math.max(0,duration-(scene.props?.photoAt??(scene.props?.keywordAt??1)+1.3));
    if(scene.recipe==='paper-break')seconds=Math.min(duration,(scene.props?.changeAt??.7)+(scene.props?.changeDuration??1));
    totals[kind]+=seconds;totals[scene.recipe==='quote-fragments'?'text':'graphics']+=duration-seconds;
    rows.push({id:scene.id,kind,seconds,duration,realSeconds:real.has(kind)?seconds:0,verifiedFiles:media.filter(m=>m.exists).map(m=>m.url||m.cand)});
  }
  const duration=rows.reduce((s,r)=>s+r.duration,0),realSeconds=rows.reduce((s,r)=>s+r.realSeconds,0);
  return {method:'主要承载信息的前景素材按时长分类；图标/生成图不计真实画面，截图单列，过渡动作不重复计时',duration,realSeconds,realRatio:duration?realSeconds/duration:0,seconds:totals,scenes:rows};
}
