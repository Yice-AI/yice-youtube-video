"""离线组装回归：真实命令、素材时间戳和交付边界。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]


class NewEpisodeTests(unittest.TestCase):
    def test_custom_directory_reuses_notes_and_existing_project_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / 'custom project'
            notes = root / 'workspace/.scratch/youtube/episodes/ep02'; notes.mkdir(parents=True)
            (notes / 'script.md').write_text('已经完成的剧本')
            project.mkdir(); (project / 'notes.md').write_text('原有笔记')
            env = {**os.environ, 'YICE_WORKSPACE': str(root / 'workspace'), 'YICE_TOOLKIT': str(root / 'toolkit')}
            cmd = [str(KIT / 'scripts/new-episode.sh'), 'ep02', '--dir', str(project)]
            subprocess.run(cmd, env=env, capture_output=True, check=True)
            self.assertEqual((notes / 'script.md').read_text(), '已经完成的剧本')
            self.assertEqual((project / 'notes.md').read_text(), '原有笔记')
            config = json.loads((project / 'episode.json').read_text()); config['end'] = 42
            (project / 'episode.json').write_text(json.dumps(config))
            (project / 'beats.json').write_text('{"scenes": []}')
            subprocess.run(cmd, env=env, capture_output=True, check=True)
            self.assertEqual(json.loads((project / 'episode.json').read_text())['end'], 42)
            self.assertEqual((project / 'beats.json').read_text(), '{"scenes": []}')
            bad = subprocess.run([str(KIT / 'scripts/new-episode.sh'), 'ep03', '--dir', str(project)],
                                 env=env, capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual((project / 'beats.json').read_text(), '{"scenes": []}')


class VideoTests(unittest.TestCase):
    def test_timestamp_preparation_keeps_motion_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); src = root / 'source.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=30:duration=1',
                            '-vf', 'setpts=PTS+1/TB', '-fps_mode', 'passthrough', '-c:v', 'libx264', str(src)], check=True)
            original = src.read_bytes()
            code = f"""import {{prepareVideo,probeVideo}} from {json.dumps((KIT/'template/video.mjs').as_uri())};
            const p=prepareVideo({json.dumps(str(src))},{json.dumps(str(root))});
            console.log(JSON.stringify({{...p,info:probeVideo(p.file)}}));"""
            p = subprocess.run(['node', '--input-type=module', '-e', code], capture_output=True, text=True, check=True)
            data = json.loads(p.stdout)
            self.assertTrue(data['prepared'])
            self.assertEqual(float(data['info']['start_time']), 0)
            self.assertEqual(src.read_bytes(), original)
            self.assertAlmostEqual(float(data['info']['duration']), 1, places=2)
            frames = subprocess.run(['ffmpeg', '-v', 'error', '-i', data['file'], '-f', 'framemd5', '-'],
                                    capture_output=True, text=True, check=True).stdout
            checksums = [l.rsplit(',', 1)[-1] for l in frames.splitlines() if not l.startswith('#')]
            self.assertGreater(len(set(checksums)), 20)

    def test_even_one_blank_transition_frame_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); src = root / 'gap.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=white:size=160x90:rate=30:duration=1,drawbox=color=black:t=fill:enable=eq(n\\,10)',
                            '-c:v', 'libx264', str(src)], check=True)
            code = f"""import {{blackFrames}} from {json.dumps((KIT/'template/check-video.mjs').as_uri())};
            console.log(JSON.stringify(blackFrames({json.dumps(str(src))},0,1)));"""
            result = json.loads(subprocess.run(['node', '--input-type=module', '-e', code],
                                capture_output=True, text=True, check=True).stdout)
            self.assertEqual(len(result), 1)
            self.assertAlmostEqual(result[0]['time'], 10/30, places=5)

    def test_black_video_panel_is_detected_with_a_bright_surround(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'panel.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=white:size=160x90:rate=30:duration=1,drawbox=x=40:y=20:w=80:h=50:color=black:t=fill',
                            '-c:v', 'libx264', str(src)], check=True)
            code = f"""import {{blackFrames}} from {json.dumps((KIT/'template/check-video.mjs').as_uri())};
            import assert from 'node:assert/strict';
            const file={json.dumps(str(src))};
            assert.equal(blackFrames(file,0,1).length,0);
            assert.equal(blackFrames(file,0,1,{{x:42,y:22,width:76,height:46}}).length,30);
            assert.throws(()=>blackFrames(file,0,2),/完整转场/);"""
            p = subprocess.run(['node', '--input-type=module', '-e', code], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)


class BuildTests(unittest.TestCase):
    def fixture(self, root):
        project = root / 'project'; shutil.copytree(KIT / 'template', project)
        voice = project / 'voice'; voice.mkdir()
        chapters = [{'id': f'{i:02}', 'start': i * 2.0004, 'end': (i + 1) * 2.0004, 'path': f'{i:02}.wav'} for i in range(3)]
        timing = [{'id': f'{i}-1', 'firstCharTime': c['start'] + .2, 'end': c['end'] - .2,
                   'anchors': [{'phrase': '落下', 'time': c['start'] + .5}]} for i, c in enumerate(chapters)]
        (voice / 'voice-manifest.json').write_text(json.dumps({'chapters': chapters}))
        (voice / 'voice-timing.json').write_text(json.dumps(timing))
        for c in chapters:
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2:sample_rate=48000',
                            str(voice / c['path'])], check=True)
        config = {'id': 'ep02', 'voiceDir': 'voice', 'end': 9,
                  'chapters': {c['id']: {'title': f'章节{c["id"]}', 'stage': 'paper-gray'} for c in chapters}}
        beats = {'scenes': [{'id': f'S{i}-1', 'sents': [t['id']], 'recipe': 'single-line',
                            'spec': {'text': '回归测试'}, 'enter': 'cut'} for i, t in enumerate(timing)]}
        (project / 'episode.json').write_text(json.dumps(config)); (project / 'beats.json').write_text(json.dumps(beats))
        return project, config

    def test_chapter_boundary_uses_sentence_time_before_rounding_and_episode_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, _ = self.fixture(Path(tmp))
            subprocess.run(['node', 'build.mjs'], cwd=project, capture_output=True, check=True)
            report = json.loads((project / 'build-report.json').read_text())
            self.assertEqual([s['chapter'] for s in report], ['00', '01', '02'])
            self.assertEqual(report[1]['B'], 2)
            html = (project / 'compositions/scenes/s1-1.html').read_text()
            self.assertIn('"episodeId":"ep02"', html)
            # A non-numeric sentence ID falls back to the unrounded first character.
            timing = json.loads((project / 'voice/voice-timing.json').read_text())
            timing[1]['id'] = 'opening'
            beats = json.loads((project / 'beats.json').read_text()); beats['scenes'][1]['sents'] = ['opening']
            (project / 'voice/voice-timing.json').write_text(json.dumps(timing)); (project / 'beats.json').write_text(json.dumps(beats))
            subprocess.run(['node', 'build.mjs'], cwd=project, capture_output=True, check=True)
            self.assertEqual(json.loads((project / 'build-report.json').read_text())[1]['chapter'], '01')

    def test_formal_build_mixes_abc_sfx_and_exact_length_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, config = self.fixture(Path(tmp))
            for name, hz, duration in [('bed', 220, 10), ('stamp', 880, .15)]:
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                f'sine=frequency={hz}:duration={duration}:sample_rate=48000', str(project / f'{name}.wav')], check=True)
            config['audio'] = {'bgm': {k: 'bed.wav' for k in 'ABC'}, 'sfx_files': {'stamp': 'stamp.wav'},
                               'events': [{'scene': 'S1-1', 'at': '@落下', 'name': 'stamp'}]}
            (project / 'episode.json').write_text(json.dumps(config))
            built = subprocess.run(['node', 'build.mjs'], cwd=project, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            report = json.loads((project / 'audio-report.json').read_text())
            self.assertEqual(report['samples'], 9 * 48000)
            self.assertEqual(report['config']['bgm_below_voice_db'], 24)
            self.assertEqual(report['config']['sfx_normal_below_voice_db'], 18)
            self.assertEqual(report['config']['sfx_key_below_voice_db'], 12)
            self.assertAlmostEqual(float(report['loudness']['input_i']), -14, delta=.15)
            self.assertLessEqual(float(report['loudness']['input_tp']), -1)
            self.assertAlmostEqual(report['events'][0]['start'], 2.5004 - 2/30, places=5)
            index = (project / 'index.html').read_text()
            self.assertEqual(index.count('<audio '), 1); self.assertIn('id="master"', index)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json',
                                    str(project / 'assets/audio/master.wav')], capture_output=True, text=True, check=True)
            self.assertEqual(float(json.loads(probe.stdout)['format']['duration']), 9)


class RecipeTests(unittest.TestCase):
    def test_recipe_runtime_parameters(self):
        p = subprocess.run(['node', str(KIT / 'tests/recipe-runtime.mjs')], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_source_and_shipped_recipe_stay_in_sync(self):
        for name in ['checklist', 'photo-word', 'strike-slips']:
            source = (KIT / f'template/recipes/_src/{name}.js').read_text().rstrip()
            self.assertIn(source, (KIT / f'template/recipes/{name}.html').read_text())

    def test_tail_review_uses_episode_end(self):
        text = (KIT.parent / 'references/review-gates.md').read_text()
        self.assertIn('成片时长等于 episode.end', text)
        self.assertIn('2–4 秒', text)
        self.assertNotIn('成片时长与 voice-timing 的 end 一致', text)


if __name__ == '__main__':
    unittest.main()
