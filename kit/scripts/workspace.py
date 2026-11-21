"""读取跨机器路径配置；配置作为数据解析，不执行其中的 shell 内容。"""
import os
import shlex
import sys
from pathlib import Path


def load_environment(environ=None):
    environ = os.environ if environ is None else environ
    home = Path(environ.get("HOME", str(Path.home()))).expanduser()
    config = home / ".config/yice-video/env"
    values = {}
    if config.is_file():
        for line in config.read_text().splitlines():
            parts = shlex.split(line, comments=True)
            if not parts:
                continue
            if len(parts) != 1 or "=" not in parts[0]:
                raise ValueError("路径配置须每行一个带引号的赋值，不支持执行 shell 命令")
            name, value = parts[0].split("=", 1)
            if name not in {"YICE_WORKSPACE", "YICE_TOOLKIT"}:
                raise ValueError("路径配置只支持 YICE_WORKSPACE 和 YICE_TOOLKIT")
            values[name] = value

    def path(value):
        value = str(value).replace("${HOME}", str(home)).replace("$HOME", str(home))
        if value == "~" or value.startswith("~/"):
            value = str(home) + value[1:]
        if not value or any(c in value for c in "\n\r\0"):
            raise ValueError("目录配置不能为空或含换行")
        return Path(value).resolve()

    workspace = path(environ.get("YICE_WORKSPACE") or values.get("YICE_WORKSPACE") or home / "Documents/Codex/个人IP")
    toolkit = path(environ.get("YICE_TOOLKIT") or values.get("YICE_TOOLKIT") or workspace / "claude-code-video-toolkit")
    dotenv = toolkit / ".env"
    endpoints = {f"MODAL_{service}_ENDPOINT_URL" for service in ("QWEN3_TTS", "FLUX2", "MUSIC_GEN", "LTX2")}
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            key, sep, raw = line.strip().removeprefix("export ").partition("=")
            if sep and key.strip() in endpoints:
                parts = shlex.split(raw, comments=True)
                if len(parts) == 1:
                    environ.setdefault(key.strip(), parts[0])
    return workspace, toolkit


def ensure_voice_dependencies(toolkit):
    """Install only missing/wrong-version voice dependencies in the existing ASR venv."""
    import json
    import shutil
    import subprocess

    python = Path(toolkit) / "local/asr-venv/bin/python"
    required = {"librosa": "1.0.1", "soundfile": "0.14.0", "scipy": None, "numpy": None}
    if not python.is_file():
        return {"ready": False, "python": str(python), "installed": [], "missing_environment": True}
    probe = """
import importlib, importlib.metadata, json
result = {}
for package in ["librosa", "soundfile", "scipy", "numpy"]:
    try:
        importlib.import_module(package)
        result[package] = importlib.metadata.version(package)
    except Exception:
        result[package] = None
print(json.dumps(result))
"""

    def inspect():
        completed = subprocess.run([str(python), "-I", "-c", probe], capture_output=True, text=True, check=True)
        return json.loads(completed.stdout)

    before = inspect()
    missing = [name + ("==" + version if version else "")
               for name, version in required.items()
               if not before.get(name) or (version and before[name] != version)]
    if missing:
        uv = shutil.which("uv")
        command = ([uv, "pip", "install", "--python", str(python)] if uv else
                   [str(python), "-I", "-m", "pip", "install"])
        completed = subprocess.run([*command, *missing], capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError("ASR 配音依赖安装失败：" + completed.stderr[-2000:])
    after = inspect() if missing else before
    ready = all(after.get(name) and (version is None or after[name] == version)
                for name, version in required.items())
    if not ready:
        raise RuntimeError("ASR 配音依赖安装后仍无法导入或版本不匹配")
    return {"ready": True, "python": str(python), "installed": missing,
            "versions_before": before, "versions": after}


def main():
    runners = {"voice.py": ("YICE_ASR_PYTHON", "asr-venv"),
               "voice-check.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "voice-post.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "voice-repair.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "props.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "cutout.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "people_add.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "audit-v3.py": ("YICE_REVIEW_PYTHON", "tts-venv"),
               "review.py": ("YICE_REVIEW_PYTHON", "tts-venv")}
    if len(sys.argv) < 2 or sys.argv[1] not in runners:
        raise SystemExit("内部入口：workspace.py voice.py|voice-check.py|voice-post.py|voice-repair.py|props.py|cutout.py|review.py [参数]")
    workspace, toolkit = load_environment()
    variable, venv = runners[sys.argv[1]]
    python = os.environ.get(variable) or str(toolkit / "local" / venv / "bin/python")
    env = {**os.environ, "YICE_WORKSPACE": str(workspace), "YICE_TOOLKIT": str(toolkit)}
    os.execve(python, [python, str(Path(__file__).parent / sys.argv[1]), *sys.argv[2:]], env)


if __name__ == "__main__":
    main()
