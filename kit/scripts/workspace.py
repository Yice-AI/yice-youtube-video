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
    return workspace, toolkit


def main():
    runners = {"voice.py": ("YICE_ASR_PYTHON", "asr-venv"),
               "props.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "review.py": ("YICE_REVIEW_PYTHON", "tts-venv")}
    if len(sys.argv) < 2 or sys.argv[1] not in runners:
        raise SystemExit("内部入口：workspace.py voice.py|props.py|review.py [参数]")
    workspace, toolkit = load_environment()
    variable, venv = runners[sys.argv[1]]
    python = os.environ.get(variable) or str(toolkit / "local" / venv / "bin/python")
    env = {**os.environ, "YICE_WORKSPACE": str(workspace), "YICE_TOOLKIT": str(toolkit)}
    os.execve(python, [python, str(Path(__file__).parent / sys.argv[1]), *sys.argv[2:]], env)


if __name__ == "__main__":
    main()
