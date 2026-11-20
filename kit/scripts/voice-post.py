#!/usr/bin/env python3
"""Pitch-preserving voice postprocessing with semantic pause budgets and timing maps."""
import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

_spec = importlib.util.spec_from_file_location('voice_check', Path(__file__).with_name('voice-check.py'))
pd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pd)


def map_time(t, edits, endpoint='start'):
    shift = 0.
    for e in sorted(edits, key=lambda z: z['start_s']):
        a, b, new = e['start_s'], e['end_s'], e['new_duration_s']
        if b == a:
            epsilon = e.get('sample_epsilon_s', 1 / 96000)
            if t > a + epsilon or (abs(t - a) <= epsilon and endpoint == 'start'):
                shift += new
            else:
                break
        elif t >= b:
            shift += new - (b - a)
        elif t > a:
            return a + shift + (t - a) * new / (b - a)
        else:
            break
    return t + shift


def regularize(path, alignment, destination, cache, scene_boundaries=(), scene_padding=0., fade_ms=10., thresholds=None):
    x, sr = sf.read(path, always_2d=True)
    x = x.mean(axis=1)
    measurements = pd.measure(path, alignment, cache, thresholds)
    ac = pd.acoustic(path, cache)
    edits = []
    chars = measurements['characters']
    for b in measurements['boundaries']:
        if b['kind'] not in ['comma', 'contrast', 'sentence']:
            continue
        left, right = chars[b['index']], chars[b['index'] + 1]
        padding = scene_padding if b['char_boundary'] in scene_boundaries else 0.
        low, high = (v / 1000 for v in b['range_ms'])
        duration = b['pause_ms'] / 1000
        if low <= duration + padding <= high:
            continue  # An existing reasonable pause is preserved, not capped.
        target = (low + high) / 2 - padding
        if target < .03:
            raise ValueError('Scene padding exceeds semantic pause budget')
        verified_alignment_gap = (
            not b['pause_interval'] and b.get('asr_gap_ms', 0) / 1000 > high and
            any(a <= left['e'] and z >= right['s']
                for a, z in measurements.get('absolute_silence_45db', []))
        )
        if b['pause_interval']:
            a, z = b['pause_interval']
        elif verified_alignment_gap:
            # Whisper can leave a large word-time gap even when the waveform
            # contains verified absolute silence. Trim that silence to the
            # semantic target instead of treating the boundary as zero-length
            # and inserting a second pause.
            a, z = left['e'], right['s']
        else:
            # Insert at the aligned lexical boundary, not inside the previous
            # word. Edge fades suppress clicks without discarding phonemes.
            # Place an inserted pause exactly after the left lexical item. A
            # rounded midpoint can land a fraction after ``left['e']`` and
            # make the end-time mapper extend the preceding character.
            at = round(left['e'] * sr) / sr
            a = z = at
        delta = target - (z - a)
        fade = round(fade_ms / 1000 * sr)
        if delta > 0:
            at = round((a + z) * .5 * sr)
            count = round(delta * sr)
            edits.append(dict(start_s=at / sr, end_s=at / sr,
                              new_duration_s=count / sr, insert_samples=count,
                              # Allow two samples of alignment quantization so
                              # the left character's end remains before the
                              # inserted pause rather than absorbing it.
                              sample_epsilon_s=2 / sr,
                              kind='insert', char_boundary=b['char_boundary'],
                              pause_class=b['kind'], before_ms=b['pause_ms'],
                              intended_final_ms=round((target + padding) * 1000, 3),
                              scene_padding_ms=padding * 1000))
        elif -delta * sr >= fade:
            loss = round(-delta * sr)
            middle = round((a + z) * .5 * sr)
            l = middle - (loss - fade) // 2
            r = l + loss - fade
            begin, end = l - fade, r + fade
            if begin < round(a * sr) or end > round(z * sr):
                continue
            edits.append(dict(start_s=begin / sr, end_s=end / sr,
                              new_duration_s=fade / sr, kind='trim',
                              char_boundary=b['char_boundary'],
                              pause_class=b['kind'], before_ms=b['pause_ms'],
                              intended_final_ms=round((target + padding) * 1000, 3),
                              scene_padding_ms=padding * 1000))
    # A single low-energy interval can be attributed to two nearby punctuation
    # boundaries after Whisper's word-time interpolation.  Keep the stronger
    # semantic edit and record the suppressed one instead of aborting the whole
    # chapter.  The old hard failure made short, independently generated chunks
    # impossible to assemble when their boundaries landed close together.
    edits.sort(key=lambda e: e['start_s'])
    resolved, suppressed = [], []
    priority = {'sentence': 3, 'contrast': 3, 'comma': 2, 'list': 1, 'none': 0}
    for edit in edits:
        current = edit
        while current is not None and resolved and current['start_s'] < resolved[-1]['end_s']:
            previous = resolved[-1]
            current_key = (priority.get(current.get('pause_class'), 0),
                           abs(current.get('before_ms', 0) - current.get('intended_final_ms', 0)))
            previous_key = (priority.get(previous.get('pause_class'), 0),
                            abs(previous.get('before_ms', 0) - previous.get('intended_final_ms', 0)))
            if current_key > previous_key:
                suppressed.append(previous)
                resolved.pop()
            else:
                suppressed.append(current)
                current = None
        if current is not None:
            resolved.append(current)
    edits = resolved
    for e in reversed(edits):
        a, b = round(e['start_s'] * sr), round(e['end_s'] * sr)
        fade = round(fade_ms / 1000 * sr)
        if e['kind'] == 'insert':
            pre, post = x[:a].copy(), x[a:].copy()
            n = min(fade, len(pre), len(post))
            if n:
                pre[-n:] *= np.linspace(1, 0, n)
                post[:n] *= np.linspace(0, 1, n)
            x = np.r_[pre, np.zeros(e['insert_samples']), post]
        else:
            n = round(e['new_duration_s'] * sr)
            t = np.linspace(0, 1, n)
            blend = x[a:a+n] * (1 - t) + x[b-n:b] * t
            x = np.r_[x[:a], blend, x[b:]]
    updated = copy.deepcopy(alignment)
    for r in updated['mapped']:
        r['s'] = map_time(r['s'], edits, 'start')
        r['e'] = map_time(r['e'], edits, 'end')
        if r['e'] < r['s']:
            r['e'] = r['s']
    assert all(a['e'] <= b['s'] + 1e-5 for a, b in zip(updated['mapped'], updated['mapped'][1:]))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destination, x, sr, subtype='FLOAT')
    updated['semantic_pause_edits'] = edits
    updated['suppressed_pause_edits'] = suppressed
    return updated, edits


def trim_nonpunct_pauses(path, alignment, destination, cache, *, thresholds=None,
                         target_ms=120., fade_ms=10.):
    """Trim verified low-energy gaps at non-punctuation boundaries.

    Qwen3-TTS can insert a long breath-like gap inside a sentence.  It is safe
    to shorten only the measured low-energy interval, with a small crossfade;
    cutting voiced samples or fabricating a boundary is prohibited.
    """
    x, sr = sf.read(path, always_2d=True)
    x = x.mean(axis=1)
    measurements = pd.measure(path, alignment, cache, thresholds)
    maximum = float((thresholds or pd.THRESHOLDS)['nonpunct_pause_max_ms'])
    target = min(float(target_ms), max(20., maximum - 10.)) / 1000.
    fade = max(1, round(fade_ms / 1000 * sr))
    edits = []
    for boundary in measurements['boundaries']:
        if boundary['kind'] != 'none' or not boundary['pause_interval']:
            continue
        a, z = boundary['pause_interval']
        if boundary['pause_ms'] <= maximum or z - a <= target:
            continue
        loss = round((z - a - target) * sr)
        middle = round((a + z) * .5 * sr)
        left = middle - (loss - fade) // 2
        right = left + loss - fade
        begin, end = left - fade, right + fade
        if begin < round(a * sr) or end > round(z * sr) or end <= begin:
            continue
        edits.append(dict(start_s=begin / sr, end_s=end / sr,
                          new_duration_s=fade / sr, kind='nonpunct_trim',
                          char_boundary=boundary['char_boundary'],
                          pause_class=boundary['kind'], before_ms=boundary['pause_ms'],
                          intended_final_ms=round(target * 1000, 3)))
    edits.sort(key=lambda e: e['start_s'])
    for left, right in zip(edits, edits[1:]):
        if left['end_s'] > right['start_s']:
            raise ValueError('Overlapping non-punctuation trims')
    for edit in reversed(edits):
        a, b = round(edit['start_s'] * sr), round(edit['end_s'] * sr)
        n = round(edit['new_duration_s'] * sr)
        t = np.linspace(0, 1, n)
        blend = x[a:a+n] * (1 - t) + x[b-n:b] * t
        x = np.r_[x[:a], blend, x[b:]]
    updated = copy.deepcopy(alignment)
    for row in updated['mapped']:
        row['s'] = map_time(row['s'], edits, 'start')
        row['e'] = map_time(row['e'], edits, 'end')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destination, x, sr, subtype='FLOAT')
    updated['nonpunct_pause_edits'] = edits
    return updated, edits

def breath_candidates(samples, rate, alignment, acoustic):
    """Conservative broadband, low-energy proxies at verified inter-character boundaries."""
    reference = float(np.percentile(acoustic['db'], 70))
    spans = list(pd.runs(acoustic['db'] < reference - 10))
    spans += [(a['e'], b['s']) for a, b in zip(alignment['mapped'], alignment['mapped'][1:])
              if b['s'] > a['e']]
    merged = []
    for a, b in sorted(spans):
        a, b = max(0., a), min(len(samples) / rate, b)
        if merged and a <= merged[-1][1] + .015:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    result = []
    for a, b in merged:
        if not .12 <= b - a <= .6:
            continue
        nearby = [i for i, (left, right) in enumerate(zip(alignment['mapped'], alignment['mapped'][1:]))
                  if a >= left['e'] - .09 and b <= right['e'] and
                  min(abs(a - left['e']), abs(b - right['s'])) <= .3]
        if not nearby:
            continue
        segment = samples[round(a * rate):round(b * rate)]
        relative = 20 * np.log10(np.sqrt(np.mean(segment ** 2)) + 1e-12) - reference
        if not -45 <= relative <= -10:
            continue
        frame, hop = max(32, round(.02 * rate)), max(1, round(.005 * rate))
        if len(segment) < frame:
            continue
        frames = np.lib.stride_tricks.sliding_window_view(segment, frame)[::hop]
        power = np.abs(np.fft.rfft(frames * np.hanning(frame), axis=1)) ** 2 + 1e-20
        frequencies = np.fft.rfftfreq(frame, 1 / rate)
        selected = (frequencies >= 300) & (frequencies <= min(8000, rate / 2))
        power, frequencies = power[:, selected], frequencies[selected]
        probabilities = power / power.sum(axis=1, keepdims=True)
        flatness = float(np.median(np.exp(np.mean(np.log(power), axis=1)) / power.mean(axis=1)))
        entropy = float(np.median(-np.sum(probabilities * np.log(probabilities), axis=1) / np.log(power.shape[1])))
        distribution = probabilities.mean(axis=0).cumsum()
        bandwidth = float(frequencies[min(np.searchsorted(distribution, .95), len(frequencies)-1)] -
                          frequencies[min(np.searchsorted(distribution, .05), len(frequencies)-1)])
        if flatness >= .04 and entropy >= .65 and bandwidth >= 1800:
            result.append(dict(start_s=a, end_s=b, relative_voice_db=round(relative, 3),
                               flatness=round(flatness, 4), entropy=round(entropy, 4),
                               bandwidth_hz=round(bandwidth), boundary_index=nearby[0]))
    return result


def attenuate_breaths(samples, rate, alignment, acoustic, *, gain_db=-12., cut_ms=250., target_ms=150., fade_ms=10.):
    result = samples.copy()
    events = breath_candidates(samples, rate, alignment, acoustic)
    edits = []
    fade = max(1, round(fade_ms / 1000 * rate))
    for event in events:
        a, b = round(event['start_s'] * rate), round(event['end_s'] * rate)
        gain = np.full(b - a, 10 ** (gain_db / 20))
        edge = min(fade, len(gain) // 2)
        gain[:edge] = np.linspace(1, gain[edge], edge)
        gain[-edge:] = np.linspace(gain[-edge-1], 1, edge)
        result[a:b] *= gain
        event['gain_db'] = gain_db
        if (b - a) / rate * 1000 > cut_ms:
            loss = b - a - round(target_ms / 1000 * rate)
            begin = (a + b - loss - fade) // 2
            end = begin + loss + fade
            if loss > 0 and begin >= a + round(.015 * rate) and end <= b - round(.015 * rate):
                edits.append(dict(start_s=begin / rate, end_s=end / rate,
                                  new_duration_s=fade / rate, kind='breath_trim'))
                event['target_ms'] = target_ms
    for edit in reversed(edits):
        a, b = round(edit['start_s'] * rate), round(edit['end_s'] * rate)
        mix = np.linspace(0, 1, fade)
        result = np.r_[result[:a], result[a:a+fade] * (1-mix) + result[b-fade:b] * mix, result[b:]]
    updated = copy.deepcopy(alignment)
    for row in updated['mapped']:
        row['s'] = map_time(row['s'], edits, 'start')
        row['e'] = map_time(row['e'], edits, 'end')
    return result, updated, events, edits


def loudness(path, target=-16.):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
                             '-af', f'loudnorm=I={target}:TP=-1.2:LRA=11:print_format=json',
                             '-f', 'null', '-'], capture_output=True, text=True, check=True)
    return json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind('{'):])[0]


def normalize_lufs(source, destination, target=-16.):
    if not np.isfinite(target) or not -30 <= target <= -5:
        raise ValueError('LUFS target must be between -30 and -5')
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('Keep the original audio when normalizing')
    measured = loudness(source, target)
    if not np.isfinite(float(measured['input_i'])):
        raise ValueError('Cannot normalize silent or invalid audio')
    info = sf.info(source)
    filt = (f"loudnorm=I={target}:TP=-1.2:LRA=11:linear=true:"
            f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
            f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
            f"offset={measured['target_offset']}")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-af', filt,
                    '-ar', str(info.samplerate), '-ac', '1', '-c:a', 'pcm_s24le', str(destination)],
                   check=True, capture_output=True)
    if sf.info(destination).frames != info.frames:
        raise ValueError('LUFS normalization changed sample count')
    levels = loudness(destination, target)
    delta = target - float(levels['input_i'])
    if abs(delta) > .1 and float(levels['input_tp']) + delta <= -1.1:
        adjusted = Path(destination).with_name(Path(destination).stem + '-gain.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(destination),
                        '-af', f'volume={delta}dB', '-c:a', 'pcm_s24le', str(adjusted)],
                       check=True, capture_output=True)
        if sf.info(adjusted).frames != info.frames:
            raise ValueError('Gain changed sample count')
        adjusted.replace(destination)
        levels = loudness(destination, target)
    return dict(target_lufs=target, measured_lufs=float(levels['input_i']),
                true_peak_dbtp=float(levels['input_tp']), samples=info.frames)

def postprocess(audio, alignment, output, *, speed=1.08, breath_db=-12.,
                breath_cut_ms=250., breath_target_ms=150., fade_ms=10.,
                thresholds=None, scene_boundaries=(), scene_padding=0., lufs=-16.):
    if not np.isfinite([speed, breath_db, breath_cut_ms, breath_target_ms, fade_ms, scene_padding]).all():
        raise ValueError('Postprocessing parameters must be finite')
    if (not .5 <= speed <= 2 or breath_db > 0 or fade_ms <= 0 or scene_padding < 0 or
            breath_target_ms <= 2 * fade_ms + 30 or breath_cut_ms < breath_target_ms):
        raise ValueError('Invalid speed, breath, fade or scene-padding parameters')
    audio, output = Path(audio), Path(output)
    if audio.resolve() == output.resolve():
        raise ValueError('Output must differ from source; keep the original voice')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='voice-post-') as directory:
        temp = Path(directory)
        stretched = temp / 'speed.wav'
        command = ['ffmpeg', '-v', 'error', '-y', '-i', str(audio), '-af', f'atempo={speed}',
                   '-ac', '1', '-c:a', 'pcm_f32le', str(stretched)]
        if speed == 1:
            original, rate = sf.read(audio, always_2d=True)
            sf.write(stretched, original.mean(axis=1), rate, subtype='FLOAT')
        else:
            subprocess.run(command, check=True, capture_output=True)
        samples, rate = sf.read(stretched)
        updated = copy.deepcopy(alignment)
        for row in updated['mapped']:
            row['s'] = min(row['s'] / speed, len(samples) / rate)
            row['e'] = min(row['e'] / speed, len(samples) / rate)
        acoustic = pd.acoustic(stretched, temp / 'speed.npz')
        samples, updated, breaths, trims = attenuate_breaths(
            samples, rate, updated, acoustic, gain_db=breath_db, cut_ms=breath_cut_ms,
            target_ms=breath_target_ms, fade_ms=fade_ms)
        prepared = temp / 'breaths.wav'
        sf.write(prepared, samples, rate, subtype='FLOAT')
        destination = temp / 'semantic.wav'
        updated, pauses = regularize(prepared, updated, destination, temp / 'breaths.npz',
                                    scene_boundaries, scene_padding, fade_ms, thresholds)
        nonpunct = temp / 'nonpunct.wav'
        updated, nonpunct_edits = trim_nonpunct_pauses(
            destination, updated, nonpunct, temp / 'nonpunct.npz', thresholds=thresholds,
            fade_ms=fade_ms)
        levels = normalize_lufs(nonpunct, temp / 'normalized.wav', lufs)
        samples, rate = sf.read(temp / 'normalized.wav')
        temporary = output.with_name(output.stem + '.tmp.wav')
        sf.write(temporary, samples, rate, subtype='PCM_24')
        temporary.replace(output)
    updated['postprocessing'] = dict(speed=speed, breath_gain_db=breath_db,
                                    breath_events=breaths, breath_trims=trims,
                                    semantic_pause_edits=pauses, fade_ms=fade_ms,
                                    suppressed_pause_edits=updated.get('suppressed_pause_edits', []),
                                    nonpunct_pause_edits=nonpunct_edits,
                                    scene_padding_s=scene_padding,
                                    scene_boundaries=list(scene_boundaries),
                                    duration_s=len(samples) / rate, loudness=levels)
    updated['post_check'] = pd.check_chapter(output, updated, thresholds=thresholds)
    return updated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--alignment', '--timing', dest='alignment', type=Path, required=True)
    parser.add_argument('--text-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--output-alignment', type=Path, required=True)
    parser.add_argument('--speed', type=float, default=1.08)
    parser.add_argument('--breath-db', type=float, default=-12.)
    parser.add_argument('--breath-cut-ms', type=float, default=250.)
    parser.add_argument('--breath-target-ms', type=float, default=150.)
    parser.add_argument('--fade-ms', type=float, default=10.)
    parser.add_argument('--lufs', type=float, default=-16.)
    parser.add_argument('--scene-boundaries', type=Path, help='JSON list of character boundaries before scene padding')
    parser.add_argument('--scene-padding', type=float, default=0.)
    pd.add_threshold_arguments(parser)
    args = parser.parse_args(argv)
    try:
        aligned = pd.load_alignment(args.alignment, args.text_file, args.audio)
        result = postprocess(args.audio, aligned, args.output, speed=args.speed,
                             breath_db=args.breath_db, breath_cut_ms=args.breath_cut_ms,
                             breath_target_ms=args.breath_target_ms, fade_ms=args.fade_ms,
                             scene_padding=args.scene_padding,
                             lufs=args.lufs,
                             scene_boundaries=json.loads(args.scene_boundaries.read_text()) if args.scene_boundaries else [],
                             thresholds=pd.threshold_arguments(args))
        pd.write_json(args.output_alignment, result)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(dict(duration_s=result['postprocessing']['duration_s'],
                          breath_events=len(result['postprocessing']['breath_events']),
                          pause_edits=len(result['semantic_pause_edits'])), ensure_ascii=False))
    return 0 if result['post_check']['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
