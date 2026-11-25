"""本地素材装箱、成片规格、时间轴和抽帧文字检查。"""
import argparse
from collections import Counter
import getpass
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import struct
from fractions import Fraction
from pathlib import Path

from review import run
from audit_v7 import IMAGE_EXTENSIONS, difference_hash, primary_files

REAL = {"real_video", "web_cam", "screenshot"}
VISUAL = {".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".svg"}
CUTOUT_OVERLAYS = {"prop_badge", "reaction_cutout"}
GENERATED = re.compile(r"image2|ltx2|generated|metaphor-image|motion-video|prop-cutout", re.I)


def _probe_video(path: Path) -> tuple[float, int, int]:
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
                            "-select_streams", "v:0", "-of", "json", str(path)]).stdout)
    stream = probe["streams"][0]
    return float(probe["format"]["duration"]), int(stream["width"]), int(stream["height"])


def pixel_dead_frame_gate(rendered: Path, duration: float, errors: list[str], timeline: dict | None = None) -> dict:
    """直接从 MP4 抽 2fps 小帧，拦截真实连续静止画面。"""
    limit = max(0.0, duration - 3.0)
    proc = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(rendered), "-vf", "fps=2,scale=64:36:flags=bilinear,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"
    ], check=True, capture_output=True)
    size = 64 * 36
    previous = None
    run_start = None
    run_count = 0
    dead_runs = []
    static_ok = [
        (float(shot["start"]), float(shot["end"]))
        for shot in (timeline or {}).get("shots", [])
        if shot.get("kind") == "explainer_graphic"
    ]
    for index in range(0, len(proc.stdout), size):
        frame = proc.stdout[index:index + size]
        if len(frame) != size:
            break
        if previous is not None:
            change = sum(abs(a - b) for a, b in zip(previous, frame)) / (size * 255)
            timestamp = index / size / 2
            is_static_ok = any(start <= timestamp < end for start, end in static_ok)
            if change < 0.004 and timestamp < limit and not is_static_ok:
                if run_start is None:
                    run_start = max(0.0, timestamp - 0.5)
                    run_count = 0
                run_count += 1
            else:
                if run_start is not None and run_count / 2 > 4.5:
                    dead_runs.append((run_start, timestamp))
                run_start, run_count = None, 0
        previous = frame
    if run_start is not None and run_count / 2 > 4.5:
        dead_runs.append((run_start, min(duration, run_start + run_count / 2)))
    for start, end in dead_runs:
        errors.append(f"v4 真像素死镜：{start:.2f}–{end:.2f}s 连续帧差低于 0.4%")
    return {"sample_fps": 2, "dead_runs": [{"start": a, "end": b} for a, b in dead_runs]}


def black_frame_gate(rendered: Path, timeline: dict, duration: float, errors: list[str]) -> dict:
    """按真实像素平均亮度拦截非故意黑帧。"""
    sample_fps = 2
    proc = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(rendered),
        "-vf", "fps=2,scale=64:36:flags=bilinear,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"
    ], check=True, capture_output=True)
    size = 64 * 36
    threshold = 6.0
    intentional = []
    for shot in timeline.get("shots", []):
        if shot.get("intentional_black") or shot.get("name") == "黑场":
            intentional.append((float(shot["start"]), float(shot["end"])))

    def is_intentional(at):
        return any(start <= at < end for start, end in intentional)

    black_times = []
    for index in range(0, len(proc.stdout), size):
        frame = proc.stdout[index:index + size]
        if len(frame) != size:
            break
        average = sum(frame) / size
        at = index / size / sample_fps
        if average < threshold and at < duration:
            black_times.append({"start": at, "end": min(duration, at + 1 / sample_fps), "average_luma": average,
                                "intentional": is_intentional(at)})
    unexpected = [item for item in black_times if not item["intentional"]]
    for item in unexpected:
        errors.append(f"v4 黑帧：{item['start']:.2f}–{item['end']:.2f}s 平均亮度 {item['average_luma']:.2f} < 6.0")
    return {"sample_fps": sample_fps, "threshold": threshold, "black_frames": black_times,
            "unexpected_black_frames": unexpected}


def _dhash(path: Path, second: float) -> int:
    from PIL import Image
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{second:.3f}", "-i", str(path), "-frames:v", "1", tmp.name])
        with Image.open(tmp.name) as image:
            return difference_hash(image)


def dhash_gate(rendered: Path, timeline: dict, errors: list[str], *, v7=False) -> dict:
    shots = sorted(timeline.get("shots", []), key=lambda row: float(row["start"]))
    hashes = []
    for shot in shots:
        start, end = float(shot["start"]), float(shot["end"])
        if end <= start:
            continue
        at = (start + end) / 2
        hashes.append({"shot": shot.get("id", "?"), "at": at, "hash": _dhash(rendered, at)})
    groups = []
    for item in hashes:
        group = next((g for g in groups if (g[0]["hash"] ^ item["hash"]).bit_count() <= 4), None)
        if group is None:
            groups.append([item])
        else:
            group.append(item)
    repeats = [group for group in groups if len(group) > (2 if v7 else 4)]
    for group in repeats:
        reason = "v7 dHash 跨镜视觉重复超过 2 次" if v7 else "v4 dHash 跨镜重复超过 4 次"
        errors.append(reason + "：" + ", ".join(item["shot"] for item in group))
    return {"shot_samples": len(hashes), "duplicate_groups": [[item["shot"] for item in group] for group in repeats]}


def _rms_window(wav: Path, start: float = 0.0, duration: float | None = None) -> float:
    args = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", str(wav)]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    args += ["-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"]
    raw = subprocess.run(args, check=True, capture_output=True).stdout
    values = struct.iter_unpack("<f", raw)
    squares = [sample[0] * sample[0] for sample in values]
    return math.sqrt(sum(squares) / len(squares)) if squares else 0.0


def music_drop_acoustic_gate(rendered: Path, timeline: dict, errors: list[str], *, minimum=4) -> dict:
    drops = timeline.get("music_drops", [])
    bed = rendered.parent / "bed-only.wav"
    if len(drops) < minimum:
        errors.append("v4 声学门禁要求至少 4 个 Music Drop")
        return {"bed_only": str(bed), "drop_count": len(drops)}
    if not bed.is_file():
        errors.append(f"v4 缺少纯伴奏轨：{bed}")
        return {"bed_only": str(bed), "drop_count": len(drops)}
    average = _rms_window(bed)
    measurements = []
    for start, end in drops:
        rms = _rms_window(bed, float(start), float(end) - float(start))
        db = 20 * math.log10(max(rms, 1e-12) / max(average, 1e-12))
        measurements.append({"start": start, "end": end, "rms_db_vs_average": db})
        if db > -22:
            errors.append(f"v4 Music Drop 衰减不足：{start}–{end}s 为 {db:.1f} dB")
    return {"bed_only": str(bed), "drop_count": len(drops), "average_rms": average, "drops": measurements}


def subzone_gate(project: Path, errors: list[str]) -> dict:
    findings = []
    for file in project.rglob("*.html"):
        if "vendor" in file.parts:
            continue
        text = file.read_text(errors="replace")
        for match in re.finditer(r"<text\b[^>]*?\by\s*=\s*[\"']([0-9.]+)[\"'][^>]*>(.*?)</text>", text, re.S | re.I):
            y = float(match.group(1))
            if y >= 900:
                findings.append({"file": str(file), "y": y, "text": re.sub(r"<[^>]+>", "", match.group(2)).strip()[:80]})
    for finding in findings:
        errors.append(f"v4 字幕安全区冲突：{finding['file']} y={finding['y']:.0f} 「{finding['text']}」")
    return {"violations": findings}


def cutout_overlays_gate(timeline, project, errors):
    missing = []
    for shot in timeline["shots"]:
        for overlay in shot.get("overlays", []):
            if overlay.get("kind") not in CUTOUT_OVERLAYS:
                continue
            source = overlay.get("source")
            if (not isinstance(source, str) or Path(source).suffix.lower() not in IMAGE_EXTENSIONS
                    or source not in shot.get("aux_files", []) or source not in shot.get("files", [])
                    or not (project / source).is_file()):
                missing.append({"shot": shot.get("id"), "overlay": overlay["kind"]})
    if missing:
        errors.append("抠像叠层缺少已登记的图片素材")
    return {"ok": not missing, "missing": missing}


def precheck(args, errors):
    ledger = args.project / "asset-ledger.jsonl"
    files = []
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if GENERATED.search(str([row.get(key) for key in ("kind", "sourceType", "tool")])):
                continue
            entries = [row["path"]] if row.get("path") else [
                item["path"] if isinstance(item, dict) else item for item in row.get("files", [])]
            files.extend(args.project / entry for entry in entries)
    else:
        files = (args.project / "assets").rglob("*")
    digests = set()
    for file in files:
        if file.suffix.lower() in VISUAL and not GENERATED.search(str(os.path.relpath(file, args.project))) and file.is_file() and file.stat().st_size:
            with file.open("rb") as source:
                digests.add(hashlib.file_digest(source, "sha256").hexdigest())
    required = math.ceil(args.target_seconds * args.min_assets_per_min / 60)
    missing = max(0, required - len(digests))
    if missing:
        errors.append(f"实证素材缺 {missing} 件")
    return dict(required=required, assets=len(digests), missing=missing)


def _v4_timeline_metrics(data, duration, errors):
    """执行 v4 的反复用、沉浸布局、节奏与 Music Drop 门禁。"""
    shots = sorted(data.get("shots", []), key=lambda row: row["start"])
    file_counts = Counter()
    slice_counts = Counter()
    layout_seconds = Counter()
    actions = []
    for shot in shots:
        length = max(0.0, min(float(shot["end"]), duration) - float(shot["start"]))
        layout_seconds[shot.get("layout", "split_box")] += length
        files = shot.get("files", [])
        media_start = shot.get("media_start", shot.get("mediaStart", 0.0))
        for file in files:
            file_counts[str(file)] += 1
            slice_counts[(str(file), round(float(media_start), 1))] += 1
        start = float(shot["start"])
        for beat in shot.get("beats", []):
            value = float(beat)
            actions.append(start + value if 0 <= value < length else value)
    actions = sorted(value for value in actions if 0 <= value <= duration)
    intervals = [b - a for a, b in zip(actions, actions[1:]) if b >= a]
    avg_beat_interval = sum(intervals) / len(intervals) if intervals else duration
    max_beat_gap = max(intervals, default=duration)
    immersive = sum(layout_seconds[name] for name in ("fullbleed", "print_desk", "ab_compare"))
    music_drops = data.get("music_drops", [])
    if not music_drops:
        music_drops = [mark for mark in data.get("sound_marks", []) if mark.get("kind") == "music_drop"]
    metrics = {
        "max_file_reuse": max(file_counts.values(), default=0),
        "max_slice_reuse": max(slice_counts.values(), default=0),
        "split_box_ratio": layout_seconds["split_box"] / duration,
        "immersive_ratio": immersive / duration,
        "avg_beat_interval": avg_beat_interval,
        "max_beat_gap": max_beat_gap,
        "music_drop_count": len(music_drops),
        "layout_seconds": dict(layout_seconds),
    }
    # 文件名统计只作报告。v4 的重复门禁必须以成片中点 dHash 为准，避免通过改名或
    # 依赖后置 JSON 统计制造假阳性。
    if metrics["split_box_ratio"] > 0.22:
        errors.append("v4 split_box 占比超过 22%")
    if metrics["immersive_ratio"] < 0.65:
        errors.append("v4 满屏跟焦、相纸桌面与 A/B 沉浸布局占比低于 65%")
    if metrics["avg_beat_interval"] > 2.5:
        errors.append("v4 平均视觉动作间隔超过 2.5 秒")
    if metrics["max_beat_gap"] > 3.8:
        errors.append("v4 存在超过 3.8 秒的静止空档")
    if metrics["music_drop_count"] < 4:
        errors.append("v4 Music Drop 少于 4 处")
    if metrics["max_file_reuse"] > 4:
        errors.append(f"v4 单文件复用超过 4 次：{metrics['max_file_reuse']} 次")
    return metrics



def _v5_timeline_metrics(data, duration, project, errors):
    """Skill v5 防循环、唯一素材和从容节奏门禁。"""
    counts = Counter()
    names_by_digest = {}
    digests_by_path = {}
    short_sources = []
    short = []
    spans = []
    dynamic_duration = 0.0
    static_duration = 0.0
    forbidden = []
    for shot in data.get("shots", []):
        start, end = float(shot.get("start", 0)), float(shot.get("end", 0))
        span = end - start
        spans.append(span)
        if span < 2.5 and not shot.get("montage_countdown"):
            short.append(shot.get("id", "?"))
        files = shot.get("files", [])
        has_dynamic_video = any(Path(rel).suffix.lower() == ".mp4" for rel in files)
        has_static_image = any(Path(rel).suffix.lower() in {".png", ".jpg", ".jpeg"} for rel in files)
        if has_dynamic_video:
            dynamic_duration += span
        elif has_static_image:
            static_duration += span
        for rel in files:
            media = project / rel
            identity = rel
            if media.is_file():
                if media not in digests_by_path:
                    with media.open("rb") as source:
                        digests_by_path[media] = hashlib.file_digest(source, "sha256").hexdigest()
                identity = names_by_digest.setdefault(digests_by_path[media], rel)
            counts[identity] += 1
            rel_name = Path(rel).name
            if re.search(r"v5-frame-", rel_name, re.I) or re.search(r"EP03-全片-.*\.mp4$", rel_name, re.I):
                forbidden.append(rel)
            if rel.lower().endswith(".mp4"):
                media = project / rel
                if media.is_file():
                    try:
                        probe = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(media)])
                        source_duration = float(probe.stdout.strip())
                        offset = float(shot.get("media_start", 0))
                        is_graphic = shot.get("kind") == "explainer_graphic"
                        required = span + offset
                        if is_graphic:
                            required += 0.35
                        elif shot.get("kind") == "web_cam":
                            required += 1.0
                        # 编码时长只允许一帧取整偏差。
                        if source_duration + 1/30 < required or (is_graphic and source_duration - required > 1/30):
                            short_sources.append({"shot": shot.get("id"), "source": rel,
                                                  "actual": source_duration, "required": required})
                            errors.append(f"v5 素材时长不符 {rel}: 实际 {source_duration:.3f}s，要求 {required:.3f}s")
                    except (ValueError, subprocess.SubprocessError):
                        errors.append(f"v5 无法读取素材时长 {rel}")
                else:
                    errors.append(f"v5 镜头 {shot.get('id','?')} 缺少素材 {rel}")
    repeated = {name: n for name, n in counts.items() if n > 1}
    repeated_twice = {name: n for name, n in repeated.items() if n == 2}
    if len(repeated_twice) > 2 or any(n > 2 for n in repeated.values()):
        errors.append(f"v5 素材复用超限: {repeated}")
    static_reuse = {name: n for name, n in counts.items() if Path(name).suffix.lower() in {'.png','.jpg','.jpeg'} and n != 1}
    graphic_reuse = {name: n for name, n in counts.items() if 'exp-' in Path(name).name and n != 1}
    if static_reuse:
        errors.append(f"v5 静态图必须只用一次: {static_reuse}")
    if graphic_reuse:
        errors.append(f"v5 解说动效必须只用一次: {graphic_reuse}")
    if short:
        errors.append(f"v5 存在短于 2.5 秒的非倒数镜头: {short}")
    if not 65 <= len(spans) <= 90:
        errors.append(f"v5 镜头数 {len(spans)} 不在 65–90")
    average = sum(spans) / len(spans) if spans else 0
    if average < 4.8:
        errors.append(f"v5 平均镜长 {average:.2f}s 小于 4.8s")
    moving_ratio = dynamic_duration / duration if duration else 0.0
    static_ratio = static_duration / duration if duration else 0.0
    if moving_ratio < 0.82:
        errors.append(f"v5 动态视频镜头占比 {moving_ratio:.3f} 低于 0.82")
    if static_ratio > 0.10:
        errors.append(f"v5 静态图镜头占比 {static_ratio:.3f} 高于 0.10")
    if forbidden:
        errors.append(f"v5 禁止使用伪素材: {sorted(set(forbidden))}")
    loop_files = []
    for html_file in project.rglob('index.html'):
        try:
            if re.search(r'<video[^>\n]*\bloop\b', html_file.read_text(errors='replace'), re.I):
                loop_files.append(str(html_file.relative_to(project)))
        except OSError:
            continue
    if loop_files:
        errors.append(f"v5 发现 video loop: {loop_files}")
    return {"no_loop_restart_gate": {"loop_files": loop_files, "short_sources": short_sources},
            "strict_uniqueness_gate": {"reuse": counts, "repeated": repeated},
            "calm_pacing_gate": {"shot_count": len(spans), "average_shot": average, "source_shot_count": len(spans), "short_shots": short},
            "moving_video_ratio_gate": {"dynamic_video_ratio": moving_ratio, "static_image_ratio": static_ratio,
                                         "forbidden_pseudo_assets": sorted(set(forbidden))}}

def timeline_metrics(data, duration, project, errors, *, v4=False, v5=False):
    previous = real = stock = breaks = continuous = longest = max_windows = 0
    for shot in sorted(data["shots"], key=lambda row: row["start"]):
        start, end, kind = shot["start"], shot["end"], shot["kind"]
        if kind == "text_card" and start < previous <= end:
            # 允许叠在满屏实录上的短字卡，字卡自身仍由 HyperFrames layout gate 检查。
            continue
        if kind == "evidence_wall":
            errors.append(f"镜头 {shot.get('id')} 使用了已禁用的多宫格碎框证据墙（evidence_wall），请改用单主视窗或 A/B 双视窗")
            continue
        if not (previous <= start < end <= duration + 0.2) or kind not in REAL | {"stock_broll", "ai_generated", "text_card", "chapter_break", "explainer_graphic", "triptych_cards"}:
            raise ValueError(f"无效镜头 {shot.get('id')}")
        length = min(end, duration) - start
        files = shot.get("files", [])
        windows = len(primary_files(shot))
        max_windows = max(max_windows, windows)
        if windows > 3:
            errors.append(f"镜头 {shot.get('id')} 同屏堆砌 {windows} 个视窗（上限 3 个，严禁蚂蚁字碎框）")
        if kind not in {"text_card", "chapter_break"}:
            if not files or not all((project / file).is_file() and (project / file).stat().st_size for file in files):
                errors.append(f"镜头 {shot.get('id')} 缺少素材")
        if kind in REAL:
            real += length
        if kind == "stock_broll":
            stock += length
        if kind == "chapter_break":
            breaks += length
            continuous = 0
        elif kind == "text_card":
            continuous = length + (continuous if start - previous <= 0.6 else 0)
            longest = max(continuous, longest)
        else:
            continuous = 0
        previous = end
    if real / duration < 0.55:
        errors.append("实证覆盖率低于 55%")
    if stock / duration > 0.15:
        errors.append("图库空镜（stock_broll）占比超过 15%，严禁拿图库视频铺满当壁纸")
    if breaks > max(8.5, duration * 0.15):
        errors.append("片名与章节扉页（chapter_break）总长超标")
    if longest > 5:
        errors.append("连续纯字卡超过 5 秒")
    result = dict(real_ratio=real / duration, stock_broll_ratio=stock / duration,
                  longest_text_card=longest, max_windows_per_shot=max_windows)
    if v4:
        result.update(_v4_timeline_metrics(data, duration, errors))
    if v5:
        result.update(_v5_timeline_metrics(data, duration, project, errors))
    return result


VIEWPORT_ONLY_TERMS = ("Johnny Harris", "Fireship")


def cited_viewport_terms(timeline, second):
    """Return only channel names declared in a reference shot at this frame."""
    declared = []
    for shot in (timeline or {}).get("shots", []):
        if (shot.get("stage_mode") not in {"reference_breakdown", "triptych_cards"}
                or not shot["start"] <= second < shot["end"]):
            continue
        declared.extend([shot.get("channel"), *(shot.get("semantic_tags") or [])])
        for card in shot.get("cards") or []:
            if isinstance(card, dict):
                declared.extend(card.get(field) for field in ("channel", "label", "sublabel"))
    names = [name.casefold() for name in declared if isinstance(name, str)]
    return {term for term in VIEWPORT_ONLY_TERMS
            if any(re.search(r"(?<![a-z0-9])" + r"\s*".join(map(re.escape,term.casefold().split()))
                             + r"(?![a-z0-9])", name) for name in names)}


def frame_ocr_hits(rows, second, terms, *, citation_timeline=None):
    viewport_terms = tuple(term for term in VIEWPORT_ONLY_TERMS
                           if term not in cited_viewport_terms(citation_timeline, second))
    for row in rows:
        normalized = "".join(row["text"].casefold().split())
        box_y = row.get("box", [0, 0, 0, 0])[1]
        active_terms = (*terms, *viewport_terms) if box_y < 930 else terms
        for term in active_terms:
            if term.strip() and "".join(term.casefold().split()) in normalized:
                yield dict(seconds=second, term=term, text=row["text"])


def scan_frames(args, duration, out, errors, *, timeline=None):
    from PIL import Image, ImageDraw
    source = Path(__file__).resolve().parents[1] / "tools/ocr/ocr.swift"
    binary = source.with_suffix("")
    terms = [os.getenv("USER") or getpass.getuser(), "/Users/", "Documents/Codex", "@gmail.com",
             "盲测", "片名卡", "静态截图", "本期实测底账", *args.forbid.split(",")]
    citation_timeline = timeline if getattr(args,"v7",False) else None
    times = range(0, math.ceil(duration), 2)
    canvas = Image.new("RGB", (320 * min(5, len(times)), 204 * math.ceil(len(times)/5)), "#202020")
    draw = ImageDraw.Draw(canvas)
    hits = []
    with tempfile.TemporaryDirectory() as temp:
        if not os.access(binary, os.X_OK) or binary.stat().st_mtime < source.stat().st_mtime:
            binary = Path(temp) / "ocr"
            run(["xcrun", "swiftc", str(source), "-o", str(binary)])
        frame = Path(temp) / "frame.png"
        for index, second in enumerate(times):
            run(["ffmpeg", "-v", "error", "-y", "-ss", str(second), "-i", str(args.rendered),
                 "-frames:v", "1", str(frame)])
            with Image.open(frame) as image:
                image.thumbnail((320,180))
                x, y = index % 5 * 320, index // 5 * 204
                canvas.paste(image, (x,y))
                draw.text((x+8,y+183), f"{second:.1f}s", fill="white")
            rows = json.loads(run([str(binary), str(frame)]).stdout)["results"]
            hits.extend(frame_ocr_hits(rows,second,terms,citation_timeline=citation_timeline))
            frame.unlink()
    canvas.save(out / "contact-sheet.jpg", quality=93)
    errors.extend(f"OCR {hit['seconds']}s {hit['text']}" for hit in hits)
    return dict(sample_count=len(times), hits=hits)


def voice_speed_checks(project):
    findings = []
    for directory, folders, names in os.walk(project):
        folders[:] = [name for name in folders if not name.startswith(".") and name not in {"node_modules", "vendor", "assets", "render"}]
        for name in names:
            file = Path(directory) / name
            if file.suffix not in {".py", ".sh", ".mjs", ".js", ".ts"}:
                continue
            code = "\n".join(line for line in file.read_text(errors="replace").splitlines()
                             if not line.lstrip().startswith(("#", "//")))
            if not re.search(r"voice/|chapter-", code):
                continue
            for match in re.finditer(r"\batempo\s*=\s*([^,\s'\";]+)", code):
                try:
                    if float(match[1]) == 1:
                        continue
                except ValueError:
                    pass
                findings.append(f"{file.relative_to(project)} 含人声素材及变速滤镜 {match[0]}，请核对原速拼接")
    return findings


def rendered(args, out, errors):
    v6 = getattr(args, "v6", False)
    v7 = getattr(args, 'v7', False)
    errors.extend(voice_speed_checks(args.project))
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                            "-of", "json", str(args.rendered)]).stdout)
    streams = probe["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    duration = float(probe["format"]["duration"])
    fps = float(Fraction(video["avg_frame_rate"]))
    if not (video["width"] == 1920 and video["height"] == 1080 and video["codec_name"] == "h264"
            and abs(fps - 30) <= 0.1 and any(s["codec_type"] == "audio" for s in streams) and duration > 0):
        errors.append("成片规格不符")
    result = dict(duration=duration, fps=fps, width=video["width"], height=video["height"])
    expected = args.expected_duration
    timeline = None
    if args.timeline:
        timeline = json.loads(args.timeline.read_text())
        if any(overlay.get("kind") in CUTOUT_OVERLAYS for shot in timeline["shots"] for overlay in shot.get("overlays", [])):
            result["cutout_overlays_gate"] = cutout_overlays_gate(timeline, args.project, errors)
        legacy_timeline = timeline
        if v6 and not v7:
            from audit_v6 import timeline_gates, masks, voice_continuity
            legacy_timeline = dict(timeline, shots=[dict(shot, kind="real_video") if shot["kind"]=="studio_ui" else shot for shot in timeline["shots"]])
        if v7:
            from audit_v7 import video_gates
            result.update(video_gates(timeline,args.project,args.rendered,duration,errors))
        else:
            result.update(timeline_metrics(legacy_timeline, duration, args.project, errors,
                                           v4=args.v4 or args.v5 or v6, v5=args.v5 or v6))
        if v6 and not v7:
            result.update(timeline_gates(timeline,args.project,duration,errors))
            found=masks(args.rendered,timeline)
            result["redaction_mask_gate"]={"hits":found,"banned_sources":result.pop("banned_sources")}
            if found: errors.append("疑似打码遮挡色块")
            result["voice_continuity_gate"]=voice_continuity(args.project)
            if result["voice_continuity_gate"]["violations"]: errors.append("章节配音连续性未通过")
        if expected is None:
            expected = timeline.get("end")
    if expected is not None and not abs(expected-duration) <= 0.2:
        errors.append("成片时长不符")
    summary = run(["ffmpeg", "-nostats", "-i", str(args.rendered), "-vn", "-af", "ebur128=peak=true",
                   "-f", "null", "-"]).stderr.rsplit("Summary:", 1)[-1]
    low_lufs, high_lufs = (-15.3,-13.7) if v7 else (-15.,-13.)
    for key, pattern, low, high in [("integrated_lufs", r"I:\s+([\w.+-]+) LUFS", low_lufs, high_lufs),
                                   ("true_peak_dbtp", r"Peak:\s+([\w.+-]+) dBFS", -150, -1)]:
        match = re.search(pattern, summary)
        value = float(match[1]) if match else None
        result[key] = value if value is not None and math.isfinite(value) else None
        if value is None or not low <= value <= high:
            errors.append(f"{key} 超出范围或无法测量")
    result["ocr"] = scan_frames(args, duration, out, errors,timeline=timeline)
    if args.v4 or args.v5 or v6 or v7:
        if timeline is None:
            errors.append("v4 需要真实 shot-timeline.json 才能做跨镜像素审计")
        else:
            result["pixel_gate"] = pixel_dead_frame_gate(args.rendered, duration, errors, timeline)
            result["black_frame_gate"] = black_frame_gate(args.rendered, timeline, duration, errors)
            result["dhash_gate"] = dhash_gate(args.rendered, timeline, errors,v7=v7)
            result["music_drop_acoustic"] = music_drop_acoustic_gate(args.rendered, timeline, errors,
                                                                    minimum=0 if v7 else 4)
        result["subzone_gate"] = subzone_gate(args.project, errors)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--precheck", action="store_true")
    mode.add_argument("--rendered", type=Path)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--expected-duration", type=float)
    parser.add_argument("--target-seconds", type=float, default=60)
    parser.add_argument("--min-assets-per-min", type=float, default=5)
    parser.add_argument("--forbid", default="")
    parser.add_argument("--v4", action="store_true", help="启用 Skill v4.0 头部创作硬门禁")
    parser.add_argument("--v5", action="store_true", help="启用 Skill v5.0 自治成片硬门禁")
    parser.add_argument("--v6", action="store_true", help="启用句首、科技实证、遮挡与云端配音门禁")
    parser.add_argument('--v7',action='store_true',help='启用语义、开场音轨、叠层动效与自然呼吸门禁')
    args = parser.parse_args()
    if args.v6 and (not args.rendered or not args.timeline): parser.error("--v6 需要 --rendered 与 --timeline")
    if args.v7 and (not args.rendered or not args.timeline): parser.error('--v7 需要 --rendered 与 --timeline')
    errors = []
    out = args.out or args.project
    out.mkdir(parents=True, exist_ok=True)
    try:
        if args.target_seconds <= 0 or args.min_assets_per_min <= 0:
            raise ValueError("目标时长和素材密度须为正数")
        metrics = precheck(args, errors) if args.precheck else rendered(args, out, errors)
    except (OSError, ImportError, ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError, subprocess.SubprocessError) as exc:
        metrics = {}
        errors.append(str(exc) or "缺少有效视频流")
    report = json.dumps(dict(ok=not errors, errors=errors, **metrics), ensure_ascii=False, indent=2)
    (out / "audit-v3-report.json").write_text(report + "\n")
    if args.v4:
        (out / "audit-v4-report.json").write_text(report + "\n")
    if args.v5:
        (out / "audit-v5-report.json").write_text(report + "\n")
    if args.v6:
        (out / "audit-v6-report.json").write_text(report + "\n")
    if args.v7:
        (out/'audit-v7-report.json').write_text(report+'\n')
    print(report)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
