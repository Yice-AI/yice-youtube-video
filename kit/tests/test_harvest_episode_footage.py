import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
harvest = importlib.import_module('harvest-episode-footage')


class FootagePoolTests(unittest.TestCase):
    def test_public_demo_requires_https_and_excludes_creator_hosts(self):
        self.assertTrue(harvest.is_allowed_demo_url('https://motion.example/demo'))
        for url in ('http://motion.example/demo', '/clip.mp4', 'https://sub.youtube.com/watch'):
            with self.subTest(url=url):
                self.assertFalse(harvest.is_allowed_demo_url(url))

    def test_pool_deduplicates_final_files_across_input_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / 'first'
            second = root / 'second'
            first.mkdir()
            second.mkdir()
            (first / 'clip.mp4').write_bytes(b'a' * 100_001)
            (second / 'copy.mp4').write_bytes(b'a' * 100_001)
            (second / 'other.mp4').write_bytes(b'b' * 100_001)
            (second / 'unused.raw.mp4').write_bytes(b'c' * 100_001)
            (second / 'pending.part.mp4').write_bytes(b'd' * 100_001)
            (second / 'undersized.mp4').write_bytes(b'e' * 100_000)

            report = harvest.audit_pool([first, second, root / 'missing'], 61, per_minute=2)
            self.assertFalse(report['ok'])
            self.assertEqual(report['unique_mp4_count'], 2)
            self.assertEqual(report['required_mp4_count'], 3)
            self.assertEqual(report['by_directory'], {str(first): 1, str(second): 2, str(root / 'missing'): 0})
            self.assertTrue(harvest.audit_pool([first, second], 40, per_minute=2)['ok'])

    def test_stock_harvest_reuses_existing_clip_and_selects_full_hd(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'cached.mp4').write_bytes(b'c' * 150_001)
            clips = {'videos': [{'id': 12, 'duration': 8, 'video_files': [
                {'file_type': 'video/mp4', 'width': 1280, 'height': 720, 'link': 'https://example.invalid/720'},
                {'file_type': 'video/mp4', 'width': 1920, 'height': 1080, 'link': 'https://example.invalid/1080'},
            ]}]}

            def encode(command, *, check):
                self.assertTrue(check)
                self.assertIn('crop=1920:1080,fps=30', ' '.join(command))
                Path(command[-1]).write_bytes(b'converted fixture')

            with patch.object(harvest.urllib.request, 'urlopen', side_effect=[
                io.BytesIO(json.dumps(clips).encode()), io.BytesIO(b'fixture download'),
            ]) as request, patch.object(harvest.subprocess, 'run', side_effect=encode):
                records = harvest.fetch_pexels_1080p(
                    [('cached', 'cached query'), ('fresh', 'fresh query')], folder, 'synthetic-key'
                )

            self.assertEqual(request.call_count, 2)
            self.assertEqual(request.call_args.args[0].full_url, 'https://example.invalid/1080')
            self.assertTrue(records[0]['cached'])
            self.assertEqual(records[1]['provider_id'], 12)
            self.assertFalse((folder / 'fresh.raw.mp4').exists())


if __name__ == '__main__':
    unittest.main()
