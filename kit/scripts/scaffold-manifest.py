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


def draft_stage(index, span=5, *, chapter_title=None):
    """Use actual media slots throughout. The producer fills their subjects from the script."""
    prefix = f'media/shot-{index+1:02}'
    def spatial(recipe, data, look='swiss_paper'):
        return dict(stage_mode='hyperframes_block', visual_mode='M1', stage_look=look,
                    spatial_spec=dict(recipe=recipe, stage_look=look, data=data),
                    semantic_binding='conceptual_explainer', visual_subject='待填实际作品与可见动作')
    if chapter_title is not None:
        return spatial('kinetic_title_bridge',dict(words=[dict(text=chapter_title[:10],at=0.)],
                                                    underline_at=.38))
    if index == 0:
        return spatial('triptych_curtain',dict(videos=[f'{prefix}-{n}.mp4' for n in (1,2,3)],
                    words=[dict(text='作品成果',at=0.,line=1),dict(text='本期方法',at=min(.38,span*.35),line=2)],
                    underline_at=min(.78,span*.55)), 'cinema_black')
    slot=index%9
    if slot in (1,6):
        return dict(stage_mode='onetake_clip',visual_mode='M3',shutter=180,look='dusk',
                    onetake_spec=dict(recipe='split_wipe_compare',stage_look='cinema_black',
                    data=dict(mode='center_scan',before=prefix+'-before.mp4',after=prefix+'-after.mp4')),
                    semantic_binding='conceptual_explainer',visual_subject='待填前后对比证据')
    if slot==3:
        return spatial('progressive_sim_cards',dict(board=True, heading='案例对照',
            cards=[dict(source=f'{prefix}-{n+1}.mp4',label=label,at=round(span*f,3))
                   for n,(label,f) in enumerate(zip(('第一项','第二项','第三项'),(.01,.34,.65)))]))
    if slot==5:
        return spatial('logo_bento_stage',dict(expected_items=3,brand=dict(name='工具分类'),
            modules=[dict(category=label,at=round(span*f,3),items=[dict(name=name,at=round(span*(f+.10),3))])
                     for label,name,f in [('制作','工具一',.02),('展示','工具二',.29),('交付','工具三',.61)]]))
    if slot==8:
        return spatial('step_tree_focus',dict(heading='操作步骤',branches=[
            dict(no='①',title='准备',at=.05,children=[dict(label='输入',at=round(span*.20,3))]),
            dict(no='②',title='核对结果',at=round(span*.55,3))],
            focus_sequence=[dict(index=i,at=round(span*f,3)) for i,f in [(0,.2),(1,.55),(0,.83)]]))
    result=dict(stage_mode='fullbleed_rig',visual_mode='M2',framing='fullbleed',motion='focus_push',
                source=prefix+'.mp4',semantic_binding='exact_tool_capture',visual_subject='待填实录动作和结果')
    if slot==4 and span>=1.2:
        result['overlays']=[dict(kind='editorial_punch',label='一句结论',lines=['一句结论'],at=round(span*.35,3))]
    return result


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
    chapters = voice.get('chapters', [])
    bridges = {}
    for chapter in chapters[1:]:
        start = float(chapter['start'])
        idx = next((n for n,(at,_) in enumerate(expanded) if at >= start-.05),None)
        if idx is None: continue
        at,anchor = expanded[idx]
        stop = expanded[idx+1][0] if idx+1 < len(expanded) else duration
        if stop-at < 2.6: continue
        within = [t for t,_ in lines if 1.2 <= t-at <= 1.8]
        end = round((min(within,key=lambda t:abs(t-at-1.5)) if within else at+1.5)*FPS)/FPS
        bridges[anchor['id']] = str(chapter.get('title') or anchor['text'])
        follow = dict(id=anchor['id']+'-body',firstCharTime=end,end=stop,
                      text=''.join(v for t,v in lines if end-.001<=t<stop-.001) or anchor['text'])
        expanded.insert(idx+1,(end,follow))
    cuts = expanded
    shots = []
    for i,(start,cue) in enumerate(cuts):
        end = cuts[i+1][0] if i+1<len(cuts) else duration
        stage = draft_stage(i,end-start,chapter_title=bridges.get(cue['id']))
        chapter = next((str(c['id']) for c in reversed(chapters) if start >= float(c['start'])-.05),'01')
        shot = dict(id=f'shot-{i+1:02}',act='act-'+chapter,chapter=chapter,case_tag='待填案例',case_windows=[dict(tag='待填案例',start=0.,end=round(end-start,5))],start=start,end=end,anchor_cue_id=cue['id'],
                    spoken_topic=cue['text'],semantic_tags=['分镜草稿'],**stage)
        if end-start > (6.2 if lines else 6.5):
            shot['needs_subcut'] = True
        shots.append(shot)
    anchors = [cue for _,cue in cuts]
    used = {cue['id'] for cue in anchors}
    anchors.extend(cue for cue in cues if cue['id'] not in used)
    ledger = output.with_name('semantic-alignment.json')
    if ledger.exists():
        ledger = output.with_name(output.stem+'.semantic-alignment.json')
    if ledger.exists():
        raise FileExistsError(f'画面账本已存在：{ledger}')
    result = dict(version='v14.0',review_pack=True,episode_kind='tool_tutorial',theme='obsidian',semantic_alignment=ledger.name,
                  audio=dict(bgm=['builtin:forward-drive','builtin:city-groove','builtin:bright-step'],
                             bgm_cuts=[round(duration*f,3) for f in (1/3,2/3)],crossfade=min(5,duration/12)),
                  title=title,filename='episode',duration=duration,cues=sorted(anchors,key=lambda cue:cue['firstCharTime']),
                  voice_manifest=os.path.relpath(manifest,output.parent),shots=shots)
    if captions:
        result['captions'] = os.path.relpath(captions,output.parent)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    rows = [dict(shot_id=s['id'],start=s['start'],end=s['end'],quote=s['spoken_topic'],case_tag=s['case_tag'],
                 case_windows=s['case_windows'],evidence=s['visual_subject']) for s in shots]
    with ledger.open('x',encoding='utf-8') as stream:
        json.dump(rows,stream,ensure_ascii=False,indent=2)
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
