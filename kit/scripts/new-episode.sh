#!/bin/bash
set -euo pipefail
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 - "$KIT_DIR" "$@" <<'PY'
import argparse, json, os, re, shutil, sys
from pathlib import Path
kit = Path(sys.argv[1])
sys.path.insert(0, str(kit / 'scripts'))
from workspace import load_environment
parser = argparse.ArgumentParser(description='新建或补齐一期项目，保留已有剧本和配置。')
parser.add_argument('episode')
parser.add_argument('--dir', type=Path, help='项目目录；默认 toolkit/local/episodes/<ep-id>')
args = parser.parse_args(sys.argv[2:])
ep = args.episode
if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', ep):
    parser.error('编号只用小写字母、数字、短横线和下划线')
workspace, toolkit = load_environment()
project = args.dir.expanduser().resolve() if args.dir else toolkit / 'local/episodes' / ep
notes = workspace / '.scratch/youtube/episodes' / ep
if (project / 'episode.json').exists():
    existing = json.loads((project / 'episode.json').read_text())
    if existing.get('id') != ep:
        raise SystemExit(f'项目编号不符，未修改：{project}')
def copy_missing(src, dst):
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
for src in (kit / 'template').rglob('*'):
    if src.is_file() and '__pycache__' not in src.parts and src.name != '.DS_Store':
        copy_missing(src, project / src.relative_to(kit / 'template'))
notes.mkdir(parents=True, exist_ok=True)
for name in ('script', 'asset-needs', 'beat-table'):
    copy_missing(project / f'{name}.example.md', notes / f'{name}.md')
copy_missing(project / 'anchors.example.json', notes / 'anchors.json')
(notes / 'evidence').mkdir(exist_ok=True)
for name in ('voice', 'assets/local', 'assets/props', 'assets/stock', 'renders'):
    (project / name).mkdir(parents=True, exist_ok=True)
config = json.loads((project / 'episode.example.json').read_text())
config['id'] = ep
if not (project / 'episode.json').exists():
    (project / 'episode.json').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
copy_missing(project / 'beats.example.json', project / 'beats.json')
print(json.dumps({'project':str(project),'notes':str(notes),'next':'准备素材与旁白，运行voice.sh，再调整episode.json和beats.json并构建。'},ensure_ascii=False,indent=2))
PY
