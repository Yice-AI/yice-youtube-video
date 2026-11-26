#!/usr/bin/env python3
"""把本机 Onetake 合成渲染成分幕可消费的固定帧率视频。"""

import argparse
import json
from math import ceil, isfinite
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from workspace import ONETAKE_COLORS, ONETAKE_FONTS, composition_files, onetake_look, onetake_python, resolve_onetake, render_priority, render_workers

FONT_ROOT = Path(__file__).resolve().parents[1] / 'template/assets/fonts'

# 使用上游采样和连续性算法，同时保留其 CLI 文本报告中才有的逐帧失败信息。
PROBE = r"""
import asyncio, json, runpy, sys

probe, entry = sys.argv[1:]
upstream = runpy.run_path(probe)

async def measure():
    async with upstream['async_playwright']() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.add_init_script(upstream['TRACKER_JS'])
        await page.goto(entry)
        contract = await page.evaluate('''async () => {
            const meta = window.__meta;
            if (typeof window.__seek !== 'function' || window.__ready == null ||
                !Number.isFinite(meta?.dur) || meta.dur <= 0 || meta.fps !== 30)
                throw new Error('Expected __seek, __ready and __meta with dur > 0, fps = 30');
            await window.__ready;
            return {beats: meta.beats ?? meta.cuts ?? [],
                    events: typeof window.__events === 'function' ? await window.__events() : []};
        }''')
        result = await upstream['collect_page'](page, entry)
        result.update(W=1920, H=1080)
        await browser.close()
    return {**contract, 'dur': result['dur'], 'fps': result['fps'], 'seek_errors': result['failed'],
            'page_errors': errors, 'continuity': upstream['continuity'](result)}

print(json.dumps(asyncio.run(measure())))
"""


def write_look_assets(folder, look):
    colors = {name:look['color'][name] for name in ONETAKE_COLORS}
    if not all(re.fullmatch(r'#[0-9a-fA-F]{6}',color) for color in colors.values()):
        raise ValueError('Onetake 色板须由八个十六进制颜色组成')
    faces = {
        'display':('"Source Han Serif CN",serif',900),
        'text':('"Source Han Sans CN",sans-serif',700),
        'mono':('"Source Code Pro",monospace',400),
    }
    types = {role:dict(stack=stack,weight=weight,tracking=float(look['type'][role]['tracking']))
             for role,(stack,weight) in faces.items()}
    styles = [f'--{key}:{value}' for key,value in colors.items()]
    for role,face in types.items():
        styles.extend((f"--{role}:{face['stack']}", f"--{role}-weight:{face['weight']}",
                       f"--{role}-tracking:{face['tracking']}em"))
    (folder/'look-tokens.css').write_text(':root{'+';'.join(styles)+'}\n')
    meta = json.dumps(dict(name=look['name'],color=colors,type=types),ensure_ascii=False)
    (folder/'look-tokens.js').write_text(
        'window.LOOK='+meta+';\n'
        'LOOK.font=(role,px,weight)=>`${weight || LOOK.type[role].weight} ${px}px ${LOOK.type[role].stack}`;\n'
        'LOOK.track=(role,px)=>`${(LOOK.type[role].tracking*px).toFixed(2)}px`;\n'
        'LOOK.ready=Promise.all(Object.keys(LOOK.type).map(role=>document.fonts.load(LOOK.font(role,32),"Aa 中文"))).then(()=>document.fonts.ready);\n'
    )


def stage_composition(entry, folder, runtime, *, look=None):
    for source in composition_files(entry):
        target = folder / source.relative_to(entry.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    staged = folder / entry.name
    html = staged.read_text()
    additions = []
    for name in ('motion.js', 'ui_kit.js'):
        source = runtime / 'lib' / name
        if not source.is_file():
            continue
        for target in (folder / name, folder / 'lib' / name):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if not re.search(rf'<script\b[^>]*\bsrc=["\'](?:\./)?(?:lib/)?{re.escape(name)}["\']', html, re.I):
            additions.append(f'<script src="lib/{name}"></script>')
    fonts = folder / 'assets/fonts'
    fonts.mkdir(parents=True, exist_ok=True)
    rules = []
    for name, family, weight in zip(ONETAKE_FONTS, ('Source Han Sans CN', 'Source Han Serif CN', 'Source Code Pro'),
                                    (700, 900, 400)):
        shutil.copy2(FONT_ROOT / name, fonts / name)
        rules.append(f'@font-face{{font-family:"{family}";src:url("assets/fonts/{name}");font-weight:{weight}}}')
    additions.append('<style>' + ''.join(rules) + '</style>')
    if look is not None:
        write_look_assets(folder,look)
        additions.append('<link rel="stylesheet" href="look-tokens.css"><script src="look-tokens.js"></script>')
    head = re.search(r'<head(?:\s[^>]*)?>', html, re.I)
    if head:
        html = html[:head.end()] + ''.join(additions) + html[head.end():]
    else:
        doctype = re.match(r'\s*<!doctype[^>]*>', html, re.I)
        at = doctype.end() if doctype else 0
        html = html[:at] + ''.join(additions) + html[at:]
    staged.write_text(html)
    return staged


def validate_probe(probe, allow_staccato):
    continuity = probe['continuity']
    if probe['seek_errors'] or probe['page_errors']:
        raise ValueError(f"Onetake 页面采样失败：{probe['seek_errors'][:1] or probe['page_errors'][:1]}")
    boundaries = continuity['events']
    if boundaries and all(boundary['kind'] == 'bare' for boundary in boundaries) and not allow_staccato:
        raise ValueError('Onetake 跨拍全部为 bare，需要连续承接或显式声明 allow_staccato')
    if not isinstance(probe['beats'], list) or any(
        type(beat) not in (int, float) or not 0 <= beat < probe['dur'] for beat in probe['beats']
    ):
        raise ValueError('Onetake __meta.beats 须为镜头内的时间点')
    if not isinstance(probe['events'], list) or any(
        not isinstance(event, dict) or type(event.get('t')) not in (int, float)
        or not 0 <= event['t'] < probe['dur'] or not isinstance(event.get('kind'), str) or not event['kind']
        or ('gain' in event and (type(event['gain']) not in (int, float) or not isfinite(event['gain']) or event['gain'] < 0))
        for event in probe['events']
    ):
        raise ValueError('Onetake __events() 须返回有效的镜头内 {t, kind, gain?} 列表')


def render_clip(entry, output, *, shutter=180, workers=None, span=None, allow_staccato=False, look=None, look_from_shots=()):
    workers = render_workers(workers)
    runtime = resolve_onetake()
    if runtime is None:
        raise ValueError('找不到 Onetake，请设置 YICE_ONETAKE_DIR')
    if not 0 < shutter <= 360 or workers < 1 or (span is not None and (not isfinite(span) or span <= 0)):
        raise ValueError('Onetake 快门、进程数或镜头时长无效')
    if entry.is_dir():
        entry = entry / 'comp.html'
    entry, output = entry.absolute(), output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    python = onetake_python()
    with TemporaryDirectory(prefix='.onetake-', dir=output.parent) as temporary:
        work = Path(temporary)
        palette = onetake_look(runtime,look,shots=look_from_shots,output=work/'product.json') if look is not None or look_from_shots else None
        staged = stage_composition(entry, work / 'composition', runtime, look=palette)
        result = subprocess.run([*python, '-c', PROBE, str(runtime / 'scripts/probe.py'), staged.as_uri()],
                                check=True, **render_priority(), stdout=subprocess.PIPE, text=True)
        probe = json.loads(result.stdout)
        probe_path = output.with_suffix('.onetake-probe.json')
        probe_pending = work / 'probe.json'
        probe_pending.write_text(json.dumps(probe, ensure_ascii=False, indent=2) + '\n')
        try:
            validate_probe(probe, allow_staccato)
        except ValueError:
            probe_pending.replace(probe_path)
            raise
        pending = work / 'render.mp4'
        subprocess.run([*python, str(runtime / 'scripts/render.py'), str(staged), '--out', str(pending),
                        '--fps', '30', '--shutter', str(shutter), '--workers', str(workers)], check=True, **render_priority())
        render_path = pending.with_suffix('.render.json')
        render = json.loads(render_path.read_text())
        if render['fps'] != 30 or render['size'] != [1920, 1080] or render['shutter'] != shutter:
            raise ValueError('Onetake 渲染分辨率、帧率或快门与请求不符')
        render['comp'] = entry.name
        if palette is not None:
            render['look'] = {key:palette[key] for key in ('name','color')}
        if span is not None:
            frames = ceil((span + .35) * 30 - 1e-6)
            if render['frames'] < frames:
                padded = work / 'padded.mp4'
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(pending),
                                '-vf', f"tpad=stop_mode=clone:stop={frames - render['frames']}",
                                '-an', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-threads', '2', str(padded)], check=True, **render_priority())
                pending = padded
                render['padded_frames'] = frames
        render_path.write_text(json.dumps(render, ensure_ascii=False, indent=2) + '\n')
        probe_pending.replace(probe_path)
        render_path.replace(output.with_suffix('.render.json'))
        pending.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('composition', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--shutter', type=float, default=180)
    parser.add_argument('--workers', type=int)
    parser.add_argument('--span', type=float)
    parser.add_argument('--allow-staccato', action='store_true')
    parser.add_argument('--look')
    parser.add_argument('--look-from-shots', nargs='+', type=Path, default=())
    args = parser.parse_args()
    try:
        render_clip(args.composition, args.out, shutter=args.shutter, workers=args.workers,
                    span=args.span, allow_staccato=args.allow_staccato,look=args.look,look_from_shots=args.look_from_shots)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
