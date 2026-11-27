"""Offline native-HTML, X media, picture processing and asset-ledger acceptance."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
import json
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
harvest=import_module('harvest-showcase-media')


def synth(path, source, seconds):
    harvest.ffmpeg(['-f','lavfi','-i',source,'-t',seconds,'-an','-c:v','libx264',
                    '-preset','ultrafast','-pix_fmt','yuv420p','-threads','2',path])


class QuietServer(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


class HarvestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        cls.motion=cls.root/'motion.mp4'
        synth(cls.motion,'testsrc2=s=320x180:r=30',7)
        cls.portrait=cls.root/'portrait.mp4'
        synth(cls.portrait,'testsrc2=s=180x320:r=30',5)
        cls.white=cls.root/'white.mp4'
        synth(cls.white,'color=white:s=320x180:r=30',6)

    def test_live_offline_dom_scripts_and_blocklist(self):
        (self.root/'index.html').write_text("""<title>Local research</title>
          <video><source src="motion.mp4"></video><a href="https://www.youtube.com/clip.mp4">clip</a>
          <script>const manifest={"preview":"assets/teaser.mov?v=1"};
          const v=document.createElement('video');v.dataset.src="late.webm";document.body.append(v);</script>""")
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietServer,directory=self.root))
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            page=harvest.browser_job(dict(url=f'http://127.0.0.1:{server.server_port}/index.html',
                                          blocked=harvest.BLOCKED_CREATOR_DOMAINS))
        finally:
            server.shutdown();server.server_close();thread.join()
        page['base']='https://research.github.io/project/'
        self.assertEqual(set(harvest.extract_links(page)),{page['base']+n for n in
                                                          ['motion.mp4','assets/teaser.mov?v=1','late.webm']})
        for host in ['youtu.be','m.youtube.com','bilibili.com','cdn.bilivideo.com','douyin.com','www.tiktok.com']:
            self.assertFalse(harvest.video_url(f'https://{host}/clip.mp4'))
        self.assertTrue(harvest.video_url('https://lab.github.io/demo.webm?token=123'))

    def test_extensionless_native_and_redirect_policy(self):
        attachment='https://github.com/user-attachments/assets/12345678-1234-1234-1234-123456789abc'
        self.assertTrue(harvest.video_url(attachment))
        links=harvest.extract_links(dict(base='https://research.github.io/',links=[attachment],
            native=['/binary/clip','https://v.douyin.com/media','blob:https://research.github.io/xxx'],
            scripts=''))
        self.assertEqual(links,[attachment,'https://research.github.io/binary/clip'])
        with self.assertRaises(ValueError):
            harvest.SourceRedirect().redirect_request(None,None,302,'',{},'https://video.bilivideo.com/clip.mp4')

    def test_short_download_resumes_exact_bytes_and_enforces_limit(self):
        def response(data,status,headers):
            stream=BytesIO(data);stream.status=status;stream.headers=headers;return stream
        first=response(b'abc',200,{'Content-Length':'6','ETag':'"version"'})
        rest=response(b'def',206,{'Content-Range':'bytes 3-5/6'})
        opener=Mock()
        opener.open.side_effect=[first,rest,response(b'',200,{'Content-Length':'1000'})]
        with patch.object(harvest.request,'build_opener',return_value=opener):
            target=self.root/'raw-source.mp4'
            harvest.download('https://lab.github.io/raw.mp4',target,20)
            self.assertEqual(target.read_bytes(),b'abcdef')
            resumed=opener.open.call_args_list[1].args[0]
            self.assertEqual(resumed.get_header('Range'),'bytes=3-')
            with self.assertRaisesRegex(ValueError,'超过下载上限'):
                harvest.download('https://lab.github.io/raw.mp4',target,20)

    def test_x_highest_bitrate_normalized_cli_and_degradation(self):
        base='https://video.twimg.com/demo/'
        tweet=dict(id='123',author=dict(screenName='Lab'),media=[dict(type='video',video_info=dict(variants=[
            dict(content_type='video/mp4',bitrate=300,url=base+'low.mp4'),
            dict(content_type='video/mp4',bitrate=1200,url=base+'high.mp4')]))])
        self.assertEqual(harvest.tweet_media([tweet])[0],dict(url=base+'high.mp4',sourceName='@Lab',sourceUrl='https://x.com/Lab/status/123'))
        tweet['media']=[dict(type='video',url=base+'best.mp4')]
        self.assertEqual(harvest.tweet_media(dict(data=[tweet]))[0]['url'],base+'best.mp4')
        self.assertEqual(harvest.collect_x('demo',[],self.root/'missing'),([], 'cli_unavailable'))
        with patch.object(subprocess,'run',side_effect=subprocess.TimeoutExpired('twitter',1)):
            self.assertEqual(harvest.collect_x('demo',[],sys.executable),([], 'unavailable'))

    def test_landscape_portrait_and_duration(self):
        for source,mode in [(self.motion,'crop'),(self.portrait,'blur_dark')]:
            output=self.root/(mode+'.mp4')
            self.assertEqual(harvest.normalize_showcase_video(source,output),mode)
            info=harvest.probe(output)
            self.assertEqual((info['width'],info['height'],info['fps']),(1920,1080,'30/1'))
            if mode=='crop':
                self.assertGreater(info['duration'],6)
            else:
                raw=harvest.ffmpeg(['-ss',1,'-i',output,'-frames:v','1','-vf','scale=160:90','-pix_fmt','rgb24','-f','rawvideo','-'])
                rgb=np.frombuffer(raw,dtype=np.uint8).reshape(90,160,3)
                self.assertGreater(rgb[:,:40].std(),8)
                self.assertLess(rgb[:,:40].mean(),rgb[:,66:94].mean())

    def test_rank_motion_over_still_white_and_black(self):
        self.assertEqual(harvest.rank_highlights(self.white),[])
        black=self.root/'black.mp4';synth(black,'color=black:s=320x180:r=30',5)
        self.assertEqual(harvest.rank_highlights(black),[])
        mixed=self.root/'mixed.mp4'
        harvest.ffmpeg(['-i',self.white,'-i',self.motion,'-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]',
                        '-map','[v]','-threads','2',mixed])
        choice=harvest.rank_highlights(mixed)[0]
        self.assertGreaterEqual(choice['start'],6)
        self.assertEqual(choice['end']-choice['start'],4.5)

    def test_pool_sheet_ledger_and_repeat(self):
        url='https://example.github.io/lab/'
        args=SimpleNamespace(output=self.root/'pool',urls=[url],plan=None,x_query=None,x_urls=[],
                             max_mb=120,max_seconds=25,rank_highlights=True,top=1)
        with patch.object(harvest,'discover',return_value=('Example Lab',[url+'clip.mp4'])), \
             patch.object(harvest,'download',side_effect=lambda _,target,limit:shutil.copy2(self.motion,target)) as download:
            result=harvest.harvest(args)
            second=harvest.harvest(args)
            self.assertEqual(download.call_count,1)
        self.assertEqual(result['issues'],[])
        self.assertEqual(len(second['highlights']),1)
        row=result['highlights'][0]
        self.assertEqual(row['sourceUrl'],url);self.assertEqual(row['sourceName'],'Example Lab')
        self.assertEqual(row['usage'],'editorial_commentary_muted')
        self.assertEqual(harvest.probe(args.output/row['path'])['duration'],4.5)
        self.assertTrue((args.output/'showcase-candidates.jpg').read_bytes().startswith(b'\xff\xd8'))
        stored=[json.loads(s) for s in (args.output/'asset-ledger.jsonl').read_text().splitlines()]
        self.assertEqual(len(stored),2)
        self.assertEqual(json.loads((args.output/'manifest.json').read_text())['highlights'][0]['id'],row['id'])


if __name__=='__main__':
    unittest.main()
