import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT.parent), str(KIT/'scripts')]

from audit_v7 import onetake_craft_gate
from kit.editorial.editorial import EditorialStage

assemble = importlib.import_module('assemble-episode')
bridge = importlib.import_module('render-onetake-clip')


class DualEngineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = self.root/'runtime'
        for relative in (*assemble.ONETAKE_FILES, 'lib/ui_kit.js'):
            path = self.runtime/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('// runtime')
        self.entry = self.root/'motion'/'opener'/'comp.html'
        self.entry.parent.mkdir(parents=True)
        self.entry.write_text('<!doctype html><head></head><body>合成</body>')
        self.good_probe = dict(dur=1.0, fps=30, seek_errors=[], page_errors=[], beats=[.2,.6],
                               events=[dict(t=.2,kind='tick')], continuity=dict(events=[dict(kind='carried')]))

    def test_probe_blocks_before_render(self):
        for report,reason in (
            (dict(self.good_probe,seek_errors=[[.3,'bad']]),'采样失败'),
            (dict(self.good_probe,continuity=dict(events=[dict(kind='bare')])),'bare'),
        ):
            with self.subTest(reason=reason), patch.object(bridge,'resolve_onetake',return_value=self.runtime), \
                 patch.object(bridge.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(report))) as run:
                output = self.root/'out'/'clip.mp4'
                with self.assertRaisesRegex(ValueError,reason):
                    bridge.render_clip(self.entry,output)
                self.assertEqual(run.call_count,1)
                self.assertEqual(json.loads(output.with_suffix('.onetake-probe.json').read_text()),report)
        bridge.validate_probe(report, True)

    def test_bridge_packages_assets_and_uses_upstream_shutter(self):
        commands = []

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            if '-c' in cmd:
                staged = Path(cmd[-1].removeprefix('file://'))
                self.assertIn('lib/motion.js',staged.read_text())
                self.assertTrue((staged.parent/'lib/ui_kit.js').is_file())
                self.assertTrue(all((staged.parent/'assets/fonts'/name).is_file() for name in bridge.ONETAKE_FONTS))
                return subprocess.CompletedProcess(cmd,0,json.dumps(self.good_probe))
            if '--shutter' in cmd:
                target = Path(cmd[cmd.index('--out')+1])
                target.write_bytes(b'mp4')
                target.with_suffix('.render.json').write_text(json.dumps(
                    dict(fps=30, size=[1920,1080], shutter=180, frames=30)))
            else:
                Path(cmd[-1]).write_bytes(b'padded')
            return subprocess.CompletedProcess(cmd,0)

        output = self.root/'out'/'clip.mp4'
        with patch.object(bridge,'resolve_onetake',return_value=self.runtime), patch.object(bridge.subprocess,'run',side_effect=fake_run):
            bridge.render_clip(self.entry,output,span=1.0)
        self.assertTrue(commands[0][-2].endswith('/probe.py'))
        self.assertIn('180',commands[1])
        self.assertIn('tpad=stop_mode=clone:stop=11',commands[2])
        self.assertEqual(output.read_bytes(),b'padded')
        self.assertEqual(json.loads(output.with_suffix('.render.json').read_text())['padded_frames'],41)

    def test_onetake_cache_tracks_assets_and_audit_checks_shutter(self):
        shot = dict(id='one',comp='motion/opener/comp.html',start=0,end=1)
        output = self.root/'act'
        commands = []

        def render(cmd, **kwargs):
            commands.append(cmd)
            target = Path(cmd[cmd.index('--out')+1])
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(b'mp4')
            target.with_suffix('.onetake-probe.json').write_text(json.dumps(self.good_probe))
            target.with_suffix('.render.json').write_text('{"shutter": 180}')

        with patch.object(assemble,'resolve_onetake',return_value=self.runtime), patch.object(assemble,'probe_video',return_value=1.366016):
            clip, report = assemble.onetake(shot,self.root,output,render)
            self.assertEqual(report,self.good_probe)
            assemble.onetake(shot,self.root,output,render)
            self.assertEqual(len(commands),1)
            self.entry.with_name('style.css').write_text('body{color:red}')
            assemble.onetake(shot,self.root,output,render)
            self.assertEqual(len(commands),2)
        data = [dict(id='one',stage_mode='onetake_clip',files=[clip])]
        self.assertTrue(onetake_craft_gate(data,output)['ok'])
        (output/clip).with_suffix('.render.json').write_text('{"shutter": 0}')
        self.assertFalse(onetake_craft_gate(data,output)['ok'])

    def test_subcomposition_mount_assets_and_render_stamp(self):
        entry = self.root/'blocks'/'flow'/'index.html'
        entry.parent.mkdir(parents=True)
        entry.write_text('<html><head><style>#flow{color:white}</style></head><body>'
                         '<div id="flow" data-composition-id="flow"></div></body></html>')
        entry.with_name('colors.css').write_text('#flow{color:white}')
        vendor = self.root/'gsap.js'
        vendor.write_text('/* local */')
        act = self.root/'act'
        shot = dict(id='pipe', stage_mode='hyperframes_block', start=0., end=1., spoken_topic='流程',
                    media=[], media_start=0., composition='blocks/flow/index.html')
        stage = assemble.build_act([shot],self.root,act,'测试',None,gsap=vendor)
        stage.write_project(act)
        rendered = (act/'index.html').read_text()
        self.assertIn('data-composition-src="compositions/pipe/index.html"',rendered)
        self.assertIn('data-composition-id="flow"',rendered)
        mounted = act/'compositions/pipe'
        self.assertIn('<template>\n<style>',(mounted/'index.html').read_text())
        self.assertTrue((mounted/'assets/fonts/SourceHanSansCN-Bold.otf').is_file())
        self.assertEqual((mounted/'vendor/gsap.min.js').read_text(),vendor.read_text())
        assemble.install_asset(vendor,act/'vendor/gsap.min.js')
        (act/'assets').mkdir()
        (act/'assets/mix.wav').write_bytes(b'audio')

        def render(command, operation, args, folder, env, run):
            if operation=='render':
                (folder/args[-1]).write_bytes(b'mp4')

        with patch.object(assemble,'probe_video',return_value=1.), patch.object(assemble,'hyperframes_step',side_effect=render):
            self.assertEqual(assemble.render_act(act,stage,['hf'],{},None),'rendered')
            stamp = json.loads((act/'.render-stamp.json').read_text())
            self.assertEqual(set(stamp['media']),{'assets/mix.wav','vendor/gsap.min.js'})
            self.assertIn('compositions/pipe/colors.css',stamp['subcompositions'])
            self.assertEqual(assemble.render_act(act,stage,['hf'],{},None),'reused')
            (mounted/'colors.css').write_text('#flow{color:blue}')
            self.assertEqual(assemble.render_act(act,stage,['hf'],{},None),'rendered')
        entry.with_name('outside.css').symlink_to(vendor)
        with self.assertRaisesRegex(ValueError,'普通文件'):
            assemble.build_act([shot],self.root,act,'测试',None,gsap=vendor)

    def test_perspective_material_and_foreground(self):
        stage = EditorialStage('测试',duration=3.)
        stage.add_callout_rig(0.,3.,'source.mp4',framing='perspective_3d',motion='focus_push',
                              overlays=[dict(kind='prop_badge',at=.2,source='caliper.png',
                                             side='left',placement='foreground_hero',size=460)])
        stage.add_cinema_material(0.,3.,'aurora_indigo')
        combined = stage.render_visual_layers()
        self.assertIn('perspective:1400px',combined)
        self.assertIn('refractive-edge',combined)
        self.assertIn('film-grain',combined)
        self.assertIn('ambient-glow-bloom',combined)
        self.assertIn('rotationY:-8',str(stage.scripts))
        self.assertIn('back.out(1.4)',str(stage.scripts))
        self.assertIn('width="460.0"',combined)
        old = EditorialStage('测试',duration=3.)
        old.add_fullbleed_rig(0.,3.,'source.mp4',framing='studio_window')
        plain = old.render_visual_layers()
        self.assertNotIn('perspective-stage',plain)
        self.assertNotIn('shimmer-sweep',plain)
        self.assertNotIn('film-grain',plain)

    def test_transition_overlaps_only_visuals_at_the_cut(self):
        expression = dict(whip_push='xPercent:-100',zoom_through='scale:1.85',
                          iris_reveal='circle(135% at 50% 50%)',blur_crossfade='blur(16px)')
        for kind,pattern in expression.items():
            with self.subTest(kind=kind):
                shot = dict(stage_mode='title_sequence', spoken_topic='测试', media=[], media_start=0.)
                transition = dict(kind=kind,duration=.36)
                shots = [dict(shot,id='left',start=0.,end=2.),dict(shot,id='right',start=2.,end=4.,transition_in=transition)]
                stage = assemble.build_act(shots,self.root,self.root/'out','测试',None)
                stage.add_captions([dict(start=0.,end=2.,text='字幕')])
                stage.write_project(self.root/'out')
                rendered = (self.root/'out'/'index.html').read_text()
                self.assertIn('id="visual-left"',rendered)
                self.assertIn('id="visual-right"',rendered)
                self.assertIn('data-duration="2.36000"',rendered)
                self.assertIn('data-duration="2.00000" data-track-index="15"',rendered)
                self.assertIn(pattern,rendered)
                self.assertTrue(any("tl.to('#visual-left'" in line and '},2.00000)' in line for line in stage.scripts))
                self.assertTrue(any("tl.fromTo('#visual-right'" in line and '},2.00000)' in line for line in stage.scripts))
                self.assertEqual(stage.shots[0]['end'],stage.shots[1]['start'])
                self.assertIn(dict(kind='whoosh',at=2.0,gain=.60),list(stage.sound_events()))


if __name__ == '__main__':
    unittest.main()
