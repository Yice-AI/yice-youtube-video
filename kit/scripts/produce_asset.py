#!/usr/bin/env python3
"""剪辑时按需生产素材，并以同一账本执行整期预算守卫。"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


KINDS = {"web-cam", "metaphor-image", "prop-cutout", "motion-video", "web-capture", "stock-footage", "rec-task"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def project_path(value):
    path = Path(value or os.environ.get("YICE_EPISODE", ".")).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_path(project):
    return project / "asset-ledger.jsonl"


def read_ledger(project):
    path = ledger_path(project)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_ledger(project, entry):
    path = ledger_path(project)
    rows = read_ledger(project)
    rows = [row for row in rows if row.get("id") != entry["id"]]
    rows.append(entry)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(path)


def budget_state(rows, image_budget, stock_budget):
    image_spent = sum(float(row.get("cost_usd", 0) or 0) for row in rows
                      if row.get("sourceType") == "image2")
    stock_calls = sum(int(row.get("api_calls", 0) or 0) for row in rows
                      if row.get("sourceType") == "stock-footage")
    if image_spent > image_budget + 1e-9:
        raise RuntimeError(f"image2 累计费用 ${image_spent:.4f} 已超过 ${image_budget:.2f} 上限")
    if stock_calls >= stock_budget:
        raise RuntimeError(f"图库 API 已达到 {stock_budget} 次本期上限")
    return image_spent, stock_calls


def modal_guard():
    value = os.environ.get("YICE_MODAL_SPEND_LIMIT_USD")
    if value is None:
        guard = os.environ.get("YICE_MODAL_GUARD_FILE")
        if guard and Path(guard).is_file():
            value = json.loads(Path(guard).read_text()).get("spend_limit_usd")
    if str(value) != "0":
        raise RuntimeError("Modal spend_limit_usd 未核验为 0，拒绝启动云端视频生产")


def tool_python():
    if __package__:
        from .workspace import load_environment
    else:
        from workspace import load_environment
    _, toolkit = load_environment()
    candidate = Path(os.environ.get("YICE_TOOLKIT_PYTHON", toolkit / ".venv/bin/python"))
    return str(candidate if candidate.exists() else sys.executable), toolkit


def run_command(command, *, timeout=900):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout or "命令失败").strip()[-1200:]
        raise RuntimeError(f"素材工具失败：{detail}")
    return result.stdout.strip()


def output_file(project, kind, requested=None, suffix=".mp4"):
    if requested:
        path = Path(requested).expanduser()
        if not path.is_absolute():
            path = project / path
    else:
        path = project / "assets" / kind / f"asset-{int(time.time())}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"拒绝覆盖已有素材：{path}")
    return path


def produce(args, project, rows):
    if args.kind == "web-cam":
        command = ["node", str(Path(__file__).with_name("record-web-cam.mjs")),
                   "--project", str(project), "--id", args.id, "--seconds", str(args.seconds if args.seconds is not None else args.duration)]
        for key in ("url", "scene", "source", "highlight", "actions", "fps"):
            value = getattr(args, key)
            if value is not None:
                command.extend(["--" + key, str(value)])
        return json.loads(run_command(command))
    prompt = (args.prompt or "").strip()
    source = args.source or args.url or args.query or ""
    entry = {"id": args.id, "kind": args.kind, "sourceType": args.kind,
             "tool": "produce-asset", "prompt_or_url": source,
             "path": "", "width": args.width, "height": args.height,
             "duration": args.duration, "license": args.license or "待核对",
             "cost_usd": 0.0, "api_calls": 0, "created_at": now()}
    python, toolkit = tool_python()
    if args.kind == "metaphor-image":
        if not prompt:
            raise RuntimeError("metaphor-image 需要 --prompt")
        spent, _ = budget_state(rows, args.image_budget, args.stock_budget)
        if spent + args.reserve_image > args.image_budget + 1e-9:
            raise RuntimeError("image2 预算不足，拒绝发起请求")
        path = output_file(project, args.kind, args.output, ".png")
        command = [python, str(toolkit / "local/tools/image2.py"), "--prompt", prompt,
                   "--width", str(args.width or 1920), "--height", str(args.height or 1080),
                   "--output", str(path), "--aspect", args.aspect, "--json"]
        output = run_command(command, timeout=600)
        metadata = json.loads(output.splitlines()[-1]) if output else {}
        entry.update(sourceType="image2", tool="image2", path=str(path), width=metadata.get("width", args.width or 1920),
                     height=metadata.get("height", args.height or 1080), model=metadata.get("model", "gpt-image-2"),
                     elapsed_seconds=metadata.get("elapsed_seconds"), cost_usd=args.cost)
    elif args.kind == "prop-cutout":
        plan = args.plan or args.input
        if not plan:
            raise RuntimeError("prop-cutout 需要 --plan 指向 props.py 计划")
        path = output_file(project, args.kind, args.output, ".json")
        run_command([python, str(Path(__file__).with_name("props.py")), plan,
                     "--case-dir", str(path.parent), "--budget", str(args.image_budget)], timeout=1800)
        entry.update(tool="props.py", path=str(path.parent), sourceType="image2")
    elif args.kind == "motion-video":
        modal_guard()
        if not prompt:
            raise RuntimeError("motion-video 需要 --prompt")
        path = output_file(project, args.kind, args.output, ".mp4")
        frames = 1 + 8 * max(1, round(args.duration * 24 / 8))
        command = [python, str(toolkit / "tools/ltx2.py"), "--prompt", prompt, "--cloud", "modal",
                   "--width", str(args.width), "--height", str(args.height), "--num-frames", str(frames),
                   "--quality", args.quality, "--output", str(path), "--no-open", "--json"]
        run_command(command, timeout=1800)
        entry.update(tool="ltx2.py", path=str(path), sourceType="generated-video", cost_usd=args.cost)
    elif args.kind == "web-capture":
        if not args.url:
            raise RuntimeError("web-capture 需要 --url")
        directory = project / "assets" / "web" / args.id
        run_command(["node", str(Path(__file__).with_name("capture-web.mjs")), "--project", str(project),
                     "--url", args.url, "--id", args.id, "--scene", args.scene, "--seconds", str(args.duration)], timeout=900)
        entry.update(tool="capture-web.mjs", path=str(directory), sourceType="web_capture", duration=args.duration)
    elif args.kind == "stock-footage":
        if not args.query:
            raise RuntimeError("stock-footage 需要 --query")
        _, calls = budget_state(rows, args.image_budget, args.stock_budget)
        if calls + 1 > args.stock_budget:
            raise RuntimeError("图库 API 调用已达到 60 次本期上限")
        directory = project / "assets" / "stock" / args.id
        filters = ["--sources", args.source] if args.source in {"pexels", "pixabay"} else []
        run_command(["node", str(Path(__file__).with_name("find-media.mjs")), "--q", args.query,
                     *filters, "--min-width", str(args.width), "--min-height", str(args.height),
                     "--type", args.media_type, "--n", str(args.count), "--out", str(directory),
                     "--project", str(project)], timeout=900)
        entry.update(tool="find-media.mjs", path=str(directory), sourceType="stock-footage", api_calls=1)
    elif args.kind == "rec-task":
        path = output_file(project, args.kind, args.output, ".json")
        payload = {"id": args.id, "kind": "rec-task", "project": args.input or str(project),
                   "prompt": prompt, "created_at": now()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        entry.update(tool="rec-shot", path=str(path), sourceType="recording")
    if not entry["path"]:
        raise RuntimeError("素材工具没有返回产物路径")
    try:
        entry["path"] = str(Path(entry["path"]).resolve().relative_to(project))
    except ValueError:
        entry["path"] = str(Path(entry["path"]).resolve())
    append_ledger(project, entry)
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=sorted(KINDS), required=True)
    parser.add_argument("--project")
    parser.add_argument("--id", default="asset")
    parser.add_argument("--prompt", "-p")
    parser.add_argument("--highlight")
    parser.add_argument("--actions")
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--url")
    parser.add_argument("--query")
    parser.add_argument("--source")
    parser.add_argument("--output", "-o")
    parser.add_argument("--input")
    parser.add_argument("--plan")
    parser.add_argument("--scene", default="S1")
    parser.add_argument("--license")
    parser.add_argument("--width", "-W", type=int, default=1920)
    parser.add_argument("--height", "-H", type=int, default=1080)
    parser.add_argument("--aspect", choices=["16:9", "9:16", "1:1", "4:3", "3:2"], default="16:9")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--media-type", choices=["photo", "video"], default="video")
    parser.add_argument("--quality", choices=["fast", "standard"], default="fast")
    parser.add_argument("--image-budget", type=float, default=5.0)
    parser.add_argument("--stock-budget", type=int, default=60)
    parser.add_argument("--reserve-image", type=float, default=.20)
    parser.add_argument("--cost", type=float, default=0.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.duration is None:
        args.duration = 6 if args.kind == "web-cam" else 5
    if args.width < 1 or args.height < 1 or args.duration <= 0 or args.cost < 0:
        parser.error("尺寸、时长和费用必须为正数")
    project = project_path(args.project)
    try:
        result = produce(args, project, read_ledger(project))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False) if args.json else result["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
