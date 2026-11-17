import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).parents[1] / 'scripts'


class MediaBudgetTests(unittest.TestCase):
    def run_node(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'stock.env').write_text('PEXELS_API_KEY="fixture-pexels-secret"\nPIXABAY_API_KEY=fixture-pixabay-secret\n')
            script = "import fs from 'node:fs';import path from 'node:path';import {createHash} from 'node:crypto';" + f"import * as a from {json.dumps((SCRIPTS / 'media-api.mjs').as_uri())};import * as m from {json.dumps((SCRIPTS / 'find-media.mjs').as_uri())};import * as s from {json.dumps((SCRIPTS / 'stock-media.mjs').as_uri())};const root={json.dumps(tmp)};" + body
            run = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, env={**os.environ, 'YICE_MEDIA_OFFLINE': '1'})
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            return json.loads(run.stdout)

    def test_cache_normalizes_query_and_expires_after_24h(self):
        d = self.run_node("let time=1700000000000,hits=0;const options={root,episode:'/ep',now:()=>time,transport:async()=>{hits++;return Response.json({photos:[]});}};await a.createMediaApi(options).request('pexels','https://api.pexels.com/v1/search?query=paper&per_page=8',{query:' Paper  desk ',type:'photo',search:true});await a.createMediaApi(options).request('pexels','https://api.pexels.com/v1/search?query=paper&per_page=30',{query:'paper desk',type:'photo',search:true});const before=hits;time+=86400001;await a.createMediaApi(options).request('pexels','https://api.pexels.com/v1/search',{query:'paper desk',type:'photo',search:true});console.log(JSON.stringify({before,hits,logs:a.readUsage(root).length}));")
        self.assertEqual(d, {'before': 1, 'hits': 2, 'logs': 2})

    def test_invocation_cap_counts_all_sources(self):
        d = self.run_node("let hits=0;const api=a.createMediaApi({root,transport:async()=>{hits++;return Response.json({});}});for(const [source,url] of [['pexels','https://api.pexels.com/v1/search'],['pixabay','https://pixabay.com/api/'],['nasa','https://images-api.nasa.gov/search']])await api.request(source,url);let code;try{await api.request('commons','https://commons.wikimedia.org/w/api.php');}catch(e){code=e.code;}console.log(JSON.stringify({hits,code}));")
        self.assertEqual(d, {'hits': 3, 'code': 'INVOCATION_LIMIT'})

    def test_episode_combined_budget_blocks_61_before_network(self):
        d = self.run_node("const id=createHash('sha256').update('/ep').digest('hex');fs.writeFileSync(path.join(root,'media-budgets.json'),JSON.stringify({[id]:59}));let hits=0;const api=a.createMediaApi({root,episode:'/ep',transport:async()=>{hits++;return Response.json({});}});await api.request('pexels','https://api.pexels.com/v1/search');let code;try{await api.request('pixabay','https://pixabay.com/api/');}catch(e){code=e.code;}console.log(JSON.stringify({hits,code,used:a.readBudgets(root).episodes[id]}));")
        self.assertEqual(d, {'hits': 1, 'code': 'EPISODE_BUDGET', 'used': 60})

    def test_monthly_budget_shared_across_episodes(self):
        d = self.run_node("fs.writeFileSync(path.join(root,'media-budgets.json'),JSON.stringify({schema:2,episodes:{},months:{'2026-11':1499}}));let hits=0;const options={root,now:()=>Date.parse('2026-11-17T00:00:00Z'),transport:async()=>{hits++;return Response.json({});}};await a.createMediaApi({...options,episode:'/ep1'}).request('pexels','https://api.pexels.com/v1/search');let code;try{await a.createMediaApi({...options,episode:'/ep2'}).request('pixabay','https://pixabay.com/api/');}catch(e){code=e.code;}console.log(JSON.stringify({hits,code,used:a.readBudgets(root).months['2026-11']}));")
        self.assertEqual(d, {'hits': 1, 'code': 'MONTHLY_BUDGET', 'used': 1500})

    def test_header_units_private_log_and_no_key_in_persisted_response(self):
        d = self.run_node("const time=1700000000000,auth=[];const api=a.createMediaApi({root,now:()=>time,transport:async(url,options)=>{auth.push([url,options.headers.Authorization]);return Response.json({next:'https://pixabay.com/api/?key=fixture-pixabay-secret'},{headers:{'X-RateLimit-Limit':'100','X-RateLimit-Remaining':'99','X-RateLimit-Reset':url.includes('pixabay')?'59':'1700003600'}});}});await api.request('pexels','https://api.pexels.com/v1/search',{query:'paper'});await api.request('pixabay','https://pixabay.com/api/',{query:'paper'});const rows=a.readUsage(root);const files=[path.join(root,'usage.jsonl'),...fs.readdirSync(path.join(root,'media-cache')).map(f=>path.join(root,'media-cache',f))];console.log(JSON.stringify({rows,secretLeak:files.some(f=>fs.readFileSync(f,'utf8').includes('fixture-')),mode:fs.statSync(path.join(root,'usage.jsonl')).mode&511,authCorrect:auth[0][1]==='fixture-pexels-secret'&&auth[1][0].includes('key=fixture-pixabay-secret')}));")
        self.assertFalse(d['secretLeak']);self.assertTrue(d['authCorrect']);self.assertEqual(d['mode'], 0o600)
        self.assertEqual(d['rows'][0]['resetAt'], '2023-11-14T23:13:20.000Z')
        self.assertEqual(d['rows'][1]['resetAt'], '2023-11-14T22:14:19.000Z')

    def test_error_cache_stops_repeat_and_does_not_leak_transport_exception(self):
        d = self.run_node("let hits=0;const options={root,transport:async()=>{hits++;throw new Error('fixture-pixabay-secret');}};let messages=[];for(let i=0;i<2;i++)try{await a.createMediaApi(options).request('pixabay','https://pixabay.com/api/',{query:'desk',search:true,type:'photo'});}catch(e){messages.push(e.message);}console.log(JSON.stringify({hits,messages,rows:a.readUsage(root)}));")
        self.assertEqual(d['hits'], 1);self.assertEqual(len(d['rows']), 1)
        self.assertNotIn('fixture-pixabay-secret', json.dumps(d))

    def test_daily_usage_is_observation_not_assumed_account_history(self):
        d = self.run_node("console.log(JSON.stringify(a.usageSummary([{at:'2026-11-17T00:00:00.000Z',source:'pexels',remaining:3,limit:100,resetAt:'2026-11-18T00:00:00.000Z'},{at:'2026-11-17T01:00:00.000Z',source:'pexels',remaining:null},{at:'2026-11-17T02:00:00.000Z',source:'pixabay',remaining:98,limit:100,resetAt:'2026-11-17T02:01:00.000Z'}],{now:Date.parse('2026-11-17T03:00:00.000Z')}))); ")
        self.assertEqual(d['youtubeLine']['daily'][0]['sources'], {'pexels': 2, 'pixabay': 1})
        self.assertFalse(d['sharedAccountRemaining']['pexels']['stale']);self.assertTrue(d['sharedAccountRemaining']['pixabay']['stale'])

    def test_offline_mode_rejects_real_transport_before_network(self):
        d = self.run_node("try{await a.createMediaApi({root}).request('pexels','https://api.pexels.com/v1/search');}catch(e){console.log(JSON.stringify(e.code));}")
        self.assertEqual(d, 'OFFLINE')

    def test_missing_keys_do_not_consume_requests(self):
        d = self.run_node("fs.unlinkSync(path.join(root,'stock.env'));let hits=0;try{await a.createMediaApi({root,transport:async()=>{hits++;return Response.json({});}}).request('pexels','https://api.pexels.com/v1/search');}catch(e){console.log(JSON.stringify({hits,code:e.code}));}")
        self.assertEqual(d, {'hits': 0, 'code': 'SOURCE_DISABLED'})

    def test_host_validation_prevents_key_forwarding(self):
        d = self.run_node("let hits=0;try{await a.createMediaApi({root,transport:async()=>{hits++;return Response.json({});}}).request('pixabay','https://example.com/api/');}catch(e){console.log(JSON.stringify({hits,code:e.code}));}")
        self.assertEqual(d, {'hits': 0, 'code': 'INVALID_API'})

    def test_five_sources_are_bounded_and_report_deferred(self):
        d = self.run_node("let hits=0;const api=a.createMediaApi({root,transport:async()=>{hits++;return Response.json({});}});const result=await m.findCandidates({query:'desk',providers:m.PROVIDERS,api});console.log(JSON.stringify({hits,sources:result.sources.map(s=>s.status)}));")
        self.assertEqual(d['hits'], 3);self.assertEqual(d['sources'][-2:], ['deferred_budget', 'deferred_budget'])

    def test_pexels_photo_and_video_normalization(self):
        d = self.run_node("const video=s.pexelsCandidates({videos:[{id:1,url:'https://www.pexels.com/video/1/',image:'https://images.pexels.com/x.jpg',duration:12,user:{name:'A'},video_files:[{link:'https://videos.pexels.com/4k.mp4',file_type:'video/mp4',width:3840,height:2160},{link:'https://videos.pexels.com/hd.mp4',file_type:'video/mp4',width:1920,height:1080}]}]},'video')[0];const photo=s.pexelsCandidates({photos:[{id:2,url:'https://www.pexels.com/photo/2/',photographer:'B',width:4000,height:3000,src:{original:'https://images.pexels.com/2.jpeg',medium:'https://images.pexels.com/2.jpeg?w=350'}}]},'photo')[0];console.log(JSON.stringify({video:m.normalizeCandidate(video,'video'),photo:m.normalizeCandidate(photo,'photo')}));")
        self.assertEqual(d['video']['width'], 1920);self.assertEqual(d['video']['durationSeconds'], 12)
        self.assertEqual(d['photo']['creator'], 'B');self.assertFalse(d['photo']['shareAlike'])

    def test_pixabay_1080_selection_and_source_attribution(self):
        d = self.run_node("const raw=s.pixabayCandidates({hits:[{id:1,pageURL:'https://pixabay.com/videos/id-1/',user:'A',duration:9,tags:'paper',videos:{large:{url:'https://cdn.pixabay.com/4k.mp4',width:3840,height:2160},medium:{url:'https://cdn.pixabay.com/hd.mp4',width:1920,height:1080,thumbnail:'https://cdn.pixabay.com/hd.jpg'}}}]},'video')[0];console.log(JSON.stringify(m.normalizeCandidate(raw,'video')));")
        self.assertEqual(d['downloadUrl'], 'https://cdn.pixabay.com/hd.mp4');self.assertEqual(d['durationSeconds'], 9)
        self.assertIn('Pixabay', d['license']);self.assertFalse(d['attributionRequired'])

    def test_duration_resolution_filter_does_not_download_media(self):
        d = self.run_node("const calls=[];const report=await m.findCandidates({query:'paper',type:'video',providers:['pixabay'],minWidth:1920,minHeight:1080,maxDuration:15,requestFn:async url=>{calls.push(url);return Response.json({hits:[12,20].map((duration,i)=>({id:i,pageURL:'https://pixabay.com/videos/id-'+i+'/',user:'A',duration,videos:{medium:{url:'https://cdn.pixabay.com/'+i+'.mp4',width:1920,height:1080}}}))});}});console.log(JSON.stringify({calls,count:report.candidates.length,duration:report.candidates[0].durationSeconds}));")
        self.assertEqual(d['count'], 1);self.assertEqual(d['duration'], 12);self.assertEqual(len(d['calls']), 1)


if __name__ == '__main__': unittest.main()
