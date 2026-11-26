"""Turn a declarative scene into an offline HyperFrames project."""
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil

HERE = Path(__file__).parent
RECIPES = ('carousel_3d_select', 'layer_explode_3d', 'roadmap_thread_camera', 'literal_action_stage')
ACTIONS = ('bad_slides_pileup', 'dead_image_locked', 'slot_lock_fill', 'folder_pack_outro')


def number(value, low, high, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} 应在 {low} 至 {high} 之间')
    return value


def label(value):
    return html.escape(str(value), quote=True)


def build(spec, source_dir, output, gsap):
    recipe = spec['recipe']
    if recipe not in RECIPES:
        raise ValueError('未知空间配方')
    ident = spec['id']
    if not re.fullmatch(r'[A-Za-z][\w-]*', ident, re.ASCII):
        raise ValueError('合成 id 须以字母开头')
    duration = number(spec['duration'], 1, 120, 'duration')
    data = dict(spec.get('data', {}))
    assets = {'media/SourceHanSansCN-Bold.otf': HERE.parent/'template/assets/fonts/SourceHanSansCN-Bold.otf',
              'media/LICENSE-SourceHan-OFL.txt': HERE.parent/'template/assets/fonts/LICENSE-SourceHan-OFL.txt'}

    def picture(source):
        path = (source_dir / source).resolve()
        if not path.is_file() or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.svg'}:
            raise ValueError(f'需要本地图片或 SVG：{source}')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:20]
        name = f'media/{digest}{path.suffix.lower()}'
        assets[name] = path
        return name

    def img(source):
        return f'<img src="{picture(source)}" alt="">'

    def items(key, low, high):
        values = data.get(key)
        if not isinstance(values, list) or not low <= len(values) <= high:
            raise ValueError(f'{key} 需要 {low} 至 {high} 项')
        return values

    overlay = ''
    if recipe == 'carousel_3d_select':
        images = items('images', 5, 12)
        selected = data['selected_index']
        if type(selected) is not int or not 0 <= selected < len(images):
            raise ValueError('selected_index 超出图片范围')
        number(data['select_at'], .3, duration-.35, 'select_at')
        body = ''.join(f'<div class="orbit-card" data-spatial-subject>{img(src)}</div>' for src in images)
        body = f'<div class="orbit">{body}</div>'
    elif recipe == 'layer_explode_3d':
        source = picture(data['image'])
        bottom = picture(data['background_image']) if data.get('background_image') else source
        chips, borders = [], []
        boxes = items('boxes', 1, 400)
        captions = data.get('box_labels', [])
        if captions and (not isinstance(captions, list) or len(captions) != len(boxes)):
            raise ValueError('每个文字框需要一个对应的实际文本')
        for index,(x,y,w,h) in enumerate(boxes):
            for value in (x,y):
                number(value, 0, 1, '归一化位置')
            number(w, .000001, 1-x+.00001, '框宽'); number(h, .000001, 1-y+.00001, '框高')
            pos = f'left:{100*x:.4f}%;top:{100*y:.4f}%;width:{100*w:.4f}%;height:{100*h:.4f}%'
            bx,by=(100*x/(1-w) if w<1 else 0),(100*y/(1-h) if h<1 else 0)
            image_style = f"background-image:url('{source}');background-size:{100/w:.3f}% {100/h:.3f}%;background-position:{bx:.3f}% {by:.3f}%"
            content = (f'<span>{label(captions[index])}</span>' if captions else '')
            chips.append(f'<i class="chip" style="{pos};{image_style}">{content}</i>')
            borders.append(f'<i class="bare-box" style="{pos}"></i>')
        number(data['count'], 1, 1000000, 'count')
        body = (f'<div class="model" data-spatial-subject><div class="layer base" data-spatial-layer="base"><img src="{bottom}" alt=""><img class="face" src="{source}" alt=""><b class="plate-tag">01　柔光底纹层</b></div>'
                f'<div class="layer skeleton" data-spatial-layer="skeleton">{"".join(borders)}<b class="plate-tag">02　矢量图表层</b></div><div class="layer letters" data-spatial-layer="letters"><div class="text-boxes">{"".join(chips)}</div><b class="plate-tag">03　{len(boxes)} 个独立文字层</b></div>'
                '<i class="guide g1"></i><i class="guide g2"></i></div>')
        overlay = (f'<aside class="meter"><strong>0</strong><b>{label(data.get("unit", "个图层"))}</b></aside>')
    elif recipe == 'roadmap_thread_camera':
        nodes = items('steps', 3, 4)
        if type(data['focus_step']) is not int or not 0 <= data['focus_step'] < len(nodes):
            raise ValueError('focus_step 超出节点数')
        previous = -1
        pts, cards = [], []
        for i,node in enumerate(nodes):
            at = number(node['at'], 0, duration-.45, '节点时间')
            if at <= previous:
                raise ValueError('节点时间必须递增')
            previous = at
            x,y=260+i*1370/(len(nodes)-1), 460+(i%2)*135
            pts.append((x,y))
            cards.append(f'<section class="node" style="left:{x-125}px;top:{y-88}px"><small>{label(node["no"])}</small><h2>{label(node["title"])}</h2><p>{label(node["sub"])}</p></section>')
        path = f'M -60 600 C 60 570,120 {pts[0][1]},260 {pts[0][1]}'
        for (x,y),(xx,yy) in zip(pts,pts[1:]):
            path += f' C {x+210} {y-90},{xx-200} {yy+80},{xx} {yy}'
        body = f'<div class="route-map"><svg viewBox="0 0 1920 1080"><path d="{path}" class="track"/><path d="{path}" class="thread" pathLength="1"/><circle class="pen-tip" r="8"/></svg>{"".join(cards)}</div>'
    else:
        action = data['action']
        if action not in ACTIONS:
            raise ValueError('未知物理动作')
        if action == 'bad_slides_pileup':
            body = ''.join(f'<div class="old-card"><small>0{i+1}</small><h2>{label(t)}</h2><i></i><i></i><i></i></div>' for i,t in enumerate(items('labels',3,3))) + f'<div class="warning">×　{label(data["warning"])}</div>'
        elif action == 'dead_image_locked':
            body = f'<div class="locked-shot">{img(data["image"])}</div><div class="pointer">↖</div><i class="ripple"></i><div class="warning">⊠　{label(data["warning"])}</div>'
        elif action == 'slot_lock_fill':
            words = items('labels',3,4)
            body = '<div class="plan-lines" data-spatial-subject>' + ''.join(f'<div>{label(word)}</div>' for word in words) + '</div><div class="slots" data-spatial-subject>' + ''.join('<i></i>' for _ in words) + '</div>' + ''.join(f'<b class="token">{label(w)}</b>' for w in words)
        else:
            body = ''.join(f'<div class="file-card">{img(src)}</div>' for src in items('images',2,6)) + f'<div class="command">{label(data["command"])}</div><div class="folder"><small>{label(data["folder"])}</small><h2>SKILL.md</h2></div>'

    accent=spec.get('accent','#df6b50')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',accent):
        raise ValueError('accent 需要六位颜色值')
    css=(HERE/'stage.css').read_text().replace('STAGE','#'+ident)
    motion = action if recipe == 'literal_action_stage' else recipe
    script=(HERE/'camera.js').read_text() + (HERE/(motion+'.js')).read_text()
    settings_data = {key:data[key] for key in ('selected_index','select_at','count','focus_step','action') if key in data}
    if 'steps' in data:
        settings_data['steps'] = [{'at':step['at']} for step in data['steps']]
    settings=json.dumps(settings_data,ensure_ascii=False).replace('<','\\u003c')
    markup=f'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><style>{css}</style><script src="vendor/gsap.min.js"></script></head><body>
<div id="{ident}" data-composition-id="{ident}" data-start="0" data-duration="{duration}" data-width="1920" data-height="1080" data-spatial-recipe="{recipe}" data-spatial-action="{label(data.get('action',''))}" style="--accent:{accent}">
<div class="stage-light"></div><div class="bloom"></div><header data-spatial-title><small>{label(spec.get('eyebrow',''))}</small><h1>{label(spec.get('title',''))}</h1></header><div class="stage"><div class="world">{body}</div></div><div class="streak"></div>{overlay}<div class="film-grain"></div></div>
<script>(()=>{{const root=document.getElementById('{ident}'), q=s=>root.querySelector(s), all=s=>[...root.querySelectorAll(s)];
const data={settings}, dur={duration}, tl=gsap.timeline({{paused:true}});{script}
tl.to({{}},{{duration:.001}},{duration}-.001);window.__timelines=window.__timelines||{{}};window.__timelines['{ident}']=tl;
}})();</script></body></html>'''
    for name,path in {**assets,'vendor/gsap.min.js':gsap}.items():
        dest=output/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    (output/'index.html').write_text(markup)
    return output/'index.html'
