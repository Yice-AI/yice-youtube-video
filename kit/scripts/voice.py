#!/usr/bin/env python3
"""T61 的章级 MLX 配音、Whisper 字级估计、captions.align 和换幕静音封装。"""
import argparse
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import wave
from pathlib import Path

from workspace import load_environment, load_voice_reference, valid_whisper_directory

WORKSPACE, TOOLKIT = load_environment()


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


_CHINESE_TTS_CHAR = r'[\u3400-\u9fff\uf900-\ufaff\U00020000-\U000323af，。！？、；：…—《》〈〉（）【】「」『』“”‘’]'
_CHINESE_TTS_SPACES = re.compile(rf'(?<={_CHINESE_TTS_CHAR}) +| +(?={_CHINESE_TTS_CHAR})')


def normalize_tts_text(text):
    return _CHINESE_TTS_SPACES.sub("", text)


_PRONUNCIATION_NOTE = re.compile(r"([\u3400-\u9fffA-Za-z0-9]+)〔(?:读|音)[：:]\s*([^〕]+?)〕")


def extract_pronunciations(text):
    pairs = {}
    for prefix, reading in _PRONUNCIATION_NOTE.findall(text or ""):
        prefix, reading = prefix.strip(), reading.strip()
        if "=" in reading:
            surface, reading = (part.strip() for part in reading.split("=", 1))
        elif re.search(r"[A-Za-z0-9]+$", prefix):
            surface = re.search(r"[A-Za-z0-9]+$", prefix)[0]
        else:
            surface = prefix[-len(reading):] if len(prefix) >= len(reading) else prefix
        if surface and reading and surface != reading:
            pairs[surface] = reading
    return pairs


def apply_pronunciations(text, pronunciations=None):
    result = text
    for surface, reading in sorted((pronunciations or {}).items(), key=lambda item: -len(item[0])):
        result = result.replace(surface, reading)
    return result


def spoken(text):
    plain = re.sub(r"〔[^〕]*〕", "", text).replace("**", "").replace("`", "")
    return normalize_tts_text(re.sub(r"\s+", " ", plain).strip())


def parse_script(path):
    chapters, chapter, seen = [], None, set()
    for line in Path(path).read_text().splitlines():
        heading = re.match(r"^##\s+(\d{2}[a-z]?)\s*(.*)", line)
        if heading:
            chapter = {"id": heading[1], "title": heading[2].strip(), "scenes": [], "pronunciations": {}}
            if any(c["id"] == chapter["id"] for c in chapters):
                raise ValueError(f"重复章号：{chapter['id']}")
            chapters.append(chapter)
        if not line.lstrip().startswith("|"):
            continue
        cells = [s.strip() for s in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not re.fullmatch(r"\d+[a-z]?-\d+[a-z]?\+?", cells[0]):
            continue
        if chapter is None:
            raise ValueError("幕行前须有 ## 00 章标题")
        sid, text = cells[0].removesuffix("+"), spoken(cells[1])
        if sid in seen or not text:
            raise ValueError(f"重复幕号或空旁白：{sid}")
        seen.add(sid)
        chapter["pronunciations"].update(extract_pronunciations(cells[1]))
        chapter["scenes"].append({"id": sid, "text": text})
    chapters = [c for c in chapters if c["scenes"]]
    if not chapters:
        raise ValueError("未找到 script-v2 格式的章标题和旁白表格")
    for chapter in chapters:
        chapter["text"] = normalize_tts_text(" ".join(s["text"] for s in chapter["scenes"]))
    return chapters


def scene_text_spans(chapter):
    end = 0
    for scene in chapter["scenes"]:
        start = chapter["text"].index(scene["text"], end)
        end = start + len(scene["text"])
        yield scene, start, end


def generate_jobs(jobs, brand, backend="modal", candidates=3):
    if backend in {"modal", "kaggle"}:
        for job in jobs:
            generate_modal_job(job, brand, backend)
        return
    import random
    sys.path[:0] = [str(TOOLKIT / "local/tools"), str(TOOLKIT / "tools")]
    from local_voiceover import MLXBackend, load_clone
    mlx = MLXBackend("8bit", load_clone(brand))
    for job in jobs:
        target = Path(job["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"拒绝覆盖已有原音：{target}")
        mode = job.get("chunk_mode", "long_paragraph")
        pronunciations = job.get("pronunciations") or {}
        if job.get("chunks"):
            chunks = [apply_pronunciations(c, pronunciations) for c in job["chunks"]]
        else:
            chunks = chapter_chunks(apply_pronunciations(job["text"], pronunciations), mode)
        pauses = {int(k): v for k, v in job.get("pauses", {}).items()}
        if len(chunks) == 1 and not pauses:
            mlx.mx.random.seed(job["seed"])
            random.seed(job["seed"])
            mlx.generate(text=normalize_tts_text(chunks[0]), model=mlx.model,
                         ref_audio=mlx.clone["audio"], ref_text=mlx.clone["text"],
                         lang_code=mlx.clone["language"], stt_model=None,
                         output_path=str(target.parent), file_prefix=target.stem,
                         audio_format="wav", join_audio=True, verbose=False,
                         max_tokens=4096, split_pattern="")
        else:
            folder = target.with_suffix(".chunks")
            folder.mkdir(exist_ok=True)
            raw = []
            for index, chunk in enumerate(chunks):
                part = folder / f"chunk-{index:03}.wav"
                chunk_seed = (int(job["seed"]) + index * 997) % (2**32)
                mlx.mx.random.seed(chunk_seed)
                random.seed(chunk_seed)
                mlx.generate(text=normalize_tts_text(chunk), model=mlx.model,
                             ref_audio=mlx.clone["audio"], ref_text=mlx.clone["text"],
                             lang_code=mlx.clone["language"], stt_model=None,
                             output_path=str(folder), file_prefix=part.stem,
                             audio_format="wav", join_audio=True, verbose=False,
                             max_tokens=4096, split_pattern="")
                if not part.is_file() or part.stat().st_size <= 44:
                    raise RuntimeError(f"MLX 未生成有效分段 WAV：{part}")
                raw.append(part)
            _concat_wavs(raw, target, pauses=pauses)
            write_json(folder / "chunks.json", dict(texts=chunks, pauses=pauses, backend="local", chunk_mode=mode))
        if not target.is_file() or target.stat().st_size <= 44:
            raise RuntimeError(f"MLX 未生成有效 WAV：{target}")


def semantic_chunks(text, minimum=3, maximum=5, min_chars=60, max_chars=120):
    """按句末标点切成适合 TTS 的语义组，保留原文顺序（严防 chunks[-2] += pop() 下标漂移丢段）。"""
    sentences = [
        part.strip()
        for part in re.findall(r'[^。！？!?]+[。！？!?]+[”"’\）)]*|[^。！？!?]+$', text)
        if part.strip()
    ]
    chunks, current = [], []
    size = 0
    for sentence in sentences or [text.strip()]:
        if current and (len(current) >= maximum or (size >= min_chars and size + len(sentence) > max_chars)):
            chunks.append("".join(current))
            current, size = [], 0
        current.append(sentence)
        size += len(sentence)
    if current:
        chunks.append("".join(current))
    if len(chunks) > 1 and len(chunks[-1]) < min_chars:
        tail = chunks.pop()
        chunks[-1] = chunks[-1] + tail
    return chunks or [text]


CHUNK_MODES = ('whole_chapter', 'long_paragraph', 'legacy_chunk')


def chapter_chunks(text, mode='long_paragraph'):
    text = text.strip()
    if not text or mode not in CHUNK_MODES:
        raise ValueError('须提供非空旁白及有效的分段模式')
    if mode == 'legacy_chunk':
        return semantic_chunks(text)
    if mode == 'whole_chapter':
        return [text]

    min_chars, max_chars, maximum = 65, 115, 5
    boundaries = [0, *(match.end() for match in re.finditer(r'[。！？]+[”’"）)]*', text))]
    if boundaries[-1] != len(text):
        boundaries.append(len(text))
    if any(end - start > max_chars for start, end in zip(boundaries, boundaries[1:])):
        raise ValueError('单句超过 115 字，请在自然停顿处补句末标点')

    # Prefer the fewest short groups, then the fewest cuts.
    last = len(boundaries) - 1
    scores = [(0, 0)] * (last + 1)
    next_group = [last] * last
    for start in range(last - 1, -1, -1):
        best = None
        for end in range(min(start + maximum, last), start, -1):
            length = boundaries[end] - boundaries[start]
            if length > max_chars:
                continue
            short_groups, groups = scores[end]
            score = (short_groups + (length < min_chars), groups + 1)
            if best is None or score < best:
                best, next_group[start] = score, end
        scores[start] = best

    chunks, start = [], 0
    while start < last:
        end = next_group[start]
        chunks.append(text[boundaries[start]:boundaries[end]])
        start = end
    return chunks


def _clone_reference(brand):
    return load_voice_reference(TOOLKIT, brand)


def resolve_backend(stage, backend, allow_slow_local=False):
    if backend == "local" and not allow_slow_local:
        raise ValueError("本机配音需要显式指定 --backend local --allow-slow-local")
    if backend != "auto":
        return backend
    if stage == "draft" and os.environ.get("KAGGLE_TTS_ENDPOINT_URL"):
        return "kaggle"
    if os.environ.get("MODAL_QWEN3_TTS_ENDPOINT_URL"):
        if stage == "draft":
            print("Kaggle 测试端点未配置，本次使用 Modal。", file=sys.stderr)
        return "modal"
    if os.environ.get("KAGGLE_TTS_ENDPOINT_URL"):
        return "kaggle"
    raise ValueError("请配置 Kaggle 或 Modal 云端配音端点")


def _kaggle_async_batch(base, body, headers, timeout):
    """Return None only for an old server that lacks the submission route."""
    deadline = time.monotonic()+timeout

    def request(url, data=None):
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        req = urllib.request.Request(url,data=data,headers=headers,method='POST' if data is not None else 'GET')
        request_timeout = 60. if data is not None else 15.
        with urllib.request.urlopen(req,timeout=min(request_timeout,remaining)) as response:
            return json.load(response)

    try:
        submitted = request(base+'/tts_async',body)
    except urllib.error.HTTPError as exc:
        if exc.code==404:
            return None
        raise RuntimeError(f'Kaggle 异步提交失败（HTTP {exc.code}）') from None
    except (OSError,ValueError):
        # A response may have been lost after accepting the job. Do not
        # submit another copy automatically and pay for the same synthesis twice.
        raise RuntimeError('Kaggle 异步提交未收到有效回执') from None
    job_id = submitted.get('job_id') if isinstance(submitted,dict) else None
    if not isinstance(job_id,str) or not re.fullmatch(r'[0-9a-f]{16}',job_id):
        raise RuntimeError('Kaggle 异步回执缺少有效任务号')

    url = base+'/tts_job/'+job_id
    while (remaining := deadline-time.monotonic())>0:
        time.sleep(min(2.5,remaining))
        try:
            status = request(url)
        except urllib.error.HTTPError as exc:
            if exc.code==429 or 500<=exc.code<600:
                continue
            raise RuntimeError(f'Kaggle 异步轮询失败（HTTP {exc.code}）') from None
        except OSError:
            continue
        except ValueError:
            raise RuntimeError('Kaggle 异步轮询返回无效 JSON') from None
        state = status.get('status') if isinstance(status,dict) else None
        if state=='done':
            return status
        if state=='error':
            raise RuntimeError('Kaggle 后台合成失败')
        if state!='running':
            raise RuntimeError('Kaggle 异步轮询返回未知状态')
    raise RuntimeError(f'Kaggle 异步任务超过 {timeout:g} 秒等待上限')


def _remote_batch(texts, brand, backend, temperature):
    """通过 HTTPS 直传 Base64 参考音频，严禁把 clone 请求改写为 R2。"""
    env_name = "MODAL_QWEN3_TTS_ENDPOINT_URL" if backend == "modal" else "KAGGLE_TTS_ENDPOINT_URL"
    endpoint = os.environ.get(env_name)
    if not endpoint:
        raise ValueError(f"{env_name} 未设置，无法使用 {backend} 配音后端")
    if urlsplit(endpoint).scheme != "https" or not urlsplit(endpoint).hostname:
        raise ValueError("克隆参考音频必须使用已配置的 HTTPS 端点")
    ref_audio, ref_text, language = _clone_reference(os.environ.get("YICE_VOICE_BRAND", brand))
    payload = {
        "text": texts,
        "mode": "clone",
        "language": language,
        "output_format": "wav",
        "ref_audio_base64": base64.b64encode(ref_audio.read_bytes()).decode("ascii"),
        "ref_text": ref_text,
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json", "User-Agent": "yice-youtube-video/7.0"}
    if backend == "kaggle" and os.environ.get("KAGGLE_TTS_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["KAGGLE_TTS_TOKEN"]
    sync_timeout = float(os.environ.get('YICE_TTS_TIMEOUT','300'))
    async_timeout = float(os.environ.get('YICE_TTS_TIMEOUT','900'))
    if not math.isfinite(async_timeout) or async_timeout<=0:
        raise ValueError('YICE_TTS_TIMEOUT 须为正的有限秒数')
    kaggle_base = endpoint.rstrip('/').removesuffix('/tts') if backend=='kaggle' else None

    def _post_subbatch(sub_texts):
        sub_payload = {**payload, "text": sub_texts}
        body_bytes = json.dumps(sub_payload).encode()
        if kaggle_base is not None:
            result = _kaggle_async_batch(kaggle_base,body_bytes,headers,async_timeout)
            if result is not None:
                return result
        sync_url = kaggle_base+'/tts' if kaggle_base is not None else endpoint
        last_exc = None
        for attempt in range(4):
            request = urllib.request.Request(sync_url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=sync_timeout) as response:
                    return json.loads(response.read().decode())
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                last_exc = exc
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
        status = getattr(last_exc, "code", type(last_exc).__name__)
        raise RuntimeError(f"{backend} 配音端点请求失败（{status}）") from None

    audio = []
    texts = [normalize_tts_text(text) for text in texts]
    for start_idx in range(0, len(texts), 4):
        sub_texts = texts[start_idx:start_idx + 4]
        result = _post_subbatch(sub_texts)
        outputs = result.get("outputs") if isinstance(result, dict) else None
        if not isinstance(outputs, list):
            item = result if isinstance(result, dict) and result.get("audio_base64") else None
            outputs = [item] if item else []
        if len(outputs) != len(sub_texts):
            raise RuntimeError(f"{backend} 配音返回 {len(outputs)} 段，预期 {len(sub_texts)} 段")
        for index, item in enumerate(outputs):
            encoded = item.get("audio_base64") if isinstance(item, dict) else None
            if not encoded:
                raise RuntimeError(f"{backend} 配音输出 {start_idx + index} 缺少 audio_base64")
            audio.append(base64.b64decode(encoded))
    return audio


def room_tone(source, rate, frames, seed=0, dbfs=-60.):
    """Repeat a quiet source window, or provide a deterministic low floor."""
    import numpy as np
    if not frames:
        return source[:0]
    tail = source[-min(len(source), round(.5*rate)):]
    window = max(1, min(len(tail), round(.06*rate)))
    windows = [tail[i:i+window] for i in range(0, len(tail)-window+1, window)]
    tone = min(windows, key=lambda segment: float(np.mean(segment**2))).copy()
    tone -= tone.mean(axis=0)
    rms = float(np.sqrt(np.mean(tone**2)))
    target = 10 ** (dbfs/20)
    shape = (frames, *source.shape[1:])
    if rms >= 10 ** (-72/20) and np.max(np.abs(tone)) <= 4*rms:
        tiled = np.resize(tone, shape)
        tiled_rms = float(np.sqrt(np.mean(tiled**2)))
        if tiled_rms > 0:
            gain = target/tiled_rms
            channels = tiled.reshape(frames, -1)
            quiet = np.max(np.abs(channels),axis=1) < 10 ** (-80/20)/min(1.,gain)
            tiled *= gain
            edges = np.flatnonzero(np.diff(np.r_[False,quiet,False]))
            block = max(1,min(frames,round(.010*rate)))
            energy = np.r_[0.,np.cumsum(np.mean(channels**2,axis=1),dtype=np.float64)]
            level = (energy[block:]-energy[:-block])/block
            if (not np.any(edges[1::2]-edges[::2]>.005*rate)
                    and np.all((level>=target**2*10**(-.3)) & (level<=target**2*10**.3))):
                return tiled
    noise = np.random.default_rng(seed).standard_normal(shape)
    # Bound the fallback's amplitude so short windows stay within 3 dB
    # after RMS normalization and cannot reintroduce sustained dead zones.
    noise = np.copysign(np.clip(np.abs(noise),.85,1.15),noise)
    return noise * (target/float(np.sqrt(np.mean(noise**2))))


def preserve_room_floor(samples, rate, dbfs):
    """Replace prolonged digital silence without changing sample counts."""
    import numpy as np
    if not len(samples):
        return samples
    quiet = np.max(np.abs(samples),axis=1) < 10 ** (-80/20)
    edges = np.flatnonzero(np.diff(np.r_[False,quiet,False]))
    for a,b in edges.reshape(-1,2):
        if b-a > round(.025*rate):
            samples[a:b] = room_tone(samples[a:b],rate,b-a,seed=int(a),dbfs=dbfs)
    return samples


def _read_wav_float32_2d(path):
    import numpy as np
    try:
        import soundfile as sf
        return sf.read(path, dtype="float32", always_2d=True)
    except ImportError:
        with wave.open(str(path), "rb") as wf:
            ch, sw, rate, nframes = wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
            raw = wf.readframes(nframes)
        if sw == 2:
            arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        elif sw == 3:
            b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            val = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int8).astype(np.int32) << 16)
            arr = val.astype(np.float32) / 8388608.0
        elif sw == 4:
            arr = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"不支持的 WAV 位深：{sw}")
        return arr.reshape(-1, ch), rate


def _write_wav_pcm24(target, samples, rate):
    import numpy as np
    try:
        import soundfile as sf
        sf.write(target, samples, rate, subtype="PCM_24")
    except ImportError:
        clipped = np.clip(samples, -1.0, 8388607.0 / 8388608.0)
        ints = np.round(clipped * 8388608.0).astype("<i4")
        raw = ints.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
        with wave.open(str(target), "wb") as wf:
            wf.setnchannels(samples.shape[1])
            wf.setsampwidth(3)
            wf.setframerate(int(rate))
            wf.writeframes(raw)


def _concat_wavs(paths, target, crossfade_ms=60, pauses=None, room_tone_dbfs=-68.):
    """用室温底噪连接长段，渐变衔接前导和尾音。"""
    import numpy as np

    if not paths:
        raise ValueError("没有可拼接的句组音频")
    if not math.isfinite(crossfade_ms) or crossfade_ms < 60 or not -80 < room_tone_dbfs <= -58:
        raise ValueError('拼接使用至少 60ms 淡化，室温底噪高于 -80 且至多 -58 dBFS')
    rendered = None
    original_rate = channels = None
    previous_tail = 0
    for index, path in enumerate(paths):
        samples, rate = _read_wav_float32_2d(path)
        if original_rate is None:
            original_rate, channels = rate, samples.shape[1]
        if original_rate != rate or channels != samples.shape[1] or not len(samples):
            raise ValueError("句组音频采样参数不一致或为空")
        samples = samples - np.mean(samples, axis=0, keepdims=True)
        level = np.max(np.abs(samples), axis=1)
        voiced = np.flatnonzero(level > 10 ** (-56 / 20))
        if not len(voiced):
            raise ValueError("句组音频全为静音")
        source_left = round(.025*rate) if voiced[0]>.05*rate else 0
        fade_frames = round(rate * crossfade_ms / 1000)
        pre_roll, post_roll = max(1,round(.110*rate)), max(1,round(.130*rate))
        left = max(source_left, voiced[0]-fade_frames-pre_roll) if index else source_left
        right = min(len(samples), voiced[-1]+1+fade_frames+post_roll) if index+1<len(paths) else len(samples)
        piece = samples[left:right].copy()
        preserve_room_floor(piece,rate,room_tone_dbfs)
        lead = int(voiced[0])-left
        tail_count = right-int(voiced[-1])-1
        if index and lead:
            head = piece[:lead]
            phase = np.clip(1 - (lead-np.arange(lead))/pre_roll,0.,1.)
            gain = ((1-np.cos(np.pi*phase))/2)[:,None]
            floor = room_tone(head,rate,lead,seed=index,dbfs=room_tone_dbfs)
            head[:] = head*gain + floor*(1-gain)
        if index+1<len(paths) and tail_count:
            tail = piece[-tail_count:]
            phase = np.clip((np.arange(tail_count)+1)/post_roll,0.,1.)
            gain = ((1+np.cos(np.pi*phase))/2)[:,None]
            floor = room_tone(tail,rate,tail_count,seed=index,dbfs=room_tone_dbfs)
            tail[:] = tail*gain + floor*(1-gain)
        if index+1<len(paths) and tail_count<fade_frames+post_roll:
            padding = fade_frames+post_roll-tail_count
            piece = np.concatenate((piece,room_tone(piece,rate,padding,seed=index,dbfs=room_tone_dbfs)))
            tail_count += padding
        if rendered is None:
            rendered = piece
            previous_tail = tail_count
            continue
        pause = float((pauses or {}).get(index, .12))
        if not math.isfinite(pause) or pause < 0:
            raise ValueError('段间留白须为非负有限秒数')
        missing_lead = max(0,fade_frames+pre_roll-lead)
        if missing_lead:
            piece = np.concatenate((room_tone(piece,rate,missing_lead,seed=index,dbfs=room_tone_dbfs),piece))
        fade = fade_frames
        tail_fade = min(fade_frames, len(rendered))
        remaining = round(pause*rate)
        if index in (pauses or {}):
            remaining = max(0, remaining-previous_tail-lead-missing_lead)
        frames = remaining + tail_fade + fade
        bridge = room_tone(rendered,rate,frames,seed=index,dbfs=room_tone_dbfs)
        previous_tail = tail_count
        down = (1-np.cos(np.linspace(0, np.pi, tail_fade)))[:, None] / 2
        bridge[:tail_fade] = rendered[-tail_fade:]*(1-down) + bridge[:tail_fade]*down
        if fade:
            up = (1-np.cos(np.linspace(0, np.pi, fade)))[:, None] / 2
            bridge[-fade:] = bridge[-fade:]*(1-up) + piece[:fade]*up
        rendered = np.concatenate((rendered[:-tail_fade], bridge, piece[fade:]))
    preserve_room_floor(rendered,original_rate,room_tone_dbfs)
    _write_wav_pcm24(target, rendered, original_rate)


def concat_wav_command(paths, output, pauses, crossfade_ms, room_tone_dbfs):
    if len(paths) < 2:
        raise ValueError('拼接至少需要两段已有 WAV')
    if output.resolve() in {path.resolve() for path in paths}:
        raise ValueError('输出路径须与原音不同')
    gaps = {}
    for item in pauses:
        boundary,seconds = item.split('=',1)
        at,gap = int(boundary),float(seconds)
        if not 1 <= at < len(paths) or at in gaps or not math.isfinite(gap) or gap < 0:
            raise ValueError('留白边界从 1 起，须唯一且位于相邻拼接段之间')
        gaps[at] = gap
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        staging = Path(tmp)/'concat.wav'
        _concat_wavs(paths,staging,crossfade_ms=crossfade_ms,pauses=gaps,room_tone_dbfs=room_tone_dbfs)
        staging.replace(output)
    return dict(ok=True,segments=len(paths),pauses=gaps,crossfade_ms=crossfade_ms,room_tone_dbfs=room_tone_dbfs)


def generate_modal_job(job, brand, backend="modal"):
    target = Path(job["path"])
    if target.is_file() and target.stat().st_size > 44 and (target.with_suffix(".chunks") / "chunks.json").is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = job.get('chunk_mode', 'long_paragraph')
    pronunciations = job.get("pronunciations") or {}
    if job.get("chunks"):
        chunks = [apply_pronunciations(c, pronunciations) for c in job["chunks"]]
    else:
        chunks = chapter_chunks(apply_pronunciations(job["text"], pronunciations), mode)
    temperatures = [0.65, 0.72, 0.78]
    temperature = temperatures[int(job.get("seed", 0)) % len(temperatures)]
    folder = target.with_suffix(".chunks")
    folder.mkdir(exist_ok=True)
    raw = []
    for index, data in enumerate(_remote_batch(chunks, brand, backend, temperature)):
        path = folder / f"chunk-{index:03}.wav"
        path.write_bytes(data)
        raw.append(path)
    pauses = {int(k): v for k, v in job.get("pauses", {}).items()}
    _concat_wavs(raw, target, pauses=pauses)
    write_json(folder / "chunks.json", dict(texts=chunks, pauses=pauses, temperature=temperature, backend=backend, chunk_mode=mode))
    if not target.is_file() or target.stat().st_size <= 44:
        raise RuntimeError(f"{backend} 未生成有效 WAV：{target}")


def generate_raw(chapters, output, brand, seeds=(42, 43), backend="local", candidates=3, chunk_mode='long_paragraph'):
    jobs = [dict(text=chapter["text"], pronunciations=chapter.get("pronunciations") or {},
                 seed=seed, chunk_mode=chunk_mode,
                 path=str(output / f"seed{seed}" / f"chapter-{chapter['id']}-raw.wav"))
            for chapter in chapters for seed in seeds]
    generate_jobs(jobs, brand, backend=backend, candidates=candidates)


def make_generator(brand, folder, reuse=None, backend="modal", candidates=3):
    import shutil
    folder = Path(folder)
    cached = json.loads(Path(reuse).read_text()) if reuse else []
    if not isinstance(cached, list):
        raise ValueError("候选缓存须为 text/seed/path/sha256/brand 记录列表")
    index = {}
    for item in cached:
        key = (item["text"], item["seed"])
        if key in index or item.get("brand") != brand:
            raise ValueError("候选缓存身份重复或品牌不匹配")
        index[key] = item
    def generate(jobs):
        folder.mkdir(parents=True, exist_ok=True)
        pending, reused = [], []
        for job in jobs:
            target = Path(job["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise ValueError(f"拒绝覆盖候选原音：{target}")
            previous = index.get((job["text"], job["seed"]))
            if previous:
                source = Path(previous["path"])
                if hashlib.sha256(source.read_bytes()).hexdigest() != previous["sha256"]:
                    raise ValueError("候选缓存哈希不匹配")
                shutil.copy2(source, target)
                chunk_dir = source.with_suffix(".chunks")
                if chunk_dir.is_dir():
                    shutil.copytree(chunk_dir, target.with_suffix(".chunks"))
                reused.append(dict(text=job["text"], seed=job["seed"], sha256=previous["sha256"], source=str(source), path=str(target)))
            else:
                pending.append(job)
        serial = len(list(folder.glob("jobs-*.json"))) + 1
        request = folder / f"jobs-{serial:03}.json"
        write_json(request, dict(generated=pending, reused=reused))
        if pending:
            worker_jobs = folder / f"worker-{serial:03}.json"
            write_json(worker_jobs, pending)
            python = (os.environ.get("YICE_TTS_PYTHON", str(TOOLKIT / "local/tts-venv/bin/python"))
                      if backend == "local" else sys.executable)
            env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
            with (folder / f"generation-{serial:03}.log").open("w") as log:
                subprocess.run([python, str(Path(__file__).resolve()), str(request), "--output", str(folder),
                                "--brand", brand, "--backend", backend, "--candidates", str(candidates),
                                "--generation-jobs", str(worker_jobs), *(["--allow-slow-local"] if backend == "local" else [])],
                               env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    return generate


def resolve_asr_model(explicit=None):
    configured = explicit or os.environ.get("YICE_ASR_MODEL")
    if configured:
        return os.path.expanduser(configured)
    local = Path.home() / "yice-demo/我的视频/models/Whisper-Large-v3-Turbo"
    if valid_whisper_directory(local):
        return str(local)
    return "mlx-community/whisper-large-v3-turbo"


def make_transcriber(model, prompt, folder):
    folder = Path(folder)
    def transcribe(audio):
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        sha = hashlib.sha256(Path(audio).read_bytes()).hexdigest()
        settings = hashlib.sha256(json.dumps(dict(model=model, prompt=prompt, temperature=0, chunk_v=9), sort_keys=True).encode()).hexdigest()[:12]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{sha}-{settings}.json"
        if path.exists():
            value = json.loads(path.read_text())
            if value["sha256"] != sha:
                raise ValueError("ASR 缓存不属于当前音频")
            return value["transcript"]
        import mlx_whisper
        y, sr = None, 0
        try:
            import numpy as np
            import soundfile as sf
            data, sr = sf.read(str(audio))
            y = data[:, 0] if data.ndim > 1 else data
        except Exception:
            y = None
        if y is None or sr <= 0 or len(y) / sr <= 26.0:
            result = mlx_whisper.transcribe(str(audio), path_or_hf_repo=model, language="zh",
                                           condition_on_previous_text=False,
                                           initial_prompt=prompt or None, temperature=0, word_timestamps=True, verbose=False)
        else:
            import tempfile
            hop, start, total = max(1, int(0.02 * sr)), 0, len(y)
            segments, texts = [], []
            while start < total:
                remaining = total - start
                if remaining / sr <= 25.0:
                    end = total
                else:
                    lo, hi = start + int(15.8 * sr), min(total - hop, start + int(18.8 * sr))
                    quiet = [float(np.sqrt(np.mean(y[p:p + hop] ** 2))) < 10 ** (-45 / 20) for p in range(lo, hi, hop)]
                    best_len, best_mid, run_start = 0, None, None
                    for idx, is_q in enumerate(quiet + [False]):
                        if is_q and run_start is None:
                            run_start = idx
                        elif not is_q and run_start is not None:
                            if idx - run_start > best_len:
                                best_len = idx - run_start
                                best_mid = lo + ((run_start + idx) * hop) // 2
                            run_start = None
                    if best_mid is not None and best_len >= 4:
                        end = best_mid
                    else:
                        rms = [float(np.sqrt(np.mean(y[p:p + hop * 2] ** 2))) for p in range(lo, hi, hop * 2)]
                        end = lo + int(np.argmin(rms)) * hop * 2 if rms else start + int(21.0 * sr)
                with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                    sf.write(tmp.name, y[start:end], sr)
                    chunk = mlx_whisper.transcribe(tmp.name, path_or_hf_repo=model, language="zh",
                                                  condition_on_previous_text=False,
                                                  initial_prompt=prompt or None, temperature=0, word_timestamps=True, verbose=False)
                off = start / sr
                texts.append(chunk.get("text", ""))
                for seg in chunk.get("segments", []):
                    words = [dict(w, start=w["start"] + off, end=w["end"] + off) for w in seg.get("words", [])]
                    segments.append(dict(seg, start=seg["start"] + off, end=seg["end"] + off, words=words))
                start = end
            result = dict(text="".join(texts), segments=segments)
        if y is not None and sr > 0 and isinstance(result.get("segments"), list):
            clean_segs, clean_texts = [], []
            sil_amp = 10 ** (-44 / 20)
            step = max(1, int(0.01 * sr))
            for seg in result["segments"]:
                words = seg.get("words") or []
                probs = [float(w.get("probability", 1.0)) for w in words]
                sa, sb = max(0, int(float(seg.get("start", 0.0)) * sr)), min(len(y), max(1, int(float(seg.get("end", 0.0)) * sr)))
                seg_rms = float(np.sqrt(np.mean(y[sa:sb] ** 2))) if sb > sa else 0.0
                if seg_rms < sil_amp and seg.get("avg_logprob", 0.0) < -1.2 and probs and max(probs) < 0.12:
                    continue
                trimmed = []
                p85 = float(np.percentile(np.abs(y[sa:sb]), 85)) if sb > sa else 0.0
                word_sil = max(10 ** (-38 / 20), p85 * (10 ** (-24 / 20)))
                for w in words:
                    ws, we = float(w["start"]), float(w["end"])
                    if we - ws > 0.14:
                        a, b = max(0, int(ws * sr)), min(len(y), int((we - 0.05) * sr))
                        while a + step < b and float(np.sqrt(np.mean(y[a:a + step] ** 2))) < word_sil:
                            a += step
                        ws = min(we - 0.05, a / sr)
                        lo_end, hi_end = max(0, int((ws + 0.05) * sr)), min(len(y), int(we * sr))
                        while hi_end - step > lo_end and float(np.sqrt(np.mean(y[hi_end - step:hi_end] ** 2))) < word_sil:
                            hi_end -= step
                        we = max(ws + 0.05, hi_end / sr)
                    trimmed.append({**w, "start": ws, "end": we})
                clean_segs.append({**seg, "words": trimmed})
                clean_texts.append(seg.get("text", ""))
            result = {**result, "text": "".join(clean_texts), "segments": clean_segs}
        write_json(path, dict(sha256=sha, model=model, prompt=prompt, transcript=result))
        return result
    return transcribe


def chars(text):
    return [(i, ch) for i, ch in enumerate(text) if ch.isalnum()]


def align_characters(text, transcription, duration, normalizations, *, auto_homophones=()):
    # T61 把 Whisper 词时间等分到字，再调用既有 align；不另写匹配/插值算法。
    sys.path.insert(0, str(TOOLKIT / "tools"))
    from captions import align
    heard = []
    for segment in transcription["segments"]:
        for word in segment.get("words", []):
            letters = [ch for _, ch in chars(word["word"])]
            for i, ch in enumerate(letters):
                heard.append({"w": ch, "s": word["start"] + (word["end"] - word["start"]) * i / len(letters),
                              "e": word["start"] + (word["end"] - word["start"]) * (i + 1) / len(letters)})
    if not heard:
        raise ValueError("Whisper 没有可对齐的字级时间；原音保留，未输出虚构时间轴")
    # 配置键为原稿、值为 ASR 别写，与 T61 审查记录一致。
    for intended, recognized in sorted(normalizations.items(), key=lambda pair: -len(pair[1])):
        old, new = "".join(ch for _, ch in chars(recognized)), "".join(ch for _, ch in chars(intended))
        if not old or not new:
            raise ValueError("归一化短语不能只含标点")
        start = 0
        while (at := "".join(h["w"] for h in heard).find(old, start)) >= 0:
            lo, hi = heard[at]["s"], heard[at + len(old) - 1]["e"]
            heard[at:at + len(old)] = [{"w": ch, "s": lo + (hi - lo) * i / len(new),
                                      "e": lo + (hi - lo) * (i + 1) / len(new)} for i, ch in enumerate(new)]
            start = at + len(new)
    for row in auto_homophones:
        start = row['heard_start']
        for item, wanted in zip(heard[start:start+len(row['heard'])], row['intended']):
            item['w'] = wanted
    positions = chars(text)
    # captions.norm 原生只保留 ASCII。Unicode 编码适配使中文参与同一套匹配算法。
    token = lambda ch: format(ord(ch.lower()), "x")
    aligned, ratio = align([token(ch) for _, ch in positions],
                           [{**h, "w": token(h["w"])} for h in heard])
    mapped, previous, clamps = [], 0, 0
    for (index, _), word in zip(positions, aligned):
        start = min(duration, max(previous, word["s"]))
        end = min(duration, max(start, word["e"]))
        clamps += int(start != word["s"] or end != word["e"])
        mapped.append({"charStart": index, "charEnd": index + 1, "s": start, "e": end})
        previous = end
    return mapped, ratio, clamps


def align_with_audit(text, transcription, duration, audit):
    positional = [item for item in audit.get('auto_homophone', []) if 'heard_start' in item]
    kwargs = {'auto_homophones': positional} if positional else {}
    return align_characters(text, transcription, duration, audit['normalizations'], **kwargs)


def ranges(text, pattern):
    return [(m.start(), m.end(), m.group().strip()) for m in re.finditer(pattern, text) if chars(m.group())]


def short_captions(chapter, mapped, offset):
    captions = []
    clauses = r'[^，,。！？!?；;：:、]+[，,。！？!?；;：:、]*'
    break_words = ('所以','因为','然后','接着','这样','以及','但是','同时','或者','而且','直接','放一','有四','在','和','把','用','往','从')
    for scene, first, end in scene_text_spans(chapter):
        for a,b,_ in ranges(scene['text'],clauses):
            text = chapter['text']
            letters = [m for m in mapped if first+a <= m['charStart'] < min(end,first+b)]
            while letters:
                full_label = text[letters[0]['charStart']:letters[-1]['charEnd']].strip()
                if len(letters) <= 22 and len(full_label) <= 22:
                    count = len(letters)
                else:
                    upper = min(22, len(letters) - 6) if len(letters) <= 28 else 20
                    upper = max(8, upper)
                    while upper > 8 and len(text[letters[0]['charStart']:letters[upper-1]['charEnd']].strip()) > 22:
                        upper -= 1
                    lower = max(7, min(upper - 1, len(letters) - 18))
                    count = upper
                    for cut in range(upper, lower - 1, -1):
                        i,j = letters[cut-1]['charEnd'],letters[cut]['charStart']
                        if text[i:j] or any(text[j:].startswith(word) for word in break_words):
                            count = cut
                            break
                    else:
                        def ascii_letter(index):
                            char = text[letters[index]['charStart']]
                            return char.isascii() and char.isalnum()
                        while count > lower and ascii_letter(count-1) and ascii_letter(count):
                            count -= 1
                        if ascii_letter(count-1) and ascii_letter(count):
                            count = upper
                window,letters = letters[:count],letters[count:]
                label = text[window[0]['charStart']:window[-1]['charEnd']].strip()
                start = round((offset+window[0]['s'])*1000)
                end_ms = round((offset+window[-1]['e'])*1000)
                if label and end_ms>start:
                    captions.append(dict(text=label,startMs=start,endMs=end_ms))
    return captions


def prepare_chapter(chapter, raw_path, output, transcription, normalizations, silence, offset, anchors, aligned=None):
    with wave.open(str(raw_path), "rb") as source:
        params, pcm = source.getparams(), source.readframes(source.getnframes())
    rate, stride = params.framerate, params.nchannels * params.sampwidth
    duration = params.nframes / rate
    if aligned is None:
        mapped, ratio, clamps = align_characters(chapter["text"], transcription, duration, normalizations)
    else:
        mapped = aligned["mapped"]
        ratio, clamps = aligned.get("matched_ratio", 1.), aligned.get("monotonic_clamps", 0)
    scenes = []
    for scene, cursor, end in scene_text_spans(chapter):
        positions = [m for m in mapped if cursor <= m["charStart"] < end]
        if not positions:
            raise ValueError(f"幕 {scene['id']} 没有口播文字")
        scenes.append({**scene, "chars": positions, "char_start": cursor})
    cuts = [0] + [round((a["chars"][-1]["e"] + b["chars"][0]["s"]) / 2 * rate)
                  for a, b in zip(scenes, scenes[1:])] + [params.nframes]
    gap = round(silence * rate)
    chunks, segments, timing, scene_timing, captions = [], [], [], [], []
    output_mapped = []
    for i, scene in enumerate(scenes):
        lo, hi = cuts[i], cuts[i + 1]
        chunks.extend([b"\0" * gap * stride, pcm[lo * stride:hi * stride]])
        added = (i + 1) * gap / rate
        output_mapped.extend({**row, "s": row["s"] + added, "e": row["e"] + added}
                             for row in scene["chars"])
        start, end = offset + lo / rate + i * gap / rate, offset + hi / rate + added
        first = offset + scene["chars"][0]["s"] + added
        segments.append({"id": scene["id"], "source_start_sample": lo, "source_end_sample": hi,
                         "output_start_sample": lo + (i + 1) * gap,
                         "output_end_sample": hi + (i + 1) * gap, "silence_before_samples": gap})
        parts = ranges(scene["text"], r"[^。！？!?]+[。！？!?]*")
        sentence_ids = []
        prior_end = start
        for j, (a, b, text) in enumerate(parts):
            inside = [m for m in scene["chars"] if a <= m["charStart"] - scene["char_start"] < b]
            first_time, last_time = offset + inside[0]["s"] + added, offset + inside[-1]["e"] + added
            sent_end = end
            if j + 1 < len(parts):
                next_at = parts[j + 1][0] + scene["char_start"]
                next_char = next(m for m in scene["chars"] if m["charStart"] >= next_at)
                sent_end = offset + (inside[-1]["e"] + next_char["s"]) / 2 + added
            sid = scene["id"] if len(parts) == 1 else f"{scene['id']}.{j + 1}"
            found = []
            for request in anchors:
                if request["scene"] != scene["id"]:
                    continue
                phrase = request.get("spoken_phrase", request["phrase"])
                for match in re.finditer(re.escape(phrase), scene["text"]):
                    if a <= match.start() < b:
                        pos = scene["char_start"] + match.start()
                        point = next((m for m in inside if m["charStart"] >= pos), None)
                        if point:
                            found.append({"phrase": request["phrase"], "time": round(offset + point["s"] + added, 5)})
            timing.append({"id": sid, "text": text, "start": round(prior_end, 5), "end": round(sent_end, 5),
                           "firstCharTime": round(first_time, 5), "anchors": found})
            sentence_ids.append(sid)
            prior_end = sent_end
        # T61 在标点处分字幕，保留中文原稿，不把字之间加空格。
        clauses = ranges(scene["text"], r"[^，,。！？!?；;：:]+[，,。！？!?；;：:]*")
        for a, b, text in clauses:
            inside = [m for m in scene["chars"] if a <= m["charStart"] - scene["char_start"] < b]
            captions.append({"text": text, "startMs": round((offset + inside[0]["s"] + added) * 1000),
                             "endMs": round((offset + inside[-1]["e"] + added) * 1000)})
        scene_timing.append({"id": scene["id"], "chapter": chapter["id"], "start": round(start, 5),
                             "end": round(end, 5), "firstCharTime": round(first, 5), "sentences": sentence_ids})
    final = output / f"chapter-{chapter['id']}.wav"
    with wave.open(str(final), "wb") as target:
        target.setparams(params)
        target.writeframes(b"".join(chunks))
    final_duration = (params.nframes + len(scenes) * gap) / rate
    record = {"id": chapter["id"], "path": final.name, "audio": final.name,
              "start": round(offset, 5), "end": round(offset + final_duration, 5),
              "duration": round(final_duration, 5), "original_duration": round(duration, 5),
              "added_boundary_silence": round(len(scenes) * gap / rate, 5), "scenes": [s["id"] for s in scenes],
              "sha256": hashlib.sha256(final.read_bytes()).hexdigest()}
    analysis = {"chapter": chapter["id"], "text": chapter["text"], "mapped": mapped,
                "matched_ratio": ratio, "monotonic_clamps": clamps, "normalizations": normalizations,
                "sample_rate": rate, "segments": segments, "raw_pcm_preserved": True,
                "output_mapped": output_mapped}
    return record, timing, scene_timing, captions, analysis


def load_voice_tool(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def finish_chapter(chapter, raw, output, transcription, normalizations, silence, offset, anchors,
                   *, skip_post=False, post_options=None, asr_threshold=.97, profile='legacy'):
    """Generate final timing and reject content/prosody failures before export."""
    check_tool = load_voice_tool("voice-check")
    quality = load_voice_tool("voice-quality")
    natural = profile == 'natural_v7'
    audit = quality.audit(chapter["text"], transcription, normalizations, asr_threshold, auto_homophone=natural)
    with wave.open(str(raw), "rb") as source:
        original_duration = source.getnframes() / source.getframerate()
    mapped, ratio, clamps = align_with_audit(chapter["text"], transcription, original_duration, audit)
    audit["alignment_ratio"] = ratio
    audit["ok"] = audit["ok"] and ratio >= asr_threshold
    write_json(output / "analysis" / f"asr-audit-{chapter['id']}.json", audit)
    aligned = dict(text=chapter["text"], mapped=mapped, matched_ratio=ratio, monotonic_clamps=clamps,
                   planned_pauses=chapter.get("planned_pauses", {}))
    audio = raw
    options = dict(post_options or {})
    master = options.pop("cloud_master", False)
    if master or natural:
        silence = 0
    if not skip_post:
        post_tool = load_voice_tool("voice-post")
        boundaries = []
        for _, cursor, end in list(scene_text_spans(chapter))[:-1]:
            boundaries.append(max(row["charEnd"] for row in mapped if cursor <= row["charStart"] < end))
        processed = output / "processed"
        processed.mkdir(exist_ok=True)
        audio = processed / f"chapter-{chapter['id']}.wav"
        if natural:
            aligned = post_tool.postprocess(raw, aligned, audio, preserve_natural_breath=True,
                                            thresholds=check_tool.thresholds_for(profile), **options)
        elif master:
            # Calibrate once on the original PCM; keep all word-internal issues for a cloud redraw.
            semantic = processed / f"semantic-{chapter['id']}.wav"
            aligned, _ = post_tool.regularize(raw, aligned, semantic, semantic.with_suffix(".npz"), fade_ms=15)
            post_tool.normalize_lufs(semantic, audio, options.get("lufs", -16.))
        else:
            aligned = post_tool.postprocess(raw, aligned, audio, scene_boundaries=boundaries,
                                            scene_padding=silence, **options)
    write_json(output / "analysis" / f"post-alignment-{chapter['id']}.json", aligned)
    record, timing, scenes, captions, analysis = prepare_chapter(
        chapter, audio, output, transcription, audit["normalizations"], silence, offset, anchors, aligned=aligned)
    padding = record["added_boundary_silence"]
    final_alignment = dict(text=chapter["text"], mapped=analysis["output_mapped"], matched_ratio=ratio,
                           planned_pauses=chapter.get("planned_pauses", {}))
    if not skip_post and not master and not natural:
        # Close pauses against the ACTUAL padded waveform; never add padding twice.
        current = output / record["path"]
        final_edits = []
        # ``regularize`` closes all measured semantic pauses in one pass. A
        # second pass re-measures the same lexical boundary as zero-length and
        # inserts the target pause again, duplicating silence on short chunks.
        for attempt in range(1):
            destination = output / "analysis" / f"final-semantic-{chapter['id']}-{attempt}.wav"
            final_alignment, edits = post_tool.regularize(
                current, final_alignment, destination, destination.with_suffix(".npz"))
            final_edits.extend(edits)
            current = destination
            if not edits:
                break
        normalized = output / "analysis" / f"final-normalized-{chapter['id']}.wav"
        levels = post_tool.normalize_lufs(current, normalized, options.get("lufs", -16.))
        record, timing, scenes, captions, analysis = prepare_chapter(
            chapter, normalized, output, {}, audit["normalizations"], 0, offset, anchors, aligned=final_alignment)
        record.update(loudness=levels, added_boundary_silence=padding,
                      final_semantic_pause_edits=final_edits, retiming_additional_silence=0)
        final_alignment = dict(text=chapter["text"], mapped=analysis["output_mapped"], matched_ratio=ratio,
                           planned_pauses=chapter.get("planned_pauses", {}))
    write_json(output / "analysis" / f"final-alignment-{chapter['id']}.json", final_alignment)
    check = check_tool.check_chapter(output / record["path"] , final_alignment, chapter=chapter["id"],
                                    cache=output / "analysis" / f"voice-check-{chapter['id']}.npz", profile=profile)
    check.update(prosody_ok=check["ok"], asr=audit, ok=check["ok"] and audit["ok"])
    write_json(output / "analysis" / f"voice-check-{chapter['id']}.json", check)
    record.update(generated_duration=original_duration, postprocessing=not skip_post,
                  prosody_alert_count=len(check["alerts"]), asr_matched_ratio=audit["ratio"], asr_passed=audit["ok"])
    return record, timing, scenes, captions, analysis, check


def main():
    import shutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('script',type=Path,nargs='?')
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument('--concat-wavs',type=Path,nargs='+')
    parser.add_argument('--pause',action='append',default=[],help='拼接边界序号=留白秒数，例如 1=3.0')
    parser.add_argument('--crossfade-ms',type=float,default=60.)
    parser.add_argument('--room-tone-dbfs',type=float,default=-68.)
    parser.add_argument("--brand", default="yice")
    parser.add_argument("--anchors", type=Path)
    parser.add_argument("--normalizations", type=Path, help="分类的 ASR 例外：number_unit/english_name/homophone")
    parser.add_argument("--silence", type=float, default=.2)
    parser.add_argument("--asr-model")
    parser.add_argument("--asr-prompt", default="", help="领域词表；不要提供完整台词诱导识别")
    parser.add_argument("--asr-threshold", type=float, default=.97)
    parser.add_argument("--seeds")
    parser.add_argument("--stage", choices=["draft", "master"], default="master")
    parser.add_argument("--backend", choices=["auto", "modal", "kaggle", "local"], default="auto")
    parser.add_argument('--chunk-mode', choices=CHUNK_MODES, default='long_paragraph')
    parser.add_argument('--profile', choices=('natural_v7', 'legacy'), default='natural_v7')
    parser.add_argument("--allow-slow-local", action="store_true")
    parser.add_argument("--candidates", type=int, default=3,
                        help="每个语义句组的温度候选数，默认3")
    parser.add_argument("--chapters", help="只处理指定章号，如 00,01")
    parser.add_argument("--pause-after", action="append", help="在完整句组后留停顿，如 0-3=3.0")
    parser.add_argument("--reuse-candidates", type=Path, help="显式哈希候选缓存；复跑时保留原始生成证据")
    parser.add_argument("--max-repair-rounds", type=int, default=3)
    parser.add_argument("--generation-jobs", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--generate-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--skip-post", action="store_true", help="保留原音；ASR/韵律仍必须通过")
    parser.add_argument("--speed", type=float, default=1.)
    parser.add_argument("--breath-db", type=float, default=-12.)
    parser.add_argument("--breath-cut-ms", type=float, default=250.)
    parser.add_argument("--breath-target-ms", type=float, default=150.)
    parser.add_argument("--fade-ms", type=float, default=10.)
    parser.add_argument("--lufs", type=float, default=-16.)
    args = parser.parse_args()
    if args.concat_wavs:
        if args.script:
            parser.error('拼接现有 WAV 与从旁白稿生成是两种入口')
        try:
            report = concat_wav_command(args.concat_wavs,args.output,args.pause,args.crossfade_ms,args.room_tone_dbfs)
        except (ValueError,OSError,RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps(report,ensure_ascii=False))
        return
    if args.script is None and not args.generation_jobs:
        parser.error('请提供旁白稿，或使用 --concat-wavs 拼接现有原音')
    quality = load_voice_tool("voice-quality")
    try:
        args.backend = resolve_backend(args.stage, args.backend, args.allow_slow_local)
        seeds = quality.seeds(args.seeds if args.seeds is not None else ('42,43' if args.profile=='legacy' else '42'))
    except ValueError as exc:
        parser.error(str(exc))
    if (not 0 <= args.silence <= 2 or not 0 < args.asr_threshold <= 1 or
            not 0 <= args.max_repair_rounds <= 3 or not 1 <= args.candidates <= 8):
        parser.error("换幕静音须为0–2秒，ASR阈值须为(0,1]，修复轮数须为0–3，候选数须为1–8")
    if args.generation_jobs:
        jobs = json.loads(args.generation_jobs.read_text())
        for job in jobs:
            job.setdefault('chunk_mode', args.chunk_mode)
        generate_jobs(jobs, args.brand, backend=args.backend, candidates=args.candidates)
        return
    chapters, output = parse_script(args.script), args.output.resolve()
    if args.chapters:
        requested = set(args.chapters.split(","))
        if requested - {chapter["id"] for chapter in chapters}:
            parser.error("存在未知章号")
        chapters = [chapter for chapter in chapters if chapter["id"] in requested]
    if args.generate_only:
        generate_raw(chapters, output / "raw", args.brand, seeds, backend=args.backend,
                     candidates=args.candidates, chunk_mode=args.chunk_mode)
        return
    if output.exists() and any(output.iterdir()):
        parser.error(f"输出目录不是空目录，拒绝覆盖：{output}")
    anchors_path = args.anchors or args.script.parent / "anchors.json"
    anchors = json.loads(anchors_path.read_text()) if anchors_path.exists() else []
    normalization = json.loads(args.normalizations.read_text()) if args.normalizations else {}
    known = {scene["id"]: scene["text"] for chapter in chapters for scene in chapter["scenes"]}
    if args.chapters:
        anchors = [anchor for anchor in anchors if anchor["scene"] in known]
    for anchor in anchors:
        phrase = anchor.get("spoken_phrase", anchor["phrase"])
        if anchor["scene"] not in known or phrase not in known[anchor["scene"]]:
            parser.error(f"锚点必须有对应原稿；画面别名用 spoken_phrase：{anchor}")
    (output / "raw").mkdir(parents=True, exist_ok=True)
    (output / "analysis").mkdir()
    write_json(output / "analysis/script-manifest.json", {"chapters": chapters})
    generate = make_generator(args.brand, output / "generation", args.reuse_candidates, args.backend, args.candidates)
    asr_cache = Path(os.environ["YICE_ASR_CACHE_DIR"]) if os.environ.get("YICE_ASR_CACHE_DIR") else (output / "analysis/asr")
    transcribe = make_transcriber(resolve_asr_model(args.asr_model), args.asr_prompt, asr_cache)
    jobs = [dict(chapter=chapter["id"], text=chapter["text"], pronunciations=chapter.get("pronunciations") or {},
                 seed=seed, chunk_mode=args.chunk_mode,
                 path=str(output / "raw" / f"seed{seed}" / f"chapter-{chapter['id']}-raw.wav"))
            for chapter in chapters for seed in seeds]
    if args.pause_after:
        pauses = dict(value.rsplit("=", 1) for value in args.pause_after)
        if set(pauses) - set(known):
            parser.error("停顿幕号必须出现在所选章中")
        for chapter in chapters:
            planned = {}
            for scene, cursor, _ in scene_text_spans(chapter):
                if scene["id"] in pauses:
                    end = max(i + 1 for i, char in enumerate(scene["text"]) if char.isalnum())
                    planned[str(cursor + end)] = float(pauses[scene["id"]])
            chapter["planned_pauses"] = planned
        for job in jobs:
            chapter = next(c for c in chapters if c["id"] == job["chapter"])
            sections, buffer, gaps = [], [], {}
            for scene in chapter["scenes"]:
                buffer.append(scene["text"])
                if scene["id"] in pauses:
                    sections.extend(chapter_chunks(normalize_tts_text(" ".join(buffer)), args.chunk_mode))
                    buffer = []
                    gaps[len(sections)] = float(pauses[scene["id"]])
            if buffer:
                sections.extend(chapter_chunks(normalize_tts_text(" ".join(buffer)), args.chunk_mode))
            job.update(chunks=sections, pauses=gaps)
    generate(jobs)
    flow = load_voice_tool("voice-repair")
    records, timings, scenes, subtitles, compact_subtitles, offset = [], [], [], [], [], 0
    failed = []
    for chapter in chapters:
        chapter_exceptions = normalization
        if chapter.get("pronunciations"):
            if any(k in {"number_unit", "english_name", "homophone"} for k in normalization):
                chapter_exceptions = {k: dict(v) for k, v in normalization.items()}
                chapter_exceptions.setdefault("homophone", {})
                for surface, reading in chapter["pronunciations"].items():
                    chapter_exceptions["homophone"].setdefault(surface, reading)
            else:
                chapter_exceptions = dict(normalization)
                for surface, reading in chapter["pronunciations"].items():
                    chapter_exceptions.setdefault(surface, reading)
        result = flow.process_chapter(chapter, [job for job in jobs if job["chapter"] == chapter["id"]],
            output / "candidates" / chapter["id"], generate, transcribe, exceptions=chapter_exceptions,
            threshold=args.asr_threshold, silence=args.silence, offset=offset, anchors=anchors,
            skip_post=args.skip_post, max_rounds=args.max_repair_rounds,
            profile=args.profile,
            cloud_backend=args.backend if args.backend != "local" else None, brand=args.brand, post_options=dict(
                cloud_master=args.stage == "master" and args.backend in {"modal", "kaggle"} and args.speed == 1.,
                speed=args.speed, breath_db=args.breath_db, breath_cut_ms=args.breath_cut_ms,
                breath_target_ms=args.breath_target_ms, fade_ms=args.fade_ms, lufs=args.lufs))
        record = result["record"]
        if not result["check"]["ok"] or not result["asr"]["ok"]:
            failed.append(chapter["id"])
        target = output / f"chapter-{chapter['id']}.wav"
        shutil.copy2(result["audio"], target)
        record.update(path=target.name, audio=target.name, sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                      repair_rounds=result.get("repair_rounds", []))
        for name, value in [("aligned-characters", result["analysis"]), ("final-alignment", result["alignment"]),
                            ("voice-check", result["check"]), ("asr-audit", result["asr"])]:
            write_json(output / "analysis" / f"{name}-{chapter['id']}.json", value)
        write_json(output / f"voice-check-{chapter['id']}.json", result["check"])
        write_json(output / f"voice-timing-{chapter['id']}.json", result["timing"])
        records.append(record)
        timings.extend(result["timing"]); scenes.extend(result["scenes"]); subtitles.extend(result["captions"])
        compact_subtitles.extend(short_captions(chapter,result["analysis"]["output_mapped"],offset))
        offset = record["end"]
    if failed:
        write_json(output / "analysis/failures.json", dict(chapters=failed, max_repair_rounds=args.max_repair_rounds))
        raise SystemExit("ASR/配音检测未通过，最多修复3轮后停止组装：" + ", ".join(failed))
    sys.path.insert(0, str(TOOLKIT / "tools"))
    from captions import export_subtitles
    (output / "voice.srt").write_text(export_subtitles(subtitles, max_words=1))
    write_json(output / "captions.json", compact_subtitles)
    write_json(output / "voice-timing.json", timings)
    manifest = {"version": 1, "backend": args.backend, "stage": args.stage, "speed": args.speed, "time_unit": "seconds", "time_origin": "whole_episode",
                "total_duration": offset, "chapters": records, "scene_timing": scenes,
                "scene_count": len(scenes), "sentence_count": len(timings), "subtitle_count": len(subtitles),
                "anchor_count": sum(len(t["anchors"]) for t in timings),
                "raw_voice_duration": round(sum(record["generated_duration"] for record in records), 5),
                "boundary_silence_duration": round(sum(record["added_boundary_silence"] for record in records), 5),
                "source_script_sha256": hashlib.sha256(args.script.read_bytes()).hexdigest(),
                "postprocessing": not args.skip_post, "prosody_check": "passed", "asr_check": "passed",
                "seeds": seeds, "chunk_mode": args.chunk_mode, "profile": args.profile,
                "asr_threshold": args.asr_threshold, "max_repair_rounds": args.max_repair_rounds,
                "alignment_note": "最终波形经LUFS归一化、整章ASR和韵律复扫；整句修复后重算字时间、字幕和锚点。"}
    write_json(output / "voice-manifest.json", manifest)
    print(json.dumps({"output": str(output), "duration": offset, "chapters": len(records),
                      "sentences": len(timings), "anchors": manifest["anchor_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
