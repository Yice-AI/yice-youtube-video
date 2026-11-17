import json
from pathlib import Path
import subprocess
import unittest
from test_visual_variety import fixture as visual_fixture
from test_cinema import fixture as cinema_fixture

TEMPLATE=Path(__file__).parents[1]/'template'


class CinemaSecondTests(unittest.TestCase):
    def node(self,body,data=None):
        code=f"import * as f from {json.dumps((TEMPLATE/'cinema-frames.mjs').as_uri())};import * as c from {json.dumps((TEMPLATE/'check-cinema.mjs').as_uri())};import * as v from {json.dumps((TEMPLATE/'check-visual.mjs').as_uri())};import * as m from {json.dumps((TEMPLATE/'media-coverage.mjs').as_uri())};"+"import fs from 'node:fs';const input=JSON.parse(fs.readFileSync(0,'utf8'));"+body
        r=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(data),capture_output=True,text=True,check=True);return json.loads(r.stdout)

    def test_change_threshold_is_strict_pixel_delta_and_inclusive_area(self):
        result=self.node("const rows=[];for(const [delta,area]of [[32,100],[33,11],[33,12]]){const t=f.visualChangeTracker({width:10,height:10});t.push(Buffer.alloc(100),0);const b=Buffer.alloc(100);b.fill(delta,0,area);t.push(b,.5);rows.push(t.finish(1).events);}console.log(JSON.stringify(rows));")
        self.assertEqual(result,[0,0,1])

    def test_peak_suppression_prefers_stronger_change_within_quarter_second(self):
        result=self.node("const t=f.visualChangeTracker({width:10,height:10});t.push(Buffer.alloc(100),0);t.push(Buffer.alloc(100,40),.25);t.push(Buffer.alloc(100,80),.5);t.push(Buffer.alloc(100,120),1);console.log(JSON.stringify(t.finish(2))); ")
        self.assertEqual(result['events'],2);self.assertEqual(result['eventsPerSecond'],1)

    def test_new_gates_accept_exact_limits_and_reject_below(self):
        data=cinema_fixture();self.assertTrue(self.node('console.log(JSON.stringify(c.evaluateCinema(input)));',data)['ok'])
        data['media']['realRatio']=.299;data['frames']['visualChange']['eventsPerSecond']=.449
        result=self.node('console.log(JSON.stringify(c.evaluateCinema(input)));',data)
        self.assertEqual([x['code'] for x in result['findings']],['real_media_ratio_low','visual_change_rate_low'])

    def test_unmeasured_changes_are_not_a_pass(self):
        data=cinema_fixture();data['frames'].pop('visualChange')
        result=self.node('console.log(JSON.stringify(c.evaluateCinema(input)));',data)
        self.assertEqual(result['findings'][0]['code'],'visual_change_unmeasured')

    def test_generated_picture_and_logo_are_not_counted_as_real_photos(self):
        result=self.node("const media=[{exists:true,file:'/sample.png',url:'sample.png'}];console.log(JSON.stringify([m.sceneMediaClass({recipe:'stock-shot'},media,[{path:'sample.png',provider:'image2'}]),m.sceneMediaClass({recipe:'brand-hero'},media),m.sceneMediaClass({recipe:'news-card'},media),m.sceneMediaClass({recipe:'cutout-stack'},media)]));")
        self.assertEqual(result,['graphics','graphics','screenshot','cutout'])

    def test_commentary_can_be_in_body_but_not_thumbnail(self):
        data=visual_fixture();data['assetLedger']=[{'id':'person','scene':'S0','tier':'commentary','role':'body'}]
        self.assertTrue(self.node('console.log(JSON.stringify(v.evaluateVisualVariety(input)));',data)['ok'])
        data['thumbnailManifest']={'assets':['person']}
        result=self.node('console.log(JSON.stringify(v.evaluateVisualVariety(input)));',data)
        self.assertIn('commentary_in_thumbnail',[r['code'] for r in result['findings']])

    def test_default_person_is_allowed_in_thumbnail(self):
        data=visual_fixture();data['assetLedger']=[{'id':'person','tier':'default','role':'thumbnail'}]
        self.assertTrue(self.node('console.log(JSON.stringify(v.evaluateVisualVariety(input)));',data)['ok'])

    def test_fifth_sticker_is_blocked(self):
        data=visual_fixture();data['beats']['scenes']=[{**s,'recipe':'reaction-cutout','props':{'text':'我们的评论','person':'person.png'}} for s in data['beats']['scenes']]
        while len(data['beats']['scenes'])<5:data['beats']['scenes'].append({**data['beats']['scenes'][-1],'id':'extra'+str(len(data['beats']['scenes']))})
        for i,scene in enumerate(data['beats']['scenes']):scene.update(start=i*8,end=(i+1)*8)
        result=self.node('console.log(JSON.stringify(v.evaluateVisualVariety(input)));',data)
        self.assertIn('sticker_density_high',[r['code'] for r in result['findings']])


if __name__=='__main__':unittest.main()
