"""Compile editable data into a frame-seekable, offline Onetake composition."""
from hashlib import sha256
from html import escape
import json
from math import isfinite
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).parent
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.svg')
VIDEO_EXTS = ('.mp4', '.webm')
RECIPES = (
    'duplicate_laser_sweep', 'bitmap_lock_glitch', 'energy_roadmap_dive',
    'live_control_sync', 'capsule_archive_seal',
    'split_wipe_compare', 'handdrawn_sketch_stage',
)


def _extract_video_frames(path, output, duration):
    digest = sha256(path.read_bytes()).hexdigest()[:20]
    fps = 24
    max_dur = min(float(duration) + 0.5, 12.0)
    frame_dir = output / f'vframes_{digest}'
    existing = sorted(frame_dir.glob('f_*.jpg')) if frame_dir.is_dir() else []
    if not existing:
        frame_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            'ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(path),
            '-t', f'{max_dur:.3f}',
            '-vf', f"fps={fps},scale='min(960,iw)':-2:flags=lanczos",
            '-q:v', '3', str(frame_dir / 'f_%04d.jpg'),
        ]
        subprocess.run(cmd, check=True)
        existing = sorted(frame_dir.glob('f_*.jpg'))
        if not existing:
            raise ValueError(f'视频未能抽出任何帧：{path.name}')
    return {'type': 'video', 'fps': fps, 'frames': [f'vframes_{digest}/{p.name}' for p in existing]}


def build(spec, source_dir, output):
    recipe = spec['recipe']
    duration = spec['duration']
    if recipe not in RECIPES or type(duration) not in (int, float) or not isfinite(duration) or not 1 <= duration <= 120:
        raise ValueError('需要已知 Onetake 配方及 1–120 秒时长')
    data = spec['data']
    output.mkdir(parents=True, exist_ok=True)

    def image(source):
        path = (source_dir / source).resolve()
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            raise ValueError(f'需要本地截图：{source}')
        name = sha256(path.read_bytes()).hexdigest()[:20] + path.suffix.lower()
        if not (output / name).exists():
            shutil.copyfile(path, output / name)
        return name

    def media_slot(source):
        path = (source_dir / source).resolve()
        ext = path.suffix.lower()
        if not path.is_file() or ext not in (*IMAGE_EXTS, *VIDEO_EXTS):
            raise ValueError(f'需要本地图片或视频：{source}')
        if ext in VIDEO_EXTS:
            return _extract_video_frames(path, output, duration)
        return {'type': 'image', 'src': image(source)}

    def items(key, low, high):
        rows = data[key]
        if not isinstance(rows, list) or not low <= len(rows) <= high:
            raise ValueError(f'{key} 需要 {low}–{high} 项')
        return rows

    values = dict(HUD=escape(spec.get('hud', recipe.replace('_', ' ').upper())), DURATION=str(duration))
    styles = (HERE / 'stage.css').read_text()
    if recipe == 'duplicate_laser_sweep':
        cards = items('cards', 3, 3)
        values['CARDS'] = ''.join(
            f'<section class="slidecard" data-spatial-subject><small>{escape(data["series"])} · {i:02d}</small>'
            f'<h2>{escape(title)}</h2><p>{escape(data["caption"])}</p><i></i><i></i></section>'
            for i, title in enumerate(cards, 1))
        values['LABEL'] = escape(data.get('warning', 'DUPLICATE LAYOUT ×3'))
    elif recipe == 'bitmap_lock_glitch':
        values.update(IMAGE=image(data['image']), LABEL=escape(data.get('warning', 'FLAT BITMAP · 0 EDITABLE NODES')))
    elif recipe == 'energy_roadmap_dive':
        stations = items('stations', 3, 4)
        target = data.get('target', 0)
        if type(target) is not int or not 0 <= target < len(stations):
            raise ValueError('target 须指向实际路线站点')
        centers = [round(375 + i * 1170 / (len(stations) - 1)) for i in range(len(stations))]
        nodes, curve = [], 'M-150 708'
        for i, (station, x) in enumerate(zip(stations, centers)):
            y = 420 if i % 2 == 0 else 458
            pic = image(station['image'])
            inside = image(data['dive_image']) if i == target and data.get('dive_image') else pic
            inset = f'<img id="terminal-inside" src="{inside}" alt="">' if i == target else ''
            nodes.append(f'<section class="station" data-overview-station data-spatial-subject style="left:{x-173}px;top:{y}px">'
                         f'<img src="{pic}" alt="">{inset}<strong>{i+1:02d}　{escape(station["label"])}</strong>'
                         f'<small>{escape(station.get("caption",""))}</small></section>')
            curve += f' S{x-150} {420 if i%2==0 else 680} {x} {y+135}'
        values.update(STATIONS=''.join(nodes), PATH=curve, TARGET=str(target), TARGET_X=str(centers[target]))
        styles += (HERE / 'roadmap.css').read_text()
    elif recipe == 'live_control_sync':
        values.update(IMAGE=image(data['image']), SLIDER=escape(data['slider']), SWITCH=escape(data['switch']),
                      CANVAS=escape(data['canvas']))
        styles += (HERE / 'controls.css').read_text()
    elif recipe == 'split_wipe_compare':
        mode = data.get('mode', 'center_scan')
        if mode not in ('center_scan', 'diagonal_wipe', 'quad_race'):
            raise ValueError(f'未知对比模式：{mode}')
        cfg = {
            'mode': mode,
            'before': media_slot(data['before']),
            'after': media_slot(data['after']),
        }
        values.update(
            BEFORE_LABEL=escape(data.get('before_label', '↺ 修改前')),
            AFTER_LABEL=escape(data.get('after_label', '✦ 修改后')),
            LEFT_META=escape(data.get('left_meta', 'BASELINE')),
            RIGHT_META=escape(data.get('right_meta', 'ENHANCED')),
            CONFIG=json.dumps(cfg, ensure_ascii=False).replace('<', '\\u003c'),
        )
        styles += (HERE / 'compare.css').read_text()
    elif recipe == 'handdrawn_sketch_stage':
        style_name = data.get('style', 'pencil_watercolor')
        if style_name not in ('pencil_watercolor', 'riso_halftone'):
            raise ValueError(f'未知手绘风格：{style_name}')
        nodes = data.get('nodes', [])
        if not isinstance(nodes, list) or not 2 <= len(nodes) <= 4:
            raise ValueError('handdrawn_sketch_stage 的 nodes 需要 2–4 项')
        cfg = {
            'style': style_name,
            'nodes': nodes,
            'monster': bool(data.get('monster', False)),
            'gauge': data.get('gauge'),
        }
        values.update(
            TITLE=escape(data.get('title') or spec.get('title') or '手绘概念推演'),
            CONFIG=json.dumps(cfg, ensure_ascii=False).replace('<', '\\u003c'),
        )
        styles += (HERE / 'sketch.css').read_text()
    else:
        values.update(IMAGES=json.dumps([image(s) for s in items('images', 2, 6)]),
                      PROJECT=escape(data['project']), FILE=escape(data.get('file', 'SKILL.md')),
                      COMMAND=escape(data['command'].removeprefix('$ ')))
        styles += (HERE / 'archive.css').read_text()

    shared = ''
    if recipe in ('duplicate_laser_sweep', 'bitmap_lock_glitch', 'energy_roadmap_dive'):
        shared = '<script>\n' + (HERE / 'lattice.js').read_text() + '</script>\n'
    elif recipe == 'handdrawn_sketch_stage':
        shutil.copyfile(HERE / 'sketch_brush.js', output / 'sketch_brush.js')
        shared = '<script src="sketch_brush.js"></script>\n'
    body = re.sub(r'@@([A-Z_]+)@@', lambda m: values[m[1]], (HERE / f'{recipe}.html').read_text())
    entry = output / 'comp.html'
    cinema = spec.get('stage_look') == 'cinema_black' and recipe == 'split_wipe_compare'
    stage_attrs = ' data-stage-look="cinema_black" data-onetake-recipe="split_wipe_compare"' if cinema else ''
    entry.write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><style>\n' + styles
                     + f'\n</style><body{stage_attrs}>\n' + shared + body + '\n</body></html>\n')
    return entry
