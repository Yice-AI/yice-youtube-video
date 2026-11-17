#!/usr/bin/env node
// Commons / Openverse 匿名素材入口；只下载许可和署名完整的一件素材。
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { recordAsset, wallReason } from './capture-web.mjs';

const UA='YiceVideoToolkit/0.1 (public media research)';
const MAX_BYTES=25*1024*1024;
const plain=text=>String(text||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();

export function licenseUrlKey(url) {
  try {
    const u=new URL(url);
    if(!['https:','http:'].includes(u.protocol)||u.username||u.password||! /^(?:www\.)?creativecommons\.org$/.test(u.hostname)) return null;
    const match=u.pathname.match(/^\/(licenses\/(?:by|by-sa)\/[\d.]+|publicdomain\/(?:zero|mark)\/[\d.]+)(?:\/(?:deed|legalcode)(?:\.[a-zA-Z_-]+)?)?\/?$/);
    return match?`https://creativecommons.org/${match[1]}/`:null;
  } catch {return null;}
}

export function licenseAllowed(url) {
  return licenseUrlKey(url)!==null;
}

function publicUrl(value) {
  const u=new URL(value);
  if(!['https:','http:'].includes(u.protocol)||u.username||u.password||
    /^(localhost|127\.|10\.|192\.168\.|169\.254\.|\[::1\])/i.test(u.hostname)) throw new Error('素材来源必须是公开 HTTP(S) URL');
  return u.href;
}

async function request(url) {
  const response=await fetch(publicUrl(url),{headers:{'User-Agent':UA},signal:AbortSignal.timeout(25000)});
  if(!response.ok)throw new Error(`HTTP ${response.status} ${new URL(url).hostname}`);
  return response;
}

export function commonsCandidates(data) {
  return Object.values(data.query?.pages||{}).flatMap(page=>{
    const info=page.imageinfo?.[0];if(!info)return [];
    const meta=info.extmetadata||{}, get=key=>plain(meta[key]?.value);
    return [{provider:'commons',title:page.title.replace(/^File:/,''),sourceUrl:info.descriptionurl,
      downloadUrl:info.mime?.startsWith('image/')?(info.thumburl||info.url):info.url,originalUrl:info.url,
      mime:info.thumburl?(info.thumbmime||info.mime):info.mime,bytes:info.size,creator:get('Artist'),
      license:get('LicenseShortName')||get('UsageTerms'),licenseUrl:get('LicenseUrl'),
      licenseEvidence:{method:'Commons imageinfo extmetadata',pageId:page.pageid,metadata:meta}}];
  });
}

export function openverseCandidates(data) {
  return (data.results||[]).map(item=>({provider:'openverse',title:item.title,sourceUrl:item.foreign_landing_url,
    downloadUrl:item.url,originalUrl:item.url,creator:plain(item.creator),creatorUrl:item.creator_url,
    license:`CC ${String(item.license||'').toUpperCase()} ${item.license_version||''}`.trim(),licenseUrl:item.license_url,
    licenseEvidence:{method:'Openverse API metadata; primary-page verification required',id:item.id,source:item.source}}));
}

async function filePage(page,url) {
  const response=await page.goto(publicUrl(url),{waitUntil:'domcontentloaded',timeout:30000});
  const text=await page.locator('body').innerText();
  const reason=wallReason({status:response?.status(),title:await page.title(),text});
  if(reason)throw new Error(reason);
  return page.evaluate(()=>{
    const licenseLinks=[...document.querySelectorAll('.licensetpl a[href], a[rel="license"]')].map(a=>a.href);
    const author=document.querySelector('#fileinfotpl_aut')?.nextElementSibling;
    return {title:document.querySelector('h1')?.innerText.replace(/^File:/,''),sourceUrl:location.href,
      downloadUrl:document.querySelector('.fullImageLink a')?.href||document.querySelector('.fullMedia a.internal')?.href,
      creator:author?.innerText.trim()||document.querySelector('.licensetpl_aut')?.textContent.trim(),
      licenseLinks,licenseText:document.querySelector('.licensetpl')?.innerText.slice(0,2500),
      fileInfo:document.querySelector('.fullMedia')?.innerText.slice(0,500)};
  });
}

async function browserSearch(provider,query,limit,browser) {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const url=provider==='commons' ? 'https://commons.wikimedia.org/w/index.php?'+new URLSearchParams({search:query,title:'Special:Search',ns6:'1'}) :
    'https://openverse.org/search/image?'+new URLSearchParams({q:query,license:'cc0,by,by-sa,pdm'});
  try {
    const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForLoadState('networkidle',{timeout:5000}).catch(()=>{});
    const text=await page.locator('body').innerText(),title=await page.title();
    const reason=wallReason({status:response?.status(),title,text});
    if(reason)throw new Error(`${reason}；公开搜索页不可访问，不登录、不绕过验证`);
    const links=await page.evaluate(provider=>[...new Set([...document.querySelectorAll(provider==='commons'?'.mw-search-result-heading a':'a[href*="/image/"]')].map(a=>a.href))],provider);
    const items=[];
    for(const sourceUrl of links.slice(0,limit)) {
      try {
        if(provider==='commons') {
          const file=await filePage(page,sourceUrl),licenseUrl=file.licenseLinks.find(licenseAllowed);
          items.push({...file,provider,licenseUrl,license:licenseUrl?new URL(licenseUrl).pathname:'unknown',licenseEvidence:{method:'Commons public file page',text:file.licenseText}});
        } else {
          await page.goto(sourceUrl,{waitUntil:'domcontentloaded',timeout:30000});
          const item=await page.evaluate(()=>({title:document.querySelector('h1')?.innerText,
            sourceUrl:[...document.querySelectorAll('a[href]')].find(a=>/visit source|source page|来源/i.test(a.innerText))?.href,
            downloadUrl:document.querySelector('a[download]')?.href,
            creator:document.querySelector('[data-testid="attribution-creator"]')?.textContent,
            licenseLinks:[...document.querySelectorAll('a[href*="creativecommons.org"]')].map(a=>a.href)}));
          const licenseUrl=item.licenseLinks.find(licenseAllowed);
          items.push({...item,provider,licenseUrl,license:licenseUrl?new URL(licenseUrl).pathname:'unknown',licenseEvidence:{method:'Openverse public item page',itemUrl:sourceUrl}});
        }
      }catch(error){items.push({provider,sourceUrl,error:error.message});}
    }
    return {items,url,method:'public_browser_search'};
  }finally{await page.close();}
}

export async function downloadAsset({project,candidate,scene='',requestFn=request}) {
  if(!licenseAllowed(candidate.licenseUrl))throw new Error('不是已核验的 CC BY / BY-SA / CC0 / 公有领域许可');
  if(!candidate.creator)throw new Error('缺少作者/署名，不下载');
  if(!candidate.sourceUrl||!candidate.downloadUrl)throw new Error('缺少原始来源页或文件直链');
  if(candidate.bytes>MAX_BYTES)throw new Error('素材超过25MiB，本次跳过');
  const response=await requestFn(publicUrl(candidate.downloadUrl));
  const mime=(response.headers.get('content-type')||'').split(';')[0];
  if(!/^(image|video)\//.test(mime))throw new Error(`下载不是图/视频：${mime}`);
  const advertised=Number(response.headers.get('content-length'));
  if(advertised>MAX_BYTES)throw new Error('素材超过25MiB，本次跳过');
  const chunks=[];let count=0;
  for await(const chunk of response.body){count+=chunk.length;if(count>MAX_BYTES)throw new Error('素材超过25MiB，本次跳过');chunks.push(Buffer.from(chunk));}
  const data=Buffer.concat(chunks);if(!data.length)throw new Error('下载为空');
  const sha256=createHash('sha256').update(data).digest('hex');
  const extension=({'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/svg+xml':'svg','image/gif':'gif','video/webm':'webm','video/mp4':'mp4','video/ogg':'ogv'})[mime];
  if(!extension)throw new Error(`暂未支持的媒体格式 ${mime}`);
  const id=`${candidate.provider}-${sha256.slice(0,12)}`,relative=`assets/open/${id}.${extension}`;
  fs.mkdirSync(path.join(project,'assets/open'),{recursive:true});fs.writeFileSync(path.join(project,relative),data);
  const entry={...candidate,id,type:mime.startsWith('video/')?'video':'image',sourceType:'third_party',path:relative,sha256,bytes:data.length,mime,
    capturedAt:new Date().toISOString(),scene,attribution:`${candidate.title} — ${candidate.creator} · ${candidate.license} · ${candidate.licenseUrl} · ${candidate.sourceUrl}`,
    approval:'license_metadata_recorded',rightsNote:'署名与许可随成片保留；人物/商标等其他权利按使用语境核对'};
  recordAsset(project,entry);return entry;
}

export async function collectOpenMedia({provider,query,project,scene='',limit=5}) {
  if(!['commons','openverse'].includes(provider))throw new Error('provider 只能为 commons 或 openverse');
  project=path.resolve(project);fs.mkdirSync(project,{recursive:true});
  const report={provider,query,at:new Date().toISOString(),status:'failed',attempts:[]};
  let candidates=[],browser;
  const getBrowser=async()=>{
    if(browser)return browser;
    const require=createRequire(path.join(project,'package.json')),{chromium}=require(process.env.YICE_PLAYWRIGHT_MODULE||'playwright-core');
    browser=await chromium.launch({headless:true,...(process.env.YICE_CHROME_EXECUTABLE?{executablePath:process.env.YICE_CHROME_EXECUTABLE}:{channel:'chrome'})});return browser;
  };
  try {
    const api=provider==='commons' ? 'https://commons.wikimedia.org/w/api.php?'+new URLSearchParams({action:'query',format:'json',generator:'search',gsrsearch:query,gsrnamespace:'6',gsrlimit:String(limit),prop:'imageinfo',iiprop:'url|size|mime|extmetadata|thumbmime',iiurlwidth:'1600'}) :
      'https://api.openverse.org/v1/images/?'+new URLSearchParams({q:query,page_size:String(limit),license:'cc0,by,by-sa,pdm'});
    report.searchUrl=api;
    try{const data=await (await request(api)).json();candidates=provider==='commons'?commonsCandidates(data):openverseCandidates(data);report.method='anonymous_api';}
    catch(error){
      report.apiError=error.message;
      const fallback=await browserSearch(provider,query,limit,await getBrowser());candidates=fallback.items;report.method=fallback.method;report.publicSearchUrl=fallback.url;
    }
    report.candidates=candidates;
    for(let candidate of candidates) {
      try {
        if(candidate.error)throw new Error(candidate.error);
        if(provider==='openverse') {
          const page=await (await getBrowser()).newPage();
          try {
            if(new URL(candidate.sourceUrl).hostname==='commons.wikimedia.org') {
              const verified=await filePage(page,candidate.sourceUrl);const licenseUrl=verified.licenseLinks.find(licenseAllowed);
              candidate={...candidate,...verified,licenseUrl,license:licenseUrl?new URL(licenseUrl).pathname:'unknown',licenseEvidence:{method:'Openverse discovery + Commons primary file page',text:verified.licenseText}};
            }else{
              const response=await page.goto(publicUrl(candidate.sourceUrl),{waitUntil:'domcontentloaded',timeout:25000});
              if(response.status()>=400)throw new Error('原来源页不可访问，不能核对许可');
              const links=await page.locator('a[href*="creativecommons.org"]').evaluateAll(nodes=>nodes.map(n=>n.href));
              if(!licenseAllowed(candidate.licenseUrl)||!links.some(url=>licenseUrlKey(url)===licenseUrlKey(candidate.licenseUrl)))throw new Error('原来源页没有匹配的许可链接');
              candidate.licenseEvidence={...candidate.licenseEvidence,primaryLicenseLinkVerified:true};
            }
          }finally{await page.close();}
        }
        const entry=await downloadAsset({project,candidate,scene});report.asset=entry;report.status='downloaded';break;
      }catch(error){report.attempts.push({title:candidate.title,sourceUrl:candidate.sourceUrl,reason:error.message});}
    }
    if(report.status!=='downloaded')report.reason='没有可下载且许可/署名完整的候选';
  }catch(error){report.status=/HTTP 40[13]|http_40[13]|challenge|验证/.test(error.message)?'skipped':'failed';report.reason=error.message;}
  finally{
    await browser?.close();
    fs.writeFileSync(path.join(project,`open-media-${provider}-report.json`),JSON.stringify(report,null,2)+'\n');
  }
  return report;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  const args=process.argv.slice(2),get=key=>args[args.indexOf(key)+1];
  if(!args.includes('--provider')||!args.includes('--query')||!args.includes('--project'))throw new Error('用法：open-media.mjs --provider commons|openverse --query 关键词 --project 每期目录 [--scene S1]');
  const result=await collectOpenMedia({provider:get('--provider'),query:get('--query'),project:get('--project'),scene:args.includes('--scene')?get('--scene'):''});
  console.log(JSON.stringify(result,null,2));process.exitCode=result.status==='failed'?1:0;
}
