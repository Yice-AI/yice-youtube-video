#!/usr/bin/env python3
"""T61 的章级 MLX 配音、Whisper 字级估计、captions.align 和换幕静音封装。"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
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


def generate_raw(chapters, output, brand):
    sys.path[:0] = [str(TOOLKIT / "local/tools"), str(TOOLKIT / "tools")]
    from local_voiceover import MLXBackend, load_clone
    backend = MLXBackend("8bit", load_clone(brand))
    for chapter in chapters:
        target = output / f"chapter-{chapter['id']}-raw.wav"
        backend.generate(text=chapter["text"], model=backend.model,
                         ref_audio=backend.clone["audio"], ref_text=backend.clone["text"],
                         lang_code=backend.clone["language"], stt_model=None,
                         output_path=str(output), file_prefix=target.stem,
                         audio_format="wav", join_audio=True, verbose=False,
                         max_tokens=4096, split_pattern="")
        if not target.is_file() or target.stat().st_size <= 44:
            raise RuntimeError(f"MLX 未生成有效 WAV：{target}")


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
    for intended, recognized in normalizations.items():
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


def prepare_chapter(chapter, raw_path, output, transcription, normalizations, silence, offset, anchors):
    with wave.open(str(raw_path), "rb") as source:
        params, pcm = source.getparams(), source.readframes(source.getnframes())
    rate, stride = params.framerate, params.nchannels * params.sampwidth
    duration = params.nframes / rate
    mapped, ratio, clamps = align_characters(chapter["text"], transcription, duration, normalizations)
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
    for i, scene in enumerate(scenes):
        lo, hi = cuts[i], cuts[i + 1]
        chunks.extend([b"\0" * gap * stride, pcm[lo * stride:hi * stride]])
        added = (i + 1) * gap / rate
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
                "sample_rate": rate, "segments": segments, "raw_pcm_preserved": True}
    return record, timing, scene_timing, captions, analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--brand", default="yice")
    parser.add_argument("--anchors", type=Path)
    parser.add_argument("--normalizations", type=Path, help='JSON：原稿短语→ASR 别写')
    parser.add_argument("--silence", type=float, default=.2)
    parser.add_argument("--asr-model", default="mlx-community/whisper-large-v3-turbo")
    parser.add_argument("--generate-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0 <= args.silence <= 2:
        parser.error("换幕静音须在 0–2 秒之间")
    chapters, output = parse_script(args.script), args.output.resolve()
    if args.generate_only:
        generate_raw(chapters, output / "raw", args.brand)
        return
    if output.exists() and any(output.iterdir()):
        parser.error(f"输出目录不是空目录，拒绝覆盖：{output}")
    anchors_path = args.anchors or args.script.parent / "anchors.json"
    anchors = json.loads(anchors_path.read_text()) if anchors_path.exists() else []
    normalization = json.loads(args.normalizations.read_text()) if args.normalizations else {}
    known = {s["id"]: s["text"] for c in chapters for s in c["scenes"]}
    for anchor in anchors:
        phrase = anchor.get("spoken_phrase", anchor["phrase"])
        if anchor["scene"] not in known or phrase not in known[anchor["scene"]]:
            parser.error(f"锚点必须有对应原稿；画面别名用 spoken_phrase：{anchor}")
    (output / "raw").mkdir(parents=True, exist_ok=True)
    (output / "analysis").mkdir()
    write_json(output / "analysis/script-manifest.json", {"chapters": chapters})
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
    tts_python = os.environ.get("YICE_TTS_PYTHON", str(TOOLKIT / "local/tts-venv/bin/python"))
    with (output / "analysis/voice-generation.log").open("w") as log:
        subprocess.run([tts_python, str(Path(__file__).resolve()), str(args.script.resolve()),
                        "--output", str(output), "--brand", args.brand, "--generate-only"],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    os.environ.update({k: env[k] for k in ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"]})
    import mlx_whisper
    records, timings, scenes, subtitles, offset = [], [], [], [], 0
    for chapter in chapters:
        raw = output / "raw" / f"chapter-{chapter['id']}-raw.wav"
        transcription = mlx_whisper.transcribe(str(raw), path_or_hf_repo=args.asr_model,
                                               language="zh", word_timestamps=True, verbose=False)
        write_json(output / "analysis" / f"whisper-{chapter['id']}.json", transcription)
        record, timing, scene, captions, analysis = prepare_chapter(
            chapter, raw, output, transcription, normalization, args.silence, offset, anchors)
        write_json(output / "analysis" / f"aligned-characters-{chapter['id']}.json", analysis)
        records.append(record); timings.extend(timing); scenes.extend(scene); subtitles.extend(captions)
        offset = record["end"]
    sys.path.insert(0, str(TOOLKIT / "tools"))
    from captions import export_subtitles
    (output / "voice.srt").write_text(export_subtitles(subtitles, max_words=1))
    write_json(output / "voice-timing.json", timings)
    manifest = {"version": 1, "time_unit": "seconds", "time_origin": "whole_episode",
                "total_duration": offset, "chapters": records, "scene_timing": scenes,
                "scene_count": len(scenes), "sentence_count": len(timings), "subtitle_count": len(subtitles),
                "anchor_count": sum(len(t["anchors"]) for t in timings),
                "raw_voice_duration": round(sum(c["original_duration"] for c in records), 5),
                "boundary_silence_duration": round(sum(c["added_boundary_silence"] for c in records), 5),
                "source_script_sha256": hashlib.sha256(args.script.read_bytes()).hexdigest(),
                "alignment_note": "T61：Whisper 字时间估计，原稿归一化后复用 captions.align 插值；章内 PCM 原样保留，仅每幕前加静音。"}
    write_json(output / "voice-manifest.json", manifest)
    print(json.dumps({"output": str(output), "duration": offset, "chapters": len(records),
                      "sentences": len(timings), "anchors": manifest["anchor_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
