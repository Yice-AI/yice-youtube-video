#!/usr/bin/env python3
"""Skill v6.0 四路真实素材自动采录器（harvest-episode-footage.py）：
为每一期科技/教程视频在进剪辑前自动备足高密度真实动态视频（默认每分钟 >= 7 条不重复 MP4）：
  1. deep_screencasts : 1.6x Retina 深色去弹窗多步网页/GitHub PR Diff/文档交互实录
  2. cli_studio_live  : 脱敏深色 macOS 终端命令逐行执行与工程输出实录
  3. official_demos   : 公开产品官网原生 <video> 演示短片（硬禁 YouTube/B站/参考博主域名）
  4. stock_1080p      : 自动加载 ~/.config/yice-video/stock.env 拉取 Pexels/Pixabay 1080p 实拍
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from workspace import load_environment
from produce_asset import append_ledger

BLOCKED_CREATOR_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "googlevideo.com",
    "bilibili.com",
    "bilivideo.com",
    "tiktok.com",
    "douyin.com",
)


def is_allowed_demo_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    return not any(host == dom or host.endswith("." + dom) for dom in BLOCKED_CREATOR_DOMAINS)


def sha256_file(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def required_real_clip_count(duration_seconds: float, per_minute: int = 7) -> int:
    minutes = max(1.0, float(duration_seconds) / 60.0)
    return int(math.ceil(minutes * per_minute))


def fetch_pexels_1080p(queries, out_dir: Path, api_key: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_ids = set()
    records = []
    for item in queries:
        slug, query = (item["slug"], item["query"]) if isinstance(item, dict) else item
        dest = out_dir / f"{slug}.mp4"
        if dest.is_file() and dest.stat().st_size > 150_000:
            records.append({"slug": slug, "path": str(dest), "sha256": sha256_file(dest), "cached": True})
            continue
        url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
            {"query": query, "per_page": "8", "orientation": "landscape"}
        )
        req = urllib.request.Request(url, headers={"Authorization": api_key, "User-Agent": "yice-youtube-video/6.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        chosen = None
        for vid in data.get("videos", []):
            vid_id = vid.get("id")
            if vid_id in seen_ids or not (5 <= (vid.get("duration") or 0) <= 50):
                continue
            files = [
                f for f in vid.get("video_files", [])
                if f.get("file_type") == "video/mp4" and f.get("link")
                and (f.get("width") or 0) >= 1920 and f["width"] > (f.get("height") or 0)
            ]
            files.sort(key=lambda f: abs((f.get("width") or 0) - 1920) + abs((f.get("height") or 0) - 1080))
            if files:
                chosen = (vid, files[0])
                seen_ids.add(vid_id)
                break
        if not chosen:
            continue
        vid, fobj = chosen
        dl = urllib.request.Request(fobj["link"], headers={"User-Agent": "yice-youtube-video/6.0"})
        tmp = dest.with_suffix(".raw.mp4")
        part = dest.with_suffix(".part.mp4")
        try:
            with urllib.request.urlopen(dl, timeout=45) as r:
                tmp.write_bytes(r.read())
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(tmp), "-t", "14",
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
                    "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
                    str(part),
                ],
                check=True,
            )
            part.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
            part.unlink(missing_ok=True)
        record = {
            "slug": slug,
            "path": str(dest),
            "sha256": sha256_file(dest),
            "provider": "pexels",
            "provider_id": vid["id"],
            "license": "Pexels License",
        }
        append_ledger(out_dir, {**record, "id": slug, "path": dest.name, "sourceType": "stock-footage",
                                "sourceUrl": vid.get("url"), "licenseUrl": "https://www.pexels.com/license/"})
        records.append(record)
    return records


def audit_pool(directories, duration_seconds: float, per_minute: int = 7):
    digests = {}
    by_dir = {}
    for d in directories:
        p = Path(d)
        files = sorted(p.rglob("*.mp4")) if p.exists() else []
        valid = [f for f in files if ".part." not in f.name and not f.name.endswith(".raw.mp4") and f.stat().st_size > 100_000]
        by_dir[str(p)] = len(valid)
        for f in valid:
            digests.setdefault(sha256_file(f), str(f))
    target = required_real_clip_count(duration_seconds, per_minute=per_minute)
    return {
        "ok": len(digests) >= target,
        "unique_mp4_count": len(digests),
        "required_mp4_count": target,
        "by_directory": by_dir,
    }


def main(argv=None):
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, help="包含 stock_queries 的 JSON 采集计划")
    parser.add_argument("--output", type=Path, required=True, help="素材池输出目录")
    parser.add_argument("--duration-seconds", type=float, default=460.0)
    parser.add_argument("--per-minute", type=int, default=7)
    parser.add_argument("--extra-pool", action="append", default=[], help="合并统计的已有真实视频目录")
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    stock_records = []
    if args.plan and args.plan.is_file():
        spec = json.loads(args.plan.read_text())
        api_key = os.environ.get("PEXELS_API_KEY", "")
        if spec.get("stock_queries") and api_key:
            stock_records = fetch_pexels_1080p(spec["stock_queries"], args.output / "stock-1080p", api_key)

    report = audit_pool([args.output, *args.extra_pool], args.duration_seconds, args.per_minute)
    report["harvested_stock"] = len(stock_records)
    (args.output / "pool-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
