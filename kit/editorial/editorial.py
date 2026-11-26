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
import re
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
PALETTES = {
    'pine': dict(bg=INK, gradient='radial-gradient(ellipse at 65% 37%,#243531 0%,#172322 53%,#111a19 100%)',
                 panel='#172322fa', panel_soft='#172322eb', panel_dense='#172322f5', ink=IVORY,
                 sub=GREEN_MONO, line=LINE, edge='#7aaba0', accent=CORAL, accent2='#7aaba0', is_light=False),
    'obsidian': dict(bg='#0F1419', gradient='radial-gradient(ellipse at 28% 22%,#1E2B3A 0%,#121922 52%,#0B0F14 100%)',
                     panel='#18222Efa', ink='#F4F6FA', sub='#9DB0C4', line='#33465A', accent='#FF6B4A', accent2='#38BDF8', is_light=False),
    'aurora_indigo': dict(bg='#0B0D18', gradient='radial-gradient(ellipse at 72% 20%,#1F1D42 0%,#111324 54%,#090A12 100%)',
                          panel='#171A30fa', ink='#F5F7FF', sub='#A5B4FC', line='#313762', accent='#818CF8', accent2='#34D399', is_light=False),
    'paper_cool': dict(bg='#F6F3EC', gradient='radial-gradient(ellipse at 24% 18%,#FFFCF5 0%,#F6F3EC 58%,#EFE9DD 100%)',
                       panel='#FFFFFFf5', ink='#141821', sub='#49525F', line='#C8C1B3', accent='#D62828', accent2='#1D4E89', is_light=True),
    'paper_warm': dict(bg='#F3ECE0', gradient='radial-gradient(ellipse at 24% 18%,#FAF6EE 0%,#F1E9DA 58%,#E2D6C1 100%)',
                       panel='#FCF9F2f5', ink='#1F1A14', sub='#695D4F', line='#D0C3AE', accent='#C93B2B', accent2='#2B5B84', is_light=True),
}
EXPLAINER_THEMES = {'obsidian':'ink','aurora_indigo':'navy','paper_cool':'bauhaus','paper_warm':'paper'}
BREATHING_MOTIONS = {'focus_push','spring_glide'}
VERIFIED_OVERLAYS = {'spotlight_box','highlighter_sweep','hand_circle'}
STUDIO_VIEW = (136,142,1648,726)
STUDIO_GLOW = 'radial-gradient(ellipse at 54% 29%,#253653 0%,#162234 47%,#0B0F17 100%)'
FONT_FILES = ('SourceHanSerifCN-Heavy.otf','SourceHanSansCN-Regular.otf',
              'SourceHanSansCN-Bold.otf','SourceCodePro-Regular.otf')
FONT_CSS = """
@font-face{font-family:'Yice Song';src:url('assets/fonts/SourceHanSerifCN-Heavy.otf') format('opentype');font-weight:700 900;font-display:block;unicode-range:U+0000-024F,U+2000-206F,U+2E80-9FFF,U+F900-FAFF,U+FF00-FFEF}
@font-face{font-family:'Yice Sans';src:url('assets/fonts/SourceHanSansCN-Regular.otf') format('opentype');font-weight:100 500;font-display:block;unicode-range:U+0000-024F,U+2000-206F,U+2E80-9FFF,U+F900-FAFF,U+FF00-FFEF}
@font-face{font-family:'Yice Sans';src:url('assets/fonts/SourceHanSansCN-Bold.otf') format('opentype');font-weight:501 900;font-display:block;unicode-range:U+0000-024F,U+2000-206F,U+2E80-9FFF,U+F900-FAFF,U+FF00-FFEF}
@font-face{font-family:'Yice Mono';src:url('assets/fonts/SourceCodePro-Regular.otf') format('opentype');font-display:block;unicode-range:U+0000-024F,U+2000-206F,U+2190-21FF,U+2500-259F}
body,svg text[font-family="sans-serif"]{font-family:'Yice Sans',system-ui,sans-serif}
svg text[font-family="serif"]{font-family:'Yice Song','Yice Sans',serif}
svg text[font-family="monospace"],svg text[font-family^="Menlo"]{font-family:'Yice Mono','Yice Sans',monospace}
"""


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


def cutout_overlay_box(overlay):
    foreground = overlay.get('placement')=='foreground_hero' or overlay.get('depth')=='foreground'
    side = overlay.get('side','right')
    low,high = (340,460) if foreground else (140,260)
    size = float(overlay.get('size',380 if foreground else 210))
    if side not in {'left','right'} or not low<=size<=high:
        raise ValueError(f'抠像挂件仅支持左右侧，尺寸须为 {low}–{high}')
    margin = 42 if foreground else 80
    label = bool(str(overlay.get('label','')))
    x = margin if side=='left' else 1920-margin-size
    y = (856 if foreground else 850)-size-(42 if label else 0)
    return x,y,size,size+(42 if label else 0)


def studio_source_point(x, y):
    """Project 1920×1080 source coordinates through the studio viewport's cover fit."""
    _,_,w,h = STUDIO_VIEW
    scale = max(w/1920,h/1080)
    return x*scale+(w-1920*scale)/2, y*scale+(h-1080*scale)/2


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
        self.glow_layers: list[str] = []
        self.media_layers: list[str] = []
        self.plates: list[str] = []
        self.grain_layers: list[str] = []
        self.captions: list[str] = []
        self.scripts: list[str] = []
        self.shots: list[dict] = []
        self.sound_marks: list[tuple[str, float]] = []
        self.sound_gains: dict[int, float] = {}
        self.music_drops: list[tuple[float, float]] = []
        self.light_zones: list[tuple[float, float]] = []
        self.subcompositions: list[str] = []
        self.shot_layers: list[tuple[str, float, float, tuple]] = []
        self.transition_filters: list[str] = []
        self._camera_move_history: list[str] = []
        self.font_assets = False

    def apply_palette(self, theme, start, end, before, *, keep_studio_panels=False):
        if theme=='pine':
            return
        palette = PALETTES[theme]
        if keep_studio_panels:
            dark = PALETTES['obsidian'] if palette['is_light'] else palette
            for index in range(before[0],len(self.bg_layers)):
                self.bg_layers[index] = self.bg_layers[index].replace('background:#151c20',f'background:{dark["gradient"]}')
            return
        colors = {
            INK:palette['bg'], PAPER:palette['bg'], IVORY:palette['ink'], '#e7e9df':palette['ink'],
            GREEN_MONO:palette['sub'], MUTED:palette['sub'], '#a5b7b6':palette['sub'],
            LINE:palette['line'], '#263833':palette['line'], '#7aaba0':palette['accent2'],
            CORAL:palette['accent'], CRIMSON:palette['accent'], '#ff8369':palette['accent'],
            '#b6d5a8':palette['accent2'], '#f2a491':palette['accent'], '#b9d5bf':palette['sub'],
            '#172322eb':palette['panel'], '#172322fa':palette['panel'], '#172322f5':palette['panel'],
            '#151c20':palette['bg'], '#252e33':palette['panel'], '#1d2529':palette['line'],
        }
        pattern = re.compile(r'((?:fill|stroke)="|background:)(#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?)(?![0-9A-Fa-f])')
        studio_window = any('data-studio-backdrop' in row for row in self.bg_layers[before[0]:])
        for group_layers, first in zip((self.bg_layers,self.plates),before):
            for index in range(first,len(group_layers)):
                if 'data-studio-backdrop' in group_layers[index]:
                    if not palette['is_light']:
                        group_layers[index] = group_layers[index].replace(STUDIO_GLOW,palette['gradient'])
                    continue
                group_layers[index] = pattern.sub(lambda token:token[1]+colors.get(token[2],token[2]),group_layers[index])
                group_layers[index] = group_layers[index].replace(f'inset:0;background:{palette["bg"]}',
                                                                 f'inset:0;background:{palette["gradient"]}')
        if len(self.bg_layers)==before[0]:
            self.bg_layers.append(f'<div class="clip bg-fill" data-start="{start:.5f}" data-duration="{end-start:.5f}" '
                                  f'data-track-index="1" style="inset:0;background:{palette["gradient"]}"></div>')
        if palette['is_light'] and not studio_window:
            self.light_zones.append((start,end))

    def masked_heading(self, start, end, body, x, y, w, h):
        mask = f'heading-mask-{len(self.plates)}'
        self.scripts.append(f"tl.fromTo('#{mask}-text',{{y:{h},opacity:0}},"
                            f"{{y:0,opacity:1,duration:{min(.66,end-start):.5f},ease:'expo.out',"
                            f"immediateRender:false}},{start:.5f});")
        return (f'<defs><clipPath id="{mask}">{rect(x,y,w,h,"white")}</clipPath></defs>'
                f'<g clip-path="url(#{mask})"><g id="{mask}-text">{body}</g></g>')

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
        body += self.masked_heading(start,end,''.join(word(96,423+133*i,text,min(120,1660//max(1,len(text))),
                                    accent if text==highlight else color) for i,text in enumerate(lines)),90,285,1740,310)
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

    def visual_layers(self):
        return self.bg_layers, self.glow_layers, self.media_layers, self.plates, self.grain_layers

    def add_subcomposition(self, key, composition_id, entry, start, end):
        self.subcompositions.append(entry)
        self.media_layers.append(
            f'<div id="sub-{key}" class="clip hf-subcomp" style="inset:0;z-index:4" '
            f'data-composition-id="{composition_id}" data-composition-src="{html.escape(entry)}" '
            f'data-start="{start:.5f}" data-duration="{end-start:.5f}" '
            f'data-width="1920" data-height="1080" data-track-index="4"></div>'
        )

    def add_cinema_material(self, start, end, theme):
        span = end-start
        index = len(self.glow_layers)
        ident = f'ambient-{index}'
        timing = f'data-start="{start:.5f}" data-duration="{span:.5f}"'
        tint = '#4B4B9A' if theme=='aurora_indigo' else '#2D5373'
        self.glow_layers.append(f'<div id="{ident}" class="clip bg-fill ambient-glow-bloom" {timing} data-track-index="1" '
                                f'data-layout-allow-overflow style="inset:0;pointer-events:none;background:'
                                f'radial-gradient(ellipse at 42% 61%,{tint}75 0%,transparent 68%)"></div>')
        self.scripts.append(f"tl.fromTo('#{ident}',{{opacity:.65,x:-28,y:-8}},"
                            f"{{opacity:.98,x:23,y:12,duration:{span/2:.5f},repeat:1,yoyo:true,"
                            f"ease:'sine.inOut',immediateRender:false}},{start:.5f});")
        noise = ('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22192%22 height=%22192%22%3E'
                 '%3Cfilter id=%22n%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%22.89%22 '
                 'numOctaves=%223%22 seed=%2217%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E'
                 '%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23n)%22/%3E%3C/svg%3E')
        self.grain_layers.append(f'<div id="grain-{index}" class="clip film-grain" {timing} data-track-index="13" data-layout-ignore '
                                 f'style="inset:0;z-index:9;opacity:.055;pointer-events:none;background-image:url(\'{noise}\')"></div>')

    def register_visual_shot(self, key, start, end, before, transition=None):
        self.shot_layers.append((key,start,end,tuple((first,len(group)) for first,group in zip(before,self.visual_layers()))))
        if transition is None:
            return
        prior, _, cut, ranges = self.shot_layers[-2]
        duration = transition['duration']

        def extend(match):
            tag = match[0]
            began = re.search(r'\bdata-start="([\d.]+)"',tag)
            length = re.search(r'\bdata-duration="([\d.]+)"',tag)
            if began and length and abs(float(began[1])+float(length[1])-cut)<.00002:
                return tag[:length.start(1)] + f'{float(length[1])+duration:.5f}' + tag[length.end(1):]
            return tag

        for group,(first,last) in zip(self.visual_layers(),ranges):
            for index in range(first,last):
                group[index] = re.sub(r'<[^/!][^>]*\bdata-duration="[^"]+"[^>]*>',extend,group[index])
        out, incoming = f'#visual-{prior}', f'#visual-{key}'
        timing = f"duration:{duration:.5f},ease:'power2.inOut',immediateRender:false"
        kind = transition['kind']
        motion = {
            'whip_push': ('xPercent:-100', 'xPercent:100', 'xPercent:0'),
            'zoom_through': ('scale:1.85,opacity:0', 'scale:.82,opacity:0', 'scale:1,opacity:1'),
            'iris_reveal': ('scale:1.08', "clipPath:'circle(0% at 50% 50%)'",
                            "clipPath:'circle(135% at 50% 50%)'"),
            'blur_crossfade': ("filter:'blur(16px)'", "filter:'blur(16px)',opacity:0",
                               "filter:'blur(0px)',opacity:1"),
        }
        leave, enter, settle = motion[kind]
        self.scripts.extend((
            f"tl.to('{out}',{{{leave},{timing}}},{start:.5f});",
            f"tl.fromTo('{incoming}',{{{enter}}},{{{settle},{timing}}},{start:.5f});",
        ))
        if kind=='whip_push':
            filt = f'whip-{key}'
            self.transition_filters.append(f'<filter id="{filt}" x="-10%" width="120%"><feGaussianBlur stdDeviation="0 0"/></filter>')
            both = f'{out},{incoming}'
            self.scripts.extend((
                f"tl.set('{both}',{{filter:'url(#{filt})'}},{start:.5f});",
                f"tl.to('#{filt} feGaussianBlur',{{attr:{{stdDeviation:'24 0'}},duration:{duration/2:.5f},"
                f"repeat:1,yoyo:true,ease:'sine.inOut'}},{start:.5f});",
                f"tl.set('{both}',{{filter:'none'}},{start+duration:.5f});",
            ))
        self.add_sound_mark('whoosh',start,gain=.12)

    def render_visual_layers(self):
        groups = self.visual_layers()
        if not self.transition_filters and not any('transition_in' in row for row in self.shots):
            return '\n'.join(layer for group in groups for layer in group)
        filters = '<svg width="0" height="0" style="position:absolute"><defs>' + ''.join(self.transition_filters) + '</defs></svg>'
        scenes = []
        for key,_,_,ranges in self.shot_layers:
            body = '\n'.join(layer for layers,(first,last) in zip(groups,ranges) for layer in layers[first:last])
            scenes.append(f'<div id="visual-{key}" class="shot-visual" style="position:absolute;inset:0;isolation:isolate" '
                          f'data-layout-allow-overflow>{body}</div>')
        return filters+'\n'.join(scenes)

    def sound_events(self, offset=0.):
        for index,(kind,at) in enumerate(self.sound_marks):
            event = dict(kind=kind,at=round(offset+at,5))
            if index in self.sound_gains:
                event['gain'] = self.sound_gains[index]
            yield event

    def add_callout_rig(self, start, end, src, *, overlays, media_start=0., motion='glide', camera_moves=None,
                        framing='fullbleed', window_title='', refractive=False):
        focus = None
        if motion!='hold':
            target = next((overlay for overlay in overlays if overlay.get('kind') in VERIFIED_OVERLAYS),None)
            if target is not None:
                x,y,w,h = verified_spotlight_box(target)
                focus = (x+w/2,y+h/2)
        sid = self.add_fullbleed_rig(start,end,src,media_start=media_start,motion=motion,focus=focus,camera_moves=camera_moves,
                                    framing=framing,window_title=window_title,refractive=refractive)
        self.shots[-1].update(stage_mode='callout_rig',media_start=media_start)
        self.add_overlays(start,end,overlays,focus=focus,motion=motion,framing=framing)
        return sid

    def _camera_tween(self, selector, start, span, *, scale, shift=(0.,0.), focus=None, ease='none'):
        origin = f",transformOrigin:'{focus[0]:.1f}px {focus[1]:.1f}px'" if focus else ''
        self.scripts.append(f"tl.fromTo('{selector}',{{scale:{scale[0]:.3f},x:{shift[0]:.1f}{origin}}},"
                            f"{{scale:{scale[1]:.3f},x:{shift[1]:.1f},duration:{span:.5f},"
                            f"ease:'{ease}',immediateRender:false}},{start:.5f});")

    def _breathing_tween(self, selector, start, span, motion, focus=None):
        scale = (1.,1.27) if motion=='focus_push' or focus else (1.06,1.20)
        shift = (0.,0.) if motion=='focus_push' or focus else (-27.,72.)
        if span < 1.4:
            self._camera_tween(selector,start,span,scale=scale,shift=shift,focus=focus,ease='power2.out')
            return
        scale_mid = scale[0]+.7*(scale[1]-scale[0])
        shift_mid = shift[0]+.7*(shift[1]-shift[0])
        self._camera_tween(selector,start,.65,scale=(scale[0],scale_mid),shift=(shift[0],shift_mid),focus=focus,ease='power3.out')
        self._camera_tween(selector,start+.65,span-.65,scale=(scale_mid,scale[1]),shift=(shift_mid,shift[1]),focus=focus,ease='sine.out')

    def add_overlays(self, start, end, overlays, *, nle_plate=None, focus=None, motion=None, framing='fullbleed'):
        if not 1 <= len(overlays) <= 2:
            raise ValueError('叠层镜头需要一至两个明确的贴图动作')
        shot = self.shots[-1]
        shot['has_motion_overlay'] = True
        beats = shot.setdefault('beats', [])
        nle_windows = []
        studio = framing in {'studio_window','perspective_3d'}
        perspective = framing=='perspective_3d'
        def projected_box(overlay):
            x,y,w,h = verified_spotlight_box(overlay)
            if min(x,y)<64 or x+w>1856 or y+h>890:
                raise ValueError('高亮框超出可用视窗')
            if studio:
                end_x,end_y = studio_source_point(x+w,y+h)
                x,y = studio_source_point(x,y)
                w,h = end_x-x,end_y-y
                if x<0 or y<0 or end_x>STUDIO_VIEW[2] or end_y>STUDIO_VIEW[3]:
                    raise ValueError('核验框超出圆角视窗的可见画面')
            return x,y,w,h

        for index, overlay in enumerate(overlays):
            at = float(overlay['at'])
            hold = float(overlay.get('duration',end-start-at))
            if not 0 <= at < end-start or hold <= 0 or start+at+hold > end+1e-6:
                raise ValueError('贴图须在镜头时间窗内')
            begin = start+at
            style = overlay['kind']
            label = str(overlay.get('label',''))
            if style in {'highlighter_sweep','hand_circle'}:
                x,y,w,h = projected_box(overlay)
                if style=='highlighter_sweep':
                    shape = rect(x,y,w,h,'rgba(255,212,59,0.26)','rx="8"')
                    shape += rect(x,y+h-4,w,4,'#FFD43B','rx="2"')
                    body = group('verified-sweep',shape)
                else:
                    def oval(dx,dy):
                        left,top = x+dx,y+dy
                        return (f'M{left+w*.52} {top} C{left+w*1.18} {top-6} {left+w*1.15} {top+h} {left+w*.53} {top+h} '
                                f'S{left-w*.12} {top+h*.03} {left+w*.52} {top}')
                    body = ''.join(f'<path class="verified-circle" d="{oval(dx,dy)}" fill="none" '
                                   f'stroke="#FFD43B" stroke-width="{width}" opacity="{opacity}" stroke-linecap="round" '
                                   'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>'
                                   for dx,dy,width,opacity in ((0,0,5,.96),(4,3,2,.66)))
                audio = 'marker'
            elif style == 'spotlight_box':
                x,y,w,h = projected_box(overlay)
                shape = f'M{x} {y}h{w}v{h}h{-w}z'
                outer_w,outer_h = STUDIO_VIEW[2:] if studio else (1920,1080)
                body = f'<path fill="#101b1b42" fill-rule="evenodd" d="M0 0H{outer_w}V{outer_h}H0Z {shape}"/>'
                body += rect(x,y,w,h,'none',f'rx="10" stroke="{CORAL}" stroke-width="3"')
                label_y = y+h+8 if y<125 else y-49
                label_width = min(700,85+len(label)*28,outer_w-64-x)
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
                x,y = (136,34) if studio else (80,82)
                height = (68 if studio else 80) if sublabel else 56
                text_width = width-48-inset
                main_fit = f'textLength="{text_width}" lengthAdjust="spacingAndGlyphs"' if len(label)*28>text_width else ''
                body = rect(x,y,width,height,'#172322eb','rx="10"') + rect(x,y,5,height,CORAL)
                if logo:
                    body += svg_image(x+22,y+(height-32)//2,32,32,logo)
                body += txt(x+24+inset,y+36,label,28,attrs=main_fit)
                if sublabel:
                    sub_fit = f' textLength="{text_width}" lengthAdjust="spacingAndGlyphs"' if len(sublabel)*22>text_width else ''
                    body += txt(x+24+inset,y+65,sublabel,22,MUTED,attrs='data-layout-ignore'+sub_fit)
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
                foreground = overlay.get('placement')=='foreground_hero' or overlay.get('depth')=='foreground'
                if not isinstance(source,str) or Path(source).suffix.lower() not in IMAGE_EXTENSIONS:
                    raise ValueError('抠像挂件需要 PNG、WebP 或 SVG 素材')
                x,y,size,_ = cutout_overlay_box(overlay)
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
            if studio and style in VERIFIED_OVERLAYS:
                plate = f's{len(self.plates)}'
                x,y,w,h = STUDIO_VIEW
                mark = (f'<div id="{plate}" class="clip studio-window-mark" data-start="{begin:.5f}" '
                                   f'data-duration="{hold:.5f}" data-track-index="{11+index}" data-layout-allow-occlusion '
                                   f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
                                   f'<div class="studio-mark-plane" data-layout-allow-overflow>'
                                   f'<svg viewBox="0 0 {w} {h}">{body}</svg></div></div>')
                self.plates.append(self.perspective_plane(mark,start,7) if perspective else mark)
            else:
                plate = self.add_plate(begin,begin+hold,style,body,track=11+index)
                self.shots.pop()  # The overlay belongs to the underlying shot.
            if style in VERIFIED_OVERLAYS and focus:
                selector = f'#{plate} .studio-mark-plane' if studio else f'#{plate}'
                origin = studio_source_point(*focus) if studio else focus
                if motion in BREATHING_MOTIONS:
                    self._breathing_tween(selector,start,end-start,motion,focus=origin)
                else:
                    self._camera_tween(selector,start,end-start,scale=(1.,1.12),focus=origin)
            if style=='highlighter_sweep':
                self.scripts.append(f"tl.fromTo('#{plate} .verified-sweep',{{scaleX:0}},"
                                    f"{{scaleX:1,duration:{min(.32,hold):.5f},transformOrigin:'left center',"
                                    f"transformBox:'fill-box',ease:'power2.out',immediateRender:false}},{begin:.5f});")
            if style=='hand_circle':
                self.scripts.append(f"tl.fromTo('#{plate} .verified-circle',{{attr:{{'stroke-dashoffset':1}}}},"
                                    f"{{attr:{{'stroke-dashoffset':0}},duration:{min(.38,hold):.5f},"
                                    f"ease:'power2.inOut',immediateRender:false}},{begin:.5f});")
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
                ease = 'back.out(1.4)' if foreground else 'back.out(1.35)'
                self.scripts.append(f"tl.fromTo('#{plate} .cutout-hit',{{scale:1.18,rotation:4,y:-9,opacity:0}},"
                                    f"{{scale:1,rotation:-1.5,y:0,opacity:1,duration:{min(.34,hold):.5f},"
                                    f"transformOrigin:'center center',transformBox:'fill-box',ease:'{ease}',immediateRender:false}},{begin:.5f});")
                if foreground and hold>.34:
                    self.scripts.append(f"tl.to('#{plate} .cutout-hit',{{x:{8 if side=='left' else -8},y:-8,rotation:.8,"
                                        f"duration:{(hold-.34)/2:.5f},repeat:1,yoyo:true,ease:'sine.inOut'}},{begin+.34:.5f});")
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

    def add_triptych_cards(self, start, end, *, heading, cards, theme='pine'):
        if not 2 <= len(cards) <= 4:
            raise ValueError('多栏舞台需要两至四张卡片')
        span = end - start
        width = (1728 - 32 * (len(cards) - 1)) // len(cards)
        height = min(420, round(width * 9 / 16))
        top = 470 - height // 2
        size = min(74, 1670 // max(1,len(heading)))
        body = self.masked_heading(start,end,word(960,155,heading,size,anchor='middle'),90,67,1740,105)
        modern = theme!='pine'
        surfaces = []
        if modern:
            palette = PALETTES[theme]
            key = f'glass-{round(start*self.fps)}'
            surfaces.append(f'<defs><linearGradient id="{key}" x2="0" y2="1">'
                            f'<stop stop-color="{palette["line"]}"/><stop offset="1" stop-color="{palette["panel"]}"/>'
                            '</linearGradient></defs>')
        files, beats, reveals = [], [], []
        for index, card in enumerate(cards):
            at = float(card['reveal_at'])
            source = card['source']
            if not 0 <= at < span or card.get('loop'):
                raise ValueError('卡片须在镜头内点亮且媒体不得循环')
            x = 96 + index * (width + 32)
            begin = start + at
            media = (x+16,top+23,width-32,height-18) if modern else (x,top,width,height)
            suffix = Path(source).suffix.lower()
            if suffix in VIDEO_EXTENSIONS:
                viewport = self.add_video(begin,end,source,*media,media_start=card.get('media_start',0.),fit='contain')
            elif suffix in IMAGE_EXTENSIONS:
                viewport = self.add_image(begin,end,source,*media,zoom_to=1.,tone='natural',fit='contain')
            else:
                raise ValueError('卡片素材格式不支持')
            label = card['label']
            sublabel = card.get('sublabel','')
            logo = card.get('logo')
            inset = 46 if logo else 0
            label_size = min(38,(width-inset)//max(1,len(label)))
            sublabel_size = min(27,(width-inset)//max(1,len(sublabel)))
            if modern:
                panel_y,panel_h = top-56,height+198
                mx,my,mw,mh = media
                self.media_layers[-1] = self.media_layers[-1].replace('style="', 'style="border-radius:14px;',1)
                for offset,opacity in ((22,.08),(16,.11),(10,.16)):
                    surfaces.append(rect(x+offset/3,panel_y+offset,width,panel_h,'#080d18',f'rx="28" opacity="{opacity}"'))
                surfaces.extend((
                    rect(x,panel_y,width,panel_h,f'url(#{key})',f'rx="25" stroke="{palette["line"]}" stroke-width="1"'),
                    rect(mx,my,mw,mh,palette['bg'],'rx="14"'),
                    rect(x+24,panel_y+1,width-48,1,palette['sub'],'rx="1" opacity=".64"'),
                    rect(x+19,panel_y+19,66,37,palette['panel'],f'rx="17" stroke="{palette["line"]}"'),
                    mono(x+52,panel_y+45,f'{index+1:02}',24,palette['ink'],anchor='middle'),
                ))
                body += f'<g class="card-{index}" opacity="0">'
                body += rect(mx,my,mw,mh,'none',f'class="card-glint" rx="14" stroke="{palette["accent2"]}" '
                             'stroke-width="2" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"')
                if logo:
                    body += svg_image(x+20,top+height+29,29,29,logo)
                body += txt(x+20+inset,top+height+56,label,min(label_size,(width-40-inset)//max(1,len(label))),palette['ink'])
                body += txt(x+20+inset,top+height+95,sublabel,
                            min(sublabel_size,(width-40-inset)//max(1,len(sublabel))),palette['sub'])+'</g>'
            else:
                body += (rect(x,top,width,height,'none',f'rx="9" stroke="{LINE}" stroke-width="1.5" '
                              'stroke-dasharray="8 10"')+f'<g class="card-{index}" opacity="0">')
                if logo:
                    body += svg_image(x,top+height+29,32,32,logo)
                body += frame(x,top,width,height,CORAL) + txt(x+inset,top+height+58,label,label_size)
                body += txt(x+inset,top+height+95,sublabel,sublabel_size,MUTED) + '</g>'
            files.append(source)
            beats.append(at)
            reveals.append((index,viewport,begin))
            self.sound_marks.append(('pop',begin))
        plate = self.add_plate(start,end,heading,body,bg=INK,kind='triptych_cards',files=files)
        if modern:
            self.glow_layers.append(f'<div id="{key}-surfaces" class="clip bg-fill" style="inset:0" '
                                    f'data-start="{start:.5f}" data-duration="{span:.5f}" data-track-index="1" '
                                    f'data-layout-allow-occlusion><svg viewBox="0 0 1920 1080">'
                                    +''.join(surfaces)+'</svg></div>')
        self.shots[-1].update(stage_mode='triptych_cards',has_motion_overlay=True,beats=sorted(set(beats)),cards=cards)
        for index, viewport, begin in reveals:
            duration = min(.42,end-begin)
            self.scripts.append(f"tl.fromTo('#{plate} .card-{index}',{{opacity:0,y:10}},"
                                f"{{opacity:1,y:0,duration:{duration:.5f},ease:'back.out(1.22)',immediateRender:false}},{begin:.5f});")
            self.scripts.append(f"tl.fromTo('#{viewport} .vp-inner',{{opacity:0,scale:.96}},"
                                f"{{opacity:1,scale:1,duration:{duration:.5f},ease:'back.out(1.22)',immediateRender:false}},{begin:.5f});")
            if modern:
                self.scripts.append(f"tl.to('#{plate} .card-{index} .card-glint',{{attr:{{'stroke-dashoffset':0}},"
                                    f"duration:{duration:.5f},ease:'power2.out'}},{begin:.5f});")
        return self.shots[-1]['id']

    def perspective_plane(self, body, start, layer):
        key = round(start*self.fps)
        return (f'<div class="perspective-stage" data-layout-allow-overflow '
                f'style="position:absolute;inset:0;perspective:1400px;z-index:{layer};pointer-events:none">'
                f'<div class="perspective-window p3d-{key}" data-layout-allow-overflow '
                f'style="position:absolute;inset:0;transform-style:preserve-3d">{body}</div></div>')

    def studio_window_chrome(self, start, end, title, *, perspective=False, refractive=False):
        timing = f'data-start="{start:.5f}" data-duration="{end-start:.5f}"'
        self.bg_layers.append(f'<div class="clip bg-fill" {timing} data-track-index="1" data-studio-backdrop '
                              f'style="inset:0;background:{STUDIO_GLOW}"><div class="studio-grid"></div></div>')
        shadow = rect(144,122,1648,760,'rgba(0,0,0,.42)','rx="18"')
        shadow += rect(136,114,1648,760,'rgba(0,0,0,.22)','rx="18"')
        shadow_layer = (f'<div class="clip studio-window-shadow" {timing} data-track-index="1" '
                        f'data-layout-allow-occlusion><svg viewBox="0 0 1920 1080">{shadow}</svg></div>')
        self.bg_layers.append(self.perspective_plane(shadow_layer,start,1) if perspective else shadow_layer)
        body = '<path fill="#161D27" d="M136 142V124Q136 108 152 108H1768Q1784 108 1784 124V142Z"/>'
        body += ''.join(f'<circle cx="{x}" cy="125" r="5.5" fill="{color}"/>'
                        for x,color in zip((157,178,199),('#E06C65','#E5C07B','#7EC699')))
        if title:
            body += mono(960,132,title,min(21,1360//max(1,len(title))),'#D9E1EC',anchor='middle')
        body += rect(136,108,1648,760,'none','rx="18" stroke="rgba(255,255,255,.16)" stroke-width="1.5"')
        optics = ''
        if perspective or refractive:
            key = f'shimmer-{round(start*self.fps)}'
            optics = (f'<div class="refractive-edge" style="position:absolute;left:151px;top:108px;width:1618px;'
                      f'height:1px;overflow:hidden;background:linear-gradient(90deg,transparent,#c0deffb0,transparent)">'
                      f'<i id="{key}" class="shimmer-sweep" style="position:absolute;width:250px;height:1px;'
                      f'background:linear-gradient(115deg,transparent,#edfaff,transparent)"></i></div>')
            self.scripts.append(f"tl.fromTo('#{key}',{{x:-250}},{{x:1620,duration:{min(1.05,(end-start)*.72):.5f},"
                                f"ease:'sine.inOut',immediateRender:false}},{start:.5f});")
        chrome = (f'<div class="clip plate studio-window-chrome" {timing} data-track-index="8" '
                  f'data-layout-allow-occlusion><svg viewBox="0 0 1920 1080">{body}</svg>{optics}</div>')
        self.plates.append(self.perspective_plane(chrome,start,8) if perspective else chrome)
        if perspective:
            pose = f'.p3d-{round(start*self.fps)}'
            intro = min(.78,(end-start)*.5)
            self.scripts.extend((
                f"tl.fromTo('{pose}',{{rotationY:-8,rotationX:3.5,rotationZ:-.55,scale:.94}},"
                f"{{rotationY:-2,rotationX:1,rotationZ:0,scale:1.02,duration:{intro:.5f},"
                f"ease:'power3.out',immediateRender:false}},{start:.5f});",
                f"tl.to('{pose}',{{rotationY:-3.5,rotationX:1.7,rotationZ:.22,scale:1.008,"
                f"duration:{end-start-intro:.5f},ease:'sine.inOut'}},{start+intro:.5f});",
            ))

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
        framing: str = "fullbleed",
        window_title: str = "",
        refractive: bool = False,
    ) -> str:
        """铺满 1920×1080 的连续跟焦镜头，并登记可审计的视觉 beats。

        ``motion`` 支持 push、glide、pull、hold、punch。旧版四元组相机关键帧仍可用，
        也可在关键帧末尾加动作名覆盖整段默认动作。
        """
        if motion not in {"push", "glide", "pull", "hold", "punch"} | BREATHING_MOTIONS:
            raise ValueError("未知运镜方式")
        if framing not in {'fullbleed','studio_window','perspective_3d'} or not isinstance(window_title,str):
            raise ValueError('framing 须为 fullbleed、studio_window 或 perspective_3d，window_title 须为文本')
        if motion == "push" and len(self._camera_move_history) >= 2 and self._camera_move_history[-2:] == ["push", "push"]:
            raise ValueError("禁止连续三镜使用 push，请改用 glide、pull、hold 或 punch")
        self._camera_move_history.append(motion)
        idx = len(self.media_layers)
        vid = f"vp{idx}"
        tone_cls = f" tone-{tone}" if tone != "natural" else ""
        studio = framing in {'studio_window','perspective_3d'}
        perspective = framing=='perspective_3d'
        x,y,w,h = STUDIO_VIEW if studio else (0,0,1920,1080)
        cls = 'studio-window-media' if studio else 'fullbleed'
        if studio:
            self.studio_window_chrome(start,end,window_title,perspective=perspective,refractive=refractive)
            if focus:
                focus = studio_source_point(*focus)
        media = (
            f'<div id="{vid}" class="viewport {cls}{tone_cls}" '
            + (f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">' if studio else
               'style="left:0;top:0;width:1920px;height:1080px">')
            +
            f'<video id="film{idx}" class="clip vp-inner" src="{html.escape(src)}" muted playsinline preload="auto" '
            f'data-start="{start:.5f}" data-duration="{end - start:.5f}" data-media-start="{media_start:.3f}" '
            f'data-track-index="2" style="object-fit:cover;transform-origin:50% 50%"></video></div>'
        )
        self.media_layers.append(self.perspective_plane(media,start,2) if perspective else media)
        moves = sorted(camera_moves or [], key=lambda row: row[0])
        beats = [float(row[0]) for row in moves]
        if camera_moves is None:
            span = end-start
            selector = f'#{vid} .vp-inner'
            if motion in BREATHING_MOTIONS:
                self._breathing_tween(selector,start,span,motion,focus=focus)
            elif focus or motion=="push":
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
        sid = self._shot("悬浮视窗跟焦" if studio else "满屏连续跟焦","web_cam",start,end,[src],layout=framing,beats=beats)
        if studio:
            self.shots[-1].update(framing=framing,window_title=window_title)
        return sid

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
            switches = sorted({t for zone in self.light_zones for t in zone if st+.08 <= t <= en-.08})
            on_light = lambda t:any(a <= t < b for a,b in self.light_zones)
            bounds = [st]
            for point in switches:
                if point-bounds[-1]>=.08-1e-8 and on_light(point-1e-7)!=on_light(point+1e-7):
                    bounds.append(point)
            for start,end in zip(bounds,[*bounds[1:],en]):
                cls = "cap caption-on-light" if on_light((start+end)/2) else "cap"
                self.captions.append(
                    f'<div class="clip {cls}" data-start="{start:.5f}" data-duration="{end-start:.5f}" '
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
.studio-grid{position:absolute;inset:0;z-index:1;opacity:.45;background-image:linear-gradient(rgba(173,192,221,.065) 1px,transparent 1px),linear-gradient(90deg,rgba(173,192,221,.065) 1px,transparent 1px);background-size:64px 64px}
.studio-window-media,.studio-window-mark{border-radius:0 0 17px 17px;overflow:hidden}
.studio-window-mark{z-index:7;pointer-events:none}
.studio-mark-plane,.studio-mark-plane svg{position:absolute;inset:0;width:100%;height:100%}
.studio-window-shadow{position:absolute;inset:0;z-index:1;pointer-events:none}
.clip.viewport{background:#121b19}
.vp-inner{display:block;width:100%;height:100%;background:#121b19;will-change:transform}
.evidence-window{border-radius:14px}
.evidence-plane,.evidence-media,.evidence-mark{position:absolute;inset:0;width:100%;height:100%}
.evidence-media{object-fit:contain;background:#121b19}
.evidence-mark{pointer-events:none}
.tone-paper-tint.clip.viewport,.tone-paper-tint .vp-inner{background:#ebe3d2}
.tone-paper-tint .vp-inner{filter:sepia(.08) brightness(.94) contrast(1.04)}
.tone-dark-soft .vp-inner{filter:brightness(.93) contrast(1.05)}
.tone-invert-log .vp-inner{background:#f4f4f4;filter:invert(.92) hue-rotate(155deg) saturate(.75) contrast(1.12)}
.plate{inset:0;z-index:6;pointer-events:none}
.cap{width:100%;left:0;bottom:44px;text-align:center;z-index:12}
.cap span{display:inline-block;color:#fffaf0;padding:9px 27px 13px;font-weight:750;font-size:44px;line-height:1.28;-webkit-text-stroke:1.5px rgba(12,18,17,.88);text-shadow:0 2px 6px rgba(0,0,0,.85),0 6px 22px rgba(0,0,0,.65);border-bottom:3px solid #ff745a}
.cap[data-caption-style="editorial_box"] span{background:rgba(17,26,25,.94);box-shadow:0 8px 24px rgba(0,0,0,.34)}
.cap.caption-on-light span{color:#f8fafc;border:1.5px solid rgba(255,255,255,.18);border-bottom:3px solid #ff6b4a;-webkit-text-stroke:0;text-shadow:0 2px 8px rgba(0,0,0,.45);background:rgba(13,18,26,.90);border-radius:14px;padding:9px 26px 12px}
.caption-on-light{bottom:44px}
.chapter-pill{position:absolute;left:72px;top:54px;padding:10px 18px;border:1px solid rgba(255,250,240,.42);border-radius:22px;color:#fffaf0;background:rgba(20,29,27,.54);backdrop-filter:blur(10px);font:600 22px/1.1 system-ui,sans-serif}
.rig-checklist{position:absolute;right:72px;top:54px;display:grid;gap:10px;padding:14px 18px;border-radius:14px;background:rgba(20,29,27,.88);backdrop-filter:blur(10px);color:#fffaf0;font:600 20px/1.2 system-ui,sans-serif}
.check-row{display:flex;gap:10px;align-items:center;opacity:1;color:#fffaf0}.check-row.checked{color:#ffb29f}.check-row.checked i{color:#ff745a}.check-row i{font-style:normal;color:#fffaf0}
.rig-callout{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.writeon{fill:none;stroke:#ff5b52;stroke-width:8;stroke-linecap:round;stroke-dasharray:1200;stroke-dashoffset:1200;filter:drop-shadow(0 2px 2px rgba(0,0,0,.42))}.spotlight{position:absolute;border:2px solid rgba(255,250,240,.9);box-shadow:0 0 0 9999px rgba(0,0,0,.46),0 0 22px rgba(255,250,240,.28);border-radius:8px}
.print-desk{z-index:6}.print-item{transform-box:fill-box;transform-origin:center;filter:drop-shadow(0 18px 16px rgba(0,0,0,.34))}
svg{display:block}"""
        if self.font_assets:
            css += FONT_CSS
        html_doc = (
            f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=1920,height=1080">'
            f'<title>{html.escape(self.title)}</title>'
            f'<script src="vendor/gsap.min.js"></script><style>{css}</style></head>'
            f'<body><main id="root" data-composition-id="main" data-start="0" '
            f'data-width="1920" data-height="1080" data-duration="{self.duration:g}" data-fps="{self.fps}">'
            + self.render_visual_layers() + "\n".join(self.captions)
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
