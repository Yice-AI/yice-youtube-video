import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

TEMPLATE=Path(__file__).parents[1]/'template'


def fixture():
    return {'scenes':[{'id':'A'},{'id':'B'}], 'frames':{'visualChange':{'eventsPerSecond':.45},'scenes':[{'id':name,'frames':60,'longestStillSeconds':2.5,'stillRuns':[{'start':0,'end':2.5,'seconds':2.5}]} for name in ['A','B']]},'media':{'realRatio':.3},'probe':{'camera':[{'id':'A','moving':True},{'id':'B','moving':False}],'readings':[{'scene':'A','region':'headline','effectiveTextHeightPx':28}]}}


class CinemaTests(unittest.TestCase):
    def node(self,body,data=None):
        code="import fs from 'node:fs';import path from 'node:path';"+f"import * as c from {json.dumps((TEMPLATE/'check-cinema.mjs').as_uri())};import * as f from {json.dumps((TEMPLATE/'cinema-frames.mjs').as_uri())};import * as p from {json.dumps((TEMPLATE/'cinema-probe.mjs').as_uri())};const input=JSON.parse(fs.readFileSync(0,'utf8'));"+body
        result=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(data),capture_output=True,text=True,env={**os.environ,'YICE_MEDIA_OFFLINE':'1'})
        self.assertEqual(result.returncode,0,result.stderr[-2000:]);return json.loads(result.stdout)

    def evaluate(self,data):return self.node('console.log(JSON.stringify(c.evaluateCinema(input)));',data)

    def test_exact_three_boundaries_pass(self):
        self.assertTrue(self.evaluate(fixture())['ok'])

    def test_still_over_limit_reports_scene_and_interval(self):
        data=fixture();row=data['frames']['scenes'][0];row.update(longestStillSeconds=2.6,stillRuns=[{'start':1,'end':3.6,'seconds':2.6}]);result=self.evaluate(data)
        self.assertEqual([r['code'] for r in result['findings']],['shot_still_too_long']);self.assertEqual(result['findings'][0]['scenes'],['A'])

    def test_effective_read_height_not_source_font_size(self):
        data=fixture();data['probe']['readings'][0]['effectiveTextHeightPx']=27.99;result=self.evaluate(data)
        self.assertEqual(result['findings'][0]['code'],'read_text_too_small');self.assertIn('zoom/crop',result['findings'][0]['message'])

    def test_camera_ratio_counts_shots_not_duration(self):
        data=fixture();data['probe']['camera'][0]['moving']=False;result=self.evaluate(data)
        self.assertEqual(result['metrics']['noCameraRatio'],1);self.assertEqual(result['findings'][0]['scenes'],['A','B'])

    def test_unmeasured_reading_region_is_not_a_pass(self):
        data=fixture();data['probe']['readings'][0]={'scene':'A','region':'body','error':'区域不可见'}
        self.assertEqual(self.evaluate(data)['findings'][0]['code'],'readability_unmeasured')

    def test_slow_visible_change_accumulates_instead_of_false_static(self):
        d=self.node("const tracker=f.stillTracker([{id:'A',B:0,E:4}],{width:32,height:18});for(let i=0;i<40;i++)tracker.push(Buffer.alloc(32*18,30+i),i/10);console.log(JSON.stringify(tracker.finish()[0]));")
        self.assertLess(d['longestStillSeconds'],1.2);self.assertGreaterEqual(len(d['changes']),3)

    def test_hud_and_low_noise_do_not_reset_static_clock(self):
        d=self.node("const tracker=f.stillTracker([{id:'A',B:0,E:3}],{width:100,height:100});for(let i=0;i<72;i++){const frame=Buffer.alloc(10000,50+i%2*2);for(let y=96;y<100;y++)frame.fill(i%2*200,y*100,(y+1)*100);tracker.push(frame,i/24);}console.log(JSON.stringify(tracker.finish()[0]));")
        self.assertEqual(d['longestStillSeconds'],3);self.assertEqual(d['changes'],[])

    def test_camera_uses_sampled_transform_delta(self):
        d=self.node("const samples=x=>[{time:.55,transforms:[{id:'cam',x:0,y:0,sx:1,sy:1}]},{time:1.5,transforms:[{id:'cam',x,y:0,sx:1,sy:1}]}];console.log(JSON.stringify({static:p.cameraMotion(samples(0)),moving:p.cameraMotion(samples(3))}));")
        self.assertFalse(d['static']['moving']);self.assertTrue(d['moving']['moving'])

    def test_limits_are_configurable_and_validated(self):
        data=fixture();data['probe']['readings'][0]['effectiveTextHeightPx']=20;data['limits']={'minReadTextPx':20};self.assertTrue(self.evaluate(data)['ok'])
        d=self.node("try{c.cinemaLimits({maxNoCameraRatio:1.1});}catch(e){console.log(JSON.stringify(e.message));}");self.assertIn('超出范围',d)

    def test_actual_video_frames_and_missing_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'still.mp4';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=gray:s=256x144:r=24:d=1.5','-c:v','libx264','-y',str(file)],check=True,capture_output=True)
            d=self.node("const valid=await f.analyzeRendered(input,[{id:'A',B:0,E:1.5}]);let error;try{await f.analyzeRendered(input,[{id:'A',B:0,E:3}]);}catch(e){error=e.message;}console.log(JSON.stringify({valid,error}));",str(file))
            self.assertEqual(d['valid']['frames'],36);self.assertEqual(d['valid']['scenes'][0]['longestStillSeconds'],1.5);self.assertIn('没有覆盖',d['error'])

    def browser_fixture(self,root,duration=2):
        (root/'assets').mkdir(exist_ok=True);(root/'compositions/scenes').mkdir(parents=True,exist_ok=True)
        for file in ['frame.css','vocab.css','yice.js','vocab.js']:(root/'assets'/file).write_text('')
        (root/'compositions/scenes/A.html').write_text('<template><div class="yf-cam" style="position:absolute;width:1920px;height:1080px;background:white"><div style="position:absolute;left:100px;top:100px;font:40px Arial;color:black">Real product evidence</div><div style="position:absolute;left:100px;top:300px;font:20px Arial;color:black">Small important text</div></div><script>window.__timelines.a=gsap.timeline({paused:true}).to(".yf-cam",{x:30,duration:'+str(duration)+',ease:"none"},0);</script></template>')

    @unittest.skipUnless(os.environ.get('YICE_PLAYWRIGHT_MODULE') and os.environ.get('YICE_GSAP_PATH'),'需要已有离线Chrome/Playwright/GSAP')
    def test_real_dom_camera_and_rendered_pixel_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.browser_fixture(root)
            d=self.node("console.log(JSON.stringify(await p.probeCompositions(input,[{id:'A',B:0,E:2,dur:2,recipe:'fixture',readingRegions:[{name:'large',screenRect:{x:90,y:95,w:650,h:80}},{name:'small',screenRect:{x:90,y:295,w:650,h:60}}]}])));",tmp)
            self.assertTrue(d['camera'][0]['moving']);self.assertGreaterEqual(d['readings'][0]['effectiveTextHeightPx'],28);self.assertLess(d['readings'][1]['effectiveTextHeightPx'],28)

    @unittest.skipUnless(os.environ.get('YICE_PLAYWRIGHT_MODULE') and os.environ.get('YICE_GSAP_PATH'),'需要已有离线Chrome/Playwright/GSAP')
    def test_check_cli_blocks_without_running_online_native_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shutil.copytree(TEMPLATE,root,dirs_exist_ok=True);self.browser_fixture(root,3)
            (root/'episode.json').write_text('{"end":3}');(root/'beats.json').write_text('{"scenes":[{"id":"A","recipe":"fixture"}]}');(root/'build-report.json').write_text('[{"id":"A","B":0,"E":3,"start":0,"dur":3}]')
            file=root/'still.mp4';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=gray:s=256x144:r=24:d=3','-c:v','libx264','-y',str(file)],check=True,capture_output=True)
            result=subprocess.run(['node','check.mjs','--cinema-only','--rendered',str(file),'--json'],cwd=root,capture_output=True,text=True,env={**os.environ,'YICE_MEDIA_OFFLINE':'1'})
            self.assertEqual(result.returncode,1,result.stderr[-1000:]);report=json.loads((root/'check-report.json').read_text());self.assertFalse(report['ok']);self.assertEqual(report['cinema']['findings'][0]['code'],'shot_still_too_long')


if __name__=='__main__':unittest.main()
