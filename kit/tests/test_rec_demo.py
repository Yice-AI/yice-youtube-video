import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_rec_shot import FakeBackend, INPUT

SPEC = importlib.util.spec_from_file_location('rec_demo_test', Path(__file__).resolve().parents[1] / 'scripts/rec-demo.py')
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


def parameters(root):
    return {'version': 1, 'project': '演示项目', 'output_dir': str(root),
            'title_contains': ['演示项目'], 'reference_window': [0, 0, 100, 100],
            'input': {'region': INPUT[:], 'empty_text': '给示例发消息'},
            'messages': [{'text': '@示例：第一条', 'completion_text': '用时', 'timeout': 5},
                         {'text': '第二条', 'completion_text': '用时', 'timeout': 5}]}


class DemoBackend(FakeBackend):
    def __init__(self, private=None):
        super().__init__()
        self.result_at = 100

    def window(self, process, titles):
        self.calls.append(('window', process, titles))
        return [0, 0, 100, 100]

    def ocr(self, rect):
        self.calls.append(('ocr', rect, self.buffer))
        result = [{'text': self.buffer or '给示例发消息', 'center': [50, 70], 'screen_box': INPUT[:]}]
        if rect != INPUT and self.now >= self.result_at:
            result.append({'text': '用时 2 秒', 'center': [40, 20], 'screen_box': [10, 10, 40, 10]})
        return result

    def key(self, key):
        super().key(key)
        if key == 'return':
            self.result_at = self.now + 2


def runner(shot, backend):
    return demo.rec.Runner(shot, backend, lambda: backend.now, backend.sleep)


class RecDemoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.params = parameters(self.root / 'output')

    def test_message_order_text_completion_and_hard_recording_boundaries(self):
        shots = demo.build_shots(self.params)
        self.assertEqual(len(shots), 2)
        for actual, expected in zip(shots, self.params['messages']):
            steps = actual['shot']['steps']
            self.assertEqual([s['type'] for s in steps], ['rec_start', 'prepare_input', 'paste', 'key', 'wait_text', 'rec_stop'])
            self.assertEqual(steps[2]['text'], expected['text'])
            self.assertEqual(steps[-2]['text'], expected['completion_text'])
            self.assertTrue(steps[-2]['fresh'])
        self.assertFalse((self.root / 'output').exists())

    def test_browser_and_finder_steps_keep_their_declared_order(self):
        target = demo.build_shots(self.params)[0]['shot']['target']
        self.params['before'] = [{'name': 'Finder originals', 'target': {**target, 'process': 'Finder'},
                                  'steps': [{'type': 'click_text', 'region': INPUT, 'text': '大小', 'timeout': 4}]}]
        self.params['after'] = [{'name': 'Browser result', 'target': {**target, 'process': 'Google Chrome'},
                                 'steps': [{'type': 'wait_text', 'region': INPUT, 'text': '处理完成', 'timeout': 8}]}]
        shots = demo.build_shots(self.params)
        self.assertEqual([s['name'] for s in shots], ['Finder originals', 'message-01', 'message-02', 'Browser result'])
        self.assertEqual(shots[0]['shot']['steps'][1]['timeout'], 4)

    def test_calibration_maps_reference_regions_and_coordinates(self):
        shot = demo.build_shots(self.params)[0]['shot']
        shot['steps'] = [shot['steps'][0], {'type': 'click', 'x': 30, 'y': 40}, shot['steps'][-1]]
        fake = DemoBackend()
        fake.window = lambda *_: [200, 100, 200, 200]
        calibrated = demo.calibrate(shot, fake)
        self.assertEqual(calibrated['steps'][1], {'type': 'click', 'x': 260, 'y': 180})
        self.assertEqual(calibrated['steps'][0]['region'], [200, 100, 200, 200])
        self.assertEqual(calibrated['target']['input']['region'], [220, 220, 160, 40])
        self.assertEqual(shot['target']['region'], [0, 0, 100, 100])

    def test_input_is_located_by_unique_known_placeholder(self):
        shot = demo.build_shots(self.params)[0]['shot']
        fake = DemoBackend()
        moved = [10, 40, 80, 15]
        fake.ocr = lambda _: [{'text': '给示例发消息', 'center': [50, 47], 'screen_box': moved}]
        self.assertEqual(demo.calibrate(shot, fake)['target']['input']['region'], moved)
        fake.ocr = lambda _: [{'text': '给示例发消息', 'screen_box': INPUT}] * 2
        with self.assertRaisesRegex(demo.rec.ShotError, '多个候选'):
            demo.calibrate(shot, fake)

    def test_schema_rejects_shell_output_override_and_malformed_messages(self):
        cases = []
        for field, value in [('command', 'do not execute'), ('messages', []), ('output_dir', 'relative'), ('input', {})]:
            params = copy.deepcopy(self.params)
            params[field] = value
            cases.append(params)
        for message in [{'text': 'x', 'completion_text': 'done', 'timeout': -1},
                        {'text': 'x', 'completion_text': 'done', 'timeout': 3, 'shell': 'forbidden'}]:
            params = copy.deepcopy(self.params)
            params['messages'] = [message]
            cases.append(params)
        params = copy.deepcopy(self.params)
        params['after'] = [{'name': 'bad', 'target': demo.build_shots(params)[0]['shot']['target'],
                            'steps': [{'type': 'rec_start', 'region': INPUT, 'out': '/outside/take.mov'}]}]
        cases.append(params)
        for params in cases:
            with self.subTest(params=params), self.assertRaises(demo.rec.ShotError):
                demo.build_shots(params)

    def test_dry_run_has_no_ui_subprocess_or_file_writes(self):
        source = self.root / 'params.json'
        source.write_text(json.dumps(self.params))
        output = io.StringIO()
        with mock.patch.object(demo.rec, 'MacBackend', side_effect=AssertionError('UI')), \
                mock.patch.object(demo.rec.subprocess, 'run', side_effect=AssertionError('process')), \
                mock.patch.object(Path, 'mkdir', side_effect=AssertionError('mkdir')), \
                mock.patch.object(Path, 'write_text', side_effect=AssertionError('write')), contextlib.redirect_stdout(output):
            self.assertEqual(demo.main([str(source), '--dry-run']), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['mode'], 'dry-run')
        self.assertIn('deferred', result['calibration'])
        self.assertEqual(len(result['shots']), 2)

    def test_synthetic_run_produces_takes_events_index_and_empty_failure_report(self):
        backends = []
        def backend_factory(path):
            fake = DemoBackend(path)
            backends.append(fake)
            return fake
        result = demo.run_demo(self.params, backend_factory, runner)
        folder = Path(result['folder'])
        self.assertEqual(result['state'], 'complete')
        self.assertEqual(len(result['segments']), 2)
        self.assertEqual(len(list(folder.glob('*.mov'))), 2)
        for name in ['events.json', 'index.md', 'failure.json', 'dry-run.json', '01-shot.json', '02-shot.json']:
            self.assertTrue((folder / name).exists(), name)
        self.assertIsNone(json.loads((folder / 'failure.json').read_text())['failure'])
        for fake in backends:
            names = [call[0] for call in fake.calls]
            self.assertLess(names.index('rec_start'), names.index('clear_input'))
            self.assertEqual(names.count('rec_stop'), 1)

    def test_repeated_run_uses_new_directory_and_preserves_old_takes(self):
        first = demo.run_demo(self.params, DemoBackend, runner)
        original = Path(first['folder']) / '01-take.mov'
        data = original.read_bytes()
        second = demo.run_demo(self.params, DemoBackend, runner)
        self.assertNotEqual(first['folder'], second['folder'])
        self.assertEqual(original.read_bytes(), data)

    def test_unknown_popup_stops_first_segment_and_records_exact_step(self):
        fake = DemoBackend()
        fake.has_modal = lambda: True
        with self.assertRaisesRegex(demo.rec.ShotError, 'failure.json'):
            demo.run_demo(self.params, lambda _: fake, runner)
        report = json.loads((Path(self.params['output_dir']) / 'demo-take01/failure.json').read_text())
        self.assertEqual(report['failure']['segment'], 'message-01')
        self.assertEqual(report['failure']['step'], 1)
        self.assertIn('synthetic-failure.png', report['failure']['screenshot'])
        self.assertNotIn('paste', [call[0] for call in fake.calls])
        self.assertFalse((Path(self.params['output_dir']) / 'demo-take01/02-shot.json').exists())

    def test_failed_calibration_gets_a_report_and_never_records(self):
        fake = DemoBackend()
        fake.window = mock.Mock(side_effect=demo.rec.ShotError('window missing'))
        with self.assertRaisesRegex(demo.rec.ShotError, 'failure.json'):
            demo.run_demo(self.params, lambda _: fake, runner)
        report = json.loads((Path(self.params['output_dir']) / 'demo-take01/failure.json').read_text())
        self.assertEqual(report['failure']['step'], 'calibration')
        self.assertNotIn('rec_start', [call[0] for call in fake.calls])

    def test_preflight_failure_does_not_construct_backend(self):
        factory = mock.Mock(side_effect=AssertionError('must not run'))
        self.params['messages'][0]['timeout'] = -1
        with self.assertRaises(demo.rec.ShotError):
            demo.run_demo(self.params, factory, runner)
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
