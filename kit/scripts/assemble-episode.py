#!/usr/bin/env python3
"""从声明式清单导出标准 HyperFrames 分幕工程、母带、成片与字幕。"""
import argparse
import copy
import hashlib
import json
from html.parser import HTMLParser
from math import ceil, isfinite
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import sys
import time
from urllib.parse import unquote
from xml.etree import ElementTree

from PIL import Image

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(KIT.parent))
from audit_v7 import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, probe_video, semantic_binding_gate
from workspace import ONETAKE_FILES, ONETAKE_FONTS, composition_files, resolve_gsap_runtime, resolve_hyperframes_command, resolve_onetake, render_workers, render_priority
from kit.editorial.audio_mix import INTERACTION_SOUNDS, mix_episode_audio
from kit.editorial.editorial import EditorialStage, EXPLAINER_THEMES, FONT_FILES, PALETTES, evidence_box
from kit.onetake.scene import build as build_onetake_scene
from kit.spatial.block import build as build_spatial_scene
from kit.studio_ui import add_workbench

FPS = 30
MODES = {'cold_open_ab','title_sequence','callout_rig','fullbleed_rig','studio_ui','explainer_clip','triptych_cards','reference_breakdown','evidence_spotlight','onetake_clip','hyperframes_block'}
TRANSITIONS = {'whip_push','zoom_through','iris_reveal','blur_crossfade'}
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
        if mode in {'fullbleed_rig','callout_rig'} and media and 'interactions' not in src:
            track = locate(root,src['cursor_track']) if src.get('cursor_track') else (
                media[0].with_name('cursor-track.json') if media[0].name=='video.mp4' else None)
            if track and track.is_file():
                action_map={'click':'click','type':'type','delete':'delete','confirm':'confirm','page_turn':'page_turn','drag':'soft_click','highlight':'line_draw'}
                events = []
                for event in read(track)['events']:
                    action=action_map.get(event['kind'])
                    t=round(float(event['t'])-media_start,5)
                    if action and 0<=t<end-start:
                        events.append(dict(action=action,at=t,gain=.60 if action=='line_draw' else .34))
                src=dict(src,interactions=events)
        if mode=='evidence_spotlight':
            src = evidence_metadata(src,root)
        if 'transition_in' in src:
            transition = src['transition_in']
            if (not result or result[-1]['act'] != act or not isinstance(transition,dict)
                    or not isinstance(transition.get('kind'),str) or transition['kind'] not in TRANSITIONS
                    or type(transition.get('duration')) not in (int,float)
                    or not 0 < transition['duration'] < end-start):
                raise ValueError(f'镜头 {key} 的转场须位于同幕第二镜起，时长须短于入镜')
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


def caption_light_zones(source, media_start, start, end):
    span = end - start
    inset = min(.6, span * .2)
    samples = [inset, span / 2, span - inset] if span >= 4 else [span / 2]
    previous = samples[0]
    light = bright_caption_band(source, media_start + previous)
    boundary = start
    for sample in samples[1:]:
        current = bright_caption_band(source, media_start + sample)
        if current != light:
            lo, hi = round(previous * FPS), round(sample * FPS)
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if bright_caption_band(source, media_start + mid / FPS) == light:
                    lo = mid
                else:
                    hi = mid
            cut = start + hi / FPS
            if light:
                yield boundary, cut
            boundary = cut
        light, previous = current, sample
    if light:
        yield boundary, end


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


def composition_entry(root, value, default):
    if not isinstance(value,str) or not value or not Path(value).parts:
        raise ValueError('合成需要目录或 HTML 入口')
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('合成入口须位于清单下的本地目录')
    entry = root / path
    if entry.is_dir():
        entry /= default
    if entry.parent == root or any(part.is_symlink() for part in (entry,*entry.parents) if part != root and root in part.parents):
        raise ValueError('合成须位于专用目录，路径不可含软链接')
    return entry


def compile_inline_scene(shot, root, folder, gsap):
    """Publish a complete compiled scene only after all its inputs have been resolved."""
    spatial = shot['stage_mode'] == 'hyperframes_block'
    field = 'spatial_spec' if spatial else 'onetake_spec'
    if field not in shot:
        return shot
    span = round(shot['end']-shot['start'], 6)
    spec = dict(shot[field], duration=span if spatial else round(span+.36, 6))
    spec.setdefault('id', 'scene-'+shot['id'])
    cache = folder/'scene-cache'/shot['id']
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as temporary:
        staging = Path(temporary)
        entry = (build_spatial_scene(spec, root, staging, gsap) if spatial
                 else build_onetake_scene(spec, root, staging))
        # Include compiled media, CSS and motion code, even when only a screenshot changed.
        inputs = [(p.relative_to(staging).as_posix(),file_fingerprint(p)) for p in composition_files(entry)]
        version = hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
        target = cache/version
        if not target.is_dir():
            try:
                staging.rename(target)
            except OSError:
                if not target.is_dir():
                    raise
        return dict(shot, compiled_entry=target/entry.name)


def onetake(shot, root, folder, run, *, force_render=False, workers=None):
    entry = shot.get('compiled_entry') or composition_entry(root,shot.get('comp'),'comp.html')
    runtime = resolve_onetake()
    if runtime is None:
        raise ValueError('找不到本机 Onetake')
    shutter = shot.get('shutter',180)
    allow_staccato = shot.get('allow_staccato',False)
    look = shot.get('look')
    screenshots = shot.get('look_from_shots',[])
    if ((look is not None and not isinstance(look,str)) or not isinstance(screenshots,list)
            or len(screenshots)>3 or any(not isinstance(item,str) or not item for item in screenshots)
            or ('look_from_shots' in shot and not screenshots)):
        raise ValueError('Onetake 色板或截图参数无效')
    shots = [locate(root,item) for item in screenshots]
    if type(shutter) not in (int,float) or not 0 < shutter <= 360 or not isinstance(allow_staccato,bool):
        raise ValueError('Onetake 快门或 allow_staccato 参数无效')
    output = folder/'assets'/f"otk-{shot['id']}.mp4"
    stamp = output.with_suffix('.render-stamp.json')
    probe = output.with_suffix('.onetake-probe.json')
    render = output.with_suffix('.render.json')
    span = round(shot['end']-shot['start'],6)
    runtime_files = [*ONETAKE_FILES, 'lib/ui_kit.js']
    if look is not None or shots:
        runtime_files.append('looks/looks.json')
    if shots:
        runtime_files.append('scripts/look.py')
    inputs = dict(entry=entry.name,span=span,shutter=shutter,allow_staccato=allow_staccato,
                  composition={p.relative_to(entry.parent).as_posix():file_fingerprint(p) for p in composition_files(entry)},
                  runtime={name:file_fingerprint(runtime/name) for name in runtime_files if (runtime/name).is_file()},
                  fonts={name:file_fingerprint(KIT/'template/assets/fonts'/name) for name in ONETAKE_FONTS},
                  bridge=file_fingerprint(Path(__file__).with_name('render-onetake-clip.py')))
    if look is not None or shots:
        inputs['look'] = dict(preset=look,screenshots=[file_fingerprint(path) for path in shots])
    minimum_frames = ceil((span + .35)*FPS - 1e-6)
    if not force_render and all(path.is_file() for path in (output,stamp,probe,render)):
        try:
            report = read(probe)
            if (read(stamp)==inputs and not report['seek_errors'] and not report['page_errors']
                    and read(render)['shutter']==shutter and round(probe_video(output)*FPS)>=minimum_frames):
                return output.relative_to(folder).as_posix(), report
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            pass
    cmd = [sys.executable,str(Path(__file__).with_name('render-onetake-clip.py')),str(entry),
           '--out',str(output),'--span',str(span),'--shutter',str(shutter),'--workers',str(render_workers(workers))]
    if allow_staccato:
        cmd.append('--allow-staccato')
    if look is not None:
        cmd.extend(('--look',look))
    if shots:
        cmd.extend(('--look-from-shots',*map(str,shots)))
    run(cmd,check=True,**render_priority())
    write(stamp,inputs)
    return output.relative_to(folder).as_posix(), read(probe)


class CompositionRoot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.composition_id = None
        self.templated = False

    def handle_starttag(self, tag, attrs):
        if tag == 'template' and self.composition_id is None:
            self.templated = True
        attributes = dict(attrs)
        if self.composition_id is None and 'data-composition-src' not in attributes:
            self.composition_id = attributes.get('data-composition-id')


def install_subcomposition(shot, root, folder, gsap):
    entry = shot.get('compiled_entry') or composition_entry(root,shot.get('composition'),'index.html')
    files = composition_files(entry)
    parser = CompositionRoot()
    markup = entry.read_text()
    parser.feed(markup)
    if parser.composition_id is None:
        raise ValueError(f"子合成 {shot['id']} 缺少 data-composition-id")
    composition_id = identifier(parser.composition_id)
    dest = folder/'compositions'/shot['id']
    if dest.is_symlink() or dest.parent.is_symlink():
        raise ValueError('子合成输出目录不可为软链接')
    if dest.exists():
        shutil.rmtree(dest)
    for source in files:
        target = dest / source.relative_to(entry.parent)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    if not parser.templated:
        head = re.search(r'<head\b[^>]*>(.*?)</head\s*>',markup,re.I|re.S)
        body = re.search(r'<body\b[^>]*>(.*?)</body\s*>',markup,re.I|re.S)
        assets = re.findall(r'<(?:style|script)\b[^>]*>.*?</(?:style|script)\s*>|<link\b[^>]*>',
                            head[1],re.I|re.S) if head else []
        fragment = body[1] if body else markup
        (dest/entry.name).write_text('<!doctype html><meta charset="utf-8"><template>\n'
                                    +'\n'.join(assets+[fragment])+'\n</template>\n')
    install_asset(gsap,dest/'vendor/gsap.min.js')
    install_fonts(dest)
    return (dest/entry.name).relative_to(folder).as_posix(),composition_id


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
            run(['bash',str(renderer),'--spec',str(config),'--out',str(pending)],check=True,**render_priority())
            if probe_video(pending)+1/FPS < span+.35:
                raise ValueError(f"解说动效未覆盖镜头时长：{shot['id']}")
            pending.replace(target)
            write(stamp,inputs)
        finally:
            pending.unlink(missing_ok=True)
    return target.relative_to(folder).as_posix(),spec


def _spatial_sound_marks(sp_spec, span):
    recipe = sp_spec.get('recipe', '')
    data = sp_spec.get('data') or {}
    cues = []
    def add(kind, rel_t, gain=0.32):
        t = float(rel_t)
        if 0.0 <= t < span - 0.04:
            key_gains = {'marker_stroke': .74, 'card_thock': .40 if recipe in {'logo_bento_stage','step_tree_focus'} else .70, 'shutter_whip': .68, 'counter_roll': .38, 'whoosh': .60}
            cues.append((round(t, 4), kind, key_gains.get(kind, gain)))

    swiss = (sp_spec.get('stage_look') or data.get('stage_look')) == 'swiss_paper'
    land = 'card_thock' if swiss else 'pop'
    if recipe == 'kinetic_title_bridge':
        for word in data.get('words', []):
            add('pop',word['at']+.12,.30)
        add('marker_stroke', data['underline_at'])
    elif recipe == 'triptych_curtain':
        add('shutter_whip', 0.02)
        for i,word in enumerate(data.get('words',[])):
            if word.get('sound',True) and (i==0 or word.get('line')!=data['words'][i-1].get('line')):
                cues.append((round(word['at']+.12,4), 'impact_bass_2' if i==0 else 'card_thock', .38))
        if 'underline_at' in data:
            add('marker_stroke',data['underline_at'])
    elif recipe == 'perspective_video_fan':
        add('whoosh', 0.04, 0.30)
        focus_at = float(data.get('focus_at', span * 0.42))
        add('click', focus_at, 0.34)
        add('chime', focus_at + 0.08, 0.24)
        if isinstance(data.get('punch_at'), (int, float)):
            add('impact', data['punch_at'], 0.40)
    elif recipe == 'logo_bento_stage':
        for idx, mod in enumerate(data.get('modules') or []):
            mat = float(mod.get('at', 0.12 + idx * 0.28))
            add(land, mat, 0.32)
            for j, it in enumerate(mod.get('items') or []):
                if isinstance(it, dict) and isinstance(it.get('at'), (int, float)):
                    add('click_soft' if swiss else 'click', it['at'], 0.34)
        for focus in data.get('focus_sequence',[]):
            add('click_soft',focus['at'],.32)
    elif recipe == 'progressive_sim_cards':
        for idx, card in enumerate(data.get('cards') or []):
            cat = float(card.get('at', 0.12 + idx * 0.65))
            if card.get('reveal', True):
                add(land, cat, 0.34)
            for page in card.get('pages',[]):
                add('page_flip',page['at'],.34)
            for at in card.get('panel_accents',[]):
                add('click_soft',at,.31)
            if card.get('kind') == 'race_bars':
                add('counter_roll' if swiss else 'chime', cat + 0.36, 0.26)
    elif recipe == 'prompt_iter_workbench':
        for chip in data['prompt_chips']:
            add('click_soft', chip['at'])
        add('page_flip', data.get('iter_at', round(span*.46, 3)))
    elif recipe == 'step_tree_focus':
        for idx, br in enumerate(data.get('branches') or []):
            bat = float(br.get('at', 0.12 + idx * 1.1))
            linked = swiss and idx and data.get('relationship') != 'parallel'
            add('marker_stroke' if linked else land,
                max(.03,bat-.16) if linked else bat, .36)
            for ch in (br.get('children') or []):
                if isinstance(ch.get('at'), (int, float)):
                    add('click_soft' if swiss else 'click', ch['at'], 0.28)
        focus_steps = data.get('focus_sequence') or []
        for prev,step in zip(focus_steps,focus_steps[1:]):
            if isinstance(step.get('at'), (int, float)):
                add(('click_soft' if prev['index']==step['index'] else 'focus_reveal') if swiss else 'whoosh', step['at'], .38)
    elif recipe == 'formula_pill_chain':
        add('pop', 0.04, 0.30)
        rev = float(data.get('reveal_at', span * 0.32))
        add('whoosh', rev, 0.30)
        add('click', rev + 0.10, 0.34)
    elif recipe == 'carousel_3d_select':
        add('whoosh', 0.05, 0.28)
        sel = float(data.get('select_at', span * 0.5))
        add('impact', sel, 0.34)
    elif recipe == 'layer_explode_3d':
        add('zoom_swoosh', span*.04, .62)
        add('counter_roll', data.get('count_at',span*.07), .34)
        add('ping',span*.84,.36)
    elif recipe == 'roadmap_thread_camera':
        for idx, st in enumerate(data.get('steps') or []):
            add('pop', float(st.get('at', 0.15 + idx * 0.8)), 0.30)
    elif recipe == 'cutout_parallax_stage':
        add('whoosh', 0.05, 0.28)
        add('pop', 0.28, 0.28)
    elif recipe == 'documentary_ken_burns':
        add('whoosh', 0.05, 0.24)
        if isinstance(data.get('split_at'), (int, float)):
            add('click', data['split_at'], 0.30)
    else:
        add('pop', 0.08, 0.30)
        add('click', span * 0.42, 0.28)

    if 'exit_zoom_index' in data or data.get('exit_zoom') or data.get('exit_zoom_after'):
        exit_at = data.get('exit_zoom_at', round(span - (.46 if data.get('exit_zoom_after') else .48), 3))
        cues = [cue for cue in cues if cue[1] not in ('click', 'zoom_swoosh') or abs(cue[0]-exit_at) >= .14]
        add('click', exit_at, .42)
        add('zoom_swoosh', exit_at, .60)
    deduped, last_by_kind = [], {}
    for t, kind, gain in sorted(cues):
        if t - last_by_kind.get(kind, -9.0) >= (.035 if recipe=='logo_bento_stage' else .14):
            deduped.append((kind, t, gain))
            last_by_kind[kind] = t
    return deduped


def build_act(shots, root, folder, title, run, *, force_render=False, gsap=None, workers=None):
    first,last = shots[0]['start'],shots[-1]['end']
    stage = EditorialStage(title,duration=last-first,fps=FPS)
    for shot in shots:
        mode,key = shot['stage_mode'],shot['id']
        if mode in ('hyperframes_block', 'onetake_clip'):
            shot = compile_inline_scene(shot,root,folder,gsap or gsap_runtime({},root))
        a,b = shot['start']-first,shot['end']-first
        text = shot['spoken_topic']
        start = shot['media_start']
        span = b-a
        theme = shot.get('theme','pine')
        cinema = theme in {'obsidian','aurora_indigo'} or shot.get('atmosphere')=='cinema_glow'
        before = tuple(len(group) for group in stage.visual_layers())
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
                if shot.get('framing','fullbleed')=='fullbleed' and overlay.get('position','auto')=='auto':
                    overlay = dict(overlay,position='top_right')
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
                                  camera_moves=shot.get('camera_moves'),framing=shot.get('framing','fullbleed'),window_title=shot.get('window_title',''),refractive=cinema)
        elif mode == 'fullbleed_rig':
            stage.add_fullbleed_rig(a,b,assets[0],media_start=start,motion=shot.get('motion','glide'),
                                    camera_moves=shot.get('camera_moves'),chapter_pill=shot.get('chapter_pill'),framing=shot.get('framing','fullbleed'),window_title=shot.get('window_title',''),refractive=cinema)
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
            stage.add_triptych_cards(a,b,heading=shot['heading'],cards=cards,theme=theme)
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
        elif mode == 'onetake_clip':
            clip,probe = onetake(shot,root,folder,run,force_render=force_render,workers=workers)
            stage.add_video(a,b,clip,0,0,1920,1080,fit='cover')
            stage._shot(text,'onetake_motion',a,b,[clip],beats=probe['beats'])
            entry = shot.get('compiled_entry') or composition_entry(root,shot['comp'],'comp.html')
            source_folder = folder/'onetake-sources'/key
            for source in composition_files(entry):
                install_asset(source,source_folder/source.relative_to(entry.parent))
            row_entry = source_folder/entry.name
            stage.shots[-1]['comp'] = row_entry.relative_to(folder).as_posix()
            for event in probe['events']:
                if event['t'] < span:
                    stage.add_sound_mark(event['kind'],a+event['t'],gain=event.get('gain'))
            ot_data = (shot.get('onetake_spec') or {}).get('data') or {}
            if shot.get('look') in {'paper', 'tabletop', 'riso', 'ember'} or ot_data.get('style') == 'pencil_watercolor':
                stage.light_zones.append((a, b))
        elif mode == 'hyperframes_block':
            entry,composition_id = install_subcomposition(shot,root,folder,gsap or gsap_runtime({},root))
            stage.add_subcomposition(key,composition_id,entry,a,b)
            sp_spec = shot.get('spatial_spec') or {}
            auto_marks = _spatial_sound_marks(sp_spec, span)
            stage._shot(text,'hyperframes_motion',a,b,[],beats=[round(t,4) for _,t,_ in auto_marks])
            stage.shots[-1]['composition'] = entry
            for sfx_kind, rel_t, sfx_gain in auto_marks:
                stage.add_sound_mark(sfx_kind, a + rel_t, gain=sfx_gain)
            sp_look = sp_spec.get('stage_look') or (sp_spec.get('data') or {}).get('stage_look')
            sp_recipe = sp_spec.get('recipe')
            if sp_look in {'swiss_paper', 'editorial_paper', 'scroll_paper', 'paper'} or (
                sp_look is None and sp_recipe in {'cutout_parallax_stage', 'documentary_ken_burns', 'step_tree_focus', 'progressive_sim_cards', 'logo_bento_stage'}
            ):
                stage.light_zones.append((a, b))
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
        zone_count = len(stage.light_zones)
        stage.apply_palette(theme,a,b,palette_start,keep_studio_panels=mode=='studio_ui')
        if cinema:
            stage.add_cinema_material(a,b,theme)
        if mode in {'fullbleed_rig','callout_rig'} and shot.get('framing','fullbleed') == 'fullbleed':
            del stage.light_zones[zone_count:]
            stage.light_zones.extend(caption_light_zones(folder/assets[0],start,a,b))
        fields = ('chapter','anchor_cue_id','anchor_cue_start','anchor_text','spoken_topic','visual_subject',
                  'camera_moves','visual_mode','look','shutter','page_region','case_tag','case_windows','stage_look','semantic_binding','binding','semantic_tags','spoken_entity','topic_kind','media_start','callback_of','theme','transition_in')
        row = stage.shots[-1]
        row.update({field:shot[field] for field in fields if field in shot},id=key,stage_mode=mode)
        row['source_names'] = [Path(str(src)).name for src in shot.get('media', [])]
        recipe_spec = shot.get('spatial_spec') or shot.get('onetake_spec') or {}
        if recipe_spec:
            row['recipe'] = recipe_spec.get('recipe')
            data = recipe_spec.get('data') or {}
            if row['recipe'] in {'triptych_curtain','kinetic_title_bridge','progressive_sim_cards','prompt_iter_workbench','logo_bento_stage','step_tree_focus'}:
                action_times = [0.]
                for group in ('words','cards','modules','branches','focus_sequence','prompt_chips'):
                    for item in data.get(group,[]):
                        if not isinstance(item,dict):
                            continue
                        if 'at' in item:
                            action_times.append(item['at'])
                        action_times.extend(item.get('panel_accents',[]))
                        action_times.extend(page['at'] for page in item.get('pages',[]))
                        if group=='words': action_times.append(item.get('at',0)+.12)
                        for child in item.get('children',[]) + item.get('items',[]):
                            if isinstance(child,dict) and 'at' in child:
                                action_times.append(child['at'])
                if row['recipe'] == 'prompt_iter_workbench':
                    action_times.append(data.get('iter_at', round(span*.46, 3)))
                if 'underline_at' in data:
                    action_times.append(data['underline_at'])
                if row['recipe']=='step_tree_focus':
                    action_times.extend(max(.03,b['at']-.16) for b in data['branches'][1:] if 'at' in b)
                row['visual_action_times'] = sorted(set(action_times))
            if 'exit_zoom_index' in data or data.get('exit_zoom') or data.get('exit_zoom_after'):
                at = data.get('exit_zoom_at', round(span - (.46 if data.get('exit_zoom_after') else .48), 3))
                row['camera_action_times'] = [at]
                row['visual_action_times'] = sorted(set([*row.get('visual_action_times', row.get('beats', [])), at]))
            if row['recipe']=='layer_explode_3d':
                row['visual_action_times']=[span*.04,data.get('count_at',span*.07),span*.84]
            if 'expected_items' in data:
                row['expected_items'] = data['expected_items']
            row['source_names'] += [Path(v).name for v in (data.get('videos') or [])]
            row['source_names'] += [Path(data[k]).name for k in ('before','after','before_source','after_source') if isinstance(data.get(k),str)]
            row['source_names'] += [Path(card['source']).name for card in data.get('cards',[]) if isinstance(card, dict) and card.get('source')]
        if 'presenter_shortcuts' in shot:
            row['presenter_shortcuts'] = shot['presenter_shortcuts']
        if 'custom_layout' in shot:
            row['custom_layout'] = shot['custom_layout']
        if mode in {'fullbleed_rig','callout_rig'}:
            moves = shot.get('camera_moves')
            camera = ([float(move[0]) for move in moves if (move[4] if len(move)>4 else shot.get('motion'))!='hold']
                      if moves is not None else [0.] if shot.get('motion') in {'push','pull','focus_push','punch'} else [])
            manual = [r['at'] for r in shot.get('interactions',[]) if r['action']=='camera_zoom']
            for at in camera:
                if 0<=at<span and not any(abs(at-t)<=.12 for t in manual):
                    stage.add_sound_mark('camera_sweep',a+at,gain=.59)
            row['camera_action_times']=camera
        if 'interactions' in shot:
            row['interactions'] = shot['interactions']
            for act in row['interactions']:
                rel = float(act['at'])
                if act['action'] not in INTERACTION_SOUNDS or not 0 <= rel < span:
                    raise ValueError('交互动作类型或时刻超出镜头')
                stage.add_sound_mark(INTERACTION_SOUNDS[act['action']], a+rel, gain=act.get('gain',.39))
        if mode == 'hyperframes_block' and sp_recipe == 'triptych_curtain':
            row['curtain_source_hashes'] = [file_fingerprint(root / src)['sha256']
                                            for src in sp_spec['data']['videos']]
        if mode == 'hyperframes_block' and sp_look:
            row['stage_look'] = sp_look
        if mode == 'onetake_clip' and shot.get('onetake_spec', {}).get('stage_look') == 'cinema_black':
            row['stage_look'] = 'cinema_black'
        if 'overlays' in shot:
            row['overlays'] = overlays
        if auxiliary:
            row['aux_files'] = auxiliary
            row['files'] = list(dict.fromkeys([*row['files'],*auxiliary]))
        if gif_hashes:
            row['gif_source_hashes'] = gif_hashes
        for custom_sfx in shot.get('sound_marks', []):
            rel_at = float(custom_sfx['at'])
            if custom_sfx['kind'] == 'shutter_whip' and row.get('recipe') != 'triptych_curtain':
                continue
            if 0.0 <= rel_at < span:
                stage.add_sound_mark(custom_sfx['kind'], a + rel_at, gain=custom_sfx.get('gain', 0.34))
        stage.register_visual_shot(key,a,b,before,shot.get('transition_in'))
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
            result = run(command+[operation,*args],cwd=folder,env=env,check=True,capture_output=True,text=True,**render_priority())
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


def render_act(folder, stage, command, env, run, *, force_render=False, workers=None, draft=False, artifact="render"):
    workers = render_workers(workers)
    arguments = ['.','--fps',str(FPS),'--quality','draft' if draft else 'looks']
    media = {'vendor/gsap.min.js','assets/mix.wav',*(path for row in stage.shots for path in row['files'])}
    inputs = dict(duration=round(stage.duration,6),command=command,arguments=arguments,
                  html=file_fingerprint(folder/'index.html'),
                  media={name:file_fingerprint(folder/name) for name in sorted(media)})
    if getattr(stage,'font_assets',False):
        inputs['fonts'] = {name:file_fingerprint(folder/'assets/fonts'/name) for name in FONT_FILES}
    if getattr(stage,'subcompositions',[]):
        inputs['subcompositions'] = {
            path.relative_to(folder).as_posix():file_fingerprint(path)
            for entry in stage.subcompositions for path in composition_files(folder/entry)
        }
    output,stamp = folder/f'{artifact}.mp4',folder/f'.{artifact}-stamp.json'
    if not force_render and matching_render(output,stamp,inputs,stage.duration):
        return 'reused'
    pending = folder/f'{artifact}.pending.mp4'
    try:
        hyperframes_step(command,'check',['.'],folder,env,run)
        hyperframes_step(command,'render',[*arguments,'--workers',str(workers),'--output',pending.name],folder,env,run)
        if abs(probe_video(pending)-stage.duration)>1/FPS+.00001:
            raise ValueError(f'分幕渲染时长不符：{folder.name}')
        pending.replace(output)
        write(stamp,inputs)
    finally:
        pending.unlink(missing_ok=True)
    return 'rendered'


def assemble(manifest, output, *, build_only=False, force_render=False, run=subprocess.run, workers=None, draft=False):
    workers = render_workers(workers)
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
        stage = build_act(items,root,folder,raw.get('title',name),run,force_render=force_render,gsap=gsap,workers=workers)
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
            for field in ('explainer_spec','composition','comp'):
                if field in row:
                    global_row[field] = (prefix/row[field]).as_posix()
            global_shots.append(global_row)
    cuts = None
    music = audio.get('bgm',[])
    if 1<len(music)<=len(stages):
        cuts = [stages[round(i*len(stages)/len(music))][2] for i in range(1,len(music))]
    # Place a quiet beat under the actual overlay landing when no authored drop covers it.
    drops = list(audio.get('music_drops', []))
    for shot in global_shots:
        for overlay in shot.get('overlays', []):
            if overlay['kind'] != 'editorial_punch':
                continue
            hit = shot['start']+overlay['at']
            windows = [(w['start'], w['end']) if isinstance(w,dict) else w for w in drops]
            if not any(lo <= hit <= hi for lo,hi in windows):
                drops.append([hit, min(duration, hit+.24)])
    audio['music_drops'] = drops
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
    timeline['captions'] = captions
    if 'voice_manifest' in raw:
        manifest_path = locate(root, raw.get('chapter_reference_manifest', raw['voice_manifest']))
        canonical = read(manifest_path)
        selected = {str(row['id']) for row in voice_files}
        if 'chapter_reference_manifest' in raw and selected - {str(chapter['id']) for chapter in canonical['chapters']}:
            raise ValueError('选用的章节未在原声清单中找到')
        timeline['chapter_reference'] = []
        for chapter in canonical['chapters']:
            if str(chapter['id']) in selected:
                sound = manifest_path.parent / (chapter.get('audio') or chapter['path'])
                timeline['chapter_reference'].append(dict(id=chapter['id'],duration=sf.info(sound).duration,
                                                          sha256=file_fingerprint(sound)['sha256']))
    if 'semantic_alignment' in raw:
        ledger = locate(root, raw['semantic_alignment'])
        timeline['semantic_alignment'] = json.loads(ledger.read_text())
        write(output/'semantic-alignment.json', timeline['semantic_alignment'])
    if 'version' in raw:
        timeline['version'] = raw['version']
    if 'episode_kind' in raw:
        timeline['episode_kind'] = raw['episode_kind']
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
    review_pack = bool(raw.get('review_pack'))
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
            render_status[folder.name] = render_act(folder,stage,command,env,run,force_render=force_render,workers=workers,draft=draft)
            if review_pack:
                captions_html=stage.captions
                try:
                    stage.captions=[]
                    stage.write_project(folder,timeline_out=folder/'shot-timeline.json')
                    render_act(folder,stage,command,env,run,workers=workers,force_render=force_render,
                               draft=True,artifact='blind-render')
                finally:
                    stage.captions=captions_html
                    stage.write_project(folder,timeline_out=folder/'shot-timeline.json')
    result = dict(ok=True,duration=duration,acts=len(stages),shots=len(shots),timeline='shot-timeline.json',srt=f'{name}.srt')
    if not build_only:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(dir=output) as scratch:
            scratch=Path(scratch)
            for render in (['render','blind-render'] if review_pack else ['render']):
                concat=scratch/'acts.ffconcat'
                lines=['ffconcat version 1.0']
                for i,(folder,stage,_) in enumerate(stages):
                    frames=round(stage.duration*FPS)
                    pic=scratch/f'picture-{i}.mp4'
                    run(['ffmpeg','-nostdin','-v','error','-y','-i',str(folder/(render+'.mp4')),
                         '-map','0:v:0','-c:v','copy','-frames:v',str(frames),str(pic)],check=True)
                    lines.extend([f"file '{pic.name}'",f'duration {frames/FPS:.9f}'])
                concat.write_text('\n'.join(lines)+'\n')
                staged=scratch/(render+'-mux.mp4')
                run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(concat),
                     '-i',str(output/'mix.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy',
                     '-c:a','aac','-ac','2','-b:a','256k','-movflags','+faststart',str(staged)],check=True)
                if render=='render': staged.replace(output/f'{name}.mp4')
                else:
                    from review import episode_review_pack
                    episode_review_pack(output/f'{name}.mp4',staged,global_shots,output,duration)
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
    parser.add_argument('--workers',type=int,help='渲染并发数，默认取 YICE_RENDER_WORKERS 或 2')
    parser.add_argument('--draft',action='store_true',help='以草稿画质渲染并复用一致的 Onetake 片段')
    args = parser.parse_args(argv)
    try:
        result = assemble(args.manifest,args.output,build_only=args.build_only,force_render=args.force_render,workers=args.workers,draft=args.draft)
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
