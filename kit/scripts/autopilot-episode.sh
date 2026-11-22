#!/bin/sh
set -eu
if [ "$#" -lt 2 ]; then
  echo '用法：autopilot-episode.sh <voice-timing.json> <asset-plan.json> [output-dir]' >&2
  exit 2
fi
VOICE=$1
PLAN=$2
OUT=${3:-$(dirname "$PLAN")}
mkdir -p "$OUT"
python3 - "$VOICE" "$PLAN" "$OUT" <<'PY'
import json, sys
from pathlib import Path
from kit.editorial.autopilot import SemanticBeatPlanner, UniqueAssetLedger
voice= json.loads(Path(sys.argv[1]).read_text())
cues=voice.get('cues', voice if isinstance(voice,list) else [])
planner=SemanticBeatPlanner()
plan=planner.asset_plan(planner.plan(cues, asset_names=[]), UniqueAssetLedger())
Path(sys.argv[2]).write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'beats':len(plan['beats']), 'output':sys.argv[2]}, ensure_ascii=False))
PY
