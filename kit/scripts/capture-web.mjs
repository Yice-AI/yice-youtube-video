#!/usr/bin/env node
// 公开页面实拍使用无登录浏览器上下文，逐帧推进滚动。
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {recordBrowserFrames} from './browser-frames.mjs';

export function wallReason({ status = 200, title = '', text = '', password = false }) {
  if (status >= 400) return `http_${status}`;
  if (/just a moment|verify.{0,25}human|access denied|checking your browser|正在进行安全验证|验证您不是自动程序|确认您是真人/i.test(title + '\n' + text.slice(0,1200))) return 'challenge';
  if (password || /(?:sign|log) in to (?:continue|read)|subscribe to (?:continue|read|unlock)|subscription required|订阅后(?:继续|阅读)|请登录后阅读/i.test(text)) return 'login_or_paywall';
  return null;
}

import {recordAsset} from '../template/asset-ledger.mjs';
export {recordAsset};

const DEFAULT_PLAYWRIGHT_MODULE = '/opt/homebrew/lib/node_modules/openclaw/node_modules/playwright-core';
const DEFAULT_CHROME_EXECUTABLE = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function preparePage(page) {
  await page.evaluate(async () => {
    const images = [...document.images];
    images.filter(img => img.loading === 'lazy').forEach(img => { img.loading = 'eager'; });
    function decodeVisible() {
      return Promise.allSettled(images.filter(img => {
        const box = img.getBoundingClientRect();
        return box.bottom > 0 && box.top < innerHeight;
      }).map(img => img.decode()));
    }
    const decoding = [decodeVisible()];
    try {
      for (const y of [800, 1600, 2400]) {
        window.scrollTo({top:y,behavior:'instant'});
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        decoding.push(decodeVisible());
      }
      await Promise.race([Promise.all(decoding),new Promise(resolve => setTimeout(resolve,1200))]);
    } finally {
      window.scrollTo({top:0,behavior:'instant'});
    }
  });
  await page.evaluate(() => {
    const marketing = '#intercom-container,.crisp-client,[id*="cookie" i],[class*="newsletter" i],iframe[title*="chat" i]';
    const dialog = '[role="dialog"],[aria-modal="true"],dialog[open]';
    for (const element of document.body.querySelectorAll('*')) {
      if (element.closest('header,nav') && !element.matches(dialog)) continue;
      const fixed = getComputedStyle(element).position === 'fixed';
      if (!fixed && !element.matches(dialog)) continue;
      const box = element.getBoundingClientRect();
      if (box.bottom <= 0 || box.top >= innerHeight || box.right <= 0 || box.left >= innerWidth) continue;
      const bottom = box.bottom >= innerHeight * .9 && box.top >= innerHeight * .45;
      const overlay = box.width >= innerWidth * .75 && box.height >= innerHeight * .45;
      if (element.matches(dialog) || element.matches(marketing) || bottom || overlay) {
        element.style.setProperty('visibility','hidden','important');
      }
    }
  });
}

export async function capturePage({ project, url, id = 'web-page', seconds = 7, scene = '', sourceName, highlight,
  license = '原页面权利人保留；短段引用，发布用途待核对', licenseUrl, details=false, scroll=true, scale=1.25, theme='auto' }) {
  const target = new URL(url);
  if (!['https:','http:'].includes(target.protocol) || target.username || target.password) throw new Error('只采集无账号信息的公开 HTTP(S) 页面');
  if (!/^[a-zA-Z0-9_-]+$/.test(id)) throw new Error('id 只用字母、数字、下划线和短横线');
  if (!Number.isFinite(seconds) || seconds < 6 || seconds > 8) throw new Error('滚动片段长度为 6–8 秒');
  if (!Number.isFinite(scale) || scale < 1 || scale > 2.5) throw new Error('scale 范围为 1–2.5');
  if (!['auto','dark','light'].includes(theme)) throw new Error('theme 只接受 auto、dark 或 light');
  project = path.resolve(project);
  const output = path.join(project, 'assets/web', id); fs.mkdirSync(output,{recursive:true});
  const require = createRequire(path.join(project, 'package.json'));
  const playwrightModule = process.env.YICE_PLAYWRIGHT_MODULE ||
    (fs.existsSync(DEFAULT_PLAYWRIGHT_MODULE) ? DEFAULT_PLAYWRIGHT_MODULE : 'playwright-core');
  const { chromium } = require(playwrightModule);
  const launch = { headless:true };
  if (process.env.YICE_CHROME_EXECUTABLE || fs.existsSync(DEFAULT_CHROME_EXECUTABLE)) launch.executablePath = process.env.YICE_CHROME_EXECUTABLE || DEFAULT_CHROME_EXECUTABLE;
  else launch.channel = 'chrome';
  const browser = await chromium.launch(launch);
  const result = { id, url, sourceName:sourceName || target.hostname, capturedAt:new Date().toISOString(),
    sourceType:'web_capture', scene, license, viewport:{width:1920,height:1080}, scale, seconds, fps:30, status:'failed' };
  try {
    const viewport = {width:Math.round(1920/scale),height:Math.round(1080/scale)};
    const context = await browser.newContext({viewport,deviceScaleFactor:scale,acceptDownloads:false,
      ...(theme==='auto'?{}:{colorScheme:theme})});
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    const response = await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForLoadState('networkidle',{timeout:5000}).catch(()=>{});
    const rejected = [];
    for (const frame of page.frames()) {
      const button = frame.getByRole('button',{name:/^(reject all|reject optional cookies|reject non-essential cookies|only necessary|necessary cookies only|decline optional cookies|全部拒绝|拒绝所有|仅必要|拒绝非必要.*)$/i}).first();
      if (await button.isVisible().catch(()=>false)) {
        const label=await button.innerText();
        try { await button.click({timeout:2000});rejected.push(label); } catch {}
      }
    }
    result.cookieAction = rejected.length ? {action:'reject_nonessential',buttons:rejected} : {action:'no_reject_button_found'};
    const state = {status:response?.status() || 0,title:await page.title(),text:await page.locator('body').innerText({timeout:5000}),
      password:await page.locator('input[type=password]:visible').count()>0};
    result.title = state.title; result.httpStatus = state.status; result.finalUrl = page.url();
    const reason = wallReason(state);
    if (reason) { result.status='skipped';result.reason=reason;return result; }
    await page.evaluate(()=>document.fonts.ready);
    await preparePage(page).catch(()=>{});
    if (highlight) {
      const heading=page.getByRole('heading',{name:highlight,exact:true}).first();
      const locator=await heading.count()?heading:page.getByText(highlight,{exact:false}).first();
      if (await locator.count()) {
        await locator.scrollIntoViewIfNeeded();
        const textBox=await locator.evaluate((element,quote)=>{
          const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT);
          let node;
          while(node=walker.nextNode()) {
            const start=node.textContent.indexOf(quote);if(start<0)continue;
            const range=document.createRange();range.setStart(node,start);range.setEnd(node,start+quote.length);
            const r=range.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};
          }
          return null;
        },highlight);
        const box = textBox || await locator.boundingBox();
        result.highlight={text:highlight,box:box && {x:box.x*1920/viewport.width,y:box.y*1080/viewport.height,
          width:box.width*1920/viewport.width,height:box.height*1080/viewport.height},precision:textBox?'text_range':'element',status:'located'};
      } else result.highlight={text:highlight,status:'not_found'};
    }
    result.scrollStart=await page.evaluate(()=>window.scrollY);
    let still=await page.screenshot();
    const size = still.readUInt32BE(16)===1920 && still.readUInt32BE(20)===1080 ? undefined : result.viewport;
    if(size) still=execFileSync('ffmpeg',['-v','error','-f','image2pipe','-i','pipe:0','-vf','scale=1920:1080',
      '-frames:v','1','-f','image2pipe','-c:v','png','pipe:1'],{input:still,maxBuffer:16*1024*1024});
    fs.writeFileSync(path.join(output,'still.png'),still);
    result.scrollPixels = await page.evaluate(()=>Math.max(0,document.documentElement.scrollHeight-innerHeight-window.scrollY));
    // 只滚动一个短片段，不把整篇长文变成录像。
    result.scrollPixels = Math.min(result.scrollPixels,2160);
    result.motion = result.scrollPixels ? 'smooth_scroll' : 'short_page_hold_no_scroll_range';
    if(scroll)await recordBrowserFrames(page,path.join(output,'scroll.mp4'),{seconds,fps:result.fps,size,step:async p=>{
      const ease=p*p*(3-2*p);
      await page.evaluate(y=>window.scrollTo({top:y,behavior:'instant'}),result.scrollStart+Math.round(result.scrollPixels*ease));
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    }});
    if(details){const {inspectEntityPage}=await import('./entity-page.mjs');result.details=await inspectEntityPage(page,{project,output,record:typeof details==='object'?details.record!==false:true});}
    result.status='captured';
    result.files=['still.png',...(scroll?['scroll.mp4']:[])].map(name=>({path:path.relative(project,path.join(output,name)),sha256:createHash('sha256').update(fs.readFileSync(path.join(output,name))).digest('hex')}));
    recordAsset(project,{...result,attribution:`${result.sourceName} · ${url} · ${result.capturedAt.slice(0,10)}`,licenseUrl:licenseUrl || url,approval:'editorial_review'});
    return result;
  } catch(error) {
    result.reason=error.message;return result;
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(output,'capture.json'),JSON.stringify(result,null,2)+'\n');
    if(result.status!=='captured') fs.rmSync(path.join(output,'scroll.mp4.part.mp4'),{force:true});
  }
}

export async function captureNeeds({ project, needs, capture = capturePage, scale, theme }) {
  const report={schemaVersion:1,items:[]};
  const items=Array.isArray(needs)?needs:needs.items;
  if(!Array.isArray(items)) throw new Error('需求单需要 items 数组');
  for(const item of items.filter(x=>x.type==='news_capture')) {
    const attempts=[];
    if(!Array.isArray(item.candidateUrls)||!item.candidateUrls.length) {
      report.items.push({id:item.id,status:'failed',reason:'缺少 candidateUrls'});continue;
    }
    for(const url of item.candidateUrls) {
      let result;
      try { result=await capture({project,url,id:item.id,scene:item.scene,sourceName:item.sourceName,
        seconds:item.capture?.seconds??7,highlight:item.capture?.highlight,license:item.license?.name,licenseUrl:item.license?.url,
        scale:item.capture?.scale??scale,theme:item.capture?.theme??theme}); }
      catch(error) { result={id:item.id,url,status:'failed',reason:error.message}; }
      attempts.push(result);if(result.status==='captured')break;
    }
    report.items.push({...attempts.at(-1),claim:item.claim,attempts});
  }
  report.captured=report.items.filter(x=>x.status==='captured').length;
  report.skipped=report.items.filter(x=>x.status==='skipped').length;
  report.failed=report.items.filter(x=>x.status==='failed').length;
  fs.mkdirSync(project,{recursive:true});fs.writeFileSync(path.join(project,'web-capture-report.json'),JSON.stringify(report,null,2)+'\n');
  return report;
}

if (process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) {
  const args=process.argv.slice(2), get=(key,fallback)=>{const i=args.indexOf(key);return i<0?fallback:args[i+1];};
  if (!get('--project') || (!get('--url')&&!get('--needs'))) throw new Error('用法：capture-web.mjs --project <每期目录> (--needs asset-needs.json | --url <公开URL>)');
  const scale=Number(get('--scale','1.25')), theme=get('--theme','auto');
  const result=get('--needs') ? await captureNeeds({project:path.resolve(get('--project')),needs:JSON.parse(fs.readFileSync(get('--needs'),'utf8')),scale,theme}) :
    await capturePage({project:get('--project'),url:get('--url'),id:get('--id','web-page'),seconds:Number(get('--seconds','7')),scene:get('--scene',''),sourceName:get('--source'),highlight:get('--highlight'),license:get('--license'),scale,theme});
  console.log(JSON.stringify(result,null,2));process.exitCode=result.status==='failed'||result.failed?1:0;
}
