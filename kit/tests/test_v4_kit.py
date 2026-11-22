import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("audit_v4", ROOT / "scripts" / "audit-v3.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
sys.path.insert(0, str(ROOT))
from editorial import EditorialStage  # noqa: E402


class V4Kit(unittest.TestCase):
    def test_fullbleed_and_print_desk_write_auditable_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.png").write_bytes(b"image")
            stage = EditorialStage("v4", duration=8)
            stage.add_fullbleed_rig(
                0, 4, "sample.mp4", camera_moves=[(0.0, 1.2, 500, 400), (1.5, 1.35, 1400, 600)],
                chapter_pill="01 · 实录", checklist=[(0.6, "抓取首屏")],
                callouts=[{"at_sec": 1.2, "kind": "circle", "cx": 700, "cy": 400}],
            )
            stage.add_print_desk(4, 8, header="素材优先级", items=[(4.0, "sample.png", 300, 300, 500, 300, -2, "01")])
            stage.add_music_drops([(1.0, 1.3), (5.0, 5.2)])
            timeline = root / "timeline.json"
            stage.write_project(root / "project", timeline_out=timeline)
            data = json.loads(timeline.read_text())
            self.assertEqual(data["shots"][0]["layout"], "fullbleed")
            self.assertEqual(data["shots"][1]["layout"], "print_desk")
            self.assertGreaterEqual(len(data["shots"][0]["beats"]), 3)
            self.assertEqual(len(data["music_drops"]), 2)
            html = (root / "project" / "index.html").read_text()
            self.assertIn("chapter-pill", html)
            self.assertIn("print-item", html)

    def test_v4_gate_rejects_reuse_and_sparse_beats(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            errors = []
            data = {
                "shots": [{
                    "start": 0, "end": 10, "kind": "real_video", "layout": "split_box",
                    "files": ["same.mp4"] * 5, "beats": [0.0],
                }],
                "music_drops": [],
            }
            metrics = audit.timeline_metrics(data, 10, root, errors, v4=True)
            self.assertGreater(metrics["max_file_reuse"], 4)
            self.assertEqual(metrics["max_beat_gap"], 10)
            self.assertTrue(any("Music Drop" in error for error in errors))

    def test_pixel_gate_reads_rendered_pixels_independent_of_timeline_json(self):
        frame = bytes([80]) * (64 * 36)
        with patch.object(audit.subprocess, "run", return_value=type("Result", (), {"stdout": frame * 14})()):
            errors = []
            result = audit.pixel_dead_frame_gate(Path("renamed-final.mp4"), 10, errors)
        self.assertTrue(result["dead_runs"])
        self.assertTrue(any("真像素死镜" in error for error in errors))

    def test_black_frame_gate_rejects_non_intentional_dark_pixels(self):
        frame = bytes([5]) * (64 * 36)
        with patch.object(audit.subprocess, "run", return_value=type("Result", (), {"stdout": frame * 2})()):
            errors = []
            result = audit.black_frame_gate(Path("final.mp4"), {"shots": []}, 1, errors)
        self.assertEqual(len(result["unexpected_black_frames"]), 2)
        self.assertTrue(any("黑帧" in error for error in errors))

    def test_black_frame_gate_allows_explicit_intentional_black(self):
        frame = bytes([5]) * (64 * 36)
        timeline = {"shots": [{"start": 0, "end": 1, "intentional_black": True}]}
        with patch.object(audit.subprocess, "run", return_value=type("Result", (), {"stdout": frame})()):
            errors = []
            result = audit.black_frame_gate(Path("final.mp4"), timeline, 1, errors)
        self.assertEqual(result["unexpected_black_frames"], [])
        self.assertEqual(errors, [])

    def test_dhash_gate_rejects_file_renames_by_content(self):
        timeline = {"shots": [{"id": f"s{i}", "start": i, "end": i + 1} for i in range(5)]}
        with patch.object(audit, "_dhash", return_value=1234):
            errors = []
            result = audit.dhash_gate(Path("renamed-final.mp4"), timeline, errors)
        self.assertEqual(len(result["duplicate_groups"]), 1)
        self.assertTrue(any("dHash" in error for error in errors))

    def test_music_drop_gate_rejects_fake_timeline_without_acoustic_drop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bed-only.wav").write_bytes(b"wav")
            timeline = {"music_drops": [[0.0, 0.4], [1.0, 1.4], [2.0, 2.4], [3.0, 3.4]]}
            with patch.object(audit, "_rms_window", return_value=1.0):
                errors = []
                result = audit.music_drop_acoustic_gate(root / "final.mp4", timeline, errors)
            self.assertEqual(result["drop_count"], 4)
            self.assertTrue(any("Music Drop 衰减不足" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
