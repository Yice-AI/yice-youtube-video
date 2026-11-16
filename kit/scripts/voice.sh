#!/bin/bash
set -euo pipefail
# --seeds, ASR gates and automatic repair are forwarded to the shared Python flow.
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$KIT_DIR/scripts/workspace.py" voice.py "$@"
