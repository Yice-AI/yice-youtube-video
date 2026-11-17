"""首批视觉词汇：逐配方/转场/质感层浏览器执行，以及接口异常路径。"""
import json
from pathlib import Path
import subprocess
import unittest

TEMPLATE=Path(__file__).resolve().parents[1]/'template'
EXAMPLES=json.loads((TEMPLATE/'vocab-examples.json').read_text())


class VocabularyBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run=subprocess.run(['node',str(Path(__file__).with_name('vocab-browser.mjs'))],capture_output=True,text=True,timeout=120)
        if run.returncode:
            raise RuntimeError(run.stderr[-1800:])
        cls.results=json.loads(run.stdout)


def browser_case(key):
    def test(self):
        self.assertTrue(self.results[key]['ok'],self.results[key])
    return test


for _kind,_names in [('recipe',EXAMPLES),('transition',['directional-wipe','cinematic-zoom','grid-pixelate-wipe','halftone-dissolve','flash-through-white','chromatic-aberration-wipe']),('layer',['grain-overlay','light-sweep-pass','notification-stack']),('layout',['title-free'])]:
    for _name in _names:
        setattr(VocabularyBrowserTests,'test_'+_kind+'_'+_name.replace('-','_'),browser_case(_kind+':'+_name))


class VocabularyPropsTests(unittest.TestCase):
    def prepare(self,scene):
        code=f"import {{prepareVocab}} from {json.dumps((TEMPLATE/'vocab-props.mjs').as_uri())};"+"let s='';for await(const c of process.stdin)s+=c;try{console.log(JSON.stringify({ok:true,value:prepareVocab(JSON.parse(s))}));}catch(e){console.log(JSON.stringify({ok:false,error:e.message}));}"
        run=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(scene),capture_output=True,text=True,check=True)
        return json.loads(run.stdout)

    def test_unknown_legacy_recipe_stays_compatible(self):
        scene={'recipe':'photo-word','media':[{'src':'x.png'}],'spec':{'word':{'text':'原有配方'}}}
        self.assertEqual(self.prepare(scene)['value']['media'],scene['media'])

    def test_non_yice_stage_rejected(self):
        self.assertFalse(self.prepare({'recipe':'headline-slam','props':{'text':'测试'},'stage':'paper-gray'})['ok'])

    def test_show_title_requires_boolean(self):
        self.assertFalse(self.prepare({'recipe':'headline-slam','props':{'text':'测试','showTitle':'false'}})['ok'])

    def test_rank_requires_source(self):
        props={**EXAMPLES['rank-race'],'source':''}
        self.assertFalse(self.prepare({'recipe':'rank-race','props':props})['ok'])

    def test_rank_requires_multiple_observations(self):
        props={**EXAMPLES['rank-race'],'frames':EXAMPLES['rank-race']['frames'][:1]}
        self.assertFalse(self.prepare({'recipe':'rank-race','props':props})['ok'])

    def test_rank_accepts_changing_top_three_membership(self):
        props={**EXAMPLES['rank-race'],'frames':[{'t':0,'items':[{'label':'照片01','value':90}]},{'t':1,'items':[{'label':'照片04','value':93}]}]}
        self.assertTrue(self.prepare({'recipe':'rank-race','props':props})['ok'])

    def test_rank_rejects_duplicate_members(self):
        props={**EXAMPLES['rank-race'],'frames':[{'t':0,'items':[{'label':'照片01','value':90},{'label':'照片01','value':91}]},{'t':1,'items':[{'label':'照片02','value':93}]}]}
        self.assertFalse(self.prepare({'recipe':'rank-race','props':props})['ok'])

    def test_cursor_log_and_zoom_validation(self):
        props={**EXAMPLES['cursor-zoom'],'zoom':3}
        self.assertFalse(self.prepare({'recipe':'cursor-zoom','props':props})['ok'])
        props={**EXAMPLES['cursor-zoom'],'cursorLog':[{'t':0,'x':2500,'y':100}]}
        self.assertFalse(self.prepare({'recipe':'cursor-zoom','props':props})['ok'])

    def test_missing_media_rejected(self):
        self.assertFalse(self.prepare({'recipe':'device-stage','props':{'chrome':'browser'}})['ok'])

    def test_unsupported_layer_rejected(self):
        self.assertFalse(self.prepare({'recipe':'headline-slam','props':{'text':'测试'},'layers':[{'kind':'galaxy'}]})['ok'])

    def test_laptop_bounds_are_enforced(self):
        self.assertFalse(self.prepare({'recipe':'laptop-3d','props':{'media':'x.mp4','angle':13}})['ok'])

    def test_social_account_is_not_made_public_by_normalization(self):
        result=self.prepare({'recipe':'social-post','props':EXAMPLES['social-post']})
        self.assertNotIn('publicAccount',result['value']['props'])


def props_case(name):
    def test(self):
        result=self.prepare({'recipe':name,'props':EXAMPLES[name]})
        self.assertTrue(result['ok'],result)
        for media in result['value']['media']:
            self.assertTrue(media['src'])
    return test


for _name in EXAMPLES:
    setattr(VocabularyPropsTests,'test_example_'+_name.replace('-','_'),props_case(_name))


if __name__=='__main__':unittest.main()
