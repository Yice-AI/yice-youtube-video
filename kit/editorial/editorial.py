"""一策看片室 · 开放式原生 HyperFrames 编辑部版式与视窗原语库（v3.1）。

源自 60 秒双盲实测获胜版（盲测-A）视觉语言：
- 统一视觉世界：深松墨绿微网格主舞台（#172322） + 暖米纸档案扉页（#e7ddc5），拒绝满屏图库空镜壁纸；
- 编辑部版式母版：顶部刊头（一策 | 栏目 + 右侧等宽档案标签）+ 衬线主标题 + 等宽元数据 + 20px 精密刻度尺 + 珊瑚红（#ff745a）唯一强调色；
- 干净实证视窗（printframe + viewport）：四角 L 型取景框包裹 16:9 录屏/第三方网页，内置平滑推近运镜（zoom）与柔和暗框调和，同屏最多 1–2 个主视窗（团队总览最多 3 卡），严禁 9–12 宫格蚂蚁字贴膏药；
- 原生 HyperFrames 开放输出：直接生成标准 HTML + SVG + GSAP 时间轴 + 珊瑚红底线内嵌字幕，不做封闭式 JSON 模板限制。
"""
from __future__ import annotations

import html
import json
from math import cos, isfinite, pi, sin
from pathlib import Path

IVORY = "#f6f0df"
INK = "#172322"
GREEN_MONO = "#b5c9a9"
CORAL = "#ff745a"
CRIMSON = "#a03528"
MUTED = "#a3b3a7"
LINE = "#465750"
PAPER = "#e7ddc5"
IMAGE_EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.svg'}
VIDEO_EXTENSIONS = {'.mp4','.m4v','.mov','.webm'}


def txt(x: float, y: float, value: object, size: int = 38, color: str = IVORY,
        anchor: str = "start", family: str = "sans-serif", weight: int = 600, attrs: str = "") -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
        f'font-family="{family}" font-weight="{weight}" {attrs}>{html.escape(str(value))}</text>'
    )


def mono(x: float, y: float, value: object, size: int = 28, color: str = GREEN_MONO,
         anchor: str = "start", weight: int = 550) -> str:
    return txt(x, y, value, size, color, anchor=anchor, family="monospace", weight=weight)


def word(x: float, y: float, value: object, size: int = 108, color: str = IVORY,
         anchor: str = "start", weight: int = 800) -> str:
    return txt(x, y, value, size, color, anchor=anchor, family="serif", weight=weight)


def rect(x: float, y: float, w: float, h: float, fill: str, attrs: str = "") -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {attrs}/>'


def ln(x1: float, y1: float, x2: float, y2: float, color: str = LINE, width: float = 2, attrs: str = "") -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" {attrs}/>'


def group(cls: str, body: str) -> str:
    return f'<g class="{cls}">{body}</g>'


def svg_image(x, y, w, h, source):
    return (f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="{html.escape(source)}" '
            'preserveAspectRatio="xMidYMid meet"/>')


def evidence_box(value):
    if not isinstance(value,(list,tuple)) or len(value)!=4:
        raise ValueError('证据高亮需要原图的 [x, y, w, h] 坐标')
    try:
        x,y,w,h = map(float,value)
    except (TypeError,ValueError):
        raise ValueError('证据高亮坐标必须为有限数值') from None
    if not all(isfinite(v) for v in (x,y,w,h)) or min(x,y)<0 or min(w,h)<=0 or x+w>1920.001 or y+h>1080.001:
        raise ValueError('证据高亮框超出 1920×1080 原图')
    return [x,y,w,h]


def verified_spotlight_box(overlay):
    note, box = overlay.get('target_note'), overlay.get('box')
    if overlay.get('target_verified') is not True or not isinstance(note,str) or not note.strip():
        raise ValueError('局部高亮框需要核对像素目标并填写 target_note')
    if not isinstance(box,(list,tuple)) or len(box)!=4:
        raise ValueError('局部高亮框需要显式 box 坐标')
    try:
        x,y,w,h = map(float,box)
    except (TypeError,ValueError):
        raise ValueError('局部高亮框坐标须为有限数值') from None
    if not all(isfinite(value) for value in (x,y,w,h)):
        raise ValueError('局部高亮框坐标须为有限数值')
    if w>680 or h>340:
        raise ValueError('局部高亮框尺寸过大，请改用 corner_tag 或复合舞台')
    if w<64 or h<48:
        raise ValueError('局部高亮框尺寸至少为 64×48')
    return x,y,w,h


def grid(color: str = LINE) -> str:
    v_lines = "".join(ln(x, 146, x, 901, color, 1, 'opacity=".30"') for x in range(92, 1835, 100))
    h_lines = "".join(ln(88, y, 1832, y, color, 1, 'opacity=".30"') for y in range(195, 890, 100))
    return v_lines + h_lines


def rule(x: float, y: float, w: int, color: str = MUTED) -> str:
    ticks = "".join(
        ln(x + i, y, x + i, y + (22 if i % 100 == 0 else 10), color, 2)
        for i in range(0, w + 1, 20)
    )
    return ln(x, y, x + w, y, color, 2) + ticks


def frame(x: float, y: float, w: float, h: float, color: str = IVORY, arm: int = 32, pad: int = 6) -> str:
    corners = [
        (x - pad, y - pad, arm, arm),
        (x + w + pad, y - pad, -arm, arm),
        (x - pad, y + h + pad, arm, -arm),
        (x + w + pad, y + h + pad, -arm, -arm),
    ]
    return "".join(
        f'<path d="M {cx} {cy} h {dx} M {cx} {cy} v {dy}" stroke="{color}" fill="none" stroke-width="3"/>'
        for cx, cy, dx, dy in corners
    )


def printframe(x: float, y: float, w: float, h: float, tag: str,
               color: str = IVORY, tag_color: str = GREEN_MONO, badge: str = "") -> str:
    right = mono(x + w, y - 22, badge, 21, MUTED, anchor="end") if badge else ""
    return frame(x, y, w, h, color) + mono(x, y - 22, tag, 24, tag_color) + right


def mast(label: str, tag: str, color: str = IVORY) -> str:
    return (
        txt(80, 77, "一策", 40, color, weight=850)
        + ln(188, 43, 188, 81, color, 2)
        + txt(215, 75, label, 28, color, weight=600)
        + txt(1840, 73, tag, 25, color, anchor="end", family="monospace", weight=500)
        + ln(80, 109, 1840, 109, color, 1, 'opacity=".55"')
    )


def caseleft(eyebrow: str, lines: list[str], desc: str, subdesc: str = "",
             size: int = 104, step: int = 120) -> str:
    extra = mono(91, 822, subdesc, 23, GREEN_MONO) if subdesc else ""
    return (
        mono(88, 258, eyebrow)
        + group("rise", "".join(word(84, 412 + i * step, line, size) for i, line in enumerate(lines)))
        + ln(90, 704, 536, 704, LINE, 2)
        + txt(91, 764, desc, 33, MUTED, weight=600)
        + extra
    )


def stamp(x: float, y: float, text: str, angle: float = -7, outline_only: bool = False) -> str:
    if outline_only:
        inner = (
            rect(0, 0, 544, 183, "none", f'stroke="{CRIMSON}" stroke-width="12"')
            + txt(272, 133, text, 102, CRIMSON, anchor="middle", weight=700)
        )
    else:
        inner = (
            rect(0, 0, 530, 128, CORAL)
            + rect(9, 9, 512, 110, "none", f'stroke="{INK}" stroke-width="3"')
            + txt(265, 94, text, 78, INK, anchor="middle", weight=900)
        )
    return f'<g transform="translate({x} {y}) rotate({angle})"><g class="stamp">{inner}</g></g>'


def perforations(color: str = "#46554b") -> str:
    return "".join(rect(x, y, 29, 13, color) for x in range(100, 1820, 56) for y in (180, 864))


def countdown_dial(cx: float, cy: float, step_index: int, value: int) -> str:
    arcs = "".join(
        f'<path d="M {cx + 60 * cos(j * pi / 12):.2f} {cy + 60 * sin(j * pi / 12):.2f} '
        f'l {7 * cos(j * pi / 12):.2f} {7 * sin(j * pi / 12):.2f}" '
        f'stroke="{CORAL if j < 24 - 8 * step_index else LINE}" stroke-width="4"/>'
        for j in range(24)
    )
    return arcs + txt(cx, cy + 25, value, 79, IVORY, anchor="middle", family="monospace", weight=800)


class EditorialStage:
    """开放式原生 HyperFrames 舞台构建器。"""

    def __init__(self, title: str, duration: float = 60.0, fps: int = 30) -> None:
        self.title = title
        self.duration = duration
        self.fps = fps
        self.bg_layers: list[str] = []
        self.media_layers: list[str] = []
        self.plates: list[str] = []
        self.captions: list[str] = []
        self.scripts: list[str] = []
        self.shots: list[dict] = []
        self.sound_marks: list[tuple[str, float]] = []
        self.sound_gains: dict[int, float] = {}
        self.music_drops: list[tuple[float, float]] = []
        self.light_zones: list[tuple[float, float]] = []
        self._camera_move_history: list[str] = []

    def _shot(self, name: str, kind: str, start: float, end: float, files: list[str],
              *, layout: str = "fullbleed", beats: list[float] | None = None) -> str:
        """登记镜头元数据，保持旧版 shots 字段兼容。"""
        sid = f"s{len(self.shots)}"
        self.shots.append({
            "id": sid,
            "name": name,
            "kind": kind,
            "layout": layout,
            "start": round(start, 5),
            "end": round(end, 5),
            "files": files,
            "beats": [round(float(value), 5) for value in (beats or [])],
        })
        return sid

    def add_cold_open_ab(self, start, end, left, right, *, hook, labels=('A', 'B'),
                         countdown=3, media_start=0.):
        if not isinstance(countdown, int) or countdown < 1 or end-start < countdown or len(labels) != 2:
            raise ValueError('双窗开场需要两个标签与完整的整数秒倒数区间')
        y, width, height = 265, 848, 477
        body = group('rise', word(960,183,hook,min(78,1530//max(1,len(hook))),anchor='middle'))
        for x, file, label in zip((80,992),(left,right),labels):
            self.add_video(start,end,file,x,y,width,height,fit='cover',media_start=media_start)
            body += printframe(x,y,width,height,label)
        self.add_plate(start,end,hook,body,kind='real_video',files=[left,right])
        intro = end-countdown
        for i in range(countdown):
            at = intro+i
            svg = countdown_dial(960,827,min(i,2),countdown-i)
            self.plates.append(f'<div class="clip plate" data-start="{at:.5f}" data-duration="1" '
                               f'data-track-index="11"><svg viewBox="0 0 1920 1080">{svg}</svg></div>')
            self.sound_marks.append(('tick',at))
        row = self.shots[-1]
        row.update(stage_mode='cold_open_ab',layout='ab_compare',has_motion_overlay=True,
                   montage_countdown=True,media_start=media_start,
                   beats=sorted({0.,*[intro-start+i for i in range(countdown)]}))
        return row['id']

    def add_title_sequence(self, start, end, title, *, subtitle='', highlight='', brand='一策', paper=False, logo=None):
        if not 1.8 <= round(end-start,5) <= 3.2:
            raise ValueError('片头扉页时长须为 1.8–3.2 秒')
        lines = title.splitlines() if isinstance(title,str) else list(title)
        if not 1 <= len(lines) <= 2 or not all(lines):
            raise ValueError('片头须有一至两行主题')
        color = INK if paper else IVORY
        accent = CRIMSON if paper else CORAL
        body = grid()
        if logo:
            body += svg_image(100,182,32,32,logo)
        body += mono(148 if logo else 100,208,brand,31,color)
        body += group('rise',''.join(word(96,423+133*i,text,min(120,1660//max(1,len(text))),
                                          accent if text==highlight else color) for i,text in enumerate(lines)))
        if subtitle:
            body += txt(100,683,subtitle,39,color)
        body += group('title-ruler',rule(100,755,1660,accent))
        plate = self.add_plate(start,end,' / '.join(lines),body,bg=PAPER if paper else INK,
                               kind='chapter_break',files=[logo] if logo else None)
        self.scripts.append(f"tl.fromTo('#{plate} .title-ruler',{{scaleX:0}},"
                            f"{{scaleX:1,transformOrigin:'left center',duration:.8,immediateRender:false}},{start+.12:.5f});")
        self.sound_marks.extend((('whoosh',start),('stamp',start+.82)))
        row = self.shots[-1]
        row.update(stage_mode='title_sequence',layout='fullbleed',has_motion_overlay=True,beats=[0.,.12,.82])
        if logo:
            row['logo'] = logo
        return row['id']

    def add_reference_breakdown(self, start, end, src, *, channel, claim,
                                cut_points=(), metrics=(), media_start=0.):
        if any(not isinstance(value,str) or not value.strip() for value in (channel,claim)):
            raise ValueError('原片拆解需要非空频道署名与拆解主张')
        try:
            points = tuple(float(point) for point in cut_points)
        except (TypeError,ValueError):
            raise ValueError('拆解切点须为镜头内的有效时间') from None
        if not all(0 < point < end-start for point in points) or any(a>=b for a,b in zip(points,points[1:])):
            raise ValueError('拆解切点须在镜头内严格递增')
        if (not isinstance(metrics,(list,tuple)) or len(metrics)>3
                or any(not isinstance(row,dict) or not isinstance(row.get('label'),str)
                       or not row['label'].strip() or row.get('value') is None for row in metrics)):
            raise ValueError('拆解指标最多三项，每项需要名称和实测值')

        def panel_text(y, value, size, color=IVORY):
            fit = 'textLength="500" lengthAdjust="spacingAndGlyphs"' if len(str(value))*size>500 else ''
            return txt(1304,y,value,size,color,attrs=fit)

        self.add_video(start,end,src,80,156,1152,648,fit='cover',media_start=media_start)
        credit = f'画面引用 · {channel}'
        fit = 'textLength="1160" lengthAdjust="spacingAndGlyphs"' if len(credit)*30>1160 else ''
        grid_id = f'ref-grid-{len(self.plates)}'
        backdrop = (f'<defs><clipPath id="{grid_id}"><path clip-rule="evenodd" '
                    'd="M0 0H1920V1080H0Z M80 156H1232V804H80Z"/></clipPath></defs>'
                    f'<g clip-path="url(#{grid_id})">{grid()}</g>')
        body = (backdrop + rect(80,84,5,34,CORAL) + txt(103,112,credit,30,attrs=fit)
                + txt(1840,112,'静音拆解 · 剪辑节奏实测',22,MUTED,anchor='end',attrs='data-layout-ignore')
                + frame(80,156,1152,648) + rule(80,826,1152)
                + rect(1268,156,572,648,'#1d2b2af5','rx="18" stroke="#7aaba0"')
                + panel_text(222,claim,34)
                + txt(1304,318,'镜头 #01',62,CORAL,attrs='class="ref-cut-counter"')
                + ln(1304,358,1804,358))
        for index, row in enumerate(metrics):
            baseline = 418+96*index
            body += panel_text(baseline,row['label'],28,MUTED)
            body += panel_text(baseline+45,row['value'],38)
        plate = self.add_plate(start,end,claim,body,bg='#141d1d',kind='real_video',files=[src])
        row = self.shots[-1]
        row.update(stage_mode='reference_breakdown',layout='split_inspector',has_motion_overlay=True,
                   channel=channel,claim=claim,cut_count=1+len(points),cut_points=list(points),
                   metrics=list(metrics),media_start=media_start,beats=[0.,*points])
        for index, point in enumerate((0.,*points),start=1):
            self.scripts.append(f"tl.set('#{plate} .ref-cut-counter',"
                                f"{{textContent:'镜头 #{index:02d}',immediateRender:false}},{start+point:.5f});")
            if point:
                self.add_sound_mark('tick',start+point,gain=.10)
        return row['id']

    def add_sound_mark(self, kind, at, *, gain=None):
        if gain is not None:
            self.sound_gains[len(self.sound_marks)] = gain
        self.sound_marks.append((kind,at))

    def sound_events(self, offset=0.):
        for index,(kind,at) in enumerate(self.sound_marks):
            event = dict(kind=kind,at=round(offset+at,5))
            if index in self.sound_gains:
                event['gain'] = self.sound_gains[index]
            yield event

    def add_callout_rig(self, start, end, src, *, overlays, media_start=0., motion='glide'):
        focus = None
        if motion!='hold':
            target = next((overlay for overlay in overlays if overlay.get('kind')=='spotlight_box'),None)
            if target is not None:
                x,y,w,h = verified_spotlight_box(target)
                focus = (x+w/2,y+h/2)
        sid = self.add_fullbleed_rig(start,end,src,media_start=media_start,motion=motion,focus=focus)
        self.shots[-1].update(stage_mode='callout_rig',media_start=media_start)
        self.add_overlays(start,end,overlays,focus=focus)
        return sid

    def _camera_tween(self, selector, start, span, *, scale, shift=(0.,0.), focus=None):
        origin = f",transformOrigin:'{focus[0]:.1f}px {focus[1]:.1f}px'" if focus else ''
        self.scripts.append(f"tl.fromTo('{selector}',{{scale:{scale[0]:.3f},x:{shift[0]:.1f}{origin}}},"
                            f"{{scale:{scale[1]:.3f},x:{shift[1]:.1f},duration:{span:.5f},"
                            f"ease:'none',immediateRender:false}},{start:.5f});")

    def add_overlays(self, start, end, overlays, *, nle_plate=None, focus=None):
        if not 1 <= len(overlays) <= 2:
            raise ValueError('叠层镜头需要一至两个明确的贴图动作')
        shot = self.shots[-1]
        shot['has_motion_overlay'] = True
        beats = shot.setdefault('beats', [])
        nle_windows = []
        for index, overlay in enumerate(overlays):
            at = float(overlay['at'])
            hold = float(overlay.get('duration',end-start-at))
            if not 0 <= at < end-start or hold <= 0 or start+at+hold > end+1e-6:
                raise ValueError('贴图须在镜头时间窗内')
            begin = start+at
            style = overlay['kind']
            label = str(overlay.get('label',''))
            if style == 'spotlight_box':
                x,y,w,h = verified_spotlight_box(overlay)
                if min(x,y) < 64 or x+w > 1856 or y+h > 890:
                    raise ValueError('高亮框超出可用视窗')
                shape = f'M{x} {y}h{w}v{h}h{-w}z'
                body = f'<path fill="#101b1b42" fill-rule="evenodd" d="M0 0H1920V1080H0Z {shape}"/>'
                body += rect(x,y,w,h,'none',f'rx="10" stroke="{CORAL}" stroke-width="3"')
                label_y = y+h+8 if y<125 else y-49
                label_width = min(700,85+len(label)*28,1856-x)
                fit = f'textLength="{label_width-24}" lengthAdjust="spacingAndGlyphs"' if len(label)*28>label_width-24 else ''
                body += ('<g class="rise" data-layout-allow-overlap>'+rect(x,label_y,label_width,44,INK,'rx="8"')
                         +txt(x+12,label_y+31,label,28,attrs=fit)+'</g>')
                audio = 'pop'
            elif style == 'corner_tag':
                sublabel = str(overlay.get('sublabel',''))
                if not label.strip():
                    raise ValueError('角落铭牌需要文字')
                logo = overlay.get('logo')
                inset = 44 if logo else 0
                width = min(760,max(190,57+inset+max(len(label)*28,len(sublabel)*22)))
                height = 80 if sublabel else 56
                text_width = width-48-inset
                main_fit = f'textLength="{text_width}" lengthAdjust="spacingAndGlyphs"' if len(label)*28>text_width else ''
                body = rect(80,82,width,height,'#172322eb','rx="10"') + rect(80,82,5,height,CORAL)
                if logo:
                    body += svg_image(102,82+(height-32)//2,32,32,logo)
                body += txt(104+inset,118,label,28,attrs=main_fit)
                if sublabel:
                    sub_fit = f' textLength="{text_width}" lengthAdjust="spacingAndGlyphs"' if len(sublabel)*22>text_width else ''
                    body += txt(104+inset,147,sublabel,22,MUTED,attrs='data-layout-ignore'+sub_fit)
                body = group('rise',body)
                audio = 'pop'
            elif style == 'stat_badge':
                value = float(overlay['value'])
                unit = str(overlay.get('unit',''))
                if not isfinite(value):
                    raise ValueError('数字角标需要有穷实测值')
                body = group('rise',rect(1194,105,585,245,'#172322fa','rx="23" stroke="#7aaba0"')
                             +txt(1235,157,label,32)+txt(1235,267,f'{value:g}{unit}',82,CORAL,attrs='class="stat-readout"')
                             +rule(1235,304,460))
                audio = 'pop'
            elif style == 'strikethrough_list':
                items = [str(item) for item in overlay.get('items',[])]
                if not 1 <= len(items) <= 4 or not all(items):
                    raise ValueError('划线排疑需要一至四项文字')
                x,y = float(overlay.get('x',80)),float(overlay.get('y',152))
                width = 728
                body = rect(x,y,width,92+70*len(items),'#172322f5','rx="16" stroke="#7aaba0"')
                body += txt(x+32,y+57,label,36,attrs='textLength="664" lengthAdjust="spacingAndGlyphs"' if len(label)*36>664 else '')
                for i,item in enumerate(items):
                    baseline = y+121+70*i
                    size = max(28,min(36,664//len(item)))
                    fit = 'textLength="664" lengthAdjust="spacingAndGlyphs"' if len(item)*size>664 else ''
                    body += txt(x+32,baseline,item,size,attrs=fit)
                    body += ln(x+28,baseline-13,x+min(701,32+len(item)*size),baseline-13,CORAL,6,f'class="strike-{i}"')
                if nle_plate:
                    nle_windows.append((begin,begin+hold))
                audio = 'marker'
            elif style == 'verdict_stamp':
                if not label or len(label)>10:
                    raise ValueError('裁决印章须为短标签')
                body = stamp(1000,535,label)
                audio = 'stamp'
            elif style in {'prop_badge','reaction_cutout'}:
                source, side = overlay.get('source'),overlay.get('side','right')
                size = float(overlay.get('size',210))
                if not isinstance(source,str) or Path(source).suffix.lower() not in IMAGE_EXTENSIONS:
                    raise ValueError('抠像挂件需要 PNG、WebP 或 SVG 素材')
                if side not in {'left','right'} or not 140<=size<=260:
                    raise ValueError('抠像挂件仅支持左右侧，尺寸须为 140–260')
                x = 80 if side=='left' else 1840-size
                y = 850-size-(42 if label else 0)
                image = svg_image(x,y,size,size,source)
                if label:
                    image += rect(x,y+size+5,size,37,'#172322eb','rx="8"')
                    fit = f'textLength="{size-14}" lengthAdjust="spacingAndGlyphs"' if len(label)*28>size-14 else ''
                    image += txt(x+size/2,y+size+31,label,28,anchor='middle',attrs=fit)
                body = group('cutout-hit',image)
                audio = 'pop'
            else:
                raise ValueError(f'未知动态贴图类型：{style}')
            if style != 'spotlight_box':
                body = '<g data-layout-allow-overlap>'+body+'</g>'
            plate = self.add_plate(begin,begin+hold,style,body,track=11+index)
            self.shots.pop()  # The overlay belongs to the underlying shot.
            if style=='spotlight_box' and focus:
                self._camera_tween(f'#{plate}',start,end-start,scale=(1.,1.12),focus=focus)
            if style == 'stat_badge':
                decimals = min(3,len(str(overlay['value']).partition('.')[2]))
                suffix = json.dumps(unit,ensure_ascii=False).replace('<','\\u003c')
                self.scripts.append(f"{{const n={{v:0}};const label=document.querySelector('#{plate} .stat-readout');"
                                    f"tl.to(n,{{v:{value},duration:{min(.65,hold):.4f},"
                                    f"onUpdate:()=>label.textContent=n.v.toFixed({decimals})+{suffix}}},{begin:.5f});}}")
            if style == 'strikethrough_list':
                for i,_ in enumerate(items):
                    delay = i*min(.31,hold/(len(items)+1))
                    self.scripts.append(f"tl.fromTo('#{plate} .strike-{i}',{{scaleX:0}},"
                                        f"{{scaleX:1,transformOrigin:'left',immediateRender:false,duration:{min(.27,hold-delay):.4f}}},{begin+delay:.5f});")
                    if i:
                        self.sound_marks.append((audio,begin+delay))
                        beats.append(at+delay)
            if style == 'verdict_stamp':
                self.add_stamp_slam(plate,begin)
            if style in {'prop_badge','reaction_cutout'}:
                self.scripts.append(f"tl.fromTo('#{plate} .cutout-hit',{{scale:1.18,rotation:4,y:-9,opacity:0}},"
                                    f"{{scale:1,rotation:-1.5,y:0,opacity:1,duration:{min(.34,hold):.5f},"
                                    f"transformOrigin:'center center',transformBox:'fill-box',ease:'back.out(1.35)',immediateRender:false}},{begin:.5f});")
            if style!='corner_tag' or not overlay.get('silent'):
                self.add_sound_mark(audio,begin,gain=.10 if style=='corner_tag' else None)
            beats.append(at)
        shot['beats'] = sorted(set(beats))
        if nle_windows:
            selector = f'#{nle_plate} .nle-bin'
            finish = None
            for begin, stop in sorted(nle_windows):
                if finish is None or begin > finish:
                    if finish is not None:
                        self.scripts.append(f"tl.set('{selector}',{{autoAlpha:1,display:'inline'}},{finish:.5f});")
                    self.scripts.append(f"tl.set('{selector}',{{autoAlpha:0,display:'none'}},{begin:.5f});")
                finish = max(finish,stop) if finish is not None else stop
            if finish < end-1e-6:
                self.scripts.append(f"tl.set('{selector}',{{autoAlpha:1,display:'inline'}},{finish:.5f});")

    def add_evidence_spotlight(self, start, end, source, *, heading, source_credit='', logo=None,
                               media_start=0., highlight_box=None, highlight_at=.45):
        span = end-start
        x,y,w,h = 200,148,1520,712
        box = evidence_box(highlight_box) if highlight_box is not None else None
        at = float(highlight_at)
        if box and (not isfinite(at) or at<0 or at>=span):
            raise ValueError('荧光标记时间须在证据镜头内')
        suffix = Path(source).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            raise ValueError('证据检视台的素材格式无效')
        moving = suffix in VIDEO_EXTENSIONS
        idx = len(self.media_layers)
        key = f'vp{idx}'
        timing = f'data-start="{start:.5f}" data-duration="{span:.5f}"'
        escaped = html.escape(source)
        item = f'class="clip evidence-media" src="{escaped}" {timing} data-track-index="{2+idx%6}"'
        if moving:
            media = f'<video {item} muted playsinline preload="auto" data-media-start="{media_start:.5f}"></video>'
        else:
            media = f'<img {item} alt=""/>'
        annotation = ''
        focus = (w/2,h/2)
        if box:
            left,top,width,height = box
            scale = h/1080
            bx,by = (w-1920*scale)/2+left*scale,top*scale
            bw,bh = width*scale,height*scale
            focus = (bx+bw/2,by+bh/2)
            annotation = (f'<svg class="clip evidence-mark" viewBox="0 0 {w} {h}" {timing} data-track-index="9" '
                          'data-layout-allow-occlusion>'
                          +rect(round(bx,3),round(by,3),round(bw,3),round(bh,3),'#f4ed55',
                                'class="evidence-stripe" rx="3" opacity="0"')+'</svg>')
        self.media_layers.append(
            f'<div class="viewport evidence-window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
            f'<div id="{key}" class="evidence-plane" data-layout-allow-overflow '
            f'style="transform-origin:{focus[0]:.3f}px {focus[1]:.3f}px">'
            +media+annotation+'</div></div>')
        body = svg_image(200,34,32,32,logo) if logo else ''
        if source_credit:
            body += mono(248 if logo else 200,58,source_credit,min(28,1440//max(1,len(source_credit))))
        body += txt(200,116,heading,min(49,1520//max(1,len(heading))))
        body += rect(x,y,w,h,'none','rx="14" stroke="#829590" stroke-width="2"')
        plate = self.add_plate(start,end,heading,body,bg=INK,animate=False,
                               kind='real_video' if moving else 'screenshot',files=[source,*([logo] if logo else [])])
        shadow = rect(209,163,w,h,'#00000036','rx="14"')+rect(205,154,w,h,'#00000046','rx="14"')
        self.bg_layers.append(f'<div class="clip bg-fill" style="inset:0;pointer-events:none" {timing} data-track-index="1" '
                              f'data-layout-allow-occlusion><svg viewBox="0 0 1920 1080">{shadow}</svg></div>')
        row = self.shots[-1]
        row.update(stage_mode='evidence_spotlight',layout='evidence_window',has_motion_overlay=True,
                   highlight_box=box,source_credit=source_credit,beats=[0.,at] if box else [0.])
        if logo:
            row['logo'] = logo
        intro = min(.42,span)
        self.scripts.append(f"tl.fromTo('#{plate} svg, #{key}',{{opacity:0,y:8}},"
                            f"{{opacity:1,y:0,duration:{intro:.5f},ease:'power3.out',immediateRender:false}},{start:.5f});")
        if box:
            zoom = min(.65,span-at)
            self.scripts.append(f"tl.fromTo('#{key}',{{scale:1}},"
                                f"{{scale:1.28,duration:{zoom:.5f},ease:'power3.inOut',immediateRender:false}},{start+at:.5f});")
            self.scripts.append(f"tl.fromTo('#{key} .evidence-stripe',{{scaleX:0,opacity:0}},"
                                f"{{scaleX:1,opacity:.38,duration:{zoom:.5f},transformOrigin:'left center',"
                                f"transformBox:'fill-box',ease:'power3.inOut',immediateRender:false}},{start+at:.5f});")
            if span-at > zoom:
                self.scripts.append(f"tl.to('#{key}',{{scale:1.32,duration:{span-at-zoom:.5f},ease:'sine.inOut'}},{start+at+zoom:.5f});")
            self.add_sound_mark('marker',start+at)
        else:
            self.scripts.append(f"tl.fromTo('#{key}',{{scale:1}},"
                                f"{{scale:1.07,duration:{span:.5f},ease:'sine.inOut',immediateRender:false}},{start:.5f});")
            self.add_sound_mark('pop',start)
        return row['id']

    def add_triptych_cards(self, start, end, *, heading, cards):
        if not 2 <= len(cards) <= 4:
            raise ValueError('多栏舞台需要两至四张卡片')
        span = end - start
        width = (1728 - 32 * (len(cards) - 1)) // len(cards)
        height = min(420, round(width * 9 / 16))
        top = 470 - height // 2
        size = min(74, 1670 // max(1,len(heading)))
        body = group('rise', word(960,155,heading,size,anchor='middle'))
        files, beats, reveals = [], [], []
        for index, card in enumerate(cards):
            at = float(card['reveal_at'])
            source = card['source']
            if not 0 <= at < span or card.get('loop'):
                raise ValueError('卡片须在镜头内点亮且媒体不得循环')
            x = 96 + index * (width + 32)
            begin = start + at
            suffix = Path(source).suffix.lower()
            if suffix in VIDEO_EXTENSIONS:
                viewport = self.add_video(begin,end,source,x,top,width,height,media_start=card.get('media_start',0.),fit='contain')
            elif suffix in IMAGE_EXTENSIONS:
                viewport = self.add_image(begin,end,source,x,top,width,height,zoom_to=1.,tone='natural',fit='contain')
            else:
                raise ValueError('卡片素材格式不支持')
            label = card['label']
            sublabel = card.get('sublabel','')
            logo = card.get('logo')
            inset = 46 if logo else 0
            label_size = min(38,(width-inset)//max(1,len(label)))
            sublabel_size = min(27,(width-inset)//max(1,len(sublabel)))
            body += f'<g class="card-{index}" opacity=".35">'
            if logo:
                body += svg_image(x,top+height+29,32,32,logo)
            body += frame(x,top,width,height,CORAL) + txt(x+inset,top+height+58,label,label_size)
            body += txt(x+inset,top+height+95,sublabel,sublabel_size,MUTED) + '</g>'
            files.append(source)
            beats.append(at)
            reveals.append((index,viewport,begin))
            self.sound_marks.append(('pop',begin))
        plate = self.add_plate(start,end,heading,body,bg=INK,kind='triptych_cards',files=files)
        self.shots[-1].update(stage_mode='triptych_cards',has_motion_overlay=True,beats=sorted(set(beats)),cards=cards)
        for index, viewport, begin in reveals:
            duration = min(.32,end-begin)
            self.scripts.append(f"tl.fromTo('#{plate} .card-{index}',{{opacity:.35,y:10}},"
                                f"{{opacity:1,y:0,duration:{duration:.5f},immediateRender:false}},{begin:.5f});")
            self.scripts.append(f"tl.fromTo('#{viewport} .vp-inner',{{opacity:0,scale:.96}},"
                                f"{{opacity:1,scale:1,duration:{duration:.5f},immediateRender:false}},{begin:.5f});")
        return self.shots[-1]['id']

    def add_fullbleed_rig(
        self,
        start: float,
        end: float,
        src: str,
        *,
        media_start: float = 0.0,
        tone: str = "natural",
        camera_moves: list[tuple[float, float, float, float]] | None = None,
        motion: str = "hold",
        focus: tuple[float, float] | None = None,
        chapter_pill: str | None = None,
        checklist: list[tuple[float, str]] | None = None,
        callouts: list[dict] | None = None,
        sfx: bool = False,
    ) -> str:
        """铺满 1920×1080 的连续跟焦镜头，并登记可审计的视觉 beats。

        ``motion`` 支持 push、glide、pull、hold、punch。旧版四元组相机关键帧仍可用，
        也可在关键帧末尾加动作名覆盖整段默认动作。
        """
        if motion not in {"push", "glide", "pull", "hold", "punch"}:
            raise ValueError("motion 必须是 push、glide、pull、hold 或 punch")
        if motion == "push" and len(self._camera_move_history) >= 2 and self._camera_move_history[-2:] == ["push", "push"]:
            raise ValueError("禁止连续三镜使用 push，请改用 glide、pull、hold 或 punch")
        self._camera_move_history.append(motion)
        idx = len(self.media_layers)
        vid = f"vp{idx}"
        tone_cls = f" tone-{tone}" if tone != "natural" else ""
        self.media_layers.append(
            f'<div id="{vid}" class="viewport fullbleed{tone_cls}" style="left:0;top:0;width:1920px;height:1080px">'
            f'<video id="film{idx}" class="clip vp-inner" src="{html.escape(src)}" muted playsinline preload="auto" '
            f'data-start="{start:.5f}" data-duration="{end - start:.5f}" data-media-start="{media_start:.3f}" '
            f'data-track-index="2" style="object-fit:cover;transform-origin:50% 50%"></video></div>'
        )
        moves = sorted(camera_moves or [], key=lambda row: row[0])
        beats = [float(row[0]) for row in moves]
        if camera_moves is None:
            span = end-start
            selector = f'#{vid} .vp-inner'
            if focus or motion=="push":
                self._camera_tween(selector,start,span,scale=(1.,1.12),focus=focus)
            elif motion=="pull":
                self._camera_tween(selector,start,span,scale=(1.12,1.))
            elif motion=="glide":
                self._camera_tween(selector,start,span,scale=(1.07,1.07),shift=(-42.,42.))
            elif motion=="punch":
                kick = min(.45,span*.35)
                self._camera_tween(selector,start,kick,scale=(1.,1.08))
                self._camera_tween(selector,start+kick,span-kick,scale=(1.08,1.12))
                beats.append(kick)
            beats.insert(0,0.)
            if sfx:
                self.add_sound_mark("whoosh",start)
        for index, row in enumerate(moves):
            at, scale, focus_x, focus_y = row[:4]
            row_motion = row[4] if len(row) > 4 else motion
            local_at = max(start, min(end, start + at if at < end - start else at))
            next_at = moves[index + 1][0] if index + 1 < len(moves) else end - start
            # Let the final camera move carry through the remainder of a long
            # semantic shot. A short capped tween would leave a real video
            # frozen after its opening beats and fail the pixel-motion gate.
            if index == len(moves) - 1:
                duration = max(0.18, next_at - at - 0.08)
            else:
                duration = max(0.18, min(0.55 if row_motion != "punch" else 0.32, next_at - at - 0.08))
            safe_scale = max(1.0, min(float(scale), 3.0))
            safe_x = max(-960.0, min(960.0, (960.0 - float(focus_x)) * (safe_scale - 1.0)))
            safe_y = max(-540.0, min(540.0, (540.0 - float(focus_y)) * (safe_scale - 1.0)))
            if row_motion == "hold":
                safe_scale, safe_x, safe_y = 1.0, 0.0, 0.0
            elif row_motion == "pull":
                safe_scale = min(safe_scale, 1.04)
            elif row_motion == "glide":
                safe_y = 0.0
            ease = "power3.out" if row_motion == "punch" else "power2.inOut"
            self.scripts.append(
                f"tl.to('#{vid} .vp-inner',{{scale:{safe_scale:.3f},x:{safe_x:.1f},y:{safe_y:.1f},duration:{duration:.3f},ease:'{ease}',immediateRender:false}},{local_at:.5f});"
            )
            if sfx:
                self.sound_marks.append(("whoosh", round(local_at, 5)))
        overlay_id = f"rig-{len(self.plates)}"
        overlay = []
        if chapter_pill:
            overlay.append(f'<div class="chapter-pill">{html.escape(chapter_pill)}</div>')
        if checklist:
            overlay.append('<div class="rig-checklist">' + "".join(
                f'<div class="check-row" data-at="{float(at):.3f}"><i>□</i><span>{html.escape(label)}</span></div>'
                for at, label in checklist
            ) + '</div>')
            for at, _ in checklist:
                local_at = start + at if at < end - start else at
                self.scripts.append(
                    f"tl.to('#{overlay_id} .check-row:nth-child({len([x for x in checklist if x[0] <= at])})',{{className:'check-row checked',duration:.16}},{local_at:.5f});"
                )
                beats.append(float(at))
                self.sound_marks.append(("tick", round(local_at, 5)))
        for callout in callouts or []:
            at = float(callout.get("at_sec", callout.get("at", 0)))
            kind = callout.get("kind", "circle")
            if kind == "arrow":
                overlay.append(
                    f'<svg class="rig-callout" viewBox="0 0 1920 1080"><path class="writeon" d="M {float(callout.get("x1", 300))} {float(callout.get("y1", 300))} L {float(callout.get("x2", 650))} {float(callout.get("y2", 300))}"/></svg>'
                )
            elif kind == "spotlight":
                overlay.append(
                    f'<div class="spotlight" style="left:{float(callout.get("x", 0))}px;top:{float(callout.get("y", 0))}px;width:{float(callout.get("w", 400))}px;height:{float(callout.get("h", 240))}px"></div>'
                )
            else:
                overlay.append(
                    f'<svg class="rig-callout" viewBox="0 0 1920 1080"><ellipse class="writeon" cx="{float(callout.get("cx", 960))}" cy="{float(callout.get("cy", 540))}" rx="{float(callout.get("rx", 180))}" ry="{float(callout.get("ry", 100))}"/></svg>'
                )
            local_at = start + at if at < end - start else at
            self.scripts.append(f"tl.fromTo('#{overlay_id} .writeon',{{strokeDashoffset:1200}},{{strokeDashoffset:0,duration:.35,ease:'power1.out',immediateRender:false}},{local_at:.5f});")
            beats.append(at)
            self.sound_marks.append(("marker", round(local_at, 5)))
        if overlay:
            self.plates.append(
                f'<div class="clip rig-overlay" id="{overlay_id}" data-start="{start:.5f}" data-duration="{end - start:.5f}" data-track-index="8" data-layout-ignore>'
                + "".join(overlay) + '</div>'
            )
        return self._shot("满屏连续跟焦", "web_cam", start, end, [src], layout="fullbleed", beats=beats)

    def add_print_desk(
        self,
        start: float,
        end: float,
        *,
        bg_style: str = "dark_desk",
        header: str | None = None,
        items: list[tuple[float, str, float, float, float, float, float, str]],
        props: list[dict] | None = None,
    ) -> str:
        """将截图或剪报按相纸卡片步进摆上桌面。"""
        bg = "#202824" if bg_style == "dark_desk" else PAPER
        if bg_style != "dark_desk":
            self.light_zones.append((float(start), float(end)))
        body = f'<rect width="1920" height="1080" fill="{bg}"/>'
        if header:
            body += txt(92, 96, header, 38, IVORY if bg_style == "dark_desk" else INK, weight=750)
        beats: list[float] = []
        for index, item in enumerate(items):
            at, src, x, y, w, h, angle, tag = item
            local_at = float(at)
            if local_at < start:
                local_at += start
            local_at = max(start, min(end, local_at))
            card = (
                f'<g transform="translate({x} {y}) rotate({angle} {w/2:.2f} {h/2:.2f})">'
                f'<g class="print-item" id="print-{len(self.plates)}-{index}" opacity="0">'
                f'<rect x="-14" y="-14" width="{w+28}" height="{h+28}" rx="3" fill="#fffaf0"/>'
                f'<rect x="-4" y="-4" width="{w+8}" height="{h+8}" fill="none" stroke="#d5c8aa" stroke-width="2"/>'
                f'<image href="{html.escape(str(src))}" x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"/>'
                f'<text x="0" y="{h+48}" fill="{INK}" font-size="24" font-family="monospace">{html.escape(str(tag))}</text></g></g>'
            )
            body += card
            self.scripts.append(
                f"tl.fromTo('#print-{len(self.plates)}-{index}',{{y:-24,scale:1.14,opacity:0}},{{y:0,scale:1,opacity:1,duration:.24,ease:'power3.out',immediateRender:false}},{local_at:.5f});"
            )
            beats.append(local_at - start)
            self.sound_marks.append(("slap", round(local_at, 5)))
        for prop in props or []:
            body += f'<image href="{html.escape(str(prop.get("src", "")))}" x="{float(prop.get("x", 0))}" y="{float(prop.get("y", 0))}" width="{float(prop.get("w", 160))}" height="{float(prop.get("h", 160))}" opacity="{float(prop.get("opacity", 1))}"/>'
        sid = f"s{len(self.plates)}"
        self.plates.append(
            f'<div class="clip plate print-desk" id="{sid}" data-start="{start:.5f}" data-duration="{end - start:.5f}" data-track-index="7" data-layout-allow-occlusion><svg viewBox="0 0 1920 1080" width="1920" height="1080">{body}</svg></div>'
        )
        self._shot("实物相纸步进桌面", "screenshot", start, end, [str(item[1]) for item in items], layout="print_desk", beats=beats)
        return sid

    def add_music_drops(self, music_drops: list[tuple[float, float]]) -> None:
        """登记底乐瞬抽窗口，供混音器和 v4 审计门禁共同使用。"""
        self.music_drops.extend((float(a), float(b)) for a, b in music_drops)
        self.sound_marks.extend(("music_drop", float(a)) for a, _ in music_drops)

    def add_video(
        self,
        start: float,
        end: float,
        src: str,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        media_start: float = 0.0,
        fit: str = "cover",
        tone: str = "natural",
        zoom_from: float = 1.0,
        zoom_to: float = 1.0,
        pan_x: float = 0.0,
        pan_y: float = 0.0,
        origin: str = "50% 50%",
    ) -> str:
        idx = len(self.media_layers)
        vid = f"vp{idx}"
        tone_cls = f" tone-{tone}" if tone != "natural" else ""
        self.media_layers.append(
            f'<div id="{vid}" class="viewport{tone_cls}" '
            f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
            f'<video id="film{idx}" class="clip vp-inner" src="{html.escape(src)}" muted playsinline preload="auto" '
            f'data-start="{start:.5f}" data-duration="{end - start:.5f}" data-media-start="{media_start:.3f}" '
            f'data-track-index="{2 + (idx % 6)}" '
            f'style="object-fit:{fit};transform-origin:{origin}"></video></div>'
        )
        if zoom_from != 1.0 or zoom_to != 1.0 or pan_x or pan_y:
            dur = max(0.15, end - start - 0.04)
            self.scripts.append(
                f"tl.fromTo('#{vid} .vp-inner',"
                f"{{scale:{zoom_from:.3f},x:0,y:0}},"
                f"{{scale:{zoom_to:.3f},x:{pan_x:.1f},y:{pan_y:.1f},duration:{dur:.4f},ease:'sine.inOut',immediateRender:false}},"
                f"{start + 0.01:.5f});"
            )
        return vid

    def add_image(
        self,
        start: float,
        end: float,
        src: str,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fit: str = "cover",
        position: str = "50% 50%",
        tone: str = "paper-tint",
        zoom_from: float = 1.0,
        zoom_to: float = 1.06,
        origin: str = "50% 35%",
    ) -> str:
        idx = len(self.media_layers)
        vid = f"vp{idx}"
        tone_cls = f" tone-{tone}" if tone != "natural" else ""
        self.media_layers.append(
            f'<div id="{vid}" class="clip viewport{tone_cls}" data-start="{start:.5f}" '
            f'data-duration="{end - start:.5f}" data-track-index="{2 + (idx % 6)}" '
            f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
            f'<img class="vp-inner" src="{html.escape(src)}" alt="" '
            f'style="object-fit:{fit};object-position:{position};transform-origin:{origin}"/></div>'
        )
        if zoom_from != 1.0 or zoom_to != 1.0:
            dur = max(0.15, end - start - 0.04)
            self.scripts.append(
                f"tl.fromTo('#{vid} .vp-inner',"
                f"{{scale:{zoom_from:.3f}}},"
                f"{{scale:{zoom_to:.3f},duration:{dur:.4f},ease:'sine.out',immediateRender:false}},"
                f"{start + 0.01:.5f});"
            )
        return vid

    def add_plate(
        self,
        start: float,
        end: float,
        name: str,
        body: str,
        *,
        head: tuple[str, str] | tuple[str, str, str] | None = None,
        bg: str | None = None,
        animate: bool = True,
        kind: str = "real_video",
        files: list[str] | None = None,
        track: int = 10,
    ) -> str:
        sid = f"s{len(self.plates)}"
        if bg:
            if bg == PAPER:
                self.light_zones.append((float(start), float(end)))
            self.bg_layers.append(
                f'<div class="clip bg-fill" data-start="{start:.5f}" data-duration="{end - start:.5f}" '
                f'data-track-index="1" style="inset:0;background:{bg}"></div>'
            )
        full_body = body + (mast(*head) if head and kind == "chapter_break" else "")
        self.plates.append(
            f'<div class="clip plate" id="{sid}" data-start="{start:.5f}" data-layout-allow-occlusion '
            f'data-duration="{end - start:.5f}" data-track-index="{track}">'
            f'<svg viewBox="0 0 1920 1080" width="1920" height="1080">{full_body}</svg></div>'
        )
        if animate:
            self.scripts.append(
                f"for(const el of document.querySelectorAll('#{sid} .rise')) "
                f"tl.fromTo(el,{{y:32,opacity:0}},{{y:0,opacity:1,duration:.36,ease:'power3.out',immediateRender:false}},{start + 0.015:.5f});"
            )
            self.scripts.append(
                f"for(const el of document.querySelectorAll('#{sid} .slide')) "
                f"tl.fromTo(el,{{x:-75,opacity:.1}},{{x:0,opacity:1,duration:.45,ease:'power3.out',immediateRender:false}},{start + 0.025:.5f});"
            )
            self.scripts.append(
                f"for(const el of document.querySelectorAll('#{sid} .scan')) "
                f"tl.fromTo(el,{{x:0}},{{x:480,duration:{max(0.1, end - start - 0.12):.5f},ease:'none',immediateRender:false}},{start + 0.03:.5f});"
            )
        self.shots.append(
            {
                "id": f"s{len(self.shots)}",
                "name": name,
                "kind": kind,
                "start": round(start, 5),
                "end": round(end, 5),
                "files": files or [],
            }
        )
        return sid

    def add_stamp_slam(self, sid: str, at_time: float, scale_from: float = 1.6) -> None:
        self.scripts.append(
            f"tl.fromTo('#{sid} .stamp',{{scale:{scale_from},opacity:0,transformOrigin:'50% 50%'}},"
            f"{{scale:1,opacity:1,duration:.20,ease:'back.out(1.9)',immediateRender:false}},{at_time:.5f});"
        )

    def add_captions(self, cues: list[dict], style: str = "clean_cinema") -> None:
        if style not in {"clean_cinema", "editorial_box"}:
            raise ValueError("字幕样式必须是 clean_cinema 或 editorial_box")
        for cue in cues:
            st, en, text = cue["start"], cue["end"], cue["text"]
            on_light = any(a <= (st + en) / 2 <= b for a, b in self.light_zones)
            cls = "cap caption-on-light" if on_light else "cap"
            self.captions.append(
                f'<div class="clip {cls}" data-start="{st:.5f}" data-duration="{en - st:.5f}" '
                f'data-track-index="15" data-caption-style="{style}" data-layout-allow-caption-zone><span>{html.escape(text)}</span></div>'
            )

    def write_project(self, project_dir: Path, audio_src: str = "assets/mix.wav",
                      timeline_out: Path | None = None) -> None:
        css = """*{box-sizing:border-box}
html,body{margin:0;width:100%;height:100%;background:#172322;color:#f6f0df;font-family:system-ui,sans-serif}
#root{position:relative;width:100%;height:100%;overflow:hidden;background:radial-gradient(ellipse at 65% 37%,#243531 0%,#172322 53%,#111a19 100%)}
.clip{position:absolute}
.bg-fill{z-index:1}
.viewport{position:absolute;z-index:2;overflow:hidden;pointer-events:none}
.fullbleed{z-index:2}
.clip.viewport{background:#121b19}
.vp-inner{display:block;width:100%;height:100%;background:#121b19;will-change:transform}
.evidence-window{border-radius:14px}
.evidence-plane,.evidence-media,.evidence-mark{position:absolute;inset:0;width:100%;height:100%}
.evidence-media{object-fit:contain;background:#121b19}
.evidence-mark{pointer-events:none;mix-blend-mode:multiply}
.tone-paper-tint.clip.viewport,.tone-paper-tint .vp-inner{background:#ebe3d2}
.tone-paper-tint .vp-inner{filter:sepia(.08) brightness(.94) contrast(1.04)}
.tone-dark-soft .vp-inner{filter:brightness(.93) contrast(1.05)}
.tone-invert-log .vp-inner{background:#f4f4f4;filter:invert(.92) hue-rotate(155deg) saturate(.75) contrast(1.12)}
.plate{inset:0;z-index:6;pointer-events:none}
.cap{width:100%;left:0;bottom:44px;text-align:center;z-index:12}
.cap span{display:inline-block;color:#fffaf0;padding:9px 27px 13px;font-weight:750;font-size:44px;line-height:1.28;-webkit-text-stroke:1.5px rgba(12,18,17,.88);text-shadow:0 2px 6px rgba(0,0,0,.85),0 6px 22px rgba(0,0,0,.65);border-bottom:3px solid #ff745a}
.cap[data-caption-style="editorial_box"] span{background:rgba(17,26,25,.94);box-shadow:0 8px 24px rgba(0,0,0,.34)}
.caption-on-light span{color:#172322;border:0;-webkit-text-stroke:0;text-shadow:none;background:rgba(255,250,240,.86);border-radius:8px;padding:4px 16px}
.caption-on-light{bottom:44px}
.chapter-pill{position:absolute;left:72px;top:54px;padding:10px 18px;border:1px solid rgba(255,250,240,.42);border-radius:22px;color:#fffaf0;background:rgba(20,29,27,.54);backdrop-filter:blur(10px);font:600 22px/1.1 system-ui,sans-serif}
.rig-checklist{position:absolute;right:72px;top:54px;display:grid;gap:10px;padding:14px 18px;border-radius:14px;background:rgba(20,29,27,.88);backdrop-filter:blur(10px);color:#fffaf0;font:600 20px/1.2 system-ui,sans-serif}
.check-row{display:flex;gap:10px;align-items:center;opacity:1;color:#fffaf0}.check-row.checked{color:#ffb29f}.check-row.checked i{color:#ff745a}.check-row i{font-style:normal;color:#fffaf0}
.rig-callout{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.writeon{fill:none;stroke:#ff5b52;stroke-width:8;stroke-linecap:round;stroke-dasharray:1200;stroke-dashoffset:1200;filter:drop-shadow(0 2px 2px rgba(0,0,0,.42))}.spotlight{position:absolute;border:2px solid rgba(255,250,240,.9);box-shadow:0 0 0 9999px rgba(0,0,0,.46),0 0 22px rgba(255,250,240,.28);border-radius:8px}
.print-desk{z-index:6}.print-item{transform-box:fill-box;transform-origin:center;filter:drop-shadow(0 18px 16px rgba(0,0,0,.34))}
svg{display:block}"""
        html_doc = (
            f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=1920,height=1080">'
            f'<title>{html.escape(self.title)}</title>'
            f'<script src="vendor/gsap.min.js"></script><style>{css}</style></head>'
            f'<body><main id="root" data-composition-id="main" data-start="0" '
            f'data-width="1920" data-height="1080" data-duration="{self.duration:g}" data-fps="{self.fps}">'
            + "\n".join(self.bg_layers + self.media_layers + self.plates + self.captions)
            + f'<audio id="mix" src="{html.escape(audio_src)}" data-start="0" '
              f'data-duration="{self.duration:g}" data-track-index="16" data-volume="1"></audio>'
            + "</main><script>\nwindow.__timelines = window.__timelines || {};\nconst tl = gsap.timeline({paused:true});\n"
            + "\n".join(self.scripts)
            + f"\ntl.to({{}}, {{duration:.01}}, {max(0.01, self.duration - 0.01):.3f});\n"
            + "window.__timelines.main = tl;\n</script></body></html>\n"
        )
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "index.html").write_text(html_doc)
        if timeline_out is not None:
            timeline_out.write_text(
                json.dumps({
                    "end": self.duration,
                    "shots": self.shots,
                    "sound_marks": list(self.sound_events()),
                    "music_drops": [[round(float(a), 5), round(float(b), 5)] for a, b in self.music_drops],
                }, ensure_ascii=False, indent=2) + "\n"
            )
