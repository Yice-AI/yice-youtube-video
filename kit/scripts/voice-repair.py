#!/usr/bin/env python3
"""Repair whole flagged sentences, retain candidates/clips, and rescan the chapter."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import librosa
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import voice as v

quality = v.load_voice_tool('voice-quality')
check_tool = v.load_voice_tool('voice-check')
post = v.load_voice_tool('voice-post')


def cuts_for(audio, alignment, flagged=None, *, natural=False):
    measurement = check_tool.measure(audio, alignment)
    sentences = check_tool.sentence_ranges(alignment['text'])
    groups = [[row for row in alignment['mapped'] if lo <= row['charStart'] < hi] for lo, hi, _ in sentences]
    if any(not group for group in groups):
        raise ValueError('修复句子缺少完整字时间')
    waveform, rate = sf.read(audio)
    intervals = (check_tool.runs(np.asarray(measurement['db']) < -55.) if natural
                 else measurement.get('absolute_silence_45db', []))
    quiet_points = []
    for left, right in zip(groups, groups[1:]):
        center = (left[-1]['e'] + right[0]['s']) / 2
        if natural:
            limit = right[0]['s'] - .14
            quiet = [(max(a,left[-1]['e']), min(b,limit))
                     for a,b in intervals if min(b,limit)-max(a,left[-1]['e']) >= .10]
        else:
            quiet = [(a, b) for a, b in intervals if b-a >= .04 and a >= left[-1]['s']
                     and b <= right[0]['e'] + .05 and abs((a+b)/2-center) <= .4]
        if quiet:
            a, b = min(quiet, key=lambda pair: abs(sum(pair)/2-center))
            margin = .05 if natural else .015
            lo, hi = round((a + margin) * rate), round((b - margin) * rate)
            window = waveform[lo:hi]
            zero = np.flatnonzero(window[:-1] * window[1:] <= 0) + lo
            if len(zero):
                point = zero[np.argmin(abs(zero - (a + b) * rate / 2))]
                quiet_points.append((point / rate, True))
                continue
        quiet_points.append((center, False))
    if flagged is None:
        if any(not is_q for _, is_q in quiet_points):
            raise ValueError('句间没有已验证的自然低能量边界，拒绝剪入发声部分')
        cuts = [0.] + [pt for pt, _ in quiet_points] + [sf.info(audio).duration]
    else:
        flagged_set = set(flagged)
        changed = not natural
        while changed:
            changed = False
            for idx, (_, is_q) in enumerate(quiet_points):
                if not is_q and ((idx in flagged_set) != (idx + 1 in flagged_set)):
                    flagged_set.add(idx)
                    flagged_set.add(idx + 1)
                    changed = True
        cuts = [0.] + [pt for pt, _ in quiet_points] + [sf.info(audio).duration]
    if not all(a < b for a, b in zip(cuts, cuts[1:])):
        raise ValueError('无效的整句边界')
    if flagged is None:
        return sentences, groups, cuts
    return sentences, groups, (cuts, sorted(flagged_set), [is_q for _, is_q in quiet_points])


def feature(samples, rate):
    samples = np.asarray(samples, dtype=float)
    coefficients = librosa.feature.mfcc(y=samples, sr=rate, n_mfcc=20).mean(axis=1)
    pitch = librosa.pyin(samples, fmin=60, fmax=450, sr=rate, frame_length=1024, hop_length=240)[0]
    pitch = pitch[np.isfinite(pitch)]
    return coefficients, float(np.median(pitch)) if len(pitch) else None


def continuity(before, after, rate):
    first, old_pitch = feature(before, rate)
    second, new_pitch = feature(after, rate)
    denominator = np.linalg.norm(first) * np.linalg.norm(second)
    cosine = float(np.dot(first, second) / denominator) if denominator else 0.
    shift = 12 * math.log2(new_pitch / old_pitch) if old_pitch and new_pitch else None
    return dict(mfcc_mean_cosine=cosine, pitch_shift_semitones=shift,
                ok=cosine >= .94 and shift is not None and abs(shift) <= 3.5)


def flagged_sentences(text, check, audit, allowed_kinds=None):
    ranges = check_tool.sentence_ranges(text)
    flagged = {row['sentence'] for row in check['alerts']
               if allowed_kinds is None or row['kind'] in allowed_kinds}
    positions = [index for index, char in enumerate(text) if char.isalnum()]
    for difference in (audit['differences'] if not audit['ok'] else []):
        at = positions[min(difference['expected_start'], len(positions)-1)]
        flagged.update(index for index, (a, b, _) in enumerate(ranges) if a <= at < b)
    if any(index < 0 or index >= len(ranges) for index in flagged):
        raise ValueError('告警无法对应完整句子')
    return sorted(flagged)


def splice(samples, rate, alignment, cuts, groups, replacements, *, natural=False):
    output, mapped, splices = np.array([], dtype=float), [], []
    previous_replaced = False
    covered = {idx for take in replacements.values() for idx in take.get('span', [take['sentence']])[1:]}
    for index, group in enumerate(groups):
        if index in covered:
            continue
        replaced = index in replacements
        end_idx = replacements[index].get('span', [index])[-1] + 1 if replaced else index + 1
        old = samples[round(cuts[index]*rate):round(cuts[end_idx]*rate)].copy()
        if replaced:
            take = replacements[index]
            chunk, candidate_rate = sf.read(take['processed'])
            if candidate_rate != rate or chunk.ndim != 1:
                raise ValueError('整句替换必须同采样率、单声道')
            rms = lambda y: float(np.sqrt(np.mean(y[np.abs(y) > .005]**2))) if np.any(np.abs(y) > .005) else 0.
            gain = rms(old) / max(rms(chunk), 1e-10)
            peak = np.max(np.abs(chunk))
            if peak > 0:
                gain = min(gain, 10 ** (-1 / 20) / peak)
            chunk = chunk * gain
            local = copy.deepcopy(take['alignment']['mapped'])
            char_offset = take['char_offset']
            if natural:
                # Keep the entire candidate, including the breath before its first word.
                # Give the overlap a separate quiet landing window on each edge.
                fade = round(.05*rate)
                lead = fade + max(0, round((.14-local[0]['s'])*rate))
                chunk = np.concatenate((v.room_tone(chunk, rate, lead),
                                        chunk, v.room_tone(chunk, rate, fade)))
                for row in local:
                    row['s'] += lead/rate
                    row['e'] += lead/rate
        else:
            chunk = old
            char_offset = 0
            local = [{**row, 's': max(0, row['s']-cuts[index]),
                      'e': min(len(chunk)/rate, max(0, row['e']-cuts[index]))} for row in group]
        fade = min(round((.05 if natural else .015)*rate), len(output), len(chunk)) if index and (replaced or previous_replaced) else 0
        start = (len(output)-fade)/rate
        if fade:
            weights = (1 - np.cos(np.linspace(0, np.pi, fade))) / 2
            output = np.r_[output[:-fade], output[-fade:]*(1-weights)+chunk[:fade]*weights, chunk[fade:]]
            splices.append(dict(sentence=index, at=start, fade_ms=1000*fade/rate))
        else:
            output = np.r_[output, chunk]
        mapped.extend(dict(charStart=char_offset+row['charStart'], charEnd=char_offset+row['charEnd'],
                           s=start+row['s'], e=start+row['e']) for row in local)
        previous_replaced = replaced
    if any(left['e'] > right['s'] + 1/rate for left, right in zip(mapped, mapped[1:])):
        raise ValueError('淡化接缝侵入字时间，拒绝拼接')
    return output, dict(text=alignment['text'], mapped=mapped, matched_ratio=1.,
                        planned_pauses=alignment.get('planned_pauses', {})), splices


def final_scan(chapter, audio, alignment, folder, transcribe, exceptions, threshold, *, silence=0,
               offset=0, anchors=(), lufs=-16., profile='legacy'):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'analysis').mkdir(exist_ok=True)
    destination = folder/'analysis/semantic.wav'
    calibrate = post.preserve_breaths if profile == 'natural_v7' else post.regularize
    alignment, edits = calibrate(audio, alignment, destination, destination.with_suffix('.npz'))
    audio = destination
    normalized = folder/'analysis/normalized.wav'
    levels = post.normalize_lufs(audio, normalized, lufs)
    record, timing, scenes, captions, analysis = v.prepare_chapter(
        chapter, normalized, folder, {}, {}, silence, offset, anchors, aligned=alignment)
    final = folder/record['path']
    aligned = dict(text=chapter['text'], mapped=analysis['output_mapped'],
                   planned_pauses=alignment.get('planned_pauses', {}))
    transcript = transcribe(final)
    audit = quality.audit(chapter['text'], transcript, exceptions, threshold, auto_homophone=profile=='natural_v7')
    if transcript.get('segments'):
        mapped, ratio, clamps = v.align_with_audit(chapter['text'], transcript, sf.info(final).duration, audit)
        aligned.update(mapped=mapped, matched_ratio=ratio, monotonic_clamps=clamps)
        record, timing, scenes, captions, analysis = v.prepare_chapter(
            chapter, final, folder, {}, audit['normalizations'], 0, offset, anchors, aligned=aligned)
        audit.update(alignment_ratio=ratio, ok=audit['ok'] and ratio >= threshold)
    audit['sha256'] = hashlib.sha256(final.read_bytes()).hexdigest()
    checked = check_tool.check_chapter(final, aligned, chapter=chapter['id'], cache=folder/'analysis/final.npz', profile=profile)
    checked.update(prosody_ok=checked['ok'], asr=audit, ok=checked['ok'] and audit['ok'])
    record.update(prosody_alert_count=len(checked['alerts']), asr_matched_ratio=audit['ratio'],
                  asr_passed=audit['ok'], loudness=levels, postprocessing=True)
    for name, data in [('final-transcript', transcript), ('asr-audit', audit), ('voice-check', checked),
                       ('final-alignment', aligned), ('semantic-edits', edits)]:
        v.write_json(folder/'analysis'/f'{name}-{chapter["id"]}.json', data)
    return dict(audio=str(final), alignment=aligned, asr=audit, check=checked, record=record,
                timing=timing, scenes=scenes, captions=captions, analysis=analysis, folder=str(folder))


def repair(chapter, current, output, generate, transcribe, *, exceptions=None, threshold=.97,
           max_rounds=3, candidates_per_sentence=3, lufs=-16., anchors=(), offset=0, post_options=None, allowed_kinds=None, profile='legacy'):
    if not 0 <= max_rounds <= 3 or candidates_per_sentence < 2:
        raise ValueError('最多修复3轮，每句至少2个seed')
    output = Path(output)
    history = []
    for round_number in range(1, max_rounds+1):
        if current['check']['ok'] and current['asr']['ok']:
            break
        folder = output/f'round-{round_number}'
        folder.mkdir(parents=True, exist_ok=True)
        flagged = flagged_sentences(chapter['text'], current['check'], current['asr'], allowed_kinds)
        if not flagged:
            history.append(dict(round=round_number, error='内容/对齐不通过，但无法定位安全整句'))
            break
        sentences, groups, (cuts, expanded_flagged, quiet_flags) = cuts_for(current['audio'], current['alignment'], flagged=flagged, natural=profile=='natural_v7')
        flagged = expanded_flagged
        if profile == 'natural_v7':
            flagged = [idx for idx in flagged
                       if (idx == 0 or quiet_flags[idx-1])
                       and (idx == len(groups)-1 or quiet_flags[idx])]
            if not flagged:
                history.append(dict(round=round_number, error='有实质告警，但无法定位保护吸气的安全整句剪点'))
                break
        # Merge adjacent flagged sentences ONLY when the boundary between them lacks verified natural quiet
        spans = []
        for idx in flagged:
            if spans and idx == spans[-1][-1] + 1 and not quiet_flags[idx - 1]:
                spans[-1].append(idx)
            else:
                spans.append([idx])
        samples, rate = sf.read(current['audio'])
        jobs = []
        for span in spans:
            lo = sentences[span[0]][0]
            hi = sentences[span[-1]][1]
            span_text = chapter['text'][lo:hi]
            leading = len(span_text) - len(span_text.lstrip())
            chapter_number = int(re.match(r'\d+', chapter['id'])[0]) if re.match(r'\d+', chapter['id']) else 0
            for candidate in range(candidates_per_sentence):
                seed = 200000 + round_number*10000 + chapter_number*300 + span[0]*candidates_per_sentence + candidate
                jobs.append(dict(text=span_text.strip(), seed=seed, sentence=span[0], span=span, char_offset=lo+leading,
                                 path=str(folder/f'sentence-{span[0]:02}-seed-{seed}.wav')))
        generate(jobs)
        selections, screened = {}, []
        for job in jobs:
            raw = Path(job['path'])
            candidate = {**job, 'ok': False}
            try:
                transcript = transcribe(raw)
                audit = quality.audit(job['text'], transcript, exceptions, threshold, auto_homophone=profile=='natural_v7')
                v.write_json(raw.with_suffix('.transcript.json'), transcript)
                candidate['asr'] = audit
                if not audit['ok']:
                    screened.append(candidate)
                    continue
                mapped, ratio, clamps = v.align_with_audit(job['text'], transcript, sf.info(raw).duration, audit)
                if ratio < threshold:
                    candidate['alignment_ratio'] = ratio
                    screened.append(candidate)
                    continue
                aligned = dict(text=job['text'], mapped=mapped, matched_ratio=ratio, monotonic_clamps=clamps)
                processed = raw.with_suffix('.post.wav')
                if profile == 'natural_v7':
                    aligned, _ = post.preserve_breaths(raw, aligned, processed, raw.with_suffix('.pitch.npz'))
                else:
                    if (post_options or {}).get('speed', 1.) == 1.:
                        aligned, _ = post.regularize(raw, aligned, processed, raw.with_suffix('.pitch.npz'), fade_ms=15)
                    else:
                        aligned = post.postprocess(raw, aligned, processed, **post_options)
                    for attempt in range(2):
                        semantic = raw.with_suffix(f'.semantic-{attempt}.wav')
                        aligned, changes = post.regularize(processed, aligned, semantic, semantic.with_suffix('.npz'))
                        y, sr = sf.read(semantic)
                        sf.write(processed, y, sr, subtype='PCM_24')
                        if not changes:
                            break
                new, new_rate = sf.read(processed)
                if new_rate != rate:
                    raise ValueError('替换句采样率不同')
                span_end = job.get('span', [job['sentence']])[-1] + 1
                old = samples[round(cuts[job['sentence']]*rate):round(cuts[span_end]*rate)]
                match = continuity(old, new, rate)
                checked = check_tool.check_chapter(processed, aligned, cache=raw.with_suffix('.check.npz'), profile=profile)
                candidate.update(processed=str(processed), alignment=aligned, check=checked,
                                 continuity=match, ok=checked['ok'] and match['ok'])
                if candidate['ok']:
                    prior = selections.get(job['sentence'])
                    if prior is None or abs(match['pitch_shift_semitones']) < abs(prior['continuity']['pitch_shift_semitones']):
                        selections[job['sentence']] = candidate
            except (ValueError, OSError, RuntimeError) as exc:
                candidate['error'] = str(exc)
            screened.append(candidate)
        v.write_json(folder/'candidates.json', screened)
        if not selections:
            history.append(dict(round=round_number, flagged=flagged, selected=[], ok=False))
            continue
        assembled, aligned, splices = splice(samples, rate, current['alignment'], cuts, groups, selections, natural=profile=='natural_v7')
        source = folder/'spliced.wav'
        sf.write(source, assembled, rate, subtype='PCM_24')
        updated = final_scan(chapter, source, aligned, folder/'final', transcribe, exceptions, threshold,
                             anchors=anchors, offset=offset, lufs=lufs, profile=profile)
        clips = folder/'clips'
        clips.mkdir()
        for index, take in selections.items():
            span_last = take.get('span', [index])[-1]
            old_center = (groups[index][0]['s']+groups[span_last][-1]['e'])/2
            new_rows = [row for row in updated['alignment']['mapped'] if sentences[index][0] <= row['charStart'] < sentences[span_last][1]]
            new_center = (new_rows[0]['s']+new_rows[-1]['e'])/2
            after, _ = sf.read(updated['audio'])
            for label, waveform, center in [('before', samples, old_center), ('after', after, new_center)]:
                start = max(0, min(len(waveform)/rate-2, center-.75))
                sf.write(clips/f'sentence-{index:02}-{label}.wav', waveform[round(start*rate):round((start+2)*rate)], rate, subtype='PCM_24')
        history.append(dict(round=round_number, flagged=flagged, selected=[dict(sentence=index, seed=take['seed'],
                            continuity=take['continuity']) for index, take in selections.items()], splices=splices,
                            clips=str(clips), ok=updated['check']['ok']))
        current = {**updated, 'seed': current.get('seed', 0)}
    output.mkdir(parents=True, exist_ok=True)
    v.write_json(output/'repair-report.json', dict(ok=current['check']['ok'], rounds=history,
                                                  text_unchanged=current['alignment']['text'] == chapter['text']))
    current['repair_rounds'] = history
    return current


def screen_chapter(chapter, candidate, folder, transcribe, exceptions, threshold,
                   silence, offset, anchors, skip_post, post_options, profile='legacy'):
    out = Path(folder)/f'seed{candidate["seed"]}'
    (out/'analysis').mkdir(parents=True, exist_ok=True)
    transcript = transcribe(Path(candidate['path']))
    v.write_json(out/'analysis/raw-transcript.json', transcript)
    record, timing, scenes, captions, analysis, checked = v.finish_chapter(
        chapter, Path(candidate['path']), out, transcript, exceptions or {}, silence, offset, anchors,
        skip_post=skip_post, post_options=post_options, asr_threshold=threshold, profile=profile)
    audio = out/record['path']
    final_transcript = transcribe(audio)
    audit = quality.audit(chapter['text'], final_transcript, exceptions, threshold, auto_homophone=profile=='natural_v7')
    audit['sha256'] = hashlib.sha256(audio.read_bytes()).hexdigest()
    if final_transcript.get('segments'):
        mapped, ratio, clamps = v.align_with_audit(chapter['text'], final_transcript, sf.info(audio).duration, audit)
        aligned = dict(text=chapter['text'], mapped=mapped, matched_ratio=ratio, monotonic_clamps=clamps,
                       planned_pauses=chapter.get('planned_pauses', {}))
        final_record, timing, scenes, captions, analysis = v.prepare_chapter(
            chapter, audio, out, {}, audit['normalizations'], 0, offset, anchors, aligned=aligned)
        record.update(sha256=final_record['sha256'])
        checked = check_tool.check_chapter(audio, aligned, chapter=chapter['id'],
                                           cache=out/'analysis'/f"voice-check-{chapter['id']}.npz", profile=profile)
        checked['prosody_ok'] = checked['ok']
        audit['sha256'] = record['sha256']
    audit['alignment_ratio'] = analysis['matched_ratio']
    audit['ok'] = audit['ok'] and audit['alignment_ratio'] >= threshold
    checked.update(asr=audit, ok=checked['prosody_ok'] and audit['ok'])
    record.update(asr_matched_ratio=audit['ratio'], asr_passed=audit['ok'])
    v.write_json(out/'analysis/final-transcript.json', final_transcript)
    v.write_json(out/'analysis/final-asr-audit.json', audit)
    v.write_json(out/'analysis/final-check.json', checked)
    return dict(seed=candidate['seed'], audio=str(audio), alignment=dict(text=chapter['text'], mapped=analysis['output_mapped'],
                                                                          planned_pauses=chapter.get('planned_pauses', {})),
                         asr=audit, check=checked, record=record, timing=timing, scenes=scenes,
                         captions=captions, analysis=analysis, folder=str(out))


def process_chapter(chapter, candidates, folder, generate, transcribe, *, exceptions=None, threshold=.97,
                    silence=.2, offset=0, anchors=(), post_options=None, skip_post=False, max_rounds=3,
                    cloud_backend=None, brand=None, profile='legacy'):
    def screen(candidate):
        return screen_chapter(chapter, candidate, folder, transcribe, exceptions, threshold,
                              silence, offset, anchors, skip_post, post_options, profile=profile)
    screened = [screen(candidate) for candidate in candidates]
    chosen = min(screened, key=quality.rank)
    v.write_json(Path(folder)/'selection.json', dict(selected_seed=chosen['seed'], candidates=[
        dict(seed=x['seed'], asr_ok=x['asr']['ok'], ratio=x['asr']['ratio'], alerts=len(x['check']['alerts'])) for x in screened]))
    if cloud_backend and profile == 'legacy':
        source = next(Path(c["path"]) for c in candidates if c["seed"] == chosen["seed"])
        chunk_dir = source.with_suffix(".chunks")
        history = []
        if max_rounds and not chosen["check"]["ok"]:
            if not (chunk_dir / "chunks.json").is_file():
                raise ValueError("云端重抽需要原始句组音频和清单")
            manifest = json.loads((chunk_dir / "chunks.json").read_text())
            texts = manifest["texts"]
            paths = [chunk_dir / f"chunk-{i:03}.wav" for i in range(len(texts))]
            pauses = {int(k): val for k, val in manifest["pauses"].items()}
            sentences = check_tool.sentence_ranges(chapter["text"])
            compact = lambda text: "".join(text.split())
            lengths = np.cumsum([len(compact(t)) for t in texts])
            for attempt in range(1, max_rounds + 1):
                flagged = flagged_sentences(chapter["text"], chosen["check"], chosen["asr"])
                indexes = set()
                for n in flagged:
                    lo, hi, _ = sentences[n]
                    left = len(compact(chapter["text"][:lo]))
                    right = len(compact(chapter["text"][:hi]))
                    for k, end in enumerate(lengths):
                        if left < end and right > (lengths[k-1] if k else 0):
                            indexes.add(k)
                if not indexes:
                    break
                indexes = sorted(indexes)
                dest = Path(folder) / f"redraw-{attempt}"
                dest.mkdir()
                temps = (.65, .72, .78)
                temp = temps[(int(chosen["seed"]) + attempt) % len(temps)]
                resp = v._remote_batch([texts[k] for k in indexes], brand, cloud_backend, temp)
                redrawn = paths.copy()
                for k, wav in zip(indexes, resp):
                    redrawn[k] = dest / f"chunk-{k:03}.wav"
                    redrawn[k].write_bytes(wav)
                master = dest / "assembled.wav"
                v._concat_wavs(redrawn, master, pauses=pauses)
                candidate = screen(dict(seed=1000000+attempt, path=str(master)))
                better = quality.rank(candidate) < quality.rank(chosen)
                history.append(dict(round=attempt, chunks=indexes, temperature=temp, accepted=better))
                if better:
                    paths, chosen = redrawn, candidate
                if chosen["check"]["ok"]:
                    break
        chosen["repair_rounds"] = history
        chosen["record"].update(seed=chosen["seed"], backend=cloud_backend, repair_unit="semantic_chunk")
        return chosen
    final = repair(chapter, chosen, Path(folder)/'repair', generate, transcribe, exceptions=exceptions, threshold=threshold,
                   max_rounds=max_rounds, lufs=(post_options or {}).get('lufs', -16.), anchors=anchors,
                   offset=offset, post_options=post_options, profile=profile,
                   candidates_per_sentence=2 if profile=='natural_v7' else 3)
    if cloud_backend:
        final['record'].update(backend=cloud_backend, repair_unit='whole_sentence')
    final['record'].update(seed=chosen['seed'], generated_duration=chosen['record']['generated_duration'],
                           added_boundary_silence=chosen['record']['added_boundary_silence'])
    return final


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--alignment', type=Path, required=True)
    parser.add_argument('--text-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--chapter-manifest', type=Path)
    parser.add_argument('--chapter', default='00')
    parser.add_argument('--brand', default='yice')
    parser.add_argument('--profile', choices=('natural_v7', 'legacy'), default='natural_v7')
    parser.add_argument('--asr-threshold', type=float, default=.97)
    parser.add_argument('--normalizations', type=Path)
    parser.add_argument('--asr-model', default='mlx-community/whisper-large-v3-turbo')
    parser.add_argument('--asr-prompt', default='')
    parser.add_argument('--reuse-candidates', type=Path)
    parser.add_argument('--backend', choices=['auto', 'modal', 'kaggle', 'local'], default='auto')
    parser.add_argument('--candidates', type=int, default=3)
    parser.add_argument('--max-rounds', type=int, default=3)
    parser.add_argument('--lufs', type=float, default=-16.)
    args = parser.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('输出目录须为空，原片和以前的修复记录不能覆盖')
    args.output.mkdir(parents=True, exist_ok=True)
    alignment = check_tool.load_alignment(args.alignment, args.text_file, args.audio)
    text = alignment['text']
    chapter = dict(id='00', text=text, scenes=[dict(id='0-1', text=text)])
    if args.chapter_manifest:
        chapter = next(c for c in json.loads(args.chapter_manifest.read_text())['chapters'] if c['id'] == args.chapter)
        if chapter['text'] != text:
            raise ValueError('音轨对齐文本与章节原稿不符')
    exceptions = json.loads(args.normalizations.read_text()) if args.normalizations else {}
    transcribe = v.make_transcriber(args.asr_model, args.asr_prompt, args.output/'asr')
    if not 1 <= args.candidates <= 8:
        parser.error('候选数须为1–8')
    resolved_backend = v.resolve_backend('draft', args.backend, allow_slow_local=(args.backend == 'local'))
    generate = v.make_generator(args.brand, args.output/'generation', args.reuse_candidates,
                                resolved_backend, args.candidates)
    checked = check_tool.check_chapter(args.audio, alignment, profile=args.profile)
    audit = quality.audit(text, transcribe(args.audio), exceptions, args.asr_threshold, auto_homophone=args.profile=='natural_v7')
    checked['ok'] = checked['ok'] and audit['ok']
    current = dict(audio=str(args.audio), alignment=alignment, check=checked, asr=audit, seed=0)
    result = repair(chapter, current, args.output, generate, transcribe, exceptions=exceptions,
                    threshold=args.asr_threshold, max_rounds=args.max_rounds, lufs=args.lufs,
                    post_options={'speed': 1., 'fade_ms': 15.}, profile=args.profile,
                    candidates_per_sentence=2 if args.profile=='natural_v7' else 3,
                    allowed_kinds={'intra_word_stutter', 'hesitation', 'long_character', 'punctuation_pause', 'duration_or_rate_outlier'} if resolved_backend == 'kaggle' else None)
    print(json.dumps(dict(ok=result['check']['ok'], chapter=chapter['id'])))
    return 0 if result['check']['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
