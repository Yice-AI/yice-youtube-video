#!/bin/bash
set -euo pipefail
rec_demo_dir=$(cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$rec_demo_dir/rec-demo.py" "$@"
