"""读取跨机器路径配置；配置作为数据解析，不执行其中的 shell 内容。"""
import os
import json
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ONETAKE_FILES = ('lib/motion.js', 'scripts/probe.py', 'scripts/render.py')
ONETAKE_FONTS = ('SourceHanSansCN-Bold.otf', 'SourceHanSerifCN-Heavy.otf', 'SourceCodePro-Regular.otf')
ONETAKE_COLORS = ('ground','deep','card','line','mute','ink','accent','accent2')


def render_workers(value=None):
    workers = int(os.environ.get('YICE_RENDER_WORKERS', 2) if value is None else value)
    if workers < 1:
        raise ValueError('渲染进程数至少为 1')
    return workers


def render_priority():
    if os.name != 'posix':
        return {}
    target = max(10, int(os.environ.get('YICE_RENDER_NICE', 10)))

    def lower_priority():
        try:
            os.nice(max(0, target - os.nice(0)))
        except OSError:
            pass

    return {'preexec_fn': lower_priority}


def composition_files(entry):
    if entry.is_symlink() or not entry.is_file() or entry.suffix.lower() != '.html':
        raise ValueError(f'合成入口须为本地 HTML：{entry.name}')
    files = []
    for path in sorted(entry.parent.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f'合成目录只允许普通文件和目录：{path.name}')
        if path.is_file():
            files.append(path)
    return files


def resolve_onetake(environ=None):
    environ = os.environ if environ is None else environ
    home = Path(environ.get('HOME', str(Path.home())))
    override = environ.get('YICE_ONETAKE_DIR')
    candidates = [Path(override).expanduser()] if override else []
    candidates.extend(home / path for path in (
        '.codex/skills/onetake', '.gemini/config/skills/onetake', '.claude/skills/onetake',
    ))
    return next((path.resolve() for path in candidates
                 if all((path / name).is_file() for name in ONETAKE_FILES)), None)


def onetake_python():
    return shlex.split(os.environ.get('YICE_ONETAKE_PYTHON','')) or [sys.executable]


def onetake_looks(runtime):
    return json.loads((runtime/'looks/looks.json').read_text())['looks']


def onetake_look(runtime, look=None, *, shots=(), output=None):
    presets = onetake_looks(runtime)
    name = 'paper' if look is None else look
    if not isinstance(name,str) or name not in presets:
        raise ValueError('Onetake 色板须为 '+', '.join(presets))
    if not shots:
        return dict(presets[name],name=name)
    if not 1 <= len(shots) <= 3 or not all(Path(shot).is_file() for shot in shots):
        raise ValueError('产品吸色需要 1–3 张本地截图')
    subprocess.run([*onetake_python(),str(runtime/'scripts/look.py'),'from-shot',*map(str,shots),
                    '--faces',name,'--out',str(output)],check=True,capture_output=True,text=True)
    return json.loads(Path(output).read_text())


def valid_whisper_directory(path):
    config = path / "config.json"
    return config.is_file() and os.access(config, os.R_OK) and any(
        (path / name).is_file() for name in ("weights.safetensors", "model.safetensors", "weights.npz")
    )


def load_voice_reference(toolkit, brand):
    private = Path.home() / '.config/yice-youtube-video'
    ref, transcript = private / 'voice-reference.wav', private / 'voice-reference.txt'
    if brand == 'yice' and (ref.exists() or transcript.exists()):
        if not (ref.is_file() and transcript.is_file()):
            raise ValueError('迁移声纹需要 voice-reference.wav 和 voice-reference.txt 两个文件')
        if any(p.stat().st_mode & 0o077 for p in (ref,transcript)):
            raise ValueError('请将两份私人参考音文件权限设为 0600')
        words = transcript.read_text(encoding='utf-8').strip()
        if not words or not ref.stat().st_size:
            raise ValueError('私人参考音或对应文本为空')
        return ref, words, 'Chinese'
    config = toolkit / "brands" / brand / "voice.json"
    if not config.is_file():
        raise ValueError(f"缺少声音配置：{config}")
    qwen = json.loads(config.read_text()).get("qwen3", {})
    clone = qwen.get("clone", {})
    ref = config.parent / clone.get("refAudio", "")
    if not ref.is_file():
        raise ValueError(f"缺少声音参考音频：{ref}")
    return ref, clone.get("refText", ""), qwen.get("language", "Chinese")


def resolve_hyperframes_command(environ=None):
    environ = os.environ if environ is None else environ
    override = shlex.split(environ.get("YICE_HYPERFRAMES_BIN", ""))
    if override:
        return override
    installed = shutil.which("hyperframes", path=environ.get("PATH",os.defpath))
    if installed:
        return [installed]
    home = Path(environ.get("HOME",str(Path.home()))).expanduser()
    candidates = []
    for binary in (home / ".npm/_npx").glob("*/node_modules/.bin/hyperframes"):
        if not binary.is_file() or not os.access(binary,os.X_OK):
            continue
        manifest = binary.parent.parent / "hyperframes/package.json"
        try:
            version = json.loads(manifest.read_text())["version"]
            parts = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?",version)
        except (OSError,ValueError,TypeError,KeyError):
            continue
        if parts:
            release = tuple(map(int,parts.groups()[:3]))
            prerelease = parts[4]
            sequence = tuple((0,int(part)) if part.isdecimal() else (1,part)
                             for part in (prerelease or "").split("."))
            candidates.append((release,prerelease is None,sequence,str(binary)))
    return [max(candidates)[-1]] if candidates else ["npx","--offline","hyperframes"]


def resolve_gsap_runtime(explicit=None, *, root=None, environ=None):
    env = dict(os.environ if environ is None else environ)
    home = Path(env.get("HOME",str(Path.home()))).expanduser()
    root = Path.cwd() if root is None else Path(root)

    def locate(value):
        if not value:
            return None
        value = str(value)
        if value.startswith("~/"):
            value = str(home / value[2:])
        path = (root / Path(value).expanduser()).resolve()
        return path if path.is_file() else None

    for value in (explicit,env.get("YICE_GSAP_PATH")):
        path = locate(value)
        if path:
            return path
    workspace, toolkit = load_environment(env)
    for value in (toolkit/"local/vendor/gsap.min.js",home/".config/yice-video/vendor/gsap.min.js"):
        path = locate(value)
        if path:
            return path

    repo = Path(__file__).resolve().parents[2]
    directories = dict.fromkeys(item.resolve() for item in (root,repo,workspace,toolkit))
    node = shutil.which("node",path=env.get("PATH",os.defpath))
    if node is None:
        return None
    for directory in directories:
        if not directory.is_dir():
            continue
        try:
            result = subprocess.run([node,"-p","require.resolve('gsap/dist/gsap.min.js')"],
                                    cwd=directory,env=env,capture_output=True,text=True,timeout=8)
        except (OSError,subprocess.TimeoutExpired):
            continue
        if result.returncode==0:
            path = locate(result.stdout.strip())
            if path:
                return path
    return None


def load_environment(environ=None, *, kaggle_voice=False):
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
            if name not in {"YICE_WORKSPACE", "YICE_TOOLKIT", "YICE_ASR_MODEL"}:
                raise ValueError("路径配置只支持 YICE_WORKSPACE、YICE_TOOLKIT 和 YICE_ASR_MODEL")
            values[name] = value

    def expand_home(value):
        value = str(value).replace("${HOME}", str(home)).replace("$HOME", str(home))
        if value == "~" or value.startswith("~/"):
            value = str(home) + value[1:]
        return value

    def path(value):
        value = expand_home(value)
        if not value or any(c in value for c in "\n\r\0"):
            raise ValueError("目录配置不能为空或含换行")
        return Path(value).resolve()

    if values.get("YICE_ASR_MODEL"):
        environ.setdefault("YICE_ASR_MODEL", expand_home(values["YICE_ASR_MODEL"]))
    workspace = path(environ.get("YICE_WORKSPACE") or values.get("YICE_WORKSPACE") or home / "Documents/Codex/个人IP")
    toolkit = path(environ.get("YICE_TOOLKIT") or values.get("YICE_TOOLKIT") or workspace / "claude-code-video-toolkit")
    dotenv = toolkit / ".env"
    kaggle_keys = {"KAGGLE_TTS_ENDPOINT_URL", "KAGGLE_TTS_TOKEN"}
    endpoints = {f"MODAL_{service}_ENDPOINT_URL" for service in ("QWEN3_TTS", "FLUX2", "MUSIC_GEN", "LTX2")} | kaggle_keys
    stock_keys = {"PEXELS_API_KEY", "PIXABAY_API_KEY"}
    private = home / ".config/yice-youtube-video/kaggle-tts.env"
    files = [(dotenv, endpoints | stock_keys), (home / ".config/yice-video/stock.env", stock_keys)]
    if kaggle_voice:
        files.insert(0, (private, kaggle_keys))
    for env_file, allowed in files:
        if not env_file.is_file():
            continue
        with env_file.open(encoding="utf-8") as assignments:
            if env_file == private and stat.S_IMODE(os.fstat(assignments.fileno()).st_mode) != 0o600:
                continue
            for line in assignments:
                key, sep, raw = line.strip().removeprefix("export ").partition("=")
                if sep and key.strip() in allowed:
                    parts = shlex.split(raw, comments=True)
                    if len(parts) == 1:
                        environ.setdefault(key.strip(), parts[0])
    return workspace, toolkit


def ensure_voice_dependencies(toolkit):
    """Install only missing/wrong-version voice dependencies in the existing ASR venv."""
    python = Path(toolkit) / "local/asr-venv/bin/python"
    required = {"librosa": "1.0.1", "soundfile": "0.14.0", "scipy": None, "numpy": None, "Pillow": None, "pypinyin": "0.55.0"}
    if not python.is_file():
        return {"ready": False, "python": str(python), "installed": [], "missing_environment": True}
    probe = """
import importlib, importlib.metadata, json, sys
result = {}
for package in sys.argv[1:]:
    try:
        importlib.import_module("PIL" if package == "Pillow" else package)
        result[package] = importlib.metadata.version(package)
    except Exception:
        result[package] = None
print(json.dumps(result))
"""

    def inspect():
        completed = subprocess.run([str(python), "-I", "-c", probe, *required],
                                   capture_output=True, text=True, check=True)
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
               "visual-palette.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "render-onetake-clip.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "voice-check.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "voice-post.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "voice-repair.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "assemble-episode.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "scout-video-scenes.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "mix-episode-audio.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "props.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "cutout.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "people_add.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "thumbnail.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "produce_asset.py": ("YICE_IMAGE_PYTHON", "tts-venv"),
               "scaffold-manifest.py": ("YICE_VOICE_PYTHON", "asr-venv"),
               "audit-v3.py": ("YICE_REVIEW_PYTHON", "asr-venv"),
               "review.py": ("YICE_REVIEW_PYTHON", "tts-venv")}
    if len(sys.argv) < 2 or sys.argv[1] not in runners:
        raise SystemExit('内部入口：workspace.py ' + '|'.join(runners) + ' [参数]')
    workspace, toolkit = load_environment(kaggle_voice=sys.argv[1] in {"voice.py", "voice-repair.py"})
    variable, venv = runners[sys.argv[1]]
    python = os.environ.get(variable) or str(toolkit / "local" / venv / "bin/python")
    env = {**os.environ, "YICE_WORKSPACE": str(workspace), "YICE_TOOLKIT": str(toolkit)}
    os.execve(python, [python, str(Path(__file__).parent / sys.argv[1]), *sys.argv[2:]], env)


if __name__ == "__main__":
    main()
