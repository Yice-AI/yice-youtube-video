import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'kit/scripts'))
from workspace import load_environment, ensure_voice_dependencies


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
    def test_check_mode_leaves_skill_and_path_config_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            env = {k: v for k, v in os.environ.items() if k not in ['YICE_WORKSPACE', 'YICE_TOOLKIT']}
            env['HOME'] = str(test_root)
            result = subprocess.run([str(REPO / 'install.sh'), '--check', '--toolkit', str(test_root / 'toolkit')],
                                    env=env, capture_output=True, text=True, check=True)
            report = json.loads(result.stdout)
            self.assertTrue(report['check_only'])
            self.assertEqual(report['links'], [])
            self.assertFalse((test_root / '.codex').exists())
            self.assertFalse((test_root / '.claude').exists())
            self.assertFalse((test_root / '.config/yice-video/env').exists())

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
            self.assertEqual(next(home.joinpath('.config/yice-video/backups/.claude').glob('yice-youtube-video.bak-*')).joinpath('keep.txt').read_text(), 'existing skill')
            self.assertTrue(next(home.joinpath('.config/yice-video/backups/.codex').glob('yice-youtube-video.bak-*')).is_symlink())
            self.assertEqual(load_environment(env), (ws, tk))
            self.assertIn('toolkit', result['missing'])
            self.assertEqual((home / '.config/yice-video/env').stat().st_mode & 0o777, 0o600)
            second = json.loads(subprocess.run(command, env=env, capture_output=True, text=True, check=True).stdout)
            self.assertEqual(second['backups'], [])
            updated = json.loads(subprocess.run([str(REPO / 'install.sh'), '--workspace', str(home / 'new'), '--toolkit', str(tk)], env=env, capture_output=True, text=True, check=True).stdout)
            self.assertEqual(len(updated['backups']), 1)
            self.assertTrue(Path(updated['backups'][0]).name.startswith('env.bak-'))


class VoiceDependencyTests(unittest.TestCase):
    versions = {'librosa': '1.0.1', 'soundfile': '0.14.0', 'scipy': '1.18.1', 'numpy': '2.5.4'}

    def toolkit(self, directory):
        toolkit = Path(directory)
        python = toolkit / 'local/asr-venv/bin/python'
        python.parent.mkdir(parents=True)
        python.touch()
        return toolkit

    def test_ready_environment_skips_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            response = subprocess.CompletedProcess([], 0, stdout=json.dumps(self.versions))
            with patch('subprocess.run', return_value=response) as run:
                result = ensure_voice_dependencies(self.toolkit(tmp))
            self.assertTrue(result['ready'])
            self.assertEqual(result['installed'], [])
            self.assertEqual(run.call_count, 1)
            self.assertIn('-I', run.call_args.args[0])

    def test_only_missing_or_wrong_version_packages_are_installed(self):
        before = {**self.versions, 'librosa': '0.11.0', 'soundfile': None, 'scipy': None}
        responses = [subprocess.CompletedProcess([], 0, stdout=json.dumps(before)),
                     subprocess.CompletedProcess([], 0, stdout='', stderr=''),
                     subprocess.CompletedProcess([], 0, stdout=json.dumps(self.versions))]
        with tempfile.TemporaryDirectory() as tmp, patch('shutil.which', return_value='uv'), \
                patch('subprocess.run', side_effect=responses) as run:
            result = ensure_voice_dependencies(self.toolkit(tmp))
        self.assertTrue(result['ready'])
        self.assertEqual(result['installed'], ['librosa==1.0.1', 'soundfile==0.14.0', 'scipy'])
        self.assertEqual(run.call_args_list[1].args[0][-3:], result['installed'])

    def test_install_failure_does_not_claim_ready(self):
        responses = [subprocess.CompletedProcess([], 0, stdout=json.dumps({})),
                     subprocess.CompletedProcess([], 1, stdout='', stderr='download failed')]
        with tempfile.TemporaryDirectory() as tmp, patch('shutil.which', return_value='uv'), \
                patch('subprocess.run', side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, '依赖安装失败'):
                ensure_voice_dependencies(self.toolkit(tmp))


if __name__ == '__main__':
    unittest.main()
