#!/usr/bin/env node
// 真实素材：只检索候选和预览；明确选择候选 ID 后才下载原件并入账。
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { commonsCandidates, downloadAsset, licenseAllowed, licenseUrlKey, request } from './open-media.mjs';
import {createMediaApi,fixtureApi} from './media-api.mjs';
import {stockSearchUrl,pexelsCandidates,pixabayCandidates,PEXELS_LICENSE,PIXABAY_LICENSE} from './stock-media.mjs';

export const NASA_POLICY='https://www.nasa.gov/nasa-brand-center/images-and-media/';
export const PROVIDERS=['commons','nasa','archive','pexels','pixabay'];
const text=value=>String(Array.isArray(value)?value.join('; '):value||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
const hash=value=>createHash('sha256').update(value).digest('hex');
const positive=value=>Number.isFinite(+value)&&+value>0?+value:null;
const ext=url=>new URL(url).pathname.split('.').at(-1).toLowerCase();
const mime=url=>({jpg:'image/jpeg',jpeg:'image/jpeg',png:'image/png',webp:'image/webp',mp4:'video/mp4',webm:'video/webm',ogv:'video/ogg'})[ext(url)]||'';

export function durationSeconds(value){
  if(value==null||value==='')return null;
  if(Array.isArray(value))return durationSeconds(value[0]);
  if(typeof value==='object'){
    const scale=String(value.scale||'1').split('/').map(Number);
    return positive(Number(value.value)*scale[0]/(scale[1]||1));
  }
  if(/^\d+(?:\.\d+)?$/.test(String(value)))return positive(value);
  if(/^\d+(?::\d+(?:\.\d+)?){1,2}$/.test(String(value)))return String(value).split(':').reduce((a,b)=>a*60+Number(b),0);
  const iso=String(value).match(/^PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?$/);
  return iso?Number(iso[1]||0)*3600+Number(iso[2]||0)*60+Number(iso[3]||0):null;
}

export function normalizeCandidate(candidate,type){
  const license=licenseUrlKey(candidate.licenseUrl);
  if(!license||!text(candidate.creator)||!candidate.sourceUrl||!candidate.downloadUrl)return null;
  if(/non.?commercial|no.?derivatives|\bNC\b|\bND\b|by-nc|by-nd/i.test(candidate.license||''))return null;
  const actual=candidate.originalMime||candidate.mime||mime(candidate.downloadUrl);
  if(type==='video'?!actual.startsWith('video/'):!/^image\/(jpeg|png|webp|gif)$/.test(actual))return null;
  const shareAlike=license.includes('/by-sa/'),attributionRequired=license.includes('/by/')||shareAlike||license===NASA_POLICY;
  return {...candidate,id:candidate.id||candidate.provider+'-'+hash(candidate.sourceUrl+'|'+candidate.downloadUrl).slice(0,12),
    type,mime:actual,licenseUrl:license,commercial:true,shareAlike,attributionRequired,
    obligations:shareAlike?'保留作者、来源和许可链接；改编作品依同一许可共享。':attributionRequired?'保留作者、来源和许可链接。':[PEXELS_LICENSE,PIXABAY_LICENSE].includes(license)?'可商用，成品无需署名；素材文档仍保留图库名称、作者、来源页和具体许可限制。':'保留来源和公有领域/CC0依据。',
    width:positive(candidate.width),height:positive(candidate.height),
    durationSeconds:type==='video'?durationSeconds(candidate.durationSeconds??candidate.duration):null,
    attribution:text(candidate.title)+' — '+text(candidate.creator)+' · '+text(candidate.license)+' · '+candidate.sourceUrl,
    selection:'candidate_only'};
}

export function nasaCandidates(data,type){
  return (data.collection?.items||[]).flatMap(item=>{
    const d=item.data?.[0];if(!d||d.media_type!==(type==='photo'?'image':'video'))return [];
    const credit=text(d.photographer||d.secondary_creator||d.creator),description=text(d.description);
    if(/©|\bcopyright\b|all rights reserved|Getty|Shutterstock|SpaceX|Blue Origin|\bESA\b/i.test(credit+' '+description))return [];
    if(credit&&!/\bNASA\b/i.test(credit))return [];
    if(!d.center&&!/\bNASA\b/i.test(credit))return [];
    const links=item.links||[],files=links.filter(x=>type==='photo'?/^image\//.test(mime(x.href)):mime(x.href).startsWith('video/'));
    const file=files.find(x=>x.rel==='canonical')||files.sort((a,b)=>(b.width||0)-(a.width||0))[0];
    const thumbnail=links.find(x=>x.rel==='preview'&&/^image\//.test(mime(x.href)))||links.find(x=>/^image\//.test(mime(x.href)));
    return [{provider:'nasa',nasaId:d.nasa_id,title:d.title,creator:credit||'NASA / '+d.center,
      sourceUrl:'https://images.nasa.gov/details/'+encodeURIComponent(d.nasa_id),downloadUrl:file?.href||null,
      thumbnailUrl:thumbnail?.href||null,mime:file?mime(file.href):(type==='video'?'video/mp4':'image/jpeg'),
      width:file?.width,height:file?.height,bytes:file?.size,duration:d.duration||file?.duration,
      manifestUrl:item.href,license:'PD-US-Gov (NASA原创，按官方媒体使用规则)',licenseUrl:NASA_POLICY,
      rightsNote:'事实性编辑用途，不表示NASA背书；人物或标识用于广告/封面需另外核对。',
      licenseEvidence:{method:'NASA原始馆藏元数据 + 官方媒体使用规则',nasaOriginal:true,policyUrl:NASA_POLICY,metadata:d}}];
  });
}

export function archiveCandidate(identifier,data,type){
  const meta=data.metadata||{},collections=[].concat(meta.collection||[]),license=licenseUrlKey(text(meta.licenseurl));
  const institutional=type==='video'?collections.includes('prelinger'):collections.some(x=>['nasa','NASA','nasa_images'].includes(x));
  if(!institutional||!license?.includes('/publicdomain/'))return null;
  if(/copyright|all rights reserved|non.?commercial|no.?derivatives/i.test(text(meta.rights))&&!/no copyright/i.test(text(meta.rights)))return null;
  const files=(data.files||[]).filter(f=>type==='video'?/\.(mp4|webm|ogv)$/i.test(f.name):/\.(jpe?g|png|webp)$/i.test(f.name)&&!/(?:thumb|itemimage)/i.test(f.name));
  files.sort((a,b)=>(Number(b.width)||0)-(Number(a.width)||0)||(Number(a.size)||Infinity)-(Number(b.size)||Infinity));
  const file=files[0];if(!file)return null;
  const url='https://archive.org/download/'+encodeURIComponent(identifier)+'/'+file.name.split('/').map(encodeURIComponent).join('/');
  return {provider:'archive',archiveId:identifier,title:text(meta.title)||identifier,creator:text(meta.creator)||(type==='photo'?'NASA':'Prelinger Archives'),
    sourceUrl:'https://archive.org/details/'+encodeURIComponent(identifier),downloadUrl:url,thumbnailUrl:'https://archive.org/services/img/'+encodeURIComponent(identifier),
    mime:mime(url),width:file.width||meta.width,height:file.height||meta.height,bytes:Number(file.size),duration:file.length||file.duration||meta.runtime,
    license:license.includes('/zero/')?'CC0':'Public domain',licenseUrl:license,
    licenseEvidence:{method:'Internet Archive机构馆藏 + item metadata许可',collection:collections,licenseurl:meta.licenseurl,rights:meta.rights||'',file:file.name}};
}

export function searchUrl(provider,query,type,n){
  if(!PROVIDERS.includes(provider))throw new Error('未知素材来源');
  if(['pexels','pixabay'].includes(provider))return stockSearchUrl(provider,query,type);
  if(provider==='commons')return 'https://commons.wikimedia.org/w/api.php?'+new URLSearchParams({action:'query',format:'json',generator:'search',gsrsearch:query+' filetype:'+(type==='video'?'video':'bitmap'),gsrnamespace:'6',gsrlimit:String(n),prop:'imageinfo',iiprop:'url|size|mime|extmetadata|metadata|commonmetadata|thumbmime',iiurlwidth:'640'});
  if(provider==='nasa')return 'https://images-api.nasa.gov/search?'+new URLSearchParams({q:query,media_type:type==='photo'?'image':'video',page_size:String(n)});
  const terms=query.match(/\S+/g).map(x=>'"'+x.replace(/["\\]/g,'')+'"').join(' AND ');
  const collection=type==='video'?'collection:prelinger':'(collection:nasa OR collection:NASA OR collection:nasa_images)';
  return 'https://archive.org/advancedsearch.php?'+new URLSearchParams({q:'('+terms+') AND mediatype:'+(type==='video'?'movies':'image')+' AND '+collection+' AND licenseurl:*publicdomain*','fl[]':'identifier',rows:String(n),output:'json'});
}

function metaValue(object,names){
  if(!object||typeof object!=='object')return null;
  for(const [key,value]of Object.entries(object))if(names.includes(key.replace(/.*:/,'').toLowerCase()))return value;
  for(const value of Object.values(object)){const result=metaValue(value,names);if(result!=null)return result;}
  return null;
}

export async function searchProvider({provider,query,type,n,requestFn,api}){
  const client=api||(requestFn?fixtureApi(requestFn):createMediaApi());
  const call=(url,search=false)=>client.request(provider,url,{query,type,search});
  const url=searchUrl(provider,query,type,n),data=await(await call(url,true)).json();let raw=[];const warnings=[];
  if(provider==='commons')raw=commonsCandidates(data).map(x=>({...x,downloadUrl:x.originalUrl||x.downloadUrl,mime:x.originalMime||x.mime}));
  if(provider==='pexels')raw=pexelsCandidates(data,type);
  if(provider==='pixabay')raw=pixabayCandidates(data,type);
  if(provider==='nasa'){
    raw=nasaCandidates(data,type);
    for(const c of raw){
      if(!c.downloadUrl&&c.manifestUrl)try{
        const manifest=await(await call(c.manifestUrl)).json(),files=manifest.collection?.items||[];
        c.downloadUrl=files.find(x=>/~medium\.mp4$/.test(x.href))?.href||files.find(x=>/\.(mp4|webm|ogv)$/.test(x.href))?.href||null;
      }catch(error){c.metadataNote=error.message;}
      if(type==='video'&&(!c.width||!c.height||!c.duration))try{
        const loc=await(await call('https://images-api.nasa.gov/metadata/'+encodeURIComponent(c.nasaId))).json();
        if(loc.location){const md=await(await call(loc.location)).json();c.width=c.width||metaValue(md,['width','imagewidth','videoframewidth']);c.height=c.height||metaValue(md,['height','imageheight','videoframeheight']);c.duration=c.duration||metaValue(md,['duration','length','runtime']);}
      }catch(error){c.metadataNote='补充尺寸/时长未取得：'+error.message;}
    }
  }
  if(provider==='archive')for(const row of data.response?.docs||[]){
    try{const md=await(await call('https://archive.org/metadata/'+encodeURIComponent(row.identifier))).json(),c=archiveCandidate(row.identifier,md,type);if(c)raw.push(c);}
    catch(error){warnings.push({id:row.identifier,reason:error.message});if(error.code==='INVOCATION_LIMIT')break;}
  }
  return {provider,url,seen:provider==='archive'?(data.response?.docs||[]).length:raw.length,warnings,candidates:raw.map(x=>normalizeCandidate(x,type)).filter(Boolean)};
}

export function mergeCandidates(groups,n){
  const result=[],seen=new Set();let index=0;
  while(result.length<n&&groups.some(g=>g[index])){
    for(const group of groups){const c=group[index];if(!c||seen.has(c.sourceUrl+'|'+c.downloadUrl))continue;seen.add(c.sourceUrl+'|'+c.downloadUrl);result.push(c);if(result.length===n)break;}index++;
  }
  return result;
}

export async function findCandidates({query,type='photo',n=8,providers,requestFn,api,episode,privateDir,maxDuration=Infinity,minWidth=0,minHeight=0}){
  if(!query?.trim())throw new Error('--q不能为空');
  if(!['photo','video'].includes(type))throw new Error('--type只能为photo或video');
  if(!Number.isInteger(n)||n<1||n>100)throw new Error('--n必须为1–100整数');
  if(!(maxDuration>0)||!Number.isFinite(minWidth)||!Number.isFinite(minHeight)||minWidth<0||minHeight<0)throw new Error('时长/分辨率筛选参数无效');
  if(providers&&(!providers.length||providers.some(x=>!PROVIDERS.includes(x))))throw new Error('未知素材来源');
  const client=api||(requestFn?fixtureApi(requestFn):createMediaApi({episode,root:privateDir}));
  providers??=[...['pexels','pixabay'].filter(p=>client.enabled?.(p)), 'commons','nasa','archive'];
  if(!providers.length||providers.some(x=>!PROVIDERS.includes(x)))throw new Error('未知素材来源');
  const reports=[],groups=[];
  for(const provider of providers){
    try{
      const r=await searchProvider({provider,query,type,n,api:client});
      const eligible=r.candidates.filter(c=>(!minWidth||c.width>=minWidth)&&(!minHeight||c.height>=minHeight)&&(maxDuration===Infinity||(c.durationSeconds!=null&&c.durationSeconds<=maxDuration)));
      reports.push({provider,status:'searched',url:r.url,seen:r.seen,eligible:eligible.length,warnings:r.warnings});groups.push(eligible);
    }catch(error){
      if(['EPISODE_BUDGET','MONTHLY_BUDGET','OFFLINE'].includes(error.code))throw error;
      reports.push({provider,status:error.code==='INVOCATION_LIMIT'?'deferred_budget':error.code==='SOURCE_DISABLED'?'not_configured':'test_limit',reason:error.message,note:'不重试；缓存命中不消耗API调用。'});groups.push([]);
    }
  }
  return {schemaVersion:1,query,type,requested:n,filters:{maxDuration:Number.isFinite(maxDuration)?maxDuration:null,minWidth,minHeight},createdAt:new Date().toISOString(),downloadPolicy:'仅候选和缩略图；中心选定ID后显式下载入账。',usage:client.stats(),sources:reports,candidates:mergeCandidates(groups,n)};
}

const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export async function candidateSheet(report,out,{requestFn=request,title,imageName='candidates.png',jsonName='candidates.json'}={}){
  fs.mkdirSync(path.join(out,'previews'),{recursive:true});const cards=[];
  for(const c of report.candidates){
    let image='';
    if(c.thumbnailUrl)try{
      const response=await requestFn(c.thumbnailUrl),type=response.headers.get('content-type')||'';
      if(!type.startsWith('image/'))throw new Error('缩略图不是图片');
      const bytes=Buffer.from(await response.arrayBuffer());if(bytes.length>8*1024*1024)throw new Error('缩略图过大');
      const filename='previews/'+hash(c.id).slice(0,16)+'.'+(type.includes('png')?'png':type.includes('webp')?'webp':type.includes('gif')?'gif':'jpg');fs.writeFileSync(path.join(out,filename),bytes);
      c.previewPath=filename;image='data:'+type.split(';')[0]+';base64,'+bytes.toString('base64');
    }catch(error){c.previewError=error.message;}
    const dimensions=c.width&&c.height?c.width+' × '+c.height:'源未给出分辨率';
    const duration=c.type==='video'?(c.durationSeconds!=null?c.durationSeconds.toFixed(1)+'秒':'源未给出时长'):'照片';
    cards.push('<article><div class="image">'+(image?'<img src="'+image+'">':'<span>预览不可用</span>')+'</div><b>'+escape(c.id)+'</b><h3>'+escape(c.title)+'</h3><p>'+escape(c.provider+' · '+dimensions+' · '+duration)+'</p><p>'+escape(c.license+(c.shareAlike?' · 需署名及同许可共享':''))+'</p><small>'+escape(c.creator)+'</small></article>');
  }
  const require=createRequire(path.join(out,'package.json')),{chromium}=require(process.env.YICE_PLAYWRIGHT_MODULE||'playwright-core');
  const browser=await chromium.launch({headless:true,...(process.env.YICE_CHROME_EXECUTABLE?{executablePath:process.env.YICE_CHROME_EXECUTABLE}:{channel:'chrome'})});
  try{
    const page=await browser.newPage({viewport:{width:1600,height:900}});
    await page.setContent('<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:24px;background:#E4E6E2;color:#1E1A15;font:16px Arial,"PingFang SC",sans-serif}h1{font-size:26px;margin:0 0 16px}main{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}article{background:#FBFBF8;padding:12px;min-width:0}.image{height:210px;background:#ddd;display:grid;place-items:center;overflow:hidden}img{display:block;width:100%;height:210px;min-width:0;min-height:0;object-fit:contain}h3{font-size:16px;height:40px;overflow:hidden;margin:8px 0}b{display:block;font-size:13px;margin-top:8px}p,small{font-size:13px;margin:5px 0;overflow-wrap:anywhere}</style><h1>'+escape(report.query)+' · '+report.candidates.length+'个许可候选</h1><main>'+cards.join('')+'</main>'+(cards.length?'':'<p>没有可用候选，详见candidates.json的来源结果。</p>'));
    await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))));
    if(title)await page.locator('h1').evaluate((e,t)=>e.textContent=t,title);
    await page.screenshot({path:path.join(out,imageName),fullPage:true});
  }finally{await browser.close();}
  if(jsonName)fs.writeFileSync(path.join(out,jsonName),JSON.stringify(report,null,2)+'\n');
}

export async function downloadSelection({file,ids,project,scene='',maxMiB=25,maxDuration,requestFn=request}){
  if(!ids?.length)throw new Error('必须明确给出中心选定的候选ID');
  const report=JSON.parse(fs.readFileSync(file,'utf8')),selected=ids.map(id=>{const c=report.candidates.find(x=>x.id===id);if(!c)throw new Error('候选ID不存在：'+id);return c;});
  const assets=[];fs.mkdirSync(project,{recursive:true});
  for(const c of selected)assets.push(await downloadAsset({project,candidate:{...c,selectedCandidateId:c.id,selection:'explicitly_selected'},scene,requestFn,transcodeVideo:true,maxBytes:maxMiB*1024*1024,maxDuration:maxDuration??report.filters?.maxDuration??Infinity}));
  return assets;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  const args=process.argv.slice(2),get=(flag,fallback)=>args.includes(flag)?args[args.indexOf(flag)+1]:fallback;
  try{
    if(args.includes('--download')){
      const assets=await downloadSelection({file:path.resolve(get('--download')),ids:(get('--select','')).split(',').filter(Boolean),project:path.resolve(get('--project',process.cwd())),scene:get('--scene',''),maxMiB:Number(get('--max-mib','25')),maxDuration:args.includes('--max-duration')?Number(get('--max-duration')):undefined});
      console.log(JSON.stringify({status:'downloaded',assets},null,2));
    }else{
      const out=path.resolve(get('--out','media-candidates')),report=await findCandidates({query:get('--q',''),type:get('--type','photo'),n:Number(get('--n','8')),providers:args.includes('--sources')?get('--sources').split(','):undefined,episode:path.resolve(get('--project',process.cwd())),maxDuration:Number(get('--max-duration','Infinity')),minWidth:Number(get('--min-width','0')),minHeight:Number(get('--min-height','0'))});
      fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'candidates.json'),JSON.stringify(report,null,2)+'\n');await candidateSheet(report,out);
      console.log(JSON.stringify({status:'candidates_ready',count:report.candidates.length,sources:report.sources,json:path.join(out,'candidates.json'),sheet:path.join(out,'candidates.png')},null,2));
    }
  }catch(error){console.error(error.message);process.exitCode=1;}
}
