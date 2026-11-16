#!/bin/bash
set -euo pipefail
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 - "$KIT_DIR" "$@" <<'PY'
import json, os, re, shutil, sys
from pathlib import Path
kit = Path(sys.argv[1])
sys.path.insert(0, str(kit / 'scripts'))
from workspace import load_environment
if len(sys.argv) != 3 or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', sys.argv[2]):
    raise SystemExit('用法：new-episode.sh <ep-id>；编号只用小写字母、数字、短横线和下划线')
ep = sys.argv[2]
workspace, toolkit = load_environment()
project = toolkit / 'local/episodes' / ep
notes = workspace / '.scratch/youtube/episodes' / ep
if project.exists() or notes.exists():
    raise SystemExit(f'已存在，未覆盖：{project} 或 {notes}')
shutil.copytree(kit / 'template', project, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))
notes.mkdir(parents=True)
for name in ('script', 'asset-needs', 'beat-table'):
    shutil.copy2(project / f'{name}.example.md', notes / f'{name}.md')
shutil.copy2(project / 'anchors.example.json', notes / 'anchors.json')
(notes / 'evidence').mkdir()
for name in ('voice', 'assets/local', 'assets/props', 'assets/stock', 'renders'):
    (project / name).mkdir(parents=True, exist_ok=True)
config = json.loads((project / 'episode.example.json').read_text())
config['id'] = ep
(project / 'episode.json').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
shutil.copy2(project / 'beats.example.json', project / 'beats.json')
print(json.dumps({'project':str(project),'notes':str(notes),'next':'准备素材与旁白，运行voice.sh，再调整episode.json和beats.json并构建。'},ensure_ascii=False,indent=2))
PY
