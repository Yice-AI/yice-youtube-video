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
        draw.text((28, top + 10), f"#{index} [{row['archetype']}]", font=title, fill="#f4f6fa")
        with Image.open(batch / row["file"]) as source:
            source = source.convert("RGB")
            for x, size, name in zip((28, 686, 1024), PREVIEWS, ("Main preview", "Desktop feed", "Mobile feed")):
                draw.text((x+310 if x==28 else x, top+17), f"{name}  {size[0]} px", font=label, fill="#bac7d4")
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


ARCHETYPES = {
    'treasure_fan': '右侧以三至四件高颜值实际视觉作品（深色科技视频画面、克莱因蓝瑞士网格演示页、精致图文排版卡）在干净深蓝黑背景中呈立体扇形错落展开，前大后小，边缘锐利干净。',
    'versus_shock': '左侧三分之一为灰暗单调的白底方框失败初稿并带一枚干净红色叉号；右侧三分之二以通透醒目的深色演示大屏与瑞士蓝白排版成品立体叠放突出，呈现同一份内容的前后质感反差。',
    'power_desk': '前景是一枚极简发光单行输入胶囊，右侧由近到远立体分层展开精致的演示页面、数据图表与竖版封面成品，深色纯净摄影棚背景，光影克制高级。',
}


def cover_brief(title, summary, hook=None, badge=None, archetype='treasure_fan'):
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
    description = ('唯一允许印在画面上的主文字为核心钩子「'+hook+'」'+
                   ('和左上角一枚极简胶囊「'+badge+'」' if badge else '，不添加其他标语')+'。'
                   '主文字使用现代平面几何无衬线粗黑体（第一行纯白、第二行明黄，干净利落，严禁塑料感3D厚立体倒角、严禁红底黄字促销贴、严禁毛笔刷痕），位于画面左侧，168px 缩图清晰易读。'
                   + ARCHETYPES[archetype] +
                   '严禁画无关的自然风景雪山或廉价水晶盾牌；用干净的现代软件设计界面与排版色块呈现成果，避免乱码小字。'
                   '右下 x>78%、y>80% 净空，只延续深色背景，不放信息主体、文字、数字或标志。'
                   '下面是仅供理解主题的背景材料，不印成标题：'+summary[:1000])
    return hook, description


REF_STYLES = (
    (
        "punchy_dark_number",
        "深邃蓝黑电光质感背景配细腻景深光效，既有爆款视觉冲击力又留有呼吸空间、不拥挤不呆板。"
        "左侧以超大立体电光蓝数字或核心词搭配纯白与亮黄撞色粗黑主标题，辅以一枚发光胶囊副标；"
        "右侧将参考图中的真实作品界面带细腻高光边框立体错落叠放，层次鲜活抓人眼球。",
    ),
    (
        "punchy_light_burst",
        "明亮通透的浅蓝白科技感渐变背景带轻快光束动势（拒绝死板灰白墙）。"
        "左侧高对比黑蓝撞色重磅主标题配醒目蓝底白字副标胶囊，版面松紧有度；"
        "右侧将参考图中的真实作品呈强透视破框扇形飞出，光影鲜活。",
    ),
    (
        "cinema_glow_fan",
        "暗调科技发布会光影背景，左侧超醒目白黄撞色重磅大字与极简副标条，干净有力不堆砌底部长句；"
        "右侧将参考图中的真实作品原件以发光悬浮视窗倾斜展开，主次分明。",
    ),
)


ASPECT_TARGETS = {
    "16:9": ((1920, 1080), "1792x1024", "YouTube 16:9 横版缩略图，左右分栏构图"),
    "4:3": ((1440, 1080), "1536x1152", "抖音 4:3 横封面，紧凑左右构图，左右两侧均留足 8% 安全边距防裁字"),
    "3:4": ((1080, 1440), "1152x1536", "抖音/小红书 3:4 竖封面，上下结构（上半区居中放大主标题，下半区立体叠放真实作品界面），左右两侧均留足 8% 安全边距绝不贴边裁字"),
}


def generate_with_refs(python, script, title, summary, refs, batch, count, aspect="16:9"):
    target_wh, req_size, layout_hint = ASPECT_TARGETS[aspect]
    helper = (
        "import base64, concurrent.futures, io, json, pathlib, sys, time, requests\n"
        "from PIL import Image, ImageOps\n"
        "payload = json.loads(sys.stdin.read())\n"
        "sys.path.insert(0, str(pathlib.Path(payload['script']).parent))\n"
        "import image2\n"
        "creds = image2.load_credentials()\n"
        "blobs = [(pathlib.Path(p).name, pathlib.Path(p).read_bytes(), 'image/png') for p in payload['refs']]\n"
        "tw, th = payload['target_wh']\n"
        "def one(job):\n"
        "  t0 = time.perf_counter()\n"
        "  style_name, style_desc, out_path = job['style'], job['desc'], job['out']\n"
        "  prompt = (\n"
        "    f'高点击率科技视频封面（{payload[\"layout_hint\"]}）。' + style_desc + ' '\n"
        "    f'主标题文字为：「{payload[\"title\"]}」，副标精炼为：「{payload[\"summary\"][:80]}」（数字不要重复写两遍）。'\n"
        "    '严格保持参考图中真实作品的版式、配色与文字细节；严禁脑补未出现在参考图里的第三方软件图标，严禁在右下角画任何时长数字（如 07:32）或占位框，右下角留净空。'\n"
        "  )\n"
        "  for sz in ([payload['req_size'], '1024x1536'] if tw < th else [payload['req_size'], '1536x1024', '1792x1024']):\n"
        "    resp = requests.post(f'{creds.base_url}/images/edits', headers={'Authorization': f'Bearer {creds.api_key}'},\n"
        "                         data={'model': creds.model, 'prompt': prompt, 'n': '1', 'size': sz}, files=[('image[]', b) for b in blobs], timeout=(30, 240))\n"
        "    if resp.ok: break\n"
        "  if not resp.ok:\n"
        "    raise RuntimeError(image2.redact(f'HTTP {resp.status_code}: {resp.text[:240]}', creds.sensitive_values))\n"
        "  item = resp.json()['data'][0]\n"
        "  raw = base64.b64decode(item['b64_json']) if item.get('b64_json') else requests.get(item['url'], timeout=60).content\n"
        "  with Image.open(io.BytesIO(raw)) as src:\n"
        "    ImageOps.fit(ImageOps.exif_transpose(src), (tw, th), method=Image.Resampling.LANCZOS).save(out_path, format='PNG')\n"
        "  return {'output': out_path, 'width': tw, 'height': th, 'model': creds.model, 'archetype': style_name, 'aspect': payload['aspect'], 'elapsed_seconds': round(time.perf_counter()-t0, 2)}\n"
        "with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(payload['jobs']))) as ex:\n"
        "  res = list(ex.map(one, payload['jobs']))\n"
        "print(json.dumps({'outputs': res, 'attempts': len(res)}))\n"
    )
    jobs = []
    for idx in range(1, count + 1):
        sname, sdesc = REF_STYLES[(idx - 1) % len(REF_STYLES)]
        jobs.append({"style": sname, "desc": sdesc, "out": str(batch / f"candidate-{idx}.png")})
    proc = subprocess.run(
        [python, "-c", helper],
        input=json.dumps({"script": str(script), "title": title, "summary": summary, "refs": [str(r) for r in refs],
                          "aspect": aspect, "target_wh": list(target_wh), "req_size": req_size, "layout_hint": layout_hint, "jobs": jobs}),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "image2 多图参考生成失败").strip())
    return json.loads(proc.stdout)


def generate(args, project, root):
    summary = args.content_file.read_text(encoding="utf-8") if args.content_file else args.summary
    if not (args.title and args.title.strip() and summary and summary.strip()):
        raise ValueError("生成需要 --title 和 --summary 或 --content-file")
    refs = []
    for raw_ref in (args.ref or ()):
        rp = Path(raw_ref).expanduser()
        rp = (rp if rp.is_absolute() else project / rp).resolve()
        if not rp.is_file():
            raise ValueError(f"参考图不存在：{raw_ref}")
        refs.append(rp)
    if len(refs) > 4:
        raise ValueError("参考图最多传 4 张核心成品原图，避免画面拥挤")
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
    rows = []
    attempts = 0
    direct_mode = args.archetype == "direct" and not args.hook and not args.badge
    if refs:
        generated = generate_with_refs(python, script, args.title.strip(), summary.strip(), refs, batch, args.candidates, aspect=args.aspect)
        attempts += generated.get("attempts", len(generated["outputs"]))
        for item in generated["outputs"]:
            file = Path(item["output"])
            with Image.open(file) as image:
                size = image.size
                image.load()
            rows.append({**item, "file": file.name, "width": size[0], "height": size[1],
                         **watermark_result(file, size)})
    else:
        if not direct_mode:
            hook, _ = cover_brief(args.title, summary, args.hook, args.badge)
        for index in range(1, args.candidates+1):
            file = batch / f'candidate-{index}.png'
            if direct_mode:
                archetype = "direct"
                call_title, call_summary = args.title.strip(), summary.strip()
            else:
                archetype = tuple(ARCHETYPES)[(index-1) % len(ARCHETYPES)] if args.archetype == 'diverse' else args.archetype
                _, call_summary = cover_brief(args.title, summary, hook, args.badge, archetype)
                call_title = hook
            output = run_command([python, str(script), '--title', call_title, '--summary', call_summary, '--role', 'thumbnail',
                                  '--guard', 'light', '--thumb-guard', 'r_plus', '--candidates', '1',
                                  '-o', str(file), '--json'])
            generated = json.loads(output)
            if len(generated['outputs']) != 1:
                raise ValueError('image2 返回的候选数量不符')
            item = generated['outputs'][0]
            source = Path(item['output']).resolve()
            if source != file.with_stem(file.stem + '-1').resolve():
                raise ValueError(f'image2 返回了非预期的候选路径：{index}')
            source.rename(file)
            item.update(output=str(file), archetype=archetype)
            attempts += generated.get('attempts', 1)
            with Image.open(file) as image:
                size = image.size
                image.load()
            rows.append({**item, "file": file.name, "width": size[0], "height": size[1],
                         **watermark_result(file, size)})
    sheet = contact_sheet(batch, rows)
    result = {"batch": str(batch), "path": str(sheet), "candidates": len(rows),
              "attempts": attempts, "outputs": rows}
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
    parser.add_argument("--archetype", choices=("direct", "diverse", *ARCHETYPES), default="direct")
    parser.add_argument("--aspect", choices=("16:9", "4:3", "3:4"), default="16:9", help="封面画幅：YouTube 16:9，抖音横封面 4:3、竖封面 3:4")
    parser.add_argument("--ref", action="append", help="传入 1–4 张片中真实成品截图，走 image2 多图参考生成")
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
