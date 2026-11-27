import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

TEMPLATE=Path(__file__).parents[1]/'template'


class AutoSfxTests(unittest.TestCase):
    def test_skill_reports_bundled_audio_file_count(self):
        kit = TEMPLATE.parent
        count = len(list((kit / 'assets/sfx').glob('*.mp3')))
        descriptions = re.findall(r'(\d+) 款(?:专业)?真实动作音效', (kit.parent / 'SKILL.md').read_text())
        self.assertTrue(descriptions, '请在 Skill 说明中标明内置音效数量')
        self.assertEqual(set(descriptions), {str(count)}, '请按内置 MP3 文件数更新 Skill 说明')

    def node(self,body,data=None):
        code=f"import fs from 'node:fs';import path from 'node:path';import {{execFileSync}} from 'node:child_process';import * as s from {json.dumps((TEMPLATE/'auto-sfx.mjs').as_uri())};import * as audio from {json.dumps((TEMPLATE/'audio.mjs').as_uri())};const input=JSON.parse(fs.readFileSync(0,'utf8'));"+body
        result=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(data),capture_output=True,text=True,env={**os.environ,'YICE_MEDIA_OFFLINE':'1'})
        self.assertEqual(result.returncode,0,result.stderr[-2000:]);return json.loads(result.stdout)

    def test_semantic_events_cover_all_five_kinds(self):
        scenes=[{'id':'a','start':1,'end':5,'enter':'wipe','recipe':'bar-compare'}, {'id':'b','start':5,'end':8,'recipe':'chat-bubble','props':{'turns':[{'at':.2},{'at':1.4}]}}, {'id':'c','start':8,'end':11,'recipe':'paper-break','props':{'highlight':[{}]}}]
        d=self.node('console.log(JSON.stringify(s.planAutoSfx(input)));',scenes)
        self.assertEqual({e['name'] for e in d},{'whoosh','tick','pop','thump','swipe'})
        self.assertTrue(next(e for e in d if e['name']=='thump')['key'])
        self.assertTrue(all(e['time']<11 for e in d))

    def test_hard_cut_does_not_add_whoosh_and_density_is_deterministic(self):
        d=self.node("const scenes=Array.from({length:20},(_,i)=>({id:'s'+i,start:i*3,end:i*3+3,enter:'cut',recipe:'bar-compare'}));console.log(JSON.stringify({all:s.planAutoSfx(scenes),half:s.planAutoSfx(scenes,{density:.5}),again:s.planAutoSfx(scenes,{density:.5}),off:s.planAutoSfx(scenes,{density:0})}));")
        self.assertNotIn('whoosh',[e['name'] for e in d['all']]);self.assertEqual(d['half'],d['again']);self.assertEqual(d['off'],[])
        self.assertGreater(len(d['half']),0);self.assertLess(len(d['half']),len(d['all']))

    def test_repeat_spacing_crosses_scene_boundaries_and_aliases(self):
        d=self.node("console.log(JSON.stringify(s.spaceSfx([{name:'pop',src:'same.wav',scene:'a',time:0},{name:'click',src:'same.wav',scene:'b',time:.999},{name:'pop',src:'same.wav',scene:'b',time:1},{name:'tick',src:'other.wav',time:.1}])));")
        self.assertEqual([e['time'] for e in d['events']],[0,.1,1]);self.assertEqual(len(d['dropped']),1)

    def test_explicit_beats_override_inference_and_can_disable_scene(self):
        d=self.node("console.log(JSON.stringify(s.planAutoSfx([{id:'a',start:0,end:2,recipe:'bar-compare',sfx:[{name:'thump',at:.7}]},{id:'b',start:2,end:4,recipe:'chat-bubble',props:{turns:[{}]},sfx:false}])));")
        self.assertEqual([(e['name'],e['time']) for e in d],[('thump',.7)])

    def test_stack_spacing_and_zip_landing_follow_the_visual_beats(self):
        result=self.node("const events=s.planAutoSfx([{id:'stack',start:0,end:5,recipe:'cutout-stack',props:{items:Array(25).fill({}),stagger:.15}},{id:'zip',start:5,end:7,recipe:'paper-break',props:{changeAt:.15,changeDuration:1}}]);console.log(JSON.stringify(s.spaceSfx(events))); ")
        pop=[e['time'] for e in result['events'] if e['name']=='pop']
        self.assertTrue(all(b-a>=1 for a,b in zip(pop,pop[1:])))
        self.assertAlmostEqual(next(e['time'] for e in result['events'] if e['name']=='thump'),6.03)

    def test_bad_density_times_and_names_fail(self):
        d=self.node("const failures=[];for(const [scenes,options] of [[[{id:'bad',start:0,end:2}],{density:1.1}],[[{id:'bad',start:2,end:1}],{}],[[{id:'bad',start:0,end:2,sfx:[{name:'unknown',at:0}]}],{}]])try{s.planAutoSfx(scenes,options);}catch(e){failures.push(e.message);}console.log(JSON.stringify(failures));")
        self.assertEqual(len(d),3)

    def test_disabled_preserves_existing_manual_events(self):
        d=self.node("console.log(JSON.stringify(s.prepareAutoSfx({root:'/unused',scenes:[],config:{},manualEvents:[{name:'stamp',time:1}]})));")
        self.assertEqual(d['events'],[{'name':'stamp','time':1}]);self.assertFalse(d['enabled'])

    def test_copy_ledger_and_real_mix_use_existing_level_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.node("const root=input;fs.mkdirSync(path.join(root,'bank'));for(const [i,name] of Object.keys(s.AUTO_SFX_FILES).entries())execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','sine=frequency='+(400+i*100)+':duration=0.12','-y',path.join(root,'bank',s.AUTO_SFX_FILES[name])]);const config={sfx_dir:'bank',auto_sfx:{enabled:true},voice_lufs:-16,segments:{}};const scene={id:'a',start:0,end:3,B:0,E:3,sfx:Object.keys(s.AUTO_SFX_FILES).map((name,i)=>({name,at:.1+i*.5}))};const resolve=src=>path.resolve(root,src),plan=s.prepareAutoSfx({root,scenes:[scene],config,resolve});audio.mixAudio({root,config,manifest:{chapters:[]},timing:[],scenes:[scene],end:3,voiceDir:root,resolve,events:plan.events});const report=JSON.parse(fs.readFileSync(path.join(root,'audio-report.json')));console.log(JSON.stringify({plan,report,rows:fs.readFileSync(path.join(root,'asset-ledger.jsonl'),'utf8').trim().split(String.fromCharCode(10)).map(JSON.parse),master:fs.existsSync(path.join(root,'assets/audio/master.wav'))}));",tmp)
            self.assertTrue(d['master']);self.assertEqual(len(d['rows']),5);self.assertEqual(len(d['plan']['events']),5)
            self.assertEqual(d['report']['samples'],144000)
            for event in d['report']['events']:
                import math
                expected=-16-(12 if event['key'] else 18)-event['inputLufs']+(-2.3 if event['key'] else -1)
                self.assertAlmostEqual(20*math.log10(event['gain']),expected,places=5)
            self.assertTrue(all('未声明CC0' in row['license'] for row in d['rows']))


if __name__=='__main__':unittest.main()
