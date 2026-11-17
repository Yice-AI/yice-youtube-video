#!/usr/bin/env node
// 公开页面实拍：新建无登录浏览器上下文，逐帧真实滚动，不下载页面中的视频。
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';

export function wallReason({ status = 200, title = '', text = '', password = false }) {
  if (status >= 400) return `http_${status}`;
  if (/just a moment|verify.{0,25}human|access denied|checking your browser|正在进行安全验证|验证您不是自动程序|确认您是真人/i.test(title + '\n' + text.slice(0,1200))) return 'challenge';
  if (password || /(?:sign|log) in to (?:continue|read)|subscribe to (?:continue|read|unlock)|subscription required|订阅后(?:继续|阅读)|请登录后阅读/i.test(text)) return 'login_or_paywall';
  return null;
}

export function recordAsset(project, entry) {
  const file=path.join(project,'asset-ledger.jsonl');
  const rows=fs.existsSync(file)?fs.readFileSync(file,'utf8').split('\n').filter(Boolean).map(JSON.parse):[];
  const text=[...rows.filter(row=>row.id!==entry.id),entry].map(row=>JSON.stringify(row)).join('\n')+'\n';
  fs.writeFileSync(file+'.tmp',text);fs.renameSync(file+'.tmp',file);
}

export async function capturePage({ project, url, id = 'web-page', seconds = 7, scene = '', sourceName, highlight,
  license = '原页面权利人保留；短段引用，发布用途待核对', licenseUrl }) {
  const target = new URL(url);
  if (!['https:','http:'].includes(target.protocol) || target.username || target.password) throw new Error('只采集无账号信息的公开 HTTP(S) 页面');
  if (!/^[a-zA-Z0-9_-]+$/.test(id)) throw new Error('id 只用字母、数字、下划线和短横线');
  if (!Number.isFinite(seconds) || seconds < 6 || seconds > 8) throw new Error('滚动片段长度为 6–8 秒');
  project = path.resolve(project);
  const output = path.join(project, 'assets/web', id); fs.mkdirSync(output,{recursive:true});
  const require = createRequire(path.join(project, 'package.json'));
  const { chromium } = require(process.env.YICE_PLAYWRIGHT_MODULE || 'playwright-core');
  const launch = { headless:true };
  if (process.env.YICE_CHROME_EXECUTABLE) launch.executablePath = process.env.YICE_CHROME_EXECUTABLE;
  else launch.channel = 'chrome';
  const browser = await chromium.launch(launch);
  const result = { id, url, sourceName:sourceName || target.hostname, capturedAt:new Date().toISOString(),
    sourceType:'web_capture', scene, license, viewport:{width:1920,height:1080}, seconds, fps:15, status:'failed' };
  let encoder;
  try {
    const context = await browser.newContext({viewport:result.viewport,deviceScaleFactor:1,acceptDownloads:false});
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
    await page.evaluate(()=>window.scrollTo(0,0));
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
        result.highlight={text:highlight,box:textBox||await locator.boundingBox(),precision:textBox?'text_range':'element',status:'located'};
      } else result.highlight={text:highlight,status:'not_found'};
    }
    result.scrollStart=await page.evaluate(()=>window.scrollY);
    await page.screenshot({path:path.join(output,'still.png')});
    result.scrollPixels = await page.evaluate(()=>Math.max(0,document.documentElement.scrollHeight-innerHeight-window.scrollY));
    // 只滚动一个短片段，不把整篇长文变成录像。
    result.scrollPixels = Math.min(result.scrollPixels,2160);
    result.motion = result.scrollPixels ? 'smooth_scroll' : 'short_page_hold_no_scroll_range';
    const part = path.join(output,'scroll.part.mp4');
    let stderr='', pipeError;
    encoder=spawn('ffmpeg',['-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate','15','-i','pipe:0',
      '-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',part],{stdio:['pipe','ignore','pipe']});
    encoder.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-2000);});
    encoder.stdin.on('error',error=>{pipeError=error;});
    const closed = new Promise((resolve,reject)=>{encoder.once('error',reject);encoder.once('close',code=>code===0?resolve():reject(new Error(stderr || `ffmpeg退出${code}`)));});
    // 给提前失败的编码器挂处理器，循环最终仍会抛出原始错误。
    closed.catch(()=>{});
    for (let frame=0;frame<seconds*15;frame++) {
      const p=frame/(seconds*15-1), ease=p*p*(3-2*p);
      if(pipeError) throw pipeError;
      await page.evaluate(y=>window.scrollTo(0,y),result.scrollStart+Math.round(result.scrollPixels*ease));
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const pixels=await page.screenshot();
      if (!encoder.stdin.write(pixels)) await once(encoder.stdin,'drain');
    }
    encoder.stdin.end();await closed;
    fs.renameSync(part,path.join(output,'scroll.mp4'));
    result.status='captured';
    result.files=['still.png','scroll.mp4'].map(name=>({path:path.relative(project,path.join(output,name)),sha256:createHash('sha256').update(fs.readFileSync(path.join(output,name))).digest('hex')}));
    recordAsset(project,{...result,attribution:`${result.sourceName} · ${url} · ${result.capturedAt.slice(0,10)}`,licenseUrl:licenseUrl || url,approval:'editorial_review'});
    return result;
  } catch(error) {
    encoder?.kill();result.reason=error.message;return result;
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(output,'capture.json'),JSON.stringify(result,null,2)+'\n');
    if(result.status!=='captured') fs.rmSync(path.join(output,'scroll.part.mp4'),{force:true});
  }
}

export async function captureNeeds({ project, needs, capture = capturePage }) {
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
        seconds:item.capture?.seconds??7,highlight:item.capture?.highlight,license:item.license?.name,licenseUrl:item.license?.url}); }
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
  const result=get('--needs') ? await captureNeeds({project:path.resolve(get('--project')),needs:JSON.parse(fs.readFileSync(get('--needs'),'utf8'))}) :
    await capturePage({project:get('--project'),url:get('--url'),id:get('--id','web-page'),seconds:Number(get('--seconds','7')),scene:get('--scene',''),sourceName:get('--source'),highlight:get('--highlight'),license:get('--license')});
  console.log(JSON.stringify(result,null,2));process.exitCode=result.status==='failed'||result.failed?1:0;
}
