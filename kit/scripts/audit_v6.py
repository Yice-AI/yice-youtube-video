"""审计字幕锚点、科技实证覆盖、工作台边距、配音来源与像素遮挡。"""
import hashlib
import json
from pathlib import Path
import re
import subprocess


BANNED = re.compile(r'(codex-live|editor-timeline|retake-(sources|plain-review|benchmark|editing|cut-speed|duration|change|workflow|compare|pitch|finalcut|conclusion|ruler|library|tiers))\.mp4$', re.I)
GRAPHICS = {'studio_ui', 'explainer_graphic'}


def rhythm(shots, duration):
    halves = [[s for s in shots if (s['start'] < duration/2) == first] for first in (True, False)]
    counts = [sum(s['kind'] in GRAPHICS for s in half) for half in halves]
    fractions = [count/max(1,len(half)) for count,half in zip(counts, halves)]
    return counts, abs(fractions[0]-fractions[1])


def timeline_gates(data, project, duration, errors):
    shots = data['shots']
    timing_path = project / 'voice/voice-timing.json'
    cues = {}
    if not timing_path.is_file():
        errors.append('缺少正式配音的逐句时间表')
    else:
        offsets = data.get('chapter_voice_offsets', {})
        for cue in json.loads(timing_path.read_text()):
            chapter = cue['id'].split('-', 1)[0]
            cues[cue['id']] = float(cue['firstCharTime']) + float(offsets.get(chapter, 0))
    bad_sources, bad_sync, bad_margin = [], [], []
    real_seconds = max_offset = 0.
    for shot in shots:
        kind = shot['kind']
        files = shot.get('files', [])
        bad_sources.extend(f for f in files if BANNED.search(Path(f).name))
        if kind != 'chapter_break' and not (shot['start']==0 and shot.get('opening_prelude')):
            cue = cues.get(shot.get('anchor_cue_id'))
            offset = None if cue is None else abs(shot['start']-cue)
            if offset is not None:
                max_offset = max(max_offset, offset)
            if offset is None or offset>.220001 or abs(shot.get('anchor_cue_start',-1)-cue)>.001:
                bad_sync.append(shot['id'])
        if kind in GRAPHICS and (shot.get('outer_scale', 1)>1.02 or shot.get('title_padding',64)<64):
            bad_margin.append(shot['id'])
        if (kind in {'real_video','web_cam','studio_ui','stock_broll'} and files and all((project/f).is_file() for f in files)) or (shot.get('grammar')=='y2_vox' and shot.get('document_source') and (project/shot['document_source']).is_file()):
            real_seconds += shot['end']-shot['start']
    counts, difference = rhythm(shots, duration)
    ratio=real_seconds/duration
    for condition,message in [(bad_sources,'包含禁用源素材'),(bad_sync,'句首次序或时间偏差超限'),(bad_margin,'工程框超出安全边距'),(ratio<.70,'真实科技素材时长低于70%'),(min(counts)<6 or difference>.15,'前后半程动效或工程台分布不均')]:
        if condition: errors.append(message)
    return dict(real_ratio=ratio, av_sync_lock_gate=dict(max_deviation=max_offset, violations=bad_sync),
                viewport_safe_margin_gate=dict(violations=bad_margin), banned_sources=bad_sources,
                high_real_tech_ratio_gate=dict(ratio=ratio,half_counts=counts,share_difference=difference))


def rectangles(rgb):
    import numpy as np
    from scipy import ndimage
    # 四倍下采样。筛选完整矩形，避免把纯底文档的文字间留白视为遮挡。
    gray=rgb.mean(axis=2)
    neutral=(np.ptp(rgb.astype('int16'),axis=2)<4) & (gray>115)
    flat=ndimage.maximum_filter(gray,3)-ndimage.minimum_filter(gray,3)<2
    labels,count=ndimage.label(neutral & flat)
    found=[]
    for index,area in enumerate(ndimage.find_objects(labels),1):
        if area is None: continue
        y,x=area
        w,h=x.stop-x.start,y.stop-y.start
        if min(w,h)<=65 or min(y.start,x.start)<3 or x.stop>gray.shape[1]-3 or y.stop>gray.shape[0]-3: continue
        if (labels[area]==index).mean()<.96 or gray[area].std()>=1.2: continue
        border=np.concatenate([gray[y.start-3:y.start,x].ravel(),gray[y.stop:y.stop+3,x].ravel(),gray[y,x.start-3:x.start].ravel(),gray[y,x.stop:x.stop+3].ravel()])
        if border.std()>12 and np.mean(np.abs(border-gray[area].mean())>8)>.35:
            found.append([x.start*4,y.start*4,w*4,h*4])
    return found


def masks(video, data):
    import numpy as np
    step=1.5
    cmd=['ffmpeg','-v','error','-i',str(video),'-vf','fps=2/3:start_time=0,scale=480:270:flags=area','-pix_fmt','rgb24','-f','rawvideo','-']
    hits=[]
    with subprocess.Popen(cmd,stdout=subprocess.PIPE) as proc:
        n=0
        while raw:=proc.stdout.read(480*270*3):
            frame=np.frombuffer(raw,'uint8').reshape(270,480,3)
            at=n*step
            n+=1
            shot=next((s for s in data['shots'] if s['start']<=at<s['end']),{})
            if shot.get('kind') not in {'web_cam','real_video','screenshot'}:continue
            for rect in rectangles(frame): hits.append(dict(at=at,shot=shot.get('id'),rect=rect))
        if proc.wait():raise ValueError('遮挡检查的视频解码失败')
    return hits


def voice_continuity(project):
    voice=project/'voice'
    manifest=json.loads((voice/'voice-manifest.json').read_text())
    failures=[]
    if manifest.get('backend') not in {'modal','kaggle'} or manifest.get('speed')!=1.0: failures.append('配音来源或原速不符')
    chapters=manifest.get('chapters',[])
    if not chapters or manifest.get('stage') != 'master':
        failures.append('缺少正式配音批次')
    script_path = voice / 'analysis/script-manifest.json'
    if script_path.is_file():
        expected = {c['id'] for c in json.loads(script_path.read_text())['chapters']}
        if expected != {c['id'] for c in chapters}:
            failures.append('配音清单与本次正式稿章号不一致')
    for chapter in chapters:
        key = chapter['id']
        check = voice / f'voice-check-{key}.json'
        audio = voice / chapter.get('audio', '')
        acoustic = json.loads(check.read_text()) if check.is_file() else {}
        if acoustic.get('ok') is not True:
            failures.append(f'{key} 未通过声学检查')
        asr_report = voice / 'analysis' / f'asr-audit-{key}.json'
        asr = json.loads(asr_report.read_text()) if asr_report.is_file() else {}
        if asr.get('ok') is not True:
            failures.append(f'{key} 未通过最终音轨转录检查')
        original = chapter.get('backend')
        repair = chapter.get('repair_backend', original)
        if original not in {'modal', 'kaggle'} or repair not in {'modal', 'kaggle'}:
            failures.append(f'{key} 缺少云端原音或补录后端')
        if manifest.get('backend') not in {original, repair} or chapter.get('repair_unit') not in {'semantic_chunk', 'whole_sentence'}:
            failures.append(f'{key} 缺少本次云端批次的整句或整组生成记录')
        if chapter.get('surgical') or 'surgical' in str(audio) or not audio.is_file():
            failures.append(f'{key} 音频缺失或使用了逐句拼接')
        else:
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            if chapter.get('sha256') != digest:
                failures.append(f'{key} 音频与正式清单的摘要不一致')
            if acoustic.get('measurement', {}).get('sha256') != digest or asr.get('sha256') != digest:
                failures.append(f'{key} 声学或转录报告与最终音轨的摘要不一致')
    return dict(backend=manifest.get('backend'), chapters=len(chapters), violations=failures)
