#!/usr/bin/env python3
"""从声明式清单导出标准 HyperFrames 分幕工程、母带、成片与字幕。"""
import argparse
import copy
import hashlib
import json
from math import ceil, isfinite
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote
from xml.etree import ElementTree

from PIL import Image

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(KIT.parent))
from audit_v7 import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, probe_video, semantic_binding_gate
from workspace import resolve_gsap_runtime, resolve_hyperframes_command
from kit.editorial.audio_mix import mix_episode_audio
from kit.editorial.editorial import EditorialStage, EXPLAINER_THEMES, FONT_FILES, PALETTES, evidence_box
from kit.studio_ui import add_workbench

FPS = 30
MODES = {'cold_open_ab','title_sequence','callout_rig','fullbleed_rig','studio_ui','explainer_clip','triptych_cards','reference_breakdown','evidence_spotlight'}
SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
LOGO_EXTENSIONS = {'.svg','.png','.webp'}


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
        validate_media(path,media_start+span-reveal_at,durations,allow_image=True)
        yield dict(card,source=str(path),reveal_at=reveal_at,media_start=media_start)


def validate_media(path, length, durations, *, allow_image=False):
    suffix = path.suffix.lower()
    if suffix=='.gif' or (allow_image and suffix in IMAGE_EXTENSIONS):
        return
    if suffix not in VIDEO_EXTENSIONS:
        raise ValueError(f'舞台素材格式不支持：{path.name}')
    if path not in durations:
        durations[path] = probe_video(path)
    if durations[path]+1e-5 < length+.2:
        raise ValueError(f'源视频不足以覆盖切片及 0.2 秒余量：{path.name}')


def evidence_metadata(shot, root):
    box = shot.get('highlight_box')
    credit = shot.get('source_credit')
    if shot.get('capture_meta'):
        capture = read(locate(root,shot['capture_meta']))
        credit = credit or capture.get('sourceName')
        highlight = capture.get('highlight') or {}
        if box is None and highlight.get('status')=='located' and isinstance(highlight.get('box'),dict):
            bounds = highlight['box']
            try:
                box = evidence_box([bounds[key] for key in ('x','y','width','height')])
            except (KeyError,ValueError):
                pass
    return dict(shot,highlight_box=box,source_credit=credit or '')


def prepare_document(raw, root):
    audio = dict(raw.get('audio',{}))
    timing = raw.get('cues',raw.get('voice_timing'))
    captions_default = None
    if isinstance(timing,str):
        timing = read(locate(root,timing))
    if 'voice_manifest' in raw:
        path = locate(root,raw['voice_manifest'])
        voice = read(path)
        audio.setdefault('voice_tracks',[dict(id=row['id'],path=str(path.parent/row.get('audio',row.get('path'))),
                    at=row['start']) for row in voice['chapters']])
        audio.setdefault('voice_processing_logs',[str(item) for item in sorted((path.parent/'analysis').glob('post-alignment-*.json'))])
        timing = timing or voice.get('scene_timing')
        if (path.parent/'captions.json').is_file():
            captions_default = str(path.parent/'captions.json')
    if not isinstance(timing,list) or not timing:
        raise ValueError('清单需要已有音轨的首字时间 cues')
    cues = {row['id']:dict(row,firstCharTime=float(row['firstCharTime'])) for row in timing}
    if len(cues)!=len(timing) or any(not isfinite(row['firstCharTime']) or row['firstCharTime']<0 for row in cues.values()):
        raise ValueError('首字锚点重复或时间无效')
    if not audio.get('voice_tracks'):
        raise ValueError('清单需要实际人声音轨 voice_tracks 或 voice_manifest')
    for row in audio['voice_tracks']:
        row['path'] = str(locate(root,row['path']))
    captions = raw.get('captions',captions_default or timing)
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
    default_theme = raw.get('theme','pine')
    if default_theme not in PALETTES:
        raise ValueError(f'未知舞台主题：{default_theme}')
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
        theme = src.get('theme',default_theme)
        if theme not in PALETTES:
            raise ValueError(f'未知舞台主题：{theme}')
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
        expected = {'cold_open_ab':2,'callout_rig':1,'fullbleed_rig':1,'reference_breakdown':1,'evidence_spotlight':1}.get(mode)
        if expected is not None and len(media)!=expected:
            raise ValueError(f'镜头 {key} 需要 {expected} 条素材源')
        if expected:
            for path in media:
                validate_media(path,media_start+end-start,durations,allow_image=mode=='evidence_spotlight')
        if mode=='evidence_spotlight':
            src = evidence_metadata(src,root)
        result.append(dict(src,id=key,act=act,start=start,end=end,media=media,media_start=media_start,theme=theme,
                           anchor_text=cue.get('text',''),anchor_cue_start=cue['firstCharTime'],
                           has_motion_overlay=(mode in {'callout_rig','studio_ui'} and bool(src.get('overlays'))
                                               or mode in {'cold_open_ab','title_sequence','triptych_cards','reference_breakdown','evidence_spotlight'})))
    if not result:
        raise ValueError('清单至少需要一个镜头')
    if 'duration' in raw and abs(float(raw['duration'])-previous)>1/FPS:
        raise ValueError('声明片长与最后一个镜头不吻合')
    semantic = semantic_binding_gate(result,raw.get('custom_entities'))
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


def sanitized_svg(source):
    raw = source.read_text(encoding='utf-8-sig')
    if re.search(r'<\s*!(?:DOCTYPE|ENTITY)\b',raw,re.I):
        raise ValueError(f'SVG 含不安全的文档声明：{source.name}')
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise ValueError(f'SVG 格式无效：{source.name}') from error
    if root.tag not in {'svg',f'{{{SVG_NAMESPACE}}}svg'}:
        raise ValueError(f'SVG 根节点无效：{source.name}')
    for element in root.iter():
        tag = element.tag.rsplit('}',1)[-1].lower()
        attributes = {key.rsplit('}',1)[-1].lower():value for key,value in element.attrib.items()}
        values = list(element.attrib.values())
        if tag=='style':
            values.append(element.text or '')
        urls = (match.group(1).strip().strip("'\"").strip() for value in values
                for match in re.finditer(r'url\s*\(([^)]*)\)',value,re.I))
        if (tag in {'script','foreignobject','iframe','object','embed','animate','set','animatetransform','animatemotion'}
                or any(key.startswith('on') for key in attributes)
                or any(re.search(r'https?\s*://|javascript\s*:|@import',value,re.I) for value in values)
                or any(not re.fullmatch(r'#[^\s]+|data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=\s]+',value.strip(),re.I)
                       for key,value in attributes.items() if key in {'href','src'})
                or any(not url.startswith('#') for url in urls)):
            raise ValueError(f'SVG 含不安全元素或外部引用：{source.name}')
        if ('{http://www.w3.org/XML/1998/namespace}base' in element.attrib
                or any('\\' in value for value in values)):
            raise ValueError(f'SVG 含不安全样式：{source.name}')
        if not element.tag.startswith('{'):
            element.tag = f'{{{SVG_NAMESPACE}}}{element.tag}'
    ElementTree.register_namespace('',SVG_NAMESPACE)
    return ElementTree.tostring(root,encoding='utf-8',xml_declaration=True)


def install_visual(source, target_base, *, length=0., run=subprocess.run):
    suffix = source.suffix.lower()
    target = target_base.with_suffix({'.webp':'.png','.gif':'.mp4'}.get(suffix,suffix))
    if suffix not in {'.webp','.svg','.gif'}:
        return install_asset(source,target)
    target.parent.mkdir(parents=True,exist_ok=True)
    staging = target.with_name(f'{target.stem}.tmp{target.suffix}')
    try:
        if suffix=='.webp':
            with Image.open(source) as image:
                image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(staging)
        elif suffix=='.svg':
            staging.write_bytes(sanitized_svg(source))
        else:
            minimum = (ceil((length+.25)*FPS)+1)/FPS
            padding = max(0.,minimum-probe_video(source))
            filters = f'fps={FPS},pad=ceil(iw/2)*2:ceil(ih/2)*2,tpad=stop_mode=clone:stop_duration={padding:.6f}'
            run(['ffmpeg','-nostdin','-v','error','-y','-ignore_loop','1','-i',str(source),
                 '-vf',filters,'-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p',
                 '-movflags','+faststart',str(staging)],check=True)
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)
    return target


def gsap_runtime(raw, root):
    runtime = resolve_gsap_runtime(raw.get('gsap'),root=root)
    if runtime is None:
        raise ValueError('找不到本地 GSAP 运行时，请运行 install.sh --check')
    return runtime


def install_fonts(folder):
    source = KIT/'template/assets/fonts'
    if not source.is_dir():
        return False
    for name in FONT_FILES:
        install_asset(source/name,folder/'assets/fonts'/name)
    return True


def bright_caption_band(source, second):
    filters = ('scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,'
               'crop=1920:160:0:900,scale=1:1:flags=area,format=gray')
    try:
        result = subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',f'{second:.5f}','-i',str(source),
                                 '-an','-vf',filters,'-frames:v','1','-f','rawvideo','pipe:1'],
                                check=True,capture_output=True,timeout=8)
        return bool(result.stdout and result.stdout[0]>=170)
    except (OSError,subprocess.SubprocessError):
        return False


def restore_file_paths(value):
    """Keep rebased paths local until the explainer opens its own file server."""
    if isinstance(value,dict):
        return {key:restore_file_paths(item) for key,item in value.items()}
    if isinstance(value,list):
        return [restore_file_paths(item) for item in value]
    if isinstance(value,str) and value.startswith('/__file__/'):
        return unquote(value.removeprefix('/__file__/'))
    return value


def file_fingerprint(path):
    with path.open('rb') as source:
        return dict(size=path.stat().st_size,sha256=hashlib.file_digest(source,'sha256').hexdigest())


def matching_render(output, stamp, inputs, duration):
    if not output.is_file() or not stamp.is_file():
        return False
    try:
        return read(stamp)==inputs and abs(probe_video(output)-duration)<=1/FPS+.00001
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError):
        return False


def explainer(shot, root, folder, run, *, force_render=False):
    spec_source = shot['spec']
    if isinstance(spec_source,str):
        spec_file = locate(root,spec_source)
        spec,base = read(spec_file), spec_file.parent
    else:
        spec,base = copy.deepcopy(spec_source),root
    # Resolve sources before moving the adjusted spec to the act directory.
    from importlib.util import spec_from_file_location,module_from_spec
    loader = spec_from_file_location('explainer_spec_assets',KIT/'explainer/spec_assets.py')
    assets = module_from_spec(loader)
    loader.loader.exec_module(assets)
    local_files = set()
    spec = restore_file_paths(assets.localize(spec,base,allowed=local_files))
    spec.setdefault('safe',{'top':56,'bottom':172})
    if shot.get('theme') in EXPLAINER_THEMES:
        spec.setdefault('theme',EXPLAINER_THEMES[shot['theme']])
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
    stamp = target.with_suffix('.render-stamp.json')
    renderer = KIT/'scripts/render-explainer-clip.sh'
    engine_files = [renderer,*(path for path in (KIT/'explainer').rglob('*')
                               if path.is_file() and path.suffix in {'.py','.js','.mjs','.css','.html'})]
    inputs = dict(spec=spec,media={name:file_fingerprint(Path(name)) for name in sorted(local_files)},
                  engine={path.relative_to(KIT).as_posix():file_fingerprint(path) for path in sorted(engine_files)})
    if spec.get('grammar')=='t7_editorial_board':
        directory = KIT/'template/assets/fonts'
        inputs['fonts'] = {name:file_fingerprint(directory/name) for name in FONT_FILES[:3] if (directory/name).is_file()}
    write(config,spec)
    if force_render or not matching_render(target,stamp,inputs,span+.35):
        pending = target.with_suffix('.pending.mp4')
        try:
            run(['bash',str(renderer),'--spec',str(config),'--out',str(pending)],check=True)
            if probe_video(pending)+1/FPS < span+.35:
                raise ValueError(f"解说动效未覆盖镜头时长：{shot['id']}")
            pending.replace(target)
            write(stamp,inputs)
        finally:
            pending.unlink(missing_ok=True)
    return target.relative_to(folder).as_posix(),spec


def build_act(shots, root, folder, title, run, *, force_render=False):
    first,last = shots[0]['start'],shots[-1]['end']
    stage = EditorialStage(title,duration=last-first,fps=FPS)
    for shot in shots:
        mode,key = shot['stage_mode'],shot['id']
        a,b = shot['start']-first,shot['end']-first
        text = shot['spoken_topic']
        start = shot['media_start']
        span = b-a
        theme = shot.get('theme','pine')
        palette_start = (len(stage.bg_layers),len(stage.plates))
        assets, auxiliary, gif_hashes = [],[],{}
        for i,path in enumerate(shot['media']):
            length = start+span
            if mode=='triptych_cards':
                card = shot['cards'][i]
                length = card['media_start']+span-card['reveal_at']
            asset = install_visual(path,folder/'assets'/f'{key}-{i}',length=length,run=run).relative_to(folder).as_posix()
            assets.append(asset)
            if path.suffix.lower()=='.gif':
                gif_hashes[asset] = file_fingerprint(path)['sha256']

        def attach(value, slot, extensions):
            if not isinstance(value,str) or not value:
                raise ValueError(f'镜头 {key} 的 {slot} 需要素材路径')
            source = locate(root,value)
            if source.suffix.lower() not in extensions:
                raise ValueError(f'镜头 {key} 的 {slot} 素材格式不支持：{source.name}')
            saved = install_visual(source,folder/'assets'/f'{key}-{slot}',run=run).relative_to(folder).as_posix()
            auxiliary.append(saved)
            return saved

        def with_logo(row, slot):
            return dict(row,logo=attach(row['logo'],slot,LOGO_EXTENSIONS)) if 'logo' in row else row

        overlays = []
        for i,original in enumerate(shot.get('overlays',[])):
            overlay = original
            if overlay['kind']=='corner_tag':
                overlay = with_logo(overlay,f'overlay-{i}-logo')
            if overlay['kind'] in {'prop_badge','reaction_cutout'}:
                overlay = dict(overlay,source=attach(overlay.get('source'),f'overlay-{i}-cutout',LOGO_EXTENSIONS))
            overlays.append(overlay)
        if mode == 'cold_open_ab':
            hook = shot.get('hook',text)
            stage.add_cold_open_ab(a,b,*assets,hook=hook,labels=shot.get('labels',('A','B')),
                                   countdown=shot.get('countdown',3),media_start=start)
        elif mode == 'title_sequence':
            logo = with_logo(shot,'logo').get('logo')
            stage.add_title_sequence(a,b,shot.get('title',text),subtitle=shot.get('subtitle',''),
                                     highlight=shot.get('highlight',''),brand=shot.get('brand','一策'),
                                     paper=theme=='pine' and shot.get('paper',False),logo=logo)
        elif mode == 'callout_rig':
            stage.add_callout_rig(a,b,assets[0],overlays=overlays,media_start=start,motion=shot.get('motion','glide'),
                                  framing=shot.get('framing','fullbleed'),window_title=shot.get('window_title',''))
        elif mode == 'fullbleed_rig':
            stage.add_fullbleed_rig(a,b,assets[0],media_start=start,motion=shot.get('motion','glide'),
                                    framing=shot.get('framing','fullbleed'),window_title=shot.get('window_title',''))
        elif mode == 'studio_ui':
            data = dict(shot['data'])
            data['evidence'] = assets
            if 'monitor' in data:
                monitor = locate(root,data['monitor'])
                validate_media(monitor,span,{})
                data['monitor'] = install_visual(monitor,folder/'assets'/f'{key}-monitor',length=span,run=run).relative_to(folder).as_posix()
            base_plate = add_workbench(stage,a,b,shot['studio_style'],shot.get('title',text),data)
            if overlays:
                stage.add_overlays(a,b,overlays,nle_plate=base_plate if shot['studio_style']=='nle_timeline' else None)
        elif mode == 'triptych_cards':
            cards = [dict(with_logo(card,f'card-{i}-logo'),source=asset)
                     for i,(card,asset) in enumerate(zip(shot['cards'],assets))]
            stage.add_triptych_cards(a,b,heading=shot['heading'],cards=cards)
        elif mode == 'evidence_spotlight':
            logo = with_logo(shot,'logo').get('logo')
            stage.add_evidence_spotlight(a,b,assets[0],heading=shot.get('heading') or text,
                                         source_credit=shot['source_credit'],logo=logo,media_start=start,
                                         highlight_box=shot['highlight_box'],highlight_at=shot.get('highlight_at',.45))
            if overlays:
                stage.add_overlays(a,b,overlays)
        elif mode == 'reference_breakdown':
            stage.add_reference_breakdown(a,b,assets[0],channel=shot.get('channel'),claim=shot.get('claim'),
                                          cut_points=shot.get('cut_points',()),metrics=shot.get('metrics',()),media_start=start)
        else:
            clip,spec = explainer(shot,root,folder,run,force_render=force_render)
            stage.add_video(a,b,clip,0,0,1920,1080,fit='cover')
            stage._shot(text,'explainer_graphic',a,b,[clip],beats=[r['at'] for r in spec['cues']])
            stage.shots[-1]['grammar'] = spec['grammar']
            stage.shots[-1]['explainer_spec'] = str(Path(clip).with_suffix('.json'))
            clip_theme = spec.get('theme')
            theme_name = clip_theme.get('name') if isinstance(clip_theme,dict) else clip_theme
            if theme_name in {'snow','paper','bauhaus'} or (not clip_theme and spec['grammar']=='t6_swiss_card'):
                stage.light_zones.append((a,b))
        stage.apply_palette(theme,a,b,palette_start,keep_studio_panels=mode=='studio_ui')
        if mode in {'fullbleed_rig','callout_rig'} and bright_caption_band(folder/assets[0],start+span/2):
            stage.light_zones.append((a,b))
        fields = ('anchor_cue_id','anchor_cue_start','anchor_text','spoken_topic','visual_subject',
                  'semantic_binding','binding','semantic_tags','spoken_entity','topic_kind','media_start','callback_of','theme')
        row = stage.shots[-1]
        row.update({field:shot[field] for field in fields if field in shot},id=key,stage_mode=mode)
        if 'overlays' in shot:
            row['overlays'] = overlays
        if auxiliary:
            row['aux_files'] = auxiliary
            row['files'] = list(dict.fromkeys([*row['files'],*auxiliary]))
        if gif_hashes:
            row['gif_source_hashes'] = gif_hashes
    return stage


def clock(seconds):
    h, rest = divmod(round(seconds*1000),3600000)
    m, rest = divmod(rest,60000)
    s, ms = divmod(rest,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def cleanup_failure(error, *, checked):
    output = '\n'.join(part or '' for part in (error.stdout,error.stderr))
    if not any(message in output for message in ('Browser process did not exit after forced shutdown','check_cleanup_failure')):
        return False
    for name, following in (('Layout','Motion'),('Motion','Contrast'),('Audio','Snapshots')):
        section = re.search(rf'(?ms)^{name}\b(.*?)(?=^{following}\b|\Z)',output)
        if section and re.search(r'(?<!\d)[1-9]\d*\s+errors?(?:\(s\))?',section[1]):
            return False
        if not checked and (not section or not re.search(r'\b0 (?:issues|errors?)\b',section[1])):
            return False
    return True


def hyperframes_step(command, operation, args, folder, env, run):
    for attempt in range(3):
        try:
            result = run(command+[operation,*args],cwd=folder,env=env,check=True,capture_output=True,text=True)
        except subprocess.CalledProcessError as error:
            if attempt==2 or not cleanup_failure(error,checked=operation=='render'):
                if error.stdout:
                    print(error.stdout,end='',file=sys.stderr)
                if error.stderr:
                    print(error.stderr,end='',file=sys.stderr)
                raise
            time.sleep(2.)
        else:
            if result is not None:
                if result.stdout:
                    print(result.stdout,end='',file=sys.stderr)
                if result.stderr:
                    print(result.stderr,end='',file=sys.stderr)
            return


def render_act(folder, stage, command, env, run, *, force_render=False):
    arguments = ['.','--fps',str(FPS),'--quality','looks']
    media = {'vendor/gsap.min.js','assets/mix.wav',*(path for row in stage.shots for path in row['files'])}
    inputs = dict(duration=round(stage.duration,6),command=command,arguments=arguments,
                  html=file_fingerprint(folder/'index.html'),
                  media={name:file_fingerprint(folder/name) for name in sorted(media)})
    if getattr(stage,'font_assets',False):
        inputs['fonts'] = {name:file_fingerprint(folder/'assets/fonts'/name) for name in FONT_FILES}
    output,stamp = folder/'render.mp4',folder/'.render-stamp.json'
    if not force_render and matching_render(output,stamp,inputs,stage.duration):
        return 'reused'
    pending = folder/'render.pending.mp4'
    try:
        hyperframes_step(command,'check',['.'],folder,env,run)
        hyperframes_step(command,'render',[*arguments,'--output',pending.name],folder,env,run)
        if abs(probe_video(pending)-stage.duration)>1/FPS+.00001:
            raise ValueError(f'分幕渲染时长不符：{folder.name}')
        pending.replace(output)
        write(stamp,inputs)
    finally:
        pending.unlink(missing_ok=True)
    return 'rendered'


def assemble(manifest, output, *, build_only=False, force_render=False, run=subprocess.run):
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
        stage = build_act(items,root,folder,raw.get('title',name),run,force_render=force_render)
        stages.append((folder,stage,offset))
        marks.extend(stage.sound_events(offset))
        for row in stage.shots:
            prefix = folder.relative_to(output)
            files = [(prefix/p).as_posix() for p in row['files']]
            global_row = dict(row,start=round(offset+row['start'],5),end=round(offset+row['end'],5),files=files)
            if 'aux_files' in row:
                global_row['aux_files'] = [(prefix/p).as_posix() for p in row['aux_files']]
            if 'gif_source_hashes' in row:
                global_row['gif_source_hashes'] = {(prefix/p).as_posix():digest for p,digest in row['gif_source_hashes'].items()}
            if row.get('logo'):
                global_row['logo'] = (prefix/row['logo']).as_posix()
            if 'overlays' in row:
                global_row['overlays'] = [dict(overlay,**{key:(prefix/overlay[key]).as_posix()
                                                         for key in ('source','logo') if overlay.get(key)})
                                          for overlay in row['overlays']]
            if row['stage_mode']=='triptych_cards':
                global_row['cards'] = [dict(card,**{key:(prefix/card[key]).as_posix()
                                                   for key in ('source','logo') if card.get(key)})
                                       for card in row['cards']]
            if 'explainer_spec' in row:
                global_row['explainer_spec'] = (folder/row['explainer_spec']).relative_to(output).as_posix()
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
    if 'custom_entities' in raw:
        timeline['custom_entities'] = raw['custom_entities']
    timeline['music_drops'] = [[row['start'],row['end']] if isinstance(row,dict) else row for row in timeline['music_drops']]
    write(output/'shot-timeline.json',timeline)
    (output/f'{name}.srt').write_text('\n'.join(f"{i}\n{clock(c['start'])} --> {clock(c['end'])}\n{c['text']}\n"
                                                  for i,c in enumerate(captions,1)))
    wave,rate = sf.read(output/'mix.wav',dtype='float32')
    command = resolve_hyperframes_command()
    env = {**os.environ,'HYPERFRAMES_TELEMETRY_DISABLED':'1','DO_NOT_TRACK':'1'}
    render_status = {}
    for folder,stage,offset in stages:
        stop = offset+stage.duration
        local = [dict(text=row['text'],start=max(offset,row['start'])-offset,end=min(stop,row['end'])-offset)
                 for row in captions if max(offset,row['start'])<min(stop,row['end'])]
        stage.add_captions(local)
        install_asset(gsap,folder/'vendor/gsap.min.js')
        stage.font_assets = install_fonts(folder)
        stage.write_project(folder,timeline_out=folder/'shot-timeline.json')
        (folder/'assets').mkdir(exist_ok=True)
        sf.write(folder/'assets/mix.wav',wave[round(offset*rate):round(stop*rate)],rate,subtype='PCM_24')
        if not build_only:
            render_status[folder.name] = render_act(folder,stage,command,env,run,force_render=force_render)
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
        result['act_render_status'] = render_status
    write(output/'assembly-report.json',result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--build-only',action='store_true',help='生成分幕工程和母带，跳过浏览器渲染')
    parser.add_argument('--force-render',action='store_true',help='忽略已有分幕渲染缓存')
    args = parser.parse_args(argv)
    try:
        result = assemble(args.manifest,args.output,build_only=args.build_only,force_render=args.force_render)
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
