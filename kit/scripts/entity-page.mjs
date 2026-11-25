import path from 'node:path';
import fs from 'node:fs';
import {recordBrowserFrames} from './browser-frames.mjs';

export function publicUrl(value,base){
  try{const u=new URL(value,base);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)return null;u.hash='';return u.href;}catch{return null;}
}
export function pressPermission(text){
  return text.match(/.{0,100}(?:(?:available|provided|permitted|may be used|free to use).{0,100}(?:press|media|editorial)|(?:press|media|editorial) use|供媒体使用|媒体(?:可|可以)使用).{0,140}/i)?.[0]||null;
}
export function classifyLinks(links,site){
  const official=url=>{try{const a=new URL(url).hostname.replace(/^www\./,''),b=new URL(site).hostname.replace(/^www\./,'');return a===b||a.endsWith('.'+b);}catch{return false;}};
  const valid=links.map(l=>({...l,url:publicUrl(l.url,site)})).filter(l=>l.url);
  return {
    press:valid.filter(l=>official(l.url)&&/press|brand|media.?kit|newsroom|品牌资源|媒体资料/i.test(l.url+' '+l.text)),
    announcements:valid.filter(l=>official(l.url)&&/\/blog|\/news|\/index\/|\/changelog|\/releases/i.test(l.url)&&officialAnnouncement(l.url)),
    interactive:valid.filter(l=>(/\b(?:try|demo|playground)\b|试用|在线体验/i.test(l.text)||/\/(?:demo|playground|spaces)(?:\/|$)/i.test(new URL(l.url).pathname))&&!(/\/login|\/signup|\/sign-in/i.test(l.url))),
  };
}
export function officialAnnouncement(url){
  const u=new URL(url);
  // HF 的官方域也托管任意用户博客；不能把社区文章包装成官方公告。
  if(u.hostname==='huggingface.co'&&u.pathname.startsWith('/blog/'))return !/^\/blog\/(?:community|zh|en|de|fr|es|ja|ko)\/?$/.test(u.pathname)&&(/^\/blog\/[^/]+\/?$/.test(u.pathname)||/^\/blog\/huggingface\//.test(u.pathname));
  return true;
}
export function latestAnnouncement(links,site){
  const seen=new Set();const candidates=classifyLinks(links,site).announcements.filter(l=>{
    const u=new URL(l.url),parts=u.pathname.split('/').filter(Boolean);
    if(parts.length<2||seen.has(l.url)||!l.text.trim())return false;seen.add(l.url);return true;
  });
  const dateText=text=>(text||'').match(/\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b/i)?.[0];
  const dated=candidates.map(l=>({...l,date:l.date||dateText(l.text)||null})).filter(l=>Number.isFinite(Date.parse(l.date||''))).sort((a,b)=>Date.parse(b.date)-Date.parse(a.date));
  const chosen=dated[0]||candidates[0];return chosen?{...chosen,selection:dated.length?'latest_dated_on_official_listing':'first_listed_date_unverified'}:null;
}

export async function inspectEntityPage(page,{project,output,record=true}){
  const info=await page.evaluate(()=>{
    const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
    const absolute=src=>{try{return new URL(src,document.baseURI).href;}catch{return null;}};
    return {
      text:document.body.innerText.slice(0,35000),
      links:[...document.querySelectorAll('a[href]')].map(a=>({url:a.href,text:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,220),date:a.closest('article,li')?.querySelector('time')?.dateTime||null})).slice(0,350),
      images:[...document.images].map(i=>({url:i.currentSrc||i.src,canonicalUrl:i.getAttribute('data-canonical-src'),alt:i.alt,width:i.naturalWidth,height:i.naturalHeight,inReadme:!!i.closest('.markdown-body,article[itemprop="text"]')})).filter(i=>i.url).slice(0,100),
      readmeVideos:[...new Set([
        ...[...document.querySelectorAll('.markdown-body video,article video')].map(v=>
          v.currentSrc||v.getAttribute('src')||v.querySelector('source[src]')?.src||v.getAttribute('data-canonical-src')),
        ...[...document.querySelectorAll('.markdown-body a[href*="user-attachments/assets/"]')].map(a=>a.href),
      ].filter(Boolean).map(absolute).filter(Boolean))],
      logos:[...document.querySelectorAll('header img,nav img,img[alt*="logo" i],img[src*="logo" i],link[rel~="icon"]')].map(i=>({url:i.currentSrc||i.src||i.href,label:i.alt||'site icon'})).filter(i=>i.url),
      inlineLogos:[...document.querySelectorAll('header a[href="/"] svg,nav a[href="/"] svg,header svg[aria-label*="logo" i]')].slice(0,2).map(e=>({label:e.getAttribute('aria-label')||e.closest('a')?.getAttribute('aria-label')||'official header brand',svg:e.outerHTML})),
      inputs:[...document.querySelectorAll('textarea,input:not([type=hidden]):not([type=checkbox]):not([type=radio])')].filter(visible).map(e=>({type:e.type||e.tagName.toLowerCase(),placeholder:e.placeholder||e.getAttribute('aria-label')||'',formAction:e.form?.action||null})).slice(0,10),
      embeds:[...document.querySelectorAll('iframe')].map(i=>({url:i.src,title:i.title})).filter(i=>i.url),
      publishedAt:document.querySelector('meta[property="article:published_time"]')?.content||document.querySelector('article time')?.dateTime||null,
    };
  });
  info.sections=[];info.demos=[];
  if(!record)return info;
  const heads=page.locator('main h2,main h3,article h2,.markdown-body h2');
  let previousY=-Infinity;
  for(let i=0;i<await heads.count()&&info.sections.length<3;i++){
    const h=heads.nth(i);if(!await h.isVisible())continue;
    await h.evaluate(e=>window.scrollTo(0,window.scrollY+e.getBoundingClientRect().top-160));
    const y=await page.evaluate(()=>window.scrollY);if(Math.abs(y-previousY)<240)continue;previousY=y;
    const title=(await h.innerText()).trim();const file=path.join(output,`section-${i+1}.png`);
    await page.screenshot({path:file});info.sections.push({title,path:path.relative(project,file),box:await h.boundingBox()});
  }
  const demos=page.locator('main video,main img[src*=".gif" i],article video,.markdown-body img[src*=".gif" i]');
  const total=await demos.count();info.demoCount=total;
  for(let i=0;i<Math.min(total,6);i++){
    const el=demos.nth(i),entry={index:i,status:'skipped'};info.demos.push(entry);
    try{
      const b=await el.boundingBox();if(!b||b.width<160||b.height<90){entry.reason='small_or_hidden_media';continue;}
      await el.scrollIntoViewIfNeeded();
      const state=await el.evaluate(e=>({url:e.currentSrc||e.getAttribute('src')||e.querySelector('source[src]')?.src||e.getAttribute('data-canonical-src'),
        kind:e.tagName==='VIDEO'?'video':'gif'}));
      Object.assign(entry,state);
      const file=path.join(output,`demo-${i+1}.mp4`);
      const source=state.url&&publicUrl(state.url,page.url());
      if(state.kind==='video'&&source&&process.env.YICE_MEDIA_OFFLINE!=='1'){
        const {downloadEntityFile,normalizeDemoVideo}=await import('./collect-entity.mjs');
        let original;
        try{
          original=await downloadEntityFile(source,file+'-source',{allowVideo:true});
          if(!original.mime.startsWith('video/'))throw new Error('来源未返回视频');
          Object.assign(entry,normalizeDemoVideo(original.file,file),{status:'captured',path:path.relative(project,file),method:'direct_download'});
          continue;
        }catch(error){entry.directDownloadError=error.message;}
        finally{if(original?.file)fs.rmSync(original.file,{force:true});}
      }
      if(state.kind==='video'){
        entry.playing=await el.evaluate(async e=>{
          e.muted=true;
          await Promise.race([e.play().catch(()=>{}),new Promise(resolve=>setTimeout(resolve,1500))]);
          return !e.paused;
        });
        if(!entry.playing){entry.reason='page_player_requires_interaction';continue;}
      }
      Object.assign(entry,await recordBrowserFrames(page,file,{seconds:6,fps:30,realtime:true}),{status:'captured',path:path.relative(project,file),box:await el.boundingBox(),method:'browser_frames'});
    }catch(error){entry.reason=error.message;}
  }
  if(total>6)info.demoOmitted=total-6;
  return info;
}
