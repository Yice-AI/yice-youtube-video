#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {capturePage} from './capture-web.mjs';
import {publicUrl,pressPermission,classifyLinks,latestAnnouncement} from './entity-page.mjs';
import {recordAsset} from '../template/asset-ledger.mjs';
import {candidateSheet} from './find-media.mjs';

const DEFAULT_PLAYWRIGHT_MODULE = '/opt/homebrew/lib/node_modules/openclaw/node_modules/playwright-core';
const DEFAULT_CHROME_EXECUTABLE = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if (!process.env.YICE_PLAYWRIGHT_MODULE && fs.existsSync(DEFAULT_PLAYWRIGHT_MODULE)) process.env.YICE_PLAYWRIGHT_MODULE = DEFAULT_PLAYWRIGHT_MODULE;
if (!process.env.YICE_CHROME_EXECUTABLE && fs.existsSync(DEFAULT_CHROME_EXECUTABLE)) process.env.YICE_CHROME_EXECUTABLE = DEFAULT_CHROME_EXECUTABLE;

const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const editorial='原页面/素材权利人保留；仅用于有来源的正文评论或产品说明，不作为公有领域素材。';
export const slug=value=>value.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g,'-').replace(/^-|-$/g,'')||'entity';
export function chooseLogoSource(details,site){
  return (details.logos||[]).map(l=>({...l,url:publicUrl(l.url,site)})).filter(l=>l.url&&!/onetrust|cookielaw|powered by/i.test(l.url+' '+l.label)).sort((a,b)=>{
    const score=l=>(new URL(l.url).hostname===new URL(site).hostname?10:0)+(/\.svg(?:[?#]|$)/i.test(l.url)?5:0)+(/\.png(?:[?#]|$)/i.test(l.url)?2:0)-(/\.ico(?:[?#]|$)/i.test(l.url)?10:0);
    return score(b)-score(a);
  })[0]?.url;
}
export function validateEntity({name,site,github,press}){
  if(typeof name!=='string'||!name.trim())throw new Error('需要 --name');
  if(!site&&!github&&!press)throw new Error('至少提供 --site / --github / --press 一个公开来源');
  for(const u of [site,press].filter(Boolean))if(!publicUrl(u))throw new Error('只接受不含账号信息的 HTTP(S) URL');
  if(github&&!/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(github))throw new Error('--github 使用 owner/repo');
}
export function harnessDraft(name,entries,out){
  return '# '+name+' · 交互录屏草稿（未派发）\n\n由中心审核后再派给 Harness；本工具不写 dsh-inbox。\n\n'+entries.map((e,i)=>
    `## 镜头 ${i+1}\n\n入口：${e.url}\n看什么：${e.label||'产品从输入到输出的真实变化'}。\n怎么操作：先确认可匿名访问；在页面允许的演示入口输入一项合成示例，停留在可辨认的结果上。若需登录、付费或遇自动访问限制，停止并回报。\n时长：8–12 秒，1920×1080，静音，开头与结果各留 1 秒。\n交到：${path.join(out,'harness-incoming',String(i+1).padStart(2,'0')+'.mp4')}，附实际操作说明和来源。\n`
  ).join('\n')+(entries.length?'':'未发现可确认的在线交互入口；不凭空生成操作步骤。\n');
}

export async function downloadEntityFile(url,file,{fetchFn=fetch,maxBytes=40*1024*1024,allowVideo=false}={}){
  if(!publicUrl(url))throw new Error('媒体地址必须为公开 HTTP(S) URL');
  if(fetchFn===fetch&&process.env.YICE_MEDIA_OFFLINE==='1')throw new Error('离线测试不访问网络');
  const response=await fetchFn(url,{signal:AbortSignal.timeout(25000)});
  if(!response.ok)throw new Error(`http_${response.status}`);
  let mime=(response.headers.get('content-type')||'').split(';')[0].trim().toLowerCase();
  const videoMime={'video/mp4':'.mp4','video/webm':'.webm','video/quicktime':'.mov'};
  const probeVideo=allowVideo&&!videoMime[mime]&&(mime==='application/octet-stream'||mime.startsWith('video/'));
  if(!mime.startsWith('image/')&&!(allowVideo&&(videoMime[mime]||probeVideo)))throw new Error(allowVideo?'来源未返回图片或视频':'来源未返回图片');
  if(Number(response.headers.get('content-length'))>maxBytes)throw new Error('素材超过下载上限');
  const chunks=[];let size=0;
  for await(const chunk of response.body){size+=chunk.length;if(size>maxBytes)throw new Error('素材超过下载上限');chunks.push(chunk);}
  const bytes=Buffer.concat(chunks);
  if(probeVideo){
    if(bytes.toString('ascii',4,8)==='ftyp')mime='video/mp4';
    else if(bytes.subarray(0,4).equals(Buffer.from([0x1a,0x45,0xdf,0xa3]))&&bytes.subarray(0,256).includes('webm'))mime='video/webm';
    else throw new Error('来源未返回可识别的视频');
  }
  const ext=videoMime[mime]||({'image/svg+xml':'.svg','image/png':'.png','image/gif':'.gif','image/webp':'.webp','image/jpeg':'.jpg','image/x-icon':'.ico'})[mime]||'.img';
  const target=file+ext;fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,bytes);
  return {file:target,mime,bytes:bytes.length,sha256:sha(bytes)};
}

export function normalizeDemoVideo(inputFile,targetMp4,{maxSeconds=6}={}){
  const part=targetMp4+'.part.mp4';
  try{
    execFileSync('ffmpeg',['-v','error','-y','-i',inputFile,'-map','0:v:0','-t',String(maxSeconds),'-an',
      '-vf','scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:0x172322,setsar=1,fps=30',
      '-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',part],{timeout:30000});
    const seconds=Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','csv=p=0',part],{encoding:'utf8',timeout:5000}));
    if(!Number.isFinite(seconds)||seconds<=0)throw new Error('演示视频没有有效画面');
    fs.renameSync(part,targetMp4);
    return {seconds,fps:30,width:1920,height:1080,audio:false};
  }finally{fs.rmSync(part,{force:true});}
}

export async function resolveEntityLogo({project,name,source,site}){
  const cli=process.env.YICE_HYPERFRAMES_CLI;
  const command=cli?'node':'npx',prefix=cli?[cli]:['--no-install','hyperframes'];
  const args=['media-use','resolve','--type','logo','--entity',name,'--intent',name+' official brand mark','--project',project,'--json'];
  execFileSync(command,[...prefix,...args,'--candidates'],{encoding:'utf8',timeout:60000,maxBuffer:2*1024*1024,env:{...process.env,DO_NOT_TRACK:'1'}});
  // 页面明确的官方文件优先，避免把其他公司的全局缓存当作该实体 logo。
  const raw=execFileSync(command,[...prefix,...args,...(source?['--from',source]:[])],{encoding:'utf8',timeout:90000,maxBuffer:2*1024*1024,env:{...process.env,DO_NOT_TRACK:'1'}});
  const result=JSON.parse(raw),asset=result.asset||result.result||result;
  const ledger=path.join(project,'.media/manifest.jsonl');
  const rows=fs.existsSync(ledger)?fs.readFileSync(ledger,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse):[];
  const record=rows.at(-1)||asset;const candidate=asset.path||asset.localPath||record.path||record.localPath;
  if(!candidate)throw new Error('media-use 未返回冻结后的文件路径');
  const file=path.resolve(project,candidate);if(!fs.existsSync(file))throw new Error('media-use 输出文件不存在');
  return {path:path.relative(project,file),sha256:sha(fs.readFileSync(file)),url:source&&publicUrl(source)?source:site,provider:'media-use',provenance:record.provenance||null};
}

export async function entityOverview(manifest,project){
  const previewDir=path.join(project,'overview-previews');fs.mkdirSync(previewDir,{recursive:true});
  const candidates=[];
  for(const item of manifest.items){
    let file=item.path&&path.resolve(project,item.path);
    if(file&&/\.mp4$/i.test(file)){
      const still=path.join(previewDir,item.id+'.jpg');
      try{execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-ss','0.2','-i',file,'-frames:v','1',still],{timeout:20000});file=still;}catch{file=null;}
    }
    candidates.push({id:item.id,title:item.title||item.type,provider:item.status,creator:manifest.name,license:item.status==='captured'?item.license||'':'跳过：'+(item.reason||'无可用素材'),width:item.width||null,height:item.height||null,type:item.path?.endsWith('.mp4')?'video':'photo',durationSeconds:item.seconds||null,thumbnailUrl:file?'local:'+file:null});
  }
  await candidateSheet({query:manifest.name,candidates},project,{title:manifest.name+' · 实体素材总览',imageName:'overview.png',jsonName:null,requestFn:async url=>{
    const file=url.slice(6),ext=path.extname(file);return new Response(fs.readFileSync(file),{headers:{'content-type':ext==='.svg'?'image/svg+xml':ext==='.png'?'image/png':ext==='.gif'?'image/gif':ext==='.webp'?'image/webp':'image/jpeg'}});
  }});
}

export async function collectEntity(options,{capture=capturePage,download=downloadEntityFile,logo=resolveEntityLogo,overview=entityOverview}={}){
  validateEntity(options);const {name,site,github,press}=options;
  const project=path.resolve(options.out||path.join('entities',slug(name)));fs.mkdirSync(project,{recursive:true});
  const manifest={schemaVersion:1,name,site:site||null,github:github||null,press:press||null,capturedAt:new Date().toISOString(),items:[],interactive:[],warnings:[],harnessDispatched:false};
  function add(entry){
    const item={capturedAt:new Date().toISOString(),usage:'正文来源证据',license:editorial,...entry};
    if(item.path&&fs.existsSync(path.resolve(project,item.path)))item.sha256=sha(fs.readFileSync(path.resolve(project,item.path)));
    manifest.items.push(item);
    if(item.status==='captured')recordAsset(project,{...item,sourceType:item.type,sourceUrl:item.url,sourceName:name,licenseUrl:item.licenseUrl||item.url,approval:'editorial_review',files:item.path?[{path:item.path,sha256:item.sha256}]:[]});
    return item;
  }
  async function page(kind,url,{scroll=false,record=false}={}){
    let result;
    try{result=await capture({project,url,id:kind,sourceName:name,seconds:8,scroll,details:{record},license:editorial});}
    catch(error){result={status:'failed',reason:error.message};}
    if(result.status!=='captured'){add({id:kind,type:kind,url,status:result.status||'failed',reason:result.reason});return result;}
    for(const file of result.files||[])add({id:kind+(file.path.endsWith('.mp4')?'-scroll':'-hero'),type:file.path.endsWith('.mp4')?'official_scroll':kind,url:result.finalUrl||url,path:file.path,status:'captured',title:result.title,width:1920,height:1080,...(file.path.endsWith('.mp4')?{seconds:8,audio:false}:{})});
    for(const [i,section]of (result.details?.sections||[]).entries())add({id:kind+'-section-'+(i+1),type:'official_section',url,path:section.path,status:'captured',title:section.title,focusBox:section.box,width:1920,height:1080});
    for(const [i,demo]of (result.details?.demos||[]).entries())add({id:kind+'-demo-'+(i+1),type:'official_demo',url,mediaUrl:publicUrl(demo.url)||null,path:demo.path,status:demo.status,reason:demo.reason,seconds:demo.seconds??6,audio:false,usage:'来源：官网；采集至多6秒供剪辑，成片引用≤5秒、静音，仅评论语境'});
    if(result.details?.demoOmitted)manifest.warnings.push(`${kind}: ${result.details.demoOmitted} 个额外演示未录制，保留页面供后续选镜。`);
    const links=classifyLinks(result.details?.links||[],site||url);
    manifest.interactive.push(...links.interactive.map(l=>({url:l.url,label:l.text,sourcePage:url})),...(result.details?.embeds||[]).filter(e=>/hf\.space|huggingface.co\/spaces|demo|playground/i.test(e.url)).map(e=>({url:e.url,label:e.title,sourcePage:url})));
    if(result.details?.inputs?.some(i=>/text|textarea|search/.test(i.type)&&!/newsletter|subscribe|email|邮箱/i.test(i.placeholder)))manifest.interactive.push({url,label:'页面可输入区域；需核实是产品演示还是站内搜索',sourcePage:url,verification:'needs_human_review'});
    return result;
  }
  const home=site?await page('site',site,{scroll:true,record:true}):null;
  const homeDetails=home?.details||{},homeLinks=classifyLinks(homeDetails.links||[],site||press||'https://github.com');
  if(home?.status==='captured'){
    try{
      let source=chooseLogoSource(homeDetails,site);
      const inline=homeDetails.inlineLogos?.[0];
      if(inline?.svg){const file=path.join(project,'official-header-logo.svg');let svg=inline.svg;if(!/xmlns=/.test(svg))svg=svg.replace('<svg','<svg xmlns="http://www.w3.org/2000/svg"');fs.writeFileSync(file,svg);source=file;}
      const result=await logo({project,name,source,site});add({id:'logo',type:'official_logo',status:'captured',...result,usage:'品牌识别；按品牌规则使用，不暗示代言',license:'官方品牌标志；商标及版权归权利人，非PD。'});
    }catch(error){add({id:'logo',type:'official_logo',url:site,status:'skipped',reason:error.message});}
  }else add({id:'logo',type:'official_logo',url:site||null,status:'skipped',reason:'官网未能访问，无法核对官方标志来源'});
  const pressUrl=press||homeLinks.press[0]?.url;
  if(pressUrl){
    const release=await page('press',pressUrl),permission=pressPermission(release.details?.text||'');
    if(permission){
      const images=(release.details?.images||[]).filter(i=>i.width>=320&&i.height>=180&&!/avatar|logo|icon/i.test(i.alt)).slice(0,8);
      for(const [i,img]of images.entries()){
        const id='press-image-'+(i+1);
        try{const file=await download(publicUrl(img.url,pressUrl),path.join(project,'downloads',id));add({id,type:'press_image',status:'captured',url:pressUrl,mediaUrl:img.url,path:path.relative(project,file.file),title:img.alt,license:'媒体使用声明：'+permission,licenseUrl:pressUrl});}
        catch(error){add({id,type:'press_image',status:'skipped',url:pressUrl,reason:error.message});}
      }
      if(!images.length)add({id:'press-images',type:'press_image',status:'skipped',url:pressUrl,reason:'媒体使用声明存在，但未找到产品图片'});
    }else add({id:'press-images',type:'press_image',status:'skipped',url:pressUrl,reason:'页面未明确声明图片可供媒体使用，未下载'});
  }else add({id:'press',type:'press_kit',status:'skipped',url:site||null,reason:'未发现官方媒体资料入口'});
  if(github){
    const url='https://github.com/'+github,repo=await page('github',url,{record:true});
    const gifs=(repo.details?.images||[]).filter(i=>i.inReadme&&/\.gif(?:[?#]|$)/i.test(i.canonicalUrl||i.url));
    for(const [i,img]of gifs.entries()){
      const id='github-gif-'+(i+1),src=publicUrl(img.canonicalUrl||img.url,url);
      try{const file=await download(src,path.join(project,'downloads',id));if(file.mime!=='image/gif')throw new Error('README来源未返回GIF');add({id,type:'github_readme_gif',status:'captured',url,mediaUrl:src,path:path.relative(project,file.file),title:img.alt,license:'README演示的版权由原作者保留；代码仓库开源许可不自动覆盖所有媒体。'});}
      catch(error){add({id,type:'github_readme_gif',status:'skipped',url,reason:error.message});}
    }
    if(!gifs.length)add({id:'github-gifs',type:'github_readme_gif',status:'skipped',url,reason:'README未发现演示GIF'});
    const videos=[...new Set((repo.details?.readmeVideos||[]).map(src=>publicUrl(src,url)).filter(Boolean))].slice(0,4);
    for(const [i,mediaUrl]of videos.entries()){
      const id='github-video-'+(i+1),base=path.join(project,'downloads',id);
      let original;
      try{
        original=await download(mediaUrl,base+'-source',{allowVideo:true});
        if(!original.mime.startsWith('video/'))throw new Error('README来源未返回视频');
        const file=base+'.mp4',video=normalizeDemoVideo(original.file,file);
        add({id,type:'github_readme_video',status:'captured',url,mediaUrl,path:path.relative(project,file),...video,
          license:'README演示的版权由原作者保留；代码仓库开源许可不自动覆盖所有媒体。'});
      }catch(error){add({id,type:'github_readme_video',status:'skipped',url,mediaUrl,reason:error.message});}
      finally{if(original?.file)fs.rmSync(original.file,{force:true});}
    }
  }
  let announcement=site?latestAnnouncement(homeDetails.links||[],site):null;
  const index=homeLinks.announcements.find(l=>/^\/(?:blog|news|index|changelog|releases)\/?$/.test(new URL(l.url).pathname));
  if(index){const listing=await page('announcement-list',index.url);announcement=latestAnnouncement(listing.details?.links||[],site)||announcement;}
  if(announcement){
    const article=await page('announcement',announcement.url);const item=manifest.items.find(i=>i.id==='announcement-hero');
    if(item){item.publishedAt=article.details?.publishedAt||announcement.date||null;item.selection=announcement.selection;}
  }else add({id:'announcement',type:'announcement',status:'skipped',url:site||null,reason:'未发现可核实的官方公告/博客文章'});
  for(const [index,evidence]of (options.evidence||[]).entries()){
    if(!['app-ranking','finance','benchmark'].includes(evidence.type)||!publicUrl(evidence.url))throw new Error('证据截图需要 app-ranking / finance / benchmark 与公开URL');
    const id='evidence-'+evidence.type+'-'+(index+1);await page(id,evidence.url);
    const item=manifest.items.find(i=>i.id===id+'-hero');if(item){item.type='evidence_'+evidence.type;item.claim=evidence.claim||null;item.dataValues=evidence.values||null;item.usage='可用于news-card；数值已人工核对时可重画bar-compare，须保留来源';}
  }
  manifest.interactive=[...new Map(manifest.interactive.filter(i=>publicUrl(i.url)).map(i=>[i.url,i])).values()];
  fs.writeFileSync(path.join(project,'harness-draft.md'),harnessDraft(name,manifest.interactive,project));
  manifest.harnessDraft='harness-draft.md';
  try{await overview(manifest,project);manifest.overview='overview.png';}catch(error){manifest.warnings.push('总览生成失败：'+error.message);}
  fs.writeFileSync(path.join(project,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  return manifest;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  const args=process.argv.slice(2),get=k=>{const i=args.indexOf(k);return i<0?undefined:args[i+1];};
  try{const report=await collectEntity({name:get('--name'),site:get('--site'),github:get('--github'),press:get('--press'),out:get('--out'),evidence:get('--evidence')?JSON.parse(fs.readFileSync(get('--evidence'),'utf8')):[]});console.log(JSON.stringify({name:report.name,captured:report.items.filter(i=>i.status==='captured').length,skipped:report.items.filter(i=>i.status!=='captured').length,warnings:report.warnings,manifest:path.resolve(get('--out')||path.join('entities',slug(report.name)),'manifest.json')},null,2));}
  catch(error){console.error(error.message);process.exitCode=1;}
}
