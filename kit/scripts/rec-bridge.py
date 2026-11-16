#!/usr/bin/env python3
"""Private, single-instance queue for ping, local OCR and guarded rec-shot only."""
import argparse
from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

SCRIPTS = Path(__file__).resolve().parent
DEFAULT_ROOT = Path.home() / "Library/Application Support/yice-video/rec-bridge"
MAX_REQUEST_BYTES = 1_048_576


def stamp():
    return datetime.now(timezone.utc).isoformat()


def private_directory(path):
    if path.is_symlink():
        raise ValueError("私有子目录不能是符号链接")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REQUEST_BYTES:
        raise ValueError("拒绝符号链接或超过 1 MiB 的请求/镜头单")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("请求/镜头单必须是 JSON 对象")
    return value


def shot_module():
    spec = importlib.util.spec_from_file_location("rec_shot_bridge", SCRIPTS / "rec-shot.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def demo_module():
    spec = importlib.util.spec_from_file_location("rec_demo_bridge", SCRIPTS / "rec-demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def allowed_path(value, roots):
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError("路径必须是字符串")
    expanded = os.path.expandvars(value)
    if "$" in expanded:
        raise ValueError("路径含未定义环境变量")
    candidate = Path(expanded).expanduser()
    if not candidate.is_absolute():
        raise ValueError("路径必须是绝对路径")
    resolved = candidate.resolve()
    if not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError("路径越界：只接受证据目录或中转器 private 目录")
    return resolved


def terminate_group(process, grace):
    """Ask the runner to close capture, then reap any children in its isolated group."""
    if process.poll() is None:
        process.terminate()  # rec-shot handles TERM and stops its recorder/logger.
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    # A parent can exit before its child. Kill only this dedicated process group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_command(command, folder, timeout, grace):
    stdout_path, stderr_path = folder / "stdout.log", folder / "stderr.log"
    started = time.monotonic()
    timed_out = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        stdout_path.chmod(0o600)
        stderr_path.chmod(0o600)
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_group(process, grace)
            code = 124
        except BaseException:
            terminate_group(process, grace)
            raise
    def tail(path):
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 8192))
            return stream.read().decode("utf-8", errors="replace")
    return {"exit_code": code, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stdout": tail(stdout_path), "stderr": tail(stderr_path),
            "artifacts": [str(stdout_path), str(stderr_path)]}


class Bridge:
    def __init__(self, root, evidence_roots, timeout=1800, grace=35):
        self.root = private_directory(Path(root).expanduser().resolve())
        self.queue = private_directory(self.root / "queue")
        self.done = private_directory(self.root / "done")
        self.claimed = private_directory(self.root / "claimed")
        self.private = private_directory(self.root / "private")
        self.roots = [Path(p).expanduser().resolve() for p in evidence_roots] + [self.private]
        self.timeout, self.grace = timeout, grace
        self.lock = None

    def acquire(self):
        self.lock = (self.root / "bridge.lock").open("a+")
        (self.root / "bridge.lock").chmod(0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            self.lock = None
            raise ValueError("此队列已有中转器实例") from None
        self.lock.seek(0)
        self.lock.truncate()
        self.lock.write(str(os.getpid()) + "\n")
        self.lock.flush()
        # Never replay a request whose previous executor died mid-action.
        for path in self.claimed.glob("*.json"):
            result = self.done / path.name
            if not result.exists():
                write_json(result, {"exit_code": 125, "state": "interrupted", "finished_at": stamp(),
                                    "stdout": "", "stderr": "上次执行中断，未自动重放；检查素材后用新请求名重试", "artifacts": []})

    def close(self):
        if self.lock is not None:
            self.lock.close()
            self.lock = None

    def prepare(self, request, folder):
        action = request.get("action")
        fields = {"ping": {"action"}, "probe": {"action", "region"},
                  "rec-shot": {"action", "shot", "dry_run"}, "rec-demo": {"action", "params"}}
        if not isinstance(action, str) or action not in fields or set(request) - fields[action]:
            raise ValueError("只允许 ping、probe、rec-shot、rec-demo 及其白名单参数")
        if action == "ping":
            return None, []
        if action == "rec-demo":
            source = allowed_path(request.get("params"), self.roots)
            params = read_json(source)
            params["output_dir"] = str(allowed_path(params.get("output_dir"), self.roots))
            demo_module().build_shots(params)
            snapshot = folder / "params.json"
            write_json(snapshot, params)
            return ["bash", str(SCRIPTS / "rec-demo.sh"), str(snapshot)], [Path(params["output_dir"]), snapshot]
        module = shot_module()
        if action == "probe":
            rect = module.region(request.get("region"))
            return [sys.executable, str(Path(__file__).resolve()), "--probe-worker", str(folder),
                    "--region", ",".join(map(str, rect))], [folder / "probe.png", folder / "probe.json"]
        if not isinstance(request.get("dry_run", False), bool):
            raise ValueError("dry_run 必须是布尔值")
        source = allowed_path(request.get("shot"), self.roots)
        shot = read_json(source)
        module.build_plan(shot)  # Preserve all guards; reject unknown steps/fields.
        artifacts = []
        for step in shot["steps"]:
            if step["type"] == "rec_start":
                output = allowed_path(step["out"], self.roots)
                step["out"] = str(output)
                artifacts.extend([output, output.with_suffix(output.suffix + ".rec") / "events.json",
                                  output.parent / "index.md"])
        # Freeze the validated plan to avoid a file changing after validation.
        snapshot = folder / "shot.json"
        write_json(snapshot, shot)
        command = ["bash", str(SCRIPTS / "rec-shot.sh"), str(snapshot)]
        if request.get("dry_run", False):
            command.append("--dry-run")
        return command, artifacts + [snapshot]

    def process(self, path):
        if self.lock is None:
            raise RuntimeError("处理请求前必须持有单实例锁")
        name = path.name
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json", name):
            raise ValueError("请求文件名须为 ASCII 字母/数字/点/下划线/连字符")
        if (self.done / name).exists() or (self.claimed / name).exists():
            # A duplicate name is never executed, even after a successful request.
            path.rename(self.claimed / (name + ".duplicate-" + str(time.time_ns())))
            return False
        source = self.claimed / name
        path.rename(source)
        result = {"request": name, "started_at": stamp(), "exit_code": 2,
                  "stdout": "", "stderr": "", "artifacts": []}
        folder = private_directory(self.private / name[:-5])
        try:
            request = read_json(source)
            result["action"] = request.get("action")
            command, artifacts = self.prepare(request, folder)
            if command is None:
                result.update(exit_code=0, stdout=json.dumps({"status": "ok", "pid": os.getpid(), "at": stamp()}))
            else:
                result.update(run_command(command, folder, self.timeout, self.grace))
                result["artifacts"].extend(str(p) for p in artifacts if p.exists())
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            result["stderr"] = f"{type(exc).__name__}: {exc}"
        except KeyboardInterrupt:
            result.update(exit_code=130, stderr="中转器收到停止信号，当前子进程组已终止")
            raise
        finally:
            result["state"] = "done" if result["exit_code"] == 0 else "rejected_or_failed"
            result["finished_at"] = stamp()
            write_json(self.done / name, result)
        return True

    def drain(self):
        count = 0
        for path in sorted(self.queue.glob("*.json")):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json", path.name):
                # Record invalid names without allowing them to stall later requests.
                rejected = self.claimed / ("invalid-" + str(time.time_ns()) + ".json")
                path.rename(rejected)
                write_json(self.done / rejected.name, {"request": path.name, "exit_code": 2,
                           "stdout": "", "stderr": "无效请求文件名，已拒绝", "artifacts": [], "finished_at": stamp()})
                continue
            count += self.process(path)
        return count


def probe_worker(folder, rect):
    module = shot_module()
    backend = module.MacBackend(folder)
    try:
        process, title = backend.front()
        geometry = subprocess.check_output(["osascript", "-e",
            'tell application "System Events"\n'
            'set p to first application process whose frontmost is true\n'
            'set w to value of attribute "AXFocusedWindow" of p\n'
            'return {position of w, size of w}\nend tell'], text=True)
        values = [float(v.strip()) for v in geometry.strip().split(",")]
        if len(values) != 4:
            raise ValueError("未能读取窗口坐标")
        screenshot = folder / "probe.png"
        shutil.copy2(backend.capture(rect), screenshot)
        screenshot.chmod(0o600)
        ocr = json.loads(subprocess.check_output([backend.binary("ocr", "ocr"), str(screenshot)], text=True))
        result = {"process": process, "title": title, "position": values[:2], "size": values[2:],
                  "region_points": rect, "ocr": ocr, "screenshot": str(screenshot), "at": stamp()}
        write_json(folder / "probe.json", result)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        backend.close()


def interrupted(_signal, _frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--evidence-root", type=Path, action="append")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--stop-grace", type=float, default=35)
    parser.add_argument("--once", action="store_true", help="处理当前队列后退出（测试用）")
    parser.add_argument("--probe-worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--region", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    for value in [args.timeout, args.stop_grace]:
        if not math.isfinite(value) or value <= 0:
            parser.error("timeout/stop-grace 必须是有限正数")
    signal.signal(signal.SIGTERM, interrupted)
    if args.probe_worker:
        rect = shot_module().region([float(v) for v in (args.region or "").split(",")])
        probe_worker(args.probe_worker, rect)
        return 0
    if args.evidence_root is None:
        from workspace import load_environment
        workspace, _ = load_environment()
        args.evidence_root = [workspace / ".scratch/youtube/evidence"]
    bridge = Bridge(args.queue_dir, args.evidence_root, args.timeout, args.stop_grace)
    try:
        bridge.acquire()
        print(json.dumps({"state": "ready", "queue": str(bridge.queue), "pid": os.getpid()}), flush=True)
        while True:
            bridge.drain()
            if args.once:
                break
            time.sleep(0.5)
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as exc:
        print(f"rec-bridge: {exc}", file=sys.stderr)
        return 2
    finally:
        bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
