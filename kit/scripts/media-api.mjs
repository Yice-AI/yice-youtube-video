// API 访问统一入口：24h 私有缓存、单次 3 请求、每期 60 / 本线每月 1500 请求。
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';

export const PRIVATE_ROOT=path.join(os.homedir(),'.config/yice-video');
const DAY=24*60*60*1000;
const STOCK=new Set(['pexels','pixabay']);
const HOSTS={pexels:['api.pexels.com'],pixabay:['pixabay.com'],commons:['commons.wikimedia.org'],nasa:['images-api.nasa.gov','images-assets.nasa.gov'],archive:['archive.org']};
const hash=value=>createHash('sha256').update(value).digest('hex');
const error=(message,code)=>Object.assign(new Error(message),{code});
const normalize=value=>String(value).trim().replace(/\s+/g,' ').toLowerCase();
function readJSON(file,fallback){return fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):fallback;}
function save(file,value){fs.writeFileSync(file+'.tmp',JSON.stringify(value)+'\n',{mode:0o600});fs.renameSync(file+'.tmp',file);fs.chmodSync(file,0o600);}
function stripCredentialParams(value){
  if(Array.isArray(value))return value.map(stripCredentialParams);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,item])=>[key,stripCredentialParams(item)]));
  if(typeof value==='string'&&/^https?:\/\//.test(value))try{const url=new URL(value);for(const key of [...url.searchParams.keys()])if(/^(key|api_key|apikey|authorization)$/i.test(key))url.searchParams.delete(key);return url.href;}catch{}
  return value;
}

export function readStockKeys(root=PRIVATE_ROOT){
  const file=path.join(root,'stock.env'),keys={};
  if(!fs.existsSync(file))return keys;
  for(const line of fs.readFileSync(file,'utf8').split(/\r?\n/)){
    const match=line.match(/^\s*(?:export\s+)?(PEXELS_API_KEY|PIXABAY_API_KEY)\s*=\s*(.*?)\s*$/);
    if(!match)continue;
    let value=match[2];if((value.startsWith('"')&&value.endsWith('"'))||(value.startsWith("'")&&value.endsWith("'")))value=value.slice(1,-1);
    if(value&&!/[\r\n\0]/.test(value))keys[match[1].startsWith('PEXELS')?'pexels':'pixabay']=value;
  }
  return keys;
}

export function readUsage(root=PRIVATE_ROOT){
  const file=path.join(root,'usage.jsonl');
  return fs.existsSync(file)?fs.readFileSync(file,'utf8').split('\n').filter(Boolean).map(JSON.parse):[];
}

export function readBudgets(root=PRIVATE_ROOT){
  const raw=readJSON(path.join(root,'media-budgets.json'),{});
  if(raw.schema===2)return raw;
  const months={};for(const row of readUsage(root)){const month=row.at.slice(0,7);months[month]=(months[month]||0)+1;}
  return {schema:2,episodes:raw,months};
}

export function usageSummary(rows,{now=Date.now(),budgets,episode}={}){
  const days={};const latest={};
  for(const row of rows){const day=row.at.slice(0,10);days[day]??={};days[day][row.source]=(days[day][row.source]||0)+1;if(row.remaining!=null)latest[row.source]=row;}
  const month=new Date(now).toISOString().slice(0,7);
  const monthlyUsed=budgets?.months?.[month]??rows.filter(r=>r.at.startsWith(month)).length;
  return {youtubeLine:{daily:Object.entries(days).sort().map(([day,sources])=>({day,sources})),monthly:{month,used:monthlyUsed,limit:1500},...(episode?{episode:{used:budgets?.episodes?.[hash(path.resolve(episode))]||0,limit:60}}:{})},sharedAccountRemaining:Object.fromEntries(Object.entries(latest).map(([source,row])=>[source,{limit:row.limit,remaining:row.remaining,resetAt:row.resetAt,observedAt:row.at,stale:!!row.resetAt&&Date.parse(row.resetAt)<=now}])),note:'本线用量按UTC日/月统计，含失败预留；账户剩余额度与Prezto等项目共用，是响应头最后观测值。缓存命中不计数。历史控制台用量不能倒推归因，过期窗口不代表实时额度。'};
}

export function createMediaApi({episode=process.cwd(),root=PRIVATE_ROOT,transport=fetch,now=Date.now}={}){
  const cacheDir=path.join(root,'media-cache'),budgetFile=path.join(root,'media-budgets.json'),lock=path.join(root,'media-api.lock');
  const episodeId=hash(path.resolve(episode));let calls=0,cacheHits=0;
  const keys=readStockKeys(root);
  function cached(file){
    const row=readJSON(file,null);if(!row||now()-row.at>=DAY)return null;
    cacheHits++;if(row.error)throw error(row.error,row.code||'CACHED_FAILURE');
    return new Response(JSON.stringify(row.data),{headers:{'content-type':'application/json','x-yice-cache':'hit'}});
  }
  async function request(provider,rawUrl,{query='',type='',search=false}={}){
    const u=new URL(rawUrl);
    if(u.protocol!=='https:'||u.username||u.password||!HOSTS[provider]?.includes(u.hostname))throw error('不支持的素材 API 地址','INVALID_API');
    u.searchParams.delete('key');
    const cacheKey=search?[provider,normalize(query),type].join('|'):provider+'|'+u.href;
    const file=path.join(cacheDir,hash(cacheKey)+'.json');
    const hit=cached(file);if(hit)return hit;
    if(STOCK.has(provider)&&!keys[provider])throw error(provider+' 未配置本机密钥，跳过','SOURCE_DISABLED');
    if(calls>=3)throw error('单次 find-media 已达 3 次 API 请求；其余来源延后，可复用缓存','INVOCATION_LIMIT');
    if(process.env.YICE_MEDIA_OFFLINE==='1'&&transport===fetch)throw error('离线测试禁止真实素材 API 请求','OFFLINE');
    fs.mkdirSync(cacheDir,{recursive:true,mode:0o700});
    try{fs.mkdirSync(lock,{mode:0o700});}catch{throw error('另一素材请求正在更新额度；稍后重试','API_BUSY');}
    try{
      const secondHit=cached(file);if(secondHit)return secondHit;
      if(STOCK.has(provider)){
        const budgets=readBudgets(root),used=budgets.episodes[episodeId]||0,month=new Date(now()).toISOString().slice(0,7),monthly=budgets.months[month]||0;
        if(used>=60)throw error('本期 Pexels+Pixabay 已达 60 次 API 预算，拒绝新请求','EPISODE_BUDGET');
        if(monthly>=1500)throw error('YouTube本线本月已达 1500 次 API 预算，拒绝新请求','MONTHLY_BUDGET');
        budgets.episodes[episodeId]=used+1;budgets.months[month]=monthly+1;save(budgetFile,budgets); // 请求前预留，网络失败也保守计费。
      }
      calls++;
      const at=now(),headers={'User-Agent':'YiceVideoToolkit/1.0 (human-directed media search)'};
      if(provider==='pexels')headers.Authorization=keys.pexels;
      if(provider==='pixabay')u.searchParams.set('key',keys.pixabay);
      let response;
      try{response=await transport(u.href,{headers,redirect:'error',signal:AbortSignal.timeout(25000)});}
      catch{/* 不记录原始异常或带 key 的 URL。 */}
      if(STOCK.has(provider)){
        const number=name=>{const value=response?.headers.get(name);return value!=null&&Number.isFinite(+value)?+value:null;};
        const reset=number('x-ratelimit-reset');
        const resetMs=reset==null?null:provider==='pixabay'?at+reset*1000:reset*1000;
        const row={at:new Date(at).toISOString(),source:provider,query:normalize(query),limit:number('x-ratelimit-limit'),remaining:number('x-ratelimit-remaining'),reset,resetAt:resetMs==null?null:new Date(resetMs).toISOString()};
        fs.appendFileSync(path.join(root,'usage.jsonl'),JSON.stringify(row)+'\n',{mode:0o600});fs.chmodSync(path.join(root,'usage.jsonl'),0o600);
      }
      if(!response?.ok){const message=provider+' API '+(response?'HTTP '+response.status:'请求失败')+'；24h内不重复请求';save(file,{at,error:message,code:'API_FAILED'});throw error(message,'API_FAILED');}
      let data;
      try{data=await response.json();}catch{const message=provider+' API 响应不是有效 JSON';save(file,{at,error:message,code:'API_FAILED'});throw error(message,'API_FAILED');}
      // API 返回的分页 URL 也必须先脱敏；密钥绝不进缓存、候选、日志。
      let serialized=JSON.stringify(stripCredentialParams(data));for(const key of Object.values(keys))serialized=serialized.split(key).join('[REDACTED]');data=JSON.parse(serialized);
      save(file,{at,data});return new Response(JSON.stringify(data),{headers:{'content-type':'application/json','x-yice-cache':'miss'}});
    }finally{fs.rmdirSync(lock);}
  }
  return {request,stats:()=>({apiRequests:calls,cacheHits,maxApiRequests:3,episodeBudget:60,monthlyBudget:1500}),enabled:provider=>!STOCK.has(provider)||!!keys[provider]};
}

// 离线 fixture 注入使用同样的调用上限，不接触真实私有目录或密钥。
export function fixtureApi(transport){
  let calls=0;
  return {request:async(provider,url)=>{if(calls>=3)throw error('单次 3 次 API 上限','INVOCATION_LIMIT');calls++;return transport(url);},stats:()=>({apiRequests:calls,fixture:true})};
}
