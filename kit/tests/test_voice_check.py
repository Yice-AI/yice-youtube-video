"""Offline prosody regression tests; every waveform is synthesized in a temporary directory."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


check, post, voice = module("voice-check"), module("voice-post"), module("voice")


class VoiceCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def synth(self, text="甲乙丙丁戊己。", durations=None, gaps=None, noise=False, falling=None):
        rate, cursor, parts, mapped = 16000, 0, [], []
        positions = [(i, c) for i, c in enumerate(text) if c.isalnum()]
        durations = durations or [.16] * len(positions)
        gaps = gaps or {}
        rng = np.random.default_rng(41)
        for number, (index, _) in enumerate(positions):
            count = round(durations[number] * rate)
            frequency = np.linspace(240, 130, count) if number == falling else np.full(count, 160.)
            tone = .18 * np.sin(2 * np.pi * np.cumsum(frequency) / rate)
            tone[:48] *= np.linspace(0, 1, 48)
            tone[-48:] *= np.linspace(1, 0, 48)
            parts.append(tone)
            mapped.append(dict(charStart=index, charEnd=index + 1, s=cursor / rate, e=(cursor + count) / rate))
            cursor += count
            gap = round(gaps.get(number, 0) * rate)
            parts.append(rng.normal(0, .004, gap) if noise else np.zeros(gap))
            cursor += gap
        audio = self.root / "synthetic.wav"
        sf.write(audio, np.concatenate(parts), rate, subtype="PCM_24")
        return audio, dict(text=text, mapped=mapped)

    def scan(self, audio, alignment):
        return check.check_chapter(audio, alignment, cache=self.root / "features.npz")

    def test_long_internal_character_is_flagged(self):
        audio, aligned = self.synth(durations=[.16, .16, .52, .16, .16, .16])
        flags = self.scan(audio, aligned)["alerts"]
        self.assertTrue(any(f["kind"] == "long_character" and f["index"] == 2 for f in flags))

    def test_unpunctuated_hesitation_needs_long_onset(self):
        audio, aligned = self.synth(durations=[.16, .16, .30, .16, .16, .16], gaps={1: .10})
        flags = self.scan(audio, aligned)["alerts"]
        self.assertTrue(any("low_energy_plus_long_onset" in f.get("reasons", []) for f in flags))

    def test_unpunctuated_long_pause_alone_is_flagged(self):
        audio, aligned = self.synth(gaps={1: .23})
        self.assertTrue(any("nonpunct_pause" in f.get("reasons", []) for f in self.scan(audio, aligned)["alerts"]))

    def test_legal_comma_pause_is_not_flagged(self):
        audio, aligned = self.synth(text="甲乙，丙丁戊己。", gaps={1: .24})
        self.assertEqual(self.scan(audio, aligned)["alerts"], [])

    def test_missing_contrast_pause_is_flagged(self):
        audio, aligned = self.synth(text="免费没有，得用账号。")
        self.assertTrue(any(f.get("pause_class") == "contrast" for f in self.scan(audio, aligned)["alerts"]))

    def test_lexical_falling_tone_alone_is_not_flagged(self):
        audio, aligned = self.synth(falling=2)
        result = self.scan(audio, aligned)
        self.assertLess(result["measurement"]["characters"][2]["f0_change_st"], -4)
        self.assertEqual(result["alerts"], [])

    def test_post_adds_missing_contrast_pause(self):
        audio, aligned = self.synth(text="免费没有，得用账号。")
        output = self.root / "processed.wav"
        updated = post.postprocess(audio, aligned, output)
        result = self.scan(output, updated)
        boundary = next(b for b in result["measurement"]["boundaries"] if b["kind"] == "contrast")
        self.assertGreaterEqual(boundary["pause_ms"], 300)
        self.assertLessEqual(boundary["pause_ms"], 450)
        self.assertEqual(result["alerts"], [])

    def test_post_preserves_pause_already_in_range(self):
        audio, aligned = self.synth(text="甲乙，丙丁戊己。", gaps={1: .24})
        output = self.root / "processed.wav"
        updated = post.postprocess(audio, aligned, output, speed=1)
        self.assertEqual(updated["semantic_pause_edits"], [])
        result = self.scan(output, updated)
        self.assertEqual(result["alerts"], [])
        self.assertLessEqual(abs(result["measurement"]["boundaries"][1]["pause_ms"] - 240), 20)

    def test_breath_noise_is_attenuated_and_shortened(self):
        audio, aligned = self.synth(gaps={1: .36}, noise=True)
        samples, rate = sf.read(audio)
        acoustic = check.acoustic(audio, self.root / "breath.npz")
        result, _, events, edits = post.attenuate_breaths(samples, rate, aligned, acoustic)
        self.assertTrue(events)
        self.assertTrue(edits)
        self.assertAlmostEqual((len(samples) - len(result)) / rate, .36 - .15, delta=.03)
        a, b = round(.34 * rate), round(.37 * rate)
        gain = 20 * np.log10(np.sqrt(np.mean(result[a:b] ** 2) / np.mean(samples[a:b] ** 2)))
        self.assertAlmostEqual(gain, -12, delta=.1)

    def test_speed_preserves_pitch(self):
        audio, aligned = self.synth(durations=[.25] * 6)
        output = self.root / "processed.wav"
        updated = post.postprocess(audio, aligned, output)
        self.assertAlmostEqual(sf.info(output).duration, sf.info(audio).duration / 1.08, delta=.05)
        samples, rate = sf.read(output)
        segment = samples[round(.03 * rate):round(.18 * rate)]
        frequencies = np.fft.rfftfreq(len(segment), 1 / rate)
        peak = frequencies[np.argmax(np.abs(np.fft.rfft(segment)))]
        self.assertAlmostEqual(peak, 160, delta=4)
        self.assertEqual(updated["postprocessing"]["speed"], 1.08)

    def test_scene_padding_is_in_semantic_budget(self):
        audio, aligned = self.synth(text="甲乙。 丙丁戊己。")
        chapter = dict(id="00", text=aligned["text"], scenes=[dict(id="0-1", text="甲乙。"), dict(id="0-2", text="丙丁戊己。")])
        (self.root / "analysis").mkdir()
        with patch.object(voice, "align_characters", return_value=(aligned["mapped"], 1., 0)):
            record, _, _, _, _, checked = voice.finish_chapter(chapter, audio, self.root, {}, {}, .2, 0, [])
        self.assertTrue(checked["ok"], checked["alerts"])
        boundary = next(b for b in checked["measurement"]["boundaries"] if b["kind"] == "sentence")
        self.assertGreaterEqual(boundary["pause_ms"], 300)
        self.assertLessEqual(boundary["pause_ms"], 450)
        self.assertTrue(record["postprocessing"])

    def test_skip_post_does_not_skip_check(self):
        audio, aligned = self.synth(durations=[.16, .16, .52, .16, .16, .16])
        chapter = dict(id="00", text=aligned["text"], scenes=[dict(id="0-1", text=aligned["text"])])
        (self.root / "analysis").mkdir()
        with patch.object(voice, "align_characters", return_value=(aligned["mapped"], 1., 0)):
            record, _, _, _, _, checked = voice.finish_chapter(chapter, audio, self.root, {}, {}, 0, 0, [], skip_post=True)
        self.assertFalse(checked["ok"])
        self.assertGreater(record["prosody_alert_count"], 0)
        self.assertTrue((self.root / "analysis/voice-check-00.json").is_file())

    def test_cli_alerts_and_invalid_timing_return_nonzero(self):
        audio, aligned = self.synth(gaps={1: .23})
        alignment, text_file, output = (self.root / n for n in ("timing.json", "text.txt", "result.json"))
        alignment.write_text(json.dumps(aligned))
        text_file.write_text(aligned["text"])
        command = [sys.executable, str(SCRIPTS / "voice-check.py"), "--audio", str(audio),
                   "--timing", str(alignment), "--text-file", str(text_file), "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(json.loads(output.read_text())["alerts"])
        wrapper = subprocess.run(["bash", str(SCRIPTS / "voice-check.sh"), *command[2:]],
                                 env={**os.environ, "YICE_VOICE_PYTHON": sys.executable},
                                 capture_output=True, text=True)
        self.assertEqual(wrapper.returncode, 1, wrapper.stderr)
        alignment.write_text(json.dumps([dict(start=0, end=1, text=aligned["text"])]))
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("character", json.loads(output.read_text())["error"])

    def test_generation_entry_blocks_manifest_on_alert(self):
        audio, aligned = self.synth(durations=[.16, .16, .52, .16, .16, .16])
        script, output = self.root / "script.md", self.root / "delivery"
        script.write_text("## 00 示例\n| 0-1 | " + aligned["text"] + " |\n")

        def fake_generation(*args, **kwargs):
            shutil.copyfile(audio, output / "raw/chapter-00-raw.wav")

        argv = ["voice.py", str(script), "--output", str(output), "--skip-post", "--silence", "0"]
        with patch.object(sys, "argv", argv), patch.object(voice.subprocess, "run", side_effect=fake_generation), \
                patch.dict(sys.modules, {"mlx_whisper": types.SimpleNamespace(transcribe=lambda *a, **k: {})}), \
                patch.object(voice, "align_characters", return_value=(aligned["mapped"], 1., 0)):
            with self.assertRaisesRegex(SystemExit, "配音检测未通过"):
                voice.main()
        self.assertFalse((output / "voice-manifest.json").exists())
        self.assertFalse((output / "voice.srt").exists())
        self.assertTrue(json.loads((output / "analysis/voice-check-00.json").read_text())["alerts"])

    def test_incomplete_alignment_and_silence_do_not_pass(self):
        audio, aligned = self.synth()
        text = self.root / "text.txt"
        text.write_text(aligned["text"])
        alignment = self.root / "alignment.json"
        alignment.write_text(json.dumps({**aligned, "mapped": aligned["mapped"][:-1]}))
        with self.assertRaisesRegex(ValueError, "cover every"):
            check.load_alignment(alignment, text, audio)
        sf.write(audio, np.zeros(16000), 16000, subtype="PCM_24")
        with self.assertRaisesRegex(ValueError, "non-silent"):
            self.scan(audio, aligned)


if __name__ == "__main__":
    unittest.main()
