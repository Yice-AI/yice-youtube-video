import fs from 'node:fs';
import path from 'node:path';

export function recordAsset(project,entry){
  const file=path.join(project,'asset-ledger.jsonl');
  const rows=fs.existsSync(file)?fs.readFileSync(file,'utf8').split('\n').filter(Boolean).map(JSON.parse):[];
  const text=[...rows.filter(row=>row.id!==entry.id),entry].map(row=>JSON.stringify(row)).join('\n')+'\n';
  fs.writeFileSync(file+'.tmp',text);fs.renameSync(file+'.tmp',file);
}
