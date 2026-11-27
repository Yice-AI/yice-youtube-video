#!/usr/bin/env bash
set -euo pipefail
exec "${YICE_VOICE_PYTHON:-python3}" "$(dirname "$0")/harvest-showcase-media.py" "$@"
