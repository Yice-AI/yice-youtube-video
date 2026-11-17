import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {recordAsset} from './asset-ledger.mjs';

export function bindPersonScene(scene,{root,library,useAsset=p=>p}={}){
  const ref=scene.props?.personRef;if(!ref)return scene;
  const dir=path.resolve(ref.library||library||process.env.YICE_PEOPLE_LIBRARY||path.join(os.homedir(),'Documents/Codex/个人IP/ip-tools/data/people-library'));
  const manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json')));
  const choices=manifest.items.filter(i=>(i.name.toLowerCase()===ref.name?.toLowerCase()||(i.aliases||[]).includes(ref.name))&&i.mood===ref.mood&&(!ref.tier||ref.tier===i.tier));
  choices.sort((a,b)=>(a.tier==='default'?0:1)-(b.tier==='default'?0:1));const item=choices[0];
  if(!item)throw new Error('人物库没有该姓名/表情：'+ref.name+' / '+ref.mood);
  const file=path.resolve(dir,item.path);if(!file.startsWith(dir+path.sep))throw new Error('人物素材越出私有库');
  const hash=createHash('sha256').update(fs.readFileSync(file)).digest('hex');if(hash!==item.sha256)throw new Error('人物素材哈希不一致');
  const local=useAsset(file),props={...scene.props,person:local,tier:item.tier,personName:item.name,mood:item.mood};delete props.personRef;
  recordAsset(root,{...item,id:scene.id+'-person-'+item.id,scene:scene.id,role:scene.role||'body',path:local,files:[{path:local,sha256:hash}],sourceType:'person_library',libraryItem:item.id});
  return {...scene,props};
}
