#!/bin/bash
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
  echo '缺少 python3；请先安装，再运行 install.sh。' >&2
  exit 2
fi
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 - "$REPO_DIR" "$@" <<'PY'
import argparse, json, os, shlex, shutil, sys
from datetime import datetime
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / 'kit/scripts'))
from workspace import load_environment

parser = argparse.ArgumentParser(description='安装 skill 软链接与机器路径配置；依赖只检查，不自动安装。')
parser.add_argument('--workspace', type=Path)
parser.add_argument('--toolkit', type=Path)
args = parser.parse_args(sys.argv[2:])
workspace, toolkit = load_environment()
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

for target in [home / '.claude/skills/yice-youtube-video', home / '.codex/skills/yice-youtube-video']:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == repo:
        links.append({'path': str(target), 'state': 'already_linked'})
        continue
    backup(target, outside=True)
    target.symlink_to(repo, target_is_directory=True)
    links.append({'path': str(target), 'state': 'linked'})
config = home / '.config/yice-video/env'
config.parent.mkdir(parents=True, exist_ok=True)
content = 'YICE_WORKSPACE=' + shlex.quote(str(workspace)) + '\nYICE_TOOLKIT=' + shlex.quote(str(toolkit)) + '\n'
if not config.is_file() or config.read_text() != content:
    backup(config)
    temporary = config.with_name('env.tmp-' + stamp)
    temporary.write_text(content)
    temporary.chmod(0o600)
    temporary.replace(config)

checks = {name: bool(shutil.which(name)) for name in ['node', 'npm', 'ffmpeg', 'ffprobe', 'python3']}
checks.update({
    'toolkit': toolkit.is_dir(),
    'tts-venv': (toolkit / 'local/tts-venv/bin/python').is_file(),
    'asr-venv': (toolkit / 'local/asr-venv/bin/python').is_file(),
    'Qwen3-TTS 8bit 离线模型': (toolkit / 'local/models/Qwen3-TTS-12Hz-1.7B-Base-8bit').is_dir(),
    'Whisper 离线模型': (home / '.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo').is_dir(),
    'rec 录屏工具': all((toolkit / 'local/tools/rec' / name).is_file() for name in ['rec.sh', 'mouse', 'cursorlog', 'ingest.sh', 'ingest.py']),
    'image2.py': (toolkit / 'local/tools/image2.py').is_file(),
    'local_voiceover.py': (toolkit / 'local/tools/local_voiceover.py').is_file(),
    'captions.py': (toolkit / 'tools/captions.py').is_file(),
})
print(json.dumps({'repository': str(repo), 'links': links, 'backups': backups, 'config': str(config),
                  'workspace': str(workspace), 'toolkit': str(toolkit), 'dependencies': checks,
                  'missing': [name for name, exists in checks.items() if not exists],
                  'note': '缺失依赖请自行准备；安装器没有下载模型、安装软件或修改应用设置。'}, ensure_ascii=False, indent=2))
PY
