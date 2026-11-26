import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from PIL import Image, ImageDraw

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT.parent), str(KIT/'scripts')]

from cutout import paper_cutout, validate_subject_mask
from kit.editorial.editorial import EditorialStage
from workspace import ONETAKE_COLORS, onetake_look

assemble = importlib.import_module('assemble-episode')
bridge = importlib.import_module('render-onetake-clip')
palette = importlib.import_module('visual-palette')
scout = importlib.import_module('scout-video-scenes')


class DiversityAndGuardsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = self.root/'onetake'
        self.animation = self.root/'animation'
        for path in (self.runtime/'lib',self.runtime/'looks',self.runtime/'scripts',self.animation/'transitions'):
            path.mkdir(parents=True)
        self.preset = dict(color={name:f'#{i:06x}' for i,name in enumerate(ONETAKE_COLORS)},
                           mood='示例',type={role:dict(tracking=0) for role in ('display','text','mono')})
        (self.runtime/'looks/looks.json').write_text(json.dumps(dict(looks={'paper':self.preset})))
        (self.runtime/'lib/motion.js').write_text('window.OM={}\n *   enter    wordRise · letterDrop\n'
                                                 ' *   contact  press · sim.{magnet, follow, jelly, verlet}\n')
        (self.runtime/'lib/ui_kit.js').write_text('window.UIK={}\n')
        (self.animation/'blueprints-index.md').write_text(
            '<blueprint id="cursor-ui-demo" roles="Hook, Key_Feature" duration="4–8s">浏览产品</blueprint>\n'
            '<blueprint id="end" roles="Brand_Outro" duration="3–5s">品牌片尾</blueprint>')
        (self.animation/'rules-index.md').write_text('<3d-flight path="rules/3d-flight.md">进入视窗</3d-flight>')
        (self.animation/'transitions/catalog.md').write_text('| Push | Whip pan, Vertical push | `transitions/css-push.md` |')

    def test_subject_mask_rejects_border_and_paper_slabs(self):
        slab = Image.new('L',(60,60))
        ImageDraw.Draw(slab).rectangle((0,0,59,45),fill=255)
        with self.assertRaisesRegex(ValueError,'抠图未分离出独立主体'):
            validate_subject_mask(slab)
        dense_corner = Image.new('L',(60,60))
        ImageDraw.Draw(dense_corner).rectangle((0,0,33,28),fill=255)
        with self.assertRaisesRegex(ValueError,'大面积背景底板'):
            validate_subject_mask(dense_corner)
        valid_corner = Image.new('L',(60,60))
        ImageDraw.Draw(valid_corner).line((0,29,28,0),fill=255,width=4)
        validate_subject_mask(valid_corner)
        rgba = Image.new('RGBA',slab.size,'white')
        rgba.putalpha(slab)
        self.assertIsNotNone(paper_cutout(rgba,allow_edge_bleed=True).getbbox())

    def test_video_overlay_ocr_finds_text_entering_at_midpoint(self):
        row = dict(id='verify-focus',source='clip.mp4',media_start=.5,play_span=5.,
                   viewport=(0,0,1920,1080),overlays=[dict(kind='prop_badge',at=.8,duration=4.0,
                       side='left',placement='foreground_hero',size=380,label='卡尺')])
        before = [dict(text='别处文字',box=[1400,530,50,42])]
        obscured = dict(text='把想要的东西说清楚',box=[399,541,860,92])
        with patch.object(scout,'overlay_ocr',side_effect=[before,[obscured],before]) as ocr:
            hits,unavailable = scout.overlay_text_check(row,self.root/'clip.mp4')
        self.assertEqual([call.args[1] for call in ocr.call_args_list],[1.3,3.3,5.26667])
        self.assertFalse(unavailable)
        self.assertEqual(len(hits),1)
        self.assertEqual((hits[0]['sample'],hits[0]['text']),('中',obscured['text']))
        self.assertEqual(hits[0]['overlay_box'],[42,434,380,422])

    def test_stat_badge_must_leave_dense_quadrant_heading_visible(self):
        import audit_v7
        cells = [dict(text='正文',box=[x,y+dy,80,18])
                 for x,y in [(270,190),(1100,190),(270,620),(1100,620)] for dy in (0,50,90)]
        heading = dict(text='37 个文本框',box=[1540,108,150,30])
        stat = dict(kind='stat_badge',at=.3)
        row = dict(id='four',source='proof.mp4',media_start=0,play_span=4,overlays=[stat],
                   viewport=(0,0,1920,1080))
        with patch.object(scout,'overlay_ocr',return_value=cells+[heading]):
            hits, missing = scout.overlay_text_check(row,self.root/'proof.mp4')
        self.assertFalse(missing)
        self.assertEqual([h['text'] for h in hits],[heading['text']]*3)
        self.assertTrue(all(h['severity']=='error' for h in hits))
        self.assertEqual(audit_v7.quadrant_heading_hits(cells,row['viewport']),[])
        self.assertEqual(audit_v7.quadrant_heading_hits([heading],row['viewport']),[])
        real_reader = audit_v7.stat_badge_occlusions
        def read_fixture(row,source,overlay):
            return real_reader(row,source,overlay,reader=lambda *args:cells+[heading])
        shot=dict(row,start=0,end=4,stage_mode='callout_rig',files=['proof.mp4'])
        with patch.object(audit_v7,'stat_badge_occlusions',side_effect=read_fixture):
            self.assertFalse(audit_v7.quadrant_overlay_gate([shot],self.root)['ok'])
            self.assertTrue(audit_v7.quadrant_overlay_gate([dict(shot,overlays=[])],self.root)['ok'])

    def test_onetake_look_from_shot_and_local_injection(self):
        source = self.root/'product.png'
        Image.new('RGB',(40,30),'lavender').save(source)
        output = self.root/'product.json'

        def extract(cmd, **kwargs):
            self.assertIn('from-shot',cmd)
            self.assertIn(str(source),cmd)
            Path(cmd[-1]).write_text(json.dumps(dict(self.preset,name='product')))
            return subprocess.CompletedProcess(cmd,0)

        with patch('workspace.subprocess.run', side_effect=extract):
            look = onetake_look(self.runtime,'paper',shots=[source],output=output)
        entry = self.root/'composition'/'comp.html'
        entry.parent.mkdir()
        entry.write_text('<!doctype html><head></head><body></body>')
        folder = self.root/'staged'
        staged = bridge.stage_composition(entry,folder,self.runtime,look=look)
        self.assertIn('look-tokens.css',staged.read_text())
        self.assertIn('lib/ui_kit.js',staged.read_text())
        self.assertTrue((folder/'lib/ui_kit.js').is_file())
        css = (folder/'look-tokens.css').read_text()
        self.assertTrue(all(f'--{key}:' in css for key in ONETAKE_COLORS))
        js = (folder/'look-tokens.js').read_text()
        self.assertIn('window.LOOK=',js)
        self.assertIn('LOOK.ready=',js)
        self.assertIn('Source Han Serif CN',js)

    def test_visual_palette_commands_and_role_filter(self):
        target = self.root/'generated.json'
        screenshot = self.root/'screen.png'
        screenshot.touch()
        with patch.object(palette,'resolve_onetake',return_value=self.runtime), \
             patch.object(palette,'animation_directory',return_value=self.animation), \
             patch.object(palette,'search_registry',return_value={'total':1}), \
             patch.object(palette,'onetake_look',return_value=self.preset):
            cases = [
                (['--list-looks'],lambda value: 'paper' in value['onetake'] and len(value['stage'])==5),
                (['--list-blueprints','--role','Hook'],lambda value: [item['id'] for item in value]==['cursor-ui-demo']),
                (['--list-rules'],lambda value: value[0]['id']=='3d-flight'),
                (['--list-transitions'],lambda value: value[0]['moves'][0]=='Whip pan'),
                (['--list-onetake-moves'],lambda value: 'sim.magnet' in [row['id'] for row in value]),
                (['--search-registry','rolling number'],lambda value: value['total']==1),
                (['--from-shot',str(screenshot),'--output',str(target)],lambda value: len(value['color'])==8),
            ]
            for arguments, predicate in cases:
                with self.subTest(arguments=arguments), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(palette.main([*arguments,'--json']),0)
                    self.assertTrue(predicate(json.loads(output.getvalue())))

    def test_modern_triptych_keeps_pine_structure(self):
        cards = [dict(label='样片',source=f'asset-{index}.png',reveal_at=index*.24) for index in range(3)]
        modern,old = (EditorialStage('验证',4.) for _ in range(2))
        modern.add_triptych_cards(0.,4.,heading='实证对照',cards=cards,theme='aurora_indigo')
        old.add_triptych_cards(0.,4.,heading='实证对照',cards=cards)
        html = modern.render_visual_layers()
        self.assertIn('glass-0-surfaces',html)
        self.assertIn('border-radius:14px',html)
        self.assertIn('>03</text>',html)
        self.assertIn('card-glint',html)
        self.assertNotIn('drop-shadow',html)
        self.assertNotIn('glass-0-surfaces',old.render_visual_layers())
        self.assertIn('stroke-dasharray="8 10"',old.render_visual_layers())


if __name__=='__main__':
    unittest.main()
