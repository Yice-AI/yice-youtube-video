import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {parseArgs} from 'node:util';
import {recordBrowserFrames} from './browser-frames.mjs';

const options = Object.fromEntries('project url id seconds highlight actions source scene fps theme scale'.split(' ').map(key => [key,{type:'string'}]));
const {values:args} = parseArgs({options});
const url = new URL(args.url);
const duration = Number(args.seconds ?? 6), fps = Number(args.fps ?? 30);
const scale = Number(args.scale ?? 1.5);
const colorScheme = args.theme === 'light' ? 'light' : 'dark';
if (!args.project || !/^[\w-]+$/.test(args.id || '') || !['http:','https:','file:'].includes(url.protocol) || url.username || url.password)
  throw Error('需要 project、合法 id 与公开网页或本地文件 URL');
if (!(duration >= 2 && duration <= 20 && fps === 30)) throw Error('要求 2–20 秒、30fps');
if (!(scale >= 1 && scale <= 2.5)) throw Error('要求 scale 在 1.0–2.5 之间');
const project = path.resolve(args.project);
const folder = path.join(project,'assets/webcam',args.id);
const actions = args.actions ? JSON.parse(args.actions.trimStart().startsWith('[') ? args.actions : fs.readFileSync(args.actions,'utf8')) : [];
if (args.highlight) actions.unshift({type:'highlight',text:args.highlight});
if (!Array.isArray(actions)) throw Error('actions 需要数组');
const require = createRequire(path.join(project,'package.json'));
const search = [project,process.cwd(),import.meta.dirname,...(process.env.NODE_PATH||'').split(path.delimiter),
  path.join(os.homedir(),'.codex/skills/guizang-social-card-skill')];
const {chromium} = require(process.env.YICE_PLAYWRIGHT_MODULE || require.resolve('playwright-core',{paths:search}));
const viewport = {width:Math.round(1920/scale),height:Math.round(1080/scale)};
const cx0 = Math.round(viewport.width/2), cy0 = Math.round(viewport.height/2);
const browser = await chromium.launch(process.env.YICE_CHROME_EXECUTABLE ? {executablePath:process.env.YICE_CHROME_EXECUTABLE} : {channel:'chrome'});
const events = [];
let position = {x:cx0,y:cy0};
function log(t,kind,rect,camScale) {
  events.push({t,kind,...position,rect,recommendedCamera:{scale:camScale,cx:Math.round(position.x*scale),cy:Math.round(position.y*scale)}});
}
try {
  fs.mkdirSync(path.dirname(folder),{recursive:true});
  fs.mkdirSync(folder);
} catch (error) { await browser.close(); throw error; }
try {
  const page = await browser.newPage({viewport,deviceScaleFactor:scale,colorScheme,acceptDownloads:false});
  page.setDefaultTimeout(5000);
  await page.addInitScript(({ix,iy})=>{
    addEventListener('DOMContentLoaded',()=>{
      const pointer=document.createElement('div');
      pointer.id='yice-capture-pointer';
      pointer.style.cssText=`position:fixed;left:0;top:0;transform:translate(${ix}px,${iy}px);z-index:2147483647;pointer-events:none;filter:drop-shadow(0 2px 3px #000)`;
      pointer.innerHTML='<svg width="24" height="34" viewBox="0 0 26 36"><path d="M2 2L23 20L13 21L10 31Z" fill="#ff745a" stroke="#f6f0df" stroke-width="2.2"/></svg>';
      document.documentElement.append(pointer);
    },{once:true});
  },{ix:cx0,iy:cy0});
  const response=await page.goto(args.url,{waitUntil:'domcontentloaded'});
  if(response && !response.ok()) throw Error('网页响应 '+response.status());
  const steps = actions.map(action=>{
    if(!['wait','scroll','move','click','type','highlight'].includes(action.type)) throw Error('未知动作 '+action.type);
    const frames=Math.max(1,Math.round(Number(action.ms ?? 350)*fps/1000));
    if(!Number.isFinite(frames)) throw Error('动作时长无效');
    return {action,frames};
  });
  if(steps.reduce((n,s)=>n+s.frames,0)>Math.round(duration*fps)) throw Error('动作超出录屏时长');
  let start=0, index=0, origin, target, rect, scrollStart, scrollEnd, locator, frame=0;
  log(0,'start',{...position,w:1,h:1},1);
  await recordBrowserFrames(page,path.join(folder,'video.mp4'),{seconds:duration,fps,step:async()=>{
    const n=frame++;
    if(index>=steps.length) return;
    const {action:a,frames}=steps[index];
    const first=n===start,last=n===start+frames-1;
    if(first){
      origin={...position};
      locator=a.selector ? page.locator(a.selector).filter({visible:true}).first() :
        a.text && a.type!=='type' ? page.getByText(a.text).filter({visible:true}).first() : null;
      scrollStart=await page.evaluate(()=>scrollY);
      scrollEnd=scrollStart;
      if(locator){
        const box=await locator.boundingBox();
        if(!box) throw Error('目标不可见');
        scrollEnd=await page.evaluate(y=>Math.max(0,Math.min(document.documentElement.scrollHeight-innerHeight,y)),scrollStart+box.y+box.height/2-cy0);
        rect={x:box.x,y:box.y+scrollStart-scrollEnd,w:box.width,h:box.height};
        target={x:rect.x+rect.w/2,y:rect.y+rect.h/2};
      }else{
        target={x:a.x??position.x,y:a.y??position.y};rect={...target,w:1,h:1};
        if(a.type==='scroll') scrollEnd+=Number(a.dy);
      }
    }
    const progress=(n-start+1)/frames;
    const ease=progress*progress*(3-2*progress);
    position={x:origin.x+(target.x-origin.x)*ease,y:origin.y+(target.y-origin.y)*ease};
    await page.evaluate(({pos,y})=>{
      window.scrollTo({top:y,behavior:'instant'});
      document.getElementById('yice-capture-pointer').style.transform='translate('+pos.x+'px,'+pos.y+'px)';
    },{pos:position,y:scrollStart+(scrollEnd-scrollStart)*ease});
    if(a.type!=='wait') await page.mouse.move(position.x,position.y);
    if(last){
      if(a.type==='click'){
        await page.mouse.click(position.x,position.y);
        await page.evaluate(()=>{
          const el=document.getElementById('yice-capture-pointer');
          el.animate([{outline:'4px solid #fb5',borderRadius:'50%'},{outline:'16px solid transparent',borderRadius:'50%'}],450);
        });
      }
      if(a.type==='type') await locator.fill(a.text);
      if(a.type==='highlight') await locator.evaluate((el,color)=>{
        el.style.backgroundImage='linear-gradient('+color+','+color+')';
        el.style.backgroundRepeat='no-repeat';
        el.style.borderRadius='4px';
        el.animate([{backgroundSize:'0% 100%'},{backgroundSize:'100% 100%'}],{duration:330,fill:'forwards'});
      },a.color||'rgba(255,116,90,.34)');
      log(n/fps,a.type,rect,locator ? 1.55 : 1);
      index++;start=n+1;
    }else if(a.type==='move') log(n/fps,'move',rect,1.25);
  }});
  await page.screenshot({path:path.join(folder,'still.png')});
  fs.writeFileSync(path.join(folder,'cursor-track.json'),JSON.stringify({url:args.url,width:1920,height:1080,cssViewport:viewport,deviceScaleFactor:scale,colorScheme,fps,duration,events},null,2));
  const rel=path.relative(project,folder);
  const entry={id:args.id,kind:'web_cam_recording',sourceType:'web_capture',url:args.url,source:args.source||url.hostname,
    path:rel+'/video.mp4',stillPath:rel+'/still.png',trackPath:rel+'/cursor-track.json',scene:args.scene||'',
    sha256:createHash('sha256').update(fs.readFileSync(path.join(folder,'video.mp4'))).digest('hex'),
    capturedAt:new Date().toISOString(),license:'fair_use_commentary'};
  fs.appendFileSync(path.join(project,'asset-ledger.jsonl'),JSON.stringify(entry)+'\n');
  console.log(JSON.stringify(entry));
}catch(error){
  fs.rmSync(folder,{recursive:true,force:true});
  throw error;
}finally{await browser.close();}
