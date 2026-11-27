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
from workspace import load_environment, ensure_voice_dependencies, resolve_gsap_runtime, resolve_hyperframes_command


class EnvironmentTests(unittest.TestCase):
    def test_hyperframes_uses_highest_cached_version_and_respects_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = {'HOME':tmp,'PATH':str(home/'no-path')}
            def cached(slot, version, executable=True):
                modules = home/'.npm/_npx'/slot/'node_modules'
                binary = modules/'.bin/hyperframes'
                binary.parent.mkdir(parents=True)
                binary.write_text('#!/bin/sh\n')
                binary.chmod(0o755 if executable else 0o644)
                manifest = modules/'hyperframes/package.json'
                manifest.parent.mkdir()
                manifest.write_text(json.dumps({'version':version}))
                return binary
            cached('first','0.9.72')
            newest = cached('second','0.9.82')
            cached('rc','0.9.82-rc.1')
            cached('nonexecutable','0.10.0',executable=False)
            self.assertEqual(resolve_hyperframes_command(env),[str(newest)])
            command = '/custom folder/hyperframes'
            self.assertEqual(resolve_hyperframes_command({**env,'YICE_HYPERFRAMES_BIN':f'"{command}" --quiet'}),
                             [command,'--quiet'])

    def test_gsap_finds_toolkit_vendor_without_environment_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            toolkit = root/'toolkit'
            vendor = toolkit/'local/vendor/gsap.min.js'
            vendor.parent.mkdir(parents=True)
            vendor.write_text('// bundled in test toolkit')
            cfg = root/'.config/yice-video/env'
            cfg.parent.mkdir(parents=True)
            cfg.write_text(f'YICE_TOOLKIT="{toolkit}"\n')
            env = {'HOME':tmp,'PATH':str(root/'no-path')}
            self.assertEqual(resolve_gsap_runtime(root=root,environ=env),vendor)
            explicit = root/'episode-gsap.js'
            explicit.touch()
            self.assertEqual(resolve_gsap_runtime('episode-gsap.js',root=root,environ=env),explicit)
            home_override = root/'configured-gsap.js'
            home_override.touch()
            self.assertEqual(resolve_gsap_runtime(root=root,environ={**env,'YICE_GSAP_PATH':'~/configured-gsap.js'}),
                             home_override)

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

    def test_private_kaggle_config_is_voice_only_and_respects_exported_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            private = home / '.config/yice-youtube-video/kaggle-tts.env'
            private.parent.mkdir(parents=True)
            private.write_text('KAGGLE_TTS_TOKEN=private\nKAGGLE_TTS_ENDPOINT_URL=private-url\n'
                               'PEXELS_API_KEY=unrelated\n')
            private.chmod(0o600)
            (home / '.env').write_text('KAGGLE_TTS_ENDPOINT_URL=legacy-url\n')
            base = {'HOME': tmp, 'YICE_TOOLKIT': tmp}
            env = {**base, 'KAGGLE_TTS_TOKEN': 'explicit'}
            load_environment(env, kaggle_voice=True)
            self.assertEqual(env['KAGGLE_TTS_TOKEN'], 'explicit')
            self.assertEqual(env['KAGGLE_TTS_ENDPOINT_URL'], 'private-url')
            self.assertNotIn('PEXELS_API_KEY', env)
            for mode, voice, expected in ((0o600, True, 'private'), (0o600, False, None),
                                          (0o644, True, None)):
                with self.subTest(mode=mode, voice=voice):
                    private.chmod(mode)
                    env = dict(base)
                    load_environment(env, kaggle_voice=voice)
                    self.assertEqual(env.get('KAGGLE_TTS_TOKEN'), expected)
                    if expected is None:
                        self.assertEqual(env['KAGGLE_TTS_ENDPOINT_URL'], 'legacy-url')

    def test_stock_keys_respect_exported_environment_and_file_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            toolkit = home / 'toolkit'
            toolkit.mkdir()
            (toolkit / '.env').write_text(
                'export PEXELS_API_KEY="toolkit # literal" # comment\n'
                'KAGGLE_TTS_TOKEN=toolkit-test-value\n'
            )
            stock = home / '.config/yice-video/stock.env'
            stock.parent.mkdir(parents=True)
            stock.write_text(
                'PEXELS_API_KEY=stock-file-value\n'
                'PIXABAY_API_KEY=stock-fallback\n'
                'KAGGLE_TTS_ENDPOINT_URL=https://ignored.invalid\n'
                'UNRELATED_KEY=ignored\n'
            )
            base = {'HOME': tmp, 'YICE_TOOLKIT': str(toolkit)}
            env = dict(base)
            load_environment(env)
            self.assertEqual(env['PEXELS_API_KEY'], 'toolkit # literal')
            self.assertEqual(env['PIXABAY_API_KEY'], 'stock-fallback')
            self.assertEqual(env['KAGGLE_TTS_TOKEN'], 'toolkit-test-value')
            self.assertNotIn('KAGGLE_TTS_ENDPOINT_URL', env)
            self.assertNotIn('UNRELATED_KEY', env)

            env = {**base, 'PEXELS_API_KEY': 'exported-value'}
            load_environment(env)
            self.assertEqual(env['PEXELS_API_KEY'], 'exported-value')


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
            self.assertIn('Whisper 离线模型', report['missing'])
            self.assertIn('HyperFrames 离线 CLI', report['dependencies'])
            self.assertIn('品牌参考音', report['missing_hints'])
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
            antigravity = home / '.gemini/config/skills/yice-youtube-video'
            antigravity.mkdir(parents=True)
            (antigravity/'original.txt').write_text('existing skill')
            env = {k: v for k, v in os.environ.items() if k not in ['YICE_WORKSPACE', 'YICE_TOOLKIT']}
            env['HOME'] = str(home)
            ws, tk = home / 'workspace space', home / 'toolkit'
            command = [str(REPO / 'install.sh'), '--workspace', str(ws), '--toolkit', str(tk)]
            first = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
            result = json.loads(first.stdout)
            self.assertEqual(len(result['backups']), 3)
            self.assertEqual(claude.resolve(), REPO)
            self.assertEqual(codex.resolve(), REPO)
            self.assertEqual(antigravity.resolve(), REPO)
            self.assertEqual(next(home.joinpath('.config/yice-video/backups/.claude').glob('yice-youtube-video.bak-*')).joinpath('keep.txt').read_text(), 'existing skill')
            self.assertTrue(next(home.joinpath('.config/yice-video/backups/.codex').glob('yice-youtube-video.bak-*')).is_symlink())
            self.assertTrue(any((Path(item)/'original.txt').is_file() for item in result['backups']))
            self.assertEqual(load_environment(env), (ws, tk))
            self.assertIn('toolkit', result['missing'])
            self.assertEqual((home / '.config/yice-video/env').stat().st_mode & 0o777, 0o600)
            second = json.loads(subprocess.run(command, env=env, capture_output=True, text=True, check=True).stdout)
            self.assertEqual(second['backups'], [])
            updated = json.loads(subprocess.run([str(REPO / 'install.sh'), '--workspace', str(home / 'new'), '--toolkit', str(tk)], env=env, capture_output=True, text=True, check=True).stdout)
            self.assertEqual(len(updated['backups']), 1)
            self.assertTrue(Path(updated['backups'][0]).name.startswith('env.bak-'))


class VoiceDependencyTests(unittest.TestCase):
    versions = {'librosa': '1.0.1', 'soundfile': '0.14.0', 'scipy': '1.18.1', 'numpy': '2.5.4', 'Pillow': '13.0.0'}

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
        before = {**self.versions, 'librosa': '0.11.0', 'soundfile': None, 'scipy': None, 'Pillow': None}
        responses = [subprocess.CompletedProcess([], 0, stdout=json.dumps(before)),
                     subprocess.CompletedProcess([], 0, stdout='', stderr=''),
                     subprocess.CompletedProcess([], 0, stdout=json.dumps(self.versions))]
        with tempfile.TemporaryDirectory() as tmp, patch('shutil.which', return_value='uv'), \
                patch('subprocess.run', side_effect=responses) as run:
            result = ensure_voice_dependencies(self.toolkit(tmp))
        self.assertTrue(result['ready'])
        self.assertEqual(result['installed'], ['librosa==1.0.1', 'soundfile==0.14.0', 'scipy', 'Pillow'])
        self.assertEqual(run.call_args_list[1].args[0][-4:], result['installed'])

    def test_install_failure_does_not_claim_ready(self):
        responses = [subprocess.CompletedProcess([], 0, stdout=json.dumps({})),
                     subprocess.CompletedProcess([], 1, stdout='', stderr='download failed')]
        with tempfile.TemporaryDirectory() as tmp, patch('shutil.which', return_value='uv'), \
                patch('subprocess.run', side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, '依赖安装失败'):
                ensure_voice_dependencies(self.toolkit(tmp))


if __name__ == '__main__':
    unittest.main()
