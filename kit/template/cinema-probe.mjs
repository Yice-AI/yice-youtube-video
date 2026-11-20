import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

export function cameraMotion(samples,{minTranslationPx=.5,minScaleChange=.001}={}){
  const tracks=new Map();
  for(const sample of samples)for(const transform of sample.transforms){const list=tracks.get(transform.id)||[];list.push({...transform,time:sample.time});tracks.set(transform.id,list);}
  const moving=[];
  for(const [id,track] of tracks){
    const range=key=>Math.max(...track.map(t=>t[key]))-Math.min(...track.map(t=>t[key]));
    const translation=Math.max(range('x'),range('y')),scale=Math.max(range('sx'),range('sy'));
    if(translation>minTranslationPx||scale>minScaleChange)moving.push({id,translationPx:translation,scaleChange:scale});
  }
  return {moving:moving.length>0,tracks:moving,samples:samples.length};
}

export function readingRegions(scene){
  if(Array.isArray(scene.readingRegions))return scene.readingRegions;
  if(Array.isArray(scene.props?.readingRegions))return scene.props.readingRegions;
  if(scene.recipe==='news-card')return scene.props?.focusRect?[{name:'focus',media:0,rect:scene.props.focusRect}]:(scene.props?.highlight||[]).map((rect,i)=>({name:'highlight-'+i,media:0,rect}));
  if(scene.recipe==='hand-mark'&&scene.sourceType==='web_capture'&&scene.props?.media)return [{name:'marked-region',screenRect:scene.props.target}];
  return [];
}

function gsapPath(root){
  if(process.env.YICE_GSAP_PATH&&fs.existsSync(process.env.YICE_GSAP_PATH))return process.env.YICE_GSAP_PATH;
  const vendor=path.join(root,'node_modules/hyperframes/dist/vendor/npm');
  if(fs.existsSync(vendor))for(const entry of fs.readdirSync(vendor).filter(s=>s.startsWith('gsap@'))){const file=path.join(vendor,entry,'dist/gsap.min.js');if(fs.existsSync(file))return file;}
  throw new Error('机位/字高检查需要本机 GSAP；设置 YICE_GSAP_PATH 或安装本期依赖');
}

export async function probeCompositions(root,scenes,{outputDir=root,limits={}}={}){
  const require=createRequire(path.join(root,'package.json')),{chromium}=require(process.env.YICE_PLAYWRIGHT_MODULE||'playwright-core');
  const gsap=gsapPath(root),documents=new Map(),crops=[],camera=[],unmarked=[];
  const cropDir=path.join(outputDir,'reading-regions');fs.mkdirSync(cropDir,{recursive:true});
  for(const scene of scenes){
    const file=path.join(root,'compositions/scenes',scene.id+'.html');
    const html=fs.readFileSync(file,'utf8'),body=html.match(/<template[^>]*>([\s\S]*?)<\/template>/i)?.[1];
    if(!body)throw new Error('场景缺少可加载的composition：'+scene.id);
    documents.set('/__probe/'+encodeURIComponent(scene.id),'<!doctype html><meta charset="utf-8"><base href="/"><link rel="stylesheet" href="/assets/frame.css"><link rel="stylesheet" href="/assets/vocab.css"><script src="/__gsap.js"></script><script src="/assets/yice.js"></script><script src="/assets/vocab.js"></script><script>window.__timelines={};</script><body style="margin:0;overflow:hidden">'+body);
  }
  const server=http.createServer((request,response)=>{
    const url=new URL(request.url,'http://localhost');
    if(documents.has(url.pathname)){response.setHeader('Content-Type','text/html');response.end(documents.get(url.pathname));return;}
    const file=url.pathname==='/__gsap.js'?gsap:path.resolve(root,'.'+decodeURIComponent(url.pathname));
    if((file!==gsap&&!file.startsWith(root+path.sep))||!fs.existsSync(file)||!fs.statSync(file).isFile()){response.writeHead(404).end();return;}
    const type={'.js':'text/javascript','.css':'text/css','.html':'text/html','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.mp4':'video/mp4'}[path.extname(file)]||'application/octet-stream';
    response.setHeader('Content-Type',type);const size=fs.statSync(file).size,match=request.headers.range?.match(/bytes=(\d+)-(\d*)/);
    if(match){const start=Number(match[1]),end=Math.min(size-1,match[2]?Number(match[2]):size-1);if(start>=size){response.writeHead(416).end();return;}response.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${size}`,'Content-Length':end-start+1,'Accept-Ranges':'bytes'});fs.createReadStream(file,{start,end}).pipe(response);}
    else{response.setHeader('Content-Length',size);fs.createReadStream(file).pipe(response);}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true,...(process.env.YICE_CHROME_EXECUTABLE?{executablePath:process.env.YICE_CHROME_EXECUTABLE}:{channel:'chrome'})});
  try{
    const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
    let pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.message));
    await page.route('**/*',route=>route.request().url().startsWith(origin+'/')?route.continue():route.abort());
    for(const scene of scenes){
      pageErrors=[];
      await page.goto(origin+'/__probe/'+encodeURIComponent(scene.id),{waitUntil:'load'});
      if(pageErrors.length)throw new Error(scene.id+' 场景脚本错误：'+pageErrors.join('; '));
      await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode().catch(()=>{})));});
      const duration=scene.dur??scene.E-(scene.compositionStart??scene.B),samples=await page.evaluate(({duration,recipe})=>{
        const tl=Object.values(window.__timelines||{})[0];if(!tl)throw new Error('缺少主时间轴');tl.pause();
        const elements=[...document.querySelectorAll('.yf-cam,[data-camera],.v-world,.r-rec .world')];
        if(recipe==='laptop-3d'){const rig=document.querySelector('.v-browser')?.parentElement;if(rig)elements.push(rig);}
        if(recipe==='filmed-screen'){const frame=document.querySelector('.v-browser');if(frame)elements.push(frame);}
        const unique=[...new Set(elements)],result=[];
        // 跳过统一的0.5秒入场和0.5秒退场；测真正的镜头机位层。
        const start=Math.min(.55,duration/3),end=Math.max(start,duration-.55);
        for(let time=start;time<=end+.001;time+=.1){tl.seek(time,false);result.push({time,transforms:unique.map((e,i)=>{const m=new DOMMatrix(getComputedStyle(e).transform);return {id:e.id||e.className+'-'+i,x:m.m41,y:m.m42,sx:Math.hypot(m.m11,m.m12,m.m13),sy:Math.hypot(m.m21,m.m22,m.m23)};})});}
        return result;
      },{duration,recipe:scene.recipe});
      const reframes=await page.evaluate(()=>JSON.parse(document.querySelector('.yf-cam')?.dataset.reframes||'[]'));
      const aspect=await page.evaluate(()=>[...document.querySelectorAll('.v-media')].map((element,index)=>{const box=element.getBoundingClientRect(),style=getComputedStyle(element);const sourceWidth=element.naturalWidth||element.videoWidth||0,sourceHeight=element.naturalHeight||element.videoHeight||0,sourceRatio=sourceHeight?sourceWidth/sourceHeight:Infinity,ratio=box.height?box.width/box.height:Infinity;return {index,width:box.width,height:box.height,ratio,sourceRatio,objectFit:style.objectFit};}).filter(row=>row.sourceRatio>=1.35&&(row.ratio<1.35||row.objectFit==='cover'&&row.ratio<1.5)));
      camera.push({id:scene.id,...cameraMotion(samples,limits),reframes,measurements:samples,aspect});
      const regions=readingRegions(scene);if(!regions.length&&scene.sourceType==='web_capture')unmarked.push(scene.id);
      for(const [index,region] of regions.entries()){
        const time=region.at??Math.max(.55,duration-.75);
        const box=await page.evaluate(({region,time})=>{
          Object.values(window.__timelines)[0].seek(time,false);
          const intersect=(a,b)=>{const x=Math.max(a.x,b.x),y=Math.max(a.y,b.y),right=Math.min(a.x+a.width,b.x+b.width),bottom=Math.min(a.y+a.height,b.y+b.height);return {x,y,width:Math.max(0,right-x),height:Math.max(0,bottom-y)};};
          const viewport={x:0,y:0,width:1920,height:1080};
          if(region.screenRect){const r=region.screenRect;return intersect({x:r.x,y:r.y,width:r.w??r.width,height:r.h??r.height},viewport);}
          const candidates=region.selector?[...document.querySelectorAll(region.selector)]:[...document.querySelectorAll('img')].filter(e=>e.id.endsWith('-m'+(region.media??0))||e.id.endsWith('-detail-media'));
          const boxes=[];
          for(const image of candidates){
            if(!image.naturalWidth)continue;let visible=true;
            for(let e=image;e;e=e.parentElement){const s=getComputedStyle(e);if(+s.opacity<.1||s.visibility==='hidden'||s.display==='none')visible=false;}
            if(!visible)continue;
            const b=image.getBoundingClientRect(),style=getComputedStyle(image),fit=style.objectFit==='cover'?Math.max(b.width/image.naturalWidth,b.height/image.naturalHeight):Math.min(b.width/image.naturalWidth,b.height/image.naturalHeight);
            const content={x:b.x+(b.width-image.naturalWidth*fit)/2,y:b.y+(b.height-image.naturalHeight*fit)/2};const r=region.rect;
            if(!r)continue;
            const full={x:content.x+r.x*fit,y:content.y+r.y*fit,width:(r.w??r.width)*fit,height:(r.h??r.height)*fit};let clipped=intersect(full,viewport);
            for(let e=image.parentElement;e&&e!==document.body&&e!==document.documentElement;e=e.parentElement){const s=getComputedStyle(e);if(/hidden|clip|scroll|auto/.test(s.overflow+s.overflowX+s.overflowY))clipped=intersect(clipped,e.getBoundingClientRect());}
            if(clipped.width*clipped.height>=full.width*full.height*.9)boxes.push({...clipped,scale:fit});
          }
          return boxes.sort((a,b)=>b.scale-a.scale)[0]||null;
        },{region,time});
        if(!box||box.width<2||box.height<2){crops.push({scene:scene.id,region:region.name||String(index),error:'阅读区域不可见或裁切不完整'});continue;}
        const file=path.join(cropDir,scene.id+'-'+index+'.png');
        const clip={x:Math.max(0,Math.floor(box.x)),y:Math.max(0,Math.floor(box.y)),width:Math.min(1920-Math.floor(box.x),Math.ceil(box.width)),height:Math.min(1080-Math.floor(box.y),Math.ceil(box.height))};
        await page.screenshot({path:file,clip});crops.push({scene:scene.id,region:region.name||String(index),time,clip,file});
      }
    }
  }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
  const files=crops.filter(r=>r.file).map(r=>r.file);
  const ocr=files.length?JSON.parse(execFileSync('xcrun',['swift',path.join(path.dirname(fileURLToPath(import.meta.url)),'vision-readability.swift'),...files],{encoding:'utf8',timeout:180000,maxBuffer:8e6})):[];
  const readings=crops.map(c=>{
    if(c.error)return c;
    const result=ocr.find(r=>r.file===c.file),words=(result?.words||[]).filter(w=>w.confidence>=.3&&w.text.trim().length>=2);
    return {...c,error:result?.error||(!words.length?'重点区域未识别到文字；需核对所选区域':null),effectiveTextHeightPx:words.length?Math.min(...words.map(w=>w.heightPx)):null,words};
  });
  return {camera,readings,unmarkedReadingScenes:unmarked,method:'1920×1080本地composition实测；机位层变换采样；重点区域实际像素截图经Apple Vision测字高；未访问外网。'};
}
