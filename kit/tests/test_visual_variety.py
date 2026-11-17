"""单调度门：每条拦截规则、精确边界与真实 CLI 写盘。"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'template'


def fixture():
    sources = ['recording', 'code_animation', 'third_party', 'web_capture']
    # 既有规则分别隔离验证；新增容器/版式默认门由专用用例验证。
    return {'episode': {'id': 'ep02', 'end': 40, 'visual': {'limits': {'minRecordingContainerKinds': 0,'minTitleFreeRatio':0,'maxConsecutiveLayout':1000}}}, 'beats': {'scenes': [
        {'id': f'S{i}', 'recipe': f'r{i}', 'start': i * 10, 'end': (i + 1) * 10,
         'sourceType': source, 'enter': ['cut', 'cut', 'push', 'lift'][i]}
        for i, source in enumerate(sources)]},
        'previous': {'episodeId': 'ep01', 'recipeCounts': {'r0': 1}}}


class VisualVarietyTests(unittest.TestCase):
    def evaluate(self, data):
        code = f"import {{evaluateVisualVariety}} from {json.dumps((TEMPLATE/'check-visual.mjs').as_uri())};" + \
               "let s='';for await(const c of process.stdin)s+=c;console.log(JSON.stringify(evaluateVisualVariety(JSON.parse(s))));"
        result = subprocess.run(['node', '--input-type=module', '-e', code], input=json.dumps(data),
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def assert_only(self, data, code):
        result = self.evaluate(data)
        self.assertFalse(result['ok'])
        self.assertEqual([f['code'] for f in result['findings']], [code])
        return result

    def stretch_first(self, data, end):
        scenes = data['beats']['scenes']; bounds = [0, end, 30, 35, 40]
        for i, scene in enumerate(scenes): scene.update(start=bounds[i], end=bounds[i + 1])

    def test_complete_pass(self):
        result = self.evaluate(fixture())
        self.assertTrue(result['ok'])
        self.assertEqual(result['fingerprint']['nonRecordingRatio'], .75)
        self.assertEqual(result['fingerprint']['sourceDurations']['recording'], 10)

    def test_built_entity_reference_is_validated_using_its_resolved_media(self):
        data=fixture();scene=data['beats']['scenes'][3];scene.update(recipe='news-card',props={'entity':{'manifest':'entity/manifest.json','item':'proof'}})
        data['buildReport']=[{'id':scene['id'],'resolvedProps':{'source':'Official proof','date':'2026-11-17','shot':'assets/proof.png'}}]
        self.assertTrue(self.evaluate(data)['ok'])

    def test_long_bare_recording(self):
        data = fixture(); self.stretch_first(data, 23)
        self.assert_only(data, 'bare_recording_too_long')

    def test_recording_segments_are_merged_across_cuts(self):
        data = fixture(); scenes = data['beats']['scenes']
        scenes[:1] = [{**scenes[0], 'id': f'R{i}', 'recipe': f'rec{i}', 'start': i*8, 'end': (i+1)*8} for i in range(3)]
        scenes[3].update(start=24, end=30); scenes[4].update(start=30, end=35); scenes[5].update(start=35, end=40)
        result = self.assert_only(data, 'bare_recording_too_long')
        self.assertEqual(result['fingerprint']['bareRecordingRuns'][0]['duration'], 24)

    def test_low_non_recording_ratio_despite_overlay(self):
        data = fixture(); self.stretch_first(data, 25)
        data['beats']['scenes'][0]['overlays'] = [{'at': 10, 'duration': 1}]
        self.assert_only(data, 'non_recording_ratio_low')

    def test_less_than_three_sources(self):
        data = fixture()
        for scene in data['beats']['scenes'][1:]: scene['sourceType'] = 'code_animation'
        self.assert_only(data, 'source_types_low')

    def test_recipe_more_than_four_times(self):
        data = fixture(); data['previous'] = None
        scenes = data['beats']['scenes']; scenes.append(copy.deepcopy(scenes[-1]))
        for i, scene in enumerate(scenes): scene.update(id=f'S{i}', recipe='same', start=i*8, end=(i+1)*8)
        self.assert_only(data, 'recipe_repeated')

    def test_default_hard_cuts_are_allowed(self):
        data = fixture()
        for scene in data['beats']['scenes']: scene['enter'] = 'cut'
        self.assertTrue(self.evaluate(data)['ok'])

    def test_transition_minimum_remains_configurable(self):
        data = fixture();data['limits']={'minTransitionKinds':3}
        for scene in data['beats']['scenes']: scene['enter'] = 'cut'
        self.assert_only(data, 'transition_kinds_low')

    def test_previous_overlap_more_than_seventy_percent(self):
        data = fixture(); data['previous']['recipeCounts'] = {f'r{i}': 1 for i in range(3)}
        self.assert_only(data, 'previous_recipe_overlap')

    def test_no_new_recipe_even_when_overlap_threshold_relaxed(self):
        data = fixture(); data['previous']['recipeCounts'] = {f'r{i}': 1 for i in range(4)}
        data['limits'] = {'maxPreviousRecipeOverlap': 1}
        self.assert_only(data, 'no_new_recipe')

    def test_exact_twenty_seconds_is_allowed(self):
        data = fixture(); self.stretch_first(data, 20)
        self.assertTrue(self.evaluate(data)['ok'])

    def test_exact_forty_percent_and_seventy_percent_are_allowed(self):
        data = fixture(); data['previous']['recipeCounts'] = {f'r{i}': 1 for i in range(7)}
        data['beats']['scenes'] = [
            {'id': f'S{i}', 'recipe': f'r{i}', 'start': i*4, 'end': (i+1)*4,
             'sourceType': 'recording' if i < 6 else ['code_animation','third_party','web_capture','image2'][i-6],
             'enter': ['cut','push','lift'][i%3]} for i in range(10)]
        data['beats']['scenes'][2]['overlays'] = [{'at': 0, 'duration': 1}]
        result = self.evaluate(data)
        self.assertTrue(result['ok']); self.assertEqual(result['comparison']['overlap'], .7)
        self.assertEqual(result['fingerprint']['nonRecordingRatio'], .4)

    def test_insert_breaks_recording_and_counts_only_its_duration(self):
        data = fixture(); self.stretch_first(data, 25)
        data['beats']['scenes'][0]['inserts'] = [{'at': 10, 'duration': 2, 'sourceType': 'web_capture'}]
        result = self.evaluate(data)
        self.assertTrue(result['ok']); self.assertEqual(result['fingerprint']['nonRecordingSeconds'], 17)
        self.assertEqual([r['duration'] for r in result['fingerprint']['bareRecordingRuns']], [10, 13])

    def test_same_source_overlap_not_counted_twice_and_outside_overlay_ignored(self):
        data = fixture(); data['beats']['scenes'][0]['media'] = [
            {'sourceType': 'recording'}, {'sourceType': 'recording', 'at': 2, 'duration': 3}]
        data['beats']['scenes'][0]['overlays'] = [{'at': 12}]
        result = self.evaluate(data)
        self.assertEqual(result['fingerprint']['sourceDurations']['recording'], 10)
        self.assertEqual(result['fingerprint']['bareRecordingRuns'][0]['duration'], 10)

    def test_timing_driven_boundaries_and_anchor_overlays(self):
        data = fixture(); data['timing'] = []
        for i, scene in enumerate(data['beats']['scenes']):
            scene.pop('start'); scene.pop('end'); scene['sents'] = [f's{i}']
            data['timing'].append({'id': f's{i}', 'firstCharTime': i*10+.2, 'anchors': [{'phrase':'重点','time':i*10+3}]})
        data['beats']['scenes'][0]['spec'] = {'hls': [{'at': '@重点', 'duration': 2}]}
        result = self.evaluate(data)
        self.assertTrue(result['ok'])
        self.assertEqual([r['duration'] for r in result['fingerprint']['bareRecordingRuns']], [3,5])

    def test_cli_fails_before_hyperframes_and_writes_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = fixture(); self.stretch_first(data, 23)
            for name in ['check.mjs','check-video.mjs','check-visual.mjs','vocab-props.mjs']: shutil.copy2(TEMPLATE/name, root/name)
            (root/'episode.json').write_text(json.dumps(data['episode']))
            (root/'beats.json').write_text(json.dumps(data['beats']))
            run = subprocess.run(['node','check.mjs','--json'],cwd=root,capture_output=True,text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertEqual(json.loads(run.stdout)['visualVariety']['findings'][0]['code'], 'bare_recording_too_long')
            self.assertTrue((root/'visual-fingerprint.json').exists())
            self.assertNotIn('videoTransitions',json.loads((root/'check-report.json').read_text()))

    def container_fixture(self):
        data=fixture();data['episode'].pop('visual')
        first=data['beats']['scenes'][0]
        first.update(recipe='device-stage',end=5)
        data['beats']['scenes'].insert(1,{**first,'id':'B2','recipe':'laptop-3d','start':5,'end':10,'enter':'cut'})
        return data

    def test_two_recording_containers_pass_default_gate(self):
        result=self.evaluate(self.container_fixture())
        self.assertTrue(result['ok'])
        self.assertEqual(result['fingerprint']['recordingContainers'],['device-stage','laptop-3d'])

    def test_repeating_one_container_does_not_count_as_two(self):
        data=self.container_fixture();data['beats']['scenes'][1]['recipe']='device-stage'
        self.assert_only(data,'recording_containers_low')

    def test_container_showing_non_recording_does_not_count(self):
        data=self.container_fixture();data['beats']['scenes'][1]['sourceType']='web_capture'
        result=self.assert_only(data,'recording_containers_low')
        self.assertEqual(result['fingerprint']['recordingContainers'],['device-stage'])

    def test_numeric_bar_highlight_is_not_an_overlay_array(self):
        data=self.container_fixture();scene=data['beats']['scenes'][2]
        scene.update(recipe='bar-compare',props={'items':[{'label':'前','value':132},{'label':'后','value':14.8}],'highlight':1})
        self.assertTrue(self.evaluate(data)['ok'])

    def test_notification_starts_when_its_text_appears(self):
        data=fixture();self.stretch_first(data,23)
        data['beats']['scenes'][0]['layers']=[{'kind':'notification-stack','items':[{'text':'已完成','at':22}]}]
        result=self.assert_only(data,'bare_recording_too_long')
        self.assertEqual(result['fingerprint']['bareRecordingRuns'][0]['duration'],22)

    def layout_fixture(self, title_free):
        data=fixture();limits=data['episode']['visual']['limits']
        limits.pop('minTitleFreeRatio');limits.pop('maxConsecutiveLayout')
        examples=json.loads((TEMPLATE/'vocab-examples.json').read_text())
        names=['chat-bubble','terminal-run','bar-compare','progress-ring','social-post']
        data['beats']['scenes']=[{'id':f'L{i}','recipe':name,'start':i*8,'end':(i+1)*8,
            'sourceType':['recording','code_animation','third_party','web_capture','code_animation'][i],
            'enter':['cut','push','lift','pan','cut'][i],
            'props':{**examples[name],'showTitle':i not in title_free}} for i,name in enumerate(names)]
        return data

    def test_exact_forty_percent_title_free_and_three_repeated_layouts_pass(self):
        result=self.evaluate(self.layout_fixture({3,4}))
        self.assertTrue(result['ok'],result['findings'])
        self.assertEqual(result['fingerprint']['titleFreeRatio'],.4)
        self.assertEqual(max(r['count'] for r in result['fingerprint']['layoutRuns']),3)

    def test_too_few_title_free_scenes_are_blocked(self):
        self.assert_only(self.layout_fixture({2}),'title_free_ratio_low')

    def test_four_different_recipes_with_same_layout_are_blocked(self):
        data=self.layout_fixture({4});data['episode']['visual']['limits']['minTitleFreeRatio']=0
        result=self.assert_only(data,'layout_repeated')
        self.assertEqual(result['findings'][0]['details'][0]['count'],4)

    def test_statement_recipes_count_as_intrinsically_title_free(self):
        data=self.layout_fixture(set());examples=json.loads((TEMPLATE/'vocab-examples.json').read_text())
        for i,name in [(1,'headline-slam'),(3,'word-swap')]:
            data['beats']['scenes'][i].update(recipe=name,props=examples[name])
        result=self.evaluate(data)
        self.assertTrue(result['ok'],result['findings'])
        self.assertEqual(result['fingerprint']['titleFreeScenes'],2)


if __name__ == '__main__': unittest.main()
