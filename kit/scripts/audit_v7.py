"""Audit the relationship between narration, shot subjects and actual masters."""
from collections import Counter
import hashlib
import json
from math import isfinite
from pathlib import Path
import re
import subprocess
import unicodedata


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
}
ABSTRACT = ('规则', '清单', '优先级', '总结', '原则', '三句话', '步骤', 'rules', 'checklist', 'summary', 'priority')
BINDINGS = {'exact_tool_capture', 'conceptual_explainer', 'physical_prop', 'callback_cut'}
MOTION = {'explainer_clip', 'title_sequence', 'cold_open_ab', 'triptych_cards'}
REAL = {'callout_rig', 'cold_open_ab', 'fullbleed_rig', 'web_cam', 'real_video', 'stock_broll'}
SFX = {'tick', 'whoosh', 'pop', 'marker', 'stamp', 'riser', 'slap'}


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


def entities(value):
    text = unicodedata.normalize('NFKC', value).casefold()
    result = set()
    for tool, aliases in TOOLS.items():
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


def semantic_binding_gate(shots):
    violations = []
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
        mentioned = entities(spoken)
        labeled = entities(' '.join(tags))
        shown = entities(visual)
        explicit = shot.get('spoken_entity')
        if isinstance(explicit,str) and explicit.strip():
            named = entities(explicit)
            if not named and not (normalized(explicit) in {normalized(tag) for tag in tags}
                                  and normalized(explicit) in normalized(visual)):
                violations.append({'shot':shot.get('id'),'reason':'声明的工具实体未同时出现在主体和素材标签'})
                continue
            mentioned |= named
        if mode in REAL and mentioned and not mentioned <= (shown & labeled):
            violations.append({'shot':shot.get('id'),'reason':'点名工具与实际画面实体不一致',
                               'spoken_entities':sorted(mentioned),'visual_entities':sorted(shown & labeled)})
            continue
        is_abstract = shot.get('topic_kind') in {'rule','checklist','summary','principle'} or any(
            text in spoken.casefold() for text in ABSTRACT)
        if is_abstract and mode in REAL and not (binding=='exact_tool_capture' and mentioned
                and re.search(r'打开|点击|在.+里|open\s|click\s',spoken,re.I)):
            overlays = shot.get('overlays', [])
            labels = ' '.join(' '.join([str(overlay.get('label','')), *map(str,overlay.get('items',[]))])
                              for overlay in overlays)
            matches_topic = any(text in labels.casefold() for text in ABSTRACT) or any(
                len(normalized(tag))>=2 and normalized(tag) in normalized(labels)
                and normalized(tag) in normalized(topic) for tag in tags)
            if (mode not in {'callout_rig','cold_open_ab'} or not shot.get('has_motion_overlay')
                    or binding not in {'callback_cut','conceptual_explainer'} or not matches_topic):
                violations.append({'shot':shot.get('id'),'reason':'抽象规则或清单需要语义匹配的动效或总结贴图'})
    return {'ok':not violations,'violations':violations}


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
        has_overlay = mode in {'callout_rig','studio_ui'} and shot.get('has_motion_overlay') and shot.get('overlays')
        moving[half] += int(mode in MOTION or bool(has_overlay))
        if mode in REAL and mode != 'cold_open_ab' and not has_overlay:
            bare = (bare if start-previous<=.001 else 0.)+end-start
            longest = max(longest,bare)
        else:
            bare = 0.
        previous = end
    shares = [motion/max(1,n) for motion,n in zip(moving,counts)]
    return {'ok':min(shares)>=.35 and longest<=14.+1e-6,'half_motion_shares':shares,
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


def timeline_gates(timeline, project, duration):
    shots = timeline['shots']
    project = Path(project)
    cues = {str(row['id']):float(row['firstCharTime']) for row in timeline.get('cues',[])}
    previous = real_seconds = deviation = 0.
    invalid, unaligned, missing = [],[],[]
    seen_ids, digest_cache = set(),{}
    card_durations, invalid_cards = {}, []
    source_reuse = Counter()
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
        if mode=='triptych_cards':
            cards = shot.get('cards',[])
            if (not isinstance(cards,list) or not 2<=len(cards)<=4
                    or any(not isinstance(card,dict) or not isinstance(card.get('source'),str) for card in cards)
                    or [card['source'] for card in cards]!=shot.get('files')):
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
                        if path.suffix.lower()=='.mp4':
                            if path not in card_durations:
                                card_durations[path] = probe_video(path)
                            if card_durations[path]+1e-5<media_start+b-a-reveal_at+.2:
                                raise ValueError('卡片视频缺少余量')
                        elif path.suffix.lower() not in {'.png','.jpg','.jpeg'}:
                            raise ValueError('卡片素材格式无效')
                    except (TypeError,ValueError,KeyError,OSError,subprocess.CalledProcessError):
                        invalid_cards.append(key)
                        break
        if mode in REAL:
            real_seconds += b-a
            files = [project/f for f in shot.get('files',[]) if Path(f).suffix.lower() in {'.mp4','.m4v','.mov','.webm'}]
            if not files:
                missing.append(key)
            for path in files:
                if not path.is_file():
                    missing.append(key)
                    continue
                if path not in digest_cache:
                    with path.open('rb') as f:
                        digest_cache[path] = hashlib.file_digest(f,'sha256').hexdigest()
                source_reuse[digest_cache[path]] += 1
    if abs(previous-duration)>.045:
        invalid.append('timeline_end')
    ratio = real_seconds/duration if duration else 0.
    ratio_ok = .45<=ratio<=.72
    repeats = {digest:count for digest,count in source_reuse.items() if count>3}
    return {'ok':not (invalid or unaligned or repeats or missing or invalid_cards) and ratio_ok,
            'real_ratio':ratio,'ratio_ok':ratio_ok,'invalid_shots':invalid,'missing_real_media':missing,
            'invalid_triptych_media':invalid_cards,
            'max_anchor_deviation':deviation,'unaligned':unaligned,'overused_sources':repeats}


def video_gates(timeline, project, rendered, duration, errors):
    gates = {
        'v7_timeline_gate': timeline_gates(timeline,project,duration),
        'semantic_binding_gate': semantic_binding_gate(timeline['shots']),
        'opener_bgm_and_sfx_gate': opener_bgm_and_sfx_gate(Path(rendered).parent/'bed-only.wav',timeline.get('sound_marks',[]),duration),
        'first_half_motion_density_gate': first_half_motion_density_gate(timeline['shots'],duration),
        'breath_integrity_gate': breath_integrity_gate(project,timeline),
    }
    for name,report in gates.items():
        if not report['ok']:
            errors.append(f'v7 {name} 未通过')
    return {'real_ratio':gates['v7_timeline_gate']['real_ratio'],**gates}
