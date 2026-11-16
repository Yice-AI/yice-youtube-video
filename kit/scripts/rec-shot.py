#!/usr/bin/env python3
"""Deterministic, locally guarded macOS recording. Dry-run never creates a backend."""
import argparse
import fcntl
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
CAPTURE_LOCK = Path.home() / "Library/Application Support/yice-video/capture.lock"
# Only these glyph variants are interchangeable. Never discard '@' or words.
CHAR_EQUIVALENTS = str.maketrans({
    "＠": "@", "﹫": "@", "“": '"', "”": '"', "＂": '"',
    "‘": "'", "’": "'", "＇": "'", "，": ",", "：": ":",
    "！": "!", "？": "?", "（": "(", "）": ")", "\u3000": " ",
})
KEYS = {"return": 36, "enter": 76, "tab": 48, "escape": 53,
        "left": 123, "right": 124, "down": 125, "up": 126,
        "home": 115, "end": 119, "pageup": 116, "pagedown": 121}
MODIFIERS = {"cmd": "command down", "ctrl": "control down",
             "alt": "option down", "shift": "shift down"}


class ShotError(RuntimeError):
    pass


def normalized(text):
    return "".join(unicodedata.normalize("NFC", exact_text(text)).split())


def exact_text(value):
    """Send comparison preserves whitespace, case and all non-table characters."""
    return value.translate(CHAR_EQUIVALENTS)


def trim_bounds(events, duration, padding=0.4):
    active = {"click", "key", "input_start", "input_end", "send", "result", "ui_recovery"}
    times = [event["t"] for event in events if event["type"] in active]
    if not times:
        return 0, duration
    start = max(0, min(times) - padding)
    end = min(duration, max(times) + padding)
    return (start, end) if end > start else (0, duration)


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
    for key in ["suggestions", "empty_texts"]:
        words(inp.get(key, []), key, allow_empty=True)
    ui = target.get("ui", {})
    if not isinstance(ui, dict):
        raise ShotError("target.ui 须为对象")
    if ui:
        region(ui.get("region", target["region"]))
        words(ui.get("question_markers", []), "question_markers", allow_empty=True)
        words(ui.get("forbidden", []), "forbidden", allow_empty=True)
        text(ui.get("skip_text", "跳过"), "skip_text")
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
        "click": {"x", "y", "send"}, "click_text": {"region", "text", "send", "timeout"},
        "paste": {"text"}, "key": {"key"}, "wait": {"sec"},
        "prepare_input": set(), "wait_text": {"region", "text", "timeout", "fresh"},
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
        if kind == "click_text":
            number(step.get("timeout", 0))
        if "fresh" in step and not isinstance(step["fresh"], bool):
            raise ShotError("fresh 须为布尔值")
        if kind in {"paste", "prepare_input", "key", "click", "click_text"} and not recording:
            raise ShotError("输入和点击前必须先 rec_start 确认开录")
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
        if step["type"] == "prepare_input":
            expected = ""
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
        self.capture_lock = None

    def binary(self, folder, name):
        source = KIT / "tools" / folder / f"{name}.swift"
        output = source.with_suffix("")
        if not output.exists() or source.stat().st_mtime > output.stat().st_mtime:
            subprocess.run(["xcrun", "swiftc", "-O", str(source), "-o", str(output)], check=True)
        return str(output)

    def front(self):
        script = ('tell application "System Events"\n'
                  'set p to first application process whose frontmost is true\n'
                  'set w to value of attribute "AXFocusedWindow" of p\n'
                  'return (name of p) & linefeed & (name of w)\nend tell')
        result = subprocess.check_output(["osascript", "-e", script], text=True).rstrip("\n").split("\n", 1)
        if len(result) != 2 or not all(x.strip() and x != "missing value" for x in result):
            raise ShotError("无法读取前台窗口")
        return result

    def window(self, process, titles):
        """Select one already-open, matching window; never launch an app or navigate."""
        script = '''on run argv
tell application "System Events"
set p to application process (item 1 of argv)
set candidates to {}
repeat with w in windows of p
set matches to true
repeat with token in items 2 thru -1 of argv
if name of w does not contain (contents of token) then set matches to false
end repeat
if matches then set end of candidates to contents of w
end repeat
if count of candidates is not 1 then error "Target window is not unique"
set w to item 1 of candidates
set frontmost of p to true
perform action "AXRaise" of w
set xy to position of w
set wh to size of w
return (item 1 of xy as text) & "," & (item 2 of xy as text) & "," & (item 1 of wh as text) & "," & (item 2 of wh as text)
end tell
end run'''
        return region([float(x) for x in subprocess.check_output(
            ["osascript", "-e", script, process, *titles], text=True).strip().split(",")])

    def has_modal(self):
        script = '''tell application "System Events"
set p to first application process whose frontmost is true
set w to value of attribute "AXFocusedWindow" of p
return ((count of sheets of w) > 0) or ((value of attribute "AXSubrole" of w) is "AXDialog")
end tell'''
        return subprocess.check_output(["osascript", "-e", script], text=True).strip() == "true"

    def input_bounds(self):
        script = '''tell application "System Events"
set p to first application process whose frontmost is true
set e to value of attribute "AXFocusedUIElement" of p
if role of e is not in {"AXTextArea", "AXTextField", "AXComboBox"} then error "Focus is not a text input"
set xy to position of e
set wh to size of e
return (item 1 of xy as text) & "," & (item 2 of xy as text) & "," & (item 1 of wh as text) & "," & (item 2 of wh as text)
end tell'''
        return region([float(x) for x in subprocess.check_output(
            ["osascript", "-e", script], text=True).strip().split(",")])

    def read_input(self):
        # Do not use OCR as the final sending authority. Preserve the paste chunk.
        previous = subprocess.check_output(["pbpaste"])
        sentinel = f"rec-shot-empty-{time.time_ns()}"
        try:
            self.copy_verified(sentinel)
            subprocess.run(["osascript", "-e", 'tell application "System Events"\n'
                            'keystroke "a" using command down\nkeystroke "c" using command down\nend tell'], check=True)
            time.sleep(0.15)
            value = subprocess.check_output(["pbpaste"]).decode("utf-8")
            self.key("right")
            return "" if value == sentinel else value
        finally:
            subprocess.run(["pbcopy"], input=previous, check=True)

    def clear_input(self):
        subprocess.run(["osascript", "-e", 'tell application "System Events"\n'
                        'keystroke "a" using command down\nkey code 51\nend tell'], check=True)
        time.sleep(0.15)

    def recording_alive(self):
        return self.recording is not None and all(
            self.recording[key] is not None and self.recording[key].poll() is None
            for key in ["recorder", "logger"])

    def capture_process(self, command, handle):
        # A background shell may inherit SIGINT=IGNORE. Reset it before exec.
        reset = "import os,signal,sys; signal.signal(signal.SIGINT,signal.SIG_DFL); os.execv(sys.argv[1],sys.argv[1:])"
        return subprocess.Popen([sys.executable, "-c", reset, *command],
                                stdout=subprocess.DEVNULL, stderr=handle)

    def acquire_capture(self):
        CAPTURE_LOCK.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = os.fdopen(os.open(CAPTURE_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), "a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ShotError("已有 toolkit 录制正在运行，拒绝重叠录制") from exc
        self.capture_lock = handle

    def release_capture(self):
        handle = getattr(self, "capture_lock", None)
        if handle:
            handle.close()
            self.capture_lock = None

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
            item["screen_box"] = [rect[0] + x * rect[2] / result["width"],
                                  rect[1] + y * rect[3] / result["height"],
                                  w * rect[2] / result["width"], h * rect[3] / result["height"]]
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
        self.acquire_capture()
        epoch = time.time()
        command = ["/usr/sbin/screencapture", "-v", "-x", "-R", ",".join(map(str, rect)), str(output)]
        handle = None
        try:
            handle = (log_dir / "capture.log").open("wb")
            launch = time.monotonic()
            recorder = self.capture_process(command, handle)
        except BaseException:
            if handle:
                handle.close()
            self.release_capture()
            raise
        self.recording = {"recorder": recorder, "logger": None, "handle": handle, "epoch": epoch, "region": rect}
        try:
            self.recording["logger"] = self.capture_process(
                [logger_binary, "3600", str(log_dir / "cursor.json"), str(epoch), ",".join(map(str, rect))],
                handle)
            deadline, previous = launch + 8, 0
            while time.monotonic() < deadline:
                if not self.recording_alive():
                    raise ShotError("录制进程提前退出，请检查私有日志及系统权限")
                size = output.stat().st_size if output.exists() else 0
                if previous > 0 and size > previous:
                    return {"ready": True, "launch_monotonic": launch}
                previous = size
                time.sleep(0.1)
            raise ShotError("未确认录制文件持续写入，禁止输入或发送")
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
            for name in ["recorder", "logger"]:
                process = state[name]
                if process is None:
                    continue
                try:
                    results[name] = process.wait(timeout=5)
                    if results[name] not in {0, -signal.SIGINT}:
                        errors.append(f"{name} 退出码 {results[name]}")
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    errors.append(f"{name} 停止超时，已强制结束；素材需检查")
        finally:
            for name in ["recorder", "logger"]:
                process = state[name]
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)
            state["handle"].close()
            self.release_capture()
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

    def trim(self, source, output, start, end):
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-ss", str(start),
                        "-i", str(source), "-t", str(end - start), "-map", "0:v:0", "-map", "0:a?",
                        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac",
                        "-movflags", "+faststart", str(output)], check=True)

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
        self.recording, self.failure = None, None
        self.step, self.completed, self.baselines = 0, [], {}
        self.prepared = False

    def event(self, kind, **details):
        if self.recording is not None:
            self.recording["events"].append({"t": round(self.clock() - self.recording["start"], 6), "type": kind, **details})
            self.write_events("recording")

    def write_events(self, state, **metadata):
        record = self.recording
        payload = {"version": 1, "state": state, "file": record["out"].name,
                   "clock": "recording process launch; first frame offset uncalibrated",
                   "video_start_offset_seconds": None, "events": record["events"], **metadata}
        path = record["dir"] / "events.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(path)

    def fail(self, message):
        self.failure = {"step": self.step, "error": message, "screenshot": None}
        try:
            path = self.backend.save_failure(self.shot["target"]["region"])
            self.failure["screenshot"] = path
            message += f"；私有截图：{path}"
        except Exception as exc:
            self.failure["screenshot_error"] = type(exc).__name__
        raise ShotError(message)

    def front_guard(self, target):
        for attempt in range(4):  # First read + three retries, only for unreadable titles.
            try:
                process, title = self.backend.front()
                if not title.strip() or title == "missing value":
                    raise ShotError("窗口标题暂不可读")
            except (OSError, ValueError, ShotError, subprocess.SubprocessError) as exc:
                if attempt == 3:
                    self.fail(f"无法读取前台窗口，重试 3 次失败：{type(exc).__name__}")
                self.sleep(0.2)
                continue
            if process != target["process"] or any(value not in title for value in target["title_contains"]):
                self.fail("前台进程或目标窗口标题不符，已中止")
            return

    def require_recording(self):
        if not self.recording or not self.recording.get("ready") or not self.backend.recording_alive():
            self.fail("录屏未确认开始或已经退出，禁止输入、点击和发送")

    def ocr_text(self, rect):
        try:
            return "\n".join(item["text"] for item in self.backend.ocr(rect))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.fail(f"无法完成区域 OCR：{type(exc).__name__}")

    def question_card(self):
        if self.backend.has_modal():
            self.fail("未知弹窗，停止并等待人工处理")
        target = self.shot["target"]
        ui = target.get("ui", {})
        if not ui:
            return None
        items = self.backend.ocr(ui.get("region", target["region"]))
        content = normalized("\n".join(item["text"] for item in items))
        if any(normalized(word) in content for word in ui.get("forbidden", [])):
            self.fail("出现禁止或未知界面状态")
        markers = ui.get("question_markers", [])
        known = any(normalized(word) in content for word in markers)
        matches = [item for item in items if normalized(item["text"]) == normalized(ui.get("skip_text", "跳过"))]
        card_controls = {"跳过", "skip", "提交", "submit", "允许", "allow", "批准", "approve"}
        unknown_control = any(normalized(item["text"]).lower() in card_controls for item in items)
        if matches or known or unknown_control:
            if not known or len(matches) != 1:
                self.fail("未知提问卡片或跳过按钮不唯一")
            return matches[0]["center"]
        return None

    def input_labels(self):
        inp = self.shot["target"]["input"]
        return [inp.get("empty_text", ""), *inp.get("empty_texts", []), *inp.get("suggestions", [])]

    def focus_input(self):
        self.require_recording()
        target, inp = self.shot["target"], self.shot["target"]["input"]
        labels = {normalized(label) for label in self.input_labels() if label.strip()}
        actual = normalized(self.ocr_text(inp["region"]))
        if actual in labels:
            x, y, w, h = inp["region"]
            point = [x + w / 2, y + h / 2]
        else:
            matches = [item for item in self.backend.ocr(target["region"]) if normalized(item["text"]) in labels]
            if len(matches) != 1:
                # Already focused and genuinely empty is safe; a blank arbitrary area is not.
                bounds = self.backend.input_bounds()
                if actual or bounds != inp["region"]:
                    self.fail("找不到唯一的已知输入框，禁止盲点")
                return
            point = matches[0]["center"]
        self.front_guard(target)
        self.require_recording()
        self.backend.click(*point)
        inp["region"] = self.backend.input_bounds()
        self.check_input_bounds()

    def check_input_bounds(self):
        target, inp = self.shot["target"], self.shot["target"]["input"]
        bounds = self.backend.input_bounds()
        x, y, w, h = bounds
        tx, ty, tw, th = target["region"]
        ix, iy, iw, ih = inp["region"]
        if (x < tx or y < ty or x + w > tx + tw or y + h > ty + th
                or min(x + w, ix + iw) <= max(x, ix) or min(y + h, iy + ih) <= max(y, iy)):
            self.fail("输入焦点离开已确认的输入框")
        inp["region"] = bounds

    def verify_input(self):
        self.require_recording()
        self.front_guard(self.shot["target"])
        self.check_input_bounds()
        actual = self.backend.read_input()
        self.front_guard(self.shot["target"])
        if exact_text(actual) != exact_text(self.expected):
            self.fail("发送前逐字核对不一致（等价表之外不放宽）")

    def prepare_input(self):
        if self.expected:
            self.fail("准备输入时已有未发送文字，拒绝清除")
        self.require_recording()
        self.focus_input()
        # Always clear the selection/suggestion once. Never click again after this.
        self.front_guard(self.shot["target"])
        self.require_recording()
        self.backend.clear_input()
        self.verify_input()
        self.prepared = True
        self.event("ui_recovery", action="clear_suggestion_and_selection")

    def guard(self, extra=None, allow_card=False):
        target, inp = self.shot["target"], self.shot["target"]["input"]
        self.front_guard(target)
        card = self.question_card()
        if card and self.recording and self.recording.get("ready"):
            if self.expected:
                self.fail("输入途中出现提问卡片")
            self.require_recording()
            self.front_guard(target)
            self.backend.click(*card)
            self.event("ui_recovery", action="skip_known_question")
            self.sleep(0.2)
            if self.question_card():
                self.fail("跳过后提问卡片仍存在")
            self.focus_input()
            self.prepared = False
            card = None
        if card and not allow_card:
            self.fail("提问卡片只能在确认开录后处理")
        if not card:
            if self.prepared:
                self.check_input_bounds()
            actual = normalized(self.ocr_text(inp["region"]))
            allowed = {normalized(self.expected)} if self.expected else {"", *map(normalized, self.input_labels())}
            if actual not in allowed:
                # OCR alone may omit '@'. Require exact clipboard readback, never ignore it.
                if self.expected and actual == normalized(self.expected).replace("@", ""):
                    self.verify_input()
                else:
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
        if self.recording:
            self.fail("已有活动录制")
        expanded = os.path.expandvars(step["out"])
        if "$" in expanded:
            raise ShotError("输出路径包含未设置的环境变量")
        requested = Path(expanded).expanduser().resolve()
        requested.parent.mkdir(parents=True, exist_ok=True)
        for serial in range(1, 10000):
            output = requested if serial == 1 else requested.with_name(f"{requested.stem}-take{serial:02}{requested.suffix}")
            log_dir = output.with_suffix(output.suffix + ".rec")
            if output.exists() or output.is_symlink():
                continue
            try:
                log_dir.mkdir(mode=0o700)
            except FileExistsError:
                continue
            if output.exists():
                log_dir.rmdir()
                continue
            break
        else:
            raise ShotError("无法保留唯一输出名")
        self.recording = {"out": output, "dir": log_dir, "start": self.clock(), "events": [], "ready": False}
        ready = self.backend.start_record(step["region"], output, log_dir)
        if not ready or ready.get("ready") is not True:
            self.fail("未收到录制启动确认，禁止输入或发送")
        self.recording["start"] = ready.get("launch_monotonic", self.recording["start"])
        self.recording["ready"] = True
        self.require_recording()
        self.event("rec_start", region=step["region"])

    def stop_record(self, failed=False):
        if self.recording is None:
            return
        self.event("rec_stop")
        record = self.recording
        try:
            capture = self.backend.stop_record()
            if failed:
                self.write_events("aborted", capture=capture, failure=self.failure)
                return
            video = self.backend.probe(record["out"])
            if video["width"] <= 0 or video["height"] <= 0 or video["duration"] <= 0:
                raise ShotError("录制文件没有有效视频")
            # Read the persisted events, which also remain valid for the raw take.
            events = json.loads((record["dir"] / "events.json").read_text())["events"]
            start, end = trim_bounds(events, video["duration"])
            trimmed = record["out"]
            if start > 0 or end < video["duration"]:
                trimmed = record["dir"] / "take-trimmed.mov"
                self.backend.trim(record["out"], trimmed, start, end)
                trimmed_video = self.backend.probe(trimmed)
                if trimmed_video["duration"] <= 0:
                    raise ShotError("裁切输出无有效视频")
            trim = {"file": str(trimmed), "start": start, "end": end, "duration": end - start}
            (record["dir"] / "trimmed-events.json").write_text(json.dumps({
                "source": "events.json", "offset": start, "events": [
                    {**event, "t": round(event["t"] - start, 6)} for event in events if start <= event["t"] <= end
                ]}, ensure_ascii=False, indent=2) + "\n")
            self.write_events("complete", video=video, capture=capture, trim=trim)
            index = record["out"].parent / "index.md"
            if not index.exists():
                index.write_text("| 文件 | 像素 | 原始/裁后时长 | 关键时间点（启动时钟，未校准） | 需模糊区域 |\n|---|---|---|---|---|\n")
            moments = "; ".join(f"{event['type']} {event['t']:.2f}s" for event in events)
            filename = record["out"].name.replace("|", "\\|").replace("\n", " ")
            with index.open("a") as handle:
                handle.write(f"| {filename} → {trimmed.relative_to(index.parent)} | {video['width']}×{video['height']} | {video['duration']:.2f}/{end-start:.2f}s | {moments} |  |\n")
            self.completed.append({"raw": str(record["out"]), "take": str(trimmed),
                                   "events": str(record["dir"] / "events.json"), "trim": trim})
        except BaseException as exc:
            self.write_events("aborted", error=str(exc))
            raise
        finally:
            self.recording = None

    def run(self):
        try:
            for row in self.plan:
                step, kind = row["action"], row["action"]["type"]
                self.step = row["step"]
                if row["guards"]:
                    self.guard(step if kind == "guard" else None, allow_card=kind in {"guard", "rec_start"})
                if kind in {"prepare_input", "paste", "click", "click_text", "key"}:
                    self.require_recording()
                if row.get("send"):
                    for future in self.plan[self.step:]:
                        action = future["action"]
                        if action["type"] == "wait_text":
                            key = (tuple(action["region"]), action["text"])
                            self.baselines[key] = normalized(self.ocr_text(action["region"])).count(normalized(action["text"]))
                            break
                    self.guard()
                    self.verify_input()
                if kind == "prepare_input":
                    self.prepare_input()
                elif kind == "paste":
                    if not self.expected and not self.prepared:
                        self.prepare_input()
                    self.event("input_start")
                    for chunk in row["chunks"]:
                        self.require_recording()
                        self.backend.copy_verified(chunk)
                        self.guard()
                        self.require_recording()
                        self.backend.paste_clipboard()
                        self.expected += chunk
                    self.guard()
                    self.event("input_end", characters=len(step["text"]))
                elif kind in {"click", "click_text"}:
                    if kind == "click":
                        x, y = step["x"], step["y"]
                    else:
                        deadline = self.clock() + step.get("timeout", 0)
                        while True:
                            matches = [item for item in self.backend.ocr(step["region"])
                                       if normalized(item["text"]) == normalized(step["text"])]
                            if len(matches) == 1:
                                break
                            if len(matches) > 1 or self.clock() >= deadline:
                                self.fail("click_text 未找到唯一文字框")
                            self.sleep(min(0.5, deadline - self.clock()))
                            self.guard()
                        x, y = matches[0]["center"]
                    self.guard()
                    if row.get("send"):
                        self.verify_input()
                    self.require_recording()
                    self.backend.click(x, y)
                    self.event("click", x=x, y=y)
                elif kind == "key":
                    self.require_recording()
                    self.front_guard(self.shot["target"])
                    self.backend.key(step["key"])
                    if not row.get("send"):
                        self.event("key", key=step["key"])
                elif kind == "wait":
                    self.sleep(step["sec"])
                elif kind == "wait_text":
                    deadline = self.clock() + step["timeout"]
                    baseline = self.baselines.get((tuple(step["region"]), step["text"]), 0)
                    cleared = baseline == 0
                    while True:
                        self.guard()
                        count = normalized(self.ocr_text(step["region"])).count(normalized(step["text"]))
                        cleared = cleared or count == 0
                        if count and (not step.get("fresh", False) or cleared or count > baseline):
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
                    self.expected, self.prepared = "", False
        except BaseException as exc:
            if self.failure is None:
                try:
                    self.fail(str(exc))
                except ShotError:
                    pass
            try:
                self.stop_record(failed=True)
            except Exception as stop_error:
                self.failure["stop_error"] = str(stop_error)
            finally:
                self.backend.close()
            raise
        self.backend.close()
        return self.completed


def interrupt_recording(_signal, _frame):
    # A bridge timeout first signals this runner; Runner.run closes active capture.
    raise KeyboardInterrupt


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
        previous_handler = signal.signal(signal.SIGTERM, interrupt_recording)
        try:
            Runner(shot, MacBackend(args.private_dir)).run()
        finally:
            signal.signal(signal.SIGTERM, previous_handler)
        return 0
    except (ShotError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"rec-shot: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("rec-shot: 用户中止，录制已停止", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
