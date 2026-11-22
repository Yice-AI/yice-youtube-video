"""一策看片室 v4 的底乐瞬抽与动作音效元数据辅助器。

实际音频仍由项目自己的 ffmpeg/HyperFrames 混音脚本负责，这里提供一个小而稳定的
参数层，避免每个剧集重复拼接滤镜字符串。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class MusicDrop:
    start: float
    end: float


def normalise_music_drops(drops: list[tuple[float, float]] | None) -> list[MusicDrop]:
    result = []
    for start, end in drops or []:
        start, end = float(start), float(end)
        if start < 0 or end <= start:
            raise ValueError("Music Drop 的结束时间必须晚于开始时间，且开始时间不得为负数")
        result.append(MusicDrop(start, end))
    return sorted(result, key=lambda item: item.start)


def music_drop_volume_filter(drops: list[tuple[float, float]] | None) -> str:
    """生成 0.18 秒淡出、0.22 秒恢复的真实底乐音量自动化。"""
    expression = "1"
    target = 0.005
    for drop in reversed(normalise_music_drops(drops)):
        fade_out = min(0.18, max(0.01, drop.end - drop.start))
        fade_in = 0.22
        out_end = drop.start + fade_out
        in_end = drop.end + fade_in
        expression = (
            f"if(lt(t,{drop.start:.3f}),{expression},"
            f"if(lt(t,{out_end:.3f}),{target}+(1-{target})*0.5*(1+cos(PI*(t-{drop.start:.3f})/{fade_out:.3f})),"
            f"if(lt(t,{drop.end:.3f}),{target},"
            f"if(lt(t,{in_end:.3f}),{target}+(1-{target})*0.5*(1-cos(PI*(t-{drop.end:.3f})/{fade_in:.3f})),{expression}))))"
        )
    return f"volume='{expression}':eval=frame" if expression != "1" else "anull"


def render_bed_only(bed: str | Path, output: str | Path,
                    drops: list[tuple[float, float]] | None) -> Path:
    """按同一 Music Drop 窗口导出纯伴奏轨，供 audit-v4 做声学验收。"""
    bed, output = Path(bed), Path(output)
    if not bed.is_file():
        raise FileNotFoundError(f"底乐不存在：{bed}")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(bed), "-af", music_drop_volume_filter(drops),
        "-acodec", "pcm_s16le", str(output)
    ], check=True)
    return output


def action_mark(kind: str, at: float) -> dict[str, object]:
    allowed = {"whoosh", "marker", "slap", "tick", "stamp", "music_drop"}
    if kind not in allowed:
        raise ValueError(f"未知动作音效类型：{kind}")
    return {"kind": kind, "at": round(float(at), 5)}
