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
from math import cos, pi, sin
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
            f'<div id="{vid}" class="clip viewport{tone_cls}" data-start="{start:.5f}" '
            f'data-duration="{end - start:.5f}" data-track-index="{2 + (idx % 6)}" '
            f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
            f'<video class="vp-inner" src="{html.escape(src)}" muted playsinline preload="auto" '
            f'data-start="{start:.5f}" data-duration="{end - start:.5f}" data-media-start="{media_start:.3f}" '
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
            self.bg_layers.append(
                f'<div class="clip bg-fill" data-start="{start:.5f}" data-duration="{end - start:.5f}" '
                f'data-track-index="1" style="inset:0;background:{bg}"></div>'
            )
        full_body = body + (mast(*head) if head else "")
        self.plates.append(
            f'<div class="clip plate" id="{sid}" data-start="{start:.5f}" '
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
                "id": sid,
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

    def add_captions(self, cues: list[dict]) -> None:
        for cue in cues:
            st, en, text = cue["start"], cue["end"], cue["text"]
            self.captions.append(
                f'<div class="clip cap" data-start="{st:.5f}" data-duration="{en - st:.5f}" '
                f'data-track-index="15"><span>{html.escape(text)}</span></div>'
            )

    def write_project(self, project_dir: Path, audio_src: str = "assets/mix.wav",
                      timeline_out: Path | None = None) -> None:
        css = """*{box-sizing:border-box}
html,body{margin:0;width:100%;height:100%;background:#172322;color:#f6f0df;font-family:"PingFang SC","Hiragino Sans GB",system-ui,sans-serif}
#root{position:relative;width:100%;height:100%;overflow:hidden;background:radial-gradient(ellipse at 65% 37%,#243531 0%,#172322 53%,#111a19 100%)}
.clip{position:absolute}
.bg-fill{z-index:1}
.viewport{z-index:2;overflow:hidden;background:#121b19;box-shadow:inset 0 0 0 1px rgba(246,240,223,.14)}
.vp-inner{display:block;width:100%;height:100%;will-change:transform}
.tone-paper-tint{background:#ebe3d2}
.tone-paper-tint .vp-inner{filter:sepia(.08) brightness(.94) contrast(1.04)}
.tone-dark-soft .vp-inner{filter:brightness(.93) contrast(1.05)}
.tone-invert-log{background:#111918}
.tone-invert-log .vp-inner{filter:invert(.92) hue-rotate(155deg) saturate(.75) contrast(1.12)}
.plate{inset:0;z-index:6;pointer-events:none}
.cap{width:100%;left:0;bottom:44px;text-align:center;z-index:12}
.cap span{display:inline-block;background:rgba(17,26,25,.94);color:#fff7e5;padding:9px 27px 13px;font-weight:650;font-size:42px;line-height:1.28;border-bottom:3px solid #ff745a;box-shadow:0 8px 24px rgba(0,0,0,.34)}
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
                json.dumps({"end": self.duration, "shots": self.shots}, ensure_ascii=False, indent=2) + "\n"
            )
