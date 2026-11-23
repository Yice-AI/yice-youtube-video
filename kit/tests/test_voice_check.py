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

    def test_intra_word_micro_dip_is_flagged(self):
        audio, aligned = self.synth(text="甲乙丙丁戊己。")
        samples, rate = sf.read(audio)
        right = aligned["mapped"][2]
        start = round(right["s"] * rate) + round(.05 * rate)
        end = start + round(.11 * rate)
        samples[start:start + round(.04 * rate)] *= .02
        sf.write(audio, samples, rate, subtype="PCM_24")
        self.assertFalse(any(f["kind"] == "intra_word_stutter" for f in self.scan(audio, aligned)["alerts"]))
        samples[start + round(.04 * rate):end] *= .02
        sf.write(audio, samples, rate, subtype="PCM_24")
        alerts = self.scan(audio, aligned)["alerts"]
        self.assertTrue(any(flag["kind"] == "intra_word_stutter" for flag in alerts))

    def test_legal_comma_pause_is_not_flagged(self):
        audio, aligned = self.synth(text="甲乙，丙丁戊己。", gaps={1: .24})
        self.assertEqual(self.scan(audio, aligned)["alerts"], [])

    def test_plain_comma_allows_continuous_speech(self):
        audio, aligned = self.synth(text="你觉得，哪一段。")
        result = self.scan(audio, aligned)
        self.assertFalse(any(a["kind"] == "punctuation_pause" for a in result["alerts"]))
        boundary = next(b for b in result["measurement"]["boundaries"] if b["kind"] == "comma")
        self.assertEqual(boundary["range_ms"], [0., 340.])

    def test_missing_contrast_pause_is_flagged(self):
        audio, aligned = self.synth(text="免费没有，得用账号。")
        self.assertTrue(any(f.get("pause_class") == "contrast" for f in self.scan(audio, aligned)["alerts"]))

    def test_natural_v7_accepts_linked_speech_and_protected_planned_pause(self):
        text = "免费没有，得用账号。现在开始。等等再看。"
        planned_at = text.index("。", text.index("。") + 1)
        gap_after = sum(c.isalnum() for c in text[:planned_at]) - 1
        audio, aligned = self.synth(text, gaps={gap_after: 3.34})
        aligned["planned_pauses"] = {str(planned_at): 3.0}
        natural = check.check_chapter(audio, aligned, profile="natural_v7")
        boundaries = [b for b in natural["measurement"]["boundaries"] if b["kind"] != "none"]
        self.assertEqual([b["range_ms"] for b in boundaries], [[0.,1250.],[0.,1250.],[2850.,3600.]])
        self.assertEqual([b["pause_ms"] for b in boundaries[:2]], [0.,0.])
        self.assertEqual([a for a in natural["alerts"] if a["kind"] == "punctuation_pause"], [], boundaries)
        legacy = self.scan(audio, aligned)
        self.assertTrue(any(a["kind"] == "punctuation_pause" for a in legacy["alerts"]))
        audio, aligned = self.synth(text="甲乙。丙丁戊己。", gaps={1: 1.4})
        natural = check.check_chapter(audio, aligned, profile="natural_v7")
        self.assertTrue(any(a.get("pause_class") == "sentence" for a in natural["alerts"]))

    def test_natural_v7_tolerates_short_unpunctuated_breath_and_flags_long_pause(self):
        audio, aligned = self.synth(gaps={1: .20})
        natural = check.check_chapter(audio, aligned, profile="natural_v7")
        kinds = {a["kind"] for a in natural["alerts"]}
        self.assertFalse(kinds & {"hesitation", "intra_word_stutter"})
        self.assertTrue(any("nonpunct_pause" in a.get("reasons", []) for a in self.scan(audio, aligned)["alerts"]))
        audio, aligned = self.synth(gaps={1: .34})
        natural = check.check_chapter(audio, aligned, profile="natural_v7")
        self.assertTrue(any("nonpunct_pause" in a.get("reasons", []) for a in natural["alerts"]))

    def test_lexical_falling_tone_alone_is_not_flagged(self):
        audio, aligned = self.synth(falling=2)
        result = self.scan(audio, aligned)
        self.assertLess(result["measurement"]["characters"][2]["f0_change_st"], -4)
        self.assertEqual(result["alerts"], [])

    def test_post_defers_missing_contrast_pause_without_silence(self):
        audio, aligned = self.synth(text="免费没有，得用账号。")
        output = self.root / "processed.wav"
        updated = post.postprocess(audio, aligned, output)
        result = self.scan(output, updated)
        boundary = next(b for b in result["measurement"]["boundaries"] if b["kind"] == "contrast")
        self.assertIn(boundary["char_boundary"], updated["unresolved_pause_boundaries"])
        self.assertEqual(updated["semantic_pause_edits"], [])
        self.assertTrue(any(alert["kind"] == "punctuation_pause" for alert in result["alerts"]))

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
            record, _, _, _, _, checked = voice.finish_chapter(chapter, audio, self.root, {"text": aligned["text"]}, {}, .2, 0, [])
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
            record, _, _, _, _, checked = voice.finish_chapter(chapter, audio, self.root, {"text": aligned["text"]}, {}, 0, 0, [], skip_post=True)
        self.assertFalse(checked["ok"])
        self.assertGreater(record["prosody_alert_count"], 0)
        self.assertTrue((self.root / "analysis/voice-check-00.json").is_file())

    def test_cli_alerts_and_invalid_timing_return_nonzero(self):
        audio, aligned = self.synth(gaps={1: .23})
        alignment, text_file, output = (self.root / n for n in ("timing.json", "text.txt", "result.json"))
        alignment.write_text(json.dumps(aligned))
        text_file.write_text(aligned["text"])
        command = [sys.executable, str(SCRIPTS / "voice-check.py"), "--audio", str(audio),
                   "--timing", str(alignment), "--text-file", str(text_file), "--output", str(output), "--profile", "legacy"]
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

        def fake_generation(jobs):
            for job in jobs:
                target = Path(job['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(audio, target)

        flow = voice.load_voice_tool('voice-repair')
        original_loader = voice.load_voice_tool
        argv = ["voice.py", str(script), "--output", str(output), "--skip-post", "--silence", "0",
                "--backend", "kaggle", "--profile", "legacy", "--max-repair-rounds", "0"]
        with patch.object(sys, "argv", argv), patch.object(voice, 'make_generator', return_value=fake_generation), \
                patch.object(voice, 'make_transcriber', return_value=lambda _: {'text': aligned['text']}), \
                patch.object(voice, 'load_voice_tool', side_effect=lambda name: flow if name == 'voice-repair' else original_loader(name)), \
                patch.object(flow.v, "align_characters", return_value=(aligned["mapped"], 1., 0)):
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
