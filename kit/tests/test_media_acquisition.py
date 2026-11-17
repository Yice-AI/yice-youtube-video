"""素材采集：离线覆盖访问墙、批次回退、许可与下载账本，不访问公网。"""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


class MediaAcquisitionTests(unittest.TestCase):
    def node(self, body):
        with tempfile.TemporaryDirectory() as directory:
            prefix = f"import * as media from {json.dumps((SCRIPTS/'open-media.mjs').as_uri())};\n" \
                     f"import * as web from {json.dumps((SCRIPTS/'capture-web.mjs').as_uri())};\n" + r"""
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
let input='';for await(const chunk of process.stdin)input+=chunk;
const {project}=JSON.parse(input);
const candidate={provider:'commons',title:'Sample',creator:'Test Author',
 sourceUrl:'https://commons.wikimedia.org/wiki/File:Sample.png',downloadUrl:'https://upload.wikimedia.org/sample.png',
 license:'CC BY 4.0',licenseUrl:'https://creativecommons.org/licenses/by/4.0/'};
const ledger=()=>fs.existsSync(path.join(project,'asset-ledger.jsonl'))?
 fs.readFileSync(path.join(project,'asset-ledger.jsonl'),'utf8').trim().split('\n').map(JSON.parse):[];
const emit=value=>console.log(JSON.stringify(value));
"""
            result = subprocess.run(['node', '--input-type=module', '-e', prefix + body],
                                    input=json.dumps({'project': directory}), text=True,
                                    capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr[-1500:])
            return json.loads(result.stdout)

    def test_access_walls_are_reported(self):
        result = self.node("""
emit([{status:403},{title:'Just a moment'},{text:'正在进行安全验证，验证您不是自动程序'},
 {text:'Sign in to continue'},{text:'订阅后阅读'},{password:true}].map(web.wallReason));
""")
        self.assertEqual(result, ['http_403', 'challenge', 'challenge', 'login_or_paywall',
                                  'login_or_paywall', 'login_or_paywall'])

    def test_public_article_with_optional_signin_is_not_wall(self):
        self.assertIsNone(self.node("emit(web.wallReason({text:'Image compression. Sign in · Create account'}));"))

    def test_invalid_capture_inputs_fail_before_browser_launch(self):
        errors = self.node("""
const errors=[];
for(const options of [{url:'file:///private/test'},{url:'https://user:pass@example.com'},
 {id:'../escape'},{seconds:5},{seconds:9}]){
 try{await web.capturePage({project,url:'https://example.com',...options});errors.push(null);}
 catch(error){errors.push(error.message);}
}emit(errors);
""")
        self.assertTrue(all(errors))
        self.assertIn('HTTP(S)', errors[0])
        self.assertIn('id', errors[2])
        self.assertIn('6–8', errors[3])

    def test_batch_fallback_and_failed_item_do_not_stop_later_items(self):
        result = self.node("""
const calls=[];
const needs={items:[
 {id:'first',type:'news_capture',claim:'原始论点',scene:'S1',candidateUrls:['blocked','okay','unused'],capture:{seconds:6,highlight:'重点'}},
 {id:'second',type:'news_capture',candidateUrls:['throws']},
 {id:'third',type:'news_capture',candidateUrls:['okay']} ]};
const report=await web.captureNeeds({project,needs,capture:async options=>{
 calls.push(options);if(options.url==='throws')throw new Error('network unavailable');
 return {id:options.id,status:options.url==='blocked'?'skipped':'captured',reason:options.url==='blocked'?'http_403':null};
}});emit({report,calls,saved:JSON.parse(fs.readFileSync(path.join(project,'web-capture-report.json')))});
""")
        self.assertEqual([c['url'] for c in result['calls']], ['blocked', 'okay', 'throws', 'okay'])
        self.assertEqual((result['report']['captured'], result['report']['failed']), (2, 1))
        self.assertEqual(result['report']['items'][0]['claim'], '原始论点')
        self.assertEqual(result['calls'][0]['highlight'], '重点')
        self.assertEqual(result['report'], result['saved'])

    def test_batch_missing_urls_and_skips_stay_explicit(self):
        report = self.node("""
emit(await web.captureNeeds({project,needs:{items:[
 {id:'open',type:'open_media',candidateUrls:['not-a-web-task']},
 {id:'missing',type:'news_capture'},
 {id:'wall',type:'news_capture',candidateUrls:['private']} ]},
 capture:async options=>({id:options.id,status:'skipped',reason:'login_or_paywall'})}));
""")
        self.assertEqual([r['id'] for r in report['items']], ['missing', 'wall'])
        self.assertEqual((report['captured'], report['skipped'], report['failed']), (0, 1, 1))

    def test_invalid_needs_are_rejected(self):
        self.assertIn('items', self.node("try{await web.captureNeeds({project,needs:{}});}catch(error){emit(error.message);}"))

    def test_ledger_replaces_stale_hash_and_preserves_other_assets(self):
        result = self.node("""
web.recordAsset(project,{id:'one',sha256:'old'});web.recordAsset(project,{id:'two',sha256:'other'});
web.recordAsset(project,{id:'one',sha256:'new'});
emit({rows:ledger(),tempExists:fs.existsSync(path.join(project,'asset-ledger.jsonl.tmp'))});
""")
        self.assertEqual({r['id']: r['sha256'] for r in result['rows']}, {'one': 'new', 'two': 'other'})
        self.assertEqual(len(result['rows']), 2)
        self.assertFalse(result['tempExists'])

    def test_license_deeds_and_canonical_urls_match(self):
        result = self.node("""
emit(['https://creativecommons.org/licenses/by-sa/3.0/deed.en',
 'http://creativecommons.org/licenses/by-sa/3.0/',
 'https://creativecommons.org/publicdomain/zero/1.0/legalcode.zh-Hans',
 'https://creativecommons.org/publicdomain/mark/1.0/'].map(media.licenseUrlKey));
""")
        self.assertEqual(result[0], result[1])
        self.assertTrue(all(result))

    def test_restricted_unknown_and_lookalike_licenses_are_rejected(self):
        result = self.node("""
emit(['https://creativecommons.org/licenses/by-nc/4.0/',
 'https://creativecommons.org/licenses/by-nd/4.0/',
 'https://creativecommons.org.evil.example/licenses/by/4.0/',
 'https://creativecommons.org/licenses/by/4.0/fake',
 'ftp://creativecommons.org/licenses/by/4.0/',null,''].map(media.licenseAllowed));
""")
        self.assertEqual(result, [False] * 7)

    def test_commons_search_keeps_author_and_original_source(self):
        result = self.node("""
emit(media.commonsCandidates({query:{pages:{3:{pageid:3,title:'File:Sample.png',imageinfo:[{
 url:'https://upload.wikimedia.org/original.png',thumburl:'https://upload.wikimedia.org/thumb.png',
 mime:'image/png',descriptionurl:candidate.sourceUrl,size:123,
 extmetadata:{Artist:{value:'<a href="/User:Author">Author</a>'},LicenseShortName:{value:'CC BY 4.0'},LicenseUrl:{value:candidate.licenseUrl}}
}]}}}}));
""")
        self.assertEqual(result[0]['creator'], 'Author')
        self.assertTrue(result[0]['downloadUrl'].endswith('/thumb.png'))
        self.assertTrue(result[0]['originalUrl'].endswith('/original.png'))
        self.assertEqual(result[0]['licenseEvidence']['pageId'], 3)

    def test_openverse_search_keeps_primary_source_for_verification(self):
        result = self.node("""
emit(media.openverseCandidates({results:[{id:'abc',title:'Laptop',creator:'Maker',
 foreign_landing_url:'https://example.com/original',url:'https://example.com/laptop.jpg',
 license:'by',license_version:'4.0',license_url:candidate.licenseUrl,source:'flickr'}]}));
""")
        self.assertEqual(result[0]['sourceUrl'], 'https://example.com/original')
        self.assertEqual(result[0]['license'], 'CC BY 4.0')
        self.assertIn('verification required', result[0]['licenseEvidence']['method'])

    def test_download_records_matching_file_hash_and_attribution(self):
        result = self.node("""
const bytes=Buffer.from('synthetic-media-test');
const entry=await media.downloadAsset({project,candidate,scene:'S3',
 requestFn:async()=>new Response(bytes,{headers:{'content-type':'image/png'}})});
const file=fs.readFileSync(path.join(project,entry.path));
emit({entry,rows:ledger(),actualHash:createHash('sha256').update(file).digest('hex')});
""")
        self.assertEqual(result['actualHash'], result['entry']['sha256'])
        self.assertEqual(result['rows'], [result['entry']])
        self.assertEqual(result['entry']['scene'], 'S3')
        self.assertIn('Test Author', result['entry']['attribution'])
        self.assertIn('creativecommons.org', result['entry']['attribution'])

    def test_incomplete_or_restricted_metadata_never_downloads(self):
        result = self.node("""
let called=0;const errors=[];
for(const patch of [{creator:''},{sourceUrl:''},{licenseUrl:'https://creativecommons.org/licenses/by-nc/4.0/'},{bytes:26*1024*1024}]){
 try{await media.downloadAsset({project,candidate:{...candidate,...patch},requestFn:async()=>{called++;return new Response('x');}});}
 catch(error){errors.push(error.message);}
}emit({called,errors,rows:ledger()});
""")
        self.assertEqual(result['called'], 0)
        self.assertEqual(len(result['errors']), 4)
        self.assertEqual(result['rows'], [])

    def test_bad_empty_or_oversized_responses_never_enter_ledger(self):
        result = self.node("""
const errors=[];
for(const [content,type,length] of [['<html>Access denied</html>','text/html'],['','image/png'],
 ['x','image/bmp'],['x','image/png',26*1024*1024]]){
 try{await media.downloadAsset({project,candidate,requestFn:async()=>new Response(content,
 {headers:{'content-type':type,...(length?{'content-length':String(length)}:{})}})});}
 catch(error){errors.push(error.message);}
}emit({errors,rows:ledger(),files:fs.existsSync(path.join(project,'assets/open'))});
""")
        self.assertEqual(len(result['errors']), 4)
        self.assertEqual(result['rows'], [])
        self.assertFalse(result['files'])

    def test_network_failure_does_not_claim_download_success(self):
        result = self.node("""
try{await media.downloadAsset({project,candidate,requestFn:async()=>{throw new Error('HTTP 429');}});}
catch(error){emit({error:error.message,rows:ledger()});}
""")
        self.assertEqual(result, {'error': 'HTTP 429', 'rows': []})


if __name__ == '__main__':
    unittest.main()
