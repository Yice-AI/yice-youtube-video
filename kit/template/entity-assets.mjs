import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {recordAsset} from './asset-ledger.mjs';

// news-card / social-post 的同一个来源引用同时带入画面文件、来源、日期和账本。
export function bindEntityScene(scene,{root,resolvePath=p=>path.resolve(root,p),useAsset=p=>p}={}){
  const ref=scene.props?.entity;if(!ref)return scene;
  if(!['news-card','social-post','bar-compare'].includes(scene.recipe))throw new Error('entity 引用用于 news-card / social-post / bar-compare');
  if(!ref.manifest||!ref.item)throw new Error('entity 需要 manifest 和 item');
  const manifestFile=resolvePath(ref.manifest);if(!manifestFile)throw new Error('entity manifest 不存在');
  const manifest=JSON.parse(fs.readFileSync(manifestFile,'utf8'));
  const item=manifest.items?.find(i=>i.id===ref.item);
  if(!item||item.status!=='captured'||!item.path)throw new Error('entity 素材未成功采集：'+ref.item);
  const file=path.resolve(path.dirname(manifestFile),item.path);
  if(!file.startsWith(path.dirname(manifestFile)+path.sep))throw new Error('entity 素材路径越出 manifest 目录');
  const hash=createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  if(item.sha256&&hash!==item.sha256)throw new Error('entity 素材与采集哈希不一致');
  const local=useAsset(file),props={...scene.props};delete props.entity;
  if(scene.recipe==='news-card')Object.assign(props,{shot:local,source:props.source||manifest.name,date:props.date||item.capturedAt?.slice(0,10),headline:props.headline||item.title||manifest.name});
  else if(scene.recipe==='bar-compare'){
    if(!item.dataValues?.length)throw new Error('实体证据没有已核对的数值，不能自动编造柱图');
    Object.assign(props,{items:item.dataValues,source:props.source||manifest.name+' · '+item.url});
  }else Object.assign(props,{image:local,source:props.source||manifest.name+' · 官网摘录',name:props.name||manifest.name,publicAccount:true,text:props.text||item.title||manifest.name,time:props.time||'采集 '+item.capturedAt?.slice(0,10)});
  props.sourceUrl=item.url;
  recordAsset(root,{...item,id:scene.id+'-entity-'+item.id,sourceType:'entity_reference',sourceUrl:item.url,sourceName:manifest.name,entityManifest:manifestFile,entityItem:item.id,scene:scene.id,path:local,sha256:hash,files:[{path:local,sha256:hash}]});
  return {...scene,props};
}
