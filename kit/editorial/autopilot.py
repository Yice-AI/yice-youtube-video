"""Skill v5 自治制片的可复用规划原语。

模块保持纯 Python，可在没有浏览器、Modal 或媒体文件的离线环境中做规划和门禁前置检查。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import os
import subprocess
from typing import Iterable, Any


@dataclass(frozen=True)
class Beat:
    """一个自然语义句群及其唯一素材需求。"""

    id: str
    start: float
    end: float
    text: str
    asset: str | None = None
    kind: str = "real_video"
    narrative_callback: bool = False

    @property
    def span(self) -> float:
        return round(self.end - self.start, 3)

    @property
    def required_duration(self) -> float:
        return round(self.span + 0.5, 2)


class UniqueAssetLedger:
    """全片素材账本，默认拒绝重复分配。"""

    def __init__(self) -> None:
        self._uses: dict[str, list[dict[str, Any]]] = {}

    def allocate(self, asset: str, beat_id: str, *, kind: str = "real_video",
                 narrative_callback: bool = False) -> None:
        uses = self._uses.setdefault(asset, [])
        if uses and not narrative_callback:
            raise ValueError(f"素材 {asset} 已在 {uses[0]['beat_id']} 使用，禁止重复")
        if len(uses) >= 2:
            raise ValueError(f"素材 {asset} 超过最大复用次数 2")
        uses.append({"beat_id": beat_id, "kind": kind, "narrative_callback": narrative_callback})

    def count(self, asset: str) -> int:
        return len(self._uses.get(asset, []))

    def counts(self) -> dict[str, int]:
        return {asset: len(uses) for asset, uses in self._uses.items()}

    def validate(self) -> list[str]:
        errors: list[str] = []
        repeated = [asset for asset, uses in self._uses.items() if len(uses) > 1]
        if len(repeated) > 2:
            errors.append(f"允许复用的素材文件超过 2 个：{len(repeated)}")
        for asset, uses in self._uses.items():
            if len(uses) > 1 and not all(item["narrative_callback"] for item in uses):
                errors.append(f"素材 {asset} 存在未声明的重复使用")
        return errors

    def as_dict(self) -> dict[str, list[dict[str, Any]]]:
        return self._uses


class SemanticBeatPlanner:
    """将句子按语义和时长聚合为 3.0–8.5 秒镜头。"""

    def __init__(self, min_span: float = 3.0, max_span: float = 8.5) -> None:
        if not 0 < min_span <= max_span:
            raise ValueError("句群时长范围无效")
        self.min_span = min_span
        self.max_span = max_span

    def plan(self, cues: Iterable[dict[str, Any]], *, prefix: str = "beat",
             asset_names: Iterable[str] | None = None, kind: str = "real_video") -> list[Beat]:
        rows = sorted((dict(cue) for cue in cues), key=lambda row: float(row["start"]))
        assets = iter(asset_names or [])
        result: list[Beat] = []
        group: list[dict[str, Any]] = []

        def emit(items: list[dict[str, Any]]) -> None:
            if not items:
                return
            start = float(items[0]["start"])
            end = float(items[-1]["end"])
            text = "".join(str(item.get("text", "")) for item in items).strip()
            asset = next(assets, None)
            result.append(Beat(f"{prefix}-{len(result)+1:02d}", round(start, 3), round(end, 3), text, asset, kind))

        for cue in rows:
            if not group:
                group = [cue]
                continue
            proposed = float(cue["end"]) - float(group[0]["start"])
            if proposed <= self.max_span:
                group.append(cue)
            else:
                emit(group)
                group = [cue]
        emit(group)

        # 合并过短的尾组，优先与前组形成完整语义镜头。
        i = 1
        while i < len(result):
            if result[i].span < self.min_span:
                prev = result[i - 1]
                current = result[i]
                merged = Beat(prev.id, prev.start, current.end, f"{prev.text}{current.text}", prev.asset, prev.kind)
                result[i - 1] = merged
                result.pop(i)
            else:
                i += 1
        for idx, beat in enumerate(result, 1):
            result[idx - 1] = Beat(f"{prefix}-{idx:02d}", beat.start, beat.end, beat.text, beat.asset, beat.kind)
        return result

    def balance_visual_rhythm(self, beats):
        """只为未指定素材的句组推荐表达方式，保留句序与句首。"""
        beats = list(beats)
        if not beats:
            return []
        midpoint = (beats[0].start + beats[-1].end) / 2
        schedule = {}
        for half in ([b for b in beats if b.start < midpoint],
                     [b for b in beats if b.start >= midpoint]):
            for index, beat in enumerate(half):
                if beat.asset:
                    schedule[beat.id] = beat.kind
                else:
                    schedule[beat.id] = ("web_cam", "studio_ui", "stock_broll", "explainer_graphic")[index % 4]
        return [dict(id=b.id, start=b.start, end=b.end, suggested_kind=schedule[b.id]) for b in beats]

    def asset_plan(self, beats: Iterable[Beat], ledger: UniqueAssetLedger | None = None) -> dict[str, Any]:
        ledger = ledger or UniqueAssetLedger()
        rows = []
        for beat in beats:
            if beat.asset:
                ledger.allocate(beat.asset, beat.id, kind=beat.kind, narrative_callback=beat.narrative_callback)
            rows.append({"id": beat.id, "start": beat.start, "end": beat.end, "text": beat.text,
                         "kind": beat.kind, "asset": beat.asset, "required_duration": beat.required_duration})
        return {"beats": rows, "assets": ledger.as_dict(), "errors": ledger.validate()}


class ExactDurationExplainerBuilder:
    """生成精确镜头时长的解说 spec，并在镜尾预留稳态 Hold。"""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)

    def build(self, beat: Beat, *, recipe: str, props: dict[str, Any] | None = None) -> Path:
        if beat.span <= 0:
            raise ValueError("镜头时长必须为正")
        duration = round(beat.span + 0.35, 2)
        cues = [{"at": round(beat.span * ratio, 3), "text": beat.text}
                for ratio in (0.08, 0.36, 0.68)]
        spec = {"id": beat.id, "recipe": recipe, "duration": duration,
                "shot_span": beat.span, "hold": 0.35, "cues": cues, "props": props or {}}
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{beat.id}.json"
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
        return path

    @staticmethod
    def validate(spec: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        shot_span = float(spec.get("shot_span", 0))
        duration = float(spec.get("duration", 0))
        if duration + 1e-6 < shot_span + 0.35:
            errors.append("解说 spec 未覆盖镜头时长与 0.35 秒 Hold")
        if any(float(cue.get("at", 0)) > shot_span * 0.72 + 1e-6 for cue in spec.get("cues", [])):
            errors.append("cue 超过镜头前 72% 的安全区")
        return errors


@dataclass
class WebCamBatchRecorder:
    project: Path
    recorder: Path
    chrome: str | None = None

    def command(self, item: dict[str, Any]) -> list[str]:
        required = float(item["required_duration"])
        seconds = min(20, max(6, math.ceil(required + 1.5)))
        cmd = ["node", str(self.recorder), "--project", str(self.project), "--id", str(item["id"]),
               "--url", str(item["url"]), "--seconds", str(seconds), "--fps", "30", "--theme", "dark", "--scale", "1.5"]
        if item.get("highlight"):
            cmd += ["--highlight", str(item["highlight"])]
        if item.get("actions"):
            cmd += ["--actions", json.dumps(item["actions"], ensure_ascii=False)]
        return cmd

    def record(self, item: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        default_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        default_module = Path("/opt/homebrew/lib/node_modules/openclaw/node_modules/playwright-core")
        if self.chrome:
            env["YICE_CHROME_EXECUTABLE"] = self.chrome
        elif default_chrome.is_file():
            env.setdefault("YICE_CHROME_EXECUTABLE", str(default_chrome))
        if default_module.is_dir():
            env.setdefault("YICE_PLAYWRIGHT_MODULE", str(default_module))
        return subprocess.run(self.command(item), check=True, text=True, capture_output=True, env=env)
