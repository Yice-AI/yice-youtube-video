#!/usr/bin/env python3
"""从长视频挑选高信息量片段，并为分幕清单生成渲染前核验图。"""
import argparse
from bisect import bisect_left
from io import BytesIO
import json
from math import isfinite
import os
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from audit_v7 import VIDEO_EXTENSIONS, difference_hash, probe_video

SIZE = (320, 180)
SCALE = 'scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2'
VIDEO_STAGES = {'callout_rig','fullbleed_rig','cold_open_ab','triptych_cards','reference_breakdown','studio_ui','evidence_spotlight'}
OCR = Path(__file__).resolve().parents[1] / 'tools/ocr/ocr'


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def frame_at(source, second):
    result = subprocess.run(['ffmpeg','-v','error','-ss',f'{second:.6f}','-i',str(source),'-frames:v','1',
                             '-vf',SCALE,'-c:v','png','-threads','1','-f','image2pipe','-'],
                            check=True,capture_output=True)
    with Image.open(BytesIO(result.stdout)) as image:
        return image.convert('RGB')


def sample_frames(source, step):
    command = ['ffmpeg','-v','error','-i',str(source),'-map','0:v:0',
               '-vf',f'fps=1/{step:g}:start_time=0,{SCALE}','-pix_fmt','rgb24','-f','rawvideo','-']
    size = SIZE[0]*SIZE[1]*3
    with subprocess.Popen(command,stdout=subprocess.PIPE) as process:
        index = 0
        while data := process.stdout.read(size):
            if len(data)!=size:
                raise ValueError(f'抽帧数据不完整：{source.name}')
            yield index*step,Image.frombytes('RGB',SIZE,data)
            index += 1
        if process.wait():
            raise ValueError(f'视频抽帧失败：{source.name}')


def frame_scores(frame):
    rgb = np.asarray(frame)
    quantized = rgb.astype(np.uint16) >> 4
    bins = (quantized[:,:,0]<<8) | (quantized[:,:,1]<<4) | quantized[:,:,2]
    counts = np.bincount(bins.ravel(),minlength=4096)
    flat = float(np.partition(counts,-2)[-2:].sum()/bins.size)
    grey = np.asarray(frame.convert('L'),dtype=np.float32)
    edge = float((np.abs(np.diff(grey,axis=0)).mean()+np.abs(np.diff(grey,axis=1)).mean())/510)
    is_flat = flat>=.72
    band = grey[148:176,40:280]
    # 字幕的浅色笔画旁会紧贴深色描边，并在数个相邻行横向分布。
    bright = band[1:-1,1:-1]
    dark = np.minimum.reduce([band[:-2,1:-1],band[2:,1:-1],band[1:-1,:-2],band[1:-1,2:]])
    outlines = (bright >= 200) & (bright-dark >= 100)
    text_rows = outlines.sum(axis=1) >= 12
    subtitle_edge = bool(np.count_nonzero(text_rows)>=3 and np.count_nonzero(outlines.any(axis=0))>=30)
    return dict(dhash=f'{difference_hash(frame):016x}',flat_bg_ratio=round(flat,4),is_flat_slide=is_flat,
                richness_score=round(edge*(.35 if is_flat else 1.),4),has_burned_subtitle=subtitle_edge)


def subtitle_ocr(row, binary):
    try:
        with tempfile.TemporaryDirectory() as temp:
            frame = Path(temp) / 'frame.png'
            subprocess.run(['ffmpeg','-v','error','-ss',str(row['at']),'-i',row['source'],
                            '-frames:v','1','-threads','1',str(frame)],check=True,capture_output=True,timeout=10)
            with Image.open(frame) as image:
                width,height = image.size
            region = ','.join(str(int(value)) for value in (.12*width,.82*height,.76*width,.16*height))
            result = subprocess.run([str(binary),str(frame),'--region',region],check=True,
                                    capture_output=True,text=True,timeout=5)
            return any(sum(char.isalnum() for char in text['text'])>=3
                       and .28*width <= text['box'][0]+text['box'][2]/2 <= .72*width
                       for text in json.loads(result.stdout)['results'])
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        return None


def scene_candidates(sources, window, step, top, include_flat, allow_burned_subtitles=False):
    candidates = []
    for source in dict.fromkeys(Path(item).resolve() for item in sources):
        last_start = probe_video(source)-window-.25
        if last_start<0:
            continue
        samples = [(at,frame_scores(frame)) for at,frame in sample_frames(source,min(step,window/2))]
        times = [at for at,_ in samples]
        for at,metrics in samples:
            start = min(last_start,max(0.,at-window/2))
            if at>=start+window:
                continue
            inside = [scores for _,scores in samples[bisect_left(times,start):bisect_left(times,start+window)]]
            if not include_flat and any(scores['is_flat_slide'] for scores in inside):
                continue
            hashes = [int(scores['dhash'],16) for scores in inside]
            if any((left^right).bit_count()>24 for left,right in zip(hashes,hashes[1:])):
                continue
            candidates.append(dict(source=str(source),start=round(start,5),end=round(start+window,5),
                                   duration=window,at=at,**metrics))
    candidates.sort(key=lambda row:(row['is_flat_slide'],-row['richness_score'],row['source'],row['at']))
    if os.access(OCR,os.X_OK):
        for row in candidates[:top*2]:
            burned = subtitle_ocr(row,OCR)
            if burned is not None:
                row['has_burned_subtitle'] = burned
    representatives, selected = [], []
    for row in candidates:
        if row['has_burned_subtitle'] and not allow_burned_subtitles:
            continue
        value = int(row['dhash'],16)
        if any((value^other).bit_count()<=6 for other in representatives):
            continue
        representatives.append(value)
        if any((value^int(old['dhash'],16)).bit_count()<=8 or
               (row['source']==old['source'] and max(row['start'],old['start'])<min(row['end'],old['end']))
               for old in selected):
            continue
        selected.append(dict(row,id=f'{len(selected)+1:02d}'))
        if len(selected)>=top:
            break
    return selected


def contact_font(size):
    for path in ('/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/Supplemental/Songti.ttc','DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(path,size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def fitted_line(draw, x, y, label, width, font, color='white'):
    label = str(label).replace('\n',' ')
    if draw.textlength(label,font=font)>width:
        while label and draw.textlength(label+'…',font=font)>width:
            label = label[:-1]
        label += '…'
    draw.text((x,y),label,font=font,fill=color)


def write_scene_contact(candidates, output):
    width, height = 336, 235
    columns = min(4,max(1,len(candidates)))
    image = Image.new('RGB',(columns*width,max(1,(len(candidates)+columns-1)//columns)*height),'#172322')
    draw, font = ImageDraw.Draw(image), contact_font(17)
    if not candidates:
        draw.text((12,14),'未找到满足选段条件的片段',font=font,fill='white')
    for index,row in enumerate(candidates):
        x,y = index%columns*width+8,index//columns*height+8
        image.paste(frame_at(Path(row['source']),row['at']),(x,y))
        fitted_line(draw,x,y+185,f"#{row['id']} {Path(row['source']).name}",width-16,font)
        kind = 'flat' if row['is_flat_slide'] else 'rich'
        fitted_line(draw,x,y+209,f"{row['start']:.2f}–{row['end']:.2f}s · {kind}",width-16,font,'#b5c9a9')
    image.save(output/'scene-candidates.jpg',quality=92)


def anchor_texts(raw, root):
    cues = raw.get('cues',raw.get('voice_timing'))
    if isinstance(cues,str):
        cues = read_json(root/cues)
    if not cues and raw.get('voice_manifest'):
        cues = read_json(root/raw['voice_manifest']).get('scene_timing')
    return {cue['id']:cue.get('text','') for cue in cues or []}


def shot_sources(shot):
    mode = shot['stage_mode']
    span = float(shot['end'])-float(shot['start'])
    media_start = float(shot.get('media_start',0.))
    if mode=='triptych_cards':
        for card in shot.get('cards',[]):
            yield card['source'],float(card.get('media_start',0.)),span-float(card['reveal_at'])
        return
    if mode=='studio_ui':
        monitor = shot.get('data',{}).get('monitor')
        if monitor:
            yield monitor,0.,span
    files = shot.get('sources')
    if files is None:
        single = shot.get('source',shot.get('asset'))
        files = [single] if single else []
    for source in files:
        yield source,media_start,span


def make_verification_rows(manifest):
    raw = read_json(manifest)
    root = manifest.parent
    anchors = anchor_texts(raw,root)
    rows = []
    for shot in raw['shots']:
        if shot.get('stage_mode') not in VIDEO_STAGES:
            continue
        topic = shot.get('spoken_topic','')
        anchor = shot.get('anchor_text') or anchors.get(shot.get('anchor_cue_id'),'')
        boxes = [overlay.get('box') for overlay in shot.get('overlays',[]) if overlay.get('kind')=='spotlight_box']
        if shot.get('highlight_box'):
            boxes.append(shot['highlight_box'])
        elif shot.get('capture_meta'):
            highlight = read_json(root/shot['capture_meta']).get('highlight') or {}
            bounds = highlight.get('box')
            if highlight.get('status')=='located' and isinstance(bounds,dict):
                boxes.append([bounds.get(key) for key in ('x','y','width','height')])
        for asset, start, span in dict.fromkeys(shot_sources(shot)):
            suffix = Path(asset).suffix.lower()
            if suffix not in VIDEO_EXTENSIONS | {'.gif'}:
                continue
            if not isfinite(start) or not isfinite(span) or start<0 or span<=0:
                raise ValueError(f"镜头 {shot['id']} 的源片时间窗无效")
            pad = min(.3,span/4)
            times = (start+pad,start+span/2,start+span-pad)
            if suffix=='.gif':
                last = max(0.,probe_video(root/asset)-.1)
                times = tuple(min(at,last) for at in times)
            rows.append(dict(id=shot['id'],source=asset,media_start=start,play_span=span,
                             times=[round(at,5) for at in times],
                             spoken_topic=topic,anchor_text=anchor,spotlight_boxes=[box for box in boxes if box]))
    return rows


def write_verification(manifest, output):
    rows = make_verification_rows(manifest)
    font, small = contact_font(18),contact_font(15)
    pages = []
    row_height = 256
    for first in range(0,max(1,len(rows)),10):
        page = rows[first:first+10]
        image = Image.new('RGB',(1008,max(1,len(page))*row_height),'#172322')
        draw = ImageDraw.Draw(image)
        if not page:
            draw.text((12,14),'清单未声明视频镜头',font=font,fill='white')
        for index,row in enumerate(page):
            y = index*row_height+8
            label = f"{row['id']} · {row['spoken_topic']} · {Path(row['source']).name}"
            fitted_line(draw,10,y,label,988,font)
            fitted_line(draw,10,y+25,row['anchor_text'],988,small,'#b5c9a9')
            for col,at in enumerate(row['times']):
                x = 10+col*333
                frame = frame_at((manifest.parent/row['source']).resolve(),at)
                marks = ImageDraw.Draw(frame)
                for bx,by,bw,bh in row['spotlight_boxes']:
                    marks.rectangle((bx/6,by/6,(bx+bw)/6,(by+bh)/6),outline='#ff745a',width=2)
                image.paste(frame,(x,y+43))
                draw.text((x,y+226),f"{('首','中','尾')[col]} · {at:.2f}s",font=small,fill='white')
        name = 'manifest-visual-verify.jpg' if first==0 else f'manifest-visual-verify-{first//10+1:02d}.jpg'
        image.save(output/name,quality=93)
        pages.append(name)
        for row in page:
            row['page'] = name
    write_json(output/'manifest-visual-verify.json',dict(shots=rows,pages=pages,manual_review_required=True))
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('videos',nargs='*',type=Path)
    parser.add_argument('--verify-manifest',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--window',type=float,default=7.)
    parser.add_argument('--step',type=float,default=2.)
    parser.add_argument('--top',type=int,default=16)
    parser.add_argument('--include-flat',action='store_true')
    parser.add_argument('--allow-burned-subtitles',action='store_true')
    args = parser.parse_args(argv)
    if bool(args.videos)==bool(args.verify_manifest):
        parser.error('请选择视频选段或清单核验模式')
    if not all(isfinite(value) and value>0 for value in (args.step,args.window)) or args.top<1:
        parser.error('窗口、抽帧间隔和输出数量须为正数')
    args.output.mkdir(parents=True,exist_ok=True)
    try:
        if args.verify_manifest:
            count = write_verification(args.verify_manifest.resolve(),args.output)
        else:
            rows = scene_candidates(args.videos,args.window,args.step,args.top,args.include_flat,args.allow_burned_subtitles)
            write_scene_contact(rows,args.output)
            write_json(args.output/'scene-candidates.json',rows)
            count = len(rows)
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(dict(ok=True,count=count),ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
