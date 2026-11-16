#!/usr/bin/env python3
"""One parameter file, deterministic shots. --dry-run never constructs a backend."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SPEC = importlib.util.spec_from_file_location("rec_shot_demo", Path(__file__).with_name("rec-shot.py"))
rec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rec)


def output_path(value):
    rec.text(value, "output_dir")
    expanded = os.path.expandvars(value)
    if "$" in expanded or not Path(expanded).expanduser().is_absolute():
        raise rec.ShotError("output_dir 必须是已展开的绝对路径")
    return Path(expanded).expanduser().resolve()


def validate_params(params):
    fields = {"version", "project", "output_dir", "process", "title_contains", "reference_window",
              "input", "ocr", "ui", "messages", "before", "after"}
    if not isinstance(params, dict) or params.get("version") != 1 or set(params) - fields:
        raise rec.ShotError("参数 version 必须为 1，且只能包含白名单字段")
    rec.text(params.get("project"), "project")
    output_path(params.get("output_dir"))
    for key in ["input", "ui"]:
        if not isinstance(params.get(key, {}), dict):
            raise rec.ShotError(f"{key} 须为对象")
    messages = params.get("messages")
    if not isinstance(messages, list) or not messages:
        raise rec.ShotError("messages 须为非空列表")
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"text", "completion_text", "timeout"}:
            raise rec.ShotError("每条消息只能含 text、completion_text、timeout")
        rec.text(message["text"], "message.text")
        rec.text(message["completion_text"], "completion_text")
        rec.number(message["timeout"])
        if message["timeout"] <= 0:
            raise rec.ShotError("timeout 必须大于 0")
    for name in ["before", "after"]:
        if not isinstance(params.get(name, []), list):
            raise rec.ShotError(f"{name} 须为镜头列表")
        for shot in params.get(name, []):
            if not isinstance(shot, dict) or set(shot) != {"name", "target", "steps"}:
                raise rec.ShotError("附加镜头只能含 name、target、steps")
            rec.text(shot["name"], "shot.name")
            if not isinstance(shot["target"], dict):
                raise rec.ShotError("附加镜头 target 须为对象")
            rec.region(shot["target"].get("region"))
            if not isinstance(shot["steps"], list) or not shot["steps"]:
                raise rec.ShotError("附加镜头 steps 不能为空")
            if any(not isinstance(step, dict) or step.get("type") in {"rec_start", "rec_stop"} for step in shot["steps"]):
                raise rec.ShotError("附加镜头的启停与输出由 rec-demo 统一管理")
    return params


def build_shots(params, destination=None):
    """Pure preflight, also used for bridge validation. No screen or file mutations."""
    validate_params(params)
    destination = Path(destination) if destination else output_path(params["output_dir"]) / "demo-take01"
    rect = rec.region(params.get("reference_window", [0, 0, 1200, 800]))
    x, y, w, h = rect
    target = {"process": params.get("process", "ChatGPT"),
              "title_contains": params.get("title_contains", [params["project"]]),
              "region": rect, "input": {"region": [x + w * .1, y + h * .7, w * .8, h * .15],
                                         "initial_text": "", **params.get("input", {})},
              "ocr": params.get("ocr", []), "ui": {"skip_text": "跳过", **params.get("ui", {})}}
    if target["input"]["initial_text"]:
        raise rec.ShotError("rec-demo 必须从空输入框开始")
    if not any(target["input"].get(key) for key in ["empty_text", "empty_texts", "suggestions"]):
        raise rec.ShotError("提供至少一种已知输入占位文字或建议，供自动定位")
    middle = []
    for i, message in enumerate(params["messages"], 1):
        middle.append({"name": f"message-{i:02}", "target": target, "steps": [
            {"type": "prepare_input"}, {"type": "paste", "text": message["text"]},
            {"type": "key", "key": "return"},
            {"type": "wait_text", "region": rect, "text": message["completion_text"],
             "timeout": message["timeout"], "fresh": True}]})
    result = []
    for i, item in enumerate([*params.get("before", []), *middle, *params.get("after", [])], 1):
        item = copy.deepcopy(item)
        shot = {"version": 1, "target": item["target"], "steps": [
            {"type": "rec_start", "region": item["target"]["region"], "out": str(destination / f"{i:02}-take.mov")},
            *item["steps"], {"type": "rec_stop"}]}
        rec.build_plan(shot)
        result.append({"name": item["name"], "shot": shot})
    return result


def calibrate(shot, backend):
    """Translate reference coordinates to the one matching, currently open window."""
    shot = copy.deepcopy(shot)
    target = shot["target"]
    reference = target["region"][:]
    for attempt in range(4):
        try:
            actual = backend.window(target["process"], target["title_contains"])
            break
        except (OSError, ValueError, rec.ShotError, subprocess.SubprocessError):
            if attempt == 3:
                raise
            time.sleep(.2)
    rx, ry, rw, rh = reference
    ax, ay, aw, ah = actual

    def point(x, y):
        return ax + (x - rx) * aw / rw, ay + (y - ry) * ah / rh

    def rect(value):
        x, y = point(*value[:2])
        return [x, y, value[2] * aw / rw, value[3] * ah / rh]

    target["region"] = actual
    target["input"]["region"] = rect(target["input"]["region"])
    for check in target.get("ocr", []):
        check["region"] = rect(check["region"])
    if "region" in target.get("ui", {}):
        target["ui"]["region"] = rect(target["ui"]["region"])
    for step in shot["steps"]:
        if "region" in step:
            step["region"] = rect(step["region"])
        if step["type"] == "click":
            step["x"], step["y"] = point(step["x"], step["y"])
    # A known placeholder/suggestion gives the initial input location. AX refines
    # its bounds after recording starts and it is safe to focus that input.
    if any(step["type"] == "prepare_input" for step in shot["steps"]):
        inp = target["input"]
        labels = {rec.normalized(value) for value in [inp.get("empty_text", ""),
                  *inp.get("empty_texts", []), *inp.get("suggestions", [])] if value}
        matches = [item for item in backend.ocr(actual) if rec.normalized(item["text"]) in labels]
        if len(matches) == 1:
            target["input"]["region"] = matches[0]["screen_box"]
        elif len(matches) > 1:
            raise rec.ShotError("输入框标定出现多个候选，停止")
        # With a known question card, Runner skips it after capture is ready.
    rec.build_plan(shot)
    return shot


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def run_demo(params, backend_factory=None, runner_factory=None):
    build_shots(params)  # Mandatory dry-run before any backend is constructed.
    root = output_path(params["output_dir"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for serial in range(1, 10000):
        folder = root / f"demo-take{serial:02}"
        try:
            folder.mkdir(mode=0o700)
            break
        except FileExistsError:
            continue
    else:
        raise rec.ShotError("无法保留新的录制目录")
    shots = build_shots(params, folder)
    write_json(folder / "dry-run.json", {"mode": "dry-run", "shots": shots})
    result = {"state": "working", "project": params["project"], "folder": str(folder), "segments": []}
    write_json(folder / "failure.json", {"state": "working", "failure": None})
    backend_factory = backend_factory or rec.MacBackend
    runner_factory = runner_factory or rec.Runner
    backend, runner, current = None, None, None
    try:
        for i, current in enumerate(shots, 1):
            runner = None
            backend = backend_factory(folder / "private")
            calibrated = calibrate(current["shot"], backend)
            plan = rec.build_plan(calibrated)  # Validate live calibration before recording.
            write_json(folder / f"{i:02}-shot.json", calibrated)
            write_json(folder / f"{i:02}-dry-run.json", {"mode": "dry-run", "steps": plan})
            runner = runner_factory(calibrated, backend)
            takes = runner.run()
            backend = None  # Runner has closed it, including any failed capture.
            result["segments"].append({"name": current["name"], "takes": takes})
            write_json(folder / "events.json", result)
    except BaseException as exc:
        failure = {"segment": current["name"] if current else None,
                   "step": runner.step if runner else "calibration", "error": str(exc), "screenshot": None}
        if runner and runner.failure:
            failure.update(runner.failure)
        elif backend:
            try:
                failure["screenshot"] = backend.save_failure(current["shot"]["target"]["region"])
            except Exception as screenshot_error:
                failure["screenshot_error"] = str(screenshot_error)
        result.update(state="failed", failure=failure)
        write_json(folder / "failure.json", {"state": "failed", "failure": failure})
        write_json(folder / "events.json", result)
        with (folder / "index.md").open("a") as stream:
            stream.write(f"\n停止在 {failure['segment']} / 步骤 {failure['step']}；详见 failure.json。\n")
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise rec.ShotError(f"录制停止；失败报告：{folder / 'failure.json'}") from exc
    finally:
        if backend:
            backend.close()
    result["state"] = "complete"
    write_json(folder / "events.json", result)
    write_json(folder / "failure.json", {"state": "complete", "failure": None})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("params", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    previous = None
    try:
        if args.params.stat().st_size > 1_048_576:
            raise rec.ShotError("参数文件不得超过 1 MiB")
        params = json.loads(args.params.read_text())
        shots = build_shots(params)
        if args.dry_run:
            print(json.dumps({"mode": "dry-run", "calibration": "deferred until real run; reference coordinates only",
                              "shots": shots}, ensure_ascii=False, indent=2))
            return 0
        previous = signal.signal(signal.SIGTERM, rec.interrupt_recording)
        print(json.dumps(run_demo(params), ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, TypeError, rec.ShotError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
