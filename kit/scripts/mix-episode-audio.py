#!/usr/bin/env python3
"""按清单合成全片人声、底乐、动作音效与独立伴奏轨。"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kit.editorial.audio_mix import mix_episode_audio


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    try:
        report = mix_episode_audio(data.get('audio',data),float(data['duration']),args.output,
                                   root=args.manifest.resolve().parent)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report,ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
