import json
import tempfile
import unittest
from pathlib import Path

from editorial.autopilot import (
    Beat,
    ExactDurationExplainerBuilder,
    SemanticBeatPlanner,
    UniqueAssetLedger,
    WebCamBatchRecorder,
)


class V5Autopilot(unittest.TestCase):
    def test_planner_joins_short_cues_and_emits_required_duration(self):
        cues = [
            {"start": 0.0, "end": 1.8, "text": "先找"},
            {"start": 1.8, "end": 3.4, "text": "再剪"},
            {"start": 3.4, "end": 7.2, "text": "最后才补"},
        ]
        beats = SemanticBeatPlanner().plan(cues, asset_names=["a.mp4"])
        self.assertEqual(len(beats), 1)
        self.assertGreaterEqual(beats[0].span, 3.0)
        self.assertEqual(beats[0].required_duration, 7.7)

    def test_ledger_rejects_unplanned_reuse(self):
        ledger = UniqueAssetLedger()
        ledger.allocate("clip.mp4", "b1")
        with self.assertRaises(ValueError):
            ledger.allocate("clip.mp4", "b2")
        ledger.allocate("callback.mp4", "b1", narrative_callback=True)
        ledger.allocate("callback.mp4", "b2", narrative_callback=True)
        self.assertEqual(ledger.count("callback.mp4"), 2)

    def test_exact_builder_writes_hold_and_validates(self):
        with tempfile.TemporaryDirectory() as temp:
            beat = Beat("b-01", 2.0, 8.0, "一句完整的镜头说明")
            path = ExactDurationExplainerBuilder(temp).build(beat, recipe="y2_vox")
            spec = json.loads(path.read_text())
            self.assertEqual(spec["duration"], 6.35)
            self.assertEqual(ExactDurationExplainerBuilder.validate(spec), [])

    def test_webcam_command_adds_safety_defaults(self):
        recorder = WebCamBatchRecorder(Path("/tmp/project"), Path("record-web-cam.mjs"))
        command = recorder.command({"id": "asset-1", "url": "https://example.com", "required_duration": 8.2})
        self.assertIn("--theme", command)
        self.assertIn("dark", command)
        self.assertIn("--fps", command)
        self.assertIn("30", command)


if __name__ == "__main__":
    unittest.main()
