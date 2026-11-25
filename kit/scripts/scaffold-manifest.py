#!/usr/bin/env python3
"""根据已有旁白时间轴生成可装配的分镜清单草稿。"""
import argparse
import json
from math import isfinite
import os
from pathlib import Path

FPS = 30


def scaffold(manifest, timing, output, title):
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
    shots = []
    for i,(start,cue) in enumerate(cuts):
        end = cuts[i+1][0] if i+1<len(cuts) else duration
        text = cue['text']
        shots.append(dict(id=f'shot-{i+1:02}',act='act-1',start=start,end=end,anchor_cue_id=cue['id'],
                          stage_mode='explainer_clip',spoken_topic=text,visual_subject='待替换素材的分镜占位',
                          semantic_binding='conceptual_explainer',semantic_tags=['分镜草稿'],
                          spec=dict(grammar='t7_editorial_board',data={'title':'画面待补'},
                                    cues=[dict(kind='card',at=0.,text=text)])))
    anchors = [cue for _,cue in cuts]
    used = {cue['id'] for cue in anchors}
    anchors.extend(cue for cue in cues if cue['id'] not in used)
    result = dict(title=title,filename='episode',duration=duration,cues=sorted(anchors,key=lambda cue:cue['firstCharTime']),
                  voice_manifest=os.path.relpath(manifest,output.parent),shots=shots)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voice-manifest',required=True,type=Path)
    parser.add_argument('--voice-timing',type=Path)
    parser.add_argument('--output',type=Path,default=Path('episode-manifest.json'))
    parser.add_argument('--title',default='分镜草稿')
    args = parser.parse_args()
    try:
        result = scaffold(args.voice_manifest.resolve(),args.voice_timing,args.output.resolve(),args.title)
    except (OSError,TypeError,ValueError,KeyError) as error:
        parser.error(str(error))
    print(json.dumps(dict(path=str(args.output.resolve()),duration=result['duration'],shots=len(result['shots'])),ensure_ascii=False))


if __name__=='__main__':
    main()
