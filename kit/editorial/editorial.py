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

    def add_title_sequence(self, start, end, title, *, subtitle='', highlight='', brand='一策', paper=False):
        if not 1.8 <= round(end-start,5) <= 3.2:
            raise ValueError('片头扉页时长须为 1.8–3.2 秒')
        lines = title.splitlines() if isinstance(title,str) else list(title)
        if not 1 <= len(lines) <= 2 or not all(lines):
            raise ValueError('片头须有一至两行主题')
        color = INK if paper else IVORY
        accent = CRIMSON if paper else CORAL
        body = grid() + mono(100,208,brand,31,color)
        body += group('rise',''.join(word(96,423+133*i,text,min(120,1660//max(1,len(text))),
                                          accent if text==highlight else color) for i,text in enumerate(lines)))
        if subtitle:
            body += txt(100,683,subtitle,39,color)
        body += group('title-ruler',rule(100,755,1660,accent))
        plate = self.add_plate(start,end,' / '.join(lines),body,bg=PAPER if paper else INK,kind='chapter_break')
        self.scripts.append(f"tl.fromTo('#{plate} .title-ruler',{{scaleX:0}},"
                            f"{{scaleX:1,transformOrigin:'left center',duration:.8,immediateRender:false}},{start+.12:.5f});")
        self.sound_marks.extend((('whoosh',start),('stamp',start+.82)))
        row = self.shots[-1]
        row.update(stage_mode='title_sequence',layout='fullbleed',has_motion_overlay=True,beats=[0.,.12,.82])
        return row['id']

    def add_callout_rig(self, start, end, src, *, overlays, media_start=0., motion='glide'):
        if not 1 <= len(overlays) <= 2:
            raise ValueError('叠层镜头需要一至两个明确的贴图动作')
        sid = self.add_fullbleed_rig(start,end,src,media_start=media_start,motion=motion)
        shot = self.shots[-1]
        shot.update(stage_mode='callout_rig',has_motion_overlay=True,media_start=media_start)
        for overlay in overlays:
            at = float(overlay['at'])
            hold = float(overlay.get('duration',end-start-at))
            if not 0 <= at < end-start or hold <= 0 or start+at+hold > end+1e-6:
                raise ValueError('贴图须在镜头时间窗内')
            begin = start+at
            style = overlay['kind']
            label = str(overlay.get('label',''))
            if style == 'spotlight_box':
                x,y,w,h = map(float,overlay.get('box',[632,208,620,405]))
                if min(x,y,w,h) < 64 or x+w > 1856 or y+h > 890:
                    raise ValueError('高亮框超出可用视窗')
                shape = f'M{x} {y}h{w}v{h}h{-w}z'
                body = f'<path fill="#101b1bd9" fill-rule="evenodd" d="M0 0H1920V1080H0Z {shape}"/>'
                body += rect(x,y,w,h,'none',f'rx="14" stroke="{CORAL}" stroke-width="5" '
                                            'style="filter:drop-shadow(0 0 12px #ff745a)"')
                body += group('rise',rect(x,y-49,min(700,85+len(label)*28),44,INK,'rx="8"')+txt(x+16,y-18,label,28))
                audio = 'pop'
            elif style == 'stat_badge':
                value = float(overlay['value'])
                unit = str(overlay.get('unit',''))
                if not isfinite(value):
                    raise ValueError('数字角标需要有穷实测值')
                body = group('rise',rect(1194,105,585,245,'#203333e8','rx="23" stroke="#7aaba0"')
                             +txt(1235,157,label,32)+txt(1235,267,f'{value:g}{unit}',82,CORAL,attrs='class="stat-readout"')
                             +rule(1235,304,460))
                audio = 'pop'
            elif style == 'strikethrough_list':
                items = [str(item) for item in overlay.get('items',[])]
                if not 1 <= len(items) <= 4 or not all(items):
                    raise ValueError('划线排疑需要一至四项文字')
                body = rect(100,170,820,110+90*len(items),'#172322ea','rx="20"')+txt(136,238,label,39)
                for i,item in enumerate(items):
                    y = 324+90*i
                    body += txt(143,y,item,min(48,730//len(item)))
                    body += ln(138,y-16,min(883,143+len(item)*50),y-16,CORAL,7,f'class="strike-{i}"')
                audio = 'marker'
            elif style == 'verdict_stamp':
                if not label or len(label)>10:
                    raise ValueError('裁决印章须为短标签')
                body = stamp(1000,535,label)
                audio = 'stamp'
            else:
                raise ValueError(f'未知动态贴图类型：{style}')
            plate = self.add_plate(begin,begin+hold,style,body)
            self.shots.pop()  # The overlay belongs to the underlying video shot.
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
                        shot['beats'].append(at+delay)
            if style == 'verdict_stamp':
                self.add_stamp_slam(plate,begin)
            self.sound_marks.append((audio,begin))
            shot['beats'].append(at)
        shot['beats'] = sorted(set(shot['beats']))
        return sid

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
        if camera_moves is None:
            span = max(0.1, end - start)
            if motion == "push":
                camera_moves = [(0.0, 1.0, 960.0, 540.0), (span, 1.08, 960.0, 540.0)]
            elif motion == "pull":
                camera_moves = [(0.0, 1.08, 960.0, 540.0), (span, 1.0, 960.0, 540.0)]
            elif motion == "glide":
                camera_moves = [(0.0, 1.05, 860.0, 540.0), (span, 1.05, 1060.0, 540.0)]
            else:
                camera_moves = [(0.0, 1.0, 960.0, 540.0), (span, 1.02, 960.0, 540.0)]
        moves = sorted(camera_moves or [], key=lambda row: row[0])
        beats = [float(row[0]) for row in moves]
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
            f'data-duration="{end - start:.5f}" data-track-index="10">'
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
                    "sound_marks": [{"kind": kind, "at": round(float(at), 5)} for kind, at in self.sound_marks],
                    "music_drops": [[round(float(a), 5), round(float(b), 5)] for a, b in self.music_drops],
                }, ensure_ascii=False, indent=2) + "\n"
            )
