"""Phase 1 本机离线实证。设置 YICE_PHASE1_EVIDENCE 可保留浏览器与封面产物。"""
from contextlib import contextmanager
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
harvest = importlib.import_module("harvest-episode-footage")
scout = importlib.import_module("scout-video-scenes")
PLAYWRIGHT = Path(os.environ.get("YICE_PLAYWRIGHT_MODULE") or
                  "/opt/homebrew/lib/node_modules/openclaw/node_modules/playwright-core")


@contextmanager
def fixture_project(name):
    if evidence := os.environ.get("YICE_PHASE1_EVIDENCE"):
        project = Path(evidence).resolve() / name
        project.mkdir(parents=True, exist_ok=True)
        yield project
    else:
        with tempfile.TemporaryDirectory() as directory:
            yield Path(directory).resolve()


def probe(file):
    return json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(file)]
    ))


class Phase1Tests(unittest.TestCase):
    def node(self, project, source, **env):
        command = ["node", "--input-type=module", "-e", source, str(project)]
        result = subprocess.run(command, cwd=SCRIPTS, capture_output=True, text=True, timeout=120,
                                env={**os.environ, **env})
        self.assertEqual(result.returncode, 0, result.stderr[-3500:])
        return json.loads(result.stdout)

    def test_thumbnail_candidates_warn_export_and_refuse_duplicate(self):
        with fixture_project("thumbnail") as project:
            fake = project / "fake-image2.py"
            fake.write_text(r'''
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

args = sys.argv[1:]
base = Path(args[args.index("-o")+1])
with (base.parents[2]/"calls.jsonl").open("a") as log:
    log.write(json.dumps(args)+"\n")
outputs = []
font = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
for i, (bg, accent) in enumerate((("#172d45", "#43d9df"), ("#211542", "#cc9bf5"), ("#283722", "#d4e777")), 1):
    target = base.with_name(f"candidate-{i}.png")
    image = Image.new("RGB", (1920,1080), bg)
    draw = ImageDraw.Draw(image)
    draw.ellipse((1100,-120,2060,840), fill=accent)
    draw.rounded_rectangle((126,168,510,243), radius=22, fill=accent)
    draw.text((160,182), "YICE VIDEO LAB", font=ImageFont.load_default(size=44), fill=bg)
    draw.text((110,350), "SOURCE", font=ImageFont.load_default(size=174), fill="white")
    draw.text((110,540), "TO SCREEN", font=ImageFont.load_default(size=174), fill="white")
    draw.line((135,801,1030,801), fill=accent, width=8)
    draw.text((135,860), "Phase 1 / local fixture", font=ImageFont.load_default(size=56), fill=accent)
    if i == 1:
        draw.rectangle((1520,900,1890,1050), fill="black")
        draw.text((1560,910), "12:34", fill="white", font=ImageFont.truetype(font, 100))
    image.save(target)
    outputs.append({"output":str(target),"width":1920,"height":1080,"model":"fixture","elapsed_seconds":0})
print(json.dumps({"outputs":outputs,"candidates":3,"attempts":3}))
''', encoding="utf-8")
            entry = [str(SCRIPTS / "thumbnail.sh"), "--project", str(project), "--json"]
            generation = ["--batch", "fixture", "--title", "采集画质", "--summary", "本地验收。",
                          "--image2-script", str(fake)]
            result = subprocess.run([*entry, *generation], text=True, capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            batch = json.loads(result.stdout)
            self.assertEqual((batch["candidates"], batch["attempts"]), (3, 3))
            calls = project / "calls.jsonl"
            call = json.loads(calls.read_text())
            self.assertIn('仅供选择实物题材', call[3])
            self.assertIn('本地验收。', call[3])
            self.assertIn('右下 x>78%、y>80%', call[3])
            self.assertEqual(call, [
                "--title", "采集画质", "--summary", call[3], "--role", "thumbnail", "--guard", "light",
                "--thumb-guard", "r_plus", "--candidates", "3",
                "-o", str(project/"thumbnails/fixture/candidate.png"), "--json",
            ])
            invalid = subprocess.run([*entry, '--title','演示评测', '--hook','一二三四五六七八九十多一个字',
                                      '--summary','实际案例', '--image2-script',str(fake)],
                                     text=True,capture_output=True,timeout=15)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn('10 个汉字', invalid.stderr)
            first = batch["outputs"][0]
            if os.access(scout.OCR, os.X_OK):
                self.assertTrue(first["watermark_warning"], first)
                self.assertIn("12:34", first["watermark_text"])
                self.assertFalse(batch["outputs"][1]["watermark_warning"])
            with Image.open(batch["path"]) as sheet:
                self.assertEqual(sheet.size, (1224, 1420))
                self.assertNotEqual(sheet.getpixel((0,0)), sheet.getpixel((50,150)))
                if first["watermark_warning"]:
                    self.assertEqual(sheet.getpixel((690,315)), (246,184,83))
            duplicate = subprocess.run([*entry, *generation], text=True, capture_output=True, timeout=15)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("拒绝覆盖", duplicate.stderr)
            result = subprocess.run([sys.executable, str(SCRIPTS/"produce_asset.py"), "--kind", "thumbnail",
                                     "--project", str(project), "--select", "2", "--json"],
                                    text=True, capture_output=True, check=True, timeout=30)
            export = json.loads(result.stdout)
            jpg = Path(export["path"])
            self.assertLess(export["bytes"], 2_000_000)
            self.assertEqual(hashlib.sha256(jpg.read_bytes()).hexdigest(), export["sha256"])
            with Image.open(jpg) as image:
                self.assertEqual((image.size,image.format), ((1920,1080),"JPEG"))
            for width,height in [(320,180),(168,94)]:
                with Image.open(jpg.with_name(f"thumbnail-selected-{width}p.png")) as small:
                    self.assertEqual(small.size, (width,height))
            ledger = [json.loads(line) for line in (project/"asset-ledger.jsonl").read_text().splitlines()]
            self.assertEqual([(row["kind"],row["sourceType"]) for row in ledger], [("thumbnail","image2")]*2)
            self.assertEqual(len(calls.read_text().splitlines()), 1)

    @unittest.skipUnless(PLAYWRIGHT.exists(), "需要本机 Playwright 和 Chrome")
    def test_browser_lazy_scroll_and_native_github_and_site_video(self):
        with fixture_project("browser") as project:
            clip = project/"input.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=s=320x180:r=15:d=2",
                            "-f","lavfi","-i","sine=d=2","-c:v","libx264","-c:a","aac",str(clip)],check=True)
            result = self.node(project, r'''
import {createServer} from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {capturePage} from './capture-web.mjs';
import {collectEntity,downloadEntityFile} from './collect-entity.mjs';

const project=process.argv[1];
const clip=fs.readFileSync(path.join(project,'input.mp4'));
const img='<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="#00ff00"/></svg>';
const html=`<body style="margin:0;background:white"><header style="position:fixed;top:0;z-index:2;background:blue;color:white">Fixture navigation</header>
<main class="markdown-body" style="height:3200px;padding-top:55px"><h1>Local browser proof</h1>
<img id="lazy" loading="lazy" src="/lazy.svg" width="80" height="80" style="display:block">
<video preload="none" width="640" height="360"><source src="/clip.mp4" type="video/mp4"></video>
<a href="/user-attachments/assets/demo">README video link</a>
<div style="height:1000px"></div><img id="observed" width="80" height="80"></main>
<div id="cookie-fixture" role="dialog" style="position:fixed;inset:0;background:magenta;z-index:5"></div>
<script>new IntersectionObserver(entries=>{if(entries[0].isIntersecting)observed.src='/observed.svg'}).observe(observed)</script></body>`;
const requests=[];
const server=createServer((req,res)=>{
  requests.push(req.url);
  if(req.url==='/clip.mp4'||req.url==='/user-attachments/assets/demo'){
    res.setHeader('content-type',req.url==='/clip.mp4'?'video/mp4':'application/octet-stream');
    res.end(clip);
  }else if(req.url.endsWith('.svg')){res.setHeader('content-type','image/svg+xml');res.end(img);}
  else{res.setHeader('content-type','text/html');res.end(html);}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
try{
  const url='http://127.0.0.1:'+server.address().port;
  const capture=await capturePage({project,url,seconds:6,details:true,theme:'light'});
  const irregular=await capturePage({project,url,id:'irregular',scale:1.37,scroll:false});
  const manifest=await collectEntity({name:'Fixture',github:'fixture/demo',out:project}, {
    capture:async ()=>({...capture,details:{...capture.details,demos:[],sections:[]}}),overview:async ()=>{},
  });
  let reject;
  try{await downloadEntityFile(url+'/clip.mp4',path.join(project,'image-only'));}
  catch(error){reject=error.message;}
  console.log(JSON.stringify({capture,irregular,manifest,requests,reject}));
}finally{await new Promise(resolve=>server.close(resolve));}
''', YICE_PLAYWRIGHT_MODULE=str(PLAYWRIGHT), YICE_MEDIA_OFFLINE="0")
            capture = result["capture"]
            self.assertEqual(capture["status"], "captured", capture.get("reason"))
            self.assertEqual(capture["scale"], 1.25)
            self.assertIn("/lazy.svg", result["requests"])
            self.assertIn("/observed.svg", result["requests"])
            still = project / capture["files"][0]["path"]
            with Image.open(still) as image:
                self.assertEqual(image.size, (1920,1080))
                self.assertEqual(image.getpixel((15,3))[:3], (0,0,255))
                self.assertEqual(image.getpixel((1500,500))[:3], (255,255,255))
                pixels = np.asarray(image.crop((0,110,110,270)).convert("RGB"))
                self.assertTrue(np.any((pixels == [0,255,0]).all(axis=2)))
            self.assertEqual(result["irregular"]["status"], "captured", result["irregular"].get("reason"))
            with Image.open(project / result["irregular"]["files"][0]["path"]) as image:
                self.assertEqual(image.size, (1920,1080))
            scroll = project / capture["files"][1]["path"]
            inspected = probe(scroll)
            scroll.with_name("scroll.ffprobe.json").write_text(json.dumps(inspected, indent=2)+"\n")
            demos = capture["details"]["demos"]
            self.assertEqual(demos[0]["method"], "direct_download")
            videos = [item for item in result["manifest"]["items"] if item["type"]=="github_readme_video"]
            self.assertEqual([item["status"] for item in videos], ["captured","captured"])
            self.assertEqual(result["reject"], "来源未返回图片")
            ledger = [json.loads(line) for line in (project/"asset-ledger.jsonl").read_text().splitlines()]
            self.assertEqual(sum(row["sourceType"]=="github_readme_video" for row in ledger), 2)
            for file, duration in [(scroll,6), *((project/row["path"],2) for row in [demos[0], *videos])]:
                metadata = probe(file)
                self.assertEqual(len(metadata["streams"]), 1)
                video = metadata["streams"][0]
                self.assertEqual((video["codec_type"],video["width"],video["height"],video["r_frame_rate"]),
                                 ("video",1920,1080,"30/1"))
                self.assertAlmostEqual(float(metadata["format"]["duration"]), duration, places=2)

    def test_stock_rejects_vertical_and_720p_and_records_success(self):
        with fixture_project("stock") as project:
            rows = self.node(project, r'''
import {pexelsCandidates,pixabayCandidates} from './stock-media.mjs';
const shapes=[[1080,1920],[1280,720],[1920,1080],[3840,2160]];
const variant=([width,height],i)=>({width,height,url:'https://example.invalid/'+i});
const p=shapes.map((shape,id)=>({id,video_files:[{...variant(shape,id),link:variant(shape,id).url,file_type:'video/mp4'}]}));
p[2].video_files.push({...variant(shapes[3],3),link:variant(shapes[3],3).url,file_type:'video/mp4'});
const q=shapes.map((shape,id)=>({id,videos:{medium:variant(shape,id)}}));
q[2].videos.large=variant(shapes[3],3);
console.log(JSON.stringify([pexelsCandidates({videos:p},'video'),pixabayCandidates({hits:q},'video')]));
''')
            for provider in rows:
                self.assertEqual([row["providerId"] for row in provider], [2,3])
                self.assertEqual(provider[0]["width"], 1920)
            def response(files):
                variants = [dict(file_type="video/mp4",width=w,height=h,link=f"https://example.invalid/{w}")
                            for w,h in files]
                return io.BytesIO(json.dumps({"videos":[dict(id=3,duration=8,video_files=variants)]}).encode())
            def encode(command, *, check):
                self.assertIn("17", command)
                Path(command[-1]).write_bytes(b"offline converted video")
            with patch.object(harvest.urllib.request, "urlopen", side_effect=[
                response([(1080,1920),(1280,720)]), response([(1080,1920),(1280,720),(1920,1080)]),
                io.BytesIO(b"source"),
            ]) as request, patch.object(harvest.subprocess, "run", side_effect=encode):
                records = harvest.fetch_pexels_1080p([("reject","vertical"),("keep","desktop")],project,"fixture")
            self.assertEqual(request.call_count, 3)
            self.assertEqual([row["slug"] for row in records], ["keep"])
            row = json.loads((project/"asset-ledger.jsonl").read_text())
            self.assertEqual((row["id"],row["sourceType"],row["provider"],row["path"],row["license"]),
                             ("keep","stock-footage","pexels","keep.mp4","Pexels License"))
            self.assertEqual(row["sha256"], hashlib.sha256((project/row["path"]).read_bytes()).hexdigest())

    def test_scout_rejects_burned_subtitles_and_keeps_clean_texture(self):
        with fixture_project("scout") as project:
            clean, burned = project/"clean.mp4", project/"burned.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=s=640x360:r=30:d=3",
                            "-c:v","libx264","-pix_fmt","yuv420p",str(clean)],check=True)
            overlay = project/"subtitle.png"
            label = Image.new("RGBA",(640,360))
            ImageDraw.Draw(label).text((320,322),"OLD SUBTITLE",anchor="mm",
                                       font=ImageFont.load_default(size=38),fill="white",
                                       stroke_width=3,stroke_fill="black")
            label.save(overlay)
            subprocess.run(["ffmpeg","-v","error","-y","-i",str(clean),"-i",str(overlay),"-filter_complex","overlay",
                            "-c:v","libx264","-pix_fmt","yuv420p",str(burned)],check=True)
            self.assertFalse(scout.frame_scores(scout.frame_at(clean,1))["has_burned_subtitle"])
            self.assertTrue(scout.frame_scores(scout.frame_at(burned,1))["has_burned_subtitle"])
            self.assertTrue(scout.scene_candidates([clean],1.5,.5,4,False))
            self.assertFalse(scout.scene_candidates([burned],1.5,.5,4,False))
            accepted = scout.scene_candidates([burned],1.5,.5,4,False,allow_burned_subtitles=True)
            self.assertTrue(accepted and all(row["has_burned_subtitle"] for row in accepted))

    def test_scout_rejects_window_that_straddles_hard_cut(self):
        with fixture_project("scout-cut") as project:
            source = project/"cut.mp4"
            first = Image.effect_noise((320,180),67).convert("RGB")
            reverse = Image.fromarray(255-np.asarray(first))
            self.assertGreater((scout.difference_hash(first)^scout.difference_hash(reverse)).bit_count(),24)
            rows = [(0.,first),(.5,first),(1.,reverse),(1.5,reverse),(2.,reverse)]
            with patch.object(scout,"sample_frames",return_value=iter(rows)), patch.object(scout,"probe_video",return_value=2.25):
                self.assertEqual(scout.scene_candidates([source],2,.5,4,False), [])


if __name__ == "__main__":
    unittest.main()
