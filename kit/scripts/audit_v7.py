"""Audit the relationship between narration, shot subjects and actual masters."""
from collections import defaultdict
import hashlib
import json
from math import ceil, isfinite
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata


sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from kit.editorial.editorial import STAT_BADGE_BOX, STUDIO_VIEW

OCR = Path(__file__).resolve().parents[1] / 'tools/ocr/ocr'


TOOLS = {
    'hyperframes': ('hyperframes', 'hyper frames'),
    'playwright': ('playwright', 'play wright'),
    'codex': ('codex', 'code x'),
    'finder': ('finder', '访达'),
    'ffmpeg': ('ffmpeg', 'ffmpeg cli'),
    'transformers': ('transformers',),
    'claude': ('claude',),
    'github': ('github', 'git hub'),
    'kaggle': ('kaggle',),
    'remotion': ('remotion',),
    'motioncanvas': ('motion canvas',),
    'gsap': ('gsap',),
    'whisper': ('whisper',),
    'cursor': ('cursor',),
    'huggingface': ('hugging face', 'huggingface'),
    'qwen3tts': ('qwen3-tts', 'qwen3 tts'),
    'johnnyharris': ('johnny harris', 'johnny'),
    'fireship': ('fireship',),
    'openai': ('openai','chatgpt'),
    'gemini': ('gemini','谷歌双子座'),
    'deepseek': ('deepseek','深度求索'),
    'qwen': ('qwen','通义千问'),
    'ollama': ('ollama',),
    'vllm': ('vllm',),
    'docker': ('docker',),
    'nextjs': ('next.js','nextjs','next js'),
    'supabase': ('supabase',),
    'cloudflare': ('cloudflare',),
    'youtube': ('youtube','油管'),
}
CREATORS = {'johnnyharris','fireship'}
ABSTRACT = ('规则', '清单', '优先级', '总结', '原则', '三句话', '步骤', 'rules', 'checklist', 'summary', 'priority')
BINDINGS = {'exact_tool_capture', 'conceptual_explainer', 'physical_prop', 'callback_cut'}
MOTION = {'explainer_clip', 'title_sequence', 'cold_open_ab', 'triptych_cards', 'reference_breakdown', 'evidence_spotlight',
          'onetake_clip', 'hyperframes_block'}
REAL = {'callout_rig', 'cold_open_ab', 'fullbleed_rig', 'web_cam', 'real_video', 'stock_broll', 'reference_breakdown'}
VERIFIED_OVERLAYS = {'spotlight_box','highlighter_sweep','hand_circle'}
MOTION_OVERLAYS = {'editorial_punch','stat_badge','strikethrough_list','verdict_stamp','corner_tag','prop_badge','reaction_cutout'} | VERIFIED_OVERLAYS
from kit.editorial.audio_mix import SFX_KINDS
SFX = SFX_KINDS | {'slap'}
VIDEO_EXTENSIONS = {'.mp4','.m4v','.mov','.webm'}
IMAGE_EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.svg'}
WHITEBOARD_ICONS = {'person','cat','network','doc','chat','bulb','check','cross','screen','stack','gear','target','clock','chart'}
STRUCTURED_CUES = {'bar','line','candle','image','clip','card','equation'}


def difference_hash(image):
    resized = image.convert('L').resize((9,8))
    pixels = list(resized.get_flattened_data()) if hasattr(resized,'get_flattened_data') else list(resized.getdata())
    bits = 0
    for row in range(8):
        for column in range(8):
            i = row*9+column
            bits = (bits << 1) | int(pixels[i]>pixels[i+1])
    return bits


def frame_scores(frame):
    import numpy as np
    rgb = np.asarray(frame)
    quantized = rgb.astype(np.uint16) >> 4
    bins = (quantized[:,:,0]<<8) | (quantized[:,:,1]<<4) | quantized[:,:,2]
    counts = np.bincount(bins.ravel(),minlength=4096)
    flat = float(np.partition(counts,-2)[-2:].sum()/bins.size)
    grey = np.asarray(frame.convert('L'),dtype=np.float32)
    edge = float((np.abs(np.diff(grey,axis=0)).mean()+np.abs(np.diff(grey,axis=1)).mean())/510)
    is_flat = flat>=.72
    band = grey[-32:-4,40:280]
    # 字幕的浅色笔画旁会紧贴深色描边，并在数个相邻行横向分布。
    bright = band[1:-1,1:-1]
    dark = np.minimum.reduce([band[:-2,1:-1],band[2:,1:-1],band[1:-1,:-2],band[1:-1,2:]])
    outlines = (bright >= 200) & (bright-dark >= 100)
    text_rows = outlines.sum(axis=1) >= 12
    subtitle_edge = bool(np.count_nonzero(text_rows)>=3 and np.count_nonzero(outlines.any(axis=0))>=30)
    return dict(dhash=f'{difference_hash(frame):016x}',flat_bg_ratio=round(flat,4),is_flat_slide=is_flat,
                edge_density=round(edge,5), richness_score=round(edge*(.35 if is_flat else 1.),4),has_burned_subtitle=subtitle_edge)


def probe_video(path):
    proc = subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
                           'format=duration:stream=duration','-of','json',str(path)],
                          check=True,capture_output=True,text=True)
    data = json.loads(proc.stdout)
    if not data['streams']:
        raise ValueError(f'素材没有视频流：{path.name}')
    video_duration = data['streams'][0].get('duration')
    return float(data['format']['duration'] if video_duration in (None,'N/A') else video_duration)


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def entity_vocabulary(custom=None):
    if custom is None:
        return TOOLS
    if isinstance(custom,list):
        if any(not isinstance(name,str) for name in custom):
            raise ValueError('custom_entities 列表须包含实体名称')
        custom = {name:[] for name in custom}
    if not isinstance(custom,dict):
        raise ValueError('custom_entities 须为字典或名称列表')
    vocabulary = dict(TOOLS)
    for name, aliases in custom.items():
        aliases = [aliases] if isinstance(aliases,str) else aliases
        if not isinstance(name,str) or not name.strip() or not isinstance(aliases,list) or any(
                not isinstance(alias,str) or not alias.strip() for alias in aliases):
            raise ValueError('custom_entities 的名称和别名须为非空文本')
        key = unicodedata.normalize('NFKC',name.strip()).casefold()
        vocabulary[key] = (*vocabulary.get(key,()),key,*(unicodedata.normalize('NFKC',alias.strip()).casefold() for alias in aliases))
    return vocabulary


def entities(value, vocabulary=TOOLS):
    text = unicodedata.normalize('NFKC', value).casefold()
    result = set()
    for tool, aliases in vocabulary.items():
        for alias in aliases:
            pattern = re.escape(alias)
            if alias.isascii():
                pattern = rf'(?<![a-z0-9]){pattern}(?![a-z0-9])'
            if re.search(pattern, text):
                result.add(tool)
                break
    return result


def stage_mode(shot):
    return shot.get('stage_mode', shot.get('kind'))


def primary_files(shot):
    auxiliary = set(shot.get('aux_files',()))
    return [path for path in shot.get('files',[]) if path not in auxiliary]


def is_real_shot(shot):
    mode = stage_mode(shot)
    if mode in REAL:
        return True
    if mode=='evidence_spotlight':
        files = shot.get('media',primary_files(shot))
        return bool(files and Path(files[0]).suffix.lower() in VIDEO_EXTENSIONS | {'.gif'})
    return False


def semantic_binding_gate(shots, custom_entities=None):
    violations = []
    vocabulary = entity_vocabulary(custom_entities)
    for shot in shots:
        mode = stage_mode(shot)
        topic = shot.get('spoken_topic')
        visual = shot.get('visual_subject')
        binding = shot.get('semantic_binding', shot.get('binding'))
        tags = shot.get('semantic_tags', [])
        if (not isinstance(topic,str) or not topic.strip() or not isinstance(visual,str) or not visual.strip()
                or binding not in BINDINGS or not isinstance(tags,list)
                or not tags or any(not isinstance(tag,str) or not tag.strip() for tag in tags)):
            violations.append({'shot':shot.get('id'),'reason':'缺少台词主题、画面主体、语义标签或绑定类别'})
            continue
        spoken = topic+' '+str(shot.get('anchor_text',''))
        mentioned = entities(spoken,vocabulary)
        labeled = entities(' '.join(tags),vocabulary)
        shown = entities(visual,vocabulary)
        explicit = shot.get('spoken_entity')
        if isinstance(explicit,str) and explicit.strip():
            named = entities(explicit,vocabulary)
            if not named and not (normalized(explicit) in {normalized(tag) for tag in tags}
                                  and normalized(explicit) in normalized(visual)):
                violations.append({'shot':shot.get('id'),'reason':'声明的工具实体未同时出现在主体和素材标签'})
                continue
            mentioned |= named
        required = mentioned
        if mode!='reference_breakdown' and binding in {'physical_prop','callback_cut'}:
            required = mentioned-CREATORS
        real = is_real_shot(shot)
        if real and required and not required <= (shown & labeled):
            violations.append({'shot':shot.get('id'),'reason':'点名工具与实际画面实体不一致',
                               'spoken_entities':sorted(mentioned),'visual_entities':sorted(shown & labeled)})
            continue
        is_abstract = shot.get('topic_kind') in {'rule','checklist','summary','principle'} or any(
            text in spoken.casefold() for text in ABSTRACT)
        if is_abstract and real and not (binding=='exact_tool_capture' and mentioned
                and re.search(r'打开|点击|在.+里|open\s|click\s',spoken,re.I)):
            overlays = shot.get('overlays', [])
            labels = ' '.join(' '.join([str(overlay.get('label','')), *map(str,overlay.get('items',[]))])
                              for overlay in overlays)
            if mode=='reference_breakdown':
                labels += ' '+str(shot.get('claim',''))
            matches_topic = any(text in labels.casefold() for text in ABSTRACT) or any(
                len(normalized(tag))>=2 and normalized(tag) in normalized(labels)
                and normalized(tag) in normalized(topic) for tag in tags)
            if (mode not in {'callout_rig','cold_open_ab','reference_breakdown','evidence_spotlight'} or not shot.get('has_motion_overlay')
                    or binding not in {'callback_cut','conceptual_explainer'} or not matches_topic):
                violations.append({'shot':shot.get('id'),'reason':'抽象规则或清单需要语义匹配的动效或总结贴图'})
    return {'ok':not violations,'violations':violations}


def spotlight_restraint_gate(shots):
    violations = []
    coordinates = {}
    count = 0
    maximum = max(3,int(len(shots)*.08))
    for shot in shots:
        key = shot.get('id')
        if stage_mode(shot)=='reference_breakdown' and any(
                not isinstance(shot.get(field),str) or not shot[field].strip() for field in ('channel','claim')):
            violations.append({'shot':key,'reason':'原片拆解缺少频道署名或拆解主张'})
        for overlay in shot.get('overlays',[]):
            if overlay.get('kind') not in VERIFIED_OVERLAYS:
                continue
            count += 1
            box = overlay.get('box')
            try:
                x,y,w,h = map(float,box)
                valid_box = all(isfinite(v) for v in (x,y,w,h)) and 64<=w<=680 and 48<=h<=340
            except (TypeError,ValueError):
                valid_box = False
            note = overlay.get('target_note')
            if not valid_box or overlay.get('target_verified') is not True or not isinstance(note,str) or not note.strip():
                violations.append({'shot':key,'reason':'局部高亮框未做像素目标核验或尺寸超限'})
            if valid_box:
                coords = tuple(round(v,1) for v in (x,y,w,h))
                first = coordinates.setdefault(coords,key)
                if first!=key:
                    violations.append({'shot':key,'first_shot':first,'reason':'禁止跨镜头复制粘贴相同盲框坐标'})
    if count>maximum:
        violations.append({'reason':'局部高亮框滥用超过全片 8% 上限','count':count,'maximum':maximum})
    return {'ok':not violations,'violations':violations,'spotlight_count':count,'maximum':maximum}


def opener_bgm_and_sfx_gate(bed, marks, duration):
    import numpy as np
    import soundfile as sf

    bed = Path(bed)
    rms_dbfs = None
    if bed.is_file():
        with sf.SoundFile(bed) as audio:
            source = audio.read(frames=round(min(15.,duration)*audio.samplerate),always_2d=True)
        if len(source):
            rms_dbfs = float(20*np.log10(max(1e-10,np.sqrt(np.mean(source**2)))))
    points = {round(float(mark['at']),3) for mark in marks if mark.get('kind') in SFX
              and 0 <= float(mark.get('at',-1)) < min(duration,45.) and float(mark.get('gain',1.))>0}
    return {'ok':rms_dbfs is not None and rms_dbfs > -42. and len(points)>=3,
            'bed_opener_rms_dbfs':rms_dbfs,'opener_sound_mark_count':len(points)}


def first_half_motion_density_gate(shots, duration):
    counts = [0,0]
    moving = [0,0]
    bare, longest = 0.,0.
    previous = 0.
    for shot in sorted(shots,key=lambda clip:float(clip['start'])):
        start,end = float(shot['start']),float(shot['end'])
        half = int(start >= duration/2)
        counts[half] += 1
        mode = stage_mode(shot)
        has_overlay = any(overlay.get('kind') in MOTION_OVERLAYS for overlay in shot.get('overlays',[]))
        moving[half] += int(mode in MOTION or mode=='studio_ui' or has_overlay)
        if is_real_shot(shot) and mode not in MOTION and not has_overlay:
            bare = (bare if start-previous<=.001 else 0.)+end-start
            longest = max(longest,bare)
        else:
            bare = 0.
        previous = end
    shares = [motion/max(1,n) for motion,n in zip(moving,counts)]
    return {'ok':min(shares)>=.35 and longest<=16.+1e-6,'half_motion_shares':shares,
            'motion_shots_by_half':moving,'longest_bare_video_seconds':longest}


def _voice_files(project, timeline):
    tracks = timeline.get('voice_tracks',[])
    if tracks:
        return [(row.get('id',str(i+1)),project/row['path']) for i,row in enumerate(tracks)]
    manifest = project/'voice/voice-manifest.json'
    if not manifest.is_file():
        return []
    return [(chapter['id'],manifest.parent/chapter['audio'])
            for chapter in json.loads(manifest.read_text())['chapters']]


def breath_integrity_gate(project, timeline):
    import numpy as np
    import soundfile as sf

    project = Path(project)
    violations = []
    tracks = _voice_files(project,timeline)
    if not tracks:
        violations.append({'reason':'缺少可审计的原始人声轨'})
    for key,path in tracks:
        if not path.is_file():
            violations.append({'chapter':key,'reason':'人声轨缺失'})
            continue
        x,rate = sf.read(path,always_2d=True)
        loud = np.max(np.abs(x),axis=1) >= 10**(-80/20)
        active = np.flatnonzero(loud)
        if not len(active):
            violations.append({'chapter':key,'reason':'人声轨没有有效声音'})
            continue
        start,stop = active[0],active[-1]+1
        edges = np.flatnonzero(np.diff(np.r_[False,~loud[start:stop],False]))
        for left,right in edges.reshape(-1,2):
            if right-left > .040*rate:
                violations.append({'chapter':key,'at':round((start+left)/rate,5),
                                   'duration_ms':round((right-left)*1000/rate,2),'reason':'句间真空断崖'})
    logs = list((project/'voice/analysis').glob('post-alignment-*.json'))
    logs.extend(project/path for path in timeline.get('voice_processing_logs',[]))
    for path in sorted(set(logs)):
        text = path.read_text()
        if 'np.zeros' in text or re.search(r'"kind"\s*:\s*"insert"',text):
            violations.append({'log':str(path.relative_to(project)),'reason':'检测到句间真空插入记录'})
    return {'ok':not violations,'chapters':len(tracks),'violations':violations}


def timeline_gates(timeline, project, duration, *, real_range=(.45,.72)):
    shots = timeline['shots']
    project = Path(project)
    cues = {str(row['id']):float(row['firstCharTime']) for row in timeline.get('cues',[])}
    previous = real_seconds = deviation = 0.
    invalid, unaligned, missing = [],[],[]
    seen_ids, digest_cache = set(),{}
    card_durations, invalid_cards = {}, []
    source_reuse = defaultdict(list)
    overlaps, bad_callbacks = [], []
    for shot in sorted(shots,key=lambda row:float(row['start'])):
        key = shot['id']
        a,b = float(shot['start']),float(shot['end'])
        if key in seen_ids or not (abs(a-previous)<=.001 and a<b<=duration+.045):
            invalid.append(key)
        seen_ids.add(key)
        previous = b
        cue = cues.get(shot.get('anchor_cue_id'))
        if cue is not None:
            deviation = max(deviation,abs(a-cue))
        if cue is None or abs(a-cue)>.220001:
            unaligned.append(key)
        mode = stage_mode(shot)
        span = b-a
        video_windows = []
        files = primary_files(shot)
        if any(file not in shot.get('files',()) or Path(file).suffix.lower() not in IMAGE_EXTENSIONS
               or not (project/file).is_file() for file in shot.get('aux_files',())):
            missing.append(key)
        if mode=='triptych_cards':
            cards = shot.get('cards',[])
            if (not isinstance(cards,list) or not 2<=len(cards)<=4
                    or any(not isinstance(card,dict) or not isinstance(card.get('source'),str) for card in cards)
                    or [card['source'] for card in cards]!=files):
                invalid_cards.append(key)
            else:
                for card in cards:
                    path = project/card['source']
                    try:
                        reveal_at = float(card['reveal_at'])
                        media_start = float(card.get('media_start',0.))
                        if (card.get('loop') or not path.is_file() or not 0<=reveal_at<b-a
                                or not isfinite(media_start) or media_start<0):
                            raise ValueError('卡片源或入点无效')
                        if path.suffix.lower() in VIDEO_EXTENSIONS:
                            if path not in card_durations:
                                card_durations[path] = probe_video(path)
                            if card_durations[path]+1e-5<media_start+span-reveal_at+.2:
                                raise ValueError('卡片视频缺少余量')
                            video_windows.append((path,media_start,span-reveal_at))
                        elif path.suffix.lower() not in IMAGE_EXTENSIONS:
                            raise ValueError('卡片素材格式无效')
                    except (TypeError,ValueError,KeyError,OSError,subprocess.CalledProcessError):
                        invalid_cards.append(key)
                        break
        if mode=='evidence_spotlight' and (len(files)!=1 or not (project/files[0]).is_file()
                                           or Path(files[0]).suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS):
            missing.append(key)
        if is_real_shot(shot):
            real_seconds += span
            videos = [project/f for f in files if Path(f).suffix.lower() in VIDEO_EXTENSIONS]
            if not videos:
                missing.append(key)
            media_start = float(shot.get('media_start',0.))
            video_windows.extend((path,media_start,span) for path in videos)
        callback_of = shot.get('callback_of')
        valid_callback = bool(
            callback_of and callback_of != key and callback_of in seen_ids
            and mode in {'hyperframes_block', 'onetake_clip'}
        )
        for path, source_start, play_span in video_windows:
            if not path.is_file():
                missing.append(key)
                continue
            if not isfinite(source_start) or source_start<0 or play_span<=0:
                invalid.append(key)
                continue
            digests = shot.get('gif_source_hashes',{})
            digest = digests.get(path.relative_to(project).as_posix()) if digests and path.is_relative_to(project) else None
            if not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest):
                digest = None
            if digest is None and path not in digest_cache:
                with path.open('rb') as f:
                    digest_cache[path] = hashlib.file_digest(f,'sha256').hexdigest()
            digest = digest or digest_cache[path]
            previous_uses = source_reuse[digest]
            callback = bool(callback_of and callback_of!=key and any(use['shot']==callback_of for use in previous_uses))
            valid_callback |= callback
            source_end = source_start+play_span
            if not callback:
                for use in previous_uses:
                    overlap = min(source_end,use['end'])-max(source_start,use['start'])
                    if not use['callback'] and overlap>.250001:
                        overlaps.append(dict(sha256=digest,first_shot=use['shot'],shot=key,seconds=round(overlap,5)))
            previous_uses.append(dict(shot=key,start=source_start,end=source_end,callback=callback))
        if callback_of and not valid_callback:
            bad_callbacks.append(key)
    if abs(previous-duration)>.045:
        invalid.append('timeline_end')
    ratio = real_seconds/duration if duration else 0.
    ratio_ok = real_range[0]<=ratio<=real_range[1]
    repeats = {digest:len(uses) for digest,uses in source_reuse.items()
               if sum(not use['callback'] for use in uses)>2 or sum(use['callback'] for use in uses)>1}
    return {'ok':not (invalid or unaligned or repeats or missing or invalid_cards or overlaps or bad_callbacks) and ratio_ok,
            'real_ratio':ratio,'ratio_ok':ratio_ok,'invalid_shots':invalid,'missing_real_media':missing,
            'invalid_triptych_media':invalid_cards,
            'overlapping_source_windows':overlaps,'invalid_callbacks':bad_callbacks,
            'max_anchor_deviation':deviation,'unaligned':unaligned,'overused_sources':repeats}


def explainer_density_gate(shots, project=None):
    violations = []
    for shot in shots:
        if stage_mode(shot)!='explainer_clip':
            continue
        key = shot['id']
        spec = shot.get('spec')
        if not isinstance(spec,dict) and project is not None:
            root = Path(project)
            path = shot.get('explainer_spec') or spec
            if not path:
                files = shot.get('files',[])
                expected = f'exp-{key}.json'
                path = next((str(Path(item).with_suffix('.json')) for item in files
                             if Path(item).with_suffix('.json').name==expected),None)
            candidates = [root/path] if path else sorted(root.glob(f'acts/*/assets/exp-{key}.json'))
            try:
                spec = json.loads(candidates[0].read_text()) if len(candidates)==1 else None
            except (OSError,ValueError):
                spec = None
        if not isinstance(spec,dict) or not isinstance(spec.get('cues'),list):
            violations.append(dict(shot=key,reason='缺少可核验的解说动效 spec'))
            continue
        cues = spec['cues']
        if spec.get('grammar')=='y3_whiteboard' and any(
                cue.get('kind')=='draw' and (cue.get('data') or {}).get('icon') not in WHITEBOARD_ICONS for cue in cues):
            violations.append(dict(shot=key,reason='y3_whiteboard 的 draw 缺少有效 data.icon，禁止空笔画白板'))
        visible = sum(len(''.join(str(row.get(field) or '').split())) for cue in cues
                      for row in (cue,cue.get('data') or {}) for field in ('text','sub','bad','good','label'))
        if visible<26 and not any(cue.get('kind') in STRUCTURED_CUES for cue in cues):
            violations.append(dict(shot=key,reason='解说动效信息密度过低（少于 26 字且无图表/卡片结构），页面过于空旷'))
    return {'ok':not violations,'violations':violations}


def onetake_craft_gate(shots, project):
    checked, violations = [], []
    project = Path(project)
    for shot in shots:
        if stage_mode(shot) != 'onetake_clip':
            continue
        key = shot['id']
        checked.append(key)
        files = primary_files(shot)
        try:
            if len(files) != 1:
                raise ValueError('缺少 Onetake 视频')
            clip = (project/files[0]).resolve()
            if not clip.is_relative_to(project.resolve()) or not clip.is_file():
                raise ValueError('Onetake 视频路径无效')
            probe = json.loads(clip.with_suffix('.onetake-probe.json').read_text())
            render = json.loads(clip.with_suffix('.render.json').read_text())
            if probe['seek_errors'] or probe['page_errors']:
                raise ValueError('Onetake 探针检测到页面或 seek 异常')
            if type(render['shutter']) not in (int,float) or not 0 < render['shutter'] <= 360:
                raise ValueError('Onetake 渲染未启用快门')
        except (OSError,ValueError,TypeError,KeyError) as error:
            violations.append(dict(shot=key,reason=str(error)))
    return dict(ok=not violations,checked=checked,violations=violations)


def video_gates(timeline, project, rendered, duration, errors, *, v10=False):
    gates = {
        'v7_timeline_gate': timeline_gates(timeline,project,duration,real_range=(.30,.65) if v10 else (.45,.72)),
        'semantic_binding_gate': semantic_binding_gate(timeline['shots'],timeline.get('custom_entities')),
        'spotlight_restraint_gate': spotlight_restraint_gate(timeline['shots']),
        'opener_bgm_and_sfx_gate': opener_bgm_and_sfx_gate(Path(rendered).parent/'bed-only.wav',timeline.get('sound_marks',[]),duration),
        'first_half_motion_density_gate': first_half_motion_density_gate(timeline['shots'],duration),
        'breath_integrity_gate': breath_integrity_gate(project,timeline),
        'explainer_density_gate': explainer_density_gate(timeline['shots'],project),
        'onetake_craft_gate': onetake_craft_gate(timeline['shots'],project),
    }
    for name,report in gates.items():
        if not report['ok']:
            errors.append(f'v7 {name} 未通过')
    return {'real_ratio':gates['v7_timeline_gate']['real_ratio'],**gates}


RIGS = {'fullbleed_rig', 'callout_rig', 'real_video', 'web_cam'}
WINDOWED = {'perspective_3d', 'studio_window'}
RASTER = {'.jpg', '.jpeg', '.png', '.webp'}


def shot_span(shot):
    return round(float(shot['end']) - float(shot['start']), 5)


def pacing_and_rhythm_gate(shots, duration):
    from math import ceil
    spans = sorted(shot_span(s) for s in shots)
    average = duration / len(shots) if shots else 0
    p90 = spans[ceil(.9 * len(spans))-1] if spans else 0
    long_shots, violations = [], []
    for shot in shots:
        span, mode = shot_span(shot), stage_mode(shot)
        reveals = {card.get('reveal_at', 0) for card in shot.get('cards', [])
                   if Path(card['source']).suffix.lower() in VIDEO_EXTENSIONS}
        compound = (mode == 'triptych_cards' and len(reveals) >= 2 or mode == 'cold_open_ab'
                    or mode == 'reference_breakdown' and shot.get('cut_points') or len(shot.get('camera_moves', [])) >= 2)
        limit = 13 if compound else 10.5
        if span > 10.5:
            long_shots.append(shot['id'])
        if span > limit:
            violations.append(dict(shot=shot['id'], seconds=span, limit=limit))
    if not shots or average > 6.5 or p90 > 9 or len(long_shots) > max(1, len(shots)//20):
        violations.append(dict(reason='全片均值、P90 或长镜数量超限'))
    return dict(ok=not violations, average_shot_seconds=round(average, 3), p90_shot_seconds=p90,
                long_shots=long_shots, violations=violations)


def framing_and_variety_gate(shots, duration):
    from itertools import groupby
    captures = [s for s in shots if stage_mode(s) in RIGS]
    full = sum(shot_span(s) for s in captures if s.get('framing','fullbleed') == 'fullbleed')
    capture_span = sum(map(shot_span,captures))
    full_ratio = full/capture_span if capture_span else 1.
    angle = sum(shot_span(s) for s in shots if s.get('framing') == 'perspective_3d')
    angle_ratio = angle/duration if duration else 0.
    callouts = [s for s in shots if stage_mode(s) == 'callout_rig']
    corners = sum({o['kind'] for o in s.get('overlays', [])} == {'corner_tag'} for s in callouts)
    corner_ratio = corners/len(callouts) if callouts else 0.
    studio_count = sum(stage_mode(s) == 'studio_ui' for s in shots)
    studio_ratio = studio_count / len(shots) if shots else 0.
    violations = []
    if studio_ratio > .18:
        violations.append(dict(reason='studio_ui_ratio', limit=.18))
    for left, right in zip(shots, shots[1:]):
        if stage_mode(left) == stage_mode(right) == 'studio_ui':
            violations.append(dict(reason='adjacent_studio_ui', shots=[left['id'], right['id']]))
    for name, failed in [('fullbleed_ratio', full_ratio < .70), ('perspective_ratio', angle_ratio > .15),
                         ('corner_tag_ratio', len(callouts) >= 4 and corner_ratio > .60)]:
        if failed:
            violations.append(dict(reason=name))
    window_runs = [list(group) for windowed,group in groupby(shots, lambda s:s.get('framing') in WINDOWED) if windowed]
    for run in window_runs:
        if len(run) > 1:
            violations.append(dict(reason='adjacent_windows', shots=[s['id'] for s in run]))
    runs = {}
    for name, matches, count_limit, time_limit in (
            ('fullbleed',lambda s:stage_mode(s) in RIGS and s.get('framing','fullbleed')=='fullbleed',5,35),
            ('graphic',lambda s:not is_real_shot(s),4,28)):
        lengths = []
        for match,group in groupby(shots,matches):
            if match:
                run = list(group)
                seconds = round(sum(map(shot_span,run)),5)
                lengths.append((len(run),seconds))
                if len(run)>count_limit or seconds>time_limit:
                    violations.append(dict(reason=name+'_run',shots=[s['id'] for s in run],seconds=seconds))
        runs[name] = dict(max_count=max((n for n,_ in lengths),default=0),
                          max_seconds=max((t for _,t in lengths),default=0))
    return dict(ok=not violations, fullbleed_ratio=round(full_ratio,4), perspective_ratio=round(angle_ratio,4),
                runs=runs,capture_count=len(captures), perspective_count=sum(s.get('framing')=='perspective_3d' for s in captures),
                max_consecutive_windowed_shots=max(map(len,window_runs),default=0),
                studio_ui_count=studio_count, studio_ui_ratio=round(studio_ratio,4),
                corner_tag_ratio=round(corner_ratio,4), violations=violations)


def effective_frame(frame, shot, rendered=False):
    from PIL import ImageOps
    width, height = frame.size
    if shot.get('framing') in WINDOWED:
        if rendered:
            return frame.crop((round(width*136/1920), round(height*142/1080),
                               round(width*1784/1920), round(height*868/1080)))
        return ImageOps.fit(frame, (320,141))
    return frame.crop((0,0,width,round(height*890/1080)))


def shell_metrics(scores, *, precheck=False):
    from statistics import median
    flat = median(s['flat_bg_ratio'] for s in scores)
    edge = median(s['edge_density'] for s in scores)
    richness = median(s['richness_score'] for s in scores)
    return dict(flat_bg_ratio=flat, edge_density=edge, richness_score=richness,
                low_density=sum(s['flat_bg_ratio'] > .78 and (s['edge_density'] < .018 or precheck and s['richness_score'] < .007)
                                for s in scores) > len(scores)/2)


def capture_frame(shot, project, rendered, local, source=None, *, prefer_rendered=False):
    from io import BytesIO
    from PIL import Image
    files = [source] if source else primary_files(shot) or [shot.get('source','')]
    path = next((Path(project)/f for f in files if Path(f).suffix.lower() in VIDEO_EXTENSIONS
                 and (Path(project)/f).is_file()), None)
    use_render = prefer_rendered or path is None
    at = float(shot['start'] if use_render else shot.get('media_start',0)) + local
    video = rendered if use_render else path
    if not video:
        raise ValueError('缺少可抽帧的视频')
    cmd = ['ffmpeg','-nostdin','-v','error','-ss',f'{at:.5f}','-threads','2','-i',str(video),
           '-frames:v','1','-vf','scale=320:-1','-threads','1','-c:v','png','-f','image2pipe','-']
    data = subprocess.run(cmd,check=True,capture_output=True).stdout
    with Image.open(BytesIO(data)) as frame:
        return effective_frame(frame.convert('RGB'),shot,use_render)


def overlay_ocr(source, at, viewport, binary):
    x,y,w,h = viewport
    with tempfile.TemporaryDirectory() as temp:
        frame = Path(temp)/'frame.png'
        transform = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},pad=1920:1080:{x}:{y}'
        subprocess.run(['ffmpeg','-v','error','-ss',str(at),'-i',str(source),'-frames:v','1',
                        '-vf',transform,'-threads','1',str(frame)],check=True,capture_output=True,timeout=10)
        result = subprocess.run([str(binary),str(frame)],check=True,capture_output=True,text=True,timeout=5)
    return json.loads(result.stdout)['results']


def quadrant_heading_hits(lines, viewport):
    """Find text obscured in the upper-right title area of a dense four-panel view."""
    left, top, width, height = viewport
    groups = [[], [], [], []]
    for line in lines:
        if not any(c.isalnum() for c in line['text']):
            continue
        x,y,w,h = line['box']
        cx,cy = (x+w/2-left)/width, (y+h/2-top)/height
        if .04 <= cx < .98 and .07 <= cy < .96:
            groups[2*int(cy >= .5)+int(cx >= .5)].append(line)
    if min(map(len,groups)) < 3:
        return []
    bx,by,bw,bh = STAT_BADGE_BOX
    hits = []
    for line in groups[1]:
        x,y,w,h = line['box']
        if y <= top+height*.25 and x<bx+bw and x+w>bx and y<by+bh and y+h>by:
            hits.append(line)
    return hits


def stat_badge_occlusions(row, source, overlay, binary=OCR, reader=overlay_ocr):
    span, start = row['play_span'], float(overlay.get('at',0))
    stop = min(span,start+float(overlay.get('duration',span-start)))
    hits, unavailable = [], []
    if stop <= start:
        return hits, unavailable
    for sample,local in zip(('首','中','尾'),(start,(start+stop)/2,max(start,stop-1/30))):
        at = row['media_start']+local
        context = dict(shot=row['id'],source=str(source),overlay='stat_badge',sample=sample,
                       media_time=at,overlay_box=list(STAT_BADGE_BOX))
        try:
            lines = reader(source,at,row['viewport'],binary)
        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
            unavailable.append(dict(context,reason=str(exc)))
            continue
        for line in quadrant_heading_hits(lines,row['viewport']):
            hits.append(dict(context,text=line['text'],text_box=line['box'],severity='error',
                             reason='quadrant_heading_occlusion'))
    return hits, unavailable


def corner_title_violation(shot, overlay):
    if overlay.get('kind') == 'corner_tag' and shot.get('framing', 'fullbleed') == 'fullbleed' and overlay.get('position') == 'top_left':
        return dict(shot=shot['id'], reason='corner_tag_over_source_title', severity='error')
    return None


def quadrant_overlay_gate(shots, project):
    violations = []
    for shot in shots:
        violations.extend(hit for o in shot.get('overlays',[]) if (hit := corner_title_violation(shot,o)))
        badges = [o for o in shot.get('overlays',[]) if o.get('kind')=='stat_badge']
        if not badges:
            continue
        files = primary_files(shot) or [shot.get('source','')]
        video = next((name for name in files if Path(name).suffix.lower() in VIDEO_EXTENSIONS),None)
        if not video:
            continue
        framed = shot.get('framing') or shot.get('layout','fullbleed')
        row = dict(id=shot['id'],play_span=shot_span(shot),media_start=shot.get('media_start',0),
                   viewport=STUDIO_VIEW if framed in {'studio_window','perspective_3d'} else (0,0,1920,1080))
        for badge in badges:
            hits, missing = stat_badge_occlusions(row,Path(project)/video,badge)
            violations.extend(hits+missing)
    return dict(ok=not violations,violations=violations)


def visual_richness_gate(timeline, project, rendered):
    checked, violations = {}, []
    for shot in timeline['shots']:
        if stage_mode(shot) not in RIGS or shot.get('semantic_binding') != 'exact_tool_capture':
            continue
        span = shot_span(shot)
        pad = min(.3, span/4)
        try:
            scores = [frame_scores(capture_frame(shot,project,rendered,t)) for t in (pad,span/2,span-pad)]
            metrics = shell_metrics(scores)
            checked[shot['id']] = dict(samples=scores, **metrics)
            if metrics['low_density']:
                violations.append(dict(shot=shot['id'],reason='low_density_shell_capture',**metrics))
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            violations.append(dict(shot=shot['id'],reason=str(exc)))
    return dict(ok=not violations,checked=checked,violations=violations)


def composition_entry_for_audit(shot, project, manifest_root=None):
    project = Path(project)
    mode = stage_mode(shot)
    field, default = ('comp','comp.html') if mode == 'onetake_clip' else ('composition','index.html')
    for root in (project,Path(manifest_root) if manifest_root else project):
        if shot.get(field):
            path = root/shot[field]
            path = path/default if path.is_dir() else path
            if path.is_file():
                return path
    # v8 renders keep HyperFrames sources in the act and Onetake sources beside the manifest.
    root = Path(manifest_root) if manifest_root else project.parent
    manifest = root/'episode-manifest.json'
    if manifest.is_file():
        original = next((s for s in json.loads(manifest.read_text())['shots'] if s['id']==shot['id']), {})
        if original.get(field):
            path = root/original[field]
            path = path/default if path.is_dir() else path
            if path.is_file():
                return path
    raise ValueError('缺少合成源码')


def composition_material(entry):
    scripts = [entry, *(p for p in entry.parent.rglob('*') if p.suffix.lower() in {'.js','.mjs','.css'}
                        and 'vendor' not in p.relative_to(entry.parent).parts
                        and p.name not in {'motion.js','ui_kit.js','gsap.min.js','sketch_brush.js'})]
    sources, images = [], set()
    for path in scripts:
        code = path.read_text()
        sources.append(f"<script>{code}</script>" if path.suffix.lower() in {".js", ".mjs"} else code)
        for name in re.findall(r"""[\w./%+@-]+\.(?:png|jpe?g|webp)\b""", code, re.I):
            if re.search(r'(?:^|/)vframes_[0-9a-f]+/f_(?!0001\.jpg)\d+\.jpg$', name, re.I):
                continue
            image = (path.parent/name).resolve()
            if not image.is_file():
                image = (entry.parent/name).resolve()
            images.add(image)
    return '\n'.join(sources), sorted(images)


def legacy_pink_outline(source):
    color = r'(?:#(?:ec4899|f43f5e|e61e72|ff5497|ff6398|ff488f|ff3e8d)(?:[0-9a-f]{2})?\b|rgba?\(\s*(?:244\s*,\s*63\s*,\s*94|236\s*,\s*72\s*,\s*153)\b)'
    return bool(re.search(r'(?:border(?:-[\w-]+)?|outline(?:-color)?|box-shadow)\s*:[^;{}]*?' + color, source, re.I))


def dual_engine_craft_gate(shots, project, manifest_root=None, *, v10=False):
    checked, violations, modes = {}, [], {}
    for shot in shots:
        mode = stage_mode(shot)
        if mode not in {'onetake_clip','hyperframes_block'}:
            continue
        try:
            entry = composition_entry_for_audit(shot,project,manifest_root)
            source,images = composition_material(entry)
            if v10 and shot.get('stage_look')=='cinema_black' and legacy_pink_outline(source):
                violations.append(dict(shot=shot['id'],reason='legacy_pink_outline'))
            checked[shot['id']] = [p.name for p in images]
            spatial = False
            if v10:
                from audit_spatial import composition_motion
                spatial, modes[shot['id']] = composition_motion(source, shot.get('visual_mode'))
            if len(images) >= 2 and not spatial:
                violations.append(dict(shot=shot['id'], reason='static_raster_gallery', images=checked[shot['id']]))
            if mode == 'onetake_clip':
                zooms = {float(n) for n in re.findall(r'\bzoom\s*:\s*([\d.]+)',source)}
                morph = re.search(r'\b(?:OM\.(?:morphRect|zoomThrough|spring)|UIK\.\w+|SKETCH\.\w+|(?:ctx|context)\.(?:arc|bezierCurveTo)|setAttribute\([\'"]d[\'"])\s*[, (]',source)
                if len(zooms)<2 and not morph:
                    violations.append(dict(shot=shot['id'],reason='missing_camera_or_morph'))
        except (OSError,ValueError) as exc:
            violations.append(dict(shot=shot['id'],reason=str(exc)))
    return dict(ok=not violations,checked=checked,violations=violations,**({'verified_modes':modes} if v10 else {}))


def visual_fingerprint(image):
    """Remove solid page margins before comparing versions of the same visual."""
    from PIL import Image, ImageChops, ImageStat
    image = image.convert('RGB')
    thumb = image.copy()
    thumb.thumbnail((320,320))
    background = thumb.getpixel((0,0))
    diff = ImageChops.difference(thumb,Image.new('RGB',thumb.size,background)).convert('L')
    box = diff.point(lambda value: 255 if value > 22 else 0).getbbox()
    content = thumb.crop(box) if box else thumb
    if min(content.size) < 3 or max(ImageStat.Stat(content).stddev) < 5:
        return None
    return difference_hash(content)


def stage_visuals(timeline, project, rendered):
    from PIL import Image
    from audit_spatial import page_signature
    from io import BytesIO
    cache = {}
    fingerprints, errors = [], []
    project = Path(project)
    for shot in timeline['shots']:
        key, mode = shot['id'], stage_mode(shot)
        try:
            files = primary_files(shot) or shot.get('sources',[]) or ([shot['source']] if shot.get('source') else [])
            images = {project/p for p in files if Path(p).suffix.lower() in RASTER}
            cards = shot.get('cards',[])
            images.update(project/c['source'] for c in cards if Path(c['source']).suffix.lower() in RASTER)
            if mode in {'onetake_clip','hyperframes_block'}:
                entry = composition_entry_for_audit(shot,project)
                source, stills = composition_material(entry)
                images.update(stills)
                for directory in {p.parent for p in stills if p.parent.name.startswith('vframes_')}:
                    sequence = sorted(directory.glob('f_*.jpg'))
                    if sequence:
                        images.add(sequence[len(sequence)//2])
                # Source manifests may also name the original input. Only DOM media
                # links and existing script-referenced assets are part of the composition.
                video_refs = re.findall(r"""<(?:video|source)\b[^>]*?\bsrc=["']([^"']+)["']""", source, re.I)
                images.update((entry.parent/ref).resolve() for ref in video_refs
                              if Path(ref).suffix.lower() in VIDEO_EXTENSIONS)
                for ref in re.findall(r"""[\w./%+@-]+\.(?:mp4|webm)\b""", source, re.I):
                    media = entry.parent / ref
                    if media.is_file():
                        images.add(media.resolve())
            for path in sorted(images):
                path = path.resolve()
                if path not in cache:
                    if path.suffix.lower() in VIDEO_EXTENSIONS:
                        midpoint = probe_video(path) / 2
                        cmd = ['ffmpeg','-nostdin','-v','error','-ss',str(midpoint),'-threads','2','-i',str(path),
                               '-frames:v','1','-vf','scale=320:-1','-threads','1','-c:v','png','-f','image2pipe','-']
                        stream = BytesIO(subprocess.run(cmd, check=True, capture_output=True).stdout)
                    else:
                        stream = path.open('rb')
                    with stream, Image.open(stream) as image:
                        cache[path] = page_signature(image)
                fingerprints.append((key, *cache[path]))
            if mode in REAL or mode in {'triptych_cards','evidence_spotlight','studio_ui'}:
                videos = [(p,shot.get('media_start',0),0) for p in files if Path(p).suffix.lower() in VIDEO_EXTENSIONS]
                if cards:
                    videos = [(c['source'],c.get('media_start',0),c.get('reveal_at',0)) for c in cards
                              if Path(c['source']).suffix.lower() in VIDEO_EXTENSIONS]
                if not videos and mode in RIGS:
                    videos = [(None,0,0)]
                for video,start,reveal in videos:
                    frame = capture_frame(dict(shot,media_start=start,start=shot['start']+reveal),
                                          project,rendered,(shot_span(shot)-reveal)/2,video)
                    fingerprints.append((key, *page_signature(frame)))
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            errors.append(dict(shot=key,reason=str(exc)))
    return fingerprints, errors


def cross_stage_asset_dedup_gate(timeline, project, rendered, *, samples=None):
    import numpy as np
    fingerprints, errors = samples if samples is not None else stage_visuals(timeline, project, rendered)
    callbacks = {s['id']:s.get('callback_of') for s in timeline['shots']}
    collisions = set()
    for _, perceptual, colors in fingerprints:
        if perceptual is None:
            continue
        matched = []
        for key, other_hash, other_colors in fingerprints:
            if (key not in matched and other_hash is not None and
                    (perceptual ^ other_hash).bit_count() <= 6 and np.abs(colors-other_colors).mean() < 11):
                matched.append(key)
        if len(matched) > 2:
            valid_callback = any(callbacks[key] in matched[:i] for i,key in enumerate(matched))
            if len(matched)-int(valid_callback)>2:
                collisions.add(tuple(matched))
    violations = errors + [dict(shots=list(ids),reason='repeated_visual') for ids in sorted(collisions)]
    return dict(ok=not violations,fingerprints=len(fingerprints),violations=violations)


def external_showcase_diversity_gate(timeline, project, rendered, duration, *, samples=None):
    from urllib.parse import urlsplit
    from ipaddress import ip_address
    required = timeline.get('episode_kind') == 'tool_tutorial' and duration >= 90
    clusters, tools, urls, violations = [], set(), set(), []
    minimum = max(6, ceil(duration / 30)) if required else 0
    if required:
        visuals, errors = samples if samples is not None else stage_visuals(timeline, project, rendered)
        violations.extend(errors)
        for _, fingerprint, _ in visuals:
            if fingerprint is not None and all((fingerprint ^ other).bit_count() > 8 for other in clusters):
                clusters.append(fingerprint)
        if len(clusters) < minimum:
            violations.append(dict(reason='insufficient_visual_clusters', minimum=minimum))
        root = Path(project)
        ledger = root/'asset-ledger.jsonl'
        if not ledger.exists() and (root.parent/'episode-manifest.json').exists():
            ledger = root.parent/'asset-ledger.jsonl'
        if ledger.is_file():
            for line in ledger.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    url = next((row[k] for k in ('sourceUrl','source_url','url','prompt_or_url','source') if row.get(k)), '')
                    address = urlsplit(url)
                    host = address.hostname or ''
                    if address.scheme not in ('https','http') or '.' not in host or host.endswith(('.local','.localhost','.test','.invalid')):
                        continue
                    try:
                        if not ip_address(host).is_global:
                            continue
                    except ValueError:
                        pass
                    tool = Path(row.get('tool') or '').stem
                    if not tool and row.get('sourceType') == 'web_capture':
                        tool = 'record-web-cam' if row.get('kind') == 'web_cam_recording' else 'capture-web'
                    if not tool and row.get('usage') == '正文来源证据' and row.get('sourceName'):
                        tool = 'collect-entity'
                    if tool not in ('harvest-showcase-media','collect-entity','capture-web','rec-demo','record-web-cam','find-media'):
                        continue
                    if row.get('status') in ('failed','skipped') or not row.get('path') or not (ledger.parent/row['path']).exists():
                        continue
                    tools.add(tool)
                    urls.add(address._replace(fragment='').geturl())
                except (ValueError, AttributeError, TypeError):
                    violations.append(dict(reason='invalid_asset_record'))
            if len(tools) < 2 and len(urls) < 3:
                violations.append(dict(reason='insufficient_external_sources'))
    return dict(ok=not violations, required=required, distinct_clusters=len(clusters), minimum=minimum,
                tools=sorted(tools), external_sources=len(urls), violations=violations)


def tutorial_workflow_gate(timeline):
    shots = timeline['shots']
    vocabulary = entity_vocabulary(timeline.get('custom_entities'))
    named, process, product = set(), [], []
    checked = timeline.get('capture_scores')
    input_markers = r'输入.{0,8}(提示词|命令)|双击.{0,8}(改字|数字|图片)|拖动.{0,6}(图片|控制点)|点击.{0,8}(改色|配色)|安装命令|终端执行|命令行执行|agent.{0,8}(执行|运行|生成过程)|type.{0,8}prompt|terminal command'
    result_markers = r'交互|点击|拖[动拽]|编辑|操作成品|演示成品|interactive|click|drag|edit'
    for shot in shots:
        key = shot['id']
        visual = ' '.join([shot.get('visual_subject',''),*shot.get('semantic_tags',[])])
        named.update(entities(shot.get('spoken_topic','')+' '+str(shot.get('spoken_entity',''))+' '+visual,vocabulary)-CREATORS)
        files = primary_files(shot) or shot.get('sources',[]) or [shot.get('source','')]
        capture = (stage_mode(shot) in RIGS and shot.get('semantic_binding')=='exact_tool_capture'
                   and any(Path(f).suffix.lower() in VIDEO_EXTENSIONS for f in files))
        metric = (checked or {}).get(key,{})
        motion = checked is None or len({s['dhash'] for s in metric.get('samples',[])}) > 1
        if stage_mode(shot)=='studio_ui' and shot.get('studio_style') in {'terminal_pipeline','vscode_workbench'} and any(files):
            process.append(key)
        elif capture and motion and re.search(input_markers,visual,re.I):
            process.append(key)
        elif capture and motion and not metric.get('low_density') and re.search(result_markers,visual,re.I):
            product.append(key)
    duration = timeline.get('end') or sum(map(shot_span,shots))
    ratio = sum(shot_span(s) for s in shots if is_real_shot(s))/duration if duration else 0.
    kind = timeline.get('episode_kind')
    required = kind=='tool_tutorial' or kind!='essay' and len(named)>=2 and ratio>=.45
    minimum = max(2 if len(named)>=2 else 1,len(named)//2)
    violations = []
    if required and len(process)<minimum:
        violations.append('missing_input_or_execution')
    if required and not product:
        violations.append('missing_interactive_result')
    return dict(ok=not violations,required=required,entities=sorted(named),minimum_process_shots=minimum,
                process_shots=process,product_shots=product,violations=violations)


def case_monotony_gate(shots, duration):
    seconds, missing = defaultdict(float), []
    for shot in shots:
        tag, span = shot.get('case_tag'), shot_span(shot)
        if not isinstance(tag, str) or not tag.strip():
            missing.append(shot['id'])
            continue
        windows = shot.get('case_windows', [dict(tag=tag, start=0, end=span)])
        by_case = defaultdict(list)
        if not isinstance(windows, list) or not windows:
            missing.append(shot['id'])
            continue
        for window in windows:
            if not isinstance(window, dict):
                missing.append(shot['id'])
                break
            name, start, end = (window.get(k) for k in ('tag','start','end'))
            if (not isinstance(name, str) or not name.strip()
                    or any(type(t) not in (int, float) or not isfinite(t) for t in (start, end))
                    or not 0 <= start < end <= span + .001):
                missing.append(shot['id'])
                break
            by_case[name].append((start, min(end,span)))
        # Concurrent panels count once per visible case, even when two panels show the same work.
        for name, intervals in by_case.items():
            last = 0.
            for start, end in sorted(intervals):
                seconds[name] += max(0, end - max(start, last))
                last = max(last, end)
        covered = 0.
        for start, end in sorted(interval for values in by_case.values() for interval in values):
            if start > covered + .001:
                break
            covered = max(covered, end)
        if covered < span - .001:
            missing.append(shot['id'])
    curtains = sorted((shot for shot in shots if 'curtain_source_hashes' in shot),
                     key=lambda shot: shot['start'])
    for i, shot in enumerate(curtains):
        window = [s for s in curtains[:i+1] if shot['start'] - s['start'] < 85]
        sources = [h for s in window for h in s['curtain_source_hashes']]
        if len(window) > 2 or len(shot['curtain_source_hashes']) != 3 or len(sources) != len(set(sources)):
            missing.append(shot['id'])
    shares = {key: value / duration for key, value in seconds.items()}
    overused = [key for key, share in shares.items() if share > .30 + 1e-8]
    return dict(ok=not (missing or overused), shares=shares, missing=sorted(set(missing)), overused=overused)


def semantic_match_ledger(timeline):
    shots = {shot['id']:shot for shot in timeline['shots']}
    rows = timeline.get('semantic_alignment')
    cues = {cue['id']: cue.get('text') for cue in timeline.get('cues', [])}
    seen, invalid = set(), []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not isinstance(row.get('shot_id'), str):
            invalid.append('invalid_row')
            continue
        key = row['shot_id']
        shot = shots.get(key)
        if (not shot or key in seen or row.get('quote') != shot.get('spoken_topic')
                or row.get('quote') != cues.get(shot.get('anchor_cue_id'))
                or row.get('case_tag') != shot.get('case_tag')
                or row.get('case_windows') != shot.get('case_windows')
                or row.get('evidence') != shot.get('visual_subject')
                or not str(row.get('evidence', '')).strip()
                or any(type(row.get(k)) not in (int, float) or not isfinite(row[k]) for k in ('start','end'))
                or abs(row['start'] - shot['start']) > .034
                or abs(row.get('end', -1) - shot['end']) > .034):
            invalid.append(key)
        seen.add(key)
    missing = sorted(shots.keys() - seen)
    return dict(ok=not (invalid or missing), checked=len(seen), missing=missing, invalid=invalid)



def sfx_diversity_and_sync_gate(timeline, duration):
    from collections import Counter
    from kit.editorial.audio_mix import BUNDLED_SFX_MAP, INTERACTION_SOUNDS
    marks = sorted((m for m in timeline.get('sound_marks', []) if m.get('kind') != 'music_drop'),
                   key=lambda m: float(m['at']))
    counts, violations, previous = Counter(), [], []
    files_by_digest, audible_frames, deltas = {}, {}, []
    for mark in marks:
        kind, at = mark['kind'], float(mark['at'])
        gain = float(mark.get('gain',.32))
        if not isfinite(gain) or gain < .24:
            violations.append(dict(at=at,reason='inaudible_sfx_padding',gain=gain))
            continue
        audible_frames.setdefault(round(at*30),at)
        source = mark.get('source_file') or BUNDLED_SFX_MAP.get(kind)
        if not source:
            violations.append(dict(at=at,reason='unknown_source'))
            continue
        source = files_by_digest.setdefault(mark.get('source_sha256') or source, source)
        counts[source] += 1
        previous.append((source, mark.get('playback_rate', 1.)))
        if len(previous) >= 3 and previous[-1] == previous[-2] == previous[-3]:
            violations.append(dict(at=at,reason='identical_three_in_a_row',file=source))
        shot = (
            next((s for s in timeline['shots'] if s['start'] - 1e-3 <= at < s['end'] - 1e-4), None)
            or next((s for s in timeline['shots'] if s['start'] - 1e-3 <= at <= s['end'] + 1e-3), None)
        )
        if shot is None:
            violations.append(dict(at=at,reason='outside_shots'))
            continue
        points = [0., *shot.get('visual_action_times', shot.get('beats', []))]
        points.extend(float(row['at']) for key in ('overlays','interactions') for row in shot.get(key, []))
        if shot.get('interactions') and kind in INTERACTION_SOUNDS.values():
            points = [i['at'] for i in shot['interactions'] if INTERACTION_SOUNDS.get(i['action'])==kind]
            if not points:
                points = shot.get('visual_action_times',[])
        if kind=='zoom_swoosh':
            points = [*points,*shot.get('camera_action_times',[])]
        in_punch = any(o['kind']=='editorial_punch' for o in shot.get('overlays',[]))
        primary = kind in {'marker_stroke','shutter_whip','whoosh_cinematic','whoosh_short','whoosh','zoom_swoosh'} or (
            kind.startswith('impact_bass_') and in_punch)
        detail = kind in {'page_flip','click','click_soft','keypress','typing','counter_roll','ui_lock_bonk','paper_slap'}
        if shot.get('recipe') in {'logo_bento_stage','step_tree_focus'} and kind in {'card_thock','pop'}:
            detail = True
        if (primary and not .55 <= gain <= .74) or (detail and not .28 <= gain <= .44):
            violations.append(dict(at=at,reason='sfx_gain_tier',kind=kind,gain=gain))
        if kind in {'impact_bass_1','impact_bass_2'} and any(o['kind']=='editorial_punch' for o in shot.get('overlays',[])):
            points = [o['at'] for o in shot['overlays'] if o['kind']=='editorial_punch']
        if not points:
            violations.append(dict(shot=shot['id'],at=at,reason='wrong_interaction_sound'))
            continue
        delta = min(abs(at-shot['start']-p) for p in points)
        deltas.append(delta)
        if delta > .12001 or (kind == 'shutter_whip' and shot.get('recipe') != 'triptych_curtain'):
            violations.append(dict(shot=shot['id'],at=at,delta=round(delta,4),reason='action_mismatch'))
    times = sorted({0., duration, *audible_frames.values()})
    max_gap = max((b-a for a,b in zip(times,times[1:])),default=0.)
    density = len(audible_frames)/duration if duration else 0.
    if duration >= 30:
        if density < .72:
            violations.append(dict(reason='sfx_density_below_minimum',density=round(density,4)))
        if max_gap > 3.60001:
            violations.append(dict(reason='long_sfx_gap',seconds=round(max_gap,4)))
        if len(counts) < 6:
            violations.append(dict(reason='fewer_than_six_files'))
        if counts and max(counts.values()) > .28 * len(marks):
            violations.append(dict(reason='single_file_above_28_percent'))
    return dict(ok=not violations,count=len(marks),audible_action_points=len(audible_frames),
                density=round(density,4),max_sfx_gap=round(max_gap,4),
                max_sync_error=round(max(deltas,default=0.),5),files=dict(counts),violations=violations)


def chapter_voice_completeness_gate(timeline, project, duration):
    import soundfile as sf
    project = Path(project)
    refs = {str(r['id']): r for r in timeline.get('chapter_reference', [])}
    tracks = sorted(timeline.get('voice_tracks', []),key=lambda row:row.get('at',0.))
    picture_end = min(duration, max((s['end'] for s in timeline['shots']), default=0.))
    ends, violations = {}, []
    for index, track in enumerate(tracks):
        name = str(track.get('id',index+1))
        try:
            path = project / track['path']
            span = sf.info(path).duration
            end = track.get('at',0.) + span
            ends[name] = round(end,5)
            same_chapter = [s['end'] for s in timeline['shots'] if str(s.get('chapter',''))==name]
            coverage = max(same_chapter) if same_chapter else picture_end
            if index+1 < len(tracks):
                coverage = min(coverage,tracks[index+1].get('at',picture_end))
            if end > min(coverage,picture_end) + 1/30:
                violations.append(dict(chapter=name,reason='voice_past_picture',end=end))
            ref = refs.get(name)
            if ref:
                with path.open('rb') as source:
                    digest = hashlib.file_digest(source,'sha256').hexdigest()
                if abs(span-ref['duration']) > 1/30 or digest != ref['sha256']:
                    violations.append(dict(chapter=name,reason='voice_differs_from_reference'))
        except (OSError, RuntimeError, ValueError) as exc:
            violations.append(dict(chapter=name,reason=str(exc)))
    if not tracks or set(refs)-set(ends):
        violations.append(dict(reason='missing_chapter_track'))
    last_line = max((c['end'] for c in timeline.get('captions', [])), default=0.)
    if last_line > picture_end + 1/30:
        violations.append(dict(reason='last_caption_past_picture',end=last_line))
    return dict(ok=not violations, track_ends=ends,last_caption_end=last_line,violations=violations)


def enumerated_count_gate(shots, measured):
    numbers = {char:i for i,char in enumerate('零一二三四五六七八九十')}
    checked, violations = [], []
    for shot in shots:
        actual = measured.get(shot['id'],{}).get('frames',[])
        recipe = shot.get('recipe') or next((f.get('recipe') for f in actual if f.get('recipe')), None)
        expected = shot.get('expected_items')
        numbered_recipe = recipe in {'logo_bento_stage','progressive_sim_cards','step_tree_focus','formula_pill_chain'}
        # A showcase intro may promise five tools before the actual named list.
        if expected is None and not numbered_recipe:
            continue
        claim = ''.join([shot.get('spoken_topic',''), shot.get('visual_subject',''),
                         next((f['countClaim'] for f in actual if f.get('countClaim')), '')])
        numerals = re.findall(r'([一二两三四五六七八九十]|\d+)(?:个(?:免费|开源)*神器|款工具|大优势|大降维打击|个步骤|步(?:工作流|流程)|步(?=第一步|$))',
                              re.sub(r'\s+', '', claim))
        declared = {int(n) if n.isdecimal() else 2 if n=='两' else numbers[n] for n in numerals}
        if expected is not None:
            declared.add(expected)
        if not declared:
            continue
        expected = max(declared)
        counts = [f.get('enumeratedItems',[]) for f in actual]
        names = max(counts,key=lambda group:len(set(group)),default=[])
        checked.append(dict(shot=shot['id'],expected=expected,items=names))
        if len(declared)!=1 or len(names)!=expected or len(set(names))!=expected:
            violations.append(checked[-1])
    return dict(ok=not violations,checked=checked,violations=violations)


def no_early_cli_gate(timeline, frames):
    violations = []
    if timeline.get('episode_kind') == 'tool_tutorial':
        for shot in timeline['shots']:
            if shot['start'] >= 55: continue
            names = shot.get('source_names', []) + shot.get('files', [])
            if (shot.get('studio_style') == 'terminal_pipeline'
                or re.search(r'(?:^|[/ _-])(?:cli|terminal)(?:[._/-]|$)', ' '.join(names), re.I)):
                violations.append(dict(shot=shot['id'],reason='terminal_source'))
        for at, lines in frames:
            if at >= 55: continue
            for line in lines:
                if re.search(r'^(?:[\w.-]+@[\w.-]+.*?[%$#>]\s*|(?:[$%>]\s*)?(?:npm (?:install|run)|npx\s+|pip3? install|git (?:clone|checkout)|python3?\s+\S+\.py)|last login:)',line['text'].strip(),re.I):
                    violations.append(dict(at=at,reason='terminal_command_in_frame'))
                    break
    return dict(ok=not violations,violations=violations)


def presenter_shortcut_line(shot, line):
    """Ignore only the small, measured keyboard legend in a captured deck's corner."""
    hint = shot.get('presenter_shortcuts') or {}
    if not re.search(r'ESC.{0,5}索引', hint.get('text',''), re.I) or '翻页' not in hint.get('text',''):
        return False
    box = hint.get('box',[])
    if len(box)!=4: return False
    left,top,width,height = box
    x,y,w,h = line['box']
    return (left>=1450 and top>=990 and 0<width<=350 and 0<height<=28
            and left-8<=x and x+w<=left+width+8 and top-5<=y and y+h<=top+height+5)


def subtitle_safe_zone_gate(timeline, measured, frames, project=None):
    violations = []
    for shot in timeline['shots']:
        key = shot['id']
        if project is not None and shot.get('custom_layout') and shot.get('files'):
            # Read the underlying image before captions can obscure its text.
            files = [f for f in shot['files'] if Path(f).suffix.lower() in VIDEO_EXTENSIONS]
            for file in files[:1]:
                for phase in (.12,.50,.88):
                    pos = shot.get('media_start',0.) + phase*shot_span(shot)
                    try:
                        rows = overlay_ocr(Path(project)/file,pos,(0,0,1920,1080),OCR)
                    except (ValueError,OSError,subprocess.SubprocessError) as exc:
                        violations.append(dict(shot=key,reason=str(exc)))
                        break
                    for row in rows:
                        x,y,w,h = row['box']
                        if len(normalized(row['text'])) >= 2 and y+h >= 860 and not presenter_shortcut_line(shot,row):
                            violations.append(dict(shot=key,phase=phase,text=row['text'],bottom=round(y+h)))
        for frame in measured.get(key,{}).get('frames', []):
            if frame.get('unsafeCoreText'):
                violations.append(dict(shot=key,phase=frame['phase'],text=frame['unsafeCoreText']))
                break
    for at, lines in frames:
        shot = next((s for s in timeline['shots'] if s['start']<=at<s['end']),None)
        if not shot: continue
        overlay_words = [normalized(o.get(k,'')) for o in shot.get('overlays',[]) for k in ('label','sublabel')]
        active_subs = [normalized(c['text']) for c in timeline.get('captions',[]) if c['start']-.04<=at<=c['end']+.04]
        for line in lines:
            word = normalized(line['text']);x,y,w,h = line['box']
            if len(word)<2 or y+h < 860 or presenter_shortcut_line(shot,line) or any(word in sub for sub in active_subs):
                continue
            if shot.get('custom_layout') or any(word in o for o in overlay_words if o):
                violations.append(dict(shot=shot['id'],at=at,text=line['text'],bottom=round(y+h)))
    return dict(ok=not violations,violations=violations)


def precheck_narrative_gate(timeline, project, duration):
    import importlib.util
    episode_dir = Path(project).resolve().parent
    script_path = episode_dir / 'script.md'
    has_packaging = (episode_dir / 'packaging.json').is_file() or (episode_dir / 'packaging.md').is_file()
    required = bool(script_path.is_file() and (timeline.get('version') == 'v15.0' or has_packaging))
    if not required:
        return dict(ok=True, required=False, violations=[])
    spec = importlib.util.spec_from_file_location('precheck_episode', Path(__file__).with_name('precheck-episode.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    violations = []
    for stg in ('packaging', 'script'):
        try:
            rep = mod.run(episode_dir, stage=stg, require_thumbnails=False)
            for err in rep['stages'][stg]['errors']:
                violations.append(dict(stage=stg, code=err['code'], message=err['message']))
        except Exception as exc:
            violations.append(dict(stage=stg, code='precheck_error', message=str(exc)))
    return dict(ok=not violations, required=True, violations=violations)


def recipe_monotony_and_workbench_gate(timeline, duration):
    from collections import Counter
    required = bool((timeline.get('version') == 'v15.0' or 'semantic_alignment' in timeline)
                    and timeline.get('episode_kind') == 'tool_tutorial' and duration >= 90)
    if not required:
        return dict(ok=True, required=False, violations=[])
    shots = timeline.get('shots') or []
    counts = Counter()
    asterisk_bento = []
    for shot in shots:
        spec = shot.get('spatial_spec') or shot.get('onetake_spec') or {}
        rec = spec.get('recipe') or shot.get('recipe')
        if rec:
            counts[rec] += 1
        if rec == 'logo_bento_stage' and isinstance(shot.get('spatial_spec'), dict):
            mods = (shot['spatial_spec'].get('data') or {}).get('modules') or []
            has_real_logo = any(isinstance(it, dict) and it.get('logo') for m in mods for it in (m.get('items') or []))
            if not has_real_logo:
                asterisk_bento.append(shot['id'])
    violations = []
    cap = max(3, int(len(shots) * 0.06))
    for diagram in ('logo_bento_stage', 'step_tree_focus', 'roadmap_thread_camera', 'handdrawn_sketch_stage'):
        if counts[diagram] > cap:
            violations.append(dict(reason='overused_diagram_recipe', recipe=diagram, count=counts[diagram], max_allowed=cap))
    if len(asterisk_bento) > 1:
        violations.append(dict(reason='logo_bento_missing_real_logos', shots=asterisk_bento,
                               hint='无真实 SVG/PNG 标志时严禁反复套用默认星号白框 logo_bento_stage，请提供真实 logo 或改用带真画面的 progressive_sim_cards / perspective_video_fan'))
    if duration >= 120 and counts['prompt_iter_workbench'] < 2:
        violations.append(dict(reason='insufficient_prompt_iter_workbench', count=counts['prompt_iter_workbench'], minimum=2,
                               hint='实操长教程至少须有 2 个镜头真实使用 prompt_iter_workbench 展示提示词胶囊与前后画面对比'))
    return dict(ok=not violations, required=True, recipe_counts=dict(counts), violations=violations)


def v9_gates(timeline, project, rendered, duration, errors, *, v10=False):
    shots = timeline['shots']
    richness = visual_richness_gate(timeline,project,rendered)
    samples = stage_visuals(timeline,project,rendered)
    result = dict(pacing_and_rhythm_gate=pacing_and_rhythm_gate(shots,duration),
                  framing_and_variety_gate=framing_and_variety_gate(shots,duration),
                  visual_richness_gate=richness,
                  dual_engine_craft_gate=dual_engine_craft_gate(shots,project,v10=v10),
                  cross_stage_asset_dedup_gate=cross_stage_asset_dedup_gate(timeline,project,rendered,samples=samples),
                  external_showcase_diversity_gate=external_showcase_diversity_gate(timeline,project,rendered,duration,samples=samples),
                  tutorial_workflow_gate=tutorial_workflow_gate(dict(timeline,capture_scores=richness['checked'])))
    if v10:
        from audit_spatial import capture_stage_backgrounds, spatial_frame_gates, spatial_measurements, subpage_repeats, three_mode_symphony_gate
        result['precheck_narrative_gate'] = precheck_narrative_gate(timeline, project, duration)
        result['recipe_monotony_and_workbench_gate'] = recipe_monotony_and_workbench_gate(timeline, duration)
        editorial = any('case_tag' in shot or shot.get('stage_look') in {'swiss_paper', 'cinema_black'}
                        or any(o.get('kind') == 'editorial_punch' for o in shot.get('overlays', []))
                        for shot in shots)
        if 'semantic_alignment' in timeline or editorial:
            result['case_monotony_gate'] = case_monotony_gate(shots, duration)
            result['semantic_match_ledger'] = semantic_match_ledger(timeline)
        result['quadrant_overlay_gate'] = quadrant_overlay_gate(shots,project)
        measurements = spatial_measurements(shots,project)
        result['enumerated_count_gate'] = enumerated_count_gate(shots,measurements)
        result['sfx_diversity_and_sync_gate'] = sfx_diversity_and_sync_gate(timeline,duration)
        result['chapter_voice_completeness_gate'] = chapter_voice_completeness_gate(timeline,project,duration)
        result['subtitle_safe_zone_gate'] = subtitle_safe_zone_gate(timeline,measurements,[],project)
        result.update(spatial_frame_gates(shots,duration,measurements,
                                          result['tutorial_workflow_gate']['required']))
        stage_gate = result['unified_cyber_stage_and_accent_gate']
        if stage_gate['required']:
            capture_stage_backgrounds(shots,project,rendered,stage_gate)
        result['three_mode_symphony_gate'] = three_mode_symphony_gate(
            timeline, duration, result['dual_engine_craft_gate']['verified_modes'],
            tutorial=result['tutorial_workflow_gate']['required'])
        dedup = result['cross_stage_asset_dedup_gate']
        dedup['violations'].extend(subpage_repeats(shots,project,rendered))
        dedup['ok'] = not dedup['violations']
    errors.extend(name for name,gate in result.items() if not gate['ok'])
    return result
