#!/bin/bash
set -euo pipefail
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 - "$KIT_DIR" "$@" <<'PY'
import argparse, json, re, shlex, shutil, sys
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
    existing = project / f'{name}.md'
    copy_missing(existing if existing.is_file() else project / f'{name}.example.md',notes / f'{name}.md')
copy_missing(notes / 'script.md',project / 'script.md')
if not (notes / 'anchors.json').exists():
    (notes / 'anchors.json').write_text('[]\n')
(notes / 'evidence').mkdir(exist_ok=True)
for name in ('voice', 'assets/local', 'assets/props', 'assets/stock', 'assets/ref-clips', 'renders'):
    (project / name).mkdir(parents=True, exist_ok=True)
config = json.loads((project / 'episode.example.json').read_text())
config['id'] = ep
if not (project / 'episode.json').exists():
    (project / 'episode.json').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
copy_missing(project / 'beats.example.json', project / 'beats.json')
copy_missing(project / 'episode-manifest.example.json',project / 'episode-manifest.json')
scripts = shlex.quote(str(kit/'scripts'))
steps = [
    f'{scripts}/record-web-cam.sh --project . --url "$PUBLIC_URL" --id shot-a --seconds 7',
    f'{scripts}/voice.sh script.md --backend kaggle --speed 1.0 --output voice',
    f'{scripts}/scaffold-manifest.sh --voice-manifest voice/voice-manifest.json --output episode-manifest.draft.json',
    f'{scripts}/scout-video-scenes.sh --verify-manifest episode-manifest.json --output verify',
    f'{scripts}/assemble-episode.sh episode-manifest.json --output out --workers 2',
    f'{scripts}/audit-v3.sh --v10 --project out --timeline out/shot-timeline.json --rendered out/episode.mp4',
    f'{scripts}/thumbnail.sh --help',
]
print(json.dumps({'project':str(project),'notes':str(notes),'next':steps},ensure_ascii=False,indent=2))
PY
