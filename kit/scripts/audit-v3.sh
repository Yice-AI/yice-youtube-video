#!/bin/sh
exec python3 "$(dirname "$0")/workspace.py" audit-v3.py "$@"
