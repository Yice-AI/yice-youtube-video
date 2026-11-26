#!/usr/bin/env python3
"""根据已有旁白时间轴生成可装配的分镜清单草稿。"""
import argparse
import json
from math import isfinite
import os
from pathlib import Path

FPS = 30


def caption_cuts(start, end, captions):
    """Choose a complete path through subtitle starts, closest to five seconds per shot."""
    points = {round(at * FPS): at for at, _ in captions if start < at < end}
    first, last = round(start * FPS), round(end * FPS)
    cost, previous = {first: 0.}, {}
    for frame in sorted(set(points) | {last}):
        choices = [(cost[left] + ((frame-left)/FPS-5)**2, left)
                   for left in range(frame-6*FPS, frame-105+1) if left in cost]
        if choices:
            cost[frame], previous[frame] = min(choices)
    if last not in previous:
        return []
    result = []
    frame = previous[last]
    while frame != first:
        result.append(points[frame])
        frame = previous[frame]
    return list(reversed(result))


def draft_stage(index, span=5):
    key = f'shot-{index+1:02}'
    beat = index % 10
    route = ('M1', 'M3', 'M2', 'M3', 'M2', 'M1', 'M2', 'M3', 'M2', 'M3')[beat]
    images = [f'media/{key}-{n}.png' for n in range(1,6)]
    if route == 'M1':
        if beat == 0:
            spec = dict(recipe='carousel_3d_select', hud='素材选择',
                        data=dict(images=images,selected_index=0,select_at=round(max(.3,min(span-.35,span*.42)),3)))
        else:
            spec = dict(recipe='layer_explode_3d', hud='图层拆解',
                        data=dict(image=images[0],boxes=[[.1,.15,.5,.1]],count=1))
        return dict(stage_mode='hyperframes_block', visual_mode=route, spatial_spec=spec,
                    semantic_binding='conceptual_explainer', visual_subject='待填本片真实截图与结构')
    if route == 'M3':
        if beat == 1:
            spec = dict(recipe='duplicate_laser_sweep',hud='版式检查',
                        data=dict(cards=['开场','过程','结果'],series='布局',caption='待填实际例子'))
        elif beat == 3:
            spec = dict(recipe='live_control_sync',hud='实时预览',
                        data=dict(image=images[0],slider='强度',switch='动态预览',canvas='画布'))
        elif beat == 7:
            spec = dict(recipe='energy_roadmap_dive',hud='操作路线',
                        data=dict(stations=[dict(image=path,label=title) for path,title in
                                            zip(images,('准备','制作','交付'))],target=0))
        else:
            spec = dict(recipe='capsule_archive_seal',hud='交付',
                        data=dict(images=images[:3],project='项目',file='SKILL.md',command='open ./output'))
        return dict(stage_mode='onetake_clip', visual_mode=route, onetake_spec=spec,
                    shutter=180, look='dusk' if beat in (1, 7) else 'ember',
                    semantic_binding='conceptual_explainer', visual_subject='待填本片真实操作与结果')
    return dict(stage_mode='fullbleed_rig', visual_mode=route, framing='fullbleed', motion='focus_push',
                source=f'media/{key}.mp4', semantic_binding='exact_tool_capture', visual_subject='待录制满屏操作与结果')


def scaffold(manifest, timing, output, title, captions=None):
    if captions is None and (manifest.parent/"captions.json").is_file():
        captions = manifest.parent/"captions.json"
    lines = sorted((float(r["startMs"])/1000 if "startMs" in r else float(r["start"]), str(r["text"]))
                   for r in json.loads(captions.read_text())) if captions else []
    voice = json.loads(manifest.read_text())
    if timing is None and (manifest.parent/'voice-timing.json').is_file():
        timing = manifest.parent/'voice-timing.json'
    rows = json.loads(timing.read_text()) if timing else voice['scene_timing']
    total = float(voice['total_duration'])
    if not isinstance(rows,list) or not rows or not isfinite(total) or total<=0:
        raise ValueError('旁白清单须包含有效时长和首字时间')
    duration = max(1,round(total*FPS))/FPS
    rows = sorted(rows,key=lambda row:float(row['firstCharTime']))
    cues, cuts = [], []
    ids = set()
    for i,row in enumerate(rows):
        at = float(row['firstCharTime'])
        key = str(row['id'])
        if key in ids or not isfinite(at) or not 0<=at<duration:
            raise ValueError(f'首字时间或编号无效：{key}')
        ids.add(key)
        nxt = float(rows[i+1]['firstCharTime']) if i+1<len(rows) else duration
        end = min(duration,float(row.get('end',nxt)))
        if end<=at:
            end = min(duration,at+1/FPS)
        cue = dict(id=key,firstCharTime=at,end=end,text=str(row.get('text') or '待补旁白文字'))
        cues.append(cue)
        cut = round(at*FPS)/FPS
        if cut<duration and (not cuts or cut>cuts[-1][0]):
            cuts.append((cut,cue))
    if not cuts:
        raise ValueError('旁白时间轴未形成有效镜头')
    if cuts[0][0]<=.22:
        cuts[0] = (0.,cuts[0][1])
    else:
        opening = 'opening-lead'
        while opening in ids:
            opening += '-lead'
        cuts.insert(0,(0.,dict(id=opening,firstCharTime=0.,end=cuts[0][0],text='开场')))
    expanded = []
    for i,(start,cue) in enumerate(cuts):
        end = cuts[i+1][0] if i+1<len(cuts) else duration
        subcuts = caption_cuts(start,end,lines) if lines and end-start > 6.2 else []
        for j,at in enumerate([start,*subcuts]):
            anchor = cue
            if subcuts:
                key = f"{cue['id']}-{j+1}"
                while key in ids:
                    key += '-sub'
                ids.add(key)
                stop = (subcuts+[end])[j]
                words = ''.join(text for t,text in lines if at-1e-6 <= t < stop-1e-6)
                anchor = dict(id=key,firstCharTime=at if j else cue['firstCharTime'],end=stop,text=words or cue['text'])
            expanded.append((round(at*FPS)/FPS,anchor))
    cuts = expanded
    shots = []
    for i,(start,cue) in enumerate(cuts):
        end = cuts[i+1][0] if i+1<len(cuts) else duration
        stage = draft_stage(i,end-start)
        shot = dict(id=f'shot-{i+1:02}',act='act-1',start=start,end=end,anchor_cue_id=cue['id'],
                    spoken_topic=cue['text'],semantic_tags=['分镜草稿'],**stage)
        if end-start > (6.2 if lines else 6.5):
            shot['needs_subcut'] = True
        shots.append(shot)
    anchors = [cue for _,cue in cuts]
    used = {cue['id'] for cue in anchors}
    anchors.extend(cue for cue in cues if cue['id'] not in used)
    result = dict(title=title,filename='episode',duration=duration,cues=sorted(anchors,key=lambda cue:cue['firstCharTime']),
                  voice_manifest=os.path.relpath(manifest,output.parent),shots=shots)
    if captions:
        result['captions'] = os.path.relpath(captions,output.parent)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voice-manifest',required=True,type=Path)
    parser.add_argument('--voice-timing',type=Path)
    parser.add_argument('--captions',type=Path)
    parser.add_argument('--output',type=Path,default=Path('episode-manifest.json'))
    parser.add_argument('--title',default='分镜草稿')
    args = parser.parse_args()
    try:
        result = scaffold(args.voice_manifest.resolve(),args.voice_timing,args.output.resolve(),args.title,args.captions)
    except (OSError,TypeError,ValueError,KeyError) as error:
        parser.error(str(error))
    print(json.dumps(dict(path=str(args.output.resolve()),duration=result['duration'],shots=len(result['shots'])),ensure_ascii=False))


if __name__=='__main__':
    main()
