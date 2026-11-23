#!/usr/bin/env python3
"""从声明式清单导出标准 HyperFrames 分幕工程、母带、成片与字幕。"""
import argparse
import json
from math import isfinite
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from urllib.parse import unquote

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(KIT.parent))
from audit_v7 import probe_video, semantic_binding_gate
from kit.editorial.audio_mix import mix_episode_audio
from kit.editorial.editorial import EditorialStage
from kit.studio_ui import add_workbench

FPS = 30
MODES = {'cold_open_ab','title_sequence','callout_rig','fullbleed_rig','studio_ui','explainer_clip','triptych_cards'}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(path)


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',value):
        raise ValueError('镜头和幕标识仅支持字母、数字、下划线与连字符')
    return value


def locate(root, value):
    path = (root/value).resolve()
    if not path.is_file():
        raise ValueError(f'素材不存在：{path.name}')
    return path


def prepare_cards(shot, root, span, durations):
    heading = shot.get('heading')
    cards = shot.get('cards')
    if not isinstance(heading,str) or not heading.strip() or not isinstance(cards,list) or not 2<=len(cards)<=4:
        raise ValueError('多栏舞台需要标题和两至四张卡片')
    for card in cards:
        if not isinstance(card,dict) or not isinstance(card.get('label'),str) or not card['label'].strip():
            raise ValueError('卡片需要文字标签')
        if not isinstance(card.get('sublabel',''),str) or card.get('loop') or not isinstance(card.get('source'),str):
            raise ValueError('卡片副标题或素材无效，媒体不得循环')
        path = locate(root,card['source'])
        reveal_at, media_start = float(card.get('reveal_at',float('nan'))),float(card.get('media_start',0.))
        if not 0<=reveal_at<span or not isfinite(media_start) or media_start<0:
            raise ValueError('卡片点亮时间或源入点无效')
        if path.suffix.lower()=='.mp4':
            if path not in durations:
                durations[path] = probe_video(path)
            if durations[path]+1e-5 < media_start+span-reveal_at+.2:
                raise ValueError(f'卡片源视频不足以覆盖切片及 0.2 秒余量：{path.name}')
        elif path.suffix.lower() not in {'.png','.jpg','.jpeg'}:
            raise ValueError('卡片素材须为 PNG、JPEG 或 MP4')
        yield dict(card,source=str(path),reveal_at=reveal_at,media_start=media_start)


def prepare_document(raw, root):
    audio = dict(raw.get('audio',{}))
    timing = raw.get('cues',raw.get('voice_timing'))
    if isinstance(timing,str):
        timing = read(locate(root,timing))
    if 'voice_manifest' in raw:
        path = locate(root,raw['voice_manifest'])
        voice = read(path)
        audio.setdefault('voice_tracks',[dict(id=row['id'],path=str(path.parent/row.get('audio',row.get('path'))),
                    at=row['start']) for row in voice['chapters']])
        audio.setdefault('voice_processing_logs',[str(item) for item in sorted((path.parent/'analysis').glob('post-alignment-*.json'))])
        timing = timing or voice.get('scene_timing')
    if not isinstance(timing,list) or not timing:
        raise ValueError('清单需要已有音轨的首字时间 cues')
    cues = {row['id']:dict(row,firstCharTime=float(row['firstCharTime'])) for row in timing}
    if len(cues)!=len(timing) or any(not isfinite(row['firstCharTime']) or row['firstCharTime']<0 for row in cues.values()):
        raise ValueError('首字锚点重复或时间无效')
    if not audio.get('voice_tracks'):
        raise ValueError('清单需要实际人声音轨 voice_tracks 或 voice_manifest')
    for row in audio['voice_tracks']:
        row['path'] = str(locate(root,row['path']))
    captions = raw.get('captions',timing)
    if isinstance(captions,str):
        captions = read(locate(root,captions))
    cues_list = []
    for row in captions:
        start = float(row['startMs'])/1000 if 'startMs' in row else float(row.get('firstCharTime',row.get('start')))
        end = float(row['endMs'])/1000 if 'endMs' in row else float(row['end'])
        if not isfinite(start) or not isfinite(end) or not 0 <= start < end or not str(row['text']).strip():
            raise ValueError('字幕时间窗或文字无效')
        cues_list.append(dict(start=start,end=end,text=row['text']))
    if not cues_list:
        raise ValueError('缺少可导出的字幕行')
    return audio,cues,sorted(cues_list,key=lambda row:row['start'])


def prepare_shots(raw, root, cues):
    previous = 0.
    result = []
    known, seen_acts, durations = set(),set(),{}
    for src in raw['shots']:
        key,act = identifier(src['id']),identifier(src.get('act','act-1'))
        a,b = float(src['start']),float(src['end'])
        if not all(isfinite(v) for v in (a,b)) or min(a,b)<0:
            raise ValueError(f'镜头 {key} 时间无效')
        start,end = round(a*FPS)/FPS,round(b*FPS)/FPS
        if key in known or abs(start-previous)>1e-5 or end<=start:
            raise ValueError(f'镜头 {key} 重复、断档或重叠')
        if result and act!=result[-1]['act'] and act in seen_acts:
            raise ValueError('同一幕的镜头须连续')
        known.add(key)
        seen_acts.add(act)
        previous = end
        cue = cues.get(src['anchor_cue_id'])
        if cue is None or abs(start-cue['firstCharTime'])>.220001:
            raise ValueError(f'镜头 {key} 与首字锚点相差超过 0.22 秒')
        mode = src['stage_mode']
        if mode not in MODES or src.get('loop'):
            raise ValueError(f'镜头 {key} 的舞台模式或循环方式无效')
        files = src.get('sources')
        if files is None:
            one = src.get('source',src.get('asset'))
            files = [one] if one else []
        media = [locate(root,value) for value in files]
        if mode=='triptych_cards':
            cards = list(prepare_cards(src,root,end-start,durations))
            src = dict(src,cards=cards)
            media = [Path(card['source']) for card in cards]
        media_start = float(src.get('media_start',0.))
        if not isfinite(media_start) or media_start<0:
            raise ValueError(f'镜头 {key} 的源入点不合法')
        expected = {'cold_open_ab':2,'callout_rig':1,'fullbleed_rig':1}.get(mode)
        if expected is not None and len(media)!=expected:
            raise ValueError(f'镜头 {key} 需要 {expected} 条视频源')
        if expected:
            for path in media:
                if path not in durations:
                    durations[path] = probe_video(path)
                if durations[path]+1e-5 < media_start+end-start+.2:
                    raise ValueError(f'镜头 {key} 源视频不足以覆盖切片及 0.2 秒余量')
        result.append(dict(src,id=key,act=act,start=start,end=end,media=media,media_start=media_start,
                           anchor_text=cue.get('text',''),anchor_cue_start=cue['firstCharTime'],
                           has_motion_overlay=(mode in {'callout_rig','studio_ui'} and bool(src.get('overlays'))
                                               or mode in {'cold_open_ab','title_sequence','triptych_cards'})))
    if not result:
        raise ValueError('清单至少需要一个镜头')
    if 'duration' in raw and abs(float(raw['duration'])-previous)>1/FPS:
        raise ValueError('声明片长与最后一个镜头不吻合')
    semantic = semantic_binding_gate(result)
    if not semantic['ok']:
        raise ValueError('语义绑定不符：'+json.dumps(semantic['violations'],ensure_ascii=False))
    return result,previous


def install_asset(source, target):
    source,target = Path(source),Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.samefile(source):
        return target
    staging = target.with_suffix(target.suffix+'.tmp')
    try:
        if staging.exists():
            staging.unlink()
        os.link(source,staging)
    except OSError:
        shutil.copy2(source,staging)
    staging.replace(target)
    return target


def gsap_runtime(raw, root):
    provided = raw.get('gsap') or os.environ.get('YICE_GSAP_PATH')
    if provided:
        return locate(root,provided)
    proc = subprocess.run(['node','-p',"require.resolve('gsap/dist/gsap.min.js')"],cwd=root,
                          capture_output=True,text=True)
    if proc.returncode:
        raise ValueError('请通过清单 gsap 或 YICE_GSAP_PATH 提供本地 GSAP 运行时')
    return locate(root,proc.stdout.strip())


def restore_file_paths(value):
    """Keep rebased paths local until the explainer opens its own file server."""
    if isinstance(value,dict):
        return {key:restore_file_paths(item) for key,item in value.items()}
    if isinstance(value,list):
        return [restore_file_paths(item) for item in value]
    if isinstance(value,str) and value.startswith('/__file__/'):
        return unquote(value.removeprefix('/__file__/'))
    return value


def explainer(shot, root, folder, run):
    spec_source = shot['spec']
    if isinstance(spec_source,str):
        spec_file = locate(root,spec_source)
        spec,base = read(spec_file), spec_file.parent
    else:
        spec,base = dict(spec_source),root
    # Resolve sources before moving the adjusted spec to the act directory.
    from importlib.util import spec_from_file_location,module_from_spec
    loader = spec_from_file_location('explainer_spec_assets',KIT/'explainer/spec_assets.py')
    assets = module_from_spec(loader)
    loader.loader.exec_module(assets)
    spec = restore_file_paths(assets.localize(spec,base,allowed=set()))
    span = shot['end']-shot['start']
    cues = spec['cues']
    latest = max((float(row['at']) for row in cues),default=0.)
    scale = min(1.,span*.72/latest) if latest else 1.
    for row in cues:
        row['at'] = round(float(row['at'])*scale,5)
    spec.update(duration=round(span+.35,6),fps=FPS,width=1920,height=1080)
    target = folder/'assets'/f"exp-{shot['id']}.mp4"
    target.parent.mkdir(parents=True,exist_ok=True)
    config = target.with_suffix('.json')
    write(config,spec)
    run(['bash',str(KIT/'scripts/render-explainer-clip.sh'),'--spec',str(config),'--out',str(target)],check=True)
    if probe_video(target)+1/FPS < span+.35:
        raise ValueError(f"解说动效未覆盖镜头时长：{shot['id']}")
    return target.relative_to(folder).as_posix(),spec


def build_act(shots, root, folder, title, run):
    first,last = shots[0]['start'],shots[-1]['end']
    stage = EditorialStage(title,duration=last-first,fps=FPS)
    for shot in shots:
        mode,key = shot['stage_mode'],shot['id']
        a,b = shot['start']-first,shot['end']-first
        assets = [install_asset(path,folder/'assets'/f'{key}-{i}{path.suffix.lower()}').relative_to(folder).as_posix()
                  for i,path in enumerate(shot['media'])]
        text = shot['spoken_topic']
        start = shot['media_start']
        if mode == 'cold_open_ab':
            hook = shot.get('hook',text)
            stage.add_cold_open_ab(a,b,*assets,hook=hook,labels=shot.get('labels',('A','B')),
                                   countdown=shot.get('countdown',3),media_start=start)
        elif mode == 'title_sequence':
            stage.add_title_sequence(a,b,shot.get('title',text),subtitle=shot.get('subtitle',''),
                                     highlight=shot.get('highlight',''),brand=shot.get('brand','一策'),paper=shot.get('paper',False))
        elif mode == 'callout_rig':
            stage.add_callout_rig(a,b,assets[0],overlays=shot['overlays'],media_start=start,motion=shot.get('motion','glide'))
        elif mode == 'fullbleed_rig':
            stage.add_fullbleed_rig(a,b,assets[0],media_start=start,motion=shot.get('motion','glide'))
        elif mode == 'studio_ui':
            data = dict(shot['data'])
            data['evidence'] = assets
            if 'monitor' in data:
                monitor = locate(root,data['monitor'])
                if probe_video(monitor)<b-a+.2:
                    raise ValueError(f'工程台监视器视频过短：{key}')
                data['monitor'] = install_asset(monitor,folder/'assets'/f'{key}-monitor{monitor.suffix}').relative_to(folder).as_posix()
            add_workbench(stage,a,b,shot['studio_style'],shot.get('title',text),data)
            if shot.get('overlays'):
                stage.add_overlays(a,b,shot['overlays'])
        elif mode == 'triptych_cards':
            cards = [dict(card,source=asset) for card,asset in zip(shot['cards'],assets)]
            stage.add_triptych_cards(a,b,heading=shot['heading'],cards=cards)
        else:
            clip,spec = explainer(shot,root,folder,run)
            stage.add_video(a,b,clip,0,0,1920,1080,fit='cover')
            stage._shot(text,'explainer_graphic',a,b,[clip],beats=[r['at'] for r in spec['cues']])
            stage.shots[-1]['grammar'] = spec['grammar']
            if spec['grammar']=='t6_swiss_card':
                stage.light_zones.append((a,b))
        fields = ('anchor_cue_id','anchor_cue_start','anchor_text','spoken_topic','visual_subject',
                  'semantic_binding','binding','semantic_tags','spoken_entity','topic_kind','overlays','media_start')
        stage.shots[-1].update({field:shot[field] for field in fields if field in shot},id=key,stage_mode=mode)
    return stage


def clock(seconds):
    h, rest = divmod(round(seconds*1000),3600000)
    m, rest = divmod(rest,60000)
    s, ms = divmod(rest,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def assemble(manifest, output, *, build_only=False, run=subprocess.run):
    import soundfile as sf
    from itertools import groupby

    manifest,output = Path(manifest).resolve(),Path(output).resolve()
    raw = read(manifest)
    root = manifest.parent
    audio,cues,captions = prepare_document(raw,root)
    shots,duration = prepare_shots(raw,root,cues)
    if any(row['end']>duration+1/FPS for row in captions):
        raise ValueError('字幕超出全片时长')
    name = raw.get('filename','episode')
    if not isinstance(name,str) or not name.strip() or Path(name).name!=name or name in ('.','..'):
        raise ValueError('成片文件名须为单个文件名')
    gsap = gsap_runtime(raw,root)
    output.mkdir(parents=True,exist_ok=True)
    stages,marks,global_shots = [],[],[]
    for act,items in groupby(shots,key=lambda row:row['act']):
        items = list(items)
        folder = output/'acts'/act
        folder.mkdir(parents=True,exist_ok=True)
        offset = items[0]['start']
        stage = build_act(items,root,folder,raw.get('title',name),run)
        stages.append((folder,stage,offset))
        marks.extend(dict(kind=kind,at=round(offset+at,5)) for kind,at in stage.sound_marks)
        for row in stage.shots:
            files = [(folder/p).relative_to(output).as_posix() for p in row['files']]
            global_row = dict(row,start=round(offset+row['start'],5),end=round(offset+row['end'],5),files=files)
            if row['stage_mode']=='triptych_cards':
                global_row['cards'] = [dict(card,source=file) for card,file in zip(row['cards'],files)]
            global_shots.append(global_row)
    cuts = None
    music = audio.get('bgm',[])
    if 1<len(music)<=len(stages):
        cuts = [stages[round(i*len(stages)/len(music))][2] for i in range(1,len(music))]
    mix = mix_episode_audio(audio,duration,output,root=root,sound_marks=marks,bgm_cuts=cuts)
    voice_files = []
    for i,row in enumerate(audio['voice_tracks']):
        src = Path(row['path'])
        saved = install_asset(src,output/'voice'/f'track-{i+1}{src.suffix}')
        voice_files.append(dict(id=row.get('id',str(i+1)),path=saved.relative_to(output).as_posix(),at=row.get('at',0)))
    voice_logs = [install_asset(locate(root,path),output/'voice'/'analysis'/f'source-log-{i+1}.json').relative_to(output).as_posix()
                  for i,path in enumerate(audio.get('voice_processing_logs',[]))]
    timeline = dict(end=duration,shots=global_shots,cues=list(cues.values()),voice_tracks=voice_files,
                    voice_processing_logs=voice_logs,sound_marks=mix['sound_marks'],music_drops=audio.get('music_drops',[]))
    timeline['music_drops'] = [[row['start'],row['end']] if isinstance(row,dict) else row for row in timeline['music_drops']]
    write(output/'shot-timeline.json',timeline)
    (output/f'{name}.srt').write_text('\n'.join(f"{i}\n{clock(c['start'])} --> {clock(c['end'])}\n{c['text']}\n"
                                                  for i,c in enumerate(captions,1)))
    wave,rate = sf.read(output/'mix.wav',dtype='float32')
    command = shlex.split(os.environ.get('YICE_HYPERFRAMES_BIN','npx --offline hyperframes'))
    env = {**os.environ,'HYPERFRAMES_TELEMETRY_DISABLED':'1','DO_NOT_TRACK':'1'}
    for folder,stage,offset in stages:
        stop = offset+stage.duration
        local = [dict(text=row['text'],start=max(offset,row['start'])-offset,end=min(stop,row['end'])-offset)
                 for row in captions if max(offset,row['start'])<min(stop,row['end'])]
        stage.add_captions(local)
        install_asset(gsap,folder/'vendor/gsap.min.js')
        stage.write_project(folder,timeline_out=folder/'shot-timeline.json')
        (folder/'assets').mkdir(exist_ok=True)
        sf.write(folder/'assets/mix.wav',wave[round(offset*rate):round(stop*rate)],rate,subtype='PCM_24')
        if not build_only:
            run(command+['check','.'],cwd=folder,env=env,check=True)
            run(command+['render','.','--fps',str(FPS),'--quality','looks','--output','render.mp4'],
                cwd=folder,env=env,check=True)
    result = dict(ok=True,duration=duration,acts=len(stages),shots=len(shots),timeline='shot-timeline.json',srt=f'{name}.srt')
    if not build_only:
        concat = output/'acts.ffconcat'
        concat.write_text('ffconcat version 1.0\n'+''.join(
            f"file '{folder.relative_to(output).as_posix()}/render.mp4'\nduration {stage.duration:.9f}\n"
            for folder,stage,_ in stages))
        staged = output/f'{name}.pending.mp4'
        run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(concat),
             '-i',str(output/'mix.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy',
             '-c:a','aac','-b:a','256k','-movflags','+faststart','-shortest',str(staged)],check=True)
        staged.replace(output/f'{name}.mp4')
        result['mp4'] = f'{name}.mp4'
    write(output/'assembly-report.json',result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--build-only',action='store_true',help='生成分幕工程和母带，跳过浏览器渲染')
    args = parser.parse_args(argv)
    try:
        result = assemble(args.manifest,args.output,build_only=args.build_only)
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
