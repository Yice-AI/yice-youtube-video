#!/bin/bash
set -euo pipefail
rec_bridge_dir=$(cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$rec_bridge_dir/rec-bridge.py" "$@"
