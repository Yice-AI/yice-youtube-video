"""离线检查：不调用 TTS、Whisper、image2 网络或 Modal。"""
import contextlib
import importlib.util
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))


def module(name):
    spec = importlib.util.spec_from_file_location(name, KIT / "scripts" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


voice, props = module("voice"), module("props")


class VoiceTests(unittest.TestCase):
    def test_notes_plus_and_multisentence(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "script.md"
            script.write_text("## 00 开场\n| 0-1+ | **声音**〔核：不读〕。下一句！ | L7 | 图 |\n## 01b 准备\n| 1b-2 | `Codex`。 | L7 | 图 |\n")
            chapters = voice.parse_script(script)
            self.assertEqual(chapters[0]["scenes"][0], {"id": "0-1", "text": "声音。下一句！"})
            self.assertEqual(chapters[1]["text"], "Codex。")
            script.write_text(script.read_text() + "| 0-1 | 重复。 | L7 | 图 |\n")
            with self.assertRaisesRegex(ValueError, "重复幕号"):
                voice.parse_script(script)

    def test_chinese_alignment_and_normalization(self):
        asr = {"segments": [{"words": [{"word": "深图", "start": 0, "end": 1}, {"word": "Code", "start": 1, "end": 2}]}]}
        mapped, ratio, _ = voice.align_characters("生图 Code。", asr, 2, {"生图": "深图"})
        self.assertEqual(ratio, 1)
        self.assertEqual([m["charStart"] for m in mapped], [0, 1, 3, 4, 5, 6])
        self.assertEqual(mapped[-1]["s"], 1.75)

    def test_silence_only_at_scene_boundaries_preserves_pcm(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            raw = out / "raw.wav"
            pcm = struct.pack("<" + "h" * 200, *range(1, 201))
            with wave.open(str(raw), "wb") as f:
                f.setparams((1, 2, 100, 200, "NONE", "not compressed")); f.writeframes(pcm)
            chapter = {"id": "00", "text": "声音。 图。", "scenes": [{"id": "0-1", "text": "声音。"}, {"id": "0-2", "text": "图。"}]}
            asr = {"segments": [{"words": [{"word": "声音", "start": .1, "end": .7}, {"word": "图", "start": 1.1, "end": 1.7}]}]}
            rec, timing, scenes, _, analysis = voice.prepare_chapter(chapter, raw, out, asr, {}, .2, 7, [{"scene": "0-2", "phrase": "图"}])
            with wave.open(str(out / "chapter-00.wav"), "rb") as f:
                padded = f.readframes(f.getnframes())
            recovered = b"".join(padded[s["output_start_sample"] * 2:s["output_end_sample"] * 2] for s in analysis["segments"])
            self.assertEqual(recovered, pcm)
            self.assertEqual(padded[:40], b"\0" * 40)
            self.assertEqual(rec["duration"], 2.4)
            self.assertEqual(timing[1]["anchors"][0]["time"], 8.5)
            self.assertEqual(scenes[0]["end"], scenes[1]["start"])


class PropsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps({"items": [{"id": "test", "prompt": "test prop", "candidates": 3}]}))
        self.case = self.root / "case"
        self.requests = 0
        from PIL import Image
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); image.putpixel((3, 3), (255, 255, 255, 255))
        self.image = image
        fake = types.ModuleType("image2")
        fake.load_credentials = lambda: types.SimpleNamespace(sensitive_values=("secret",))
        fake.redact = lambda text, secrets: text.replace("secret", "[REDACTED]")

        def post(*a, **kw):
            self.requests += 1
            return types.SimpleNamespace(status_code=200, json=lambda: {"usage": {"input_tokens_details": {"text_tokens": 0, "image_tokens": 0}, "output_tokens_details": {"image_tokens": 2000}}, "data": [{}]})

        fake.requests = types.SimpleNamespace(post=post)

        def generate(prompt, width, height, output, credentials, background):
            self.assertEqual(background, "transparent")
            fake.requests.post("https://test.invalid")
            output.parent.mkdir(parents=True, exist_ok=True)
            self.image.save(output)

        fake.generate = generate
        self.fake = fake

    def tearDown(self):
        self.tmp.cleanup()

    def run_props(self, budget="0.2"):
        with patch.dict(sys.modules, {"image2": self.fake}), patch.object(sys, "argv", ["props", str(self.plan), "--case-dir", str(self.case), "--budget", budget, "--reserve-per-image", "0.1"]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            props.main()

    def test_cumulative_budget_and_resume_never_repeat_success(self):
        self.run_props()
        ledger = json.loads((self.case / "image2-ledger.json").read_text())
        self.assertEqual(self.requests, 2)
        self.assertEqual(props.total(ledger), .12)
        self.assertEqual(len(list((self.case / "checks").glob("*.jpg"))), 2)
        self.run_props()
        self.assertEqual(self.requests, 2)
        with self.assertRaises(SystemExit):
            self.run_props("0.3")

    def test_uncertain_charge_blocks_next_run_and_redacts_error(self):
        def fail(*a, **kw):
            raise TimeoutError("secret timeout")
        self.fake.generate = fail
        with self.assertRaises(SystemExit):
            self.run_props()
        ledger = json.loads((self.case / "image2-ledger.json").read_text())
        self.assertEqual(props.total(ledger), .1)
        self.assertEqual(ledger["calls"][0]["state"], "unknown_cost")
        self.assertNotIn("secret", ledger["calls"][0]["error"])
        with self.assertRaises(SystemExit):
            self.run_props()
        self.assertEqual(self.requests, 0)

    def test_failed_alpha_check_keeps_paid_usage(self):
        from PIL import Image
        self.image = Image.new("RGB", (8, 8), "white")
        with self.assertRaises(SystemExit):
            self.run_props()
        ledger = json.loads((self.case / "image2-ledger.json").read_text())
        self.assertEqual(props.total(ledger), .06)
        self.assertEqual(self.requests, 1)
        self.assertEqual(ledger["calls"][0]["state"], "error")


class CommandTests(unittest.TestCase):
    def test_new_episode_rejects_traversal_and_reuses_existing_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "YICE_WORKSPACE": tmp, "YICE_TOOLKIT": str(Path(tmp) / "toolkit")}
            run = lambda name: subprocess.run([str(KIT / "scripts/new-episode.sh"), name], env=env, capture_output=True, text=True)
            self.assertNotEqual(run("../escape").returncode, 0)
            self.assertEqual(run("test").returncode, 0)
            project = Path(tmp) / "toolkit/local/episodes/test"
            keep = project / "keep.txt"; keep.write_text("user work")
            self.assertEqual(run("test").returncode, 0)
            self.assertEqual(keep.read_text(), "user work")

    def test_render_propagates_exit_code_and_keeps_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "episode.json").write_text("{}")
            binary = root / "bin"; binary.mkdir()
            npm = binary / "npm"; npm.write_text("#!/bin/sh\necho render-failed\nexit 7\n"); npm.chmod(0o755)
            result = subprocess.run([str(KIT / "scripts/render.sh"), str(root)], env={**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 7)
            self.assertIn("render-failed", next((root / "renders").glob("*.log")).read_text())


if __name__ == "__main__":
    unittest.main()
