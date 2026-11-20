#!/usr/bin/env python3
"""T61 的章级 MLX 配音、Whisper 字级估计、captions.align 和换幕静音封装。"""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import wave
from pathlib import Path

from workspace import load_environment

WORKSPACE, TOOLKIT = load_environment()


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def spoken(text):
    return re.sub(r"\s+", " ", re.sub(r"〔[^〕]*〕", "", text).replace("**", "").replace("`", "")).strip()


def parse_script(path):
    chapters, chapter, seen = [], None, set()
    for line in Path(path).read_text().splitlines():
        heading = re.match(r"^##\s+(\d{2}[a-z]?)\s*(.*)", line)
        if heading:
            chapter = {"id": heading[1], "title": heading[2].strip(), "scenes": []}
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
        chapter["scenes"].append({"id": sid, "text": text})
    chapters = [c for c in chapters if c["scenes"]]
    if not chapters:
        raise ValueError("未找到 script-v2 格式的章标题和旁白表格")
    for chapter in chapters:
        chapter["text"] = " ".join(s["text"] for s in chapter["scenes"])
    return chapters


def generate_jobs(jobs, brand, backend="modal", candidates=3):
    if backend in {"modal", "kaggle"}:
        for job in jobs:
            generate_modal_job(job, brand, backend)
        return
    import random
    sys.path[:0] = [str(TOOLKIT / "local/tools"), str(TOOLKIT / "tools")]
    from local_voiceover import MLXBackend, load_clone
    backend = MLXBackend("8bit", load_clone(brand))
    for job in jobs:
        target = Path(job["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"拒绝覆盖已有原音：{target}")
        backend.mx.random.seed(job["seed"])
        random.seed(job["seed"])
        backend.generate(text=job["text"], model=backend.model,
                         ref_audio=backend.clone["audio"], ref_text=backend.clone["text"],
                         lang_code=backend.clone["language"], stt_model=None,
                         output_path=str(target.parent), file_prefix=target.stem,
                         audio_format="wav", join_audio=True, verbose=False,
                         max_tokens=4096, split_pattern="")
        if not target.is_file() or target.stat().st_size <= 44:
            raise RuntimeError(f"MLX 未生成有效 WAV：{target}")


def semantic_chunks(text, minimum=3, maximum=5, min_chars=60, max_chars=120):
    """按句末标点切成适合 TTS 的语义组，保留原文顺序。"""
    sentences = [part.strip() for part in re.findall(r"[^。！？!?]+[。！？!?]*", text) if part.strip()]
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
        chunks[-2] += chunks.pop()
    return chunks or [text]


def _clone_reference(brand):
    config = TOOLKIT / "brands" / brand / "voice.json"
    if not config.is_file():
        raise ValueError(f"缺少声音配置：{config}")
    data = json.loads(config.read_text())
    qwen = data.get("qwen3", {})
    clone = qwen.get("clone", {})
    ref = Path(clone.get("refAudio", ""))
    if not ref.is_absolute():
        ref = TOOLKIT / ref
    if not ref.is_file():
        raise ValueError(f"缺少声音参考音频：{ref}")
    return ref, clone.get("refText", ""), qwen.get("language", "Chinese")


def _remote_batch(texts, brand, backend, temperature):
    """通过 HTTPS 直传 Base64 参考音频，严禁把 clone 请求改写为 R2。"""
    env_name = "MODAL_QWEN3_TTS_ENDPOINT_URL" if backend == "modal" else "KAGGLE_TTS_ENDPOINT_URL"
    endpoint = os.environ.get(env_name)
    if not endpoint:
        raise ValueError(f"{env_name} 未设置，无法使用 {backend} 配音后端")
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
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=int(os.environ.get("YICE_TTS_TIMEOUT", "900"))) as response:
            result = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"{backend} 配音端点请求失败：{exc}") from exc
    outputs = result.get("outputs") if isinstance(result, dict) else None
    if not isinstance(outputs, list):
        item = result if isinstance(result, dict) and result.get("audio_base64") else None
        outputs = [item] if item else []
    if len(outputs) != len(texts):
        raise RuntimeError(f"{backend} 配音返回 {len(outputs)} 段，预期 {len(texts)} 段")
    audio = []
    for index, item in enumerate(outputs):
        encoded = item.get("audio_base64") if isinstance(item, dict) else None
        if not encoded:
            raise RuntimeError(f"{backend} 配音输出 {index} 缺少 audio_base64")
        audio.append(base64.b64decode(encoded))
    return audio


def _concat_wavs(paths, target, crossfade_ms=10):
    """拼接同采样率 WAV，句组边界做 10ms 交叉淡化。"""
    if not paths:
        raise ValueError("没有可拼接的句组音频")
    segments = []
    params = None
    for path in paths:
        with wave.open(str(path), "rb") as source:
            current = source.getparams()
            if params is None:
                params = current
            if (current.nchannels, current.sampwidth, current.framerate) != (params.nchannels, params.sampwidth, params.framerate):
                raise ValueError("句组音频采样参数不一致")
            segments.append(source.readframes(source.getnframes()))
    width = params.sampwidth
    if width != 2:
        with wave.open(str(target), "wb") as output:
            output.setparams(params)
            output.writeframes(b"".join(segments))
        return
    import array
    merged = array.array("h")
    overlap = max(0, round(params.framerate * crossfade_ms / 1000))
    for raw in segments:
        current = array.array("h")
        current.frombytes(raw)
        if not merged:
            merged.extend(current)
            continue
        n = min(overlap, len(merged), len(current))
        for i in range(n):
            a = (n - i) / n
            b = i / n
            merged[len(merged) - n + i] = max(-32768, min(32767, round(merged[len(merged) - n + i] * a + current[i] * b)))
        merged.extend(current[n:])
    with wave.open(str(target), "wb") as output:
        output.setparams(params)
        output.writeframes(merged.tobytes())


def generate_modal_job(job, brand, backend="modal"):
    target = Path(job["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    chunks = semantic_chunks(job["text"])
    temperatures = [0.65, 0.72, 0.78]
    temperature = temperatures[int(job.get("seed", 0)) % len(temperatures)]
    with tempfile.TemporaryDirectory(prefix="yice-tts-") as temporary:
        raw = []
        for index, data in enumerate(_remote_batch(chunks, brand, backend, temperature)):
            path = Path(temporary) / f"chunk-{index:03}.wav"
            path.write_bytes(data)
            raw.append(path)
        _concat_wavs(raw, target)
    if not target.is_file() or target.stat().st_size <= 44:
        raise RuntimeError(f"{backend} 未生成有效 WAV：{target}")


def generate_raw(chapters, output, brand, seeds=(42, 43), backend="local", candidates=3):
    jobs = [dict(text=chapter["text"], seed=seed,
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
                reused.append(dict(text=job["text"], seed=job["seed"], sha256=previous["sha256"], source=str(source), path=str(target)))
            else:
                pending.append(job)
        serial = len(list(folder.glob("jobs-*.json"))) + 1
        request = folder / f"jobs-{serial:03}.json"
        write_json(request, dict(generated=pending, reused=reused))
        if pending:
            worker_jobs = folder / f"worker-{serial:03}.json"
            write_json(worker_jobs, pending)
            python = os.environ.get("YICE_TTS_PYTHON", str(TOOLKIT / "local/tts-venv/bin/python"))
            env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
            with (folder / f"generation-{serial:03}.log").open("w") as log:
                subprocess.run([python, str(Path(__file__).resolve()), str(request), "--output", str(folder),
                                "--brand", brand, "--backend", backend, "--candidates", str(candidates),
                                "--generation-jobs", str(worker_jobs)],
                               env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    return generate


def make_transcriber(model, prompt, folder):
    folder = Path(folder)
    def transcribe(audio):
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        sha = hashlib.sha256(Path(audio).read_bytes()).hexdigest()
        settings = hashlib.sha256(json.dumps(dict(model=model, prompt=prompt, temperature=0), sort_keys=True).encode()).hexdigest()[:12]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{sha}-{settings}.json"
        if path.exists():
            value = json.loads(path.read_text())
            if value["sha256"] != sha:
                raise ValueError("ASR 缓存不属于当前音频")
            return value["transcript"]
        import mlx_whisper
        result = mlx_whisper.transcribe(str(audio), path_or_hf_repo=model, language="zh",
                                       initial_prompt=prompt or None, temperature=0, word_timestamps=True, verbose=False)
        write_json(path, dict(sha256=sha, model=model, prompt=prompt, transcript=result))
        return result
    return transcribe


def chars(text):
    return [(i, ch) for i, ch in enumerate(text) if ch.isalnum()]


def align_characters(text, transcription, duration, normalizations):
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


def ranges(text, pattern):
    return [(m.start(), m.end(), m.group().strip()) for m in re.finditer(pattern, text) if chars(m.group())]


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
    scenes, cursor = [], 0
    for scene in chapter["scenes"]:
        end = cursor + len(scene["text"])
        positions = [m for m in mapped if cursor <= m["charStart"] < end]
        if not positions:
            raise ValueError(f"幕 {scene['id']} 没有口播文字")
        scenes.append({**scene, "chars": positions, "char_start": cursor})
        cursor = end + 1
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
                   *, skip_post=False, post_options=None, asr_threshold=.97):
    """Generate final timing and reject content/prosody failures before export."""
    check_tool = load_voice_tool("voice-check")
    quality = load_voice_tool("voice-quality")
    audit = quality.audit(chapter["text"], transcription, normalizations, asr_threshold)
    with wave.open(str(raw), "rb") as source:
        original_duration = source.getnframes() / source.getframerate()
    mapped, ratio, clamps = align_characters(chapter["text"], transcription, original_duration, audit["normalizations"])
    audit["alignment_ratio"] = ratio
    audit["ok"] = audit["ok"] and ratio >= asr_threshold
    write_json(output / "analysis" / f"asr-audit-{chapter['id']}.json", audit)
    aligned = dict(text=chapter["text"], mapped=mapped, matched_ratio=ratio, monotonic_clamps=clamps)
    audio = raw
    options = dict(post_options or {})
    if not skip_post:
        post_tool = load_voice_tool("voice-post")
        boundaries, cursor = [], 0
        for scene in chapter["scenes"][:-1]:
            end = cursor + len(scene["text"])
            boundaries.append(max(row["charEnd"] for row in mapped if cursor <= row["charStart"] < end))
            cursor = end + 1
        processed = output / "processed"
        processed.mkdir(exist_ok=True)
        audio = processed / f"chapter-{chapter['id']}.wav"
        aligned = post_tool.postprocess(raw, aligned, audio, scene_boundaries=boundaries,
                                        scene_padding=silence, **options)
    write_json(output / "analysis" / f"post-alignment-{chapter['id']}.json", aligned)
    record, timing, scenes, captions, analysis = prepare_chapter(
        chapter, audio, output, transcription, audit["normalizations"], silence, offset, anchors, aligned=aligned)
    padding = record["added_boundary_silence"]
    final_alignment = dict(text=chapter["text"], mapped=analysis["output_mapped"], matched_ratio=ratio)
    if not skip_post:
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
        final_alignment = dict(text=chapter["text"], mapped=analysis["output_mapped"], matched_ratio=ratio)
    write_json(output / "analysis" / f"final-alignment-{chapter['id']}.json", final_alignment)
    check = check_tool.check_chapter(output / record["path"] , final_alignment, chapter=chapter["id"],
                                    cache=output / "analysis" / f"voice-check-{chapter['id']}.npz")
    check.update(prosody_ok=check["ok"], asr=audit, ok=check["ok"] and audit["ok"])
    write_json(output / "analysis" / f"voice-check-{chapter['id']}.json", check)
    record.update(generated_duration=original_duration, postprocessing=not skip_post,
                  prosody_alert_count=len(check["alerts"]), asr_matched_ratio=audit["ratio"], asr_passed=audit["ok"])
    return record, timing, scenes, captions, analysis, check


def main():
    import shutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--brand", default="yice")
    parser.add_argument("--anchors", type=Path)
    parser.add_argument("--normalizations", type=Path, help="分类的 ASR 例外：number_unit/english_name/homophone")
    parser.add_argument("--silence", type=float, default=.2)
    parser.add_argument("--asr-model", default="mlx-community/whisper-large-v3-turbo")
    parser.add_argument("--asr-prompt", default="", help="领域词表；不要提供完整台词诱导识别")
    parser.add_argument("--asr-threshold", type=float, default=.97)
    parser.add_argument("--seeds", default="42,43")
    parser.add_argument("--backend", choices=["modal", "kaggle", "local"], default="modal",
                        help="配音后端，默认 Modal；local 仅作离线兜底")
    parser.add_argument("--candidates", type=int, default=3,
                        help="每个语义句组的温度候选数，默认3")
    parser.add_argument("--chapters", help="只处理指定章号，如 00,01")
    parser.add_argument("--reuse-candidates", type=Path, help="显式哈希候选缓存；复跑时保留原始生成证据")
    parser.add_argument("--max-repair-rounds", type=int, default=3)
    parser.add_argument("--generation-jobs", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--generate-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--skip-post", action="store_true", help="保留原音；ASR/韵律仍必须通过")
    parser.add_argument("--speed", type=float, default=1.08)
    parser.add_argument("--breath-db", type=float, default=-12.)
    parser.add_argument("--breath-cut-ms", type=float, default=250.)
    parser.add_argument("--breath-target-ms", type=float, default=150.)
    parser.add_argument("--fade-ms", type=float, default=10.)
    parser.add_argument("--lufs", type=float, default=-16.)
    args = parser.parse_args()
    quality = load_voice_tool("voice-quality")
    try:
        seeds = quality.seeds(args.seeds)
    except ValueError as exc:
        parser.error(str(exc))
    if (not 0 <= args.silence <= 2 or not 0 < args.asr_threshold <= 1 or
            not 0 <= args.max_repair_rounds <= 3 or not 1 <= args.candidates <= 8):
        parser.error("换幕静音须为0–2秒，ASR阈值须为(0,1]，修复轮数须为0–3，候选数须为1–8")
    if args.generation_jobs:
        generate_jobs(json.loads(args.generation_jobs.read_text()), args.brand, backend=args.backend, candidates=args.candidates)
        return
    chapters, output = parse_script(args.script), args.output.resolve()
    if args.chapters:
        requested = set(args.chapters.split(","))
        if requested - {chapter["id"] for chapter in chapters}:
            parser.error("存在未知章号")
        chapters = [chapter for chapter in chapters if chapter["id"] in requested]
    if args.generate_only:
        generate_raw(chapters, output / "raw", args.brand, seeds, backend=args.backend, candidates=args.candidates)
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
    transcribe = make_transcriber(args.asr_model, args.asr_prompt, output / "analysis/asr")
    jobs = [dict(chapter=chapter["id"], text=chapter["text"], seed=seed,
                 path=str(output / "raw" / f"seed{seed}" / f"chapter-{chapter['id']}-raw.wav"))
            for chapter in chapters for seed in seeds]
    generate(jobs)
    flow = load_voice_tool("voice-repair")
    records, timings, scenes, subtitles, offset = [], [], [], [], 0
    failed = []
    for chapter in chapters:
        result = flow.process_chapter(chapter, [job for job in jobs if job["chapter"] == chapter["id"]],
            output / "candidates" / chapter["id"], generate, transcribe, exceptions=normalization,
            threshold=args.asr_threshold, silence=args.silence, offset=offset, anchors=anchors,
            skip_post=args.skip_post, max_rounds=args.max_repair_rounds, post_options=dict(
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
        records.append(record)
        timings.extend(result["timing"]); scenes.extend(result["scenes"]); subtitles.extend(result["captions"])
        offset = record["end"]
    if failed:
        write_json(output / "analysis/failures.json", dict(chapters=failed, max_repair_rounds=args.max_repair_rounds))
        raise SystemExit("ASR/配音检测未通过，最多修复3轮后停止组装：" + ", ".join(failed))
    sys.path.insert(0, str(TOOLKIT / "tools"))
    from captions import export_subtitles
    (output / "voice.srt").write_text(export_subtitles(subtitles, max_words=1))
    write_json(output / "voice-timing.json", timings)
    manifest = {"version": 1, "time_unit": "seconds", "time_origin": "whole_episode",
                "total_duration": offset, "chapters": records, "scene_timing": scenes,
                "scene_count": len(scenes), "sentence_count": len(timings), "subtitle_count": len(subtitles),
                "anchor_count": sum(len(t["anchors"]) for t in timings),
                "raw_voice_duration": round(sum(record["generated_duration"] for record in records), 5),
                "boundary_silence_duration": round(sum(record["added_boundary_silence"] for record in records), 5),
                "source_script_sha256": hashlib.sha256(args.script.read_bytes()).hexdigest(),
                "postprocessing": not args.skip_post, "prosody_check": "passed", "asr_check": "passed",
                "seeds": seeds, "asr_threshold": args.asr_threshold, "max_repair_rounds": args.max_repair_rounds,
                "alignment_note": "最终波形经LUFS归一化、整章ASR和韵律复扫；整句修复后重算字时间、字幕和锚点。"}
    write_json(output / "voice-manifest.json", manifest)
    print(json.dumps({"output": str(output), "duration": offset, "chapters": len(records),
                      "sentences": len(timings), "anchors": manifest["anchor_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
