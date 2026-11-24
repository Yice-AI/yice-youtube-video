#!/bin/bash
set -euo pipefail
rec_shot_dir=$(cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$rec_shot_dir/rec-shot.py" "$@"
