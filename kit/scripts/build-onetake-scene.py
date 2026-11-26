#!/usr/bin/env python3
"""从 JSON 与本地素材生成可复用的 Onetake 场景。"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kit.onetake.scene import build

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(build(json.loads(args.spec.read_text()), args.spec.resolve().parent, args.output))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
