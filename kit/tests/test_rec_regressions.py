import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from test_rec_shot import FakeBackend, INPUT, RESULT, rec, shot


class RecordingRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def scene(self, *steps):
        return shot({"type": "rec_start", "region": [0, 0, 100, 100], "out": str(self.root / "take.mov")},
                    *steps, {"type": "rec_stop"})

    def execute(self, value, fake=None):
        fake = fake or FakeBackend()
        runner = rec.Runner(value, fake, lambda: fake.now, fake.sleep)
        runner.run()
        return runner, fake

    def test_equivalence_table_does_not_relax_other_characters(self):
        self.assertEqual(rec.exact_text('“＠示例”：＂a＂'), rec.exact_text('"@示例":"a"'))
        for left, right in [('A b', 'Ab'), ('X', 'x'), ('@示例', '示例'), ('a\n', 'a'), ('é', 'e\u0301')]:
            with self.subTest(left=left):
                self.assertNotEqual(rec.exact_text(left), rec.exact_text(right))

    def test_ocr_missing_at_requires_exact_input_readback(self):
        fake = FakeBackend()
        original = fake.ocr
        def ocr(rect):
            result = original(rect)
            if rect == INPUT:
                for row in result:
                    row['text'] = row['text'].replace('@', '')
            return result
        fake.ocr = ocr
        self.execute(self.scene({'type': 'paste', 'text': '请写“@示例”'}, {'type': 'key', 'key': 'return'}), fake)
        self.assertIn(('read_input', '请写“@示例”'), fake.calls)
        self.assertIn(('key', 'return'), fake.calls)

    def test_missing_at_in_actual_input_never_sends(self):
        fake = FakeBackend()
        original = fake.paste_clipboard
        def paste():
            original()
            fake.buffer = fake.buffer.replace('@', '')
        fake.paste_clipboard = paste
        with self.assertRaisesRegex(rec.ShotError, '逐字核对'):
            self.execute(self.scene({'type': 'paste', 'text': '@示例'}, {'type': 'key', 'key': 'return'}), fake)
        self.assertNotIn(('key', 'return'), fake.calls)

    def test_send_rejects_whitespace_and_case_changes_hidden_by_ocr(self):
        for actual in ['AB', 'a b', 'A B\n']:
            with self.subTest(actual=actual):
                fake = FakeBackend()
                fake.read_input = lambda: actual if fake.buffer else ''
                with self.assertRaisesRegex(rec.ShotError, '逐字核对'):
                    self.execute(self.scene({'type': 'paste', 'text': 'A B'}, {'type': 'key', 'key': 'return'}), fake)
                self.assertNotIn(('key', 'return'), fake.calls)

    def test_exact_readback_restores_paste_clipboard_even_on_error(self):
        backend = rec.MacBackend.__new__(rec.MacBackend)
        backend.copy_verified = mock.Mock()
        backend.key = mock.Mock()
        for response in [b'@example', RuntimeError('copy error')]:
            with self.subTest(response=response), mock.patch.object(rec.subprocess, 'check_output', side_effect=[b'next chunk', response]), \
                    mock.patch.object(rec.subprocess, 'run') as write, mock.patch.object(rec.time, 'sleep'):
                if isinstance(response, Exception):
                    with self.assertRaises(RuntimeError):
                        backend.read_input()
                else:
                    self.assertEqual(backend.read_input(), '@example')
                self.assertEqual(write.call_args.kwargs['input'], b'next chunk')

    def test_mutating_steps_cannot_run_without_rec_start(self):
        for step in [{'type': 'paste', 'text': 'x'}, {'type': 'prepare_input'}, {'type': 'key', 'key': 'return'},
                     {'type': 'click', 'x': 1, 'y': 1}, {'type': 'click_text', 'region': INPUT, 'text': 'Send'}]:
            with self.subTest(step=step), self.assertRaisesRegex(rec.ShotError, 'rec_start'):
                rec.build_plan(shot(step))

    def test_failed_or_unconfirmed_capture_never_inputs(self):
        for ready in [None, {'ready': False}]:
            fake = FakeBackend()
            fake.start_record = mock.Mock(return_value=ready)
            with self.subTest(ready=ready), self.assertRaisesRegex(rec.ShotError, '启动确认'):
                self.execute(self.scene({'type': 'paste', 'text': 'x'}, {'type': 'key', 'key': 'return'}), fake)
            self.assertFalse(any(call[0] in {'paste', 'click', 'key', 'clear_input'} for call in fake.calls))

    def test_capture_dying_after_clipboard_copy_prevents_paste(self):
        fake = FakeBackend()
        original = fake.copy_verified
        def copy_chunk(chunk):
            original(chunk)
            fake.active = False
        fake.copy_verified = copy_chunk
        with self.assertRaisesRegex(rec.ShotError, '禁止输入'):
            self.execute(self.scene({'type': 'paste', 'text': 'x'}), fake)
        self.assertNotIn('paste', [call[0] for call in fake.calls])

    def test_window_read_retries_three_times_then_recovers(self):
        fake = FakeBackend()
        original = fake.front
        fake.front = mock.Mock(side_effect=[OSError('missing value')] * 3 + [original()] * 40)
        self.execute(self.scene({'type': 'wait', 'sec': 1}), fake)
        self.assertEqual([call for call in fake.calls if call == ('sleep', .2)], [('sleep', .2)] * 3)

    def test_window_read_failure_stops_after_four_attempts(self):
        fake = FakeBackend()
        fake.front = mock.Mock(side_effect=rec.ShotError('missing value'))
        with self.assertRaisesRegex(rec.ShotError, '重试 3 次失败'):
            self.execute(self.scene({'type': 'paste', 'text': 'x'}), fake)
        self.assertEqual(fake.front.call_count, 4)
        self.assertFalse(any(call[0] == 'rec_start' for call in fake.calls))

    def test_wrong_nonempty_window_is_not_retried(self):
        fake = FakeBackend()
        fake.front = mock.Mock(return_value=('ChatGPT', '别的会话'))
        with self.assertRaisesRegex(rec.ShotError, '窗口标题'):
            self.execute(self.scene({'type': 'paste', 'text': 'x'}), fake)
        self.assertEqual(fake.front.call_count, 1)

    def test_suggestion_is_cleared_and_never_clicked_again_before_typing(self):
        fake = FakeBackend()
        fake.buffer = '使用示例建议'
        value = self.scene({'type': 'paste', 'text': '新输入'}, {'type': 'key', 'key': 'return'})
        value['target']['input']['suggestions'] = ['使用示例建议']
        self.execute(value, fake)
        kinds = [call[0] for call in fake.calls]
        clear, paste = kinds.index('clear_input'), kinds.index('paste')
        self.assertNotIn('click', kinds[clear + 1:paste])
        self.assertIn(('read_input', '新输入'), fake.calls)

    def test_known_question_is_skipped_and_moved_input_is_relocated(self):
        fake = FakeBackend()
        fake.card = True
        moved = [10, 40, 80, 15]
        def ocr(rect):
            if rect == [0, 0, 100, 100]:
                return ([{'text': '请选择演示方式', 'center': [50, 20]}, {'text': '跳过', 'center': [80, 25]}]
                        if fake.card else [{'text': '给示例发消息', 'center': [50, 47]}])
            value = '' if fake.card or rect != moved else (fake.buffer or '给示例发消息')
            return [{'text': value, 'center': [50, 47]}] if value else []
        fake.ocr = ocr
        original_click = fake.click
        def click(x, y):
            original_click(x, y)
            if [x, y] == [80, 25]:
                fake.card = False
        fake.click = click
        fake.input_bounds = lambda: moved[:]
        value = self.scene({'type': 'paste', 'text': '演示'}, {'type': 'key', 'key': 'return'})
        value['target']['input']['empty_text'] = '给示例发消息'
        value['target']['ui'] = {'question_markers': ['请选择演示方式']}
        self.execute(value, fake)
        self.assertEqual(fake.calls.count(('click', 80, 25)), 1)
        self.assertIn(('read_input', '演示'), fake.calls)
        self.assertLess([x[0] for x in fake.calls].index('rec_start'), fake.calls.index(('click', 80, 25)))

    def test_unknown_card_and_modal_stop_with_failure_screenshot(self):
        for control, modal in [('跳过', False), ('提交', False), ('允许', False), ('跳过', True)]:
            fake = FakeBackend()
            fake.has_modal = lambda: modal
            original = fake.ocr
            fake.ocr = lambda rect: [{'text': control, 'center': [20, 20]}] if rect == [0, 0, 100, 100] else original(rect)
            value = self.scene({'type': 'paste', 'text': '禁止输入'})
            value['target']['ui'] = {'question_markers': ['已知提问']}
            with self.subTest(modal=modal), self.assertRaisesRegex(rec.ShotError, '未知'):
                self.execute(value, fake)
            self.assertIn('failure', [call[0] for call in fake.calls])
            self.assertNotIn('paste', [call[0] for call in fake.calls])

    def test_existing_video_or_log_directory_gets_a_new_number(self):
        output = self.root / 'take.mov'
        output.write_bytes(b'KEEP')
        (self.root / 'take-take02.mov.rec').mkdir()
        runner, fake = self.execute(self.scene({'type': 'paste', 'text': 'x'}))
        self.assertEqual(output.read_bytes(), b'KEEP')
        self.assertEqual(Path(runner.completed[0]['raw']).name, 'take-take03.mov')
        self.assertIn('paste', [call[0] for call in fake.calls])

    def test_delayed_button_is_waited_for_and_ambiguous_button_never_clicked(self):
        runner, fake = self.execute(self.scene({'type': 'click_text', 'region': RESULT, 'text': '重新对齐完成', 'timeout': 3}))
        self.assertEqual(fake.now, 2)
        self.assertIn(('click', 15, 20), fake.calls)
        fake = FakeBackend()
        original = fake.ocr
        fake.ocr = lambda rect: [{'text': '开始', 'center': [10, 10]}] * 2 if rect == RESULT else original(rect)
        with self.assertRaisesRegex(rec.ShotError, '唯一文字框'):
            self.execute(self.scene({'type': 'click_text', 'region': RESULT, 'text': '开始', 'timeout': 3}), fake)
        self.assertNotIn('click', [call[0] for call in fake.calls])

    def test_old_completion_marker_cannot_finish_a_new_message(self):
        fake = FakeBackend()
        fake.result_at = 0
        with self.assertRaisesRegex(rec.ShotError, '超时'):
            self.execute(self.scene({'type': 'paste', 'text': '新任务'}, {'type': 'key', 'key': 'return'},
                {'type': 'wait_text', 'region': RESULT, 'text': '完成', 'timeout': 3, 'fresh': True}), fake)

    def test_native_start_requires_live_processes_and_file_growth(self):
        for mode in ['growing', 'stuck', 'dead']:
            backend = rec.MacBackend.__new__(rec.MacBackend)
            backend.binary = mock.Mock(return_value='/synthetic/cursorlog')
            processes = [mock.Mock(), mock.Mock()]
            for process in processes:
                process.poll.return_value = 1 if mode == 'dead' else None
            backend.capture_process = mock.Mock(side_effect=processes)
            backend.stop_record = mock.Mock()
            now = [0.0]
            folder = self.root / mode
            folder.mkdir()
            output = folder / 'video.mov'
            def advance(seconds):
                now[0] += seconds
                if mode == 'growing':
                    with output.open('ab') as stream:
                        stream.write(b'FAKE')
            with self.subTest(mode=mode), mock.patch.object(rec.time, 'monotonic', side_effect=lambda: now[0]), \
                    mock.patch.object(rec.time, 'sleep', side_effect=advance), mock.patch.object(rec, 'CAPTURE_LOCK', self.root / 'capture.lock'):
                if mode == 'growing':
                    self.assertTrue(backend.start_record([0, 0, 100, 100], output, folder)['ready'])
                else:
                    with self.assertRaises(rec.ShotError):
                        backend.start_record([0, 0, 100, 100], output, folder)
            backend.recording['handle'].close()
            backend.release_capture()

    def test_single_capture_lock_prevents_overlapping_recorders(self):
        first = rec.MacBackend.__new__(rec.MacBackend)
        second = rec.MacBackend.__new__(rec.MacBackend)
        with mock.patch.object(rec, 'CAPTURE_LOCK', self.root / 'capture.lock'):
            first.acquire_capture()
            try:
                with self.assertRaisesRegex(rec.ShotError, '重叠录制'):
                    second.acquire_capture()
            finally:
                first.release_capture()
            second.acquire_capture()
            second.release_capture()

    def test_capture_child_explicitly_resets_inherited_sigint(self):
        backend = rec.MacBackend.__new__(rec.MacBackend)
        with mock.patch.object(rec.subprocess, 'Popen') as popen:
            backend.capture_process(['/native/capture', '-v'], io.BytesIO())
        command = popen.call_args.args[0]
        self.assertIn('signal.signal(signal.SIGINT,signal.SIG_DFL)', command[2])
        self.assertEqual(command[3:], ['/native/capture', '-v'])

    def test_unresponsive_recorder_is_reaped_after_bounded_escalation(self):
        backend = rec.MacBackend.__new__(rec.MacBackend)
        recorder, logger = mock.Mock(), mock.Mock()
        recorder.poll.side_effect = [None, 0]
        logger.poll.side_effect = [None, 0]
        recorder.wait.side_effect = [subprocess.TimeoutExpired('capture', 5), subprocess.TimeoutExpired('capture', 3), -9]
        logger.wait.return_value = 0
        backend.recording = {'recorder': recorder, 'logger': logger, 'handle': io.BytesIO(), 'epoch': 0, 'region': INPUT}
        with self.assertRaisesRegex(rec.ShotError, '强制结束'):
            backend.stop_record()
        recorder.terminate.assert_called_once()
        recorder.kill.assert_called_once()
        self.assertEqual([call.kwargs['timeout'] for call in recorder.wait.call_args_list], [5, 3, 2])
        logger.send_signal.assert_called_once_with(rec.signal.SIGINT)

    def test_event_trim_removes_only_static_head_and_tail_and_keeps_raw(self):
        runner, fake = self.execute(self.scene({'type': 'wait', 'sec': 5}, {'type': 'paste', 'text': 'abc'},
                                              {'type': 'wait', 'sec': 7}))
        info = runner.completed[0]
        self.assertAlmostEqual(info['trim']['start'], 4.6)
        self.assertAlmostEqual(info['trim']['end'], 5.5)
        self.assertTrue(Path(info['raw']).exists())
        self.assertTrue(Path(info['take']).exists())
        events = json.loads((Path(info['events']).parent / 'trimmed-events.json').read_text())
        self.assertTrue(all(event['t'] >= 0 for event in events['events']))
        self.assertEqual(rec.trim_bounds([], 8), (0, 8))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
    def test_native_trim_on_synthetic_video_preserves_source(self):
        source, output = self.root / 'synthetic.mov', self.root / 'trimmed.mov'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=10:d=4',
                        '-c:v', 'libx264', str(source)], check=True)
        original = source.read_bytes()
        backend = rec.MacBackend.__new__(rec.MacBackend)
        backend.trim(source, output, 1, 2.5)
        self.assertAlmostEqual(backend.probe(output)['duration'], 1.5, places=1)
        self.assertEqual(source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
