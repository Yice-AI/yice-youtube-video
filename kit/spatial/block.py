"""Turn a declarative scene into an offline HyperFrames project."""
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil

HERE = Path(__file__).parent
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
VIDEO_EXTS = {'.mp4', '.webm'}
RECIPES = (
    'carousel_3d_select', 'layer_explode_3d', 'roadmap_thread_camera', 'literal_action_stage',
    'perspective_video_fan', 'logo_bento_stage', 'cutout_parallax_stage',
    'documentary_ken_burns', 'step_tree_focus', 'progressive_sim_cards', 'formula_pill_chain',
)
ACTIONS = ('bad_slides_pileup', 'dead_image_locked', 'slot_lock_fill', 'folder_pack_outro')
LIGHT_LOOKS = {'editorial_paper', 'scroll_paper'}
STAGE_LOOKS = {'cyber_glass', 'editorial_paper', 'scroll_paper', 'ultramarine'}


def number(value, low, high, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} 应在 {low} 至 {high} 之间')
    return value


def label(value):
    return html.escape(str(value), quote=True)


def _trim_transparent_png(path, dest_dir):
    """Trim outer fully-transparent margins from a PNG so cutout subjects fill their stage cleanly."""
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(path) as opened:
        if 'A' not in opened.getbands():
            return None
        rgba = opened.convert('RGBA')
        alpha = rgba.getchannel('A')
        bbox = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
        if bbox is None:
            return None
        pad = 4
        box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
               min(rgba.width, bbox[2] + pad), min(rgba.height, bbox[3] + pad))
        if box == (0, 0, rgba.width, rgba.height):
            return None
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f'trimmed_{hashlib.sha256(path.read_bytes()).hexdigest()[:20]}.png'
        rgba.crop(box).save(out)
        return out


def _default_look(recipe, data):
    explicit = data.get('stage_look')
    if explicit is not None:
        if explicit not in STAGE_LOOKS:
            raise ValueError(f'未知 stage_look：{explicit}')
        return explicit
    if recipe == 'cutout_parallax_stage':
        return 'scroll_paper'
    if recipe in ('documentary_ken_burns', 'step_tree_focus', 'progressive_sim_cards', 'logo_bento_stage'):
        return 'editorial_paper'
    if recipe == 'formula_pill_chain':
        return 'ultramarine'
    return 'cyber_glass'


def build(spec, source_dir, output, gsap):
    recipe = spec['recipe']
    if recipe not in RECIPES:
        raise ValueError('未知空间配方')
    ident = spec['id']
    if not re.fullmatch(r'[A-Za-z][\w-]*', ident, re.ASCII):
        raise ValueError('合成 id 须以字母开头')
    duration = number(spec['duration'], 1, 120, 'duration')
    data = dict(spec.get('data', {}))
    fonts_dir = HERE.parent / 'template/assets/fonts'
    assets = {
        'media/SourceHanSansCN-Bold.otf': fonts_dir / 'SourceHanSansCN-Bold.otf',
        'media/SourceHanSerifCN-Bold.otf': fonts_dir / 'SourceHanSerifCN-Bold.otf',
        'media/SourceCodePro-Regular.otf': fonts_dir / 'SourceCodePro-Regular.otf',
        'media/LICENSE-SourceHan-OFL.txt': fonts_dir / 'LICENSE-SourceHan-OFL.txt',
    }
    trimmed_cache = output / '.trimmed'
    video_counter = 0

    def media_asset(source, *, allow_video=True, trim_alpha=False):
        path = (source_dir / source).resolve()
        exts = IMAGE_EXTS | VIDEO_EXTS if allow_video else IMAGE_EXTS
        if not path.is_file() or path.suffix.lower() not in exts:
            kind_msg = '本地图片或视频' if allow_video else '本地图片或 SVG'
            raise ValueError(f'需要{kind_msg}：{source}')
        actual = path
        if trim_alpha and path.suffix.lower() == '.png':
            trimmed = _trim_transparent_png(path, trimmed_cache)
            if trimmed is not None:
                actual = trimmed
        digest = hashlib.sha256(actual.read_bytes()).hexdigest()[:20]
        name = f'media/{digest}{actual.suffix.lower()}'
        assets[name] = actual
        return name, actual.suffix.lower() in VIDEO_EXTS

    def picture(source):
        return media_asset(source, allow_video=False)[0]

    def _is_non_widescreen_raster(path):
        if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
            return False
        try:
            from PIL import Image
            with Image.open(path) as opened:
                w, h = opened.size
            return h > 0 and not (1.28 <= (w / h) <= 2.05)
        except Exception:
            return False

    def media_tag(source, *, cls='', style=''):
        nonlocal video_counter
        name, is_video = media_asset(source, allow_video=True)
        cls_attr = f' class="{cls}"' if cls else ''
        if is_video:
            video_counter += 1
            vid_id = f'{ident}-v{video_counter}'
            return (f'<video id="{vid_id}"{cls_attr} src="{name}" muted playsinline preload="auto" '
                    f'data-start="0" data-duration="{duration}" '
                    f'style="width:100%;height:100%;object-fit:cover;{style}"></video>')
        style_attr = f' style="{style}"' if style else ''
        if _is_non_widescreen_raster(assets[name]):
            fg_cls = f'{cls} media-aspect-fg'.strip()
            return (f'<div class="media-aspect-box">'
                    f'<img class="media-aspect-bg" src="{name}" alt="">'
                    f'<img class="{fg_cls}" src="{name}" alt=""{style_attr}></div>')
        return f'<img{cls_attr} src="{name}" alt=""{style_attr}>'

    def img(source):
        return media_tag(source)

    def items(key, low, high):
        values = data.get(key)
        if not isinstance(values, list) or not low <= len(values) <= high:
            raise ValueError(f'{key} 需要 {low} 至 {high} 项')
        return values

    stage_look = spec.get('stage_look') or _default_look(recipe, data)
    if stage_look not in STAGE_LOOKS:
        raise ValueError(f'未知 stage_look：{stage_look}')
    hud = label(spec.get('hud') or spec.get('eyebrow') or spec.get('title', ''))
    header_html = f'<header data-spatial-title>{hud}</header>'
    bg_extra = ''
    overlay = ''

    if recipe == 'carousel_3d_select':
        images = items('images', 5, 12)
        selected = data['selected_index']
        if type(selected) is not int or not 0 <= selected < len(images):
            raise ValueError('selected_index 超出图片范围')
        number(data['select_at'], .3, duration - .35, 'select_at')
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
        for index, (x, y, w, h) in enumerate(boxes):
            for value in (x, y):
                number(value, 0, 1, '归一化位置')
            number(w, .000001, 1 - x + .00001, '框宽')
            number(h, .000001, 1 - y + .00001, '框高')
            pos = f'left:{100*x:.4f}%;top:{100*y:.4f}%;width:{100*w:.4f}%;height:{100*h:.4f}%'
            bx, by = (100 * x / (1 - w) if w < 1 else 0), (100 * y / (1 - h) if h < 1 else 0)
            image_style = f"background-image:url('{source}');background-size:{100/w:.3f}% {100/h:.3f}%;background-position:{bx:.3f}% {by:.3f}%"
            content = (f'<span>{label(captions[index])}</span>' if captions else '')
            chips.append(f'<i class="chip" style="{pos};{image_style}">{content}</i>')
            borders.append(f'<i class="bare-box" style="{pos}"></i>')
        if data.get('vector_shapes'):
            vectors = []
            for x, y, w, h in items('vector_shapes', 1, 1200):
                number(x, 0, 1, '矢量横坐标')
                number(y, 0, 1, '矢量纵坐标')
                number(w, 0, 1 - x + .00001, '矢量宽度')
                number(h, 0, 1 - y + .00001, '矢量高度')
                vectors.append(f'<rect x="{x*1000:.2f}" y="{y*562.5:.2f}" width="{max(.8,w*1000):.2f}" height="{max(.8,h*562.5):.2f}"/>')
            borders = ['<svg class="native-vectors" viewBox="0 0 1000 562.5">' + ''.join(vectors) + '</svg>']
        number(data['count'], 1, 1000000, 'count')
        body = (f'<div class="model" data-spatial-subject><div class="layer base" data-spatial-layer="base"><img src="{bottom}" alt=""><img class="face" src="{source}" alt=""><b class="plate-tag">01 · AMBIENT BASE</b></div>'
                f'<div class="layer skeleton" data-spatial-layer="skeleton">{"".join(borders)}<b class="plate-tag">02 · VECTOR GRAPHICS</b></div><div class="layer letters" data-spatial-layer="letters"><div class="text-boxes">{"".join(chips)}</div><b class="plate-tag">03 · {len(boxes)} NATIVE TEXTS</b></div>'
                '<i class="guide g1"></i><i class="guide g2"></i></div>')
        overlay = (f'<div class="depth-ruler" aria-hidden="true"><small>Z</small></div><aside class="meter"><strong>0</strong><b>{label(data.get("unit", "个图层"))}</b></aside>')
    elif recipe == 'roadmap_thread_camera':
        nodes = items('steps', 3, 4)
        if type(data['focus_step']) is not int or not 0 <= data['focus_step'] < len(nodes):
            raise ValueError('focus_step 超出节点数')
        previous = -1
        pts, cards = [], []
        for i, node in enumerate(nodes):
            at = number(node['at'], 0, duration - .45, '节点时间')
            if at <= previous:
                raise ValueError('节点时间必须递增')
            previous = at
            x, y = 260 + i * 1370 / (len(nodes) - 1), 460 + (i % 2) * 135
            pts.append((x, y))
            cards.append(f'<section class="node" style="left:{x-125}px;top:{y-88}px"><small>{label(node["no"])}</small><h2>{label(node["title"])}</h2><p>{label(node["sub"])}</p></section>')
        path = f'M -60 600 C 60 570,120 {pts[0][1]},260 {pts[0][1]}'
        for (x, y), (xx, yy) in zip(pts, pts[1:]):
            path += f' C {x+210} {y-90},{xx-200} {yy+80},{xx} {yy}'
        body = f'<div class="route-map"><svg viewBox="0 0 1920 1080"><path d="{path}" class="track"/><path d="{path}" class="thread" pathLength="1"/><circle class="pen-tip" r="8"/></svg>{"".join(cards)}</div>'
    elif recipe == 'perspective_video_fan':
        raw_items = items('items', 3, 6)
        focus_idx = data.get('focus_index', min(2, len(raw_items) - 1))
        if type(focus_idx) is not int or not 0 <= focus_idx < len(raw_items):
            raise ValueError('focus_index 超出视频墙范围')
        focus_at = number(data.get('focus_at', round(duration * 0.42, 3)), 0.25, duration - 0.35, 'focus_at')
        data['focus_index'] = focus_idx
        data['focus_at'] = focus_at
        aspect = data.get('card_aspect', 'widescreen')
        if aspect not in ('widescreen', 'portrait'):
            raise ValueError('card_aspect 仅支持 widescreen 或 portrait')
        data['card_aspect'] = aspect
        badge = label(data.get('badge', '✦ 修改后'))
        header_html = f'<div class="fan-badge" data-spatial-title data-title-kind="editorial_single"><i>✦</i><span>{badge.lstrip("✦ ")}</span></div>'
        cards_html = []
        for idx, item in enumerate(raw_items):
            src = item['source'] if isinstance(item, dict) else item
            lbl = item.get('label', '') if isinstance(item, dict) else ''
            lbl_html = f'<span class="fan-label">{label(lbl)}</span>' if lbl else ''
            cards_html.append(f'<div class="fan-card" data-spatial-subject><div class="fan-card-inner">{media_tag(src)}{lbl_html}</div></div>')
        stage_cls = 'fan-stage is-portrait' if aspect == 'portrait' else 'fan-stage'
        if data.get('punch_text'):
            punch_at = number(data.get('punch_at', round(duration * 0.72, 3)), 0.2, duration - 0.2, 'punch_at')
            data['punch_at'] = punch_at
            psub = f'<span>{label(data["punch_sub"])}</span>' if data.get('punch_sub') else ''
            overlay = f'<div class="fan-punch"><div class="fan-punch-box"><strong>{label(data["punch_text"])}</strong>{psub}</div></div>'
        body = f'<div class="{stage_cls}">{"".join(cards_html)}</div>'
    elif recipe == 'logo_bento_stage':
        modules = items('modules', 2, 4)
        brand = data.get('brand') or {}
        if isinstance(brand, str):
            brand = {'name': brand}
        b_name = label(brand.get('name', 'Workflow'))
        b_tag = label(brand.get('tag', 'AI Stack'))
        b_logo = f'<img src="{picture(brand["logo"])}" alt="">' if brand.get('logo') else ''
        header_html = (f'<header class="bento-brand" data-spatial-title data-title-kind="editorial_single">'
                       f'<span class="bento-brand-pill">{b_logo}{b_name}</span>'
                       f'<span class="bento-brand-title">{b_tag}</span></header>')
        fallback_svg = '<svg viewBox="0 0 64 64" aria-hidden="true"><g fill="none" stroke="#e47b54" stroke-width="4" stroke-linecap="round"><line x1="32" y1="6" x2="32" y2="58"/><line x1="6" y1="32" x2="58" y2="32"/><line x1="13" y1="13" x2="51" y2="51"/><line x1="51" y1="13" x2="13" y2="51"/></g></svg>'
        cols_html = []
        for idx, mod in enumerate(modules):
            if 'at' in mod:
                number(mod['at'], 0, duration - 0.2, '模块出场时间')
            mod_items = mod.get('items', [])[:3]
            rows_html = []
            for item_idx, entry in enumerate(mod_items):
                entry_obj = entry if isinstance(entry, dict) else {'name': str(entry)}
                if 'at' in entry_obj:
                    number(entry_obj['at'], 0, duration - 0.15, '子项出场时间')
                logo_html = f'<img src="{picture(entry_obj["logo"])}" alt="">' if entry_obj.get('logo') else fallback_svg
                spin_cls = ' bento-spin' if (idx == 0 and item_idx == 0 and len(mod_items) == 1) or entry_obj.get('spin') else ''
                badge_html = f'<span class="bento-item-badge">{label(entry_obj["badge"])}</span>' if entry_obj.get('badge') else ''
                rows_html.append(
                    f'<div class="bento-item"><div class="bento-logo-wrap{spin_cls}">{logo_html}</div>'
                    f'<div class="bento-item-name">{label(entry_obj.get("name", ""))}</div>{badge_html}</div>'
                )
            cols_html.append(
                f'<section class="bento-col" data-item-count="{len(mod_items)}" data-spatial-subject>'
                f'<div class="bento-box">{"".join(rows_html)}</div>'
                f'<div class="bento-cat">{label(mod["category"])}</div></section>'
            )
        body = f'<div class="bento-grid">{"".join(cols_html)}</div>'
    elif recipe == 'cutout_parallax_stage':
        hero_name, _ = media_asset(data['hero'], allow_video=False, trim_alpha=True)
        prop_names = [media_asset(src, allow_video=False, trim_alpha=True)[0] for src in items('props', 1, 3)]
        banner = data.get('banner') or {'title': spec.get('title', '专题'), 'sub': ''}
        header_html = (f'<header class="hanging-plaque" data-spatial-title data-title-kind="archive_plaque">'
                       f'<div class="plaque-title">{label(banner.get("title", ""))}</div>'
                       f'<p>{label(banner.get("sub", ""))}</p></header>')
        tiles = data.get('tiles') or []
        tiles_html = ''.join(f'<div class="poem-tile">{label(ch)}</div>' for ch in tiles[:12])
        counter = data.get('counter')
        if counter:
            sub_html = f'<div class="torn-sub">{label(counter["sub"])}</div>' if counter.get('sub') else ''
            overlay = (f'<aside class="torn-counter"><div class="torn-main">'
                       f'{label(counter.get("prefix", ""))} <span class="cnt">{int(counter.get("start", 0))}</span> {label(counter.get("unit", ""))}'
                       f'</div>{sub_html}</aside>')
        bg_extra = '<div class="parallax-sky"></div><div class="brocade-bar brocade-top"></div><div class="brocade-bar brocade-bottom"></div>'
        mountain_svg = ('<svg class="parallax-mountains" viewBox="0 0 2400 420" preserveAspectRatio="none" aria-hidden="true">'
                        '<path d="M0 420 L0 190 Q200 75 410 175 T820 155 T1240 110 T1660 165 T2080 115 T2400 170 L2400 420 Z" fill="#9bb1c4" opacity="0.72"/>'
                        '<path d="M0 420 L0 250 Q240 155 480 235 T960 215 T1420 175 T1900 225 T2400 195 L2400 420 Z" fill="#6f8ca3" opacity="0.86"/>'
                        '</svg>')
        props_html = ''.join(f'<div class="parallax-prop" data-spatial-subject><img class="paper-cutout-img" src="{p}" alt=""></div>' for p in prop_names)
        body = (f'{mountain_svg}<div class="parallax-earth"></div>'
                f'<canvas class="dust-canvas" width="1920" height="1080"></canvas>'
                f'<div class="poem-tiles">{tiles_html}</div>{props_html}'
                f'<div class="parallax-hero" data-spatial-subject><img class="paper-cutout-img" src="{hero_name}" alt=""></div>')
    elif recipe == 'documentary_ken_burns':
        painting_name = picture(data['image'])
        tag = data.get('archive_tag') or {}
        formula = data.get('formula')
        if isinstance(formula, dict):
            header_html = (f'<header class="doc-header" data-spatial-title data-title-kind="editorial_single">'
                           f'<span class="doc-header-label">{label(formula.get("label", ""))}</span>'
                           f'<i class="doc-header-sep"></i>'
                           f'<span class="doc-header-key">{label(formula.get("key", ""))}</span>'
                           f'<span class="doc-header-hi">{label(formula.get("highlight", ""))}</span></header>')
        elif isinstance(formula, str) and formula.strip():
            header_html = f'<header class="doc-header" data-spatial-title data-title-kind="editorial_single"><span class="doc-header-hi">{label(formula)}</span></header>'
        else:
            header_html = f'<header class="doc-header" data-spatial-title data-title-kind="editorial_single"><span class="doc-header-key">{label(tag.get("eyebrow", ""))}</span><span class="doc-header-hi">{label(tag.get("title", hud))}</span></header>'
        plaque_html = ''
        if tag:
            plaque_html = f'<div class="doc-plaque"><small>{label(tag.get("eyebrow", ""))}</small><b>{label(tag.get("title", ""))}</b></div>'
        anatomy_html = ''
        anatomy = data.get('anatomy_cards') or []
        if anatomy:
            if len(anatomy) != 3:
                raise ValueError('anatomy_cards 须为 3 张裁切解剖卡')
            if 'split_at' in data:
                number(data['split_at'], 0.3, duration - 0.5, 'split_at')
            cards_parts = []
            for card in anatomy:
                x, y, w, h = card['crop']
                for v in (x, y):
                    number(v, 0, 1, '裁切位置')
                number(w, 0.05, 1 - x + 1e-5, '裁切宽')
                number(h, 0.05, 1 - y + 1e-5, '裁切高')
                crop_style = (f"left:{-100*x/w:.2f}%;top:{-100*y/h:.2f}%;"
                              f"width:{100/w:.2f}%;height:{100/h:.2f}%")
                sub_span = f'<span>{label(card["sub"])}</span>' if card.get('sub') else ''
                cards_parts.append(
                    f'<article class="doc-anatomy-card" data-spatial-subject><img class="doc-crop-bg" src="{painting_name}" style="{crop_style}" alt="">'
                    f'<div class="doc-anatomy-cap"><strong>{label(card["label"])}</strong>{sub_span}</div></article>'
                )
            anatomy_html = f'<div class="doc-anatomy-row" style="opacity:0">{"".join(cards_parts)}</div>'
        body = (f'<div class="doc-frame" data-spatial-subject>{media_tag(data["image"], cls="doc-painting")}'
                f'<div class="doc-vignette"></div></div>{plaque_html}{anatomy_html}'
                f'<canvas class="dust-canvas" width="1920" height="1080"></canvas>')
    elif recipe == 'step_tree_focus':
        branches = items('branches', 2, 3)
        heading_txt = label(data.get('heading') or spec.get('title', '工作流'))
        header_html = f'<header class="editorial-heading" data-spatial-title data-title-kind="editorial_single">{heading_txt}</header>'
        total = len(branches)
        xs = [310, 1080] if total == 2 else [140, 720, 1300]
        box_w = 530 if total == 2 else 450
        branch_html, child_html, svg_paths = [], [], []
        for idx, b in enumerate(branches):
            number(b.get('at', 0.2 + idx * 1.2), 0, duration - 0.3, '分支时间')
            bx = xs[idx]
            by = 285
            branch_html.append(
                f'<section class="tree-branch" data-spatial-subject style="left:{bx}px;top:{by}px;width:{box_w}px">'
                f'<span class="tree-no">{label(b["no"])}</span><span>{label(b["title"])}</span></section>'
            )
            if idx > 0:
                x0 = xs[idx - 1] + box_w + 14
                x1 = bx - 16
                ym = by + 74
                svg_paths.append(
                    f'<path class="tree-link" pathLength="1" d="M {x0} {ym} Q {(x0+x1)/2} {ym-22} {x1} {ym} M {x1-16} {ym-12} L {x1} {ym} L {x1-16} {ym+12}"/>'
                )
            children = b.get('children') or []
            if children:
                cx_center = bx + box_w / 2
                spread = min(200, 560 / max(1, len(children)))
                for c_idx, ch in enumerate(children):
                    number(ch.get('at', 0.8 + c_idx * 0.3), 0, duration - 0.2, '子标签时间')
                    offset = (c_idx - (len(children) - 1) / 2) * spread
                    cx = cx_center + offset
                    cy = by + 272
                    svg_paths.append(
                        f'<path class="tree-stem" pathLength="1" d="M {cx_center} {by+148} L {cx_center} {by+206} L {cx} {by+206} L {cx} {cy-6}"/>'
                    )
                    child_html.append(
                        f'<div class="tree-child" data-spatial-subject style="left:{cx-84}px;top:{cy}px">{label(ch["label"])}</div>'
                    )
        body = f'<div class="tree-stage"><svg class="tree-svg" viewBox="0 0 1920 1080">{"".join(svg_paths)}</svg>{"".join(branch_html)}{"".join(child_html)}</div>'
    elif recipe == 'progressive_sim_cards':
        cards = items('cards', 2, 3)
        head_cfg = data.get('heading', '')
        if isinstance(head_cfg, dict):
            head_html = f'{label(head_cfg.get("text", ""))}<span>{label(head_cfg.get("highlight", ""))}</span>'
        else:
            head_html = label(head_cfg or spec.get('title', ''))
        header_html = f'<header class="sim-heading" data-spatial-title data-title-kind="editorial_single">{head_html}</header>'
        cards_html = []
        for idx, card in enumerate(cards):
            number(card.get('at', 0.15 + idx * 0.8), 0, duration - 0.3, '卡片时间')
            kind = card.get('kind', 'live_media')
            if kind == 'race_bars':
                slow_lbl = label(card.get('slow_label', '视频模型'))
                fast_lbl = label(card.get('fast_label', '代码'))
                panel = (
                    f'<div class="sim-panel">'
                    f'<div class="sim-bar-group"><div class="sim-bar-top"><span>{slow_lbl} ⟳</span><b class="sim-pct-slow">1%</b></div>'
                    f'<div class="sim-bar-track"><div class="sim-bar-fill is-slow"></div></div></div>'
                    f'<div class="sim-bar-group"><div class="sim-bar-top"><span>{fast_lbl} ✓</span><b class="sim-pct-fast">0%</b></div>'
                    f'<div class="sim-bar-track"><div class="sim-bar-fill is-fast"></div></div></div></div>'
                )
            else:
                panel = f'<div class="sim-panel is-media">{media_tag(card["source"])}</div>'
            cards_html.append(f'<article class="sim-card" data-spatial-subject>{panel}<div class="sim-label">{label(card["label"])}</div></article>')
        body = f'<div class="sim-row">{"".join(cards_html)}</div>'
    elif recipe == 'formula_pill_chain':
        reveal_at = number(data.get('reveal_at', round(duration * 0.35, 3)), 0.15, duration - 0.35, 'reveal_at')
        data['reveal_at'] = reveal_at
        src_pill = label(data['source_pill'])
        dst_pill = label(data['target_pill'])
        header_html = (f'<header class="chain-bar" data-spatial-title data-title-kind="editorial_single">'
                       f'<span class="pill-src">{src_pill}</span>'
                       f'<svg class="chain-arrow" viewBox="0 0 64 28"><path pathLength="1" d="M 4 14 L 56 14 M 44 4 L 58 14 L 44 24"/></svg>'
                       f'<span class="pill-dst">{dst_pill}</span></header>')
        badge_html = f'<span class="chain-badge">{label(data["badge"])}</span>' if data.get('badge') else ''
        body = f'<div class="chain-frame" data-spatial-subject>{badge_html}{media_tag(data["media"])}</div>'
    else:
        action = data['action']
        if action not in ACTIONS:
            raise ValueError('未知物理动作')
        if action == 'bad_slides_pileup':
            body = ''.join(f'<div class="old-card"><small>0{i+1}</small><h2>{label(t)}</h2><i></i><i></i><i></i></div>' for i, t in enumerate(items('labels', 3, 3))) + f'<div class="warning">×　{label(data["warning"])}</div>'
        elif action == 'dead_image_locked':
            body = f'<div class="locked-shot">{img(data["image"])}</div><div class="pointer">↖</div><i class="ripple"></i><div class="warning">⊠　{label(data["warning"])}</div>'
        elif action == 'slot_lock_fill':
            words = items('labels', 3, 4)
            paths, rows = [], []
            fields = data.get('fields', [])
            if fields and (not isinstance(fields, list) or len(fields) != len(words)):
                raise ValueError('每个数据槽需要一个对应的来源字段')
            for i, word in enumerate(words):
                y = 336 + i * 83
                curve = f'M 696 {y} C 790 {y-55} 1008 {y-5} 1215 {y}'
                paths.append(f'<path class="wire-rail" d="{curve}"/><path class="data-wire" pathLength="1" d="{curve}"/><circle class="comet" r="4"/>')
                field = f'<em>{label(fields[i])}</em>' if fields else ''
                rows.append(f'<div>{field}<b>{label(word)}</b></div>')
            body = ('<svg class="slot-traces" viewBox="0 0 1920 1080">' + ''.join(paths) + '</svg>'
                    + '<div class="plan-lines" data-spatial-subject><small>' + label(data.get('source_label', '输入'))
                    + '</small>' + ''.join(rows) + '</div><div class="slots" data-spatial-subject>'
                    + '<i></i>' * len(words) + '</div>' + ''.join(f'<b class="token">{label(w)}</b>' for w in words))
        else:
            body = ''.join(f'<div class="file-card">{img(src)}</div>' for src in items('images', 2, 6)) + f'<div class="command">{label(data["command"])}</div><div class="folder"><small>{label(data["folder"])}</small><h2>SKILL.md</h2></div>'

    accent = spec.get('accent', '#df6b50')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        raise ValueError('accent 需要六位颜色值')
    css = (HERE / 'stage.css').read_text().replace('STAGE', '#' + ident)
    motion = action if recipe == 'literal_action_stage' else recipe
    script = (HERE / 'camera.js').read_text() + (HERE / (motion + '.js')).read_text()
    keep_keys = (
        'selected_index', 'select_at', 'count', 'focus_step', 'action',
        'focus_index', 'focus_at', 'counter', 'focal_from',
        'focal_to', 'split_at', 'branches', 'focus_sequence', 'reveal_at',
        'card_aspect', 'punch_at',
    )
    settings_data = {key: data[key] for key in keep_keys if key in data}
    if 'modules' in data:
        clean_mods = []
        for mod in data['modules']:
            clean_items = [
                ({k: v for k, v in it.items() if k != 'logo'} if isinstance(it, dict) else it)
                for it in mod.get('items', [])
            ]
            clean_mods.append({**{k: v for k, v in mod.items() if k != 'items'}, 'items': clean_items})
        settings_data['modules'] = clean_mods
    if 'cards' in data:
        settings_data['cards'] = [{k: v for k, v in card.items() if k != 'source'} for card in data['cards']]
    if 'steps' in data:
        settings_data['steps'] = [{'at': step['at']} for step in data['steps']]
    settings = json.dumps(settings_data, ensure_ascii=False).replace('<', '\\u003c')
    markup = f'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><style>{css}</style><script src="vendor/gsap.min.js"></script></head><body>
<div id="{ident}" data-composition-id="{ident}" data-start="0" data-duration="{duration}" data-width="1920" data-height="1080" data-spatial-recipe="{recipe}" data-spatial-action="{label(data.get('action',''))}" data-stage-look="{stage_look}" style="--accent:{accent}">
<div class="stage-light"></div><div class="bloom"></div><svg class="ambient-wires" viewBox="0 0 1920 1080" aria-hidden="true"><path d="M-90 830C310 760 382 355 805 433S1365 776 2010 255"/><path class="energy-thread" pathLength="1" d="M-90 830C310 760 382 355 805 433S1365 776 2010 255"/></svg>{bg_extra}{header_html}<div class="stage"><div class="world">{body}</div></div><div class="streak"></div>{overlay}<div class="film-grain"></div></div>
<script>(()=>{{const root=document.getElementById('{ident}'), q=s=>root.querySelector(s), all=s=>[...root.querySelectorAll(s)];
const data={settings}, dur={duration}, tl=gsap.timeline({{paused:true}});{script}
tl.to({{}},{{duration:.001}},{duration}-.001);window.__timelines=window.__timelines||{{}};window.__timelines['{ident}']=tl;
}})();</script></body></html>'''
    for name, path in {**assets, 'vendor/gsap.min.js': gsap}.items():
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    if trimmed_cache.exists():
        shutil.rmtree(trimmed_cache, ignore_errors=True)
    (output / 'index.html').write_text(markup)
    return output / 'index.html'
