#!/bin/bash
set -euo pipefail
# 草稿与正式配音的 --stage、后端和声学检查统一交给 Python 入口。
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$KIT_DIR/scripts/workspace.py" voice.py "$@"
