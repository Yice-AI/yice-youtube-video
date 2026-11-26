"""Phase 3 画面、字幕、母带和草稿入口的离线验证。"""
import importlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(KIT/'scripts'))
assemble = importlib.import_module('assemble-episode')
audit = importlib.import_module('audit_v7')
voice = importlib.import_module('voice')
scout = importlib.import_module('scout-video-scenes')
from kit.editorial.audio_mix import EpisodeAudioMixer
from kit.editorial.editorial import EditorialStage, FONT_FILES, PALETTES
from kit.studio_ui import _code, _terminal


def fixture_head(index, theme, start, end):
    return dict(id=f'shot-{index}',anchor_cue_id=str(index),start=start,end=end,stage_mode='title_sequence',
                theme=theme,spoken_topic='镜头题目',visual_subject='片头扉页',semantic_tags=['片头'],
                semantic_binding='conceptual_explainer',title='新阶段开始')


class Phase3Tests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def test_palettes_asset_links_and_mask(self):
        shots = [fixture_head(i,theme,i*2.,(i+1)*2.) for i,theme in enumerate(PALETTES)]
        shots[1]['subtitle'] = '原始颜色 #172322'
        cues = {str(i):{'firstCharTime':s['start']} for i,s in enumerate(shots)}
        rows,_ = assemble.prepare_shots({'shots':shots},self.root,cues)
        stage = assemble.build_act(rows,self.root,self.root,'四色板',subprocess.run)
        for i,(theme,palette) in enumerate(PALETTES.items()):
            self.assertIn(palette['ink'],stage.plates[i])
            self.assertIn(palette['bg'] if theme=='pine' else palette['gradient'],stage.bg_layers[i])
        self.assertEqual(stage.light_zones,[(i*2.,(i+1)*2.) for i,palette in enumerate(PALETTES.values())
                                           if palette['is_light']])
        self.assertIn('原始颜色 #172322',stage.plates[1])
        self.assertIn('#172322fa',PALETTES['pine']['panel'])
        self.assertIn('<clipPath',stage.plates[0])
        self.assertIn("ease:'expo.out'",''.join(stage.scripts))
        stage.font_assets = assemble.install_fonts(self.root)
        self.assertTrue(stage.font_assets)
        for name in FONT_FILES:
            self.assertTrue((self.root/'assets/fonts'/name).samefile(KIT/'template/assets/fonts'/name))
        stage.write_project(self.root)
        html = (self.root/'index.html').read_text()
        self.assertIn("@font-face",html)
        self.assertIn('unicode-range',html)

    def test_breathing_camera_and_verified_marks_share_focus(self):
        mark = dict(kind='highlighter_sweep',at=.6,box=[390,280,250,68],
                    target_verified=True,target_note='说明文本')
        stage = EditorialStage('核验',4)
        stage.add_callout_rig(0,4,'clip.mp4',motion='focus_push',overlays=[mark])
        scripts = [row for row in stage.scripts if "transformOrigin:'515.0px 314.0px'" in row]
        self.assertEqual(len(scripts),4)
        self.assertEqual(scripts[0].split(',{scale:',1)[1],scripts[2].split(',{scale:',1)[1])
        self.assertEqual(scripts[1].split(',{scale:',1)[1],scripts[3].split(',{scale:',1)[1])
        self.assertIn("duration:0.65000,ease:'power3.out'",scripts[0])
        self.assertIn("duration:3.35000,ease:'sine.out'",scripts[1])
        self.assertIn('rgba(255,212,59,0.26)',''.join(stage.plates))
        short = EditorialStage('短镜',1)
        circle = dict(mark,kind='hand_circle',at=.1)
        short.add_callout_rig(0,1,'clip.mp4',motion='spring_glide',overlays=[circle])
        self.assertEqual(''.join(short.plates).count('class="verified-circle"'),2)
        self.assertIn("ease:'power2.out'",short.scripts[0])
        self.assertEqual(next(short.sound_events())['kind'],'marker')
        self.assertFalse(audit.spotlight_restraint_gate([
            dict(id='a',overlays=[mark]),dict(id='b',overlays=[circle]),
        ])['ok'])
        video = self.root/'clip.mp4'
        video.touch()
        manifest = self.root/'shots.json'
        manifest.write_text(json.dumps({'shots':[dict(id='a',source=video.name,start=0,end=1,
                         stage_mode='callout_rig',overlays=[mark,circle])]}))
        self.assertEqual(scout.make_verification_rows(manifest)[0]['spotlight_boxes'],[mark['box'],circle['box']])

    def test_captions_split_at_light_boundary_and_band_detection(self):
        for name,color in [('bright','0xf0eee3'),('dark','0x161c22')]:
            target = self.root/f'{name}.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color={color}:s=320x180:r=30:d=2.5',
                            '-c:v','libx264',str(target)],check=True)
        self.assertTrue(assemble.bright_caption_band(self.root/'bright.mp4',.8))
        self.assertFalse(assemble.bright_caption_band(self.root/'dark.mp4',.8))
        shots = [dict(fixture_head(i,'pine',i*2,(i+1)*2),stage_mode='fullbleed_rig',motion='hold',
                      source=f'{name}.mp4') for i,name in enumerate(('dark','bright'))]
        rows,_ = assemble.prepare_shots({'shots':shots},self.root,{'0':{'firstCharTime':0},'1':{'firstCharTime':2}})
        stage=assemble.build_act(rows,self.root,self.root,'换底',subprocess.run)
        self.assertEqual(stage.light_zones,[(2.,4.)])
        stage.add_captions([dict(start=1.6,end=2.6,text='跨镜短句')])
        self.assertEqual(len(stage.captions),2)
        self.assertIn('data-duration="0.40000"',stage.captions[0])
        self.assertIn('cap caption-on-light',stage.captions[1])
        self.assertIn('data-start="2.00000"',stage.captions[1])

    def test_studio_window_keeps_footage_mark_and_caption_separate(self):
        stage = EditorialStage('暗场实录',4)
        before = (0,0)
        stage.add_callout_rig(0,4,'capture.mp4',framing='studio_window',window_title='真实网页',
            motion='focus_push',overlays=[
                dict(kind='highlighter_sweep',at=.5,box=[240,300,300,70],
                     target_verified=True,target_note='核对标题'),
                dict(kind='corner_tag',at=.6,label='官网',sublabel='网页实录'),
            ])
        stage.apply_palette('aurora_indigo',0,4,before)
        self.assertIn('#1F1D42',stage.bg_layers[0])
        self.assertIn('x="144" y="122" width="1648" height="760"',stage.bg_layers[1])
        self.assertIn('left:136px;top:142px;width:1648px;height:726px',stage.media_layers[0])
        chrome,mark,corner = stage.plates
        self.assertIn('stroke-width="1.5"',chrome)
        self.assertIn('真实网页',chrome)
        self.assertNotIn('drop-shadow',chrome)
        self.assertIn('class="studio-mark-plane"',mark)
        self.assertIn('x="136" y="34"',corner)
        camera = [s for s in stage.scripts if "transformOrigin:'334.8px 187.0px'" in s]
        self.assertEqual(len(camera),4)
        self.assertEqual(camera[0].split(',{scale:',1)[1],camera[2].split(',{scale:',1)[1])
        stage.light_zones.append((0,4))
        stage.add_captions([dict(start=.5,end=2,text='字幕在视窗下方')])
        stage.write_project(self.root)
        html = (self.root/'index.html').read_text()
        self.assertIn('background:rgba(13,18,26,.90)',html)
        self.assertIn('color:#f8fafc',html)
        self.assertNotIn('rgba(255,250,240,.94)',html)
        self.assertIn('cap caption-on-light',stage.captions[0])

    def test_light_theme_preserves_dark_studio_panels(self):
        shot = dict(fixture_head(0,'paper_cool',0,3),stage_mode='studio_ui',
                    studio_style='terminal_pipeline',data=dict(command='git status',lines=['已核对']))
        rows,_ = assemble.prepare_shots({'shots':[shot]},self.root,{'0':{'firstCharTime':0}})
        stage = assemble.build_act(rows,self.root,self.root,'深色终端',subprocess.run)
        self.assertIn('#0F1419',PALETTES['obsidian']['bg'])
        self.assertIn('#18222E',PALETTES['obsidian']['panel'])
        self.assertIn('#252e33',stage.plates[0])
        self.assertIn('#e7e9df',stage.plates[0])
        self.assertNotIn('#FFFFFFf5',stage.plates[0])
        self.assertEqual(stage.light_zones,[])

    def test_timed_short_subtitles_and_manifest_priority(self):
        text='先看画面的颜色和排版然后顺手标出需要反向核对的几个相关位置，第二句话。'
        chapter=dict(text=text,scenes=[dict(text=text)])
        mapped=[dict(charStart=i,charEnd=i+1,s=j*.10,e=j*.10+.08) for j,(i,_) in enumerate(voice.chars(text))]
        rows=voice.short_captions(chapter,mapped,.4)
        self.assertGreaterEqual(len(rows),3)
        self.assertEqual(rows[0]['startMs'],400)
        self.assertEqual(''.join(row['text'] for row in rows),text.replace('，','').replace('。',''))
        self.assertTrue(all(len(row['text'])<=22 for row in rows))
        (self.root/'voice.wav').touch()
        (self.root/'voice-manifest.json').write_text(json.dumps({'chapters':[dict(id='0',path='voice.wav',start=0)]}))
        (self.root/'captions.json').write_text(json.dumps(rows))
        raw=dict(voice_manifest='voice-manifest.json',cues=[dict(id='0',text='旧字幕',firstCharTime=0,end=1)])
        self.assertEqual(assemble.prepare_document(raw,self.root)[2][0]['text'],rows[0]['text'])
        self.assertEqual(assemble.prepare_document(dict(raw,captions=raw['cues']),self.root)[2][0]['text'],'旧字幕')

    def test_audio_seams_and_effect_master(self):
        rate=24000
        mixer=EpisodeAudioMixer(sample_rate=rate)
        source=np.linspace(-.3,.3,rate*6)
        repeated=mixer._loop_music(source,rate*17)
        self.assertEqual(len(repeated),17*rate)
        self.assertLess(float(np.max(np.abs(np.diff(repeated)))),.001)
        for name in ('tick','whoosh','stamp','pop','marker'):
            waveform=mixer._effect(name)
            self.assertTrue(np.isfinite(waveform).all())
            self.assertAlmostEqual(float(np.max(np.abs(waveform))),1.)
            self.assertEqual((waveform[0],waveform[-1]),(0,0))
        voice_file=self.root/'voice.wav'
        sf.write(voice_file,.08*np.sin(2*np.pi*246*np.arange(rate*4)/rate),rate)
        music=self.root/'music.wav'
        sf.write(music,source[:rate*2],rate)
        mix=mixer.mix(4,[dict(path=voice_file)],self.root/'mix',bgm=[music],
                      sound_marks=[dict(kind=name,at=.28*i) for i,name in enumerate(('tick','marker','whoosh','pop','stamp'))])
        self.assertLessEqual(abs(mix['measured_lufs']+14.5),.8)
        self.assertLessEqual(mix['true_peak_dbtp'],-1)

    def test_scaffold_shell_and_custom_entities(self):
        (self.root/'voice.wav').touch()
        voice_manifest=self.root/'voice-manifest.json'
        voice_manifest.write_text(json.dumps(dict(total_duration=4,chapters=[dict(id='0',start=0,path='voice.wav')])))
        timing=self.root/'voice-timing.json'
        timing.write_text(json.dumps([dict(id='a',firstCharTime=.049,end=1.44,text='开场'),
                                      dict(id='b',firstCharTime=1.963,end=3.7,text='第二段')]))
        target=self.root/'episode-manifest.json'
        subprocess.run([str(KIT/'scripts/scaffold-manifest.sh'),'--voice-manifest',str(voice_manifest),
                        '--voice-timing',str(timing),'--output',str(target)],check=True,capture_output=True)
        raw=json.loads(target.read_text())
        _,cues,_=assemble.prepare_document(raw,self.root)
        shots,duration=assemble.prepare_shots(raw,self.root,cues)
        self.assertEqual((duration,shots[0]['start'],shots[1]['start']),(4.,0.,59/30))
        real=dict(id='a',stage_mode='fullbleed_rig',spoken_topic='打开 Polaris',visual_subject='其他界面',
                  semantic_tags=['其他画面'],semantic_binding='exact_tool_capture')
        self.assertFalse(audit.semantic_binding_gate([real],{'Polaris':['北极星']})['ok'])
        self.assertTrue(audit.semantic_binding_gate([dict(real,visual_subject='北极星窗口',semantic_tags=['Polaris'])],
                                                    {'Polaris':['北极星']})['ok'])

    def test_studio_focus_and_readable_long_lines(self):
        line='git show --stat --pretty=fuller ' + 'x'*54
        longer='视图层状态'*40
        code=_code(dict(tree=['main.py'],file='main.py',lines=[line,longer],status='Ready',focus_lines=[2]))
        terminal=_terminal(dict(command='git status',lines=[line,longer],focus_lines=[1]))
        for markup in (code,terminal):
            self.assertIn(line,markup)
            self.assertIn('…',markup)
            self.assertIn('opacity=".17"',markup)
            self.assertNotIn(longer,markup)

    @unittest.skipUnless(shutil.which('uv'),
                         '需要本机离线 Playwright 与 Chrome')
    def test_featured_board_and_architecture_audit(self):
        samples=[
            dict(grammar='t7_editorial_board',theme='bauhaus',data=dict(title='先确定证据的用途',layout='featured',eyebrow='编辑部看板'),
                 cues=[dict(at=.1,kind='card',text='原文和实录配对',sub='同一时间窗内保留对象',data=dict(badge='01',bad='孤立截图',good='展示上下文',tag='核心')),
                       dict(at=.6,kind='card',text='确认引用来源',sub='记录页面与采集日期',
                            data=dict(bad='只存缩略图',good='保留页面原址',tag='来源')),
                       dict(at=1.1,kind='card',text='核对音画',sub='首字切点与字幕入点逐一对应',
                            data=dict(bad='靠感觉切换',good='按首字核对',tag='对齐')),
                       dict(at=1.6,kind='footer',text='为编辑和复核保留同一份材料')]),
            dict(grammar='t4_blueprint_arch',theme='navy',data=dict(title='架构信号流',eyebrow='输入到输出'),
                 cues=[dict(at=.08,kind='step',text='网页采集',sub='源页与坐标',data=dict(stage='01 采集')),
                       dict(at=.6,kind='point',text='规格归一',sub='格式与时长',data=dict(stage='02 转换')),
                       dict(at=1.1,kind='step',text='镜头编排',sub='时间轴依赖',data=dict(stage='03 装配')),
                       dict(at=1.5,kind='point',text='审片输出',sub='音画指标',data=dict(stage='04 验收'))]),
        ]
        for i,config in enumerate(samples):
            with self.subTest(grammar=config['grammar']):
                spec=self.root/f'sample-{i}.json'
                report=self.root/f'audit-{i}.json'
                spec.write_text(json.dumps(dict(config,width=1920,height=1080,duration=2.5,fps=30,
                                                 safe=dict(top=56,bottom=172)),ensure_ascii=False))
                run=subprocess.run(['uv','run','--offline','--with','playwright','python3',
                                    str(KIT/'explainer/render.py'),'--spec',str(spec),'--audit',str(report)],
                                    env=os.environ.copy(),
                                    text=True,capture_output=True,timeout=100)
                self.assertEqual(run.returncode,0,run.stderr+run.stdout)
                data=json.loads(report.read_text())
                self.assertEqual((data['red'],data['yellow']),([],[]),run.stdout)


if __name__=='__main__':
    unittest.main()
