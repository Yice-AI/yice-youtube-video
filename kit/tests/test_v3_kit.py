import functools
import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class V3Kit(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)

    def audit(self, name, *options, expected=0):
        output = self.project / name
        command = [SCRIPTS / "audit-v3.sh", "--project", self.project, "--out", output, *options]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        report = (output / "audit-v3-report.json").read_text()
        if os.getenv("YICE_V3_TEST_REPORTS"):
            dest = Path(os.environ["YICE_V3_TEST_REPORTS"])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (name+".json")).write_text(report)
        return json.loads(report)

    def movie(self, text):
        still = self.project / "source.png"
        image = Image.new("RGB", (1920,1080), "white")
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96)
        ImageDraw.Draw(image).text((320,390), text, fill="black", font=font)
        image.save(still)
        video = self.project / "movie.mp4"
        subprocess.run(["ffmpeg","-v","error","-loop","1","-framerate","30","-i",still,
                        "-f","lavfi","-i","sine=frequency=1000:sample_rate=48000",
                        "-af","volume=7dB","-t","6","-c:v","libx264","-pix_fmt","yuv420p",
                        "-preset","ultrafast","-c:a","aac",video], check=True)
        return video

    def test_record(self):
        (self.project / "index.html").write_text('<h1>Focus target</h1><button>Go</button><input>')
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.project)
        server = http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        actions = [{"type":"move","selector":"button"},{"type":"click","selector":"button"},
                   {"type":"type","selector":"input","text":"demo"},{"type":"scroll","dy":300,"ms":100}]
        result = subprocess.run([SCRIPTS/"produce-asset.sh","--kind","web-cam","--project",self.project,
                                 "--id","demo","--url",f"http://127.0.0.1:{server.server_port}/",
                                 "--seconds","2","--highlight","Focus target","--actions",json.dumps(actions)],
                                capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        entry = json.loads((self.project/"asset-ledger.jsonl").read_text())
        for key in ("path","trackPath","stillPath"):
            self.assertTrue((self.project/entry[key]).stat().st_size)
        track = json.loads((self.project/entry["trackPath"]).read_text())
        self.assertGreater(max(event["recommendedCamera"]["scale"] for event in track["events"]),1.3)
        self.assertTrue(self.audit("packed","--precheck","--target-seconds","12")["ok"])

    def test_missing(self):
        report = self.audit("shortage","--precheck",expected=1)
        self.assertEqual(report["missing"],5)

    def test_timeline(self):
        video = self.movie("Public evidence")
        timeline = self.project/"shots.json"
        for kind in ["real_video","text_card"]:
            timeline.write_text(json.dumps({"end":6,"shots":[{"id":"S1","kind":kind,"start":0,
                                             "end":6,"files":["source.png"]}]}))
            report = self.audit(kind,"--rendered",video,"--timeline",timeline,expected=int(kind=="text_card"))
            self.assertEqual(report["ocr"]["sample_count"],3)
            self.assertEqual(report["longest_text_card"],6 if kind=="text_card" else 0)
            self.assertTrue((self.project/kind/"contact-sheet.jpg").is_file())

    def test_ocr(self):
        report = self.audit("private","--rendered",self.movie("/Users/demo"),expected=1)
        self.assertTrue(any(hit["term"]=="/Users/" and hit["seconds"]==0 for hit in report["ocr"]["hits"]))
