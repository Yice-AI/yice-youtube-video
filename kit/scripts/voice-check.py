#!/usr/bin/env python3
"""Offline character-level prosody checks; alignment estimates do not replace listening."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

PUNCT = set('，。！？；：、…,.!?;:')
QUOTES = set('“”‘’"\'')
END = set('。！？.!?')
HOP = .01
THRESHOLDS = dict(single_character_N=2.4, active_character_N=2., onset_character_N=1.7,
                  nonpunct_low_energy_min_ms=60., nonpunct_pause_max_ms=150.,
                  falling_end_st=-4., punctuation_tolerance_ms=20.,
                  intra_word_drop_db=14., intra_word_min_ms=95., intra_word_max_ms=260.,
                  sentence_rate_deviation=.38, seam_cosine=0.94, seam_pitch_st=3.2, seam_loudness_db=1.8,
                  contrast_pause_ms=[300., 450.], comma_pause_ms=[0., 340.],
                  sentence_pause_ms=[200., 620.])


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def load_alignment(path, text_file, audio):
    """Require actual character timing; sentence-only timing cannot locate a hesitation."""
    data = json.loads(Path(path).read_text())
    text = Path(text_file).read_text().strip()
    if isinstance(data, dict):
        if data.get('text', text) != text:
            raise ValueError('Reading text differs from alignment text')
        rows = data.get('mapped', data.get('characters'))
    else:
        rows = data
    if not text or not isinstance(rows, list) or not rows:
        raise ValueError('Expected text and nonempty character-level mapped/characters timing')
    info = sf.info(audio)
    previous, mapped = 0., []
    expected = [(i, i + 1) for i, c in enumerate(text) if c.isalnum()]
    for row in rows:
        if not all(k in row for k in ('charStart', 'charEnd', 's', 'e')):
            raise ValueError('Expected character timing: charStart, charEnd, s, e; sentence timing is insufficient')
        start, end = row['charStart'], row['charEnd']
        s, e = float(row['s']), float(row['e'])
        if (not isinstance(start, int) or not isinstance(end, int) or
                not 0 <= start < end <= len(text) or end != start + 1 or
                not np.isfinite([s, e]).all() or s < previous - 1e-5 or
                e < s or e > info.duration + 1 / info.samplerate):
            raise ValueError('Invalid, overlapping or out-of-audio character timing')
        mapped.append(dict(charStart=start, charEnd=end, s=s, e=e))
        previous = e
    if [(r['charStart'], r['charEnd']) for r in mapped] != expected:
        raise ValueError('Character timing must cover every spoken letter, digit and character once')
    return dict(text=text, mapped=mapped, planned_pauses=data.get('planned_pauses', {}) if isinstance(data, dict) else {})


def add_threshold_arguments(parser):
    parser.add_argument('--long-ratio', type=float, default=2.4)
    parser.add_argument('--active-ratio', type=float, default=2.)
    parser.add_argument('--onset-ratio', type=float, default=1.7)
    parser.add_argument('--hesitation-ms', type=float, default=60.)
    parser.add_argument('--nonpunct-max-ms', type=float, default=150.)
    parser.add_argument('--fall-semitones', type=float, default=4.)
    parser.add_argument('--pause-tolerance-ms', type=float, default=20.)
    parser.add_argument('--comma-ms', type=float, nargs=2, default=[0., 340.])
    parser.add_argument('--contrast-ms', type=float, nargs=2, default=[300., 450.])
    parser.add_argument('--sentence-ms', type=float, nargs=2, default=THRESHOLDS['sentence_pause_ms'])
    parser.add_argument('--intra-word-drop-db', type=float, default=14.)
    parser.add_argument('--intra-word-min-ms', type=float, default=95.)
    parser.add_argument('--intra-word-max-ms', type=float, default=260.)
    parser.add_argument('--rate-outlier-ratio', type=float, default=.38, help='每句字速相对章中位数的最大偏离比例')


def threshold_arguments(args):
    values = dict(single_character_N=args.long_ratio, active_character_N=args.active_ratio,
                  onset_character_N=args.onset_ratio, nonpunct_low_energy_min_ms=args.hesitation_ms,
                  nonpunct_pause_max_ms=args.nonpunct_max_ms, falling_end_st=-args.fall_semitones,
                  punctuation_tolerance_ms=args.pause_tolerance_ms, comma_pause_ms=args.comma_ms,
                  contrast_pause_ms=args.contrast_ms, sentence_pause_ms=args.sentence_ms,
                  intra_word_drop_db=args.intra_word_drop_db, intra_word_min_ms=args.intra_word_min_ms,
                  intra_word_max_ms=args.intra_word_max_ms, sentence_rate_deviation=args.rate_outlier_ratio)
    for name, value in values.items():
        items = value if isinstance(value, list) else [abs(value) if name == 'falling_end_st' else value]
        if not all(np.isfinite(v) and v >= 0 for v in items):
            raise ValueError('Thresholds must be finite and nonnegative')
        if isinstance(value, list) and (value[1] <= 0 or value[0] > value[1] or
                                        (value[0] == 0 and name != 'comma_pause_ms')):
            raise ValueError('Only ordinary commas allow a zero minimum pause')
    if min(args.long_ratio, args.active_ratio, args.onset_ratio, args.fall_semitones) <= 0:
        raise ValueError('Duration ratios and fall threshold must be positive')
    return values


def runs(mask, hop=HOP):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return [(float(a * hop), float(b * hop)) for a, b in
            zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))]


def acoustic(path, cache=None):
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if cache is not None and cache.exists():
        z = np.load(cache)
        if str(z['sha']) == sha:
            return {k: z[k] for k in z.files}
    x, sr = sf.read(path, always_2d=True)
    x = x.mean(axis=1)
    if not len(x) or not np.isfinite(x).all() or np.max(np.abs(x)) < 1e-9:
        raise ValueError('Audio must contain finite, non-silent samples')
    g = int(np.gcd(sr, 16000))
    y = resample_poly(x, 16000 // g, sr // g)
    frame = 320
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(y, (160, 160)), frame)[::160]
    db = 20 * np.log10(np.sqrt(np.mean(frames * frames, axis=1)) + 1e-12)
    f0, voiced, prob = librosa.pyin(y, fmin=60, fmax=450, sr=16000,
                                  frame_length=1024, hop_length=160,
                                  fill_na=np.nan)
    data = dict(sha=np.array(sha), db=db, f0=f0, voiced=voiced,
                voiced_probability=prob, duration=np.array(len(x) / sr))
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **data)
    return data


def pitch_stats(ac, a, b):
    t = np.arange(len(ac['f0'])) * HOP
    # pYIN already uses a Viterbi voiced/unvoiced decision. A second 0.1
    # probability cutoff discards most low-pitch voiced Chinese syllables.
    mask = (t >= a) & (t <= b) & np.isfinite(ac['f0'])
    ids = np.flatnonzero(mask)
    if len(ids) < 4:
        return dict(voiced_frames=int(len(ids)), f0_start_hz=None, f0_end_hz=None,
                    f0_change_st=None, f0_median_hz=None)
    values = ac['f0'][ids]
    count = max(2, len(values) // 3)
    start = float(np.median(values[:count]))
    end = float(np.median(values[-count:]))
    return dict(voiced_frames=len(ids), f0_start_hz=round(start, 2),
                f0_end_hz=round(end, 2), f0_change_st=round(12 * np.log2(end / start), 3),
                f0_median_hz=round(float(np.median(values)), 2))


def sentence_ranges(text):
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r'[^。！？.!?]+[。！？.!?]+[”"’\'\）)]*|[^。！？.!?]+$', text) if any(c.isalnum() for c in m.group())]


def pause_class(text, left, right, thresholds=None):
    thresholds = {**THRESHOLDS, **(thresholds or {})}
    between = text[left['charEnd']:right['charStart']]
    punct = ''.join(c for c in between if c in PUNCT)
    has_quote = any(c in QUOTES for c in between)
    if '…' in punct:
        return 'ellipsis', [200., 850.], punct
    if any(c in END for c in punct):
        return 'sentence', thresholds['sentence_pause_ms'], punct
    if any(c in '，,;；' for c in punct):
        context = text[max(0, left['charStart'] - 12):right['charStart'] + 10]
        contrast = bool(re.search(r'(没有[,，]得[是用]|[,，](?:但|不过|而是|却|得是|得用|反而)|[;；])', context))
        return ('contrast', thresholds['contrast_pause_ms'], punct) if contrast else ('comma', thresholds['comma_pause_ms'], punct)
    if punct:
        return ('list', [80., 320.], punct)
    if has_quote:
        return ('quote', [0., 420.], '“”')
    return ('none', [0, thresholds['nonpunct_pause_max_ms']], punct)


def measure(path, alignment, cache=None, thresholds=None):
    ac = acoustic(path, cache)
    text = alignment['text']
    lengths = [r['e'] - r['s'] for r in alignment['mapped']
               if re.fullmatch(r'[\u4e00-\u9fff]', text[r['charStart']:r['charEnd']])
               and .025 <= r['e'] - r['s'] <= .7]
    lengths = lengths or [r['e'] - r['s'] for r in alignment['mapped'] if r['e'] > r['s']]
    if not lengths:
        raise ValueError('Alignment has no positive character durations')
    med = float(np.median(lengths))
    threshold = float(np.percentile(ac['db'], 70) - 20)
    quiet = [(a, min(b, float(ac['duration']))) for a, b in runs(ac['db'] < threshold)
             if b - a >= .04]
    absolute = [(a, min(b, float(ac['duration']))) for a, b in runs(ac['db'] < -45)
                if b - a >= .05]
    chars = []
    sranges = sentence_ranges(text)
    mapped_list = [dict(r) for r in alignment['mapped']]
    clause_breaks = END | {'：', ':', '…', '；', ';'} | QUOTES
    comma_breaks = {'，', ',', '、'}
    for i, r in enumerate(mapped_list):
        prev_end = mapped_list[i - 1]['charEnd'] if i else 0
        between_prev = text[prev_end:r['charStart']]
        is_major = i == 0 or any(c in clause_breaks for c in between_prev)
        is_comma = any(c in comma_breaks for c in between_prev)
        if is_major or is_comma:
            min_q = .04 if is_major else .13
            cand = [qb for qa, qb in quiet if r['s'] - .02 <= qa <= r['s'] + .22 and qb > r['s'] + .03 and qb - qa >= min_q]
            if cand:
                qb = max(cand)
                k = i
                while (k + 1 < len(mapped_list)
                       and mapped_list[k + 1]['charStart'] == mapped_list[k]['charEnd']
                       and qb >= mapped_list[k]['e'] - .03):
                    k += 1
                span_end = mapped_list[k]['e']
                n_span = k - i + 1
                if qb < span_end - .04 * n_span:
                    for m in range(n_span):
                        mapped_list[i + m]['s'] = qb + (span_end - qb) * m / n_span
                        mapped_list[i + m]['e'] = qb + (span_end - qb) * (m + 1) / n_span
    for i, r in enumerate(mapped_list):
        w = text[r['charStart']:r['charEnd']]
        sentence = next((j for j, (a, b, _) in enumerate(sranges) if a <= r['charStart'] < b), -1)
        q = sum(max(0, min(r['e'], b) - max(r['s'], a)) for a, b in quiet)
        row = dict(**r, w=w, duration_ms=round((r['e'] - r['s']) * 1000, 2),
                   ratio=round((r['e'] - r['s']) / med, 3), sentence=sentence,
                   active_ms=round(max(0, r['e'] - r['s'] - q) * 1000, 2),
                   **pitch_stats(ac, r['s'], r['e']))
        chars.append(row)
    boundaries = []
    for i, (left, right) in enumerate(zip(chars, chars[1:])):
        kind, interval, punct = pause_class(text, left, right, thresholds)
        planned = alignment.get('planned_pauses', {}).get(str(left['charEnd']))
        if planned is not None and kind in ('comma', 'contrast', 'sentence'):
            interval = [1000 * float(planned)] * 2
        # Whisper often assigns the pause to the NEXT word; examine a boundary
        # window extending into its first 80%, without conflating a whole word.
        lo = max(left['s'], left['e'] - .10)
        hi = min(right['e'], right['s'] + min(.65, (right['e'] - right['s']) * .8))
        gaps = [(a, b) for a, b in quiet if b > lo and a < hi and a >= left['e'] - .09
                and (abs(a - left['e']) <= .14 or abs(b - right['s']) <= .14
                     or left['e'] <= a <= right['e'])]
        gap = max(gaps, key=lambda ab: ab[1] - ab[0], default=None)
        duration = (gap[1] - gap[0]) * 1000 if gap else 0.
        boundaries.append(dict(index=i, char_boundary=left['charEnd'], left=left['w'],
                               right=right['w'], kind=kind, punctuation=punct,
                               range_ms=interval, pause_ms=round(duration, 1),
                               pause_interval=gap, asr_gap_ms=round((right['s'] - left['e']) * 1000, 2),
                               context=text[max(0, left['charStart'] - 8):right['charEnd'] + 8]))
    # One measured acoustic interval can belong to only one lexical boundary.
    # Multi-character Whisper words otherwise create duplicate false alarms.
    owners = {}
    suppressed = []
    for b in boundaries:
        if b['pause_interval']:
            owners.setdefault(tuple(b['pause_interval']), []).append(b)
    for interval, candidates in owners.items():
        if len(candidates) > 1:
            chosen = min(candidates, key=lambda b: abs(interval[0] - chars[b['index']]['e'])
                         - (.15 if b['punctuation'] else 0))
            for b in candidates:
                if b is not chosen:
                    suppressed.append(dict(index=b['index'], context=b['context'],
                                           pause_ms=b['pause_ms'], owner=chosen['index']))
                    b.update(pause_ms=0., pause_interval=None, shared_pause_owner=chosen['index'])
    return dict(file=str(path), sha256=str(ac['sha']), duration_s=float(ac['duration']),
                text=text, median_char_ms=round(med * 1000, 3),
                relative_quiet_threshold_dbfs=round(threshold, 3),
                absolute_silence_45db=absolute, relative_quiet=quiet,
                db=np.asarray(ac['db']).tolist(),
                characters=chars, boundaries=boundaries,
                sentences=[dict(start=a, end=b, text=s) for a, b, s in sranges],
                chunk_seams=alignment.get('chunk_seams', []),
                measurement_version=4, duplicate_boundary_attributions_suppressed=suppressed,
                method='Whisper word alignment; multi-character words evenly apportioned; '
                       'raw-to-post mapping follows exact edits; pYIN 60–450Hz/10ms hop; '
                       'relative low-energy pauses may be audible, not digital silence.')


def detect(measurement, chapter_median_ms=None, thresholds=None):
    """Sensitive candidates, not claims of human-confirmed disfluency.

    A bare Mandarin falling tone is intentionally insufficient. Require
    duration or an acoustic hesitation as corroboration. Latin continuation
    letters and timing swallowed by punctuation are excluded explicitly.
    """
    thresholds = {**THRESHOLDS, **(thresholds or {})}
    d = measurement
    envelope = np.asarray(d.get('db', []), dtype=float)
    median = chapter_median_ms or d['median_char_ms']
    chars = d['characters']
    flags = []
    for i, r in enumerate(chars):
        prev = d['boundaries'][i - 1] if i else None
        after = d['boundaries'][i] if i < len(d['boundaries']) else None
        internal = prev and after and prev['kind'] == after['kind'] == 'none'
        if (internal and re.fullmatch(r'[\u4e00-\u9fff]', r['w'])
                and r['duration_ms'] / median >= thresholds['single_character_N']
                and r['active_ms'] / median >= thresholds['active_character_N']):
            flags.append(dict(kind='long_character', index=i, sentence=r['sentence'],
                              char_start=r['charStart'], char_end=r['charEnd'],
                              ratio=round(r['duration_ms'] / median, 3), token=r['w']))
    sentences = {}
    for char in chars:
        if char['sentence'] >= 0:
            sentences.setdefault(char['sentence'], []).append(char)
    def pronunciation_units(value):
        units = 0
        for token in re.findall(r'[A-Za-z]+|\d+|[\u4e00-\u9fff]', value):
            units += max(1, round(len(token) / 3.5)) if re.fullmatch(r'[A-Za-z\d]+', token) else 1
        return units

    speeds = {}
    for i, rows in sentences.items():
        spoken_s = sum(max(0., row['e'] - row['s']) for row in rows)
        if len(rows) >= 4 and spoken_s > 0.15:
            speeds[i] = pronunciation_units(''.join(row['w'] for row in rows)) / spoken_s
    if speeds:
        typical = float(np.median(list(speeds.values())))
        for sentence, speed in speeds.items():
            deviation = speed / typical - 1
            if abs(deviation) > thresholds['sentence_rate_deviation'] + 1e-9:
                rows = sentences[sentence]
                flags.append(dict(kind='duration_or_rate_outlier', sentence=sentence,
                                  char_start=rows[0]['charStart'], char_end=rows[-1]['charEnd'],
                                  chars_per_second=round(speed, 3), chapter_median=round(typical, 3),
                                  deviation=round(deviation, 3)))
    times = np.arange(len(envelope)) * HOP
    seen_valleys = set()
    for b in d['boundaries']:
        i = b['index']
        left, right = chars[i], chars[i + 1]
        if b['kind'] == 'none':
            if re.fullmatch('[A-Za-z]', left['w']) and re.fullmatch('[A-Za-z]', right['w']):
                continue
            ratio = right['duration_ms'] / median
            duration = b['pause_ms']
            fall = left['f0_change_st']
            reasons = []
            if duration >= thresholds['nonpunct_low_energy_min_ms'] and ratio >= thresholds['onset_character_N']:
                reasons.append('low_energy_plus_long_onset')
            if fall is not None and fall <= thresholds['falling_end_st'] and duration >= thresholds['nonpunct_low_energy_min_ms'] and left['duration_ms'] / median >= thresholds['onset_character_N']:
                reasons.append('mid_sentence_falling_end')
            if duration > thresholds['nonpunct_pause_max_ms']:
                reasons.append('nonpunct_pause')
            if reasons:
                flags.append(dict(kind='hesitation', reasons=reasons, index=i,
                                  sentence=right['sentence'], char_start=left['charStart'],
                                  char_end=right['charEnd'], context=b['context'],
                                  onset_ratio=round(ratio, 3), pause_ms=duration, f0_change_st=fall))
                if 'mid_sentence_falling_end' in reasons:
                    flags.append(dict(kind='mid_sentence_fall', index=i, sentence=right['sentence'],
                                      char_start=left['charStart'], char_end=right['charEnd'],
                                      f0_change_st=fall, pause_ms=duration, context=b['context']))
            # Compare the local 10ms envelope around adjacent syllables. This
            # catches a short relative collapse that never reaches -42 dBFS.
            if (left['sentence'] != right['sentence'] or left['charEnd'] != right['charStart']
                    or bool(re.fullmatch('[A-Za-z]', left['w'])) != bool(re.fullmatch('[A-Za-z]', right['w']))):
                continue
            ids = np.flatnonzero((times >= left['s']) & (times < right['e']))
            if not len(ids):
                continue
            local = envelope[ids]
            left_db = local[times[ids] < left['e']]
            right_db = local[times[ids] >= right['s']]
            if not len(left_db) or not len(right_db):
                continue
            ref = min(float(left_db.max()), float(right_db.max()))
            if ref <= -42:
                continue
            for lo, hi in runs(local <= ref - thresholds['intra_word_drop_db']):
                start_bin, end_bin = round(lo / HOP), round(hi / HOP)
                # An ASR boundary can lead the syllable by one or two hops.
                # Require a measurable shoulder on both sides of an internal dip.
                if start_bin < 3 or len(local) - end_bin < 3:
                    continue
                if local[start_bin:end_bin].min() <= -75:
                    continue
                interval = (int(ids[0]) + start_bin, int(ids[0]) + end_bin)
                duration_ms = round((end_bin - start_bin) * HOP * 1000, 2)
                if (interval in seen_valleys or not thresholds['intra_word_min_ms']
                        <= duration_ms <= thresholds['intra_word_max_ms']):
                    continue
                seen_valleys.add(interval)
                flags.append(dict(kind='intra_word_stutter', index=i, sentence=right['sentence'],
                                  char_start=left['charStart'], char_end=right['charEnd'],
                                  drop_db=round(ref - float(local[start_bin:end_bin].min()), 2),
                                  duration_ms=duration_ms, start_s=round(interval[0]*HOP, 3),
                                  context=b['context']))
        elif b['kind'] in ['comma', 'contrast', 'sentence']:
            low, high = b['range_ms']
            if not low - thresholds['punctuation_tolerance_ms'] <= b['pause_ms'] <= high + thresholds['punctuation_tolerance_ms']:
                flags.append(dict(kind='punctuation_pause', index=i, sentence=left['sentence'],
                                  char_start=left['charStart'], char_end=right['charEnd'],
                                  context=b['context'], pause_class=b['kind'],
                                  pause_ms=b['pause_ms'], expected_ms=b['range_ms']))
    for seam in d.get('chunk_seams', []):
        if not isinstance(seam, dict):
            continue
        cosine, pitch, loudness = seam.get('mfcc_mean_cosine'), seam.get('pitch_shift_semitones'), seam.get('loudness_delta_db')
        if ((cosine is not None and cosine < thresholds['seam_cosine']) or
                (pitch is not None and abs(pitch) > thresholds['seam_pitch_st']) or
                 (loudness is not None and abs(loudness) > thresholds['seam_loudness_db'])):
            flags.append(dict(kind='chunk_seam_jump', seam=seam))
    return flags

def check_chapter(audio, alignment, *, chapter=None, cache=None, thresholds=None):
    thresholds = {**THRESHOLDS, **(thresholds or {})}
    measurement = measure(audio, alignment, cache, thresholds)
    alerts = detect(measurement, thresholds=thresholds)
    return dict(chapter=chapter or Path(audio).stem, ok=not alerts, alerts=alerts,
                thresholds=thresholds, measurement=measurement)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--alignment', '--timing', dest='alignment', type=Path, required=True)
    parser.add_argument('--text-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--chapter')
    add_threshold_arguments(parser)
    args = parser.parse_args(argv)
    try:
        alignment = load_alignment(args.alignment, args.text_file, args.audio)
        report = check_chapter(args.audio, alignment, chapter=args.chapter,
                               cache=args.cache, thresholds=threshold_arguments(args))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        write_json(args.output, dict(ok=False, error=str(exc), alerts=[]))
        print(str(exc), file=sys.stderr)
        return 2
    write_json(args.output, report)
    print(json.dumps(dict(chapter=report['chapter'], ok=report['ok'],
                          alert_count=len(report['alerts'])), ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
