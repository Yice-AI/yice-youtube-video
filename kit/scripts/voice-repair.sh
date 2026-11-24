#!/bin/bash
set -euo pipefail
voice_repair_dir=$(cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$voice_repair_dir/workspace.py" voice-repair.py "$@"
