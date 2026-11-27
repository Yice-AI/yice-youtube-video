#!/usr/bin/env python3
"""通过 image2 的标题模式生成并核对 YouTube 封面。"""
import argparse
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

from produce_asset import append_ledger, now, project_path, run_command, tool_python

OCR = Path(__file__).resolve().parents[1] / "tools/ocr/ocr"
TIMESTAMP = re.compile(r"\b(?:\d{1,2}:\d{2}(?::\d{2})?|XX:XX)\b", re.IGNORECASE)
PREVIEWS = ((640, 360), (320, 180), (168, 94))


def watermark_result(file, size):
    if not os.access(OCR, os.X_OK):
        return {"watermark_warning": False, "watermark_check": "unavailable"}
    width, height = size
    x, y = int(width * .76), int(height * .80)
    region = f"{x},{y},{width-x},{height-y}"
    try:
        result = subprocess.run([str(OCR), str(file), "--region", region], capture_output=True,
                                text=True, check=True, timeout=5)
        texts = [row["text"] for row in json.loads(result.stdout)["results"]]
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return {"watermark_warning": False, "watermark_check": "unavailable"}
    matches = [text for text in texts if TIMESTAMP.search(text)]
    return {"watermark_warning": bool(matches), "watermark_check": "checked", "watermark_text": matches}


def contact_sheet(batch, rows):
    sheet = Image.new("RGB", (1224, 76 + 448 * len(rows)), "#111820")
    draw = ImageDraw.Draw(sheet)
    title = ImageFont.load_default(size=25)
    label = ImageFont.load_default(size=16)
    draw.text((28, 23), "YOUTUBE THUMBNAIL CANDIDATES", font=title, fill="#f4f6fa")
    for index, row in enumerate(rows, 1):
        top = 65 + 448 * (index - 1)
        draw.rounded_rectangle((16, top, 1208, top + 432), radius=14, fill="#1b2632")
        draw.text((28, top + 10), f"#{index}", font=title, fill="#f4f6fa")
        with Image.open(batch / row["file"]) as source:
            source = source.convert("RGB")
            for x, size, name in zip((28, 686, 1024), PREVIEWS, ("Main preview", "Desktop feed", "Mobile feed")):
                draw.text((x+50 if x==28 else x, top+17), f"{name}  {size[0]} px", font=label, fill="#bac7d4")
                sheet.paste(ImageOps.pad(source, size, method=Image.Resampling.LANCZOS), (x, top+47))
        checked = row["watermark_check"] == "checked"
        status = "No timestamp detected" if checked else "OCR unavailable"
        if row["watermark_warning"]:
            draw.rounded_rectangle((686, top + 245, 1192, top + 283), radius=6, fill="#f6b853")
            draw.text((698, top + 253), "Check timestamp in lower-right corner", font=label, fill="#23190e")
        else:
            draw.text((686, top+250), status, font=label, fill="#bac7d4")
    target = batch / "thumbnail-contact-sheet.png"
    sheet.save(target)
    return target


def cover_brief(title, summary, hook=None, badge=None):
    units = re.compile(r'[一-鿿]|[A-Za-z0-9]+')
    if hook is None:
        budget = 10 - len(units.findall(badge or ''))
        clauses = [part.strip() for part in re.split(r'[：:，,。！？!?｜|]', title) if units.search(part)]
        hook = next((part for part in clauses if len(units.findall(part)) <= budget), None)
        if hook is None:
            words = list(units.finditer(clauses[0])) if clauses else []
            hook = clauses[0][:words[budget-1].end()] if 0 < budget <= len(words) else ''
    if not units.search(hook) or len(units.findall(hook)) + len(units.findall(badge or '')) > 10:
        raise ValueError('核心钩子与可选数字胶囊合计最多 10 个汉字或词组')
    if badge and not re.search(r'\d|[一二三四五六七八九十]', badge):
        raise ValueError('可选胶囊只放一个短数字信息')
    comparison = ('左侧三分之一是一张传统蓝框模板演示页，压暗并配一条简洁红斜杠。'
                  '右侧三分之二是立体展开的克莱因蓝点阵演示页、暖白瑞士图表页与苹果风深色演示页。'
                  if re.search(r'PPT|演示稿', title+' '+summary, re.I) else
                  '左侧三分之一展示实际遇到的问题，右侧三分之二放同一主题可见的改进成果。只选一组实物反差。')
    description = ('唯一允许印在画面上的字为核心钩子「'+hook+'」'+
                   ('和左上角一枚小数字胶囊「'+badge+'」' if badge else '，不使用任何徽章或数字胶囊')+'。'
                   '核心字固定在左上至中左（x=4–47%，y=10–56%），字面逐字正确且只出现一次。不要把文案放在底边。样张只用线条、点阵、无字图形模拟版式。'+comparison+
                   '瑞士纸感和克制的摄影棚光影。重磅几何无衬线，近景实物对比，168px 缩图仍可辨。'
                   '右下 x>78%、y>80% 净空，仅显示无字摄影棚桌面；文字、徽章、数字、标志、图表读数均不能移入。不要长标题、图标列表、促销小字、蓝水晶盾牌、毛笔飞白或霓虹辉光。'
                   '下面是仅供选择实物题材的背景材料，不印成文字：'+summary[:1400])
    return hook, description


def generate(args, project, root):
    summary = args.content_file.read_text(encoding="utf-8") if args.content_file else args.summary
    if not (args.title and args.title.strip() and summary and summary.strip()):
        raise ValueError("生成需要 --title 和 --summary 或 --content-file")
    hook, brief = cover_brief(args.title, summary, args.hook, args.badge)
    name = args.batch or datetime.now().strftime("batch-%Y%m%d-%H%M%S")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
        raise ValueError("生成批次需要单个目录名")
    batch = root / name
    try:
        batch.mkdir(parents=True)
    except FileExistsError:
        raise ValueError(f"拒绝覆盖已有封面批次：{batch}") from None
    python, toolkit = tool_python()
    script = args.image2_script or toolkit / "local/tools/image2.py"
    output = run_command([python, str(script), "--title", hook, "--summary", brief, "--role", "thumbnail",
                          "--guard", "light", "--thumb-guard", "r_plus", "--candidates", str(args.candidates),
                          "-o", str(batch / "candidate.png"), "--json"])
    generated = json.loads(output)
    if len(generated["outputs"]) != args.candidates:
        raise ValueError("image2 返回的候选数量不符")
    rows = []
    for index, item in enumerate(generated["outputs"], 1):
        file = batch / f"candidate-{index}.png"
        if Path(item["output"]).resolve() != file.resolve():
            raise ValueError(f"image2 返回了非预期的候选路径：{index}")
        with Image.open(file) as image:
            size = image.size
            image.load()
        rows.append({**item, "file": file.name, "width": size[0], "height": size[1],
                     **watermark_result(file, size)})
    sheet = contact_sheet(batch, rows)
    result = {"batch": str(batch), "path": str(sheet), "candidates": len(rows),
              "attempts": generated.get("attempts"), "outputs": rows}
    (batch / "batch-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    append_ledger(project, {"id": f"thumbnail-{name}", "sourceType": "image2", "tool": "image2", "kind": "thumbnail",
                            "path": str(sheet.relative_to(project)), "candidates": len(rows), "created_at": now()})
    return result


def select(args, project, root):
    if args.batch:
        requested = Path(args.batch).expanduser()
        batch = (requested if requested.is_absolute() else root / requested).resolve()
        if batch.parent != root.resolve():
            raise ValueError("批次必须位于项目的 thumbnails 目录")
    else:
        complete = (path.parent for path in root.glob("*/batch-manifest.json"))
        batch = max(complete, key=lambda path: ((path/"batch-manifest.json").stat().st_mtime_ns, path.name), default=None)
        if batch is None:
            raise ValueError("项目没有已完成的封面批次")
    file = batch / f"candidate-{args.select}.png"
    if not file.is_file():
        raise ValueError(f"未找到封面候选 #{args.select}")
    target = Path(args.output).expanduser() if args.output else root / "thumbnail-selected.jpg"
    if not target.is_absolute():
        target = project / target
    if target.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("导出路径需以 .jpg 或 .jpeg 结尾")
    with Image.open(file) as source:
        image = source.convert("RGB")
    for quality in range(94, 0, -1):
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= args.max_bytes:
            break
    else:
        raise ValueError(f"封面无法压缩至 {args.max_bytes} 字节")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    for size in PREVIEWS[1:]:
        ImageOps.pad(image, size, method=Image.Resampling.LANCZOS).save(target.with_name(f"{target.stem}-{size[0]}p.png"))
    result = {"path": str(target), "batch": str(batch), "selected": args.select, "bytes": len(data),
              "sha256": sha256(data).hexdigest(), "quality": quality}
    append_ledger(project, {**result, "id": "thumbnail-selected", "kind": "thumbnail", "tool": "thumbnail",
                            "sourceType": "image2", "created_at": now()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--title")
    parser.add_argument("--hook", help="封面唯一核心大字")
    parser.add_argument("--badge", help="可选的一枚极简数字胶囊")
    brief = parser.add_mutually_exclusive_group()
    brief.add_argument("--summary")
    brief.add_argument("--content-file", type=Path)
    parser.add_argument("--candidates", type=int, default=3)
    parser.add_argument("--batch")
    parser.add_argument("--image2-script", type=Path)
    parser.add_argument("--select", type=int)
    parser.add_argument("--output")
    parser.add_argument("--max-bytes", type=int, default=1_950_000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.candidates < 1 or (args.select is not None and args.select < 1):
        parser.error("候选数量与选择编号须为正整数")
    if not 0 < args.max_bytes < 2_000_000:
        parser.error("max-bytes 须小于 2000000 且大于 0")
    if args.select is not None and any((args.title, args.summary, args.content_file, args.hook, args.badge)):
        parser.error("生成候选和选定导出请分别执行")
    try:
        project = project_path(args.project)
        root = project / "thumbnails"
        result = select(args, project, root) if args.select is not None else generate(args, project, root)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False) if args.json else result["path"])


if __name__ == "__main__":
    main()
