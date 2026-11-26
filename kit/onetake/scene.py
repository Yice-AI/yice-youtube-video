"""Compile editable data into a frame-seekable, offline Onetake composition."""
from hashlib import sha256
from html import escape
import json
from math import isfinite
from pathlib import Path
import re
import shutil

HERE = Path(__file__).parent
RECIPES = ('duplicate_laser_sweep', 'bitmap_lock_glitch', 'energy_roadmap_dive',
           'live_control_sync', 'capsule_archive_seal')


def build(spec, source_dir, output):
    recipe = spec['recipe']
    duration = spec['duration']
    if recipe not in RECIPES or type(duration) not in (int, float) or not isfinite(duration) or not 1 <= duration <= 120:
        raise ValueError('需要已知 Onetake 配方及 1–120 秒时长')
    data = spec['data']
    output.mkdir(parents=True, exist_ok=True)

    def image(source):
        path = (source_dir / source).resolve()
        if not path.is_file() or path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.svg'):
            raise ValueError(f'需要本地截图：{source}')
        name = sha256(path.read_bytes()).hexdigest()[:20] + path.suffix.lower()
        if not (output/name).exists():
            shutil.copyfile(path, output/name)
        return name

    def items(key, low, high):
        rows = data[key]
        if not isinstance(rows, list) or not low <= len(rows) <= high:
            raise ValueError(f'{key} 需要 {low}–{high} 项')
        return rows

    values = dict(HUD=escape(spec.get('hud', recipe.replace('_',' ').upper())), DURATION=str(duration))
    styles = (HERE/'stage.css').read_text()
    if recipe == 'duplicate_laser_sweep':
        cards = items('cards', 3, 3)
        values['CARDS'] = ''.join(
            f'<section class="slidecard" data-spatial-subject><small>{escape(data["series"])} · {i:02d}</small>'
            f'<h2>{escape(title)}</h2><p>{escape(data["caption"])}</p><i></i><i></i></section>'
            for i, title in enumerate(cards, 1))
        values['LABEL'] = escape(data.get('warning','DUPLICATE LAYOUT ×3'))
    elif recipe == 'bitmap_lock_glitch':
        values.update(IMAGE=image(data['image']), LABEL=escape(data.get('warning','FLAT BITMAP · 0 EDITABLE NODES')))
    elif recipe == 'energy_roadmap_dive':
        stations = items('stations', 3, 4)
        target = data.get('target', 0)
        if type(target) is not int or not 0 <= target < len(stations):
            raise ValueError('target 须指向实际路线站点')
        centers = [round(375 + i*1170/(len(stations)-1)) for i in range(len(stations))]
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
        styles += (HERE/'roadmap.css').read_text()
    elif recipe == 'live_control_sync':
        values.update(IMAGE=image(data['image']), SLIDER=escape(data['slider']), SWITCH=escape(data['switch']),
                      CANVAS=escape(data['canvas']))
        styles += (HERE/'controls.css').read_text()
    else:
        values.update(IMAGES=json.dumps([image(s) for s in items('images', 2, 6)]),
                      PROJECT=escape(data['project']), FILE=escape(data.get('file','SKILL.md')),
                      COMMAND=escape(data['command'].removeprefix('$ ')))
        styles += (HERE/'archive.css').read_text()
    shared = ''
    if recipe in ('duplicate_laser_sweep','bitmap_lock_glitch','energy_roadmap_dive'):
        shared = '<script>\n'+(HERE/'lattice.js').read_text()+'</script>\n'
    body = re.sub(r'@@([A-Z_]+)@@', lambda m: values[m[1]], (HERE/f'{recipe}.html').read_text())
    entry = output/'comp.html'
    entry.write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><style>\n'+styles
                     +'\n</style><body>\n'+shared+body+'\n</body></html>\n')
    return entry
