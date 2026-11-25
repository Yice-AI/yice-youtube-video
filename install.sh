#!/bin/bash
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
  echo '缺少 python3；请先安装，再运行 install.sh。' >&2
  exit 2
fi
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 - "$REPO_DIR" "$@" <<'PY'
import argparse, json, os, shlex, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / 'kit/scripts'))
from workspace import (load_environment, ensure_voice_dependencies, load_voice_reference, resolve_onetake,
                       resolve_gsap_runtime, resolve_hyperframes_command, valid_whisper_directory)

parser = argparse.ArgumentParser(description='安装/检查 skill；自动补齐现有 ASR 环境的配音依赖，其余依赖仅检查。')
parser.add_argument('--workspace', type=Path)
parser.add_argument('--toolkit', type=Path)
parser.add_argument('--check', action='store_true', help='检查并补齐 ASR 配音依赖，不修改 skill 软链接或路径配置')
args = parser.parse_args(sys.argv[2:])
workspace, toolkit = load_environment(dict(os.environ))
if args.workspace:
    workspace = args.workspace.expanduser().resolve()
    if not args.toolkit and not os.environ.get('YICE_TOOLKIT'):
        toolkit = workspace / 'claude-code-video-toolkit'
if args.toolkit:
    toolkit = args.toolkit.expanduser().resolve()
for value in [workspace, toolkit, repo]:
    if any(c in str(value) for c in '\n\r\0'):
        parser.error('目录不能含换行')
home = Path.home()
env = {**os.environ, 'YICE_WORKSPACE':str(workspace), 'YICE_TOOLKIT':str(toolkit)}
load_environment(env)
stamp = datetime.now().strftime('%Y%m%dT%H%M%S-%f')
backups, links = [], []

def backup(path, outside=False):
    if path.exists() or path.is_symlink():
        # skill 目录的备份放到 skills 目录之外，否则会被当成第二个同名 skill 加载
        bdir = (home / '.config/yice-video/backups' / path.parent.parent.name) if outside else path.parent
        bdir.mkdir(parents=True, exist_ok=True)
        dest = bdir / (path.name + '.bak-' + stamp)
        if dest.exists() or dest.is_symlink():
            raise RuntimeError('备份目标已存在，未覆盖')
        path.rename(dest)
        backups.append(str(dest))

config = home / '.config/yice-video/env'
if not args.check:
    clients = [home / '.claude',home / '.codex']
    if (home / '.gemini/config').is_dir():
        clients.append(home / '.gemini/config')
    for target in [client / 'skills/yice-youtube-video' for client in clients]:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() and target.resolve() == repo:
            links.append({'path': str(target), 'state': 'already_linked'})
            continue
        backup(target, outside=True)
        target.symlink_to(repo, target_is_directory=True)
        links.append({'path': str(target), 'state': 'linked'})
    config.parent.mkdir(parents=True, exist_ok=True)
    content = 'YICE_WORKSPACE=' + shlex.quote(str(workspace)) + '\nYICE_TOOLKIT=' + shlex.quote(str(toolkit)) + '\n'
    if config.is_file():
        for line in config.read_text().splitlines():
            parts = shlex.split(line,comments=True)
            if parts and parts[0].startswith('YICE_ASR_MODEL='):
                content += 'YICE_ASR_MODEL=' + shlex.quote(parts[0].split('=',1)[1]) + '\n'
    if not config.is_file() or config.read_text() != content:
        backup(config)
        temporary = config.with_name('env.tmp-' + stamp)
        temporary.write_text(content)
        temporary.chmod(0o600)
        temporary.replace(config)

voice_dependencies = ensure_voice_dependencies(toolkit)

def local_command(command, cwd=repo):
    try:
        return subprocess.run(command,cwd=cwd,env={**env,'npm_config_offline':'true',
                              'HYPERFRAMES_TELEMETRY_DISABLED':'1','DO_NOT_TRACK':'1'},
                              capture_output=True,text=True,timeout=12)
    except (OSError,subprocess.TimeoutExpired):
        return None


def whisper_ready():
    configured = env.get('YICE_ASR_MODEL')
    if configured:
        model = Path(configured).expanduser()
        if model.is_absolute() or model.exists() or configured.startswith('.') or configured.count('/')!=1:
            return valid_whisper_directory(model)
    elif valid_whisper_directory(home / 'yice-demo/我的视频/models/Whisper-Large-v3-Turbo'):
        return True
    model_id = configured or 'mlx-community/whisper-large-v3-turbo'
    hf_home = Path(env.get('HF_HOME',home / '.cache/huggingface')).expanduser()
    hub = Path(env.get('HF_HUB_CACHE',hf_home / 'hub')).expanduser()
    snapshots = hub / ('models--'+model_id.replace('/','--')) / 'snapshots'
    return any(valid_whisper_directory(snapshot) for snapshot in snapshots.glob('*'))


def gsap_ready():
    return resolve_gsap_runtime(root=repo,environ=env) is not None


def brand_ready():
    try:
        ref, text, _ = load_voice_reference(toolkit,env.get('YICE_VOICE_BRAND') or 'yice')
        return ref.stat().st_size>0 and isinstance(text,str) and bool(text.strip())
    except (OSError,ValueError,TypeError,AttributeError):
        return False


hyperframes = local_command([*resolve_hyperframes_command(env),'--version'])
token_file = home / '.kaggle/access_token'
stock_config = home / '.config/yice-video/stock.env'
checks = {name: bool(shutil.which(name)) for name in ['node', 'npm', 'ffmpeg', 'ffprobe', 'python3']}
checks.update({
    'toolkit': toolkit.is_dir(),
    'tts-venv': (toolkit / 'local/tts-venv/bin/python').is_file(),
    'asr-venv': (toolkit / 'local/asr-venv/bin/python').is_file(),
    'ASR 配音声学依赖': voice_dependencies['ready'],
    'Qwen3-TTS 8bit 离线模型': (toolkit / 'local/models/Qwen3-TTS-12Hz-1.7B-Base-8bit').is_dir(),
    'Whisper 离线模型': whisper_ready(),
    'HyperFrames 离线 CLI': hyperframes is not None and hyperframes.returncode==0,
    'GSAP 本地运行时': gsap_ready(),
    'Kaggle 凭证或端点': bool(env.get('KAGGLE_TTS_ENDPOINT_URL')) or (token_file.is_file() and token_file.stat().st_size>0),
    '图库配置': stock_config.is_file() and any(env.get(key) for key in ('PEXELS_API_KEY','PIXABAY_API_KEY')),
    '品牌参考音': brand_ready(),
    'rec 录屏工具': all((toolkit / 'local/tools/rec' / name).is_file() for name in ['rec.sh', 'mouse', 'cursorlog', 'ingest.sh', 'ingest.py']),
    'image2.py': (toolkit / 'local/tools/image2.py').is_file(),
    'local_voiceover.py': (toolkit / 'local/tools/local_voiceover.py').is_file(),
    'captions.py': (toolkit / 'tools/captions.py').is_file(),
})
hints = {
    'Whisper 离线模型':'检查 YICE_ASR_MODEL、本机目录或 Hugging Face 缓存中的 config.json 与权重实文件。',
    'HyperFrames 离线 CLI':'先准备本机 HyperFrames CLI 缓存，再运行 npx --offline hyperframes --version。',
    'GSAP 本地运行时':'在本机项目安装 GSAP 或将 YICE_GSAP_PATH 指向 gsap.min.js。',
    'Kaggle 凭证或端点':'准备 ~/.kaggle/access_token 或设置已授权的 KAGGLE_TTS_ENDPOINT_URL。',
    '图库配置':'在 ~/.config/yice-video/stock.env 配好 Pexels 或 Pixabay 凭证。',
    '品牌参考音':'检查所用品牌的 voice.json、参考音频实文件及参考文本。',
}
print(json.dumps({'repository': str(repo), 'links': links, 'backups': backups, 'config': str(config),
                  'workspace': str(workspace), 'toolkit': str(toolkit), 'dependencies': checks,
                  'voice_dependencies': voice_dependencies, 'check_only': args.check,
                  'onetake_ready': resolve_onetake(env) is not None,
                  'missing': [name for name, exists in checks.items() if not exists],
                  'missing_hints': {name:hint for name,hint in hints.items() if not checks[name]},
                  'note': '仅自动补齐现有 asr-venv 的配音 Python 依赖；其余缺失依赖请自行准备，不下载模型。'}, ensure_ascii=False, indent=2))
PY
