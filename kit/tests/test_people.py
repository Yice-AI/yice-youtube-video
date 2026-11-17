import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys
import subprocess
from PIL import Image, ImageDraw

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from people_add import add_person, validate


class PeopleTests(unittest.TestCase):
    def fixture(self, root):
        file=Path(root)/'person.png';im=Image.new('RGBA',(160,240));ImageDraw.Draw(im).rectangle((35,20,120,225),fill=(170,50,30,255));im.save(file);return file

    def provenance(self):return {'sourceUrl':'https://example.com/official-person','license':'Official press portrait; rights reserved','sourceType':'official_press'}

    def test_uniform_canvas_border_source_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=self.fixture(tmp);original=source.read_bytes();library=Path(tmp)/'private';item=add_person('Example Person',source,'default','笑',library,self.provenance())
            with Image.open(library/item['path']) as im:
                self.assertEqual(im.size,(1080,1080));self.assertEqual(im.getpixel((0,0))[3],0)
                self.assertTrue(any(r>=244 and g>=244 and b>=244 and a==255 for r,g,b,a in im.getdata()))
                self.assertTrue(any(r==170 and g==50 and b==30 and a==255 for r,g,b,a in im.getdata()))
            self.assertEqual(source.read_bytes(),original);self.assertEqual(item['processing']['whiteBorderPx'],10)
            self.assertFalse(item['processing']['expressionAltered']);self.assertTrue(Path(item['sourcePath']).exists())
            self.assertEqual(json.loads((library/'asset-ledger.jsonl').read_text())['tier'],'default')

    def test_same_photo_cannot_be_relabeled_to_fill_another_mood(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=self.fixture(tmp);library=Path(tmp)/'private';add_person('Person',source,'default','笑',library,self.provenance())
            with self.assertRaisesRegex(ValueError,'改标签'):add_person('Person',source,'default','皱眉',library,self.provenance())
            self.assertEqual(len(json.loads((library/'manifest.json').read_text())['items']),1)

    def test_same_asset_retry_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=self.fixture(tmp);library=Path(tmp)/'private'
            a=add_person('Person',source,'commentary','思考',library,{'sourceUrl':'https://example.com/news','license':'rights reserved'})
            b=add_person('Person',source,'commentary','思考',library,{'sourceUrl':'https://example.com/news','license':'rights reserved'})
            self.assertEqual(a['sha256'],b['sha256']);self.assertEqual(len(json.loads((library/'manifest.json').read_text())['items']),1)

    def test_invalid_default_provenance_and_mood_are_rejected(self):
        for tier,mood,source in [('wrong','笑',self.provenance()),('default','哭',self.provenance()),('default','笑',{'sourceUrl':'https://example.com','license':'unknown'})]:
            with self.assertRaises(ValueError):validate('Person',tier,mood,source)

    def test_no_subject_is_failure_not_an_opaque_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'opaque.png';Image.new('RGB',(160,240),'red').save(source)
            def no_mask(a,b):Image.open(a).save(b);return {'backend':'fake-no-subject'}
            with self.assertRaisesRegex(ValueError,'透明背景'):add_person('Person',source,'default','笑',Path(tmp)/'private',self.provenance(),backend=no_mask)
            self.assertFalse((Path(tmp)/'private/manifest.json').exists())

    def test_transparent_fringe_is_not_mistaken_for_removed_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'photo.png';im=Image.new('RGBA',(160,240),'gray');im.putpixel((0,0),(0,0,0,0));im.save(source);calls=[]
            def segment(a,b):
                calls.append(1);mask=Image.new('RGBA',(160,240));ImageDraw.Draw(mask).rectangle((40,30,120,220),fill='red');mask.save(b);return {'backend':'segmented'}
            item=add_person('Person',source,'default','笑',Path(tmp)/'private',self.provenance(),backend=segment)
            self.assertEqual(calls,[1]);self.assertEqual(item['processing']['backend'],'segmented')

    def test_crop_preserves_original_and_rejects_outside_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=self.fixture(tmp);library=Path(tmp)/'private'
            item=add_person('Person',source,'default','笑',library,self.provenance(),crop=(20,10,120,225))
            self.assertEqual(item['processing']['crop'],(20,10,120,225))
            with self.assertRaisesRegex(ValueError,'裁切'):add_person('Person',source,'default','笑',library,self.provenance(),crop=(150,0,50,80))

    def test_reaction_binding_keeps_commentary_tier_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=self.fixture(tmp);library=Path(tmp)/'private';root=Path(tmp)/'episode';root.mkdir()
            add_person('Person',source,'commentary','思考',library,{'sourceUrl':'https://example.com/news','license':'rights reserved'})
            module=Path(__file__).parents[1]/'template/people-assets.mjs'
            code="import fs from 'node:fs';const {bindPersonScene}=await import(process.argv[1]);const [library,root]=JSON.parse(fs.readFileSync(0,'utf8'));const scene=bindPersonScene({id:'S1',recipe:'reaction-cutout',props:{personRef:{name:'Person',mood:'思考'}}},{root,library});console.log(JSON.stringify({scene,ledger:JSON.parse(fs.readFileSync(root+'/asset-ledger.jsonl','utf8'))}));"
            data=json.loads(subprocess.check_output(['node','--input-type=module','-e',code,module.as_uri()],input=json.dumps([str(library),str(root)]),text=True))
            self.assertEqual(data['scene']['props']['tier'],'commentary')
            self.assertEqual(data['ledger']['tier'],'commentary');self.assertEqual(data['ledger']['role'],'body')
            self.assertEqual(data['ledger']['sourceUrl'],'https://example.com/news')


if __name__=='__main__':unittest.main()
