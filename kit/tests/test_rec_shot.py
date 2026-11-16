import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location("rec_shot", Path(__file__).resolve().parents[1] / "scripts/rec-shot.py")
assert SPEC is not None and SPEC.loader is not None
rec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rec)
INPUT = [10, 60, 80, 20]
RESULT = [10, 10, 80, 40]


def shot(*steps):
    return {"version": 1, "target": {"process": "ChatGPT", "title_contains": ["演示项目", "演示会话"],
            "region": [0, 0, 100, 100], "input": {"region": INPUT, "initial_text": ""}},
            "steps": list(steps)}


class FakeBackend:
    """In-memory UI; never calls macOS, OCR, clipboard or a capture program."""
    def __init__(self):
        self.calls, self.buffer, self.clipboard = [], "", ""
        self.process, self.title = "ChatGPT", "演示项目 / 演示会话"
        self.now, self.result_at = 0, 2
        self.switch_after_copy = False

    def front(self):
        self.calls.append(("front", self.title))
        return self.process, self.title

    def ocr(self, rect):
        self.calls.append(("ocr", rect[:], self.buffer))
        value = self.buffer if rect == INPUT else ("重新对齐完成" if self.now >= self.result_at else "")
        return [{"text": value, "box": [0, 0, 10, 10], "confidence": 1, "center": [15, 20]}] if value else []

    def save_failure(self, rect):
        self.calls.append(("failure", rect))
        return "private/synthetic-failure.png"

    def click(self, x, y):
        self.calls.append(("click", x, y))

    def key(self, key):
        self.calls.append(("key", key))
        if rec.parse_key(key)[1] in {"enter", "return"}:
            self.buffer = ""

    def copy_verified(self, chunk):
        self.calls.append(("copy_verified", chunk))
        self.clipboard = chunk
        if self.switch_after_copy:
            self.title = "另一会话"

    def paste_clipboard(self):
        self.calls.append(("paste", self.clipboard))
        self.buffer += self.clipboard
        self.now += 0.1

    def start_record(self, rect, output, log_dir):
        self.calls.append(("rec_start", str(output)))
        output.write_bytes(b"FAKE VIDEO: unit test only")
        self.started = self.now

    def stop_record(self):
        self.calls.append(("rec_stop",))
        return {"exit_codes": {"recorder": 0, "logger": 0}, "simulated": True}

    def probe(self, output):
        return {"width": 200, "height": 200, "duration": max(0.1, self.now - self.started)}

    def close(self):
        self.calls.append(("close",))

    def sleep(self, sec):
        self.calls.append(("sleep", sec))
        self.now += sec


class RecShotTests(unittest.TestCase):
    def run_shot(self, value, backend=None):
        backend = backend or FakeBackend()
        rec.Runner(value, backend, lambda: backend.now, backend.sleep).run()
        return backend

    def test_parse_valid_and_reject_malformed_or_unbalanced_steps(self):
        value = shot({"type": "paste", "text": "按旁白重新对齐。"}, {"type": "key", "key": "return"})
        self.assertEqual(len(rec.build_plan(value)), 2)
        for replacement in [{"type": "unknown"}, {"type": "rec_stop"},
                            {"type": "wait", "sec": float("nan")},
                            {"type": "click", "x": True, "y": 2},
                            {"type": "key", "key": "cmd+garbage"}]:
            with self.subTest(replacement=replacement), self.assertRaises(rec.ShotError):
                rec.build_plan(shot(replacement))
        for field in ["process", "title_contains", "input"]:
            malformed = copy.deepcopy(value)
            del malformed["target"][field]
            with self.subTest(field=field), self.assertRaises(rec.ShotError):
                rec.build_plan(malformed)

    def test_guards_cannot_be_disabled(self):
        with self.assertRaises(rec.ShotError):
            rec.build_plan(shot({"type": "paste", "text": "测试", "guard": False}))
        with self.assertRaises(rec.ShotError):
            rec.build_plan(shot({"type": "key", "key": "return"}))

    def test_bad_window_stops_before_any_mutation_and_saves_failure(self):
        fake = FakeBackend()
        fake.title = "错误会话"
        with self.assertRaisesRegex(rec.ShotError, "窗口标题"):
            self.run_shot(shot({"type": "paste", "text": "不应输入"}, {"type": "key", "key": "return"}), fake)
        kinds = [x[0] for x in fake.calls]
        self.assertIn("failure", kinds)
        self.assertNotIn("copy_verified", kinds)
        self.assertNotIn("key", kinds)

    def test_input_mismatch_stops_before_send(self):
        fake = FakeBackend()
        fake.buffer = "意外文字"
        value = shot({"type": "key", "key": "cmd+return"})
        value["target"]["input"]["initial_text"] = "预期文字"
        with self.assertRaisesRegex(rec.ShotError, "输入框 OCR"):
            self.run_shot(value, fake)
        self.assertNotIn("key", [x[0] for x in fake.calls])

    def test_paste_is_three_characters_and_every_chunk_has_guard(self):
        fake = self.run_shot(shot({"type": "paste", "text": "按旁白重新对齐。"}))
        self.assertEqual([x[1] for x in fake.calls if x[0] == "paste"], ["按旁白", "重新对", "齐。"])
        previous = 0
        for index, call in enumerate(fake.calls):
            if call[0] == "paste":
                segment = fake.calls[previous:index]
                self.assertIn("copy_verified", [x[0] for x in segment])
                self.assertTrue(any(x[0] == "ocr" and x[1] == INPUT for x in segment))
                self.assertEqual(segment[-1][0], "front")
                previous = index + 1

    def test_window_switch_after_clipboard_copy_aborts_without_pasting(self):
        fake = FakeBackend()
        fake.switch_after_copy = True
        with self.assertRaises(rec.ShotError):
            self.run_shot(shot({"type": "paste", "text": "不应粘贴"}), fake)
        self.assertNotIn("paste", [x[0] for x in fake.calls])

    def test_ocr_forbidden_text_aborts(self):
        value = shot({"type": "click", "x": 30, "y": 40})
        value["target"]["ocr"] = [{"region": RESULT, "must_not_contain": ["重新对齐"]}]
        fake = FakeBackend()
        fake.now = 10
        with self.assertRaisesRegex(rec.ShotError, "区域 OCR"):
            self.run_shot(value, fake)
        self.assertNotIn("click", [x[0] for x in fake.calls])

    def test_click_text_uses_unique_ocr_center(self):
        fake = FakeBackend()
        fake.now = 10
        self.run_shot(shot({"type": "click_text", "region": RESULT, "text": "重新对齐完成"}), fake)
        self.assertIn(("click", 15, 20), fake.calls)

    def test_wait_text_polls_every_two_seconds_and_timeout_aborts(self):
        fake = self.run_shot(shot({"type": "wait_text", "region": RESULT, "text": "重新对齐", "timeout": 5}))
        self.assertEqual([x[1] for x in fake.calls if x[0] == "sleep"], [2])
        fake = FakeBackend()
        fake.result_at = 100
        with self.assertRaisesRegex(rec.ShotError, "超时"):
            self.run_shot(shot({"type": "wait_text", "region": RESULT, "text": "完成", "timeout": 3}), fake)
        self.assertEqual([x[1] for x in fake.calls if x[0] == "sleep"], [2, 1])

    def test_events_and_index_use_recording_relative_time(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "take.mov"
            fake = FakeBackend()
            fake.now = 100
            value = shot({"type": "rec_start", "region": [0, 0, 100, 100], "out": str(output)},
                         {"type": "click", "x": 30, "y": 70},
                         {"type": "paste", "text": "按旁白重新对齐。"},
                         {"type": "key", "key": "return"},
                         {"type": "wait_text", "region": RESULT, "text": "完成", "timeout": 3},
                         {"type": "rec_stop"})
            self.run_shot(value, fake)
            data = json.loads((Path(str(output) + ".rec") / "events.json").read_text())
            self.assertEqual(data["state"], "complete")
            self.assertEqual([event["type"] for event in data["events"]],
                             ["rec_start", "click", "input_start", "input_end", "send", "result", "rec_stop"])
            self.assertTrue(all(0 <= event["t"] < 1 for event in data["events"]))
            self.assertIsNone(data["video_start_offset_seconds"])
            self.assertIn("200×200", (Path(directory) / "index.md").read_text())
            self.assertTrue((Path(directory) / "index.md").read_text().endswith(" |  |\n"))

    def test_abort_stops_recording_and_marks_events_aborted(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "take.mov"
            fake = FakeBackend()
            fake.switch_after_copy = True
            value = shot({"type": "rec_start", "region": [0, 0, 100, 100], "out": str(output)},
                         {"type": "paste", "text": "不能发送"}, {"type": "rec_stop"})
            with self.assertRaises(rec.ShotError):
                self.run_shot(value, fake)
            data = json.loads((Path(str(output) + ".rec") / "events.json").read_text())
            self.assertEqual(data["state"], "aborted")
            self.assertIn(("rec_stop",), fake.calls)
            self.assertFalse((Path(directory) / "index.md").exists())

    def test_dry_run_has_no_backend_subprocess_or_filesystem_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shot.json"
            path.write_text(json.dumps(shot({"type": "paste", "text": "按旁白重新对齐。"})))
            before = sorted(Path(directory).rglob("*"))
            output = io.StringIO()
            with mock.patch.object(rec, "MacBackend", side_effect=AssertionError("backend")), \
                    mock.patch.object(rec.subprocess, "run", side_effect=AssertionError("process")), \
                    mock.patch.object(Path, "mkdir", side_effect=AssertionError("mkdir")), \
                    mock.patch.object(Path, "write_text", side_effect=AssertionError("write")), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(rec.main([str(path), "--dry-run"]), 0)
            plan = json.loads(output.getvalue())
            self.assertEqual(plan["mode"], "dry-run")
            self.assertEqual(plan["steps"][0]["guards"][0]["input_equals"], "")
            self.assertEqual(before, sorted(Path(directory).rglob("*")))

    def test_clipboard_exact_comparison_preserves_trailing_newline(self):
        backend = rec.MacBackend.__new__(rec.MacBackend)
        with mock.patch.object(rec.subprocess, "run") as copy_run, \
                mock.patch.object(rec.subprocess, "check_output", side_effect=[b"x", b"x\n"]) as read, \
                mock.patch.object(rec.time, "sleep"):
            backend.copy_verified("x\n")
        self.assertEqual(read.call_count, 2)
        self.assertEqual(copy_run.call_args.kwargs["input"], b"x\n")

    def test_native_stop_signals_both_processes_and_rejects_early_exit(self):
        for early in [False, True]:
            with self.subTest(early=early):
                backend = rec.MacBackend.__new__(rec.MacBackend)
                recorder, logger = mock.Mock(), mock.Mock()
                recorder.poll.side_effect = [1 if early else None, 0]
                recorder.wait.return_value = 1 if early else 0
                logger.poll.side_effect = [None, 0]
                logger.wait.return_value = 0
                handle = io.BytesIO()
                backend.recording = {"recorder": recorder, "logger": logger,
                                     "handle": handle, "epoch": 10, "region": [0, 0, 100, 100]}
                if early:
                    with self.assertRaisesRegex(rec.ShotError, "rec_stop 前已退出"):
                        backend.stop_record()
                else:
                    self.assertEqual(backend.stop_record()["exit_codes"], {"recorder": 0, "logger": 0})
                    recorder.send_signal.assert_called_once_with(rec.signal.SIGINT)
                logger.send_signal.assert_called_once_with(rec.signal.SIGINT)
                self.assertTrue(handle.closed)
                self.assertIsNone(backend.recording)


if __name__ == "__main__":
    unittest.main()
