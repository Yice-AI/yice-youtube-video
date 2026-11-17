"""实体采集离线测试：来源、访问墙、媒体声明、任务草稿、卡片接线。"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]


class EntityTests(unittest.TestCase):
    def node(self, body, timeout=20):
        with tempfile.TemporaryDirectory() as directory:
            prefix = f"import * as e from {json.dumps((KIT/'scripts/collect-entity.mjs').as_uri())};\n" \
                     f"import * as p from {json.dumps((KIT/'scripts/entity-page.mjs').as_uri())};\n" \
                     f"import {{capturePage}} from {json.dumps((KIT/'scripts/capture-web.mjs').as_uri())};\n" \
                     f"import {{bindEntityScene}} from {json.dumps((KIT/'template/entity-assets.mjs').as_uri())};\n" + r"""
import fs from 'node:fs';import path from 'node:path';import {createHash} from 'node:crypto';
let input='';for await(const c of process.stdin)input+=c;const {project}=JSON.parse(input);
const emit=x=>console.log(JSON.stringify(x));
const base={name:'Example',site:'https://example.com',out:project};
const fake=async o=>({status:'captured',title:'Official title',finalUrl:o.url,files:[],details:{links:[],images:[],logos:[],sections:[],demos:[]}});
const noLogo=async()=>{throw new Error('logo unavailable')};const noOverview=async()=>{};
"""
            r = subprocess.run(['node', '--input-type=module', '-e', prefix+body], input=json.dumps({'project': directory}), text=True, capture_output=True, timeout=timeout, env={**os.environ, 'YICE_MEDIA_OFFLINE':'1'})
            self.assertEqual(r.returncode, 0, r.stderr[-2500:])
            return json.loads(r.stdout)

    def test_validate_before_network_or_files(self):
        errors = self.node("""const errors=[];for(const o of [{},{name:'x'},{name:'x',site:'file:///x'},{name:'x',site:'https://a:b@example.com'},{name:'x',github:'../bad/thing'}])try{e.validateEntity(o);errors.push(null)}catch(x){errors.push(x.message)}emit(errors);""")
        self.assertTrue(all(errors))

    def test_logo_prefers_official_svg_over_ico_and_cookie_vendor(self):
        result = self.node("emit(e.chooseLogoSource({logos:[{url:'https://example.com/a.ico'},{url:'https://cdn.cookielaw.org/logos/x.svg'},{url:'https://example.com/a.png'},{url:'https://example.com/a.svg'}]},base.site));")
        self.assertEqual(result, 'https://example.com/a.svg')

    def test_official_links_exclude_lookalike_domains(self):
        result = self.node("""emit(p.classifyLinks([{url:'https://example.com/blog/a',text:'news'},{url:'https://example.com.evil.test/blog/a',text:'news'},{url:'https://blog.example.com/posts/1',text:'blog'},{url:'https://example.com/demo',text:'Try demo'},{url:'https://example.com/login',text:'try demo'},{url:'javascript:alert(1)',text:'demo'}],base.site));""")
        self.assertEqual(len(result['announcements']), 2)
        self.assertFalse(any('evil.test' in x['url'] for x in result['announcements']))
        self.assertEqual([x['url'] for x in result['interactive']], ['https://example.com/demo'])

    def test_latest_dated_announcement_and_honest_fallback(self):
        result = self.node("""emit([p.latestAnnouncement([{url:'https://example.com/blog/old',text:'old',date:'2025-01-01'},{url:'https://example.com/blog/new',text:'new',date:'2026-01-01'}],base.site),p.latestAnnouncement([{url:'https://example.com/blog',text:'Blog'},{url:'https://example.com/blog/a',text:'A'}],base.site)]);""")
        self.assertTrue(result[0]['url'].endswith('/new'))
        self.assertEqual(result[1]['selection'], 'first_listed_date_unverified')

    def test_media_kit_title_is_not_a_permission(self):
        result = self.node("emit(['Brand media kit. All rights reserved.','These product images are available for media use.','此处产品图可供媒体使用。'].map(p.pressPermission));")
        self.assertIsNone(result[0]); self.assertTrue(result[1]); self.assertTrue(result[2])

    def test_hf_community_blog_and_incidental_words_are_not_official_or_demo(self):
        result = self.node("""emit(p.classifyLinks([{url:'https://huggingface.co/blog/community-user/post',text:'Community post'},{url:'https://huggingface.co/blog/official-post',text:'Official post'},{url:'https://huggingface.co/blog/country',text:'Demographics and industry'}],'https://huggingface.co'));""")
        self.assertEqual(len(result['announcements']), 2)
        self.assertFalse(result['interactive'])

    def test_walls_are_recorded_without_bypass_or_logo_fallback(self):
        result = self.node("""let calls=0;const m=await e.collectEntity(base,{capture:async()=>{calls++;return {status:'skipped',reason:'challenge'}},logo:async()=>{throw new Error('must not run')},overview:noOverview});emit({m,calls,exists:fs.existsSync(path.join(project,'manifest.json'))});""")
        self.assertEqual(result['calls'], 1)
        self.assertEqual(result['m']['items'][0]['reason'], 'challenge')
        self.assertTrue(result['exists']); self.assertFalse(result['m']['harnessDispatched'])

    def test_press_images_download_only_with_explicit_statement(self):
        result = self.node("""const results=[];for(const allowed of [false,true]){let downloads=0;const m=await e.collectEntity({...base,press:'https://example.com/press'},{capture:async o=>({...await fake(o),details:{links:[],images:[{url:'https://example.com/a.png',width:800,height:600,alt:'Product'}],text:allowed?'Images provided for media use.':'Brand media kit'}}),download:async(url,file)=>{downloads++;fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file+'.png','image');return {file:file+'.png'}},logo:noLogo,overview:noOverview});results.push({downloads,items:m.items});}emit(results);""")
        self.assertEqual([r['downloads'] for r in result], [0,1])
        self.assertTrue(any(i['type']=='press_image' and i['status']=='captured' for i in result[1]['items']))

    def test_interaction_is_a_draft_not_a_dispatched_task(self):
        result = self.node("""const m=await e.collectEntity(base,{capture:async o=>({...await fake(o),details:{links:[{url:'https://huggingface.co/spaces/example/demo',text:'Try the demo'}],inputs:[]}}),logo:noLogo,overview:noOverview});emit({m,draft:fs.readFileSync(path.join(project,'harness-draft.md'),'utf8'),dirs:fs.readdirSync(project)});""")
        self.assertEqual(len(result['m']['interactive']), 1)
        self.assertIn('8–12 秒', result['draft']); self.assertIn('未派发', result['draft'])
        self.assertNotIn('dsh-inbox', result['dirs'])

    def test_page_files_sections_and_demo_have_provenance(self):
        result = self.node("""fs.writeFileSync(path.join(project,'still.png'),'image');const m=await e.collectEntity(base,{capture:async o=>({...await fake(o),files:[{path:'still.png'}],details:{links:[],sections:[{path:'still.png',title:'Proof'}],demos:[{path:'still.png',status:'captured',url:'https://cdn.example.com/demo.mp4'}]}}),logo:noLogo,overview:noOverview});emit(m);""")
        done=[i for i in result['items'] if i['status']=='captured']
        self.assertEqual(len(done), 3)
        self.assertTrue(all(i['url'] and i['capturedAt'] and i['license'] and i['sha256'] for i in done))
        self.assertIn('≤5秒', done[-1]['usage'])

    def test_download_rejects_html_and_large_payload(self):
        result = self.node("""const errors=[];for(const r of [new Response('html',{headers:{'content-type':'text/html'}}),new Response('12345678',{headers:{'content-type':'image/png'}})])try{await e.downloadEntityFile('https://example.com/x',path.join(project,'x'),{fetchFn:async()=>r,maxBytes:4});errors.push(null)}catch(x){errors.push(x.message)}emit(errors);""")
        self.assertTrue(all(result))

    def test_bind_news_and_social_import_source_and_actual_file(self):
        result = self.node(r"""const dir=path.join(project,'entity');fs.mkdirSync(dir);fs.writeFileSync(path.join(dir,'image.png'),'bytes');const item={id:'site-hero',status:'captured',path:'image.png',title:'Official proof',url:'https://example.com',capturedAt:'2026-11-17T00:00:00Z',license:'Editorial'};fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({name:'Brand',items:[item]}));const scenes=['news-card','social-post'].map((recipe,i)=>bindEntityScene({id:'S'+i,recipe,props:{entity:{manifest:'entity/manifest.json',item:'site-hero'}}},{root:project}));emit({scenes,ledger:fs.readFileSync(path.join(project,'asset-ledger.jsonl'),'utf8').trim().split('\n').map(JSON.parse)});""")
        self.assertEqual(result['scenes'][0]['props']['source'], 'Brand')
        self.assertEqual(result['scenes'][0]['props']['date'], '2026-11-17')
        self.assertEqual(result['scenes'][1]['props']['text'], 'Official proof')
        self.assertTrue(result['scenes'][1]['props']['publicAccount'])
        self.assertEqual(len(result['ledger']), 2)

    def test_bind_rejects_failed_changed_and_escaping_assets(self):
        result = self.node("""const dir=path.join(project,'entity');fs.mkdirSync(dir);fs.writeFileSync(path.join(dir,'image.png'),'bytes');const errors=[];for(const item of [{id:'a',status:'skipped'},{id:'a',status:'captured',path:'image.png',sha256:'wrong'},{id:'a',status:'captured',path:'../secret'}]){fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify({name:'Brand',items:[item]}));try{bindEntityScene({id:'S',recipe:'news-card',props:{entity:{manifest:'entity/manifest.json',item:'a'}}},{root:project});errors.push(null)}catch(x){errors.push(x.message)}}emit(errors);""")
        self.assertTrue(all(result))

    def test_evidence_types_keep_source_and_verified_values(self):
        result = self.node("""fs.writeFileSync(path.join(project,'still.png'),'image');const types=['app-ranking','finance','benchmark'];const m=await e.collectEntity({...base,evidence:types.map(type=>({type,url:'https://example.com/'+type,values:[{label:'A',value:77.3}]}))},{capture:async o=>({...await fake(o),files:[{path:'still.png'}]}),logo:noLogo,overview:noOverview});fs.writeFileSync(path.join(project,'manifest.json'),JSON.stringify(m));const bars=bindEntityScene({id:'B',recipe:'bar-compare',props:{entity:{manifest:'manifest.json',item:'evidence-benchmark-3-hero'}}},{root:project});emit({items:m.items.filter(x=>x.type.startsWith('evidence_')),bars});""")
        self.assertEqual([x['type'] for x in result['items']],['evidence_app-ranking','evidence_finance','evidence_benchmark'])
        self.assertEqual(result['bars']['props']['items'][0]['value'],77.3)
        self.assertEqual(result['bars']['props']['sourceUrl'],'https://example.com/benchmark')

    def test_bar_binding_will_not_invent_numbers_from_a_screenshot(self):
        result=self.node("""fs.writeFileSync(path.join(project,'still.png'),'image');fs.writeFileSync(path.join(project,'manifest.json'),JSON.stringify({name:'Proof',items:[{id:'proof',status:'captured',path:'still.png',url:'https://example.com/proof'}]}));try{bindEntityScene({id:'B',recipe:'bar-compare',props:{entity:{manifest:'manifest.json',item:'proof'}}},{root:project});emit(null)}catch(e){emit(e.message)}""")
        self.assertIn('没有已核对的数值',result)

    @unittest.skipUnless(os.environ.get('YICE_PLAYWRIGHT_MODULE'),'需要已安装的离线Chrome/Playwright')
    def test_real_browser_capture_and_silent_demo_are_offline(self):
        result = self.node(r"""
const {createServer}=await import('node:http');const {execFileSync}=await import('node:child_process');
const video=path.join(project,'clip.mp4');execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=15:d=2','-c:v','libx264','-pix_fmt','yuv420p','-y',video]);
const html='<main style="min-height:2700px;background:#eee"><h1>Official fixture</h1><h2>First proof</h2><video muted autoplay loop width="640" height="360" src="/clip.mp4"></video><div style="height:900px"></div><h2>Second proof</h2></main>';
const server=createServer((req,res)=>{const movie=req.url==='/clip.mp4',bytes=movie?fs.readFileSync(video):Buffer.from(html);res.writeHead(200,{'content-type':movie?'video/mp4':'text/html','content-length':bytes.length});res.end(bytes);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));let result;
try{result=await capturePage({project,url:'http://127.0.0.1:'+server.address().port,seconds:6,details:true});}
finally{await new Promise(r=>server.close(r));}
const demo=result.details?.demos?.find(d=>d.status==='captured');
const probe=demo?JSON.parse(execFileSync('ffprobe',['-v','error','-show_streams','-show_format','-of','json',path.join(project,demo.path)],{encoding:'utf8'})):null;
emit({result,probe});
""", timeout=60)
        self.assertEqual(result['result']['status'], 'captured', result['result'].get('reason'))
        self.assertEqual(len(result['result']['details']['sections']), 2)
        self.assertIsNotNone(result['probe'])
        self.assertAlmostEqual(float(result['probe']['format']['duration']), 6, places=2)
        self.assertEqual([(s['codec_type'],s.get('width'),s.get('height')) for s in result['probe']['streams']], [('video',1920,1080)])


if __name__ == '__main__': unittest.main()
