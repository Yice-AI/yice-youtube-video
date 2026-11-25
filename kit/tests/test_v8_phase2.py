"""Phase 2 素材安装、编排与审计的离线回归。"""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(KIT/'scripts'))
assemble = importlib.import_module('assemble-episode')
audit_v7 = importlib.import_module('audit_v7')
audit_v3 = importlib.import_module('audit-v3')
scout = importlib.import_module('scout-video-scenes')

MARK = '<svg viewBox="0 0 64 64"><path fill="#e4b650" d="M4 4h56v56H4z"/></svg>'


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.act = self.root/'act'
        (self.root/'brand.svg').write_text(MARK)
        self.pixel = (34,111,191,95)
        Image.new('RGBA',(33,25),self.pixel).save(self.root/'plate.webp',lossless=True)
        frames = [Image.new('RGB',(33,25),color) for color in ('#844443','#328a55','#d5a750')]
        frames[0].save(self.root/'motion.gif',save_all=True,append_images=frames[1:],duration=120,loop=0)

    def shot(self, mode, **data):
        return dict(id='demo',anchor_cue_id='cue',start=0,end=3,stage_mode=mode,spoken_topic='观察资料',
                    visual_subject='来源资料',semantic_tags=['资料'],semantic_binding='conceptual_explainer',**data)

    def build(self, shot):
        rows,_ = assemble.prepare_shots({'shots':[shot]},self.root,{'cue':{'firstCharTime':0}})
        return assemble.build_act(rows,self.root,self.act,'素材台',subprocess.run)

    def test_webp_pixels_and_svg_namespace_are_preserved(self):
        svg = assemble.install_visual(self.root/'brand.svg',self.act/'assets/brand')
        self.assertEqual(svg.suffix,'.svg')
        self.assertIn('xmlns="http://www.w3.org/2000/svg"',svg.read_text())
        self.assertIn('d="M4 4h56v56H4z"',svg.read_text())
        png = assemble.install_visual(self.root/'plate.webp',self.act/'assets/plate')
        self.assertEqual(png.suffix,'.png')
        with Image.open(png) as image:
            self.assertEqual((image.size,image.mode,image.getpixel((16,12))),((33,25),'RGBA',self.pixel))

    def test_svg_rejects_active_content_and_external_resources(self):
        for invalid in ('<a/>','<svg><script/></svg>','<svg><foreignObject/></svg>',
                        '<svg><image href="https://example.invalid/a.png"/></svg>',
                        '<svg><image href="//example.invalid/a.png"/></svg>',
                        '<svg><path onclick="go()"/></svg>',
                        '<svg><style>path{fill:url(other.svg);stroke:url(#local)}</style></svg>',
                        '<!DOCTYPE svg SYSTEM "bad.dtd"><svg/>'):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError,'SVG'):
                source = self.root/'invalid.svg'
                source.write_text(invalid)
                assemble.install_visual(source,self.act/'assets/rejected')
        self.assertFalse((self.act/'assets/rejected.svg').exists())
        good = self.root/'gradient.svg'
        good.write_text('<svg><defs><linearGradient id="local"/></defs><path fill="url(#local)"/></svg>')
        self.assertTrue(assemble.install_visual(good,self.act/'assets/gradient').is_file())

    def test_triptych_gif_tail_is_frozen_and_logos_are_dependencies(self):
        stage = self.build(self.shot('triptych_cards',heading='双卡取证',cards=[
            dict(label='动态演示',source='motion.gif',reveal_at=.5,logo='brand.svg'),
            dict(label='实物裁切',source='plate.webp',reveal_at=1.),
        ]))
        row, = stage.shots
        self.assertEqual(row['files'],['assets/demo-0.mp4','assets/demo-1.png','assets/demo-card-0-logo.svg'])
        self.assertEqual(row['aux_files'],['assets/demo-card-0-logo.svg'])
        gif = self.act/row['cards'][0]['source']
        checked = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(gif)]))
        video, = checked['streams']
        self.assertEqual((video['r_frame_rate'],video['pix_fmt']),('30/1','yuv420p'))
        self.assertGreaterEqual(float(video['duration']),2.75)
        def pixels(at):
            return subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(gif),'-frames:v','1',
                                            '-f','rawvideo','-pix_fmt','rgb24','-'])
        last = pixels(2.5)
        self.assertTrue(last)
        self.assertEqual(last,pixels(1))
        self.assertNotEqual(last,pixels(0))
        gate = audit_v7.timeline_gates({'shots':[row],'cues':[{'id':'cue','firstCharTime':0}]},self.act,3.)
        self.assertEqual(gate['invalid_triptych_media'],[])
        self.assertEqual(gate['real_ratio'],0.)

    def test_evidence_uses_capture_box_and_safe_cutout_locations(self):
        data = {'sourceName':'来源样页','viewport':{'width':1920,'height':1080},
                'highlight':{'status':'located','box':{'x':260,'y':315,'width':410,'height':42}}}
        (self.root/'capture.json').write_text(json.dumps(data))
        stage = self.build(self.shot('evidence_spotlight',source='plate.webp',capture_meta='capture.json',logo='brand.svg',
                                     overlays=[dict(kind='prop_badge',source='plate.webp',at=.8,size=250,label='原件'),
                                               dict(kind='reaction_cutout',source='brand.svg',at=1.6,side='left',size=210)]))
        row, = stage.shots
        self.assertEqual(row['kind'],'screenshot')
        self.assertEqual(row['highlight_box'],[260,315,410,42])
        self.assertEqual(row['source_credit'],'来源样页')
        self.assertFalse(audit_v7.is_real_shot(row))
        self.assertEqual([mark['kind'] for mark in stage.sound_events()],['marker','pop','pop'])
        media, = stage.media_layers
        self.assertIn('left:200px;top:148px;width:1520px;height:712px',media)
        self.assertIn('class="evidence-stripe"',media)
        self.assertIn('scale:1.28',''.join(stage.scripts))
        self.assertIn('scale:1.32',''.join(stage.scripts))
        chrome = ''.join(stage.plates+stage.bg_layers)
        self.assertNotIn('drop-shadow',chrome)
        self.assertIn('<image x="1590.0" y="558.0"',chrome)
        self.assertIn('<image x="80" y="640.0"',chrome)
        self.assertIn('<text x="248" y="58"',chrome)
        self.assertTrue({'prop_badge','reaction_cutout'} <= audit_v7.MOTION_OVERLAYS)
        self.assertTrue(all((self.act/path).is_file() for path in row['files']))
        errors = []
        self.assertEqual(audit_v3.timeline_metrics({'shots':[row]},3.,self.act,errors)['max_windows_per_shot'],1)
        self.assertEqual(errors,[])
        self.assertTrue(audit_v3.cutout_overlays_gate({'shots':[row]},self.act,errors)['ok'])
        self.assertFalse(audit_v3.cutout_overlays_gate({'shots':[dict(row,aux_files=[])]},self.act,[])['ok'])
        stage.write_project(self.act)
        self.assertFalse(audit_v3.subzone_gate(self.act,[])['violations'])

    def test_title_logo_corner_logo_and_original_asset_collection(self):
        old = self.build(self.shot('title_sequence')).shots[0]
        self.assertEqual(old['files'],[])
        self.assertNotIn('aux_files',old)
        new = self.build(self.shot('title_sequence',logo='brand.svg')).shots[0]
        self.assertEqual(new['files'],['assets/demo-logo.svg'])
        callout = self.build(self.shot('callout_rig',source='motion.gif',
                                      overlays=[dict(kind='corner_tag',at=.15,label='实证',logo='brand.svg')]))
        self.assertEqual(callout.shots[0]['aux_files'],['assets/demo-overlay-0-logo.svg'])
        self.assertIn('<image x="102"',callout.plates[-1])
        self.assertIn('<text x="148"',callout.plates[-1])
        self.assertEqual(audit_v7.primary_files(callout.shots[0]),['assets/demo-0.mp4'])

    def test_evidence_svg_and_video_audit_and_invalid_box(self):
        image = self.build(self.shot('evidence_spotlight',source='brand.svg'))
        self.assertEqual(image.shots[0]['files'],['assets/demo-0.svg'])
        self.assertNotIn('evidence-stripe',''.join(image.media_layers))
        self.assertEqual(next(image.sound_events())['kind'],'pop')
        video = self.build(self.shot('evidence_spotlight',source='motion.gif'))
        self.assertTrue(audit_v7.is_real_shot(video.shots[0]))
        self.assertEqual(video.shots[0]['kind'],'real_video')
        self.assertIn('assets/demo-0.mp4',video.shots[0]['gif_source_hashes'])
        row = self.shot('evidence_spotlight',source='motion.gif')
        manifest = self.root/'manifest.json'
        manifest.write_text(json.dumps({'shots':[row],'cues':[]}))
        proofs, = scout.make_verification_rows(manifest)
        self.assertLessEqual(max(proofs['times']),.36)
        with self.assertRaisesRegex(ValueError,'超出'):
            self.build(self.shot('evidence_spotlight',source='brand.svg',highlight_box=[1880,500,100,45]))
        with self.assertRaisesRegex(ValueError,'尺寸'):
            self.build(self.shot('evidence_spotlight',source='brand.svg',
                                 overlays=[dict(kind='reaction_cutout',source='plate.webp',at=.8,size=300)]))


if __name__ == '__main__':
    unittest.main()
