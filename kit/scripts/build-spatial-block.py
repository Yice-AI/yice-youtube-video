#!/usr/bin/env python3
"""生成离线、可逐帧定位的原生 HyperFrames 空间动效。"""
import argparse
import json
from pathlib import Path
import sys

from workspace import resolve_gsap_runtime
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kit.spatial.block import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        entry = build(json.loads(args.spec.read_text()), args.spec.resolve().parent,
                      args.output, resolve_gsap_runtime())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(entry)


if __name__ == '__main__':
    main()
