import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {analyzeRendered} from './cinema-frames.mjs';
import {probeCompositions} from './cinema-probe.mjs';
import {mediaCoverage} from './media-coverage.mjs';

export const DEFAULT_CINEMA_LIMITS=Object.freeze({maxStillSeconds:2.5,minReadTextPx:28,maxNoCameraRatio:.5,pixelDelta:10,changedFraction:.002,minTranslationPx:.5,minScaleChange:.001,minRealRatio:.3,minChangesPerSecond:.45,maxNearStaticSourceSeconds:1.8});

export function cinemaLimits(overrides={}){
  const limits={...DEFAULT_CINEMA_LIMITS,...overrides};
  for(const [key,value] of Object.entries(limits))if(!(key in DEFAULT_CINEMA_LIMITS)||!Number.isFinite(value)||value<0)throw new Error('无效 cinema.limits.'+key);
  if(limits.maxNoCameraRatio>1||limits.changedFraction>1||limits.minRealRatio>1||limits.pixelDelta>255)throw new Error('机位/变化比例或像素差阈值超出范围');
  return limits;
}

export function evaluateCinema({scenes,frames,probe,media,limits={}}){
  limits=cinemaLimits(limits);const findings=[];
  if(!scenes?.length)throw new Error('画面检查需要镜头列表');
  for(const scene of scenes){
    const viewports=[scene.props?.viewport,...(scene.props?.viewports||[]),scene.props?.left,scene.props?.right,scene.viewport].filter(Boolean);
    for(const viewport of viewports){const width=Number(viewport.width??viewport.w),height=Number(viewport.height??viewport.h);if(Number.isFinite(width)&&Number.isFinite(height)&&width/height<1.35)findings.push({severity:'error',code:'horizontal_aspect_cropped',scenes:[scene.id],message:'16:9 承载窗口宽高比小于1.35',actual:{width,height,ratio:width/height}});}
    const row=frames.scenes.find(s=>s.id===scene.id);
    if(!row||!row.frames){findings.push({severity:'error',code:'cinema_input_missing',scenes:[scene.id],message:'缺少该镜头成片帧'});continue;}
    const runs=row.stillRuns.filter(r=>r.seconds>limits.maxStillSeconds+1e-8);
    if(runs.length)findings.push({severity:'error',code:'shot_still_too_long',scenes:[scene.id],message:`镜头内静止超过 ${limits.maxStillSeconds}s`,actual:row.longestStillSeconds,runs});
    const sourceVideo = scene.sourceType === 'recording' || scene.sourceType === 'camera' ||
      ['device-stage','laptop-3d','filmed-screen','cursor-zoom','phone-cam','cinematic-broll','terminal-over-footage','suspect-focus','footage-bigword'].includes(scene.recipe);
    const staticRuns = row.stillRuns.filter(r=>r.seconds>limits.maxNearStaticSourceSeconds+1e-8);
    if(sourceVideo && staticRuns.length)findings.push({severity:'error',code:'near_static_source',scenes:[scene.id],message:`源画面连续静止超过 ${limits.maxNearStaticSourceSeconds}s`,runs:staticRuns});
    for(const box of row.blankBoxes||[])if(box.blank===true||Number(box.variance??1)<.002)findings.push({severity:'error',code:'blank_or_low_variance_box',scenes:[scene.id],message:'检测到空白或低方差画面框',box});
  }
  for(const region of probe.readings){
    if(region.error||!Number.isFinite(region.effectiveTextHeightPx))findings.push({severity:'error',code:'readability_unmeasured',scenes:[region.scene],region:region.region,message:region.error||'重点区域字高未测得'});
    else if(region.effectiveTextHeightPx+1e-8<limits.minReadTextPx)findings.push({severity:'error',code:'read_text_too_small',scenes:[region.scene],region:region.region,actual:region.effectiveTextHeightPx,message:`重点文字实测字高不足 ${limits.minReadTextPx}px；使用 zoom/crop 放大重点区域`});
  }
  const missingCamera=scenes.filter(s=>!probe.camera.some(c=>c.id===s.id));
  if(missingCamera.length)findings.push({severity:'error',code:'cinema_input_missing',scenes:missingCamera.map(s=>s.id),message:'缺少实际机位层采样'});
  for(const row of probe.camera||[])if(row.aspect?.length)findings.push({severity:'error',code:'horizontal_aspect_cropped',scenes:[row.id],message:'成片媒体窗口宽高比小于1.35或存在高风险cover裁切',boxes:row.aspect});
  const noCamera=scenes.filter(s=>!probe.camera.find(c=>c.id===s.id)?.moving).map(s=>s.id),ratio=noCamera.length/scenes.length;
  if(ratio>limits.maxNoCameraRatio+1e-8)findings.push({severity:'error',code:'camera_motion_ratio_low',scenes:noCamera,actual:ratio,message:`无推/移/视差的镜头占比 ${(ratio*100).toFixed(1)}%，超过 ${limits.maxNoCameraRatio*100}%`});
  if(!Number.isFinite(media?.realRatio))findings.push({severity:'error',code:'media_coverage_unmeasured',message:'未核对实际素材文件与占时长'});
  else if(media.realRatio+1e-8<limits.minRealRatio)findings.push({severity:'error',code:'real_media_ratio_low',actual:media.realRatio,message:`真实画面占时长不足 ${limits.minRealRatio*100}%`});
  const changes=frames.visualChange?.eventsPerSecond;
  if(!Number.isFinite(changes))findings.push({severity:'error',code:'visual_change_unmeasured',message:'未按24fps像素口径测量画面变化率'});
  else if(changes+1e-8<limits.minChangesPerSecond)findings.push({severity:'error',code:'visual_change_rate_low',actual:changes,message:`画面变化率不足 ${limits.minChangesPerSecond} 次/秒`});
  return {ok:findings.length===0,limits,findings,metrics:{totalScenes:scenes.length,noCameraScenes:noCamera,noCameraRatio:ratio,readingRegions:probe.readings.length,unmarkedReadingScenes:probe.unmarkedReadingScenes||[],realRatio:media?.realRatio,visualChangesPerSecond:changes},frames,probe,media};
}

export async function checkCinema(root,{rendered,outputDir=root,limits={}}={}){
  if(!rendered||!fs.existsSync(rendered))throw new Error('三条画面硬门需要完整成片：check --rendered 成片.mp4；渲染前可用 --visual-only 做结构预检');
  root=path.resolve(root);fs.mkdirSync(outputDir,{recursive:true});
  const episode=JSON.parse(fs.readFileSync(path.join(root,'episode.json'))),beats=JSON.parse(fs.readFileSync(path.join(root,'beats.json'))),report=JSON.parse(fs.readFileSync(path.join(root,'build-report.json')));
  const scenes=(beats.scenes||beats).map(scene=>{const built=report.find(s=>s.id===scene.id);if(!built)throw new Error('镜头尚未build：'+scene.id);return {...scene,B:built.B,E:built.E,compositionStart:built.start,dur:built.dur};});
  const config=cinemaLimits({...episode.cinema?.limits,...limits});
  const frames=await analyzeRendered(rendered,scenes,config),probe=await probeCompositions(root,scenes,{outputDir,limits:config});
  const ledgerFile=path.join(root,'asset-ledger.jsonl'),ledger=fs.existsSync(ledgerFile)?fs.readFileSync(ledgerFile,'utf8').split('\n').filter(Boolean).map(JSON.parse):[];
  const media=mediaCoverage(root,scenes,report,episode,ledger);
  const result={...evaluateCinema({scenes,frames,probe,media,limits:config}),rendered:path.resolve(rendered),renderedSha256:createHash('sha256').update(fs.readFileSync(rendered)).digest('hex')};
  fs.writeFileSync(path.join(outputDir,'cinema-check-report.json'),JSON.stringify(result,null,2)+'\n');return result;
}
