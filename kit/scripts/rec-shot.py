#!/usr/bin/env python3
"""Deterministic, locally guarded macOS recording. Dry-run never creates a backend."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata

KIT = Path(__file__).resolve().parents[1]
KEYS = {"return": 36, "enter": 76, "tab": 48, "escape": 53,
        "left": 123, "right": 124, "down": 125, "up": 126,
        "home": 115, "end": 119, "pageup": 116, "pagedown": 121}
MODIFIERS = {"cmd": "command down", "ctrl": "control down",
             "alt": "option down", "shift": "shift down"}


class ShotError(RuntimeError):
    pass


def normalized(text):
    return "".join(unicodedata.normalize("NFC", text).split())


def region(value):
    if (not isinstance(value, list) or len(value) != 4
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not math.isfinite(x) for x in value)
            or value[2] <= 0 or value[3] <= 0):
        raise ShotError("region 须为 [x,y,w,h]，宽高必须大于 0")
    return value


def number(value, minimum: float = 0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ShotError("时间或坐标必须是有限数字，时间不能为负")


def words(value, label, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ShotError(f"{label} 须为非空字符串列表")


def text(value, label, empty=False):
    if not isinstance(value, str) or "\0" in value or (not empty and not value.strip()):
        raise ShotError(f"{label} 须为字符串")


def parse_key(value):
    text(value, "key")
    parts = value.lower().split("+")
    if any(x not in MODIFIERS for x in parts[:-1]) or parts[-1] not in KEYS:
        raise ShotError("key 只支持命名控制键及 cmd/ctrl/alt/shift 组合；输入文字请用 paste")
    return parts[:-1], parts[-1]


def sends(step):
    return (step.get("send", False)
            or (step["type"] == "key" and parse_key(step["key"])[1] in {"return", "enter"})
            or (step["type"] == "click_text" and normalized(step["text"]).lower() in {"发送", "send"}))


def validate_shot(shot):
    if not isinstance(shot, dict) or shot.get("version") != 1:
        raise ShotError("镜头单 version 必须为 1")
    target = shot.get("target", {})
    if not isinstance(target, dict):
        raise ShotError("缺少 target")
    text(target.get("process"), "target.process")
    words(target.get("title_contains"), "target.title_contains")
    region(target.get("region"))
    inp = target.get("input", {})
    if not isinstance(inp, dict):
        raise ShotError("缺少 target.input")
    region(inp.get("region"))
    text(inp.get("initial_text"), "initial_text", empty=True)
    text(inp.get("empty_text", ""), "empty_text", empty=True)
    checks = target.get("ocr", [])
    if not isinstance(checks, list):
        raise ShotError("target.ocr 须为列表")
    for check in checks:
        validate_ocr_guard(check)
    steps = shot.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ShotError("steps 不能为空")
    recording = False
    outputs = set()
    fields = {
        "guard": {"process", "title_contains", "region", "must_contain", "must_not_contain"},
        "click": {"x", "y", "send"}, "click_text": {"region", "text", "send"},
        "paste": {"text"}, "key": {"key"}, "wait": {"sec"},
        "wait_text": {"region", "text", "timeout"},
        "rec_start": {"region", "out"}, "rec_stop": set(),
    }
    for step in steps:
        if not isinstance(step, dict) or step.get("type") not in fields:
            raise ShotError("未知步骤类型")
        kind = step["type"]
        if set(step) - fields[kind] - {"type"}:
            raise ShotError(f"{kind} 含未知字段（不允许关闭守卫）")
        if "send" in step and not isinstance(step["send"], bool):
            raise ShotError("send 必须为布尔值")
        if kind == "guard":
            if "process" in step:
                text(step["process"], "process")
            if "title_contains" in step:
                words(step["title_contains"], "title_contains")
            if "region" in step or "must_contain" in step or "must_not_contain" in step:
                validate_ocr_guard(step)
        if kind in {"click_text", "wait_text", "rec_start"}:
            region(step.get("region"))
        if kind in {"paste", "click_text", "wait_text"}:
            text(step.get("text"), "text")
        if kind == "click":
            number(step.get("x"), -math.inf)
            number(step.get("y"), -math.inf)
        if kind == "key":
            parse_key(step.get("key"))
        if kind in {"wait", "wait_text"}:
            number(step.get("sec" if kind == "wait" else "timeout"))
        if kind == "rec_start":
            text(step.get("out"), "out")
            if recording or step["out"] in outputs:
                raise ShotError("不能嵌套录制或复用输出文件")
            recording = True
            outputs.add(step["out"])
        if kind == "rec_stop":
            if not recording:
                raise ShotError("rec_stop 前缺少 rec_start")
            recording = False
    if recording:
        raise ShotError("录制必须用 rec_stop 收尾")
    return shot


def validate_ocr_guard(check):
    if not isinstance(check, dict):
        raise ShotError("OCR guard 须为对象")
    region(check.get("region"))
    words(check.get("must_contain", []), "must_contain", allow_empty=True)
    words(check.get("must_not_contain", []), "must_not_contain", allow_empty=True)
    if not check.get("must_contain") and not check.get("must_not_contain"):
        raise ShotError("OCR guard 至少指定 must_contain 或 must_not_contain")


def build_plan(shot):
    """Pure plan, shared by dry-run and execution. Guards cannot be disabled."""
    validate_shot(shot)
    expected = shot["target"]["input"]["initial_text"]
    rows = []
    for index, step in enumerate(shot["steps"], 1):
        guarded = step["type"] not in {"wait", "rec_stop"}
        row = {"step": index, "action": step, "guards": []}
        if guarded:
            row["guards"] = [{"target": shot["target"], "input_equals": expected,
                              "extra": step if step["type"] == "guard" else None}]
        if step["type"] == "paste":
            row["chunks"] = [step["text"][i:i + 3] for i in range(0, len(step["text"]), 3)]
            row["chunk_guards"] = "每块粘贴前：窗口标题 + 当前输入框 OCR；pbpaste 必须完全一致"
            expected += step["text"]
            row["verify_after"] = expected
        if sends(step):
            if not normalized(expected):
                raise ShotError("发送前预期输入不能为空")
            row["send"] = True
            expected = ""
        rows.append(row)
    return rows


class MacBackend:
    def __init__(self, private_dir):
        if sys.platform != "darwin":
            raise ShotError("真实执行仅支持 macOS")
        self.private = Path(private_dir).expanduser().resolve()
        self.private.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.private.chmod(0o700)
        self.temp = tempfile.TemporaryDirectory(prefix="run-", dir=self.private)
        self.last_image = None
        self.recording = None

    def binary(self, folder, name):
        source = KIT / "tools" / folder / f"{name}.swift"
        output = source.with_suffix("")
        if not output.exists() or source.stat().st_mtime > output.stat().st_mtime:
            subprocess.run(["xcrun", "swiftc", "-O", str(source), "-o", str(output)], check=True)
        return str(output)

    def front(self):
        script = ('tell application "System Events"\n'
                  'set p to first application process whose frontmost is true\n'
                  'return (name of p) & linefeed & (name of front window of p)\nend tell')
        result = subprocess.check_output(["osascript", "-e", script], text=True).rstrip("\n").split("\n", 1)
        if len(result) != 2:
            raise ShotError("无法读取前台窗口")
        return result

    def capture(self, rect):
        path = Path(self.temp.name) / "guard.png"
        subprocess.run(["/usr/sbin/screencapture", "-x", "-R", ",".join(map(str, rect)), str(path)], check=True)
        self.last_image = path
        return path

    def ocr(self, rect):
        path = self.capture(rect)
        result = json.loads(subprocess.check_output([self.binary("ocr", "ocr"), str(path)], text=True))
        for item in result["results"]:
            x, y, w, h = item["box"]
            item["center"] = [rect[0] + (x + w / 2) * rect[2] / result["width"],
                              rect[1] + (y + h / 2) * rect[3] / result["height"]]
        return result["results"]

    def save_failure(self, rect):
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 1000000000}"
        dest = self.private / f"guard-failed-{stamp}.png"
        shutil.copy2(self.capture(rect), dest)
        dest.chmod(0o600)
        return str(dest)

    def click(self, x, y):
        subprocess.run([self.binary("rec", "mouse"), "click", str(x), str(y), "600"], check=True)

    def key(self, key):
        modifiers, name = parse_key(key)
        suffix = " using {" + ", ".join(MODIFIERS[x] for x in modifiers) + "}" if modifiers else ""
        subprocess.run(["osascript", "-e", f'tell application "System Events" to key code {KEYS[name]}{suffix}'], check=True)

    def copy_verified(self, chunk):
        subprocess.run(["pbcopy"], input=chunk.encode("utf-8"), check=True)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if subprocess.check_output(["pbpaste"]).decode("utf-8") == chunk:
                return
            time.sleep(0.05)
        raise ShotError("剪贴板内容未能完全匹配，停止粘贴")

    def paste_clipboard(self):
        subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'], check=True)
        time.sleep(0.15)

    def start_record(self, rect, output, log_dir):
        # Same native capture flags and cursor logger as tools/rec/rec.sh.
        logger_binary = self.binary("rec", "cursorlog")
        epoch = time.time()
        handle = (log_dir / "capture.log").open("wb")
        command = ["/usr/sbin/screencapture", "-v", "-x", "-R", ",".join(map(str, rect)), str(output)]
        recorder = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=handle, start_new_session=True)
        self.recording = {"recorder": recorder, "logger": None, "handle": handle, "epoch": epoch, "region": rect}
        try:
            self.recording["logger"] = subprocess.Popen(
                [logger_binary, "3600", str(log_dir / "cursor.json"), str(epoch), ",".join(map(str, rect))],
                stdout=subprocess.DEVNULL, stderr=handle, start_new_session=True)
            time.sleep(0.3)
            if recorder.poll() is not None:
                raise ShotError("录制进程提前退出，请检查私有日志及系统权限")
        except BaseException:
            self.stop_record()
            raise

    def stop_record(self):
        if self.recording is None:
            return {}
        state, self.recording = self.recording, None
        results, errors = {}, []
        try:
            for name in ["recorder", "logger"]:
                process = state[name]
                if process is None:
                    continue
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                else:
                    errors.append(f"{name} 在 rec_stop 前已退出")
                try:
                    results[name] = process.wait(timeout=15)
                    if results[name] not in {0, -signal.SIGINT}:
                        errors.append(f"{name} 退出码 {results[name]}")
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    errors.append(f"{name} 未能正常停止，素材可能不完整")
        finally:
            for name in ["recorder", "logger"]:
                process = state[name]
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
            state["handle"].close()
        if errors:
            raise ShotError("；".join(errors))
        return {"exit_codes": results, "launch_epoch": state["epoch"], "region_points": state["region"]}

    def probe(self, output):
        data = json.loads(subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,duration:format=duration", "-of", "json", str(output)], text=True))
        stream = data["streams"][0]
        return {"width": stream["width"], "height": stream["height"],
                "duration": float(stream.get("duration") or data["format"]["duration"])}

    def close(self):
        try:
            self.stop_record()
        finally:
            self.temp.cleanup()


class Runner:
    def __init__(self, shot, backend, clock=time.monotonic, sleep=time.sleep):
        self.shot, self.backend = shot, backend
        self.plan = build_plan(shot)
        self.clock, self.sleep = clock, sleep
        self.expected = shot["target"]["input"]["initial_text"]
        self.recording = None

    def event(self, kind, **details):
        if self.recording is not None:
            self.recording["events"].append({"t": round(self.clock() - self.recording["start"], 6), "type": kind, **details})
            self.write_events("recording")

    def write_events(self, state, **metadata):
        record = self.recording
        if record is None:
            raise ShotError("没有活动录制，不能写事件日志")
        payload = {"version": 1, "state": state, "file": record["out"].name,
                   "clock": "recording process launch; first frame offset uncalibrated",
                   "video_start_offset_seconds": None, "events": record["events"], **metadata}
        path = record["dir"] / "events.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(path)

    def fail(self, message):
        try:
            path = self.backend.save_failure(self.shot["target"]["region"])
            message += f"；私有截图：{path}"
        except Exception as exc:
            message += f"；截图未能保存：{type(exc).__name__}"
        raise ShotError(message)

    def front_guard(self, target):
        try:
            process, title = self.backend.front()
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.fail(f"无法读取前台窗口：{type(exc).__name__}")
        if process != target["process"] or any(value not in title for value in target["title_contains"]):
            self.fail("前台进程或目标窗口标题不符，已中止")

    def ocr_text(self, rect):
        try:
            return "\n".join(item["text"] for item in self.backend.ocr(rect))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.fail(f"无法完成区域 OCR：{type(exc).__name__}")

    def guard(self, extra=None):
        target = self.shot["target"]
        self.front_guard(target)
        inp = target["input"]
        actual = normalized(self.ocr_text(inp["region"]))
        expected = normalized(self.expected if self.expected else inp.get("empty_text", ""))
        if actual != expected:
            self.fail("输入框 OCR 与预期不符，已中止")
        checks = list(target.get("ocr", []))
        if extra:
            self.front_guard({"process": extra.get("process", target["process"]),
                              "title_contains": extra.get("title_contains", target["title_contains"])})
            if "region" in extra:
                checks.append(extra)
        for check in checks:
            actual = normalized(self.ocr_text(check["region"]))
            if (any(normalized(word) not in actual for word in check.get("must_contain", []))
                    or any(normalized(word) in actual for word in check.get("must_not_contain", []))):
                self.fail("区域 OCR 守卫不通过，已中止")
        self.front_guard(target)

    def start_record(self, step):
        expanded = os.path.expandvars(step["out"])
        if "$" in expanded:
            raise ShotError("输出路径包含未设置的环境变量")
        output = Path(expanded).expanduser().resolve()
        log_dir = output.with_suffix(output.suffix + ".rec")
        if output.exists() or log_dir.exists():
            raise ShotError("拒绝覆盖已有录制或日志")
        output.parent.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(mode=0o700)
        self.recording = {"out": output, "dir": log_dir, "start": self.clock(), "events": []}
        self.backend.start_record(step["region"], output, log_dir)
        self.event("rec_start", region=step["region"])

    def stop_record(self, failed=False):
        if self.recording is None:
            return
        self.event("rec_stop")
        capture = self.backend.stop_record()
        record = self.recording
        if failed:
            self.write_events("aborted", capture=capture)
            self.recording = None
            return
        video = self.backend.probe(record["out"])
        if video["width"] <= 0 or video["height"] <= 0 or video["duration"] <= 0:
            raise ShotError("录制文件没有有效视频")
        self.write_events("complete", video=video, capture=capture)
        index = record["out"].parent / "index.md"
        if not index.exists():
            index.write_text("| 文件 | 像素 | 时长 | 关键时间点（启动时钟，未校准） | 需模糊区域 |\n|---|---|---|---|---|\n")
        moments = "; ".join(f"{event['type']} {event['t']:.2f}s" for event in record["events"])
        filename = record["out"].name.replace("|", "\\|").replace("\n", " ")
        with index.open("a") as handle:
            handle.write(f"| {filename} | {video['width']}×{video['height']} | {video['duration']:.2f}s | {moments} |  |\n")
        self.recording = None

    def run(self):
        try:
            for row in self.plan:
                step, kind = row["action"], row["action"]["type"]
                if row["guards"]:
                    self.guard(step if kind == "guard" else None)
                if kind == "paste":
                    self.event("input_start")
                    for chunk in row["chunks"]:
                        self.backend.copy_verified(chunk)
                        self.guard()
                        self.backend.paste_clipboard()
                        self.expected += chunk
                    self.guard()
                    self.event("input_end", characters=len(step["text"]))
                elif kind in {"click", "click_text"}:
                    if kind == "click":
                        x, y = step["x"], step["y"]
                    else:
                        matches = [item for item in self.backend.ocr(step["region"])
                                   if normalized(item["text"]) == normalized(step["text"])]
                        if len(matches) != 1:
                            self.fail("click_text 未找到唯一文字框")
                        x, y = matches[0]["center"]
                    # OCR matching can take time: check again immediately before moving.
                    self.guard()
                    self.backend.click(x, y)
                    self.event("click", x=x, y=y)
                elif kind == "key":
                    self.backend.key(step["key"])
                elif kind == "wait":
                    self.sleep(step["sec"])
                elif kind == "wait_text":
                    deadline = self.clock() + step["timeout"]
                    while True:
                        self.guard()
                        if normalized(step["text"]) in normalized(self.ocr_text(step["region"])):
                            self.event("result", text=step["text"])
                            break
                        if self.clock() >= deadline:
                            self.fail("wait_text 超时")
                        self.sleep(min(2, deadline - self.clock()))
                elif kind == "rec_start":
                    self.start_record(step)
                elif kind == "rec_stop":
                    self.stop_record()
                if row.get("send"):
                    self.event("send")
                    self.expected = ""
        except BaseException:
            try:
                self.stop_record(failed=True)
            finally:
                self.backend.close()
            raise
        self.backend.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shot", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--private-dir", type=Path,
                        default=Path.home() / "Library/Application Support/yice-video/rec-shot/private")
    args = parser.parse_args(argv)
    try:
        shot = json.loads(args.shot.read_text())
        plan = build_plan(shot)
        if args.dry_run:
            print(json.dumps({"mode": "dry-run", "steps": plan}, ensure_ascii=False, indent=2))
            return 0
        Runner(shot, MacBackend(args.private_dir)).run()
        return 0
    except (ShotError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"rec-shot: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("rec-shot: 用户中止，录制已停止", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
