#!/usr/bin/env python3
"""检索本机双引擎色板、动效配方和组件目录。"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from workspace import onetake_look, onetake_looks, resolve_hyperframes_command, resolve_onetake

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from kit.editorial.editorial import PALETTES

ROLES = ('Hook','Problem','Product_Intro','Key_Feature','Benefits','Social_Proof','CTA','Brand_Outro')
TOPICS = {
    'paper':'清爽产品交互、教程、工具演示',
    'dusk':'夜景、技术发布、空间感',
    'tabletop':'实物、手作、桌面流程',
    'ultramarine':'数据增长、产品指标、商业分析',
    'riso':'印刷质感、设计、观点对撞',
    'ember':'深度叙事、暖调产品、衬线金句',
}


def animation_directory():
    override = os.environ.get('YICE_HYPERFRAMES_ANIMATION_DIR')
    dirs = [Path(override).expanduser()] if override else []
    dirs += [Path.home()/base/'skills/hyperframes-animation' for base in ('.claude','.agents','.codex')]
    root = next((path for path in dirs if (path/'blueprints-index.md').is_file()),None)
    if root is None:
        raise ValueError('找不到本机 HyperFrames Animation 动效参考')
    return root


def blueprints(root, role=None):
    markup = (root/'blueprints-index.md').read_text()
    entries = re.findall(r'<blueprint id="([^"]+)" roles="([^"]+)" duration="([^"]+)">\s*(.*?)\s*</blueprint>',
                         markup,re.S)
    rows = []
    for name,slots,duration,description in entries:
        roles = slots.split(', ')
        if role is None or role in roles:
            rows.append(dict(id=name,roles=roles,duration=duration,description=description,
                             recipe=str(root/f'blueprints/{name}.md')))
    return rows


def rules(root):
    markup = (root/'rules-index.md').read_text()
    entries = re.findall(r'^<([\w-]+) path="(rules/[^"]+)">(.*?)</\1>',markup,re.M)
    return [dict(id=name,description=description,recipe=str(root/path)) for name,path,description in entries]


def transitions(root):
    catalog = (root/'transitions/catalog.md').read_text()
    entries = re.findall(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*`(transitions/[^\`]+)`\s*\|',catalog,re.M)
    return [dict(category=group,moves=moves.split(', '),recipe=str(root/path)) for group,moves,path in entries]


def onetake_moves(runtime):
    categories = re.findall(r'^ \*   (enter|carry|contact|camera|fluid)\s+(.+)$',
                            (runtime/'lib/motion.js').read_text(),re.M)
    rows = [dict(id=name,category='curves') for name in ('spring','spline')]
    for category,items in categories:
        for name in items.split(' · '):
            if name.startswith('sim.{'):
                rows.extend(dict(id='sim.'+move,category=category) for move in name[5:-1].split(', '))
            elif name not in {'project','unproject','projectBox','screenTravel'}:
                rows.append(dict(id=name,category=category))
    for row in rows:
        row['reference'] = str(runtime/'references/motion-library.md')
    return rows


def search_registry(query):
    env = {**os.environ,'npm_config_offline':'true','HYPERFRAMES_TELEMETRY_DISABLED':'1','DO_NOT_TRACK':'1'}
    result = subprocess.run([*resolve_hyperframes_command(),'catalog','--query',query,'--json'],
                            check=True,capture_output=True,text=True,env=env)
    return json.loads(result.stdout)


def readable(result):
    if isinstance(result,list):
        return '\n'.join(' · '.join(str(row[key]) for key in ('id','category','duration','description','recipe','reference')
                                   if key in row) + (f" · {', '.join(row['moves'])}" if 'moves' in row else '')
                         for row in result)
    return json.dumps(result,ensure_ascii=False,indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for option in ('list-looks','list-blueprints','list-rules','list-onetake-moves','list-transitions'):
        actions.add_argument('--'+option,action='store_true')
    actions.add_argument('--from-shot',nargs='+',type=Path)
    actions.add_argument('--search-registry')
    parser.add_argument('--role',choices=ROLES)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--json',action='store_true')
    args = parser.parse_args(argv)
    if args.role and not args.list_blueprints:
        parser.error('--role 只用于 --list-blueprints')
    if bool(args.output) != bool(args.from_shot):
        parser.error('--from-shot 需要 --output')
    try:
        if args.list_looks or args.list_onetake_moves or args.from_shot:
            runtime = resolve_onetake()
            if runtime is None:
                raise ValueError('找不到本机 Onetake')
        if args.list_looks:
            result = dict(onetake={name:dict(spec,topics=TOPICS.get(name,'')) for name,spec in onetake_looks(runtime).items()},
                          stage=PALETTES)
        elif args.from_shot:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            result = onetake_look(runtime,shots=args.from_shot,output=args.output)
        elif args.list_blueprints:
            result = blueprints(animation_directory(),args.role)
        elif args.list_rules:
            result = rules(animation_directory())
        elif args.list_onetake_moves:
            result = onetake_moves(runtime)
        elif args.list_transitions:
            result = transitions(animation_directory())
        else:
            result = search_registry(args.search_registry)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        parser.exit(1,f'{error}\n')
    print(json.dumps(result,ensure_ascii=False,indent=2) if args.json else readable(result))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
