#!/usr/bin/env python3
"""复用 image2 原生透明生图；全案共用账本，付费请求前预留预算。"""
import argparse
import base64
import fcntl
import hashlib
import io
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from workspace import load_environment

WORKSPACE, TOOLKIT = load_environment()


def save(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def estimate_cost(usage):
    details = usage.get("input_tokens_details", {})
    output = usage.get("output_tokens_details", {})
    if not all(k in details for k in ["text_tokens", "image_tokens"]) or "image_tokens" not in output:
        raise ValueError("缺少分项 usage，不能确认实际费用")
    if output.get("text_tokens", 0):
        raise ValueError("未知的文本输出计费，停止自动续跑")
    return round((details["text_tokens"] * 5 + details["image_tokens"] * 8 + output["image_tokens"] * 30) / 1_000_000, 8)


def total(ledger):
    return round(sum(c.get("cost_usd", c["reserved_usd"]) for c in ledger["calls"]), 8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="JSON：items[{id,prompt,candidates,width,height}]")
    parser.add_argument("--case-dir", required=True, type=Path, help="本案所有批次共用目录与账本")
    parser.add_argument("--budget", required=True, type=float, help="全案美元上限，已有账本不允许改大")
    parser.add_argument("--reserve-per-image", type=float, default=.20, help="单次保守预算预留，默认 $0.20")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not all(math.isfinite(v) for v in [args.budget, args.reserve_per_image]) or not 0 < args.reserve_per_image <= args.budget:
        parser.error("预留须大于 0，且不超过全案预算")
    plan = json.loads(args.plan.read_text())
    jobs, seen = [], set()
    for item in plan["items"]:
        key = item["id"]
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", key) or key in seen:
            parser.error(f"道具 id 不合法或重复：{key}")
        seen.add(key)
        n, width, height = item.get("candidates", 1), item.get("width", 1536), item.get("height", 1024)
        if any(type(v) is not int or v < 1 for v in [n, width, height]) or max(width, height) > 4096:
            parser.error("候选数和尺寸须为正整数，尺寸不超过 4096")
        if not isinstance(item.get("prompt"), str) or not item["prompt"].strip() or len(item["prompt"]) > 6000:
            parser.error("prompt 须非空且不超过 6000 字符")
        for i in range(1, n + 1):
            job = {**item, "candidate": i, "key": f"{key}-{i:02}", "width": width, "height": height}
            job["request_hash"] = hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()
            jobs.append(job)
    case = args.case_dir.resolve()
    case.mkdir(parents=True, exist_ok=True)
    ledger_path = case / "image2-ledger.json"
    with (case / ".props.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {
            "budget_usd": args.budget, "calls": [], "cost_basis": "usage×文本输入5/图像输入8/图像输出30美元每百万token；非结算账单"}
        if args.budget > ledger["budget_usd"]:
            parser.error("已有全案账本不允许通过重跑提高预算")
        budget = min(args.budget, ledger["budget_usd"])
        previous = {c["key"]: c for c in ledger["calls"]}
        if any(c["state"] in ["pending", "unknown_cost", "received"] for c in ledger["calls"]):
            parser.error("存在未完成或未确认计费的请求，保留预留额并停止；先人工核对账单")
        pending = []
        for job in jobs:
            old = previous.get(job["key"])
            if old:
                if old["request_hash"] != job["request_hash"] or old["state"] != "success":
                    parser.error(f"已有候选不能被不同计划或失败重试覆盖：{job['key']}")
                if not (case / old["output"]).is_file():
                    parser.error(f"账本成功记录的文件丢失：{job['key']}")
            else:
                pending.append(job)
        if args.dry_run:
            print(json.dumps({"pending": len(pending), "spent_usd": total(ledger), "budget_usd": budget,
                              "next_request_allowed": bool(pending) and total(ledger) + args.reserve_per_image <= budget}, ensure_ascii=False))
            return
        sys.path.insert(0, str(TOOLKIT / "local/tools"))
        import image2
        from PIL import Image
        credentials = image2.load_credentials()
        for job in pending:
            if total(ledger) + args.reserve_per_image > budget + 1e-9:
                print(json.dumps({"state": "budget_stop", "spent_usd": total(ledger), "budget_usd": budget,
                                  "next": job["key"], "reserved_per_request": args.reserve_per_image}, ensure_ascii=False))
                return
            output = case / "images" / f"{job['key']}.png"
            if output.exists():
                parser.error(f"存在无账本图片，拒绝覆盖：{output}")
            entry = {"key": job["key"], "request_hash": job["request_hash"], "started_at": now(),
                     "state": "pending", "reserved_usd": args.reserve_per_image,
                     "output": str(output.relative_to(case)), "background": "transparent", "prompt": job["prompt"]}
            ledger["calls"].append(entry)
            save(ledger_path, ledger)
            original_post = image2.requests.post

            def recorded_post(*a, **kw):
                response = original_post(*a, **kw)
                entry["http_status"] = response.status_code
                try:
                    payload = response.json()
                    entry["usage"] = payload.get("usage", {})
                    entry["cost_usd"] = estimate_cost(entry["usage"])
                    entry["state"] = "received"
                    data = payload.get("data", [{}])[0]
                    if data.get("b64_json"):
                        with Image.open(io.BytesIO(base64.b64decode(data["b64_json"]))) as src:
                            entry["source_image"] = {"mode": src.mode, "size": list(src.size)}
                except (ValueError, TypeError, KeyError, IndexError):
                    entry["state"] = "unknown_cost"
                save(ledger_path, ledger)
                return response

            image2.requests.post = recorded_post
            try:
                image2.generate(job["prompt"], job["width"], job["height"], output, credentials, background="transparent")
                with Image.open(output) as src:
                    if "A" not in src.getbands() or src.getchannel("A").getextrema()[0] == 255:
                        raise ValueError("返回图片没有原生透明区域；已计费，不自动重试")
                    rgba = src.convert("RGBA")
                    check = Image.new("RGBA", rgba.size, "#252522")
                    check.alpha_composite(rgba)
                    check_path = case / "checks" / f"{job['key']}-charcoal.jpg"
                    check_path.parent.mkdir(exist_ok=True)
                    check.convert("RGB").save(check_path, quality=92)
                    entry["check"] = str(check_path.relative_to(case))
                    entry["alpha_extrema"] = list(rgba.getchannel("A").getextrema())
                if entry["state"] == "unknown_cost":
                    raise ValueError("图片已保存，但费用未确认，停止后续请求")
                entry["state"] = "success"
                entry["finished_at"] = now()
                save(ledger_path, ledger)
                print(json.dumps({"output": str(output), "spent_usd": total(ledger), "budget_usd": budget}, ensure_ascii=False))
                if entry["cost_usd"] > args.reserve_per_image:
                    raise ValueError("服务实际费用超过预留估计，停止后续请求；请核对网关定价")
            except Exception as exc:
                if entry["state"] != "unknown_cost":
                    entry["state"] = "error" if "cost_usd" in entry else "unknown_cost"
                entry["error"] = image2.redact(str(exc), credentials.sensitive_values)
                save(ledger_path, ledger)
                raise SystemExit(entry["error"]) from None
            finally:
                image2.requests.post = original_post


if __name__ == "__main__":
    main()
