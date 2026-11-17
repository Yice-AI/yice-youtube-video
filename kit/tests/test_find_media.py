"""匿名三源素材候选、许可过滤、显式下载与真实视频转码。"""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
PD='https://creativecommons.org/publicdomain/mark/1.0/'
BY='https://creativecommons.org/licenses/by/4.0/'
NASA={'collection':{'items':[{'href':'https://images-assets.nasa.gov/image/A/collection.json',
    'data':[{'nasa_id':'A','center':'JSC','title':'Laptop on station','media_type':'image','description':'NASA equipment photo'}],
    'links':[{'href':'https://images-assets.nasa.gov/image/A/A~orig.jpg','rel':'canonical','width':4000,'height':3000},
             {'href':'https://images-assets.nasa.gov/image/A/A~thumb.jpg','rel':'preview','width':640,'height':480}]}]}}


class FindMediaTests(unittest.TestCase):
    def node(self,code,data=None):
        program="import * as m from "+json.dumps((SCRIPTS/'find-media.mjs').as_uri())+";import * as o from "+json.dumps((SCRIPTS/'open-media.mjs').as_uri())+";import fs from 'node:fs';let raw='';for await(const c of process.stdin)raw+=c;const input=raw?JSON.parse(raw):null;"+code
        run=subprocess.run(['node','--input-type=module','-e',program],input=json.dumps(data),capture_output=True,text=True,check=True)
        return json.loads(run.stdout)

    def test_nasa_preserves_canonical_resolution_and_original_evidence(self):
        d=self.node("console.log(JSON.stringify(m.nasaCandidates(input,'photo').map(x=>m.normalizeCandidate(x,'photo'))));",NASA)
        self.assertEqual((d[0]['width'],d[0]['height']),(4000,3000))
        self.assertTrue(d[0]['licenseEvidence']['nasaOriginal'])
        self.assertIn('~orig.jpg',d[0]['downloadUrl'])
        self.assertIsNone(d[0]['durationSeconds'])

    def test_nasa_does_not_relicense_third_party_credits(self):
        data=json.loads(json.dumps(NASA));data['collection']['items'][0]['data'][0]['description']='Copyright ESA / Getty Images'
        self.assertEqual(self.node("console.log(JSON.stringify(m.nasaCandidates(input,'photo')));",data),[])

    def test_nasa_without_agency_or_creator_is_not_assumed_public_domain(self):
        data=json.loads(json.dumps(NASA));data['collection']['items'][0]['data'][0].pop('center')
        self.assertEqual(self.node("console.log(JSON.stringify(m.nasaCandidates(input,'photo')));",data),[])

    def test_archive_public_domain_curated_collection_and_duration(self):
        data={'metadata':{'collection':['prelinger'],'licenseurl':'http://creativecommons.org/licenses/publicdomain/','creator':'Archive source','title':'City at night','runtime':'01:02'},
              'files':[{'name':'city.ogv','size':'400','width':'1280','height':'720'}]}
        result=self.node("console.log(JSON.stringify(m.normalizeCandidate(m.archiveCandidate('film',input,'video'),'video')));",data)
        self.assertEqual(result['durationSeconds'],62)
        self.assertEqual(result['width'],1280)
        self.assertEqual(result['mime'],'video/ogg')
        self.assertEqual(result['licenseUrl'],PD)

    def test_random_uploader_pd_label_is_not_curated_public_domain(self):
        data={'metadata':{'collection':['opensource_movies'],'licenseurl':PD,'title':'Mario TV episode'},'files':[{'name':'episode.mp4'}]}
        self.assertIsNone(self.node("console.log(JSON.stringify(m.archiveCandidate('fake',input,'video')));",data))

    def test_archive_restrictive_license_is_filtered(self):
        data={'metadata':{'collection':['prelinger'],'licenseurl':'https://creativecommons.org/licenses/by-nc/4.0/'},'files':[{'name':'x.mp4'}]}
        self.assertIsNone(self.node("console.log(JSON.stringify(m.archiveCandidate('x',input,'video')));",data))

    def test_conflicting_nc_label_and_unknown_license_are_filtered(self):
        for license,url in [('CC BY-NC',BY),('unknown','https://example.com/license')]:
            candidate={'provider':'commons','title':'paper','creator':'A','sourceUrl':'https://commons.wikimedia.org/wiki/File:Paper.jpg','downloadUrl':'https://upload.wikimedia.org/paper.jpg','mime':'image/jpeg','license':license,'licenseUrl':url}
            self.assertIsNone(self.node("console.log(JSON.stringify(m.normalizeCandidate(input,'photo')));",candidate))

    def test_share_alike_obligation_is_explicit(self):
        c={'provider':'commons','title':'paper','creator':'A','sourceUrl':'https://commons.wikimedia.org/wiki/File:Paper.jpg','downloadUrl':'https://upload.wikimedia.org/paper.jpg','mime':'image/jpeg','license':'CC BY-SA 4.0','licenseUrl':'https://creativecommons.org/licenses/by-sa/4.0/'}
        d=self.node("console.log(JSON.stringify(m.normalizeCandidate(input,'photo')));",c)
        self.assertTrue(d['shareAlike']);self.assertTrue(d['attributionRequired']);self.assertIn('同一许可',d['obligations'])

    def test_commons_video_search_and_metadata(self):
        d=self.node("const data={query:{pages:{1:{pageid:1,title:'File:City.webm',imageinfo:[{mime:'video/webm',width:1920,height:1080,url:'https://upload.wikimedia.org/city.webm',thumburl:'https://upload.wikimedia.org/city.jpg',descriptionurl:'https://commons.wikimedia.org/wiki/File:City.webm',metadata:[{name:'length',value:8}],extmetadata:{Artist:{value:'<b>A</b>'},LicenseShortName:{value:'CC BY'},LicenseUrl:{value:input}}}]}}}};console.log(JSON.stringify({url:m.searchUrl('commons','city','video',8),item:m.normalizeCandidate(o.commonsCandidates(data)[0],'video')}));",BY)
        self.assertIn('filetype%3Avideo',d['url'])
        self.assertEqual(d['item']['durationSeconds'],8)
        self.assertEqual(d['item']['creator'],'A')
        self.assertEqual(d['item']['mime'],'video/webm')

    def test_source_failure_keeps_other_sources_and_does_not_download(self):
        d=self.node("const calls=[];const result=await m.findCandidates({query:'laptop',n:8,requestFn:async url=>{calls.push(url);if(url.includes('commons'))throw new Error('HTTP 403');return {json:async()=>url.includes('images-api')?input:{response:{docs:[]}}};}});console.log(JSON.stringify({result,calls}));",NASA)
        self.assertEqual(d['result']['sources'][0]['status'],'test_limit')
        self.assertEqual(len(d['result']['candidates']),1)
        self.assertFalse(any('~orig' in url for url in d['calls']))

    def test_balanced_merge_and_deduplication(self):
        d=self.node("const c=(provider,n)=>({provider,sourceUrl:'https://x/'+n,downloadUrl:'https://x/'+n+'.jpg'});console.log(JSON.stringify(m.mergeCandidates([[c('a',1),c('a',2)],[c('b',3),c('b',1)],[c('c',4)]],4)));")
        self.assertEqual([x['provider'] for x in d],['a','b','c','a'])
        self.assertEqual(len({x['sourceUrl'] for x in d}),4)

    def test_bad_inputs_fail_before_network(self):
        for opts in [{'query':''},{'query':'x','type':'audio'},{'query':'x','n':0},{'query':'x','providers':['other']}]:
            self.assertTrue(self.node("try{await m.findCandidates({...input,requestFn:()=>{throw new Error('NETWORK CALLED');}});console.log(false);}catch(e){console.log(JSON.stringify(!e.message.includes('NETWORK CALLED')));}",opts))

    def test_explicit_selection_is_required(self):
        d=self.node("try{await m.downloadSelection({file:'/missing',ids:[],project:'/missing'});console.log(false);}catch(e){console.log(JSON.stringify(e.message));}")
        self.assertIn('选定',d)

    def test_duration_formats(self):
        d=self.node("console.log(JSON.stringify(['02:10','PT1M2.5S',12,{value:1200,scale:'1/1000'},null].map(m.durationSeconds)));")
        self.assertEqual(d,[130,62.5,12,1.2,None])

    def test_nasa_policy_cannot_authorize_unrelated_source(self):
        d=self.node("try{await o.downloadAsset({project:'/missing',candidate:{provider:'commons',licenseUrl:m.NASA_POLICY,creator:'A',sourceUrl:'https://example.com',downloadUrl:'https://example.com/x.jpg'}});console.log(false);}catch(e){console.log(JSON.stringify(e.message));}")
        self.assertIn('NASA',d)

    def test_webm_is_transcoded_and_derivative_hash_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'sample.webm';project=Path(tmp)/'project';project.mkdir()
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=s=160x90:r=10:d=0.8','-an','-c:v','libvpx-vp9',str(src)],check=True,capture_output=True)
            d=self.node("const bytes=fs.readFileSync(input.src);const asset=await o.downloadAsset({project:input.project,candidate:{provider:'commons',title:'Synthetic test',creator:'test',license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/',sourceUrl:'https://commons.wikimedia.org/wiki/File:Test.webm',downloadUrl:'https://upload.wikimedia.org/test.webm'},requestFn:async()=>new Response(bytes,{headers:{'content-type':'video/webm'}}),transcodeVideo:true});console.log(JSON.stringify(asset));",{'src':str(src),'project':str(project)})
            self.assertEqual(d['mime'],'video/mp4')
            self.assertEqual((d['width'],d['height']),(160,90))
            self.assertNotEqual(d['sha256'],d['originalSha256'])
            self.assertTrue((project/d['originalPath']).exists())
            entries=[json.loads(x) for x in (project/'asset-ledger.jsonl').read_text().splitlines()]
            self.assertEqual(entries[0]['path'],d['path'])

    def test_failed_transcode_never_enters_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.node("try{await o.downloadAsset({project:input,candidate:{provider:'commons',title:'Bad',creator:'test',license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/',sourceUrl:'https://commons.wikimedia.org/wiki/File:Bad.webm',downloadUrl:'https://upload.wikimedia.org/bad.webm'},requestFn:async()=>new Response('broken',{headers:{'content-type':'video/webm'}}),transcodeVideo:true});console.log(false);}catch(e){console.log(JSON.stringify(!fs.existsSync(input+'/asset-ledger.jsonl')));}",tmp)
            self.assertTrue(d)

    def test_actual_duration_is_capped_when_api_understates_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=160x90:r=10:d=0.8','-c:v','libx264',str(src)],check=True,capture_output=True)
            d=self.node("const bytes=fs.readFileSync(input.src);const asset=await o.downloadAsset({project:input.root,candidate:{provider:'commons',title:'Synthetic duration test',creator:'test',license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/',sourceUrl:'https://commons.wikimedia.org/wiki/File:Test.mp4',downloadUrl:'https://upload.wikimedia.org/test.mp4',durationSeconds:.4},requestFn:async()=>new Response(bytes,{headers:{'content-type':'video/mp4'}}),transcodeVideo:true,maxDuration:.45});console.log(JSON.stringify(asset));",{'src':str(src),'root':tmp})
            self.assertLessEqual(d['durationSeconds'],.45)
            self.assertGreater(d['originalDurationSeconds'],.45)
            self.assertTrue((root/d['originalPath']).exists())
            self.assertNotEqual(d['sha256'],d['originalSha256'])

    def test_candidate_sheet_uses_only_preview_and_keeps_license(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.node("const c=m.normalizeCandidate({provider:'commons',title:'Paper',creator:'A',sourceUrl:'https://commons.wikimedia.org/wiki/File:Paper.png',downloadUrl:'https://upload.wikimedia.org/orig.png',thumbnailUrl:'https://upload.wikimedia.org/thumb.png',mime:'image/png',license:'CC0',licenseUrl:'https://creativecommons.org/publicdomain/zero/1.0/'},'photo');const calls=[];await m.candidateSheet({query:'paper',candidates:[c]},input.dir,{requestFn:async url=>{calls.push(url);return new Response(Buffer.from(input.png,'base64'),{headers:{'content-type':'image/png'}});}});console.log(JSON.stringify({calls,sheet:fs.existsSync(input.dir+'/candidates.png'),saved:JSON.parse(fs.readFileSync(input.dir+'/candidates.json','utf8'))}));",{'dir':tmp,'png':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a9sAAAAASUVORK5CYII='})
            self.assertTrue(d['sheet']);self.assertEqual(len(d['calls']),1);self.assertIn('thumb.png',d['calls'][0])
            self.assertEqual(d['saved']['candidates'][0]['license'],'CC0')


if __name__=='__main__':unittest.main()
