"""私有人物表情素材入库；复用本地前景分割，不生成或改变人物表情。"""
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps
from cutout import paper_cutout, vision_extract
from workspace import load_environment

MOODS = ['得意', '震惊', '扶额', '摊手', '思考', '笑', '皱眉']


def validate(name, tier, mood, provenance):
    if not name or not name.strip(): raise ValueError('需要人物姓名')
    if tier not in ['default', 'commentary']: raise ValueError('tier 只能是 default / commentary')
    if mood not in MOODS: raise ValueError('未知 mood')
    for key in ['sourceUrl', 'license']:
        if not provenance.get(key): raise ValueError('人物来源缺少 ' + key)
    if tier == 'default' and provenance.get('sourceType') not in ['official_press', 'official_event', 'commons']:
        raise ValueError('default 档须注明 official_press / official_event / commons 来源依据')


def add_person(name, source, tier, mood, library, provenance, *, frame=None, crop=None, backend=vision_extract):
    validate(name, tier, mood, provenance)
    if frame is not None and (not math.isfinite(frame) or frame < 0): raise ValueError('视频截帧时间必须为非负数')
    source=Path(source).resolve();library=Path(library).resolve();library.mkdir(parents=True, exist_ok=True)
    manifest_file=library/'manifest.json'
    manifest=json.loads(manifest_file.read_text()) if manifest_file.exists() else {'schemaVersion':1,'private':True,'items':[]}
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    identity=hashlib.sha256((source_hash+':'+str(frame)).encode()).hexdigest()
    if any(i['name'].casefold()==name.casefold() and i.get('sourceIdentity')==identity and i['mood']!=mood for i in manifest['items']):
        raise ValueError('同一原图/同一视频帧不能改标签凑另一种表情')
    person_slug=re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-') or 'person-'+hashlib.sha256(name.encode()).hexdigest()[:8]
    asset_id=person_slug+'-'+identity[:12];output=library/person_slug/(mood+'-'+identity[:12]);output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        tmp=Path(tmp);photo=source
        if frame is not None:
            photo=tmp/'frame.png';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(frame),'-i',str(source),'-frames:v','1',str(photo)],capture_output=True,check=True)
        with Image.open(photo) as opened: image=ImageOps.exif_transpose(opened).convert('RGBA')
        if crop:
            x,y,w,h=crop
            if min(x,y)<0 or min(w,h)<=0 or x+w>image.width or y+h>image.height:raise ValueError('人物裁切须在原图内')
            image=image.crop((x,y,x+w,y+h))
        image.thumbnail((1600,1600),Image.Resampling.LANCZOS);prepared=tmp/'input.png';raw=tmp/'raw.png';image.save(prepared)
        # 官网PNG常只有一圈透明像素，仍有完整照片背景，不能当作已抠图。
        hist=image.getchannel('A').histogram();transparent_ratio=sum(hist[:250])/(image.width*image.height)
        if transparent_ratio >= .03: image.save(raw);info={'backend':'existing-alpha'}
        else: info=backend(prepared,raw)
        with Image.open(raw) as opened: subject=opened.convert('RGBA')
        alpha=subject.getchannel('A')
        if alpha.getbbox() is None or alpha.getextrema()[0]>=250:raise ValueError('没有得到有效人物透明背景')
        subject=subject.crop(alpha.getbbox());scale=860/max(subject.size)
        subject=subject.resize((max(1,round(subject.width*scale)),max(1,round(subject.height*scale))),Image.Resampling.LANCZOS)
        decorated=paper_cutout(ImageOps.expand(subject,border=1,fill=(0,0,0,0)),angle=0,border=10,seed=0)
        canvas=Image.new('RGBA',(1080,1080));canvas.alpha_composite(decorated,((1080-decorated.width)//2,(1080-decorated.height)//2));canvas.save(output/'paper.png')
        transparent=Image.new('RGBA',(1080,1080));transparent.alpha_composite(subject,((1080-subject.width)//2,(1080-subject.height)//2));transparent.save(output/'transparent.png')
    original=output/('original'+(source.suffix or '.bin'))
    if source!=original.resolve():shutil.copy2(source,original)
    item={**provenance,'id':asset_id,'name':name,'tier':tier,'mood':mood,'sourcePath':str(original),'sourceSha256':source_hash,'sourceIdentity':identity,'frameSeconds':frame,'capturedAt':datetime.now(timezone.utc).isoformat(),'type':'person_cutout','kind':'cutout','path':str((output/'paper.png').relative_to(library)),'width':1080,'height':1080,'sha256':hashlib.sha256((output/'paper.png').read_bytes()).hexdigest(),'processing':{**info,'whiteBorderPx':10,'shadowOpacity':.24,'subjectMaxEdge':860,'canvas':[1080,1080],'expressionAltered':False},'usage':'正文和缩略图' if tier=='default' else '仅正文评论；禁止缩略图；不得编台词或暗示代言'}
    item['processing']['crop']=crop
    item['files']=[{'path':str((output/f).relative_to(library)),'sha256':hashlib.sha256((output/f).read_bytes()).hexdigest()} for f in ['paper.png','transparent.png']]
    manifest['items']=[i for i in manifest['items'] if i['id']!=asset_id]+[item]
    temp=manifest_file.with_suffix('.json.tmp');temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');temp.replace(manifest_file)
    module=Path(__file__).parents[1]/'template/asset-ledger.mjs'
    subprocess.run(['node','--input-type=module','-e',"import fs from 'node:fs';const {recordAsset}=await import(process.argv[1]);const x=JSON.parse(fs.readFileSync(0,'utf8'));recordAsset(x.library,x.item);",module.as_uri()],input=json.dumps({'library':str(library),'item':item}),text=True,check=True)
    return item


def fetch_source(src, directory):
    if not re.match(r'^https?://',src):return Path(src).expanduser().resolve()
    url=urllib.parse.urlsplit(src)
    if url.username or url.password:raise ValueError('只读取不含登录信息的公开URL')
    file=Path(directory)/'source'
    with urllib.request.urlopen(urllib.request.Request(src,headers={'User-Agent':'YiceVideo/1.0 editorial material collection'}),timeout=30) as response:
        mime=response.headers.get_content_type()
        if not (mime.startswith('image/') or mime.startswith('video/')):raise ValueError('来源未返回图片或视频')
        total=0
        with file.open('wb') as out:
            while chunk:=response.read(1024*1024):
                total+=len(chunk)
                if total>80*1024*1024:raise ValueError('人物来源文件超过80MB，请先提供指定帧')
                out.write(chunk)
    return file


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--src',required=True);p.add_argument('--tier',choices=['default','commentary'],required=True);p.add_argument('--mood',choices=MOODS,required=True);p.add_argument('--source-json');p.add_argument('--library');p.add_argument('--frame',type=float)
    p.add_argument('--crop',help='原图 x,y,width,height；只裁出指定人物，不改变表情')
    a=p.parse_args();workspace,_=load_environment();library=Path(a.library) if a.library else workspace/'ip-tools/data/people-library'
    crop=tuple(map(int,a.crop.split(','))) if a.crop else None
    if crop and len(crop)!=4:p.error('--crop 需要 x,y,width,height')
    provenance=json.loads(Path(a.source_json).read_text()) if a.source_json else {'sourceUrl':a.src,'license':'原权利人保留；仅用于有来源的评论/识别，不暗示代言','sourceType':'commentary'}
    validate(a.name,a.tier,a.mood,provenance)
    with tempfile.TemporaryDirectory() as tmp:
        source=fetch_source(a.src,tmp);item=add_person(a.name,source,a.tier,a.mood,library,provenance,frame=a.frame,crop=crop)
    print(json.dumps({'id':item['id'],'name':item['name'],'mood':item['mood'],'tier':item['tier'],'path':str(library/item['path'])},ensure_ascii=False))


if __name__=='__main__':main()
