"""本地素材装箱、成片规格、时间轴和抽帧文字检查。"""
import argparse
import getpass
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from review import run

REAL = {"real_video", "web_cam", "screenshot", "stock_broll", "evidence_wall"}
VISUAL = {".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".svg"}
GENERATED = re.compile(r"image2|ltx2|generated|metaphor-image|motion-video|prop-cutout", re.I)


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


def timeline_metrics(data, duration, project, errors):
    previous = real = continuous = longest = 0
    for shot in sorted(data["shots"], key=lambda row: row["start"]):
        start, end, kind = shot["start"], shot["end"], shot["kind"]
        if not (previous <= start < end <= duration + 0.2) or kind not in REAL | {"ai_generated", "text_card"}:
            raise ValueError(f"无效镜头 {shot.get('id')}")
        length = min(end, duration) - start
        if kind != "text_card":
            files = shot.get("files", [])
            if not files or not all((project / file).is_file() and (project / file).stat().st_size for file in files):
                errors.append(f"镜头 {shot.get('id')} 缺少素材")
        if kind in REAL:
            real += length
        if kind == "text_card":
            continuous = length + (continuous if start - previous <= 0.6 else 0)
            longest = max(continuous, longest)
        else:
            continuous = 0
        previous = end
    if real / duration < 0.55:
        errors.append("实证覆盖率低于 55%")
    if longest > 5:
        errors.append("连续纯字卡超过 5 秒")
    return dict(real_ratio=real / duration, longest_text_card=longest)


def scan_frames(args, duration, out, errors):
    from PIL import Image, ImageDraw
    source = Path(__file__).resolve().parents[1] / "tools/ocr/ocr.swift"
    binary = source.with_suffix("")
    terms = [os.getenv("USER") or getpass.getuser(), "/Users/", "Documents/Codex", "@gmail.com",
             "盲测", "片名卡", "静态截图", "本期实测底账", "Johnny Harris", "Fireship", *args.forbid.split(",")]
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
            for row in json.loads(run([str(binary), str(frame)]).stdout)["results"]:
                normalized = "".join(row["text"].casefold().split())
                for term in terms:
                    if term.strip() and "".join(term.casefold().split()) in normalized:
                        hits.append(dict(seconds=second, term=term, text=row["text"]))
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
    if args.timeline:
        timeline = json.loads(args.timeline.read_text())
        result.update(timeline_metrics(timeline, duration, args.project, errors))
        if expected is None:
            expected = timeline.get("end")
    if expected is not None and not abs(expected-duration) <= 0.2:
        errors.append("成片时长不符")
    summary = run(["ffmpeg", "-nostats", "-i", str(args.rendered), "-vn", "-af", "ebur128=peak=true",
                   "-f", "null", "-"]).stderr.rsplit("Summary:", 1)[-1]
    for key, pattern, low, high in [("integrated_lufs", r"I:\s+([\w.+-]+) LUFS", -15, -13),
                                   ("true_peak_dbtp", r"Peak:\s+([\w.+-]+) dBFS", -150, -1)]:
        match = re.search(pattern, summary)
        value = float(match[1]) if match else None
        result[key] = value if value is not None and math.isfinite(value) else None
        if value is None or not low <= value <= high:
            errors.append(f"{key} 超出范围或无法测量")
    result["ocr"] = scan_frames(args, duration, out, errors)
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
    args = parser.parse_args()
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
    print(report)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
