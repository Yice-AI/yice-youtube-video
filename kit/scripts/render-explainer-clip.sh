#!/usr/bin/env bash
set -euo pipefail

SPEC=''
OUT=''
AUDIT=0
while (($#)); do
  case "$1" in
    --spec) SPEC=${2:?--spec 需要 JSON 路径}; shift 2 ;;
    --out) OUT=${2:?--out 需要 MP4 路径}; shift 2 ;;
    --audit) AUDIT=1; shift ;;
    *) echo "用法：$0 --spec clip.json --out clip.mp4 [--audit]" >&2; exit 2 ;;
  esac
done
[[ -n "$SPEC" ]] || { echo '--spec 必填' >&2; exit 2; }
if [[ -z "${PLAYWRIGHT_EXECUTABLE_PATH:-}" && -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
  export PLAYWRIGHT_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fi
RUNNER=(uv run --with playwright python3)
if (( AUDIT )); then
  "${RUNNER[@]}" "$(dirname "$0")/../explainer/render.py" --spec "$SPEC" --audit
fi
[[ -n "$OUT" ]] || { echo '--out 必填' >&2; exit 2; }
"${RUNNER[@]}" "$(dirname "$0")/../explainer/render.py" --spec "$SPEC" --out "$OUT"
