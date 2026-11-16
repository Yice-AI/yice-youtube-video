import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'kit/scripts'))
from workspace import load_environment


class EnvironmentTests(unittest.TestCase):
    def test_priority_and_default_are_independent_of_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            ws, tk = load_environment({'HOME': tmp})
            self.assertEqual(ws, home / 'Documents/Codex/个人IP')
            self.assertEqual(tk, ws / 'claude-code-video-toolkit')
            cfg = home / '.config/yice-video/env'; cfg.parent.mkdir(parents=True)
            cfg.write_text("YICE_WORKSPACE='$HOME/config space'\nYICE_TOOLKIT='~/local toolkit'\n")
            ws, tk = load_environment({'HOME': tmp})
            self.assertEqual(ws, home / 'config space')
            self.assertEqual(tk, home / 'local toolkit')
            ws, tk = load_environment({'HOME': tmp, 'YICE_WORKSPACE': str(home / 'override'), 'YICE_TOOLKIT': str(home / 'custom')})
            self.assertEqual(ws, home / 'override')
            self.assertEqual(tk, home / 'custom')

    def test_configuration_is_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve(); cfg = home / '.config/yice-video/env'; cfg.parent.mkdir(parents=True)
            marker = home / 'should-not-exist'
            cfg.write_text(f'YICE_WORKSPACE=$(touch {marker})\n')
            with self.assertRaises(ValueError):
                load_environment({'HOME': tmp})
            self.assertFalse(marker.exists())


class InstallTests(unittest.TestCase):
    def test_fake_home_preserves_existing_entries_and_writes_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / 'home'; home.mkdir()
            claude = home / '.claude/skills/yice-youtube-video'; claude.mkdir(parents=True)
            (claude / 'keep.txt').write_text('existing skill')
            codex = home / '.codex/skills/yice-youtube-video'; codex.parent.mkdir(parents=True)
            codex.symlink_to(home / 'missing-target')
            env = {k: v for k, v in os.environ.items() if k not in ['YICE_WORKSPACE', 'YICE_TOOLKIT']}
            env['HOME'] = str(home)
            ws, tk = home / 'workspace space', home / 'toolkit'
            command = [str(REPO / 'install.sh'), '--workspace', str(ws), '--toolkit', str(tk)]
            first = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
            result = json.loads(first.stdout)
            self.assertEqual(len(result['backups']), 2)
            self.assertEqual(claude.resolve(), REPO)
            self.assertEqual(codex.resolve(), REPO)
            self.assertEqual(next(claude.parent.glob('yice-youtube-video.bak-*')).joinpath('keep.txt').read_text(), 'existing skill')
            self.assertTrue(next(codex.parent.glob('yice-youtube-video.bak-*')).is_symlink())
            self.assertEqual(load_environment(env), (ws, tk))
            self.assertIn('toolkit', result['missing'])
            self.assertEqual((home / '.config/yice-video/env').stat().st_mode & 0o777, 0o600)
            second = json.loads(subprocess.run(command, env=env, capture_output=True, text=True, check=True).stdout)
            self.assertEqual(second['backups'], [])
            updated = json.loads(subprocess.run([str(REPO / 'install.sh'), '--workspace', str(home / 'new'), '--toolkit', str(tk)], env=env, capture_output=True, text=True, check=True).stdout)
            self.assertEqual(len(updated['backups']), 1)
            self.assertTrue(Path(updated['backups'][0]).name.startswith('env.bak-'))


if __name__ == '__main__':
    unittest.main()
